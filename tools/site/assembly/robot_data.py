"""Pure binary mesh identities and mechanical frame controls for assembly data."""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import struct
import stat


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vertices(path):
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError('Truncated binary STL')
    count = struct.unpack_from('<I', data, 80)[0]
    if not count or len(data) != 84+50*count:
        raise ValueError('STL triangle count/length mismatch')
    result = []
    for i in range(count):
        fields = struct.unpack_from('<12fH', data, 84+50*i)
        if not all(math.isfinite(v) for v in fields[:12]):
            raise ValueError('Nonfinite STL geometry')
        result.extend(tuple(fields[k:k+3]) for k in (3, 6, 9))
    return result


def bounds(path):
    points = vertices(path)
    return [min(p[k] for p in points) for k in range(3)]+[max(p[k] for p in points) for k in range(3)]


def module_point(point, side, y_offset):
    """body_params.to_robot: physical right module rotates 180deg Z, no reflection."""
    if side not in ('L', 'R') or len(point) != 3 or not all(math.isfinite(v) for v in (*point, y_offset)):
        raise ValueError('Invalid physical module frame')
    x, y, z = point
    return (x, y+y_offset, z) if side == 'L' else (-x, -(y+y_offset), z)


def landmarks(points):
    """Four actual, distinct noncoplanar mesh vertices; not a bounding-box fixture."""
    unique = list(dict.fromkeys(points))
    if len(unique) < 4:
        raise ValueError('Too few distinct mesh points')
    p0 = min(unique)
    dist2 = lambda p,q: sum((p[i]-q[i])**2 for i in range(3))
    p1 = max(unique, key=lambda p: dist2(p,p0))
    a = tuple(p1[i]-p0[i] for i in range(3))
    cross = lambda b,c: (b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
    area = lambda p: sum(v*v for v in cross(a,tuple(p[i]-p0[i] for i in range(3))))
    p2 = max(unique,key=area)
    n = cross(a,tuple(p2[i]-p0[i] for i in range(3)))
    volume = lambda p: abs(sum(n[i]*(p[i]-p0[i]) for i in range(3)))
    p3 = max(unique,key=volume)
    if dist2(p0,p1) < 1e-12 or area(p2) < 1e-12 or volume(p3) < 1e-9:
        raise ValueError('Degenerate landmark frame')
    return [p0,p1,p2,p3]


def nearest_errors(expected, actual, tolerance=.02):
    """Spatial buckets measure actual vertices; no unbounded quadratic full mesh compare."""
    if tolerance <= 0:
        raise ValueError('Positive millimetre tolerance required')
    cell = lambda p: tuple(math.floor(v/tolerance) for v in p)
    buckets = {}
    for p in actual: buckets.setdefault(cell(p),[]).append(p)
    errors = []
    for p in expected:
        key = cell(p)
        nearby = [q for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1)
                  for q in buckets.get((key[0]+x,key[1]+y,key[2]+z),())]
        errors.append(min((math.dist(p,q) for q in nearby),default=math.inf))
    return errors


def inventory(root):
    """Complete regular-file membership; lstat first also rejects symlink dirs."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Nonregular inventory member: '+path.relative_to(root).as_posix())
        files[path.relative_to(root).as_posix()] = {'sha256':sha(path),'mode':stat.S_IMODE(mode),'bytes':path.stat().st_size}
    return files
