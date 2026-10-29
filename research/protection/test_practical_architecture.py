"""Regression gates for the bounded architecture comparison, not physical tests."""
import copy
import json
import unittest
import calculate_practical_architecture as C


class ArchitectureComparison(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(C.INPUT.read_text())

    def test_baseline_and_recommendation_remain_conditional(self):
        r = C.compare(self.data)
        self.assertAlmostEqual(r['baseline_candidate_B']['15V_enable_margin_V'], .0690196, places=6)
        self.assertAlmostEqual(r['baseline_candidate_B']['series_loss_W'], 5.980131, places=5)
        p = r['enhanced_low_loss_direction']
        self.assertGreater(p['15V_enable_margin_after_gate_enhancement_V'], 1.3)
        self.assertLess(p['front_loss_screen_W'], 1)
        self.assertTrue(p['6cm2_copper_condition_satisfies_scenario'])
        self.assertFalse(p['minimal_footprint_condition_satisfies_scenario'])
        self.assertIsNone(p['startup_before_gate_enhancement'])
        self.assertIsNone(p['actual_charged_reverse_pin_peaks'])
        self.assertTrue(all(v is False for v in r['qualifications'].values()))

    def test_bare_controller_differential_negative_controls(self):
        r = C.compare(self.data)
        self.assertEqual(r['raw_charged_reverse_stress_V'], 97)
        self.assertEqual(r['bare_controller_rejection'], {
            'LTC4359_raw_IN_absolute_margin_V': -2,
            'LM7480_differential_margin_V': -12,
            'LM74910H_differential_margin_V': -9})

    def test_large_module_does_not_inherit_fit_or_heat_pass(self):
        r = C.compare(self.data)['larger_converter_direction']
        self.assertAlmostEqual(r['output_corner_V'], 12.3)
        self.assertAlmostEqual(r['output_screen_W'], 39.975)
        self.assertGreater(r['body_plan_area_ratio_to_legacy_board'], 1)
        self.assertTrue(all(not t['stock_thermal_condition_satisfies_scenario'] for t in r['thermal_scenarios']))
        self.assertGreater(min(r['OVP_range_V']), 12.6)
        self.assertIsNone(r['reverse_input_protection'])

    def test_old_16V_variant_cannot_borrow_new_specification(self):
        self.data['manufacturer_values']['RP60Q-11012SRUWB/P']['input_min_V'] = 16
        with self.assertRaises(ValueError): C.compare(self.data)

    def test_resistance_regression_can_lose_both_margins(self):
        self.data['design_assumptions']['front_FET_hot_ohm'] = .4
        p = C.compare(self.data)['enhanced_low_loss_direction']
        self.assertLess(p['15V_enable_margin_after_gate_enhancement_V'], 0)
        self.assertFalse(p['6cm2_copper_condition_satisfies_scenario'])

    def test_invalid_and_qualification_inputs_fail_closed(self):
        for bad in (0, -1, float('nan'), float('inf'), True):
            d = copy.deepcopy(self.data)
            d['design_assumptions']['front_FET_hot_ohm'] = bad
            with self.assertRaises(ValueError): C.compare(d)
        self.data['qualifications']['thermal'] = True
        with self.assertRaises(ValueError): C.compare(self.data)

    def test_missing_qualification_cannot_hide_a_gap(self):
        del self.data['qualifications']['startup_gate_bodydiode']
        with self.assertRaises(ValueError): C.compare(self.data)

    def test_bound_receipt_matches_current_sources(self):
        self.assertEqual(json.loads(C.OUTPUT.read_text()), C.artifact())


if __name__ == '__main__':
    unittest.main()
