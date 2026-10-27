"""The two flywheels: set speed from CONFIG, the 200 ms ramp, a bounded speed trim, READY, and the pre-feed eRPM check
(docs/turret-firmware.md section 4).

The set speed comes from the tyre and the launch ratio (config.set_rpm); the throttle is a feed-forward from the
throttle map (test 4.3) or the no-load model, plus a PI trim bounded to +-8 % so that a doubled rail cannot hide under
the loop: on 24 V the wheels run away, the trim saturates, and the eRPM passes the limit.

The pre-feed check is the guard: every eRPM read of either wheel above 1.10 x KV x 12 V x 7 pole pairs (81,312 eRPM,
11,616 rpm for the X2216 880 KV) counts, three in a row trip it, and a tripped guard latches SAFE: zero throttle and no
dial step until the host clears it with the safety line released. A dial step also needs both wheels' eRPM fresher
than 20 ms, under the limit and READY.

What the firmware does not do (hardware, reported only): the 12 V-only rail is the ceiling; the phase-short brake
closes 10 ms after ARM falls; the chronograph latch trips at 66 fps.
"""
from __future__ import annotations

from collections import deque
from typing import List, Optional, Tuple

import config as C
import dshot


class ErpmGuard:
    def __init__(self, limit: float = C.ERPM_LIMIT, reads: int = C.ERPM_LIMIT_READS):
        self.limit, self.reads = limit, reads
        self.over = [0, 0]
        self.tripped = False
        self.first_over_t: Optional[float] = None
        self.trip_t: Optional[float] = None
        self.trip_erpm = 0.0
        self.max_erpm = 0.0

    def check(self, wheel: int, t: float, erpm: float) -> bool:
        self.max_erpm = max(self.max_erpm, erpm)
        if erpm > self.limit:
            if self.over[wheel] == 0 and not self.tripped:
                self.first_over_t = t if self.first_over_t is None else self.first_over_t
            self.over[wheel] += 1
            if self.over[wheel] >= self.reads and not self.tripped:
                self.tripped, self.trip_t, self.trip_erpm = True, t, erpm
                return True
        else:
            self.over[wheel] = 0
            if not self.tripped and max(self.over) == 0:
                self.first_over_t = None
        return False

    def clear(self):
        self.__init__(self.limit, self.reads)


class Wheel:
    def __init__(self):
        self.erpm: Optional[float] = None
        self.t = -1.0
        self.temp_c: Optional[float] = None
        self.volt_v: Optional[float] = None
        self.frames = 0
        self.bad = 0
        self.integral = 0.0
        self.trim = 0.0
        self.out = 0.0

    @property
    def rpm(self) -> float:
        return (self.erpm or 0.0) / C.POLE_PAIRS


class Flywheels:
    """mode: 'off' (the ESC rail is down), 'arming' (up, zero throttle until the ESCs arm), 'idle' (armed, zero
    throttle), 'speed' (closed loop on the set speed), 'throttle' (open loop: bench tests 4.1-4.3, 4.6)."""

    def __init__(self, cfg: C.Config):
        self.cfg = cfg
        self.w = [Wheel(), Wheel()]
        self.guard = ErpmGuard()
        self.mode = 'off'
        self.esc_on_t: Optional[float] = None
        self.edt_left = 0
        self.rpm_set = 0.0
        self.throttle_set = 0.0
        self.t0 = 0.0
        self.ready_since: Optional[float] = None
        self.hist: deque = deque()

    # ------------------------------------------------------------------ commands
    def esc_power(self, t: float, on: bool):
        if on and self.mode == 'off':
            self.mode, self.esc_on_t, self.edt_left = 'arming', t, 6
        elif not on:
            self.mode, self.esc_on_t = 'off', None
            for w in self.w:
                w.integral, w.trim, w.out = 0.0, 0.0, 0.0
            self.ready_since = None

    def esc_armed(self) -> bool:
        return self.mode in ('idle', 'speed', 'throttle')

    def spin_speed(self, t: float, rpm: float):
        if not self.esc_armed():
            return False
        if self.mode != 'speed':
            self.t0 = t
            for w in self.w:
                w.integral, w.trim = 0.0, 0.0
            self.ready_since = None
        self.mode, self.rpm_set = 'speed', rpm
        return True

    def spin_throttle(self, t: float, throttle: float):
        if not self.esc_armed():
            return False
        if self.mode != 'throttle':
            self.t0, self.ready_since = t, None
        self.mode, self.throttle_set = 'throttle', max(0.0, min(1.0, throttle))
        return True

    def stop(self, t: float):
        if self.mode in ('speed', 'throttle'):
            self.mode = 'idle'
        self.ready_since = None
        for w in self.w:
            w.integral, w.trim, w.out = 0.0, 0.0, 0.0

    @property
    def spinning(self) -> bool:
        return self.mode in ('speed', 'throttle')

    # ------------------------------------------------------------------ telemetry
    def on_frame(self, wheel: int, t: float, word16: int):
        d = dshot.decode_telemetry(word16)
        w = self.w[wheel]
        if d is None:
            w.bad += 1
            return
        kind, v = d
        if kind == 'erpm':
            w.erpm, w.t = v, t
            w.frames += 1
            self.guard.check(wheel, t, v)
        elif kind == 'temp_c':
            w.temp_c = v
        elif kind == 'volt_v':
            w.volt_v = v

    def fresh(self, t: float, age: float = C.TELEMETRY_STALE_S) -> bool:
        return all(w.erpm is not None and t - w.t <= age for w in self.w)

    def stopped(self, t: float) -> bool:
        """Both wheels below 300 rpm, or their ESCs silent (unpowered after a release)."""
        return all(w.erpm is None or t - w.t > 0.05 or w.rpm < 300.0 for w in self.w)

    def telemetry_lost(self, t: float) -> bool:
        return self.spinning and t - self.t0 > C.TELEMETRY_LOST_S and \
            any(w.erpm is None or t - w.t > C.TELEMETRY_LOST_S for w in self.w)

    # ------------------------------------------------------------------ the loop
    def update(self, t: float) -> Tuple[int, int]:
        """The two 16-bit DShot frames for this tick."""
        if self.mode == 'arming' and t - self.esc_on_t >= C.ESC_ARM_S:
            self.mode = 'idle'
        if self.mode in ('off', 'arming'):
            return dshot.frame(0), dshot.frame(0)
        if self.mode == 'idle':
            if self.edt_left > 0:                       # extended telemetry on (temperatures), once per power-up
                self.edt_left -= 1
                f = dshot.frame(dshot.CMD_EDT_ENABLE, telemetry=True)
                return f, f
            return dshot.frame(0), dshot.frame(0)
        el = t - self.t0
        out = []
        for w in self.w:
            if self.mode == 'throttle':
                thr = min(self.throttle_set, el / C.RAMP_S)
            else:
                frac = min(1.0, el / C.RAMP_S)
                thr = self.cfg.throttle_for(self.rpm_set * frac)
                if frac >= 1.0 and w.erpm is not None and self.rpm_set > 0:
                    e = (self.rpm_set - w.rpm) / self.rpm_set
                    w.integral = max(-C.TRIM_MAX, min(C.TRIM_MAX, w.integral + C.TRIM_KI * e * 0.001))
                    want = max(-C.TRIM_MAX, min(C.TRIM_MAX, C.TRIM_KP * e + w.integral))
                    # bumpless: the trim moves at most TRIM_SLEW a tick, so it never steps the current at the ramp's end
                    w.trim += max(-C.TRIM_SLEW, min(C.TRIM_SLEW, want - w.trim))
                    thr += w.trim
            w.out = max(0.0, min(1.0, thr))
            out.append(dshot.frame(dshot.throttle_value(w.out)))
        self._ready_track(t)
        return out[0], out[1]

    def _ready_track(self, t: float):
        self.hist.append((t, self.w[0].erpm or 0.0, self.w[1].erpm or 0.0))
        while self.hist and self.hist[0][0] < t - 0.12:
            self.hist.popleft()
        ok = self.fresh(t)
        if ok and self.mode == 'speed':
            ok = t - self.t0 >= C.RAMP_S and all(abs(w.rpm - self.rpm_set) <= C.READY_TOL * self.rpm_set
                                                  for w in self.w)
        elif ok and self.mode == 'throttle':
            ok = t - self.t0 >= C.RAMP_S * self.throttle_set + 0.15 and self.hist[0][0] <= t - 0.1 and \
                all(abs(self.hist[-1][k] - self.hist[0][k]) <= 0.01 * max(1.0, self.hist[-1][k]) for k in (1, 2))
        if ok:
            self.ready_since = t if self.ready_since is None else self.ready_since
        else:
            self.ready_since = None

    def ready(self, t: float) -> bool:
        return self.spinning and self.ready_since is not None and t - self.ready_since >= C.READY_HOLD_S

    def prefeed_ok(self, t: float) -> Tuple[bool, str]:
        if self.guard.tripped:
            return False, 'erpm limit'
        if not self.fresh(t):
            return False, 'telemetry stale'
        if any(w.erpm > C.ERPM_LIMIT for w in self.w):
            return False, 'erpm over the limit'
        if not self.ready(t):
            return False, 'not ready'
        return True, ''

    def rpms(self) -> List[float]:
        return [w.rpm for w in self.w]
