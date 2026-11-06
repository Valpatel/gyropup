"""Plot a training run's curves from its TensorBoard log and save the key numbers.

    cd rl && .venv/bin/python scripts/plot_training.py [logs/rsl_rl/gyropup_velocity/<run>]

Writes results/training_curves.png and results/training_summary.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

HERE = Path(__file__).resolve().parents[1]
STEP_DT = 0.02          # policy period (s)
CMD_WINDOW_S = 8.0      # mjlab normalises the tracking-error metric by the longest command window (8 s)


def latest_run() -> Path:
    runs = sorted(p for p in (HERE / 'logs/rsl_rl/gyropup_velocity').glob('*') if list(p.glob('events*')))
    return runs[-1]


def series(ea, tag):
    ev = ea.Scalars(tag)
    return np.array([e.step for e in ev]), np.array([e.value for e in ev]), np.array([e.wall_time for e in ev])


def smooth(y, n=25):
    if len(y) < n:
        return y
    k = np.ones(n) / n
    return np.concatenate([y[:n - 1] * np.nan, np.convolve(y, k, mode='valid')])


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    ea = EventAccumulator(str(next(run.glob('events*'))), size_guidance={'scalars': 0})
    ea.Reload()
    it, rew, wall = series(ea, 'Train/mean_reward')
    # Episode terms are only logged on iterations where some episode ended: resample everything onto `it`.
    def on_it(tag):
        x, y, _ = series(ea, tag)
        return np.interp(it, x, y) if len(x) else np.zeros_like(it, dtype=float)
    eplen = on_it('Train/mean_episode_length')
    exy = on_it('Metrics/twist/error_vel_xy')
    eyaw = on_it('Metrics/twist/error_vel_yaw')
    vmax = on_it('Curriculum/command_vel/lin_vel_x_max')
    wmax = on_it('Curriculum/command_vel/ang_vel_z_max')
    push = on_it('Curriculum/push_intensity')
    fell = on_it('Episode_Termination/fell_over')
    # The logged tracking error is a per-episode sum divided by (8 s / dt); turn it into a per-step mean.
    steps = np.maximum(eplen, 1)
    mean_exy = exy * (CMD_WINDOW_S / STEP_DT) / steps
    mean_eyaw = eyaw * (CMD_WINDOW_S / STEP_DT) / steps
    minutes = (wall - wall[0]) / 60

    fig, ax = plt.subplots(2, 2, figsize=(12, 7.5))
    a = ax[0, 0]
    a.plot(it, rew, color='#2a6fdb', alpha=0.25, lw=0.8)
    a.plot(it, smooth(rew), color='#2a6fdb', lw=1.8)
    a.set_title('Mean episode return')
    a.set_xlabel('PPO iteration')
    top = a.secondary_xaxis('top', functions=(lambda x: np.interp(x, it, minutes), lambda m: np.interp(m, minutes, it)))
    top.set_xlabel('wall-clock minutes (RTX 3080, 4096 envs)')
    a = ax[0, 1]
    a.plot(it, eplen * STEP_DT, color='#2b8a3e', lw=1.5)
    a.set_title('Mean episode length (s, 20 s = never fell)')
    a.set_xlabel('PPO iteration')
    a.set_ylim(0, 21)
    a = ax[1, 0]
    a.plot(it, smooth(mean_exy, 10), color='#2a6fdb', lw=1.5, label='forward speed (m/s)')
    a.plot(it, smooth(mean_eyaw, 10), color='#d9480f', lw=1.5, label='yaw rate (rad/s)')
    a.set_title('Mean absolute tracking error per step')
    a.set_xlabel('PPO iteration')
    a.set_ylim(0, max(0.6, float(np.nanmax(smooth(mean_eyaw[len(it) // 20:], 10)))) * 1.1 if len(it) > 40 else None)
    a.legend(frameon=False)
    a = ax[1, 1]
    a.plot(it, vmax, color='#2a6fdb', lw=1.5, label='max |forward command| (m/s)')
    a.plot(it, wmax, color='#d9480f', lw=1.5, label='max |yaw command| (rad/s)')
    a.plot(it, push, color='#7048e8', lw=1.5, label='push intensity (x 0.5 m/s kicks)')
    a.set_title('Curriculum')
    a.set_xlabel('PPO iteration')
    a.legend(frameon=False, fontsize=8)
    for x in ax.flat:
        x.grid(alpha=0.3)
    fig.suptitle(f'Gyropup velocity task, PPO on mjlab: run {run.name}', fontsize=11)
    fig.tight_layout()
    out = HERE / 'results'
    out.mkdir(exist_ok=True)
    fig.savefig(out / 'training_curves.png', dpi=120)

    last = slice(-50, None)
    summary = {
        'run': run.name, 'iterations': int(it[-1]) + 1, 'wall_clock_min': round(float(minutes[-1]), 1),
        'env_steps': int((it[-1] + 1) * 4096 * 24),
        'first_iteration': {'mean_return': float(rew[0]), 'episode_length_s': float(eplen[0] * STEP_DT)},
        'last_50_iterations': {
            'mean_return': round(float(np.mean(rew[last])), 2),
            'episode_length_s': round(float(np.mean(eplen[last]) * STEP_DT), 2),
            'mean_abs_speed_error_mps': round(float(np.mean(mean_exy[last])), 3),
            'mean_abs_yaw_rate_error_radps': round(float(np.mean(mean_eyaw[last])), 3),
            'falls_per_episode_batch': round(float(np.mean(fell[last])), 4),
            'command_range': {'forward_mps': float(vmax[-1]), 'yaw_radps': float(wmax[-1])},
            'push_intensity': float(push[-1]),
        },
        'best_mean_return': round(float(np.max(rew)), 2),
        'note': 'Tracking errors are converted from mjlab\'s Metrics/twist/* (episode sum / (8 s / 0.02 s)) to a mean per step.',
    }
    (out / 'training_summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
