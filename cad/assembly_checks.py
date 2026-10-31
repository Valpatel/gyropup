"""Screw stacks: each screw's length against the stack it clamps and the thread it goes into. Shapes play no part: the
rows carry the numbers. The rest of the assembly checks (floating parts, interference, motion) are cad-agent's gates now
(cad/rig_gates.py, issue #14); this stays until the fastener gate's tool sweep has the rig's assembly steps.

    screw_stacks(rows)
"""
from __future__ import annotations

import math
from typing import Iterable, List, Mapping


def screw_stacks(rows: Iterable[Mapping]) -> List[dict]:
    """Each screw against what it clamps and what it threads into. A row:
        {'joint': str, 'd': mm, 'length': mm (under the head), 'clamp': [mm, ...] (the stack under the head),
         'thread': {'kind': 'tapped' | 'insert' | 'nut' | 'slot_nut', 'depth': mm available (a blind hole's or insert's
                    length, a nut's thickness), 'beyond': mm free behind it (a blind hole's bottom; inf when open)},
         'min_engage': mm (default 0.8 d; 1.0 d into aluminium or plastic)}
    The engagement is the length past the stack, cut to what the thread offers; the tip must stop before `beyond` runs
    out. Returns each row with engage_mm, tip_room_mm, ok and why."""
    out = []
    for r in rows:
        d, L = float(r['d']), float(r['length'])
        grip = sum(float(x) for x in r['clamp'])
        th = r['thread']
        depth, beyond = float(th['depth']), float(th.get('beyond', math.inf))
        past = L - grip
        engage = max(0.0, min(past, depth))
        tip_room = depth + beyond - past
        need = float(r.get('min_engage', 0.8 * d))
        why = []
        if past <= 0:
            why.append(f'too short: {L:g} mm under a {grip:g} mm stack')
        elif engage < need - 1e-9:
            why.append(f'{engage:.2f} mm of thread, {need:.2f} needed')
        if tip_room < -1e-9:
            why.append(f'the tip runs {-tip_room:.2f} mm past the room behind the thread')
        if th['kind'] == 'nut' and depth <= past < depth + float(r.get('pitch', 0.15 * d)):
            why.append('no thread showing past the nut')
        out.append({'joint': r['joint'], 'screw': f"M{d:g} x {L:g}" if 'name' not in r else r['name'], 'grip_mm': round(grip, 2),
                    'engage_mm': round(engage, 2), 'need_mm': round(need, 2), 'tip_room_mm': None if tip_room == math.inf else round(tip_room, 2),
                    'qty': r.get('qty', 1), 'ok': not why, 'why': '; '.join(why)})
    return out
