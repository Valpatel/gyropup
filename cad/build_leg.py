"""Build leg v2 (cad/fivebar.py): every printed part as STEP and print-ready STL, the assembled leg, pictures, the
print plan, the parts list with McMaster part numbers, the mass, and a clash sweep over the whole range.

    .venv/bin/python cad/build_leg.py [--no-render] [--no-clash]

Writes exports/leg/: <part>.step, <part>.stl (print orientation, on z = 0), leg_stand.step (the assembled leg with the
bought parts as envelopes: the vendor models are not redistributed), *.png, print-plan.json, bom.json, leg.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402
import gmi  # noqa: E402
import printplan  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402
from cadagent.robot import solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'leg'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
HARDWARE = {i['key']: i for i in json.loads((R / 'catalog/hardware.json').read_text())}
CATALOG = {it['id']: it for f in ('leg_actuators.json', 'wheel_motors.json') for it in json.loads((R / 'catalog' / f).read_text())}

# print orientation (rotation onto the bed), from each part's own frame
DOWN_OUTER = ((1, 0, 0), -90)        # the part's +y face on the bed
DOWN_INNER = ((1, 0, 0), 90)         # its -y face on the bed
ROT = {'hip_frame': DOWN_OUTER,      # the web's outer face down, the flanges up
       'upper_link': DOWN_OUTER,     # head pockets open at the bed, the spigot recess and nut pocket on top
       'front_link': DOWN_INNER,     # body and knee boss start flush on the inner face
       'wheel_link': DOWN_OUTER,     # body and knee boss end flush on the outer face; the hub and the boss rise
       'output_adapter': DOWN_INNER, # the motor side down, the standard face up
       'apex_spacer': DOWN_INNER,
       'stop_sleeve': DOWN_INNER}

# Bought parts per leg: catalogue key (catalog/hardware.json, or a motor id), how many, what for
BOUGHT = [
    ('robstride-rs-04', 2, 'the two leg motors, in the hip frame'),
    ('odrive-botwheel', 1, 'the wheel, on the wheel link\'s hub'),
    ('bearing_61812', 4, 'support bearings round the two output adapters; two at the apex on the wheel link\'s hub'),
    ('bearing_6201', 4, 'two in each knee'),
    ('circlip_60', 1, 'holds the apex 61812 on the wheel link\'s hub'),
    ('knee_pin_70', 2, 'knee shoulder screws, 12 mm x 70, M10 (cad/fivebar.py knee_pin_length)'),
    ('nut_m10_nyloc', 2, 'knee pins, in the upper links\' pockets'),
    ('washer_m12_thin', 4, 'each side of each knee\'s bearing stack'),
    ('knee_spacer', 2, 'between each knee\'s two inner races (28 mm)'),
    ('eye_sleeve', 2, 'steel sleeve pressed into each upper link\'s knee eye: spreads the pin\'s load on the plastic'),
    ('stop_post', 4, 'stop posts (TPU sleeves over them)'),
    ('insert_m8', 4, 'stop posts, in the hip frame'),
    ('screw_m4x20', 20, 'motor lugs (10 per motor), heads 10 mm down in the hip frame: 5.9 mm into the 7 mm threads'),
    ('dowel_5x16', 4, 'into each motor\'s two locating holes'),
    ('screw_m5x30', 18, 'motor outputs into the output adapters (9 per motor)'),
    ('screw_m5x40', 16, 'upper links onto the output adapters (8 each), heads proud'),
    ('insert_m5', 22, 'the adapters\' standard faces (16), the frame\'s flange ends (6)'),
    ('screw_m3x6', 6, 'bearing retainers on the hip frame'),
    ('washer_m3_large', 6, 'under the retainer screws, over the outer races'),
    ('insert_m3', 6, 'for the retainer screws'),
    ('screw_m6x30', 4, 'the BotWheel\'s flange, from inside the wheel link\'s hub (M6 x 40 bottoms out unless its threads are > 15 deep: measure)'),
]


CUT_FROM_STOCK = {'knee_spacer': (4, 5.2)}      # pieces per stocked length, grams per piece


def mass_g(name, shape):
    mat = fb.leg_parts().meta[name]['material']
    return solid_mass_properties(shape.val() if hasattr(shape, 'val') else shape, MATERIALS[mat]['density_g_cm3'], 1.0, name).mass * 1000


def bom():
    """The bought list per leg with part numbers, prices and masses (None where the catalogue has no entry yet)."""
    rows = []
    for key, qty, why in BOUGHT:
        if key in CATALOG:
            it = CATALOG[key]
            rows.append({'key': key, 'qty': qty, 'for': why, 'vendor': it.get('vendor'), 'part_number': it.get('model') or key,
                         'name': it.get('name'), 'mass_g_each': it['specs'].get('mass_g'), 'price_usd_each': it.get('price_usd')})
            continue
        it = HARDWARE.get(key)
        row = {'key': key, 'qty': qty, 'for': why, 'vendor': 'McMaster-Carr' if it else None,
               'part_number': it['model'] if it else None, 'name': it['name'] if it else 'TO SOURCE',
               'mass_g_each': it['specs'].get('mass_g') if it else None, 'price_usd_each': it.get('price_usd') if it else None,
               'cad': bool(it and (it.get('cad') or {}).get('file'))}
        if key in CUT_FROM_STOCK and it:                         # cut from a stocked length: per piece, not per length
            n, g = CUT_FROM_STOCK[key]
            row.update(price_usd_each=round(it['price_usd'] / n, 2), mass_g_each=g, name=f"{it['name']} (cut {n} per length)")
        rows.append(row)
    return rows


def assembled(h_mm: float, lean: float = 0.0, vendor: bool = False):
    """{name: (shape, kind)} at a stance. vendor=False: the motors as envelopes (for files that leave this machine)."""
    phi = fb.stance(h_mm, lean)
    if not vendor:
        fb.motor_model.cache_clear()
        real = fb.gmi.STEP_FRAMES.pop(fb.MOTOR, None)
        try:
            asm = fb.assembly(*phi)
        finally:
            if real:
                fb.gmi.STEP_FRAMES[fb.MOTOR] = real
            fb.motor_model.cache_clear()
        return asm
    return fb.assembly(*phi)


COLOURS = {'screws': (.15, .15, .17), 'hip_frame': (.40, .43, .48), 'output_adapter': (.62, .65, .70), 'upper_link': (.96, .72, .16), 'front_link': (.96, .72, .16),
           'wheel_link': (.93, .60, .12), 'stop_sleeve': (.85, .22, .2), 'motor': (.17, .18, .2), 'bearing': (.78, .8, .83),
           'knee_6201': (.78, .8, .83), 'apex_circlip': (.3, .3, .32), 'apex': (.78, .8, .83), 'knee_pin': (.66, .68, .72), 'knee_nut': (.66, .68, .72),
           'knee_washer': (.7, .72, .76), 'stop_posts': (.6, .62, .66), 'wheel_tyre': (.1, .1, .11), 'wheel_hub': (.3, .32, .35)}


def colour(n):
    for k, v in COLOURS.items():
        if n.startswith(k):
            return v
    return (.6, .6, .6)


EXPLODE = {'motor': (0, -70, 0), 'output_adapter': (0, -25, 0), 'bearing_61812': (0, -12, 0), 'hip_frame': (0, -45, 0),
           'stop': (0, 10, 0), 'upper_link': (0, 30, 0), 'knee_nut': (0, 20, 0), 'front_link': (0, 75, 0), 'apex': (0, 75, 0),
           'knee_6201': (0, 95, 0), 'knee_washer': (0, 95, 0), 'wheel_link': (0, 120, 0), 'knee_pin': (0, 175, 0), 'wheel': (0, 170, 0)}


def render(out: Path):
    from cadagent.render import Renderer
    r = Renderer(out, subtitle='GYROPUP LEG v2 | FIVE-BAR, TWO RS-04, BOTWHEEL')
    views = {'iso': (0.9, 1.0, 0.55), 'outside': (0.0, 1.0, 0.0), 'inside': (0.6, -1.0, 0.45), 'front': (1.0, 0.0, 0.08)}
    made = []
    for h, tag, vs in ((300, 'stand', ('iso', 'outside', 'inside', 'front')), (130, 'crouch', ('outside', 'iso')), (380, 'tall', ('outside',))):
        asm = assembled(h, vendor=True)
        shapes = [((s.val() if hasattr(s, 'val') else s), colour(n)) for n, (s, _) in asm.items() if s is not None]
        for v in vs:
            r.render(f'leg-{tag}-{v}.png', shapes=shapes, view=views[v], caption=f'Leg v2, {tag} ({h} mm hip to axle), {v}')
            made.append(f'leg-{tag}-{v}.png')
        if tag == 'stand':
            ex = []
            for n, (s, _) in asm.items():
                if s is None:
                    continue
                d = next((v for k, v in EXPLODE.items() if n.startswith(k)), (0, 0, 0))
                ex.append(((s.val() if hasattr(s, "val") else s).translate(cq.Vector(*d)), colour(n)))
            r.render('leg-exploded.png', shapes=ex, view=(0.75, 1.0, 0.45), caption='Leg v2, exploded (outwards along the motor axes)')
            made.append('leg-exploded.png')
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-clash', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    L = fb.leg_parts()
    report, plan, masses = {}, {}, {}
    for name, shape in L.parts.items():
        m = L.meta[name]
        solid = shape.val()
        masses[name] = round(mass_g(name, shape), 1)
        cq.exporters.export(solid, str(OUT / f'{name}.step'))
        rep = export_print_stl(solid, OUT / f'{name}.stl', rotation=ROT.get(name))
        report[name] = {**rep, 'qty': m['qty'], 'material': m['material'], 'made': m['note']}
        plan[name] = printplan.row(solid, ROT.get(name), m['material'], m['qty'], masses[name], m.get('solid', True), m['note'])
    too_big = printplan.write(OUT / 'print-plan.json', plan)
    asm = assembled(300.0)
    comp = cq.Compound.makeCompound([(s.val() if hasattr(s, 'val') else s) for s, _ in asm.values() if s is not None])
    cq.exporters.export(comp, str(OUT / 'leg_stand.step'))
    rows = bom()
    printed_g = sum(masses[n] * L.meta[n]['qty'] for n in masses)
    bought_g = sum((r['mass_g_each'] or 0) * r['qty'] for r in rows)
    missing = [r['key'] for r in rows if r['part_number'] is None]
    no_cad = [r['key'] for r in rows if r['vendor'] == 'McMaster-Carr' and not r.get('cad')]
    (OUT / 'bom.json').write_text(json.dumps({'per_leg': rows, 'to_source': missing, 'cad_pending': no_cad,
                                              'price_usd_per_leg': round(sum((r['price_usd_each'] or 0) * r['qty'] for r in rows), 2)}, indent=1) + '\n')
    clashes = None if a.no_clash else fb.clashes(heights=(125, 130, 160, 200, 260, 320, 380, 390), leans=(-20, -10, 0, 10, 20))
    phi_s = fb.stance(300.0)
    j = fb.fk(*phi_s)
    summary = {
        'params': fb.P, 'stack_mm': fb.Y, 'stack_notes': fb.S.notes,
        'leg_range_mm': [round(-fb.fk(*fb.stop_angles()[0::2])['E'][1], 1), round(-fb.fk(*fb.stop_angles()[1::2])['E'][1], 1)],
        'track_mm_two_legs_back_to_back': round(2 * (fb.Y['wheel'] - fb.Y['centre_plane']), 1),
        'stand_300': {'phi_deg': [round(math.degrees(v), 1) for v in phi_s], 'knees': [list(map(lambda v: round(v, 1), j['C'])), list(map(lambda v: round(v, 1), j['D']))]},
        'lug_clock_deg': fb.lug_clock()[0], 'stop_posts_mm': [[round(v, 1) for v in p] for p in fb.stop_posts()],
        'mass_g': {'printed': round(printed_g), 'bought': round(bought_g), 'total': round(printed_g + bought_g), 'printed_parts': masses},
        'print': {'too_big': too_big, 'hours': round(sum(p['hours'] for p in plan.values()), 1)},
        'clashes': clashes,
        'bought_to_source': missing,
    }
    if not a.no_render:
        summary['pictures'] = render(OUT)
    (OUT / 'leg.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f"leg v2: printed {printed_g / 1000:.2f} kg + bought {bought_g / 1000:.2f} kg = {(printed_g + bought_g) / 1000:.2f} kg per leg; "
          f"range {summary['leg_range_mm']} mm; track {summary['track_mm_two_legs_back_to_back']} mm; print {summary['print']['hours']} h"
          f"{'; TOO BIG: ' + ', '.join(too_big) if too_big else ''}")
    for n, p in plan.items():
        print(f"  {n:15} x{p['qty']}  {p['material']:6} {p['grams_each']:5d} g  {p['size_mm']}  {p['placement']}")
    if clashes is not None:
        print(f'  clashes: {len(clashes)}', *[f'    {c}' for c in clashes], sep='\n')
    if missing:
        print('  to source:', ', '.join(missing))
    print(f'  {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
