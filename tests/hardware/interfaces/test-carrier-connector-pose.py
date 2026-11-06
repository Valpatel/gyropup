"""Kernel-free guards for the explicitly limited external C3 candidate."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('connector_pose',Path(__file__).with_name('check-carrier-connector-pose.py'))
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
RECEIPT=MOD.ROOT/'research/carrier-service-connectors/external-pose.json'


class CandidateEvidence(unittest.TestCase):
    def setUp(self):self.receipt=json.loads(RECEIPT.read_text())

    def test_current_source_identity(self):
        self.assertTrue(MOD.validate_receipt(self.receipt))

    def test_explicit_external_positives_and_collision_controls(self):
        checks={r['id']:r['external_clear'] for r in self.receipt['external_checks']}
        self.assertEqual(checks,{
            'module_housing_installed':True,
            'fixed_housing_swept_box:mated->unplugged':True,
            'fixed_housing_swept_box:unplugged->outboard_before_park':True,
            'fixed_housing_swept_box:outboard_before_park->parked':True,
            'latch_finger_RESERVATION':True,
            'NEGATIVE:lowered_housing':False,'NEGATIVE:bad_park':False})
        self.assertEqual(self.receipt['negative_controls'],{
            'lower_housing_intersects_installed_bumper':True,
            'parked_housing_inside_carrier_is_rejected':True})
        self.assertIs(self.receipt['readiness'],False)

    def test_helper_change_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in set(self.receipt['inputs']['files'])|set(self.receipt['context_files']):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(MOD.ROOT/name,p)
            self.assertTrue(MOD.validate_receipt(self.receipt,root))
            p=root/'cad/gmi.py';p.write_bytes(p.read_bytes()+b'\n# changed neighbour geometry dependency\n')
            with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(self.receipt,root)

    def test_false_readiness_and_private_substitution_reject(self):
        changed=copy.deepcopy(self.receipt);changed['readiness']=True
        with self.assertRaises(ValueError):MOD.validate_receipt(changed)
        changed=copy.deepcopy(self.receipt);changed['private_inputs']['43025-1200']='0'*64
        with self.assertRaises(ValueError):MOD.validate_receipt(changed)


if __name__=='__main__':unittest.main()
