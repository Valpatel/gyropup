"""Check every catalog file against catalog/SCHEMA.md and write catalog/index.json for the designer.

    python tools/check_catalog.py          # prints problems; exit 1 if any are errors

Errors: not a list, missing id/category/vendor/model, duplicate ids, unknown category, a price without a check date,
a "price_usd" that is not a number or null, or an ownership field (the repo lists prices, not who owns what).
Warnings: no source, no buy link, no mass, a price older than 90 days.
"""
from pathlib import Path
from datetime import date
import json, re, sys

R = Path(__file__).resolve().parents[1]
C = R / 'catalog'
SKIP = {'index.json', 'materials.json', 'fabrication.json'}
CATEGORIES = set(re.findall(r'`(\w+)`', (C / 'SCHEMA.md').read_text().split('Categories:')[1].split('\n\n')[0]))


def main():
    errors, warnings, files, seen = [], [], [], {}
    for f in sorted(C.glob('*.json')):
        if f.name in SKIP:
            continue
        try:
            items = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            errors.append(f'{f.name}: not valid JSON ({e})')
            continue
        if not isinstance(items, list):
            errors.append(f'{f.name}: must be a JSON list of items')
            continue
        files.append(f.name)
        for i, it in enumerate(items):
            where = f'{f.name}[{i}] {it.get("id", "?")}'
            for k in ('id', 'category', 'vendor', 'model'):
                if not it.get(k):
                    errors.append(f'{where}: missing {k}')
            if it.get('id') in seen:
                errors.append(f'{where}: duplicate id (also in {seen[it["id"]]})')
            seen[it.get('id')] = f.name
            if it.get('category') not in CATEGORIES:
                errors.append(f'{where}: unknown category {it.get("category")!r}')
            if 'owned' in it:
                errors.append(f'{where}: remove "owned"; list the price instead')
            p = it.get('price_usd')
            if p is not None and not isinstance(p, (int, float)):
                errors.append(f'{where}: price_usd must be a number or null')
            if p is not None and not it.get('price_checked'):
                errors.append(f'{where}: price without price_checked')
            if it.get('price_checked'):
                try:
                    age = (date.today() - date.fromisoformat(it['price_checked'])).days
                    if age > 90:
                        warnings.append(f'{where}: price is {age} days old')
                except ValueError:
                    errors.append(f'{where}: price_checked is not YYYY-MM-DD')
            if not it.get('sources'):
                warnings.append(f'{where}: no sources')
            if not it.get('buy'):
                warnings.append(f'{where}: no buy link')
            if (it.get('specs') or {}).get('mass_g') is None:
                warnings.append(f'{where}: no mass')
    (C / 'index.json').write_text(json.dumps({'files': files, 'items': len(seen)}, indent=2) + '\n')
    for w in warnings:
        print('warn ', w)
    for e in errors:
        print('ERROR', e)
    print(f'{len(seen)} items in {len(files)} files: {len(errors)} errors, {len(warnings)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
