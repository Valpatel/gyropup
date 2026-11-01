#!/usr/bin/env python3
"""cad-agent v0.6.0's Study.layer_check() on Gyropup's printed FEA studies, in each part's print orientation.

    python research/fea-v060-29/layer_check.py leg --out build/layer-check/leg --summary exports/leg/fea/summary.json
    python research/fea-v060-29/layer_check.py turret --out build/layer-check/turret

It runs the record's own studies unchanged (cad/leg_studies.py, cad/turret_studies.py: the same parts, loads, clamps,
mesh and judged elements) and, after each solve of a printed part, resolves the stress against the layers:

  bond  sqrt((max(sigma_n, 0) / S_z)^2 + (tau_n / S_s)^2): sigma_n across the layers against the across-layer
        allowable S_z, tau_n along them against the interlayer shear allowable S_s
  bulk  von Mises / S_xy, the in-layer allowable
  SF = 1 / the larger of the two, at the worst judged element corner

with S_xy and S_z from the material row's layer_strengths_mpa (PA6-CF humid: 40.84 / 18.13 MPa; PETG 24.6 / 20).
The interlayer shear allowable S_s is on no data sheet. The toolkit assumes S_z / sqrt(3); the turret study's own
layer-aware check (cad/turret_studies.py) assumes S_z / 2. Both are reported: neither is measured.

Layer normals, in the frame each study meshes the part in:
  leg     every printed part is turned about x by +-90 deg onto the bed (cad/build_leg.py ROT), so the layers stack
          along the part's y: n = (0, 1, 0). The whole-leg studies are not run here (the members are checked one by
          one, and the whole leg's three cases take about 1.5 h).
  turret  the print rotation in cad/turret.py MADE, taken back to the part (turret_studies.layer_normal), which is the
          rotation the turret's print STLs are exported with.

The judged elements are the record's: away from clamps and load patches, and for the leg's special cases the same
masks cad/leg_studies.py applies (a stop pin's bearing band on the hip frame, the bonded pad's rim on the upper link).
For the leg the load shares come from --summary (copied into --out), as tools/hip-frame-study.py does.
Writes <out>/layer-check.json. A screening check of the isotropic solve, not a qualification of a print.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LEG_NORMAL = (0.0, 1.0, 0.0)
LEG_PARTS = ['upper_link', 'front_link', 'wheel_link', 'hip_frame']
ROWS: list = []


def leg_judged(ls, st, part, case):
    """The elements cad/leg_studies.py takes the design stress over, for this part and case."""
    import fivebar as fb
    import gmi
    keep = ~st._touches_bc
    c = st.points[st.tets[:, :4]].mean(axis=1)
    if part == 'hip_frame' and case in ls.STOP_POST_AT:
        px, pz = ls.STOP_POST_AT[case]
        keep &= np.hypot(c[:, 0] - px, c[:, 2] - pz) > fb.STOP_PIN[0] / 2 + fb.STOP_HOLE_PLAY + ls.PIN_HOLE_BAND
    if part == 'upper_link':                       # every upper-link study meshes the padded link (leg_studies.run)
        r_rim = gmi.STD['AO-L']['journal_d'] / 2
        keep &= np.hypot(np.hypot(c[:, 0], c[:, 2]) - r_rim, c[:, 1]) > ls.PAD_RIM_BAND
    return keep


def check(st, part, case, normal, judge):
    s_z = st.material.layer_strengths_mpa[1]
    toolkit = st.layer_check(normal, judge=judge)
    half = st.layer_check(normal, judge=judge, strength_shear=0.5 * s_z)
    ROWS.append({'part': part, 'case': case, 'material': st.material.name,
                 'material_data': st.result.get('material_data'),
                 'layer_check': toolkit.as_dict(),
                 'shear_half_sz': {k: v for k, v in half.as_dict().items() if k in ('safety_factor', 'governed_by',
                                                                                   'safety_factor_bond', 'allowables_mpa')}})


def install(module, normal_of, judged_of):
    from cadagent.simulation.fea import Study

    class Checked(Study):
        def solve(self):
            r = super().solve()
            part, case = self.name.split(' ', 1)
            if self.material.layer_strengths_mpa is not None and not case.endswith('-out-of-plane'):
                check(self, part, case, normal_of(part), judged_of(self, part, case))
            return r
    module.Study = Checked


def run_leg(out, mesh, parts, cases, summary):
    import gmsh  # noqa: F401  (before CadQuery, as the compute hosts' mesher wants)
    import leg_studies as ls
    install(ls, lambda part: LEG_NORMAL, lambda st, part, case: leg_judged(ls, st, part, case))
    shutil.copyfile(summary, out / 'summary.json')
    ls.OUT = out
    return ls.run(mesh, anim=False, only=parts, only_cases=cases)


def run_turret(out, mesh, parts):
    import gmsh  # noqa: F401
    import turret_studies as ts
    install(ts, lambda part: tuple(float(v) for v in ts.layer_normal(part)), lambda st, part, case: None)
    ts.OUT = out
    return ts.run(mesh, anim=False, only=parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suite', choices=('leg', 'turret'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mesh', type=float)
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--cases', nargs='+')
    ap.add_argument('--summary', type=Path, default=ROOT / 'exports/leg/fea/summary.json',
                    help='leg: the record whose load shares the single-part studies take')
    a = ap.parse_args()
    sys.path[:0] = [str(ROOT / 'cad'), str(ROOT)]
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.suite == 'leg':
        summ = run_leg(out, a.mesh or 4.0, a.only or LEG_PARTS, a.cases, a.summary.resolve())
    else:
        summ = run_turret(out, a.mesh or 2.5, a.only)
    gate = {(r['part'], r['case']): r for r in summ['results']}
    for row in ROWS:
        r = gate.get((row['part'], row['case']))
        if r is None:
            continue
        lc = row['layer_check']['safety_factor']
        row.update(target=r['target'], gate_sf=r['safety_factor'], gate_material=r['material_id'],
                   verdict_sf=r.get('verdict_sf', r['safety_factor']), turret_layer_aware_sf=r.get('sf_layer_aware'),
                   layer_check_governs=lc is not None and lc < r['safety_factor'],
                   layer_check_ok=lc is not None and lc >= r['target'])
    from importlib.metadata import version            # cadagent has no __version__ (v0.6.0)
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    res = {'schema': 1, 'suite': a.suite, 'source_revision': rev, 'toolkit_version': version('cad-agent'),
           'mesh_mm': a.mesh or (4.0 if a.suite == 'leg' else 2.5), 'seconds': round(time.time() - t0, 1),
           'shear_assumption': 'toolkit default S_z / sqrt(3) (no data sheet gives an interlayer shear strength); '
                               'shear_half_sz repeats the check at S_z / 2, the turret study\'s own rule',
           'rows': [r for r in ROWS if 'gate_sf' in r]}
    (out / 'layer-check.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    for r in res['rows']:
        lc = r['layer_check']
        print(f"{r['part']:15} {r['case']:12} gate {r['gate_sf']:5} (>= {r['target']})  layer_check {lc['safety_factor']} "
              f"[{lc['governed_by']}]  at S_z/2 {r['shear_half_sz']['safety_factor']}  governs={r['layer_check_governs']}", flush=True)


if __name__ == '__main__':
    main()
