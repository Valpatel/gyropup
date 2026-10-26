"""Simulate a design: build its physics model and run the scenario suite.

    python tools/simulate.py designs/default.json                # every scenario
    python tools/simulate.py designs/default.json --only stand push --video
    python tools/simulate.py --all                               # every design in designs/

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


def simulate(design: Path, only=None, video=False) -> dict:
    design = Path(design).resolve()
    info = build(design)
    xml = R / 'build' / 'sim' / design.stem / 'robot.xml'
    out = R / 'exports' / 'sim' / design.stem
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    suite = dict(SCENARIOS)
    if info.get('head_payload'):
        suite['recoil'] = recoil_scenario(info)
    for name, sc in suite.items():
        if only and name not in only:
            continue
        if sc.needs_tail and not info.get('tail'):
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
    prev.update(results)
    summary = {'design': info['design'], 'name': info['name'], 'mass_kg': round(info['total_mass_kg'], 3),
               'mass_reconciles': info['mass_reconciles'], 'scenarios': prev,
               'passed': sum(1 for s in prev.values() if s['pass']), 'total': len(prev), 'estimates': info['estimates'],
               'physical_test': False}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?', default=str(R / 'designs/default.json'))
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
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
