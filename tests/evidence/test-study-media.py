#!/usr/bin/env python3
"""Artifact faults must fail before the static study video is published."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('study_check', Path(__file__).resolve().parents[2] / 'tools/evidence/media/check-study-media.py')
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)

producer_spec = importlib.util.spec_from_file_location('e1_export', check.ROOT / 'tools/engineering/legs/export-hip-frame-e1.py')
producer = importlib.util.module_from_spec(producer_spec); producer_spec.loader.exec_module(producer)

renderer_spec = importlib.util.spec_from_file_location('e1_render', check.ROOT / check.VIDEO_RENDERER)
renderer = importlib.util.module_from_spec(renderer_spec); renderer_spec.loader.exec_module(renderer)


class RendererPaths(unittest.TestCase):
    def test_either_declared_identity_reads_the_same_current_report(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-source-') as tmp:
            root = Path(tmp)
            report = root / 'hardware/exports/leg/fea/summary.json'
            report.parent.mkdir(parents=True)
            report.write_bytes(b'current report')
            legacy = root / 'exports/leg/fea/summary.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'legacy decoy')
            with patch.object(renderer, 'ROOT', root):
                for key in ('exports/leg/fea/summary.json', 'hardware/exports/leg/fea/summary.json'):
                    receipt = {'source_hashes': {key: hashlib.sha256(report.read_bytes()).hexdigest()}}
                    self.assertEqual(renderer.report_input(receipt), report)

    def test_missing_duplicate_and_wrong_report_bindings_reject(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-binding-') as tmp:
            root = Path(tmp)
            report = root / 'hardware/exports/leg/fea/summary.json'
            report.parent.mkdir(parents=True)
            report.write_bytes(b'current report')
            value = hashlib.sha256(report.read_bytes()).hexdigest()
            for hashes in ({}, {'exports/leg/fea/summary.json': value, 'hardware/exports/leg/fea/summary.json': value},
                           {'hardware/exports/leg/fea/summary.json': '0' * 64}):
                with patch.object(renderer, 'ROOT', root), self.assertRaises(ValueError):
                    renderer.report_input({'source_hashes': hashes})

    def test_legacy_physical_report_cannot_replace_the_current_report(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-missing-') as tmp:
            root = Path(tmp)
            legacy = root / 'exports/leg/fea/summary.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'legacy decoy')
            with patch.object(renderer, 'ROOT', root), self.assertRaises(FileNotFoundError):
                renderer.report_input({'source_hashes': {'exports/leg/fea/summary.json': hashlib.sha256(legacy.read_bytes()).hexdigest()}})


class ProducerPaths(unittest.TestCase):
    def fixture(self, root):
        from hardware.cad.manufacturing.print_provenance import FORMER_CAD_TESTS, SOURCE_PARENTS, SOURCE_ROOTS
        for directory in SOURCE_ROOTS:
            (root / directory).mkdir(parents=True)
        current = [*FORMER_CAD_TESTS, *SOURCE_PARENTS, 'hardware/cad/legs/input.py',
                   'software/simulation/leg_rig.py', 'software/simulation/leg_control.py',
                   'hardware/exports/leg/rig-results.json', 'hardware/exports/leg/fea/summary.json',
                   'tools/engineering/legs/export-hip-frame-e1.py',
                   'tools/site/source_layout.py', 'tools/site/source-layout.json']
        for name in [*current, 'exports/leg/rig-results.json', 'exports/leg/fea/summary.json']:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('owned input fixture: ' + name)
        return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in current}

    def test_source_preflight_binds_current_paths_not_legacy_decoys(self):
        with tempfile.TemporaryDirectory(prefix='e1-source-paths-') as tmp:
            root = Path(tmp)
            expected = self.fixture(root)
            with patch.object(producer, 'ROOT', root):
                self.assertEqual(producer.source_hashes(), expected)
                path = root / 'hardware/exports/leg/fea/summary.json'
                path.write_text('a changed current report')
                expected[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(producer.source_hashes(), expected)

    def test_missing_current_report_rejects_a_present_legacy_copy(self):
        with tempfile.TemporaryDirectory(prefix='e1-missing-source-') as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / 'hardware/exports/leg/fea/summary.json').unlink()
            with patch.object(producer, 'ROOT', root), self.assertRaises(FileNotFoundError):
                producer.source_hashes()

    def test_field_download_identity_resolves_to_the_current_output(self):
        with tempfile.TemporaryDirectory(prefix='e1-output-path-') as tmp:
            root = Path(tmp)
            fields = root / 'hardware/exports/leg/fea/hip-frame-e1-media/hip_frame-E1.json'
            with patch.object(producer, 'ROOT', root):
                identity = producer.field_identity(fields)
                self.assertEqual(check.source_file(root, identity), fields)
                self.assertTrue(identity.startswith(check.MEDIA))
                with self.assertRaises(ValueError):
                    producer.field_identity(root / 'unrelated/hip_frame-E1.json')


class StudyMedia(unittest.TestCase):
    def test_leg_rig_companions(self):
        subprocess.run(['node', '--test', 'tests/site/media/test-rig-media.mjs'], cwd=check.ROOT, check=True)

    def test_real_video_and_sources(self):
        self.assertEqual(check.validate()['decoded_frames'], 288)

    def test_frozen_frame_negative_control(self):
        with self.assertRaisesRegex(ValueError, 'Frozen model'):
            check.moving_model(bytes(range(256)) * 20, bytes(range(256)) * 20)

    def test_corruptions(self):
        with tempfile.TemporaryDirectory(prefix='gyropup-study-faults-') as tmp:
            root = Path(tmp)
            paths = [check.SUMMARY, 'exports/leg/fea/media.json', check.VIDEO_RENDERER, check.LOCATION_SOURCE, check.FINER]
            paths += [p.relative_to(check.ROOT).as_posix() for p in check.source_file(check.ROOT, check.MEDIA.rstrip('/')).iterdir() if p.is_file()]
            for path in paths:
                target = check.source_file(root, path); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(check.source_file(check.ROOT, path), target)
            def fault(path, mutate, pattern):
                target = check.source_file(root, path); original = target.read_bytes()
                try:
                    mutate(target)
                    with self.assertRaisesRegex(ValueError, pattern): check.validate(root, decode=False)
                finally: target.write_bytes(original)
            def edit(fn):
                def mutate(path):
                    data = json.loads(path.read_text()); fn(data); path.write_text(json.dumps(data))
                return mutate
            fault(check.SUMMARY, edit(lambda d: d['results'].append({'part':'different','case':'E1'})), 'Stale report binding')
            fault(check.VIDEO_RENDERER, lambda p: p.write_bytes(p.read_bytes()+b'\n# changed\n'), 'Stale animation source')
            fault(check.FINER, edit(lambda d: d['meshes']['3.0']['cases'][0].update(safety_factor=2.5)), 'Stale animation source')
            fault(check.MEDIA+'hip_frame-E1.json', lambda p: p.write_bytes(p.read_bytes()+b'\n'), 'Field bytes changed')
            fault(check.MEDIA+'hip-frame-e1.mp4', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault(check.MEDIA+'hip-frame-e1.webm', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault(check.MEDIA+'hip-frame-e1-poster.png', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1']['recorded'].update(safety_factor=2.5)), 'Media index differs')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(transient_simulation=True)), 'Static evidence mislabeled')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(video='elsewhere.mp4')), 'Media index paths differ')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['timeline'][144].update(load_factor=2)), 'Presentation extrapolates')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['outputs'].pop(check.MEDIA+'hip-frame-e1-poster.png')), 'Incomplete rendered artifacts')
            fault(check.MEDIA+'field-receipt.json', edit(lambda d: d.update(qualified_for_manufacture=True)), 'Static evidence cannot qualify')


if __name__ == '__main__': unittest.main()
