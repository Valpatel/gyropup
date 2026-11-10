"""Kernel-free source-operation checks; actual geometry is a separate gate."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('robot_recipe', ROOT/'tools/site/assembly/robot_recipe.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class SourceOperations(unittest.TestCase):
    def setUp(self):
        record = json.loads((ROOT/'hardware/exports/robot/robot.json').read_text())
        self.names = {n for g in record['groups'].values() for n in g['members'] if not n.startswith('turret.')}
        self.ops = recipe.robot_operations()

    def test_complete_declared_construction_membership(self):
        self.assertEqual(recipe.validate_operations(self.ops, self.names), self.names)
        self.assertEqual(len(self.names), 171)
        self.assertEqual(len(self.ops), 23)
        # This checks the retained collector inventory, not fresh native output.

    def test_stationary_and_rotating_owners_are_separate(self):
        by = {p: op['id'] for op in self.ops for p in op['additions']}
        for side in ('L', 'R'):
            self.assertEqual(by[side+'.motor_front'], side.lower()+'-motors')
            self.assertEqual(by[side+'.output_adapter_front'], side.lower()+'-upper')
            self.assertEqual(by[side+'.knee_pin_front'], side.lower()+'-front-knee')
            self.assertEqual(by[side+'.knee_pin_rear'], side.lower()+'-rear-knee')
            self.assertEqual(by[side+'.wheel_hub'], side.lower()+'-wheel')
            self.assertLess(list(by.values()).index(side.lower()+'-motors'), list(by.values()).index(side.lower()+'-upper'))

    def test_actual_grouped_screw_envelopes_stay_grouped(self):
        for side in ('L', 'R'):
            groups = {n for n in self.names if n.startswith(side+'.screws_')}
            self.assertEqual(groups, {side+'.screws_'+k for k in ('lugs','links','outputs','wheel')})
            self.assertFalse(any(n.startswith(side+'.screws_lugs_') for n in self.names))

    def test_unknown_missing_and_double_assigned_members_reject(self):
        for kind in ('unknown','missing','duplicate'):
            ops = json.loads(json.dumps(self.ops))
            if kind == 'unknown': ops[0]['additions'].append('invented.part')
            elif kind == 'missing': ops[0]['additions'].pop()
            else: ops[1]['additions'].append(ops[0]['additions'][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                recipe.validate_operations(ops, self.names)

    def test_operation_sources_exist_and_all_steps_keep_wip_boundary(self):
        for op in self.ops:
            first = op['source_operation'].split('::')[0]
            self.assertTrue((ROOT/first).is_file(), first)
            self.assertNotIn(recipe.WARNING, op['text'])
            self.assertTrue(op['text'].strip())
        with self.assertRaises(ValueError): recipe.leg_operations('mirrored')


if __name__ == '__main__':
    unittest.main()
