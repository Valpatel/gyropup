"""sim/leg_limits.py: the leg's protection limits (docs/leg-protection.md) and the file the firmware, the rig and the
playground read.

    python -m pytest sim/test_leg_limits.py -q          # seconds; no MuJoCo (the jump sweep is read from the JSON)
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from sim import leg_limits as ll  # noqa: E402

D = json.loads(ll.OUT.read_text())
ROBOT, PLA = D['profiles']['robot'], D['profiles']['pla_bench']


def test_the_committed_file_is_what_the_sources_give():
    assert ll.build() == D, 're-run python -m sim.leg_limits (and firmware/balance/tools/gen_limits.py)'


def test_the_firmware_header_is_current():
    out = subprocess.run([sys.executable, str(R / 'firmware' / 'balance' / 'tools' / 'gen_limits.py'), '--check'],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_the_robot_leg_every_day_cap_is_its_weakest_every_day_row():
    rows = ROBOT['everyday_rows']
    weakest = min(rows, key=lambda r: r['nm'])
    assert ROBOT['everyday_nm'] == math.floor(weakest['nm'])
    assert weakest['part'] == 'hip_frame' and weakest['case'] == 'E3o'
    for r in rows:                                      # linear FEA: the row at its target carries T0 x SF / target
        assert r['nm'] == pytest.approx(r['at_nm'] * r['sf'] / r['target'], abs=0.06)


def test_the_peak_is_the_push_only_and_never_past_the_motor_or_a_rare_row():
    assert ROBOT['everyday_nm'] <= ROBOT['peak_nm'] <= 120.0
    assert ROBOT['peak_nm'] == math.floor(min(r['nm'] for r in ROBOT['peak_rows']))
    assert ROBOT['motor_limit_torque_nm'] == ROBOT['peak_nm']
    assert ROBOT['peak_max_s'] == 0.35                  # GP_JUMP_PUSH_MAX_S: the push's own time limit
    knee = ROBOT['knee_capacity']['weakest']['n']
    at = {r['cap_nm']: r for r in D['jump_sweep']['at_limits']}
    assert max(at[ROBOT['peak_nm']]['knee_push_n'], at[ROBOT['peak_nm']]['knee_after_n']) <= knee + 1.0
    assert max(at[ROBOT['everyday_nm']]['knee_push_n'], at[ROBOT['everyday_nm']]['knee_after_n']) <= knee


def test_the_rms_limit_is_under_the_every_day_cap_and_marked_pending_until_the_heat_model_lands():
    assert ROBOT['rms_nm'] < ROBOT['everyday_nm']
    assert ROBOT['rms_pending'] == (not ll.THERMAL.exists())
    assert 25.0 < ROBOT['rms_tau_s'] < 40.0


def test_the_pla_bench_leg_is_the_motor_day_cap_and_names_its_first_failure():
    der = json.loads(ll.DERATING.read_text())
    assert PLA['everyday_nm'] == PLA['peak_nm'] == PLA['motor_limit_torque_nm'] == der['pla_cap_nm'] <= 60.0
    ff = PLA['first_failure']
    assert ff['cap_nm'] > PLA['everyday_nm'] and not der['caps'][f"{ff['cap_nm']}"]['all_ok']
    assert ff['row'].startswith('wheel_link R1w')


def test_the_jump_sweep_shows_speed_not_torque_limits_the_jump():
    runs = {r['cap_nm']: r for r in D['jump_sweep']['runs']}
    assert runs[120.0]['jump_mm'] - runs[60.0]['jump_mm'] < 15.0           # double the torque, under 10 % more jump
    assert runs[120.0]['knee_push_n'] > 1.8 * runs[60.0]['knee_push_n']    # ... and nearly double the knees' load
    capped = D['jump_sweep']['capped_motor'][0]
    assert capped['motor_peak_nm'] == 60.0 and capped['jump_mm'] < 0.7 * runs[60.0]['jump_mm']


def test_soft_stops_never_push_further_into_a_stop_and_leave_a_motor_that_could_stop_in_time_alone():
    lo, hi = math.radians(-97.0), math.radians(3.0)
    m = math.radians(ll.SOFT_MARGIN_DEG)
    rnd = random.Random(7)
    untouched = 0
    for _ in range(20000):
        T = rnd.choice((PLA['everyday_nm'], ROBOT['everyday_nm']))
        tau, w = rnd.uniform(-T, T), rnd.uniform(-16.0, 16.0)
        phi = rnd.uniform(lo - 0.05, hi + 0.05)
        out = ll.soft_stop(tau, phi, w, lo, hi, T)
        if lo + m <= phi <= hi - m and w <= ll.approach_limit(hi - phi - m, T) and -w <= ll.approach_limit(phi - lo - m, T):
            assert out == tau
            untouched += 1
        if hi - phi < m:
            assert out <= 0.0                            # nothing towards hi: zeroed, or a brake away from it
        if phi - lo < m:
            assert out >= 0.0
        assert abs(out) <= max(abs(tau), T) + 1e-9
    assert untouched > 5000


def test_the_approach_limit_meets_the_stop_with_the_energy_it_takes_at_the_every_day_torque():
    J = D['soft_stop']['j_kg_m2']
    assert ll.j_leg() == J
    for p in (ROBOT, PLA):
        T = p['everyday_nm']
        w = ll.approach_limit(0.0, T)
        assert 0.5 * J * w * w == pytest.approx(T * T / (2 * ll.STOP_K_NM_PER_RAD))   # its peak: w sqrt(k J) = T
        assert w * math.sqrt(ll.STOP_K_NM_PER_RAD * J) == pytest.approx(T)
        assert ll.approach_limit(0.1, T) > w
    # the robot's leg at its fastest (the jump's 12.8 rad/s) must start braking well outside the old 10 deg zone
    assert D['soft_stop']['brake_from_no_load_deg']['robot'] > 12.0


def test_the_soft_stops_assume_the_whole_leg_behind_a_stop_not_the_rotor_alone():
    inn = D['inertia']
    worst = max(v['kg_m2'] for v in inn['worst'].values())
    assert inn['bound_kg_m2'] >= worst and inn['bound_kg_m2'] - worst < 0.0011
    assert worst > 4 * inn['rotor_and_upper_link_kg_m2']          # the lower links and the 4 kg wheel dominate
    assert all(v['kg_m2'] <= worst for v in inn['at_stops'].values()) and len(inn['at_stops']) == 4
    assert D['soft_stop']['j_kg_m2'] == inn['bound_kg_m2']


def test_a_free_swing_into_each_stop_meets_it_at_no_more_than_its_build_s_every_day_torque():
    runs = D['free_swing']
    assert len(runs) == 16                                          # 2 builds x 2 motors x 2 stops, guarded and not
    for r in runs:
        if r['soft_stops']:
            # the stop's peak: the contact (at most the every-day torque) plus the hanging leg's own weight on it
            assert r['peak_stop_nm'] <= r['drive_nm'] + 10.0, r
            assert r['contact_rad_s'] <= D['soft_stop']['contact_rad_s'][r['build']] * 1.15 + 0.3, r
    worse = [(a, b) for a in runs for b in runs if a['soft_stops'] and not b['soft_stops'] and
             (a['build'], a['motor'], a['stop']) == (b['build'], b['motor'], b['stop'])]
    assert len(worse) == 8 and all(b['peak_stop_nm'] > a['peak_stop_nm'] for a, b in worse)


def test_the_peak_also_holds_at_the_hips_and_the_knee_base_is_the_record_s():
    fea = json.loads(ll.FEA.read_text())
    assert ll.r1_knee_force(fea) == ROBOT['knee_capacity']['at_n'] == 574.0
    hip = ROBOT['hip_capacity']
    assert hip['row'] == 'hip_frame R1' and hip['n'] == pytest.approx(574.0 * hip['sf'] / hip['target'], abs=0.1)
    at = {r['cap_nm']: r for r in D['jump_sweep']['at_limits']}[ROBOT['peak_nm']]
    assert max(at['hip_push_n'], at['hip_after_n']) <= hip['n']
    assert any(r['case'] == 'R1 (hip force)' for r in ROBOT['peak_rows'])


def test_every_commanded_pose_is_reachable_inside_the_stops_and_away_from_dead_points():
    lo_f, hi_f = math.radians(-97.0), math.radians(3.0)
    lo_r, hi_r = -math.pi - hi_f, -math.pi - lo_f
    m = math.radians(D['command']['margin_deg']) - 1e-6
    for lean, a, b in D['command']['window']:
        for L in (a, (a + b) / 2, b):
            q = ll.fb.stance(L * 1000.0, math.degrees(lean))
            assert q is not None
            assert lo_f + m <= q[0] <= hi_f - m and lo_r + m <= q[1] <= hi_r - m
            assert ll.dead_point_margin(*q) >= D['command']['dead_point_min_deg'] - 0.5
    # the controller's own range upright, the sit and the jump's crouch fit; full height leaning back 0.35 rad does not
    assert ll.window_at(D['command']['window'], 0.0)[0] <= 0.110 and ll.window_at(D['command']['window'], 0.0)[1] >= 0.375
    assert ll.window_at(D['command']['window'], -0.35)[1] < 0.375
    assert ll.fb.stance(375.0, math.degrees(-0.35)) is None                   # it is out of the five-bar's reach


def test_the_stops_alone_allow_no_crossed_or_unreachable_pose_but_their_squeeze_can_reach_a_dead_point():
    s = D['stop_box']
    assert s['unreachable'] == 0 and s['crossed'] == 0
    assert s['dead_point_min_deg'] < D['command']['dead_point_min_deg']       # but they do reach near a dead point
    assert D['dead_limp_deg'] < s['dead_point_min_deg']                       # so the dead-point limp never trips inside them
    # the knee-in/knee-in corner: one motor 4 deg past its stop (the sleeve's squeeze at 61 N m is 4.1) is a dead point
    fo, fi, ro, ri = ll.fb.stop_angles()
    squeeze = math.degrees(ROBOT['everyday_nm'] / ll.STOP_K_NM_PER_RAD)
    assert squeeze > 4.0
    assert ll.dead_point_margin(fi - math.radians(4.0), ri) < 0.5
    assert ll.dead_point_margin(fi - math.radians(2.5), ri) < D['dead_limp_deg']    # the limp trips before it


def test_the_window_overlap_keeps_a_lagging_lean_inside_the_stops():
    tab = D['command']['window']
    lo_f, hi_f = math.radians(-97.0), math.radians(3.0)
    lo_r, hi_r = -math.pi - hi_f, -math.pi - lo_f
    for lean_cmd in (-0.35, -0.2, 0.0, 0.1):
        for err in (-0.1, -0.05, 0.05, 0.1):
            for L in (0.05, 0.25, 0.5):
                Lc = ll.clamp_L(L, lean_cmd, lean_cmd + err, tab)
                q = ll.fb.stance(Lc * 1000.0, math.degrees(lean_cmd + err))
                assert q is not None and lo_f <= q[0] <= hi_f and lo_r <= q[1] <= hi_r
