"""Exercise the real no-render guard without importing CAD or modifying retained images."""
import ast
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / 'tools/motor_day.py').read_text())
STEPS_NODE = next(n for n in TREE.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'STEPS' for t in n.targets))
FUNCTIONS = [n for n in TREE.body if isinstance(n, ast.FunctionDef)
             and n.name in ('step_visuals', 'require_rendered_steps')]


class RenderInputs(unittest.TestCase):
    def setUp(self):
        self.module = {'json': json, 'STEPS': ast.literal_eval(STEPS_NODE.value)}
        exec(compile(ast.Module(body=FUNCTIONS, type_ignores=[]), 'motor_day.py', 'exec'), self.module)
        self.items = {'hip_frame': 1, 'robstride-rs-04': 30}
        self.rows = [{'step': i + 1} for i in range(len(self.module['STEPS']))]
        self.rendered = json.loads(json.dumps({'items': self.items, 'step_visuals': self.module['step_visuals'](),
                                              'sheets': [{'number': 'MD-01'}]}))

    def check(self):
        self.module['require_rendered_steps'](self.rows, self.rendered, self.items)

    def test_json_round_trip_of_actual_step_inputs_passes(self):
        self.check()

    def test_changed_parts_are_rejected(self):
        self.module['STEPS'][2][1].append('another-part')
        with self.assertRaisesRegex(SystemExit, 'parts, explode offsets or camera'):
            self.check()

    def test_changed_explode_offset_is_rejected(self):
        lift = self.module['STEPS'][2][2]
        key = next(iter(lift))
        lift[key] = (lift[key][0] + 1, *lift[key][1:])
        with self.assertRaisesRegex(SystemExit, 'explode offsets'):
            self.check()

    def test_changed_camera_is_rejected(self):
        row = self.module['STEPS'][2]
        self.module['STEPS'][2] = (*row[:3], (0.1, 0.2, 0.3), row[4])
        with self.assertRaisesRegex(SystemExit, 'camera'):
            self.check()

    def test_editable_prose_does_not_require_new_pictures(self):
        row = self.module['STEPS'][2]
        self.module['STEPS'][2] = ('New title', *row[1:4], 'New instructions')
        self.check()

    def test_legacy_parts_only_receipt_requires_rendering(self):
        self.rendered['step_parts'] = [list(st[1]) for st in self.module['STEPS']]
        del self.rendered['step_visuals']
        with self.assertRaisesRegex(SystemExit, 'render again'):
            self.check()

    def test_changed_bom_and_step_count_are_rejected(self):
        self.items['hip_frame'] = 2
        with self.assertRaisesRegex(SystemExit, 'BOM item numbers'):
            self.check()
        self.items['hip_frame'] = 1
        self.rows.pop()
        with self.assertRaisesRegex(SystemExit, 'render again'):
            self.check()

    def test_missing_rendered_outputs_are_rejected(self):
        self.rendered['sheets'] = []
        with self.assertRaisesRegex(SystemExit, 'needs the rendered steps'):
            self.check()


if __name__ == '__main__':
    unittest.main()
