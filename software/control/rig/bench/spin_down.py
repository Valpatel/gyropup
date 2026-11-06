"""B2: the RS-04's rotor inertia (reflected to the output) and its friction, from a torque step and a coast.

    python -m rig.bench.spin_down --iface can0 --id 1            # the motor alone on the dyno plate, no spider

MIT mode with Kp = Kd = 0: a 2 N m step from rest until 0.4 s or 8 rad/s, then 0 N m while it coasts down; the speed
logged every 2 ms. J dw/dt = t - c sign(w) - b w is fitted over both parts by least squares (the coast alone separates
the friction from the inertia). The simulation assumes 0.0243 kg m^2 (3e-4 x 9^2: an estimate, the manual gives none);
the main session sets ARMATURE from this (F1). The push ends at 8 rad/s because the speed field saturates at 15.
Nothing on the output: the dyno hub's own inertia would add to the answer.

Writes exports/rig/bench/b2-motor<id>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from rig import rs04 as P

R = Path(__file__).resolve().parents[2]
OUT = R / 'exports' / 'rig' / 'bench'


def record(bus, motor: int, tau: float = 2.0, t_push: float = 0.4, w_push: float = 8.0, t_coast: float = 1.5, dt: float = 0.002,
           clock=time.monotonic, sleep=time.sleep, step=None) -> dict:
    """[t], [w], [p], [t_cmd]: the step and the coast. `step(dt)` advances a simulated plant instead of waiting."""
    m = P.Motor(bus, motor)
    m.stop()
    m.write_check('run_mode', 0)
    m.enable()
    t0 = clock()
    ts, ws, ps, cmds = [], [], [], []
    t_end = None                                            # when the push ended (t_push, or w_push reached)
    try:
        k = 0
        cmd = tau
        while True:
            t = k * dt
            if t_end is not None and t > t_end + t_coast:
                break
            fb = m.mit(t=cmd)
            ts.append(t)
            ws.append(fb.v)
            ps.append(fb.p)
            cmds.append(cmd)
            if t_end is None and (t + dt >= t_push or abs(fb.v) >= w_push):
                t_end, cmd = t + dt, 0.0
            if step:
                step(dt)
            else:
                while clock() - t0 < (k + 1) * dt:
                    sleep(0.0002)
            k += 1
    finally:
        m.stop()
    return {'t': ts, 'w': ws, 'p': ps, 't_cmd': cmds}


def fit(rec: dict) -> dict:
    """J, the Coulomb c and viscous b from the step and the coast (rows while moving, w > 0.05 rad/s)."""
    t, w, u = (np.asarray(rec[k], dtype=float) for k in ('t', 'w', 't_cmd'))
    a = np.gradient(w, t)
    keep = (np.abs(w) > 0.05) & (np.abs(w) < 14.5)
    keep[1:] &= u[1:] == u[:-1]                            # not across the step's edge, where the gradient mixes both
    keep[:-1] &= u[:-1] == u[1:]
    A = np.column_stack([a[keep], np.sign(w[keep]), w[keep]])
    J, c, b = np.linalg.lstsq(A, u[keep], rcond=None)[0]
    resid = u[keep] - A @ np.array([J, c, b])
    return {'J_kg_m2': float(J), 'coulomb_nm': float(c), 'viscous_nm_s_rad': float(b), 'rms_residual_nm': float(np.sqrt(np.mean(resid ** 2))),
            'peak_speed_rad_s': float(np.max(np.abs(w))), 'sim_assumes_J': 3.0e-4 * 81}


def main(argv=None, transport=None, out=print) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.bench.spin_down')
    ap.add_argument('--iface', default='can0')
    ap.add_argument('--id', type=int, default=1)
    ap.add_argument('--tau', type=float, default=2.0)
    a = ap.parse_args(argv)
    if transport is None:
        from rig.canio import SocketCan
        transport = SocketCan(a.iface)
    runs = []
    for k in range(3):                                      # three repeats: the spread is part of the answer
        rec = record(P.RS04Bus(transport), a.id, a.tau)
        runs.append({'fit': fit(rec), 'record': rec})
        time.sleep(1.0)
    Js = [r['fit']['J_kg_m2'] for r in runs]
    doc = {'test': 'B2', 'motor': a.id, 'J_kg_m2': float(np.mean(Js)), 'J_spread': float(np.ptp(Js) / max(np.mean(Js), 1e-9)), 'runs': runs}
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f'b2-motor{a.id}.json'
    f.write_text(json.dumps(doc, indent=1) + '\n')
    out(f"motor {a.id}: J {doc['J_kg_m2']:.4f} kg m^2 (spread {doc['J_spread'] * 100:.0f} %; the sim assumes 0.0243) -> {f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
