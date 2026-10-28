"""Build the single-leg test rig (cad/rig_parts.py around leg v2): every made part as STEP (the printed ones also as
print-ready STL), the carriage plate's DXF and order sheet for SendCutSend, the assembled rig with the leg at four
poses (renders), the rig's parts list and print plan, and the checks of docs/leg-prototype-plan.md section 2.2.

    .venv/bin/python cad/build_rig.py [--no-render] [--no-sweep] [--no-sim]

Writes exports/rig/: <part>.step/.stl, rig_300.step (the assembly, bought parts as envelopes), rig-*.png,
print-plan.json, rig.json (masses, ballast, travel, clearances, block loads, post and brace, bumpers, the
harness slots, the controller's feed-forward masses), sendcutsend/carriage_plate.{dxf,step} + README.md.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cadquery as cq
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))
import fivebar as fb  # noqa: E402
import gmi  # noqa: E402
import printplan  # noqa: E402
import rig_parts as rp  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402

OUT = R / 'exports' / 'rig'
SCS = OUT / 'sendcutsend'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
DESIGN_KG = 14.75
STEEL = 7.85                          # g/cm3
AL6061 = 2.70

# ----------------------------------------------------------------------------------- the rig's layout (deck frame)

Z_FRAME_TOP = -rp.DECK_T
BASE_W = 700.0                        # x, outside the side members
Y_FRONT = 283.35                      # the base's front edge (the tyre's outer face is at y 127)
BRACE_RUN = 400.0                     # the brace's foot this far behind the post's back face
Y_REAR = rp.Y_POST_BACK - BRACE_RUN - 20.0
Z_BRACE = 668.0                       # the brace meets the post this high: its cut length is then 720 mm (a priced length)
HINGE = 25.0                          # each brace hinge holds the brace's end this far off the face it is on
RAIL_TOP = rp.RAIL_Z0 + rp.RAIL_LEN
Y_POST_C = (rp.Y_POST_FRONT + rp.Y_POST_BACK) / 2
POD_Z = 120.0                         # the pod's bottom above the deck, on the post's -x side
X_SIDE = BASE_W / 2 - 20.0
CROSS = {'front': Y_FRONT - 20.0, 'wheel': fb.Y['wheel'], 'bumper': rp.Y_POST_FRONT + 20.0, 'rear': Y_REAR + 20.0}


def zh_on_deck(L_mm: float, lean_deg: float = 0.0) -> float:
    """The hip axis above the deck when the wheel stands on it."""
    return rp.WHEEL_R + L_mm * math.cos(math.radians(lean_deg))


def base_members() -> dict:
    """{name: (kind, axis, length, at, flat)}: the base frame (members on the floor) and the post, the brace apart."""
    zc = Z_FRAME_TOP - 20.0
    inner = X_SIDE - 20.0
    m = {'side_left': ('4040', 'y', Y_FRONT - Y_REAR, (-X_SIDE, Y_REAR, zc), False),
         'side_right': ('4040', 'y', Y_FRONT - Y_REAR, (X_SIDE, Y_REAR, zc), False),
         'post_member': ('4080', 'x', 2 * inner, (-inner, Y_POST_C, zc), True)}
    for k, y in CROSS.items():
        m[f'{k}_member'] = ('4040', 'x', 2 * inner, (-inner, y, zc), False)
    m['post'] = ('8080', 'z', rp.POST_LEN, (0.0, Y_POST_C, Z_FRAME_TOP), False)
    return m


def brace_line():
    """The brace's centre line (y, z) ends: from the post's back face at Z_BRACE to the rear member's top."""
    p1 = (rp.Y_POST_BACK - HINGE, Z_BRACE)
    p2 = (CROSS['rear'], Z_FRAME_TOP + HINGE)
    return p1, p2


def brace():
    (y1, z1), (y2, z2) = brace_line()
    L = math.hypot(y1 - y2, z1 - z2) - 2 * 20.0                # the hinges take 20 mm of each end
    ang = math.degrees(math.atan2(z1 - z2, y1 - y2))           # above horizontal, rising towards the post (+y)
    b = rp.extrusion('4040', 'y', L, (0.0, -L / 2, 0.0))
    b = b.rotate((0, 0, 0), (1, 0, 0), ang).translate((0.0, (y1 + y2) / 2, (z1 + z2) / 2))
    hinges = rp.box(-20, 20, y1 - 20 + HINGE, y1 + HINGE, z1 - 20, z1 + 20).union(
        rp.box(-20, 20, y2 - 20, y2 + 20, Z_FRAME_TOP, Z_FRAME_TOP + 2 * HINGE - 10))
    return b, hinges, {'length_mm': round(L, 1), 'angle_deg': round(ang, 1), 'cut_length_mm': round(math.ceil(L / 5) * 5, 0)}


def deck():
    return rp.box(-300.0, 300.0, rp.Y_POST_FRONT, Y_FRONT, -rp.DECK_T, 0.0)


def rails():
    out = None
    for sx in (-1, 1):
        r = rp.box(sx * rp.BLOCK_X - rp.HG15['rail_w'] / 2, sx * rp.BLOCK_X + rp.HG15['rail_w'] / 2, rp.Y_POST_FRONT,
                   rp.Y_POST_FRONT + rp.HG15['rail_h'], rp.RAIL_Z0, RAIL_TOP)
        out = r if out is None else out.union(r)
    return out


def bumpers_fixed(with_bottom: bool = True):
    """The bottom bumpers (base, TPU, cap) on the deck and the top stop (bracket, TPU, caps) on the post."""
    b = rp.BUMPER
    out = {}
    if with_bottom:
        hb = rp.bumper_base_h()
        for sx, side in ((-1, 'left'), (1, 'right')):
            at = (sx * b['x'], b['y'], 0.0)
            out[f'bumper_base_{side}'] = rp.bumper_base().translate(at)
            out[f'bumper_tpu_{side}'] = rp.bumper_tpu().translate((at[0], at[1], hb))
            out[f'bumper_cap_{side}'] = rp.bumper_cap().translate((at[0], at[1], hb + b['tpu_h'] - b['skirt']))
    z_face = rp.top_stop_z(RAIL_TOP)                            # the TPU blocks' lower faces (where the plate's edge meets them)
    out['top_stop_bracket'] = rp.top_stop_bracket().translate((0.0, rp.Y_POST_FRONT, z_face - 2.0))
    for sx, side in ((-1, 'left'), (1, 'right')):
        cx = sx * b['x']
        tpu = rp.bumper_tpu().translate((cx, b['y'], z_face))
        out[f'top_tpu_{side}'] = tpu
    return out


def tof_fixed():
    """The ToF sensor's mount on the deck under the carriage's target."""
    return {'tof_mount': rp.tof_mount().translate((rp.TOF['x'], (rp.Y_PLATE_FRONT + rp.Y_PLATE_BACK) / 2 + 3.0, 0.0))}


def pod_parts():
    """The pod on the post's back face (turned so its depth runs to -y), its panel on the -x side, the pendant's clip."""
    turn = lambda s: s.rotate((0, 0, 0), (0, 0, 1), 90).translate((0.0, rp.Y_POST_BACK, POD_Z))
    return {'pod': turn(rp.pod()), 'pod_lid': turn(rp.pod_lid().translate((0, rp.POD['d'] / 2, 0))),
            'pendant_clip': rp.pendant_clip().rotate((0, 0, 0), (0, 0, 1), -90).translate((rp.POD['d'] / 2, rp.Y_POST_BACK - 70.0, POD_Z + 80.0))}


def fixed_parts(with_bottom_bumpers: bool = True) -> dict:
    out = {}
    for name, (kind, axis, L, at, flat) in base_members().items():
        out[name] = rp.extrusion(kind, axis, L, at, flat)
    b, h, _ = brace()
    out['brace'] = b
    out['brace_hinges'] = h
    out['deck'] = deck()
    out['rails'] = rails()
    out.update(bumpers_fixed(with_bottom_bumpers))
    out.update(pod_parts())
    out.update(tof_fixed())
    return out


def carriage_parts(zh: float, n_plates: int = 2, tof: bool = True) -> dict:
    """The parts that ride with the hip frame, at hip height zh (deck frame)."""
    t = (0.0, 0.0, zh)
    out = {'carriage_plate': rp.carriage_plate().translate(t), 'blocks': rp.blocks().translate(t),
           'ballast': rp.ballast(n_plates).translate(t)}
    if tof:
        out['tof_arm'] = rp.tof_arm().translate(t)
    return out


def leg_parts(L_mm: float, lean: float, zh: float) -> dict:
    """fivebar's leg at a stance, moved so its hip axis is at zh: {name: (shape, 'static'|'moving')}."""
    phi = fb.stance(L_mm, lean)
    fb.motor_model.cache_clear()
    real = fb.gmi.STEP_FRAMES.pop(fb.MOTOR, None)               # envelopes: quick, and nothing vendor leaves the machine
    try:
        asm = fb.assembly(*phi)
    finally:
        if real:
            fb.gmi.STEP_FRAMES[fb.MOTOR] = real
        fb.motor_model.cache_clear()
    out = {}
    for n, (s, _) in asm.items():
        if s is None or n == 'wheel_cable':
            continue
        static = n.startswith(fb.STATIC) or n == 'screws_lugs'
        out['leg_' + n] = ((s.val() if hasattr(s, 'val') else s).translate(cq.Vector(0, 0, zh)), 'static' if static else 'moving')
    return out


# ----------------------------------------------------------------------------------- clearance

def _bb(s):
    return (s.val() if hasattr(s, 'val') else s).BoundingBox()


def _bb_gap(a, b) -> float:
    gx = max(a.xmin - b.xmax, b.xmin - a.xmax, 0.0)
    gy = max(a.ymin - b.ymax, b.ymin - a.ymax, 0.0)
    gz = max(a.zmin - b.zmax, b.zmin - a.zmax, 0.0)
    return math.sqrt(gx * gx + gy * gy + gz * gz)


def min_distance(a, b) -> float:
    sa = a.val() if hasattr(a, 'val') else a
    sb = b.val() if hasattr(b, 'val') else b
    try:
        return float(sa.distance(sb))
    except Exception:
        return float('nan')


ALLOWED = {('leg_wheel_tyre', 'deck')}            # the tyre stands on the deck


def clearance_sweep(heights, leans, limit: float = 10.0) -> dict:
    """Every moving leg part against every rig part (fixed and carriage) at each stance with the wheel on the deck:
    the smallest gap per pair, and every pair under `limit` (the tyre on the deck excepted)."""
    fixed = fixed_parts()
    fixed_bb = {n: _bb(s) for n, s in fixed.items()}
    worst, under, poses = {}, [], 0
    for L in heights:
        for lean in leans:
            phi = fb.stance(L, lean)
            fo, fi, ro, ri = fb.stop_angles()
            if phi is None or not (fi - 1e-6 <= phi[0] <= fo + 1e-6 and ro - 1e-6 <= phi[1] <= ri + 1e-6):
                continue
            poses += 1
            zh = zh_on_deck(L, lean)
            others = dict(fixed)
            others.update(carriage_parts(zh))
            obb = dict(fixed_bb)
            obb.update({n: _bb(s) for n, s in others.items() if n not in fixed_bb})
            for n, (s, kind) in leg_parts(L, lean, zh).items():
                if kind != 'moving':
                    continue
                sb = _bb(s)
                for m, o in others.items():
                    if (n, m) in ALLOWED or n.startswith('leg_wheel_tyre') and m == 'deck':
                        continue
                    if _bb_gap(sb, obb[m]) > limit:
                        continue
                    d = min_distance(s, o)
                    key = f'{n} / {m}'
                    if key not in worst or d < worst[key][0]:
                        worst[key] = (round(d, 1), L, lean)
                    if d < limit:
                        under.append([n, m, round(d, 1), L, lean])
    return {'poses': poses, 'limit_mm': limit, 'closest': dict(sorted(worst.items(), key=lambda kv: kv[1][0])[:12]), 'under_limit': under}


def travel_check(zh_points: dict, limit: float = 10.0) -> dict:
    """The carriage and the leg's static parts (they ride with it) against the fixed rig over the carriage's travel:
    the blocks on the rails at both ends, and the smallest gaps (designed contacts: blocks on rails, the plate on the
    bumpers at their contact height, on the top stop at its contact height)."""
    fixed = fixed_parts()
    fixed_bb = {n: _bb(s) for n, s in fixed.items()}
    out = {}
    for tag, zh in zh_points.items():
        moving = carriage_parts(zh)
        moving.update({n: s for n, (s, k) in leg_parts(300.0, 0.0, zh).items() if k == 'static'})
        gaps = []
        for n, s in moving.items():
            sb = _bb(s)
            for m, o in fixed.items():
                if (n, m) == ('blocks', 'rails'):
                    continue
                if _bb_gap(sb, fixed_bb[m]) > limit:
                    continue
                gaps.append([n, m, round(min_distance(s, o), 1)])
        gaps.sort(key=lambda g: g[2])
        b_lo = zh - rp.BLOCK_Z - rp.HG15['L'] / 2
        b_hi = zh + rp.BLOCK_Z + rp.HG15['L'] / 2
        out[tag] = {'zh_mm': round(zh, 1), 'blocks_z_mm': [round(b_lo, 1), round(b_hi, 1)],
                    'on_rails': bool(b_lo >= rp.RAIL_Z0 - 1e-6 and b_hi <= RAIL_TOP + 1e-6), 'closest': gaps[:6]}
    return out


# ----------------------------------------------------------------------------------- loads

def block_loads(Fz: float, side_frac: float = 0.10, y_cm: float = -70.0, zh: float = 300.0) -> dict:
    """The four blocks' reactions for a tyre force Fz (N, up) with side_frac of it fore-aft and sideways, the moving
    carriage's centre of mass at y_cm (the tyre at y_wheel): a rigid carriage on four equal x-y springs (the rails take
    nothing along z). Returns the worst block's load and its safety on C0 and on the block's own moment ratings."""
    yw, zt = fb.Y['wheel'], 0.0                                   # the tyre's contact, deck frame
    F = np.array([side_frac * Fz, side_frac * Fz, Fz])
    P = np.array([0.0, yw, zt])
    # the carriage accelerates with the vertical force; its inertia acts at its centre of mass: the rail takes the moment
    # of Fz about that point (conservative: the leg's own moving mass, on the tyre's side, is left out)
    C = np.array([0.0, y_cm, zh])
    M = np.cross(P - C, F)
    blocks = [(sx * rp.BLOCK_X, rp.Y_RAIL, zh + sz * rp.BLOCK_Z) for sx in (-1, 1) for sz in (-1, 1)]
    # unknowns: fx, fy at each block (8); equations: Fx, Fy, Mx, My, Mz about C; least-norm = equal springs
    A, b = [], []
    for comp in range(2):                                         # sum fx = -Fx, sum fy = -Fy
        A.append([1.0 if (k % 2 == comp) else 0.0 for k in range(8)])
        b.append(-F[comp])
    for axis in range(3):                                         # moments about C
        row = []
        for (bx, by, bz) in blocks:
            r = np.array([bx, by, bz]) - C
            for comp in range(2):
                f = np.zeros(3)
                f[comp] = 1.0
                row.append(np.cross(r, f)[axis])
        A.append(row)
        b.append(-M[axis])
    sol, *_ = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)
    loads = [float(math.hypot(sol[2 * k], sol[2 * k + 1])) for k in range(4)]
    worst = max(loads)
    return {'Fz_n': round(Fz, 0), 'side_frac': side_frac, 'moment_on_rails_nm': [round(float(v) / 1000, 1) for v in M],
            'block_loads_n': [round(v, 0) for v in loads], 'worst_n': round(worst, 0),
            'sf_C0': round(rp.HG15['C0_kn'] * 1000 / worst, 1)}


def frame2d(nodes, elements, fixed, loads):
    """A small 2-D frame solver (y-z plane): nodes [(y, z)], elements [(i, j, EA, EI or None for a pinned strut)],
    fixed {node: (uy, uz, rot) flags}, loads {node: (Fy, Fz, M)}. Returns displacements and each element's end forces
    (axial N, moments N mm at both ends)."""
    n = len(nodes)
    K = np.zeros((3 * n, 3 * n))
    cache = []
    for i, j, EA, EI in elements:
        (y1, z1), (y2, z2) = nodes[i], nodes[j]
        L = math.hypot(y2 - y1, z2 - z1)
        c, s = (y2 - y1) / L, (z2 - z1) / L
        k = np.zeros((6, 6))
        a = EA / L
        k[0, 0] = k[3, 3] = a
        k[0, 3] = k[3, 0] = -a
        if EI:
            b1, b2, b3, b4 = 12 * EI / L ** 3, 6 * EI / L ** 2, 4 * EI / L, 2 * EI / L
            k[1, 1] = k[4, 4] = b1
            k[1, 4] = k[4, 1] = -b1
            k[1, 2] = k[2, 1] = k[1, 5] = k[5, 1] = b2
            k[4, 2] = k[2, 4] = k[4, 5] = k[5, 4] = -b2
            k[2, 2] = k[5, 5] = b3
            k[2, 5] = k[5, 2] = b4
        T = np.zeros((6, 6))
        for o in (0, 3):
            T[o, o], T[o, o + 1], T[o + 1, o], T[o + 1, o + 1], T[o + 2, o + 2] = c, s, -s, c, 1.0
        kg = T.T @ k @ T
        dofs = [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
        for p in range(6):
            for q in range(6):
                K[dofs[p], dofs[q]] += kg[p, q]
        cache.append((dofs, k, T))
    Fv = np.zeros(3 * n)
    for nd, (fy, fz, m) in loads.items():
        Fv[3 * nd:3 * nd + 3] += (fy, fz, m)
    free = [d for d in range(3 * n) if not fixed.get(d // 3, (0, 0, 0))[d % 3]]
    for i, j, EA, EI in elements:                                 # a pinned strut's own rotations are free nodes: pin them
        if not EI:
            for nd in (i, j):
                d = 3 * nd + 2
                if abs(K[d, d]) < 1e-9 and d in free:
                    free.remove(d)
    u = np.zeros(3 * n)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], Fv[free])
    forces = []
    for dofs, k, T in cache:
        f = k @ (T @ u[dofs])
        forces.append({'axial_n': float(-f[0]), 'm1_nmm': float(f[2]), 'm2_nmm': float(-f[5])})
    return u, forces


def post_check(M_couple: float, zh: float, braced: bool = True, foot: str = 'fixed') -> dict:
    """The post (8080) loaded by the carriage's couple M (N m, about x: the rails' pull and push at the blocks, 250 mm
    apart) at hip height zh, with or without the brace, its foot fixed or pinned. Bending stress, the sway at the
    carriage, the brace's force."""
    E = rp.E_AL
    p8, p4 = rp.PROFILES['8080'], rp.PROFILES['4040']
    EI, EA = E * p8['I_mm4'], E * p8['A_mm2']
    EA4 = E * p4['A_mm2']
    y0 = Y_POST_C
    zs = sorted({Z_FRAME_TOP, zh - rp.BLOCK_Z, zh + rp.BLOCK_Z, Z_BRACE, Z_FRAME_TOP + rp.POST_LEN})
    nodes = [(y0, z) for z in zs]
    els = [(k, k + 1, EA, EI) for k in range(len(nodes) - 1)]
    fixed = {0: (1, 1, 1 if foot == 'fixed' else 0)}
    if braced:
        (y1, z1), (y2, z2) = brace_line()
        nodes.append((y2, z2))
        els.append((zs.index(Z_BRACE), len(nodes) - 1, EA4, None))
        fixed[len(nodes) - 1] = (1, 1, 1)
    F = M_couple * 1000 / (2 * rp.BLOCK_Z)
    loads = {zs.index(zh + rp.BLOCK_Z): (F, 0.0, 0.0), zs.index(zh - rp.BLOCK_Z): (-F, 0.0, 0.0)}
    u, forces = frame2d(nodes, els, fixed, loads)
    mmax = max(max(abs(f['m1_nmm']), abs(f['m2_nmm'])) for f, e in zip(forces, els) if e[3])
    sigma = mmax / (p8['I_mm4'] / (p8['w'] / 2))
    sway = max(abs(u[3 * zs.index(zh + rp.BLOCK_Z)]), abs(u[3 * zs.index(zh - rp.BLOCK_Z)]))
    out = {'M_nm': round(M_couple, 0), 'zh_mm': zh, 'braced': braced, 'foot': foot, 'max_moment_nm': round(mmax / 1000, 1),
           'stress_mpa': round(sigma, 1), 'sf_yield': round(rp.YIELD_6063 / max(sigma, 1e-9), 1), 'sway_at_carriage_mm': round(sway, 2)}
    if braced:
        out['brace_force_n'] = round(forces[-1]['axial_n'], 0)
    return out


# ----------------------------------------------------------------------------------- masses

def carriage_mass() -> dict:
    """The carriage's own parts (what rides with the hip frame), from the CAD and the makers' masses."""
    plate = rp.carriage_plate().val()
    pv = plate.Volume() / 1000 * AL6061 / 1000
    shaft_kg = math.pi / 4 * (rp.SHAFT['d'] / 10) ** 2 * rp.SHAFT['len'] / 10 * STEEL / 1000
    parts = {'carriage_plate': round(pv, 3), 'blocks_4x': round(4 * rp.HG15['block_kg'], 3), 'ballast_shafts_2x': round(2 * shaft_kg, 3),
             'screws_and_washers': 0.12, 'tof_arm_and_sensor': round(rp.tof_arm().val().Volume() / 1000 * MATERIALS['petg']['density_g_cm3'] / 1000 + 0.005, 3),
             'harness_share_and_ties': 0.15}
    y = {'carriage_plate': (rp.Y_PLATE_FRONT + rp.Y_PLATE_BACK) / 2, 'blocks_4x': (rp.Y_POST_FRONT + rp.HG15['H1'] + rp.Y_PLATE_BACK) / 2,
         'ballast_shafts_2x': rp.Y_PLATE_BACK - rp.SHAFT['len'] / 2, 'screws_and_washers': rp.Y_PLATE_BACK,
         'tof_arm_and_sensor': rp.Y_PLATE_FRONT, 'harness_share_and_ties': rp.Y_PLATE_BACK}
    return {'parts_kg': parts, 'total_kg': round(sum(parts.values()), 3), 'y_mm': y}


def leg_masses() -> dict:
    """The leg's groups from sim/leg_rig.py's mass_props (CAD solids + datasheet masses): the frame group rides the
    carriage; the rest moves. Also what the controller's feed-forward needs."""
    from sim import leg_rig as lr
    mp = lr.mass_props()
    moving = mp['upper'].mass * 2 + mp['front'].mass + mp['wheel_link'].mass + mp['rotor'].mass
    return {'frame_kg': round(mp['frame'].mass, 3), 'frame_com_y_mm': round(mp['frame'].com[1] * 1000, 1), 'moving_kg': round(moving, 3),
            'rotor_kg': round(mp['rotor'].mass, 4), 'wheel_link_kg': round(mp['wheel_link'].mass, 4)}


WASHER_TRIM_KG = 0.14                  # a 3.5 in OD washer for a 1 in screw (McMaster 91117A251)


def ballast_table(cm: dict, lm: dict, plate_kg: dict) -> dict:
    """The weight plates for each carried mass: dummy = half mass - the leg's moving parts - its frame group - the
    carriage's own parts; split over the two posts."""
    rows = {}
    floor = lm['moving_kg'] + lm['frame_kg'] + cm['total_kg']
    shafts = cm['parts_kg']['ballast_shafts_2x']
    rows['lightest_kg'] = {'with_posts': round(floor, 2), 'posts_removed': round(floor - shafts, 2),
                           'note': 'the carriage\'s own parts set the floor: below it the rig cannot go (the plan\'s 11 kg point is out of reach)'}
    for hm in (11.0, 13.1, DESIGN_KG, 16.0):
        need = hm - floor
        if need < 0:
            rows[str(hm)] = {'plates_needed_kg': round(need, 3), 'reachable': hm >= floor - shafts,
                             'note': 'below the carriage with its ballast posts' + (': remove the posts' if hm >= floor - shafts else ': not reachable')}
            continue
        best = None
        tol = max(0.05, 0.02 * hm)                                 # within 2 % of the carried mass
        for n125 in range(0, 7, 2):                                # the plates the same on both posts
            for n25 in range(0, 9, 2):
                for nw in range(0, 9):                             # 3.5 in washers (0.14 kg) trim it
                    tot = n125 * plate_kg['1.25 lb'] + n25 * plate_kg['2.5 lb'] + nw * WASHER_TRIM_KG
                    err = tot - need
                    if abs(err) > tol:
                        continue
                    score = abs(err) + 0.05 * (n125 + n25 + nw)    # fewer pieces win over a few grams
                    if best is None or score < best[0]:
                        best = (score, n125, n25, nw, tot)
        if best is None:
            rows[str(hm)] = {'plates_needed_kg': round(need, 3), 'note': 'no combination within 2 %'}
            continue
        rows[str(hm)] = {'plates_needed_kg': round(need, 3), 'per_post': {'1.25 lb': best[1] // 2, '2.5 lb': best[2] // 2},
                         'washers_3p5in': best[3], 'ballast_kg': round(best[4], 3), 'over_by_kg': round(best[4] - need, 3),
                         'carried_kg': round(floor + best[4], 3),
                         'note': 'weigh the plates: the table assumes 0.567 and 1.134 kg; the washers (McMaster 91117A251) '
                                 '~0.14 kg each go on either post'}
    return rows


# ----------------------------------------------------------------------------------- the plate for SendCutSend

def order_sheet(path: Path, summary: dict) -> None:
    """exports/rig/sendcutsend/README.md: what to enter in SendCutSend's order form for the carriage plate, the hole
    table it checks against on arrival (from rig_parts.plate_holes(), the list the DXF and STEP are made from)."""
    names = {'frame_m5': ('M5 clearance', 'the hip frame\'s six flange inserts (M5 x 16 + washer from the back)'),
             'block_m4': ('M4 clearance', 'the four HGH15CA blocks (M4 x 10 from the front, into the blocks)'),
             'ballast': ('3/8 in clearance', 'the two ballast posts (3/8-16 x 1 in from the front)'),
             'drop_pin': ('pin hole', 'the drop test\'s quick-release pin (S4)'),
             'tether': ('tether hole', 'the carriage tether\'s screwgate carabiner'),
             'tof_m4': ('M4 clearance', 'the ToF target arm')}
    L = ['# Carriage plate: the SendCutSend order', '',
         'Generated by `cad/build_rig.py` with the plate it describes. Upload one of the two files; both are the same plate.', '',
         '| | |', '|---|---|',
         '| Files | `carriage_plate.dxf` (flat, mm, 1:1, one layer, no text) or `carriage_plate.step` |',
         '| Material | Aluminium 6061-T6, 0.250 in (6.35 mm) |',
         f"| Size | {rp.PLATE_W:.0f} x {rp.PLATE_H:.0f} mm, 6 mm corner radii; {summary['carriage_plate']['mass_kg']} kg |",
         '| Quantity | 1 |',
         '| Finish | Deburring on (both faces carry parts); no anodise, no powder coat |',
         '| Operations | None: every hole is a clearance hole (no tapping, no countersinks, no bends) |',
         '| Units check | The upload must read 300 x 320 mm (11.81 x 12.60 in); if it reads 25.4 times too big or small, re-upload in mm |',
         '| Price | The instant price shown at upload (D40: no quotes); the estimate is $60-90. Backup: Xometry, instant price from the STEP |', '',
         '## The holes (plate coordinates: the hip axis at 0, 0; x across, z up; seen from the front)', '',
         '| Holes | Size mm | Where (x, z mm) | For |', '|---|---|---|---|']
    groups = {}
    for h in rp.plate_holes():
        groups.setdefault(h[0], []).append(h)
    for k, hs in groups.items():
        if k.startswith('harness_'):
            for h in hs:
                L.append(f"| 1 slot | {h[3]:.1f} x {h[4]:.1f} | ({h[1]:.1f}, {h[2]:.1f}) | the {k.split('_', 1)[1]} motor's lead (XT30 and GH plug) |")
            continue
        size, what = names.get(k, (k, ''))
        where = '; '.join(f'({h[1]:.1f}, {h[2]:.1f})' for h in hs)
        L.append(f'| {len(hs)} x {size} | {hs[0][3]:.2f} | {where} | {what} |')
    webs = summary['carriage_plate'].get('thin_webs') if isinstance(summary.get('carriage_plate'), dict) else None
    L += ['', '## On arrival', '',
          '- Measure the thickness (6.35 mm, +-0.25) and the outline (300 x 320).',
          '- Hold an HGH15CA block on each group of four M4 holes: the four screws must start by hand.',
          '- With the hip frame\'s inserts set, the frame sits on the plate with all six M5 screws starting by hand (5.5 mm holes).',
          '- The harness slots pass an XT30 plug and a GH plug together.']
    if webs:
        L.append(f'- Thinnest web between features: {webs}.')
    path.write_text('\n'.join(L) + '\n')


def plate_dxf(path: Path) -> dict:
    """The carriage plate as a flat DXF (mm, the outline with 6 mm corner radii, holes as circles, the harness slots as
    closed polylines with arcs; no text, one layer) and its re-import check against plate_holes()."""
    import ezdxf
    doc = ezdxf.new('R2010', setup=False)
    doc.units = ezdxf.units.MM
    doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()
    W, H, rc = rp.PLATE_W, rp.PLATE_H, 6.0
    x0, x1, z0, z1 = -W / 2, W / 2, -H / 2, H / 2
    b = math.tan(math.radians(90) / 4)                                  # bulge for a 90 deg arc
    outline = [(x0 + rc, z0, 0), (x1 - rc, z0, b), (x1, z0 + rc, 0), (x1, z1 - rc, b), (x1 - rc, z1, 0), (x0 + rc, z1, b),
               (x0, z1 - rc, 0), (x0, z0 + rc, b)]
    msp.add_lwpolyline([(x + W / 2, z + H / 2, 0, 0, bu) for x, z, bu in outline], format='xyseb', close=True)
    for h in rp.plate_holes():
        if len(h) == 4:
            msp.add_circle((h[1] + W / 2, h[2] + H / 2), h[3] / 2)
        else:
            cx, cz, w, hh = h[1] + W / 2, h[2] + H / 2, h[3], h[4]
            r = min(w, hh) / 2
            if w >= hh:
                pts = [(cx - w / 2 + r, cz - r, 0, 0, 0), (cx + w / 2 - r, cz - r, 0, 0, 1), (cx + w / 2 - r, cz + r, 0, 0, 0),
                       (cx - w / 2 + r, cz + r, 0, 0, 1)]
            else:
                pts = [(cx + r, cz - hh / 2 + r, 0, 0, 0), (cx + r, cz + hh / 2 - r, 0, 0, 1), (cx - r, cz + hh / 2 - r, 0, 0, 0),
                       (cx - r, cz - hh / 2 + r, 0, 0, 1)]
            msp.add_lwpolyline(pts, format='xyseb', close=True)
    doc.saveas(path)
    # read it back: every hole of the table must be there, at its place and size
    back = ezdxf.readfile(path)
    circles = [(round(c.dxf.center.x - W / 2, 3), round(c.dxf.center.y - H / 2, 3), round(2 * c.dxf.radius, 3)) for c in back.modelspace().query('CIRCLE')]
    polys = back.modelspace().query('LWPOLYLINE')
    want = [(round(h[1], 3), round(h[2], 3), round(h[3], 3)) for h in rp.plate_holes() if len(h) == 4]
    missing = [w for w in want if not any(abs(w[0] - c[0]) < 1e-3 and abs(w[1] - c[1]) < 1e-3 and abs(w[2] - c[2]) < 1e-3 for c in circles)]
    ext = None
    for p in polys:
        xs = [v[0] for v in p.get_points('xy')]
        ys = [v[1] for v in p.get_points('xy')]
        if max(xs) - min(xs) > W - 1:
            ext = (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3))
    slots = len(polys) - 1
    by_d = {}
    for c in circles:
        by_d[c[2]] = by_d.get(c[2], 0) + 1
    return {'file': str(path.relative_to(R)), 'circles': len(circles), 'holes_by_diameter_mm': dict(sorted(by_d.items())),
            'slots': slots, 'outline_mm': ext, 'units': 'mm', 'reimport_ok': not missing and ext == (W, H) and slots == 2,
            'missing': missing}


# ----------------------------------------------------------------------------------- bought parts of the rig

BOUGHT = [   # (catalog/rig.json key, qty, what for)
    ('rail_hgr15_set', 2, 'HGR15 x 1000 mm rail with two HGH15CA blocks: the carriage\'s guide, on the post\'s front slots'),
    ('extrusion_8080_1200', 1, 'the post'),
    ('extrusion_4040', 7, f"base: 2 x {Y_FRONT - Y_REAR:.0f} sides, 4 x {2 * (X_SIDE - 20):.0f} cross members, 1 brace (cut lengths in rig.json)"),
    ('extrusion_4080_620', 1, 'the post\'s member (lying flat under it)'),
    ('bracket_corner_8', 24, 'every base joint (2 per joint) and the post\'s foot (4)'),
    ('hinge_8', 2, 'the brace\'s two ends'),
    ('tnut_m8_8', 70, 'brackets (48), hinges (8), top stop (4), drop bracket (2), pod (4), tether eye (2), spare'),
    ('screw_m8x16', 70, 'with the M8 T-nuts'),
    ('tnut_m4_8', 34, 'the rails, 17 per rail at 60 mm'),
    ('screw_m4x16', 34, 'the rails into the T-nuts'),
    ('screw_m4x12', 16, 'the four blocks onto the plate (a washer under each: 4.85 mm into the 5 mm threads)'),
    ('washer_m4', 16, 'under the block screws'),
    ('screw_m5x16', 6, 'the plate onto the hip frame\'s six inserts (with washers)'),
    ('washer_m5', 6, 'under those'),
    ('tnut_m6_8', 12, 'the deck (8) and the bottom bumpers (4)'),
    ('screw_m6x45_fh', 12, 'the deck and the bumpers into the members\' top slots'),
    ('ballast_shaft', 2, '1 in steel shaft, end-tapped: the ballast posts'),
    ('screw_ballast', 4, 'into the shafts\' tapped ends: one through the plate, one with a fender washer at the free end'),
    ('washer_fender_1in', 4, 'retain the plates; also fine ballast'),
    ('weight_plate_1p25', 4, 'standard 1 in plates (ballast table in rig.json)'),
    ('weight_plate_2p5', 4, 'standard 1 in plates'),
    ('quick_pin_10', 1, 'the drop test\'s release pin (S4), with a lanyard'),
    ('webbing_sling', 2, 'the safety tethers: carriage to the post\'s top; the wheel link to the carriage'),
    ('carabiner', 3, 'the tethers\' ends'),
    ('plywood_18', 1, 'the deck (600 x 400) and the load plate\'s pad (400 x 300), from one 2 x 4 ft panel'),
    ('rubber_mat', 1, 'under the base: it rests on the floor along every member'),
    ('carriage_plate', 1, 'SendCutSend, 6061-T6 0.25 in (exports/rig/sendcutsend/)'),
]


def bom() -> dict:
    cat = {}
    p = R / 'catalog' / 'rig.json'
    if p.exists():
        for it in json.loads(p.read_text()):
            cat[it.get('key') or it['id']] = it
    rows, missing = [], []
    for key, qty, why in BOUGHT:
        it = cat.get(key)
        if not it:
            missing.append(key)
        unit = (it or {}).get('price_usd')
        pack = (it or {}).get('pack_qty') or 1
        packs = math.ceil(qty / pack) if pack > 1 else qty
        rows.append({'key': key, 'qty': qty, 'for': why, 'vendor': (it or {}).get('vendor'), 'part_number': (it or {}).get('model'),
                     'name': (it or {}).get('name'), 'price_usd_each': unit, 'pack_qty': pack,
                     'cost_usd': round((it or {}).get('pack_price_usd', unit or 0) * packs if pack > 1 else (unit or 0) * qty, 2)})
    return {'rows': rows, 'not_in_catalog': missing, 'total_usd': round(sum(r['cost_usd'] for r in rows), 2)}


# ----------------------------------------------------------------------------------- renders

COL = {'deck': (.80, .66, .45), 'post': (.62, .65, .70), 'rails': (.35, .37, .40), 'blocks': (.25, .27, .30),
       'carriage_plate': (.78, .80, .83), 'ballast': (.20, .21, .23), 'brace': (.62, .65, .70), 'member': (.62, .65, .70),
       'bumper_tpu': (.85, .22, .20), 'top_tpu': (.85, .22, .20), 'bumper': (.30, .55, .85), 'top_stop': (.30, .55, .85),
       'pod': (.30, .55, .85), 'pendant': (.95, .80, .10), 'tof_arm': (.95, .95, .95), 'tof': (.30, .55, .85), 'drop': (.30, .55, .85), 'hinge': (.4, .4, .45),
       'side_': (.62, .65, .70)}


def colour(n: str):
    if n.startswith('leg_'):
        import build_leg as bl
        return bl.colour(n[4:])
    for k, v in COL.items():
        if n.startswith(k) or k in n:
            return v
    return (.6, .6, .6)


def scene(L_mm: float, lean: float = 0.0, zh: float = None, extra: dict = None):
    zh = zh_on_deck(L_mm, lean) if zh is None else zh
    parts = dict(fixed_parts())
    parts.update(carriage_parts(zh))
    if extra:
        parts.update(extra)
    shapes = [((s.val() if hasattr(s, 'val') else s), colour(n)) for n, s in parts.items()]
    shapes += [(s, colour(n)) for n, (s, k) in leg_parts(L_mm, lean, zh).items()]
    return shapes


def render(jump_zh: float) -> list:
    from cadagent.render import Renderer
    r = Renderer(OUT, subtitle='GYROPUP SINGLE-LEG RIG | M3')
    made = []
    for L, tag, view in ((130.0, 'crouch', (1.0, 0.85, 0.45)), (300.0, 'stand', (1.0, 0.85, 0.45)), (392.0, 'tall', (1.0, 0.85, 0.45))):
        r.render(f'rig-{tag}.png', shapes=scene(L), view=view, caption=f'Rig, the leg at {L:.0f} mm (wheel on the deck)')
        made.append(f'rig-{tag}.png')
    r.render('rig-jump-apex.png', shapes=scene(250.0, zh=jump_zh), view=(1.0, 0.85, 0.45),
             caption=f'Rig at the jump\'s apex (14.75 kg): the hip {jump_zh:.0f} mm over the deck, the leg tucked to 250 mm')
    made.append('rig-jump-apex.png')
    r.render('rig-side.png', shapes=scene(300.0), view=(1.0, 0.0, 0.05), caption='Rig from the side (+x): post, rails, carriage, brace')
    made.append('rig-side.png')
    r.render('rig-back.png', shapes=scene(300.0), view=(-0.5, -1.0, 0.35), caption='Rig from behind: ballast posts, brace, pod')
    made.append('rig-back.png')
    return made


# ----------------------------------------------------------------------------------- main

def jump_apex(half_mass: float) -> dict:
    """The highest hip and the landing in a 60 N m jump at this carried mass: the rig's controller in the simulation."""
    from rig.run import Pack, pack_for, run_sim
    o = run_sim('jump', half_mass, 500.0, pack_for('jump'), 1, rail_low=rp.BUMPER['contact_leg_mm'] / 1000, save=False)
    a = o['log'].arrays()
    res = o['results']
    rail = a['rail_mm']
    zh0 = zh_on_deck(300.0)
    return {'half_mass_kg': half_mass, 'jump_mm': res['jump_height_mm'], 'zh_max_mm': round(zh0 + float(np.nanmax(rail - rail[0])), 1),
            'peak_wheel_force_n': res['peak_wheel_force_n']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-sweep', action='store_true')
    ap.add_argument('--no-sim', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    SCS.mkdir(parents=True, exist_ok=True)
    summary = {'frame': 'deck frame: the leg\'s x (forward), y (outwards) and z (up); the origin on the deck under the hip axis',
               'frame_mounts': rp.FM}

    # the made parts: printed (STEP + print STL + plan) and the plate (STEP + DXF)
    plan, report = {}, {}
    for name, (fn, mat, qty, note, rot) in rp.PRINTED.items():
        s = fn().val()
        cq.exporters.export(s, str(OUT / f'{name}.step'))
        rep = export_print_stl(s, OUT / f'{name}.stl', rotation=rot)
        g = s.Volume() / 1000 * MATERIALS[mat]['density_g_cm3']
        solid = '100 %' in note
        grams = g if solid else g * 0.55
        plan[name] = printplan.row(s, rot, mat, qty, grams, solid, note)
        report[name] = {'watertight': rep.get('watertight'), 'valid': s.isValid()}
    too_big = printplan.write(OUT / 'print-plan.json', plan, note='the rig\'s printed parts; grams: solid parts in full, the rest '
                              'at ~55 % of solid (walls and infill); hours are rough')
    plate = rp.carriage_plate().val()
    cq.exporters.export(plate, str(SCS / 'carriage_plate.step'))
    dxf = plate_dxf(SCS / 'carriage_plate.dxf')
    summary['carriage_plate'] = {'material': '6061-T6 aluminium, 0.25 in (6.35 mm)', 'size_mm': [rp.PLATE_W, rp.PLATE_H],
                                 'mass_kg': round(plate.Volume() / 1e6 * AL6061, 3), 'holes': rp.plate_holes(),
                                 'webs_under_thickness': rp.plate_webs(), 'dxf': dxf, 'harness_slots': rp.harness_slots()}
    summary['printed'] = {'report': report, 'too_big': too_big}

    # masses and ballast
    cm = carriage_mass()
    lm = leg_masses()
    plate_kg = {'1.25 lb': 0.567, '2.5 lb': 1.134}
    summary['mass'] = {'carriage_parts': cm, 'leg': lm, 'ballast': ballast_table(cm, lm, plate_kg),
                       'note': f'the simulation\'s carriage at {DESIGN_KG} kg is the leg\'s frame group + the dummy; the rig\'s '
                               'dummy is its carriage parts + the plates'}
    summary['controller'] = {'rotor_kg': lm['rotor_kg'], 'wheel_link_kg': lm['wheel_link_kg'],
                             'ff_n_at_design': round(DESIGN_KG * 9.81 - (lm['rotor_kg'] + 0.5 * lm['wheel_link_kg']) * 9.81, 2)}

    # travel: the carriage's lowest (the bumpers crushed), the bumpers' contact, a stand, the drop's start, the jump's
    # apex at the lightest carried mass, the top stop's contact and crush
    zh_bottom = zh_on_deck(rp.BUMPER['contact_leg_mm'] - rp.BUMPER['crush'])
    apex = {} if a.no_sim else {str(m): jump_apex(m) for m in (11.0, DESIGN_KG)}
    zh_apex = max((v['zh_max_mm'] for v in apex.values()), default=zh_on_deck(300.0) + 330.0)
    z_top_face = rp.top_stop_z(RAIL_TOP)
    zh_top_contact = z_top_face - rp.PLATE_H / 2
    zh_top_crushed = zh_top_contact + rp.BUMPER['crush']
    zpts = {'bumpers_crushed': zh_bottom, 'bumper_contact': zh_on_deck(rp.BUMPER['contact_leg_mm']), 'stand_300': zh_on_deck(300.0),
            'drop_start': zh_on_deck(300.0) + 150.0, 'jump_apex': zh_apex, 'top_stop_contact': zh_top_contact, 'top_stop_crushed': zh_top_crushed}
    summary['travel'] = {'rails_z_mm': [rp.RAIL_Z0, RAIL_TOP], 'jump_apex': apex, 'margin_apex_to_top_stop_mm': round(zh_top_contact - zh_apex, 1),
                         'points': travel_check(zpts) if not a.no_sweep else {k: round(v, 1) for k, v in zpts.items()}}

    # loads at the design mass (exports/rig/predictions.json: the rig's own controller in the simulation)
    pred = json.loads((OUT / 'predictions.json').read_text())['tests'] if (OUT / 'predictions.json').exists() else {}
    Fj = pred.get('jump', {}).get('summary', {}).get('peak_wheel_force_n', 3700.0)
    Fd = pred.get('drop_150', {}).get('summary', {}).get('peak_wheel_force_n', 2309.5)
    y_cm = (sum(cm['parts_kg'][k] * cm['y_mm'][k] for k in cm['parts_kg']) + lm['frame_kg'] * lm['frame_com_y_mm']
            + (DESIGN_KG - lm['moving_kg'] - lm['frame_kg'] - cm['total_kg']) * (rp.Y_PLATE_BACK - 40.0)) / (DESIGN_KG - lm['moving_kg'])
    bl_j = block_loads(Fj, 0.10, y_cm)
    bl_d = block_loads(Fd, 0.10, y_cm)
    Mx = abs(bl_j['moment_on_rails_nm'][0])
    posts = [post_check(Mx, zh, braced, foot) for zh in (zh_on_deck(160.0), zh_on_deck(250.0), 600.0)
             for braced, foot in ((False, 'fixed'), (True, 'fixed'), (True, 'pinned'))]
    summary['loads'] = {'source': 'exports/rig/predictions.json (rig/run.py --predict, 14.75 kg)', 'carriage_com_y_mm': round(y_cm, 1),
                        'jump': bl_j, 'drop_150': bl_d, 'post': posts,
                        'post_worst': max(posts, key=lambda p: p['stress_mpa']),
                        'brace': brace()[2]}
    # the bumpers: the power cut onto them (S5) from the prediction: the carriage's speed at contact, the energy, the
    # mean force a 25 mm crush needs, per bumper
    s5 = pred.get('power_off', {})
    ser = s5.get('series', {})
    e_info = {}
    if ser:
        t = np.array(ser['t'])
        rail = np.array(ser['rail_mm']) / 1000
        L = np.array(ser['L_mm'])
        v = np.gradient(rail, t)
        i = int(np.argmax(L <= rp.BUMPER['contact_leg_mm'] + 0.5)) if np.any(L <= rp.BUMPER['contact_leg_mm'] + 0.5) else None
        m_c = DESIGN_KG - lm['moving_kg']
        if i:
            vc = float(abs(v[max(i - 1, 0)]))
            E = 0.5 * m_c * vc ** 2 + m_c * 9.81 * rp.BUMPER['crush'] / 1000
            e_info = {'carriage_kg': round(m_c, 2), 'speed_at_contact_m_s': round(vc, 2), 'energy_j': round(E, 1),
                      'mean_force_per_bumper_n': round(E / (rp.BUMPER['crush'] / 1000) / 2, 0)}
    a_tpu = (rp.BUMPER['w'] - 2 * rp.BUMPER['wall'] - 0.8) ** 2
    summary['bumpers'] = {'contact_leg_mm': rp.BUMPER['contact_leg_mm'], 'bottomed_leg_mm': rp.BUMPER['contact_leg_mm'] - rp.BUMPER['crush'],
                          'leg_stops_mm': 101.5, 'base_h_mm': round(rp.bumper_base_h(), 2), 'contact_z_mm': round(rp.bumper_contact_z(), 2),
                          'power_cut_S5': e_info, 'tpu_face_mm2': round(a_tpu, 0),
                          'plateau_needed_mpa': round(e_info.get('mean_force_per_bumper_n', 0) / a_tpu, 3) if e_info else None,
                          'gyroid_estimate': 'TPU 95A gyroid crushes at roughly 0.3 x E x density^2 (elastomeric cells): 0.05 MPa at 15 %, '
                                             '0.12 MPa at 20 %, 0.26 MPa at 30 % (E 9.8 MPa, Bambu); R0 in docs/leg-bench-tests.md drops '
                                             'the carriage on them to choose the infill'}
    # the base cannot tip: everything's weight and the moving mass's inertia inside the footprint
    rig_kg = sum(rp.PROFILES[k]['kg_m'] * L / 1000 for k, ax, L, at, fl in base_members().values()) + 2.6 + 3.0
    summary['base'] = {'footprint_mm': {'x': [-BASE_W / 2, BASE_W / 2], 'y': [round(Y_REAR, 1), Y_FRONT]}, 'rig_kg_est': round(rig_kg, 1),
                       'members': {k: {'kind': v[0], 'length_mm': round(v[2], 1)} for k, v in base_members().items()},
                       'note': 'the deck\'s push from the tyre and the rails\' couple are internal to one frame; the floor sees '
                               'the weights and the moving mass\'s inertia, inside the footprint at y -33 mm'}
    summary['harness'] = {'grommet': rp.GROMMET, 'slots': rp.harness_slots(), 'lug_clock_deg': fb.lug_clock()[0],
                          'note': 'the leads leave the rear covers 6-19 mm in front of the mount plane, pointing at the frame\'s '
                                  'flanges; they go straight back through the plate. The slots follow fivebar\'s clocking: '
                                  'rebuild the DXF after any change to it'}
    # clearances
    if not a.no_sweep:
        hs = list(np.linspace(101.5, 392.0, 14))
        summary['clearance'] = clearance_sweep([round(h, 1) for h in hs], (-20.0, 0.0, 20.0))
    summary['bom'] = bom()                     # the CAD's bought parts; exports/rig/bom.json is tools/rig_orders.py's
    order_sheet(OUT / 'sendcutsend' / 'README.md', summary)
    asm = scene(300.0)
    comp = cq.Compound.makeCompound([s for s, _ in asm])
    cq.exporters.export(comp, str(OUT / 'rig_300.step'))
    if not a.no_render:
        summary['pictures'] = render(zh_apex)
    summary['print'] = json.loads((OUT / 'print-plan.json').read_text())['by_material']
    (OUT / 'rig.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f"rig: plate {summary['carriage_plate']['mass_kg']} kg, DXF re-import {'OK' if dxf['reimport_ok'] else 'FAILED'}; "
          f"carriage parts {cm['total_kg']} kg; ballast at {DESIGN_KG} kg: {summary['mass']['ballast'][str(DESIGN_KG)]}")
    print(f"  blocks: jump worst {bl_j['worst_n']} N (SF {bl_j['sf_C0']} on C0), drop {bl_d['worst_n']} N; post worst {summary['loads']['post_worst']}")
    print(f"  travel: apex hip {zh_apex:.0f} mm, top stop contact {zh_top_contact:.0f} mm (margin {zh_top_contact - zh_apex:.0f})")
    if 'clearance' in summary:
        c = summary['clearance']
        print(f"  clearance: {c['poses']} poses, under {c['limit_mm']} mm: {len(c['under_limit'])}; closest {list(c['closest'].items())[:4]}")
    print(f'  {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
