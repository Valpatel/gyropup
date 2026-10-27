"""The turret's assembly order, step by step, with a picture of each step from the CAD.

    .venv/bin/python cad/turret_assembly.py

Each step adds parts to what is already built: the new parts in colour, lifted along the way they go in (an exploded
view of that step), the parts already fitted in grey. Writes exports/turret/assembly/step-NN.png, steps.json and the
written order, docs/turret-assembly.md (every fastener's part number is in exports/turret/bench/bom.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402

OUT = R / 'exports' / 'turret' / 'assembly'
GREY = (0.78, 0.79, 0.81)

# (title, parts added, how far each lifts in the picture (mm, along +z unless a vector), view, what holds it)
STEPS = [
    ('The pan base and its inserts', ['pan_base'], {}, (0.6, -1.0, 0.7),
     'Heat-set inserts first, with the base on its foot: 5 x M3 in the clamp ears, 3 x M3 in the carrier bosses (from '
     'below), 4 x M3 in the base-board bosses, 4 x M4 in the DT pad, 5 short M3 in the bumper tabs.'),
    ('The pan servo, its pinion and the DT12 receptacle', ['pan_servo', 'pan_pinion', 'dt_receptacle'],
     {'pan_servo': 40, 'pan_pinion': 70, 'dt_receptacle': (0, -40, 0)}, (0.6, -1.0, 0.7),
     'The STS3215 drops into its pocket, bus plugs down, on its four posts: 4 x M2 x 20 up through the foot. The pinion on '
     'its horn: 4 x M3 x 16 (heads sunk). The DT04-12PA on the pad: 4 x M4 x 10; its 12 pins and the W12P wedge with the '
     'harness to the base board.'),
    ('The base board and the index magnet', ['base_board', 'index_magnet'], {'base_board': (25, 0, 0), 'index_magnet': 25},
     (0.8, -0.6, 0.7),
     'The base board (the 555, the 12 V pan regulator, the 10 A main fuse, the ring\'s stator plug) on its four bosses: '
     '4 x M3 x 6. The 3/16 in magnet glued on the housing\'s top at pan 0 (the clamp ring has its hole).'),
    ('The pan bearing and its clamp', ['pan_bearing', 'pan_bearing_inner', 'pan_clamp'],
     {'pan_bearing': 30, 'pan_bearing_inner': 30, 'pan_clamp': 50}, (0.6, -1.0, 0.8),
     'The 6810-2RS pressed into its seat onto the Ø62 shoulder; the aluminium clamp ring (SendCutSend) over it: 5 x M3 x 8.'),
    ('The turntable, its spacer and the circlip', ['pan_ring', 'hall_switch', 'pan_spacer', 'circlip_50'],
     {'pan_ring': 45, 'hall_switch': 45, 'pan_spacer': -45, 'circlip_50': -60}, (0.6, -1.0, 0.45),
     'Before it goes in: 4 x M4 inserts in its top, the hall switch glued in the pocket underneath (leads up its hole). '
     'Its journal down through the inner race, the gear in mesh with the pinion; from below, through the foot\'s Ø65 '
     'opening, the spacer and the DIN 471-50 circlip in its groove (circlip pliers).'),
    ('The ring driver and the slip ring on its carrier', ['ring_driver', 'slip_ring', 'slip_ring_rotor', 'ring_coupling', 'ring_carrier'],
     {'ring_driver': 60, 'slip_ring': -70, 'slip_ring_rotor': -70, 'ring_coupling': -70, 'ring_carrier': -70}, (0.6, -1.0, -0.35),
     'The driver pressed into the top of the turntable\'s bore (three crush ribs and a drop of CA). The ring screwed to '
     'its carrier (3 x M3 x 8 with washers), a 25 mm length of the 5/16 in tube on its rotor stub, its rotor leads '
     'gathered; from below, the ring goes up the bore, the tube into the driver\'s socket and the leads out through '
     'the driver\'s crescent; the carrier\'s tabs into their pockets: 3 x M3 x 10 flat heads.'),
    ('The tilt yoke and the turret-board bay', ['tilt_yoke', 'ring_leads_rotor', 'board_bay', 'turret_board'],
     {'tilt_yoke': 50, 'board_bay': (0, -40, 0), 'turret_board': (0, -70, 0)}, (0.5, -1.0, 0.5),
     'The rotor leads through the yoke\'s slot, the yoke on the turntable: 4 x M4 x 10. 4 x M3 inserts in the -y arm, the '
     'bay on them: 4 x M3 x 8 flat heads; the three boards on their standoffs (12 and 14 mm); the ring\'s rotor plug and '
     'the hall into level 2.'),
    ('The tilt servo and the cradle', ['tilt_servo', 'tilt_bearing', 'tilt_bearing_inner', 'cradle', 'shoulder_screw'],
     {'tilt_servo': (0, 40, 0), 'cradle': 40, 'shoulder_screw': (0, -40, 0)}, (0.5, -1.0, 0.5),
     'The STS3215 into its pocket on the +y arm, 4 x M2 x 10 from the arm\'s inner face. The MR126 into the -y arm\'s '
     'seat. The cradle: its hub onto the servo\'s horn (4 x M3 x 12), the ISO 7379 shoulder screw through the -y arm and '
     'the bearing into the cradle\'s M5 insert. Check the 0 and -25 deg stops by hand before anything else.'),
    ('The laser', ['laser_mount', 'laser'], {'laser_mount': -30, 'laser': -30}, (0.7, -1.0, 0.4),
     'The mount on the cradle\'s tab: 2 x M3 x 10 up through it; the laser in the mount on three nylon-tip M3 set screws '
     '(boresight them on the bench).'),
    ('The cartridge: feed motor, dial, ESCs and wheels', ['cartridge_body', 'feed_motor', 'feed_esc', 'dial', 'flywheel_motor_l', 'flywheel_motor_r',
                                                          'esc_l', 'esc_r', 'flywheel', 'flywheel_tyre'],
     {'feed_motor': -40, 'feed_esc': (-30, 0, 0), 'dial': 40, 'flywheel_motor_l': -30, 'flywheel_motor_r': -30, 'flywheel': -45, 'flywheel_tyre': -45},
     (0.6, -1.0, 0.6),
     'On the bench, not on the turret: the M2006 under the dial floor (3 x M3 x 6 flat), the dial on its D shaft (M3 x 8 '
     'and a washer from the top of the cone); the C610 on the base plate with two cable ties; the Snails up under the cage '
     'plate (4 x M3 x 6 each), each wheel on its bell (3 x M2 x 8 and two 1/16 in pins), the tyres stretched on (a drop of '
     'CA if they creep); the AM32 ESCs and the brake board on the plate.'),
    ('The barrel, the hopper and the lid', ['barrel', 'hopper', 'hopper_lid', 'hopper_flap'],
     {'barrel': (40, 0, 0), 'hopper': 40, 'hopper_lid': 70, 'hopper_flap': 80}, (0.6, -1.0, 0.6),
     'The barrel into its socket (a nylon-tip M3 set screw through the socket\'s insert), the gates\' emitters and '
     'receivers in its bosses; the hopper on the housing (3 x M3 x 8); the lid; the flap on its 2 mm pin and spring.'),
    ('The cartridge on the cradle, the bumper, the mount', ['ct_thumbscrew', 'bumper_ring'], {'ct_thumbscrew': -30, 'bumper_ring': -30},
     (0.6, -1.0, 0.5),
     'The cartridge down onto the cradle\'s two dowels, the knurled thumbscrew up into its insert (its O-ring keeps it in '
     'the rail); the two CT plugs (2 x 3 power, 2 x 6 signal). The bumper ring on its tabs: 5 x M3 x 20 and oversized '
     'washers. Then the turret on its stand or head ring: 2 x Ø5 dowels, 4 x M5 x 16, and the DT12 plug.'),
]


def main():
    from cadagent.render import Renderer
    OUT.mkdir(parents=True, exist_ok=True)
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
    P = T.posed(0.0, 0.0, robot=False)
    r = Renderer(OUT, size=(1400, 1000), subtitle='GYROPUP TURRET | ASSEMBLY')
    done, rows = [], []
    for k, (title, add, lift, view, how) in enumerate(STEPS, 1):
        missing = [n for n in add if n not in P]
        if missing:
            raise KeyError(f'step {k}: not in the CAD: {missing}')
        shapes = []
        for n in done:
            shapes += _items(n, P[n], GREY + (0.55,), None)
        for n in add:
            off = lift.get(n, 0)
            off = (0, 0, off) if isinstance(off, (int, float)) else off
            shapes += _items(n, P[n], tu.COL.get(n, (0.6, 0.6, 0.6)), off)
        f = f'step-{k:02d}.png'
        first = how.split('. ')[0].split(': ')[0]
        r.render(f, shapes=shapes, view=view, caption=f'{k}. {title}', note=(first[:120] + ' ...') if len(first) > 120 else first, zoom=0.9)
        rows.append({'step': k, 'title': title, 'adds': add, 'how': how, 'picture': f'exports/turret/assembly/{f}'})
        done += add
    (OUT / 'steps.json').write_text(json.dumps(rows, indent=1) + '\n')
    write_doc(rows)
    print(f'{len(rows)} steps -> {OUT}, docs/turret-assembly.md')


def write_doc(rows):
    """docs/turret-assembly.md from the steps (regenerated with the pictures; edit STEPS, not the page)."""
    bom = json.loads((R / 'exports/turret/bench/bom.json').read_text()) if (R / 'exports/turret/bench/bom.json').exists() else {}
    hw = [r for r in bom.get('bench_turret', []) if r['for'].startswith('hw_')]
    lines = ['# Turret assembly', '',
             'The order to build the turret in, from cad/turret_assembly.py (which draws the pictures from the CAD: the new',
             'parts of each step in colour, lifted along the way they go in; what is already fitted in grey). Tools: a',
             'soldering iron with heat-set insert tips (M3, M4, M5), metric hex keys 1.5-4 mm, DIN 471 circlip pliers for a',
             '50 mm ring, a crimper for Micro-Fit and DT contacts (IWISS IWD-1620 class), cyanoacrylate gel.', '']
    for r in rows:
        lines += [f"## {r['step']}. {r['title']}", '', f"![step {r['step']}](../{r['picture']})", '', r['how'], '']
    if hw:
        lines += ['## The hardware, all steps', '', '| Line | Part | Part number | Qty |', '|---|---|---|---|']
        for r in hw:
            lines.append(f"| {r['for'][3:].replace('_', ' ')} | {r['item']} | {r.get('vendor') or ''} {r.get('part_number') or ''} | {r['qty']} |")
        lines.append('')
    (R / 'docs' / 'turret-assembly.md').write_text('\n'.join(lines))


def _items(name, shape, colour, offset):
    """The renderer's (shape, colour[, offset]) items for one part; the flywheels and tyres come in pairs."""
    v = shape.val() if hasattr(shape, 'val') else shape
    out = [(v, colour) if offset is None else (v, colour, offset)]
    if name in ('flywheel', 'flywheel_tyre'):
        m = shape.mirror('XZ').val()
        out.append((m, colour) if offset is None else (m, colour, offset))
    return out


if __name__ == '__main__':
    main()
