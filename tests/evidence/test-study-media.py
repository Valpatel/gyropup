#!/usr/bin/env python3
"""Artifact faults must fail before the static study video is published."""
import importlib.util
import importlib.abc
import hashlib
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
