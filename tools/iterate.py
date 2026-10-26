"""The overnight design loop: Optuna searches motors and dimensions; every candidate is built and checked end to end
by tools/trial_eval.py (designer checks, CAD, clashes, physics scenarios, stiffness and strength, cables).

    .venv/bin/python tools/iterate.py --workers 7 --hours 10        # on a many-core machine
    .venv/bin/python tools/iterate.py --report                       # the leaderboard so far

Search space (catalog parts that are in stock and rated for the 60 V pack, catalog/availability.json):
  leg actuator   RobStride RS-03, RS-04, RS-06 (the same model for hip and knee)
  thigh, shin    170-240 mm
  links          thigh box width, depth and wall; shin width and wall
  yoke           sheet thickness, side-flange depth, gusset length (a bent hat channel)
  crank radius   35-60 mm (the push-rod force is knee torque / crank radius)
Objective: the lightest robot (the physics model's mass, with the CAD parts) that passes everything; cost breaks ties
(1 kg ~ $1000), and a part that is not in stock costs 5 kg. Failed candidates score by how far they got, so the
search still learns from them. Results: work/iterate/<trial>/metrics.json, work/iterate/study.db (Optuna), and
exports/iterate/leaderboard.json (the best 25, refreshed after every trial).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
WORK = R / 'work' / 'iterate'
BOARD = R / 'exports' / 'iterate' / 'leaderboard.json'
ACTUATORS = ['robstride-rs-03', 'robstride-rs-04']     # in stock and rated to 60 V (RS-06 cannot hold a crouch)
BUSES = {'60v': 'designs/default.json', '2x20v': 'designs/flexvolt-2x20v.json'}   # where each bus's power parts come from
POWER_SLOTS = ('battery', 'dcdc_compute', 'dcdc_12v', 'motor_driver', 'battery_adapter', 'regen_clamp')
STAGES = ['designer', 'cad', 'clashes', 'sims', 'fea', 'cables', 'done']


def availability(part_id: str) -> bool:
    f = R / 'catalog' / 'availability.json'
    if not f.exists():
        return True
    p = json.loads(f.read_text()).get('parts', {}).get(part_id, {})
    return p.get('in_stock') is not False


def suggest(trial) -> tuple[dict, dict]:
    act = trial.suggest_categorical('leg_actuator', ACTUATORS)
    geo = {'thigh_mm': trial.suggest_int('thigh_mm', 170, 240, step=10), 'shin_mm': trial.suggest_int('shin_mm', 170, 240, step=10),
           'knee_min_deg': trial.suggest_int('knee_min_deg', 42, 60, step=2), 'knee_max_deg': trial.suggest_int('knee_max_deg', 140, 160, step=5),
           'bus': trial.suggest_categorical('bus', list(BUSES))}
    params = {
        'link_w': trial.suggest_float('link_w', 30.0, 46.0, step=2.0), 'link_t': trial.suggest_float('link_t', 22.0, 34.0, step=2.0),
        'wall': trial.suggest_float('wall', 1.6, 3.2, step=0.2), 'shin_w': trial.suggest_float('shin_w', 26.0, 40.0, step=2.0),
        'shin_wall': trial.suggest_float('shin_wall', 1.6, 3.2, step=0.2), 'yoke_t': trial.suggest_float('yoke_t', 3.0, 6.0, step=1.0),
        'yoke_depth': trial.suggest_float('yoke_depth', 25.0, 60.0, step=5.0), 'yoke_gusset': trial.suggest_float('yoke_gusset', 50.0, 110.0, step=10.0),
        'crank_r': trial.suggest_float('crank_r', 45.0, 70.0, step=5.0),
        'lever_beta_deg': trial.suggest_float('lever_beta_deg', -90.0, -60.0, step=5.0),
    }
    return {'leg_actuator': act, **geo}, params


OBJECTIVES = ['mass_kg', 'cost_usd', 'motor_load', 'track_mm']    # all minimised (NSGA-II)


def score(m: dict) -> list:
    """Four objectives. A failed candidate gets a penalty by how far it got (later is better), so the search still
    learns which way to go; an out-of-stock part counts as a failure."""
    if m.get('ok') and availability(m.get('leg_actuator', '')):
        return [m['model_mass_kg'], m.get('cost_usd', 0), m.get('worst_motor_of_peak', 1.0), m.get('track_mm', 600)]
    p = 100.0 - 10.0 * STAGES.index(m.get('stage', 'designer'))
    return [p + (m.get('model_mass_kg') or 30.0), p * 100 + 9000, p + 1.0, p * 10 + 700]


def run_trial(trial) -> float:
    choice, params = suggest(trial)
    tdir = WORK / f'trial_{trial.number:05d}'
    tdir.mkdir(parents=True, exist_ok=True)
    d = json.loads((R / 'designs' / 'default.json').read_text())
    d['name'] = f'Gyropup trial {trial.number}'
    d['parts']['leg_actuator'] = choice['leg_actuator']
    d['geometry']['thigh_mm'], d['geometry']['shin_mm'] = choice['thigh_mm'], choice['shin_mm']
    d['geometry']['knee_min_deg'], d['geometry']['knee_max_deg'] = choice['knee_min_deg'], choice['knee_max_deg']
    if choice['bus'] != '60v':                                   # take that bus's power parts from its design file
        pw = json.loads((R / BUSES[choice['bus']]).read_text())
        for slot in POWER_SLOTS:
            if slot in pw['parts'] or slot in d['parts']:
                d['parts'][slot] = pw['parts'].get(slot)
        d['battery_count'] = pw.get('battery_count', 1)
        d['part_qty'] = {**d.get('part_qty', {}), **pw.get('part_qty', {})}
    design = tdir / f'trial_{trial.number:05d}.json'
    design.write_text(json.dumps(d, indent=1) + '\n')
    (tdir / 'params.json').write_text(json.dumps(params) + '\n')
    env = {**os.environ, 'GYROPUP_EXPORTS': str(tdir), 'GYROPUP_CAD_PARAMS': str(tdir / 'params.json'),
           'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '4'}
    try:
        r = subprocess.run([sys.executable, str(R / 'tools' / 'trial_eval.py'), str(design)], cwd=R, env=env,
                           capture_output=True, text=True, timeout=5400)
        m = json.loads((tdir / 'metrics.json').read_text())
    except Exception as e:                                       # a crash or a timeout is a failed candidate
        m = {'ok': False, 'stage': 'designer', 'reasons': [f'{type(e).__name__}: {e}'[:300]]}
    m.update(leg_actuator=choice['leg_actuator'], choice=choice, params=params)
    (tdir / 'metrics.json').write_text(json.dumps(m, indent=1) + '\n')
    for k in ('ok', 'stage', 'model_mass_kg', 'min_safety_factor', 'wheel_deflection_mm', 'cost_usd', 'track_mm', 'worst_motor_of_peak', 'worst_motor', 'min_sin_phi'):
        trial.set_user_attr(k, m.get(k))
    trial.set_user_attr('reasons', (m.get('reasons') or [])[:3])
    s = score(m)
    write_board(trial.study)
    return s


def write_board(study):
    rows = []
    for t in study.get_trials(deepcopy=False):
        if t.values is None:
            continue
        rows.append({'trial': t.number, 'score': round(t.values[0], 3), **{k: t.user_attrs.get(k) for k in ('ok', 'stage', 'model_mass_kg',
                     'min_safety_factor', 'wheel_deflection_mm', 'cost_usd', 'track_mm', 'worst_motor_of_peak', 'worst_motor', 'min_sin_phi', 'reasons')}, 'params': t.params})
    rows.sort(key=lambda r: (not r['ok'], r['score']))
    ok = [r for r in rows if r['ok']]
    board = {'updated': time.strftime('%Y-%m-%d %H:%M:%S'), 'trials': len(rows), 'passing': len(ok),
             'by_stage': {s: sum(1 for r in rows if r['stage'] == s) for s in STAGES},
             'baseline': json.loads((WORK / 'baseline.json').read_text()) if (WORK / 'baseline.json').exists() else None,
             'objectives': OBJECTIVES,
             'pareto': sorted([t.number for t in study.best_trials if t.user_attrs.get('ok')]) if rows else [],
             'best': rows[:25]}
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    tmp = BOARD.with_suffix('.tmp')
    tmp.write_text(json.dumps(board, indent=1) + '\n')
    tmp.replace(BOARD)


def worker(storage: str, deadline: float, seed: int):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.load_study(study_name='gyropup', storage=storage, sampler=optuna.samplers.NSGAIISampler(seed=seed, population_size=24))
    while time.time() < deadline:
        study.optimize(run_trial, n_trials=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 4) // 5))
    ap.add_argument('--hours', type=float, default=10.0)
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    import optuna
    WORK.mkdir(parents=True, exist_ok=True)
    storage = f'sqlite:///{WORK / "study.db"}'
    study = optuna.create_study(study_name='gyropup', storage=storage, directions=['minimize'] * len(OBJECTIVES), load_if_exists=True)
    if a.report:
        write_board(study)
        print(BOARD.read_text())
        return
    if not study.trials:
        # start from today's design, so the search has a passing point to improve on
        base = {'leg_actuator': 'robstride-rs-03', 'thigh_mm': 200, 'shin_mm': 200, 'knee_min_deg': 48, 'knee_max_deg': 155, 'link_w': 40.0,
                'link_t': 30.0, 'wall': 2.6, 'shin_w': 34.0, 'shin_wall': 2.0, 'yoke_t': 4.0, 'yoke_depth': 40.0, 'yoke_gusset': 80.0,
                'crank_r': 60.0, 'lever_beta_deg': -75.0}
        study.enqueue_trial({**base, 'bus': '60v'})               # today's design, on both buses: passing points to improve on
        study.enqueue_trial({**base, 'bus': '2x20v'})
    deadline = time.time() + a.hours * 3600
    procs = [mp.Process(target=worker, args=(storage, deadline, 1000 + k)) for k in range(a.workers)]
    for p in procs:
        p.start()
        time.sleep(5)                                            # stagger the sqlite writes
    for p in procs:
        p.join()
    write_board(study)
    print(BOARD.read_text()[:2000])


if __name__ == '__main__':
    main()
