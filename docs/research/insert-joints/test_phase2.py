#!/usr/bin/env python3
"""Checks of phase 2 (the joints through cad-agent's insert and limiter checks), kernel-free and toolkit-free.

CI pins an older cad-agent without these modules, so nothing here imports cadagent: it reads phase2.json. The
committed outputs must be bound to the joints.json and the generator they came from, cover every joint, carry a reason
for every disagreement and skip, and hold numbers that recompute by hand from their recorded SI inputs. Controls
tamper with a copy and expect each check to catch it.
"""
import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phase2 as p2  # noqa: E402

STATUSES = ('agree', 'disagree')


def load():
    return json.loads(p2.OUT_JSON.read_text()), json.loads(p2.JOINTS.read_text())


def coverage(doc, joints):
    """Every joint of joints.json once, in order; evaluated ones compared, skipped ones with a reason."""
    bad = []
    ids = [j['id'] for j in joints['joints']]
    got = [e['id'] for e in doc['joints']]
    if got != ids:
        bad.append(f'joints differ from joints.json: missing {sorted(set(ids) - set(got))}, extra '
                   f'{sorted(set(got) - set(ids))}, or out of order')
    with_insert = {j['id'] for j in joints['joints'] if j.get('insert')}
    for e in doc['joints']:
        if e['status'] == 'evaluated':
            if not e.get('comparisons'):
                bad.append(f"{e['id']}: evaluated with no comparison")
            if not (e.get('call') or {}).get('sources'):
                bad.append(f"{e['id']}: no record of where its inputs came from")
        elif e['status'] == 'skipped':
            if not (e.get('reason') or '').strip():
                bad.append(f"{e['id']}: skipped without a reason")
            if e['id'] in with_insert:
                bad.append(f"{e['id']}: an insert joint was skipped")
        else:
            bad.append(f"{e['id']}: status {e['status']!r}")
    return bad


def wellformed(doc):
    """Each comparison names its check, a stated tolerance and a status; each disagreement says why; the summary adds
    up."""
    bad = []
    tols = set(doc['tolerances'].values())
    n = {'agree': 0, 'disagree': 0}
    for e in doc['joints']:
        for c in e.get('comparisons', []):
            where = f"{e['id']} {c.get('check')}"
            if c.get('status') not in STATUSES:
                bad.append(f'{where}: status {c.get("status")!r}')
                continue
            n[c['status']] += 1
            if not any(c.get('tolerance', '').startswith(t) for t in tols):
                bad.append(f'{where}: tolerance not one of the stated ones')
            if c['status'] == 'disagree' and not (c.get('why') or '').strip():
                bad.append(f'{where}: disagrees without a reason')
            if c.get('inventory') is None or c.get('toolkit') is None:
                bad.append(f'{where}: a side is missing')
    s = doc['summary']
    if (s['agree'], s['disagree']) != (n['agree'], n['disagree']):
        bad.append(f"summary says {s['agree']} / {s['disagree']}, the joints hold {n['agree']} / {n['disagree']}")
    if s['evaluated'] + s['skipped'] != s['joints'] or s['joints'] != len(doc['joints']):
        bad.append('summary joint counts do not add up')
    return bad


def rederive(doc):
    """Each numeric agree / disagree again from the recorded numbers and the stated tolerance."""
    bad = []
    for e in doc['joints']:
        for c in e.get('comparisons', []):
            inv, tk = c['inventory'], c['toolkit']
            if c['tolerance'] == doc['tolerances']['band'] and c['check'] == 'pull-out capacity':
                agree = tk['low_n'] <= inv['value_n'] <= tk['high_n']
            elif c['tolerance'] == doc['tolerances']['band'] and c['check'] == 'preload at torque':
                agree = tk['low_n'] <= inv['preload_n'] <= tk['high_n']
            elif c['tolerance'] == doc['tolerances']['side']:
                agree = (inv['sf'] >= 2.0) == (tk['sf_low'] >= 2.0)
            elif c['tolerance'] == doc['tolerances']['pct25']:
                agree = abs(inv['preload_n'] / tk['preload_n'] - 1.0) <= 0.25
            elif c['check'] == 'clamp path':
                agree = inv['path'] == tk['path']
            elif c['check'] == 'tightening torque':
                agree = inv['flagged'] == (tk['verdict'] != 'pass')
            elif c['check'] == 'boss':
                agree = inv['verdict'] == ('pass' if tk['verdict'] == 'pass' else 'warn')
            else:
                agree = inv['verdict'] == tk['verdict']
            if agree != (c['status'] == 'agree'):
                bad.append(f"{e['id']} {c['check']}: recorded {c['status']}, the numbers say "
                           f"{'agree' if agree else 'disagree'}")
    return bad


def handcalc(doc):
    """The toolkit's formulas again by hand from the SI inputs each comparison records, and their units."""
    bad = []
    for e in doc['joints']:
        for c in e.get('comparisons', []):
            si, tk = c.get('si'), c['toolkit']
            if not si:
                continue
            v = {k: x['value'] for k, x in si.items()}
            if not all(x.get('source') for x in si.values()):
                bad.append(f"{e['id']} {c['check']}: an SI input without its source")
            lengths = [x for k, x in v.items() if k.endswith('_m')]
            if any(not 0 < x < 0.1 for x in lengths):
                bad.append(f"{e['id']} {c['check']}: a length not in metres ({lengths})")
            if c['check'] == 'pull-out capacity':
                if not 1e6 < v['shear_strength_pa'] < 1e8:
                    bad.append(f"{e['id']}: shear strength {v['shear_strength_pa']} is not in pascals")
                for k in ('low', 'mid', 'high'):
                    f = (v['calibration'][k] * v['shear_strength_pa'] * math.pi * v['outer_diameter_m'] * v['length_m']
                         * v['basis_scale'])
                    if abs(f - tk[f'{k}_n']) > 1e-4 * f:
                        bad.append(f"{e['id']} pull-out {k}: c tau pi D L = {f:.1f} N, recorded {tk[f'{k}_n']}")
            if c['check'] == 'melt volume':
                disp = v['insert_volume_m3'] - math.pi / 4 * (v['hole_diameter_m'] ** 2 - v['bore_diameter_m'] ** 2) * v['length_m']
                pocket = math.pi / 4 * v['hole_diameter_m'] ** 2 * max(v['depth_m'] - v['length_m'], 0.0)
                for name, x, rec in (('displaced', disp, tk['displaced_m3']), ('pocket', pocket, tk['pocket_m3'])):
                    if abs(x - rec) > 1e-4 * abs(x) + 1e-12:
                        bad.append(f"{e['id']} melt {name}: {x:.4g} m3 by hand, recorded {rec}")
    return bad


# the counts per check this release gives (v0.18.2); a change is a finding to explain, not to paste over
BY_CHECK = {
    'pilot diameter': {'agree': 0, 'disagree': 36}, 'pilot depth': {'agree': 32, 'disagree': 0},
    'melt volume': {'agree': 18, 'disagree': 5}, 'screw tip': {'agree': 12, 'disagree': 8},
    'boss': {'agree': 18, 'disagree': 0}, 'insert axis': {'agree': 36, 'disagree': 0},
    'clamp path': {'agree': 22, 'disagree': 0}, 'pull-out capacity': {'agree': 24, 'disagree': 12},
    'pull-out margin': {'agree': 16, 'disagree': 1}, 'preload at torque': {'agree': 5, 'disagree': 0},
    'tightening torque': {'agree': 4, 'disagree': 1}, 'head bearing preload': {'agree': 5, 'disagree': 0},
}


def comparison(doc, jid, check):
    e = next(e for e in doc['joints'] if e['id'] == jid)
    return next(c for c in e['comparisons'] if c['check'] == check)


class Phase2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.joints = load()

    def test_current(self):
        self.assertEqual(p2.stale(), [], 'run python3 research/insert-joints/phase2.py --cad-agent PATH')

    def test_bound_to_joints_and_toolkit(self):
        self.assertEqual(self.doc['joints_json']['sha256'], p2.sha256(p2.JOINTS))
        self.assertEqual(self.doc['toolkit']['tag'], p2.PIN)
        self.assertRegex(self.doc['toolkit']['commit'], r'^[0-9a-f]{40}$')
        self.assertEqual(set(self.doc['toolkit']['modules']), set(p2.MODULES))

    def test_coverage(self):
        self.assertEqual(coverage(self.doc, self.joints), [])
        self.assertGreater(self.doc['summary']['evaluated'], 30)

    def test_wellformed(self):
        self.assertEqual(wellformed(self.doc), [])

    def test_rederive(self):
        self.assertEqual(rederive(self.doc), [])

    def test_handcalc(self):
        self.assertEqual(handcalc(self.doc), [])

    def test_golden(self):
        """Fixed values, by hand: a check that the units and the inputs are the ones the toolkit documents."""
        c = comparison(self.doc, 'leg.hip_frame_mount', 'pull-out capacity')
        si = {k: x['value'] for k, x in c['si'].items()}
        self.assertAlmostEqual(si['outer_diameter_m'], 7.11e-3)          # 94459A775's knurl, McMaster's STEP
        self.assertAlmostEqual(si['length_m'], 7.9e-3)
        self.assertAlmostEqual(si['shear_strength_pa'], 12.75e6)         # half PA6-CF20 wet's 25.5 MPa across
        low = 0.5067196392044561 * 12.75e6 * math.pi * 7.11e-3 * 7.9e-3  # c low: CNC Kitchen's PETG / PolyLite PETG
        self.assertAlmostEqual(low, 1140.05, places=1)                    # on the Polymaker sheet
        self.assertAlmostEqual(si['basis_scale'], 22.67 / 25.5, places=5)  # to the inventory's humid basis
        self.assertAlmostEqual(c['toolkit']['sheet_n']['low'], low, delta=0.01)
        self.assertAlmostEqual(c['toolkit']['low_n'], low * 22.67 / 25.5, delta=0.01)
        m = comparison(self.doc, 'body.bus_insulator', 'melt volume')
        disp = 42.13e-9 - math.pi / 4 * (3.75e-3 ** 2 - 2.35e-3 ** 2) * 5.7e-3   # the 4.0 pilot printed 0.25 small
        self.assertAlmostEqual(disp * 1e9, 3.898, places=3)
        self.assertAlmostEqual(m['toolkit']['displaced_m3'], disp, delta=1e-13)
        self.assertAlmostEqual(m['toolkit']['pocket_m3'], math.pi / 4 * 3.75e-3 ** 2 * (6.5e-3 - 5.7e-3), delta=1e-13)
        self.assertAlmostEqual(m['toolkit']['as_drawn']['displaced_m3'] * 1e9, -4.775, places=3)
        w = next(e for e in self.doc['joints'] if e['id'] == 'leg.wheel_botwheel')['toolkit_only']['own_washer']
        area = math.pi / 4 * (11.0 ** 2 - 6.6 ** 2)                        # the DIN 433 on the 6.6 hole, mm2
        self.assertAlmostEqual(w['area_m2'] * 1e6, area, places=2)
        self.assertAlmostEqual(w['preload_cap_n'], 54.7e6 / 2 * area * 1e-6, delta=0.5)
        self.assertAlmostEqual(w['allowed_nm'], 1.18, delta=0.01)
        h = comparison(self.doc, 'leg.upper_link_hub', 'head bearing preload')
        self.assertAlmostEqual(h['inventory']['preload_n'], 25.0 * 33.0, places=0)   # 25 MPa on 33 mm2
        area = math.pi / 4 * (8.03 ** 2 - 5.5 ** 2)                        # ISO 4762 M5 dw min on the 5.5 hole
        self.assertAlmostEqual(h['toolkit']['area_mm2'], area, places=1)
        self.assertAlmostEqual(h['toolkit']['preload_n'], 54.7 / 2 * area, delta=1.0)   # PA6-CF20 wet along / 2
        t = comparison(self.doc, 'leg.hip_frame_mount', 'preload at torque')
        k = t['toolkit']['nut_factor']
        self.assertAlmostEqual(t['toolkit']['high_n'], 1.5 / (k['low'] * 5e-3), delta=0.01)
        self.assertAlmostEqual(t['toolkit']['low_n'], 1.5 / (k['high'] * 5e-3), delta=0.01)

    def test_by_check_golden(self):
        """The counts per check, fixed: a generator that regenerates but reads a field wrongly moves them."""
        self.assertEqual(self.doc['summary']['by_check'], BY_CHECK)

    def test_joint_goldens(self):
        """Inputs and verdicts of a few joints, fixed by hand from joints.json and the toolkit's rules."""
        call = {e['id']: e['call']['kwargs'] for e in self.doc['joints'] if e['status'] == 'evaluated'}
        self.assertEqual(call['body.post_m3']['axis'], 'lying')            # joints.json axis layer-plane
        self.assertEqual(call['leg.hip_frame_mount']['axis'], 'upright')   # print-z
        self.assertEqual(call['body.post_m3']['head_mm'], 5.6)             # clamp.bearing_od_mm (a pan head)
        self.assertEqual(call['leg.wheel_botwheel']['head_washer'], 'iso7089')
        self.assertEqual(call['body.riser_top_tm']['clamped'],            # D76: the pan base's 5 mm foot (the plinth's tray was 4.5)
                         {'material': 'pa6-cf20-polymaker-wet', 'thickness_mm': 5.0})
        self.assertEqual(call['body.post_m5']['clamped'], {'material': 'metal'})
        m = comparison(self.doc, 'body.riser_top_tm', 'pull-out margin')
        self.assertAlmostEqual(m['toolkit']['sf_low'], 3.24, places=2)     # its low end: 1014 N / 313 N (D76; 1.58 at 640 N)
        self.assertEqual(m['status'], 'agree')
        d = comparison(self.doc, 'body.bay_rail_side', 'pilot depth')    # 6.5 deep: under L + 2 pitches, a note
        self.assertEqual((d['inventory']['verdict'], d['toolkit']['verdict'], d['status']), ('warn', 'warn', 'agree'))
        t = comparison(self.doc, 'leg.hip_frame_mount', 'tightening torque')
        self.assertTrue(t['inventory']['flagged'])                          # preload-vs-pullout
        self.assertEqual(t['toolkit']['governed_by'], 'insert_face')
        a = comparison(self.doc, 'body.post_m3', 'insert axis')
        self.assertEqual((a['inventory']['verdict'], a['toolkit']['verdict']), ('warn', 'warn'))
        h = comparison(self.doc, 'body.post_m3', 'head bearing preload')
        self.assertAlmostEqual(h['toolkit']['area_mm2'], math.pi / 4 * (5.6 ** 2 - 3.4 ** 2), places=2)

    def test_markdown_from_json(self):
        md = p2.OUT_MD.read_text()
        self.assertEqual(md, p2.markdown(self.doc))
        for e in self.doc['joints']:
            if e['status'] == 'skipped':
                self.assertIn(f"`{e['id']}`: {e['reason']}", md)

    def test_public_text(self):
        """No local paths in the committed outputs (the toolkit is named by tag and commit only)."""
        for path in (p2.OUT_JSON, p2.OUT_MD):
            text = path.read_text()
            for bad in ('/home/', '/tmp/', '/Users/', 'C:\\'):
                self.assertNotIn(bad, text, path.name)


class Controls(unittest.TestCase):
    """Each check catches a tampered copy."""

    @classmethod
    def setUpClass(cls):
        cls.doc, cls.joints = load()

    def tampered(self):
        return copy.deepcopy(self.doc)

    def test_stale_joints(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            j = tmp / 'joints.json'
            j.write_text(p2.JOINTS.read_text().replace('"tip_room_mm": 0.5', '"tip_room_mm": 0.6', 1))
            self.assertIn('joints.json changed since phase2.json was generated', p2.stale(joints_path=j))

    def test_stale_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = Path(tmp) / 'phase2.py'
            g.write_text(Path(p2.__file__).read_text() + '\n# edited\n')
            self.assertIn('phase2.py changed since phase2.json was generated', p2.stale(generator=g))

    def test_stale_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / 'phase2.md'
            md.write_text(p2.OUT_MD.read_text().replace('disagree', 'differ', 1))
            self.assertIn('phase2.md does not match phase2.json', p2.stale(out_md=md))

    def test_dropped_joint(self):
        d = self.tampered()
        d['joints'] = [e for e in d['joints'] if e['id'] != 'body.post_m5']
        self.assertTrue(coverage(d, self.joints))

    def test_skip_without_reason(self):
        d = self.tampered()
        next(e for e in d['joints'] if e['status'] == 'skipped')['reason'] = ''
        self.assertTrue(coverage(d, self.joints))

    def test_insert_joint_skipped(self):
        d = self.tampered()
        e = next(e for e in d['joints'] if e['id'] == 'leg.hip_frame_mount')
        e.clear()
        e.update(id='leg.hip_frame_mount', status='skipped', reason='no time')
        self.assertTrue(coverage(d, self.joints))

    def test_disagreement_without_reason(self):
        d = self.tampered()
        c = next(c for e in d['joints'] for c in e.get('comparisons', []) if c['status'] == 'disagree')
        c['why'] = ' '
        self.assertTrue(wellformed(d))

    def test_flipped_status(self):
        d = self.tampered()
        c = next(c for e in d['joints'] for c in e.get('comparisons', [])
                 if c['check'] == 'pull-out capacity' and c['status'] == 'agree')
        c['status'] = 'disagree'
        c['why'] = 'tampered'
        self.assertTrue(rederive(d))
        self.assertTrue(wellformed(d))               # the summary no longer adds up

    def test_tampered_toolkit_number(self):
        d = self.tampered()
        c = next(c for e in d['joints'] for c in e.get('comparisons', []) if c['check'] == 'pull-out capacity')
        c['toolkit']['low_n'] *= 1.05
        self.assertTrue(handcalc(d))

    def test_millimetres_for_metres(self):
        d = self.tampered()
        c = next(c for e in d['joints'] for c in e.get('comparisons', []) if c['check'] == 'melt volume')
        c['si']['hole_diameter_m']['value'] *= 1000
        self.assertTrue(handcalc(d))


if __name__ == '__main__':
    unittest.main(verbosity=1)
