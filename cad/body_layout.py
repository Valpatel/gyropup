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
import os
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
PLATE_H = 42.0                   # the power plate's underside above the tray's top (printed PA6-CF posts, M5 inserts both ends)
PLATE_X = (28.0, 152.0)
PLATE_Y = (-120.0, 86.0)
FUSES = {'kind': 'provisional', 'box': (120.0, 42.0, 32.0), 'mass_g': 90.0,
         'note': 'branch fuse block (sized when the DC-rated fuse system is chosen, catalog/body.json)'}


def j501_items():
    """The compute bay: the J501 carrier on its pallet, the module and cooler, the plug zones of the ports in use and
    the fan's exhaust column (keep-outs)."""
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
    # G48R heat-pipe tower and its 9215 fan on top; the fan blows UP (j501-agx 94da39d): it draws the body's air in through
    # the fins' open +-y faces and blows it up through the deck's cells and out of the riser's sides
    st_t = sp.get('thickness', 0.0)
    if st_t:
        out.append(Item('agx_spreader', centred(sx, sy, st['cooler_bottom'], sp['size'][0], sp['size'][1], st_t), 200.0,
                        'CAD volume x copper 8.96 g/cm3 (100 x 110 x 2 mm)', 'compute', 'P0', '',
                        'the cooler\'s 2 mm copper spreader on the module', (0.80, 0.50, 0.30)))
    out.append(Item('agx_cooler', centred(cx, cy, st['cooler_bottom'] + st_t, cw, cd, ch - st_t), 450.0,
                    'estimate (G48R: five 6 mm copper heat pipes, 6063 fins, 9215 fan; Seeed publishes no mass)', 'compute', 'P0', '',
                    f"{(j.get('cooler_model') or 'cooler').split(':')[0]}, {cw:g} x {cd:g} x {ch:g} mm", (0.75, 0.76, 0.78)))
    fan_r = (j.get('fan') or {}).get('frame', 84.0) / 2
    out.append(Item('fan_column', (cx - fan_r, cx + fan_r, cy - fan_r, cy + fan_r, st['cooler_top'], bp.TOP - bp.STOCK[bp.DECK]['t']), 0, '', 'compute',
                    keepout=True, owner='agx_cooler', note='the fan\'s exhaust column up to the deck (nothing in it; the fan duct)', cyl=(cx, cy, fan_r)))
    fw, fd = j.get('fins') or (cw, cd)
    for side, ey in (('left', 1.0), ('right', -1.0)):           # the air in across the fins (the plates' +-y faces)
        ya = cy + ey * fd / 2
        out.append(Item(f'cooler_fins_{side}', (cx - fw / 2, cx + fw / 2, min(ya, ya + ey * 30), max(ya, ya + ey * 30),
                                                   st['cooler_bottom'] + st_t, st['cooler_top'] - (j.get('fan') or {}).get('thickness', 0.0)),
                        0, '', 'compute', keepout=True, owner='agx_cooler', note='the cooler draws the body\'s air in here (keep it open)'))
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
    for u in bp.j501_params()['underside_envelopes']['items']:
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
    cell = 'DCB609'
    zt = bp.z_tray_top()
    zd = bp.TOP - bp.STOCK[bp.DECK]['t']
    items = j501_items()
    # ---------------- the power bay. The cables from the belly and the spine's gap come up through the tray slot over the
    # spine's front end (x 40..135, |y| <= 15). The DDR-120C stands on the tray in the left strip; everything else is on
    # the POWER PLATE (5052-H32 0.100 in, PEM nuts for every part) on four printed posts: the P0 power skid, built
    # and tested on the bench as one plate, then dropped in.
    items.append(Item('tray_slot', (SLOT_X[0], SLOT_X[1], -SLOT_HALF, SLOT_HALF, zt - 20.0, zt + 12.0), 0, '', 'power', keepout=True,
                      note='the cables\' way up from the spine\'s gap and the front chase'))
    pz = zt + PLATE_H                                   # the power plate's underside
    pt = bp.STOCK['5052-0.100']['t']
    items.append(Item('power_plate', (PLATE_X[0], PLATE_X[1], PLATE_Y[0], PLATE_Y[1], pz, pz + pt), 0, '', 'frame', 'P0',
                      keepout=True, owner='plate', note='5052-H32 0.100 in, on four printed PA6-CF posts from the tray'))
    # hanging under the plate (fins and leads down), screws up into the plate's nuts
    items.append(Item('plate_vesc_r', box_xyz(37.0, -68.0, pz - 35.0, 108.0, 50.7, 35.0), 230.0, 'catalogue (estimate)', 'power', 'P0', 'flipsky-75100',
                      'Flipsky 75100, the right wheel, hung under the plate on its four M5 flange holes; leads out of its rear end', (0.17, 0.42, 0.69)))
    items.append(Item('plate_vesc_l', box_xyz(37.0, 17.3, pz - 35.0, 108.0, 50.7, 35.0), 230.0, 'catalogue (estimate)', 'power', 'P0', 'flipsky-75100',
                      'Flipsky 75100, the left wheel', (0.17, 0.42, 0.69)))
    # the switch hangs 3 mm under the plate in its cradle: the 12 V rail's screw tips come through above it
    items.append(Item('plate_main_switch', box_xyz(52.0, -116.0, pz - 19.5, 60.0, 45.0, 16.5), 110.0, 'estimate (metal case 60 x 45 x 16.5)', 'power', 'P0',
                      'flipsky-antispark-smart-enhanced-v2', 'Flipsky Anti Spark Switch Smart Enhanced 300A V2.0 (12-84 V, 100 A), low side, '
                      'in a printed cradle under the plate; its 16 mm momentary button on the rear panel (P3)', (0.25, 0.27, 0.3)))
    items.append(Item('plate_shunt', box_xyz(40.0, 32.0, pz + pt + 3.0, 85.0, 30.0, 25.0), 85.0,     # on 3 mm printed spacers: a VESC screw's tip under it
                      'estimate (150 A / 50 mV meter shunt)', 'power', 'P0',
                      'blue-sea-150a-50mv-shunt', 'the current shunt in the negative lead (the switch\'s load side to the - bus)',
                      (0.7, 0.7, 0.72)))
    # on the plate
    # D65: the bus is 30-41 V, under the DDR-120C-24's 33.6 V minimum. One TRACO TEP 150-4812WI (18-75 V in, isolated,
    # 12 V 12.5 A, 150 W) takes the DDR-120C-24's and the DDR-60L-12's places: the J501 (12-36 V in) and the 12 V rail
    # (lidar, lights, eyes, the 5 V buck) from one converter (D66: the turret has its own). It stands on its long edge where
    # the DDR-60L-12 stood, its base flange screwed to a printed bracket's upright at the plate's right edge.
    d = DCDC
    zc = pz + pt + bf.DCDC_FOOT_T
    items.append(Item('power_dcdc', (d['x'][0], d['x'][1], d['y'][0], d['y'][1], zc, zc + d['h']), d['mass_g'], d['mass_basis'], 'power', 'P0',
                      'traco-tep-150-4812wi', '12 V 12.5 A from 18-75 V, isolated: the J501 and the 12 V rail; standing on its long edge on '
                      'a printed bracket at the plate\'s right edge, terminals at its ends', (0.62, 0.64, 0.68)))
    BUS_XY.clear()
    BUS_XY.extend([(34.0, -60.0), (34.0, -36.0)])       # + and - bus bars (frame parts: SendCutSend C110 on printed insulators)
    items.append(Item('plate_mrbf_block', box_xyz(125.0, -15.0, pz + pt + 3.0, 20.0, 60.9, 44.5), 90.0,     # on 3 mm spacers: a VESC screw's tip
                      'catalogue (70 g) + MRBF fuse (est 20 g)',
                      'power', 'P0', 'blue-sea-5191-mrbf-terminal-fuse-block', 'main fuse 80 A (Blue Sea 5181) on the battery + lead\'s insulated M10 post',
                      (0.1, 0.1, 0.12)))
    # the fuse bundle stays clear of the left VESC's screw tips at y 29
    items.append(Item('plate_fuses', box_xyz(36.0, -12.0, pz + pt, 85.0, 36.0, 22.0), 110.0, 'estimate (10 inline MINI holders, 58 V fuses, leads)',
                      'power', 'P0', 'littelfuse-0997-mini-58v', 'the ten branch fuses: Littelfuse MINI 58V in inline holders, bundled on the plate',
                      (0.85, 0.75, 0.2)))
    items.append(Item('plate_mcu_board', box_xyz(32.0, 64.0, pz + pt, 85.0, 22.0, 72.0), 75.0,
                      'estimate (Nucleo-G474RE 48 g + 4 CAN Pal + INA228 + QT Py ESP32-S3 + carrier)', 'power', 'P0', 'st-nucleo-g474re',
                      'balance MCU: the Nucleo-G474RE standing on edge in a printed carrier with four CAN Pal, the INA228 and a QT Py '
                      'ESP32-S3 that reads the BMS over Bluetooth (no wire to the BMS: its UART ground is B-)', (0.16, 0.5, 0.3)))
    items.append(Item('plate_buck_5v', box_xyz(124.0, 64.0, pz + pt, 20.0, 20.0, 12.0), 4.0, 'catalogue (Pololu D36V28F5)', 'power', 'P0',
                      'pololu-d36v28f5', '5 V 3.6 A from the 12 V rail: MCU, VN-100, CAN boards, radio-stop receiver', (0.16, 0.5, 0.3)))
    # ---------------- the IMU, rigid on the tray near the hip axis, under the carrier's front
    items.append(Item('vn100', box_xyz(-40.0, -16.55, zt, 35.9, 33.1, 8.9), 15.0, 'catalogue (VectorNav: 15 g)', 'power', 'P0',
                      'vectornav-vn-100-rugged', 'VN-100 Rugged on 2 x M3 + 2 dowels in the tray; its connector faces +x', (0.8, 0.2, 0.2)))
    # ---------------- the lidar's interface box behind the cooler (the G48R's fins draw in at +-y and its fan blows up through
    # the deck, so the strip behind its heat pipes' bends is the free one), its cable coiled flat under the deck beside it
    items.append(Item('lidar_box', (-156.0, -121.0, 10.0, 95.0, zt + 53.0, zd - 2.0), 120.0, 'estimate (Polycase LP-41 class, plan 90 g + gland)',
                      'compute', 'P1', '', 'VLP-16 interface box standing on edge on a printed bracket behind the cooler, left; RJ45 '
                      'over the carrier to its 1GbE on the right edge', (0.3, 0.3, 0.33)))
    items.append(Item('lidar_coil', (-156.0, -121.0, -48.0, 5.0, zd - 16.0, zd - 2.0), LIDAR_CABLE_G, LIDAR_CABLE_BASIS, 'compute', 'P1', '',
                      'the VLP-16\'s 3 m cable, coiled flat under the deck behind the cooler, clear of the turret harness\'s drop', (0.3, 0.3, 0.33)))
    gx, gy = bp.TURRET_GROMMET
    items.append(Item('turret_harness_drop', (gx - 12.0, gx + 12.0, gy - 12.0, gy + 12.0, zt + 45.0, zd), 0, '', 'deck', keepout=True,
                      owner='turret', note='the turret\'s 300 mm pigtail down through its grommet (docs/turret-next-plan.md 3.1)'))
    # ---------------- the deck: lidar, riser, turret (P2), harness passes
    lid = bp.lidar()
    t = bp.tm()
    pb = bp.turret_plug_box()
    items.append(Item('turret_plug_sweep', pb['box'], 0, '', 'deck', keepout=True, owner='turret',
                      note=f"the turret's DT06-12SA plug and the 30 mm it withdraws ({pb['source']})"))
    items.append(Item('vlp16', (lid['x'] - lid['d'] / 2, lid['x'] + lid['d'] / 2, -lid['d'] / 2, lid['d'] / 2, bp.TOP, bp.TOP + lid['h']), lid['mass_g'],
                      'catalogue (830 g without cable)', 'deck', 'P1', 'velodyne-vlp-16', 'VLP-16 on the deck', (0.17, 0.18, 0.2),
                      cyl=(lid['x'], 0.0, lid['d'] / 2)))
    tj = json.loads((R / 'exports/turret/turret.json').read_text())
    hz = t['com_above_face_mm']                       # the head budget: 1.70 kg with its centre 100 mm above the TM face
    items.append(Item('turret', (t['pan_x'] - t['bumper_r'], t['pan_x'] + t['bumper_r'], -t['bumper_r'], t['bumper_r'], t['face_z'], t['face_z'] + 2 * hz),
                      1000.0 * t['mass_kg'], f"budget {t['mass_kg']} kg (turret.json: {tj['mass_g_with_balls'] / 1000:.3f} kg with 30 balls); "
                      + t['mass_basis'], 'deck', 'P2', '', 'the foam-ball turret on the riser (P1: a dummy of the budget mass)',
                      (0.55, 0.57, 0.6), cyl=(t['pan_x'], 0.0, t['bumper_r'])))
    # ---------------- the battery in the belly (D65): two DCB609 packs on their rail adapters
    g = bb.geometry()
    for k, box_ in bb.pack_boxes().items():
        items.append(Item(f'battery_{k}', box_, bb.PACK['mass_g'], bb.PACK['source'], 'battery', 'P0', 'dewalt-dcb609',
                          f'{bb.PACK["name"]}: slides out of the {k} door', (0.99, 0.73, 0.07)))
    for k, box_ in bb.adapter_boxes().items():
        items.append(Item(f'battery_adapter_{k}', box_, bb.ADAPTER['mass_g'], bb.ADAPTER['basis'], 'battery', 'P0', 'terrafirma-dewalt-20v-adapter-10awg',
                          f'the {k} pack\'s rail adapter (10 AWG leads, 30 A), screwed to its printed plate', (0.15, 0.15, 0.17)))
    B = {'outer': (g['x_out'][0], g['x_out'][1], -g['side_out'], g['side_out'], g['z_bottom'], g['z_belly']), 'half_y': g['side_out'],
         'bottom_z': g['z_bottom']}
    items.append(Item('battery_bay', B['outer'], 0, '', 'frame', 'P1', keepout=True, owner='battery', note='the bay (floor, sides, rails, doors, skids)'))
    # ---------------- what the frame parts must give these items (holes, slots, nuts)
    mounts = mounts_for(items, B)
    return {'items': items, 'mounts': mounts, 'cell': cell, 'brick': None, 'bay': B}


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
        T.append((x, y, 5.5, 'power plate post, M5 x 10 ISO 7380 up from below into its insert'))
    T.append(('slot', (SLOT_X[0] + SLOT_X[1]) / 2, 0.0, SLOT_X[1] - SLOT_X[0], 2 * SLOT_HALF, 6.0, 'cables up from the gap and the front chase'))
    for x, y in bf.ISOLATORS:
        T.append(('pem', x, y, 'S-M4-0', 'compute pallet isolator stud'))
    v = _get(items, 'vn100')
    vx0, vx1, vy0, vy1, *_ = v.box
    vcx = (vx0 + vx1) / 2
    for sx in (-1, 1):                                  # VN-100: 2 x M3 (tapped) 30.84 apart, 17.8 from the connector end; its
        T.append((vcx + sx * 15.42, vy0 + 17.8, 2.5, 'tap M3 x 0.5: VN-100'))      # dowel holes are 3.81 from the screws: a 1.8 mm web,
                                                        # under SendCutSend's minimum, so no dowels (the firmware calibrates the mounting)
    # ---- belly: the bay's rails and adapter plates (S-M4-0 beyond the cheeks' ends), the leads' slot
    import body_battery as bb
    for x, yc in bb.rail_holes():
        for sy in (1, -1):
            BE.append(('pem', x, sy * yc, 'S-M4-0', 'battery bay rail'))
    for k in ('front', 'rear'):
        for x, y in bb.plate_holes(k):
            BE.append(('pem', x, y, 'S-M4-0', f'{k} pack adapter plate'))
    BE.append(('slot', bb.LEADS_SLOT[0], 0.0, bb.LEADS_SLOT[1], 22.0, 6.0, 'the packs\' two leads up into the spine\'s gap'))
    # ---- deck
    for name, inset, what in (('lidar_box', 12.0, 'lidar interface box bracket'), ('lidar_coil', 20.0, 'lidar cable coil clip')):
        b = _get(items, name).box                     # two M4 from above along the item's longer side
        cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
        pts = ([(b[0] + inset, cy), (b[1] - inset, cy)] if b[1] - b[0] >= b[3] - b[2] else [(cx, b[2] + inset), (cx, b[3] - inset)])
        for x, y in pts:
            D.append((x, y, 4.5, f'{what}, M4 from above'))
    lid = bp.lidar()
    D.append((lid['x'] - 30.0, 88.0, 28.0, 'VLP-16 cable pass: split printed grommet'))
    D.append((bp.TURRET_GROMMET[0], bp.TURRET_GROMMET[1], 17.5, 'turret harness grommet, right rear (the DT12 plug is on the turret\'s right)'))
    # ---- power plate
    for name in ('plate_vesc_r', 'plate_vesc_l'):
        for x, y in vesc_holes(_get(items, name)):
            PL.append(('pem', x, y, 'F-M5-2', f'{name[6:]}: M5 x 10 up through its flange'))
    sw = _get(items, 'plate_main_switch')
    for x in (sw.box[0] + 10.0, sw.box[1] - 10.0):
        PL.append(('pem', x, (sw.box[2] + sw.box[3]) / 2, 'F-M4-2', 'switch cradle'))
    for x, y in bf.dcdc_bracket_holes():                  # the converter's bracket: two M4 on its inner side
        PL.append(('pem', x, y, 'F-M4-2', 'the converter\'s bracket'))
    for name, (bx, by) in zip(('bus_pos', 'bus_neg'), BUS_XY):
        yc = by + bf.BUS_W / 2
        for u in (bf.BUS_INS[0] + 22.5, bf.BUS_INS[1] - 22.5):
            PL.append((bx + u, yc, 3.4, f'{name} insulator, M3 x 8 up from below into its insert'))
    mr = _get(items, 'plate_mrbf_block')
    PL.append(((mr.box[0] + mr.box[1]) / 2, mr.box[2] + 9.5, 14.0, 'MRBF block\'s M8 post in a printed insulating bushing'))
    sh = _get(items, 'plate_shunt')
    for x in (sh.box[0] + 10.0, sh.box[1] - 6.0):      # the first 12.8 mm from the left VESC's flange nut
        PL.append(('pem', x, (sh.box[2] + sh.box[3]) / 2, 'F-M5-2', 'shunt base'))
    mc = _get(items, 'plate_mcu_board')
    for x in (mc.box[0] + 25.0, mc.box[1] - 12.0):      # the first clear of the plate's post at (44, 80)
        PL.append(('pem', x, (mc.box[2] + mc.box[3]) / 2, 'F-M4-2', 'MCU carrier'))
    bk = _get(items, 'plate_buck_5v')
    PL.append(((bk.box[0] + bk.box[1]) / 2, (bk.box[2] + bk.box[3]) / 2, 3.4, '5 V buck on an M3 standoff'))
    fu = _get(items, 'plate_fuses')
    for x in (fu.box[0] + 10.0, fu.box[1] - 10.0):
        for y in (fu.box[2] + 6.0, 24.0):                 # y 24: P3's fuse board ties through the same slot (body_fuse_board.MOUNTS)
            PL.append(('slot', x, y, 4.0, 10.0, 2.0, 'cable-tie slot for the fuse bundle'))
    return m


DCDC = {'x': (30.0, 128.0), 'y': (-118.0, -82.0), 'h': 65.0, 'mass_g': 300.0,     # its base flange at y -118, on the bracket's upright
        'mass_basis': 'TRC lists 300 g (the 4815WI); 98 x 65 x 35.7 mm (TRACO\'s outline as Farnell and RS give it): measure on arrival'}


def frame_boxes():
    """Boxes of the frame parts the items must not overlap (posts, cheeks' flanges, the shelf's standoffs)."""
    out = []
    zt = bp.z_tray_top()
    zd = bp.TOP - bp.STOCK[bp.DECK]['t']
    for k, (x, y) in enumerate(bp.POSTS):
        out.append((f'post_{k + 1}', (x - bp.POST_W / 2, x + bp.POST_W / 2, y - bp.POST_W / 2, y + bp.POST_W / 2, zt, zd)))
    out.append(('deck', (bp.BODY_X[0], bp.BODY_X[1], -bp.BODY_HALF_Y, bp.BODY_HALF_Y, zd - 1.0, bp.TOP)))   # 1 mm under it kept clear
    for k, (x, y) in enumerate(__import__('body_frame').PLATE_STANDOFFS):
        w = __import__('body_frame').PLATE_POST_W
        out.append((f'plate_post_{k + 1}', (x - w / 2, x + w / 2, y - w / 2, y + w / 2, zt, zt + PLATE_H)))
    return out


# ------------------------------------------------------------------------------------------- mass and centre of mass

HARDWARE_G = 300.0               # frame screws, standoffs, PEM nuts, inserts, cable ties (est)
# lever 14 (taken on #10, D71): the VLP-16's 3 m cable shortened to 1 m (the coordinator's call; Velodyne's waiver to read):
# 230 g for 3 m coiled, so about 77 g for 1 m
LIDAR_CABLE_G = 77.0
LIDAR_CABLE_BASIS = 'estimate: the VLP-16 cable cut to 1 m (lever 14; 230 g for the 3 m coil x 1/3)'
WHEEL_CONNECTORS_G = 45.0       # D69: a DTP 4-way and a DT 6-way pair a wheel, mated, with contacts (est)
HARNESS_G = 400.0                # every wire and connector of the body (est; docs/body-electrical.md lists them)
LEG_STOPS_EXTRA_G = 200.0        # per leg: the hip frame's 13 mm flanges and the stop redesign (main cdda86d, 2026-10-27: 'roughly
                                 # 0.2 kg' over leg.json's 9.28 kg; D53 says 204 g) until exports/leg/leg.json carries them
LEG_TOTAL_BEFORE_STOPS_G = 9282  # leg.json's mass_g.total that the 0.2 kg was announced against: once the leg publishes another
                                 # total (its stops and the strength fixes in), the ledger takes that total as it is

# D71 (docs/decisions.yaml, 2026-10-28): the robot is designed for 37.5 kg (18.75 kg a leg) in every strength case and held
# under 37.0 kg as built (it replaces D69's 35.5 / 35.0 kg and D57's 32.5 / 32.0 kg); the on-call savings levers stay
# listed as margin. The sub-budgets split the 37.0 kg: each leg is leg.json with D53's stops (9.48 kg) plus the D69
# wheel's 1.33 kg over the BotWheel and 40 g for the foot's clamp hardware (10.85 kg); the body and head get the rest
# (15.3 kg). cad/test_body.py gates every commit on it.
BUDGET = {'robot_kg': 37.0, 'legs_kg_each': 10.85, 'body_and_head_kg': 15.3, 'design_mass_kg': 37.5, 'design_half_mass_kg': 18.75,
          'com_x_mm': 10.0, 'com_y_mm': 5.0,
          'basis': 'D71 (37.0 kg as built, 37.5 kg design; it replaces D69\'s 35.0 / 35.5 kg); legs 2 x 10.85 kg (leg.json + D53 stops '
                   '+ the D69 wheel at its listed 3.53 kg + the clamp hardware), body and head 15.3 kg'}

# D69's wheel: a 10 in hoverboard-class hub motor with a 10 x 2.125 pneumatic tyre. exports/leg/bom.json still lists the
# ODrive BotWheel (2.2 kg) until the leg workstream's foot change lands (issue #25); until then the ledger puts this wheel
# in the BotWheel's rows (the rotor 60 %: tyre, rim and magnets; the stator, shaft and halls 40 %), at the centres of the
# wheel's solids (cad/body_params.py _fivebar() draws D69's wheel in the leg's place). The mass is the one listed number read on a
# seller's page; D69 brackets 3.5-4.0 kg and two motors are weighed before the foot is cut (W1): GYROPUP_WHEEL_CHANGE_G adds
# a change per wheel on top (e.g. 470 for the 4.0 kg the leg rig simulated).
D69_WHEEL = {'key': 'hoverboard-10in-36v-350w', 'mass_g': 3530.0, 'od_mm': 254.0, 'tyre_width_mm': 54.0, 'rotor_share': 0.6,
             'botwheel_width_mm': 44.6, 'sim_upper_mass_g': 4000.0,
             'basis': 'D69 wheel: e-gizmo 230300029 lists 3.53 kg with the 10 x 2.125 pneumatic tyre (research/air-tyre-hub-wheels.md 3); '
                      'weigh two before the foot is cut (docs/wheel-change-plan.md W1)'}

# The mass levers of docs/body-next-plan.md 2.3, in its order: scheduled for P2/P3, then on call when the ledger crosses
# the ceiling (D57). grams < 0 saves mass. 'taken' says how the ledger shows the lever done (a check on the CAD), so the
# status is never typed by hand: (key, n, grams, cost_usd, stage, kind, what, taken-check name)
LEVERS = [
    ('shell_2mm', 1, -240, 0.0, 'P3', 'scheduled', 'shell panels in 2 mm PETG with 1.6 mm ribs instead of 3 mm (PA6-CF at the ear-pod bosses)', 'shell_from_cad'),
    ('tray_cutouts', 2, -150, 62.0, 'P3', 'scheduled', 'floor tray Rev B: lightening cutouts where nothing bolts and T1 is low (1/8 in stays)', 'tray_lightened'),
    ('deck_cutouts', 3, -120, 65.0, 'P3', 'scheduled', 'deck Rev B: cutouts outside the lidar, the TM pattern and the intake field', 'deck_lightened'),
    ('turret_plate', 4, +135, 25.0, 'P2', 'scheduled', 'the turret mount plate under the deck at the riser, 6061-T6 0.125 in, pocketed (D59)', 'turret_plate'),
    ('hollow_posts', 5, -100, 0.0, 'P2', 'scheduled', 'deck posts printed hollow (22 mm square, 4 mm walls) instead of solid', 'hollow_posts'),
    ('pallet_cutouts', 6, -60, 30.0, 'P3', 'scheduled', 'compute pallet cutouts under the module between the tie-down and the standoffs', 'pallet_lightened'),
    ('fuse_board', 7, -35, 20.0, 'P3', 'scheduled', 'the fuse board (D60) instead of ten inline MINI holders and their leads', 'fuse_board'),
    ('board_shunt', 8, -75, 3.0, 'P3', 'scheduled', 'the 1 mOhm shunt on the fuse board instead of the 85 g Blue Sea 150 A block', 'board_shunt'),
    ('harness_10awg', 9, -60, 25.0, 'P2', 'scheduled', 'the main path in 10 AWG, the VESC leads in 14 AWG, lengths cut to P0\'s measurements', 'harness_10awg'),
    ('pololu_12v', 10, 0, 0.0, 'P3', 'retired', 'Pololu D42V110F12 instead of the DDR-60L-12: moot since D65 (the TRACO TEP 150 replaced the DDR-60L-12)', None),
    ('cheeks_rev_b', 11, -150, 120.0, 'P3', 'on call', 'cheeks Rev B: lightening windows where the strength envelope is under 25 MPa (taken on #10)', 'cheeks_lightened'),
    ('alu_standoffs', 12, -80, 30.0, 'P3', 'on call', 'aluminium M5 x 120 hex standoffs in place of the printed deck posts', None),
    ('cooler_34mm', 13, -200, 49.0, 'P3', 'on call', 'the 34 mm WS-RDN-601 cooler instead of the fitted G48R (the user\'s call after the thermal test)', None),
    ('lidar_cable_1m', 14, -153, 0.0, 'P3', 'on call', 'the VLP-16 cable shortened to 1 m (taken on #10; Velodyne\'s waiver to read)', 'lidar_cable_1m'),
    ('turret_levers', 15, -51, 0.0, 'P2', 'on call', 'the turret\'s own: a 24-ball hopper, a one-board bay (its plan, not scheduled here)', None),
    # after D69 (issue #10): what else could close the gap, none taken without the user's or the coordinator's word
    ('packs_weighed', 16, -210, 0.0, 'P3', 'on call', 'the two DCB609 at DeWalt\'s DCB547-XJ sheet\'s 1.46 kg (taken on #10) against the US page\'s 1.565 kg: weigh one', 'packs_sheet'),
    ('wheel_8in5', 17, -460, 0.0, 'P1', 'on call', 'D69\'s backup wheel, the 8.5 in of the same family (about 3.3 kg each, unverified): jump +15 mm, kerb 35 mm', None),
    ('packs_6ah', 18, -1000, 0.0, 'P1', 'on call', 'two DCB606 FLEXVOLT 6.0 Ah in the same bay and adapters (about 1.0 kg lighter the pair, 2/3 the energy: masses to read from DeWalt)', None),
]


def wheel_is_d69_override() -> bool:
    """True while exports/leg/bom.json still lists the BotWheel: the ledger then carries D69's wheel in its place."""
    keys = {r['key'] for r in json.loads((R / 'exports/leg/bom.json').read_text())['per_leg']}
    return 'odrive-botwheel' in keys


def wheel_g() -> float:
    """One wheel's mass (g) in the ledger: D69's wheel while the leg's BOM still lists the BotWheel, else the leg's own."""
    rows = {r['key']: r for r in json.loads((R / 'exports/leg/bom.json').read_text())['per_leg']}
    if 'odrive-botwheel' in rows:
        return D69_WHEEL['mass_g']
    hub = next((r for k, r in rows.items() if 'hoverboard' in k or 'hub-motor' in k), None)
    return hub['mass_g_each'] if hub else D69_WHEEL['mass_g']


def leg_stops_extra_g() -> tuple:
    """(grams a leg, basis): the stops' and flanges' mass the ledger adds to exports/leg/leg.json's total until the leg
    publishes a total with them in."""
    total = json.loads((R / 'exports/leg/leg.json').read_text())['mass_g']['total']
    if round(total) == LEG_TOTAL_BEFORE_STOPS_G:
        return LEG_STOPS_EXTRA_G, f'leg.json {total} g + {LEG_STOPS_EXTRA_G:.0f} g announced for the stops and flanges (D53)'
    return 0.0, f'leg.json {total} g (published with the stops in)'


def lever_taken(check: str, parts=None, L=None) -> bool:
    """Whether a lever shows in the CAD (its check names what to look for)."""
    import body_frame as bf
    parts = parts or {}
    if check == 'turret_plate':
        return 'turret_plate' in parts
    if check == 'hollow_posts':
        p = parts.get('post_1')
        if p is None:
            return False
        v = (p.shape.val() if hasattr(p.shape, 'val') else p.shape).Volume()
        return v < 0.9 * bp.POST_W ** 2 * bf.post_height()
    if check in ('tray_lightened', 'deck_lightened', 'pallet_lightened', 'cheeks_lightened'):
        name = {'tray_lightened': 'floor_tray', 'deck_lightened': 'deck', 'pallet_lightened': 'compute_pallet',
                'cheeks_lightened': 'cheek_left'}[check]
        sp = parts.get(name).sheet if parts.get(name) is not None else None
        return bool(sp and any(f.note.startswith('lightening') for f in sp.features))
    names = {i.name for i in (L or {}).get('items', [])}
    if check == 'fuse_board':
        return 'plate_fuse_board' in names
    if check == 'board_shunt':
        return 'plate_fuse_board' in names and 'plate_shunt' not in names
    if check == 'lidar_cable_1m':
        return LIDAR_CABLE_G <= 80.0
    if check == 'packs_sheet':
        import body_battery as bb
        return bb.PACK['mass_g'] <= 1460.0
    if check == 'harness_10awg':
        return HARNESS_G <= 340.0
    if check == 'shell_from_cad':
        return 'shell_side_l_front' in parts
    return False


def levers(parts=None, L=None) -> list:
    out = []
    for key, n, g, usd, stage, kind, what, check in LEVERS:
        taken = bool(check) and lever_taken(check, parts, L)
        out.append({'key': key, 'n': n, 'grams': g, 'cost_usd': usd, 'stage': stage, 'kind': kind, 'what': what,
                    'status': 'taken' if taken else 'open'})
    return out


def gate(led: dict) -> dict:
    """D71's gate on a P3 ledger: the ledger as it is, and with every scheduled lever not yet in the CAD taken (their
    grams as the plan states them), against the ceiling (BUDGET): the robot, each leg, the body and head."""
    open_g = sum(l['grams'] for l in led['levers'] if l['kind'] == 'scheduled' and l['status'] == 'open')
    proj = led['total_kg'] + open_g / 1000.0
    proj_bh = led['body_and_head_kg'] + open_g / 1000.0
    b = BUDGET
    legs_each = led['legs_kg'] / 2
    return {'ceiling_kg': b['robot_kg'], 'gap_kg': round(led['total_kg'] - b['robot_kg'], 3),
            'open_scheduled_g': open_g, 'with_scheduled_levers_kg': round(proj, 3),
            'body_and_head_with_levers_kg': round(proj_bh, 3), 'leg_each_kg': round(legs_each, 3),
            'pass': proj <= b['robot_kg'] + 1e-9 and proj_bh <= b['body_and_head_kg'] + 1e-9 and legs_each <= b['legs_kg_each'] + 1e-9,
            'on_call_next': [l['key'] for l in led['levers'] if l['kind'] == 'on call' and l['status'] == 'open'][:3],
            'margin_kg': round(b['robot_kg'] - proj, 3),
            'on_call_open_g': sum(l['grams'] for l in led['levers'] if l['kind'] == 'on call' and l['status'] == 'open'),
            'rule': f"the P3 ledger with every scheduled lever taken (the open ones at the plan's grams) under the {b['robot_kg']} kg "
                    f"ceiling, each leg under {b['legs_kg_each']} kg and the body and head under {b['body_and_head_kg']} kg (D71); "
                    'over it, the on-call levers go in order before the next order, each with the user\'s or the coordinator\'s word'}


def leg_rows(h_mm=300.0):
    """Each leg's parts at a stance (robot frame): printed parts from their solids (PA6-CF, 100 %), the machined output
    adapters and bought parts from exports/leg/leg.json and bom.json, at their posed envelopes' centres; whatever of
    leg.json's total (mass_g.total) is left over goes in at the leg's centre. Both legs; [(name, g, (x, y, z))]."""
    import body_frame as bf
    from cadagent.robot import solid_mass_properties
    fb = bp._fivebar()
    dens = json.loads((R / 'catalog/materials.json').read_text())['pa6-cf']['density_g_cm3']
    legs = bf.legs(h_mm)
    bom = {r['key']: r for r in json.loads((R / 'exports/leg/bom.json').read_text())['per_leg']}
    each = lambda k: bom[k]['mass_g_each'] if k in bom else 0.0
    bought = {'motor_front': each('robstride-rs-04'), 'motor_rear': each('robstride-rs-04'),
              'wheel_tyre': wheel_g() * D69_WHEEL['rotor_share'], 'wheel_hub': wheel_g() * (1 - D69_WHEEL['rotor_share']),
              'bearing_61812_front': each('bearing_61812'), 'bearing_61812_rear': each('bearing_61812'),
              'apex_61812': 2 * each('bearing_61812'), 'knee_6201_front_in': each('bearing_6201'), 'knee_6201_front_out': each('bearing_6201'),
              'knee_6201_rear_in': each('bearing_6201'), 'knee_6201_rear_out': each('bearing_6201'), 'knee_pin_front': each('knee_pin'),
              'knee_pin_rear': each('knee_pin'), 'stop_posts': 4 * each('stop_post'), 'apex_circlip': each('circlip_60'),
              'eye_sleeve_front': 2 * each('eye_sleeve'), 'eye_sleeve_rear': 2 * each('eye_sleeve'),
              'screws_lugs': 20 * each('screw_m4x20'), 'screws_links': 16 * each('screw_m5x40'), 'screws_wheel': 4 * each('screw_m6x30')}
    leg_json = json.loads((R / 'exports/leg/leg.json').read_text())['mass_g']
    machined = leg_json.get('machined_parts', {})
    rows = []
    for name, shape in legs.items():
        side, part = name.split('.', 1)
        v = shape.val() if hasattr(shape, 'val') else shape
        c = v.Center()
        if part in bought:
            g = bought[part]
        elif part.startswith('output_adapter') and 'output_adapter' in machined:
            g = machined['output_adapter']
            c = solid_mass_properties(v, 1.0, 1.0, part)
            c = tuple(x * 1000 for x in c.com)
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
                                                              'screw_m5x25', 'screw_m5x30', 'insert_m5') if k in bom}
    for side, sy in (('L', 1.0), ('R', -1.0)):
        rows.append((f'{side}.small_hardware', sum(rest.values()), (0.0, sy * (bp.y_off() + 30.0), 0.0)))
    extra = leg_stops_extra_g()[0]
    if wheel_is_d69_override():                           # D69's wheel in place of the BotWheel leg.json counts
        extra += wheel_g() - each('odrive-botwheel')
    for side, sy in (('L', 1.0), ('R', -1.0)):            # to leg.json's total (its own count of every part)
        placed = sum(g for n, g, _ in rows if n.startswith(side + '.'))
        left = leg_json['total'] + extra - placed
        if abs(left) > 1.0:
            rows.append((f'{side}.rest_of_leg_json', left, (0.0, sy * (bp.y_off() + 30.0), -100.0)))
    if WHEEL_CHANGE_G:                                    # a wheel study's change (issue #18), at each wheel's centre
        for side in ('L', 'R'):
            w = next(((n, g, c) for n, g, c in rows if n == f'{side}.wheel_hub'), None)
            rows.append((f'{side}.wheel_change', WHEEL_CHANGE_G, w[2] if w else (0.0, 0.0, -h_mm)))
    return rows


# The wheels are the leg's (exports/leg/leg.json: the ODrive BotWheel, 2.2 kg each). Issue #18 studies 8-10 in air-tyre hub
# motors (+0.8 to +2.3 kg a wheel): set this (or GYROPUP_WHEEL_CHANGE_G) to a candidate's change per wheel to see the
# ledger and the gate with it, before anything is redesigned round it.
WHEEL_CHANGE_G = float(os.environ.get('GYROPUP_WHEEL_CHANGE_G', 0.0))


SHELL_PREFIXES = ('shell_', 'ear_bracket', 'receiver_bay', 'd435_cradle', 'fan_duct', 'eyes_clip')    # the shell group's CAD


def frame_rows(parts, stage='P3'):
    """[(name, g, com, group)] of the made parts on the robot at a stage (frame, tub; the shell's own in 'shell')."""
    import body_frame as bf
    from cadagent.robot import solid_mass_properties
    mats = json.loads((R / 'catalog/materials.json').read_text())
    rows = []
    for n, p in parts.items():
        if not bf.on_robot(p, stage):
            continue
        v = p.shape.val() if hasattr(p.shape, 'val') else p.shape
        if p.kind == 'sheet':
            dens = next(st['density'] for st in bp.STOCK.values() if st['material'] == p.material)
            b = solid_mass_properties(v, dens, 1.0, n)
        elif p.kind == 'printed':
            b = solid_mass_properties(v, mats[p.material]['density_g_cm3'], 1.0, n)
        else:
            continue
        group = 'shell' if n.startswith(SHELL_PREFIXES) else 'frame'
        rows.append((f'{group}.{n}', b.mass * 1000, tuple(x * 1000 for x in b.com), group))
    return rows


def ledger(L=None, parts=None, stage='P3'):
    """The robot's mass and centre (robot frame, standing at 300 mm) by group, with every row's basis."""
    import body_frame as bf
    L = L or layout()
    parts = parts or bf.all_parts(L['mounts'])
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
    for n, g, c, grp in frame_rows(parts, stage):
        add(grp, n, g, c, 'CAD (sheet and printed solids)' if grp == 'frame' else 'CAD (cad/body_shell.py, printed)')
    for it in L['items']:
        if it.keepout or not it.mass_g or not keep(it):
            continue
        add(it.group, it.name, it.mass_g, it.centre, it.basis)
    zt = bp.z_tray_top()
    add('frame', 'hardware', HARDWARE_G, (0.0, 0.0, 40.0), 'estimate')
    import body_battery as bb
    mats = json.loads((R / 'catalog/materials.json').read_text())
    dv = sum((b[1] - b[0]) * (b[3] - b[2]) * (b[5] - b[4]) for p in bb.pad_boxes() for b in bb.pad_retention_boxes(p)) / 1000.0
    add('frame', 'bay_pads_solid_lips', dv * (mats['tpu95']['density_g_cm3'] - mats[bb.PAD['material']]['density_g_cm3']),
        (0.0, 0.0, bb.geometry()['z_floor']), 'CAD: the pads\' webs and lips are solid TPU, not lattice (#26)')
    add('power', 'harness', HARNESS_G, (60.0, 0.0, zt + 20.0), 'estimate (docs/body-wiring.md)')
    for side, sy in (('l', 1.0), ('r', -1.0)):          # D69: each wheel's DTP04-4P/DTP06-4S (phases) and DT04-6P/DT06-6S (halls,
        add('power', f'wheel_connectors_{side}', WHEEL_CONNECTORS_G, (-30.0, sy * 70.0, zt),   # NTC) at the cheek where the wheel lead enters
            'estimate (two Deutsch pairs with contacts and wedgelocks, at the belly box\'s side gland)')
    if stage == 'P3':
        for n, g, c, b in shell_items(parts):
            add('shell', n, g, c, b)
    m = sum(r['mass_g'] for r in rows)
    com = [sum(r['mass_g'] * r['com_mm'][k] for r in rows) / m for k in range(3)]
    legs_g = groups.get('legs', 0.0)
    out = {'stage': stage, 'total_kg': round(m / 1000, 2), 'com_mm': [round(v, 1) for v in com], 'groups_kg': {k: round(v / 1000, 3) for k, v in groups.items()},
           'legs_kg': round(legs_g / 1000, 2), 'body_and_head_kg': round((m - legs_g) / 1000, 2), 'rows': rows,
           'budget': dict(BUDGET), 'leg_extra': leg_stops_extra_g()[1], 'levers': levers(parts, L)}
    if stage == 'P3':
        out['gate'] = gate(out)
    return out


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


def shell_items(parts):
    """The P3 shell's ledger rows: its bought parts (catalogue masses) where cad/body_shell.py puts them; the panels,
    brackets and tub come from the CAD (frame_rows), so the estimates here are only for what has no CAD."""
    import body_shell as bs3
    if 'shell_side_l_front' not in parts:
        return SHELL_ITEMS
    c = lambda s: tuple(round(v, 1) for v in bs3._v(s).Center().toTuple())
    out = [('depth_camera_front', 75.0, c(bs3.d435(True)), 'catalogue (D435 75 g), cad/body_shell.py'),
           ('depth_camera_rear', 75.0, c(bs3.d435(False)), 'catalogue (D435 75 g), cad/body_shell.py'),
           ('eyes', 11.0, c(bs3.eyes_board()), 'catalogue (DualEye 11 g), cad/body_shell.py'),
           ('eye_controller', 8.0, (150.0, 0.0, 170.0), 'catalogue (QT Py ESP32-S3)'),
           ('ear_pod_l', 154.0, c(bs3.ear_pod('l')), 'catalogue (SSC1 154 g each), cad/body_shell.py'),
           ('ear_pod_r', 154.0, c(bs3.ear_pod('r')), 'catalogue (SSC1 154 g each), cad/body_shell.py'),
           ('shell_hardware', 60.0, (0.0, 0.0, 150.0), 'estimate (M3/M5 screws, nuts, inserts of the shell and tub)')]
    return out


def write_ledger():
    """exports/body/mass.json (P1 and P3) without the whole build: the layout, every part and the ledger."""
    import body_frame as bf
    L = layout()
    parts = bf.all_parts(L['mounts'])
    led = {st: ledger(L, parts, stage=st) for st in ('P1', 'P3')}
    (OUT / 'mass.json').write_text(json.dumps(led, indent=1) + '\n')
    return led


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', action='store_true', help='write exports/body/mass.json (else: the overlap check only)')
    a = ap.parse_args()
    L = layout()
    bad = check(L['items'], frame_boxes())
    print(f"{len(L['items'])} items, {len(bad)} problems")
    for b in bad:
        print('  ', b)
    if a.ledger:
        led = write_ledger()
        g = led['P3']['gate']
        print(f"P1 {led['P1']['total_kg']} kg, P3 {led['P3']['total_kg']} kg (ceiling {g['ceiling_kg']}, gap {g['gap_kg']:+.3f}); "
              f"with the open scheduled levers {g['with_scheduled_levers_kg']} kg: {'pass' if g['pass'] else 'OVER'}")
        for l in led['P3']['levers']:
            print(f"   {l['n']:2} {l['key']:15} {l['grams']:+5} g  {l['stage']} {l['kind']:9} {l['status']}")
