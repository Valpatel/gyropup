"""The single-leg test rig (milestone M3): one leg v2 (cad/fivebar.py) on a carriage riding two profile rails on an 8080
post, a braced extrusion base with a plywood deck the wheel lands on, bumpers, ballast and the electrics pod
(docs/leg-prototype-plan.md section 2; cad/build_rig.py builds, checks and exports it).

Rig frame: the leg's own axes (x forward, y outwards: the linkage and the wheel at +y, z up) with the origin on the
deck's top surface under the hip axis. The carriage (the plate, the blocks, the ballast, the hip frame and the motors)
moves on z: at a hip height zh the leg's module frame sits at (0, 0, zh).

    side (looking along +x)                          plan (looking down)
        post 8080 |P|                                 rear member  ======  (brace foot)
        rails     |P|] blocks ] plate | motors ...       brace       |
        brace    /|P|                                  post 8080   [##]   on a 4080 member
                / |P|  bumpers [] under the plate      bumper member ====  (the deck starts at the post)
      =========================== deck (18 mm)         wheel member  ====  (the tyre lands right above it)
      base 4040 / 4080 members on the floor            front member  ====

Everything the rig adds is one of: an extrusion or a fastener (bought, envelopes here), the carriage plate (cut by
SendCutSend from cad/build_rig.py's DXF), or a printed part (PETG, the bumpers TPU 95A).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cadquery as cq

import fivebar as fb
import gmi

FAST = gmi.FAST

# ----------------------------------------------------------------------------------- bought: rails, extrusions

# HIWIN HG15 (HGH15CA block, HGR15 rail), HIWIN's catalogue (read 2026-10-27): block height over the rail's base H 28,
# block underside H1 4.3, width W 34, mounting B x C 26 x 26 with M4 x 5 threads, length L 61.4, mass 0.18 kg;
# rail 15 x 15, M4 x 16 screws at P 60 (end distance E 20), 1.45 kg/m. Ratings: the 2024 catalogue gives C 14.7 kN,
# C0 23.47 kN, MR/MP/MY 0.12/0.14/0.14 kN m; the 2017 one 11.38 / 16.97 / 0.12/0.10/0.10. The kits on the order list
# are unbranded copies with no rating: the checks use the 2017 figures.
HG15 = {'H': 28.0, 'H1': 4.3, 'W': 34.0, 'B': 26.0, 'C': 26.0, 'L': 61.4, 'thread': 'M4', 'thread_depth': 5.0,
        'block_kg': 0.18, 'rail_w': 15.0, 'rail_h': 15.0, 'P': 60.0, 'E': 20.0, 'rail_kg_m': 1.45,
        'C_kn': 11.38, 'C0_kn': 16.97, 'M0R_knm': 0.12, 'M0P_knm': 0.10, 'M0Y_knm': 0.10, 'ratings_from': 'HIWIN 2017 HG catalogue'}
# 8-series (10 mm slot, 40 mm module) aluminium profiles, MISUMI HFS8 class: kg/m and the second moment of area about
# either axis through the centre (MISUMI's tables; the 4080's about its strong axis, Ix, and weak axis, Iy)
PROFILES = {'8080': {'w': 80.0, 'h': 80.0, 'kg_m': 4.57, 'A_mm2': 1691.0, 'I_mm4': 1.291e6},      # MISUMI HFS8-8080
            '4040': {'w': 40.0, 'h': 40.0, 'kg_m': 1.73, 'A_mm2': 640.0, 'I_mm4': 1.04e5},       # HFS8-4040
            '4080': {'w': 40.0, 'h': 80.0, 'kg_m': 3.00, 'A_mm2': 1109.0, 'I_strong_mm4': 7.19e5, 'I_weak_mm4': 1.98e5}}   # HFS8-4080
SLOT_W, SLOT_D = 10.2, 3.0          # the slot opening and the depth drawn (an envelope: the T-groove is not modelled)
E_AL = 69e3                          # MPa, 6063-T5 / 6061-T6
YIELD_6063 = 145.0                   # MPa, 6063-T5 (MISUMI's profile alloy is 6063-T5 or 6N01)

# ----------------------------------------------------------------------------------- the leg's mount and the stack

DECK_T = 18.0                        # 18 mm (23/32 in) plywood
PLATE_T = 6.35                       # 6061-T6 0.25 in (SendCutSend stock)
PLATE_W, PLATE_H = 300.0, 320.0      # x, z; centred on the hip axis
BLOCK_X, BLOCK_Z = 20.0, 125.0       # the four blocks at (+-20, +-125): on the post's slot centres, 250 mm apart
POST_LEN = 1200.0
RAIL_LEN = 1000.0
RAIL_Z0 = 1.0                        # the rails' bottom end just above the deck (the blocks reach 4.3 mm above the
                                     # deck at the carriage's lowest possible point: the plate on the deck)
WHEEL_R = (gmi.motor_interface(fb.WHEEL)['od'] or 171.3) / 2


def frame_mounts() -> dict:
    """The hip frame's six M5 inserts (x, z) and the plane they end on (y): fivebar.frame_mounts() when the leg has it
    (plan F3), else the same numbers from hip_frame()'s construction (fl_x 95, 12 mm in from the ends, the flanges'
    mid-height plus 1.5 mm above the motors' ring)."""
    if hasattr(fb, 'frame_mounts'):
        fm = fb.frame_mounts()
        return {'plane_y': float(fm['plane_y']), 'inserts_xz': [tuple(map(float, p)) for p in fm['inserts_xz']], 'from': 'fivebar.frame_mounts()'}
    b = gmi.motor_interface(fb.MOTOR)['case']['bolts']
    ring_r = max(b['pcd'] / 2 + gmi.clear(b['thread']) + 4.5, fb.AC['bearing_od'] / 2 + 6)
    fl_t, fl_x = 7.0, 95.0
    zs = ring_r + fl_t / 2 + 1.5
    return {'plane_y': float(fb.Y['centre_plane']), 'inserts_xz': [(x, s * zs) for s in (1, -1) for x in (-fl_x + 12, 0.0, fl_x - 12)],
            'from': 'hip_frame() constants (fivebar.frame_mounts() not on this branch yet)'}


FM = frame_mounts()
Y_PLATE_FRONT = FM['plane_y']                      # -82.3: the hip frame's flange ends bolt to the plate's front face
Y_PLATE_BACK = Y_PLATE_FRONT - PLATE_T             # the blocks' top faces
Y_POST_FRONT = Y_PLATE_BACK - HG15['H']            # the rails' base = the post's front face
Y_POST_BACK = Y_POST_FRONT - PROFILES['8080']['h']
Y_RAIL = Y_POST_FRONT + HG15['rail_h'] / 2         # the rails' centre line (y)

# the harness: the RS-04's lead leaves its rear cover through a grommet (the vendor STEP RS04.stp, solid 27, measured
# 2026-10-27: centred 76.8 deg from the STEP's +x, reaching r 57 mm, 13.4-26.4 mm behind the case face, i.e. 6-19 mm in
# front of the mount plane). Between the frame's flanges there is no room to turn outwards, so each lead goes straight
# back through a slot in the plate behind its grommet.
GROMMET = {'angle_step_deg': 76.8, 'r_out': 57.0, 'y_from_plane': (5.8, 18.8)}
HARNESS_SLOT = (32.0, 22.0)                        # x, z: passes the XT30 plug (16 x 10) and the GH1.25 with room


def grommet_xz(front: bool):
    """Where a motor's lead leaves its grommet, on the plate (x, z), and its direction (deg, x-z plane): from the
    motor's clocking in fivebar (the same turn the leg's CAD gives the vendor model)."""
    (ax, _), (bx, _) = fb.motors()
    mx = ax if front else bx
    a = -(GROMMET['angle_step_deg'] + fb.step_turn(front))          # gmi.place maps the motor's +y onto the leg's -z
    a = (a + 180) % 360 - 180
    r = GROMMET['r_out']
    return (mx + r * math.cos(math.radians(a)), r * math.sin(math.radians(a))), a


def harness_slots():
    """The two slots (x, z centre, w, h): at each lead's exit, kept between the flanges (|z| <= 46: a full plate
    thickness of web to the frame's M5 holes at z = +-67)."""
    out = []
    for front in (True, False):
        (x, z), a = grommet_xz(front)
        z = max(-46.0, min(46.0, z))
        out.append({'x': round(x, 2), 'z': round(z, 2), 'w': HARNESS_SLOT[0], 'h': HARNESS_SLOT[1], 'exit_deg': round(a, 1),
                    'motor': 'front' if front else 'rear'})
    return out


# ----------------------------------------------------------------------------------- helpers

def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def cyl(r, axis, a0, a1, u=0.0, v=0.0):
    """A cylinder of radius r along 'x', 'y' or 'z' from a0 to a1, centred at (u, v) in the other two (in order)."""
    if axis == 'z':
        return cq.Workplane('XY').workplane(offset=a0).center(u, v).circle(r).extrude(a1 - a0)
    if axis == 'y':
        return cq.Workplane('XZ', origin=(0, a1, 0)).center(u, v).circle(r).extrude(a1 - a0)
    return cq.Workplane('YZ', origin=(a0, 0, 0)).center(u, v).circle(r).extrude(a1 - a0)


def stadium(cx, cz, w, h, y0, y1):
    """A rounded slot (w x h in x-z, full round ends on the short side) through y0..y1."""
    r = min(w, h) / 2
    s = cq.Workplane('XZ', origin=(0, y1, 0)).center(cx, cz).slot2D(max(w, h), 2 * r, 0 if w >= h else 90).extrude(y1 - y0)
    return s


def extrusion(kind: str, axis: str, length: float, at=(0.0, 0.0, 0.0), flat: bool = False):
    """A slotted 8-series profile along 'x', 'y' or 'z', its section centred on `at` in the other two axes and its
    length from at[axis] onwards. A 4080 has 40 along the first other axis and 80 along the second (y then z for a beam
    along x); flat=True swaps them (a 4080 along x lying flat: 80 in y, 40 tall)."""
    p = PROFILES[kind]
    w, h = (p['h'], p['w']) if flat else (p['w'], p['h'])
    x, y, z = at
    if axis == 'z':
        b = box(x - w / 2, x + w / 2, y - h / 2, y + h / 2, z, z + length)
        faces = [('x', x - w / 2, h, y), ('x', x + w / 2, h, y), ('y', y - h / 2, w, x), ('y', y + h / 2, w, x)]
    elif axis == 'y':
        b = box(x - w / 2, x + w / 2, y, y + length, z - h / 2, z + h / 2)
        faces = [('x', x - w / 2, h, z), ('x', x + w / 2, h, z), ('z', z - h / 2, w, x), ('z', z + h / 2, w, x)]
    else:
        b = box(x, x + length, y - w / 2, y + w / 2, z - h / 2, z + h / 2)
        faces = [('y', y - w / 2, h, z), ('y', y + w / 2, h, z), ('z', z - h / 2, w, y), ('z', z + h / 2, w, y)]
    for normal, pos, span, centre in faces:                     # a slot every 40 mm along each face
        n = int(round(span / 40))
        for k in range(n):
            c = centre - span / 2 + 20 + 40 * k
            sgn = 1 if pos > (x if normal == 'x' else y if normal == 'y' else z) else -1
            d0, d1 = (pos - SLOT_D, pos + 1) if sgn > 0 else (pos - 1, pos + SLOT_D)
            if axis == 'z':
                g = box(d0, d1, c - SLOT_W / 2, c + SLOT_W / 2, z - 1, z + length + 1) if normal == 'x' else \
                    box(c - SLOT_W / 2, c + SLOT_W / 2, d0, d1, z - 1, z + length + 1)
            elif axis == 'y':
                g = box(d0, d1, y - 1, y + length + 1, c - SLOT_W / 2, c + SLOT_W / 2) if normal == 'x' else \
                    box(c - SLOT_W / 2, c + SLOT_W / 2, y - 1, y + length + 1, d0, d1)
            else:
                g = box(x - 1, x + length + 1, d0, d1, c - SLOT_W / 2, c + SLOT_W / 2) if normal == 'y' else \
                    box(x - 1, x + length + 1, c - SLOT_W / 2, c + SLOT_W / 2, d0, d1)
            b = b.cut(g)
    return b


# ----------------------------------------------------------------------------------- the carriage plate (SendCutSend)

BALLAST_X, BALLAST_Z = 125.0, 20.0        # the two ballast posts (behind the plate, -y): plates of Ø150 at most
                                          # stay 10 mm off the post and above the bottom bumpers' reach
DROP_PIN = (125.0, 140.0, 10.2)           # x, z, hole: a 3/8 in ball-lock pin (McMaster 92384A274) into the drop bracket
TETHER = (-125.0, 140.0, 12.5)            # the safety tether's shackle
TOF_HOLES = ((-138.0, -104.0), (-138.0, -136.0))   # the ToF arm (2 x M4)
BALLAST_SCREW = {'d': 10.5, 'thread': '3/8-16', 'note': "3/8-16 x 1 in SHCS + washer into the shaft's 3/4 in deep thread"}


def plate_holes() -> list:
    """Every hole of the carriage plate in plate coordinates (x, z; the hip axis at 0, 0): [kind, x, z, d] for round
    holes, [kind, x, z, w, h] for slots. This list is what the DXF, the STEP and the checks share."""
    h = []
    for (x, z) in FM['inserts_xz']:
        h.append(['frame_m5', x, z, FAST['M5']['clear']])
    for sx in (-1, 1):
        for sz in (-1, 1):
            for dx in (-1, 1):
                for dz in (-1, 1):
                    h.append(['block_m4', sx * BLOCK_X + dx * HG15['B'] / 2, sz * BLOCK_Z + dz * HG15['C'] / 2, FAST['M4']['clear']])
    for sx in (-1, 1):
        h.append(['ballast', sx * BALLAST_X, BALLAST_Z, BALLAST_SCREW['d']])
    h.append(['drop_pin', DROP_PIN[0], DROP_PIN[1], DROP_PIN[2]])
    h.append(['tether', TETHER[0], TETHER[1], TETHER[2]])
    for (x, z) in TOF_HOLES:
        h.append(['tof_m4', x, z, FAST['M4']['clear']])
    for s in harness_slots():
        h.append(['harness_' + s['motor'], s['x'], s['z'], s['w'], s['h']])
    return h


def carriage_plate():
    """The carriage plate in the leg's module frame: front face on the hip frame's mount plane, 300 x 320 x 6.35."""
    p = box(-PLATE_W / 2, PLATE_W / 2, Y_PLATE_BACK, Y_PLATE_FRONT, -PLATE_H / 2, PLATE_H / 2).edges('|Y').fillet(6.0)
    for hole in plate_holes():
        if len(hole) == 4:
            p = p.cut(cyl(hole[3] / 2, 'y', Y_PLATE_BACK - 1, Y_PLATE_FRONT + 1, hole[1], hole[2]))
        else:
            p = p.cut(stadium(hole[1], hole[2], hole[3], hole[4], Y_PLATE_BACK - 1, Y_PLATE_FRONT + 1))
    return p


def plate_webs(min_web: float = PLATE_T) -> list:
    """Pairs of plate features closer than min_web (edge to edge) or to the plate's edge: SendCutSend asks for at
    least the thickness between holes and to an edge."""
    feats = []
    for h in plate_holes():
        if len(h) == 4:
            feats.append((h[0], h[1], h[2], h[3] / 2, h[3] / 2))
        else:
            feats.append((h[0], h[1], h[2], h[3] / 2, h[4] / 2))
    out = []
    for i in range(len(feats)):
        n, x, z, rx, rz = feats[i]
        edge = min(PLATE_W / 2 - abs(x) - rx, PLATE_H / 2 - abs(z) - rz)
        if edge < min_web:
            out.append([n, 'edge', round(edge, 2)])
        for j in range(i + 1, len(feats)):
            m, x2, z2, rx2, rz2 = feats[j]
            gx = abs(x - x2) - rx - rx2
            gz = abs(z - z2) - rz - rz2
            gap = math.hypot(max(gx, 0), max(gz, 0)) if (gx > 0 or gz > 0) else -1.0
            if gap < min_web:
                out.append([n, m, round(gap, 2)])
    return out


# ----------------------------------------------------------------------------------- carriage hardware (bought)

def blocks():
    """The four HGH15CA blocks on the plate's back face (module frame)."""
    out = None
    for sx in (-1, 1):
        for sz in (-1, 1):
            b = box(sx * BLOCK_X - HG15['W'] / 2, sx * BLOCK_X + HG15['W'] / 2, Y_POST_FRONT + HG15['H1'], Y_PLATE_BACK,
                    sz * BLOCK_Z - HG15['L'] / 2, sz * BLOCK_Z + HG15['L'] / 2)
            out = b if out is None else out.union(b)
    return out


SHAFT = {'d': 25.4, 'len': 152.4}         # 1 in x 6 in shaft tapped 3/8-16 both ends (McMaster 6649K433)
WEIGHT_PLATE = {'d': 129.5, 't': 20.3, 'bore': 27.0}   # Body-Solid RPB 2.5 lb standard plate (5.1 x 0.8 in); the 1.25 lb is
                                                       # 4 x 0.4 in; the 5 lb (6.7 in) would reach the post: not used


def ballast(n_plates: int = 2):
    """The two ballast posts and n plates on each (module frame), pointing back (-y) from the plate."""
    out = None
    for sx in (-1, 1):
        x = sx * BALLAST_X
        s = cyl(SHAFT['d'] / 2, 'y', Y_PLATE_BACK - SHAFT['len'], Y_PLATE_BACK, x, BALLAST_Z)
        y = Y_PLATE_BACK - 2.0
        for _ in range(n_plates):
            s = s.union(cyl(WEIGHT_PLATE['d'] / 2, 'y', y - WEIGHT_PLATE['t'], y, x, BALLAST_Z)
                        .cut(cyl(WEIGHT_PLATE['bore'] / 2, 'y', y - WEIGHT_PLATE['t'] - 1, y + 1, x, BALLAST_Z)))
            y -= WEIGHT_PLATE['t'] + 1.0
        out = s if out is None else out.union(s)
    return out


# ----------------------------------------------------------------------------------- printed parts

BUMPER = {'w': 60.0, 'd': 60.0, 'tpu_h': 40.0, 'cap_t': 5.0, 'skirt': 8.0, 'wall': 3.0, 'crush': 25.0,
          'contact_leg_mm': 140.0, 'x': 75.0}     # bottom bumpers at x = +-75: 8 mm beside the lower blocks (x <= 37)
BUMPER['y'] = (Y_PLATE_BACK + Y_PLATE_FRONT) / 2   # centred under the plate's edge


def bumper_contact_z(leg_mm: float = BUMPER['contact_leg_mm']) -> float:
    """The plate's bottom edge above the deck when the wheel stands on it at this leg length."""
    return leg_mm + WHEEL_R - PLATE_H / 2


def bumper_base_h() -> float:
    return bumper_contact_z() - BUMPER['tpu_h'] - BUMPER['cap_t']


def bumper_tpu():
    """The TPU 95A crush block (30 % gyroid to start: 33 J in 25 mm across two; R0 in docs/leg-bench-tests.md settles it)."""
    b = BUMPER
    return box(-b['w'] / 2 + b['wall'] + 0.4, b['w'] / 2 - b['wall'] - 0.4, -b['d'] / 2 + b['wall'] + 0.4, b['d'] / 2 - b['wall'] - 0.4,
               0.0, b['tpu_h']).edges('|Z').fillet(3.0)


def bumper_base():
    """PETG: stands on the deck, the TPU block in its pocket; 2 x M6 x 35 through the deck into drop-in nuts in the bumper member.
    Its height puts the cap at the plate's bottom edge when the leg is 140 mm long."""
    b = BUMPER
    hb = bumper_base_h()
    pocket = b['skirt']
    s = box(-b['w'] / 2, b['w'] / 2, -b['d'] / 2, b['d'] / 2, 0.0, hb + pocket).edges('|Z').fillet(4.0)
    s = s.cut(box(-b['w'] / 2 + b['wall'], b['w'] / 2 - b['wall'], -b['d'] / 2 + b['wall'], b['d'] / 2 - b['wall'], hb, hb + pocket + 1))
    for dx in (-15.0, 15.0):                                      # M6 x 35 SHCS: counterbored 14 deep from the pocket's floor,
        s = s.cut(cyl(3.3, 'z', -1, hb + 1, dx, 0.0))             # so 6.65 mm of base + the deck + the slot's lip leave 7 mm
        s = s.cut(cyl(5.6, 'z', hb - 14.0, hb + 1, dx, 0.0))     # in the drop-in nut
    return s


def bumper_cap():
    """PETG lid over the TPU block: the plate's 6.35 mm edge strikes it and it spreads the load."""
    b = BUMPER
    s = box(-b['w'] / 2, b['w'] / 2, -b['d'] / 2, b['d'] / 2, 0.0, b['cap_t'] + b['skirt']).edges('|Z').fillet(4.0)
    return s.cut(box(-b['w'] / 2 + b['wall'], b['w'] / 2 - b['wall'], -b['d'] / 2 + b['wall'], b['d'] / 2 - b['wall'], -1, b['skirt']))


TOP_STOP = {'gap_below_rail_top': 30.0}   # the top bumpers meet the plate's top edge this far below the rails' end


def top_stop_z(rail_top: float) -> float:
    """Where the top bumpers' TPU faces are (deck frame): the blocks still 25 mm inside the rails when crushed."""
    return rail_top - TOP_STOP['gap_below_rail_top']


def top_stop_bracket():
    """PETG: clamps on the post's front face above the rails' end (2 x M8 T-nuts in each front slot... the slots carry
    the rails below, so the bracket's own T-nuts slide in from the post's top), two cups for TPU blocks hanging over
    the plate's top edge at x = +-70. Built with its clamp face at y = 0 (the post's front face), z = 0 its underside's
    cup faces; cad/build_rig.py places it."""
    b = BUMPER
    reach = Y_PLATE_FRONT - Y_POST_FRONT + 30.0                 # from the post's face to past the plate
    t = 12.0
    s = box(-110.0, 110.0, 0.0, reach, b['tpu_h'] + 2.0, b['tpu_h'] + 2.0 + t)            # the arm over the carriage
    s = s.union(box(-45.0, 45.0, 0.0, 14.0, b['tpu_h'] + 2.0, b['tpu_h'] + 2.0 + 60.0))  # the clamp plate on the post
    for sx in (-1, 1):                                                # gussets
        s = s.union(box(sx * 30 - 4, sx * 30 + 4, 14.0, 50.0, b['tpu_h'] + 2.0 + t, b['tpu_h'] + 2.0 + 50.0))
        cx = sx * b['x']
        cup = box(cx - b['w'] / 2 - 3, cx + b['w'] / 2 + 3, (Y_PLATE_BACK + Y_PLATE_FRONT) / 2 - Y_POST_FRONT - b['d'] / 2 - 3,
                  (Y_PLATE_BACK + Y_PLATE_FRONT) / 2 - Y_POST_FRONT + b['d'] / 2 + 3, b['tpu_h'] - b['skirt'] + 2.0, b['tpu_h'] + 2.0 + t)
        cup = cup.cut(box(cx - b['w'] / 2 + b['wall'] - 0.2, cx + b['w'] / 2 - b['wall'] + 0.2,
                          (Y_PLATE_BACK + Y_PLATE_FRONT) / 2 - Y_POST_FRONT - b['d'] / 2 + b['wall'] - 0.2,
                          (Y_PLATE_BACK + Y_PLATE_FRONT) / 2 - Y_POST_FRONT + b['d'] / 2 - b['wall'] + 0.2,
                          b['tpu_h'] - b['skirt'] + 1.0, b['tpu_h'] + 2.0))
        s = s.union(cup)
    for sx in (-1, 1):
        for z in (b['tpu_h'] + 2.0 + 25.0, b['tpu_h'] + 2.0 + 48.0):
            s = s.cut(cyl(4.3, 'y', -1, 15, sx * 20.0, z))            # M8 x 16 into drop-in nuts in the front slots,
            s = s.cut(cyl(7.5, 'y', 6.0, 15, sx * 20.0, z))           # counterbored: 6 mm under the head
    return s


def drop_bracket():
    """PETG, fitted for the drop test (S4) only: an L-clamp on the post's +x side face (2 x M8 x 16 into drop-in nuts,
    heads outside) with an arm out in front of the post to a 3/8 in ball-lock pin's bush, through the plate's drop hole.
    Built in place in the module frame at the carriage's drop height (z 0 = the hip axis at the drop's start). Nothing of
    the carriage passes under it while it is fitted: the weight plates stay 15 mm below it when pinned."""
    x0 = PROFILES['8080']['w'] / 2
    xp, zp = DROP_PIN[0], DROP_PIN[1]
    y_b = Y_PLATE_BACK - 2.0
    clamp = box(x0, x0 + 12.0, Y_POST_BACK + 6.0, Y_POST_FRONT - 2.0, zp - 20.0, zp + 20.0)
    arm = box(x0, xp + 20.0, Y_POST_FRONT - 2.0, y_b, zp - 20.0, zp + 20.0)
    rib = box(x0, x0 + 40.0, Y_POST_BACK + 6.0, y_b, zp + 14.0, zp + 20.0)
    s = clamp.union(arm).union(rib)
    s = s.cut(cyl(4.9, 'y', Y_POST_FRONT - 3.0, y_b + 1, xp, zp))                                  # the pin's bore
    for y in (Y_POST_FRONT - 20.0, Y_POST_FRONT - 60.0):
        s = s.cut(cyl(4.3, 'x', x0 - 1, x0 + 13, y, zp))                                            # M8 into the side slots,
        s = s.cut(cyl(7.5, 'x', x0 + 4.0, x0 + 13, y, zp))                                          # heads on the outside
    return s


TOF = {'x': -212.0, 'target_below_plate': 15.0, 'target': 50.0}   # the target's centre x, how far below the plate's edge


def tof_arm():
    """PETG: a 50 x 50 white target held out past the plate's -x edge, 15 mm below the plate's bottom edge, so it is
    always the nearest thing above the VL53L1X on the deck (bolted to the plate's front face with 2 x M4; module
    frame). The sensor stays fixed and wired: its 15-27 deg cone sees nothing else of the carriage."""
    z_t = -PLATE_H / 2 - TOF['target_below_plate']
    x_end = TOF['x'] - TOF['target'] / 2
    s = box(x_end, -PLATE_W / 2 + 26.0, Y_PLATE_FRONT, Y_PLATE_FRONT + 6.0, z_t, -90.0)          # the arm on the plate
    s = s.union(box(x_end, x_end + TOF['target'], Y_PLATE_FRONT - 22.0, Y_PLATE_FRONT + 28.0, z_t, z_t + 4.0))   # the target
    for (x, z) in TOF_HOLES:
        s = s.cut(cyl(2.25, 'y', Y_PLATE_FRONT - 1, Y_PLATE_FRONT + 7, x, z))
    return s


def tof_mount():
    """PETG: holds the VL53L1X breakout (Adafruit 3967, 25.4 x 17.8 mm, 2 x M2.5 holes 20.3 mm apart) facing up on the
    deck under the carriage's target, its cable (STEMMA QT) to the pod. Two wood screws into the deck."""
    s = box(-22.0, 22.0, -16.0, 16.0, 0.0, 4.0)
    s = s.union(box(-15.0, 15.0, -12.0, 12.0, 4.0, 9.0)).cut(box(-13.2, 13.2, -9.4, 9.4, 6.0, 10.0))
    for dx in (-10.15, 10.15):
        s = s.cut(cyl(1.1, 'z', 3.0, 10.0, dx, 0.0))
    for dx in (-18.0, 18.0):
        s = s.cut(cyl(2.2, 'z', -1, 5, dx, 0.0)).cut(cyl(4.2, 'z', 2.5, 5, dx, 0.0))
    return s


POD = {'w': 140.0, 'd': 200.0, 'h': 230.0, 'wall': 4.0}   # the electrics pod on the post's back face: depth off the post
                                                          # (w), width across it (d), height
# what goes inside (makers' drawings): the contactor bottom-mounted on 2 x M4 46.3 mm apart (TE LEV100: a Ø39.5 can 58 mm
# tall, its M5 load terminals 17.78 apart on top); the off-delay relay (ProSense T2R, 2 in square, one central screw);
# the Class CC fuse holder and the 12 V DC-DC on a 35 mm top-hat rail printed on the inside of the post wall; the rig
# node (Feather M4 CAN on a FeatherWing Proto, 4 x M2.5) and the USB-CAN adapter in a pocket
POD_PARTS = {'contactor': {'x': -70.0, 'y': -50.0, 'holes': 46.3, 'can_d': 39.5, 'h': 58.0},
             'timer': {'x': -70.0, 'y': 45.0, 'size': 51.0, 'h': 45.0},
             'din_rail': {'z': 150.0, 'y0': -90.0, 'y1': 90.0},
             'feather': {'x': -110.0, 'y': 0.0, 'z': 60.0, 'holes': (45.7, 17.8)},
             'usb_can': {'x': -40.0, 'y': 60.0, 'w': 52.0, 'd': 24.0}}


def pod():
    """PETG electrics pod on the post's back face (the carriage's weight plates sweep both of the post's sides). Built
    with its mounting face at x = 0 (it reaches to -x), z = 0 its floor's underside, open on +y for its panel
    (pod_lid); cad/build_rig.py turns it onto the post. 4 x M8 x 16 into drop-in nuts in the post's back slots."""
    w, d, h, t = POD['w'], POD['d'], POD['h'], POD['wall']
    P = POD_PARTS
    s = box(-w, 0.0, -d / 2, d / 2, 0.0, h).edges('|X').fillet(6.0)
    s = s.cut(box(-w + t, -t, -d / 2 + t, d / 2 + 1.0, t, h - t))
    for z in (40.0, h - 40.0):
        for y in (-20.0, 20.0):
            s = s.cut(cyl(4.3, 'x', -t - 1, 1, y, z))                             # M8 into the post's back slots
    # the top-hat rail (35 x 7.5) on the post wall's inside, along y
    r = P['din_rail']
    rail = box(-t - 7.5, -t, r['y0'], r['y1'], r['z'] - 17.5, r['z'] + 17.5)
    rail = rail.cut(box(-t - 7.6, -t - 1.2, r['y0'] - 1, r['y1'] + 1, r['z'] - 12.5, r['z'] + 12.5))   # the two 5 mm lips
    s = s.union(rail)
    # bosses with M4 heat-set inserts: the contactor's two, the relay's one; M2.5 pilots for the node
    c = P['contactor']
    for dy in (-c['holes'] / 2, c['holes'] / 2):
        s = s.union(cyl(5.0, 'z', t - 0.01, t + 6.0, c['x'], c['y'] + dy)).cut(cyl(FAST['M4']['insert_pilot'] / 2, 'z', t - 3.0, t + 6.1, c['x'], c['y'] + dy))
    m = P['timer']
    s = s.union(cyl(5.0, 'z', t - 0.01, t + 6.0, m['x'], m['y'])).cut(cyl(FAST['M4']['insert_pilot'] / 2, 'z', t - 3.0, t + 6.1, m['x'], m['y']))
    f = P['feather']
    for dx in (-f['holes'][0] / 2, f['holes'][0] / 2):                            # on the pod's -y wall's inside, standing
        for dz in (-f['holes'][1] / 2, f['holes'][1] / 2):
            s = s.union(cyl(3.0, 'y', -d / 2 + t - 0.01, -d / 2 + t + 6.0, f['x'] + dx, f['z'] + dz + 40.0))
            s = s.cut(cyl(1.1, 'y', -d / 2 + t - 0.01, -d / 2 + t + 6.1, f['x'] + dx, f['z'] + dz + 40.0))
    u = P['usb_can']                                                              # a pocket the adapter slides into
    s = s.union(box(u['x'] - u['w'] / 2 - 2, u['x'] + u['w'] / 2 + 2, u['y'] - u['d'] / 2 - 2, u['y'] + u['d'] / 2 + 2, t - 0.01, t + 8.0))
    s = s.cut(box(u['x'] - u['w'] / 2, u['x'] + u['w'] / 2, u['y'] - u['d'] / 2, u['y'] + u['d'] / 2 + 3, t + 2.0, t + 9.0))
    s = s.cut(cyl(9.0, 'z', h - t - 1, h + 1, -w / 2, 0.0))                      # the service loop (motor power + CAN) out the top
    s = s.cut(cyl(5.0, 'z', -1, t + 1, -w + 25.0, -60.0))                         # the sensors' leads (ToF, load cells) out the bottom
    return s


def pod_lid():
    """The pod's panel (PETG, 3 mm; the makers' panel cutouts as cad/turret_stand.py PANEL): the pack's XT60E-M inlet
    (its lead carries the female, so no live pin is ever bare), the XT60E-F outlet to the motors, the 12 V converter's
    5 x 20 fuse holder, the pendant's 3.5 mm jack, the node's and the adapter's USB-C cables."""
    w, h, t = POD['w'], POD['h'], 3.0
    s = box(-w, 0.0, 0.0, t, 0.0, h).edges('|Y').fillet(6.0)
    cut = [('xt60_in', -105.0, 45.0, ('rect', 16.6, 8.6)), ('xt60_out', -105.0, 85.0, ('rect', 16.6, 8.6)),
           ('fuse_12v', -35.0, 45.0, ('d', 12.75, 12.13)), ('jack', -35.0, 85.0, ('round', 6.35)),
           ('usb_node', -105.0, 200.0, ('rect', 14.0, 8.0)), ('usb_can', -35.0, 200.0, ('rect', 14.0, 8.0))]
    for name, x, z, c in cut:
        if c[0] == 'rect':
            s = s.cut(box(x - c[1] / 2, x + c[1] / 2, -1, t + 1, z - c[2] / 2, z + c[2] / 2))
            if name.startswith('xt60'):
                for sx in (-1.0, 1.0):                                            # screws 18-28 mm apart: slots (turret_stand)
                    for dx in (9.0, 14.0):
                        s = s.cut(cyl(1.6, 'y', -1, t + 1, x + sx * dx, z))
                    xa, xb = sorted((x + sx * 9.0, x + sx * 14.0))
                    s = s.cut(box(xa, xb, -1, t + 1, z - 1.6, z + 1.6))
        elif c[0] == 'd':
            hole = cyl(c[1] / 2, 'y', -1, t + 1, x, z).cut(box(x - 10, x + 10, -2, t + 2, z + c[2] - c[1] / 2, z + 10))
            s = s.cut(hole)
        else:
            s = s.cut(cyl(c[1] / 2, 'y', -1, t + 1, x, z))
    for (x, z) in ((-w + 8, 8), (-8, 8), (-w + 8, h - 8), (-8, h - 8)):
        s = s.cut(cyl(1.7, 'y', -1, t + 1, x, z))
    return s


PENDANT_HOLDER = {'d': 36.0}              # the AbleNet Specs is a 35 mm button


def pendant_clip():
    """PETG: parks the pendant on the pod's side when nobody holds it (cup Ø36, a slot for its cord)."""
    d = PENDANT_HOLDER['d']
    s = box(-d / 2 - 4, d / 2 + 4, 0.0, 6.0, -10.0, d + 14.0)
    cup = cyl(d / 2 + 3, 'y', 6.0, 22.0, 0.0, d / 2 + 4).cut(cyl(d / 2 + 0.5, 'y', 8.0, 23.0, 0.0, d / 2 + 4))
    s = s.union(cup).cut(box(-4.0, 4.0, 5.0, 23.0, d / 2 + 4, d + 30.0))
    for z in (0.0, d + 6.0):
        s = s.cut(cyl(2.0, 'y', -1, 7, 0.0, z))
    return s


LOAD_CELL = {'w': 34.0, 'h': 8.0}         # a 50 kg half-bridge cell (the common 34 x 34 x 8 'bathroom scale' cell)


def load_cell_mount():
    """PETG: one of four corner mounts for the load plate's half-bridge cells (the cell's rim on the deck side, its
    centre pin under the pad)."""
    w = LOAD_CELL['w']
    s = box(-w / 2 - 4, w / 2 + 4, -w / 2 - 4, w / 2 + 4, 0.0, 6.0).edges('|Z').fillet(4.0)
    s = s.cut(box(-w / 2 - 0.3, w / 2 + 0.3, -w / 2 - 0.3, w / 2 + 0.3, 3.0, 7.0))
    s = s.cut(cyl(11.0, 'z', 1.0, 7.0))                                            # room for the cell's flexure to move
    s = s.cut(box(-3.0, 3.0, w / 2 - 2, w / 2 + 6, 3.0, 7.0))                    # the leads
    return s


PRINTED = {
    # name: (builder, material, qty, note, print rotation, in-place?)
    'bumper_tpu': (bumper_tpu, 'tpu95', 4, 'TPU 95A, 30 % gyroid, 2 walls (sized for 33 J: a hard fault at a jump\'s apex; '
                   'docs/leg-bench-tests.md R0 confirms the infill by dropping the carriage on them); two under the plate, two in '
                   'the top stop', None),
    'bumper_base': (bumper_base, 'petg', 2, 'PETG, 4 walls, 40 % gyroid; 2 x M6 x 45 countersunk through the deck into T-nuts', None),
    'bumper_cap': (bumper_cap, 'petg', 4, 'PETG, 100 % (it spreads the plate edge\'s blow); printed upside down', ((1, 0, 0), 180)),
    'top_stop_bracket': (top_stop_bracket, 'petg', 1, 'PETG, 6 walls, 50 % gyroid; 4 x M8 x 16 into T-nuts on the post\'s front', ((1, 0, 0), -90)),
    'drop_bracket': (drop_bracket, 'petg', 1, 'PETG, 100 %; fitted for the drop test only (2 x M8 x 16 into the post\'s side slots)', ((0, 0, 1), 0)),
    'tof_arm': (tof_arm, 'petg', 1, 'PETG, white (the ToF\'s target); 2 x M4 x 10 to the plate', ((1, 0, 0), 90)),
    'tof_mount': (tof_mount, 'petg', 1, 'PETG; the VL53L1X on 2 x M2.5 x 8, two wood screws into the deck', None),
    'pod': (pod, 'petg', 1, 'PETG, 3 walls, 25 % infill; 4 x M8 x 16 into the post\'s back slots; 3 x M4 inserts (contactor, relay)', ((0, 1, 0), 90)),
    'pod_lid': (pod_lid, 'petg', 1, 'PETG; 4 x M3 x 10 into the pod\'s inserts', ((1, 0, 0), 90)),
    'pendant_clip': (pendant_clip, 'petg', 1, 'PETG; 2 x M4 to the pod', ((1, 0, 0), -90)),
    'load_cell_mount': (load_cell_mount, 'petg', 4, 'PETG; under the load plate\'s corners (stand and squat only)', None),
}
