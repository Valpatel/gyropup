#!/usr/bin/env python3
"""Issue #29's gallery: the hip frame before and after, at one colour scale and one deformation scale, the sweep's
chart, and a record of every trial, each with where it came from. It never runs CAD or a solver.

    python research/hip-frame-29/gallery.py --before <run> --after <run> --search <search> --runs <runs.json> \\
        --out exports/leg/fea/hip-frame-29

<run> is a tools/hip-frame-study.py output folder (result.json and hip_frame-<case>-fixed.png, made with the same
--vmax and --dscale). <search> is cad-agent optimise's search folder (trials.jsonl, leaderboard.html); each trial's
result.json is read from the folder its evaluation names, when it is there. <runs.json> lists the screening runs:
[{"name", "host_role", "source_revision", "command", "result": <result.json>}]. The chart is cad-agent's own
leaderboard chart (its SVG, drawn by cadagent.explore.page), captured with a headless browser.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ('R1', 'E1', 'E3o', 'E3i', 'R3o')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name


def case_rows(res: dict) -> dict:
    return {c['case']: {'sf': c['safety_factor'], 'target': c['target'], 'ok': c['ok'],
                        'layers_sf': c['layers'][res['print_normal']]['sf'],
                        'peak_mpa': c['von_mises_design_mpa'], 'peak_at_mm': c['design_peak_at_mm'],
                        'tets': c['mesh']['tets']} for c in res['cases']}


def pair(before: Path, after: Path, case: str, rb: dict, ra: dict, out: Path):
    from PIL import Image, ImageDraw, ImageFont
    a, b = Image.open(before / f'hip_frame-{case}-fixed.png').convert('RGB'), Image.open(after / f'hip_frame-{case}-fixed.png').convert('RGB')
    h = max(a.height, b.height)
    W, top = a.width + b.width + 24, 64
    im = Image.new('RGB', (W, h + top), 'white')
    im.paste(a, (0, top)); im.paste(b, (a.width + 24, top))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
        small = ImageFont.truetype('DejaVuSans.ttf', 15)
    except OSError:
        font = small = ImageFont.load_default()
    cb, ca = case_rows(rb)[case], case_rows(ra)[case]
    for x, label, c, res in ((8, 'Before: dev', cb, rb), (a.width + 32, 'After: issue #29', ca, ra)):
        hip = res['hip']
        d.text((x, 6), f"{label}   {case} SF {c['sf']} (target {c['target']})", fill='black', font=font)
        d.text((x, 34), f"flanges {hip['top_t']:g} / {hip['bottom_t']:g} mm, out {hip['flange_dz']:g} mm, root fillet "
                        f"{hip['root_r']:g} mm, {res['mass_g']:g} g", fill=(70, 70, 70), font=small)
    im.save(out)


def chart(search: Path, out: Path):
    """cad-agent's leaderboard chart (an inline SVG), as a PNG, through the installed Chrome."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome')
        try:
            page = browser.new_page(viewport={'width': 1000, 'height': 800}, device_scale_factor=2, color_scheme='light')
            page.goto((search / 'leaderboard.html').resolve().as_uri())
            el = page.locator('svg').first
            el.wait_for()
            el.screenshot(path=str(out))
        finally:
            browser.close()


def trial_table(search: Path) -> list:
    rows = []
    for line in (search / 'trials.jsonl').read_text().splitlines():
        t = json.loads(line)
        ev = t['evaluation']
        hip = (ev.get('params') or {}).get('hip') or {}
        m = {k: (v or {}).get('value') for k, v in (ev.get('metrics') or {}).items()}
        rows.append({'trial': t['trial'], 'hip': hip, 'verdict': ev['verdict'], 'summary': ev.get('summary'),
                     'margin_min': m.get('margin_min'), 'mass_g': m.get('mass_g'),
                     'sf': {c: m.get(f'sf_{c}') for c in CASES if m.get(f'sf_{c}') is not None},
                     'failed_checks': [c['text'] for c in ev.get('checks', []) if c['level'] == 'fail'
                                       and not c['id'].startswith(('objective-', 'constraint-'))]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--after', type=Path, required=True)
    ap.add_argument('--search', type=Path, required=True)
    ap.add_argument('--runs', type=Path, help='the screening runs (JSON list)')
    ap.add_argument('--host-role', default='mechanical compute host')
    ap.add_argument('--out', type=Path, default=ROOT / 'exports/leg/fea/hip-frame-29')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rb, ra = (json.loads((d / 'result.json').read_text()) for d in (a.before, a.after))
    for k in ('mesh_mm', 'render'):
        if rb.get(k) != ra.get(k):
            raise SystemExit(f'before and after differ in {k}: {rb.get(k)} / {ra.get(k)}; they would not compare')
    outputs = []
    for case in CASES:
        p = a.out / f'hip_frame-{case}-before-after.png'
        pair(a.before, a.after, case, rb, ra, p)
        outputs.append(p)
    png = a.out / 'sweep-chart.png'
    chart(a.search, png)
    outputs.append(png)
    trials = trial_table(a.search)
    runs = json.loads(a.runs.read_text()) if a.runs else []
    for r in runs:
        res = json.loads(Path(r.pop('result')).read_text())
        r.update({'hip': res['hip'], 'mass_g': res['mass_g'], 'mesh_mm': res['mesh_mm'], 'cases': case_rows(res),
                  'bed': res['bed']['placement'], 'body_ok': res['body']['ok']})
    table = a.out / 'trials.json'
    table.write_text(json.dumps({'schema': 1, 'screening': runs, 'search': trials}, indent=1) + '\n')
    outputs.append(table)
    search_cfg = json.loads((a.search / 'search.json').read_text()) if (a.search / 'search.json').exists() else {}
    prov = {'schema': 1, 'purpose': "issue #29: the hip frame before and after, the sweep's chart and every trial",
            'host_role': a.host_role,
            'before': {'source_revision': rb['source_revision'], 'source_dirty': rb['source_dirty'], 'hip': rb['hip'],
                       'mesh_mm': rb['mesh_mm'], 'render': rb.get('render'), 'mass_g': rb['mass_g'], 'cases': case_rows(rb),
                       'result_sha256': sha(a.before / 'result.json')},
            'after': {'source_revision': ra['source_revision'], 'source_dirty': ra['source_dirty'], 'hip': ra['hip'],
                      'mesh_mm': ra['mesh_mm'], 'render': ra.get('render'), 'mass_g': ra['mass_g'], 'cases': case_rows(ra),
                      'result_sha256': sha(a.after / 'result.json')},
            'commands': {'before_after': 'tools/hip-frame-study.py --out <run> --mesh <mesh> --vmax <vmax> --dscale <dscale> --dump'
                                         ' [--params <params.json>]',
                         'search': 'cad-agent optimise --project research/hip-frame-29 --sampler nsga2',
                         'gallery': 'python research/hip-frame-29/gallery.py --before <run> --after <run> --search <search> --runs <runs.json>'},
            'search': {'config': search_cfg.get('config') or search_cfg, 'trials': len(trials),
                       'trials_jsonl_sha256': sha(a.search / 'trials.jsonl')},
            'chart': 'cad-agent leaderboard.html chart (cadagent.explore.page), screenshot in headless Chrome',
            'assumptions': ['loads: cad/leg_studies.py hip-frame cases at D71 18.75 kg a leg, the whole-leg load shares from '
                            'exports/leg/fea/summary.json', 'material: PA6-CF across the layers (pa6_cf_z, 23.04 MPa) everywhere, '
                            'humid; the layer-resolved check uses pa6_cf_xy (48.96 MPa) in the layers',
                            'linear elastic, small deflection, P2 tetrahedra; the colour scale is fixed, stress above it is the top colour'],
            'outputs': {rel(p): sha(p) for p in outputs}}
    (a.out / 'gallery.json').write_text(json.dumps(prov, indent=1) + '\n')
    print('\n'.join(rel(p) for p in outputs + [a.out / 'gallery.json']))


if __name__ == '__main__':
    main()
