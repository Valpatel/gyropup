"""The battery (milestone M5, D65): two DeWalt DCB609 FLEXVOLT packs in 20 V mode, in series, in a bay under the belly
plate. Robot frame (mm).

D65 (the user's choice, 2026-10-27) replaces D43's 13S2P brick and its Daly BMS: each pack (5S3P in 20 V mode, 9.0 Ah)
slides onto an off-the-shelf DeWalt 20 V rail adapter (Terrafirma Technology, 10 AWG leads, 30 A stated, no fuse or
switch), the two in series: 10S3P, 36 V nominal, about 41 V full, 30 V empty (3.0 V a cell: the robot enforces the
cut-off and a current limit itself; the packs talk to nothing). Charging is the user's DeWalt chargers: the packs
come out, so the robot has no charge port and no dock contacts (D64's dock is overtaken).

Why the belly, again (the alternatives in docs/body-sections.md 1): a pack is 138 x 87 x 97 mm and nothing in the body
above the belly plate has 122 mm of height free over a 138 x 87 footprint (the floor tray carries the J501 and the
power plate; the deck has 120 mm under it and the turret over it); on the front and rear faces the packs would grow the
body 244 mm, sit in the lidar's lowest beam and the eyes', and hang where a child grabs them. In the belly they are low
(the robot's centre falls), boxed, and between the legs, at a price: the bay is 132 mm deep, so the robot sits on its
skids when its legs are under 139 mm (it never runs under 150: sim/robot_v2.py H_RANGE).

The bay (one design from P1 on; the 13S2P's printed P0-P2 bay and P3 tub are gone):
  - two printed PA6-CF adapter plates screwed up into the belly plate's PEM nuts (4 x M4 each); each adapter screws to
    its plate (M3 into heat-set inserts placed from the adapter's own holes on arrival: their pattern is not published)
  - the packs hang from the adapters as from a tool, their rails along x: the front pack slides out forwards, the rear
    one backwards, each through its end door; a 30 mm space between them holds the adapters' leads, the series link's
    XT90 pair and the two leads' way up through the belly's slot into the spine's gap
  - a SendCutSend 5052 0.063 floor (a U, its 20 mm flanges up) and two flat side plates with lightening windows, the
    sides screwed to the floor's flange nuts and to two printed rails, the rails screwed up into the belly's nuts
  - two PETG end doors on two knurled M3 thumbscrews each (tool-free), four TPU 95A gyroid crush pads on VHB tape under the floor
    (issue #19): the robot sits on them
"""
from __future__ import annotations

import functools
import math

import cadquery as cq

import body_params as bp

# The pack (the DeWalt sheet for its EU twin DCB547-XJ: 138 x 87 x 97 mm, 1.46 kg; Ace Tool lists the DCB609 at 3.2 lb.
# DeWalt publishes no US outline: measure one pack before the bay is printed). The rail runs along L on the top face.
PACK = {'name': 'DeWalt DCB609 FLEXVOLT 20V/60V MAX 9.0 Ah (20 V mode: 5S3P)', 'L': 138.0, 'W': 87.0, 'H': 97.0, 'mass_g': 1565.0,
        'wh_rated': 180.0, 'ah': 9.0, 'series': 5,
        'source': 'DeWalt DCB547-XJ datasheet (138 x 87 x 97 mm incl. the rail tower); DeWalt US 3.45 lb = 1565 g (the conservative of 1.46-1.57 kg): weigh one'}
# The rail adapter (Terrafirma Technology "4pack 10AWG Adapter for DeWALT 20V", Amazon B07HYJ628S, $64.00 the four, 30 A
# stated). Its outline is not published: this envelope is a guess to be measured on arrival (the bay's plates are printed).
ADAPTER = {'L': 100.0, 'W': 72.0, 'H': 25.0, 'mass_g': 70.0, 'basis': 'envelope estimate: Terrafirma publishes no drawing'}
SERIES = 2 * PACK['series']                  # 10S
V_FULL, V_NOM, V_EMPTY = 4.1 * SERIES, 3.6 * SERIES, 3.0 * SERIES
R_PACK_OHM = 0.10                            # the leg rig's figure for the pair with its leads (rig/run.py, D65)

PLATE_T = 4.0                                # the printed adapter plates under the belly
GAP_MID = 30.0                               # between the packs: the leads and the series link
DOOR_T = 4.0
END_CLEAR = 2.0                              # a pack's end to its door
SIDE_CLEAR = 4.5                             # a pack's side to the floor's flange: the flange nuts' bodies (3.2) and the M3 x 6 tips
FLOOR_CLEAR = 1.0                            # under a pack
TUB_STOCK = '5052-0.063'
TUB_FLANGE = 20.0
# Issue #19: four crush pads under the floor in place of the 3 mm skids. D69's 10 in wheels lift the body 41 mm at every
# leg length, so the old skids would never reach the floor (they touched under a 98 mm leg; the leg folds to 101.5 mm on its
# stops): the pads reach down instead. Each pad is a printed TPU 95A HF gyroid block (the lattice's density, not the shore
# hardness, sets its stiffness: the stock P1S filament) on VHB tape, and in sim/robot_v2.py a body
# on a slide joint: a spring (k), a damper (c), a stroke, then the densified lattice as a stiff stop. The robot sits on
# them (D55, D69's parking brake). Sizing: sim/bay_pad_study.py, exports/body/bay-pad-study.json.
#   h       its free height under the floor: the floor at 65.4 mm over the ground at the lowest controlled leg (160 mm)
#           less h keeps D69's 40 mm (puddles, the rolling step) under the pads; they touch the ground under a 119.7 mm leg
#   stroke  0.6 h: a gyroid lattice densifies past about 60 % strain (the coupon test checks it)
#   k, c    the pair of numbers the study sized, per pad (N/mm, N s/m)
#   unload_ratio  the lattice's hysteresis: unloading, its spring gives back this share of k x (an elastomer lattice
#           dissipates about half of a large compression in its first cycles; the coupon's rebound height measures it)
PAD = {'h': 25.0, 'w': 30.0, 'stroke': 15.0, 'k_n_per_mm': 80.0, 'c_ns_per_m': 250.0, 'unload_ratio': 0.5, 'material': 'tpu95-gyroid',
       'wheel_r': 127.0, 'basis': 'issue #19: sized by sim/bay_pad_study.py at the D69 mass; coupon drop test to confirm k and c'}
SKID_T = PAD['h']
RAIL_W, RAIL_H = 8.0, 10.0                   # the printed rails at the top, inside the side plates
THUMB = {'thread': 'M3', 'length': 10.0}     # the doors' knurled thumbscrews into the rails' end inserts
LEADS_SLOT = (-30.0, 24.0)                   # the belly's slot for the two leads (x centre, length): between the standoffs at x -72 and -10


def z_belly():
    """The belly plate's underside: the bay's roof."""
    return -bp.z_spine_top() - bp.STOCK[bp.BELLY]['t']


@functools.lru_cache(maxsize=1)
def geometry():
    """The bay's numbers (robot frame)."""
    t = bp.STOCK[TUB_STOCK]['t']
    zr = z_belly()
    z_adapter = (zr - PLATE_T - ADAPTER['H'], zr - PLATE_T)
    z_pack = (z_adapter[0] - PACK['H'], z_adapter[0])
    z_floor_top = z_pack[0] - FLOOR_CLEAR
    side_in = PACK['W'] / 2 + SIDE_CLEAR + t                  # the floor's flanges sit inside the side plates
    side_out = side_in + t
    inner_x = PACK['L'] * 2 + GAP_MID + 2 * END_CLEAR
    x_in = (-inner_x / 2, inner_x / 2)
    x_out = (x_in[0] - DOOR_T, x_in[1] + DOOR_T)
    packs = {'front': (GAP_MID / 2, GAP_MID / 2 + PACK['L']), 'rear': (-GAP_MID / 2 - PACK['L'], -GAP_MID / 2)}
    adapters = {k: ((a + b) / 2 - ADAPTER['L'] / 2 + (1 if k == 'front' else -1) * (PACK['L'] - ADAPTER['L']) / 2,
                    (a + b) / 2 + ADAPTER['L'] / 2 + (1 if k == 'front' else -1) * (PACK['L'] - ADAPTER['L']) / 2)
                for k, (a, b) in packs.items()}             # each adapter at its door's end: the latch and release face the door
    return {'t': t, 'z_belly': zr, 'z_adapter': z_adapter, 'z_pack': z_pack, 'z_floor_top': z_floor_top, 'z_floor': z_floor_top - t,
            'z_bottom': z_floor_top - t - SKID_T, 'side_in': side_in, 'side_out': side_out, 'flange_in': side_in - t,
            'x_in': x_in, 'x_out': x_out, 'packs': packs, 'adapters': adapters,
            'rail_y': (side_in - RAIL_W, side_in),
            'rail_z': (zr - RAIL_H, zr), 'half_y': side_out}


def pack_boxes():
    g = geometry()
    return {k: (a, b, -PACK['W'] / 2, PACK['W'] / 2, *g['z_pack']) for k, (a, b) in g['packs'].items()}


def adapter_boxes():
    g = geometry()
    return {k: (a, b, -ADAPTER['W'] / 2, ADAPTER['W'] / 2, *g['z_adapter']) for k, (a, b) in g['adapters'].items()}


def summary():
    g = geometry()
    wheel_r = PAD['wheel_r']                                 # D69's 10 in tyre
    sit = -g['z_bottom'] - wheel_r                           # the leg length at which the pads touch the floor
    return {'pack': PACK['name'], 'config': f'{SERIES}S3P (two packs in series)', 'v_full': round(V_FULL, 1), 'v_nominal': V_NOM, 'v_empty': V_EMPTY,
            'wh_rated': 2 * PACK['wh_rated'], 'packs_kg': round(2 * PACK['mass_g'] / 1000, 2),
            'bay_mm': [round(g['x_out'][1] - g['x_out'][0], 1), round(2 * g['side_out'], 1), round(g['z_belly'] - g['z_bottom'], 1)],
            'bay_bottom_z': round(g['z_bottom'], 1), 'sits_on_skids_below_leg_mm': round(sit, 1),
            'clearance_at_150_mm': round(150 + wheel_r + g['z_bottom'], 1), 'clearance_at_160_mm': round(160 + wheel_r + g['z_bottom'], 1),
            'clearance_at_300_mm': round(300 + wheel_r + g['z_bottom'], 1), 'pad': {k: v for k, v in PAD.items() if k != 'basis'},
            'knee_gap_mm': round(83.0 - g['side_out'], 1), 'adapter': ADAPTER['basis']}


# ------------------------------------------------------------------------------------------- the parts

def _box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def _cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def _cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


# The belly's nuts for the bay: S-M4-0, their bodies on the belly's top, so only beyond the cheeks' ends (|x| > 92: inside
# them the cheeks' lower flanges lie on the belly out to |y| 45.5)
BELLY_NUT_X = (-150.0, -102.0, 102.0, 150.0)


def plate_holes(k):
    """An adapter plate's four M4 screws up into the belly's PEM nuts (robot x, y): at its outer end, beyond the cheeks."""
    sx = 1.0 if k == 'front' else -1.0
    return [(sx * x, y) for x in (102.0, 150.0) for y in (-ADAPTER['W'] / 2 + 6.0, ADAPTER['W'] / 2 - 6.0)]


def rail_holes():
    """The rails' M4 screws up into the belly's PEM nuts (robot x, |y|): four each, beyond the cheeks' ends."""
    g = geometry()
    yc = (g['rail_y'][0] + g['rail_y'][1]) / 2
    return [(x, yc) for x in BELLY_NUT_X]


SIDE_SCREWS_X = (-125.0, -60.0, 0.0, 60.0, 125.0)            # the side plates into the floor's flange nuts and the rails' inserts


def adapter_plate(k):
    """A printed PA6-CF plate under the belly that carries one adapter: four M4 counterbored from below up into the
    belly's nuts (the heads under the adapter's footprint's edges), the adapter's own screws into inserts set on arrival."""
    g = geometry()
    a, b = g['adapters'][k]
    a, b = (min(a, 96.0), min(max(b, 154.5), g['x_in'][1] - 0.5)) if k == 'front' else (max(min(a, -154.5), g['x_in'][0] + 0.5), max(b, -96.0))
    zr = g['z_belly']
    w = ADAPTER['W'] / 2
    s = _box(a, b, -w, w, zr - PLATE_T, zr)
    for x, y in plate_holes(k):
        s = s.cut(_cyl_z(2.25, zr - PLATE_T - 1, zr + 1, x, y)).cut(_cyl_z(4.0, zr - PLATE_T - 1, zr - PLATE_T + 1.5, x, y))
    return s


def rail(side):
    """A rail (PA6-CF), inside the side plate at the top: up into the belly's nuts (M4, heads sunk), the side plate's
    top row into its inserts (M3), the doors' thumbscrews into inserts in its ends."""
    g = geometry()
    sy = 1.0 if side == 'l' else -1.0
    y0, y1 = sorted((sy * g['rail_y'][0], sy * g['rail_y'][1]))
    z0, z1 = g['rail_z']
    x0, x1 = g['x_in']
    r = _box(x0, x1, y0, y1, z0, z1)
    yc = (y0 + y1) / 2
    for x, _ in rail_holes():                                 # M4 x 16 socket heads under the rail (19 mm over the packs)
        r = r.cut(_cyl_z(2.25, z0 - 1, z1 + 1, x, yc))
    zc = (z0 + z1) / 2
    for x in SIDE_SCREWS_X:                                   # M3 inserts from the outer face (the side plate's top row)
        yo = sy * g['side_in']
        r = r.cut(_cyl_y(2.0, *sorted((yo, yo - sy * 6.5)), x, zc))
    for xe, d in ((x0, 1), (x1, -1)):                          # the doors' thumbscrews: M3 inserts in the ends
        r = r.cut(_cyl_x(2.0, *sorted((xe, xe + d * 7.5)), yc, zc))
    return r


def floor_part():
    """The bay's floor (SendCutSend 5052-H32 0.063 in): a U with 20 mm flanges up, PEM S-M3-0 in the flanges for the side
    plates' bottom row, the skids' holes."""
    import body_sheet as bs
    g = geometry()
    L = g['x_in'][1] - g['x_in'][0]
    W = 2 * g['side_in'] - 0.1                                   # its flanges inside the side plates
    feats = []
    for x in SIDE_SCREWS_X:
        for e in ('S', 'N'):
            feats.append(bs.Feature('pem', e, (x - g['x_in'][0], 12.0), bp.PEM['S-M3-0']['H'], spec='S-M3-0', note='bay side plate'))
    feats.append(bs.Feature('slot', 'base', (L / 2, W / 2), size=(24.0, 40.0, 4.0), note='drain and the leads\' inspection'))
    return bs.SheetPart('bay_floor', TUB_STOCK, L, W, flanges=[bs.Flange('S', TUB_FLANGE), bs.Flange('N', TUB_FLANGE)], features=feats,
                        note='the battery bay\'s floor: flanges up; PEM S-M3-0 pressed from the inside')


def side_part():
    """A bay side plate (SendCutSend 5052-H32 0.063 in, flat; one part for both sides), three lightening windows."""
    import body_sheet as bs
    g = geometry()
    L = g['x_in'][1] - g['x_in'][0]
    H = g['z_belly'] - g['z_floor']
    feats = []
    for x in SIDE_SCREWS_X:
        feats.append(bs.Feature('hole', 'base', (x - g['x_in'][0], 12.0), 3.4, note='M3 x 6 into the floor flange\'s nut'))
        feats.append(bs.Feature('hole', 'base', (x - g['x_in'][0], H - RAIL_H / 2), 3.4, note='M3 x 6 into the rail\'s insert'))
    zw0, zw1 = TUB_FLANGE + 6.0, H - RAIL_H - 6.0
    for xa, xb in ((-115.0, -70.0), (-50.0, -10.0), (10.0, 50.0), (70.0, 115.0)):
        feats.append(bs.Feature('slot', 'base', (((xa + xb) / 2) - g['x_in'][0], (zw0 + zw1) / 2), size=(xb - xa, zw1 - zw0, 6.0),
                                note='lightening window'))
    return bs.SheetPart('bay_side', TUB_STOCK, L, H, features=feats, qty=2, note='flat; the two sides are the same part')


def place_floor(shape):
    g = geometry()
    W = 2 * g['side_in'] - 0.1
    return shape.translate((g['x_in'][0], -W / 2, g['z_floor']))


def place_side(shape, side):
    g = geometry()
    s = shape.rotate((0, 0, 0), (1, 0, 0), 90).translate((g['x_in'][0], 0, g['z_floor']))     # (u, v, w) -> (x, -w, z)
    return s.translate((0, g['side_out'], 0)) if side == 'l' else s.mirror('XZ').translate((0, -g['side_out'], 0))


def door(front):
    """An end door (PETG, 4 mm): the pack slides out behind it; two knurled M3 thumbscrews into the rails' ends."""
    g = geometry()
    x0, x1 = (g['x_in'][1], g['x_out'][1]) if front else (g['x_out'][0], g['x_in'][0])
    w = g['side_out']
    d = _box(x0, x1, -w, w, g['z_floor'], g['z_belly'] - 0.5).edges('|X').fillet(3.0)
    zc = sum(g['rail_z']) / 2
    yc = (g['rail_y'][0] + g['rail_y'][1]) / 2
    for y in (yc, -yc):
        d = d.cut(_cyl_x(1.7, x0 - 1, x1 + 1, y, zc))
    return d


def pad_boxes():
    """The four crush pads' boxes (x0, x1, y0, y1, z0, z1), robot frame: under the floor's long edges, front and rear."""
    g = geometry()
    W = 2 * g['side_in'] - 0.1
    half = (g['x_in'][1] - g['x_in'][0] - 12) / 2
    out = []
    for sy in (1.0, -1.0):
        for j in range(2):
            x0 = g['x_in'][0] + 5 + j * (half + 2)
            y0, y1 = sorted((sy * (W / 2 - 1.0), sy * (W / 2 - 1.0 - PAD['w'])))
            out.append((x0, x0 + half, y0, y1, g['z_bottom'], g['z_floor']))
    return out


def skids():
    """The crush pads as solids (the names stay bay_skid_N: the joints and the views know them by it)."""
    return [_box(*b) for b in pad_boxes()]


def bay_parts() -> dict:
    """Every part of the bay as body_frame.Part (robot frame), from P1."""
    import body_frame as bf
    Part = bf.Part
    out = {}
    pa6, petg, al = (0.22, 0.24, 0.27), (0.85, 0.55, 0.15), (0.66, 0.70, 0.75)
    fl = floor_part()
    fls = fl.solid()
    out['bay_floor'] = Part('bay_floor', 'sheet', place_floor(fls), 1, fl, fls, fl.s['material'], colour=al, note=fl.note)
    sd = side_part()
    sds = sd.solid()
    for side in ('l', 'r'):
        out[f'bay_side_{side}'] = Part(f'bay_side_{side}', 'sheet', place_side(sds, side), 1, sd if side == 'l' else None, sds,
                                       sd.s['material'], colour=al, note=sd.note)
        out[f'bay_rail_{side}'] = Part(f'bay_rail_{side}', 'printed', rail(side), 1, material='pa6-cf', colour=pa6,
                                       note='PA6-CF; four M4 x 16 up into the belly\'s nuts, five M3 inserts, two in its ends')
    for k in ('front', 'rear'):
        out[f'adapter_plate_{k}'] = Part(f'adapter_plate_{k}', 'printed', adapter_plate(k), 1, material='pa6-cf', colour=pa6,
                                         note='PA6-CF; four M4 x 8 up into the belly\'s nuts; the adapter\'s screws into inserts set on arrival')
        out[f'bay_door_{k}'] = Part(f'bay_door_{k}', 'printed', door(k == 'front'), 1, material='petg', colour=petg,
                                    note='PETG; two knurled M3 x 10 thumbscrews into the rails\' ends', print_rotation=((0, 1, 0), 90))
    for i, sk in enumerate(skids()):
        out[f'bay_skid_{i + 1}'] = Part(f'bay_skid_{i + 1}', 'printed', sk, 1, material=PAD['material'], colour=(0.15, 0.15, 0.17),
                                        note=f"crush pad (#19): TPU 95A HF gyroid, {PAD['h']:.0f} mm free, {PAD['stroke']:.0f} mm stroke, on 3M VHB "
                                             'tape (no screw: under the packs there is 1 mm); the robot sits on these')
    return out
