#!/usr/bin/env python3
"""The leg's printed parts on cad-agent's Study.layer_check() in three print orientations, from the record's own solves.

    python research/leg-preprint/orientation_screen.py --out build/leg-preprint/orientation [--mesh 4] [--only upper_link]

It runs cad/leg_studies.py's single-part studies unchanged (the same parts, loads, clamps, mesh and judged elements as
the record, the load shares from --summary; the whole-leg solves are not run) and after each solve of a printed part
resolves the stress on three layer planes, each given by its normal in the frame the part is meshed in:

  y  today's print (cad/build_leg.py ROT turns every part about x onto the bed): the layers stack along the part's y,
     the axis of every boss, bore, pin and screw in the leg
  z  on edge: a link stood on its long edge (layers along the link's width); the hip frame on a flange's outer face
  x  on end: the part's long axis up

The isotropic solve's stress does not depend on the orientation, so one solve gives all three. Each check is
research/fea-v060-29/layer_check.py's (the toolkit's default bond criterion, S_s = S_z / sqrt(3), and at S_z / 2), on
the elements the record judges. The orientation's other effects (bores turned horizontal print out of round, new
overhangs, the bed's size) are not in this number: screen.py and README.md weigh them.

Writes <out>/orientation-screen.json. A screening check, not a qualification: a printed part settles it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NORMALS = {'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0), 'x': (1.0, 0.0, 0.0)}
PARTS = ['upper_link', 'front_link', 'wheel_link', 'hip_frame']
ROWS: list = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--only', nargs='+', default=PARTS)
    ap.add_argument('--summary', type=Path, default=ROOT / 'exports/leg/fea/summary.json')
    a = ap.parse_args()
    sys.path[:0] = [str(ROOT / 'cad'), str(ROOT), str(ROOT / 'research/fea-v060-29')]
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    import gmsh  # noqa: F401  (before CadQuery, as the compute hosts' mesher wants)
    import layer_check as lc
    import leg_studies as ls
    from cadagent.simulation.fea import Study

    class Checked(Study):
        def solve(self):
            r = super().solve()
            part, case = self.name.split(' ', 1)
            if self.material.layer_strengths_mpa is None or case.endswith('-out-of-plane'):
                return r
            judge = lc.leg_judged(ls, self, part, case)
            s_z = self.material.layer_strengths_mpa[1]
            row = {'part': part, 'case': case, 'material': self.material.name, 'orientations': {}}
            for key, n in NORMALS.items():
                full = self.layer_check(n, judge=judge).as_dict()
                half = self.layer_check(n, judge=judge, strength_shear=0.5 * s_z).as_dict()
                w = full['worst']
                row['orientations'][key] = {
                    'normal': list(n), 'sf': full['safety_factor'], 'governed_by': full['governed_by'],
                    'sf_bond': full['safety_factor_bond'], 'sf_bulk': full['safety_factor_bulk'],
                    'sf_at_half_sz': half['safety_factor'],
                    'worst': {'corner_mm': w['corner_mm'], 'sigma_n_mpa': w['sigma_n_mpa'], 'tau_n_mpa': w['tau_n_mpa']}}
            ROWS.append(row)
            print(f"  {part:12} {case:5} " + '  '.join(f"{k} {v['sf']}" for k, v in row['orientations'].items()), flush=True)
            return r

    ls.Study = Checked
    shutil.copyfile(a.summary.resolve(), out / 'summary.json')
    ls.OUT = out
    t0 = time.time()
    summ = ls.run(a.mesh, anim=False, only=a.only)
    gate = {(r['part'], r['case']): r for r in summ['results']}
    for row in ROWS:
        r = gate.get((row['part'], row['case']))
        if r is not None:
            row.update(target=r['target'], gate_sf=r['safety_factor'], gate_material=r['material_id'])
    import cadagent
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    res = {'schema': 1, 'source_revision': rev, 'toolkit': lc.toolkit_identity(cadagent), 'mesh_mm': a.mesh,
           'seconds': round(time.time() - t0, 1), 'normals': {k: list(v) for k, v in NORMALS.items()},
           'shear_assumption': 'toolkit default S_z / sqrt(3); sf_at_half_sz repeats it at S_z / 2; neither is measured',
           'rows': [r for r in ROWS if 'gate_sf' in r]}
    (out / 'orientation-screen.json').write_text(json.dumps(res, indent=1, default=float) + '\n')


if __name__ == '__main__':
    main()
