#!/usr/bin/env python3
"""Re-solve the turret FEA studies of the named parts and merge them into exports/turret/fea/summary.json.

    python tools/turret-fea-refresh.py tilt_yoke [pan_ring ...] [--mesh 2.5] [--no-anim]

cad/turret_studies.py re-solves every part (28 studies, hours on the compute hosts) and writes summary.json only on a
full run; `--only` exports a part's study files but leaves the summary as it was. When one part's geometry changes,
this runs `turret_studies.run(only=parts)` and replaces just those parts' results in the committed summary, then
rebuilds the verdict and the table the same way run() does (merge() mirrors it; tools/test-turret-fea-refresh.py checks
the two agree). The other parts keep their recorded results, and the masses those were solved with stay in `masses`;
the refreshed parts' masses go in `refreshed`, with the parts and the reason.
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


def merge(old, new, parts, why):
    """old's results with the named parts' replaced by new's, in old's order (a part new to the summary goes last)."""
    parts = list(parts)
    fresh = [r for r in new['results'] if r['part'] in parts]
    if {r['part'] for r in fresh} != set(parts):
        raise ValueError(f'no new results for {sorted(set(parts) - {r["part"] for r in fresh})}')
    out, placed = [], False
    for r in old['results']:
        if r['part'] in parts:
            if not placed:
                out.extend(fresh)
                placed = True
            continue
        out.append(r)
    if not placed:
        out.extend(fresh)
    if new['mesh_mm'] != old['mesh_mm']:
        raise ValueError(f'mesh {new["mesh_mm"]} mm differs from the record\'s {old["mesh_mm"]} mm')
    merged = dict(old)
    merged['results'] = out
    merged['verdict'] = verdict(out)
    merged['table'] = table(out)
    merged['refreshed'] = {'parts': parts, 'why': why, 'masses': new['masses']}
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parts', nargs='+')
    ap.add_argument('--why', required=True, help='why these parts were re-solved (kept in the summary)')
    ap.add_argument('--mesh', type=float, default=2.5)
    ap.add_argument('--no-anim', action='store_true')
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / 'cad'))
    import numpy as np
    import turret_studies as ts
    old = json.loads(SUMMARY.read_text())
    new = ts.run(a.mesh, anim=not a.no_anim, only=a.parts)
    merged = merge(old, new, a.parts, a.why)
    SUMMARY.write_text(json.dumps(merged, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)) + '\n')
    for r in merged['results']:
        if r['part'] in a.parts:
            print(f"{r['part']:14s} {r['case']:14s} verdict SF {r['verdict_sf']} (>= {r['target']}) {'ok' if r['ok'] else 'BELOW'}")
    print('verdict:', json.dumps(merged['verdict']))


if __name__ == '__main__':
    main()
