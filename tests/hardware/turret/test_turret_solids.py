"""Every turret part is a valid closed solid, as cad-agent's design gates require (#61).

cad-agent's relation table (v0.6.0 on) refuses an invalid BREP before it computes any volume, so one bad part stops
hardware/cad/turret/turret_gates.py and, behind it, hardware/cad/builders/build_turret_box.py. This finds the part by name instead.

    .venv/bin/python -m pytest tests/hardware/turret/test_turret_solids.py -q
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))


import sys
from pathlib import Path

import cadquery as cq
import pytest
from OCP.BRepCheck import BRepCheck_Analyzer

sys.path.insert(0, str((Path(__file__).resolve().parents[3] / 'hardware/cad')))
import hardware.cad.turret.turret as tu  # noqa: E402


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


def test_the_latch_head_clears_the_yoke_to_the_stop(turret):
    """cad-agent's motion gate found the CT latch's Ø16 head 1.7 mm into the yoke's bridge from -22.9 deg on (#61): the
    bridge is relieved by the head's sweep, so the cradle reaches its -25 deg stop and 2 deg past it with the head clear."""
    for tilt in (0.0, -12.5, -22.9, -25.0, -27.0):
        posed = turret.posed(0.0, tilt, names=['ct_thumbscrew', 'tilt_yoke'], robot=False)
        common = posed['ct_thumbscrew'].val().intersect(posed['tilt_yoke'].val())
        assert common.Volume() < 1e-6, f'the latch head is in the yoke at tilt {tilt} deg'
        if tilt <= -22.9:                                   # where the relief works: the swept clearance, 1 mm
            gap = posed['ct_thumbscrew'].val().distance(posed['tilt_yoke'].val())
            assert gap > 0.98, f'{gap:.3f} mm between the latch head and the yoke at tilt {tilt} deg'


def test_the_relief_is_needed_and_small(turret):
    """The control: the bridge without the relief is hit at the stop; the relief stays a small notch on the front edge."""
    G = turret.G
    b0, b1 = G.bridge_z
    a1 = G.arm_y[1]
    bridge = tu.box(-20, 20, -a1, a1, b0, b1)
    head = tu.thumb_solid(G).translate((-G.tilt_x, 0, G.path_t)).rotate((0, 0, G.tilt_t), (0, 1, G.tilt_t), -G.tilt_min)
    assert head.intersect(bridge).val().Volume() > 10.0
    cut = tu.thumb_sweep(G, clear=1.0, to_deg=-(-G.tilt_min + 2.0)).intersect(bridge).val()
    bb = cut.BoundingBox()
    assert cut.Volume() < 500.0 and b1 - bb.zmin < 5.0 and bb.xmin > 10.0     # <= 5 mm into the 12 mm bridge's front top
