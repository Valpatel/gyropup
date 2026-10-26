"""Evaluate one design candidate end to end, for the optimiser (tools/iterate.py), in its own folder.

    GYROPUP_EXPORTS=<trial dir> GYROPUP_CAD_PARAMS=<trial dir>/params.json .venv/bin/python tools/trial_eval.py <design.json>

Steps (each one can reject the candidate, and the later ones are skipped):
  1. the designer's checks (tools/derive.mjs): any 'fail' (a voltage outside a motor's range, too little torque, ...)
  2. the CAD (cad/build.py --fast): masses, the real stack across the hip, the parts list
  3. clashes between the leg parts from full crouch to full stand
  4. the physics scenarios (tools/simulate.py) on the model built from that CAD
  5. stiffness and strength (cad/studies.py) under that run's worst joint loads and the design floor
  6. the cable routes (cad/cables.py)
Writes <trial dir>/metrics.json and prints it.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd, timeout):
    return subprocess.run(cmd, cwd=R, capture_output=True, text=True, timeout=timeout, env=os.environ.copy())


def main(design: Path) -> dict:
    out = Path(os.environ['GYROPUP_EXPORTS'])
    out.mkdir(parents=True, exist_ok=True)
    m = {'design': str(design.relative_to(R)), 'stage': 'start', 'ok': False, 'reasons': [], 'seconds': {}}

    def stage(name, fn):
        t0 = time.time()
        try:
            fn()
        except Exception as e:                          # a crash in a stage fails the candidate, with the reason
            m['reasons'].append(f'{name} crashed: {type(e).__name__}: {e}'[:300])
        finally:
            m['seconds'][name] = round(time.time() - t0, 1)

    def designer():
        r = run(['node', 'tools/derive.mjs', str(design)], 120)
        if r.returncode:
            raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'derive.mjs failed')
        ev = json.loads(r.stdout)
        fails = [c['text'] for c in ev['checks'] if c['level'] == 'fail']
        m.update(designer_mass_kg=ev['mass']['total_kg'], cost_usd=round(ev['cost']['total_usd']), designer_fails=fails,
                 leg_torque_margin=ev['legs'].get('peak_margin'), runtime_min=ev['power'].get('runtime_min'))
        if fails:
            m['reasons'] += fails
    stage('designer', designer)
    if m['reasons']:
        return finish(m, out, 'designer')

    def cad():
        r = run([PY, 'cad/build.py', str(design), '--fast'], 900)
        if r.returncode:
            m['reasons'].append('CAD build failed: ' + r.stderr.strip().splitlines()[-1][:300])
            return
        ml = json.loads((out / 'mech-layout.json').read_text())
        mp = json.loads((out / 'mass-properties.json').read_text())
        m.update(track_mm=round(ml['track_mm']), made_kg=round(mp['made_total_g'] / 1000, 3), stack_notes=ml['notes'])
    stage('cad', cad)
    if m['reasons']:
        return finish(m, out, 'cad')

    def clashes():
        code = ('import sys, json; sys.path.insert(0, "cad"); sys.path.insert(0, "."); import leg; '
                f'print(json.dumps(leg.clashes_for_design("{design}")))')
        r = run([PY, '-c', code], 900)
        if r.returncode:
            m['reasons'].append('clash check failed: ' + r.stderr.strip().splitlines()[-1][:300])
            return
        hits = json.loads(r.stdout.strip().splitlines()[-1])
        m['clashes'] = hits
        if hits:
            m['reasons'].append(f'{len(hits)} clashes, e.g. {hits[0]}')
    stage('clashes', clashes)
    if m['reasons']:
        return finish(m, out, 'clashes')

    def sims():
        r = run([PY, 'tools/simulate.py', str(design)], 1800)
        sm = json.loads((out / 'sim' / design.stem / 'summary.json').read_text())
        m.update(model_mass_kg=sm['mass_kg'], scenarios_passed=sm['passed'], scenarios_total=sm['total'],
                 scenario_fails={k: v['reasons'] for k, v in sm['scenarios'].items() if not v['pass']})
        if sm['passed'] < sm['total']:
            m['reasons'].append(f"{sm['total'] - sm['passed']} scenarios fail: {', '.join(m['scenario_fails'])}")
    stage('sims', sims)
    if m['reasons']:
        return finish(m, out, 'sims')

    def fea():
        r = run([PY, 'cad/studies.py', str(design), '--mesh', '3.5'], 1800)
        if r.returncode:
            m['reasons'].append('FEA failed: ' + r.stderr.strip().splitlines()[-1][:300])
            return
        fs = json.loads((out / 'fea' / 'summary.json').read_text())
        v = fs['verdict']['al6061']
        m.update(min_safety_factor=v['min_safety_factor'], wheel_deflection_mm=v['wheel_deflection_mm'],
                 safety_factors={f"{x['part']} {x['case']}": x['safety_factor'] for x in fs['results']})
        if v['min_safety_factor'] < fs['targets']['metal_sf']:
            m['reasons'].append(f"safety factor {v['min_safety_factor']} < {fs['targets']['metal_sf']}")
        if v['wheel_deflection_mm'] > fs['targets']['wheel_deflection_mm']:
            m['reasons'].append(f"wheel deflection {v['wheel_deflection_mm']} mm > {fs['targets']['wheel_deflection_mm']} mm")
    stage('fea', fea)
    if m['reasons']:
        return finish(m, out, 'fea')

    def cables():
        r = run([PY, 'cad/cables.py', str(design)], 900)
        if r.returncode:
            m['reasons'].append('cable check failed: ' + r.stderr.strip().splitlines()[-1][:300])
            return
        c = json.loads((out / 'cables.json').read_text())['wheel']
        m.update(cable_clearance_mm=min(v['clearance_mm'] for v in c['clearance'].values()), cable_ok=c['clearance_ok'] and c['bend_radius']['ok'])
        if not m['cable_ok']:
            m['reasons'].append(f"cables: clearance {m['cable_clearance_mm']} mm")
    stage('cables', cables)
    return finish(m, out, 'done')


def finish(m, out, stage):
    m['stage'] = stage
    m['ok'] = not m['reasons'] and stage == 'done'
    (out / 'metrics.json').write_text(json.dumps(m, indent=1) + '\n')
    print(json.dumps(m))
    return m


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
