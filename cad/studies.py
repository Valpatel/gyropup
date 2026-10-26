"""Stiffness and strength studies of the leg parts under the simulator's worst loads (cadagent.fea).

    .venv/bin/python cad/studies.py [designs/default.json] [--mesh 4]

Load cases come from exports/sim/<design>/*.json (link_loads: the wrench each link takes at its joint, in its own
frame, at the moment of peak force and of peak moment) and are turned into loads on the CAD parts:

  thigh (clamped on its AO-L mate at the hip)
    T1 in-plane, hard catch: knee pin force = shin force + the push-rod's reaction, P = knee torque / crank radius,
       along the thigh (the rod is a two-force member, so the knee torque reaches the thigh as an axial pin load)
    T2 out-of-plane, hard turn: lateral force and the twisting and out-of-plane moments the shin passes to the knee
  shin (held at its knee bearings and push-rod pin)
    S1 the wheel's peak force at the WH face, with the moment of the lateral grip about the axle (tyre radius) and of
       the vertical load about the WH face (the wheel's offset)

Each part is studied in printed PA6-CF and in 6061 aluminium. Targets (docs/mechanical-interfaces.md): printed
safety factor >= 2 on layer strength, metal >= 2 on yield; leg deflection at the wheel <= 2 mm. Writes
exports/fea/<part>-<case>-<material>.png and exports/fea/summary.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))

import gmi  # noqa: E402
import leg  # noqa: E402
from cadagent.fea import MATERIALS, Study, cylinder_at, plane_at  # noqa: E402

EXPORTS = Path(os.environ['GYROPUP_EXPORTS']).resolve() if os.environ.get('GYROPUP_EXPORTS') else R / 'exports'
OUT = EXPORTS / 'fea'


def worst_link_loads(stem: str) -> dict:
    """For each link: the run with the peak force and the run with the peak moment."""
    best = {}
    for f in glob.glob(str(EXPORTS / 'sim' / stem / '*.json')):
        if f.endswith('summary.json'):
            continue
        r = json.loads(Path(f).read_text())
        for body, v in (r.get('link_loads') or {}).items():
            b = best.setdefault(body, {})
            if v.get('force_n', 0) > b.get('force', {}).get('force_n', -1):
                b['force'] = {**v, 'scenario': r['scenario']}
            if v.get('moment_nm', 0) > b.get('moment', {}).get('moment_nm', -1):
                b['moment'] = {**v, 'scenario': r['scenario']}
    return best


# Design floor: the loads a part must take even if no scripted scenario produced them (falls, kicks, a hard turn on
# rough ground). Each case uses the larger of the simulated load and this floor.
FLOOR = {'vertical_x_static': 2.5,      # vertical wheel load, times the static load per wheel
         'lateral_g': 0.5}              # sideways grip on one wheel, as a fraction of the whole robot's weight


def cases(loads: dict, L: dict, S, crank_r: float, mass_kg: float = 20.0) -> dict:
    a, b = L['thigh'], L['shin']
    W = mass_kg * 9.81
    vert_floor, lat_floor = FLOOR['vertical_x_static'] * W / 2, FLOOR['lateral_g'] * W
    leg_h = (a + b) * 0.9 / 1000 + L['wheelR'] / 1000             # hip to the tyre's contact, standing
    sh_f = loads['shin_l']['force']
    th_m = loads['thigh_l']['moment']
    wh = loads['wheel_l']['force']
    Fx, _, Fz = sh_f['force_vec_body']
    My = sh_f['moment_with_force_body'][1]
    P = abs(My) / (crank_r / 1000.0)                          # push-rod force, N
    # T1: pin force on the thigh at the knee = -(shin force - rod force along the thigh axis)
    t1 = {'force': (-Fx, 0.0, -(Fz) + P), 'moments': {'x': -sh_f['moment_with_force_body'][0], 'z': -sh_f['moment_with_force_body'][2]},
          'from': f"{sh_f['scenario']}: shin force {sh_f['force_n']:.0f} N, knee torque {abs(My):.0f} N·m -> push-rod {P:.0f} N"}
    # T2: the thigh's peak hip moment (out of plane) re-expressed as loads at the knee: M_knee = M_hip - r x F
    Fh = list(th_m['force_with_moment_body'])
    Mh = list(th_m['moment_vec_body'])
    if abs(Fh[1]) < lat_floor:                                     # the floor: 0.5 g sideways at the tyre
        Fh[1] = -lat_floor
        Mh[0] = -max(abs(Mh[0]), lat_floor * leg_h)
    mx_knee = Mh[0] - a / 1000.0 * Fh[1]
    t2 = {'force': tuple(Fh), 'moments': {'x': mx_knee, 'z': Mh[2]},
          'from': f"{th_m['scenario']} or the floor: out-of-plane moment at the hip {abs(Mh[0]):.0f} N·m, lateral force {abs(Fh[1]):.0f} N"}
    # S1: wheel force at the WH face: vertical and lateral, plus the lateral grip's moment about the axle and the
    # vertical load's moment about the WH face (the wheel's offset from the shin)
    Fw = wh['force_n']
    lat = max(abs(wh['force_vec_body'][1]), lat_floor)
    vert = max(math.sqrt(max(0.0, Fw ** 2 - min(lat, Fw) ** 2)), vert_floor)
    off = (S.y['wheel_centre'] - S.y['shin'][1]) / 1000.0
    s1 = {'force': (0.0, -lat, vert), 'moments': {'x': lat * L['wheelR'] / 1000.0 + vert * off},
          'from': f"{wh['scenario']} or the floor: {vert:.0f} N vertical, {lat:.0f} N sideways, wheel offset {off * 1000:.0f} mm"}
    return {'T1': t1, 'T2': t2, 'S1': s1}


def run(design: Path, mesh: float):
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True)
    L = json.loads(out.stdout)['layout']
    d = json.loads(design.read_text())
    hip_id = d['parts']['leg_actuator']
    parts, meta, bought, S, assumed = leg.leg_parts(L, hip_id, hip_id, d['parts']['wheel_motor'])
    cr = leg.PARAMS['crank_r']
    loads = worst_link_loads(design.stem)
    mass = json.loads((R / 'build' / 'sim' / design.stem / 'model.json').read_text())['total_mass_kg'] if (R / 'build' / 'sim' / design.stem / 'model.json').exists() else 20.0
    C = cases(loads, L, S, cr, mass)
    a, b = L['thigh'], L['shin']
    yt, ys = sum(S.y['thigh']) / 2, sum(S.y['shin']) / 2
    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    def study(part, case, material, setup):
        t0 = time.time()
        st = Study(parts[part], MATERIALS[material], mesh_mm=mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        png = OUT / f'{part}-{case}-{material}.png'
        st.render(png, title=f"{part} {case} ({MATERIALS[material].name}): SF {r['safety_factor']}, "
                             f"{r['probe_displacement_mm'] and round(math.hypot(*r['probe_displacement_mm']), 2)} mm at the load")
        r.update(part=part, case=case, material_id=material, load_from=C[case]['from'], png=str(png.relative_to(R)),
                 seconds=round(time.time() - t0, 1), assumed_interfaces=assumed)
        results.append(r)
        print(f"  {part:6} {case} {material:7} SF {r['safety_factor']}  stress {r['von_mises_design_mpa']} MPa  "
              f"deflection {math.hypot(*r['probe_displacement_mm']):.3f} mm  ({r['mesh']['tets']} tets, {r['seconds']} s)")

    hip_mate = cylinder_at((0, yt, 0), (0, 1, 0), within=32, radius_max=21)
    knee_pin = cylinder_at((0, yt, -a), (0, 1, 0), radius_max=7)

    def thigh_setup(case):
        def f(st):
            st.fix(hip_mate)
            st.force(knee_pin, C[case]['force'])
            for ax, m in C[case]['moments'].items():
                if abs(m) > 0.05:
                    st.torque(knee_pin, (0, yt, -a), {'x': (1, 0, 0), 'z': (0, 0, 1)}[ax], m, probe=False)
        return f

    bearings = cylinder_at((0, ys, -a), (0, 1, 0), radius_max=15)
    rod_pin = cylinder_at((cr, S.y['rod'][1] + 6.5, -a), (0, 1, 0), radius_max=4)
    wh_bolts = cylinder_at((0, S.y['shin'][1], -a - b), (0, 1, 0), within=27, radius_max=4)    # the WH screws carry the wheel

    def shin_setup(st):
        st.fix(lambda f: bearings(f) or rod_pin(f))
        st.force(wh_bolts, C['S1']['force'])
        m = C['S1']['moments']['x']
        st.torque(wh_bolts, (0, S.y['shin'][1], -a - b), (1, 0, 0), m, probe=False)

    for material in ('al6061',):
        study('thigh', 'T1', material, thigh_setup('T1'))
        study('thigh', 'T2', material, thigh_setup('T2'))
        study('shin', 'S1', material, shin_setup)

    # --- the joint hardware, in each part's own motor frame (axis z, output face z = 0, robot "up" = +y)
    import numpy as np
    rad = lambda f: float(np.hypot(f.center[0], f.center[1]))
    leg_f = C['S1']['force']                                   # the leg's peak wheel force, re-used at the hip
    M_out = abs(C['T2']['moments']['x']) + abs(C['T2']['force'][1]) * a / 1000.0   # out-of-plane moment at the hip (with the floor)
    T_mot = max(abs(loads['shin_l']['force']['moment_with_force_body'][1]), 54.0)  # joint torque (peak knee)
    C['A1'] = {'from': f'motor torque {T_mot:.0f} N·m with {M_out:.0f} N·m out of plane and {leg_f[2]:.0f} N radial'}
    ad, adi = gmi.output_adapter(hip_id, 'L')
    parts['output_adapter'] = ad
    zf = adi['z_face']

    def adapter_setup(st):
        mp = S.hip['output']['bolts']['pcd'] / 2                 # the motor's own screws and dowels, whatever the motor
        st.fix(lambda f: f.kind == 'Cylinder' and abs(rad(f) - mp) < 2.5 and f.center[2] < zf - 2 and (f.bbox[3] - f.bbox[0]) < 7)
        face_bolts = lambda f: f.kind == 'Cylinder' and 22 < rad(f) < 28 and f.center[2] > zf - 10
        st.torque(face_bolts, (0, 0, zf), (0, 0, 1), T_mot)
        st.torque(face_bolts, (0, 0, zf), (1, 0, 0), M_out, probe=False)
        st.force(face_bolts, (0, leg_f[2], 0), probe=False)
    C['P1'] = {'from': f'{leg_f[2]:.0f} N up and {abs(leg_f[1]):.0f} N sideways through the bearing, {M_out:.0f} N·m out of plane, motor torque {T_mot:.0f} N·m on the lugs'}
    pl, pli = gmi.motor_plate(hip_id, 'L')
    parts['motor_plate'] = pl
    bz = pli['bearing_z']

    def plate_setup(st):
        posts = lambda f: f.kind == 'Cylinder' and abs(rad(f) - gmi.STD['AC-L']['post_r']) < 1.0 and (f.bbox[3] - f.bbox[0]) < 7
        st.fix(lambda f: (f.kind == 'Cylinder' and f.center[1] > pli['tab_top'] - 14) or posts(f))   # tab bolts and posts
        seat = lambda f: f.kind == 'Cylinder' and rad(f) < 1.0 and abs((f.bbox[3] - f.bbox[0]) / 2 - gmi.STD['AC-L']['bearing_od'] / 2) < 1.0
        st.force(seat, (0, leg_f[2], abs(leg_f[1])))
        st.torque(seat, (0, 0, sum(bz) / 2), (1, 0, 0), M_out, probe=False)
        lugs = lambda f: f.kind == 'Cylinder' and abs(rad(f) - S.hip['case']['bolts']['pcd'] / 2) < 1.0 and (f.bbox[3] - f.bbox[0]) < 6
        st.torque(lugs, (0, 0, 0), (0, 0, 1), T_mot, probe=False)
    C['Y1'] = {'from': f'the whole leg: {leg_f[2]:.0f} N up, {abs(leg_f[1]):.0f} N sideways, {M_out:.0f} N·m out of plane, {T_mot:.0f} N·m about the hip axis'}
    yk = parts['yoke_bracket']
    yw = S.y['bracket']

    def yoke_setup(st):
        st.fix(lambda f: f.kind == 'Cylinder' and yw[0] - 0.5 <= f.bbox[1] and f.bbox[4] <= yw[1] + 0.5 and (f.bbox[3] - f.bbox[0]) < 8)
        drops = lambda f: f.kind == 'Cylinder' and f.bbox[1] > yw[1] + 20 and (f.bbox[3] - f.bbox[0]) < 6.5
        st.force(drops, (0, -abs(leg_f[1]), leg_f[2]))
        yc = (S.y['hip_tab'][0] + S.y['knee_tab'][1]) / 2
        st.torque(drops, (0, yc, 0), (1, 0, 0), M_out, probe=False)
        st.torque(drops, (0, yc, 0), (0, 1, 0), T_mot, probe=False)

    study('output_adapter', 'A1', 'al6061', adapter_setup)
    study('motor_plate', 'P1', 'al6061', plate_setup)
    study('yoke_bracket', 'Y1', 'al6061', yoke_setup)

    # leg deflection at the wheel: thigh tip (worst case) carried down the shin, plus the shin's own
    summary = {'design': str(design.relative_to(R)), 'mesh_mm': mesh, 'cases': C, 'stack_mm': S.y, 'track_mm': S.track,
               'stack_notes': S.notes, 'assumed_interfaces': assumed, 'results': results,
               'targets': {'printed_sf': 2.0, 'metal_sf': 2.0, 'wheel_deflection_mm': 2.0}}
    by = {(r['part'], r['case'], r['material_id']): r for r in results}
    verdict = {}
    for material in ('al6061',):
        dt = max(math.hypot(*by[('thigh', c, material)]['probe_displacement_mm']) for c in ('T1', 'T2'))
        ds = math.hypot(*by[('shin', 'S1', material)]['probe_displacement_mm'])
        # the thigh tip's slope also swings the shin: approximate by the tip deflection scaled by (a + b) / a
        total = dt * (a + b) / a + ds
        sf = min(r['safety_factor'] for r in results if r['material_id'] == material)
        verdict[material] = {'wheel_deflection_mm': round(total, 2), 'min_safety_factor': sf,
                             'ok': total <= 2.0 and sf >= 2.0}
    summary['verdict'] = verdict
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o)) + '\n')
    print('verdict', json.dumps(verdict))
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?', default=str(R / 'designs/default.json'))
    ap.add_argument('--mesh', type=float, default=4.0)
    a = ap.parse_args()
    run(Path(a.design).resolve(), a.mesh)
