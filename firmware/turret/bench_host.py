"""The bench host: runs the v0 bench tests of docs/turret-prototype-plan.md section 5 that need the turret's firmware,
its CAN link or a reading to record, and writes each test's readings and pass/fail to exports/turret/bench/<file>.json.

    .venv/bin/python firmware/turret/bench_host.py --sim                    # every test, a dry run on the sim
    .venv/bin/python firmware/turret/bench_host.py --sim --tests 3.5,4.2    # some of them
    .venv/bin/python firmware/turret/bench_host.py --can socketcan:can0 --tests 3.1   # on the bench (python-can)
    .venv/bin/python firmware/turret/bench_host.py --list

--sim runs each test against sim_turret.py (the simulated turret with the firmware reference on it) and writes to
exports/turret/bench/sim/, never to exports/turret/bench/: a simulated result can never be mistaken for a bench reading.
Long tests are shortened in --sim (at most SIM_MAX_S of simulated time per phase; the JSON says so). Readings that need
an instrument the simulation does not model (an ohmmeter on the ring, an IR thermometer, paper targets) are filled by a
stated stand-in in --sim and listed under 'stand_ins'.

On the bench the script tells the operator what to do (hold or release the pendant, wire a fault, load balls) and asks
for the instruments' readings; --answers FILE answers them from a JSON {"<test>/<key>": value}. The host heartbeat
runs in a background thread, so the turret stays armed while the operator reads a scope. Tests 1.x and 2.x (fits,
strength) need neither firmware nor CAN and are not here.

Hard rules the script never relaxes: it never asks for a tilt above level (the firmware clamps it anyway), never fires
with the converter bypassed (test 4.6 runs with the feed servo unplugged and no balls), and never arms without
the operator's pendant.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import random
import statistics as st
import sys
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import can_msgs as M  # noqa: E402
import config as C  # noqa: E402

R = HERE.parents[1]
BENCH_OUT = R / 'exports' / 'turret' / 'bench'
SIM_OUT = BENCH_OUT / 'sim'
SIM_MAX_S = 120.0


# ===================================================================================== links
class SimLink:
    """The host on the simulated turret's CAN segment; time is the simulation's."""

    def __init__(self, rig):
        self.rig = rig
        self.error_frames = 0

    def now(self) -> float:
        return self.rig.t

    def send(self, cid: int, data: bytes):
        self.rig.hw.to_fw.append((cid, bytes(data)))

    def poll(self):
        q = self.rig.hw.to_host
        out = list(q)
        q.clear()
        return out

    def sleep(self, dt: float):
        self.rig.run(dt)

    def heartbeat_thread(self, flags_fn):
        return None


class CanLink:
    """The host on the bench's USB-CAN (python-can): 'socketcan:can0', 'slcan:/dev/ttyACM0', 'gs_usb:0'."""

    def __init__(self, spec: str):
        try:
            import can  # noqa: F401
        except ImportError:
            sys.exit('python-can is needed on the bench: pip install python-can')
        import can
        kind, _, chan = spec.partition(':')
        self.can = can
        self.bus = can.Bus(interface=kind, channel=chan or None, bitrate=1_000_000)
        self.t0 = time.monotonic()
        self.q: deque = deque()
        self.lock = threading.Lock()
        self.error_frames = 0
        self.stop = False
        self.flags_fn: Callable[[], int] = lambda: 0       # the arm request, from whichever test is running
        self.hb_thread: Optional[threading.Thread] = None
        threading.Thread(target=self._rx, daemon=True).start()

    def now(self) -> float:
        return time.monotonic() - self.t0

    def send(self, cid: int, data: bytes):
        self.bus.send(self.can.Message(arbitration_id=cid, data=data, is_extended_id=False))

    def _rx(self):
        while not self.stop:
            m = self.bus.recv(timeout=0.05)
            if m is None:
                continue
            if m.is_error_frame:
                self.error_frames += 1
                continue
            with self.lock:
                self.q.append((self.now(), m.arbitration_id, bytes(m.data)))

    def poll(self):
        with self.lock:
            out = list(self.q)
            self.q.clear()
        return out

    def sleep(self, dt: float):
        time.sleep(dt)

    def heartbeat_thread(self, flags_fn):
        """One heartbeat thread for the link's life; each test's Turret only swaps the flag source."""
        self.flags_fn = flags_fn
        if self.hb_thread is None:
            def run():
                n = 0
                while not self.stop:
                    n += 1
                    self.send(*M.pack('HOST_HEARTBEAT', counter=n & 0xFF, host_state=1, flags=self.flags_fn()))
                    time.sleep(0.1)
            self.hb_thread = threading.Thread(target=run, daemon=True)
            self.hb_thread.start()
        return self.hb_thread


# ===================================================================================== the turret as the host sees it
class Turret:
    def __init__(self, link):
        self.link = link
        self.arm_req = False
        self.hb_n = 0
        self.next_hb = 0.0
        self.hb: Dict = {}
        self.pose: Dict = {}
        self.wheels: Dict = {}
        self.feedmsg: Dict = {}
        self.power: Dict = {}
        self.health: Dict = {}
        self.events: List[tuple] = []
        self.shots: List[tuple] = []
        self.poses: deque = deque(maxlen=200_000)
        self.wheel_log: deque = deque(maxlen=200_000)
        self.pose_per_s: Dict[int, int] = defaultdict(int)
        self.first_hb_t: Optional[float] = None
        self.hb_log: deque = deque(maxlen=20_000)
        self.threaded = link.heartbeat_thread(lambda: 1 if self.arm_req else 0) is not None

    def now(self) -> float:
        return self.link.now()

    def pump(self):
        t = self.now()
        if not self.threaded and t >= self.next_hb:
            self.next_hb = t + 0.1
            self.hb_n += 1
            self.link.send(*M.pack('HOST_HEARTBEAT', counter=self.hb_n & 0xFF, host_state=1,
                                   flags=1 if self.arm_req else 0))
        for tf, cid, data in self.link.poll():
            if cid not in M.MSGS:
                continue
            name, f = M.unpack(cid, data)
            if name == 'TURRET_HEARTBEAT':
                self.hb = dict(f, t=tf)
                self.first_hb_t = tf if self.first_hb_t is None else self.first_hb_t
                self.hb_log.append((tf, f['state'], f['faults'], f['flags']))
            elif name == 'POSE':
                self.pose = dict(f, t=tf)
                self.poses.append((tf, f['pan_cdeg'] / 100.0, f['tilt_cdeg'] / 100.0, f['pan_rate']))
                self.pose_per_s[int(tf)] += 1
            elif name == 'WHEELS':
                self.wheels = dict(f, t=tf)
                self.wheel_log.append((tf, f['rpm_l'], f['rpm_r'], f['temp_l'], f['temp_r']))
            elif name == 'FEED':
                self.feedmsg = f
            elif name == 'POWER':
                self.power = f
            elif name == 'HEALTH':
                self.health = dict(f, t=tf)
            elif name == 'EVENT':
                self.events.append((tf, f))
            elif name == 'SHOT':
                self.shots.append((tf, f))

    def wait(self, s: float):
        end = self.now() + s
        while self.now() < end - 1e-9:
            self.link.sleep(min(0.01, end - self.now()))
            self.pump()

    def wait_for(self, pred: Callable[[], bool], timeout: float) -> bool:
        end = self.now() + timeout
        while self.now() < end:
            self.pump()
            if pred():
                return True
            self.link.sleep(0.01)
        self.pump()
        return pred()

    # ---------------------------------------------------------------- commands
    def aim(self, pan: float, tilt: float = 0.0, rate: float = 90.0):
        self.link.send(*M.pack('AIM', pan_cdeg=round(pan * 100), tilt_cdeg=round(min(0.0, tilt) * 100),
                               rate=int(rate)))

    def fire(self, balls: int, rate: float = 3.0, fps: float = 0.0, req: int = 1):
        self.link.send(*M.pack('FIRE', balls=balls, rate_d=round(rate * 10), fps_d=round(fps * 10), req=req))

    def cmd(self, code: int, a: int = 0, b: int = 0, c: int = 0):
        self.link.send(*M.pack('COMMAND', code=code, a=a, b=b, c=c))

    def config(self, kind: int, index: int = 0, a: int = 0, b: int = 0):
        self.link.send(*M.pack('CONFIG', kind=kind, index=index, a=a, b=b))

    def laser(self, on: bool):
        self.link.send(*M.pack('LASER', on=1 if on else 0))

    # ---------------------------------------------------------------- state
    def state(self) -> Optional[str]:
        return M.STATES[self.hb['state']] if self.hb else None

    def flags(self) -> int:
        return self.hb.get('flags', 0)

    def faults(self) -> int:
        return self.hb.get('faults', 0)

    def homed(self) -> bool:
        return bool(self.flags() & M.H_HOMED)

    def pan(self) -> Optional[float]:
        return self.pose['pan_cdeg'] / 100.0 if self.pose else None

    def tilt(self) -> Optional[float]:
        return self.pose['tilt_cdeg'] / 100.0 if self.pose else None

    def ev(self, code: int, since: float = 0.0) -> List[tuple]:
        return [(t, f) for t, f in self.events if f['code'] == code and t >= since]

    def shots_since(self, since: float) -> List[tuple]:
        return [(t, f) for t, f in self.shots if t >= since]

    def pan_rate_at(self, t: float) -> float:
        best = None
        for tp, _p, _t, r in reversed(self.poses):
            if tp <= t:
                best = r
                break
        return abs(best or 0)


# ===================================================================================== the operator and the instruments
class Bench:
    """The operator's hands and the bench instruments. On the bench: printed instructions and typed readings (or an
    answers file). In --sim: actions on the simulated turret, readings from its models or a stated stand-in."""

    def __init__(self, tt: Turret, rig=None, answers: Optional[dict] = None, test_id: str = '', quiet: bool = False):
        self.tt, self.rig, self.answers, self.id = tt, rig, answers or {}, test_id
        self.quiet = quiet
        self.stand_ins: List[str] = []
        self.scaled: Dict[str, dict] = {}

    @property
    def sim(self) -> bool:
        return self.rig is not None

    @property
    def hw(self):
        return self.rig.hw

    def say(self, text: str):
        if not self.sim and not self.quiet:
            print(f'  [{self.id}] {text}')

    def do(self, text: str, sim: Optional[Callable] = None):
        if self.sim:
            if sim:
                sim()
            return
        key = f'{self.id}/do:{text}'
        if key in self.answers:
            return
        input(f'  [{self.id}] {text}  (Enter when done) ')

    def ask(self, key: str, prompt: str, sim: Optional[Callable] = None, stand_in: bool = False, kind=float):
        if self.sim:
            if stand_in:
                self.stand_ins.append(key)
            return sim() if sim else None
        k = f'{self.id}/{key}'
        if k in self.answers:
            return self.answers[k]
        while True:
            v = input(f'  [{self.id}] {prompt}: ').strip()
            try:
                if kind is bool:
                    return v.lower().startswith('y')
                if kind is list:
                    return [float(x) for x in v.replace(',', ' ').split()]
                return kind(v)
            except ValueError:
                print('    a number, please')

    def duration(self, name: str, seconds: float) -> float:
        """A long phase's duration: the plan's on the bench, at most SIM_MAX_S in --sim (recorded)."""
        if self.sim and seconds > SIM_MAX_S:
            self.scaled[name] = {'plan_s': seconds, 'sim_s': SIM_MAX_S}
            return SIM_MAX_S
        return seconds

    # ---------------------------------------------------------------- the common actions
    def pendant(self, held: bool, wait: bool = True) -> bool:
        self.do('Hold the pendant' if held else 'Release the pendant', lambda: self.hw.set_pendant(held))
        if not wait:
            return True
        return self.tt.wait_for(lambda: bool(self.tt.flags() & M.H_ARM) == held, 0.5 if self.sim else 10.0)

    def ring_fault(self, kind: Optional[str], text: str):
        self.do(text, lambda: self.hw.set_ring_fault(kind))

    def load_balls(self, n: int, kind: str = 'new'):
        def s():
            self.hw.hopper = n
            if kind in ('worn', 'damp'):                 # stand-in: softer, tackier balls jam and feed less well
                self.hw.p_jam, self.hw.p_fill, self.hw.p_double = 0.02, 0.75, 0.002
        self.do(f'Load {n} {kind} balls into the hopper', s)


# ===================================================================================== results
class Result:
    def __init__(self, test: str, title: str, file: str):
        self.test, self.title, self.file = test, title, file
        self.readings: Dict = {}
        self.checks: List[dict] = []
        self.notes: List[str] = []

    def reading(self, key: str, value):
        self.readings[key] = value

    def check(self, name: str, value, ok: bool, limit: str):
        self.checks.append({'check': name, 'value': value, 'limit': limit, 'pass': bool(ok)})

    def note(self, text: str):
        self.notes.append(text)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c['pass'] for c in self.checks)


TESTS: List[tuple] = []


def test(tid: str, title: str, file: str, **sim_opts):
    def deco(fn):
        TESTS.append((tid, title, file, sim_opts, fn))
        return fn
    return deco


# ===================================================================================== shared steps
def r1(x, n=1):
    return None if x is None else round(x, n)


def boot(tt: Turret, b: Bench, timeout: float = 20.0) -> bool:
    """Wait for the turret's heartbeat and its homing; send the bench CONFIG (Ø38, the bench mount, the ring)."""
    ok = tt.wait_for(lambda: tt.homed() and tt.state() in ('IDLE', 'FAULT', 'ARMED'), timeout)
    tt.config(M.CF_TYRE, a=C.TYRE_DESIGN_MM)
    tt.config(M.CF_MOUNT, a=M.MOUNTS.index('bench'))
    tt.config(M.CF_RING, a=1)
    tt.wait(0.1)
    return ok


def arm(tt: Turret, b: Bench, timeout: float = 5.0) -> bool:
    b.pendant(True)
    tt.arm_req = False
    tt.wait(0.3)                                       # the re-arm: the request is seen low first
    tt.arm_req = True
    ok = tt.wait_for(lambda: tt.state() == 'ARMED', timeout)
    tt.wait(0.8)                                       # the ESCs arm on 0.6 s of zero throttle; the feed servo boots
    return ok


def disarm(tt: Turret, b: Bench):
    tt.arm_req = False
    b.pendant(False)
    tt.wait_for(lambda: tt.state() in ('IDLE', 'FAULT'), 3.0)


def burst_done(tt: Turret, since: float, timeout: float) -> Optional[dict]:
    tt.wait_for(lambda: bool(tt.ev(M.EV_BURST_DONE, since)), timeout)
    e = tt.ev(M.EV_BURST_DONE, since)
    return e[-1][1] if e else None


def bench_done(tt: Turret, since: float, timeout: float) -> bool:
    return tt.wait_for(lambda: bool(tt.ev(M.EV_BENCH_DONE, since)), timeout)


def fps_list(shots) -> List[float]:
    return [f['fps_d'] / 10.0 for _, f in shots if not f['flags'] & (M.S_GATE1_ONLY | M.S_STRAY)]


def pan_continuous(tt: Turret, rate: float, seconds: float, direction: int = 1, tilt: float = 0.0):
    """Pan for `seconds` at `rate` deg/s by keeping the AIM goal a second ahead; then hold where it is."""
    end = tt.now() + seconds
    while tt.now() < end:
        p = tt.pan() or 0.0
        tt.aim(p + direction * rate * 1.0, tilt, rate)
        tt.wait(0.1)
    tt.aim(tt.pan() or 0.0, tilt, rate)


def wrap(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


def stats(xs: List[float]) -> dict:
    if not xs:
        return {'n': 0}
    return {'n': len(xs), 'mean': round(st.mean(xs), 2), 'sd': round(st.pstdev(xs), 2), 'min': round(min(xs), 2),
            'max': round(max(xs), 2)}


# ===================================================================================== 5.3 electrics without motors
@test('3.1', 'Power-up: 5 V, 3.3 V, 12 V MAIN, 12 V PAN, the heartbeat, the servos, the pulse train and the 3.3 V inputs', 'power_up',
      ct_unplugged=True)
def t_power_up(tt, b, r):
    b.do('Unplug both CT connectors; switch the stand on now', lambda: b.rig.power_cycle())
    t0 = tt.now()
    got = tt.wait_for(lambda: tt.first_hb_t is not None and tt.first_hb_t >= t0, 5.0)
    hb_s = (tt.first_hb_t - t0) if got else None
    tt.wait(max(0.0, 2.0 - (tt.now() - t0)))
    f = tt.faults()
    pan_v, tilt_v = tt.power.get('pan_dv', 0) / 10.0, tt.power.get('tilt_dv', 0) / 10.0
    v5 = b.ask('rail_5v', 'Multimeter, 5 V on level 1 (V)', lambda: 5.02, stand_in=True)
    v33 = b.ask('rail_3v3', 'Multimeter, 3.3 V at the Feather\'s 3V pin (V)', lambda: 3.30, stand_in=True)
    fuses = b.ask('fuses_whole', 'Every fuse whole? (y/n)', lambda: True, stand_in=True, kind=bool)
    # the pulse train and the opto's LED current with the pendant held (docs/turret-wiring.md 3.1), and the Feather's
    # inputs (none may exceed 3.3 V: the SAMD51 is not 5 V tolerant)
    hz = b.ask('pulse_hz', 'Scope, pendant held: the 555\'s frequency at ring 7 (Hz)', lambda: 986.0, stand_in=True)
    r8 = b.ask('r8_drop_v', 'Scope, pendant held: the peak drop across R8 on level 1 (V)', lambda: 4.4, stand_in=True)
    vpin = b.ask('max_input_v', 'Scope: the highest level on D0, D9, D10, D11, D12, A0, A1, A3 (V)', lambda: 3.3, stand_in=True)
    r.reading('heartbeat_after_s', r1(hb_s, 3))
    r.reading('pan_servo_rail_v', pan_v)
    r.reading('tilt_servo_rail_v', tilt_v)
    r.reading('faults', [n for k, n in M.FAULT_NAMES.items() if f & k])
    r.check('heartbeat on CAN within 2 s', r1(hb_s, 3), hb_s is not None and hb_s <= 2.0, '<= 2 s')
    r.check('pan servo answers (ID 1)', not f & M.F_PAN_MISSING, not f & M.F_PAN_MISSING, 'answers')
    r.check('tilt servo answers (ID 2)', not f & M.F_TILT_MISSING, not f & M.F_TILT_MISSING, 'answers')
    r.check('12 V PAN at the pan servo', pan_v, 11.5 <= pan_v <= 12.5, '11.5-12.5 V (the servo reads it)')
    r.check('12 V MAIN at the tilt servo', tilt_v, 11.5 <= tilt_v <= 12.5, '11.5-12.5 V')
    r.check('5 V', v5, 4.75 <= v5 <= 5.25, '4.75-5.25 V')
    r.check('3.3 V', v33, 3.2 <= v33 <= 3.4, '3.2-3.4 V')
    r.check('the pulse train', hz, 900.0 <= hz <= 1075.0, '900-1,075 Hz (986 nominal; the firmware accepts 870-1,176)')
    r.check('the opto LED\'s current (R8 2.2 k)', r8, 3.5 <= r8 <= 5.3, '3.5-5.3 V: 1.6-2.4 mA')
    r.check('no Feather input above 3.3 V', vpin, vpin <= 3.4, '<= 3.4 V')
    r.check('no fuse blown', fuses, fuses, 'all whole')


@test('3.2', 'The pulse-train safety line with a lamp on 12 V FLY: release and the ring faults', 'safety_line',
      ct_unplugged=True)
def t_safety_line(tt, b, r):
    boot(tt, b)
    rows = []
    cases = [('release', None, 'Release the pendant'),
             ('open at the ring', 'open', 'Open the SAFETY pair at the ring'),
             ('short to GND', 'gnd', 'Short SAFETY+ to GND'),
             ('short to +24 V', '24v', 'Short SAFETY+ to +24 V'),
             ('DC level', 'dc', 'Inject a DC level from the generator'),
             ('300 Hz train', 'f300', 'Inject a 300 Hz train from the generator'),
             ('3 kHz train', 'f3k', 'Inject a 3 kHz train from the generator'),
             ('50 Hz hum', 'hum50', 'Couple 50 Hz hum onto the pair')]
    for name, kind, text in cases:
        b.ring_fault(None, 'Remove any fault: the genuine 1 kHz train')
        arm(tt, b)
        lamp_before = bool(tt.flags() & M.H_ARM)
        t_f = tt.now()
        if kind is None:
            b.pendant(False, wait=False)
        else:
            b.ring_fault(kind, text)
        tt.wait(0.25)
        if b.sim:
            off = [t for t, k in b.hw.timeline if k == 'rail_off' and t >= t_f]
            rail_ms = (off[0] - t_f) * 1000 if off else None
        else:
            v = b.ask(f'rail_off_ms_{kind or "release"}', f'{name}: scope at the 2815 output, ms to off (blank if it '
                      f'stayed on)', kind=str)
            rail_ms = float(v) if v not in ('', None) else None
        safe = tt.ev(M.EV_SAFE, t_f)
        fw_ms = (safe[0][0] - t_f) * 1000 if safe else None
        causes = [n for k, n in M.FAULT_NAMES.items() if safe and safe[0][1]['a'] & k]
        rows.append({'case': name, 'lamp_on_before': lamp_before, 'rail_off_ms': r1(rail_ms),
                     'firmware_safe_ms': r1(fw_ms), 'firmware_causes': causes, 'state_after': tt.state()})
        if kind is None:
            b.pendant(True)
    # the genuine train back: the hardware re-arms at once, the firmware only after the host's re-arm
    b.ring_fault(None, 'Remove the fault: the genuine 1 kHz train, pendant held')
    b.pendant(True)
    tt.wait(0.5)
    hw_rearmed = bool(tt.flags() & M.H_ARM)
    fw_waits = tt.state() != 'ARMED' and bool(tt.flags() & M.H_REARM_WAIT)
    ok_rearm = arm(tt, b)
    disarm(tt, b)
    r.reading('cases', rows)
    wrong_freq = ('300 Hz train', '3 kHz train', '50 Hz hum')
    for row in rows:
        if row['case'] in wrong_freq:
            # docs/turret-bench-tests.md 3.2: the one-shot sees edges, so the rail may stay on (the hardware frequency
            # window is a v1 item); the firmware must zero the throttle and refuse to feed on PULSE_MON
            r.reading(f"{row['case']}: rail off (2815 output), ms (expected: stays on)", row['rail_off_ms'])
            r.check(f"{row['case']}: firmware zero throttle (SAFE)", row['firmware_safe_ms'],
                    row['firmware_safe_ms'] is not None and row['firmware_safe_ms'] <= 10.0, '<= 10 ms')
            continue
        hw_ok = row['rail_off_ms'] is not None and row['rail_off_ms'] <= 25.0
        r.check(f"{row['case']}: rail off (2815 output)", row['rail_off_ms'], hw_ok, '<= 25 ms')
        r.check(f"{row['case']}: firmware zero throttle (SAFE)", row['firmware_safe_ms'],
                row['firmware_safe_ms'] is not None and row['firmware_safe_ms'] <= 25.0, '<= 25 ms')
    r.check('genuine train arms the hardware again', hw_rearmed, hw_rearmed, 'armed')
    r.check('firmware waits for the host re-arm', fw_waits, fw_waits, 'not ARMED until the request cycles')
    r.check('host re-arm accepted', ok_rearm, ok_rearm, 'ARMED')
    r.note('The 20 ms retriggerable one-shot is kept triggered by any train faster than ~50 Hz: a 300 Hz or 3 kHz '
           'train (and 50 Hz hum at the one-shot\'s own period) holds the rails on, as docs/turret-wiring.md 3.1 says. '
           'The firmware refuses on PULSE_MON (periods outside 0.85-1.15 ms); the hardware frequency window (a 74HC221 '
           'pair) is a v1 item.')


@test('3.3', 'Trip latch with simulated gate pairs', 'trip', ct_unplugged=True)
def t_trip(tt, b, r):
    boot(tt, b)
    b.pendant(True)
    win_ms = C.GATE_SPACING_M / (C.TRIP_FPS * C.FPS) * 1000.0
    rows = []
    for ms in (1.3, 1.6, 1.75, 1.8, 1.85, 1.9, 1.95, 2.1):     # D68: the window is 1.875 ms (105 fps over 60 mm)
        b.do('Press the recessed trip reset', lambda: b.hw.reset_trip())
        tt.wait(0.1)
        t0 = tt.now()
        b.do(f'Signal generator: one gate pair, {ms} ms apart', lambda: b.hw.gate_pair(ms / 1000.0))
        tt.wait(0.25)
        shots = tt.shots_since(t0)
        fps = shots[-1][1]['fps_d'] / 10.0 if shots else None
        rows.append({'pair_ms': ms, 'pair_fps': round(C.GATE_SPACING_M / (ms / 1000.0) / C.FPS, 1),
                     'latched': bool(tt.flags() & M.H_TRIP), 'arm_while_latched': bool(tt.flags() & M.H_ARM),
                     'firmware_interval_ms': round(C.GATE_SPACING_M / (fps * C.FPS) * 1000, 3) if fps else None})
    # the latch holds until the button: a slower ball after the trip (its gate 2 outside the window) must not clear it
    b.do('One gate pair, 1.3 ms apart', lambda: b.hw.gate_pair(0.0013))
    tt.wait(0.3)
    b.do('Then one gate pair, 3.5 ms apart (a slower ball after the trip)', lambda: b.hw.gate_pair(0.0035))
    tt.wait(1.0)
    held = bool(tt.flags() & M.H_TRIP)
    arm_low = not tt.flags() & M.H_ARM
    b.do('Press the recessed trip reset', lambda: b.hw.reset_trip())
    tt.wait(0.2)
    cleared = not tt.flags() & M.H_TRIP and bool(tt.flags() & M.H_ARM)
    b.pendant(False)
    r.reading('window_ms_for_trip_fps_over_60mm', round(win_ms, 3))
    r.reading('pairs', rows)
    sel = [x['pair_ms'] for x in rows if x['latched']]
    r.reading('boundary_ms', {'largest_latched': max(sel) if sel else None,
                              'smallest_not_latched': min([x['pair_ms'] for x in rows if not x['latched']] or [None])})
    for x in rows:
        if x['pair_ms'] <= 1.8:
            r.check(f"{x['pair_ms']} ms ({x['pair_fps']} fps) latches", x['latched'], x['latched'], 'latched')
        elif x['pair_ms'] >= 1.95:
            r.check(f"{x['pair_ms']} ms ({x['pair_fps']} fps) does not", x['latched'], not x['latched'], 'not latched')
        if x['latched']:
            r.check(f"ARM held low while latched ({x['pair_ms']} ms)", x['arm_while_latched'],
                    not x['arm_while_latched'], 'ARM low')
        if x['firmware_interval_ms'] is not None:
            r.check(f"firmware times the {x['pair_ms']} ms pair", x['firmware_interval_ms'],
                    abs(x['firmware_interval_ms'] - x['pair_ms']) <= 0.02, '+-0.02 ms')
    r.check('the latch holds until the button (a slower pair after the trip does not clear it)', held and arm_low, held and arm_low,
            'latched, ARM low after 1 s')
    r.check('the button clears it and ARM returns', cleared, cleared, 'cleared')
    r.note('Judged on the 60 mm gates\' window (1.875 ms = 105 fps, D68): latch at <= 1.80 ms (109 fps), none at >= 1.95 ms '
           '(101 fps); 1.85 and 1.9 ms are inside the band the 30 us edge jitter and a 1 % timing part allow (+-2.7 fps).')


@test('3.4', 'Brake timing with a lamp: BRAKE after ARM falls, and before 12 V FLY returns', 'brake_timing',
      ct_unplugged=True)
def t_brake_timing(tt, b, r):
    boot(tt, b)
    rows = []
    for k in range(5):
        b.pendant(True)
        tt.wait(0.5)
        t0 = tt.now()
        b.pendant(False, wait=False)
        tt.wait(0.2)
        b.pendant(True, wait=False)
        tt.wait(0.2)
        if b.sim:
            tl = [(t, e) for t, e in b.hw.timeline if t >= t0]
            ta = next(t for t, e in tl if e == 'arm_off')
            tb = next(t for t, e in tl if e == 'brake_on')
            ta_on = next(t for t, e in tl if e == 'arm_on' and t > tb)
            tr_on = next(t for t, e in tl if e == 'rail_on')
            tb_off = next(t for t, e in tl if e == 'brake_off')
            on_ms, off_ms, off_vs_rail = (tb - ta) * 1000, (tb_off - ta_on) * 1000, (tb_off - tr_on) * 1000
        else:
            on_ms = b.ask(f'brake_on_ms_{k}', 'Scope: ms from ARM falling to BRAKE rising')
            off_ms = b.ask(f'brake_off_ms_{k}', 'Scope: ms from ARM rising to BRAKE falling')
            off_vs_rail = b.ask(f'brake_off_vs_rail_ms_{k}', 'Scope: ms from 12 V FLY returning to BRAKE falling '
                                '(negative if BRAKE fell first)')
        rows.append({'brake_on_after_arm_off_ms': r1(on_ms), 'brake_off_after_arm_on_ms': r1(off_ms),
                     'brake_off_minus_rail_on_ms': r1(off_vs_rail)})
    b.pendant(False)
    r.reading('releases', rows)
    for i, x in enumerate(rows):
        r.check(f'release {i + 1}: BRAKE rises after ARM falls', x['brake_on_after_arm_off_ms'],
                5.0 <= x['brake_on_after_arm_off_ms'] <= 14.0, '5-14 ms')
        r.check(f're-arm {i + 1}: BRAKE falls within 2 ms of ARM rising', x['brake_off_after_arm_on_ms'],
                x['brake_off_after_arm_on_ms'] <= 2.0, '<= 2 ms (0.6-1.4 ms drawn; the ESCs drive nothing for 0.5 s after 12 V FLY returns)')
    r.note('As drawn (docs/turret-wiring.md 3.3: ARM through 6.8 k into 1 uF and one 74HCT14 inverter on the cartridge '
           'board) BRAKE rises 6.8 ms x ln(3.3 / V_T-) = 5-14 ms (about 8) after ARM falls; D3 and 1 k fill the capacitor '
           '(tau 0.9 ms) when ARM rises, so BRAKE falls 0.6-1.4 ms later, long before the ESCs can drive.')


@test('3.5', 'Homing: 50 power-ups at random pans; 10 continuous turns each way and back', 'homing_bench')
def t_homing(tt, b, r):
    rng = random.Random(b.rig.seed if b.sim else 0)
    rows = []
    for k in range(50):
        pan0 = rng.uniform(-180.0, 180.0)
        t0 = tt.now()
        if b.sim:
            b.rig.power_cycle(pan_deg=pan0)
        else:
            b.do(f'Power-up {k + 1}/50: switch off, turn the turntable by hand to about {pan0:.0f} deg, switch on')
            t0 = tt.now()
        got = tt.wait_for(lambda: bool(tt.ev(M.EV_HOMED, t0)) or bool(tt.ev(M.EV_HOME_FAILED, t0)), 15.0)
        e = tt.ev(M.EV_HOMED, t0)
        if not e:
            rows.append({'run': k + 1, 'homed': False})
            continue
        te, f = e[0]
        rows.append({'run': k + 1, 'homed': True, 'time_s': round(te - t0, 2), 'homing_s': f['a'] / 100.0,
                     'centre_counts': round(f['b'] / 16.0, 3), 'swept_deg': f['c'],
                     'true_err_deg': None})
        tt.wait(0.8)
        if b.sim:
            rows[-1]['true_err_deg'] = round(wrap((tt.pan() or 0.0) - b.hw.true_pan()), 3)
    boot(tt, b)
    homed = [x for x in rows if x['homed']]
    cs = [x['centre_counts'] for x in homed]
    ref = cs[0] if cs else 0.0
    dev = [((c - ref + 2048) % 4096 - 2048) * C.PAN_PER_COUNT for c in cs]
    spread = (max(dev) - min(dev)) if dev else None
    times = [x['time_s'] for x in homed]
    # 10 continuous turns each way and back
    turns = []
    for direction in (+1, -1):
        tt.aim(tt.pan() or 0.0, 0.0, 90)
        tt.wait(1.5)
        p0 = tt.pan()
        true0 = b.hw.true_pan() if b.sim else None
        tt.aim(p0 + direction * 3600.0, 0.0, 90)
        tt.wait_for(lambda: abs((tt.pan() or 0.0) - (p0 + direction * 3600.0)) < 0.5, 60.0)
        tt.wait(1.0)
        tt.aim(p0, 0.0, 90)
        tt.wait_for(lambda: abs((tt.pan() or 0.0) - p0) < 0.3, 60.0)
        tt.wait(1.5)
        if b.sim:
            back = abs(wrap(b.hw.true_pan() - true0))
        else:
            back = b.ask(f'turns_back_deg_{direction}', 'Laser dot back at its start mark: offset at the wall '
                         '(deg; mm / distance mm x 57.3)')
        turns.append({'direction': '+' if direction > 0 else '-', 'firmware_back_deg': round(abs(tt.pan() - p0), 3),
                      'back_within_deg': r1(back, 3)})
    tt.wait(1.2)
    worst = tt.health.get('index_worst', 0) / 100.0
    r.reading('power_ups', rows)
    r.reading('home_time_s', stats(times))
    r.reading('index_centre_spread_deg', r1(spread, 3))
    r.reading('turns', turns)
    r.reading('index_recheck_worst_deg', worst)
    r.check('every power-up homed', len(homed), len(homed) == 50, '50 of 50')
    r.check('every home within 7 s', max(times) if times else None, bool(times) and max(times) <= 7.0, '<= 7 s')
    r.check('index centre spread', r1(spread, 3), spread is not None and spread <= 0.1, '<= 0.1 deg (max - min)')
    for x in turns:
        r.check(f"10 turns {x['direction']} and back", x['back_within_deg'], x['back_within_deg'] is not None and
                x['back_within_deg'] <= 0.2, '<= 0.2 deg')
    r.check('index re-check worst', worst, worst <= 0.2, '<= 0.2 deg (none asks for a re-home)')


@test('3.6', 'The servo bus over the ring: 1 h of 100 Hz reads and writes to the pan servo at 500 kbit/s',
      'ring_servo_bus')
def t_ring_servo_bus(tt, b, r):
    boot(tt, b)
    dur = b.duration('panning', 3600.0)
    tt.wait(1.2)
    e0 = tt.health.get('servo_err', 0)
    t0 = tt.now()
    errs = []
    stops = 0
    while tt.now() - t0 < dur:
        pan_continuous(tt, 90.0, min(20.0, dur - (tt.now() - t0)))
        tt.wait(1.5)                                   # a stop: the command arrived?
        goal = tt.pan()
        tt.aim(goal + 15.0, 0.0, 90)
        tt.wait(1.5)
        errs.append(abs((tt.pan() or 0.0) - (goal + 15.0)) / C.PAN_PER_COUNT)
        stops += 1
    tt.wait(1.2)
    n_err = tt.health.get('servo_err', 0) - e0
    secs = tt.now() - t0
    txn = secs * C.SERVO_READ_HZ
    rate = n_err / txn if txn else None
    r.reading('seconds', round(secs, 1))
    r.reading('servo_errors', n_err)
    r.reading('pan_reads_est', int(txn))
    r.reading('position_error_counts_at_stops', [round(x, 1) for x in errs])
    r.check('checksum retries', r1(100 * rate, 4) if rate is not None else None,
            rate is not None and rate < 0.001, '< 0.1 % of transfers')
    r.check('no command lost', r1(max(errs), 1) if errs else None, bool(errs) and max(errs) <= 2.0,
            'within 2 counts at every stop')
    r.note('The pan servo is read at 100 Hz; the transfer count is that rate x the time (HEALTH carries the error '
           'count, not the transfers).')


@test('3.7', 'Ring contact resistance and dropouts (operator readings)', 'ring_contacts')
def t_ring_contacts(tt, b, r):
    boot(tt, b)
    rng = random.Random(7)
    res = []
    for k in range(12):
        tt.aim(k * 30.0, 0.0, 90)
        tt.wait(1.5)
        p = b.ask(f'r_pos_mohm_{k}', f'Pan {k * 30} deg: 5 A through the +24 V pair, mOhm',
                  lambda: round(24 + rng.uniform(0, 8), 1), stand_in=True)
        g = b.ask(f'r_gnd_mohm_{k}', f'Pan {k * 30} deg: 5 A through the GND pair, mOhm',
                  lambda: round(24 + rng.uniform(0, 8), 1), stand_in=True)
        res.append({'pan_deg': k * 30, 'pos_pair_mohm': p, 'gnd_pair_mohm': g})
    out = {}
    for rpm, rate in ((15, 90.0), (2, 12.0)):
        b.say(f'Scope the drop at 1 MHz, 10 captures of 10 s while the turret pans at {rpm} rpm with 5 A flowing')
        pan_continuous(tt, rate, b.duration(f'pan_{rpm}rpm', 100.0))
        drop = b.ask(f'dropout_us_{rpm}', f'{rpm} rpm: longest dropout (us)', lambda: 0.0, stand_in=True)
        var = b.ask(f'variation_mohm_{rpm}', f'{rpm} rpm: peak resistance variation (mOhm)',
                    lambda: round(10 + rng.uniform(0, 6), 1), stand_in=True)
        out[f'{rpm}rpm'] = {'longest_dropout_us': drop, 'variation_mohm': var}
    r.reading('static', res)
    r.reading('dynamic', out)
    worst = max(max(x['pos_pair_mohm'], x['gnd_pair_mohm']) for x in res)
    r.check('resistance per paralleled pair', worst, worst <= 60.0, '<= 60 mOhm')
    for k, v in out.items():
        r.check(f'{k}: no dropout over 100 us', v['longest_dropout_us'], v['longest_dropout_us'] <= 100.0, '<= 100 us')
        r.check(f'{k}: variation', v['variation_mohm'], v['variation_mohm'] <= 60.0, '<= 60 mOhm')


@test('3.8', 'CAN over the ring: 1,000 frames/s while panning at 15 rpm, then 2 rpm', 'ring_can')
def t_ring_can(tt, b, r):
    boot(tt, b)
    phases = {}
    for rpm, rate in ((15, 90.0), (2, 12.0)):
        dur = b.duration(f'{rpm}rpm', 3600.0)
        tt.wait(1.2)
        h0 = dict(tt.health)
        ef0 = tt.link.error_frames
        tt.cmd(M.CMD_BENCH_STREAM, a=1000, b=int(dur) + 2)
        t0 = tt.now()
        tt.wait(1.0)
        pan_continuous(tt, rate, dur)
        tt.wait(1.2)
        secs = [s for s in range(int(t0) + 2, int(t0 + dur))]
        counts = [tt.pose_per_s.get(s, 0) for s in secs]
        lost = sum(1 for c in counts if c < 900)
        frames = sum(counts)
        h1 = tt.health
        ef = b.ask(f'error_frames_{rpm}', f'{rpm} rpm: the adapter\'s error frames (candump -e / ip -s link)',
                   lambda: tt.link.error_frames - ef0, stand_in=False) if not b.sim else tt.link.error_frames - ef0
        phases[f'{rpm}rpm'] = {'seconds': len(secs), 'pose_frames': frames, 'min_per_s': min(counts) if counts else 0,
                               'lost_seconds': lost, 'busoff': h1.get('busoff', 0) - h0.get('busoff', 0),
                               'tec_max': h1.get('tec'), 'rec_max': h1.get('rec'), 'error_frames': ef}
    r.reading('phases', phases)
    for k, v in phases.items():
        r.check(f'{k}: no bus-off', v['busoff'], v['busoff'] == 0, '0')
        r.check(f'{k}: error frames', v['error_frames'], v['error_frames'] <= max(1, v['pose_frames'] // 1_000_000),
                '< 1 per 10^6 frames')
        r.check(f'{k}: no lost telemetry second', v['lost_seconds'], v['lost_seconds'] == 0,
                'every second >= 900 POSE frames')


@test('3.9', 'Feed servo alone: 200 steps empty, 200 full, a deliberate jam', 'feed_servo', ct_unplugged=True,
      feed_bench_power=True)
def t_feed_servo(tt, b, r):
    boot(tt, b)
    b.do('Power the feed servo from the bench through CT power pin 3; the hopper empty',
         lambda: (setattr(b.hw, 'hopper', 0), setattr(b.hw, 'p_jam', 0.0)))
    arm(tt, b)
    out = {}
    for label, prep in (('empty hopper', None), ('full hopper', 'Fill the hopper (30 balls)')):
        if prep:
            def full():
                b.hw.feed_servo.extra_load, b.hw.feed_servo.load_factor = 150, 0.9
            b.do(prep, full)
        t0 = tt.now()
        tt.cmd(M.CMD_BENCH_FEED_STEPS, a=200, b=30)
        bench_done(tt, t0, 200 / 3.0 + 30)
        ev = tt.ev(M.EV_FEED_STEP, t0)
        clean = [f for _, f in ev if not f['c'] & 0x8000]
        settle = [f['b'] for f in clean]
        loads = [f['c'] & 0x7FFF for f in clean]
        out[label] = {'steps': len(ev), 'clean': len(clean), 'settle_ms': stats(settle),
                      'load_mean_0p1pct': stats(loads), 'jams': len(tt.ev(M.EV_FEED_JAM, t0))}
    b.do('Put a pencil in a pocket (a deliberate jam)', lambda: setattr(b.hw, 'force_jam_next', True))
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_FEED_STEPS, a=3, b=30)
    bench_done(tt, t0, 10.0)
    jams = tt.ev(M.EV_FEED_JAM, t0)
    steps = tt.ev(M.EV_FEED_STEP, t0)
    jam = {'detected': bool(jams), 'detect_ms_after_command': jams[0][1]['b'] if jams else None,
           'cause': ('timeout', 'load')[(jams[0][1]['c'] & 0xF) - 1] if jams else None,
           'recovered': any(f['c'] & 0x8000 for _, f in steps), 'steps_after': len(steps)}
    disarm(tt, b)
    r.reading('runs', out)
    r.reading('deliberate_jam', jam)
    for k, v in out.items():
        r.check(f'{k}: 200 steps', v['steps'], v['steps'] == 200, '200')
        r.check(f'{k}: settled within 2 deg', v['settle_ms'].get('max'), v['settle_ms'].get('max', 9e9) <= 250,
                '<= 250 ms')
        cv = v['load_mean_0p1pct']['sd'] / v['load_mean_0p1pct']['mean'] if v['load_mean_0p1pct'].get('mean') else 9
        r.check(f'{k}: load reading repeatable', round(cv, 3), cv <= 0.15, 'SD <= 15 % of the mean')
    r.check('deliberate jam detected', jam['detect_ms_after_command'], jam['detected'] and
            jam['detect_ms_after_command'] <= 300, '<= 300 ms after the step command')
    r.check('jam reversed and the step completed', jam['recovered'], jam['recovered'], 'reversed, retried, settled')


# ===================================================================================== 5.4 flywheels
@test('4.1', 'No-load eRPM at 100 % throttle on the trimmed rail (the D68 trim)', 'ceiling_noload', hopper=0)
def t_ceiling_noload(tt, b, r):
    boot(tt, b)
    arm(tt, b)
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_SPIN, a=1000, b=30)
    bench_done(tt, t0, 8.0)
    held = [(t, l, rr) for t, l, rr, _a, _b in tt.wheel_log if t >= t0 + 1.0 and l > 0]
    tail = [x for x in held if x[0] >= held[-1][0] - 1.0] if held else []
    rl = [x[1] for x in tail]
    rr = [x[2] for x in tail]
    rail = b.ask('rail_v', 'Multimeter: the FLY rail at the ESCs under load (V)', lambda: round(b.hw.rail_v, 2))
    disarm(tt, b)
    lim_plan = C.ERPM_LIMIT / C.POLE_PAIRS
    r.reading('rpm_left', stats(rl))
    r.reading('rpm_right', stats(rr))
    r.reading('erpm_max', round(max(rl + rr) * C.POLE_PAIRS) if rl else None)
    r.reading('rail_v', rail)
    mx = max(rl + rr) if rl else None
    r.check('both wheels under the eRPM guard (a ball at 105 fps)', mx, mx is not None and mx <= lim_plan,
            f'<= {lim_plan:.0f} rpm ({C.ERPM_LIMIT} eRPM)')
    r.check('the faster wheel at or under the trim (warm, after a 3 minute spin)', mx,
            mx is not None and mx <= C.NO_LOAD_RPM_MAX,
            f'<= {C.NO_LOAD_RPM_MAX:.0f} rpm (no_load_rpm_max): else change the trim resistor down a step, never fire')
    r.check('the FLY rail under load', rail, 10.7 <= rail <= 12.0, '10.8-11.9 V (the trim for KV +-5 %)')


@test('4.2', 'Ceiling with balls: 20 balls at 100 % throttle, Ø38', 'ceiling', hopper=25)
def t_ceiling(tt, b, r):
    boot(tt, b)
    b.load_balls(20)
    arm(tt, b)
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_FIRE_THROTTLE, a=1000, b=20, c=30)
    bench_done(tt, t0, 30.0)
    gates = fps_list(tt.shots_since(t0))
    if b.sim:
        ref = [x['ref_fps'] for x in b.hw.launched if x['t'] >= t0 and not x['stray']]
    else:
        ref = b.ask('reference_fps', 'Reference chronograph, the 20 readings (fps, spaces between)', kind=list)
    disarm(tt, b)
    r.reading('gates_fps', stats(gates))
    r.reading('reference_fps', stats(ref))
    r.reading('gates_each', gates)
    r.check('20 balls', len(gates), len(gates) == 20, '20')
    r.check(f'every ball <= {C.TRIP_FPS:.0f} fps on the barrel gates', max(gates) if gates else None,
            bool(gates) and max(gates) <= C.TRIP_FPS, f'<= {C.TRIP_FPS:.0f} fps')
    r.check(f'every ball <= {C.TRIP_FPS:.0f} fps on the reference', max(ref) if ref else None,
            bool(ref) and max(ref) <= C.TRIP_FPS, f'<= {C.TRIP_FPS:.0f} fps')
    r.note('D68: Ø38 at 40 % crush is the only tyre. Hasbro rounds should read 95-100 fps here (the launch model: '
           f'{C.FULL_THROTTLE_FPS} fps); repeat with the lightest accepted off-brand rounds (1.6 g): every one at or '
           'under 105, or the trim comes down a step.')


@test('4.3', 'Speed at every throttle: 10 balls each at 60-100 %', 'speed_map', hopper=60)
def t_speed_map(tt, b, r):
    boot(tt, b)
    b.load_balls(50)
    arm(tt, b)
    rows = []
    for thr in (0.6, 0.7, 0.8, 0.9, 1.0):
        t0 = tt.now()
        tt.cmd(M.CMD_BENCH_FIRE_THROTTLE, a=int(thr * 1000), b=10, c=30)
        bench_done(tt, t0, 20.0)
        sh = tt.shots_since(t0)
        f = fps_list(sh)
        first = sh[0][0] if sh else tt.now()
        rpms = [(l + rr) / 2.0 for t, l, rr, _a, _b in tt.wheel_log if t0 + 0.5 <= t < first - 0.05]
        rows.append({'throttle': thr, 'fps': stats(f), 'rpm_before_first_ball': round(max(rpms)) if rpms else None})
        tt.wait(1.0)
    disarm(tt, b)
    means = [x['fps'].get('mean', 0) for x in rows]
    r.reading('table', rows)
    r.reading('config_throttle_map_rows', [{'throttle_permille': int(x['throttle'] * 1000),
                                            'rpm': x['rpm_before_first_ball']} for x in rows])
    r.check('monotonic', means, all(b2 > a2 for a2, b2 in zip(means, means[1:])), 'each step faster')
    for x in rows:
        r.check(f"SD at {int(x['throttle'] * 100)} %", x['fps'].get('sd'), x['fps'].get('sd', 9) <= 3.0, '<= 3 fps (3 %)')
        r.check(f"10 balls at {int(x['throttle'] * 100)} %", x['fps']['n'], x['fps']['n'] == 10, '10')


@test('4.4', 'Set speed: 50 balls at the set rpm for 95 fps (Ø38)', 'set_speed', hopper=55)
def t_set_speed(tt, b, r):
    boot(tt, b)
    b.load_balls(50)
    arm(tt, b)
    t0 = tt.now()
    tt.fire(50, 3.0, C.SET_FPS_DESIGN)
    burst_done(tt, t0, 60.0)
    f = fps_list(tt.shots_since(t0))
    disarm(tt, b)
    s = stats(f)
    r.reading('set_rpm', round(C.set_rpm(C.SET_FPS_DESIGN, C.TYRE_DESIGN_MM)))
    r.reading('fps', s)
    r.check('50 balls', s['n'], s['n'] == 50, '50')
    r.check('mean', s.get('mean'), abs(s.get('mean', 0) - C.SET_FPS_DESIGN) <= 3.0, f'{C.SET_FPS_DESIGN:.0f} +- 3 fps')
    r.check('SD', s.get('sd'), s.get('sd', 9) <= 3.0, '<= 3 fps')
    r.check(f'none over {C.TRIP_FPS:.0f} fps', s.get('max'), s.get('max', 999) <= C.TRIP_FPS, f'<= {C.TRIP_FPS:.0f} fps')


@test('4.5', 'Spin-up current with the 800 ms ramp, and burst recovery (8 balls at 3/s)', 'spinup_current', hopper=10)
def t_spinup_current(tt, b, r):
    boot(tt, b)
    b.load_balls(8)
    arm(tt, b)
    if b.sim:
        b.hw.i24_peak, b.hw.bus_min = 0.0, b.hw.supply_now
    t0 = tt.now()
    tt.fire(8, 3.0, C.SET_FPS_DESIGN)
    burst_done(tt, t0, 20.0)
    spin_peak = None
    if b.sim:                                          # the spin-up's peak: up to the first ball at the nip
        first = min([x['t'] for x in b.hw.launched if x['t'] >= t0] or [tt.now()])
        spin_peak = round(max([i for t, i in b.hw.i24_log if t0 <= t < first] or [0.0]), 2)
    f = fps_list(tt.shots_since(t0))
    peak = b.ask('ring_peak_a', 'Shunt in the ring\'s +24 V lead: peak current during the spin-up, before the first '
                 'ball (A)', lambda: spin_peak)
    rec = b.ask('burst_peak_a', 'Shunt: peak during the burst\'s recovery pulses (A)', lambda: round(b.hw.i24_peak, 2))
    bus_min = b.ask('bus_min_v', 'Scope: lowest bus voltage at the turret board (V)', lambda: round(b.hw.bus_min, 2))
    resets = [e for e in tt.ev(M.EV_SAFE, t0) if e[1]['a'] & M.F_TELEMETRY]
    disarm(tt, b)
    r.reading('ring_peak_a', peak)
    r.reading('burst_recovery_peak_a', rec)
    r.reading('bus_min_v', bus_min)
    r.reading('burst_fps', f)
    r.check('ring peak with the ramp', peak, peak <= 4.0, '<= 4 A at 24 V (D68: ~96 W at the input)')
    r.check('bus at the board', bus_min, bus_min >= 16.0, '>= 16 V')
    r.check('no ESC reset (telemetry continuous)', len(resets), not resets, 'none')
    r.check('8 balls', len(f), len(f) == 8, '8')
    r.check('every shot within 6 % of the set speed', max(abs(x - C.SET_FPS_DESIGN) for x in f) if f else None,
            bool(f) and all(abs(x - C.SET_FPS_DESIGN) <= 0.06 * C.SET_FPS_DESIGN for x in f), f'{C.SET_FPS_DESIGN:.0f} +- 6 %')


@test('4.6', 'The converter bypassed (the ESCs on the 20.5 V pack) without a ball: the pre-feed check, and the trip '
            'with a 1.3-1.6 ms pair', 'fault_24v', rail_v=20.5, hopper=0, feed_unplugged=True)
def t_fault_24v(tt, b, r):
    boot(tt, b)
    b.say('NEVER a ball with the converter bypassed: the hopper empty, no balls on the bench, the muzzle into a catch box.')
    b.do('Unplug the feed servo; feed the ESC rail 20.5 V from the bench supply through the CT power plug ONLY')
    arm(tt, b)
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_SPIN, a=1000, b=20)
    tt.wait_for(lambda: bool(tt.ev(M.EV_SAFE, t0)), 5.0)
    tt.wait(0.3)
    safe = tt.ev(M.EV_SAFE, t0)
    mx = max([max(l, rr) for t, l, rr, _a, _b in tt.wheel_log if t >= t0] or [0])
    t1 = tt.now()
    tt.cmd(M.CMD_BENCH_FEED_STEPS, a=1, b=30)          # the dial must refuse
    tt.wait(0.5)
    refused = not tt.ev(M.EV_FEED_STEP, t1) and tt.state() != 'ARMED'
    b.pendant(False)
    tt.arm_req = False
    b.do('Back to the trimmed rail on the ESCs', lambda: setattr(b.hw, 'rail_v', C.RAIL_V))
    b.do('Press the recessed trip reset', lambda: b.hw.reset_trip())
    b.pendant(True)
    tt.wait(0.2)
    b.do('Signal generator: one gate pair, 1.45 ms apart', lambda: b.hw.gate_pair(0.00145))
    tt.wait(0.3)
    latched = bool(tt.flags() & M.H_TRIP)
    b.do('Press the recessed trip reset', lambda: b.hw.reset_trip())
    b.pendant(False)
    tt.cmd(M.CMD_CLEAR_FAULTS)
    tt.wait(0.3)
    lat = safe[0][1]['b'] if safe else None
    r.reading('safe_event', {'latency_ms': lat, 'causes': [n for k, n in M.FAULT_NAMES.items()
                                                           if safe and safe[0][1]['a'] & k],
                             'erpm_at_trip': safe[0][1]['c'] * 10 if safe else None} if safe else None)
    r.reading('max_rpm_reported', mx)
    r.check('(a) SAFE on the eRPM limit', bool(safe and safe[0][1]['a'] & M.F_ERPM_LIMIT),
            bool(safe and safe[0][1]['a'] & M.F_ERPM_LIMIT), 'cause: eRPM over the limit')
    r.check('(a) within 100 ms of the first eRPM read above the limit', lat, lat is not None and lat <= 100,
            '<= 100 ms')
    r.check('(a) refuses to step the dial', refused, refused, 'no step')
    r.check('(b) trip latched on a 1.45 ms pair', latched, latched, 'latched')
    r.note(f'The eRPM never reaches the 20.5 V no-load (~28,500 rpm): the ramp passes the limit ({C.ERPM_LIMIT / C.POLE_PAIRS:,.0f} '
           'rpm) about half a second in and the turret is SAFE three telemetry reads later.')


@test('4.7', 'Release braking: 20 releases at the set speed, no ball', 'release', hopper=0)
def t_release(tt, b, r):
    boot(tt, b)
    rows = []
    for k in range(20):
        arm(tt, b)
        tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=300)
        tt.wait_for(lambda: tt.state() == 'READY', 3.0)
        tt.wait(0.5)
        t_rel = tt.now()
        rpm0 = sum(b.hw.rpm) / 2 if b.sim else None
        b.pendant(False, wait=False)
        tt.wait(0.3)
        if b.sim:
            tl = [(t, e) for t, e in b.hw.timeline if t >= t_rel]
            t_off = next(t for t, e in tl if e == 'rail_off')
            t_brake = next(t for t, e in tl if e == 'brake_on')
            last = max([e for e in [b.hw.last_edge] if e is not None and e <= t_off] or [t_rel])
            pct = 100.0 * b.hw.rpm_at(t_off + 0.050) / rpm0 if rpm0 else None
            row = {'rail_off_after_last_pulse_ms': r1((t_off - last) * 1000), 'short_after_rail_off_ms':
                   r1((t_brake - t_off) * 1000), 'speed_pct_at_rail_off_plus_50ms': r1(pct),
                   'speed_pct_at_release_plus_50ms': r1(100.0 * b.hw.rpm_at(t_rel + 0.050) / rpm0)}
        else:
            row = {'rail_off_after_last_pulse_ms': b.ask(f'rail_off_ms_{k}', 'Scope: ms from the last pulse to the '
                                                         'ESC rail off'),
                   'short_after_rail_off_ms': b.ask(f'short_ms_{k}', 'Scope: ms from the rail off to the phase short'),
                   'speed_pct_at_rail_off_plus_50ms': b.ask(f'speed_pct_{k}', 'Back-EMF: speed at +50 ms, % of before')}
        safe = tt.ev(M.EV_SAFE, t_rel)
        row['firmware_zero_throttle_ms'] = r1((safe[0][0] - t_rel) * 1000) if safe else None
        rows.append(row)
        tt.arm_req = False
        tt.wait(max(0.0, 6.0 - (tt.now() - t_rel)))
    fets = b.ask('fet_temp_c', 'IR: brake FETs after 20 releases in 2 min (C)', lambda: 38.0, stand_in=True)
    r.reading('releases', rows)
    r.reading('fet_temp_c', fets)
    worst = lambda k, f=max: f(x[k] for x in rows if x[k] is not None)  # noqa: E731
    r.check('ESC rail off after the last pulse', worst('rail_off_after_last_pulse_ms'),
            worst('rail_off_after_last_pulse_ms') <= 25.0, '<= 25 ms (the one-shot is 16-22 ms)')
    r.check('short closed after the rail off',
            [worst('short_after_rail_off_ms', min), worst('short_after_rail_off_ms')],
            5.0 <= worst('short_after_rail_off_ms', min) and worst('short_after_rail_off_ms') <= 14.0, '5-14 ms')
    r.check('speed by +50 ms (after the rail off)', worst('speed_pct_at_rail_off_plus_50ms'),
            worst('speed_pct_at_rail_off_plus_50ms') <= 5.0, '<= 5 %')
    r.check('FETs after 20 releases in 2 min', fets, fets < 60.0, '< 60 C')
    r.note('The firmware sees the release on PULSE_MON (no edge for 4 ms) and commands zero throttle at once, so AM32 '
           'brakes on stop ~16 ms before the monostable cuts the rail; the phase short then finishes the job.')


@test('4.8', 'Tyre growth at the set speed and creep after 500 balls (operator readings)', 'tyre_growth', hopper=0)
def t_tyre_growth(tt, b, r):
    boot(tt, b)
    arm(tt, b)
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=150)
    tt.wait_for(lambda: tt.state() == 'READY', 3.0)
    g = b.ask('growth_mm', 'Strobe or video at the set speed: growth of the tyre OD (mm)', lambda: 0.42, stand_in=True)
    bench_done(tt, t0, 20.0)
    disarm(tt, b)
    creep = b.ask('creep', 'After 500 balls: the tyre crept on its rim? (y/n)', lambda: False, stand_in=True, kind=bool)
    r.reading('growth_mm', g)
    r.reading('creep', creep)
    r.check('growth on the diameter', g, g <= 0.7, '<= +0.7 mm')
    r.check('no creep on the rim', creep, not creep, 'none')


@test('4.9', 'Ring temperature: 5 A for 1 h at 15 rpm (operator reading)', 'ring_temperature')
def t_ring_temperature(tt, b, r):
    boot(tt, b)
    b.say('5 A through the ring (a resistive load on the rotor side); thermocouple on the ring body and the carrier')
    pan_continuous(tt, 90.0, b.duration('panning', 3600.0))
    rise = b.ask('rise_k', 'Thermocouple: rise of the ring body over ambient after 1 h (K)', lambda: 9.5, stand_in=True)
    carrier = b.ask('carrier_rise_k', 'Thermocouple: rise of the carrier (K)', lambda: 6.0, stand_in=True)
    r.reading('ring_rise_k', rise)
    r.reading('carrier_rise_k', carrier)
    r.check('ring body rise', rise, rise <= 20.0, '<= 20 K')


@test('3.10', "The gates' light: each collector clear and cut, one clean edge per gate (operator readings)", 'gates',
      ct_unplugged=True)
def t_gate_optics(tt, b, r):
    boot(tt, b)
    rows = []
    for g in (1, 2):
        clear = b.ask(f'clear_v_{g}', f'Gate {g}: Q{7 + g} collector with the beam clear (V)', lambda: 0.3, stand_in=True)
        cut = b.ask(f'cut_v_{g}', f'Gate {g}: the collector with a 22 mm rod in the barrel (V)', lambda: 4.8, stand_in=True)
        edges = b.ask(f'edges_{g}', f'Gate {g}: edges on the output for one ball pushed through by hand', lambda: 2,
                      stand_in=True, kind=int)
        rows.append({'gate': g, 'clear_v': clear, 'cut_v': cut, 'edges': edges})
    r.reading('gates', rows)
    for x in rows:
        r.check(f"gate {x['gate']}: clear under 1 V", x['clear_v'], x['clear_v'] < 1.0, '< 1 V (else R41/R42 to 39 k)')
        r.check(f"gate {x['gate']}: cut over 4 V", x['cut_v'], x['cut_v'] > 4.0, '> 4 V')
        r.check(f"gate {x['gate']}: one clean pulse", x['edges'], x['edges'] == 2, 'one rise and one fall, no chatter')


@test('4.10', "The brake FETs while driving, and no energy into the 12 V rails (operator readings)", 'rails', hopper=0)
def t_rails(tt, b, r):
    boot(tt, b)
    arm(tt, b)
    t0 = tt.now()
    tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=100)
    tt.wait_for(lambda: tt.state() == 'READY', 3.0)
    kick = b.ask('fet_gate_peak_v', "Scope: Q2's gate, peak while the wheels run at the set speed (V)", lambda: 0.12, stand_in=True)
    tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=350, b=100)
    tt.wait(1.0)
    tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=100)
    tt.wait(1.0)
    fly = b.ask('fly_peak_v', 'Scope: 12 V FLY, highest through the step down, up and the stop (V)', lambda: 12.2, stand_in=True)
    main = b.ask('main_peak_v', 'Scope: 12 V MAIN, highest through the same (V)', lambda: 12.1, stand_in=True)
    bench_done(tt, t0, 10.0)
    disarm(tt, b)
    fets = b.ask('fet_temp_c_running', 'IR: the brake FETs after a minute at the set speed (C)', lambda: 27.0, stand_in=True)
    r.reading('fet_gate_peak_v', kick)
    r.reading('rail_peaks_v', {'fly': fly, 'main': main})
    r.check("a brake FET's gate while the ESC drives", kick, kick < 0.5, '< 0.5 V peak')
    r.check('12 V FLY through a step down and a stop', fly, fly < 13.0, '< 13 V')
    r.check('12 V MAIN through the same', main, main < 13.0, '< 13 V')
    r.check('the brake FETs stay cold while driving', fets, fets < 40.0, '< 40 C')


# ===================================================================================== 5.5 feeding
def feed_pose(tt, b, balls: int, rate: float, tilt: float = 0.0, panning: float = 0.0, chunk: int = 0) -> dict:
    """Fire `balls` at a pose and count. On the bench the hopper holds 30: `chunk` balls a burst with refills."""
    tt.aim(tt.pan() or 0.0, tilt, 90)
    tt.wait(1.0)
    t0 = tt.now()
    left = balls
    bursts = 0
    while left > 0 and bursts < 12:
        n = min(left, chunk) if chunk else left
        if bursts and not b.sim:
            b.do(f'Refill the hopper with {n} balls')
        tb = tt.now()
        if panning:
            tt.cmd(M.CMD_BENCH_FIRE_ANY_AIM, a=n, b=0, c=int(rate * 10))
            end = tb + n / rate * 3 + 20
            while not tt.ev(M.EV_BENCH_DONE, tb) and tt.now() < end:
                pan_continuous(tt, panning, 1.0, tilt=tilt)
            tt.aim(tt.pan() or 0.0, tilt, 90)
        else:
            tt.fire(n, rate, C.SET_FPS_DESIGN)
            burst_done(tt, tb, n / rate * 3 + 20)
        shots = [s for s in tt.shots_since(tb) if not s[1]['flags'] & M.S_STRAY]
        left -= len(shots)
        bursts += 1
        if not shots:
            break
        tt.wait(0.5)
    shots = [s for s in tt.shots_since(t0) if not s[1]['flags'] & M.S_STRAY]
    steps = tt.ev(M.EV_FEED_STEP, t0)
    empties = tt.ev(M.EV_FEED_EMPTY, t0)
    dur = (shots[-1][0] - shots[0][0]) if len(shots) > 1 else None
    dith = tt.ev(M.EV_DITHER, t0)
    out = {'balls': len(shots), 'steps': len(steps), 'doubles': sum(1 for _, f in shots if f['flags'] & M.S_DOUBLE),
           'jams': len(tt.ev(M.EV_FEED_JAM, t0)), 'steps_dithered': sum(1 for _, f in dith if f['a'] == 1),
           'dithers': len(dith), 'empty_after_dither': len(empties), 'lifts': len(tt.ev(M.EV_LIFT, t0)),
           'bursts': bursts, 'ball_rate_per_s': r1((len(shots) - 1) / dur, 2) if dur else None,
           'fps': stats(fps_list(shots))}
    st_ = [t for t, _ in steps]
    out['step_rate_per_s'] = r1((len(st_) - 1) / (st_[-1] - st_[0]), 2) if len(st_) > 1 else None
    out['empty_after_dither_pct'] = r1(100.0 * out['empty_after_dither'] / max(1, out['steps']), 2)
    out['jams_per_100'] = r1(100.0 * out['jams'] / max(1, out['balls']), 2)
    return out


@test('5.1', 'Feed: 100 balls per pose at 3/s (level, -25 deg, level while panning at 60 deg/s)', 'feed', hopper=320)
def t_feed(tt, b, r):
    boot(tt, b)
    b.load_balls(30)
    if b.sim:
        b.hw.hopper = 320                               # stand-in for the operator's refills
    arm(tt, b)
    poses = {'level': feed_pose(tt, b, 100, 3.0, 0.0, chunk=25),
             '-25 deg': feed_pose(tt, b, 100, 3.0, -25.0, chunk=25),
             'level, panning 60 deg/s': feed_pose(tt, b, 100, 3.0, 0.0, panning=60.0, chunk=25)}
    disarm(tt, b)
    r.reading('poses', poses)
    for k, v in poses.items():
        r.check(f'{k}: 100 balls', v['balls'], v['balls'] >= 100, '100')
        r.check(f'{k}: no double', v['doubles'], v['doubles'] == 0, '0')
        r.check(f'{k}: jams', v['jams_per_100'], v['jams_per_100'] <= 1.0, '<= 1 per 100')
        r.check(f'{k}: empty steps after the dither', v['empty_after_dither_pct'], v['empty_after_dither_pct'] <= 5.0,
                '<= 5 %')
    r.note('The panning pose uses the bench burst that does not wait for a settled aim (the settle rule is for '
           'accuracy; every safety condition stays).')


@test('5.2', 'Feed at the firmware\'s maximum rate', 'feed_max_rate', hopper=120)
def t_feed_max(tt, b, r):
    boot(tt, b)
    b.load_balls(30)
    if b.sim:
        b.hw.hopper = 120
    arm(tt, b)
    v = feed_pose(tt, b, 100, C.RATE_MAX, 0.0, chunk=25)
    disarm(tt, b)
    r.reading('requested_rate_per_s', C.RATE_MAX)
    r.reading('result', v)
    r.check('no double', v['doubles'], v['doubles'] == 0, '0')
    r.note(f'The feed is paced on gate 1: a step only after the last ball reached the barrel, and never sooner than '
           f'{C.FEED_MIN_PERIOD_S * 1000:.0f} ms after the last step (the rerun\'s 3/s maximum). The plan\'s 4/s is '
           'ruled out by the feed rerun; this test runs at the firmware\'s maximum, 3/s.')


@test('5.3', 'Feed with 50 worn and 50 damp balls, level, 3/s (information)', 'feed_worn_damp', hopper=60)
def t_feed_worn(tt, b, r):
    boot(tt, b)
    arm(tt, b)
    out = {}
    for kind in ('worn', 'damp'):
        b.load_balls(50, kind)
        out[kind] = feed_pose(tt, b, 50, 3.0, 0.0, chunk=25)
    disarm(tt, b)
    r.reading('balls', out)
    for k, v in out.items():
        r.check(f'{k}: no double', v['doubles'], v['doubles'] == 0, '0')
    r.note('Jams are logged, not judged (an information test). In --sim worn and damp balls are a stand-in: '
           'p_jam 0.02, p_fill 0.75.')


@test('5.4', 'Parked safe: dial parked, rail off, the stand shaken and knocked at tilt 0 and -25', 'parked_safe',
      hopper=30)
def t_parked(tt, b, r):
    boot(tt, b)
    rows = []
    for tilt in (0.0, -25.0):
        tt.aim(tt.pan() or 0.0, tilt, 90)
        tt.wait(1.0)
        t0 = tt.now()
        b.do(f'Tilt {tilt:.0f} deg: shake the stand by hand (~5 m/s^2) for 10 s, then knock it (~13 m/s^2) 5 times')
        tt.wait(2.0)
        rows.append({'tilt_deg': tilt, 'balls_at_the_gates': len(tt.shots_since(t0))})
    r.reading('poses', rows)
    for x in rows:
        r.check(f"tilt {x['tilt_deg']:.0f}: no ball reaches the wheels", x['balls_at_the_gates'],
                x['balls_at_the_gates'] == 0, '0')
    if b.sim:
        b.stand_ins.append('shaking')
        r.note('The simulation cannot shake the stand: the parked dial holds by construction (the physics\' feed_dyn '
               'case is the model evidence).')


@test('5.5', 'The 5-ball hopper at -25 deg: the lift-to-0 rule empties it', 'feed_last_balls', hopper=5)
def t_last_balls(tt, b, r):
    boot(tt, b)
    b.load_balls(5)
    arm(tt, b)
    tt.aim(tt.pan() or 0.0, -25.0, 90)
    tt.wait(1.0)
    t0 = tt.now()
    tt.fire(10, 3.0, C.SET_FPS_DESIGN)
    done = burst_done(tt, t0, 90.0)
    shots = [s for s in tt.shots_since(t0) if not s[1]['flags'] & M.S_STRAY]
    left = b.ask('balls_left', 'Balls left in the hopper and the chute', lambda: b.hw.hopper + b.hw.resting_balls(),
                 kind=int)
    disarm(tt, b)
    r.reading('balls_fired', len(shots))
    r.reading('lifts', len(tt.ev(M.EV_LIFT, t0)))
    r.reading('burst_end', [k for k, v in M.BURST_END.items() if done and v == done['c']])
    r.reading('balls_left', left)
    r.check('all 5 fired', len(shots), len(shots) == 5, '5')
    r.check('no ball left behind', left, left == 0, '0')
    r.check('the lift rule ran', len(tt.ev(M.EV_LIFT, t0)), len(tt.ev(M.EV_LIFT, t0)) >= 1, '>= 1 lift')


# ===================================================================================== 5.6 accuracy and the game
def flight_point(fps: float, d_m: float, rng: random.Random) -> tuple:
    """Stand-in impact point on a target d metres out (cm right, cm below the bore line): drag Cd 0.47 on a 22.8 mm,
    1.75 g ball, launch angle scatter 3.8 mrad (yaw) and 6.1 mrad (pitch) SD (the launch rerun before D68, Ø34 at 52 fps)."""
    v, x, y, vy, dt = fps * C.FPS, 0.0, 0.0, 0.0, 0.0005
    k = 0.5 * 1.2 * 0.47 * math.pi * 0.0114 ** 2 / 0.00175
    while x < d_m:
        sp = math.hypot(v, vy)
        v, vy = v - k * sp * v * dt, vy - (9.81 + k * sp * vy) * dt
        x, y = x + v * dt, y + vy * dt
    return d_m * rng.gauss(0, 0.0038) * 100, (-y + d_m * rng.gauss(0, 0.0061)) * 100


def group(tt, b, d_m: float, n: int, key: str):
    tt.wait(0.1)                                       # past the last burst's BURST_DONE, so it is not taken for this one
    t0 = tt.now()
    tt.fire(n, 2.0, C.SET_FPS_DESIGN)
    burst_done(tt, t0, 40.0)
    f = fps_list(tt.shots_since(t0))
    if b.sim:
        rng = random.Random(int(d_m * 10) + b.rig.seed)
        pts = [flight_point(v, d_m, rng) for v in f]
        cx, cy = st.mean(p[0] for p in pts), st.mean(p[1] for p in pts)
        rad = sorted(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
        r68 = rad[int(0.68 * len(rad)) - 1] if rad else None
        b.stand_ins.append(f'{key}_group')
        return {'balls': len(f), 'r68_cm': r1(r68, 2), 'centre_right_cm': r1(cx, 2), 'centre_drop_cm': r1(cy, 2),
                'fps': stats(f)}
    r68 = b.ask(f'{key}_r68_cm', f'{d_m:.0f} m: radius holding 68 % of the {n} holes (cm)')
    cy = b.ask(f'{key}_drop_cm', f'{d_m:.0f} m: the group centre below the aim point (cm)')
    return {'balls': len(f), 'r68_cm': r68, 'centre_drop_cm': cy, 'fps': stats(f)}


@test('6.1', 'Boresight the laser at 4 m', 'boresight', hopper=15)
def t_boresight(tt, b, r):
    boot(tt, b)
    b.load_balls(10)
    arm(tt, b)
    tt.laser(True)
    tt.wait(0.5)
    g = group(tt, b, 4.0, 10, 'boresight')
    off = b.ask('dot_to_group_cm', 'Laser dot to the group centre at 4 m (cm)', lambda: 1.3, stand_in=True)
    tt.laser(False)
    disarm(tt, b)
    r.reading('group', g)
    r.reading('dot_to_group_cm', off)
    r.check('dot within 2 cm of the group centre at 4 m', off, off <= 2.0, '<= 2 cm')


@test('6.2', 'Groups at 2 and 4 m: 20 shots each, level', 'groups', hopper=45)
def t_groups(tt, b, r):
    boot(tt, b)
    b.load_balls(40)
    arm(tt, b)
    out = {}
    for d, lim in ((2.0, 1.5), (4.0, 5.0)):
        b.do(f'Paper target at {d:.0f} m, aim point level with the bore')
        out[f'{d:.0f}m'] = dict(group(tt, b, d, 20, f'{d:.0f}m'), limit_cm=lim)
    disarm(tt, b)
    r.reading('groups', out)
    r.reading('drop_table_cm', {k: v['centre_drop_cm'] for k, v in out.items()})
    for k, v in out.items():
        r.check(f'{k}: 68 % radius', v['r68_cm'], v['r68_cm'] is not None and v['r68_cm'] <= v['limit_cm'],
                f"<= {v['limit_cm']} cm")
        r.check(f'{k}: 20 shots', v['balls'], v['balls'] == 20, '20')


@test('6.3', 'Aim repeatability: 20 moves to one target from both pan sides', 'aim_repeat')
def t_aim_repeat(tt, b, r):
    boot(tt, b)
    target = 40.0
    arr = []
    t90 = None
    for k in range(20):
        side = -30.0 if k % 2 == 0 else 30.0
        tt.aim(target + side, -5.0, 90)
        tt.wait(1.2)
        t0 = tt.now()
        tt.aim(target, -5.0, 90)
        tt.wait_for(lambda: abs((tt.pan() or 0) - target) < 0.05 and tt.pan_rate_at(tt.now()) == 0, 3.0)
        tt.wait(0.6)
        if b.sim:
            arr.append(wrap(b.hw.true_pan() - target))
        else:
            arr.append(b.ask(f'dot_mm_{k}', 'Laser dot from its mark at 4 m (mm, + to the right)') / 4000.0 * 57.2958)
    # a 90 deg pan within 1.2 s (the plan's 2.2 'Aim')
    tt.aim(target, -5.0, 90)
    tt.wait(1.5)
    t0 = tt.now()
    tt.aim(target + 90.0, -5.0, 90)
    ok = tt.wait_for(lambda: abs((tt.pan() or 0) - (target + 90.0)) <= C.AIM_TOL_DEG, 3.0)
    t90 = tt.now() - t0 if ok else None
    spread = (max(arr) - min(arr)) * math.pi / 180 * 1000 if arr else None
    r.reading('arrivals_mrad', [round(x * math.pi / 180 * 1000, 2) for x in arr])
    r.reading('pan_90deg_s', r1(t90, 2))
    r.check('within 3 mrad approaching in +pan', r1(spread, 2), spread is not None and spread <= 3.0,
            '<= 3 mrad (max - min of 20 arrivals)')
    r.check('a 90 deg pan', r1(t90, 2), t90 is not None and t90 <= 1.2, '<= 1.2 s to within 0.5 deg')


@test('6.4', 'Fire while panning at 10 and 90 deg/s: held above 10 deg/s', 'fire_while_panning', hopper=15)
def t_fire_panning(tt, b, r):
    boot(tt, b)
    b.load_balls(10)
    arm(tt, b)
    rows = []
    for rate in (10.0, 90.0):
        tt.aim(tt.pan() or 0.0, 0.0, 90)
        tt.wait(1.0)
        t0 = tt.now()
        tt.fire(3, 3.0, C.SET_FPS_DESIGN)
        pan_continuous(tt, rate, 3.0)
        t_stop = tt.now()
        burst_done(tt, t0, 15.0)
        sh = [s for s in tt.shots_since(t0) if not s[1]['flags'] & M.S_STRAY]
        during = [s for s in sh if s[0] < t_stop + 0.25]
        rates = [round(tt.pan_rate_at(s[0] - 0.35), 1) for s in sh]   # the pan rate when its step was commanded
        rows.append({'pan_rate_deg_s': rate, 'shots': len(sh), 'shots_while_panning': len(during),
                     'pan_rate_at_step_deg_s': rates})
    disarm(tt, b)
    r.reading('runs', rows)
    for x in rows:
        r.check(f"{x['pan_rate_deg_s']:.0f} deg/s: no shot while panning", x['shots_while_panning'],
                x['shots_while_panning'] == 0, '0')
        r.check(f"{x['pan_rate_deg_s']:.0f} deg/s: the burst fires once settled", x['shots'], x['shots'] == 3, '3')


@test('6.5', 'Knock-down: 20 g hinged plates at 2 and 4 m, 5 balls each', 'knockdown', hopper=15)
def t_knockdown(tt, b, r):
    boot(tt, b)
    b.load_balls(10)
    arm(tt, b)
    out = {}
    for d in (2.0, 4.0):
        b.do(f'Set the 20 g hinged plate at {d:.0f} m, aim at it')
        g = group(tt, b, d, 5, f'plate{d:.0f}')
        down = b.ask(f'plate_{d:.0f}m_down', f'{d:.0f} m plate down? (y/n)',
                     lambda: g['r68_cm'] is not None and g['r68_cm'] < 9.0, stand_in=True, kind=bool)
        out[f'{d:.0f}m'] = {'balls': g['balls'], 'down': down}
    disarm(tt, b)
    r.reading('plates', out)
    for k, v in out.items():
        r.check(f'{k} plate down', v['down'], v['down'], 'down')


@test('6.6', 'Temperature: 100 balls in 2 min, then 10 min at speed', 'temperature', hopper=110)
def t_temperature(tt, b, r):
    boot(tt, b)
    b.load_balls(30)
    if b.sim:
        b.hw.hopper = 110
    arm(tt, b)
    t0 = tt.now()
    tt.fire(100, 0.85, C.SET_FPS_DESIGN)
    burst_done(tt, t0, 200.0)
    t1 = tt.now()
    tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=int(b.duration('at_speed', 600.0) * 10))
    bench_done(tt, t1, b.duration('at_speed', 600.0) + 10)
    esc = [max(a, c) for t, _l, _r, a, c in tt.wheel_log if t >= t0]
    hw = b.hw if b.sim else None
    vals = {}
    for key, prompt, fn in (('esc_c', 'IR: hottest ESC (C)', lambda: round(max(hw.temp['esc']), 1)),
                            ('motor_c', 'IR: hottest motor (C)', lambda: round(max(hw.temp['motor']), 1)),
                            ('regulator_c', 'IR: the 12 V FLY regulator (C)', lambda: round(hw.temp['reg'], 1)),
                            ('servo_c', 'IR: hottest servo (C)', lambda: 41.0)):
        vals[key] = b.ask(key, prompt, fn, stand_in=True)
    disarm(tt, b)
    r.reading('balls', len(fps_list(tt.shots_since(t0))))
    r.reading('esc_telemetry_max_c', max(esc) if esc else None)
    r.reading('ir', vals)
    r.check('ESCs', vals['esc_c'], vals['esc_c'] <= 80, '<= 80 C')
    r.check('motors', vals['motor_c'], vals['motor_c'] <= 70, '<= 70 C')
    r.check('flywheel regulator', vals['regulator_c'], vals['regulator_c'] <= 60, '<= 60 C')
    r.check('servos', vals['servo_c'], vals['servo_c'] <= 60, '<= 60 C')


@test('6.7', 'Safety-line release during feeding: 20 releases at random points of 8-ball bursts', 'release_feeding',
      hopper=200)
def t_release_feeding(tt, b, r):
    boot(tt, b)
    b.load_balls(30)
    if b.sim:
        b.hw.hopper = 200
    rng = random.Random(b.rig.seed if b.sim else 1)
    rows = []
    for k in range(20):
        arm(tt, b)
        t0 = tt.now()
        tt.fire(8, 3.0, C.SET_FPS_DESIGN)
        tt.wait_for(lambda: bool(tt.shots_since(t0)), 5.0)
        tt.wait(rng.uniform(0.0, 2.0))
        t_rel = tt.now()
        b.pendant(False, wait=False)
        tt.wait(1.5)
        after = [(s[0] - t_rel, s[1]['fps_d'] / 10.0) for s in tt.shots_since(t_rel)]
        row = {'release_s_into_burst': round(t_rel - t0, 2), 'balls_after_release': len(after),
               'fps_after_release': [round(f, 1) for _, f in after]}
        if b.sim:
            row['nip_ms_after_release'] = [round((x['t'] - t_rel) * 1000) for x in b.hw.launched if x['t'] >= t_rel]
            row['resting_at_the_nip'] = b.hw.resting_balls()
        else:
            row['where_resting'] = b.ask(f'resting_{k}', 'Where did any resting ball end? (text)', kind=str)
        tt.arm_req = False
        tt.wait(0.5)
        # the next arm pulls a resting ball through at a few fps (the stray ball)
        if b.sim and b.hw.resting_balls():
            arm(tt, b)
            t2 = tt.now()
            tt.cmd(M.CMD_BENCH_SPIN_SPEED, a=int(C.SET_FPS_DESIGN * 10), b=10)
            bench_done(tt, t2, 5.0)
            row['stray_fps'] = [s[1]['fps_d'] / 10.0 for s in tt.shots_since(t2)]
            tt.arm_req = False
            b.pendant(False)
        rows.append(row)
    worst = max([f for x in rows for f in x['fps_after_release']] or [0.0])
    late = [f for x in rows for (dt, f) in zip(x.get('nip_ms_after_release', []), x['fps_after_release']) if dt > 15]
    r.reading('releases', rows)
    r.reading('fastest_after_release_fps', worst)
    if b.sim:
        r.reading('fastest_reaching_the_nip_15ms_after_release_fps', max(late) if late else None)
    r.check('no ball above 20 fps after a release', worst, worst <= C.AFTER_RELEASE_FPS, '<= 20 fps')
    r.note('A ball already at the nip, or reaching it within ~10 ms of the release, leaves fast whatever the brake '
           'does (the physics\' own table: 36 fps at 0-10 ms). The firmware cuts the throttle on the PULSE_MON gap '
           '(4 ms) and AM32 brakes on stop before the rail drops at ~20 ms, which narrows that window but cannot close '
           'it.')


@test('6.8', 'Mock lidar: the depression table loaded; barrel and balls clear at every pan', 'mock_lidar')
def t_mock_lidar(tt, b, r):
    boot(tt, b)
    table, lidar, used = None, {}, 'exports/turret/lidar/lidar.json firmware_table'
    src = R / 'exports' / 'turret' / 'lidar' / 'lidar.json'
    if src.exists():
        try:
            d = json.loads(src.read_text())
            table = [(float(x['pan_deg']), float(x['min_tilt_deg'])) for x in d['firmware_table']]
            lidar = d.get('lidar') or {}
        except (KeyError, ValueError):
            table = None
    if not table:                                      # the firmware's built-in robot table, made for the same lidar
        table, lidar, used = list(C.ROBOT_DEPRESSION), {}, 'config.ROBOT_DEPRESSION'
    x = lidar.get('centre_x_mm', C.ROBOT_DEPRESSION_FOR['lidar_to_pan_mm'])
    top = lidar.get('top_above_tm_mm', C.ROBOT_DEPRESSION_FOR['lidar_top_above_tm_mm'])
    r.reading('table_source', used)
    r.reading('lidar_centre_ahead_mm', x)
    r.reading('lidar_top_above_tm_mm', top)
    tt.config(M.CF_CLEAR, a=1)
    for i, (p, m) in enumerate(table):
        tt.config(M.CF_DEPRESSION, index=i, a=int(round(p * 10)), b=int(round(m * 100)))
    tt.wait(0.3)
    cfg = C.Config(depression=table)
    rows = []
    b.do(f'Mock lidar (Ø103 x 72 cylinder, {x:.0f} mm ahead, top {top:.1f} mm above the TM face) in place')
    for p in range(0, 360, 10):
        tt.aim(float(p), -25.0, 90)
        tt.wait(1.2)
        tilt = tt.tilt()
        lim = cfg.min_tilt(float(p))
        clear = b.ask(f'clear_{p}', f'Pan {p}: barrel and ball path >= 10 mm from the mock lidar? (y/n)',
                      lambda: tilt is not None and tilt >= lim - 0.5, stand_in=True, kind=bool)
        rows.append({'pan_deg': p, 'tilt_deg': tilt, 'table_min_deg': lim, 'clear': clear})
    tt.config(M.CF_CLEAR, a=1)
    r.reading('rows', rows)
    r.reading('table_rows', len(table))
    worst = min(x['tilt_deg'] - x['table_min_deg'] for x in rows if x['tilt_deg'] is not None)
    r.check('the tilt never below the table', round(worst, 2), worst >= -0.5, '>= table - 0.5 deg at every pan')
    r.check('clear at every pan', sum(1 for x in rows if not x['clear']), all(x['clear'] for x in rows), '10 mm')


# ===================================================================================== running
def run_test(entry, args, answers) -> dict:
    tid, title, file, sim_opts, fn = entry
    rig = None
    if args.sim:
        import sim_turret
        seed = args.seed * 1000 + int(tid.replace('.', ''))
        opts = {k: v for k, v in sim_opts.items() if k not in ('ct_unplugged', 'feed_bench_power', 'feed_unplugged')}
        rig = sim_turret.SimRig(seed=seed, **opts)
        hw = rig.hw
        if sim_opts.get('ct_unplugged'):
            hw.esc_unplugged = True
            hw.feed_unplugged = True
        if sim_opts.get('feed_bench_power'):
            hw.feed_unplugged = False
            hw.feed_bench_power = True
            hw.feed_servo.set_power(True, 0.0)
        if sim_opts.get('feed_unplugged'):
            hw.feed_unplugged = True
        link = SimLink(rig)
    else:
        link = args.link
    tt = Turret(link)
    b = Bench(tt, rig, answers, tid, quiet=args.quiet)
    res = Result(tid, title, file)
    t_wall = time.time()
    t_sim0 = tt.now()
    if not args.sim:
        print(f'\n== {tid} {title}')
    try:
        if tid not in ('3.1', '3.5'):
            boot(tt, b)
        fn(tt, b, res)
        err = None
    except Exception as e:  # a test that cannot finish is a failed test, recorded as such
        err = f'{type(e).__name__}: {e}'
        res.check('the test ran to the end', err, False, 'no error')
    finally:
        tt.arm_req = False
    out = {'test': tid, 'title': title, 'plan': 'docs/turret-prototype-plan.md section 5', 'mode':
           'sim' if args.sim else 'bench', 'date': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
           'pass': res.passed, 'checks': res.checks, 'readings': res.readings, 'notes': res.notes}
    if args.sim:
        out['sim'] = {'seed': rig.seed, 'simulated_s': round(tt.now() - t_sim0, 1),
                      'wall_s': round(time.time() - t_wall, 1),
                      'stand_ins': sorted(set(b.stand_ins)), 'shortened': b.scaled,
                      'warning': 'simulated turret (firmware/turret/sim_turret.py): not a bench reading'}
    out['firmware'] = {'build': C.BUILD, 'servo_baud': C.SERVO_BAUD, 'motor': C.MOTOR, 'kv': C.MOTOR_KV,
                       'pole_pairs': C.POLE_PAIRS, 'erpm_limit': C.ERPM_LIMIT, 'tyre_mm': C.TYRE_DESIGN_MM,
                       'set_rpm_95fps': round(C.set_rpm(C.SET_FPS_DESIGN, C.TYRE_DESIGN_MM)), 'ramp_s': C.RAMP_S}
    if err:
        out['error'] = err
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{file}.json').write_text(json.dumps(out, indent=1, default=str) + '\n')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--sim', action='store_true', help='run against the simulated turret (writes to bench/sim/)')
    ap.add_argument('--can', default=None, help="python-can channel, e.g. socketcan:can0")
    ap.add_argument('--tests', default='all', help='comma list of test numbers, or all')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default=None)
    ap.add_argument('--answers', default=None, help='JSON of readings for an unattended bench run')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    if args.list:
        for tid, title, file, _o, _f in TESTS:
            print(f'{tid:5s} {file + ".json":28s} {title}')
        return 0
    if not args.sim and not args.can:
        ap.error('--sim or --can CHANNEL')
    want = None if args.tests == 'all' else set(args.tests.split(','))
    sel = [e for e in TESTS if want is None or e[0] in want]
    args.out = args.out or str(SIM_OUT if args.sim else BENCH_OUT)
    if args.sim and Path(args.out).resolve() == BENCH_OUT.resolve():
        ap.error('simulated results never go to exports/turret/bench/ itself')
    args.link = None if args.sim else CanLink(args.can)
    answers = json.loads(Path(args.answers).read_text()) if args.answers else {}
    index = []
    for e in sel:
        res = run_test(e, args, answers)
        line = {'test': res['test'], 'file': e[2] + '.json', 'pass': res['pass'],
                'failed': [c['check'] for c in res['checks'] if not c['pass']]}
        if args.sim:
            line['simulated_s'] = res['sim']['simulated_s']
        index.append(line)
        print(f"{res['test']:5s} {'pass' if res['pass'] else 'FAIL':4s} {e[2]}"
              + (f"  ({len(line['failed'])} failed: {'; '.join(line['failed'][:3])})" if line['failed'] else ''))
    if want is None:
        Path(args.out, 'index.json').write_text(json.dumps({'mode': 'sim' if args.sim else 'bench', 'tests': index},
                                                           indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
