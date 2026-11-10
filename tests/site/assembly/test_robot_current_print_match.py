"""Current contract controls; the expensive actual comparison is a separate action.

Pass --collection-folder to exercise accepted266 actual bytes without sampling.
No test fixture is an accepted geometry measurement or production acceptance.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools/site/assembly')]
import robot_current_print_match as current
import robot_current_print_acceptance as accepted
from robot_manufacturing import hip_geometry_match, mapping
from robot_project import prepared

parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--collection-folder',type=Path)
OPTIONS,REMAINING=parser.parse_known_args()


class CurrentContract(unittest.TestCase):
    def test_unaccepted_actual_contract_stays_disabled_without_fallback(self):
        collection={'source_commit':current.SOURCE}
        with patch('robot_print_match.source_guard',side_effect=AssertionError('No fallback')):
            for name in current.INSTANCES:
                self.assertIsNone(hip_geometry_match(ROOT,collection,name))
            self.assertIsNone(hip_geometry_match(ROOT,collection,'L.upper_link_front'))

    def test_unaccepted_hashes_are_external_not_supplied_by_proof(self):
        if accepted.PROOF_SHA256 is None:
            self.assertIsNone(accepted.ACCEPTANCE_SHA256)
        else:
            self.assertRegex(accepted.PROOF_SHA256,r'^[0-9a-f]{64}$')
            self.assertRegex(accepted.ACCEPTANCE_SHA256,r'^[0-9a-f]{64}$')
        self.assertEqual(current.INSTANCES,('L.hip_frame','R.hip_frame'))


@unittest.skipUnless(OPTIONS.collection_folder,'Explicit actual266 byte-preflight invocation required')
class ActualCollection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=OPTIONS.collection_folder.resolve()
        cls.collection=json.loads((cls.folder/'collection.json').read_text())

    def test_actual_complete_95_inputs_80_meshes_historical_receipt_and_project(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No Git/network/children')):
            binding=current.binding(ROOT,self.collection,self.folder)
            self.assertEqual(len(binding['current_inputs']),95)
            self.assertEqual(len(binding['protected_leg_mesh_sha256']),80)
            self.assertFalse(binding['historical']['engineering_pass'])
            self.assertEqual(binding['historical']['engineering_counts']['fail'],8)
            projects=prepared(ROOT,binding['original_sha256'])
            self.assertEqual(len(projects),1)
            self.assertEqual(projects[0]['kind'],'geometry-only')

    def test_actual_accepted_both_hip_mapper_keeps_other_part_pending(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No Git/network/children')):
            wheels=[side+'.'+part for side in ('L','R') for part in ('wheel_hub','wheel_tyre')]
            rows=mapping(ROOT,[*current.INSTANCES,'L.upper_link_front',*wheels],self.collection,collection_folder=self.folder)
        for name in current.INSTANCES:
            row=rows[name]
            self.assertEqual(row['geometry_match']['status'],'matched')
            self.assertEqual(row['geometry_match']['evidence']['sha256'],accepted.PROOF_SHA256)
            self.assertEqual(len(row['prepared_projects']),1)
            self.assertEqual(row['originals'][0]['sha256'],current.ORIGINAL_SHA)
            self.assertIn('322 pass / 40 warn / 8 fail',row['qualification'])
            self.assertIn('unsliced',row['qualification'])
        self.assertEqual(rows['L.upper_link_front']['geometry_match']['status'],'pending')
        self.assertNotIn('prepared_projects',rows['L.upper_link_front'])
        for name in wheels:
            self.assertEqual(rows[name]['kind'],'unresolved')
            self.assertNotIn('odrive-botwheel',json.dumps(rows[name]))
            self.assertEqual(rows[name]['design_reference']['nominal_diameter_mm'],254)
            self.assertFalse(rows[name]['design_reference']['ordered_sku_verified'])

    def test_missing_extra_changed_current_input_and_frame_metadata_reject(self):
        for change in ('missing','extra','changed','source','runtime','frame'):
            collection=copy.deepcopy(self.collection)
            if change=='missing':collection['inputs'].pop(next(iter(collection['inputs'])))
            elif change=='extra':collection['inputs']['hardware/cad/unrecorded.py']='0'*64
            elif change=='changed':collection['inputs']['hardware/cad/body/body_battery.py']='0'*64
            elif change=='source':collection['source_commit']='0'*40
            elif change=='runtime':collection['runtime']['cadquery']='0'
            else:collection['datums']['y_off_mm']+=1
            with self.subTest(change=change),self.assertRaises(ValueError):
                current.binding(ROOT,collection,self.folder)

    def test_current_body_leg_sampler_original_and_actual_mesh_byte_changes_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'source';folder=Path(temporary)/'collection'
            required=set(self.collection['inputs'])|{
                str(current.INPUTS),str(current.ORIGINAL),str(current.SAMPLER),
                str(current.PROOF),str(current.ACCEPTANCE),
                str(current.history.ARCHIVE),str(current.history.MANIFEST),
                str(current.history.PLAN/'baseline.json'),str(current.history.JOB/'job.json')}
            for path in (ROOT/current.history.ENGINEERING).iterdir():
                if path.is_file():required.add(path.relative_to(ROOT).as_posix())
            for relative in required:
                dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,dest)
            folder.mkdir();shutil.copyfile(self.folder/'collection.json',folder/'collection.json')
            for part in self.collection['parts']:
                if part['name'].startswith(('L.','R.')):
                    dest=folder/part['file'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.folder/part['file'],dest)
            current.binding(root,self.collection,folder)
            for name in current.INSTANCES:
                self.assertEqual(hip_geometry_match(root,self.collection,name,collection_folder=folder)['status'],'matched')
            files=[root/'hardware/cad/body/body_battery.py',root/'hardware/cad/legs/fivebar.py',
                   root/current.SAMPLER,root/current.ORIGINAL,folder/'meshes/L__hip_frame.stl',
                   root/current.INPUTS,root/current.history.ARCHIVE]
            for path in files:
                raw=path.read_bytes();path.write_bytes(raw+b'\nchanged')
                with self.subTest(file=path.name),self.assertRaises(ValueError):
                    current.binding(root,self.collection,folder)
                with self.subTest(consumer_file=path.name):
                    self.assertIsNone(hip_geometry_match(root,self.collection,'L.hip_frame',collection_folder=folder))
                path.write_bytes(raw)
            for relative in (current.PROOF,current.ACCEPTANCE):
                path=root/relative;raw=path.read_bytes();data=json.loads(raw)
                for mutation in ('extra','readiness','self-certify'):
                    changed=copy.deepcopy(data)
                    if mutation=='extra':changed['unreviewed_field']=True
                    elif mutation=='readiness':changed['physical_qualification']=True
                    else:changed['measurement_sha256']='0'*64
                    path.write_text(json.dumps(changed))
                    with self.subTest(proof_or_acceptance=str(relative),mutation=mutation):
                        self.assertIsNone(hip_geometry_match(root,self.collection,'L.hip_frame',collection_folder=folder))
                path.write_bytes(raw)
            self.assertEqual(hip_geometry_match(root,self.collection,'R.hip_frame',collection_folder=folder)['status'],'matched')


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*REMAINING])
