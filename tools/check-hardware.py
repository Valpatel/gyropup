"""The hardware folders keep their skeleton (hardware/README.md): every component folder under hardware/<category>/<name>/
has a README with the standard sections, an interfaces page and an inventory; every JSON parses and carries a schema;
every relative link in the folders' Markdown resolves; the map lists every folder; and every number a config file
takes from elsewhere (a #define, a JSON pointer, a line of a source file) still matches its source.

    python3 tools/check-hardware.py          # exit 1 with the problems listed
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / 'hardware'
CATEGORIES = ('actuators', 'drives', 'sensors', 'power', 'compute', 'comms', 'turret')
SECTIONS = ('References', 'Interfaces', 'Config and profiles', 'Driver', 'Inventory', 'Bring-up and tests', 'Open questions')
PCB_PROJECTS = ('fuse-board', 'carrier-packaging', 'carrier-pan-protection')
LINK = re.compile(r'\]\(([^)\s]+)\)')


def _pointer(doc, pointer: str):
    for part in [x.replace('~1', '/').replace('~0', '~') for x in pointer.strip('/').split('/') if x]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def _number(tok: str):
    t = tok.rstrip('uUlL')
    if t.lower().startswith(('0x', '-0x')):
        return int(t, 16)
    return float(t.rstrip('fF'))


def source_problems(rel, d: dict) -> list:
    """A gyropup.config/1 file's 'sources': each dotted path's value must equal what its source says.

    {"c_define": file, "name": NAME}   the #define's number (decimal, float or hex)
    {"json": file, "pointer": "/a/b"}   the value at that JSON pointer
    {"contains": file, "text": "...", "count": n}   the file holds that text verbatim (n times, when given: a
                                        string sent twice must still be sent twice)
    """
    out = []
    for path, src in d.get('sources', {}).items():
        have = d
        try:
            for k in path.split('.'):
                have = have[k]
        except (KeyError, TypeError):
            out.append(f'{rel}: sources names {path}, which the file does not have')
            continue
        f = ROOT / (src.get('c_define') or src.get('json') or src.get('contains') or '')
        if not f.is_file():
            out.append(f'{rel}: {path}: source {f.relative_to(ROOT)} does not exist')
            continue
        text = f.read_text()
        if 'contains' in src:
            want = src.get('text', have)
            n = text.count(want)
            if n == 0 or ('count' in src and n != src['count']):
                out.append(f'{rel}: {path}: {f.relative_to(ROOT)} contains {want!r} {n} time(s)'
                           + (f', not {src["count"]}' if 'count' in src else ''))
            continue
        if 'json' in src:
            try:
                got = _pointer(json.loads(text), src['pointer'])
            except (KeyError, IndexError, TypeError, ValueError):
                out.append(f'{rel}: {path}: {src["pointer"]} does not resolve in {f.relative_to(ROOT)}')
                continue
        else:
            m = re.search(rf'^#define\s+{re.escape(src["name"])}\s+(-?0[xX][0-9a-fA-F]+[uUlL]*|[-+0-9.eE]+[fFuUlL]*)\b', text, re.M)
            if not m:
                out.append(f'{rel}: {path}: no #define {src["name"]} in {src["c_define"]}')
                continue
            got = _number(m.group(1))
        ok = (abs(float(got) - float(have)) <= 1e-9) if isinstance(have, (int, float)) and isinstance(got, (int, float)) else got == have
        if not ok:
            out.append(f'{rel}: {path} is {have!r} but its source says {got!r}')
    return out


def components():
    for cat in CATEGORIES:
        d = HW / cat
        if d.is_dir():
            for c in sorted(p for p in d.iterdir() if p.is_dir()):
                yield cat, c


def links(md: Path):
    for target in LINK.findall(md.read_text()):
        if re.match(r'^[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
            continue
        yield target.split('#')[0]


def check() -> list:
    out = []
    readme = HW / 'README.md'
    if not readme.is_file():
        return ['hardware/README.md is missing']
    mapped = readme.read_text()
    for cat, c in components():
        rel = c.relative_to(ROOT)
        if f'{cat}/{c.name}/' not in mapped:
            out.append(f'hardware/README.md does not list {rel}/')
        r = c / 'README.md'
        if not r.is_file():
            out.append(f'{rel}: no README.md')
            continue
        heads = re.findall(r'^## (.+)$', r.read_text(), re.M)
        missing = [s for s in SECTIONS if s not in heads]
        if missing:
            out.append(f'{rel}/README.md: missing the sections {missing}')
        if not (c / 'interfaces.md').is_file():
            out.append(f'{rel}: no interfaces.md')
        inv = c / 'inventory.json'
        if not inv.is_file():
            out.append(f'{rel}: no inventory.json')
    for f in sorted(HW.rglob('*.json')):
        rel = f.relative_to(ROOT)
        if any(rel.parts[1] == p for p in PCB_PROJECTS):
            continue
        try:
            d = json.loads(f.read_text())
        except ValueError as e:
            out.append(f'{rel}: not JSON ({e})')
            continue
        if not isinstance(d, dict) or not str(d.get('schema', '')).startswith('gyropup.'):
            out.append(f'{rel}: no gyropup.* schema')
        if f.name == 'inventory.json':
            held = sum(a.get('count', 0) for k in ('arrived', 'held') for a in d.get(k, []))
            units = d.get('units', [])
            if len(units) != held:
                out.append(f'{rel}: {len(units)} unit records for {held} arrived or held')
        if d.get('schema') == 'gyropup.config/1':
            out += source_problems(rel, d)
    for p in PCB_PROJECTS:
        if f'{p}/' not in mapped:
            out.append(f'hardware/README.md does not list the existing {p}/')
    for md in [readme, *sorted(p for cat in CATEGORIES if (HW / cat).is_dir() for p in (HW / cat).rglob('*.md'))]:
        for t in links(md):
            if t and not (md.parent / t).resolve().exists():
                out.append(f'{md.relative_to(ROOT)}: broken link {t}')
    return out


if __name__ == '__main__':
    bad = check()
    for b in bad:
        print('error:', b)
    n = len(list(components()))
    print(f'hardware: {n} component folders, {len(bad)} problem(s)')
    sys.exit(1 if bad else 0)
