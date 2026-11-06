"""Regress private-input deletion turning manufacturer checks green.

Run with the CAD environment: python tools/test-base-board-manufacturer.py.
Temporary files below are presence sentinels, not vendor CAD. Missing-input tests
must return before any geometry loader, so they need no private manufacturer cache.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cad'))
import turret_base_board as bb
import check_base_board_service as checker


class ManufacturerInputs(unittest.TestCase):
    def test_empty_or_partial_cache_cannot_qualify_either_manufacturer_stage(self):
        for absent in (set(bb.MANUFACTURER_PARTS), *({pn} for pn in bb.MANUFACTURER_PARTS)):
            for group in ('base_board_screws', 'base_carrier_screws'):
                with self.subTest(absent=sorted(absent), group=group), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    for pn in set(bb.MANUFACTURER_PARTS) - absent:
                        path = root / f'references/vendor/mcmaster/{pn}/{pn}.norm.step'
                        path.parent.mkdir(parents=True)
                        path.write_text('presence sentinel: geometry must not be loaded\n')
                    with patch.object(bb, 'ROOT', root), patch.object(bb, 'hardware',
                            side_effect=AssertionError('missing-input preflight must precede geometry')):
                        result = checker.hardware_gate(group, manufacturer=True)
                    self.assertFalse(result['pass'])
                    self.assertEqual(result['counts']['pass'], 0)
                    self.assertEqual(result['counts']['fail'], 1)
                    self.assertEqual(result['findings'][0]['id'], 'manufacturer:inputs')
                    self.assertEqual(set(result['findings'][0]['evidence']['missing']), absent)
                    self.assertIn('manufacturer fastener geometry', result['not_checked'])

    def test_strict_hardware_loader_cannot_use_authored_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bb, 'ROOT', Path(tmp)):
            with self.assertRaisesRegex(FileNotFoundError, 'no silent fallback'):
                bb.hardware(private=True)

    def test_aggregate_requires_every_valid_private_input_even_with_green_geometry(self):
        passing_geometry = [{'id': 'geometry', 'pass': True}]
        complete = {pn: {'available': True, 'valid': True} for pn in bb.MANUFACTURER_PARTS}
        self.assertTrue(checker.model_checks_pass(passing_geometry, complete))
        self.assertFalse(checker.model_checks_pass([], complete))
        self.assertFalse(checker.model_checks_pass(passing_geometry, {}))
        for pn in bb.MANUFACTURER_PARTS:
            for bad in ({}, {'available': False}, {'available': True},
                        {'available': True, 'valid': False}):
                with self.subTest(part=pn, bad=bad):
                    self.assertFalse(checker.model_checks_pass(passing_geometry, {**complete, pn: bad}))
        self.assertFalse(checker.model_checks_pass([{'id': 'geometry', 'pass': False}], complete))

    def test_explicit_public_geometry_check_remains_public(self):
        # Real bounded BREP regression, independent of private inputs on the host.
        with tempfile.TemporaryDirectory() as tmp, patch.object(bb, 'ROOT', Path(tmp)):
            result = checker.hardware_gate('base_board_screws')
        self.assertTrue(result['pass'], result['findings'])
        self.assertEqual(result['counts']['pass'], 28)
        self.assertEqual(result['hardware_geometry'], bb.PUBLIC_NOTE)
        self.assertEqual(result['manufacturer_models'], {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
