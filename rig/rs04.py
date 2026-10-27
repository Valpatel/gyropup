"""RobStride RS-04: the private CAN protocol (29-bit extended frames, 1 Mbit/s), a bus and motor handle, a command line.

    python -m rig.rs04 --iface can0 scan                          # every motor that answers, with its unique id
    python -m rig.rs04 --iface can0 --id 1 param                  # read every parameter of the table
    python -m rig.rs04 --iface can0 --id 1 param limit_torque     # read one
    python -m rig.rs04 --iface can0 --id 1 param limit_torque 60  # write one (volatile until 'save')
    python -m rig.rs04 --iface can0 --id 1 enable | stop | clear | zero | save | watch
    python -m rig.rs04 --iface can0 --id 127 setid 1              # a new motor arrives as 127

Where the layout comes from (the plan's task T6 asked for it to be checked against the manual before coding):
  - RS04 User Manual 260713 (RobStride Product_Information, kept locally in references/vendor/robstride-rs-04/):
    4.1 the 29-bit id: bits 28-24 the communication type, 23-8 'data area 2', 7-0 the destination address;
    4.1.1-4.1.12 every frame type; 4.1.13 the parameter table (index, type, range); 4.1.14 a worked read of loc_kp;
    4.4 the C sample (float_to_uint, the ranges P +-12.57, V +-15, T +-120, Kp 0-5000, Kd 0-100); 3.3 the
    upper-computer table (CAN_MASTER 253, the host id the motor answers by default; CAN_ID 127 from the factory);
    3.3.6 the CAN timeout (20000 = 1 s); 4.2.5 the power-off anti-backdrive 'damper'; 3.2 a worked type-18 frame.
  - RobStride's Python_Sample (github.com/RobStride/Python_Sample, MIT, read 2026-10-27): the same type numbers and
    parameter indices; the RS-04 MIT ranges +-4pi rad, +-15 rad/s, +-120 N m, Kp 5000, Kd 100.

Two small differences between the sources, and what this module does:
  - The manual scales a 16-bit field over 0..65535 (float_to_uint: (x - min) * 65535 / span, truncated); the Python
    sample uses (x / max + 1) * 32767. They differ by at most one count (0.004 N m of torque). This follows the manual.
  - The manual's table gives the angle as -4pi..4pi; its C sample uses 12.57 (4pi rounded). This uses 4pi (0.03 %).

Things the manual does not settle, marked where they are used: byte 7 of the type 23/24/25 frames (the manual lists
'01 02 03 04 05 06 F_CMD'; byte 7 is sent as 0) and the byte order of the type-21 fault words (little-endian, like
every other multi-byte value in a data field except the MIT/feedback fields, which are big-endian).

The velocity field saturates at +-15 rad/s, below the RS-04's 21-24 rad/s no-load speed: a jump's push reaches 16.7
rad/s in the simulation (exports/leg/rig-results.json), so rig/can_bus.py takes the speed from the angle's rate
whenever the reported speed sits on the rail.
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------------- communication types (manual 4.1)

GET_ID, MIT, FEEDBACK, ENABLE, STOP, SET_ZERO, SET_ID = 0, 1, 2, 3, 4, 6, 7
READ_PARAM, WRITE_PARAM, FAULT, SAVE, SET_BAUD, REPORT, SET_PROTOCOL = 17, 18, 21, 22, 23, 24, 25
TYPE_NAMES = {GET_ID: 'get id', MIT: 'mit', FEEDBACK: 'feedback', ENABLE: 'enable', STOP: 'stop', SET_ZERO: 'set zero',
              SET_ID: 'set id', READ_PARAM: 'read', WRITE_PARAM: 'write', FAULT: 'fault', SAVE: 'save',
              SET_BAUD: 'baud', REPORT: 'report', SET_PROTOCOL: 'protocol'}

HOST_ID = 0xFD             # the motors' default CAN_MASTER (manual 3.3, function code 0x200a = 253)
FACTORY_ID = 0x7F          # CAN_ID 127 out of the box (0x2009)
ID_REPLY_DEST = 0xFE       # a type-0 reply is addressed to 0xFE (4.1.1)
MODES = {0: 'reset', 1: 'calibration', 2: 'run'}
RUN_MODES = {0: 'operation (MIT)', 1: 'position (PP)', 2: 'velocity', 3: 'current', 5: 'position (CSP)'}
BAUD_CODES = {1: 1_000_000, 2: 500_000, 3: 250_000, 4: 125_000}


@dataclass(frozen=True)
class Ranges:
    """The 16-bit fields' full scale (manual 4.1.2 and 4.4 for the RS-04)."""
    p: float = 4 * math.pi        # rad, +-
    v: float = 15.0               # rad/s, +-
    t: float = 120.0              # N m, +-
    kp: float = 5000.0            # N m/rad, 0..
    kd: float = 100.0             # N m s/rad, 0..


RS04 = Ranges()
FULL = 0xFFFF


def f2u(x: float, lo: float, hi: float) -> int:
    """The manual's float_to_uint (4.4): clamp to lo..hi, scale to 0..65535, truncate. lo and hi map exactly to 0 and
    65535. NaN and infinities are refused: a motor must never be sent one."""
    if not math.isfinite(x):
        raise ValueError(f'not a finite number: {x}')
    if x <= lo:
        return 0
    if x >= hi:
        return FULL
    return int((x - lo) * FULL / (hi - lo))


def u2f(u: int, lo: float, hi: float) -> float:
    """The inverse: 0 -> lo, 65535 -> hi."""
    return lo + u * (hi - lo) / FULL


def can_id(kind: int, data2: int, dest: int) -> int:
    """A 29-bit id: type in bits 28-24, 'data area 2' in 23-8, the destination in 7-0."""
    return ((kind & 0x1F) << 24) | ((data2 & 0xFFFF) << 8) | (dest & 0xFF)


def id_fields(cid: int) -> Tuple[int, int, int]:
    """(type, data area 2, destination) of a 29-bit id."""
    return (cid >> 24) & 0x1F, (cid >> 8) & 0xFFFF, cid & 0xFF


# ----------------------------------------------------------------------------------- the parameter table (manual 4.1.13)

@dataclass(frozen=True)
class Param:
    name: str
    index: int
    kind: str                     # 'f' float32, 'B' uint8, 'H' uint16, 'I' uint32
    writable: bool
    unit: str = ''
    lo: Optional[float] = None
    hi: Optional[float] = None
    note: str = ''


PARAMS: Dict[str, Param] = {p.name: p for p in (
    Param('run_mode', 0x7005, 'B', True, '', 0, 5, '0 operation (MIT), 1 position PP, 2 velocity, 3 current, 5 position CSP'),
    Param('iq_ref', 0x7006, 'f', True, 'A', -90, 90, 'current-mode command'),
    Param('spd_ref', 0x700A, 'f', True, 'rad/s', -20, 20, 'velocity-mode command'),
    Param('limit_torque', 0x700B, 'f', True, 'N m', 0, 120, 'torque limit (the rig sets 60: D38 cap, independent of the laptop)'),
    Param('cur_kp', 0x7010, 'f', True, '', None, None, 'current loop Kp (default 0.17)'),
    Param('cur_ki', 0x7011, 'f', True, '', None, None, 'current loop Ki (default 0.012)'),
    Param('cur_filt_gain', 0x7014, 'f', True, '', 0, 1, 'current filter (default 0.1)'),
    Param('loc_ref', 0x7016, 'f', True, 'rad', None, None, 'position-mode command'),
    Param('limit_spd', 0x7017, 'f', True, 'rad/s', 0, 20, 'CSP speed limit'),
    Param('limit_cur', 0x7018, 'f', True, 'A', 0, 90, 'velocity/position-mode current limit'),
    Param('mechPos', 0x7019, 'f', False, 'rad', None, None, 'output angle'),
    Param('iqf', 0x701A, 'f', False, 'A', -90, 90, 'filtered iq'),
    Param('mechVel', 0x701B, 'f', False, 'rad/s', -15, 15, 'output speed'),
    Param('VBUS', 0x701C, 'f', False, 'V', None, None, 'bus voltage'),
    Param('loc_kp', 0x701E, 'f', True, '', None, None, 'position Kp (default 60)'),
    Param('spd_kp', 0x701F, 'f', True, '', None, None, 'speed Kp (default 6)'),
    Param('spd_ki', 0x7020, 'f', True, '', None, None, 'speed Ki (default 0.02)'),
    Param('spd_filt_gain', 0x7021, 'f', True, '', None, None, 'speed filter (default 0.1)'),
    Param('acc_rad', 0x7022, 'f', True, 'rad/s^2', None, None, 'velocity-mode acceleration (default 15)'),
    Param('vel_max', 0x7024, 'f', True, 'rad/s', None, None, 'PP speed (default 10)'),
    Param('acc_set', 0x7025, 'f', True, 'rad/s^2', None, None, 'PP acceleration (default 10)'),
    Param('EPScan_time', 0x7026, 'H', True, '', 1, None, 'active report period: 1 = 10 ms, each +1 adds 5 ms'),
    Param('canTimeout', 0x7028, 'I', True, '1/20000 s', 0, None, 'CAN watchdog: no frame for this long -> reset mode; 0 off (3.3.6)'),
    Param('zero_sta', 0x7029, 'B', True, '', 0, 1, 'power-on angle range: 0 -> 0..2pi, 1 -> -pi..pi'),
    Param('damper', 0x702A, 'B', True, '', 0, 1, 'power-off anti-backdrive damping: 0 on (default), 1 off (4.2.5)'),
    Param('add_offset', 0x702B, 'f', True, 'rad', None, None, 'zero offset'),
    Param('alveolous_open', 0x702C, 'B', True, '', 0, 1, 'cogging compensation'),
    Param('iq_test', 0x702D, 'B', True, '', 0, 1, 'longer initialisation calibration'),
    Param('dcc_set', 0x702E, 'f', True, 'rad/s^2', None, None, 'PP deceleration (default 10)'),
)}
BY_INDEX: Dict[int, Param] = {p.index: p for p in PARAMS.values()}
TIMEOUT_TICKS_PER_S = 20000


def param(name_or_index) -> Param:
    if isinstance(name_or_index, int):
        return BY_INDEX[name_or_index]
    if name_or_index in PARAMS:
        return PARAMS[name_or_index]
    low = {k.lower(): v for k, v in PARAMS.items()}
    if str(name_or_index).lower() in low:
        return low[str(name_or_index).lower()]
    raise KeyError(f'unknown RS-04 parameter {name_or_index!r}; known: {", ".join(PARAMS)}')


def pack_value(p: Param, value) -> bytes:
    """Bytes 4-7 of a type-18 frame: little-endian, a one- or two-byte value padded with zeros (manual 4.4.4-4.4.5)."""
    if p.kind == 'f':
        return struct.pack('<f', float(value))
    v = int(value)
    if v < 0 or v >= 1 << (8 * struct.calcsize(p.kind)):
        raise ValueError(f'{p.name}: {value} out of range for {p.kind}')
    return struct.pack('<' + p.kind, v).ljust(4, b'\0')


def unpack_value(p: Param, raw: bytes):
    if p.kind == 'f':
        return struct.unpack('<f', raw[:4])[0]
    return struct.unpack_from('<' + p.kind, raw)[0]


# ----------------------------------------------------------------------------------- host -> motor frames

ZERO8 = bytes(8)
MAGIC = bytes((1, 2, 3, 4, 5, 6))       # the head of the type 22-25 frames (manual 4.1.9-4.1.12)


def pack_get_id(motor: int, host: int = HOST_ID):
    return can_id(GET_ID, host, motor), ZERO8


def pack_enable(motor: int, host: int = HOST_ID):
    return can_id(ENABLE, host, motor), ZERO8


def pack_stop(motor: int, host: int = HOST_ID, clear_fault: bool = False):
    """Stop (reset mode). Byte 0 = 1 also clears the faults; it must be 0 in normal running (4.1.4)."""
    return can_id(STOP, host, motor), (b'\x01' if clear_fault else b'\x00') + bytes(7)


def pack_version(motor: int, host: int = HOST_ID):
    """The firmware version request: a type-4 frame with 00 C4 (4.1.3): it stops the motor too, so only when idle."""
    return can_id(STOP, host, motor), b'\x00\xc4' + bytes(6)


def pack_zero(motor: int, host: int = HOST_ID):
    """Set the mechanical zero at the present angle (4.1.5; not in PP mode, 4.2.6)."""
    return can_id(SET_ZERO, host, motor), b'\x01' + bytes(7)


def pack_set_id(motor: int, new_id: int, host: int = HOST_ID):
    """Give a motor a new CAN id, at once (type 7: the new id in bits 23-16)."""
    if not 1 <= new_id <= 0x7F:
        raise ValueError('a motor id is 1..127')
    return can_id(SET_ID, (new_id << 8) | host, motor), ZERO8


def pack_mit(motor: int, p: float, v: float, kp: float, kd: float, t: float, r: Ranges = RS04):
    """The operation-control (MIT) command (4.1.2): torque in the id's data area, angle, speed, Kp, Kd big-endian in
    the data. The motor runs t_ref = Kd (v - w) + Kp (p - angle) + t."""
    return (can_id(MIT, f2u(t, -r.t, r.t), motor),
            struct.pack('>HHHH', f2u(p, -r.p, r.p), f2u(v, -r.v, r.v), f2u(kp, 0.0, r.kp), f2u(kd, 0.0, r.kd)))


def pack_read(motor: int, name_or_index, host: int = HOST_ID):
    idx = param(name_or_index).index if not isinstance(name_or_index, int) else name_or_index
    return can_id(READ_PARAM, host, motor), struct.pack('<HHI', idx, 0, 0)


def pack_write(motor: int, name_or_index, value, host: int = HOST_ID):
    p = param(name_or_index)
    if not p.writable:
        raise ValueError(f'{p.name} is read-only')
    return can_id(WRITE_PARAM, host, motor), struct.pack('<HH', p.index, 0) + pack_value(p, value)


def pack_save(motor: int, host: int = HOST_ID):
    """Keep the written parameters over a power cycle (type 22; data 01..08)."""
    return can_id(SAVE, host, motor), bytes(range(1, 9))


def pack_report(motor: int, on: bool, host: int = HOST_ID):
    """Active reporting on/off (type 24; F_CMD in byte 6, byte 7 sent as 0: the manual lists seven bytes)."""
    return can_id(REPORT, host, motor), MAGIC + bytes((1 if on else 0, 0))


def pack_baud(motor: int, code: int, host: int = HOST_ID):
    """Change the bit rate after a power cycle (type 23): 1 = 1 M, 2 = 500 k, 3 = 250 k, 4 = 125 k. Not used by the rig."""
    if code not in BAUD_CODES:
        raise ValueError(f'baud code {code}: one of {sorted(BAUD_CODES)}')
    return can_id(SET_BAUD, host, motor), MAGIC + bytes((code, 0))


# ----------------------------------------------------------------------------------- motor -> host frames

FEEDBACK_FAULTS = {16: 'under-voltage', 17: 'over-current', 18: 'over-temperature', 19: 'magnetic encoder',
                   20: 'stall overload', 21: 'uncalibrated'}                     # id bits of a type-2 frame (4.1.2)
FAULT_BITS = {0: 'over-temperature (145 C)', 1: 'driver chip', 2: 'under-voltage (12 V)', 3: 'over-voltage (60 V)',
              4: 'phase B over-current', 5: 'phase C over-current', 7: 'encoder uncalibrated',
              8: 'hardware identification', 9: 'position initialisation', 14: 'stall overload',
              16: 'phase A over-current'}                                         # type-21 fault word (4.1.8)
WARNING_BITS = {0: 'over-temperature warning (135 C)'}


@dataclass
class Feedback:
    """A type-2 (or type-24 active report) frame: the motor's state."""
    motor: int
    host: int
    mode: int                     # 0 reset, 1 calibration, 2 run
    faults: int                   # the six fault bits, bit 0 = id bit 16
    p: float                      # rad (output)
    v: float                      # rad/s (saturates at +-15)
    t: float                      # N m (the motor's own estimate, from its current)
    temp_c: float
    raw: Tuple[int, int, int, int] = (0, 0, 0, 0)

    @property
    def fault_names(self) -> List[str]:
        return [n for b, n in FEEDBACK_FAULTS.items() if self.faults >> (b - 16) & 1]

    @property
    def mode_name(self) -> str:
        return MODES.get(self.mode, str(self.mode))


@dataclass
class ParamReply:
    motor: int
    host: int
    index: int
    ok: bool
    raw: bytes

    @property
    def value(self):
        p = BY_INDEX.get(self.index)
        return unpack_value(p, self.raw) if p else self.raw


@dataclass
class DeviceId:
    motor: int
    uid: bytes


@dataclass
class FaultFrame:
    motor: int
    host: int
    fault: int
    warning: int

    @property
    def names(self) -> List[str]:
        return ([n for b, n in FAULT_BITS.items() if self.fault >> b & 1]
                + [n for b, n in WARNING_BITS.items() if self.warning >> b & 1])


@dataclass
class Version:
    motor: int
    host: int
    version: str


def encode_feedback(motor: int, host: int, mode: int, faults: int, p: float, v: float, t: float, temp_c: float,
                    r: Ranges = RS04, kind: int = FEEDBACK):
    """What a motor sends (used by the software RS-04 in rig/rs04_emu.py and the tests)."""
    cid = can_id(kind, ((mode & 3) << 14) | ((faults & 0x3F) << 8) | (motor & 0xFF), host)
    temp = max(0, min(FULL, int(round(temp_c * 10))))
    return cid, struct.pack('>HHHH', f2u(p, -r.p, r.p), f2u(v, -r.v, r.v), f2u(t, -r.t, r.t), temp)


def encode_param_reply(motor: int, host: int, index: int, raw4: bytes, ok: bool = True):
    return can_id(READ_PARAM, ((0 if ok else 1) << 8) | motor, host), struct.pack('<HH', index, 0) + bytes(raw4).ljust(4, b'\0')


def encode_id_reply(motor: int, uid: bytes):
    return can_id(GET_ID, motor, ID_REPLY_DEST), bytes(uid).ljust(8, b'\0')[:8]


def encode_fault(motor: int, host: int, fault: int, warning: int = 0):
    return can_id(FAULT, motor, host), struct.pack('<II', fault, warning)


def parse(cid: int, data: bytes, r: Ranges = RS04):
    """A frame a motor sent -> Feedback | ParamReply | DeviceId | FaultFrame | Version, or None for anything else
    (including frames a host sends: see parse_request)."""
    kind, d2, dest = id_fields(cid)
    data = bytes(data)
    if kind in (FEEDBACK, REPORT) and len(data) == 8:
        motor, faults, mode = d2 & 0xFF, (d2 >> 8) & 0x3F, (d2 >> 14) & 0x3
        if data[:3] == b'\x00\xc4\x56':
            return Version(motor, dest, '.'.join(str(b) for b in data[3:7]))
        pu, vu, tu, temp = struct.unpack('>HHHH', data)
        return Feedback(motor, dest, mode, faults, u2f(pu, -r.p, r.p), u2f(vu, -r.v, r.v), u2f(tu, -r.t, r.t),
                        temp / 10.0, (pu, vu, tu, temp))
    if kind == READ_PARAM and len(data) == 8:
        # a reply: status in bits 23-16 (0 read, 1 refused), the motor in 15-8, the host in 7-0 (4.1.6, 4.1.14). A
        # host's own read request has the same shape (host in 15-8, motor in 7-0): SocketCAN never hands a socket its
        # own frames, and parse_request() is what a motor (rig/rs04_emu.py) uses.
        return ParamReply(d2 & 0xFF, dest, struct.unpack_from('<H', data)[0], (d2 >> 8) & 0xFF == 0, data[4:8])
    if kind == GET_ID and dest == ID_REPLY_DEST:
        return DeviceId(d2 & 0xFF, data)
    if kind == FAULT and len(data) == 8:
        f, w = struct.unpack('<II', data)
        return FaultFrame(d2 & 0xFF, dest, f, w)
    return None


@dataclass
class Request:
    """A frame a host sent, decoded (what the software RS-04 acts on, and the round-trip tests)."""
    kind: int
    motor: int
    host: Optional[int] = None
    fields: dict = field(default_factory=dict)


def parse_request(cid: int, data: bytes, r: Ranges = RS04) -> Optional[Request]:
    kind, d2, dest = id_fields(cid)
    data = bytes(data).ljust(8, b'\0')
    if kind == MIT:
        pu, vu, kpu, kdu = struct.unpack('>HHHH', data)
        return Request(MIT, dest, None, {'p': u2f(pu, -r.p, r.p), 'v': u2f(vu, -r.v, r.v), 'kp': u2f(kpu, 0, r.kp),
                                         'kd': u2f(kdu, 0, r.kd), 't': u2f(d2, -r.t, r.t),
                                         'raw': (pu, vu, kpu, kdu, d2)})
    host = d2 & 0xFF
    if kind == GET_ID and dest != ID_REPLY_DEST:
        return Request(GET_ID, dest, host)
    if kind == ENABLE:
        return Request(ENABLE, dest, host)
    if kind == STOP:
        if data[:2] == b'\x00\xc4':
            return Request(STOP, dest, host, {'version': True})
        return Request(STOP, dest, host, {'clear_fault': data[0] == 1})
    if kind == SET_ZERO:
        return Request(SET_ZERO, dest, host, {'zero': data[0] == 1})
    if kind == SET_ID:
        return Request(SET_ID, dest, host, {'new_id': (d2 >> 8) & 0xFF})
    if kind in (READ_PARAM, WRITE_PARAM) and (d2 >> 8) & 0xFF == 0 and dest != ID_REPLY_DEST:
        idx = struct.unpack_from('<H', data)[0]
        f = {'index': idx}
        if kind == WRITE_PARAM:
            p = BY_INDEX.get(idx)
            f['value'] = unpack_value(p, data[4:8]) if p else bytes(data[4:8])
        return Request(kind, dest, host, f)
    if kind in (SAVE, SET_BAUD, REPORT, SET_PROTOCOL):
        return Request(kind, dest, host, {'f_cmd': data[6], 'magic_ok': data[:6] == (MAGIC if kind != SAVE else bytes(range(1, 7)))})
    return None


# ----------------------------------------------------------------------------------- a bus of motors

class NoReply(RuntimeError):
    pass


class RS04Bus:
    """Several RS-04s on one transport (rig/canio.py): requests with their replies, and the control loop's exchange.
    Frames that are not a reply being waited for (the rig node's 11-bit frames, a late reply) go to `on_other`."""

    def __init__(self, transport, host: int = HOST_ID, ranges: Ranges = RS04,
                 on_other: Optional[Callable[[int, bytes, bool], None]] = None):
        self.t = transport
        self.host = host
        self.r = ranges
        self.on_other = on_other
        self.last: Dict[int, Feedback] = {}          # the newest feedback from each motor
        self.faults: Dict[int, FaultFrame] = {}      # the newest type-21 frame from each motor

    def send(self, frame) -> None:
        cid, data = frame
        self.t.send(cid, data, True)

    def _take(self, cid, data, ext):
        """Parse one received frame, keep what it says about a motor, return the parsed object (or None)."""
        if not ext:
            if self.on_other:
                self.on_other(cid, data, ext)
            return None
        m = parse(cid, data, self.r)
        if isinstance(m, Feedback):
            self.last[m.motor] = m
        elif isinstance(m, FaultFrame):
            self.faults[m.motor] = m
        elif m is None and self.on_other:
            self.on_other(cid, data, ext)
        return m

    def request(self, frame, want: Callable[[object], bool], timeout: float = 0.05):
        """Send a frame and wait for the first reply `want` accepts."""
        self.send(frame)
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise NoReply(f'no reply to a {TYPE_NAMES.get(id_fields(frame[0])[0], "?")} frame for motor '
                              f'{id_fields(frame[0])[2]} within {timeout * 1000:.0f} ms')
            f = self.t.recv(left)
            if f is None:
                continue
            m = self._take(*f)
            if m is not None and want(m):
                return m

    def drain(self, timeout: float = 0.0) -> int:
        """Read whatever is waiting (or arrives within timeout); returns how many frames."""
        n = 0
        while True:
            f = self.t.recv(timeout)
            if f is None:
                return n
            self._take(*f)
            n += 1

    def exchange(self, commands: Sequence[Tuple[int, float, float, float, float, float]], timeout: float = 0.0015
                 ) -> Dict[int, Feedback]:
        """One control tick: an MIT frame to each motor (motor, p, v, kp, kd, t), then each one's feedback. Motors that
        did not answer within timeout are missing from the result (the caller decides what a missed tick means)."""
        t0 = time.monotonic()
        for c in commands:
            self.send(pack_mit(*c, r=self.r))
        want = {c[0] for c in commands}
        got: Dict[int, Feedback] = {}
        while want - set(got):
            left = t0 + timeout - time.monotonic()
            if left <= 0:
                break
            f = self.t.recv(left)
            if f is None:
                break
            m = self._take(*f)
            if isinstance(m, Feedback) and m.motor in want:
                got[m.motor] = m
        return got

    def scan(self, ids: Iterable[int] = range(1, 128), timeout: float = 0.02) -> Dict[int, bytes]:
        """Ask every id for its unique id (type 0); returns {motor id: 8-byte uid}."""
        found = {}
        for i in ids:
            try:
                m = self.request(pack_get_id(i, self.host), lambda m, i=i: isinstance(m, DeviceId) and m.motor == i, timeout)
                found[i] = m.uid
            except NoReply:
                pass
        return found

    def motor(self, motor_id: int) -> 'Motor':
        return Motor(self, motor_id)


class Motor:
    """One RS-04 on an RS04Bus. Every call waits for the motor's answer (NoReply after the timeout)."""

    def __init__(self, bus: RS04Bus, motor_id: int, timeout: float = 0.05):
        self.bus, self.id, self.timeout = bus, motor_id, timeout

    def _fb(self, frame) -> Feedback:
        return self.bus.request(frame, lambda m: isinstance(m, Feedback) and m.motor == self.id, self.timeout)

    def enable(self) -> Feedback:
        return self._fb(pack_enable(self.id, self.bus.host))

    def stop(self, clear_fault: bool = False) -> Feedback:
        return self._fb(pack_stop(self.id, self.bus.host, clear_fault))

    def zero(self) -> Feedback:
        return self._fb(pack_zero(self.id, self.bus.host))

    def mit(self, p: float = 0.0, v: float = 0.0, kp: float = 0.0, kd: float = 0.0, t: float = 0.0) -> Feedback:
        return self._fb(pack_mit(self.id, p, v, kp, kd, t, self.bus.r))

    def read(self, name_or_index):
        p = param(name_or_index)
        m = self.bus.request(pack_read(self.id, p.index, self.bus.host),
                             lambda m: isinstance(m, ParamReply) and m.motor == self.id and m.index == p.index, self.timeout)
        if not m.ok:
            raise NoReply(f'motor {self.id} refused to read {p.name}')
        return m.value

    def write(self, name_or_index, value) -> Feedback:
        return self._fb(pack_write(self.id, name_or_index, value, self.bus.host))

    def write_check(self, name_or_index, value, tol: float = 1e-4):
        """Write, read back, and refuse to go on if the motor kept something else (the plan: configuration is written
        once and read back at start-up)."""
        self.write(name_or_index, value)
        got = self.read(name_or_index)
        if abs(float(got) - float(value)) > tol * max(1.0, abs(float(value))):
            raise RuntimeError(f'motor {self.id}: wrote {param(name_or_index).name} = {value}, read back {got}')
        return got

    def save(self) -> Feedback:
        return self._fb(pack_save(self.id, self.bus.host))

    def uid(self) -> bytes:
        return self.bus.request(pack_get_id(self.id, self.bus.host),
                                lambda m: isinstance(m, DeviceId) and m.motor == self.id, self.timeout).uid

    def version(self) -> str:
        """Firmware version (sends the type-4 version frame: stops the motor)."""
        return self.bus.request(pack_version(self.id, self.bus.host),
                                lambda m: isinstance(m, Version) and m.motor == self.id, self.timeout).version

    def set_id(self, new_id: int) -> int:
        m = self.bus.request(pack_set_id(self.id, new_id, self.bus.host),
                             lambda m: isinstance(m, DeviceId) and m.motor == new_id, self.timeout)
        self.id = new_id
        return m.motor

    def set_watchdog(self, seconds: float):
        """The motor-side CAN timeout (canTimeout, 0x7028; manual 3.3.6: 20000 = 1 s): no frame for this long and the
        motor drops to reset mode by itself. 0 turns it off."""
        return self.write_check('canTimeout', int(round(seconds * TIMEOUT_TICKS_PER_S)))


# The rig's motor settings, written and read back at every start-up (plan 4.2: configuration, not control).
RIG_CONFIG = {'run_mode': 0,            # operation (MIT) mode: the laptop sends torque only (Kp = Kd = 0)
              'limit_torque': 60.0,     # N m: D38's cap, in the motor, independent of the laptop
              'canTimeout': 2000,       # 0.1 s: a hung laptop or a pulled CAN lead stops the motor (3.3.6)
              'zero_sta': 1}            # power-on angle in -pi..pi (with 0 a link below its zero would read ~2pi)
# Read and logged at every start-up. 'damper' (0x702A, uint8) is the power-off anti-backdrive protection (manual
# 4.2.5): 0 = on (the factory default), 1 = off. It is a switch, not a level: B1 measures the back-drive torque
# against speed at both settings, and the run log records which one was in the motor.
LOGGED = ('damper', 'run_mode', 'limit_torque', 'canTimeout', 'zero_sta', 'EPScan_time', 'add_offset', 'VBUS', 'mechPos')


def configure(m: Motor, config: Optional[dict] = None, damper: Optional[int] = None, version: bool = True) -> dict:
    """Stop the motor, write the rig's settings (and the damper switch when given: B1), read every one back, and
    return what the motor holds plus its firmware version and uid: the start-up record of every run. Raises if a
    written value does not read back."""
    m.stop()
    for k, v in (RIG_CONFIG if config is None else config).items():
        m.write_check(k, v)
    if damper is not None:
        if damper not in (0, 1):
            raise ValueError('damper is a switch: 0 = power-off anti-backdrive protection on (default), 1 = off')
        m.write_check('damper', damper)
    out = {k: m.read(k) for k in LOGGED}
    out['uid'] = m.uid().hex()
    if version:
        out['firmware'] = m.version()
    out['damper_meaning'] = 'protection on' if out['damper'] == 0 else 'protection off'
    return out


# ----------------------------------------------------------------------------------- command line

def _transport(a):
    if a.iface == 'emu':                                     # a software motor, for trying the commands without hardware
        from rig.canio import VirtualBus
        from rig.rs04_emu import EmulatedRS04
        vb = VirtualBus()
        for i in a.emu_ids:
            vb.attach(EmulatedRS04(i).handle)
        return vb.port()
    from rig.canio import SocketCan
    return SocketCan(a.iface)


def _val(v) -> str:
    return f'{v:.6g}' if isinstance(v, float) else str(v)


def _fmt_fb(fb: Feedback) -> str:
    f = ', '.join(fb.fault_names) or 'no faults'
    return (f'motor {fb.motor}: {fb.mode_name}, angle {fb.p:+.4f} rad, speed {fb.v:+.3f} rad/s, torque {fb.t:+.2f} N m, '
            f'{fb.temp_c:.1f} C, {f}')


def main(argv: Optional[Sequence[str]] = None, transport=None, out=print) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.rs04', description=__doc__.split('\n\n')[0])
    ap.add_argument('--iface', default='can0', help="SocketCAN interface, or 'emu' for a software motor")
    ap.add_argument('--emu-ids', type=int, nargs='*', default=[1, 2], help='motor ids the software bus answers for')
    ap.add_argument('--host', type=lambda s: int(s, 0), default=HOST_ID)
    ap.add_argument('--id', type=int, default=1, help='motor id (127 out of the box)')
    ap.add_argument('--timeout', type=float, default=0.05)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sc = sub.add_parser('scan')
    sc.add_argument('--first', type=int, default=1)
    sc.add_argument('--last', type=int, default=127)
    sub.add_parser('enable')
    sub.add_parser('stop')
    sub.add_parser('clear', help='stop and clear the faults')
    sub.add_parser('zero', help='the present angle becomes zero (motor idle, not in PP mode)')
    sub.add_parser('save', help='keep the written parameters over a power cycle')
    sub.add_parser('version', help='firmware version (stops the motor)')
    su = sub.add_parser('setup', help="write the rig's settings (limit_torque 60, canTimeout 0.1 s, zero_sta 1, MIT mode), "
                                      'read them back with the damper switch')
    su.add_argument('--damper', type=int, choices=(0, 1), help='also set the power-off anti-backdrive switch: 0 on, 1 off')
    sid = sub.add_parser('setid')
    sid.add_argument('new_id', type=int)
    pp = sub.add_parser('param', help='read every parameter, read one, or write one')
    pp.add_argument('name', nargs='?')
    pp.add_argument('value', nargs='?')
    w = sub.add_parser('watch', help='angle, speed and bus voltage by parameter reads (the motor is not enabled)')
    w.add_argument('--hz', type=float, default=10.0)
    w.add_argument('--seconds', type=float, default=5.0)
    a = ap.parse_args(argv)
    t = transport or _transport(a)
    bus = RS04Bus(t, a.host)
    m = Motor(bus, a.id, a.timeout)
    try:
        if a.cmd == 'scan':
            found = bus.scan(range(a.first, a.last + 1), timeout=min(a.timeout, 0.05))
            if not found:
                out('no motor answered (check the 120 ohm terminators, the bit rate: ip link set can0 up type can bitrate 1000000)')
            for i, uid in sorted(found.items()):
                mm = Motor(bus, i, a.timeout)
                try:
                    extra = f", VBUS {mm.read('VBUS'):.1f} V, run_mode {mm.read('run_mode')}, limit_torque {mm.read('limit_torque'):.1f} N m"
                except NoReply as e:
                    extra = f' ({e})'
                out(f'motor {i}: uid {uid.hex()}{extra}')
            return 0 if found else 1
        if a.cmd == 'enable':
            out(_fmt_fb(m.enable()))
        elif a.cmd == 'stop':
            out(_fmt_fb(m.stop()))
        elif a.cmd == 'clear':
            out(_fmt_fb(m.stop(clear_fault=True)))
        elif a.cmd == 'zero':
            out(_fmt_fb(m.zero()))
        elif a.cmd == 'save':
            out(_fmt_fb(m.save()))
        elif a.cmd == 'version':
            out(f'motor {a.id}: firmware {m.version()}')
        elif a.cmd == 'setup':
            for k, v in configure(m, damper=a.damper).items():
                out(f'motor {a.id}: {k} = {_val(v)}')
            out(f'motor {a.id}: written values are volatile; "save" keeps them (zero_sta must be saved to act at power-on)')
        elif a.cmd == 'setid':
            out(f'motor {a.id} is now motor {m.set_id(a.new_id)}')
        elif a.cmd == 'param':
            if a.name is None:
                for p in PARAMS.values():
                    try:
                        out(f'{p.name:15} 0x{p.index:04X} = {_val(m.read(p.name)):>12} {p.unit:9} {p.note}')
                    except NoReply as e:
                        out(f'{p.name:15} 0x{p.index:04X}   ({e})')
            elif a.value is None:
                p = param(a.name)
                out(f'{p.name} = {_val(m.read(p.name))} {p.unit}')
            else:
                p = param(a.name)
                v = float(a.value) if p.kind == 'f' else int(a.value, 0)
                out(f'{p.name} = {_val(m.write_check(p.name, v))} {p.unit} (volatile until "save")')
        elif a.cmd == 'watch':
            n = max(1, int(a.seconds * a.hz))
            for _ in range(n):
                out(f"motor {a.id}: angle {m.read('mechPos'):+.4f} rad, speed {m.read('mechVel'):+.3f} rad/s, VBUS {m.read('VBUS'):.2f} V")
                time.sleep(1.0 / a.hz)
        return 0
    except NoReply as e:
        out(f'error: {e}')
        return 2
    finally:
        if transport is None:
            t.close()


if __name__ == '__main__':
    sys.exit(main())
