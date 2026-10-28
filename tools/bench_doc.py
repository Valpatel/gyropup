"""Fill the generated tables in docs/leg-bench-tests.md from the files they come from, so the page never drifts:

    .venv/bin/python tools/bench_doc.py

  <!-- gen:assumes -->      what sim/leg_rig.py assumes for each bench test (rig/bench/fit_params.py assumed())
  <!-- gen:predictions -->  the rig tests' predicted numbers at the design mass (exports/rig/predictions.json)
  <!-- gen:criteria -->     each rig test's pass/fail checks (rig/criteria.json) with the prediction's own value

Each section runs from its marker to the matching <!-- /gen:... --> and is rewritten whole.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
DOC = R / 'docs' / 'leg-bench-tests.md'
PRED = R / 'exports' / 'rig' / 'predictions.json'
CRIT = R / 'rig' / 'criteria.json'

NAMES = {'stand_up': 'S1 stand-up', 'squat': 'S2 squat', 'jump': 'S3 jump', 'drop_150': 'S4 drop 150 mm',
         'power_off': 'S5 power cut, undamped', 'power_off_damped': 'S5 power cut, damped',
         'power_off_S6': 'S6 power cut onto the stops, undamped', 'power_off_damped_S6': 'S6 power cut onto the stops, damped',
         'tyre_press': 'B5 tyre press (on the rig)'}


def fmt(v, nd=0):
    if v is None:
        return '-'
    if isinstance(v, (list, tuple)):
        return '-'.join(fmt(x, nd) for x in v)
    if isinstance(v, float):
        return f'{v:,.{nd}f}'
    return str(v)


def assumes() -> str:
    from rig.bench.fit_params import assumed
    a = assumed()
    if 'error' in a:
        return f'(sim/leg_rig.py could not be read: {a["error"]})'
    rows = [('B1', 'power-off drag of an RS-04 (OFF_DAMPING)', f"{a['OFF_DAMPING']:.2f} N m s/rad, linear (the undamped case: 0)"),
            ('B2', 'rotor inertia at the output (ARMATURE)', f"{a['ARMATURE']:.4f} kg m^2 (3e-4 x 9^2, an estimate)"),
            ('B3', 'stop sleeve rate (STOP_K) and travel', f"{a['stop_k_n_per_mm']:.0f} N/mm at the post ({a['STOP_K']:.0f} N m/rad at "
                                                         f"r {a['stop_r_m'] * 1000:.0f} mm), {a['stop_travel_mm']:.1f} mm before steel"),
            ('B4', 'preload per M5 in the hub joint (HUB_PRELOAD_N)', f"{a['HUB_PRELOAD_N']:.0f} N"),
            ('B5', 'tyre contact (TYRE_SOLREF)', f"solref {a['TYRE_SOLREF']} (about 100-250 N/mm)"),
            ('B6', 'pack resistance (rig/run.py --r-int)', '0.25 ohm (an estimate: 15S1P tool cells)')]
    L = ['| Test | What the simulation assumes | Value now |', '|---|---|---|']
    L += [f'| {t} | {w} | {v} |' for t, w, v in rows]
    return '\n'.join(L)


def predictions() -> str:
    d = json.loads(PRED.read_text())
    L = [f"At {d['half_mass_kg']} kg carried, {d['rate_hz']:.0f} Hz with one tick of latency, the pack at its start rule "
         f"(jumps and drops from {d['v_start_max_dynamic']} V, R_int {d['pack_r_int']} ohm), the bumpers meeting the carriage "
         f"at a leg length of {d['bumper_contact_leg_m'] * 1000:.0f} mm (S6: lowered to 74 mm). From `{d['made_by']}`.", '',
         '| Test | Motor peak N m | Gearbox peak N m | Wheel N | Knee pin N | Leg length mm | VBUS V | Jump mm | Fall s |',
         '|---|---|---|---|---|---|---|---|---|']
    for k, v in d['tests'].items():
        s, m = v['summary'], v['metrics']
        L.append(f"| {NAMES.get(k, k)} | {fmt(s.get('peak_motor_nm'), 1)} | {fmt(s.get('peak_gearbox_nm'), 1)} | "
                 f"{fmt(s.get('peak_wheel_force_n'))} | {fmt(s.get('peak_knee_pin_n'))} | {fmt(s.get('L_range_mm'))} | "
                 f"{fmt([round(x, 1) for x in m['vbus_range_v']], 1)} | {fmt(m.get('jump_height_mm'))} | {fmt(m.get('fall_time_s'), 2)} |")
    return '\n'.join(L)


def criteria() -> str:
    c = json.loads(CRIT.read_text())['tests']
    d = json.loads(PRED.read_text())['tests']
    L = ['| Test | Check | Limit | The prediction |', '|---|---|---|---|']
    for k, spec in c.items():
        pv = {r['what']: r for r in d.get(k, {}).get('verdict', [])}
        for ch in spec['checks']:
            lim = ch.get('tol', ch.get('max', ch.get('rel_tol')))
            if ch['kind'] in ('hold', 'pp', 'track', 'follow'):
                lim = f'{lim * 1000:g} mm' if ch['kind'] != 'pp' else f"{ch['max'] * 1000:g} mm p-p"
            elif ch['kind'] in ('range',):
                k_ = 1000.0 if ch.get('signal') == 'L' else 1.0
                lo_, hi_ = ch.get('min'), ch.get('max')
                lim = f"{fmt(None if lo_ is None else lo_ * k_)} to {fmt(None if hi_ is None else hi_ * k_)}{' mm' if k_ > 1 else ''}"
            elif ch['kind'] in ('jump',):
                lim = f"{ch['min']:g}-{ch['max']:g} mm"
            elif ch['kind'] in ('settle',):
                lim = f"{ch['within_s']:g} s"
            elif ch['kind'] in ('dip', 'fall_time', 'press'):
                lim = f"{ch['rel_tol'] * 100:g} %"
            elif ch['kind'] == 'max_abs':
                lim = f"{ch['max']:g}"
            r = pv.get(ch['what'])
            val = '-' if r is None else ('(the run itself)' if r['value'] in ('no prediction',) else
                                         ('(measured only)' if r['value'] == 'not measured' else
                                          f"{fmt(r['value'], 2 if ch['kind'] == 'fall_time' else 1)}"))
            L.append(f"| {NAMES.get(k, spec['id'])} | {ch['what']} | {lim} | {val} |")
    return '\n'.join(L)


def fill(text: str, key: str, body: str) -> str:
    pat = re.compile(rf'(<!-- gen:{key} -->\n)(.*?)(<!-- /gen:{key} -->)', re.S)
    if not pat.search(text):
        raise SystemExit(f'docs/leg-bench-tests.md has no <!-- gen:{key} --> section')
    return pat.sub(lambda m: m.group(1) + body.rstrip() + '\n' + m.group(3), text)


def main() -> int:
    t = DOC.read_text()
    for key, fn in (('assumes', assumes), ('predictions', predictions), ('criteria', criteria)):
        t = fill(t, key, fn())
    DOC.write_text(t)
    print(f'filled {DOC.relative_to(R)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
