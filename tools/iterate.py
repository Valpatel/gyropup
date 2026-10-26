"""The overnight design loop: Optuna searches motors and dimensions; every candidate is built and checked end to end
by tools/trial_eval.py (designer checks, CAD, clashes, physics scenarios, stiffness and strength, cables).

    .venv/bin/python tools/iterate.py --workers 7 --hours 10        # on a many-core machine
    .venv/bin/python tools/iterate.py --report                       # the leaderboard so far

Every made part is printed (D33: PA6-CF for structure). Search space:
  leg actuator   RobStride RS-04 or RS-03 (the same model for hip and knee; both capped at 60 N·m in firmware)
  thigh, shin    170-240 mm (a part that does not fit the 256 mm bed fails the candidate)
  links          thigh box width, depth and wall; shin width and wall
  yoke           wall thickness, side-flange depth, gusset length (a printed hat channel)
  motor plates   thickness (via the adapter journal), arm width, tab height
  crank          radius, lever angle, thickness
Objectives (NSGA-II, all minimised): the robot's mass (the physics model, with the CAD parts), print hours, the hardest
motor's share of its limit, and the track width. Failed candidates score by how far they got, so the search still
learns from them. Results: work/iterate/<trial>/metrics.json, work/iterate/study.db (Optuna), and
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
ACTUATORS = ['robstride-rs-04', 'robstride-rs-03']     # rated to 60 V (RS-06 cannot hold a landing; see docs/cad-plan.md)
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
        'link_w': trial.suggest_float('link_w', 48.0, 72.0, step=4.0), 'link_t': trial.suggest_float('link_t', 36.0, 56.0, step=4.0),
        'wall': trial.suggest_float('wall', 3.5, 6.5, step=0.5), 'shin_w': trial.suggest_float('shin_w', 40.0, 60.0, step=4.0),
        'shin_wall': trial.suggest_float('shin_wall', 3.0, 5.0, step=0.5), 'yoke_t': trial.suggest_float('yoke_t', 6.0, 11.0, step=1.0),
        'yoke_depth': trial.suggest_float('yoke_depth', 35.0, 70.0, step=5.0), 'yoke_gusset': trial.suggest_float('yoke_gusset', 60.0, 110.0, step=10.0),
        'crank_r': trial.suggest_float('crank_r', 45.0, 70.0, step=5.0), 'crank_t': trial.suggest_float('crank_t', 10.0, 18.0, step=2.0),
        'lever_beta_deg': trial.suggest_float('lever_beta_deg', -90.0, -60.0, step=5.0),
        'journal_extra': trial.suggest_float('journal_extra', 6.0, 16.0, step=1.0), 'plate_arm_w': trial.suggest_float('plate_arm_w', 20.0, 36.0, step=4.0),
        'tab_extra': trial.suggest_float('tab_extra', 4.0, 14.0, step=2.0),
    }
    return {'leg_actuator': act, **geo}, params


OBJECTIVES = ['mass_kg', 'print_hours', 'motor_load', 'track_mm']    # all minimised (NSGA-II)


def score(m: dict) -> list:
    """Four objectives. A failed candidate gets a penalty by how far it got (later is better), so the search still
    learns which way to go; an out-of-stock part counts as a failure."""
    if m.get('ok') and availability(m.get('leg_actuator', '')):
        return [m['model_mass_kg'], m.get('print_hours', 400), m.get('worst_motor_of_peak', 1.0), m.get('track_mm', 600)]
    p = 100.0 - 10.0 * STAGES.index(m.get('stage', 'designer'))
    return [p + (m.get('model_mass_kg') or 30.0), p * 10 + (m.get('print_hours') or 600), p + 1.0, p * 10 + 700]


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
    for k in ('ok', 'stage', 'model_mass_kg', 'min_safety_factor', 'min_safety_factor_fall', 'wheel_deflection_mm', 'cost_usd', 'track_mm', 'worst_motor_of_peak',
              'worst_motor', 'min_sin_phi', 'print_hours', 'print_kg', 'weakest_part'):
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
                     'min_safety_factor', 'min_safety_factor_fall', 'wheel_deflection_mm', 'cost_usd', 'track_mm', 'worst_motor_of_peak', 'worst_motor',
                     'min_sin_phi', 'print_hours', 'print_kg', 'weakest_part', 'reasons')}, 'params': t.params})
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
        base = {'leg_actuator': 'robstride-rs-04', 'thigh_mm': 200, 'shin_mm': 200, 'knee_min_deg': 48, 'knee_max_deg': 155, 'link_w': 60.0,
                'link_t': 52.0, 'wall': 6.0, 'shin_w': 48.0, 'shin_wall': 4.0, 'yoke_t': 10.0, 'yoke_depth': 55.0, 'yoke_gusset': 80.0,
                'crank_r': 60.0, 'crank_t': 14.0, 'lever_beta_deg': -75.0, 'journal_extra': 11.0, 'plate_arm_w': 28.0, 'tab_extra': 8.0}
        study.enqueue_trial({**base, 'bus': '60v'})               # today's design, on both buses, and on the RS-03
        study.enqueue_trial({**base, 'bus': '2x20v'})
        study.enqueue_trial({**base, 'bus': '60v', 'leg_actuator': 'robstride-rs-03'})
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
