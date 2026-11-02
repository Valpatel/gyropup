#!/usr/bin/env python3
"""SendCutSend's instant price for every metal part of every option, and four probe plates that separate the price of
a bend and of a PEM nut. It drives the public quote page the way tools/sendcutsend_quote.py does (that tool's App and
quote(), imported, not changed): upload the DXF, pick the material and thickness, add the bends, countersinks, taps and
PEM nuts, pick deburring, set the quantity, read the price. No account, no cart, no order.

    .venv/bin/python research/body-sheet-metal/quote.py [--only cheek deck_2b] [--probes-only]

Writes research/body-sheet-metal/dxf/*.dxf (the flat patterns quoted) and research/body-sheet-metal/prices.json.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parts as P  # noqa: E402  (puts cad/ and tools/ on the path)

import body_params as bp  # noqa: E402
import body_sheet as bs  # noqa: E402
import sendcutsend_quote as q  # noqa: E402

R = P.R
OUT = HERE / 'prices.json'
DXF = HERE / 'dxf'


def probes() -> dict:
    """A 200 x 150 mm plate of 1/8 in 5052: flat with four plain holes, the same with two 20 mm lips, and flat with four
    and with twelve PEM SS-M5-0 nuts. The differences are the price of two bends and of a PEM nut."""
    hole = [(40.0, 40.0), (160.0, 40.0), (40.0, 110.0), (160.0, 110.0)]
    more = hole + [(70.0, 40.0), (100.0, 40.0), (130.0, 40.0), (70.0, 110.0), (100.0, 110.0), (130.0, 110.0), (40.0, 75.0), (160.0, 75.0)]
    mk = lambda pts, kind: [bs.Feature(kind, 'base', p, bp.PEM['SS-M5-0']['H'] if kind == 'pem' else 5.5,
                                       spec='SS-M5-0' if kind == 'pem' else '') for p in pts]
    return {'probe_flat': bs.SheetPart('probe_flat', '5052-0.125', 200.0, 150.0, features=mk(hole, 'hole')),
            'probe_2b': bs.SheetPart('probe_2b', '5052-0.125', 200.0, 150.0, flanges=[bs.Flange('S', 20.0), bs.Flange('N', 20.0)],
                                     features=mk(hole, 'hole')),
            'probe_4pem': bs.SheetPart('probe_4pem', '5052-0.125', 200.0, 150.0, features=mk(hole, 'pem')),
            'probe_12pem': bs.SheetPart('probe_12pem', '5052-0.125', 200.0, 150.0, features=mk(more, 'pem'))}


def every_part() -> dict:
    out = {}
    for opt, ps in P.options().items():
        for name, part in ps.items():
            out.setdefault(name, part)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--probes-only', action='store_true')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    todo = probes()
    if not a.probes_only:
        todo.update(every_part())
    DXF.mkdir(exist_ok=True)
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    today = datetime.date.today().isoformat()
    with sync_playwright() as pw:
        for name, part in todo.items():
            if a.only and name not in a.only:
                continue
            o = part.order()
            path = DXF / f"{name}_{part.stock}_x{part.qty}.dxf"
            part.export_dxf(path)
            feats = [{'d': f.d, 'note': f.note, 'kind': f.kind} for f in part.features]
            order = q.order_of({**o, 'material': o['material'], 'thickness_in': o['thickness_in']}, feats)
            app = q.App(pw)
            try:
                r = q.quote(app, path, order)
            except Exception as e:                     # recorded, never retried blindly
                r = {'file': str(path.relative_to(R)), 'error': str(e)[:400]}
            finally:
                app.close()
            r.update({'read_on': today, 'seller': 'SendCutSend', 'url': q.APP, 'order': order,
                      'flat_mm': o['flat_mm'], 'stock': part.stock})
            res[name] = r
            OUT.write_text(json.dumps(res, indent=1) + '\n')
            f = r.get('final') or {}
            print(f"{name:16} each ${f.get('each')} subtotal ${f.get('subtotal')} (qty {order['qty']}) cut-only ${(r.get('cut_only') or {}).get('each')}"
                  f" refused {r.get('refused') or '-'}" + (f"  ERROR {r['error']}" if 'error' in r else ''), flush=True)


if __name__ == '__main__':
    main()
