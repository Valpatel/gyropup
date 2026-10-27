"""1,000 random power-ups of the pan homing and turn counting (firmware/turret/homing.py) against a model of the real
hardware, the acceptance test of docs/turret-plan.md task T4. Writes exports/turret/firmware/homing.json.

    .venv/bin/python firmware/turret/test_homing.py [--runs 1000] [--seed 1]

The model, per run (everything random within the stated ranges):
  - the turntable starts anywhere (0-360 deg); the servo's zero is anywhere relative to the magnet;
  - the STS3215's position read: 12 bits per servo turn, +-1 count of noise, 50-100 Hz with +-10 % jitter, 0-3 % of
    reads failing (a bus error: the firmware skips it);
  - the drive: the servo turns 3 x the turntable through the 63:21 gear with 0.44 deg of backlash at the turntable
    (0.15 mm per flank, docs/turret-physics.md section 8), and follows a speed command with a 60 ms lag;
  - the index: an A1120 hall switch over a 1/4 in magnet: on within +-1.5..4 deg of the magnet, off 0.3..1.0 deg
    later (its hysteresis), edges timestamped by an interrupt with +-50 us of jitter;
  - the assembly calibration found the window's centre to +-0.3 deg (setting pan 0 by eye).
Then, after homing, 20 s of random moves (up to +-720 deg, up to 90 deg/s, both directions) with the index re-check.
Pass: homed in every run within 400 deg and 8 s; the homing adds at most 0.15 deg to the calibration's own error; the
pan estimate, each time the turret has settled after a move, is within 0.15 deg of where homing left it (the tracker
puts the backlash back after a reversal; mid-reversal the turntable is somewhere in the backlash); no false re-home. The calibration's +-0.3 deg is a fixed offset the boresight takes out.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import homing as hm  # noqa: E402

R = Path(__file__).resolve().parents[2]
DT = 0.001


class Hardware:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.table = rng.uniform(0.0, 360.0)                 # the turntable's true pan (deg, continuous; magnet at 0)
        self.servo_zero = rng.uniform(0.0, 360.0)            # servo reads 0 at this turntable angle (mod 120)
        self.backlash = 0.44
        self.servo = self.table * hm.RATIO                   # the servo output's angle, deg (continuous)
        self.slack = rng.uniform(-0.5, 0.5) * self.backlash  # where the teeth sit inside the backlash
        self.v = 0.0
        self.w_on = rng.uniform(1.5, 4.0)
        self.h = rng.uniform(0.3, 1.0)
        self.hall = abs(self._d()) <= self.w_on
        self.read_hz = rng.uniform(50.0, 100.0)
        self.p_fail = rng.uniform(0.0, 0.03)
        self.next_read = 0.0

    def _d(self):
        return (self.table + 180.0) % 360.0 - 180.0

    def move(self, t, v_cmd, events):
        """Advance one step at the commanded pan speed (deg/s); append hall edges (time, rising, direction)."""
        self.v += (v_cmd - self.v) * DT / 0.06
        ds = self.v * hm.RATIO * DT
        self.servo += ds
        # the turntable follows the servo through the backlash: the slack absorbs motion until a flank is reached
        target = self.servo / hm.RATIO
        old = self.table
        lo, hi = target - self.backlash / 2, target + self.backlash / 2
        new = min(max(self.table, lo), hi)
        self.table = new
        d0, d1 = (old + 180.0) % 360.0 - 180.0, (new + 180.0) % 360.0 - 180.0
        if abs(d1 - d0) > 180.0:
            return
        on = self.hall
        thr = self.w_on if not on else self.w_on + self.h
        inside = abs(d1) <= thr
        if inside != on:
            # the crossing time inside the step, by interpolation, plus the interrupt's jitter
            f = 0.5
            for a, b in ((d0, d1),):
                edge = math.copysign(thr, d1 if abs(d1) > abs(d0) else d0)
                if b != a:
                    f = min(1.0, max(0.0, (edge - a) / (b - a)))
            events.append((t - DT + f * DT + self.rng.uniform(-50e-6, 50e-6), inside, 1 if new > old else -1))
            self.hall = inside

    def read(self, t):
        """None when there is no read this step or it failed; else the raw 12-bit count."""
        if t < self.next_read:
            return None, False
        self.next_read = t + (1.0 / self.read_hz) * self.rng.uniform(0.9, 1.1)
        if self.rng.random() < self.p_fail:
            return None, True
        ang = (self.servo - self.servo_zero * hm.RATIO) % 360.0
        raw = int(round(ang / 360.0 * hm.COUNTS + self.rng.uniform(-1.0, 1.0))) % hm.COUNTS
        return raw, True


def run(seed: int):
    rng = random.Random(seed)
    hw = Hardware(rng)
    # the assembly calibration: the window's centre in a +pan sweep sits h/2 past the magnet; measured to +-0.3 deg
    cal_err = rng.uniform(-0.3, 0.3)
    offset = hw.h / 2 + cal_err
    H = hm.Homing(calibrated_offset_deg=offset)
    t, ev = 0.0, []
    tilt_at_zero_t = rng.uniform(0.2, 0.6)
    start_table = hw.table
    while H.state not in ('DONE', 'FAILED') and t < 12.0:
        v = H.step(t, t >= tilt_at_zero_t)
        hw.move(t, v, ev)
        for (te, rising, _d) in ev:
            H.hall_edge(te, rising)
        ev.clear()
        raw, tried = hw.read(t)
        if tried:
            H.servo_read(t, raw)
        t += DT
    out = {'seed': seed, 'cal_err_deg': round(cal_err, 3), 'result': H.result or 'timeout', 'home_s': round(t, 2), 'swept_deg': round(hw.table - start_table, 1),
           'w_on': round(hw.w_on, 2), 'hyst': round(hw.h, 2), 'read_hz': round(hw.read_hz), 'p_fail': round(hw.p_fail, 3)}
    if H.result != 'homed':
        return out
    # brake to a stop, then check the estimate
    for _ in range(300):
        hw.move(t, 0.0, ev)
        ev.clear()
        raw, tried = hw.read(t)
        if tried:
            H.servo_read(t, raw)
        t += DT
    tr = H.tracker

    def err():
        p = tr.pan_deg()
        return ((p - hw.table) + 180.0) % 360.0 - 180.0

    e0 = err()
    out['err_after_home_deg'] = round(e0, 3)
    out['homing_repeatability_deg'] = round(e0 - cal_err, 3)          # the error the homing adds to the calibration's own
    # 20 s of random moves with the index re-check
    chk = hm.IndexCheck(tr, calibrated_offset_deg=offset)
    worst = 0.0
    t_end = t + 20.0
    goal, speed = hw.table, 0.0
    while t < t_end:
        if abs(goal - hw.table) < 0.5 and rng.random() < 0.002:
            goal = hw.table + rng.uniform(-720.0, 720.0)
            speed = rng.uniform(20.0, 90.0)
        dv = goal - hw.table
        v = max(-speed, min(speed, 4.0 * dv))
        hw.move(t, v, ev)
        for (te, rising, d) in ev:
            chk.hall_edge(te, rising, d)
        ev.clear()
        raw, tried = hw.read(t)
        if tried:
            tr.read(t, raw)
            if raw is not None:
                chk.after_read(t)
        if raw is not None and abs(hw.v) < 0.5 and abs(goal - hw.table) < 0.5:
            worst = max(worst, abs(err() - e0))           # settled (where it aims and fires), not mid-reversal
        t += DT
    out.update({'worst_track_err_deg': round(worst, 3), 'index_passes_checked': chk.passes,
                'index_worst_deg': round(chk.worst_deg, 3), 'false_rehome': chk.rehome})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    rows = [run(a.seed * 100000 + k) for k in range(a.runs)]
    ok = [r for r in rows if r['result'] == 'homed']
    fails = [r for r in rows if r['result'] != 'homed' or r['home_s'] > 8.0 or r['swept_deg'] > 400.0
             or abs(r.get('homing_repeatability_deg', 9)) > 0.15 or r.get('worst_track_err_deg', 9) > 0.15 or r.get('false_rehome')]
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(p * len(xs)))]
    hs = [r['home_s'] for r in ok]
    summary = {'runs': len(rows), 'homed': len(ok), 'failed_acceptance': len(fails),
               'home_time_s': {'median': q(hs, 0.5), 'p99': q(hs, 0.99), 'max': max(hs)} if hs else None,
               'swept_deg_max': max(r['swept_deg'] for r in ok) if ok else None,
               'err_after_home_deg_max': max(abs(r['err_after_home_deg']) for r in ok) if ok else None,
               'homing_repeatability_deg_max': max(abs(r['homing_repeatability_deg']) for r in ok) if ok else None,
               'track_err_deg_max': max(r['worst_track_err_deg'] for r in ok) if ok else None,
               'index_rechecks': sum(r['index_passes_checked'] for r in ok), 'index_recheck_worst_deg': max(r['index_worst_deg'] for r in ok) if ok else None,
               'false_rehomes': sum(1 for r in ok if r['false_rehome']),
               'pass': not fails, 'model': __doc__.split('\n\n')[1].strip()}
    out = R / 'exports' / 'turret' / 'firmware'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'homing.json').write_text(json.dumps({'summary': summary, 'failures': fails[:20], 'runs': rows[:50]}, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'model'}, indent=1))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
