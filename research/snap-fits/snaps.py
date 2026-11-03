#!/usr/bin/env python3
"""The turret lids' snap fits (#131 wave 1) through cad-agent's snap-fit calculator, at a pinned release.

cad/turret_snaps.py holds every snap dimension cad/turret.py builds the latches from. This writes its declaration to
snaps.yaml, runs the toolkit's own command on it,

    cad-agent snapfit research/snap-fits/snaps.yaml --output research/snap-fits/snapfit.json

and writes summary.json: the load each lid holds and its source, the toolkit's rows per latch, and the checks the
toolkit does not make, by hand from its numbers: the pull-off at the high bound against the hand limit, the totals
over each lid's latches, the hopper's curved tongues against the straight beam the toolkit assumes, the barb and
the ridge in shear across the layers, the tongue bent out of its plane, and the backing behind the thin walls.

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


def row(check, value, limit, ok, detail):
    return {'check': check, 'value': value, 'limit': limit, 'pass': bool(ok), 'detail': detail}


def lid_summary(part: str, result: dict) -> dict:
    lat = ts.LATCHES[part]
    n = lat['n']
    load = ts.LOADS[part]()
    rows = {s['name']: s for s in result['snaps']}
    lo, hi = rows[ts.snap_name(part, 'low')], rows[ts.snap_name(part, 'high')]
    k = curved(lat)
    P = ts.profile()
    b = ts.tongue_width()
    allow = hi['material']['allowable']
    strain = hi['strain'] * k['k_strain']
    retention = lo['separation_force_n'] * k['k_force']                    # the lowest modulus, the low friction
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
    release_lift = ts.PLAY + ts.UNDERCUT / math.tan(math.radians(ts.RETURN_DEG))
    backed_to = ts.BACKING_DEPTH - release_lift
    contact_s = P['ridge'][2][0]                                           # the ridge's top back corner
    checks = [
        row('toolkit rows', [lo['pass'], hi['pass']], True, lo['pass'] and hi['pass'],
            'every cad-agent row of both declarations passes (root strain, root radius, retention at the low '
            'bound, mating at the high bound)'),
        row('root strain, beam-corrected', strain, allow, strain <= allow,
            f'{strain * 100:.3f} % (the toolkit\'s {hi["strain"] * 100:.3f} % x {k["k_strain"]:.4f}) vs {allow * 100:.3f} %'),
        row('retention, all latches, low bound', n * retention, load['required_n'], n * retention >= load['required_n'],
            f'{n} x {retention:.2f} N (friction {ts.FRICTION["low"]}, the lowest data-sheet modulus) vs '
            f'{load["required_n"]:.2f} N = {load["sf"]} x {load["force_n"]:.2f} N'),
        row('pull-off, all latches, high bound', n * pull, ts.HAND_N, n * pull <= ts.HAND_N,
            f'{n} x {pull:.2f} N (friction {ts.FRICTION["high"]}, the highest data-sheet modulus, return '
            f'{ts.RETURN_DEG:g} deg) vs {ts.HAND_N:g} N by hand'),
        row('push-on, all latches, high bound', n * push, ts.HAND_N, n * push <= ts.HAND_N,
            f'{n} x {push:.2f} N (lead {ts.LEAD_DEG:g} deg) vs {ts.HAND_N:g} N by hand'),
        row('barb and ridge, shear across the layers', tau, ts.PETG_SHEAR_MPA / 2, tau <= ts.PETG_SHEAR_MPA / 2,
            f'{pull:.2f} N on {min(a_barb, a_ridge):.1f} mm2: {tau:.2f} MPa vs {ts.PETG_SHEAR_MPA:g} / 2 (SF 2)'),
        row('tongue bent out of its plane', sigma, ts.PETG_ALONG_MPA / 2, sigma <= ts.PETG_ALONG_MPA / 2,
            f'6 x {pull:.2f} N x {lat["L"]:g} / ({lat["h"]:g} x {b:.2f}^2) = {sigma:.2f} MPa along the layers vs '
            f'{ts.PETG_ALONG_MPA:g} / 2 (SF 2)'),
        row('wall backed to the release', backed_to, contact_s, backed_to >= contact_s,
            f'the backing ({ts.BACKING_DEPTH:g} deep) still reaches s {backed_to:.3f} when the barb tops the ridge '
            f'(lift {release_lift:.3f}); the contact is at s {contact_s:.3f}'),
    ]
    return {'catch': lat['catch'], 'latches': n, 'print': ts.PRINT[part], 'catch_print': ts.PRINT[lat['catch']],
            'cycles': lat['cycles'], 'cycles_basis': lat['cycles_basis'],
            'arm': {'length_mm': lat['L'], 'thickness_mm': lat['h'], 'width_mm': b, 'undercut_mm': ts.UNDERCUT,
                    'root_radius_mm': lat['root_r'], 'lead_deg': ts.LEAD_DEG, 'return_deg': ts.RETURN_DEG,
                    'barb_mm': lat['barb_w'], 'curved': bool(lat.get('curved'))},
            'load': load, 'curved_beam': k,
            'per_latch': {'root_strain': strain, 'allowable': allow, 'retention_low_n': retention, 'pull_off_high_n': pull,
                          'push_on_high_n': push, 'shear_mpa': tau, 'bending_mpa': sigma},
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
        print(f"{part}: {lid['latches']} latches, strain {p['root_strain'] * 100:.2f} % of {p['allowable'] * 100:.2f} %, "
              f"retention {lid['latches'] * p['retention_low_n']:.1f} N >= {lid['load']['required_n']:.1f}, pull-off "
              f"{lid['latches'] * p['pull_off_high_n']:.1f} N and push-on {lid['latches'] * p['push_on_high_n']:.1f} N "
              f"<= {ts.HAND_N:g}: {'PASS' if lid['pass'] else 'FAIL'}")
    print(f"wrote {rel(SPEC)}, {rel(RESULT)}, {rel(SUMMARY)}: {'PASS' if doc['pass'] else 'FAIL'}")
    return 0 if doc['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
