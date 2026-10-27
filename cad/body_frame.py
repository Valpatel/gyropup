"""The body's frame (milestone M5, task T2): the parts that carry both hip modules, the compute, the battery and the
power skid, and the deck that carries the lidar and the turret. Robot frame (mm), see cad/body_params.py.

    import body_frame as bf
    parts = bf.frame_parts(layout_mounts)      # {name: Part}: SendCutSend sheet, printed, bought (envelopes)
    asm = bf.assembled(parts)                  # {name: (shape in the robot frame, kind, colour)}

The spine: two identical C-channel cheeks (SendCutSend 5052-H32 3/16 in, two bends, eight PEM SS-M5-0 nuts each), held
31 mm apart by eight M4 x 31 hex standoffs in the hip frames' bolt rows (M4 flat heads flush in countersinks on the
frame side). Each hip frame bolts to its own cheek's outer face with its six M5 inserts (M5 x 12 ISO 7380 button heads
from inside the gap, 3 mm hex, 3 N m). The floor tray (5052-H32 0.100 in, 15 mm lips down) lies on the cheeks' upper
flanges, the belly plate (6061-T6 0.100 in) under their lower flanges; with the standoffs that makes a closed box
between the legs. The deck (5052-H32 0.100 in, lips down) stands on four printed PA6-CF posts over the tray; the
compute pallet (6061-T6 0.125 in, countersunk) sits on four printed TPU isolators on the tray; the power plate on four
printed posts; the turret's riser (printed PA6-CF) on the deck.
"""
from __future__ import annotations

import functools
import json
import math
import os
from dataclasses import dataclass, field

import cadquery as cq

import body_params as bp
import body_sheet as bs

T5 = bp.STOCK[bp.CHEEK]['t']             # cheek thickness
GAP_Y = bp.SPACER_L / 2                  # the cheeks' inner (gap-side) faces at y = +-GAP_Y
FACE_Y = bp.SPINE_W / 2                  # their outer faces, where the hip frames bear
ZT = bp.z_spine_top()                    # the cheeks' flange outer faces: z = +-ZT
CHEEK_H = 2 * ZT
CHEEK_L = bp.SPINE_X[1] - bp.SPINE_X[0]
PEM_W = None                             # set below: the flange nuts' distance from the gap-side face


@dataclass
class Part:
    name: str
    kind: str                    # 'sheet' | 'printed' | 'bought'
    shape: object                # in the robot frame
    qty: int = 1
    sheet: bs.SheetPart = None   # sheet parts: the definition (flat pattern, order, checks)
    local: object = None         # sheet parts: the formed solid in the part's own frame
    material: str = ''
    mass_g: float = None
    note: str = ''
    colour: tuple = (0.6, 0.6, 0.6)
    print_rotation: tuple = None  # printed parts: rotation onto the bed (axis, deg)


# ------------------------------------------------------------------------------------------- helpers

def box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def hexagon_z(af, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).polygon(6, af / math.cos(math.pi / 6)).extrude(z1 - z0)


def hexagon_y(af, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).polygon(6, af / math.cos(math.pi / 6)).extrude(y1 - y0)


def button_head_y(d, length, y_face, direction, x, z):
    """An ISO 7380 button head screw along y: the head's underside on y_face, the shank going `direction` (+1/-1)."""
    head_d, head_h = {3: (5.7, 1.65), 4: (7.6, 2.2), 5: (9.5, 2.75), 6: (10.5, 3.3)}[int(d)]
    s = direction
    head = cyl_y(head_d / 2, min(y_face, y_face - s * head_h), max(y_face, y_face - s * head_h), x, z)
    shank = cyl_y(d / 2, min(y_face, y_face + s * length), max(y_face, y_face + s * length), x, z)
    return head.union(shank)


def button_head_z(d, length, z_face, direction, x, y):
    head_d, head_h = {3: (5.7, 1.65), 4: (7.6, 2.2), 5: (9.5, 2.75), 6: (10.5, 3.3)}[int(d)]
    s = direction
    head = cyl_z(head_d / 2, min(z_face, z_face - s * head_h), max(z_face, z_face - s * head_h), x, y)
    shank = cyl_z(d / 2, min(z_face, z_face + s * length), max(z_face, z_face + s * length), x, y)
    return head.union(shank)


# ------------------------------------------------------------------------------------------- the cheeks (spine)

def cheek_to_part(x, z):
    """Left cheek, robot (x, z) -> part (u, v)."""
    return (bp.SPINE_X[1] - x, z + ZT)


def place_cheek(shape, side='left'):
    """Part frame (base outer face z = 0 is the gap-side face; flanges towards +z = outwards) -> robot frame."""
    s = shape.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 180).translate((bp.SPINE_X[1], GAP_Y, -ZT))
    return s if side == 'left' else s.rotate((0, 0, 0), (0, 0, 1), 180)


def pem_w(stock=bp.CHEEK, spec='SS-M5-0'):
    """Where a flange's PEM nut goes (OML distance from the base's outer face): half a die from the bend's centreline
    (hole edge), N from the bend area, and K from the free edge (the flange is long enough for both)."""
    s, P = bp.STOCK[stock], bp.PEM[spec]
    lo = max(s['ossb'] + (s['half_die'] - s['ba'] / 2) + P['H'] / 2, s['ossb'] + P['N'])
    hi = bp.CHEEK_FLANGE - P['K']
    if lo > hi:
        raise ValueError(f'flange {bp.CHEEK_FLANGE} mm too short for {spec}: needs {lo:.2f}..{hi:.2f}')
    return round((lo + hi) / 2, 2)


PEM_W = pem_w()
PEM_Y = GAP_Y + PEM_W                    # robot |y| of the flange nuts (and of the tray's and belly's screws)
FLANGE_NUT_X = (-62.0, -20.0, 20.0, 62.0)       # clear of the frame's insert bosses at x = 0, +-83 (12.5 mm round
                                                # each) and K from the cheek's ends
# the standoffs stand in the hip frames' bolt rows (z = +-67.5, 2.5 mm inside the bolts' +-70), beside the bolts (x 0 and
# +-83): each leg's roll moment reaches its cheek as a push at one bolt row and a pull at the other, and the standoffs
# carry it straight across to the
# other frame in compression and tension instead of bending the cheeks' webs. cad/body_studies.py S1 at the rig's loads
# on the body (2026-10-27, 3/16 in cheeks): this layout SF 1.96 (2.29 away from the standoffs' bonded ends); three at
# z +-40..45 (x 0, +-80) 0.92 (2.67 away: their ends take the bolt rows' load); none 1.33. The frame screw at x 0 has
# 1.2 mm between its head and the hexes either side: the key's short arm goes in between
SPACER_HEX = 6.0                         # McMaster 95947A065 (M4 x 31, 6 mm hex)
SPACERS_XZ = [(10.0, 67.5), (-10.0, 67.5), (72.0, 67.5), (-72.0, 67.5), (10.0, -67.5), (-10.0, -67.5), (72.0, -67.5), (-72.0, -67.5)]
if os.environ.get('GYROPUP_BODY_SPACERS'):          # a study can try another layout (cad/body_studies.py)
    SPACERS_XZ = [tuple(p) for p in json.loads(os.environ['GYROPUP_BODY_SPACERS'])]


def harness_windows():
    """Where each RS-04's harness leaves its motor (left leg, robot x-z): the leg's own clocking (fivebar.harness_angle:
    the grommet, a radial exit at r 58 near the rear cover, points out nearest level, the front motor forwards and the
    rear one backwards). Both now leave past the cheek's ends, so they need no window: each lead turns in round the
    cheek's end into the spine's gap (the cable chase) and up through the tray's slot. The right leg is the left one
    turned 180 deg about z, so its exits are these with x negated. [(name, (x, z), angle)]"""
    fb = bp._fivebar()
    out = []
    for (mx, front) in ((fb.motors()[0][0], True), (fb.motors()[1][0], False)):
        a = fb.harness_angle(front)
        ex = (mx + RS04_EXIT_R * math.cos(math.radians(a)), RS04_EXIT_R * math.sin(math.radians(a)))
        out.append(('rs04_front' if front else 'rs04_rear', ex, a))
    return out


RS04_EXIT_R = 58.0            # the harness grommet's radius from the motor axis (cad/fivebar.py RS04_HARNESS)


def cheek_windows():
    """(name, x0, x1, z0, z1, corner r) of the cheek's windows, left cheek, robot frame; sized round the exits and
    kept clear of the frame's bearing faces (|z| 60..74 within |x| <= 95), half a die from the flanges' bends, and a
    thickness plus 2 mm inside the cheek's ends (a window is shifted along x, not cut short)."""
    s = bp.STOCK[bp.CHEEK]
    end = s['t'] + 2.0
    out = [('wheel_harness', -20.0, 20.0, -25.0, 25.0, 6.0)]
    for name, (ex, ez), a in harness_windows():
        if ex + 6.0 >= bp.SPINE_X[1] or ex - 6.0 <= bp.SPINE_X[0]:   # past the cheek's end: the harness drops beside it
            continue
        x0, x1 = ex - 16.0, ex + 16.0
        if x1 > bp.SPINE_X[1] - end:
            x0, x1 = x0 - (x1 - (bp.SPINE_X[1] - end)), bp.SPINE_X[1] - end
        if x0 < bp.SPINE_X[0] + end:
            x0, x1 = bp.SPINE_X[0] + end, x1 + (bp.SPINE_X[0] + end - x0)
        if ez < 0:            # going down: a window above the frame's lower bearing face
            z0, z1 = max(-57.0, ez - 9.0), ez + 15.0
        else:                 # going up under the upper flange: the window stops below the flange's bearing face
            z0, z1 = ez - 15.0, min(57.0, ez + 9.0)
        out.append((name, round(x0, 1), round(x1, 1), round(z0, 1), round(z1, 1), 5.0))
    return out


def cheek_part() -> bs.SheetPart:
    """One C-channel cheek (CHEEK_L x CHEEK_H OML, two CHEEK_FLANGE flanges outwards): holes for the hip frame's six
    inserts, countersinks for the standoffs, the harness windows; SS-M5-0 nuts in both flanges for the tray and the belly."""
    feats = []
    m = bp.frame_mounts()
    for x, z in m['holes']:
        feats.append(bs.Feature('hole', 'base', cheek_to_part(x, z), 5.5, note='hip frame insert, M5 x 12 ISO 7380 from the gap'))
    for x, z in SPACERS_XZ:                  # countersunk on the frame side: the heads sit flush under the motors' covers
        feats.append(bs.Feature('csk', 'base', cheek_to_part(x, z), 4.5, spec='M4', side='z1', note='M4 x 31 hex standoff, M4 x 10 flat head'))
    for name, x0, x1, z0, z1, r in cheek_windows():
        u0, v0 = cheek_to_part(x1, z0)
        u1, v1 = cheek_to_part(x0, z1)
        feats.append(bs.Feature('slot', 'base', ((u0 + u1) / 2, (v0 + v1) / 2), size=(u1 - u0, v1 - v0, r), note=name))
    for x in FLANGE_NUT_X:
        for edge in ('N', 'S'):
            feats.append(bs.Feature('pem', edge, (bp.SPINE_X[1] - x, PEM_W), bp.PEM['SS-M5-0']['H'], spec='SS-M5-0',
                                    note='floor tray' if edge == 'N' else 'belly plate'))
    return bs.SheetPart('cheek', bp.CHEEK, CHEEK_L, CHEEK_H, flanges=[bs.Flange('S', bp.CHEEK_FLANGE), bs.Flange('N', bp.CHEEK_FLANGE)],
                        features=feats, qty=2,
                        note='one part for both sides (the right cheek is the left one turned 180 deg about z); '
                             'bends both 90 deg the same way; PEM SS-M5-0 pressed from the flanges\' inner (frame) side')


# ------------------------------------------------------------------------------------------- tray, belly, deck, pallet

def place_tray(shape, z_top):
    """A tray-like part (flanges towards +z in its frame) upside down with its base's outer (top) face at z_top, its
    part (u, v) = (x + 160, 127 - y)."""
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((bp.BODY_X[0], bp.BODY_HALF_Y, z_top))


def tray_uv(x, y):
    return (x - bp.BODY_X[0], bp.BODY_HALF_Y - y)


def tray_part(mounts=None) -> bs.SheetPart:
    """The floor tray: 320 x 254, 15 mm lips down; screws into the cheeks' upper flange nuts; the posts' screws; the
    holes the layout asks for (mounts['tray']: [(x, y, d, note) | ('slot', x, y, lx, ly, r, note) | ('pem', x, y, spec, note)])."""
    feats = []
    for x in FLANGE_NUT_X:
        for s in (1, -1):
            feats.append(bs.Feature('hole', 'base', tray_uv(x, s * PEM_Y), 5.5, note='M5 x 10 ISO 7380 into the cheek flange nut'))
    for (x, y) in bp.POSTS:
        feats.append(bs.Feature('hole', 'base', tray_uv(x, y), 5.5, note='post, M5 x 12 ISO 7380 from below'))
    feats += _mount_features((mounts or {}).get('tray', []), tray_uv)
    return bs.SheetPart('floor_tray', bp.TRAY, bp.BODY_X[1] - bp.BODY_X[0], 2 * bp.BODY_HALF_Y,
                        flanges=[bs.Flange(e, bp.TRAY_LIP) for e in ('S', 'N', 'W', 'E')], features=feats,
                        note='lips 15 mm down all round, open corners with round reliefs')


def _mount_features(rows, uv):
    out = []
    for r in rows:
        if r[0] == 'slot':
            _, x, y, lx, ly, rad, note = r
            u, v = uv(x, y)
            out.append(bs.Feature('slot', 'base', (u, v), size=(lx, ly, rad), note=note))
        elif r[0] == 'pem':
            _, x, y, spec, note = r
            out.append(bs.Feature('pem', 'base', uv(x, y), bp.PEM[spec]['H'], spec=spec, note=note))
        elif r[0] == 'csk':
            _, x, y, spec, d, note = r
            out.append(bs.Feature('csk', 'base', uv(x, y), d, spec=spec, note=note))
        else:
            x, y, d, note = r
            out.append(bs.Feature('hole', 'base', uv(x, y), d, note=note))
    return out


def belly_uv(x, y):
    return (x - bp.BODY_X[0], bp.BELLY_HALF_Y - y)


def place_belly(shape):
    """Flat part: part (u, v, 0..t) -> robot, its top face (part z = 0) against the cheeks' lower flanges."""
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((bp.BODY_X[0], bp.BELLY_HALF_Y, -ZT))


def belly_part(mounts=None) -> bs.SheetPart:
    feats = []
    for x in FLANGE_NUT_X:
        for s in (1, -1):
            feats.append(bs.Feature('hole', 'base', belly_uv(x, s * PEM_Y), 5.5, note='M5 x 10 ISO 7380 up into the cheek flange nut'))
    feats += _mount_features((mounts or {}).get('belly', []), belly_uv)
    return bs.SheetPart('belly_plate', bp.BELLY, bp.BODY_X[1] - bp.BODY_X[0], 2 * bp.BELLY_HALF_Y, features=feats,
                        note='flat; the power skid hangs under it (the plate is the VESCs\' heat sink)')


def deck_part(mounts=None) -> bs.SheetPart:
    """The deck: 320 x 254, 25 mm lips down; the posts, the lidar (1/4-20 + two Ø4.06 pins), the riser's four
    screws, the fan's intake field inside the riser, the turret harness and lidar cable passes."""
    feats = []
    for (x, y) in bp.POSTS:
        feats.append(bs.Feature('hole', 'base', tray_uv(x, y), 5.5, note='post, M5 x 12 ISO 7380 from above'))
    lid = bp.lidar()
    feats.append(bs.Feature('hole', 'base', tray_uv(lid['x'], 0.0), lid['centre_clear_d'], note='VLP-16 1/4-20 x 3/8 in from below'))
    for (x, y) in lid['pins']:
        feats.append(bs.Feature('hole', 'base', tray_uv(x, y), 3.95, note='VLP-16 locating pin 5/32 in (ream to a light press)'))
    t = bp.tm()
    for (x, y) in RISER_FEET:
        feats.append(bs.Feature('hole', 'base', tray_uv(t['pan_x'] + x, y), 5.5, note='riser, M5 x 12 from below into its insert'))
    for (x, y) in intake_cells():
        feats.append(bs.Feature('slot', 'base', tray_uv(x, y), size=(INTAKE_CELL, INTAKE_CELL, 1.5), note='fan intake'))
    feats += _mount_features((mounts or {}).get('deck', []), tray_uv)
    return bs.SheetPart('deck', bp.DECK, bp.BODY_X[1] - bp.BODY_X[0], 2 * bp.BODY_HALF_Y,
                        flanges=[bs.Flange(e, bp.DECK_LIP) for e in ('S', 'N', 'W', 'E')], features=feats,
                        note='lips 25 mm down all round (its stiffness: the front cantilevers past the front posts)')


INTAKE_CELL = 8.0             # square cells, 3 mm webs: a child's finger does not reach the fan 45 mm below
INTAKE_PITCH = 11.0
INTAKE_R = round((bp.j501().get('fan') or {}).get('blade_diameter', 88.0) / 2 + 2.0, 1)   # the field round the J501 fan's axis: its blades + 2 mm
RISER_FEET = [(40.0, 40.0), (-40.0, 40.0), (-40.0, -40.0), (40.0, -40.0)]     # under the TM bolts (turret.TM_BOLTS)


def intake_cells():
    """The fan's intake field in the deck (robot x, y): square cells on a grid centred on the fan's axis, within
    INTAKE_R of it, under the riser's ring (12 mm inside its edge) and clear of the riser's feet."""
    t = bp.tm()
    fx, fy = bp.j501_stack()['fan_xy']
    out = []
    n = int(INTAKE_R // INTAKE_PITCH) + 1
    half = INTAKE_CELL * 0.71
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = fx + i * INTAKE_PITCH, fy + j * INTAKE_PITCH
            if math.hypot(x - fx, y - fy) + half > INTAKE_R:
                continue
            if math.hypot(x - t['pan_x'], y) + half > t['foot_r'] - 12.0:
                continue
            if any(math.hypot(x - (t['pan_x'] + a), y - b) < RISER_FOOT_R + 3.0 + half for a, b in RISER_FEET):
                continue
            out.append((round(x, 2), round(y, 2)))
    return out


def pallet_uv(x, y):
    return (x - PALLET_X[0], PALLET_Y[1] - y)


PALLET_X = None
PALLET_Y = None


def pallet_part(mounts=None) -> bs.SheetPart:
    """The compute pallet (6061-T6 0.125 in, SendCutSend countersinks): the J501 carrier on four M3 x 16 hex standoffs
    (M3 x 6 flat heads from below), the AGX module's cooler tie-down (four M3 x 35 flat heads up through 16 mm spacer
    tubes into the module-to-heatsink standoffs, the j501-agx rule), four printed TPU isolators to the tray."""
    feats = []
    j = bp.j501()
    for (xp, yp) in j['holes']:
        x, y = bp.pcb_to_robot(xp, yp)
        feats.append(bs.Feature('csk', 'base', pallet_uv(x, y), 3.4, spec='M3', side='z1', note='J501 carrier standoff, M3 x 6 flat head from below'))
    for (xp, yp) in j['module_holes']:
        x, y = bp.pcb_to_robot(xp, yp)
        feats.append(bs.Feature('csk', 'base', pallet_uv(x, y), 3.4, spec='M3', side='z1', note='cooler tie-down, M3 x 35 flat head from below'))
    for (x, y) in ISOLATORS:
        feats.append(bs.Feature('hole', 'base', pallet_uv(x, y), 8.0, note='printed TPU isolator\'s neck; M4 x 20 through it into the tray\'s nut'))
    feats += _mount_features((mounts or {}).get('pallet', []), pallet_uv)
    W, H = PALLET_X[1] - PALLET_X[0], PALLET_Y[1] - PALLET_Y[0]
    u0 = VN_NOTCH[0] - PALLET_X[0]                       # the notch at the front middle: the VN-100 sits on the tray under the
    v0, v1 = PALLET_Y[1] - VN_NOTCH[1], PALLET_Y[1] + VN_NOTCH[1]      # carrier's front, clear of the isolated pallet
    outline = [(0.0, 0.0), (W, 0.0), (W, v0), (u0, v0), (u0, v1), (W, v1), (W, H), (0.0, H)]
    return bs.SheetPart('compute_pallet', bp.PALLET, W, H, features=feats, outline=outline,
                        note='countersinks 90 deg M3 from the underside (SendCutSend countersinking); the notch clears the VN-100')


VN_NOTCH = (-46.0, 22.0)          # (x where the notch starts, its half-width): the VN-100 on the tray under the carrier


def place_pallet(shape):
    z_top = bp.z_pallet_top()
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((PALLET_X[0], PALLET_Y[1], z_top))


def _pallet_box():
    """The pallet's outline: the PCB's four corner holes and the module pattern with a margin, and the isolators."""
    j = bp.j501()
    pts = [bp.pcb_to_robot(*h) for h in j['holes']]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return ((min(xs) - 22.0, max(xs) + 22.0), (min(ys) - 14.0, max(ys) + 14.0))


PALLET_X, PALLET_Y = _pallet_box()
ISOLATORS = [(PALLET_X[0] + 12.0, PALLET_Y[0] + 9.0), (PALLET_X[0] + 12.0, PALLET_Y[1] - 9.0),     # the rear pair 8 mm (flat)
             (PALLET_X[1] - 9.0, PALLET_Y[0] + 9.0), (PALLET_X[1] - 9.0, PALLET_Y[1] - 9.0)]     # from the tray's rear bend


# ------------------------------------------------------------------------------------------- printed parts

POST_H = None


def post_height():
    return bp.TOP - bp.STOCK[bp.DECK]['t'] - bp.z_tray_top()


def post():
    """A deck post (PA6-CF, 100 % solid): square POST_W, M5 heat-set inserts (94459A775, Ø6.4 x 11 pilot) both ends,
    the edges rounded; printed standing (layers across the post: the post is in compression and the inserts pull
    along it, so the pull-out crosses the layers: M3's coupon test covers it)."""
    h = post_height()
    w = bp.POST_W
    s = box(-w / 2, w / 2, -w / 2, w / 2, 0.0, h).edges('|Z').fillet(3.0)
    s = s.cut(cyl_z(3.2, -1.0, 11.0)).cut(cyl_z(3.2, h - 11.0, h + 1.0))
    return s


PLATE_POST_W = 16.0


def plate_post():
    """A power-plate post (PA6-CF, 100 %): 16 mm square x PLATE_H, M5 heat-set inserts (94459A775) both ends; printed
    standing, as the deck posts."""
    import body_layout as bl
    h, w = bl.PLATE_H, PLATE_POST_W
    s = box(-w / 2, w / 2, -w / 2, w / 2, 0.0, h).edges('|Z').fillet(2.5)
    return s.cut(cyl_z(3.2, -1.0, 11.0)).cut(cyl_z(3.2, h - 11.0, h + 1.0))


ISOLATOR_D = 16.0


def isolator():
    """A pallet isolator (TPU 95A, printed): a Ø16 x ISOLATOR_H foot under the pallet with a Ø7.6 x 3.2 neck up through
    the pallet's Ø8 hole, and a separate Ø12 x 3 cap above it; an M4 x 20 socket head with a washer goes down through
    both into the tray's S-M4-0 nut, snug, not tight: the pallet touches only TPU."""
    h = bp.ISOLATOR_H
    foot = cyl_z(ISOLATOR_D / 2, 0.0, h).union(cyl_z(3.8, h, h + bp.STOCK[bp.PALLET]['t'] - 0.2))
    cap = cyl_z(6.0, h + bp.STOCK[bp.PALLET]['t'] + 0.5, h + bp.STOCK[bp.PALLET]['t'] + 3.5)      # Ø12: clear of the carrier's standoffs
    return foot.union(cap).cut(cyl_z(2.3, -1.0, h + 10.0))


def din_rail(length, hole_off=None):
    """A printed TS35 rail piece (PA6-CF): the standard hat (35 wide, 7.5 deep, 27 between the lips), its lips 1.0 mm
    thick for the converters' clips, two M4 countersunk holes. Check the clip on the first print; a cut steel TS35 is the
    fallback."""
    t, w, d, inner = 1.0, 35.0, 7.5, 27.0
    base = box(-inner / 2 + 1.5, inner / 2 - 1.5, -length / 2, length / 2, 0.0, 2.0)
    sides = [box(sx * inner / 2 - (1.5 if sx > 0 else 0.0), sx * inner / 2 + (0.0 if sx > 0 else 1.5), -length / 2, length / 2, 0.0, d)
             for sx in (-1, 1)]
    lips = [box(min(sx * inner / 2, sx * w / 2), max(sx * inner / 2, sx * w / 2), -length / 2, length / 2, d - t, d) for sx in (-1, 1)]
    s = base
    for b in sides + lips:
        s = s.union(b)
    off = hole_off if hole_off is not None else length / 4
    for v in (-off, off):
        s = s.cut(cyl_z(2.25, -1.0, 3.0, 0.0, v)).cut(cyl_z(4.2, 1.0, 3.0, 0.0, v))
    return s


def din_rails(items):
    """The two rail pieces, placed on their PEM nuts (body_layout.mounts_for): {name: (length, hole_off, (x, y, z))}."""
    get = lambda n: next(i for i in items if i.name == n)
    d, dd = get('ddr120c_24'), get('plate_ddr60l_12')
    ya, yb = d.box[2] + 6.0, d.box[2] + 20.0                      # the tray's two S-M4-0 nuts under the 24 V rail
    yc, yd = dd.box[2] + 8.0, dd.box[3] - 8.0                     # the plate's two F-M4-2 nuts under the 12 V rail
    return {'din_rail_24v': (26.0, (yb - ya) / 2, ((d.box[0] + d.box[1]) / 2, (ya + yb) / 2, d.box[4] - 7.5)),
            'din_rail_12v': (60.0, (yd - yc) / 2, ((dd.box[0] + dd.box[1]) / 2, (yc + yd) / 2, dd.box[4] - 7.5))}


RISER_LEG_R = 9.0
RISER_FOOT_R = 18.0         # each leg ends in a Ø36 x 4 foot: it spreads the turret's fall load on the 0.100 in deck (D2)
RISER_FOOT_T = 4.0
RISER_TOP_T = 9.0


def riser():
    """The turret riser (PA6-CF, 100 % solid), in the TM frame (pan axis at the origin, its top face = the TM face at
    z = RISER_H, its feet on z = 0): a Ø144 top ring (the turret's foot) with the TM pattern (4 x M5 inserts on
    80 x 80, 2 x Ø5 dowel holes, the Ø45 hole), four legs under the TM bolts, open sides between them for the J501
    fan's intake air; M5 inserts in the feet for the deck's screws."""
    t = bp.tm()
    H = bp.RISER_H
    ro = t['foot_r']
    ring = cyl_z(ro, H - RISER_TOP_T, H).cut(cyl_z(30.0, H - RISER_TOP_T - 1, H + 1))
    s = ring
    for (x, y) in RISER_FEET:
        s = s.union(cyl_z(RISER_LEG_R, 0.0, H - RISER_TOP_T + 0.01, x, y)).union(cyl_z(RISER_FOOT_R, 0.0, RISER_FOOT_T, x, y))
    for (x, y) in t['bolts']:
        s = s.cut(cyl_z(3.2, H - 9.5, H + 1.0, x, y))                          # M5 insert from the top (the turret)
    for (x, y) in RISER_FEET:
        s = s.cut(cyl_z(3.2, -1.0, 9.5, x, y))                                  # M5 insert from below (the deck)
    for (x, y) in t['dowels']:
        s = s.cut(cyl_z(2.5 - 0.03, H - 8.0, H + 1.0, x, y))
    s = s.cut(cyl_z(t['hole_d'] / 2, H - RISER_TOP_T - 1, H + 1))
    return s


# ------------------------------------------------------------------------------------------- bought parts (envelopes)

def spacers():
    """The eight M4 hex standoffs (McMaster 95947A065: 6 mm hex, 31 mm, female both ends) between the cheeks."""
    out = None
    for x, z in SPACERS_XZ:
        s = hexagon_y(SPACER_HEX, -GAP_Y, GAP_Y, x, z).cut(cyl_y(2.05, -GAP_Y - 1, GAP_Y + 1, x, z))     # threaded through: the screws go in
        out = s if out is None else out.union(s)
    return out


def spacer_screws():
    """Sixteen M4 x 10 ISO 10642 flat heads, flush in the cheeks' countersinks (envelope: the shank and the cone)."""
    out = None
    for x, z in SPACERS_XZ:
        for side in (1, -1):
            y0 = side * FACE_Y
            shank = cyl_y(2.0, min(y0, y0 - side * 10.0), max(y0, y0 - side * 10.0), x, z)
            out = shank if out is None else out.union(shank)
    return out


def frame_screws(side='left'):
    """The six M5 x 12 ISO 7380 per hip frame, heads in the gap on the cheek's inner face."""
    out = None
    m = bp.frame_mounts()
    for x, z in m['holes']:
        p = bp.to_robot((x, m['centre_plane_y'], z), side)
        sgn = 1 if side == 'left' else -1
        s = button_head_y(5, bp.FRAME_SCREW['length'], sgn * GAP_Y, sgn, p[0], p[2])
        out = s if out is None else out.union(s)
    return out


def pem_bodies(part: bs.SheetPart, place):
    """The PEM nuts' bodies (envelopes) on a sheet part, placed: each on the side away from where its screw enters.
    Flange nuts on the cheeks: the screws come from the tray (above) and the belly plate (below), so the bodies hang
    on the flanges' inner sides, towards the frame."""
    out = None
    t = part.t
    for f in part.features:
        if f.kind != 'pem':
            continue
        P = bp.PEM[f.spec]
        (x, y, z), n = part.to3d(f)
        if f.panel == 'base':                # base nuts: body on the part's +z (inner) side
            b = cyl_z(P['body_d'] / 2, t, t + P['body_h'], x, y)
        elif f.panel in ('N', 'S'):          # flange nuts: body on the flange's inner side (towards the base's middle)
            yi = y - t if f.panel == 'N' else y + t
            b = cyl_y(P['body_d'] / 2, min(yi, yi - (P['body_h'] if f.panel == 'N' else -P['body_h'])),
                      max(yi, yi - (P['body_h'] if f.panel == 'N' else -P['body_h'])), x, z)
        else:
            continue
        out = b if out is None else out.union(b)
    return place(out) if out is not None else None


# ------------------------------------------------------------------------------------------- the frame

@functools.lru_cache(maxsize=4)
def _cached_cheek():
    p = cheek_part()
    return p, p.solid()


def frame_parts(mounts=None) -> dict:
    """Every frame part: {name: Part} in the robot frame."""
    out = {}
    cp, cl = _cached_cheek()
    for side in ('left', 'right'):
        out[f'cheek_{side}'] = Part(f'cheek_{side}', 'sheet', place_cheek(cl, side), 1, cp, cl, cp.s['material'],
                                    colour=(0.72, 0.75, 0.80), note=cp.note)
    for name, fn, place, colour in (('floor_tray', tray_part, lambda s: place_tray(s, bp.z_tray_top()), (0.62, 0.66, 0.72)),
                                    ('belly_plate', belly_part, place_belly, (0.55, 0.58, 0.64)),
                                    ('deck', deck_part, lambda s: place_tray(s, bp.TOP), (0.20, 0.22, 0.25)),
                                    ('compute_pallet', pallet_part, place_pallet, (0.70, 0.72, 0.76))):
        sp = fn(mounts)
        loc = sp.solid()
        out[name] = Part(name, 'sheet', place(loc), 1, sp, loc, sp.s['material'], colour=colour, note=sp.note)
    ph = post()
    zt = bp.z_tray_top()
    for k, (x, y) in enumerate(bp.POSTS):
        out[f'post_{k + 1}'] = Part(f'post_{k + 1}', 'printed', ph.translate((x, y, zt)), 1, material='pa6-cf',
                                    colour=(0.25, 0.27, 0.30), note='PA6-CF, 100 % solid, printed standing; 2 x M5 inserts')
    t = bp.tm()
    out['riser'] = Part('riser', 'printed', riser().translate((t['pan_x'], 0.0, bp.TOP)), 1, material='pa6-cf',
                        colour=(0.25, 0.27, 0.30), note='PA6-CF, 100 % solid, printed on its top face; 8 x M5 inserts, 2 x Ø5 dowels',
                        print_rotation=((1, 0, 0), 180))
    iso = isolator()
    for k, (x, y) in enumerate(ISOLATORS):
        out[f'isolator_{k + 1}'] = Part(f'isolator_{k + 1}', 'printed', iso.translate((x, y, zt)), 1, material='tpu95',
                                        colour=(0.15, 0.15, 0.17), note='TPU 95A: the pallet\'s isolator foot, neck and cap')
    import body_layout as _bl
    if mounts is not None:
        for name, (length, off, (x, y, z)) in din_rails(_bl.layout()['items']).items():
            out[name] = Part(name, 'printed', din_rail(length, off).translate((x, y, z)), 1, material='pa6-cf',
                             colour=(0.55, 0.57, 0.6), note='PA6-CF TS35 rail piece; 2 x M4 x 10 flat heads into the nuts below')
    # ---- the power plate (the P0 skid), its standoffs, the bus bars on their insulators
    import body_layout as bl
    pp = power_plate_part(mounts)
    loc = pp.solid()
    out['power_plate'] = Part('power_plate', 'sheet', place_plate(loc), 1, pp, loc, pp.s['material'], colour=(0.66, 0.70, 0.75), note=pp.note)
    zt = bp.z_tray_top()
    pl = plate_post()
    for k, (x, y) in enumerate(PLATE_STANDOFFS):
        out[f'plate_post_{k + 1}'] = Part(f'plate_post_{k + 1}', 'printed', pl.translate((x, y, zt)), 1, material='pa6-cf',
                                          colour=(0.25, 0.27, 0.30), note='PA6-CF, 100 %; M5 inserts both ends; printed standing')
    bus = bus_bar_part()
    bloc = bus.solid()
    ins = bus_insulator()
    zp = zt + bl.PLATE_H + bp.STOCK['5052-0.100']['t']
    if mounts is not None and mounts.get('_bus_xy'):
        for k, (bx, by) in enumerate(mounts['_bus_xy']):
            out[f'bus_bar_{k + 1}'] = Part(f'bus_bar_{k + 1}', 'sheet', bloc.translate((bx, by, zp + 10.0)), 1, bus if k == 0 else None, bloc,
                                           bus.s['material'], colour=(0.85, 0.45, 0.2) if k == 0 else (0.25, 0.25, 0.27), note=bus.note)
            out[f'bus_insulator_{k + 1}'] = Part(f'bus_insulator_{k + 1}', 'printed', ins.translate((bx, by, zp)), 1, material='pa6-cf',
                                                 colour=(0.2, 0.2, 0.22), note='PA6-CF, 100 %; 4 x M3 inserts')
    # ---- the battery bay under the belly plate (printed PETG, TPU skids)
    import body_battery as bb
    for n, sh in bb.bay_parts(bb.brick()).items():
        mat = 'tpu95' if 'skid' in n else 'petg'
        out[n] = Part(n, 'printed', sh, 1, material=mat, colour=(0.15, 0.15, 0.17) if 'skid' in n else (0.85, 0.55, 0.15),
                      note='TPU 95A skid' if 'skid' in n else 'PETG, 3 mm walls; 4 x M5 x 10 up into the belly plate\'s nuts each side')
    out['spacers'] = Part('spacers', 'bought', spacers(), len(SPACERS_XZ), colour=(0.8, 0.8, 0.82), note='M4 x 31 hex standoff, 6 mm hex, female-female, aluminium (95947A065)')
    out['spacer_screws'] = Part('spacer_screws', 'bought', spacer_screws(), 2 * len(SPACERS_XZ), colour=(0.15, 0.15, 0.17), note='M4 x 10 ISO 10642 flat head')
    for side in ('left', 'right'):
        out[f'frame_screws_{side}'] = Part(f'frame_screws_{side}', 'bought', frame_screws(side), 6, colour=(0.15, 0.15, 0.17),
                                           note='M5 x 12 ISO 7380 into the hip frame\'s inserts')
        out[f'cheek_nuts_{side}'] = Part(f'cheek_nuts_{side}', 'bought', pem_bodies(cp, lambda s, sd=side: place_cheek(s, sd)), 8,
                                         colour=(0.6, 0.6, 0.62), note='PEM SS-M5-0 (pressed by SendCutSend)')
    return out


# ------------------------------------------------------------------------------------------- the legs, placed

def legs(h_mm, lean_deg=0.0, with_bought=True):
    """Both legs at a stance in the robot frame: {name: shape}. The left is cad/fivebar.py's module shifted by Y_OFF;
    the right is the same leg turned 180 deg about z (the physical right leg: same parts, same motors)."""
    fb = bp._fivebar()
    phi = fb.stance(h_mm, lean_deg)
    if phi is None:
        return None
    yo = bp.y_off()
    out = {}
    real = fb.gmi.STEP_FRAMES.pop(fb.MOTOR, None)               # the motors as envelopes: fast to intersect
    fb.motor_model.cache_clear()
    try:
        asm = fb.assembly(*phi, with_bought=with_bought)
    finally:
        if real:
            fb.gmi.STEP_FRAMES[fb.MOTOR] = real
        fb.motor_model.cache_clear()
    for n, (s, kind) in asm.items():
        if s is None or n == 'wheel_cable':
            continue
        sl = s.translate((0, yo, 0))
        out[f'L.{n}'] = sl
        out[f'R.{n}'] = sl.rotate((0, 0, 0), (0, 0, 1), 180)
    return out


# ------------------------------------------------------------------------------------------- the power plate and bus bars

def plate_uv(x, y):
    import body_layout as bl
    return (x - bl.PLATE_X[0], bl.PLATE_Y[1] - y)


def place_plate(shape):
    """Flat part (u, v, 0..t) -> robot, its underside (part z = t after the turn) on the standoffs."""
    import body_layout as bl
    z_top = bp.z_tray_top() + bl.PLATE_H + bp.STOCK['5052-0.100']['t']
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((bl.PLATE_X[0], bl.PLATE_Y[1], z_top))


PLATE_STANDOFFS = [(44.0, -96.0), (47.0, 80.0), (145.0, -88.0), (145.0, 80.0)]     # clear of the pallet; 8 mm (flat) from the tray's front bend


def power_plate_part(mounts=None) -> bs.SheetPart:
    """The power plate (5052-H32 0.100 in, flat): the P0 power skid. Four printed posts to the tray; a notch
    round the front-right deck post; PEM nuts and holes for every part on it and under it (mounts['plate'])."""
    import body_layout as bl
    W, H = bl.PLATE_X[1] - bl.PLATE_X[0], bl.PLATE_Y[1] - bl.PLATE_Y[0]
    px, py = bp.POSTS[1]
    nx0 = px - bp.POST_W / 2 - 3.0
    ny1 = py + bp.POST_W / 2 + 3.0
    un, vn = nx0 - bl.PLATE_X[0], bl.PLATE_Y[1] - ny1        # the notch's corner (part u, v): x >= nx0 and y <= ny1 go
    outline = [(0.0, 0.0), (W, 0.0), (W, vn), (un, vn), (un, H), (0.0, H)]
    feats = [bs.Feature('hole', 'base', plate_uv(x, y), 5.5, note='M5 x 10 ISO 7380 down into the post\'s insert') for x, y in PLATE_STANDOFFS]
    feats += _mount_features((mounts or {}).get('plate', []), plate_uv)
    return bs.SheetPart('power_plate', '5052-0.100', W, H, features=feats, outline=outline,
                        note='flat; the whole P0 power skid on one plate; deburr; PEM nuts per the order sheet')


BUS_L, BUS_W = 110.0, 20.0
BUS_HOLES = [10.0, 32.5, 55.0, 77.5, 100.0]         # along the bar: M6 tapped (the input, then the branches)


def bus_bar_part() -> bs.SheetPart:
    """A bus bar: C110 copper 0.125 in, 110 x 20, five M6 tapped holes (drawn at the M6 tap drill, 5.0 mm). One part
    for + and -; the ring lugs stack on M6 x 12 screws into the taps."""
    feats = [bs.Feature('hole', 'base', (u, BUS_W / 2), 5.0, note='tap M6 x 1.0 through') for u in BUS_HOLES]
    feats += [bs.Feature('hole', 'base', (u, BUS_W / 2), 3.4, note='M3 x 8 down into the insulator\'s inserts') for u in BUS_INS]
    return bs.SheetPart('bus_bar', 'C110-0.125', BUS_L, BUS_W, features=feats, qty=2,
                        note='C110 copper: five holes tapped M6 x 1.0 (the lugs), two clearance holes for M4 into the printed insulator; '
                             'deburr; + and - are the same part')


BUS_INS = (21.25, 88.75)


def bus_insulator():
    """The printed PA6-CF block a bus bar sits on: 110 x 20 x 10, four M3 heat-set inserts (94459A140, Ø4.0 x 6.5:
    two from above for the bar, two from below for the plate's screws, offset so they never meet). The bar's
    potential never reaches the plate: every screw ends in plastic."""
    s = box(0.0, BUS_L, 0.0, BUS_W, 0.0, 10.0).edges('|Z').fillet(2.0)
    for u in BUS_INS:
        s = s.cut(cyl_z(2.0, 10.0 - 6.5, 10.1, u, BUS_W / 2))           # M3 insert from above (the bar)
    for u in (BUS_INS[0] + 22.5, BUS_INS[1] - 22.5):
        s = s.cut(cyl_z(2.0, -0.1, 6.5, u, BUS_W / 2))                  # M3 insert from below (the plate)
    for u in BUS_HOLES:                                                 # clear the M6 screws' tips
        s = s.cut(cyl_z(4.0, 10.0 - 7.0, 10.1, u, BUS_W / 2))
    return s
