"""Generate portable editable KiCad schematic and BOM; no PCB/fabrication output.
Uses the repository's existing KiCad S-expression helper. Standard-library Python only.
"""
from pathlib import Path
import csv
import json
import sys
import uuid
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'fuse-board'))
import sexp as S
sys.path.insert(0, str(HERE))
import circuit_design as D
NS = uuid.UUID('8f4ecb6d-33b0-444e-b111-79ee1f3d2808')
def uid(*v): return str(uuid.uuid5(NS, '/'.join(map(str,v))))
def n(tag,*args): return [S.Sym(tag),*args]
def atom(s): return S.Sym(s)
def effects(size=1.27,justify=None,hide=False):
    x=n('effects',n('font',n('size',size,size)))
    if justify: x.append(n('justify',*[atom(t) for t in justify.split()]))
    if hide: x.append(n('hide',atom('yes')))
    return x
def prop(k,v,x=0,y=0,hide=False): return n('property',k,v,n('at',x,y,0),effects(hide=hide))
def line(a,b): return n('polyline',n('pts',n('xy',*a),n('xy',*b)),n('stroke',n('width',0.254),n('type',atom('default'))),n('fill',n('type',atom('none'))))
def symbol(name, s):
    bw,bh=s['box']; body=[]
    if name in ('C','C_POL'):
        body=[line((-1.27,2.54),(-1.27,-2.54)),line((1.27,2.54),(1.27,-2.54))]
    elif name=='FLAG': body=[line((0,0),(0,2.54)),line((0,2.54),(2.54,2.54)),line((2.54,2.54),(0,3.81))]
    else: body=[n('rectangle',n('start',-bw,bh),n('end',bw,-bh),n('stroke',n('width',0.254),n('type',atom('default'))),n('fill',n('type',atom('background'))))]
    pins=[]; seen=set()
    for num,pname,kind,x,y,a in s['pins']:
        # Hidden stacked leads stay electrically explicit. One visible number is supplemented by pins.md.
        hidden=(x,y) in seen; seen.add((x,y))
        p=n('pin',atom('passive' if hidden else kind),atom('line'),n('at',x,y,a),n('length',5.08),n('name',pname,effects(1.016)),n('number',num,effects(1.016)))
        if hidden:p.append(n('hide',atom('yes')))
        pins.append(p)
    return n('symbol','Candidate:'+name,n('pin_names',n('offset',1.016)),n('exclude_from_sim',atom('no')),
      n('in_bom',atom('yes')),n('on_board',atom('yes')),prop('Reference','U'),prop('Value',name),prop('Footprint','',hide=True),
      n('symbol',name+'_0_1',*body),n('symbol',name+'_1_1',*pins))
def generate():
    root=uid('root'); placed=[]; connections=[]
    libs=[symbol(k,v) for k,v in D.SYMBOLS.items()]
    # True power-path wires are independently exported by KiCad, not a separately invented netlist.
    linked={('Q1','1'),('Q1','2'),('Q1','3'),('Q2','1'),('Q2','2'),('Q2','3'),
            ('Q2','5'),('Q2','6'),('Q2','7'),('Q2','8'),('R1','1'),('R1','2'),('U2','A4'),('U2','B4')}
    for ref,p in D.PARTS.items():
        X,Y=p['xy']; s=D.SYMBOLS[p['symbol']]; symid=uid('part',ref); flag=ref.startswith('#')
        fields=[prop('Reference',ref,X,Y-s['box'][1]-6.35,flag),prop('Value',p['value'],X,Y-s['box'][1]-2.54,flag),
                prop('Footprint',p['footprint'],hide=True),prop('Datasheet',p['datasheet'],hide=True),
                prop('MPN',p['mpn'],hide=True),prop('Status','UNSELECTED / UNQUALIFIED CANDIDATE',hide=True),prop('Note',p['note'],hide=True)]
        part=n('symbol',n('lib_id','Candidate:'+p['symbol']),n('at',X,Y,0),n('unit',1),n('exclude_from_sim',atom('no')),
               n('in_bom',atom('no' if flag else 'yes')),n('on_board',atom('no' if flag else 'yes')),n('dnp',atom('no')),
               n('uuid',symid),*fields)
        seen=set()
        for num,pname,kind,px,py,angle in s['pins']:
            part.append(n('pin',num,n('uuid',uid('pin',ref,num))))
            pt=(round(X+px,4),round(Y-py,4)); net=p['pins'][num]
            if pt in seen: continue
            seen.add(pt)
            if net is None:
                connections.append(n('no_connect',n('at',*pt),n('uuid',uid('nc',ref,num))))
                continue
            if (ref,num) in linked: continue
            a=(angle+180)%360
            connections.append(n('label',net,n('at',*pt,a),effects(1.016, 'left bottom' if a in (0,90) else 'right bottom'),n('uuid',uid('label',ref,num))))
        part.append(n('instances',n('project',D.NAME,n('path','/'+root,n('reference',ref),n('unit',1)))))
        placed.append(part)
    for i,(a,b,net) in enumerate([
        ((88.9,45.72),(132.08,45.72),'COMMON_SOURCE'),
        ((157.48,45.72),(201.93,45.72),'SENSE_HI'),
        ((219.71,45.72),(307.34,45.72),'PAN_INPUT'),
    ]):
        connections.append(n('wire',n('pts',n('xy',*a),n('xy',*b)),n('stroke',n('width',0),n('type',atom('default'))),n('uuid',uid('wire',i))))
        connections.append(n('label',net,n('at',*a,0),effects(1.016,'left bottom'),n('uuid',uid('wirelabel',i))))
    notes=[n('text',text,n('exclude_from_sim',atom('no')),n('at',x,y,0),effects(1.27,'left'),n('uuid',uid('text',i))) for i,(x,y,text) in enumerate(D.NOTES)]
    doc=n('kicad_sch',n('version',20250114),n('generator','eeschema'),n('generator_version','10.0'),n('uuid',root),n('paper','A3'),
          n('title_block',n('title','Gyropup PAN input cutoff - circuit candidate'),n('date',D.DATE),n('rev','CANDIDATE A'),
            n('company','Valpatel Software LLC'),n('comment',1,'Issue83 / PR84. Not for fabrication. No PCB or footprint qualification.')),
          n('lib_symbols',*libs),*placed,*connections,*notes,n('sheet_instances',n('path','/',n('page','1'))),n('embedded_fonts',atom('no')))
    (HERE/(D.NAME+'.kicad_sch')).write_text(S.dump(doc)+'\n')
    (HERE/'candidate.kicad_sym').write_text(S.dump(n('kicad_symbol_lib',n('version',20250114),n('generator','kicad_symbol_editor'),*[n('symbol',s[1].split(':')[1],*s[2:]) for s in libs]))+'\n')
    (HERE/'sym-lib-table').write_text('(sym_lib_table (lib (name "Candidate")(type "KiCad")(uri "${KIPRJMOD}/candidate.kicad_sym")(options "")(descr "Authored candidate symbols; see pins.md")))\n')
    # No rule suppressions. An empty project makes the directory the library-table root for CLI ERC.
    (HERE/(D.NAME+'.kicad_pro')).write_text('{}\n')
    with (HERE/'candidate-bom.csv').open('w') as f:
        w=csv.writer(f); w.writerow(['reference','qty','value','candidate_mpn','datasheet','note'])
        for r,p in D.PARTS.items():
            if not r.startswith('#'):w.writerow([r,1,p['value'],p['mpn'],p['datasheet'],p['note']])
    print('generated native schematic + editable library + candidate BOM')
if __name__=='__main__': generate()
