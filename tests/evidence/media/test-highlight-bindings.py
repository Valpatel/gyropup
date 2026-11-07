"""Kernel-free source-footprint controls over the real highlight binding function.

The small synthetic capture isolates the limits dependency. It is not a real
capture, product adoption, or replacement for the full decoded-media guards.
"""
import ast
import hashlib
import importlib.util
import json
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
                      'expected_sources': lambda capture: {self.key},
                      'safe_path': lambda root, name: root / name,
                      'file_sha': lambda path: digest, 'git_sha': lambda *args: digest,
                      'CAPTURE_SCRIPT': self.key, 'CAPTURE_LOCATIONS': (),
                      'WIDTH': 1280, 'HEIGHT': 720, 'FPS': 30}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), self.scope)
        self.actual_required = self.scope['required_capture_inputs']
        # Keep the exact actual source-binding body; isolate one required input
        # so byte and omission faults cannot be masked by unrelated stale media.
        self.scope['required_capture_inputs'] = lambda: {LIMIT}
        self.hashes = {self.key: digest}
        self.capture = {'sourceRevision': self.revision, 'servedVersion': {'revision': self.revision},
                        'locationContracts': {}, 'recipeSha256': digest,
                        'width': 1280, 'height': 720, 'fps': 30,
                        'inputs': {LIMIT: {'repoSha256': digest, 'servedSha256': digest}}}

    def check(self):
        self.scope['validate_source_bindings'](self.revision, self.hashes, self.capture)

    def test_actual_required_set_includes_runtime_firing_limits(self):
        self.assertIn(LIMIT, self.actual_required())

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
        self.assertIn('a12cf8e73f337274174c56e14c22832250acf284', revisions)
        # Actual job254 omitted this renderer revision and failed after encoding.
        self.assertIn('99c92d4a511c16d7743e9583b129e2a178651cb8', revisions)
        self.assertEqual(len(revisions), len(set(revisions)))

    def test_renderer_revision_is_derived_and_not_a_fixed_list(self):
        self.check.read = lambda path: {'source_revision': 'b' * 40 if path.name == 'video-receipt.json' else 'a' * 40}
        self.assertIn('b' * 40, self.helpers.historical_revisions(self.check, 'c' * 40))
        self.check.read = lambda path: {'source_revision': 'main'}
        with self.assertRaises(ValueError):
            self.helpers.historical_revisions(self.check, 'c' * 40)

    def test_expected_poster_matches_the_existing_encoder_constant(self):
        tree = ast.parse(SOURCE.read_text())
        poster = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'POSTER' for t in n.targets))
        self.assertEqual(poster, self.check.POSTER)
        names = self.helpers.candidate_names(self.check)
        self.assertEqual(len(names), 6)
        self.assertIn(poster, names)
        self.assertNotIn('poster.webp', names)


if __name__ == '__main__':
    unittest.main()
