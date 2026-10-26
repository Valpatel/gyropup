"""Sim-to-sim check: run the exported ONNX policy in plain CPU MuJoCo on the full generated model.

    cd rl && .venv/bin/python scripts/sim2sim.py [--video] [--delay-ms 10]

Differences from training, on purpose: the original robot.xml (1 ms timestep, turret joints present and held by
their own PD, the repo's floor), numpy actuator code instead of mjlab's, onnxruntime instead of torch, and a fixed
command latency. The DcMotor law is re-implemented exactly (PD, then the linear torque-speed clip). The same drive
course as scripts/play.py is used. Writes results/sim2sim_metrics.json (and results/sim2sim_drive.mp4 with --video).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import deque
from pathlib import Path

import mujoco
import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'scripts'))
from play import COURSE, SECONDS, command_at  # noqa: E402

LEGS = ('hip_l', 'knee_l', 'hip_r', 'knee_r')
WHEELS = ('wheel_l', 'wheel_r')


def dc_clip(tau, omega, peak, omega_max):
    top = np.minimum(peak * (1 - omega / omega_max), peak)
    bot = np.maximum(peak * (-1 - omega / omega_max), -peak)
    return np.clip(tau, bot, top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--onnx', type=Path, default=HERE / 'results/policy.onnx')
    ap.add_argument('--delay-ms', type=float, default=10.0)
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--tag', default='', help='suffix for the metrics file, e.g. a design name')
    a = ap.parse_args()
    meta = json.loads(a.onnx.with_suffix('.json').read_text())
    os.environ['GYROPUP_DESIGN'] = meta['design']
    from gyropup_rl import robot as rb
    g = rb.load(meta['design'])

    spec = mujoco.MjSpec.from_file(g.xml)
    spec.visual.global_.offwidth, spec.visual.global_.offheight = 1280, 720   # room for the 960x540 video
    m = spec.compile()
    d = mujoco.MjData(m)
    sess = ort.InferenceSession(str(a.onnx), providers=['CPUExecutionProvider'])
    qadr = {n: m.joint(n).qposadr[0] for n in LEGS + WHEELS + rb.TURRET_JOINTS}
    vadr = {n: m.joint(n).dofadr[0] for n in qadr}
    act_id = {n: m.actuator(n).id for n in qadr}
    base = m.body('base').id
    gyro = m.sensor('imu_gyro').adr[0]

    # initial state: the same standing pose as training
    mujoco.mj_resetData(m, d)
    d.qpos[0:3] = g.base_pos
    d.qpos[3:7] = g.base_quat
    for n in LEGS + WHEELS:
        d.qpos[qadr[n]] = g.joint_pos[n]
    mujoco.mj_forward(m, d)

    A = meta['actuators']
    kp, kd = A['leg']['kp'], A['leg']['kd']
    default = np.array(meta['default_leg_pos'])
    lay = {s['name']: s for s in meta['observation_layout']}
    dt = m.opt.timestep
    decim = int(round(1 / meta['policy_hz'] / dt))
    delay = int(round(a.delay_ms / 1000 / dt))
    last = np.zeros(6, dtype=np.float32)
    cur = (default.copy(), np.zeros(2))
    hist = deque([cur] * (delay + 1), maxlen=delay + 1)   # hist[0] = the target issued `delay` steps ago
    log = {k: [] for k in ('t', 'cmd_vx', 'cmd_wz', 'vx', 'wz', 'pitch')}
    fell_at = None

    vid = None
    if a.video:
        os.environ.setdefault('MUJOCO_GL', 'egl')
        W, H = 960, 540
        ren = mujoco.Renderer(m, H, W)
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        cam.trackbodyid = base
        cam.distance, cam.elevation, cam.azimuth = 2.4, -15, 135
        vid = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                                '-r', '50', '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast',
                                '-crf', '26', str(HERE / 'results/sim2sim_drive.mp4')], stdin=subprocess.PIPE)

    steps = int(SECONDS / dt)
    for k in range(steps):
        t = k * dt
        if k % decim == 0:
            _, vx_c, wz_c, _ = command_at(t)
            R = d.xmat[base].reshape(3, 3)
            obs = np.zeros(meta['onnx']['input_size'], dtype=np.float32)
            q = np.array([d.qpos[qadr[n]] for n in LEGS])
            qd = np.array([d.qvel[vadr[n]] for n in LEGS + WHEELS])
            parts = {'projected_gravity': R.T @ np.array([0, 0, -1.0]), 'base_ang_vel': d.sensordata[gyro:gyro + 3],
                     'leg_pos': q - default, 'joint_vel': qd, 'actions': last, 'command': np.array([vx_c, 0.0, wz_c])}
            for name, v in parts.items():
                s = lay[name]
                obs[s['start']:s['start'] + s['size']] = np.asarray(v) * s['scale']
            act = sess.run(None, {'obs': obs[None]})[0][0]
            last = act.astype(np.float32)
            cur = (default + meta['actions']['leg_scale'] * act[:4], meta['actions']['wheel_scale'] * act[4:])
            # log at the policy rate
            # body-frame velocities (mj_objectVelocity's "local" frame is the inertial principal-axis frame, which
            # the generated base's fullinertia rotates, so use the free joint and the gyro instead)
            v_b = R.T @ d.qvel[0:3]
            w_b = d.sensordata[gyro:gyro + 3]
            gb = R.T @ np.array([0, 0, -1.0])
            log['t'].append(t); log['cmd_vx'].append(vx_c); log['cmd_wz'].append(wz_c)
            log['vx'].append(float(v_b[0])); log['wz'].append(float(w_b[2]))
            log['pitch'].append(float(np.degrees(np.arctan2(gb[0], -gb[2]))))
            if fell_at is None and abs(log['pitch'][-1]) > 50:
                fell_at = t
            if vid is not None:
                ren.update_scene(d, cam)
                vid.stdin.write(ren.render().tobytes())
        # command latency: targets issued `delay` physics steps ago
        hist.append(cur)
        leg_t, wheel_t = hist[0]
        qd_leg = np.array([d.qvel[vadr[n]] for n in LEGS])
        q_leg = np.array([d.qpos[qadr[n]] for n in LEGS])
        tau_leg = dc_clip(kp * (leg_t - q_leg) - kd * qd_leg, qd_leg, A['leg']['peak_nm'], A['leg']['no_load_rad_s'])
        qd_wh = np.array([d.qvel[vadr[n]] for n in WHEELS])
        tau_wh = dc_clip(A['wheel']['kd'] * (wheel_t - qd_wh), qd_wh, A['wheel']['peak_nm'], A['wheel']['no_load_rad_s'])
        for n, v in zip(LEGS, tau_leg):
            d.ctrl[act_id[n]] = v
        for n, v in zip(WHEELS, tau_wh):
            d.ctrl[act_id[n]] = v
        for n in rb.TURRET_JOINTS:     # hold the head still
            d.ctrl[act_id[n]] = np.clip(-20 * d.qpos[qadr[n]] - 0.5 * d.qvel[vadr[n]], *m.actuator_ctrlrange[act_id[n]])
        mujoco.mj_step(m, d)
    if vid is not None:
        vid.stdin.close(); vid.wait(); ren.close()

    t = np.array(log['t'])
    settled = np.zeros_like(t, dtype=bool)
    for i, c in enumerate(COURSE):
        end = COURSE[i + 1][0] if i + 1 < len(COURSE) else SECONDS
        settled |= (t >= c[0] + 1.0) & (t < end)
    ev = np.array(log['vx']) - np.array(log['cmd_vx'])
    ew = np.array(log['wz']) - np.array(log['cmd_wz'])
    res = {
        'simulator': f'MuJoCo {mujoco.__version__} CPU, {dt * 1000:.0f} ms timestep, full robot.xml (turret held by PD)',
        'model': str(Path(g.xml).parent), 'model_mass_kg': g.total_mass, 'policy': str(a.onnx.name), 'command_delay_ms': a.delay_ms, 'fell_at_s': fell_at,
        'rms_vx_error_mps': float(np.sqrt(np.mean(ev[settled] ** 2))),
        'rms_yaw_rate_error_radps': float(np.sqrt(np.mean(ew[settled] ** 2))),
        'max_abs_pitch_deg': float(np.max(np.abs(log['pitch']))),
        'final_position_m': [float(d.qpos[0]), float(d.qpos[1])],
        'segments': [],
    }
    for i, c in enumerate(COURSE):
        end = COURSE[i + 1][0] if i + 1 < len(COURSE) else SECONDS
        msk = (t >= c[0] + 1.0) & (t < end)
        res['segments'].append({'segment': c[3], 'cmd_vx': c[1], 'cmd_wz': c[2], 'mean_vx': round(float(np.mean(np.array(log['vx'])[msk])), 3),
                                'mean_wz': round(float(np.mean(np.array(log['wz'])[msk])), 3)})
    out = HERE / 'results/sim2sim_metrics.json' if a.tag == '' else HERE / f'results/sim2sim_metrics_{a.tag}.json'
    out.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
