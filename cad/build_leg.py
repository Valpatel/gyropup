"""Build leg v2 (cad/fivebar.py): every printed part as STEP and print-ready STL, the assembled leg, pictures, the
print plan, the parts list with McMaster part numbers, the mass, and a clash sweep over the whole range.

    .venv/bin/python cad/build_leg.py [--no-render] [--no-clash]

Writes exports/leg/: <part>.step, <part>.stl (print orientation, on z = 0), leg_stand.step (the assembled leg with the
bought parts as envelopes: the vendor models are not redistributed), *.png, print-plan.json, bom.json, leg.json; and
exports/leg/cnc/ for the parts machined to order (D46): <part>.step in the frame it is machined in, <part>.stl for its
picture, README.md with the callouts the order needs beyond the STEP, cnc.json.
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
       'stop_sleeve': DOWN_OUTER}    # cap-down: the bore opens upwards, nothing bridged

# Bought parts per leg: catalogue key (catalog/hardware.json, or a motor id), how many, what for
BOUGHT = [
    ('robstride-rs-04', 2, 'the two leg motors, in the hip frame'),
    ('odrive-botwheel', 1, 'the wheel, on the wheel link\'s hub'),
    ('bearing_61812', 4, 'support bearings round the two output adapters; two at the apex on the wheel link\'s hub'),
    ('bearing_6301', 4, 'two in each knee'),
    ('circlip_60', 1, 'holds the apex 61812 on the wheel link\'s hub'),
    ('knee_pin', 2, 'knee shoulder screws, 12 mm x 90, M10 (cad/fivebar.py knee_pin_length)'),
    ('nut_m10_nyloc', 2, 'knee pins, in the upper links\' pockets'),
    ('washer_m12_thin', 4, 'each side of each knee\'s bearing stack'),
    ('knee_spacer', 2, f'between each knee\'s two inner races ({fb.knee_spacer_length():g} mm)'),
    ('eye_sleeve', 4, 'steel sleeves, two end to end in each upper link\'s knee eye: spread the pin\'s load on the plastic'),
    ('stop_pin', 4, 'stop posts: Ø16 x 40 vented pull-out dowels, 23 mm into blind holes in the hip frame (retaining compound), TPU sleeves over them'),
    ('screw_m4x20', 20, 'motor lugs (10 per motor), seats 8.5 mm down: 4.4 mm nominal penetration into 5 mm-min usable threads; measure before assembly'),
    ('dowel_5x16', 4, 'into each motor\'s two locating holes, 12 mm into the hip frame'),
    ('dowel_5x20', 4, 'two in each adapter\'s standard face, pressed 8 mm into its H7 holes, 12 mm into the upper link (issue #5)'),
    ('screw_m5x25', 18, 'motor outputs through the CNC output adapters (9 per motor), heads in pockets below the face'),
    ('screw_m5x40', 16, 'upper links onto the output adapters (8 each), heads proud'),
    ('insert_m5', 6, 'the frame\'s flange ends (the body, or the rig\'s carriage)'),
    ('screw_m6x30', 4, 'the BotWheel\'s flange, from inside the wheel link\'s hub (M6 x 40 bottoms out unless its threads are > 15 deep: measure)'),
]


CUT_FROM_STOCK = {'knee_spacer': (4, round(fb.knee_spacer_length() * 73.78 * 2.70e-3, 1))}   # pieces per stocked length,
                                                 # grams per piece: the tube's 73.78 mm2 (15.875 x 12.573) of 6061


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
        row = {'key': key, 'qty': qty, 'for': why, 'vendor': (it.get('vendor') or 'McMaster-Carr') if it else None,
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
           'knee_bearing': (.78, .8, .83), 'apex_circlip': (.3, .3, .32), 'apex': (.78, .8, .83), 'knee_pin': (.66, .68, .72), 'knee_nut': (.66, .68, .72),
           'knee_washer': (.7, .72, .76), 'stop_posts': (.6, .62, .66), 'wheel_tyre': (.1, .1, .11), 'wheel_hub': (.3, .32, .35)}


def colour(n):
    for k, v in COLOURS.items():
        if n.startswith(k):
            return v
    return (.6, .6, .6)


EXPLODE = {'motor': (0, -70, 0), 'output_adapter': (0, -25, 0), 'screws_outputs': (0, -25, 0), 'bearing_61812': (0, -12, 0), 'hip_frame': (0, -45, 0),
           'stop': (0, 10, 0), 'upper_link': (0, 30, 0), 'knee_nut': (0, 20, 0), 'front_link': (0, 75, 0), 'apex': (0, 75, 0),
           'knee_bearing': (0, 95, 0), 'knee_washer': (0, 95, 0), 'wheel_link': (0, 120, 0), 'knee_pin': (0, 175, 0), 'wheel': (0, 170, 0)}


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


CNC_ORDER = {'vendor': 'JLCCNC (jlccnc.com: upload the STEP for the instant price)', 'backup': 'Xometry (xometry.com: instant quote from the STEP)',
             'price_estimate_usd_each': 40.0,
             'price_note': 'an estimate until the instant price is read on upload (D40: no quotes; JLCCNC turned-and-milled 6061, qty 4); '
                           'shipping from China is extra and takes 5-10 days'}


def cnc_part(name: str, m: dict, grams: float) -> dict:
    """A part machined to order: its STEP in the frame it is machined in, an STL for its picture, and the callouts."""
    shape, spec = m['machining']
    solid = shape.val() if hasattr(shape, 'val') else shape
    d = OUT / 'cnc'
    d.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(solid, str(d / f'{name}.step'))
    cq.exporters.export(solid, str(d / f'{name}.stl'), tolerance=0.05, angularTolerance=0.1)
    bb = solid.BoundingBox()
    row = {'key': name, 'qty': m['qty'], 'material': MATERIALS[m['material']]['name'], 'mass_g_each': round(grams, 1),
           'size_mm': [round(v, 1) for v in (bb.xlen, bb.ylen, bb.zlen)], 'step': str((d / f'{name}.step').relative_to(R)),
           'stl': str((d / f'{name}.stl').relative_to(R)), 'spec': spec, 'price_usd_each': None, 'note': m['note'], **CNC_ORDER}
    index = json.loads((d / 'cnc.json').read_text()) if (d / 'cnc.json').exists() else {}
    index[name] = row
    (d / 'cnc.json').write_text(json.dumps(index, indent=1, ensure_ascii=False) + '\n')
    lines = ['# Leg parts machined to order', '',
             'Each part is ordered online at an instant price (docs/decisions.yaml D40, D46): upload the STEP, enter the callouts below in the',
             "order form (most are also in the STEP's geometry; the tolerances and threads are not), and attach this page as the drawing.",
             'Regenerated by `cad/build_leg.py`; the STEP is in the frame the part is machined in (axis +z, the motor face at z = 0).', '']
    for n, r in index.items():
        lines += [f"## {n} (x{r['qty']} per leg, x{2 * r['qty']} per robot)", '',
                  f"- File: `{Path(r['step']).name}` ({r['material']}, {r['mass_g_each']:g} g, {' x '.join(f'{v:g}' for v in r['size_mm'])} mm)",
                  f"- Order: {r['vendor']}; backup {r['backup']}",
                  f"- Price: {r['price_note']} (estimate ${r['price_estimate_usd_each']:.0f} each)", '', '**Callouts**', '']
        lines += [f'- {c}' for c in r['spec']] + ['']
    (d / 'README.md').write_text('\n'.join(lines))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-clash', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    L = fb.leg_parts()
    report, plan, masses, cnc = {}, {}, {}, {}
    for name, shape in L.parts.items():
        m = L.meta[name]
        solid = shape.val()
        masses[name] = round(mass_g(name, shape), 1)
        if m.get('made') == 'cnc':                       # machined to order from its STEP: not printed
            cnc[name] = cnc_part(name, m, masses[name])
            report[name] = {'qty': m['qty'], 'material': m['material'], 'made': m['note'], 'order': cnc[name]['step']}
            for stale in (OUT / f'{name}.step', OUT / f'{name}.stl'):
                stale.unlink(missing_ok=True)
            continue
        cq.exporters.export(solid, str(OUT / f'{name}.step'))
        rep = export_print_stl(solid, OUT / f'{name}.stl', rotation=ROT.get(name))
        report[name] = {**rep, 'qty': m['qty'], 'material': m['material'], 'made': m['note']}
        plan[name] = printplan.row(solid, ROT.get(name), m['material'], m['qty'], masses[name], m.get('solid', True), m['note'])
    too_big = printplan.write(OUT / 'print-plan.json', plan)
    asm = assembled(300.0)
    comp = cq.Compound.makeCompound([(s.val() if hasattr(s, 'val') else s) for s, _ in asm.values() if s is not None])
    cq.exporters.export(comp, str(OUT / 'leg_stand.step'))
    rows = bom()
    printed_g = sum(masses[n] * L.meta[n]['qty'] for n in masses if n not in cnc)
    cnc_g = sum(masses[n] * L.meta[n]['qty'] for n in cnc)
    bought_g = sum((r['mass_g_each'] or 0) * r['qty'] for r in rows)
    missing = [r['key'] for r in rows if r['part_number'] is None]
    no_cad = [r['key'] for r in rows if r.get('cad') is False]          # catalogue hardware with no vendor model yet
    cnc_rows = [{k: c[k] for k in ('key', 'qty', 'vendor', 'backup', 'material', 'mass_g_each', 'size_mm', 'step', 'spec', 'price_usd_each',
                                   'price_estimate_usd_each', 'price_note')} for c in cnc.values()]
    (OUT / 'bom.json').write_text(json.dumps({'per_leg': rows, 'made_to_order': cnc_rows, 'to_source': missing, 'cad_pending': no_cad,
                                              'price_usd_per_leg': round(sum((r['price_usd_each'] or 0) * r['qty'] for r in rows), 2),
                                              'made_to_order_estimate_usd_per_leg': round(sum(c['price_estimate_usd_each'] * c['qty'] for c in cnc_rows), 2)},
                                             indent=1) + '\n')
    clashes = None if a.no_clash else fb.clashes(heights=(125, 130, 160, 200, 260, 320, 380, 390), leans=(-20, -10, 0, 10, 20),
                                                  poses=fb.stop_poses())          # the stops too (review M1)
    phi_s = fb.stance(300.0)
    j = fb.fk(*phi_s)
    summary = {
        'params': fb.P, 'stack_mm': fb.Y, 'stack_notes': fb.S.notes,
        'leg_range_mm': [round(-fb.fk(*fb.stop_angles()[0::2])['E'][1], 1), round(-fb.fk(*fb.stop_angles()[1::2])['E'][1], 1)],
        'track_mm_two_legs_back_to_back': round(2 * (fb.Y['wheel'] - fb.Y['centre_plane']), 1),
        'stand_300': {'phi_deg': [round(math.degrees(v), 1) for v in phi_s], 'knees': [list(map(lambda v: round(v, 1), j['C'])), list(map(lambda v: round(v, 1), j['D']))]},
        'lug_clock_deg': fb.lug_clock()[0], 'stop_posts_mm': [[round(v, 1) for v in p] for p in fb.stop_posts()],
        'mass_g': {'printed': round(printed_g), 'machined': round(cnc_g), 'bought': round(bought_g), 'total': round(printed_g + cnc_g + bought_g),
                   'printed_parts': {n: g for n, g in masses.items() if n not in cnc}, 'machined_parts': {n: masses[n] for n in cnc}},
        'made_to_order': {n: c['step'] for n, c in cnc.items()},
        'print': {'too_big': too_big, 'hours': round(sum(p['hours'] for p in plan.values()), 1)},
        'clashes': clashes,
        'cable_route': None if a.no_clash else fb.cable_check(),
        'bought_to_source': missing,
    }
    if not a.no_render:
        summary['pictures'] = render(OUT)
    (OUT / 'leg.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f"leg v2: printed {printed_g / 1000:.2f} kg + machined {cnc_g / 1000:.2f} kg + bought {bought_g / 1000:.2f} kg = "
          f"{(printed_g + cnc_g + bought_g) / 1000:.2f} kg per leg; "
          f"range {summary['leg_range_mm']} mm; track {summary['track_mm_two_legs_back_to_back']} mm; print {summary['print']['hours']} h"
          f"{'; TOO BIG: ' + ', '.join(too_big) if too_big else ''}")
    for n, p in plan.items():
        print(f"  {n:15} x{p['qty']}  {p['material']:6} {p['grams_each']:5d} g  {p['size_mm']}  {p['placement']}")
    for n, c in cnc.items():
        print(f"  {n:15} x{c['qty']}  {c['material']} {c['mass_g_each']:5.0f} g  {c['size_mm']}  machined to order: {c['step']}")
    if clashes is not None:
        print(f'  clashes: {len(clashes)}', *[f'    {c}' for c in clashes], sep='\n')
    if missing:
        print('  to source:', ', '.join(missing))
    print(f'  {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
