"""Baseline balance controller, tuned per design from the design's own model.

Same structure as Upkie's and the Diablo-class LQR balancers:

- **Legs:** joint PD to the pose that puts each wheel under the hip at the commanded height, plus a gravity feedforward
  from the model (generalised gravity minus the ground reaction through the wheel Jacobian). With stiff legs the robot
  is one pendulum on two wheels.
- **Balance:** a linearised wheeled-inverted-pendulum LQR. Its parameters (masses, centre-of-mass height, inertias,
  wheel inertia) are read from the MuJoCo model at the current pose and the gains are recomputed as the height
  changes, so each design gets a controller made for it.
- **Turning:** differential wheel torque on yaw rate.
- **Actuators:** each torque is clipped to the motor's torque–speed line (full torque at standstill, none at the
  no-load speed for this battery voltage) and to its peak, like mjlab's and Isaac Lab's DCMotor.

State comes from the simulator (exact); noise and delay are options, so robustness can be tested too.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import mujoco
import numpy as np
from scipy.linalg import solve_continuous_are

G = 9.81


def knee_for(a, b, h):
    return math.acos(max(-1.0, min(1.0, (a * a + b * b - h * h) / (2 * a * b))))


def hip_for(a, b, h):
    return math.acos(max(-1.0, min(1.0, (a * a + h * h - b * b) / (2 * a * h))))


@dataclass
class Command:
    height: float = 0.6        # 0 = deepest crouch, 1 = full stand
    speed: float = 0.0         # m/s forward
    yaw_rate: float = 0.0      # rad/s, positive = turn left
    look_up: float = 0.0       # rad: lean the body back (nose up) on the legs to look up; balance keeps the CoM over the wheels
    dip: float = 0.0           # instant height offset (fraction), not slewed: quick expressive moves such as a shot flinch
    kick: float = 0.0          # rad, instant lean back on the legs, not slewed (the flinch's rock back)


@dataclass
class Gains:
    leg_kp_per_nm: float = 2.5     # kp = this × peak torque (N m/rad)
    leg_kd_per_nm: float = 0.06
    q: tuple = (40.0, 600.0, 30.0, 20.0)   # LQR weights: position, pitch, speed, pitch rate
    r: float = 2.0
    yaw_kp_per_nm: float = 0.25    # yaw gain = this × wheel peak torque (N m per rad/s)
    yaw_share: float = 0.3          # turning may use at most this share of a wheel's peak torque
    height_rate: float = 0.6       # height command slew, fraction of range per second
    speed_margin: float = 0.5      # top speed = this × wheel no-load speed, keeping half the torque in reserve for balance
    accel: float = 1.5             # m/s², commanded speed slew
    roll_rate: float = 4.0         # body levelling: leg-height difference grows at this × roll (fraction of range per s per rad)
    roll_max: float = 0.45         # the most one leg may be shorter than the other, fraction of the height range


class Robot:
    """Indices and geometry of a model written by sim.model."""

    def __init__(self, model: mujoco.MjModel, info: dict):
        self.m, self.info = model, info
        L = info['layout_mm']
        self.a, self.b, self.r = L['thigh'] / 1000, L['shin'] / 1000, L['wheelR'] / 1000
        lo = math.radians(L['kneeMinDeg']); hi = math.radians(L['kneeMaxDeg'])
        self.h_min, self.h_max = [math.sqrt(self.a ** 2 + self.b ** 2 - 2 * self.a * self.b * math.cos(g)) for g in (lo, hi)]
        j = lambda n: model.joint(n)
        self.qadr = {n: j(n).qposadr[0] for n in ('hip_l', 'knee_l', 'wheel_l', 'hip_r', 'knee_r', 'wheel_r')}
        self.vadr = {n: j(n).dofadr[0] for n in self.qadr}
        self.act = {n: model.actuator(n).id for n in self.qadr}
        self.base = model.body('base').id
        self.bodies = [i for i in range(1, model.nbody) if model.body_rootid[i] == self.base]   # the robot only, not darts or props
        self.wheels = [model.body('wheel_l').id, model.body('wheel_r').id]
        self.leg_peak = info['leg_actuator']['peak_nm']
        self.leg_omega = info['leg_actuator']['omega_max']
        self.wheel_peak = info['wheel_motor']['peak_nm']
        self.wheel_omega = info['wheel_motor']['omega_max']
        self.total_mass = float(sum(model.body_mass[i] for i in self.bodies))
        self.knee_coupled = int(model.actuator_trntype[self.act['knee_l']]) == int(mujoco.mjtTrn.mjTRN_TENDON)

    def peak_for(self, name):
        return self.wheel_peak if name.startswith('wheel') else self.leg_peak

    def rated_for(self, name):
        return self.info['wheel_motor' if name.startswith('wheel') else 'leg_actuator']['rated_nm']

    def height_m(self, frac):
        return self.h_min + (self.h_max - self.h_min) * frac

    def pose_angles(self, frac):
        h = self.height_m(frac)
        return hip_for(self.a, self.b, h), knee_for(self.a, self.b, h) - math.pi


def clip_torque(tau, omega, peak, omega_max):
    """Four-quadrant DC motor line: motoring torque falls to zero at the no-load speed; braking may use full peak."""
    if tau * omega > 0:
        limit = peak * max(0.0, 1.0 - abs(omega) / omega_max)
    else:
        limit = peak
    return max(-limit, min(limit, tau))


def place_standing(robot: Robot, data: mujoco.MjData, frac: float):
    """Put the robot on the floor at a height with its legs at the controller's own pose, and tilt the whole robot
    about the axle until the centre of mass is over it, so the run starts in balance with no transient."""
    m = robot.m
    mujoco.mj_resetData(m, data)
    hip, knee = robot.pose_angles(frac)
    pitch = 0.0
    q = data.qpos
    for _ in range(40):
        q[0:3] = (0, 0, 1.0)
        q[3:7] = (math.cos(pitch / 2), 0, math.sin(pitch / 2), 0)
        for side in ('l', 'r'):
            q[robot.qadr[f'hip_{side}']] = hip
            q[robot.qadr[f'knee_{side}']] = knee
        mujoco.mj_kinematics(m, data)
        mujoco.mj_comPos(m, data)
        com = data.subtree_com[robot.base]
        axle = (data.xpos[robot.wheels[0]] + data.xpos[robot.wheels[1]]) / 2
        dx, dz = com[0] - axle[0], com[2] - axle[2]
        if abs(dx) < 1e-7:
            break
        pitch -= math.atan2(dx, dz) * 0.9           # rotate the whole robot about the axle
    q[0] -= axle[0]
    q[2] += robot.r - axle[2]                        # wheels on the floor, axle over x = 0
    mujoco.mj_forward(m, data)
    return pitch


@dataclass
class Controller:
    robot: Robot
    gains: Gains = field(default_factory=Gains)
    noise: float = 0.0               # pitch noise std, rad
    delay_steps: int = 0

    def __post_init__(self):
        self.height = None
        self.x_ref = 0.0
        self.K = None
        self.K_height = None
        self.prev_theta = None
        self.buffer = []
        self.saturation = {n: 0 for n in self.robot.act}
        self.steps = 0

    # --- the linear model of the robot as a wheeled pendulum, from MuJoCo at the current pose
    def pendulum_params(self, data):
        m = self.robot.m
        wheel_set = set(self.robot.wheels)
        Mb, com = 0.0, np.zeros(3)
        for i in self.robot.bodies:
            if i in wheel_set:
                continue
            Mb += m.body_mass[i]
            com += m.body_mass[i] * data.xipos[i]
        com /= Mb
        axle = (data.xpos[self.robot.wheels[0]] + data.xpos[self.robot.wheels[1]]) / 2
        l = float(np.linalg.norm((com - axle)[[0, 2]]))
        Ib = 0.0
        for i in self.robot.bodies:
            if i in wheel_set:
                continue
            R = data.ximat[i].reshape(3, 3)
            I = R @ np.diag(m.body_inertia[i]) @ R.T
            d = data.xipos[i] - com
            Ib += I[1, 1] + m.body_mass[i] * (d[0] ** 2 + d[2] ** 2)
        mw = sum(m.body_mass[w] for w in self.robot.wheels)
        Iw = sum(m.body_inertia[w][1] for w in self.robot.wheels) + sum(m.dof_armature[self.robot.vadr[n]] for n in ('wheel_l', 'wheel_r'))
        return Mb, l, Ib, mw, Iw

    def lqr(self, data):
        Mb, l, Ib, mw, Iw = self.pendulum_params(data)
        r = self.robot.r
        A2 = np.array([[Mb + mw + Iw / r ** 2, Mb * l], [Mb * l, Ib + Mb * l ** 2]])
        Ainv = np.linalg.inv(A2)
        # [xdd, thdd] = Ainv @ ([u/r, -u] + [0, Mb g l th])
        A = np.zeros((4, 4)); B = np.zeros((4, 1))
        A[0, 2] = A[1, 3] = 1.0
        A[2:, 1] = Ainv @ np.array([0.0, Mb * G * l])
        B[2:, 0] = Ainv @ np.array([1 / r, -1.0])
        Q = np.diag(self.gains.q); Rm = np.array([[self.gains.r]])
        P = solve_continuous_are(A, B, Q, Rm)
        return (np.linalg.inv(Rm) @ B.T @ P).ravel(), dict(mass_body=Mb, com_height=l, inertia_body=Ib)

    def heading(self, data):
        R = data.xmat[self.robot.base].reshape(3, 3)
        fwd = R[:, 0].copy(); fwd[2] = 0
        n = np.linalg.norm(fwd)
        return fwd / n if n > 1e-6 else np.array([1.0, 0, 0])

    def control(self, data, cmd: Command, dt: float):
        rb, m = self.robot, self.robot.m
        self.steps += 1
        # height slew
        if self.height is None:
            self.height = cmd.height
        step = self.gains.height_rate * dt
        self.height += max(-step, min(step, cmd.height - self.height))
        # body levelling (no hip ab/adduction): on a side slope or with one wheel on a kerb, shorten the leg on the
        # high side and lengthen the other until the body is level; roll > 0 = the left side up
        Rb = data.xmat[rb.base].reshape(3, 3)
        roll = math.asin(max(-1.0, min(1.0, float(Rb[2, 1]))))
        self.dh = getattr(self, 'dh', 0.0)
        h0 = max(0.0, min(1.0, self.height + cmd.dip))
        lim = min(self.gains.roll_max, h0, 1.0 - h0)
        self.dh = max(-lim, min(lim, self.dh + self.gains.roll_rate * roll * dt))
        targets = {}
        self.look = getattr(self, 'look', 0.0)
        dl = 0.5 * dt                                             # look-up slew, rad/s
        self.look += max(-dl, min(dl, max(-0.1, min(0.35, cmd.look_up)) - self.look))
        for side, sgn in (('l', -1.0), ('r', 1.0)):
            hq, kq = rb.pose_angles(h0 + sgn * self.dh)
            targets[side] = (hq + self.look + cmd.kick, kq)       # rotate the body back relative to the legs
        if self.K is None or abs(self.height - (self.K_height or 0)) > 0.05:
            self.K, self.lqr_info = self.lqr(data)
            self.K_height = self.height

        fwd = self.heading(data)
        # pendulum angle: body centre of mass relative to the axle, in the heading's vertical plane
        wheel_set = set(rb.wheels)
        com = np.zeros(3); Mb = 0.0
        for i in rb.bodies:
            if i in wheel_set:
                continue
            com += m.body_mass[i] * data.xipos[i]; Mb += m.body_mass[i]
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
        # speed governor: never ask for more than the wheels can do with torque left over for balancing
        vmax = self.gains.speed_margin * rb.wheel_omega * rb.r
        target = max(-vmax, min(vmax, cmd.speed))
        self.v_cmd = getattr(self, 'v_cmd', 0.0)
        dv = self.gains.accel * dt
        self.v_cmd += max(-dv, min(dv, target - self.v_cmd))
        self.top_speed = vmax
        self.x_ref += self.v_cmd * dt
        # keep the position reference close so a big push is not chased back the whole way
        self.x_ref = x + max(-0.3, min(0.3, self.x_ref - x))
        s = np.array([x - self.x_ref, theta, v - self.v_cmd, theta_dot])
        u = float(-self.K @ s)
        mujoco.mj_objectVelocity(m, data, mujoco.mjtObj.mjOBJ_BODY, rb.base, vel, 0)
        yaw_rate = float(vel[2])                      # world-frame angular velocity about z
        tau_yaw = self.gains.yaw_kp_per_nm * rb.wheel_peak * (cmd.yaw_rate - yaw_rate)
        lim = self.gains.yaw_share * rb.wheel_peak               # balancing keeps the rest of each wheel's torque
        tau_yaw = max(-lim, min(lim, tau_yaw))

        # legs: PD + gravity feedforward (generalised gravity minus the ground reaction through each wheel)
        kp, kd = self.gains.leg_kp_per_nm * rb.leg_peak, self.gains.leg_kd_per_nm * rb.leg_peak
        jacp = np.zeros((3, m.nv))
        weight = np.array([0, 0, rb.total_mass * G / 2])
        tau = {}
        for side, wid in (('l', rb.wheels[0]), ('r', rb.wheels[1])):
            mujoco.mj_jacBody(m, data, jacp, None, wid)
            hip_t, knee_t = targets[side]
            for name, target in ((f'hip_{side}', hip_t), (f'knee_{side}', knee_t)):
                qi, vi = rb.qadr[name], rb.vadr[name]
                ff = data.qfrc_bias[vi] - jacp[:, vi] @ weight
                tau[name] = kp * (target - data.qpos[qi]) - kd * data.qvel[vi] + ff
        tau['wheel_l'] = 0.5 * u - tau_yaw
        tau['wheel_r'] = 0.5 * u + tau_yaw

        out = {}
        if rb.knee_coupled:
            # joint torques -> motor torques: the knee motor drives hip + knee (parallelogram), so it supplies all of the
            # knee's torque and that much of the hip's; the hip motor supplies the rest
            for side in ('l', 'r'):
                tau[f'hip_{side}'] -= tau[f'knee_{side}']
        for name, t in tau.items():
            omega = data.actuator_velocity[rb.act[name]]               # the motor's own speed (hip + knee for the knee motor)
            peak, om = (rb.wheel_peak, rb.wheel_omega) if name.startswith('wheel') else (rb.leg_peak, rb.leg_omega)
            c = clip_torque(t, omega, peak, om)
            if abs(c) < abs(t) - 1e-9:
                self.saturation[name] += 1
            out[name] = c
        if self.delay_steps:
            self.buffer.append(out)
            out = self.buffer.pop(0) if len(self.buffer) > self.delay_steps else {n: 0.0 for n in out}
        for name, c in out.items():
            data.ctrl[rb.act[name]] = c
        return dict(theta=theta, x=x, v=v, u=u, height=self.height, v_cmd=self.v_cmd, roll=roll, level=self.dh)
