"""Export Robot/Combined guides from a separately accepted real per-part collection.

Pure serialization/copying only: never imports CAD or turns the retained
playground manifest into construction geometry. Writes a fresh candidate tree;
transactional adoption/index composition remain separate reviewable steps.
"""
from __future__ import annotations
import argparse
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_data import bounds, sha
from robot_manufacturing import mapping
from robot_recipe import WARNING, operation, robot_operations, validate_operations

ROOT=Path(__file__).resolve().parents[3]


def encode(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
def digest(value):return hashlib.sha256(value).hexdigest()


def verified_parts(collection,folder):
    if collection.get('schema')!='gyropup.robot-assembly-parts/1' or collection.get('units')!='mm' or collection.get('up')!='z':
        raise ValueError('Not a real CAD-mm/Z-up collection')
    if not re.fullmatch('[0-9a-f]{40}',collection.get('source_commit','')):
        raise ValueError('Immutable collection commit required')
    parts=collection['parts'];names=[p['name'] for p in parts]
    if not names or len(names)!=len(set(names)):
        raise ValueError('Empty or duplicate collection parts')
    files=set()
    for part in parts:
        file=part['file'];path=folder/file
        if not file.startswith('meshes/') or file in files or path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError('Unsafe or aliased collection mesh')
        files.add(file)
        if sha(path)!=part['sha256'] or bounds(path)!=part['bounds_mm']:
            raise ValueError('Actual collection mesh differs: '+part['name'])
    validate_operations(robot_operations(),[n for n in names if not n.startswith('turret.')])
    if not any(n.startswith('turret.') for n in names):
        raise ValueError('Combined collection lacks actual mounted turret')
    mount=collection['mount_reference']
    if (abs(mount['tm_face_z_mm']-mount['riser_top_mm'])>.02 or mount['pan_base_contact_vertices']<3
        or mount.get('wrong_xy_rejected') is not True
        or set(mount.get('bolt_center_errors_mm',{}))!={'riser','turret.pan_base'}
        or any(len(errors)!=4 or any(not math.isfinite(e) or e>.02 for e in errors)
               for errors in mount['bolt_center_errors_mm'].values())):
        raise ValueError('Missing actual body/turret mounting-plane evidence')
    return parts


def plain(guide):
    sections=[]
    for i,step in enumerate(guide['steps'],1):
        items=''.join('<li>'+escape(r['title'])+' ×'+str(r['quantity'])+' modeled instances</li>' for r in guide['source']['requirements_by_step'][step['id']])
        sections.append('<section id="'+step['id']+'"><h2>'+str(i)+'. '+escape(step['title'])+'</h2><p>'+escape(step['text'])+'</p><ul>'+items+'</ul></section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Robot assembly · educational WIP</title><style>body{max-width:760px;margin:24px auto;padding:0 16px;font:16px/1.6 system-ui}section{margin:32px 0}</style>'
            '<main><h1>'+escape(guide['snapshot']['id'])+'</h1><p>'+escape(guide['source']['qualification'])+'</p>'+''.join(sections)+'</main></html>') .encode()


def generate(collection,folder,recipe_sha256,bom_hashes,collection_sha256,manufacturing):
    parts=verified_parts(collection,folder);pin=collection['source_commit'];short=pin[:12]
    directories={key:key+'-wip-'+short for key in ('robot','combined')}
    outputs={};rows=[]
    for kind in ('robot','combined'):
        directory=directories[kind]
        included=[p for p in parts if kind=='combined' or not p['name'].startswith('turret.')]
        model_parts=[]
        for part in included:
            public={k:part[k] for k in ('name','color','visible','bounds_mm','sha256')}
            public['compound']=part.get('compound',False)
            public['logical_part']=manufacturing[part['name']].get('key',part['name'])
            public['title']=part['name'].replace('_',' ')
            material=manufacturing[part['name']].get('plan',{}).get('material')
            if material:public['material']=material
            if kind=='combined' and not part['name'].startswith('turret.'):
                public['file']='../'+directories['robot']+'/'+part['file']
            else:
                public['file']=part['file'];outputs[directory+'/'+part['file']]=(folder/part['file']).read_bytes()
            public['source_group']=part['source_group'];public['frame']='assembled robot CAD mm/Z-up'
            model_parts.append(public)
        model=encode({'title':'Gyropup '+kind+' assembly','units':'mm','up':'z','parts':model_parts})
        outputs[directory+'/view.json']=model
        ops=robot_operations()
        if kind=='combined':
            ops.append(operation('turret-module','Mounted turret subassembly',
                [p['name'] for p in parts if p['name'].startswith('turret.')],
                'tools/engineering/robot/robot_view.py::turret_shapes; hardware/cad/body/body_params.py::tm',
                'The already-modeled turret subassembly is located on the actual collected P3 riser TM face and pan-axis datum. '
                'This is not the bench model transplanted at an assumed height. Its internal build order and unplaced '
                'fitting gaps remain those of the separate Turret WIP guide; this step does not qualify those fittings.', 'turret'))
        names=[p['name'] for p in included];seen=[];steps=[];groups={}
        steps.append({'id':'overview','title':'Full '+kind+' CAD reference','subassembly':'overview','parts':names,
                      'highlight':[],'offsets_mm':{},'text':'Assembled source CAD reference at the 300 mm stance. This overview does not mark any construction operation complete. '+WARNING,
                      'camera':{'direction':[1,-1,.65]}})
        groups['overview']={'id':'overview','title':'Assembled reference','parts':names}
        requirements={'overview':[]};sources={};kinds={'overview':'reference'}
        for op in ops:
            seen+=op['additions'];chapter=op['subassembly']
            group=groups.setdefault(chapter,{'id':chapter,'title':{'body':'Body','l-leg':'Left leg','r-leg':'Right leg','turret':'Mounted turret'}[chapter],'parts':[]})
            group['parts']+=op['additions']
            step={'id':op['id'],'title':op['title'],'subassembly':chapter,'parts':list(seen),'highlight':op['additions'],
                  'offsets_mm':{name:op['offset'] for name in op['additions']},'text':op['text'],'camera':op['camera']}
            if len(steps)>1:step['requires']=[steps[-1]['id']]
            steps.append(step);requirements[op['id']]=[{'title':n,'quantity':1} for n in op['additions']]
            sources[op['id']]=op['source_operation'];kinds[op['id']]='construction' if chapter!='turret' else 'subassembly-placement'
        if set(seen)!=set(names) or len(seen)!=len(set(seen)):
            raise ValueError('Construction stages do not exactly cover this snapshot')
        source={'qualification':WARNING,'configuration':collection['configuration'],'cad_inputs':collection['inputs'],
                'collection_sha256':collection_sha256,'native_producer_inputs':collection.get('producer_inputs',{}),'exporter_sha256':sha(Path(__file__)),'hardware_tree':collection['hardware_tree'],
                'collector_sha256':collection['collector_sha256'],'recipe_sha256':recipe_sha256,'bom_hashes':bom_hashes,
                'manufacturing_mapper_sha256':sha(Path(__file__).with_name('robot_manufacturing.py')),
                'overview_step_id':'overview','step_kinds':kinds,
                'install_order_by_step':{'overview':[],**{op['id']:op['additions'] for op in ops}},
                'install_order_basis':'Explicit educational presentation order from the authored source operations; not verified insertion, fastening or physical assembly order.',
                'manufacturing_by_part':{name:manufacturing[name] for name in names},'operation_sources':sources,
                'requirements_by_step':requirements,'datums':collection['datums'],'mount_reference':collection['mount_reference'],
                'limits':'Source-owned WIP sequence; no physical fit, insertion path, fastening/preload, power, motion or strength qualification.'}
        guide={'schema':'cad-agent.assembly-guide/1','snapshot':{'id':directory,'revision':short,'status':'wip','source_commit':pin},
               'model':{'file':'view.json','sha256':digest(model)},'source':source,'subassemblies':list(groups.values()),'steps':steps}
        instruction=encode({'snapshot':guide['snapshot'],'qualification':source['qualification'],
                            'steps':[{'id':s['id'],'title':s['title'],'text':s['text'],'requirements':requirements[s['id']]} for s in steps]})
        source['instructions']={'file':'instructions.json','sha256':digest(instruction)}
        outputs[directory+'/instructions.json']=instruction;outputs[directory+'/instructions.html']=plain(guide)
        raw=encode(guide);outputs[directory+'/guide.json']=raw
        rows.append({'id':directory,'title':kind.title()+' · '+short+' · WIP','assembly':kind,'status':'wip',
                     'file':directory+'/guide.json','sha256':digest(raw)})
    outputs['index-entries.json']=encode(rows)
    return outputs


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    collection=json.loads(args.collection.read_text());folder=args.collection.parent
    config=json.loads((ROOT/'tools/engineering/robot/readme-design.json').read_text())
    if collection['inputs']!=config['source']['files'] or collection['hardware_tree']!=config['source']['hardware_tree']:
        raise ValueError('Collected geometry differs from the current recorded CAD/hardware boundary')
    for file,value in collection['inputs'].items():
        if sha(ROOT/file)!=value:raise ValueError('Actual source changed: '+file)
    boms={f:sha(ROOT/f) for f in ('hardware/exports/body/bom.json','hardware/exports/leg/bom.json','hardware/exports/turret/bench/bom.json')}
    manufacturing=mapping(ROOT,[p['name'] for p in collection['parts']],collection)
    outputs=generate(collection,folder,sha(Path(__file__).with_name('robot_recipe.py')),boms,sha(args.collection),manufacturing)
    if not args.check and args.out.exists():raise ValueError('Use a fresh candidate output')
    for name,data in outputs.items():
        path=args.out/name
        if args.check:
            if path.read_bytes()!=data:raise ValueError('Stale generated guide output: '+name)
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    print(('PASS' if args.check else 'Generated candidate:')+' '+str(len(outputs))+' source-bound outputs; no adoption or qualification')


if __name__=='__main__':main()
