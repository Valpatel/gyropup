#!/usr/bin/env python3
"""Artifact faults must fail before the static study video is published."""
import importlib.util
import importlib.abc
import hashlib
import io
import json
from pathlib import Path
import shutil
import os
import signal
import sys
import subprocess
import tempfile
import unittest
import types
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('study_check', Path(__file__).resolve().parents[2] / 'tools/evidence/media/check-study-media.py')
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)

producer_spec = importlib.util.spec_from_file_location('e1_export', check.ROOT / 'tools/engineering/legs/export-hip-frame-e1.py')
producer = importlib.util.module_from_spec(producer_spec); producer_spec.loader.exec_module(producer)

renderer_spec = importlib.util.spec_from_file_location('e1_render', check.ROOT / check.VIDEO_RENDERER)
renderer = importlib.util.module_from_spec(renderer_spec); renderer_spec.loader.exec_module(renderer)


class RendererPaths(unittest.TestCase):
    def test_either_declared_identity_reads_the_same_current_report(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-source-') as tmp:
            root = Path(tmp)
            report = root / 'hardware/exports/leg/fea/summary.json'
            report.parent.mkdir(parents=True)
            report.write_bytes(b'current report')
            legacy = root / 'exports/leg/fea/summary.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'legacy decoy')
            with patch.object(renderer, 'ROOT', root):
                for key in ('exports/leg/fea/summary.json', 'hardware/exports/leg/fea/summary.json'):
                    receipt = {'source_hashes': {key: hashlib.sha256(report.read_bytes()).hexdigest()}}
                    self.assertEqual(renderer.report_input(receipt), report)
                    check.report_binding(root, receipt)

    def test_missing_duplicate_and_wrong_report_bindings_reject(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-binding-') as tmp:
            root = Path(tmp)
            report = root / 'hardware/exports/leg/fea/summary.json'
            report.parent.mkdir(parents=True)
            report.write_bytes(b'current report')
            value = hashlib.sha256(report.read_bytes()).hexdigest()
            for hashes in ({}, {'exports/leg/fea/summary.json': value, 'hardware/exports/leg/fea/summary.json': value},
                           {'hardware/exports/leg/fea/summary.json': '0' * 64}):
                with patch.object(renderer, 'ROOT', root), self.assertRaises(ValueError):
                    renderer.report_input({'source_hashes': hashes})
                with self.assertRaises(ValueError):
                    check.report_binding(root, {'source_hashes': hashes})

    def test_legacy_physical_report_cannot_replace_the_current_report(self):
        with tempfile.TemporaryDirectory(prefix='e1-render-missing-') as tmp:
            root = Path(tmp)
            legacy = root / 'exports/leg/fea/summary.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'legacy decoy')
            with patch.object(renderer, 'ROOT', root), self.assertRaises(FileNotFoundError):
                renderer.report_input({'source_hashes': {'exports/leg/fea/summary.json': hashlib.sha256(legacy.read_bytes()).hexdigest()}})
            with self.assertRaises(FileNotFoundError):
                check.report_binding(root, {'source_hashes': {'exports/leg/fea/summary.json': hashlib.sha256(legacy.read_bytes()).hexdigest()}})


class E1CollectorLifecycle(unittest.TestCase):
    def load_collector(self):
        path = check.ROOT / '.agents/plans/leg-control/regenerate-e1-field.py'
        spec = importlib.util.spec_from_file_location('e1_collector_test', path)
        module = importlib.util.module_from_spec(spec)
        # A normal import may define helpers, but cannot launch a process.
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('Operational import')):
            spec.loader.exec_module(module)
        return module

    def test_video_collector_import_is_inert(self):
        path = check.ROOT / '.agents/plans/leg-control/regenerate-e1-video.py'
        spec = importlib.util.spec_from_file_location('e1_video_collector_test', path)
        module = importlib.util.module_from_spec(spec)
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('Operational import')):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))

    def test_video_bootstrap_requires_both_actual_rig_history_objects(self):
        path = check.ROOT / '.agents/plans/leg-control/regenerate-e1-video.py'
        spec = importlib.util.spec_from_file_location('e1_video_history_test', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        record = json.loads((check.ROOT / 'hardware/exports/leg/rig-media.json').read_text())
        expected = (record['producer_revision'], record['derivation']['converter_revision'])
        self.assertEqual(module.rig_history_revisions(record), tuple(dict.fromkeys(expected)))
        changed = {**record, 'derivation': {**record['derivation'], 'converter_revision': 'b' * 40}}
        self.assertIn('b' * 40, module.rig_history_revisions(changed))
        for bad in ({}, {'producer_revision': 'main', 'derivation': {'converter_revision': 'a' * 40}},
                    {'producer_revision': 'a' * 40, 'derivation': {'converter_revision': None}}):
            with self.assertRaises(ValueError): module.rig_history_revisions(bad)

    def test_exact_worker_preflight_is_syntactically_valid(self):
        collector = self.load_collector()
        compile(collector.worker_preflight_code(), 'actual-worker-preflight', 'exec')

    def test_import_is_inert_and_children_start_unmasked(self):
        collector = self.load_collector()
        with tempfile.TemporaryDirectory(prefix='e1-phase-') as tmp:
            collector.ROOT = collector.OUT = Path(tmp)
            collector.results = {'phases': {}}
            collector.processes_quiescent = True
            code = 'import signal; assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, set())'
            collector.phase('unmasked', [sys.executable, '-I', '-S', '-B', '-c', code], timeout=3)
            self.assertTrue(collector.results['phases']['unmasked']['process_cleanup']['group_gone'])

    def test_pending_signal_before_popen_returns_retains_error_and_reaps_child(self):
        collector = self.load_collector()
        previous = signal.getsignal(signal.SIGTERM)
        actual_popen = subprocess.Popen
        created = []
        def spawn(*args, **kwargs):
            child = actual_popen(*args, **kwargs)
            created.append(child)
            os.kill(os.getpid(), signal.SIGTERM)
            return child
        def interrupt(signum, frame):
            raise KeyboardInterrupt('controlled pending TERM')
        try:
            signal.signal(signal.SIGTERM, interrupt)
            with tempfile.TemporaryDirectory(prefix='e1-pending-') as tmp:
                collector.ROOT = collector.OUT = Path(tmp)
                collector.results = {'phases': {}}
                collector.processes_quiescent = True
                with patch.object(collector.subprocess, 'Popen', spawn), self.assertRaisesRegex(KeyboardInterrupt, 'controlled pending TERM'):
                    collector.phase('pending', [sys.executable, '-I', '-S', '-B', '-c', 'import time; time.sleep(10)'], timeout=3)
                record = json.loads((Path(tmp) / 'result.json').read_text())['phases']['pending']
                self.assertIn('KeyboardInterrupt', record['original_error'])
                self.assertTrue(record['process_cleanup']['group_gone'])
                self.assertIsNotNone(created[0].poll())
        finally:
            signal.signal(signal.SIGTERM, previous)


class TopologyInspection(unittest.TestCase):
    def load(self, name):
        path = check.ROOT / '.agents/plans/hip-study' / name
        spec = importlib.util.spec_from_file_location('topology_' + name.replace('-', '_'), path)
        module = importlib.util.module_from_spec(spec)
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('Operational import')), patch.dict(
                sys.modules, {n: None for n in ('cadquery', 'cadagent', 'gmsh', 'OCP')}):
            spec.loader.exec_module(module)
        return module

    def test_synthetic_receipt_and_all_source_bindings_without_native_imports(self):
        worker = self.load('inspect-step-worker.py')
        with tempfile.TemporaryDirectory(prefix='topology-synthetic-') as tmp:
            root = Path(tmp); cfg = self.fixture(root)
            step, receipt = worker.bound_inputs(root, cfg)
            self.assertEqual(step.name, 'hip_frame.step')
            self.assertEqual(receipt['source_inputs']['project']['files'], cfg['cad_sources'])

    def fixture(self, root):
        # Explicit unit fixture, not a CAD artifact or claim that a historical
        # inspection recipe must remain current after future geometry changes.
        cfg = json.loads((check.ROOT / '.agents/plans/hip-study/topology-inputs.json').read_text())
        for name in cfg['cad_sources']:
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(('synthetic source input: ' + name).encode())
            cfg['cad_sources'][name] = hashlib.sha256(target.read_bytes()).hexdigest()
        step = root / cfg['step']['path']; step.parent.mkdir(parents=True, exist_ok=True)
        step.write_bytes(b'synthetic input-guard fixture; SI_UNIT(.MILLI.,.METRE.)')
        cfg['step']['sha256'] = hashlib.sha256(step.read_bytes()).hexdigest()
        receipt = root / cfg['receipt']['path']
        receipt.write_text(json.dumps({'source_inputs': {'project': {'files': cfg['cad_sources']}},
                                       'artifacts': {'hip_frame': {'files': {'step': cfg['step']['sha256']}}}}))
        cfg['receipt']['sha256'] = hashlib.sha256(receipt.read_bytes()).hexdigest()
        return cfg

    def test_missing_current_step_and_changed_source_or_payload_reject(self):
        worker = self.load('inspect-step-worker.py')
        with tempfile.TemporaryDirectory(prefix='topology-input-') as tmp:
            root = Path(tmp); cfg = self.fixture(root)
            worker.bound_inputs(root, cfg)
            step = root / cfg['step']['path']; original = step.read_bytes()
            old = root / 'exports/leg/rs04-mounting-fit/hip_frame.step'
            old.parent.mkdir(parents=True); old.write_bytes(original)
            step.unlink()
            with self.assertRaises(ValueError): worker.bound_inputs(root, cfg)
            step.write_bytes(original + b'changed')
            with self.assertRaises(AssertionError): worker.bound_inputs(root, cfg)
            step.write_bytes(original)
            source = root / next(iter(cfg['cad_sources']))
            source.write_bytes(source.read_bytes() + b'changed')
            with self.assertRaises(AssertionError): worker.bound_inputs(root, cfg)

    def test_inherited_parameter_rejects_actual_worker_before_output(self):
        worker = self.load('inspect-step-worker.py')
        study = HipStudyInputs().load_study()
        with tempfile.TemporaryDirectory(prefix='topology-env-') as tmp:
            root = Path(tmp); out = root / 'out'
            args = [part for name, value in {'root': root, 'config': root / 'missing', 'runtime': root / 'missing',
                                             'contract': root / 'missing', 'out': out}.items()
                    for part in ('--' + name, str(value))]
            with patch.dict(os.environ, {'GYROPUP_HIP_PARAMS': 'inherited-candidate.json'}), self.assertRaisesRegex(
                    ValueError, 'Inherited product parameters'):
                worker.main(args)
            self.assertFalse(out.exists())
            with patch.dict(os.environ, {'GYROPUP_HIP_PARAMS': 'inherited-candidate.json'}):
                study.use_params(root / 'old-behavior', None)
                self.assertEqual(os.environ['GYROPUP_HIP_PARAMS'], 'inherited-candidate.json')

    def test_actual_collector_phase_unmasks_and_reaps_pending_signal(self):
        collector = self.load('collect-step-topology.py')
        case = E1CollectorLifecycle()
        with patch.object(case, 'load_collector', return_value=collector):
            case.test_import_is_inert_and_children_start_unmasked()
            case.test_pending_signal_before_popen_returns_retains_error_and_reaps_child()

    def test_independent_capture_and_save_failures_reach_later_guards(self):
        collector = self.load('collect-step-topology.py')
        for failed in ('project', 'hardware'):
            for mode in ('capture', 'save'):
                with self.subTest(failed=failed, mode=mode):
                    seen = []; saved = {}
                    def observe(name):
                        seen.append(name)
                        if name == failed and mode == 'capture': raise OSError('capture failed')
                        return name
                    def save(name, value):
                        if name == failed + '-after.json' and mode == 'save': raise OSError('save failed')
                        saved[name] = value
                    observations = [(n + '-after.json', lambda n=n: observe(n), n)
                                    for n in ('project', 'hardware', 'runtime', 'status')]
                    result = {'status': 'PASS_IMPORT_TOPOLOGY_ONLY'}
                    with patch.object(collector, 'save', save), self.assertRaises(RuntimeError):
                        collector.final_observations(result, observations, lambda: None, True)
                    self.assertEqual(seen, ['project', 'hardware', 'runtime', 'status'])
                    self.assertEqual(saved['result.json']['status'], 'FAILED')

    def test_archive_nonquiescence_and_final_write_never_hide_primary_failure(self):
        collector = self.load('collect-step-topology.py')
        for fault in ('archive', 'nonquiescent', 'final-write'):
            seen = []
            def archive():
                seen.append('archive')
                if fault == 'archive': raise OSError('archive failure')
            def save(name, value):
                if name == 'result.json' and fault == 'final-write': raise OSError('final write failure')
            def actual():
                result = {'status': 'FAILED'}
                try: raise ValueError('primary diagnostic failure')
                except BaseException as exc:
                    result['original_error'] = str(exc); raise
                finally:
                    with patch.object(collector, 'save', save):
                        collector.final_observations(result, [('later', lambda: seen.append('later'), None)],
                                                     archive, fault != 'nonquiescent')
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'primary diagnostic failure'):
                actual()
            self.assertIn('later', seen)
            self.assertEqual('archive' in seen, fault != 'nonquiescent')
        with patch.object(collector, 'save', side_effect=OSError('final write failure')), self.assertRaises(RuntimeError):
            collector.final_observations({'status': 'PASS'}, [], lambda: None, True)

    def test_worker_final_record_failure_is_nonzero_or_preserves_primary(self):
        worker = self.load('inspect-step-worker.py')
        def write(*args): raise OSError('final worker write failed')
        result = {'status': 'PASS'}
        with self.assertRaises(OSError): worker.final_record(result, write)
        self.assertEqual(result['status'], 'FAILED')
        result = {'status': 'FAILED', 'original_error': 'native primary'}
        worker.final_record(result, write)
        self.assertEqual(result['original_error'], 'native primary')

    def test_hardware_inventory_rejects_a_symlink_directory(self):
        collector = self.load('collect-step-topology.py')
        with tempfile.TemporaryDirectory(prefix='topology-links-') as tmp:
            root = Path(tmp); (root / 'real').mkdir(); (root / 'link').symlink_to(root / 'real')
            with self.assertRaises(ValueError): collector.inventory(root)

    def test_invalid_output_refuses_before_handlers_or_final_writes(self):
        collector = self.load('collect-step-topology.py')
        with tempfile.TemporaryDirectory(prefix='topology-output-') as tmp:
            root = Path(tmp); out = root / 'hardware'; out.mkdir()
            with patch.object(Path, 'cwd', return_value=root), patch.dict(os.environ, {'FLEET_RUN_OUT': str(out)}), patch.object(
                    sys, 'argv', ['collector', '--head', 'a' * 40, '--runtime', str(root / 'absent')]), patch.object(
                    collector.ctypes, 'CDLL', side_effect=AssertionError('Unexpected handler setup')), self.assertRaisesRegex(
                    AssertionError, 'Invalid owned output directory'):
                collector.main()
            self.assertEqual(list(out.iterdir()), [])

    def test_submitter_import_and_exact_remote_program_are_inert(self):
        submit = self.load('submit-topology-once.py')
        compile(submit.REMOTE, 'actual-remote-topology-bootstrap', 'exec')
        with self.assertRaisesRegex(AssertionError, 'Explicit execution required'):
            submit.main(['--review-url', 'https://github.com/Valpatel/gyropup/issues/8#fixture',
                         '--operator-sha256', '0' * 64, '--config-sha256', '0' * 64,
                         '--private-config', '/tmp/nonexistent-topology-unit-fixture',
                         '--receipt', '/tmp/nonexistent-topology-unit-intent'])

    def test_submit_hash_guards_precede_network_and_intent(self):
        submit = self.load('submit-topology-once.py')
        with tempfile.TemporaryDirectory(prefix='topology-submit-hash-') as tmp:
            root = Path(tmp); cfg = root / 'config.json'; cfg.write_text('{}')
            for bad in ('operator', 'config'):
                out = root / (bad + '-intent.json')
                args = ['--execute', '--review-url', 'https://github.com/Valpatel/gyropup/issues/8#fixture',
                        '--operator-sha256', '0' * 64 if bad == 'operator' else submit.sha(submit.__file__),
                        '--config-sha256', '0' * 64 if bad == 'config' else submit.sha(cfg),
                        '--private-config', str(cfg), '--receipt', str(out)]
                with patch.object(submit, 'command', side_effect=AssertionError('Network reached')) as command:
                    with self.assertRaises(AssertionError): submit.main(args)
                    command.assert_not_called()
                self.assertFalse(out.exists())

    def test_controller_result_is_unambiguous_and_never_repeatable(self):
        submit = self.load('submit-topology-once.py')
        started = {'head': 'a' * 40, 'cpus': [0, 1, 2, 3], 'launcher_pid': 42, 'run': '/tmp/fixture-run',
                   'command': ['bash', '/tmp/fixture-run/src/.agents/plans/hip-study/launch-step-topology.sh'],
                   'started_utc': '2026-11-07T00:00:00Z'}
        cases = ((1, '', AssertionError), (0, 'not a launcher receipt', json.JSONDecodeError),
                 (0, json.dumps({**started, 'launcher_pid': 0}), AssertionError),
                 (0, json.dumps(started), None))
        for rc, stdout, error in cases:
            with self.subTest(rc=rc), tempfile.TemporaryDirectory(prefix='topology-submit-fault-') as tmp:
                root = Path(tmp); repo = root / 'repo'; repo.mkdir()
                cli = root / 'fixture-cli'; cli.write_text('synthetic client fixture')
                files = {}
                for name in submit.SOURCE_FILES:
                    target = repo / name; target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(check.ROOT / name, target); files[name] = submit.sha(target)
                cfg = {'repo': str(repo), 'head': 'a' * 40, 'base': 'b' * 40, 'pr': 263,
                       'branch': 'study/hip-frame-foot-topology', 'files': files, 'fleet_cli': str(cli),
                       'fleet_cli_sha256': submit.sha(cli), 'role': 'cpu-a', 'node': 'fixture-node',
                       'fleet_environment_file': str(root / 'fixture-env'), 'runtime_sha256': 'c' * 64,
                       'run_name': 'fixture-run'}
                config = root / 'config.json'; config.write_text(json.dumps(cfg))
                intent = root / 'intent.json'
                def command(argv, **kwargs):
                    if argv[:3] == ['git', 'rev-parse', 'HEAD']: return cfg['head']
                    if argv[:3] == ['git', 'status', '--porcelain']: return ''
                    if argv[0] == 'gh':
                        if '/pulls/' in argv[-1]:
                            return json.dumps({'state': 'open', 'merged': False, 'draft': True,
                                               'head': {'sha': cfg['head'], 'ref': cfg['branch']},
                                               'base': {'ref': 'dev', 'sha': cfg['base']}})
                        return json.dumps({'state': 'open'})
                    if argv == [str(cli), 'nodes']:
                        return 'NODE STATE CPU MEMORY LOAD ROLE\nfixture-node IDLE 0/12 0/32768 0 cpu-a\n'
                    if argv == [str(cli), 'queue']: return 'JOB HEADER\n'
                    if argv[0] == 'bash': return 'fixture-node:fixture-target'
                    raise AssertionError('Unexpected mocked command')
                args = ['--execute', '--review-url', 'https://github.com/Valpatel/gyropup/issues/8#fixture',
                        '--operator-sha256', submit.sha(submit.__file__), '--config-sha256', submit.sha(config),
                        '--private-config', str(config), '--receipt', str(intent)]
                with patch.object(submit, 'command', command), patch.object(submit.subprocess, 'run', return_value=
                        types.SimpleNamespace(returncode=rc, stdout=stdout, stderr='controlled client output')) as invoke:
                    if error:
                        with self.assertRaises(error): submit.main(args)
                    else:
                        output = io.StringIO()
                        with patch.object(sys, 'stdout', output): submit.main(args)
                        self.assertEqual(json.loads(output.getvalue())['status'], 'STARTED_NOT_ACCEPTED')
                    record = json.loads(intent.read_text())
                    self.assertEqual(record['returncode'], rc)
                    self.assertEqual(record['stdout'], stdout)
                    self.assertEqual('local_error' in record, error is not None)
                    first = intent.read_bytes()
                    with self.assertRaises(AssertionError): submit.main(args)
                    self.assertEqual(intent.read_bytes(), first)
                    self.assertEqual(invoke.call_count, 1)


class FieldStage(unittest.TestCase):
    def test_real_historical_field_can_be_checked_without_a_video_claim(self):
        result = check.validate(decode=False, scope='field')
        self.assertEqual(result['scope'], 'field-only')
        self.assertFalse(result['video_validated'])
        self.assertEqual((result['vertices'], result['triangles']), (25232, 50552))

    def test_field_stage_does_not_read_video_and_full_still_rejects_a_stale_video(self):
        original = Path.read_text
        # A rejecting sentinel proves field-only never reads either video input.
        def no_video(path, *args, **kwargs):
            if path.name in ('video-receipt.json', 'media.json'):
                raise AssertionError('Field-only read a video input')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', no_video):
            self.assertFalse(check.validate(decode=False, scope='field')['video_validated'])
        # The ordinary default path still rejects the planted stale video.
        def stale(path, *args, **kwargs):
            if path.name == 'video-receipt.json':
                data = json.loads(original(path, *args, **kwargs))
                data['source_hashes'][check.VIDEO_RENDERER] = '0' * 64
                return json.dumps(data)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', stale), self.assertRaisesRegex(ValueError, 'Stale animation source'):
            check.validate(decode=False)


class ProducerPaths(unittest.TestCase):
    def fixture(self, root):
        from hardware.cad.manufacturing.print_provenance import FORMER_CAD_TESTS, SOURCE_PARENTS, SOURCE_ROOTS
        for directory in SOURCE_ROOTS:
            (root / directory).mkdir(parents=True)
        current = [*FORMER_CAD_TESTS, *SOURCE_PARENTS, 'hardware/cad/legs/input.py',
                   'software/simulation/leg_rig.py', 'software/simulation/leg_control.py',
                   'hardware/exports/leg/rig-results.json', 'hardware/exports/leg/fea/summary.json',
                   'tools/engineering/legs/export-hip-frame-e1.py',
                   'tools/site/source_layout.py', 'tools/site/source-layout.json']
        for name in [*current, 'exports/leg/rig-results.json', 'exports/leg/fea/summary.json']:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('owned input fixture: ' + name)
        return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in current}

    def test_source_preflight_binds_current_paths_not_legacy_decoys(self):
        with tempfile.TemporaryDirectory(prefix='e1-source-paths-') as tmp:
            root = Path(tmp)
            expected = self.fixture(root)
            with patch.object(producer, 'ROOT', root):
                self.assertEqual(producer.source_hashes(), expected)
                path = root / 'hardware/exports/leg/fea/summary.json'
                path.write_text('a changed current report')
                expected[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(producer.source_hashes(), expected)

    def test_missing_current_report_rejects_a_present_legacy_copy(self):
        with tempfile.TemporaryDirectory(prefix='e1-missing-source-') as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / 'hardware/exports/leg/fea/summary.json').unlink()
            with patch.object(producer, 'ROOT', root), self.assertRaises(FileNotFoundError):
                producer.source_hashes()

    def test_field_download_identity_resolves_to_the_current_output(self):
        with tempfile.TemporaryDirectory(prefix='e1-output-path-') as tmp:
            root = Path(tmp)
            fields = root / 'hardware/exports/leg/fea/hip-frame-e1-media/hip_frame-E1.json'
            with patch.object(producer, 'ROOT', root):
                identity = producer.field_identity(fields)
                self.assertEqual(check.source_file(root, identity), fields)
                self.assertTrue(identity.startswith(check.MEDIA))
                with self.assertRaises(ValueError):
                    producer.field_identity(root / 'unrelated/hip_frame-E1.json')


class HipStudyInputs(unittest.TestCase):
    def load_study(self):
        class NoNative(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'cadquery', 'cadagent', 'gmsh', 'OCP'}:
                    raise AssertionError('Native import during input preflight: ' + fullname)
        spec = importlib.util.spec_from_file_location(
            'hip_study_inputs_test', check.ROOT / 'tools/engineering/legs/hip-frame-study.py')
        module = importlib.util.module_from_spec(spec)
        # The source-input path uses no NumPy operations or CAD kernel.
        blocked = {name: None for name in ('cadquery', 'cadagent', 'gmsh', 'OCP')}
        with patch.dict(sys.modules, {'numpy': types.ModuleType('numpy'), **blocked}), patch.object(
                sys, 'meta_path', [NoNative(), *sys.meta_path]), patch.object(
                subprocess, 'Popen', side_effect=AssertionError('Process at import')):
            spec.loader.exec_module(module)
        return module

    def fixture(self, root):
        expected = ProducerPaths().fixture(root)
        expected.pop('tools/engineering/legs/export-hip-frame-e1.py')
        name = 'tools/engineering/legs/hip-frame-study.py'
        path = root / name
        path.write_text('owned study input fixture')
        expected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return expected

    def test_current_inputs_are_bound_and_added_cad_members_are_not_dropped(self):
        study = self.load_study()
        with tempfile.TemporaryDirectory(prefix='hip-study-inputs-') as tmp:
            root = Path(tmp); expected = self.fixture(root)
            with patch.object(study, 'ROOT', root):
                self.assertEqual(study.source_hashes(), expected)
                path = root / 'hardware/exports/leg/fea/summary.json'
                path.write_text('changed current report')
                expected[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
                extra = root / 'hardware/cad/legs/additional.py'
                extra.write_text('new CAD input')
                expected[extra.relative_to(root).as_posix()] = hashlib.sha256(extra.read_bytes()).hexdigest()
                self.assertEqual(study.source_hashes(), expected)

    def test_missing_current_inputs_fail_before_output_or_native_work(self):
        study = self.load_study()
        for missing in ('hardware/exports/leg/rig-results.json', 'hardware/exports/leg/fea/summary.json'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(prefix='hip-study-missing-') as tmp:
                root = Path(tmp); self.fixture(root)
                (root / missing).unlink()
                self.assertTrue((root / missing.removeprefix('hardware/')).is_file())
                out = root / 'candidate-output'
                with patch.object(study, 'ROOT', root), patch.object(
                        study, 'install_recorder', side_effect=AssertionError('Native study reached')), patch.dict(
                        sys.modules, {name: None for name in ('gmsh', 'cadquery', 'cadagent', 'OCP')}):
                    with self.assertRaises(FileNotFoundError):
                        study.run_variant(out, None, ['E1'], 3.0, None, False)
                self.assertFalse(out.exists())

    def test_actual_checkout_has_complete_canonical_source_closure(self):
        study = self.load_study()
        from hardware.cad.manufacturing.print_provenance import source_files
        paths = {path.relative_to(check.ROOT).as_posix() for path in source_files(check.ROOT)}
        paths.update(('software/simulation/leg_rig.py', 'software/simulation/leg_control.py',
                      'hardware/exports/leg/rig-results.json', 'hardware/exports/leg/fea/summary.json',
                      'tools/engineering/legs/hip-frame-study.py',
                      'tools/site/source_layout.py', 'tools/site/source-layout.json'))
        expected = {name: hashlib.sha256((check.ROOT / name).read_bytes()).hexdigest() for name in paths}
        self.assertEqual(study.source_hashes(), expected)

    def test_evaluator_rejects_missing_current_inputs_before_cad_precheck(self):
        study = self.load_study()
        for missing in ('hardware/exports/leg/rig-results.json', 'hardware/exports/leg/fea/summary.json'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(prefix='hip-evaluator-missing-') as tmp:
                root = Path(tmp); self.fixture(root)
                (root / missing).unlink()
                self.assertTrue((root / missing.removeprefix('hardware/')).is_file())
                out = root / 'candidate-output'
                reply = io.StringIO()
                # Exercise the actual evaluator without redirecting the test process's file descriptors.
                with patch.object(study, 'ROOT', root), patch.object(sys, 'stdin', io.StringIO(
                        json.dumps({'id': 'trial', 'params': {'hip': {'root_r': 7.5}}}))), patch.object(
                        os, 'dup', return_value=1), patch.object(os, 'dup2'), patch.object(
                        os, 'fdopen', return_value=reply), patch.dict(sys.modules, {
                        name: None for name in ('gmsh', 'cadquery', 'cadagent', 'OCP')}), patch.object(
                        subprocess, 'Popen', side_effect=AssertionError('Native process during evaluator preflight')):
                    study.evaluator(out, 3.0)
                result = json.loads(reply.getvalue())
                self.assertEqual(result['metrics'], {})
                self.assertEqual(result['checks'][0]['level'], 'fail')
                self.assertIn('FileNotFoundError:', result['checks'][0]['text'])
                self.assertIn(missing, result['checks'][0]['text'])
                self.assertFalse(out.exists())


class StudyMedia(unittest.TestCase):
    def test_leg_rig_companions(self):
        subprocess.run(['node', '--test', 'tests/site/media/test-rig-media.mjs'], cwd=check.ROOT, check=True)

    def test_real_video_and_sources(self):
        self.assertEqual(check.validate()['decoded_frames'], 288)

    def test_frozen_frame_negative_control(self):
        with self.assertRaisesRegex(ValueError, 'Frozen model'):
            check.moving_model(bytes(range(256)) * 20, bytes(range(256)) * 20)

    def test_corruptions(self):
        with tempfile.TemporaryDirectory(prefix='gyropup-study-faults-') as tmp:
            root = Path(tmp)
            paths = [check.SUMMARY, 'exports/leg/fea/media.json', check.VIDEO_RENDERER, check.LOCATION_SOURCE, check.FINER]
            paths += [p.relative_to(check.ROOT).as_posix() for p in check.source_file(check.ROOT, check.MEDIA.rstrip('/')).iterdir() if p.is_file()]
            for path in paths:
                target = check.source_file(root, path); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(check.source_file(check.ROOT, path), target)
            def fault(path, mutate, pattern):
                target = check.source_file(root, path); original = target.read_bytes()
                try:
                    mutate(target)
                    with self.assertRaisesRegex(ValueError, pattern): check.validate(root, decode=False)
                finally: target.write_bytes(original)
            def edit(fn):
                def mutate(path):
                    data = json.loads(path.read_text()); fn(data); path.write_text(json.dumps(data))
                return mutate
            fault(check.SUMMARY, edit(lambda d: d['results'].append({'part':'different','case':'E1'})), 'Stale report binding')
            fault(check.VIDEO_RENDERER, lambda p: p.write_bytes(p.read_bytes()+b'\n# changed\n'), 'Stale animation source')
            fault(check.FINER, edit(lambda d: d['meshes']['3.0']['cases'][0].update(safety_factor=2.5)), 'Stale animation source')
            fault(check.MEDIA+'hip_frame-E1.json', lambda p: p.write_bytes(p.read_bytes()+b'\n'), 'Field bytes changed')
            fault(check.MEDIA+'hip-frame-e1.mp4', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault(check.MEDIA+'hip-frame-e1.webm', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault(check.MEDIA+'hip-frame-e1-poster.png', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1']['recorded'].update(safety_factor=2.5)), 'Media index differs')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(transient_simulation=True)), 'Static evidence mislabeled')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(video='elsewhere.mp4')), 'Media index paths differ')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['timeline'][144].update(load_factor=2)), 'Presentation extrapolates')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['outputs'].pop(check.MEDIA+'hip-frame-e1-poster.png')), 'Incomplete rendered artifacts')
            fault(check.MEDIA+'field-receipt.json', edit(lambda d: d.update(qualified_for_manufacture=True)), 'Static evidence cannot qualify')


if __name__ == '__main__': unittest.main()
