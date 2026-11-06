"""C6: can the laptop hold the control loop's rate? Zero-torque MIT frames to the motors at the loop's schedule, the
lateness of each send and the round trip to the last reply measured (plan section 4.5 step 2: 99 % of ticks within
+-0.3 ms; if not, run the first stand at 250 Hz and move the loop to the Feather later).

    python -m rig.bench.jitter --iface can0 --ids 1 --rate 500 --seconds 20
    python -m rig.bench.jitter --iface can0 --ids 1 2 --rate 500 --seconds 20 --load   # with a CPU hog beside it

The motors are enabled with Kp = Kd = 0 and 0 N m (they do nothing); they are stopped at the end and on Ctrl-C.
Writes exports/rig/bench/c6-jitter-<rate>hz.json.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

from rig import rs04 as P
from rig.can_bus import Timing

R = Path(__file__).resolve().parents[2]
OUT = R / 'exports' / 'rig' / 'bench'


def run(bus: P.RS04Bus, ids, rate: float = 500.0, seconds: float = 20.0, clock=time.monotonic, sleep=time.sleep) -> Timing:
    tick = 1.0 / rate
    tm = Timing()
    motors = [P.Motor(bus, i) for i in ids]
    for m in motors:
        m.stop()
        m.write_check('run_mode', 0)
        m.enable()
    t0 = clock()
    k = 0
    try:
        while k * tick < seconds:
            due = t0 + k * tick
            while True:
                left = due - clock()
                if left <= 0:
                    break
                if left > 0.0005:
                    sleep(left - 0.0004)
            sent = clock()
            got = bus.exchange([(i, 0.0, 0.0, 0.0, 0.0, 0.0) for i in ids], timeout=0.75 * tick)
            tm.late_ms.append((sent - due) * 1000.0)
            if len(got) == len(ids):
                tm.rtt_ms.append((clock() - sent) * 1000.0)
            else:
                tm.missed += 1
            k += 1
    finally:
        for m in motors:
            try:
                m.stop()
            except P.NoReply:
                pass
    return tm


def _hog(stop):
    x = 0
    while not stop.is_set():
        x = (x * 1103515245 + 12345) & 0xFFFFFFFF


def main(argv=None, transport=None, out=print) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.bench.jitter')
    ap.add_argument('--iface', default='can0')
    ap.add_argument('--ids', type=int, nargs='+', default=[1])
    ap.add_argument('--rate', type=float, default=500.0)
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--load', action='store_true', help='a busy process on every other core while it runs')
    a = ap.parse_args(argv)
    if transport is None:
        from rig.canio import SocketCan
        transport = SocketCan(a.iface)
    stop, hogs = mp.Event(), []
    if a.load:
        for _ in range(max(1, mp.cpu_count() - 1)):
            p = mp.Process(target=_hog, args=(stop,), daemon=True)
            p.start()
            hogs.append(p)
    try:
        tm = run(P.RS04Bus(transport), a.ids, a.rate, a.seconds)
    finally:
        stop.set()
    s = tm.summary()
    ok = (s['within_0p3ms'] or 0) >= 0.99 and s['missed'] <= 0.001 * max(1, s['ticks'] + s['missed'])
    doc = {'test': 'C6', 'rate_hz': a.rate, 'ids': a.ids, 'load': a.load, 'summary': s, 'pass': ok,
           'rule': '99 % of sends within +-0.3 ms of the schedule, under 0.1 % of ticks missing a reply'}
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"c6-jitter-{a.rate:.0f}hz{'-load' if a.load else ''}.json"
    f.write_text(json.dumps(doc, indent=1) + '\n')
    out(f"{'PASS' if ok else 'FAIL'}: {s} -> {f}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
