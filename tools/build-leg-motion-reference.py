#!/usr/bin/env python3
"""Pin an independently inspected leg attachment reference; no CAD kernel.

Run intentionally after reviewing the datums and stock geometry, not from the
browser test. Requires cad-agent's motion-trace module to generate required poses.
"""
import hashlib
import json
import math
from pathlib import Path
import struct

from cadagent.motion_trace import required_poses

ROOT = Path(__file__).resolve().parents[1]
RIG = ROOT / 'exports/sim/v2/rig'
ATTACHMENTS = ROOT / 'exports/sim/v2/leg-attachments'


def vertices(path):
    data = path.read_bytes()
    return [struct.unpack_from('<3f', data, 84 + t * 50 + 12 + v * 12)
            for t in range(struct.unpack_from('<I', data, 80)[0]) for v in range(3)]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def indices(points):
    a = 0
    b = max(range(len(points)), key=lambda i: dot(sub(points[i], points[a]), sub(points[i], points[a])))
    line = sub(points[b], points[a])
    c = max(range(len(points)), key=lambda i: dot(cross(line, sub(points[i], points[a])), cross(line, sub(points[i], points[a]))))
    normal = cross(line, sub(points[c], points[a]))
    d = max(range(len(points)), key=lambda i: abs(dot(normal, sub(points[i], points[a]))))
    assert abs(dot(normal, sub(points[d], points[a]))) > 1
    extremes = [f(range(len(points)), key=lambda i: points[i][axis]) for axis in range(3) for f in [min, max]]
    return list(dict.fromkeys([a, b, c, d, *extremes]))


def generate():
    # CAD fivebar: D=150, upper length150, lower250, nominal wheel centre(0,-300).
    # Axes independently confirmed by fixed motor STL cylinders centred x=±75,z=0.
    r = math.hypot(75, 300)
    offset = math.acos((150**2 + r*r - 250**2) / (2*150*r))
    home = {'f': math.atan2(-300, -75)+offset, 'r': math.atan2(-300, 75)-offset}
    sources, components, vertex_indices, joints = {}, {}, {}, {}
    part_names = ['output_adapter', *[f'output_screw_{i}' for i in range(1, 10)]]
    for side, sign in [('l', 1), ('r', -1)]:
        for end, x in [('f', 75.), ('r', -75.)]:
            owner = f'upper_{end}_{side}'
            joints[owner] = {'parent': None, 'pivot': [x, sign*82.3, 0], 'axis': [0, -1, 0], 'range_deg': [-45, 45]}
            for part in part_names:
                file = ATTACHMENTS / f'{part}.stl'
                points = vertices(file)
                ids = indices(points)
                # Adapter reference comes from the independently pinned original
                # body mesh, not the attachment export's claimed translation.
                if part == 'output_adapter':
                    original = RIG / 'body__adapter_f_l.stl'
                    sources[str(original.relative_to(ROOT))] = hashlib.sha256(original.read_bytes()).hexdigest()
                    points = [sub(p, [75., 82.3, 0.]) for p in vertices(original)]
                angle = home[end]
                def pose(p):
                    return [x+p[0]*math.cos(angle)-p[2]*math.sin(angle), sign*(82.3+p[1]),
                            p[0]*math.sin(angle)+p[2]*math.cos(angle)]
                name = f'{part}_{end}_{side}'
                components[name] = {'joint': owner, 'points': [pose(points[i]) for i in ids]}
                # Mirroring swaps the last two triangle vertices for winding.
                vertex_indices[name] = [i//3*3 + [0,2,1][i%3] for i in ids] if sign < 0 else ids
                sources[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
            name = f'motor_{end}_{side}'
            file = RIG / f'body__{name}{"_m" if sign < 0 else ""}.stl'
            points = vertices(file); ids = indices(points)
            components[name] = {'joint': None, 'points': [points[i] for i in ids]}
            vertex_indices[name] = ids
            sources[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    contract = {'schema_version': 1, 'length_unit': 'mm', 'frame': 'assembly-home',
                'reference': 'CAD fivebar.assembly/link_frames ownership; independently inspected original adapter and motor STL shafts; explicit 150/150/250 mm linkage at 300 mm reference height. Stock screw geometry separately checked against catalogue. Not the renderer manifest.',
                'joints': joints, 'components': components}
    poses = required_poses(contract)
    poses.append(dict(zip(joints, [21., -17., -23., 19.])))
    return {'contract': contract, 'vertex_indices': vertex_indices, 'source_hashes': sources,
            'home_angle_rad': home, 'poses': poses, 'tolerance_mm': .02,
            'limits': 'Sampled rendered ownership only. Independent joint probes are not closed-loop physical poses. No claim of load, collision, fit, manufacture or safety validation.'}


if __name__ == '__main__':
    (ROOT / 'tests/fixtures/leg-attachment-motion.json').write_text(json.dumps(generate(), indent=2) + '\n')
