#!/usr/bin/env python3
"""Retain one RS04 coupon slice for UNPOWERED FIT OBSERVATION ONLY.

No CAD generation, printer connection, geometry repair, or automatic orientation.
This recipe is a new declared trial, not an established leg-print process.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import re
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

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
          'orientation': 'parent hip-frame outer face down; +Z layer normal preserved; in-plane rigid placement allowed',
          'copies': 1, 'scope': SCOPE}
QUALIFICATION = {'physical_fit_verified': False, 'mounting_approved': False, 'strength_verified': False,
                 'support_removal_verified': False, 'printer_calibration_verified': False,
                 'full_leg_print_released': False, 'powered_operation_approved': False}
TOOLKIT_COMMIT = '2ad426943ce2c7232875e105e50810849f9a3e5e'
TOOLKIT_HELPERS = {'cadagent.mesh3mf': 'cf5aa2a2f6dab9d2a1e76539f158a10e38bc5e0fb72ceaabdf264178b83ce29f',
                   'cadagent.slicer': 'fd5a746a54d920d13af228a9766da4b5b390cc043dded2fd0be4486db3f415f0',
                   'cadagent._deps': '9a637459accd62b83497bcc0452e55c156f4775ce9bd816c4c334ddacaf59f9a'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def input_identity(root=ROOT):
    """Use the existing strict failing-candidate guard, without loading CAD."""
    directory = root / SOURCE
    data = json.loads((directory / 'checks.json').read_text())
    rs04_lug_checks.validate_receipt(data, directory, root)
    from cadagent import mesh3mf, slicer, _deps
    helpers = {m.__name__: sha(m.__file__) for m in (mesh3mf, slicer, _deps)}
    if helpers != TOOLKIT_HELPERS:
        raise ValueError('Use the released cad-agent helpers from ' + TOOLKIT_COMMIT)
    versions = {}
    for line in (root / 'tools/fit-job-requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        package, expected = line.split('==')
        versions[package] = importlib.metadata.version(package)
        if versions[package] != expected:
            raise ValueError('Fit-job runtime version differs: ' + package)
    files = ['tools/package-fit-job.py', 'tools/fit-job-requirements.txt', 'cad/print_slicing.py', 'cad/print_provenance.py',
             'cad/rs04_lug_checks.py', str(SOURCE / 'checks.json'), str(SOURCE / (PART + '.stl'))]
    return {'files': {name: sha(root / name) for name in files},
            'toolkit_helpers': helpers, 'toolkit_commit': TOOLKIT_COMMIT, 'runtime_packages': versions,
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


def toolpaths(text, machine, nozzle_temp=275., bed_temp=100., drawings=None):
    """Check this single-extruder Bambu dialect, not arbitrary machine programs.

    Startup/end homing, purge and wipe paths are vendor machine operations and
    intentionally leave the object bed area. Bounds below cover object/nozzle
    paths between layer markers and end G-code, including arc sweep extrema.
    Temperature waits must precede actual object deposition.
    """
    import numpy as np
    xyze, relative_e, absolute_xyz = {}, False, True
    nozzle, waited_nozzle, bed, waited_bed = None, None, None, None
    feature, layer, body = None, None, False
    conditional_depth = 0
    known_features = {'Custom', 'Inner wall', 'Outer wall', 'Gap infill', 'Bottom surface', 'Top surface',
                      'Internal solid infill', 'Sparse infill', 'Bridge', 'Overhang wall', 'Floating vertical shell',
                      'Skirt', 'Brim'}
    motion_codes = {'G0', 'G1', 'G2', 'G3', 'G4', 'G17', 'G21', 'G90', 'G92'}
    startup_motion_codes = motion_codes | {'G28', 'G29', 'G29.1', 'G29.2', 'G91', 'G380'}
    body_m_codes = {'M73', 'M82', 'M83', 'M104', 'M106', 'M109', 'M140', 'M190', 'M204', 'M400',
                    'M622', 'M622.1', 'M623', 'M971', 'M981', 'M991', 'M1002', 'M1003', 'M1004'}
    points, features, layer_z = [], {}, set()
    for line in text.splitlines():
        if line.startswith('; MACHINE_END_GCODE_START'):
            body = False
        if line.startswith('; FEATURE: '):
            feature = line.split(': ', 1)[1]
            if feature not in known_features:
                raise ValueError('Unknown or unsupported deposition feature: ' + feature)
        if line.startswith('; Z_HEIGHT: '):
            layer = float(line.split(': ', 1)[1])
            if not math.isfinite(layer): raise ValueError('Nonfinite layer height')
            layer_z.add(layer)
            body = True
        command = line.split(';', 1)[0].strip()
        if not command: continue
        code = command.split()[0].upper()
        if not re.fullmatch(r'[GMT]\d+(?:\.\d+)?', code):
            raise ValueError('Unsupported command syntax: ' + code)
        if re.search(r'\s[GM]\d+(?:\.\d+)?(?=\s|$)', command.upper()):
            raise ValueError('Multiple commands on one line are unsupported')
        # Reject modal/coordinate operations even before the first layer. Their
        # state persists into deposition; comments are not a machine reset.
        if code.startswith('G') and code not in (motion_codes if body else startup_motion_codes):
            raise ValueError('Unsupported motion/modal command: ' + code)
        if code in ('G90', 'G91', 'G17', 'G21') and len(command.split()) != 1:
            raise ValueError('Unsupported arguments on coordinate-mode command')
        args = {k: float(v) for k, v in re.findall(r'([XYZEFIJSR])\s*([-+]?(?:\d*\.\d+|\d+\.?\d*))', command.upper())}
        if code in ('G0', 'G1', 'G2', 'G3', 'G92'):
            allowed = 'E' if code == 'G92' else 'XYZEF' if code in ('G0', 'G1') else 'XYZEFIJP'
            tail = command[len(command.split()[0]):].upper()
            if not re.fullmatch(r'(?:\s*['+allowed+r']\s*[-+]?(?:\d*\.\d+|\d+\.?\d*))*\s*', tail):
                raise ValueError('Unsupported motion arguments: ' + command)
        if code == 'G90': absolute_xyz = True
        if code == 'G91': absolute_xyz = False
        if body and code.startswith('T'):
            raise ValueError('Unexpected tool change during object printing')
        if body and code.startswith('M') and code not in body_m_codes:
            raise ValueError('Unsupported object machine command: ' + code)
        if code == 'M622': conditional_depth += 1
        if code == 'M623':
            conditional_depth -= 1
            if conditional_depth < 0: raise ValueError('Unbalanced conditional block')
        if code == 'M83': relative_e = True
        if code == 'M82': relative_e = False
        if code in ('M104', 'M109'):
            target = args.get('S', args.get('R'))
            if target is None: raise ValueError('Unknown nozzle temperature command')
            if target != nozzle or conditional_depth: waited_nozzle = None
            nozzle = target
            if code == 'M109' and not conditional_depth: waited_nozzle = nozzle
        if code in ('M140', 'M190'):
            target = args.get('S', args.get('R'))
            if target is None: raise ValueError('Unknown bed temperature command')
            if target != bed or conditional_depth: waited_bed = None
            bed = target
            if code == 'M190' and not conditional_depth: waited_bed = bed
        if code == 'G92':
            if set(args) != {'E'}:
                raise ValueError('Only an explicit G92 E reset is supported')
            xyze['E'] = args['E']
        if code in ('G28', 'G29', 'G380'):
            # Vendor startup homing/probing must be followed by explicit
            # coordinates before an object point can be checked.
            for axis in 'XYZ': xyze.pop(axis, None)
        if code not in ('G0', 'G1', 'G2', 'G3'): continue
        if body and not absolute_xyz: raise ValueError('Relative object motion is unsupported')
        start = dict(xyze)
        for axis in 'XYZ':
            if axis not in args: continue
            if absolute_xyz: xyze[axis] = args[axis]
            elif axis in xyze: xyze[axis] += args[axis]
        if not body: continue
        # Feedrate-only and retract/unretract commands do not move the nozzle.
        # In particular, the first retraction remains at the vendor purge line.
        if code in ('G0', 'G1') and not any(k in args for k in 'XYZ'): continue
        if not all(k in xyze for k in 'XYZ'): raise ValueError('Unknown object position')
        points.append([xyze[k] for k in 'XYZ'])
        line_points = [[start.get('X', xyze['X']), start.get('Y', xyze['Y'])], [xyze['X'], xyze['Y']]]
        if code in ('G2', 'G3'):
            if 'R' in args or not all(k in start for k in 'XY'):
                raise ValueError('Unsupported object arc')
            cx, cy = start['X'] + args.get('I', 0), start['Y'] + args.get('J', 0)
            radius = math.hypot(args.get('I', 0), args.get('J', 0))
            first = math.atan2(start['Y']-cy, start['X']-cx)
            last = math.atan2(xyze['Y']-cy, xyze['X']-cx)
            direction = 1 if code == 'G3' else -1
            sweep = ((last-first)*direction) % (2*math.pi)
            if math.hypot(xyze['X']-start['X'], xyze['Y']-start['Y']) < 1e-6:
                sweep = 2*math.pi
            if drawings is not None and layer in drawings:
                angles = np.linspace(first, first+direction*sweep, max(2, int(sweep*radius/.3)+1))
                line_points = np.column_stack((cx+radius*np.cos(angles), cy+radius*np.sin(angles))).tolist()
            for angle in (0, math.pi/2, math.pi, 3*math.pi/2):
                if ((angle-first)*direction) % (2*math.pi) <= sweep + 1e-8:
                    points.append([cx+radius*math.cos(angle), cy+radius*math.sin(angle), xyze['Z']])
        extrusion = args.get('E', 0)
        if extrusion > 0 and any(k in args for k in 'XY'):
            if not relative_e: raise ValueError('Absolute object extrusion is unsupported')
            if (nozzle, waited_nozzle, bed, waited_bed) != (nozzle_temp, nozzle_temp, bed_temp, bed_temp):
                raise ValueError(f'Object deposition temperatures/waits differ: {(nozzle, waited_nozzle, bed, waited_bed)}')
            if not feature or feature == 'Custom': raise ValueError('Unexpected/unknown object deposition')
            row = features.setdefault(feature, {'moves': 0, 'layer_z_mm': set()})
            row['moves'] += 1
            row['layer_z_mm'].add(layer)
            if drawings is not None and layer in drawings:
                drawings[layer].append((feature, line_points))
    if conditional_depth: raise ValueError('Unclosed conditional block')
    if not points or not features or not layer_z: raise ValueError('No object toolpaths')
    bounds = bed_check(np.array(points), machine, margin=.3)
    return {'object_nozzle_bounds': bounds, 'layer_count': len(layer_z),
            'first_last_layer_z_mm': [min(layer_z), max(layer_z)],
            'object_temperature_C': nozzle_temp, 'bed_temperature_C': bed_temp,
            'temperature_waits_verified': True, 'support_deposition_moves': 0,
            'features': {k: {**v, 'layer_z_mm': sorted(v['layer_z_mm'])} for k, v in features.items()},
            'limits': 'Object paths only; vendor homing/purge/wipe excluded. No physical bridge/support-removal or printer calibration qualification.'}


def sliced_inspection(job, identity):
    import numpy as np
    from cadagent.mesh3mf import CORE_NS, read_3mf
    ns = {'m': CORE_NS, 'p': 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'}
    with zipfile.ZipFile(job / 'slice/out/sliced.3mf') as z:
        root = ET.fromstring(z.read('3D/3dmodel.model'))
        items = root.findall('m:build/m:item', ns)
        components = root.findall('m:resources/m:object/m:components/m:component', ns)
        if root.get('unit') != 'millimeter' or len(items) != 1 or len(components) != 1:
            raise ValueError('Expected one millimetre object in sliced project')
        component = components[0]
        if component.get('transform') != '1 0 0 0 1 0 0 0 1 0 0 0':
            raise ValueError('Unexpected nested object transform')
        part = ET.fromstring(z.read(component.get('{'+ns['p']+'}path').lstrip('/')))
        v = np.array([[float(q.get(k)) for k in 'xyz'] for q in part.findall('.//m:vertex', ns)])
        f = np.array([[int(q.get(k)) for k in ('v1', 'v2', 'v3')] for q in part.findall('.//m:triangle', ns)])
        source_v, source_f = read_3mf(job / 'geometry.3mf')
        if (v.shape != source_v.shape or not np.array_equal(f, source_f)
                or not np.allclose(v-v[0], source_v-source_v[0], atol=1e-4, rtol=0)):
            raise ValueError('Slicer repaired or changed the source mesh')
        transform = np.array([float(n) for n in items[0].get('transform').split()]).reshape(4, 3)
        rot = transform[:3]
        if (not np.allclose(rot @ rot.T, np.eye(3), atol=1e-7, rtol=0)
                or not np.isclose(np.linalg.det(rot), 1, atol=1e-7)
                or not np.allclose(rot[2], [0, 0, 1], atol=1e-7, rtol=0)):
            raise ValueError('Sliced placement changes scale, handedness or parent layer normal')
        placed = v @ rot + transform[3]
        if abs(placed[:, 2].min()) > 1e-4: raise ValueError('Sliced object is not on bed')
        bed = bed_check(placed, identity['effective_profiles']['machine'], margin=6.)
        actual = json.loads(z.read('Metadata/project_settings.config'))
        expected = {'printer_model': 'Bambu Lab P1S', 'printer_settings_id': PROFILES['printer'],
                    'print_settings_id': PROFILES['process'], 'filament_settings_id': [PROFILES['filament']],
                    'nozzle_diameter': ['0.4'], 'layer_height': '0.2', **OVERRIDES,
                    'textured_plate_temp': ['100'], 'filament_type': ['PA6-CF']}
        # Standard/high-flow variants may be retained as equal entries by Bambu.
        # Every variant must request the same trial temperature, never select one
        # favorable entry from inconsistent machine/filament mapping.
        for key in ('nozzle_temperature', 'nozzle_temperature_initial_layer'):
            values = actual.get(key)
            if not isinstance(values, list) or not values or set(values) != {'275'}:
                raise ValueError('Sliced nozzle temperature mapping differs')
            expected[key] = values
        if any(actual.get(k) != value for k, value in expected.items()):
            raise ValueError('Sliced machine/material/process mapping differs')
        gcode = z.read('Metadata/plate_1.gcode')
        if (job / 'slice/out/plate_1.gcode').read_bytes() != gcode:
            raise ValueError('Standalone and archived G-code differ')
        paths = toolpaths(gcode.decode(), identity['effective_profiles']['machine'])
        return {'placed_geometry': bed, 'transform_3mf': transform.tolist(),
                'in_plane_rotation_deg': math.degrees(math.atan2(rot[0, 1], rot[0, 0])),
                'parent_layer_normal_preserved': True, 'actual_settings': expected, 'toolpaths': paths,
                'limits': 'In-plane raster direction may differ from a future parent job; no structural equivalence claim.'}


def plot_layers(job, identity):
    """Retain visual witnesses of the actual first, bridge and final layers."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    drawings = {z: [] for z in (.2, 8.8, 23.2, 24.2)}
    toolpaths((job / 'slice/out/plate_1.gcode').read_text(), identity['effective_profiles']['machine'], drawings=drawings)
    fig, axes = plt.subplots(2, 2, figsize=(12, 12))
    colors = {'Bridge': '#dc2626', 'Overhang wall': '#f97316', 'Outer wall': '#172554', 'Inner wall': '#64748b'}
    for (height, paths), ax in zip(drawings.items(), axes.flat):
        if not paths: raise ValueError('Missing critical layer witness')
        ordered = sorted(paths, key=lambda row: row[0] in ('Bridge', 'Overhang wall'))
        ax.add_collection(LineCollection([p for _, p in ordered], colors=[colors.get(f, '#a5c9db') for f, _ in ordered], linewidths=.35))
        ax.set(xlim=(60, 196), ylim=(58, 194), aspect='equal', xlabel='X / mm', ylabel='Y / mm', title=f'Actual deposition at Z={height:g} mm')
    fig.suptitle('Unpowered RS04 fit observation — actual G-code\nRed: bridge; orange: overhang wall; blue/gray: other deposition. No physical bridge qualification.')
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(job / 'critical-layers.png', dpi=140)
    plt.close(fig)


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
    required = {'source.stl', 'geometry.3mf', 'critical-layers.png', 'measurements.csv', 'process-record.csv',
                'slice/machine.json', 'slice/process.json', 'slice/filament.json', 'slice/slicer.log',
                'slice/exit-code.json', 'slice/out/result.json', 'slice/out/sliced.3mf', 'slice/out/plate_1.gcode'}
    if not required <= set(report['files_sha256']):
        raise ValueError('Retained job is incomplete')
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
    if report['sliced_inspection'] != sliced_inspection(job, identity):
        raise ValueError('Actual sliced placement/toolpath inspection differs')
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
    inspection = sliced_inspection(job, identity)
    plot_layers(job, identity)
    with (job / 'measurements.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        fields = ['location', 'actual_screw_length_mm', 'remaining_grip_mm', 'measurement_uncertainty_mm',
                  'calculated_penetration_mm', 'seat_flatness_mm', 'contact_or_surface_notes',
                  'seat_diameter_mm', 'seat_depth_mm', 'photo', 'notes']
        writer.writerow(fields)
        for location in [f'motor_hole_{n:02}' for n in range(1, 11)] + ['bearing_seat_and_lip', 'dowel_1', 'dowel_2', 'outer_roof_1', 'outer_roof_2']:
            writer.writerow([location] + ['']*(len(fields)-1))
    with (job / 'process-record.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        fields = ['source_mesh_sha256', 'recipe', 'job_receipt_sha256', 'date_operator', 'printer', 'nozzle',
                  'plate', 'filament_brand_lot', 'drying_temperature_time', 'feeding_conditions', 'calibration', 'notes']
        writer.writerow(fields)
        writer.writerow([sha(job / 'source.stl'), RECIPE['id']] + ['']*(len(fields)-2))
    report = {'schema': 'gyropup.fit-job/1', 'recipe': RECIPE, 'qualification': QUALIFICATION,
              'slice_complete': True, 'inputs': before, 'slice_inputs': identity,
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'geometry': geometry, 'metrics': measurements(job), 'archive_members': sliced_members(job),
              'sliced_inspection': inspection}
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
