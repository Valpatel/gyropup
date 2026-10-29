import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('packaging_check', HERE / 'check.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads((HERE / 'component-inventory.json').read_text())
        self.reference = json.loads((HERE / 'front-reference-contract.json').read_text())

    def test_current_source_inventory_and_reference(self):
        self.assertEqual(C.validate_inventory(self.inventory)['electronic_items'],47)
        self.assertEqual(C.validate_reference(self.reference)['reference_items'],10)

    def test_omitted_and_duplicated_parts_rejected(self):
        for kind in ('drop','duplicate'):
            with self.subTest(kind=kind):
                d=copy.deepcopy(self.inventory)
                if kind=='drop':d['rows'].pop()
                else:d['rows'].append(copy.deepcopy(d['rows'][0]))
                with self.assertRaises(ValueError):C.validate_inventory(d)

    def test_stale_source_or_package_record_rejected(self):
        for kind in ('source','dimension'):
            with self.subTest(kind=kind):
                d=copy.deepcopy(self.inventory)
                if kind=='source':d['source_sha256']['cad/turret_boards.py']='0'*64
                else:d['rows'][0]['maximum_envelope']['maximum_body_mm'][2]=0
                with self.assertRaises(ValueError):C.validate_inventory(d)

    def test_readiness_cannot_be_promoted(self):
        for key in ('frozen','complete_physical_inventory','fit_qualified'):
            d=copy.deepcopy(self.inventory);d[key]=True
            with self.assertRaises(ValueError):C.validate_inventory(d)

    def test_floating_reference_must_not_be_grounded(self):
        for pin in ('6','7'):
            d=copy.deepcopy(self.reference);d['component_pins']['I.U1'][pin]='GND'
            with self.assertRaises(ValueError):C.validate_reference(d)

    def test_reversed_clamp_and_grounded_cout_rejected(self):
        for ref in ('I.D1','I.D2','I.D3','I.D4','I.D5','I.D6'):
            d=copy.deepcopy(self.reference);p=d['component_pins'][ref];p['A'],p['K']=p['K'],p['A']
            with self.subTest(ref=ref),self.assertRaises(ValueError):C.validate_reference(d)
        d=copy.deepcopy(self.reference);d['component_pins']['I.COUT']['2']='GND'
        with self.assertRaises(ValueError):C.validate_reference(d)

    def test_package_variant_and_load_cap_confusion_rejected(self):
        d=copy.deepcopy(self.reference);d['component_pins']['I.U1']['7']='GND'
        with self.assertRaises(ValueError):C.validate_reference(d)
        d=copy.deepcopy(self.reference);d['interfaces']['load_capacitance']['dedicated_front_capacitor']='P.C1'
        with self.assertRaises(ValueError):C.validate_reference(d)

    def test_reference_revision_requires_visual_review(self):
        d=copy.deepcopy(self.reference);d['reference']['pdf_sha256']='0'*64
        with self.assertRaises(ValueError):C.validate_reference(d)


if __name__=='__main__':unittest.main()
