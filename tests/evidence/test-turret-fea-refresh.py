#!/usr/bin/env python3
"""tools/turret-fea-refresh.py: its verdict and table equal the record's own, and a merge replaces only the named part."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = (Path(__file__).resolve().parents[2])
spec = importlib.util.spec_from_file_location('refresh', (ROOT / 'tools/engineering/turret/turret-fea-refresh.py'))
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)
SUMMARY = json.loads(((ROOT / 'hardware/exports/turret/fea/summary.json')).read_text())


def run_expression(key):
    """The expression cad/turret_studies.py's run() assigns to summary[key], compiled from its source (no import: the
    test needs no CAD kernel). A change to run()'s verdict or table changes what this evaluates."""
    tree = ast.parse(((ROOT / 'hardware/cad/turret/turret_studies.py')).read_text())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    for node in ast.walk(run):
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == 'summary'
                and isinstance(node.targets[0].slice, ast.Constant) and node.targets[0].slice.value == key):
            return compile(ast.Expression(node.value), 'turret_studies.run', 'eval')
    raise LookupError(key)


class Refresh(unittest.TestCase):
    def test_the_verdict_and_table_are_run_s_own(self):
        """verdict() and table() equal run()'s own expressions, taken from cad/turret_studies.py's source, on the
        committed results; and the committed summary holds exactly that."""
        results = SUMMARY['results']
        self.assertEqual(refresh.verdict(results), eval(run_expression('verdict'), {}, {'results': results}))
        self.assertEqual(refresh.table(results), eval(run_expression('table'), {}, {'results': results}))
        self.assertEqual(refresh.verdict(results), SUMMARY['verdict'])
        self.assertEqual(refresh.table(results), SUMMARY['table'])

    def test_a_merge_replaces_only_the_named_part_in_place(self):
        new = {'mesh_mm': SUMMARY['mesh_mm'], 'masses': {'tilt_yoke': 1.0},
               'results': [dict(r, verdict_sf=9.99, ok=True) for r in SUMMARY['results'] if r['part'] == 'tilt_yoke']}
        merged = refresh.merge(copy.deepcopy(SUMMARY), new, ['tilt_yoke'], 'test')
        self.assertEqual([(r['part'], r['case']) for r in merged['results']], [(r['part'], r['case']) for r in SUMMARY['results']])
        for a, b in zip(merged['results'], SUMMARY['results']):
            self.assertEqual(a['verdict_sf'] == 9.99, a['part'] == 'tilt_yoke')
            if a['part'] != 'tilt_yoke':
                self.assertEqual(a, b)
        self.assertEqual(merged['masses'], SUMMARY['masses'])
        self.assertEqual(merged['refreshed'][-1]['parts'], ['tilt_yoke'])

    def test_refreshes_accumulate_and_keep_the_records_order(self):
        """A second refresh of two parts that are not next to each other keeps every result in place and appends to
        `refreshed`, so the first refresh's record survives."""
        parts = ['tilt_yoke', 'cradle']
        new = {'mesh_mm': SUMMARY['mesh_mm'], 'masses': {},
               'results': [dict(r, verdict_sf=9.99) for r in reversed(SUMMARY['results']) if r['part'] in parts]}
        once = refresh.merge(copy.deepcopy(SUMMARY), new, ['tilt_yoke'], 'one', {'commit': 'a'})
        twice = refresh.merge(once, new, parts, 'two', {'commit': 'b'})
        self.assertEqual([(r['part'], r['case']) for r in twice['results']], [(r['part'], r['case']) for r in SUMMARY['results']])
        self.assertEqual([r['why'] for r in twice['refreshed']][-2:], ['one', 'two'])
        self.assertEqual(twice['refreshed'][-1]['commit'], 'b')

    def test_provenance_names_the_imported_toolkit(self):
        """provenance() reads the cad-agent tree it is given (version from its pyproject, its git commit), not the
        venv's metadata: a fake package in a git-less folder gets a source hash and its own version."""
        import tempfile, types
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / 'src' / 'cadagent'
            pkg.mkdir(parents=True)
            (pkg / '__init__.py').write_text('x = 1\n')
            (Path(d) / 'pyproject.toml').write_text('[project]\nname = "cad-agent"\nversion = "9.8.7"\n')
            p = refresh.provenance(types.SimpleNamespace(__file__=str(pkg / '__init__.py')))
        self.assertEqual(p['cad_agent'], '9.8.7')
        self.assertTrue(p['cad_agent_tree'].startswith('sha256:'))
        self.assertEqual(len(p['turret_py_sha256']), 64)

    def test_controls(self):
        """A part with no new results, or a different mesh, is refused."""
        new = {'mesh_mm': SUMMARY['mesh_mm'], 'masses': {}, 'results': []}
        with self.assertRaises(ValueError):
            refresh.merge(copy.deepcopy(SUMMARY), new, ['tilt_yoke'], 'test')
        new = {'mesh_mm': 1.0, 'masses': {}, 'results': [r for r in SUMMARY['results'] if r['part'] == 'tilt_yoke']}
        with self.assertRaises(ValueError):
            refresh.merge(copy.deepcopy(SUMMARY), new, ['tilt_yoke'], 'test')


if __name__ == '__main__':
    unittest.main()
