#!/usr/bin/env python3
"""Bought hardware from McMaster-Carr: download each part's STEP and product data, normalise its frame, and keep
catalog/hardware.json up to date. A thin wrapper over the cad-agent toolkit (cadagent.mcmaster, `cad-agent mcmaster`;
the process is in cad-agent's skills/mcmaster-parts/SKILL.md).

    .venv/bin/python tools/mcmaster_cad.py --catalog            # every item in catalog/hardware.json
    .venv/bin/python tools/mcmaster_cad.py --catalog --only screw_m5x20 knee_pin
    .venv/bin/python tools/mcmaster_cad.py 91290A242 --kind screw   # one part, no catalogue entry

catalog/hardware.json is a list of catalogue items (catalog/SCHEMA.md). Each item names its part (`model` = the
McMaster part number), `key` (our name for it), `cad.kind` (the frame convention), `used_for`, `qty_per_robot` and
`notes`, and optionally `choose` (option texts to click on the product page, e.g. ["Right Hand"]). This script fills
in the rest from the product page and the model: price per unit and per pack, buy link, mass, dimensions, material,
the whole McMaster specification table (specs.mcmaster.raw / .parsed), and the normalised CAD file and frame.

Files go in references/vendor/mcmaster/<PN>/ (<PN>.step as downloaded, <PN>.norm.step in our frame, <PN>.page.json,
<PN>.norm.json, SOURCE.txt). That folder is gitignored except SOURCE.txt: McMaster-Carr CAD is for design use, not
redistributed. Pages are read one at a time with a pause between them, like an engineer choosing parts; a part whose
STEP is already here is not downloaded again (--force to refresh it).

Needs Playwright in the venv (`.venv/bin/pip install playwright`; with Google Chrome installed nothing else is needed).
It is a tool dependency, not a requirement of the CAD build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cadagent import mcmaster as mc

R = Path(__file__).resolve().parents[1]
CATALOG = R / 'catalog/hardware.json'
VENDOR = R / 'references/vendor/mcmaster'
CATEGORY = {'bearing': 'bearing', 'rod_end': 'bearing', 'grommet': 'wiring'}      # everything else: fastener


def refresh(pn: str, kind: str, session, force: bool = False, choose=None):
    """Download (unless already here) and normalise one part. Returns (page, info, cad path relative to the repo)."""
    folder = VENDOR / pn
    step, page_file = folder / f'{pn}.step', folder / f'{pn}.page.json'
    if force or not step.exists():
        session.fetch(pn, folder, choose=choose)
    page = json.loads(page_file.read_text())
    material = mc.material_of(page.get('specs', {}).get('raw', {}))
    norm, info = mc.normalise(step, kind, material=material)
    (folder / f'{pn}.norm.json').write_text(json.dumps(info, indent=1) + '\n')
    return page, info, str(norm.relative_to(R))


def to_item(item: dict, page: dict, info: dict, cad: str) -> dict:
    """Our catalogue item (catalog/SCHEMA.md) from the toolkit's entry for the part."""
    kind = item.get('cad', {}).get('kind') or item.get('kind')
    e = mc.catalog_entry(page, info, cad=cad)
    pack, pack_price = e['pack_qty'] or 1, e['price_usd']
    specs = {f'{k}_mm' if isinstance(v, (int, float)) else k: v for k, v in e['dims_mm'].items()}
    specs.update({'mass_g': e['mass_g'], 'mass_basis': e['mass_basis'], 'material': e['material'],
                  'mcmaster': e['specs']})
    out = {
        'id': item['id'], 'key': item.get('key'), 'category': CATEGORY.get(kind, 'fastener'),
        'vendor': 'McMaster-Carr', 'model': page['pn'], 'name': page['description'],
        'price_usd': round(pack_price / pack, 4) if pack_price is not None else None,
        'price_note': f"McMaster-Carr: {page.get('price_text')} (price_usd is per piece)",
        'price_checked': page.get('read'), 'pack_qty': pack, 'pack_price_usd': pack_price,
        'buy': [{'seller': 'McMaster-Carr', 'url': page['url'], 'in_stock': None, 'ships_from': 'US'}],
        'specs': specs,
        'cad': {'file': cad, 'kind': kind, 'frame': mc.FRAMES[kind], 'available': True, 'step_url': page['url'],
                'bbox_mm': info['bbox_mm'], 'volume_mm3': info['volume_mm3']},
        'frame': mc.FRAMES[kind],
        'sources': [page['url']], 'confidence': 'product page',
        'used_for': item.get('used_for'), 'qty_per_robot': item.get('qty_per_robot'),
    }
    for k in ('choose', 'notes'):
        if item.get(k):
            out[k] = item[k]
    if page.get('options'):
        out['options'] = page['options']
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pns', nargs='*', metavar='PN', help='McMaster part numbers (with --kind)')
    ap.add_argument('--kind', choices=mc.KINDS, help='frame convention for the PNs given')
    ap.add_argument('--catalog', action='store_true', help=f'refresh every item in {CATALOG.relative_to(R)}')
    ap.add_argument('--only', nargs='+', metavar='KEY', help='with --catalog: just these keys')
    ap.add_argument('--force', action='store_true', help='download again even when the STEP is here')
    ap.add_argument('--delay', type=float, default=3.0, help='seconds between product pages (default 3)')
    a = ap.parse_args(argv)
    if not a.catalog and not a.pns:
        ap.error('give part numbers (with --kind) or --catalog')
    if a.pns and not a.kind:
        ap.error('--kind is needed with part numbers')
    rc = 0
    with mc.Session(delay_s=a.delay) as s:
        for pn in a.pns:
            page, info, cad = refresh(pn.upper(), a.kind, s, a.force)
            print(f"{pn}: {page['description']} | {page['price_text']} | bbox {info['bbox_mm']['size']} -> {cad}")
        if a.catalog:
            items = json.loads(CATALOG.read_text())
            for i, item in enumerate(items):
                if a.only and item.get('key') not in a.only:
                    continue
                pn, kind = item['model'], item.get('cad', {}).get('kind') or item.get('kind')
                try:
                    page, info, cad = refresh(pn, kind, s, a.force, item.get('choose'))
                except Exception as exc:                     # one bad part should not stop the others
                    print(f"{item.get('key')} ({pn}): FAILED {exc}", file=sys.stderr)
                    rc = 1
                    continue
                items[i] = to_item(item, page, info, cad)
                CATALOG.write_text(json.dumps(items, indent=1, ensure_ascii=False) + '\n')
                print(f"{item.get('key')}: {pn} {page['description']} | {page['price_text']} | bbox {info['bbox_mm']['size']}")
    return rc


if __name__ == '__main__':
    sys.exit(main())
