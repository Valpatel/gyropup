"""Independent exported-net checks and actual native-schematic negative controls."""
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'fuse-board'))
import sexp as S
import verify
import calculate

class CircuitTests(unittest.TestCase):
    def setUp(self):self.root=ET.parse(HERE/'reports/netlist.xml').getroot()
    def test_actual_kicad_netlist(self):
        self.assertEqual(verify.check_netlist(self.root)['package_leads'],62)
    def test_artifact_binding(self): verify.check_receipt()
    def test_receipt_cannot_drop_source_bindings(self):
        receipt=json.loads((HERE/'reports/receipt.json').read_text())
        del receipt['files_sha256']['pan-cutoff.kicad_sch']
        with self.assertRaises(AssertionError):verify.check_receipt(receipt)
    def test_arithmetic_and_limits(self):
        r=calculate.calculate()
        self.assertAlmostEqual(r['FET_pair_loss_W_at3_25A_max25C_Rds'],.1352)
        self.assertAlmostEqual(r['servo_12_6V_static_margin_V'],.24)
        self.assertLess(r['OV']['trip_V'][0],47)
        self.assertGreater(r['OV']['trip_V'][1],47.9)
        self.assertGreater(r['OV']['recover_V'][0],42)
        self.assertLess(r['UV']['recover_V'][1],15)
        self.assertLess(r['startup_margin_A_before_capacitance_at_15V80pct'],0)
        self.assertIn('12V_regeneration',r['unqualified'])
        self.assertEqual(json.loads((HERE/'reports/calculations.json').read_text()),r)
    def test_candidate_bom_and_availability_coverage(self):
        with (HERE/'candidate-bom.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),16)
        self.assertEqual({r['reference']:r['candidate_mpn'] for r in rows},verify.MPNS)
        offers=json.loads((HERE/'availability.json').read_text())
        pairs={}
        for row in offers['rows']:
            self.assertEqual(row['build_quantity'],len(row['references']))
            self.assertEqual(row['status'],'candidate_not_selected')
            for ref in row['references']:
                self.assertNotIn(ref,pairs);pairs[ref]=row['mpn']
        self.assertEqual(pairs,verify.MPNS)
        self.assertTrue(offers['not_ready_to_order'])
    def test_missing_or_extra_lead_rejected(self):
        net=self.root.find("./nets/net[@name='/GND']")
        node=net.find("node[@ref='U2'][@pin='B3']");net.remove(node)
        with self.assertRaises(AssertionError):verify.check_netlist(self.root)
    def test_wrong_manufacturer_pin_function_rejected(self):
        self.root.find("./nets/net/node[@ref='U1'][@pin='9']").set('pinfunction','VOUT_9')
        with self.assertRaises(AssertionError):verify.check_netlist(self.root)
    def test_wrong_part_variant_rejected(self):
        self.root.find("./components/comp[@ref='U1']/fields/field[@name='MPN']").text='LTC4368IMS-1#PBF'
        with self.assertRaises(AssertionError):verify.check_netlist(self.root)
    def native_negative(self,change):
        with tempfile.TemporaryDirectory(prefix='pan-native-negative-') as td:
            td=Path(td);tree=S.parse((HERE/'pan-cutoff.kicad_sch').read_text());change(tree)
            sch=td/'pan-cutoff.kicad_sch';sch.write_text(S.dump(tree)+'\n')
            subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(td/'actual.xml'),str(sch)],check=True,capture_output=True,text=True)
            with self.assertRaises(AssertionError):verify.check_netlist(ET.parse(td/'actual.xml').getroot())
    def test_native_wrong_fet_orientation(self):
        def change(tree):
            q2=next(s for s in S.find(tree,'symbol') if any(p[1:3]==['Reference','Q2'] for p in S.find(s,'property')))
            S.first(q2,'lib_id')[1]='Candidate:Q_IN'
        self.native_negative(change)
    def test_native_sense_pins_reversed(self):
        def change(tree):
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:LTC4368IMS2')
            for unit in S.find(lib,'symbol'):
                for pin in S.find(unit,'pin'):
                    num=S.first(pin,'number')
                    if num[1] in ('8','9'): num[1]='9' if num[1]=='8' else '8'
        self.native_negative(change)
    def test_native_hidden_power_pin_implicit_net(self):
        def change(tree):
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:D42V55F12')
            for unit in S.find(lib,'symbol'):
                for pin in S.find(unit,'pin'):
                    if S.first(pin,'number')[1]=='B4':pin[1]=S.Sym('power_in')
        self.native_negative(change)
    def test_native_cutoff_bypass(self):
        def change(tree):
            for label in S.find(tree,'label'):
                if label[1]=='PAN_INPUT':label[1]='BUS_HEAD_FUSED'
        self.native_negative(change)
    def test_native_hotswap_cap_wrong_return(self):
        def change(tree):
            labels=[l for l in S.find(tree,'label') if l[1]=='COMMON_SOURCE' and float(S.first(l,'at')[2])>70]
            self.assertEqual(len(labels),1);labels[0][1]='GND'
        self.native_negative(change)
    def test_invalid_resistance(self):
        old=calculate.D.PARTS['R1']['value']
        try:
            for bad in ('0','-1','nan','inf'):
                calculate.D.PARTS['R1']['value']=bad
                with self.assertRaises(ValueError):calculate.resistance('R1')
        finally:calculate.D.PARTS['R1']['value']=old
if __name__=='__main__':unittest.main(verbosity=2)
