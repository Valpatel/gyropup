"""The turret's power from its one XT30 input (D66), with the D68 flywheels: every supply, the ring, the stand's rocker.

    .venv/bin/python sim/turret_power.py      # writes exports/turret/e2e/power.json and power.png (~2 min: run it on a GB10)

The chain (docs/turret-wiring.md 4, docs/turret-sections.md 7): a supply (one DCB609 in 20 V mode on the stand, 15 V
empty under load to 20.5 V full; or Gyropup's 10S bus, 30 V near empty to 42 V full) behind its source resistance (the
pack or bus, the leads, the fuses, the rocker, the XT30: est) -> the plinth's input node. On that node: the J4012 (a
constant power, up to 48 W: 40 W module + 8 W carrier, fan and SSD, est), and the head branch through its 10 A fuse to
the base board, which takes the pan servo's 12 V (D36V50F12, 90 %) and sends the rest up the slip ring's three
paralleled +BUS circuits and back on three GND circuits (each circuit 2 x 250 mm of the ring's 28 AWG leads, 0.107 Ohm,
plus a contact of 10 or 60 mOhm) to the bay's bank (2 x 470 uF 63 V). On the bank: the flywheel rail (TDK i6A4W, buck
to the trimmed 11.31 V; 95.5 % at 15 V in to 93 % at 42 V, plus 1 W of its own: est inside TDK's 90-97 %; it holds
the rail until its input is within 0.8 V of it, est, and stops under 8 V), the tilt servo's 12 V AUX (D36V50F12, 90 %),
the 5 V logic (D36V28F5; the MCU, the gates, the laser: 3 W typical, 5 W peak at the bank). The rail, switched by ARM
(Pololu 2815), feeds the two AM32 ESCs and the feed servo.
Per motor (sim/turret_launch.py MOTOR: the SunnySky X2216 1400 KV, D68): the ESC applies duty D so that D V_rail =
ke w + R_eff i; the phase current follows a PI speed loop on a 0 -> set-speed ramp (the firmware's 800 ms, or the ramp
under study), clipped at AM32's 10 A; the DC side is D i / 0.95 (power balance, est). 20 us steps. The burst: 8 shots
at 10/s with the wheels at speed, each shot taking the launch model's speed drop in its contact time
(exports/turret/launch/launch3d.json recoil).
The servos (three STS3215 at 12 V): 1.5 A each at the firmware's 50 % torque cap (2.7 A stall at 12 V, est), 0.6 A
moving, 0.15 A holding (est). The peak cases put every servo that can move at its cap at once (pan and tilt aiming
through a spin-up; pan, tilt and the feed through a burst) with the J4012 at 48 W: a coincidence worse than play.
'play' puts them moving (0.6 A), not at their caps, the J4012 still at 48 W; 'typical' holding, the J4012 at 25 W.
Judged (the ring's 2 A a circuit and the rocker's 10 A are heating ratings): a spin-up by its 100 ms peak (the ramp's
top lasts ~0.2 s), a burst by its worst 1 s RMS (each shot's recovery pulse, 2 x 10 A at the rail, lasts ~10 ms); the
instantaneous peaks are listed beside them. The ring's busiest circuit carries 42 % of the ring's current (its contact
at 10 mOhm, the other two at 60). The sweeps find, per supply, the slowest spin-up ramp and the fastest 8-shot burst
that keep the ring and, on the stand, the rocker within those ratings: the firmware's profile by BUS_V.
The game average (est): per minute, ARM held 30 s with 4 spin-ups and 4 bursts of 8; pan and tilt moving 30 % of the
time; the feed stepping 0.1 s a shot; the J4012 at 25 W (typical) or 48 W (flat out).
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
SUPPLIES = {'pack_15v': 15.0, 'pack_20v5': 20.5, 'bus_30v': 30.0, 'bus_42v': 42.0}
SWEEP_V = {**SUPPLIES, 'pack_18v': 18.0}                 # + the pack's nominal, for the firmware's profile
PLAN = {
    'supplies_v': SUPPLIES,
    'source_r_ohm': {'pack': 0.060, 'bus': 0.040},          # est: the DCB609 (5S3P in 20 V mode) or the bus branch, leads, fuses, XT30
    'ring': {'circuits': 3, 'lead_ohm': 0.107, 'contact_ohm': (0.010, 0.060), 'rating_a': 2.0,
             'note': 'SparkFun ROB-13065: 12 x 2 A; circuits 1, 2, 11 = +BUS, 3, 4, 12 = GND (docs/turret-wiring.md 1.2); '
                     'each 2 x 250 mm of 28 AWG (0.213 Ohm/m) and its contact'},
    'head_wiring_ohm': 0.015,                                # est: 18 AWG base lead, the board tails, the bay's leads
    'bank_f': 2 * 470e-6, 'bank_esr_ohm': 0.02,              # 2 x Panasonic EEU-FR1J471B in parallel (est ESR 0.04 each)
    'rail_v': None,                                          # sim/turret_launch.py RAIL_V_TRIM (set at import)
    'i6_eff': ((15.0, 0.955), (42.0, 0.93)), 'i6_own_w': 1.0, 'i6_headroom_v': 0.8, 'i6_off_v': 8.0, 'i6_ocp_a': 27.0,
    'esc_eff': 0.95, 'esc_i_limit': 10.0, 'ramp_s': 0.8,
    'servo': {'v': 12.0, 'cap_a': 1.5, 'move_a': 0.6, 'hold_a': 0.15, 'reg_eff': 0.90},
    'logic_w': {'typical': 3.0, 'peak': 5.0},
    'j4012_w': {'typical': 25.0, 'peak': 48.0},
    # D70: the stand's switch is DC-rated for 15 A or more: a Blue Sea 6006 battery switch (48 V DC, 275 A continuous)
    # replaces the Bulgin R13244AAAA rocker (10 A 28 V DC), which the 800 ms / 10/s case put at 11-14 A on the empty pack
    'rocker': {'part': 'blue-sea-6006', 'rating_a': 275.0, 'rating_v': 48.0, 'was': {'part': 'bulgin-r13244aaaa', 'rating_a': 10.0}},
    'game_per_min': {'arm_s': 30.0, 'spinups': 4, 'bursts': 4, 'shots_per_burst': 8, 'aim_moving_frac': 0.3, 'feed_step_s': 0.1},
    'source': 'D66 (the input), D68 (the flywheels: X2216 1400 KV, the trimmed ~11.31 V rail, AM32 10 A, the 800 ms ramp); '
              'docs/turret-wiring.md 4-5; the converters\' data sheets; est where marked',
}


# the load levels: 'worst' every servo that can move at its torque cap at once and the J4012 flat out (a coincidence
# worse than play); 'play' the servos moving (not at their caps), the J4012 flat out; 'typical' holding, 25 W
LOADS = {'worst': {'aim': 'cap_a', 'feed': 'cap_a', 'j4012': 'peak', 'logic': 'peak'},
         'play': {'aim': 'move_a', 'feed': 'move_a', 'j4012': 'peak', 'logic': 'peak'},
         'play_j25': {'aim': 'move_a', 'feed': 'move_a', 'j4012': 'typical', 'logic': 'peak'},
         'worst_j25': {'aim': 'cap_a', 'feed': 'cap_a', 'j4012': 'typical', 'logic': 'peak'},
         'typical': {'aim': 'hold_a', 'feed': 'move_a', 'j4012': 'typical', 'logic': 'typical'}}


def _ring_r(contact):
    """The ring's + and return paths in series, three circuits in parallel each way."""
    n, lead = PLAN['ring']['circuits'], PLAN['ring']['lead_ohm']
    return 2 * (lead + contact) / n


def _worst_share():
    """The share of the ring's current on its busiest circuit: one contact at 10 mOhm, the other two at 60."""
    lo, hi = PLAN['ring']['contact_ohm']
    g_lo, g_hi = 1 / (PLAN['ring']['lead_ohm'] + lo), 1 / (PLAN['ring']['lead_ohm'] + hi)
    return g_lo / (g_lo + (PLAN['ring']['circuits'] - 1) * g_hi)


def _i6_eff(v):
    (v0, e0), (v1, e1) = PLAN['i6_eff']
    return e0 + (e1 - e0) * min(1.0, max(0.0, (v - v0) / (v1 - v0)))


def _avg(x, n):
    """Moving average over n samples (for the 100 ms figures)."""
    if n <= 1:
        return x
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = (c[n:] - c[:-n]) / n
    return np.concatenate([np.full(n - 1, out[0]), out])


def simulate(supply, w_set, L, contact, mode='spinup', ramp_s=None, dt=2e-5, t_end=None, loads='peak', burst=None):
    """One case at one supply. mode 'spinup' (0 -> w_set on the ramp) or 'burst' (the wheels at speed, 8 shots at
    10/s from 0.1 s) or 'hold' (at speed, nothing fired). loads 'peak': the servos that can move at their caps, the
    J4012 at 48 W, the logic at 5 W; 'typical': the servos holding, 25 W and 3 W."""
    tl = tc.sim_module('turret_launch')
    S = tl.MOTOR
    ke = 60.0 / (2 * math.pi * S['kv_rpm_v'])
    kt = S['kt']
    tf_per_w = kt * S['i0_a'] / (S['i0_at_rpm'] * 2 * math.pi / 60)
    Rm = L.r_eff_ohm
    ramp_s = ramp_s or PLAN['ramp_s']
    v_s = SWEEP_V[supply]
    r_src = PLAN['source_r_ohm']['pack' if supply.startswith('pack') else 'bus']
    r_ring = _ring_r(contact) + PLAN['head_wiring_ohm']
    C, esr = PLAN['bank_f'], PLAN['bank_esr_ohm']
    sv = PLAN['servo']
    rail = PLAN['rail_v']
    lv = LOADS[loads]
    p_j = PLAN['j4012_w'][lv['j4012']]
    p_logic = PLAN['logic_w'][lv['logic']]
    i_pan = i_tilt = sv[lv['aim']]
    i_feed_step = sv[lv['feed']]
    p_pan_in = sv['v'] * i_pan / sv['reg_eff']                 # from the plinth node (the base board's D36V50F12)
    p_tilt_in = sv['v'] * i_tilt / sv['reg_eff']               # from the bank (U15, 12 V AUX)
    if t_end is None:
        t_end = ramp_s + 0.5 if mode == 'spinup' else (1.1 if mode == 'burst' else 0.3)
    n = int(round(t_end / dt))
    shots = []
    if mode == 'burst':
        rate, n_shots, drop, contact_s = burst
        shots = [(0.1 + k / rate, 0.1 + k / rate + contact_s) for k in range(n_shots)]
    feed_on = (0.1, 0.1 + (shots[-1][0] - shots[0][0]) + 0.1) if shots else None
    w = [w_set, w_set] if mode != 'spinup' else [0.0, 0.0]
    integ = [0.0, 0.0]
    if mode != 'spinup':                                       # start in the steady state: the loop's integral holds the drag
        integ = [tf_per_w * w_set / kt / (L.ki * 1000)] * 2
    vb = v_s
    v_node = v_s
    i_tot_prev = 0.0
    log = {k: np.zeros(n) for k in ('i_in', 'i_ring', 'v_bank', 'p_fly_in', 'rpm', 'i_base')}
    kp, ki, ilim = L.kp * 1000, L.ki * 1000, PLAN['esc_i_limit']
    for k in range(n):
        tk = k * dt
        tgt = w_set * min(1.0, tk / ramp_s) if mode == 'spinup' else w_set
        load = 0.0
        for a, b in shots:
            if a <= tk < b:
                load = L.wheel_I * drop * w_set / (b - a)
        # the rail: regulated while the bank stays over it plus the headroom, then it follows the bank down; off under 8 V
        v_rail = rail if vb > rail + PLAN['i6_headroom_v'] else max(0.0, vb - PLAN['i6_headroom_v'])
        if vb < PLAN['i6_off_v']:
            v_rail = 0.0
        i_dc_tot = 0.0
        for j in (0, 1):
            err = tgt - w[j]
            integ[j] += err * dt
            i_cmd = max(-ilim, min(ilim, kp * err + ki * integ[j]))
            i_av = (v_rail - ke * w[j]) / Rm
            i = max(min(i_cmd, i_av), -2.0)
            D = min(1.0, max(0.0, (ke * w[j] + Rm * i) / v_rail)) if v_rail > 0 else 0.0
            w[j] += (kt * i - tf_per_w * w[j] - load) / L.wheel_I * dt
            i_dc_tot += D * i / PLAN['esc_eff'] if i > 0 else D * i
        i_feed = i_feed_step if (feed_on and feed_on[0] <= tk < feed_on[1]) else sv['hold_a']
        p_rail = v_rail * (max(0.0, i_dc_tot) + i_feed)                # the feed servo on the rail (11.31 V)
        p_fly_in = p_rail / _i6_eff(vb) + PLAN['i6_own_w'] if v_rail > 0 else 0.0
        p_rail_out_cap = PLAN['i6_ocp_a'] * rail
        p_fly_in = min(p_fly_in, p_rail_out_cap / _i6_eff(vb) + PLAN['i6_own_w'])
        p_head = p_fly_in + p_tilt_in + p_logic
        i_head = p_head / max(vb, 1.0)
        # the plinth's node from the last step's total, the ring into the bank (through the bank's ESR)
        v_node = v_s - r_src * i_tot_prev
        i_ring = (v_node - vb) / (r_ring + esr) + (i_head * esr) / (r_ring + esr)
        vb += (i_ring - i_head) / C * dt
        i_base = p_pan_in / max(v_node, 1.0) + i_ring
        i_tot = i_base + p_j / max(v_node, 1.0)
        i_tot_prev = i_tot
        L_ = log
        L_['i_in'][k], L_['i_ring'][k], L_['v_bank'][k], L_['p_fly_in'][k], L_['rpm'][k], L_['i_base'][k] = i_tot, i_ring, vb, p_fly_in, w[0] * 60 / (2 * math.pi), i_base
    t = np.arange(n) * dt
    n100 = int(round(0.1 / dt))
    share = _worst_share()
    i_in100, i_ring100 = _avg(log['i_in'], n100), _avg(log['i_ring'], n100)
    n1s = min(n, int(round(1.0 / dt)))                         # the 1 s RMS (a contact's and a lead's heating): the worst second
    ring_rms1 = float(np.sqrt(_avg(log['i_ring'] ** 2, n1s).max()))
    in_rms1 = float(np.sqrt(_avg(log['i_in'] ** 2, n1s).max()))
    rpm = log['rpm']
    w95 = 0.95 * w_set * 60 / (2 * math.pi)
    return {
        'supply': supply, 'supply_v': v_s, 'contact_ohm': contact, 'mode': mode, 'loads': loads, 'ramp_s': ramp_s if mode == 'spinup' else None,
        'input_peak_a': round(float(log['i_in'].max()), 2), 'input_peak_100ms_a': round(float(i_in100.max()), 2),
        'input_mean_a': round(float(log['i_in'].mean()), 2),
        'ring_peak_a': round(float(log['i_ring'].max()), 2), 'ring_peak_100ms_a': round(float(i_ring100.max()), 2),
        'ring_per_circuit_peak_100ms_a': round(float(i_ring100.max()) * share, 2), 'ring_per_circuit_peak_a': round(float(log['i_ring'].max()) * share, 2),
        'ring_mean_a': round(float(log['i_ring'].mean()), 2),
        'ring_per_circuit_rms_1s_a': round(ring_rms1 * share, 2), 'input_rms_1s_a': round(in_rms1, 2),
        'head_branch_peak_100ms_a': round(float(_avg(log['i_base'], n100).max()), 2),
        'flywheel_in_peak_w': round(float(log['p_fly_in'].max()), 1), 'flywheel_in_peak_100ms_w': round(float(_avg(log['p_fly_in'], n100).max()), 1),
        'flywheel_in_energy_j': round(float(log['p_fly_in'].sum() * dt), 2), 'flywheel_in_end_w': round(float(log['p_fly_in'][-int(0.05 / dt):].mean()), 1),
        'bank_v_min': round(float(log['v_bank'].min()), 2),
        'rail_held': bool(log['v_bank'].min() > PLAN['rail_v'] + PLAN['i6_headroom_v']),
        'time_to_95pct_speed_s': round(float(t[np.argmax(rpm >= w95)]), 3) if (rpm >= w95).any() else None,
        'duration_s': t_end,
        'trace': {'t': t[::250].round(4).tolist(), 'i_in': log['i_in'][::250].round(3).tolist(), 'i_ring': log['i_ring'][::250].round(3).tolist(),
                  'v_bank': log['v_bank'][::250].round(3).tolist(), 'p_fly_in': log['p_fly_in'][::250].round(2).tolist(), 'rpm': rpm[::250].round(0).tolist()},
    }


def _strip(r):
    return {k: v for k, v in r.items() if k != 'trace'}


def game_average(res_sup, v_s):
    """The game's average input power and current at one supply (PLAN game_per_min, est), from the flywheel cases."""
    g, sv = PLAN['game_per_min'], PLAN['servo']
    hold_w = res_sup['hold']['flywheel_in_end_w']
    e_spin = res_sup['spinup_typical']['flywheel_in_energy_j']
    t_spin = res_sup['spinup_typical']['duration_s']
    e_burst = res_sup['burst_typical']['flywheel_in_energy_j'] - hold_w * res_sup['burst_typical']['duration_s']
    fly_j = g['spinups'] * e_spin + max(0.0, g['arm_s'] - g['spinups'] * t_spin) * hold_w + g['bursts'] * e_burst
    i_aim = g['aim_moving_frac'] * sv['move_a'] + (1 - g['aim_moving_frac']) * sv['hold_a']
    aim_w = 2 * sv['v'] * i_aim / sv['reg_eff']                                   # pan + tilt
    shots = g['bursts'] * g['shots_per_burst']
    feed_as = shots * g['feed_step_s'] * sv['move_a'] + (g['arm_s'] - shots * g['feed_step_s']) * sv['hold_a']   # powered only while ARM
    feed_w = sv['v'] * feed_as / 60.0 / _i6_eff(v_s)
    head = fly_j / 60.0 + feed_w + aim_w / 2 + PLAN['logic_w']['typical']          # the ring's share: no pan servo
    out = {}
    for mode, pj in (('typical', PLAN['j4012_w']['typical']), ('flat_out', PLAN['j4012_w']['peak'])):
        p = fly_j / 60.0 + feed_w + aim_w + PLAN['logic_w']['typical'] + pj
        out[mode] = {'input_w': round(p, 1), 'input_a': round(p / v_s, 2)}
    out['flywheels_w'] = round(fly_j / 60.0, 1)
    out['flywheels_holding_w'] = hold_w
    out['ring_mean_a'] = round(head / v_s, 2)
    out['ring_mean_per_circuit_a'] = round(head / v_s / PLAN['ring']['circuits'], 2)
    return out


def _judge(spin, bursts, cap):
    """Within a rating: the spin-up's 100 ms peak (the ramp's top lasts ~0.2 s) and the burst's worst 1 s RMS (its
    recovery pulses last ~10 ms each: a heating matter) both at or under cap."""
    return spin <= cap and bursts <= cap


def study():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tl = tc.sim_module('turret_launch')
    l3 = tc.sim_module('turret_launch3d')
    PLAN['rail_v'] = tl.RAIL_V_TRIM
    OUT.mkdir(parents=True, exist_ok=True)
    L = l3.design_launcher()
    w_set = tl.set_speed_for(tl.DESIGN['nominal'], L, tl.DESIGN['set_fps'] * tl.FPS)
    l3j = R / 'exports' / 'turret' / 'launch' / 'launch3d.json'
    rec = json.loads(l3j.read_text())['recoil'] if l3j.exists() else {'wheel_speed_drop_pct': [5.7], 'contact_ms': 5.1}
    drop, contact_s = rec['wheel_speed_drop_pct'][0] / 100, rec['contact_ms'] / 1000
    burst = (10.0, 8, drop, contact_s)
    lo, hi = PLAN['ring']['contact_ohm']
    ring_cap, rocker_cap = PLAN['ring']['rating_a'], PLAN['rocker']['rating_a']
    res = {'plan': PLAN, 'loads': LOADS, 'set_rpm': round(w_set * 60 / (2 * math.pi)), 'wheel_I_kg_m2': L.wheel_I,
           'energy_pair_j': round(L.wheel_I * w_set ** 2, 2), 'ring_worst_share': round(_worst_share(), 3),
           'burst': {'rate_hz': burst[0], 'shots': burst[1], 'speed_drop': drop, 'contact_s': contact_s},
           'judged_on': 'a spin-up by its 100 ms peak, a burst by its worst 1 s RMS (ring: the busiest of 3 circuits; rocker: the whole input)',
           'supplies': {}}
    for sup, v in SUPPLIES.items():
        s = {}
        for lv in ('worst', 'play'):
            s[f'spinup_{lv}'] = simulate(sup, w_set, L, hi, 'spinup', loads=lv)
            s[f'burst_{lv}'] = simulate(sup, w_set, L, hi, 'burst', loads=lv, burst=burst)
        s['burst_worst_low_contact'] = simulate(sup, w_set, L, lo, 'burst', loads='worst', burst=burst)
        s['spinup_typical'] = simulate(sup, w_set, L, hi, 'spinup', loads='typical')
        s['burst_typical'] = simulate(sup, w_set, L, hi, 'burst', loads='typical', burst=burst)
        s['hold'] = simulate(sup, w_set, L, hi, 'hold', loads='typical')
        summ = {}
        for lv in ('worst', 'play'):
            sp, bu = s[f'spinup_{lv}'], s[f'burst_{lv}']
            extra = [s['burst_worst_low_contact']] if lv == 'worst' else []
            summ[lv] = {'spinup_input_peak_100ms_a': sp['input_peak_100ms_a'], 'burst_input_rms_1s_a': bu['input_rms_1s_a'],
                        'burst_input_peak_100ms_a': bu['input_peak_100ms_a'], 'input_peak_a': max(c['input_peak_a'] for c in [sp, bu] + extra),
                        'spinup_ring_per_circuit_100ms_a': sp['ring_per_circuit_peak_100ms_a'], 'burst_ring_per_circuit_rms_1s_a': bu['ring_per_circuit_rms_1s_a'],
                        'burst_ring_per_circuit_100ms_a': bu['ring_per_circuit_peak_100ms_a'],
                        'ring_per_circuit_peak_a': max(c['ring_per_circuit_peak_a'] for c in [sp, bu] + extra),
                        'head_branch_peak_100ms_a': max(sp['head_branch_peak_100ms_a'], bu['head_branch_peak_100ms_a']),
                        'flywheel_in_peak_100ms_w': sp['flywheel_in_peak_100ms_w'], 'flywheel_in_peak_w': max(c['flywheel_in_peak_w'] for c in [sp, bu] + extra),
                        'bank_v_min': min(c['bank_v_min'] for c in [sp, bu] + extra), 'rail_held': all(c['rail_held'] for c in [sp, bu] + extra)}
            summ[lv]['ring_within_2a'] = _judge(sp['ring_per_circuit_peak_100ms_a'], bu['ring_per_circuit_rms_1s_a'], ring_cap)
            if sup.startswith('pack'):
                summ[lv]['rocker_within_10a'] = _judge(sp['input_peak_100ms_a'], bu['input_rms_1s_a'], rocker_cap)
        summ['time_to_95pct_speed_s'] = s['spinup_play']['time_to_95pct_speed_s']
        summ['hold_input_a'] = s['hold']['input_mean_a']
        summ['hold_ring_per_circuit_a'] = round(s['hold']['ring_mean_a'] * res['ring_worst_share'], 2)
        s['summary'] = summ
        s['average'] = game_average(s, v)
        res['supplies'][sup] = s
    # what the firmware must do on each supply (play loads) to keep the ring's busiest circuit within 2 A and, on the
    # stand, the input within the rocker's 10 A: the spin-up ramp and the burst rate
    res['ramp_sweep'], res['rate_sweep'], res['needed'] = [], [], {}
    for sup in ('pack_15v', 'pack_18v', 'pack_20v5', 'bus_30v', 'bus_42v'):
        pack = sup.startswith('pack')
        need = {}
        for lv in (('play', 'play_j25') if pack else ('play',)):
            n_ring = n_rock = None
            for rs in (0.8, 1.0, 1.2, 1.6, 2.0, 2.4, 3.0, 4.0):
                r = simulate(sup, w_set, L, hi, 'spinup', ramp_s=rs, loads=lv)
                row = {'supply': sup, 'loads': lv, 'ramp_s': rs, 'ring_peak_a': r['ring_peak_100ms_a'], 'per_circuit_a': r['ring_per_circuit_peak_100ms_a'],
                       'input_peak_100ms_a': r['input_peak_100ms_a'], 'flywheel_in_peak_100ms_w': r['flywheel_in_peak_100ms_w'],
                       'time_to_95pct_speed_s': r['time_to_95pct_speed_s'], 'within_2a_per_circuit': r['ring_per_circuit_peak_100ms_a'] <= ring_cap,
                       'within_rocker': (r['input_peak_100ms_a'] <= rocker_cap) if pack else None}
                res['ramp_sweep'].append(row)
                n_ring = rs if n_ring is None and row['within_2a_per_circuit'] else n_ring
                n_rock = rs if pack and n_rock is None and row['within_rocker'] else n_rock
                if n_ring is not None and (n_rock is not None or not pack):
                    break
            b_ring = b_rock = None
            for hz in (10.0, 6.0, 4.0, 3.0, 2.0, 1.0):
                r = simulate(sup, w_set, L, hi, 'burst', loads=lv, burst=(hz, 8, drop, contact_s), t_end=0.3 + 8 / hz)
                row = {'supply': sup, 'loads': lv, 'rate_hz': hz, 'per_circuit_rms_1s_a': r['ring_per_circuit_rms_1s_a'],
                       'input_rms_1s_a': r['input_rms_1s_a'], 'rail_held': r['rail_held'], 'bank_v_min': r['bank_v_min'],
                       'within_2a_per_circuit': r['ring_per_circuit_rms_1s_a'] <= ring_cap,
                       'within_rocker': (r['input_rms_1s_a'] <= rocker_cap) if pack else None}
                res['rate_sweep'].append(row)
                b_ring = hz if b_ring is None and row['within_2a_per_circuit'] else b_ring
                b_rock = hz if pack and b_rock is None and row['within_rocker'] else b_rock
                if b_ring is not None and (b_rock is not None or not pack):
                    break
            need[lv] = {'ramp_s_for_ring': n_ring, 'ramp_s_for_rocker': n_rock, 'burst_hz_for_ring': b_ring, 'burst_hz_for_rocker': b_rock}
        res['needed'][sup] = need
    # the stand's profile (the firmware, on BUS_V under 24 V): the longest ramp and the slowest burst any pack voltage
    # needs, checked again at 15 V with every load at its worst
    np_ = [res['needed']['pack_15v']['play']]                                    # the empty pack sets it
    ramps = [x['ramp_s_for_ring'] for x in np_] + [x['ramp_s_for_rocker'] for x in np_]
    rates = [x['burst_hz_for_ring'] for x in np_] + [x['burst_hz_for_rocker'] for x in np_]
    prof = {'ramp_s': max(r for r in ramps if r is not None) if all(r is not None for r in ramps) else None,
            'burst_hz': min(r for r in rates if r is not None) if all(r is not None for r in rates) else None}
    if prof['ramp_s'] and prof['burst_hz']:
        for lv in ('play', 'worst', 'worst_j25'):
            sp = simulate('pack_15v', w_set, L, hi, 'spinup', ramp_s=prof['ramp_s'], loads=lv)
            bu = simulate('pack_15v', w_set, L, hi, 'burst', loads=lv, burst=(prof['burst_hz'], 8, drop, contact_s), t_end=0.3 + 8 / prof['burst_hz'])
            prof[f'at_15v_{lv}'] = {'spinup_ring_per_circuit_100ms_a': sp['ring_per_circuit_peak_100ms_a'], 'burst_ring_per_circuit_rms_1s_a': bu['ring_per_circuit_rms_1s_a'],
                                    'spinup_input_peak_100ms_a': sp['input_peak_100ms_a'], 'burst_input_rms_1s_a': bu['input_rms_1s_a'],
                                    'time_to_95pct_speed_s': sp['time_to_95pct_speed_s'], 'rail_held': sp['rail_held'] and bu['rail_held'],
                                    'ring_ok': _judge(sp['ring_per_circuit_peak_100ms_a'], bu['ring_per_circuit_rms_1s_a'], ring_cap),
                                    'rocker_ok': _judge(sp['input_peak_100ms_a'], bu['input_rms_1s_a'], rocker_cap)}
    res['stand_profile'] = prof
    p15 = res['supplies']['pack_15v']['summary']
    res['rocker'] = {'part': PLAN['rocker']['part'], 'rating': f"{PLAN['rocker']['rating_a']:.0f} A {PLAN['rocker']['rating_v']:.0f} V DC", 'stand_v': [15.0, 20.5],
                     'at_800ms_10hz_15v': {lv: {'spinup_peak_100ms_a': p15[lv]['spinup_input_peak_100ms_a'], 'burst_rms_1s_a': p15[lv]['burst_input_rms_1s_a'],
                                                'instant_peak_a': p15[lv]['input_peak_a'], 'ok': p15[lv]['rocker_within_10a']} for lv in ('worst', 'play')},
                     'idle_at_15v_a': p15['hold_input_a'],
                     'average_at_15v_a': {k: res['supplies']['pack_15v']['average'][k]['input_a'] for k in ('typical', 'flat_out')},
                     'voltage_ok': SUPPLIES['pack_20v5'] <= PLAN['rocker']['rating_v'],
                     'with_the_stand_profile': {lv: prof.get(f'at_15v_{lv}', {}).get('rocker_ok') for lv in ('play', 'worst', 'worst_j25')}}
    # the keys cad/turret_mount.py reads (the robot: the 10S bus at 30 V, its low end; ramp_sweep rows at RAMP_S)
    b30 = res['supplies']['bus_30v']
    res['verdict'] = {'supply': 'bus_30v (the robot, near empty)', 'ramp_ring_peak_a': b30['spinup_play']['ring_peak_100ms_a'],
                      'burst_ring_peak_a': b30['burst_play']['ring_peak_a'], 'burst_ring_rms_a': round(b30['burst_play']['ring_per_circuit_rms_1s_a'] / res['ring_worst_share'], 2),
                      'step_ring_peak_a': None, 'never_stepped': 'the firmware always ramps (config.RAMP_S)',
                      'ring_within_2a_at_800ms_10hz': {sup: {lv: res['supplies'][sup]['summary'][lv]['ring_within_2a'] for lv in ('worst', 'play')} for sup in SUPPLIES},
                      'rail_held': {sup: res['supplies'][sup]['summary']['play']['rail_held'] for sup in SUPPLIES},
                      'stand_profile': {k: v for k, v in prof.items() if not k.startswith('at_')},
                      'stand_profile_ok_at_15v': {lv: prof.get(f'at_15v_{lv}', {}).get('ring_ok') for lv in ('play', 'worst', 'worst_j25')}}
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), dpi=130)
    for sup in SUPPLIES:
        tr = res['supplies'][sup]['spinup_play']['trace']
        ax[0].plot(tr['t'], tr['i_in'], label=sup)
        ax[1].plot(tr['t'], np.array(tr['i_ring']) * res['ring_worst_share'], label=sup)
        tb = res['supplies'][sup]['burst_play']['trace']
        ax[2].plot(tb['t'], np.array(tb['i_ring']) * res['ring_worst_share'], label=sup)
    ax[0].axhline(rocker_cap, color='k', ls=':', lw=0.8)
    ax[0].set_title('input current: spin-up, 800 ms ramp, play loads (J4012 48 W)', fontsize=9)
    ax[1].axhline(ring_cap, color='k', ls=':', lw=0.8)
    ax[1].set_title('the ring\'s busiest circuit (3 paralleled): same spin-up', fontsize=9)
    ax[2].axhline(ring_cap, color='k', ls=':', lw=0.8)
    ax[2].set_title('the ring\'s busiest circuit: 8 shots at 10/s, play loads', fontsize=9)
    for a in ax:
        a.set_xlabel('s')
        a.set_ylabel('A')
        a.grid(alpha=0.3)
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / 'power.png')
    plt.close(fig)
    for s in res['supplies'].values():
        for k, v in s.items():
            if isinstance(v, dict) and 'trace' in v and k not in ('spinup_play', 'burst_play'):
                v.pop('trace')
    (OUT / 'power.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    return res


if __name__ == '__main__':
    r = study()
    for sup, s in r['supplies'].items():
        print(sup, json.dumps(s['summary']))
        print('   average', json.dumps(s['average']))
    print('needed', json.dumps(r['needed']))
    print('stand profile', json.dumps(r['stand_profile']))
    print('rocker', json.dumps(r['rocker']))
