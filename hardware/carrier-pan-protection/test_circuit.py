"""Independent exported-net checks and actual native-schematic negative controls."""
import csv
import copy
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
        self.assertEqual(verify.check_netlist(self.root)['package_leads'],104)
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
        self.assertLess(r['legacy_10mohm_startup_min_A'],3.25)
        screen=calculate.require_static_screen()
        self.assertGreater(screen['startup_margin_A'],.28)
        self.assertGreater(screen['15V_enable_margin_V'],.06)
        self.assertFalse(screen['qualified'])
        self.assertAlmostEqual(screen['charged_reverse_U1_differential_V'],-57)
        self.assertIn('12V_regeneration',r['unqualified'])
        self.assertEqual(json.loads((HERE/'reports/calculations.json').read_text()),r)
    def test_candidate_bom_and_availability_coverage(self):
        with (HERE/'candidate-bom.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),30)
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
    def test_static_acceptance_boundaries_reject_unsafe_scenarios(self):
        for case in ({'cin_uF':2000},{'efficiency':.7},{'diode_drop_V':1.6},
                     {'clamp_min_V':-6},{'charged_output_V':61},{'raw_reverse_V':-146},
                     {'measured_slew_V_per_s':450},{'fet_pair_ohm':.05}):
            with self.subTest(case=case),self.assertRaises(ValueError):calculate.require_static_screen(**case)
        for case in ({'cin_uF':float('nan')},{'efficiency':1.1},{'measured_slew_V_per_s':0}):
            with self.subTest(case=case),self.assertRaises(ValueError):calculate.require_static_screen(**case)
    def test_missing_ramp_capacitance_fails_sequencing(self):
        old=calculate.D.PARTS['C6']['value']
        try:
            calculate.D.PARTS['C6']['value']='1nF 100V 1%'
            with self.assertRaises(ValueError):calculate.require_static_screen()
        finally:calculate.D.PARTS['C6']['value']=old
    def test_wrong_supervisor_ov_variant_rejected(self):
        self.root.find("./components/comp[@ref='U3']/fields/field[@name='MPN']").text='TPS3760E012DYYR'
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
            c3=next(s for s in S.find(tree,'symbol') if any(p[1:3]==['Reference','C3'] for p in S.find(s,'property')))
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]==S.first(c3,'lib_id')[1])
            pin=next(p for unit in S.find(lib,'symbol') for p in S.find(unit,'pin') if S.first(p,'number')[1]=='2')
            xy=S.first(c3,'at'); local=S.first(pin,'at'); point=(round(float(xy[1])+float(local[1]),4),round(float(xy[2])-float(local[2]),4))
            wires=[w for w in S.find(tree,'wire') if any(tuple(map(float,xy[1:]))==point for xy in S.find(S.first(w,'pts'),'xy'))]
            self.assertEqual(len(wires),1);tree.remove(wires[0])
            label=copy.deepcopy(next(l for l in S.find(tree,'label') if l[1]=='GND'))
            S.first(label,'at')[1:]=[*point,0];S.first(label,'uuid')[1]='32972365-1e54-4d39-acd1-a9dc74735440';tree.append(label)
        self.native_negative(change)
    def test_native_reverse_series_barrier(self):
        def change(tree):
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:D_SERIES')
            for unit in S.find(lib,'symbol'):
                for pin in S.find(unit,'pin'):S.first(pin,'at')[1]=-float(S.first(pin,'at')[1])
        self.native_negative(change)
    def test_native_reverse_negative_clamp(self):
        def change(tree):
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:D_CLAMP')
            for unit in S.find(lib,'symbol'):
                for pin in S.find(unit,'pin'):S.first(pin,'at')[2]=-float(S.first(pin,'at')[2])
        self.native_negative(change)
    def test_native_enable_bypassed(self):
        def change(tree):
            for label in S.find(tree,'label'):
                if label[1]=='PAN_ENABLE':label[1]='PAN_INPUT'
        self.native_negative(change)
    def test_native_parallel_sense_resistor_missing(self):
        def change(tree):
            resistor=next(s for s in S.find(tree,'symbol') if any(p[1:3]==['Reference','R10'] for p in S.find(s,'property')))
            tree.remove(resistor)
        self.native_negative(change)
    def test_native_discrete_diode_graphics_match_polarity(self):
        tree=S.parse((HERE/'pan-cutoff.kicad_sch').read_text())
        for name,axis in [('D_SERIES',0),('D_CLAMP',1)]:
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:'+name)
            lines=[p for unit in S.find(lib,'symbol') for p in S.find(unit,'polyline')]
            triangle=next(p for p in lines if len(S.find(S.first(p,'pts'),'xy'))==4)
            points=[tuple(map(float,p[1:])) for p in S.find(S.first(triangle,'pts'),'xy')[:-1]]
            tip=next(p for p in points if sum(p[axis]==q[axis] for q in points)==1)
            back=next(p for p in points if sum(p[axis]==q[axis] for q in points)==2)
            pins=[p for unit in S.find(lib,'symbol') for p in S.find(unit,'pin')]
            k=float(S.first(next(p for p in pins if S.first(p,'number')[1]=='K'),'at')[axis+1])
            a=float(S.first(next(p for p in pins if S.first(p,'number')[1]=='1'),'at')[axis+1])
            self.assertGreater((tip[axis]-back[axis])*(k-a),0)
    def assert_body_diodes(self,tree):
        # Check the visible diode separately from net connectivity: graphics can lie while ERC passes.
        for name in ('Q_IN','Q_OUT'):
            lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:'+name)
            lines=[p for unit in S.find(lib,'symbol') for p in S.find(unit,'polyline')]
            triangles=[p for p in lines if len(S.find(S.first(p,'pts'),'xy'))==4 and S.first(S.first(p,'fill'),'type')[1]=='none']
            self.assertEqual(len(triangles),1)
            points=[tuple(map(float,p[1:])) for p in S.find(S.first(triangles[0],'pts'),'xy')[:-1]]
            cathode=next(p for p in points if sum(p[0]==q[0] for q in points)==1)
            anode=next(p for p in points if sum(p[0]==q[0] for q in points)==2)
            pins=[p for unit in S.find(lib,'symbol') for p in S.find(unit,'pin')]
            drain=float(S.first(next(p for p in pins if S.first(p,'number')[1]=='5'),'at')[1])
            source=float(S.first(next(p for p in pins if S.first(p,'number')[1]=='1'),'at')[1])
            self.assertGreater((cathode[0]-anode[0])*(drain-source),0,'body diode cathode must face drain')
            bars=[]
            for line in lines:
                ends=[tuple(map(float,p[1:])) for p in S.find(S.first(line,'pts'),'xy')]
                if len(ends)==2 and ends[0][0]==ends[1][0]==cathode[0] and min(p[1] for p in ends)<cathode[1]<max(p[1] for p in ends):bars.append(line)
            self.assertEqual(len(bars),1,'one explicit cathode bar must match the diode triangle')
    def test_native_mosfet_body_diodes_match_drain_source(self):
        self.assert_body_diodes(S.parse((HERE/'pan-cutoff.kicad_sch').read_text()))
    def test_reversed_body_diode_graphic_rejected(self):
        tree=S.parse((HERE/'pan-cutoff.kicad_sch').read_text())
        lib=next(s for s in S.find(S.first(tree,'lib_symbols'),'symbol') if s[1]=='Candidate:Q_IN')
        for unit in S.find(lib,'symbol'):
            for line in S.find(unit,'polyline'):
                points=S.find(S.first(line,'pts'),'xy')
                # Reverse only the diode graphic, preserving package pins and the real electrical netlist.
                if all(float(p[2])>4 for p in points):
                    for p in points:p[1]=-float(p[1])
        with self.assertRaises(AssertionError):self.assert_body_diodes(tree)
    def test_invalid_resistance(self):
        old=calculate.D.PARTS['R1']['value']
        try:
            for bad in ('0','-1','nan','inf'):
                calculate.D.PARTS['R1']['value']=bad
                with self.assertRaises(ValueError):calculate.resistance('R1')
        finally:calculate.D.PARTS['R1']['value']=old
if __name__=='__main__':unittest.main(verbosity=2)
