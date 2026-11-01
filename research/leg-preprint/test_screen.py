#!/usr/bin/env python3
"""Checks of the leg pre-print screen, kernel-free (no CadQuery, no cad-agent).

The committed screen.json / screen.md / sheets must equal a fresh generation, and the screen must catch what it claims
to: controls edit one bound source line in memory and expect the matching finding to move.
"""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import screen as sc  # noqa: E402


class Patched(sc.Repo):
    """The repository with some files edited in memory."""

    def __init__(self, root, edits):
        super().__init__(root)
        self.edits = edits

    def text(self, rel):
        t = super().text(rel)
        for a, b in self.edits.get(rel, ()):
            assert a in t, (rel, a)
            t = t.replace(a, b)
        return t


def generate(edits=None):
    return sc.document(Patched(sc.ROOT, edits or {}))


def fit(doc, name):
    return next(f for f in doc['fits']['rows'] if f['fit'].startswith(name))


def joint(doc, jid):
    return next(j for j in doc['joints'] if j['id'] == jid)


class Screen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = generate()

    def test_committed_outputs_are_current(self):
        for path, text in sc.outputs(sc.Repo(sc.ROOT)).items():
            rel = path.relative_to(sc.ROOT)
            self.assertTrue(path.exists(), f'{rel} is missing: run research/leg-preprint/screen.py')
            self.assertEqual(path.read_text(), text, f'{rel} is stale: run research/leg-preprint/screen.py')

    def test_front_link_floats_as_oriented(self):
        part = next(p for p in self.doc['parts']['parts'] if p['part'] == 'front_link')
        self.assertIn('floats', [f['code'] for f in part['flags']])
        others = [p['part'] for p in self.doc['parts']['parts'] if any(f['code'] == 'floats' for f in p['flags'])]
        self.assertEqual(others, ['front_link'])

    def test_hip_frame_needs_a_spool_change(self):
        part = next(p for p in self.doc['parts']['parts'] if p['part'] == 'hip_frame')
        self.assertIn('spool', [f['code'] for f in part['flags']])

    def test_layer_rows_below_target_carry_a_factor(self):
        for row in self.doc['layers']['rows']:
            if row['ok']:
                self.assertIsNone(row['stress_reduction_needed'])
            else:
                self.assertGreater(row['stress_reduction_needed'], 1.0, row)

    def test_required_shear_strength_formula(self):
        # sigma_n below its share: S_s = tau / sqrt((1/target)^2 - (sigma_n/S_z)^2)
        row = next(x for x in self.doc['layers']['rows'] if x['part'] == 'upper_link' and x['case'] == 'R3K')
        self.assertLess(row['sigma_n_mpa'], 0)                  # compressive: only the shear term remains
        self.assertAlmostEqual(row['S_s_needed_mpa'], abs(row['tau_mpa']) * row['target'], delta=0.11)

    def test_control_sleeve_hole_opened_relieves_the_fit(self):
        rel = 'cad/fivebar.py'
        a = 'u = u.cut(ycyl(EYE_SLEEVE[0] / 2 - 0.02, eye_sleeve_end(), t + 1, l1, 0))'
        tight = fit(self.doc, 'knee eye sleeves')
        self.assertIn('too tight', tight['verdict'])
        opened = fit(generate({rel: [(a, a.replace('- 0.02', '- 0.00'))]}), 'knee eye sleeves')
        self.assertNotIn('too tight', opened['verdict'])
        self.assertLess(opened['interference_printed_mm'][1], tight['interference_printed_mm'][1])

    def test_control_flange_thickness_moves_the_insert_wall(self):
        rel = 'cad/fivebar.py'
        base = joint(self.doc, 'leg.hip_frame_mount')['today']
        doc = generate({rel: [('FLANGE_T, FLANGE_X = 13.0, ', 'FLANGE_T, FLANGE_X = 17.0, ')]})
        self.assertIn('2.94 mm of wall', base)
        self.assertIn('4.9', joint(doc, 'leg.hip_frame_mount')['today'].split(' mm of wall')[0][-5:])
        self.assertIn('17 mm flange', joint(doc, 'leg.hip_frame_mount')['today'])

    def test_control_unbound_line_is_stale(self):
        with self.assertRaises(sc.Stale):
            generate({'cad/fivebar.py': [('STOP_HOLE_PLAY = 0.05', 'STOP_HOLE_CLEARANCE = 0.05')]})

    def test_every_leg_joint_has_a_pick(self):
        inv = json.loads((sc.ROOT / 'research/insert-joints/joints.json').read_text())
        leg = {j['id'] for j in inv['joints'] if j['id'].startswith('leg.')}
        screened = {j['id'] for j in self.doc['joints']}
        self.assertLessEqual(leg, screened)
        for j in self.doc['joints']:
            self.assertTrue(j['pick'], j['id'])

    def test_sheets_have_one_row_per_sample(self):
        for c in sc.COUPONS:
            lines = (HERE / 'sheets' / c['sheet']).read_text().splitlines()
            self.assertEqual(lines[0].split(','), c['columns'])
            self.assertEqual(len(lines) - 1, len(c['rows']))

    def test_no_paths_or_addresses(self):
        home = re.compile(r'/(home|Users)/[^/\s]+')
        ipv4 = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
        for path in sc.outputs(sc.Repo(sc.ROOT)):
            text = path.read_text()
            self.assertIsNone(home.search(text), f'{path.name} has a home path')
            self.assertIsNone(ipv4.search(text), f'{path.name} has an address')


if __name__ == '__main__':
    unittest.main(verbosity=1)
