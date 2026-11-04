"""The turret sims take their tilt range from the hard stops, and their aiming works above level (#201, D77).

    .venv/bin/python -m pytest sim/test_turret_limits.py -q

The upper stop is still at 0 deg in the CAD until it moves (after #196); these tests also aim with a raised stop, so the
solvers are known to handle positive elevation before the CAD changes.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_common as tc  # noqa: E402

LIMITS = json.loads((R / 'exports' / 'turret' / 'limits.json').read_text())


def game():
    pytest.importorskip('mujoco')
    return tc.game_turret()


def flight():
    pytest.importorskip('numpy')
    return tc.sim_module('turret_flight')


def test_limits_file_is_the_cads():
    pytest.importorskip('cadquery')
    spec = importlib.util.spec_from_file_location('turret_limits', R / 'cad' / 'turret_limits.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert (R / 'exports' / 'turret' / 'limits.json').read_text() == m.text(), 'run cad/turret_limits.py'


def test_every_sim_reads_the_same_stops():
    lo, hi = LIMITS['tilt_deg']['min'], LIMITS['tilt_deg']['max']
    assert lo < hi
    assert tc.tilt_stops_deg() == (lo, hi)
    g = game()
    assert (g.TILT_MIN_DEG, g.TILT_MAX_DEG) == (lo, hi)


def test_no_never_above_horizontal_rule_left_in_the_aiming():
    """The old rule lived in the aiming code as "elev <= 0" / "hi=0.0"; none of it may come back."""
    for f in ('sim/turret.py', 'sim/turret_flight.py', 'sim/turret_e2e.py', 'designer/turret3d.js', 'designer/sim.js'):
        text = (R / f).read_text().lower()
        assert 'never above horizontal' not in text and 'never above level' not in text, f
    assert 'elev <= 0.0' not in (R / 'sim/turret.py').read_text()
    assert 'MAX_TILT_UP' not in (R / 'designer/turret3d.js').read_text()


def test_joint_clamp_is_the_stops_not_the_world():
    g = game()
    # a target 10 deg up on a level body: inside a +20 deg stop, clipped by a 0 deg stop
    up = math.radians(10.0)
    t, inside = g.joint_tilt(up, 0.0, (-25.0, 20.0))
    assert inside and t == pytest.approx(-up)
    t, inside = g.joint_tilt(up, 0.0, (-25.0, 0.0))
    assert not inside and t == pytest.approx(0.0)
    # the stop is in the joint: a body pitched 5 deg nose up (pitch -5 deg) reaches 10 deg up with only 5 deg of joint
    t, inside = g.joint_tilt(up, math.radians(-5.0), (-25.0, 6.0))
    assert inside and t == pytest.approx(-math.radians(5.0))
    # the lower stop still holds
    t, inside = g.joint_tilt(math.radians(-40.0), 0.0, (-25.0, 20.0))
    assert not inside and t == pytest.approx(math.radians(25.0))


def test_game_solver_finds_upward_shots():
    g = game()
    el = g.elevation_for(6.0, 0.8)                 # 0.8 m above the muzzle at 6 m: an upward shot
    assert el is not None and el > 0.0
    assert g.fly(el, 6.0) == pytest.approx(0.8, abs=0.005)
    el = g.elevation_for(4.0, -0.25)               # below the muzzle: still the old downward solution
    assert el is not None and g.fly(el, 4.0) == pytest.approx(-0.25, abs=0.005)


def test_flight_solver_aims_up_within_a_raised_stop_and_not_past_it():
    tf, tb = flight(), tc.sim_module('turret_ball')
    tl = tc.sim_module('turret_launch')
    spec = tb.nominal()
    v0 = 55 * tl.FPS
    h0 = 0.55
    # a target 0.4 m above the muzzle at 4 m needs the barrel up
    el = tf.elevation_for(v0, spec, 4, h0 + 0.4, h0=h0, hi=math.radians(20.0))
    assert el is not None and el > 0.0
    assert tf.drop_at(v0, spec, 4, el, h0) == pytest.approx(h0 + 0.4, abs=0.01)
    # with the stop at level it is out of reach (None), as before
    assert tf.elevation_for(v0, spec, 4, h0 + 0.4, h0=h0, hi=0.0) is None
    # the default range is the stops' own
    lo, hi = (math.radians(a) for a in tc.tilt_stops_deg())
    el = tf.elevation_for(v0, spec, 2, 0.30, h0=h0)
    assert el is not None and lo <= el <= hi
