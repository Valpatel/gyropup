"""Simulate a design: build its physics model and run the scenario suite.

    python tools/simulate.py designs/default.json                # every scenario
    python tools/simulate.py designs/default.json --only stand push --video
    python tools/simulate.py --v2 [--only ...] [--video]        # Gyropup v2: five-bar legs (sim/robot_v2.py)

Writes exports/sim/<design>/<scenario>.json (metrics and replay frames), <scenario>.mp4 with --video, and summary.json.
Swap a part in the design file (or in the designer) and run it again: the model, the controller and the limits all
follow the parts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
os.environ.setdefault('MUJOCO_GL', 'egl')

from sim.model import build                     # noqa: E402
from sim.scenarios import SCENARIOS, recoil_scenario, run          # noqa: E402


def simulate(design: Path, only=None, video=False, v2=False) -> dict:
    exports = Path(os.environ['GYROPUP_EXPORTS']).resolve() if os.environ.get('GYROPUP_EXPORTS') else R / 'exports'
    if v2:                                               # Gyropup v2: two five-bar legs, the turret, an interim body
        from sim.robot_v2 import build as build_v2
        info = build_v2()
        xml = R / 'build' / 'sim' / 'v2' / 'robot.xml'
        out = exports / 'sim' / 'v2'
    else:
        design = Path(design).resolve()
        info = build(design)
        xml = R / 'build' / 'sim' / design.stem / 'robot.xml'
        out = exports / 'sim' / design.stem
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    suite = dict(SCENARIOS)
    if info.get('head_payload'):
        suite['recoil'] = recoil_scenario(info)
    for name, sc in suite.items():
        if only and name not in only:
            continue
        t0 = time.time()
        res = run(xml, info, sc, video=(out / f'{name}.mp4') if video else None)
        res['wall_s'] = round(time.time() - t0, 2)
        (out / f'{name}.json').write_text(json.dumps(res) + '\n')
        results[name] = {k: v for k, v in res.items() if k not in ('frames', 'link_loads', 'terrain')}
        worst = max(res['motors'].items(), key=lambda kv: kv[1]['of_peak'])
        print(f"  {name:6} {'PASS' if res['pass'] else 'FAIL'}  max lean {res['max_theta_deg']:5.1f}°  "
              f"worst motor {worst[0]} {worst[1]['of_peak'] * 100:4.0f}% of peak  ({res['wall_s']} s)"
              + (f"  — {'; '.join(res['reasons'])}" if res['reasons'] else ''))
    prev = {}
    if (out / 'summary.json').is_file():
        prev = json.loads((out / 'summary.json').read_text()).get('scenarios', {})
    prev = {k: v for k, v in prev.items() if k in suite}       # scenarios that no longer exist drop out
    prev.update(results)
    summary = {'design': info['design'], 'name': info['name'], 'mass_kg': round(info['total_mass_kg'], 3),
               'mass_reconciles': info['mass_reconciles'], 'scenarios': prev,
               'passed': sum(1 for s in prev.values() if s['pass']), 'total': len(prev), 'estimates': info['estimates'],
               'physical_test': False}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    if v2:                                               # the body's evidence (D62): exports/sim/ is not kept in git
        body_evidence(summary, info, exports)
    return summary


def body_evidence(summary, info, exports):
    """exports/body/sim-v2.json: each scenario's verdict, its worst motor and the body's impact, with the model's mass
    and its reconciliation against the body's ledger, the bus voltage and the date: what the body workstream commits."""
    import datetime
    rows = {}
    for n, r in summary['scenarios'].items():
        worst = max(r['motors'].items(), key=lambda kv: kv[1]['of_peak'])
        rows[n] = {'pass': r['pass'], 'reasons': r['reasons'], 'max_theta_deg': r['max_theta_deg'], 'top_speed_mps': r['top_speed_mps'],
                   'worst_motor': [worst[0], worst[1]['peak_torque_nm'], worst[1]['of_peak']], 'saturated_s': max(m['saturated_s'] for m in r['motors'].values()),
                   'body_impact_peak_n': r.get('body_impact_peak_n'), 'fell_at': r.get('fell_at'), 'lqr': r.get('lqr')}
    ev = {'date': datetime.date.today().isoformat(), 'model': 'sim/robot_v2.py (the body as built, D62)', 'mass_kg': summary['mass_kg'],
          'ledger_kg': (info.get('ledger') or {}).get('total_kg'), 'mass_reconciles': summary['mass_reconciles'], 'bus_v': info.get('bus_v'),
          'com_mm': info.get('com_mm'), 'track_mm': info.get('track_mm'), 'passed': summary['passed'], 'total': summary['total'],
          'scenarios': rows, 'note': 'tools/simulate.py --v2 (the full results and videos: exports/sim/v2/, not in git)'}
    f = exports / 'body' / 'sim-v2.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(ev, indent=1) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?', default=str(R / 'designs/default.json'))
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--v2', action='store_true', help='Gyropup v2 (five-bar legs, sim/robot_v2.py)')
    a = ap.parse_args()
    if a.v2:
        print('Gyropup v2:')
        s = simulate(None, a.only, a.video, v2=True)
        print(f"  {s['passed']}/{s['total']} scenarios pass; model {s['mass_kg']} kg")
        return 0 if s['passed'] == s['total'] else 1
    designs = sorted((R / 'designs').glob('*.json')) if a.all else [Path(a.design)]
    ok = True
    for d in designs:
        print(f'{d.name}:')
        s = simulate(d, a.only, a.video)
        print(f"  {s['passed']}/{s['total']} scenarios pass; model {s['mass_kg']} kg")
        ok &= s['passed'] == s['total']
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
