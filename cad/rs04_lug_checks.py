"""Bounded RS-04 front-lug checks using released cad-agent measurements.

Run on the isolated CAD host, with a private vendor cache; nothing is downloaded:
  python cad/rs04_lug_checks.py --vendor-root /path/references/vendor --out /new/run --export

This checks the actual printed seats and private manufacturer screw against the
selected manufacturer lug plate. The drawing's guaranteed thread depth is a
separate constraint: a deeper modelled hole does not extend that guarantee.
It preserves the candidate's known support failures. Receipt integrity is not
leg qualification. Declared driver access is limited to the stated fitting step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cad'))
PN = '91290A168'
MIN_ENGAGEMENT_MM = 4.0
DEPTH_RESERVE_MM = 0.5
EXPECTED_INSTANCES = {'leg_front': 10, 'leg_rear': 10, 'dyno': 10, 'coupon_nom': 10}
TOOLKIT_COMMIT = '2ad426943ce2c7232875e105e50810849f9a3e5e'
TOOLKIT_SOURCES = 'c2941322d5f3d000d3777b0047567211d06855861fa5e14229d7d7519fef3ed3'
CONTEXT_FILES = ('tools/test-rs04-lug-stacks.py', 'research/actuator-interfaces.md')
OUTPUT_PARTS = ('hip_frame', 'dyno_lug_plate', 'coupon_frame_ring_nom')
READY_FLAGS = ('physical_fit_verified', 'full_assembly_qualified', 'thread_mating_verified',
               'tool_access_verified', 'manufacturing_tolerance_stack_verified', 'strength_verified')
CONTROL_PENETRATION = {'legacy_counterbore_11': 6.9, 'legacy_dyno_14': 6., 'insufficient_engagement': 3.4}
SUPPORT_FAILURE_INSTANCES = {'leg_front_04', 'leg_front_09', 'leg_rear_03', 'leg_rear_08',
                             'coupon_nom_04', 'coupon_nom_09', 'dyno_02', 'dyno_07'}
SUPPORT_FAILURE_LINES = {'leg_front_04': 2, 'leg_front_09': 6, 'leg_rear_03': 2, 'leg_rear_08': 6,
                         'coupon_nom_04': 2, 'coupon_nom_09': 6, 'dyno_02': 0, 'dyno_07': 4}
RECESS_PROBES = {'native_minus_15': ('dyno_02', -15., 0), 'native_165': ('dyno_07', 165., 4)}
DRIVER_NAME = 'declared_3mm_hex_driver'
DRIVER_ENVELOPE = {'segments': [{'d': 4., 'length': 60.}, {'d': 25., 'length': 80.}], 'start': 'head'}
MEASURED_DRIVER_ENVELOPE = {**DRIVER_ENVELOPE, 'offset_mm': 0., 'swing': None}
DRIVER_STEP = {'order': 1, 'fit': 'motor',
               'note': 'Motor fitting on the separate frame/fixture, before upper links and stop posts are installed'}
PRIVATE_HASHES = {
    'robstride-rs-04/RS04.stp': '92859a1e85a8846881432e193c808fe03a3da49ac18ad201c2d89de1746b9082',
    'robstride-rs-04/RS04User_Manual260713.pdf': '6782bf105cf4cc945142e65356bd7a21a9fc007b008ec3616307956030d72b31',
    f'mcmaster/{PN}/{PN}.step': '8673cceae9ae657b9f1123f3cc019893698c47f39fcc0a5c376aee0c8cc3cf71',
    f'mcmaster/{PN}/{PN}.norm.step': '307eceea05ccd5456991bcac212aec25db6c6462895d8b9b1911f48a2061977a',
    f'mcmaster/{PN}/{PN}.norm.json': '1536c07d3dbb37b1690adeab0e8b6464324c157f7221ea13315b3e0d1f447827',
    f'mcmaster/{PN}/{PN}.page.json': 'b4611ea236efce814835b36b177955b5aaa511fafadf6c0a9dfe43afa55a977b',
}
PRIVATE_FILES = (
    'robstride-rs-04/RS04.stp', 'robstride-rs-04/RS04User_Manual260713.pdf',
    f'mcmaster/{PN}/{PN}.step', f'mcmaster/{PN}/{PN}.norm.step',
    f'mcmaster/{PN}/{PN}.norm.json', f'mcmaster/{PN}/{PN}.page.json',
)
LIMITS = [
    'Only the forty declared front-lug screw instances and the authored dyno hub interface are checked.',
    'The selected manufacturer lug plate is checked; the rest of the motor is not modelled in this bounded assembly.',
    'Fastener material rays sample the head seat, stack, hole and receiver. Features between samples can be missed.',
    'Exact screw-to-printed-part relations are checked. Full screw-to-motor thread mating is not checked.',
    'Four millimetres minimum engagement is a declared geometric screen, not a thread pull-out or torque rating.',
    'The 0.5 mm depth reserve is a nominal design allowance, not a verified manufacturing tolerance stack.',
    'Driver access uses a declared 4 mm diameter x 60 mm shaft and 25 mm diameter x 80 mm handle envelope from the screw head, '
    'at the separate motor-fitting step before upper links and stop posts; no actual tool, socket engagement, hand room or final service path is qualified.',
    'The eight unsupported stack sectors over factory-retainer recesses remain failures; their load-spreading capacity is unqualified.',
    'Physical fit, bearing fits, print shrink, fatigue, strength and operation remain unqualified.',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def instance_names():
    return {f'{group}_{i + 1:02d}' for group, count in EXPECTED_INSTANCES.items() for i in range(count)}


def instance_check_ids(name):
    return {f'fastener:{name}:{kind}' for kind in ('seat', 'stack', 'holes', 'engagement', 'tip', 'length', 'tool')} | {
        f'{name}:printed-relation', f'{name}:drawing-depth'}


def expected_check_ids():
    return set().union(*(instance_check_ids(n) for n in instance_names())) | {
        'instance-coverage', 'dyno-hub-clearance', 'coupon-parent-transform', 'input-stability',
        *(f'control:{n}' for n in CONTROL_PENETRATION), 'control:blocked-driver',
        *(f'factory-recess:{n}' for n in RECESS_PROBES)}


def context_inputs(root=ROOT):
    return {name: digest(Path(root) / name) for name in CONTEXT_FILES}


def validate_receipt(data, directory, root=ROOT):
    """Validate integrity of this explicitly FAILING candidate, never leg qualification.

    This validates the receipt's identity and recorded outcome; it does not rerun CAD.
    A changed accepted source/recipe needs a fresh run, never a re-signed old report.
    """
    root, directory = Path(root), Path(directory)
    inputs = data.get('source_inputs') or {}
    project = inputs.get('project') or {}
    source_files = {p.relative_to(root).as_posix(): digest(p) for folder in ('cad', 'catalog', 'designs')
                    for p in (root / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json')}
    if not source_files or project.get('files') != source_files or inputs.get('context_files') != context_inputs(root):
        raise ValueError('Source/context closure changed')
    if (inputs.get('private_files') != PRIVATE_HASHES or inputs.get('toolkit_commit') != TOOLKIT_COMMIT
            or project.get('toolkit_sources_sha256') != TOOLKIT_SOURCES
            or project.get('versions', {}).get('cad-agent') != '0.4.2'
            or project.get('GYROPUP_CAD_PARAMS_sha256') is not None):
        raise ValueError('Private/toolkit/parameter identity differs')
    if any(data.get(key) is not False for key in READY_FLAGS):
        raise ValueError('Bounded evidence cannot become readiness')
    if (data.get('assumptions') != LIMITS or data.get('schema') != 'cadagent.gate/1'
            or data.get('gate') != 'rs04-front-lugs'
            or data.get('limits') != {'min_engagement_mm': MIN_ENGAGEMENT_MM,
                                      'nominal_depth_reserve_mm': DEPTH_RESERVE_MM}):
        raise ValueError('Check limits differ')
    top = data.get('checks') or []
    ids = [c.get('id') for c in top]
    if len(ids) != len(set(ids)) or set(ids) != expected_check_ids():
        raise ValueError('Check coverage differs')
    counts = {s: sum(c.get('status') == s for c in top) for s in ('pass', 'warn', 'fail')}
    expected_failures = {f'fastener:{n}:stack' for n in SUPPORT_FAILURE_INSTANCES}
    expected_warnings = {f'fastener:{n}:length' for n in instance_names()}
    if ({c['id'] for c in top if c['status'] == 'fail'} != expected_failures
            or {c['id'] for c in top if c['status'] == 'warn'} != expected_warnings):
        raise ValueError('Known failure/warning membership changed; this is not an engineering approval')
    if (data.get('pass') is not False or sum(counts.values()) != len(top)
            or data.get('counts') != counts or data.get('status') != 'fail'
            or data.get('findings') != [c for c in top if c['status'] != 'pass']):
        raise ValueError('Engineering failure was promoted or summary is inconsistent')
    by_id = {c['id']: c for c in top}
    rows = data.get('instances') or []
    names = [r.get('name') for r in rows]
    if len(names) != len(set(names)) or set(names) != instance_names():
        raise ValueError('Instance coverage differs')
    for row in rows:
        name = row['name']
        measured = row.get('measurement') or {}
        depth = drawing_depth(row.get('toolkit_row', {}).get('grip_mm'),
                              measured.get('screw', {}).get('length_mm'), 5.)
        if (depth['pass'] is not True or row.get('drawing') != depth
                or by_id[f'{name}:drawing-depth'].get('evidence') != depth):
            raise ValueError('Measured drawing-depth evidence differs')
        if (by_id[f'fastener:{name}:length'].get('message') != '7.00 mm of thread modelled, the record says 5'
                or abs(row.get('toolkit_row', {}).get('thread_depth_mm', -1) - 7.) > .001):
            raise ValueError('Modelled-depth versus guaranteed-depth warning changed')
        if name in SUPPORT_FAILURE_LINES:
            failure = by_id[f'fastener:{name}:stack']
            angles = failure.get('evidence', {}).get('angles') or []
            if (not failure.get('message', '').startswith('nothing under printed within 0.05 mm')
                    or len(angles) != 8
                    or [a.get('angle') for a in angles if a.get('ok') is False] != [SUPPORT_FAILURE_LINES[name]]):
                raise ValueError('Known support-sector failure evidence changed')
        tool = measured.get('tool') or {}
        if (tool.get('clear') is not True or tool.get('blocked') != [] or tool.get('error')
                or tool.get('tool') != DRIVER_NAME or tool.get('step') != DRIVER_STEP['order']
                or tool.get('present') != ['printed', 'motor', name]
                or tool.get('envelope') != MEASURED_DRIVER_ENVELOPE or tool.get('start_t_mm') != -4.):
            raise ValueError('Declared driver evidence differs')
    controls = data.get('negative_controls') or {}
    if set(controls) != set(CONTROL_PENETRATION):
        raise ValueError('Negative-control coverage differs')
    for name, penetration in CONTROL_PENETRATION.items():
        row = controls[name]
        cs = row.get('checks') or []
        if len(cs) != len(instance_check_ids(name)) or {c.get('id') for c in cs} != instance_check_ids(name):
            raise ValueError('Negative-control check coverage differs')
        depth = drawing_depth(row.get('toolkit_row', {}).get('grip_mm'),
                              row.get('measurement', {}).get('screw', {}).get('length_mm'), 5.)
        if (row.get('caught') is not True or depth['pass'] is not False or row.get('drawing') != depth
                or abs(depth['nominal_penetration_mm'] - penetration) > .01
                or not any(c['id'] == f'{name}:drawing-depth' and c['status'] == 'fail'
                           and c.get('evidence') == depth for c in cs)):
            raise ValueError('Negative-control measured failure lost')
    driver = data.get('driver_approach') or {}
    blocked = driver.get('blocked_control') or {}
    block_evidence = blocked.get('tool') or {}
    if (driver.get('name') != DRIVER_NAME or driver.get('envelope') != DRIVER_ENVELOPE
            or driver.get('step') != DRIVER_STEP or blocked.get('caught') is not True
            or blocked.get('check', {}).get('id') != 'negative:blocked-driver'
            or blocked.get('check', {}).get('status') != 'fail'
            or block_evidence.get('clear') is not False or block_evidence.get('error')
            or not any(r.get('part') == 'blocked_driver_path' and r.get('state') in ('overlapping', 'contains')
                       for r in block_evidence.get('blocked', []))):
        raise ValueError('Driver blocked-path control missing or changed')
    recesses = data.get('factory_recesses') or {}
    if set(recesses) != set(RECESS_PROBES):
        raise ValueError('Factory-recess evidence coverage differs')
    for key, record in recesses.items():
        if (record.get('source_step_sha256') != PRIVATE_HASHES[PRIVATE_FILES[0]]
                or by_id[f'factory-recess:{key}'].get('evidence') != record
                or record.get('representative_instance') != RECESS_PROBES[key][0]
                or not isinstance(record.get('factory_fastener_sha256'), str)
                or len(record['factory_fastener_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in record['factory_fastener_sha256'])
                or abs(record.get('factory_head_z_mm', -1) - 24.79) > .001
                or abs(record.get('factory_head_recess_mm', -1) - .21) > .001):
            raise ValueError('Factory-retainer identity or recess changed')
        if set(record.get('candidate_shapes', {})) != {data.get('manufacturer_lug_plate', {}).get('sha256'),
                                                      record['factory_fastener_sha256']}:
            raise ValueError('Factory-recess candidate membership changed')
        rays = record.get('rays') or []
        if [r.get('radius_mm') for r in rays] != [2.45, 2.825, 3.2]:
            raise ValueError('Factory-recess ray coverage differs')
        for ray in rays:
            intervals = ray.get('material_intervals_t_from_z26') or {}
            starts = [span[0] for spans in intervals.values() for span in spans]
            if (not starts or record['factory_fastener_sha256'] not in intervals
                    or set(intervals) - set(record.get('candidate_shapes', {}))
                    or abs((min(starts) - 1.) - .21) > .001
                    or abs(ray.get('nearest_material_gap_mm', -1) - (min(starts) - 1.)) > 1e-6):
                raise ValueError('Factory-recess measured gap changed')
    artifacts = data.get('artifacts') or {}
    if set(artifacts) != set(OUTPUT_PARTS) or any(set(r.get('files', {})) != {'step', 'stl'} for r in artifacts.values()):
        raise ValueError('Artifact binding incomplete')
    for name, row in artifacts.items():
        mesh = row.get('stl_check') or {}
        if mesh.get('cad_valid') is not True or mesh.get('watertight') is not True or mesh.get('solid_count') != 1:
            raise ValueError('Invalid exported part receipt')
        for ext, expected in row['files'].items():
            path = directory / f'{name}.{ext}'
            if not path.is_file() or digest(path) != expected:
                raise ValueError('Public artifact changed')
    return True


def private_inputs(vendor_root):
    """Preflight the complete input set before importing a CAD kernel; never substitute envelopes."""
    vendor_root = Path(vendor_root)
    missing = [name for name in PRIVATE_FILES if not (vendor_root / name).is_file()]
    if missing:
        raise FileNotFoundError('Missing private inputs: ' + ', '.join(missing))
    return {name: digest(vendor_root / name) for name in PRIVATE_FILES}


def drawing_depth(grip_mm, length_mm, guaranteed_depth_mm, *, minimum=MIN_ENGAGEMENT_MM,
                  reserve=DEPTH_RESERVE_MM):
    """A drawing constraint on *measured* geometry, also usable in kernel-free controls."""
    values = (grip_mm, length_mm, guaranteed_depth_mm, minimum, reserve)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Finite measured grip, length and drawing limits are required')
    if min(grip_mm, length_mm, guaranteed_depth_mm, minimum) <= 0 or reserve < 0:
        raise ValueError('Invalid measured grip, length or drawing limits')
    penetration = length_mm - grip_mm
    remaining = guaranteed_depth_mm - penetration
    return {'pass': penetration >= minimum - 1e-6 and remaining >= reserve - 1e-6,
            'measured_grip_mm': grip_mm, 'measured_screw_length_mm': length_mm,
            'nominal_penetration_mm': round(penetration, 6),
            'guaranteed_thread_depth_mm': guaranteed_depth_mm,
            'remaining_guaranteed_depth_mm': round(remaining, 6),
            'minimum_engagement_mm': minimum, 'required_nominal_depth_reserve_mm': reserve,
            'basis': 'catalog/interfaces.json: robstride-rs-04.case.bolts.depth; drawing front face 5 Min'}


def _valid(shape, label):
    s = shape.val() if hasattr(shape, 'val') else shape
    if not s.isValid() or len(s.Solids()) != 1 or not math.isfinite(s.Volume()) or s.Volume() <= 0:
        raise ValueError(f'{label}: expected one valid nonempty solid')
    return s


def select_lug_plate(imported):
    """Identify the manufacturer solid geometrically, never by incidental STEP index."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    matches = []
    for solid in imported.solids().vals():
        axes = set()
        for face in solid.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Cylinder:
                continue
            cylinder = surface.Cylinder()
            axis = cylinder.Axis()
            point, direction = axis.Location(), axis.Direction()
            box = face.BoundingBox()
            if (abs(cylinder.Radius() - 1.65) < .01 and abs(direction.Z()) > .999999
                    and abs(math.hypot(point.X(), point.Y()) - 53) < .01
                    and abs(box.zmin - 18) < .01 and abs(box.zmax - 25) < .01):
                axes.add((round(point.X(), 5), round(point.Y(), 5)))
        box = solid.BoundingBox()
        if len(axes) == 10 and abs(box.zmin - 18) < .01 and abs(box.zmax - 25) < .01:
            matches.append((_valid(solid, 'manufacturer lug plate'), sorted(axes)))
    if len(matches) != 1:
        raise ValueError(f'Expected one RS04 solid with ten PCD106 front lug bores; found {len(matches)}')
    return matches[0]


def _relation_check(name, relation, parts):
    from cadagent.gates.verdict import Check
    clear = relation.state in ('apart', 'touching')
    return Check(name, 'pass' if clear else 'fail',
                 f'Exact relation: {relation.state}', parts, relation.to_dict())


def instance_assembly(name, printed, motor, screw, seat, guaranteed_depth):
    from cadagent.gates import Assembly
    from cadagent.gates.fasteners import FastenerSpec
    import gmi
    placed = _valid(gmi.place(screw, seat, (0, 1, 0)), name)
    assembly = Assembly({'printed': printed, 'motor': motor, name: placed})
    spec = FastenerSpec(name, 'printed', 'motor', axes=[(seat, (0, -1, 0))], key=PN,
                        diameter_mm=4., length_mm=20., pitch_mm=.7, min_engagement_mm=MIN_ENGAGEMENT_MM,
                        thread_depth_mm=guaranteed_depth, instances=[name], tool=DRIVER_NAME)
    return assembly, spec, placed


def check_instance(name, printed, motor, screw, seat, guaranteed_depth):
    """Reuse the toolkit's measurements/rules; do not infer fit from declared stack numbers."""
    from cadagent.gates import Tolerances, relate
    from cadagent.gates.fasteners import FastenerOptions, evaluate, measure, tool_access
    from cadagent.gates.verdict import Check
    assembly, spec, placed = instance_assembly(name, printed, motor, screw, seat, guaranteed_depth)
    options = FastenerOptions(lines=8, tip_clearance_mm=.5)
    relation = relate(placed, printed, Tolerances())
    measurement = measure(assembly, spec, 0, options, relations={'printed': relation})
    if measurement.get('error'):
        raise ValueError(f'{name}: {measurement["error"]}')
    measurement['tool'] = tool_access(assembly, spec, 0, DRIVER_NAME, DRIVER_ENVELOPE,
                                      ['printed', 'motor', name], DRIVER_STEP)
    checks, row = evaluate(spec, measurement, options)
    checks.append(_relation_check(f'{name}:printed-relation', relation, [name, 'printed']))
    depth = drawing_depth(row.get('grip_mm'), measurement['screw']['length_mm'], guaranteed_depth)
    checks.append(Check(f'{name}:drawing-depth', 'pass' if depth['pass'] else 'fail',
                        f"{depth['nominal_penetration_mm']:.3f} mm nominal penetration; "
                        f"{depth['remaining_guaranteed_depth_mm']:.3f} mm guaranteed-depth reserve",
                        [name, 'printed', 'motor'], depth))
    return checks, {'name': name, 'measurement': measurement, 'toolkit_row': row, 'drawing': depth}


def blocked_driver_control(printed, motor, screw, seat, depth):
    import cadquery as cq
    from cadagent.gates.fasteners import tool_access, tool_check
    name = 'blocked_driver_control'
    assembly, spec, _ = instance_assembly(name, printed, motor, screw, seat, depth)
    x, y, z = seat
    assembly.add('blocked_driver_path', cq.Solid.makeBox(10, 3, 10, cq.Vector(x - 5, y + 14, z - 5)))
    tool = tool_access(assembly, spec, 0, DRIVER_NAME, DRIVER_ENVELOPE,
                       ['printed', 'motor', name, 'blocked_driver_path'], DRIVER_STEP)
    check = tool_check('negative:blocked-driver', name, spec, tool)
    caught = (check.status == 'fail' and tool.get('clear') is False and not tool.get('error')
              and any(r['part'] == 'blocked_driver_path' and r['state'] in ('overlapping', 'contains')
                      for r in tool.get('blocked', [])))
    return {'caught': caught, 'tool': tool, 'check': check.to_dict(),
            'blocker': {'size_mm': [10, 3, 10], 'origin_mm': [x - 5, y + 14, z - 5]}}


def factory_recess_evidence(imported, plate, rows, dyno_turn, dyno_axis_z):
    """Probe the real factory-retainer recesses against every nearby imported solid.

    Identifications use surfaces/axes/bounds and content hashes, never STEP indices.
    The pinned toolkit's material-ray probe is diagnostic; it adds no support waiver.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Cone
    from cadagent.evidence import shape_content_hash
    from cadagent.gates import Assembly
    from cadagent.gates.fasteners import _Probe
    from cadagent.gates.verdict import Check
    solids = imported.solids().vals()
    if len(solids) != 43:
        raise ValueError('Pinned RS04 assembly must retain all 43 imported solids')
    result, checks = {}, []
    for key, (instance, angle_deg, line) in RECESS_PROBES.items():
        angle = math.radians(angle_deg)
        expected_xy = (57.6 * math.cos(angle), 57.6 * math.sin(angle))
        cylinders, cones = [], []
        for face in plate.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            kind, box = surface.GetType(), face.BoundingBox()
            if kind not in (GeomAbs_Cylinder, GeomAbs_Cone):
                continue
            geom = surface.Cylinder() if kind == GeomAbs_Cylinder else surface.Cone()
            point, direction = geom.Axis().Location(), geom.Axis().Direction()
            if abs(direction.Z()) < .999999 or math.hypot(point.X() - expected_xy[0], point.Y() - expected_xy[1]) > .01:
                continue
            if kind == GeomAbs_Cylinder and abs(geom.Radius() - 2.5) < .01 and abs(box.zmin - 24.65) < .01 and abs(box.zmax - 25) < .01:
                cylinders.append({'axis_xy_mm': [point.X(), point.Y()], 'radius_mm': geom.Radius(),
                                  'z_mm': [box.zmin, box.zmax]})
            if kind == GeomAbs_Cone and abs(abs(geom.SemiAngle()) - math.pi / 4) < .001 and abs(box.zmin - 23.6) < .01 and abs(box.zmax - 24.65) < .01:
                cones.append({'axis_xy_mm': [point.X(), point.Y()], 'angle_rad': geom.SemiAngle(),
                              'z_mm': [box.zmin, box.zmax]})
        if not cylinders or not cones:
            raise ValueError(f'{key}: factory countersink surfaces were not identified')
        factory = []
        for solid in solids:
            box = solid.BoundingBox()
            if (math.hypot((box.xmin + box.xmax) / 2 - expected_xy[0],
                           (box.ymin + box.ymax) / 2 - expected_xy[1]) < .02
                    and 1 < max(box.xlen, box.ylen) < 6.5 and 23.6 < box.zmax <= 25.01):
                factory.append(_valid(solid, key + ' factory fastener'))
        if len(factory) != 1:
            raise ValueError(f'{key}: expected one small coaxial factory fastener, found {len(factory)}')
        factory_hash = shape_content_hash(factory[0])
        row = next(r for r in rows if r['name'] == instance)
        measurement = row['measurement']
        origin = measurement['origin']
        radii = measurement['annulus']['radii_mm']
        phase = 2 * math.pi * (line + .5) / len(measurement['annulus']['lines'])
        c, s = math.cos(math.radians(-dyno_turn)), math.sin(math.radians(-dyno_turn))
        rays = []
        for radius in radii:
            wx = origin[0] + radius * math.cos(phase)
            rotated_y = dyno_axis_z - (origin[2] + radius * math.sin(phase))
            rays.append({'radius_mm': radius, 'native_xy_mm': [c * wx - s * rotated_y, s * wx + c * rotated_y]})
        xs, ys = [r['native_xy_mm'][0] for r in rays], [r['native_xy_mm'][1] for r in rays]
        candidates, boxes = {}, {}
        for solid in solids:
            box = solid.BoundingBox()
            if (box.xmin <= max(xs) and box.xmax >= min(xs) and box.ymin <= max(ys) and box.ymax >= min(ys)
                    and box.zmin <= 26 and box.zmax >= 22):
                sha = shape_content_hash(_valid(solid, 'recess probe candidate'))
                if sha in candidates:
                    raise ValueError('Duplicate imported shape identity in factory-recess probe')
                candidates[sha] = solid
                boxes[sha] = [box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax]
        if factory_hash not in candidates or shape_content_hash(plate) not in candidates:
            raise ValueError('Factory-recess probe omitted its plate or fastener')
        assembly = Assembly(candidates)
        probe = _Probe(assembly)
        for ray in rays:
            x, y = ray['native_xy_mm']
            intervals = probe.along(list(assembly), (x, y, 26), (0, 0, -1), 0, 4)
            starts = [iv[0] for spans in intervals.values() for iv in spans]
            if not starts:
                raise ValueError('Factory-recess material ray found no material')
            ray.update(material_intervals_t_from_z26=intervals, nearest_material_gap_mm=round(min(starts) - 1, 6))
        head_z = factory[0].BoundingBox().zmax
        record = {'source_step_sha256': PRIVATE_HASHES[PRIVATE_FILES[0]], 'representative_instance': instance,
                  'cylinder': cylinders[0], 'cone': cones[0], 'factory_fastener_sha256': factory_hash,
                  'candidate_shapes': boxes, 'factory_head_z_mm': head_z,
                  'factory_head_recess_mm': round(25 - head_z, 6), 'rays': rays,
                  'interpretation': 'The factory head is recessed below the mating plane; no support exception is granted.'}
        observed = abs(record['factory_head_recess_mm'] - .21) < .001 and all(
            abs(r['nearest_material_gap_mm'] - .21) < .001 for r in rays)
        checks.append(Check('factory-recess:' + key, 'pass' if observed else 'fail',
                            'Reproduce the recessed factory head and the unsupported annular sector', evidence=record))
        result[key] = record
    return checks, result


def geometry_checks(vendor_root, *, export_dir=None):
    import cadquery as cq
    import fivebar as fb
    import rig_bench as rb
    import gmi
    from cadagent.evidence import shape_content_hash
    from cadagent.gates import relate, Tolerances
    from cadagent.gates.verdict import Check
    vendor_root = Path(vendor_root)
    screw_dir = vendor_root / 'mcmaster' / PN
    page = json.loads((screw_dir / f'{PN}.page.json').read_text())
    norm = json.loads((screw_dir / f'{PN}.norm.json').read_text())
    parsed = page['specs']['parsed']
    if (page.get('pn') != PN or parsed['Length']['value'] != 20
            or parsed['Thread Size']['d'] != 4 or parsed['Thread Size']['pitch'] != .7
            or norm.get('kind') != 'screw' or norm.get('head') != 'flat underside'):
        raise ValueError('Offline screw metadata does not identify the selected M4 x 20 normalized screw')
    screw = _valid(cq.importers.importStep(str(screw_dir / f'{PN}.norm.step')), 'normalized screw')
    box = screw.BoundingBox()
    actual = [box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax]
    expected = [-3.5, -3.5, -20, 3.5, 3.5, 4]
    if any(abs(a - b) > .05 for a, b in zip(actual, expected)):
        raise ValueError(f'Normalized screw frame/dimensions differ: {actual}')
    imported_motor = cq.importers.importStep(str(vendor_root / PRIVATE_FILES[0]))
    motor_raw, lug_axes = select_lug_plate(imported_motor)
    motor = motor_raw.translate((0, 0, -gmi.STEP_FRAMES[fb.MOTOR]['output_z']))
    depth = gmi.CAT[fb.MOTOR]['case']['bolts']['depth']
    if depth != 5 or gmi.CAT[fb.MOTOR]['case']['bolts']['thread'] != 'M4':
        raise ValueError('RS04 front-lug drawing constraint differs; review this bounded checker')
    print('Building authored frame, dyno plate and exact parent coupon', flush=True)
    frame_built = fb.hip_frame()
    frame = _valid(frame_built, 'hip frame')
    dyno = _valid(rb.dyno_lug_plate(), 'dyno lug plate')
    coupon = _valid(rb.coupon_frame_ring_parent(frame_built), 'nominal parent-ring coupon')
    checks, rows, completed = [], [], {}
    shapes = {'hip_frame': frame, 'dyno_lug_plate': dyno, 'coupon_frame_ring_parent': coupon}
    (ax, _), (bx, _) = fb.motors()
    seat_y = fb.Y['frame'][1] - fb.LUG_CB
    r = gmi.motor_interface(fb.MOTOR)['case']['bolts']['pcd'] / 2
    cases = []
    for label, mx, front, printed in [('leg_front', ax, True, frame), ('leg_rear', bx, False, frame),
                                      ('coupon_nom', ax, True, coupon)]:
        placed_motor = gmi.place(motor.rotate((0, 0, 0), (0, 0, 1), fb.step_turn(front)),
                                 (mx, fb.Y['motor_out'], 0), (0, 1, 0))
        seats = [(mx + r * math.cos(math.radians(a)), seat_y, r * math.sin(math.radians(a)))
                 for a in fb.lug_angles(front)]
        cases.append((label, printed, placed_motor, seats))
    # The XZ installation reverses angular handedness. Clock about a dowel axis
    # so both the ten-hole pattern and the diametrically opposite dowels match.
    dyno_turn = -2 * fb.RS04_DOWELS[0]
    dyno_motor = gmi.place(motor.rotate((0, 0, 0), (0, 0, 1), dyno_turn),
                           (0, .5, rb.DYNO_AXIS_Z), (0, 1, 0))
    seats = [(x, rb.lug_screw_seat_y(), rb.DYNO_AXIS_Z + z)
             for x, z in rb.pts(2 * r, [fb.RS04_LUG0 + 36 * k for k in range(10)])]
    cases.append(('dyno', dyno, dyno_motor, seats))
    for label, printed, receiver, seats in cases:
        print(f'Measuring {label}: {len(seats)} screws', flush=True)
        receiver = _valid(receiver, label + ' manufacturer lug plate')
        completed[label] = 0
        for i, seat in enumerate(seats):
            name = f'{label}_{i + 1:02d}'
            cs, row = check_instance(name, printed, receiver, screw, seat, depth)
            checks.extend(cs)
            rows.append(row)
            completed[label] += 1
    checks.append(Check('instance-coverage', 'pass' if completed == EXPECTED_INSTANCES else 'fail',
                        'Every declared front-lug instance must be measured', evidence={'expected': EXPECTED_INSTANCES,
                                                                                       'completed': completed}))
    print('Diagnosing both factory-retainer recesses against all nearby manufacturer solids', flush=True)
    recess_checks, recesses = factory_recess_evidence(imported_motor, motor_raw, rows, dyno_turn, rb.DYNO_AXIS_Z)
    checks.extend(recess_checks)
    front_case = cases[0]
    blocked_driver = blocked_driver_control(front_case[1], front_case[2], screw, front_case[3][0], depth)
    checks.append(Check('control:blocked-driver', 'pass' if blocked_driver['caught'] else 'fail',
                        'The same declared driver must fail when a solid blocks its approach'))
    hub = _valid(gmi.place(rb.dyno_hub(), (0, .5, rb.DYNO_AXIS_Z), (0, 1, 0)), 'dyno hub')
    hub_relation = relate(dyno, hub, Tolerances())
    checks.append(_relation_check('dyno-hub-clearance', hub_relation, ['dyno_lug_plate', 'dyno_hub']))
    # Rebuild the defective geometry in this process only. A control counts as
    # caught only when the measurement completed and the intended rule failed.
    from unittest.mock import patch
    negative_controls = {}
    for label, counterbore in [('legacy_counterbore_11', 11.), ('insufficient_engagement', 7.5)]:
        print(f'Geometry control: {label}', flush=True)
        with patch.object(fb, 'LUG_CB', counterbore):
            defective = _valid(fb.hip_frame(), label)
        x, _, z = front_case[3][0]
        cs, control = check_instance(label, defective, front_case[2], screw,
                                     (x, fb.Y['frame'][1] - counterbore, z), depth)
        caught = any(c.id.endswith(':drawing-depth') and c.status == 'fail' for c in cs)
        negative_controls[label] = {'caught': caught, **control, 'checks': [c.to_dict() for c in cs]}
        checks.append(Check(f'control:{label}', 'pass' if caught else 'fail',
                            'Defective measured seat must fail the drawing-depth constraint'))
    # The old seat is the current plate cut back to its 14 mm main face; the
    # unrelated new hub relief is retained. This is an actual solid measurement.
    defective = _valid(dyno.cut(cq.Solid.makeBox(1000, 1000, 1000,
                                                cq.Vector(-500, rb.LUG_T, -500))), 'legacy dyno seats')
    x, _, z = seats[0]
    cs, control = check_instance('legacy_dyno_14', defective, dyno_motor, screw, (x, rb.LUG_T, z), depth)
    caught = any(c.id.endswith(':drawing-depth') and c.status == 'fail' for c in cs)
    negative_controls['legacy_dyno_14'] = {'caught': caught, **control, 'checks': [c.to_dict() for c in cs]}
    checks.append(Check('control:legacy_dyno_14', 'pass' if caught else 'fail',
                        'Measured 14 mm dyno seat must fail the drawing-depth constraint'))
    # Derive the print transform independently from the parent frame's outer face.
    coupon_print = coupon.rotate((0, 0, 0), (1, 0, 0), -90).translate((-ax, 0, fb.Y['frame'][1]))
    generated_coupon = _valid(rb.coupon_frame_ring(0), 'nominal print coupon')
    same_coupon = shape_content_hash(coupon_print) == shape_content_hash(generated_coupon)
    checks.append(Check('coupon-parent-transform', 'pass' if same_coupon else 'fail',
                        'Nominal coupon is the parent ring with the outer-face-down print transform',
                        evidence={'expected': shape_content_hash(coupon_print),
                                  'actual': shape_content_hash(generated_coupon)}))
    artifacts = {}
    if export_dir is not None:
        print('Exporting the three authored candidate parts', flush=True)
        from cadagent.geometry import export_print_stl
        export_dir = Path(export_dir)
        for name, shape, rotation in [('hip_frame', frame, ((1, 0, 0), -90)),
                                      ('dyno_lug_plate', dyno, None),
                                      ('coupon_frame_ring_nom', generated_coupon, None)]:
            cq.exporters.export(shape, str(export_dir / f'{name}.step'))
            mesh_report = export_print_stl(shape, export_dir / f'{name}.stl', rotation=rotation)
            artifacts[name] = {'stl_check': mesh_report,
                               'files': {ext: digest(export_dir / f'{name}.{ext}') for ext in ('step', 'stl')}}
    return checks, {'instances': rows, 'authored_shapes': {n: shape_content_hash(s) for n, s in shapes.items()},
                    'manufacturer_lug_plate': {'sha256': shape_content_hash(motor_raw), 'bore_axes_xy_mm': lug_axes,
                                               'bbox_mm': [-60, -60, 18, 60, 60, 25]},
                    'screw_bbox_mm': actual, 'dyno_motor_clock_deg': dyno_turn, 'artifacts': artifacts,
                    'negative_controls': negative_controls, 'factory_recesses': recesses,
                    'driver_approach': {'name': DRIVER_NAME, 'envelope': DRIVER_ENVELOPE,
                                        'step': DRIVER_STEP, 'blocked_control': blocked_driver}}


def run(vendor_root, *, export_dir=None):
    from cadagent.gates.verdict import Check, verdict
    import print_provenance
    checks, evidence, inputs = [], {}, {}
    try:
        inputs = {'project': print_provenance.snapshot(ROOT), 'private_files': private_inputs(vendor_root),
                  'context_files': context_inputs(), 'toolkit_commit': TOOLKIT_COMMIT}
        if (inputs['private_files'] != PRIVATE_HASHES
                or inputs['project']['toolkit_sources_sha256'] != TOOLKIT_SOURCES
                or inputs['project']['versions'].get('cad-agent') != '0.4.2'
                or inputs['project']['GYROPUP_CAD_PARAMS_sha256'] is not None):
            raise ValueError('Pinned manufacturer inputs, released toolkit or default parameters differ')
        checks, evidence = geometry_checks(vendor_root, export_dir=export_dir)
        after = {'project': print_provenance.snapshot(ROOT), 'private_files': private_inputs(vendor_root),
                 'context_files': context_inputs(), 'toolkit_commit': TOOLKIT_COMMIT}
        checks.append(Check('input-stability', 'pass' if after == inputs else 'fail',
                            'Project, toolkit and private inputs must remain unchanged during the check'))
    except Exception as exc:
        checks.append(Check('incomplete-geometry', 'fail', f'{type(exc).__name__}: {exc}'))
    return verdict('rs04-front-lugs', checks, assumptions=LIMITS,
                   limits={'min_engagement_mm': MIN_ENGAGEMENT_MM, 'nominal_depth_reserve_mm': DEPTH_RESERVE_MM},
                   extra={'source_inputs': inputs, **evidence, 'full_assembly_qualified': False,
                          'thread_mating_verified': False, 'tool_access_verified': False,
                          'manufacturing_tolerance_stack_verified': False, 'strength_verified': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New output directory; existing paths are refused')
    parser.add_argument('--export', action='store_true', help='Export authored candidate parts only')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    result = run(args.vendor_root, export_dir=args.out if args.export else None)
    (args.out / 'checks.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'pass': result['pass'], 'counts': result['counts'], 'report': str(args.out / 'checks.json')}))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
