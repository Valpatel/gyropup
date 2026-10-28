"""The CAN backend on a simulated rig: two software RS-04s (rig/rs04_emu.py) on an in-memory CAN bus, their angles and
speeds taken from the MuJoCo rig (rig/sim_bus.py) every tick, the rig node's RUN and VBUS frames sent as the Feather
would, and the contactor opened at a set time. Everything rig/can_bus.py does on the real bus (the frames, the
16-bit quantisation, the calibration's zero and direction, the 15 rad/s speed rail, the start-up configuration, a
missing reply) runs against the same physics as the simulation backend.

    link = HilLink(SimBus('jump', latency_ticks=0), cal)
    bus = CanBus(link.port, cal, realtime=False, clock=link.clock, after_exchange=link.advance)
    link.begin(); tk = bus.start(); ...
"""
from __future__ import annotations

from typing import Optional

from rig import rs04 as P
from rig.canio import VirtualBus
from rig.node import RUN, VBUS, pack_run, pack_vbus
from rig.rs04_emu import EmulatedRS04


class HilLink:
    def __init__(self, sim, cal, cut_at: Optional[float] = None, run_closed: bool = True,
                 drop: Optional[callable] = None):
        self.sim = sim
        self.cal = cal
        self.cut_at = cut_at                       # plant time the contactor opens (None: never)
        self.run_closed = run_closed               # the pendant held
        self.t = 0.0
        self.vb = VirtualBus()
        self.vb.drop = drop
        self.emu = {mc.id: EmulatedRS04(mc.id, clock=self.clock, plant=None) for mc in (cal.front, cal.rear)}
        for e in self.emu.values():
            self.vb.attach(e.handle)
        self.port = self.vb.port()                 # the laptop's transport
        self.node = self.vb.port()                 # the rig node's
        self.seq = 0
        self.cut = False
        self.tk = None

    def clock(self) -> float:
        return self.t

    def begin(self):
        self.tk = self.sim.start()
        self._sync()
        return self.tk

    def _sync(self) -> None:
        tk = self.tk
        for mc, st in ((self.cal.front, tk.f), (self.cal.rear, tk.r)):
            e = self.emu[mc.id]
            e.offset = 0.0
            e.angle = (st.phi - mc.phi_zero) / mc.dir
            e.speed = st.w / mc.dir
            e.temp_c = st.temp_c
            if tk.vbus is not None:
                e.vbus = tk.vbus
        self.seq += 1
        self.node.send(RUN, pack_run(self.run_closed, self.seq, 0b1111 if self.run_closed else 0), False)
        if tk.vbus is not None:
            self.node.send(VBUS, pack_vbus(tk.vbus, tk.vbus, tk.vbus, self.seq), False)

    def advance(self) -> None:
        """Called by CanBus after each exchange: run the plant one tick with what the motors were told."""
        if self.cut_at is not None and not self.cut and self.t >= self.cut_at - 1e-9:
            self.cut = True
            self.sim.power_off()
            for e in self.emu.values():
                e.mute = True                      # an unpowered motor answers nothing
        taus, kd = [], 0.0
        for mc in (self.cal.front, self.cal.rear):
            e = self.emu[mc.id]
            p, v, kp, kdm, t_ff = e.cmd
            on = e.mode == 2 and not e.fault_word and not e.mute
            lim = min(float(e.params['limit_torque']), P.RS04.t)
            taus.append(mc.dir * max(-lim, min(lim, t_ff)) if on else 0.0)
            kd = max(kd, kdm if on else 0.0)
        self.tk = self.sim.step(taus[0], taus[1], kd)
        self.t = self.tk.t
        self._sync()
