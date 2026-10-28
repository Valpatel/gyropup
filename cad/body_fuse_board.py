"""The fuse board (D60, task B5) as the rest of the body sees it: where it sits on the power plate, what it weighs, its
holders, its studs and pads with the wires that land on them, the P3 rows of the wire list, and the parts to order.
Plain data; the board itself (KiCad, gerbers, checks) is hardware/fuse-board/, and docs/body-fuse-board.md explains it.

    .venv/bin/python cad/body_fuse_board.py          # prints the summary

The board replaces two P0 items of cad/body_layout.py's power plate: plate_fuses (the inline MINI holders) and
plate_shunt (the Blue Sea 150 A / 50 mV block). It sits in the free area x 34..122, y -14..62 (88 x 76 mm) on the
plate's top face, on printed standoffs: one M5 screw into the plate's flush nut at (50, 47) (the shunt's old base
nut), which also bonds the plate to the - bus, and three cable ties through the plate's slots at (46, -6), (111, -6),
(111, 24). The fuse bundle's old slot at (46, 24) and the shunt's nut at (119, 47) are left unused.

Topology change against P0 (docs/body-fuse-board.md 2): the shunt is on the HIGH side (between the MRBF's load stud and
the board's + bus), not in the pack's negative lead. The INA228's inputs may not go below -0.3 V from its ground
(TI SLYS021A 6.1); its ground is the switched - bus (the MCU's), so with the shunt in the negative lead before the
low-side switch, opening the switch drags the - bus up to the + bus while the INA228's inputs stay at the pack's -:
its input protection would then carry the robot's load current round the open switch. On the high side its inputs sit
0-41 V (D65: 10S) above its ground whether the switch is on or off. D65 (two DCB609 packs, 10S, 30-41 V, no charge
port) and D66 (the turret on its own fused branch; one TRACO 12 V converter for the J501 and the rail) set the
holders of section HOLDERS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
BOARD_DIR = R / 'hardware' / 'fuse-board'
sys.path.insert(0, str(BOARD_DIR))
import design as D  # noqa: E402

PLATE_TOP_Z = 138.215          # the power plate's top face: cad/body_layout.py z_tray_top() + PLATE_H + 0.100 in (2.54 mm)
STANDOFF_H = 10.0              # printed standoffs (PETG; PA6-GF if the plate runs over 60 C; never PA6-CF: carbon conducts)
HOLDER_TOP = 15.6              # Littelfuse MINI FL1 body above the board
FUSE_ABOVE = 8.8               # a MINI fuse's body above its holder
LUG_ROOM = 22.0                # above the board at the studs: a lug's barrel turned up and its lead's bend


def to_robot(bx, by):
    return (round(bx + D.ORIGIN[0], 3), round(by + D.ORIGIN[1], 3))


X0, Y0 = D.ORIGIN
X1, Y1 = X0 + D.SIZE[0], Y0 + D.SIZE[1]
Z_BOARD_BOTTOM = PLATE_TOP_Z + STANDOFF_H
Z_BOARD_TOP = Z_BOARD_BOTTOM + D.THICKNESS
ENVELOPE = {'x0': X0, 'x1': X1, 'y0': Y0, 'y1': Y1, 'z0': PLATE_TOP_Z, 'z1': round(Z_BOARD_TOP + HOLDER_TOP + FUSE_ABOVE, 3),
            'z_board_bottom': Z_BOARD_BOTTOM, 'z_board_top': round(Z_BOARD_TOP, 3),
            'note': 'robot frame, mm: the standoffs from the plate\'s top, the board, the holders with their fuses (the tallest '
                    'parts); the lugs and their leads need LUG_ROOM above the board at every stud'}


def mass_g():
    """(grams, basis): hardware/fuse-board/reports/analysis.json's estimate (board, holders, fuses, shunt, the INA228 board,
    screws, nuts and printed standoffs; the lugs and leads are the harness's)."""
    f = BOARD_DIR / 'reports' / 'analysis.json'
    if f.exists():
        m = json.loads(f.read_text())['mass']
        return m['total_g'], 'estimate (hardware/fuse-board/analysis.py: FR-4 and copper from the filled board, parts from datasheets)'
    return 132.0, 'estimate (hardware/fuse-board/analysis.py, 2026-10-27)'


FUSE_KEY = {20: 'fuse_mini58_20a', 30: 'fuse_mini58_30a', 10: 'fuse_mini58_10a', 7.5: 'fuse_mini58_7a5', 5: 'fuse_mini58_5a'}

# the holders: (ref, branch, wire it feeds, fuse A, the catalogue key of the fuse, the input it hangs off, its stud)
HOLDERS = []
for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
    stud = next(s for s in D.STUDS if s[2] == D.out_net(ref))
    HOLDERS.append({'ref': ref, 'branch': label, 'wire': wire, 'fuse_a': amps, 'fuse_key': FUSE_KEY.get(amps),
                    'input': net_in, 'stud': stud[0], 'robot_xy': to_robot(*D.holder_xy(col, row))})

LUG_KEY = {'J1': 'lug_8awg_m6', 'J6': 'ring_12awg_m4', 'J7': 'ring_12awg_m4', 'J8': 'ring_18awg_m4', 'J10': None, 'J11': None}  # the rest: 16-14 AWG

# every stud, pad and connector a wire lands on: (ref, name, net, size, robot (x, y), [wires], lug)
PADS = []
for ref, label, net, x, y, size, wires in D.STUDS:
    lug = LUG_KEY.get(ref, 'ring_14awg_m4')
    PADS.append({'ref': ref, 'name': label, 'net': net, 'stud': size, 'robot_xy': to_robot(x, y), 'wires': wires, 'lug': lug})
PADS += [
    {'ref': D.GH[0], 'name': 'I2C (JST GH 4)', 'net': '1 GND, 2 3V3, 3 SDA, 4 SCL', 'stud': 'SM04B-GHS-TB',
     'robot_xy': to_robot(D.GH[1], D.GH[2]), 'wires': ['W42 to the MCU carrier (GHR-04V-S, 4 x 300 mm pre-crimped)'], 'lug': None},
] + [{'ref': ref, 'name': f'test pad {net}', 'net': net, 'stud': 'THT pad 2.0 mm', 'robot_xy': to_robot(x, y),
      'wires': ['the Adafruit 5832\'s ' + {'INN': 'VIN-', 'INP': 'VIN+', 'VBUS': 'VBUS'}[net] + ' (only when it replaces U1)'], 'lug': None}
     for ref, net, x, y, note in D.TPS]

MOUNTS = [
    {'ref': 'MH1', 'robot_xy': to_robot(16.0, 61.0), 'into': 'the plate\'s F-M5-2 flush nut at (50, 47) (plate_shunt\'s base nut)',
     'hardware': 'M5 x 14 socket head (91290A230) down through the plated hole and a printed standoff 10 mm tall, OD 12',
     'bonds': 'the power plate to BUS- (the star point) through the screw and the nut'},
] + [{'ref': ref, 'robot_xy': to_robot(x, y), 'into': f'the plate\'s cable-tie slot at {to_robot(x, y)} (4 x 10)',
      'hardware': 'a cable tie (7130K12) up through the plate\'s slot, a printed tie block 10 mm tall and the board\'s slot, round '
                  'the block'} for ref, x, y in D.TIES]
STANDOFFS = {'height_mm': STANDOFF_H, 'material': 'PETG (PA6-GF if the plate runs over 60 C); never a carbon-filled filament',
             'stud_foot': 'under every stud: OD 12 (M4) or 16 (M6), a hex pocket at the top for the stud\'s nyloc (M4: 7.2 AF '
                          'x 5.3 deep; M6: 10.2 AF x 6.3), the screw\'s hole through; the lug sits on the top pad and the '
                          'screw comes down through it (copper to copper, serviced from above)',
             'count': len(D.STUDS) + 1 + len(D.TIES),
             'keep_clear_under_board': [(to_robot(x, y), r, what) for x, y, r, what in D.UNDER_KEEPOUT]}

# the P3 rows of the wire list (cad/body_wiring.py's tuple: id, from, to, AWG, colour, ends, fuse, why). The body's
# implementer merges these; "was" says what each replaces. D65: the bus is two DCB609 packs in series (10S, 30-41 V)
# with no charge port; D66 and the body's TRACO TEP 150-4812WI: one isolated 12 V converter for the J501 and the rail.
_LOAD = {'W10': 'RS-04 left front (XT60H)', 'W11': 'RS-04 left rear (XT60H)', 'W12': 'RS-04 right front (XT60H)',
         'W13': 'RS-04 right rear (XT60H)', 'W14': 'VESC left (Flipsky 75100) +', 'W15': 'VESC right +'}
P3_WIRES = [
    ('W4', 'MRBF block, load stud (M8)', 'fuse board J1 BUS+ IN (M6 stud)', 8, 'red', 'lugs M8 / M6', 'MRBF 80 A',
     'the whole robot through the board\'s shunt; was: to the + bus bar, which carries nothing in P3 (a load there would bypass the shunt)'),
    ('W5', 'the packs\' - (the series pair\'s negative)', 'main switch IN- (B-)', 8, 'black', 'lug / its lead', '-',
     'straight to the switch: no shunt in the - lead (W6 goes)'),
] + [(h['wire'], f'fuse board {h["stud"]} (M4 stud)', _LOAD[h['wire']], {20: 14, 30: 12}[h['fuse_a']], 'red', 'ring M4 / XT60H-F',
      f'MINI 58V {h["fuse_a"]:g} A (board {h["ref"]})', 'was: from a + bus tap through an inline holder') for h in HOLDERS if h['wire'] in _LOAD] + [
    ('W16', 'fuse board J8 (M4 stud)', 'TRACO TEP 150-4812WI Vin+', 18, 'red', 'ring M4 / ferrule', 'MINI 58V 10 A (board F7)',
     '150 W out: about 5.6 A in at 30 V, plus its inrush; was: the DDR-120C-24\'s input'),
    ('W22', 'fuse board J9 (M4 stud)', 'stop relay, pole B (in); pole B (out) to the turret\'s XT30 (W34)', 16, 'red', 'ring M4 / screw terminal',
     'MINI 58V 7.5 A (board F8)', 'D66: the turret on the 10S bus, about 40 W, bursts to about 140 W (4.7 A at 30 V); the radio stop still '
     'cuts it (pole B, the G2RL-2: see docs/body-fuse-board.md 1 for its DC rating); was: the 24 V rail'),
    ('W40', 'TRACO TEP 150-4812WI +V', 'fuse board J14 12V IN (M4 stud)', 14, 'red', 'ferrule / ring M4', '(the converter\'s 12.5 A limit)',
     'new: the 12 V rail into the board\'s two holders (W21, W43 start there)'),
    ('W21', 'fuse board J12 (M4 stud)', 'J501 DC-IN (XT30)', 16, 'red', 'ring M4 / XT30U-F', 'MINI 58V 10 A (board F11)',
     'the J501 at 12 V (12-36 V in): 55-60 W, 5 A; was: 24 V from the DDR-120C-24'),
    ('W43', 'fuse board J13 (M4 stud)', 'the 12 V rail: lidar box, SSC1 lights, eyes, 5 V buck', 16, 'red', 'ring M4 / per load',
     'MINI 58V 7.5 A (board F12)', 'new: about 40 W, 3.3 A; was: the DDR-60L-12\'s +V (W24-W26)'),
    ('W23', 'TRACO TEP 150-4812WI -V', 'the 12 V returns; fuse board J15 STAR', 14, 'black', 'ferrule / ring M4', '-',
     'the isolated 12 V rail\'s one tie to the - bus (the CAN reference), at the board\'s star stud'),
    ('W33', 'frame (a tray PEM stud)', 'fuse board J16 FRAME (M4 stud)', 14, 'green', 'ring M5 / ring M4', '-',
     'the frame bond on its own stud; 14 AWG (was 18): a + lead chafed before its branch fuse puts the MRBF\'s let-through on this wire'),
    ('W41', '- bus bar, tap 5 (M6)', 'fuse board J15 STAR (M4 stud)', 14, 'black', 'ring M6 / ring M4', '-',
     'new: ties the board\'s BUS- (star, frame bond, plate bond, the INA228\'s ground) to the - bus'),
    ('W42', 'fuse board J17 (JST GH 4: 1 GND, 2 3V3, 3 SDA, 4 SCL)', 'MCU carrier: Nucleo I2C1 (PB8 SCL, PB9 SDA), 3V3, GND; 4.7 kOhm pull-ups there',
     28, 'white', 'GHR-04V-S / per the carrier', '-', 'new: the INA228 on I2C (replaces W30-W32: the sense lines and VBUS are on the board)'),
]
P3_REMOVED = ['W6 (shunt to the switch: the shunt is on the board, on the + side)', 'W30, W31, W32 (the Kelvin pair and VBUS: on the board)',
              'W8, W9 (D65: no charge port)', 'W17, W27 (D66: the DDR-60L-12 is gone)',
              'the inline holders of W10-W16, W21, W22 (on the board)']

# the parts to order for one board built (five bare boards come from JLCPCB): (catalogue key, qty, note)
ORDER = [
    ('fuse_board_pcb', 1, 'one JLCPCB order of 5 boards (2 oz, 1.6 mm, lead-free HASL): fab/fuse-board-gerbers.zip'),
    ('fuse_holder_mini_pcb', 14, '12 on the board and 2 spares'),
    ('fuse_mini58_7a5', 3, 'F8 (the turret), F12 (the 12 V rail) and a spare'),
    ('shunt_1mohm_3920', 2, 'R1 and a spare'),
    ('res_10r_0603', 20, 'R2, R3 (LCSC sells 20+)'),
    ('cap_100n_100v_0603', 50, 'C1 (LCSC sells 50+)'),
    ('cap_100n_50v_0603', 50, 'C2 (LCSC sells 50+)'),
    ('res_4k7_2512', 10, 'R4 (LCSC sells 10+)'),
    ('gh_header_4p_smd', 5, 'J17 (LCSC sells 5+)'),
    ('gh_housing_4p', 2, 'W42 at both ends'),
    ('gh_lead_2p_300', 4, 'W42\'s four pre-crimped wires'),
    ('ring_12awg_m4', 3, 'W14, W15 and a spare (3-pack)'),
    ('ring_14awg_m4', 12, 'W10-W13, W21, W22, W43 (16 AWG), W40, W23, W41, W33 and a spare (4 x 3-pack)'),
    ('ring_18awg_m4', 3, 'W16 and two spares (3-pack)'),
    ('screw_m4x12_socket', 15, 'the M4 studs (100-pack)'),
    ('nut_m4_nyloc', 15, 'in the standoffs\' pockets (100-pack)'),
    ('screw_m6x12_socket', 1, 'J1 (100-pack)'),
    ('nut_m6_nyloc', 1, 'J1 (on the body\'s order already: the bus bars\' 100-pack)'),
    ('screw_m5x14_socket', 1, 'MH1 into the plate (100-pack)'),
    ('cable_tie_4in', 3, 'the tie slots (100-pack)'),
    ('ina228', 0, 'reuse P0\'s Adafruit 5832 (its 15 mOhm shunt off, wired to TP1-TP3), or fit ina228_ic as U1'),
    ('ina228_ic', 0, 'optional bare INA228 for U1 (LCSC had none in stock on 2026-10-27)'),
]
REUSED = ['the MINI 58V fuses of P0 (fuse_mini58_20a x 4, 30a x 2, 10a x 2)', 'the Adafruit 5832 (ina228)',
          'W4\'s 8 AWG M6 lug (lug_8awg_m6)']


def catalogue():
    out = {}
    for f in ('body.json', 'hardware.json'):
        p = R / 'catalog' / f
        if p.exists():
            for it in json.loads(p.read_text()):
                if isinstance(it, dict) and it.get('key'):
                    out[it['key']] = it
    return out


def order_cost():
    """[(key, qty, note, what is paid, usd)]: packs bought whole; the PCB's price is the 5-board order."""
    cat = catalogue()
    rows = []
    for key, qty, note in ORDER:
        it = cat.get(key)
        if not it or qty == 0:
            rows.append((key, qty, note, 'reused / optional', 0.0))
            continue
        pack = it.get('pack_qty') or 1
        if key == 'nut_m6_nyloc':
            rows.append((key, qty, note, 'on the body\'s order', 0.0))
            continue
        if pack > 1:
            packs = -(-qty // pack)
            rows.append((key, qty, note, f'{packs} x {pack}-pack', packs * it['pack_price_usd']))
        else:
            rows.append((key, qty, note, f'{qty} x', qty * it['price_usd']))
    return rows


LAYOUT_ITEM = {
    'name': 'plate_fuse_board', 'box': (X0, X1, Y0, Y1, PLATE_TOP_Z, ENVELOPE['z1']), 'group': 'power', 'stage': 'P3',
    'catalog': 'gyropup-fuse-board-jlcpcb', 'rgb': (0.1, 0.35, 0.2),
    'note': 'the fuse board (D60): twelve MINI 58V holders, the 1 mOhm high-side shunt and the INA228, the star and frame-bond '
            'studs; on 10 mm printed standoffs, one M5 into the plate\'s nut at (50, 47) (the plate bond), three ties',
    'replaces': ['plate_fuses', 'plate_shunt'],
}


def summary():
    g, basis = mass_g()
    e = ENVELOPE
    print(f"fuse board {D.SIZE[0]:g} x {D.SIZE[1]:g} mm, {D.COPPER_OZ:g} oz, {D.THICKNESS} mm; robot x {e['x0']:g}..{e['x1']:g}, "
          f"y {e['y0']:g}..{e['y1']:g}, z {e['z0']:g}..{e['z1']:g} (board {e['z_board_bottom']:g}..{e['z_board_top']:g}); "
          f"{g:g} g ({basis})")
    print('holders (Littelfuse MINI FL1, 58 V DC, 22 A continuous; Littelfuse MINI 58V fuses only):')
    for h in HOLDERS:
        print(f"  {h['ref']:4} {h['branch']:13} {('%g' % h['fuse_a']) if h['fuse_a'] else '-':>3} A  {h['wire'] or '-':4} from {h['input']:5} -> {h['stud']}")
    print('studs and pads:')
    for p in PADS:
        print(f"  {p['ref']:4} {p['name']:15} {p['net']:28} {p['stud']:13} at {p['robot_xy']}: {'; '.join(p['wires'])}")
    print('mounting:')
    for m in MOUNTS:
        print(f"  {m['ref']:4} at {m['robot_xy']}: {m['hardware']}")
    print('P3 wire rows:')
    for w in P3_WIRES:
        print(f"  {w[0]:4} {w[1]} -> {w[2]} ({w[3]} AWG {w[4]}, {w[6]})")
    print('removed in P3:', '; '.join(P3_REMOVED))
    total = 0.0
    print('order (one board built):')
    for key, qty, note, paid, usd in order_cost():
        total += usd
        print(f"  {key:22} {qty:3}  {paid:22} ${usd:7.2f}  {note}")
    print(f"  total ${total:.2f} before shipping (reused: {'; '.join(REUSED)})")


if __name__ == '__main__':
    summary()
