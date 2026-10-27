"""The bench turret's print files (docs/turret-prototype-plan.md 4.2): every part printed for v0 as a 3MF in its print
orientation, sliced by Bambu Studio for a P1S with a 0.4 mm hardened-steel nozzle, with the material's profile and the
settings the strength checks assume, and the print schedule.

    .venv/bin/python cad/turret_print.py [--only pan_base dial ...] [--no-slice]

Reads the print-oriented meshes the builds write (cad/turret.py: exports/turret/<part>.stl; cad/build_turret.py:
exports/turret/bench/stand_*.stl). Writes exports/turret/print/<part>.3mf (one part centred on the 256 mm bed, in the
orientation it prints in), print.json (each part's material, slicer settings, copies, and the slicer's grams and time)
and docs/turret-print.md (what to load, in what order, on how many plates). The slicer runs as a separate program
(cadagent.slicer); its work folders are under build/slicer/turret (not kept).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
OUT = R / 'exports' / 'turret' / 'print'
WORK = R / 'build' / 'slicer' / 'turret'
BED = (256.0, 256.0)
PRINTER = 'Bambu Lab P1S 0.4 nozzle'
PROCESS = '0.20mm Standard @BBL X1C'                   # lists the P1S 0.4 among its printers; overrides below
FILAMENT = {'pa6-cf': 'Bambu PA6-CF @BBL X1C', 'petg': 'Bambu PETG HF @BBL P1S 0.4 nozzle', 'petg-clear': 'Bambu PETG Translucent @BBL X1C',
            'tpu95': 'Bambu TPU 95A @BBL X1C'}
# what the FEA and the mass model assume (cad/turret.py MADE, PARTIAL_FILL; cad/turret_studies.py): PA6-CF solid except
# the pan base (4 perimeters, 5 top and bottom layers, 40 % gyroid); PETG 2 mm walls and 40 % gyroid; TPU tyres solid
SOLID = {'wall_loops': '4', 'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag'}
PARTIAL = {'wall_loops': '4', 'top_shell_layers': '5', 'bottom_shell_layers': '5', 'sparse_infill_density': '40%', 'sparse_infill_pattern': 'gyroid'}
PETG = {'wall_loops': '5', 'sparse_infill_density': '40%', 'sparse_infill_pattern': 'gyroid'}
STAND = {'wall_loops': '3', 'sparse_infill_density': '20%', 'sparse_infill_pattern': 'gyroid'}   # the stand carries no fall load: lighter
TPU = {'wall_loops': '3', 'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag'}
SUPPORT = {'enable_support': '1', 'support_type': 'tree(auto)', 'support_threshold_angle': '30'}
PLATE = {'curr_bed_type': 'Textured PEI Plate'}      # the slicer's default cool plate refuses PETG, PA6-CF and TPU
# (part, mesh file, material, copies, settings, needs support, how it sits on the bed, note)
PARTS = [
    ('stand_box', 'bench/stand_box.stl', 'petg', 1, STAND, True, 'upside down, on its top plate', 'the stand first: it needs no decision'),
    ('stand_bottom', 'bench/stand_bottom.stl', 'petg', 1, STAND, False, 'flat', ''),
    ('pan_base', 'pan_base.stl', 'pa6-cf', 1, PARTIAL, True, 'on its foot', '40 % gyroid inside 4 perimeters (the FEA case)'),
    ('pan_ring', 'pan_ring.stl', 'pa6-cf', 1, SOLID, True, 'upside down: the gear teeth flat on the bed', ''),
    ('pan_spacer', 'pan_spacer.stl', 'pa6-cf', 1, SOLID, False, 'on its wide end', ''),
    ('pan_pinion', 'pan_pinion.stl', 'pa6-cf', 1, SOLID, False, 'flat', ''),
    ('ring_carrier', 'ring_carrier.stl', 'pa6-cf', 1, SOLID, False, 'on its top face', 'reprint once the ring\'s flange holes are measured (plan T6)'),
    ('ring_driver', 'ring_driver.stl', 'pa6-cf', 1, SOLID, False, 'on its top face', ''),
    ('tilt_yoke', 'tilt_yoke.stl', 'pa6-cf', 1, SOLID, True, 'on its back: the layers run along the arms', ''),
    ('cradle', 'cradle.stl', 'pa6-cf', 1, SOLID, True, 'flat',
     'its cheeks bend across the layers (FEA: SF 0.77 under a 50 N push on the muzzle, humid PA6-CF): keep it dry, do not push the barrel, '
     'and print a spare when the schedule allows'),
    ('cartridge_body', 'cartridge_body.stl', 'pa6-cf', 1, SOLID, True, 'on its base; supports under the floor, the chute and the cage plate',
     'the longest print: after the motor and a servo are checked against the drawings (plan T2, T4)'),
    ('flywheel', 'flywheel.stl', 'pa6-cf', 2, SOLID, False, 'on its top face (the flange seat flat on the bed)', 'ream the bore to 5.00'),
    ('dial', 'dial.stl', 'petg', 1, PETG, True, 'on its bottom, cone up', ''),
    ('hopper', 'hopper.stl', 'petg-clear', 1, PETG, False, 'upright, on its bottom rim and the baffle', 'translucent PETG so the balls show'),
    ('hopper_lid', 'hopper_lid.stl', 'petg', 1, PETG, False, 'upside down', 'the fill flap is not fitted on the bench'),
    ('barrel', 'barrel.stl', 'petg', 1, PETG, True, 'standing on its socket end', 'change to blaze orange for the last 15 mm (a filament change at that layer)'),
    ('laser_mount', 'laser_mount.stl', 'petg', 1, PETG, False, 'on its foot', ''),
    ('board_bay', 'board_bay.stl', 'petg', 1, PETG, False, 'on its back', ''),
    ('flywheel_tyre', 'flywheel_tyre_d34.stl', 'tpu95', 2, TPU, False, 'flat', 'Ø34 mounted (printed 4 % under the Ø28 rim): the only tyre for the X2216 (D42)'),
]
NOT_PRINTED = {'bumper_ring': 'v1 (the robot): no bumper on the bench', 'hopper_flap': 'v1: the dock\'s fill flap',
               'pan_clamp': 'cut by SendCutSend in 6061-T6 aluminium (exports/turret/pan_clamp.dxf)'}
# the print order (plan 4.2): the stand first, then the pan stack and the tilt group, the cartridge parts after the motor
# and the servo are in hand, the tyres last
SCHEDULE = [('Day 1', ['stand_box', 'stand_bottom']),
            ('Day 1-2: the pan stack (PA6-CF)', ['pan_base', 'pan_ring', 'pan_spacer', 'pan_pinion', 'ring_carrier', 'ring_driver']),
            ('Day 2-3: the tilt group (PA6-CF, PETG)', ['tilt_yoke', 'cradle', 'board_bay', 'laser_mount']),
            ('Once the X2216 and a servo are in hand: the cartridge', ['cartridge_body', 'flywheel', 'dial', 'hopper', 'hopper_lid', 'barrel']),
            ('Last', ['flywheel_tyre'])]


def make_3mf(name: str, stl: Path) -> dict:
    import trimesh
    from cadagent.mesh3mf import write_3mf
    mesh = trimesh.load_mesh(stl, process=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = write_3mf(OUT / f'{name}.3mf', mesh.vertices, mesh.faces, name, BED)
    ext = mesh.bounds[1] - mesh.bounds[0]
    return {'file': f'exports/turret/print/{name}.3mf', 'size_mm': [round(float(e), 1) for e in ext], 'ok': bool(rep.get('ok'))}


def slice_one(name: str, material: str, settings: dict, support: bool) -> dict:
    from cadagent.slicer import slice_part
    over = {**settings, **PLATE}
    if support:
        over.update(SUPPORT)
    work = WORK / name
    r = slice_part(OUT / f'{name}.3mf', workdir=work, printer=PRINTER, process=PROCESS, filament=FILAMENT[material], overrides=over)
    err = r.get('error')
    err = None if not err or str(err).strip().rstrip('.').lower() == 'success' else err
    return {'grams': r.get('grams'), 'minutes': r.get('minutes'), 'filament_m': r.get('filament_m'), 'error': err,
            'exit_code': r.get('exit_code'), 'log_tail': (r.get('log_tail') or '')[-400:] or None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--no-slice', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    path = OUT / 'print.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    rows = dict(old.get('parts', {}))
    for name, mesh, mat, copies, settings, support, how, note in PARTS:
        if a.only and name not in a.only:
            continue
        src = R / 'exports' / 'turret' / mesh
        if not src.exists():
            raise FileNotFoundError(f'{src}: run cad/turret.py and cad/build_turret.py first')
        row = {'material': mat, 'filament_profile': FILAMENT[mat], 'copies': copies, 'orientation': how, 'note': note,
               'settings': {**settings, **PLATE, **(SUPPORT if support else {})}, **make_3mf(name, src)}
        if not a.no_slice:
            row.update(slice_one(name, mat, settings, support))
            print(f"  {name:15} {mat:10} x{copies}  {row.get('grams')} g  {row.get('minutes')} min  {row['size_mm']}"
                  f"{'  ERROR ' + str(row.get('error')) if row.get('error') or not row.get('grams') else ''}  ({time.time() - t0:.0f} s)")
        rows[name] = row
    tot = lambda key, mats: round(sum((r.get(key) or 0) * r['copies'] for r in rows.values() if r['material'] in mats), 1)
    by = {m: {'grams': tot('grams', (m,)), 'hours': round(tot('minutes', (m,)) / 60, 1)} for m in ('pa6-cf', 'petg', 'petg-clear', 'tpu95')}
    res = {'printer': PRINTER, 'nozzle': '0.4 mm hardened steel (PA6-CF is abrasive)', 'process': PROCESS, 'bed_mm': BED, 'parts': rows,
           'by_material': by, 'total_grams': round(sum(v['grams'] for v in by.values()), 1), 'total_hours': round(sum(v['hours'] for v in by.values()), 1),
           'not_printed_v0': NOT_PRINTED, 'schedule': SCHEDULE,
           'note': 'grams and minutes are Bambu Studio\'s own (command line) for the part in this orientation with these settings and its '
                   'supports; copies multiply them'}
    path.write_text(json.dumps(res, indent=1) + '\n')
    write_doc(res)
    shutil.rmtree(WORK, ignore_errors=True)
    print(f"{len(rows)} parts: {res['total_grams']} g, {res['total_hours']} h; {by}")


def write_doc(res: dict):
    rows = res['parts']
    hrs = lambda n: round((rows[n].get('minutes') or 0) * rows[n]['copies'] / 60, 1)
    lines = ['# Printing the bench turret (v0)', '',
             'From `cad/turret_print.py`: every printed part of the bench turret and its stand as a 3MF in the orientation it prints in '
             '(`exports/turret/print/<part>.3mf`, one part centred on the bed), sliced by Bambu Studio for a P1S with these settings, so '
             'the grams and hours are the slicer\'s own. Open a 3MF in Bambu Studio, pick the printer, the filament and the settings in the '
             'table, and slice. The strength checks (cad/turret_studies.py) assume these settings: PA6-CF solid except the pan base, PETG with '
             '2 mm walls (5 loops) and 40 % gyroid.', '',
             '**Before printing:** the P1S needs its 0.4 mm hardened-steel nozzle for PA6-CF (it is abrasive), and the PA6-CF must be dried '
             '(Bambu: 80 °C for 8 h); print it on the textured PEI plate with the glue stick. Heat-set inserts go in while the part is still '
             'warm where you can. Measure the fits of bench test 1.1 as parts come off (docs/turret-bench-tests.md).', '',
             '| Part | Material (Bambu profile) | Copies | On the bed | Settings | g each | h each | Note |', '|---|---|---|---|---|---|---|---|']
    for name, r in rows.items():
        s = r['settings']
        st = f"{s.get('wall_loops')} walls, {s.get('sparse_infill_density')}" + (f" {s['sparse_infill_pattern']}" if s.get('sparse_infill_pattern') else '') + \
             (', tree supports' if s.get('enable_support') == '1' else '')
        lines.append(f"| [{name}](../{r['file']}) | {r['material']} ({r['filament_profile']}) | {r['copies']} | {r['orientation']} | {st} | "
                     f"{r.get('grams') or ''} | {round((r.get('minutes') or 0) / 60, 1) or ''} | {r['note']} |")
    by = res['by_material']
    lines += ['', f"**Totals:** {res['total_grams']} g of filament, {res['total_hours']} h on one printer: "
              + ', '.join(f"{m} {v['grams']} g / {v['hours']} h" for m, v in by.items() if v['grams']) + '.', '',
              '## The schedule', '']
    for day, names in res['schedule']:
        have = [n for n in names if n in rows]
        lines.append(f"- **{day}**: " + ', '.join(f"{n} ({hrs(n)} h)" for n in have) + f" — {round(sum(hrs(n) for n in have), 1)} h")
    lines += ['', 'With one P1S that is about ' + str(round(res['total_hours'] / 20, 1)) + ' days at 20 printing hours a day; the stand can go on a second '
              'printer. The cartridge, hubs, dial and hopper wait for the X2216 and a servo (their sizes are checked against the drawings first).', '',
              '## Not printed for the bench', '']
    lines += [f"- `{k}`: {v}" for k, v in res['not_printed_v0'].items()]
    (R / 'docs' / 'turret-print.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
