"""The turret firmware's numbers (docs/turret-firmware.md): the build-time constants, which only a firmware build
changes, and the runtime CONFIG the host may set over CAN (0x304), inside limits the firmware enforces.

v0 is the bench build of docs/turret-prototype-plan.md: the slip ring and continuous pan as drawn, the pulse-train
safety line, two SunnySky X2216 880 KV flywheel motors on AM32 ESCs on the fixed 12 V rail, and a third STS3215 (ID 3)
stepping the dial. Pure Python, no dependencies; the Feather port copies these numbers.

The safety numbers are build-time on purpose: the motor's KV, its pole pairs and the rail set the pre-feed eRPM limit,
and no CAN frame can raise it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

BUILD = 'v0'
CONTINUOUS_PAN = True          # the slip ring, as cad/turret.py; False is the cable-loop fallback (plan 2.4), not built

# ---------------------------------------------------------------- the servo bus (Feetech STS3215, half-duplex TTL)
SERVO_BAUD = 500_000           # over the ring (pan on ring circuit 9); the Feetech default is 1 Mbit/s
ID_PAN, ID_TILT, ID_FEED = 1, 2, 3
COUNTS = 4096                  # 12-bit absolute angle per servo turn
DEG_PER_COUNT = 360.0 / COUNTS
SERVO_READ_HZ = 100            # position reads of every servo that is on the bus
SERVO_RETRIES = 1              # a reply with a bad checksum or none is retried once, then counted as a failed read
SERVO_TORQUE_LIMIT = 500       # register 48, 0.1 % of stall: 50 % on all three (the printed pinion's cap; the dial's)
SERVO_NO_LOAD_CPS = 3072       # 45 rpm at 12 V = 270 deg/s of the servo's output, in counts/s

# drive modes (register 33, EEPROM, set once with the setup tool and only verified by the firmware):
#   pan  : step mode (3): every move one relative step from the unwrapped angle; continuous pan has no window
#   tilt : position mode (0), its angle limits = the tilt range, so the servo itself refuses a goal above level
#   feed : step mode (3): the dial steps forward for ever
MODE_POSITION, MODE_STEP = 0, 3
SERVO_MODE = {ID_PAN: MODE_STEP, ID_TILT: MODE_POSITION, ID_FEED: MODE_STEP}
STEP_REF = 'present'           # what a step-mode step is relative to: 'present' position or the last 'goal' (test 3.9)

# ---------------------------------------------------------------- pan (63:21 drive) and tilt
PAN_RATIO = 3.0                # servo turns per pan turn
PAN_PER_COUNT = DEG_PER_COUNT / PAN_RATIO
PAN_SPEED_MAX = 90.0           # deg/s: the servo's 45 rpm through 3:1
TILT_MAX_DEG = 0.0             # the barrel never points above level: every tilt goal clamps to <= 0
TILT_MIN_DEG = -25.0           # the lower hard stop
TILT_ZERO_COUNT = 2048         # tilt servo count at 0 deg (assembly step 8: the cradle on its 0 deg stop)
TILT_SIGN = -1                 # counts per degree of tilt: -1 = counts rise as the barrel depresses (assembly)
AIM_RATE_CAP = 100.0           # deg/s, pan and tilt, armed or not (D7)
AIM_TOL_DEG = 0.5              # 'reached' for the settle rule and test 6.3
SETTLE_RATE = 10.0             # fire only below this pan rate ...
SETTLE_S = 0.25                # ... and this long after the last pan command (physics findings 8, 10)
ONE_SIDED_DEG = 1.0            # every pan move ends in +pan: arriving from above, overshoot this far and come back
STRAY_TILT_DEG = -25.0         # every arm starts the ramp with the muzzle depressed (physics section 5)

# ---------------------------------------------------------------- the feed (STS3215 ID 3 under the dial floor)
FEED_ZERO_COUNT = 0            # servo count with a pocket centred over the exit hole (assembly step 10)
FEED_POCKETS = 8
FEED_STEP_COUNTS = 512         # 45 deg
FEED_SETTLE_COUNTS = 23        # 'settled': within 2.0 deg
FEED_STEP_TIMEOUT_S = 0.300    # a step not settled by then is a jam
FEED_REVERSE_COUNTS = 228      # 20 deg back from where it stuck, then the step again
FEED_DITHER_COUNTS = 114       # 10 deg: back and forward again after an empty step
FEED_MAX_JAMS = 3              # three jams in a row stop feeding (fault)
FEED_SPEED_CPS = 2608          # register 46: 4.0 rad/s, the feed rerun on the STS3215 (exports/turret/feed/
#                                feed_dyn.json: a 45 deg step settles within 2 deg in 232-246 ms; command to first
#                                touch 300-330 ms)
FEED_ACC = 0                   # register 41: 0 = no ramp, the acceleration left to the 50 % torque cap. The rerun's 60
#                                rad/s^2 (39,100 counts/s^2) is above the register's top (254 x 100 counts/s^2 = 39
#                                rad/s^2), and at 254 the step settles in ~260 ms, over the 250 ms target
FEED_JAM_LOAD = 400            # Present_Load (0.1 % of stall): 40 %, 80 % of the 50 % torque cap ...
FEED_JAM_LOAD_S = 0.060        # ... held this long ...
FEED_JAM_LOAD_IGNORE_S = 0.040  # ... after the first 40 ms of a move (the start draws the cap for ~20 ms)
FEED_LOST_READS = 5            # consecutive failed reads: the servo has left the bus (its rail was cut)
FEED_PING_S = 0.050            # ping period while the feed servo is off the bus
DROP_CHUTE_S = 0.130           # the plan's ball drop and chute, from the pocket over the hole to the nip
NIP_TO_GATE1_S = 0.012         # the nip's 4.8 ms and the bore to gate 1
FEED_SETTLE_MAX_S = 0.250      # the step's settle target
FEED_GATE_WAIT_S = math.ceil((FEED_SETTLE_MAX_S + DROP_CHUTE_S + NIP_TO_GATE1_S) * 100) / 100   # 0.40 s: GATE_1
#                                is expected within this of a step's (or a dither's) command, else the dial dithers
FEED_AFTER_SETTLE_WAIT_S = FEED_GATE_WAIT_S - 0.235   # a settle later than usual (a jam's retry) gets this long
FEED_MIN_PERIOD_S = 0.335      # step to step at least: the rerun's ~235 ms step + 100 ms with the pocket over the hole
FEED_MAX_DITHERS = 2           # two dithers without a ball: an empty step, and the dial steps on
LIFT_BELOW_DEG = -12.0         # an empty step below this tilt lifts the barrel to 0 deg for LIFT_S first
LIFT_S = 0.4
HOPPER_EMPTY_STEPS = 4         # four empty steps in a row (each after two dithers): the hopper is empty
RATE_DEFAULT, RATE_MAX = 3.0, 3.0   # balls per second: 3/s is the maximum (step ~235 ms + 100 ms rest = 335 ms)

# ---------------------------------------------------------------- the flywheels
MOTOR = 'SunnySky X2216 880KV V3'
MOTOR_KV = 880.0               # rpm/V
POLE_PAIRS = 7                 # 12N14P
RAIL_V = 12.0                  # the fixed 12 V FLY regulator: the physical ceiling
ERPM_LIMIT = round(1.10 * MOTOR_KV * RAIL_V * POLE_PAIRS)   # 81,312 eRPM = 11,616 rpm: above it, SAFE and no feed
ERPM_LIMIT_READS = 3           # consecutive telemetry reads over the limit (one corrupt frame is not a fault)
# the launch rerun on the X2216 (exports/turret/launch/launch.json 'design'): 52 fps on Ø34 at 8,855 rpm (61,985 eRPM),
# 84 % of the nominal 12 V no-load 10,499 rpm; the worst corner (KV +5 %, rail +4 %) no-load is 11,461 rpm
SET_RPM_DESIGN, SET_FPS_DESIGN, TYRE_DESIGN_MM = 8855.0, 52.0, 34
NO_LOAD_RPM_NOMINAL = 10499.0
NO_LOAD_RPM_MAX_D34 = 11180.0  # bench limit for test 4.1 (78,260 eRPM): above it a ball could pass 66 fps on Ø34
LAUNCH_RATIO = SET_FPS_DESIGN * 0.3048 / (SET_RPM_DESIGN * math.pi * TYRE_DESIGN_MM / 1000.0 / 60.0)   # 1.0054:
#                                ball speed / nominal tyre surface speed at the design point (the launch model's 0.945
#                                is per the grown, crushed contact); CONFIG carries the bench's value after test 4.4
TYRES_MM = (34,)               # Ø34 only: Ø36 reaches 70.7 fps at the worst corner, over the cap; others are refused
SET_FPS_DEFAULT = {34: 52.0}
SET_FPS_MIN, SET_FPS_MAX = 40.0, 56.0   # 56 fps = 9,536 rpm = 91 % of no-load: the trim keeps its 8 % headroom
RAMP_S = 0.300                 # spin-up ramp, 0 to the set speed: 2.51 A on the ring's +24 V pair (200 ms: 3.56 A,
#                                over test 4.5's 3 A; a stepped start: 12 A). The firmware never steps
READY_TOL = 0.05               # READY: both wheels within 5 % of the set speed ...
READY_HOLD_S = 0.050           # ... for this long
TRIM_MAX = 0.08                # the speed loop's throttle trim is bounded: a doubled rail cannot hide under it
TRIM_KP, TRIM_KI = 0.3, 2.0    # on the relative speed error (1, 1/s)
TRIM_SLEW = 0.0005             # the trim changes at most 0.05 % throttle a millisecond (bumpless at the ramp's end)
K_NL = NO_LOAD_RPM_NOMINAL / (MOTOR_KV * RAIL_V)   # 0.994: no-load / (KV x rail); test 4.3's map replaces it
ESC_ARM_S = 0.600              # zero throttle after the ESC rail comes up before any spin (AM32 arms after ~0.5 s)
TELEMETRY_STALE_S = 0.020      # no dial step on an eRPM older than this
TELEMETRY_LOST_S = 0.200       # spinning with no eRPM this long: SAFE
STRAY_WINDOW_S = 0.100         # a ball in the first 100 ms of a ramp is the stray ball of the last release
SPIN_HOLD_S = 3.0              # after a burst the wheels stay at speed this long, then stop (AM32 brake on stop)
DSHOT_RATE_HZ = 1000           # DShot300 frames (and eRPM telemetry back) per wheel

# the hardware the firmware only reports (it neither drives nor can override it)
BRAKE_DELAY_S = 0.010          # the phase-short closes 10 ms after ARM falls (74HC14 + 10 k / 1 uF) ...
BRAKE_TAU_S = 0.0069           # ... and the wheel decays with tau 6.9 ms (the X2216 model): 5 % 30 ms after ARM falls
GATE_SPACING_M = 0.060
TRIP_FPS = 66.0                # the latch's 2.98 ms window over 60 mm; the firmware's own per-shot check uses it too
CAP_FPS = 70.0                 # the hard rule
GATE_PAIR_MAX_S = 0.050        # gate 2 later than this after gate 1 is not the same ball (60 mm at 4 fps)
AFTER_RELEASE_FPS = 20.0       # a ball faster than this after a release fails test 6.7

# ---------------------------------------------------------------- the safety line
HEARTBEAT_MAX_AGE_S = 0.200    # host heartbeat older than this: zero throttle, no feed
PULSE_PERIOD_S = 0.001         # the base's 555 at 1 kHz, seen on PULSE_MON through the 4N35
PULSE_TOL = 0.15               # a 'good' period is 0.85-1.15 ms
PULSE_WINDOW_S = 0.020         # judged over the monostable's own 20 ms ...
PULSE_MIN_GOOD = 15            # ... at least 15 good periods in it, and no period shorter than 0.85 ms
PULSE_GAP_S = 0.004            # no edge for 4 ms is a release: zero throttle (AM32 brakes on stop) 16 ms before the
#                                monostable cuts the rail; a bouncing contact (< 1 ms) rides through

FPS = 0.3048                   # m/s per fps


def set_rpm(fps: float, tyre_mm: float, launch_ratio: float = LAUNCH_RATIO) -> float:
    """The flywheel speed for a ball speed: rpm = (v_set / ratio) x 60 / (pi x D)."""
    return (fps * FPS / launch_ratio) * 60.0 / (math.pi * tyre_mm / 1000.0)


def rpm_to_fps(rpm: float, tyre_mm: float, launch_ratio: float = LAUNCH_RATIO) -> float:
    return rpm * math.pi * tyre_mm / 1000.0 / 60.0 * launch_ratio / FPS


@dataclass
class Config:
    """The runtime CONFIG (0x304 rows). Everything here is bounded by the build constants above."""
    tyre_mm: int = 34
    launch_ratio: float = LAUNCH_RATIO
    mount: str = 'bench'                                         # 'bench' | 'robot' | 'box' (bench commands: 'bench')
    ring: bool = CONTINUOUS_PAN                                  # must equal the build's flag, else CONFIG_MISMATCH
    depression: List[Tuple[float, float]] = field(default_factory=list)   # (pan deg, min tilt deg), the mount's table
    keepouts: List[Tuple[float, float]] = field(default_factory=list)     # (from, to) pan deg mod 360: aim, never fire
    throttle_map: List[Tuple[float, float]] = field(default_factory=list)  # (throttle 0-1, rpm) from test 4.3

    def set_fps(self, fps: float = 0.0) -> float:
        """The requested ball speed clamped to the usable band (0 asks for the tyre's default)."""
        f = fps if fps > 0 else SET_FPS_DEFAULT[self.tyre_mm]
        return min(SET_FPS_MAX, max(SET_FPS_MIN, f))

    def rpm_for(self, fps: float = 0.0) -> float:
        return set_rpm(self.set_fps(fps), self.tyre_mm, self.launch_ratio)

    def min_tilt(self, pan_deg: float) -> float:
        """The deepest depression allowed at this pan: the table interpolated, rounded toward safety (up, 0.1 deg)."""
        if not self.depression:
            return TILT_MIN_DEG
        rows = sorted(((p % 360.0), m) for p, m in self.depression)
        p = pan_deg % 360.0
        ext = [(rows[-1][0] - 360.0, rows[-1][1])] + rows + [(rows[0][0] + 360.0, rows[0][1])]
        for (p0, m0), (p1, m1) in zip(ext, ext[1:]):
            if p0 <= p <= p1:
                m = m0 + (m1 - m0) * (p - p0) / (p1 - p0) if p1 > p0 else max(m0, m1)
                m = max(m, min(m0, m1))
                return max(TILT_MIN_DEG, math.ceil(m * 10.0) / 10.0)
        return TILT_MIN_DEG

    def in_keepout(self, pan_deg: float) -> bool:
        p = pan_deg % 360.0
        for a, b in self.keepouts:
            a, b = a % 360.0, b % 360.0
            if (a <= p <= b) if a <= b else (p >= a or p <= b):
                return True
        return False

    def throttle_for(self, rpm: float) -> float:
        """The feed-forward throttle for a wheel speed: the bench map (test 4.3) if loaded, else the no-load model."""
        m = sorted(self.throttle_map)
        if len(m) >= 2:
            if rpm <= m[0][1]:
                return max(0.0, m[0][0] * rpm / m[0][1]) if m[0][1] > 0 else 0.0
            for (t0, r0), (t1, r1) in zip(m, m[1:]):
                if r0 <= rpm <= r1:
                    return t0 + (t1 - t0) * (rpm - r0) / (r1 - r0) if r1 > r0 else t0
            return 1.0
        return min(1.0, rpm / (MOTOR_KV * RAIL_V * K_NL))
