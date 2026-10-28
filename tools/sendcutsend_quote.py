#!/usr/bin/env python3
"""SendCutSend's instant price for the body's sheet parts, read the way a person reads it: each part's DXF uploaded to
app.sendcutsend.com (no account is needed for a price), its material and thickness picked, its bends, countersinks,
PEM nuts and taps added as the order sheet says, deburring chosen, the quantity set; then the price each, the
subtotal, the quantity breaks and the first ship date are read off the page (D40: an instant price, never a quote).

    .venv/bin/python tools/sendcutsend_quote.py                    # every part in exports/body/body.json
    .venv/bin/python tools/sendcutsend_quote.py --only bus_bar     # some of them
    .venv/bin/python tools/sendcutsend_quote.py --body exports/body/p2.json --out exports/body/sendcutsend/prices.json

Writes exports/body/sendcutsend/prices.json ({part: {...}}, merged with what is there), read by cad/body_bom.py into
bom.json's made_to_order lines. Nothing is put in a cart and nothing is ordered. Needs Playwright with the system
Chrome (as tools/mcmaster_cad.py). A part SendCutSend will not make as drawn (an operation refused, as the 1 in
minimum width for tapping on a narrow bar) is recorded with the app's own words, so the CAD can be changed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
APP = 'https://app.sendcutsend.com/'

# SendCutSend's menus for our stock (read in the app 2026-10-27)
MATERIAL = {'5052-H32 aluminium': ('Aluminum', '5052 H32 Aluminum'), '6061-T6 aluminium': ('Aluminum', '6061 T6 Aluminum'),
            'C110 copper': ('Copper', None)}
THICKNESS = {0.040: '.040" (1.0 MM)', 0.063: '.063" (1.6 MM)', 0.080: '.080" (2.0 MM)', 0.090: '.090" (2.3 MM)', 0.1: '.100" (2.5 MM)',
             0.125: '.125" (3.2 MM)', 0.187: '.187" (4.7 MM)', 0.25: '.250" (6.3 MM)'}
# countersinks: the app lists them as major / minor diameter (in) / angle; ours are ISO 10642 90 deg flat heads
COUNTERSINK = {'M3': '0.236 / 0.13 / 90°', 'M4': '0.315 / 0.164 / 90°', 'M5': '0.394 / 0.202 / 90°', 'M6': '0.472 / 0.255 / 90°'}
# PEM nuts: the app's catalogue category and item for each PEM part number on our drawings
HARDWARE = {'SS-M5-0': ('Nut', 'Nut, M5x0.8'), 'S-M4-0': ('Nut', 'Nut, M4x0.7'), 'S-M3-0': ('Nut', 'Nut, M3x0.5'),
            'F-M4-2': ('Flush Nut', None), 'F-M5-2': ('Flush Nut', None)}


def rx(t):
    return re.compile(r'^\s*' + re.escape(t) + r'\s*$', re.I)


def money(s):
    return float(s.replace(',', ''))


class App:
    """One browser on SendCutSend's quote page."""

    def __init__(self, p, shots: Path | None = None):
        self.b = p.chromium.launch(channel='chrome', headless=True)
        self.pg = self.b.new_context(viewport={'width': 1400, 'height': 1000}).new_page()
        self.shots = shots
        self.n = 0

    def shot(self, tag):
        if self.shots:
            self.n += 1
            self.shots.mkdir(parents=True, exist_ok=True)
            self.pg.screenshot(path=str(self.shots / f'{self.n:02d}_{tag}.png'))

    def click(self, text, wait=3.0, scope=None):
        s = scope or self.pg
        loc = s.get_by_role('button', name=rx(text))
        if loc.count() == 0:
            loc = s.get_by_text(rx(text))
        loc.last.click(timeout=20000)
        time.sleep(wait)

    def body(self):
        return self.pg.inner_text('body')

    def price(self):
        t = self.body()
        each = re.search(r'Qty\s*\n+\s*\$([\d,.]+)\s*\n+\s*/ea', t)
        sub = re.search(r'Subtotal:\s*\n+\s*\$([\d,.]+)', t)
        breaks = {int(q): money(v) for q, v in re.findall(r'\n(\d+) = \$([\d,.]+)\s*\n+\s*/ea', t)}
        ship = re.search(r'Arrives as soon as:\s*\n*\s*([A-Za-z]{3} \d{1,2})', t)
        return {'each': money(each.group(1)) if each else None, 'subtotal': money(sub.group(1)) if sub else None,
                'breaks': breaks, 'arrives': ship.group(1) if ship else None}

    def disabled_reason(self, service):
        """The app's tooltip on a greyed-out service panel, or None when the panel is enabled."""
        panel = self.pg.locator('.op-panel', has_text=service).first
        if 'disabled' not in (panel.get_attribute('class') or ''):
            return None
        panel.hover()
        time.sleep(1.5)
        tips = self.pg.locator('.tooltip-inner, [role=tooltip], .tooltip')
        txt = [tips.nth(i).inner_text().strip() for i in range(tips.count())]
        self.pg.mouse.move(5, 5)
        return re.sub(r'\s+', ' ', next((x for x in txt if x), 'disabled (no reason shown)')).replace(' LEARN MORE', '')

    def close_panel(self):
        """Close the service panel that is open (its own DONE or CLOSE button, not the page's), so the others show."""
        for name in ('Done', 'Close'):
            b = self.pg.locator('.op-panel').get_by_role('button', name=rx(name))
            for i in range(b.count()):
                if b.nth(i).is_visible():
                    b.nth(i).click()
                    time.sleep(2.0)
                    return True
        return False

    def close(self):
        self.b.close()


def order_of(part: dict, features: list) -> dict:
    """What to pick in the app for one part, from body.json's sheet order and its features."""
    cat, mat = MATERIAL[part['material']]
    taps = {}
    for f in features:
        m = re.match(r'tap (M\d+) x ([\d.]+)', f.get('note', ''))
        if m:
            taps[f"{f['d']:.3f}mm"] = f'{m.group(1)} x {m.group(2)}'
    return {'cat': cat, 'mat': mat, 'th': THICKNESS[round(part['thickness_in'], 3)], 'qty': part['qty'], 'bends': part['bends'],
            'csk': {k: COUNTERSINK[k] for k in (part.get('countersinks') or {})}, 'hw': dict(part.get('hardware') or {}), 'taps': taps}


def dropdown_rows(app, mapping, note):
    """Countersinking or tapping: each hole size's row, its dropdown set to the option (by hole diameter or by spec)."""
    done = {}
    rows = app.pg.locator('tr')
    for i in range(rows.count()):
        r = rows.nth(i)
        if not r.is_visible():                                # rows of a closed panel stay in the page
            continue
        txt = r.inner_text()
        m = re.search(r'([\d.]+)mm', txt)
        if not m or r.locator('.dropdown-trigger').count() == 0:
            continue
        dia = f'{float(m.group(1)):.3f}mm'
        want = mapping.get(dia)
        if want is None:
            continue
        r.locator('.dropdown-trigger').first.click()
        time.sleep(1.0)
        items = r.locator('.dropdown-item')
        opts = [items.nth(j).inner_text().strip() for j in range(items.count())]
        pick = next((j for j, o in enumerate(opts) if o == want or o.lower().startswith(want.lower())), None)
        if pick is None:
            raise RuntimeError(f'{note} {dia}: no option {want!r} in {opts}')
        items.nth(pick).click()
        time.sleep(2.0)
        done[dia] = opts[pick]
    return done


def quote(app: App, dxf: Path, o: dict) -> dict:
    out = {'file': str(dxf.relative_to(R)), 'refused': {}, 'picked': {}}
    app.pg.goto(APP, wait_until='domcontentloaded', timeout=60000)
    time.sleep(6)
    app.pg.query_selector_all('input[type=file]')[0].set_input_files(str(dxf))
    time.sleep(10)
    app.click('Confirm')                                     # the drawing's units (the DXF says mm)
    app.click('Metals')
    app.click(o['cat'])
    if o['mat']:
        app.click(o['mat'])
    app.click(o['th'], wait=4.0)
    out['cut_only'] = app.price()
    app.click('Next')
    if o['bends']:
        why = app.disabled_reason('Bending')
        if why:
            out['refused']['bending'] = why
        else:
            app.click('Bending')
            panel = app.pg.locator('.op-panel', has_text='Direction').first     # it retitles itself ("1 Bend") as angles go in
            n = panel.locator('input').count()
            for k in range(n):
                box = app.pg.locator('.op-panel', has_text='Direction').first.locator('input').nth(k)
                box.fill('90')
                box.press('Tab')
                time.sleep(1.0)
            app.close_panel()
            out['picked']['bending'] = f'{n} bends found in the DXF\'s BEND layer, each 90 deg UP'
            if n != o['bends']:
                out['refused']['bending'] = f'the app found {n} bend lines, the part has {o["bends"]}'
            time.sleep(2.0)
    for service, mapping in (('Countersinking', o['csk']), ('Tapping', o['taps'])):
        if not mapping:
            continue
        why = app.disabled_reason(service)
        if why:
            out['refused'][service.lower()] = why
            continue
        app.click(service)
        if service == 'Countersinking':                       # by hole size: M3 3.4, M4 4.5 in our drawings
            sizes = {'M3': '3.400mm', 'M4': '4.500mm', 'M5': '5.500mm', 'M6': '6.600mm'}
            mapping = {sizes[k]: v for k, v in mapping.items()}
        out['picked'][service.lower()] = dropdown_rows(app, mapping, service)
        app.shot(service)
        app.close_panel()
    if o['hw']:
        why = app.disabled_reason('Hardware Insertion')
        if why:
            out['refused']['hardware'] = why
        else:
            app.click('Hardware Insertion')
            import body_params as bp
            sizes = {f"{bp.PEM[k]['H']:.3f}mm": k for k in o['hw']}
            picked = {}
            for dia, spec in sizes.items():
                cat, item = HARDWARE[spec]
                row = app.pg.locator('tr', has_text=dia).filter(has=app.pg.get_by_text(re.compile('open catalog', re.I))).first
                row.get_by_text(re.compile('open catalog', re.I)).first.click()
                time.sleep(3.0)
                modal = app.pg.locator('.modal').last
                modal.get_by_text(cat, exact=True).first.click()
                time.sleep(2.5)
                names = [x.strip() for x in modal.inner_text().split('\n') if x.strip()]
                if item is None:                              # a flush nut: the one for this thread
                    thread = spec.split('-')[1] + 'x' + {'M4': '0.7', 'M5': '0.8', 'M3': '0.5'}[spec.split('-')[1]]
                    item = next((x for x in names if thread.lower() in x.lower()), None)
                if item is None or item not in names:
                    raise RuntimeError(f'hardware {spec}: {item!r} not in the catalogue: {names}')
                modal.get_by_text(item, exact=True).first.click()
                time.sleep(1.5)
                app.click('Apply', scope=modal)
                picked[dia] = f'{spec} -> {item}'
            out['picked']['hardware'] = picked
            app.shot('hardware')
            app.close_panel()
    out['with_services'] = app.price()
    app.click('Next')
    app.click('Deburring', wait=4.0)
    out['picked']['finish'] = 'Deburring'
    if o['qty'] != 1:                                         # the Qty box beside the price
        box = app.pg.locator('.field', has_text=re.compile(r'^\s*Qty', re.I)).locator('input')
        target = box.first if box.count() else app.pg.get_by_label(re.compile('qty', re.I)).first
        target.fill(str(o['qty']))
        target.press('Tab')
        time.sleep(4.0)
    out['final'] = app.price()
    out['qty'] = o['qty']
    app.shot('final')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--body', default=str(R / 'exports/body/body.json'))
    ap.add_argument('--out', default=str(R / 'exports/body/sendcutsend/prices.json'))
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--shots', help='a folder for screenshots of each step')
    a = ap.parse_args()
    sys.path.insert(0, str(R / 'cad'))
    from playwright.sync_api import sync_playwright
    import body_frame as bf
    body = json.loads(Path(a.body).read_text())
    parts = {'cheek': bf.cheek_part, 'floor_tray': bf.tray_part, 'belly_plate': bf.belly_part, 'deck': bf.deck_part,
             'compute_pallet': bf.pallet_part, 'power_plate': bf.power_plate_part, 'bus_bar': bf.bus_bar_part}
    outf = Path(a.out)
    res = json.loads(outf.read_text()) if outf.exists() else {}
    today = datetime.date.today().isoformat()
    with sync_playwright() as p:
        for name, s in body['sheet'].items():
            if a.only and name not in a.only:
                continue
            feats = []
            if name in parts:
                import body_layout as bl
                sp = parts[name](bl.layout()['mounts']) if name not in ('cheek', 'bus_bar') else parts[name]()
                feats = [{'d': f.d, 'note': f.note, 'kind': f.kind} for f in sp.features]
            o = order_of(s, feats)
            app = App(p, Path(a.shots) / name if a.shots else None)
            try:
                r = quote(app, R / s['dxf'], o)
            except Exception as e:
                app.shot('error')
                r = {'file': s['dxf'], 'error': str(e)[:400]}
            finally:
                app.close()
            r.update({'read_on': today, 'seller': 'SendCutSend', 'url': APP, 'order': o})
            res[name] = r
            outf.write_text(json.dumps(res, indent=1) + '\n')
            f = r.get('final') or {}
            print(f"{name:15} each ${f.get('each')}  subtotal ${f.get('subtotal')} (qty {o['qty']})  refused: {r.get('refused') or '-'}"
                  + (f"  ERROR {r['error']}" if 'error' in r else ''))


if __name__ == '__main__':
    main()
