#!/usr/bin/env python3
"""Checks of the insert-joint inventory, kernel-free (no CadQuery, no cad-agent).

The committed joints.json / joints.md must equal a fresh generation, and the screen must catch what it claims to:
controls edit one bound source line in memory and expect the matching finding to appear or go away.
"""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as inv  # noqa: E402


class Patched(inv.Repo):
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

    def json(self, rel):
        if rel in self.edits:
            return json.loads(self.text(rel))
        return super().json(rel)


def generate(edits=None):
    repo = Patched(inv.ROOT, edits or {})
    return inv.document(repo)


def codes(doc, jid):
    return {f['code'] for f in next(j for j in doc['joints'] if j['id'] == jid)['findings']}


class Inventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = generate()

    def test_committed_outputs_are_current(self):
        js = json.dumps(self.doc, indent=1, ensure_ascii=False) + '\n'
        self.assertEqual((HERE / 'joints.json').read_text(), js, 'joints.json is stale: run research/insert-joints/inventory.py')
        self.assertEqual((HERE / 'joints.md').read_text(), inv.markdown(self.doc), 'joints.md is stale')

    def test_formulas(self):
        self.assertAlmostEqual(inv.preload(1.5, 5), 1500.0)                 # T / (K d), K 0.2
        self.assertAlmostEqual(inv.torque_for(1500.0, 5), 1.5)
        self.assertAlmostEqual(inv.tau_petg(), 119 * 9.80665 / (math.pi * 4.0 * 5.7))
        self.assertAlmostEqual(inv.pullout(inv.tau_petg(), 4.0, 5.7), 119 * 9.80665)
        self.assertAlmostEqual(inv.annulus(10.0, 6.0), math.pi * 16.0)

    def test_every_family_is_complete(self):
        for j in self.doc['joints']:
            for k in ('id', 'assembly', 'where', 'qty_robot', 'material', 'findings', 'verdict'):
                self.assertIn(k, j, j['id'])
            if j.get('insert'):
                self.assertIn(j['insert'], self.doc['inserts'])
                self.assertIn('hole', j, j['id'])
                self.assertIn('capacity_n', j, j['id'])
        ids = [j['id'] for j in self.doc['joints']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_body_inserts_all_inventoried(self):
        """Every P3 insert joint of the body's own check lands in a family (the generator raises otherwise)."""
        integ = json.loads((inv.ROOT / 'exports/body/integrity.json').read_text())
        names = {j['joint'] for j in integ['joints'] if j['stage'] == 'P3' and j['receiver'][0] == 'insert'}
        listed = set()
        for j in self.doc['joints']:
            if j['assembly'].startswith('body') or j['id'] == 'leg.hip_frame_mount':
                listed |= {n for n in names if n in j.get('notes', '')}
        self.assertEqual(names - listed, set())

    def test_known_findings(self):
        d = self.doc
        self.assertIn('screw-bottoms', codes(d, 'body.riser_top_tm'))
        self.assertIn('screw-bottoms', codes(d, 'turret.plinth_columns'))
        self.assertIn('pilot-shorter-than-insert', codes(d, 'stand.dock'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.wheel_botwheel'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.upper_link_hub'))
        self.assertIn('engagement-low', codes(d, 'turret.pan_ring_yoke'))
        self.assertNotIn('screw-bottoms', codes(d, 'body.riser_feet'))
        self.assertEqual(d['summary']['fix'], sum(f['level'] == 'fix' for f in d['findings']))

    def test_control_deeper_riser_pilot_clears_the_bottoming(self):
        d = generate({'cad/body_frame.py': [('cyl_z(3.2, H - 9.5, H + 1.0, x, y)', 'cyl_z(3.2, H - 13.0, H + 1.0, x, y)')]})
        c = codes(d, 'body.riser_top_tm')
        self.assertNotIn('screw-bottoms', c)
        self.assertNotIn('tip-near-floor', c)

    def test_control_oversize_pilot_is_caught(self):
        d = generate({'cad/interfaces.json': [('"insert_pilot": 6.4', '"insert_pilot": 6.6')]})
        self.assertIn('hole-oversize', codes(d, 'body.post_m5'))

    def test_control_shallow_post_pilot(self):
        d = generate({'cad/body_frame.py': [('s = s.cut(cyl_z(3.2, -1.0, 11.0)).cut(cyl_z(3.2, h - 11.0, h + 1.0))',
                                             's = s.cut(cyl_z(3.2, -1.0, 7.0)).cut(cyl_z(3.2, h - 11.0, h + 1.0))')]})
        c = codes(d, 'body.post_m5')
        self.assertIn('pilot-shorter-than-insert', c)
        self.assertIn('screw-bottoms', c)

    def test_control_a_changed_bound_line_stops_generation(self):
        with self.assertRaises(inv.Stale):
            generate({'cad/fivebar.py': [('LUG_CB = 8.5', 'LUG_CB_MM = 8.5')]})

    def test_control_a_fixed_note_must_be_dropped(self):
        with self.assertRaises(inv.Stale):
            generate({'cad/fivebar.py': [('its 4 x M6 x 40', 'its 4 x M6 x 30')]})


if __name__ == '__main__':
    unittest.main(verbosity=1)
