"""The leg rig's wiring: one diagram a person builds from (exports/rig/wiring.svg) and the wire list behind it
(exports/rig/wiring.json), both from the table below. docs/leg-rig-wiring.md explains them.

    .venv/bin/python tools/rig_wiring.py
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'rig'

# blocks: name -> (x, y, w, h, title, lines)
BLOCKS = {
    'pack': (20, 40, 170, 70, 'FLEXVOLT DCB609 (60 V mode)', ['15S, 54 V nom, 60 V full', 'dock adapter, 12 AWG leads', 'XT60H female on its lead']),
    'fuse': (260, 40, 150, 70, 'Class CC fuse 30 A', ['Littelfuse KLDR030', 'in LPSC0001Z (DIN)', '300 VDC']),
    'cont': (470, 40, 170, 70, 'Contactor (hold-to-run)', ['TE LEV100A4ANG', '+ terminal to the fuse', '12 V coil, 0.36 A']),
    'motors': (720, 30, 200, 90, 'RS-04 x 2 (ids 1, 2)', ['XT30 Y-splice on the carriage', 'XT30UW-F leads, 310 mm', 'CAN on GH1.25-2P plugs']),
    'dcdc': (260, 170, 150, 70, '12 V rail', ['Mean Well DDR-30L-12', '18-75 V in, 12 V 2.5 A', 'input fuse 5 A (5x20, DC)']),
    'timer': (470, 170, 170, 80, 'Off-delay relay', ['ProSense T2R-M1-ADJ-240U', 'OFF DELAY, 1.0 s (DIP A off, B on;', 'C, D on: 0.1-10 s; E, F on: knob)']),
    'pendant': (470, 300, 170, 60, 'Pendant (hold to run)', ['AbleNet Specs IC, N.O.', '3.5 mm jack on the pod']),
    'node': (720, 250, 200, 120, 'Rig node: Feather M4 CAN', ['D5: pendant (10k / 2.2k divider)', 'A2: VBUS (100k / 4.7k)', 'I2C: VL53L1X (STEMMA QT)',
                                                              'D6, D9: HX711 (load plate)', 'USB-C: laptop (power, log)']),
    'u2c': (980, 250, 160, 70, 'USB-CAN: BTT U2C V2.1', ['candleLight -> SocketCAN', '120 ohm jumper ON (bus end)']),
    'laptop': (980, 380, 160, 60, 'Laptop', ['python -m rig.run', 'can0 at 1 Mbit/s']),
    'junction': (980, 120, 160, 80, 'CAN junction (carriage)', ['FeatherWing Proto', '2 x JST GH 2-pin headers', '120 ohm H-L (bus end)']),
}
# wires: (from, to, what, gauge, colour, length_m, ends)
WIRES = [
    ('pack', 'fuse', 'pack +', '12 AWG', '#d33', 0.6, 'adapter + -> XT60H (F) -> pod inlet XT60E-M + -> fuse holder line'),
    ('fuse', 'cont', 'fused +', '12 AWG', '#d33', 0.15, 'fuse holder load -> contactor + terminal (M5, 4 N m)'),
    ('cont', 'motors', 'switched +', '12 AWG', '#d33', 1.6, 'contactor - terminal -> pod outlet XT60E-F + -> service loop -> Y-splice + -> 2 x XT30 (M) +'),
    ('pack', 'motors', 'pack -', '12 AWG', '#222', 1.9, 'adapter - -> XT60 - -> pod outlet - -> service loop -> Y-splice - -> 2 x XT30 (M) -'),
    ('fuse', 'dcdc', 'fused + to the 12 V rail', '18 AWG', '#d33', 0.2, 'fuse holder load -> panel 5x20 holder -> DDR-30L-12 +Vin; -Vin to pack -'),
    ('dcdc', 'timer', '+12 V supply', '22 AWG', '#e80', 0.2, 'DDR +Vo -> T2R supply + (and its relay common, a jumper); -Vo -> T2R supply -'),
    ('timer', 'cont', 'coil', '22 AWG', '#e80', 0.15, 'T2R N.O. contact -> contactor coil + (flying lead); coil - -> 0 V; 1N4001 across the coil, cathode to +'),
    ('dcdc', 'pendant', '+12 V to the pendant', '22 AWG', '#e80', 0.2, 'DDR +Vo -> 3.5 mm jack tip'),
    ('pendant', 'timer', 'trigger', '22 AWG', '#e80', 0.2, 'jack sleeve -> T2R pin 5 (trigger: the switch between pin 5 and input +, the insert\'s Fig. D)'),
    ('pendant', 'node', 'pendant sense', '22 AWG', '#e80', 0.2, 'jack sleeve -> 10k -> Feather D5 -> 2.2k -> GND (12 V reads 2.2 V)'),
    ('cont', 'node', 'VBUS sense', '22 AWG', '#d33', 0.2, 'contactor - terminal -> 100k -> Feather A2 -> 4.7k -> GND (60 V reads 2.7 V)'),
    ('u2c', 'node', 'CAN (pod)', 'twisted pair + GND', '#36c', 0.3, 'U2C H, L, GND -> Feather CAN terminal H, L, G'),
    ('node', 'junction', 'CAN trunk', 'Quabbin Q0357-1, shield at the pod end', '#36c', 1.6, 'Feather H, L, G -> service loop -> junction H, L, GND'),
    ('junction', 'motors', 'CAN stubs', 'motor leads (GH1.25)', '#36c', 0.35, 'junction GH headers -> each motor\'s GH plug (blue CAN_H, brown CAN_L)'),
    ('laptop', 'u2c', 'USB', 'USB-C', '#888', 1.0, 'laptop -> U2C'),
    ('laptop', 'node', 'USB', 'USB-C', '#888', 1.0, 'laptop -> Feather (power and its log)'),
]


def svg() -> str:
    W, H = 1180, 540
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Arial, sans-serif">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<text x="20" y="24" font-size="16" font-weight="bold" fill="#142b38">Gyropup leg rig: power, hold-to-run and CAN</text>']
    centre = {k: (x + w / 2, y + h / 2) for k, (x, y, w, h, *_ ) in BLOCKS.items()}
    offset = {'pack -': 14, 'VBUS sense': 0, 'CAN stubs': -20, 'USB': 0}
    for a, b, what, gauge, col, L, ends in WIRES:
        (x1, y1), (x2, y2) = centre[a], centre[b]
        dy = offset.get(what, 0)
        y1, y2 = y1 + dy, y2 + dy
        mx = (x1 + x2) / 2
        out.append(f'<path d="M{x1:.0f},{y1:.0f} L{mx:.0f},{y1:.0f} L{mx:.0f},{y2:.0f} L{x2:.0f},{y2:.0f}" fill="none" stroke="{col}" '
                   f'stroke-width="{3 if "12 AWG" in gauge else 1.6}" opacity="0.8"/>')
        out.append(f'<text x="{mx + 4:.0f}" y="{(y1 + y2) / 2 - 3:.0f}" font-size="9" fill="{col}">{what} ({gauge})</text>')
    for k, (x, y, w, h, title, lines) in BLOCKS.items():
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#f4f6f8" stroke="#142b38" stroke-width="1.2"/>')
        out.append(f'<text x="{x + 8}" y="{y + 16}" font-size="11" font-weight="bold" fill="#142b38">{title}</text>')
        for i, t in enumerate(lines):
            out.append(f'<text x="{x + 8}" y="{y + 31 + 12 * i}" font-size="9.5" fill="#333">{t}</text>')
    out.append('<text x="20" y="525" font-size="10" fill="#555">Red: the motors\' bus (12 AWG pack side). Orange: the 12 V hold-to-run loop. '
               'Blue: CAN at 1 Mbit/s, 120 ohm at the U2C and at the junction. Grounds meet at the pack\'s negative (the pod\'s inlet).</text>')
    out.append('</svg>')
    return '\n'.join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'wiring.svg').write_text(svg())
    (OUT / 'wiring.json').write_text(json.dumps({'blocks': {k: {'title': v[4], 'notes': v[5]} for k, v in BLOCKS.items()},
                                                 'wires': [dict(zip(('from', 'to', 'what', 'gauge', 'colour', 'length_m', 'ends'), w)) for w in WIRES]},
                                                indent=1) + '\n')
    print(f'{len(WIRES)} wires -> exports/rig/wiring.svg, wiring.json')


if __name__ == '__main__':
    main()
