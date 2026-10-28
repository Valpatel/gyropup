"""The balance firmware's host build (libgp_host.so, src/host/gp_host.c) through ctypes.

    fw = Firmware.load()                 # finds the library (GP_FW_HOST_LIB, or the usual build directories)
    fw.configure(profile=RIG, motors=[(1, A, -1, phi0), ...], leg_ff_n=...)
    fw.init(0)
    mcu_run = fw.tick(now_us, stop_run=True)
    for bus, cid, data, ext in fw.tx(): ...
    fw.can_rx(bus, cid, data, ext, now_us); fw.ina228(v, i, now_us); fw.vn100(...)
    s = fw.snapshot()                    # gp_snapshot as a ctypes structure
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
from typing import Iterator, Optional, Sequence, Tuple

FW = Path(__file__).resolve().parents[1]
REPO = FW.parents[1]
ROBOT, RIG = 0, 1
BUS_A, BUS_B, BUS_C = 0, 1, 2
MODES = ('boot', 'idle', 'arming', 'run', 'jump', 'sit', 'settle', 'limp')
REASONS = {0: 'none', 1: 'stop', 2: 'link', 3: 'people', 4: 'uvlo', 5: 'jetson', 6: 'vbus stale', 7: 'cut-off', 10: 'motor missing',
           11: 'motor fault', 12: 'leg window', 13: 'over-voltage', 14: 'imu', 15: 'fallen', 16: 'arm timeout'}
JUMP_REFUSALS = {0: 'ok', 1: 'people near', 2: 'voltage', 3: 'not running', 4: 'link', 5: 'height 0'}
FLAG_JUMP_OK, FLAG_UVLO_WARN, FLAG_UVLO_SIT = 0x40, 0x10, 0x20


class Frame(C.Structure):
    _fields_ = [('id', C.c_uint32), ('len', C.c_uint8), ('ext', C.c_uint8), ('data', C.c_uint8 * 8)]


U, F = C.c_uint32, C.c_float


class Snapshot(C.Structure):
    _fields_ = ([(n, U) for n in ('t_us', 'mode', 'reason', 'flags', 'jump_phase', 'jump_refusal', 'jumps', 'jumps_refused',
                                  'boot_mask', 'latched', 'link_ok', 'people', 'mcu_run', 'stop_run', 'uvlo_warn', 'uvlo_sat')]
                + [(n, F) for n in ('vbus', 'ibus', 'vrest', 'jump_scale', 'jump_v_target')]
                + [('L', F * 2), ('th', F * 2), ('L_cmd', F * 2), ('tau', F * 4), ('wheel', F * 2), ('wheel_current', F * 2)]
                + [(n, F) for n in ('theta', 'theta_dot', 'v', 'x_err', 'height')]
                + [('phi', F * 4), ('w', F * 4), ('misses', U * 4)]
                + [(n, U) for n in ('tx_drops', 'can_rx', 'imu_packets', 'imu_crc_errors', 'cutoff')]
                + [(n, F) for n in ('vload', 'iavg', 'ilimit', 'bus_scale', 'push_ilimit', 'push_scale')])


def library_candidates() -> list:
    env = os.environ.get('GP_FW_HOST_LIB')
    c = [Path(env)] if env else []
    c += [REPO / 'build' / 'fw-host' / 'libgp_host.so', FW / 'build-host' / 'libgp_host.so',
          Path('/mnt/storage-10tb/claude-scratch/gyropup/body/fw/build-host/libgp_host.so')]
    return c


def find_library() -> Optional[Path]:
    return next((p for p in library_candidates() if p.exists()), None)


class Firmware:
    def __init__(self, path: Path):
        self.path = Path(path)
        L = self.lib = C.CDLL(str(self.path))
        L.gp_host_sizeof.restype = C.c_uint
        L.gp_host_set.argtypes = [C.c_char_p, C.c_float]
        L.gp_host_set_motor.argtypes = [C.c_int, C.c_int, C.c_int, C.c_int, C.c_float]
        L.gp_host_init.argtypes = [C.c_uint32]
        L.gp_host_tick.argtypes = [C.c_uint32, C.c_int]
        L.gp_host_tx_pop.argtypes = [C.POINTER(C.c_uint8), C.POINTER(Frame)]
        L.gp_host_can_rx.argtypes = [C.c_uint8, C.POINTER(Frame), C.c_uint32]
        L.gp_host_ina228.argtypes = [C.c_float, C.c_float, C.c_uint32]
        L.gp_host_vn100.argtypes = [C.c_float] * 6 + [C.c_uint32]
        L.gp_host_snapshot.argtypes = [C.POINTER(Snapshot)]
        L.gp_host_jump_scale.argtypes = [C.c_float]
        L.gp_host_jump_scale.restype = C.c_float
        for which, cls in ((0, Frame), (1, Snapshot)):
            got = L.gp_host_sizeof(which)
            if got != C.sizeof(cls):
                raise RuntimeError(f'{self.path}: {cls.__name__} is {got} bytes in C, {C.sizeof(cls)} here: fwlib.py is stale')
        self._f = Frame()
        self._bus = C.c_uint8()
        self._snap = Snapshot()

    @classmethod
    def load(cls) -> 'Firmware':
        p = find_library()
        if p is None:
            raise FileNotFoundError('libgp_host.so not built: cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host')
        return cls(p)

    def configure(self, profile: int, motors: Sequence[Tuple[int, int, int, float]] = (), **numbers) -> None:
        self.lib.gp_host_default(profile)
        for i, (mid, bus, d, phi0) in enumerate(motors):
            self.lib.gp_host_set_motor(i, mid, bus, d, phi0)
        for k, v in numbers.items():
            if not self.lib.gp_host_set(k.encode(), float(v)):
                raise KeyError(k)

    def init(self, now_us: int) -> None:
        self.lib.gp_host_init(now_us)

    def tick(self, now_us: int, stop_run: bool = True) -> bool:
        return bool(self.lib.gp_host_tick(now_us & 0xFFFFFFFF, 1 if stop_run else 0))

    def tx(self) -> Iterator[Tuple[int, int, bytes, bool]]:
        while self.lib.gp_host_tx_pop(C.byref(self._bus), C.byref(self._f)):
            f = self._f
            yield self._bus.value, f.id, bytes(f.data[:f.len]), bool(f.ext)

    def can_rx(self, bus: int, cid: int, data: bytes, ext: bool, now_us: int) -> None:
        f = self._f
        f.id, f.len, f.ext = cid, len(data), 1 if ext else 0
        for k, b in enumerate(bytes(data)[:8]):
            f.data[k] = b
        self.lib.gp_host_can_rx(bus, C.byref(f), now_us & 0xFFFFFFFF)

    def ina228(self, vbus: float, current_in_to_out: float, now_us: int) -> None:
        self.lib.gp_host_ina228(vbus, current_in_to_out, now_us & 0xFFFFFFFF)

    def vn100(self, yaw: float, pitch: float, roll: float, gx: float, gy: float, gz: float, now_us: int) -> None:
        self.lib.gp_host_vn100(yaw, pitch, roll, gx, gy, gz, now_us & 0xFFFFFFFF)

    def snapshot(self) -> Snapshot:
        self.lib.gp_host_snapshot(C.byref(self._snap))
        return self._snap

    def jump_scale(self, vrest: float) -> float:
        return float(self.lib.gp_host_jump_scale(vrest))
