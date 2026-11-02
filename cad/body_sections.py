"""The body broken into its sections, every part and every decision justified (milestone M5; the user, 2026-10-27:
"breaking the design down by sections, reviewing each piece to justify all design decisions, and building proper
models"). Writes docs/body-sections.md from the CAD and its checks, so the tables cannot drift from the model.

    .venv/bin/python cad/body_sections.py      # after cad/build_body.py (reads exports/body/*.json)

Each section: what it does and the numbers it must meet; its interfaces to the other sections; every part with its
material, how it is made and how it is held (the joints of cad/body_joints.py and the listed holds: the same records the
integrity checks read through the CAD); and each decision with why and what was turned down.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
DOC = R / 'docs' / 'body-sections.md'
EX = R / 'exports' / 'body'


def _j(p):
    f = EX / p
    return json.loads(f.read_text()) if f.exists() else {}


# Which section each part and layout item belongs to: (section, name prefixes)
SECTIONS = [
    ('power', 'Skid and power', ('battery_', 'bay_', 'adapter_plate_', 'power_plate', 'plate_', 'bus_bar_', 'bus_insulator_', 'dcdc_bracket',
                                 'power_dcdc', 'item.battery', 'item.plate_', 'item.power_dcdc')),
    ('frame', 'Frame', ('cheek_', 'spacer', 'frame_screws_', 'floor_tray', 'belly_plate', 'compute_pallet', 'isolator_', 'post_',
                        'item.j501_', 'item.agx_', 'item.vn100')),
    ('head', 'Head and mounts', ('deck', 'riser', 'turret_plate', 'fan_duct', 'item.vlp16', 'item.lidar_', 'item.turret')),
    ('shell', 'Shell (P3)', ('shell_', 'ear_', 'd435', 'eyes_')),
]

TEXT = {
    'power': {
        'does': 'Carries the battery and turns it into every rail the robot needs: the 10S bus for the legs, the wheels and the '
                'turret, 12 V for the J501 and the sensors, 5 V for the MCU; protects every wire with a fuse sized to it; lets the '
                'packs out without tools.',
        'needs': [
            'two DeWalt DCB609 packs in series, 30-41 V, 360 Wh rated (D65); swapped by hand, no tool',
            'every load rated over 30-41 V: the RS-04 24-60 V, the Flipsky 75100 14-84 V, the anti-spark switch 12-84 V, the '
            'TRACO TEP 150-4812WI 18-75 V (the DDR-120C-24 starts at 33.6 V and is out)',
            '80 A for 0.5 s (a jump\'s push) and 30 A continuous (the adapters\' stated rating): the firmware limits both',
            'the bay under the belly between the knees: |y| <= 58 (25 mm from the knee eyes at |y| 83)',
            'the robot\'s only battery protection is its own: cut-off at 3.0 V a cell, a current limit, a regen clamp '
            '(docs/body-firmware.md 5)',
        ],
        'interfaces': [
            'the belly plate: the bay\'s rails and adapter plates on S-M4-0 nuts beyond the cheeks\' ends (|x| 102, 150)',
            'the floor tray: the power plate\'s four printed posts (M5 inserts both ends); the tray slot (x 40..135) for the cables',
            'the legs: four XT60H-F sockets for the RS-04 pigtails; the wheels\' VESCs under the plate',
            'the J501: 12 V on an XT30 (W21); CAN bus C (the MCU)',
            'the turret (D66): its XT30 on a 7.5 A branch of the bus through the stop relay\'s pole B; its dry safety loop',
        ],
        'decisions': [
            ('D65', 'Two DCB609 FLEXVOLT packs in 20 V mode, in series (10S3P)',
             'the user\'s choice: tool packs and chargers, swapped in seconds, no pack to build',
             '13S2P Molicel brick (D43/D54: best jump, 2.0 kg, but a pack to build and a BMS to read); two packs in 60 V mode in '
             'parallel (a fresh pack sits at the RS-04\'s 60 V fault); one pack (18 V, under the RS-04\'s 24 V)'),
            ('this page', 'The bay under the belly, the packs hanging from their adapters as from a tool, out through end doors',
             'a pack is 138 x 87 x 97 mm: nothing above the belly has 122 mm free over 138 x 87 (the tray holds the J501 and the '
             'plate; the deck has 120 mm under it and the turret over it); low and boxed between the legs',
             'on the front and rear faces (the body 244 mm longer, in the lidar\'s lowest beam and the eyes\', where a child '
             'grabs them); on the side walls (blocks the louvres, hatch and door; outside the shell); the cost of the belly: the '
             'bay is 132 mm deep, the robot sits on its skids under a 139 mm leg (it never runs under 160)'),
            ('this page', 'One TRACO TEP 150-4812WI (12 V 150 W, 18-75 V) for the J501 and the 12 V rail',
             'the only listed isolated converters that cover 30-41 V are 4:1 chassis bricks; the J501 takes 12-36 V; one '
             'converter instead of two saves 366 g and a DIN rail; it stands at the plate\'s right edge where the DDR-60L-12 stood',
             'DDR-120C-24 (starts at 33.6 V); every Mean Well DDR-120/RSD 2:1 variant (none covers 30-45 V); DDR-60L-24 (60 W: '
             'the J501 alone peaks there); TEP 150-4815WI 24 V for the J501 alone (no room in the left strip for its bracket '
             'beside the ear bracket\'s nuts: the integrity check found it)'),
            ('D55', 'MRBF 80 A main fuse, low-side anti-spark switch, MINI 58V branch fuses, the frame bonded to -',
             'the pack can deliver hundreds of amps into a short; the switch takes the spark; a chafed + lead to the frame '
             'blows a fuse instead of leaving the frame live', 'a contactor (D37: no e-stop contactor); 32 V MINI fuses (they '
             'cannot interrupt 41 V)'),
            ('#11', 'The shunt in the + lead after the MRBF (the INA228 high side)',
             'in the - lead ahead of the low-side switch, opening the switch drives the INA228\'s inputs far below its ground: '
             'it dies and bypasses the switch (docs/body-fuse-board.md 1)', 'an isolated INA228 in the - lead (more parts)'),
            ('this page', 'Bus-bar insulators in PETG, tested > 10 MOhm at 50 V',
             'the plate is bonded to the - bus; carbon-filled PA6-CF conducts', 'PA6-CF (conducts); PA6-GF (fine, if the plate '
             'runs over 60 C)'),
            ('this page', 'The VESCs\' flange screws M5 x 8, pockets under the bus insulators, the shunt and MRBF on 3 mm spacers',
             'the integrity check found the M5 x 10 tips coming up through the plate 1 mm from a lug screw\'s tip inside an '
             'insulator: a short of a bus bar to the plate', 'moving the bars (the VESCs\' holes are 100 mm apart and the '
             'bars 110 long: no position clears both)'),
            ('D60', 'A JLCPCB fuse board in P3 (Littelfuse MINI FL1 holders, the 1 mOhm high-side shunt, the INA228)',
             'eleven inline holders and a meter shunt are a nest of wire; the FL1 is the only PCB MINI holder with a DC rating '
             'at the bus voltage', 'Keystone 3568 (20 A, no DC rating)'),
        ],
    },
    'frame': {
        'does': 'Joins the two legs into one stiff body and carries everything else: the hip frames bolt to two cheeks, the '
                'cheeks to each other through eight standoffs; the floor tray on their upper flanges carries the J501 and the '
                'power plate, the belly plate under their lower flanges carries the battery bay.',
        'needs': [
            'the legs\' reactions at the hip frame\'s mount plane at 16.25 kg a leg (D56, D57): 197 N m and 555 N in a 150 mm '
            'drop, 287 N m and 1016 N in the power-off fault; SF >= 2.0 everyday, 1.2 in the fault',
            'the track the legs need (the cheeks\' webs 31 mm apart: 414 mm of track)',
            'every sheet part orderable at SendCutSend\'s instant price as drawn (cad/body_sheet.py\'s rules)',
        ],
        'interfaces': [
            'the legs: six M5 x 12 per hip frame into its inserts, heads in the gap',
            'the power section (the plate\'s posts on the tray, the bay under the belly) and the head (the deck\'s four posts)',
            'the J501: on the compute pallet\'s four standoffs, the pallet on four TPU isolators',
        ],
        'decisions': [
            ('D44', 'Two bent 3/16 in 5052 cheeks on eight M4 standoffs in the hip frames\' bolt rows',
             'the standoffs carry each leg\'s roll moment straight across to the other frame', 'a one-piece 36 mm U (SendCutSend '
             'cannot bend a channel whose base is under twice its flanges); 1/8 in cheeks (SF 0.6 in the landing)'),
            ('D71', 'The design mass 37.5 kg, 18.75 kg a leg; a 37.0 kg ledger gate (it replaces D69\'s 35.5 / 35.0 and D57\'s 32.5 / 32.0 kg)',
             'the leg\'s loads scale with mass; the gate keeps the robot honest against them; D65\'s packs, D69\'s hub wheels and '
             'D66\'s turret computer are heavier', 'designing to the 26.8 kg estimate; D69\'s 35.0 kg (set before the packs were in)'),
            ('this page', 'The tray and belly into the cheeks\' flange nuts with M5 x 12 (was x 10)', 'the integrity check: an '
             'M5 x 10 engaged 2.8 mm of the SS-M5-0\'s thread under the 3.2 mm tray', '-'),
        ],
    },
    'head': {
        'does': 'Carries the lidar at the front of the deck and the turret on its riser over the J501\'s fan; takes a child '
                'leaning on it and the turret falling over; lets the J501\'s exhaust out.',
        'needs': [
            '300 N on the deck (a child) SF >= 2.0 and <= 0.5 mm; a 30 g tip-over of the 1.70 kg head SF >= 2.0 (D59)',
            'the turret\'s TM pattern (4 x M5 on 80 x 80, two dowels) 30 mm over the deck; the lidar\'s 1/4-20 and two pins',
            'the J501 fan\'s exhaust out through the deck (it blows up: j501-agx 94da39d) without a finger reaching its blades',
        ],
        'interfaces': [
            'the frame: the deck on its four posts (M5 x 12 into inserts)',
            'the turret (D66): its pan base on the riser\'s TM pattern; its XT30, Ethernet and safety loop through the grommet',
            'the J501: the fan duct from 2 mm over the fan to the turret plate\'s opening',
        ],
        'decisions': [
            ('D59', 'A 6061 0.125 in turret plate under the deck at the riser', 'the deck alone: SF 1.3 in the tip-over; with '
             'the plate the deck 2.12 and the plate 3.00 (cad/body_studies.py D2)', 'a thicker deck (heavier everywhere)'),
            ('D61', 'The fan duct: printed PETG from the plate\'s opening to 2 mm over the fan', 'keeps the exhaust from coming '
             'back round through the fins (the J501 box re-breathed +3.5 K)', 'an open deck'),
            ('this page', 'The duct hangs on three M3 x 6 in tapped holes in the turret plate', 'it was floating: the '
             'integrity check found it held by nothing', 'bonding it'),
        ],
    },
    'shell': {
        'does': 'Closes the body: keeps fingers out of everything that moves or is live, carries the cameras, eyes, ear pods and '
                'the rear panel\'s controls, lets air in for the J501.',
        'needs': [
            'ISO 13854: 25 mm from every moving part, or ISO 13857: no opening over 4 mm (no shell part 4-25 mm from a leg)',
            'every port a person plugs (the J501\'s HDMI, USB) passes its mated plug through the hatch (cadagent.connectors)',
            'the ear pods under the lidar\'s lowest beam (4.3 mm)',
            'every print on the P1S bed (256 mm)',
        ],
        'interfaces': [
            'the frame: every wall and face into M3 inserts in the deck posts\' bosses',
            'the head: the ear pods\' tops under the lidar\'s beam',
        ],
        'decisions': [
            ('D61', '2 mm ribbed PETG walls in halves with a splice; PA6-CF where bolts take load', 'the bed is 256 mm; '
             'PETG is tough and cheap', 'a sheet-metal shell (heavier; sharp edges)'),
            ('this page', 'The service door 55 mm long, on the left', 'at 78 mm it took the right front corner post\'s two '
             'screws away (the integrity check); on the right it now faces the converter', '-'),
            ('this page', 'The D435 cradles screwed to the aprons, the eyes on a clip, the receiver bay printed with the rear face',
             'each was floating in the CAD (the integrity check)', '-'),
        ],
    },
}


def held(parts_names, joints, holds):
    """{part: [how it is held]} from the joints (screws through or into it) and the holds."""
    out = defaultdict(list)
    for j in joints:
        if j.get('screw_part') in parts_names:
            out[j['screw_part']].append(f"they are the {j['joint'].replace('_', ' ')} joint's {j['count']} screws")
        names = list(j['stack']) + [j['receiver'][1]]
        for n in names:
            if n in parts_names:
                role = 'head side' if n == j['stack'][0] else ('thread' if n == j['receiver'][1] else 'clamped')
                out[n].append(f"{j['count']} x {j['screw']} ({j['joint'].replace('_', ' ')}, {role})")
    for a, b, why, *_ in holds:
        for n, m in ((a, b), (b, a)):
            if n in parts_names:
                out[n].append(f'{why} (to {m})')
    return out


def part_rows(section, names_info, held_by):
    pre = dict((s, p) for s, _, p in SECTIONS)[section]
    rows = []
    for n, info in sorted(names_info.items()):
        if not n.startswith(pre):
            continue
        h = held_by.get(n) or held_by.get(n.replace('item.', ''))
        hs = '; '.join(dict.fromkeys(h)) if h else 'NOT HELD'
        rows.append(f"| {n.replace('item.', '')} | {info['what']} | {info['g']} | {hs} |")
    return rows


def main():
    import body_frame as bf
    import body_layout as bl
    import body_battery as bb
    import build_body as bbd
    L = bbd._layout()
    parts = bf.all_parts(L['mounts'])
    body, integ, mass, fea = _j('body.json'), _j('integrity.json'), _j('mass.json'), json.loads((EX / 'fea' / 'summary.json').read_text())
    load_hm = (_j('leg-loads.json') or {}).get('half_mass_kg', '?')     # the legs' loads the FEA ran on
    pm = (body.get('mass_g') or {}).get('frame_parts', {})
    info = {}
    for n, p in parts.items():
        if not bf.on_robot(p, 'P3') and not bf.on_robot(p, 'P1'):
            continue
        if p.kind == 'sheet' and p.sheet is not None:
            what = f"SendCutSend {p.sheet.s['material']} {p.sheet.s['t_in']} in"
        elif p.kind == 'sheet':
            what = 'SendCutSend (as its twin)'
        elif p.kind == 'printed':
            what = f'printed {p.material.upper()}'
        else:
            what = f'bought: {p.note}'
        info[n] = {'what': what + (f' ({p.stage}{"-" + p.until if p.until else ""})' if p.stage != 'P1' or p.until else ''),
                   'g': f"{pm.get(n):.0f}" if pm.get(n) else '-'}
    for it in L['raw']['items']:
        if not it.keepout:
            info[f'item.{it.name}'] = {'what': f'bought: {it.note[:90]}', 'g': f'{it.mass_g:.0f}'}
    holds = integ.get('holds', [])
    held_by = held(set(info), [j for j in integ.get('joints', [])], holds)
    s = integ.get('summary', {})
    g3 = mass.get('P3', {})
    b = bb.summary()
    o = ['# The body by sections: every part, how it is held, and why', '',
         'Generated by `cad/body_sections.py` from the CAD and its checks (regenerate, never edit); written 2026-10-27 for '
         'the user\'s "breaking the design down by sections, reviewing each piece to justify all design decisions, and '
         'building proper models". Every screw below is a joint in `cad/body_joints.py`: the integrity check reads each one '
         'through the solids (head on its face, stack touching, holes, thread engaged, tip clear) and checks that every part '
         'reaches the cheeks.', '',
         f"**Integrity now:** {s.get('joints')} joints, {s.get('screws')} screws; joints with problems: "
         f"{', '.join(s.get('joints_with_problems') or []) or 'none'}; floating parts: {s.get('floating') or 'none'}; "
         f"interference between body parts: {s.get('clashes')}; cad-agent's connectivity gate (issue #14): "
         f"{', '.join(f'{k} ' + ('pass' if v else 'FAIL') for k, v in (s.get('connectivity_pass') or {}).items()) or 'not run'}.", '',
         f"**Mass (P3, the ledger):** {g3.get('total_kg')} kg against the {(g3.get('budget') or {}).get('robot_kg')} kg gate (D71): "
         + ', '.join(f'{k} {v} kg' for k, v in (g3.get('groups_kg') or {}).items()) + '. '
         f"With the scheduled levers {((g3.get('gate') or {}).get('with_scheduled_levers_kg'))} kg: "
         f"{'passes' if (g3.get('gate') or {}).get('pass') else 'over: section 6'}.", '']
    for k, title, _ in SECTIONS:
        t = TEXT[k]
        num = {'power': 1, 'frame': 2, 'head': 3, 'shell': 4}[k]
        o += [f'## {num}. {title}', '', t['does'], '', '**Must meet:**', ''] + [f'- {x}' for x in t['needs']] + ['', '**Interfaces:**', '']
        o += [f'- {x}' for x in t['interfaces']] + ['', '**Parts** (mass from the CAD where it exists; "held by" from the joints and holds):', '',
                                                     '| Part | Material and making | g | Held by |', '|---|---|---|---|']
        o += part_rows(k, info, held_by)
        o += ['', '**Decisions:**', '', '| | Choice | Why | Turned down |', '|---|---|---|---|']
        o += [f'| {d} | {c} | {w} | {a} |' for d, c, w, a in t['decisions']]
        if k == 'power':
            pad = b.get('pad') or {}
            o += ['', f"The bay: {b['bay_mm'][0]} x {b['bay_mm'][1]} x {b['bay_mm'][2]} mm with its crush pads, their bottom at z "
                  f"{b['bay_bottom_z']}; on D69's 10 in wheels the robot sits on the pads under a {b['sits_on_skids_below_leg_mm']} mm leg; "
                  f"{b['clearance_at_lowest_leg_mm']} mm under them at the lowest controlled leg ({pad.get('lowest_leg_mm')} mm), "
                  f"{b['clearance_at_300_mm']} at 300; {b['knee_gap_mm']} mm from the knee eyes. The pads (issue #19): printed TPU 95A "
                  f"gyroid, {pad.get('h')} mm, a {pad.get('plateau_n')} N crush plateau each over {pad.get('stroke')} mm "
                  '(sim/bay_pad_study.py, exports/body/bay-pad-study.json and bay-pad-depth.json).']
        if k == 'frame':
            r = fea.get('results', {})
            o += ['', f"Strength (cad/body_studies.py at {load_hm} kg a leg): " + '; '.join(
                f"{n} SF {v.get('sf_by_part') or v.get('sf_away_from_spacer_ends') or v['safety_factor']} ({'pass' if v['pass'] else 'FAIL'})"
                for n, v in r.items()) + '.']
        o.append('')
    # wiring
    w = _j('wiring.json')
    by_awg = defaultdict(int)
    for r in w.get('wires', []):
        by_awg[r['awg']] += 1
    o += ['## 5. Wiring', '',
          'The wire list is `cad/body_wiring.py` (docs/body-electrical.md 3.1 is generated from it): every run with both ends, '
          'its gauge, colour, connector and the fuse that protects it. A test checks no fuse is larger than its wire carries and '
          'that every live end on the body is a socket.', '',
          f"- {len(w.get('wires', []))} runs: " + ', '.join(f'{n} at {a} AWG' for a, n in sorted(by_awg.items(), key=lambda x: (x[0] is None, x[0] or 0))),
          '- the main path 8 AWG (MRBF 80 A); the packs\' own adapter leads 10 AWG (unfused, as every pack lead: kept to 300 mm)',
          '- the branches: RS-04 14 AWG on 20 A, VESCs 12 AWG on 30 A (their battery limit 20 A), the converter 18 AWG on '
          '10 A, the turret 16 AWG on 7.5 A, the J501 16 AWG on 10 A, the 12 V loads 16 AWG on 7.5 A, the INA228\'s VBUS 22 AWG on 5 A',
          '- CAN: A and B the legs, C the wheels and the J501 (1 Mbit/s each, twisted 22 AWG)', '',
          '| | Choice | Why | Turned down |', '|---|---|---|---|',
          '| D58 | Sockets on every live end of the body | a child touching a plug touches no live pin | pins on the body |',
          '| this page | W33, the frame bond, 14 AWG | a chafed + lead ahead of its branch fuse puts the MRBF\'s let-through on it | 18 AWG |',
          '| D66 | The turret on its own 10 A bus branch through the stop relay | it is its own robot; the radio stop still cuts it | the shared 24 V converter (D45) |',
          '']
    # mass
    gate = g3.get('gate') or {}
    tur = next((it for it in L['raw']['items'] if it.name == 'turret'), None)     # the head as the ledger carries it
    lv = {l['key']: l for l in (g3.get('levers') or [])}
    oc = [l for l in (g3.get('levers') or []) if l['kind'] == 'on call' and l['status'] == 'open']
    o += ['## 6. The mass gate (D71)', '',
          f"The P3 ledger is {g3.get('total_kg')} kg; with every scheduled lever {gate.get('with_scheduled_levers_kg')} kg against "
          f"D71's {gate.get('ceiling_kg')} kg ceiling (37.5 kg design mass, 18.75 kg a leg): a margin of {gate.get('margin_kg'):+.2f} kg, "
          f"{'pass' if gate.get('pass') else 'OVER'}. The wheels are D69's 10 in hub motors at the listed 3.53 kg each; the battery "
          f"group is {(g3.get('groups_kg') or {}).get('battery')} kg (two DCB609 at DeWalt US's 1565 g each). The head is "
          + (f"the turret as its own robot (D66) at {tur.mass_g / 1000:.2f} kg with 30 balls ({tur.note.split(';')[0]}), "
             f"{tur.mass_g / 1000 - 1.70:+.2f} kg on the 1.70 kg head budget" if tur is not None else 'the 1.70 kg head budget')
          + '. The on-call levers stay listed as margin (D71), none taken without the user\'s or the coordinator\'s word:', '',
          '| # | Lever | g | Stage |', '|---|---|---|---|']
    o += [f"| {l['n']} | {l['what']} | {l['grams']} | {l['stage']} |" for l in oc]
    o += ['']
    DOC.write_text('\n'.join(o) + '\n')
    print(f'{DOC.relative_to(R)}: {sum(1 for x in o if x.startswith("| ") and "NOT HELD" in x)} parts not held')


if __name__ == '__main__':
    main()
