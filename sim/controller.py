"""Baseline balance controller, tuned per design from the design's own model.

Same structure as Upkie's and the Diablo-class LQR balancers:

- **Legs:** joint PD to the pose that puts each wheel under the hip at the commanded height, plus a gravity feedforward
  from the model (generalised gravity minus the ground reaction through the wheel Jacobian). With stiff legs the robot
  is one pendulum on two wheels.
- **Balance:** a linearised wheeled-inverted-pendulum LQR. Its parameters (masses, centre-of-mass height, inertias,
  wheel inertia) are read from the MuJoCo model at the current pose and the gains are recomputed as the height
  changes, so each design gets a controller made for it.
- **Turning:** differential wheel torque on yaw rate.
- **Tail** (when the design has one): held up while balancing (and wagging, if asked). To sit, the robot crouches,
  puts the tail where it will meet the ground and leans back onto it; balance switches off and the wheels hold. To
  stand, the tail pushes the body forward and balance takes over again. If the robot tips backwards past saving,
  the tail swings down and catches it (then it stands back up). An e-stop is a controlled stop (IEC 60204-1
  category 1): sit, engage the tail's fail-safe ratchet, then cut every motor.
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
    sit: bool = False          # sit back on the tail (a tripod: no balancing needed)
    estop: bool = False        # controlled stop: sit, lock the tail, cut all motors
    wag: float = 0.0           # tail wag amplitude, rad
    tail_up: float = 0.45      # tail angle while balancing, rad above horizontal


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
        jn = [model.joint(i).name for i in range(model.njnt)]
        self.tail = info.get('tail') if 'tail_pitch' in jn else None
        if self.tail:
            self.tq = {n: j(n).qposadr[0] for n in ('tail_pitch', 'tail_yaw')}
            self.tv = {n: j(n).dofadr[0] for n in ('tail_pitch', 'tail_yaw')}
            self.tact = {n: model.actuator(n).id for n in ('tail_pitch', 'tail_yaw')}
            self.tail_jid = model.joint('tail_pitch').id
            self.tail_tip = model.site('tail_tip').id
            self.tail_peak = {'tail_pitch': self.tail['pitch']['peak_nm'], 'tail_yaw': self.tail['yaw']['peak_nm']}
            self.tail_omega = {'tail_pitch': self.tail['pitch']['omega_max'], 'tail_yaw': self.tail['yaw']['omega_max']}
            self.tail_rated = {'tail_pitch': self.tail['pitch']['rated_nm'], 'tail_yaw': self.tail['yaw']['rated_nm']}
            self.tail_reach = self.tail['reach_m']          # pivot to the shoe's centre

    def peak_for(self, name):
        if name.startswith('tail'):
            return self.tail_peak[name]
        return self.wheel_peak if name.startswith('wheel') else self.leg_peak

    def rated_for(self, name):
        if name.startswith('tail'):
            return self.tail_rated[name]
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
        if robot.tail:
            q[robot.tq['tail_pitch']] = 0.45                # the tail starts up, where balancing holds it
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
        self.saturation = {n: 0 for n in list(self.robot.act) + (list(self.robot.tact) if self.robot.tail else [])}
        self.steps = 0
        self.mode, self.mode_since = 'balance', 0.0
        self.modes = []                  # (time, mode) transitions, for the run's events
        self.theta_ref = 0.0
        self.x_hold = None
        self.lock_q = None               # tail ratchet engaged at this angle (None = released)
        self.press = 0.0
        self.lock_range = None           # the joint's normal upper limit, kept while the ratchet is engaged
        self.tail_load = {}              # mode -> peak tail motor torque; 'lock' -> peak torque on the ratchet

    def engage_lock(self, q):
        rb = self.robot
        if self.lock_q is None:
            self.lock_range = float(rb.m.jnt_range[rb.tail_jid][1])
            self.lock_q = q

    def release_lock(self):
        rb = self.robot
        if self.lock_q is not None:
            rb.m.jnt_range[rb.tail_jid][1] = self.lock_range
            self.lock_q = None

    def set_mode(self, mode, t):
        if mode != self.mode:
            self.mode, self.mode_since = mode, t
            self.modes.append((round(t, 3), mode))

    def tail_contact_angle(self, data):
        """Tail pitch that puts the shoe on the floor, for the body's current pose."""
        rb = self.robot
        p = data.xanchor[rb.tail_jid]
        R = data.xmat[rb.base].reshape(3, 3)
        L, dz = rb.tail_reach, rb.tail.get('drop_m', 0.0)
        want = rb.tail['shoe_r_m'] - p[2]
        # the shoe in the pitch frame is (-L, 0, -dz); turned by q about y, then by the body's orientation
        f = lambda q: R[2, 0] * (-L * math.cos(q) - dz * math.sin(q)) + R[2, 2] * (L * math.sin(q) - dz * math.cos(q))
        lo, hi = -1.7, 0.9
        if f(lo) >= want:
            return lo
        if f(hi) <= want:
            return hi
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if f(mid) < want else (lo, mid)
        return 0.5 * (lo + hi)

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
        t_now = data.time
        seated = self.mode in ('sitting_down', 'sitting', 'off', 'standing_up')
        h_cmd = 0.0 if seated else cmd.height
        step = self.gains.height_rate * (2.5 if cmd.estop else 1.0) * dt
        self.height += max(-step, min(step, h_cmd - self.height))
        hip_t, knee_t = rb.pose_angles(max(0.0, min(1.0, self.height + cmd.dip)))
        self.look = getattr(self, 'look', 0.0)
        dl = 0.5 * dt                                             # look-up slew, rad/s
        self.look += max(-dl, min(dl, max(-0.1, min(0.35, cmd.look_up)) - self.look))
        hip_t += self.look + cmd.kick                             # rotate the body back relative to the legs
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
        tail = self.tail_step(data, cmd, theta, theta_dot, t_now) if rb.tail else None
        if self.mode == 'off':
            for i in range(m.nu):
                data.ctrl[i] = 0.0
            return dict(theta=theta, x=0.0, v=0.0, u=0.0, height=self.height, v_cmd=0.0, mode=self.mode)
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
        if self.mode in ('sitting_down', 'standing_up', 'catching'):
            self.x_ref, self.v_cmd = x, 0.0              # no pull back to a position while getting on or off the tail
        s = np.array([x - self.x_ref, theta - self.theta_ref, v - self.v_cmd, theta_dot])
        u = float(-self.K @ s)
        if self.mode == 'sitting':                    # a tripod: no balancing, the wheels just hold their place
            if self.x_hold is None:
                self.x_hold = x
            u = -(0.6 * rb.wheel_peak) * max(-1.0, min(1.0, 8.0 * (x - self.x_hold) + 3.0 * v))
        else:
            self.x_hold = None
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
            for name, target in ((f'hip_{side}', hip_t), (f'knee_{side}', knee_t)):
                qi, vi = rb.qadr[name], rb.vadr[name]
                ff = data.qfrc_bias[vi] - jacp[:, vi] @ weight
                tau[name] = kp * (target - data.qpos[qi]) - kd * data.qvel[vi] + ff
        tau['wheel_l'] = 0.5 * u - tau_yaw
        tau['wheel_r'] = 0.5 * u + tau_yaw

        out = {}
        for name, t in tau.items():
            omega = data.qvel[rb.vadr[name]]
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
        self.last_v = v
        return dict(theta=theta, x=x, v=v, u=u, height=self.height, v_cmd=self.v_cmd, mode=self.mode)

    # --- the tail
    def tail_step(self, data, cmd, theta, theta_dot, t):
        rb, m = self.robot, self.robot.m
        qa, va = rb.tq['tail_pitch'], rb.tv['tail_pitch']
        q, qd = data.qpos[qa], data.qvel[va]
        tip_z = data.site_xpos[rb.tail_tip][2]
        touching = tip_z < rb.tail['shoe_r_m'] + 0.01
        in_mode = t - self.mode_since
        q_contact = self.tail_contact_angle(data)
        # --- modes
        if self.mode == 'balance':
            if cmd.sit or cmd.estop:
                self.set_mode('sitting_down', t)
            elif theta < -0.2 and theta_dot < -0.3 and getattr(self, 'last_v', 0.0) < 0.15:
                # falling backwards, and not just leaning back to brake after a forward shove
                self.set_mode('catching', t)
        elif self.mode in ('sitting_down', 'catching'):
            settled = touching and theta < -0.08 and abs(theta_dot) < 0.3 and (self.mode == 'catching' or self.height < 0.04)
            if self.mode == 'catching' and touching:
                self.engage_lock(q)                     # the pawl drops in: the tail cannot be pushed up
                if in_mode > 0.15:                      # caught: stop balancing against the tail, sit, then get up
                    settled, in_mode = True, 1.0
            if settled and in_mode > 0.3:
                self.set_mode('sitting', t)
                self.press = q if self.lock_q is not None else q_contact
        elif self.mode == 'sitting':
            if theta > 0.03 and not cmd.estop:
                # bounced forward off the tail: the weight is ahead of the wheels, so this is balancing, not sitting
                self.release_lock()
                self.set_mode('balance', t)
            elif in_mode > 0.3:
                self.engage_lock(q)                     # parked on the ratchet: the motor need not hold the load
            if cmd.estop and in_mode > 0.3:
                self.set_mode('off', t)                 # category 1: seated and still, now cut the power
            elif not cmd.sit and not cmd.estop and in_mode > 1.0:
                self.set_mode('standing_up', t)
                self.release_lock()
        elif self.mode == 'standing_up':
            if cmd.sit or cmd.estop:
                self.set_mode('sitting_down', t)
            elif theta > -0.03 and abs(theta_dot) < 0.3 and in_mode > 0.3:
                self.set_mode('balance', t)
        # --- lean reference for the balance loop
        if self.mode == 'sitting_down':
            near = self.height < 0.08 and abs(q - q_contact) < 0.12
            goal = -0.12 if near else 0.0
            rate = 0.35
        elif self.mode == 'standing_up':
            goal, rate = 0.0, 0.25
        elif self.mode == 'sitting':
            goal, rate = theta, 10.0                   # follow, so standing up starts from where it sits
        else:
            goal, rate = 0.0, 0.6
        dr = rate * m.opt.timestep
        self.theta_ref += max(-dr, min(dr, goal - self.theta_ref))
        # --- tail targets (positive = up)
        peak = rb.tail_peak['tail_pitch']
        if self.lock_q is not None:
            # the ratchet stops the tail being pushed up; it can still drop (and then catches on a lower tooth)
            self.lock_q = min(self.lock_q, q)
            m.jnt_range[rb.tail_jid][1] = self.lock_q + rb.tail['lock_tooth_rad']
            self.tail_load['lock'] = max(self.tail_load.get('lock', 0.0), abs(float(data.qfrc_constraint[va])))
        if self.mode == 'off':
            return None
        if self.mode == 'balance':
            q_t, kp = cmd.tail_up, 0.8 * peak
        elif self.mode == 'sitting_down':
            q_t, kp = (q_contact if self.height < 0.08 else max(q_contact + 0.1, -1.6)), 1.5 * peak
        elif self.mode == 'catching':
            q_t, kp = q_contact, 3.0 * peak
        elif self.mode == 'sitting':
            q_t, kp = self.press, 1.5 * peak           # hold the angle it sat down at: a stiff third leg, no pushing
        else:                                          # standing up: balance rolls under the body; the tail just follows the floor
            q_t, kp = (q_contact + 0.02 if touching else cmd.tail_up), 0.5 * peak
        # move at up to 4 rad/s (a deliberate, quick motion) except when catching a fall, which goes flat out
        prev = getattr(self, 'tail_q_cmd', q)
        if self.mode != 'catching':
            dq = 4.0 * m.opt.timestep
            q_t = prev + max(-dq, min(dq, q_t - prev))
        self.tail_q_cmd = q_t
        kd = 0.08 * peak
        tau = kp * (q_t - q) - kd * qd + data.qfrc_bias[va]
        yq, yv = rb.tq['tail_yaw'], rb.tv['tail_yaw']
        wag = cmd.wag * math.sin(2 * math.pi * 2.2 * t) if self.mode == 'balance' else 0.0
        ypk = rb.tail_peak['tail_yaw']
        tau_y = 1.2 * ypk * (wag - data.qpos[yq]) - 0.05 * ypk * data.qvel[yv] + data.qfrc_bias[yv]
        for name, val, vi in (('tail_pitch', tau, va), ('tail_yaw', tau_y, yv)):
            c = clip_torque(val, data.qvel[vi], rb.tail_peak[name], rb.tail_omega[name])
            if abs(c) < abs(val) - 1e-9:
                self.saturation[name] += 1
            data.ctrl[rb.tact[name]] = c
        if t - self.mode_since > 0.5:                  # steady-state load per mode, after the transition
            self.tail_load[self.mode] = max(self.tail_load.get(self.mode, 0.0), abs(float(data.ctrl[rb.tact['tail_pitch']])))
        return dict(q=q, q_contact=q_contact, touching=touching)
