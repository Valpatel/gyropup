"""Kernel-free freshness and negative-evidence guards for the C3 support."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('support_check',Path(__file__).resolve().parents[3] / 'tools/evidence/interfaces/check-carrier-connector-support.py')
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
from tools.evidence.manufacturing.retained_study_inputs import study_inputs
RECEIPT=MOD.ROOT/'docs/research/carrier-service-connectors/support-candidate.json'


class SupportEvidence(unittest.TestCase):
    def setUp(self):
        self.receipt=json.loads(RECEIPT.read_text())
        self.source=self.enterContext(study_inputs('connector-support'))

    def test_dated_source_identity_and_current_staleness(self):
        with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(self.receipt)
        self.assertTrue(MOD.validate_receipt(self.receipt,self.source))

    def test_private_hardware_identity_and_failed_check_reject(self):
        changed=copy.deepcopy(self.receipt);changed['private_hardware_sha256']['91290A113']='0'*64
        with self.assertRaisesRegex(ValueError,'hardware identities'):MOD.validate_receipt(changed,self.source)
        changed=copy.deepcopy(self.receipt);changed['checks'][0]['pass']=False
        with self.assertRaisesRegex(ValueError,'failed checks'):MOD.validate_receipt(changed,self.source)

    def test_deleted_clearance_false_summary_and_duplicate_checks_reject(self):
        for target in ('support:installed_neighbours','carrier:nonmating_neighbours',
                       'carrier_added_material:all_neighbours'):
            changed=copy.deepcopy(self.receipt)
            changed['checks']=[c for c in changed['checks'] if c['id']!=target]
            with self.assertRaisesRegex(ValueError,'check coverage'):MOD.validate_receipt(changed,self.source)
        changed=copy.deepcopy(self.receipt);changed['checks'].append(copy.deepcopy(changed['checks'][0]))
        with self.assertRaisesRegex(ValueError,'check coverage'):MOD.validate_receipt(changed,self.source)
        changed=copy.deepcopy(self.receipt);changed['bounded_geometry_checks_pass']=False
        with self.assertRaisesRegex(ValueError,'failed checks'):MOD.validate_receipt(changed,self.source)

    def test_source_closure_change_rejects(self):
        self.assertTrue(MOD.validate_receipt(self.receipt,self.source))
        p=self.source/'hardware/cad/turret/turret_base_board.py';p.write_bytes(p.read_bytes()+b'\n# altered underlying mount\n')
        with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(self.receipt,self.source)

    def test_missing_partial_or_changed_artifact_binding_rejects(self):
        for replacement in (None,{}, {'C3-support-layout.step':self.receipt['public_artifact_sha256']['C3-support-layout.step']}):
            changed=copy.deepcopy(self.receipt)
            if replacement is None:del changed['public_artifact_sha256']
            else:changed['public_artifact_sha256']=replacement
            with self.assertRaisesRegex(ValueError,'artifact binding'):MOD.validate_receipt(changed,self.source)
        self.assertTrue(MOD.validate_receipt(self.receipt,self.source))
        p=self.source/'hardware/exports/turret/base-board-service/connectors/C3-support-candidate.step'
        p.write_bytes(p.read_bytes()+b'\nchanged export\n')
        with self.assertRaisesRegex(ValueError,'public artifact changed'):MOD.validate_receipt(self.receipt,self.source)

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
        for name in ('C3_service:mated->unplugged','C3_service:unplugged->outboard_before_park',
                     'C3_service:outboard_before_park->parked','negative:C3_unplug_blocker',
                     'carrier_added_material:all_neighbours','carrier:nonmating_neighbours'):
            self.assertIs(checks[name],True)
        mates=self.receipt['existing_unqualified_mates']
        self.assertEqual(set(mates),{f'base_board_inserts#{i}_AUTHORED' for i in range(4)})
        for row in mates.values():
            self.assertEqual(row['baseline']['state'],'overlapping')
            self.assertEqual(row['candidate']['state'],'overlapping')
            self.assertIs(row['physical_fit_verified'],False)

    def test_strength_snap_and_thread_limits_cannot_become_readiness(self):
        self.assertIs(self.receipt['readiness'],False)
        self.assertIs(self.receipt['panel_retention_qualified'],False)
        screen=self.receipt['load_screen']
        self.assertEqual(screen['mating_force_n'],96.)
        self.assertEqual(screen['force_direction'],[0.,-1.,0.])
        self.assertEqual(screen['mount_moments_nmm'],{'about_X':2304.,'about_Z':-2688.})
        self.assertIsNone(screen['unmating_force_max_n'])
        self.assertIsNone(screen['allowable_mpa'])
        self.assertGreater(screen['one_post_equivalent_estimate_mpa'],35.)
        for key in ('readiness',):
            changed=copy.deepcopy(self.receipt);changed[key]=True
            with self.assertRaisesRegex(ValueError,'readiness'):MOD.validate_receipt(changed,self.source)
        changed=copy.deepcopy(self.receipt);changed['load_screen']['structural_readiness']=True
        with self.assertRaisesRegex(ValueError,'readiness'):MOD.validate_receipt(changed,self.source)


if __name__=='__main__':unittest.main()
