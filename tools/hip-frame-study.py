#!/usr/bin/env python3
"""The hip frame's strength cases (cad/leg_studies.py) for one geometry, with the stress resolved against the print's
layers: issue #29's study and sweep evaluator.

    python tools/hip-frame-study.py --out build/hip-frame/base                   # every hip-frame case, 4 mm mesh
    python tools/hip-frame-study.py --params p.json --cases E1 R1 --out DIR      # a variant (cad/fivebar.py HIP keys)
    python tools/hip-frame-study.py --evaluator --out-root build/hip-frame/sweep   # cad-agent optimise command evaluator

It runs leg_studies.run(only=['hip_frame']) unchanged (same loads, clamps, masks and allowable), so its safety factor
is the one summary.json records, and adds, per case:

  layers   the stress at every element corner resolved against the layers of a print whose layer normal is n
           (web-down, the frame's print: n = y). sigma_n = n.S.n is the stress across the layers, tau_n the shear
           along them. Two checks, both on the elements leg_studies judges (away from the clamps, the load patches
           and a stop pin's bearing band):
             bond  sqrt(max(sigma_n, 0)^2 + 3 tau_n^2) against the across-layer allowable (pa6_cf_z: 23.0 MPa)
             bulk  von Mises against the in-layer allowable (pa6_cf_xy: 49.0 MPa)
           The interlayer shear strength is not on the data sheet; tau_n is taken against the across-layer allowable
           as von Mises takes shear (S / sqrt 3). Compression across the layers does not open them and counts only
           in the bulk check. It is a screening criterion for a transversely isotropic print, not a qualification.
  peak     where the isotropic design stress is, its stress tensor and principal stresses
  mass     the frame's printed mass (CAD volume x the material's density)

The leg's load shares come from exports/leg/fea/summary.json (copied into --out), as in tools/export-hip-frame-e1.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LAYER_NORMALS = {'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0), 'x': (1.0, 0.0, 0.0)}
PRINT_NORMAL = 'y'                 # the frame prints web-down: its layers are x-z planes, stacked along y
HF_CASES = ('E1', 'R1', 'E3o', 'E3i', 'R3o')
STUDIES = []                       # every Study solved in this process, in order


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stress_corners(st):
    """The Cauchy stress (MPa) at each element's four corners, as cadagent.fea computes von Mises: (3, 3, nel, 4)."""
    from skfem import Basis, ElementTetP2, ElementVector
    from skfem.models.elasticity import lame_parameters
    Xv = np.array([[0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
    vb = Basis(st._m, ElementVector(ElementTetP2()), quadrature=(Xv, np.full(4, 1.0 / 24)))
    G = vb.interpolate(st._u).grad
    eps = 0.5 * (G + np.transpose(G, (1, 0, 2, 3)))
    lam, mu = lame_parameters(st.material.E_mpa, st.material.nu)
    tr = eps[0, 0] + eps[1, 1] + eps[2, 2]
    sig = 2 * mu * eps
    for i in range(3):
        sig[i, i] += lam * tr
    return sig


def layer_terms(sig, n):
    """sigma_n and tau_n (MPa) for layer normal n at every corner: (nel, 4) each."""
    n = np.asarray(n, float)
    t = np.einsum('ijek,j->iek', sig, n)                       # traction on the layer plane
    sn = np.einsum('iek,i->ek', t, n)
    tau = np.linalg.norm(t - sn[None] * n[:, None, None], axis=0)
    return sn, tau


def install_recorder():
    import leg_studies
    from cadagent.fea import Study

    class Recorded(Study):
        def solve(self):
            r = super().solve()
            STUDIES.append(self)
            return r
    leg_studies.Study = Recorded
    return leg_studies


def judged_mask(ls, st, case):
    """The elements leg_studies takes the design stress over: away from clamps and loads, and for a stop-post case
    away from the pin's bearing band too."""
    keep = ~st._touches_bc
    if case in ls.STOP_POST_AT:
        px, pz = ls.STOP_POST_AT[case]
        import fivebar as fb
        c = st.points[st.tets[:, :4]].mean(axis=1)
        keep &= np.hypot(c[:, 0] - px, c[:, 2] - pz) > fb.STOP_PIN[0] / 2 + fb.STOP_HOLE_PLAY + ls.PIN_HOLE_BAND
    return keep


def analyse(ls, st, case, s_z, s_xy):
    keep = judged_mask(ls, st, case)
    sig = stress_corners(st)
    vm = st.vm_corner
    i = int(np.argmax(np.where(keep, st.vm_elem, -1.0)))
    k = int(np.argmax(vm[i]))
    S = sig[:, :, i, k]
    w, v = np.linalg.eigh(S)
    corner = st._m.p[:, st._m.t[k, i]]
    out = {'peak': {'element_centre_mm': [round(float(x), 1) for x in st._m.p[:, st._m.t[:, i]].mean(axis=1)],
                    'corner_mm': [round(float(x), 1) for x in corner],
                    'von_mises_mpa': round(float(vm[i, k]), 2),
                    'stress_mpa': [[round(float(S[a, b]), 2) for b in range(3)] for a in range(3)],
                    'principal_mpa': [round(float(x), 2) for x in w[::-1]],
                    'principal_dirs': [[round(float(x), 3) for x in v[:, j]] for j in (2, 1, 0)]},
           'layers': {}}
    for name, n in LAYER_NORMALS.items():
        sn, tau = layer_terms(sig, n)
        bond = np.sqrt(np.maximum(sn, 0.0) ** 2 + 3 * tau ** 2) / s_z
        bulk = vm / s_xy
        f = np.maximum(bond, bulk).max(axis=1)
        j = int(np.argmax(np.where(keep, f, -1.0)))
        kk = int(np.argmax(np.maximum(bond[j], bulk[j])))
        bond_e, bulk_e = bond.max(axis=1), bulk.max(axis=1)
        out['layers'][name] = {
            'sf': round(1.0 / float(f[j]), 2), 'governed_by': 'bond' if bond[j, kk] >= bulk[j, kk] else 'bulk',
            'sf_bond': round(1.0 / float(np.where(keep, bond_e, 0).max()), 2),
            'sf_bulk': round(1.0 / float(np.where(keep, bulk_e, 0).max()), 2),
            'at_mm': [round(float(x), 1) for x in st._m.p[:, st._m.t[:, j]].mean(axis=1)],
            'sigma_n_mpa': round(float(sn[j, kk]), 2), 'tau_n_mpa': round(float(tau[j, kk]), 2),
            'at_isotropic_peak': {'sigma_n_mpa': round(float(sn[i, k]), 2), 'tau_n_mpa': round(float(tau[i, k]), 2)}}
    return out


def render(st, path, vmax, title, view):
    """cadagent.fea.Study.render with the colour scale fixed at vmax (MPa), so variants compare at one scale."""
    saved = dict(st.result)
    st.result['von_mises_design_mpa'] = vmax
    try:
        st.render(path, view=view, title=title)
    finally:
        st.result.clear()
        st.result.update(saved)


def run_variant(out: Path, params: dict | None, cases, mesh: float, vmax: float | None, viewer: bool, dump: bool = False):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if params:
        (out / 'params.json').write_text(json.dumps(params, indent=1) + '\n')
        os.environ['GYROPUP_HIP_PARAMS'] = str((out / 'params.json').resolve())
    shutil.copyfile(ROOT / 'exports/leg/fea/summary.json', out / 'summary.json')
    sys.path[:0] = [str(ROOT / 'cad'), str(ROOT)]
    import gmsh  # noqa: F401  (before CadQuery, as the compute hosts' mesher wants)
    ls = install_recorder()
    import fivebar as fb
    from cadagent.fea import MATERIALS
    ls.OUT = out
    t0 = time.time()
    summ = ls.run(mesh, anim=False, only=['hip_frame'], only_cases=list(cases), viewer=viewer)
    s_z, s_xy = MATERIALS['pa6_cf_z'].strength_mpa, MATERIALS['pa6_cf_xy'].strength_mpa
    frame = fb.leg_parts().parts['hip_frame'].val()
    rows = []
    for r, st in zip(summ['results'], STUDIES):
        a = analyse(ls, st, r['case'], s_z, s_xy)
        if dump:                                             # the field, for probing the stress along a feature later
            sig = stress_corners(st).mean(axis=3)
            np.savez_compressed(out / f"field-{r['case']}.npz", centre=st.points[st.tets[:, :4]].mean(axis=1).astype(np.float32),
                                vm=st.vm_elem.astype(np.float32), keep=judged_mask(ls, st, r['case']),
                                sig=np.stack([sig[0, 0], sig[1, 1], sig[2, 2], sig[0, 1], sig[1, 2], sig[0, 2]]).T.astype(np.float32))
        row = {k: r.get(k) for k in ('part', 'case', 'safety_factor', 'target', 'ok', 'von_mises_design_mpa', 'design_peak_at_mm',
                                     'max_displacement_mm', 'load_from', 'material_id', 'seconds')}
        row['mesh'] = r['mesh']
        row.update(a)
        row['layers_ok'] = a['layers'][PRINT_NORMAL]['sf'] >= r['target']
        if vmax:
            png = out / f"hip_frame-{r['case']}-fixed.png"
            render(st, png, vmax, f"hip_frame {r['case']}: SF {r['safety_factor']} (target {r['target']}), colour scale 0-{vmax:g} MPa",
                   ls.VIEWS['hip_frame'])
            row['png_fixed_scale'] = png.name
        rows.append(row)
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', 'cad', 'sim', 'tools/hip-frame-study.py'], cwd=ROOT, text=True,
                           capture_output=True).stdout.strip()
    import cadagent
    res = {'schema': 1, 'source_revision': rev, 'source_dirty': bool(dirty), 'params': params or {}, 'hip': dict(getattr(fb, 'HIP', {})),
           'mesh_mm': mesh, 'cases': rows, 'mass_g': round(frame.Volume() / 1000 * MATERIALS['pa6_cf_z'].density_g_cm3, 1),
           'volume_mm3': round(frame.Volume(), 1), 'allowables_mpa': {'across_layers': s_z, 'in_layers': s_xy},
           'print_normal': PRINT_NORMAL, 'toolkit': str(Path(cadagent.__file__).parent), 'seconds': round(time.time() - t0, 1),
           'inputs_sha256': {p: sha(ROOT / p) for p in ('cad/fivebar.py', 'cad/leg_studies.py', 'sim/leg_rig.py',
                                                        'exports/leg/rig-results.json', 'exports/leg/fea/summary.json')}}
    (out / 'result.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


def metrics(res):
    """The sweep's numbers: each case's isotropic SF (the gate) and its layer-resolved SF in the frame's print."""
    m = {'mass_g': res['mass_g']}
    worst = []
    for c in res['cases']:
        m[f"sf_{c['case']}"] = c['safety_factor']
        m[f"sf_layers_{c['case']}"] = c['layers'][PRINT_NORMAL]['sf']
        worst.append(c['safety_factor'] / c['target'])
    m['margin_min'] = round(min(worst), 3)
    return m


def evaluator(out_root: Path, mesh: float):
    """cad-agent optimise's command evaluator: the request (JSON) on stdin, the result (JSON) on stdout."""
    req = json.loads(sys.stdin.read())
    params = (req.get('params') or {}).get('hip') or {}
    out = out_root / req.get('id', 'trial')
    try:
        res = run_variant(out, params, HF_CASES, mesh, None, False)
    except Exception as exc:                                 # a geometry the kernel cannot build is a failed trial
        print(json.dumps({'metrics': {}, 'checks': [{'id': 'build', 'level': 'fail', 'text': f'{type(exc).__name__}: {exc}'}]}))
        return
    m = metrics(res)
    checks = [{'id': f"sf-{c['case']}", 'level': 'ok' if c['ok'] else 'fail',
               'text': f"{c['case']} SF {c['safety_factor']} against {c['target']}"} for c in res['cases']]
    print(json.dumps({'metrics': {**m, 'mass_kg': round(res['mass_g'] / 1000, 4)}, 'checks': checks,
                      'summary': ', '.join(f"{c['case']} {c['safety_factor']}" for c in res['cases']),
                      'data': {'result': str((out / 'result.json').relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out / 'result.json')}}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path)
    ap.add_argument('--params', type=Path, help='JSON: cad/fivebar.py HIP keys to change')
    ap.add_argument('--cases', nargs='+', default=list(HF_CASES))
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--vmax', type=float, help='also render each case with this colour scale (MPa)')
    ap.add_argument('--viewer', action='store_true')
    ap.add_argument('--dump', action='store_true', help='save each case\'s stress field (field-<case>.npz)')
    ap.add_argument('--evaluator', action='store_true')
    ap.add_argument('--out-root', type=Path, default=ROOT / 'build/hip-frame/sweep')
    a = ap.parse_args()
    if a.evaluator:
        return evaluator(a.out_root, a.mesh)
    params = json.loads(a.params.read_text()) if a.params else None
    res = run_variant(a.out, params, a.cases, a.mesh, a.vmax, a.viewer, a.dump)
    for c in res['cases']:
        L = c['layers'][PRINT_NORMAL]
        print(f"{c['case']:4} SF {c['safety_factor']:5} (>= {c['target']})  layers({PRINT_NORMAL}) {L['sf']} [{L['governed_by']}] "
              f"peak {c['peak']['element_centre_mm']} sigma_n {L['at_isotropic_peak']['sigma_n_mpa']} tau_n {L['at_isotropic_peak']['tau_n_mpa']}",
              flush=True)
    print('mass', res['mass_g'], 'g')


if __name__ == '__main__':
    main()
