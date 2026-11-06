#!/usr/bin/env python3
"""Before and after for issue #29's re-run of the FEA records with cad-agent v0.6.0, and cad-agent #197's projection.

    python research/fea-v060-29/compare.py [--before d794466] [--check]

before      the records at --before (dev before the re-run; made with cad-agent v0.4.2), read with git show
after       the records in the working tree (made with v0.6.0)
projection  cad-agent #197's method: each recorded SF times the new strength over the old (pa6_cf_xy 40.84 / 49,
            pa6_cf_z 18.13 / 23, al6061 241.3 / 276; petg unchanged), each deflection times the old modulus over the new

A linear-static study loaded by forces has a stress field that does not depend on E (nu is unchanged in every row
these studies use), so the projection is exact for a study whose part and loads did not change: the re-run's design
stress then equals the record's. Where it differs, the part or its loads changed after the record was made (the
`stress_ratio` column). Writes comparison.json and comparison.md next to this file; --check fails if either is stale.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RECORDS = {'leg': 'exports/leg/fea/summary.json', 'turret': 'exports/turret/fea/summary.json'}
# Not regenerated: cad/studies.py's inputs (cad/gmi.py, designs/default.json, exports/sim/default) changed after this
# record was made, and part of them was never committed, so a re-run is a different design (evidence/
# historical-leg-rerun.json). Its v0.6.0 values are the exact scaling, which evidence/historical-scaling-control.json
# checks: the same studies under v0.4.2 and v0.6.0 on one revision give the same stress field.
HISTORICAL = {'historical leg (D33)': 'exports/fea/summary.json'}
# cad-agent v0.4.2 (2ad4269) MATERIALS, which made the records at --before: (E MPa, strength MPa)
OLD = {'pa6_cf_xy': (3000.0, 49.0), 'pa6_cf_z': (2400.0, 23.0), 'al6061': (68900.0, 276.0), 'petg': (1800.0, 20.0)}
# cad-agent #197 read gyropup at this revision (a checkout of main whose turret record is the 2026-10-27 v0 turret)
PR197_REVISION = 'a79e48c'
# Today's leg on v0.4.2: cad/leg_studies.py at the same revision under the old toolkit (evidence/leg-v042-today.json).
# The leg record predates PR 134's frame and knee, so this is what separates the design's change from the data's. (Its
# member loads come from whole-leg solves meshed in one material, so they do not move with the modulus either.)
LEG_V042_TODAY = HERE / 'evidence/leg-v042-today.json'
THRESHOLDS = (2.0, 1.2)


def git_json(rev, path):
    return json.loads(subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT))


def new_constants(rows):
    """(E, strength) per material key, from the after records' material_data (cad-agent v0.6.0)."""
    out = {}
    for r in rows:
        md = r.get('material_data') or {}
        if md.get('key'):
            out[md['key']] = (md['E_mpa'], md['strength_mpa'])
    return out


def projected_counts(rows, ratio):
    sel = [r for r in rows if r.get('material_id') in ratio]
    return {'studies': len(sel),
            **{f'below_{t}': {'before': sum(r['safety_factor'] < t for r in sel),
                              'projected': sum(r['safety_factor'] * ratio[r['material_id']] < t for r in sel)} for t in THRESHOLDS}}


def num(v):
    return None if v is None else float(v)


def build(before_rev):
    after = {k: json.loads((ROOT / p).read_text()) for k, p in RECORDS.items()}
    before = {k: git_json(before_rev, p) for k, p in {**RECORDS, **HISTORICAL}.items()}
    NEW = new_constants([r for d in after.values() for r in d['results']])
    s_ratio = {k: NEW[k][1] / OLD[k][1] for k in OLD if k in NEW}
    # the materials whose strength changed (PETG's did not: only its modulus), as cad-agent #197 counted
    strength_changed = {k for k, v in s_ratio.items() if abs(v - 1) > 1e-9}
    e_ratio = {k: OLD[k][0] / NEW[k][0] for k in OLD if k in NEW}
    today = ({(r['part'], r['case']): r['safety_factor'] for r in json.loads(LEG_V042_TODAY.read_text())['results']}
             if LEG_V042_TODAY.exists() else {})
    rows = []
    for rec in RECORDS:
        b = {(r['part'], r['case']): r for r in before[rec]['results']}
        for ra in after[rec]['results']:
            key = (ra['part'], ra['case'])
            rb = b.get(key)
            mat = ra.get('material_id')
            row = {'record': rec, 'part': key[0], 'case': key[1], 'material': mat, 'target': ra.get('target'),
                   'sf_after': num(ra['safety_factor']), 'vm_after_mpa': num(ra['von_mises_design_mpa']),
                   'dmax_after_mm': num(ra['max_displacement_mm']), 'verdict_sf_after': num(ra.get('verdict_sf')),
                   'material_data_hash': (ra.get('material_data') or {}).get('constants_hash')}
            if rb is None:
                row['new_study'] = True
                row['after_kind'] = 're-run'
                rows.append(row)
                continue
            sb, vb, db = num(rb['safety_factor']), num(rb['von_mises_design_mpa']), num(rb['max_displacement_mm'])
            row.update(sf_before=sb, vm_before_mpa=vb, dmax_before_mm=db, verdict_sf_before=num(rb.get('verdict_sf')),
                       target_before=rb.get('target'),
                       sf_projected=round(sb * s_ratio[mat], 2) if mat in s_ratio else None,
                       stress_ratio=round(row['vm_after_mpa'] / vb, 4) if vb else None,
                       deflection_ratio=round(row['dmax_after_mm'] / db, 3) if db else None,
                       deflection_ratio_projected=round(e_ratio[mat], 3) if mat in e_ratio else None)
            row['design_or_load_changed'] = row['stress_ratio'] is not None and abs(row['stress_ratio'] - 1) > 0.005
            # today's part under the old data: separates the design's change from the material's
            row['sf_v042_today'] = round(OLD[mat][1] / row['vm_after_mpa'], 2) if mat in OLD and row['vm_after_mpa'] else None
            if rec == 'leg':
                row['sf_v042_today'] = today.get(key)
            vb_, va_ = row['verdict_sf_before'], row['verdict_sf_after']
            row['verdict_crosses'] = ([t for t in THRESHOLDS if (vb_ >= t) != (va_ >= t)]
                                      if vb_ is not None and va_ is not None else [])
            row['crosses'] = [t for t in THRESHOLDS if (sb >= t) != (row['sf_after'] >= t)]
            row['after_kind'] = 're-run'
            if row['target'] is not None:
                row['ok_before'] = (row['verdict_sf_before'] if row['verdict_sf_before'] is not None else sb) >= row['target']
                row['ok_after'] = (row['verdict_sf_after'] if row['verdict_sf_after'] is not None else row['sf_after']) >= row['target']
            rows.append(row)
    for rec in HISTORICAL:
        for rb in before[rec]['results']:
            mat, sb = rb.get('material_id'), num(rb['safety_factor'])
            vb = num(rb['von_mises_design_mpa'])
            row = {'record': rec, 'part': rb['part'], 'case': rb['case'], 'material': mat, 'target': rb.get('target'),
                   'sf_before': sb, 'vm_before_mpa': vb, 'sf_projected': round(sb * s_ratio[mat], 2) if mat in s_ratio else None,
                   'after_kind': 'scaled: record kept (inputs not in git); v0.6.0 strength over the recorded design stress, '
                                 'exact by evidence/historical-scaling-control.json'}
            row['sf_after'] = round(NEW[mat][1] / vb, 2)
            row['crosses'] = [t for t in THRESHOLDS if (sb >= t) != (row['sf_after'] >= t)]
            rows.append(row)
    changed = [r for r in rows if r.get('material') in strength_changed and 'sf_before' in r]
    counts = {f'below_{t}': {'before': sum(r['sf_before'] < t for r in changed),
                             'projected': sum(r['sf_projected'] < t for r in changed),
                             'after': sum(r['sf_after'] < t for r in changed)} for t in THRESHOLDS}
    targeted = [r for r in rows if 'ok_after' in r]
    counts['below_target'] = {'before': sum(not r['ok_before'] for r in targeted), 'after': sum(not r['ok_after'] for r in targeted),
                              'studies': len(targeted), 'basis': 'each record\'s own verdict (the turret: layer-aware SF for '
                              'printed parts); regenerated records only'}
    stale = [r for k, p in {**RECORDS, **HISTORICAL}.items() for r in git_json(PR197_REVISION, p)['results']]
    return {'schema': 1, 'before_revision': subprocess.check_output(['git', 'rev-parse', before_rev], cwd=ROOT, text=True).strip(),
            'toolkit': {'before': 'cad-agent v0.4.2 (2ad4269)', 'after': 'cad-agent v0.6.0 (50d4921)'},
            'strength_ratio': {k: round(v, 4) for k, v in s_ratio.items()},
            'deflection_ratio_from_modulus': {k: round(v, 3) for k, v in e_ratio.items()},
            'counts': {'studies_in_changed_materials': len(changed), **counts},
            'pr197': {'revision_read': PR197_REVISION,
                      'its_counts': projected_counts(stale, {k: s_ratio[k] for k in strength_changed}),
                      'same_method_on_before': projected_counts([r for d in before.values() for r in d['results']],
                                                                {k: s_ratio[k] for k in strength_changed})},
            'rows': rows}


def fmt(v, d=2):
    return '' if v is None else f'{v:.{d}f}'


def markdown(c):
    L = ['# Before and after: the FEA records on cad-agent v0.6.0 (issue #29)', '',
         f"Generated by `research/fea-v060-29/compare.py` from the records at `{c['before_revision'][:7]}` (made with "
         'cad-agent v0.4.2) and the regenerated ones (v0.6.0), with `figure.py`\'s chart in `sf-before-after.png`.', '',
         '- **SF** is the isotropic gate value each record reports; **verdict** is what the turret record judges its printed '
         'parts on (its layer-aware SF), shown before -> after.',
         '- **#197** is cad-agent #197\'s projection: the recorded SF times the new strength over the old.',
         '- **stress** is the re-run\'s design stress over the record\'s. At 1.000 the part and its loads are unchanged, so only '
         'the material moved the SF, and the projection is exact. Away from 1 the part or its loads changed after the record '
         'was made.',
         '- **v0.4.2 today** is today\'s part under the old data: the difference from **SF before** is the design\'s change, '
         'from **SF after** the material\'s. For the leg it is a run of its own (`evidence/leg-v042-today.json`: '
         '`cad/leg_studies.py` at the same revision with cad-agent v0.4.2). For the turret it is the old strength over '
         'today\'s design stress, which is exact for a part of one material under force loads '
         '(`evidence/historical-scaling-control.json`, and the leg\'s two runs).',
         '- **deflection** is the re-run\'s largest displacement over the record\'s, with the modulus ratio in brackets.', '',
         '| Record | Part | Case | Material | Target | SF before | #197 | SF after | Crosses | verdict | stress | v0.4.2 today | deflection |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in c['rows']:
        if r['after_kind'] != 're-run' and 'sf_before' in r:
            L.append(f"| {r['record']} | {r['part']} | {r['case']} | {r['material']} | {fmt(r['target'], 1)} | {fmt(r['sf_before'])} | "
                     f"{fmt(r['sf_projected'])} | {fmt(r['sf_after'])} (scaled) | {', '.join(f'{t:g}' for t in r['crosses'])} | | | | |")
            continue
        if 'sf_before' not in r:
            L.append(f"| {r['record']} | {r['part']} | {r['case']} | {r['material']} | {fmt(r['target'], 1)} | (new) | | {fmt(r['sf_after'])} | | | | | |")
            continue
        cross = ', '.join(f'{t:g}' for t in r['crosses'])
        verdict = (f"{fmt(r['verdict_sf_before'])} -> {fmt(r['verdict_sf_after'])}"
                   if r.get('verdict_sf_before') is not None and r['material'] != 'al6061' else '')
        fail = ' **(below target)**' if r.get('ok_after') is False else ''
        L.append(f"| {r['record']} | {r['part']} | {r['case']} | {r['material']} | {fmt(r['target'], 1)} | {fmt(r['sf_before'])} | "
                 f"{fmt(r['sf_projected'])} | **{fmt(r['sf_after'])}**{fail if not verdict else ''} | {cross} | {verdict}{fail if verdict else ''} | "
                 f"{fmt(r['stress_ratio'], 3)} | {fmt(r.get('sf_v042_today'))} | {fmt(r['deflection_ratio'])} ({fmt(r['deflection_ratio_projected'])}) |")
    k = c['counts']
    p = c['pr197']
    L += ['', f"The historical leg record (`exports/fea/`, D33) is not regenerated: its inputs changed after it was made and part of "
          'them was never committed (`evidence/historical-leg-rerun.json`). Its v0.6.0 values are the new strength over its '
          'recorded design stress, which `evidence/historical-scaling-control.json` shows is exact.', '',
          f"Studies in the materials whose strength changed: {k['studies_in_changed_materials']}.", '',
          '| | before | #197 method on these records | after |', '|---|---|---|---|']
    for t in THRESHOLDS:
        x = k[f'below_{t}']
        L.append(f"| below SF {t:g} | {x['before']} | {x['projected']} | {x['after']} |")
    bt = k['below_target']
    L += ['', f"Below target on each record's own verdict (regenerated records, {bt['studies']} studies with a target): "
          f"{bt['before']} before, {bt['after']} after.", '']
    q = p['its_counts']
    L += [f"cad-agent #197 read gyropup at `{p['revision_read']}` ({q['studies']} studies): below 2.0 "
          f"{q['below_2.0']['before']} -> {q['below_2.0']['projected']}, below 1.2 {q['below_1.2']['before']} -> "
          f"{q['below_1.2']['projected']}. That checkout's turret record is the 2026-10-27 v0 turret (22 studies); dev's is "
          'the 2026-10-28 one (28).', '']
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', default='d794466')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    c = build(a.before)
    js, md = json.dumps(c, indent=1) + '\n', markdown(c)
    if a.check:
        ok = (HERE / 'comparison.json').read_text() == js and (HERE / 'comparison.md').read_text() == md
        raise SystemExit(0 if ok else 'comparison.json / comparison.md are stale: rerun compare.py')
    (HERE / 'comparison.json').write_text(js)
    (HERE / 'comparison.md').write_text(md)
    print(md)


if __name__ == '__main__':
    main()
