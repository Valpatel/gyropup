#!/usr/bin/env python3
"""Re-solve the turret FEA studies of the named parts and merge them into exports/turret/fea/summary.json.

    python tools/turret-fea-refresh.py tilt_yoke [pan_ring ...] [--mesh 2.5] [--no-anim]

cad/turret_studies.py re-solves every part (28 studies, hours on the compute hosts) and writes summary.json only on a
full run; `--only` exports a part's study files but leaves the summary as it was. When one part's geometry changes,
this runs `turret_studies.run(only=parts)` and replaces just those parts' results in the committed summary, then
rebuilds the verdict and the table the same way run() does (verdict() and table() mirror it; the test evaluates
run()'s own expressions from cad/turret_studies.py's source and checks the two agree). The other parts keep their
recorded results, and the masses those were solved with stay in `masses`. Each refresh appends to `refreshed`: the
parts, the reason, the masses it solved with, the commit, the SHA-256 of cad/turret.py and the cad-agent actually
imported (its version and tree).
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / 'exports/turret/fea/summary.json'
VERDICT_ON = ('the layer-aware SF for printed parts (N2), the yield SF for the aluminium parts; the isotropic columns '
              'are reported with each result')


def verdict(results):
    """turret_studies.run()'s verdict on a list of results."""
    return {'on': VERDICT_ON,
            'min_sf_everyday': min((r['verdict_sf'] for r in results if r['case'].startswith('E')), default=None),
            'min_sf_rare': min((r['verdict_sf'] for r in results if r['case'].startswith('R')), default=None),
            'all_ok': all(r['ok'] for r in results),
            'weakest': (lambda w: f"{w['part']} {w['case']}")(min(results, key=lambda r: r['verdict_sf'] / r['target'])) if results else None,
            'below_target': [f"{r['part']} {r['case']}: {r['verdict_sf']} < {r['target']}" for r in results if not r['ok']]}


def table(results):
    """turret_studies.run()'s table on a list of results."""
    return [{'part': r['part'], 'case': r['case'], 'target': r['target'], 'sf_as_v0': r['safety_factor'],
             'sf_isotropic_weak': r['sf_isotropic_weak'], 'sf_layer_aware': r['sf_layer_aware'],
             'governs': (r['layer_aware'] or {}).get('governs'), 'verdict_sf': r['verdict_sf'], 'ok': r['ok']} for r in results]


def merge(old, new, parts, why, provenance=None):
    """old's results with the named parts' replaced by new's. Each new (part, case) takes the place of the old one; a
    case new to a part goes after that part's last result, and a part new to the summary goes last. An old case the
    re-solve no longer makes is dropped."""
    parts = list(parts)
    fresh = [r for r in new['results'] if r['part'] in parts]
    if {r['part'] for r in fresh} != set(parts):
        raise ValueError(f'no new results for {sorted(set(parts) - {r["part"] for r in fresh})}')
    by_key = {(r['part'], r['case']): r for r in fresh}
    out, used = [], set()
    for r in old['results']:
        k = (r['part'], r['case'])
        if r['part'] not in parts:
            out.append(r)
        elif k in by_key:
            out.append(by_key[k])
            used.add(k)
    for r in fresh:                         # cases or parts the record did not have
        k = (r['part'], r['case'])
        if k in used:
            continue
        last = max((i for i, o in enumerate(out) if o['part'] == r['part']), default=len(out) - 1)
        out.insert(last + 1, r)
        used.add(k)
    if new['mesh_mm'] != old['mesh_mm']:
        raise ValueError(f'mesh {new["mesh_mm"]} mm differs from the record\'s {old["mesh_mm"]} mm')
    merged = dict(old)
    merged['results'] = out
    merged['verdict'] = verdict(out)
    merged['table'] = table(out)
    prior = old.get('refreshed', [])
    prior = [prior] if isinstance(prior, dict) else list(prior)
    merged['refreshed'] = prior + [dict({'parts': parts, 'why': why, 'masses': new['masses']}, **(provenance or {}))]
    return merged


def provenance(cadagent_module):
    """What this refresh runs on: the commit, cad/turret.py's SHA-256, and the cad-agent that is actually imported
    (its checkout's git commit, else the SHA-256 of its source files) with its version from that tree's pyproject,
    not the venv's metadata, which can name another install. Taken before the solve, so a failure costs nothing."""
    import hashlib
    import re
    import subprocess
    src = Path(cadagent_module.__file__).resolve().parent
    try:
        toolkit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=src, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        h = hashlib.sha256()
        for f in sorted(src.rglob('*.py')):
            h.update(f.relative_to(src).as_posix().encode() + b'\0' + f.read_bytes())
        toolkit = 'sha256:' + h.hexdigest()
    pyproject = src.parent.parent / 'pyproject.toml'
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.M) if pyproject.exists() else None
    return {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'turret_py_sha256': hashlib.sha256((ROOT / 'cad/turret.py').read_bytes()).hexdigest(),
            'cad_agent': m.group(1) if m else None, 'cad_agent_tree': toolkit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parts', nargs='+')
    ap.add_argument('--why', required=True, help='why these parts were re-solved (kept in the summary)')
    ap.add_argument('--mesh', type=float, default=2.5)
    ap.add_argument('--no-anim', action='store_true')
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / 'cad'))
    import numpy as np
    import cadagent
    import turret_studies as ts
    old = json.loads(SUMMARY.read_text())
    prov = provenance(cadagent)
    new = ts.run(a.mesh, anim=not a.no_anim, only=a.parts)
    merged = merge(old, new, a.parts, a.why, prov)
    SUMMARY.write_text(json.dumps(merged, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)) + '\n')
    for r in merged['results']:
        if r['part'] in a.parts:
            print(f"{r['part']:14s} {r['case']:14s} verdict SF {r['verdict_sf']} (>= {r['target']}) {'ok' if r['ok'] else 'BELOW'}")
    print('verdict:', json.dumps(merged['verdict']))


if __name__ == '__main__':
    main()
