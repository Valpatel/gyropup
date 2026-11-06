"""The battery bay's crush pads against the power-cut falls (issue #19): what lands, how fast, and the pad that keeps the
body's impact under 3,000 N.

    python -m sim.robot_v2 && python -m sim.bay_pad_study          # -> exports/body/bay-pad-study.json
    python -m sim.bay_pad_study quick                               # the pad as designed only (no sweep)
    python -m sim.bay_pad_study depth                               # deeper pads (rebuilds the model): -> bay-pad-depth.json

sim/robot_v2.py models each of the four pads (cad/body_battery.py PAD) as a body on a slide joint under the bay's floor:
a spring k and a damper c over its stroke, then the joint's limit as the densified lattice (a stiff, critically damped
stop); its contact with the floor is stiff, so k and c are the pad's own. sim/scenarios.py's body impact counts the sum
of the four pads' floor forces at each step (what the body takes through them) with every direct contact of the base.

This study, on D69's robot (10 in hub wheels, the ledger's mass):
  1. the pad as designed in the three falls (front, back, side): the peak through the pads, each pad's peak, the
     deepest stroke, whether a pad bottomed, the speed at first touch, and the body's largest direct contact;
  2. a baseline with the pads made rigid (the old 3 mm skids' behaviour, at the pads' depth);
  3. a sweep of the crush plateau and c at the design k, stroke and rebound, of the rebound (unload_ratio) at the design k and c, and of
     the falls' pushes (x0.6 to x1.4), to show the margin round the chosen pad;
  4. the chosen pad at D71's design mass, 37.5 kg (ballast at the base's centre of mass up to it; at least 1.0 kg, which
     covers the 4.0 kg wheels or the turret's 2.55 kg head).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import mujoco
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
sys.path.insert(0, str(R / 'cad'))
from sim import scenarios as S  # noqa: E402

BUILD = R / 'build' / 'sim' / 'v2'
OUT = R / 'exports' / 'body' / 'bay-pad-study.json'
FALLS = ('fall_front', 'fall_back', 'fall_side')
P_SWEEP = (450.0, 600.0, 750.0, 1000.0, 1e9)   # N a pad: the crush plateau (1e9: a linear pad, no plateau)
C_SWEEP = (50.0, 100.0, 250.0)               # N s/m a pad
UNLOAD_SWEEP = (0.0, 0.1, 0.2, 0.3, 0.5, 1.0)  # the share of k x a pad gives back unloading (1.0: an ideal spring)
PUSHES = (0.6, 0.8, 1.2, 1.4)                # the falls' pushes scaled: how robust the landing is
DESIGN_MASS_KG = 37.5                         # D71
HEAVY_KG = 1.0                               # the ledger + 1.0 kg at the base's centre: the 4.0 kg wheels (+0.94) or the turret
                                             # branch's 2.55 kg head (+0.85); the ledger already exceeds D69's 35.5 kg design mass
LIMIT_N = 3000.0
_rec: dict = {}
_orig_step = mujoco.mj_step


def _watch(model, data):
    """After each step: the pads' deepest stroke and the speed at the first touch of any pad."""
    _orig_step(model, data)
    for j, qa, va in _rec['pads']:
        q = float(data.qpos[qa])
        _rec['max_stroke'] = max(_rec['max_stroke'], q)
    if _rec['touch'] is None:
        for ci in range(data.ncon):
            c = data.contact[ci]
            if c.geom1 in _rec['pad_geoms'] or c.geom2 in _rec['pad_geoms']:
                base = model.body('base').id
                _rec['touch'] = {'t': round(float(data.time), 3), 'base_vz_mps': round(float(data.qvel[2]), 3),
                                 'base_v_mps': round(float(np.linalg.norm(data.qvel[:3])), 3),
                                 'robot_kg': round(float(model.body_subtreemass[base]), 2)}
                break


def set_pad(xml: str, c=None, stroke=None) -> str:
    """The pads' joints with another damper c (N s/m) or stroke (mm)."""
    def sub(m):
        j = m.group(0)
        if c is not None:
            j = re.sub(r'damping="[^"]*"', f'damping="{c:.1f}"', j)
        if stroke is not None:
            j = re.sub(r'range="[^"]*"', f'range="0 {stroke / 1000.0:.5f}"', j)
        return j
    return re.sub(r'<joint name="pad_\d+" type="slide"[^>]*/>', sub, xml)


def with_ballast(xml: str, extra_kg: float) -> str:
    """The base's mass raised by extra_kg at its own centre (inertia scaled with it): the design-mass case."""
    def sub(m):
        mass = float(m.group(2))
        k = (mass + extra_kg) / mass
        full = ' '.join(f'{float(v) * k:.6g}' for v in m.group(3).split())
        return f'{m.group(1)}mass="{mass + extra_kg:.4f}" fullinertia="{full}"/>'
    return re.sub(r'(<freejoint name="root"/>\s*<inertial pos="[^"]*" )mass="([^"]*)" fullinertia="([^"]*)"/>', sub, xml, count=1)


def fall(xml_text: str, info: dict, name: str, **pad) -> dict:
    """One fall with the pads' law changed by pad (k_n_per_mm_each, plateau_n_each, unload_ratio); c is in the XML."""
    m = mujoco.MjModel.from_xml_string(xml_text)                   # robot.xml names its mesh folder itself
    pads = [(j, int(m.jnt_qposadr[j]), int(m.jnt_dofadr[j])) for j in range(m.njnt) if m.joint(j).name.startswith('pad_')]
    pad_geoms = {g for g in range(m.ngeom) if m.body(m.geom_bodyid[g]).name.startswith('pad_')}
    stroke = max((float(m.jnt_range[j][1]) for j, _, _ in pads), default=0.0)
    with tempfile.NamedTemporaryFile('w', suffix='.xml', dir=BUILD, delete=False) as f:
        f.write(xml_text)
        p = Path(f.name)
    try:
        _rec.clear()
        _rec.update(pads=pads, pad_geoms=pad_geoms, max_stroke=0.0, touch=None)
        mujoco.mj_step = _watch
        inf = {**info, 'pads': {**info['pads'], **pad}}
        r = S.run(p, inf, S.SCENARIOS[name])
    finally:
        mujoco.mj_step = _orig_step
        p.unlink()
    return {'pass': r.get('pass'), 'reasons': r.get('reasons'), 'body_impact_peak_n': r.get('body_impact_peak_n'),
            'pads_peak_n': r.get('pads_peak_n'), 'pad_each_peak_n': r.get('pad_each_peak_n'),
            'max_stroke_mm': round(_rec['max_stroke'] * 1000, 1), 'bottomed': _rec['max_stroke'] >= stroke - 1e-4,
            'first_touch': _rec['touch']}


DEPTHS = (25.0, 35.0, 45.0, 50.0)                  # pad free height (mm); the lowest controlled leg that keeps 40 mm under it
DEPTH_PLATEAUS = (600.0, 750.0, 900.0, 1050.0)
DEPTH_PUSHES = (0.6, 1.0, 1.4)


def scaled(name: str, f: float) -> str:
    """A copy of a fall with its push scaled by f, registered under a temporary name."""
    sc = S.SCENARIOS[name]
    key = f'_{name}_x{f}'
    S.SCENARIOS[key] = S.replace(sc, name=key, pushes=[S.replace(q, impulse_ns=q.impulse_ns * f) for q in sc.pushes])
    return key


def depth():
    """The pad's free height against the falls: for each depth (the model rebuilt with GYROPUP_PAD_H, stroke 0.6 h), each
    plateau at c 100 N s/m, each fall at its push x0.6, x1.0 and x1.4. A pad passes when every one of the nine stays
    under 3,000 N with nothing else failing. The model is rebuilt as designed at the end."""
    import os
    import subprocess
    out = {'limit_n': LIMIT_N, 'c_ns_per_m': 100.0, 'rows': []}
    for h in DEPTHS:
        env = dict(os.environ, GYROPUP_PAD_H=str(h))
        subprocess.run([sys.executable, '-m', 'sim.robot_v2'], cwd=R, env=env, check=True, stdout=subprocess.DEVNULL)
        xml = set_pad((BUILD / 'robot.xml').read_text(), c=100.0)
        info = json.loads((BUILD / 'model.json').read_text())
        lowest = info['fivebar']['h_range_mm'][0]                      # applied: the model's lowest leg keeps 40 mm under the pad
        for fp in DEPTH_PLATEAUS:
            row = {'h_mm': h, 'stroke_mm': round(0.6 * h, 1), 'lowest_leg_mm': lowest, 'plateau_n': fp, 'runs': {}}
            for n in FALLS:
                for f in DEPTH_PUSHES:
                    r = fall(xml, info, scaled(n, f), plateau_n_each=fp)
                    row['runs'][f'{n} x{f}'] = {k: r[k] for k in ('pass', 'reasons', 'body_impact_peak_n', 'max_stroke_mm', 'bottomed')}
            row['worst_n'] = max(v['body_impact_peak_n'] for v in row['runs'].values())
            row['all_pass'] = all(v['pass'] for v in row['runs'].values())
            row['max_stroke_mm'] = max(v['max_stroke_mm'] for v in row['runs'].values())
            out['rows'].append(row)
            print('depth', h, fp, row['worst_n'], row['max_stroke_mm'], row['all_pass'],
                  [(k, v['reasons']) for k, v in row['runs'].items() if not v['pass']], flush=True)
    subprocess.run([sys.executable, '-m', 'sim.robot_v2'], cwd=R, check=True, stdout=subprocess.DEVNULL)
    ok = [r for r in out['rows'] if r['all_pass']]
    out['verdict'] = {'passing': [(r['h_mm'], r['plateau_n'], r['worst_n']) for r in ok],
                      'shallowest_passing_h_mm': min((r['h_mm'] for r in ok), default=None)}
    (OUT.parent / 'bay-pad-depth.json').write_text(json.dumps(out, indent=1) + '\n')
    print(out['verdict'])


def main():
    if 'depth' in sys.argv[1:]:
        return depth()
    quick = 'quick' in sys.argv[1:]
    xml = (BUILD / 'robot.xml').read_text()
    info = json.loads((BUILD / 'model.json').read_text())
    pad = info['pads']
    out = {'model_kg': info.get('total_mass_kg'), 'wheel': info.get('wheel'), 'pad': pad, 'limit_n': LIMIT_N,
           'as_designed': {}, 'rigid': {}, 'sweep': [], 'heavy': {}}
    for name in FALLS:
        out['as_designed'][name] = fall(xml, info, name)
        print('as designed', name, out['as_designed'][name], flush=True)
    if not quick:
        rigid = set_pad(xml, c=500.0, stroke=0.2)                       # the pads made rigid (0.2 mm), at their depth
        for name in FALLS:
            out['rigid'][name] = fall(rigid, info, name, k_n_per_mm_each=1000.0, plateau_n_each=1e9)
            print('rigid', name, out['rigid'][name], flush=True)
        for fp in P_SWEEP:
            for c in C_SWEEP:
                x = set_pad(xml, c=c)
                row = {'plateau_n': fp, 'c_ns_per_m': c}
                for name in FALLS:
                    row[name] = fall(x, info, name, plateau_n_each=fp)
                row['worst_n'] = max(row[n]['body_impact_peak_n'] for n in FALLS)
                row['bottomed'] = any(row[n]['bottomed'] for n in FALLS)
                row['max_stroke_mm'] = max(row[n]['max_stroke_mm'] for n in FALLS)
                row['all_pass'] = all(row[n]['pass'] for n in FALLS)
                out['sweep'].append(row)
                print('sweep', fp, c, row['worst_n'], row['max_stroke_mm'], row['bottomed'], row['all_pass'], flush=True)
        out['unload_sweep'] = []                                         # the lattice's hysteresis, the least known number
        for u in UNLOAD_SWEEP:
            row = {'unload_ratio': u, **{n: fall(xml, info, n, unload_ratio=u) for n in FALLS}}
            row['worst_n'] = max(row[n]['body_impact_peak_n'] for n in FALLS)
            row['all_pass'] = all(row[n]['pass'] for n in FALLS)
            out['unload_sweep'].append(row)
            print('unload', u, row['worst_n'], row['all_pass'], [(n, row[n]['reasons']) for n in FALLS if not row[n]['pass']], flush=True)
        out['push_sweep'] = []
        for f in PUSHES:
            row = {'push_scale': f}
            for n in FALLS:
                sc = S.SCENARIOS[n]
                S.SCENARIOS['_scaled'] = S.replace(sc, name=f'{n}_x{f}', pushes=[S.replace(q, impulse_ns=q.impulse_ns * f) for q in sc.pushes])
                row[n] = fall(xml, info, '_scaled')
            S.SCENARIOS.pop('_scaled', None)
            row['all_pass'] = all(row[n]['pass'] for n in FALLS)
            row['worst_n'] = max(row[n]['body_impact_peak_n'] for n in FALLS)
            out['push_sweep'].append(row)
            print('push', f, row['worst_n'], row['all_pass'], [(n, row[n]['reasons']) for n in FALLS if not row[n]['pass']], flush=True)
        extra = max(HEAVY_KG, DESIGN_MASS_KG - info['total_mass_kg'])
        xb = with_ballast(xml, extra)
        out['heavy'] = {'kg': round(info['total_mass_kg'] + extra, 2), 'ballast_kg': round(extra, 3)}
        for name in FALLS:
            out['heavy'][name] = fall(xb, info, name)
            print('heavy', name, out['heavy'][name], flush=True)
    worst = max(v['body_impact_peak_n'] for v in out['as_designed'].values())
    out['verdict'] = {'worst_fall_n': worst, 'pass': worst <= LIMIT_N and all(v['pass'] for v in out['as_designed'].values()),
                      'falls_pass': {n: v['pass'] for n, v in out['as_designed'].items()},
                      'bottomed': any(v['bottomed'] for v in out['as_designed'].values()),
                      'max_stroke_mm': max(v['max_stroke_mm'] for v in out['as_designed'].values()),
                      'heavy_worst_n': max((v['body_impact_peak_n'] for v in out['heavy'].values() if isinstance(v, dict)), default=None),
                      'rigid_worst_n': max((v['body_impact_peak_n'] for v in out['rigid'].values()), default=None)}
    OUT.write_text(json.dumps(out, indent=1) + '\n')
    print(out['verdict'])


if __name__ == '__main__':
    main()
