"""Play a trained Gyropup policy on a scripted drive course in the training simulator (mjlab, MuJoCo Warp), record
an MP4 and score velocity tracking.

    cd rl && MUJOCO_GL=egl .venv/bin/python scripts/play.py [--checkpoint logs/.../model_3999.pt] [--design designs/x.json]

Writes results/gyropup_drive.mp4, results/play_tracking.png and results/play_metrics.json. The nominal robot is used
(no mass/friction/motor randomisation, no pushes); the 0-20 ms command latency stays on.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

# (start s, forward m/s, yaw rad/s, label)
COURSE = [
    (0.0, 0.0, 0.0, 'stand'),
    (2.0, 0.5, 0.0, 'forward 0.5 m/s'),
    (5.0, 1.0, 0.0, 'forward 1.0 m/s'),
    (8.0, 0.6, 1.0, 'arc left'),
    (11.0, 0.0, -1.5, 'spin right'),
    (13.5, -0.5, 0.0, 'reverse 0.5 m/s'),
    (16.0, 0.8, -0.8, 'arc right'),
    (19.0, 0.0, 0.0, 'stop'),
]
SECONDS = 21.0


def command_at(t):
    cur = COURSE[0]
    for c in COURSE:
        if t >= c[0]:
            cur = c
    return cur


def latest_checkpoint() -> Path:
    runs = sorted((HERE / 'logs/rsl_rl/gyropup_velocity').glob('*'))
    for run in reversed(runs):
        cks = sorted(run.glob('model_*.pt'), key=lambda p: int(p.stem.split('_')[1]))
        if cks:
            return cks[-1]
    raise FileNotFoundError('no checkpoint under logs/rsl_rl/gyropup_velocity')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', type=Path)
    ap.add_argument('--design', default=os.environ.get('GYROPUP_DESIGN', 'designs/default.json'))
    ap.add_argument('--out', type=Path, default=HERE / 'results')
    ap.add_argument('--width', type=int, default=960)
    ap.add_argument('--height', type=int, default=540)
    a = ap.parse_args()
    os.environ['GYROPUP_DESIGN'] = a.design
    os.environ.setdefault('MUJOCO_GL', 'egl')

    import numpy as np
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import RslRlVecEnvWrapper
    from gyropup_rl.tasks import GyropupRunner
    from gyropup_rl.velocity_env_cfg import GyropupVelocityRlCfg, gyropup_velocity_env_cfg

    ckpt = a.checkpoint or latest_checkpoint()
    cfg = gyropup_velocity_env_cfg(play=True)
    cfg.scene.num_envs = 1
    for k in ('mass', 'base_com', 'motor_strength', 'pd_gains', 'encoder_bias', 'wheel_friction'):
        cfg.events.pop(k, None)
    cfg.events['reset_base'].params['pose_range'] = {}
    cfg.events['reset_base'].params['velocity_range'] = {}
    cfg.events['reset_joints'].params['position_range'] = (0.0, 0.0)
    tw = cfg.commands['twist']
    tw.resampling_time_range = (1e9, 1e9)
    tw.rel_standing_envs = 0.0
    cfg.viewer.width, cfg.viewer.height = a.width, a.height
    cfg.viewer.distance, cfg.viewer.elevation, cfg.viewer.azimuth = 2.4, -15.0, 135.0
    cfg.terminations.pop('time_out', None)

    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    env = ManagerBasedRlEnv(cfg=cfg, device=device, render_mode='rgb_array')
    venv = RslRlVecEnvWrapper(env)
    runner = GyropupRunner(venv, asdict(GyropupVelocityRlCfg), log_dir=None, device=device)
    runner.load(str(ckpt), load_cfg={'actor': True}, strict=True, map_location=device)
    policy = runner.get_inference_policy(device=device)

    a.out.mkdir(parents=True, exist_ok=True)
    mp4 = a.out / 'gyropup_drive.mp4'
    fps = int(round(1 / env.step_dt))
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', f'{a.width}x{a.height}', '-r', str(fps), '-i', '-', '-c:v', 'libx264',
                           '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '26', str(mp4)], stdin=subprocess.PIPE)
    term = env.command_manager.get_term('twist')
    robot = env.scene['robot']
    obs = venv.get_observations()
    log = {k: [] for k in ('t', 'cmd_vx', 'cmd_wz', 'vx', 'wz', 'pitch', 'height', 'tau_max_leg', 'tau_max_wheel')}
    falls = 0
    steps = int(SECONDS / env.step_dt)
    for k in range(steps):
        t = k * env.step_dt
        _, vx_c, wz_c, _ = command_at(t)
        term.vel_command_b[:, 0] = vx_c
        term.vel_command_b[:, 1] = 0.0
        term.vel_command_b[:, 2] = wz_c
        obs = venv.get_observations()
        with torch.no_grad():
            act = policy(obs)
        obs, _, dones, _ = venv.step(act)
        if bool(dones[0]):
            falls += 1
        d = robot.data
        g = d.projected_gravity_b[0].cpu().numpy()
        f = d.actuator_force[0].abs().cpu().numpy()
        log['t'].append(t)
        log['cmd_vx'].append(vx_c)
        log['cmd_wz'].append(wz_c)
        log['vx'].append(float(d.root_link_lin_vel_b[0, 0]))
        log['wz'].append(float(d.root_link_ang_vel_b[0, 2]))
        log['pitch'].append(float(np.degrees(np.arctan2(g[0], -g[2]))))
        log['height'].append(float(d.root_link_pos_w[0, 2]))
        log['tau_max_leg'].append(float(f[:4].max()))
        log['tau_max_wheel'].append(float(f[4:].max()))
        frame = env.render()
        ff.stdin.write(np.ascontiguousarray(frame).tobytes())
    ff.stdin.close()
    ff.wait()
    env.close()

    t = np.array(log['t'])
    settled = np.zeros_like(t, dtype=bool)
    for i, c in enumerate(COURSE):           # score after 1 s of settling into each segment
        end = COURSE[i + 1][0] if i + 1 < len(COURSE) else SECONDS
        settled |= (t >= c[0] + 1.0) & (t < end)
    ev = np.array(log['vx']) - np.array(log['cmd_vx'])
    ew = np.array(log['wz']) - np.array(log['cmd_wz'])
    segs = []
    for i, c in enumerate(COURSE):
        end = COURSE[i + 1][0] if i + 1 < len(COURSE) else SECONDS
        m = (t >= c[0] + 1.0) & (t < end)
        segs.append({'segment': c[3], 'cmd_vx': c[1], 'cmd_wz': c[2],
                     'mean_vx': float(np.mean(np.array(log['vx'])[m])), 'mean_wz': float(np.mean(np.array(log['wz'])[m]))})
    metrics = {
        'checkpoint': str(ckpt.relative_to(HERE)) if ckpt.is_relative_to(HERE) else str(ckpt),
        'design': a.design, 'seconds': SECONDS, 'falls': falls,
        'rms_vx_error_mps': float(np.sqrt(np.mean(ev[settled] ** 2))),
        'rms_yaw_rate_error_radps': float(np.sqrt(np.mean(ew[settled] ** 2))),
        'max_abs_pitch_deg': float(np.max(np.abs(log['pitch']))),
        'height_min_max_m': [float(min(log['height'])), float(max(log['height']))],
        'peak_leg_torque_nm': float(max(log['tau_max_leg'])), 'peak_wheel_torque_nm': float(max(log['tau_max_wheel'])),
        'segments': segs,
    }
    (a.out / 'play_metrics.json').write_text(json.dumps(metrics, indent=1) + '\n')
    np.savez_compressed(a.out / 'play_log.npz', **{k: np.array(v) for k, v in log.items()})

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True)
    ax[0].plot(t, log['cmd_vx'], color='#888', lw=2, label='command')
    ax[0].plot(t, log['vx'], color='#2a6fdb', lw=1.3, label='actual')
    ax[0].set_ylabel('forward speed (m/s)')
    ax[0].legend(loc='upper right', frameon=False)
    ax[1].plot(t, log['cmd_wz'], color='#888', lw=2)
    ax[1].plot(t, log['wz'], color='#d9480f', lw=1.3)
    ax[1].set_ylabel('yaw rate (rad/s)')
    ax[2].plot(t, log['pitch'], color='#2b8a3e', lw=1.3)
    ax[2].set_ylabel('body pitch (deg)')
    ax[2].set_xlabel('time (s)')
    for x in ax:
        x.grid(alpha=0.3)
        for c in COURSE[1:]:
            x.axvline(c[0], color='#ccc', lw=0.8, zorder=0)
    for c in COURSE:
        ax[0].text(c[0] + 0.05, ax[0].get_ylim()[1], c[3], fontsize=7, va='top', color='#555')
    fig.suptitle(f'Gyropup policy on the drive course: RMS speed error {metrics["rms_vx_error_mps"]:.2f} m/s, '
                 f'yaw-rate error {metrics["rms_yaw_rate_error_radps"]:.2f} rad/s, falls {falls}', fontsize=10)
    fig.tight_layout()
    fig.savefig(a.out / 'play_tracking.png', dpi=120)
    print(json.dumps(metrics, indent=1))
    print('video:', mp4)


if __name__ == '__main__':
    main()
