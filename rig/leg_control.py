"""The leg's controller on the rig: sim/leg_rig.py's virtual-model controller and scenarios, ported to run from the
motors' feedback alone, with the rig's safety supervisor (docs/leg-prototype-plan.md sections 3.3, 4.1-4.5).

    ctl = LegController('squat', ff_n=..., limits=Limits())
    cmd = ctl.update(tick)                    # -> Command(tau_f, tau_r, kd, power_off, stop, phase, abort)

What is reused unchanged (plan 4.1): fivebar's fk / jacobian / stop_angles, and sim.leg_rig's vmc, Gains, clip_motor
and command(). Those three and the scenario table are copied here as a thin adapter so the laptop that drives the
motors never imports MuJoCo; rig/tests/test_control.py checks that they stay identical to sim/leg_rig.py's (until the
main session moves them into a MuJoCo-free module, plan F4).

What is not ported (plan 4.2): the TPU stops as springs, OFF_DAMPING, ARMATURE, TYRE_SOLREF are the plant's (they live
in rig/sim_bus.py); the motors run MIT with Kp = Kd = 0, so the torque is pure feed-forward and this is the only loop.

What is new: the jump has to know when the wheel leaves the ground and lands (the simulation reads the contact force;
the rig has no force sensor under the wheel in a jump), so `Flight` estimates it from the leg: the push ending starts
the flight, a landing shows as the leg being driven shorter than commanded at speed.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

R = Path(__file__).resolve().parents[1]
if str(R / 'cad') not in sys.path:
    sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402

G = 9.81
LEG_PEAK = 120.0                  # N m, RS-04 peak (catalog/leg_actuators.json)
LEG_CAP = 60.0                    # N m, the firmware cap (D38; limit_torque in the motors)
REF_DT = 0.0005                   # s: sim.leg_rig runs its controller every MuJoCo step


# ----------------------------------------------------------------------------------- sim.leg_rig's controller, MuJoCo-free

@dataclass
class Gains:
    kp_L: float = 3000.0          # N/m on the virtual leg's length
    kd_L: float = 250.0
    kp_th: float = 150.0          # N m/rad on its lean
    kd_th: float = 6.0


TUCK = Gains(kp_L=3000, kd_L=260)  # the jump's gains in the air (sim.leg_rig.run)


def clip_motor(tau, omega, peak, omega_max, cap=None):
    lim = peak if tau * omega <= 0 else peak * max(0.0, 1.0 - abs(omega) / omega_max)
    if cap:
        lim = min(lim, cap)
    return max(-lim, min(lim, tau))


def polar(phi1: float, phi2: float, w1: float, w2: float):
    """The virtual leg from the motor angles and speeds: length (m), lean (rad, + = wheel forward), their rates, the
    Jacobian d(x, z)/d(phi) (m/rad) and the axle (x, z) in m (sim.leg_rig.Leg.polar without MuJoCo)."""
    E = fb.fk(phi1, phi2)['E']
    J = np.array(fb.jacobian(phi1, phi2)) / 1000.0
    x, z = E[0] / 1000, E[1] / 1000
    dx, dz = J @ np.array([w1, w2])
    L = math.hypot(x, z)
    th = math.atan2(x, -z)
    return L, th, (x * dx + z * dz) / L, (-z * dx + x * dz) / (L * L), J, (x, z)


def vmc(pol, L_cmd, th_cmd=0.0, ff=0.0, g: Gains = Gains(), force=None):
    """Motor torques for a spring-damper virtual leg, or a straight push (force N along the leg)."""
    L, th, dL, dth, J, _ = pol
    F = force if force is not None else g.kp_L * (L_cmd - L) - g.kd_L * dL + ff
    T = g.kp_th * (th_cmd - th) - g.kd_th * dth
    uL = np.array([math.sin(th), -math.cos(th)])
    uth = np.array([math.cos(th), math.sin(th)])
    return J.T @ (F * uL + (T / L) * uth)


@dataclass
class Scenario:
    name: str
    title: str
    duration: float
    start_h: float = 300.0
    start_rail: Optional[float] = None
    cap: Optional[float] = LEG_CAP
    rail_low: float = 0.115


SCENARIOS = {
    'stand_up': Scenario('stand_up', 'Stand up from the deepest crouch in 1 s and hold', 3.0, start_h=140.0),
    'squat': Scenario('squat', 'Three squats, 300 to 150 mm at 0.5 Hz', 6.5),
    'jump': Scenario('jump', 'Crouch, push off at the 60 N m cap, tuck in the air, land', 3.0),
    'jump_peak': Scenario('jump_peak', 'The same jump at the motors\' full 120 N m (no cap)', 3.0, cap=None),
    'drop_150': Scenario('drop_150', 'Dropped with the wheel 150 mm off the floor, the leg holding 300 mm', 2.0, start_rail=None),
    'power_off': Scenario('power_off', 'Standing, then the motors lose power (no damping): the leg folds onto its own stops', 2.5, rail_low=0.06),
    'power_off_damped': Scenario('power_off_damped', "The same, with the RS-04's power-off anti-backdrive damping (assumed 20 % of shorted phases)",
                                 2.5, rail_low=0.06),
}


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def command(sc: Scenario, t: float, state: dict):
    """(L_cmd mm, mode) for a scenario at time t; mode 'pd', 'push', 'off' (sim.leg_rig.command)."""
    if sc.name == 'stand_up':
        return 140 + (300 - 140) * smooth((t - 0.3) / 1.0), 'pd'
    if sc.name == 'squat':
        return 225 + 75 * math.cos(2 * math.pi * 0.5 * max(0.0, t - 0.25)), 'pd'
    if sc.name in ('jump', 'jump_peak'):
        if t < 0.6:
            return 300 - 150 * smooth(t / 0.5), 'pd'
        if not state.get('pushed'):
            return None, 'push'
        return 250, 'pd'
    if sc.name == 'drop_150':
        return 300, 'pd'
    if sc.name.startswith('power_off'):
        return (300, 'pd') if t < 0.6 else (None, 'off')
    return 300, 'pd'


# ----------------------------------------------------------------------------------- the jump's flight, from the leg alone

@dataclass
class Flight:
    """Wheel on the ground or not, for the jump. The push ending starts the flight (the tuck pulls the wheel off at
    once: the carriage leaves at about 2.3 m/s); it lands when the leg is driven shorter than commanded (by `dz`)
    while shortening faster than `dL`, after at least `min_air` s in the air. In the air without the feed-forward the
    wheel hangs about 8 mm below the command, so a touchdown has to compress the leg past it first."""
    min_air: float = 0.12         # s: the tuck after the push is over by then (it never fired in the air: 8 jumps,
    dL: float = -0.60             # m/s   20-60 N m, 13.1 and 14.75 kg; it lagged the real touchdown 2-8 ms at 500 Hz)
    dz: float = 0.0               # m
    t_off: Optional[float] = None
    t_land: Optional[float] = None

    def contact(self, t: float, pushed: bool, L: float, dL: float, L_cmd: float) -> bool:
        if not pushed:
            return True
        if self.t_off is None:
            self.t_off = t
        if self.t_land is None and t - self.t_off >= self.min_air and dL < self.dL and L < L_cmd - self.dz:
            self.t_land = t
        return self.t_land is not None


# ----------------------------------------------------------------------------------- the safety supervisor

@dataclass
class Limits:
    vbus_max: float = 58.0        # V, instantaneous: regeneration pushes the pack up; the RS-04 trips at 60 (plan 3.2)
    vbus_min: float = 46.0        # V, averaged over vbus_tau: the pack has no cut-off of its own (15 x 3.07 V)
    vbus_floor: float = 36.0      # V, instantaneous: far below any sag a healthy pack shows (the RS-04 runs to 24 V)
    vbus_tau: float = 1.0         # s: a push sags the bus ~9 V for 0.1 s; that is not a flat pack
    temp_max: float = 80.0        # C winding: the motor warns at 135 and trips at 145; abort far below
    L_min: float = 0.095          # m: the leg-length window (plan 4.4), outside the leg's own 101.5-392.4 mm only by
    L_max: float = 0.395          # the stops' squeeze
    cap: float = LEG_CAP          # N m: the laptop clips too (the motors' limit_torque is the independent cap)
    rate: Optional[float] = None  # N m per tick, a limiter: off for the scenarios (the jump reverses 120 N m in one
                                  # tick at the push's end; 40 N m/tick moved its height 4 mm); 5 for the first hanging tests
    regen_w: Optional[float] = None   # W per motor: while braking (torque against speed) |t w| is held under this
    miss_max: int = 3             # ticks in a row without both motors' feedback -> limp
    sit_s: float = 0.3            # the sit-down's duration (plan 3.3)
    sit_to: float = 0.150         # m: the sit-down's end


@dataclass
class Command:
    tau_f: float = 0.0
    tau_r: float = 0.0
    kd: float = 0.0
    power_off: bool = False       # cut the motors' power (the power-off tests; on the rig, the contactor)
    stop: bool = False            # send the motors their stop frames: the run is over
    phase: str = ''
    L_cmd: Optional[float] = None
    contact: bool = True
    abort: Optional[str] = None   # why the supervisor took over


class LegController:
    """One scenario, tick by tick, under the supervisor. Abort actions: 'sitdown' (the pendant released, the RUN frames
    stale, VBUS low, a motor hot: the leg sits down to 150 mm in 0.3 s, then the motors stop) and 'limp' (VBUS high,
    feedback lost, a motor fault, the leg outside its window: zero torque at once, then stop; the bumpers catch the
    carriage). An abort is final for the run."""

    def __init__(self, scenario: str, ff_n: float, limits: Limits = Limits(), gains: Gains = Gains(),
                 flight: Optional[Flight] = None, contact_truth: bool = False, tick: Optional[float] = None,
                 external_cut: bool = False):
        self.sc = SCENARIOS[scenario]
        self.tick = tick                            # None: measured from the ticks themselves
        self._t_prev: Optional[float] = None
        self.ff = ff_n
        self.lim = limits
        self.g = gains
        self.flight = flight or Flight()
        self.contact_truth = contact_truth          # use the simulation's contact (to measure the estimate's effect)
        self.state: dict = {}
        self.abort: Optional[str] = None
        self.t_abort = 0.0
        self.L_abort = 0.3
        self.misses = 0
        self.prev = (0.0, 0.0)
        self.powered = True
        self.done = False
        self.vbus_avg: Optional[float] = None
        # the power-cut tests (S5, S6) cut the motors' power by the pendant: the contactor opens 1 s after it is
        # released, so the leg must keep standing through that second instead of sitting down
        self.hold_on_release = self.sc.name.startswith('power_off')
        # in the simulation the power goes at 0.6 s; on the rig (and its HIL stand-in) the contactor takes it whenever it
        # opens, and the controller keeps standing until the motors fall silent
        self.external_cut = external_cut

    def _limit(self, tau_f: float, tau_r: float, cap: Optional[float], w=(0.0, 0.0)):
        c = min(self.lim.cap, cap if cap else LEG_PEAK)
        out = []
        for t, p, om in zip((tau_f, tau_r), self.prev, w):
            t = max(-c, min(c, t))
            if self.lim.regen_w and t * om < 0 and abs(om) > 1e-3:
                b = self.lim.regen_w / abs(om)
                t = max(-b, min(b, t))
            if self.lim.rate:
                t = max(p - self.lim.rate, min(p + self.lim.rate, t))
            out.append(t)
        self.prev = tuple(out)
        return out

    def check(self, tk) -> Optional[str]:
        """The first reason to stop this tick, or None."""
        lim = self.lim
        if not self.powered:
            return None
        if not tk.ok:
            self.misses += 1
            if self.misses >= lim.miss_max:
                return 'limp: no feedback'
        else:
            self.misses = 0
        faults = tk.f.faults + tk.r.faults
        if faults:
            return 'limp: motor fault ' + ', '.join(faults)
        if tk.vbus is not None:
            a = min(1.0, (self.tick or 0.002) / lim.vbus_tau)
            self.vbus_avg = tk.vbus if self.vbus_avg is None else self.vbus_avg + a * (tk.vbus - self.vbus_avg)
            if tk.vbus > lim.vbus_max:
                return f'limp: VBUS {tk.vbus:.1f} V > {lim.vbus_max:.0f}'
            if tk.vbus < lim.vbus_floor:
                return f'limp: VBUS {tk.vbus:.1f} V < {lim.vbus_floor:.0f}'
        if not tk.run and not self.hold_on_release:
            return 'sitdown: safety line open'
        if self.vbus_avg is not None and self.vbus_avg < lim.vbus_min:
            return f'sitdown: VBUS {self.vbus_avg:.1f} V (mean) < {lim.vbus_min:.0f}'
        hot = max(tk.f.temp_c, tk.r.temp_c)
        if hot > lim.temp_max:
            return f'sitdown: motor {hot:.0f} C > {lim.temp_max:.0f}'
        L = polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w)[0]
        if not lim.L_min <= L <= lim.L_max:
            return f'limp: leg {L * 1000:.0f} mm outside {lim.L_min * 1000:.0f}-{lim.L_max * 1000:.0f}'
        return None

    def update(self, tk) -> Command:
        if self._t_prev is not None and tk.t > self._t_prev:
            dt = tk.t - self._t_prev
            self.tick = dt if self.tick is None else 0.9 * self.tick + 0.1 * dt
        self._t_prev = tk.t
        if self.done:
            return Command(stop=True, phase='stopped', abort=self.abort)
        if self.external_cut and self.hold_on_release and self.powered and not tk.ok and tk.t > 0.1:
            self.powered = False                                     # the contactor opened: the motors are silent
            self.prev = (0.0, 0.0)
        if not self.powered and self.abort is None:
            return Command(power_off=True, phase='off')
        if self.abort is None:
            why = self.check(tk)
            if why:
                self.abort, self.t_abort = why, tk.t
                self.L_abort = polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w)[0]
        if self.abort:
            return self._aborting(tk)
        return self._scenario(tk)

    def _aborting(self, tk) -> Command:
        dt = tk.t - self.t_abort
        if self.abort.startswith('limp') or not tk.ok:
            if dt > 0.05:
                self.done = True
            self.prev = (0.0, 0.0)
            return Command(stop=self.done, phase='limp', abort=self.abort)
        pol = polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w)
        L_cmd = self.L_abort + (self.lim.sit_to - self.L_abort) * smooth(dt / self.lim.sit_s)
        tau = vmc(pol, L_cmd, 0.0, ff=self.ff, g=self.g)
        f, r = self._limit(float(tau[0]), float(tau[1]), self.sc.cap, (tk.f.w, tk.r.w))
        if dt > self.lim.sit_s + 0.2:
            self.done = True
        return Command(f, r, stop=self.done, phase='sitdown', L_cmd=L_cmd, abort=self.abort)

    def _scenario(self, tk) -> Command:
        sc, state, t = self.sc, self.state, tk.t
        pol = polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w)
        L = pol[0]
        L_cmd, mode = command(sc, t, state)
        if mode == 'off' and self.external_cut:
            L_cmd, mode = 300, 'pd'                                   # hold until the contactor opens
        slow = (self.tick or REF_DT) > REF_DT * 1.01
        if mode == 'push' and slow:
            # sim.leg_rig ends the push one 0.5 ms step after the leg passes 310 mm (on average 0.75 ms after it);
            # a loop that holds each torque for a whole tick would push up to a tick too long (at 500 Hz +9 mm of
            # jump), so it decides before this tick's torque, looking ahead to stop at the same mean time
            state.setdefault('t_push', t)
            if L + pol[2] * (self.tick / 2 - 1.5 * REF_DT) > 0.31 or t - state['t_push'] > 0.35:
                state['pushed'] = True
                L_cmd, mode = command(sc, t, state)                           # the tuck starts this tick
        if mode == 'push':
            tau = vmc(pol, None, 0.0, force=5000.0, g=self.g)              # as hard as the motors allow
            if not slow and (L > 0.31 or (state.get('t_push') and t - state['t_push'] > 0.35)):
                state['pushed'] = True
            state.setdefault('t_push', t)
            f, r = self._limit(float(tau[0]), float(tau[1]), sc.cap, (tk.f.w, tk.r.w))
            return Command(f, r, phase='push', contact=True)
        if mode == 'off':
            self.powered = False
            self.prev = (0.0, 0.0)
            return Command(power_off=True, phase='off')
        jump = sc.name in ('jump', 'jump_peak')
        if self.contact_truth and 'contact' in tk.extra:
            contact = tk.extra['contact'] or not state.get('pushed')
        else:
            contact = self.flight.contact(t, bool(state.get('pushed')), L, pol[2], L_cmd / 1000) if jump else True
        g = self.g if (contact or not jump or not state.get('pushed')) else TUCK
        tau = vmc(pol, L_cmd / 1000, 0.0, ff=self.ff if contact or not state.get('pushed') else 0.0, g=g)
        f, r = self._limit(float(tau[0]), float(tau[1]), sc.cap, (tk.f.w, tk.r.w))
        phase = 'air' if not contact else ('land' if state.get('pushed') else 'track')
        return Command(f, r, phase=phase, L_cmd=L_cmd / 1000, contact=contact)


def ff_for(half_mass: float, rotor_kg: float, wheel_link_kg: float) -> float:
    """What the leg holds up, as sim.leg_rig.run() feeds it forward: the carried mass less the wheel's rotor and half
    the wheel link (those hang below the leg's force)."""
    return half_mass * G - (rotor_kg + wheel_link_kg * 0.5) * G
