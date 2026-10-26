"""Run the exported policy for one control step with onnxruntime on the CPU (no torch, no simulator).

    cd rl && .venv/bin/python scripts/run_onnx.py [results/policy.onnx]

Builds the observation of a robot standing still and level with a zero command, runs one step, converts the
output to joint targets, checks the result against the torch reference stored in policy.json and times the call.
This is the path the robot's computer (Jetson AGX Orin) will use; TensorRT can load the same .onnx file later.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parents[1]


def main():
    onnx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results/policy.onnx'
    meta = json.loads(onnx_path.with_suffix('.json').read_text())
    sess = ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'])
    inp = sess.get_inputs()[0]
    print(f'model: {onnx_path.name}  input {inp.name}{inp.shape}  output {sess.get_outputs()[0].name}{sess.get_outputs()[0].shape}'
          f'  providers {sess.get_providers()}')

    # 1. Reference check: the observation recorded from the training simulator gives the torch policy's action.
    ref_obs = np.array(meta['reference']['obs'], dtype=np.float32)[None]
    ref_act = np.array(meta['reference']['actions'], dtype=np.float32)
    got = sess.run(None, {inp.name: ref_obs})[0][0]
    print(f'reference check: max |onnx - torch| = {np.max(np.abs(got - ref_act)):.2e}')

    # 2. One control step from a hand-built observation: standing still, level, zero command.
    obs = np.zeros((1, meta['onnx']['input_size']), dtype=np.float32)
    seg = {s['name']: s for s in meta['observation_layout']}
    g = seg['projected_gravity']
    obs[0, g['start'] + 2] = -1.0 * g['scale']
    act = sess.run(None, {inp.name: obs})[0][0]
    legs = np.array(meta['default_leg_pos']) + meta['actions']['leg_scale'] * act[:4]
    wheels = meta['actions']['wheel_scale'] * act[4:]
    print('raw action        :', np.round(act, 3))
    for n, v in zip(meta['actions']['order'][:4], legs):
        print(f'  {n:8s} position target {v:+.3f} rad')
    for n, v in zip(meta['actions']['order'][4:], wheels):
        print(f'  {n:8s} velocity target {v:+.3f} rad/s')

    # 3. Latency on this CPU (the policy runs at 50 Hz, a 20 ms budget).
    n = 2000
    t0 = time.perf_counter()
    for _ in range(n):
        sess.run(None, {inp.name: obs})
    dt = (time.perf_counter() - t0) / n
    print(f'onnxruntime CPU latency: {dt * 1e6:.0f} us per step ({meta["policy_hz"]:.0f} Hz control loop budget '
          f'{1e6 / meta["policy_hz"]:.0f} us)')


if __name__ == '__main__':
    main()
