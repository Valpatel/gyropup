"""Kernel-free interface guards; the separate bounded checker supplies BREP evidence."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cad'))
import turret_carrier_interfaces as ci


class CarrierInterfaces(unittest.TestCase):
    def test_unknown_qualification_cannot_become_ready_from_green_space_checks(self):
        self.assertFalse(ci.readiness({'geometry':True}))
        all_evidence={k:True for k in ('geometry','connector_models','latch_and_retention','bend_radius',
                     'solder_and_insulation','c3_and_servo_disconnect','source_protection','physical_fit')}
        self.assertTrue(ci.readiness(all_evidence))
        for key in all_evidence:
            for absent in (False,None,'true',1):
                with self.subTest(key=key,value=absent):
                    self.assertFalse(ci.readiness({**all_evidence,key:absent}))

    def test_fixed_tails_can_release_but_do_not_allow_connected_module_withdrawal(self):
        for kind in ('power','signal'):
            normal=ci.tail_requirements(kind,'fixed')
            self.assertTrue(normal['length_lower_bound_pass'])
            self.assertEqual(len(normal['samples']),33)
            self.assertIsNone(normal['bend_radius_mm'])
            self.assertFalse(normal['route_qualified'])
            self.assertFalse(ci.tail_requirements(kind,'fixed',retained_mm=10.)['length_lower_bound_pass'])
            self.assertFalse(ci.tail_requirements(kind,'fixed',module_travel=45.)['length_lower_bound_pass'])

    def test_module_tail_and_anchor_translate_together(self):
        for kind in ('power','signal'):
            seated=ci.tail_requirements(kind,'module')
            removed=ci.tail_requirements(kind,'module',module_travel=45.)
            self.assertAlmostEqual(seated['required_geometric_lower_bound_mm'],removed['required_geometric_lower_bound_mm'])

    def test_receipt_is_current_and_does_not_erase_unqualified_coverage(self):
        receipt=json.loads((ROOT/'exports/turret/base-board-service/interfaces/interfaces.json').read_text())
        for path,digest in receipt['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
        for path,digest in receipt['artifact_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/'exports/turret/base-board-service/interfaces'/path).read_bytes()).hexdigest(),digest,path)
        self.assertTrue(receipt['bounded_reservation_checks_pass'])
        self.assertFalse(receipt['readiness'])
        self.assertFalse(receipt['physical_fit_verified'])
        ids={c['id'] for c in receipt['checks'] if c['pass']}
        self.assertIn('negative:closed_window',ids)
        self.assertIn('negative:bumper_blocks_power_grip',ids)
        self.assertIn('negative:blocked_latch',ids)
        for kind in ('power','signal'):
            self.assertIn('negative:withdraw_still_mated:'+kind,ids)


if __name__=='__main__':
    unittest.main(verbosity=2)
