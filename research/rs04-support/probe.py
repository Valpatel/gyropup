"""Read-only RS04 contact/clearance investigation, not a mounting acceptance gate.

Run in the isolated CAD environment after committing this source:
  python -B research/rs04-support/probe.py --vendor-root references/vendor --out /new/probe

Imports all manufacturer solids, uses released cad-agent relations, and exports
only authored comparison rings. Geometric classification tolerances stay at their
released defaults; the recorded broad-phase near margin equals the touch margin.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cad'))
import rs04_lug_checks as lugs

MATING_Z = 25.0
OUTPUT_Z = 25.5
# Actual inch stock, not a nominal 2 mm substituted for 0.080 inch sheet.
THICKNESSES_MM = (2.032, 3.175)
INNER_DIAMETERS_MM = (80., 94.)
OUTER_DIAMETERS_MM = (118., 120.)
LUG_HOLE_D_MM = 4.5
DOWEL_CLEARANCE_D_MM = 5.3
# Query exact geometry only where enclosing boxes cannot prove no contact.
# This is a broad-phase policy, not a physical clearance/fit requirement.
BROAD_PHASE_MM = .01
CONTEXT = ('research/rs04-support/probe.py', 'research/rs04-support/README.md',
           'exports/leg/rs04-mounting-fit/checks.json')
LIMITS = [
    'This is contact geometry and finite-pose clearance evidence, not a qualified mounting design.',
    'No elastic contact, bolt preload, thread pull-out, creep or strength calculation is performed.',
    'A ring bridges interrupted support laterally; the existing axial-ray stack failures are not waived.',
    'Ring thickness replaces equal printed thickness. No motor/output datum or total nominal grip is moved.',
    'Ring holes are provisional clearance holes; no machining tolerance or locating fit is qualified.',
    'All 43 manufacturer solids are checked at the source pose; their motion ownership is not inferred.',
    'Authored output adapter and dyno hub are checked at eight angles. This is not a continuous motion proof.',
    'A projected head-footprint witness is an analysis region, not substitute bought hardware.',
    'Contact area is nominal geometric area, not a uniform pressure distribution or load rating.',
    'Remote pairs have analytical AABB gap lower bounds, not measured exact clearances.',
    'No stock washer is modelled without its selected manufacturer model and specification.',
    'No full hip frame, fixture, bearing, dowel or assembled-leg acceptance is established here.',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(vendor_root):
    import print_provenance
    project = print_provenance.snapshot(ROOT)
    private = lugs.private_inputs(vendor_root)
    if (private != lugs.PRIVATE_HASHES
            or project['toolkit_sources_sha256'] != lugs.TOOLKIT_SOURCES
            or project['versions'].get('cad-agent') != '0.4.2'
            or project['GYROPUP_CAD_PARAMS_sha256'] is not None):
        raise ValueError('Pinned vendor/toolkit/default-parameter identity differs')
    return {'project': project, 'private_files': private,
            'context': {p: digest(ROOT / p) for p in CONTEXT},
            'toolkit_commit': lugs.TOOLKIT_COMMIT}


def valid(shape, label):
    return lugs._valid(shape, label)


def box_values(shape):
    from cadagent.gates import bounding_box
    return list(bounding_box(shape))


def checkpoint(out, report):
    """Atomic diagnostic replacement; an interruption cannot publish a final result."""
    path = out / 'probe-incomplete.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def relation(a, b, a_name, b_name):
    from cadagent.gates import relate, Tolerances
    r = relate(a, b, Tolerances(), names=(a_name, b_name), contact_area=True)
    if r.state in ('unknown', 'unchecked') or r.error:
        raise ValueError(f'{a_name}/{b_name}: uncertain relation {r.to_dict()}')
    return r.to_dict()


def candidate_relations(candidate, name, counterparts):
    """Use the released broad phase and volume memoization; retain every requested pair."""
    from cadagent.gates import Assembly, Tolerances, relation_table
    tol = Tolerances(near_mm=BROAD_PHASE_MM)
    assembly = Assembly({name: candidate, **counterparts})
    boxes = {key: box_values(assembly.shape(key)) for key in assembly}
    table = relation_table(assembly, tol, only=[name], contact_area=True, cache=None)
    rows = {}
    for key in counterparts:
        r = table.get(name, key)
        if r.state in ('unknown', 'unchecked') or r.error:
            raise ValueError(f'{name}/{key}: uncertain relation {r.to_dict()}')
        if not r.exact:
            a, b = boxes[name], boxes[key]
            bound = math.sqrt(sum(max(0., a[i] - b[i + 3], b[i] - a[i + 3]) ** 2 for i in range(3)))
            if (r.state != 'apart' or not math.isfinite(bound) or bound <= tol.near_mm
                    or r.gap_lower_bound_mm is None
                    or abs(r.gap_lower_bound_mm - bound) > 5.0001e-7):
                raise ValueError(f'{name}/{key}: unjustified broad-phase relation {r.to_dict()}')
        rows[key] = r.to_dict()
    return rows, boxes, dict(table.stats)


def annulus(cq, outside, inside, z, thickness, xy=(0., 0.)):
    return valid(cq.Workplane('XY', origin=(xy[0], xy[1], z)).circle(outside / 2)
                 .circle(inside / 2).extrude(thickness), 'analysis annulus')


def ring(cq, outside, inside, thickness, axes):
    shape = cq.Workplane(obj=annulus(cq, outside, inside, MATING_Z, thickness))
    for x, y in axes:
        cutter = cq.Workplane('XY', origin=(x, y, MATING_Z - 1)).circle(LUG_HOLE_D_MM / 2).extrude(thickness + 2)
        shape = shape.cut(cutter)
    for angle in (3., 183.):
        x, y = 53 * math.cos(math.radians(angle)), 53 * math.sin(math.radians(angle))
        cutter = cq.Workplane('XY', origin=(x, y, MATING_Z - 1)).circle(DOWEL_CLEARANCE_D_MM / 2).extrude(thickness + 2)
        shape = shape.cut(cutter)
    return valid(shape, 'comparison spreader ring')


def probe(vendor_root, out, report):
    import cadquery as cq
    import gmi
    import fivebar as fb
    import rig_bench as rb
    from cadagent.evidence import shape_content_hash
    from cadagent.gates import Tolerances
    vendor_root = Path(vendor_root)
    before = inputs(vendor_root)
    report['source_inputs'] = before
    baseline = json.loads((ROOT / CONTEXT[-1]).read_text())
    lugs.validate_receipt(baseline, ROOT / 'exports/leg/rs04-mounting-fit', ROOT)
    report['baseline'] = {'receipt_sha256': digest(ROOT / CONTEXT[-1]),
                          'engineering_pass': baseline['pass'], 'counts': baseline['counts'],
                          'failures': [c['id'] for c in baseline['checks'] if c['status'] == 'fail'],
                          'factory_recesses': baseline['factory_recesses']}
    report['relation_policy'] = {'api': 'cadagent.gates.relation_table',
                                 'bounding_box_api': 'cadagent.gates.bounding_box',
                                 'candidate_pair_count': 59, 'cache': False,
                                 'tolerances': asdict(Tolerances(near_mm=BROAD_PHASE_MM))}
    report['candidate_rings'] = {}
    report['progress'] = {'stage': 'manufacturer_inputs', 'completed_candidates': 0}
    checkpoint(out, report)
    imported = cq.importers.importStep(str(vendor_root / lugs.PRIVATE_FILES[0]))
    plate, axes = lugs.select_lug_plate(imported)
    solids = imported.solids().vals()
    if len(solids) != 43:
        raise ValueError(f'Expected 43 manufacturer solids, got {len(solids)}')
    by_hash = {}
    for solid in solids:
        sha = shape_content_hash(valid(solid, 'manufacturer solid'))
        if sha in by_hash:
            raise ValueError('Duplicate manufacturer solid content identity')
        by_hash[sha] = solid
    plate_hash = shape_content_hash(plate)
    report['manufacturer_solids'] = {sha: {'bbox_mm': box_values(s), 'volume_mm3': s.Volume(),
                                         'is_lug_plate': sha == plate_hash}
                                     for sha, s in sorted(by_hash.items())}
    report['native_frame'] = {'mating_z_mm': MATING_Z, 'output_z_mm': OUTPUT_Z,
                              'axis': [0, 0, 1], 'lug_axes_xy_mm': axes,
                              'lug_plate_sha256': plate_hash}

    screw = valid(cq.importers.importStep(str(vendor_root / f'mcmaster/{lugs.PN}/{lugs.PN}.norm.step')),
                  'manufacturer M4 screw')
    sb = screw.BoundingBox()
    if max(abs(v - w) for v, w in zip(box_values(screw), [-3.5, -3.5, -20, 3.5, 3.5, 4])) > .001:
        raise ValueError('Manufacturer screw dimensions/frame changed')
    head_d = max(sb.xlen, sb.ylen)
    hole_d = gmi.clear('M4')
    if abs(hole_d - LUG_HOLE_D_MM) > 1e-9:
        raise ValueError('Actual printed lug-hole clearance changed')
    footprints = {}
    for x, y in axes:
        key = f'{math.degrees(math.atan2(y, x)):.5f}'
        # Thin analysis volume rests on the actual factory mounting plane. Its
        # lower annulus is exactly the projected head radius outside the actual
        # printed clearance bore; it is not a model of a washer.
        witness = annulus(cq, head_d, hole_d, MATING_Z, .1, (x, y))
        rel = relation(witness, plate, 'head_projected_footprint', 'manufacturer_lug_plate')
        area = math.pi / 4 * (head_d ** 2 - hole_d ** 2)
        contact = rel.get('contact_area_mm2')
        if rel['state'] != 'touching' or contact is None or not 0 < contact <= area + 1e-4:
            raise ValueError(f'{key}: invalid projected-footprint contact evidence')
        footprints[key] = {'axis_xy_mm': [x, y], 'annulus_d_mm': [hole_d, head_d],
                           'footprint_area_mm2': area, 'supported_area_mm2': contact,
                           'unsupported_area_mm2': area - contact,
                           'supported_fraction': contact / area, 'relation': rel}
    report['lug_footprints'] = footprints
    report['progress'] = {'stage': 'footprints_complete', 'completed_candidates': 0}
    checkpoint(out, report)

    # These are the authored mating rotating parts, not envelopes. The motor
    # native frame has its output face at z25.5. Both authoring functions use
    # the output face at z0 and the rotation axis +Z.
    adapter, adapter_info = gmi.output_adapter(fb.MOTOR, 'L')
    moving = {'leg_output_adapter': valid(adapter, 'leg adapter').translate((0, 0, OUTPUT_Z)),
              'dyno_hub': valid(rb.dyno_hub(), 'dyno hub').translate((0, 0, OUTPUT_Z))}
    report['authored_mating_parts'] = {
        name: {'sha256': shape_content_hash(shape), 'bbox_mm': box_values(shape)}
        for name, shape in moving.items()}
    report['authored_mating_parts']['leg_output_adapter']['axial_dimensions'] = adapter_info
    posed = {f'{part}@{angle}': shape.rotate((0, 0, 0), (0, 0, 1), angle)
             for part, shape in moving.items() for angle in range(0, 360, 45)}
    report['authored_mating_poses'] = {
        key: {'source_sha256': report['authored_mating_parts'][key.split('@')[0]]['sha256'],
              'sha256': shape_content_hash(shape), 'bbox_mm': box_values(shape),
              'rotation_origin_mm': [0, 0, 0], 'rotation_axis': [0, 0, 1],
              'angle_deg': int(key.split('@')[1])} for key, shape in posed.items()}
    counterparts = {**dict(sorted(by_hash.items())), **posed}
    report['progress'] = {'stage': 'candidates_ready', 'completed_candidates': 0}
    checkpoint(out, report)
    for outside in OUTER_DIAMETERS_MM:
        for inside in INNER_DIAMETERS_MM:
            for thickness in THICKNESSES_MM:
                name = f'od{outside:g}-id{inside:g}-t{thickness:g}'
                started = time.perf_counter()
                report['progress'] = {'stage': 'candidate_running', 'candidate': name,
                                      'completed_candidates': len(report['candidate_rings'])}
                checkpoint(out, report)
                print(f'Probing {name} against all 43 motor solids and authored rotating parts', flush=True)
                candidate = ring(cq, outside, inside, thickness, axes)
                rows, boxes, stats = candidate_relations(candidate, name, counterparts)
                vendor_relations = {sha: rows[sha] for sha in sorted(by_hash)}
                moving_relations = {part: {str(angle): rows[f'{part}@{angle}'] for angle in range(0, 360, 45)}
                                    for part in moving}
                # Bind the exact boxes used for broad-phase proof to the already
                # recorded shape/pose identities, rather than a second anonymous set.
                for key in counterparts:
                    expected = (report['manufacturer_solids'][key] if key in by_hash
                                else report['authored_mating_poses'][key])['bbox_mm']
                    if boxes[key] != expected:
                        raise ValueError(f'{key}: relation-table bounds changed')
                plate_relation = vendor_relations[plate_hash]
                support = plate_relation.get('contact_area_mm2')
                if (plate_relation.get('exact') is not True or plate_relation['state'] != 'touching'
                        or support is None or support <= 0):
                    raise ValueError(f'{name}: no measured lug-plate face support')
                # A top-face footprint lets the ring receive load from printed
                # material; its motor-side support remains explicitly partial.
                projected_area = candidate.Volume() / thickness
                path = out / f'{name}.step'
                cq.exporters.export(candidate, str(path))
                report['candidate_rings'][name] = {
                    'shape_sha256': shape_content_hash(candidate), 'step_sha256': digest(path),
                    'bbox_mm': boxes[name], 'relation_stats': stats,
                    'elapsed_s': time.perf_counter() - started,
                    'outside_d_mm': outside, 'inside_d_mm': inside, 'thickness_mm': thickness,
                    'lug_hole_d_mm': LUG_HOLE_D_MM, 'dowel_clearance_d_mm': DOWEL_CLEARANCE_D_MM,
                    'z_mm': [MATING_Z, MATING_Z + thickness],
                    'projected_face_area_mm2': projected_area, 'motor_contact_area_mm2': support,
                    'unsupported_motor_side_area_mm2': projected_area - support,
                    'vendor_relations': vendor_relations, 'authored_moving_relations': moving_relations,
                    'interference_found': any(r['state'] in ('overlapping', 'contains')
                                              for r in list(vendor_relations.values()) +
                                              [r for poses in moving_relations.values() for r in poses.values()]),
                    'nominal_stack': {'ring_replaces_print_mm': thickness,
                                      'remaining_printed_grip_mm': 15.6 - thickness,
                                      'total_grip_mm': 15.6, 'm4x20_penetration_mm': 4.4,
                                      'stack_verified_for_redesign': False},
                }
                # Preserve useful partial diagnostics if a later candidate fails.
                report['progress'] = {'stage': 'candidate_complete', 'candidate': name,
                                      'completed_candidates': len(report['candidate_rings'])}
                checkpoint(out, report)
                print(f'Completed {name}: {stats["kernel_queries"]} exact, '
                      f'{59 - stats["kernel_queries"]} bounded, '
                      f'{report["candidate_rings"][name]["elapsed_s"]:.2f}s', flush=True)
    report['source_inputs_after'] = inputs(vendor_root)
    if report['source_inputs_after'] != before:
        raise ValueError('Inputs changed during the probe')
    report['probe_complete'] = True
    report['progress'] = {'stage': 'complete', 'completed_candidates': 8}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New directory only')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'gyropup.rs04-support-probe/2', 'probe_complete': False,
              'engineering_pass': False, 'physical_fit_verified': False,
              'structural_qualification': False, 'fabrication_release': False,
              'limits': LIMITS}
    try:
        probe(args.vendor_root, args.out, report)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    (args.out / 'probe.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    if report['probe_complete']:
        (args.out / 'probe-incomplete.json').unlink()
    print(json.dumps({'probe_complete': report['probe_complete'], 'engineering_pass': False,
                      'error': report.get('error'), 'report': str(args.out / 'probe.json')}))
    return 0 if report['probe_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
