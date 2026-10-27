"""Strength of leg v2's printed parts (cadagent.fea) under the single-leg rig's loads (sim/leg_rig.py).

    .venv/bin/python cad/leg_studies.py [--mesh 4] [--no-anim] [--only upper_link wheel_link]

The rig gives the wheel's ground force at its worst moments; the five-bar's statics (sim.leg_rig.pin_forces) turn a
ground force into the force in every joint, so each part is loaded at its own pins at the same instant. Out of the
leg's plane (a lateral grip, the wheel's offset) the whole moment is sent down the wheel link's side of the loop: the
front lower link's apex bearing would share some of it, so this is conservative for the wheel link and rear upper
link and a little optimistic for nothing.

The rig's forces are the axle's (MuJoCo's joint force on the wheel), not the ground's: in a landing much of the
ground's spike only stops the wheel itself. A sideways grip acts at the tyre's contact patch; the vertical load at the
wheel's mid-plane, outboard of the links: those two make the leg's out-of-plane moment.

Cases. Rare events (safety factor >= 1.2, humid printed allowables):
  R1 landing   dropped from 150 mm (rig drop_150; jumps are held to the same touchdown speed in firmware), crooked:
               +10 % fore-aft and 10 % sideways
  R2 fault     a motor at its full 120 N m (the firmware cap failed) against a stalled leg
  R3 collapse  power lost while standing, no motor damping: the upper link lands on its stop post (rig power_off)
Everyday (safety factor >= 2):
  E1 turn      standing at 300 mm, 2.5 x the static wheel load, 0.5 g of the whole robot sideways at the tyre
  E2 cap       a motor at its 60 N m cap against a stalled leg
  E3 stop      a motor at its cap driving its link into the stop post
Writes exports/leg/fea/<part>-<case>.png (+ .mp4 overload video and .json for the interactive viewer) and summary.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))
import fivebar as fb  # noqa: E402
import gmi  # noqa: E402
from cadagent.fea import MATERIALS, Study  # noqa: E402
from sim.leg_rig import WHEEL_R, pin_forces  # noqa: E402

OUT = R / 'exports' / 'leg' / 'fea'
TARGETS = {'sf': 2.0, 'sf_rare': 1.2}
ROBOT_KG = 22.0                      # the condensed robot (the rig carries half)
G = 9.81
CAP, PEAK = 60.0, 120.0


def rot_in(alpha, v):
    """A world (x, z) vector in a link's frame whose +x points at angle alpha."""
    x, z = v
    return (x * math.cos(alpha) + z * math.sin(alpha), -x * math.sin(alpha) + z * math.cos(alpha))


def loads_at(h_mm, Fw3, lean=0.0):
    """Every joint's load for a wheel force Fw3 = (Fx, Fy, Fz) at a stance: Fx, Fz on the axle, Fy (sideways grip) at
    the tyre's contact patch. World vectors, N and N m."""
    phi = fb.stance(h_mm, lean)
    j = fb.fk(*phi)
    pf = pin_forces(*phi, (Fw3[0], Fw3[2]), at_axle=True)
    A, B, C, D, E = (np.array(j[k]) for k in 'ABCDE')
    ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
    yk = sum(fb.Y['knee_boss']) / 2
    W3 = np.array([E[0], fb.Y['wheel'], E[1]])                             # the axle at the wheel's mid-plane (mm)
    P3 = np.array([E[0], fb.Y['wheel'], E[1] - WHEEL_R * 1000])            # the contact patch
    D3 = np.array([D[0], yk, D[1]])
    E3 = np.array([E[0], yk, E[1]])
    F3 = np.array(Fw3, float)
    Fin, Fside = np.array([F3[0], 0.0, F3[2]]), np.array([0.0, F3[1], 0.0])
    fu = np.array([pf['knee_front_n'][0], 0.0, pf['knee_front_n'][1]])
    M_D = (np.cross(W3 - D3, Fin) + np.cross(P3 - D3, Fside) + np.cross(E3 - D3, fu)) / 1000.0   # about the rear knee, N m
    B3 = np.array([B[0], sum(fb.Y['bearing']) / 2, B[1]])
    M_B = (np.cross(W3 - B3, Fin) + np.cross(P3 - B3, Fside)) / 1000.0    # the wheel's force about the rear motor's bearing
    return {'phi': phi, 'j': j, 'front_axial': pf['front_axial_n'], 'F_C_on_upper': -np.array(pf['knee_front_n']),
            'F_D_on_upper': -np.array(pf['knee_rear_n']), 'F_D_on_wheel_link': np.array(pf['knee_rear_n']),
            'fu': np.array(pf['knee_front_n']), 'Fw3': F3, 'M_D_out': (M_D[0], M_D[2]), 'M_B_out': (M_B[0], M_B[2]), 'tau': (pf['tau_front'], pf['tau_rear']),
            'alpha': {'upper_front': ang(A, C), 'upper_rear': ang(B, D), 'front_link': ang(C, E), 'wheel_link': ang(D, E)}}


def cases():
    rig = json.loads((R / 'exports/leg/rig-results.json').read_text())['scenarios']
    land = rig['drop_150']
    Fz = land['peak_axle_force_n']
    h_land = land['pose_at_peak_axle_force']['L_mm']
    static = ROBOT_KG / 2 * G
    off = rig['power_off']
    out = {
        'R1': {'title': 'landing', 'rare': True, 'h': h_land, 'Fw3': (0.10 * Fz, 0.10 * Fz, Fz),
               'from': f"rig 'drop_150': {Fz:.0f} N on the axle at {h_land:.0f} mm, plus 10 % fore-aft and 10 % sideways"},
        'E1': {'title': 'turn', 'rare': False, 'h': 300.0, 'Fw3': (0.0, 0.5 * ROBOT_KG * G, 2.5 * static),
               'from': f"standing: 2.5 x {static:.0f} N vertical, 0.5 g of a {ROBOT_KG:.0f} kg robot sideways"},
    }
    for k, c in out.items():
        c['loads'] = loads_at(c['h'], c['Fw3'])
    out['R3'] = {'title': 'collapse', 'rare': True, 'stop_nm': off['peak_stop_nm'],
                 'from': f"rig 'power_off' (no motor damping): {off['peak_stop_nm']:.0f} N m on a stop post"}
    return out


VIEWS = {'upper_link': (20, -115), 'front_link': (20, -115), 'wheel_link': (20, -115), 'hip_frame': (25, -60), 'output_adapter': (25, -60)}


def whole_leg_shape(h_mm, lean=0.0):
    """The four links at a stance, fused into one solid by plugs standing in for the bearing stacks (the knees' two
    6201s and the apex's two 61812s carry moment, so bonding them is close; the joints' own stresses are not this
    model's job). In the module frame; also returns the joint points."""
    phi = fb.stance(h_mm, lean)
    fr, j = fb.link_frames(*phi)
    L = fb.leg_parts()
    s = fb.place(L.parts['upper_link'], *fr['upper_front'])
    for name, key in (('upper_link', 'upper_rear'), ('front_link', 'front_link'), ('wheel_link', 'wheel_link')):
        s = s.union(fb.place(L.parts[name], *fr[key]))
    kb1 = fb.Y['knee_boss'][1]
    # plugs a little bigger than the bearing seats and ending inside the parts: no coincident faces for the mesher
    for p in (j['C'], j['D']):
        s = s.union(fb.ycyl(fb.KC['bearing_od'] / 2 + 0.6, 0.6, kb1 - 0.6, *p))
    s = s.union(fb.ycyl(gmi.STD['AC-L']['bearing_od'] / 2 + 0.6, fb.Y['apex_eye'][0] + 0.6, fb.Y['wheel_link'][0] + 2.0, *j['E']))
    return s.clean(), j


JOINTS = {}                  # the whole-leg study's joint points per case


def members_only(st, j):
    """The whole-leg study's safety factor on the printed members: elements more than the joints' plug radius (+ 8 mm)
    from the knee and apex axes are judged; the plugs stand in for steel pins and bearings (checked by joint_checks)."""
    c = st.points[st.tets[:, :4]].mean(axis=1)
    keep = ~st._touches_bc
    for (x, z), r in ((j['C'], fb.KC['bearing_od'] / 2 + 8), (j['D'], fb.KC['bearing_od'] / 2 + 8), (j['E'], gmi.STD['AC-L']['bearing_od'] / 2 + 8)):
        keep &= np.hypot(c[:, 0] - x, c[:, 2] - z) > r
    vm = float(st.vm_elem[keep].max())
    return round(st.material.strength_mpa / vm, 2), round(vm, 2)


def joint_checks(C):
    """The joints the whole-leg study bonds, checked on their own (rare case R1, the out-of-plane moment shared by the
    two sides of the loop): the knee's steel pin in bending, the 6201s against their static rating, the printed eye's
    bearing pressure on the pin, the apex 61812s."""
    ld = C['R1']['loads']
    M = math.hypot(*ld['M_D_out']) / 2                       # each knee's share of the out-of-plane moment, N m
    F = max(np.linalg.norm(ld['F_D_on_upper']), np.linalg.norm(ld['F_C_on_upper']))
    kb0, kb1 = fb.Y['knee_boss']
    span = (kb1 - kb0) - fb.KC['bearing_w']                   # between the two 6201s' centres, mm
    brg = math.hypot(F / 2, M / (span / 1000))                # the more loaded 6201, N
    pin_z = math.pi * 12.0 ** 3 / 32                          # Ø12 shoulder, mm^3
    pin_sigma = (M * 1000 + F * (fb.P['upper_t'] / 2 + 2)) / pin_z
    t = fb.P['upper_t']
    d_eye = fb.EYE_SLEEVE[0]                                  # the steel sleeve in the eye spreads the pin's load
    eye_p = (6 * M * 1000 / t ** 2 + F / t) / d_eye            # peak bearing pressure on the printed eye (linear), MPa
    apex = math.hypot(F / 2, M * 2 / ((fb.Y['apex_bearing'][0] - fb.Y['apex_bearing_in'][0]) / 1000))
    return {'case': 'R1', 'out_of_plane_nm_per_knee': round(M, 1), 'knee_pin_force_n': round(F),
            'knee_6201': {'load_n': round(brg), 'C0_n': 3100, 'sf': round(3100 / brg, 2)},
            'knee_pin': {'stress_mpa': round(pin_sigma), 'yield_mpa': 1080, 'sf': round(1080 / pin_sigma, 2), 'note': 'ISO 7379 class 12.9'},
            'upper_eye_pressure': {'mpa': round(eye_p, 1), 'allowable_mpa': 40.0, 'sf': round(40.0 / eye_p, 2),
                                   'note': f'PA6-CF, humid, sustained; through a Ø{d_eye:g} steel sleeve'},
            'apex_61812': {'load_n': round(apex), 'C0_n': 10200, 'sf': round(10200 / apex, 2)}}


def run(mesh, anim=True, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    L = fb.leg_parts()
    C = cases()
    results = []

    def study(part, case, setup, rare, why):
        if only and part not in only:
            return
        t0 = time.time()
        mat = L.meta[part].get('fea_material') or 'pa6_cf_xy'
        st = Study(L.parts[part], MATERIALS[mat], mesh_mm=mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        png = OUT / f'{part}-{case}.png'
        disp = r['probe_displacement_mm'] and round(math.hypot(*r['probe_displacement_mm']), 2)
        st.render(png, view=VIEWS.get(part, (25, -60)), title=f"{part} {case} ({MATERIALS[mat].name}): SF {r['safety_factor']}, {disp} mm at the load")
        if anim:
            r['animation'] = str(st.animate(OUT / f'{part}-{case}.mp4', view=VIEWS.get(part, (25, -60)), title=f'{part} {case}: {MATERIALS[mat].name}').relative_to(R))
            r['viewer'] = str(st.export_viewer(OUT / f'{part}-{case}.json').relative_to(R))
        target = TARGETS['sf_rare' if rare else 'sf']
        if part == 'leg':                                        # the printed members; the joints are joint_checks()
            r['safety_factor_with_joint_plugs'] = r['safety_factor']
            r['safety_factor'], r['von_mises_design_mpa'] = members_only(st, JOINTS[case])
        r.update(part=part, case=case, material_id=mat, load_from=why, png=str(png.relative_to(R)), target=target,
                 ok=r['safety_factor'] >= target, seconds=round(time.time() - t0, 1))
        results.append(r)
        print(f"  {part:14} {case:3} {mat:9} SF {r['safety_factor']:5} (>= {target})  {r['von_mises_design_mpa']} MPa  "
              f"{disp} mm  ({r['mesh']['tets']} tets, {r['seconds']} s)")

    rad = lambda f, x=0.0, z=0.0: math.hypot(f.center[0] - x, f.center[2] - z)
    half = lambda f: max(f.bbox[3] - f.bbox[0], f.bbox[5] - f.bbox[2]) / 2
    l1, l2 = fb.P['l1'], fb.P['l2']
    ao = gmi.STD['AO-L']

    # ---- the upper link (hub at the origin, along +x; the knee bore at (l1, 0)). Fixed where it is bolted to the AO.
    # the hub's whole interface with the adapter: the bolt and dowel holes, the spigot recess's wall and floor (in the
    # real joint the screws' preload carries the torque by friction: 8 x M5 hold ~250 N m; the holes alone overstate it)
    hub_fix = lambda f: (f.kind == 'Cylinder' and (abs(rad(f) - ao['pcd'] / 2) < 1.0 and half(f) < 4 or rad(f) < 0.5 and abs(half(f) - ao['spigot_d'] / 2) < 0.6)
                         or f.kind == 'Plane' and rad(f) < 1.0 and abs(f.center[1] - (ao['spigot_h'] + 0.3)) < 0.2)
    knee_bore = lambda f: f.kind == 'Cylinder' and rad(f, l1) < 0.5 and half(f) < 6.5
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        for link, F, a in (('front', ld['F_C_on_upper'], ld['alpha']['upper_front']), ('rear', ld['F_D_on_upper'], ld['alpha']['upper_rear'])):
            fx, fz = rot_in(a, F)
            fy = -c['Fw3'][1] if link == 'rear' else 0.0
            mx, mz = (-ld['M_D_out'][0], -ld['M_D_out'][1]) if link == 'rear' else (0.0, 0.0)
            mxl, mzl = rot_in(a, (mx, mz))

            def setup(st, fx=fx, fy=fy, fz=fz, mxl=mxl, mzl=mzl):
                st.fix(hub_fix)
                st.force(knee_bore, (fx, fy, fz))
                if abs(mxl) > 0.05:
                    st.torque(knee_bore, (l1, 13.0, 0.0), (1, 0, 0), mxl, probe=False)
                if abs(mzl) > 0.05:
                    st.torque(knee_bore, (l1, 13.0, 0.0), (0, 0, 1), mzl, probe=False)
            if link == 'rear':                                   # the rear link carries the out-of-plane share: the worse one
                study('upper_link', key, setup, c['rare'], f"{c['from']}; rear upper link at {math.degrees(a):.0f} deg")

    # R2 / E2: a motor at full torque / its cap against a stalled leg: the knee bore holds, the hub is twisted
    for key, T, rare in (('R2', PEAK, True), ('E2', CAP, False)):
        def setup(st, T=T):
            st.fix(knee_bore)
            st.torque(hub_fix, (0.0, 13.0, 0.0), (0, 1, 0), T)
        study('upper_link', key, setup, rare, f'a motor at {T:.0f} N m against a stalled leg')

    # E3: the cap into a stop post: the post (r = stop_r) pushes the link's edge, the hub twists
    def stop_setup(T):
        def f(st):
            st.fix(hub_fix)
            edge = lambda f: f.kind == 'Plane' and f.center[2] > 10 and f.bbox[1] < 1.0 and f.bbox[4] > fb.P['upper_t'] - 1.0
            r_c = 0.5 * fb.P['l1']                                     # the edge face's middle, roughly half the link
            st.force(edge, (0.0, 0.0, -T / (r_c / 1000.0)))            # the same moment about the hub as the post's push
        return f
    study('upper_link', 'E3', stop_setup(CAP), False, f"a motor at its {CAP:.0f} N m cap driving the link into a stop post at {fb.P['stop_r']:.0f} mm")
    study('upper_link', 'R3', stop_setup(C['R3']['stop_nm']), True, C['R3']['from'])

    # ---- the front lower link (knee at the origin, the apex seat at (l2, 0)): an axial strut, plus a lateral share
    knee_seats = lambda f: f.kind == 'Cylinder' and rad(f) < 0.5 and half(f) < fb.KC['bearing_od'] / 2 + 1
    apex_seat = lambda f: f.kind == 'Cylinder' and rad(f, l2) < 0.5 and 35 < half(f) < 40
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        fx, fz = rot_in(ld['alpha']['front_link'], -ld['fu'])           # the wheel link pushes the front link back at E

        def setup(st, fx=fx, fz=fz, fy=-c['Fw3'][1] / 2):
            st.fix(knee_seats)
            st.force(apex_seat, (fx, fy, fz))
        study('front_link', key, setup, c['rare'], f"{c['from']}; axial {ld['front_axial']:.0f} N, half the sideways force")

    # ---- the wheel link (knee D at the origin, apex E at (l2, 0)): the wheel at its seat, the front link on the hub
    hub = lambda f: f.kind == 'Cylinder' and rad(f, l2) < 0.5 and abs(half(f) - 30.0) < 0.6
    seat = lambda f: rad(f, l2) < 26 and f.center[1] > fb.Y['wheel_boss'] - 0.5 and (f.kind == 'Plane' or abs(half(f) - 25.0) < 0.6)
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        a = ld['alpha']['wheel_link']
        Fx, Fy, Fz = c['Fw3']
        wx, wz = rot_in(a, (Fx, Fz))
        ux, uz = rot_in(a, ld['fu'])
        # the ground force acts at the contact patch: its moment about the seat's centre is carried by the seat
        S3 = np.array([l2, fb.Y['wheel_boss'] + 2.6, 0.0])
        Pl = np.array([l2 + rot_in(a, (0.0, -WHEEL_R * 1000))[0], fb.Y['wheel'], rot_in(a, (0.0, -WHEEL_R * 1000))[1]])
        M = np.cross(Pl - S3, np.array([wx, Fy, wz])) / 1000.0

        def setup(st, wx=wx, wz=wz, Fy=Fy, ux=ux, uz=uz, M=M):
            st.fix(knee_seats)
            st.force(seat, (wx, Fy, wz))
            st.force(hub, (ux, 0.0, uz), probe=False)
            for i, ax in ((0, (1, 0, 0)), (1, (0, 1, 0)), (2, (0, 0, 1))):
                if abs(M[i]) > 0.05:
                    st.torque(seat, tuple(S3), ax, float(M[i]), probe=False)
        study('wheel_link', key, setup, c['rare'], f"{c['from']}; the front link's {ld['front_axial']:.0f} N on the hub")

    # ---- the hip frame: held by its six flange inserts (the body or the rig); each 61812 seat takes its upper link's
    # pin force (and the rear one the out-of-plane moment), the lug circles the motors' reaction torques
    yc = fb.Y['centre_plane']
    flange_inserts = lambda f: f.kind == 'Cylinder' and f.center[1] < yc + 12 and half(f) < 3.5
    (ax_, _), (bx_, _) = fb.motors()
    seat_at = lambda x: (lambda f: f.kind == 'Cylinder' and rad(f, x) < 0.5 and abs(half(f) - gmi.STD['AC-L']['bearing_od'] / 2) < 0.6)
    lugs_at = lambda x: (lambda f: f.kind == 'Cylinder' and abs(rad(f, x) - 53.0) < 1.0 and half(f) < 4.6)
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        Ff, Fr = ld['F_C_on_upper'], ld['F_D_on_upper']
        Mx, Mz = ld['M_B_out']
        tf, tr = ld['tau']

        def setup(st, Ff=Ff, Fr=Fr, Mx=Mx, Mz=Mz, tf=tf, tr=tr, Fy=c['Fw3'][1]):
            st.fix(flange_inserts)
            st.force(seat_at(ax_), (Ff[0], 0.0, Ff[1]))
            st.force(seat_at(bx_), (Fr[0], Fy, Fr[1]), probe=False)
            ym = sum(fb.Y['bearing']) / 2
            for x_, share in ((bx_, 0.6), (ax_, 0.4)):                              # the loop shares it (whole-leg study):
                st.torque(seat_at(x_), (x_, ym, 0.0), (1, 0, 0), share * Mx, probe=False)   # 60 % on the rear motor
                st.torque(seat_at(x_), (x_, ym, 0.0), (0, 0, 1), share * Mz, probe=False)
            st.torque(lugs_at(ax_), (ax_, ym, 0.0), (0, 1, 0), tf, probe=False)       # the motors' reactions on their lugs
            st.torque(lugs_at(bx_), (bx_, ym, 0.0), (0, 1, 0), tr, probe=False)
        study('hip_frame', key, setup, c['rare'], f"{c['from']}; both upper links' pin forces, the out-of-plane moment at the rear motor")

    # ---- the output adapter (motor frame: axis +y from the module's placement), as GMI's A1
    zf = -fb.Y['motor_out']
    ld = C['R1']['loads']
    M_out = math.hypot(*ld['M_D_out'])
    Frad = float(np.linalg.norm(ld['F_D_on_upper']))
    face_bolts = lambda f: f.kind == 'Cylinder' and 22 < math.hypot(f.center[0], f.center[2]) < 28 and f.center[1] > -12
    motor_holes = lambda f: f.kind == 'Cylinder' and abs(math.hypot(f.center[0], f.center[2]) - 18.0) < 2.5 and half(f) < 3.6
    for key, T, rare in (('R1', PEAK, True), ('E1', CAP, False)):
        def setup(st, T=T, rare=rare):
            st.fix(motor_holes)
            st.torque(face_bolts, (0.0, 0.0, 0.0), (0, 1, 0), T)
            st.torque(face_bolts, (0.0, 0.0, 0.0), (1, 0, 0), M_out if rare else M_out * 0.25, probe=False)
            st.force(face_bolts, (0.0, 0.0, Frad if rare else Frad * 0.25), probe=False)
        study('output_adapter', key, setup, rare, f"motor torque {T:.0f} N m with the R1 out-of-plane moment {M_out:.0f} N m and {Frad:.0f} N radial"
              + ('' if rare else ' (x 0.25)'))

    # ---- the whole leg (the loop shares the wheel's out-of-plane load): fixed on both hubs' bolt circles, the wheel's
    # force at its seat with its moment about the seat (the wheel's mid-plane and the contact patch are outboard)
    for key in ('R1', 'E1'):
        if only and 'leg' not in only:
            continue
        c = C[key]
        shape, j = whole_leg_shape(c['h'])
        E = j['E']
        (ax_, _), (bx_, _) = fb.motors()
        hubfix = lambda f, ax_=ax_, bx_=bx_: f.kind == 'Cylinder' and f.center[1] < fb.P['upper_t'] and any(
            abs(math.hypot(f.center[0] - x, f.center[2]) - ao['pcd'] / 2) < 1.0 and half(f) < 4
            or math.hypot(f.center[0] - x, f.center[2]) < 0.5 and abs(half(f) - ao['spigot_d'] / 2) < 0.6 for x in (ax_, bx_))
        wseat = lambda f, E=E: math.hypot(f.center[0] - E[0], f.center[2] - E[1]) < 26 and f.center[1] > fb.Y['wheel_boss'] - 0.5 \
            and (f.kind == 'Plane' or abs(half(f) - 25.0) < 0.6)
        Fx, Fy, Fz = c['Fw3']
        S3 = np.array([E[0], fb.Y['wheel_boss'] + 2.6, E[1]])
        Mw = (np.cross(np.array([E[0], fb.Y['wheel'], E[1]]) - S3, np.array([Fx, 0.0, Fz]))
              + np.cross(np.array([E[0], fb.Y['wheel'], E[1] - WHEEL_R * 1000]) - S3, np.array([0.0, Fy, 0.0]))) / 1000.0

        def setup(st, Fx=Fx, Fy=Fy, Fz=Fz, Mw=Mw, S3=S3):
            st.fix(hubfix)
            st.force(wseat, (Fx, Fy, Fz))
            for i, ax in ((0, (1, 0, 0)), (2, (0, 0, 1))):
                if abs(Mw[i]) > 0.05:
                    st.torque(wseat, tuple(S3), ax, float(Mw[i]), probe=False)
        L.parts['leg'] = shape
        L.meta['leg'] = {'fea_material': 'pa6_cf_xy'}
        VIEWS['leg'] = (20, -60)
        JOINTS[key] = j
        study('leg', key, setup, c['rare'], f"{c['from']}; the whole loop, joints bonded (the knees' 6201 pairs and the apex's 61812 pair carry moment)")

    # ---- the front lower link as a strut: Euler buckling, pinned both ends, about its weak axis
    E_mod = MATERIALS['pa6_cf_xy'].E_mpa if hasattr(MATERIALS['pa6_cf_xy'], 'E_mpa') else 3000.0
    t, w = fb.P['front_t'], fb.P['front_w']
    I = min(w * t ** 3, t * w ** 3) / 12
    P_cr = math.pi ** 2 * E_mod * I / l2 ** 2
    buckling = {'P_cr_n': round(P_cr), 'R1_compression_n': round(C['R1']['loads']['front_axial']), 'sf': round(P_cr / max(1.0, C['R1']['loads']['front_axial']), 2),
                'note': f'{w:.0f} x {t:.0f} mm section, E {E_mod:.0f} MPa, pinned ends, {l2:.0f} mm'}
    joints = joint_checks(C)
    print('joints', joints)
    summary = {'cases': {k: {kk: (vv if not isinstance(vv, np.ndarray) else vv.tolist()) for kk, vv in v.items() if kk != 'loads'} for k, v in C.items()},
               'targets': TARGETS, 'mesh_mm': mesh, 'results': results, 'front_link_buckling': buckling, 'joints': joints,
               'verdict': {'min_sf_everyday': min((r['safety_factor'] for r in results if not r['case'].startswith('R')), default=None),
                           'min_sf_rare': min((r['safety_factor'] for r in results if r['case'].startswith('R')), default=None),
                           'all_ok': all(r['ok'] for r in results) and P_cr / max(1.0, C['R1']['loads']['front_axial']) >= 3.0,
                           'weakest': min(results, key=lambda r: r['safety_factor'] / r['target'])['part'] + ' ' + min(results, key=lambda r: r['safety_factor'] / r['target'])['case'] if results else None}}
    if not only:
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=lambda o: list(o) if isinstance(o, (tuple, np.ndarray)) else str(o)) + '\n')
    print('buckling', buckling)
    print('verdict', summary['verdict'])
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--no-anim', action='store_true')
    ap.add_argument('--only', nargs='+')
    a = ap.parse_args()
    run(a.mesh, anim=not a.no_anim, only=a.only)
