"""Bidirectional DShot300 to the two AM32 ESCs, and the eRPM telemetry that comes back on the same wire.

A frame is 16 bits: an 11-bit value, the telemetry-request bit and a 4-bit checksum. Values 48-2047 are throttle
0-100 %; 0 is 'stop' (and the zero throttle AM32 arms on); 1-47 are commands, sent only with the motor stopped (13
turns on extended telemetry, EDT). Bidirectional DShot inverts the line and the checksum, and the ESC answers every
frame with a 21-bit GCR word carrying the electrical revolution period (e: 3-bit exponent, m: 9-bit mantissa,
period = m << e microseconds, eRPM = 60e6 / period) or, with EDT, a temperature, voltage or current frame.

The firmware decodes the frames itself; the simulated ESC (sim_turret.py) encodes them, so both ends are exercised.
"""
from __future__ import annotations

from typing import Optional, Tuple

CMD_STOP = 0
CMD_EDT_ENABLE = 13
THROTTLE_MIN, THROTTLE_MAX = 48, 2047

GCR = {0x0: 0x19, 0x1: 0x1B, 0x2: 0x12, 0x3: 0x13, 0x4: 0x1D, 0x5: 0x15, 0x6: 0x16, 0x7: 0x17,
       0x8: 0x1A, 0x9: 0x09, 0xA: 0x0A, 0xB: 0x0B, 0xC: 0x1E, 0xD: 0x0D, 0xE: 0x0E, 0xF: 0x0F}
UNGCR = {v: k for k, v in GCR.items()}

EDT_TYPES = {0x2: 'temp_c', 0x4: 'volt_v', 0x6: 'current_a', 0x8: 'debug1', 0xA: 'debug2', 0xC: 'stress',
             0xE: 'status'}


def throttle_value(throttle: float) -> int:
    """0-1 throttle to the 11-bit value; exactly 0 is the stop value."""
    if throttle <= 0.0:
        return 0
    return min(THROTTLE_MAX, THROTTLE_MIN + int(round(min(1.0, throttle) * (THROTTLE_MAX - THROTTLE_MIN))))


def value_throttle(value: int) -> float:
    return 0.0 if value < THROTTLE_MIN else (value - THROTTLE_MIN) / (THROTTLE_MAX - THROTTLE_MIN)


def frame(value: int, telemetry: bool = False, bidir: bool = True) -> int:
    v = ((value & 0x7FF) << 1) | (1 if telemetry else 0)
    crc = (v ^ (v >> 4) ^ (v >> 8)) & 0x0F
    if bidir:
        crc = ~crc & 0x0F
    return (v << 4) | crc


def unframe(f: int, bidir: bool = True) -> Optional[Tuple[int, bool]]:
    """(value, telemetry bit) of a frame, or None if its checksum fails (what the ESC does with a frame)."""
    v = f >> 4
    crc = (v ^ (v >> 4) ^ (v >> 8)) & 0x0F
    if bidir:
        crc = ~crc & 0x0F
    if crc != f & 0x0F:
        return None
    return v >> 1, bool(v & 1)


def _tlm_crc(payload12: int) -> int:
    return ~(payload12 ^ (payload12 >> 4) ^ (payload12 >> 8)) & 0x0F


def encode_erpm(erpm: float) -> int:
    """The ESC's side: the 16-bit telemetry word for an eRPM (0 = stopped)."""
    period = int(round(60e6 / erpm)) if erpm >= 1.0 else 1 << 30
    if period > (0x1FE << 7):                         # slower than ~919 eRPM (131 rpm): reported as stopped
        payload = 0x0FFF
    else:
        period = max(1, period)
        e = 0
        while period > 0x1FF:
            period >>= 1
            e += 1
        payload = (e << 9) | period
    return (payload << 4) | _tlm_crc(payload)


def encode_edt(kind: str, value: int) -> int:
    t = {v: k for k, v in EDT_TYPES.items()}[kind]
    payload = (t << 8) | (value & 0xFF)
    return (payload << 4) | _tlm_crc(payload)


def decode_telemetry(word16: int, edt: bool = True):
    """('erpm', value) | (edt kind, value) | None if the checksum fails."""
    payload, crc = word16 >> 4, word16 & 0x0F
    if _tlm_crc(payload) != crc:
        return None
    if payload == 0x0FFF:
        return 'erpm', 0.0
    if edt and (payload & 0x100) == 0 and (payload >> 9) != 0:
        kind = EDT_TYPES.get(payload >> 8)
        if kind is None:
            return None
        v = payload & 0xFF
        return kind, (v * 0.25 if kind == 'volt_v' else v)
    period = (payload & 0x1FF) << (payload >> 9)
    return ('erpm', 60e6 / period) if period else None


def gcr_encode(word16: int) -> int:
    """The 21-bit line word: four GCR quintets, then transition coding (a 1 is an edge), starting high."""
    g = 0
    for k in (12, 8, 4, 0):
        g = (g << 5) | GCR[(word16 >> k) & 0xF]
    raw, bit = 1, 1
    for i in range(19, -1, -1):
        bit ^= (g >> i) & 1
        raw = (raw << 1) | bit
    return raw


def gcr_decode(raw21: int) -> Optional[int]:
    g = (raw21 ^ (raw21 >> 1)) & 0xFFFFF
    w = 0
    for k in (15, 10, 5, 0):
        n = UNGCR.get((g >> k) & 0x1F)
        if n is None:
            return None
        w = (w << 4) | n
    return w
