"""The real motor bus: two RS-04s over SocketCAN (rig/rs04.py), at a fixed real-time tick.

    cal = Calibration.load()                                  # rig/calibration.json, made by rig/calibrate.py
    bus = CanBus(SocketCan('can0'), cal)
    tk = bus.start()                                          # configure (limit_torque 60, canTimeout 0.1 s, ...),
    tk = bus.step(tau_f, tau_r)                               # read back and log, enable; then one MIT exchange a tick

Each tick sends both MIT frames (Kp = 0; Kd only when asked) at the scheduled time and returns the motors' replies:
the state when the command arrived, so a command acts one tick after the state it was computed from (the simulation
backend models the same with latency_ticks=1). Missing replies are not waited for past ~75 % of the tick: the tick
comes back with `fresh` False and the supervisor counts it.

Angles: phi = phi_zero + dir * angle_motor (rig/calibration.json: each motor zeroed with its upper link on the bare
knee-out stop post). Speed: the motor's own, except when it sits on the 16-bit field's +-15 rad/s rail (a jump's push
reaches 16.7 rad/s): then the angle's rate over the tick. Bus voltage: the rig node's 0x702 frame when it is fresh
(the max of the last 10 ms, so a regeneration spike is seen), else a VBUS read from one motor every `vbus_every`
ticks. The safety line: the rig node's RUN frame, fresher than 50 ms.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from rig import rs04 as P
from rig.bus import MotorBus, MotorState, Tick
from rig.node import HOST, NodeState, pack_host

R = Path(__file__).resolve().parents[1]
CAL_FILE = R / 'rig' / 'calibration.json'
V_RAIL = P.RS04.v * 0.997            # rad/s: a reported speed this close to +-15 is the field's rail, not a measurement


@dataclass
class MotorCal:
    id: int
    dir: int                          # +1: the motor's positive angle turns phi up
    phi_zero: float                   # rad: the leg angle at the motor's zero

    def to_leg(self, p: float) -> float:
        return self.phi_zero + self.dir * p

    def to_motor_torque(self, tau_leg: float) -> float:
        return self.dir * tau_leg


@dataclass
class Calibration:
    front: MotorCal
    rear: MotorCal
    note: str = ''

    @classmethod
    def load(cls, path: Path = CAL_FILE) -> 'Calibration':
        d = json.loads(Path(path).read_text())
        return cls(MotorCal(**d['front']), MotorCal(**d['rear']), d.get('note', ''))

    def save(self, path: Path = CAL_FILE) -> None:
        Path(path).write_text(json.dumps({'front': asdict(self.front), 'rear': asdict(self.rear), 'note': self.note}, indent=1) + '\n')


@dataclass
class Timing:
    late_ms: list = field(default_factory=list)       # send time after the schedule
    rtt_ms: list = field(default_factory=list)        # first command sent -> last reply in
    missed: int = 0

    def summary(self) -> dict:
        def pct(v, q):
            s = sorted(v)
            return round(s[min(len(s) - 1, int(q * len(s)))], 3) if s else None
        return {'ticks': len(self.rtt_ms), 'missed': self.missed, 'late_ms_p50': pct(self.late_ms, 0.5),
                'late_ms_p99': pct(self.late_ms, 0.99), 'rtt_ms_p50': pct(self.rtt_ms, 0.5), 'rtt_ms_p99': pct(self.rtt_ms, 0.99),
                'within_0p3ms': (round(sum(1 for x in self.late_ms if abs(x) <= 0.3) / len(self.late_ms), 4) if self.late_ms else None)}


class CanBus(MotorBus):
    def __init__(self, transport, cal: Calibration, tick: float = 0.002, host: int = P.HOST_ID,
                 clock: Callable[[], float] = time.monotonic, realtime: bool = True, vbus_every: int = 25,
                 config: Optional[dict] = None, damper: Optional[int] = None, require_node: bool = True,
                 after_exchange: Optional[Callable[[], None]] = None):
        self.t = transport
        self.cal = cal
        self.tick = tick
        self.clock = clock
        self.realtime = realtime
        self.vbus_every = vbus_every
        self.config = config
        self.damper = damper
        self.require_node = require_node
        self.after_exchange = after_exchange          # the HIL link advances its plant here
        self.node = NodeState()
        self.bus = P.RS04Bus(transport, host, on_other=self._other)
        self.timing = Timing()
        self.startup: Dict[str, dict] = {}
        self.k = 0
        self.prev: Dict[int, tuple] = {}              # motor id -> (angle, t) for the rate fallback
        self.unwrap: Dict[int, float] = {}
        self.last: Dict[int, MotorState] = {}
        self.vbus_motor: Optional[float] = None
        self.powered = True
        self.host_state = 0

    # ------------------------------------------------------------- frames that are not motor replies
    def _other(self, cid, data, ext):
        if not ext:
            self.node.take(cid, bytes(data), self.clock())

    # ------------------------------------------------------------- the bus
    def start(self) -> Tick:
        for name, mc in (('front', self.cal.front), ('rear', self.cal.rear)):
            self.startup[name] = P.configure(P.Motor(self.bus, mc.id), self.config, self.damper)
        for mc in (self.cal.front, self.cal.rear):
            P.Motor(self.bus, mc.id).enable()
        self.t0 = self.clock()
        self.next = self.t0
        self.host_state = 2
        return self._exchange(0.0, 0.0, 0.0)

    def step(self, tau_f: float, tau_r: float, kd: float = 0.0) -> Tick:
        self.next += self.tick
        if self.realtime:
            self._wait(self.next)
        if not self.powered:
            return self._exchange(0.0, 0.0, 0.0)
        return self._exchange(tau_f, tau_r, kd)

    def power_off(self) -> None:
        """The laptop cannot open the contactor (the pendant does, through the off-delay relay): it stops driving."""
        self.powered = False
        self.stop()

    def stop(self) -> None:
        self.host_state = 3 if self.host_state == 2 else self.host_state
        for mc in (self.cal.front, self.cal.rear):
            try:
                self.bus.send(P.pack_stop(mc.id, self.bus.host))
            except OSError:
                pass
        self.bus.drain(0.002)

    def close(self) -> None:
        self.stop()
        self.t.close()

    # ------------------------------------------------------------- one tick
    def _wait(self, deadline: float) -> None:
        while True:
            left = deadline - self.clock()
            if left <= 0:
                return
            if left > 0.0006:
                time.sleep(left - 0.0005)
            else:
                while self.clock() < deadline:
                    pass
                return

    def _exchange(self, tau_f: float, tau_r: float, kd: float) -> Tick:
        cf, cr = self.cal.front, self.cal.rear
        t_send = self.clock()
        if self.k:
            self.timing.late_ms.append((t_send - self.next) * 1000)
        cmds = [(cf.id, 0.0, 0.0, 0.0, kd, cf.to_motor_torque(tau_f)), (cr.id, 0.0, 0.0, 0.0, kd, cr.to_motor_torque(tau_r))]
        got = self.bus.exchange(cmds, timeout=0.75 * self.tick)
        t_rx = self.clock()
        self.timing.rtt_ms.append((t_rx - t_send) * 1000)
        if len(got) < 2:
            self.timing.missed += 1
        if self.after_exchange:
            self.after_exchange()
        if self.k % self.vbus_every == self.vbus_every - 1 and not self.node.vbus_fresh(t_rx):
            mc = (cf, cr)[(self.k // self.vbus_every) % 2]
            try:
                self.vbus_motor = P.Motor(self.bus, mc.id, timeout=0.5 * self.tick).read('VBUS')
            except P.NoReply:
                pass
        if self.k % 10 == 0:
            try:
                self.t.send(HOST, pack_host(self.host_state, self.k // 10), False)
            except OSError:
                pass
        self.bus.drain(0.0)
        states = [self._state(mc, got.get(mc.id), t_rx) for mc in (cf, cr)]
        self.k += 1
        now = t_rx
        if self.node.vbus_fresh(now):
            vbus = self.node.vbus_max
        else:
            vbus = self.vbus_motor
        run = self.node.run_fresh(now) if self.require_node else True
        extra = {'node': {'height_mm': self.node.height_mm, 'tof_ok': self.node.tof_ok, 'force_n': self.node.force_n,
                          'vbus_mean': self.node.vbus_mean, 'vbus_min': self.node.vbus_min},
                 'rtt_ms': self.timing.rtt_ms[-1]}
        return Tick(t=t_send - self.t0 if self.k > 1 else 0.0, f=states[0], r=states[1], vbus=vbus, run=run, extra=extra)

    def _state(self, mc: MotorCal, fb: Optional[P.Feedback], now: float) -> MotorState:
        if fb is None:
            old = self.last.get(mc.id)
            if old is None:
                return MotorState(float('nan'), 0.0, 0.0, float('nan'), 'missing', [], fresh=False)
            return MotorState(old.phi, old.w, old.tau, old.temp_c, 'missing', old.faults, fresh=False)
        p = fb.p
        if mc.id in self.unwrap:                                  # continuous through the +-4pi wrap
            q = self.unwrap[mc.id]
            p = q + ((p - q + 4 * math.pi) % (8 * math.pi) - 4 * math.pi)
        self.unwrap[mc.id] = p
        w = fb.v
        prev = self.prev.get(mc.id)
        if abs(w) >= V_RAIL and prev is not None and now > prev[1]:
            w = (p - prev[0]) / (now - prev[1])                   # the speed field is on its rail: use the angle's rate
        self.prev[mc.id] = (p, now)
        st = MotorState(mc.to_leg(p), mc.dir * w, mc.dir * fb.t, fb.temp_c, fb.mode_name, fb.fault_names, fresh=True)
        self.last[mc.id] = st
        return st
