"""The turret's own dynamics while it shoots: recoil, the flywheels' gyroscopic loads, the servos, and the aim.

    .venv/bin/python sim/turret_dynamics.py      # writes exports/turret/e2e/dynamics.json

Inputs: the CAD's masses and inertias (cad/turret_motion.py -> exports/turret/motion.json), the launch stage's force
pulse and impulse (sim/turret_launch3d.py), the STS3215 datasheet (references/vendor/feetech-sts3215: 30 kg cm stall,
45 rpm, backlash <= 0.5 deg, 0.088 deg resolution) and the printed gear's backlash (cad/turret.py gear_profile: 0.15 mm
per flank at module 1.25).

What it computes (reduced, analytic models; the e2e MuJoCo scene applies the same recoil to the posed CAD):
  1. Recoil: the ball's momentum at the muzzle per shot and per burst; the force pulse on the cage (peak ~2 m a);
     its moment about the tilt axis (the ball path runs tilt_c = 15 mm under the axis) and about the pan axis (zero by
     symmetry); how far the tilting group turns through the servo's backlash before gravity's preload stops it.
  2. Gyroscopic loads: each tyre's angular momentum I w; a pan slew is about the spin axis (no torque); a tilt at rate
     W gives each motor mount I w W, equal and opposite for the counter-rotating pair, so the pair puts no net torque
     on the cartridge; a single wheel (one ESC faulted) does.
  3. Servo margins with the wheels spinning: cad/turret_motion.py's margins plus the recoil moment and the gyro terms.
  4. The aim movers: how much each effect moves the point of impact at 2, 4 and 6 m.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
sys.path.insert(0, str(R / 'cad'))

OUT = R / 'exports' / 'turret' / 'e2e'
STS3215 = {'stall_nm': 2.94, 'no_load_rad_s': 45 * 2 * math.pi / 60, 'backlash_deg': 0.5, 'resolution_deg': 360 / 4096, 'ratio': 345,
           'source': 'Feetech ST-3215-C018 datasheet (references/vendor/feetech-sts3215/ST-3215-C018.pdf): 30 kg cm, 45 rpm, backlash <= 0.5 deg, 0.088 deg/pulse; checked 2026-10-27'}
GEAR = {'module': 1.25, 'z_ring': 63, 'z_pinion': 21, 'backlash_mm_per_flank': 0.15, 'source': 'cad/turret.py gear_profile(backlash=0.15) and Geo.gear'}


def load_motion():
    p = R / 'exports' / 'turret' / 'motion.json'
    return json.loads(p.read_text()) if p.exists() else None


def recoil(launch_recoil: dict, motion: dict, G):
    """launch_recoil: sim/turret_launch3d.py's 'recoil' block (impulse_ns [x, y, z], peak_force_on_cage_n, contact_ms)."""
    Jx = abs(launch_recoil['impulse_ns'][0])
    Fpk = launch_recoil['peak_force_on_cage_n']
    arm = G.tilt_c / 1000                                    # the ball path is tilt_c under the tilt axis
    tilt = motion['tilt']
    I_t = tilt['margins']['inertia_kg_m2']
    tau_g = max(abs(r['gravity_torque_nm']) for r in tilt['rows'])     # the CoM behind the axis: nose-up preload
    dw = Jx * arm / I_t                                      # the angular speed the recoil gives the tilting group (nose down)
    alpha_g = tau_g / I_t
    theta_stop = dw ** 2 / (2 * alpha_g)                     # where gravity's preload stops it, if inside the backlash
    backlash = math.radians(STS3215['backlash_deg'])
    kick = min(theta_stop, backlash)
    return {'impulse_per_shot_ns': round(Jx, 5), 'impulse_5_burst_ns': round(5 * Jx, 4), 'impulse_30_hopper_ns': round(30 * Jx, 3),
            'peak_force_on_cage_n': round(Fpk, 1), 'pulse_ms': round(launch_recoil['contact_ms'], 2),
            'peak_moment_about_tilt_axis_nm': round(Fpk * arm, 3), 'moment_arm_mm': G.tilt_c,
            'tilt_angular_impulse_nms': round(Jx * arm, 7), 'tilt_group_inertia_kg_m2': I_t, 'tilt_kick_rad_s': round(dw, 4),
            'gravity_preload_nm': round(tau_g, 4), 'kick_stops_after_mrad': round(theta_stop * 1000, 3), 'servo_backlash_mrad': round(backlash * 1000, 2),
            'aim_shift_mrad': round(kick * 1000, 3), 'crosses_backlash': theta_stop >= backlash,
            'pan_moment': 'zero: the ball path lies in the pan axis\'s plane (y = 0) and both tyres push alike',
            'mean_force_in_burst_n': {f'{r}_per_s': round(Jx * r, 4) for r in (3, 5, 10)},
            'on_the_robot': 'a 30-ball hopper dump is 0.9 N s: 0.05 m/s on a 17 kg robot (docs/head-payload.md budget 0.05 N s per shot)'}


def gyro(launch: dict, motion: dict, L_wheel_I, w_rad_s):
    L = L_wheel_I * w_rad_s
    tilt_w = math.radians(200)                               # cad/turret_motion.py: the 25 deg tilt in 0.25 s peaks at 200 deg/s
    pan_w = math.radians(90)
    body_pitch_w = 1.0                                       # est: a balancing robot catching a shove, rad/s
    return {'wheel_angular_momentum_nms': round(L, 6), 'wheel_I_kg_m2': L_wheel_I, 'w_rad_s': round(w_rad_s),
            'pan_slew_torque_nm': 0.0, 'pan_note': 'the spin axes are parallel to the pan axis: no gyroscopic torque',
            'tilt_at_200deg_s_per_wheel_nm': round(L * tilt_w, 5), 'tilt_pair_net_nm': 0.0,
            'body_pitch_1rad_s_per_wheel_nm': round(L * body_pitch_w, 5), 'pair_note': 'the two tyres counter-rotate: equal and opposite on the cartridge, net zero; each Snail mount sees the per-wheel value',
            'one_wheel_faulted_tilt_nm': round(L * tilt_w, 5), 'vs_tilt_servo_stall': round(L * tilt_w / STS3215['stall_nm'], 6)}


def servo_margins(motion: dict, rec: dict, gy: dict):
    t = motion['tilt']['margins']
    p = motion['pan']['margins']
    # sustained loads: the move (inertia + gravity), the mean recoil moment in a 10/s burst, one wheel's gyro torque;
    # the 5 ms recoil pulse is not a servo load: the tilting group's inertia takes it (the kick in recoil())
    mean_recoil = rec['tilt_angular_impulse_nms'] * 10.0
    tilt_need = t['move_torque_nm'] + mean_recoil + gy['one_wheel_faulted_tilt_nm']
    return {'tilt': {'move_torque_nm': t['move_torque_nm'], 'plus_mean_recoil_at_10_per_s_nm': round(mean_recoil, 4), 'plus_gyro_one_wheel_nm': gy['one_wheel_faulted_tilt_nm'],
                     'sustained_total_nm': round(tilt_need, 3), 'available_at_peak_speed_nm': t['available_at_peak_speed_nm'], 'margin': round(t['available_at_peak_speed_nm'] / tilt_need, 1),
                     'recoil_pulse_nm_5ms': rec['peak_moment_about_tilt_axis_nm'], 'pulse_vs_stall': round(rec['peak_moment_about_tilt_axis_nm'] / STS3215['stall_nm'], 2),
                     'pulse_note': 'the pulse exceeds nothing the servo must hold continuously; it turns the tilting group 1-2 mrad against gravity\'s preload inside the gear lash (recoil.aim_shift_mrad)',
                     'hold_margin_at_stall': round(STS3215['stall_nm'] / (t['gravity_torque_max_nm'] + mean_recoil), 1)},
            'pan': {'move_torque_at_servo_nm': p['move_torque_at_servo_nm'], 'speed_limit_deg_s_at_turret': p['max_speed_deg_s_at_turret'], 'fastest_90_deg_s': p['fastest_90_deg_s'],
                    'note': 'speed-limited, not torque-limited: 45 rpm through 3:1 is 90 deg/s at the turret, so the 90 deg in 1.2 s move (150 deg/s peak) is not reachable; recoil adds no pan moment',
                    'yaw_margin_against_body': p['yaw_margin']},
            'source': motion['servo']['source']}


def aim_movers(G, rec, flight_slew, v_ball_m_s=16.76):
    """How far each effect moves the point of impact (cm) at 2, 4, 6 m."""
    r_ring = GEAR['module'] * GEAR['z_ring'] / 2
    pan_gear_backlash = 2 * GEAR['backlash_mm_per_flank'] / r_ring                 # both flanks thinned: the full lash in rad at the turret
    pan_servo_backlash = math.radians(STS3215['backlash_deg']) / (GEAR['z_ring'] / GEAR['z_pinion'])
    tilt_backlash = math.radians(STS3215['backlash_deg'])
    res_pan = math.radians(STS3215['resolution_deg']) / (GEAR['z_ring'] / GEAR['z_pinion'])
    res_tilt = math.radians(STS3215['resolution_deg'])
    rows = {
        'recoil_tilt_kick': {'mrad': rec['aim_shift_mrad'], 'direction': 'down', 'note': 'stopped by the gravity preload inside the backlash'},
        'pan_gear_backlash_total': {'mrad': round(pan_gear_backlash * 1000, 2), 'direction': 'either', 'note': '0.15 mm per flank on the 63 T ring: the lash the pan can sit anywhere in when the load reverses'},
        'pan_servo_backlash_through_3_1': {'mrad': round(pan_servo_backlash * 1000, 2), 'direction': 'either', 'note': 'STS3215 <= 0.5 deg, divided by the 3:1'},
        'tilt_servo_backlash': {'mrad': round(tilt_backlash * 1000, 2), 'direction': 'either', 'note': 'direct drive: the full 0.5 deg; gravity preloads it nose-up, recoil pushes nose-down'},
        'pan_resolution': {'mrad': round(res_pan * 1000, 3), 'direction': 'either', 'note': '0.088 deg per count through 3:1'},
        'tilt_resolution': {'mrad': round(res_tilt * 1000, 3), 'direction': 'either'},
    }
    for k, v in flight_slew.items():
        rows[f'pan_slew_{k}'] = {'mrad': round(math.radians(v['deflection_deg']) * 1000, 2), 'direction': 'against the slew', 'note': 'the muzzle\'s own sideways velocity (155 mm from the pan axis) adds to the ball\'s'}
    for v in rows.values():
        v['cm_at'] = {f'{d}_m': round(v['mrad'] / 1000 * d * 100, 2) for d in (2, 4, 6)}
    return rows


def study(launch3d=None, flight=None):
    import turret_common as tc
    tu = tc.cad_turret()
    OUT.mkdir(parents=True, exist_ok=True)
    G = tu.Geo()
    motion = load_motion()
    if motion is None:
        raise SystemExit('run cad/turret_motion.py first (exports/turret/motion.json)')
    l3 = launch3d or json.loads((R / 'exports' / 'turret' / 'launch' / 'launch3d.json').read_text())
    fl = flight or json.loads((R / 'exports' / 'turret' / 'flight' / 'flight.json').read_text())
    rec = recoil(l3['recoil'], motion, G)
    import turret_launch as tl
    L = tl.launcher_for(l3['design']['wheel_d_mm'], l3['design']['crush'])
    gy = gyro(l3, motion, L.wheel_I, l3['design']['set_rpm'] * 2 * math.pi / 60)
    sm = servo_margins(motion, rec, gy)
    am = aim_movers(G, rec, fl['pan_slew_deflection'])
    res = {'sts3215': STS3215, 'gear': GEAR, 'recoil': rec, 'gyroscopic': gy, 'servo_margins': sm, 'aim_movers': am,
           'checks': {'recoil_within_budget_0_05ns': rec['impulse_per_shot_ns'] <= 0.05, 'tilt_servo_margin_ok': sm['tilt']['margin'] >= 2.0,
                      'pan_reaches_90deg_in_1_2s': sm['pan']['fastest_90_deg_s'] <= 1.2, 'recoil_kick_inside_backlash': not rec['crosses_backlash'],
                      'recoil_kick_under_3mrad': rec['aim_shift_mrad'] <= 3.0}}
    (OUT / 'dynamics.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    return res


if __name__ == '__main__':
    r = study()
    print(json.dumps({k: r[k] for k in ('recoil', 'gyroscopic', 'servo_margins', 'aim_movers', 'checks')}, indent=1))
