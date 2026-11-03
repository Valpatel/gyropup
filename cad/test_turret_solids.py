"""Every turret part is a valid closed solid, as cad-agent's design gates require (#61).

cad-agent's relation table (v0.6.0 on) refuses an invalid BREP before it computes any volume, so one bad part stops
cad/turret_gates.py and, behind it, cad/build_turret_box.py. This finds the part by name instead.

    .venv/bin/python -m pytest cad/test_turret_solids.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq
import pytest
from OCP.BRepCheck import BRepCheck_Analyzer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import turret as tu  # noqa: E402


def _valid(shape) -> bool:
    v = shape.val() if hasattr(shape, 'val') else shape
    return BRepCheck_Analyzer(v.wrapped, True).IsValid()


@pytest.fixture(scope='module')
def turret():
    return tu.Turret({'bodyTop': 100.0})


def test_every_part_is_a_valid_solid(turret):
    bad = [n for n, s in turret.local.items() if not _valid(s)]
    assert not bad, f'invalid BREP (the gates refuse these): {bad}'


def test_the_rotor_leads_keep_their_envelope(turret):
    """The bend became a ball of the bundle's radius; the run's reach is unchanged."""
    v = turret.local['ring_leads_rotor'].val()
    bb = v.BoundingBox()
    rl, zl = tu.LEADS['d'] / 2, tu.LEADS['z_run']
    assert len(v.Solids()) == 1
    assert bb.zmax == pytest.approx(zl + rl, abs=1e-6)
    assert bb.ymax == pytest.approx(-tu.LEADS['r'] + rl, abs=1e-6)


def test_the_check_catches_the_old_bend():
    """The control: two equal cylinders meeting with the vertical one's end tangent to the other's top is invalid."""
    rl, zl, r = 3.75, 89.0, 13.0
    old = tu.cyl_z(rl, 40.0, zl + rl, 0.0, -r).union(tu.cyl_y(rl, -70.0, -r, 0.0, zl))
    new = (tu.cyl_z(rl, 40.0, zl, 0.0, -r).union(tu.cyl_y(rl, -70.0, -r, 0.0, zl))
           .union(cq.Workplane('XY').sphere(rl).translate((0.0, -r, zl))))
    assert not _valid(old)
    assert _valid(new)
