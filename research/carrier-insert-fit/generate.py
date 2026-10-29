#!/usr/bin/env python3
"""Extract nominal fit specimens. Geometry identity is not physical qualification."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'cad'))
import print_provenance as provenance

# Capture before importing CAD modules that consume source/configuration.
INPUTS = provenance.snapshot(ROOT)
CONTEXT = provenance.context_snapshot(ROOT, sorted(HERE.glob('*.py')))
import cadquery as cq
import trimesh
from cadagent.gates import Tolerances, relate
from cadagent.gates.relations import RELATIONS_VERSION
from cadagent.geometry import export_print_stl
from cadagent.mesh3mf import write_3mf
import turret as turret
import turret_base_board as board
import turret_print

TOL = Tolerances(overlap_mm3=1e-6, contain_mm3=math.nextafter(5e-7, 0.))
SPECS = {
    'carrier-boss': {
        'part': 'base_board_carrier', 'clip_mm': [48., 56., -28.4, -16.4, 5.5, 15.],
        'mouth_mm': [48., -22.4, 9.], 'inward_axis': [1., 0., 0.],
        'rotation_y_deg': 90., 'print_axis': [0., 0., -1.],
        'stock_depth_mm': 8., 'pilot_depth_mm': 6.5,
    },
    'base-anchor': {
        'part': 'pan_base', 'clip_mm': [45., 53., -35., -27., 0., 18.],
        'mouth_mm': [53., -31., 9.], 'inward_axis': [-1., 0., 0.],
        'rotation_y_deg': 0., 'print_axis': [-1., 0., 0.],
        'stock_depth_mm': 8., 'pilot_depth_mm': 6.5,
    },
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shape(value):
    return value.val() if hasattr(value, 'val') else value


def valid(value):
    s = shape(value)
    if not s.isValid() or len(s.Solids()) != 1:
        raise ValueError('Specimen must be one valid solid')
    return s


def relation(a, b):
    r = relate(shape(a), shape(b), TOL, contact_area=False)
    if r.state not in ('apart', 'touching', 'overlapping', 'contains'):
        raise ValueError(f'Unknown geometry relation: {r.error or r.state}')
    return r


def same(a, b):
    r = relation(a, b)
    if r.state != 'contains' or r.contained != 'both':
        raise ValueError('Extracted geometry differs from its source')
    return r.to_dict()


def bore_probe(spec, start, stop, radius):
    origin = cq.Vector(*spec['mouth_mm'])
    direction = cq.Vector(*spec['inward_axis'])
    return cq.Solid.makeCylinder(radius, stop-start, origin + direction*start, direction)


def validate_local(s, spec):
    valid(s)
    # Independent dimensional witnesses, deliberately inside boundaries.
    bore = relation(s, bore_probe(spec, .01, 6.49, 1.99))
    if bore.state not in ('apart', 'touching'):
        raise ValueError('Nominal pilot is obstructed or too shallow')
    floor = relation(s, bore_probe(spec, 6.51, 7.99, 1.99))
    if floor.state != 'contains' or floor.contained != 'b_in_a':
        raise ValueError(f'Blind pilot floor/back wall is missing or too thin: {floor.to_dict()}')
    return {'pilot_clear': bore.to_dict(), 'floor_present': floor.to_dict()}


def printed(s, spec):
    angle = spec['rotation_y_deg']
    turned = s.rotate((0, 0, 0), (0, 1, 0), angle)
    b = turned.BoundingBox()
    shift = (-b.xmin, -b.ymin, -b.zmin)
    return turned.translate(shift), shift


def transformed_axis(spec):
    a = math.radians(spec['rotation_y_deg'])
    x, y, z = spec['inward_axis']
    return [math.cos(a)*x + math.sin(a)*z, y, -math.sin(a)*x + math.cos(a)*z]


def validate_orientation(spec):
    if any(abs(a-b) > 1e-9 for a, b in zip(transformed_axis(spec), spec['print_axis'])):
        raise ValueError('Insert pilot has the wrong layer/print orientation')


def controls(source, spec):
    outcomes = {}
    for name, fn in {
        'filled_pilot': lambda: validate_local(source.fuse(bore_probe(spec, .1, 6.4, 1.)), spec),
        'drilled_through': lambda: validate_local(source.cut(bore_probe(spec, -.1, 8.1, 2.)), spec),
        'wrong_orientation': lambda: validate_orientation({**spec, 'rotation_y_deg': spec['rotation_y_deg']+90.}),
    }.items():
        try:
            fn()
        except ValueError as error:
            outcomes[name] = {'rejected': True, 'reason': str(error)}
        else:
            raise ValueError(f'Negative control unexpectedly accepted: {name}')
    return outcomes


def run(output):
    if RELATIONS_VERSION != "4":
        raise ValueError('Use reviewed cad-agent relation engine4')
    if board.INSERT_PILOT != 4. or board.INSERT_LENGTH != 5.74:
        raise ValueError('Nominal insert/pilot basis changed; revise the specimen plan before regenerating')
    if output.exists():
        raise ValueError('Use a fresh output directory; do not overwrite a prior measurement package')
    parts = {'base_board_carrier': board.carrier().val(), 'pan_base': turret.pan_base(turret.Geo()).val()}
    records = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.carrier-fit-', dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, spec in SPECS.items():
            raw = valid(valid(parts[spec['part']]).intersect(board.box(*spec['clip_mm']).val()))
            witnesses = validate_local(raw, spec)
            validate_orientation(spec)
            negative = controls(raw, spec)
            oriented, translation = printed(raw, spec)
            step, stl = stage / f'{name}.step', stage / f'{name}.stl'
            cq.exporters.export(oriented, str(step))
            mesh_report = export_print_stl(oriented, stl)
            mesh = trimesh.load_mesh(stl, process=True)
            if (not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0
                    or len(mesh.split(only_watertight=False)) != 1):
                raise ValueError(f'{name}: invalid or disconnected print mesh')
            readback = valid(cq.importers.importStep(str(step)))
            step_relation = same(oriented, readback)
            # Recover source frame and compare the entire clipped specimen.
            inverse = readback.translate(tuple(-v for v in translation)).rotate((0,0,0), (0,1,0), -spec['rotation_y_deg'])
            original_relation = same(raw, inverse)
            mesh_bounds = mesh.bounds.tolist()
            bb = oriented.BoundingBox()
            expected_bounds = [[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]]
            error = max(abs(a-b) for row_a, row_b in zip(mesh_bounds, expected_bounds) for a, b in zip(row_a, row_b))
            if error > .02:
                raise ValueError(f'{name}: mesh bounds differ by {error} mm')
            package = write_3mf(stage / f'{name}.3mf', mesh.vertices, mesh.faces, name, turret_print.BED)
            package['file'] = f'{name}.3mf'
            recipe = turret_print.part_metadata(next(p for p in turret_print.PARTS if p[0] == spec['part']))
            recipe.update({'copies': 3, 'parent_part': spec['part'], 'settings_basis': 'Inherited requested parent recipe, not a sliced or proven process',
                           'printer': turret_print.PRINTER, 'process': turret_print.PROCESS,
                           'package_contains_settings': False, 'sliced': False, 'actual_printed': False})
            records[name] = {**spec, 'pilot_diameter_mm': board.INSERT_PILOT,
                'insert_model_length_mm': board.INSERT_LENGTH,
                'nominal_insert_tip_to_bore_floor_mm': spec['pilot_depth_mm']-board.INSERT_LENGTH,
                'floor_to_outer_face_mm': spec['stock_depth_mm']-spec['pilot_depth_mm'],
                'print_translation_mm': translation, 'bounds_mm': expected_bounds,
                'geometry_witnesses': witnesses, 'step_readback': step_relation, 'source_readback': original_relation,
                'negative_controls': negative, 'mesh': {'watertight': True, 'connected_components': 1,
                'triangles': len(mesh.faces), 'bounds_error_mm': error, 'export_report': mesh_report},
                'geometry_only_3mf': package, 'requested_recipe': recipe}
        with (stage/'measurements.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['specimen','repeat','print_batch','filament_lot','drying_record','printer_nozzle','slicer_version','resolved_profile_hash','support_removal','insert_lot','measured_pilot_mouth_mm','measured_pilot_depth_mm','measured_insert_length_mm','installation_tip','tip_temperature_C','dwell_seconds','seated_depth_mm','cracks_bulging','thread_obstruction','fixture_and_method','operator_date','notes'])
            for name in SPECS:
                for repeat in range(1,4):writer.writerow([name, repeat]+['']*20)
        receipt = {'schema': 'gyropup.carrier-insert-fit/1',
            'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'inputs': INPUTS, 'context_files': CONTEXT, 'relation_engine': RELATIONS_VERSION,
            'specimens': records, 'physical_measurements': None, 'physical_fit_verified': False, 'release_ready': False,
            'limits': ['Small specimens change heat flow, support, cooling and stress relative to complete parts.',
                       'No proven heat-setting temperature, dwell, installation load, retention torque or pull strength.',
                       'Geometry-only 3MF has no printer/process settings or G-code; apply and verify the recorded recipe.',
                       'Three repeats per orientation are a measurement plan, not a statistical qualification.']}
        receipt['files'] = {p.name: sha(p) for p in sorted(stage.iterdir()) if p.is_file()}
        if INPUTS != provenance.snapshot(ROOT) or CONTEXT != provenance.context_snapshot(ROOT, [ROOT/p for p in CONTEXT]):
            raise ValueError('Inputs changed during generation')
        (stage/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        stage.rename(output)
    print(json.dumps({'output': str(output), 'specimens': list(records), 'physical_fit_verified': False, 'release_ready': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out.resolve())
