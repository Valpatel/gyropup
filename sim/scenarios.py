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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import mujoco
import numpy as np

from sim.controller import Command, Controller, Robot, place_standing

FPS = 30


@dataclass
class Push:
    t: float
    impulse_ns: float          # along the robot's heading (negative = backwards); per kg of robot unless absolute
    duration: float = 0.1
    height_m: float = 0.15     # above the hip axis, in the base frame
    absolute: bool = False     # True: impulse_ns is in N·s (a dart's recoil), not per kg


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


def curb(height, x0=0.8):
    return f'<geom name="curb" type="box" size="1.5 1.5 {height / 2}" pos="{x0 + 1.5} 0 {height / 2}" rgba=".6 .6 .62 1"/>'


def ramp_profile(t, start, ramp_s, v):
    return 0.0 if t < start else min(v, v * (t - start) / ramp_s)


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


def run(xml_path: Path, info: dict, sc: Scenario, video: Optional[Path] = None, noise=0.0, delay_steps=0) -> dict:
    xml = with_terrain(Path(xml_path).read_text(), sc.terrain)
    model = mujoco.MjModel.from_xml_string(xml.replace('<compiler ', f'<compiler meshdir="{Path(xml_path).parent}" ', 1))
    data = mujoco.MjData(model)
    rb = Robot(model, info)
    place_standing(rb, data, sc.start_height)
    ctl = Controller(rb, noise=noise, delay_steps=delay_steps)
    ctl.height = sc.start_height                 # start from the pose the robot is placed in
    dt = model.opt.timestep
    steps = int(sc.seconds / dt)
    frame_every = max(1, int(round(1 / (FPS * dt))))
    names = list(rb.act)
    peak_tau = {n: 0.0 for n in names}
    energy = {n: 0.0 for n in names}
    thetas, speed_err, frames = [], [], []
    link_load = {model.body(i).name: {'force_n': 0.0, 'moment_nm': 0.0} for i in range(1, model.nbody)}
    fell_at, max_theta, x_max, v_peak = None, 0.0, -1e9, 0.0
    vid = Video(model, video) if video else None
    pushes = list(sc.pushes)
    base = rb.base
    for k in range(steps):
        t = data.time
        cmd = sc.command(t)
        data.xfrc_applied[base] = 0
        for p in pushes:
            if p.t <= t < p.t + p.duration:
                fwd = ctl.heading(data)
                F = fwd * ((p.impulse_ns if p.absolute else p.impulse_ns * rb.total_mass) / p.duration)
                data.xfrc_applied[base, :3] = F
                R = data.xmat[base].reshape(3, 3)
                arm = R @ np.array([0, 0, p.height_m])
                data.xfrc_applied[base, 3:] = np.cross(arm, F)
        st = ctl.control(data, cmd, dt)
        mujoco.mj_step(model, data)
        th = st['theta']
        thetas.append(th)
        max_theta = max(max_theta, abs(th))
        x_max = max(x_max, st['x'])
        speed_err.append(st['v'] - st['v_cmd'])
        v_peak = max(v_peak, abs(st['v']))
        for n in names:
            tau = data.actuator_force[rb.act[n]]
            peak_tau[n] = max(peak_tau[n], abs(tau))
            energy[n] += abs(tau * data.qvel[rb.vadr[n]]) * dt
        if k % 10 == 0:
            mujoco.mj_rnePostConstraint(model, data)
            for i in range(1, model.nbody):
                f = data.cfrc_int[i]
                ll = link_load[model.body(i).name]
                ll['moment_nm'] = max(ll['moment_nm'], float(np.linalg.norm(f[:3])))
                ll['force_n'] = max(ll['force_n'], float(np.linalg.norm(f[3:])))
        base_z = data.xpos[base][2]
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
    if fell_at is not None:
        reasons.append(f'fell at {fell_at:.1f} s')
    if sc.must_reach_x is not None and x_max < sc.must_reach_x:
        reasons.append(f'only reached {x_max:.2f} m of {sc.must_reach_x} m')
    if sc.hold_from is not None and fell_at is None:
        tail = th[int(sc.hold_from / dt):]
        if len(tail) and np.max(np.abs(tail)) > math.radians(5):
            reasons.append(f'still swinging {math.degrees(np.max(np.abs(tail))):.1f}° after {sc.hold_from} s')
    leg_rated = info['leg_actuator']['rated_nm']
    motors = {}
    for n in names:
        is_wheel = n.startswith('wheel')
        peak = rb.wheel_peak if is_wheel else rb.leg_peak
        rated = info['wheel_motor' if is_wheel else 'leg_actuator']['rated_nm']
        motors[n] = {'peak_torque_nm': round(peak_tau[n], 2), 'of_peak': round(peak_tau[n] / peak, 3), 'of_rated': round(peak_tau[n] / rated, 3),
                     'saturated_s': round(ctl.saturation[n] * dt, 3), 'energy_j': round(energy[n], 1)}
    return {
        'scenario': sc.name, 'title': sc.title, 'seconds': round(float(data.time), 3), 'pass': not reasons, 'reasons': reasons,
        'max_theta_deg': round(math.degrees(max_theta), 2), 'theta_rms_deg': round(math.degrees(float(np.sqrt(np.mean(th ** 2)))), 3),
        'speed_rms_mps': round(float(np.sqrt(np.mean(np.square(speed_err)))), 3), 'x_max_m': round(x_max, 3),
        'top_speed_mps': round(v_peak, 2), 'speed_limit_mps': round(ctl.top_speed, 2),
        'motors': motors, 'energy_j': round(sum(energy.values()), 1), 'link_loads': {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in link_load.items()},
        'lqr': {k: round(float(v), 4) for k, v in ctl.lqr_info.items()},
        'frames': {'fps': FPS, 'qpos': frames, 'joint_order': ['free(7)'] + [model.joint(j).name for j in range(1, model.njnt)]},
        'terrain': sc.terrain, 'video': video.name if video else None,
        'physical_test': False,
    }
