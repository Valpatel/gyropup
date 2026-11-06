"""The RS-04 units in hand (hardware/actuators/rs04/inventory.json), filled from the motor tool's config exports.

    python -m rig.rs04_inventory                                   # the four units, as recorded
    python -m rig.rs04_inventory add rs04-left-front-1a2b3c4d.json # a unit's record from the tool's Config -> Export
    python -m rig.rs04_inventory add export.json --mass-g 1512 --notes "scuff on the housing"
    python -m rig.rs04_inventory check                             # exit 1 if the file is malformed or inconsistent

A record is matched by the motor's unique id (the uid it answers a scan with); a new uid takes the first empty unit.
Nothing is typed in by hand: every field except mass and notes comes from the export, so a serial is never invented.
Two units may not share a uid, a CAN id or a joint.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

ROOT = (Path(__file__).resolve().parents[3])
FILE = ROOT / 'hardware' / 'actuators' / 'rs04' / 'inventory.json'
SCHEMA = 'gyropup.inventory/1'
EXPORT_SCHEMA = 'rs04-motor-config/1'
JOINTS = ('left-front', 'left-rear', 'right-front', 'right-rear')
FIELDS = ('unit', 'uid', 'can_id', 'joint', 'firmware', 'zero_offset_rad', 'zero_pose', 'mass_g', 'profile', 'exported', 'notes')


def load(path: Path = FILE) -> dict:
    return json.loads(path.read_text())


def problems(inv: dict) -> List[str]:
    out = []
    if inv.get('schema') != SCHEMA:
        out.append(f'schema is {inv.get("schema")!r}, not {SCHEMA}')
    units = inv.get('units', [])
    arrived = sum(a.get('count', 0) for a in inv.get('arrived', []))
    if len(units) != arrived:
        out.append(f'{len(units)} unit records for {arrived} arrived')
    for u in units:
        missing = [f for f in FIELDS if f not in u]
        if missing:
            out.append(f'unit {u.get("unit")}: missing {missing}')
        if u.get('uid') is not None and not re.fullmatch(r'[0-9a-f]{16}', str(u['uid'])):
            out.append(f'unit {u.get("unit")}: uid {u["uid"]!r} is not 8 bytes of hex')
        if u.get('can_id') is not None and not (isinstance(u['can_id'], int) and 1 <= u['can_id'] <= 127):
            out.append(f'unit {u.get("unit")}: CAN id {u["can_id"]!r} is not 1..127')
        if u.get('joint') is not None and u['joint'] not in JOINTS:
            out.append(f'unit {u.get("unit")}: joint {u["joint"]!r} is not one of {JOINTS}')
    for key in ('uid', 'can_id', 'joint'):
        vals = [u.get(key) for u in units if u.get(key) is not None]
        dup = sorted({v for v in vals if vals.count(v) > 1}, key=str)
        if dup:
            out.append(f'two units share {key} {dup}')
    return out


def add(inv: dict, export: dict, mass_g: Optional[float] = None, notes: Optional[str] = None) -> dict:
    """The record for an export, merged into inv (returned); raises ValueError on anything inconsistent."""
    if export.get('schema') != EXPORT_SCHEMA:
        raise ValueError(f'not a motor tool export ({EXPORT_SCHEMA})')
    uid = str(export.get('uid') or '')
    if not re.fullmatch(r'[0-9a-f]{16}', uid):
        raise ValueError(f'the export has no motor uid ({uid!r}): scan the motor first')
    units = inv['units']
    unit = next((u for u in units if u.get('uid') == uid), None) or next((u for u in units if u.get('uid') is None), None)
    if unit is None:
        raise ValueError(f'uid {uid} is not one of the {len(units)} units recorded and none is empty: record the arrival first')
    params = export.get('params') or {}
    zero = export.get('zero') or {}
    rec = dict(unit)
    rec.update({'uid': uid, 'can_id': export.get('can_id'), 'joint': export.get('joint'), 'firmware': export.get('firmware'),
                'zero_offset_rad': params.get('add_offset'), 'zero_pose': zero.get('pose', rec.get('zero_pose')),
                'profile': export.get('profile'), 'exported': export.get('exported')})
    if mass_g is not None:
        rec['mass_g'] = mass_g
    if notes is not None:
        rec['notes'] = notes
    trial = dict(inv, units=[rec if u is unit else u for u in units])
    bad = problems(trial)
    if bad:
        raise ValueError('; '.join(bad))
    return trial


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.rs04_inventory', description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd')
    a = sub.add_parser('add', help="a unit's record from the motor tool's config export")
    a.add_argument('export', type=Path)
    a.add_argument('--mass-g', type=float)
    a.add_argument('--notes')
    sub.add_parser('check')
    args = ap.parse_args(argv)
    inv = load()
    if args.cmd == 'add':
        try:
            inv = add(inv, json.loads(args.export.read_text()), args.mass_g, args.notes)
        except ValueError as e:
            print('error:', e)
            return 1
        FILE.write_text(json.dumps(inv, indent=2) + '\n')
        print(f'recorded uid {json.loads(args.export.read_text())["uid"]} in {FILE.relative_to(ROOT)}')
        return 0
    bad = problems(inv)
    if args.cmd == 'check':
        for b in bad:
            print('error:', b)
        return 1 if bad else 0
    for u in inv['units']:
        print(f'unit {u["unit"]}: ' + (', '.join(f'{k} {u[k]}' for k in FIELDS[1:] if u.get(k) not in (None, ''))
                                       or 'not scanned yet'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
