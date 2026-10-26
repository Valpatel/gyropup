"""The whole robot as one assembly: every made, bought and electronic part, placed, on the link it moves with, with
its mass, centre of mass and inertia. The physics model (sim/model.py) takes its links' inertials and visual meshes
from here, so the simulator weighs and shows exactly what the CAD holds.

Links (the physics model's bodies; their frames are the robot frame shifted, legs at the zero pose):
  base             origin on the hip axis: chassis, bay, electronics, J501 box, battery, sensors, the leg modules'
                   fixed parts (yoke, motor plates, posts, both motors)
  thigh_l / _r     origin at the hip: thigh, hip output adapter; the knee crank and its adapter (they turn about the
                   hip axis with the knee motor; the model has no crank body, so they ride here, at the axis); half of
                   the push-rod
  shin_l / _r      origin at the knee: shin, wheel adapter, the BotWheel's stator, the other half of the push-rod
  wheel_l / _r     origin at the axle: the BotWheel's rotor and tyre
Masses: printed parts from their CAD volume (100 % solid where structural); bought parts at their catalogue mass,
spread uniformly over their CAD (vendor STEP where it is on this machine, else the drawing's envelope); hardware not
yet modelled part by part is the designer's allowance, spread over the links.

Writes exports/assembly.json, and with meshes=True exports/mjcf/*.stl (robot frame, mm; not committed: vendor
geometry stays local).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq

from cadagent.robot import Body, combine, printed_part_body, solid_mass_properties

try:                                    # cad-agent PR #4; until it is released, meshes are left as exported
    from cadagent.robot import fit_mesh
except ImportError:                     # pragma: no cover
    def fit_mesh(path, max_faces=150_000):
        return 0

LEG_HARDWARE_SHARE = 0.5          # of the hardware allowance not yet placed part by part: the share in the legs
ROTOR_SHARE = 0.75                # BotWheel: the spinning share (rotor + tyre); the stator rides on the shin


def _val(s):
    return s.val() if hasattr(s, 'val') else s


def body_of(shape, mass_g: float | None = None, density: float | None = None, solid: bool = True, name: str = '') -> Body:
    """A part's Body in the robot frame (SI): a printed part from its density (solid or 2 mm walls at 40 %), a bought
    one with its catalogue mass spread over its volume."""
    s = _val(shape)
    if mass_g is not None:
        vol_cm3 = s.Volume() / 1000.0
        return solid_mass_properties(s, mass_g / vol_cm3, 1.0, name)
    b, _ = printed_part_body(s, density, wall_mm=500.0 if solid else 2.0, infill=1.0 if solid else 0.4, name=name)
    return b


class Assembly:
    def __init__(self, origins: dict):
        self.origins = origins            # link -> (x, y, z) mm in the robot frame
        self.items = []                   # (link, name, kind, Body (robot frame), visual shape or None, colour, estimate)

    def add(self, link, name, kind, body: Body, shape=None, color='#9aa3ad', estimate=False):
        """shape: what the part looks like (may differ from what its mass was computed on, e.g. a vendor STEP)."""
        self.items.append((link, name, kind, body, shape, color, estimate))

    def links(self) -> dict:
        """link -> Body in the link's own frame."""
        out = {}
        for link, o in self.origins.items():
            bs = [b for (lk, _, _, b, _, _, _) in self.items if lk == link]
            c = combine(bs, link)
            out[link] = c.translated(tuple(-v / 1000.0 for v in o)) if c.mass > 0 else c
        return out

    def write(self, path: Path, design: str, mesh_dir: Path | None = None, notes=()):
        links = self.links()
        parts = {lk: [] for lk in self.origins}
        if mesh_dir:
            mesh_dir.mkdir(parents=True, exist_ok=True)
            for old in mesh_dir.glob('*.stl'):
                old.unlink()
        for (lk, name, kind, b, shape, color, est) in self.items:
            mesh = None
            if mesh_dir is not None and shape is not None:
                f = mesh_dir / f'{lk}__{name}.stl'
                cq.exporters.export(_val(shape), str(f), tolerance=0.3, angularTolerance=0.3)
                fit_mesh(f, 150_000)                       # MuJoCo takes at most 200 000 faces (vendor models exceed it)
                mesh = str(f)
            parts[lk].append({'name': name, 'kind': kind, 'mass_kg': round(b.mass, 5), 'com_m': [round(v, 5) for v in b.com],
                              'mesh': mesh, 'color': color, 'estimate': est})
        by_kind = {}
        for (_, _, kind, b, _, _, _) in self.items:
            by_kind[kind] = round(by_kind.get(kind, 0.0) + b.mass, 4)
        total = sum(b.mass for (_, _, _, b, _, _, _) in self.items)
        data = {'design': design, 'units': 'robot frame, legs at the zero pose; origins mm, inertials SI in each link frame',
                'total_kg': round(total, 4), 'by_kind_kg': by_kind, 'notes': list(notes),
                'links': {lk: {'origin_mm': [round(v, 3) for v in self.origins[lk]], **links[lk].as_dict(), 'parts': parts[lk]}
                          for lk in self.origins}}
        Path(path).write_text(json.dumps(data, indent=1) + '\n')
        return data


def mirror_y(shape):
    return _val(shape).mirror('XZ')


def mirror_body(b: Body) -> Body:
    """The same body reflected y -> -y."""
    (ixx, ixy, ixz), (_, iyy, iyz), (_, _, izz) = b.inertia
    inertia = ((ixx, -ixy, ixz), (-ixy, iyy, -iyz), (ixz, -iyz, izz))
    return Body(b.mass, (b.com[0], -b.com[1], b.com[2]), inertia, b.name)
