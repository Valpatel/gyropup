"""The turret firmware: the reference the Feather M4 CAN port follows (docs/turret-firmware.md). Pure Python.

One `tick(t)` per millisecond. The board is behind `HAL` (the simulated turret implements it; the Feather port
replaces it with pins, timers and the two buses). The arm chain is hardware: this code reads ARM_IN, TRIP_IN and
PULSE_MON and can only ever command zero throttle and stop the dial; it cannot raise ARM.

The rules it holds, whatever the host sends:
  - the barrel never points above level: every tilt goal clamps to [max(-25, the depression table), 0] deg, and the
    tilt servo's own angle limits are checked at boot;
  - nothing spins or feeds without ARM_IN high, the 1 kHz train good on PULSE_MON, a host heartbeat no older than
    200 ms, the host's arm request (seen low after the line is held: the pendant alone never arms, and nothing re-arms
    by itself after a SAFE), no trip and no latched fault; losing any of them is zero throttle and a stopped dial in
    the same millisecond;
  - no dial step without both wheels' eRPM fresh, under 1.10 x KV x 12 V x 7 and READY (the pre-feed check);
  - pan and tilt stay live when disarmed, at most 100 deg/s; homing (homing.py, unchanged) before anything moves on
    command.
"""
from __future__ import annotations

import math
from collections import deque
from typing import List, Optional, Tuple

import can_msgs as M
import config as C
import homing as hm
import sts
from feed import FAULT as FEED_FAULT
from feed import MOVING, OFFLINE, PARKED, Burst, FeedDriver, FeedPort
from flywheel import Flywheels

ARMED_STATES = ('ARMED', 'SPIN_UP', 'READY', 'FIRING')
LATCHING = M.F_ERPM_LIMIT | M.F_OVERSPEED | M.F_HOME_FAILED | M.F_SERVO_CONFIG | M.F_CONFIG_MISMATCH
PAN_ACC = 254                  # register 41 for pan and tilt: the highest ramp (~0.12 s to full speed at the turret)
HOME_SWEEP_COUNTS = int((hm.MAX_SWEEP_DEG + 40.0) / C.PAN_PER_COUNT)
SEG_COUNTS = 30000             # the longest relative step written (a step-mode goal is 15 bits and a sign)
HOME_TIMEOUT_S = 15.0          # homing that has not found the index by then has failed (a stuck pan, a dead hall)


class HAL:
    """What the firmware needs from the board."""

    def arm_in(self) -> bool: raise NotImplementedError                      # D12
    def trip_in(self) -> bool: raise NotImplementedError                     # A1
    def pulse_edges(self) -> List[float]: raise NotImplementedError          # A3 falling edges (opto on) since the last call
    def hall_edges(self) -> List[Tuple[float, bool]]: raise NotImplementedError   # D11 (time, rising)
    def gate_edges(self) -> List[Tuple[float, int]]: raise NotImplementedError    # D9/D10 (time, 1 or 2)
    def esc_frames(self) -> List[Tuple[int, float, int]]: raise NotImplementedError  # (wheel, time, 16-bit word)
    def dshot(self, frames: Tuple[int, int]): raise NotImplementedError      # D5/D6, one frame per wheel per tick; None: pin low
    def servo_txn(self, pkt: bytes) -> Optional[bytes]: raise NotImplementedError   # Serial1 + D4
    def can_recv(self) -> List[Tuple[int, bytes]]: raise NotImplementedError
    def can_send(self, cid: int, data: bytes): raise NotImplementedError
    def can_counters(self) -> Tuple[int, int, int]: return 0, 0, 0           # TEC, REC, bus-off count
    def laser(self, on: bool): pass                                          # A5 (not D13: the bootloader pulses it)
    def bus_mv(self) -> int: return 24000                                    # A0, the ring's +24 V through 10:1


class PulseMonitor:
    """PULSE_MON: the 4N35's output. Good = at least 15 periods of 0.85-1.15 ms in the last 20 ms and none shorter;
    longer gaps that are whole periods are dropped pulses (the ring-drop counter), which the 20 ms monostable rides."""

    def __init__(self):
        self.last: Optional[float] = None
        self.good: deque = deque()
        self.short: deque = deque()
        self.drops = 0
        self.ok = False

    def update(self, t: float, edges: List[float]):
        lo, hi = C.PULSE_PERIOD_S * (1 - C.PULSE_TOL), C.PULSE_PERIOD_S * (1 + C.PULSE_TOL)
        for e in edges:
            if self.last is not None:
                p = e - self.last
                if lo <= p <= hi:
                    self.good.append(e)
                elif p < lo:
                    self.short.append(e)
                else:
                    k = round(p / C.PULSE_PERIOD_S)
                    if abs(p - k * C.PULSE_PERIOD_S) <= C.PULSE_TOL * C.PULSE_PERIOD_S:
                        self.drops += k - 1
            self.last = e
        for q in (self.good, self.short):
            while q and q[0] < t - C.PULSE_WINDOW_S:
                q.popleft()
        self.ok = (len(self.good) >= C.PULSE_MIN_GOOD and not self.short and self.last is not None
                   and t - self.last <= C.PULSE_GAP_S)


class TurretFirmware:
    def __init__(self, hal: HAL, cfg: Optional[C.Config] = None, index_offset_deg: float = 0.0):
        self.hal = hal
        self.cfg = cfg or C.Config()
        self.index_offset_deg = index_offset_deg          # assembly calibration (homing.calibrate)
        self.master = sts.Master(hal.servo_txn, retries=C.SERVO_RETRIES)
        self.feed = FeedDriver(FeedPort(self.master))
        self.fly = Flywheels(self.cfg)
        self.pulse = PulseMonitor()
        self.t = 0.0
        self.state, self.state_t = 'BOOT', 0.0
        self.arm = False
        self.arm_rise_t = self.arm_fall_t = None
        self.trip = False
        self.trip_t = None
        self.hb_t = -10.0
        self.host_arm = False
        self.rearm_wait = True
        self.latched = 0
        self.causes = 0
        self.cfg_bad = set()                             # CONFIG rows refused: 'tyre', 'ring' (F_CONFIG_MISMATCH)
        self.pan_ok = self.tilt_ok = False
        self.next_init = 0.0
        # pan
        self.homing: Optional[hm.Homing] = None
        self.tracker: Optional[hm.PanTracker] = None
        self.check: Optional[hm.IndexCheck] = None
        self.home_v = 0.0
        self.home_t0 = 0.0
        self.home_sent_t = 0.0
        self.pan_speed_cps = 0.0
        self.pan_read_t = 0.0
        self.pan_goal = 0.0
        self.pan_move: Optional[dict] = None
        self.pan_cmd_t = 0.0
        self.pan_speed_reg = None
        self.rate = C.PAN_SPEED_MAX
        self.plus_from: Optional[float] = None           # the unwrapped count where +pan motion last began
        # tilt
        self.tilt_deg = 0.0
        self.tilt_rate = 0.0
        self.tilt_read_t = 0.0
        self.tilt_goal = 0.0
        self.tilt_cmd: Optional[float] = None
        self.tilt_written_t = -1.0
        self.tilt_speed_reg = None
        self.tilt_clamped = 0                             # host tilt goals above level that were clamped
        # firing
        self.fire_req: Optional[dict] = None
        self.burst: Optional[Burst] = None
        self.spin: Optional[dict] = None
        self.bench: Optional[dict] = None
        self.stray_until = -1.0
        self.stray_tilt = False
        self.lift = False
        self.ready_idle_t = 0.0
        self.gate1: Optional[float] = None
        self.shots = 0
        self.shot_log: List[dict] = []
        self.balls_fired = 0
        self.empties = 0
        self.jams = 0
        self.stream_until = -1.0
        self.stream_period = 0.02
        self.overspeed_t: Optional[float] = None
        self.double_next = False
        self.keepout_t: Optional[float] = None
        # telemetry
        self.next = {'hb': 0.0, 'pose': 0.0, 'wheels': 0.0, 'feed': 0.0, 'power': 0.0, 'health': 0.0, 'read': 0.0,
                     'volt': 0.0}
        self.seq = 0
        self.ev_seq = 0
        self.volts = {C.ID_PAN: 0.0, C.ID_TILT: 0.0, C.ID_FEED: 0.0}
        self.volt_rr = 0
        self.log: List[tuple] = []                       # (t, what, info) for the tests

    # =================================================================== the tick
    def tick(self, t: float):
        self.t = t
        arm = self.hal.arm_in()
        if arm and not self.arm:
            self.arm_rise_t = t
            self.fly.esc_power(t, True)                  # the 2815 re-powers 12 V FLY and 12 V FEED with ARM
        elif self.arm and not arm:
            self.arm_fall_t = t
            self.fly.esc_power(t, False)
            if self.feed.online:
                self._event(M.EV_SERVO_LOST, C.ID_FEED)
            self.feed.power_lost(t)
        self.arm = arm
        if not arm:
            self.rearm_wait = True                      # the pendant alone never arms: the host asks again after it
        trip = self.hal.trip_in()
        if trip and not self.trip:
            self.trip_t = t
        self.trip = trip
        self.pulse.update(t, self.hal.pulse_edges())
        for cid, data in self.hal.can_recv():
            if cid in M.MSGS:
                self._can(t, *M.unpack(cid, data))
        for wheel, tf, word in self.hal.esc_frames():
            self.fly.on_frame(wheel, tf, word)
        self._gates(t, self.hal.gate_edges())
        for te, rising in self.hal.hall_edges():
            if self.state == 'HOMING' and self.homing is not None:
                self.homing.hall_edge(te, rising)
            elif self.check is not None:
                self.check.hall_edge(te, rising, 1 if self.pan_speed_cps > 0 else -1)
        self._servos(t)
        self._safety(t)
        self._run(t)
        self.hal.dshot(self.fly.update(t))
        self._telemetry(t)

    # =================================================================== inputs
    def _can(self, t: float, name: str, f: dict):
        if name == 'HOST_HEARTBEAT':
            self.hb_t = t
            self.host_arm = bool(f['flags'] & 1)
            if not self.host_arm and self.arm:          # the re-arm: the request seen low with the line already held
                self.rearm_wait = False
        elif name == 'AIM':
            self.pan_goal = f['pan_cdeg'] / 100.0
            tilt = f['tilt_cdeg'] / 100.0
            if tilt > C.TILT_MAX_DEG:
                self.tilt_clamped += 1
            self.tilt_goal = min(C.TILT_MAX_DEG, max(C.TILT_MIN_DEG, tilt))
            self.rate = max(1.0, min(C.AIM_RATE_CAP, C.PAN_SPEED_MAX, float(f['rate'] or C.PAN_SPEED_MAX)))
        elif name == 'FIRE':
            self._fire(t, f['balls'], f['rate_d'] / 10.0 or C.RATE_DEFAULT, f['fps_d'] / 10.0, f['req'])
        elif name == 'LASER':
            self.hal.laser(bool(f['on']))
        elif name == 'CONFIG':
            self._config(f)
        elif name == 'COMMAND':
            self._command(t, f)

    def _config(self, f: dict):
        if self.state in ('SPIN_UP', 'READY', 'FIRING'):
            return
        k, i, a, b = f['kind'], f['index'], f['a'], f['b']
        cfg = self.cfg
        if k == M.CF_TYRE:
            if a in C.TYRES_MM:
                cfg.tyre_mm = a
                self.cfg_bad.discard('tyre')
            else:                                         # refused: Ø36 passes the cap on this motor
                self.cfg_bad.add('tyre')
        elif k == M.CF_RING:
            (self.cfg_bad.discard if bool(a) == C.CONTINUOUS_PAN else self.cfg_bad.add)('ring')
        elif k == M.CF_MOUNT and 0 <= a < len(M.MOUNTS):
            cfg.mount = M.MOUNTS[a]
        elif k == M.CF_LAUNCH_RATIO and 8500 <= a <= 11000:
            cfg.launch_ratio = a / 10000.0
        elif k == M.CF_DEPRESSION:
            self._row(cfg.depression, i, (a / 10.0, min(C.TILT_MAX_DEG, max(C.TILT_MIN_DEG, b / 100.0))))
        elif k == M.CF_KEEPOUT:
            self._row(cfg.keepouts, i, (a / 10.0, b / 10.0))
        elif k == M.CF_THROTTLE_MAP and 0 < a <= 1000 and b > 0:
            cfg.throttle_map = [r for r in cfg.throttle_map if abs(r[0] - a / 1000.0) > 1e-6] + [(a / 1000.0, float(b))]
        elif k == M.CF_CLEAR:
            if a == 1:
                cfg.depression = []
            elif a == 2:
                cfg.keepouts = []
            elif a == 3:
                cfg.throttle_map = []
        self.latched = (self.latched | M.F_CONFIG_MISMATCH) if self.cfg_bad else (self.latched & ~M.F_CONFIG_MISMATCH)

    @staticmethod
    def _row(rows: list, i: int, row: tuple):
        if i < len(rows):
            rows[i] = row
        else:
            rows.append(row)

    def _command(self, t: float, f: dict):
        code = f['code']
        if code == M.CMD_REHOME:
            if self.state in ('IDLE', 'FAULT') and self.pan_ok and self.tilt_ok:
                self.latched &= ~M.F_HOME_FAILED
                self._begin_homing(t)
        elif code == M.CMD_STOP:
            self._end_burst(t, 'aborted')
            self.fire_req = None
            if self.bench and self.bench['kind'] == 'feed_steps':
                self._bench_done(t)
        elif code == M.CMD_SPIN_DOWN:
            self._end_burst(t, 'aborted')
            self.fire_req = self.bench = None
            if self.state in ('SPIN_UP', 'READY', 'FIRING'):
                self.fly.stop(t)
                self._enter('ARMED', t)
        elif code == M.CMD_CLEAR_FAULTS:
            if not self.arm:                              # only with the safety line released
                self.latched &= ~(M.F_ERPM_LIMIT | M.F_OVERSPEED)
                self.fly.guard.clear()
                self.feed.clear_fault()
        elif self.cfg.mount == 'bench' and code in (M.CMD_BENCH_FEED_STEPS, M.CMD_BENCH_SPIN,
                                                     M.CMD_BENCH_FIRE_THROTTLE, M.CMD_BENCH_SPIN_SPEED,
                                                     M.CMD_BENCH_FIRE_ANY_AIM):
            if code == M.CMD_BENCH_FIRE_ANY_AIM and self.state == 'READY' and self.bench is None:
                self.bench = {'kind': 'fire_any_aim', 'code': code}   # the wheels already at speed: like a FIRE
                self._fire(t, f['a'], f['c'] / 10.0 or C.RATE_DEFAULT, f['b'] / 10.0, 0)
                return
            if self.state != 'ARMED' or self.bench is not None:
                self._event(M.EV_SHOT_REFUSED, code, M.STATES.index(self.state))
                return
            if code == M.CMD_BENCH_FEED_STEPS:
                if self.feed.state != PARKED:
                    self._event(M.EV_SHOT_REFUSED, code, 100)
                    return
                self.bench = {'kind': 'feed_steps', 'n': f['a'], 'period': 1.0 / max(0.5, f['b'] / 10.0 or 3.0),
                              'next': t, 'issued': 0, 'base': self.feed.stats['settled'], 'code': code}
            elif code == M.CMD_BENCH_SPIN:
                self.bench = {'kind': 'spin', 'hold': f['b'] / 10.0, 'code': code}
                self._spin_up(t, throttle=f['a'] / 1000.0)
            elif code == M.CMD_BENCH_SPIN_SPEED:
                self.bench = {'kind': 'spin', 'hold': f['b'] / 10.0, 'code': code}
                self._spin_up(t, rpm=self.cfg.rpm_for(f['a'] / 10.0))
            elif code == M.CMD_BENCH_FIRE_ANY_AIM:
                self.bench = {'kind': 'fire_any_aim', 'code': code}
                self.fire_req = {'balls': max(1, f['a']), 'rate': f['c'] / 10.0 or C.RATE_DEFAULT, 'req': 0}
                self._spin_up(t, rpm=self.cfg.rpm_for(f['b'] / 10.0))
            else:
                self.bench = {'kind': 'fire_throttle', 'code': code}
                self.fire_req = {'balls': f['b'], 'rate': f['c'] / 10.0 or C.RATE_DEFAULT, 'req': 0}
                self._spin_up(t, throttle=f['a'] / 1000.0)
        elif self.cfg.mount == 'bench' and code == M.CMD_BENCH_STREAM:
            self.stream_until = t + f['b']
            self.stream_period = 1.0 / max(1, min(1000, f['a']))

    def _fire(self, t: float, balls: int, rate: float, fps: float, req: int):
        why = None
        if self.state not in ('ARMED', 'READY'):
            why = M.STATES.index(self.state)
        elif self.tracker is not None and self.cfg.in_keepout(self.tracker.pan_deg() or 0.0):
            why = 200
        elif self.feed.state != PARKED:
            why = 100
        if why is not None:
            self._event(M.EV_SHOT_REFUSED, req, why)
            return
        rpm = self.cfg.rpm_for(fps)
        self.fire_req = {'balls': max(1, balls), 'rate': min(C.RATE_MAX, rate), 'req': req}
        if self.state == 'READY':
            if self.spin and self.spin.get('rpm') and abs(self.spin['rpm'] - rpm) > 1.0:
                self.spin['rpm'] = rpm
                self.fly.spin_speed(t, rpm)
        else:
            self._spin_up(t, rpm=rpm)

    # =================================================================== gates and shots
    def _gates(self, t: float, edges):
        for te, g in edges:
            if g == 1:
                if self.gate1 is not None:
                    self._shot(self.gate1, None)
                self.gate1 = te
                kind = self.burst.on_gate1(te) if self.burst is not None else None
                if kind == 'double':
                    self.log.append((te, 'double', None))
                    self.double_next = True
            elif g == 2 and self.gate1 is not None and te - self.gate1 <= C.GATE_PAIR_MAX_S:
                self._shot(self.gate1, te)
                self.gate1 = None
        if self.gate1 is not None and t - self.gate1 > C.GATE_PAIR_MAX_S:
            self._shot(self.gate1, None)
            self.gate1 = None

    def _shot(self, t1: float, t2: Optional[float]):
        fps = C.GATE_SPACING_M / (t2 - t1) / C.FPS if t2 else 0.0
        flags = 0
        if t2 is None:
            flags |= M.S_GATE1_ONLY
        if t1 <= self.stray_until or (self.spin is None and not self.fly.spinning):
            flags |= M.S_STRAY
        if fps > C.TRIP_FPS:
            flags |= M.S_OVERSPEED
        if not self.arm or (self.arm_fall_t is not None and t1 - self.arm_fall_t < 1.0 and
                            (self.arm_rise_t is None or self.arm_rise_t < self.arm_fall_t)):
            flags |= M.S_AFTER_RELEASE
        if self.fly.mode == 'throttle':
            flags |= M.S_THROTTLE_MODE
        if self.double_next:
            flags |= M.S_DOUBLE
            self.double_next = False
        self.shots += 1
        rpm = sum(self.fly.rpms()) / 2.0
        rec = {'t1': t1, 't2': t2, 'fps': fps, 'flags': flags, 'rpm': rpm}
        self.shot_log.append(rec)
        self.hal.can_send(*M.pack('SHOT', shot=self.shots & 0xFFFF, fps_d=M.sat(fps * 10, 0, 65535),
                                  rpm=M.sat(rpm, 0, 65535), flags=flags))
        if flags & M.S_STRAY and fps:
            self._event(M.EV_STRAY, M.sat(fps * 10, 0, 65535))
        if fps > C.TRIP_FPS:                              # the firmware's own per-shot check (the latch is hardware)
            self.latched |= M.F_OVERSPEED
            self.overspeed_t = t1

    # =================================================================== servos
    def _servos(self, t: float):
        if not (self.pan_ok and self.tilt_ok):
            if t >= self.next_init:
                self.next_init = t + 0.1
                self._init_servos(t)
            return
        if t >= self.next['read']:
            self.next['read'] = t + 1.0 / C.SERVO_READ_HZ
            self._read_pan(t)
            raw = self.master.read_pos(C.ID_TILT)
            if raw is not None:
                tilt = (raw - C.TILT_ZERO_COUNT) * C.DEG_PER_COUNT * C.TILT_SIGN
                if t > self.tilt_read_t:
                    self.tilt_rate = (tilt - self.tilt_deg) / (t - self.tilt_read_t)
                self.tilt_deg, self.tilt_read_t = tilt, t
        if t >= self.next['volt']:
            self.next['volt'] = t + 0.5
            sid = (C.ID_PAN, C.ID_TILT, C.ID_FEED)[self.volt_rr % 3]
            self.volt_rr += 1
            if sid != C.ID_FEED or self.feed.online:
                v = self.master.read_voltage(sid)
                self.volts[sid] = v or 0.0
            else:
                self.volts[sid] = 0.0
        for e in self.feed.update(t):
            self._feed_event(t, e)
        if self.state == 'HOMING':
            self._homing(t)
        elif self.tracker is not None and not self.latched & M.F_SERVO_CONFIG:
            self._pan_control(t)
        if self.state != 'BOOT' and not self.latched & M.F_SERVO_CONFIG:
            self._tilt_control(t)

    def _init_servos(self, t: float):
        for sid, mode in ((C.ID_PAN, C.MODE_STEP), (C.ID_TILT, C.MODE_POSITION)):
            ok = self.pan_ok if sid == C.ID_PAN else self.tilt_ok
            if ok or not self.master.ping(sid):
                continue
            e = self.master.read_eeprom(sid)
            if e is None:
                continue
            good = e['mode'] == mode
            if sid == C.ID_TILT:
                over = int(math.ceil(1.0 / C.DEG_PER_COUNT))          # at most 1 deg above level, into the stop
                if C.TILT_SIGN < 0:
                    good = good and e['min_angle'] >= C.TILT_ZERO_COUNT - over and e['max_angle'] != 0
                else:
                    good = good and 0 < e['max_angle'] <= C.TILT_ZERO_COUNT + over
            if not good:
                self.latched |= M.F_SERVO_CONFIG
                continue
            m = self.master
            speed = int(C.AIM_RATE_CAP / C.DEG_PER_COUNT) if sid == C.ID_TILT else int(hm.HOME_SPEED_DEG_S *
                                                                                          C.PAN_RATIO / C.DEG_PER_COUNT)
            ok = (m.write(sid, sts.R_TORQUE_LIMIT, sts.u16(C.SERVO_TORQUE_LIMIT)) and
                  m.write(sid, sts.R_ACC, bytes([PAN_ACC])) and m.write(sid, sts.R_GOAL_SPEED, sts.u16(speed)))
            if sid == C.ID_TILT:
                raw = m.read_pos(sid)
                ok = ok and raw is not None and m.write(sid, sts.R_GOAL_POS, sts.u16(raw))
            ok = ok and m.write(sid, sts.R_TORQUE_ENABLE, b'\x01')
            if ok and sid == C.ID_PAN:
                self.pan_ok, self.pan_speed_reg = True, speed
            elif ok:
                self.tilt_ok, self.tilt_speed_reg = True, speed
        if self.latched & M.F_SERVO_CONFIG:
            self._enter('FAULT', t)

    def _read_pan(self, t: float):
        b = self.master.read(C.ID_PAN, sts.R_PRESENT_POS, 4)
        raw = None
        if b is not None:
            raw = sts.from_sm(sts.le16(b, 0)) % C.COUNTS
            self.pan_speed_cps = float(sts.from_sm(sts.le16(b, 2)))
            self.pan_read_t = t
        if self.state == 'HOMING' and self.homing is not None:
            self.homing.servo_read(t, raw)
        elif self.tracker is not None:
            was = self.tracker.direction
            self.tracker.read(t, raw)
            if self.tracker.direction > 0 and (was < 0 or self.plus_from is None) and self.tracker.total is not None:
                self.plus_from = self.tracker.total - 3           # the tracker turns after 3 counts
            if raw is not None and self.check is not None:
                was = self.check.rehome
                self.check.after_read(t)
                if self.check.rehome and not was:
                    self.latched |= M.F_REHOME
                    self._event(M.EV_REHOME_ASKED, M.sat(self.check.worst_deg * 100, 0, 65535))

    def _begin_homing(self, t: float):
        self.homing = hm.Homing(calibrated_offset_deg=self.index_offset_deg)
        self.tracker = self.check = None
        self.home_v, self.home_t0 = 0.0, t
        self.pan_move = None
        self._enter('HOMING', t)

    def _homing(self, t: float):
        h = self.homing
        v = h.step(t, abs(self.tilt_deg) <= C.AIM_TOL_DEG)
        resend = v > 0 and t - self.home_sent_t > 0.5 and abs(h.swept_deg) < 0.5   # the sweep's step was lost
        if v != self.home_v or resend:
            if v > 0:
                self._pan_speed(int(v * C.PAN_RATIO / C.DEG_PER_COUNT))
                self.master.write_once(C.ID_PAN, sts.R_GOAL_POS, sts.sm16(HOME_SWEEP_COUNTS))
            else:
                self.master.write_once(C.ID_PAN, sts.R_GOAL_POS, sts.sm16(0))
            self.home_v, self.home_sent_t = v, t
        if h.state not in ('DONE', 'FAILED') and t - self.home_t0 > HOME_TIMEOUT_S:
            h.state, h.result = 'FAILED', 'no index within %.0f s' % HOME_TIMEOUT_S
            self.master.write_once(C.ID_PAN, sts.R_GOAL_POS, sts.sm16(0))
        if h.state == 'DONE':
            self.tracker = h.tracker
            self.check = hm.IndexCheck(self.tracker, calibrated_offset_deg=self.index_offset_deg)
            centre = (self.tracker.index_total + self.index_offset_deg / C.PAN_PER_COUNT) % C.COUNTS
            self._event(M.EV_HOMED, M.sat((t - self.home_t0) * 100, 0, 65535), M.sat(centre * 16, 0, 65535),
                        M.sat(abs(h.swept_deg), 0, 65535))
            self.log.append((t, 'homed', {'time_s': t - self.home_t0, 'centre_counts': centre,
                                          'swept_deg': h.swept_deg}))
            self.pan_goal = self.tracker.pan_deg() or 0.0
            self.pan_move = None
            self.latched &= ~M.F_REHOME
            self._enter('IDLE', t)
        elif h.state == 'FAILED':
            self._event(M.EV_HOME_FAILED, M.sat((t - self.home_t0) * 100, 0, 65535), 0, M.sat(abs(h.swept_deg), 0,
                                                                                               65535))
            self.latched |= M.F_HOME_FAILED
            self._enter('FAULT', t)

    def _pan_speed(self, cps: int):
        cps = max(1, min(C.SERVO_NO_LOAD_CPS, cps))
        if cps != self.pan_speed_reg:
            if self.master.write(C.ID_PAN, sts.R_GOAL_SPEED, sts.u16(cps)):
                self.pan_speed_reg = cps

    def pan_deg(self) -> Optional[float]:
        return self.tracker.pan_deg() if self.tracker is not None else None

    def _pan_control(self, t: float):
        """Moves are relative steps from the unwrapped angle, in the servo frame of the + flank (the turntable sits
        on it after any +pan motion); every move ends in +pan (a goal below the present pan goes 1 deg under first)."""
        tr = self.tracker
        if tr.total is None:
            return
        goal = self.pan_goal
        m = self.pan_move
        if m is None or abs(goal - m['goal']) > 0.02:
            d = goal - tr.pan_deg()
            # a direct move only if it is itself longer than the backlash, or continues on an engaged + flank
            direct = d >= C.ONE_SIDED_DEG or (d >= 0.0 and self.plus_flank())
            m = self.pan_move = {'goal': goal, 'phase': 'final' if direct else 'over', 'sent': False, 'tries': 0}
        if m['phase'] == 'done':
            return
        tgt = goal - C.ONE_SIDED_DEG if m['phase'] == 'over' else goal
        target_total = tr.index_total + tgt / C.PAN_PER_COUNT
        now = tr.total + self.pan_speed_cps * (t - self.pan_read_t)
        if not m['sent'] or (abs(target_total - now) > SEG_COUNTS and abs(m['seg_end'] - now) < SEG_COUNTS / 10):
            # one relative step, or the next segment of a long move before the last one runs out
            self._pan_speed(int(self.rate * C.PAN_RATIO / C.DEG_PER_COUNT))
            rel = int(round(max(-SEG_COUNTS, min(SEG_COUNTS, target_total - now))))
            if abs(rel) > 1:
                self.master.write_once(C.ID_PAN, sts.R_GOAL_POS, sts.sm16(rel))
                self.pan_cmd_t = t
            m.update(sent=True, seg_end=now + rel,
                     t_max=t + abs(rel) * C.PAN_PER_COUNT / max(1.0, self.rate) + 0.6)
            return
        err = target_total - tr.total
        arrived = abs(err) <= 2 and abs(self.pan_speed_cps) < 30
        if arrived or (t > m['t_max'] and abs(target_total - now) <= SEG_COUNTS):
            if m['phase'] == 'over':
                m.update(phase='final', sent=False)
            elif (abs(err) > 2 or not self.plus_flank()) and m['tries'] < 2:   # a correction, one-sided again
                m.update(phase='final' if err > 0 and self.plus_flank() else 'over', sent=False, tries=m['tries'] + 1)
            else:
                m['phase'] = 'done'

    def plus_flank(self) -> bool:
        """The turntable rests on the + flank: the last motion was +pan and longer than the backlash (homing.py's
        tracker turns its direction after 3 counts; the turntable changes flank only after the full backlash)."""
        tr = self.tracker
        return (tr is not None and tr.direction > 0 and self.plus_from is not None and tr.total is not None and
                tr.total - self.plus_from >= tr.backlash_deg / C.PAN_PER_COUNT + 3)

    def _tilt_control(self, t: float):
        if self.state == 'HOMING':
            want = 0.0
        elif self.stray_tilt:
            want = C.STRAY_TILT_DEG
        elif self.lift:
            want = 0.0
        else:
            want = self.tilt_goal
        pan = self.pan_deg() or 0.0
        want = min(C.TILT_MAX_DEG, max(C.TILT_MIN_DEG, self.cfg.min_tilt(pan), want))   # never above level
        if self.tilt_cmd is None or abs(want - self.tilt_cmd) > 0.05 or t - self.tilt_written_t > 1.0:
            spd = int(min(C.AIM_RATE_CAP, self.rate if self.state != 'HOMING' else C.AIM_RATE_CAP) / C.DEG_PER_COUNT)
            if spd != self.tilt_speed_reg and self.master.write(C.ID_TILT, sts.R_GOAL_SPEED, sts.u16(spd)):
                self.tilt_speed_reg = spd
            counts = int(round(C.TILT_ZERO_COUNT + C.TILT_SIGN * want / C.DEG_PER_COUNT))
            if self.master.write(C.ID_TILT, sts.R_GOAL_POS, sts.u16(counts)):
                self.tilt_cmd, self.tilt_written_t = want, t

    def aim_settled(self, t: float) -> bool:
        if self.tracker is None or self.pan_move is None or self.pan_move['phase'] != 'done':
            return False
        pan = self.tracker.pan_deg()
        rate = abs(self.pan_speed_cps) * C.PAN_PER_COUNT
        return (rate < C.SETTLE_RATE and t - self.pan_cmd_t >= C.SETTLE_S and abs(pan - self.pan_goal) <= C.AIM_TOL_DEG
                and self.tilt_cmd is not None and abs(self.tilt_deg - self.tilt_cmd) <= C.AIM_TOL_DEG)

    # =================================================================== feed events
    def _feed_event(self, t: float, e: tuple):
        k = e[0]
        if k == 'settled':
            _, n, settle, peak, lm, clean = e
            self._event(M.EV_FEED_STEP, n & 0xFFFF, M.sat(settle * 1000, 0, 65535),
                        (M.sat(lm, 0, 32767)) | (0 if clean else 0x8000))
        elif k == 'jam':
            self.jams += 1
            self._event(M.EV_FEED_JAM, e[1] & 0xFFFF, M.sat(e[4] * 1000, 0, 65535),
                        (1 if e[2] == 'timeout' else 2) | (e[3] << 4))
        elif k == 'fault':
            self._event(M.EV_FEED_FAULT, 1 if e[1] == 'jams' else 2)
        elif k == 'online':
            self._event(M.EV_SERVO_BACK, C.ID_FEED, self.feed.stats['reinit'])
        elif k == 'lost':
            self._event(M.EV_SERVO_LOST, C.ID_FEED)

    # =================================================================== safety and states
    def armed_ok(self, t: float) -> int:
        """The conditions for spinning or feeding, as missing-cause bits (0 = all present)."""
        c = 0
        if not self.arm:
            c |= M.F_ARM_LOW
        if t - self.hb_t > C.HEARTBEAT_MAX_AGE_S:
            c |= M.F_HEARTBEAT
        if self.arm and not self.pulse.ok:
            c |= M.F_PULSE
        if self.trip:
            c |= M.F_TRIP
        if self.fly.guard.tripped:
            self.latched |= M.F_ERPM_LIMIT
        if self.fly.telemetry_lost(t):
            c |= M.F_TELEMETRY
        return c | (self.latched & LATCHING)

    def _safety(self, t: float):
        self.causes = self.armed_ok(t)
        if self.state in ARMED_STATES:
            if self.causes:
                self._safe(t, self.causes)
            elif not self.host_arm:
                self._disarm(t)

    def _safe(self, t: float, causes: int):
        self.fly.stop(t)
        self.feed.abort(t)
        self._end_burst(t, 'aborted')
        self.fire_req = self.spin = None
        if self.bench is not None:
            self._bench_done(t)
        self.stray_tilt = self.lift = False
        self.rearm_wait = True
        lat, val = 0.0, 0
        if causes & M.F_ERPM_LIMIT and self.fly.guard.first_over_t is not None:
            lat, val = t - self.fly.guard.first_over_t, self.fly.guard.trip_erpm / 10.0
        elif causes & M.F_ARM_LOW and self.arm_fall_t is not None:
            lat = t - self.arm_fall_t
        elif causes & M.F_TRIP and self.trip_t is not None:
            lat = t - self.trip_t
        elif causes & M.F_HEARTBEAT:
            lat = t - (self.hb_t + C.HEARTBEAT_MAX_AGE_S)
        elif causes & M.F_OVERSPEED and self.overspeed_t is not None:
            lat = t - self.overspeed_t
        self._event(M.EV_SAFE, causes, M.sat(lat * 1000, 0, 65535), M.sat(val, 0, 65535))
        self.log.append((t, 'safe', {'causes': causes, 'latency_s': lat, 'value': val}))
        self._enter('SAFE', t)

    def _disarm(self, t: float):
        self.fly.stop(t)
        self._end_burst(t, 'aborted')
        self.fire_req = self.spin = self.bench = None
        self.stray_tilt = self.lift = False
        if self.feed.state == MOVING:
            self.feed.abort(t)
        self._enter('IDLE', t)

    def _enter(self, s: str, t: float):
        if s != self.state:
            self.log.append((t, 'state', s))
        self.state, self.state_t = s, t

    def _end_burst(self, t: float, why: str):
        if self.burst is not None:
            b = self.burst
            self.balls_fired += b.balls
            self.empties += b.empty
            self._event(M.EV_BURST_DONE, b.balls, b.steps, M.BURST_END.get(b.done or why, 4))
            self.log.append((t, 'burst', dict(b.summary(), done=b.done or why)))
            self.burst = None
        self.lift = False

    def _bench_done(self, t: float):
        if self.bench is not None:
            self._event(M.EV_BENCH_DONE, self.bench['code'])
            self.bench = None

    def _spin_up(self, t: float, rpm: Optional[float] = None, throttle: Optional[float] = None):
        self.spin = {'rpm': rpm, 'throttle': throttle, 'phase': 'depress', 't': t}
        self._enter('SPIN_UP', t)

    def _run(self, t: float):
        s = self.state
        if s == 'BOOT':
            if self.pan_ok and self.tilt_ok:
                self._begin_homing(t)
        elif s == 'FAULT':
            if not self.latched & (M.F_HOME_FAILED | M.F_SERVO_CONFIG | M.F_CONFIG_MISMATCH | M.F_ERPM_LIMIT |
                                   M.F_OVERSPEED) and not self.trip:
                self._enter('IDLE', t)
        elif s == 'SAFE':
            if t - self.state_t >= 0.2 and self.fly.stopped(t) or t - self.state_t >= 2.0:
                bad = self.latched & (M.F_HOME_FAILED | M.F_SERVO_CONFIG | M.F_CONFIG_MISMATCH | M.F_ERPM_LIMIT |
                                      M.F_OVERSPEED)
                self._enter('FAULT' if bad or self.trip else 'IDLE', t)
        elif s == 'IDLE':
            if (self.tracker is not None and self.host_arm and not self.rearm_wait and not self.causes):
                self._enter('ARMED', t)
        elif s == 'ARMED':
            if self.bench is not None and self.bench['kind'] == 'feed_steps':
                b = self.bench                                  # the dial alone at a rate (test 3.9)
                done = self.feed.stats['settled'] - b['base']
                if self.feed.state == FEED_FAULT or (done >= b['n'] and self.feed.state == PARKED):
                    self._bench_done(t)
                elif self.feed.state == PARKED and t >= b['next'] and b['issued'] < b['n']:
                    if self.feed.request_step(t):
                        b['issued'] += 1
                        b['next'] = t + b['period']
        elif s == 'SPIN_UP':
            sp = self.spin
            if sp['phase'] == 'depress':
                self.stray_tilt = True
                low = max(C.TILT_MIN_DEG, self.cfg.min_tilt(self.pan_deg() or 0.0))
                if (abs(self.tilt_deg - low) <= 1.0 or t - sp['t'] > 0.6) and self.fly.esc_armed():
                    ok = self.fly.spin_speed(t, sp['rpm']) if sp['rpm'] else self.fly.spin_throttle(t, sp['throttle'])
                    if ok:
                        sp['phase'], sp['t'] = 'ramp', t
                        self.stray_until = t + C.STRAY_WINDOW_S
            elif sp['phase'] == 'ramp':
                if t >= self.stray_until:
                    self.stray_tilt = False
                    sp['phase'] = 'wait'
            elif self.fly.ready(t):
                self.ready_idle_t = t
                self._enter('READY', t)
        elif s == 'READY':
            if self.fire_req is not None:
                fr = self.fire_req
                self.burst = Burst(fr['balls'], fr['rate'], t)
                self.fire_req = None
                self._enter('FIRING', t)
            elif self.bench is not None and self.bench['kind'] == 'spin':
                if t - self.state_t >= self.bench['hold']:
                    self.fly.stop(t)
                    self.spin = None
                    self._bench_done(t)
                    self._enter('ARMED', t)
            elif t - self.ready_idle_t >= C.SPIN_HOLD_S:
                self.fly.stop(t)
                self.spin = None
                self._enter('ARMED', t)
        elif s == 'FIRING':
            b = self.burst
            pan = self.pan_deg() or 0.0
            any_aim = self.bench is not None and self.bench['kind'] == 'fire_any_aim'
            can = (self.fly.prefeed_ok(t)[0] and (any_aim or self.aim_settled(t)) and not self.cfg.in_keepout(pan)
                   and not self.lift)
            if not can and self.cfg.in_keepout(pan):              # held in a keep-out sector for 3 s: end the burst
                self.keepout_t = t if self.keepout_t is None else self.keepout_t
                if t - self.keepout_t > 3.0:
                    b.done = 'aborted'
            else:
                self.keepout_t = None
            act = b.update(t, self.feed, can, self.tilt_deg)
            self.lift = act == 'lift'
            for be in b.events:
                if be[0] == 'empty':                    # an empty step: no ball after two dithers
                    self._event(M.EV_FEED_EMPTY, b.empty & 0xFFFF, b.steps & 0xFFFF)
                elif be[0] == 'dither':
                    self._event(M.EV_DITHER, be[1], b.steps & 0xFFFF)
                elif be[0] == 'lift':
                    self._event(M.EV_LIFT, b.lifts)
            b.events.clear()
            if b.done:
                self._end_burst(t, b.done)
                if self.bench is not None and self.bench['kind'] in ('fire_throttle', 'fire_any_aim'):
                    self.fly.stop(t)
                    self.spin = None
                    self._bench_done(t)
                    self._enter('ARMED', t)
                else:
                    self.ready_idle_t = t
                    self._enter('READY', t)

    # =================================================================== telemetry
    def _event(self, code: int, a: int = 0, b: int = 0, c: int = 0):
        self.ev_seq = (self.ev_seq + 1) & 0xFF
        self.hal.can_send(*M.pack('EVENT', code=code, seq=self.ev_seq, a=a & 0xFFFF, b=b & 0xFFFF, c=c & 0xFFFF))

    def faults(self) -> int:
        f = self.causes | self.latched
        if self.feed.state == FEED_FAULT:
            f |= M.F_FEED_JAM
        if self.arm and self.feed.state == OFFLINE and self.arm_rise_t is not None and self.t - self.arm_rise_t > 1.0:
            f |= M.F_FEED_MISSING
        if not self.pan_ok:
            f |= M.F_PAN_MISSING
        if not self.tilt_ok:
            f |= M.F_TILT_MISSING
        return f & 0xFFFF

    def _telemetry(self, t: float):
        n = self.next
        if t >= n['hb']:
            n['hb'] = t + 0.1
            fl = ((M.H_ARM if self.arm else 0) | (M.H_TRIP if self.trip else 0) |
                  (M.H_HOMED if self.tracker is not None else 0) | (M.H_PULSE_OK if self.pulse.ok else 0) |
                  (M.H_HOST_ARMED if self.state in ARMED_STATES else 0) | (M.H_REARM_WAIT if self.rearm_wait else 0) |
                  (M.H_FEED_ONLINE if self.feed.online else 0) | (M.H_WHEELS_READY if self.fly.ready(t) else 0))
            self.seq = (self.seq + 1) & 0xFF
            self.hal.can_send(*M.pack('TURRET_HEARTBEAT', state=M.STATES.index(self.state), faults=self.faults(),
                                      flags=fl, seq=self.seq))
        period = self.stream_period if t < self.stream_until else 0.02
        if t >= n['pose'] - 1e-9:
            n['pose'] = t + period
            pan = self.pan_deg()
            rate = self.pan_speed_cps * C.PAN_PER_COUNT
            self.hal.can_send(*M.pack('POSE', pan_cdeg=M.sat((pan or 0.0) * 100, -2**31, 2**31 - 1),
                                      tilt_cdeg=M.sat(self.tilt_deg * 100, -32768, 32767),
                                      pan_rate=M.sat(rate, -127, 127), tilt_rate=M.sat(self.tilt_rate, -127, 127)))
        if t >= n['wheels']:
            n['wheels'] = t + 0.05
            l, r = self.fly.w
            self.hal.can_send(*M.pack('WHEELS', rpm_l=M.sat(l.rpm, 0, 65535), rpm_r=M.sat(r.rpm, 0, 65535),
                                      temp_l=M.sat(l.temp_c or 0, 0, 255), temp_r=M.sat(r.temp_c or 0, 0, 255)))
        if t >= n['feed']:
            n['feed'] = t + 0.2
            b = self.burst
            fl = ((M.FD_FAULT if self.feed.state == FEED_FAULT else 0) | (M.FD_ONLINE if self.feed.online else 0))
            d = self.feed.dial_deg()
            self.hal.can_send(*M.pack('FEED', balls=(self.balls_fired + (b.balls if b else 0)) & 0xFFFF,
                                      empty=(self.empties + (b.empty if b else 0)) & 0xFF, jams=self.jams & 0xFF,
                                      flags=fl, dial=0 if d is None else int(d / 360.0 * 256) & 0xFF))
        if t >= n['power']:
            n['power'] = t + 0.2
            self.hal.can_send(*M.pack('POWER', bus_mv=M.sat(self.hal.bus_mv(), 0, 65535),
                                      pan_dv=M.sat(self.volts[C.ID_PAN] * 10, 0, 255),
                                      tilt_dv=M.sat(self.volts[C.ID_TILT] * 10, 0, 255),
                                      feed_dv=M.sat(self.volts[C.ID_FEED] * 10, 0, 255)))
        if t >= n['health']:
            n['health'] = t + 1.0
            tec, rec, boff = self.hal.can_counters()
            worst = self.check.worst_deg if self.check is not None else 0.0
            self.hal.can_send(*M.pack('HEALTH', tec=tec & 0xFF, rec=rec & 0xFF, busoff=boff & 0xFF,
                                      ring_drops=min(65535, self.pulse.drops),
                                      servo_err=min(65535, self.master.retried + self.master.failed),
                                      index_worst=M.sat(worst * 100, 0, 255)))
