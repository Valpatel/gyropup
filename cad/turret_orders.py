"""The bench turret's order sheets (docs/turret-prototype-plan.md T1): one page per seller from the parts list and the
catalogue, with what to buy, how many (whole packs), the listed price, the link and a backup seller for every line.

    .venv/bin/python cad/turret_orders.py        (cad/build_turret.py runs it after writing bom.json)

Writes exports/turret/bench/orders/<seller>.md and orders/README.md: the order to place them in (the parts with the
longest lead first), each seller's total, the SendCutSend upload, and the robot-only (v1) lines that are not ordered
now. Prices are the catalogue's (catalog/*.json, each with the date it was read); nothing here is ordered.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]
BENCH = R / 'exports' / 'turret' / 'bench'
OUT = BENCH / 'orders'
# the parts rule's sellers (docs/decisions.yaml D40); a line bought elsewhere is flagged on the summary page
D40_SELLERS = ('McMaster-Carr', 'Digi-Key', 'Mouser', 'SparkFun', 'Adafruit', 'Pololu', 'SendCutSend', 'Waveshare', 'SunnySky USA',
               'Palm Beach Bots', 'Repeat Robotics', 'AbleNet', 'FYSETC', 'Caldwell', 'IWISS', 'VXB Bearings')
# the order to place the orders in: the longest leads first (the servos ship from China, 1-3 weeks)
PRIORITY = ['Waveshare', 'SunnySky USA', 'Palm Beach Bots', 'Pololu', 'Adafruit', 'SparkFun', 'Digi-Key', 'Mouser', 'McMaster-Carr',
            'VXB Bearings', 'SendCutSend']
WHEN = {'Waveshare': 'Day one: the three servos are the critical path (Waveshare ships in about 3 business days, then 3-8 working days by UPS/DHL).',
        'SunnySky USA': 'Day one: the flywheel motors (the cartridge is printed after the motor is measured in hand, plan T2).',
        'SendCutSend': 'Day one: upload the drawing for an instant price; 3-5 days.'}


def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def catalogue():
    from build_turret import _catalogue                      # every catalogue item by id and key
    return _catalogue()


SAME_SELLER = {'VXB': 'VXB Bearings', 'Digikey': 'Digi-Key', 'DigiKey': 'Digi-Key'}       # one store under two names


def seller_name(b: dict | None) -> str:
    s = ((b or {}).get('seller') or '').split(' (')[0].strip() or 'unknown'
    return SAME_SELLER.get(s, s)


def money(x) -> str:
    return '' if x is None else f'${x:,.2f}'


def lines_from_bom(bom: dict, cat: dict, alts: dict) -> list[dict]:
    """One row per catalogue key with the quantities summed over the parts list's lines."""
    rows: dict[str, dict] = {}
    for sec in ('bench_turret', 'bench_stand', 'tools'):
        for r in bom.get(sec, []):
            if not r.get('qty'):
                continue
            k = r['key']
            row = rows.setdefault(k, {'key': k, 'qty': 0, 'for': [], 'section': sec})
            row['qty'] += r['qty']
            row['for'].append(r['for'])
    out = []
    for k, row in rows.items():
        it = cat.get(k) or {}
        buys = [b for b in (it.get('buy') or []) if b.get('url')]
        prim = buys[0] if buys else {}
        backup = buys[1] if len(buys) > 1 else None
        alt = (alts.get(k) or [None])[0]
        pack = it.get('pack_qty') or prim.get('pack_qty') or 1
        unit = it.get('price_usd')
        if it.get('pack_price_usd') is not None:
            pack_price = it['pack_price_usd']
        elif prim.get('price_usd') is not None and (prim.get('pack_qty') or 1) > 1 and 'ft' not in str(it.get('name', '')).lower():
            pack_price = prim['price_usd']
        else:
            pack_price = None if unit is None else unit * pack
        if pack > 1 and 'wire' in str(it.get('name', '')).lower():   # wire: the price is per spool, qty is in spools
            pack, pack_price = 1, unit
        packs = math.ceil(row['qty'] / pack) if pack else row['qty']
        out.append({**row, 'name': it.get('name') or it.get('model') or k, 'model': it.get('model'), 'vendor': it.get('vendor'),
                    'seller': seller_name(prim) if prim else (it.get('vendor') or 'unknown'), 'seller_pn': prim.get('seller_pn') or it.get('model'),
                    'url': prim.get('url'), 'unit': unit, 'pack': pack, 'packs': packs, 'pack_price': pack_price,
                    'cost': None if pack_price is None else round(packs * pack_price, 2), 'used': None if unit is None else round(row['qty'] * unit, 2),
                    'backup': ({'seller': seller_name(backup), 'pn': backup.get('seller_pn'), 'price': backup.get('price_usd'), 'url': backup.get('url')}
                               if backup else ({'seller': alt.get('supplier'), 'pn': alt.get('part_number'), 'price': alt.get('price_usd_each'), 'url': alt.get('url'),
                                                'changes': alt.get('changes') if not alt.get('drop_in') else None} if alt else None)),
                    'checked': it.get('price_checked'), 'note': it.get('price_note')})
    return out


def write(bom_path: Path = BENCH / 'bom.json') -> dict:
    bom = json.loads(bom_path.read_text())
    cat = catalogue()
    alts = json.loads((R / 'catalog' / 'alternates.json').read_text())
    rows = lines_from_bom(bom, cat, alts)
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r['seller'], []).append(r)
    order = sorted(by, key=lambda s: (PRIORITY.index(s) if s in PRIORITY else len(PRIORITY), -sum(x['cost'] or 0 for x in by[s])))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*.md'):
        old.unlink()
    totals = {}
    for n, s in enumerate(order, 1):
        rs = sorted(by[s], key=lambda r: (r['section'] != 'bench_turret', r['name']))
        tot = round(sum(r['cost'] or 0 for r in rs), 2)
        totals[s] = tot
        md = [f'# Order {n}: {s}', '', WHEN.get(s, ''), '',
              f'{len(rs)} lines, **{money(tot)}** before shipping and tax (whole packs). Prices as the catalogue read them (the date is per line in '
              '`catalog/*.json`); check the cart against this sheet. Each line has a backup seller in the last column.', '',
              '| # | Part | Seller part no. | For | Need | Buy | Each | Line | Backup |', '|---|---|---|---|---|---|---|---|---|']
        for k, r in enumerate(rs, 1):
            buy = f"{r['packs']} x {r['pack']}" if r['pack'] > 1 else str(r['packs'])
            link = f"[{r['name']}]({r['url']})" if r['url'] else r['name']
            b = r['backup']
            bk = '' if not b else (f"[{b['seller']} {b.get('pn') or ''}]({b['url']})" if b.get('url') else f"{b['seller']} {b.get('pn') or ''}") + \
                (f" {money(b['price'])}" if b.get('price') is not None else '') + (f" (not a drop-in: {b['changes'][:80]})" if b.get('changes') else '')
            fors = ', '.join(sorted(set(f.replace('el_', '').replace('hw_', '').replace('_', ' ') for f in r['for'])))[:60]
            line_cost = money(r['cost']) if r['cost'] is not None else ('instant price on upload' if s == 'SendCutSend' else 'not listed')
            md.append(f"| {k} | {link} | {r['seller_pn'] or ''} | {fors} | {r['qty']} | {buy} | {money(r['unit'])} | {line_cost} | {bk or 'none found'} |")
        (OUT / f'{n:02d}-{slug(s)}.md').write_text('\n'.join(md) + '\n')
    grand = round(sum(totals.values()), 2)
    off_rule = sorted({r['seller'] for r in rows if r['seller'] not in D40_SELLERS})
    no_backup = sorted(r['name'] for r in rows if not r['backup'])
    sheet = bom.get('ordered_to_drawing', {})
    md = ['# Ordering the bench turret (v0)', '',
          'Generated by `cad/turret_orders.py` from `exports/turret/bench/bom.json` and the catalogue: every bought line of the bench '
          'turret, its stand and the tools, by seller, in the order to place them. Nothing has been ordered. The robot-only (v1) lines are '
          'listed at the end and are not in the totals.', '',
          '| Order | Seller | Lines | Total | When |', '|---|---|---|---|---|']
    for n, s in enumerate(order, 1):
        shown = money(totals[s]) if totals[s] or s != 'SendCutSend' else 'on upload'
        md.append(f"| [{n}]({n:02d}-{slug(s)}.md) | {s} | {len(by[s])} | {shown} | {WHEN.get(s, 'with the first batch').split(':')[0]} |")
    md += ['', f'**Total: {money(grand)}** before shipping and tax (whole packs; the McMaster packs and the tools are most of the gap to the '
           '"parts used" figure).', '']
    if sheet:
        md += ['## The custom part (SendCutSend)', '']
        for name, s in sheet.items():
            md.append(f"- `{name}`: upload `{s['drawing']}` at {s.get('url', 'sendcutsend.com')} as **{s['name']}, {s['thickness_in']} in "
                      f"({s['thickness_mm']} mm)**, quantity 1, deburred, no finish. The instant price shows on upload.")
        md.append('')
    if off_rule:
        md += ['## Bought outside the parts rule\'s seller list', '',
               'No Digi-Key, Mouser, SparkFun, Adafruit, Pololu or McMaster listing was found for these sellers\' lines (docs/decisions.yaml D40): '
               + ', '.join(off_rule) + '. Each has a listed price and a link; check the backup column.', '']
    if no_backup:
        md += ['## Lines without a second seller yet', '', ', '.join(no_backup) + '.', '']
    v1 = bom.get('v1_only', [])
    if v1:
        md += ['## Not ordered now: the robot (v1) lines', '', '| Part | For | Qty |', '|---|---|---|']
        md += [f"| {r['item']} | {r['for']} | {r['qty']} |" for r in v1]
        md.append('')
    (OUT / 'README.md').write_text('\n'.join(md))
    summary = {'sellers': order, 'totals': totals, 'grand_total_usd': grand, 'lines': len(rows), 'off_rule_sellers': off_rule, 'no_backup': no_backup}
    (OUT / 'orders.json').write_text(json.dumps(summary, indent=1) + '\n')
    return summary


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(R / 'cad'))
    s = write()
    print(f"{s['lines']} lines from {len(s['sellers'])} sellers, ${s['grand_total_usd']:,.2f}; off the D40 list: {s['off_rule_sellers']}; "
          f"no backup: {s['no_backup']}")
