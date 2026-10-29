"""Bounded native schematic build. KiCad10 CLI only; no PCB/DRC/Spice/physical qualification."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import calculate
import generate
import verify
HERE=Path(__file__).resolve().parent
CLI=os.environ.get('KICAD_CLI','kicad-cli')

def run(*args):
    return subprocess.run([CLI,*args],cwd=HERE,check=True,capture_output=True,text=True).stdout.strip()
def normalize_netlist(path):
    tree=ET.parse(path);root=tree.getroot()
    root.find('./design/source').text='pan-cutoff.kicad_sch'
    root.find('./design/date').text='reproducible export; see receipt.json'
    ET.indent(tree,space='  ');tree.write(path,encoding='UTF-8',xml_declaration=True)
    path.write_bytes(path.read_bytes()+b'\n')

def build():
    version=run('version')
    if version!='10.0.1': raise RuntimeError('Review required before changing pinned KiCad10.0.1: '+version)
    (HERE/'reports').mkdir(exist_ok=True);(HERE/'pictures').mkdir(exist_ok=True)
    generate.generate()
    print(run('sch','erc','--severity-all','--exit-code-violations','-o','reports/erc.rpt','pan-cutoff.kicad_sch'))
    erc=HERE/'reports/erc.rpt';erc.write_text('\n'.join(erc.read_text().splitlines()[1:])+'\n')
    run('sch','export','netlist','--format','kicadxml','-o','reports/netlist.xml','pan-cutoff.kicad_sch')
    normalize_netlist(HERE/'reports/netlist.xml')
    contract=verify.check_netlist(ET.parse(HERE/'reports/netlist.xml').getroot())
    run('sch','export','svg','-o','pictures/','pan-cutoff.kicad_sch')
    svg=HERE/'pictures/pan-cutoff.svg'
    stable,count=re.subn(r'<title>SVG Image created as pan-cutoff\.svg date [^<]+</title>',
                        '<title>Gyropup PAN cutoff candidate; see source-bound receipt</title>',svg.read_text())
    if count!=1: raise RuntimeError('Unexpected KiCad SVG title format; review before normalizing metadata')
    # KiCad emits trailing spaces inside multiline style attributes; retain the
    # newline separators while normalizing that insignificant export whitespace.
    svg.write_text('\n'.join(line.rstrip() for line in stable.splitlines())+'\n')
    (HERE/'reports/calculations.json').write_text(json.dumps(calculate.calculate(),indent=2,sort_keys=True)+'\n')
    files=['README.md','pins.md','fault-review.md','availability.json','circuit_design.py','generate.py','calculate.py','verify.py','test_circuit.py','build.py',
      'pan-cutoff.kicad_sch','pan-cutoff.kicad_pro','candidate.kicad_sym','sym-lib-table','candidate-bom.csv',
      'pictures/pan-cutoff.svg','reports/erc.rpt','reports/netlist.xml','reports/calculations.json']
    receipt={'schema':1,'status':'CANDIDATE_NOT_QUALIFIED','kicad':version,'source_base':'d284f63f26d3f5a83347c33e402103f486668b24',
      'interface_source':'PR67 8b86e7f, confirmed unchanged at36aa696','command':'python hardware/carrier-pan-protection/build.py',
      'contract':contract,'files_sha256':{p:verify.sha(HERE/p) for p in files},
      'limits':['No PCB, DRC or footprint qualification','No transient simulation or measured circuit','No safe/ready/selected claim']}
    # The shared parser is an actual generator dependency, recorded relative to this directory.
    receipt['files_sha256']['../fuse-board/sexp.py']=verify.sha(HERE.parent/'fuse-board/sexp.py')
    (HERE/'reports/receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(contract,sort_keys=True)); print('Candidate schematic build passed; physical qualification remains open.')
if __name__=='__main__':build()
