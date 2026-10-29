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
import fcntl
import shutil
import sys
import time
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import print_provenance as provenance  # noqa: E402
import print_slicing  # noqa: E402
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
    ('stand_box', 'bench/stand_box.stl', 'petg', 1, STAND, True, 'upside down, on its top plate', 'verify the selected panel switch and mounting geometry before printing'),
    ('stand_bottom', 'bench/stand_bottom.stl', 'petg', 1, STAND, False, 'flat', ''),
    ('compute_tray', 'compute_tray.stl', 'pa6-cf', 1, PARTIAL, False, 'flat, ribs up', 'the compute plinth\'s floor (D66): 4 x M4 inserts'),
    ('compute_shell', 'compute_shell.stl', 'petg', 1, PETG, True, 'upside down, on its top rim', 'the compute plinth\'s wall (D66): 4 x M5 inserts in the column tops'),
    ('pan_base', 'pan_base.stl', 'pa6-cf', 1, PARTIAL, True, 'on its foot', '40 % gyroid inside 4 perimeters (the FEA case)'),
    ('pan_ring', 'pan_ring.stl', 'pa6-cf', 1, SOLID, True, 'upside down: the gear teeth flat on the bed', ''),
    ('pan_spacer', 'pan_spacer.stl', 'pa6-cf', 1, SOLID, False, 'on its wide end', ''),
    ('pan_pinion', 'pan_pinion.stl', 'pa6-cf', 1, SOLID, False, 'flat', ''),
    ('ring_carrier', 'ring_carrier.stl', 'pa6-cf', 1, SOLID, False, 'on its top face', 'reprint once the ring\'s flange holes are measured (plan T6)'),
    ('ring_driver', 'ring_driver.stl', 'pa6-cf', 1, SOLID, False, 'on its top face', ''),
    ('tilt_yoke', 'tilt_yoke.stl', 'pa6-cf', 1, SOLID, True, 'on its back: the layers run along the arms', ''),
    ('cradle', 'cradle.stl', 'pa6-cf', 1, SOLID, False, 'flat, no supports',
     'the rail frame (D48): its cheeks are the two SendCutSend plates; 8 x M3 inserts in the rebates, put in from the side'),
    ('horn_boss', 'horn_boss.stl', 'pa6-cf', 1, SOLID, False, 'on an end face', 'between the +y plate and the tilt servo\'s horn (D48)'),
    ('pivot_spacer', 'pivot_spacer.stl', 'pa6-cf', 1, SOLID, False, 'on its boss face, the land up',
     'between the -y plate and the MR126 (D48); its 1 mm land bears on the inner race only'),
    ('cartridge_body', 'cartridge_body.stl', 'pa6-cf', 1, SOLID, True, 'on its base; supports under the floor, the chute and the cage plate',
     'the longest print: after the motor and a servo are checked against the drawings (plan T2, T4)'),
    ('flywheel', 'flywheel.stl', 'pa6-cf', 2, SOLID, False, 'on its top face (the flange seat flat on the bed)', 'ream the bore to 5.00'),
    ('dial', 'dial.stl', 'petg', 1, PETG, True, 'on its bottom, cone up', ''),
    ('hopper', 'hopper.stl', 'petg-clear', 1, PETG, False, 'upright, on its bottom rim and the baffle', 'translucent PETG so the balls show'),
    ('hopper_lid', 'hopper_lid.stl', 'petg', 1, PETG, False, 'upside down', 'the fill flap is not fitted on the bench'),
    ('barrel', 'barrel.stl', 'petg', 1, PETG, True, 'standing on its socket end', 'change to blaze orange for the last 15 mm (a filament change at that layer)'),
    ('laser_mount', 'laser_mount.stl', 'petg', 1, PETG, False, 'on its foot', ''),
    ('board_bay', 'board_bay.stl', 'petg', 1, PETG, False, 'on its back', ''),
    ('board_bay_lid', 'board_bay_lid.stl', 'petg', 1, PETG, False, 'flat, the lip up', 'the bay\'s snap lid (modelled since 2026-10-27)'),
    ('flywheel_tyre', 'flywheel_tyre.stl', 'tpu95', 2, TPU, False, 'flat', 'the selected CAD tyre in its unstretched print shape; do not substitute a historical diameter variant'),
]
NOT_PRINTED = {'bumper_ring': 'v1 (the robot): no bumper on the bench', 'hopper_flap': 'v1: the dock\'s fill flap',
               'pan_clamp': 'cut by SendCutSend in 6061-T6 aluminium (exports/turret/pan_clamp.dxf)',
               'cradle_plate_l': 'cut by SendCutSend in 6061-T6 aluminium 0.125 in, 4 countersinks (exports/turret/cradle_plate_l.dxf; D48)',
               'cradle_plate_r': 'cut by SendCutSend in 6061-T6 aluminium 0.125 in, tapped M5, 2 countersinks (exports/turret/cradle_plate_r.dxf; D48)',
               'stop_lug': 'cut by SendCutSend in 6061-T6 aluminium 0.100 in, 2 holes tapped M3 (exports/turret/stop_lug.dxf; D48)'}
# the print order (plan 4.2): the stand first, then the pan stack and the tilt group, the cartridge parts after the motor
# and the servo are in hand, the tyres last
SCHEDULE = [('Day 1', ['stand_box', 'stand_bottom']),
            ('Day 1-2: the compute plinth and the pan stack (PA6-CF, PETG)', ['compute_tray', 'compute_shell', 'pan_base', 'pan_ring', 'pan_spacer', 'pan_pinion', 'ring_carrier', 'ring_driver']),
            ('Day 2-3: the tilt group (PA6-CF, PETG)', ['tilt_yoke', 'cradle', 'horn_boss', 'pivot_spacer', 'board_bay', 'board_bay_lid', 'laser_mount']),
            ('Once the X2216 and a servo are in hand: the cartridge', ['cartridge_body', 'flywheel', 'dial', 'hopper', 'hopper_lid', 'barrel']),
            ('Last', ['flywheel_tyre'])]


def make_3mf(name: str, stl: Path, output: Path) -> dict:
    import trimesh
    from cadagent.mesh3mf import write_3mf
    mesh = trimesh.load_mesh(stl, process=True)
    output.mkdir(parents=True, exist_ok=True)
    rep = write_3mf(output / f'{name}.3mf', mesh.vertices, mesh.faces, name, BED)
    ext = mesh.bounds[1] - mesh.bounds[0]
    return {'file': f'exports/turret/print/{name}.3mf', 'size_mm': [round(float(e), 1) for e in ext], 'ok': bool(rep.get('ok'))}


def slice_one(name: str, output: Path, work: Path, identity: dict) -> dict:
    return print_slicing.run(output / f'{name}.3mf', work / name, identity)


def recipe(part: tuple, slice_inputs: dict | None) -> str:
    _, _, mat, copies, settings, support, how, _ = part
    return provenance.fingerprint({'material': mat, 'copies': copies, 'settings': settings,
        'support': support, 'orientation': how, 'printer': PRINTER, 'process': PROCESS,
        'filament': FILAMENT[mat], 'plate': PLATE, 'support_settings': SUPPORT, 'slice_inputs': slice_inputs})


def _copy_verified(source: Path, destination: Path, expected: str):
    import hashlib
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{source.name}: input changed during packaging')
    destination.write_bytes(raw)


def _publish(staged: Path, document: Path, backup: Path):
    """Rollback ordinary publication errors; the old generation stays intact until validation.

    A process/host crash between directory renames can leave the backup directory.
    Do not auto-delete it: the next run stops for explicit recovery.
    """
    doc = R / 'docs/turret-print.md'
    old_doc = doc.read_bytes() if doc.exists() else None
    had_output = OUT.exists()
    if had_output:
        OUT.rename(backup)
    try:
        staged.rename(OUT)
        document.replace(doc)
    except BaseException:
        if OUT.exists():
            shutil.rmtree(OUT)
        if had_output:
            backup.rename(OUT)
        if old_doc is None:
            doc.unlink(missing_ok=True)
        else:
            doc.write_bytes(old_doc)
        raise
    if had_output:
        shutil.rmtree(backup)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--no-slice', action='store_true')
    a = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Serialize writers; readers use hashes to reject a generation interrupted by a crash.
    with (OUT.parent / '.print-package.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backup = OUT.with_name('print-previous-generation')
        if backup.exists():
            raise ValueError('Interrupted publication: recover print-previous-generation before rebuilding')
        with tempfile.TemporaryDirectory(prefix='print-staging-', dir=OUT.parent) as temp:
            _build(a, ap, Path(temp), backup)


def _build(a, ap, stage: Path, backup: Path):
    t0 = time.time()
    path = OUT / 'print.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    names = {p[0] for p in PARTS}
    if a.only and not set(a.only) <= names:
        ap.error('Unknown part(s): ' + ', '.join(sorted(set(a.only) - names)))
    inputs = provenance.snapshot(R)
    sources, recipes, slicing, rows = {}, {}, {}, {}
    output = stage / 'print'
    output.mkdir()
    meshes = stage / 'meshes'
    meshes.mkdir()
    work = WORK / stage.name
    retained = old.get('parts', {}) if a.only else {}
    # Copy verified bytes into a private generation. No visible output changes on failure.
    for part in PARTS:
        name, mesh, mat, copies, settings, support, how, note = part
        selected = not a.only or name in a.only
        if not selected and name not in retained:
            continue
        src = R / 'exports/turret' / mesh
        sources[name] = provenance.validate_mesh(R, src, inputs)
        over = {**settings, **PLATE, **(SUPPORT if support else {})}
        slicing[name] = None if a.no_slice else print_slicing.capture(PRINTER, PROCESS, FILAMENT[mat], over)
        recipes[name] = recipe(part, slicing[name])
        _copy_verified(src, meshes / f'{name}.stl', sources[name]['sha256'])
        if not selected:
            row = retained[name]
            expected_output = f'exports/turret/print/{name}.3mf'
            if (row.get('file') != expected_output or row.get('source') != sources[name]
                    or row.get('recipe_sha256') != recipes[name] or row.get('slice_inputs') != slicing[name]
                    or (not a.no_slice and not provenance.successful_slice(row))):
                raise ValueError(f'{name}: retained print output is stale or unbound; regenerate the full package')
            try:
                _copy_verified(R / expected_output, output / f'{name}.3mf', row.get('sha256'))
            except (OSError, ValueError) as exc:
                raise ValueError(f'{name}: retained print output is stale or unbound; regenerate the full package') from exc
            rows[name] = row
    try:
        for part in PARTS:
            name, mesh, mat, copies, settings, support, how, note = part
            if a.only and name not in a.only:
                continue
            src = meshes / f'{name}.stl'
            row = {'material': mat, 'filament_profile': FILAMENT[mat], 'copies': copies, 'orientation': how, 'note': note,
                   'settings': {**settings, **PLATE, **(SUPPORT if support else {})}, **make_3mf(name, src, output),
                   'source': sources[name], 'recipe_sha256': recipes[name], 'slice_inputs': slicing[name]}
            if not row.get('ok') or provenance.digest(src) != sources[name]['sha256']:
                raise ValueError(f'{name}: mesh changed during packaging or 3MF writer rejected it')
            row['sha256'] = provenance.digest(output / f'{name}.3mf')
            if not a.no_slice:
                row.update(slice_one(name, output, work, slicing[name]))
                if not provenance.successful_slice(row):
                    raise ValueError(f'{name}: slicer failed or returned invalid measurements (exit {row.get("exit_code")})')
                print(f"  {name:15} {mat:10} x{copies}  {row['grams']} g  {row['minutes']} min  ({time.time() - t0:.0f} s)")
            rows[name] = row
        rows = {p[0]: rows[p[0]] for p in PARTS if p[0] in rows}
        totals = provenance.slice_totals(rows, names)
        res = {'printer': PRINTER, 'nozzle': '0.4 mm hardened steel (PA6-CF is abrasive)', 'process': PROCESS, 'bed_mm': BED,
               'parts': rows, 'complete': set(rows) == names, 'slice_complete': bool(totals and totals['complete']),
               'physical_fit_verified': False,
               'qualification': 'Source-bound print preparation; mechanical and physical acceptance remain separate.',
               'by_material': totals['by_material'] if totals else {}, 'total_grams': totals['grams'] if totals else None,
               'total_hours': totals['hours'] if totals else None, 'not_printed_v0': NOT_PRINTED, 'schedule': SCHEDULE,
               'note': '3MF geometry coverage and successful slicing are separate; missing slice measurements are null.'}
        (output / 'print.json').write_text(json.dumps(res, indent=1) + '\n')
        doc = stage / 'turret-print.md'
        write_doc(res, doc)
        # Check originals, staged bytes, context, toolchain and profiles again after the last slice.
        if provenance.snapshot(R) != inputs:
            raise ValueError('CAD inputs changed during packaging')
        for name, source in sources.items():
            if provenance.validate_mesh(R, R / source['file'], inputs) != source:
                raise ValueError(f'{name}: source receipt changed during packaging')
            if (provenance.digest(meshes / f'{name}.stl') != source['sha256']
                    or provenance.digest(output / f'{name}.3mf') != rows[name]['sha256']):
                raise ValueError(f'{name}: staged input/output changed during packaging')
            if slicing[name] is not None and not print_slicing.current(slicing[name]):
                raise ValueError(f'{name}: slicer inputs changed during packaging')
        _publish(output, doc, backup)
        print(f"{len(rows)} parts: {res['total_grams']} g, {res['total_hours']} h; sliced={res['slice_complete']}")
    finally:
        # Keep failed slicer logs for diagnosis. Successful captured settings live in print.json.
        if not stage.joinpath('print').exists():
            shutil.rmtree(work, ignore_errors=True)


def write_doc(res: dict, destination: Path):
    rows = res['parts']
    hrs = lambda n: round((rows[n].get('minutes') or 0) * rows[n]['copies'] / 60, 1)
    lines = ['# Printing the bench turret (v0)', '',
             '**Research prototype — not a fabrication release.** Review the current [mechanical readiness gates](mechanical-readiness.md) '
             'before printing. Matching source hashes establish artifact identity, not fit, strength or safe operation. '
             + ('This package includes every planned print row.' if res['complete'] else 'This package is partial; its totals are incomplete.'), '',
             ('Slicing completed for every planned row.' if res['slice_complete'] else '**Slicing is incomplete or was skipped; missing measurements are not zero.**'), '',
             'From `cad/turret_print.py`: every printed part of the bench turret and its stand as a 3MF in the orientation it prints in '
             '(`exports/turret/print/<part>.3mf`, one part centred on the bed). When slicing succeeds, grams and hours come from '
             'Bambu Studio with the recorded P1S profiles and settings. Open a 3MF in Bambu Studio, pick the printer, the filament and the settings in the '
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
    total_text = ('**Totals:** not measured; slicing was skipped.' if res['total_grams'] is None else
                  f"**Totals:** {res['total_grams']} g of filament, {res['total_hours']} h on one printer: ")
    lines += ['', total_text
              + ', '.join(f"{m} {v['grams']} g / {v['hours']} h" for m, v in by.items() if v['grams']) + '.', '',
              '## The schedule', '']
    for day, names in res['schedule']:
        have = [n for n in names if n in rows]
        labels = [f"{n} ({hrs(n)} h)" if provenance.successful_slice(rows[n]) else f'{n} (not sliced)' for n in have]
        lines.append(f"- **{day}**: " + ', '.join(labels))
    if res['slice_complete']:
        lines += ['', f"At 20 printing hours per day, the measured schedule is about {round(res['total_hours'] / 20, 1)} days on one P1S."]
    lines += ['', 'The cartridge, hubs, dial and hopper wait for motor and servo dimensions to be checked against the drawings.',
              '', '## Not printed for the bench', '']
    lines += [f"- `{k}`: {v}" for k, v in res['not_printed_v0'].items()]
    destination.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
