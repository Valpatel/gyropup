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
 'BUS_HEAD_FUSED':'Q1.5 Q1.6 Q1.7 Q1.8 U1.1 R2.1 R4.1 R6.1',
 'COMMON_SOURCE':'Q1.1 Q1.2 Q1.3 Q2.1 Q2.2 Q2.3 C3.2',
 'SENSE_HI':'Q2.5 Q2.6 Q2.7 Q2.8 R1.1 U1.9',
 'PAN_INPUT':'R1.2 U1.8 U2.A4 U2.B4 C1.1 R9.1',
 'GATE':'U1.10 Q1.4 Q2.4 R8.1 C3.1',
 'GATE_RC':'R8.2 C2.1',
 'UV_DIV':'R4.2 R5.1 U1.2',
 'OV_DIV':'R2.2 R3.1 U1.3',
 'SHDN_DIV':'R6.2 R7.1 U1.6',
 'GND':'U1.4 U1.5 U2.A2 U2.A3 U2.B2 U2.B3 R3.2 R5.2 R7.2 R9.2 C1.2 C2.2',
 '12V_PAN':'U2.A1 U2.B1',
}
NC_GROUPS={frozenset(('U1.7',)),frozenset(('U2.A6',)),frozenset(('U2.B6',)),frozenset(('U2.A5','U2.B5'))}
PINS_U1={'1':'VIN','2':'UV','3':'OV','4':'RETRY','5':'GND','6':'SHDN','7':'FAULT','8':'VOUT','9':'SENSE','10':'GATE'}
PINS_U2={'A1':'VOUT','B1':'VOUT','A2':'GND','A3':'GND','B2':'GND','B3':'GND','A4':'VIN','B4':'VIN','A5':'VRP','B5':'VRP','A6':'PG','B6':'EN'}
MPNS={'U1':'LTC4368IMS-2#PBF','U2':'Pololu 5577','Q1':'CSD19531Q5AT','Q2':'CSD19531Q5AT',
      'R1':'WSL2512R0100FEA','R2':'TNPW0805464KBEEN','R3':'TNPW08054K99BEEN','R4':'TNPW0805127KBEEN',
      'R5':'TNPW08054K99BEEN','R6':'TNPW0805499KBEEN','R7':'TNPW0805100KBEEN','R8':'TNPW080522K0BEEN','R9':'TNPW0805100KBEEN',
      'C1':'EEU-FC2A220','C2':'C0805C332J1GACTU','C3':'C0805C682J5GACTU'}

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
    for ref,pins in [('U1',PINS_U1),('U2',PINS_U2),('Q1',dict(zip(map(str,range(1,9)),('S','S','S','G','D','D','D','D')))),('Q2',dict(zip(map(str,range(1,9)),('S','S','S','G','D','D','D','D'))))]:
        for pin,func in pins.items():assert functions[ref+'.'+pin]==func,f'{ref}.{pin} wrong manufacturer pin name'
    comps={c.attrib['ref']:c for c in root.findall('./components/comp')}
    assert set(comps)==set(MPNS), 'missing/extra component'
    for ref,mpn in MPNS.items():
        assert comps[ref].find("./fields/field[@name='MPN']").text==mpn, f'{ref} wrong candidate MPN'
    assert len(seen)==62, f'expected62 package leads, got{len(seen)}'
    return {'components':len(comps),'package_leads':len(seen),'connected_nets':len(actual),'NC_groups':len(ncs)}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_receipt():
    receipt=json.loads((HERE/'reports/receipt.json').read_text())
    for path,wanted in receipt['files_sha256'].items():
        assert sha(HERE/path)==wanted,f'stale artifact/source: {path}'
    return receipt
if __name__=='__main__':
    print(json.dumps(check_netlist(ET.parse(HERE/'reports/netlist.xml').getroot()),sort_keys=True))
    check_receipt();print('source and artifact binding: PASS')
