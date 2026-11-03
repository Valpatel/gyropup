#!/usr/bin/env python3
"""Checks of the turret lids' snap fits (#131 wave 1), kernel-free and toolkit-free.

Nothing here imports cadagent or a CAD kernel: it reads the committed snaps.yaml, snapfit.json (cad-agent's own
output at the pinned release) and summary.json. snaps.yaml must be what cad/turret_snaps.py declares (the constants
cad/turret.py builds the latches from; cad/test_turret_snaps.py measures the CAD against the same file), the toolkit's
result must be bound to it and pass every row, its numbers must recompute by hand from the declared inputs, and every
check of the summary must follow from them. Controls tamper with copies and expect each check to catch it. With
CAD_AGENT set to a cad-agent checkout at the pin, the toolkit is run again and must give the committed JSON.

    python3 research/snap-fits/test_snaps.py
"""
import copy
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import snaps as sn  # noqa: E402

ts = sn.ts


def load():
    return json.loads(sn.RESULT.read_text()), json.loads(sn.SUMMARY.read_text())


def handcalc(result):
    """The toolkit's numbers again from the guide's closed form, for a constant-section rectangle (design 1): root
    strain eps = y h / (0.67 L^2); P = (b h^2 / 6) E eps / L; W = P (mu + tan a) / (1 - mu tan a)."""
    bad = []
    spec = {s['name']: s for s in ts.spec()['snaps']}
    for r in result['snaps']:
        s = spec[r['name']]
        L, u = s['length_mm'], s['undercut_mm']
        b, h = s['section']['rect']['width_mm'], s['section']['rect']['thickness_mm']
        eps = u * h / (0.67 * L ** 2)
        if abs(eps - r['strain']) > 1e-9:
            bad.append(f"{r['name']}: strain {r['strain']} vs {eps} by hand")
        m = r['material']
        for key, e in (('deflection_force_n', m['secant_mpa']), ('retention_deflection_force_n', m['retention_secant_mpa'])):
            p = b * h * h / 6 * e * eps / L
            if key in r and abs(p - r[key]) > 1e-9 * p:
                bad.append(f"{r['name']}: {key} {r[key]} vs {p} by hand")
        mu = s['friction']
        if abs(m['friction'] - mu) > 1e-12:
            bad.append(f"{r['name']}: friction {m['friction']} vs declared {mu}")
        w = r['deflection_force_n'] * sn.wedge(mu, s['lead_deg'])
        if abs(w - r['mating_force_n']) > 1e-9 * w:
            bad.append(f"{r['name']}: mating {r['mating_force_n']} vs {w} by hand")
        p_ret = r.get('retention_deflection_force_n', r['deflection_force_n'])
        sep = p_ret * sn.wedge(mu, s['return_deg'])
        if abs(sep - r['separation_force_n']) > 1e-9 * sep:
            bad.append(f"{r['name']}: separation {r['separation_force_n']} vs {sep} by hand")
        allow = 0.6 * 0.7 * 51 / 2780                                    # Bambu PETG Basic V3.0 along: UTS / E, x 0.6 repeated
        if abs(m['allowable'] - allow) > 1e-12:
            bad.append(f"{r['name']}: allowable {m['allowable']} vs {allow}")
    return bad


def summary_follows(result, summary):
    """Every number and verdict of summary.json again from snapfit.json."""
    fresh = sn.document(json.dumps(result, indent=2) + '\n', summary['toolkit']['tag'], summary['toolkit']['commit'])
    bad = []
    for part, lid in summary['lids'].items():
        f = fresh['lids'][part]
        for k, v in lid['per_latch'].items():
            if abs(v - f['per_latch'][k]) > 1e-9 * max(1.0, abs(v)):
                bad.append(f'{part} {k}: {v} vs {f["per_latch"][k]}')
        for c, fc in zip(lid['checks'], f['checks']):
            if c['pass'] != fc['pass'] or c['check'] != fc['check']:
                bad.append(f"{part} {c['check']}: recorded {c['pass']}, the numbers say {fc['pass']}")
        if lid['pass'] != all(c['pass'] for c in lid['checks']):
            bad.append(f'{part}: pass does not follow from its checks')
    return bad


class Snaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result, cls.summary = load()

    def test_current(self):
        self.assertEqual(sn.stale(), [], 'run python3 research/snap-fits/snaps.py --cad-agent PATH')

    def test_yaml_is_the_constants(self):
        """snaps.yaml is cad/turret_snaps.py's declaration, number for number."""
        self.assertEqual(sn.SPEC.read_text(), ts.yaml_text())
        names = [s['name'] for s in ts.spec()['snaps']]
        self.assertEqual(names, ['hopper_lid-latch-mu-low', 'hopper_lid-latch-mu-high', 'board_bay_lid-latch-mu-low',
                                 'board_bay_lid-latch-mu-high'])
        for s in ts.spec()['snaps']:
            lat = ts.LATCHES[s['name'].split('-latch')[0]]
            self.assertEqual((s['length_mm'], s['section']['rect']['thickness_mm'], s['undercut_mm']), (lat['L'], lat['h'], ts.UNDERCUT))
            self.assertAlmostEqual(s['section']['rect']['width_mm'], ts.tongue_width(lat), places=4)
            self.assertEqual(s['root_radius_mm'], round(0.6 * lat['h'], 3))
            self.assertEqual((s['material'], s['orientation'], s['repeated']), ('petg-bambu-basic', 'along', True))

    def test_bound_to_spec_and_toolkit(self):
        self.assertEqual(self.summary['toolkit']['tag'], sn.PIN)
        self.assertRegex(self.summary['toolkit']['commit'], r'^[0-9a-f]{40}$')
        self.assertEqual(self.summary['spec']['sha256'], sn.sha256(sn.SPEC))
        self.assertEqual(self.summary['result']['sha256'], sn.sha256(sn.RESULT))

    def test_every_toolkit_row_passes(self):
        self.assertTrue(self.result['pass'])
        self.assertEqual(len(self.result['snaps']), 4)
        for s in self.result['snaps']:
            self.assertTrue(s['pass'], s['name'])
            checks = {r['check'] for r in s['rows']}
            self.assertTrue({'root strain', 'root radius'} <= checks, s['name'])
            self.assertIn('retention force' if s['name'].endswith('low') else 'mating force', checks)
            for r in s['rows']:
                self.assertTrue(r['pass'], f"{s['name']} {r['check']}")
            self.assertEqual(s['warnings'], [], s['name'])
            self.assertEqual(s['material']['orientation'], 'along')

    def test_handcalc(self):
        self.assertEqual(handcalc(self.result), [])

    def test_summary_follows(self):
        self.assertEqual(summary_follows(self.result, self.summary), [])
        self.assertTrue(self.summary['pass'])

    def test_load_golden(self):
        """The hopper lid's load by hand: 30 balls x 1.83 g + the lid's 32 g bound, at 30 g x sin 25 deg."""
        f = (30 * 1.83 + 32.0) / 1000 * 9.81 * 30 * math.sin(math.radians(25))
        self.assertAlmostEqual(f, 10.808, places=3)
        lid = self.summary['lids']['hopper_lid']
        self.assertAlmostEqual(lid['load']['force_n'], f, places=9)
        self.assertAlmostEqual(lid['load']['required_n'], 1.2 * f, places=9)
        self.assertAlmostEqual(self.summary['lids']['board_bay_lid']['load']['force_n'], 14.5 / 1000 * 9.81 * 30, places=9)

    def test_load_cases(self):
        """Each lid's declared cases are what summary.json weighed: one design case (the load), every included case
        held, and the one excluded case (the hopper upside down) not held, with its reason, which says no detent of
        these latches holds it and pulls off by hand: the pull-off it would take is over the hand limit."""
        for part, lid in self.summary['lids'].items():
            cases = lid['load_cases']
            declared = ts.load_cases(part)
            self.assertEqual([(c['case'], c['status']) for c in cases], [(c['case'], c['status']) for c in declared])
            design = [c for c in cases if c['status'] == 'design']
            self.assertEqual(len(design), 1)
            self.assertAlmostEqual(design[0]['required_n'], lid['load']['required_n'], places=9)
            held = lid['latches'] * lid['per_latch']['retention_low_n']
            for c in cases:
                self.assertAlmostEqual(c['retained_n'], held, places=9)
                if c['status'] == 'excluded':
                    self.assertTrue(c['reason'] and not c['held'] and c['pull_off_needed_n'] > ts.HAND_N, c['case'])
                else:
                    self.assertTrue(c['held'] and c['required_n'] <= design[0]['required_n'] + 1e-9, c['case'])
        excluded = [c['case'] for lid in self.summary['lids'].values() for c in lid['load_cases'] if c['status'] == 'excluded']
        self.assertEqual(excluded, [ts.hopper_inverted_load()['case']])
        up = self.summary['lids']['hopper_lid']['load_cases'][-1]
        f = (30 * 1.83 + 32.0) / 1000 * 9.81 * 30
        self.assertAlmostEqual(up['required_n'], 1.2 * f, places=9)                            # 30.7 N
        lid = self.summary['lids']['hopper_lid']['per_latch']
        self.assertAlmostEqual(up['pull_off_needed_n'], 1.2 * f * lid['pull_off_high_n'] / lid['retention_low_n'], places=9)

    def test_combined_strain_golden(self):
        """The strain at the root's corner by hand: eps = u h / (0.67 L^2), in-plane x k_strain, out-of-plane
        eps x k_force x W/P x h / b, at each friction bound; under the allowable at the high one."""
        for part, lid in self.summary['lids'].items():
            lat = ts.LATCHES[part]
            eps = ts.UNDERCUT * lat['h'] / (0.67 * lat['L'] ** 2)
            k = lid['curved_beam']
            b = lat['s_hi'] - lat['s_lo']
            for mu, key in ((0.35, 'combined_strain_low'), (0.60, 'combined_strain_high')):
                t30 = math.tan(math.radians(30))
                w = (mu + t30) / (1 - mu * t30)
                self.assertAlmostEqual(lid['per_latch'][key], eps * (k['k_strain'] + k['k_force'] * w * lat['h'] / b), places=12)
            self.assertLess(lid['per_latch']['combined_strain_high'], lid['per_latch']['allowable'])

    def test_root_anchor_golden(self):
        """The hopper's root block by hand: Roark's rectangle 8 x 6.3 (a/c 1.27: alpha 0.2194) twisted by p L, plus
        p as a shear; peeled by pull L (6 M / (c a^2)) plus the pull."""
        lid = self.summary['lids']['hopper_lid']
        lat = ts.HOPPER
        a, c = 8.0, 1.3 + 2.0 + 3.0
        self.assertEqual(lid['arm']['root_block_mm'], [a, c])
        alpha = 0.208 + (0.231 - 0.208) * (a / c - 1.0) / 0.5
        pull = lid['per_latch']['pull_off_high_n']
        t30 = math.tan(math.radians(30))
        p = pull / ((0.6 + t30) / (1 - 0.6 * t30))
        self.assertAlmostEqual(lid['per_latch']['block_twist_mpa'], p * lat['L'] / (alpha * a * c * c) + p / (a * c), places=9)
        self.assertAlmostEqual(lid['per_latch']['block_peel_mpa'], 6 * pull * lat['L'] / (c * a * a) + pull / (a * c), places=9)

    def test_hand_alone_agrees(self):
        """hand_latch (the closed form alone, for sizes the toolkit was not run on) gives summary.json's numbers for
        the current sizes, and its material is the toolkit's."""
        for part, lid in self.summary['lids'].items():
            h = sn.hand_latch(ts.LATCHES[part])
            per = lid['per_latch']
            for k, kp in (('retention_low_n',) * 2, ('pull_off_high_n',) * 2, ('push_on_high_n',) * 2,
                          ('twist_mpa', 'block_twist_mpa'), ('peel_mpa', 'block_peel_mpa'), ('tongue_twist_mpa',) * 2,
                          ('allowable',) * 2):
                self.assertAlmostEqual(h[k], per[kp], places=9, msg=f'{part} {k}')
            self.assertAlmostEqual(h['combined_high'], per['combined_strain_high'], places=12)
        for s in self.result['snaps']:
            m = s['material']
            self.assertEqual((m['secant_mpa'], m['retention_secant_mpa']),
                             (sn.HAND_MATERIAL['secant_mpa'], sn.HAND_MATERIAL['retention_secant_mpa']))

    def test_coupon_bands(self):
        """Each coupon's bands: the pull-off between the latch's share of the required retention and of the hand
        limit, the push-on under the latter; the predictions inside; the undercut's room by the strain."""
        for part, lid in self.summary['lids'].items():
            cp, n = lid['coupon'], lid['latches']
            self.assertEqual(cp['pull_off_band_n'], [lid['load']['required_n'] / n, ts.HAND_N / n])
            lo, hi = cp['pull_off_band_n']
            pr = cp['predicted_n']
            self.assertTrue(lo <= pr['retention_low'] and pr['pull_off_high'] <= hi and pr['push_on_high'] <= cp['push_on_max_n'])
            self.assertEqual(cp['cycles'], 2 * ts.LATCHES[part]['cycles'])
            self.assertGreater(cp['undercut']['max_by_strain_mm'], ts.UNDERCUT)
            h = ts.LATCHES[part]['h']
            self.assertAlmostEqual(cp['print_tolerance']['force_factor'][1], 1.1 * (h + 0.1) ** 3 / h ** 3, places=12)

    def test_coupon_verdict(self):
        """A measured coupon read against the hopper's bands: in band, pass; under, a deeper undercut; over, a
        shallower one; a pull-off too low for any step the strain allows, redesign; a push-on over its limit with a
        pull-off already at the band's foot, the return angle."""
        cp = self.summary['lids']['hopper_lid']['coupon']
        lo, hi = cp['pull_off_band_n']
        v = sn.coupon_verdict
        self.assertEqual(v(cp, (lo + hi) / 2, (lo + hi) / 2)['action'], 'pass')
        under = v(cp, 0.8 * lo, 0.8 * lo)
        self.assertEqual((under['action'], under['undercut_mm'] > ts.UNDERCUT), ('undercut', True))
        over = v(cp, 1.15 * hi, 1.15 * hi)
        self.assertEqual((over['action'], over['undercut_mm'] < ts.UNDERCUT), ('undercut', True))
        self.assertTrue(lo <= 1.15 * hi * over['undercut_mm'] / ts.UNDERCUT <= hi)
        self.assertEqual(v(cp, 0.4 * lo, 0.4 * lo)['action'], 'redesign')
        self.assertEqual(v(cp, 1.01 * lo, 1.05 * cp['push_on_max_n'])['action'], 'return angle')

    def test_curved_beam_golden(self):
        """The arc's Castigliano factors for the hopper's tongue (L 26 on r 53.2) by hand, and their limits: a short
        arc is a straight beam."""
        phi = 26.0 / 53.2
        k_force = (phi ** 3 / 3) / (phi / 2 - math.sin(2 * phi) / 4)
        k = self.summary['lids']['hopper_lid']['curved_beam']
        self.assertAlmostEqual(k['k_force'], k_force, places=9)
        self.assertAlmostEqual(k['k_strain'], k_force * math.sin(phi) / phi, places=9)
        self.assertTrue(1.0 < k['k_force'] < 1.1 and 1.0 < k['k_strain'] < 1.02)
        lat = dict(ts.HOPPER, L=0.5)                                     # a short arc tends to the straight beam
        self.assertAlmostEqual(sn.curved(lat)['k_force'], 1.0, places=4)

    def test_profile(self):
        """The (s, n) profile: the barb overlaps the ridge by the undercut, its return face is the ridge's back face
        moved PLAY along s, both 30 deg; the ridge's entry face is steeper than the barb's lead."""
        P = ts.profile()
        (r0, r1, r2, r3), (b0, b1, b2, b3) = P['ridge'], P['barb']
        self.assertAlmostEqual(r1[1] - b1[1], ts.UNDERCUT)
        self.assertAlmostEqual(b0[1] - r1[1], ts.TONGUE_GAP)
        slope = lambda p, q: math.degrees(math.atan2(abs(q[1] - p[1]), abs(q[0] - p[0])))
        self.assertAlmostEqual(slope(r2, r3), ts.RETURN_DEG)
        self.assertAlmostEqual(slope(b0, b1), ts.RETURN_DEG)
        self.assertAlmostEqual(slope(b2, b3), ts.LEAD_DEG)
        self.assertGreater(slope(r0, r1), ts.LEAD_DEG)
        # the return faces are one line apart by PLAY along s
        at = lambda p, q, n: p[0] + (q[0] - p[0]) * (n - p[1]) / (q[1] - p[1])
        self.assertAlmostEqual(at(b0, b1, 0.7) - at(r2, r3, 0.7), ts.PLAY)
        self.assertAlmostEqual(P['barb_s'][1], b3[0])
        for lat in ts.LATCHES.values():                                  # every tongue carries its whole barb
            self.assertTrue(lat['s_lo'] <= -ts.PLATE_T and lat['s_hi'] >= b3[0])

    def test_public_text(self):
        """No local paths in the committed files (the toolkit is named by tag and commit only)."""
        for path in (sn.SPEC, sn.RESULT, sn.SUMMARY):
            text = path.read_text()
            for bad in ('/home/', '/tmp/', '/Users/', 'C:\\'):
                self.assertNotIn(bad, text, path.name)

    def test_live_toolkit(self):
        """With CAD_AGENT at the pin, the toolkit run again gives the committed snapfit.json."""
        path = os.environ.get('CAD_AGENT')
        if not path:
            self.skipTest('set CAD_AGENT to a cad-agent checkout at ' + sn.PIN)
        if sn.toolkit_id(Path(path))[0] != sn.PIN:
            self.skipTest(f'CAD_AGENT is not at {sn.PIN}')
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest('the toolkit reads YAML: run with a Python that has PyYAML')
        self.assertEqual(sn.run_toolkit(Path(path), sn.SPEC), sn.RESULT.read_text())


class Controls(unittest.TestCase):
    """Each check catches a tampered copy or a design that does not hold."""

    @classmethod
    def setUpClass(cls):
        cls.result, cls.summary = load()

    def test_stale_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            y = Path(tmp) / 'snaps.yaml'
            y.write_text(sn.SPEC.read_text().replace('length_mm: 26.0', 'length_mm: 30.0', 1))
            self.assertIn('snaps.yaml does not match cad/turret_snaps.py', sn.stale(spec=y))

    def test_stale_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'turret_snaps.py'
            shutil.copy(sn.CONSTANTS, c)
            c.write_text(c.read_text() + '\n# edited\n')
            self.assertIn('cad/turret_snaps.py changed since summary.json was generated', sn.stale(constants=c))

    def test_stale_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp) / 'snapfit.json'
            r.write_text(sn.RESULT.read_text().replace('"pass": true', '"pass": false', 1))
            self.assertIn('snapfit.json changed since summary.json was generated', sn.stale(result=r))

    def test_tampered_strain(self):
        r = copy.deepcopy(self.result)
        r['snaps'][0]['strain'] *= 0.9
        self.assertTrue(handcalc(r))

    def test_tampered_force(self):
        r = copy.deepcopy(self.result)
        r['snaps'][1]['mating_force_n'] *= 0.9
        self.assertTrue(handcalc(r))

    def test_flipped_verdict(self):
        s = copy.deepcopy(self.summary)
        s['lids']['hopper_lid']['checks'][2]['pass'] = False
        self.assertTrue(summary_follows(self.result, s))

    def test_stiffer_arm_fails_the_hand_limit(self):
        """The same hopper latch 20 % stiffer (the push and pull at the high bound) goes over 50 N for the lid."""
        r = copy.deepcopy(self.result)
        for s in r['snaps']:
            if s['name'].startswith('hopper_lid'):
                for k in ('deflection_force_n', 'mating_force_n'):
                    s[k] *= 1.2
        lid = sn.lid_summary('hopper_lid', r)
        failed = {c['check'] for c in lid['checks'] if not c['pass']}
        self.assertEqual(failed, {'pull-off, all latches, high bound', 'push-on, all latches, high bound'})

    def test_old_sizing_fails(self):
        """The sizes the review of PR #181 failed (ts.OLD): the strain at the root's corner, with the out-of-plane
        bending, over the allowable at the high bound on both lids (0.96 % and 0.91 % against 0.77 %), and the root
        blocks' layers twisted past half the interlaminar strength (the hopper's 9.2 MPa by hand against the review's
        FE, p90 8.7 MPa: the hand model reads a little high)."""
        for part, lat in ts.OLD.items():
            h = sn.hand_latch(lat)
            self.assertGreater(h['combined_high'], h['allowable'], part)
            self.assertLess(h['strain'] * sn.curved(lat)['k_strain'], h['allowable'], part)     # in-plane alone passed
            self.assertGreater(h['twist_mpa'], ts.PETG_SHEAR_MPA / 2, part)
        self.assertTrue(8.7 <= sn.hand_latch(ts.OLD['hopper_lid'])['twist_mpa'] <= 10.0)

    def test_an_unheld_case_included_fails(self):
        """Declared as included, the upside-down case fails the load-case row: the exclusion is what lets it pass."""
        orig = ts.load_cases
        try:
            ts.load_cases = lambda part: [dict(c, status='included') for c in orig(part)]
            lid = sn.lid_summary('hopper_lid', self.result)
        finally:
            ts.load_cases = orig
        self.assertEqual({c['check'] for c in lid['checks'] if not c['pass']}, {'load cases: every included case held'})

    def test_softer_arm_fails_retention(self):
        """The same hopper latch 25 % softer at the low bound no longer holds the fall."""
        r = copy.deepcopy(self.result)
        for s in r['snaps']:
            if s['name'].startswith('hopper_lid'):
                s['separation_force_n'] *= 0.75
        lid = sn.lid_summary('hopper_lid', r)
        self.assertIn('retention, all latches, low bound', {c['check'] for c in lid['checks'] if not c['pass']})


if __name__ == '__main__':
    unittest.main(verbosity=1)
