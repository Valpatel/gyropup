"""Evaluate every design in designs/ with the designer's model and write exports/designs.json for the project site.

    python tools/summarize_designs.py

Runs `node tools/derive.mjs <design>` (the same model the web designer uses) for each designs/*.json.
"""
from pathlib import Path
import json, subprocess, sys

R = Path(__file__).resolve().parents[1]


def fmt(v, digits=0):
    return None if v is None else round(v, digits) if digits else round(v)


def summarize(path: Path) -> dict:
    design = json.loads(path.read_text())
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(path)], capture_output=True, text=True, check=True)
    r = json.loads(out.stdout)
    levels = {lvl: sum(1 for c in r['checks'] if c['level'] == lvl) for lvl in ('ok', 'warn', 'fail')}
    lvl_of = {c['id']: c['level'] for c in r['checks']}
    legs, wheels, power = r['legs'], r['wheels'], r['power']
    metrics = [
        {'label': 'chassis & actuators', 'value': f"${fmt(r['cost']['chassis_actuators_usd']):,}"},
        {'label': 'sensors & compute', 'value': f"${fmt(r['cost']['sensors_compute_usd']):,}"},
        {'label': 'mass', 'value': fmt(r['mass']['total_kg'], 1), 'unit': 'kg', 'estimate': True},
        {'label': 'standing hip height', 'value': fmt(legs['stand_hip_mm']), 'unit': 'mm'},
        {'label': 'leg torque margin (dynamic)', 'value': fmt(legs.get('peak_margin'), 1), 'unit': '×', 'estimate': True,
         'level': lvl_of.get('leg-dynamic', '')},
        {'label': 'lean it can catch', 'value': fmt(wheels.get('catch_lean_deg')), 'unit': '°', 'level': lvl_of.get('balance', '')},
        {'label': 'jump', 'value': fmt(legs.get('jump_height_mm')), 'unit': 'mm', 'estimate': True, 'level': lvl_of.get('leg-speed', '')},
        {'label': 'runtime', 'value': fmt(power.get('runtime_min')), 'unit': 'min', 'estimate': True},
    ]
    name = {l['slot']: l['name'] for l in r['lines']}
    summary = (f"{name.get('leg_actuator')} legs, {name.get('wheel_motor')} wheels, {name.get('battery')} battery. "
               f"{len(r['parts'])} printed part types, {round(sum(p['mass_g'] * p['qty'] for p in r['parts']))} g of filament.")
    out = {'name': design.get('name', path.stem), 'file': path.relative_to(R).as_posix(), 'verdict': r['verdict'],
           'summary': summary, 'metrics': metrics, 'checks': levels, 'link': 'designer/',
           'links': [{'title': 'Simulate in 3D', 'href': f'designer/sim.html?design={path.relative_to(R).as_posix()}'}]}
    sim = R / 'exports' / 'sim' / path.stem / 'summary.json'
    if sim.is_file():
        sm = json.loads(sim.read_text())
        out['badges'] = [{'label': f"{n} {'pass' if v['pass'] else 'fail'}", 'level': 'done' if v['pass'] else 'fail',
                          'title': '; '.join(v.get('reasons', [])) or v.get('title', n)} for n, v in sm['scenarios'].items()]
        out['metrics'].append({'label': 'simulated scenarios passed', 'value': f"{sm['passed']}/{sm['total']}",
                               'level': '' if sm['passed'] == sm['total'] else 'fail'})
        out['links'].insert(0, {'title': 'Simulation results', 'href': f'designer/results.html#{path.stem}'})
        if sm['passed'] < sm['total'] and out['verdict'] == 'ok':
            out['verdict'] = 'warn'
    return out


def main():
    designs = [summarize(p) for p in sorted((R / 'designs').glob('*.json'))]
    (R / 'exports').mkdir(exist_ok=True)
    (R / 'exports/designs.json').write_text(json.dumps({'designs': designs}, indent=1) + '\n')
    print(f'wrote exports/designs.json: {len(designs)} designs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
