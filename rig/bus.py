"""The motor bus the leg controller talks to: two RS-04s at a fixed tick, on CAN (rig/can_bus.py) or simulated in
MuJoCo (rig/sim_bus.py). The controller cannot tell which one it drives.

    bus = SimBus('stand_up')                 # or CanBus(...)
    tk = bus.start()                         # the state at t = 0
    while tk.t < 3.0:
        tk = bus.step(tau_f, tau_r)          # hold these output torques for one tick, return the state a tick later
    bus.stop()

Angles are the leg's motor angles (cad/fivebar.py: phi1 front, phi2 rear, radians, rear continuous -183..-83 deg),
torques are at the motor outputs in the same sense (+ turns phi up). Each backend maps them onto its motors.

The torques are pure feed-forward (the RS-04's MIT Kp = 0; plan section 4.2): the laptop's virtual-model controller
is the only loop. `kd` is the motor's own damping term (MIT Kd), allowed as a safety damper and for aborts.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MotorState:
    phi: float                  # rad, the leg's motor angle
    w: float                    # rad/s
    tau: float                  # N m, what the motor reports (its own estimate from its current)
    temp_c: float
    mode: str = 'run'           # reset | calibration | run | off | missing
    faults: List[str] = field(default_factory=list)
    fresh: bool = True          # False when this tick's feedback did not arrive (the values are the last ones)


@dataclass
class Tick:
    t: float                    # s since start()
    f: MotorState               # front motor (phi1)
    r: MotorState               # rear motor (phi2)
    vbus: Optional[float]       # V (None when the backend has no fresh reading)
    run: bool = True            # the safety line (pendant) is closed and the rig node's RUN frames are fresh
    extra: dict = field(default_factory=dict)   # backend-specific: the simulation's ground truth, the rig node's sensors

    @property
    def ok(self) -> bool:
        return self.f.fresh and self.r.fresh


class MotorBus(ABC):
    tick: float = 0.002

    @abstractmethod
    def start(self) -> Tick:
        ...

    @abstractmethod
    def step(self, tau_f: float, tau_r: float, kd: float = 0.0) -> Tick:
        ...

    @abstractmethod
    def power_off(self) -> None:
        """Take the motors' power away (the contactor on the rig; the simulation's power-off model)."""

    @abstractmethod
    def stop(self) -> None:
        """Motors to their stopped (reset) state: no torque."""

    def close(self) -> None:
        self.stop()


@dataclass
class Pack:
    """The FLEXVOLT pack behind the motors, simply: an open-circuit voltage behind a resistance. The bus current is
    the motors' electrical power over the voltage; regeneration (negative power) lifts the voltage. Used by the
    simulation backend so the VBUS window can trip there as it would on the rig. Pack(54, 0) is sim.leg_rig's ideal
    54 V bus (what rig-results.json assumes)."""
    v_oc: float = 50.0          # V: the jump rule's start (V_start <= 57.5 - 27 A x r_int; docs/leg-bench-tests.md)
    r_int: float = 0.25         # ohm: a FLEXVOLT in 60 V mode is one string of 15 cells (~15 mOhm each) plus the
                                # leads, fuse and contactor: an estimate until the rig's first jumps measure it
    r_phase: float = 0.12       # ohm: RS-04 winding, line to line (an estimate)
    kt: float = 2.1             # N m per A rms at the output (manual 1.3)
    idle_w: float = 4.0         # W per motor (drive electronics)

    def vbus(self, taus, omegas) -> tuple:
        p = 0.0
        for t, w in zip(taus, omegas):
            i = abs(t) / self.kt
            p += t * w + 1.5 * i * i * self.r_phase + self.idle_w
        v = self.v_oc
        for _ in range(3):                                        # V = V_oc - R I, I = P / V
            v = self.v_oc - self.r_int * p / max(v, 1.0)
        return v, p / max(v, 1.0)


@dataclass
class Thermal:
    """A motor's winding temperature, first order: losses I^2 R in, through a thermal resistance to the air. The
    numbers are estimates (an RS-04 on a printed frame has no heat sink): the rig's long holds measure them."""
    t_amb: float = 25.0
    r_th: float = 1.2           # K/W winding to air
    c_th: float = 450.0         # J/K
    r_phase: float = 0.12
    kt: float = 2.1
    temp: float = 30.0

    def step(self, tau: float, dt: float) -> float:
        i = abs(tau) / self.kt
        p = 1.5 * i * i * self.r_phase
        self.temp += (p - (self.temp - self.t_amb) / self.r_th) / self.c_th * dt
        return self.temp


def wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
