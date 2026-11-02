"""The body's metal parts today and in the study's options, as SheetParts (cad/body_sheet.py), built from the body's own
CAD functions (cad/body_frame.py, cad/body_battery.py) and changed only here: nothing in cad/ is edited.

    from parts import options                 # {option: {part: (SheetPart, note)}}

Each option is a list of SendCutSend parts. The non-metal side of each option (printed parts, bought hardware,
assembly steps) is in study.py. The variants:

  tray_2b     the floor tray with lips on its two long sides only (2 bends, not 4)
  deck_2b     the deck in 1/8 in 5052 with lips on its two long sides only, the turret plate (D59) folded into it:
              its three fan-duct tabs become PEM S-M3-0 nuts in the deck, its two end screws go
  keel_half   the battery bay's side, half its floor and a top flange in one 2-bend C-channel (0.090 in 5052), two of
              them riveted to two flat straps: the bay and the belly plate in two identical parts (option B)
  strap       the flat strap the two keel halves are riveted to (option B), one under the floor seam and one across
              the top flanges under the spine's gap
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / 'cad', R / 'tools'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import body_params as bp  # noqa: E402

# SendCutSend's 0.090 in 5052-H32 row, as cad-agent's process profile reads SendCutSend's specs JSON
# (cadagent.manufacturing.process, shop table ALU-090: R 0.813 mm, K 0.37, flange 8.28 mm, relief 3.607 mm). The die
# width is not in that table; 0.630 in (the 0.100 and 0.125 in die) is taken, which keeps cut features further from the
# bends than a smaller die would ask.
if '5052-0.090' not in bp.STOCK:
    s = {'material': '5052-H32 aluminium', 't_in': 0.090, 'bend': True, 'r_in': 0.813 / 25.4, 'k': 0.37, 'bd_in': None,
         'min_flange_in': 8.28 / 25.4, 'die_in': 0.630, 'countersink': False, 'hardware': True, 'density': 2.68,
         'yield_mpa': 193.0, 'E_mpa': 70300.0}
    s['t'] = s['t_in'] * bp.IN
    s['r'] = s['r_in'] * bp.IN
    s['ossb'] = s['r'] + s['t']
    s['ba'] = math.pi / 2 * (s['r'] + s['k'] * s['t'])
    s['bd'] = 2 * s['ossb'] - s['ba']
    s['bd_in'] = s['bd'] / bp.IN
    s['min_flange'] = s['min_flange_in'] * bp.IN
    s['half_die'] = s['die_in'] * bp.IN / 2
    bp.STOCK['5052-0.090'] = s

import body_battery as bb  # noqa: E402
import body_frame as bf  # noqa: E402
import body_sheet as bs  # noqa: E402

RIVET = {'name': '1/8 in (3.2 mm) aluminium blind rivet, 0.126-0.187 in grip', 'hole_mm': 3.3, 'pitch_mm': 40.0, 'edge_mm': 6.4}
KEEL_STOCK = '5052-0.090'
KEEL_IN = 3.0               # both flanges of a keel half stop 3 mm short of the centreline (a 6 mm seam under a strap)
RIVET_Y = 10.0              # each rivet row's robot |y|: 7 mm from the flange's inner edge, 10 mm from the strap's
STRAP_W = 40.0
RAIL_SCREW_BELOW = 16.0     # option B: the bay rails' M3 screws through the web this far below the top flange's face


def _mounts():
    import body_layout as bl
    return bl.layout()['mounts']


def today(m=None) -> dict:
    """The SendCutSend parts of the body as cad/ builds them today: {name: SheetPart}."""
    m = m if m is not None else _mounts()
    return {'cheek': bf.cheek_part(), 'floor_tray': bf.tray_part(m), 'belly_plate': bf.belly_part(m), 'deck': bf.deck_part(m),
            'compute_pallet': bf.pallet_part(m), 'power_plate': bf.power_plate_part(m), 'bus_bar': bf.bus_bar_part(),
            'turret_plate': bf.turret_plate_part(m), 'bay_floor': bb.floor_part(), 'bay_side': bb.side_part()}


def two_bends(part: bs.SheetPart, name: str, stock: str | None = None) -> bs.SheetPart:
    """The same part with lips on its two long (S, N) edges only."""
    p = copy.deepcopy(part)
    p.name = name
    p.flanges = [f for f in p.flanges if f.edge in ('S', 'N')]
    if stock:
        p.stock = stock
    return p


def tray_2b(m) -> bs.SheetPart:
    p = two_bends(bf.tray_part(m), 'floor_tray_2b')
    p.note = 'the floor tray with 15 mm lips on its two long sides only (2 bends); otherwise as today'
    return p


def deck_2b(m) -> bs.SheetPart:
    """The deck in 1/8 in 5052, two lips, the turret plate folded in: its end screws' holes go, the fan duct's three tabs
    become PEM S-M3-0 nuts pressed from the deck's underside (they were tapped holes in the turret plate)."""
    import body_shell as bsh
    p = two_bends(bf.deck_part(m), 'deck_2b', stock='5052-0.125')
    ends = [bf.tray_uv(x, y) for x, y in bf.turret_plate_end_holes()]
    p.features = [f for f in p.features if not any(math.dist(f.at, e) < 0.5 for e in ends)]
    for (x, y) in bsh.duct_tabs():
        p.features.append(bs.Feature('pem', 'base', bf.tray_uv(x, y), bp.PEM['S-M3-0']['H'], spec='S-M3-0',
                                     note='fan duct tab (was tapped in the turret plate)'))
    p.note = ('the deck in 1/8 in 5052 with 20 mm lips on its two long sides (2 bends); the turret plate (D59) folded in: '
              'the riser bolts straight through the deck, the duct tabs into three PEM S-M3-0')
    return p


def keel_geometry() -> dict:
    g = bb.geometry()
    t = bp.STOCK[KEEL_STOCK]['t']
    web = (-bf.ZT) - g['z_floor']                       # from the cheeks' lower flange face to the bay floor's underside
    return {'L': bp.BODY_X[1] - bp.BODY_X[0], 'x0': bp.BODY_X[0], 'web': web,       # the belly plate's 320 mm length
            'top': g['half_y'] - KEEL_IN, 'floor': g['half_y'] - KEEL_IN, 'half_y': g['half_y'], 't': t}


def keel_half(m) -> bs.SheetPart:
    """One keel half (both are the same part; the right one is the left turned 180 deg about z): a C-channel whose web is
    the bay's side, whose bottom flange is half the bay's floor and whose top flange, under the cheeks' lower flanges,
    takes the belly plate's job: four M5 screws up into the cheek nuts, the pack adapter plates' four S-M4-0 nuts, and
    the strap's rivets. Both flanges stop 3 mm short of the centreline. The web keeps today's side-plate holes (the rails' M3 screws) and windows."""
    k = keel_geometry()
    L, H = k['L'], k['web']
    feats = []
    xs = lambda x: x - k['x0']                      # robot x -> u
    # the top flange ('N', w = distance from the web's outer face inwards): the belly plate's features with y > 0
    belly = bf.belly_part(m)
    for f in belly.features:
        x = f.at[0] + bp.BODY_X[0]
        y = bp.BELLY_HALF_Y - f.at[1]
        if y <= 0 or f.kind == 'slot':
            continue
        if 'rail' in f.note:                         # the rails now screw to the web (below); their belly nuts go
            continue
        w = k['half_y'] - y                          # from the web's outer face
        if f.kind == 'pem':
            feats.append(bs.Feature('pem', 'N', (xs(x), w), f.d, spec=f.spec, note=f.note))
        else:
            feats.append(bs.Feature('hole', 'N', (xs(x), w), f.d, note=f.note))
    nr = int((L - 2 * RIVET['edge_mm']) // RIVET['pitch_mm']) + 1
    pitch = (L - 2 * RIVET['edge_mm']) / (nr - 1)
    for i in range(nr):                              # the strap's rivets: top flange (across the gap) and floor seam
        u = RIVET['edge_mm'] + i * pitch
        for e in ('N', 'S'):
            feats.append(bs.Feature('hole', e, (u, k['half_y'] - RIVET_Y), RIVET['hole_mm'], note='rivet to a strap'))
    side = bb.side_part()                            # the web: today's side plate's rail holes and windows (u along x, v up
                                                     # from the floor); its screws into the old floor's flange nuts go
    for f in side.features:
        if 'floor' in f.note:
            continue
        v = f.at[1]
        if 'rail' in f.note:                         # the rails grow from 10 to 20 mm tall so their screws clear the top bend
            v = H - RAIL_SCREW_BELOW
        feats.append(bs.Feature(f.kind, 'base', (f.at[0] + bb.geometry()['x_in'][0] - k['x0'], v), f.d, size=f.size, note=f.note))
    return bs.SheetPart('keel_half', KEEL_STOCK, L, H, flanges=[bs.Flange('S', k['floor']), bs.Flange('N', k['top'])],
                        features=feats, qty=2,
                        note='option B: the bay side, half the floor and a top flange in one C-channel (both flanges inwards); '
                             'two of them riveted to two straps; the right one is the left turned 180 deg about z')


def strap() -> bs.SheetPart:
    k = keel_geometry()
    L = k['L']
    nr = int((L - 2 * RIVET['edge_mm']) // RIVET['pitch_mm']) + 1
    pitch = (L - 2 * RIVET['edge_mm']) / (nr - 1)
    feats = []
    for i in range(nr):                       # the strap's centreline is the robot's y = 0; a rivet row each side
        u = RIVET['edge_mm'] + i * pitch
        for s in (1, -1):
            feats.append(bs.Feature('hole', 'base', (u, STRAP_W / 2 + s * RIVET_Y), RIVET['hole_mm'], note='rivet'))
    x_lead = bb.LEADS_SLOT[0] - k['x0']
    feats.append(bs.Feature('slot', 'base', (x_lead, STRAP_W / 2), size=(bb.LEADS_SLOT[1], 10.0, 4.0),
                            note='the packs\' leads (top strap); a drain (floor strap)'))
    return bs.SheetPart('strap', KEEL_STOCK, L, STRAP_W, features=feats, qty=2,
                        note='option B: flat; one under the floor seam, one across the top flanges under the spine\'s gap (the belly '
                             'plate\'s tie between the cheeks); the same part twice')


def options(m=None) -> dict:
    """{option: {part name: SheetPart}} for the SendCutSend side of each option."""
    m = m if m is not None else _mounts()
    t = today(m)
    a = {k: v for k, v in t.items() if k not in ('floor_tray', 'deck', 'turret_plate')}
    a.update({'floor_tray_2b': tray_2b(m), 'deck_2b': deck_2b(m)})
    b = {k: v for k, v in a.items() if k not in ('belly_plate', 'bay_floor', 'bay_side')}
    b.update({'keel_half': keel_half(m), 'strap': strap()})
    c = {k: v for k, v in b.items() if k not in ('floor_tray_2b', 'deck_2b', 'compute_pallet', 'power_plate')}
    c['turret_plate'] = t['turret_plate']
    return {'today': t, 'A': a, 'B': b, 'C': c}
