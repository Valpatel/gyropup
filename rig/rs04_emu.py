"""A software RS-04: answers the private protocol the way the manual describes (rig/rs04.py has the sources), so the
driver, the CAN backend and the command line can be exercised without a motor.

    from rig.canio import VirtualBus
    vb = VirtualBus(); m1 = EmulatedRS04(1); vb.attach(m1.handle)
    python -m rig.rs04 --iface emu --emu-ids 1 2 scan

It holds the state a real motor reports (mode, angle, speed, torque, temperature, faults, the parameter table) and runs
the MIT law t = Kd (v_set - w) + Kp (p_set - angle) + t_ff, clipped to limit_torque, while in run mode. The angle and
speed come from a small built-in plant (the rotor's reflected inertia and a little friction) or from outside:
`plant = None` and set .angle / .speed yourself (rig/can_bus.py's simulated-motor mode does that from MuJoCo).

What is assumed (not in the manual): the parameter defaults it does not list (limit_torque 120 N m, VBUS 48 V), a
firmware version string, and that canTimeout counts from the last frame addressed to this motor.
"""
from __future__ import annotations

import math
import os
import time
from typing import Callable, List, Optional

from rig import rs04 as P

DEFAULTS = {'run_mode': 0, 'iq_ref': 0.0, 'spd_ref': 0.0, 'limit_torque': 120.0, 'cur_kp': 0.17, 'cur_ki': 0.012,
            'cur_filt_gain': 0.1, 'loc_ref': 0.0, 'limit_spd': 10.0, 'limit_cur': 23.0, 'iqf': 0.0, 'loc_kp': 60.0,
            'spd_kp': 6.0, 'spd_ki': 0.02, 'spd_filt_gain': 0.1, 'acc_rad': 15.0, 'vel_max': 10.0, 'acc_set': 10.0,
            'EPScan_time': 1, 'canTimeout': 0, 'zero_sta': 0, 'damper': 0, 'add_offset': 0.0, 'alveolous_open': 0,
            'iq_test': 0, 'dcc_set': 10.0}


class EmulatedRS04:
    def __init__(self, motor_id: int = P.FACTORY_ID, host: int = P.HOST_ID, uid: Optional[bytes] = None,
                 clock: Callable[[], float] = time.monotonic, plant: Optional[str] = 'inertia',
                 inertia: float = 3.0e-4 * 81, friction: float = 0.3, viscous: float = 0.05, vbus: float = 48.0):
        self.id = motor_id
        self.host = host
        self.uid = uid or os.urandom(8)
        self.clock = clock
        self.plant = plant
        self.J, self.coulomb, self.b = inertia, friction, viscous
        self.mode = 0
        self.params = dict(DEFAULTS)
        self.saved = dict(DEFAULTS)
        self.angle = 0.0                  # rad, output, absolute
        self.speed = 0.0                  # rad/s
        self.offset = 0.0                 # the mechanical zero
        self.temp_c = 28.0
        self.vbus = vbus
        self.fault_word = 0
        self.cmd = (0.0, 0.0, 0.0, 0.0, 0.0)   # p, v, kp, kd, t
        self.applied = 0.0
        self.last_rx = clock()
        self.last_step = clock()
        self.version = (0, 4, 1, 24)      # the manual's example table shows AppCodeVersion 0.4.1.24
        self.frames_seen = 0
        self.mute = False                 # fault injection: stop answering (a lead pulled out)

    # ------------------------------------------------------------- state as the motor reports it
    @property
    def position(self) -> float:
        p = self.angle - self.offset + self.params['add_offset']
        lim = 4 * math.pi
        return (p + lim) % (2 * lim) - lim                    # the type-2 angle loops within -4pi..4pi (4.2.3)

    def feedback_faults(self) -> int:
        bits = 0
        if self.fault_word & (1 << 2):
            bits |= 1 << 0                                     # under-voltage
        if self.fault_word & ((1 << 4) | (1 << 5) | (1 << 16)):
            bits |= 1 << 1                                     # over-current
        if self.fault_word & 1:
            bits |= 1 << 2                                     # over-temperature
        if self.fault_word & (1 << 14):
            bits |= 1 << 4                                     # stall overload
        if self.fault_word & (1 << 7):
            bits |= 1 << 5                                     # uncalibrated
        return bits

    def _feedback(self):
        return P.encode_feedback(self.id, self.host, self.mode, self.feedback_faults(), self.position, self.speed,
                                 self.applied, self.temp_c)

    # ------------------------------------------------------------- the motor's own behaviour
    def watchdog(self, now: float) -> None:
        to = self.params['canTimeout']
        if to and self.mode == 2 and now - self.last_rx > to / P.TIMEOUT_TICKS_PER_S:
            self.mode = 0                                      # 3.3.6: the motor enters reset mode
            self.applied = 0.0

    def torque(self, now: Optional[float] = None) -> float:
        """The output torque now (N m): the MIT law in run mode, nothing otherwise."""
        now = self.clock() if now is None else now
        self.watchdog(now)
        if self.vbus > 60.0:
            self.fault_word |= 1 << 3                          # over-voltage: the drive stops
        if self.mode != 2 or self.fault_word:
            self.applied = 0.0
            return 0.0
        p, v, kp, kd, t = self.cmd
        tau = kd * (v - self.speed) + kp * (p - self.position) + t
        lim = min(float(self.params['limit_torque']), P.RS04.t)
        self.applied = max(-lim, min(lim, tau))
        return self.applied

    def step(self, now: Optional[float] = None) -> None:
        """Advance the built-in plant to `now`."""
        now = self.clock() if now is None else now
        dt = max(0.0, now - self.last_step)
        self.last_step = now
        if self.plant != 'inertia' or dt == 0.0:
            return
        n = max(1, int(dt / 2e-4))
        h = dt / n
        for _ in range(n):
            tau = self.torque(now)
            fr = self.coulomb * (1 if self.speed > 0 else -1 if self.speed < 0 else 0) + self.b * self.speed
            if self.speed == 0.0 and abs(tau) <= self.coulomb:
                continue
            self.speed += (tau - fr) / self.J * h
            self.angle += self.speed * h

    # ------------------------------------------------------------- the protocol
    def handle(self, cid: int, data: bytes, extended: bool = True) -> List[tuple]:
        """A frame on the bus -> the frames this motor answers with."""
        if not extended or self.mute:
            return []                                          # the private protocol ignores 11-bit frames
        req = P.parse_request(cid, data)
        if req is None or req.motor != self.id:
            return []
        now = self.clock()
        self.step(now)
        self.last_rx = now
        self.frames_seen += 1
        k = req.kind
        if k == P.GET_ID:
            return [P.encode_id_reply(self.id, self.uid)]
        if k == P.ENABLE:
            if not self.fault_word:
                self.mode = 2
            return [self._feedback()]
        if k == P.STOP:
            if req.fields.get('version'):
                cid2 = P.can_id(P.FEEDBACK, self.id, self.host)
                return [(cid2, b'\x00\xc4\x56' + bytes(self.version) + b'\x00')]
            self.mode = 0
            self.applied = 0.0
            if req.fields.get('clear_fault'):
                self.fault_word = 0
            return [self._feedback()]
        if k == P.SET_ZERO:
            if self.params['run_mode'] != 1 and req.fields.get('zero'):
                self.offset = self.angle + self.params['add_offset']
                p0, v0, kp0, kd0, t0 = self.cmd
                self.cmd = (0.0, v0, kp0, kd0, t0)             # 4.2.6: the target becomes 0, the motor stays put
            return [self._feedback()]
        if k == P.SET_ID:
            self.id = req.fields['new_id']
            return [P.encode_id_reply(self.id, self.uid)]
        if k == P.MIT:
            f = req.fields
            self.cmd = (f['p'], f['v'], f['kp'], f['kd'], f['t'])
            self.torque(now)
            return [self._feedback()]
        if k == P.READ_PARAM:
            p = P.BY_INDEX.get(req.fields['index'])
            if p is None:
                return [P.encode_param_reply(self.id, self.host, req.fields['index'], bytes(4), ok=False)]
            live = {'mechPos': self.position, 'mechVel': self.speed, 'VBUS': self.vbus, 'iqf': self.applied / 2.1}
            v = live.get(p.name, self.params.get(p.name, 0))
            return [P.encode_param_reply(self.id, self.host, p.index, P.pack_value(p, v))]
        if k == P.WRITE_PARAM:
            p = P.BY_INDEX.get(req.fields['index'])
            if p is not None and p.writable:
                v = req.fields['value']
                if p.lo is not None:
                    v = max(p.lo, v)
                if p.hi is not None:
                    v = min(p.hi, v)
                self.params[p.name] = v
            return [self._feedback()]
        if k == P.SAVE:
            self.saved = dict(self.params)
            return [self._feedback()]
        return [self._feedback()]

    def power_cycle(self) -> None:
        """What survives a power cycle: the saved parameters and the zero (an assumption: the manual's zero is set
        with type 6 and kept by the drive)."""
        self.params = dict(self.saved)
        self.mode = 0
        self.applied = 0.0
        self.cmd = (0.0, 0.0, 0.0, 0.0, 0.0)
