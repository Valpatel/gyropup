"""Fault injection: a bus wrapper that corrupts what a backend reports from a set time, so every abort of the
supervisor (rig/leg_control.py) can be shown in the simulation before the rig ever sees it (plan task T8).

    bus = FaultBus(SimBus('squat'), 'run', at=1.0)          # the pendant let go at 1 s
    python -m rig.run --backend sim --test squat --inject run@1.0
    python -m rig.run --faults                               # every fault -> exports/rig/faults.json

Kinds: run (the safety line opens), vbus_high (59 V), vbus_low (the pack at 44 V), hot (a motor at 90 C), window (the
leg reported at 90 mm), silent (the motors stop answering), fault (a motor reports over-current).
"""
from __future__ import annotations

import copy

from rig.bus import MotorBus, Tick

KINDS = ('run', 'vbus_high', 'vbus_low', 'hot', 'window', 'silent', 'fault')
EXPECT = {'run': 'sitdown', 'vbus_high': 'limp', 'vbus_low': 'sitdown', 'hot': 'sitdown', 'window': 'limp',
          'silent': 'limp', 'fault': 'limp'}


class FaultBus(MotorBus):
    def __init__(self, inner, kind: str, at: float = 1.0):
        if kind not in KINDS:
            raise ValueError(f'fault kind {kind}: one of {KINDS}')
        self.inner, self.kind, self.at = inner, kind, at
        self.tick = inner.tick

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def _corrupt(self, tk: Tick) -> Tick:
        if tk.t < self.at:
            return tk
        tk = copy.deepcopy(tk)
        k = self.kind
        if k == 'run':
            tk.run = False
        elif k == 'vbus_high':
            tk.vbus = 59.0
        elif k == 'vbus_low':
            tk.vbus = 44.0
        elif k == 'hot':
            tk.f.temp_c = 90.0
        elif k == 'window':
            import fivebar as fb
            tk.f.phi, tk.r.phi = fb.stance(90.0)                   # past the knee-out stops: 90 mm reported
        elif k == 'silent':
            tk.f.fresh = tk.r.fresh = False
        elif k == 'fault':
            tk.f.faults = ['over-current']
        return tk

    def start(self) -> Tick:
        return self._corrupt(self.inner.start())

    def step(self, tau_f, tau_r, kd=0.0) -> Tick:
        return self._corrupt(self.inner.step(tau_f, tau_r, kd))

    def power_off(self) -> None:
        self.inner.power_off()

    def stop(self) -> None:
        self.inner.stop()

    def close(self) -> None:
        self.inner.close()
