"""The balance law on the whole robot: the firmware (robot profile, its host build) balancing sim/robot_v2.py's MuJoCo
model through the same emulated devices as the HIL (four rig/rs04_emu.py RS-04s on buses A and B, the VESCs' status
and current frames, VN-100 packets, INA228 registers, the Jetson's setpoints), against sim/controller_v2.py
ControllerV2 driving the same model directly. The leg rig cannot pitch, so this is where the LQR, the yaw loop, the
pendulum-angle estimate and every sign between the sensors and the wheels are checked.

    python firmware/balance/hil/sil_robot.py            # needs build/sim/v2 (python -m sim.robot_v2)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness  # noqa: E402
import fwlib  # noqa: E402

BUILD = harness.REPO / 'build' / 'sim' / 'v2'
SIDES = ('l', 'r')


def command(t: float):
    """(height, speed): stand, drive 0.5 m/s, stop, crouch."""
    speed = 0.5 if 1.5 <= t < 4.0 else 0.0
    height = 0.3 if t >= 6.0 else 0.6
    return height, speed


class Plant:
    def __init__(self):
        import mujoco
        from sim.controller_v2 import RobotV2, place_standing
        self.mj = mujoco
        self.info = json.loads((BUILD / 'model.json').read_text())
        # the INA228 reads robot_v2's BUS_V (the 10S nominal, D65), the bus the simulation's speed lines are at
        self.bus_v = float(self.info['bus_v'])
        self.m = mujoco.MjModel.from_xml_path(str(BUILD / 'robot.xml'))
        self.d = mujoco.MjData(self.m)
        self.rb = RobotV2(self.m, self.info)
        place_standing(self.rb, self.d, 0.6)
        self.lr = harness.import_rig()[0]

    def stops(self):
        fo, fi, ro, ri = self.rb.stops
        for s in SIDES:
            p1, p2 = self.rb.phi(self.d, s)
            for jn, ph, lo, hi in ((f'motor_f_{s}', p1, fi, fo), (f'motor_r_{s}', p2, ro, ri)):
                self.d.qfrc_applied[self.rb.vadr[jn]] = self.lr.stop_torque(ph, self.d.qvel[self.rb.vadr[jn]], lo, hi)

    def truth(self) -> dict:
        """theta, the axle's x and speed, the legs' length, as sim/controller_v2.py measures them."""
        rb, m, d = self.rb, self.m, self.d
        com, M = np.zeros(3), 0.0
        for i in rb.bodies:
            if i not in rb.wheels:
                com += m.body_mass[i] * d.xipos[i]
                M += m.body_mass[i]
        axle = (d.xpos[rb.wheels[0]] + d.xpos[rb.wheels[1]]) / 2
        dd = com / M - axle
        L = [rb.leg_state(d, s)[0] for s in SIDES]
        return {'theta': math.atan2(dd[0], dd[2]), 'x': float(axle[0]), 'v': float(d.qvel[0]), 'L': L,
                'yaw': math.atan2(d.xmat[rb.base][3], d.xmat[rb.base][0])}


def run_python(seconds: float = 8.0) -> dict:
    from sim.controller import Command
    from sim.controller_v2 import ControllerV2
    p = Plant()
    ctl = ControllerV2(p.rb)
    ctl.height = 0.6
    log = {k: [] for k in ('t', 'theta', 'x', 'v', 'L')}
    for k in range(int(seconds / p.m.opt.timestep)):
        t = k * p.m.opt.timestep
        h, v = command(t)
        ctl.control(p.d, Command(height=h, speed=v), p.m.opt.timestep)
        p.mj.mj_step(p.m, p.d)
        tr = p.truth()
        for key in ('theta', 'x', 'v'):
            log[key].append(tr[key])
        log['L'].append(sum(tr['L']) / 2)
        log['t'].append(t + p.m.opt.timestep)
    return log


def run_firmware(seconds: float = 8.0) -> dict:
    lr, hil, sim_bus, can_bus, canio, rbus, _ = harness.import_rig()
    from rig.rs04_emu import EmulatedRS04
    p = Plant()
    rb, m, d, mj = p.rb, p.m, p.d, p.mj
    imu = m.site('imu').id
    fw = fwlib.Firmware.load()
    fo, _, ro, _ = lr.fb.stop_angles()
    cal = [(1, fwlib.BUS_A, -1, fo + 0.05), (2, fwlib.BUS_A, -1, ro - 0.05), (3, fwlib.BUS_B, 1, fo - 0.03), (4, fwlib.BUS_B, 1, ro + 0.02)]
    joints = ['motor_f_l', 'motor_r_l', 'motor_f_r', 'motor_r_r']
    fw.configure(fwlib.ROBOT, cal)
    fw.init(0)
    clock = {'t': 0.0}
    buses = [canio.VirtualBus(), canio.VirtualBus(), canio.VirtualBus()]
    emu = []
    for mid, bus, _, _ in cal:
        e = EmulatedRS04(mid, clock=lambda: clock['t'], plant=None)
        buses[bus].attach(e.handle)
        emu.append(e)
    ports = [b.port() for b in buses]
    devices = buses[2].port()
    vesc = {10: 0.0, 11: 0.0}
    wheel_dir = {10: 1, 11: -1}
    kt, pp = 0.951, 15
    seq = 0
    now = 0
    running = False
    log = {k: [] for k in ('t', 'theta', 'x', 'v', 'L', 'fw_theta', 'mode', 'imu_pitch', 'imu_q')}
    t0 = None
    while True:
        t = (now / 1e6 - t0) if running else 0.0
        if running and t >= seconds:
            break
        h, v = command(t)
        # the motors report the plant's angles (motor sense), the VESCs the wheels' speeds, the IMU the body
        for (mid, bus, dr, phi0), e, jn in zip(cal, emu, joints):
            side = jn[-1]
            ph = rb.phi(d, side)[0 if '_f_' in jn else 1]
            e.angle = (ph - phi0) / dr
            e.speed = float(d.qvel[rb.vadr[jn]]) / dr
        if now % 2000 == 0:
            for vid, side in ((10, 'l'), (11, 'r')):
                w = float(d.qvel[rb.vadr[f'wheel_{side}']])
                erpm = int(round(wheel_dir[vid] * w * pp * 60 / (2 * math.pi)))
                devices.send((9 << 8) | vid, erpm.to_bytes(4, 'big', signed=True) + bytes(4), True)
            fw.ina228(p.bus_v, 0.0, now)
        if now % 10000 == 0:
            seq = (seq + 1) & 0xFF
            sp = int(round(v * 1000)).to_bytes(2, 'little', signed=True) + bytes(2) + bytes((int(round(h * 200)), 0, 1, seq))
            devices.send(0x110, sp, False)
        # the VN-100 at the model's 'imu' site (the base's frame: x fwd, y left, z up). Not mjOBJ_BODY: a body's
        # 'local' velocity is in its principal-inertia frame (ximat), 81 deg about z from the base's frame on B3's
        # model, which turned most of the pitch rate into roll rate.
        R = d.site_xmat[imu].reshape(3, 3)
        roll, pitch, yaw = math.atan2(R[2, 1], R[2, 2]), math.asin(-R[2, 0]), math.atan2(R[1, 0], R[0, 0])
        av = np.zeros(6)
        mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_SITE, imu, av, 1)
        imu_now = (pitch, av[1])
        fw.vn100(-math.degrees(yaw), -math.degrees(pitch), math.degrees(roll), av[0], -av[1], -av[2], now)
        for bus, port in enumerate(ports):
            while (f := port.recv(0)) is not None:
                fw.can_rx(bus, f[0], f[1], f[2], now)
        fw.tick(now, True)
        for bus, cid, data, ext in fw.tx():
            ports[bus].send(cid, data, ext)
        while (f := devices.recv(0)) is not None:
            if f[2] and (f[0] >> 8) == 1:
                vesc[f[0] & 0xFF] = int.from_bytes(f[1][:4], 'big', signed=True) / 1000.0
        for bus, port in enumerate(ports):
            while (f := port.recv(0)) is not None:
                fw.can_rx(bus, f[0], f[1], f[2], now)
        s = fw.snapshot()
        if not running and s.mode == 3:
            running, t0 = True, now / 1e6
        if running:
            for (mid, bus, dr, phi0), e, jn in zip(cal, emu, joints):
                on = e.mode == 2 and not e.fault_word
                lim = min(float(e.params['limit_torque']), 120.0)
                d.ctrl[rb.act[jn]] = dr * max(-lim, min(lim, e.cmd[4])) if on else 0.0
            for vid, side in ((10, 'l'), (11, 'r')):
                d.ctrl[rb.act[f'wheel_{side}']] = wheel_dir[vid] * kt * vesc[vid]
            p.stops()
            mj.mj_step(m, d)
            clock['t'] += m.opt.timestep
            tr = p.truth()
            log['t'].append(now / 1e6 - t0 + m.opt.timestep)
            for key in ('theta', 'x', 'v'):
                log[key].append(tr[key])
            log['L'].append(sum(tr['L']) / 2)
            log['fw_theta'].append(s.theta)
            log['mode'].append(s.mode)
            log['imu_pitch'].append(imu_now[0])
            log['imu_q'].append(imu_now[1])
        elif now > 2_000_000:
            raise RuntimeError(f'the firmware did not arm: {fwlib.MODES[s.mode]}, boot {s.boot_mask:#x}')
        now += 1000
    log['bus_v'] = p.bus_v
    return log


def summary(fwl: dict, pyl: dict) -> dict:
    t = np.asarray(pyl['t'])
    out = {'seconds': float(t[-1]), 'fell': bool(np.max(np.abs(fwl['theta'])) > 0.35),
           'worst_theta_deg_firmware': float(np.degrees(np.max(np.abs(fwl['theta'])))),
           'worst_theta_deg_python': float(np.degrees(np.max(np.abs(pyl['theta'])))),
           'theta_estimate_error_deg': float(np.degrees(np.max(np.abs(np.asarray(fwl['fw_theta']) - np.asarray(fwl['theta']))))),
           'final_mode': fwlib.MODES[fwl['mode'][-1]], 'bus_v': fwl['bus_v']}
    # the emulated VN-100 is self-consistent: its pitch rate is its pitch angle's rate (B3's model caught a gyro read in
    # the base's principal-inertia frame: 1/6 of the true pitch rate)
    dp = np.diff(fwl['imu_pitch']) / np.diff(fwl['t'])
    q = 0.5 * (np.asarray(fwl['imu_q'][1:]) + np.asarray(fwl['imu_q'][:-1]))
    out['imu_pitch_rate_error'] = float(np.max(np.abs(dp - q)))
    for key, scale in (('x', 1.0), ('v', 1.0), ('L', 1.0), ('theta', 180 / math.pi)):
        a = np.interp(t, fwl['t'], fwl[key]) * scale
        b = np.asarray(pyl[key]) * scale
        out[f'worst_diff_{key}'] = float(np.max(np.abs(a - b)))
    for when in (3.9, 5.9, 7.9):
        k = int(np.searchsorted(t, when))
        out[f'at_{when}s'] = {'x_fw': round(float(np.interp(when, fwl['t'], fwl['x'])), 3), 'x_py': round(float(pyl['x'][k]), 3),
                              'v_fw': round(float(np.interp(when, fwl['t'], fwl['v'])), 3), 'v_py': round(float(pyl['v'][k]), 3),
                              'L_fw_mm': round(float(np.interp(when, fwl['t'], fwl['L'])) * 1000, 1), 'L_py_mm': round(float(pyl['L'][k]) * 1000, 1)}
    return out


if __name__ == '__main__':
    print(json.dumps(summary(run_firmware(), run_python()), indent=1))
