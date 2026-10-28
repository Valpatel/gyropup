"""The body's joints and its integrity checks (milestone M5; the user's "building proper models"): every screw as a
modelled joint, checked against the CAD itself, and the body checked for floating parts.

    .venv/bin/python cad/body_joints.py            # -> exports/body/integrity.json (cad/build_body.py runs it too)

A Joint is a group of identical screws: the thread and length, the head's bearing point(s) and the axis into the
work, the parts the screw clamps (head side first) and what takes its thread (a PEM nut pressed in a sheet, a heat-set
insert in a printed part, a nut, a tapped hole or a female standoff). The checks are generic: they read the solids
along each screw's line (OpenCascade line-face intersections, then a point classifier between them), never the
numbers the joint was written from, so a moved part, a missing hole or a wrong length shows up:

  - the head sits on the first part (its bearing face within 0.3 mm of the head point);
  - the parts on the line, just outside the hole (the annulus the head and nut clamp), are the stack the joint says,
    in that order, each touching the next (no gap over 0.3 mm: a gap bends a sheet or leaves a part loose);
  - every clamped part has its clearance hole on the screw's axis (nothing solid on the axis through the stack);
  - the thread engages enough: into a PEM nut, a tapped hole or a standoff at least 0.8 d (a flush nut: all of its
    thread); into a heat-set insert at least 1.2 d and the screw short of the pilot's bottom by 0.5 mm; through a nut its height and a pitch;
  - the screw's tip hits nothing beyond its receiver.

Connectivity is cad-agent's gate (cadagent.gates.connectivity, issue #14): the parts on the robot at each stage (the
frame, the shell, the bought envelopes of the layout, the hip frames) go into an Assembly; the cheeks are grounded;
each joint is declared as fasteners (each clamped part into the receiver) whose reach is this module's own check of
the screw's line through the solids (a joint with a problem holds nothing up); each declared hold (a PEM pressed into
its sheet, a converter on its DIN rail, the turret on the riser's bolts) is a fastener without a solid whose reach is
its parties' measured gap (within HOLD_GAP_MM, or the hold's own reach). The gate adds the geometry's contacts, so a
part resting on another counts as held, and lists every contact nothing declares (a warning: integrity.json and
exports/body/gates/connectivity-<stage>.json). A part whose island reaches no cheek floats.
Interference is cad/build_body.py's (body_internal_clashes at every stage): integrity.json carries its count.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_frame as bf  # noqa: E402
import body_params as bp  # noqa: E402

OUT = R / 'exports' / 'body' / 'integrity.json'
THREAD = {'M3': {'d': 3.0, 'pitch': 0.5, 'clear': 3.4, 'nut_h': 2.4, 'nyloc_h': 4.0, 'head_r': 2.75},
          'M4': {'d': 4.0, 'pitch': 0.7, 'clear': 4.5, 'nut_h': 3.2, 'nyloc_h': 5.0, 'head_r': 3.5},
          'M5': {'d': 5.0, 'pitch': 0.8, 'clear': 5.5, 'nut_h': 4.7, 'nyloc_h': 5.0, 'head_r': 4.75},
          'M6': {'d': 6.0, 'pitch': 1.0, 'clear': 6.6, 'nut_h': 5.2, 'nyloc_h': 6.0, 'head_r': 5.0},
          '1/4-20': {'d': 6.35, 'pitch': 1.27, 'clear': 6.6, 'nut_h': 5.6, 'nyloc_h': 7.1, 'head_r': 5.0}}
SEAT_TOL, GAP_TOL = 0.3, 0.3          # mm: the head on its face; the parts of a stack touching
ENGAGE = {'pem': 0.8, 'tapped': 0.8, 'standoff': 0.8, 'insert': 1.2}     # x d (an insert: its pull-out governs, not the brass)
BOTTOM_CLEAR = 0.5                    # a screw short of a blind pilot's bottom by this much


@dataclass
class Joint:
    name: str
    thread: str
    length: float                     # under the head (a flat head: overall, its top flush with the first face)
    head: str                         # 'button' | 'socket' | 'flat' | 'pan' | 'hex'
    at: list                          # the heads' bearing points (robot frame, mm)
    axis: tuple                       # unit vector from the head into the work
    stack: tuple                      # the clamped parts, head side first (part names)
    receiver: tuple                   # (kind, part): kind pem | insert | nut | nyloc | tapped | standoff; part None for a loose nut
    stage: str = 'P1'
    until: str = None
    washer: float = 0.0               # a washer under the head (mm)
    screw_part: str = None            # the screws' own modelled part, if any (joined to the stack)
    bom: str = None                   # the BOM line the screws come from (catalog/body.json key)
    note: str = ''
    envelope: tuple = ()              # parts drawn as envelopes (bought boxes): no hole or seat checks in them
    pem: str = None                   # the PEM nut's spec when the receiver is a sheet's pressed nut
    nut_parts: tuple = ()             # the nuts' modelled bodies (PEM bodies), joined to the receiver
    nut_at: float = None              # a nut held in a pocket of a clamped part: its near face's distance from the head

    def on(self, stage):
        return bf.on_robot(self, stage)


# ------------------------------------------------------------------------------------------- the joints

def _z(x, y, z):
    return (float(x), float(y), float(z))


def frame_joints():
    """The P0/P1 frame: hip frames, standoffs, tray, belly, posts, deck, riser, turret plate, isolators, the power
    plate, its posts, the bus bars, the DIN rails."""
    zt = bp.z_tray_top()
    tt = bp.STOCK[bp.TRAY]['t']
    tb = bp.STOCK[bp.BELLY]['t']
    zd = bp.TOP
    td = bp.STOCK[bp.DECK]['t']
    J = []
    m = bp.frame_mounts()
    for side, sy in (('left', 1.0), ('right', -1.0)):
        pts = []
        for x, z in m['holes']:
            p = bp.to_robot((x, m['centre_plane_y'], z), side)
            pts.append(_z(p[0], sy * bf.GAP_Y, p[2]))
        J.append(Joint(f'hip_frame_{side}', 'M5', bp.FRAME_SCREW['length'], 'button', pts, (0.0, sy, 0.0), (f'cheek_{side}',),
                       ('insert', f'leg.{side}_hip_frame'), screw_part=f'frame_screws_{side}', bom='screw_m5x12_button',
                       note='the hip frame to its cheek, heads in the gap'))
        J.append(Joint(f'standoff_{side}', 'M4', 10.0, 'flat', [_z(x, sy * bf.FACE_Y, z) for x, z in bf.SPACERS_XZ], (0.0, -sy, 0.0),
                       (f'cheek_{side}',), ('standoff', 'spacers'), screw_part='spacer_screws', bom='screw_m4x10_flat',
                       note='the cheeks on the eight standoffs, flush in the countersinks'))
        fl = bp.FLANGE_SCREW['length']
        J.append(Joint(f'tray_flange_{side}', 'M5', fl, 'button', [_z(x, sy * bf.PEM_Y, zt) for x in bf.FLANGE_NUT_X], (0.0, 0.0, -1.0),
                       ('floor_tray', f'cheek_{side}'), ('pem', f'cheek_{side}'), pem='SS-M5-0', nut_parts=(f'cheek_nuts_{side}',),
                       bom=bp.FLANGE_SCREW['key'], note='the tray on the cheeks\' upper flanges'))
        J.append(Joint(f'belly_flange_{side}', 'M5', fl, 'button', [_z(x, sy * bf.PEM_Y, -bf.ZT - tb) for x in bf.FLANGE_NUT_X],
                       (0.0, 0.0, 1.0), ('belly_plate', f'cheek_{side}'), ('pem', f'cheek_{side}'), pem='SS-M5-0', nut_parts=(f'cheek_nuts_{side}',),
                       bom=bp.FLANGE_SCREW['key'], note='the belly plate under the cheeks\' lower flanges'))
    posts = [f'post_{k + 1}' for k in range(len(bp.POSTS))]
    for k, (x, y) in enumerate(bp.POSTS):
        J.append(Joint(f'post_{k + 1}_foot', 'M5', 12.0, 'button', [_z(x, y, zt - tt)], (0.0, 0.0, 1.0), ('floor_tray',), ('insert', posts[k]),
                       bom='screw_m5x12_button', note='a deck post on the tray, from below'))
        J.append(Joint(f'post_{k + 1}_head', 'M5', 12.0, 'button', [_z(x, y, zd)], (0.0, 0.0, -1.0), ('deck',), ('insert', posts[k]),
                       bom='screw_m5x12_button', note='the deck on a post, from above'))
    t = bp.tm()
    feet = [(t['pan_x'] + a, b) for a, b in bf.RISER_FEET]
    tpt = bp.STOCK[bf.TURRET_PLATE['stock']]['t']
    J.append(Joint('riser_p1', 'M5', 12.0, 'button', [_z(x, y, zd - td) for x, y in feet], (0.0, 0.0, 1.0), ('deck',), ('insert', 'riser'),
                   stage='P1', until='P1', bom='screw_m5x12_button', note='the riser on the deck (P1, no turret plate)'))
    J.append(Joint('riser', 'M5', 16.0, 'button', [_z(x, y, zd - td - tpt) for x, y in feet], (0.0, 0.0, 1.0), ('turret_plate', 'deck'),
                   ('insert', 'riser'), stage='P2', bom='screw_m5x16_button', note='the riser through the turret plate and the deck (D59)'))
    J.append(Joint('turret_plate_ends', 'M5', 10.0, 'button', [_z(x, y, zd) for x, y in bf.turret_plate_end_holes()], (0.0, 0.0, -1.0),
                   ('deck', 'turret_plate'), ('pem', 'turret_plate'), pem='SS-M5-0', nut_parts=('turret_plate_nuts',), stage='P2', bom='screw_m5x10_button',
                   note='the turret plate\'s ends up against the deck'))
    hi = bp.ISOLATOR_H + bp.STOCK[bp.PALLET]['t'] + 0.5 + bf.ISOLATOR_CAP_T
    for k, (x, y) in enumerate(bf.ISOLATORS):
        J.append(Joint(f'isolator_{k + 1}', 'M4', ISOLATOR_SCREW_L, 'socket', [_z(x, y, zt + hi + 0.8)], (0.0, 0.0, -1.0), (f'isolator_{k + 1}', 'floor_tray'),
                       ('pem', 'floor_tray'), pem='S-M4-0', washer=0.8, bom='screw_m4x20',
                       note='a TPU isolator (snug, not tight): an M4 x 20 and a washer through its cap and foot into the tray\'s nut'))
    import body_layout as bl
    pt = bp.STOCK['5052-0.100']['t']
    pz = zt + bl.PLATE_H
    for k, (x, y) in enumerate(bf.PLATE_STANDOFFS):
        J.append(Joint(f'plate_post_{k + 1}_foot', 'M5', 10.0, 'button', [_z(x, y, zt - tt)], (0.0, 0.0, 1.0), ('floor_tray',),
                       ('insert', f'plate_post_{k + 1}'), bom='screw_m5x10_button', note='a power-plate post on the tray'))
        J.append(Joint(f'plate_post_{k + 1}_head', 'M5', 10.0, 'button', [_z(x, y, pz + pt)], (0.0, 0.0, -1.0),
                       ('power_plate',), ('insert', f'plate_post_{k + 1}'), bom='screw_m5x10_button', note='the power plate on a post'))
    # the DIN rails: two M4 x 10 flat heads on the counterbore's floor (1 mm up the base) into the nuts under them
    L_ = bl.layout()['items']
    d = bl.DCDC
    J.append(Joint('power_dcdc', 'M3', 6.0, 'pan', [_z(x, d['y'][0] + DCDC_FLANGE_T, z) for x, z in bf.dcdc_screws()], (0.0, -1.0, 0.0),
                   ('item.power_dcdc', 'dcdc_bracket'), ('insert', 'dcdc_bracket'), envelope=('item.power_dcdc',), bom='screw_m3x6',
                   note='the converter\'s base flange (its slots) on the bracket\'s upright'))
    J.append(Joint('dcdc_bracket', 'M4', 12.0, 'socket', [_z(x, y, pz + pt + bf.DCDC_FOOT_T) for x, y in bf.dcdc_bracket_holes()], (0.0, 0.0, -1.0),
                   ('dcdc_bracket', 'power_plate'), ('pem', 'power_plate'), pem='F-M4-2', bom='screw_m4x12_socket',
                   note='the converter\'s bracket down into the plate\'s flush nuts (the switch hangs 3 mm under the plate)'))
    # the bus bars on their insulators, the insulators on the plate (M3 x 8 into heat-set inserts both ways)
    for k, (bx, by) in enumerate(bl.BUS_XY):
        yc = by + bf.BUS_W / 2
        zi = pz + pt
        J.append(Joint(f'bus_insulator_{k + 1}', 'M3', 8.0, 'socket', [_z(bx + u, yc, pz) for u in (bf.BUS_INS[0] + 22.5, bf.BUS_INS[1] - 22.5)],
                       (0.0, 0.0, 1.0), ('power_plate',), ('insert', f'bus_insulator_{k + 1}'), bom='screw_m3x8_socket',
                       note='a bus bar\'s insulator up from under the plate'))
        J.append(Joint(f'bus_bar_{k + 1}', 'M3', 8.0, 'socket', [_z(bx + u, yc, zi + bf.BUS_INS_H + bp.STOCK['C110-0.125']['t']) for u in bf.BUS_INS],
                       (0.0, 0.0, -1.0), (f'bus_bar_{k + 1}',), ('insert', f'bus_insulator_{k + 1}'), bom='screw_m3x8_socket',
                       note='a bus bar down onto its insulator'))
    return J


def _item_joints(items_by_name):
    """The bought parts screwed to the frame (the layout's envelopes: no hole checks in them)."""
    import body_layout as bl
    zt = bp.z_tray_top()
    pt = bp.STOCK['5052-0.100']['t']
    pz = zt + bl.PLATE_H
    J = []
    for name in ('plate_vesc_r', 'plate_vesc_l'):
        it = items_by_name.get(name)
        if it is None:
            continue
        J.append(Joint(f'{name}_flange', 'M5', VESC_SCREW_L, 'button', [_z(x, y, pz - VESC_FLANGE_T) for x, y in bl.vesc_holes(_It(it))], (0.0, 0.0, 1.0),
                       (f'item.{name}', 'power_plate'), ('pem', 'power_plate'), pem='F-M5-2', bom='screw_m5x10_button',
                       envelope=(f'item.{name}',), note='a VESC hung under the power plate by its flange'))
    return J


VESC_FLANGE_T = 4.0          # the Flipsky 75100's mounting flange (assumed: measure on arrival)
DCDC_FLANGE_T = 2.0          # the TRACO's base flange (assumed)
VESC_SCREW_L = 8.0           # 4 mm of flange and the 2.54 mm plate's flush nut: 1.5 mm stands up through it
ISOLATOR_SCREW_L = 20.0      # with the isolator's cap 1.5 mm thick (3.0 left 2.1 mm of the nut's thread)


class _It:
    def __init__(self, d):
        b = (d['shape'].val() if hasattr(d['shape'], 'val') else d['shape']).BoundingBox()
        self.box = (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)


def bay_joints():
    """The battery bay (cad/body_battery.py, D65)."""
    import body_battery as bb
    g = bb.geometry()
    J = []
    for side, sy in (('l', 1.0), ('r', -1.0)):
        J.append(Joint(f'bay_rail_{side}', 'M4', 20.0, 'socket', [_z(x, sy * yc, g['rail_z'][0]) for x, yc in bb.rail_holes()], (0.0, 0.0, 1.0),
                       (f'bay_rail_{side}', 'belly_plate'), ('pem', 'belly_plate'), pem='S-M4-0', bom='screw_m4x20',
                       note='a bay rail up into the belly\'s nuts, beyond the cheeks\' ends'))
        J.append(Joint(f'bay_side_{side}_low', 'M3', 6.0, 'button', [_z(x, sy * g['side_out'], g['z_floor'] + 12.0) for x in bb.SIDE_SCREWS_X],
                       (0.0, -sy, 0.0), (f'bay_side_{side}', 'bay_floor'), ('pem', 'bay_floor'), pem='S-M3-0', bom='screw_m3x6',
                       note='a side plate into the floor\'s flange nuts'))
        J.append(Joint(f'bay_side_{side}_high', 'M3', 6.0, 'button', [_z(x, sy * g['side_out'], g['z_belly'] - bb.RAIL_H / 2) for x in bb.SIDE_SCREWS_X],
                       (0.0, -sy, 0.0), (f'bay_side_{side}',), ('insert', f'bay_rail_{side}'), bom='screw_m3x6',
                       note='a side plate into its rail\'s inserts'))
    yc = (g['rail_y'][0] + g['rail_y'][1]) / 2
    zc = sum(g['rail_z']) / 2
    for k, sx in (('front', 1.0), ('rear', -1.0)):
        J.append(Joint(f'adapter_plate_{k}', 'M4', 12.0, 'socket', [_z(x, y, g['z_belly'] - bb.PLATE_T + 1.5) for x, y in bb.plate_holes(k)],
                       (0.0, 0.0, 1.0), (f'adapter_plate_{k}', 'belly_plate'), ('pem', 'belly_plate'), pem='S-M4-0', bom='screw_m4x12_socket',
                       note='a pack adapter\'s printed plate up into the belly\'s nuts (heads counterbored 1.5 mm)'))
        for side, sy in (('l', 1.0), ('r', -1.0)):
            J.append(Joint(f'bay_door_{k}_{side}', 'M3', bb.THUMB['length'], 'thumb', [_z(sx * g['x_out'][1], sy * yc, zc)], (-sx, 0.0, 0.0),
                           (f'bay_door_{k}',), ('insert', f'bay_rail_{side}'), bom='thumbscrew_m3x10',
                           note='a door\'s knurled thumbscrew into its rail\'s end (tool-free)'))
    return J


def shell_joints():
    """The P3 shell (cad/body_shell.py): the walls and faces into the posts, the splices, the door, the hatch, the ear
    brackets, the cameras' cradles, the eyes' clip, the fan duct."""
    import body_shell as s3
    W = s3
    post = {(x, y): f'post_{k + 1}' for k, (x, y) in enumerate(bp.POSTS)}
    J = []
    for side, sy in (('l', 1.0), ('r', -1.0)):
        for half, px in (('front', 142.0), ('rear', -142.0)):
            J.append(Joint(f'wall_{side}_{half}', 'M3', 16.0, 'pan', [_z(px, sy * W.YO, z) for z in W.POST_Z_SIDE], (0.0, -sy, 0.0),
                           (f'shell_side_{side}_{half}',), ('insert', post[(px, sy * 109.0)]), stage='P3', bom='screw_m3x16',
                           note='a side wall into its corner post\'s side inserts'))
        J.append(Joint(f'splice_{side}', 'M3', 8.0, 'pan', [_z(W.SPLIT_X + 7.0, sy * W.YO, z) for z in W.SPLICE_SCREWS_Z], (0.0, -sy, 0.0),
                       (f'shell_side_{side}_front', f'shell_side_{side}_rear'), ('nut', f'shell_side_{side}_rear'), nut_at=W.WALL_T + 1.0, stage='P3', bom='screw_m3x8_socket',
                       note='the side wall\'s halves: through the front half into a nut held in the rear half\'s tab'))
        x0, x1 = W.EAR['x']
        J.append(Joint(f'ear_bracket_{side}', 'M5', 14.0, 'button',
                       [_z(x, sy * (W.YO + W.EAR['plate_t']), z) for x in (x0 + 10.0, x1 - 10.0) for z in W.EAR['bolts_z']], (0.0, -sy, 0.0),
                       (f'ear_bracket_{side}', f'shell_side_{side}_front'), ('nyloc', None), stage='P3', bom='screw_m5x14_socket',
                       note='an ear bracket through the wall, nyloc nuts inside'))
    for front, sx in ((True, 1.0), (False, -1.0)):
        face = 'shell_front' if front else 'shell_rear'
        for y in (109.0, -109.0):
            J.append(Joint(f'{face}_post_{"l" if y > 0 else "r"}', 'M3', 16.0, 'pan', [_z(sx * W.XO, y, z) for z in W.POST_Z_FACE], (-sx, 0.0, 0.0),
                           (face,), ('insert', post[(sx * 142.0, y)]), stage='P3', bom='screw_m3x16', note='a face into its post\'s end inserts'))
        cr = f'd435_cradle_{"front" if front else "rear"}'
        J.append(Joint(f'{cr}_feet', 'M3', 8.0, 'pan', [_z(sx * W.XO, y, z) for y, z in W.cradle_screws()], (-sx, 0.0, 0.0), (face,),
                       ('insert', cr), stage='P3', bom='screw_m3x8_socket', note='the camera\'s cradle to the apron, from outside'))
        L_, Wd, H = W.D435['size']
        xb = sx * (W.XO - L_)
        zc = sum(W.D435['z']) / 2
        cam = f'd435_{"front" if front else "rear"}'
        J.append(Joint(f'{cam}_back', 'M3', 8.0, 'socket', [_z(xb - sx * 4.0, y, zc) for y in (-W.D435['back_m3'] / 2, W.D435['back_m3'] / 2)],
                       (sx, 0.0, 0.0), (cr,), ('tapped', cam), envelope=(cam,), stage='P3', bom='screw_m3x8_socket',
                       note='the D435 on its two back M3 threads (4 mm in: check the camera\'s maximum screw depth on arrival)'))
    J.append(Joint('eyes_clip', 'M3', 6.0, 'socket', [_z(W.XI - W.EYES['board'][2] - 2.0, y, z) for y, z in W.eyes_clip_screws()], (1.0, 0.0, 0.0),
                   ('eyes_clip',), ('insert', 'shell_front'), stage='P3', bom='screw_m3x6', note='the eyes\' clip into the face\'s bosses'))
    ds = 1.0 if W.DOOR_SIDE == 'l' else -1.0
    J.append(Joint('shell_door', 'M3', 8.0, 'pan', [_z(x, ds * (W.YO + W.WALL_T), z) for x, z in W.door_screws()],
                   (0.0, -ds, 0.0), ('shell_door', f'shell_side_{W.DOOR_SIDE}_front'), ('nut', f'shell_side_{W.DOOR_SIDE}_front'), nut_at=2 * W.WALL_T + 1.0, stage='P3', bom='screw_m3x8_socket',
                   note='the service door into the nuts held in the wall\'s pads'))
    J.append(Joint('shell_hatch', 'M3', 8.0, 'pan', [_z(x, W.YO + W.WALL_T, z) for x, z in W.hatch_screws()], (0.0, -1.0, 0.0),
                   ('shell_hatch', 'shell_side_l_rear'), ('nut', 'shell_side_l_rear'), nut_at=2 * W.WALL_T + 1.0, stage='P3', bom='screw_m3x8_socket',
                   note='the J501 hatch into the nuts held in the wall\'s rim'))
    zp = bp.TOP - bp.STOCK[bp.DECK]['t'] - bp.STOCK[bf.TURRET_PLATE['stock']]['t']
    J.append(Joint('fan_duct', 'M3', 6.0, 'socket', [_z(x, y, zp - W.DUCT_TAB_T) for x, y in W.duct_tabs()], (0.0, 0.0, 1.0),
                   ('fan_duct', 'turret_plate'), ('tapped', 'turret_plate'), stage='P3', bom='screw_m3x6',
                   note='the fan duct up into the turret plate\'s tapped holes'))
    return J


def joints(items=None):
    items_by_name = {i['name']: i for i in (items or [])}
    import body_shell as bs3
    return frame_joints() + _item_joints(items_by_name) + bay_joints() + shell_joints()


# Holds that are not screws (each a reason): a PEM nut pressed into its sheet, a part captured or clipped, a bought
# part bonded or standing on its own fixing. Connectivity treats them as edges; they are listed in integrity.json.
def holds():
    H = [('cheek_nuts_left', 'cheek_left', 'PEM SS-M5-0 pressed by SendCutSend'),
         ('compute_pallet', 'isolator_1', 'captured between the isolators\' feet and caps (four, each on its M4)'),
         ('item.battery_front', 'item.battery_adapter_front', 'the DeWalt rail and its latch; the door behind it'),
         ('item.battery_rear', 'item.battery_adapter_rear', 'the DeWalt rail and its latch; the door behind it'),
         ('item.battery_adapter_front', 'adapter_plate_front', 'the adapter\'s own screws into inserts set from its holes on arrival'),
         ('item.battery_adapter_rear', 'adapter_plate_rear', 'the adapter\'s own screws into inserts set from its holes on arrival'),
         ('ear_pod_l', 'ear_bracket_l', 'the SSC1\'s 5/16-18 foot bolt into the nut held in the bracket\'s shelf'),
         ('ear_pod_r', 'ear_bracket_r', 'the SSC1\'s 5/16-18 foot bolt into the nut held in the bracket\'s shelf'),
         ('eyes_board', 'eyes_clip', 'clamped between the clip and the face round its window'),
         ('bay_skid_1', 'bay_floor', '3M VHB tape'), ('bay_skid_2', 'bay_floor', '3M VHB tape'),
         ('bay_skid_3', 'bay_floor', '3M VHB tape'), ('bay_skid_4', 'bay_floor', '3M VHB tape'),
         ('cheek_nuts_right', 'cheek_right', 'PEM SS-M5-0 pressed by SendCutSend'),
         ('turret_plate_nuts', 'turret_plate', 'PEM SS-M5-0 pressed by SendCutSend'),
         ]
    return H


# ------------------------------------------------------------------------------------------- the line through the solids

def _intervals(shape, bb, p, u, t0, t1):
    """The parameter intervals [a, b] along p + t u (t0..t1) inside a solid."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.TopAbs import TopAbs_IN
    # a quick reject on the box
    q0 = [p[i] + u[i] * t0 for i in range(3)]
    q1 = [p[i] + u[i] * t1 for i in range(3)]
    lo = [min(a, b) for a, b in zip(q0, q1)]
    hi = [max(a, b) for a, b in zip(q0, q1)]
    if hi[0] < bb.xmin - 0.1 or lo[0] > bb.xmax + 0.1 or hi[1] < bb.ymin - 0.1 or lo[1] > bb.ymax + 0.1 or hi[2] < bb.zmin - 0.1 or lo[2] > bb.zmax + 0.1:
        return []
    isect = IntCurvesFace_ShapeIntersector()
    isect.Load(shape.wrapped, 1e-5)
    isect.Perform(gp_Lin(gp_Pnt(*p), gp_Dir(*u)), t0, t1)
    ts = sorted({round(isect.WParameter(i), 5) for i in range(1, isect.NbPnt() + 1)})
    ts = [t0] + [v for v in ts if t0 < v < t1] + [t1]
    cls = BRepClass3d_SolidClassifier(shape.wrapped)
    out = []
    for a, b in zip(ts, ts[1:]):
        if b - a < 1e-4:
            continue
        mid = (a + b) / 2
        cls.Perform(gp_Pnt(p[0] + u[0] * mid, p[1] + u[1] * mid, p[2] + u[2] * mid), 1e-6)
        if cls.State() == TopAbs_IN:
            if out and abs(out[-1][1] - a) < 1e-4:
                out[-1][1] = b
            else:
                out.append([a, b])
    return out


def _perp(u):
    a = (1.0, 0.0, 0.0) if abs(u[0]) < 0.9 else (0.0, 1.0, 0.0)
    v = (u[1] * a[2] - u[2] * a[1], u[2] * a[0] - u[0] * a[2], u[0] * a[1] - u[1] * a[0])
    n = math.sqrt(sum(c * c for c in v))
    v = tuple(c / n for c in v)
    w = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return v, w


class Solids:
    """The shapes the checks read: {name: (shape, bbox)}."""

    def __init__(self, shapes: dict):
        self.s = {}
        for n, sh in shapes.items():
            v = sh.val() if hasattr(sh, 'val') else sh
            self.s[n] = (v, v.BoundingBox())

    def along(self, p, u, t0, t1, names=None):
        out = {}
        for n, (sh, bb) in self.s.items():
            if names is not None and n not in names:
                continue
            iv = _intervals(sh, bb, p, u, t0, t1)
            if iv:
                out[n] = iv
        return out


PEM_SHANK = 0.76                      # the S/SS nuts' shank in the sheet (code -0: PennEngineering's 0.030 in)


def pem_thread(spec, sheet_t):
    """(where the thread starts, measured back from the sheet's far face; its length) for a PEM nut."""
    P = bp.PEM[spec]
    if spec.startswith('F'):                       # flush: the thread fills the sheet
        return sheet_t, sheet_t
    return PEM_SHANK, PEM_SHANK + P['body_h']


def check_joint(j: Joint, S: Solids, stage):
    """Every screw of a joint against the solids on the robot at a stage: [{at, problems, grip, engagement}]."""
    th = THREAD[j.thread]
    d, L = th['d'], j.length
    u = tuple(float(c) for c in j.axis)
    v, w = _perp(u)
    r_ann = th['clear'] / 2 + 0.8
    if j.pem:
        r_ann = max(r_ann, bp.PEM[j.pem]['H'] / 2 + 0.4)      # outside the nut's mounting hole (the nut is not drawn)
    t0, t1 = -1.0, L + 25.0
    kind, rpart = j.receiver
    skip = {j.screw_part, *j.nut_parts, *j.envelope}
    rows = []
    for p in j.at:
        probs = []
        # the annulus: four lines just outside the clearance hole, where the head and the nut clamp
        found = defaultdict(list)
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            q = tuple(p[i] + r_ann * (math.cos(a) * v[i] + math.sin(a) * w[i]) for i in range(3))
            for n, iv in S.along(q, u, t0, t1).items():
                found[n].extend(x for x in iv if x[1] > 0.05)          # what lies behind the head is not the stack
        found = {n: sorted(iv) for n, iv in found.items() if iv}
        first = {n: iv[0][0] for n, iv in found.items()}
        on_axis = S.along(p, u, t0, t1)
        want = list(j.stack)
        # the head's seat
        s0 = want[0]
        if s0 not in j.envelope:
            if s0 not in found:
                probs.append(f'{s0} is not under the head')
            elif abs(max(first[s0], 0.0) - j.washer) > SEAT_TOL and j.head != 'flat':
                probs.append(f'the head is {first[s0] - j.washer:+.2f} mm off {s0}\'s face')
        # where the thread starts and how long it is
        t_start, t_len = None, None
        if kind == 'pem':
            if rpart in found:
                exit_ = max(b for a_, b in found[rpart] if a_ < L + 1)
                back, t_len = pem_thread(j.pem, exit_ - first[rpart])
                t_start = exit_ - back
        elif kind in ('insert', 'tapped', 'standoff'):
            if rpart in found:
                t_start = first[rpart]
        # the stack: the parts on the annulus before the thread (or to the screw's end for a nut), in order, touching
        lim = t_start if t_start is not None else L
        got = [n for n in sorted(first, key=first.get) if first[n] < lim - 0.05 and n not in skip and not n.startswith('item.')
               and not (n == rpart and kind in ('insert', 'tapped', 'standoff'))]
        if [n for n in got if n in want] != [n for n in want if n in got]:
            probs.append(f'the stack is {got}, not {want}')
        for n in want:
            if n not in found:
                probs.append(f'{n} is not in the stack')
        extra = [n for n in got if n not in want]
        if extra:
            probs.append(f'the stack also clamps {extra}')
        seq = [n for n in want if n in found]
        grip = 0.0
        for i, n in enumerate(seq):
            nxt = first[seq[i + 1]] if i + 1 < len(seq) else (t_start if t_start is not None and n != rpart else L)
            end = max([b for a_, b in found[n] if a_ < nxt - 0.05] or [first[n]])
            grip = max(grip, end)
            if i + 1 < len(seq) and seq[i + 1] not in j.envelope and n not in j.envelope and first[seq[i + 1]] - end > GAP_TOL:
                probs.append(f'a {first[seq[i + 1]] - end:.2f} mm gap between {n} and {seq[i + 1]}')
        if seq and seq[0] not in j.envelope and j.head != 'flat' and first[seq[0]] - j.washer > GAP_TOL:
            pass                                        # (the seat check reports it)
        # the holes: nothing solid on the axis through the clamped parts
        for n in want:
            if n in on_axis and n not in j.envelope:
                hit = [x for x in on_axis[n] if x[0] < grip - 0.05 and x[1] > 0.05]
                if hit:
                    probs.append(f'no hole in {n} (solid on the axis at {hit[0][0]:.1f}..{hit[0][1]:.1f})')
        # the thread
        engage, tip_from = None, grip
        if kind in ('pem', 'tapped', 'standoff', 'insert'):
            if t_start is None:
                probs.append(f'the screw does not reach {rpart}')
            else:
                engage = L - t_start
                if kind == 'pem':
                    need = min(ENGAGE['pem'] * d, t_len)
                    engage = min(engage, t_len)
                    tip_from = t_start + t_len
                else:
                    need = ENGAGE[kind] * d
                    tip_from = t_start
                if engage < need - 0.05:
                    probs.append(f'{engage:.1f} mm of thread in {rpart} ({kind}{" " + j.pem if j.pem else ""}), under {need:.1f}')
                if kind == 'insert':                       # the pilot's bottom on the axis
                    solid = [x for x in on_axis.get(rpart, []) if x[1] > t_start + 0.05]
                    if solid and solid[0][0] < L + BOTTOM_CLEAR:
                        probs.append(f'the screw bottoms in {rpart}\'s pilot ({solid[0][0] - t_start:.1f} deep, the screw {L - t_start:.1f} in)')
        elif kind in ('nut', 'nyloc'):
            h = th['nyloc_h' if kind == 'nyloc' else 'nut_h']
            if j.nut_at is not None:                     # captive in a pocket: the clamp ends at the nut
                grip = j.nut_at
            engage = L - grip
            need = h + th['pitch']
            if engage < need - 0.05:
                probs.append(f'{engage:.1f} mm past the stack for a {kind} {h} mm tall and a pitch ({need:.1f})')
            tip_from = grip + h
        # the tip: nothing else on the axis from the thread's end to the screw's end
        for n, iv in on_axis.items():
            if n in want or n == rpart or n in skip:
                continue
            hit = [x for x in iv if x[0] < L - 0.05 and x[1] > tip_from + 0.05 and x[1] > 0.05]
            if hit:
                probs.append(f'the tip hits {n} at {max(hit[0][0], 0):.1f} mm')
        rows.append({'at': [round(c, 2) for c in p], 'grip_mm': round(grip, 2), 'engagement_mm': round(engage, 2) if engage is not None else None,
                     'problems': probs})
    return rows


# ------------------------------------------------------------------------------------------- connectivity

GROUND = ('cheek_left', 'cheek_right')
HOLD_GAP_MM = 1.0                     # a declared hold's parties within this of each other (unless the hold gives its reach)
GATES_DIR = OUT.parent / 'gates'


def connectivity(shapes, J, H, stage, S=None, rows_by_joint=None, cache=None, out=None):
    """cad-agent's connectivity gate on the parts on the robot at a stage. ``shapes`` {name: shape}; ``J`` the joints,
    ``H`` the holds [(a, b, why[, reach_mm])]; ``rows_by_joint`` this module's checks of each joint at the stage (a joint
    with a problem holds nothing up). Returns the gate's verdict (written to ``out`` with its .dot when given)."""
    from cadagent.gates.connectivity import ASSUMPTIONS, GATE, Declarations, Node, analyse, owner, verdict, write_dot, write_verdict
    from cadagent.gates.relations import Assembly, Tolerances, relate_pair, relation_table
    asm = Assembly()
    for n, sh in shapes.items():
        asm.add(n, sh.val() if hasattr(sh, 'val') else sh)
    names = set(asm)
    tol = Tolerances(touch_mm=0.05)
    table = relation_table(asm, tol, cache=cache)
    fasteners, reach = {}, {}
    for j in J:
        if not j.on(stage):
            continue
        rows = (rows_by_joint or {}).get(j.name)
        if rows is None and S is not None:
            rows = check_joint(j, S, stage)
        bad = [r for r in rows or [] if r['problems']]
        stack = [n for n in j.stack if n in names]
        into = j.receiver[1] if j.receiver[1] in names else (stack[-1] if stack else None)
        for n in [*stack, *[q for q in (j.screw_part, *j.nut_parts) if q and q in names]]:
            if n == into or into is None:
                continue
            key = f'{j.name}:{n}'
            fasteners[key] = {'clamps': n, 'into': into}
            reach[key] = {'ok': rows is not None and not bad, 'axes': [],
                          'reason': '' if rows is not None and not bad else
                          ('not checked' if rows is None else f"cad/body_joints.py: {bad[0]['problems'][0]} (x{len(bad)})")}
    for h in H:
        a, b, why = h[:3]
        limit = h[3] if len(h) > 3 else HOLD_GAP_MM
        if a not in names or b not in names:
            continue
        r = relate_pair(asm, a, b, tol, cache=cache)
        gap = 0.0 if r.in_contact else r.gap_mm
        key = f'hold:{a}|{b}'
        fasteners[key] = {'clamps': a, 'into': b, 'why': why}
        ok = gap is not None and gap <= limit
        reach[key] = {'ok': ok, 'axes': [], 'gap_mm': None if gap is None else round(gap, 3),
                      'reason': '' if ok else f'{why}: the parties are {gap} mm apart (allowed {limit} mm)'}
    decl = Declarations(grounded=[g for g in GROUND if g in names], fasteners=fasteners, joints={})
    nodes = {k: Node(k, owner(k), asm[k].kind, asm[k].body, asm[k].group) for k in asm}

    def measure(a, b):
        return table.relations.get((a, b)) or table.relations.get((b, a)) or relate_pair(asm, a, b, tol, cache=cache)
    an = analyse(nodes, list(table), decl, measure=measure, lower_bounds=table.lower_bounds, fastener_reach=reach)
    an.extra['relation_stats'] = {k: table.stats[k] for k in ('parts', 'pairs', 'candidates') if k in table.stats}
    v = verdict(GATE, an.checks, assumptions=list(ASSUMPTIONS) + [
        'cad/body_joints.py: each joint\'s fasteners hold only when its own line-through-the-solids check passes; each '
        f'declared hold when its parties are within {HOLD_GAP_MM} mm (or its own reach)'],
        exclusions=an.exclusions, extra=an.extra,
        limits={'touch_mm': tol.touch_mm, 'near_mm': tol.near_mm, 'hold_gap_mm': HOLD_GAP_MM})
    if out is not None:
        write_verdict(out, v)
        write_dot(v, Path(out).with_suffix('.dot'))
    return v


def floating(v) -> list:
    """The parts of a connectivity verdict's islands that reach no grounded part."""
    return sorted(p for isl in (v.get('floating') or []) for p in isl['parts'])


# ------------------------------------------------------------------------------------------- the run

def leg_frames():
    """The hip frames (the legs' parts bolted to the cheeks), robot frame: the receivers of the hip-frame screws."""
    legs = bf.legs(300.0, 0.0, with_bought=False)
    out = {}
    for n, s in legs.items():
        side, part = n.split('.', 1)
        if 'hip_frame' in part or part.startswith('frame'):
            out[f'leg.{"left" if side == "L" else "right"}_hip_frame'] = s
    return out


def run(parts, items=None, stages=('P1', 'P2', 'P3'), clashes=None):
    """The integrity report: every joint's screws at every stage they are on, the floating parts per stage."""
    J = joints(items)
    H = holds()
    for it in (items or []):
        H.extend(item_holds(it))
    legs = leg_frames()
    report = {'joints': [], 'floating': {}, 'connectivity': {}, 'holds': [list(h) for h in H], 'stages': list(stages)}
    from cadagent.gates.cache import PairCache
    cache = PairCache(R / 'build' / 'gates-cache')            # unchanged pairs are free on the next build
    for st in stages:
        shapes = {n: p.shape for n, p in parts.items() if p.shape is not None and bf.on_robot(p, st)}
        shapes.update(legs)
        for it in (items or []):
            if bf.STAGES.index(it.get('stage') or 'P0') <= bf.STAGES.index(st):
                shapes[f'item.{it["name"]}'] = it['shape']
        S = Solids(shapes)
        rows_by = {j.name: check_joint(j, S, st) for j in J if j.on(st)}    # every joint on: the gate's fasteners hold by these
        for j in J:
            if not j.on(st) or (st != stages[-1] and j.on(stages[-1]) and j.until is None and st != j.stage):
                continue                                       # each joint reported at the first stage it is on (and its last)
            rows = rows_by[j.name]
            bad = [r for r in rows if r['problems']]
            report['joints'].append({'joint': j.name, 'stage': st, 'screw': f'{j.thread} x {j.length:g} {j.head}', 'count': len(j.at),
                                     'stack': list(j.stack), 'receiver': list(j.receiver), 'bom': j.bom, 'note': j.note, 'screw_part': j.screw_part,
                                     'grip_mm': sorted({r['grip_mm'] for r in rows}), 'engagement_mm': sorted({r['engagement_mm'] for r in rows if r['engagement_mm'] is not None}),
                                     'problems': [{'at': r['at'], 'problems': r['problems']} for r in bad]})
        gdir = GATES_DIR if st == stages[-1] else R / 'build' / 'gates'      # the last stage's verdict is kept in git
        gdir.mkdir(parents=True, exist_ok=True)
        v = connectivity(shapes, J, H, st, rows_by_joint=rows_by, cache=cache, out=gdir / f'connectivity-{st}.json')
        report['floating'][st] = [p for p in floating(v) if not p.startswith('leg.')]
        report['connectivity'][st] = {'status': v.get('status'), 'pass': v.get('pass'),
                                      'fails': [c['id'] for c in v['checks'] if c['status'] == 'fail'],
                                      'undeclared_contacts': [c['id'].split(':', 1)[1] for c in v['checks']
                                                              if c['status'] == 'warn' and c['id'].startswith('contact:')],
                                      'verdict': str((gdir / f'connectivity-{st}.json').relative_to(R))}
    report['screw_count'] = screw_counts(J)
    report['summary'] = {'joints': len({r['joint'] for r in report['joints']}), 'screws': sum(j.__dict__['at'].__len__() for j in J),
                         'joints_with_problems': sorted({r['joint'] for r in report['joints'] if r['problems']}),
                         'floating': {st: v for st, v in report['floating'].items() if v},
                         'connectivity_pass': {st: c['pass'] for st, c in report['connectivity'].items()},
                         'clashes': clashes}
    return report


def item_holds(it):
    """The layout's bought parts that are held without a modelled screw: on DIN rails, on the carrier's standoffs,
    the turret on the riser, the lidar on the deck."""
    n = it['name']
    rule = ITEM_HOLDS.get(n) or next((v for k, v in ITEM_HOLDS.items() if k.endswith('*') and n.startswith(k[:-1])), None)
    if rule is None:
        return []
    return [(f'item.{n}', *rule)]


ITEM_HOLDS = {
    'j501_carrier': ('item.j501_standoff_15_16.5', 'four M3 x 6 into the hex standoffs (the J501\'s own holes)'),
    'j501_standoff_*': ('compute_pallet', 'M3 x 6 flat heads up through the pallet (body_frame.pallet_part)'),
    'agx_module': ('item.j501_carrier', 'the module\'s connector and its two M3 screws'),
    'agx_spreader': ('item.agx_module', 'clamped under the cooler'),
    'agx_cooler': ('item.j501_carrier', 'the cooler\'s four spring screws through the carrier (j501-agx)', 40.0),
    'plate_main_switch': ('power_plate', 'in its printed cradle (3 mm under the plate), two M4 into the plate\'s F-M4-2', 3.0),
    'plate_shunt': ('power_plate', 'on 3 mm printed spacers, two M5 into the plate\'s F-M5-2', 3.0),
    'plate_mrbf_block': ('power_plate', 'on 3 mm printed spacers, its M8 post through a printed bushing in the plate', 3.0),
    'plate_fuses': ('power_plate', 'cable-tied through the plate\'s slots'),
    'plate_mcu_board': ('power_plate', 'its printed carrier on two M4 into the plate\'s F-M4-2'),
    'plate_buck_5v': ('power_plate', 'an M3 standoff in the plate'),
    'vn100': ('floor_tray', 'two M3 into tapped holes in the tray'),
    'lidar_box': ('deck', 'its printed bracket on two M4 from above'),
    'lidar_coil': ('deck', 'two printed clips on M4 from above'),
    'vlp16': ('deck', 'its 1/4-20 from below and two locating pins'),
    'turret': ('riser', 'four M5 into the riser\'s top inserts and two dowels (the TM pattern)'),
}


def screw_counts(J):
    c = defaultdict(int)
    for j in J:
        c[f'{j.thread} x {j.length:g} {j.head} ({j.stage}{"-" + j.until if j.until else "+"})'] += len(j.at)
    return dict(sorted(c.items()))


def main():
    import build_body as bb
    L = bb._layout()
    parts = bf.all_parts(L['mounts'])
    r = run(parts, L['items'])
    OUT.write_text(json.dumps(r, indent=1) + '\n')
    s = r['summary']
    print(f"{s['joints']} joints, {s['screws']} screws; with problems: {s['joints_with_problems']}; floating: {s['floating']}")
    for row in r['joints']:
        if row['problems']:
            print(f"  {row['joint']} ({row['stage']}, {row['screw']}): {row['problems'][0]['problems']} (x{len(row['problems'])})")


if __name__ == '__main__':
    main()
