"""The overnight design loop: Optuna searches motors and dimensions; every candidate is built and checked end to end
by tools/trial_eval.py (designer checks, CAD, clashes, physics scenarios, stiffness and strength, cables).

    .venv/bin/python tools/iterate.py --workers 7 --hours 10        # on a many-core machine
    .venv/bin/python tools/iterate.py --report                       # the leaderboard so far

Search space (catalog parts that are in stock and rated for the 60 V pack, catalog/availability.json):
  leg actuator   RobStride RS-03, RS-04, RS-06 (the same model for hip and knee)
  thigh, shin    170-240 mm
  links          thigh box width, depth and wall; shin width and wall
  yoke           wall, deck and rib thickness
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
ACTUATORS = ['robstride-rs-03', 'robstride-rs-04', 'robstride-rs-06']
STAGES = ['designer', 'cad', 'clashes', 'sims', 'fea', 'cables', 'done']


def availability(part_id: str) -> bool:
    f = R / 'catalog' / 'availability.json'
    if not f.exists():
        return True
    p = json.loads(f.read_text()).get('parts', {}).get(part_id, {})
    return p.get('in_stock') is not False


def suggest(trial) -> tuple[dict, dict]:
    act = trial.suggest_categorical('leg_actuator', ACTUATORS)
    geo = {'thigh_mm': trial.suggest_int('thigh_mm', 170, 240, step=10), 'shin_mm': trial.suggest_int('shin_mm', 170, 240, step=10)}
    params = {
        'link_w': trial.suggest_float('link_w', 30.0, 46.0, step=2.0), 'link_t': trial.suggest_float('link_t', 22.0, 34.0, step=2.0),
        'wall': trial.suggest_float('wall', 1.6, 3.2, step=0.2), 'shin_w': trial.suggest_float('shin_w', 26.0, 40.0, step=2.0),
        'shin_wall': trial.suggest_float('shin_wall', 1.6, 3.2, step=0.2), 'yoke_wall': trial.suggest_float('yoke_wall', 8.0, 14.0, step=1.0),
        'yoke_deck': trial.suggest_float('yoke_deck', 6.0, 12.0, step=1.0), 'yoke_rib': trial.suggest_float('yoke_rib', 4.0, 8.0, step=1.0),
        'crank_r': trial.suggest_float('crank_r', 35.0, 60.0, step=5.0),
    }
    return {'leg_actuator': act, **geo}, params


def score(m: dict) -> float:
    if m.get('ok'):
        s = m['model_mass_kg'] + m.get('cost_usd', 0) / 1000.0 * 0.1
        s += 0 if availability(m.get('leg_actuator', '')) else 5.0
        return s
    # how far it got: later failures are better, so the search learns which way to go
    return 100.0 - 10.0 * STAGES.index(m.get('stage', 'designer')) + (m.get('model_mass_kg') or 30.0) * 0.1


def run_trial(trial) -> float:
    choice, params = suggest(trial)
    tdir = WORK / f'trial_{trial.number:05d}'
    tdir.mkdir(parents=True, exist_ok=True)
    d = json.loads((R / 'designs' / 'default.json').read_text())
    d['name'] = f'Gyropup trial {trial.number}'
    d['parts']['leg_actuator'] = choice['leg_actuator']
    d['geometry']['thigh_mm'], d['geometry']['shin_mm'] = choice['thigh_mm'], choice['shin_mm']
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
    for k in ('ok', 'stage', 'model_mass_kg', 'min_safety_factor', 'wheel_deflection_mm', 'cost_usd', 'track_mm'):
        trial.set_user_attr(k, m.get(k))
    trial.set_user_attr('reasons', (m.get('reasons') or [])[:3])
    s = score(m)
    write_board(trial.study)
    return s


def write_board(study):
    rows = []
    for t in study.get_trials(deepcopy=False):
        if t.value is None:
            continue
        rows.append({'trial': t.number, 'score': round(t.value, 3), **{k: t.user_attrs.get(k) for k in ('ok', 'stage', 'model_mass_kg',
                     'min_safety_factor', 'wheel_deflection_mm', 'cost_usd', 'track_mm', 'reasons')}, 'params': t.params})
    rows.sort(key=lambda r: r['score'])
    ok = [r for r in rows if r['ok']]
    board = {'updated': time.strftime('%Y-%m-%d %H:%M:%S'), 'trials': len(rows), 'passing': len(ok),
             'by_stage': {s: sum(1 for r in rows if r['stage'] == s) for s in STAGES},
             'baseline': json.loads((WORK / 'baseline.json').read_text()) if (WORK / 'baseline.json').exists() else None,
             'best': rows[:25]}
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    tmp = BOARD.with_suffix('.tmp')
    tmp.write_text(json.dumps(board, indent=1) + '\n')
    tmp.replace(BOARD)


def worker(storage: str, deadline: float, seed: int):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.load_study(study_name='gyropup', storage=storage, sampler=optuna.samplers.TPESampler(seed=seed, multivariate=True))
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
    study = optuna.create_study(study_name='gyropup', storage=storage, direction='minimize', load_if_exists=True)
    if a.report:
        write_board(study)
        print(BOARD.read_text())
        return
    if not any(t.params.get('leg_actuator') == 'robstride-rs-03' and t.params.get('link_w') == 40.0 for t in study.trials):
        # start from today's design, so the search has a passing point to improve on
        study.enqueue_trial({'leg_actuator': 'robstride-rs-03', 'thigh_mm': 200, 'shin_mm': 200, 'link_w': 40.0, 'link_t': 30.0, 'wall': 2.6,
                             'shin_w': 34.0, 'shin_wall': 2.0, 'yoke_wall': 12.0, 'yoke_deck': 10.0, 'yoke_rib': 6.0, 'crank_r': 45.0})
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
