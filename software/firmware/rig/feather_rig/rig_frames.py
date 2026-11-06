"""The rig node's CAN frames (the same layout as rig/node.py, which the laptop decodes them with): kept in a module of
its own so CircuitPython runs it on the Feather and CPython tests it against rig/node.py (rig/tests/test_bench.py).

    0x700  RUN     100 Hz  b0 0x5A while the pendant is held (else 0x00), b1 sequence, b2 flags
                           (bit0 pendant, bit1 coil powered, bit2 ToF ok, bit3 load cell ok)
    0x701  SENSE    50 Hz  b0-1 carriage height mm (uint16 LE), b2 ToF range status (0 = valid),
                           b3-4 load force in 0.1 N (int16 LE), b5 sequence
    0x702  VBUS    100 Hz  the motors' bus over the last 10 ms: b0-1 max, b2-3 min, b4-5 mean, in mV (uint16 LE), b6 sequence
"""
import struct

RUN, SENSE, VBUS, HOST = 0x700, 0x701, 0x702, 0x708
RUN_CLOSED = 0x5A


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def pack_run(closed, seq, flags=0):
    return bytes((RUN_CLOSED if closed else 0x00, seq & 0xFF, flags & 0xFF))


def pack_sense(height_mm, tof_status, force_n, seq):
    return struct.pack('<HBhB', _clamp(int(height_mm), 0, 0xFFFF), tof_status & 0xFF,
                       _clamp(int(round(force_n * 10)), -32768, 32767), seq & 0xFF)


def pack_vbus(vmax, vmin, vmean, seq):
    def mv(v):
        return _clamp(int(round(v * 1000)), 0, 0xFFFF)
    return struct.pack('<HHHB', mv(vmax), mv(vmin), mv(vmean), seq & 0xFF)
