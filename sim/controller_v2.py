"""The balance controller for Gyropup v2 (sim/robot_v2.py): v1's (sim/controller.py) wheeled-pendulum LQR and yaw
control, with the five-bar legs driven by virtual model control instead of hip/knee joint PD.

Each leg is a virtual spring-damper on the line from the hip centre to the wheel axle, in the body's frame: its length
follows the height command (plus the roll-levelling difference between the sides, as v1), its lean the look-up and kick
commands; a gravity feed-forward holds the robot's weight. The force goes to the two motors through the five-bar's
Jacobian, each torque clipped to the RS-04's torque-speed line and the firmware cap. The TPU stops are spring torques
on the motor joints (sim/leg_rig.py's), passive: they act with the motors off too.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import mujoco
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402
from sim.controller import Command, Controller, Gains, clip_torque  # noqa: E402
from sim import leg_rig as lr  # noqa: E402

G = 9.81
SIDES = ('l', 'r')


class RobotV2:
    """Indices and geometry of a model written by sim/robot_v2.py, with the attributes sim/scenarios.py uses."""

    def __init__(self, model: mujoco.MjModel, info: dict):
        self.m, self.info = model, info
        fv = info['fivebar']
        self.ref = fv['ref']
        self.h_min, self.h_max = (v / 1000 for v in fv['h_range_mm'])
        self.r = info['wheel_r_m']
        j = lambda n: model.joint(n)
        names = [f'{k}_{s}' for s in SIDES for k in ('motor_f', 'motor_r', 'knee_f', 'knee_r', 'wheel')]
        self.qadr = {n: j(n).qposadr[0] for n in names}
        self.vadr = {n: j(n).dofadr[0] for n in names}
        self.act = {n: model.actuator(n).id for n in (f'{k}_{s}' for s in SIDES for k in ('motor_f', 'motor_r', 'wheel'))}
        self.base = model.body('base').id
        self.bodies = [i for i in range(1, model.nbody) if model.body_rootid[i] == self.base]
        self.wheels = [model.body('wheel_l').id, model.body('wheel_r').id]
        la, wm = info['leg_actuator'], info['wheel_motor']
        self.leg_peak, self.leg_omega, self.leg_cap = la['peak_nm'], la['omega_max'], la.get('cap_nm')
        self.wheel_peak, self.wheel_omega = wm['peak_nm'], wm['omega_max']
        self.total_mass = float(sum(model.body_mass[i] for i in self.bodies))
        self.wheel_mass = float(sum(model.body_mass[w] for w in self.wheels))
        self.knee_coupled = False
        self.stops = fv['stops_rad']                     # front out, front in, rear out, rear in (rad)

    def peak_for(self, name):
        return self.wheel_peak if name.startswith('wheel') else self.leg_peak

    def rated_for(self, name):
        return self.info['wheel_motor' if name.startswith('wheel') else 'leg_actuator']['rated_nm']

    def height_m(self, frac):
        return self.h_min + (self.h_max - self.h_min) * frac

    def phi(self, data, side):
        return (data.qpos[self.qadr[f'motor_f_{side}']] + self.ref['phi1'], data.qpos[self.qadr[f'motor_r_{side}']] + self.ref['phi2'])

    def leg_state(self, data, side):
        """Virtual leg in the body frame: length (m), lean (rad, + = wheel forward), their rates, d(x,z)/d(phi) (m/rad)."""
        p1, p2 = self.phi(data, side)
        E = fb.fk(p1, p2)['E']
        J = np.array(fb.jacobian(p1, p2)) / 1000.0
        x, z = E[0] / 1000, E[1] / 1000
        dphi = np.array([data.qvel[self.vadr[f'motor_f_{side}']], data.qvel[self.vadr[f'motor_r_{side}']]])
        dx, dz = J @ dphi
        L = math.hypot(x, z)
        return L, math.atan2(x, -z), (x * dx + z * dz) / L, (-z * dx + x * dz) / (L * L), J

    def set_leg(self, data, side, h_m, lean=0.0):
        """Joint angles for a leg length and lean, consistent with the closed loop."""
        phi = fb.stance(h_m * 1000, math.degrees(lean))
        if phi is None:
            return False
        j = fb.fk(*phi)
        ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
        rf = self.ref
        data.qpos[self.qadr[f'motor_f_{side}']] = phi[0] - rf['phi1']
        data.qpos[self.qadr[f'motor_r_{side}']] = phi[1] - rf['phi2']
        data.qpos[self.qadr[f'knee_f_{side}']] = (ang(j['C'], j['E']) - phi[0]) - (rf['af'] - rf['phi1'])
        data.qpos[self.qadr[f'knee_r_{side}']] = (ang(j['D'], j['E']) - phi[1]) - (rf['aw'] - rf['phi2'])
        return True

    def pose_angles(self, frac):                          # for code that asks v1's question
        return 0.0, 0.0


def place_standing(robot: RobotV2, data: mujoco.MjData, frac: float):
    """Both legs at a height, the wheels on the floor, the whole robot tilted about the axle until its centre of mass
    is over it (as v1's place_standing)."""
    m = robot.m
    mujoco.mj_resetData(m, data)
    h = robot.height_m(frac)
    pitch = 0.0
    q = data.qpos
    for _ in range(40):
        q[0:3] = (0, 0, 1.0)
        q[3:7] = (math.cos(pitch / 2), 0, math.sin(pitch / 2), 0)
        for s in SIDES:
            robot.set_leg(data, s, h)
        mujoco.mj_kinematics(m, data)
        mujoco.mj_comPos(m, data)
        com = data.subtree_com[robot.base]
        axle = (data.xpos[robot.wheels[0]] + data.xpos[robot.wheels[1]]) / 2
        dx, dz = com[0] - axle[0], com[2] - axle[2]
        if abs(dx) < 1e-7:
            break
        pitch -= math.atan2(dx, dz) * 0.9
    q[0] -= axle[0]
    q[2] += robot.r - axle[2]
    mujoco.mj_forward(m, data)
    return pitch


@dataclass
class LegGains:
    kp_L: float = 9000.0          # N/m on the virtual leg's length
    kd_L: float = 350.0
    kp_th: float = 450.0          # N m/rad on its lean (relative to the body)
    kd_th: float = 14.0


@dataclass
class ControllerV2(Controller):
    leg: LegGains = field(default_factory=LegGains)

    def control(self, data, cmd: Command, dt: float):
        rb, m = self.robot, self.robot.m
        self.steps += 1
        if self.height is None:
            self.height = cmd.height
        step = self.gains.height_rate * dt
        self.height += max(-step, min(step, cmd.height - self.height))
        Rb = data.xmat[rb.base].reshape(3, 3)
        roll = math.asin(max(-1.0, min(1.0, float(Rb[2, 1]))))
        self.dh = getattr(self, 'dh', 0.0)
        h0 = max(0.0, min(1.0, self.height + cmd.dip))
        lim = min(self.gains.roll_max, h0, 1.0 - h0)
        self.dh = max(-lim, min(lim, self.dh + self.gains.roll_rate * roll * dt))
        self.look = getattr(self, 'look', 0.0)
        dl = 0.5 * dt
        self.look += max(-dl, min(dl, max(-0.1, min(0.35, cmd.look_up)) - self.look))
        if self.K is None or abs(self.height - (self.K_height or 0)) > 0.05:
            self.K, self.lqr_info = self.lqr(data)
            self.K_height = self.height
        # the wheeled pendulum (v1's, unchanged)
        fwd = self.heading(data)
        wheel_set = set(rb.wheels)
        com = np.zeros(3)
        Mb = 0.0
        for i in rb.bodies:
            if i in wheel_set:
                continue
            com += m.body_mass[i] * data.xipos[i]
            Mb += m.body_mass[i]
        com /= Mb
        axle = (data.xpos[rb.wheels[0]] + data.xpos[rb.wheels[1]]) / 2
        d = com - axle
        theta = math.atan2(float(d @ fwd), float(d[2])) + (np.random.normal(0, self.noise) if self.noise else 0.0)
        theta_dot = 0.0 if self.prev_theta is None else (theta - self.prev_theta) / dt
        self.prev_theta = theta
        vel = np.zeros(6)
        mujoco.mj_objectVelocity(m, data, mujoco.mjtObj.mjOBJ_BODY, rb.wheels[0], vel, 0)
        v0 = vel[3:] @ fwd
        mujoco.mj_objectVelocity(m, data, mujoco.mjtObj.mjOBJ_BODY, rb.wheels[1], vel, 0)
        v = 0.5 * (v0 + vel[3:] @ fwd)
        x = float(axle[0] * fwd[0] + axle[1] * fwd[1])
        vmax = self.gains.speed_margin * rb.wheel_omega * rb.r
        target = max(-vmax, min(vmax, cmd.speed))
        self.v_cmd = getattr(self, 'v_cmd', 0.0)
        dv = self.gains.accel * dt
        self.v_cmd += max(-dv, min(dv, target - self.v_cmd))
        self.top_speed = vmax
        self.x_ref += self.v_cmd * dt
        self.x_ref = x + max(-0.3, min(0.3, self.x_ref - x))
        s = np.array([x - self.x_ref, theta, v - self.v_cmd, theta_dot])
        u = float(-self.K @ s)
        mujoco.mj_objectVelocity(m, data, mujoco.mjtObj.mjOBJ_BODY, rb.base, vel, 0)
        yaw_rate = float(vel[2])
        tau_yaw = self.gains.yaw_kp_per_nm * rb.wheel_peak * (cmd.yaw_rate - yaw_rate)
        lim = self.gains.yaw_share * rb.wheel_peak
        tau_yaw = max(-lim, min(lim, tau_yaw))

        # the legs: a virtual spring-damper per side, gravity feed-forward, through the five-bar's Jacobian
        g = self.leg
        ff = (rb.total_mass - rb.wheel_mass) * G / 2
        lean_cmd = -(self.look + cmd.kick)                  # the body leans back on its legs: the wheels move forward
        out = {}
        for side, sgn in (('l', -1.0), ('r', 1.0)):
            L, th, dL, dth, J = rb.leg_state(data, side)
            L_cmd = rb.height_m(h0 + sgn * self.dh)
            F = g.kp_L * (L_cmd - L) - g.kd_L * dL + ff
            T = g.kp_th * (lean_cmd - th) - g.kd_th * dth
            uL = np.array([math.sin(th), -math.cos(th)])
            uth = np.array([math.cos(th), math.sin(th)])
            tau = J.T @ (F * uL + (T / L) * uth)
            out[f'motor_f_{side}'], out[f'motor_r_{side}'] = float(tau[0]), float(tau[1])
        out['wheel_l'] = 0.5 * u - tau_yaw
        out['wheel_r'] = 0.5 * u + tau_yaw
        for name, t in out.items():
            omega = data.actuator_velocity[rb.act[name]]
            if name.startswith('wheel'):
                c = clip_torque(t, omega, rb.wheel_peak, rb.wheel_omega)
            else:
                c = lr.clip_motor(t, omega, rb.leg_peak, rb.leg_omega, rb.leg_cap)
            if abs(c) < abs(t) - 1e-9:
                self.saturation[name] += 1
            out[name] = c
        if self.delay_steps:
            self.buffer.append(out)
            out = self.buffer.pop(0) if len(self.buffer) > self.delay_steps else {n: 0.0 for n in out}
        for name, c in out.items():
            data.ctrl[rb.act[name]] = c
        # the TPU stops: passive springs on the motor joints (they act whether the motors are on or not)
        fo, fi, ro, ri = rb.stops
        for side in SIDES:
            p1, p2 = rb.phi(data, side)
            for jn, ph, lo, hi in ((f'motor_f_{side}', p1, fi, fo), (f'motor_r_{side}', p2, ro, ri)):
                data.qfrc_applied[rb.vadr[jn]] = lr.stop_torque(ph, data.qvel[rb.vadr[jn]], lo, hi)
        return dict(theta=theta, x=x, v=v, u=u, height=self.height, v_cmd=self.v_cmd, roll=roll, level=self.dh)
