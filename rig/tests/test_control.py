"""The controller port against sim/leg_rig.py (the copies must not drift), T7's reproduction, the supervisor's aborts
(T8) and the CAN path on the HIL stand-in.

    .venv/bin/python -m pytest rig/tests -q          # ~1-3 min: it runs MuJoCo
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
import pytest

from rig import leg_control as lc
from rig.bus import Pack

lr = pytest.importorskip('sim.leg_rig')
R = Path(__file__).resolve().parents[2]
REF = json.loads((R / 'exports' / 'leg' / 'rig-results.json').read_text())


# ----------------------------------------------------------------------------------- the port is sim/leg_rig.py's

def test_the_controller_is_sim_leg_controls_and_the_scenarios_sim_leg_rigs():
    import sim.leg_control as slc
    assert lc.vmc_from_state is slc.vmc_from_state and lc.polar is slc.polar and lc.Gains is slc.Gains
    assert lc.clip_motor is slc.clip_motor and lr.vmc_from_state is slc.vmc_from_state
    assert lc.LEG_CAP == lr.LEG_CAP and lc.LEG_PEAK == lr.LEG_PEAK
    assert set(lc.SCENARIOS) == set(lr.SCENARIOS)
    for k, s in lc.SCENARIOS.items():
        assert s.__dict__ == lr.SCENARIOS[k].__dict__
    for k in lc.SCENARIOS:
        for st in ({}, {'pushed': True}):
            for t in np.arange(0.0, 3.0, 0.013):
                assert lc.command(lc.SCENARIOS[k], t, dict(st)) == lr.command(lr.SCENARIOS[k], t, dict(st))


@pytest.fixture(scope='module')
def model():
    import mujoco
    xml, info = lr.mjcf(13.1)
    m = mujoco.MjModel.from_xml_string(xml)
    return m, mujoco.MjData(m), lr.Leg(m)


def test_polar_from_the_angles_equals_the_simulated_legs(model):
    """fivebar's kinematics (what the rig computes from the motors' angles) against MuJoCo's leg."""
    m, d, leg = model
    rnd = random.Random(5)
    for _ in range(60):
        h = rnd.uniform(120, 380)
        leg.set_height(d, h)
        d.qvel[leg.v['motor_f']], d.qvel[leg.v['motor_r']] = rnd.uniform(-10, 10), rnd.uniform(-10, 10)
        p1, p2 = leg.phi(d)
        w1, w2 = d.qvel[leg.v['motor_f']], d.qvel[leg.v['motor_r']]
        a, b = lc.polar(p1, p2, w1, w2), leg.polar(d)
        for x, y in zip(a[:4], b[:4]):
            assert x == pytest.approx(y, rel=1e-9, abs=1e-12)


# ----------------------------------------------------------------------------------- T7

def _run(name, rate=500.0, pack=None, latency=0, **kw):
    """rig.run's simulation of a scenario at the reference's mass, on sim/leg_rig.py's ideal bus (its BUS_V, no
    resistance) unless a pack is given: the bus the reference (exports/leg/rig-results.json) was made on."""
    from rig.run import run_sim
    pack = pack or Pack(REF.get('bus_v', lr.BUS_V), 0.0)
    return run_sim(name, REF['half_mass_kg'], rate, pack, latency, save=False, rig=False, **kw)['results']


@pytest.mark.parametrize('name', ['stand_up', 'squat'])
def test_t7_stand_up_and_squat_peaks_within_5_percent(name):
    r, a = _run(name), REF['scenarios'][name]
    for k in ('peak_motor_nm', 'peak_motor_speed_rad_s', 'peak_wheel_force_n', 'peak_axle_force_n', 'peak_gearbox_nm', 'peak_knee_pin_n'):
        assert abs(r[k] - a[k]) <= 0.05 * abs(a[k]), k


def test_t7_jump_height_within_10_mm():
    r, a = _run('jump'), REF['scenarios']['jump']
    assert abs(r['jump_height_mm'] - a['jump_height_mm']) <= 10.0
    assert abs(r['peak_wheel_force_n'] - a['peak_wheel_force_n']) <= 0.05 * a['peak_wheel_force_n']


def test_at_the_simulations_own_rate_with_its_contact_the_port_is_exact():
    r, a = _run('jump', rate=2000.0, contact_truth=True), REF['scenarios']['jump']
    for k in ('jump_height_mm', 'peak_motor_nm', 'peak_wheel_force_n', 'peak_gearbox_nm', 'peak_knee_pin_n'):
        assert r[k] == pytest.approx(a[k], abs=0.051), k


# ----------------------------------------------------------------------------------- T8: the supervisor

@pytest.mark.parametrize('kind', ['run', 'vbus_high', 'hot', 'window', 'silent', 'fault'])
def test_every_fault_aborts_as_designed(kind):
    from rig.faults import EXPECT
    from rig.run import run_sim
    o = run_sim('squat', 14.75, 500.0, Pack(38.0, 0.10), 1, save=False, inject=(kind, 1.0))
    log = o['log']
    assert log.aborts and log.aborts[0][1].startswith(EXPECT[kind]), log.aborts
    assert log.aborts[0][0] <= 1.0 + 0.0061                       # within three ticks
    a = log.arrays()
    stopped = a['phase'] == 8
    assert stopped.any() and np.all(a['tau_cmd_f'][stopped] == 0) and np.all(a['tau_cmd_r'][stopped] == 0)


def test_sitdown_ends_near_150_mm():
    from rig.run import run_sim
    a = run_sim('squat', 14.75, 500.0, Pack(38.0, 0.10), 1, save=False, inject=('run', 2.0))['log'].arrays()
    i = np.flatnonzero(a['phase'] == 8)[0]
    assert a['L'][i] == pytest.approx(0.150, abs=0.012)


def test_power_cut_tests_hold_until_the_cut_and_never_sit_down():
    from rig.run import run_sim
    o = run_sim('power_off_damped', 14.75, 500.0, Pack(38.0, 0.10), 1, save=False, inject=('run', 0.3))
    assert not o['log'].aborts                                    # the pendant's release is how the power is cut
    assert o['results']['L_range_mm'][0] < 120                     # and the leg folds once it goes


# ----------------------------------------------------------------------------------- the CAN path, without hardware

def test_hil_squat_matches_the_simulation_with_one_tick_of_latency():
    from rig.run import run_hil, run_sim
    h = run_hil('squat', 14.75, 500.0, Pack(38.0, 0.10))
    s = run_sim('squat', 14.75, 500.0, Pack(38.0, 0.10), 1, save=False)['results']
    for k in ('peak_motor_nm', 'peak_wheel_force_n', 'peak_knee_pin_n'):          # the CAN frames' 16-bit fields and the
        assert h['results'][k] == pytest.approx(s[k], rel=0.03), k             # latency's timing: 2.3 % on the 155 N peak
    assert h['bus'].startup['front']['limit_torque'] == 60.0 and h['bus'].startup['front']['damper'] == 0
    for p in h['paths'].values():
        p.unlink()


def test_hil_jump_survives_the_speed_fields_rail():
    """The push passes 15 rad/s, where the feedback's speed field saturates: the backend switches to the angle's
    rate and the jump still matches the simulation."""
    from rig.run import run_hil, run_sim
    # the ideal 54 V bus: fast enough to run past the feedback's 15 rad/s field (on D65's 36 V packs it rarely is)
    h = run_hil('jump', 14.75, 500.0, Pack(54.0, 0.0))
    s = run_sim('jump', 14.75, 500.0, Pack(54.0, 0.0), 1, save=False)['results']
    w = h['log'].arrays()['w_f']
    assert np.max(np.abs(w)) > 15.0                                # seen past the rail
    assert h['results']['jump_height_mm'] == pytest.approx(s['jump_height_mm'], abs=5.0)
    for p in h['paths'].values():
        p.unlink()


# ----------------------------------------------------------------------------------- B5 on the rig: the tyre press

def _held_leg_ticks(ctl, L_of_t, t_end, dt=0.002):
    """Feed the controller a leg whose length follows L_of_t (the carriage held by the top stop: the wheel cannot move
    away), the motors reporting the commanded torque; return the commands."""
    import fivebar as fb
    from rig.bus import MotorState, Tick
    out, t = [], 0.0
    while t <= t_end:
        phi1, phi2 = fb.ik(0.0, -L_of_t(t) * 1000.0)
        cmd = ctl.update(Tick(t, MotorState(phi1, 0.0, out[-1][1].tau_f if out else 0.0, 30.0),
                              MotorState(phi2, 0.0, out[-1][1].tau_r if out else 0.0, 30.0), 38.0))
        out.append((t, cmd))
        if cmd.stop:
            break
        t += dt
    return out


def test_tyre_press_steps_the_force_through_the_leg_and_back():
    from rig import leg_control as lc
    ctl = lc.LegController('tyre_press', 140.0, lc.Limits(), tick=0.002, external_cut=True)
    L = lambda t: 0.140 + (0.360 - 0.140) * lc.smooth(t / 2.0) if t < 2.0 else 0.360
    cmds = _held_leg_ticks(ctl, L, 66.0)
    assert ctl.abort is None
    seen = {}
    for t, c in cmds:
        if c.phase.startswith('press'):
            seen.setdefault(c.phase, []).append(max(abs(c.tau_f), abs(c.tau_r)))
    assert list(dict.fromkeys(seen)) == [f'press {F} N' for F in dict.fromkeys(lc.PRESS_STEPS)]
    pol = lc.polar(*__import__('fivebar').ik(0.0, -360.0), 0.0, 0.0)
    per_n = max(abs(x) for x in pol[4].T @ [0.0, -1.0])                       # N m per N at 360 mm
    assert max(seen['press 900 N']) == pytest.approx(900 * per_n, rel=0.05) and max(seen['press 900 N']) <= 60.0
    assert max(seen['press 200 N']) == pytest.approx(200 * per_n, rel=0.05)


def test_tyre_press_goes_limp_if_the_carriage_is_not_held():
    from rig import leg_control as lc
    ctl = lc.LegController('tyre_press', 140.0, lc.Limits(), tick=0.002, external_cut=True)
    L = lambda t: (0.140 + 0.220 * lc.smooth(t / 2.0)) if t < 3.2 else min(0.390, 0.360 + 0.2 * (t - 3.2))   # it stretches
    cmds = _held_leg_ticks(ctl, L, 6.0)
    assert ctl.abort and 'not held' in ctl.abort and cmds[-1][1].stop


def test_the_rig_draws_the_simulations_wheel():
    """D69: the rig's wheel envelope and hip heights use the 10 in hub wheel the simulation runs (254 mm)."""
    import sys
    sys.path.insert(0, str(R / 'cad'))
    import rig_parts as rp
    assert rp.WHEEL_R == pytest.approx(lr.WHEEL_R * 1000)


def test_the_rigs_scenarios_crouch_to_the_lowest_controlled_leg():
    """D71: the rig's stand, squats and jump go no lower than 185 mm; the low case keeps the bumpers' 140 mm."""
    for name in ('stand_up', 'squat', 'jump'):
        sc = lc.RIG_SCENARIOS[name]
        lows = [lc.command(sc, t, {})[0] for t in np.arange(0.0, 3.0, 0.01)]
        assert min(x for x in lows if x is not None) == pytest.approx(lc.CROUCH_MM, abs=0.5), name
    low = lc.RIG_SCENARIOS['stand_up_low']
    assert lc.command(low, 0.0, {})[0] == pytest.approx(lc.LOW_MM) and low.start_h == lc.LOW_MM
