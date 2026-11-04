"""The RS-04 inventory (hardware/actuators/rs04/inventory.json) and its filling from the motor tool's export.

    python -m unittest rig.tests.test_rs04_inventory
"""
from __future__ import annotations

import copy
import unittest

from rig import rs04_inventory as I


def export(uid='0011223344556677', can_id=1, joint='left-front', **kw):
    e = {'schema': 'rs04-motor-config/1', 'exported': '2026-11-04T10:00:00.000Z', 'uid': uid, 'can_id': can_id,
         'joint': joint, 'firmware': '0.4.1.24', 'profile': {'id': 'pla-bench', 'version': 1},
         'zero': {'pose': 'Upper link on its bare knee-out stop post', 'at': '2026-11-04T09:59:00.000Z'},
         'params': {'add_offset': 0.0, 'limit_torque': 12.0}, 'unsaved': []}
    e.update(kw)
    return e


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inv = I.load()

    def test_committed_file_is_consistent_and_invents_nothing(self):
        self.assertEqual(I.problems(self.inv), [])
        self.assertEqual(len(self.inv['units']), 4)
        for u in self.inv['units']:
            if u['uid'] is None:          # not scanned yet: every scanned field is blank
                self.assertTrue(all(u[k] is None for k in ('can_id', 'joint', 'firmware', 'zero_offset_rad', 'exported')), u)

    def test_an_export_fills_the_first_empty_unit_and_then_its_own(self):
        inv = I.add(self.blank(), export())
        u = inv['units'][0]
        self.assertEqual((u['uid'], u['can_id'], u['joint'], u['firmware'], u['zero_offset_rad']),
                         ('0011223344556677', 1, 'left-front', '0.4.1.24', 0.0))
        self.assertEqual(u['zero_pose'], 'Upper link on its bare knee-out stop post')
        inv = I.add(inv, export(firmware='0.4.1.25'), mass_g=1512)
        self.assertEqual(inv['units'][0]['firmware'], '0.4.1.25')
        self.assertEqual(inv['units'][0]['mass_g'], 1512)
        self.assertIsNone(inv['units'][1]['uid'])

    def test_conflicts_are_refused(self):
        inv = I.add(self.blank(), export())
        with self.assertRaisesRegex(ValueError, 'share can_id'):
            I.add(inv, export(uid='8899aabbccddeeff', joint='left-rear'))
        with self.assertRaisesRegex(ValueError, 'share joint'):
            I.add(inv, export(uid='8899aabbccddeeff', can_id=2))
        with self.assertRaisesRegex(ValueError, 'no motor uid'):
            I.add(inv, export(uid=None))
        with self.assertRaisesRegex(ValueError, 'not a motor tool export'):
            I.add(inv, {'schema': 'x'})
        full = self.blank()
        for i, j in enumerate(I.JOINTS):
            full = I.add(full, export(uid=f'{i:016x}', can_id=i + 1, joint=j))
        with self.assertRaisesRegex(ValueError, 'none is empty'):
            I.add(full, export(uid='ffffffffffffffff', can_id=9, joint=None))

    def test_bad_records_are_caught(self):
        inv = self.blank()
        inv['units'][0]['uid'] = 'SERIAL-123'
        self.assertTrue(any('not 8 bytes' in p for p in I.problems(inv)))
        inv = self.blank()
        inv['units'].pop()
        self.assertTrue(any('3 unit records for 4 arrived' in p for p in I.problems(inv)))

    def blank(self):
        inv = copy.deepcopy(self.inv)
        for u in inv['units']:
            for k in I.FIELDS[1:]:
                u[k] = '' if k == 'notes' else None
        return inv


if __name__ == '__main__':
    unittest.main()
