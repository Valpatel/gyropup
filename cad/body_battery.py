"""The battery (milestone M5): a 13S2P Li-ion brick in the belly, and the bay that holds it. Robot frame (mm).

Why the belly, not a cassette on the floor tray (docs/body-plan.md 1.2 had a 95 x 160 cassette behind a right-side
door): with the J501 carrier at the rear of the tray (its fan has to sit under the turret's riser) the tray's front
third cannot also take the cassette, the 24 V converter, the wheel VESCs and the lidar's interface box; T3 measured it
(cad/body_layout.py). In the belly the battery is 2.0 kg at z ~ -110 instead of +130, which lowers the robot's centre
by ~15 mm, and it sits right over the dock's charge pads (D18).

The brick (the standard e-bike / e-board build: no cassette to print, nothing that does not fit the P1S bed):
  26 cells lying, axes across the robot (y), 13 parallel pairs side by side along x, two layers; printed PETG end combs
  hold the cell ends; 0.2 x 8 mm pure nickel joins each pair to the next on alternate faces; the BMS (Daly K-series 13S
  100 A, 98 x 65 x 14, tabs to 123) lies on top; fish paper rings, barley paper, Kapton, 2 mm EVA foam at the ends,
  then 0.2 mm PVC heat shrink. B+ and the BMS's P- leave the front end on 150 mm of 10 AWG to an XT90-S, the BMS's
  UART and KEY leads on a 6-pin JST-XH beside it; a nylon strap to pull it.
The bay: the belly plate on top, a printed PA6-CF tub in two halves under it (the bed is 256 mm), a hinged door at the
front with a quarter-turn latch, the charge port on the rear cap; the tub's floor carries replaceable TPU skids.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq

import body_params as bp

# Molicel datasheets (molicel.com product pages and datasheets, read 2026-10-27; max dimensions and masses)
CELLS = {
    'P30B': {'name': 'Molicel INR-18650-P30B', 'd': 18.6, 'L': 65.2, 'mass_g': 47.0, 'ah': 3.0, 'a_cont': 36.0, 'a_charge': 3.0,
             'dcir_mohm': 15.0, 'source': 'molicel.com/product/inr-18650-p30b (3.0 Ah, 36 A, 18.6 x 65.2 max, 47 g max); DCIR est'},
    'P50B': {'name': 'Molicel INR-21700-P50B', 'd': 21.55, 'L': 70.15, 'mass_g': 71.0, 'ah': 5.0, 'a_cont': 60.0, 'a_charge': 25.0,
             'dcir_mohm': 12.8, 'source': 'molicel.com/product/inr-21700-p50b (5.0 Ah, 60 A at an 80 C cut-off, 21.55 x 70.15, 71 g max, DCIR 12.8 mOhm)'},
    'P45B': {'name': 'Molicel INR-21700-P45B', 'd': 21.6, 'L': 70.2, 'mass_g': 69.0, 'ah': 4.5, 'a_cont': 45.0, 'a_charge': 13.5,
             'dcir_mohm': 15.0, 'source': 'molicel.com/product/inr-21700-p45b'},
}
BMS = {'name': 'Daly K-series smart BMS, Li-ion 13S 48 V 100 A, Bluetooth + UART (SKU G08-RK-89704)', 'body': (98.0, 65.0, 14.0),
       'tabs_l': 123.0, 'mass_g': 110.0, 'mass_basis': 'estimate (not published; a 98 x 65 x 14 board with its FETs and potting)',
       'switch': 'negative side (B- / P-), common port', 'balance_ma': 100}
SERIES, PARALLEL = 13, 2
CELL = 'P30B'                    # 13S2P of 18650 P30B: 1.54 kg against the plan's P50B 2.17 kg (the mass ledger is over
                                 # budget and the legs' power-off load grows with the mass); 256 Wh at 4.10 V/cell, 72 A
                                 # continuous; the P50B brick (426 Wh) needs a 6 mm deeper bay
PITCH_GAP = 0.9                  # printed comb web between cells
WRAP = 2.0                       # fish paper, foam, shrink: each side
STRIP = (0.2, 8.0)               # nickel (thickness, width)


@dataclass
class Brick:
    cell: str
    box: tuple                   # (x0, x1, y0, y1, z0, z1) in the robot frame
    mass_g: float
    energy_wh: float             # nominal, 4.2 V/cell
    energy_wh_410: float         # at the 4.10 V/cell charge rule
    capacity_ah: float
    cont_a: float
    sag_v_80a: float
    shapes: dict


def brick(cell=CELL, x_front=None, z_top=None) -> Brick:
    """The 13S2P brick, front end at x_front, its top just under the belly bay's roof."""
    c = CELLS[cell]
    p = c['d'] + PITCH_GAP
    nx, nz = SERIES, PARALLEL
    lx = nx * p + 2 * 4.0                       # the combs' end walls
    ly = c['L'] + 2 * (STRIP[0] + 3.0)          # cell length + nickel + comb lips
    lz = nz * p + BMS['body'][2] + 3.0          # two layers + the BMS on a 1 mm insulator + wiring room
    lx, ly, lz = lx + 2 * WRAP, ly + 2 * WRAP, lz + 2 * WRAP
    x1 = x_front if x_front is not None else BAY_X[0] + BAY_WALL + 0.5 + (SERIES * (c['d'] + PITCH_GAP) + 8.0 + 2 * WRAP)
    # the brick sits at the bay's rear; the front of the bay (behind the door) is the connector space: the XT90 joint
    # to the robot's lead (down through the belly slot) and the charge port's Y-splice
    z1 = z_top if z_top is not None else bay_roof() - 1.0
    box = (x1 - lx, x1, -ly / 2, ly / 2, z1 - lz, z1)
    cells_g = SERIES * PARALLEL * c['mass_g']
    extras = BMS['mass_g'] + 45.0 + 35.0 + 70.0 + 60.0   # BMS, nickel, combs, leads + XT90-S + balance wires, wrap + foam
    ah = PARALLEL * c['ah']
    e42 = SERIES * 3.6 * ah
    e410 = e42 * 0.91                                       # ~9 % less stored energy at 4.10 V/cell (rule of thumb)
    r_pack = SERIES * c['dcir_mohm'] / PARALLEL / 1000 + 0.015    # cells + nickel and leads (est)
    shapes = {}
    x0 = box[0] + WRAP + 4.0
    zc0 = box[4] + WRAP + 1.0
    cells = None
    for i in range(nx):
        for k in range(nz):
            cx, cz = x0 + p / 2 + i * p, zc0 + p / 2 + k * p
            s = cq.Workplane('XZ', origin=(0, c['L'] / 2, 0)).center(cx, cz).circle(c['d'] / 2).extrude(c['L'])
            cells = s if cells is None else cells.union(s)
    shapes['cells'] = cells
    bx, by, bz = BMS['body']
    shapes['bms'] = cq.Workplane('XY').box(bx, by, bz).translate(((box[0] + box[1]) / 2, 0, zc0 + nz * p + 1.0 + bz / 2))
    return Brick(cell, box, cells_g + extras, e42, e410, ah * 0.92, PARALLEL * c['a_cont'], 80.0 * r_pack, shapes)


# ------------------------------------------------------------------------------------------- the bay

BAY_WALL = 3.0                   # printed PA6-CF tub walls
BAY_FLOOR = 3.0
DOOR_T = 4.0
BAY_X = (-150.0, 158.0)
SKID_T = 3.0                     # TPU 95A skid strips under the floor


def bay_roof():
    """The underside of the belly plate: the bay's roof."""
    return -bp.z_spine_top() - bp.STOCK[bp.BELLY]['t']


def bay(b: Brick):
    """The tub round the brick: inside it 2 mm all round, its walls inside |y| <= BELLY_HALF_Y (the knees' 25 mm)."""
    x0, x1, y0, y1, z0, z1 = b.box
    zr = bay_roof()
    iz0 = z0 - 2.0
    out = {'inner': (BAY_X[0] + BAY_WALL, BAY_X[1] - DOOR_T, y0 - 2.0, y1 + 2.0, iz0, zr),
           'outer': (BAY_X[0], BAY_X[1], y0 - 2.0 - BAY_WALL, y1 + 2.0 + BAY_WALL, iz0 - BAY_FLOOR - SKID_T, zr)}
    out['half_y'] = y1 + 2.0 + BAY_WALL
    out['bottom_z'] = out['outer'][4]
    return out


CONNECTOR_SPACE = 30.0           # behind the door: the XT90-S pair lying across y, the charge port's leads


def bay_parts(b: Brick):
    """The printed bay (PETG, 3 mm walls, impact-tough), robot frame: a rear and a front half (each fits the bed),
    each a tub (floor + two walls) with outward flanges screwed up into the belly plate's PEM nuts, and the door with
    the charge port (XT60E-F: the robot's side is the female, no live pins) and two thumbscrews."""
    B = bay(b)
    x0, x1, y0, y1, z0, z1 = B['outer']
    wall, floor = BAY_WALL, BAY_FLOOR
    zf = z0 + SKID_T                                   # the floor's underside (the skids under it)
    flange_w = 12.0
    seam = (x0 + x1 - DOOR_T) / 2
    parts = {}
    for name, (a, c) in (('bay_rear', (x0, seam)), ('bay_front', (seam, x1 - DOOR_T))):
        tub = cq.Workplane('XY').box(c - a, y1 - y0, z1 - zf, centered=False).translate((a, y0, zf))
        inner = cq.Workplane('XY').box(c - a + 2, y1 - y0 - 2 * wall, z1 - zf - floor + 1, centered=False).translate((a - 1, y0 + wall, zf + floor))
        tub = tub.cut(inner)
        for sy in (1, -1):                              # the flanges under the belly plate
            yy = (y1, y1 + flange_w) if sy > 0 else (y0 - flange_w, y0)
            tub = tub.union(cq.Workplane('XY').box(c - a, flange_w, 4.0, centered=False).translate((a, yy[0], z1 - 4.0)))
            for x in (-135.0, -80.0, -25.0, 30.0, 85.0, 140.0):
                if a + 6 < x < c - 6:
                    tub = tub.cut(cq.Workplane('XY').workplane(offset=z1 - 5).center(x, sy * (B['half_y'] + 6.0)).circle(2.75).extrude(6))
        if name == 'bay_rear':                          # the rear wall
            tub = tub.union(cq.Workplane('XY').box(wall, y1 - y0, z1 - zf, centered=False).translate((a, y0, zf)))
        parts[name] = tub
    door = cq.Workplane('XY').box(DOOR_T, y1 - y0 + 2 * flange_w, z1 - zf, centered=False).translate((x1 - DOOR_T, y0 - flange_w, zf))
    door = door.cut(cq.Workplane('YZ', origin=(x1 - DOOR_T - 1, 0, 0)).center(0, (zf + z1) / 2 - 8).rect(16.6, 8.6).extrude(DOOR_T + 2))   # XT60E-F
    for sy in (1, -1):
        door = door.cut(cq.Workplane('YZ', origin=(x1 - DOOR_T - 1, 0, 0)).center(sy * (y1 + flange_w / 2), (zf + z1) / 2).circle(2.2).extrude(DOOR_T + 2))
    parts['bay_door'] = door
    half = (x1 - x0 - 12) / 2                           # TPU skids under the floor: two per side (the bed is 256 mm)
    for k, sy in enumerate((1, -1)):
        for j in range(2):
            parts[f'bay_skid_{2 * k + j + 1}'] = cq.Workplane('XY').box(half, 14.0, SKID_T, centered=False).translate(
                (x0 + 5 + j * (half + 2), (y1 - 18.0) if sy > 0 else (y0 + 4.0), z0))
    return parts


def summary(cell=CELL):
    b = brick(cell)
    B = bay(b)
    fb = bp._fivebar()
    wheel_r = 171.3 / 2
    clear_min = bp.LEG_RANGE[0] + wheel_r + B['bottom_z']
    return {'cell': CELLS[cell]['name'], 'config': f'{SERIES}S{PARALLEL}P', 'brick_mm': [round(b.box[1] - b.box[0], 1), round(b.box[3] - b.box[2], 1), round(b.box[5] - b.box[4], 1)],
            'mass_g': round(b.mass_g), 'capacity_ah': round(b.capacity_ah, 2), 'energy_wh_42': round(b.energy_wh), 'energy_wh_410': round(b.energy_wh_410),
            'continuous_a': b.cont_a, 'sag_at_80a_v': round(b.sag_v_80a, 1), 'bay_half_y': round(B['half_y'], 1), 'bay_bottom_z': round(B['bottom_z'], 1),
            'ground_clearance_at_stops_mm': round(clear_min, 1), 'ground_clearance_at_130_mm': round(130 + wheel_r + B['bottom_z'], 1),
            'knee_gap_mm': round(83.0 - B['half_y'], 1)}


if __name__ == '__main__':
    import json
    for c in ('P50B', 'P30B'):
        print(c, json.dumps(summary(c)))
