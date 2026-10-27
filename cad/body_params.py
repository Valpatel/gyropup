"""Gyropup's body (milestone M5): every number the body's CAD, layout, mass budget and checks use, in one place.

Robot frame (mm): x forward, y left, z up, origin on the hip axis between the two legs (as sim/robot_v2.py).

Nothing that another part of the project owns is retyped here. It is read from its source:
  - the hip frames' body interface (six M5 inserts per frame on the centre-plane face) is MEASURED from
    cad/fivebar.py hip_frame()'s solid: the round holes of the M5 insert pilot's size on the plane y = Y['centre_plane'],
    and the extent of the flat face they sit in (frame_mounts(); cached in build/body/, keyed by the sources' hashes);
  - the turret's TM pattern from cad/turret.py (TM_BOLTS, TM_DOWELS, TM_HOLE) and its foot and bumper from turret.Geo;
  - the J501 carrier, module and cooler from ~/Code/j501-agx/cad/parameters.json (J501_DIR, as cad/turret_box.py);
  - the VLP-16's mounting from catalog/sensors_compute.json.

What the body itself decides (docs/body-plan.md, changed where the build showed it had to; docs/body-frame.md):
  - The spine is TWO identical bent C-channels ("cheeks", 5052-H32 0.125 in) held 35 mm apart by M5 hex standoffs,
    each hip frame bolted to its own cheek's outer face with its six M5 inserts. The plan's one-piece 36 mm wide U,
    150 mm deep, cannot be bent: SendCutSend's bending guide asks for a U-channel's base to be at least twice its
    flanges (sendcutsend.com/guidelines/bending, read 2026-10-27), and the second flange would hit the press brake.
    A C-channel 162 tall with 22 mm flanges is well inside that rule, and one part number serves both sides (the
    right cheek is the left one turned 180 deg about z, as the right leg is the left one turned about z).
  - The cheeks' flanges turn OUT, under the floor tray and over the belly plate. Their outer faces sit at z = +-81,
    not +-76: the frame's M5 holes at z = +-67 must stay half a die width (8 mm, flat) from the bend's centreline, and
    the frame's insert bosses reach z = +-74.
  - The track and Y_OFF follow from the stock: SPINE_W = 35 + 2 x 3.175 = 41.35 mm between the frames' faces.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import os
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CACHE = R / 'build' / 'body'
J501_DIR = Path(os.environ.get('J501_DIR', Path.home() / 'Code' / 'j501-agx'))
IN = 25.4

# ------------------------------------------------------------------------------------------- SendCutSend (2026-10-27)
# sendcutsend.com/bending-calculator ("Bending specifications per material", 5052 aluminium, at 90 deg),
# sendcutsend.com/materials/5052-aluminum and /6061-aluminum (thicknesses; hardware, tapping, countersinking by
# thickness), sendcutsend.com/guidelines/bending (rules) and /guidelines/hardware/catalog (PEM dimensions).
SCS_READ = '2026-10-27'
STOCK = {
    # key: material, thickness (in), bendable, inside radius (in), K, bend deduction (in), min formed flange (in), die (in)
    '5052-0.125': {'material': '5052-H32 aluminium', 't_in': 0.125, 'bend': True, 'r_in': 0.125, 'k': 0.44, 'bd_in': 0.216,
                   'min_flange_in': 0.476, 'die_in': 0.630, 'countersink': True, 'hardware': True, 'density': 2.68,
                   'yield_mpa': 193.0, 'E_mpa': 70300.0},
    '5052-0.187': {'material': '5052-H32 aluminium', 't_in': 0.187, 'bend': True, 'r_in': 0.250, 'k': 0.43, 'bd_in': 0.356,
                   'min_flange_in': 0.798, 'die_in': 0.984, 'countersink': True, 'hardware': True, 'density': 2.68,
                   'yield_mpa': 193.0, 'E_mpa': 70300.0},
    '5052-0.100': {'material': '5052-H32 aluminium', 't_in': 0.100, 'bend': True, 'r_in': 0.125, 'k': 0.40, 'bd_in': 0.191,
                   'min_flange_in': 0.463, 'die_in': 0.630, 'countersink': False, 'hardware': True, 'density': 2.68,
                   'yield_mpa': 193.0, 'E_mpa': 70300.0},
    '6061-0.100': {'material': '6061-T6 aluminium', 't_in': 0.100, 'bend': False, 'countersink': False, 'hardware': True,
                   'density': 2.70, 'yield_mpa': 276.0, 'E_mpa': 68900.0},
    '6061-0.125': {'material': '6061-T6 aluminium', 't_in': 0.125, 'bend': False, 'countersink': True, 'hardware': True,
                   'density': 2.70, 'yield_mpa': 276.0, 'E_mpa': 68900.0},
    # sendcutsend.com/materials/copper: C110 half-hard, 99.9 %, ~100 % IACS; tapping from 0.063 in; no hardware insertion
    'C110-0.125': {'material': 'C110 copper', 't_in': 0.125, 'bend': False, 'countersink': False, 'hardware': False, 'tapping': True,
                   'density': 8.94, 'yield_mpa': 250.0, 'E_mpa': 117000.0},
}
for _s in STOCK.values():
    _s['t'] = _s['t_in'] * IN
    if _s['bend']:
        _s['r'] = _s['r_in'] * IN
        _s['ossb'] = _s['r'] + _s['t']                                   # outside setback at 90 deg
        _s['ba'] = math.pi / 2 * (_s['r'] + _s['k'] * _s['t'])           # bend allowance at 90 deg
        _s['bd'] = 2 * _s['ossb'] - _s['ba']                             # = SendCutSend's bend deduction (checked in tests)
        _s['min_flange'] = _s['min_flange_in'] * IN
        _s['half_die'] = _s['die_in'] * IN / 2                           # cut features at least this far from a bend centreline
SCS_RULES = {
    'max_flat_in': (30.0, 44.0),             # instant pricing
    'min_flat_in': (0.25, 0.375),
    'min_hole_frac_t': 0.5,                  # holes and cutouts at least 50 % of the thickness (pre-flight checklist)
    'channel_base_to_flange': 2.0,           # "U/C-channel base must be at least 2x flange length for sheet metal"
    'max_bend_deg': 130.0,
    'box_flange_max_in_with_hardware': 3.0,
}
# PEM self-clinching nuts SendCutSend presses (catalogue: H hole to draw, K centre to cut edge, N centre to the edge
# of the bend allowance, M centre to centre for the same part; min sheet), inches
PEM = {
    'SS-M5-0': {'thread': 'M5', 'H_in': 0.251, 'K_in': 0.280, 'N_in': 0.280, 'M_in': 0.407, 'min_sheet_in': 0.031,
                'body_d': 9.0, 'body_h': 4.6, 'note': 'stainless M5 nut; body Ø and height are envelopes (est) for clash checks'},
    'S-M4-0': {'thread': 'M4', 'H_in': 0.212, 'K_in': 0.272, 'N_in': 0.272, 'M_in': 0.379, 'min_sheet_in': 0.031,
               'body_d': 7.9, 'body_h': 4.0, 'note': 'M4 nut; envelope est'},
    'S-M3-0': {'thread': 'M3', 'H_in': 0.168, 'K_in': 0.250, 'N_in': 0.250, 'M_in': 0.336, 'min_sheet_in': 0.031,
               'body_d': 6.4, 'body_h': 3.2, 'note': 'M3 nut; envelope est'},
    # flush nuts: nothing stands proud of either face (sheet >= 0.090 in): for plates used on both faces
    'F-M4-2': {'thread': 'M4', 'H_in': 0.290, 'K_in': 0.283, 'N_in': 0.283, 'M_in': 0.428, 'min_sheet_in': 0.090,
               'body_d': 0.0, 'body_h': 0.0, 'note': 'flush M4 nut'},
    'F-M5-2': {'thread': 'M5', 'H_in': 0.312, 'K_in': 0.315, 'N_in': 0.315, 'M_in': 0.471, 'min_sheet_in': 0.090,
               'body_d': 0.0, 'body_h': 0.0, 'note': 'flush M5 nut'},
}
for _p in PEM.values():
    for _k in ('H', 'K', 'N', 'M'):
        _p[_k] = _p[f'{_k}_in'] * IN

# ------------------------------------------------------------------------------------------- sources' hashes


def _hash(*paths) -> str:
    h = hashlib.sha1()
    for p in paths:
        h.update(Path(p).read_bytes())
    for k in sorted(os.environ):
        if k.startswith('GYROPUP_'):                       # parameter overrides change the leg
            h.update(f'{k}={os.environ[k]}'.encode())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------------------------------- the leg's interface


def _fivebar():
    import sys
    sys.path.insert(0, str(R / 'cad'))
    import fivebar
    return fivebar


@functools.lru_cache(maxsize=1)
def frame_mounts() -> dict:
    """The hip frame's body interface (module frame of the LEFT leg: x forward, y outwards, z up; the face is the
    plane y = Y['centre_plane']):
      holes   [(x, z)] of the M5 inserts on that plane
      pilot_d the pilots' diameter (gmi M5 insert_pilot), depth the hole depth into the frame
      face    [(x0, x1, z0, z1, area)] the flat bearing faces on that plane (flange ends and boss faces)
      source  'fivebar.frame_mounts' when cad/fivebar.py publishes the pattern (the leg workstream's function, F3 of
              docs/leg-prototype-plan.md), else 'measured'; the faces are always measured from hip_frame()'s solid,
              and measured_holes is kept so a test can see the two agree.
    A change to the frame in cad/fivebar.py flows through here; nothing is copied."""
    fb = _fivebar()
    src = (R / 'cad/fivebar.py', R / 'cad/gmi.py', R / 'cad/interfaces.json', R / 'catalog/interfaces.json')
    key = _hash(*src)
    f = CACHE / 'frame_mounts.json'
    if f.exists():
        d = json.loads(f.read_text())
        if d.get('key') == key:
            return d
    d = _measure_frame(fb, key)
    if hasattr(fb, 'frame_mounts'):                                      # the leg's own statement of the interface
        pub = fb.frame_mounts()
        import gmi
        d.update({'holes': sorted((round(x, 3), round(z, 3)) for x, z in pub['inserts_xz']), 'depth': pub['pilot_depth'],
                  'pilot_d': gmi.FAST[pub['thread']]['insert_pilot'], 'centre_plane_y': pub['plane_y'],
                  'source': 'fivebar.frame_mounts'})
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1) + '\n')
    return d


def _measure_frame(fb, key) -> dict:
    """The interface measured from hip_frame()'s solid: M5 pilot circles and flat faces on the centre plane."""
    import gmi
    yc = fb.Y['centre_plane']
    pilot = gmi.FAST['M5']['insert_pilot']
    solid = fb.hip_frame().val()
    holes = set()
    for e in solid.Edges():
        if e.geomType() == 'CIRCLE' and abs(e.Center().y - yc) < 1e-3 and abs(2 * e.radius() - pilot) < 0.05:
            holes.add((round(e.Center().x, 3), round(e.Center().z, 3)))
    faces = []
    for fc in solid.Faces():
        if fc.geomType() == 'PLANE' and abs(fc.Center().y - yc) < 1e-3:
            b = fc.BoundingBox()
            faces.append((round(b.xmin, 2), round(b.xmax, 2), round(b.zmin, 2), round(b.zmax, 2), round(fc.Area(), 1)))
    # the pilot's depth: probe along y from the face until the hole's wall ends (the deepest circular edge of that size)
    depth = 0.0
    for e in solid.Edges():
        if e.geomType() == 'CIRCLE' and abs(2 * e.radius() - pilot) < 0.05:
            c = e.Center()
            if any(abs(c.x - x) < 1e-3 and abs(c.z - z) < 1e-3 for x, z in holes):
                depth = max(depth, c.y - yc)
    bb = solid.BoundingBox()
    return {'key': key, 'centre_plane_y': yc, 'holes': sorted(holes), 'measured_holes': sorted(holes), 'pilot_d': pilot,
            'depth': round(depth, 2), 'face': sorted(faces),
            'frame_bbox': [round(v, 2) for v in (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)], 'source': 'measured',
            'basis': 'faces measured from cad/fivebar.py hip_frame() (planar faces and M5 pilot circles on the centre plane)'}


# ------------------------------------------------------------------------------------------- the spine

CHEEK = os.environ.get('GYROPUP_BODY_CHEEK', '5052-0.187')       # 3/16 in: 1/8 in fails the landing (cad/body_studies.py S1)
SPACER_L = float(os.environ.get('GYROPUP_BODY_SPACER_L', 31.0))     # hex standoffs between the cheeks' inner faces: McMaster's
                                    # 6 mm hex M4 F-F series has 30, 31 and 37 (no 35); 31 keeps the track at ~414 (the plan's 415.8)
SPINE_W = SPACER_L + 2 * STOCK[CHEEK]['t']          # between the two hip frames' centre-plane faces (40.5)
SPINE_X = (-92.0, 92.0)             # the cheeks' length: just inside the hip frames' flange ends (x +-95), so each front
                                    # RS-04's harness (it leaves its rear cover downwards at x ~ 95) drops past the cheek's
                                    # end into the belly, and the spine weighs 0.57 kg, not 0.93
CHEEK_FLANGE = float(os.environ.get('GYROPUP_BODY_CHEEK_FLANGE', 30.0))   # outward flanges (OML): an SS-M5-0 nut needs 7.6 mm (half die) from the bend and
                                    # 7.1 mm (K) to the edge, beyond the 6.35 mm setback
FRAME_SCREW = {'size': 'M5', 'length': 12.0, 'head': 'ISO 7380 button head, 3 mm hex', 'torque_nm': 3.0,
               'why': f'through the {STOCK[CHEEK]["t"]:.2f} mm cheek it engages {12.0 - STOCK[CHEEK]["t"]:.1f} mm of the 7.9 mm insert and stays '
                      f'{11.0 - (12.0 - STOCK[CHEEK]["t"]):.1f} mm short of the pilot\'s 11 mm bottom; M5 x 16 would bottom out'}


def y_off() -> float:
    """Where the left module's y = 0 (its AO face) sits in the robot frame: its centre-plane face on the cheek."""
    return SPINE_W / 2 - _fivebar().Y['centre_plane']


def track() -> float:
    """Wheel centre to wheel centre (mm)."""
    return 2 * (y_off() + _fivebar().Y['wheel'])


def to_robot(p_module, side: str = 'left'):
    """A point (x, y, z) of the LEFT leg's module frame in the robot frame, for the left leg or the right one. The
    right leg is the left one turned 180 deg about z (the same motors and frame; the five-bar is symmetric in x), so
    a module point (x, y, z) is at (-x, -(y + Y_OFF), z) on the right."""
    x, y, z = p_module
    yo = y_off()
    return (x, y + yo, z) if side == 'left' else (-x, -(y + yo), z)


def z_spine_top() -> float:
    """The cheeks' upper flange outer face (= the floor tray's underside). Two limits: the frame's M5 hole must be
    half a die width (flat) from the bend's centreline, and the flange's inner face must clear the insert bosses."""
    s = STOCK[CHEEK]
    m = frame_mounts()
    z_hole = max(z for _, z in m['holes'])
    hole_r = 5.5 / 2                                                     # M5 clearance in the cheek
    z_rule = z_hole + hole_r + (s['half_die'] - s['ba'] / 2) + s['ossb']
    z_boss = max(f[3] for f in m['face'])                               # the bosses' top on the face
    z_clear = z_boss + 2.0 + s['t']
    return math.ceil(max(z_rule, z_clear) * 2 + 0.5) / 2               # rounded up to 0.5 mm, with margin


# ------------------------------------------------------------------------------------------- the box

TRAY = '5052-0.100'
DECK = '5052-0.100'
BELLY = '6061-0.100'
PALLET = '6061-0.125'
BODY_X = (-160.0, 160.0)            # the floor tray and deck, outside (OML)
BODY_HALF_Y = 127.0                 # 254 wide: the shell's side walls go outside this (T7)
TRAY_LIP = 15.0
DECK_LIP = 20.0
TOP = 216.0                         # the deck's top face (the sim's TOP)
# Four posts at the deck's corners (the battery lives in the belly, so no door path crosses the tray).
POSTS = [(142.0, 109.0), (142.0, -109.0), (-142.0, 109.0), (-142.0, -109.0)]
POST_W = 22.0                       # printed PA6-CF posts, square, M5 inserts at both ends
BELLY_HALF_Y = 58.0                 # the belly plate 320 x 116: the upper links' knee eye bosses sweep past at |y| >= 83
                                    # (fivebar EYE_BOSS), from z +31 down to -169; ISO 13854 asks 25 mm for a finger,
                                    # so nothing of the belly comes nearer (the plan's 160 mm plate left a 3 mm shear edge)
RISER_H = 30.0                      # D41: the turret stands on a 30 mm printed riser on the deck
LIDAR_TO_PAN = 143.0                # the turret's pan axis this far behind the lidar's: sim/robot_v2.py turret_clearance()
                                    # with its 5 mm gap to anything that turns (docs/body-plan.md 1.5)
ISOLATOR_H = 8.0                    # the compute pallet's rubber isolators (est until the part is chosen)


def z_tray_top() -> float:
    return z_spine_top() + STOCK[TRAY]['t']


def z_belly_top() -> float:
    return -z_spine_top()


# ------------------------------------------------------------------------------------------- the turret (TM)


HEAD_BUDGET = {'mass_kg': 1.70, 'com_above_face_mm': 100.0,      # the turret plan's head payload budget (docs/turret-next-plan.md:
               'basis': 'docs/turret-next-plan.md 3.1 (proposed head payload budget)'}   # 1.639 kg with 30 balls today)
TURRET_GROMMET = (-130.0, -60.0)    # the turret harness through the deck, right rear: the turret's DT12 plug is on its right


@functools.lru_cache(maxsize=1)
def tm() -> dict:
    """The turret's mounting face (cad/turret.py): bolts, dowels, centre hole, the foot and bumper, and where the
    pan axis stands on the body (docs/body-plan.md 1.5: 143 mm behind the lidar's axis, the turret's depression table
    is computed for that). The turret's interface file exports/turret/mount.json (docs/turret-next-plan.md N5) wins for
    the mass and centre when it exists; until then the head budget (1.70 kg, centre <= 100 mm above the face)."""
    import sys
    sys.path.insert(0, str(R / 'cad'))
    import turret as tu
    G = tu.Geo()
    out = {'bolts': [tuple(p) for p in tu.TM_BOLTS], 'dowels': [tuple(p) for p in tu.TM_DOWELS], 'hole_d': tu.TM_HOLE,
           'bolt': 'M5', 'dowel_d': 5.0, 'foot_r': G.base_r, 'bumper_r': G.bumper_r[1], 'pan_x': lidar()['x'] - LIDAR_TO_PAN,
           'face_z': TOP + RISER_H, 'mass_kg': HEAD_BUDGET['mass_kg'], 'com_above_face_mm': HEAD_BUDGET['com_above_face_mm'],
           'mass_basis': HEAD_BUDGET['basis'], 'grommet_xy': TURRET_GROMMET}
    f = R / 'exports' / 'turret' / 'mount.json'
    if f.exists():
        m = json.loads(f.read_text())
        mk = m.get('mass_kg') or ((m.get('mass_g') or 0) / 1000.0) or None
        com = m.get('com_mm') or m.get('centre_mm')
        if mk:
            out['mass_kg'] = max(mk, HEAD_BUDGET['mass_kg'])
            out['mass_basis'] = 'exports/turret/mount.json (the budget when larger)'
        if com:
            out['com_above_face_mm'] = max(float(com[2]), HEAD_BUDGET['com_above_face_mm'])
        out['mount_json'] = m
    return out


# ------------------------------------------------------------------------------------------- the lidar (VLP-16)


@functools.lru_cache(maxsize=1)
def lidar() -> dict:
    """The VLP-16 from catalog/sensors_compute.json, as near the deck's front edge as its front locating pin may be:
    the pin's hole must stay half a die (flat) from the deck's front bend, which sets the lidar 5.2 mm back from flush
    (the plan had it flush, x = 108.35; nothing in its view changes: its -15 deg beam passes 22 mm over the deck's
    edge). The cable gland points to +y, so the pins lie fore and aft."""
    cat = json.loads((R / 'catalog/sensors_compute.json').read_text())
    s = next(c for c in cat if c['id'] == 'velodyne-vlp-16')['specs']
    d = s['diameter_mm']
    m = s['mounting']
    pin_sep = 88.9                                                       # "88.9 mm (3.50 in) apart" (m['locating'])
    pin_d = 4.06
    assert '88.9' in m['locating'] and '4.06' in m['locating'], 'VLP-16 locating pattern changed in the catalogue'
    st = STOCK[DECK]
    bend_c = BODY_X[1] - st['ossb'] + st['ba'] / 2                       # the front bend's centreline (flat measure)
    x_pin = bend_c - st['half_die'] - pin_d / 2
    x = min(BODY_X[1] - d / 2, math.floor((x_pin - pin_sep / 2) * 10) / 10)
    return {'d': d, 'h': s['height_mm'], 'oc': s['optical_center_above_base_mm'], 'fov_v': s['fov_v_deg'], 'mass_g': s['mass_g'],
            'x': x, 'centre_thread': '1/4-20 UNC', 'centre_clear_d': 6.8, 'pins': [(x - pin_sep / 2, 0.0), (x + pin_sep / 2, 0.0)],
            'pin_hole_d': 4.06, 'cable_dir': (0.0, 1.0), 'basis': m['centre'] + '; ' + m['locating']}


# ------------------------------------------------------------------------------------------- the J501 (read only)


@functools.lru_cache(maxsize=1)
def j501() -> dict:
    """The J501 carrier, the AGX module's tie-down and the cooler, from the j501-agx project (read only)."""
    f = J501_DIR / 'cad' / 'parameters.json'
    P = json.loads(f.read_text())
    pcb, cool, enc = P['pcb'], P['cooler'], P['enclosure']
    return {'pcb': (pcb['width'], pcb['depth'], pcb['thickness']), 'holes': [tuple(h) for h in pcb['mount_holes']],
            'module_holes': [tuple(h) for h in pcb['module_mount_centers']], 'cooler': tuple(cool['size']),
            'cooler_c': tuple(cool['center_in_pcb']), 'agx_top': cool['agx_top_above_pcb_top'], 'tim': cool['tim_thickness'],
            'cooler_clear_top': cool.get('minimum_fan_clearance', cool.get('minimum_top_clearance', 2.0)),
            'cooler_model': cool.get('model'), 'spreader': cool.get('spreader'), 'fan': cool.get('fan'),
            'aux_fins': cool.get('aux_fins'), 'fins': (cool.get('heatsink') or {}).get('fins'),
            'standoff_h': enc['board_support_height'],
            'tie_screw': enc['heatsink_screw'], 'lowest_component': pcb['lowest_component'],
            'revision': P.get('revision'), 'source': str(f), 'ports': P['ports']}


# The carrier's X runs along the robot's x and its port edges face the sides: its front edge (DC-IN, LAN, audio) is the
# robot's right (-y), its rear edge (USB, HDMI, the J25 CAN/DIO terminal, REC/RST) the left (+y) (docs/body-plan.md 1.9).
J501_AT = (-150.0, -81.5)          # robot (x, y) of the PCB's origin corner


def pcb_to_robot(xp, yp):
    return (J501_AT[0] + xp, J501_AT[1] + yp)


def z_pallet_top() -> float:
    return z_tray_top() + ISOLATOR_H + STOCK[PALLET]['t']


def j501_stack() -> dict:
    """Heights (robot z) of the compute stack on its pallet."""
    j = j501()
    z_pcb0 = z_pallet_top() + j['standoff_h']
    z_pcb1 = z_pcb0 + j['pcb'][2]
    z_cool0 = z_pcb1 + j['agx_top'] + j['tim']
    return {'pallet_top': z_pallet_top(), 'pcb_bottom': z_pcb0, 'pcb_top': z_pcb1, 'cooler_bottom': z_cool0,
            'cooler_top': z_cool0 + j['cooler'][2], 'fan_xy': pcb_to_robot(*j['cooler_c'])}


# ------------------------------------------------------------------------------------------- the leg's sweep


LEG_RANGE = (101.5, 392.0)          # hip line to axle, the stops (exports/leg/leg.json leg_range_mm)
LEANS = (-20.0, 0.0, 20.0)


def summary() -> dict:
    """The numbers other parts of the project read (the sim, the designer): printed by cad/test_body.py."""
    fb = _fivebar()
    return {'spine_w_mm': round(SPINE_W, 3), 'y_off_mm': round(y_off(), 3), 'track_mm': round(track(), 2),
            'z_spine_top_mm': z_spine_top(), 'z_tray_top_mm': round(z_tray_top(), 3), 'top_mm': TOP,
            'body_x_mm': BODY_X, 'body_half_y_mm': BODY_HALF_Y, 'tm_face_z_mm': tm()['face_z'], 'pan_axis_x_mm': round(tm()['pan_x'], 2),
            'lidar_axis_x_mm': round(lidar()['x'], 2), 'wheel_y_module_mm': fb.Y['wheel'], 'centre_plane_module_mm': fb.Y['centre_plane']}


if __name__ == '__main__':
    print(json.dumps(summary(), indent=1))
