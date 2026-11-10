"""Kernel-free source-footprint controls over the real highlight binding function.

The small synthetic capture isolates the limits dependency. It is not a real
capture, product adoption, or replacement for the full decoded-media guards.
"""
import ast
import hashlib
import importlib.util
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'tools/evidence/media/check-highlights.py'
LIMIT = '/exports/turret/limits.json'


class HighlightLimits(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in
                 ('require', 'required_capture_inputs', 'validate_source_bindings')]
        self.assertEqual(len(nodes), 3)
        def mapping(name):
            return 'hardware/' + name if name.startswith('exports/') else name
        digest = hashlib.sha256(b'fixture limits').hexdigest()
        self.key = mapping(LIMIT.lstrip('/'))
        self.revision = 'a' * 40
        self.scope = {'ROOT': ROOT, 'source_for_public': mapping,
                      'project_path': lambda name: Path(name),
                      'read': lambda path: {'parts': [], 'body': [], 'links': {}},
                      'full_revision': lambda v: isinstance(v, str) and len(v) == 40,
                      'expected_sources': lambda capture, current=None: {self.key},
                      'safe_path': lambda root, name: root / name,
                      'file_sha': lambda path: digest, 'git_sha': lambda *args: digest,
                      'CAPTURE_SCRIPT': self.key, 'CAPTURE_LOCATIONS': (),
                      'WIDTH': 1280, 'HEIGHT': 720, 'FPS': 30}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), self.scope)
        self.actual_required = self.scope['required_capture_inputs']
        # Keep the exact actual source-binding body; isolate one required input
        # so byte and omission faults cannot be masked by unrelated stale media.
        self.scope['required_capture_inputs'] = lambda current=None: {LIMIT}
        self.current = {'source': {'file': 'synthetic-fixture', 'sha256': digest}, 'asset_hashes': {}}
        self.hashes = {self.key: digest}
        self.capture = {'format': 2, 'currentRobotSource': self.current['source'],
                        'sourceRevision': self.revision, 'servedVersion': {'revision': self.revision},
                        'locationContracts': {}, 'recipeSha256': digest,
                        'width': 1280, 'height': 720, 'fps': 30,
                        'inputs': {LIMIT: {'repoSha256': digest, 'servedSha256': digest}}}

    def check(self):
        self.scope['validate_source_bindings'](self.revision, self.hashes, self.capture, self.current)

    def test_actual_required_set_includes_runtime_firing_limits(self):
        self.assertIn(LIMIT, self.actual_required({'asset_hashes': {}}))

    def test_actual_guard_accepts_equal_served_limits(self):
        self.check()

    def test_self_consistent_omission_still_fails(self):
        self.capture['inputs'].pop(LIMIT)
        self.hashes.pop(self.key)
        with self.assertRaisesRegex(ValueError, 'Required renderer or manifest-derived mesh missing'):
            self.check()

    def test_correct_repo_hash_cannot_hide_wrong_served_limits(self):
        self.capture['inputs'][LIMIT]['servedSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Served simulation differs: /exports/turret/limits.json'):
            self.check()


class EncoderPrerequisites(unittest.TestCase):
    def setUp(self):
        source = ROOT / 'tools/evidence/media/highlight_prerequisites.py'
        spec = importlib.util.spec_from_file_location('highlight_prerequisites', source)
        self.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helpers)
        self.check = SimpleNamespace(
            E1='hardware/exports/leg/fea/hip-frame-e1-media/',
            project_path=lambda name: ROOT / name,
            read=lambda path: json.loads(path.read_text()),
            full_revision=lambda value: isinstance(value, str) and len(value) == 40
                and all(c in '0123456789abcdef' for c in value),
            LEG_REVISION='e7b512870a39259a04a4930e2908af84001bc84e',
            MOVIES=['gyropup-highlights.mp4', 'gyropup-highlights.webm'],
            POSTER='gyropup-highlights.webp')

    def test_actual_field_and_renderer_receipt_pins_are_both_required(self):
        revisions = self.helpers.historical_revisions(self.check, '9fc04c3f0af6c92fa4c82cd1f59ed647944f9ba2')
        expected = [json.loads((ROOT / 'hardware/exports/leg/fea/hip-frame-e1-media' / name).read_text())['source_revision']
                    for name in ('field-receipt.json', 'video-receipt.json')]
        # Job254 omitted its then-current renderer revision and failed after encoding.
        for revision in expected:
            self.assertIn(revision, revisions)
        self.assertEqual(len(revisions), len(set(revisions)))

    def test_renderer_revision_is_derived_and_not_a_fixed_list(self):
        self.check.read = lambda path: {'source_revision': 'b' * 40 if path.name == 'video-receipt.json' else 'a' * 40}
        self.assertIn('b' * 40, self.helpers.historical_revisions(self.check, 'c' * 40))
        self.check.read = lambda path: {'source_revision': 'main'}
        with self.assertRaises(ValueError):
            self.helpers.historical_revisions(self.check, 'c' * 40)

    def stage_fixture(self):
        source = 'c' * 40
        old, new = '1' * 64, '2' * 64
        raw = 'software/site/designer/sim.js'
        insert = 'hardware/exports/leg/fea/hip-frame-e1-media/field-receipt.json'
        check = SimpleNamespace(E1='exports/leg/fea/hip-frame-e1-media/',
            source_for_public=lambda name: 'hardware/' + name if name.startswith('exports/') else name,
            full_revision=self.check.full_revision,
            git_sha=lambda revision, name: old)
        declared = {'source': source, 'source_hashes': {raw: old, insert: old}}
        return check, source, declared, {raw: old, insert: new}, raw, insert

    def test_old_stage_and_new_e1_insert_are_distinct_valid_sources(self):
        check, source, declared, current, raw, insert = self.stage_fixture()
        before = json.dumps(declared, sort_keys=True)
        self.assertEqual(self.helpers.validate_recorded_stage(check, declared, current, source), [insert])
        self.assertEqual(json.dumps(declared, sort_keys=True), before)

    def test_resealed_stage_cannot_claim_new_e1_bytes_were_captured(self):
        check, source, declared, current, raw, insert = self.stage_fixture()
        declared['source_hashes'][insert] = current[insert]
        with self.assertRaisesRegex(ValueError, 'Historical stage'):
            self.helpers.validate_recorded_stage(check, declared, current, source)

    def test_non_e1_drift_or_missing_stage_source_cannot_be_waived(self):
        check, source, declared, current, raw, insert = self.stage_fixture()
        current[raw] = '3' * 64
        with self.assertRaisesRegex(ValueError, 'Non-E1'):
            self.helpers.validate_recorded_stage(check, declared, current, source)
        current[raw] = declared['source_hashes'][raw]
        declared['source_hashes'].pop(raw)
        with self.assertRaisesRegex(ValueError, 'Incomplete historical'):
            self.helpers.validate_recorded_stage(check, declared, current, source)

    def test_wrong_stage_revision_cannot_replace_capture_provenance(self):
        check, source, declared, current, raw, insert = self.stage_fixture()
        declared['source'] = 'd' * 40
        with self.assertRaisesRegex(ValueError, 'immutable capture'):
            self.helpers.validate_recorded_stage(check, declared, current, source)

    def test_expected_poster_matches_the_existing_encoder_constant(self):
        tree = ast.parse(SOURCE.read_text())
        poster = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'POSTER' for t in n.targets))
        self.assertEqual(poster, self.check.POSTER)
        names = self.helpers.candidate_names(self.check)
        self.assertEqual(len(names), 6)
        self.assertIn(poster, names)
        self.assertNotIn('poster.webp', names)


CurrentHighlightBindings = runpy.run_path(str(Path(__file__).with_name('test-current-highlight-bindings.py')))['CurrentHighlightBindings']


if __name__ == '__main__':
    unittest.main()
