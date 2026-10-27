"""Pan and tilt servo margins for the turret, from the CAD's masses and inertias.

    .venv/bin/python cad/turret_motion.py

Every part of cad/turret.py becomes a rigid body (cadagent.robot: printed parts by their print fill, bought parts with
their catalogue mass spread over their envelope, the 30 balls in the hopper, the not-modelled 127 g at the turntable).
From those:
  - the tilting group's inertia about the tilt axis and its gravity torque over 0..-25 deg, empty and full;
  - the panning group's inertia about the pan axis (at tilt 0 and -25), seen by the pan servo through 63:21;
  - the torque each STS3215 needs for the moves the game asks for (a 90 deg pan in 1.2 s, a 25 deg tilt in 0.25 s,
    world-frame aiming against the body's pitch and yaw while balancing and turning) against what the servo gives
    at that speed, and how fast each axis can go at all;
  - the printed gear: Lewis bending stress on the 21 T pinion and the 63 T ring at the servo's stall torque and at
    the firmware cap, against PA6-CF's humid allowables (cadagent.fea MATERIALS).
The STS3215 (Feetech, 12 V): 30 kg cm = 2.94 N m stall, 45 rpm no load (catalog feetech-sts3215-c018-12v), taken as
a straight torque-speed line. Its own rotor inertia through its ~345:1 gearbox is not published; it is left out
(it sets how quickly the servo reaches speed, which the bench measures, not how much torque the load takes).
Writes exports/turret/motion.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402
from cadagent.fea import MATERIALS  # noqa: E402
from cadagent.robot import Body, combine, printed_part_body, solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'turret'
SERVO = {'stall_nm': 2.94, 'no_load_rad_s': 45 * 2 * math.pi / 60, 'source': 'catalog feetech-sts3215-c018-12v (Waveshare ST3215: 30 kg.cm, 45 rpm at 12 V)'}
GEAR = {'ratio': 63 / 21, 'efficiency': 0.90, 'note': 'printed spur pair, dry PA6-CF on PA6-CF: 0.90 assumed'}
BRG_FRICTION_NM = 0.02          # the 6810-2Z (shielded, light load) plus the harness loop through the centre: est
G = 9.81
# what the game asks of the axes (S15: pan at most 100 deg/s near people; the hardware cannot exceed 90 deg/s anyway)
MOVES = {'pan_90': {'deg': 90.0, 's': 1.2}, 'tilt_25': {'deg': 25.0, 's': 0.25}}
BODY = {'pitch_acc_rad_s2': 30.0, 'yaw_acc_rad_s2': 15.0,
        'note': 'est for a balancing robot: catching a shove pitches the body at up to ~30 rad/s^2; a hard turn yaws it at ~15 rad/s^2'}


def bodies(T, tilt=0.0, balls=30):
    """{name: Body} for every part at (pan 0, tilt) in the T frame (SI)."""
    dens = tu.DENS
    out = {}
    for name, m in T.meta.items():
        s = T.pose_shape(T.local[name], T.frame[name], 0.0, tilt, robot=False).val()
        b, _ = printed_part_body(s, dens[m['material']], wall_mm=500.0 if m['solid'] else 2.0, infill=1.0 if m['solid'] else 0.4, name=name)
        out[name] = b
        if m['qty'] == 2:
            s2 = T.pose_shape(T.local[name].mirror('XZ'), T.frame[name], 0.0, tilt, robot=False).val()
            out[name + '_2'] = printed_part_body(s2, dens[m['material']], wall_mm=500.0 if m['solid'] else 2.0, infill=1.0 if m['solid'] else 0.4, name=name)[0]
    for name, (shape, frame, mass, _) in T.bought.items():
        if mass <= 0:
            continue
        s = T.pose_shape(shape, frame, 0.0, tilt, robot=False).val()
        out[name] = solid_mass_properties(s, mass / (s.Volume() / 1000.0), 1.0, name)
    if balls:
        Gg = T.G
        # the balls: 7 in the pockets (the exit pocket is empty when parked), the rest in the hopper above the dial
        pts = [(Gg.rp * math.cos(math.radians(45 * k)), Gg.rp * math.sin(math.radians(45 * k)), Gg.ball_z_dial) for k in range(1, 8)]
        rest = max(0, balls - 7)
        hz = Gg.dial_z0 + Gg.dial_h + Gg.ball / 2 + 2
        for k in range(rest):
            ring, j = divmod(k, 8)
            r = (Gg.dial_wall_r - Gg.ball / 2 - 1) * (0.35 if ring % 2 else 0.8)
            a = 2 * math.pi * j / 8 + 0.4 * ring
            pts.append((r * math.cos(a), r * math.sin(a), hz + Gg.ball * 0.85 * ring))
        mb = 0.00183
        bl = []
        for p in pts[:balls]:
            q = T.point(p, 'tilt', 0.0, tilt, robot=False)
            Ib = 0.4 * mb * (Gg.ball / 2000) ** 2
            bl.append(Body(mb, tuple(c / 1000 for c in q), ((Ib, 0, 0), (0, Ib, 0), (0, 0, Ib)), 'ball'))
        out['balls'] = combine(bl, 'balls')
    nm = sum(tu.NOT_MODELLED_G.values()) / 1000
    out['not_modelled'] = Body(nm, (0.0, 0.0, T.G.turntable_z[1] / 1000), ((0, 0, 0), (0, 0, 0), (0, 0, 0)), 'not modelled')
    return out


def group(T, B, frames):
    names = [n for n in B if (n.removesuffix('_2') in T.frame and T.frame[n.removesuffix('_2')] in frames)
             or (n == 'balls' and 'tilt' in frames) or (n == 'not_modelled' and 'pan' in frames)]
    return combine([B[n] for n in names], '+'.join(sorted(frames)))


def lewis(m_mm, z, face_mm, torque_nm, pitch_r_mm=None):
    """Lewis bending stress at the tooth root (MPa) for a 20 deg full-depth spur tooth, load at the tip (the
    conservative single-tooth case for printed gears): sigma = Ft / (b m Y)."""
    Y = {12: 0.245, 14: 0.277, 17: 0.303, 21: 0.328, 26: 0.346, 35: 0.373, 50: 0.409, 63: 0.425, 100: 0.446}
    ks = sorted(Y)
    y = np.interp(z, ks, [Y[k] for k in ks])
    r = pitch_r_mm or m_mm * z / 2
    Ft = torque_nm / (r / 1000)
    return Ft / (face_mm * m_mm * y), Ft, float(y)


def main():
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
    Gg = T.G
    tilt_axis = (0.0, 0.0, Gg.tilt_t / 1000)
    res = {'servo': SERVO, 'gear': GEAR, 'body': BODY, 'moves': MOVES}
    # ---- tilt
    tilt_rows = []
    for balls in (0, 30):
        for tilt in (0.0, -12.5, -25.0):
            B = bodies(T, tilt, balls)
            tg = group(T, B, {'tilt'})
            I = tg.inertia_about(tilt_axis)
            r = [tg.com[i] - tilt_axis[i] for i in range(3)]
            tau_g = tg.mass * G * r[0]                     # + = nose down (the CoM ahead of the axis pulls it down)
            tilt_rows.append({'balls': balls, 'tilt_deg': tilt, 'mass_g': round(tg.mass * 1000, 1), 'com_from_axis_mm': [round(c * 1000, 1) for c in r],
                              'I_yy_kg_m2': round(I[1][1], 6), 'gravity_torque_nm': round(tau_g, 4)})
    res['tilt'] = {'rows': tilt_rows}
    I_t = max(r['I_yy_kg_m2'] for r in tilt_rows)
    g_t = max(abs(r['gravity_torque_nm']) for r in tilt_rows)
    a, tmove = math.radians(MOVES['tilt_25']['deg']), MOVES['tilt_25']['s']
    # a triangular speed profile: half accelerating, half braking; peak speed 2a/t, acceleration 4a/t^2
    w_pk, acc = 2 * a / tmove, 4 * a / tmove ** 2
    need = I_t * acc + g_t
    avail = SERVO['stall_nm'] * (1 - w_pk / SERVO['no_load_rad_s'])
    stab = I_t * BODY['pitch_acc_rad_s2'] + g_t
    res['tilt']['margins'] = {
        'inertia_kg_m2': I_t, 'gravity_torque_max_nm': g_t,
        'move': f"{MOVES['tilt_25']['deg']:.0f} deg in {tmove} s: peak {math.degrees(w_pk):.0f} deg/s, {acc:.0f} rad/s^2",
        'move_torque_nm': round(need, 3), 'available_at_peak_speed_nm': round(avail, 3), 'move_margin': round(avail / need, 1),
        'hold_margin': round(SERVO['stall_nm'] / max(g_t, 1e-6), 1),
        'world_frame_against_body_pitch_nm': round(stab, 3), 'world_frame_margin': round(SERVO['stall_nm'] / stab, 1),
        'max_speed_deg_s': round(math.degrees(SERVO['no_load_rad_s'])),
    }
    # ---- pan
    pan_rows = []
    for tilt in (0.0, -25.0):
        B = bodies(T, tilt, 30)
        pg = group(T, B, {'pan', 'tilt'})
        Iz = pg.inertia_about((0.0, 0.0, 0.0))[2][2]
        pan_rows.append({'tilt_deg': tilt, 'mass_g': round(pg.mass * 1000, 1), 'I_zz_kg_m2': round(Iz, 6)})
    pin = bodies(T, 0.0, 0)['pan_pinion']
    sx, sy = Gg.servo_pan_xy
    I_pin = pin.inertia_about((sx / 1000, sy / 1000, 0.0))[2][2]
    I_p = max(r['I_zz_kg_m2'] for r in pan_rows)
    n, eta = GEAR['ratio'], GEAR['efficiency']
    I_servo = I_p / n ** 2 + I_pin                        # seen at the servo output
    a, tmove = math.radians(MOVES['pan_90']['deg']), MOVES['pan_90']['s']
    w_pk, acc = 2 * a / tmove, 4 * a / tmove ** 2      # at the turret
    need = (I_p * acc + BRG_FRICTION_NM) / (n * eta) + I_pin * acc * n
    avail = SERVO['stall_nm'] * (1 - w_pk * n / SERVO['no_load_rad_s'])
    yaw = (I_p * BODY['yaw_acc_rad_s2'] + BRG_FRICTION_NM) / (n * eta)
    res['pan'] = {'rows': pan_rows, 'pinion_I_kg_m2': I_pin, 'margins': {
        'inertia_at_turret_kg_m2': I_p, 'inertia_at_servo_kg_m2': round(I_servo, 7),
        'move': f"{MOVES['pan_90']['deg']:.0f} deg in {tmove} s: peak {math.degrees(w_pk):.0f} deg/s at the turret ({math.degrees(w_pk * n):.0f} at the servo), {acc:.1f} rad/s^2",
        'move_torque_at_servo_nm': round(need, 4), 'available_at_peak_speed_nm': round(avail, 3), 'move_margin': round(avail / need, 1) if avail > 0 else 0.0,
        'against_body_yaw_nm': round(yaw, 4), 'yaw_margin': round(SERVO['stall_nm'] / yaw, 1),
        'max_speed_deg_s_at_turret': round(math.degrees(SERVO['no_load_rad_s'] / n), 1),
        'fastest_90_deg_s': round(fastest(a, I_servo * n ** 2, SERVO['stall_nm'] * n * eta, SERVO['no_load_rad_s'] / n, BRG_FRICTION_NM), 2),
    }}
    # ---- gears (Lewis, tip load) at the servo's stall and at a 50 % firmware cap
    mm, face = Gg.gear['m'], 12.0
    rows = []
    for label, tq in (('stall 2.94 N m', SERVO['stall_nm']), ('cap 50 %', 0.5 * SERVO['stall_nm'])):
        s_p, Ft, y = lewis(mm, Gg.gear['z_pinion'], face, tq)
        s_r, _, y2 = lewis(mm, Gg.gear['z_ring'], 16.0, tq * n)
        rows.append({'case': label, 'tooth_force_n': round(Ft, 1), 'pinion_mpa': round(s_p, 1), 'ring_mpa': round(s_r, 1),
                     'pinion_sf_xy': round(MATERIALS['pa6_cf_xy'].strength_mpa / s_p, 2), 'ring_sf_xy': round(MATERIALS['pa6_cf_xy'].strength_mpa / s_r, 2)})
    res['gears'] = {'module': mm, 'teeth': [Gg.gear['z_pinion'], Gg.gear['z_ring']], 'face_mm': [face, 16.0], 'rows': rows,
                    'allowable': f"PA6-CF along the layers, humid: {MATERIALS['pa6_cf_xy'].strength_mpa} MPa (teeth printed flat: the root bending runs in the layers)",
                    'method': 'Lewis, load at the tooth tip on one tooth (conservative), Y for 20 deg full depth'}
    (OUT / 'motion.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k in ('tilt', 'pan', 'gears')}, indent=1))


def fastest(angle, I, tau_stall, w0, friction):
    """Shortest time to turn `angle` from rest to rest with a straight torque-speed line (stall tau_stall, no-load w0,
    at the axis) against inertia I and a constant friction torque: full torque up, full torque down (simulated)."""
    dt = 1e-4
    th = w = t = 0.0
    while True:
        # brake when the stopping distance at full reverse torque reaches what is left
        tau_brake = tau_stall + friction                  # reversing a servo gives at least its stall torque
        if w > 0 and th + w * w / (2 * tau_brake / I) >= angle:
            break
        tau = tau_stall * (1 - w / w0) - friction
        w += tau / I * dt
        th += w * dt
        t += dt
        if t > 10:
            break
    return t + w / (tau_brake / I)


if __name__ == '__main__':
    main()
