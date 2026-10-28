"""The order list for the first leg on its rig (milestone M3): every bought or ordered part with its price, buy link,
stock and a backup, grouped by vendor with totals, written to docs/leg-rig-orders.md; and the rig's parts list for the
build page (designer/build.html), exports/rig/bom.json.

    .venv/bin/python tools/rig_orders.py

Sources: catalog/rig.json (tools/rig_catalog.py: the rig, its electronics, the bench), exports/leg/bom.json with
catalog/hardware.json and catalog/alternates.json (the leg's own parts and its machined adapters), BENCH_EXTRA (more of
a part the leg or rig lists already buy), the print plans for the filament (exports/leg, exports/rig, exports/rig/bench)
priced from catalog/materials.json. Re-run it after a price check or a BOM change.

exports/rig/bom.json, as the build page reads a parts list: lists 'rig', 'electronics' and 'bench' of rows {key, qty,
for, part_number, price_usd_each, pack_qty, sellers: [primary, backups...]}, keyed by the catalogue entry the part
already has where it is the same part as the leg's or the turret's (so one order line covers both), and
'made_to_order' (the carriage plate, cut by SendCutSend from our file).
"""
from __future__ import annotations

import json
import math
import re
from collections import OrderedDict
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'docs' / 'leg-rig-orders.md'
BOM = R / 'exports' / 'rig' / 'bom.json'
EST = {'carriage_plate': (60.0, 90.0), 'output_adapter': (40.0, 40.0)}  # upload-priced: the estimate's range, each
# more of a part another list already buys, for the bench tests (docs/leg-bench-tests.md): (key, qty, what for)
BENCH_EXTRA = [
    ('screw_m5x25', 18, 'the dyno: each hub onto its motor\'s output (9 each)'),
    ('screw_m5x40', 3, 'B4: the screws under test (two inserts to 3.5 kN, the link-under-the-head test)'),
    ('insert_m5', 3, 'B4: one in each M5 puller'),
    ('insert_m8', 2, 'B4: the M8 puller; B3: the sleeve block\'s stop post'),
    ('washer_m6_deck', 2, 'B4: under the screw under test, over the cage\'s hole'),
    ('washer_3_8', 1, 'B4: under the M8 screw under test'),
    ('hx711', 1, 'B3, B4: the load cell\'s own amplifier on the rig node'),
]
# a backup for a leg line catalog/alternates.json has none for (read on the date given)
LEG_BACKUPS = {'screw_m5x25': {'supplier': 'Bolt Depot', 'part_number': '6524 (M5 x 25 class 12.9 black oxide)',
                               'url': 'https://boltdepot.com/Product-Details?product=6524', 'price': '$0.15 / ea ($10.11 / 100)',
                               'price_usd_each': 0.15, 'checked': '2026-10-27'}}
SHARED = re.compile(r'Same part as catalog/(hardware|turret)\.json ([\w.-]+?)[.;]?(?:\s|$)')


def load(p, default=None):
    p = R / p
    return json.loads(p.read_text()) if p.exists() else default


def leg_lines() -> list:
    """The leg's bought parts per leg from exports/leg/bom.json; while that file predates D46 (machined adapters),
    its adapter screws and the counts D46 changes are corrected here."""
    bom = load('exports/leg/bom.json', {'per_leg': []})['per_leg']
    alts = load('catalog/alternates.json', {})
    hw = {i['key']: i for i in load('catalog/hardware.json', [])}
    for f in ('leg_actuators.json', 'wheel_motors.json'):
        for i in load(f'catalog/{f}', []):
            hw.setdefault(i['id'], i)
    d46 = any(r['key'] == 'screw_m5x30' for r in bom)
    rows = []
    for r in bom:
        r = dict(r)
        if d46 and r['key'] == 'screw_m5x30':
            continue                                              # replaced by the M5 x 25 in catalog/rig.json (D46)
        if d46 and r['key'] == 'dowel_5x16' and not any(x['key'] == 'dowel_5x20' for x in bom):   # the adapters' own (#5)
            r['qty'], r['for'] = 8, r['for'] + '; D46: two more per adapter face (8 per leg)'
        if d46 and r['key'] == 'insert_m5':
            r['qty'], r['for'] = 6, 'the frame\'s flange ends (D46: the adapters are tapped aluminium)'
        it = hw.get(r['key'], {})
        url = ((it.get('buy') or [{}])[0].get('url')) or (f"https://www.mcmaster.com/{r['part_number']}/" if r.get('vendor') == 'McMaster-Carr' else None)
        pack = it.get('pack_qty') or 1
        row = {'key': r['key'], 'group': 'leg', 'qty': r['qty'], 'name': r.get('name') or r['key'], 'used_for': r.get('for', ''),
               'vendor': r.get('vendor'), 'model': r.get('part_number'), 'price_usd': r.get('price_usd_each'), 'pack_qty': pack,
               'pack_price_usd': it.get('pack_price_usd') or ((r.get('price_usd_each') or 0) * pack),
               'url': url, 'stock': None, 'checked': it.get('price_checked'), 'alternates': list(alts.get(r['key'], [])) or ([LEG_BACKUPS[r['key']]] if r['key'] in LEG_BACKUPS else []), 'notes': ''}
        if r['key'] == 'odrive-botwheel':                            # sold as a 2-pack: the second wheel is the other leg's
            row.update(qty=1, name='ODrive BotWheel BW0124, 2-pack', price_usd=269.0, pack_qty=1, pack_price_usd=269.0,
                       url='https://wwshop.odriverobotics.com/products/botwheels', stock='2-pack orderable (single sold out)')
        if r['key'] == 'robstride-rs-04':
            row.update(name='RobStride RS-04 (CAN 2.0)', url='https://www.seeedstudio.com/Robostride-04-Actuator-p-6775.html',
                       stock='in stock (search snippet; the page blocks reads)', vendor='Seeed Studio')
            rc = [a for a in row['alternates'] if 'rcdrone' in (a.get('supplier') or '')]
            row['alternates'] = rc + [{'supplier': 'OpenELAB', 'part_number': 'ROBSTRIDE04 (Motor w/o Debug)',
                                       'url': 'https://openelab.io/products/robstride04-qdd-120n-m-integrated-joint-motor-module',
                                       'price': '279,01 EUR incl. VAT, pre-order (sold out, read 2026-10-27 afternoon)'}] + \
                [a for a in row['alternates'] if a not in rc and 'OpenELAB' not in (a.get('supplier') or '')]
        if r['key'] in ('bearing_61812', 'bearing_6201') and row['alternates']:
            a = row['alternates'].pop(0)                             # the plan: the cheaper seller first, McMaster the backup
            row['alternates'].insert(0, {'supplier': 'McMaster-Carr', 'part_number': r.get('part_number'), 'url': url,
                                         'price': f"${r.get('price_usd_each'):.2f}", 'price_usd_each': r.get('price_usd_each')})
            row.update(vendor=a['supplier'], model=a['part_number'], price_usd=a['price_usd_each'], pack_qty=a.get('pack_qty') or 1,
                       pack_price_usd=a['price_usd_each'] * (a.get('pack_qty') or 1), url=a['url'], stock=a.get('stock'),
                       name=f"{a['part_number']} ({'60 x 78 x 10' if '6812' in a['part_number'] else '12 x 32 x 10'})")
        rows.append(row)
    for m in load('exports/leg/bom.json', {}).get('made_to_order', []):         # D46: the machined output adapters
        lo, hi = EST.get(m['key'], (m.get('price_estimate_usd_each'), m.get('price_estimate_usd_each')))
        EST[m['key']] = (lo, hi)
        rows.append({'key': m['key'], 'group': 'leg', 'qty': m['qty'], 'name': f"Output adapter, machined {m.get('material', '')}".strip(),
                     'used_for': f"two per leg, made from `{m['step']}` with the callouts in `{Path(m['step']).parent}/README.md` (D46)",
                     'vendor': m['vendor'].split(' (')[0], 'model': Path(m['step']).name, 'price_usd': m.get('price_usd_each'), 'pack_qty': 1,
                     'pack_price_usd': None, 'url': 'https://jlccnc.com/', 'stock': None, 'checked': None,
                     'alternates': [{'supplier': m.get('backup', '').split(' (')[0], 'part_number': Path(m['step']).name,
                                     'url': 'https://www.xometry.com/', 'price': 'instant price on upload'}],
                     'notes': m.get('price_note', '')})
    return rows, d46


def rig_lines() -> list:
    rows = []
    for it in load('catalog/rig.json', []):
        b = (it.get('buy') or [{}])[0]
        m = SHARED.search(it.get('notes') or '')
        rows.append({'key': it['key'], 'group': it['group'], 'qty': it['qty'], 'name': it['name'], 'used_for': it.get('used_for', ''),
                     'vendor': it['vendor'], 'model': it['model'], 'price_usd': it['price_usd'], 'pack_qty': it.get('pack_qty') or 1,
                     'pack_price_usd': it.get('pack_price_usd'), 'url': b.get('url'), 'stock': b.get('stock_text'),
                     'in_stock': b.get('in_stock'), 'ships_from': b.get('ships_from'),
                     'checked': it.get('price_checked'), 'alternates': it.get('alternates', []), 'notes': it.get('notes', ''),
                     'confidence': it.get('confidence'), 'shared_key': m.group(2) if m else None})
    return rows


def add_bench_extra(rows: list) -> list:
    """BENCH_EXTRA onto the lines that already buy the part (one order line, one pack); returns the bench's uses."""
    uses = []
    for key, qty, why in BENCH_EXTRA:
        hit = [r for r in rows if r['key'] == key or r.get('shared_key') == key]
        if not hit:
            raise SystemExit(f'BENCH_EXTRA {key}: no line buys it')
        r = hit[0]
        r.setdefault('used_for_base', r.get('used_for') or '')
        r['qty'] += qty
        r['bench_qty'] = r.get('bench_qty', 0) + qty
        r['used_for'] = (r.get('used_for') or '') + f'; +{qty} for the bench ({why})'
        uses.append((r, qty, why))
    return uses


def filament_lines() -> list:
    mats = load('catalog/materials.json', {})
    grams = {}
    skip = {'output_adapter'}                                     # D46: machined now
    for p in ('exports/leg/print-plan.json', 'exports/rig/print-plan.json', 'exports/rig/bench/print-plan.json'):
        plan = load(p)
        if not plan:
            continue
        for name, r in plan['parts'].items():
            if name in skip and 'leg' in p:
                continue
            grams[r['material']] = grams.get(r['material'], 0) + r['grams']
    rows = []
    names = {'pa6-cf': 'Bambu Lab PA6-CF (hardened nozzle; dried 8-12 h at 80 C)', 'petg': 'Bambu Lab PETG Basic', 'tpu95': 'Bambu Lab TPU 95A HF'}
    for m, g in sorted(grams.items()):
        spools = math.ceil(g * 1.25 / 1000)                        # supports, purges, a reprint
        if m == 'pa6-cf':
            spools = max(spools, math.ceil(g / 1000) + 1)          # a spare spool: the hip frame is 51 h on one
        price = mats.get(m, {}).get('price_usd_per_kg')
        rows.append({'key': f'filament_{m}', 'group': 'filament', 'qty': spools, 'name': f'{names.get(m, m)}, 1 kg spool',
                     'used_for': f'{g / 1000:.2f} kg of parts (leg, rig, bench fixtures and coupons) + 25 % for supports, purge and a reprint',
                     'vendor': 'Bambu Lab (US store)', 'model': names.get(m, m), 'price_usd': price, 'pack_qty': 1, 'pack_price_usd': price,
                     'url': 'https://us.store.bambulab.com/', 'stock': None, 'checked': '2026-10-25 (catalog/materials.json)',
                     'alternates': [{'supplier': 'Gigaparts', 'price': '$79.99/kg PA6-CF, in stock (read 2026-10-27, docs/leg-prototype-plan.md 6.1)'}] if m == 'pa6-cf'
                     else [{'supplier': 'any maker', 'price': f'the same material ({m}); the print plans assume Bambu\'s settings'}],
                     'notes': ''})
    return rows


def cost(r) -> float:
    if r['price_usd'] is None:
        lo, hi = EST.get(r['key'], (0.0, 0.0))
        return (lo + hi) / 2 * r['qty']
    pk = r.get('pack_qty') or 1
    if pk > 1:
        return (r.get('pack_price_usd') or r['price_usd'] * pk) * math.ceil(r['qty'] / pk)
    return r['price_usd'] * r['qty']


def fmt_price(r) -> str:
    if r['price_usd'] is None:
        lo, hi = EST.get(r['key'], (None, None))
        if not lo:
            return 'instant price on upload'
        return f'instant price on upload (est. ${lo:.0f}' + (f'-{hi:.0f}' if hi != lo else '') + ' each)'
    pk = r.get('pack_qty') or 1
    if pk > 1:
        return f"${r.get('pack_price_usd') or r['price_usd'] * pk:.2f} per {pk}"
    return f"${r['price_usd']:.2f}"


def link(text, url):
    return f'[{text}]({url})' if url else text


def backup(r) -> str:
    a = (r.get('alternates') or [])
    if not a:
        return ''
    a = a[0]
    price = a.get('price') or (f"${a['price_usd_each']:.2f}" if a.get('price_usd_each') else '')
    s = f"{a.get('supplier', '')} {a.get('part_number') or ''}".strip()
    extra = f" ({a['changes']})" if a.get('changes') else ''
    return f"{link(s, a.get('url'))}, {price}{extra}"


def seller_rows(r) -> list:
    pk = r.get('pack_qty') or 1
    pp = r.get('pack_price_usd') or (r['price_usd'] * pk if r.get('price_usd') is not None else None)
    out = [{'seller': r['vendor'], 'url': r['url'], 'seller_pn': r['model'], 'price_usd': pp, 'pack_qty': pk, 'stock': r.get('stock'),
            'in_stock': r.get('in_stock'), 'ships_from': r.get('ships_from'), 'read_on': r.get('checked')}]
    for a in r.get('alternates') or []:
        apk = a.get('pack_qty') or 1
        out.append({'seller': a.get('supplier'), 'url': a.get('url'), 'seller_pn': a.get('part_number'),
                    'price_usd': a['price_usd_each'] * apk if a.get('price_usd_each') is not None else None, 'pack_qty': apk,
                    'stock': a.get('stock'), 'read_on': a.get('checked'), 'drop_in': a.get('drop_in', True), 'changes': a.get('changes'),
                    'price_text': a.get('price')})
    return out


def bom_row(r, qty, why) -> dict:
    return {'key': r.get('shared_key') or r['key'], 'qty': qty, 'for': why, 'name': r['name'], 'vendor': r['vendor'],
            'part_number': r['model'], 'price_usd_each': r.get('price_usd'), 'pack_qty': r.get('pack_qty') or 1,
            'sellers': seller_rows(r)}


def write_bom(rows: list, bench_uses: list) -> dict:
    """exports/rig/bom.json for the build page (designer/build.js reads its lists, made_to_order and sellers)."""
    lists = OrderedDict((g, []) for g in ('rig', 'electronics', 'bench'))
    made = []
    for r in rows:
        if r['group'] not in lists:
            continue
        if r['key'] == 'carriage_plate':
            made.append({'key': 'carriage_plate', 'qty': r['qty'],
                         'vendor': 'SendCutSend (sendcutsend.com: upload the STEP or DXF for the instant price)',
                         'backup': 'Xometry (xometry.com: instant quote from the STEP)',
                         'material': '6061-T6 aluminium, 0.250 in (6.35 mm)', 'mass_g_each': 1609, 'size_mm': [300, 320, 6.35],
                         'step': 'exports/rig/sendcutsend/carriage_plate.step', 'drawing': 'exports/rig/sendcutsend/carriage_plate.dxf',
                         'readme': 'exports/rig/sendcutsend/README.md',
                         'spec': ['6061-T6 aluminium sheet, 0.250 in; laser or waterjet cut from the file as drawn (mm, 1:1)',
                                  'Every hole is a clearance hole: no tapping, no countersinks, no bends',
                                  'Deburr on (the blocks and the hip frame sit on both faces)',
                                  'Check on arrival: the 16 block holes against an HGH15CA block (M4 on 38 x 30), the 6 hip-frame holes '
                                  'against the frame (exports/rig/sendcutsend/README.md)'],
                         'price_usd_each': None, 'price_estimate_usd_each': sum(EST['carriage_plate']) / 2,
                         'price_note': 'an estimate until the instant price is read on upload (D40: no quotes); SendCutSend ships in '
                                       'about a week'})
            continue
        own = r['qty'] - r.get('bench_qty', 0)
        if own > 0:
            lists[r['group']].append(bom_row(r, own, r.get('used_for_base', r.get('used_for') or '')))
    for r, qty, why in bench_uses:
        lists['bench'].append(bom_row(r, qty, why))
    doc = OrderedDict(lists)
    doc['made_to_order'] = made
    doc['price_usd'] = round(sum(cost(dict(r, qty=r['qty'])) for r in rows if r['group'] in ('rig', 'electronics', 'bench')
                                 and r['key'] != 'carriage_plate'), 2)
    doc['made_to_order_estimate_usd'] = round(sum(m['price_estimate_usd_each'] * m['qty'] for m in made), 2)
    doc['made_by'] = 'tools/rig_orders.py from catalog/rig.json (tools/rig_catalog.py)'
    BOM.write_text(json.dumps(doc, indent=1) + '\n')
    return doc


def main():
    leg, d46 = leg_lines()
    rows = leg + rig_lines() + filament_lines()
    bench_uses = add_bench_extra(rows)
    bom = write_bom(rows, bench_uses)
    by_vendor = OrderedDict()
    for r in rows:
        v = (r['vendor'] or '?').split(' (')[0]
        by_vendor.setdefault(v, []).append(r)
    groups = OrderedDict([('leg', 'The leg (one leg)'), ('filament', 'Filament'), ('rig', 'The rig: guide, frame, ballast, safety'),
                          ('electronics', 'Electronics and wiring'), ('bench', 'The bench tests (B1-B6)')])
    tot = {g: sum(cost(r) for r in rows if r['group'] == g) for g in groups}
    upload = [r for r in rows if r['price_usd'] is None]
    L = []
    L.append('# Leg rig: the order list (milestone M3)\n')
    L.append('Everything the first leg and its single-leg test rig need that is not printed: bought off the shelf with a listed price, '
             'or a custom part ordered online at an instant price (docs/decisions.yaml D40: nothing on quote). Prices and stock as read '
             'on 2026-10-27 unless a line says otherwise; links go to the product page. Generated by `tools/rig_orders.py` from '
             '`catalog/rig.json`, `exports/leg/bom.json` and the print plans: re-run it after a price check.\n')
    if d46:
        L.append('The leg\'s lines include D46 (the main session, 2026-10-27): the two output adapters are machined 6061-T6 (JLCCNC, '
                 'below), fixed by 9 x M5 x 25 per motor with no washers; the face takes 8 dowels and the frame 6 M5 inserts. '
                 '`exports/leg/bom.json` on this branch predates it, so those counts are corrected here.\n')
    L.append('## Totals\n')
    L.append('| Group | Lines | Cost |')
    L.append('|---|---|---|')
    for g, title in groups.items():
        n = sum(1 for r in rows if r['group'] == g)
        L.append(f"| {title} | {n} | ${tot[g]:,.2f} |")
    L.append(f"| **All** | {len(rows)} | **${sum(tot.values()):,.2f}** |")
    L.append('')
    L.append('Shipping, tax and the motors\' duties are not included. Upload-priced parts count at the middle of their estimate: '
             + ', '.join(f"{r['name'].split(',')[0]} ({fmt_price(r)})" for r in upload) + '. Several lines buy a pack (McMaster sells '
             'screws by 25-100): the cost is the packs\'.\n')
    L.append('## Order first (long leads)\n')
    L.append('1. **RobStride RS-04 x 2**: Seeed Studio (China warehouse; 1-3 weeks). Everything on the bench waits on them: order today.\n'
             '2. **ODrive BotWheels (2-pack)**: the second wheel is the robot\'s other leg.\n'
             '3. **LCSC (China)**: the GH headers; **BIQU (China)**: the U2C adapter. Same week as the motors.\n'
             '4. **Bearings Direct**: only 5 x 6812-2RS on hand; the leg needs 4.\n'
             '5. **SendCutSend** (the carriage plate) and **JLCCNC** (the two adapters): upload the files, read the instant price, order.\n'
             '6. Everything else ships in days (MISUMI same day; McMaster next day; Adafruit, SparkFun, TTI, AutomationDirect, Galco in stock).\n')
    L.append('## By vendor\n')
    L.append('| Vendor | Lines | Cost |')
    L.append('|---|---|---|')
    for v, rs in sorted(by_vendor.items(), key=lambda kv: -sum(cost(r) for r in kv[1])):
        L.append(f'| {v} | {len(rs)} | ${sum(cost(r) for r in rs):,.2f} |')
    L.append('')
    for g, title in groups.items():
        L.append(f'## {title}\n')
        L.append('| Part | Qty | Buy (primary) | Price | Stock | Cost | Backup | For |')
        L.append('|---|---|---|---|---|---|---|---|')
        for r in [r for r in rows if r['group'] == g]:
            name = r['name'].replace('|', '/')
            prim = link(f"{r['vendor']} {r['model'] or ''}".strip(), r['url'])
            note = f" ({r['notes']})" if r.get('notes') else ''
            L.append(f"| {name} | {r['qty']} | {prim} | {fmt_price(r)} | {r.get('stock') or ''} | ${cost(r):,.2f} | {backup(r)} | "
                     f"{(r.get('used_for') or '').replace('|', '/')}{note.replace('|', '/')} |")
        L.append('')
    L.append('## Checked on arrival\n')
    L.append('- **Rails:** both blocks run smooth with no play by hand; the rail\'s hole pitch (60) and end distance (20) as drawn.\n'
             '- **Dock adapters:** each DCB609 seats and reads 20-21 V on its adapter\'s leads (20 V mode); the pair in series reads 40-41 V.\n'
             '- **Contactor:** the + terminal goes to the pack side (its contacts are polarised).\n'
             '- **Weight plates:** weigh each; the ballast table in `exports/rig/rig.json` assumes 0.567 and 1.134 kg.\n'
             '- **Motors:** firmware version (`python -m rig.rs04 --id 127 version`); the 310 mm leads and their XT30 and GH plugs.\n')
    L.append('## Considered, not bought\n')
    L.append('- **RobStride Discharge Module** (the regeneration bleeder, rcdrone $47.55, sold out 2026-10-27): the power-off damping B1 '
             'measures is the motor\'s own `damper` switch (parameter 0x702A), which needs no module; and the module starts bleeding at '
             '64 V, above the RS-04\'s 60 V trip, so it would not protect the rig\'s bus. The pack absorbs regeneration; jumps start at '
             'or under 57.5 V - 27 A x the pack\'s resistance (docs/leg-bench-tests.md).\n'
             '- **HGR20 rails** as the stronger backup: their 44 mm blocks overlap at the post\'s 40 mm slot spacing.\n'
             '- **80/20 extrusions:** a different slot; only as a whole-frame swap.\n'
             '- **A rocker switch on the pod:** the pack\'s XT60 is the master disconnect; the contactor only closes with the pendant held.\n'
             '- **The load cells under jumps:** 3.4 kN would crush 50 kg cells; the load plate is for stand and squat only.\n')
    OUT.write_text('\n'.join(L) + '\n')
    print(f'{len(rows)} lines, ${sum(tot.values()):,.2f}: ' + ', '.join(f'{g} ${t:,.0f}' for g, t in tot.items()))
    print(f"exports/rig/bom.json: {', '.join(f'{k} {len(v)}' for k, v in bom.items() if isinstance(v, list))}, ${bom['price_usd']:,.2f}"
          f" + made to order ~${bom['made_to_order_estimate_usd']:,.0f}")


if __name__ == '__main__':
    main()
