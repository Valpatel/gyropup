#!/usr/bin/env python3
"""tools/turret-fea-refresh.py: its verdict and table equal the record's own, and a merge replaces only the named part."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh', ROOT / 'tools/turret-fea-refresh.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)
SUMMARY = json.loads((ROOT / 'exports/turret/fea/summary.json').read_text())


class Refresh(unittest.TestCase):
    def test_the_verdict_and_table_are_the_records_own(self):
        """Computed from the committed results, they equal what the committed summary holds: the mirror of
        turret_studies.run() has not drifted from the code that wrote the record."""
        self.assertEqual(refresh.verdict(SUMMARY['results']), SUMMARY['verdict'])
        self.assertEqual(refresh.table(SUMMARY['results']), SUMMARY['table'])

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
        self.assertEqual(merged['refreshed']['parts'], ['tilt_yoke'])

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
