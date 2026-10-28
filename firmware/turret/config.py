"""The turret firmware's numbers (docs/turret-firmware.md): the build-time constants, which only a firmware build
changes, and the runtime CONFIG the host may set over CAN (0x304), inside limits the firmware enforces.

v0 is the bench build of docs/turret-prototype-plan.md: the slip ring and continuous pan as drawn, the pulse-train
safety line, two SunnySky X2216 1400 KV flywheel motors on AM32 ESCs on the trimmed flywheel rail (D68: a Hasbro
Rival round at 95-100 fps, every accepted ball under 105 fps by the rail itself), and a third STS3215 (ID 3) stepping
the dial. Pure Python, no dependencies; the Feather port copies these numbers.

The safety numbers are build-time on purpose: the motor, its pole pairs and the bench's trimmed no-load speed set the
pre-feed eRPM limit, and no CAN frame can raise it. None of them is the ceiling: the rail is (docs/turret-plan.md 2.10).
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
MOTOR = 'SunnySky X2216 1400KV V3'
MOTOR_KV = 1400.0              # rpm/V
POLE_PAIRS = 7                 # 12N14P
RAIL_V = 11.31                 # the flywheel rail for a nominal 1400 KV (TDK i6A4W, one fixed trim resistor per turret:
#                                10.8-11.9 V for KV +-5 %): the physical ceiling. The firmware cannot change it
# D68 (exports/turret/launch/launch.json 'trim', launch3d.json 'ceiling'): the bench trims the rail so the faster motor,
# warm, turns NO_LOAD_RPM_TRIM at 100 % throttle; the Hasbro ball then leaves at 97.1 fps flat out, and with the magnets
# 15 C warmer and the rail 2 % high (16,330 rpm) the fastest accepted ball at 103.9 and the densest (2.0 g on 22.2 mm)
# at 2,480 J/m^2, under ASTM F963's 2,500 (that limit binds first). At NO_LOAD_RPM_ASTM the densest ball would reach
# 2,500 J/m^2 and at NO_LOAD_RPM_105 the fastest 105 fps: the eRPM guard sits at the lower
NO_LOAD_RPM_TRIM = 15722.0     # 110,054 eRPM: the trim target, and test 4.1's limit (the faster motor, warm, at 100 %)
NO_LOAD_RPM_MAX = NO_LOAD_RPM_TRIM   # bench limit for test 4.1: above it the trim resistor is changed, never a ball fired
NO_LOAD_RPM_105 = 16496.0      # n_105 (launch3d.json ceiling): the no-load speed at which the fastest accepted ball leaves at 105
NO_LOAD_RPM_ASTM = 16390.0     # n_astm (launch3d.json ceiling): ... and the densest reaches 2,500 J/m^2
ERPM_LIMIT = round(min(NO_LOAD_RPM_105, NO_LOAD_RPM_ASTM) * POLE_PAIRS)   # 114,730 eRPM: above it, SAFE and no feed
ERPM_LIMIT_READS = 3           # consecutive telemetry reads over the limit (one corrupt frame is not a fault)
# the design point (exports/turret/launch/launch.json 'design'): 95 fps for the Hasbro ball on Ø38 at 15,286 rpm
# (107,002 eRPM), 97 % of the trimmed no-load speed
SET_RPM_DESIGN, SET_FPS_DESIGN, TYRE_DESIGN_MM = 15286.0, 95.0, 38
FULL_THROTTLE_FPS = 97.1       # the Hasbro ball at 100 % on the trimmed rail
LAUNCH_RATIO = SET_FPS_DESIGN * 0.3048 / (SET_RPM_DESIGN * math.pi * TYRE_DESIGN_MM / 1000.0 / 60.0)   # 0.952:
#                                ball speed / tyre surface speed at the design point; CONFIG carries the bench's value
#                                after test 4.4
TYRES_MM = (38,)               # Ø38 only (D68: 40 % crush on this cage); others are refused (Ø40 crushes 49 % and
#                                reaches 108.5 fps at the worst corner; Ø36 leaves a Hasbro ball at 82)
SET_FPS_DEFAULT = {38: 95.0}
SET_FPS_MIN, SET_FPS_MAX = 40.0, 100.0  # 100 fps asks for more than the rail gives a Hasbro ball (97.1): the wheels run
#                                flat out on the rail, which is the ceiling, and READY holds (within 5 %)
RAMP_S = 0.800                 # spin-up ramp, 0 to the set speed: the wheels hold 3.2 times the energy they did at 52 fps
#                                (19.4 J for the pair at 95 fps); 0.8 s keeps the peak at ~98 W from the input (6.5 A from
#                                one DCB609 at 15 V, 2.7 A from the 10S bus; 0.3 s would be ~190 W). The firmware never steps
READY_TOL = 0.05               # READY: both wheels within 5 % of the set speed ...
READY_HOLD_S = 0.050           # ... for this long
TRIM_MAX = 0.08                # the speed loop's throttle trim is bounded: a doubled rail cannot hide under it
TRIM_KP, TRIM_KI = 0.3, 2.0    # on the relative speed error (1, 1/s)
TRIM_SLEW = 0.0005             # the trim changes at most 0.05 % throttle a millisecond (bumpless at the ramp's end)
K_NL = NO_LOAD_RPM_TRIM / (MOTOR_KV * RAIL_V)   # 0.993: no-load / (KV x rail); test 4.3's map replaces it
ESC_ARM_S = 0.600              # zero throttle after the ESC rail comes up before any spin (AM32 arms after ~0.5 s)
TELEMETRY_STALE_S = 0.020      # no dial step on an eRPM older than this
TELEMETRY_LOST_S = 0.200       # spinning with no eRPM this long: SAFE
STRAY_WINDOW_S = 0.100         # a ball in the first 100 ms of a ramp is the stray ball of the last release
SPIN_HOLD_S = 3.0              # after a burst the wheels stay at speed this long, then stop (AM32 brake on stop)
DSHOT_RATE_HZ = 1000           # DShot300 frames (and eRPM telemetry back) per wheel

# the hardware the firmware only reports (it neither drives nor can override it)
BRAKE_DELAY_S = 0.008          # the phase-short closes ~8 ms after ARM falls (5-14 ms: 74HCT14 + 6.8 k / 1 uF) ...
BRAKE_TAU_S = 0.0233           # ... and the wheel decays with an effective tau of 23 ms: the 1400 KV's short through two FETs
                               # and the taps (tau 18 ms at low speed: the FETs' and taps' 56 mOhm are now half the loop)
                               # and its winding's inductance at speed (14 uH est): 5 % about 80 ms after ARM falls on the
                               # short alone, from 15,286 rpm (docs/turret-physics.md section 5)
GATE_SPACING_M = 0.060
TRIP_FPS = 105.0               # D68: the latch's 1.87 ms window over 60 mm; the firmware's own per-shot check uses it too
CAP_FPS = 105.0                # D68: the ceiling, held by the trimmed rail (no accepted ball leaves faster)
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

# ---------------------------------------------------------------- the robot's depression table (mount 'robot')
# cad/turret_lidar.py's firmware_table for the VLP-16 143 mm ahead of the pan axis with its top 41.7 mm above the TM
# face (exports/turret/lidar/lidar.json, 2026-10-27; the 143 is the body's LIDAR_TO_PAN, docs/body-plan.md 1.5): the
# rows that limit the depression and a full-range row either side, which clamp exactly as the file's 73 rows do (the
# firmware interpolates between rows). A Config with mount 'robot' and no table loaded uses it, so the robot is never
# without one; a table loaded over CAN (host.py --mount robot sends the file's rows) replaces it.
ROBOT_DEPRESSION = ((-35.0, -25.0), (-30.0, -23.0), (-25.0, -19.5), (-20.0, -18.0), (-15.0, -17.0), (-10.0, -16.5),
                    (-5.0, -16.5), (0.0, -16.5), (5.0, -16.5), (10.0, -16.5), (15.0, -17.0), (20.0, -18.0),
                    (25.0, -19.5), (30.0, -23.0), (35.0, -25.0))
ROBOT_DEPRESSION_FOR = {'lidar_to_pan_mm': 143.0, 'lidar_top_above_tm_mm': 41.7, 'margin_mm': 10.0,
                        'file': 'exports/turret/lidar/lidar.json'}


def set_rpm(fps: float, tyre_mm: float, launch_ratio: float = LAUNCH_RATIO) -> float:
    """The flywheel speed for a ball speed: rpm = (v_set / ratio) x 60 / (pi x D)."""
    return (fps * FPS / launch_ratio) * 60.0 / (math.pi * tyre_mm / 1000.0)


def rpm_to_fps(rpm: float, tyre_mm: float, launch_ratio: float = LAUNCH_RATIO) -> float:
    return rpm * math.pi * tyre_mm / 1000.0 / 60.0 * launch_ratio / FPS


@dataclass
class Config:
    """The runtime CONFIG (0x304 rows). Everything here is bounded by the build constants above."""
    tyre_mm: int = 38
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
        """The deepest depression allowed at this pan: the table interpolated, rounded toward safety (up, 0.1 deg).
        With no table loaded, mount 'robot' holds ROBOT_DEPRESSION and the other mounts the full range."""
        table = self.depression or (ROBOT_DEPRESSION if self.mount == 'robot' else ())
        if not table:
            return TILT_MIN_DEG
        rows = sorted(((p % 360.0), m) for p, m in table)
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
        return min(1.0, rpm / NO_LOAD_RPM_TRIM)
