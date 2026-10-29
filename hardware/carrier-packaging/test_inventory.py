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

    def test_terminal_contract_and_forbidden_bus_substitution(self):
        d=json.loads((HERE / 'terminal-contract.json').read_text())
        self.assertEqual(C.validate_terminals(d)['external_positions'],21)
        c3=next(x for x in d['existing_interfaces'] if x['id']=='C3.module')
        c3['pins']['11']='PAN_INPUT'
        with self.assertRaises(ValueError):C.validate_terminals(d)

    def test_ring_contact_cannot_inherit_module_wire(self):
        d=json.loads((HERE / 'terminal-contract.json').read_text())
        fixed=next(x for x in d['existing_interfaces'] if x['id']=='C3.fixed')
        fixed['wire_awg']=24
        with self.assertRaises(ValueError):C.validate_terminals(d)

    def test_unknown_terminations_remain_unallocated(self):
        d=json.loads((HERE / 'terminal-contract.json').read_text())
        d['all_terminals_allocated']=True
        with self.assertRaises(ValueError):C.validate_terminals(d)

    def test_shunt_ends_cannot_disappear_from_junction_inventory(self):
        d=json.loads((HERE / 'terminal-contract.json').read_text())
        next(x for x in d['junctions'] if x['id']=='J_BUS')['logical_members'].remove('H.D14.K')
        with self.assertRaises(ValueError):C.validate_terminals(d)

    def test_every_interface_identity_pin_and_net_is_required(self):
        original=json.loads((HERE / 'terminal-contract.json').read_text())
        for index,row in enumerate(original['existing_interfaces']):
            for mode in ('delete','duplicate','rename'):
                d=copy.deepcopy(original)
                if mode=='delete': d['existing_interfaces'].pop(index)
                elif mode=='duplicate': d['existing_interfaces'].append(copy.deepcopy(row))
                else: d['existing_interfaces'][index]['id'] += '.unexpected'
                with self.subTest(interface=row['id'],mode=mode), self.assertRaises(ValueError):
                    C.validate_terminals(d)
            for pin in row.get('pins',{}):
                for mode in ('delete','wrong_net'):
                    d=copy.deepcopy(original); pins=d['existing_interfaces'][index]['pins']
                    if mode=='delete': pins.pop(pin)
                    else: pins[pin]='BUS_HEAD_FUSED' if pins[pin]!='BUS_HEAD_FUSED' else 'PAN_INPUT'
                    with self.subTest(interface=row['id'],pin=pin,mode=mode), self.assertRaises(ValueError):
                        C.validate_terminals(d)
        # A duplicate must fail before conversion to a dictionary could hide it.
        d=copy.deepcopy(original)
        d['existing_interfaces'].append(copy.deepcopy(next(x for x in d['existing_interfaces'] if x['id']=='C3.module')))
        with self.assertRaisesRegex(ValueError,'duplicate interface'): C.validate_terminals(d)

    def test_every_bypass_and_junction_endpoint_is_required(self):
        original=json.loads((HERE / 'terminal-contract.json').read_text())
        for index,row in enumerate(original['continuous_bypasses']):
            for mode in ('delete','duplicate','missing_endpoint','wrong_net'):
                d=copy.deepcopy(original)
                if mode=='delete': d['continuous_bypasses'].pop(index)
                elif mode=='duplicate': d['continuous_bypasses'].append(copy.deepcopy(row))
                elif mode=='missing_endpoint': d['continuous_bypasses'][index][0]='MISSING.1'
                else: d['continuous_bypasses'][index][2]='GND'
                with self.subTest(bypass=row,mode=mode), self.assertRaises(ValueError): C.validate_terminals(d)
        for index,row in enumerate(original['junctions']):
            for mode in ('delete','duplicate','wrong_net'):
                d=copy.deepcopy(original)
                if mode=='delete': d['junctions'].pop(index)
                elif mode=='duplicate': d['junctions'].append(copy.deepcopy(row))
                else: d['junctions'][index]['net']='UNEXPECTED'
                with self.subTest(junction=row['id'],mode=mode), self.assertRaises(ValueError): C.validate_terminals(d)
            for member in row['logical_members']:
                for mode in ('delete','duplicate','missing_endpoint'):
                    d=copy.deepcopy(original); members=d['junctions'][index]['logical_members']
                    if mode=='delete': members.remove(member)
                    elif mode=='duplicate': members.append(member)
                    else: members[members.index(member)]='MISSING.1'
                    with self.subTest(junction=row['id'],member=member,mode=mode), self.assertRaises(ValueError):
                        C.validate_terminals(d)

    def test_legacy_and_protection_pin_membership_is_exact(self):
        original=json.loads((HERE / 'terminal-contract.json').read_text())
        for ref,pins in original['legacy_control_pins'].items():
            for pin in pins:
                for mode in ('delete','wrong_net'):
                    d=copy.deepcopy(original)
                    if mode=='delete': d['legacy_control_pins'][ref].pop(pin)
                    else: d['legacy_control_pins'][ref][pin]='UNEXPECTED'
                    with self.subTest(ref=ref,pin=pin,mode=mode), self.assertRaises(ValueError): C.validate_terminals(d)
        for index,row in enumerate(original['adjacent_protection']):
            d=copy.deepcopy(original);d['adjacent_protection'].append(copy.deepcopy(row))
            with self.subTest(ref=row['id'],mode='duplicate'), self.assertRaises(ValueError): C.validate_terminals(d)
            d=copy.deepcopy(original);d['adjacent_protection'].pop(index)
            with self.subTest(ref=row['id'],mode='delete'), self.assertRaises(ValueError): C.validate_terminals(d)
            for pin in row.get('pins',{}):
                d=copy.deepcopy(original);d['adjacent_protection'][index]['pins'][pin]='UNEXPECTED'
                with self.subTest(ref=row['id'],pin=pin), self.assertRaises(ValueError): C.validate_terminals(d)
        for port in original['protection_external_terminal_proposal']['ports']:
            d=copy.deepcopy(original);d['protection_external_terminal_proposal']['ports'].remove(port)
            with self.subTest(port=port,mode='delete'), self.assertRaises(ValueError): C.validate_terminals(d)
            d=copy.deepcopy(original);d['protection_external_terminal_proposal']['port_nets'][port]='UNEXPECTED'
            with self.subTest(port=port,mode='wrong_net'), self.assertRaises(ValueError): C.validate_terminals(d)

    def test_position_totals_do_not_replace_endpoint_membership(self):
        original=json.loads((HERE / 'terminal-contract.json').read_text())
        for key in ('C2_module','C3_module','servo','total_external_positions'):
            d=copy.deepcopy(original);d['physical_end_count'][key]+=1
            with self.subTest(key=key), self.assertRaises(ValueError): C.validate_terminals(d)
        d=copy.deepcopy(original);d['protection_external_terminal_proposal']['pad_geometry']={'imaginary':True}
        with self.assertRaises(ValueError): C.validate_terminals(d)


if __name__=='__main__':unittest.main()
