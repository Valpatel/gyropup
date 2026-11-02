#!/usr/bin/env python3
"""Coupon C4's prediction: the load at which the knee-eye stub's root should peel, from an FEA of the coupon itself.

    python research/leg-preprint/c4_fea.py --out build/c4-fea        # on a compute host, cad-agent v0.6.0 (as the records)

The coupon is cad/rig_bench.py coupon_knee_stub_link(): the upper link's knee end, cut C4_CUT_BACK back along the arm,
with dev's stub ('today') or the drawn one ('pr2'). The study holds the cut face and puts 1 kN through the knee bore
(the sleeves' and the pin's bore, as cad/leg_studies.py loads the upper link), acting at the knee boss's mid-plane:
the same lever the knee pin gives the link in the leg. It is run in four directions in the link's plane (+-x along
the arm, +-z across it), at a 2 mm mesh and, for each stub's weakest direction, at 1.5 mm.

Linear statics, so every stress scales with the load and so does each safety factor's inverse: the load at which a
criterion reaches 1 is 1 kN x its SF at 1 kN. Two predictions per row:
  layer  cad-agent's layer_check (PA6-CF humid: S_z 18.13 MPa across the layers, S_s = S_z / sqrt 3 assumed): the
         root peels. This is the number C4 calibrates: measured / predicted is the factor on the assumed S_z and S_s
  bulk   von Mises against the in-layer allowable (pa6_cf_xy, 40.84 MPa)
Elements touching the clamp or the load are left out, as the records do. A screening model: no contact with the
sleeves, no plasticity, no print voids. Writes <out>/c4-fea.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'cad'), str(ROOT)]
NORMAL = (0.0, 1.0, 0.0)          # the link prints flat: its layers stack along y
LOAD_N = 1000.0
DIRECTIONS = {'+x': (1.0, 0.0, 0.0), '-x': (-1.0, 0.0, 0.0), '+z': (0.0, 0.0, 1.0), '-z': (0.0, 0.0, -1.0)}


def solve(shape, stub, d, mesh):
    import fivebar as fb
    import rig_bench as rb
    from cadagent.fea import MATERIALS, Study
    import leg_studies as ls
    l1 = fb.P['l1']
    cut = l1 - rb.C4_CUT_BACK
    yk = sum(fb.Y['knee_boss']) / 2
    rad = lambda f: math.hypot(f.center[0] - l1, f.center[2])
    half = lambda f: max(f.bbox[3] - f.bbox[0], f.bbox[5] - f.bbox[2]) / 2
    knee_bore = lambda f: f.kind == 'Cylinder' and rad(f) < 0.5 and half(f) < fb.EYE_SLEEVE[0] / 2 + 0.5
    clamp = lambda f: f.kind == 'Plane' and abs(f.center[0] - cut) < 0.05
    st = Study(shape, MATERIALS['pa6_cf_xy'], mesh_mm=mesh, name=f'c4_{stub} {d}')
    st.fix(clamp)
    F = tuple(LOAD_N * v for v in DIRECTIONS[d])
    ls.force_at(st, knee_bore, F, (l1, yk, 0.0))
    t0 = time.time()
    r = st.solve()
    lc = st.layer_check(NORMAL, judge=~st._touches_bc).as_dict()
    return {'stub': stub, 'direction': d, 'mesh_mm': mesh, 'load_n': LOAD_N, 'load_at_y_mm': yk,
            'gate_sf_at_1kn': r['safety_factor'], 'von_mises_design_mpa': r['von_mises_design_mpa'],
            'layer_check_at_1kn': lc, 'predicted_peel_n': round(LOAD_N * lc['safety_factor']),
            'predicted_bulk_n': round(LOAD_N * r['safety_factor']), 'tets': r['mesh']['tets'],
            'seconds': round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mesh', type=float, default=2.0)
    ap.add_argument('--fine', type=float, default=1.5)
    a = ap.parse_args()
    import gmsh  # noqa: F401  (before CadQuery, as the compute hosts' mesher wants)
    import rig_bench as rb
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for stub in ('today', 'pr2'):
        shape = rb.coupon_knee_stub_link(stub).val()
        mine = []
        for d in DIRECTIONS:
            row = solve(shape, stub, d, a.mesh)
            mine.append(row)
            print(f"  {stub:5} {d}  {a.mesh} mm: layer SF {row['layer_check_at_1kn']['safety_factor']} at 1 kN "
                  f"-> peel {row['predicted_peel_n']} N; bulk {row['predicted_bulk_n']} N ({row['tets']} tets)", flush=True)
        weak = min(mine, key=lambda x: x['predicted_peel_n'])
        fine = solve(shape, stub, weak['direction'], a.fine)
        print(f"  {stub:5} {weak['direction']}  {a.fine} mm: peel {fine['predicted_peel_n']} N", flush=True)
        rows += mine + [fine]
    out = {'schema': 1, 'what': 'coupon C4: FEA of the coupon at 1 kN, the load at which each criterion reaches 1',
           'toolkit': version('cad-agent'), 'gmsh': __import__('gmsh').__version__,
           'normal': list(NORMAL), 'cut_back_mm': rb.C4_CUT_BACK, 'rows': rows}
    (a.out / 'c4-fea.json').write_text(json.dumps(out, indent=1) + '\n')
    print('wrote', a.out / 'c4-fea.json')


if __name__ == '__main__':
    main()
