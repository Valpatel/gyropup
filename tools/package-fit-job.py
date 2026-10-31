#!/usr/bin/env python3
"""Retain one RS04 coupon slice for UNPOWERED FIT OBSERVATION ONLY.

No CAD generation, printer connection, geometry repair, or automatic orientation.
This recipe is a new declared trial, not an established leg-print process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cad'))
import print_slicing
import print_provenance
import rs04_lug_checks

SOURCE = Path('exports/leg/rs04-mounting-fit')
PART = 'coupon_frame_ring_nom'
PROFILES = dict(printer='Bambu Lab P1S 0.4 nozzle', process='0.20mm Standard @BBL X1C',
                filament='Bambu PA6-CF @BBL X1C')
OVERRIDES = {'wall_loops': '4', 'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag',
             'curr_bed_type': 'Textured PEI Plate', 'enable_support': '0'}
SCOPE = 'UNPOWERED FIT OBSERVATION ONLY; no mounting, preload, torque, strength or powered-operation approval'
RECIPE = {'id': 'rs04-parent-ring-pa6cf-trial-1', 'profiles': PROFILES, 'overrides': OVERRIDES,
          'status': 'new declared trial; not an established leg process',
          'orientation': 'parent hip-frame outer face down; translation only; no auto-orient',
          'copies': 1, 'scope': SCOPE}
QUALIFICATION = {'physical_fit_verified': False, 'mounting_approved': False, 'strength_verified': False,
                 'support_removal_verified': False, 'printer_calibration_verified': False,
                 'full_leg_print_released': False, 'powered_operation_approved': False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def input_identity(root=ROOT):
    """Use the existing strict failing-candidate guard, without loading CAD."""
    directory = root / SOURCE
    data = json.loads((directory / 'checks.json').read_text())
    rs04_lug_checks.validate_receipt(data, directory, root)
    from cadagent import mesh3mf, slicer
    files = ['tools/package-fit-job.py', 'cad/print_slicing.py', 'cad/print_provenance.py',
             'cad/rs04_lug_checks.py', str(SOURCE / 'checks.json'), str(SOURCE / (PART + '.stl'))]
    return {'files': {name: sha(root / name) for name in files},
            'toolkit_helpers': {m.__name__: sha(m.__file__) for m in (mesh3mf, slicer)},
            'engineering_pass': False, 'engineering_counts': data['counts'],
            'unresolved_failures': [c['id'] for c in data['checks'] if c['status'] == 'fail']}


def bed_check(vertices, machine, margin=0.):
    """Conservative bounds check against the actual profile, including exclusion.

    Deliberately accepts only the installed rectangular P1S area; fail closed if
    the profile changes to a different polygon rather than assuming a 256 cube.
    """
    import numpy as np
    v = np.asarray(vertices, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or not len(v) or not np.isfinite(v).all():
        raise ValueError('Invalid placed vertices')
    area = machine['printable_area']
    if area != ['0x0', '256x0', '256x256', '0x256']:
        raise ValueError('Unsupported printable-area polygon')
    exclusion = machine['bed_exclude_area']
    if exclusion != ['0x0', '18x0', '18x28', '0x28']:
        raise ValueError('Unsupported bed exclusion polygon')
    lo, hi = v.min(axis=0), v.max(axis=0)
    height = float(machine['printable_height'])
    if (lo[0] - margin < 0 or lo[1] - margin < 0 or lo[2] < -1e-4
            or hi[0] + margin > 256 or hi[1] + margin > 256 or hi[2] > height
            or (lo[0] - margin < 18 and lo[1] - margin < 28)):
        raise ValueError('Placed geometry/process margin exceeds P1S volume or exclusion')
    return {'bounds_mm': [lo.tolist(), hi.tolist()], 'xy_margin_mm': margin,
            'printable_area': area, 'printable_height_mm': height, 'bed_exclude_area': exclusion}


def geometry_check(job, identity):
    import numpy as np
    import trimesh
    from cadagent.mesh3mf import center_on_bed, read_3mf
    mesh = trimesh.load_mesh(job / 'source.stl', process=True)
    if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split()) != 1:
        raise ValueError('Source must be one closed consistently wound mesh')
    v, f = read_3mf(job / 'geometry.3mf')
    # Comparing every vertex and triangle prevents unnoticed rotation/scale/repair.
    expected = center_on_bed(mesh.vertices, (256., 256.))
    if not np.array_equal(f, mesh.faces) or v.shape != expected.shape or not np.allclose(v, expected, atol=5.1e-5, rtol=0):
        raise ValueError('Packaged geometry differs from parent translation-only orientation')
    return bed_check(v, identity['effective_profiles']['machine'], margin=6.)


def sliced_members(job):
    path = job / 'slice/out/sliced.3mf'
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or z.testzip() is not None:
            raise ValueError('Invalid sliced archive')
        gcodes = [n for n in names if n.endswith('.gcode')]
        if len(gcodes) != 1:
            raise ValueError('Expected exactly one retained plate G-code')
        raw = z.read(gcodes[0])
        if len(raw) < 1000 or b'G1 ' not in raw:
            raise ValueError('Empty or invalid G-code')
        return {name: {'sha256': hashlib.sha256(z.read(name)).hexdigest(), 'bytes': z.getinfo(name).file_size}
                for name in names}


def measurements(job):
    from cadagent.slicer import _read_result
    result = _read_result(job / 'slice/out')
    raw = json.loads((job / 'slice/out/result.json').read_text())
    exit_code = json.loads((job / 'slice/exit-code.json').read_text())['exit_code']
    error = result.get('error')
    error = None if not error or str(error).strip().rstrip('.').lower() == 'success' else error
    metrics = {'grams': result.get('grams'), 'minutes': result.get('seconds', 0) / 60,
               'filament_m': result.get('filament_m'), 'exit_code': exit_code,
               'return_code': result.get('return_code'), 'error': error}
    if not print_provenance.successful_slice({**metrics, 'ok': True, 'copies': 1}) or raw.get('return_code') != 0:
        raise ValueError('Slicer failed or returned invalid time/material')
    if not isinstance(metrics['filament_m'], (int, float)) or not math.isfinite(metrics['filament_m']) or metrics['filament_m'] <= 0:
        raise ValueError('Missing/nonfinite filament length')
    return metrics


def manifest(job):
    return {p.relative_to(job).as_posix(): sha(p) for p in sorted(job.rglob('*'))
            if p.is_file() and p != job / 'job.json'}


def verify(job, root=ROOT):
    job = Path(job)
    report = json.loads((job / 'job.json').read_text())
    if report['recipe'] != RECIPE or report['qualification'] != QUALIFICATION or report['slice_complete'] is not True:
        raise ValueError('Recipe/scope/qualification changed')
    if report['inputs'] != input_identity(root) or report['files_sha256'] != manifest(job):
        raise ValueError('Input or retained-output identity changed')
    if sha(job / 'source.stl') != report['inputs']['files'][str(SOURCE / (PART + '.stl'))]:
        raise ValueError('Staged source changed')
    identity = report['slice_inputs']
    if identity['names'] != PROFILES or identity['overrides'] != OVERRIDES:
        raise ValueError('Wrong slicer recipe')
    for kind, profile in identity['effective_profiles'].items():
        if json.loads((job / 'slice' / (kind + '.json')).read_text()) != profile:
            raise ValueError('Resolved settings changed')
    if report['geometry'] != geometry_check(job, identity) or report['archive_members'] != sliced_members(job):
        raise ValueError('Geometry or sliced archive differs')
    if report['metrics'] != measurements(job):
        raise ValueError('Metrics differ from retained slicer results')
    return report


def generate(job, root=ROOT):
    import trimesh
    from cadagent.mesh3mf import write_3mf
    job = Path(job).resolve()
    before = input_identity(root)
    identity = print_slicing.capture(**PROFILES, overrides=OVERRIDES)
    job.mkdir(parents=True, exist_ok=False)
    (job / 'source.stl').write_bytes((root / SOURCE / (PART + '.stl')).read_bytes())
    mesh = trimesh.load_mesh(job / 'source.stl', process=True)
    write_3mf(job / 'geometry.3mf', mesh.vertices, mesh.faces, PART, (256., 256.))
    geometry = geometry_check(job, identity)
    print('Slicing one unpowered coupon; retaining all outputs in ' + str(job), flush=True)
    print_slicing.run(job / 'geometry.3mf', job / 'slice', identity)
    if before != input_identity(root):
        raise ValueError('Sources changed during slicing; outputs retained for diagnosis only')
    report = {'schema': 'gyropup.fit-job/1', 'recipe': RECIPE, 'qualification': QUALIFICATION,
              'slice_complete': True, 'inputs': before, 'slice_inputs': identity,
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'geometry': geometry, 'metrics': measurements(job), 'archive_members': sliced_members(job)}
    report['files_sha256'] = manifest(job)
    dump(job / 'job.json', report)
    verify(job, root)
    print(json.dumps({'job': str(job), 'metrics': report['metrics'], 'scope': SCOPE}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Fresh visible directory under home; never overwrite a job')
    parser.add_argument('--verify', type=Path, help='Check retained package against current source; no slicing')
    args = parser.parse_args()
    if bool(args.out) == bool(args.verify):
        parser.error('Choose exactly one of --out or --verify')
    if args.verify:
        report = verify(args.verify)
        print(json.dumps({'verified': str(args.verify), 'scope': SCOPE, 'metrics': report['metrics']}))
    else:
        generate(args.out)


if __name__ == '__main__':
    main()
