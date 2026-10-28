"""The legs' forces on the body at the robot's design mass: the leg rig (sim/leg_rig.py, the leg workstream's) run at
half the design mass (D71: 37.5 kg, 18.75 kg a leg, with D69's 10 in hub wheel) at the bus voltage given, through its public run() (nothing of
the leg's is written: the bus voltage is set on the imported module, as sim/leg_rig.py's own --bus-v would).

    .venv/bin/python cad/body_legloads.py [--half-mass 16.25] [--bus-v 48.1] [--ledger]   # -> exports/body/leg-loads.json

D62: the body's and the legs' strength loads come from the rig at the design mass, not the ledger (--ledger runs it at
half the ledger's P3 robot instead, for a comparison). The body's strength cases (cad/body_studies.py) read this file.

What reaches the body is less than the axle force: the leg's own 9.3 kg (the hip frame and motors, the links, the wheel)
is decelerated by the ground directly. The rig is planar, so the body's loads are taken from it by d'Alembert on the
leg module, every sample: the vertical force at the hip frame's mount plane, F = Fg - sum m_i (a_i + g), and the roll
moment about the mount plane, M = (y_tyre - y_mount) Fg - sum (y_i - y_mount) m_i (a_i + g), with each body's mass,
centre (y_i from the CAD) and acceleration (mj_objectAcceleration). The rig's own ballast (the body's share, welded to
the carriage) gives the same vertical force (cfrc_int), a check.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
sys.path.insert(0, str(R / 'cad'))
OUT = R / 'exports' / 'body' / 'leg-loads.json'
KEYS = ('peak_motor_nm', 'peak_motor_speed_rad_s', 'peak_wheel_force_n', 'peak_axle_force_n', 'peak_knee_pin_n', 'peak_gearbox_nm',
        'peak_stop_nm', 'jump_height_mm', 'L_range_mm', 'peak_joint_force_n', 'pose_at_peak_axle_force')
RARE = ('jump', 'jump_peak', 'drop_150')          # events the body is designed for at SF >= 2
FAULT = ('power_off',)                            # the undamped power cut (D39's fault case): SF >= 1.2


def half_mass_from_ledger():
    m = json.loads((R / 'exports/body/mass.json').read_text())['P3']['total_kg']
    return round(m / 2, 2)


def design_half_mass():
    import body_layout as bl
    return bl.BUDGET['design_half_mass_kg']


BUS_V = 41.0                                       # D65: the 10S FLEXVOLT pair full (the fastest motors, the hardest jump)


LEG_BODIES = ('carriage', 'upper_f', 'lower_f', 'upper_r', 'lower_r', 'wheel')     # the leg module (not the ballast)


def _probe(lr, fb, log):
    """A wrapper round the rig's sample() that also logs the body-side loads (see the docstring)."""
    import mujoco
    import numpy as np
    orig = lr.sample
    y_mount = fb.Y['centre_plane'] / 1000
    y_tyre = tyre_y_mm() / 1000
    acc = np.zeros(6)

    def sample(m, d, leg, t, state=None):
        r = orig(m, d, leg, t, state)
        fx, fz = lr.wheel_force(m, d, leg)
        Fz, Fx, Mx = fz, fx, (y_tyre - y_mount) * fz
        for name in LEG_BODIES:
            b = m.body(name).id
            mujoco.mj_objectAcceleration(m, d, mujoco.mjtObj.mjOBJ_BODY, b, acc, 0)
            mi = float(m.body_mass[b])
            fzi = -mi * acc[5]                  # MuJoCo's body accelerations carry -gravity (cacc starts at -g): this is m (a + g)
            Fz += fzi
            Fx += -mi * acc[3]
            Mx += (float(d.xipos[b][1]) - y_mount) * fzi
        bal = m.body('ballast').id
        log.append({'t': t, 'Fg': fz, 'F_mount_z': Fz, 'F_mount_x': Fx, 'M_roll_nm': Mx,
                    'ballast_z': float(d.cfrc_int[bal][5]), 'L_mm': r['L_mm'], 'axle': float(np.hypot(r['Ax'], r['Az']))})
        return r
    lr.sample = sample
    return orig


def tyre_y_mm() -> float:
    """The tyre's centre plane in the left module's frame: D69's 10 in tyre (sim/robot_v2.py use_d69_wheel())."""
    from sim import robot_v2
    return robot_v2.use_d69_wheel()['y_mm']


def run(half_mass: float, bus_v: float = BUS_V) -> dict:
    import math
    from sim import leg_rig as lr
    from sim import robot_v2
    robot_v2.use_d69_wheel()                        # D69's 10 in hub wheel in the rig's module state (as sim/wheel_study.py)
    fb = lr.fb
    rig_v = lr.BUS_V
    lr.BUS_V = bus_v                                # the motors' speed line at this bus (LEG_OMEGA is read when run() runs)
    lr.LEG_OMEGA = lr.MOTOR['no_load_speed_rpm'] * bus_v / lr.MOTOR['voltage_nominal_v'] * 2 * math.pi / 60
    out = {'half_mass_kg': half_mass, 'robot_kg': round(2 * half_mass, 2), 'bus_v': bus_v, 'rig_default_bus_v': rig_v,
           'leg_omega_rad_s': round(lr.LEG_OMEGA, 2), 'source': f'sim/leg_rig.py run() at this half mass and {bus_v} V',
           'rig_committed_half_mass_kg': lr.HALF_MASS, 'mount_y_module_mm': fb.Y['centre_plane'], 'tyre_y_module_mm': tyre_y_mm(),
           'scenarios': {}}
    for name, sc in lr.SCENARIOS.items():
        log = []
        orig = _probe(lr, fb, log)
        try:
            r = lr.run(sc, half_mass)
        finally:
            lr.sample = orig
        row = {k: r.get(k) for k in KEYS}
        im = max(range(len(log)), key=lambda i: abs(log[i]['M_roll_nm']))
        iz = max(range(len(log)), key=lambda i: log[i]['F_mount_z'])
        ib = max(range(len(log)), key=lambda i: log[i]['ballast_z'])
        rd = lambda v: round(float(v), 1)
        row['body'] = {'peak_roll_moment_nm': rd(log[im]['M_roll_nm']), 'with_vertical_n': rd(log[im]['F_mount_z']),
                       'with_fore_aft_n': rd(log[im]['F_mount_x']), 'with_ground_n': rd(log[im]['Fg']), 'at_L_mm': rd(log[im]['L_mm']),
                       'at_t_s': round(log[im]['t'], 4), 'peak_vertical_n': rd(log[iz]['F_mount_z']),
                       'peak_vertical_check_ballast_n': rd(log[ib]['ballast_z']),
                       'moment_over_axle_lever': round(log[im]['M_roll_nm'] / max(1e-6, row['peak_axle_force_n'] * (tyre_y_mm() - fb.Y['centre_plane']) / 1000), 3)}
        out['scenarios'][name] = row
    sc = out['scenarios']
    out['rare'] = max((sc[n]['peak_axle_force_n'], n) for n in RARE if n in sc)
    out['fault'] = max((sc[n]['peak_axle_force_n'], n) for n in FAULT if n in sc)
    out['rare_body'] = max((sc[n]['body']['peak_roll_moment_nm'], n) for n in RARE if n in sc)
    out['fault_body'] = max((sc[n]['body']['peak_roll_moment_nm'], n) for n in FAULT if n in sc)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--half-mass', type=float, help='kg a leg carries (default: half the design mass, D69)')
    ap.add_argument('--bus-v', type=float, default=BUS_V)
    ap.add_argument('--ledger', action='store_true', help='half the ledger\'s P3 robot instead of the design mass')
    a = ap.parse_args()
    hm = a.half_mass or (half_mass_from_ledger() if a.ledger else design_half_mass())
    t0 = time.time()
    d = run(hm, a.bus_v)
    d['basis'] = ('half the ledger\'s P3 robot' if a.ledger and not a.half_mass else
                  'given on the command line' if a.half_mass else 'half the design mass (D57, D62)')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, indent=1) + '\n')
    print(f"half mass {hm} kg at {a.bus_v} V: axle rare {d['rare']}, fault {d['fault']}; body roll moment rare {d['rare_body']}, "
          f"fault {d['fault_body']}; jump {d['scenarios'].get('jump', {}).get('jump_height_mm')} mm ({time.time() - t0:.0f} s)")
    for n, r in d['scenarios'].items():
        print(f"  {n:18} axle {r['peak_axle_force_n']:7.1f} N  body: roll {r['body']['peak_roll_moment_nm']:6.1f} N m with {r['body']['with_vertical_n']:7.1f} N "
              f"(x{r['body']['moment_over_axle_lever']} of axle x lever); peak vertical {r['body']['peak_vertical_n']:7.1f} N (ballast {r['body']['peak_vertical_check_ballast_n']:7.1f})")


if __name__ == '__main__':
    main()
