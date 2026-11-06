"""Private manufacturer-input negative controls; no CAD installation needed."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('connector_inputs',Path(__file__).resolve().parent/'check-carrier-connector-inputs.py')
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)


class PrivateInputs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/'references/vendor/example/part.step'
        self.path.parent.mkdir(parents=True);self.path.write_bytes(b'exact private model fixture')
        self.entry={'part':'fixture','private_file':'references/vendor/example/part.step',
                    'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_exact_file_identity(self):
        self.assertEqual(MOD.private_path(self.entry,self.root),self.path)

    def test_missing_exact_model_does_not_fallback(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):MOD.private_path(self.entry,self.root)

    def test_other_variant_rejected_even_at_same_path(self):
        self.path.write_bytes(b'a different connector variant')
        with self.assertRaises(ValueError):MOD.private_path(self.entry,self.root)

    def test_symlink_escape_rejected(self):
        outside=self.root/'outside.step';outside.write_bytes(self.path.read_bytes())
        self.path.unlink();self.path.symlink_to(outside)
        with self.assertRaises(ValueError):MOD.private_path(self.entry,self.root)

    def test_committed_diagnosis_matches_source_and_manifest(self):
        receipt=json.loads((MOD.ROOT/'research/carrier-service-connectors/private-input-diagnosis.json').read_text())
        self.assertTrue(MOD.validate_receipt(receipt))

    def test_changed_deleted_and_new_geometry_inputs_reject(self):
        receipt=json.loads((MOD.ROOT/'research/carrier-service-connectors/private-input-diagnosis.json').read_text())
        for name in set(receipt['inputs']['files'])|set(receipt['context_files']):
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(MOD.ROOT/name,target)
        self.assertTrue(MOD.validate_receipt(receipt,self.root))
        helper=self.root/'cad/print_provenance.py';original=helper.read_bytes()
        helper.write_bytes(original+b'\n# changed imported helper\n')
        with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(receipt,self.root)
        helper.unlink()
        with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(receipt,self.root)
        helper.write_bytes(original)
        (self.root/'cad/new_input.py').write_text('NEW_GEOMETRY=True\n')
        with self.assertRaisesRegex(ValueError,'closure changed'):MOD.validate_receipt(receipt,self.root)


if __name__=='__main__':unittest.main()
