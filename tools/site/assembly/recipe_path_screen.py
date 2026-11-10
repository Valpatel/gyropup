"""Bounded surface-interior witnesses for axial educational arrivals.

This is a regression screen, not a collision or assembly qualification gate.
It uses triangle centroids, ray parity and sampled translations; zero witnesses
cannot establish clearance. Exact BREP insertion and subassembly checks belong
to the existing CAD assembly gates.
"""
from __future__ import annotations
import math
from pathlib import Path
import struct


def triangles(path):
    data = Path(path).read_bytes()
    if len(data) < 84 or len(data) != 84 + 50 * struct.unpack_from('<I', data, 80)[0]:
        raise ValueError('Expected exact-length binary STL')
    result = []
    for values in struct.iter_unpack('<12fH', data[84:]):
        if not all(math.isfinite(v) for v in values[:12]):
            raise ValueError('Nonfinite STL')
        result.append(tuple(tuple(values[k:k+3]) for k in (3, 6, 9)))
    if not result:
        raise ValueError('Empty STL')
    return result


def axial_intervals(point, fixed, axis):
    """Interior intervals along a ray; odd/edge-degenerate rays stay unknown."""
    u, v = [k for k in range(3) if k != axis]
    hits = []
    for a, b, c in fixed:
        bu, bv, cu, cv = b[u]-a[u], b[v]-a[v], c[u]-a[u], c[v]-a[v]
        determinant = bu*cv-bv*cu
        if abs(determinant) < 1e-9:
            continue
        du, dv = point[u]-a[u], point[v]-a[v]
        s, t = (du*cv-dv*cu)/determinant, (bu*dv-bv*du)/determinant
        if min(s, t, 1-s-t) >= -1e-7 and min(s, t, 1-s-t) <= 1e-7:
            return None
        if s > 1e-7 and t > 1e-7 and s+t < 1-1e-7:
            hits.append(a[axis]+s*(b[axis]-a[axis])+t*(c[axis]-a[axis]))
    hits = sorted(set(round(value, 6) for value in hits))
    return None if len(hits) % 2 else list(zip(hits[::2], hits[1::2]))


def screen(moving, fixed, offset, *, axis=1, samples=128, positions=21, margin_mm=.05):
    """Return reproducible interior witnesses, explicitly retaining unknown rays."""
    if (axis not in (0, 1, 2) or not math.isfinite(offset) or not offset
            or samples < 4 or positions < 3 or margin_mm <= 0):
        raise ValueError('Invalid bounded axial screen')
    count = min(samples, len(moving))
    indices = [i*len(moving)//count for i in range(count)]
    points = [tuple(sum(p[k] for p in moving[i])/3 for k in range(3)) for i in indices]
    intervals = [axial_intervals(p, fixed, axis) for p in points]
    rows = []
    first_witness = None
    for i in range(positions):
        progress = i/(positions-1)
        shift = offset*(1-progress)
        witnesses = [index for index, (p, cells) in enumerate(zip(points, intervals))
                     if cells is not None and any(lo+margin_mm < p[axis]+shift < hi-margin_mm for lo, hi in cells)]
        rows.append({'progress': progress, 'interior_witnesses': len(witnesses)})
        if witnesses and first_witness is None:
            sample = witnesses[0]
            point = list(points[sample]); point[axis] += shift
            first_witness = {'progress': progress, 'moving_triangle_index': indices[sample],
                             'home_centroid_mm': list(points[sample]), 'translated_centroid_mm': point,
                             'fixed_interior_intervals_mm': [list(pair) for pair in intervals[sample]]}
    return {'surface_samples': count, 'unknown_rays': sum(v is None for v in intervals),
            'sampled_positions': positions, 'interior_margin_mm': margin_mm,
            'max_preterminal_witnesses': max(row['interior_witnesses'] for row in rows[:-1]),
            'terminal_witnesses': rows[-1]['interior_witnesses'], 'first_witness': first_witness, 'samples': rows}
