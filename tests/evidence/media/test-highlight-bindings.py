"""Kernel-free source-footprint controls over the real highlight binding function.

The small synthetic capture isolates the limits dependency. It is not a real
capture, product adoption, or replacement for the full decoded-media guards.
"""
import ast
import hashlib
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
