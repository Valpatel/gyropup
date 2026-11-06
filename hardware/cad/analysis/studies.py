"""Stiffness and strength studies of the leg parts under the simulator's worst loads (cadagent.fea).

    .venv/bin/python cad/studies.py [designs/default.json] [--mesh 4]

Load cases come from exports/sim/<design>/*.json (link_loads: the wrench each link takes at its joint, in its own
frame, at the moment of peak force and of peak moment) and are turned into loads on the CAD parts:

Bolted flanges are modelled clamped over their contact face (the yoke's wall flange on the chassis): right where the
joint stays in compression, optimistic where it lifts off. With only the bolt holes held the yoke reads ~6x weaker,
so the real number lies between; the bench test in docs/cad-plan.md (S4) measures it.

  thigh (clamped on its AO-L mate at the hip)
    T1 in-plane, hard catch: knee pin force = shin force + the push-rod's reaction, P = knee torque / crank radius,
       along the thigh (the rod is a two-force member, so the knee torque reaches the thigh as an axial pin load)
    T2 out-of-plane, hard turn: lateral force and the twisting and out-of-plane moments the shin passes to the knee
  shin (held at its knee bearings and push-rod pin)
    S1 the wheel's peak force at the WH face, with the moment of the lateral grip about the axle (tyre radius) and of
       the vertical load about the WH face (the wheel's offset)

Each part is studied in its own material (leg.leg_parts: PA6-CF along or across the layers, humid allowables).
Targets (docs/mechanical-interfaces.md): safety factor >= 2 everyday, >= 1.2 in falls; leg deflection at the wheel
<= 4 mm (printed). Writes exports/fea/<part>-<case>.png, an overload video exports/fea/<part>-<case>.mp4 (the load
ramped to failure and past it) with the interactive viewer's data exports/fea/<part>-<case>.json (--no-anim skips
both) and exports/fea/summary.json.
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


def worst_link_loads(stem: str, falls: bool = False) -> dict:
    """For each link: the run with the peak force and the run with the peak moment, over the everyday scenarios or
    (falls=True) over the fall scenarios only: falls are rare events with their own, lower, target."""
    best = {}
    for f in glob.glob(str(EXPORTS / 'sim' / stem / '*.json')):
        if f.endswith('summary.json'):
            continue
        r = json.loads(Path(f).read_text())
        if r['scenario'].startswith('fall') != falls:
            continue
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
# Printed parts: everyday SF 2 and falls 1.2 on humid, knocked-down allowables (cadagent.fea pa6_cf_*); the leg may
# flex up to 4 mm at the wheel (plastic is ~20x softer than aluminium; the balance loop tolerates it, the sim checks)
TARGETS = {'sf': 2.0, 'sf_fall': 1.2, 'wheel_deflection_mm': 4.0}
FEA_MATERIAL = {'output_adapter': 'pa6_cf_z', 'motor_plate': 'pa6_cf_xy'}


def cases(loads: dict, L: dict, S, crank_r: float, mass_kg: float = 20.0, floor: bool = True, motor_cap_nm: float | None = None) -> dict:
    a, b = L['thigh'], L['shin']
    W = mass_kg * 9.81
    vert_floor, lat_floor = (FLOOR['vertical_x_static'] * W / 2, FLOOR['lateral_g'] * W) if floor else (0.0, 0.0)
    leg_h = (a + b) * 0.9 / 1000 + L['wheelR'] / 1000             # hip to the tyre's contact, standing
    sh_f = loads['shin_l']['force']
    th_m = loads['thigh_l']['moment']
    wh = loads['wheel_l']['force']
    Fx, _, Fz = sh_f['force_vec_body']
    My = sh_f['moment_with_force_body'][1]
    sphi, at = leg.transmission(L['kneeMinDeg'], L['kneeMaxDeg'])
    # the push-rod carries only what the knee motor resists: its firmware cap (motor_cap_nm, +10 % overshoot); a fall that
    # folds the knee harder ends on the knee's hard stop, not in the rod (knee_stop_nm records that load)
    T_rod = min(abs(My), 1.1 * motor_cap_nm) if motor_cap_nm else abs(My)
    P = T_rod / (crank_r / 1000.0 * sphi)                      # push-rod force at the worst transmission angle, N
    # T1: pin force on the thigh at the knee = -(shin force - rod force along the thigh axis)
    t1 = {'force': (-Fx, 0.0, -(Fz) + P), 'moments': {'x': -sh_f['moment_with_force_body'][0], 'z': -sh_f['moment_with_force_body'][2]},
          'from': f"{sh_f['scenario']}: shin force {sh_f['force_n']:.0f} N, knee torque {abs(My):.0f} N·m"
                  + (f" (the rod takes the motor's {T_rod:.0f}, the knee stop the rest)" if T_rod < abs(My) else '')
                  + f" -> push-rod {P:.0f} N (sin phi {sphi:.2f} at a {at:.0f}° knee)",
          'rod_force_n': P, 'sin_phi': sphi, 'knee_torque_nm': abs(My), 'knee_stop_nm': max(0.0, abs(My) - T_rod)}
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


# The printed adapter on a motor's output: the torque goes through the clamp of the motor's screws (friction) and the
# dowels bearing on the plastic. Preload is limited by what PA6-CF takes under a DIN 9021 washer without creeping away.
JOINT = {'bearing_mpa': 40.0,           # PA6-CF (humid) under a pin or washer, sustained: compressive allowable
         'washer_mpa': 25.0,            # sustained pressure under a screw's washer (creep), sets the usable preload
         'mu': 0.25,                    # PA6-CF on the anodised output flange
         'washer_od': {'M3': 9.0, 'M4': 12.0, 'M5': 15.0, 'M6': 18.0}}


def output_joint(mi: dict, design: dict) -> dict:
    """Torque the screws' friction plus the dowels can carry at a motor's output, against the motor's (capped) peak."""
    o = mi['output']
    b, dw = o['bolts'], o['dowels']
    cat = json.loads((R / 'catalog/leg_actuators.json').read_text())
    items = cat if isinstance(cat, list) else cat.get('parts') or cat.get('items') or list(cat.values())
    peak = next((p['specs']['peak_torque_nm'] for p in items if isinstance(p, dict) and p.get('id') == mi['id']), 60.0)
    T = min(float(design.get('leg_torque_limit_nm') or peak), float(peak))
    clear_d = gmi.clear(b['thread'])
    area = math.pi / 4 * (JOINT['washer_od'][b['thread']] ** 2 - clear_d ** 2)
    preload = JOINT['washer_mpa'] * area                               # N per screw
    r_b = b['pcd'] / 2 / 1000
    friction = b['count'] * preload * JOINT['mu'] * r_b
    pins = 0.0
    if dw:
        engage = (dw.get('protrusion') or 3.0) if dw.get('installed') else 16.0
        pins = dw['count'] * JOINT['bearing_mpa'] * dw['d'] * engage * dw['pcd'] / 2 / 1000
    cap = friction + pins
    return {'torque_nm': round(T, 1), 'screws': f"{b['count']} x {b['thread']} on Ø{b['pcd']:g}, {preload / 1000:.1f} kN each",
            'friction_nm': round(friction, 1), 'dowels_nm': round(pins, 1), 'capacity_nm': round(cap, 1), 'sf': round(cap / T, 2),
            'note': 'clamp friction + dowel bearing on PA6-CF (humid, sustained); torque the screws to the preload, re-check after a week'}


def run(design: Path, mesh: float, anim: bool = True, only=None):
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True)
    L = json.loads(out.stdout)['layout']
    d = json.loads(design.read_text())
    hip_id = d['parts']['leg_actuator']
    parts, meta, bought, S, assumed = leg.leg_parts(L, hip_id, hip_id, d['parts']['wheel_motor'])
    cr = leg.PARAMS['crank_r']
    loads = worst_link_loads(design.stem)
    mass = json.loads((R / 'build' / 'sim' / design.stem / 'model.json').read_text())['total_mass_kg'] if (R / 'build' / 'sim' / design.stem / 'model.json').exists() else 20.0
    cap = d.get('leg_torque_limit_nm')
    C = cases(loads, L, S, cr, mass, motor_cap_nm=cap)
    a, b = L['thigh'], L['shin']
    yt, ys = sum(S.y['thigh']) / 2, sum(S.y['shin']) / 2
    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    VIEWS = {'thigh': (15, -115), 'shin': (15, -115), 'yoke_bracket': (25, -40)}

    def study(part, case, material=None, setup=None, tag=''):
        if only and part not in only:
            return
        t0 = time.time()
        material = material or meta.get(part, {}).get('fea_material') or FEA_MATERIAL.get(part, 'pa6_cf_z')
        st = Study(parts[part], MATERIALS[material], mesh_mm=mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        png = OUT / f'{part}-{case}{tag}.png'
        st.render(png, view=VIEWS.get(part, (25, -60)), title=f"{part} {case}{tag} ({MATERIALS[material].name}): SF {r['safety_factor']}, "
                             f"{r['probe_displacement_mm'] and round(math.hypot(*r['probe_displacement_mm']), 2)} mm at the load")
        if anim:
            mp4 = st.animate(OUT / f'{part}-{case}{tag}.mp4', view=VIEWS.get(part, (25, -60)),
                             title=f"{part} {case}{tag}: {MATERIALS[material].name}")
            r['animation'] = str(Path(mp4).relative_to(R))
            # the interactive viewer's data (designer/kit/fea.html?case=...): written with the videos, so the
            # optimiser's --no-anim runs stay fast and do not fill its trial folders
            r['viewer'] = str(st.export_viewer(OUT / f'{part}-{case}{tag}.json').relative_to(R))
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
    lx, lz = leg.lever_pin(cr)
    rod_pin = cylinder_at((lx, S.y['rod'][1] + 6.5, -a + lz), (0, 1, 0), radius_max=5)
    whp = gmi.STD['WH']['pcd'] / 2

    def wh_bolts(f):                                           # the WH screws' insert holes carry the wheel (on their circle)
        if f.kind != 'Cylinder' or (f.bbox[3] - f.bbox[0]) > 8.5:
            return False
        rr = math.hypot(f.center[0], f.center[2] + a + b)
        return abs(rr - whp) < 2.5 and f.bbox[4] > S.y['shin'][1] - 13

    def shin_setup(st):
        st.fix(lambda f: bearings(f) or rod_pin(f))
        st.force(wh_bolts, C['S1']['force'])
        m = C['S1']['moments']['x']
        st.torque(wh_bolts, (0, S.y['shin'][1], -a - b), (1, 0, 0), m, probe=False)

    study('thigh', 'T1', setup=thigh_setup('T1'))
    study('thigh', 'T2', setup=thigh_setup('T2'))
    study('shin', 'S1', setup=shin_setup)

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
        wall_face = plane_at(1, yw[0])                       # the flange is bolted flat to the chassis wall: clamped there
        st.fix(lambda f: (f.kind == 'Cylinder' and yw[0] - 0.5 <= f.bbox[1] and f.bbox[4] <= yw[1] + 0.5 and (f.bbox[3] - f.bbox[0]) < 8) or wall_face(f))
        drops = lambda f: f.kind == 'Cylinder' and f.bbox[1] > yw[1] + 20 and (f.bbox[3] - f.bbox[0]) < 6.5
        st.force(drops, (0, -abs(leg_f[1]), leg_f[2]))
        yc = (S.y['hip_tab'][0] + S.y['knee_tab'][1]) / 2
        st.torque(drops, (0, yc, 0), (1, 0, 0), M_out, probe=False)
        st.torque(drops, (0, yc, 0), (0, 1, 0), T_mot, probe=False)

    study('output_adapter', 'A1', setup=adapter_setup)
    study('motor_plate', 'P1', setup=plate_setup)
    study('yoke_bracket', 'Y1', setup=yoke_setup)

    # --- falls: the same parts under the fall scenarios' loads (no floor), against the lower fall target
    fall_loads = worst_link_loads(design.stem, falls=True)
    normal_results = list(results)
    fall_results = []
    if fall_loads.get('shin_l') and fall_loads.get('thigh_l') and fall_loads.get('wheel_l'):
        C_normal = C
        C = cases(fall_loads, L, S, cr, mass, floor=False, motor_cap_nm=cap)
        leg_f = C['S1']['force']
        M_out = abs(C['T2']['moments']['x']) + abs(C['T2']['force'][1]) * a / 1000.0
        T_mot = abs(fall_loads['shin_l']['force']['moment_with_force_body'][1])
        C['Y1'] = {'from': f"falls: the whole leg, {leg_f[2]:.0f} N up, {abs(leg_f[1]):.0f} N sideways, {M_out:.0f} N·m out of plane"}
        n0 = len(results)
        C = {**C, **{k + '-fall': v for k, v in C.items()}}
        study('thigh', 'T1', setup=thigh_setup('T1'), tag='-fall')
        study('thigh', 'T2', setup=thigh_setup('T2'), tag='-fall')
        study('shin', 'S1', setup=shin_setup, tag='-fall')
        study('yoke_bracket', 'Y1', setup=yoke_setup, tag='-fall')
        fall_results = results[n0:]
        for r in fall_results:
            r['case'] += '-fall'
        results[:] = normal_results
        C = {**C_normal, **{k: v for k, v in C.items() if k.endswith('-fall')}}

    if only:                                                   # a quick look at some parts: no summary, no verdict
        return {'results': results + fall_results}
    # leg deflection at the wheel: thigh tip (worst case) carried down the shin, plus the shin's own
    summary = {'design': str(design.relative_to(R)), 'mesh_mm': mesh, 'cases': C, 'stack_mm': S.y, 'track_mm': S.track,
               'stack_notes': S.notes, 'assumed_interfaces': assumed, 'results': results,
               'targets': TARGETS}
    summary['results'] = results + fall_results
    by = {(r['part'], r['case']): r for r in results}
    dt = max(math.hypot(*by[('thigh', c)]['probe_displacement_mm']) for c in ('T1', 'T2'))
    ds = math.hypot(*by[('shin', 'S1')]['probe_displacement_mm'])
    # the thigh tip's slope also swings the shin: approximate by the tip deflection scaled by (a + b) / a
    total = dt * (a + b) / a + ds
    sf = min(r['safety_factor'] for r in results)
    sf_fall = min((r['safety_factor'] for r in fall_results), default=None)
    weakest = min(results + fall_results, key=lambda r: r['safety_factor'] / (TARGETS['sf_fall'] if r['case'].endswith('fall') else TARGETS['sf']))
    verdict = {'all': {'wheel_deflection_mm': round(total, 2), 'min_safety_factor': sf, 'min_safety_factor_fall': sf_fall,
                       'weakest': f"{weakest['part']} {weakest['case']}",
                       'ok': total <= TARGETS['wheel_deflection_mm'] and sf >= TARGETS['sf'] and (sf_fall is None or sf_fall >= TARGETS['sf_fall'])}}
    # the push-rod (bought tube and rod ends): Euler buckling, pinned both ends, and the rod ends' static rating
    pr = gmi.STD['PR']
    E = 200000.0                                                # steel threaded rod (the root diameter carries it)
    I = math.pi * pr['rod_root_d'] ** 4 / 64 if pr.get('rod_root_d') else math.pi * (pr['tube_od'] ** 4 - pr['tube_id'] ** 4) / 64
    P = C['T1']['rod_force_n']
    P_cr = math.pi ** 2 * E * I / (a ** 2)
    rod_end_static = {6: 4600.0, 8: 7800.0, 10: 11200.0}.get(int(pr['rod_end_eye_d']), 4000.0)   # igus KBRM-xx static radial (approx.)
    summary['rod'] = {'force_n': round(P), 'buckling_n': round(P_cr), 'buckling_sf': round(P_cr / P, 1), 'rod_end_static_n': rod_end_static,
                      'rod_end_sf': round(rod_end_static / P, 1), 'sin_phi_min': round(C['T1']['sin_phi'], 3)}
    summary['output_joint'] = output_joint(S.hip, d)
    # what the knee's hard stop must take: the knee torque beyond the motor's cap, in any scenario (a fall with the
    # motors off folds the leg onto it); the stop is not designed yet: docs/cad-plan.md
    stops = [v.get('knee_stop_nm', 0.0) for v in C.values() if isinstance(v, dict) and 'knee_stop_nm' in v]
    summary['knee_stop'] = {'torque_nm': round(max(stops, default=0.0), 1), 'designed': False,
                            'note': 'the knee torque beyond the motor cap ends on the knee hard stop; size a stop (and a TPU bumper) for it'}
    verdict['all']['joint_ok'] = summary['output_joint']['sf'] >= TARGETS['sf']
    verdict['all']['rod_ok'] = P_cr / P >= 3 and rod_end_static / P >= 2
    verdict['all']['ok'] = verdict['all']['ok'] and verdict['all']['rod_ok'] and verdict['all']['joint_ok']
    summary['verdict'] = verdict
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o)) + '\n')
    print('verdict', json.dumps(verdict))
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?', default=str(R / 'designs/default.json'))
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--no-anim', action='store_true', help='skip the overload videos (the optimiser)')
    ap.add_argument('--only', nargs='+', help='study only these parts (a quick look; the summary is then partial)')
    a = ap.parse_args()
    run(Path(a.design).resolve(), a.mesh, anim=not a.no_anim, only=a.only)
