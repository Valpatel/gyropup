"""The RS-04 build profiles (hardware/actuators/rs04/profiles/*.json): the limits the configuration tool and its bridge
enforce, and the settings a motor should hold. Versioned JSON, read by the browser tool and rig/rs04_bridge.py.

    python -m rig.rs04_profiles             # list the profiles and check every sourced number against its source

A number with a 'sources' entry is consumed from another file (a JSON pointer into a generated export, or a #define in
the firmware's gp_config.h) and must equal it: change the source, never only the profile. A source or reference marked
'pending' names the open issue or PR that will create or replace it; until then a missing file is allowed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'hardware' / 'actuators' / 'rs04' / 'profiles'
SCHEMA = 'gyropup.rs04-profile/1'
LIMITS = ('limit_torque_nm', 'jog_torque_nm', 'jog_speed_rad_s', 'jog_kp_max', 'jog_kd_max', 'can_timeout_ticks',
          'can_timeout_max_ticks')


def names() -> List[str]:
    return sorted(p.stem for p in DIR.glob('*.json') if p.stem != 'index')


def load(name: Optional[str] = None) -> dict:
    """A profile by id (the default one when None), checked for shape and sane limits (ValueError otherwise)."""
    profiles = {n: json.loads((DIR / f'{n}.json').read_text()) for n in names()}
    if name is None:
        defaults = [n for n, p in profiles.items() if p.get('default')]
        if len(defaults) != 1:
            raise ValueError(f'exactly one profile must be the default, found {defaults}')
        name = defaults[0]
    if name not in profiles:
        raise ValueError(f'no RS-04 profile {name!r}; known: {", ".join(profiles)}')
    p = profiles[name]
    validate(p)
    return p


def validate(p: dict) -> None:
    if p.get('schema') != SCHEMA:
        raise ValueError(f'{p.get("id")}: schema {p.get("schema")!r}, expected {SCHEMA}')
    lim = p['limits']
    missing = [k for k in LIMITS if not isinstance(lim.get(k), (int, float))]
    if missing:
        raise ValueError(f'{p["id"]}: limits missing {missing}')
    if not 0 < lim['jog_torque_nm'] <= lim['limit_torque_nm'] <= 120:
        raise ValueError(f'{p["id"]}: needs 0 < jog torque <= cap <= 120 N m')
    if not 0 < lim['jog_speed_rad_s'] <= 15 or not 0 <= lim['jog_kp_max'] <= 5000 or not 0 <= lim['jog_kd_max'] <= 100:
        raise ValueError(f'{p["id"]}: jog speed or gains outside the RS-04 MIT range')
    if not 1 <= lim['can_timeout_ticks'] <= lim['can_timeout_max_ticks']:
        raise ValueError(f'{p["id"]}: canTimeout must stay on and within the maximum')
    if p['motor_config'].get('limit_torque', 0) > lim['limit_torque_nm']:
        raise ValueError(f'{p["id"]}: the stored limit_torque is over the cap')


def _pointer(doc, pointer: str):
    for part in [x.replace('~1', '/').replace('~0', '~') for x in pointer.strip('/').split('/') if x]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def resolve(src: dict):
    """The value a source names, or None when its file does not exist yet."""
    f = ROOT / (src.get('json') or src.get('c_define') or '')
    if not f.is_file():
        return None
    if 'json' in src:
        return _pointer(json.loads(f.read_text()), src['pointer'])
    m = re.search(rf'^#define\s+{re.escape(src["name"])}\s+([-+0-9.eE]+)[fFuU]*\b', f.read_text(), re.M)
    if not m:
        raise ValueError(f'{src["c_define"]}: no #define {src["name"]}')
    return float(m.group(1))


def check(p: dict) -> List[str]:
    """Problems with a profile's sourced numbers and references (an empty list when it is consistent)."""
    out = []
    for path, src in p.get('sources', {}).items():
        sect, key = path.split('.', 1)
        have = p[sect][key]
        got = resolve(src)
        if got is None:
            if not src.get('pending'):
                out.append(f'{p["id"]}: {path}: source {src.get("json") or src.get("c_define")} does not exist')
            continue
        if abs(float(got) - float(have)) > 1e-9:
            out.append(f'{p["id"]}: {path} is {have} but its source says {got} ({src.get("json") or src.get("c_define")})')
    for ref in p.get('references', []):
        f = ROOT / ref['file']
        if not f.is_file():
            if not ref.get('pending'):
                out.append(f'{p["id"]}: reference {ref["file"]} does not exist')
            continue
        if 'pointer' in ref and f.suffix == '.json':
            try:
                _pointer(json.loads(f.read_text()), ref['pointer'])
            except (KeyError, IndexError, ValueError):
                out.append(f'{p["id"]}: reference {ref["file"]}#{ref["pointer"]} does not resolve')
    return out


def main(argv=None) -> int:
    bad = []
    for n in names():
        p = load(n)
        lim = p['limits']
        print(f'{n:10} v{p["version"]}{" (default)" if p.get("default") else "":10} cap {lim["limit_torque_nm"]:g} N m, '
              f'jog {lim["jog_torque_nm"]:g} N m at {lim["jog_speed_rad_s"]:g} rad/s, canTimeout {lim["can_timeout_ticks"]}')
        bad += check(p)
    for b in bad:
        print('error:', b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
