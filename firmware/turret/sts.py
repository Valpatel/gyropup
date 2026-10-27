"""Feetech STS3215 serial-bus protocol: packets, the register map, and the bus master the firmware uses.

Half-duplex TTL through the 74AHCT125 (direction on D4), 500 kbit/s over the ring. A packet is
FF FF ID LEN INSTR PARAMS... CHECKSUM with LEN = len(PARAMS) + 2 and CHECKSUM = ~(ID + LEN + INSTR + sum(PARAMS)) & FF;
a status reply has the error byte where the instruction was. Multi-byte registers are little-endian; signed values use
bit 15 (positions, speeds) or bit 10 (load) as the sign, not two's complement.

Register addresses are the Feetech STS memory table as used by the common open-source drivers (SCServo, LeRobot); the
bench's first job (test 3.9) confirms them on the parts in hand.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

PING, READ, WRITE, REG_WRITE, ACTION, SYNC_READ, SYNC_WRITE = 0x01, 0x02, 0x03, 0x04, 0x05, 0x82, 0x83
BROADCAST = 0xFE

# EEPROM area (addresses below 40; written only by the setup tool with LOCK = 0)
R_ID, R_BAUD = 5, 6
R_MIN_ANGLE, R_MAX_ANGLE = 9, 11
R_MAX_TORQUE = 16
R_PROT_CURRENT = 28
R_OFFSET = 31
R_MODE = 33
# RAM area
R_TORQUE_ENABLE = 40
R_ACC = 41
R_GOAL_POS = 42
R_GOAL_TIME = 44
R_GOAL_SPEED = 46
R_TORQUE_LIMIT = 48
R_LOCK = 55
R_PRESENT_POS = 56
R_PRESENT_SPEED = 58
R_PRESENT_LOAD = 60
R_PRESENT_VOLTAGE = 62
R_PRESENT_TEMP = 63
R_MOVING = 66
R_PRESENT_CURRENT = 69

BAUD_CODE = {1_000_000: 0, 500_000: 1, 250_000: 2, 128_000: 3, 115_200: 4, 76_800: 5, 57_600: 6, 38_400: 7}

# status error bits
E_VOLTAGE, E_ANGLE, E_OVERHEAT, E_OVERLOAD = 0x01, 0x02, 0x04, 0x20


def checksum(body: bytes) -> int:
    return (~sum(body)) & 0xFF


def packet(sid: int, instr: int, params: bytes = b'') -> bytes:
    body = bytes([sid & 0xFF, len(params) + 2, instr & 0xFF]) + bytes(params)
    return b'\xff\xff' + body + bytes([checksum(body)])


def parse(buf: Optional[bytes]) -> Optional[Tuple[int, int, bytes]]:
    """(id, instruction or error byte, params) of the first well-formed packet in buf, or None (short, bad checksum)."""
    if not buf:
        return None
    i = buf.find(b'\xff\xff')
    if i < 0 or len(buf) < i + 6:
        return None
    sid, n = buf[i + 2], buf[i + 3]
    if n < 2 or len(buf) < i + 4 + n:
        return None
    body = buf[i + 2:i + 4 + n - 1]
    if checksum(body) != buf[i + 3 + n]:
        return None
    return sid, body[2], bytes(body[3:])


def u16(v: int) -> bytes:
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def sm16(v: int, sign_bit: int = 15) -> bytes:
    """Sign-magnitude encoding (Feetech): |v| with the sign in bit 15 (positions, speeds, steps)."""
    return u16((abs(v) & ((1 << sign_bit) - 1)) | ((1 << sign_bit) if v < 0 else 0))


def from_sm(v: int, sign_bit: int = 15) -> int:
    mag = v & ((1 << sign_bit) - 1)
    return -mag if v & (1 << sign_bit) else mag


def le16(b: bytes, i: int = 0) -> int:
    return b[i] | (b[i + 1] << 8)


class Master:
    """The firmware's end of the bus. `txn(packet) -> reply or None` is the half-duplex transfer the board provides
    (UART write, direction flip, read with a timeout). A missing or corrupt reply is retried SERVO_RETRIES times and
    counted; the counters go to the HEALTH frame (servo bus errors) and test 3.6."""

    def __init__(self, txn: Callable[[bytes], Optional[bytes]], retries: int = 1):
        self.txn = txn
        self.retries = retries
        self.transactions = 0
        self.retried = 0          # transfers that needed a retry (checksum or timeout)
        self.failed = 0           # transfers that failed after the retries

    def _do(self, sid: int, instr: int, params: bytes = b'', expect: int = 0) -> Optional[bytes]:
        pkt = packet(sid, instr, params)
        for k in range(self.retries + 1):
            self.transactions += 1
            p = parse(self.txn(pkt))
            if p is not None and p[0] == sid and len(p[2]) == expect:
                return p[2]
            if k < self.retries:
                self.retried += 1
        self.failed += 1
        return None

    def ping(self, sid: int, count: bool = True) -> bool:
        """count=False: a presence probe (the feed servo while its rail is off), not a bus error when unanswered."""
        if count:
            return self._do(sid, PING) is not None
        self.transactions += 1
        p = parse(self.txn(packet(sid, PING)))
        return p is not None and p[0] == sid

    def read(self, sid: int, addr: int, n: int) -> Optional[bytes]:
        return self._do(sid, READ, bytes([addr, n]), expect=n)

    def write(self, sid: int, addr: int, data: bytes) -> bool:
        """A write with its status reply. Not retried when the servo may already have acted on it: callers that write
        relative steps use write_once and check the position instead."""
        return self._do(sid, WRITE, bytes([addr]) + bytes(data)) is not None

    def write_once(self, sid: int, addr: int, data: bytes) -> Optional[bool]:
        """One transfer, no retry: True = acknowledged, None = no valid reply (it may or may not have been applied)."""
        self.transactions += 1
        p = parse(self.txn(packet(sid, WRITE, bytes([addr]) + bytes(data))))
        if p is not None and p[0] == sid:
            return True
        self.failed += 1
        return None

    # helpers ---------------------------------------------------------------------------------------------------
    def read_pos(self, sid: int) -> Optional[int]:
        b = self.read(sid, R_PRESENT_POS, 2)
        return None if b is None else from_sm(le16(b)) % 4096

    def read_pos_speed_load(self, sid: int) -> Optional[Tuple[int, int, int]]:
        """Position (0-4095), speed (counts/s, signed) and load (0.1 % of stall, signed) in one read."""
        b = self.read(sid, R_PRESENT_POS, 6)
        if b is None:
            return None
        return from_sm(le16(b, 0)) % 4096, from_sm(le16(b, 2)), from_sm(le16(b, 4), 10)

    def read_voltage(self, sid: int) -> Optional[float]:
        b = self.read(sid, R_PRESENT_VOLTAGE, 1)
        return None if b is None else b[0] / 10.0

    def read_eeprom(self, sid: int) -> Optional[dict]:
        """The fields the firmware verifies at every (re)init: mode and angle limits."""
        a = self.read(sid, R_MIN_ANGLE, 4)
        m = self.read(sid, R_MODE, 1)
        if a is None or m is None:
            return None
        return {'min_angle': le16(a, 0), 'max_angle': le16(a, 2), 'mode': m[0]}
