"""Independent arithmetic/claim-boundary checks, not electrical simulation."""
import json
import math
import unittest

from calculate_carrier_protection import INPUT, calculate, energy, power_load, receipt, threshold_corners


class ProtectionChecks(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads(INPUT.read_text())

    def test_energy_and_units(self):
        # 1F charged to2V stores2J; raising2V to4V adds6J, not8J.
        self.assertEqual(energy(1, 0, 2), 2)
        self.assertEqual(energy(1, 2, 4), 6)
        self.assertAlmostEqual(energy(940e-6, 0, 42), .82908)
        self.assertAlmostEqual(energy(100e-6, 12.48, 12.6), .00015048)

    def test_power_balance_and_worse_efficiency(self):
        p = power_load(12, 2.71, 15, .8)
        self.assertAlmostEqual(p['input_a'], 2.71)
        self.assertAlmostEqual(p['input_w'], p['loss_w']+p['output_w'])
        self.assertGreater(p['loss_w'], power_load(12, 2.71, 15, .9)['loss_w'])

    def test_ideal_and_monotone_threshold_corners(self):
        self.assertEqual(threshold_corners(990, 10, 0, [.5], 0), [50, 50])
        lo, hi = threshold_corners(990, 10, .01, [.49, .51], 1e-8)
        self.assertAlmostEqual(lo, .49*(1+980.1/10.1)-1e-8*980.1)
        self.assertAlmostEqual(hi, .51*(1+999.9/9.9)+1e-8*999.9)
        self.assertLess(lo, 50)
        self.assertGreater(hi, 50)

    def test_static_headroom_does_not_become_transient_proof(self):
        r = calculate(self.inputs)
        self.assertLess(r['converter_screening']['existing']['input_margin_to_d14_max_breakdown_v'], 0)
        self.assertLess(r['converter_screening']['same_board_outline_candidate']['input_margin_to_d14_specified_clamp_v'], 0)
        self.assertGreater(r['converter_screening']['wide_candidate']['input_margin_to_d14_specified_clamp_v'], 0)
        for c in r['converter_screening'].values():
            self.assertIsNone(c['guaranteed_dynamic_input_or_output_peak_v'])
        low, high = r['active_threshold_examples']
        self.assertFalse(low['guaranteed_static_recovery_above_42v'])
        self.assertTrue(high['guaranteed_static_recovery_above_42v'])
        self.assertLess(high['remaining_to_50v_before_gate_delay_v'], 0)
        self.assertIsNone(high['guaranteed_transient_output_peak_v'])

    def test_unknowns_and_typical_thermal_are_retained(self):
        r = calculate(self.inputs)
        self.assertEqual(r['unknowns'], self.inputs['unknowns'])
        self.assertGreater(len(r['unknowns']), 0)
        self.assertTrue(all(not x['qualified_enclosure_temperature'] for x in r['thermal_sensitivity']))
        self.assertGreater(r['thermal_sensitivity'][0]['estimated_case_c_at_assumed_ambient'], 105)

    def test_invalid_physics_inputs_rejected(self):
        for eta in [0, -.1, 1.01, math.nan]:
            with self.assertRaises(ValueError):
                power_load(12, 2, 42, eta)
        for args in [(0, 0, 2), (1, 4, 2), (1, 0, math.inf)]:
            with self.assertRaises(ValueError):
                energy(*args)

    def test_receipt_matches_frozen_source(self):
        result = receipt()
        self.assertEqual(len(result['inputs_sha256']), 64)
        self.assertEqual(result['source_commit'], self.inputs['source_commit'])


if __name__ == '__main__':
    unittest.main()
