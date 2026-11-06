"""The feed: the dial on its STS3215 (bus ID 3), stepped 45 deg per ball (docs/turret-firmware.md section 5).

Three layers, each usable alone (test_feed.py drives them against a simulated servo):

  FeedPort    the bus side: ping, (re)initialise, read position and load, write one relative step;
  FeedDriver  one dial move at a time: step, settle, jam, reverse, retry, dither; the servo leaving the bus when the
              12 V FEED rail is cut on a release, and its re-initialisation when it answers again on the next arm;
  Burst       a burst of balls at up to 3/s, paced on gate 1: a step only after the last ball reached the barrel, the
              dither (twice at most) when it does not, the lift to level below -12 deg, the hopper declared empty.

The servo is in step mode (mode 3): each move is one relative step, computed from the servo's 12-bit absolute angle,
so the pockets' positions never drift and the dial can step forward for ever. A relative step is never re-sent
blindly (a lost reply may hide an applied step, and a doubled step can drop two balls): an unacknowledged step is
re-sent only if the position has not moved 40 ms later.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import config as C
import sts
from homing import unwrap_step


class FeedPort:
    """The feed servo on the firmware's bus master."""

    def __init__(self, master: sts.Master, sid: int = C.ID_FEED):
        self.m, self.sid = master, sid

    def ping(self) -> bool:
        return self.m.ping(self.sid, count=False)

    def init(self):
        """Verify the EEPROM (step mode), write the RAM registers (torque limit, acceleration, speed), enable torque.
        Returns the raw position, 'config' if the EEPROM is wrong (the firmware never writes EEPROM: a release can cut
        the rail mid-write), or None if the servo stopped answering."""
        e = self.m.read_eeprom(self.sid)
        if e is None:
            return None
        if e['mode'] != C.MODE_STEP:
            return 'config'
        ok = (self.m.write(self.sid, sts.R_TORQUE_LIMIT, sts.u16(C.SERVO_TORQUE_LIMIT))
              and self.m.write(self.sid, sts.R_ACC, bytes([C.FEED_ACC]))
              and self.m.write(self.sid, sts.R_GOAL_SPEED, sts.u16(C.FEED_SPEED_CPS)))
        r = self.m.read_pos(self.sid)
        if not ok or r is None or not self.m.write(self.sid, sts.R_TORQUE_ENABLE, b'\x01'):
            return None
        return r

    def read(self) -> Optional[Tuple[int, int, int]]:
        return self.m.read_pos_speed_load(self.sid)

    def step(self, rel: int) -> Optional[bool]:
        return self.m.write_once(self.sid, sts.R_GOAL_POS, sts.sm16(int(rel)))


OFFLINE, INIT, PARKED, MOVING, FAULT = 'OFFLINE', 'INIT', 'PARKED', 'MOVING', 'FAULT'


class FeedDriver:
    """One dial move at a time. Call update(t) at 1 kHz; it reads the servo at 200 Hz while moving (20 Hz parked) and
    returns events: ('online',), ('lost',), ('offline',), ('settled', step_no, settle_s, load_peak, load_mean, clean),
    ('jam', step_no, cause, in_row, s since the step's command), ('reversed', step_no), ('fault', 'jams'|'config'),
    ('dither_done',)."""

    def __init__(self, port, zero: int = C.FEED_ZERO_COUNT, ref: str = C.STEP_REF):
        self.port, self.zero, self.ref = port, zero, ref
        self.state = OFFLINE
        self.total: Optional[float] = None       # unwrapped counts since the servo last booted
        self.last_raw: Optional[int] = None
        self.goal_total: Optional[float] = None  # what the servo was last told (for a 'goal'-referenced step mode)
        self.parked: Optional[float] = None      # the pocket position the dial rests at
        self.load = 0
        self.move: Optional[dict] = None
        self.step_no = 0
        self.jams_in_row = 0
        self.fails = 0
        self.next_read = 0.0
        self.next_ping = 0.0
        self.fault = None
        self.stats = {'steps': 0, 'settled': 0, 'clean': 0, 'jams': 0, 'jam_timeout': 0, 'jam_load': 0,
                      'reverses': 0, 'dithers': 0, 'resent': 0, 'lost': 0, 'reinit': 0, 'interrupted': 0,
                      'settle_s': [], 'load_mean': [], 'load_peak': []}

    # ------------------------------------------------------------------ requests from the firmware
    def request_step(self, t: float) -> bool:
        if self.state != PARKED:
            return False
        self.step_no += 1
        self.stats['steps'] += 1
        self._start('step', self.parked + C.FEED_STEP_COUNTS, t, step_t0=t, clean=True)
        return True

    def request_dither(self, t: float) -> bool:
        if self.state != PARKED:
            return False
        self.stats['dithers'] += 1
        self._start('dither_back', self.total - C.FEED_DITHER_COUNTS, t, home=self.total)
        return True

    def power_lost(self, t: float, events: Optional[list] = None):
        """ARM fell: the 12 V FEED rail is being cut. Forget the servo; it re-initialises when it answers again."""
        if self.state == OFFLINE:
            return
        if self.move is not None and self.move['kind'] in ('step', 'retry', 'reverse'):
            self.stats['interrupted'] += 1
        self.state, self.move, self.total = OFFLINE, None, None
        self.next_ping = t + C.FEED_PING_S
        if events is not None:
            events.append(('offline',))

    def abort(self, t: float):
        """Stop where it is (SAFE with the rail still up). The next step completes the interrupted one."""
        if self.state == MOVING:
            self._stop()
            if self.move['kind'] in ('step', 'retry', 'reverse'):
                self.stats['interrupted'] += 1
            self.move = None
            self.state = PARKED

    def clear_fault(self):
        if self.state == FAULT and self.fault == 'jams':
            self.state, self.fault, self.jams_in_row = PARKED, None, 0

    @property
    def online(self) -> bool:
        return self.state in (PARKED, MOVING, FAULT)

    def dial_deg(self) -> Optional[float]:
        return None if self.total is None else ((self.total - self.zero) % C.COUNTS) * C.DEG_PER_COUNT

    # ------------------------------------------------------------------ the loop
    def update(self, t: float) -> List[tuple]:
        ev: List[tuple] = []
        if self.state == OFFLINE:
            if t >= self.next_ping:
                self.next_ping = t + C.FEED_PING_S
                if self.port.ping():
                    self.state = INIT
            if self.state != INIT:
                return ev
        if self.state == INIT:
            r = self.port.init()
            if r is None:
                self.state = OFFLINE
                return ev
            if r == 'config':
                self.state, self.fault = FAULT, 'config'
                ev.append(('fault', 'config'))
                return ev
            self.stats['reinit'] += 1
            self.total = self.goal_total = float(r)
            self.last_raw = r
            off = (self.total - self.zero) % C.FEED_STEP_COUNTS
            # rest where it is: the pocket at or behind (or just ahead, inside the settle band); never move unasked
            self.parked = self.total - off if off <= C.FEED_STEP_COUNTS - C.FEED_SETTLE_COUNTS else \
                self.total - off + C.FEED_STEP_COUNTS
            self.state, self.fails, self.next_read = PARKED, 0, t
            ev.append(('online',))
            return ev
        if t < self.next_read:
            return ev
        self.next_read = t + (1.0 / 200.0 if self.state == MOVING else 1.0 / 20.0)
        r = self.port.read()
        if r is None:
            self.fails += 1
            if self.fails >= C.FEED_LOST_READS:
                self.stats['lost'] += 1
                self.power_lost(t)
                ev.append(('lost',))
            return ev
        self.fails = 0
        raw, _speed, load = r
        self.total += unwrap_step(self.last_raw, raw)
        self.last_raw, self.load = raw, load
        if self.state == MOVING:
            self._evaluate(t, ev)
        return ev

    # ------------------------------------------------------------------ moves
    def _stop(self):
        """Hold where it is: a zero step (or, for a goal-referenced step mode, the step back to the present)."""
        self.port.step(0 if self.ref == 'present' else int(round(self.total - self.goal_total)))
        self.goal_total = self.total

    def _start(self, kind: str, target: float, t: float, **kw):
        base = self.total if self.ref == 'present' else self.goal_total
        acked = self.port.step(int(round(target - base)))
        self.goal_total = target
        self.next_read = min(self.next_read, t + 0.005)
        # 'not settled in 300 ms' is per 45 deg step; a retry after a reverse travels up to 65 deg and gets as long
        timeout = C.FEED_STEP_TIMEOUT_S * max(1.0, abs(target - self.total) / C.FEED_STEP_COUNTS)
        m = {'kind': kind, 'target': target, 't0': t, 'from': self.total, 'base': base, 'acked': acked is True,
             'resent': 0, 'load_since': None, 'loads': [], 'peak': 0, 'timeout': timeout}
        m.update(kw)
        if self.move is not None:                       # carry the step's own start time and status through a jam
            for k in ('step_t0', 'clean', 'resume', 'home'):
                if k not in m and k in self.move:
                    m[k] = self.move[k]
        self.move, self.state = m, MOVING

    def _evaluate(self, t: float, ev: list):
        m = self.move
        err = m['target'] - self.total
        el = t - m['t0']
        m['peak'] = max(m['peak'], abs(self.load))
        if el >= C.FEED_JAM_LOAD_IGNORE_S:
            m['loads'].append(abs(self.load))
        if abs(err) <= C.FEED_SETTLE_COUNTS:
            self._finish(t, ev)
            return
        if not m['acked'] and el >= 0.040 and abs(self.total - m['from']) < 10 and m['resent'] < 2:
            m['resent'] += 1                            # the step was not applied: send it again from where it is
            self.stats['resent'] += 1
            base = self.total if self.ref == 'present' else m['base']
            m['acked'] = self.port.step(int(round(m['target'] - base))) is True
            m['t0'] = t
            return
        if m['kind'] == 'dither_back':
            if el > m['timeout']:                       # a stuck dither just returns
                self._start('dither_fwd', m['home'], t)
            return
        if el >= C.FEED_JAM_LOAD_IGNORE_S and abs(self.load) >= C.FEED_JAM_LOAD:
            if m['load_since'] is None:
                m['load_since'] = t
            elif t - m['load_since'] >= C.FEED_JAM_LOAD_S:
                self._jam(t, 'load', ev)
                return
        else:
            m['load_since'] = None
        if el > m['timeout']:
            self._jam(t, 'timeout', ev)

    def _finish(self, t: float, ev: list):
        m = self.move
        k = m['kind']
        if k in ('step', 'retry'):
            self.parked = m['target']
            self.jams_in_row = 0
            settle = t - m['step_t0']
            lm = sum(m['loads']) / len(m['loads']) if m['loads'] else float(m['peak'])
            self.stats['settled'] += 1
            self.stats['clean'] += 1 if m['clean'] else 0
            self.stats['settle_s'].append(round(settle, 4))
            self.stats['load_mean'].append(round(lm, 1))
            self.stats['load_peak'].append(m['peak'])
            ev.append(('settled', self.step_no, settle, m['peak'], lm, m['clean']))
            self.move, self.state = None, PARKED
        elif k == 'reverse':
            ev.append(('reversed', self.step_no))
            self._start(m['resume'], m['resume_target'], t)
        elif k == 'dither_back':
            self._start('dither_fwd', m['home'], t)
        else:                                           # dither_fwd
            self.move, self.state = None, PARKED
            ev.append(('dither_done',))

    def _jam(self, t: float, cause: str, ev: list):
        m = self.move
        self.jams_in_row += 1
        self.stats['jams'] += 1
        self.stats['jam_' + cause] += 1
        ev.append(('jam', self.step_no, cause, self.jams_in_row, t - m.get('step_t0', m['t0'])))
        if self.jams_in_row >= C.FEED_MAX_JAMS:
            self._stop()
            self.move, self.state, self.fault = None, FAULT, 'jams'
            ev.append(('fault', 'jams'))
            return
        if m['kind'] == 'reverse':                      # stuck both ways: try the move it was clearing for again
            self._start(m['resume'], m['resume_target'], t, clean=False)
            return
        resume = 'retry' if m['kind'] in ('step', 'retry') else m['kind']
        self.stats['reverses'] += 1
        self._start('reverse', self.total - C.FEED_REVERSE_COUNTS, t, resume=resume, resume_target=m['target'],
                    clean=False)


class Burst:
    """A burst of `balls` at up to `rate` balls/s, paced on the chronograph. The feed rerun found balls hanging in the
    exit hole through their own step (tilt -25 deg, panning at 90-150 deg/s, a 15 Hz shake), and a step on top of a
    hung ball releases two. So there is one ball in the hole at a time, and a full step is never commanded while a ball
    may still be in it.

    A step opens a window that lasts until the next step's command: the first GATE_1 edge in it is the step's ball, a
    second one is a double. The next step needs the window's ball seen at GATE_1 (it has left the hole and the chute),
    the dial parked, the aim allowed (the firmware's can_move), and FEED_MIN_PERIOD_S (335 ms) and 1/rate since the
    last step's command. With no GATE_1 within FEED_GATE_WAIT_S (400 ms) of the command (or of a late settle, after a
    jam's retry) the dial does not step on: it dithers +-10 deg to free a hanging or bridged ball and waits 400 ms more.
    Two dithers without a ball count an empty step, and the dial steps on. Below LIFT_BELOW_DEG the second dither of a
    step is preceded by a lift to level for LIFT_S (the last balls pool on the baffle; the first dither alone frees a
    bridged or hung ball, so the lift costs time only when that fails). HOPPER_EMPTY_STEPS empty steps in a row end
    the burst: the hopper is empty.

    The firmware calls update() every tick (it returns 'lift' while the barrel should be level) and on_gate1() for every
    GATE_1 edge. `events` collects ('dither', n), ('empty',), ('lift',), ('double',) for the host."""

    def __init__(self, balls: int, rate: float, t0: float):
        self.req = balls
        self.min_period = max(C.FEED_MIN_PERIOD_S, 1.0 / max(0.5, min(C.RATE_MAX, rate)))
        self.balls = self.steps = self.empty = self.dithers = self.recovered = 0
        self.doubles = self.unexpected = self.lifts = self.consecutive_empty = 0
        self.phase = 'ready'                  # 'ready' | 'wait' (for the ball) | 'lift' | 'dither_due'
        self.last_step = t0 - 10.0            # the last step's command
        self.deadline = 0.0                   # GATE_1 is expected before this
        self.window_open = False
        self.window_ball = False
        self.dithers_here = 0
        self.lifted_here = False
        self.lift_until = 0.0
        self.moving = False
        self.done: Optional[str] = None
        self.cmd_times: List[Tuple[float, str]] = []    # (time, 'step' | 'dither'): the cadence actually achieved
        self.events: List[tuple] = []

    def on_gate1(self, t: float) -> str:
        self.balls += 1
        if self.window_open and not self.window_ball:
            self.window_ball = True
            self.consecutive_empty = 0
            if self.dithers_here:
                self.recovered += 1
            return 'ball'
        if self.window_open:
            self.doubles += 1
            self.events.append(('double',))
            return 'double'
        self.unexpected += 1
        return 'unexpected'

    def update(self, t: float, feed: FeedDriver, can_move: bool, tilt_deg: float) -> Optional[str]:
        if self.done:
            return None
        if feed.state == FAULT:
            self.done = 'feed fault'
            return None
        if self.moving and feed.state == PARKED:          # a move ended: a late settle (a jam's retry) gets its wait
            self.deadline = max(self.deadline, t + C.FEED_AFTER_SETTLE_WAIT_S)
        self.moving = feed.state == MOVING
        if self.phase == 'lift':
            if t < self.lift_until:
                return 'lift'
            self.phase, self.lifted_here = 'dither_due', True
        if self.phase == 'wait':
            if self.window_ball:
                self.phase = 'ready'
            elif t >= self.deadline and feed.state == PARKED:
                if self.dithers_here >= C.FEED_MAX_DITHERS:
                    self.empty += 1
                    self.consecutive_empty += 1
                    self.events.append(('empty',))
                    self.window_open = False
                    self.phase = 'ready'
                elif tilt_deg < C.LIFT_BELOW_DEG and self.dithers_here >= 1 and not self.lifted_here:
                    self.phase, self.lift_until = 'lift', t + C.LIFT_S
                    self.lifts += 1
                    self.events.append(('lift',))
                    return 'lift'
                else:
                    self.phase = 'dither_due'
        if self.phase == 'dither_due':
            if can_move and feed.state == PARKED and feed.request_dither(t):
                self.dithers += 1
                self.dithers_here += 1
                self.events.append(('dither', self.dithers_here))
                self.cmd_times.append((t, 'dither'))
                self.deadline = t + C.FEED_GATE_WAIT_S
                self.phase = 'wait'
            return None
        if self.phase != 'ready':
            return None
        if self.consecutive_empty >= C.HOPPER_EMPTY_STEPS:
            self.done = 'hopper empty'
            return None
        if self.balls >= self.req:
            if feed.state == PARKED and t >= self.last_step + C.FEED_MIN_PERIOD_S:   # a late double still counts
                self.done = 'complete'
            return None
        if not can_move or feed.state != PARKED or t < self.last_step + self.min_period:
            return None
        if feed.request_step(t):
            self.steps += 1
            self.last_step = t
            self.cmd_times.append((t, 'step'))
            self.window_open, self.window_ball = True, False
            self.dithers_here, self.lifted_here = 0, False
            self.deadline = t + C.FEED_GATE_WAIT_S
            self.phase = 'wait'
        return None

    def summary(self) -> dict:
        return {'balls': self.balls, 'steps': self.steps, 'empty_steps': self.empty, 'dithers': self.dithers,
                'recovered_by_dither': self.recovered, 'doubles': self.doubles, 'unexpected': self.unexpected,
                'lifts': self.lifts, 'done': self.done}
