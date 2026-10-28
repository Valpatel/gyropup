"""Generate firmware/balance/include/gp/gp_model.h: the balance firmware's model constants and LQR gain table.

    python -m sim.robot_v2                              # build/sim/v2/robot.xml + model.json (git-ignored)
    python firmware/balance/tools/gen_model.py          # -> firmware/balance/include/gp/gp_model.h
    python firmware/balance/tools/gen_model.py --check  # exit 1 if the committed header differs from a fresh one

Where every number comes from:
  - the LQR table: sim/controller.py Controller.lqr() (the wheeled pendulum's parameters read from MuJoCo at the pose,
    the continuous-time Riccati solution) on sim/robot_v2.py's model placed standing (sim/controller_v2.py
    place_standing) at 21 heights from 0 to 1; the firmware interpolates it linearly in the height (the simulation
    recomputes K whenever the height has moved 0.05);
  - the gains: sim/controller.py Gains (LQR weights, yaw, slews) and sim/controller_v2.py LegGains (the robot's virtual
    legs); sim/leg_control.py Gains and sim/leg_rig.py's tuck (the leg rig profile);
  - the centre-of-mass model the firmware estimates the pendulum angle with: the base group (every body but the legs'
    links and the wheels, the turret at rest) and each link's mass and centre in its own frame, from the MJCF;
  - the five-bar (cad/fivebar.py PARAMS), the motors (catalog/leg_actuators.json; the wheel is D69's hub motor from
    sim/wheel_candidates.json hb10, whose Kt, peak torque and speed are SURVEY ESTIMATES until two motors are measured
    (docs/wheel-change-plan.md W1, W6): re-run this after the bench); the 60 N m cap of designs/default.json;
  - the rig profile's feed-forward at the design mass (D69: 17.75 kg a leg, cad/body_layout.py BUDGET), as sim/leg_rig.py
    run() computes it; the wheel is D69's hub motor (sim/robot_v2.py use_d69_wheel()).
Re-run it whenever sim/robot_v2.py's model changes (B3 puts the real body in it) and commit the header.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parent
R = FW.parents[1]
for p in (str(R), str(R / 'cad')):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault('MUJOCO_GL', 'egl')

OUT = FW / 'include' / 'gp' / 'gp_model.h'
BUILD = R / 'build' / 'sim' / 'v2'
DESIGN_HALF_MASS = None           # kg a leg: the ledger's design half mass (cad/body_layout.py BUDGET; D69: 17.75)
N_LQR = 21
LINKS = ('upper_f', 'lower_f', 'upper_r', 'lower_r')


def f(v: float) -> str:
    s = f'{float(v):.9g}'
    if s in ('-0', '0'):
        s = '0'
    if '.' not in s and 'e' not in s:
        s += '.0'
    return s + 'f'


def generate() -> str:
    import mujoco
    import numpy as np
    import fivebar as fb
    from sim.controller import Gains
    from sim.controller_v2 import ControllerV2, LegGains, RobotV2, place_standing
    from sim import leg_rig as lr
    from sim.leg_control import Gains as RigGains
    from sim import robot_v2
    import body_layout as bl
    global DESIGN_HALF_MASS
    robot_v2.use_d69_wheel()                    # D69's hub wheel in sim.leg_rig's state, as the model was built with it
    DESIGN_HALF_MASS = bl.BUDGET['design_half_mass_kg']

    info_path, xml_path = BUILD / 'model.json', BUILD / 'robot.xml'
    if not info_path.exists():
        sys.exit(f'{info_path} is missing: run `python -m sim.robot_v2` first')
    info = json.loads(info_path.read_text())
    model = mujoco.MjModel.from_xml_path(str(xml_path))
    rb = RobotV2(model, info)
    g, lg, rg = Gains(), LegGains(), RigGains()

    # ---- the LQR table
    heights, ks, pend = [], [], []
    for i in range(N_LQR):
        h = i / (N_LQR - 1)
        d = mujoco.MjData(model)
        place_standing(rb, d, h)
        ctl = ControllerV2(rb)
        K, li = ctl.lqr(d)
        heights.append(h)
        ks.append([float(k) for k in K])
        pend.append(li)

    # ---- the centre-of-mass model: links in their frames, everything else lumped as the base (robot frame)
    d0 = mujoco.MjData(model)
    mujoco.mj_forward(model, d0)
    base = model.body('base').id
    leg_ids = {model.body(f'{n}_{s}').id for n in LINKS for s in ('l', 'r')}
    wheel_ids = set(rb.wheels)
    m_base, c_base = 0.0, np.zeros(3)
    Rb = d0.xmat[base].reshape(3, 3)
    for i in rb.bodies:
        if i in leg_ids or i in wheel_ids:
            continue
        m_base += model.body_mass[i]
        c_base += model.body_mass[i] * (Rb.T @ (d0.xipos[i] - d0.xpos[base]))
    c_base /= m_base
    links = []
    for n in LINKS:
        b = model.body(f'{n}_l').id
        links.append((float(model.body_mass[b]), float(model.body_ipos[b][0]), float(model.body_ipos[b][2])))
    m_wheels = float(sum(model.body_mass[w] for w in rb.wheels))
    # check the model against MuJoCo: the pendulum angle it gives must be the simulation's at every placed height
    worst = 0.0
    for h in (0.0, 0.3, 0.6, 1.0):
        d = mujoco.MjData(model)
        place_standing(rb, d, h)
        R_ = d.xmat[base].reshape(3, 3)
        pitch = math.atan2(R_[0, 2], R_[0, 0])                 # rotation about +y (MuJoCo: + = nose down)
        mc = m_base * c_base[[0, 2]]
        M = m_base
        ax = az = 0.0
        for s in ('l', 'r'):
            p1, p2 = rb.phi(d, s)
            j = fb.fk(p1, p2)
            P = {k: np.array(v) / 1000 for k, v in j.items()}
            ang = {'upper_f': p1, 'upper_r': p2, 'lower_f': math.atan2(*(P['E'] - P['C'])[::-1]),
                   'lower_r': math.atan2(*(P['E'] - P['D'])[::-1])}
            org = {'upper_f': P['A'], 'upper_r': P['B'], 'lower_f': P['C'], 'lower_r': P['D']}
            for (mass, lx, lz), n in zip(links, LINKS):
                a = ang[n]
                mc = mc + mass * (org[n] + np.array([lx * math.cos(a) - lz * math.sin(a), lx * math.sin(a) + lz * math.cos(a)]))
                M += mass
            ax += P['E'][0] / 2
            az += P['E'][1] / 2
        c = mc / M
        theta_model = math.atan2(c[0] - ax, c[1] - az) + pitch
        com = np.zeros(3)
        Mb = 0.0
        for i in rb.bodies:
            if i in wheel_ids:
                continue
            com += model.body_mass[i] * d.xipos[i]
            Mb += model.body_mass[i]
        com /= Mb
        axle = (d.xpos[rb.wheels[0]] + d.xpos[rb.wheels[1]]) / 2
        dd = com - axle
        theta_sim = math.atan2(dd[0], dd[2])
        worst = max(worst, abs(theta_model - theta_sim))
    if worst > 2e-3:
        sys.exit(f'the centre-of-mass model disagrees with MuJoCo by {worst:.4f} rad')

    # ---- the rig profile's feed-forward at the design mass (sim/leg_rig.py run())
    mp = lr.mass_props()
    rig_ff = DESIGN_HALF_MASS * lr.G - (mp['rotor'].mass + mp['wheel_link'].mass * 0.5) * lr.G

    la, wm = info['leg_actuator'], info['wheel_motor']
    motor, wheel = lr.MOTOR, lr.WHEEL
    fo, fi, ro, ri = fb.stop_angles()
    hmin, hmax = (v / 1000 for v in info['fivebar']['h_range_mm'])
    total = float(sum(model.body_mass[i] for i in rb.bodies))
    src = hashlib.sha256(info_path.read_bytes() + xml_path.read_bytes()).hexdigest()[:16]
    L = []
    w = L.append
    w('/* GENERATED by firmware/balance/tools/gen_model.py from build/sim/v2 (python -m sim.robot_v2) and the simulation\'s')
    w(' * controllers. Do not edit: re-run the generator when the model or the gains change (docs/body-firmware.md 8). */')
    w('#ifndef GP_MODEL_H')
    w('#define GP_MODEL_H')
    w('')
    w(f'#define GP_MODEL_SOURCE "{info["name"]}, {total:.3f} kg, model+xml sha256 {src}"')
    w(f'#define GP_MODEL_MASS_KG {f(total)}')
    w('')
    w('/* the five-bar (cad/fivebar.py PARAMS), m and rad */')
    w(f'#define GP_FB_D_M {f(fb.P["D"] / 1000)}')
    w(f'#define GP_FB_L1_M {f(fb.P["l1"] / 1000)}')
    w(f'#define GP_FB_L2_M {f(fb.P["l2"] / 1000)}')
    w(f'#define GP_FB_STOP_FRONT_OUT {f(fo)}')
    w(f'#define GP_FB_STOP_FRONT_IN {f(fi)}')
    w(f'#define GP_FB_STOP_REAR_OUT {f(ro)}')
    w(f'#define GP_FB_STOP_REAR_IN {f(ri)}')
    w(f'#define GP_H_MIN_M {f(hmin)} /* the controller\'s height 0 .. 1 (sim/robot_v2.py H_RANGE) */')
    w(f'#define GP_H_MAX_M {f(hmax)}')
    w('')
    w('/* the motors */')
    w(f'#define GP_LEG_PEAK_NM {f(la["peak_nm"])}')
    w(f'#define GP_LEG_CAP_NM {f(la.get("cap_nm") or lr.LEG_CAP)}')
    w(f'#define GP_LEG_W_PER_V {f(motor["no_load_speed_rpm"] / motor["voltage_nominal_v"] * 2 * math.pi / 60)} /* rad/s of no-load speed per volt */')
    w(f'#define GP_WHEEL_R_M {f(info["wheel_r_m"])}')
    w(f'#define GP_WHEEL_PEAK_NM {f(wm["peak_nm"])}')
    w(f'#define GP_WHEEL_W_PER_V {f(wheel["no_load_speed_rpm"] / wheel["voltage_nominal_v"] * 2 * math.pi / 60)}')
    w(f'#define GP_WHEEL_KT_NM_PER_A {f(wheel["kt_nm_per_a"])}')
    w(f'#define GP_WHEEL_POLE_PAIRS {int(wheel["pole_pairs"])}')
    w('')
    w('/* the robot: masses and the legs\' gravity feed-forward ((total - wheels) g / 2, sim/controller_v2.py) */')
    w(f'#define GP_ROBOT_WHEELS_KG {f(m_wheels)}')
    w(f'#define GP_ROBOT_LEG_FF_N {f((total - m_wheels) * 9.81 / 2)}')
    w('')
    w('/* sim/controller.py Gains */')
    w(f'#define GP_G_YAW_KP_PER_NM {f(g.yaw_kp_per_nm)}')
    w(f'#define GP_G_YAW_SHARE {f(g.yaw_share)}')
    w(f'#define GP_G_HEIGHT_RATE {f(g.height_rate)}')
    w(f'#define GP_G_SPEED_MARGIN {f(g.speed_margin)}')
    w(f'#define GP_G_ACCEL {f(g.accel)}')
    w(f'#define GP_G_ROLL_RATE {f(g.roll_rate)}')
    w(f'#define GP_G_ROLL_MAX {f(g.roll_max)}')
    w(f'/* LQR weights q = {tuple(g.q)}, r = {g.r} */')
    w('')
    w('/* sim/controller_v2.py LegGains: the robot\'s virtual legs */')
    w(f'#define GP_LEG_KP_L {f(lg.kp_L)}')
    w(f'#define GP_LEG_KD_L {f(lg.kd_L)}')
    w(f'#define GP_LEG_KP_TH {f(lg.kp_th)}')
    w(f'#define GP_LEG_KD_TH {f(lg.kd_th)}')
    w('')
    w('/* the leg rig profile: sim/leg_control.py Gains, sim/leg_rig.py run()\'s tuck and feed-forward at the design mass */')
    w(f'#define GP_RIG_KP_L {f(rg.kp_L)}')
    w(f'#define GP_RIG_KD_L {f(rg.kd_L)}')
    w(f'#define GP_RIG_KP_TH {f(rg.kp_th)}')
    w(f'#define GP_RIG_KD_TH {f(rg.kd_th)}')
    w(f'#define GP_TUCK_KP_L {f(3000.0)}')
    w(f'#define GP_TUCK_KD_L {f(260.0)}')
    w(f'#define GP_RIG_HALF_MASS_KG {f(DESIGN_HALF_MASS)}')
    w(f'#define GP_RIG_LEG_FF_N {f(rig_ff)}')
    w('')
    w('/* the centre-of-mass model (robot frame: x forward, z up, origin midway between the hip axes) */')
    w(f'#define GP_COM_BASE_KG {f(m_base)}')
    w(f'#define GP_COM_BASE_X {f(c_base[0])}')
    w(f'#define GP_COM_BASE_Z {f(c_base[2])}')
    w(f'/* checked against MuJoCo\'s pendulum angle at four placed heights: worst {worst:.2e} rad */')
    w('')
    w(f'#define GP_LQR_N {N_LQR}')
    w('#ifdef GP_MODEL_TABLES')
    w('/* each leg link: mass (kg) and centre (m) in its frame (x along the link): upper_f, lower_f, upper_r, lower_r */')
    w('static const float gp_com_link[4][3] = {')
    for (m, lx, lz), n in zip(links, LINKS):
        w(f'    {{{f(m)}, {f(lx)}, {f(lz)}}}, /* {n} */')
    w('};')
    w('/* LQR gains K (u = -K [x - x_ref, theta, v - v_cmd, theta_dot], u the two wheels\' torque, N m) by height 0..1;')
    w(' * the pendulum at each: body mass (kg), centre height over the axle (m), inertia (kg m^2) */')
    w('static const float gp_lqr_k[GP_LQR_N][4] = {')
    for h, k, li in zip(heights, ks, pend):
        w(f'    {{{", ".join(f(v) for v in k)}}}, /* h {h:.2f}: {li["mass_body"]:.2f} kg, l {li["com_height"]:.4f} m, '
          f'I {li["inertia_body"]:.4f} */')
    w('};')
    w('#endif')
    w('')
    w('#endif')
    return '\n'.join(L) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    text = generate()
    if a.check:
        same = OUT.exists() and OUT.read_text() == text
        print('gp_model.h is ' + ('current' if same else 'STALE: re-run tools/gen_model.py'))
        return 0 if same else 1
    OUT.write_text(text)
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
