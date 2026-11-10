"""Neutral adaptation controls; stdlib only, no CAD/build/renderer execution."""
import importlib.util
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('turret_guide', ROOT / 'tools/site/assembly/export_turret_guide.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NeutralGuide(unittest.TestCase):
    def test_source_recipe_current_prose_not_stale_step_export(self):
        rows = module.recipe_rows((ROOT / module.RECIPE).read_bytes())
        old = json.loads((ROOT / 'hardware/exports/turret/assembly/steps.json').read_text())
        self.assertIn('0 and -25', old[7]['how'])
        self.assertIn('+12 and -25', rows[7][-1])
        self.assertNotEqual(old[7]['how'], rows[7][-1])

    def test_audited_neutral_hierarchy_is_applied_once(self):
        scene = json.loads((ROOT / module.SCENE).read_text())
        expected = {'base': [0, 0, -145], 'pinion': [0, 0, -145],
                    'pan': [0, 0, 0], 'tilt': [0, 0, 140],
                    'dial': [-48, 0, 140], 'wheel_l': [25, 25.81, 140],
                    'wheel_r': [25, -25.81, 140], 'flap': [-87, 0, 231]}
        for group, offset in expected.items():
            self.assertEqual(module.neutral_offset({'group': group}, scene['pivots']), offset)
        with self.assertRaises(ValueError):
            module.neutral_offset({'group': 'foreign'}, scene['pivots'])

    def test_binary_reframe_preserves_triangle_order_normals_and_attributes(self):
        source = b'fixture'.ljust(80, b'\0') + struct.pack('<I12fH', 1, 0, 0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 29)
        out, bounds = module.reframe_stl(source, [10, -20, 30])
        self.assertEqual(out[:96], source[:96])
        self.assertEqual(out[-2:], source[-2:])
        self.assertEqual(struct.unpack_from('<9f', out, 96), (11, -18, 33, 14, -15, 36, 17, -12, 39))
        self.assertEqual(bounds, [11, -18, 33, 17, -12, 39])
        for malformed in (source[:-1], source + b'\0', b'<html>'):
            with self.assertRaises(ValueError):
                module.reframe_stl(malformed, [0, 0, 0])
        with self.assertRaises(ValueError):
            module.reframe_stl(source, [float('nan'), 0, 0])

    def test_whole_real_snapshot_is_complete_and_reproducible(self):
        outputs = module.generate()
        guide = json.loads(outputs['guide.json'])
        view = json.loads(outputs['view.json'])
        self.assertEqual(len(view['parts']), 60)
        self.assertEqual(len(guide['steps']), 12)
        names = {p['name'] for p in view['parts']}
        self.assertEqual(set(guide['steps'][-1]['parts']), names)
        self.assertEqual(sum(len(s['highlight']) for s in guide['steps']), len(names))
        self.assertEqual(guide['model']['sha256'], module.digest(outputs['view.json']))
        for p in view['parts']:
            self.assertEqual(p['sha256'], module.digest(outputs[p['file']]))
        self.assertEqual(guide['source']['limits']['tilt_deg'], [-25.0, 12.0])
        # Both real mirrored wheel instances must be visible and highlighted.
        step = guide['steps'][9]
        self.assertTrue({'flywheel', 'flywheel_m'} <= set(step['highlight']))


if __name__ == '__main__':
    unittest.main()
