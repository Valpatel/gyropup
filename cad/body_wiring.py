"""The body's power and CAN wiring (milestone M5, P0 power skid): one wire list and the diagram drawn from it.

    .venv/bin/python cad/body_wiring.py      # -> exports/body/wiring.json, exports/body/wiring.svg

The wire list is the build sheet: every run with its two ends, gauge, colour, connector, the fuse that protects it and
why that size. docs/body-electrical.md explains the system; this file is what the drawing and the table are made from,
so they cannot disagree.

The system (D43, D47-D50): a 13S2P Molicel P30B brick (48.1 V nominal, 53.3 V charged at 4.10 V a cell, 39 V empty)
with a Daly K 13S 100 A BMS on its negative side; an XT90-S plug; the 80 A MRBF main fuse on the + lead; the 150 A /
50 mV shunt then the anti-spark main switch on the - lead (low side, as Flipsky draws it: verify on the card that
comes with it); two C110 bus bars; Littelfuse MINI 58V fuses in inline holders to every branch; isolated Mean Well
converters for 24 V (the J501, the turret) and 12 V (the lidar box, the 5 V buck, the radio stop); the charge port
straight to the pack (fused), so it charges with the robot off.
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'body'

PACK = {'cells': '13S2P Molicel INR-18650-P30B (26 cells)', 'v_nom': 48.1, 'v_full': 53.3, 'v_full_per_cell': 4.10, 'v_empty': 39.0,
        'ah': 6.0, 'wh_at_4v10': 256, 'peak_a': 80, 'cont_a': 72, 'bms': 'Daly K 13S 100 A, BT + UART, common port (B-/P-)',
        'bms_settings': {'cell_ovp_v': 4.15, 'cell_ovp_release_v': 4.10, 'cell_uvp_v': 3.00, 'cell_uvp_release_v': 3.20,
                         'charge_ocp_a': 6, 'discharge_ocp_a': 100, 'charge_temp_c': [0, 45], 'discharge_temp_c': [-10, 60],
                         'balance_start_v': 3.90, 'balance_delta_mv': 15}}

# (id, from, to, AWG, colour, connector/termination, fuse, why)
WIRES = [
    # ---- the pack and the main path
    ('W1', 'pack B+ (group 13 +)', 'XT90-S female (pack lead)', 8, 'red', 'XT90-S solder cup', 'MRBF 80 A (on the robot side)', '80 A pulses, 72 A cells'),
    ('W2', 'BMS P-', 'XT90-S female (pack lead)', 8, 'black', 'XT90-S solder cup', '-', 'the BMS switches the negative'),
    ('W3', 'XT90-S male (robot)', 'MRBF block, battery stud (M8)', 8, 'red', 'lug M8', '-', 'unfused until the MRBF: keep it short (<150 mm)'),
    ('W4', 'MRBF block, load stud (M8)', '+ bus bar, tap 1 (M6)', 8, 'red', 'lugs M8 / M6', 'MRBF 80 A', 'the whole robot'),
    ('W5', 'XT90-S male (robot)', 'shunt, battery side (M8)', 8, 'black', 'lug M8', '-', 'the battery negative'),
    ('W6', 'shunt, load side (M8)', 'main switch IN- (B-)', 8, 'black', 'ferrule / its lead', '-', 'Flipsky draws the switch on the negative: check its card'),
    ('W7', 'main switch OUT- (P-)', '- bus bar, tap 1 (M6)', 8, 'black', 'lug M6', '-', 'the switched negative: everything below is off with it'),
    # ---- the charge port (charges with the switch off; the shunt sees the charge current)
    ('W8', 'charge port XT60H-F +', 'MRBF block, battery stud (M8)', 18, 'red', 'XT60 / lug M8', 'MINI 58V 10 A (inline, at the stud)', 'charger 2-3 A; the fuse guards the lead against a pack short'),
    ('W9', 'charge port XT60H-F -', 'shunt, load side (M8)', 18, 'black', 'XT60 / lug M8', '-', 'after the shunt (it counts the charge), before the switch (the robot can be off)'),
    # ---- the 48 V branches from the bus bars
    ('W10', '+ bus tap 2', 'RS-04 left front (XT60H)', 14, 'red', 'lug M6 / XT60H-M', 'MINI 58V 20 A', '~12 A at a jump, 25 A peaks: 14 AWG silicone'),
    ('W11', '+ bus tap 2', 'RS-04 left rear (XT60H)', 14, 'red', 'lug M6 / XT60H-M', 'MINI 58V 20 A', 'as W10 (two lugs share the tap)'),
    ('W12', '+ bus tap 3', 'RS-04 right front (XT60H)', 14, 'red', 'lug M6 / XT60H-M', 'MINI 58V 20 A', 'as W10'),
    ('W13', '+ bus tap 3', 'RS-04 right rear (XT60H)', 14, 'red', 'lug M6 / XT60H-M', 'MINI 58V 20 A', 'as W10'),
    ('W14', '+ bus tap 4', 'VESC left (Flipsky 75100) +', 12, 'red', 'lug M6 / XT60H-M', 'MINI 58V 30 A', 'the wheel: firmware limits it to 25 A'),
    ('W15', '+ bus tap 4', 'VESC right +', 12, 'red', 'lug M6 / XT60H-M', 'MINI 58V 30 A', 'as W14'),
    ('W16', '+ bus tap 5', 'DDR-120C-24 Vin+', 18, 'red', 'lug M6 / ferrule', 'MINI 58V 10 A', '120 W out: 3.3 A in at 40 V, plus its inrush'),
    ('W17', '+ bus tap 5', 'DDR-60L-12 Vin+', 18, 'red', 'lug M6 / ferrule', 'MINI 58V 5 A', '60 W out: 1.7 A in at 40 V'),
    ('W18', '- bus taps 2-3', 'RS-04 x 4 (XT60H)', 14, 'black', 'lug M6 / XT60H-M', '-', 'returns, one per motor'),
    ('W19', '- bus tap 4', 'VESC left, right -', 12, 'black', 'lug M6 / XT60H-M', '-', 'returns'),
    ('W20', '- bus tap 5', 'DDR-120C-24 Vin-, DDR-60L-12 Vin-', 18, 'black', 'lug M6 / ferrule', '-', 'returns'),
    # ---- 24 V (isolated; its - tied to the - bus at the star point)
    ('W21', 'DDR-120C-24 +V', 'J501 DC-IN (XT30)', 18, 'red', 'ferrule / XT30-M', 'MINI 5 A', 'the J501: 60 W peak, 2.5 A'),
    ('W22', 'DDR-120C-24 +V', 'stop relay, pole B (in)', 18, 'red', 'ferrule / screw terminal', 'MINI 5 A', 'the turret\'s branch: 60 W peaks (its own fuse stays in the turret too)'),
    ('W23', 'DDR-120C-24 -V', 'J501 and turret returns; star point', 18, 'black', 'ferrule / XT30-M', '-', 'one tie from -V to the - bus (the CAN reference)'),
    # ---- 12 V (isolated; its - to the star point)
    ('W24', 'DDR-60L-12 +V', 'lidar interface box (XT30)', 18, 'red', 'ferrule / XT30-M', '(the converter\'s 5 A limit)', 'VLP-16: 8 W, 3 A at spin-up'),
    ('W25', 'DDR-60L-12 +V', '5 V buck VIN (Pololu D36V28F5)', 22, 'red', 'ferrule / solder', '(the converter\'s 5 A limit)', '~0.6 A at 12 V'),
    ('W26', 'DDR-60L-12 +V', 'radio-stop jack pin 3 (+12 V)', 22, 'red', 'ferrule / jack', '(the converter\'s 5 A limit)', 'D37: the jack offers 12 V'),
    ('W27', 'DDR-60L-12 -V', 'lidar box, buck, jack GND; star point', 18, 'black', 'ferrule', '-', 'one tie to the - bus'),
    # ---- 5 V
    ('W28', '5 V buck VOUT', 'Nucleo E5V, 4 CAN Pal, QT Py 5V, VN-100, radio receiver', 22, 'red', 'solder / GH', '(the buck\'s 3.2 A limit)', '~1 A in all'),
    ('W29', '5 V buck GND', 'the same, GND', 22, 'black', 'solder / GH', '-', ''),
    # ---- measurement and protection
    ('W30', 'shunt sense + (battery side screw)', 'INA228 IN+', 22, 'white', 'ring / screw terminal', '-', 'Kelvin pair, twisted, away from the 10 AWG'),
    ('W31', 'shunt sense - (load side screw)', 'INA228 IN-', 22, 'white', 'ring / screw terminal', '-', 'the INA228\'s own 15 mOhm shunt is removed'),
    ('W32', '+ bus (via the DDR-60L tap)', 'INA228 VBUS', 22, 'red', 'ring', 'MINI 58V 5 A (shared with W17)', 'pack voltage, 85 V input'),
    ('W33', 'frame (a tray PEM stud)', '- bus star point', 18, 'green', 'ring M5 / lug M6', '-', 'a + short to the frame blows a fuse, not leaves it live'),
    # ---- the turret's TM connector (DT06-12SA on the body's harness; docs/turret-wiring.md 1.1)
    ('W34', 'stop relay, pole B (out)', 'DT06-12SA pins 1, 2', 18, 'red', 'size-16 sockets', 'MINI 5 A (W22)', 'two pins in parallel, as the turret asks; dead whenever the stop relay is open'),
    ('W35', 'W23 (24 V return)', 'DT06-12SA pins 3, 4', 18, 'black', 'size-16 sockets', '-', ''),
    ('W36', 'J501 can1 (H, L)', 'DT06-12SA pins 5, 6', 22, 'white', 'twisted pair, size-16 sockets', '-', 'the turret terminates its end; the J501 its own'),
    ('W37', 'stop relay, pole A (closed = run)', 'DT12 pins 7, 8 (SAFETY_A, SAFETY_B)', 22, 'white', 'twisted pair', '-',
     'the turret\'s dry safety loop (12 V at 2 mA; D41 D7: it cuts the flywheels and the dial in hardware)'),
    ('W38', 'stop relay coil, + side', 'MCU STOP sense (divider 12 V to 3.3 V)', 22, 'white', 'GH', '-',
     '12 V on the coil = the radio says run: the MCU sits the robot down when it drops (D37)'),
    ('W39', '12 V rail via the RC switch\'s contact', 'stop relay coil, + side', 22, 'red', 'solder / screw terminal', '(the converter\'s 5 A limit)',
     'the coil (12 V, 33 mA) is fed only while the radio says run; its - side through the MCU\'s MOSFET (MCU_RUN), a diode across it'),
]

CAN = [
    ('A', 'MCU FDCAN1 (CAN Pal 1, 120 Ohm on)', ['RS-04 left front', 'RS-04 left rear (120 Ohm at its plug)'], '1 Mbit/s, the left leg'),
    ('B', 'MCU FDCAN2 (CAN Pal 2, 120 Ohm on)', ['RS-04 right front', 'RS-04 right rear (120 Ohm at its plug)'], '1 Mbit/s, the right leg'),
    ('C', 'MCU FDCAN3 (CAN Pal 3, 120 Ohm on)', ['VESC left', 'VESC right', 'QT Py ESP32-S3 (CAN Pal 4, off): the BMS over Bluetooth',
                                                 'J501 can0 (its own 120 Ohm on)'], '1 Mbit/s: wheels, battery, the computer'),
    ('T', 'J501 can1', ['the turret (its own bus)'], 'the turret workstream\'s'),
]

STOP = ('The radio stop (D37, D48): the ER3C-i receiver (failsafe: no pulses) drives one Pololu RC relay switch; its contact feeds '
        'the coil of the stop relay (Omron G2RL-2, DPDT, 12 V), whose other end goes to ground through the MCU\'s MOSFET. The relay '
        'holds only while the radio says run AND the MCU says run. Pole A is the turret\'s dry safety loop (TM pins 7, 8: the turret '
        'cuts its flywheels and dial in 20 ms), pole B is in the turret\'s 24 V branch (the independent cut); the MCU senses the coil '
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
         f'<text x="20" y="46" fill="#555">13S2P P30B, {PACK["v_nom"]} V nominal, {PACK["v_full"]} V full ({PACK["v_full_per_cell"]} V a cell). '
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
    box(20, 70, 210, 210, 'Battery drawer (belly)', ['13S2P P30B brick, 256 Wh', 'Daly K 13S 100 A BMS', '(common port: B- in, P- out)',
                                                     'BMS on Bluetooth only:', 'no wire to its UART (B- ground)', '', 'XT90-S anti-spark plug',
                                                     'female on the pack lead'], fill='#fff7e6')
    box(20, 300, 210, 80, 'Charge port (belly)', ['XT60H female in a printed bezel', 'charger 53.3 V (90 %), 2-3 A', 'charges with the switch off'], fill='#fff7e6')
    # main path parts
    box(290, 70, 170, 60, 'MRBF main fuse', ['Blue Sea 5191 + 5181 80 A', '58 V DC, 2 kA'], fill='#ffe08a')
    box(290, 200, 170, 60, 'Shunt 150 A / 50 mV', ['Blue Sea, in the - lead', 'INA228 across it (W30-31)'])
    box(290, 290, 170, 70, 'Main switch', ['Flipsky Smart Enhanced V2.0', 'low side, momentary', '(16 mm button, belly)'], fill='#e8f0ff')
    # bus bars
    box(520, 70, 60, 330, '+ bus', ['C110', '5 x M6'], fill='#fde3e3')
    box(520, 420, 60, 120, '- bus', ['C110', 'star', 'point'], fill='#e6e6e6')
    # wires of the main path
    wire([(230, 100), (290, 100)], 'red', 'W1 W3 8', 0, 4, -8)
    wire([(460, 100), (520, 100)], 'red', 'W4 8', 0, 4, -6)
    wire([(230, 250), (290, 250)], 'black', 'W2 W5 8', 0, 4, 16)
    wire([(375, 260), (375, 290)], 'black', 'W6', 0, 6, 18)
    wire([(460, 330), (500, 330), (500, 480), (520, 480)], 'black', 'W7 8', 1, 4, -4)
    wire([(230, 330), (262, 330), (262, 145), (330, 145), (330, 130)], 'red', 'W8 18 AWG (charge +)', 2, 4, 14)
    fuse(262, 230, '10 A')
    wire([(230, 360), (275, 360), (275, 268), (300, 268), (300, 260)], 'black', 'W9 18 (charge -)', 0, 4, 14, width=2)
    # branches
    loads = [('RS-04 L front', 'XT60H', 20, 14, 'W10'), ('RS-04 L rear', 'XT60H', 20, 14, 'W11'), ('RS-04 R front', 'XT60H', 20, 14, 'W12'),
             ('RS-04 R rear', 'XT60H', 20, 14, 'W13'), ('VESC left (75100)', 'XT60H', 30, 12, 'W14'), ('VESC right (75100)', 'XT60H', 30, 12, 'W15'),
             ('DDR-120C-24 in', 'ferrules', 10, 18, 'W16'), ('DDR-60L-12 in', 'ferrules', 5, 18, 'W17')]
    for i, (name, conn, amps, awg, wid) in enumerate(loads):
        y = 95 + 38 * i
        wire([(580, y), (700, y)], 'red', f'{wid} {awg} AWG', 0, 30, -5, width=2.2)
        fuse(640, y, f'{amps} A')
        box(700, y - 15, 170, 30, name, [], fill='#eef7ee')
    wire([(580, 500), (680, 500), (680, 95)], 'black', '', 0, width=2.2)
    o.append('<text x="688" y="440" font-size="11" fill="#222">W18-W20: each load\'s - back to the - bus</text>')
    # 24 V and 12 V
    box(930, 300, 170, 60, 'DDR-120C-24 out', ['24 V 5 A, isolated', '-V tied to the star (W23)'], fill='#eef7ee')
    box(930, 400, 170, 60, 'DDR-60L-12 out', ['12 V 5 A, isolated', '-V tied to the star (W27)'], fill='#eef7ee')
    box(1180, 270, 130, 30, 'J501 DC-IN', [], fill='#e8f0ff')
    box(1180, 320, 130, 30, 'Turret', [], fill='#e8f0ff')
    wire([(1100, 315), (1125, 315), (1125, 285), (1180, 285)], 'red', 'W21 18', 2, 18, -5, width=2)
    fuse(1125, 300, '5 A')
    wire([(1100, 340), (1180, 335)], 'red', 'W22 W34 18 (via the stop relay)', 0, 6, 16, width=2)
    fuse(1132, 337, '5 A')
    box(1180, 380, 150, 30, 'Lidar box (VLP-16)', [], fill='#e8f0ff')
    box(1180, 420, 150, 30, '5 V buck D36V28F5', [], fill='#e8f0ff')
    box(1180, 460, 150, 30, 'Radio-stop jack', [], fill='#e8f0ff')
    wire([(1100, 420), (1130, 420), (1130, 395), (1180, 395)], 'red', 'W24 18', 2, 8, -5, width=2)
    wire([(1100, 430), (1180, 435)], 'red', 'W25 22', 0, 14, 16, width=1.6)
    wire([(1100, 445), (1120, 445), (1120, 475), (1180, 475)], 'red', 'W26 22', 2, 8, 16, width=1.6)
    wire([(870, 323), (900, 323), (900, 330), (930, 330)], 'orange', '', 0, width=2)
    wire([(870, 361), (890, 361), (890, 430), (930, 430)], 'orange', '', 0, width=2)

    wire([(580, 525), (1015, 525), (1015, 460)], 'black', 'W23 W27: each converter\'s -V to the star point', 0, 160, 16, width=2)
    wire([(550, 540), (550, 590)], 'green', 'W33 frame bond 18 AWG', 1, 8, 0, width=2)
    # 5 V and control
    box(20, 600, 330, 140, 'MCU board (on the power plate)', ['Nucleo-G474RE: FDCAN1/2/3 = buses A/B/C', 'CAN Pal x 3 (120 Ohm on: the bus ends)',
                                                              'INA228 on I2C: pack V and I (W30-32)', 'QT Py ESP32-S3 + CAN Pal 4 on bus C:',
                                                              '  the BMS over Bluetooth', 'STOP loop in (radio relay, closed = run)', '5 V from the buck (W28-29)'], fill='#e8f0ff')
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [dict(zip(('id', 'from', 'to', 'awg', 'colour', 'termination', 'fuse', 'why'), w)) for w in WIRES]
    (OUT / 'wiring.json').write_text(json.dumps({'pack': PACK, 'wires': rows, 'can': [dict(zip(('bus', 'master', 'nodes', 'note'), c)) for c in CAN],
                                                 'stop': STOP}, indent=1) + '\n')
    (OUT / 'wiring.svg').write_text(svg())
    print(f'exports/body/wiring.json ({len(rows)} wires), exports/body/wiring.svg')


if __name__ == '__main__':
    main()
