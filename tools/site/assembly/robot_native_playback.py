"""Bind original robot BREP bytes to captured guides using the existing CAD gate.

Import-safe binding/serialization only by default. Native playback validation is
an explicit separate option for the reviewed detached compute procedure. This
module never imports project CAD, repairs geometry, invents a path or grants a
manufacturing/physical assembly release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import inspect
import os
from pathlib import Path
import re
import posixpath
from urllib.parse import unquote
import subprocess
import sys
import time
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


class ProgressWriter:
    """Flushed source-bound JSONL; storage failures are never silently ignored."""
    def __init__(self,path,context):
        self.stream=Path(path).open('x');self.context=context;self.count=0;self.synced=0
        self.started=time.monotonic();self.error=None

    def __call__(self,event):
        try:
            if not isinstance(event,dict) or event.get('schema')!='cad-agent.playback-progress/1':
                raise ValueError('Unexpected core progress protocol')
            record={'schema':'gyropup.native-playback-progress/1','sequence':self.count+1,
                    'validation_elapsed_s':time.monotonic()-self.started,'inputs':self.context,'core_event':event}
            self.stream.write(json.dumps(record,allow_nan=False)+'\n');self.stream.flush();self.count+=1
            # Every event reaches the OS. Checkpoint file data without forcing
            # tens of thousands of synchronous writes during a full pair sweep.
            if self.count%128==0 or event.get('event') in ('operation','preflight') and event.get('state')=='complete':
                os.fsync(self.stream.fileno());self.synced=self.count
        except Exception as exc:
            self.error=exc
            raise

    def finish(self):
        previous=self.synced;failed=self.error is not None
        try:
            self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
            if not failed:self.synced=self.count
        except Exception as exc:
            self.synced=previous
            if self.error is None:self.error=exc
            try:self.stream.close()
            except Exception:pass
        return self.error


def native_report(out,bundle,row,binding,payloads,gate,*,preflight_only,core_revision,options=None):
    """Persist a phase and progress prefix even if native work cannot finish."""
    guide=json.loads(bundle.files[bundle.path]);snapshot=guide['snapshot']['id']
    progress_file='progress/'+snapshot+'.jsonl';phase_file='reports/'+snapshot+'.phase.json'
    report_file='reports/'+snapshot+'.json';phase_path=out/phase_file
    (out/'progress').mkdir(exist_ok=True);phase_path.parent.mkdir(exist_ok=True)
    context={'source_commit':guide['snapshot']['source_commit'],'guide_sha256':row['guide_sha256'],
             'binding_sha256':row['binding_sha256'],'core_revision':core_revision,
             'mode':'preflight' if preflight_only else 'paths'}
    phase={'schema':'gyropup.native-playback-phase/1','state':'running','inputs':context,
           'progress':progress_file,'report':report_file,'progress_flushed_records':0,
           'progress_fsync_acknowledged_records':0,
           'progress_tail_uncertain':True,
           'writer_policy':{'flush_each_record':True,'fsync_every_records':128,
                            'fsync_completed_operations_and_preflight':True}}
    phase_path.write_bytes(encode(phase));writer=None;error=None;report=None;started=time.monotonic()
    try:
        parameters=inspect.signature(gate).parameters
        if not {'preflight_only','on_progress'}.issubset(parameters):
            raise ValueError('Selected core lacks the reviewed native preflight/progress protocol')
        writer=ProgressWriter(out/progress_file,context)
        overview=guide['source'].get('overview_step_id');references=[overview] if overview else []
        order={key:value for key,value in guide['source']['install_order_by_step'].items() if key not in references}
        settings={'options':options} if options is not None else {}
        report=gate(bundle,binding,{name:payloads[name] for name in binding['instances']},
                    install_order_by_step=order,reference_step_ids=references,
                    preflight_only=preflight_only,on_progress=writer,**settings)
        (out/report_file).write_bytes(encode(report))
        if preflight_only and (report.get('gate')!='assembly-playback-preflight'
                               or report.get('limits',{}).get('paths_checked') is not False):
            raise ValueError('Core preflight must remain distinct from a path verdict')
    except BaseException as exc:error=exc
    finally:
        if writer is not None:
            storage_error=writer.finish()
            if error is None:error=storage_error
            phase.update(progress_flushed_records=writer.count,
                         progress_fsync_acknowledged_records=writer.synced,
                         progress_tail_uncertain=writer.error is not None or writer.synced<writer.count)
        phase.update(wall_seconds=time.monotonic()-started,
                     state='complete' if error is None and report and report.get('limits',{}).get('progress_complete') is True else 'incomplete',
                     gate_pass=report.get('pass') is True if report else False)
        if error is not None:phase['error']=type(error).__name__+': '+str(error)
        try:phase_path.write_bytes(encode(phase))
        except BaseException:
            if error is None:raise
    if error is not None:raise error
    complete=phase['state']=='complete'
    return {'guide':row['guide'],'report':report_file,'sha256':sha(out/report_file),
            'phase':phase_file,'phase_sha256':sha(phase_path),'progress':progress_file,
            'progress_sha256':sha(out/progress_file),'complete':complete,
            'pass':complete and report.get('pass') is True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--guides-root',type=Path,required=True)
    p.add_argument('--guide',action='append',required=True,help='Guide path relative to guides-root; may repeat')
    p.add_argument('--toolkit',type=Path,required=True)
    p.add_argument('--toolkit-revision',required=True,help='Independently reviewed immutable core revision')
    p.add_argument('--out',type=Path,required=True)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--validate',action='store_true',help='Run finite native paths with recoverable progress; detached bounded compute only')
    modes.add_argument('--preflight-only',action='store_true',help='Read native shapes/world frames only; checks no insertion paths')
    p.add_argument('--max-samples',type=int,help='Explicit existing-core per-pair sample cap; exhaustion remains unchecked')
    a=p.parse_args(argv)
    if a.max_samples is not None and (a.max_samples<1 or a.max_samples>5000 or not (a.validate or a.preflight_only)):
        p.error('--max-samples needs a native mode and a value in 1..5000')
    os.umask(0o077)
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
    a.out.mkdir(parents=True,mode=0o700)
    for file,data in outputs.items():
        path=a.out/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    receipt={'schema':'gyropup.robot-playback-inputs/1','collection_sha256':digest(raw),
             'source_commit':collection['source_commit'],'source_producer_inputs':collection['producer_inputs'],
             'original_hash_platform':collection['native_geometry']['hash_platform'],
             'playback_toolkit_revision':a.toolkit_revision,'adapter_sha256':sha(Path(__file__)),
             'guides_root':'captured-guides','collection':'source-collection.json',
             'guides':rows,'native_validation_requested':a.validate or a.preflight_only,
             'native_mode':'preflight' if a.preflight_only else 'paths' if a.validate else 'binding-only',
             'max_samples':a.max_samples,
             'qualification':'Captured input identity only. No physical assembly, support, compliance, fastening or manufacturing qualification.'}
    (a.out/'inputs.json').write_bytes(encode(receipt))
    if a.validate or a.preflight_only:
        from cadagent.review.gates.playback import playback_gate
        options=None
        if a.max_samples is not None:
            from cadagent.review.gates.assembly import AccessOptions
            options=AccessOptions(max_samples=a.max_samples)
        reports=[];passed=True
        for bundle,row in zip(bundles,rows):
            binding=json.loads(outputs[row['binding']])
            result=native_report(a.out,bundle,row,binding,payloads,playback_gate,
                                 preflight_only=a.preflight_only,core_revision=a.toolkit_revision,options=options)
            reports.append(result);passed=passed and result['pass']
            (a.out/'reports.json').write_bytes(encode(reports))
        if not passed:
            print('Native playback has blocked or undecided checks; complete/partial evidence retained; no adoption')
            return 1
        if a.preflight_only:print('Native frame preflight completed; insertion paths were not checked')
    print('Captured '+str(len(rows))+' native playback bindings; original BREP bytes preserved; no adoption')


if __name__=='__main__':raise SystemExit(main())
