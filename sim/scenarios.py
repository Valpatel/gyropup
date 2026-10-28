"""Scenarios: what the robot is asked to do, on what ground, with what pushes; and how each run is scored.

Each scenario has terrain (extra geoms added to the model), a command schedule, optional pushes and a pass rule.
A run records:
- pass/fail and why, balance quality (pendulum angle), distance and speed tracking;
- per motor: peak torque against its rated and peak torque, time at the torque–speed limit, energy;
- per link: the largest force and moment it carried (the load cases for the stress step);
- frames at 30 fps for the 3D replay, and optionally an MP4.
"""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import replace, dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import mujoco
import numpy as np

from sim.controller import Command, Controller, Robot, place_standing
from sim.turret import HOPPER, Target, TurretController, balls_xml, fluid_option, targets_xml

FPS = 30


@dataclass
class Push:
    t: float
    impulse_ns: float          # along the robot's heading (negative = backwards); per kg of robot unless absolute
    duration: float = 0.1
    height_m: float = 0.15     # above the hip axis, in the base frame
    absolute: bool = False     # True: impulse_ns is in N·s (a shot's recoil), not per kg
    lateral: bool = False      # True: sideways (to the robot's left), not along its heading


@dataclass
class Scenario:
    name: str
    title: str
    seconds: float
    command: Callable[[float], Command]
    terrain: str = ''
    pushes: List[Push] = field(default_factory=list)
    start_height: float = 0.6
    must_reach_x: Optional[float] = None   # pass needs the axle to get this far forward (m)
    hold_from: Optional[float] = None      # pass needs |theta| small after this time
    targets: List[Target] = field(default_factory=list)   # foam targets the turret engages
    balls: int = 0                         # foam-ball bodies loaded in the hopper
    min_hit_rate: Optional[float] = None   # pass needs at least this share of shots on target
    motors_off_at: Optional[float] = None  # every motor stops at this time (e-stop, a flat battery): a fall test
    expect_fall: bool = False              # a fall is the point of the test: pass on how it lands, not on staying up
    start_drop_m: float = 0.0              # start this far above the ground (a landing test)
    max_body_impact_n: Optional[float] = None   # pass needs the body's peak contact force below this
    max_roll_deg: Optional[float] = None   # pass needs the body this level (rms roll) inside roll_window
    roll_window: tuple = (0.0, 0.0)        # seconds


def ramp(deg, x0=0.8, length=2.0):
    t = math.radians(deg)
    hl = length / 2
    cx, cz = x0 + hl * math.cos(t), hl * math.sin(t)
    nx, nz = -math.sin(t), math.cos(t)
    q = (math.cos(-t / 2), 0, math.sin(-t / 2), 0)
    top_z = 2 * cz
    return (f'<geom name="ramp" type="box" size="{hl} 1.5 0.05" pos="{cx - 0.05 * nx} 0 {cz - 0.05 * nz}" '
            f'quat="{q[0]} {q[1]} {q[2]} {q[3]}" rgba=".55 .5 .42 1" friction="0.9 0.01 0.001"/>'
            f'<geom name="plateau" type="box" size="1.5 1.5 {top_z / 2}" pos="{x0 + length * math.cos(t) + 1.5} 0 {top_z / 2}" rgba=".55 .5 .42 1"/>')


def platform(height, edge_x):
    """A raised floor the robot starts on, ending at edge_x (a kerb to drive off)."""
    return f'<geom name="platform" type="box" size="1.5 1.5 {height / 2}" pos="{edge_x - 1.5} 0 {height / 2}" rgba=".6 .6 .62 1"/>'


def curb(height, x0=0.8):
    return f'<geom name="curb" type="box" size="1.5 1.5 {height / 2}" pos="{x0 + 1.5} 0 {height / 2}" rgba=".6 .6 .62 1"/>'


def side_plank(height, x0=0.8, length=2.0):
    """A plank under the robot's LEFT wheel only (it starts 50 mm left of the centre line): one wheel rides high."""
    return (f'<geom name="side_plank" type="box" size="{length / 2} 0.725 {height / 2}" pos="{x0 + length / 2} 0.775 {height / 2}" '
            f'rgba=".6 .6 .62 1"/>')


def ramp_profile(t, start, ramp_s, v):
    return 0.0 if t < start else min(v, v * (t - start) / ramp_s)


# Knock-down targets at knee height, within range: the barrel never points upwards (kid-safety rule), and a 21.3 m/s
# foam ball fired level from a ~0.6-0.7 m muzzle is down to 0.3 m at about 4.7-5.3 m. Gyropup stands tall to shoot.
# Each target takes up to 5 balls; once its plate flips, the turret moves on.
TARGETS = [Target('target_a', (3.0, 1.3, 0.30), 5, (2.0, 16.0)), Target('target_b', (3.4, 0.2, 0.30), 5, (2.0, 16.0)),
           Target('target_c', (3.2, -1.0, 0.30), 5, (2.0, 16.0)), Target('target_d', (3.8, -2.0, 0.30), 5, (9.0, 16.0)),
           Target('target_e', (4.2, 0.9, 0.30), 5, (9.0, 16.0))]

SCENARIOS = {
    'stand': Scenario('stand', 'Stand and balance', 8.0, lambda t: Command(height=0.6), hold_from=2.0),
    'squat': Scenario('squat', 'Squat sweep: stand tall, crouch deep, stand again', 10.0,
                      lambda t: Command(height=0.95 if t < 2 else 0.1 if t < 6 else 0.95)),
    'push': Scenario('push', 'Push recovery, front and back', 9.0, lambda t: Command(height=0.6),
                     pushes=[Push(2.0, 0.35), Push(5.5, -0.35)], hold_from=8.0),
    'drive': Scenario('drive', 'Drive course: accelerate, turn, stop, reverse', 14.0,
                      lambda t: Command(height=0.6,
                                        speed=(ramp_profile(t, 1, 2, 1.0) if t < 8 else max(0.0, 1.0 - (t - 8) / 2) if t < 10.5 else -0.4 if t < 12.5 else 0.0),
                                        yaw_rate=0.8 if 4.5 < t < 7.5 else 0.0)),
    'slope': Scenario('slope', 'Climb a 10° ramp and hold on it', 12.0,
                      lambda t: Command(height=0.6, speed=ramp_profile(t, 1, 1.5, 0.5) if t < 7 else 0.0),
                      terrain=ramp(10), must_reach_x=1.6, hold_from=10.0),
    'targets': Scenario('targets', 'Knock-down range: five foam targets, standing then driving', 16.0,
                        lambda t: Command(height=0.6 if t < 1.5 else 0.9, speed=ramp_profile(t, 9, 1.0, 0.35) if t < 12.5 else 0.0),
                        targets=TARGETS, balls=HOPPER, min_hit_rate=0.4),
    'look': Scenario('look', 'Look up: lean back 15° on the legs, hold, then look ahead again', 9.0,
                     lambda t: Command(height=0.7, look_up=0.26 if 2 < t < 6 else 0.0), hold_from=8.0),
    # falls, drops and landings (review A5): how the body lands matters, and the lidar under the waist must not touch
    'fall_front': Scenario('fall_front', 'Motors cut while standing, nudged forwards: how it lands', 4.0, lambda t: Command(height=0.6),
                           pushes=[Push(1.0, 0.15)], motors_off_at=1.0, expect_fall=True, max_body_impact_n=3000.0),
    'fall_back': Scenario('fall_back', 'Motors cut while standing, nudged backwards: how it lands', 4.0, lambda t: Command(height=0.6),
                          pushes=[Push(1.0, -0.15)], motors_off_at=1.0, expect_fall=True, max_body_impact_n=3000.0),
    'fall_side': Scenario('fall_side', 'Motors cut while standing, pushed sideways: how it lands', 4.0, lambda t: Command(height=0.6),
                          pushes=[Push(1.0, 0.25, lateral=True)], motors_off_at=1.0, expect_fall=True, max_body_impact_n=3000.0),
    'kerb_drop': Scenario('kerb_drop', 'Drive off a 50 mm kerb at 0.8 m/s', 7.0,
                          lambda t: Command(height=0.6, speed=ramp_profile(t, 1, 1.0, 0.8) if t < 5 else 0.0),
                          terrain=platform(0.05, 0.6), start_drop_m=0.05, hold_from=6.5),
    'landing': Scenario('landing', 'Dropped from 80 mm while balancing: land and stay up', 5.0, lambda t: Command(height=0.6),
                        start_drop_m=0.08, hold_from=4.5),
    'side_kerb': Scenario('side_kerb', 'One wheel up a 30 mm plank, along it and off: the body stays level', 11.0,
                          lambda t: Command(height=0.6, speed=ramp_profile(t, 1.0, 1.0, 0.4) if t < 9.0 else 0.0),
                          terrain=side_plank(0.03), max_roll_deg=2.5, roll_window=(4.5, 7.0)),
    'curb': Scenario('curb', 'Drive up a 25 mm kerb', 9.0,
                     lambda t: Command(height=0.6, speed=ramp_profile(t, 1, 1.0, 0.6) if t < 6 else 0.0),
                     terrain=curb(0.025), must_reach_x=1.5),
}


def recoil_scenario(info: dict) -> Scenario:
    """Empty the head payload's magazine: bursts while standing, then while driving. Each shot pushes backwards at the
    payload's height with its recoil impulse."""
    hp = info.get('head_payload') or {}
    imp, mag = hp.get('recoil_ns_per_shot', 0.05), hp.get('magazine_shots', 24)
    burst, rate = hp.get('burst_shots', 8), hp.get('burst_rate_hz', 10)
    h = info.get('body_top_m', 0.17) + hp.get('com_above_top_mm', 120) / 1000
    shots, t = [], 2.0
    for k in range(mag):
        shots.append(Push(t, -imp, 0.004, h, True))
        t += 1 / rate if (k + 1) % burst else 1.5          # a pause between bursts
    return Scenario('recoil', f'Recoil: empty a {mag}-shot magazine in bursts of {burst}, standing then driving', t + 2.0,
                    lambda tt: Command(height=0.6, speed=ramp_profile(tt, 4.5, 1, 0.6) if tt < t else 0.0), pushes=shots)


def with_terrain(xml: str, terrain: str) -> str:
    return xml.replace('</worldbody>', terrain + '</worldbody>', 1) if terrain else xml


class Video:
    def __init__(self, model, path: Path, width=640, height=360):
        self.r = mujoco.Renderer(model, height, width)
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        self.cam.trackbodyid = model.body('base').id
        self.cam.distance, self.cam.elevation, self.cam.azimuth = 2.2, -12, 120
        self.proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                                      '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '28', str(path)],
                                     stdin=subprocess.PIPE)

    def frame(self, data):
        self.r.update_scene(data, self.cam)
        self.proc.stdin.write(self.r.render().tobytes())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()
        self.r.close()


# Shooting body language (expressive, not physics: a 1.83 g ball at 21.3 m/s is a 0.039 N·s kick, nothing on a 17 kg robot,
# and that real impulse is applied separately by the turret). While the laser is on Gyropup braces, a little lower;
# each shot it dips and rocks back on its legs and springs up again, like a pup flinching at its own bark.
BRACE = 0.10          # height fraction lower while aiming
FLINCH_DIP = 0.10     # height fraction dip per shot
FLINCH_KICK = 0.14    # rad rock back per shot
FLINCH_TAU = 0.06     # s decay


FLINCH_RISE = 0.04    # s: the flinch eases in (a step in the setpoint makes a torque spike no real motion needs)


def shooting_stance(cmd: Command, turret, t: float) -> Command:
    since = t - turret.last_shot
    rise = 0.5 - 0.5 * math.cos(math.pi * min(1.0, since / FLINCH_RISE)) if since >= 0 else 0.0
    f = rise * math.exp(-max(0.0, since - FLINCH_RISE) / FLINCH_TAU) if 0 <= since < FLINCH_RISE + 6 * FLINCH_TAU else 0.0
    return replace(cmd, height=cmd.height - (BRACE if turret.laser else 0.0) - turret.duck, dip=cmd.dip - FLINCH_DIP * f,
                   kick=cmd.kick + FLINCH_KICK * f)


def run(xml_path: Path, info: dict, sc: Scenario, video: Optional[Path] = None, noise=0.0, delay_steps=0) -> dict:
    extra = sc.terrain + (targets_xml(sc.targets) if sc.targets else '') + (balls_xml(sc.balls) if sc.balls else '')
    xml = with_terrain(Path(xml_path).read_text(), extra)
    if sc.balls:
        xml = fluid_option(xml)
    if 'meshdir=' not in xml.split('<compiler', 1)[-1].split('>', 1)[0]:          # v2 names its own mesh folder
        xml = xml.replace('<compiler ', f'<compiler meshdir="{Path(xml_path).parent}" ', 1)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    if info.get('kind') == 'fivebar':                 # Gyropup v2 (sim/robot_v2.py): five-bar legs, their controller
        from sim.controller_v2 import ControllerV2 as Ctl, RobotV2 as Rob, place_standing as place
    else:
        Rob, Ctl, place = Robot, Controller, place_standing
    rb = Rob(model, info)
    place(rb, data, sc.start_height)
    if sc.start_drop_m:
        data.qpos[2] += sc.start_drop_m
        mujoco.mj_forward(model, data)
    lidar_geom = next((g for g in range(model.ngeom) if model.geom(g).name == 'lidar'), None)
    base_geoms = {g for g in range(model.ngeom) if model.geom_bodyid[g] == rb.base}
    # the battery bay's crush pads (sim/robot_v2.py, issue #19): bodies of their own on slide joints; what they pass to the
    # body is their floor contact (a pad is ~35 g), summed over all of them at each step: the body's impact through the pads
    pad_geoms = {g for g in range(model.ngeom) if model.body(model.geom_bodyid[g]).name.startswith('pad_')}
    # a printed elastomer lattice gives back only part of what it stores (its hysteresis): unloading, a pad's spring pushes
    # with unload_ratio x k x (the joint carries k and c; the rest is taken off here, smoothly in the pad's speed)
    pad_dofs = [(int(model.jnt_qposadr[j]), int(model.jnt_dofadr[j]), float(model.jnt_stiffness[j])) for j in range(model.njnt)
                if model.joint(j).name.startswith('pad_')]
    unload = float((info.get('pads') or {}).get('unload_ratio', 1.0))
    peak_body_n, lidar_touch, force6 = 0.0, None, np.zeros(6)
    peak_pads_n, peak_pad_n = 0.0, 0.0
    ctl = Ctl(rb, noise=noise, delay_steps=delay_steps)
    ctl.height = sc.start_height                 # start from the pose the robot is placed in
    turret = TurretController(model, data, list(sc.targets), tilt_max=(info.get('turret') or {}).get('tilt_max_rad'))
    dt = model.opt.timestep
    steps = int(sc.seconds / dt)
    frame_every = max(1, int(round(1 / (FPS * dt))))
    names = list(rb.act)
    peak_tau = {n: 0.0 for n in names}
    energy = {n: 0.0 for n in names}
    thetas, speed_err, frames, rolls = [], [], [], []
    robot_joint_bodies = [i for i in range(1, model.nbody) if model.body_rootid[i] == model.body('base').id and model.body_jntnum[i] > 0
                          and model.jnt_type[model.body_jntadr[i]] != mujoco.mjtJoint.mjJNT_FREE]
    link_load = {model.body(i).name: {'force_n': 0.0, 'moment_nm': 0.0} for i in robot_joint_bodies}
    fell_at, tipping_at, max_theta, x_max, v_peak = None, None, 0.0, -1e9, 0.0
    min_base_z = 1e9
    vid = Video(model, video) if video else None
    # static props (terrain, targets) as world-frame primitives, so the 3D page can draw exactly what was simulated
    robot_set = set(rb.bodies)
    props, movers = [], []
    plate_bodies = {model.body(i).name: i for i in range(model.nbody) if model.body(i).name.endswith('_plate')}
    for name, bi in plate_bodies.items():           # target plates swing on hinges: the page animates them
        jid = model.body_jntadr[bi]
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, data.xmat[bi])
        axis = data.xaxis[jid] if jid >= 0 else np.array([0, 1, 0])
        movers.append({'body': name, 'qpos': int(model.jnt_qposadr[jid]), 'pivot': [round(float(v), 4) for v in data.xanchor[jid]],
                       'axis': [round(float(v), 4) for v in axis],
                       'geoms': [model.geom(g).name for g in range(model.body_geomadr[bi], model.body_geomadr[bi] + model.body_geomnum[bi])]})
    for gi in range(model.ngeom):
        b = model.geom_bodyid[gi]
        if b in robot_set or model.body(b).name.startswith('ball_') or model.geom_type[gi] == mujoco.mjtGeom.mjGEOM_PLANE:
            continue
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, data.geom_xmat[gi])
        props.append({'name': model.geom(gi).name, 'type': int(model.geom_type[gi]), 'size': [round(float(v), 4) for v in model.geom_size[gi]],
                      'pos': [round(float(v), 4) for v in data.geom_xpos[gi]], 'quat': [round(float(v), 5) for v in q],
                      'rgba': [round(float(v), 3) for v in model.geom_rgba[gi]]})
    pushes = list(sc.pushes)
    base = rb.base
    for k in range(steps):
        t = data.time
        cmd = sc.command(t)
        data.xfrc_applied[base] = 0
        for p in pushes:
            if p.t <= t < p.t + p.duration:
                fwd = ctl.heading(data)
                if p.lateral:
                    fwd = np.array([-fwd[1], fwd[0], 0.0])
                F = fwd * ((p.impulse_ns if p.absolute else p.impulse_ns * rb.total_mass) / p.duration)
                data.xfrc_applied[base, :3] = F
                R = data.xmat[base].reshape(3, 3)
                arm = R @ np.array([0, 0, p.height_m])
                data.xfrc_applied[base, 3:] = np.cross(arm, F)
        if turret.has and sc.targets:
            cmd = shooting_stance(cmd, turret, t)
        st = ctl.control(data, cmd, dt)
        if sc.motors_off_at is not None and t >= sc.motors_off_at:
            data.ctrl[:] = 0.0                       # power cut: every motor goes limp
        for qa, va, kp in pad_dofs:
            q, v = float(data.qpos[qa]), float(data.qvel[va])
            data.qfrc_applied[va] = (1.0 - unload) * kp * max(q, 0.0) * 0.5 * (1.0 - math.tanh(v / 0.01))
        turret.step(t, dt)
        mujoco.mj_step(model, data)
        pads_now, each_pad = 0.0, {}
        for ci in range(data.ncon):                  # what the body (and the lidar) hits
            c = data.contact[ci]
            if (c.geom1 in pad_geoms) ^ (c.geom2 in pad_geoms):
                pg, other = (c.geom1, c.geom2) if c.geom1 in pad_geoms else (c.geom2, c.geom1)
                if model.geom_bodyid[other] not in robot_set:
                    mujoco.mj_contactForce(model, data, ci, force6)
                    pads_now += abs(float(force6[0]))
                    each_pad[pg] = each_pad.get(pg, 0.0) + abs(float(force6[0]))
            if c.geom1 in base_geoms or c.geom2 in base_geoms:
                other = c.geom2 if c.geom1 in base_geoms else c.geom1
                if model.geom_bodyid[other] in robot_set:
                    continue
                mujoco.mj_contactForce(model, data, ci, force6)
                peak_body_n = max(peak_body_n, abs(float(force6[0])))
                if lidar_geom is not None and lidar_touch is None and lidar_geom in (c.geom1, c.geom2):
                    lidar_touch = round(float(data.time), 3)
        if pads_now:
            peak_pads_n = max(peak_pads_n, pads_now)
            peak_pad_n = max(peak_pad_n, max(each_pad.values()))
            peak_body_n = max(peak_body_n, pads_now)
        th = st['theta']
        thetas.append(th)
        rolls.append((t, st.get('roll', 0.0)))
        max_theta = max(max_theta, abs(th))
        x_max = max(x_max, st['x'])
        speed_err.append(st['v'] - st['v_cmd'])
        v_peak = max(v_peak, abs(st['v']))
        for n in names:
            tau = data.actuator_force[rb.act[n]]
            peak_tau[n] = max(peak_tau[n], abs(tau))
            energy[n] += abs(tau * data.actuator_velocity[rb.act[n]]) * dt
        if k % 2 == 0:
            # the load each robot link takes from its parent, at its joint: MuJoCo's cfrc_int is a spatial force about
            # the root's centre of mass, so move the moment to the joint anchor, then express both in the link's frame
            mujoco.mj_rnePostConstraint(model, data)
            for i in robot_joint_bodies:
                f = data.cfrc_int[i]
                F = f[3:]
                p = data.xanchor[model.body_jntadr[i]]
                Mj = f[:3] + np.cross(data.subtree_com[model.body_rootid[i]] - p, F)
                Rb = data.xmat[i].reshape(3, 3)
                ll = link_load[model.body(i).name]
                fn, mn = float(np.linalg.norm(F)), float(np.linalg.norm(Mj))
                if fn > ll['force_n']:
                    ll.update(force_n=fn, force_at_s=round(float(data.time), 3), force_vec_body=(Rb.T @ F).round(1).tolist(),
                              moment_with_force_body=(Rb.T @ Mj).round(2).tolist())
                if mn > ll['moment_nm']:
                    ll.update(moment_nm=mn, moment_at_s=round(float(data.time), 3), moment_vec_body=(Rb.T @ Mj).round(2).tolist(),
                              force_with_moment_body=(Rb.T @ F).round(1).tolist())
        base_z = data.xpos[base][2]
        min_base_z = min(min_base_z, base_z)
        if tipping_at is None and abs(th) > 0.35:
            tipping_at = t                         # past saving, usually: the moment for an "oh no"
        if fell_at is None and (abs(th) > 0.9 or base_z < rb.r + 0.06):
            fell_at = t
        if k % frame_every == 0:
            frames.append([round(float(v), 4) for v in data.qpos])
            if vid:
                vid.frame(data)
        if fell_at is not None and t > fell_at + 1.0:
            break
    if vid:
        vid.close()

    th = np.array(thetas)
    reasons = []
    if fell_at is not None and not sc.expect_fall:
        reasons.append(f'fell at {fell_at:.1f} s')
    if lidar_touch is not None:
        reasons.append(f'the lidar hit the ground at {lidar_touch:.2f} s')
    if sc.max_body_impact_n is not None and peak_body_n > sc.max_body_impact_n:
        reasons.append(f'body impact {peak_body_n:.0f} N (limit {sc.max_body_impact_n:.0f} N)')
    tsum = turret.summary() if turret.has else None
    if sc.min_hit_rate is not None and tsum and tsum['hit_rate'] < sc.min_hit_rate:
        reasons.append(f"hit {tsum['hits']} of {tsum['shots']} shots ({tsum['hit_rate']:.0%}), needs {sc.min_hit_rate:.0%}")
    if sc.min_hit_rate is not None and tsum and tsum.get('targets') and tsum['knocked_down'] < math.ceil(0.6 * tsum['targets']):
        reasons.append(f"knocked down {tsum['knocked_down']} of {tsum['targets']} targets, needs {math.ceil(0.6 * tsum['targets'])}")
    clear = min_base_z + (info['layout_mm']['trayBottom'] - 80) / 1000      # the lowest part: the lidar under the waist
    if info['layout_mm'].get('lidarMount') == 'under' and clear < 0.01 and lidar_geom is None:
        reasons.append(f'the lidar came within {clear * 1000:.0f} mm of the ground')
    rw = [r for (tt, r) in rolls if sc.roll_window[0] <= tt <= sc.roll_window[1]]
    roll_rms = math.degrees(math.sqrt(sum(r * r for r in rw) / len(rw))) if rw else None
    if sc.max_roll_deg is not None and fell_at is None and roll_rms is not None and roll_rms > sc.max_roll_deg:
        reasons.append(f'body not level on the plank: roll {roll_rms:.1f}° rms (limit {sc.max_roll_deg}°)')
    if sc.must_reach_x is not None and x_max < sc.must_reach_x:
        reasons.append(f'only reached {x_max:.2f} m of {sc.must_reach_x} m')
    if sc.hold_from is not None and fell_at is None:
        tail = th[int(sc.hold_from / dt):]
        if len(tail) and np.max(np.abs(tail)) > math.radians(5):
            reasons.append(f'still swinging {math.degrees(np.max(np.abs(tail))):.1f}° after {sc.hold_from} s')
    leg_rated = info['leg_actuator']['rated_nm']
    motors = {}
    for n in names:
        peak, rated = rb.peak_for(n), rb.rated_for(n)
        motors[n] = {'peak_torque_nm': round(peak_tau[n], 2), 'of_peak': round(peak_tau[n] / peak, 3), 'of_rated': round(peak_tau[n] / rated, 3),
                     'saturated_s': round(ctl.saturation[n] * dt, 3), 'energy_j': round(energy[n], 1)}
    return {
        'scenario': sc.name, 'title': sc.title, 'seconds': round(float(data.time), 3), 'pass': not reasons, 'reasons': reasons,
        'max_theta_deg': round(math.degrees(max_theta), 2),
        'max_roll_deg': round(math.degrees(max(abs(r) for _, r in rolls)), 2) if rolls else None,
        'roll_rms_window_deg': round(roll_rms, 2) if roll_rms is not None else None, 'theta_rms_deg': round(math.degrees(float(np.sqrt(np.mean(th ** 2)))), 3),
        'speed_rms_mps': round(float(np.sqrt(np.mean(np.square(speed_err)))), 3), 'x_max_m': round(x_max, 3),
        'top_speed_mps': round(v_peak, 2), 'speed_limit_mps': round(ctl.top_speed, 2),
        'motors': motors, 'energy_j': round(sum(energy.values()), 1), 'link_loads': {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in link_load.items()},
        'lqr': {k: round(float(v), 4) for k, v in ctl.lqr_info.items()},
        'frames': {'fps': FPS, 'qpos': frames, 'joint_order': ['free(7)'] + [model.joint(j).name for j in range(1, model.njnt)]},
        'terrain': sc.terrain, 'video': video.name if video else None,
        'events': [{'t': round(p.t, 3), 'type': 'shot'} for p in sc.pushes if p.absolute] + (turret.events if turret.has else [])
                  + [{'t': round(p.t, 3), 'type': 'push'} for p in sc.pushes if not p.absolute]
                  + ([{'t': round(min(tipping_at or fell_at, fell_at), 3), 'type': 'fall'}] if fell_at is not None else []),
        'fell_at': round(fell_at, 3) if fell_at is not None else None,
        'lidar_clearance_mm': round(clear * 1000, 1), 'body_impact_peak_n': round(peak_body_n), 'pads_peak_n': round(peak_pads_n), 'pad_each_peak_n': round(peak_pad_n), 'lidar_touched_at': lidar_touch,
        'turret': tsum,
        'qpos_layout': {model.joint(j).name: int(model.jnt_qposadr[j]) for j in range(model.njnt)},
        'props': props,
        'movers': movers,
        'physical_test': False,
    }
