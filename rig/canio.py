"""CAN transports: Linux SocketCAN from the standard library (no python-can needed) and an in-memory bus for tests.

    t = SocketCan('can0')               # after: sudo ip link set can0 up type can bitrate 1000000
    t.send(0x0300FD01, bytes(8))        # 29-bit id (extended=True is the default)
    t.recv(0.002)                       # -> (can_id, data, extended) or None on timeout

    bus = VirtualBus(); host = bus.port(); bus.attach(device.handle)    # a software device answers at once

Both give the same two calls, so rig/rs04.py and rig/can_bus.py never know which one they talk to. The BIGTREETECH U2C
and the FYSETC UCAN run candleLight firmware: Linux sees them as gs_usb, a native SocketCAN interface.
"""
from __future__ import annotations

import collections
import socket
import struct
import threading
import time
from typing import Callable, Optional, Tuple

Frame = Tuple[int, bytes, bool]          # (can_id without flag bits, data, extended)

# linux/can.h
CAN_EFF_FLAG = 0x80000000
CAN_RTR_FLAG = 0x40000000
CAN_ERR_FLAG = 0x20000000
CAN_EFF_MASK = 0x1FFFFFFF
CAN_SFF_MASK = 0x000007FF
_FRAME = struct.Struct('=IB3x8s')        # struct can_frame: id, dlc, 3 pad, 8 data


def encode_frame(can_id: int, data: bytes, extended: bool = True) -> bytes:
    """The 16-byte struct can_frame the kernel takes."""
    if len(data) > 8:
        raise ValueError('a classic CAN frame carries at most 8 bytes')
    cid = (can_id & CAN_EFF_MASK) | CAN_EFF_FLAG if extended else can_id & CAN_SFF_MASK
    return _FRAME.pack(cid, len(data), bytes(data).ljust(8, b'\0'))


def decode_frame(raw: bytes) -> Optional[Frame]:
    """(id, data, extended) from a struct can_frame; None for remote and error frames."""
    cid, dlc, data = _FRAME.unpack(raw[:16])
    if cid & (CAN_RTR_FLAG | CAN_ERR_FLAG):
        return None
    ext = bool(cid & CAN_EFF_FLAG)
    return (cid & CAN_EFF_MASK if ext else cid & CAN_SFF_MASK), data[:min(dlc, 8)], ext


class SocketCan:
    """A raw SocketCAN socket. The kernel does not echo our own frames back to us (CAN_RAW_RECV_OWN_MSGS is off)."""

    def __init__(self, iface: str = 'can0'):
        self.iface = iface
        self.s = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.s.bind((iface,))
        self._timeout = -1.0

    def send(self, can_id: int, data: bytes, extended: bool = True) -> None:
        self.s.send(encode_frame(can_id, data, extended))

    def recv(self, timeout: Optional[float]) -> Optional[Frame]:
        """One frame, or None when nothing came within timeout (s; None blocks, 0 polls)."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            left = None if deadline is None else max(0.0, deadline - time.monotonic())
            if left != self._timeout:
                self.s.settimeout(left)
                self._timeout = left
            try:
                raw = self.s.recv(16)
            except (socket.timeout, BlockingIOError):
                return None
            f = decode_frame(raw)
            if f is not None:
                return f
            if deadline is not None and time.monotonic() >= deadline:
                return None

    def close(self) -> None:
        self.s.close()


class VirtualPort:
    """One node's view of a VirtualBus: what it sends reaches every other port and every attached handler."""

    def __init__(self, bus: 'VirtualBus'):
        self.bus = bus
        self.q: collections.deque = collections.deque()
        self.cv = threading.Condition()

    def _put(self, f: Frame) -> None:
        with self.cv:
            self.q.append(f)
            self.cv.notify()

    def send(self, can_id: int, data: bytes, extended: bool = True) -> None:
        self.bus.deliver(self, (can_id & (CAN_EFF_MASK if extended else CAN_SFF_MASK), bytes(data), extended))

    def recv(self, timeout: Optional[float]) -> Optional[Frame]:
        with self.cv:
            if not self.q:
                if timeout == 0:
                    return None
                self.cv.wait_for(lambda: bool(self.q), timeout)
            return self.q.popleft() if self.q else None

    def close(self) -> None:
        pass


class VirtualBus:
    """An in-memory CAN bus. Handlers (software devices) are called synchronously on every frame and return the frames
    they answer with, which are delivered at once: a request's reply is waiting before send() returns. `log` keeps
    every frame (for tests); `drop` is a predicate that loses frames (fault injection)."""

    def __init__(self, log: bool = False):
        self.ports: list = []
        self.handlers: list = []
        self.log: Optional[list] = [] if log else None
        self.drop: Optional[Callable[[Frame], bool]] = None

    def port(self) -> VirtualPort:
        p = VirtualPort(self)
        self.ports.append(p)
        return p

    def attach(self, handler: Callable[[int, bytes, bool], list]) -> None:
        self.handlers.append(handler)

    def deliver(self, src, f: Frame) -> None:
        if self.drop and self.drop(f):
            return
        if self.log is not None:
            self.log.append(f)
        for p in self.ports:
            if p is not src:
                p._put(f)
        for h in self.handlers:
            if h is src:
                continue
            for cid, data, *ext in h(*f) or ():
                self.deliver(h, (cid, bytes(data), ext[0] if ext else True))
