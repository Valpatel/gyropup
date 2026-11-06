"""The rig node (Adafruit Feather M4 CAN Express on the carriage post): its CAN frames and the laptop's view of them.

All 11-bit (standard) frames in 0x700-0x70F. The RS-04s on the private protocol ignore 11-bit frames, and in the MIT
protocol an 11-bit id's bits 10-8 are a command type 0-4 with the motor id in bits 7-0 (manual section 6), so 0x7xx
can reach no motor in either protocol and no motor frame (29-bit) can be taken for one of these.

    0x700  RUN     100 Hz  b0 0x5A = the safety loop is closed (the pendant held, its 12 V present), 0x00 = open;
                           b1 sequence; b2 flags: bit0 pendant closed, bit1 contactor coil powered, bit2 ToF ok,
                           bit3 load cell ok
    0x701  SENSE    50 Hz  b0-1 carriage height (ToF, mm, uint16 LE), b2 ToF range status (0 = valid),
                           b3-4 load plate force (0.1 N, int16 LE), b5 sequence
    0x702  VBUS    100 Hz  bus voltage on the motors' side of the contactor over the last 10 ms (sampled at 2 kHz):
                           b0-1 max, b2-3 min, b4-5 mean (mV, uint16 LE), b6 sequence
    0x708  HOST     50 Hz  the laptop's state for the node's LED: b0 0 idle, 1 armed, 2 running, 3 aborted; b1 seq

The laptop only drives torque while RUN frames with 0x5A are fresher than 50 ms (plan section 3.3). The pendant
alone starts nothing: the runner also asks the operator to arm.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

RUN, SENSE, VBUS, HOST = 0x700, 0x701, 0x702, 0x708
RUN_CLOSED = 0x5A
FLAGS = {0: 'pendant', 1: 'coil', 2: 'tof', 3: 'load'}
HOST_STATES = {0: 'idle', 1: 'armed', 2: 'running', 3: 'aborted'}


def pack_run(closed: bool, seq: int, flags: int = 0) -> bytes:
    return bytes((RUN_CLOSED if closed else 0x00, seq & 0xFF, flags & 0xFF))


def pack_sense(height_mm: int, tof_status: int, force_n: float, seq: int) -> bytes:
    return struct.pack('<HBhB', max(0, min(0xFFFF, int(height_mm))), tof_status & 0xFF,
                       max(-32768, min(32767, int(round(force_n * 10)))), seq & 0xFF)


def pack_vbus(vmax: float, vmin: float, vmean: float, seq: int) -> bytes:
    mv = lambda v: max(0, min(0xFFFF, int(round(v * 1000))))
    return struct.pack('<HHHB', mv(vmax), mv(vmin), mv(vmean), seq & 0xFF)


def pack_host(state: int, seq: int) -> bytes:
    return bytes((state & 0xFF, seq & 0xFF))


@dataclass
class NodeState:
    """What the laptop knows from the rig node, with the time of each frame (the bus's clock)."""
    run_closed: bool = False
    run_flags: int = 0
    t_run: Optional[float] = None
    height_mm: Optional[int] = None
    tof_ok: bool = False
    force_n: Optional[float] = None
    t_sense: Optional[float] = None
    vbus_max: Optional[float] = None
    vbus_min: Optional[float] = None
    vbus_mean: Optional[float] = None
    t_vbus: Optional[float] = None
    counts: dict = field(default_factory=lambda: {'run': 0, 'sense': 0, 'vbus': 0, 'other': 0})

    def take(self, can_id: int, data: bytes, now: float) -> bool:
        """Absorb one 11-bit frame; False if it is not a rig-node frame."""
        if can_id == RUN and len(data) >= 3:
            self.run_closed, self.run_flags, self.t_run = data[0] == RUN_CLOSED, data[2], now
            self.counts['run'] += 1
        elif can_id == SENSE and len(data) >= 6:
            h, st, f10, _ = struct.unpack('<HBhB', data[:6])
            self.height_mm, self.tof_ok, self.force_n, self.t_sense = h, st == 0, f10 / 10.0, now
            self.counts['sense'] += 1
        elif can_id == VBUS and len(data) >= 7:
            a, b, c, _ = struct.unpack('<HHHB', data[:7])
            self.vbus_max, self.vbus_min, self.vbus_mean, self.t_vbus = a / 1000, b / 1000, c / 1000, now
            self.counts['vbus'] += 1
        else:
            self.counts['other'] += 1
            return False
        return True

    def run_fresh(self, now: float, max_age: float = 0.05) -> bool:
        return self.run_closed and self.t_run is not None and now - self.t_run <= max_age

    def vbus_fresh(self, now: float, max_age: float = 0.05) -> bool:
        return self.t_vbus is not None and now - self.t_vbus <= max_age
