"""The P1S print schedule for the first leg, its rig and the bench fixtures (docs/leg-prototype-plan.md task T5, section
6.2), from the three print plans:

    .venv/bin/python tools/print_schedule.py        # exports/rig/print-schedule.md and .json

One printer, run day and night; small parts share a plate (a shelf packing of their footprints on the 256 mm bed, 6 mm
apart); each phase in the plan's order, so the bench fixtures and the fit coupons are done before the motors arrive and
the hip frame (the biggest, riskiest print) is last. Hours are the print plans' rough ones (grams / density / a
strength-holding volumetric rate): a slicer will say less for small parts; expect +20 % for big PA6-CF ones.
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'rig'
BED, GAP = 250.0, 6.0
MACHINED = {'output_adapter'}                      # D46: machined 6061-T6, no longer printed

# the plan's phases (section 6.2), in order: (phase, title, material, [part name prefixes], purpose)
PHASES = [
    ('A', 'Fit coupons and test blocks', 'pa6-cf', ['coupon_', 'insert_coupon', 'sleeve_block', 'sleeve_anvil'],
     'first: every seat and insert dialled in on PA6-CF before any big part (the leg waits on them); B3 and B4 run on these'),
    ('B', 'The dyno and the tyre cradle', 'petg', ['dyno_lug_plate', 'dyno_hub', 'tyre_cradle'],
     'ready before the motors land (1-3 weeks): B1 and B2 start that day'),
    ('C', 'TPU', 'tpu95', ['stop_sleeve', 'bumper_tpu', 'dyno_spider'], 'the dyno\'s spider, B3\'s sleeves, the rig\'s bumpers (R0 picks their infill)'),
    ('D', 'Upper links', 'pa6-cf', ['upper_link'], 'with the coupons\' seat sizes'),
    ('E', 'Front link', 'pa6-cf', ['front_link'], 'turned on the bed'),
    ('F', 'Wheel link', 'pa6-cf', ['wheel_link'], 'turned on the bed'),
    ('G', 'The rig\'s printed parts', 'petg', ['bumper_base', 'bumper_cap', 'top_stop_bracket', 'drop_bracket', 'tof_arm', 'pod',
                                              'pod_lid', 'pendant_clip', 'load_cell_mount'],
     'the rig\'s frame goes together from bought parts meanwhile; these finish it before the first power-up'),
    ('H', 'Small leg parts and spares', 'pa6-cf', ['apex_spacer'], ''),
    ('I', 'Hip frame', 'pa6-cf', ['hip_frame'], 'last: 274 x 148 x 81 turned 45 deg; a 150 x 150 PA6-CF test slab first if the '
                                               'P1S has not held PA6-CF flat at that size'),
]
DRY = {'pa6-cf': 'dry 8-12 h at 80 C, feed from a dry box (not the AMS); dry the next spool during the print before',
       'tpu95': 'dry 6 h at 65 C; print slow, direct from the spool', 'petg': 'dry 4-6 h at 65 C if the spool was open'}


def load(p):
    p = R / p
    return json.loads(p.read_text())['parts'] if p.exists() else {}


def parts():
    out = []
    for src, plan in (('leg', load('exports/leg/print-plan.json')), ('rig', load('exports/rig/print-plan.json')),
                      ('bench', load('exports/rig/bench/print-plan.json'))):
        for name, r in plan.items():
            if src == 'leg' and name in MACHINED:
                continue
            qty = r['qty'] + (2 if name == 'stop_sleeve' else 0)          # the plan: two spare sleeves
            each_h = r['hours'] / max(r['qty'], 1)
            for k in range(qty):
                out.append({'name': name, 'src': src, 'material': r['material'], 'size': r['size_mm'], 'placement': r['placement'],
                            'grams': r['grams_each'], 'hours': round(each_h, 2)})
    return out


def pack(items):
    """Shelf packing of footprints on the bed: [[item, ...], ...] plates. A part the plan prints turned gets a plate."""
    plates = []
    for it in sorted(items, key=lambda i: -i['size'][0] * i['size'][1]):
        w, d = it['size'][0] + GAP, it['size'][1] + GAP
        if it['placement'] == 'turned' or w > BED or d > BED:
            plates.append({'items': [it], 'shelves': None})
            continue
        placed = False
        for pl in plates:
            if pl['shelves'] is None:
                continue
            for sh in pl['shelves']:                                          # [y0, height, x_used]
                if d <= sh[1] and sh[2] + w <= BED:
                    sh[2] += w
                    pl['items'].append(it)
                    placed = True
                    break
            if placed:
                break
            used = sum(sh[1] for sh in pl['shelves'])
            if used + d <= BED:
                pl['shelves'].append([used, d, w])
                pl['items'].append(it)
                placed = True
                break
        if not placed:
            plates.append({'items': [it], 'shelves': [[0.0, d, w]]})
    return [p['items'] for p in plates]


def main():
    all_parts = parts()
    left = list(all_parts)
    rows, t = [], 0.0
    for ph, title, mat, prefixes, why in PHASES:
        mine = [p for p in left if p['material'] == mat and any(p['name'].startswith(x) for x in prefixes)]
        left = [p for p in left if p not in mine]
        for k, plate in enumerate(pack(mine)):
            h = round(sum(p['hours'] for p in plate), 1)
            names = {}
            for p in plate:
                names[p['name']] = names.get(p['name'], 0) + 1
            rows.append({'phase': ph, 'title': title, 'plate': f'{ph}{k + 1}', 'material': mat, 'parts': names,
                         'grams': sum(p['grams'] for p in plate), 'hours': h, 'start_h': round(t, 1), 'why': why})
            t += h + 0.5                                                      # plate change, a check of the first layer
    for p in left:                                                            # anything a plan holds that no phase names
        rows.append({'phase': 'Z', 'title': 'Other', 'plate': f"Z-{p['name']}", 'material': p['material'], 'parts': {p['name']: 1},
                     'grams': p['grams'], 'hours': p['hours'], 'start_h': round(t, 1), 'why': ''})
        t += p['hours'] + 0.5
    total_h = round(sum(r['hours'] for r in rows), 1)
    by_mat = {}
    for r in rows:
        m = by_mat.setdefault(r['material'], {'grams': 0, 'hours': 0.0, 'plates': 0})
        m['grams'] += r['grams']
        m['hours'] = round(m['hours'] + r['hours'], 1)
        m['plates'] += 1
    days = round(t / 20.0, 1)                                                 # ~20 h a day of printing, round the clock
    doc = {'plates': rows, 'total_print_hours': total_h, 'calendar_days_at_20h': days, 'by_material': by_mat,
           'machined_not_printed': sorted(MACHINED), 'made_by': 'tools/print_schedule.py'}
    (OUT / 'print-schedule.json').write_text(json.dumps(doc, indent=1) + '\n')
    mats = ', '.join(f"{m} {v['hours']} h, {v['grams'] / 1000:.2f} kg" for m, v in by_mat.items())
    L = ['# Print schedule: the first leg, its rig and the bench fixtures (Bambu P1S)\n',
         f'One P1S with a hardened nozzle and extruder, textured PEI with glue for PA6-CF. **{total_h} h of printing** '
         f'({mats}), '
         f'about **{days} days** at 20 h a day, three weeks with drying and one reprint. The output adapters are machined '
         '(D46) and not here. Generated by `tools/print_schedule.py` from `exports/leg/print-plan.json`, '
         '`exports/rig/print-plan.json` and `exports/rig/bench/print-plan.json`.\n',
         '## Drying\n']
    for m, d in DRY.items():
        L.append(f'- **{m}**: {d}.')
    L.append('\n## Plates, in order\n')
    L.append('| Plate | Start (h) | Material | Parts | Grams | Hours | Why now |')
    L.append('|---|---|---|---|---|---|---|')
    for r in rows:
        parts_s = ', '.join(f'{n} x {q}' if q > 1 else n for n, q in r['parts'].items())
        L.append(f"| {r['plate']} {r['title']} | {r['start_h']} | {r['material']} | {parts_s} | {r['grams']} | {r['hours']} | {r['why']} |")
    L.append('\n## Rules\n')
    L.append('- The coupons (A) decide every seat before the big PA6-CF parts: if a coupon\'s seat other than the nominal one '
             'fits best, the leg\'s CAD takes that offset before D-I print (the main session\'s files); evaluate them while B prints.\n'
             '- Print the hip frame (I) only after the coupons pass and the P1S has printed PA6-CF flat at 150 x 150; the fallback '
             'for a frame that warps is a split frame (the main session).\n'
             '- The motors\' bench tests need B\'s dyno and C\'s spider; B3 needs C\'s sleeves and A\'s sleeve block.\n'
             '- Weigh every leg part: the rig\'s ballast table (exports/rig/rig.json) assumes the CAD\'s masses.\n')
    (OUT / 'print-schedule.md').write_text('\n'.join(L) + '\n')
    print(f'{len(rows)} plates, {total_h} h, {days} days at 20 h/day; ' + ', '.join(f'{m} {v["hours"]} h' for m, v in by_mat.items()))


if __name__ == '__main__':
    main()
