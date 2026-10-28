"""The body's power and CAN wiring (milestone M5, P0 power skid): one wire list and the diagram drawn from it.

    .venv/bin/python cad/body_wiring.py      # -> exports/body/wiring.json, exports/body/wiring.svg

The wire list is the build sheet: every run with its two ends, gauge, colour, connector, the fuse that protects it and
why that size. docs/body-electrical.md explains the system; this file is what the drawing and the table are made from,
so they cannot disagree.

The system (D65, D54-D56, D60, D66): two DeWalt DCB609 FLEXVOLT packs in 20 V mode on two rail adapters, in series:
10S3P, 36 V nominal, 41 V full, 30 V empty (the robot enforces 3.0 V a cell and the current limit: the packs talk to
nothing); an XT90-S at the bay's lead; the 80 A MRBF main fuse then the 150 A / 50 mV shunt on the + lead (the INA228
reads it high side: in the - lead ahead of the low-side switch it would be destroyed when the switch opens, docs/
body-fuse-board.md 1); the anti-spark main switch on the - lead (low side, as Flipsky draws it: verify on its card);
two C110 bus bars; Littelfuse MINI 58V fuses in inline holders to every branch (the fuse board in P3); one isolated
TRACO TEP 150-4812WI for 12 V (the J501, the lidar box, the lights and eyes, the 5 V buck, the radio stop); the turret
(D66) on its own fused branch of the bus through the stop relay. No charge port: the packs charge on DeWalt's chargers.

The live-end rule (hazard 11, D58): every connector on the body's side of a lead that is live with the packs in is a
SOCKET (female): the bay's XT90-S, every bus branch lead (XT60H-F; the turret's XT30U-F) and the 12 V branch leads
(XT30U-F). The devices' leads carry the pins (males): the RS-04 pigtails (the leg's: 450 mm, XT60H-M), the VESCs' own
leads, the J501's DC-IN, the lidar box's adapter lead and the turret's lead. `cad/test_body.py` checks it.
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'body'

PACK = {'cells': 'two DeWalt DCB609 FLEXVOLT 9.0 Ah in 20 V mode (5S3P each), in series: 10S3P', 'v_nom': 36.0, 'v_full': 41.0,
        'v_full_per_cell': 4.10, 'v_empty': 30.0, 'ah': 9.0, 'wh_rated': 360, 'peak_a': 80, 'cont_a': 30,
        'protection': 'none in the packs the robot can use: the firmware sits at 32 V, cuts off at 30 V under load, limits the '
                      'bus current to 30 A (1 s) and 80 A (0.5 s), clamps regeneration over 41.5 V and latches off over 44 V '
                      '(docs/body-firmware.md); the MRBF 80 A is the last line'}

# (id, from, to, AWG, colour, connector/termination, fuse, why)
WIRES = [
    # ---- the packs, the bay's lead and the main path
    ('W1', 'front adapter + (its 10 AWG lead)', 'XT90-S female (the bay\'s lead) +', 10, 'red', 'XT90-S solder cup', '-',
     'the adapter\'s own lead (Terrafirma, 10 AWG, 30 A stated): on the pack\'s side of the MRBF, unfused as every pack lead; keep it to its 300 mm'),
    ('W2', 'front adapter -', 'rear adapter + (the series link)', 10, 'black', 'XT90-S pair (in the bay\'s middle)', '-',
     'the two packs in series: the link unplugs so each half is 18 V when the bay is serviced'),
    ('W3', 'rear adapter -', 'XT90-S female (the bay\'s lead) -', 10, 'black', 'XT90-S solder cup', '-', 'the pair\'s negative'),
    ('W4', 'XT90-S male (robot) +', 'MRBF block, battery stud (M8)', 8, 'red', 'lug M8', '-', 'unfused until the MRBF: keep it short (<150 mm)'),
    ('W5', 'MRBF block, load stud (M8)', 'shunt, battery side (M8)', 8, 'red', 'lugs M8', 'MRBF 80 A',
     'the shunt on the + side: the INA228 reads it high side (docs/body-fuse-board.md 1); its base insulates it from the plate'),
    ('W6', 'shunt, load side (M8)', '+ bus bar, tap 1 (M6)', 8, 'red', 'lugs M8 / M6', 'MRBF 80 A', 'the whole robot'),
    ('W7', 'XT90-S male (robot) -', 'main switch IN- (B-)', 8, 'black', 'ferrule / its lead', '-', 'Flipsky draws the switch on the negative: check its card'),
    ('W8', 'main switch OUT- (P-)', '- bus bar, tap 1 (M6)', 8, 'black', 'lug M6', '-', 'the switched negative: everything below is off with it'),
    # ---- the bus branches
    ('W10', '+ bus tap 2', 'RS-04 left front (XT60H)', 14, 'red', 'lug M6 / XT60H-F', 'MINI 58V 20 A',
     '~12 A at a jump, 25 A peaks: 14 AWG silicone; the motor\'s 450 mm pigtail carries the XT60H-M'),
    ('W11', '+ bus tap 2', 'RS-04 left rear (XT60H)', 14, 'red', 'lug M6 / XT60H-F', 'MINI 58V 20 A', 'as W10 (two lugs share the tap)'),
    ('W12', '+ bus tap 3', 'RS-04 right front (XT60H)', 14, 'red', 'lug M6 / XT60H-F', 'MINI 58V 20 A', 'as W10'),
    ('W13', '+ bus tap 3', 'RS-04 right rear (XT60H)', 14, 'red', 'lug M6 / XT60H-F', 'MINI 58V 20 A', 'as W10'),
    ('W14', '+ bus tap 4', 'VESC left (Flipsky 75100) +', 12, 'red', 'lug M6 / XT60H-F', 'MINI 58V 30 A',
     'the wheel: its battery current limit 20 A in VESC Tool (the fuse board\'s FL1 holders carry 22 A); its own lead carries the XT60H-M'),
    ('W15', '+ bus tap 4', 'VESC right +', 12, 'red', 'lug M6 / XT60H-F', 'MINI 58V 30 A', 'as W14'),
    ('W16', '+ bus tap 5', 'TRACO TEP 150-4812WI Vin+', 18, 'red', 'lug M6 / ferrule', 'MINI 58V 10 A', '150 W out: 5.6 A in at 30 V'),
    ('W22', '+ bus tap 5', 'stop relay, pole B (in): the turret\'s branch', 16, 'red', 'lug M6 / screw terminal', 'MINI 58V 7.5 A',
     'D66: the turret\'s own robot on the bus (its Orin NX ~40 W, flywheel bursts to ~140 W: 4.7 A at 30 V); 7.5 A keeps the G2RL-2\'s '
     'contact under its 8 A (about 6 A breaking at 41 V: docs/body-fuse-board.md); the stop relay cuts it'),
    ('W18', '- bus taps 2-3', 'RS-04 x 4 (XT60H)', 14, 'black', 'lug M6 / XT60H-F', '-', 'returns, one per motor (the - of W10-W13\'s plugs)'),
    ('W19', '- bus tap 4', 'VESC left, right -', 12, 'black', 'lug M6 / XT60H-F', '-', 'returns (the - of W14-W15\'s plugs)'),
    ('W20', '- bus tap 5', 'TRACO Vin-, the turret\'s XT30U-F -', 16, 'black', 'lug M6 / ferrule / XT30', '-', 'returns'),
    # ---- 12 V (isolated; its - tied to the - bus at the star point)
    ('W21', 'TRACO +V', 'J501 DC-IN (XT30)', 16, 'red', 'ferrule / XT30U-F', 'MINI 10 A (inline)',
     'the J501 at 12 V (12-36 V in): 60 W peak, 5 A; its DC-IN adapter lead carries the XT30U-M'),
    ('W43', 'TRACO +V', '12 V loads: lidar box, buck, jack, lights, eyes', 16, 'red', 'ferrule / Wago 221', 'MINI 58V 7.5 A (inline)',
     'about 40 W: the VLP-16 8 W (3 A at spin-up), the SSC1 pods, the eyes, the 5 V buck'),
    ('W23', 'TRACO -V', 'J501 return; star point', 16, 'black', 'ferrule / XT30U-F', '-', 'one tie from -V to the - bus (the CAN reference)'),
    ('W24', '12 V loads (W43)', 'lidar interface box (XT30)', 18, 'red', 'Wago 221 / XT30U-F', '(W43\'s 7.5 A)', 'the box\'s lead carries the XT30U-M'),
    ('W25', '12 V loads (W43)', '5 V buck VIN (Pololu D36V28F5)', 22, 'red', 'Wago 221 / solder', '(W43\'s 7.5 A)', '~0.6 A at 12 V'),
    ('W26', '12 V loads (W43)', 'radio-stop jack pin 3 (+12 V)', 22, 'red', 'Wago 221 / jack', '(W43\'s 7.5 A)', 'D37: the jack offers 12 V'),
    ('W27', 'TRACO -V', 'lidar box, buck, jack GND', 18, 'black', 'ferrule', '-', 'the 12 V loads\' returns'),
    # ---- 5 V
    ('W28', '5 V buck VOUT', 'Nucleo E5V, 3 CAN Pal, VN-100, radio receiver', 22, 'red', 'solder / GH', '(the buck\'s 3.2 A limit)', '~1 A in all'),
    ('W29', '5 V buck GND', 'the same, GND', 22, 'black', 'solder / GH', '-', ''),
    # ---- measurement and protection
    ('W30', 'shunt sense + (battery side screw)', 'INA228 IN+', 22, 'white', 'ring / screw terminal', '-',
     'Kelvin pair, twisted, away from the 8 AWG; high side: 30-41 V above the INA228\'s ground, inside its 85 V'),
    ('W31', 'shunt sense - (load side screw)', 'INA228 IN-', 22, 'white', 'ring / screw terminal', '-', 'the INA228\'s own 15 mOhm shunt is removed'),
    ('W32', '+ bus tap 5', 'INA228 VBUS', 22, 'red', 'lug M6 / ring', 'MINI 58V 5 A (its own inline holder)', 'pack voltage, 85 V input; 22 AWG carries 7 A'),
    ('W33', 'frame (a tray PEM stud)', '- bus star point', 14, 'green', 'ring M5 / lug M6', '-',
     'a + short to the frame blows a fuse, not leaves it live; 14 AWG: a + lead chafed ahead of its branch fuse puts the MRBF\'s let-through on it'),
    # ---- the turret (D66: its own robot; power on an XT30, Ethernet to the J501, the dry safety loop)
    ('W34', 'stop relay, pole B (out)', 'the turret\'s XT30U-F +', 16, 'red', 'screw terminal / XT30U-F', 'MINI 58V 7.5 A (W22)',
     'dead whenever the stop relay is open; the turret\'s lead carries the XT30U-M'),
    ('W36', 'J501 Ethernet (its second port or a switch)', 'the turret\'s RJ45', None, 'blue', 'Cat 6, 0.5 m', '-', 'D66: the turret\'s link (it had can1)'),
    ('W37', 'stop relay, pole A (closed = run)', 'the turret\'s safety loop (SAFETY_A, SAFETY_B)', 22, 'white', 'twisted pair', '-',
     'the turret\'s dry safety loop (12 V at 2 mA; D41 D7: it cuts the flywheels and the dial in hardware)'),
    ('W38', 'stop relay coil, + side', 'MCU STOP sense (divider 12 V to 3.3 V)', 22, 'white', 'GH', '-',
     '12 V on the coil = the radio says run: the MCU sits the robot down when it drops (D37)'),
    ('W39', '12 V loads (W43) via the RC switch\'s contact', 'stop relay coil, + side', 22, 'red', 'solder / screw terminal', '(W43\'s 7.5 A)',
     'the coil (12 V, 33 mA) is fed only while the radio says run; its - side through the MCU\'s MOSFET (MCU_RUN), a diode across it'),
    # ---- D69: the hub wheels' leads, each through the cheek's gland at the hip (IP54) to its VESC. The body's ends are
    # sockets (DT06 / DTP06 plugs, as the live-end rule asks: the VESC side is live with the packs in); the wheel's lead
    # carries the pins (DT04 / DTP04 receptacles), so a wheel pushed by hand (its back-EMF, ~7 V at a walking pace) shows
    # pins only on the unplugged wheel. Contacts: DTP size 12 for 12-14 AWG (25 A), DT size 16 for 16-20 AWG (13 A)
    ('W50', 'VESC left phases A/B/C', 'left wheel phases (its lead\'s DTP04-4P)', 14, 'yellow/green/blue',
     'DTP06-4S plug + WM-4S wedge, 3 x 0462-203-12141 sockets (4th cavity plugged, 114017)', '-',
     'D69: 30 A motor peak for 0.5 s, 10 A continuous; 14 AWG silicone, 400 mm to the cheek\'s gland; no fuse (the VESC limits it)'),
    ('W51', 'VESC left halls (5 V, GND, H1-H3) + motor NTC', 'left wheel sensors (its lead\'s DT04-6P)', 20, 'per VESC',
     'DT06-6S plug + W6S wedge, 6 x 0462-201-20141 sockets', '-', 'D69: halls and the stator NTC; a shielded 6-core, shield to the VESC\'s GND only'),
    ('W52', 'VESC right phases A/B/C', 'right wheel phases (its lead\'s DTP04-4P)', 14, 'yellow/green/blue',
     'DTP06-4S plug + WM-4S wedge, 3 x 0462-203-12141 sockets (4th cavity plugged, 114017)', '-', 'as W50'),
    ('W53', 'VESC right halls (5 V, GND, H1-H3) + motor NTC', 'right wheel sensors (its lead\'s DT04-6P)', 20, 'per VESC',
     'DT06-6S plug + W6S wedge, 6 x 0462-201-20141 sockets', '-', 'as W51'),
]

CAN = [
    ('A', 'MCU FDCAN1 (CAN Pal 1, 120 Ohm on)', ['RS-04 left front', 'RS-04 left rear (120 Ohm at its plug)'], '1 Mbit/s, the left leg'),
    ('B', 'MCU FDCAN2 (CAN Pal 2, 120 Ohm on)', ['RS-04 right front', 'RS-04 right rear (120 Ohm at its plug)'], '1 Mbit/s, the right leg'),
    ('C', 'MCU FDCAN3 (CAN Pal 3, 120 Ohm on)', ['VESC left', 'VESC right', 'J501 can0 (its own 120 Ohm on)'], '1 Mbit/s: wheels, the computer'),
]

STOP = ('The radio stop (D37, D55): the ER3C-i receiver (failsafe: no pulses) drives one Pololu RC relay switch; its contact feeds '
        'the coil of the stop relay (Omron G2RL-2, DPDT, 12 V), whose other end goes to ground through the MCU\'s MOSFET. The relay '
        'holds only while the radio says run AND the MCU says run. Pole A is the turret\'s dry safety loop (TM pins 7, 8: the turret '
        'cuts its flywheels and dial in 20 ms), pole B is in the turret\'s bus branch (W22, W34: the independent cut); the MCU senses the coil '
        'voltage and sits the robot down when the radio drops, and opens the relay itself when the robot sits. The main switch is the '
        'hard off.')


def svg() -> str:
    """The diagram (1300 x 900): the pack and the main path left, the bus bars and fuses in the middle, the loads right,
    the low-voltage rails and CAN below. Every wire carries its W-number from WIRES."""
    W, H = 1400, 960
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif" font-size="12">',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<defs><marker id="dot" markerWidth="6" markerHeight="6" refX="3" refY="3"><circle cx="3" cy="3" r="2.2" fill="#333"/></marker></defs>',
         '<text x="20" y="28" font-size="18" font-weight="bold">Gyropup body P0: power and CAN wiring</text>',
         f'<text x="20" y="46" fill="#555">Two DCB609 in series (10S, D65): {PACK["v_nom"]} V nominal, {PACK["v_full"]} V full, {PACK["v_empty"]} V empty. '
         'W-numbers are the rows of docs/body-electrical.md (cad/body_wiring.py). Red +, black -, white sense, green frame bond.</text>']

    def box(x, y, w, h, title, lines=(), fill='#f4f6f8', stroke='#333'):
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        o.append(f'<text x="{x + 8}" y="{y + 17}" font-weight="bold">{title}</text>')
        for i, t in enumerate(lines):
            o.append(f'<text x="{x + 8}" y="{y + 33 + 14 * i}" fill="#333" font-size="11">{t}</text>')

    def wire(pts, colour, label=None, at=0, dx=4, dy=-4, width=3.0):
        c = {'red': '#d62728', 'black': '#222', 'white': '#888', 'green': '#2ca02c', 'blue': '#1f5fbf', 'orange': '#e08a00'}[colour]
        p = ' '.join(f'{x},{y}' for x, y in pts)
        o.append(f'<polyline points="{p}" fill="none" stroke="{c}" stroke-width="{width}" stroke-linejoin="round" marker-start="url(#dot)" marker-end="url(#dot)"/>')
        if label:
            x, y = pts[at]
            o.append(f'<text x="{x + dx}" y="{y + dy}" font-size="11" fill="{c}">{label}</text>')

    def fuse(x, y, label):
        o.append(f'<rect x="{x - 14}" y="{y - 7}" width="28" height="14" rx="3" fill="#ffe08a" stroke="#8a6d00"/>')
        o.append(f'<text x="{x - 12}" y="{y + 4}" font-size="9">{label}</text>')

    # the battery drawer
    box(20, 70, 210, 210, 'Battery bay (belly)', ['two DeWalt DCB609, 20 V mode', 'on two Terrafirma rail adapters', 'in series (W2: an XT90 link)',
                                                   '10S3P, 30-41 V, 360 Wh rated', 'no BMS the robot can read:', 'the firmware cuts off at 30 V', '',
                                                   'XT90-S female on the bay\'s lead'], fill='#fff7e6')
    box(20, 300, 210, 80, 'Charging', ['the packs come out and charge', 'on DeWalt\'s own chargers', '(no charge port, D65)'], fill='#fff7e6')
    # main path parts
    box(290, 70, 170, 60, 'MRBF main fuse', ['Blue Sea 5191 + 5181 80 A', '58 V DC, 2 kA'], fill='#ffe08a')
    box(290, 160, 170, 60, 'Shunt 150 A / 50 mV', ['Blue Sea, in the + lead (W5, W6)', 'INA228 high side (W30-31)'])
    box(290, 290, 170, 70, 'Main switch', ['Flipsky Smart Enhanced V2.0', 'low side, momentary', '(16 mm button, rear face)'], fill='#e8f0ff')
    # bus bars
    box(520, 70, 60, 330, '+ bus', ['C110', '5 x M6'], fill='#fde3e3')
    box(520, 420, 60, 120, '- bus', ['C110', 'star', 'point'], fill='#e6e6e6')
    # wires of the main path
    wire([(230, 100), (290, 100)], 'red', 'W1 W4 10/8', 0, 4, -8)
    wire([(375, 130), (375, 160)], 'red', 'W5 8', 0, 6, 18)
    wire([(460, 190), (490, 190), (490, 100), (520, 100)], 'red', 'W6 8', 1, 4, -6)
    wire([(230, 250), (260, 250), (260, 320), (290, 320)], 'black', 'W3 W7 10/8', 0, 4, 16)
    wire([(460, 330), (500, 330), (500, 480), (520, 480)], 'black', 'W8 8', 1, 4, -4)
    # branches
    loads = [('RS-04 L front', 'XT60H', 20, 14, 'W10'), ('RS-04 L rear', 'XT60H', 20, 14, 'W11'), ('RS-04 R front', 'XT60H', 20, 14, 'W12'),
             ('RS-04 R rear', 'XT60H', 20, 14, 'W13'), ('VESC left (75100)', 'XT60H', 30, 12, 'W14'), ('VESC right (75100)', 'XT60H', 30, 12, 'W15'),
             ('TRACO TEP 150-4812WI in', 'ferrules', 10, 18, 'W16'), ('Turret (stop relay B, XT30)', 'XT30', 7.5, 16, 'W22')]
    for i, (name, conn, amps, awg, wid) in enumerate(loads):
        y = 95 + 38 * i
        wire([(580, y), (700, y)], 'red', f'{wid} {awg} AWG', 0, 30, -5, width=2.2)
        fuse(640, y, f'{amps} A')
        box(700, y - 15, 170, 30, name, [], fill='#eef7ee')
    wire([(580, 500), (680, 500), (680, 95)], 'black', '', 0, width=2.2)
    o.append('<text x="688" y="440" font-size="11" fill="#222">W18-W20: each load\'s - back to the - bus</text>')
    # 12 V
    box(930, 340, 170, 60, 'TRACO 12 V out', ['12 V 12.5 A, isolated', '-V tied to the star (W23)'], fill='#eef7ee')
    box(1180, 300, 130, 30, 'J501 DC-IN', [], fill='#e8f0ff')
    wire([(1100, 355), (1125, 355), (1125, 315), (1180, 315)], 'red', 'W21 16', 2, 18, -5, width=2)
    fuse(1125, 335, '10 A')
    box(1180, 380, 150, 30, 'Lidar box (VLP-16)', [], fill='#e8f0ff')
    box(1180, 420, 150, 30, '5 V buck D36V28F5', [], fill='#e8f0ff')
    box(1180, 460, 150, 30, 'Radio-stop jack, lights', [], fill='#e8f0ff')
    wire([(1100, 385), (1140, 385), (1140, 395), (1180, 395)], 'red', 'W43 W24 16', 0, 4, -5, width=2)
    fuse(1140, 410, '7.5 A')
    wire([(1140, 420), (1140, 435), (1180, 435)], 'red', 'W25 22', 1, 8, 14, width=1.6)
    wire([(1140, 435), (1140, 475), (1180, 475)], 'red', 'W26 22', 1, 8, 14, width=1.6)
    wire([(870, 323), (900, 323), (900, 370), (930, 370)], 'orange', '', 0, width=2)
    wire([(580, 525), (1015, 525), (1015, 400)], 'black', 'W23: the converter\'s -V to the star point', 0, 160, 16, width=2)
    wire([(550, 540), (550, 590)], 'green', 'W33 frame bond 14 AWG', 1, 8, 0, width=2)
    # 5 V and control
    box(20, 600, 330, 140, 'MCU board (on the power plate)', ['Nucleo-G474RE: FDCAN1/2/3 = buses A/B/C', 'CAN Pal x 3 (120 Ohm on: the bus ends)',
                                                              'INA228 on I2C: pack V and I, high side (W30-32)',
                                                              'the cut-off, current limit, regen clamp (D65)', 'STOP loop in (radio relay, closed = run)', '5 V from the buck (W28-29)'], fill='#e8f0ff')
    yy = 600
    for k, (bus, master, nodes, note) in enumerate(CAN):
        y = yy + 36 * k
        o.append(f'<text x="380" y="{y + 14}" font-size="12" font-weight="bold" fill="#1f5fbf">CAN {bus}</text>')
        o.append(f'<line x1="430" y1="{y + 10}" x2="1380" y2="{y + 10}" stroke="#1f5fbf" stroke-width="2" stroke-dasharray="6 3"/>')
        txt = f'{master} → ' + ' → '.join(nodes) + f'  ({note})'
        o.append(f'<text x="436" y="{y + 26}" font-size="11" fill="#1f5fbf">{txt[:150]}</text>')
        if len(txt) > 150:
            o.append(f'<text x="436" y="{y + 39}" font-size="11" fill="#1f5fbf">{txt[150:]}</text>')
    words, line, ys = STOP.split(), '', 800
    for w_ in words:
        if len(line) + len(w_) > 190:
            o.append(f'<text x="20" y="{ys}" font-size="11" fill="#333">{line}</text>')
            line, ys = '', ys + 15
        line += w_ + ' '
    o.append(f'<text x="20" y="{ys}" font-size="11" fill="#333">{line}</text>')
    o.append('<text x="20" y="850" font-size="11" fill="#333">Fuses: Littelfuse MINI 58V (0997) in inline holders rated 32 V: the fuse interrupts (1 kA at 58 V); label every holder '
             '"58 V fuses only" and pull a fuse only with the pack unplugged.</text>')
    o.append('<text x="20" y="870" font-size="11" fill="#333">Twist every CAN pair (22 AWG); keep the shunt\'s sense pair away from the 10 AWG runs; '
             'crimp, never solder-tin, a wire that goes into a screw terminal (ferrules).</text>')
    o.append('</svg>')
    return '\n'.join(o)


DOC = R / 'docs' / 'body-electrical.md'
TABLE_HEAD = '| Wire | From | To | AWG | Colour | Ends | Fuse | Why |'


def write_doc_table(rows, doc=DOC):
    """docs/body-electrical.md section 3.1's table, rewritten from WIRES (the rows between its header and the next
    blank line), so the page and this list cannot disagree."""
    lines = doc.read_text().split('\n')
    i = lines.index(TABLE_HEAD)
    j = i + 2
    while j < len(lines) and lines[j].startswith('|'):
        j += 1
    body = [f"| {r['id']} | {r['from']} | {r['to']} | {r['awg']} | {r['colour']} | {r['termination']} | {r['fuse']} | {r['why']} |" for r in rows]
    doc.write_text('\n'.join(lines[:i + 2] + body + lines[j:]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [dict(zip(('id', 'from', 'to', 'awg', 'colour', 'termination', 'fuse', 'why'), w)) for w in WIRES]
    (OUT / 'wiring.json').write_text(json.dumps({'pack': PACK, 'wires': rows, 'can': [dict(zip(('bus', 'master', 'nodes', 'note'), c)) for c in CAN],
                                                 'stop': STOP}, indent=1) + '\n')
    (OUT / 'wiring.svg').write_text(svg())
    write_doc_table(rows)
    print(f'exports/body/wiring.json ({len(rows)} wires), exports/body/wiring.svg, docs/body-electrical.md 3.1')


if __name__ == '__main__':
    main()
