"""The feed under motion: the dial driven like the real feed servo (an STS3215 since D42), the cartridge slewing, jolted and shaken, and the
ball's state when it first touches the tyres (what the launch stage starts from).

    .venv/bin/python sim/turret_feed_dyn.py [--quick] [--video]     # writes exports/turret/feed/feed_dyn.json, plots, mp4

Built on sim/turret_feed.py (the program agent's MuJoCo feed: hopper, dial, baffle, chute from cad/turret.py's Geo;
imported unchanged). This file adds:
  - the dial motor as the Feetech STS3215 servo (12 V, 345:1) sees it: the servo's own move profile (the firmware's goal
    speed and acceleration) tracked by a stiff position loop in Python whose torque is clipped by the servo's
    torque-speed line (2.94 N m stall, 45 rpm no-load at 12 V) and by the firmware's torque limit, its motor's inertia
    reflected through 345:1 on the joint (not published: est from a typical rotor, swept), and the gear train's
    friction. The step time and the ball's drop latency follow from that, not from an assumed move. (It replaced the
    DJI M2006 + C610, which stepped in ~100 ms but cannot be bought: docs/decisions.yaml D42);
  - the cartridge frame moving: a pan slew (rate W(t) about the world-up axis through the pan axis, which passes
    through the tilt axis point (tilt_x, 0, tilt_c) of the C frame) puts centrifugal, Euler and Coriolis forces on
    every ball (applied as xfrc each step); the robot's body catching a shove (a pitch acceleration of 30 rad/s^2,
    cad/turret_motion.py BODY, 0.45 m above the hip: 13.5 m/s^2 along the barrel for 50 ms each way, est) and the
    rough-ground vibration (5 m/s^2, 8-25 Hz, as sim/turret_feed.py's park test) move the whole frame (gravity
    modulation);
  - the hand-over to the launch: each ball is taken out when its centre crosses the first-touch plane of the tyres
    (x = wheel_x - sqrt((R + r)^2 - (c/2)^2), the same point sim/turret_launch3d.py starts from) and its position,
    velocity and spin there are recorded, so one stage's exit is the next stage's input;
  - the rate of fire: how fast the dial can step (motor-limited), how long a ball takes from the step command to the
    tyres (the shot latency), when it has cleared the floor opening (the earliest safe next step), and the rate at
    which misses, doubles or struck balls appear; also continuous rotation of the dial.
Rigid spheres cannot bridge by tack (sim/turret_ball.py SOURCES hyper_hopper_patent), so the jam-rate counts in the
bench plan remain the proof for the hopper; this file's claims are about the dial, the chute and the motion.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault('MUJOCO_GL', 'egl')
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_common as tc  # noqa: E402

OUT = R / 'exports' / 'turret' / 'feed'
TIMESTEP = None                                    # taken from sim/turret_feed.py at run time

SERVO = {
    'name': 'Feetech STS3215 12 V (Waveshare ST3215), bus ID 3', 'ratio': 345, 'stall_nm': 2.94, 'no_load_rad_s': 45 * 2 * math.pi / 60,
    'torque_cap': 0.5, 'goal_speed_rad_s': 4.0, 'acc_rad_s2': 60.0,
    'source': 'Feetech STS3215 C018 data (catalog feetech-sts3215-c018-12v; references/vendor/feetech-sts3215): 30 kg cm (2.94 N m) stall and 45 rpm no-load '
              'at 12 V, 345:1, 12-bit position; the firmware sets the goal speed (85 % of no-load), the acceleration and the torque limit (50 %) '
              '(docs/turret-firmware.md, firmware/turret)',
    'rotor_I_kg_m2': 2.4e-8,
    'rotor_I_note': 'not published. est: a small iron-core 12 V motor, ~3 g of rotor at r 4 mm (m r^2 / 2): 2.4e-8, reflected through 345:1 = 2.9e-3 kg m^2, '
                    'which dominates the dial (~1e-4); swept 1e-8 .. 5e-8 (feed_dyn.json rotor_inertia_sensitivity)',
    'friction_coulomb_nm': 0.08, 'friction_viscous_nms': 0.02,
    'friction_note': 'est: a 345:1 spur train with no published no-load current; its back-driving torque (the parked dial holds) is larger than the M2006\'s',
    'loop': {'kp_nm_rad': 60.0, 'kd_nms_rad': 1.5, 'note': 'the servo\'s internal position loop, modelled as a stiff P-D on the profile (est)'},
}
JAM_RULE = {'not_settled_s': 0.3, 'reverse_deg': 20.0, 'stop_after': 3,
            'source': 'docs/turret-prototype-plan.md T7: a step not settled (within 23 counts) in 300 ms, or the load reading over a threshold, reverses 20 deg '
                      'and retries; three in a row stops the feed'}
BODY_JOLT = {'a_m_s2': 13.5, 'dt_s': 0.05, 'note': 'est: a 30 rad/s^2 pitch catch (cad/turret_motion.py BODY) at 0.45 m from the hip axis, 50 ms each way'}
SHAKE = {'a_m_s2': 5.0, 'f_hz': (8.0, 15.0, 25.0), 'note': 'sim/turret_feed.py park test: driving over rough ground'}
STEP_DEG = 45.0


def feed_module():
    return tc.sim_module('turret_feed')


def i_reflected(rotor_I=None):
    rotor_I = SERVO['rotor_I_kg_m2'] if rotor_I is None else rotor_I
    return rotor_I * SERVO['ratio'] ** 2


def tau_limit(om, cap=None):
    """What the servo can push at output speed om (rad/s): its torque-speed line at 12 V, then the firmware's torque limit
    (a fraction of the stall torque)."""
    cap = SERVO['torque_cap'] if cap is None else cap
    line = SERVO['stall_nm'] * (1 - abs(om) / SERVO['no_load_rad_s'])
    return max(0.0, min(cap * SERVO['stall_nm'], line))


class DynFeed:
    """sim/turret_feed.py's Feed with the real dial motor, a moving frame and the launch hand-over."""

    def __init__(self, G, tu, mu=0.7, n_balls=30, seed=0, rotor_I=None, i_max=None, pose=(0.0, 0.0, 0.0)):
        # i_max: the servo's torque limit as a fraction of its stall torque (None: SERVO torque_cap)
        import mujoco
        global TIMESTEP
        self.mj = mujoco
        self.tf = feed_module()
        TIMESTEP = self.tf.TIMESTEP
        self.F = self.tf.Feed(G, tu, mu, n_balls, seed)
        self.G = G
        self.m, self.d = self.F.model, self.F.data
        self.n = n_balls
        self.qadr = np.array(self.F.qadr)
        self.vadr = np.array(self.F.vadr)
        self.bodies = np.array(self.F.balls)
        self.dial_q = self.m.jnt_qposadr[self.F.dial_j]
        self.dial_v = self.m.jnt_dofadr[self.F.dial_j]
        self.i_max = i_max
        self.ball_m = self.tf.BALL_M
        r = G.ball / 2
        self.x_touch = (G.wheel_x - math.sqrt((G.wheel_d / 2 + r) ** 2 - (G.wheel_c / 2) ** 2)) / 1000     # first touch on the tyres (m)
        self.z_clear = (G.floor_z - r) / 1000                                                            # centre below this: the ball is under the dial's sweep
        self.axis_point = np.array([G.tilt_x, 0.0, G.tilt_c]) / 1000                                      # the pan axis passes through here
        self.pose = pose
        self.F.set_gravity(*pose)
        self.g_base = self.m.opt.gravity.copy()
        self.entries = []                                        # the launch hand-over: one dict per ball
        self.cleared = {}                                         # ball -> time its centre dropped under the dial's sweep
        self.gone = set()
        self.events = []
        self.dial_log = []
        self.frames = []
        self.rotor_I = rotor_I
        self.F.settle(1.5)
        self.gone |= set(self.F.gone)
        self._take_over_dial()

    def _take_over_dial(self):
        """Replace the stiff position actuator with a direct torque (ctrl = N m) and put the motor's inertia on the joint."""
        m = self.m
        m.actuator_gainprm[0, :] = 0.0
        m.actuator_gainprm[0, 0] = 1.0
        m.actuator_biasprm[0, :] = 0.0
        m.actuator_ctrllimited[0] = 0
        m.actuator_forcelimited[0] = 0
        m.dof_armature[self.dial_v] = i_reflected(self.rotor_I)
        m.dof_damping[self.dial_v] = 0.0
        m.dof_frictionloss[self.dial_v] = 0.0
        self.d.ctrl[0] = 0.0

    # --- the frame's motion
    def _fictitious(self, Om, al, u):
        """Centrifugal, Euler and Coriolis forces on every live ball for the cartridge turning at Om (rad/s), dOm/dt = al,
        about the unit axis u (C frame) through self.axis_point."""
        live = [i for i in range(self.n) if i not in self.gone]
        if not live or (abs(Om) < 1e-9 and abs(al) < 1e-9):
            return
        idx = np.array(live)
        p = np.stack([self.d.qpos[self.qadr[idx] + k] for k in range(3)], 1)
        v = np.stack([self.d.qvel[self.vadr[idx] + k] for k in range(3)], 1)
        rho = p - self.axis_point
        a = -al * np.cross(u, rho) - Om * Om * np.cross(u, np.cross(u, rho)) - 2 * Om * np.cross(u, v)
        self.d.xfrc_applied[self.bodies[idx], :3] = self.ball_m * a

    def run(self, seconds, theta_ref=None, omega_ref=None, powered=True, slew=None, jolt=None, shake=None, frame_every=None, t0=None):
        """Advance. theta_ref(t), omega_ref(t): the dial's reference (rad, rad/s); powered False: the servo unpowered (the
        safety line released: the gear train's friction alone holds the dial). slew: (Om(t), al(t)) callables; jolt: a(t) -> (ax, ay, az) m/s^2 on
        the frame; shake: (amplitude, f) as sim/turret_feed.py. Records entries (first touch) and clearing times."""
        mj, d, m = self.mj, self.d, self.m
        n = int(round(seconds / TIMESTEP))
        g0 = self.g_base
        u = -g0 / np.linalg.norm(g0)
        fed = []
        for k in range(n):
            t = d.time
            th, om = d.qpos[self.dial_q], d.qvel[self.dial_v]
            if powered and theta_ref is not None:
                tau = SERVO['loop']['kp_nm_rad'] * (theta_ref(t) - th) + SERVO['loop']['kd_nms_rad'] * ((omega_ref(t) if omega_ref else 0.0) - om)
                lim = tau_limit(om, self.i_max)
                tau = max(-lim, min(lim, tau))
                fr = SERVO['friction_coulomb_nm'] * math.tanh(om / 0.5) + SERVO['friction_viscous_nms'] * om
                d.ctrl[0] = tau - fr
                m.dof_frictionloss[self.dial_v] = 0.0
            else:
                d.ctrl[0] = 0.0
                m.dof_frictionloss[self.dial_v] = SERVO['friction_coulomb_nm']   # unpowered: the gear train's own drag (est)
            g = g0.copy()
            if shake:
                amp, f = shake
                g = g + amp * np.array([math.sin(2 * math.pi * f * t), math.sin(2 * math.pi * f * 1.37 * t + 1), 0.5 * math.sin(2 * math.pi * f * 0.71 * t + 2)])
            if jolt:
                g = g - np.array(jolt(t))                                        # the frame accelerating by a feels -a
            m.opt.gravity[:] = g
            d.xfrc_applied[:] = 0.0
            if slew:
                self._fictitious(slew[0](t), slew[1](t), u)
            mj.mj_step(m, d)
            self.dial_log.append((t, th, om, d.ctrl[0]))
            for i in range(self.n):
                if i in self.gone:
                    continue
                qa, va = self.qadr[i], self.vadr[i]
                x, y, z = d.qpos[qa:qa + 3]
                if i not in self.cleared and z < self.z_clear and x > (self.G.exit_x - self.G.br) / 1000:
                    self.cleared[i] = round(t, 4)
                if x >= self.x_touch and z < (self.G.floor_z - self.G.floor_t) / 1000:
                    vx, vy, vz = d.qvel[va:va + 3]
                    wx, wy, wz = d.qvel[va + 3:va + 6]
                    e = {'ball': i, 't': round(t, 4), 'y': y, 'z': z, 'vx': vx, 'vy': vy, 'vz': vz, 'wx': wx, 'wy': wy, 'wz': wz,
                         'x_from_wheel_axes': x - self.G.wheel_x / 1000}
                    self.entries.append(e)
                    fed.append(e)
                    self.gone.add(i)
                    d.qpos[qa:qa + 3] = (0.3 + 0.03 * i, 0.3, 0.05)
                    d.qvel[va:va + 6] = 0
                elif z < -0.05 or (math.hypot(x, y) > (self.G.dial_wall_r + 5) / 1000 and z > (self.G.floor_z - self.G.floor_t) / 1000):
                    self.events.append({'t': round(t, 4), 'escaped': i})
                    self.gone.add(i)
                    d.qpos[qa:qa + 3] = (0.3 + 0.03 * i, 0.3, 0.05)
                    d.qvel[va:va + 6] = 0
            if frame_every and k % frame_every == 0:
                self.frames.append(d.qpos.copy())
        m.opt.gravity[:] = g0
        d.xfrc_applied[:] = 0.0
        return fed

    def in_chute(self):
        """Balls below the floor that have not reached the tyres: on their way, or stuck."""
        out = []
        for i in range(self.n):
            if i in self.gone:
                continue
            x, y, z = self.d.qpos[self.qadr[i]:self.qadr[i] + 3]
            if z < (self.G.floor_z - self.G.floor_t) / 1000:
                out.append((i, round(x * 1000, 1), round(z * 1000, 1)))
        return out

    def dial_angle(self):
        return float(self.d.qpos[self.dial_q])


def cosine_step(t0, a0, da, T):
    def th(t):
        u = (t - t0) / T
        return a0 if u <= 0 else a0 + da if u >= 1 else a0 + da * 0.5 * (1 - math.cos(math.pi * u))

    def om(t):
        u = (t - t0) / T
        return 0.0 if u <= 0 or u >= 1 else da * 0.5 * math.pi / T * math.sin(math.pi * u)
    return th, om


def slew_profile(t_start, w_max_deg_s, ramp_s, hold_s):
    """Pan rate: ramp up over ramp_s, hold, ramp down. Returns (Om(t), al(t))."""
    w = math.radians(w_max_deg_s)

    def Om(t):
        s = t - t_start
        if s < 0 or s > 2 * ramp_s + hold_s:
            return 0.0
        if s < ramp_s:
            return w * s / ramp_s
        if s < ramp_s + hold_s:
            return w
        return w * (2 * ramp_s + hold_s - s) / ramp_s

    def al(t):
        s = t - t_start
        if s < 0 or s > 2 * ramp_s + hold_s:
            return 0.0
        if s < ramp_s:
            return w / ramp_s
        if s < ramp_s + hold_s:
            return 0.0
        return -w / ramp_s
    return Om, al


def jolt_profile(t_start, a=None, dt=None, axis=0):
    a = BODY_JOLT['a_m_s2'] if a is None else a
    dt = BODY_JOLT['dt_s'] if dt is None else dt

    def f(t):
        s = t - t_start
        v = [0.0, 0.0, 0.0]
        if 0 <= s < dt:
            v[axis] = a
        elif dt <= s < 2 * dt:
            v[axis] = -a
        return v
    return f


# ------------------------------------------------------------------------------------------------ cases

def servo_step(t0, a0, da, v=None, acc=None):
    """The servo's own move profile for one step: a trapezoid at the goal speed v (rad/s) with the acceleration acc
    (rad/s^2), as the firmware sets them (SERVO). Returns (theta(t), omega(t))."""
    v = SERVO['goal_speed_rad_s'] if v is None else v
    acc = SERVO['acc_rad_s2'] if acc is None else acc
    sgn = 1.0 if da >= 0 else -1.0
    D = abs(da)
    ta = v / acc
    if acc * ta * ta >= D:                                 # never reaches v: a triangle
        ta = math.sqrt(D / acc)
        v = acc * ta
        tc = 0.0
    else:
        tc = (D - acc * ta * ta) / v
    T = 2 * ta + tc

    def pos(s):
        if s <= 0:
            return 0.0
        if s < ta:
            return 0.5 * acc * s * s
        if s < ta + tc:
            return 0.5 * acc * ta * ta + v * (s - ta)
        if s < T:
            r = T - s
            return D - 0.5 * acc * r * r
        return D

    def vel(s):
        if s <= 0 or s >= T:
            return 0.0
        if s < ta:
            return acc * s
        if s < ta + tc:
            return v
        return acc * (T - s)
    return (lambda t: a0 + sgn * pos(t - t0)), (lambda t: sgn * vel(t - t0))


def burst(DF: DynFeed, n_shots, period, move_s=None, slew=None, jolt=None, shake=None, wait_ready=True, frame_every=None, tail_s=0.5):
    """n_shots dial steps, one every `period` s (or as soon as the dial is settled when the period is shorter than the
    step takes and wait_ready). Each ball is attributed to the step during whose window it dropped out of the dial
    (its clearing time), so a ball that arrives at the tyres after the next step's command still counts for the step
    that released it. Returns per-step records, each with its entries (the launch hand-over)."""
    rows = []
    a = DF.dial_angle()
    first = len(DF.entries)
    t0s = []
    for k in range(n_shots):
        t0 = DF.d.time
        t0s.append(t0)
        th, om = cosine_step(t0, a, math.radians(STEP_DEG), move_s) if move_s else servo_step(t0, a, math.radians(STEP_DEG))
        a += math.radians(STEP_DEG)
        n_log = len(DF.dial_log)
        DF.run(period, th, om, slew=slew, jolt=jolt, shake=shake, frame_every=frame_every)
        extra = 0.0
        while wait_ready and abs(DF.dial_angle() - a) > math.radians(2.0) and extra < 0.5:
            DF.run(0.01, th, om, slew=slew, jolt=jolt, shake=shake, frame_every=frame_every)
            extra += 0.01
        seg = DF.dial_log[n_log:]
        settled = next((t for t, th_, om_, _ in seg if abs(th_ - a) < math.radians(2.0) and abs(om_) < 2.0), None)
        rows.append({'step': k + 1, 't0': round(t0, 4), 'balls': 0, 'entries': [], 'latency_ms': [], 'cleared_ms': [],
                     'step_settled_ms': round((settled - t0) * 1000, 1) if settled else None,
                     'peak_tau_nm': round(max((abs(c) for _, _, _, c in seg), default=0.0), 3), 'peak_dial_rpm': round(max((abs(o) for _, _, o, _ in seg), default=0.0) * 60 / (2 * math.pi)),
                     'period_s': period, 'extra_wait_s': round(extra, 3)})
    DF.run(tail_s, lambda t: a, lambda t: 0.0, slew=slew, jolt=jolt, shake=shake, frame_every=frame_every)      # the last balls arrive
    for e in DF.entries[first:]:
        tc_ = DF.cleared.get(e['ball'], e['t'])
        k = max((i for i, t0 in enumerate(t0s) if t0 <= tc_ + 1e-9), default=0)
        r = rows[k]
        r['balls'] += 1
        r['entries'].append(e)
        r['latency_ms'].append(round((e['t'] - t0s[k]) * 1000, 1))
        if e['ball'] in DF.cleared:
            r['cleared_ms'].append(round((DF.cleared[e['ball']] - t0s[k]) * 1000, 1))
    return rows


def continuous(DF: DynFeed, rpm, seconds, slew=None, shake=None):
    """The dial turning continuously at rpm: balls fall through as the pockets pass the opening."""
    w = rpm * 2 * math.pi / 60
    a0 = DF.dial_angle()
    t0 = DF.d.time
    before = len(DF.entries)
    DF.run(seconds, lambda t: a0 + w * (t - t0), lambda t: w, slew=slew, shake=shake)
    new = DF.entries[before:]
    gaps = np.diff([e['t'] for e in new]) if len(new) > 1 else np.array([])
    return {'rpm': rpm, 'pockets_passed': round(w * seconds / math.radians(STEP_DEG), 1), 'balls': len(new), 'rate_hz': round(len(new) / seconds, 2),
            'gap_ms_min': round(float(gaps.min()) * 1000, 1) if len(gaps) else None, 'gap_ms_max': round(float(gaps.max()) * 1000, 1) if len(gaps) else None,
            'in_chute_after': DF.in_chute()}


def summarize(rows, n_balls_left_in_hopper=None):
    balls = [r['balls'] for r in rows]
    lat = [l for r in rows for l in r['latency_ms']]
    return {'steps': len(rows), 'per_step': balls, 'fed': sum(balls), 'doubles': sum(1 for b in balls if b > 1), 'misses': sum(1 for b in balls if b == 0),
            'latency_ms': {'min': min(lat) if lat else None, 'mean': round(float(np.mean(lat)), 1) if lat else None, 'max': max(lat) if lat else None},
            'cleared_ms_max': max((c for r in rows for c in r['cleared_ms']), default=None),
            'step_settled_ms': [r['step_settled_ms'] for r in rows], 'peak_tau_nm': max(r['peak_tau_nm'] for r in rows), 'peak_dial_rpm': max(r['peak_dial_rpm'] for r in rows)}


def entry_stats(entries):
    if not entries:
        return None
    y = np.array([e['y'] for e in entries]) * 1000
    z = np.array([e['z'] for e in entries]) * 1000
    vx = np.array([e['vx'] for e in entries])
    vy = np.array([e['vy'] for e in entries])
    vz = np.array([e['vz'] for e in entries])
    wy = np.array([e['wy'] for e in entries])
    return {'n': len(entries), 'y_mm': [round(float(y.mean()), 3), round(float(y.std()), 3)], 'z_mm': [round(float(z.mean()), 3), round(float(z.std()), 3)],
            'vx_m_s': [round(float(vx.mean()), 3), round(float(vx.std()), 3), round(float(vx.min()), 3), round(float(vx.max()), 3)],
            'vy_m_s_sd': round(float(vy.std()), 3), 'vz_m_s': [round(float(vz.mean()), 3), round(float(vz.std()), 3)], 'spin_y_rad_s': [round(float(wy.mean()), 1), round(float(wy.std()), 1)]}


POSES = {'level': (0.0, 0.0, 0.0), 'down25': (-25.0, 0.0, 0.0), 'down25_rolled15': (-25.0, 0.0, 15.0), 'level_pitched10': (0.0, 10.0, 0.0)}


def study(quick=False, video=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tu = tc.cad_turret()
    G = tu.Geo()
    OUT.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    res = {'servo': SERVO, 'jam_rule': JAM_RULE, 'body_jolt': BODY_JOLT, 'shake': SHAKE, 'dial_inertia_reflected_kg_m2': i_reflected(),
           'first_touch_x_mm': round(G.wheel_x - 1000 * (G.wheel_x / 1000 - DynFeed.__dict__.get('x_touch', 0)) if False else G.wheel_x - math.sqrt((G.wheel_d / 2 + G.ball / 2) ** 2 - (G.wheel_c / 2) ** 2), 2),
           'geometry': {'ball_mm': G.ball, 'bore_mm': G.bore, 'exit_x_mm': G.exit_x, 'wheel_x_mm': G.wheel_x, 'floor_z_mm': G.floor_z, 'chute_r_mm': G.chute_r}}
    poses = ['level', 'down25'] if quick else list(POSES)
    rate = 3.0
    # 1. the step and the latency at each pose, kids' rate (3/s): the hand-over states
    base = {}
    all_entries = []
    base_rows = []
    for name in poses:
        DF = DynFeed(G, tu, 0.7, 30, seed=1, pose=POSES[name])
        rows = burst(DF, 5 if quick else 8, 1.0 / rate)
        base_rows += rows
        base[name] = {**summarize(rows), 'entries': entry_stats(DF.entries), 'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
        all_entries += DF.entries
        print(f'base {name}: {base[name]["per_step"]} latency {base[name]["latency_ms"]} step {base[name]["step_settled_ms"][:3]} tau {base[name]["peak_tau_nm"]} ({time.time() - t_start:.0f} s)')
    res['steps_at_3_per_s'] = base
    res['entry_states_all'] = entry_stats(all_entries)
    res['entries'] = [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in e.items()} for e in all_entries]
    # 2. the step time against the motor's (unpublished) inertia and the firmware's torque limit (what the servo allows)
    sens = {}
    for label, rI, imax in (('rotor_1e-8', 1e-8, None), ('rotor_5e-8', 5e-8, None), ('torque_limit_30pct', None, 0.3), ('torque_limit_100pct', None, 1.0)):
        DF = DynFeed(G, tu, 0.7, 30, seed=1, rotor_I=rI, i_max=imax, pose=POSES['level'])
        rows = burst(DF, 3, 1.0 / rate)
        s = summarize(rows)
        sens[label] = {'step_settled_ms': s['step_settled_ms'], 'latency_ms': s['latency_ms'], 'peak_tau_nm': s['peak_tau_nm'], 'peak_dial_rpm': s['peak_dial_rpm']}
        print(f'sens {label}: {sens[label]} ({time.time() - t_start:.0f} s)')
    res['rotor_inertia_sensitivity'] = sens
    # 3. the rate of fire: stepping faster and faster, then continuous rotation
    rates = {}
    for rz in ((2.5, 3.0) if quick else (2.0, 2.5, 3.0, 4.0, 6.0)):      # the servo's step (~235 ms) puts the limit near 3/s
        DF = DynFeed(G, tu, 0.7, 30, seed=2, pose=POSES['down25'])
        rows = burst(DF, 6 if quick else 8, 1.0 / rz, wait_ready=True)
        s = summarize(rows)
        achieved = len(rows) / (rows[-1]['t0'] + rows[-1]['period_s'] + rows[-1]['extra_wait_s'] - rows[0]['t0']) if len(rows) > 1 else rz
        rates[f'{rz:g}_per_s'] = {**s, 'achieved_rate_hz': round(achieved, 2), 'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
        print(f'rate {rz}: fed {s["fed"]} per step {s["per_step"]} achieved {achieved:.2f}/s latency {s["latency_ms"]} ({time.time() - t_start:.0f} s)')
    res['stepping_rates'] = rates
    cont = {}
    for rpm in ((15.0, 25.0, 45.0) if quick else (10.0, 15.0, 25.0, 35.0, 45.0, 75.0)):
        DF = DynFeed(G, tu, 0.7, 30, seed=2, pose=POSES['down25'])
        cont[f'{rpm:g}_rpm'] = continuous(DF, rpm, 2.0 if quick else 3.0)
        print(f'continuous {rpm} rpm: {cont[f"{rpm:g}_rpm"]} ({time.time() - t_start:.0f} s)')
    res['continuous_dial'] = cont
    # 4. feeding while the turret slews (90 deg/s, the servo's limit, with 20 ms ramps: the hard case; and 150 deg/s)
    slews = {}
    for name in poses[:2]:
        for dps, ramp in ((90.0, 0.02), (150.0, 0.02)):
            DF = DynFeed(G, tu, 0.7, 30, seed=3, pose=POSES[name])
            t0 = DF.d.time
            rows = burst(DF, 5, 1.0 / rate, slew=slew_profile(t0 + 0.2, dps, ramp, 1.0), frame_every=(20 if video and name == 'down25' and dps == 90.0 else None))
            s = summarize(rows)
            slews[f'{name}_{dps:g}deg_s'] = {**s, 'entries': entry_stats(DF.entries), 'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
            if DF.frames:
                res['_video_frames'] = (DF, name, dps)
            print(f'slew {name} {dps}: {s["per_step"]} latency {s["latency_ms"]} entries {slews[f"{name}_{dps:g}deg_s"]["entries"]} ({time.time() - t_start:.0f} s)')
    res['feeding_while_slewing'] = slews
    # 5. the body jolt during a step, and with the dial parked (powered and not); vibration while feeding
    jolts = {}
    for name in poses[:2]:
        DF = DynFeed(G, tu, 0.7, 30, seed=4, pose=POSES[name])
        t0 = DF.d.time
        rows = burst(DF, 4, 1.0 / rate, jolt=jolt_profile(t0 + 0.05))
        jolts[f'{name}_feeding'] = {**summarize(rows), 'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
        for powered in (True, False):
            DF = DynFeed(G, tu, 0.7, 30, seed=4, pose=POSES[name])
            a = DF.dial_angle()
            before = len(DF.entries)
            DF.run(0.6, (lambda t: a), (lambda t: 0.0), powered=powered, jolt=jolt_profile(DF.d.time + 0.1))
            for f in SHAKE['f_hz']:
                DF.run(0.6, (lambda t: a), (lambda t: 0.0), powered=powered, shake=(SHAKE['a_m_s2'], f))
            jolts[f'{name}_parked_{"powered" if powered else "motor_off"}'] = {'balls_at_tyres': len(DF.entries) - before, 'dial_turned_deg': round(math.degrees(DF.dial_angle() - a), 2),
                                                                             'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
        DF = DynFeed(G, tu, 0.7, 30, seed=5, pose=POSES[name])
        rows = burst(DF, 4, 1.0 / rate, shake=(SHAKE['a_m_s2'], 15.0))
        jolts[f'{name}_feeding_shaken_15hz'] = {**summarize(rows), 'in_chute_after': DF.in_chute(), 'escaped': len(DF.events)}
        print(f'jolt/shake {name}: {jolts[f"{name}_feeding"]["per_step"]} parked {[jolts[k]["balls_at_tyres"] for k in jolts if k.startswith(name + "_parked")]} ({time.time() - t_start:.0f} s)')
    res['jolt_and_vibration'] = jolts
    # 6. the timeline of one shot (feed part): command -> step settled -> ball clears the floor -> first touch
    lvl = base['level']
    res['shot_timeline_feed_ms'] = {'dial_step_settled': lvl['step_settled_ms'][0], 'ball_clears_floor_opening': lvl['cleared_ms_max'], 'first_touch_on_tyres_mean': lvl['latency_ms']['mean'],
                                    'first_touch_on_tyres_max': lvl['latency_ms']['max'],
                                    'note': 'from the step command; the launch adds ~4.8 ms in the nip and ~7 ms down the bore (launch3d.json, flight.json)'}
    # verdict
    all_steps = [v for v in base.values()] + list(rates.values()) + list(slews.values()) + [v for k, v in jolts.items() if 'feeding' in k]
    steps_total = sum(v['steps'] for v in all_steps)
    fed_total = sum(v['fed'] for v in all_steps)
    res['verdict'] = {'doubles': sum(v['doubles'] for v in all_steps), 'misses': sum(v['misses'] for v in all_steps), 'stuck_in_chute': sum(len(v['in_chute_after']) for v in all_steps),
                      'parked_leaks': sum(v['balls_at_tyres'] for k, v in jolts.items() if 'parked' in k), 'escaped': sum(v['escaped'] for v in all_steps),
                      'steps': steps_total, 'fed': fed_total, 'hopper_delivery_fraction': round(fed_total / max(1, steps_total), 3),
                      'latency_ms_max': max(v['latency_ms']['max'] or 0 for v in all_steps), 'step_settled_ms_nominal': lvl['step_settled_ms'][0],
                      # the rate the dial and chute allow: no doubles, nothing left in the hole or chute, and the balls still coming
                      # (above ~5/s the spoke carries the ball over the hole: few or none drop); empty steps at low rates are the hopper's delivery
                      'max_clean_stepping_rate_hz': max((float(k.split('_')[0]) for k, v in rates.items() if v['doubles'] == 0 and not v['in_chute_after'] and v['fed'] >= 0.6 * v['steps']), default=None),
                      'delivery_by_rate': {k: round(v['fed'] / v['steps'], 2) for k, v in rates.items()},
                      'doubles_by_rate': {k: v['doubles'] for k, v in rates.items()},
                      'continuous_clean_rpm': [k for k, v in cont.items() if v['balls'] == round(v['pockets_passed']) and not v['in_chute_after']],
                      'continuous_note': 'with the exit a ball + 1.5 mm hole, a pocket is over it for only +-1.2 deg of travel: continuous rotation drops nothing at any rpm tried; stepping only'}
    frames = res.pop('_video_frames', None)
    (OUT / 'feed_dyn.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    print('verdict', res['verdict'])
    # plots: the dial step (angle, speed, torque) and the latency histogram
    fig, ax = plt.subplots(1, 3, figsize=(15, 4), dpi=130)
    DF = DynFeed(G, tu, 0.7, 30, seed=1, pose=POSES['level'])
    t0 = DF.d.time
    rows = burst(DF, 2, 1.0 / rate)
    log = np.array([(t - t0, th, om, c) for t, th, om, c in DF.dial_log if t >= t0])
    ax[0].plot(log[:, 0] * 1000, np.degrees(log[:, 1] - log[0, 1]), label='dial angle (deg)')
    ax[0].plot(log[:, 0] * 1000, log[:, 2] * 60 / (2 * math.pi) / 10, label='dial speed (rpm / 10)')
    ax[0].plot(log[:, 0] * 1000, log[:, 3] * 50, label='motor torque (N m x 50)')
    for e in DF.entries:
        ax[0].axvline((e['t'] - t0) * 1000, color='#c2410c', ls=':', lw=1)
    ax[0].set_xlim(0, 700)
    ax[0].set_xlabel('ms from the step command (dotted: a ball touches the tyres)')
    ax[0].set_title(f"STS3215 stepping the dial 45 deg ({SERVO['goal_speed_rad_s']:.1f} rad/s goal, {int(SERVO['torque_cap'] * 100)} % torque limit)", fontsize=9)
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    lat_all = [l for r in base_rows for l in r['latency_ms']]
    ax[1].hist(lat_all, bins=12, color='#2563eb', alpha=0.8)
    ax[1].set_xlabel('ms from the step command to first touch')
    ax[1].set_title(f'shot latency (feed part), {len(lat_all)} balls at 3/s, all poses', fontsize=9)
    ks = list(rates)
    ax[2].bar(range(len(ks)), [rates[k]['achieved_rate_hz'] for k in ks], color=['#15803d' if rates[k]['misses'] == 0 and rates[k]['doubles'] == 0 and not rates[k]['in_chute_after'] else '#c2410c' for k in ks])
    ax[2].set_xticks(range(len(ks)))
    ax[2].set_xticklabels([k.replace('_per_s', '/s cmd') for k in ks], fontsize=7)
    ax[2].set_ylabel('achieved steps per second')
    ax[2].set_title('stepping rate: green = every step fed one ball, nothing stuck', fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / 'feed_dyn.png')
    plt.close(fig)
    if video and frames:
        write_video(frames[0], OUT / 'feed_dyn.mp4', f'feeding at 3/s while panning at {frames[2]:g} deg/s, tilt -25')
    return res


def write_video(DF: DynFeed, path: Path, caption=''):
    import mujoco
    renderer = mujoco.Renderer(DF.m, 540, 960)
    cam = mujoco.MjvCamera()
    cam.lookat[:] = (0.02, 0, 0.03)
    cam.distance, cam.azimuth, cam.elevation = 0.3, -60, -30
    qpos0 = DF.d.qpos.copy()
    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '960x540', '-r', '25', '-i', '-',
                             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '26', str(path)], stdin=subprocess.PIPE)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    keep = (0, len(DF.frames) // 3, 2 * len(DF.frames) // 3, len(DF.frames) - 1)
    for i, q in enumerate(DF.frames):
        DF.d.qpos[:] = q
        mujoco.mj_forward(DF.m, DF.d)
        renderer.update_scene(DF.d, cam)
        img = renderer.render()
        proc.stdin.write(img.tobytes())
        if i in keep:
            plt.imsave(path.with_name(f'{path.stem}-frame-{i:04d}.png'), img)
    proc.stdin.close()
    proc.wait()
    DF.d.qpos[:] = qpos0
    renderer.close()
    print('video', path, caption, len(DF.frames), 'frames')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--video', action='store_true')
    a = ap.parse_args()
    study(quick=a.quick, video=a.video)
