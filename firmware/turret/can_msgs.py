"""The turret's CAN message set (docs/turret-firmware.md section 6): the 0x300 block, classic CAN at 1 Mbit/s,
little-endian, every payload at most 8 bytes. Shared by the firmware reference and the host (bench_host.py).

v0 against the set as written: the C610's DJI frames (0x200/0x201) are gone with the C610; POSE is packed into 8
bytes (it was 10, which classic CAN cannot carry: the rates are now whole deg/s); 0x317 EVENT is new (per-event data
the bench needs: each homing's index centre, each dial step's settle time and load, each SAFE's cause and latency);
COMMAND gains bench codes (accepted only with CONFIG mount = bench); CONFIG, FIRE, FEED and POWER keep their IDs and
have their fields pinned down.
"""
from __future__ import annotations

import struct
from typing import Dict, Tuple

MSGS: Dict[int, Tuple[str, str, Tuple[str, ...]]] = {
    0x300: ('HOST_HEARTBEAT', '<BBB', ('counter', 'host_state', 'flags')),            # flags bit0: arm request
    0x301: ('AIM', '<ihB', ('pan_cdeg', 'tilt_cdeg', 'rate')),                        # rate: pan/tilt limit, deg/s
    0x302: ('FIRE', '<BBHB', ('balls', 'rate_d', 'fps_d', 'req')),                    # rate 0.1/s; fps 0.1 (0: default)
    0x303: ('LASER', '<B', ('on',)),
    0x304: ('CONFIG', '<BBhh', ('kind', 'index', 'a', 'b')),
    0x305: ('COMMAND', '<BHHB', ('code', 'a', 'b', 'c')),
    0x310: ('TURRET_HEARTBEAT', '<BHBB', ('state', 'faults', 'flags', 'seq')),
    0x311: ('POSE', '<ihbb', ('pan_cdeg', 'tilt_cdeg', 'pan_rate', 'tilt_rate')),     # rates deg/s, saturating
    0x312: ('WHEELS', '<HHBB', ('rpm_l', 'rpm_r', 'temp_l', 'temp_r')),
    0x313: ('SHOT', '<HHHB', ('shot', 'fps_d', 'rpm', 'flags')),
    0x314: ('FEED', '<HBBBB', ('balls', 'empty', 'jams', 'flags', 'dial')),           # dial: 360/256 deg units
    0x315: ('POWER', '<HBBB', ('bus_mv', 'pan_dv', 'tilt_dv', 'feed_dv')),            # servo supply, 0.1 V; 0 = absent
    0x316: ('HEALTH', '<BBBHHB', ('tec', 'rec', 'busoff', 'ring_drops', 'servo_err', 'index_worst')),
    0x317: ('EVENT', '<BBHHH', ('code', 'seq', 'a', 'b', 'c')),
}
IDS = {v[0]: k for k, v in MSGS.items()}

STATES = ('BOOT', 'HOMING', 'IDLE', 'ARMED', 'SPIN_UP', 'READY', 'FIRING', 'SAFE', 'FAULT')

# TURRET_HEARTBEAT.faults (u16): the present causes and the latched faults
F_HOME_FAILED, F_REHOME, F_FEED_JAM, F_FEED_MISSING = 1 << 0, 1 << 1, 1 << 2, 1 << 3
F_ERPM_LIMIT, F_OVERSPEED, F_TRIP, F_TELEMETRY = 1 << 4, 1 << 5, 1 << 6, 1 << 7
F_PULSE, F_PAN_MISSING, F_TILT_MISSING, F_SERVO_CONFIG = 1 << 8, 1 << 9, 1 << 10, 1 << 11
F_HEARTBEAT, F_HOPPER_EMPTY, F_CONFIG_MISMATCH, F_ARM_LOW = 1 << 12, 1 << 13, 1 << 14, 1 << 15
FAULT_NAMES = {F_HOME_FAILED: 'home failed', F_REHOME: 're-home asked', F_FEED_JAM: 'feed jammed 3x',
               F_FEED_MISSING: 'feed servo missing', F_ERPM_LIMIT: 'eRPM over the limit', F_OVERSPEED: 'ball > 66 fps',
               F_TRIP: 'trip latched', F_TELEMETRY: 'eRPM telemetry lost', F_PULSE: 'safety pulses bad',
               F_PAN_MISSING: 'pan servo missing', F_TILT_MISSING: 'tilt servo missing',
               F_SERVO_CONFIG: 'servo EEPROM wrong', F_HEARTBEAT: 'host heartbeat stale',
               F_HOPPER_EMPTY: 'hopper empty', F_CONFIG_MISMATCH: 'CONFIG does not match the build',
               F_ARM_LOW: 'ARM low'}

# TURRET_HEARTBEAT.flags (u8)
(H_ARM, H_TRIP, H_HOMED, H_PULSE_OK, H_HOST_ARMED, H_REARM_WAIT, H_FEED_ONLINE,
 H_WHEELS_READY) = (1 << k for k in range(8))

# SHOT.flags
S_STRAY, S_OVERSPEED, S_AFTER_RELEASE, S_GATE1_ONLY, S_THROTTLE_MODE, S_DOUBLE = (1 << k for k in range(6))

# FEED.flags
FD_HOPPER_FULL, FD_FAULT, FD_ONLINE, FD_HOPPER_EMPTY = (1 << k for k in range(4))

# COMMAND.code
CMD_REHOME, CMD_STOP, CMD_SPIN_DOWN, CMD_CLEAR_FAULTS = 1, 2, 3, 4
CMD_BENCH_FEED_STEPS = 0x10      # a: steps, b: rate 0.1/s; the dial alone, no wheels (test 3.9)
CMD_BENCH_SPIN = 0x11            # a: throttle 0.1 %, b: hold 0.1 s; the wheels alone, open loop (4.1, 4.6, 4.7)
CMD_BENCH_FIRE_THROTTLE = 0x12   # a: throttle 0.1 %, b: balls, c: rate 0.1/s; balls at an open-loop throttle (4.2, 4.3)
CMD_BENCH_STREAM = 0x13          # a: POSE frames per s, b: seconds (3.8: 1,000 frames/s)
CMD_BENCH_SPIN_SPEED = 0x14      # a: fps x 10 (0: default), b: hold 0.1 s; the wheels at the set speed, no feed
#                                  (4.7, 4.8)
CMD_BENCH_FIRE_ANY_AIM = 0x15    # a: balls, b: fps x 10 (0: default), c: rate 0.1/s; a burst that does not wait for a
#                                  settled aim (test 5.1's panning pose); every safety condition still applies

# CONFIG.kind
(CF_DEPRESSION, CF_KEEPOUT, CF_TYRE, CF_RING, CF_MOUNT, CF_LAUNCH_RATIO, CF_THROTTLE_MAP,
 CF_CLEAR) = 1, 2, 3, 4, 5, 6, 7, 8
MOUNTS = ('bench', 'robot', 'box')

# EVENT.code
EV_HOMED, EV_HOME_FAILED, EV_FEED_STEP, EV_FEED_JAM, EV_FEED_FAULT, EV_FEED_EMPTY = 1, 2, 3, 4, 5, 6
EV_SAFE, EV_SERVO_LOST, EV_SERVO_BACK, EV_BURST_DONE, EV_DITHER, EV_STRAY = 7, 8, 9, 10, 11, 12
EV_REHOME_ASKED, EV_PULSE_BAD, EV_BENCH_DONE, EV_SHOT_REFUSED, EV_LIFT = 13, 14, 15, 16, 17
BURST_END = {'complete': 1, 'hopper empty': 2, 'feed fault': 3, 'aborted': 4}


def pack(name: str, **kw) -> Tuple[int, bytes]:
    cid = IDS[name]
    _, fmt, fields = MSGS[cid]
    return cid, struct.pack(fmt, *(int(kw.get(f, 0)) for f in fields))


def unpack(cid: int, data: bytes) -> Tuple[str, dict]:
    name, fmt, fields = MSGS[cid]
    return name, dict(zip(fields, struct.unpack(fmt, bytes(data[:struct.calcsize(fmt)]))))


def sat(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


assert all(struct.calcsize(f) <= 8 for _, f, _ in MSGS.values())
