"""sim/controller_v2.py's guard: the robot sim runs the firmware's reach window and soft stops (docs/leg-protection.md).

    python -m pytest sim/test_controller_v2_guard.py -q     # seconds; no robot model is built
The whole robot with the guard on: python tools/simulate.py --v2 (every scenario must still pass).
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[2]))


import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

R = (Path(__file__).resolve().parents[2])
sys.path.insert(0, str(R))
sys.path.insert(0, str((R / 'hardware/cad')))
import hardware.cad.legs.fivebar as fb  # noqa: E402
from software.simulation import leg_limits as ll  # noqa: E402
from software.simulation import controller_v2 as c2  # noqa: E402

D = ll.load()
TABLE = D['command']['window']


def test_the_guard_is_on_by_default():
    assert c2.ControllerV2.__dataclass_fields__['guard'].default is True


def test_clamp_L_is_the_window_at_the_lean():
    assert ll.clamp_L(0.30, 0.0) == 0.30
    assert ll.clamp_L(0.50, 0.0) == pytest.approx(0.383)
    assert ll.clamp_L(0.05, 0.0) == pytest.approx(0.107)
    top = ll.window_at(TABLE, -0.35)[1]
    assert ll.clamp_L(0.375, -0.35) == pytest.approx(top) and top < 0.375      # full height leaning back: out of reach
    assert fb.stance(0.375 * 1000, math.degrees(-0.35)) is None
    assert fb.stance(top * 1000, math.degrees(-0.35)) is not None
    for lean in (-0.5, -0.27, 0.0, 0.13, 0.5):                                # every clamped command is a reachable pose
        for L in (0.0, 0.2, 1.0):
            assert fb.stance(ll.clamp_L(L, lean) * 1000, math.degrees(lean)) is not None


def _rb(phi_f, phi_r, cap=60.0):
    return SimpleNamespace(stops=list(fb.stop_angles()), leg_cap=cap, phi=lambda data, side: (phi_f, phi_r))


def test_the_soft_stop_takes_the_torque_out_of_each_motors_own_stops():
    fo, fi, ro, ri = fb.stop_angles()
    m = math.radians(ll.SOFT_MARGIN_DEG) / 2
    mid_f, mid_r = (fo + fi) / 2, (ro + ri) / 2
    # the front motor 1 deg from its outer stop (its hi): no torque towards it, a torque away passes
    rb = _rb(fo - m, mid_r)
    assert c2.soft_stop(rb, None, 'motor_f_l', 30.0, 0.0) == 0.0
    assert c2.soft_stop(rb, None, 'motor_f_l', -30.0, 0.0) == -30.0
    assert c2.soft_stop(rb, None, 'motor_r_l', 30.0, 0.0) == 30.0                # the rear motor is mid-range
    # the rear motor 1 deg from its inner stop (its hi), right side
    rb = _rb(mid_f, ri - m)
    assert c2.soft_stop(rb, None, 'motor_r_r', 30.0, 0.0) == 0.0
    assert c2.soft_stop(rb, None, 'motor_f_r', 30.0, 0.0) == 30.0
    # racing into a stop 5 deg away: braked away from it, never past the every-day torque (the limit there is 7.9 rad/s
    # for the whole leg's 0.169 kg m^2 at 60 N m)
    rb = _rb(fi + math.radians(5.0), mid_r)
    assert c2.soft_stop(rb, None, 'motor_f_l', -20.0, -6.0) == -20.0            # slow enough for the stop: untouched
    assert c2.soft_stop(rb, None, 'motor_f_l', -20.0, -15.0) == 60.0            # too fast: full brake, away from it


def test_the_soft_stop_uses_the_robot_every_day_torque_when_the_model_has_no_cap():
    fo, fi, ro, ri = fb.stop_angles()
    rb = _rb(fi + math.radians(5.0), (ro + ri) / 2, cap=None)
    out = c2.soft_stop(rb, None, 'motor_f_l', -100.0, -40.0)
    assert out == pytest.approx(D['profiles']['robot']['everyday_nm'])


def test_the_turn_is_clamped_to_what_the_wheels_and_legs_take_at_the_speed():
    y = D['yaw']
    vm = 0.5 * 0.959931089 * 36.0 * 0.127                                  # the speed clamp's vmax at 36 V
    assert ll.yaw_rate_limit(0.0, vm, y['half_track_m'], y['a_lat_m_s2']) == pytest.approx(vm / y['half_track_m'])
    assert ll.clamp_yaw(5.0, 1.0, vm) == pytest.approx(y['a_lat_m_s2'])    # lateral acceleration a_lat at 1 m/s
    assert ll.clamp_yaw(-5.0, 1.5, vm) == pytest.approx(-y['a_lat_m_s2'] / 1.5)
    assert ll.clamp_yaw(0.8, 1.0, vm) == 0.8                               # the drive scenario's turn is untouched
    assert ll.clamp_yaw(1.0, vm + 0.1, vm) == 0.0                          # past vmax the outer wheel has nothing left
    for v in (0.0, 0.3, 0.9, 1.6, 2.1):                                    # never a wheel past vmax, never past a_lat
        w = ll.yaw_rate_limit(v, vm, y['half_track_m'], y['a_lat_m_s2'])
        assert v + w * y['half_track_m'] <= vm + 1e-9 and v * w <= y['a_lat_m_s2'] + 1e-9
