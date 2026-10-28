"""The firmware reference's own tests: the protocols, the flywheel numbers, and every hard safety rule exercised end to
end on the simulated turret (sim_turret.py). Writes exports/turret/firmware/firmware.json.

    .venv/bin/python firmware/turret/test_firmware.py [--out DIR]

Protocols    STS3215 packets and sign-magnitude fields; DShot frames (bidirectional checksum), eRPM telemetry and its
             GCR line code, EDT frames; every CAN frame packs into 8 bytes and back
Numbers      95 fps on Ø38 = 15,269 rpm = 106,883 eRPM; the limit 116,550 eRPM (D68: n_105); Ø36 refused
Safety       the tilt never above level at any command, through homing, the stray-ball depression and the lift rule;
             no spin and no dial step without ARM, the 1 kHz train, a fresh heartbeat and the host's re-arm; zero
             throttle in the same millisecond a condition is lost; the 800 ms ramp never steps, nor does a new set
             speed while spinning; no DShot frame while the ESCs are unpowered; SAFE within 100 ms of
             the first eRPM read over the limit with the converter bypassed (20.5 V), latched until cleared with the
             line released; one corrupt telemetry frame is not a fault; a ball over 105 fps latches SAFE; pan and tilt live and under
             100 deg/s while disarmed; the feed servo leaves the bus on a release and is re-initialised on the next arm
Host         host.py end to end with mount robot: homing, no arming before the mount's table is loaded, the CONFIG rows
             in the firmware, an aim, 24 balls, and people near: fire refused, pan and tilt held to 50 deg/s
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import can_msgs as M  # noqa: E402
import config as C  # noqa: E402
import dshot  # noqa: E402
import sts  # noqa: E402
from sim_turret import SimRig  # noqa: E402

R = Path(__file__).resolve().parents[2]


class Host:
    """A minimal host on the simulated CAN segment."""

    def __init__(self, rig: SimRig):
        self.rig, self.hw = rig, rig.hw
        self.arm = False
        self.hb_on = True
        self.n = 0
        self.next_hb = 0.0
        self.frames = []
        self.dshot_log = []
        orig = self.hw.dshot

        def spy(frames):
            self.dshot_log.append((self.hw.t, [dshot.value_throttle((dshot.unframe(f) or (0, 0))[0]) if f is not None else 0.0 for f in frames]))
            orig(frames)
        self.hw.dshot = spy

    def run(self, s: float, until=None) -> bool:
        end = self.hw.t + s
        while self.hw.t < end - 1e-9:
            if self.hb_on and self.hw.t >= self.next_hb:
                self.next_hb = self.hw.t + 0.1
                self.n += 1
                self.send('HOST_HEARTBEAT', counter=self.n & 0xFF, host_state=1, flags=1 if self.arm else 0)
            self.rig.step()
            while self.hw.to_host:
                t, cid, data = self.hw.to_host.popleft()
                self.frames.append((t,) + M.unpack(cid, data))
            if until is not None and until():
                return True
        return False

    def send(self, name, **kw):
        self.hw.to_fw.append(M.pack(name, **kw))

    @property
    def fw(self):
        return self.rig.fw

    def events(self, code, since=0.0):
        return [(t, f) for t, n, f in self.frames if n == 'EVENT' and f['code'] == code and t >= since]

    def shots(self, since=0.0):
        return [(t, f) for t, n, f in self.frames if n == 'SHOT' and t >= since]

    def arm_up(self) -> bool:
        self.hw.set_pendant(True)
        self.arm = False
        self.run(0.3)
        self.arm = True
        ok = self.run(3.0, lambda: self.fw.state == 'ARMED')
        self.run(0.8)
        return ok

    def boot(self):
        self.run(15.0, lambda: self.fw.state == 'IDLE')
        self.send('CONFIG', kind=M.CF_MOUNT, a=0)
        self.run(0.1)


def check(out: dict, name: str, ok: bool, **info):
    out[name] = dict(info, pass_=bool(ok))
    return ok


def t_protocols(out):
    rng = random.Random(1)
    ok = sts.packet(1, sts.PING) == bytes([0xFF, 0xFF, 0x01, 0x02, 0x01, 0xFB])
    for _ in range(500):
        sid, params = rng.randrange(254), bytes(rng.randrange(256) for _ in range(rng.randrange(8)))
        p = sts.parse(sts.packet(sid, sts.WRITE, params))
        ok = ok and p == (sid, sts.WRITE, params)
        v = rng.randrange(-30000, 30000)
        ok = ok and sts.from_sm(sts.le16(sts.sm16(v))) == v
    bad = bytearray(sts.packet(3, sts.READ, bytes([56, 2])))
    bad[-1] ^= 1
    ok = ok and sts.parse(bytes(bad)) is None
    check(out, 'sts_packets', ok, cases=500)
    ok = True
    for v in range(0, 2048):
        for tel in (False, True):
            ok = ok and dshot.unframe(dshot.frame(v, tel)) == (v, tel)
    ok = ok and dshot.unframe(dshot.frame(1000), bidir=False) is None    # the inverted checksum is not the plain one
    worst = 0.0
    for erpm in [1000.0 * 1.07 ** k for k in range(80)]:
        if erpm > 160000:
            break
        w = dshot.encode_erpm(erpm)
        kind, back = dshot.decode_telemetry(w)
        worst = max(worst, abs(back - erpm) / erpm)
        ok = ok and kind == 'erpm' and dshot.gcr_decode(dshot.gcr_encode(w)) == w
    ok = ok and dshot.decode_telemetry(dshot.encode_erpm(0)) == ('erpm', 0.0)
    ok = ok and dshot.decode_telemetry(dshot.encode_erpm(500)) == ('erpm', 0.0)      # below 919 eRPM: stopped
    ok = ok and dshot.decode_telemetry(dshot.encode_edt('temp_c', 47)) == ('temp_c', 47)
    ok = ok and dshot.decode_telemetry(dshot.encode_erpm(60000) ^ 0x1) is None
    check(out, 'dshot_frames_and_telemetry', ok and worst < 0.005, erpm_quantisation_worst=round(worst, 5))
    ok = True
    for cid, (name, fmt, fields) in M.MSGS.items():
        kw = {f: k + 1 for k, f in enumerate(fields)}
        c2, data = M.pack(name, **kw)
        ok = ok and c2 == cid and len(data) <= 8 and M.unpack(cid, data)[1] == kw
    check(out, 'can_frames', ok, messages=len(M.MSGS))


def t_numbers(out):
    rpm = C.set_rpm(95.0, 38)
    check(out, 'set_speed', abs(rpm - 15269) < 1 and round(rpm * C.POLE_PAIRS) == 106883, rpm=round(rpm, 1),
          erpm=round(rpm * C.POLE_PAIRS), throttle=round(C.Config().throttle_for(rpm), 3))
    check(out, 'erpm_limit', C.ERPM_LIMIT == 116550 and C.NO_LOAD_RPM_TRIM * 1.018 * 1.020 < C.NO_LOAD_RPM_105 and
          C.TRIP_FPS == C.CAP_FPS == 105.0, erpm=C.ERPM_LIMIT, rpm=C.ERPM_LIMIT / C.POLE_PAIRS,
          trimmed_rpm_warm_high_rail=round(C.NO_LOAD_RPM_TRIM * 1.018 * 1.020))
    rig = SimRig(seed=11)
    h = Host(rig)
    h.boot()
    h.send('CONFIG', kind=M.CF_TYRE, a=36)
    h.run(0.2)
    refused = bool(h.fw.latched & M.F_CONFIG_MISMATCH) and h.fw.cfg.tyre_mm == 38
    no_arm = not h.arm_up()
    h.send('CONFIG', kind=M.CF_TYRE, a=38)
    h.arm = False
    h.run(0.3)
    h.arm = True
    back = h.run(3.0, lambda: h.fw.state == 'ARMED')
    check(out, 'tyre_36_refused', refused and no_arm and back, refused=refused, arming_refused=no_arm, arms_on_38=back)


def t_tilt(out):
    rig = SimRig(seed=21, hopper=5)
    h = Host(rig)
    h.boot()
    for tilt in (10.0, 0.5, 0.0, -5.0, -30.0, 3.0):
        h.send('AIM', pan_cdeg=int((h.fw.pan_deg() or 0) * 100), tilt_cdeg=int(tilt * 100), rate=90)
        h.run(1.0)
    h.arm_up()
    h.send('AIM', pan_cdeg=int((h.fw.pan_deg() or 0) * 100), tilt_cdeg=-2500, rate=90)
    h.run(1.0)
    h.send('FIRE', balls=5, rate_d=30, fps_d=0, req=1)       # the stray depression, and the lift rule at -25 deg
    h.run(20.0, lambda: bool(h.events(M.EV_BURST_DONE)))
    h.send('AIM', pan_cdeg=int((h.fw.pan_deg() or 0) * 100), tilt_cdeg=500, rate=90)
    h.run(1.0)
    check(out, 'tilt_never_above_level', rig.hw.tilt_max_seen <= 0.05 and h.fw.tilt_cmd <= 0.0,
          max_true_tilt_deg=round(rig.hw.tilt_max_seen, 3), clamped_commands=h.fw.tilt_clamped,
          lifts=len(h.events(M.EV_LIFT)))


def t_arm_conditions(out):
    rig = SimRig(seed=31, hopper=20)
    h = Host(rig)
    h.boot()
    # no ARM: FIRE refused, nothing turns
    h.arm = True
    h.run(0.5)
    h.send('FIRE', balls=3, rate_d=30, fps_d=0, req=1)
    h.run(2.0)
    a = max(max(v) for _, v in h.dshot_log) == 0.0 and not h.shots() and h.events(M.EV_SHOT_REFUSED)
    check(out, 'no_spin_without_arm', a, max_throttle=max(max(v) for _, v in h.dshot_log))
    # the pendant held with the request already high: no arming until the request cycles (the re-arm)
    rig.hw.set_pendant(True)
    h.run(1.0)
    waits = h.fw.state == 'IDLE' and h.fw.rearm_wait
    h.arm = False
    h.run(0.3)
    h.arm = True
    armed = h.run(2.0, lambda: h.fw.state == 'ARMED')
    check(out, 'rearm_needs_the_request_to_cycle', waits and armed, waited=waits, armed_after=armed)
    # the heartbeat stops while spinning: zero throttle in the same millisecond SAFE is entered
    h.run(0.8)
    h.send('COMMAND', code=M.CMD_BENCH_SPIN_SPEED, a=950, b=100)
    h.run(3.0, lambda: h.fw.state == 'READY')
    t_stop = rig.hw.t
    h.hb_on = False
    h.run(0.5, lambda: h.fw.state != 'READY')
    t_safe = rig.hw.t
    after = [v for t, v in h.dshot_log if t >= t_safe]
    h.run(0.1)
    check(out, 'heartbeat_lost_zero_throttle', h.fw.state in ('SAFE', 'IDLE') and after and max(after[0]) == 0.0 and
          t_safe - t_stop <= C.HEARTBEAT_MAX_AGE_S + 0.1 + 0.002,
          safe_after_last_heartbeat_s=round(t_safe - (h.next_hb - 0.1), 3),
          throttle_at_safe=after[0] if after else None)
    h.hb_on = True
    # 300 Hz on the pair: the hardware stays armed (the drawn monostable), the firmware will not
    h.arm = False
    h.run(0.3)
    h.arm = True
    h.run(2.0, lambda: h.fw.state == 'ARMED')
    t0 = rig.hw.t
    rig.hw.set_ring_fault('f300')
    h.run(0.5)
    hw_armed = rig.hw.arm
    h.send('COMMAND', code=M.CMD_BENCH_SPIN_SPEED, a=950, b=100)
    h.run(1.0)
    spun = max((max(v) for t, v in h.dshot_log if t >= t0), default=0.0)
    safe = h.events(M.EV_SAFE, t0)
    check(out, 'wrong_pulse_train_refused', hw_armed and spun == 0.0 and safe and safe[0][1]['a'] & M.F_PULSE,
          hardware_still_armed=hw_armed, firmware_safe_ms=round((safe[0][0] - t0) * 1000, 1) if safe else None,
          max_throttle=spun)
    rig.hw.set_ring_fault(None)


def t_ramp_and_guard(out):
    # the ramp never steps; with the converter bypassed (the ESCs on the 20.5 V pack) the guard trips within 100 ms of
    # the first read over the limit and latches
    rig = SimRig(seed=41, rail_v=20.5, hopper=0)
    rig.hw.feed_unplugged = True
    h = Host(rig)
    h.boot()
    h.arm_up()
    t0 = rig.hw.t
    h.send('COMMAND', code=M.CMD_BENCH_SPIN, a=1000, b=30)
    h.run(3.0, lambda: bool(h.events(M.EV_SAFE, t0)))
    g = h.fw.fly.guard
    lat = g.trip_t - g.first_over_t if g.trip_t else None
    g_trip_t, g_trip_erpm, g_max = g.trip_t, g.trip_erpm, g.max_erpm
    steps = [b[0] - a[0] for (_, a), (_, b) in zip(h.dshot_log, h.dshot_log[1:]) if b[0] > a[0]]
    zero_after = [v for t, v in h.dshot_log if t > g_trip_t] if g_trip_t else []
    h.send('COMMAND', code=M.CMD_BENCH_FEED_STEPS, a=1, b=30)
    h.run(0.5)
    still = h.fw.state in ('FAULT', 'SAFE')
    h.send('COMMAND', code=M.CMD_CLEAR_FAULTS)                 # refused while ARM is high
    h.run(0.3)
    held = bool(h.fw.latched & M.F_ERPM_LIMIT)
    rig.hw.set_pendant(False)
    h.arm = False
    h.run(0.3)
    h.send('COMMAND', code=M.CMD_CLEAR_FAULTS)
    h.run(0.3)
    cleared = not h.fw.latched & M.F_ERPM_LIMIT
    check(out, 'ramp_never_steps', max(steps) <= 1.0 / (C.RAMP_S * 1000) + 0.002,
          max_throttle_step_per_ms=round(max(steps), 5), ramp_slope_per_ms=round(1.0 / (C.RAMP_S * 1000), 5))
    check(out, 'erpm_guard_bypassed_converter', lat is not None and lat <= 0.100 and all(max(v) == 0 for v in zero_after) and
          still and held and cleared, latency_ms=round(lat * 1000, 1) if lat is not None else None,
          trip_erpm=round(g_trip_erpm), max_erpm=round(g_max), dial_refused=still, latched_while_armed=held,
          cleared_when_released=cleared)
    # one corrupt frame over the limit is not a fault
    gd = h.fw.fly.guard.__class__()
    tripped = [gd.check(0, 0.001 * k, 190000.0 if k == 5 else 106000.0) for k in range(20)]
    check(out, 'one_bad_frame_no_trip', not any(tripped) and not gd.tripped)


def t_set_point_ramps(out):
    # a new set speed (or throttle) while spinning ramps over RAMP_S: never a step up (the ring's current) or down (with
    # the ESC's complementary PWM a step down brakes into the 12 V rail; docs/turret-wiring.md 3.6); no frame while off
    import flywheel
    fl = flywheel.Flywheels(C.Config())
    off_frames = fl.update(0.0)
    fl.esc_power(0.0, True)
    t, outs = 0.0, []
    while t < C.ESC_ARM_S + 0.01:
        fl.update(t)
        t += 0.001
    fl.spin_speed(t, 15269.0)
    for target_t, rpm in ((t + 0.8, 10000.0), (t + 1.6, 15269.0)):
        while t < target_t:
            fl.update(t)
            outs.append(fl.w[0].out)
            t += 0.001
        fl.spin_speed(t, rpm)
    while t < target_t + 0.8:
        fl.update(t)
        outs.append(fl.w[0].out)
        t += 0.001
    steps = [abs(b - a) for a, b in zip(outs, outs[1:])]
    lim = 1.0 / (C.RAMP_S * 1000) + C.TRIM_SLEW + 0.0005
    check(out, 'set_point_changes_ramp', max(steps) <= lim and off_frames == (None, None),
          max_throttle_step_per_ms=round(max(steps), 5), limit_per_ms=round(lim, 5), no_frames_while_off=off_frames == (None, None))


def t_overspeed(out):
    rig = SimRig(seed=51, hopper=10)
    h = Host(rig)
    h.boot()
    h.arm_up()
    h.send('COMMAND', code=M.CMD_BENCH_SPIN_SPEED, a=950, b=100)
    h.run(3.0, lambda: h.fw.state == 'READY')
    t0 = rig.hw.t
    rig.hw.gate_pair(0.0017)                                   # 115.8 fps
    h.run(0.5)
    safe = h.events(M.EV_SAFE, t0)
    check(out, 'ball_over_105fps_latches_safe', bool(safe and safe[0][1]['a'] & M.F_OVERSPEED) and
          bool(h.fw.latched & M.F_OVERSPEED) and rig.hw.trip_q, firmware=bool(safe), hardware_trip=rig.hw.trip_q)


def t_aim_disarmed(out):
    rig = SimRig(seed=61)
    h = Host(rig)
    h.boot()
    pans, tilts = [], []
    p0 = h.fw.pan_deg() or 0.0
    for goal, tilt in ((p0 + 170.0, -25.0), (p0 - 200.0, 0.0), (p0 + 30.0, -12.0)):
        h.send('AIM', pan_cdeg=int(goal * 100), tilt_cdeg=int(tilt * 100), rate=100)
        last_p, last_t = rig.hw.true_pan(), rig.hw.true_tilt()
        for _ in range(300):
            h.run(0.01)
            pans.append(abs(rig.hw.true_pan() - last_p) / 0.01)
            tilts.append(abs(rig.hw.true_tilt() - last_t) / 0.01)
            last_p, last_t = rig.hw.true_pan(), rig.hw.true_tilt()
    err = abs(((h.fw.pan_deg() or 0) - (p0 + 30.0) + 180) % 360 - 180)
    check(out, 'aim_live_disarmed_capped', max(pans) <= 100.0 and max(tilts) <= 100.0 and err <= C.AIM_TOL_DEG and
          not rig.hw.arm, max_pan_rate=round(max(pans), 1), max_tilt_rate=round(max(tilts), 1),
          final_pan_error_deg=round(err, 3))


def t_feed_release(out):
    rig = SimRig(seed=71, hopper=40)
    h = Host(rig)
    h.boot()
    h.arm_up()
    t0 = rig.hw.t
    h.send('FIRE', balls=8, rate_d=30, fps_d=0, req=1)
    h.run(5.0, lambda: len(h.shots(t0)) >= 3)
    rig.hw.set_pendant(False)
    h.arm = False
    h.run(1.0)
    off = h.fw.feed.state == 'OFFLINE' and not rig.hw.feed_servo.powered and bool(h.events(M.EV_SERVO_LOST, t0))
    t1 = rig.hw.t
    h.arm_up()
    back = h.events(M.EV_SERVO_BACK, t1)
    s = rig.hw.feed_servo
    regs = (s.torque_on, s.torque_limit, s.acc, s.goal_speed) == (True, C.SERVO_TORQUE_LIMIT, C.FEED_ACC,
                                                                    C.FEED_SPEED_CPS)
    t2 = rig.hw.t
    h.send('FIRE', balls=3, rate_d=30, fps_d=0, req=2)
    h.run(10.0, lambda: bool(h.events(M.EV_BURST_DONE, t2)))
    fired = [f for _, f in h.shots(t2) if not f['flags'] & M.S_STRAY]
    check(out, 'feed_servo_drop_off_and_reinit', off and back and regs and len(fired) == 3, offline_on_release=off,
          back_ms_after_arm=round((back[0][0] - t1) * 1000) if back else None, registers_rewritten=regs,
          balls_after=len(fired))
    fast = [f['fps_d'] / 10 for _, f in h.shots(t0)]
    check(out, 'every_ball_under_105fps', max(fast) <= C.TRIP_FPS, fastest_fps=max(fast), balls=len(fast))


def t_host_bridge(out):
    """host.py end to end on the simulated turret, mount robot: it homes; arming is refused before the mount's table is
    loaded; the CONFIG rows land in the firmware (N5's lidar table, the mount, Ø38, the launch ratio); an aim; 24 balls;
    then people near: a FIRE refused, and the pan held to 50 deg/s, both for an aim already under way and a new one."""
    import tempfile
    import host as H
    rig = SimRig(seed=81, hopper=30)
    with tempfile.TemporaryDirectory() as tmp:
        hb = H.TurretHost(H.SimLink(rig), 'robot', log_dir=Path(tmp), auto_config=False, link_name='test_firmware.py')
        homed = hb.start(20.0)['homed']
        hb.sim_pendant(True)
        no_table = hb.arm()
        refused = not no_table['ok'] and 'table' in no_table.get('refused', '') and not rig.fw.host_arm
        cfg = hb.load_config()
        fw = rig.fw.cfg
        table = [(round(a / 10.0, 1), round(b / 100.0, 2)) for k, i, a, b in hb.setup['rows'] if k == M.CF_DEPRESSION]
        robot = H.table_rows(H.LIDAR_JSON) or list(C.ROBOT_DEPRESSION)
        landed = (cfg['ok'] and fw.mount == 'robot' and fw.tyre_mm == 38 and not rig.fw.cfg_bad and
                  [(round(p, 1), round(m, 2)) for p, m in fw.depression] == table == [(round(p, 1), round(m, 2)) for p, m in robot] and
                  abs(fw.launch_ratio - round(C.LAUNCH_RATIO * 10000) / 10000.0) < 1e-9 and
                  sorted(fw.throttle_map) == sorted((t / 1000.0, float(r)) for t, r in hb.setup['throttle_map']))
        aim = hb.aim(10.0, -8.0, wait=True)
        armed = hb.arm()['ok']
        t0 = rig.hw.t
        burst = hb.fire(24, wait=True, timeout=40.0)
        balls = [f for _, f in hb.tt.shots_since(t0) if not f['flags'] & M.S_STRAY]
        fastest = max((f['fps_d'] / 10.0 for _, f in hb.tt.shots_since(t0)), default=0.0)

        def pan_rates(seconds):
            rates, last = [], rig.hw.true_pan()
            for _ in range(int(seconds / 0.01)):
                hb.wait(0.01)
                p = rig.hw.true_pan()
                rates.append(abs(p - last) / 0.01)
                last = p
            return rates
        # people near during a burst: the burst stops and its wheels spin down; a new FIRE is refused
        t1 = rig.hw.t
        hb.fire(4)
        hb.wait_for(lambda: any(t >= t1 for t, _f in hb.tt.shots), 5.0)
        t_near = rig.hw.t
        near = hb.set_people_near(True)
        held = hb.fire(3)
        hb.wait(1.5)
        ended = [f['c'] for _t, f in hb.tt.ev(M.EV_BURST_DONE, t1)]
        shots_held = [f for t, f in hb.tt.shots if t >= t_near + 0.5]
        wheels_off = hb.tt.wheels.get('rpm_l', 1) == 0 and hb.tt.wheels.get('rpm_r', 1) == 0
        # an aim under way at 90 deg/s slows to 50 when people near is set; a new aim runs at 50
        hb.set_people_near(False)
        p0 = hb.tt.pan()
        hb.aim(p0 + 150.0, -5.0, absolute=True)
        fast = max(pan_rates(0.6))
        hb.set_people_near(True)
        slowing = pan_rates(0.3)                                   # the servo's own deceleration to the new speed
        under_way = max(pan_rates(3.0))
        hb.wait_for(hb._reached, 5.0)
        hb.aim(hb.tt.pan() - 100.0, -5.0, absolute=True)
        fresh = max(pan_rates(3.0))
        hb.set_people_near(False)
        hb.disarm()
        log_path = hb.close()
        log = json.loads(log_path.read_text()) if log_path else {}
        logged = log.get('counts', {})
    ok = (homed and refused and landed and aim.get('reached') and armed and burst.get('done') and len(balls) == 24 and
          fastest <= C.TRIP_FPS and ended == [M.BURST_END['aborted']] and not held['ok'] and not shots_held and wheels_off and
          fast > 80.0 and under_way <= H.PEOPLE_NEAR_RATE + 0.5 and fresh <= H.PEOPLE_NEAR_RATE + 0.5 and
          log.get('mode') == 'sim' and logged.get('shots', 0) >= 24 and
          min(logged.get(k, 0) for k in ('feed', 'power', 'health', 'events')) > 0)
    check(out, 'host_bridge', ok, homed=homed, arm_refused_without_table=refused, config_rows=len(hb.setup['rows']),
          config_landed=landed, depression_rows=len(table), throttle_map_rows=len(hb.setup['throttle_map']),
          aim_reached=aim.get('reached'), armed=armed, balls=len(balls), burst_end=burst.get('end'), fastest_fps=fastest,
          people_near_in_a_burst=near['acted'], burst_ends=[H.BURST_WHY.get(c, c) for c in ended],
          shots_while_held=len(shots_held), wheels_stopped=wheels_off, fire_held=held.get('refused'),
          pan_rate_before_people_near=round(fast, 1), pan_rate_while_slowing=round(max(slowing), 1),
          pan_rate_under_way=round(under_way, 1), pan_rate_new_aim=round(fresh, 1),
          log={k: logged.get(k) for k in ('shots', 'feed', 'power', 'health', 'events', 'commands')})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(R / 'exports' / 'turret' / 'firmware'))
    a = ap.parse_args()
    out = {}
    for fn in (t_protocols, t_numbers, t_tilt, t_arm_conditions, t_ramp_and_guard, t_set_point_ramps, t_overspeed,
               t_aim_disarmed, t_feed_release, t_host_bridge):
        fn(out)
    ok = all(v['pass_'] for v in out.values())
    res = {'pass': ok, 'cases': out, 'scope': __doc__.split('\n\n')[1].strip()}
    p = Path(a.out)
    p.mkdir(parents=True, exist_ok=True)
    (p / 'firmware.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    for k, v in out.items():
        info = ', '.join(f'{a2}={b2}' for a2, b2 in v.items() if a2 != 'pass_')
        print(f"{'pass' if v['pass_'] else 'FAIL'}  {k}  {info}")
    print('ALL PASS' if ok else 'FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
