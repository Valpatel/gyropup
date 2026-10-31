"""The simulated motor bus: sim/leg_rig.py's MuJoCo rig behind the same interface as the motors.

    bus = SimBus('jump', half_mass=13.1)     # a scenario of sim.leg_rig.SCENARIOS sets the start pose and the rail stop
    tk = bus.start()
    tk = bus.step(tau_f, tau_r)              # 4 MuJoCo steps of 0.5 ms with the torques held (a 2 ms tick)
                                             # latency_ticks=1: the state returned is the one the command arrived at
                                             # (the CAN bus's request/reply), so a command acts a tick after its data
    res = bus.results()                      # the same keys as exports/leg/rig-results.json

What belongs to the plant here and not to the controller (plan section 4.2, the 'firmware cancel' list):
  - the RS-04's torque-speed line (sim.leg_rig.clip_motor at 120 N m peak) and its firmware torque cap (limit_torque,
    60 N m by default): the controller asks, the motor delivers what it can;
  - the TPU stop sleeves as springs (sim.leg_rig.stop_torque), applied every step: on the rig they are real parts;
  - the power-off behaviour: torque -b w with b = sim.leg_rig.OFF_DAMPING (the 'damped' case) or 0;
  - the motor's own Kd term when the controller asks for one (aborts, the safety damper).
The bookkeeping (the gearbox torque and the joints' forces every step, a sample every 2 ms, the summary) is
sim.leg_rig.run()'s, so a run through this bus can be compared key for key with rig-results.json.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

R = Path(__file__).resolve().parents[1]
for p in (str(R), str(R / 'cad')):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault('MUJOCO_GL', 'egl')

import mujoco  # noqa: E402

from sim import leg_rig as lr  # noqa: E402
from rig.bus import MotorBus, MotorState, Pack, Thermal, Tick  # noqa: E402


class SimBus(MotorBus):
    def __init__(self, scenario: str = 'stand_up', half_mass: float = lr.HALF_MASS, tick: float = 0.002,
                 cap: Optional[float] = lr.LEG_CAP, rail_low: Optional[float] = None, damped_off: Optional[bool] = None,
                 pack: Optional[Pack] = None, temp0: float = 30.0, video: Optional[Path] = None, meshes: Optional[dict] = None,
                 record: bool = True, latency_ticks: int = 0):
        # a name is sim/leg_rig.py's scenario; a Scenario object (the rig's, rig/leg_control.py) is taken as given
        self.sc = lr.SCENARIOS[scenario] if isinstance(scenario, str) else scenario
        self.half_mass = half_mass
        self.cap = cap
        self.xml, self.info = lr.mjcf(half_mass, meshes, self.sc.rail_low if rail_low is None else rail_low)
        self.m = mujoco.MjModel.from_xml_string(self.xml)
        self.d = mujoco.MjData(self.m)
        self.leg = lr.Leg(self.m)
        self.dt = self.m.opt.timestep
        self.n_sub = max(1, int(round(tick / self.dt)))
        self.tick = self.n_sub * self.dt
        self.off_b = lr.OFF_DAMPING if (damped_off if damped_off is not None else self.sc.name == 'power_off_damped') else 0.0
        self.pack = pack or Pack(v_oc=lr.BUS_V, r_int=0.0)      # default: sim.leg_rig's ideal 54 V bus
        self.therm = (Thermal(temp=temp0), Thermal(temp=temp0))
        self.record = record
        self.latency_ticks = latency_ticks             # 1: return the state the command arrived at, like the CAN bus
        self.powered = True
        self.vw = lr.VideoWriter(self.m, video) if video else None
        self.every = max(1, int(round(1 / (lr.FPS * self.dt))))
        mp = lr.mass_props()
        self.ff_n = half_mass * lr.G - (mp['rotor'].mass + mp['wheel_link'].mass * 0.5) * lr.G   # what run() feeds forward
        self.k = 0
        self.rec, self.state = [], {}
        self.gear = {'motor_f': 0.0, 'motor_r': 0.0}
        self.over = {'motor_f': 0.0, 'motor_r': 0.0}
        self.joint = {'knee_f': 0.0, 'knee_r': 0.0, 'hip_f': 0.0, 'hip_r': 0.0, 'apex': 0.0}
        self.jb = {'knee_f': self.m.body('lower_f').id, 'knee_r': self.m.body('lower_r').id,
                   'hip_f': self.m.body('upper_f').id, 'hip_r': self.m.body('upper_r').id}
        self.v_now = lr.BUS_V if pack is None else self.pack.v_oc

    # ------------------------------------------------------------- the bus
    def start(self) -> Tick:
        if self.sc.name == 'drop_150':
            self.leg.set_height(self.d, 300.0, rail_z=(300 + 150) / 1000 + lr.WHEEL_R)
        else:
            self.leg.set_height(self.d, self.sc.start_h)
        self.rail0 = self.top = float(self.d.qpos[self.leg.q['rail']])
        return self._tick()

    def power_off(self) -> None:
        self.powered = False

    def stop(self) -> None:
        self.powered = False
        self.off_b = 0.0

    def close(self) -> None:
        if self.vw:
            self.vw.close()
            self.vw = None

    def step(self, tau_f: float, tau_r: float, kd: float = 0.0) -> Tick:
        m, d, leg = self.m, self.d, self.leg
        pre = self._tick() if self.latency_ticks else None
        fo, fi, ro, ri = lr.fb.stop_angles()
        for _ in range(self.n_sub):
            t = self.k * self.dt
            w_max = lr.LEG_OMEGA * self.v_now / lr.BUS_V          # the no-load speed goes with the bus voltage
            for n, tau in (('motor_f', tau_f), ('motor_r', tau_r)):
                om = float(d.qvel[leg.v[n]])
                if self.powered:
                    d.ctrl[leg.a[n]] = lr.clip_motor(float(tau) - kd * om, om, lr.LEG_PEAK, w_max, self.cap)
                else:
                    d.ctrl[leg.a[n]] = -self.off_b * om
            d.ctrl[leg.a['wheel']] = 0.0
            p1, p2 = leg.phi(d)
            for n, ph, lo, hi in (('motor_f', p1, fi, fo), ('motor_r', p2, ro, ri)):
                ts = lr.stop_torque(ph, d.qvel[leg.v[n]], lo, hi)
                d.qfrc_applied[leg.v[n]] = ts
                self.state['stop_' + n] = ts
            mujoco.mj_step(m, d)
            self.top = max(self.top, float(d.qpos[leg.q['rail']]))
            if self.record:
                self._bookkeep(t)
            if self.vw and self.k % self.every == 0:
                self.vw.frame(d)
            self.k += 1
        for th, n in zip(self.therm, ('motor_f', 'motor_r')):
            th.step(float(d.actuator_force[leg.a[n]]), self.tick)
        post = self._tick()
        return pre if pre is not None else post

    # ------------------------------------------------------------- state and records
    def _bookkeep(self, t: float) -> None:
        m, d, leg = self.m, self.d, self.leg
        for n in self.gear:
            v = leg.v[n]
            tg = abs(float(d.actuator_force[leg.a[n]] - m.dof_armature[v] * d.qacc[v] - m.dof_damping[v] * d.qvel[v]))
            self.gear[n] = max(self.gear[n], tg)
            self.over[n] += self.dt if tg > lr.LEG_PEAK else 0.0
        mujoco.mj_rnePostConstraint(m, d)
        for n, b in self.jb.items():
            self.joint[n] = max(self.joint[n], float(np.linalg.norm(d.cfrc_int[b][3:6])))
        fa = [d.efc_force[i] for i in range(d.nefc) if d.efc_type[i] == mujoco.mjtConstraint.mjCNSTR_EQUALITY]
        self.joint['apex'] = max(self.joint['apex'], float(np.linalg.norm(fa)) if fa else 0.0)
        if self.k % 4 == 0:
            self.rec.append(lr.sample(m, d, leg, t, self.state))

    def _tick(self) -> Tick:
        d, leg = self.d, self.leg
        p1, p2 = leg.phi(d)
        w1, w2 = float(d.qvel[leg.v['motor_f']]), float(d.qvel[leg.v['motor_r']])
        t1, t2 = float(d.actuator_force[leg.a['motor_f']]), float(d.actuator_force[leg.a['motor_r']])
        if self.powered:
            vbus, ibus = self.pack.vbus((t1, t2), (w1, w2))
            self.v_now = vbus
        else:
            vbus, ibus = None, 0.0
        mode = 'run' if self.powered else 'off'
        fx, fz = lr.wheel_force(self.m, d, leg)
        L, th, dL, dth, J, (x, z) = leg.polar(d)
        extra = {'rail_mm': float(d.qpos[leg.q['rail']]) * 1000, 'wheel_fz_n': float(fz), 'contact': bool(fz > 1.0),
                 'L_mm_true': L * 1000, 'ibus_a': ibus, 'jump_mm': (self.top - self.rail0) * 1000}
        return Tick(t=self.k * self.dt,
                    f=MotorState(float(p1), w1, t1, self.therm[0].temp, mode),
                    r=MotorState(float(p2), w2, t2, self.therm[1].temp, mode),
                    vbus=vbus, run=True, extra=extra)

    def results(self) -> dict:
        """sim.leg_rig.run()'s summary of this run (rig-results.json's keys)."""
        res = lr.summarise(self.sc, self.rec, self.info)
        res['jump_height_mm'] = round((self.top - self.rail0) * 1000, 1) if self.sc.name.startswith('jump') else None
        res['peak_gearbox_nm'] = round(max(self.gear.values()), 1)
        res['gearbox_over_peak_ms'] = round(max(self.over.values()) * 1000, 1)
        res['peak_joint_force_n'] = {k: round(v, 1) for k, v in self.joint.items()}
        return res
