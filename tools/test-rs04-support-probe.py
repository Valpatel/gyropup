"""Kernel-free integrity checks for the unqualified RS04 contact investigation.

Exit zero means the complete, source-bound research receipt is intact. It does
not change its engineering/physical/fabrication acceptance flags to true.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cad'))
import print_provenance as provenance

SPEC = importlib.util.spec_from_file_location('rs04_support_probe', ROOT / 'research/rs04-support/probe.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
LUGS = PROBE.lugs
DEFAULT_RECEIPT = ROOT / 'research/rs04-support/results/probe.json'
RECEIPT = DEFAULT_RECEIPT
PURE = False
RINGS = {f'od{od:g}-id{id_:g}-t{thick:g}': (od, id_, thick)
         for od in (118., 120.) for id_ in (80., 94.) for thick in (2.032, 3.175)}
MOVING = {'leg_output_adapter', 'dyno_hub'}
POSES = {str(angle) for angle in range(0, 360, 45)}
PLATE = '7fbbc260947a82c2e8f1a426833b2b4a48d3303484a5b2df453ee8e57ad93a5c'
FLAGS = ('engineering_pass', 'physical_fit_verified', 'structural_qualification', 'fabrication_release')
# Set only after the actual 43-solid result has received independent review.
# A missing pin deliberately prevents a real receipt from passing this script.
EXPECTED_VENDOR_INVENTORY_SHA256 = None
EXPECTED_AUTHORED_INVENTORY_SHA256 = None
TOLERANCES = {'touch_mm': .01, 'overlap_mm3': .001, 'contain_mm3': .001,
              'near_mm': .01, 'volume_check_mm3': .01}
RELATION_POLICY = {'api': 'cadagent.gates.relation_table',
                   'bounding_box_api': 'cadagent.gates.bounding_box',
                   'candidate_pair_count': 59, 'cache': False, 'tolerances': TOLERANCES}
STATES = ('apart', 'touching', 'overlapping', 'contains', 'unknown', 'unchecked')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b, tol=1e-5):
    return finite(a) and finite(b) and abs(a - b) <= tol


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def box(bounds):
    return (isinstance(bounds, list) and len(bounds) == 6 and all(finite(v) for v in bounds)
            and all(bounds[i + 3] > bounds[i] for i in range(3)))


def box_gap(a, b):
    require(box(a) and box(b), 'Invalid broad-phase box')
    # Independently evaluate Euclidean distance between enclosing boxes. This is
    # a lower bound on solid distance, never an exact surface measurement.
    separations = [max(a[i] - b[i + 3], b[i] - a[i + 3], 0.) for i in range(3)]
    return math.hypot(*separations)


def rotated_enclosure(bounds, angle):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = [(c * x - s * y, s * x + c * y)
               for x in (bounds[0], bounds[3]) for y in (bounds[1], bounds[4])]
    return [min(x for x, _ in corners), min(y for _, y in corners), bounds[2],
            max(x for x, _ in corners), max(y for _, y in corners), bounds[5]]


def source_files(root):
    return {p.relative_to(root).as_posix(): provenance.digest(p)
            for folder in ('cad', 'catalog', 'designs') for p in (root / folder).rglob('*')
            if p.is_file() and p.suffix in ('.py', '.json')}


def strict_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result

    def bad_number(value):
        raise ValueError(f'Non-finite JSON number: {value}')

    def bounded_float(value):
        parsed = float(value)
        require(math.isfinite(parsed), 'Non-finite JSON number')
        return parsed

    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=bad_number,
                      parse_float=bounded_float)


def check_relation(row, a, b, bounds=None):
    require(isinstance(row, dict) and row.get('a') == a and row.get('b') == b,
            'Relation identity changed')
    require(row.get('state') in ('apart', 'touching', 'overlapping', 'contains')
            and type(row.get('exact')) is bool and row.get('cached') is False and not row.get('error'),
            'Uncertain or invalid relation')
    bound = None if bounds is None else box_gap(*bounds)
    if not row['exact']:
        require(bound is not None and bound > TOLERANCES['near_mm'] and row['state'] == 'apart'
                and close(row.get('gap_lower_bound_mm'), bound, 5.0001e-7),
                'Unproved broad-phase clearance')
        require(set(row) == {'a', 'b', 'state', 'exact', 'cached', 'gap_lower_bound_mm'},
                'A bound cannot claim exact gap, volume or contact measurements')
        return False
    require('gap_lower_bound_mm' not in row, 'Exact relation mislabeled as a bound')
    require(bound is None or bound <= TOLERANCES['near_mm'], 'Unexpected narrow-phase pair')
    gap, overlap = row.get('gap_mm'), row.get('overlap_mm3')
    require(finite(gap) and gap >= 0 and finite(overlap) and overlap >= 0,
            'Invalid relation measurements')
    require(bound is None or gap + 5.0001e-7 >= bound, 'Exact gap contradicts enclosing boxes')
    state = row['state']
    if state == 'apart':
        require(gap > .01 and overlap <= .001, 'Apart relation contradicts its measurements')
    elif state == 'touching':
        contact = row.get('contact_area_mm2')
        require(gap <= .01 and overlap <= .001 and finite(contact) and contact >= 0,
                'Touching relation contradicts its measurements')
        require(gap <= 1e-9 or contact == 0, 'A separated surface cannot have contact area')
    else:
        require(gap == 0 and overlap > .001, 'Interference relation contradicts its measurements')
        require(all(finite(row.get(k)) and row[k] >= 0 for k in ('a_outside_b_mm3', 'b_outside_a_mm3')),
                'Incomplete interference evidence')
        if state == 'contains':
            require(row.get('contained') in ('a_in_b', 'b_in_a', 'both'), 'Containment identity missing')
    return state in ('overlapping', 'contains')


def validate_receipt(data, directory, root=ROOT):
    """Validate recorded completeness/identity; no CAD is loaded or rerun."""
    root, directory = Path(root), Path(directory)
    require(data.get('schema') == 'gyropup.rs04-support-probe/2' and data.get('probe_complete') is True
            and 'error' not in data, 'Probe is incomplete or failed')
    require(data.get('progress') == {'stage': 'complete', 'completed_candidates': 8},
            'Final completion marker missing')
    require(data.get('relation_policy') == RELATION_POLICY, 'Relation policy or tolerances changed')
    require(all(data.get(k) is False for k in FLAGS), 'Research cannot become engineering acceptance')
    require(data.get('limits') == PROBE.LIMITS, 'Investigation limits changed')
    expected_files = {'probe.json', *(name + '.step' for name in RINGS)}
    require({p.name for p in directory.iterdir()} == expected_files, 'Public result file coverage differs')
    require(all((directory / name).is_file() and not (directory / name).is_symlink() for name in expected_files),
            'Result files must be regular local files')

    baseline_path = root / PROBE.CONTEXT[-1]
    baseline = strict_json(baseline_path)
    LUGS.validate_receipt(baseline, baseline_path.parent, root)
    expected_inputs = {'project': baseline['source_inputs']['project'],
                       'private_files': LUGS.PRIVATE_HASHES, 'toolkit_commit': LUGS.TOOLKIT_COMMIT,
                       'context': provenance.context_snapshot(root, [root / p for p in PROBE.CONTEXT])}
    before = data.get('source_inputs')
    require(before == expected_inputs and data.get('source_inputs_after') == before,
            'Source/context/runtime/input stability changed')
    require(before['project'].get('files') == source_files(root), 'CAD source closure changed')
    require(before['project'].get('toolkit_sources_sha256') == LUGS.TOOLKIT_SOURCES
            and before['project'].get('versions', {}).get('cad-agent') == '0.4.2'
            and before['project'].get('GYROPUP_CAD_PARAMS_sha256') is None,
            'Released toolkit or parameter identity changed')
    expected_baseline = {'receipt_sha256': provenance.digest(baseline_path), 'engineering_pass': baseline['pass'],
                         'counts': baseline['counts'],
                         'failures': [c['id'] for c in baseline['checks'] if c['status'] == 'fail'],
                         'factory_recesses': baseline['factory_recesses']}
    require(data.get('baseline') == expected_baseline and expected_baseline['engineering_pass'] is False,
            'Original failing baseline was lost or promoted')

    solids = data.get('manufacturer_solids') or {}
    require(len(solids) == 43 and all(sha(k) for k in solids) and PLATE in solids,
            'Manufacturer solid coverage changed')
    require(sha(EXPECTED_VENDOR_INVENTORY_SHA256)
            and provenance.fingerprint(solids) == EXPECTED_VENDOR_INVENTORY_SHA256,
            'Manufacturer inventory lacks its reviewed identity')
    for key, solid in solids.items():
        require(box(solid.get('bbox_mm')) and finite(solid.get('volume_mm3')) and solid['volume_mm3'] > 0
                and solid.get('is_lug_plate') is (key == PLATE), 'Invalid manufacturer solid evidence')
    native = data.get('native_frame') or {}
    expected_axes = sorted([[round(53 * math.cos(math.radians(-15 + 36 * i)), 5),
                             round(53 * math.sin(math.radians(-15 + 36 * i)), 5)] for i in range(10)])
    require(native == {'mating_z_mm': 25., 'output_z_mm': 25.5, 'axis': [0, 0, 1],
                       'lug_axes_xy_mm': expected_axes, 'lug_plate_sha256': PLATE},
            'Native mounting frame changed')
    footprints = data.get('lug_footprints') or {}
    expected_footprints = {f'{math.degrees(math.atan2(y, x)):.5f}': [x, y] for x, y in expected_axes}
    require(set(footprints) == set(expected_footprints), 'Lug footprint coverage changed')
    for key, xy in expected_footprints.items():
        row = footprints[key]
        area = math.pi / 4 * (7 ** 2 - 4.5 ** 2)
        support = row.get('supported_area_mm2')
        require(row.get('axis_xy_mm') == xy and len(row.get('annulus_d_mm', [])) == 2
                and close(row['annulus_d_mm'][0], 4.5) and close(row['annulus_d_mm'][1], 7.)
                and close(row.get('footprint_area_mm2'), area), 'Projected head footprint changed')
        check_relation(row.get('relation'), 'head_projected_footprint', 'manufacturer_lug_plate')
        require(row['relation']['state'] == 'touching' and finite(support) and 0 < support <= area + 1e-4
                and close(support, row['relation'].get('contact_area_mm2'))
                and close(row.get('unsupported_area_mm2'), area - support)
                and close(row.get('supported_fraction'), support / area), 'Footprint support arithmetic changed')

    authored = data.get('authored_mating_parts') or {}
    require(set(authored) == MOVING and all(sha(r.get('sha256')) and box(r.get('bbox_mm'))
                                         for r in authored.values()), 'Authored mating-part coverage changed')
    require(isinstance(authored['leg_output_adapter'].get('axial_dimensions'), dict),
            'Adapter placement dimensions missing')
    posed = data.get('authored_mating_poses') or {}
    require(set(posed) == {part + '@' + angle for part in MOVING for angle in POSES},
            'Posed shape identity coverage changed')
    require(sha(EXPECTED_AUTHORED_INVENTORY_SHA256)
            and provenance.fingerprint({'parts': authored, 'poses': posed}) == EXPECTED_AUTHORED_INVENTORY_SHA256,
            'Authored part/pose inventory lacks its reviewed identity')
    for key, row in posed.items():
        part, angle = key.split('@')
        bounds = row.get('bbox_mm')
        require(row.get('source_sha256') == authored[part]['sha256'] and sha(row.get('sha256'))
                and row.get('rotation_origin_mm') == [0, 0, 0] and row.get('rotation_axis') == [0, 0, 1]
                and row.get('angle_deg') == int(angle) and box(bounds), 'Posed shape frame changed')
        enclosure = rotated_enclosure(authored[part]['bbox_mm'], int(angle))
        require(all(bounds[i] >= enclosure[i] - 1e-5 and bounds[i + 3] <= enclosure[i + 3] + 1e-5
                    for i in range(3))
                and close(bounds[2], enclosure[2]) and close(bounds[5], enclosure[5]),
                'Posed bounds contradict the declared rigid rotation')
    candidates = data.get('candidate_rings') or {}
    require(set(candidates) == set(RINGS), 'Candidate ring coverage changed')
    for name, (od, id_, thickness) in RINGS.items():
        row = candidates[name]
        require(all(close(row.get(k), v) for k, v in
                    [('outside_d_mm', od), ('inside_d_mm', id_), ('thickness_mm', thickness),
                     ('lug_hole_d_mm', 4.5), ('dowel_clearance_d_mm', 5.3)])
                and row.get('z_mm') == [25., 25. + thickness], 'Candidate dimensions changed')
        require(sha(row.get('shape_sha256')) and sha(row.get('step_sha256'))
                and provenance.digest(directory / (name + '.step')) == row['step_sha256'],
                'Authored STEP artifact changed')
        bounds = row.get('bbox_mm')
        require(box(bounds) and all(close(v, expected) for v, expected in
                    zip(bounds, [-od / 2, -od / 2, 25., od / 2, od / 2, 25. + thickness])),
                'Candidate analytic bounds changed')
        require(finite(row.get('elapsed_s')) and row['elapsed_s'] >= 0, 'Candidate timing missing')
        vendor = row.get('vendor_relations') or {}
        moving = row.get('authored_moving_relations') or {}
        require(set(vendor) == set(solids) and set(moving) == MOVING
                and all(set(poses) == POSES for poses in moving.values()), 'Relation matrix coverage changed')
        collisions = [check_relation(rel, name, key, (bounds, solids[key]['bbox_mm'])) for key, rel in vendor.items()]
        collisions += [check_relation(rel, name, part + '@' + angle, (bounds, posed[part + '@' + angle]['bbox_mm']))
                       for part, poses in moving.items() for angle, rel in poses.items()]
        require(row.get('interference_found') is any(collisions), 'Interference summary hides or invents a collision')
        exact_rows = [rel for rel in list(vendor.values()) + [r for poses in moving.values() for r in poses.values()]
                      if rel['exact']]
        stats = row.get('relation_stats') or {}
        require(stats.get('parts') == 60 and stats.get('pairs') == 1770 and stats.get('cache_hits') == 0
                and stats.get('candidates') == len(exact_rows) and stats.get('kernel_queries') == len(exact_rows)
                and stats.get('states') == {s: sum(r['state'] == s for r in exact_rows) for s in STATES}
                and all(finite(stats.get(k)) and stats[k] >= 0 for k in ('broad_phase_s', 'narrow_phase_s')),
                'Batch query statistics disagree with the complete relation matrix')
        area = math.pi / 4 * (od ** 2 - id_ ** 2 - 10 * 4.5 ** 2 - 2 * 5.3 ** 2)
        support = row.get('motor_contact_area_mm2')
        require(vendor[PLATE]['exact'] is True and vendor[PLATE]['state'] == 'touching'
                and close(row.get('projected_face_area_mm2'), area, .001)
                and finite(support) and 0 < support <= area + .001
                and close(support, vendor[PLATE].get('contact_area_mm2'))
                and close(row.get('unsupported_motor_side_area_mm2'), row['projected_face_area_mm2'] - support),
                'Ring face/support arithmetic changed')
        require(row.get('nominal_stack') == {'ring_replaces_print_mm': thickness,
                                            'remaining_printed_grip_mm': 15.6 - thickness,
                                            'total_grip_mm': 15.6, 'm4x20_penetration_mm': 4.4,
                                            'stack_verified_for_redesign': False},
                'Nominal replacement stack changed or was qualified')
    return True


def synthetic_receipt(root, directory):
    """Schema/control fixture only; no fixture STEP or measurement is CAD evidence."""
    (root / 'cad').mkdir()
    (root / 'cad/model.py').write_text('# source identity sentinel\n')
    for name in PROBE.CONTEXT[:-1]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    project = {'files': source_files(root), 'toolkit_sources_sha256': LUGS.TOOLKIT_SOURCES,
               'versions': {'cad-agent': '0.4.2'}, 'GYROPUP_CAD_PARAMS_sha256': None}
    baseline = {'source_inputs': {'project': project}, 'pass': False,
                'counts': {'pass': 322, 'warn': 40, 'fail': 8}, 'factory_recesses': {},
                'checks': [{'id': f'fastener:{name}:stack', 'status': 'fail'}
                           for name in sorted(LUGS.SUPPORT_FAILURE_INSTANCES)]}
    baseline_path = root / PROBE.CONTEXT[-1]
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline))
    identities = {'project': project, 'private_files': LUGS.PRIVATE_HASHES, 'toolkit_commit': LUGS.TOOLKIT_COMMIT,
                  'context': provenance.context_snapshot(root, [root / p for p in PROBE.CONTEXT])}
    solids = {f'{i:064x}': {'bbox_mm': [-1, -1, 0, 1, 1, 1], 'volume_mm3': 1., 'is_lug_plate': False}
              for i in range(42)}
    solids[PLATE] = {'bbox_mm': [-60, -60, 18, 60, 60, 25], 'volume_mm3': 36357., 'is_lug_plate': True}
    axes = sorted([[round(53 * math.cos(math.radians(-15 + 36 * i)), 5),
                    round(53 * math.sin(math.radians(-15 + 36 * i)), 5)] for i in range(10)])

    def relation(a, b, area=None):
        return {'a': a, 'b': b, 'state': 'apart' if area is None else 'touching',
                'exact': True, 'cached': False, 'gap_mm': 1. if area is None else 0., 'overlap_mm3': 0.,
                **({} if area is None else {'contact_area_mm2': area})}

    authored = {name: {'sha256': provenance.fingerprint(name), 'bbox_mm': [-1, -1, 25.5, 1, 1, 27.5],
                      'axial_dimensions': {}} for name in MOVING}
    posed = {part + '@' + angle: {'source_sha256': authored[part]['sha256'],
              'sha256': provenance.fingerprint([part, angle]),
              'bbox_mm': rotated_enclosure(authored[part]['bbox_mm'], int(angle)),
              'rotation_origin_mm': [0, 0, 0], 'rotation_axis': [0, 0, 1], 'angle_deg': int(angle)}
             for part in MOVING for angle in POSES}

    footprints, rings = {}, {}
    for x, y in axes:
        area = math.pi / 4 * (7 ** 2 - 4.5 ** 2)
        support = area - (3.5 if abs(x) > 51 else 0)
        footprints[f'{math.degrees(math.atan2(y, x)):.5f}'] = {
            'axis_xy_mm': [x, y], 'annulus_d_mm': [4.5, 7.], 'footprint_area_mm2': area,
            'supported_area_mm2': support, 'unsupported_area_mm2': area - support,
            'supported_fraction': support / area,
            'relation': relation('head_projected_footprint', 'manufacturer_lug_plate', support)}
    for name, (od, id_, t) in RINGS.items():
        path = directory / (name + '.step')
        path.write_text('UNIT TEST IDENTITY SENTINEL; NOT CAD\n' + name)
        area = math.pi / 4 * (od ** 2 - id_ ** 2 - 10 * 4.5 ** 2 - 2 * 5.3 ** 2)
        rings[name] = {'outside_d_mm': od, 'inside_d_mm': id_, 'thickness_mm': t,
                       'lug_hole_d_mm': 4.5, 'dowel_clearance_d_mm': 5.3, 'z_mm': [25., 25. + t],
                       'shape_sha256': provenance.fingerprint(name), 'step_sha256': provenance.digest(path),
                       'bbox_mm': [-od / 2, -od / 2, 25., od / 2, od / 2, 25. + t], 'elapsed_s': 1.,
                       'projected_face_area_mm2': area, 'motor_contact_area_mm2': area - 20,
                       'unsupported_motor_side_area_mm2': 20., 'interference_found': False,
                       'vendor_relations': {key: relation(name, key, area - 20 if key == PLATE else None) for key in solids},
                       'authored_moving_relations': {part: {angle: relation(name, part + '@' + angle)
                                                           for angle in POSES} for part in MOVING},
                       'nominal_stack': {'ring_replaces_print_mm': t, 'remaining_printed_grip_mm': 15.6 - t,
                                         'total_grip_mm': 15.6, 'm4x20_penetration_mm': 4.4,
                                         'stack_verified_for_redesign': False}}
        for key in solids:
            if key != PLATE:
                rings[name]['vendor_relations'][key] = {
                    'a': name, 'b': key, 'state': 'apart', 'exact': False, 'cached': False,
                    'gap_lower_bound_mm': round(box_gap(rings[name]['bbox_mm'], solids[key]['bbox_mm']), 6)}
        refresh_stats(rings[name])
    data = {'schema': 'gyropup.rs04-support-probe/2', 'probe_complete': True, **{flag: False for flag in FLAGS},
            'progress': {'stage': 'complete', 'completed_candidates': 8}, 'relation_policy': copy.deepcopy(RELATION_POLICY),
            'limits': PROBE.LIMITS, 'source_inputs': identities, 'source_inputs_after': copy.deepcopy(identities),
            'baseline': {'receipt_sha256': provenance.digest(baseline_path), 'engineering_pass': False,
                         'counts': baseline['counts'], 'failures': [c['id'] for c in baseline['checks']], 'factory_recesses': {}},
            'manufacturer_solids': solids, 'native_frame': {'mating_z_mm': 25., 'output_z_mm': 25.5,
                'axis': [0, 0, 1], 'lug_axes_xy_mm': axes, 'lug_plate_sha256': PLATE}, 'lug_footprints': footprints,
            'authored_mating_parts': authored, 'authored_mating_poses': posed, 'candidate_rings': rings}
    (directory / 'probe.json').write_text(json.dumps(data))
    return data


def refresh_stats(row):
    """Keep synthetic collision controls internally consistent; not a producer."""
    exact = [rel for rel in list(row['vendor_relations'].values())
             + [r for poses in row['authored_moving_relations'].values() for r in poses.values()] if rel['exact']]
    row['relation_stats'] = {'parts': 60, 'pairs': 1770, 'cache_hits': 0,
                             'candidates': len(exact), 'kernel_queries': len(exact),
                             'states': {s: sum(r['state'] == s for r in exact) for s in STATES},
                             'broad_phase_s': .01, 'narrow_phase_s': .1}


class ReceiptControls(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.directory = self.root / 'results'
        self.directory.mkdir()
        self.receipt = synthetic_receipt(self.root, self.directory)
        # The existing lug verifier has its own real-receipt and adversarial
        # tests. This synthetic probe fixture isolates that already tested boundary.
        mocked = patch.object(LUGS, 'validate_receipt', return_value=True)
        mocked.start()
        self.addCleanup(mocked.stop)
        pin = patch.dict(globals(),
                         EXPECTED_VENDOR_INVENTORY_SHA256=provenance.fingerprint(self.receipt['manufacturer_solids']),
                         EXPECTED_AUTHORED_INVENTORY_SHA256=provenance.fingerprint(
                             {'parts': self.receipt['authored_mating_parts'], 'poses': self.receipt['authored_mating_poses']}))
        pin.start()
        self.addCleanup(pin.stop)

    def validate(self, data):
        return validate_receipt(data, self.directory, self.root)

    def rejected(self, mutate):
        changed = copy.deepcopy(self.receipt)
        mutate(changed)
        with self.assertRaises(ValueError):
            self.validate(changed)

    def test_complete_receipt_integrity_preserves_false_acceptance(self):
        self.assertTrue(self.validate(self.receipt))
        self.assertFalse(self.receipt['engineering_pass'])

    def test_incomplete_error_or_promoted_acceptance_fails(self):
        for mutate in (lambda d: d.update(probe_complete=False), lambda d: d.pop('source_inputs_after'),
                       lambda d: d.update(error='kernel failure'), lambda d: d.pop('progress')):
            self.rejected(mutate)
        for flag in FLAGS:
            self.rejected(lambda d, flag=flag: d.__setitem__(flag, True))

    def test_missing_ring_solid_footprint_part_or_pose_fails(self):
        name = next(iter(RINGS))
        for mutate in (lambda d: d['candidate_rings'].pop(name), lambda d: d['manufacturer_solids'].pop(PLATE),
                       lambda d: d['lug_footprints'].pop('-15.00000'),
                       lambda d: d['authored_mating_parts'].pop('dyno_hub'),
                       lambda d: d['candidate_rings'][name]['vendor_relations'].pop(PLATE),
                       lambda d: d['candidate_rings'][name]['authored_moving_relations']['dyno_hub'].pop('315')):
            self.rejected(mutate)

    def test_coherent_replacement_of_a_vendor_solid_cannot_preserve_integrity(self):
        def replace(d):
            old = next(k for k in d['manufacturer_solids'] if k != PLATE)
            new = 'e' * 64
            d['manufacturer_solids'][new] = d['manufacturer_solids'].pop(old)
            for row in d['candidate_rings'].values():
                row['vendor_relations'][new] = row['vendor_relations'].pop(old)
                row['vendor_relations'][new]['b'] = new
        self.rejected(replace)

    def test_unknown_error_nonfinite_and_inexact_relations_fail(self):
        name = next(iter(RINGS))
        for fields in ({'state': 'unknown'}, {'state': 'unchecked'}, {'error': 'failed Boolean'},
                       {'exact': False}, {'gap_mm': math.nan}, {'gap_mm': -1}, {'overlap_mm3': 1.}):
            self.rejected(lambda d, fields=fields: d['candidate_rings'][name]['authored_moving_relations']['dyno_hub']['0'].update(fields))

    def test_an_honestly_recorded_collision_is_not_hidden_or_qualified(self):
        data = copy.deepcopy(self.receipt)
        name = next(iter(RINGS))
        row = data['candidate_rings'][name]
        row['authored_moving_relations']['dyno_hub']['90'].update(
            state='overlapping', gap_mm=0., overlap_mm3=5., a_outside_b_mm3=100., b_outside_a_mm3=200.)
        row['interference_found'] = True
        refresh_stats(row)
        self.assertTrue(self.validate(data))
        row['interference_found'] = False
        with self.assertRaisesRegex(ValueError, 'hides'):
            self.validate(data)

    def test_bounds_cannot_fabricate_clearance_or_exact_measurements(self):
        name = next(iter(RINGS))
        solid = next(key for key in self.receipt['manufacturer_solids'] if key != PLATE)
        for fields in ({'gap_lower_bound_mm': 100.}, {'gap_lower_bound_mm': math.inf},
                       {'state': 'touching'}, {'contact_area_mm2': 0.}, {'gap_mm': 24.},
                       {'overlap_mm3': 0.}, {'exact': True}, {'cached': True}):
            self.rejected(lambda d, fields=fields: d['candidate_rings'][name]['vendor_relations'][solid].update(fields))
        for mutate in (lambda d: d['candidate_rings'][name]['bbox_mm'].__setitem__(2, 100.),
                       lambda d: d['manufacturer_solids'][solid]['bbox_mm'].__setitem__(5, 5.),
                       lambda d: d['authored_mating_poses']['dyno_hub@45']['bbox_mm'].__setitem__(2, 0.),
                       lambda d: d['authored_mating_poses']['dyno_hub@45'].update(angle_deg=90),
                       lambda d: d['relation_policy']['tolerances'].update(near_mm=1.),
                       lambda d: d['candidate_rings'][name]['relation_stats'].update(kernel_queries=0)):
            self.rejected(mutate)

    def test_nominal_apart_bounds_do_not_claim_a_physical_clearance(self):
        row = {'a': 'ring', 'b': 'part', 'state': 'apart', 'exact': False,
               'cached': False, 'gap_lower_bound_mm': .02}
        first = [-1, -1, 0, 1, 1, 1]
        self.assertFalse(check_relation(row, 'ring', 'part', (first, [-1, -1, 1.02, 1, 1, 2.02])))
        for gap in (.005, .01):
            row['gap_lower_bound_mm'] = gap
            # Z bounds begin at zero to avoid floating subtraction moving an
            # exactly-on-threshold synthetic bound above the policy margin.
            with self.assertRaisesRegex(ValueError, 'Unproved'):
                check_relation(row, 'ring', 'part', ([-1, -1, -1, 1, 1, 0], [-1, -1, gap, 1, 1, gap + 1]))
        exact = {'a': 'ring', 'b': 'part', 'state': 'touching', 'exact': True,
                 'cached': False, 'gap_mm': .005, 'overlap_mm3': 0., 'contact_area_mm2': 0.}
        self.assertFalse(check_relation(exact, 'ring', 'part', (first, [-1, -1, 1.005, 1, 1, 2.005])))

    def test_actual_plate_contact_cannot_be_replaced_by_a_bounded_row(self):
        name = next(iter(RINGS))
        self.rejected(lambda d: d['candidate_rings'][name]['vendor_relations'].__setitem__(PLATE,
                      {'a': name, 'b': PLATE, 'state': 'apart', 'exact': False,
                       'cached': False, 'gap_lower_bound_mm': 2.}))

    def test_support_arithmetic_and_stack_claims_cannot_be_relabelled(self):
        name = next(iter(RINGS))
        for mutate in (lambda d: d['lug_footprints']['-15.00000'].update(supported_fraction=1.),
                       lambda d: d['candidate_rings'][name].update(motor_contact_area_mm2=0.),
                       lambda d: d['candidate_rings'][name].update(unsupported_motor_side_area_mm2=0.),
                       lambda d: d['candidate_rings'][name]['nominal_stack'].update(stack_verified_for_redesign=True),
                       lambda d: d['baseline'].update(engineering_pass=True)):
            self.rejected(mutate)

    def test_source_context_toolkit_and_baseline_must_stay_bound(self):
        for mutate in (lambda d: d['source_inputs']['project']['files'].clear(),
                       lambda d: d['source_inputs']['context'].clear(),
                       lambda d: d['source_inputs'].update(toolkit_commit='0' * 40),
                       lambda d: d['source_inputs']['private_files'].clear(),
                       lambda d: d['baseline']['failures'].pop()):
            self.rejected(mutate)
        (self.root / 'cad/new_dependency.py').write_text('# new dependency\n')
        with self.assertRaisesRegex(ValueError, 'closure'):
            self.validate(self.receipt)

    def test_changed_missing_and_extra_artifacts_fail(self):
        path = self.directory / (next(iter(RINGS)) + '.step')
        original = path.read_bytes()
        path.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            self.validate(self.receipt)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.validate(self.receipt)
        path.write_bytes(original)
        (self.directory / 'probe-incomplete.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.validate(self.receipt)

    def test_duplicate_json_members_and_nonfinite_numbers_are_rejected(self):
        path = self.directory / 'probe.json'
        for text in ('{"probe_complete":false,"probe_complete":true}', '{"gap":NaN}', '{"gap":1e999}'):
            path.write_text(text)
            with self.assertRaises(ValueError):
                strict_json(path)


class ProducerBatchControls(unittest.TestCase):
    """Exercise orchestration without importing CAD or substituting geometry evidence."""
    def fake_toolkit(self, override=None):
        requested, calls = [], []

        class Assembly(dict):
            def shape(self, key):
                return self[key]

        def table(assembly, tol, **kwargs):
            calls.append({**kwargs, 'near_mm': tol.near_mm})

            def get(a, b):
                requested.append((a, b))
                bound = box_gap(assembly[a], assembly[b])
                data = {'a': a, 'b': b, 'state': 'apart', 'exact': False, 'cached': False,
                        'gap_lower_bound_mm': round(bound, 6)}
                if override:
                    data.update(override)
                return SimpleNamespace(**data, error=data.get('error'), to_dict=lambda: data)
            return SimpleNamespace(get=get, stats={'fixture': True})

        module = ModuleType('cadagent.gates')
        module.Assembly = Assembly
        module.Tolerances = lambda **kwargs: SimpleNamespace(near_mm=kwargs.get('near_mm', 1.))
        module.relation_table = table
        module.bounding_box = lambda shape: tuple(shape)
        mock = patch.dict(sys.modules, {'cadagent': ModuleType('cadagent'), 'cadagent.gates': module})
        mock.start()
        self.addCleanup(mock.stop)
        return requested, calls

    def test_public_batch_api_is_used_and_every_far_pair_is_retrieved(self):
        requested, calls = self.fake_toolkit()
        counterparts = {f'part{i}': [-1, -1, 10, 1, 1, 11] for i in range(59)}
        rows, boxes, stats = PROBE.candidate_relations([-1, -1, 0, 1, 1, 1], 'ring', counterparts)
        self.assertEqual(calls, [{'only': ['ring'], 'contact_area': True, 'cache': None, 'near_mm': .01}])
        self.assertEqual(requested, [('ring', key) for key in counterparts])
        self.assertEqual(set(rows), set(counterparts))
        self.assertEqual(set(boxes), {'ring', *counterparts})
        self.assertTrue(all(row['gap_lower_bound_mm'] == 9. for row in rows.values()))
        self.assertEqual(stats, {'fixture': True})

    def test_unknown_and_unjustified_bounds_fail_the_producer(self):
        for fields in ({'state': 'unknown'}, {'state': 'unchecked'}, {'gap_lower_bound_mm': 100.},
                       {'state': 'touching'}):
            self.fake_toolkit(fields)
            with self.assertRaises(ValueError):
                PROBE.candidate_relations([-1, -1, 0, 1, 1, 1], 'ring', {'part': [-1, -1, 10, 1, 1, 11]})
        self.fake_toolkit()
        with self.assertRaises(ValueError):
            PROBE.candidate_relations([-1, -1, 0, 1, 1, 1], 'ring', {'part': [-1, -1, 1.005, 1, 1, 2.005]})

    def test_interrupted_checkpoint_preserves_previous_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            previous = {'probe_complete': False, 'stage': 'footprints_complete'}
            PROBE.checkpoint(out, previous)
            with patch.object(Path, 'write_text', side_effect=OSError('interrupted write')):
                with self.assertRaises(OSError):
                    PROBE.checkpoint(out, {'probe_complete': False, 'stage': 'candidate_running'})
            self.assertEqual(strict_json(out / 'probe-incomplete.json'), previous)
            self.assertFalse((out / 'probe.json').exists())


class CommittedReceipt(unittest.TestCase):
    def test_current_complete_probe_receipt(self):
        if PURE:
            self.skipTest('Run without --pure after the actual receipt is collected and independently reviewed')
        self.assertEqual(RECEIPT.name, 'probe.json', 'Only the completed final report is accepted')
        self.assertTrue(validate_receipt(strict_json(RECEIPT), RECEIPT.parent))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--receipt', type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument('--pure', action='store_true')
    args, remaining = parser.parse_known_args()
    RECEIPT, PURE = args.receipt, args.pure
    unittest.main(argv=[sys.argv[0], *remaining])
