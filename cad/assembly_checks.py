"""Assembly integrity checks: shapes and positions in, findings out. Nothing here knows what it is checking (no part or
project names), so it can move into cad-agent as it is.

    parts = {'plate': shape, 'block_1': shape, ...}                 # cadquery shapes (Workplane or Shape), placed
    bodies = {'carriage': ['plate', 'block_1', ...], 'frame': [...]}
    floating(parts, bodies, tol=0.05)                                 # every part of a body joined to the rest of it
    joints_hold(parts, [('carriage', 'frame', 'block_1', 'rail_1', 0.2)])
    interferences(parts, allow=lambda a, b: ...)                      # solid overlaps over min_mm3
    sweep(fixed, moving_at, poses, allow=...)                         # the same at every pose of the moving bodies
    screw_stacks(rows)                                                # each screw's length against its stack

Contact is measured, not assumed: two parts are joined when their bodies come within `tol` of each other (touching
faces, a block on its rail), or when a row of `fastened` names them (two parts held only by a screw whose own model
is left out). A body passes when its parts form one connected group.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _shape(s):
    return s.val() if hasattr(s, 'val') else s


def _bbox(s):
    b = _shape(s).BoundingBox()
    return (b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax)


def bbox_gap(a, b) -> float:
    """The gap between two boxes (0 when they overlap)."""
    g = [max(a[i] - b[i + 3], b[i] - a[i + 3], 0.0) for i in range(3)]
    return math.sqrt(sum(x * x for x in g))


def gap(a, b) -> float:
    """The smallest distance between two shapes (0 when they touch or overlap)."""
    try:
        return float(_shape(a).distance(_shape(b)))
    except Exception:                                    # noqa: BLE001 - a failed measure counts as unknown
        return float('nan')


def overlap_mm3(a, b) -> float:
    """The volume two solids share (mm^3)."""
    try:
        return float(_shape(a).intersect(_shape(b)).Volume())
    except Exception:                                    # noqa: BLE001
        return float('nan')


def contact_graph(parts: Mapping[str, object], names: Sequence[str], tol: float = 0.05,
                  fastened: Iterable[Tuple[str, str]] = ()) -> Dict[str, set]:
    """{name: neighbours} among `names`: within tol of each other, or a fastened pair."""
    boxes = {n: _bbox(parts[n]) for n in names}
    adj = {n: set() for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if bbox_gap(boxes[a], boxes[b]) > tol:
                continue
            if gap(parts[a], parts[b]) <= tol:
                adj[a].add(b)
                adj[b].add(a)
    for a, b in fastened:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def components(adj: Mapping[str, set]) -> List[List[str]]:
    seen, out = set(), []
    for n in adj:
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            m = stack.pop()
            comp.append(m)
            for k in adj[m]:
                if k not in seen:
                    seen.add(k)
                    stack.append(k)
        out.append(sorted(comp))
    return sorted(out, key=len, reverse=True)


def floating(parts: Mapping[str, object], bodies: Mapping[str, Sequence[str]], tol: float = 0.05,
             fastened: Iterable[Tuple[str, str]] = ()) -> Dict[str, dict]:
    """For each body: its connected groups; ok when there is one. The smaller groups are what floats."""
    fastened = list(fastened)
    out = {}
    for body, names in bodies.items():
        comps = components(contact_graph(parts, list(names), tol, fastened))
        out[body] = {'parts': len(names), 'groups': len(comps), 'ok': len(comps) == 1, 'floating': comps[1:]}
    return out


def joints_hold(parts: Mapping[str, object], joints: Iterable[Sequence], ) -> List[dict]:
    """Each (body_a, body_b, part_a, part_b, tol): the two bodies meet where the joint says (a block on its rail, a pin
    in its bore)."""
    out = []
    for ba, bb, pa, pb, tol in joints:
        g = gap(parts[pa], parts[pb])
        out.append({'joint': f'{ba}:{pa} / {bb}:{pb}', 'gap_mm': round(g, 3), 'tol_mm': tol, 'ok': bool(g <= tol)})
    return out


def interferences(parts: Mapping[str, object], allow: Optional[Callable[[str, str], bool]] = None,
                  min_mm3: float = 1.0, names: Optional[Sequence[str]] = None,
                  against: Optional[Mapping[str, object]] = None) -> List[dict]:
    """Every pair of solids that share more than min_mm3: among `parts`, or each of `parts` against each of `against`
    (then `parts` and `against` may hold the same name for different things). `allow(a, b)` True excuses a pair (a
    screw's thread in its hole, a press fit)."""
    allow = allow or (lambda a, b: False)
    names = list(names or parts)
    boxes = {n: _bbox(parts[n]) for n in names}
    rows = []
    if against is None:
        pairs = [(a, b, parts[a], parts[b], boxes[a], boxes[b]) for i, a in enumerate(names) for b in names[i + 1:]]
    else:
        ob = {m: _bbox(s) for m, s in against.items()}
        pairs = [(a, m, parts[a], against[m], boxes[a], ob[m]) for a in names for m in against]
    for a, b, sa, sb, ba, bb in pairs:
        if bbox_gap(ba, bb) > 0.0 or allow(a, b) or allow(b, a):
            continue
        v = overlap_mm3(sa, sb)
        if not (v <= min_mm3):                           # NaN counts: an unmeasurable pair is reported
            rows.append({'parts': [a, b], 'overlap_mm3': None if v != v else round(v, 1)})
    return rows


def sweep(fixed: Mapping[str, object], moving_at: Callable[[object], Mapping[str, object]], poses: Iterable,
          allow: Optional[Callable[[str, str], bool]] = None, min_mm3: float = 1.0, within: bool = True) -> dict:
    """The moving parts against the fixed ones (and, with within=True, against each other) at every pose:
    {'poses': n, 'hits': [{pose, parts, overlap_mm3}]}."""
    hits, n = [], 0
    for pose in poses:
        mv = moving_at(pose)
        n += 1
        for r in interferences(mv, allow, min_mm3, against=fixed):
            hits.append({'pose': pose, **r})
        if within:
            for r in interferences(mv, allow, min_mm3):
                hits.append({'pose': pose, **r})
    return {'poses': n, 'hits': hits, 'ok': not hits}


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


def report_failures(sections: Mapping[str, object]) -> List[str]:
    """One line per failure across the results of the functions above (for an exit code)."""
    bad = []
    for name, res in sections.items():
        if isinstance(res, dict) and 'ok' in res and 'floating' not in res and not res['ok']:
            bad.append(f"{name}: {res.get('hits', '')}"[:300])
        elif isinstance(res, dict):
            for k, v in res.items():
                if isinstance(v, dict) and v.get('ok') is False:
                    bad.append(f"{name} {k}: {v.get('floating') or v}"[:300])
        elif isinstance(res, list):
            for v in res:
                if isinstance(v, dict) and v.get('ok') is False:
                    bad.append(f"{name}: {v}"[:300])
    return bad
