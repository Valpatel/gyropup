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
        self.assertIn('tm-com-budget', codes(d, 'body.riser_top_tm'))             # the owner's: 135 mm against D71's 100
        self.assertIn('pan-base-dowels', codes(d, 'turret.plinth_columns'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.wheel_botwheel'))
        self.assertIn('printed-clamp-crush', codes(d, 'leg.upper_link_hub'))
        self.assertIn('engagement-low', codes(d, 'rig.pendant_clip'))
        self.assertIn('plate-thinner-than-insert', codes(d, 'body.battery_adapter'))
        self.assertNotIn('screw-bottoms', codes(d, 'body.riser_feet'))
        self.assertEqual(d['summary']['fix'], sum(f['level'] == 'fix' for f in d['findings']))

    def test_fixed_joints_pass(self):
        """#137's clear fixes outside the leg are in the CAD: none of these families has a fix-level finding left (the
        leg's, leg.wheel_botwheel and leg.stop_posts, belong to the leg's print-readiness work)."""
        fixed = ('body.riser_top_tm', 'turret.plinth_columns', 'stand.dock', 'turret.pan_ring_yoke', 'rig.pod_lid',
                 'body.dcdc_bracket', 'body.bus_insulator', 'body.bay_rail_door', 'body.printed_clamps', 'turret.cradle_plates')
        for jid in fixed:
            self.assertEqual([f['code'] for f in joint(self.doc, jid)['findings'] if f['level'] == 'fix'], [], jid)
        self.assertEqual(joint(self.doc, 'rig.pod_lid')['insert'], 'insert_m3')
        self.assertEqual(joint(self.doc, 'stand.dock')['insert'], 'turret_insert_m3_short')

    def test_tm_load_from_the_tm_face(self):
        """The TM bolts' 30 g load is taken about the plinth's underside (D66), not frame T's origin."""
        j = joint(self.doc, 'body.riser_top_tm')
        m = json.loads((inv.ROOT / 'exports/turret/mount.json').read_text())
        arm = (m['com_mm'][2] - m['envelope']['lowest_z_mm']) / 1000.0
        self.assertAlmostEqual(j['loads'][0]['per_insert_n'], m['mass_kg'] * inv.G0 * 30.0 * arm / 0.160, delta=1.0)
        self.assertEqual(joint(self.doc, 'body.riser_feet')['verdict'], 'owner')   # SF < 2 on the feet

    def test_control_riser_unfixed(self):
        """The riser's pilots back at 9.5 and 8 mm: the screws bottom and both contract depths fail again."""
        d = generate({'cad/body_frame.py': [('RISER_TM_PILOT = 13.0', 'RISER_TM_PILOT = 9.5'),
                                            ('RISER_DOWEL_DEPTH = 9.5', 'RISER_DOWEL_DEPTH = 8.0')]})
        fixes = {f['code'] for f in joint(d, 'body.riser_top_tm')['findings'] if f['level'] == 'fix'}
        self.assertEqual(fixes, {'screw-bottoms', 'contract-depth', 'contract-dowel'})

    def _mount_in_frame_t(self):
        """Edits that turn the committed mount.json back into frame T (the file before #137)."""
        m = json.loads((inv.ROOT / 'exports/turret/mount.json').read_text())
        dz = m['frame_t_above_face_mm']
        com = lambda c: '"com_mm": [\n' + ',\n'.join('  ' + json.dumps(v) for v in c) + '\n ]'
        low = m['envelope']['lowest_z_mm']
        return [(com(m['com_mm']), com(m['com_mm'][:2] + [round(m['com_mm'][2] - dz, 1)])),
                (f'"frame_t_above_face_mm": {json.dumps(dz)},\n', ''),
                (f'"lowest_z_mm": {json.dumps(low)}', f'"lowest_z_mm": {json.dumps(round(low - dz, 2))}')]

    def test_control_mount_in_frame_t(self):
        """mount.json in frame T (as before #137): the datum finding comes back, the bolt load does not change."""
        before = joint(self.doc, 'body.riser_top_tm')['loads'][0]['per_insert_n']
        d = generate({'exports/turret/mount.json': self._mount_in_frame_t()})
        self.assertIn('tm-com-datum', codes(d, 'body.riser_top_tm'))
        self.assertEqual(joint(d, 'body.riser_top_tm')['loads'][0]['per_insert_n'], before)

    def test_control_a_datum_that_is_not_the_plinth_stops_generation(self):
        m = (inv.ROOT / 'exports/turret/mount.json').read_text()
        with self.assertRaises(inv.Stale):
            generate({'exports/turret/mount.json': [('"lowest_z_mm": 0.0', '"lowest_z_mm": -8.0')]})
        self.assertIn('"frame_t_above_face_mm": 86.0', m)
        with self.assertRaises(inv.Stale):
            generate({'exports/turret/mount.json': [('"frame_t_above_face_mm": 86.0', '"frame_t_above_face_mm": 80.0')]})

    def test_control_hand_check_in_frame_t(self):
        """A hand check that still takes the lever from frame T is caught: the source line and its number."""
        d = generate({'cad/turret_studies.py': [("h_face = M['com_mm'][2] + tu.PLINTH['h']", "h_face = M['com_mm'][2]")]})
        self.assertIn('tm-hand-check', codes(d, 'body.riser_top_tm'))
        s = json.loads((inv.ROOT / 'exports/turret/fea/summary.json').read_text())
        n = s['hand_checks']['tm_bolts']['tension_per_bolt_n']
        d = generate({'exports/turret/fea/summary.json': [(f'"tension_per_bolt_n": {n},', f'"tension_per_bolt_n": {round(n * 0.4)},')]})
        self.assertIn('tm-hand-check', codes(d, 'body.riser_top_tm'))

    def test_control_plinth_column_pilot_from_its_own_call(self):
        """The columns' depth is read from compute_shell's insert_hole() call: back at INSERT_DEPTH, the screws bottom."""
        d = generate({'cad/turret.py': [("s = s.cut(insert_hole(x, y, 0.0, 'M5', 12.5))", "s = s.cut(insert_hole(x, y, 0.0, 'M5'))")]})
        c = codes(d, 'turret.plinth_columns')
        self.assertIn('screw-bottoms', c)
        self.assertIn('screw-bottoms-fix', c)
        self.assertEqual(joint(d, 'turret.plinth_columns')['hole']['depth'], 8.0)

    def test_control_shallow_yoke_and_tray_pilots(self):
        d = generate({'cad/turret.py': [("s = s.cut(insert_hole(x, y, z1, 'M4'))", "s = s.cut(insert_hole(x, y, z1, 'M4', 5.0))"),
                                        ("s = s.cut(insert_hole(fx, fy, z1, 'M4'))", "s = s.cut(insert_hole(fx, fy, z1, 'M4', 4.0))")]})
        self.assertIn('pilot-shorter-than-insert', codes(d, 'turret.pan_ring_yoke'))
        self.assertIn('pilot-shorter-than-insert', codes(d, 'turret.plinth_tray_m4'))

    def test_control_yoke_screw_and_bom_must_agree(self):
        with self.assertRaises(inv.Stale):
            generate({'cad/turret.py': [("so an M4 x 12 keeps 6 mm (1.5 d)", "so an M4 x 10 keeps 6 mm (1.5 d)")]})

    def test_control_stand_dock_unfixed(self):
        d = generate({'cad/turret_stand.py': [("-TOP - 0.01, -TOP + 5.3, dx0", "-TOP - 0.01, -TOP + 4.0, dx0")]})
        self.assertEqual({f['code'] for f in joint(d, 'stand.dock')['findings'] if f['level'] == 'fix'},
                         {'pilot-shorter-than-insert', 'pilot-fix'})

    def test_control_pod_lid_pilot_too_shallow(self):
        d = generate({'cad/rig_parts.py': [("POD_LID_BOSS = {'r': 5.0, 'len': 11.0, 'pilot_depth': 8.5}",
                                            "POD_LID_BOSS = {'r': 5.0, 'len': 11.0, 'pilot_depth': 6.5}")]})
        self.assertIn('screw-bottoms', codes(d, 'rig.pod_lid'))

    def test_control_rig_stated_minimum_decides_owner_or_fix(self):
        """The rig's own min_engage is what makes a short engagement an owner decision: raise it past the engaged thread
        (ToF arm 3.65 mm, pendant clip 4 mm) and the joint becomes a fix."""
        self.assertEqual(joint(self.doc, 'rig.tof_arm')['verdict'], 'owner')
        self.assertEqual(joint(self.doc, 'rig.pendant_clip')['verdict'], 'owner')
        tof = "'min_engage': 3.5,\n                  'holds': ('carriage_plate', 'tof_arm')"
        d = generate({'cad/rig_hardware.py': [(tof, tof.replace('3.5', '4.0'))]})
        self.assertEqual(joint(d, 'rig.tof_arm')['verdict'], 'fix')
        self.assertEqual(joint(d, 'rig.pendant_clip')['verdict'], 'owner')
        pend = "'min_engage': 3.5, 'holds': ('pendant_clip', 'pod')"
        d = generate({'cad/rig_hardware.py': [(pend, pend.replace('3.5', '4.5'))]})
        self.assertEqual(joint(d, 'rig.pendant_clip')['verdict'], 'fix')
        self.assertEqual(joint(d, 'rig.tof_arm')['verdict'], 'owner')
        self.assertIn('sets 3.5 mm', ' '.join(f['text'] for f in joint(self.doc, 'rig.tof_arm')['findings']))

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

    def test_control_a_stale_note_comes_back(self):
        """A note quoted by a finding: the finding goes when the note is fixed and returns with the stale text."""
        self.assertIn('note-vs-joint', codes(self.doc, 'leg.wheel_botwheel'))          # the leg's: still stale
        d = generate({'cad/fivebar.py': [('its 4 x M6 x 40', 'its 4 x M6 x 30')],
                      'catalog/hardware.json': [("the BotWheel's stator flange, 4 x M6 from inside the wheel link (4 per leg)",
                                                 "none on the robot now")]})
        self.assertNotIn('note-vs-joint', codes(d, 'leg.wheel_botwheel'))
        d = generate({'cad/body_shell.py': [("'PETG; four M3 x 8 into the wall\\'s nuts'", "'PETG; four M3 x 16 into the wall\\'s nuts'")]})
        self.assertIn('note-vs-joint', codes(d, 'body.printed_clamps'))

    def test_control_a_quoted_literal_that_goes_stops_generation(self):
        with self.assertRaises(inv.Stale):
            generate({'cad/turret.py': [("'foot_holes_x': (-3.0, 33.0, 58.0, 77.0)", "'foot_holes_x': (-3.0, 33.0, 58.0, 78.0)")]})


if __name__ == '__main__':
    unittest.main(verbosity=1)
