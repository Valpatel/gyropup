"""Pictures and alternate sources for parts-list lines, by catalogue key: enrich(lines) gives each bought line its
thumbnail (catalog/images.json, fetched by tools/part_images.py) and its alternates (catalog/alternates.json).

    from bom_media import enrich
    rows = enrich(rows)     # build_leg.py's bom() rows, build_turret.py's rows, or any list of dicts

Each line comes back as a copy with:
  media_key   the catalogue key used: the line's 'key' (the leg), its 'id' (the turret's catalogued parts), or the key
              catalog/sourcing.json gives the line's text ('item') or its name ('for'); None when there is none
  thumb       the picture's path from the repo root (a page in designer/ loads '../' + thumb), or None when it has not
              been fetched on this machine (vendor photos are gitignored: run tools/part_images.py)
  thumb_from  the page the picture came from
  alternates  [{supplier, part_number, url, price, price_usd_each, drop_in, changes, stock, checked}, ...]
  source      for a part no catalogue file has yet (catalog/sourcing.json parts): {vendor, part_number, url, price_usd}
  also        when one line buys several products ("panel fuse holder + 5 A fuse"): the same fields for the others
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CAT = R / 'catalog'


def _load(name: str, default):
    try:
        return json.loads((CAT / name).read_text())
    except FileNotFoundError:
        return default


def _items() -> dict:
    """Catalogue items by key and id, and the parts sourcing.json holds that no catalogue file has yet."""
    out = {}
    for f in dict.fromkeys(['hardware.json', *_load('index.json', {}).get('files', [])]):
        for it in _load(f, []):
            for k in (it.get('key'), it.get('id')):
                if k:
                    out.setdefault(k, it)
    for it in _load('sourcing.json', {}).get('parts', []):
        for k in (it.get('key'), it.get('id')):
            if k:
                out.setdefault(k, {**it, 'pending': True})
    return out


def keys_of(line: dict, sourcing: dict | None = None, items: dict | None = None) -> list:
    """The catalogue keys a line buys (usually one). [] when it buys nothing of its own or nothing says."""
    sourcing = _load('sourcing.json', {}) if sourcing is None else sourcing
    items = _items() if items is None else items
    names = sourcing.get('names') or {}
    for c in (line.get('key'), line.get('id')):
        if c and c in items:
            return [c]
    for c in (line.get('item'), line.get('name'), line.get('for'), line.get('key')):
        if c and c in names:
            k = names[c]
            return list(k) if isinstance(k, list) else [k]
    return []


def _media(key: str, images: dict, alternates: dict, items: dict) -> dict:
    img = images.get(key) or {}
    have = bool(img.get('path')) and (R / img['path']).exists()
    out = {'media_key': key, 'thumb': img['path'] if have else None, 'thumb_from': img.get('source_url'),
           'alternates': list(alternates.get(key) or [])}
    it = items.get(key) or {}
    if it.get('pending'):
        buy = (it.get('buy') or [{}])[0]
        out['source'] = {'vendor': it.get('vendor'), 'part_number': it.get('model'), 'name': it.get('name'),
                         'url': buy.get('url'), 'seller': buy.get('seller'), 'price_usd': it.get('price_usd')}
    return out


def enrich(lines):
    """Copies of the lines with media_key, thumb, thumb_from and alternates (and source / also where they apply)."""
    images, alternates, sourcing, items = _load('images.json', {}), _load('alternates.json', {}), _load('sourcing.json', {}), _items()
    out = []
    for line in lines:
        row = dict(line)
        keys = keys_of(row, sourcing, items)
        if not keys:
            row.update(media_key=None, thumb=None, thumb_from=None, alternates=[])
        else:
            row.update(_media(keys[0], images, alternates, items))
            if len(keys) > 1:
                row['also'] = [_media(k, images, alternates, items) for k in keys[1:]]
        out.append(row)
    return out


if __name__ == '__main__':                     # a quick look: the leg's last BOM, enriched
    bom = json.loads((R / 'exports' / 'leg' / 'bom.json').read_text())['per_leg']
    for r in enrich(bom):
        print(f"{r['key']:28} thumb={'yes' if r['thumb'] else 'NO ':3} alternates={len(r['alternates'])}")
