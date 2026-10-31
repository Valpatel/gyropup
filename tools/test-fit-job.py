#!/usr/bin/env python3
"""Small mesh and adversarial retained-job checks; never invoke a real slicer."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import trimesh
from cadagent.mesh3mf import write_3mf

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fit_job', ROOT / 'tools/package-fit-job.py')
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)
MACHINE = {'printable_area': ['0x0', '256x0', '256x256', '0x256'],
           'printable_height': '250', 'bed_exclude_area': ['0x0', '18x0', '18x28', '0x28']}


class FitJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name)
        self.identity = {'names': fit.PROFILES, 'overrides': fit.OVERRIDES,
                         'effective_profiles': {'machine': MACHINE, 'process': fit.OVERRIDES, 'filament': {}}}
        self.mesh = trimesh.creation.box(extents=[20, 30, 5])
        self.mesh.apply_translation([0, 0, 2.5])
        self.mesh.export(self.job / 'source.stl')
        mesh = trimesh.load_mesh(self.job / 'source.stl', process=True)
        write_3mf(self.job / 'geometry.3mf', mesh.vertices, mesh.faces, 'test', (256, 256))
        self.inputs = {'files': {str(fit.SOURCE / (fit.PART + '.stl')): fit.sha(self.job / 'source.stl')}}
        self.addCleanup(patch.stopall)
        patch.object(fit, 'input_identity', return_value=self.inputs).start()
        out = self.job / 'slice/out'
        out.mkdir(parents=True)
        for kind, profile in self.identity['effective_profiles'].items():
            fit.dump(self.job / 'slice' / (kind + '.json'), profile)
        fit.dump(self.job / 'slice/exit-code.json', {'exit_code': 0})
        (self.job / 'slice/slicer.log').write_text('test fixture: not actual slicing')
        (self.job / 'critical-layers.png').write_bytes(b'test fixture: not an image')
        (self.job / 'measurements.csv').write_text('test fixture: not measured')
        fit.dump(out / 'result.json', {'return_code': 0, 'sliced_plates': [
            {'filaments': [{'total_used_g': 8}], 'total_predication': 120}]})
        with zipfile.ZipFile(out / 'sliced.3mf', 'w') as z:
            z.writestr('Metadata/plate_1.gcode', 'G1 X100 Y100 E1\n' * 100)
            z.writestr('Metadata/slice_info.config', '<filament used_m="2.5"/>')
        (out / 'plate_1.gcode').write_text('G1 X100 Y100 E1\n' * 100)
        self.report = {'schema': 'gyropup.fit-job/1', 'recipe': fit.RECIPE, 'qualification': fit.QUALIFICATION,
                       'slice_complete': True, 'inputs': self.inputs, 'slice_inputs': self.identity,
                       'geometry': fit.geometry_check(self.job, self.identity),
                       'metrics': fit.measurements(self.job), 'archive_members': fit.sliced_members(self.job),
                       'files_sha256': fit.manifest(self.job), 'sliced_inspection': {'fixture': True}}
        # The tests below exercise retention independently of full Bambu archive
        # structure; actual path/thermal parsing has separate adversarial tests.
        patch.object(fit, 'sliced_inspection', return_value={'fixture': True}).start()
        fit.dump(self.job / 'job.json', self.report)

    def test_complete_retained_fixture(self):
        self.assertEqual(fit.verify(self.job)['metrics']['minutes'], 2.)

    def test_geometry_rotation_cannot_pass_as_parent_orientation(self):
        mesh = trimesh.load_mesh(self.job / 'source.stl', process=True)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        write_3mf(self.job / 'geometry.3mf', mesh.vertices, mesh.faces, 'rotated', (256, 256))
        with self.assertRaisesRegex(ValueError, 'orientation'):
            fit.geometry_check(self.job, self.identity)

    def test_real_machine_height_exclusion_margin_and_unknown_polygon(self):
        for bounds in ([[20, 20, 0], [30, 30, 251]], [[1, 1, 0], [10, 10, 5]],
                       [[6, 30, 0], [251, 40, 5]], [[100, 100, 0], [float('nan'), 120, 5]]):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                fit.bed_check(bounds, MACHINE, margin=6.)
        with self.assertRaises(ValueError):
            fit.bed_check([[100, 100, 0], [120, 120, 5]], {**MACHINE, 'printable_area': []})

    def test_missing_changed_or_extra_retained_file_fails(self):
        path = self.job / 'slice/out/result.json'
        before = path.read_bytes()
        for mutation in ('delete', 'change', 'extra'):
            with self.subTest(mutation=mutation):
                if mutation == 'delete': path.unlink()
                elif mutation == 'change': path.write_text('{}')
                else: (self.job / 'unexpected.gcode').write_text('G1 X0')
                with self.assertRaises(ValueError): fit.verify(self.job)
                path.write_bytes(before)
                (self.job / 'unexpected.gcode').unlink(missing_ok=True)

    def test_metrics_and_qualification_cannot_be_invented(self):
        for field in ('qualification', 'metrics', 'recipe'):
            changed = copy.deepcopy(self.report)
            if field == 'qualification': changed[field]['mounting_approved'] = True
            elif field == 'metrics': changed[field]['minutes'] = 0.01
            else: changed[field]['overrides']['enable_support'] = '1'
            fit.dump(self.job / 'job.json', changed)
            with self.subTest(field=field), self.assertRaises(ValueError): fit.verify(self.job)

    def test_failure_and_nonfinite_metrics_are_rejected(self):
        path = self.job / 'slice/out/result.json'
        original = json.loads(path.read_text())
        for mutation in ('error', 'zero', 'nan'):
            data = copy.deepcopy(original)
            if mutation == 'error': data['return_code'] = 1
            else: data['sliced_plates'][0]['filaments'][0]['total_used_g'] = 0 if mutation == 'zero' else float('nan')
            path.write_text(json.dumps(data))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): fit.measurements(self.job)

    def test_geometry_only_3mf_is_not_sliced(self):
        (self.job / 'slice/out/sliced.3mf').write_bytes((self.job / 'geometry.3mf').read_bytes())
        with self.assertRaisesRegex(ValueError, 'G-code'): fit.sliced_members(self.job)

    def test_actual_object_temperature_and_waits_not_profile_labels(self):
        code = ('M190 S100\nM109 S275\nG90\nM83\nG1 X100 Y100 Z0.2\n'
                '; Z_HEIGHT: 0.2\n; FEATURE: Outer wall\nG1 X120 Y100 E1\nG1 X120 Y120 E1\n')
        got = fit.toolpaths(code, MACHINE)
        self.assertEqual(got['features']['Outer wall']['moves'], 2)
        for changed in (code.replace('M109 S275', 'M109 S205'), code.replace('M109', 'M104'),
                        code.replace('M190', 'M140'), code.replace('M190 S100', 'M190 S60'),
                        code.replace('Outer wall', 'Support'), code.replace('X120', 'X260')):
            with self.subTest(code=changed), self.assertRaises(ValueError): fit.toolpaths(changed, MACHINE)

    def test_arc_sweep_exceeding_bed_is_rejected_even_if_endpoints_fit(self):
        code = ('M190 S100\nM109 S275\nG90\nM83\nG1 X100 Y100 Z0.2\n'
                '; Z_HEIGHT: 0.2\n; FEATURE: Outer wall\nG2 X100 Y100 I100 J0 E1\n')
        with self.assertRaisesRegex(ValueError, 'volume or exclusion'): fit.toolpaths(code, MACHINE)

    def test_archived_real_205C_slice_is_rejected(self):
        archive = ROOT / 'research/retained-fit-jobs/rejected-7b67f03.zip'
        with zipfile.ZipFile(archive) as z:
            gcode = z.read('slice/out/plate_1.gcode').decode()
        with self.assertRaisesRegex(ValueError, 'temperatures/waits differ'):
            fit.toolpaths(gcode, MACHINE)


if __name__ == '__main__':
    unittest.main()
