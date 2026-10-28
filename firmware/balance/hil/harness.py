"""The balance firmware's HIL harness: the firmware (its host build, hil/fwlib.py) drives the leg rig workstream's emulated
RS-04s (rig/rs04_emu.py) on its CAN buses, each leg's two motors on the MuJoCo rig (rig/sim_bus.py through
rig/hil.py HilLink: the plant is stepped with what the motors were told), with an emulated VN-100, INA228, Jetson and
VESCs. The firmware cannot tell: it boots the motors (configure, read back, enable), runs its 1 kHz loop, and
every byte it sends or reads is a CAN frame or a sensor register.

    h = Hil(scenario='stand_up', half_mass=16.25, bus_v=36.0)
    log = h.run(3.0)                       # plant seconds after the firmware reaches RUN

Bus A carries the left leg (motors 1, 2) on one rig, bus B the right (3, 4) on a second rig running the same scenario;
bus C the VESCs (ids 10, 11) and the Jetson. Both rigs draw from one pack (open-circuit V_oc behind r_int): the INA228
reads that bus.

Transports: every bus is the rig's in-memory VirtualBus (rig/canio.py). `Bridge` joins one to a real interface (a
gs_usb/candleLight USB-CAN adapter is a SocketCAN interface: rig.canio.SocketCan; python-can for slcan) so the same
emulated devices can face the firmware on the Nucleo (B13), with the plant stepped in real time.

The `rig` package comes from this repository when it is importable, else from GYROPUP_RIG_DIR (default
~/Code/gyropup-legrig, the legrig/program worktree). sim.leg_rig is this repository's, set to the design's bus
(BUS_V, LEG_OMEGA on the imported module; the file is not edited).
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in (str(REPO), str(REPO / 'cad'), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault('MUJOCO_GL', 'egl')

import fwlib  # noqa: E402

RIG_DIR = Path(os.environ.get('GYROPUP_RIG_DIR', str(Path.home() / 'Code' / 'gyropup-legrig')))
DESIGN_HALF_MASS = 18.75      # kg a leg (D71; cad/test_body.py checks it against cad/body_layout.py BUDGET)
DESIGN_BUS_V = 36.0           # V, the 10S pack's nominal (D65: two DCB609s in 20 V mode in series; gp_config.h GP_PACK_NOMINAL_V)
PACK_FULL_V = 41.0            # V, 4.1 V a cell (GP_PACK_FULL_V)
R_PACK = 0.100                # ohm, as the firmware's resting-voltage estimate (gp_config.h GP_R_PACK_OHM)


def import_rig():
    """(sim.leg_rig, rig.hil, rig.sim_bus, rig.can_bus, rig.canio, rig.bus, rig.leg_control): this repository's
    sim.leg_rig first, so the rig's modules bind to it."""
    from sim import leg_rig as lr                       # noqa: F401  (imported before rig.sim_bus binds `sim`)
    from sim import robot_v2
    robot_v2.use_d69_wheel()                            # D69's 10 in hub wheel, as the firmware header was generated
    from sim import leg_control  # noqa: F401
    try:
        import rig.hil  # noqa: F401
    except ImportError:
        if not (RIG_DIR / 'rig' / 'hil.py').exists():
            raise
        sys.path.append(str(RIG_DIR))
        import rig.hil  # noqa: F401
    import rig.bus
    import rig.can_bus
    import rig.canio
    import rig.leg_control
    import rig.sim_bus
    return lr, rig.hil, rig.sim_bus, rig.can_bus, rig.canio, rig.bus, rig.leg_control


def set_bus_voltage(lr, bus_v: float) -> None:
    """sim.leg_rig at a pack voltage: its BUS_V and the RS-04's no-load speed with it."""
    lr.BUS_V = bus_v
    lr.LEG_OMEGA = lr.MOTOR['no_load_speed_rpm'] * bus_v / lr.MOTOR['voltage_nominal_v'] * 2 * math.pi / 60


class Bridge:
    """Forward frames both ways between a VirtualBus port and another transport (SocketCan, a python-can wrapper, or
    another VirtualBus port): call pump() as often as the loop runs."""

    def __init__(self, a, b):
        self.a, self.b = a, b
        self.count = [0, 0]

    def pump(self) -> None:
        for src, dst, k in ((self.a, self.b, 0), (self.b, self.a, 1)):
            while True:
                f = src.recv(0)
                if f is None:
                    break
                dst.send(*f)
                self.count[k] += 1


class PythonCan:
    """python-can as a rig.canio-style transport (slcan, gs_usb through libusb, ...): send(cid, data, ext), recv(timeout)."""

    def __init__(self, interface: str, channel: str, bitrate: int = 1_000_000):
        import can                                       # optional: only for adapters SocketCAN does not cover
        self.can = can
        self.bus = can.Bus(interface=interface, channel=channel, bitrate=bitrate)

    def send(self, cid, data, extended=True):
        self.bus.send(self.can.Message(arbitration_id=cid, data=bytes(data), is_extended_id=extended))

    def recv(self, timeout):
        m = self.bus.recv(timeout)
        return None if m is None else (m.arbitration_id, bytes(m.data), m.is_extended_id)

    def close(self):
        self.bus.shutdown()


def transport(spec: str):
    """'socketcan:can0' (rig.canio.SocketCan; a candleLight adapter is gs_usb, i.e. SocketCAN) or
    'python-can:<interface>:<channel>'."""
    kind, _, rest = spec.partition(':')
    if kind == 'socketcan':
        from rig.canio import SocketCan
        return SocketCan(rest or 'can0')
    if kind == 'python-can':
        iface, _, chan = rest.partition(':')
        return PythonCan(iface, chan)
    raise ValueError(f'transport {spec!r}: socketcan:<iface> or python-can:<interface>:<channel>')


@dataclass
class Jetson:
    """The J501's side of the protocol: setpoints at 100 Hz (each a heartbeat), the state frames read back."""
    run: bool = True
    people: bool = False
    height: float = 0.6
    link: bool = True
    jump_seq: int = 0
    jump_height: int = 15
    seq: int = 0
    status: dict = field(default_factory=dict)

    def setpoint(self) -> bytes:
        self.seq = (self.seq + 1) & 0xFF
        flags = (1 if self.run else 0) | (2 if self.people else 0) | ((self.jump_seq & 3) << 2) | ((self.jump_height & 15) << 4)
        return bytes((0, 0, 0, 0, int(round(self.height * 200)), 0, flags, self.seq))

    def jump(self, height: int = 15) -> None:
        self.jump_height = height
        self.jump_seq = (self.jump_seq + 1) & 3

    def take(self, cid: int, data: bytes) -> None:
        if cid == 0x122 and len(data) == 8:
            self.status = {'mode': data[0], 'flags': data[1], 'vbus': (data[2] | data[3] << 8) / 100.0,
                           'ibus': int.from_bytes(data[4:6], 'little', signed=True) / 100.0, 'reason': data[6]}


class Hil:
    def __init__(self, scenario: str = 'stand_up', half_mass: float = DESIGN_HALF_MASS, bus_v: float = DESIGN_BUS_V,
                 r_int: float = R_PACK, bench: int = 0, fw: Optional[fwlib.Firmware] = None, **fw_numbers):
        self.lr, hil, sim_bus, can_bus, canio, rbus, _ = import_rig()
        set_bus_voltage(self.lr, DESIGN_BUS_V)
        self.fw = fw or fwlib.Firmware.load()
        fo, _, ro, _ = self.lr.fb.stop_angles()
        MotorCal, Calibration = can_bus.MotorCal, can_bus.Calibration
        # the two legs calibrated differently, so the firmware's mapping is exercised both ways
        self.cal = (Calibration(MotorCal(1, -1, fo + 0.05), MotorCal(2, -1, ro - 0.05), 'HIL left'),
                    Calibration(MotorCal(3, 1, fo - 0.03), MotorCal(4, 1, ro + 0.02), 'HIL right'))
        self.v_oc, self.r_int = bus_v, r_int
        self.sims = [sim_bus.SimBus(scenario, half_mass=half_mass, tick=0.001, cap=self.lr.LEG_CAP,
                                    pack=rbus.Pack(v_oc=bus_v, r_int=0.0), record=False) for _ in range(2)]
        self.links = [hil.HilLink(s, c) for s, c in zip(self.sims, self.cal)]
        for link in self.links:
            link.begin()
        self.dev_c = canio.VirtualBus()
        self.ports = [self.links[0].port, self.links[1].port, self.dev_c.port()]   # the firmware's side of A, B, C
        self.devices = self.dev_c.port()                                            # the Jetson and the VESCs
        self.jetson = Jetson()
        self.vesc_current: Dict[int, float] = {}
        motors = [(c.id, b, c.dir, c.phi_zero) for b, cal in ((fwlib.BUS_A, self.cal[0]), (fwlib.BUS_B, self.cal[1]))
                  for c in (cal.front, cal.rear)]
        self.fw.configure(fwlib.RIG, motors, bench_scenario=bench, **fw_numbers)
        self.fw.init(0)
        self.now = 0
        self.vbus, self.ibus = bus_v, 0.0
        self.running = False                       # the plant runs once the firmware first reaches RUN
        self.stop_run = True

    # ------------------------------------------------------------- one millisecond
    def tick(self) -> fwlib.Snapshot:
        fw, now = self.fw, self.now
        if now % 10000 == 0 and self.jetson.link:
            self.devices.send(0x110, self.jetson.setpoint(), False)
        if now % 2000 == 0:
            for vid in (10, 11):                    # STATUS_1 at 500 Hz: the rig's wheels are not driven (ERPM 0)
                cur = int(round(self.vesc_current.get(vid, 0.0) * 10))
                self.devices.send((9 << 8) | vid, bytes(4) + cur.to_bytes(2, 'big', signed=True) + bytes(2), True)
            fw.ina228(self.vbus, -self.ibus, now)    # the low-side shunt reads discharge as negative (W30/W31)
        self._deliver()
        fw.tick(now, self.stop_run)
        for bus, cid, data, ext in fw.tx():
            self.ports[bus].send(cid, data, ext)
        self._deliver()
        while True:                                 # the VESCs and the Jetson read their frames
            f = self.devices.recv(0)
            if f is None:
                break
            cid, data, ext = f
            if ext and (cid >> 8) == 1:
                self.vesc_current[cid & 0xFF] = int.from_bytes(data[:4], 'big', signed=True) / 1000.0
            elif not ext:
                self.jetson.take(cid, data)
        s = fw.snapshot()
        if not self.running and s.mode == 3:
            self.running = True
        if self.running:
            for link in self.links:
                link.advance()
            self._pack()
        self.now += 1000
        return s

    def _deliver(self) -> None:
        for bus, port in enumerate(self.ports):
            while True:
                f = port.recv(0)
                if f is None:
                    break
                self.fw.can_rx(bus, f[0], f[1], f[2], self.now)

    def _pack(self) -> None:
        """One pack behind both legs: V = V_oc - r_int P / V; each rig's motors then see that bus."""
        p = sum(link.tk.extra['ibus_a'] * sim.pack.v_oc for link, sim in zip(self.links, self.sims))
        v = self.v_oc
        for _ in range(4):
            v = self.v_oc - self.r_int * p / max(v, 1.0)
        self.vbus, self.ibus = v, p / max(v, 1.0)
        for sim in self.sims:
            sim.pack.v_oc = v

    # ------------------------------------------------------------- a run
    def run(self, seconds: float, until_running: float = 2.0, each: Optional[Callable[['Hil', float, fwlib.Snapshot], None]] = None
            ) -> dict:
        """Tick until the firmware runs (at most `until_running` s of firmware time), then `seconds` of plant time.
        Returns per-tick arrays (plant time, both legs' true length and lean, the rail, the firmware's state)."""
        from sim.leg_control import polar
        log: Dict[str, List[float]] = {k: [] for k in ('t', 'L', 'lean', 'L_r', 'lean_r', 'rail_mm', 'mode', 'flags', 'reason',
                                                       'vrest', 'vbus', 'v_oc', 'jump_phase', 'tau_f', 'tau_r', 'mcu_run',
                                                       'vload', 'cutoff', 'bus_scale', 'ibus', 'vhigh', 'overcharge',
                                                       'regen_scale')}
        boot_ticks = 0
        while not self.running:
            s = self.tick()
            boot_ticks += 1
            if boot_ticks > until_running * 1000:
                raise RuntimeError(f'the firmware did not reach RUN: mode {fwlib.MODES[s.mode]}, boot mask {s.boot_mask:#x}, '
                                   f'reason {fwlib.REASONS.get(s.reason)}')
        self.boot_ticks = boot_ticks
        t0 = self.links[0].t
        while self.links[0].t - t0 < seconds - 1e-9:
            t = self.links[0].t - t0
            if each:
                each(self, t, None)
            s = self.tick()
            tk = [link.tk for link in self.links]
            pl = [polar(k.f.phi, k.r.phi, 0.0, 0.0) for k in tk]
            log['t'].append(self.links[0].t - t0)
            log['L'].append(pl[0][0])
            log['lean'].append(pl[0][1])
            log['L_r'].append(pl[1][0])
            log['lean_r'].append(pl[1][1])
            log['rail_mm'].append(tk[0].extra['rail_mm'])
            for k in ('mode', 'flags', 'reason', 'vrest', 'vbus', 'jump_phase', 'mcu_run', 'vload', 'cutoff', 'bus_scale', 'ibus',
                      'vhigh', 'overcharge', 'regen_scale'):
                log[k].append(getattr(s, k))
            log['v_oc'].append(self.v_oc)
            log['tau_f'].append(s.tau[0])
            log['tau_r'].append(s.tau[1])
        return log


def reference_stand_up(half_mass: float = DESIGN_HALF_MASS, bus_v: float = DESIGN_BUS_V) -> dict:
    """sim/leg_rig.py run() of 'stand_up' (the controller at 2 kHz on MuJoCo's own state): t, L, lean every 2 ms."""
    lr = import_rig()[0]
    set_bus_voltage(lr, bus_v)
    captured = {}
    orig = lr.summarise

    def grab(sc, rec, info):
        captured['rec'] = rec
        return orig(sc, rec, info)

    lr.summarise = grab
    try:
        lr.run(lr.SCENARIOS['stand_up'], half_mass)
    finally:
        lr.summarise = orig
    rec = captured['rec']
    return {'t': [r['t'] for r in rec], 'L': [r['L_mm'] / 1000 for r in rec], 'lean': [math.radians(r['lean_deg']) for r in rec]}


def rig_controller_stand_up(half_mass: float = DESIGN_HALF_MASS, bus_v: float = DESIGN_BUS_V) -> dict:
    """The leg rig's own controller (rig/leg_control.py) through the same HilLink and CanBus at 1 kHz."""
    lr, hil, sim_bus, can_bus, canio, rbus, lc = import_rig()
    set_bus_voltage(lr, bus_v)
    fo, _, ro, _ = lr.fb.stop_angles()
    cal = can_bus.Calibration(can_bus.MotorCal(1, -1, fo + 0.05), can_bus.MotorCal(2, -1, ro - 0.05), 'HIL')
    sim = sim_bus.SimBus('stand_up', half_mass=half_mass, tick=0.001, cap=lr.LEG_CAP, pack=rbus.Pack(bus_v, 0.0), record=False)
    link = hil.HilLink(sim, cal)
    bus = can_bus.CanBus(link.port, cal, tick=0.001, realtime=False, clock=link.clock, after_exchange=link.advance)
    link.begin()
    # the rig's own Limits carry its pack's bus window (vbus_min 46 V); here the 10S robot's: the 30 V cut-off, the
    # RS-04's 24 V floor (rig/leg_control.py is the leg rig's: it moves to 36 V with sim/leg_rig.py's BUS_V)
    limits = lc.Limits(cap=lr.LEG_CAP, vbus_min=min(lc.Limits().vbus_min, 30.0), vbus_floor=min(lc.Limits().vbus_floor, 24.0))
    ctl = lc.LegController('stand_up', sim.ff_n, limits, tick=0.001, external_cut=True)
    out = {'t': [], 'L': [], 'lean': []}
    tk = bus.start()
    while tk.t < 3.0 - 1e-9:
        cmd = ctl.update(tk)
        tk = bus.step(cmd.tau_f, cmd.tau_r, cmd.kd)
        L, th = lc.polar(link.tk.f.phi, link.tk.r.phi, 0.0, 0.0)[:2]
        out['t'].append(link.t)
        out['L'].append(L)
        out['lean'].append(th)
    return out


def compare(run: dict, ref: dict, t_max: float = 3.0) -> dict:
    """The worst and RMS differences in leg length (absolute and relative to the reference) and lean over 0..t_max."""
    import numpy as np
    t = np.asarray(ref['t'])
    keep = t <= t_max
    t = t[keep]
    L_ref, th_ref = np.asarray(ref['L'])[keep], np.asarray(ref['lean'])[keep]
    L = np.interp(t, run['t'], run['L'])
    th = np.interp(t, run['t'], run['lean'])
    dL, dth = L - L_ref, th - th_ref
    i = int(np.argmax(np.abs(dL) / L_ref))
    return {'samples': int(len(t)), 'worst_L_mm': float(np.max(np.abs(dL)) * 1000), 'worst_L_rel': float(np.max(np.abs(dL) / L_ref)),
            'worst_L_at_s': float(t[i]), 'rms_L_mm': float(np.sqrt(np.mean(dL ** 2)) * 1000),
            'worst_lean_deg': float(np.degrees(np.max(np.abs(dth)))), 'worst_lean_rad': float(np.max(np.abs(dth))),
            'worst_lean_axle_rel': float(np.max(np.abs(dth))),       # the axle's sideways error over the leg length
            'end_L_mm': [float(L[-1] * 1000), float(L_ref[-1] * 1000)]}
