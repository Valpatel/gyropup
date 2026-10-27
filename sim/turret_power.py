"""The flywheels' current as the slip ring sees it: spin-up stepped or ramped, and an 8-shot burst (plan V3).

    .venv/bin/python sim/turret_power.py      # writes exports/turret/e2e/power.json and a plot

Chain (docs/turret-plan.md 2.4-2.6, main 5f09bd9): the ring's +24 V (an ideal 24 V behind the ring's series resistance,
10 or 60 mOhm) -> the 3 x 1,000 uF bank -> the 12 V flywheel regulator (Pololu D24V150F12: 90 % efficient, 32 A
instantaneous output limit, drops out under 13.3 V in) -> two AM32 ESCs -> two flywheel motors (sim/turret_launch.py MOTOR: the
SunnySky X2216 880KV since D42, its wheel about twice the Snail's inertia, so the same ramp draws about twice the current;
`ramp_sweep` finds the ramp that keeps the ring's peak in its budget).
Per motor: the ESC applies duty D so that D V_rail = ke w + R_eff i; the phase current i follows the speed loop
(stepped: the 10 A limit until the set speed; ramped: a PI on a 0 -> set-speed ramp of 200 ms), the DC-side current
is D i / eta_esc (power balance, eta_esc 0.95 est), the regulator's input current is P_out / (0.9 V_in), the bank
integrates the difference between the ring's current and the regulator's draw, and the ring's current is
(24 - V_bank) / R_ring. 10 us steps. The burst: 8 shots at 10/s, each shot taking the launch model's 7 % of the wheels'
speed in 4.8 ms (sim/turret_launch3d.py recoil), the loop recovering on the current limit. Outputs the 24 V-side
trace: peak, charge, RMS over 1 s, the bank's minimum voltage, the ESC and regulator peaks.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_common as tc  # noqa: E402

OUT = R / 'exports' / 'turret' / 'e2e'
PLAN = {'ring_r_ohm': (0.010, 0.060), 'bank_f': 3 * 1000e-6, 'bank_esr_ohm': 0.03, 'v_in': 24.0, 'reg_v': 12.0, 'reg_eff': 0.90, 'reg_i_max': 32.0, 'reg_dropout_v': 13.3,
        'esc_eff': 0.95, 'esc_i_limit': 10.0, 'ramp_s': 0.2,
        'source': 'docs/turret-plan.md 2.4-2.6 and 7.2 (main 5f09bd9): D24V150F12 regulator, 3 x 1,000 uF low-ESR bank, ring 10-60 mOhm, AM32 limits.current 10 A, a 200 ms set-speed ramp; '
                  'the bank ESR and the ESC efficiency are est'}


def simulate(mode, w_set, L, ring_r, dt=1e-5, t_end=1.0, burst=None, ramp_s=None):
    """mode: 'step' (set speed applied at t = 0 on the 10 A limit) or 'ramp' (set speed ramps over PLAN ramp_s).
    burst: (rate_hz, n_shots, drop_fraction, contact_s) to fire from t = 0.1 s with the wheels at speed."""
    tl = tc.sim_module('turret_launch')
    S = tl.MOTOR
    ke = 60.0 / (2 * math.pi * S['kv_rpm_v'])
    kt = S['kt']
    tf_per_w = kt * S['i0_a'] / (S['i0_at_rpm'] * 2 * math.pi / 60)
    Rm = L.r_eff_ohm
    n = int(t_end / dt)
    t = np.arange(n) * dt
    w = np.zeros(2)
    if burst:
        w[:] = w_set
    integ = np.zeros(2)
    vb = PLAN['v_in']
    i_ring = np.zeros(n)
    i_reg_in = np.zeros(n)
    i_esc_dc = np.zeros(n)
    v_bank = np.zeros(n)
    w_log = np.zeros(n)
    i_phase = np.zeros(n)
    shots = []
    if burst:
        rate, n_shots, drop, contact = burst
        shots = [(0.1 + k / rate, 0.1 + k / rate + contact) for k in range(n_shots)]
    for k in range(n):
        tk = t[k]
        tgt = w_set if mode == 'step' or burst else w_set * min(1.0, tk / (ramp_s or PLAN['ramp_s']))
        # the ball's drag on the wheels during a shot: a steady torque that takes drop * w_set in contact s
        load = 0.0
        for a, b in shots:
            if a <= tk < b:
                load = L.wheel_I * drop * w_set / (b - a)
        i_dc_tot = 0.0
        for j in range(2):
            err = tgt - w[j]
            integ[j] += err * dt
            i_cmd = L.kp * err * 1000 + L.ki * integ[j] * 1000
            i_cmd = max(-PLAN['esc_i_limit'], min(PLAN['esc_i_limit'], i_cmd))
            v_rail = PLAN['reg_v'] if vb > PLAN['reg_dropout_v'] else vb * PLAN['reg_v'] / PLAN['reg_dropout_v']
            i_avail = (v_rail - ke * w[j]) / Rm
            i = min(i_cmd, i_avail)
            i = max(i, -2.0)                                   # the loop does not brake hard here
            D = min(1.0, max(0.0, (ke * w[j] + Rm * i) / v_rail))
            tau = kt * i - tf_per_w * w[j] - load
            w[j] += tau / L.wheel_I * dt
            i_dc = D * i / PLAN['esc_eff'] if i > 0 else D * i
            i_dc_tot += i_dc
            if j == 0:
                i_phase[k] = i
        p_out = PLAN['reg_v'] * max(0.0, i_dc_tot)
        i_in = p_out / (PLAN['reg_eff'] * max(vb, 1.0))
        i_in = min(i_in, PLAN['reg_i_max'] * PLAN['reg_v'] / max(vb, 1.0))
        ir = (PLAN['v_in'] - vb) / ring_r
        vb += (ir - i_in) / PLAN['bank_f'] * dt
        i_ring[k], i_reg_in[k], i_esc_dc[k], v_bank[k], w_log[k] = ir, i_in, i_dc_tot, vb, w[0]
    sel = t <= 1.0
    out = {'ring_peak_a': round(float(i_ring.max()), 2), 'ring_rms_1s_a': round(float(np.sqrt(np.mean(i_ring[sel] ** 2))), 3), 'ring_charge_c': round(float(np.trapezoid(i_ring, t)), 4),
           'ring_mean_1s_a': round(float(i_ring[sel].mean()), 3), 'reg_in_peak_a': round(float(i_reg_in.max()), 2), 'esc_dc_peak_a': round(float(i_esc_dc.max()), 2),
           'phase_peak_a': round(float(i_phase.max()), 2), 'bank_v_min': round(float(v_bank.min()), 2), 'dropout': bool(v_bank.min() < PLAN['reg_dropout_v']),
           'time_to_95pct_speed_s': round(float(t[np.argmax(w_log >= 0.95 * w_set)]), 4) if (w_log >= 0.95 * w_set).any() else None,
           'trace': {'t': t[::100].tolist(), 'i_ring': i_ring[::100].round(3).tolist(), 'i_reg_in': i_reg_in[::100].round(3).tolist(), 'v_bank': v_bank[::100].round(3).tolist(), 'rpm': (w_log[::100] * 60 / (2 * math.pi)).round(0).tolist()}}
    return out


def study():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tl = tc.sim_module('turret_launch')
    l3 = tc.sim_module('turret_launch3d')
    OUT.mkdir(parents=True, exist_ok=True)
    L = l3.design_launcher()
    w_set = tl.set_speed_for(tl.DESIGN['nominal'], L, tl.DESIGN['set_fps'] * tl.FPS)
    l3j = R / 'exports' / 'turret' / 'launch' / 'launch3d.json'
    drop = json.loads(l3j.read_text())['recoil']['wheel_speed_drop_pct'][0] / 100 if l3j.exists() else 0.07
    contact = json.loads(l3j.read_text())['recoil']['contact_ms'] / 1000 if l3j.exists() else 0.0048
    res = {'plan': PLAN, 'set_rpm': round(w_set * 60 / (2 * math.pi)), 'wheel_I_kg_m2': L.wheel_I, 'energy_per_wheel_j': round(0.5 * L.wheel_I * w_set ** 2, 3), 'cases': {}}
    for rr in PLAN['ring_r_ohm']:
        for mode in ('step', 'ramp'):
            r = simulate(mode, w_set, L, rr)
            res['cases'][f'spinup_{mode}_ring_{int(rr * 1000)}mohm'] = {k: v for k, v in r.items() if k != 'trace'}
            if rr == PLAN['ring_r_ohm'][1]:
                res['cases'][f'spinup_{mode}_ring_{int(rr * 1000)}mohm']['trace'] = r['trace']
        r = simulate('step', w_set, L, rr, burst=(10.0, 8, drop, contact))
        res['cases'][f'burst_8_at_10_per_s_ring_{int(rr * 1000)}mohm'] = {k: v for k, v in r.items() if k != 'trace'} | ({'trace': r['trace']} if rr == PLAN['ring_r_ohm'][1] else {})
    # the ramp the ring needs with this motor: the peak on the paralleled pair (two 2 A circuits) at the high ring resistance
    res['ramp_sweep'] = []
    for rs in (0.2, 0.3, 0.4, 0.5, 0.6):
        r = simulate('ramp', w_set, L, PLAN['ring_r_ohm'][1], t_end=max(1.0, rs + 0.3), ramp_s=rs)
        res['ramp_sweep'].append({'ramp_s': rs, 'ring_peak_a': r['ring_peak_a'], 'per_circuit_a': round(r['ring_peak_a'] / 2, 2),
                                  'time_to_95pct_speed_s': r['time_to_95pct_speed_s'], 'within_2a_per_circuit': r['ring_peak_a'] / 2 <= 2.0})
    ok = [x['ramp_s'] for x in res['ramp_sweep'] if x['within_2a_per_circuit']]
    res['ramp_needed_s'] = min(ok) if ok else None
    res['verdict'] = {'ramp_ring_peak_a': res['cases']['spinup_ramp_ring_60mohm']['ring_peak_a'], 'step_ring_peak_a': res['cases']['spinup_step_ring_60mohm']['ring_peak_a'],
                      'burst_ring_peak_a': res['cases']['burst_8_at_10_per_s_ring_60mohm']['ring_peak_a'], 'burst_ring_rms_a': res['cases']['burst_8_at_10_per_s_ring_60mohm']['ring_rms_1s_a'],
                      'ramp_keeps_ring_under_3a': res['cases']['spinup_ramp_ring_60mohm']['ring_peak_a'] <= 3.0,
                      'no_dropout': not any(c['dropout'] for c in res['cases'].values())}
    (OUT / 'power.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    fig, ax = plt.subplots(1, 3, figsize=(15, 4), dpi=130)
    for key, lab in (('spinup_step_ring_60mohm', 'stepped (10 A limit)'), ('spinup_ramp_ring_60mohm', '200 ms ramp')):
        tr = res['cases'][key]['trace']
        ax[0].plot(np.array(tr['t']) * 1000, tr['i_ring'], label=f'ring current, {lab}')
        ax[1].plot(np.array(tr['t']) * 1000, tr['rpm'], label=lab)
    ax[0].set_xlim(0, 400)
    ax[0].set_xlabel('ms')
    ax[0].set_ylabel('A on the 24 V ring (60 mOhm)')
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    ax[1].set_xlim(0, 400)
    ax[1].set_xlabel('ms')
    ax[1].set_ylabel('wheel rpm')
    ax[1].legend(fontsize=7)
    ax[1].grid(alpha=0.3)
    tr = res['cases']['burst_8_at_10_per_s_ring_60mohm']['trace']
    ax[2].plot(np.array(tr['t']) * 1000, tr['i_ring'], label='ring current')
    ax[2].plot(np.array(tr['t']) * 1000, np.array(tr['v_bank']) - 20, label='bank V - 20')
    ax[2].set_xlabel('ms')
    ax[2].set_title('8 shots at 10/s: the recovery pulses', fontsize=9)
    ax[2].legend(fontsize=7)
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / 'power.png')
    plt.close(fig)
    return res


if __name__ == '__main__':
    r = study()
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'trace'} for k, v in r['cases'].items()}, indent=1))
    print(r['verdict'])
