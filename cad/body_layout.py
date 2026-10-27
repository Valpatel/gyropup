"""Where everything in the body sits (milestone M5, task T3): every bought part as its real envelope, the keep-out
zones (plugs, the fan's intake, the battery drawer's path), an overlap check, the holes each part needs in the frame,
and the mass and centre-of-mass ledger. Robot frame (mm): x forward, y left, z up from the hip axis.

    .venv/bin/python cad/body_layout.py          # check, then write exports/body/mass.json and layout.json

The body's three zones (docs/body-frame.md):
  the compute bay   the J501 carrier on its pallet at the rear of the floor tray, its fan under the turret's riser
  the power bay     the front of the floor tray behind a power panel (a bent 5052 bulkhead across the body at x = 40
                    that also carries the deck's middle): the converters on DIN rails on its front face, the wheel
                    VESCs, the main switch and fuse, the bus bars and branch fuses, the shunt, the MCU board
  the battery bay   the belly: the 13S2P drawer slides out of the front between the legs (the floor tray cannot hold
                    the cassette, the J501, the 24 V converter and the lidar box together; T3 measured it)
Sizes are from the catalogue (catalog/*.json and catalog/body.json); masses carry their basis.
"""
from __future__ import annotations

import functools
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_params as bp  # noqa: E402

OUT = R / 'exports' / 'body'
G = 9.81


@dataclass
class Item:
    name: str
    box: tuple                    # (x0, x1, y0, y1, z0, z1)
    mass_g: float
    basis: str                    # where the mass comes from: datasheet | catalogue | estimate | CAD
    group: str                    # compute | power | battery | deck | shell | frame | harness
    stage: str = 'P1'             # P0 skid, P1 open frame, P2 head, P3 shell
    catalog: str = ''             # catalogue id
    note: str = ''
    rgb: tuple = (0.45, 0.5, 0.56)
    keepout: bool = False         # a zone that must stay free, not a part (no mass)
    owner: str = ''               # keep-outs: the item they serve (it may sit in its own zone)
    cyl: tuple = None             # (cx, cy, r) for round parts (z from the box): the overlap test uses the circle

    @property
    def centre(self):
        x0, x1, y0, y1, z0, z1 = self.box
        return ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def overlap(a: Item, b: Item, tol=0.05):
    A, B = a.box, b.box
    for k in range(3):
        if not (A[2 * k] < B[2 * k + 1] - tol and B[2 * k] < A[2 * k + 1] - tol):
            return False
    if a.cyl and b.cyl:
        return math.dist(a.cyl[:2], b.cyl[:2]) < a.cyl[2] + b.cyl[2] - tol
    for c, o in ((a.cyl, B), (b.cyl, A)):
        if c:
            dx = max(o[0] - c[0], 0.0, c[0] - o[1])
            dy = max(o[2] - c[1], 0.0, c[1] - o[3])
            if math.hypot(dx, dy) >= c[2] - tol:
                return False
    return True


def check(items, frame_boxes=()):
    """Every pair of parts (and parts against keep-outs other than their own) must not overlap; returns [text]."""
    bad = []
    parts = [i for i in items if not i.keepout]
    zones = [i for i in items if i.keepout]
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if overlap(a, b):
                bad.append(f'{a.name} overlaps {b.name}')
        for z in zones:
            if z.owner != a.name and not a.name.startswith(z.owner or '\0') and overlap(a, z):
                bad.append(f'{a.name} is in {z.name}')
        for fname, fb in frame_boxes:
            if overlap(a, Item(fname, fb, 0, '', 'frame')):
                bad.append(f'{a.name} overlaps the frame\'s {fname}')
    return bad


def box_xyz(x, y, z, sx, sy, sz):
    """A box from its low corner (x, y, z) and size."""
    return (x, x + sx, y, y + sy, z, z + sz)


def centred(cx, cy, z0, sx, sy, sz):
    return (cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z0 + sz)


@functools.lru_cache(maxsize=1)
def catalogue():
    out = {}
    for f in sorted((R / 'catalog').glob('*.json')):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if isinstance(d, list):
            for it in d:
                if isinstance(it, dict) and (it.get('id') or it.get('key')):
                    out[it.get('id') or it.get('key')] = it
    return out


def cat_mass(cid, default=None):
    it = catalogue().get(cid) or {}
    return (it.get('specs') or {}).get('mass_g', default)


def mass_com(rows):
    """Total mass (kg) and centre (mm) of [(name, mass_g, (x, y, z))]."""
    m = sum(r[1] for r in rows)
    c = [sum(r[1] * r[2][k] for r in rows) / m for k in range(3)] if m else [0, 0, 0]
    return m / 1000.0, c


# ------------------------------------------------------------------------------------------- the layout

BUS_XY = []                      # the bus bars' corners on the power plate (+, -), set by layout()
SLOT_X = (40.0, 135.0)          # the tray slot over the spine's front end and the front chase
SLOT_HALF = 15.0
PLATE_H = 50.0                   # the power plate's underside above the tray's top (M5 x 50 standoffs)
PLATE_X = (28.0, 152.0)
PLATE_Y = (-120.0, 86.0)
FUSES = {'kind': 'provisional', 'box': (120.0, 42.0, 32.0), 'mass_g': 90.0,
         'note': 'branch fuse block (sized when the DC-rated fuse system is chosen, catalog/body.json)'}


def j501_items():
    """The compute bay: the J501 carrier on its pallet, the module and cooler, the plug zones of the ports in use and
    the fan's intake column (keep-outs)."""
    import body_frame as bf
    j = bp.j501()
    st = bp.j501_stack()
    W, D, T = j['pcb']
    x0, y0 = bp.J501_AT
    out = [Item('j501_carrier', (x0, x0 + W, y0, y0 + D, st['pcb_bottom'], st['pcb_top']), 225.0,
                'datasheet (Seeed: carrier without module 225 g)', 'compute', 'P0', 'seeed-j501-agx-orin-32gb',
                'J501 carrier: 176 x 163 PCB on 4 x M3 x 16 hex standoffs', (0.16, 0.42, 0.24)),
           Item('j501_top_parts', (x0, x0 + W, y0, y0 + D, st['pcb_top'], st['pcb_top'] + 15.0), 0, '', 'compute', keepout=True,
                owner='agx', note='the carrier\'s top-side parts (connectors, the module socket): within 15 mm')]
    cx, cy = bp.pcb_to_robot(*j['cooler_c'])
    cw, cd, ch = j['cooler']
    sp = j.get('spreader') or {'size': (cw, cd), 'center_in_pcb': j['cooler_c'], 'thickness': 0.0}
    sx, sy = bp.pcb_to_robot(*sp['center_in_pcb'])
    out.append(Item('agx_module', centred(cx, cy, st['pcb_top'], 100.0, 87.0, st['cooler_bottom'] - st['pcb_top']), 280.0,
                    'estimate (NVIDIA publishes none; 100 x 87 x 16 module with its thermal plate)', 'compute', 'P0', '',
                    'AGX Orin 32 GB module under the cooler', (0.2, 0.22, 0.25)))
    # the fitted cooler (j501-agx parameters.json, from the user's photos): the 2 mm copper spreader on the module, the
    # G48R heat-pipe tower and its 9215 fan on top; the fan blows down and the air leaves the fins at their +-y faces
    st_t = sp.get('thickness', 0.0)
    if st_t:
        out.append(Item('agx_spreader', centred(sx, sy, st['cooler_bottom'], sp['size'][0], sp['size'][1], st_t), 200.0,
                        'CAD volume x copper 8.96 g/cm3 (100 x 110 x 2 mm)', 'compute', 'P0', '',
                        'the cooler\'s 2 mm copper spreader on the module', (0.80, 0.50, 0.30)))
    out.append(Item('agx_cooler', centred(cx, cy, st['cooler_bottom'] + st_t, cw, cd, ch - st_t), 450.0,
                    'estimate (G48R: five 6 mm copper heat pipes, 6063 fins, 9215 fan; Seeed publishes no mass)', 'compute', 'P0', '',
                    f"{(j.get('cooler_model') or 'cooler').split(':')[0]}, {cw:g} x {cd:g} x {ch:g} mm", (0.75, 0.76, 0.78)))
    fan_r = (j.get('fan') or {}).get('frame', 84.0) / 2
    out.append(Item('fan_intake', (cx - fan_r, cx + fan_r, cy - fan_r, cy + fan_r, st['cooler_top'], bp.TOP - bp.STOCK[bp.DECK]['t']), 0, '', 'compute',
                    keepout=True, owner='agx_cooler', note='the fan\'s intake column up to the deck (nothing in it)'))
    fw, fd = j.get('fins') or (cw, cd)
    for side, ey in (('left', 1.0), ('right', -1.0)):           # exhaust across the fins (the plates' +-y faces)
        ya = cy + ey * fd / 2
        out.append(Item(f'cooler_exhaust_{side}', (cx - fw / 2, cx + fw / 2, min(ya, ya + ey * 30), max(ya, ya + ey * 30),
                                                   st['cooler_bottom'] + st_t, st['cooler_top'] - (j.get('fan') or {}).get('thickness', 0.0)),
                        0, '', 'compute', keepout=True, owner='agx_cooler', note='hot air leaves the fins here'))
    # the ports in use: their plugs and 40 mm of cable room beyond the PCB's edge (the front edge faces the robot's right)
    used = {'front': ('lan_1g', 'dc_in'), 'rear': ('io_terminal', 'usb_a', 'usb_c', 'hdmi')}
    for side, names in used.items():
        for n in names:
            p = j['ports'][side][n]
            face = (p.get('mate') or {}).get('face') or p.get('box')
            if not face:
                continue
            xa, xb = x0 + face[0] - 3.0, x0 + face[2] + 3.0
            ya, yb = (y0 - 42.0, y0) if side == 'front' else (y0 + D, y0 + D + 42.0)
            out.append(Item(f'plug_{n}', (xa, xb, ya, yb, st['pcb_bottom'] - 2.0, st['pcb_top'] + 22.0), 0, '', 'compute',
                            keepout=True, owner=f'j501_{n}', note=f'{p.get("label") or n}: the mated plug and its cable'))
    for (xp, yp) in j['holes']:
        x, y = bp.pcb_to_robot(xp, yp)
        out.append(Item(f'j501_standoff_{xp}_{yp}', centred(x, y, st['pallet_top'], 6.4, 6.4, j['standoff_h']), 2.0, 'catalogue (M3 x 16 hex)', 'compute', 'P0'))
    for u in json.loads((bp.J501_DIR / 'cad' / 'parameters.json').read_text())['underside_envelopes']['items']:
        if u['role'] != 'card':                     # the SATA plug drops are unused (no drives)
            continue
        a = u['box']
        out.append(Item(f'j501_under_{u["name"]}', (x0 + a[0], x0 + a[3], y0 + a[1], y0 + a[4], st['pcb_bottom'] + a[2], st['pcb_bottom']),
                        0, '', 'compute', keepout=True, owner='j501', note=f'{u["ref"]} on the carrier\'s underside'))
    return out


def layout(cell=None):
    """Every item placed, the keep-outs, and what the frame needs from them. Returns
    {'items': [Item], 'mounts': {part: [...]}, 'checks': [text], 'mass': {...}}."""
    import body_battery as bb
    import body_frame as bf
    cell = cell or bb.CELL
    zt = bp.z_tray_top()
    zd = bp.TOP - bp.STOCK[bp.DECK]['t']
    items = j501_items()
    # ---------------- the power bay. The cables from the belly and the spine's gap come up through the tray slot over the
    # spine's front end (x 40..135, |y| <= 15). The DDR-120C stands on the tray in the left strip; everything else is on
    # the POWER PLATE (5052-H32 0.100 in, PEM nuts for every part) on four M5 x 50 standoffs: the P0 power skid, built
    # and tested on the bench as one plate, then dropped in.
    items.append(Item('tray_slot', (SLOT_X[0], SLOT_X[1], -SLOT_HALF, SLOT_HALF, zt - 20.0, zt + 12.0), 0, '', 'power', keepout=True,
                      note='the cables\' way up from the spine\'s gap and the front chase'))
    items.append(Item('ddr120c_24', box_xyz(-22.0, 89.0, zt, 125.2, 32.0, 112.3), 450.0, 'estimate (datasheet packs 0.51 kg with its carton)',
                      'power', 'P0', 'meanwell-ddr-120c-24', '24 V 5 A, isolated: the J501 and the turret; on a TS35 rail across y in the '
                      'left strip, past the carrier\'s USB-C; output terminals at its rear end, input at the front', (0.62, 0.64, 0.68)))
    pz = zt + PLATE_H                                   # the power plate's underside
    pt = bp.STOCK['5052-0.100']['t']
    items.append(Item('power_plate', (PLATE_X[0], PLATE_X[1], PLATE_Y[0], PLATE_Y[1], pz, pz + pt), 0, '', 'frame', 'P0',
                      keepout=True, owner='plate', note='5052-H32 0.100 in, on four M5 x 50 hex standoffs from the tray'))
    # hanging under the plate (fins and leads down), screws up into the plate's nuts
    items.append(Item('plate_vesc_r', box_xyz(34.0, -68.0, pz - 35.0, 108.0, 50.7, 35.0), 230.0, 'catalogue (estimate)', 'power', 'P0', 'flipsky-75100',
                      'Flipsky 75100, the right wheel, hung under the plate on its four M5 flange holes; leads out of its rear end', (0.17, 0.42, 0.69)))
    items.append(Item('plate_vesc_l', box_xyz(34.0, 17.3, pz - 35.0, 108.0, 50.7, 35.0), 230.0, 'catalogue (estimate)', 'power', 'P0', 'flipsky-75100',
                      'Flipsky 75100, the left wheel', (0.17, 0.42, 0.69)))
    items.append(Item('plate_main_switch', box_xyz(52.0, -116.0, pz - 16.5, 60.0, 45.0, 16.5), 110.0, 'estimate (metal case 60 x 45 x 16.5)', 'power', 'P0',
                      'flipsky-antispark-smart-enhanced-v2', 'Flipsky Anti Spark Switch Smart Enhanced 300A V2.0 (12-84 V, 100 A), low side, '
                      'in a printed cradle under the plate; its 16 mm momentary button on the rear panel (P3)', (0.25, 0.27, 0.3)))
    items.append(Item('plate_shunt', box_xyz(40.0, 32.0, pz + pt, 85.0, 30.0, 25.0), 85.0, 'estimate (150 A / 50 mV meter shunt)', 'power', 'P0',
                      'blue-sea-150a-50mv-shunt', 'the current shunt in the negative lead (the switch\'s load side to the - bus)',
                      (0.7, 0.7, 0.72)))
    # on the plate
    items.append(Item('plate_ddr60l_12', box_xyz(34.0, -118.0, pz + pt, 90.0, 52.5, 62.5), 216.0, 'datasheet (TRC: 216 g)', 'power', 'P0',
                      'meanwell-ddr-60l-12', '12 V 5 A (18-75 V in, isolated): lidar, lights, eyes, the 5 V buck; on a TS35 rail across y',
                      (0.62, 0.64, 0.68)))
    BUS_XY.clear()
    BUS_XY.extend([(34.0, -60.0), (34.0, -36.0)])       # + and - bus bars (frame parts: SendCutSend C110 on printed insulators)
    items.append(Item('plate_mrbf_block', box_xyz(125.0, -15.0, pz + pt, 20.0, 60.9, 44.5), 90.0, 'catalogue (70 g) + MRBF fuse (est 20 g)',
                      'power', 'P0', 'blue-sea-5191-mrbf-terminal-fuse-block', 'main fuse 80 A (Blue Sea 5181) on the battery + lead\'s insulated M10 post',
                      (0.1, 0.1, 0.12)))
    items.append(Item('plate_fuses', box_xyz(36.0, -12.0, pz + pt, 85.0, 42.0, 22.0), 110.0, 'estimate (10 inline MINI holders, 58 V fuses, leads)',
                      'power', 'P0', 'littelfuse-0997-mini-58v', 'the ten branch fuses: Littelfuse MINI 58V in inline holders, bundled on the plate',
                      (0.85, 0.75, 0.2)))
    items.append(Item('plate_mcu_board', box_xyz(32.0, 64.0, pz + pt, 85.0, 22.0, 72.0), 75.0,
                      'estimate (Nucleo-G474RE 48 g + 3 CAN Pal + INA228 + isolator + carrier)', 'power', 'P0', 'st-nucleo-g474re',
                      'balance MCU: the Nucleo-G474RE standing on edge in a printed carrier with three CAN Pal, the INA228 and the '
                      'BMS UART isolator', (0.16, 0.5, 0.3)))
    items.append(Item('plate_buck_5v', box_xyz(124.0, 64.0, pz + pt, 20.0, 20.0, 12.0), 4.0, 'catalogue (Pololu D36V28F5)', 'power', 'P0',
                      'pololu-d36v28f5', '5 V 3.6 A from the 12 V rail: MCU, VN-100, CAN boards, radio-stop receiver', (0.16, 0.5, 0.3)))
    # ---------------- the IMU, rigid on the tray near the hip axis, under the carrier's front
    items.append(Item('vn100', box_xyz(-40.0, -16.55, zt, 35.9, 33.1, 8.9), 15.0, 'catalogue (VectorNav: 15 g)', 'power', 'P0',
                      'vectornav-vn-100-rugged', 'VN-100 Rugged on 2 x M3 + 2 dowels in the tray; its connector faces +x', (0.8, 0.2, 0.2)))
    # ---------------- the lidar's interface box behind the cooler (the G48R's fins blow out at +-y and its fan draws from
    # the deck, so the strip behind its heat pipes' bends is the free one), its cable coiled flat under the deck beside it
    items.append(Item('lidar_box', (-157.0, -122.0, -80.0, 5.0, zt + 45.0, zd - 2.0), 120.0, 'estimate (Polycase LP-41 class, plan 90 g + gland)',
                      'compute', 'P1', '', 'VLP-16 interface box standing on edge on a printed bracket behind the cooler; RJ45 '
                      'down to the J501 1GbE on the carrier\'s right edge', (0.3, 0.3, 0.33)))
    items.append(Item('lidar_coil', (-157.0, -122.0, 12.0, 95.0, zd - 16.0, zd - 2.0), 230.0, 'estimate (3 m of the VLP-16 cable)', 'compute', 'P1', '',
                      'the VLP-16\'s 3 m cable, coiled flat under the deck behind the cooler', (0.3, 0.3, 0.33)))
    # ---------------- the deck: lidar, riser, turret (P2), harness passes
    lid = bp.lidar()
    t = bp.tm()
    items.append(Item('vlp16', (lid['x'] - lid['d'] / 2, lid['x'] + lid['d'] / 2, -lid['d'] / 2, lid['d'] / 2, bp.TOP, bp.TOP + lid['h']), lid['mass_g'],
                      'catalogue (830 g without cable)', 'deck', 'P1', 'velodyne-vlp-16', 'VLP-16 on the deck', (0.17, 0.18, 0.2),
                      cyl=(lid['x'], 0.0, lid['d'] / 2)))
    tj = json.loads((R / 'exports/turret/turret.json').read_text())
    tm = tj['mass_g_with_balls']
    tz = tj['info']['com'][2] - tj['info']['mount']['point'][2]
    items.append(Item('turret', (t['pan_x'] - t['bumper_r'], t['pan_x'] + t['bumper_r'], -t['bumper_r'], t['bumper_r'], t['face_z'], t['face_z'] + 2 * tz),
                      tm, 'CAD (exports/turret/turret.json, with 30 balls)', 'deck', 'P2', '', 'the foam-ball turret on the riser (P1: a 1.5 kg dummy)',
                      (0.55, 0.57, 0.6), cyl=(t['pan_x'], 0.0, t['bumper_r'])))
    # ---------------- the battery in the belly
    b = bb.brick(cell)
    B = bb.bay(b)
    items.append(Item('battery', b.box, b.mass_g, f'cells {bb.CELLS[cell]["source"]}; BMS and build est', 'battery', 'P0', '',
                      f'13S2P {bb.CELLS[cell]["name"]}, {b.capacity_ah:.1f} Ah, the Daly 13S 100 A BMS on top; slides out of the front', (0.95, 0.73, 0.1)))
    items.append(Item('battery_bay', B['outer'], 0, '', 'frame', 'P0', keepout=True, owner='battery', note='the printed bay (walls, floor, skids)'))
    # ---------------- what the frame parts must give these items (holes, slots, nuts)
    mounts = mounts_for(items, B)
    return {'items': items, 'mounts': mounts, 'cell': cell, 'brick': b, 'bay': B}


def _get(items, name):
    return next(i for i in items if i.name == name)


def vesc_holes(it):
    """The Flipsky 75100's four M5 flange holes (100 x 27 mm, catalogue) under a VESC item."""
    x0, x1, y0, y1, *_ = it.box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [(cx + sx * 50.0, cy + sy * 13.5) for sx in (-1, 1) for sy in (-1, 1)]


def mounts_for(items, B):
    """Holes, slots and nuts each frame part needs for the items: {part: [row]} in the rows _mount_features takes:
    (x, y, d, note) | ('slot', x, y, lx, ly, r, note) | ('pem', x, y, spec, note) | ('csk', x, y, spec, d, note)."""
    import body_frame as bf
    m = {'tray': [], 'belly': [], 'deck': [], 'pallet': [], 'plate': [], '_bus_xy': list(BUS_XY)}
    T, BE, D, PL = m['tray'], m['belly'], m['deck'], m['plate']
    # ---- tray
    for x, y in bf.PLATE_STANDOFFS:
        T.append((x, y, 5.5, 'power plate standoff, M5 x 10 ISO 7380 from below'))
    T.append(('slot', (SLOT_X[0] + SLOT_X[1]) / 2, 0.0, SLOT_X[1] - SLOT_X[0], 2 * SLOT_HALF, 6.0, 'cables up from the gap and the front chase'))
    for x, y in bf.ISOLATORS:
        T.append(('pem', x, y, 'S-M4-0', 'compute pallet isolator stud'))
    d = _get(items, 'ddr120c_24')
    cx = (d.box[0] + d.box[1]) / 2
    for y in (d.box[2] + 6.0, d.box[2] + 20.0):          # 8 mm (flat) clear of the tray's side bend
        T.append(('pem', cx, y, 'S-M4-0', 'DDR-120C DIN rail'))
    v = _get(items, 'vn100')
    vx0, vx1, vy0, vy1, *_ = v.box
    vcx = (vx0 + vx1) / 2
    for sx in (-1, 1):                                  # VN-100: 2 x M3 (tapped) 30.84 apart, 17.8 from the connector end; its
        T.append((vcx + sx * 15.42, vy0 + 17.8, 2.5, 'tap M3 x 0.5: VN-100'))      # dowel holes are 3.81 from the screws: a 1.8 mm web,
                                                        # under SendCutSend's minimum, so no dowels (the firmware calibrates the mounting)
    # ---- belly: the battery bay's flanges, the leads' slots
    for x in (-135.0, -80.0, -25.0, 30.0, 85.0, 140.0):
        for sy in (1, -1):
            BE.append(('pem', x, sy * (B['half_y'] + 6.0), 'SS-M5-0', 'battery bay flange'))
    BE.append(('slot', 117.5, 0.0, 45.0, 22.0, 6.0, 'the battery\'s leads up to the power plate (front chase)'))
    BE.append(('slot', -125.0, 0.0, 30.0, 22.0, 6.0, 'the charge port\'s leads up (rear chase)'))
    # ---- deck
    for name, inset, what in (('lidar_box', 12.0, 'lidar interface box bracket'), ('lidar_coil', 20.0, 'lidar cable coil clip')):
        b = _get(items, name).box                     # two M4 from above along the item's longer side
        cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
        pts = ([(b[0] + inset, cy), (b[1] - inset, cy)] if b[1] - b[0] >= b[3] - b[2] else [(cx, b[2] + inset), (cx, b[3] - inset)])
        for x, y in pts:
            D.append((x, y, 4.5, f'{what}, M4 from above'))
    lid = bp.lidar()
    D.append((lid['x'] - 30.0, 88.0, 28.0, 'VLP-16 cable pass: split printed grommet'))
    D.append((-108.0, 78.0, 16.0, 'turret harness grommet (DT06 plug on a 300 mm pigtail)'))
    # ---- power plate
    for name in ('plate_vesc_r', 'plate_vesc_l'):
        for x, y in vesc_holes(_get(items, name)):
            PL.append(('pem', x, y, 'F-M5-2', f'{name[6:]}: M5 x 10 up through its flange'))
    sw = _get(items, 'plate_main_switch')
    for x in (sw.box[0] + 10.0, sw.box[1] - 10.0):
        PL.append(('pem', x, (sw.box[2] + sw.box[3]) / 2, 'F-M4-2', 'switch cradle'))
    dd = _get(items, 'plate_ddr60l_12')
    for y in (dd.box[2] + 8.0, dd.box[3] - 8.0):
        PL.append(('pem', (dd.box[0] + dd.box[1]) / 2, y, 'F-M4-2', 'DDR-60L-12 DIN rail'))
    for name, (bx, by) in zip(('bus_pos', 'bus_neg'), BUS_XY):
        yc = by + bf.BUS_W / 2
        for u in (bf.BUS_INS[0] + 22.5, bf.BUS_INS[1] - 22.5):
            PL.append((bx + u, yc, 4.5, f'{name} insulator, M4 x 10 from below'))
    mr = _get(items, 'plate_mrbf_block')
    PL.append(((mr.box[0] + mr.box[1]) / 2, mr.box[2] + 9.5, 14.0, 'MRBF block\'s M8 post in a printed insulating bushing'))
    sh = _get(items, 'plate_shunt')
    for x in (sh.box[0] + 6.0, sh.box[1] - 6.0):
        PL.append(('pem', x, (sh.box[2] + sh.box[3]) / 2, 'F-M5-2', 'shunt base'))
    mc = _get(items, 'plate_mcu_board')
    for x in (mc.box[0] + 12.0, mc.box[1] - 12.0):
        PL.append(('pem', x, (mc.box[2] + mc.box[3]) / 2, 'F-M4-2', 'MCU carrier'))
    bk = _get(items, 'plate_buck_5v')
    PL.append(((bk.box[0] + bk.box[1]) / 2, (bk.box[2] + bk.box[3]) / 2, 3.4, '5 V buck on an M3 standoff'))
    fu = _get(items, 'plate_fuses')
    for x in (fu.box[0] + 10.0, fu.box[1] - 10.0):
        for y in (fu.box[2] + 6.0, fu.box[3] - 6.0):
            PL.append(('slot', x, y, 4.0, 10.0, 2.0, 'cable-tie slot for the fuse bundle'))
    return m


def frame_boxes():
    """Boxes of the frame parts the items must not overlap (posts, cheeks' flanges, the shelf's standoffs)."""
    out = []
    zt = bp.z_tray_top()
    zd = bp.TOP - bp.STOCK[bp.DECK]['t']
    for k, (x, y) in enumerate(bp.POSTS):
        out.append((f'post_{k + 1}', (x - bp.POST_W / 2, x + bp.POST_W / 2, y - bp.POST_W / 2, y + bp.POST_W / 2, zt, zd)))
    return out


if __name__ == '__main__':
    L = layout()
    bad = check(L['items'], frame_boxes())
    print(f"{len(L['items'])} items, {len(bad)} problems")
    for b in bad:
        print('  ', b)


# ------------------------------------------------------------------------------------------- mass and centre of mass

LEG_EXTRA_G = 150.0              # per leg until exports/leg/leg.json carries the CNC output adapters (the main session,
                                 # 2026-10-27: two 6061 adapters per leg, ~70 g heavier each)
HARDWARE_G = 300.0               # frame screws, standoffs, PEM nuts, inserts, cable ties (est)
HARNESS_G = 400.0                # every wire and connector of the body (est; docs/body-wiring.md lists them)


def leg_rows(h_mm=300.0):
    """Each leg's parts at a stance (robot frame): printed parts from their solids (PA6-CF, 100 %), bought parts from
    exports/leg/bom.json's masses at their posed envelopes' centres. Both legs; [(name, g, (x, y, z))]."""
    import body_frame as bf
    from cadagent.robot import solid_mass_properties
    fb = bp._fivebar()
    dens = json.loads((R / 'catalog/materials.json').read_text())['pa6-cf']['density_g_cm3']
    legs = bf.legs(h_mm)
    bom = {r['key']: r for r in json.loads((R / 'exports/leg/bom.json').read_text())['per_leg']}
    each = lambda k: bom[k]['mass_g_each']
    bought = {'motor_front': each('robstride-rs-04'), 'motor_rear': each('robstride-rs-04'),
              'wheel_tyre': each('odrive-botwheel') * 0.55, 'wheel_hub': each('odrive-botwheel') * 0.45,
              'bearing_61812_front': each('bearing_61812'), 'bearing_61812_rear': each('bearing_61812'),
              'apex_61812': 2 * each('bearing_61812'), 'knee_6201_front_in': each('bearing_6201'), 'knee_6201_front_out': each('bearing_6201'),
              'knee_6201_rear_in': each('bearing_6201'), 'knee_6201_rear_out': each('bearing_6201'), 'knee_pin_front': each('knee_pin'),
              'knee_pin_rear': each('knee_pin'), 'stop_posts': 4 * each('stop_post'), 'apex_circlip': each('circlip_60'),
              'eye_sleeve_front': 2 * each('eye_sleeve'), 'eye_sleeve_rear': 2 * each('eye_sleeve'),
              'screws_lugs': 20 * each('screw_m4x20'), 'screws_links': 16 * each('screw_m5x40'), 'screws_wheel': 4 * each('screw_m6x30')}
    rows = []
    for name, shape in legs.items():
        side, part = name.split('.', 1)
        v = shape.val() if hasattr(shape, 'val') else shape
        c = v.Center()
        if part in bought:
            g = bought[part]
        elif part.startswith(('hip_frame', 'output_adapter', 'upper_link', 'front_link', 'wheel_link', 'apex_spacer', 'stop_sleeve')):
            g = solid_mass_properties(v, dens if not part.startswith('stop_sleeve') else 1.22, 1.0, part).mass * 1000
            c = solid_mass_properties(v, 1.0, 1.0, part)
            c = tuple(x * 1000 for x in c.com)
        else:
            continue
        if not hasattr(c, '__len__'):
            c = (c.x, c.y, c.z)
        rows.append((name, g, tuple(c)))
    rest = {k: bom[k]['mass_g_each'] * bom[k]['qty'] for k in ('nut_m10_nyloc', 'washer_m12_thin', 'knee_spacer', 'insert_m8', 'dowel_5x16',
                                                              'screw_m5x30', 'insert_m5')}
    for side, sy in (('L', 1.0), ('R', -1.0)):
        rows.append((f'{side}.small_hardware', sum(rest.values()), (0.0, sy * (bp.y_off() + 30.0), 0.0)))
        rows.append((f'{side}.cnc_adapter_extra', LEG_EXTRA_G, (0.0, sy * (bp.y_off() - 10.0), 0.0)))
    return rows


def frame_rows(parts):
    from cadagent.robot import solid_mass_properties
    mats = json.loads((R / 'catalog/materials.json').read_text())
    rows = []
    for n, p in parts.items():
        v = p.shape.val() if hasattr(p.shape, 'val') else p.shape
        if p.kind == 'sheet':
            dens = next(st['density'] for st in bp.STOCK.values() if st['material'] == p.material)
            b = solid_mass_properties(v, dens, 1.0, n)
        elif p.kind == 'printed':
            b = solid_mass_properties(v, mats[p.material]['density_g_cm3'], 1.0, n)
        else:
            continue
        rows.append((f'frame.{n}', b.mass * 1000, tuple(x * 1000 for x in b.com)))
    return rows


def ledger(L=None, parts=None, stage='P3'):
    """The robot's mass and centre (robot frame, standing at 300 mm) by group, with every row's basis."""
    import body_frame as bf
    L = L or layout()
    parts = parts or bf.frame_parts(L['mounts'])
    order = ('P0', 'P1', 'P2', 'P3')
    keep = lambda it: order.index(it.stage) <= order.index(stage)
    rows = []
    groups = {}

    def add(group, name, g, c, basis):
        rows.append({'group': group, 'name': name, 'mass_g': round(g, 1), 'com_mm': [round(v, 1) for v in c], 'basis': basis})
        groups.setdefault(group, 0.0)
        groups[group] += g
    for n, g, c in leg_rows():
        add('legs', n, g, c, 'CAD (printed PA6-CF solids) and exports/leg/bom.json')
    for n, g, c in frame_rows(parts):
        add('frame', n, g, c, 'CAD (sheet and printed solids)')
    for it in L['items']:
        if it.keepout or not it.mass_g or not keep(it):
            continue
        add(it.group, it.name, it.mass_g, it.centre, it.basis)
    zt = bp.z_tray_top()
    add('frame', 'hardware', HARDWARE_G, (0.0, 0.0, 40.0), 'estimate')
    add('power', 'harness', HARNESS_G, (60.0, 0.0, zt + 20.0), 'estimate (docs/body-wiring.md)')
    if stage == 'P3':
        for n, g, c, b in SHELL_ITEMS:
            add('shell', n, g, c, b)
    m = sum(r['mass_g'] for r in rows)
    com = [sum(r['mass_g'] * r['com_mm'][k] for r in rows) / m for k in range(3)]
    legs_g = groups.get('legs', 0.0)
    return {'stage': stage, 'total_kg': round(m / 1000, 2), 'com_mm': [round(v, 1) for v in com], 'groups_kg': {k: round(v / 1000, 3) for k, v in groups.items()},
            'legs_kg': round(legs_g / 1000, 2), 'body_and_head_kg': round((m - legs_g) / 1000, 2), 'rows': rows,
            'budget': {'robot_kg': 28.5, 'body_and_head_kg': 10.3, 'com_x_mm': 10.0, 'com_y_mm': 5.0, 'basis': 'docs/body-plan.md 1.8'}}


# the P3 shell and what it carries (docs/body-plan.md 1.5, 1.7; the shell is T7's)
SHELL_ITEMS = [
    ('shell_panels', 800.0, (0.0, 0.0, 150.0), 'estimate (PETG 3 mm side, front and rear walls, the door and hatches)'),
    ('depth_camera_front', 75.0, (147.0, 0.0, 188.0), 'catalogue (D435 75 g)'),
    ('depth_camera_rear', 75.0, (-147.0, 0.0, 188.0), 'catalogue (D435 75 g)'),
    ('eyes', 11.0, (157.0, 0.0, 200.0), 'catalogue (DualEye 11 g)'),
    ('eye_controller', 8.0, (150.0, 0.0, 195.0), 'catalogue (QT Py ESP32-S3)'),
    ('ear_pod_l', 154.0, (20.0, 155.0, 165.0), 'catalogue (SSC1 154 g each)'),
    ('ear_pod_r', 154.0, (20.0, -155.0, 165.0), 'catalogue (SSC1 154 g each)'),
    ('belly_box_skids', 120.0, (0.0, 0.0, -150.0), 'estimate (TPU skids, the bay door)'),
]
