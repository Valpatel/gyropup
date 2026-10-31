#!/usr/bin/env python3
"""Kernel-free acquisition and fail-closed survey controls; fixtures are not CAD."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ordered_motor', ROOT / 'tools/ordered-turret-motor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def listing(asin=m.ASIN):
    # Deliberately synthetic values: tests parser identity/membership, not specs.
    rows = ''.join(f'<tr><th>{label}</th><td>synthetic {key}</td></tr>' for key, label in m.CLAIMS.items())
    return (f'<input id="ASIN" value="{asin}"><span id="productTitle">PRO3115-900KV</span>'
            '<a id="bylineInfo">Brand: Deeahdah</a><table>' + rows + '</table>')


def synthetic_survey(base):
    """A complete schema fixture, never represented as an observed motor."""
    evidence = base / 'synthetic-evidence.txt'
    evidence.write_text('UNIT TEST SENTINEL — NOT A SAMPLE OBSERVATION OR CAD EVIDENCE\n')
    ref = [{'path': evidence.name, 'sha256': m.sha(evidence)}]
    data = m.template()
    data.update(sample_id='SYNTHETIC ONLY', observed_date='2026-10-30', operator='test fixture',
                identity_evidence=copy.deepcopy(ref))
    values = {key: (lo + hi) / 2 for key, (lo, hi) in m.NUMERIC.items()}
    values.update(mount_face_to_bell_top_mm=30, mount_face_to_shaft_tip_mm=50,
                  shaft_thread_usable_length_mm=10, shaft_thread_pitch_mm=.8,
                  mount_thread_pitch_mm=.5, shaft_thread_hand='right', mount_thread_hand='right',
                  mount_hole_centres_xy_mm=[[-9, -9], [-9, 9], [9, -9], [9, 9]], lead_exit_xyz_mm=[15, 0, 3])
    for key, row in data['measurements'].items():
        row.update(value=values[key], method='synthetic observation', instrument='synthetic instrument',
                   uncertainty=None if key in m.ENUMS else .05, evidence=copy.deepcopy(ref))
    return data


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.html = self.base / 'page.html'

    def tearDown(self):
        self.tmp.cleanup()

    def acquire(self, content):
        self.html.write_text(content)
        return m.acquire(self.html, '2026-10-30')

    def test_acquisition_keeps_claims_unmeasured_and_binds_input(self):
        out = self.acquire(listing())
        self.assertEqual(out['source_html_sha256'], m.sha(self.html))
        self.assertEqual(set(out['claims']), set(m.CLAIMS))
        self.assertTrue(all(r['status'] == 'seller_claim_unmeasured' for r in out['claims'].values()))

    def test_wrong_asin_title_brand_or_multiple_selected_asins_rejected(self):
        bad = [listing('WRONG'), listing().replace('PRO3115-900KV', 'OTHER3115-900KV'),
               listing().replace('Deeahdah', 'DifferentBrand'),
               listing() + '<input id="ASIN" value="ANOTHER">']
        for content in bad:
            with self.subTest(content=content[:40]), self.assertRaises(ValueError):
                self.acquire(content)

    def test_missing_and_conflicting_rows_rejected(self):
        for content in [listing().replace('Bolt Pattern', 'Unknown Label'),
                        listing() + '<tr><th>Bolt Pattern</th><td>different</td></tr>']:
            with self.assertRaises(ValueError):
                self.acquire(content)

    def test_exact_duplicate_claim_is_not_a_conflict(self):
        out = self.acquire(listing() + '<tr><th>Bolt Pattern</th><td>synthetic mount_pattern</td></tr>')
        self.assertEqual(out['claims']['mount_pattern']['value'], 'synthetic mount_pattern')


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.data = synthetic_survey(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, data=None):
        return m.survey_verdict(data if data is not None else self.data, self.base)

    def test_complete_synthetic_survey_only_passes_completeness(self):
        out = self.report()
        self.assertTrue(out['survey_complete'])
        self.assertTrue(out['pass'])
        for key in m.BLOCKED_FLAGS:
            self.assertIs(out[key], False)
        self.assertEqual(set(out['source_sha256']), set(m.SOURCES))
        self.assertTrue(all(m.sha(ROOT / p) == h for p, h in out['source_sha256'].items()))

    def test_committed_template_is_unknown_and_fails(self):
        data = json.loads((ROOT / 'research/ordered-turret-motor/measurements.template.json').read_text())
        self.assertEqual(data, m.template())
        self.assertTrue(all(row['value'] is None for row in data['measurements'].values()))
        out = self.report(data)
        self.assertFalse(out['pass'])
        self.assertEqual(out['counts']['fail'], len(m.FIELDS) + 2)

    def test_every_required_field_missing_or_omitted_fails(self):
        for key in m.FIELDS:
            for omit in (False, True):
                data = copy.deepcopy(self.data)
                if omit:
                    del data['measurements'][key]
                else:
                    data['measurements'][key]['value'] = None
                with self.subTest(key=key, omit=omit):
                    self.assertFalse(self.report(data)['pass'])

    def test_nonfinite_bool_wrong_units_and_nonpositive_dimensions_fail(self):
        for bad in (math.nan, math.inf, -math.inf, True, '5 mm', 0, -5, 5000):
            data = copy.deepcopy(self.data)
            data['measurements']['shaft_thread_major_diameter_mm']['value'] = bad
            out = self.report(data)
            self.assertFalse(out['pass'])
            json.dumps(out, allow_nan=False)

    def test_every_observation_requires_evidence_method_instrument_and_uncertainty(self):
        for field in m.FIELDS:
            for key, value in [('evidence', []), ('method', ''), ('instrument', None), ('uncertainty', 0)]:
                data = copy.deepcopy(self.data)
                data['measurements'][field][key] = value
                with self.subTest(field=field, key=key):
                    self.assertFalse(self.report(data)['pass'])

    def test_wrong_identity_and_future_date_fail(self):
        for key, value in [('asin', 'OTHER'), ('part', 'Other 3115'), ('sample_id', ''),
                           ('observed_date', '2999-01-01'), ('datum', 'metres'), ('identity_evidence', [])]:
            data = copy.deepcopy(self.data)
            data[key] = value
            self.assertFalse(self.report(data)['pass'])

    def test_declared_fit_or_removed_qualification_flag_fails(self):
        for key in m.BLOCKED_FLAGS:
            data = copy.deepcopy(self.data)
            data[key] = True
            self.assertFalse(self.report(data)['pass'])
            del data[key]
            self.assertFalse(self.report(data)['pass'])

    def test_changed_empty_missing_or_outside_evidence_fails(self):
        file = self.base / 'synthetic-evidence.txt'
        original = file.read_bytes()
        for mutation in (b'changed', b''):
            file.write_bytes(mutation)
            self.assertFalse(self.report()['pass'])
        file.unlink()
        self.assertFalse(self.report()['pass'])
        file.write_bytes(original)
        for path in ('../outside.txt', str(file.resolve())):
            data = copy.deepcopy(self.data)
            data['identity_evidence'][0]['path'] = path
            self.assertFalse(self.report(data)['pass'])
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / 'external.txt'
            outside.write_bytes(original)
            (self.base / 'link.txt').symlink_to(outside)
            data = copy.deepcopy(self.data)
            data['identity_evidence'][0]['path'] = 'link.txt'
            self.assertFalse(self.report(data)['pass'])

    def test_inconsistent_datums_and_absence_pairs_fail(self):
        for key, value in [('mount_face_to_shaft_tip_mm', 20), ('shaft_thread_usable_length_mm', 40),
                           ('shaft_shoulder_length_mm', 0), ('rear_protrusion_mm', 0),
                           ('shaft_thread_hand', 'M5'), ('mount_hole_centres_xy_mm', [[9, 9]] * 4)]:
            data = copy.deepcopy(self.data)
            data['measurements'][key]['value'] = value
            self.assertFalse(self.report(data)['pass'])


class GaugeReceiptTests(unittest.TestCase):
    def test_current_export_identity_and_real_geometry_results(self):
        folder = ROOT / 'exports/turret/ordered-motor-fit'
        data = json.loads((folder / 'checks.json').read_text())
        self.assertEqual(data['schema'], 'cadagent.gate/1')
        self.assertEqual(data['gate'], 'ordered-motor-shaft-survey-gauge')
        self.assertIs(data['pass'], True)
        self.assertEqual(data['counts'], {'pass': 12, 'warn': 0, 'fail': 0})
        self.assertEqual(set(data['source_sha256']), {'research/ordered-turret-motor/gauge.py',
                         'research/ordered-turret-motor/seller-claims.json'})
        self.assertEqual(set(data['artifact_sha256']), {'shaft-clearance-survey.step', 'shaft-clearance-survey.stl'})
        for path, digest in data['source_sha256'].items():
            self.assertEqual(m.sha(ROOT / path), digest, path)
        for path, digest in data['artifact_sha256'].items():
            self.assertEqual(m.sha(folder / path), digest, path)
        self.assertEqual(len(data['slots']), 8)
        for i, row in enumerate(data['slots']):
            self.assertIs(row['pass'], True)
            self.assertEqual(row['cylinder_diameters_mm'], [round(4.8 + i / 10, 1)])
            self.assertIs(row['open_through_plate_and_edge'], True)
            self.assertIs(row['lands_present'], True)
        self.assertEqual(data['negative_controls'], {'wrong_first_slot_width_caught': True,
                                                    'blocked_mouths_caught': True})
        self.assertEqual(data['font']['sha256'], '5c1247acef7f2b8522a31742c76d6adcb5569bacc0be7ceaa4dc39dd252ce895')
        self.assertEqual(data['font']['explicit_font_path'], '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        self.assertEqual(data['font']['text_size_mm'], 5.0)
        self.assertEqual({r['id']: r['text'] for r in data['labels']},
                         {f'slot:{i}': f'{4.8+i/10:.1f}' for i in range(8)} | {'survey-only': 'SURVEY ONLY'})
        self.assertTrue(all(r['glyph_bounds_mm'] for r in data['labels']))
        for key in ('physical_fit_verified', 'slicer_run', 'print_release',
                    'mount_design_released', 'hub_design_released', 'powered_operation_qualified'):
            self.assertIs(data[key], False)


class SheetTests(unittest.TestCase):
    def test_committed_svg_reproduces_and_physical_units_are_one_to_one(self):
        sheet = (ROOT / 'research/ordered-turret-motor/mount-pattern-survey.svg').read_text()
        self.assertEqual(sheet, m.survey_sheet())
        svg = ET.fromstring(sheet)
        self.assertEqual(svg.attrib['width'], '210mm')
        self.assertEqual(svg.attrib['height'], '297mm')
        self.assertEqual(svg.attrib['viewBox'], '0 0 210 297')
        self.assertIn('M20 255h100', sheet)
        self.assertIn('M180 170v100', sheet)
        self.assertIn('NOT A DRILL TEMPLATE', sheet)
        self.assertEqual(sheet.count('hypothesis'), 2)


if __name__ == '__main__':
    unittest.main()
