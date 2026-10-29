"""Independent design contract checked against KiCad's exported connectivity, never generator labels.
Contract transcribed from manufacturer pins and the reviewed branch topology, not imported from design.py.
"""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
# Every actual lead, including hidden stacked leads. NCs are verified separately.
NETS={
 'BUS_HEAD_FUSED':'D1.1 D1.2',
 'VIN_PROTECTED':'D1.K D2.K C4.1 R11.1 Q1.5 Q1.6 Q1.7 Q1.8 U1.1 R2.1 R4.1 R6.1',
 'COMMON_SOURCE':'Q1.1 Q1.2 Q1.3 Q2.1 Q2.2 Q2.3 C3.2',
 'SENSE_HI':'Q2.5 Q2.6 Q2.7 Q2.8 R1.1 R10.1 U1.9',
 'PAN_INPUT':'R1.2 R10.2 U1.8 U2.A4 U2.B4 C1.1 R9.1 C5.1 R12.1 R14.1 U3.1',
 'GATE':'U1.10 Q1.4 Q2.4 R8.1 C3.1',
 'GATE_RC':'R8.2 C2.1 C6.1 C7.1 C8.1',
 'UV_DIV':'R4.2 R5.1 U1.2',
 'OV_DIV':'R2.2 R3.1 U1.3',
 'SHDN_DIV':'R6.2 R7.1 U1.6',
 'GND':'U1.4 U1.5 U2.A2 U2.A3 U2.B2 U2.B3 R3.2 R5.2 R7.2 R9.2 C1.2 C2.2 D2.1 D2.2 C4.2 C5.2 C6.2 C7.2 C8.2 R11.2 R13.2 U3.8 U3.13',
 '12V_PAN':'U2.A1 U2.B1',
 'EN_SENSE':'R12.2 R13.1 U3.3',
 'PAN_ENABLE':'R14.2 U3.6 U2.B6',
}
NC_GROUPS={frozenset(('U1.7',)),frozenset(('U2.A6',)),frozenset(('U2.A5','U2.B5')),
           *[frozenset((f'U3.{pin}',)) for pin in (2,4,5,7,9,10,11,12,14)]}
PINS_U1={'1':'VIN','2':'UV','3':'OV','4':'RETRY','5':'GND','6':'SHDN','7':'FAULT','8':'VOUT','9':'SENSE','10':'GATE'}
PINS_U2={'A1':'VOUT','B1':'VOUT','A2':'GND','A3':'GND','B2':'GND','B3':'GND','A4':'VIN','B4':'VIN','A5':'VRP','B5':'VRP','A6':'PG','B6':'EN'}
MPNS={'U1':'LTC4368IMS-2#PBF','U2':'Pololu 5577','Q1':'CSD19531Q5AT','Q2':'CSD19531Q5AT',
      'R1':'WSL2512R0100FEA','R2':'TNPW0805464KBEEN','R3':'TNPW08054K99BEEN','R4':'TNPW0805100KBEEN',
      'R5':'TNPW08054K99BEEN','R6':'TNPW0805499KBEEN','R7':'TNPW0805100KBEEN','R8':'TNPW080522K0BEEN','R9':'TNPW0805100KBEEN',
      'C1':'EEU-FC2A220','C2':'C1206C473F1GECAUTO','C3':'C0805C682J5GACTU'}

MPNS.update({'D1':'V10P20-M3/87A','D2':'V10P20-M3/87A','U3':'TPS3760A012DYYR',
 'R10':'WSL2512R0200FEA','R11':'TNPW0805100KBEEN','R12':'TNPW0805150KBEEN','R13':'TNPW080510K0BEEN','R14':'TNPW0805499KBEEN',
 'C4':'C0805C104K1RACTU','C5':'C0805C104K1RACTU','C6':'C1206C473F1GECAUTO','C7':'C1206C473F1GECAUTO','C8':'C1206C473F1GECAUTO'})
PINS_U3={'1':'VDD','3':'SENSE','6':'RESET','8':'GND','13':'GND','9':'CTR','10':'CTS',**{str(n):'NC' for n in (2,4,5,7,11,12,14)}}

def check_netlist(root):
    actual={}; ncs=set(); seen=set(); functions={}
    for net in root.findall('./nets/net'):
        nodes=net.findall('node'); keys=[]
        for node in nodes:
            key=node.attrib['ref']+'.'+node.attrib['pin']
            assert key not in seen, f'duplicate physical pin {key}'
            seen.add(key);keys.append(key)
            functions[key]=node.attrib.get('pinfunction','').rsplit('_',1)[0]
        if net.attrib['name'].startswith('unconnected-'):
            assert all('no_connect' in node.attrib['pintype'] for node in nodes),'unmarked disconnected pin'
            ncs.add(frozenset(keys))
        else:
            name=net.attrib['name'].removeprefix('/')
            assert name not in actual, f'duplicate net {name}'
            actual[name]=set(keys)
    expected={k:set(v.split()) for k,v in NETS.items()}
    assert actual==expected, f'connectivity mismatch: {[(k,sorted(actual.get(k,set())^expected.get(k,set()))) for k in actual.keys()|expected.keys() if actual.get(k)!=expected.get(k)]}'
    assert ncs==NC_GROUPS, f'NC mismatch: {ncs}'
    for ref,pins in [('U1',PINS_U1),('U2',PINS_U2),('U3',PINS_U3),('D1',{'1':'A','2':'A','K':'K'}),('D2',{'1':'A','2':'A','K':'K'}),('Q1',dict(zip(map(str,range(1,9)),('S','S','S','G','D','D','D','D')))),('Q2',dict(zip(map(str,range(1,9)),('S','S','S','G','D','D','D','D'))))]:
        for pin,func in pins.items():assert functions[ref+'.'+pin]==func,f'{ref}.{pin} wrong manufacturer pin name'
    comps={c.attrib['ref']:c for c in root.findall('./components/comp')}
    assert set(comps)==set(MPNS), 'missing/extra component'
    for ref,mpn in MPNS.items():
        assert comps[ref].find("./fields/field[@name='MPN']").text==mpn, f'{ref} wrong candidate MPN'
    assert len(seen)==102, f'expected102 package leads, got{len(seen)}'
    return {'components':len(comps),'package_leads':len(seen),'connected_nets':len(actual),'NC_groups':len(ncs)}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
REQUIRED_FILES={'README.md','pins.md','fault-review.md','availability.json','circuit_design.py','generate.py','calculate.py',
 'verify.py','test_circuit.py','build.py','pan-cutoff.kicad_sch','pan-cutoff.kicad_pro','candidate.kicad_sym',
 'sym-lib-table','candidate-bom.csv','pictures/pan-cutoff.svg','reports/erc.rpt','reports/netlist.xml',
 'reports/calculations.json','../fuse-board/sexp.py'}
def check_receipt(receipt=None):
    if receipt is None: receipt=json.loads((HERE/'reports/receipt.json').read_text())
    assert receipt['schema']==1 and receipt['status']=='CANDIDATE_NOT_QUALIFIED', 'wrong evidence schema/status'
    assert receipt['kicad']=='10.0.1', 'unreviewed EDA tool version'
    assert set(receipt['files_sha256'])==REQUIRED_FILES, 'missing/extra source or artifact bindings'
    for path,wanted in receipt['files_sha256'].items():
        assert sha(HERE/path)==wanted,f'stale artifact/source: {path}'
    return receipt
if __name__=='__main__':
    print(json.dumps(check_netlist(ET.parse(HERE/'reports/netlist.xml').getroot()),sort_keys=True))
    check_receipt();print('source and artifact binding: PASS')
