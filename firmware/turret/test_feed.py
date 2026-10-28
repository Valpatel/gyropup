"""The feed driver's unit test (docs/turret-prototype-plan.md T7): firmware/turret/feed.py against a simulated STS3215
(sim_servo.py) on a simulated bus, through the real packet code (sts.py). Writes exports/turret/firmware/feed.json.

    .venv/bin/python firmware/turret/test_feed.py [--seed 1] [--out DIR]

Cases:
  stepping_3hz_jam    30 steps at 3/s on a loaded dial; a jam injected on step 10 (the dial blocked 10-35 deg into the
                      step) that the 20 deg reverse clears: detected, reversed, retried, recovered; every other step
                      settled within 23 counts in <= 250 ms; the dial 30 pockets on; no step written twice
  jam_fault           a jam that never clears: three in a row stop feeding (fault), the dial holds
  jam_by_load         a jam early in the step is caught by the load reading before the 300 ms timeout
  drop_off            the 12 V FEED rail cut mid-step (a release) and back: the servo leaves the bus, answers again
                      after its boot, is re-initialised (torque limit, acceleration, speed, torque on) and steps again;
                      the same seen only through failed reads (no ARM signal)
  lost_replies        a step whose reply is lost but which was applied is not re-sent (no double step); a step that
                      was really lost is re-sent after 40 ms
  step_time           the 45 deg step with the configured speed and acceleration (<= 250 ms) and with the ACC
                      register at its highest ramp (254): why ACC is left at 0
  burst               the gate-paced Burst at 3/s (4/s asked: held to 3/s, 335 ms step to step); hung balls freed
                      by the dither, never by the next step (no double); the lift to level with 5 balls at -25 deg;
                      an empty step only after two dithers; the hopper declared empty
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import feed as F  # noqa: E402
import sts  # noqa: E402
from sim_servo import SimBus, SimServo  # noqa: E402

R = Path(__file__).resolve().parents[2]
DT = 0.001


class Rig:
    """A feed servo on a bus with a dial on it: jams are blocks on the dial's forward travel."""

    def __init__(self, seed: int, start: float = 0.0, p_corrupt: float = 0.0, ref: str = 'present'):
        self.rng = random.Random(seed)
        self.t = 0.0
        self.servo = SimServo(C.ID_FEED, mode=C.MODE_STEP, pos=start, rng=self.rng, p_corrupt=p_corrupt, ref=ref)
        self.servo.load_factor = 0.95            # a full hopper on the dial (est)
        self.servo.extra_load = 60
        self.bus = SimBus([self.servo], lambda: self.t)
        self.master = sts.Master(self.bus.txn, retries=C.SERVO_RETRIES)
        self.port = F.FeedPort(self.master)
        self.drv = F.FeedDriver(self.port, zero=0, ref=ref)
        self.events = []
        self.jam = None                          # {'at': counts, 'clear_below': counts, 'onset': t}
        self.step_writes = 0
        self.lose_next_reply = None              # 'applied' | 'dropped'
        self.onset = None                        # when the dial first met an injected jam
        orig = self.bus.txn

        def txn(pkt):
            p = sts.parse(pkt)
            is_step = p is not None and p[1] == sts.WRITE and p[2][:1] == bytes([sts.R_GOAL_POS])
            if is_step and self.lose_next_reply:
                kind, self.lose_next_reply = self.lose_next_reply, None
                if kind == 'applied':
                    orig(pkt)
                    self.step_writes += 1
                return None
            r = orig(pkt)
            if is_step and r is not None:
                self.step_writes += 1
            return r
        self.master.txn = txn

    def run_until(self, t_end: float, on_tick=None):
        while self.t < t_end:
            if self.jam is not None:
                j = self.jam
                if self.servo.pos >= j['at'] - 1 and j.get('onset') is None:
                    j['onset'] = self.onset = self.t
                if self.servo.pos < j['clear_below'] and j.get('onset') is not None and j['clears']:
                    self.jam, self.servo.blocked_hi = None, None
            self.servo.advance(DT)
            for e in self.drv.update(self.t):
                self.events.append((round(self.t, 4),) + tuple(e))
            if on_tick:
                on_tick(self)
            self.t += DT

    def inject_jam(self, into_deg: float, clears: bool = True):
        """Block the dial `into_deg` past the pocket it is leaving; a reverse to 10 deg short of the block clears it."""
        at = self.drv.parked + into_deg / C.DEG_PER_COUNT
        self.jam = {'at': at, 'clear_below': at - 10.0 / C.DEG_PER_COUNT, 'clears': clears}
        self.servo.blocked_hi = at


def boot(rig: Rig):
    rig.run_until(0.2)
    assert rig.drv.state == F.PARKED, rig.drv.state


def stepping(rig: Rig, n: int, rate: float, jam_on=None, jam_deg=20.0, clears=True, t_max=60.0):
    """Request a step every 1/rate s while parked; inject a jam on step `jam_on`."""
    period = 1.0 / rate
    state = {'next': rig.t, 'requested': 0}

    def tick(r: Rig):
        if state['requested'] < n and r.drv.state == F.PARKED and r.t >= state['next']:
            if jam_on is not None and state['requested'] + 1 == jam_on:
                r.inject_jam(jam_deg, clears)
            if r.drv.request_step(r.t):
                state['requested'] += 1
                state['next'] = max(state['next'] + period, r.t)
    t_end = rig.t + t_max
    start_t = rig.t
    while rig.t < t_end and (state['requested'] < n or rig.drv.state == F.MOVING):
        if rig.drv.state == F.FAULT:
            break
        rig.run_until(rig.t + 0.01, tick)
    return rig.t - start_t


def case_stepping_3hz_jam(seed):
    rig = Rig(seed, start=rig_start(seed))
    boot(rig)
    p0 = rig.drv.parked
    pos0 = rig.servo.pos
    dur = stepping(rig, 30, 3.0, jam_on=10, jam_deg=rig.rng.uniform(10.0, 35.0))
    s = rig.drv.stats
    jams = [e for e in rig.events if e[1] == 'jam']
    settled = [e for e in rig.events if e[1] == 'settled']
    clean_times = [e[3] for e in settled if e[6]]
    jam_settle = [e[3] for e in settled if not e[6]]
    det = (jams[0][0] - rig.onset) if jams and rig.onset is not None else None
    moved = (rig.servo.pos - pos0) * C.DEG_PER_COUNT
    out = {'steps': s['steps'], 'settled': s['settled'], 'clean': s['clean'], 'jams': s['jams'],
           'jam_causes': [e[3] for e in jams], 'reverses': s['reverses'], 'duration_s': round(dur, 2),
           'rate_per_s': round(30 / dur, 2), 'settle_ms_clean_max': round(1000 * max(clean_times), 1),
           'settle_ms_clean_mean': round(1000 * sum(clean_times) / len(clean_times), 1),
           'jammed_step_total_ms': round(1000 * jam_settle[0], 1) if jam_settle else None,
           'jam_detect_ms_after_contact': round(1000 * det, 1) if det is not None else None,
           'dial_moved_deg': round(moved, 2), 'expected_deg': 30 * 45.0,
           'final_offset_counts': round(rig.servo.pos - (p0 + 30 * C.FEED_STEP_COUNTS), 1),
           'step_writes': rig.step_writes, 'expected_step_writes': 30 + s['reverses'] * 2,
           'jams_in_row_after': rig.drv.jams_in_row}
    out['pass'] = (s['settled'] == 30 and s['jams'] == 1 and s['reverses'] == 1 and len(jam_settle) == 1
                   and max(clean_times) <= 0.250 and abs(out['final_offset_counts']) <= C.FEED_SETTLE_COUNTS
                   and rig.step_writes == out['expected_step_writes'] and rig.drv.jams_in_row == 0
                   and out['jam_detect_ms_after_contact'] is not None and out['jam_detect_ms_after_contact'] <= 300.0)
    return out


def rig_start(seed):
    """A pocket position (the dial parked as it should be), +-10 counts."""
    r = random.Random(seed + 7)
    return r.randrange(C.FEED_POCKETS) * C.FEED_STEP_COUNTS + r.uniform(-10.0, 10.0)


def case_jam_fault(seed):
    rig = Rig(seed, start=rig_start(seed))
    boot(rig)
    stepping(rig, 5, 3.0, jam_on=2, jam_deg=20.0, clears=False, t_max=10.0)
    s = rig.drv.stats
    held = rig.servo.pos
    rig.run_until(rig.t + 1.0)
    out = {'state': rig.drv.state, 'fault': rig.drv.fault, 'jams': s['jams'], 'reverses': s['reverses'],
           'settled_before': s['settled'], 'dial_drift_after_fault_counts': round(abs(rig.servo.pos - held), 2),
           'further_steps_refused': not rig.drv.request_step(rig.t)}
    out['pass'] = (rig.drv.state == F.FAULT and rig.drv.fault == 'jams' and s['jams'] == 3 and s['settled'] == 1
                   and out['dial_drift_after_fault_counts'] < 5 and out['further_steps_refused'])
    return out


def case_jam_by_load(seed):
    rig = Rig(seed, start=rig_start(seed))
    boot(rig)
    stepping(rig, 3, 3.0, jam_on=2, jam_deg=5.0, clears=True, t_max=5.0)
    jams = [e for e in rig.events if e[1] == 'jam']
    out = {'jams': len(jams), 'causes': [e[3] for e in jams], 'settled': rig.drv.stats['settled']}
    det = (jams[0][0] - rig.onset) if jams and rig.onset is not None else None
    out['detect_ms_after_contact'] = round(1000 * det, 1) if det is not None else None
    out['pass'] = (len(jams) == 1 and jams[0][3] == 'load' and rig.drv.stats['settled'] == 3
                   and det is not None and det < 0.300)
    return out


def case_drop_off(seed):
    res = {}
    for how in ('arm_signal', 'reads_only'):
        rig = Rig(seed, start=random.Random(seed).uniform(0, 4096))
        boot(rig)
        stepping(rig, 2, 3.0)
        # cut the rail 80 ms into the next step
        rig.drv.request_step(rig.t)
        rig.run_until(rig.t + 0.080)
        cut_t = rig.t
        rig.servo.set_power(False, rig.t)
        if how == 'arm_signal':
            ev = []
            rig.drv.power_lost(rig.t, ev)
            rig.events += [(round(rig.t, 4),) + tuple(e) for e in ev]
        rig.run_until(rig.t + 0.5)
        state_while_off = rig.drv.state
        # the servo's RAM registers are lost; it comes back on the next arm
        rig.servo.set_power(True, rig.t)
        on_t = rig.t
        while rig.drv.state != F.PARKED and rig.t < on_t + 2.0:
            rig.run_until(rig.t + 0.01)
        back_ms = (rig.t - on_t) * 1000
        regs = {'torque_on': rig.servo.torque_on, 'torque_limit': rig.servo.torque_limit, 'acc': rig.servo.acc,
                'goal_speed': rig.servo.goal_speed}
        pos_back = rig.servo.pos
        stepping(rig, 3, 3.0)
        moved = (rig.servo.pos - pos_back) * C.DEG_PER_COUNT
        lost_ev = [e for e in rig.events if e[1] in ('lost', 'offline')]
        left = round(1000 * (lost_ev[0][0] - cut_t), 1) if lost_ev else None
        res[how] = {'state_while_off': state_while_off, 'left_bus_ms_after_cut': left,
                    'back_parked_ms_after_power': round(back_ms, 1), 'registers_after': regs,
                    'reinit': rig.drv.stats['reinit'], 'steps_after_deg': round(moved, 1),
                    'interrupted': rig.drv.stats['interrupted']}
        res[how]['pass'] = (state_while_off == F.OFFLINE and regs == {'torque_on': True, 'torque_limit':
                            C.SERVO_TORQUE_LIMIT, 'acc': C.FEED_ACC, 'goal_speed': C.FEED_SPEED_CPS}
                            and rig.drv.stats['reinit'] == 2 and 3 * 45 - 25 <= moved <= 4 * 45 + 2
                            and back_ms < 600)
    res['pass'] = all(v['pass'] for v in res.values() if isinstance(v, dict))
    return res


def case_lost_replies(seed):
    out = {}
    for kind in ('applied', 'dropped'):
        rig = Rig(seed, start=rig_start(seed))
        boot(rig)
        pos0 = rig.servo.pos
        rig.lose_next_reply = kind
        stepping(rig, 1, 3.0)
        rig.run_until(rig.t + 0.3)
        moved = (rig.servo.pos - pos0) * C.DEG_PER_COUNT
        out[kind] = {'moved_deg': round(moved, 2), 'resent': rig.drv.stats['resent'], 'step_writes': rig.step_writes,
                     'settled': rig.drv.stats['settled']}
        out[kind]['pass'] = abs(moved - 45.0) <= 2.0 and rig.drv.stats['settled'] == 1 and \
            rig.drv.stats['resent'] == (0 if kind == 'applied' else 1)
    out['pass'] = out['applied']['pass'] and out['dropped']['pass']
    return out


def case_step_time(seed):
    out = {}
    for label, acc in (('configured_acc_0', C.FEED_ACC), ('acc_register_254', 254)):
        times = []
        for k in range(20):
            rig = Rig(seed * 100 + k, start=rig_start(seed * 100 + k))
            boot(rig)
            rig.master.write(C.ID_FEED, sts.R_ACC, bytes([acc]))
            stepping(rig, 3, 2.0)
            times += rig.drv.stats['settle_s']
        out[label] = {'steps': len(times), 'settle_ms_mean': round(1000 * sum(times) / len(times), 1),
                      'settle_ms_max': round(1000 * max(times), 1)}
    out['margin_ms_acc_0'] = round(250.0 - out['configured_acc_0']['settle_ms_max'], 1)
    out['margin_ms_acc_254'] = round(250.0 - out['acc_register_254']['settle_ms_max'], 1)
    out['pass'] = out['configured_acc_0']['settle_ms_max'] <= 250.0
    return out


def case_burst(seed):
    """The gate-paced Burst against the stepping rig and a simple ball model: a step's pocket reaching the hole drops a
    ball with p_fill, which crosses gate 1 90 +- 12 ms after the settle (the rerun: first touch 300-330 ms after the
    command); with p_hang it hangs in the hole instead and comes down with the next dial motion (a dither frees it
    alone, a step on top of it would release two); a dither's return refills an empty pocket with p_dither; below
    -12 deg with <= 5 balls left they pool (p 0.1) until the barrel has been level within 1.5 s."""
    out = {}
    runs = (('3/s level', 3.0, 0.0, 200, 0.875, 0.0, 30), ('4/s asked', 4.0, 0.0, 200, 0.875, 0.0, 30),
            ('hung balls (p 0.25)', 3.0, 0.0, 200, 0.875, 0.25, 30),
            ('5 balls at -25 deg', 3.0, -25.0, 5, 0.875, 0.0, 5),
            ('empty hopper', 3.0, 0.0, 0, 0.875, 0.0, 10))
    for label, rate, tilt, hopper, p_fill, p_hang, want in runs:
        rng = random.Random(seed * 31 + len(label))
        rig = Rig(seed, start=rig_start(seed))
        boot(rig)
        b = F.Burst(want, rate, rig.t)
        st_ = {'hopper': hopper, 'arrivals': [], 'hung': False, 'tilt': tilt, 'level_t': -9.0, 'seen': len(rig.events),
               'gate_times': [], 'hangs': 0, 'freed_by_dither': 0, 'freed_by_step': 0}

        def drop(t, n=1):
            for j in range(n):
                st_['arrivals'].append(t + rng.gauss(0.090, 0.012) + 0.004 * j)

        def tick(r: Rig):
            tilt_now = 0.0 if r.t < st_['level_t'] + 0.4 else st_['tilt']
            if tilt_now > -1.0:
                st_['level_t_seen'] = r.t
            for e in r.events[st_['seen']:]:
                kind = e[1]
                if kind not in ('settled', 'dither_done'):
                    continue
                pooled = st_['tilt'] < C.LIFT_BELOW_DEG and st_['hopper'] <= 5 and \
                    r.t - st_.get('level_t_seen', -9.0) > 1.5
                if st_['hung']:                                   # the next motion frees the hung ball
                    st_['hung'] = False
                    drop(r.t)
                    st_['freed_by_dither' if kind == 'dither_done' else 'freed_by_step'] += 1
                    if kind == 'dither_done':
                        continue
                p = 0.1 if pooled else (p_fill if kind == 'settled' else 0.8)
                if st_['hopper'] > 0 and rng.random() < p:
                    st_['hopper'] -= 1
                    if kind == 'settled' and rng.random() < p_hang:
                        st_['hung'] = True
                        st_['hangs'] += 1
                    else:
                        drop(r.t)
            st_['seen'] = len(r.events)
            for a in sorted(a for a in st_['arrivals'] if a <= r.t):
                st_['arrivals'].remove(a)
                st_['gate_times'].append(a)
                b.on_gate1(a)
            act = b.update(r.t, r.drv, True, tilt_now)
            if act == 'lift' and r.t >= st_['level_t'] + 0.4:
                st_['level_t'] = r.t
        t0 = rig.t
        while rig.t < t0 + 90.0 and not b.done:
            rig.run_until(rig.t + 0.01, tick)
        s_ = b.summary()
        steps = [c[0] for c in b.cmd_times if c[1] == 'step']
        gaps = [y - x for x, y in zip(steps, steps[1:])]
        g = st_['gate_times']
        s_.update({'duration_s': round(rig.t - t0, 2), 'balls_left': st_['hopper'] + (1 if st_['hung'] else 0),
                   'step_gap_min_s': round(min(gaps), 3) if gaps else None,
                   'step_rate_per_s': round((len(steps) - 1) / (steps[-1] - steps[0]), 2) if len(steps) > 1 else None,
                   'ball_rate_per_s': round((len(g) - 1) / (g[-1] - g[0]), 2) if len(g) > 1 else None,
                   'hangs': st_['hangs'], 'freed_by_dither': st_['freed_by_dither'],
                   'freed_by_step': st_['freed_by_step']})
        out[label] = s_
    lv, f4, hb, five, emp = (out[k] for k in ('3/s level', '4/s asked', 'hung balls (p 0.25)', '5 balls at -25 deg',
                                                'empty hopper'))
    out['pass'] = (lv['done'] == 'complete' and lv['doubles'] == 0 and lv['step_gap_min_s'] >= C.FEED_MIN_PERIOD_S
                   and f4['step_gap_min_s'] >= C.FEED_MIN_PERIOD_S and f4['doubles'] == 0
                   and hb['hangs'] >= 3 and hb['freed_by_step'] == 0 and hb['freed_by_dither'] == hb['hangs']
                   and hb['doubles'] == 0 and hb['done'] == 'complete'
                   and five['balls_left'] == 0 and five['lifts'] >= 1 and five['balls'] == 5
                   and emp['done'] == 'hopper empty' and emp['dithers'] == C.FEED_MAX_DITHERS * emp['empty_steps'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default=str(R / 'exports' / 'turret' / 'firmware'))
    a = ap.parse_args()
    cases = {}
    for name, fn in (('stepping_3hz_jam', case_stepping_3hz_jam), ('jam_fault', case_jam_fault),
                     ('jam_by_load', case_jam_by_load), ('drop_off', case_drop_off),
                     ('lost_replies', case_lost_replies), ('step_time', case_step_time), ('burst', case_burst)):
        cases[name] = fn(a.seed)
    summary = {'pass': all(c['pass'] for c in cases.values()), 'cases': cases,
               'config': {k: getattr(C, k) for k in ('FEED_STEP_COUNTS', 'FEED_SETTLE_COUNTS', 'FEED_STEP_TIMEOUT_S',
                                                     'FEED_REVERSE_COUNTS', 'FEED_DITHER_COUNTS', 'FEED_MAX_JAMS',
                                                     'FEED_SPEED_CPS', 'FEED_ACC', 'FEED_JAM_LOAD', 'FEED_JAM_LOAD_S',
                                                     'FEED_GATE_WAIT_S', 'FEED_MIN_PERIOD_S', 'FEED_MAX_DITHERS',
                                                     'SERVO_BAUD')},
               'model': __doc__.split('\n\n')[1].strip()}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'feed.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: (v if k != 'cases' else {n: c for n, c in v.items()}) for k, v in summary.items()
                      if k != 'model'}, indent=1))
    return 0 if summary['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
