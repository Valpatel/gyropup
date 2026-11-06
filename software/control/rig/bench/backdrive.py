"""B1: the RS-04's back-drive torque against speed with its power off (D39's decision: no spring if the damping holds
a power cut's collapse under the fault case's limit).

    python -m rig.bench.backdrive --iface can0 --driver 2 --condition unpowered_damper0
    python -m rig.bench.backdrive --iface can0 --driver 2 --condition friction    # the spider out: the driver alone

On the dyno (cad/rig_bench.py): motor A (the tested one) and motor B (the driver) output to output through the TPU
spider. B runs in velocity mode (manual 4.3.3) at each speed, both ways, and its own torque estimate is the drag: B's
torque with A coupled, less B's torque with the spider out (`friction`, run first). A's conditions:
  unpowered_damper0   A's power lead unplugged, the anti-backdrive switch at its default (damper 0, saved)
  unpowered_damper1   the same with damper 1 (protection off), saved before unplugging
  powered_stopped     A powered and in its stop (reset) state
Before 'unpowered_*': with A powered, `python -m rig.rs04 --id 1 param damper 0` (or 1), `... save`, then unplug A's XT30
and tape its pins apart: back-driven at 13 rad/s it makes about 30 V.

Writes exports/rig/bench/b1-<condition>.json; rig/bench/fit_params.py turns the set into the b(w) curve for F1.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from rig import rs04 as P

R = Path(__file__).resolve().parents[2]
OUT = R / 'exports' / 'rig' / 'bench'
SPEEDS = (0.5, 1.0, 2.0, 4.0, 7.0, 10.0, 13.0)       # rad/s at the output (the feedback's field saturates at 15)


def sweep(bus, driver: int, speeds=SPEEDS, settle: float = 1.5, hold: float = 1.5, rate: float = 200.0, limit_cur: float = 40.0,
          stop_nm: float = 60.0, clock=time.monotonic, sleep=time.sleep) -> list:
    """Run the driver at each speed, both ways; each spd_ref write returns a feedback frame, which is the sample.
    Stops a direction early once the drag passes stop_nm (the answer is then 'strong')."""
    m = P.Motor(bus, driver)
    m.stop()
    m.write_check('run_mode', 2)
    m.write_check('limit_cur', limit_cur)
    m.write('acc_rad', 20.0)
    m.enable()
    rows = []
    try:
        for sgn in (1.0, -1.0):
            for w in speeds:
                t0 = clock()
                v_s, t_s = [], []
                while clock() - t0 < settle + hold:
                    fb = m.write('spd_ref', sgn * w)
                    if clock() - t0 >= settle:
                        v_s.append(fb.v)
                        t_s.append(fb.t)
                    sleep(1.0 / rate)
                row = {'speed_cmd': sgn * w, 'speed': statistics.fmean(v_s) if v_s else None, 'torque': statistics.fmean(t_s) if t_s else None,
                       'torque_sd': statistics.pstdev(t_s) if len(t_s) > 1 else None, 'n': len(t_s)}
                rows.append(row)
                if row['torque'] is not None and abs(row['torque']) > stop_nm:
                    break
            m.write('spd_ref', 0.0)
            sleep(1.0)
    finally:
        try:
            m.write('spd_ref', 0.0)
            m.stop()
            m.write('run_mode', 0)
        except P.NoReply:
            pass
    return rows


def drag(rows: list, friction: list) -> list:
    """A's drag at each speed: the driver's torque with A coupled less its own (friction run), matched by speed."""
    def interp(w, table):
        pts = sorted((r['speed'], r['torque']) for r in table if r['speed'] is not None)
        if not pts:
            return 0.0
        if w <= pts[0][0]:
            return pts[0][1]
        for (w0, t0), (w1, t1) in zip(pts, pts[1:]):
            if w0 <= w <= w1:
                return t0 + (t1 - t0) * (w - w0) / (w1 - w0) if w1 > w0 else t0
        return pts[-1][1]
    return [{'speed': r['speed'], 'drag_nm': r['torque'] - interp(r['speed'], friction)} for r in rows if r['speed'] is not None]


def fit(rows: list, friction: list) -> dict:
    """A's drag as c sign(w) + b w (N m, N m s/rad; same sign as the speed), and the table behind it."""
    import numpy as np
    dr = drag(rows, friction)
    w = np.array([r['speed'] for r in dr])
    t = np.array([r['drag_nm'] for r in dr])
    (c, b), *_ = np.linalg.lstsq(np.column_stack([np.sign(w), w]), t, rcond=None)
    return {'coulomb_nm': float(c), 'b_nm_s_rad': float(b),
            'table': [{'w_rad_s': round(float(x), 3), 'drag_nm': round(float(y), 3)} for x, y in zip(w, t)]}


def main(argv=None, transport=None, out=print) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.bench.backdrive')
    ap.add_argument('--iface', default='can0')
    ap.add_argument('--driver', type=int, default=2)
    ap.add_argument('--condition', required=True, choices=('friction', 'unpowered_damper0', 'unpowered_damper1', 'powered_stopped'))
    ap.add_argument('--speeds', type=float, nargs='*', default=list(SPEEDS))
    ap.add_argument('--limit-cur', type=float, default=40.0)
    a = ap.parse_args(argv)
    if transport is None:
        from rig.canio import SocketCan
        transport = SocketCan(a.iface)
    rows = sweep(P.RS04Bus(transport), a.driver, a.speeds, limit_cur=a.limit_cur)
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {'test': 'B1', 'condition': a.condition, 'driver': a.driver, 'rows': rows, 'when': time.strftime('%Y-%m-%d %H:%M')}
    f = OUT / f'b1-{a.condition}.json'
    f.write_text(json.dumps(doc, indent=1) + '\n')
    for r in rows:
        out(f"  {r['speed_cmd']:+6.1f} rad/s: {r['speed'] if r['speed'] is None else round(r['speed'], 2):>6} rad/s, {r['torque'] if r['torque'] is None else round(r['torque'], 2):>7} N m")
    out(f'wrote {f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
