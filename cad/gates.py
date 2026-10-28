"""Design gates: checks that fail a build when the model is not physically coherent. Generic on purpose (shapes and
positions in, plain results out, no product names inside), so they can move into the cad-agent toolkit as they are.

    spheres_in_cavities(centres, r, solids, ...)  every sphere (a ball, a bead, a pin) clear of every solid
    sphere_overlaps(centres, r, tol)               no two spheres overlapping more than tol
    connectivity(solids, groups, links, ...)       every rigid group one connected body: each part touches a neighbour,
                                                   or is fastened to it through a declared link (a screw, a bearing)
    clear_over_poses(moving_at, others_at, poses)  a moving shape against others at every pose of a joint sweep

A gate returns {'ok': bool, ...details}; `require(results)` raises GateFailure listing every failed gate.
Units: mm, mm^3. Shapes are CadQuery Workplanes or OCP/cq Shapes.
"""
from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cadquery as cq


class GateFailure(RuntimeError):
    pass


def _shape(s):
    return s.val() if hasattr(s, 'val') else s


def _bb_gap(a, b) -> float:
    """The largest per-axis separation of two bounding boxes (<= 0 when they overlap): a lower bound of the distance."""
    return max(a.xmin - b.xmax, b.xmin - a.xmax, a.ymin - b.ymax, b.ymin - a.ymax, a.zmin - b.zmax, b.zmin - a.zmax)


def spheres_in_cavities(centres: Sequence[Sequence[float]], r: float, solids: Dict[str, object], max_mm3: float = 1.0,
                        allow: Iterable[Tuple[int, str]] = (), labels: Optional[Sequence[str]] = None) -> dict:
    """Each sphere (centre, radius r) intersected with each solid: the volume must stay under max_mm3. `allow` names
    (sphere index, solid name) pairs that touch by design (a ball squeezed by a tyre). Returns the worst offenders and
    each sphere's nearest solid."""
    allow = set(allow)
    shapes = {n: _shape(s) for n, s in solids.items()}
    boxes = {n: s.BoundingBox() for n, s in shapes.items()}
    bad, nearest = [], []
    for i, c in enumerate(centres):
        sph = cq.Solid.makeSphere(r, cq.Vector(*c))
        sb = sph.BoundingBox()
        near = (None, 1e9)
        for n, s in shapes.items():
            if _bb_gap(sb, boxes[n]) > 2.0:
                continue
            if (i, n) in allow:
                continue
            try:
                v = sph.intersect(s).Volume()
            except Exception:
                v = 0.0
            if v > max_mm3:
                bad.append({'sphere': labels[i] if labels else i, 'solid': n, 'mm3': round(v, 2)})
            d = sph.distance(s) if v <= 1e-6 else 0.0
            if d < near[1]:
                near = (n, d)
        nearest.append({'sphere': labels[i] if labels else i, 'solid': near[0], 'gap_mm': round(near[1], 2) if near[0] else None})
    return {'ok': not bad, 'spheres': len(centres), 'radius_mm': r, 'max_mm3': max_mm3, 'violations': bad,
            'tightest': sorted((x for x in nearest if x['solid']), key=lambda x: x['gap_mm'])[:5],
            'allowed_contacts': sorted([list(a) for a in allow])}


def sphere_overlaps(centres: Sequence[Sequence[float]], r: float, tol: float = 0.1, labels: Optional[Sequence[str]] = None) -> dict:
    """No two spheres of radius r closer than 2r - tol."""
    bad, worst = [], 0.0
    for i, j in itertools.combinations(range(len(centres)), 2):
        d = sum((a - b) ** 2 for a, b in zip(centres[i], centres[j])) ** 0.5
        ov = 2 * r - d
        worst = max(worst, ov)
        if ov > tol:
            bad.append({'pair': [labels[i] if labels else i, labels[j] if labels else j], 'overlap_mm': round(ov, 3)})
    return {'ok': not bad, 'tol_mm': tol, 'worst_overlap_mm': round(worst, 3), 'violations': bad}


def connectivity(solids: Dict[str, object], groups: Dict[str, str], links: Iterable[Tuple[str, str, str]] = (),
                 touch_mm: float = 0.05, ignore: Iterable[str] = (), joints: Iterable[Tuple[str, str, str]] = (),
                 joint_mm: float = 0.5) -> dict:
    """Every rigid group (parts that move together) must be one connected body: an edge joins two parts of a group
    when their solids touch (closer than touch_mm) or a declared link fastens them (a, b, how: 'screw', 'bearing',
    'press fit'...). Returns each group's connected components; a group with more than one is a floating part.
    `joints` (a, b, how) are the joints between moving bodies (a bearing, a shaft in its hub): each pair's solids must
    be within joint_mm, so every moving body is held by its neighbour and not drawn hanging in the air."""
    ignore = set(ignore)
    names = [n for n in solids if n not in ignore]
    shapes = {n: _shape(solids[n]) for n in names}
    boxes = {n: shapes[n].BoundingBox() for n in names}
    edges = {}
    for a, b, how in links:
        if a in shapes and b in shapes:
            edges.setdefault(frozenset((a, b)), how)
    by_group: Dict[str, List[str]] = {}
    for n in names:
        by_group.setdefault(groups[n], []).append(n)
    for g, members in by_group.items():
        for a, b in itertools.combinations(members, 2):
            if frozenset((a, b)) in edges or _bb_gap(boxes[a], boxes[b]) > touch_mm:
                continue
            try:
                d = shapes[a].distance(shapes[b])
            except Exception:
                d = 1e9
            if d <= touch_mm:
                edges[frozenset((a, b))] = 'touch'
    out, ok = {}, True
    for g, members in by_group.items():
        parent = {m: m for m in members}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for e in edges:
            a, b = tuple(e)
            if a in parent and b in parent:
                parent[find(a)] = find(b)
        comps: Dict[str, List[str]] = {}
        for m in members:
            comps.setdefault(find(m), []).append(m)
        parts = sorted(comps.values(), key=len, reverse=True)
        out[g] = {'parts': len(members), 'bodies': len(parts), 'floating': [p for p in parts[1:]]}
        ok = ok and len(parts) == 1
    jout = []
    for a, b, how in joints:
        try:
            d = shapes[a].distance(shapes[b])
        except Exception:
            d = 1e9
        jout.append({'a': a, 'b': b, 'how': how, 'gap_mm': round(d, 3), 'ok': d <= joint_mm})
        ok = ok and d <= joint_mm
    return {'ok': ok, 'touch_mm': touch_mm, 'groups': out, 'joints': jout, 'joint_mm': joint_mm,
            'links': sorted([sorted(e) + [h] for e, h in edges.items() if h != 'touch'])}


def clear_over_poses(moving_at, others_at, poses: Sequence, max_mm3: float = 1.0, allow: Iterable[str] = ()) -> dict:
    """A moving shape (a payload, a load of balls) against other parts over a sweep: moving_at(pose) and
    others_at(pose) -> {name: shape} give them posed; each overlap over max_mm3 is a violation. `allow` names parts it
    may touch (its own carrier)."""
    allow = set(allow)
    bad = []
    for pose in poses:
        m = _shape(moving_at(pose))
        mb = m.BoundingBox()
        for n, s in others_at(pose).items():
            if n in allow:
                continue
            s = _shape(s)
            if _bb_gap(mb, s.BoundingBox()) > 0:
                continue
            try:
                v = m.intersect(s).Volume()
            except Exception:
                v = 0.0
            if v > max_mm3:
                bad.append({'pose': list(pose) if isinstance(pose, (tuple, list)) else pose, 'part': n, 'mm3': round(v, 2)})
    return {'ok': not bad, 'poses': len(poses), 'max_mm3': max_mm3, 'violations': bad}


def require(results: Dict[str, dict]):
    """Raise GateFailure naming every gate that failed."""
    failed = {k: v for k, v in results.items() if not v.get('ok')}
    if failed:
        def why(v):
            if v.get('violations'):
                return v['violations']
            if 'groups' in v:
                return {'floating': {g: x['floating'] for g, x in v['groups'].items() if x['floating']},
                        'joints_open': [j for j in v.get('joints', []) if not j['ok']]}
            return v
        msg = '; '.join(f'{k}: ' + str(why(v))[:500] for k, v in failed.items())
        raise GateFailure(f'{len(failed)} design gate(s) failed: {msg}')
