"""A simulated turret for the firmware reference and `bench_host.py --sim`. Not firmware; kept simple and stated.

Each model, and where its numbers come from:
  safety line  the base 555 at 1 kHz (+-1 %) while the pendant is held; at the turret the 4N35 and the CD74HC423E
               retriggerable monostable (18 ms +-10 %): ARM = pulses AND /TRIP, as drawn (docs/turret-wiring.md 3.1).
               Ring faults replace the train: open, short to GND (no edges), short to +24 V or a DC level (one edge,
               then none), 300 Hz, 3 kHz and 50 Hz hum (edges at that rate)
  trip latch   gate 1 starts a one-shot of 2.98 ms (+-1 % after the R is selected on the bench); gate 2 inside it sets
               the latch; only the reset button clears it (wiring 3.2)
  2815, brake  12 V FLY and 12 V FEED follow ARM within the millisecond; BRAKE = ARM inverted through 6.8 k / 1 uF (a diode for the fast release)
               between 74HC14s: on 9.2 ms after ARM falls, off 10.8 ms after it rises (the drawn RC is symmetric)
  pan          test_homing.Hardware (the 63:21 drive, 0.44 deg backlash, the hall window with hysteresis and
               interrupt jitter) moved at the speed of the pan servo's own acceleration-limited loop (sim_servo.py),
               step mode; reads go through the ring: 2e-4 of the pan's replies are corrupted
  tilt         a position-mode servo with its angle limits, between hard stops at 0 and -25 deg
  feed         a step-mode servo on the switched 12 V FEED rail (it leaves the bus on every release); the dial: a
               pocket reaching the exit hole drops a ball with p_fill (0.85 level: the rerun's ~1 empty in 8), a
               dither's return refills it with p_dither (0.8, a stand-in), below -12 deg with <= 5 balls the balls pool
               (0.1) until the barrel is lifted, and below -12 deg 1 ball in 32 hangs in the hole and comes down with
               the next dial motion (the rerun's double at -25 deg, freed alone by a dither); a step jams with
               p_jam (0.003) 10-35 deg in, and a 20 deg reverse clears it with p 0.9
  wheels       per wheel an AM32 ESC: arms after 0.5 s of zero throttle, answers every DShot frame with eRPM (and
               EDT temperatures), drives rpm toward throttle x KV (1400 +-3 %) x rail x 0.993, the rail trimmed at the
               bench so the faster motor's no-load is at or under 15,930 rpm (one resistor step, 0-1 % under; 20.5 V
               for test 4.6: the converter bypassed), tau 15 ms, accel capped by the 10 A limit on 7.6e-6 kg m^2 (the
               D68 launch run); brake on stop (the low-side FETs on) tau 8 ms; unpowered it coasts (tau 2 s) until the
               phase short (tau 23 ms effective); a ball takes 6 % of each wheel's speed
  balls        from the pocket reaching the hole to the nip in 105 +- 12 ms (+10 ms at -25 deg: the feed rerun's
               300-330 ms from the step's command to first touch); launched at the D68 launch run's speed for the
               Hasbro ball: 95 fps at 15,269 rpm on Ø38, 98.4 at the trimmed no-load 15,930 (linear between in rpm,
               the ratio falling 0.7 %), +- 2 %; below 1,400 rpm it rests at the nip and leaves at 2.9 fps when the
               wheels pass it (the stray ball); gate 1 30 mm past the nip, gate 2 60 mm on, +-30 us edge jitter; the
               reference chronograph 1 m out reads 0.4 fps less +- 0.2
  stand-ins    ring resistance, CAN error frames, temperatures, paper groups, plates: plausible numbers for the
               dry run, marked 'sim stand-in' in every result
"""
from __future__ import annotations

import math
import random
from collections import deque
from typing import Dict, List, Optional, Tuple

import config as C
import dshot
import test_homing as th
from sim_servo import SimServo
from turret_fw import HAL

DT = 0.001


FALL = 1.0 - (C.FULL_THROTTLE_FPS / C.SET_FPS_DESIGN) / (C.NO_LOAD_RPM_TRIM / C.SET_RPM_DESIGN)   # 0.7 %


def launch_fps(rpm: float) -> float:
    """The D68 launch run's Hasbro ball on Ø38: 95 fps at 15,269 rpm, 98.4 at the trimmed no-load 15,930 (a stand-in
    between and beyond)."""
    r = rpm / C.SET_RPM_DESIGN
    fall = FALL * max(0.0, (rpm - C.SET_RPM_DESIGN) / (C.NO_LOAD_RPM_TRIM - C.SET_RPM_DESIGN))
    return C.SET_FPS_DESIGN * r * (1.0 - fall)


class SimTurret(HAL):
    def __init__(self, seed: int = 1, **opt):
        self.rng = random.Random(seed)
        r = self.rng
        self.t = 0.0
        self.opt = opt
        # -------------------------------------------------- the safety line
        self.pendant = False
        self.ring_fault: Optional[str] = None
        self.fault_t = 0.0
        self.f555 = 1000.0 * (1 + r.uniform(-0.01, 0.01))
        self.next_555: Optional[float] = None          # the next edge of whatever drives the opto (None: nothing)
        self.mono_t = 0.018 * (1 + r.uniform(-0.10, 0.10))       # 0.45 x 39 k x 1 uF (X7R, 10 %): 16-20 ms
        self.mono_until = -1.0
        self.src: Optional[float] = None
        self.last_edge: Optional[float] = None
        self.edges: List[float] = []
        self.trip_window = 0.060 / (C.TRIP_FPS * C.FPS) * (1 + r.uniform(-0.01, 0.01))
        self.trip_q = False
        self.one_shot_until = -1.0
        self.arm = False
        self.rail = False
        self.brake = False
        self.timeline: List[Tuple[float, str]] = []   # ('arm_on', 'arm_off', 'rail_on', 'rail_off', 'brake_on', ...)
        self.release_t: Optional[float] = None
        self._arm_change = 0.0
        # -------------------------------------------------- the pan
        hr = random.Random(seed * 7 + 1)
        self.pan_hw = th.Hardware(hr)
        self.index_offset = self.pan_hw.h / 2 + hr.uniform(-0.3, 0.3)     # the assembly calibration
        self.pan_servo = SimServo(C.ID_PAN, mode=C.MODE_STEP, rng=random.Random(seed * 7 + 2), p_corrupt=2e-4)
        self.pan_servo.read_noise = 1.0
        self._sync_pan()
        self.pan_servo.goal = self.pan_servo.pos
        self.hall_ev: List[Tuple[float, bool]] = []
        self.pan_true_log: List[Tuple[float, float]] = []
        # -------------------------------------------------- the tilt
        z = C.TILT_ZERO_COUNT
        span = int(round(25.0 / C.DEG_PER_COUNT))
        lo, hi = (z - 5, z + span + 5) if C.TILT_SIGN < 0 else (z - span - 5, z + 5)
        self.tilt_servo = SimServo(C.ID_TILT, mode=C.MODE_POSITION, pos=z, min_angle=lo, max_angle=hi,
                                   rng=random.Random(seed * 7 + 3))
        stop0, stop25 = z, z + C.TILT_SIGN * (-25.0) / C.DEG_PER_COUNT
        self.tilt_servo.blocked_lo, self.tilt_servo.blocked_hi = min(stop0, stop25), max(stop0, stop25)
        self.tilt_max_seen = -99.0
        # -------------------------------------------------- the feed and the dial
        self.feed_servo = SimServo(C.ID_FEED, mode=C.MODE_STEP, rng=random.Random(seed * 7 + 4),
                                   pos=r.randrange(C.FEED_POCKETS) * C.FEED_STEP_COUNTS + r.uniform(-8, 8))
        self.feed_servo.load_factor, self.feed_servo.extra_load = 0.95, 60
        self.feed_servo.set_power(False, 0.0)
        self.feed_bench_power = False
        self.feed_unplugged = False
        self.hopper = opt.get('hopper', 30)
        self.p_fill = opt.get('p_fill', 0.85)
        self.p_dither = opt.get('p_dither', 0.8)        # stand-in: test 5.1 measures what the dither recovers
        self.p_jam = opt.get('p_jam', 0.003)
        self.p_double = opt.get('p_double', 0.0)
        self.p_hang = opt.get('p_hang', 1.0 / 32.0)        # below -12 deg
        self.hung = False
        self.p_clear = 0.9
        self.force_jam_next = False
        self.jam: Optional[dict] = None
        self.last_arrival: Optional[int] = None
        self.unpooled = 0
        self.lifted_at = -10.0
        self._feed_goal = self.feed_servo.goal
        self.dial_log: Dict[str, int] = {'arrivals': 0, 'drops': 0, 'doubles': 0, 'jams': 0, 'cleared': 0}
        # -------------------------------------------------- the wheels
        self.kv = [C.MOTOR_KV * (1 + r.uniform(-0.03, 0.03)) for _ in range(2)]
        self.k_nl = [C.K_NL * (1 + r.uniform(-0.02, 0.01)) for _ in range(2)]
        # the bench's trim (test 4.1): one fixed resistor, the step under the target, for the faster motor
        self.rail_v = opt.get('rail_v', C.NO_LOAD_RPM_TRIM / max(k * n for k, n in zip(self.kv, self.k_nl)) * r.uniform(0.99, 1.0))
        self.esc = [{'on_t': None, 'armed': False, 'zero_since': None, 'thr': 0.0, 'edt': False, 'n': 0}
                    for _ in range(2)]
        self.rpm = [0.0, 0.0]
        self.temp = {'esc': [24.0, 24.0], 'motor': [24.0, 24.0], 'reg': 24.0, 'pan': 26.0, 'tilt': 26.0,
                     'feed': 26.0}
        self.esc_frames_out: List[Tuple[int, float, int]] = []
        self.esc_unplugged = False                     # CT unplugged (the 5.3 tests: a lamp on 12 V FLY instead)
        self.rpm_log: deque = deque(maxlen=30000)      # (t, mean rpm), for the release test's +50 ms reading
        self.i24_log: deque = deque(maxlen=60000)
        self.i24_peak = 0.0
        self.bus_min = 24.0
        # -------------------------------------------------- balls and gates
        self.balls: List[dict] = []
        self.gate_ev: List[Tuple[float, int]] = []
        self.launched: List[dict] = []
        self.tyre_mm = opt.get('tyre_mm', C.TYRE_DESIGN_MM)
        # -------------------------------------------------- CAN
        self.to_fw: deque = deque()
        self.to_host: deque = deque()
        self.can_frames = 0
        self.laser_on = False
        self.servos = {C.ID_PAN: self.pan_servo, C.ID_TILT: self.tilt_servo, C.ID_FEED: self.feed_servo}
        self.bus_txn = 0

    # =================================================================== the HAL
    def arm_in(self) -> bool:
        return self.arm

    def trip_in(self) -> bool:
        return self.trip_q

    def pulse_edges(self) -> List[float]:
        e, self.edges = self.edges, []
        return e

    def hall_edges(self):
        e, self.hall_ev = self.hall_ev, []
        return e

    def gate_edges(self):
        e = sorted(self.gate_ev)
        self.gate_ev = []
        return e

    def esc_frames(self):
        e, self.esc_frames_out = self.esc_frames_out, []
        return e

    def dshot(self, frames):
        for k, f in enumerate(frames):
            if f is not None:                                # None: no frame, the pin held low (ESCs unpowered)
                self._esc_frame(k, f)

    def servo_txn(self, pkt: bytes):
        self.bus_txn += 1
        sid = pkt[2] if len(pkt) > 2 else None
        s = self.servos.get(sid)
        if s is None or (sid == C.ID_FEED and self.feed_unplugged):
            return None
        return s.handle(pkt, self.t)

    def can_recv(self):
        out = []
        while self.to_fw:
            out.append(self.to_fw.popleft())
        return out

    def can_send(self, cid: int, data: bytes):
        self.can_frames += 1
        self.to_host.append((self.t, cid, bytes(data)))

    def laser(self, on: bool):
        self.laser_on = on

    def bus_mv(self) -> int:
        return int(self.bus_now * 1000)

    @property
    def bus_now(self) -> float:
        return 24.0 - 0.06 * (self.i24_log[-1][1] if self.i24_log else 0.3)

    # =================================================================== the operator's and the instruments' side
    def set_pendant(self, held: bool):
        if self.pendant and not held:
            self.release_t = self.t
        self.pendant = held

    def set_ring_fault(self, kind: Optional[str]):
        self.ring_fault, self.fault_t = kind, self.t
        if kind is not None:
            self.release_t = self.t
            if kind in ('24v', 'dc'):
                self._edge(self.t)

    def reset_trip(self):
        self.trip_q = False

    def gate_pair(self, interval_s: float, at: Optional[float] = None):
        t1 = (at or self.t) + 0.0005
        self._gate(t1, 1)
        self._gate(t1 + interval_s, 2)

    def place_pan(self, pan_deg: float):
        """Power-up at a pan (the turntable turned by hand while off)."""
        hw = self.pan_hw
        hw.table = pan_deg
        hw.servo = pan_deg * th.hm.RATIO
        hw.v = 0.0
        hw.hall = abs(hw._d()) <= hw.w_on
        self._sync_pan()
        self.pan_servo.goal = self.pan_servo.pos

    def power_cycle(self):
        for s in self.servos.values():
            s.set_power(False, self.t)
        self.pan_servo.set_power(True, self.t)
        self.tilt_servo.set_power(True, self.t)
        for e in self.esc:
            e.update(on_t=None, armed=False, zero_since=None, thr=0.0, edt=False)

    def true_pan(self) -> float:
        return self.pan_hw.table

    def true_tilt(self) -> float:
        return (self.tilt_servo.pos - C.TILT_ZERO_COUNT) * C.DEG_PER_COUNT * C.TILT_SIGN

    # =================================================================== the step
    def step(self):
        t = self.t + DT
        self.t = t
        self._safety(t)
        self._pan(t)
        self._tilt()
        self._feed(t)
        self._wheels(t)
        self._balls(t)
        self._thermal()

    # ------------------------------------------------------------------- safety line
    def _edge(self, te: float):
        self.edges.append(te)
        self.last_edge = te
        self.mono_until = max(self.mono_until, te + self.mono_t)

    def _safety(self, t: float):
        f = self.ring_fault
        per = None
        if f is None and self.pendant:
            per = 1.0 / self.f555                       # the 555 runs while the loop powers it
        elif f in ('f300', 'f3k', 'hum50'):
            per = {'f300': 1 / 300.0, 'f3k': 1 / 3000.0, 'hum50': 1 / 50.0}[f]
        if per is None:
            self.next_555, self.src = None, None
        else:
            if self.next_555 is None or self.src != per:  # a source starts: its first edge within about a period
                self.next_555, self.src = t - DT + self.rng.uniform(0.5, 1.5) * min(per, 0.001), per
            while self.next_555 <= t:
                self._edge(self.next_555)
                self.next_555 += per
        q = t < self.mono_until
        arm = q and not self.trip_q
        if arm != self.arm:
            self.timeline.append((t, 'arm_on' if arm else 'arm_off'))
            self._arm_change = t
        self.arm = arm
        rail = arm
        if rail != self.rail:
            self.timeline.append((t, 'rail_on' if rail else 'rail_off'))
            self.rail = rail
            self.feed_servo.set_power(rail or self.feed_bench_power, t)
            for k, e in enumerate(self.esc):
                if rail:
                    e.update(on_t=t, armed=False, zero_since=None)
                else:
                    e.update(on_t=None, armed=False, zero_since=None, edt=False)
        # the brake's RC (docs/turret-wiring.md 3.3): high ~8 ms after ARM falls (5-14 ms over the parts), low ~1 ms
        # after it rises (D3 and 1 k fill the capacitor: 0.6-1.4 ms)
        want = not arm
        lag = 0.0080 if want else 0.0010
        if want != self.brake and t - self._arm_change >= lag:
            self.brake = want
            self.timeline.append((t, 'brake_on' if want else 'brake_off'))

    def _gate(self, te: float, g: int):
        self.gate_ev.append((te, g))
        if g == 1:
            self.one_shot_until = te + self.trip_window
        elif g == 2 and te < self.one_shot_until:
            self.trip_q = True
            self.timeline.append((te, 'trip'))

    # ------------------------------------------------------------------- pan, tilt
    def _sync_pan(self):
        hw = self.pan_hw
        self.pan_servo.pos = (hw.servo - hw.servo_zero * th.hm.RATIO) * C.COUNTS / 360.0

    def _pan(self, t: float):
        """The servo's own loop (acceleration-limited) sets the drive's speed; test_homing.Hardware carries it through
        the backlash to the turntable and the hall. Its 60 ms first-order lag (a speed-command model) is bypassed: the
        command is chosen so its lag lands exactly on the servo's speed."""
        s = self.pan_servo
        hw = self.pan_hw
        self._sync_pan()
        v_pan = s.control(DT) * 360.0 / C.COUNTS / th.hm.RATIO
        ev = []
        hw.move(t, hw.v + (v_pan - hw.v) * 0.06 / DT, ev)
        self._sync_pan()
        s.vel_meas = self.pan_hw.v * th.hm.RATIO * C.COUNTS / 360.0
        for te, rising, _d in ev:
            self.hall_ev.append((te, rising))

    def _tilt(self):
        self.tilt_servo.advance(DT)
        tilt = self.true_tilt()
        self.tilt_max_seen = max(self.tilt_max_seen, tilt)
        if tilt > -1.0:
            self.lifted_at = self.t                     # the barrel near level: pooled balls roll back onto the dial

    # ------------------------------------------------------------------- the dial
    def _feed(self, t: float):
        s = self.feed_servo
        if s.goal - self._feed_goal >= 400 and self.jam is None:          # a forward step began
            if self.force_jam_next or self.rng.random() < self.p_jam:
                self.force_jam_next = False
                at = s.pos + self.rng.uniform(10.0, 35.0) / C.DEG_PER_COUNT
                self.jam = {'at': at, 'clear_below': at - 10.0 / C.DEG_PER_COUNT}
                s.blocked_hi = at
                self.dial_log['jams'] += 1
        self._feed_goal = s.goal
        before = s.pos
        s.advance(DT)
        if self.jam is not None and not self.jam.get('hit') and s.pos >= self.jam['at'] - 1.0:
            self.jam['hit'] = True                      # the dial has met it
        if self.jam is not None and self.jam.get('hit') and s.pos < self.jam['clear_below']:
            if self.rng.random() < self.p_clear:
                s.blocked_hi, self.jam = None, None
                self.dial_log['cleared'] += 1
            else:
                self.jam['clear_below'] -= 5.0 / C.DEG_PER_COUNT
        # a pocket arrives over the hole when its centre comes within 64 counts going forward
        z = C.FEED_ZERO_COUNT
        k0 = math.floor((before - z + 64) / C.FEED_STEP_COUNTS)
        k1 = math.floor((s.pos - z + 64) / C.FEED_STEP_COUNTS)
        if k1 > k0:
            self._arrival(t, k1)

    def _arrival(self, t: float, k: int):
        self.dial_log['arrivals'] += 1
        tilt = self.true_tilt()
        pooled = tilt < C.LIFT_BELOW_DEG and self.hopper <= 5 and t - self.lifted_at > 1.5
        redo = k == self.last_arrival
        self.last_arrival = k
        p = 0.1 if pooled else (self.p_dither if redo else self.p_fill)
        extra = 1 if self.hung else 0                   # a ball that hung in the hole comes down with this motion
        self.hung = False
        n = 1 if (self.hopper > 0 and not (extra and redo) and self.rng.random() < p) else 0   # a dither's return frees
        if n and self.hopper >= 2 and self.rng.random() < self.p_double:                      # the hung ball alone
            n = 2
        if n and not extra and tilt < C.LIFT_BELOW_DEG and self.rng.random() < self.p_hang:
            self.hung, n = True, 0                      # it hangs: this step looks empty, the next drops two
            self.hopper -= 1
        for j in range(n + extra):
            if j < n:
                self.hopper -= 1
            drop = self.rng.gauss(0.105, 0.012) + (0.010 if tilt < -12 else 0.0) + j * 0.004
            self.balls.append({'t_nip': t + drop, 'state': 'falling'})
        self.dial_log['drops'] += n + extra
        self.dial_log['doubles'] += max(0, n + extra - 1)

    # ------------------------------------------------------------------- the ESCs and wheels
    def _esc_frame(self, k: int, f: int):
        e = self.esc[k]
        if self.esc_unplugged or e['on_t'] is None or self.t - e['on_t'] < 0.05:
            return
        d = dshot.unframe(f)
        if d is None:
            return
        value, tel = d
        if value == 0:
            e['thr'] = 0.0
            e['zero_since'] = self.t if e['zero_since'] is None else e['zero_since']
            if not e['armed'] and self.t - e['zero_since'] >= 0.5:
                e['armed'] = True
        elif value < dshot.THROTTLE_MIN:
            if value == dshot.CMD_EDT_ENABLE and tel:
                e['edt'] = True
        else:
            e['zero_since'] = None
            e['thr'] = dshot.value_throttle(value) if e['armed'] else 0.0
        e['n'] += 1
        if e['edt'] and e['n'] % 100 == 0:
            word = dshot.encode_edt('temp_c', int(self.temp['esc'][k]))
        else:
            word = dshot.encode_erpm(self.rpm[k] * C.POLE_PAIRS)
        self.esc_frames_out.append((k, self.t, word))

    def _wheels(self, t: float):
        j = 7.6e-6                                     # rotor + hub + tyre, kg m^2 (the D68 launch run, Ø38)
        a_max = 10.0 * 60.0 / (2 * math.pi * C.MOTOR_KV) / j * 60.0 / (2 * math.pi)   # rpm/s at the 10 A limit
        p_tot = 0.0
        for k, e in enumerate(self.esc):
            w = self.rpm[k]
            if e['on_t'] is not None and e['armed']:
                if e['thr'] > 0:
                    target = e['thr'] * self.kv[k] * self.rail_v * self.k_nl[k]
                    dw = max(-a_max, min(a_max, (target - w) / 0.015)) * DT
                else:
                    dw = -w / 0.008 * DT                # AM32 brake on stop: the low-side FETs short the phases
            elif self.brake:
                dw = -w / C.BRAKE_TAU_S * DT            # the hardware phase short
            else:
                dw = -w / 2.0 * DT                      # coasting
            self.rpm[k] = max(0.0, w + dw)
            om, al = self.rpm[k] * 2 * math.pi / 60, dw / DT * 2 * math.pi / 60
            if e['on_t'] is not None and e['armed']:
                p_tot += max(0.0, j * om * al) / 0.85 + 2.0 * e['thr']     # ESC 85 %, ~2 W of losses at speed
        self.rpm_log.append((t, (self.rpm[0] + self.rpm[1]) / 2.0))
        i24 = 0.25 + p_tot / (24.0 * 0.9)                                 # logic and servos idle; regulator 90 %
        self.i24_log.append((t, i24))
        self.i24_peak = max(self.i24_peak, i24)
        self.bus_min = min(self.bus_min, self.bus_now)

    # ------------------------------------------------------------------- balls
    def _balls(self, t: float):
        for b in self.balls:
            if b['state'] == 'falling' and t >= b['t_nip']:
                b['state'] = 'nip'
            if b['state'] == 'nip':
                rpm = sum(self.rpm) / 2.0
                if rpm < 1400.0:
                    b['stray'] = True
                    continue
                if b.get('stray'):
                    v = (2.9 + self.rng.gauss(0, 0.4)) * C.FPS
                else:
                    v = launch_fps(rpm) * (1 + self.rng.gauss(0, 0.02)) * C.FPS
                for k in range(2):
                    self.rpm[k] *= 0.94
                t1 = t + 0.0048 + 0.030 / v + self.rng.uniform(-30e-6, 30e-6)
                t2 = t1 + 0.060 / v + self.rng.uniform(-30e-6, 30e-6)
                self._gate(t1, 1)
                self._gate(t2, 2)
                fps = v / C.FPS
                self.launched.append({'t': t, 'fps': fps, 'ref_fps': fps - 0.4 + self.rng.gauss(0, 0.2),
                                      'stray': bool(b.get('stray')), 'arm': self.arm, 'tilt': self.true_tilt(),
                                      'pan': self.true_pan(), 'rail': self.rail})
                b['state'] = 'gone'
        self.balls = [b for b in self.balls if b['state'] != 'gone']

    def rpm_at(self, t: float) -> float:
        best = 0.0
        for tt, v in reversed(self.rpm_log):
            if tt <= t:
                return v
            best = v
        return best

    def resting_balls(self) -> int:
        return sum(1 for b in self.balls if b['state'] == 'nip')

    # ------------------------------------------------------------------- stand-in temperatures
    def _thermal(self):
        if int(self.t * 1000) % 100:
            return
        for k in range(2):
            load = self.rpm[k] / 10000.0
            self.temp['esc'][k] += ((24.0 + 30.0 * load) - self.temp['esc'][k]) * 0.1 / 120.0
            self.temp['motor'][k] += ((24.0 + 26.0 * load) - self.temp['motor'][k]) * 0.1 / 180.0
        i24 = self.i24_log[-1][1] if self.i24_log else 0.0
        self.temp['reg'] += ((24.0 + 2.5 * i24) - self.temp['reg']) * 0.1 / 150.0


class SimRig:
    """The simulated turret and the firmware reference, stepped together at 1 kHz."""

    def __init__(self, seed: int = 1, cfg: Optional[C.Config] = None, **opt):
        import turret_fw
        self.seed = seed
        self.hw = SimTurret(seed, **opt)
        self.cfg = cfg or C.Config(tyre_mm=self.hw.tyre_mm)
        self._fw_mod = turret_fw
        self.fw = turret_fw.TurretFirmware(self.hw, self.cfg, index_offset_deg=self.hw.index_offset)

    @property
    def t(self) -> float:
        return self.hw.t

    def step(self):
        self.hw.step()
        self.fw.tick(self.hw.t)

    def run(self, seconds: float, until=None):
        end = self.hw.t + seconds
        while self.hw.t < end - 1e-9:
            self.step()
            if until is not None and until():
                return True
        return False

    def power_cycle(self, pan_deg: Optional[float] = None):
        """Switch the turret off and on (the stand's rocker): the firmware boots again."""
        if pan_deg is not None:
            self.hw.place_pan(pan_deg)
        self.hw.power_cycle()
        self.fw = self._fw_mod.TurretFirmware(self.hw, self.cfg, index_offset_deg=self.hw.index_offset)
