"""Pan homing and turn counting for the turret's continuous pan (docs/turret-firmware.md 3; docs/turret-plan.md 3.2).

The reference the Feather's firmware ports line for line. Pure Python, no dependencies.

The pan servo (STS3215) reports a 12-bit absolute angle per turn of its own output, and it drives the turntable through
63:21, so one servo turn is 120 deg of pan: at power-up the pan is known only modulo 120 deg. The index (a magnet in
the base at pan 0, a hall switch on the turntable) settles which of the three it is:

  1. the tilt goes to its 0 deg stop first (nothing can then meet the lidar or the deck);
  2. the pan sweeps in +pan at <= 60 deg/s (always the same direction, the one the index was calibrated in) until the
     hall's window has been crossed: its rising and falling edges are timestamped by an interrupt, the servo's
     position by its reads, and the window's centre comes from interpolating the reads at the two edge times;
  3. the turn counter is zeroed there: from then on pan = (servo counts unwrapped - counts at the index) / 4096 * 120.
     Reads at >= 50 Hz keep the unwrapping unambiguous (90 deg/s of pan is 270 deg/s at the servo: 5.4 deg a read).
  4. every later pass over the index re-checks the count; a disagreement above `RECHECK_DEG` asks for a re-home.

The window's centre is offset from the magnet by half the switch's hysteresis, the same way every time the turret
sweeps in +pan, so the assembly calibration (`calibrate`) and homing both sweep in +pan and the offset cancels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

COUNTS = 4096                 # STS3215 position counts per servo turn
RATIO = 3.0                   # servo turns per pan turn (63 : 21)
PAN_PER_COUNT = 360.0 / COUNTS / RATIO
HOME_SPEED_DEG_S = 60.0       # pan speed while homing
MAX_SWEEP_DEG = 400.0         # give up (and report) if the index has not been seen by then
RECHECK_DEG = 2.0             # an index pass this far from pan 0 asks for a re-home


def unwrap_step(prev: int, now: int) -> int:
    """Signed servo-count change between two reads, assuming less than half a servo turn between them."""
    d = (now - prev) % COUNTS
    return d - COUNTS if d >= COUNTS // 2 else d


@dataclass
class PanTracker:
    """Unwraps the servo's 12-bit angle into a continuous count and, once homed, the pan angle. The gear's backlash
    (0.44 deg at the turntable, docs/turret-physics.md section 8) puts the turntable behind the servo by the full
    backlash after a reversal: the tracker follows the drive's direction (with a 3-count dead band) and adds it back
    when the last motion was in -pan (homing and its calibration both run in +pan)."""
    backlash_deg: float = 0.44
    total: Optional[int] = None           # unwrapped servo counts since power-up
    last: Optional[int] = None            # the last raw read
    index_total: Optional[float] = None   # unwrapped count at the index (pan 0), once homed
    samples: List[Tuple[float, float]] = field(default_factory=list)   # (time, unwrapped count), for edge interpolation
    direction: int = 1
    _turn_from: Optional[int] = None

    def read(self, t: float, raw: Optional[int]):
        """Feed one servo read (None for a failed read: skipped)."""
        if raw is None:
            return
        if self.total is None:
            self.total = raw
            self._turn_from = raw
        else:
            self.total += unwrap_step(self.last, raw)
            moved = self.total - self._turn_from
            if moved * self.direction < 0 and abs(moved) >= 3:
                self.direction = -self.direction
            if moved * self.direction > 0:
                self._turn_from = self.total
        self.last = raw
        self.samples.append((t, float(self.total)))
        if len(self.samples) > 64:
            del self.samples[:-64]

    def count_at(self, t: float) -> Optional[float]:
        """The unwrapped count at time t, interpolated between the reads either side of it."""
        s = self.samples
        for (t0, c0), (t1, c1) in zip(s, s[1:]):
            if t0 <= t <= t1:
                return c0 + (c1 - c0) * (t - t0) / (t1 - t0) if t1 > t0 else c0
        return None

    @property
    def homed(self) -> bool:
        return self.index_total is not None

    def pan_deg(self) -> Optional[float]:
        if not self.homed or self.total is None:
            return None
        return (self.total - self.index_total) * PAN_PER_COUNT + (self.backlash_deg if self.direction < 0 else 0.0)


@dataclass
class Homing:
    """The homing state machine. Drive it with `step(t)` at the read rate, `servo_read(t, raw)` for every read and
    `hall_edge(t, rising)` from the hall's interrupt; it answers the pan speed to command (deg/s, + = +pan)."""
    tracker: PanTracker = field(default_factory=PanTracker)
    calibrated_offset_deg: float = 0.0    # from `calibrate`: where the window's centre lies from the magnet (+pan sweep)
    state: str = 'TILT_TO_ZERO'
    start_total: Optional[float] = None
    rise_t: Optional[float] = None
    result: Optional[str] = None
    swept_deg: float = 0.0
    fall_t: Optional[float] = None

    def servo_read(self, t: float, raw: Optional[int]):
        self.tracker.read(t, raw)
        if self.state == 'SWEEP' and self.tracker.total is not None:
            if self.start_total is None:
                self.start_total = self.tracker.total
            self.swept_deg = (self.tracker.total - self.start_total) * PAN_PER_COUNT
            if self.fall_t is not None and raw is not None and t > self.fall_t:
                self._resolve()

    def hall_edge(self, t: float, rising: bool):
        if self.state != 'SWEEP':
            return
        if rising:
            self.rise_t, self.fall_t = t, None
        elif self.rise_t is not None:
            self.fall_t = t                       # resolved at the first read after it (the reads bracket both edges)

    def _resolve(self):
        c0, c1 = self.tracker.count_at(self.rise_t), self.tracker.count_at(self.fall_t)
        self.rise_t = self.fall_t = None
        if c0 is None or c1 is None:
            return                                # a gap in the reads over the window: take the next pass
        centre = 0.5 * (c0 + c1)
        self.tracker.index_total = centre - self.calibrated_offset_deg / PAN_PER_COUNT
        self.state, self.result = 'DONE', 'homed'

    def step(self, t: float, tilt_at_zero: bool) -> float:
        if self.state == 'TILT_TO_ZERO':
            if tilt_at_zero:
                self.state = 'SWEEP'
            return 0.0
        if self.state == 'SWEEP':
            if self.swept_deg > MAX_SWEEP_DEG:
                self.state, self.result = 'FAILED', 'index not seen within %.0f deg' % MAX_SWEEP_DEG
                return 0.0
            return HOME_SPEED_DEG_S
        return 0.0


def calibrate(centre_count_total: float, true_index_total: float) -> float:
    """At assembly: the turret is set to pan 0 by eye against the magnet, then swept in +pan as in homing; the
    difference between the window's centre and the set position is stored (deg)."""
    return (centre_count_total - true_index_total) * PAN_PER_COUNT


@dataclass
class IndexCheck:
    """After homing: every pass over the index compares the count with pan 0 (mod 360)."""
    tracker: PanTracker
    calibrated_offset_deg: float = 0.0
    rise_t: Optional[float] = None
    passes: int = 0
    worst_deg: float = 0.0
    rehome: bool = False

    fall: Optional[tuple] = None
    rise_dir: int = 0

    def hall_edge(self, t: float, rising: bool, direction: int):
        """direction: the sign of the pan speed at the edge. Only a clean +pan crossing is checked (the offset is a +pan
        sweep's): both edges in +pan and the count rising between them; a pass that stops or turns back inside the
        window just counts. Resolved at the next read (`after_read`)."""
        if rising:
            self.rise_t, self.rise_dir, self.fall = t, direction, None
        elif self.rise_t is not None:
            self.fall = (t, direction)

    def after_read(self, t: float):
        if self.fall is None or t <= self.fall[0]:
            return
        (tf, direction), self.fall = self.fall, None
        c0, c1 = self.tracker.count_at(self.rise_t), self.tracker.count_at(tf)
        clean = direction > 0 and self.rise_dir > 0 and c0 is not None and c1 is not None and c1 > c0 and \
            all(b[1] >= a[1] for a, b in zip(self.tracker.samples, self.tracker.samples[1:]) if self.rise_t <= a[0] <= tf)
        self.rise_t = None
        if not clean:
            return
        pan = (0.5 * (c0 + c1) - self.tracker.index_total) * PAN_PER_COUNT - self.calibrated_offset_deg
        err = (pan + 180.0) % 360.0 - 180.0
        self.passes += 1
        self.worst_deg = max(self.worst_deg, abs(err))
        if abs(err) > RECHECK_DEG:
            self.rehome = True
