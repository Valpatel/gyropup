"""Bind original robot BREP bytes to captured guides using the existing CAD gate.

Import-safe preflight/serialization only by default. Exact playback validation is
an explicit separate option for the reviewed detached compute procedure. This
module never imports project CAD, repairs geometry, invents a path or grants a
manufacturing/physical assembly release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import posixpath
from urllib.parse import unquote
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_data import sha

IDENTITY=[1,0,0,0,0,1,0,0,0,0,1,0]


def encode(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def valid_sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def native_parts(collection,folder):
    """Verify actual original payload bytes before importing the CAD gate."""
    folder=Path(folder).resolve();meta=collection.get('native_geometry',{})
    if (collection.get('schema')!='gyropup.robot-assembly-parts/1' or collection.get('units')!='mm'
        or collection.get('up')!='z' or not re.fullmatch('[0-9a-f]{40}',collection.get('source_commit',''))
        or meta.get('schema')!='gyropup.robot-native-parts/1' or meta.get('units')!='mm'
        or meta.get('up')!='z' or meta.get('frame')!='assembled robot CAD mm/Z-up'
        or meta.get('format')!='OCCT BREP v1 without triangulation or normals'
        or not isinstance(meta.get('hash_platform'),dict) or not meta['hash_platform']
        or any(not isinstance(k,str) or not isinstance(v,str) or not v for k,v in meta['hash_platform'].items())
        or not isinstance(meta.get('source_correspondence'),str) or not meta['source_correspondence']):
        raise ValueError('Original worldshape native collection is required')
    result={};files=set()
    for part in collection['parts']:
        name=part['name'];entry=part.get('native_geometry',{});file=entry.get('file','')
        path=folder/file
        if (name in result or re.fullmatch(r'breps/[A-Za-z0-9][A-Za-z0-9_-]{0,200}\.brep',file) is None
            or file in files or path.is_symlink() or not path.resolve().is_relative_to(folder)
            or entry.get('matrix')!=IDENTITY or not valid_sha(entry.get('shape_sha256'))
            or not valid_sha(entry.get('sha256'))):
            raise ValueError('Missing, aliased or misplaced native payload: '+name)
        raw=path.read_bytes()
        if not raw or digest(raw)!=entry['sha256']:
            raise ValueError('Changed original native payload: '+name)
        result[name]=raw;files.add(file)
    if not result:raise ValueError('Empty native collection')
    return result


def bind_inputs(collection,collection_sha256,bundles,payloads,bind):
    """Call the core original-byte binder after exact collection/model coverage."""
    parts={p['name']:p for p in collection['parts']};outputs={};records=[];snapshots=set()
    for bundle in bundles:
        guide=json.loads(bundle.files[bundle.path]);parent=Path(bundle.path).parent
        model_path=unquote(posixpath.normpath((parent/guide['model']['file']).as_posix()))
        model=json.loads(bundle.files[model_path]);names=[p['name'] for p in model['parts']]
        if (guide['source'].get('collection_sha256')!=collection_sha256
            or guide['snapshot']['source_commit']!=collection['source_commit']
            or len(names)!=len(set(names)) or set(names)-set(parts)
            or any(p['sha256']!=parts[p['name']]['sha256'] for p in model['parts'])):
            raise ValueError('Guide does not bind this exact source collection')
        selected={n:payloads[n] for n in names}
        binding=bind(bundle,selected,producer_hash_platform=collection['native_geometry']['hash_platform'])
        for name,entry in binding['instances'].items():
            original=parts[name]['native_geometry']
            if (entry['brep_sha256']!=original['sha256'] or entry['shape_sha256']!=original['shape_sha256']
                or entry['matrix']!=original['matrix']):
                raise ValueError('Core binding changed original BREP identity or placement')
            file='breps/'+entry['brep_sha256']+'.brep';outputs[file]=selected[name]
        snapshot=guide['snapshot']['id']
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,160}',snapshot) or snapshot in snapshots:
            raise ValueError('Unsafe or duplicate snapshot identity')
        snapshots.add(snapshot)
        for file,data in bundle.files.items():
            captured='captured-guides/'+file
            if captured in outputs and outputs[captured]!=data:raise ValueError('Conflicting captured guide asset')
            outputs[captured]=data
        binding_file='bindings/'+snapshot+'.json';outputs[binding_file]=encode(binding)
        records.append({'guide':bundle.path,'guide_sha256':digest(bundle.files[bundle.path]),
                        'binding':binding_file,'binding_sha256':digest(outputs[binding_file]),
                        'breps':{name:'breps/'+entry['brep_sha256']+'.brep' for name,entry in binding['instances'].items()}})
    if not records:raise ValueError('At least one real captured guide is required')
    return records,outputs


def git(path,*args):return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--guides-root',type=Path,required=True)
    p.add_argument('--guide',action='append',required=True,help='Guide path relative to guides-root; may repeat')
    p.add_argument('--toolkit',type=Path,required=True)
    p.add_argument('--toolkit-revision',required=True,help='Independently reviewed immutable core revision')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--validate',action='store_true',help='Run the existing full native playback gate; detached bounded compute only')
    a=p.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{40}',a.toolkit_revision):raise ValueError('Immutable toolkit revision required')
    if git(a.toolkit,'rev-parse','HEAD')!=a.toolkit_revision or git(a.toolkit,'status','--porcelain'):
        raise ValueError('Exact clean reviewed playback toolkit required')
    if a.out.exists() or a.out.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
        raise ValueError('Fresh output outside source checkout required')
    raw=a.collection.read_bytes();collection=json.loads(raw);payloads=native_parts(collection,a.collection.parent)
    sys.path.insert(0,str(a.toolkit.resolve()/'software'))
    from cadagent.publish.guides import collect_guides
    from cadagent.review.gates.playback import bind_playback_breps
    import cadagent
    if not Path(cadagent.__file__).resolve().is_relative_to(a.toolkit.resolve()/'software/cadagent'):
        raise ValueError('Playback toolkit import escaped the reviewed checkout')
    bundles=collect_guides(a.guides_root.resolve(),a.guide)
    rows,outputs=bind_inputs(collection,digest(raw),bundles,payloads,bind_playback_breps)
    outputs['source-collection.json']=raw
    a.out.mkdir(parents=True)
    for file,data in outputs.items():
        path=a.out/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    receipt={'schema':'gyropup.robot-playback-inputs/1','collection_sha256':digest(raw),
             'source_commit':collection['source_commit'],'source_producer_inputs':collection['producer_inputs'],
             'original_hash_platform':collection['native_geometry']['hash_platform'],
             'playback_toolkit_revision':a.toolkit_revision,'adapter_sha256':sha(Path(__file__)),
             'guides_root':'captured-guides','collection':'source-collection.json',
             'guides':rows,'native_validation_requested':a.validate,
             'qualification':'Captured input identity only. No physical assembly, support, compliance, fastening or manufacturing qualification.'}
    (a.out/'inputs.json').write_bytes(encode(receipt))
    if a.validate:
        from cadagent.review.gates.playback import playback_gate
        reports=[];passed=True
        for bundle,row in zip(bundles,rows):
            binding=json.loads(outputs[row['binding']]);guide=json.loads(bundle.files[bundle.path])
            overview=guide['source'].get('overview_step_id');references=[overview] if overview else []
            order={key:value for key,value in guide['source']['install_order_by_step'].items() if key not in references}
            report=playback_gate(bundle,binding,{name:payloads[name] for name in binding['instances']},
                                 install_order_by_step=order,reference_step_ids=references)
            file='reports/'+guide['snapshot']['id']+'.json';dest=a.out/file;dest.parent.mkdir(exist_ok=True);dest.write_bytes(encode(report))
            reports.append({'guide':row['guide'],'report':file,'sha256':sha(dest),'pass':report.get('pass') is True})
            passed=passed and report.get('pass') is True
        (a.out/'reports.json').write_bytes(encode(reports))
        if not passed:
            print('Native playback has blocked or undecided paths; complete reports retained; no adoption')
            return 1
    print('Captured '+str(len(rows))+' native playback bindings; original BREP bytes preserved; no adoption')


if __name__=='__main__':raise SystemExit(main())
