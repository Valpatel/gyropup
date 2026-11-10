"""Actual historical receipt positives and bounded archive negatives; no CAD."""
import copy
import argparse
import gzip
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import shutil

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.evidence.manufacturing import retained_fit_history as history
from hardware.cad.legs import rs04_lug_checks as checks
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--full',action='store_true')
OPTIONS,REMAINING=parser.parse_known_args()


class HistoricalReceipt(unittest.TestCase):
    def test_real_full_historical_receipt_offline_and_temporary_cleanup(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No Git/network/child execution')):
            with history.captured_inputs() as captured:
                self.assertTrue(captured.is_dir())
                self.assertEqual(len(list(captured.rglob('*.*'))), 96)
                self.assertNotEqual(captured, ROOT)
        self.assertFalse(captured.exists())

    def test_default_actual_current_root_still_rejects_stale_receipt(self):
        data = json.loads((ROOT/history.ENGINEERING/'checks.json').read_text())
        with self.assertRaisesRegex(ValueError, 'Source/context closure changed'):
            checks.validate_receipt(data, ROOT/history.ENGINEERING)

    def test_known_failed_check_warning_and_readiness_cannot_be_promoted(self):
        data = json.loads((ROOT/history.ENGINEERING/'checks.json').read_text())
        mutations = [lambda d:d.update(status='pass'), lambda d:d.__setitem__('pass', True),
                     lambda d:next(c for c in d['checks'] if c['status']=='fail').update(status='pass'),
                     lambda d:d['checks'].pop()]
        mutations += [lambda d, flag=f:d.__setitem__(flag, True) for f in checks.READY_FLAGS]
        with history.captured_inputs() as captured:
            for mutate in mutations:
                changed = copy.deepcopy(data); mutate(changed)
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    checks.validate_receipt(changed, ROOT/history.ENGINEERING, captured)

    def test_actual_captured_source_and_context_changes_reject(self):
        with history.captured_inputs() as captured:
            data = json.loads((ROOT/history.ENGINEERING/'checks.json').read_text())
            for relative in ['hardware/cad/legs/fivebar.py', *checks.CONTEXT_FILES]:
                path = captured/relative; original=path.read_bytes()
                path.write_bytes(original+b'\nchanged')
                with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'Source/context'):
                    checks.validate_receipt(data, ROOT/history.ENGINEERING, captured)
                path.write_bytes(original)

    def test_fixed_anchors_and_current_execution_data_cannot_self_certify(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            paths=[history.ARCHIVE,history.MANIFEST,history.ENGINEERING/'checks.json',history.JOB/'job.json',
                   Path('hardware/cad/legs/rs04_lug_checks.py'),Path('hardware/cad/manufacturing/print_provenance.py')]
            for relative in paths:
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/relative,target)
            for relative in paths:
                path=root/relative;raw=path.read_bytes();path.write_bytes(raw+b'\n')
                with self.subTest(relative=relative),self.assertRaises(ValueError):
                    with history.captured_inputs(root):self.fail('Changed anchor/helper accepted')
                path.write_bytes(raw)


@unittest.skipUnless(OPTIONS.full,'Explicit full lightweight-runtime CI invocation required')
class FullArchive(unittest.TestCase):
    def test_real_complete_archive_and_default_packager_stale_negative(self):
        result=history.verify_archive()
        self.assertTrue(result['historical_archive_integrity'])
        self.assertFalse(result['engineering_pass'])
        self.assertEqual(result['engineering_counts'],{'pass':322,'warn':40,'fail':8})
        import importlib.util
        spec=importlib.util.spec_from_file_location('default_fit_negative',ROOT/'tools/evidence/manufacturing/package-fit-job.py')
        fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)
        with self.assertRaisesRegex(ValueError,'Source/context closure changed'):
            fit.verify(ROOT/history.JOB)


class CapturedDataParser(unittest.TestCase):
    def setUp(self):
        self.members=json.loads((ROOT/history.MANIFEST).read_text())['members']
        self.raw=(ROOT/history.ARCHIVE).read_bytes()

    def changed_archive(self, change):
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(self.raw)),mode='r:') as archive:
            rows=[(m,archive.extractfile(m).read()) for m in archive]
        change(rows)
        result=io.BytesIO()
        with tarfile.open(fileobj=result,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for member,raw in rows: archive.addfile(member,io.BytesIO(raw))
        return gzip.compress(result.getvalue(),mtime=0)

    def reject(self, raw):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises((ValueError,EOFError,tarfile.TarError,OSError)):
            history._unpack(raw,self.members,Path(temporary))

    def test_missing_duplicate_extra_alias_link_and_metadata_members_reject(self):
        mutations=[lambda rows:rows.pop(), lambda rows:rows.append(rows[0]),
                   lambda rows:setattr(rows[0][0],'name','../escape.py'),
                   lambda rows:setattr(rows[0][0],'name','./'+rows[0][0].name),
                   lambda rows:setattr(rows[0][0],'name','unrecorded.py'),
                   lambda rows:setattr(rows[0][0],'type',tarfile.SYMTYPE),
                   lambda rows:setattr(rows[0][0],'mode',0o755),
                   lambda rows:setattr(rows[0][0],'mtime',1),
                   lambda rows:rows.__setitem__(0,(rows[0][0],b'X'*len(rows[0][1])))]
        for change in mutations:
            with self.subTest(change=change):self.reject(self.changed_archive(change))

    def test_compressed_expansion_member_and_truncation_bounds_reject(self):
        self.reject(b'x'*(history.MAX_INPUT+1))
        self.reject(gzip.compress(b'x'*(history.MAX_RAW+1)))
        self.reject(self.raw[:len(self.raw)//2])
        members=copy.deepcopy(self.members);next(iter(members.values()))['bytes']=history.MAX_RAW+1
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            history._unpack(self.raw,members,Path(temporary))


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*REMAINING])
