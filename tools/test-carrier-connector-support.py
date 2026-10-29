"""Kernel-free freshness and negative-evidence guards for the C3 support."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('support_check',Path(__file__).with_name('check-carrier-connector-support.py'))
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
RECEIPT=MOD.ROOT/'research/carrier-service-connectors/support-candidate.json'


class SupportEvidence(unittest.TestCase):
    def setUp(self):self.receipt=json.loads(RECEIPT.read_text())

    def test_current_complete_source_identity(self):
        self.assertTrue(MOD.validate_receipt(self.receipt))

    def test_private_hardware_identity_and_failed_check_reject(self):
        changed=copy.deepcopy(self.receipt);changed['private_hardware_sha256']['91290A113']='0'*64
        with self.assertRaisesRegex(ValueError,'hardware identities'):MOD.validate_receipt(changed)
        changed=copy.deepcopy(self.receipt);changed['checks'][0]['pass']=False
        with self.assertRaisesRegex(ValueError,'failed checks'):MOD.validate_receipt(changed)

    def test_source_closure_change_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            artifacts={'exports/turret/base-board-service/connectors/'+n for n in self.receipt['public_artifact_sha256']}
            for name in set(self.receipt['inputs']['files'])|set(self.receipt['context_files'])|artifacts:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(MOD.ROOT/name,p)
            self.assertTrue(MOD.validate_receipt(self.receipt,root))
            p=root/'cad/turret_base_board.py';p.write_bytes(p.read_bytes()+b'\n# altered underlying mount\n')
            with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(self.receipt,root)

    def test_actual_negative_controls_and_original_mounts_present(self):
        checks={c['id']:c['pass'] for c in self.receipt['checks']}
        for i in range(4):
            for name in ('preserve_original_mount:pcb:','preserve_original_mount:retainer:','original_retainer_driver:'):
                self.assertIs(checks[name+str(i)],True)
        for i in range(2):
            for name in ('nut_seated:','screw_clearance_holes:','nut_inside_sweep:','nut_install_before_PCB:',
                         'negative:nut_removal_with_PCB:','support_driver_bench:','negative:blocked_driver:'):
                self.assertIs(checks[name+str(i)],True)
        for name in ('negative:closed_panel_blocks_housing','negative:blocked_new_hole'):
            self.assertIs(checks[name],True)

    def test_strength_snap_and_thread_limits_cannot_become_readiness(self):
        self.assertIs(self.receipt['readiness'],False)
        self.assertIs(self.receipt['panel_retention_qualified'],False)
        screen=self.receipt['load_screen']
        self.assertEqual(screen['mating_force_n'],96.)
        self.assertIsNone(screen['unmating_force_max_n'])
        self.assertIsNone(screen['allowable_mpa'])
        self.assertGreater(screen['one_post_equivalent_estimate_mpa'],35.)
        for key in ('readiness',):
            changed=copy.deepcopy(self.receipt);changed[key]=True
            with self.assertRaisesRegex(ValueError,'readiness'):MOD.validate_receipt(changed)
        changed=copy.deepcopy(self.receipt);changed['load_screen']['structural_readiness']=True
        with self.assertRaisesRegex(ValueError,'readiness'):MOD.validate_receipt(changed)


if __name__=='__main__':unittest.main()
