#!/usr/bin/env python3
"""JLCPCB's instant price for the fuse board, read the way a person reads it (D40: an instant price, never a quote):
the gerber zip uploaded on cart.jlcpcb.com/quote (no account is needed for a price), the board's options picked (2
layers, 1.6 mm FR-4, 5 pieces, 2 oz outer copper, lead-free HASL, green), then the price and the build time read off
the page. Nothing is put in a cart and nothing is ordered.

    .venv/bin/python hardware/fuse-board/jlcpcb_quote.py [--shots DIR]

Writes hardware/fuse-board/fab/jlcpcb-price.json. Needs Playwright with the system Chrome (as tools/sendcutsend_quote.py).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZIP = HERE / 'fab' / 'fuse-board-gerbers.zip'
OUT = HERE / 'fab' / 'jlcpcb-price.json'
URL = 'https://cart.jlcpcb.com/quote'
WANT = {'qty': '5', 'thickness': '1.6', 'outer': '2 oz', 'finish': 'LeadFree HASL'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', help='a folder for screenshots of each step')
    ap.add_argument('--headed', action='store_true')
    a = ap.parse_args()
    shots = Path(a.shots) if a.shots else None
    n = [0]
    from playwright.sync_api import sync_playwright

    def shot(pg, tag):
        if shots:
            shots.mkdir(parents=True, exist_ok=True)
            n[0] += 1
            pg.screenshot(path=str(shots / f'{n[0]:02d}_{tag}.png'), full_page=True)

    res = {'url': URL, 'file': str(ZIP.relative_to(HERE.parents[1])), 'read_on': datetime.date.today().isoformat(), 'wanted': WANT}
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', headless=not a.headed)
        pg = b.new_context(viewport={'width': 1500, 'height': 1100}, locale='en-US').new_page()
        pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
        time.sleep(8)
        for txt in ('Accept All', 'Accept all', 'Got it', 'I agree'):
            loc = pg.get_by_role('button', name=re.compile(txt, re.I))
            if loc.count():
                try:
                    loc.first.click(timeout=3000)
                    time.sleep(1)
                except Exception:
                    pass
        shot(pg, 'open')
        pg.locator('input[type=file]').first.set_input_files(str(ZIP))
        time.sleep(25)
        shot(pg, 'uploaded')
        body = pg.inner_text('body')

        def pick(label, option):
            """Click the option button in the row whose label matches."""
            row = pg.locator('div', has=pg.get_by_text(re.compile(r'^\s*' + re.escape(label), re.I))).filter(
                has=pg.get_by_text(re.compile(r'^\s*' + re.escape(option) + r'\s*$', re.I)))
            target = row.last.get_by_text(re.compile(r'^\s*' + re.escape(option) + r'\s*$', re.I)).first
            target.scroll_into_view_if_needed()
            target.click(timeout=10000)
            time.sleep(2.5)
            return True

        picked = {}
        for label, option in (('Outer Copper Weight', WANT['outer']), ('Surface Finish', 'LeadFree HASL')):
            try:
                picked[label] = option if pick(label, option) else None
            except Exception as e:
                picked[label] = f'not picked: {str(e)[:120]}'
        body = pg.inner_text('body')
        m = re.search(r'PCB Qty\s*\n\s*(\d+)', body)
        picked['PCB Qty (as shown)'] = m.group(1) if m else None
        picked['PCB Thickness'] = '1.6 mm (JLCPCB\'s default, highlighted on the page; see the screenshot)'
        res['picked'] = picked
        time.sleep(4)
        shot(pg, 'options')
        body = pg.inner_text('body')
        tail = body[body.find('Charge Details'):][:1500] if 'Charge Details' in body else body[-3000:]
        res['charge_text'] = tail[:600]
        def money(label):
            m = re.search(re.escape(label) + r'\s*\n?\s*\$\s?([\d.]+)', tail)
            return float(m.group(1)) if m else None
        res['charges'] = {k: money(k) for k in ('Special Offer', 'Via Covering', 'Surface Finish', 'Outer Copper Weight')}
        m = re.search(r'Calculated Price[\s\S]*?\$([\d.]+)\s*\n\s*Web[\s\S]*?\$([\d.]+)\s*\n\s*JLCONE', tail)
        res['total_usd_web'] = float(m.group(1)) if m else None
        res['total_usd_desktop_app'] = float(m.group(2)) if m else None
        m = re.search(r'Shipping Estimate\s*\n\s*\$([\d.]+)\s*\n\s*([^\n]+)\s*\n\s*([^\n]+)', tail)
        res['shipping_estimate'] = {'usd': float(m.group(1)), 'method': m.group(2).strip(), 'time': m.group(3).strip()} if m else None
        m = re.search(r'PCB Build Time\s*\n?\s*(\d+ days?)', tail)
        res['build_time'] = m.group(1) if m else None
        m = re.search(r'Detected (\d+) layer board of ([\d.]+)x([\d.]+)mm', body)
        res['detected'] = m.group(0) if m else None
        res['each_usd_web'] = round(res['total_usd_web'] / int(WANT['qty']), 2) if res['total_usd_web'] else None
        b.close()
    OUT.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'charge_text'}, indent=1))


if __name__ == '__main__':
    main()
