#!/usr/bin/env python3
"""Small source/retention mutations; no CAD or slicer invocation."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('survey_fit', ROOT / 'tools/package-survey-fit-job.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
JOB = ROOT / 'exports/turret/shaft-survey-fit-job'


class SourceTests(unittest.TestCase):
    def test_missing_or_partial_label_paths_fail_extent_screen(self):
        import numpy as np
        label = {'id': 'slot:0', 'text': '4.8', 'glyph_bounds_mm': [[0, 0, 3, 2, 3, 3.5]]}
        paths = [np.array([[.2, .2], [1.8, .2], [1.8, 2.8], [.2, 2.8], [.2, .2]])]
        self.assertEqual(m.check_label_coverage(paths, [label])[0]['text'], '4.8')
        for altered in ([], [np.array([[.8, 1.], [1.2, 1.]])], [paths[0]+100]):
            with self.assertRaises(ValueError): m.check_label_coverage(altered, [label])

    def test_current_reviewed_gauge_and_runtime(self):
        self.assertEqual(m.input_identity()['source_geometry_counts'], {'pass': 12, 'warn': 0, 'fail': 0})

    def test_source_mesh_receipt_and_helper_changes_reject(self):
        identity = m.input_identity()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in identity['files']:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, root / name)
            self.assertEqual(m.input_identity(root), identity)
            for name in identity['files']:
                path = root / name; original = path.read_bytes(); path.write_bytes(original + b'\n')
                with self.subTest(name=name):
                    try:
                        changed = m.input_identity(root)
                    except ValueError:
                        pass
                    else:
                        self.assertNotEqual(changed, identity)
                path.write_bytes(original)


class RetainedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name) / 'job'; shutil.copytree(JOB, self.job)
        self.report = json.loads((self.job / 'job.json').read_text())

    def save(self, report): m.fit.dump(self.job / 'job.json', report)

    def test_complete_current_actual_job(self):
        self.assertTrue(m.verify(self.job)['slice_complete'])
        self.assertFalse(any(self.report['qualification'].values()))
        controls = self.report['label_deposition']['missing_label_deposition_controls']
        self.assertEqual(len(controls), 18)
        self.assertTrue(all(value is True for value in controls.values()))

    def test_missing_files_and_changed_bytes_reject(self):
        for name in ('source.stl', 'profiles/machine/Bambu Lab P1S 0.4 nozzle.json',
                     'slice/out/plate_1.gcode', 'critical-layers.png', 'slice/out/result.json'):
            p = self.job / name; original = p.read_bytes()
            for mutation in ('missing', 'changed'):
                with self.subTest(name=name, mutation=mutation):
                    if mutation == 'missing': p.unlink()
                    else: p.write_bytes(original + b'\n')
                    with self.assertRaises(ValueError): m.verify(self.job)
                    p.write_bytes(original)

    def test_promoted_qualification_or_invented_metrics_reject(self):
        for key in ('qualification', 'metrics', 'recipe', 'critical_layers', 'inputs'):
            data = copy.deepcopy(self.report); data[key] = {}; self.save(data)
            with self.subTest(key=key), self.assertRaises(ValueError): m.verify(self.job)
        self.save(self.report)

    def test_fake_measurement_rejects_even_with_updated_manifest(self):
        p = self.job / 'measurements.csv'
        p.write_text(p.read_text().replace('1,4.8,,,,', '1,4.8,4.8,,,'))
        data = copy.deepcopy(self.report); data['files_sha256'] = m.fit.manifest(self.job); self.save(data)
        with self.assertRaisesRegex(ValueError, 'Blank measurement'): m.verify(self.job)

    def test_profile_membership_cannot_disappear(self):
        for key in ('engine', 'profile_files_sha256', 'effective_profiles'):
            data = copy.deepcopy(self.report); del data['slice_inputs'][key]; self.save(data)
            with self.subTest(key=key), self.assertRaises(ValueError): m.verify(self.job)

    def test_complete_zip_has_exact_bytes(self):
        expected = {str(p.relative_to(JOB.parent)): p for p in JOB.rglob('*') if p.is_file()}
        with zipfile.ZipFile(JOB.with_suffix('.zip')) as z:
            self.assertEqual(len(z.namelist()), len(set(z.namelist())))
            self.assertEqual(set(z.namelist()), set(expected))
            for name, p in expected.items(): self.assertEqual(z.read(name), p.read_bytes(), name)

    def test_actual_rejected_small_text_slice_fails_label_screen(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = ROOT / 'research/ordered-turret-motor/rejected-label-slice/job-1544582.zip'
            with zipfile.ZipFile(archive) as z: z.extractall(temp)
            old = Path(temp) / 'shaft-survey-fit-job'
            with self.assertRaisesRegex(ValueError, 'label glyph'):
                m.label_witness(old, self.report['slice_inputs'])


if __name__ == '__main__': unittest.main()
