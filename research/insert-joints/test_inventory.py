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


def joint(doc, jid):
    return next(j for j in doc['joints'] if j['id'] == jid)


def codes(doc, jid):
    return {f['code'] for f in joint(doc, jid)['findings']}


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
        self.assertIn('tm-com-datum', codes(d, 'body.riser_top_tm'))
        self.assertIn('screw-bottoms', codes(d, 'turret.plinth_columns'))
        self.assertIn('pan-base-dowels', codes(d, 'turret.plinth_columns'))
        self.assertIn('pilot-shorter-than-insert', codes(d, 'stand.dock'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.wheel_botwheel'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.upper_link_hub'))
        self.assertIn('engagement-low', codes(d, 'turret.pan_ring_yoke'))
        self.assertIn('engagement-low', codes(d, 'rig.pendant_clip'))
        self.assertIn('no-receiver', codes(d, 'rig.pod_lid'))
        self.assertIn('plate-thinner-than-insert', codes(d, 'body.battery_adapter'))
        self.assertNotIn('screw-bottoms', codes(d, 'body.riser_feet'))
        self.assertEqual(d['summary']['fix'], sum(f['level'] == 'fix' for f in d['findings']))

    def test_tm_load_from_the_tm_face(self):
        """The TM bolts' 30 g load is taken about the plinth's underside (D66), not frame T's origin."""
        j = joint(self.doc, 'body.riser_top_tm')
        m = json.loads((inv.ROOT / 'exports/turret/mount.json').read_text())
        arm = (m['com_mm'][2] - m['envelope']['lowest_z_mm']) / 1000.0
        self.assertAlmostEqual(j['loads'][0]['per_insert_n'], m['mass_kg'] * inv.G0 * 30.0 * arm / 0.160, delta=1.0)
        self.assertEqual(joint(self.doc, 'body.riser_feet')['verdict'], 'owner')   # SF < 2 on the feet

    def test_control_riser_fixed(self):
        """Both riser fixes applied: every riser finding except the turret's datum goes."""
        d = generate({'cad/body_frame.py': [('cyl_z(3.2, H - 9.5, H + 1.0, x, y)', 'cyl_z(3.2, H - 13.0, H + 1.0, x, y)'),
                                            ('cyl_z(2.5 - 0.03, H - 8.0, H + 1.0, x, y)', 'cyl_z(2.5 - 0.03, H - 13.0, H + 1.0, x, y)')]})
        fixes = {f['code'] for f in joint(d, 'body.riser_top_tm')['findings'] if f['level'] == 'fix'}
        self.assertEqual(fixes, {'tm-com-datum'})
        self.assertNotIn('tip-near-floor', codes(d, 'body.riser_top_tm'))

    def test_control_mount_datum_fixed(self):
        """mount.json measured from the plinth's underside: the datum finding goes, the bolt load stays."""
        before = joint(self.doc, 'body.riser_top_tm')['loads'][0]['per_insert_n']
        d = generate({'exports/turret/mount.json': [('"com_mm": [\n  -4.1,\n  -2.8,\n  49.2\n ]', '"com_mm": [\n  -4.1,\n  -2.8,\n  135.2\n ]'),
                                                    ('"lowest_z_mm": -86.0', '"lowest_z_mm": 0.0')]})
        self.assertNotIn('tm-com-datum', codes(d, 'body.riser_top_tm'))
        self.assertEqual(joint(d, 'body.riser_top_tm')['loads'][0]['per_insert_n'], before)

    def test_control_plinth_column_pilot_from_its_own_call(self):
        """The columns' depth is read from compute_shell's insert_hole() call, not INSERT_DEPTH."""
        d = generate({'cad/turret.py': [("s = s.cut(insert_hole(x, y, 0.0, 'M5'))", "s = s.cut(insert_hole(x, y, 0.0, 'M5', 12.5))")]})
        c = codes(d, 'turret.plinth_columns')
        self.assertNotIn('screw-bottoms', c)
        self.assertNotIn('screw-bottoms-fix', c)
        self.assertEqual(joint(d, 'turret.plinth_columns')['hole']['depth'], 12.5)

    def test_control_shallow_yoke_and_tray_pilots(self):
        d = generate({'cad/turret.py': [("s = s.cut(insert_hole(x, y, z1, 'M4'))", "s = s.cut(insert_hole(x, y, z1, 'M4', 5.0))"),
                                        ("s = s.cut(insert_hole(fx, fy, z1, 'M4'))", "s = s.cut(insert_hole(fx, fy, z1, 'M4', 4.0))")]})
        self.assertIn('pilot-shorter-than-insert', codes(d, 'turret.pan_ring_yoke'))
        self.assertIn('pilot-shorter-than-insert', codes(d, 'turret.plinth_tray_m4'))

    def test_control_stand_dock_fixed(self):
        d = generate({'cad/turret_stand.py': [("-TOP - 0.01, -TOP + 4.0, dx0", "-TOP - 0.01, -TOP + 5.8, dx0")]})
        self.assertEqual({f['code'] for f in joint(d, 'stand.dock')['findings'] if f['level'] == 'fix'}, set())

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

    def test_control_a_second_site_that_disagrees_stops_generation(self):
        """A pattern that matches two lines binds both: the pod's relay boss drifting from the contactor's is noticed."""
        with self.assertRaises(inv.Stale):
            generate({'cad/rig_parts.py': [("'z', t - 3.0, t + 6.1, m['x'], m['y']", "'z', t - 2.0, t + 6.1, m['x'], m['y']")]})

    def test_control_a_fixed_note_must_be_dropped(self):
        with self.assertRaises(inv.Stale):
            generate({'cad/fivebar.py': [('its 4 x M6 x 40', 'its 4 x M6 x 30')]})


if __name__ == '__main__':
    unittest.main(verbosity=1)
