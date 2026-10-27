"""Judge a rig run against rig/criteria.json and the simulation's prediction; overlay the two.

    python -m rig.compare exports/rig/runs/<run>.json                  # verdict into the run's JSON, printed
    python -m rig.compare exports/rig/runs/<run>.json --plot           # and <run>.png: the run over the prediction

The prediction is exports/rig/predictions.json (the rig's own controller and configuration in the simulation:
python -m rig.run --predict), falling back to exports/leg/rig-results.json (sim/leg_rig.py at 13.1 kg). Every
metric is measured the same way on the prediction's log and on the run's, so they compare like for like.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np

from rig import log as runlog

R = Path(__file__).resolve().parents[1]
CRITERIA = json.loads((R / 'rig' / 'criteria.json').read_text())
PRED_FILE = R / 'exports' / 'rig' / 'predictions.json'
REF_FILE = R / 'exports' / 'leg' / 'rig-results.json'


def _win(a, from_s=None, to_s=None, t0=0.0):
    t = a['t']
    m = np.ones_like(t, dtype=bool)
    if from_s is not None:
        m &= t >= t0 + from_s
    if to_s is not None:
        m &= t <= t0 + to_s
    return m


def touchdown(a, test: str) -> Optional[float]:
    """When the wheel lands: the controller's own estimate in a jump; the leg starting to compress in a drop."""
    t = a['t']
    if test.startswith('jump'):
        i = np.flatnonzero(a['phase'] == runlog.PHASES.index('land'))
        return float(t[i[0]]) if len(i) else None
    L = a['L']
    i = np.flatnonzero(L < L[0] - 0.002)
    return float(t[i[0]]) if len(i) else None


def cut_time(a) -> Optional[float]:
    i = np.flatnonzero(a['phase'] == runlog.PHASES.index('off'))
    if len(i):
        return float(a['t'][i[0]])
    i = np.flatnonzero(a['ok'] < 0.5)                          # on the rig: the motors fall silent when the power goes
    return float(a['t'][i[0]]) if len(i) else None


def metrics(a: dict, test: str) -> dict:
    """Everything the criteria look at, measured from a log."""
    t, L = a['t'], a['L']
    m = {'peak_motor_nm': float(np.nanmax(np.abs(np.r_[a['tau_f'], a['tau_r']])))}
    if np.isfinite(a.get('vbus', np.array([np.nan]))).any():
        m['vbus_range_v'] = [float(np.nanmin(a['vbus'])), float(np.nanmax(a['vbus']))]
    h = a.get('rail_mm')
    if h is None or not np.isfinite(h).any():
        h = a.get('height_mm')
    if h is not None and np.isfinite(h).any():
        hh = h[np.isfinite(h)]
        m['jump_height_mm'] = float(np.max(hh) - hh[0])
    if test == 'stand_up':
        w = _win(a, 2.0)
        m['hold_err_mm'] = float(np.max(np.abs(L[w] - 0.300)) * 1000)
        m['hold_pp_mm'] = float(np.ptp(L[w]) * 1000)
    if test == 'squat':
        w = _win(a, 0.5)
        m['track_err_mm'] = float(np.nanmax(np.abs(L[w] - a['L_cmd'][w])) * 1000)
    if test.startswith('jump') or test == 'drop_150':
        target = 0.250 if test.startswith('jump') else 0.300
        tol = 0.015 if test.startswith('jump') else 0.010
        td = touchdown(a, test)
        m['touchdown_s'] = td
        if td is not None:
            after = t >= td
            out = np.flatnonzero(after & (np.abs(L - target) > tol))
            m['settle_s'] = float(t[out[-1]] - td) if len(out) else 0.0
            if test == 'drop_150':
                m['dip_mm'] = float((0.300 - np.nanmin(L[after])) * 1000)
    if test.startswith('power_off'):
        tc = cut_time(a)
        m['cut_s'] = tc
        if tc is not None:
            after = t >= tc
            Lm = np.nanmin(L[after])
            reach = np.flatnonzero(after & (L <= Lm + 0.001))
            m['fall_time_s'] = float(t[reach[0]] - tc) if len(reach) else None
            m['L_min_mm'] = float(Lm * 1000)
    return m


def judge(test: str, a: dict, pred: Optional[dict] = None) -> list:
    """[{what, ok, value, limit}] for the test's checks; ok None when the run cannot show it."""
    spec = CRITERIA['tests'].get(test)
    if not spec:
        return []
    m = metrics(a, test)
    pm = (pred or {}).get('metrics', {})
    out = []
    for c in spec['checks']:
        k = c['kind']
        row = {'id': spec['id'], 'what': c['what'], 'ok': None, 'value': None, 'limit': None}
        sig = c.get('signal')
        if c.get('needs') and not np.isfinite(a.get(c['needs'], np.array([np.nan]))).any():
            row['value'] = 'not measured'
            out.append(row)
            continue
        w = _win(a, c.get('from_s'), c.get('to_s'))
        if k == 'hold':
            v = float(np.nanmax(np.abs(a[sig][w] - c['target'])))
            row.update(value=round(v * 1000, 2), limit=c['tol'] * 1000, ok=v <= c['tol'])
        elif k == 'max_abs':
            v = max(float(np.nanmax(np.abs(a[s]))) for s in sig)
            row.update(value=round(v, 2), limit=c['max'], ok=v <= c['max'])
        elif k == 'pp':
            v = float(np.ptp(a[sig][w]))
            row.update(value=round(v * 1000, 2), limit=c['max'] * 1000, ok=v <= c['max'])
        elif k == 'range':
            x = a[sig][w]
            x = x[np.isfinite(x)]
            if not len(x):
                row['value'] = 'not measured'
            else:
                lo, hi = float(np.min(x)), float(np.max(x))
                ok = (c.get('min') is None or lo >= c['min']) and (c.get('max') is None or hi <= c['max'])
                row.update(value=[round(lo, 2), round(hi, 2)], limit=[c.get('min'), c.get('max')], ok=ok)
        elif k == 'track':
            v = float(np.nanmax(np.abs(a[sig][w] - a[c['ref']][w])))
            row.update(value=round(v * 1000, 2), limit=c['tol'] * 1000, ok=v <= c['tol'])
        elif k == 'jump':
            v = m.get('jump_height_mm')
            row.update(value=None if v is None else round(v, 1), limit=[c['min'], c['max']],
                       ok=None if v is None else c['min'] <= v <= c['max'])
        elif k == 'settle':
            v = m.get('settle_s')
            row.update(value=None if v is None else round(v, 3), limit=c['within_s'], ok=None if v is None else v <= c['within_s'])
        elif k == 'dip':
            v, p = m.get('dip_mm'), pm.get('dip_mm')
            row.update(value=None if v is None else round(v, 1), limit=None if p is None else [round(p * (1 - c['rel_tol']), 1), round(p * (1 + c['rel_tol']), 1)],
                       ok=None if (v is None or p is None) else abs(v - p) <= c['rel_tol'] * p)
        elif k == 'fall_time':
            v, p = m.get('fall_time_s'), pm.get('fall_time_s')
            row.update(value=None if v is None else round(v, 3), limit=None if p is None else [round(p * (1 - c['rel_tol']), 3), round(p * (1 + c['rel_tol']), 3)],
                       ok=None if (v is None or p is None) else abs(v - p) <= c['rel_tol'] * p)
        out.append(row)
    return out


def reproduce_report(results: dict, ref: Optional[dict] = None) -> dict:
    """T7: each scenario's peaks against rig-results.json, and the acceptance."""
    ref = ref or json.loads(REF_FILE.read_text())['scenarios']
    spec = CRITERIA['reproduce']
    rows, ok = {}, True
    for name, r in results.items():
        a = ref.get(name)
        if not a:
            continue
        d = {}
        for k in spec['peak_keys'] + ['jump_height_mm', 'peak_stop_nm']:
            if a.get(k) is None or r.get(k) is None:
                continue
            d[k] = {'ref': a[k], 'run': r[k], 'diff_pct': round(100 * (r[k] - a[k]) / a[k], 2) if a[k] else None}
        d['L_range_mm'] = {'ref': a['L_range_mm'], 'run': r['L_range_mm']}
        verdict = []
        if name in spec['peaks_within_pct']:
            lim = spec['peaks_within_pct'][name]
            bad = [k for k in spec['peak_keys'] if k in d and d[k]['diff_pct'] is not None and abs(d[k]['diff_pct']) > lim]
            verdict.append({'what': f'peaks within {lim} %', 'ok': not bad, 'outside': bad})
            ok &= not bad
        if name in spec['jump_height_within_mm']:
            lim = spec['jump_height_within_mm'][name]
            dh = abs(r['jump_height_mm'] - a['jump_height_mm'])
            verdict.append({'what': f'jump height within {lim} mm', 'ok': dh <= lim, 'diff_mm': round(dh, 2)})
            ok &= dh <= lim
        d['verdict'] = verdict
        rows[name] = d
    return {'scenarios': rows, 'all_ok': bool(ok)}


def overlay(a: dict, ref_series: Optional[dict], path: Path, title: str = '', ref_label: str = 'prediction') -> Path:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    t = a['t']
    ax[0].plot(t, a['L'] * 1000, lw=1.4, label='run: leg length')
    if np.isfinite(a['L_cmd']).any():
        ax[0].plot(t, a['L_cmd'] * 1000, lw=0.8, ls='--', label='command')
    ax[1].plot(t, a['tau_f'], lw=1.2, label='run: front')
    ax[1].plot(t, a['tau_r'], lw=1.2, label='run: rear')
    h = a.get('rail_mm') if a.get('rail_mm') is not None and np.isfinite(a['rail_mm']).any() else a.get('height_mm')
    if h is not None and np.isfinite(h).any():
        ax[2].plot(t, h - h[np.isfinite(h)][0], lw=1.2, label='run: carriage')
    if ref_series:
        rt = np.asarray(ref_series['t'])
        ax[0].plot(rt, ref_series['L_mm'], lw=1.0, color='k', alpha=0.6, label=ref_label)
        ax[1].plot(rt, ref_series['tau_f'], lw=0.9, color='k', alpha=0.6, label=ref_label)
        ax[1].plot(rt, ref_series['tau_r'], lw=0.9, color='k', alpha=0.35)
        rail = np.asarray(ref_series['rail_mm'])
        ax[2].plot(rt, rail - rail[0], lw=1.0, color='k', alpha=0.6, label=ref_label)
    ax[0].set_ylabel('leg, mm')
    ax[1].set_ylabel('motor torque, N m')
    ax[2].set_ylabel('carriage rise, mm')
    ax[2].set_xlabel('s')
    for x in ax:
        x.grid(alpha=0.3)
        x.legend(loc='best', fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def prediction(test: str) -> Optional[dict]:
    if PRED_FILE.exists():
        d = json.loads(PRED_FILE.read_text())
        p = d.get('tests', {}).get(test)
        if p:
            return {**p, 'from': f"exports/rig/predictions.json ({d['half_mass_kg']} kg, the rig's controller)"}
    ref = json.loads(REF_FILE.read_text())['scenarios'].get(test)
    return {'summary': ref, 'series': ref.get('series'), 'metrics': {},
            'from': 'exports/leg/rig-results.json (sim/leg_rig.py, 13.1 kg)'} if ref else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m rig.compare')
    ap.add_argument('run')
    ap.add_argument('--plot', action='store_true')
    a = ap.parse_args(argv)
    doc, arr = runlog.load(a.run)
    test = doc['meta']['test']
    pred = prediction(test)
    verdict = judge(test, arr, pred)
    doc['verdict'] = verdict
    doc['metrics'] = metrics(arr, test)
    if pred:
        doc['prediction_from'] = pred.get('from', str(PRED_FILE.relative_to(R)))
    stem = Path(a.run).with_suffix('')
    if a.plot:
        doc['plot'] = str(overlay(arr, (pred or {}).get('series'), stem.with_suffix('.png'),
                                  f"{doc['meta']['backend']} {test}, {doc['meta'].get('half_mass_kg')} kg",
                                  'expected: ' + (pred or {}).get('from', '?').split(' (')[0].split('/')[-1]))
    stem.with_suffix('.json').write_text(json.dumps(doc, indent=1, default=runlog._json) + '\n')
    for v in verdict:
        mark = 'PASS' if v['ok'] else ('----' if v['ok'] is None else 'FAIL')
        print(f"{mark} {v['id']} {v['what']}: {v['value']} (limit {v['limit']})")
    return 0 if all(v['ok'] is not False for v in verdict) else 1


if __name__ == '__main__':
    raise SystemExit(main())
