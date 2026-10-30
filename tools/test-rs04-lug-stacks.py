"""Kernel-free receipt-integrity tests for an explicitly failing CAD candidate.

Actual geometry evidence comes from cad/rs04_lug_checks.py on the CAD host.
These controls cannot qualify a generated part or a manufacturer assembly.
"""
import importlib.util
import argparse
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rs04_lug_checks', ROOT / 'cad/rs04_lug_checks.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--pure', action='store_true', help='Run control tests before the real CAD receipt exists')
parser.add_argument('--receipt', type=Path, default=ROOT / 'exports/leg/rs04-mounting-fit/checks.json')
OPTIONS, REMAINING = parser.parse_known_args()


class LugStackControls(unittest.TestCase):
    def test_candidate_frame_and_local_dyno_seats(self):
        for grip in (24.1 - 8.5, 14 + 1.6):
            row = checks.drawing_depth(grip, 20., 5.)
            self.assertTrue(row['pass'])
            self.assertEqual(row['nominal_penetration_mm'], 4.4)
            self.assertEqual(row['remaining_guaranteed_depth_mm'], .6)

    def test_old_counterbore_fails_even_though_a_seven_mm_model_can_accept_it(self):
        old = checks.drawing_depth(24.1 - 11., 20., 5.)
        self.assertFalse(old['pass'])
        self.assertEqual(old['nominal_penetration_mm'], 6.9)
        self.assertEqual(old['remaining_guaranteed_depth_mm'], -1.9)

    def test_old_dyno_plate_fails(self):
        row = checks.drawing_depth(14., 20., 5.)
        self.assertFalse(row['pass'])
        self.assertEqual(row['nominal_penetration_mm'], 6.)

    def test_short_screw_and_no_reserve_fail(self):
        self.assertFalse(checks.drawing_depth(16.2, 20., 5.)['pass'])
        self.assertFalse(checks.drawing_depth(15.1, 20., 5.)['pass'])
        self.assertFalse(checks.drawing_depth(20.1, 20., 5.)['pass'])

    def test_missing_or_nonfinite_geometry_is_never_a_pass(self):
        for bad in (None, True, math.nan, math.inf, -1., 0.):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                checks.drawing_depth(bad, 20., 5.)

    def test_complete_private_input_set_is_required_before_geometry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                checks.private_inputs(root)
            for name in checks.PRIVATE_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'presence sentinel, never passed to a geometry loader')
            self.assertEqual(set(checks.private_inputs(root)), set(checks.PRIVATE_FILES))
            for name in checks.PRIVATE_FILES:
                path = root / name
                raw = path.read_bytes()
                path.unlink()
                with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                    checks.private_inputs(root)
                path.write_bytes(raw)


def synthetic_receipt(directory):
    """Only a schema/identity fixture. Its sentinel files are never CAD evidence."""
    def measured(name, grip):
        return {'name': name, 'measurement': {'screw': {'length_mm': 20.},
                'tool': {'clear': True, 'blocked': [], 'tool': checks.DRIVER_NAME, 'step': 1,
                         'present': ['printed', 'motor', name], 'envelope': checks.MEASURED_DRIVER_ENVELOPE,
                         'start_t_mm': -4.}},
                'toolkit_row': {'grip_mm': grip, 'thread_depth_mm': 7.}, 'drawing': checks.drawing_depth(grip, 20., 5.)}
    rows = [measured(name, 15.6) for name in sorted(checks.instance_names())]
    by_id = {key: {'id': key, 'status': 'pass'} for key in checks.expected_check_ids()}
    for row in rows:
        name = row['name']
        by_id[name + ':drawing-depth']['evidence'] = row['drawing']
        by_id[f'fastener:{name}:length'].update(status='warn', message='7.00 mm of thread modelled, the record says 5')
        if name in checks.SUPPORT_FAILURE_LINES:
            by_id[f'fastener:{name}:stack'].update(status='fail', message='nothing under printed within 0.05 mm',
                evidence={'angles': [{'angle': i, 'ok': i != checks.SUPPORT_FAILURE_LINES[name]} for i in range(8)]})
    controls = {}
    for name, penetration in checks.CONTROL_PENETRATION.items():
        row = measured(name, 20 - penetration)
        row['caught'] = True
        row['checks'] = [{'id': key, 'status': 'fail' if key.endswith(':drawing-depth') else 'pass',
                          **({'evidence': row['drawing']} if key.endswith(':drawing-depth') else {})}
                         for key in checks.instance_check_ids(name)]
        controls[name] = row
    artifacts = {}
    for name in checks.OUTPUT_PARTS:
        files = {}
        for ext in ('step', 'stl'):
            path = directory / f'{name}.{ext}'
            path.write_bytes(b'UNIT TEST IDENTITY SENTINEL: NOT CAD')
            files[ext] = checks.digest(path)
        artifacts[name] = {'files': files, 'stl_check': {'cad_valid': True, 'watertight': True, 'solid_count': 1}}
    source_files = {p.relative_to(ROOT).as_posix(): checks.digest(p) for folder in ('cad', 'catalog', 'designs')
                    for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json')}
    recesses = {}
    for key, (instance, _, _) in checks.RECESS_PROBES.items():
        record = {'source_step_sha256': checks.PRIVATE_HASHES[checks.PRIVATE_FILES[0]], 'representative_instance': instance,
                  'factory_fastener_sha256': 'a' * 64, 'factory_head_z_mm': 24.79, 'factory_head_recess_mm': .21,
                  'candidate_shapes': {'a' * 64: [], 'b' * 64: []},
                  'rays': [{'radius_mm': r, 'material_intervals_t_from_z26': {'a' * 64: [[1.21, 2.]], 'b' * 64: [[2.01, 4.]]},
                            'nearest_material_gap_mm': .21} for r in [2.45, 2.825, 3.2]]}
        recesses[key] = record
        by_id[f'factory-recess:{key}']['evidence'] = record
    top = list(by_id.values())
    return {'schema': 'cadagent.gate/1', 'gate': 'rs04-front-lugs',
            'limits': {'min_engagement_mm': checks.MIN_ENGAGEMENT_MM,
                       'nominal_depth_reserve_mm': checks.DEPTH_RESERVE_MM},
            'pass': False, 'status': 'fail',
            'counts': {s: sum(c['status'] == s for c in top) for s in ('pass', 'warn', 'fail')},
            'findings': [c for c in top if c['status'] != 'pass'], 'checks': top, 'instances': rows,
            'negative_controls': controls, 'factory_recesses': recesses, 'manufacturer_lug_plate': {'sha256': 'b' * 64},
            'driver_approach': {'name': checks.DRIVER_NAME, 'envelope': checks.DRIVER_ENVELOPE, 'step': checks.DRIVER_STEP,
                'blocked_control': {'caught': True, 'check': {'id': 'negative:blocked-driver', 'status': 'fail'},
                    'tool': {'clear': False, 'blocked': [{'part': 'blocked_driver_path', 'state': 'overlapping'}]}}},
            'artifacts': artifacts, 'assumptions': checks.LIMITS, **{k: False for k in checks.READY_FLAGS},
            'source_inputs': {'project': {'files': source_files, 'toolkit_sources_sha256': checks.TOOLKIT_SOURCES,
                                          'versions': {'cad-agent': '0.4.2'}, 'GYROPUP_CAD_PARAMS_sha256': None},
                              'context_files': checks.context_inputs(), 'private_files': checks.PRIVATE_HASHES,
                              'toolkit_commit': checks.TOOLKIT_COMMIT}}


class ReceiptControls(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.receipt = synthetic_receipt(self.directory)

    def validate(self, data):
        return checks.validate_receipt(data, self.directory)

    def test_complete_failing_receipt_has_integrity_but_is_not_qualified(self):
        self.assertTrue(self.validate(self.receipt))
        self.assertIs(self.receipt['pass'], False)

    def test_missing_failed_or_duplicate_check_cannot_pass(self):
        for mutate in (lambda d: d['checks'].pop(),
                       lambda d: d['checks'].append(copy.deepcopy(d['checks'][0])),
                       lambda d: next(c for c in d['checks'] if c['status'] == 'pass').update(status='fail')):
            changed = copy.deepcopy(self.receipt)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_lost_known_failure_or_promoted_engineering_pass_rejects(self):
        for mutate in (lambda d: d.update(status='pass'),
                       lambda d: d.__setitem__('pass', True),
                       lambda d: next(c for c in d['checks'] if c['status'] == 'fail').update(status='pass'),
                       lambda d: next(c for c in d['checks'] if c['status'] == 'warn').update(status='pass')):
            changed = copy.deepcopy(self.receipt)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_driver_and_recess_evidence_cannot_disappear_or_be_relabelled(self):
        for mutate in (lambda d: d['driver_approach'].pop('blocked_control'),
                       lambda d: d.__setitem__('checks', [c for c in d['checks'] if c['id'] != 'control:blocked-driver']),
                       lambda d: d['driver_approach']['blocked_control'].update(caught=False),
                       lambda d: d['instances'][0]['measurement']['tool'].update(clear=False),
                       lambda d: d['instances'][0]['measurement']['tool']['envelope'].update(offset_mm=100.),
                       lambda d: d['factory_recesses'].pop('native_165'),
                       lambda d: d['factory_recesses']['native_minus_15']['rays'].pop(),
                       lambda d: d['factory_recesses']['native_minus_15'].update(factory_head_recess_mm=0.)):
            changed = copy.deepcopy(self.receipt)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_all_instances_and_negative_controls_required(self):
        for mutate in (lambda d: d['instances'].pop(),
                       lambda d: d['instances'].append(copy.deepcopy(d['instances'][0])),
                       lambda d: d['negative_controls'].pop('legacy_dyno_14'),
                       lambda d: d['negative_controls']['legacy_dyno_14']['checks'].pop(),
                       lambda d: d['negative_controls']['legacy_dyno_14']['drawing'].__setitem__('pass', True)):
            changed = copy.deepcopy(self.receipt)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_source_context_toolkit_private_identity_required(self):
        for mutate in (lambda d: d['source_inputs']['project']['files'].pop('cad/fivebar.py'),
                       lambda d: d['source_inputs']['context_files'].clear(),
                       lambda d: d['source_inputs'].update(toolkit_commit='0' * 40),
                       lambda d: d['source_inputs']['project'].update(toolkit_sources_sha256='0' * 64),
                       lambda d: d['source_inputs']['private_files'].clear()):
            changed = copy.deepcopy(self.receipt)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_artifact_membership_and_bytes_are_required(self):
        changed = copy.deepcopy(self.receipt)
        del changed['artifacts']['hip_frame']['files']['step']
        with self.assertRaisesRegex(ValueError, 'Artifact binding'):
            self.validate(changed)
        (self.directory / 'hip_frame.step').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Public artifact changed'):
            self.validate(self.receipt)

    def test_measured_depth_and_readiness_cannot_be_relabelled(self):
        changed = copy.deepcopy(self.receipt)
        changed['instances'][0]['measurement']['screw']['length_mm'] = 22.
        with self.assertRaises(ValueError):
            self.validate(changed)
        for flag in checks.READY_FLAGS:
            changed = copy.deepcopy(self.receipt)
            changed[flag] = True
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'readiness'):
                self.validate(changed)


class CommittedReceipt(unittest.TestCase):
    @unittest.skipIf(OPTIONS.pure, 'Real CAD receipt is checked after collection; this invocation tests controls only')
    def test_current_committed_geometry_receipt(self):
        receipt = json.loads(OPTIONS.receipt.read_text())
        self.assertTrue(checks.validate_receipt(receipt, OPTIONS.receipt.parent))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *REMAINING])
