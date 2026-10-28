"""The bench tests' numbers to the simulation's parameters (docs/leg-bench-tests.md; the main session's F1 and F2).

    python -m rig.bench.fit_params --templates     # blank data sheets: exports/rig/bench/sheets/b3.csv, b4.csv, b5.csv, b6.csv
    python -m rig.bench.fit_params                 # every result present -> exports/rig/bench/sim-params.json

  B1  exports/rig/bench/b1-*.json (rig/bench/backdrive.py)  -> the power-off drag b(w) per condition (OFF_DAMPING's curve)
  B2  exports/rig/bench/b2-motor*.json (rig/bench/spin_down.py) -> the rotor's reflected inertia (ARMATURE)
  B3  sheets/b3.csv: cycle, force_n, deflection_mm           -> the sleeve's rate and travel (STOP_K, STOP_TRAVEL)
  B4  sheets/b4.csv: size, sample, torque_nm, tension_n, pullout_n -> torque against preload, pull-out (HUB_PRELOAD_N)
  B5  sheets/b5.csv: spot, direction, force_n, deflection_mm -> the tyre's radial rate and hysteresis (TYRE_SOLREF)
  B6  sheets/b6.csv: v_open, v_loaded, r_load_ohm             -> the pack's resistance and the jumps' start voltage
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
BENCH = R / 'exports' / 'rig' / 'bench'
SHEETS = BENCH / 'sheets'
TEMPLATES = {
    'b3.csv': ['cycle', 'force_n', 'deflection_mm'],
    'b4.csv': ['size', 'sample', 'torque_nm', 'tension_n', 'pullout_n'],
    'b5.csv': ['spot', 'direction', 'force_n', 'deflection_mm'],
    'b6.csv': ['v_open', 'v_loaded', 'r_load_ohm'],
}


def assumed() -> dict:
    """What sim/leg_rig.py assumes now (the numbers each test is compared with)."""
    try:
        if str(R) not in sys.path:
            sys.path.insert(0, str(R))
        from sim import leg_rig as L
        r = L.fb.P['stop_r'] / 1000.0
        return {'ARMATURE': L.ARMATURE, 'OFF_DAMPING': L.OFF_DAMPING, 'STOP_K': L.STOP_K, 'STOP_TRAVEL': L.STOP_TRAVEL,
                'stop_r_m': r, 'stop_k_n_per_mm': L.STOP_K / r ** 2 / 1000.0, 'stop_travel_mm': L.STOP_TRAVEL * r * 1000.0,
                'TYRE_SOLREF': L.TYRE_SOLREF, 'HUB_PRELOAD_N': 1200.0}
    except Exception as e:                                   # noqa: BLE001 - the fit still runs without the sim
        return {'error': f'{type(e).__name__}: {e}', 'stop_r_m': 0.058, 'HUB_PRELOAD_N': 1200.0}


def rows(name):
    p = SHEETS / name
    if not p.exists():
        return []
    with p.open() as f:
        out = []
        for r in csv.DictReader(f):
            try:
                out.append({k: (float(v) if k not in ('size', 'spot', 'direction') else v) for k, v in r.items() if v not in (None, '')})
            except ValueError:
                continue
        return out


def b1(sim: dict) -> dict:
    from rig.bench.backdrive import fit
    fr = BENCH / 'b1-friction.json'
    if not fr.exists():
        return {}
    friction = json.loads(fr.read_text())['rows']
    out = {}
    for f in sorted(BENCH.glob('b1-*.json')):
        d = json.loads(f.read_text())
        if d['condition'] == 'friction':
            continue
        out[d['condition']] = dict(fit(d['rows'], friction), sim_assumes_b=sim.get('OFF_DAMPING'),
                                   note='OFF_DAMPING is b; the table is the curve F1 asks for')
    return out


def b2(sim: dict) -> dict:
    Js = {f.stem: json.loads(f.read_text())['J_kg_m2'] for f in sorted(BENCH.glob('b2-motor*.json'))}
    if not Js:
        return {}
    J = float(np.mean(list(Js.values())))
    return {'per_motor': Js, 'J_kg_m2': J, 'ARMATURE': J, 'sim_assumes': sim.get('ARMATURE'),
            'pass_within_20pct': None if not sim.get('ARMATURE') else abs(J / sim['ARMATURE'] - 1) <= 0.2}


def b3(sim: dict) -> dict:
    r = rows('b3.csv')
    if not r:
        return {}
    F = np.array([x['force_n'] for x in r])
    d = np.array([x['deflection_mm'] for x in r])
    cyc = sorted({int(x['cycle']) for x in r})
    first = [x for x in r if int(x['cycle']) == cyc[0]]
    lin = [x for x in first if x['force_n'] <= 0.5 * F.max()]           # the first cycle's lower half: the sleeve alone
    k = float(np.polyfit([x['deflection_mm'] for x in lin], [x['force_n'] for x in lin], 1)[0]) if len(lin) >= 2 else None

    def at_zero(c):
        rr = [x for x in r if int(x['cycle']) == c]
        return min(rr, key=lambda x: x['force_n'])['deflection_mm']
    out = {'k_n_per_mm': k, 'travel_at_max_mm': float(d.max()), 'max_force_n': float(F.max()), 'cycles': len(cyc),
           'permanent_set_mm': float(at_zero(cyc[-1]) - at_zero(cyc[0])),
           'sim_assumes_k_n_per_mm': sim.get('stop_k_n_per_mm'), 'sim_assumes_travel_mm': sim.get('stop_travel_mm')}
    if k:
        rm = sim['stop_r_m']
        out['STOP_K'] = k * 1000.0 * rm ** 2
        out['pass_k_within_0.5_2x'] = None if not sim.get('stop_k_n_per_mm') else 0.5 <= k / sim['stop_k_n_per_mm'] <= 2.0
    return out


def b4(sim: dict) -> dict:
    r = rows('b4.csv')
    if not r:
        return {}
    out = {}
    for size in sorted({x['size'] for x in r}):
        s = [x for x in r if x['size'] == size and 'tension_n' in x and 'torque_nm' in x]
        po = [x['pullout_n'] for x in r if x['size'] == size and 'pullout_n' in x]
        d_mm = {'M5': 5.0, 'M8': 8.0}.get(size, float('nan'))
        if len(s) >= 2:
            slope = float(np.polyfit([x['torque_nm'] for x in s], [x['tension_n'] for x in s], 1)[0])     # N per N m
            K = 1000.0 / (slope * d_mm) if slope else None                                                # the nut factor T = K F d
        else:
            slope, K = None, None
        need = sim.get('HUB_PRELOAD_N', 1200.0)
        out[size] = {'n_per_nm': slope, 'nut_factor_K': K, 'torque_for_preload_nm': (need / slope) if slope else None,
                     'preload_n': need, 'pullout_min_n': min(po) if po else None,
                     'pullout_mean_n': float(np.mean(po)) if po else None,
                     'pass_pullout_2x_preload': (min(po) >= 2 * need) if po else None}
    return out


def b5(sim: dict) -> dict:
    r = rows('b5.csv')
    if not r:
        return {}
    load = [x for x in r if x.get('direction', 'load') == 'load']
    unl = [x for x in r if x.get('direction') == 'unload']
    F = np.array([x['force_n'] for x in load])
    d = np.array([x['deflection_mm'] for x in load])
    k = float(np.polyfit(d, F, 1)[0]) if len(load) >= 2 else None
    hyst = None
    if len(unl) >= 2 and len(load) >= 2:
        def area(rr):
            rr = sorted(rr, key=lambda x: x['deflection_mm'])
            return float(np.trapezoid([x['force_n'] for x in rr], [x['deflection_mm'] for x in rr]))
        a_l, a_u = area(load), area(unl)
        hyst = (a_l - a_u) / a_l if a_l else None
    return {'k_n_per_mm': k, 'hysteresis': hyst, 'sim_assumes': f"solref {sim.get('TYRE_SOLREF')} (about 100-250 N/mm)",
            'regenerate_predictions_first': None if k is None else k < 100.0,
            'note': 'under 100 N/mm: the landing loads fall; regenerate the drop test\'s predictions before S4'}


def b6(sim: dict) -> dict:
    r = rows('b6.csv')
    if not r:
        return {}
    Rs = []
    for x in r:
        i = x['v_loaded'] / x['r_load_ohm']
        Rs.append((x['v_open'] - x['v_loaded']) / i)
    Rint = float(np.median(Rs))
    return {'r_int_ohm': Rint, 'v_start_max_dynamic': round(44.5 - 40.0 * Rint, 1),
            'note': 'jumps and drops start at or under this; rig/run.py --r-int takes the resistance'}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.bench.fit_params')
    ap.add_argument('--templates', action='store_true')
    a = ap.parse_args(argv)
    if a.templates:
        SHEETS.mkdir(parents=True, exist_ok=True)
        for name, cols in TEMPLATES.items():
            p = SHEETS / name
            if not p.exists():
                p.write_text(','.join(cols) + '\n')
        print(f'blank sheets in {SHEETS}')
        return 0
    sim = assumed()
    doc = {'sim_assumes': sim, 'B1_backdrive': b1(sim), 'B2_inertia': b2(sim), 'B3_sleeve': b3(sim), 'B4_inserts': b4(sim),
           'B5_tyre': b5(sim), 'B6_pack': b6(sim)}
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / 'sim-params.json').write_text(json.dumps(doc, indent=1, default=float) + '\n')
    for k, v in doc.items():
        if k != 'sim_assumes':
            print(f'{k}: {"no data yet" if not v else json.dumps(v, default=float)[:160]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
