"""The rig's bought hardware as placed models (envelopes to the makers' dimensions) and the joint table that both
draws the screws and checks their lengths (cad/assembly_checks.py screw_stacks): one source for what is drawn and what
is checked. cad/build_rig.py adds these to the rig's parts.

Every screw is a row of JOINTS:
    name, the body it rides with ('frame' fixed or 'carriage'), the screw (thread, length, head), the head's seat point
    and the direction it goes in, the stack under its head (each layer's thickness, from the head down), what it threads
    into, and the two parts it holds together.
The positions come from the same constants the parts are built from (cad/rig_parts.py, cad/build_rig.py).

Slot data (8-series, 10 mm slot) not read from a maker's drawing yet, so the numbers the stacks rest on are named here
and listed in docs/leg-rig-sections.md to check on arrival: SLOT['lip'] (the slot's wall the drop-in nut pulls against),
SLOT['nut'] (a drop-in nut's thread length), SLOT['room'] (the groove's depth left behind the nut).
"""
from __future__ import annotations

import math

import cadquery as cq

import fivebar as fb
import rig_parts as rp

SLOT = {'lip': 3.0, 'nut': {'M4': 4.0, 'M5': 5.0, 'M6': 5.0, 'M8': 6.0}, 'room': 3.0, 'groove_w': 16.5, 'groove_d': 12.0}
SHCS = {'M4': (7.0, 4.0), 'M5': (8.5, 5.0), 'M6': (10.0, 6.0), 'M8': (13.0, 8.0), '3/8-16': (14.29, 9.53)}   # head d, k
BHCS = {'M8': (14.0, 4.4)}                                                                                    # ISO 7380
DIA = {'M4': 4.0, 'M5': 5.0, 'M6': 6.0, 'M8': 8.0, '3/8-16': 9.525}
WASHERS = {'M5': (10.0, 1.0), 'M6L': (18.0, 1.6), '3/8': (20.6, 1.65), '3/8_2in': (50.8, 3.0)}                 # OD, t
INSERT = {'M4': (6.4, 3.0), 'M5': (7.9, 3.1)}         # installed length, the pilot's depth past it
HG_THREAD = 5.0                                       # HGH15CA's M4 mounting threads (HIWIN: M4 x 5)
SHAFT_THREAD = 19.05                                  # the ballast shafts' 3/8-16 thread, 3/4 in deep (McMaster 6649K433)
WOOD_DEPTH = rp.DECK_T                                # a wood screw's room in the deck


def _plane(origin, x_dir, normal):
    return cq.Plane(origin=tuple(origin), xDir=tuple(x_dir), normal=tuple(normal))


def _perp(v):
    v = cq.Vector(*v)
    a = cq.Vector(1, 0, 0) if abs(v.x) < 0.9 else cq.Vector(0, 1, 0)
    return a.cross(v).normalized()


def screw(seat, into, thread: str, length: float, head='shcs', washer=None):
    """A screw with its head on `seat` (the bearing face, washer included when given) pointing along `into`."""
    n = cq.Vector(*into).normalized()
    d = DIA[thread]
    dk, k = (BHCS if head == 'bhcs' else SHCS)[thread]
    off = 0.0
    parts = []
    wp = cq.Workplane(_plane(seat, _perp(n), -n))          # local +z points out of the joint (against `into`)
    if washer:
        od, t = WASHERS[washer]
        parts.append(wp.circle(od / 2).circle(d / 2 + 0.3).extrude(t))
        off = t
    parts.append(cq.Workplane(_plane(cq.Vector(*seat) - n * off, _perp(n), -n)).circle(dk / 2).extrude(k))
    parts.append(cq.Workplane(_plane(cq.Vector(*seat) - n * off, _perp(n), -n)).circle(d / 2 - 0.15).extrude(-length))
    s = parts[0]
    for p in parts[1:]:
        s = s.union(p)
    return s


def l_bracket(corner, a, b, leg: float = 35.0, width: float = 18.0, t: float = 4.5):
    """A cast corner bracket in the concave corner at `corner`: one leg along `a` (on the face b points away from),
    the other along `b`; a gusset between them."""
    a, b = cq.Vector(*a).normalized(), cq.Vector(*b).normalized()
    wp = cq.Workplane(_plane(corner, a, a.cross(b)))
    s = wp.box(leg, t, width, centered=(False, False, True)).union(wp.box(t, leg, width, centered=(False, False, True)))
    g = (cq.Workplane(_plane(corner, a, a.cross(b))).polyline([(t, t), (leg * 0.7, t), (t, leg * 0.7)]).close()
         .extrude(t / 2, both=True))
    return s.union(g)


def hg_rail(x: float, y0: float, z0: float, length: float):
    """HGR15 rail: 15 x 15, counterbored for M4 at P 60 (E 20 from the bottom end)."""
    r = rp.HG15
    s = rp.box(x - r['rail_w'] / 2, x + r['rail_w'] / 2, y0, y0 + r['rail_h'], z0, z0 + length)
    for sx in (-1, 1):                                       # the ball grooves on the flanks (2 mm deep, 4 wide)
        s = s.cut(rp.box(x + sx * r['rail_w'] / 2 - 1.0, x + sx * r['rail_w'] / 2 + 1.0, y0 + 9.0, y0 + 13.0, z0 - 1, z0 + length + 1))
    z = z0 + r['E']
    while z < z0 + length - 5:
        s = s.cut(rp.cyl(2.25, 'y', y0 - 1, y0 + r['rail_h'] + 1, x, z)).cut(rp.cyl(3.75, 'y', y0 + r['rail_h'] - 5.3, y0 + r['rail_h'] + 1, x, z))
        z += r['P']
    return s


def rail_holes(z0: float, length: float):
    zs, z = [], z0 + rp.HG15['E']
    while z < z0 + length - 5:
        zs.append(z)
        z += rp.HG15['P']
    return zs


def hg_block(x: float, z: float, y_rail: float):
    """HGH15CA block on a rail whose base is at y_rail: the steel body (39.4 long), the end caps and seals, the channel
    round the rail (0.3 mm clear: the balls carry it), four M4 x 5 threads on its top."""
    r = rp.HG15
    y_b, y_t = y_rail + r['H1'], y_rail + r['H']
    body = rp.box(x - r['W'] / 2, x + r['W'] / 2, y_b, y_t, z - 19.7, z + 19.7)
    caps = rp.box(x - r['W'] / 2 + 1.5, x + r['W'] / 2 - 1.5, y_b + 1.0, y_t - 1.5, z - r['L'] / 2, z + r['L'] / 2)
    s = body.union(caps)
    s = s.cut(rp.box(x - r['rail_w'] / 2 - 0.3, x + r['rail_w'] / 2 + 0.3, y_b - 1, y_rail + r['rail_h'] + 0.3, z - r['L'] / 2 - 1, z + r['L'] / 2 + 1))
    for dx in (-r['B'] / 2, r['B'] / 2):
        for dz in (-r['C'] / 2, r['C'] / 2):
            s = s.cut(rp.cyl(1.7, 'y', y_t - HG_THREAD, y_t + 1, x + dx, z + dz))
    return s


def free_angle_hinge(post_pt, brace_pt, u, axis_x: float = 0.0, plate_normal=(0, 1, 0)):
    """A free-angle bracket at a brace end: a leaf on the member (its face through post_pt, normal plate_normal), a
    barrel on the hinge axis (along x through brace_pt), a leaf on the brace's end face (normal u, the brace's axis)."""
    n = cq.Vector(*plate_normal).normalized()
    pp, bp, u = cq.Vector(*post_pt), cq.Vector(*brace_pt), cq.Vector(*u).normalized()
    leaf1 = cq.Workplane(_plane(pp, (1, 0, 0), n)).rect(40, 40).extrude(5)                      # on the member's face
    barrel = rp.cyl(7.0, 'x', axis_x - 20, axis_x + 20, bp.y, bp.z)
    tab1 = _segment(pp + n * 5, bp, 16.0, (axis_x - 20, axis_x - 1))                           # member leaf to barrel
    end = bp - u * 14.0
    leaf2 = cq.Workplane(_plane(end, (1, 0, 0), -u)).rect(40, 40).extrude(6)                    # on the brace's end
    tab2 = _segment(end, bp, 16.0, (axis_x + 1, axis_x + 20))
    return leaf1.union(barrel).union(tab1).union(leaf2).union(tab2)


def _segment(p, q, w, xr):
    """A web from p to q (both in a y-z plane), w thick, across x range xr."""
    d = q - p
    L = d.Length
    ang = math.degrees(math.atan2(d.z, d.y))
    s = rp.box(xr[0], xr[1], 0, L, -w / 2, w / 2).rotate((0, 0, 0), (1, 0, 0), ang).translate((0, p.y, p.z))
    return s


# ----------------------------------------------------------------------------------- the joint table

def joints(zh_carriage: float = 0.0) -> list:
    """Every screwed joint of the rig: dicts with 'name', 'body', 'thread', 'length', 'head', 'washer', 'seat'
    (x, y, z in the deck frame; carriage ones at hip height zh_carriage), 'into' (unit vector), 'clamp' (mm, from the
    head down), 'thread_in' (kind, depth, beyond), 'holds' (two part names), 'qty' (1 per row)."""
    import build_rig as br                                     # the layout lives there
    J = []
    L = SLOT['lip']

    def slot(th):
        return {'kind': 'slot_nut', 'depth': SLOT['nut'][th], 'beyond': SLOT['room']}

    zc = br.Z_FRAME_TOP - 20.0
    # the deck: 8 x M6 x 30 + large washer into the members' top slots
    deck_pts = [('front_member', x) for x in (-260.0, -100.0, 100.0, 260.0)] + [('wheel_member', x) for x in (-260.0, 260.0)] + \
               [('bumper_member', x) for x in (-260.0, 260.0)]
    for m, x in deck_pts:
        y = br.CROSS[m.split('_')[0]]
        J.append({'name': f'deck_screw_{m}_{x:+.0f}', 'body': 'frame', 'thread': 'M6', 'length': 30.0, 'head': 'shcs',
                  'washer': 'M6L', 'seat': (x, y, 0.0), 'into': (0, 0, -1), 'clamp': [WASHERS['M6L'][1], rp.DECK_T, L],
                  'thread_in': slot('M6'), 'holds': ('deck', m)})
    # the bottom bumpers' bases: 2 x M6 x 35 each, counterbored, through the deck into the bumper member's slot
    hb = rp.bumper_base_h()
    for sx, side in ((-1, 'left'), (1, 'right')):
        for dx in (-15.0, 15.0):
            J.append({'name': f'bumper_screw_{side}_{dx:+.0f}', 'body': 'frame', 'thread': 'M6', 'length': 35.0, 'head': 'shcs',
                      'washer': None, 'seat': (sx * rp.BUMPER['x'] + dx, br.CROSS['bumper'], hb - 14.0), 'into': (0, 0, -1),
                      'clamp': [hb - 14.0, rp.DECK_T, L], 'thread_in': slot('M6'), 'holds': (f'bumper_base_{side}', 'bumper_member')})
    # the top stop: 4 x M8 x 16 into the post's front slots above the rails (6 mm under each head)
    z0 = rp.top_stop_z(br.RAIL_TOP) - 2.0
    for sx in (-1, 1):
        for z in (rp.BUMPER['tpu_h'] + 2.0 + 25.0, rp.BUMPER['tpu_h'] + 2.0 + 48.0):
            J.append({'name': f'top_stop_screw_{sx:+d}_{z:.0f}', 'body': 'frame', 'thread': 'M8', 'length': 16.0, 'head': 'shcs',
                      'washer': None, 'seat': (sx * 20.0, rp.Y_POST_FRONT + 6.0, z0 + z), 'into': (0, -1, 0),
                      'clamp': [6.0, L], 'thread_in': slot('M8'), 'holds': ('top_stop_bracket', 'post')})
    # the pod: 4 x M8 x 16 through its 6 mm mounting pads into the post's back slots
    for z in (40.0, rp.POD['h'] - 40.0):
        for x in (-20.0, 20.0):
            J.append({'name': f'pod_screw_{x:+.0f}_{z:.0f}', 'body': 'frame', 'thread': 'M8', 'length': 16.0, 'head': 'shcs',
                      'washer': None, 'seat': (x, rp.Y_POST_BACK - rp.POD['pad'], br.POD_Z + z), 'into': (0, 1, 0),
                      'clamp': [rp.POD['pad'], L], 'thread_in': slot('M8'), 'holds': ('pod', 'post')})
    # the rails: M4 x 16 at every hole into drop-in nuts in the post's front slots (9.7 mm of rail under each head)
    for sx in (-1, 1):
        for z in rail_holes(rp.RAIL_Z0, rp.RAIL_LEN):
            J.append({'name': f'rail_screw_{sx:+d}_{z:.0f}', 'body': 'frame', 'thread': 'M4', 'length': 16.0, 'head': 'shcs',
                      'washer': None, 'seat': (sx * rp.BLOCK_X, rp.Y_POST_FRONT + rp.HG15['rail_h'] - 5.3, z), 'into': (0, -1, 0),
                      'clamp': [rp.HG15['rail_h'] - 5.3, L], 'thread_in': slot('M4'), 'holds': (f'rail_{"left" if sx < 0 else "right"}', 'post')})
    # the corner brackets: their own M8 screws and drop-in nuts (the maker's kit), one into each member
    # the ToF sensor's mount: 2 wood screws (M4 x 16) into the deck, 2.5 mm of the mount under each head
    for dx in rp.TOF_MOUNT_SCREWS_X:
        J.append({'name': f'tof_mount_screw_{dx:+.0f}', 'body': 'frame', 'thread': 'M4', 'length': 16.0, 'head': 'shcs', 'washer': None,
                  'seat': (rp.TOF['x'] + dx, (rp.Y_PLATE_FRONT + rp.Y_PLATE_BACK) / 2 + 3.0, 2.5), 'into': (0, 0, -1),
                  'clamp': [2.5], 'thread_in': {'kind': 'wood', 'depth': WOOD_DEPTH - 2.0, 'beyond': 2.0}, 'min_engage': 8.0,
                  'holds': ('tof_mount', 'deck')})
    for z in rp.PENDANT_SCREWS_Z:                                # the pendant's clip: 2 x M4 x 10 into the pod's inserts
        J.append({'name': f'pendant_clip_screw_{z:.0f}', 'body': 'frame', 'thread': 'M4', 'length': 10.0, 'head': 'shcs', 'washer': None,
                  'seat': (rp.POD['d'] / 2 + 6.0, rp.Y_POST_BACK + rp.PENDANT_AT[0], br.POD_Z + rp.PENDANT_AT[1] + z), 'into': (-1, 0, 0),
                  'clamp': [6.0], 'thread_in': {'kind': 'insert', 'depth': INSERT['M4'][0], 'beyond': rp.POD['wall'] + 4.0 - INSERT['M4'][0]},
                  'min_engage': 3.5, 'holds': ('pendant_clip', 'pod')})
    # ---- the carriage (at hip height zh_carriage)
    zh = zh_carriage
    for sx in (-1, 1):                                          # the blocks: 16 x M4 x 10 from the plate's front
        for sz in (-1, 1):
            for dx in (-1, 1):
                for dz in (-1, 1):
                    x = sx * rp.BLOCK_X + dx * rp.HG15['B'] / 2
                    z = sz * rp.BLOCK_Z + dz * rp.HG15['C'] / 2
                    J.append({'name': f'block_screw_{sx:+d}{sz:+d}_{dx:+d}{dz:+d}', 'body': 'carriage', 'thread': 'M4', 'length': 10.0,
                              'head': 'shcs', 'washer': None, 'seat': (x, rp.Y_PLATE_FRONT, zh + z), 'into': (0, -1, 0),
                              'clamp': [rp.PLATE_T], 'thread_in': {'kind': 'tapped', 'depth': HG_THREAD, 'beyond': 0.0},
                              'min_engage': 0.8 * 4.0, 'holds': ('carriage_plate', f'block_{sx:+d}{sz:+d}')})
    for (x, z) in rp.FM['inserts_xz']:                          # the hip frame: 6 x M5 x 16 + washer from the plate's back
        J.append({'name': f'frame_screw_{x:+.0f}{z:+.0f}', 'body': 'carriage', 'thread': 'M5', 'length': 16.0, 'head': 'shcs',
                  'washer': 'M5', 'seat': (x, rp.Y_PLATE_BACK, zh + z), 'into': (0, 1, 0), 'clamp': [WASHERS['M5'][1], rp.PLATE_T],
                  'thread_in': {'kind': 'insert', 'depth': INSERT['M5'][0], 'beyond': INSERT['M5'][1]}, 'min_engage': 5.0,
                  'holds': ('carriage_plate', 'leg_hip_frame')})
    for sx in (-1, 1):                                          # the ballast posts: 3/8-16 x 1 + washer from the plate's front
        x = sx * rp.BALLAST_X
        J.append({'name': f'ballast_screw_{sx:+d}', 'body': 'carriage', 'thread': '3/8-16', 'length': 25.4, 'head': 'shcs',
                  'washer': '3/8', 'seat': (x, rp.Y_PLATE_FRONT, zh + rp.BALLAST_Z), 'into': (0, -1, 0),
                  'clamp': [WASHERS['3/8'][1], rp.PLATE_T], 'thread_in': {'kind': 'tapped', 'depth': SHAFT_THREAD, 'beyond': 0.0},
                  'min_engage': 9.525, 'holds': ('carriage_plate', f'ballast_shaft_{sx:+d}')})
        y_end = rp.Y_PLATE_BACK - rp.SHAFT['len']               # the shaft's back end: the 2 in washer and a 3/8-16 x 3/4
        J.append({'name': f'ballast_keeper_{sx:+d}', 'body': 'carriage', 'thread': '3/8-16', 'length': 19.05, 'head': 'shcs',
                  'washer': '3/8_2in', 'seat': (x, y_end, zh + rp.BALLAST_Z), 'into': (0, 1, 0),
                  'clamp': [WASHERS['3/8_2in'][1]], 'thread_in': {'kind': 'tapped', 'depth': SHAFT_THREAD, 'beyond': 0.0},
                  'min_engage': 9.525, 'holds': (f'ballast_shaft_{sx:+d}', f'ballast_shaft_{sx:+d}')})
    for (x, z) in rp.TOF_HOLES:                                 # the ToF target arm: M4 x 10 from the plate's back into inserts
        J.append({'name': f'tof_arm_screw_{z:+.0f}', 'body': 'carriage', 'thread': 'M4', 'length': 10.0, 'head': 'shcs', 'washer': None,
                  'seat': (x, rp.Y_PLATE_BACK, zh + z), 'into': (0, 1, 0), 'clamp': [rp.PLATE_T],
                  'thread_in': {'kind': 'insert', 'depth': INSERT['M4'][0], 'beyond': INSERT['M4'][1]}, 'min_engage': 3.5,
                  'holds': ('carriage_plate', 'tof_arm')})
    for j in J:
        j['d'] = DIA[j['thread']]
    return J


def screw_rows(J: list) -> list:
    """The table in assembly_checks.screw_stacks()'s form."""
    return [{'joint': j['name'], 'd': j['d'], 'length': j['length'], 'clamp': j['clamp'], 'thread': j['thread_in'],
             # 0.8 d of steel thread (an ISO nut's height), or the whole of a drop-in nut thinner than that
             'min_engage': j.get('min_engage', min(0.8 * j['d'], j['thread_in']['depth']) if j['thread_in']['kind'] == 'slot_nut' else 0.8 * j['d']),
             'name': f"{j['thread']} x {j['length']:g}"} for j in J]


def screw_shapes(J: list) -> dict:
    return {j['name']: screw(j['seat'], j['into'], j['thread'], j['length'], j['head'], j['washer']) for j in J}


# ----------------------------------------------------------------------------------- the brackets

def corner_brackets() -> dict:
    """The base's cast corner brackets (two per joint where both faces are free) and the post's four at its foot."""
    import build_rig as br
    zc = br.Z_FRAME_TOP - 20.0
    inner = br.X_SIDE - 20.0
    out = {}
    halfw = {'post_member': 40.0}
    members = {**{f'{k}_member': y for k, y in br.CROSS.items()}, 'post_member': br.Y_POST_C}
    faces = []
    for m, y in members.items():
        h = halfw.get(m, 20.0)
        for side in (1, -1):
            faces.append((m, y + side * h, side))
    taken = {}
    for m, yf, side in faces:                                   # a face another member lies against has no room
        blocked = any(abs(yf - (y2 - side * halfw.get(m2, 20.0))) < 1e-6 for m2, y2 in members.items() if m2 != m)
        if blocked:
            continue
        for sx in (-1, 1):
            corner = (sx * inner, yf, zc)
            out[f'bracket_{m}_{"front" if side > 0 else "back"}_{"right" if sx > 0 else "left"}'] = l_bracket(corner, (-sx, 0, 0), (0, side, 0))
    for sx in (-1, 1):                                          # the post's foot: on its side faces, the leg on the member
        for dy in (-20.0, 20.0):
            out[f'bracket_post_{"right" if sx > 0 else "left"}_{dy:+.0f}'] = l_bracket((sx * 40.0, br.Y_POST_C + dy, br.Z_FRAME_TOP),
                                                                                       (sx, 0, 0), (0, 0, 1), width=16.0)
    return out
