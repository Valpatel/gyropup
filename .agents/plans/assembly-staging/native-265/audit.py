"""Pure artifact/protocol audit of the explicit native control study."""
from pathlib import Path
import collections,hashlib,json,stat,sys,tarfile
fetch=Path(sys.argv[1]);repo=Path(sys.argv[2]);out=fetch/'out';base=out/'control-pair-study'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();digest=lambda b:hashlib.sha256(b).hexdigest()
final=read(out/'final-result.json');assert final['status']=='COMPLETE_SCOPED_NATIVE_CONTROL_STUDY'
assert final['source']=='05bf810d245ca1b938f9283a10dde624ed2104ba' and final['core']=='5c29c9e2abf2562baa72a05248f23de054b8241e'
assert final['input_job']==261 and final['frame_job']==263 and final['adoption_approved'] is False
assert len(final['guards'])==10 and all(final['guards'].values()) and not final['errors'] and final['processes_quiescent']
assert len(final['phases'])==6 and final['phases']['native-controls']['timeout_seconds']==120
assert all(p['exit']==0 and p['process_cleanup']['group_gone'] and not p.get('timed_out') for p in final['phases'].values())
for role in ('runtime','toolkit','candidate','guides','frame-input','input-seals','hardware','tracked','playback-core'):
 assert read(out/(role+'-before.json'))==read(out/(role+'-after.json')),role
for role in ('candidate','guides'):
 original=read(repo/'.agents/plans/assembly-staging/native-261'/(role+'-members.json'));actual=read(out/(role+'-before.json'))
 assert original.keys()==actual.keys() and all(original[n]['mode']==0o600 and actual[n]=={**original[n],'mode':0o640} for n in original)
frame_members=read(repo/'.agents/plans/assembly-staging/native-263/frame-members.json');actual=read(out/'frame-input-before.json')
assert frame_members.keys()==actual.keys() and all(frame_members[n]['mode']==0o600 and actual[n]=={**frame_members[n],'mode':0o640} for n in actual)
archive=out/'control-pair-study-produced.tgz';members=read(out/'control-pair-study-members.json');assert sha(archive)==final['control_archive_sha256'];seen=set()
with tarfile.open(archive) as tar:
 for m in tar:
  assert m.isfile() and m.name not in seen and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
  payload=tar.extractfile(m).read();assert members[m.name]=={'sha256':digest(payload),'bytes':len(payload),'mode':m.mode} and m.mode==0o600
  path=base/m.name;assert not path.is_symlink() and path.read_bytes()==payload and stat.S_IMODE(path.stat().st_mode)==0o640
  seen.add(m.name)
actual_names=set()
for p in base.rglob('*'):
 mode=p.lstat().st_mode
 if stat.S_ISDIR(mode):continue
 assert stat.S_ISREG(mode);actual_names.add(p.relative_to(base).as_posix())
assert seen==set(members)==actual_names
for name,row in frame_members.items():assert sha(base/'inputs'/name)==row['sha256'] and (base/'inputs'/name).stat().st_size==row['bytes']
full=read(base/'plan.json');query_plan=read(base/'query-plan.json');selection=read(base/'selection.json');source=read(base/'source.json');report=read(base/'report.json');phase=read(base/'phase.json');actual_exit=read(base/'native-cli-exit.json')
canonical=repo/'.agents/plans/assembly-staging'
for file,expected in [('plan.json',canonical/'pair-study/plan.json'),('selection.json',canonical/'control-pair-study/selection.json'),('source.json',canonical/'control-pair-study/plan-source.json')]:assert (base/file).read_bytes()==expected.read_bytes()
assert sha(base/'plan.json')==source['plan_sha256']=='1316f2e4e315ee2cd45ed805d92ee219699a311bf09bb8d106148145fb8a96cc'
assert sha(base/'query-plan.json')==source['query_plan_sha256']=='c8c2f01464bd49f5cd464637b277032efe761fb3e76cd216e8c146ded25d3cc6'
assert sha(base/'selection.json')==source['selection_sha256']=='ecb26e9ddd47a023664447e4078dbc34bd960e5b19c0194dfcf631503ec2a945'
assert source['adapter_sha256']=='68712d70f24061fa65e433576619318eec201d1cb6c3d4632d911a3f4295c712' and source['core_revision']==final['core']
assert source['max_samples']==256 and source['max_step_mm']==1.0
assert len(full['predecessor_rows'])==1126 and full['candidate_rows']==74 and full['excluded_rows']==1052 and len(full['queries'])==90
ids=selection['query_ids'];assert ids==source['selected_query_ids']==final['selected_query_ids'] and len(ids)==2
original={q['id']:q for q in full['queries']};assert query_plan['queries']==[original[i] for i in ids]
for k,v in full.items():
 if k!='queries':assert query_plan[k]==v
scope=query_plan['selection'];assert scope['full_plan_sha256']==source['plan_sha256'] and scope['full_query_count']==90
assert scope['selected_query_ids']==ids and len(scope['unselected_query_ids'])==88 and set(scope['unselected_query_ids'])==set(original)-set(ids)
for q in query_plan['queries']:
 identity={k:q[k] for k in ('moving','fixed','offset_mm','direction','travel_mm','installed_set','seat')}
 assert digest((json.dumps(identity,indent=2,allow_nan=False)+'\n').encode())==q['id']
prior=read(canonical/'native-264/report.json');prior_ids={q['id'] for q in prior['queries']};assert len(prior_ids)==42 and prior_ids.isdisjoint(ids)
assert read(out/'selection-preflight.json')['selected_previously_completed'] is False
assert report['inputs']==source and report['selection']==scope and report['complete'] is True and report['pass'] is False
assert [q['id'] for q in report['queries']]==ids and report['unchecked_queries']==[]
assert report['all_assembly_paths_checked'] is False and report['support_stability_verified'] is False and report['physical_assembly_verified'] is False
counts=dict(collections.Counter(q['result']['state'] for q in report['queries']));assert counts==report['counts']=={'blocked':2}
assert actual_exit['actual_native_exit']==1 and phase['state']=='complete' and phase['gate_pass'] is False
assert phase['total_pairs']==phase['completed_pairs']==2 and phase['progress_tail_uncertain'] is False
raw=(base/'progress.jsonl').read_bytes();assert raw.endswith(b'\n');events=[json.loads(line) for line in raw.splitlines()]
assert len(events)==472 and [e['sequence'] for e in events]==list(range(1,473)) and all(e['inputs']==source for e in events)
assert phase['progress_flushed_records']==phase['progress_fsync_acknowledged_records']==472
for state in ('starting','complete'):
 pairs=[e['core_event'] for e in events if e['core_event']['event']=='pair' and e['core_event']['state']==state]
 assert len(pairs)==2 and [e['project_study']['query_id'] for e in pairs]==ids
 for i,e in enumerate(pairs):
  q=query_plan['queries'][i];assert e['instance']==q['moving'] and e['obstacle']==q['fixed'] and e['project_study']['contexts']==q['contexts']
  if state=='complete':assert e['result']==report['queries'][i]['result']
for state in ('starting','complete'):
 names=[e['core_event']['instance'] for e in events if e['core_event'].get('phase')=='load' and e['core_event'].get('state')==state]
 assert len(names)==233 and len(set(names))==233
assert not any(e['core_event']['event']=='operation' for e in events)
hits=[]
for row,q,label in zip(report['queries'],query_plan['queries'],selection['case_ids']):
 r=row['result'];assert r['part']==q['fixed'] and r['travel_mm']==q['travel_mm']==60 and r['state']=='blocked'
 assert r['first_contact_mm']==[None,60.0] and r['overlap_mm3']>0 and r['samples']==2
 assert row['transient_path_complete'] is False and row['terminal_only'] is False
 hits.append({'case_id':label,'query_id':q['id'],'moving':q['moving'],'fixed':q['fixed'],'offset_mm':q['offset_mm'],
              'direction':q['direction'],'travel_mm':q['travel_mm'],'result':r})
combined={q['id']:q['result'] for q in prior['queries']};combined.update({q['id']:q['result'] for q in report['queries']})
summary={'schema':'gyropup.native-control-artifact-audit/1','date':'2026-11-10','job':265,'artifact_audit_pass':True,
 'execution_complete':True,'geometry_pass':False,'source':final['source'],'core':final['core'],'input_job':261,'frame_job':263,
 'archive_sha256':sha(archive),'archive_and_actual_files':len(seen),'preserved_original_input_files':len(frame_members),
 'all10_preservation_guards_pass':True,'all_child_groups_gone':True,'native_phase_seconds':final['phases']['native-controls']['seconds'],
 'actual_native_cli_exit':1,'selected_queries':2,'counts':counts,'unselected_full_plan_queries':88,'progress_records':472,
 'flushed_records':472,'file_fsync_acknowledged_records':472,'progress_tail_uncertain':False,'hits':hits,
 'motor_geometry_basis':'Source body_frame.legs collects the motors as envelopes; these checks are CAD/viewer path evidence, not measured hardware fit.','world_stats':report['world_stats'],'combined264_265_observed_queries':len(combined),
 'combined_counts':dict(collections.Counter(r['state'] for r in combined.values())),
 'combined_full_plan_queries_without_completed_record':len(full['queries'])-len(combined),
 'all_assembly_paths_checked':False,'support_stability_verified':False,'physical_assembly_verified':False,
 'limits':'Both controls are already intersecting at the authored60mm start pose; null/60 gives no last-clear/contact-onset bracket. Only two explicit probes complete. Combined44/90 coverage preserves distinct execution/source identities and leaves46 queries without completed results. No whole sequence, continuous clearance or physical/manufacturing approval.',
 'seals':{name:sha(base/name) for name in ('plan.json','query-plan.json','selection.json','source.json','report.json','phase.json','progress.jsonl','native-cli-exit.json')}}
print(json.dumps(summary,indent=2))
