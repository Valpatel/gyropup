"""Export a trained Gyropup policy to ONNX with the metadata a robot-side runtime needs.

    cd rl && .venv/bin/python scripts/export_onnx.py [--checkpoint logs/.../model_N.pt]

Writes results/policy.onnx (observation normaliser + MLP actor, deterministic mean action) and results/policy.json
(observation layout and scales, action scales/offsets, PD gains, motor limits, rates). Check it with
scripts/run_onnx.py; the robot (Jetson AGX Orin) can run the same file with onnxruntime or convert it to TensorRT.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'scripts'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', type=Path)
    ap.add_argument('--design', default=os.environ.get('GYROPUP_DESIGN', 'designs/default.json'))
    ap.add_argument('--out', type=Path, default=HERE / 'results')
    a = ap.parse_args()
    os.environ['GYROPUP_DESIGN'] = a.design

    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import RslRlVecEnvWrapper
    from gyropup_rl import robot as rb
    from gyropup_rl import velocity_env_cfg as vc
    from gyropup_rl.tasks import GyropupRunner
    from play import latest_checkpoint

    ckpt = a.checkpoint or latest_checkpoint()
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    cfg = vc.gyropup_velocity_env_cfg(play=True)
    cfg.scene.num_envs = 1
    env = ManagerBasedRlEnv(cfg=cfg, device=device)
    venv = RslRlVecEnvWrapper(env)
    runner = GyropupRunner(venv, asdict(vc.GyropupVelocityRlCfg), log_dir=None, device=device)
    runner.load(str(ckpt), load_cfg={'actor': True}, strict=True, map_location=device)
    a.out.mkdir(parents=True, exist_ok=True)
    runner.export_policy_to_onnx(str(a.out), 'policy.onnx')

    # A reference input/output pair from the torch policy, so the ONNX file can be checked anywhere.
    obs = venv.get_observations()
    policy = runner.get_inference_policy(device=device)
    with torch.no_grad():
        act = policy(obs)

    om = env.observation_manager
    names, dims = om.active_terms['actor'], om.group_obs_term_dim['actor']
    scales = {n: (t.scale if t.scale is not None else 1.0) for n, t in zip(names, om._group_obs_term_cfgs['actor'])}
    g = rb.load()
    kp, kd = rb.leg_gains(g)
    layout, i = [], 0
    for n, d in zip(names, dims):
        layout.append({'name': n, 'start': i, 'size': int(d[0]), 'scale': float(scales[n])})
        i += int(d[0])
    meta = {
        'checkpoint': str(ckpt.relative_to(HERE)) if ckpt.is_relative_to(HERE) else str(ckpt),
        'design': a.design,
        'policy_hz': 1 / env.step_dt, 'physics_dt_s': rb.PHYSICS_DT,
        'onnx': {'input': 'obs', 'input_size': i, 'output': 'actions', 'output_size': 6},
        'observation_layout': layout,
        'observation_notes': {
            'projected_gravity': 'gravity unit vector in the base (IMU) frame, [0, 0, -1] when level',
            'base_ang_vel': 'gyro, base frame, rad/s',
            'leg_pos': 'hip_l, knee_l, hip_r, knee_r minus default_leg_pos (rad)',
            'joint_vel': 'hip_l, knee_l, hip_r, knee_r, wheel_l, wheel_r (rad/s) x 0.1',
            'actions': 'previous raw policy output (6)',
            'command': '[forward m/s, lateral (always 0), yaw rate rad/s]',
        },
        'actions': {
            'order': list(rb.LEG_JOINTS) + list(rb.WHEEL_JOINTS),
            'leg_position_target': 'default_leg_pos + 0.5 x a[0:4] (rad)',
            'wheel_velocity_target': f'{vc.WHEEL_ACTION_SCALE} x a[4:6] (rad/s)',
            'leg_scale': vc.LEG_ACTION_SCALE, 'wheel_scale': vc.WHEEL_ACTION_SCALE,
        },
        'default_leg_pos': [g.joint_pos[n] for n in rb.LEG_JOINTS],
        'actuators': {
            'leg': {'kp': kp, 'kd': kd, 'peak_nm': g.leg['peak_nm'], 'no_load_rad_s': g.leg['omega_max']},
            'wheel': {'kp': 0.0, 'kd': rb.WHEEL_KD, 'peak_nm': g.wheel['peak_nm'], 'no_load_rad_s': g.wheel['omega_max']},
            'torque_speed': 'linear: |tau| <= peak x (1 - |omega| / no_load) when motoring, peak when braking',
        },
        'reference': {'obs': obs['actor'][0].tolist(), 'actions': act[0].tolist()},
    }
    (a.out / 'policy.json').write_text(json.dumps(meta, indent=1) + '\n')
    print('wrote', a.out / 'policy.onnx', 'and policy.json from', ckpt)


if __name__ == '__main__':
    main()
