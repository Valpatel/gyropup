#!/usr/bin/env python3
"""The body's FEA cases (cad/body_studies.py, cadagent.fea) on each option's parts, at the same loads, meshes and
targets as today's record. cad/ is imported and patched in this process only: nothing in it is edited.

    python research/body-sheet-metal/fea.py --option today            # every case, today's parts (the baseline, rerun here)
    python research/body-sheet-metal/fea.py --option A                 # the deck cases on option A's deck (no turret plate)
    python research/body-sheet-metal/fea.py --option B                 # the spine cases on option B's keel (no belly plate)
    python research/body-sheet-metal/fea.py --option C                 # the deck and tray cases with printed PA6-CF plates

Writes research/body-sheet-metal/fea/<option>/summary.json (+ a picture per case). Each option's summary records the
host's role, the mesher and the toolkit, so a before and an after are compared on one host and one mesh (the rule in
.agents/inbox/2026-10-31-a-gate-at-one-mesh-needs-its-mesher-and-a-finer-check.md).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parts as P  # noqa: E402

import body_params as bp  # noqa: E402
import body_frame as bf  # noqa: E402

CASES = {'today': ['S1', 'S1F', 'S2', 'S3', 'D1', 'D2', 'T1'],
         'A': ['D1', 'D2'],                            # the spine and the tray are today's: their cases are the baseline's
         'B': ['S1', 'S1F', 'S2', 'S3'],                      # the deck and tray are A's
         'C': ['D1', 'D2', 'T1']}                      # the spine and keel are B's
PRINTED_T = {'deck': 8.0, 'tray': 8.0}                 # option C: solid PA6-CF plates this thick (two halves each, joined)


def _printed_stock(t_mm):
    key = f'pa6cf-{t_mm:g}'
    if key not in bp.STOCK:
        s = {'material': 'PA6-CF printed', 't_in': t_mm / bp.IN, 'bend': True, 'r_in': 1.0 / bp.IN, 'k': 0.5, 'bd_in': 0.0,
             'min_flange_in': 0.0, 'die_in': 0.0, 'countersink': False, 'hardware': False, 'density': 1.09,
             'yield_mpa': 40.8, 'E_mpa': 1028.0}
        s['t'], s['r'] = t_mm, 1.0
        s['ossb'] = s['r'] + s['t']
        s['ba'] = 3.14159265 / 2 * (s['r'] + 0.5 * s['t'])
        s['bd'] = 2 * s['ossb'] - s['ba']
        s['min_flange'], s['half_die'] = 0.0, 0.0
        bp.STOCK[key] = s
    return key


def patch(option, mounts):
    """Swap the option's parts into cad/body_frame.frame_parts() and cad/body_studies for this process."""
    import body_studies as st
    orig = bf.frame_parts
    if option in ('A', 'C'):
        if option == 'A':
            # the tray keeps its four bends (the two-bend tray missed T1: fea/A-tray2b, made at b169a6d)
            deck, tray = P.deck_2b(mounts), bf.tray_part(mounts)
            bp.DECK = deck.stock
        else:
            deck = P.two_bends(bf.deck_part(mounts), 'deck_printed', stock=_printed_stock(PRINTED_T['deck']))
            tray = P.two_bends(bf.tray_part(mounts), 'tray_printed', stock=_printed_stock(PRINTED_T['tray']))
            bp.DECK, bp.TRAY = deck.stock, tray.stock
            from cadagent.fea import MATERIALS
            # the deck and tray's material. deck_cases meshes its whole model (the turret plate too) in this one
            # material, so C's deflection is an upper bound (review of PR #158); C fails D1 by 4x either way
            st.AL5052 = MATERIALS['pa6_cf_xy']

        def frame_parts(m=None):
            out = orig(m)
            out['deck'] = bf.Part('deck', 'sheet', bf.place_tray(deck.solid(), bp.TOP), 1, deck, None, deck.s['material'])
            out['floor_tray'] = bf.Part('floor_tray', 'sheet', bf.place_tray(tray.solid(), bp.z_tray_top()), 1, tray, None,
                                        tray.s['material'])
            if option == 'A':                          # the turret plate is folded into the deck
                out.pop('turret_plate', None)
                out.pop('turret_plate_nuts', None)
            return out
        bf.frame_parts = frame_parts
    if option == 'B':
        bp.BELLY = P.KEEL_STOCK
        st.spine_box = lambda: keel_spine_box()
    if option == 'A':
        _deck_by_part_without_plate(st)


def _deck_by_part_without_plate(st):
    """cad/body_studies.deck_cases judges the deck 'by part' only when the turret plate is on: the elements within 4 mm
    of a post pad's footprint or a clamp pad's rim (rigid-clamp corners, singular in a linear model) are reported apart.
    Without the plate it returns the raw peak, which sits on those corners, so option A would be judged on a measure
    today's deck is not. This rebuilds deck_cases in this process with the same by-part rule when the plate is gone (the
    riser's four feet, which bolt through the deck in A, keep their clamp zones; there are no plate elements)."""
    import inspect
    import textwrap
    src = textwrap.dedent(inspect.getsource(st.deck_cases))
    old = "        if plate is None:\n            return {}\n"
    assert old in src, 'cad/body_studies.deck_cases changed: update fea.py'
    src = src.replace(old, "")
    for a in ("+ [(x, y, PLATE_CLAMP_D) for x, y in bf.turret_plate_end_holes()])", "sf = min(v for v in (sfd, sfp) if v)"):
        assert a in src, 'cad/body_studies.deck_cases changed: update fea.py'
    src = src.replace("+ [(x, y, PLATE_CLAMP_D) for x, y in bf.turret_plate_end_holes()])",
                      "+ ([(x, y, PLATE_CLAMP_D) for x, y in bf.turret_plate_end_holes()] if parts.get('turret_plate') is not None else []))")
    src = src.replace("sf = min(v for v in (sfd, sfp) if v)", "sf = min(v for v in (sfd, sfp) if v) if (sfd or sfp) else None")
    ns = st.__dict__
    exec(compile(src, st.__file__, 'exec'), ns)        # defines deck_cases in body_studies' own namespace


def keel_spine_box():
    """Option B's spine: the cheeks and standoffs as today, the tray's middle strip as today, and in place of the belly
    plate's strip the two keel halves' top flanges (|y| 3 to 51.2) with the top strap riveted under them (|y| < 20), the
    rivets modelled as a bond. The keel's webs and floor are left out (they only add stiffness)."""
    parts = bf.frame_parts()
    s = parts['cheek_left'].shape.union(parts['cheek_right'].shape)
    for x, z in bf.SPACERS_XZ:
        s = s.union(bf.hexagon_y(bf.SPACER_HEX, -bf.GAP_Y - 0.5, bf.GAP_Y + 0.5, x, z))
    zt = bf.ZT
    ttr = bp.STOCK[bp.TRAY]['t']
    tk = bp.STOCK[P.KEEL_STOCK]['t']
    k = P.keel_geometry()
    x0, x1 = bp.SPINE_X[0] - 30.0, bp.SPINE_X[1] + 30.0
    half = bf.PEM_Y + 14.0
    tray = bf.box(x0, x1, -half, half, zt - 0.05, zt + ttr)
    flange = None
    for sy in (1, -1):
        y0, y1 = sorted((sy * P.KEEL_IN, sy * k['half_y']))
        f = bf.box(x0, x1, y0, y1, -zt - tk, -zt + 0.05)
        flange = f if flange is None else flange.union(f)
    strap = bf.box(x0, x1, -P.STRAP_W / 2, P.STRAP_W / 2, -zt - 2 * tk, -zt - tk + 0.05)
    for x in bf.FLANGE_NUT_X:
        for sy in (1, -1):
            tray = tray.cut(bf.cyl_z(2.75, zt - 1, zt + ttr + 1, x, sy * bf.PEM_Y))
            flange = flange.cut(bf.cyl_z(2.75, -zt - tk - 1, -zt + 1, x, sy * bf.PEM_Y))
    return s.union(tray).union(flange).union(strap).clean()


def provenance():
    import cadagent
    src = Path(cadagent.__file__).resolve().parents[2]
    try:
        sha = subprocess.run(['git', '-C', str(src), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = None
    try:
        import gmsh
        mesher = f'gmsh {gmsh.__version__}'
    except Exception:
        mesher = 'gmsh (version not read)'
    rsha = subprocess.run(['git', '-C', str(P.R), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    return {'host_role': os.environ.get('GYROPUP_HOST_ROLE', 'a CAD host'), 'arch': platform.machine(), 'mesher': mesher,
            'toolkit': f'cad-agent {sha[:7] if sha else "?"}', 'source': rsha[:7], 'python': platform.python_version(),
            'date': time.strftime('%Y-%m-%d')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--option', required=True, choices=sorted(CASES))
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--tag', default='', help='a suffix for the output folder (a finer-mesh check, a variant)')
    a = ap.parse_args()
    out = HERE / 'fea' / (a.option + a.tag)
    out.mkdir(parents=True, exist_ok=True)
    os.environ['GYROPUP_BODY_FEA_OUT'] = str(out)
    import body_layout as bl
    import body_studies as st
    st.OUT = out
    patch(a.option, bl.layout()['mounts'])
    cases = set(a.only or CASES[a.option])
    t0 = time.time()
    res = st.run(a.mesh, False, cases)
    summ = json.loads((out / 'summary.json').read_text())
    summ['option'] = a.option
    summ['mesh_mm'] = a.mesh
    summ['provenance'] = provenance()
    summ['seconds'] = round(time.time() - t0)
    for r in summ['results'].values():                 # repository-relative paths only
        for k in ('picture', 'animation', 'viewer'):
            if isinstance(r.get(k), str) and r[k].startswith('/'):
                r[k] = os.path.relpath(r[k], P.R)
    (out / 'summary.json').write_text(json.dumps(summ, indent=1, default=str) + '\n')
    print(f'{a.option}: {len(res)} cases in {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
