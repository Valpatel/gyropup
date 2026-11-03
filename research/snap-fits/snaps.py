#!/usr/bin/env python3
"""The turret lids' snap fits (#131 wave 1) through cad-agent's snap-fit calculator, at a pinned release.

cad/turret_snaps.py holds every snap dimension cad/turret.py builds the latches from. This writes its declaration to
snaps.yaml, runs the toolkit's own command on it,

    cad-agent snapfit research/snap-fits/snaps.yaml --output research/snap-fits/snapfit.json

and writes summary.json: the load cases each lid was weighed against (the design case, the ones it holds, the one
it does not and why), the toolkit's rows per latch, and the checks the toolkit does not make, by hand from its
numbers: the pull-off at the high bound against the hand limit, the totals over each lid's latches, the hopper's
curved tongues against the straight beam the toolkit assumes, the tongue twisted by a barb off its centre line, the
strain at the root's corner with the tongue's out-of-plane bending added to its in-plane bending, the root block's
layers twisted and peeled where it leaves the plate, the barb and the ridge in shear across the layers, and the
backing behind the thin walls. Also each lid's coupon protocol: pass bands, cycles and the knob to turn.

    python3 research/snap-fits/snaps.py --cad-agent PATH        # regenerate (PATH: a cad-agent checkout at the pin)
    python3 research/snap-fits/snaps.py --check                  # exit 1 if the committed files are stale
    python3 research/snap-fits/snaps.py --check --cad-agent PATH # also rerun the toolkit and compare

Run the toolkit with a Python that has PyYAML (the repository's .venv). This is a calculation, not a test: the
coupons (cad/turret.py snap_coupons) are printed and pulled before the numbers are trusted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'cad'))
import turret_snaps as ts  # noqa: E402

SPEC = HERE / 'snaps.yaml'
RESULT = HERE / 'snapfit.json'
SUMMARY = HERE / 'summary.json'
CONSTANTS = ROOT / 'cad' / 'turret_snaps.py'
PIN = 'v0.18.2'
COMMAND = 'cad-agent snapfit research/snap-fits/snaps.yaml --output research/snap-fits/snapfit.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def src_dir(path: Path) -> Path:
    path = Path(path).resolve()
    return path / 'src' if (path / 'src' / 'cadagent').is_dir() else path


def toolkit_id(path: Path):
    """(tag, commit) of a cad-agent checkout; the tag only where HEAD is exactly on one."""
    top = src_dir(path).parent

    def git(*a):
        r = subprocess.run(['git', '-C', str(top), *a], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    return git('describe', '--tags', '--exact-match', 'HEAD'), git('rev-parse', 'HEAD')


def run_toolkit(path: Path, spec: Path) -> str:
    """The toolkit's CLI on the spec, as its docs give it; returns the --output JSON's text. Run from the repository
    root with the spec's relative path, so the output names no local path."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'snapfit.json'
        env = dict(os.environ, PYTHONPATH=str(src_dir(path)))
        code = ('import sys; from cadagent.cli import main; '
                f'sys.exit(main(["snapfit", {rel(spec)!r}, "--output", {str(out)!r}]))')
        r = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode not in (0, 1) or not out.exists():
            raise SystemExit(f'cad-agent snapfit failed ({r.returncode}): {r.stderr.strip() or r.stdout.strip()}')
        return out.read_text()


# ---------------------------------------------------------------------------------------------------- hand checks

def wedge(mu: float, deg: float) -> float:
    """The guide's W / P = (mu + tan a) / (1 - mu tan a) (Fig. 17/18)."""
    t = math.tan(math.radians(deg))
    return (mu + t) / (1 - mu * t)


def curved(lat: dict) -> dict:
    """The hopper's tongues are arcs (radius r_mid, angle phi = L / r_mid), not the toolkit's straight beam. For a
    radial load at the tip of a circular cantilever, Castigliano gives the tip's deflection along the load
    F R^3 / EI (phi / 2 - sin 2 phi / 4) against F L^3 / 3 EI straight, and the root moment F R sin phi against F L.
    So at the same undercut the force is k_force times the straight beam's and the root strain k_strain times."""
    if not lat.get('curved'):
        return {'k_force': 1.0, 'k_strain': 1.0, 'basis': 'straight tongue: the toolkit\'s beam'}
    r = ts.HOPPER_WALL_R + ts.TONGUE_N + lat['h'] / 2
    phi = lat['L'] / r
    k_force = (phi ** 3 / 3) / (phi / 2 - math.sin(2 * phi) / 4)
    k_strain = k_force * math.sin(phi) / phi
    return {'k_force': k_force, 'k_strain': k_strain, 'r_mid_mm': r, 'phi_deg': math.degrees(phi),
            'basis': 'Castigliano, circular cantilever with a radial tip load (r_mid = the hopper wall + '
                     'TONGUE_N + h / 2)'}


# The tongue twisted by its barb: the barb bears at s = contact_s, off the tongue's centre line (its width runs
# s_lo..s_hi), so the load twists the tongue as it bends it. The extra deflection at the barb over the bending's is
# 3 E I e^2 / (G J L^2) = (1 + nu) / (2 beta) (e / L)^2, with I = b h^3 / 12, J = beta b h^3 (Roark, a thin rectangle in
# torsion) and E / G = 2 (1 + nu): the barb then needs less force to pass the undercut, so the retention is divided by
# (1 + that). PETG's Poisson ratio is not on its data sheet; 0.40, the top of the 0.35-0.40 usual for amorphous
# polyesters, twists the most (an estimate: the coupon measures the retention itself).
POISSON = 0.40
# Roark, a rectangle a x c (a >= c) in torsion: tau_max = T / (alpha a c^2); alpha by a / c (Table 10.7, case 4)
ROARK_ALPHA = ((1.0, 0.208), (1.5, 0.231), (2.0, 0.246), (2.5, 0.258), (3.0, 0.267), (4.0, 0.282), (5.0, 0.291),
               (10.0, 0.312), (1e9, 0.333))


def roark_alpha(a: float, c: float) -> float:
    r = max(a, c) / min(a, c)
    for (r0, a0), (r1, a1) in zip(ROARK_ALPHA, ROARK_ALPHA[1:]):
        if r <= r1:
            return a0 + (a1 - a0) * (r - r0) / (r1 - r0)
    return ROARK_ALPHA[-1][1]


def torsion_tau(T: float, a: float, c: float) -> float:
    """The largest shear stress in a rectangle a x c twisted by T (Roark)."""
    return T / (roark_alpha(a, c) * max(a, c) * min(a, c) ** 2)


def twist(lat: dict) -> dict:
    """The barb's offset from the tongue's centre line (along s) and what it costs the retention (above)."""
    s0, s1 = ts.tongue_s(lat)
    b, h, L = s1 - s0, lat['h'], lat['L']
    e = abs(ts.profile()['contact_s'] - (s0 + s1) / 2)
    beta = 1 / 3 - 0.21 * h / b * (1 - h ** 4 / (12 * b ** 4))
    extra = (1 + POISSON) / (2 * beta) * (e / L) ** 2
    return {'offset_mm': e, 'beta': beta, 'extra_deflection': extra, 'k_retention': 1 / (1 + extra),
            'basis': 'Roark: a thin rectangle in torsion, J = beta b h^3; Poisson ratio 0.40 (estimate, the most twist)'}


def anchor(lat: dict, p: float, pull: float) -> dict:
    """The root block where it leaves the plate (a layer plane: s 0 on both lids), loaded by the latch at its most
    (p: the tongue's in-plane tip force at the highest modulus; pull: the pull at the barb at the high bound).
    The tongue's in-plane moment p L twists the block's section about s, across the layers: Roark's rectangle,
    plus p as a direct shear. The pull's moment pull L bends the section about n, the block's layers peeled
    apart (6 M / (c a^2)), plus the pull as a direct tension. The whole moment is taken on that one plane: the
    block's layers from s 0 to the tongue's end hand it over through it. For the sizes until the review of PR #181
    this gives 9.2 MPa of twist on the hopper's block, against the review's FE: p90 8.7 MPa of interlaminar shear
    there, so the hand model reads a little high, as a check should. Also the tongue's own twist at its root, about its axis there: p at the barb's offset along s
    from the tongue's centre line (contact_s - the centre: positive past it) and the pull at its lever across: the
    barb's contact (n midway up the ridge) inside the tongue's centre line, and on an arc the tip's r (1 - cos phi)
    inside the root's tangent. With the offset positive the two turn the same way."""
    a, c = ts.root_section(lat)
    tau_block = torsion_tau(p * lat['L'], a, c) + p / (a * c)
    peel = 6 * pull * lat['L'] / (c * a * a) + pull / (a * c)
    s0, s1 = ts.tongue_s(lat)
    e = ts.profile()['contact_s'] - (s0 + s1) / 2
    lever = ts.TONGUE_N + lat['h'] / 2 - (ts.WALL_CLEAR + ts.RIDGE_H) / 2
    if lat.get('curved'):
        k = curved(lat)
        lever += k['r_mid_mm'] * (1 - math.cos(math.radians(k['phi_deg'])))
    T = abs(p * e + pull * lever)
    tau_tongue = torsion_tau(T, s1 - s0, lat['h'])
    return {'section_mm': [a, c], 'twist_mpa': tau_block, 'peel_mpa': peel, 'tongue_torque_nmm': T, 'pull_lever_mm': lever,
            'tongue_twist_mpa': tau_tongue}


def combined_strain(lat: dict, strain: float, mu: float) -> dict:
    """The strain at the root's corner: the in-plane bending's (the toolkit's, beam-corrected) and the out-of-plane
    bending's from the pull at the barb, W = P (mu + tan a) / (1 - mu tan a) on the tongue's wide way:
    6 W L / (E h b^2) = k_force eps (W / P) h / b, whatever E is. The two peak on the same corner of the root."""
    k = curved(lat)
    b = ts.tongue_width(lat)
    f = max(wedge(mu, ts.RETURN_DEG), wedge(mu, ts.LEAD_DEG))
    inp = strain * k['k_strain']
    out = strain * k['k_force'] * f * lat['h'] / b
    return {'friction': mu, 'in_plane': inp, 'out_of_plane': out, 'total': inp + out}


# The material's numbers as the toolkit reports them for 'petg-bambu-basic' along the layers, repeated (snapfit.json;
# research/snap-fits/test_snaps.py checks they match): for the hand-only numbers of sizes the toolkit was not run on
HAND_MATERIAL = {'secant_mpa': 2780.0, 'retention_secant_mpa': 1460.0, 'allowable': 0.6 * 0.7 * 51 / 2780}


def hand_latch(lat: dict) -> dict:
    """A latch's numbers by hand alone (the guide's closed form, HAND_MATERIAL), for any sizes: the controls' old
    sizing and the cross-check of lid_summary's numbers for the current one."""
    m = HAND_MATERIAL
    eps = ts.UNDERCUT * lat['h'] / (0.67 * lat['L'] ** 2)
    b = ts.tongue_width(lat)
    k = curved(lat)
    P = lambda E: b * lat['h'] ** 2 / 6 * E * eps / lat['L'] * k['k_force']
    p_hi = P(m['secant_mpa'])
    pull = p_hi * wedge(ts.FRICTION['high'], ts.RETURN_DEG)
    return {'strain': eps, 'retention_low_n': P(m['retention_secant_mpa']) * wedge(ts.FRICTION['low'], ts.RETURN_DEG)
            * twist(lat)['k_retention'], 'pull_off_high_n': pull,
            'push_on_high_n': p_hi * wedge(ts.FRICTION['high'], ts.LEAD_DEG),
            'combined_low': combined_strain(lat, eps, ts.FRICTION['low'])['total'],
            'combined_high': combined_strain(lat, eps, ts.FRICTION['high'])['total'],
            'allowable': m['allowable'], **{k_: v for k_, v in anchor(lat, p_hi, pull).items() if k_ != 'section_mm'}}


# The shallowest undercut a coupon may prescribe: the force goes as u h^3, so the print's +-0.1 mm moves it by
# +-0.1 / u; at 0.6 mm that is +-17 % (0.3 mm would be +-33 %). Under it the return angle is the knob.
UNDERCUT_MIN = 0.6


def coupon(part: str, lat: dict, load: dict, per: dict, comb_hi: float, allow: float) -> dict:
    """The coupon's protocol for one latch: what to measure, the band it must fall in, and the knob. A coupon pull
    measures the latch's retention at the real friction and modulus, so its pull-off must be at least its share of
    the required retention and at most its share of the hand limit; the push-on at most its share of the hand limit.
    The force goes as u h^3: the undercut is the knob (0.1 mm steps, the force with it, the strain too, up to where
    the combined strain at the high bound meets the allowable). The return angle is the second knob, for a band too
    narrow for a step of the undercut: steeper holds more for the same deflection."""
    n, u, h = lat['n'], ts.UNDERCUT, lat['h']
    lo, hi = load['required_n'] / n, ts.HAND_N / n
    tol = 0.1
    spread = [(u - tol) * (h - tol) ** 3 / (u * h ** 3), (u + tol) * (h + tol) ** 3 / (u * h ** 3)]
    return {'per_latch': True,
            'pull_off_band_n': [lo, hi], 'push_on_max_n': hi,
            'predicted_n': {'retention_low': per['retention_low_n'], 'pull_off_high': per['pull_off_high_n'],
                            'push_on_high': per['push_on_high_n']},
            'margins': {'retention': per['retention_low_n'] / lo - 1, 'pull_off': 1 - per['pull_off_high_n'] / hi,
                        'push_on': 1 - per['push_on_high_n'] / hi},
            'print_tolerance': {'mm': tol, 'force_factor': spread,
                                'basis': 'force as u h^3: the undercut and the thickness each 0.1 mm off'},
            'cycles': 2 * lat['cycles'],
            'inspect': 'after the cycles: no whitening at the root\'s corner, no split between layers at the root '
                       'block\'s foot or under the barb, the pull-off still in the band',
            'undercut': {'now_mm': u, 'step_mm': 0.1, 'min_mm': UNDERCUT_MIN, 'max_by_strain_mm': u * allow / comb_hi},
            'return_deg': {'now': ts.RETURN_DEG,
                           'use': 'when no step of the undercut lands both forces in their bands: steeper holds more '
                                  'for the same push'}}


def coupon_verdict(cp: dict, pull_n: float, push_n: float) -> dict:
    """A measured coupon (one latch's pull-off and push-on, N) read against its band (coupon()): pass, or the
    undercut to print next, or 'return angle' when no 0.1 mm step of the undercut from min_mm up lands both (a
    shallower undercut would leave the force to the print's tolerance), or 'redesign' when the undercut it needs
    passes the strain's limit."""
    lo, hi = cp['pull_off_band_n']
    pmax = cp['push_on_max_n']
    u, step, umax = cp['undercut']['now_mm'], cp['undercut']['step_mm'], cp['undercut']['max_by_strain_mm']
    umin = cp['undercut']['min_mm']
    if lo <= pull_n <= hi and push_n <= pmax:
        return {'pass': True, 'action': 'pass', 'undercut_mm': u}
    # the forces go with the undercut: the steps that land the pull in [lo, hi] and the push under pmax, the nearest
    # to the undercut now, 10 % inside both edges where a step lands there
    k_lo, k_hi = lo / pull_n, min(hi / pull_n, pmax / push_n)
    steps = [x for x in (round(u + i * step, 3) for i in range(-int(round(u / step)) + 1, 40)) if x >= umin - 1e-9]
    ok = [x for x in steps if k_lo <= x / u <= k_hi]
    if not ok:
        return {'pass': False, 'action': 'return angle', 'undercut_mm': None}
    fit = [x for x in ok if x <= umax]
    if not fit:
        return {'pass': False, 'action': 'redesign', 'undercut_mm': min(ok)}
    inner = [x for x in fit if 1.1 * k_lo <= x / u <= 0.9 * k_hi] or fit
    return {'pass': False, 'action': 'undercut', 'undercut_mm': min(inner, key=lambda x: abs(x - u))}


def load_cases(part: str, n: int, retention: float, pull: float) -> list:
    """Every case of ts.load_cases() against the lid's retention (n x per latch): held or not, and for a case it
    does not hold, the pull-off at the high bound a set of these latches strong enough for it would need (the
    pull-off goes with the retention: the same latch, the high bounds over the low)."""
    out = []
    for c in ts.load_cases(part):
        c = dict(c)
        c['retained_n'] = n * retention
        c['held'] = n * retention >= c['required_n']
        c['pull_off_needed_n'] = c['required_n'] * pull / retention
        out.append(c)
    return out


def row(check, value, limit, ok, detail):
    return {'check': check, 'value': value, 'limit': limit, 'pass': bool(ok), 'detail': detail}


def lid_summary(part: str, result: dict) -> dict:
    lat = ts.LATCHES[part]
    n = lat['n']
    load = ts.LOADS[part]()
    rows = {s['name']: s for s in result['snaps']}
    lo, hi = rows[ts.snap_name(part, 'low')], rows[ts.snap_name(part, 'high')]
    k = curved(lat)
    tw = twist(lat)
    P = ts.profile()
    b = ts.tongue_width(lat)
    allow = hi['material']['allowable']
    strain = hi['strain'] * k['k_strain']
    # the lowest modulus, the low friction, less the barb's twist
    retention = lo['separation_force_n'] * k['k_force'] * tw['k_retention']
    p_hi = hi['deflection_force_n'] * k['k_force']                         # the highest modulus
    pull = p_hi * wedge(ts.FRICTION['high'], ts.RETURN_DEG)
    push = hi['mating_force_n'] * k['k_force']
    # shear across the layers where the barb meets its tongue and the ridge its wall (each a plane along s; every part
    # prints with s along its z), from the most a latch is pulled with
    ridge_len = lat['barb_w'] + 2 * lat['ridge_extra']
    a_barb = lat['barb_w'] * (P['barb'][-1][0] - P['barb'][0][0])
    a_ridge = ridge_len * (P['ridge_s'][1] - P['ridge_s'][0])
    tau = pull / min(a_barb, a_ridge)
    # the tongue bent out of its plane by the pull at the barb (its stiff way: b along s), along the layers
    sigma = 6 * pull * lat['L'] / (lat['h'] * b ** 2)
    comb = {mu: combined_strain(lat, hi['strain'], ts.FRICTION[mu]) for mu in ('low', 'high')}
    anc = anchor(lat, p_hi, pull)
    cases = load_cases(part, n, retention, pull)
    release_lift = ts.PLAY + ts.UNDERCUT / math.tan(math.radians(ts.RETURN_DEG))
    backed_to = ts.BACKING_DEPTH - release_lift
    contact_s = P['ridge'][2][0]                                           # the ridge's top back corner
    checks = [
        row('toolkit rows', [lo['pass'], hi['pass']], True, lo['pass'] and hi['pass'],
            'every cad-agent row of both declarations passes (root strain, root radius, retention at the low '
            'bound, mating at the high bound)'),
        row('root strain, beam-corrected', strain, allow, strain <= allow,
            f'{strain * 100:.3f} % (the toolkit\'s {hi["strain"] * 100:.3f} % x {k["k_strain"]:.4f}) vs {allow * 100:.3f} %'),
        row('root strain, in-plane + out-of-plane at the corner, high bound', comb['high']['total'], allow,
            comb['high']['total'] <= allow,
            f'{comb["high"]["in_plane"] * 100:.3f} % + {comb["high"]["out_of_plane"] * 100:.3f} % (the pull at friction '
            f'{ts.FRICTION["high"]} bending the {b:.2f} mm wide tongue out of its plane) = '
            f'{comb["high"]["total"] * 100:.3f} % vs {allow * 100:.3f} %; at {ts.FRICTION["low"]}: '
            f'{comb["low"]["total"] * 100:.3f} %'),
        row('retention, all latches, low bound', n * retention, load['required_n'], n * retention >= load['required_n'],
            f'{n} x {retention:.2f} N (friction {ts.FRICTION["low"]}, the lowest data-sheet modulus, x '
            f'{tw["k_retention"]:.3f} for the barb {tw["offset_mm"]:.2f} mm off the tongue\'s centre line) vs '
            f'{load["required_n"]:.2f} N = {load["sf"]} x {load["force_n"]:.2f} N'),
        row('load cases: every included case held', [c['case'] for c in cases if c['status'] != 'excluded'], True,
            all(c['held'] for c in cases if c['status'] != 'excluded'),
            '; '.join(f'{c["case"]}: {c["required_n"]:.2f} N' for c in cases if c['status'] != 'excluded')
            + f' vs {n * retention:.2f} N held'),
        row('pull-off, all latches, high bound', n * pull, ts.HAND_N, n * pull <= ts.HAND_N,
            f'{n} x {pull:.2f} N (friction {ts.FRICTION["high"]}, the highest data-sheet modulus, return '
            f'{ts.RETURN_DEG:g} deg) vs {ts.HAND_N:g} N by hand'),
        row('push-on, all latches, high bound', n * push, ts.HAND_N, n * push <= ts.HAND_N,
            f'{n} x {push:.2f} N (lead {ts.LEAD_DEG:g} deg) vs {ts.HAND_N:g} N by hand'),
        row('barb and ridge, shear across the layers', tau, ts.PETG_SHEAR_MPA / 2, tau <= ts.PETG_SHEAR_MPA / 2,
            f'{pull:.2f} N on {min(a_barb, a_ridge):.1f} mm2: {tau:.2f} MPa vs {ts.PETG_SHEAR_MPA:g} / 2 (SF 2)'),
        row('root block, twisted across the layers', anc['twist_mpa'], ts.PETG_SHEAR_MPA / 2,
            anc['twist_mpa'] <= ts.PETG_SHEAR_MPA / 2,
            f'{p_hi:.2f} N x {lat["L"]:g} mm on its {anc["section_mm"][0]:g} x {anc["section_mm"][1]:.2f} section at the '
            f'plate (Roark) + the shear: {anc["twist_mpa"]:.2f} MPa vs {ts.PETG_SHEAR_MPA:g} / 2 (SF 2)'),
        row('root block, peeled across the layers', anc['peel_mpa'], ts.PETG_ACROSS_MPA / 2,
            anc['peel_mpa'] <= ts.PETG_ACROSS_MPA / 2,
            f'{pull:.2f} N x {lat["L"]:g} mm bending the section open + the pull: {anc["peel_mpa"]:.2f} MPa vs '
            f'{ts.PETG_ACROSS_MPA:g} / 2 (SF 2)'),
        row('tongue twisted at its root, across the layers', anc['tongue_twist_mpa'], ts.PETG_SHEAR_MPA / 2,
            anc['tongue_twist_mpa'] <= ts.PETG_SHEAR_MPA / 2,
            f'{anc["tongue_torque_nmm"]:.1f} N mm on the {b:.2f} x {lat["h"]:g} tongue: {anc["tongue_twist_mpa"]:.2f} MPa '
            f'vs {ts.PETG_SHEAR_MPA:g} / 2 (SF 2)'),
        row('tongue bent out of its plane', sigma, ts.PETG_ALONG_MPA / 2, sigma <= ts.PETG_ALONG_MPA / 2,
            f'6 x {pull:.2f} N x {lat["L"]:g} / ({lat["h"]:g} x {b:.2f}^2) = {sigma:.2f} MPa along the layers vs '
            f'{ts.PETG_ALONG_MPA:g} / 2 (SF 2)'),
        row('wall backed to the release', backed_to, contact_s, backed_to >= contact_s,
            f'the backing ({ts.BACKING_DEPTH:g} deep) still reaches s {backed_to:.3f} when the barb tops the ridge '
            f'(lift {release_lift:.3f}); the contact is at s {contact_s:.3f}'),
    ]
    return {'catch': lat['catch'], 'latches': n, 'print': ts.PRINT[part], 'catch_print': ts.PRINT[lat['catch']],
            'cycles': lat['cycles'], 'cycles_basis': lat['cycles_basis'],
            'arm': {'length_mm': lat['L'], 'thickness_mm': lat['h'], 'width_mm': b, 'tongue_s_mm': list(ts.tongue_s(lat)),
                    'undercut_mm': ts.UNDERCUT, 'root_radius_mm': lat['root_r'], 'lead_deg': ts.LEAD_DEG,
                    'return_deg': ts.RETURN_DEG, 'barb_mm': lat['barb_w'], 'root_block_mm': anc['section_mm'],
                    'curved': bool(lat.get('curved'))},
            'load': load, 'load_cases': cases, 'curved_beam': k, 'twist': tw,
            'per_latch': {'root_strain': strain, 'allowable': allow, 'combined_strain_low': comb['low']['total'],
                          'combined_strain_high': comb['high']['total'], 'retention_low_n': retention,
                          'pull_off_high_n': pull, 'push_on_high_n': push, 'shear_mpa': tau, 'bending_mpa': sigma,
                          'block_twist_mpa': anc['twist_mpa'], 'block_peel_mpa': anc['peel_mpa'],
                          'tongue_twist_mpa': anc['tongue_twist_mpa']},
            'coupon': coupon(part, lat, load, {'retention_low_n': retention, 'pull_off_high_n': pull,
                                               'push_on_high_n': push}, comb['high']['total'], allow),
            'checks': checks, 'pass': all(c['pass'] for c in checks)}


def document(result_text: str, tag, commit) -> dict:
    result = json.loads(result_text)
    lids = {part: lid_summary(part, result) for part in ts.LATCHES}
    return {'issue': 131, 'generator': rel(Path(__file__)), 'generator_sha256': sha256(Path(__file__)),
            'constants': rel(CONSTANTS), 'constants_sha256': sha256(CONSTANTS),
            'spec': {'file': rel(SPEC), 'sha256': hashlib.sha256(ts.yaml_text().encode()).hexdigest()},
            'result': {'file': rel(RESULT), 'sha256': hashlib.sha256(result_text.encode()).hexdigest()},
            'toolkit': {'name': 'cad-agent', 'tag': tag, 'commit': commit, 'command': COMMAND},
            'material': {'declared': ts.MATERIAL, 'orientation': ts.ORIENTATION, 'repeated': True,
                         'why': ts.__doc__.split('Material: ')[1].strip().replace('\n', ' ')},
            'friction': ts.FRICTION, 'hand_limit_n': ts.HAND_N, 'sf_retention': ts.SF_RETENTION,
            'profile': ts.profile(), 'lids': lids, 'pass': result['pass'] and all(v['pass'] for v in lids.values())}


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, sort_keys=False) + '\n'


def stale(spec=SPEC, result=RESULT, summary=SUMMARY, generator=Path(__file__), constants=CONSTANTS):
    """What makes the committed files stale, without the toolkit: a list of reasons (empty when current)."""
    why = []
    if not spec.exists() or spec.read_text() != ts.yaml_text():
        why.append('snaps.yaml does not match cad/turret_snaps.py')
    if not result.exists() or not summary.exists():
        return why + ['snapfit.json or summary.json is missing']
    doc = json.loads(summary.read_text())
    if doc['spec']['sha256'] != sha256(spec):
        why.append('snaps.yaml changed since snapfit.json was generated')
    if doc['result']['sha256'] != sha256(result):
        why.append('snapfit.json changed since summary.json was generated')
    if doc['generator_sha256'] != sha256(generator):
        why.append('snaps.py changed since summary.json was generated')
    if doc['constants_sha256'] != sha256(constants):
        why.append('cad/turret_snaps.py changed since summary.json was generated')
    if not why and summary.read_text() != dumps(document(result.read_text(), doc['toolkit']['tag'], doc['toolkit']['commit'])):
        why.append('summary.json does not follow from snapfit.json')
    return why


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 if the committed files are stale')
    ap.add_argument('--cad-agent', type=Path, help=f'a cad-agent checkout (or its src) at {PIN}')
    a = ap.parse_args(argv)
    if a.check:
        why = stale()
        if not why and a.cad_agent:
            if run_toolkit(a.cad_agent, SPEC) != RESULT.read_text():
                why.append(f'snapfit.json differs from a fresh run on {toolkit_id(a.cad_agent)[0]}')
        if why:
            print('stale: ' + '; '.join(why) + ' (run python3 research/snap-fits/snaps.py --cad-agent PATH)')
            return 1
        print('turret lid snaps: current')
        return 0
    if not a.cad_agent:
        ap.error(f'--cad-agent PATH is needed to generate (a cad-agent checkout at {PIN})')
    tag, commit = toolkit_id(a.cad_agent)
    if tag != PIN:
        ap.error(f'the cad-agent checkout is at {tag or commit}, not the pinned {PIN}: check it out, or move PIN')
    SPEC.write_text(ts.yaml_text())
    text = run_toolkit(a.cad_agent, SPEC)
    RESULT.write_text(text)
    doc = document(text, tag, commit)
    SUMMARY.write_text(dumps(doc))
    for part, lid in doc['lids'].items():
        p = lid['per_latch']
        print(f"{part}: {lid['latches']} latches, strain {p['root_strain'] * 100:.2f} % (with the out-of-plane "
              f"{p['combined_strain_high'] * 100:.2f} %) of {p['allowable'] * 100:.2f} %, "
              f"retention {lid['latches'] * p['retention_low_n']:.1f} N >= {lid['load']['required_n']:.1f}, pull-off "
              f"{lid['latches'] * p['pull_off_high_n']:.1f} N and push-on {lid['latches'] * p['push_on_high_n']:.1f} N "
              f"<= {ts.HAND_N:g}: {'PASS' if lid['pass'] else 'FAIL'}")
    print(f"wrote {rel(SPEC)}, {rel(RESULT)}, {rel(SUMMARY)}: {'PASS' if doc['pass'] else 'FAIL'}")
    return 0 if doc['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
