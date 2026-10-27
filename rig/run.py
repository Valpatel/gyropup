"""Run a rig test on the motors, on the HIL stand-in, or in the simulation; log it and judge it.

    python -m rig.run --backend sim --test squat                     # MuJoCo, the rig's controller at 500 Hz
    python -m rig.run --backend sim --test jump --rate 250 --plot
    python -m rig.run --backend hil --test jump                      # the CAN path on two software RS-04s + MuJoCo
    python -m rig.run --backend can --iface can0 --test stand_up     # the rig itself (pendant held, ARM typed)
    python -m rig.run --reproduce        # T7: every scenario as sim/leg_rig.py ran it -> exports/rig/reproduction.json
    python -m rig.run --predict          # the rig as built: 14.75 kg, the FLEXVOLT pack, a tick of latency, at 500 Hz
                                         # -> exports/rig/predictions.json (the numbers docs/leg-bench-tests.md quotes)

Every run writes exports/rig/runs/<stamp>-<backend>-<test>.npz/.json (rig/log.py) and its verdict (rig/compare.py).
The motors are only driven while the rig node's RUN frames are fresh (the pendant held) and after ARM is typed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Optional

R = Path(__file__).resolve().parents[1]
if str(R) not in sys.path:
    sys.path.insert(0, str(R))

from rig import compare, leg_control as lc  # noqa: E402
from rig.bus import Pack  # noqa: E402
from rig.log import RunLog  # noqa: E402

OUT = R / 'exports' / 'rig'
DESIGN_KG = 14.75                     # half the 29.5 kg robot of the body plan (coordinator, 2026-10-27)
REF_KG = 13.1                         # what exports/leg/rig-results.json was run at
RIG_TESTS = ('stand_up', 'squat', 'jump', 'drop_150', 'power_off', 'power_off_damped')
BUMPER_CONTACT_M = 0.140              # the bottom bumpers meet the carriage at this leg length (cad/build_rig.py)
DYNAMIC = ('jump', 'jump_peak', 'drop_150')


def v_start_max(r_int: float, i_regen: float = 27.0, v_max: float = 57.5) -> float:
    """The highest pack voltage a jump or a drop may start at: the regeneration spike (I_regen through the pack's
    resistance) must stay under v_max (the supervisor limps at 58 V, the RS-04 trips at 60 V)."""
    return round(v_max - i_regen * r_int, 1)


def pack_for(test: str, r_int: float = 0.25, v_dynamic: Optional[float] = None, v_static: float = 54.0) -> Pack:
    v = v_dynamic if v_dynamic is not None else min(54.0, v_start_max(r_int))
    return Pack(v_oc=v if test in DYNAMIC else v_static, r_int=r_int)


def loop(bus, ctl, log: RunLog, duration: float, verbose: bool = False):
    """The control loop: a tick in, a command out, until the scenario's end (or the supervisor stops it and the motors
    have been quiet for 0.5 s). Ctrl-C asks the supervisor for a sit-down."""
    tk = bus.start()
    t_stop = None
    try:
        while tk.t < duration - 1e-9:
            pol = lc.polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w) if (math.isfinite(tk.f.phi) and math.isfinite(tk.r.phi)) else None
            try:
                cmd = ctl.update(tk)
            except KeyboardInterrupt:
                raise
            log.add(tk, cmd, pol)
            if cmd.power_off and getattr(bus, 'powered', True):
                bus.power_off()
            if cmd.stop:
                if t_stop is None:
                    bus.stop()
                    t_stop = tk.t
                elif tk.t - t_stop > 0.5:
                    break
            tk = bus.step(cmd.tau_f, cmd.tau_r, cmd.kd)
    except KeyboardInterrupt:
        if ctl.abort is None:
            ctl.abort, ctl.t_abort = 'sitdown: operator (Ctrl-C)', tk.t
            ctl.L_abort = lc.polar(tk.f.phi, tk.r.phi, tk.f.w, tk.r.w)[0]
        while not ctl.done:
            cmd = ctl.update(tk)
            log.add(tk, cmd, None)
            tk = bus.step(cmd.tau_f, cmd.tau_r, cmd.kd)
    finally:
        bus.stop()
    return tk


def run_sim(test: str, half_mass: float, rate: float, pack: Pack, latency: int, rail_low: Optional[float] = None,
            contact_truth: bool = False, limits: Optional[lc.Limits] = None, video: Optional[Path] = None,
            tag: str = '', save: bool = True, plot: bool = False, inject: Optional[tuple] = None):
    from rig.sim_bus import SimBus
    sc = lc.SCENARIOS[test]
    bus = SimBus(test, half_mass=half_mass, tick=1 / rate, cap=sc.cap, rail_low=rail_low, pack=pack,
                 latency_ticks=latency, video=video)
    if inject:
        from rig.faults import FaultBus
        bus = FaultBus(bus, inject[0], inject[1])
    lim = limits or lc.Limits(cap=sc.cap or lc.LEG_PEAK)
    ctl = lc.LegController(test, bus.ff_n, lim, contact_truth=contact_truth, tick=bus.tick)
    meta = {'half_mass_kg': half_mass, 'rate_hz': round(1 / bus.tick, 1), 'latency_ticks': latency,
            'pack': {'v_oc': pack.v_oc, 'r_int': pack.r_int}, 'rail_low_m': rail_low if rail_low is not None else sc.rail_low,
            'ff_n': round(bus.ff_n, 2), 'limits': lim.__dict__, 'flight': ctl.flight.__dict__}
    log = RunLog('sim', test, meta, tag)
    loop(bus, ctl, log, sc.duration)
    bus.close()
    res = bus.results()
    out = {'results': res, 'log': log}
    if save:
        paths = log.save({'sim': {k: v for k, v in res.items() if k != 'series'}})
        out['paths'] = paths
        _judge(paths['json'], plot)
    return out


def _judge(path: Path, plot: bool) -> int:
    return compare.main([str(path)] + (['--plot'] if plot else []))


def reproduce(rate: float = 500.0) -> dict:
    """T7's acceptance: sim/leg_rig.py's scenarios through the bus at the rig's rate, against rig-results.json."""
    ref = json.loads((R / 'exports' / 'leg' / 'rig-results.json').read_text())
    results = {}
    for name in lc.SCENARIOS:
        r = run_sim(name, ref['half_mass_kg'], rate, Pack(54.0, 0.0), 0, save=False)['results']
        results[name] = {k: v for k, v in r.items() if k != 'series'}
        print(f"  {name:17} jump {r['jump_height_mm']}  motor {r['peak_motor_nm']}  wheel {r['peak_wheel_force_n']}  gearbox {r['peak_gearbox_nm']}")
    rep = compare.reproduce_report(results, ref['scenarios'])
    rep.update({'rate_hz': rate, 'half_mass_kg': ref['half_mass_kg'], 'bus': 'ideal 54 V, no latency (as sim/leg_rig.py)',
                'controller': 'rig/leg_control.py (the rig\'s port) on rig/sim_bus.py',
                'note': 'peak_gearbox_nm in the jump is the landing spike: the rig detects touchdown from the leg 2-4 ms after '
                        'MuJoCo\'s contact, so its feed-forward returns that much later (with the simulator\'s contact flag '
                        'the port reproduces it: python -m rig.run --backend sim --test jump --contact-truth)'})
    (OUT / 'reproduction.json').write_text(json.dumps(rep, indent=1) + '\n')
    return rep


def predict(half_mass: float = DESIGN_KG, rate: float = 500.0, r_int: float = 0.25, sample: str = 'jump') -> dict:
    """The rig's predicted numbers: its controller, rate and latency, the design mass, the FLEXVOLT pack as the start
    rule leaves it, the bumpers where cad/build_rig.py puts them."""
    tests = {}
    cases = [(t, t, None) for t in RIG_TESTS] + [('power_off_S6', 'power_off', 0.074), ('power_off_damped_S6', 'power_off_damped', 0.074)]
    for key, test, rail in cases:
        if rail is None:
            rail = BUMPER_CONTACT_M                                   # the bottom bumpers in place (S6: removed, the deck)
        pack = pack_for(test, r_int)
        o = run_sim(test, half_mass, rate, pack, 1, rail_low=rail, save=(key == sample), tag='prediction', plot=(key == sample))
        res, log = o['results'], o['log']
        arr = log.arrays()
        m = compare.metrics(arr, test)
        ser = {k: [round(float(x), 3) for x in arr[k][::5]] for k in ('t', 'L', 'tau_f', 'tau_r', 'rail_mm', 'wheel_fz_n', 'vbus')}
        ser['L_mm'] = [round(x * 1000, 2) for x in ser.pop('L')]
        tests[key] = {'test': test, 'rail_low_m': rail, 'pack': {'v_start': pack.v_oc, 'r_int': pack.r_int},
                      'summary': {k: v for k, v in res.items() if k != 'series'}, 'metrics': m,
                      'verdict': compare.judge(test, arr, {'metrics': m}), 'series': ser}
        print(f"  {key:20} jump {res['jump_height_mm']}  motor {res['peak_motor_nm']}  wheel {res['peak_wheel_force_n']}  "
              f"knee {res['peak_knee_pin_n']}  gearbox {res['peak_gearbox_nm']}  L {res['L_range_mm']}  VBUS {m.get('vbus_range_v')}")
    doc = {'half_mass_kg': half_mass, 'rate_hz': rate, 'latency_ticks': 1, 'pack_r_int': r_int,
           'v_start_max_dynamic': v_start_max(r_int), 'bumper_contact_leg_m': BUMPER_CONTACT_M,
           'made_by': 'python -m rig.run --predict', 'tests': tests}
    (OUT / 'predictions.json').write_text(json.dumps(doc, indent=1) + '\n')
    return doc


def faults(test: str = 'squat', at: float = 1.0) -> dict:
    """T8: every abort of the supervisor shown in the simulation, each fault injected at `at` s of `test`."""
    from rig.faults import EXPECT, KINDS
    import numpy as np
    out = {}
    for kind in KINDS:
        o = run_sim(test, DESIGN_KG, 500.0, Pack(54.0, 0.25), 1, save=False, inject=(kind, at))
        log = o['log']
        a = log.arrays()
        ab = log.aborts[0] if log.aborts else None
        t = a['t']
        after = t >= (ab[0] if ab else at)
        stopped = np.flatnonzero(a['phase'] == 8)                       # 'stopped'
        tq = np.abs(np.r_[a['tau_cmd_f'][stopped], a['tau_cmd_r'][stopped]]) if len(stopped) else np.array([0.0])
        row = {'injected_at_s': at, 'abort': ab[1] if ab else None, 'abort_at_s': ab[0] if ab else None,
               'reaction_ms': round((ab[0] - at) * 1000, 1) if ab else None, 'expected': EXPECT[kind],
               'ok': bool(ab and ab[1].startswith(EXPECT[kind]) and float(np.max(tq)) == 0.0),
               'leg_at_stop_mm': round(float(a['L'][stopped[0]]) * 1000, 1) if len(stopped) else None,
               'torque_after_stop_nm': float(np.max(tq)), 'lowest_leg_after_mm': round(float(np.nanmin(a['L'][after])) * 1000, 1)}
        out[kind] = row
        print(f"  {kind:10} -> {row['abort']} after {row['reaction_ms']} ms; leg {row['leg_at_stop_mm']} mm when stopped, "
              f"lowest {row['lowest_leg_after_mm']} mm  {'OK' if row['ok'] else 'NOT AS EXPECTED'}")
    # the rate limiter: the first hanging tests run with 5 N m per tick
    o = run_sim('stand_up', DESIGN_KG, 500.0, Pack(54.0, 0.25), 1, save=False, limits=lc.Limits(rate=5.0))
    a = o['log'].arrays()
    d = float(max(np.max(np.abs(np.diff(a['tau_cmd_f']))), np.max(np.abs(np.diff(a['tau_cmd_r'])))))
    out['rate_limit'] = {'limit_nm_per_tick': 5.0, 'largest_step_nm': round(d, 3), 'ok': d <= 5.0 + 1e-9,
                         'stand_up_still_holds': o['results']['L_range_mm']}
    print(f"  rate limit 5 N m/tick: largest step {d:.3f} N m; stand-up L {o['results']['L_range_mm']}")
    doc = {'test': test, 'half_mass_kg': DESIGN_KG, 'made_by': 'python -m rig.run --faults', 'faults': out,
           'all_ok': all(v['ok'] for v in out.values())}
    (OUT / 'faults.json').write_text(json.dumps(doc, indent=1) + '\n')
    return doc


def run_hil(test: str, half_mass: float, rate: float, pack: Pack, plot: bool = False, tag: str = 'hil'):
    from rig.can_bus import Calibration, CanBus, MotorCal
    from rig.hil import HilLink
    from rig.sim_bus import SimBus
    import fivebar as fb
    sc = lc.SCENARIOS[test]
    fo, _, ro, _ = fb.stop_angles()
    cal = Calibration(MotorCal(1, -1, fo + 0.05), MotorCal(2, -1, ro - 0.05), 'HIL: both motors reversed, zero offset')
    sim = SimBus(test, half_mass=half_mass, tick=1 / rate, cap=sc.cap, pack=pack, latency_ticks=0)
    link = HilLink(sim, cal, cut_at=0.6 if test.startswith('power_off') else None)
    bus = CanBus(link.port, cal, tick=1 / rate, realtime=False, clock=link.clock, after_exchange=link.advance)
    link.begin()
    ctl = lc.LegController(test, sim.ff_n, lc.Limits(cap=sc.cap or lc.LEG_PEAK), tick=1 / rate, external_cut=True)
    log = RunLog('hil', test, {'half_mass_kg': half_mass, 'rate_hz': rate, 'pack': {'v_oc': pack.v_oc, 'r_int': pack.r_int}}, tag)
    loop(bus, ctl, log, sc.duration)
    log.meta['startup'] = bus.startup
    log.meta['timing'] = bus.timing.summary()
    res = sim.results()
    paths = log.save({'sim': {k: v for k, v in res.items() if k != 'series'}})
    _judge(paths['json'], plot)
    return {'results': res, 'log': log, 'paths': paths, 'bus': bus}


def run_can(a) -> int:
    from rig.can_bus import Calibration, CanBus
    from rig.canio import SocketCan
    sc = lc.SCENARIOS[a.test]
    if a.test not in RIG_TESTS:
        print(f'{a.test} is not a rig test (the motors are capped at 60 N m)')
        return 2
    cal = Calibration.load()
    bus = CanBus(SocketCan(a.iface), cal, tick=1 / a.rate, require_node=not a.no_node, damper=a.damper)
    ctl = lc.LegController(a.test, lc.ff_for(a.half_mass, *_ff_masses()), lc.Limits(rate=a.rate_limit), tick=1 / a.rate,
                           external_cut=True)
    log = RunLog('can', a.test, {'half_mass_kg': a.half_mass, 'rate_hz': a.rate, 'iface': a.iface, 'calibration': cal.__dict__}, a.tag)
    if not a.yes:
        input(f'{sc.title}. Clear the zone, hold the pendant, then press Enter to configure the motors: ')
    tk = bus.start()
    log.meta['startup'] = bus.startup
    for k, v in bus.startup.items():
        print(f"  {k}: damper {v['damper']} ({v['damper_meaning']}), limit_torque {v['limit_torque']}, canTimeout {v['canTimeout']}, "
              f"VBUS {v['VBUS']:.2f} V, firmware {v.get('firmware')}")
    vb = min(v['VBUS'] for v in bus.startup.values())
    vmax = v_start_max(a.r_int) if a.test in DYNAMIC else 56.0
    if vb > vmax:
        print(f'refused: the pack is at {vb:.1f} V; {a.test} starts at {vmax} V at most (R_int {a.r_int} ohm)')
        bus.stop()
        return 3
    if not a.yes and input('Type ARM to run: ').strip() != 'ARM':
        bus.stop()
        return 4
    loop(bus, ctl, log, sc.duration)
    log.meta['timing'] = bus.timing.summary()
    paths = log.save({})
    bus.close()
    return _judge(paths['json'], a.plot)


def _ff_masses():
    """(rotor kg, wheel link kg) for the feed-forward, from exports/rig/rig.json (cad/build_rig.py)."""
    d = json.loads((OUT / 'rig.json').read_text())['controller']
    return d['rotor_kg'], d['wheel_link_kg']


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m rig.run', description=__doc__.split('\n\n')[0])
    ap.add_argument('--backend', choices=('sim', 'hil', 'can'), default='sim')
    ap.add_argument('--test', choices=tuple(lc.SCENARIOS), default='stand_up')
    ap.add_argument('--half-mass', type=float, default=DESIGN_KG)
    ap.add_argument('--rate', type=float, default=500.0)
    ap.add_argument('--r-int', type=float, default=0.25, help='the pack\'s resistance, ohm (measured: docs/leg-bench-tests.md B6)')
    ap.add_argument('--v-start', type=float, help='the pack voltage in the simulation (default: the start rule)')
    ap.add_argument('--latency', type=int, default=1)
    ap.add_argument('--contact-truth', action='store_true', help='simulation only: the controller reads MuJoCo\'s contact')
    ap.add_argument('--plot', action='store_true')
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--tag', default='')
    ap.add_argument('--iface', default='can0')
    ap.add_argument('--damper', type=int, choices=(0, 1))
    ap.add_argument('--rate-limit', type=float, help='N m per tick the command may change (the first hanging tests: 5)')
    ap.add_argument('--no-node', action='store_true', help='CAN without the rig node: bench tests only, never with the leg on the rig')
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--inject', help='simulation only: a fault kind@seconds (rig/faults.py), e.g. run@1.0')
    ap.add_argument('--faults', action='store_true', help='every abort demonstrated -> exports/rig/faults.json')
    ap.add_argument('--reproduce', action='store_true')
    ap.add_argument('--predict', action='store_true')
    a = ap.parse_args(argv)
    if a.reproduce:
        rep = reproduce(a.rate)
        print('T7 acceptance:', 'PASS' if rep['all_ok'] else 'FAIL')
        return 0 if rep['all_ok'] else 1
    if a.predict:
        predict(a.half_mass, a.rate, a.r_int)
        return 0
    if a.faults:
        return 0 if faults()['all_ok'] else 1
    pack = pack_for(a.test, a.r_int, a.v_start)
    if a.backend == 'sim':
        inj = (a.inject.split('@')[0], float(a.inject.split('@')[1])) if a.inject else None
        o = run_sim(a.test, a.half_mass, a.rate, pack, a.latency, contact_truth=a.contact_truth, tag=a.tag, plot=a.plot,
                    video=(OUT / 'runs' / f'{a.test}.mp4') if a.video else None, inject=inj,
                    limits=lc.Limits(rate=a.rate_limit) if a.rate_limit else None)
        print(json.dumps({k: v for k, v in o['results'].items() if k not in ('series', 'rig')}, indent=1))
        return 0
    if a.backend == 'hil':
        o = run_hil(a.test, a.half_mass, a.rate, pack, a.plot)
        print(json.dumps({k: v for k, v in o['results'].items() if k not in ('series', 'rig')}, indent=1))
        print('timing', o['bus'].timing.summary())
        return 0
    return run_can(a)


if __name__ == '__main__':
    sys.exit(main())
