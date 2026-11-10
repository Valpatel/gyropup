"""Bounded project pair study over original CAD; never an assembly planner.

The default writes a source-bound diagnostic plan without importing CAD. Native
execution is explicit and belongs inside the separately reviewed detached outer
phase/time/memory cap. A completed study can contain failures: blocked, seat,
unknown and unchecked results remain distinct and return nonzero.
"""
from __future__ import annotations
import argparse
import collections
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_data import inventory,sha,verify_frozen_inventory
from robot_native_playback import bind_inputs,digest,encode,git,ProgressWriter

BASELINE_CASES={stem+'-'+side for stem in (
    'motor-through-installed-hip','output-screws-after-upper','wheel-washers-outward-through-hub') for side in ('L','R')}
REVERSED_CASES={stem+'-'+side for stem in (
    'motor-wrong-inward-through-cheek','hip-wrong-inward-through-motor','inboard-bearing-inward-through-upper-eye') for side in ('L','R')}
CURRENT_CASES={stem+'-'+side for stem in (
    'hip-after-motor-outward','inboard-bearing-outward-through-shoulder','upper-after-output-screws',
    'wheel-washers-inward','circlip-outward-and-final-overlap') for side in ('L','R')}
CASE_IDS=BASELINE_CASES|REVERSED_CASES|CURRENT_CASES


def operations(guide,playback_operations):
    order={k:v for k,v in guide['source']['install_order_by_step'].items() if k!='overview'}
    return playback_operations(guide,order,('overview',))


def vector(value,size):
    return isinstance(value,list) and len(value)==size and all(type(v) in (int,float) and math.isfinite(v) for v in value)


def make_plan(guide,frames,witnesses,baseline,playback_operations,*,touch_mm=0.01):
    """Project the existing declared operations; retain every predecessor row.

    Axis-aligned CAD swept boxes are conservative exclusions for this finite
    straight translation only. A candidate or exclusion is not a native verdict.
    Diagnostics retain their declared current/baseline installed context; they
    do not replace the recipe or assert a whole historical assembly was checked.
    """
    if type(touch_mm) not in (int,float) or not math.isfinite(touch_mm) or touch_mm<0:
        raise ValueError('Invalid touch margin')
    boxes={row['instance']:row['cad_bounds_mm'] for row in frames}
    if len(boxes)!=len(frames) or any(not vector(b,6) or any(b[i]>b[i+3] for i in range(3)) for b in boxes.values()):
        raise ValueError('Invalid or duplicate CAD frame bounds')
    current=operations(guide,playback_operations);old=operations(baseline,playback_operations)
    by_name={op['instance']:op for op in current};old_by_name={op['instance']:op for op in old}
    if len(by_name)!=len(current) or set(by_name)!=set(boxes):raise ValueError('Frame/operation coverage mismatch')
    targets=sorted({row['moving'] for row in witnesses['candidate_pairs']})
    if not targets or set(targets)-set(by_name):raise ValueError('Unknown or empty changed-arrival scope')
    cases=witnesses['cases'];ids=[case['id'] for case in cases]
    if len(ids)!=len(set(ids)) or set(ids)-CASE_IDS:raise ValueError('Unreviewed or duplicate diagnostic case')
    queries={};rows=[];controls=[]
    def query(moving,fixed,offset,installed,context):
        if moving not in boxes or fixed not in boxes or moving==fixed or fixed not in installed or moving in installed:
            raise ValueError('Diagnostic obstacle is not installed in its declared context')
        if len(installed)!=len(set(installed)) or set(installed)-set(boxes) or not vector(offset,3):
            raise ValueError('Invalid pair context or offset')
        travel=math.sqrt(sum(c*c for c in offset))
        if not math.isfinite(travel) or travel<=0:raise ValueError('A finite nonzero translation is required')
        direction=[-c/travel for c in offset]
        identity={'moving':moving,'fixed':fixed,'offset_mm':list(offset),'direction':direction,
                  'travel_mm':travel,'installed_set':sorted(installed),'seat':True}
        key=digest(encode(identity))
        if key not in queries:queries[key]={'id':key,**identity,'contexts':[]}
        queries[key]['contexts'].append(context)
        return key
    for op_index,op in enumerate(current):
        moving=op['instance']
        if moving not in targets:continue
        offset=op['offset_mm'];box=boxes[moving]
        if not vector(offset,3):raise ValueError('Invalid authored offset')
        swept=[min(box[i],box[i]+offset[i%3]) if i<3 else max(box[i],box[i]+offset[i%3]) for i in range(6)]
        for other in op['installed']:
            obstacle=boxes[other]
            gaps=[max(obstacle[i]-swept[i+3],swept[i]-obstacle[i+3],0.0) for i in range(3)]
            candidate=max(gaps)<=touch_mm
            row={'moving':moving,'fixed':other,'offset_mm':list(offset),'step_id':op['step_id'],
                 'operation_index':op_index,'cad_swept_bounds_mm':swept,'fixed_cad_bounds_mm':obstacle,
                 'axis_gap_lower_bounds_mm':gaps,'candidate':candidate}
            if candidate:
                row['query']=query(moving,other,offset,op['installed'],{'kind':'candidate','step_id':op['step_id'],'operation_index':op_index})
            else:row['exclusion']='One CAD swept-box axis gap exceeds the unchanged touch margin'
            rows.append(row)
    for case in cases:
        ident=case['id'];basis='baseline' if ident in BASELINE_CASES else 'current'
        op=(old_by_name if basis=='baseline' else by_name).get(case['moving'])
        if op is None:raise ValueError('Diagnostic moving instance is absent from its source recipe')
        authored=op['offset_mm'];want=[-v for v in authored] if ident in REVERSED_CASES else authored
        if case['offset_mm']!=want:raise ValueError('Diagnostic offset does not match its declared authored/reversed source: '+ident)
        context={'kind':'diagnostic','case_id':ident,'basis':basis,'step_id':op['step_id'],
                 'reversed_authored_offset':ident in REVERSED_CASES}
        key=query(case['moving'],case['fixed'],case['offset_mm'],op['installed'],context)
        controls.append({**context,'query':key,'mesh_preterminal_witnesses':case['max_preterminal_witnesses'],
                         'mesh_terminal_witnesses':case['terminal_witnesses']})
    if not queries:raise ValueError('The selected pair study is empty')
    return {'schema':'gyropup.native-pair-study-plan/1','touch_mm':touch_mm,'moving_instances':targets,
            'predecessor_rows':rows,'candidate_rows':sum(r['candidate'] for r in rows),
            'excluded_rows':sum(not r['candidate'] for r in rows),'controls':controls,'queries':list(queries.values()),
            'limits':'Selected pair study only. Excluded CAD boxes and checked pairs do not qualify the assembly or its support.'}


def safe_file(root,name):
    if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Unsafe captured input path')
    path=root/name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Aliased captured input path')
    return path


def select_plan(plan,selection):
    """Select explicit immutable query identities; never invent or alter a path."""
    if (not isinstance(selection,dict) or selection.get('schema')!='gyropup.native-pair-selection/1'
        or selection.get('full_plan_sha256')!=digest(encode(plan))):
        raise ValueError('Selection does not bind the exact full plan')
    ids=selection.get('query_ids');queries={q['id']:q for q in plan['queries']}
    if (not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids)
        or len(ids)!=len(set(ids)) or any(i not in queries for i in ids)):
        raise ValueError('Selection requires unique known query IDs')
    cases=selection.get('case_ids')
    if cases is not None:
        if (not isinstance(cases,list) or len(cases)!=len(ids)
            or any(case not in [c.get('case_id') for c in queries[i]['contexts'] if c['kind']=='diagnostic']
                   for i,case in zip(ids,cases))):
            raise ValueError('Selection case label does not match its query identity')
    scope={'full_plan_sha256':selection['full_plan_sha256'],'full_query_count':len(queries),
           'selected_query_ids':ids[:],'unselected_query_ids':[i for i in queries if i not in ids]}
    return {**plan,'queries':[queries[i] for i in ids],'selection':scope}


def captured_inputs(root,manifest,report_sha,core):
    """Verify retained263 bytes and re-bind original payloads without CAD import."""
    actual=inventory(root);verify_frozen_inventory(actual,manifest,'frame bundle')
    inputs=json.loads((root/'inputs.json').read_text());row,=inputs['guides']
    collection_raw=(root/'source-collection.json').read_bytes();collection=json.loads(collection_raw)
    if digest(collection_raw)!=inputs['collection_sha256']:raise ValueError('Changed captured collection')
    bundles=core.collect_guides(root/'captured-guides',[row['guide']]);bundle,=bundles
    payloads={name:safe_file(root,file).read_bytes() for name,file in row['breps'].items()}
    rows,outputs=bind_inputs(collection,digest(collection_raw),bundles,payloads,core.bind_playback_breps)
    if rows!=[row] or outputs[row['binding']]!=safe_file(root,row['binding']).read_bytes():
        raise ValueError('Original captured binding no longer reproduces')
    guide=json.loads(bundle.files[bundle.path]);snapshot=guide['snapshot']['id']
    report_path=safe_file(root,'reports/'+snapshot+'.json')
    if sha(report_path)!=report_sha:raise ValueError('Changed accepted frame report')
    report=json.loads(report_path.read_text());binding=json.loads(outputs[row['binding']])
    if (report['gate']!='assembly-playback-preflight' or report['pass'] is not True or report['operations']
        or report['limits']['paths_checked'] is not False or report['limits']['progress_complete'] is not True
        or report['inputs']['guide_sha256']!=row['guide_sha256'] or report['inputs']['model_sha256']!=binding['model_sha256']
        or report['inputs']['source_commit']!=collection['source_commit']
        or report['inputs']['producer_hash_platform']!=binding['hash_platform']
        or set(f['instance'] for f in report['frames'])!=set(binding['instances'])):
        raise ValueError('A complete source-bound frame-only receipt is required')
    for case in core.witnesses['cases']+core.witnesses['candidate_pairs']:
        if any(binding['instances'][name]['mesh_sha256']!=value for name,value in case['mesh_sha256'].items()):
            raise ValueError('Pair evidence refers to different mesh bytes')
    return bundle,guide,binding,payloads,report


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.writing');temporary.write_bytes(encode(value));os.replace(temporary,path)


def execute_plan(plan,binding,payloads,frames,core,out,context,options):
    """Existing engine only; persist a recoverable prefix before each pair."""
    writer=ProgressWriter(out/'progress.jsonl',context)
    phase={'schema':'gyropup.native-pair-study-phase/1','state':'running','phase':'load','completed_pairs':0,
           'total_pairs':len(plan['queries']),'progress_flushed_records':0,'progress_fsync_acknowledged_records':0,
           'progress_tail_uncertain':True}
    report={'schema':'gyropup.native-pair-study/1','complete':False,'pass':False,'inputs':context,'queries':[],
            'all_assembly_paths_checked':False,'support_stability_verified':False,'physical_assembly_verified':False,
            'limits':'Finite selected pair probes, using unchanged native engine/tolerances. A seat result checks no transient path. No geometry repair or overlap exemptions.'}
    if 'selection' in plan:report['selection']=plan['selection']
    primary=None;world=None
    try:
        write_json(out/'phase.json',phase);write_json(out/'report.json',report)
        world=core.load_world(binding,payloads,core.tol,writer)
        if set(world.names)!=set(f['instance'] for f in frames):raise ValueError('Loaded world coverage changed')
        for f in frames:
            if max(abs(a-b) for a,b in zip(world.box(f['instance']),f['cad_bounds_mm']))>1e-7:
                raise ValueError('Loaded CAD differs from accepted frame: '+f['instance'])
        phase['phase']='pairs'
        for index,query in enumerate(plan['queries']):
            event={'schema':'cad-agent.playback-progress/1','event':'pair','operation_index':index,
                   'instance':query['moving'],'obstacle':query['fixed'],'pair_index':index,
                   'project_study':{'query_id':query['id'],'contexts':query['contexts']}}
            phase['current_query']=query['id'];write_json(out/'phase.json',phase)
            writer({**event,'state':'starting'})
            try:
                result=core.sweep_pair(world,query['moving'],tuple(query['direction']),query['fixed'],
                                       options=options,tol=core.tol,seat=True,travel_mm=query['travel_mm'])
            except Exception as exc:result={'part':query['fixed'],'state':'unknown','error':type(exc).__name__+': '+str(exc)}
            if result.get('state') not in ('clear','blocked','seat','unknown','unchecked'):
                raise ValueError('Unexpected core pair state')
            writer({**event,'state':'complete','result':result})
            report['queries'].append({'id':query['id'],'result':result,
                                      'transient_path_complete':result['state']=='clear','terminal_only':result['state']=='seat'})
            phase.update(completed_pairs=len(report['queries']),progress_flushed_records=writer.count,
                         progress_fsync_acknowledged_records=writer.synced)
            write_json(out/'report.json',report);write_json(out/'phase.json',phase)
        report['complete']=True;report['world_stats']=world.stats
    except BaseException as exc:
        primary=exc;report['error']=type(exc).__name__+': '+str(exc)
    finally:
        error=writer.finish()
        if error is not None:
            report['complete']=False;report['progress_error']=type(error).__name__+': '+str(error)
            if primary is None:primary=error;report['error']=report['progress_error']
        if world is not None:report['world_stats']=world.stats
        report['unchecked_queries']=[q['id'] for q in plan['queries'][len(report['queries']):]]
        report['counts']=dict(collections.Counter(q['result']['state'] for q in report['queries']))
        report['pass']=report['complete'] and all(q['result']['state']=='clear' for q in report['queries'])
        phase.update(state='complete' if report['complete'] else 'incomplete',gate_pass=report['pass'],
                     progress_flushed_records=writer.count,progress_fsync_acknowledged_records=writer.synced,
                     progress_tail_uncertain=writer.error is not None)
        for path,value in ((out/'report.json',report),(out/'phase.json',phase)):
            try:write_json(path,value)
            except BaseException as exc:
                report['complete']=False;report['pass']=False;phase['state']='incomplete';phase['gate_pass']=False
                if primary is None:primary=exc
        if primary is not None:
            report['complete']=False;report['pass']=False;report.setdefault('error',type(primary).__name__+': '+str(primary))
            phase['state']='incomplete';phase['gate_pass']=False
            for path,value in ((out/'report.json',report),(out/'phase.json',phase)):
                try:write_json(path,value)
                except BaseException:pass # Preserve the primary error and existing progress prefix.
    if primary is not None:raise primary
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frame-bundle',type=Path,required=True);p.add_argument('--frame-manifest',type=Path,required=True)
    p.add_argument('--frame-manifest-sha',required=True);p.add_argument('--frame-report-sha',required=True)
    p.add_argument('--witnesses',type=Path,required=True);p.add_argument('--witnesses-sha',required=True)
    p.add_argument('--baseline-guide',type=Path,required=True);p.add_argument('--toolkit',type=Path,required=True)
    p.add_argument('--toolkit-revision',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--query-selection',type=Path,help='Explicit SHA-bound query subset; the full plan remains retained')
    p.add_argument('--query-selection-sha')
    p.add_argument('--execute',action='store_true');p.add_argument('--max-samples',type=int,default=256)
    a=p.parse_args(argv);os.umask(0o077)
    if bool(a.query_selection)!=bool(a.query_selection_sha):p.error('Selection file and SHA must be supplied together')
    if not 1<=a.max_samples<=5000:p.error('--max-samples must be in 1..5000')
    if not re.fullmatch('[0-9a-f]{40}',a.toolkit_revision):raise ValueError('Immutable reviewed core revision required')
    if git(a.toolkit,'rev-parse','HEAD')!=a.toolkit_revision or git(a.toolkit,'status','--porcelain'):
        raise ValueError('Exact clean reviewed core required')
    if a.out.exists() or a.out.resolve().is_relative_to(Path(__file__).resolve().parents[3]):raise ValueError('Fresh external output required')
    if sha(a.frame_manifest)!=a.frame_manifest_sha or sha(a.witnesses)!=a.witnesses_sha:raise ValueError('Changed sealed study input')
    witnesses=json.loads(a.witnesses.read_text());baseline_raw=a.baseline_guide.read_bytes()
    if digest(baseline_raw)!=witnesses['baseline_guide_sha256']:raise ValueError('Changed source baseline guide')
    sys.path.insert(0,str(a.toolkit.resolve()/'software'))
    import cadagent
    if not Path(cadagent.__file__).resolve().is_relative_to(a.toolkit.resolve()/'software/cadagent'):raise ValueError('Core import escaped pin')
    from cadagent.publish.guides import collect_guides
    from cadagent.review.gates import playback
    from types import SimpleNamespace
    core=SimpleNamespace(collect_guides=collect_guides,bind_playback_breps=playback.bind_playback_breps,witnesses=witnesses)
    manifest=json.loads(a.frame_manifest.read_text())
    bundle,guide,binding,payloads,frame=captured_inputs(a.frame_bundle,manifest,a.frame_report_sha,core)
    plan=make_plan(guide,frame['frames'],witnesses,json.loads(baseline_raw),playback.playback_operations)
    query_plan=plan;selection_raw=None
    if a.query_selection:
        selection_raw=a.query_selection.read_bytes()
        if digest(selection_raw)!=a.query_selection_sha:raise ValueError('Changed query selection bytes')
        query_plan=select_plan(plan,json.loads(selection_raw))
    context={'emitter':'Gyropup selected pair study; results from existing core sweep_pair',
             'frame_manifest_sha256':a.frame_manifest_sha,'frame_report_sha256':a.frame_report_sha,
             'guide_sha256':digest(bundle.files[bundle.path]),'binding_sha256':digest(encode(binding)),
             'witnesses_sha256':a.witnesses_sha,'baseline_guide_sha256':digest(baseline_raw),
             'adapter_sha256':sha(Path(__file__)),'core_revision':a.toolkit_revision,'max_samples':a.max_samples,
             'max_step_mm':1.0,'outer_time_cap':'Required separately reviewed detached phase; this process does not impose a native per-pair timer.'}
    a.out.mkdir(mode=0o700,parents=True)
    for name in manifest:
        target=a.out/'inputs'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe_file(a.frame_bundle,name),target)
    (a.out/'witnesses.json').write_bytes(a.witnesses.read_bytes());(a.out/'baseline-guide.json').write_bytes(baseline_raw)
    write_json(a.out/'plan.json',plan);context['plan_sha256']=sha(a.out/'plan.json');write_json(a.out/'source.json',context)
    if selection_raw is not None:
        (a.out/'selection.json').write_bytes(selection_raw);write_json(a.out/'query-plan.json',query_plan)
        context.update(selection_sha256=digest(selection_raw),query_plan_sha256=sha(a.out/'query-plan.json'),
                       full_plan_query_count=len(plan['queries']),selected_query_ids=query_plan['selection']['selected_query_ids'])
        write_json(a.out/'source.json',context)
    if not a.execute:
        print('Prepared '+str(len(query_plan['queries']))+' of '+str(len(plan['queries']))+' finite pair probes; no CAD imported or queried');return 0
    from cadagent.review.gates.assembly import AccessOptions,sweep_pair
    from cadagent.review.gates.relations import Tolerances
    core.load_world=playback._load_world;core.sweep_pair=sweep_pair;core.tol=Tolerances()
    if core.tol.touch_mm!=plan['touch_mm']:raise ValueError('Native touch margin differs from the bound exclusion plan')
    report=execute_plan(query_plan,binding,payloads,frame['frames'],core,a.out,context,AccessOptions(max_samples=a.max_samples))
    print('Selected pair study '+('complete' if report['complete'] else 'incomplete')+'; '+json.dumps(report['counts'])+'; no assembly qualification')
    return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())
