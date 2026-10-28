"""Mesh convergence of one body strength case (cad/body_studies.py): the case at several global mesh sizes, each in its
own folder, and how its peak stress and hot spot move as the mesh refines.

    python tools/fea_convergence.py D2 --meshes 4 3 2.5 2      # -> exports/body/fea/D2-convergence.json

A real stress converges (the peak settles as the elements shrink); a singularity (a re-entrant corner of bonded solids,
a point load, a rigid clamp's edge) keeps rising at the same place. The runs write to build/fea-convergence/<case>/m<mesh>/
(GYROPUP_BODY_FEA_OUT), so exports/body/fea/ is untouched but for the summary written here.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case', help='the case prefix cad/body_studies.py --only takes (e.g. D2)')
    ap.add_argument('--meshes', nargs='+', type=float, default=[4.0, 3.0, 2.5, 2.0])
    a = ap.parse_args()
    rows = []
    for m in a.meshes:
        out = R / 'build' / 'fea-convergence' / a.case / f'm{m:g}'
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        subprocess.run([sys.executable, str(R / 'cad' / 'body_studies.py'), '--mesh', str(m), '--only', a.case, '--no-anim'],
                       cwd=R, env=dict(os.environ, GYROPUP_BODY_FEA_OUT=str(out)), check=True)
        res = json.loads((out / 'summary.json').read_text())['results']
        for name, r in res.items():
            if not name.startswith(a.case):
                continue
            hot = r.get('hot_spots') or []
            rows.append({'case': name, 'mesh_mm': m, 'wall_s': round(time.time() - t0),
                         **{k: r.get(k) for k in ('safety_factor', 'sf_by_part', 'deck_peak_mpa', 'deck_sf', 'plate_peak_mpa',
                                                  'plate_sf', 'post_corner_peak_mpa', 'max_von_mises_mpa', 'von_mises_design_mpa',
                                                  'max_displacement_mm', 'pass', 'n_nodes', 'n_elements')},
                         'hot_spots': hot[:5]})
            print(f"mesh {m:g}: {name} SF {r.get('sf_by_part') or r.get('safety_factor')} deck {r.get('deck_peak_mpa')} MPa "
                  f"plate {r.get('plate_peak_mpa')} MPa  hot {hot[:2]}  ({rows[-1]['wall_s']} s)", flush=True)
    f = R / 'exports' / 'body' / 'fea' / f'{a.case}-convergence.json'
    f.write_text(json.dumps({'case': a.case, 'meshes': a.meshes, 'rows': rows,
                             'how': 'cad/body_studies.py --only <case> --no-anim at each global mesh size (tools/fea_convergence.py)'},
                            indent=1) + '\n')
    print(f'-> {f.relative_to(R)}')


if __name__ == '__main__':
    main()
