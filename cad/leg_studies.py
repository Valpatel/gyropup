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
TARGETS = {'sf': 2.0, 'sf_rare': 1.2,
           'sf_fault': 1.0,                             # a fault (an uncontrolled power cut while standing): nothing may
                                                        # break; inspect the knees after one (D39)
           'bearing_s0': 2.0, 'bearing_s0_rare': 1.0}   # rolling bearings: static safety s0 = C0 / P0 (SKF: >= 1 with normal
                                                        # demands on running; a rare overload may use it, everyday ones not)
ROBOT_KG = 29.5                      # the robot (docs/body-plan.md's budget with its real parts); the rig carries half
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
    h_land = land['pose_at_peak_axle_force']['L_mm']
    # a landing's spike on the axle is mostly taken by the links' and the body's inertia: the knees' real peak force
    # (the rig, every step; the capped jump's landing is the worst of the landings) is what the parts above the wheel
    # link see. R1's axle force is the one whose statics gives that knee force at the landing pose; the wheel link,
    # which the full spike does load, is checked at the full axle force too (cases()['R1w']).
    knee_dyn = max(max(rig[n].get('peak_joint_force_n', {}).get(k, 0.0) for k in ('knee_f', 'knee_r')) for n in ('drop_150', 'jump'))
    Fz_full = land['peak_axle_force_n']
    ratio = land['peak_knee_pin_n'] / Fz_full                          # statics: knee force per axle force at that pose
    Fz = knee_dyn / ratio if knee_dyn else Fz_full
    static = ROBOT_KG / 2 * G
    off = rig['power_off']
    out = {
        'R1': {'title': 'landing', 'rare': True, 'h': h_land, 'Fw3': (0.10 * Fz, 0.10 * Fz, Fz),
               'gearbox_nm': max(rig[n].get('peak_gearbox_nm') or 0.0 for n in ('drop_150', 'jump')) or None,
               'from': f"the rig's landings (drop_150, the capped jump): knees at {knee_dyn:.0f} N, as {Fz:.0f} N on the axle at "
                       f"{h_land:.0f} mm (statics on the {Fz_full:.0f} N spike gives {Fz_full * ratio:.0f}), plus 10 % fore-aft and 10 % sideways"},
        'R1w': {'title': 'landing, the wheel link', 'rare': True, 'h': h_land, 'Fw3': (0.10 * Fz_full, 0.10 * Fz_full, Fz_full),
                'from': f"rig 'drop_150': the full {Fz_full:.0f} N axle spike on the wheel link, plus 10 % fore-aft and 10 % sideways"},
        'E1': {'title': 'turn', 'rare': False, 'h': 300.0, 'Fw3': (0.0, 0.5 * ROBOT_KG * G, 2.5 * static),
               'from': f"standing: 2.5 x {static:.0f} N vertical, 0.5 g of a {ROBOT_KG:.0f} kg robot sideways"},
    }
    for k, c in out.items():
        c['loads'] = loads_at(c['h'], c['Fw3'])
    out['R1w']['gearbox_nm'] = out['R1']['gearbox_nm']
    Fo = off['peak_axle_force_n']
    out['R3'] = {'title': 'collapse', 'rare': 'fault', 'stop_nm': off['peak_stop_nm'], 'h': max(102.0, off['L_range_mm'][0]),
                 'gearbox_nm': off.get('peak_gearbox_nm'),
                 'Fw3': (0.0, 0.10 * Fo, Fo),
                 'from': f"rig 'power_off' (no motor damping): folded onto the stops, {off['peak_stop_nm']:.0f} N m on a stop "
                         f"post and {Fo:.0f} N on the axle (quasi-static: the knees' real force matches statics), plus 10 % sideways"}
    out['R3']['loads'] = loads_at(out['R3']['h'], out['R3']['Fw3'])
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


def centroid(st, sel):
    """The area centroid (mm) of the faces a selector picks."""
    tags = set(st.select(sel))
    fs = [f for f in st.faces if f.tag in tags]
    return sum(f.center * f.area for f in fs) / sum(f.area for f in fs)


def couple(st, sel, M_nm, probe=False):
    """A pure moment (N m, a vector in the part's axes) carried by the selected faces. cadagent's torque() turns the
    faces about an axis through the point it is given: about any point but their centroid that adds a net force (a
    knee bore 7 mm off its centre added ~7 kN at the full knee moment), so the point here is always the centroid."""
    G = centroid(st, sel)
    for i in range(3):
        if abs(M_nm[i]) > 0.05:
            e = [0.0, 0.0, 0.0]
            e[i] = 1.0
            st.torque(sel, tuple(G), tuple(e), float(M_nm[i]), probe=probe)


def force_at(st, sel, F_n, P_mm, probe=True):
    """A force (N) whose line of action passes through P (mm), carried by the selected faces: spread evenly over them,
    plus the couple of its offset from their centroid (a knee pin carries its lower link's force from the boss's
    mid-plane to the upper link's eye: 36 mm of lever)."""
    G = centroid(st, sel)
    st.force(sel, tuple(float(v) for v in F_n), probe=probe)
    couple(st, sel, np.cross(np.asarray(P_mm, float) - G, np.asarray(F_n, float)) / 1000.0)


SHARE_MARGIN = 0.15          # each chain is checked at its measured share of the out-of-plane load plus this (the bonded
                             # whole-leg model leaves out the joints' play and the pins' bending)
SHARE_DEFAULT = {'rear': 0.75, 'front': 0.40, 'measured': None}   # until a whole-leg run has measured it


def apex_y():
    """The apex bearings' centre plane: where the lower links pass forces to each other."""
    return (fb.Y['apex_bearing_in'][0] + fb.Y['apex_bearing'][1]) / 2


def chain_moments(c, s):
    """Out-of-plane moments (N m, world x and z) when the rear chain (wheel link, rear upper link) takes the share s of
    the wheel's out-of-plane load and the front chain the rest through the apex's 61812s: what the rear knee pin (about
    D) and the front knee pin (about C) carry, and the ground's own about the apex bearings' centre H. The lower links
    pass their in-plane forces at H while the knees react them at the bosses' mid-plane: that offset is in D and C."""
    ld = c['loads']
    j = ld['j']
    yk, yh = sum(fb.Y['knee_boss']) / 2, apex_y()
    E, Cj, D = (np.array(j[k]) for k in 'ECD')
    W3 = np.array([E[0], fb.Y['wheel'], E[1]])
    P3 = np.array([E[0], fb.Y['wheel'], E[1] - WHEEL_R * 1000])
    H3, C3, D3 = np.array([E[0], yh, E[1]]), np.array([Cj[0], yk, Cj[1]]), np.array([D[0], yk, D[1]])
    F3 = np.array(c['Fw3'], float)
    Fin, Fside = np.array([F3[0], 0.0, F3[2]]), np.array([0.0, F3[1], 0.0])
    fu = np.array([ld['fu'][0], 0.0, ld['fu'][1]])                         # the front link's in-plane force on the wheel link
    M_H = (np.cross(W3 - H3, Fin) + np.cross(P3 - H3, Fside)) / 1000.0
    M_H[1] = 0.0                                                          # its out-of-plane part
    off = -(1 - s) * Fside                                                # what the front chain takes off the wheel link at H
    M_D = (np.cross(W3 - D3, Fin) + np.cross(P3 - D3, Fside) + np.cross(H3 - D3, fu + off)) / 1000.0 - (1 - s) * M_H
    M_C = np.cross(H3 - C3, -fu - off) / 1000.0 + (1 - s) * M_H
    return {'D': (M_D[0], M_D[2]), 'C': (M_C[0], M_C[2]), 'H': (M_H[0], M_H[2])}


def hub_reactions(st, hubs):
    """The reactions (force N; moment N m about the hub's axis point at y = 0) at each fixed hub of a solved study:
    K u at the fixed dofs, the stiffness re-assembled once more. hubs: {name: x of its axis}."""
    from skfem import asm
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    lam, mu = lame_parameters(st.material.E_mpa, st.material.nu)
    Rf = asm(linear_elasticity(lam, mu), st._ib) @ st._u
    lookup = {tuple(sorted(f)): i for i, f in enumerate(st._m.facets.T)}
    xs = st._ib.doflocs
    out = {}
    for name, x0 in hubs.items():
        fac = []
        for tg in st.fixed:
            tris = st.face_tris[tg]
            if len(tris) and abs(st.points[tris].mean(axis=(0, 1))[0] - x0) < 60:
                fac += [lookup[tuple(sorted(t))] for t in tris if tuple(sorted(t)) in lookup]
        dofs = st._ib.get_dofs(facets=np.unique(np.asarray(fac, dtype=np.int64)))
        F, M = np.zeros(3), np.zeros(3)
        for kind in ('nodal', 'edge', 'facet', 'interior'):
            for key, d in getattr(dofs, kind, {}).items():                # 'u^1'.. 'u^3': the x, y, z components
                k = int(key.split('^')[1]) - 1
                e = np.zeros(3)
                e[k] = 1.0
                F[k] += Rf[d].sum()
                M += np.cross(xs[:, d].T - np.array([x0, 0.0, 0.0]), np.outer(Rf[d], e)).sum(axis=0)
        out[name] = (F, M / 1000.0)
    return out


def shares_from(rx):
    """The rear chain's share of the out-of-plane load from the hubs' reactions to it alone (the moments about x and z,
    and the sideways force), and each chain's design share: its measured share plus SHARE_MARGIN, at most 1."""
    (Ff, Mf), (Fr, Mr) = rx['front'], rx['rear']
    mf, mr = math.hypot(Mf[0], Mf[2]), math.hypot(Mr[0], Mr[2])
    s_m = mr / (mf + mr)
    s_f = abs(Fr[1]) / (abs(Ff[1]) + abs(Fr[1])) if abs(Ff[1]) + abs(Fr[1]) > 1.0 else s_m
    return {'measured': {'moment': round(s_m, 3), 'sideways_force': round(s_f, 3),
                         'hub_moments_nm': {'front': [round(v, 1) for v in Mf], 'rear': [round(v, 1) for v in Mr]},
                         'hub_forces_n': {'front': [round(v, 1) for v in Ff], 'rear': [round(v, 1) for v in Fr]}},
            'rear': round(min(1.0, max(s_m, s_f) + SHARE_MARGIN), 3),
            'front': round(min(1.0, 1.0 - min(s_m, s_f) + SHARE_MARGIN), 3)}


def members_only(st, j):
    """The whole-leg study's safety factor on the printed members: elements more than the joints' plug radius (+ 8 mm)
    from the knee and apex axes are judged; the plugs stand in for steel pins and bearings (checked by joint_checks)."""
    c = st.points[st.tets[:, :4]].mean(axis=1)
    keep = ~st._touches_bc
    for (x, z), r in ((j['C'], fb.KC['bearing_od'] / 2 + 8), (j['D'], fb.KC['bearing_od'] / 2 + 8), (j['E'], gmi.STD['AC-L']['bearing_od'] / 2 + 8)):
        keep &= np.hypot(c[:, 0] - x, c[:, 2] - z) > r
    vm = float(st.vm_elem[keep].max())
    return round(st.material.strength_mpa / vm, 2), round(vm, 2)


HUB_PRELOAD_N = 1200.0       # per M5 into the CNC adapter's tapped 6061, held by the printed link under its head: an
                             # estimate (PA6-CF under a Ø8.5 head creeps); the bench's torque-tension coupon replaces it
HUB_MU = 0.15                # printed PA6-CF on machined 6061, dry (low end, so friction is not overstated)
DOWEL_ENGAGED = 8.0          # mm of each Ø5 x 16 dowel in the link (and 8 pressed into the adapter's H7 holes)


PAD_RIM_BAND = 5.0           # mm: the upper link's design stress leaves out this band round the rim of its bonded contact
                             # pad (the adapter face's edge, r 30): a bond there pulls where the real bolted joint lifts,
                             # a spike that only grows with the mesh; the joint itself is joint_checks' hub_joint


def away_from_pad_rim(st, r_rim):
    """The upper link's safety factor on the elements away from its contact pad's rim (and from every clamp and load
    patch, as cadagent does): (sf, design MPa)."""
    c = st.points[st.tets[:, :4]].mean(axis=1)
    d = np.hypot(np.hypot(c[:, 0], c[:, 2]) - r_rim, c[:, 1])
    keep = ~st._touches_bc & (d > PAD_RIM_BAND)
    vm = float(st.vm_elem[keep].max())
    return round(st.material.strength_mpa / vm, 2), round(vm, 2)


def joint_checks(C, SH):
    """The joints the whole-leg study bonds, checked on their own in the rare case R1, each chain at its design share of
    the out-of-plane load (chain_moments): each knee's steel pin in bending where it leaves the upper link's eye, its
    6201s against their static rating, the eye's bearing pressure on its steel sleeve (linear along the sleeve); the
    apex 61812s; and each hub's bolted joint (8 x M5 into the adapter's tapped holes, 2 x Ø5 dowels on the Ø60 face):
    whether the screws' preload keeps it closed under its share of the hip's out-of-plane moment, and what the dowels
    carry once the torque beats friction (the landing's spike reaches the hubs through the rotors' inertia)."""
    out = {case: _joint_checks_case(C, SH, case) for case in ('R1', 'R3')}
    checks = []
    for case, r in out.items():
        rare = TARGETS['sf_fault'] if C[case]['rare'] == 'fault' else TARGETS['sf_rare']
        s0 = TARGETS['bearing_s0_rare']
        for joint, v in r.items():
            if joint.startswith('knee'):
                checks += [(case, joint, '6201 s0', v['6201']['sf'], s0), (case, joint, 'pin', v['pin']['sf'], rare),
                           (case, joint, 'eye pressure', v['eye_pressure']['sf'], rare)]
            elif joint == 'apex_61812':
                checks.append((case, joint, 's0', v['sf'], s0))
            elif joint.startswith('hub'):
                checks.append((case, joint, 'tipping', v['sf_tip'], rare))
                if v['sf_dowel'] is not None:
                    checks.append((case, joint, 'dowel bearing', v['sf_dowel'], rare))
    out['checks'] = [{'case': c, 'joint': j, 'check': k, 'sf': s, 'target': t, 'ok': s >= t} for c, j, k, s, t in checks]
    c, j, k, s, t = min(checks, key=lambda x: x[3] / x[4])
    out['worst'] = {'case': c, 'joint': j, 'check': k, 'sf': s, 'target': t}
    out['all_ok'] = all(s >= t for _, _, _, s, t in checks)
    return out


def _joint_checks_case(C, SH, case):
    """joint_checks() for one rare case."""
    c = C[case]
    ld = c['loads']
    sr, sf = SH[case]['rear'], SH[case]['front']
    kb0, kb1 = fb.Y['knee_boss']
    yk = (kb0 + kb1) / 2
    span = (kb1 - kb0) - fb.KC['bearing_w']                   # between the two 6201s' centres, mm
    t, L_sl, d_eye = fb.P['upper_t'], fb.EYE_SLEEVES * fb.EYE_SLEEVE[2], fb.EYE_SLEEVE[0]
    pin_z = math.pi * 12.0 ** 3 / 32                          # Ø12 shoulder, mm^3
    out = {'case': case, 'shares': {'rear': sr, 'front': sf}}
    for name, F2, s_rear, key in (('rear', ld['F_D_on_upper'], sr, 'D'), ('front', ld['F_C_on_upper'], 1.0 - sf, 'C')):
        F3 = np.array([F2[0], 0.0, F2[1]])
        M3 = np.array([chain_moments(c, s_rear)[key][0], 0.0, chain_moments(c, s_rear)[key][1]]) * 1000.0   # N mm, at the boss
        M_face = np.cross([0.0, yk - t, 0.0], F3) + M3                   # where the pin leaves the eye (its outer face)
        M_sleeve = np.cross([0.0, yk - (t - L_sl / 2), 0.0], F3) + M3     # at the sleeve's middle
        Fn = float(np.linalg.norm(F3))
        brg = math.hypot(Fn / 2, float(np.linalg.norm(M3)) / span)
        sig = float(np.linalg.norm(M_face)) / pin_z
        eye_p = (6 * float(np.linalg.norm(M_sleeve)) / L_sl ** 2 + Fn / L_sl) / d_eye
        out[f'knee_{name}'] = {
            'out_of_plane_share': round(s_rear if name == 'rear' else 1.0 - s_rear, 2), 'pin_force_n': round(Fn),
            'moment_at_boss_nm': round(float(np.linalg.norm(M3)) / 1000, 1), 'moment_at_sleeve_nm': round(float(np.linalg.norm(M_sleeve)) / 1000, 1),
            '6201': {'load_n': round(brg), 'C0_n': 3100, 'sf': round(3100 / brg, 2), 'target': TARGETS['bearing_s0_rare'], 'note': 's0 = C0 / P0'},
            'pin': {'stress_mpa': round(sig), 'yield_mpa': 1080, 'sf': round(1080 / sig, 2), 'note': 'ISO 7379 class 12.9, at the eye\'s face'},
            'eye_pressure': {'mpa': round(eye_p, 1), 'allowable_mpa': 40.0, 'sf': round(40.0 / eye_p, 2),
                             'note': f'PA6-CF, humid, sustained; linear along the Ø{d_eye:g} x {L_sl:g} steel sleeve'}}
    cm = chain_moments(c, 1.0 - sf)
    fu = float(np.linalg.norm(ld['fu']))
    apex = math.hypot(fu / 2, sf * math.hypot(*cm['H']) * 1000 / (fb.Y['apex_bearing'][0] - fb.Y['apex_bearing_in'][0]))
    out['apex_61812'] = {'load_n': round(apex), 'C0_n': 10200, 'sf': round(10200 / apex, 2), 'target': TARGETS['bearing_s0_rare'], 'note': 's0 = C0 / P0'}
    ao = gmi.STD['AO-L']
    n, Fp = ao['bolts'], HUB_PRELOAD_N
    r_o, r_i = ao['journal_d'] / 2, ao['spigot_d'] / 2                   # the clamped annulus, mm
    M_lift = n * Fp * (r_o ** 2 + r_i ** 2) / (4 * r_o) / 1000.0           # its far edge starts to lift (the annulus's kern)
    M_tip = n * Fp * r_o / 1000.0                                          # it tips about its edge
    T_fric = HUB_MU * n * Fp * (2 / 3) * (r_o ** 3 - r_i ** 3) / (r_o ** 2 - r_i ** 2) / 1000.0
    M_hip = math.hypot(*ld['M_B_out'])
    gb = c.get('gearbox_nm')                                               # the torque the rig measured through the gearbox
    for name, s, T in (('rear', sr, gb or abs(ld['tau'][1])), ('front', sf, gb or abs(ld['tau'][0]))):
        M = s * M_hip
        F_dw = max(0.0, T - T_fric) / (ao['pcd'] / 2 / 1000.0) / ao['dowels']
        p_dw = F_dw / (ao['dowel_d'] * DOWEL_ENGAGED)
        out[f'hub_{name}'] = {
            'out_of_plane_nm': round(M, 1), 'edge_lifts_at_nm': round(M_lift, 1), 'tips_at_nm': round(M_tip, 1), 'sf_tip': round(M_tip / M, 2),
            'torque_nm': round(T, 1), 'torque_from': 'rig: gearbox torque, every step' if gb else 'statics on the axle force',
            'friction_nm': round(T_fric, 1), 'dowel_force_n': round(F_dw),
            'dowel_bearing_mpa': round(p_dw, 1), 'allowable_mpa': 40.0, 'sf_dowel': round(40.0 / p_dw, 2) if p_dw > 0 else None,
            'assumes': f'{Fp:.0f} N preload per screw (estimate: bench torque-tension coupon), friction {HUB_MU}, {DOWEL_ENGAGED:g} mm of each dowel engaged'}
    return out


def run(mesh, anim=True, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    L = fb.leg_parts()
    C = cases()
    results = []

    def study(part, case, setup, rare, why, shape=None, record=True):
        if only and part not in only:
            return None
        t0 = time.time()
        mat = L.meta[part].get('fea_material') or 'pa6_cf_xy'
        st = Study(shape if shape is not None else L.parts[part], MATERIALS[mat], mesh_mm=mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        if not record:
            return st
        free = ~st._touches_bc                              # where the design stress is: the element it comes from
        i = int(np.argmax(np.where(free, st.vm_elem, -1.0)))
        r['design_peak_at_mm'] = [round(float(v), 1) for v in st._m.p[:, st._m.t[:, i]].mean(axis=1)]
        png = OUT / f'{part}-{case}.png'
        disp = r['probe_displacement_mm'] and round(math.hypot(*r['probe_displacement_mm']), 2)
        st.render(png, view=VIEWS.get(part, (25, -60)), title=f"{part} {case} ({MATERIALS[mat].name}): SF {r['safety_factor']}, {disp} mm at the load")
        if anim:
            r['animation'] = str(st.animate(OUT / f'{part}-{case}.mp4', view=VIEWS.get(part, (25, -60)), title=f'{part} {case}: {MATERIALS[mat].name}').relative_to(R))
            r['viewer'] = str(st.export_viewer(OUT / f'{part}-{case}.json').relative_to(R))
        target = TARGETS['sf_fault' if rare == 'fault' else 'sf_rare' if rare else 'sf']
        if part == 'leg':                                        # the printed members; the joints are joint_checks()
            r['safety_factor_with_joint_plugs'] = r['safety_factor']
            r['safety_factor'], r['von_mises_design_mpa'] = members_only(st, JOINTS[case])
        if part == 'upper_link' and shape is not None:           # held on its bonded pad: leave out the pad rim's spike
            r['safety_factor_with_pad_rim'] = r['safety_factor']
            r['safety_factor'], r['von_mises_design_mpa'] = away_from_pad_rim(st, gmi.STD['AO-L']['journal_d'] / 2)
        r.update(part=part, case=case, material_id=mat, load_from=why, png=str(png.relative_to(R)), target=target,
                 ok=r['safety_factor'] >= target, seconds=round(time.time() - t0, 1))
        results.append(r)
        print(f"  {part:14} {case:3} {mat:9} SF {r['safety_factor']:5} (>= {target})  {r['von_mises_design_mpa']} MPa  "
              f"{disp} mm  ({r['mesh']['tets']} tets, {r['seconds']} s)", flush=True)
        return st

    rad = lambda f, x=0.0, z=0.0: math.hypot(f.center[0] - x, f.center[2] - z)
    half = lambda f: max(f.bbox[3] - f.bbox[0], f.bbox[5] - f.bbox[2]) / 2
    l1, l2 = fb.P['l1'], fb.P['l2']
    ao = gmi.STD['AO-L']
    yk, yh = sum(fb.Y['knee_boss']) / 2, apex_y()

    # ---- 1. the whole leg, first; two solves per case. (a) The case's loads: the wheel's force at the axle, its
    # sideways grip at the contact patch; judged on the printed members (the joints are joint_checks()). (b) Their
    # out-of-plane part alone, taken at the apex bearings' centre H: the sideways grip and the couple of the in-plane
    # force's offset out to the wheel's mid-plane. The in-plane part goes round the five-bar by statics, this part by
    # stiffness, and the hubs' reactions to it alone say how the loop splits it between the rear chain (wheel link, rear
    # upper link) and the front chain (front link through the apex's 61812s, front upper link). Every single-part study
    # below carries its chain's measured share plus SHARE_MARGIN.
    SH = {}
    (ax_, _), (bx_, _) = fb.motors()
    for key in ('R1', 'E1', 'R3'):
        if only and 'leg' not in only:
            continue
        c = C[key]
        shape, j = whole_leg_shape(c['h'])
        E = j['E']
        hubfix = lambda f, ax_=ax_, bx_=bx_: f.kind == 'Cylinder' and f.center[1] < fb.P['upper_t'] and any(
            abs(math.hypot(f.center[0] - x, f.center[2]) - ao['pcd'] / 2) < 1.0 and half(f) < 4
            or math.hypot(f.center[0] - x, f.center[2]) < 0.5 and abs(half(f) - ao['spigot_d'] / 2) < 0.6 for x in (ax_, bx_))
        wseat = lambda f, E=E: math.hypot(f.center[0] - E[0], f.center[2] - E[1]) < 26 and f.center[1] > fb.Y['wheel_boss'] - 0.5 \
            and (f.kind == 'Plane' or abs(half(f) - 25.0) < 0.6)
        Fx, Fy, Fz = c['Fw3']
        W3 = (E[0], fb.Y['wheel'], E[1])                               # the axle at the wheel's mid-plane
        P3 = (E[0], fb.Y['wheel'], E[1] - WHEEL_R * 1000)              # the contact patch
        M_oop = np.cross(np.subtract(W3, (E[0], apex_y(), E[1])), (Fx, 0.0, Fz)) / 1000.0
        M_oop[1] = 0.0

        def setup(st, Fx=Fx, Fy=Fy, Fz=Fz, W3=W3, P3=P3):
            st.fix(hubfix)
            force_at(st, wseat, (Fx, 0.0, Fz), W3)
            force_at(st, wseat, (0.0, Fy, 0.0), P3, probe=False)

        def setup_oop(st, Fy=Fy, P3=P3, M_oop=M_oop):
            st.fix(hubfix)
            force_at(st, wseat, (0.0, Fy, 0.0), P3)
            couple(st, wseat, M_oop)
        L.parts['leg'] = shape
        L.meta['leg'] = {'fea_material': 'pa6_cf_xy'}
        VIEWS['leg'] = (20, -60)
        JOINTS[key] = j
        study('leg', key, setup, c['rare'], f"{c['from']}; the whole loop, joints bonded (the knees' 6201 pairs and the apex's 61812 pair carry moment)")
        st = study('leg', f'{key}-out-of-plane', setup_oop, c['rare'], 'the out-of-plane part alone', record=False)
        SH[key] = shares_from(hub_reactions(st, {'front': ax_, 'rear': bx_}))
        del st
        print(f"  share {key}: rear chain {SH[key]['measured']}, design rear {SH[key]['rear']} / front {SH[key]['front']}", flush=True)
    prev = json.loads((OUT / 'summary.json').read_text()).get('shares', {}) if (OUT / 'summary.json').exists() else {}
    for key in ('R1', 'E1', 'R3'):
        SH.setdefault(key, prev.get(key) or dict(SHARE_DEFAULT))

    # ---- the upper link (hub at the origin, along +x; the knee bore at (l1, 0)). Held where it really bears: its
    # inner face on the adapter's Ø60 face round the spigot, clamped there by the 8 x M5 (they pass with clearance, so
    # fixing the holes' walls only made spikes at their edges). The study adds a 0.5 mm pad of that contact (the same
    # holes through it) and fixes the pad's face: a bonded joint, which joint_checks' hub_joint shows stays closed.
    PAD_Y = -0.5
    pad = fb.ycyl(ao['journal_d'] / 2, PAD_Y, 0.01).cut(gmi.place(gmi.std_face_mate('L', depth=fb.P['upper_t'] + 2), (0, 0, 0), (0, 1, 0)))
    upper_padded = L.parts['upper_link'].union(pad).clean()
    hub_fix = lambda f: f.kind == 'Plane' and abs(f.center[1] - PAD_Y) < 0.05
    knee_bore = lambda f: f.kind == 'Cylinder' and rad(f, l1) < 0.5 and half(f) < fb.EYE_SLEEVE[0] / 2 + 0.5   # the sleeve's bore and the pin's
    for key in ('R1', 'E1', 'R3'):
        c = C[key]
        ld = c['loads']
        for link, F, a in (('rear', ld['F_D_on_upper'], ld['alpha']['upper_rear']), ('front', ld['F_C_on_upper'], ld['alpha']['upper_front'])):
            s = SH[key][link]                                    # its chain's design share of the out-of-plane load
            fx, fz = rot_in(a, F)
            fy = s * c['Fw3'][1]
            mx, mz = rot_in(a, chain_moments(c, s if link == 'rear' else 1.0 - s)['D' if link == 'rear' else 'C'])

            def setup(st, fx=fx, fy=fy, fz=fz, mx=mx, mz=mz):
                st.fix(hub_fix)
                force_at(st, knee_bore, (fx, fy, fz), (l1, yk, 0.0))     # the pin brings it from the knee boss's mid-plane
                couple(st, knee_bore, (mx, 0.0, mz))
            case = {'R3': 'R3K'}.get(key, key) + ('F' if link == 'front' else '')       # R3 itself is the stop's own case
            study('upper_link', case, setup, c['rare'],
                  f"{c['from']}; the {link} upper link at {math.degrees(a):.0f} deg, {s:.0%} of the out-of-plane load", shape=upper_padded)

    # R2 / E2: a motor at full torque / its cap against a stalled leg: the knee bore holds, the hub is twisted
    for key, T, rare in (('R2', PEAK, True), ('E2', CAP, False)):
        def setup(st, T=T):
            st.fix(knee_bore)
            st.torque(hub_fix, (0.0, 13.0, 0.0), (0, 1, 0), T)
        study('upper_link', key, setup, rare, f'a motor at {T:.0f} N m against a stalled leg', shape=upper_padded)

    # E3: the cap into a stop post: the post (r = stop_r) pushes the link's edge, the hub twists
    def stop_setup(T):
        def f(st):
            st.fix(hub_fix)
            edge = lambda f: f.kind == 'Plane' and f.center[2] > 10 and f.bbox[1] < 1.0 and f.bbox[4] > fb.P['upper_t'] - 1.0
            r_c = 0.5 * fb.P['l1']                                     # the edge face's middle, roughly half the link
            st.force(edge, (0.0, 0.0, -T / (r_c / 1000.0)))            # the same moment about the hub as the post's push
        return f
    study('upper_link', 'E3', stop_setup(CAP), False, f"a motor at its {CAP:.0f} N m cap driving the link into a stop post at {fb.P['stop_r']:.0f} mm",
          shape=upper_padded)
    study('upper_link', 'R3', stop_setup(C['R3']['stop_nm']), 'fault', C['R3']['from'], shape=upper_padded)

    # ---- the front lower link (knee at the origin, the apex seat at (l2, 0)): an axial strut, plus a lateral share
    knee_seats = lambda f: f.kind == 'Cylinder' and rad(f) < 0.5 and half(f) < fb.KC['bearing_od'] / 2 + 1
    apex_seat = lambda f: f.kind == 'Cylinder' and rad(f, l2) < 0.5 and 35 < half(f) < 40
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        a = ld['alpha']['front_link']
        s = SH[key]['front']
        fx, fz = rot_in(a, -ld['fu'])                                   # the wheel link pushes the front link back at E
        mx, mz = rot_in(a, chain_moments(c, 1.0 - s)['H'])

        def setup(st, fx=fx, fz=fz, fy=s * c['Fw3'][1], mx=mx, mz=mz, s=s):
            st.fix(knee_seats)
            force_at(st, apex_seat, (fx, fy, fz), (l2, yh, 0.0))         # through the apex's 61812s
            couple(st, apex_seat, (s * mx, 0.0, s * mz))
        study('front_link', key, setup, c['rare'], f"{c['from']}; axial {ld['front_axial']:.0f} N, {s:.0%} of the out-of-plane load at the apex")

    # ---- the wheel link (knee D at the origin, apex E at (l2, 0)): the wheel at its seat, the front link on the hub
    hub = lambda f: f.kind == 'Cylinder' and rad(f, l2) < 0.5 and abs(half(f) - 30.0) < 0.6
    seat = lambda f: rad(f, l2) < 26 and f.center[1] > fb.Y['wheel_boss'] - 0.5 and (f.kind == 'Plane' or abs(half(f) - 25.0) < 0.6)
    for key in ('R1', 'R1w', 'E1'):
        c = C[key]
        ld = c['loads']
        a = ld['alpha']['wheel_link']
        Fx, Fy, Fz = c['Fw3']
        wx, wz = rot_in(a, (Fx, Fz))
        ux, uz = rot_in(a, ld['fu'])
        s = SH['R1' if key == 'R1w' else key]['rear']                   # what the wheel link keeps of the out-of-plane load
        Pl = (l2 + rot_in(a, (0.0, -WHEEL_R * 1000))[0], fb.Y['wheel'], rot_in(a, (0.0, -WHEEL_R * 1000))[1])   # the contact patch
        mx, mz = rot_in(a, chain_moments(c, s)['H'])

        def setup(st, wx=wx, wz=wz, Fy=Fy, ux=ux, uz=uz, Pl=Pl, mx=mx, mz=mz, s=s):
            st.fix(knee_seats)
            force_at(st, seat, (wx, Fy, wz), Pl)                        # the ground, at the contact patch
            force_at(st, hub, (ux, -(1 - s) * Fy, uz), (l2, yh, 0.0), probe=False)   # the front link, at the apex bearings,
            couple(st, hub, (-(1 - s) * mx, 0.0, -(1 - s) * mz))                    # taking its share of the out-of-plane load
        study('wheel_link', key, setup, c['rare'], f"{c['from']}; the front link's {ld['front_axial']:.0f} N on the hub; it keeps {s:.0%} of the out-of-plane load")

    # ---- the hip frame: held on its flanges' end faces at the body's centre plane (the body, or the rig's carriage,
    # is bolted against them by 6 x M5 into the inserts; fixing the inserts' bores only made spikes at their edges);
    # each 61812 seat takes its upper link's pin force (and a share of the out-of-plane moment), the lug circles the
    # motors' reaction torques
    yc = fb.Y['centre_plane']
    flange_inserts = lambda f: f.kind == 'Plane' and abs(f.center[1] - yc) < 0.05
    (ax_, _), (bx_, _) = fb.motors()
    seat_at = lambda x: (lambda f: f.kind == 'Cylinder' and rad(f, x) < 0.5 and abs(half(f) - gmi.STD['AC-L']['bearing_od'] / 2) < 0.15)   # not the lead-in
    lugs_at = lambda x: (lambda f: f.kind == 'Cylinder' and abs(rad(f, x) - 53.0) < 1.0 and half(f) < 4.6)
    for key in ('R1', 'E1'):
        c = C[key]
        ld = c['loads']
        Ff, Fr = ld['F_C_on_upper'], ld['F_D_on_upper']
        Mx, Mz = ld['M_B_out']
        tf, tr = ld['tau']

        sr, sf = SH[key]['rear'], SH[key]['front']

        def setup(st, Ff=Ff, Fr=Fr, Mx=Mx, Mz=Mz, tf=tf, tr=tr, Fy=c['Fw3'][1], sr=sr, sf=sf):
            st.fix(flange_inserts)
            st.force(seat_at(ax_), (Ff[0], sf * Fy, Ff[1]))
            st.force(seat_at(bx_), (Fr[0], sr * Fy, Fr[1]), probe=False)
            for x_, share in ((bx_, sr), (ax_, sf)):                                # each chain's share of the moment
                couple(st, seat_at(x_), (share * Mx, 0.0, share * Mz))
            couple(st, lugs_at(ax_), (0.0, tf, 0.0))                                 # the motors' reactions on their lugs
            couple(st, lugs_at(bx_), (0.0, tr, 0.0))
        study('hip_frame', key, setup, c['rare'], f"{c['from']}; both upper links' pin forces, the out-of-plane moment {sr:.0%} rear / {sf:.0%} front")

    # ---- the output adapter (CNC 6061-T6, D46; the leg's frame, its axis along y): clamped where it sits on the motor,
    # its contact face on the output flange and the motor's three pins in their sockets (the screws pass in clearance
    # holes); loaded at the standard face's tapped holes and dowels. Its 61812 is left out: all of the hip's bending
    # goes through the adapter to the motor (conservative)
    ld = C['R1']['loads']
    M_out = max(SH['R1']['rear'], SH['R1']['front']) * math.hypot(*ld['M_B_out'])   # the more loaded hub's share at the hip
    Frad = max(float(np.linalg.norm(ld['F_D_on_upper'])), float(np.linalg.norm(ld['F_C_on_upper'])))
    T_R1 = C['R1'].get('gearbox_nm') or PEAK                # a landing's torque through the hub: what the rig measured
    face_bolts = lambda f: f.kind == 'Cylinder' and 22 < math.hypot(f.center[0], f.center[2]) < 28 and f.center[1] > -16
    pins = gmi.motor_interface(fb.MOTOR)['output']['dowels']
    motor_seat = lambda f: ((f.kind == 'Plane' and abs(f.center[1] - fb.Y['motor_out']) < 0.05)
                            or (f.kind == 'Cylinder' and abs(math.hypot(f.center[0], f.center[2]) - pins['pcd'] / 2) < 0.5
                                and abs(half(f) - pins['d'] / 2) < 0.1 and f.bbox[4] < fb.Y['motor_out'] + 5))
    for key, T, rare, M in (('R1', T_R1, True, M_out), ('R2', PEAK, True, 0.0), ('E1', CAP, False, M_out * 0.25)):
        def setup(st, T=T, M=M):                            # R2: a motor at its full torque against a stalled leg (a fault)
            st.fix(motor_seat)
            st.torque(face_bolts, (0.0, 0.0, 0.0), (0, 1, 0), T)
            if M:
                couple(st, face_bolts, (M, 0.0, 0.0))
            if M:
                st.force(face_bolts, (0.0, 0.0, Frad if rare else Frad * 0.25), probe=False)
        study('output_adapter', key, setup, rare, f"motor torque {T:.0f} N m" + (f" with an out-of-plane moment of {M:.0f} N m and {Frad:.0f} N radial"
                                                                                    if M else ' against a stalled leg (a fault)'))

    # ---- the front lower link as a strut: Euler buckling, pinned both ends, about its weak axis
    E_mod = MATERIALS['pa6_cf_xy'].E_mpa if hasattr(MATERIALS['pa6_cf_xy'], 'E_mpa') else 3000.0
    t, w = fb.P['front_t'], fb.P['front_w']
    I = min(w * t ** 3, t * w ** 3) / 12
    P_cr = math.pi ** 2 * E_mod * I / l2 ** 2
    buckling = {'P_cr_n': round(P_cr), 'R1_compression_n': round(C['R1']['loads']['front_axial']), 'sf': round(P_cr / max(1.0, C['R1']['loads']['front_axial']), 2),
                'note': f'{w:.0f} x {t:.0f} mm section, E {E_mod:.0f} MPa, pinned ends, {l2:.0f} mm'}
    joints = joint_checks(C, SH)
    print('joints', joints)
    summary = {'cases': {k: {kk: (vv if not isinstance(vv, np.ndarray) else vv.tolist()) for kk, vv in v.items() if kk != 'loads'} for k, v in C.items()},
               'targets': TARGETS, 'mesh_mm': mesh, 'results': results, 'front_link_buckling': buckling, 'joints': joints, 'shares': SH,
               'verdict': {'min_sf_everyday': min((r['safety_factor'] for r in results if not r['case'].startswith('R')), default=None),
                           'min_sf_rare': min((r['safety_factor'] for r in results if r['case'].startswith('R') and r['target'] == TARGETS['sf_rare']), default=None),
                           'min_sf_fault': min((r['safety_factor'] for r in results if r['target'] == TARGETS['sf_fault']), default=None),
                           'all_ok': all(r['ok'] for r in results) and P_cr / max(1.0, C['R1']['loads']['front_axial']) >= 3.0 and joints['all_ok'],
                           'joints_worst': joints['worst'],
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
