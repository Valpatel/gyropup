"""Audit the observed capped pair prefix without performing CAD queries."""
from pathlib import Path
import collections,hashlib,json,stat,sys,tarfile
fetch=Path(sys.argv[1]);repo=Path(sys.argv[2]);out=fetch/'out';base=out/'pair-study'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
final=read(out/'final-result.json');assert final['source']=='542b9a40396845708139e95e6b77f4a4e975fb36'
assert final['core']=='5c29c9e2abf2562baa72a05248f23de054b8241e' and final['status']=='FAILED_OR_INCOMPLETE_NATIVE_PAIR_STUDY'
assert final['input_job']==261 and final['frame_job']==263 and final['paths_requested'] is True and final['adoption_approved'] is False
assert len(final['guards'])==10 and all(final['guards'].values()) and final['errors']==[] and final['processes_quiescent']
assert final['phases']['native-pairs']['timed_out'] is True and final['phases']['native-pairs']['timeout_seconds']==300
assert final['phases']['native-pairs']['process_cleanup']['group_gone']
assert all(p['process_cleanup']['group_gone'] for p in final['phases'].values())
for role in ('runtime','toolkit','candidate','guides','frame-input','input-seals','hardware','tracked','playback-core'):
 assert read(out/(role+'-before.json'))==read(out/(role+'-after.json')),role
for role in ('candidate','guides'):
 producer=read(repo/'.agents/plans/assembly-staging/native-261'/(role+'-members.json'));actual=read(out/(role+'-before.json'))
 assert actual.keys()==producer.keys() and all(producer[n]['mode']==0o600 and actual[n]=={**producer[n],'mode':0o640} for n in producer)
frame_members=read(repo/'.agents/plans/assembly-staging/native-263/frame-members.json');actual=read(out/'frame-input-before.json')
assert frame_members.keys()==actual.keys() and all(frame_members[n]['mode']==0o600 and actual[n]=={**frame_members[n],'mode':0o640} for n in actual)
archive=out/'pair-study-produced.tgz';members=read(out/'pair-study-members.json')
assert sha(archive)==final['pair_archive_sha256'];seen=set()
with tarfile.open(archive) as tar:
 for item in tar:
  assert item.isfile() and item.name not in seen and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
  data=tar.extractfile(item).read();entry={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'mode':item.mode}
  assert entry==members[item.name] and item.mode==0o600
  path=base/item.name;assert not path.is_symlink() and path.read_bytes()==data and stat.S_IMODE(path.stat().st_mode)==0o640
  seen.add(item.name)
actual_names=set()
for path in base.rglob('*'):
 mode=path.lstat().st_mode
 if stat.S_ISDIR(mode):continue
 assert stat.S_ISREG(mode);actual_names.add(path.relative_to(base).as_posix())
assert seen==set(members)==actual_names
for name,row in frame_members.items():
 copied=base/'inputs'/name;assert sha(copied)==row['sha256'] and copied.stat().st_size==row['bytes']
canonical=repo/'.agents/plans/assembly-staging/pair-study'
for actual,source in [('plan.json','plan.json'),('source.json','plan-source.json'),('baseline-guide.json','baseline-guide.json')]:
 assert (base/actual).read_bytes()==(canonical/source).read_bytes()
assert (base/'witnesses.json').read_bytes()==(repo/'.agents/plans/assembly-staging/arrival-witnesses.json').read_bytes()
plan=read(base/'plan.json');source=read(base/'source.json');phase=read(base/'phase.json');report=read(base/'report.json')
assert sha(base/'plan.json')=='1316f2e4e315ee2cd45ed805d92ee219699a311bf09bb8d106148145fb8a96cc'==source['plan_sha256']
assert source['adapter_sha256']=='63f7093468ba1ba2ab1063dcbac5e5fddb7331346a1eb6c8c4c287e87794b016' and source['core_revision']==final['core']
assert source['max_samples']==256 and source['max_step_mm']==1.0
assert len(plan['predecessor_rows'])==1126 and plan['candidate_rows']==74 and plan['excluded_rows']==1052 and len(plan['controls'])==22 and len(plan['queries'])==90
assert report['complete'] is False and report['pass'] is False and phase['state']=='running' and phase['progress_tail_uncertain'] is True
assert report['all_assembly_paths_checked'] is False and report['physical_assembly_verified'] is False and report['support_stability_verified'] is False
raw=(base/'progress.jsonl').read_bytes();events=[];tail=b''
for line in raw.splitlines(keepends=True):
 if not line.endswith(b'\n'):tail=line;break
 events.append(json.loads(line))
assert [e['sequence'] for e in events]==list(range(1,len(events)+1)) and all(e['inputs']==source for e in events)
assert all(e['schema']=='gyropup.native-playback-progress/1' for e in events)
queries=plan['queries'];lookup={q['id']:q for q in queries}
completed=[];started=[]
for event in events:
 e=event['core_event']
 if e['event']=='pair':
  qid=e['project_study']['query_id'];q=lookup[qid]
  assert e['instance']==q['moving'] and e['obstacle']==q['fixed'] and e['project_study']['contexts']==q['contexts']
  index=e['pair_index'];assert queries[index]['id']==qid and e['operation_index']==index
  if e['state']=='starting':started.append(qid)
  elif e['state']=='complete':
   assert started[-1]==qid and len(started)==len(completed)+1;completed.append({'id':qid,'result':e['result']})
  else:raise ValueError('Unknown pair state')
assert [q['id'] for q in completed]==[q['id'] for q in queries[:len(completed)]]
assert started==[q['id'] for q in queries[:len(started)]] and len(started)==len(completed)+1
assert phase['current_query']==started[-1] and phase['completed_pairs']==len(completed)
assert len(report['queries'])==len(completed)
for row,observed in zip(report['queries'],completed):
 assert row['id']==observed['id'] and row['result']==observed['result']
 state=row['result']['state'];assert row['transient_path_complete']==(state=='clear') and row['terminal_only']==(state=='seat')
assert phase['progress_fsync_acknowledged_records']<=phase['progress_flushed_records']<=len(events)
assert not (base/'native-cli-exit.json').exists() and 'unchecked_queries' not in report
pending=[q['id'] for q in queries[len(completed):]];observed={q['id']:q['result'] for q in completed}
counts=dict(collections.Counter(q['result']['state'] for q in completed))
seats=[{'query_id':r['id'],'moving':lookup[r['id']]['moving'],'fixed':lookup[r['id']]['fixed'],**r['result']} for r in completed if r['result']['state']=='seat']
controls=[{**c,'observed_state':observed[c['query']]['state'] if c['query'] in observed else None} for c in plan['controls']]
positive_lower_bounds=sum(q['result']['state']=='clear' and (q['result'].get('gap_lower_bound_mm') or 0)>0 for q in completed)
summary={'schema':'gyropup.native-pair-prefix-audit/1','job':264,'date':'2026-11-10','artifact_audit_pass':True,
 'native_study_complete':False,'source':final['source'],'core':final['core'],'input_job':261,'frame_job':263,
 'archive_sha256':sha(archive),'archive_and_actual_files':len(seen),'preserved_input_files':len(frame_members),
 'all10_preservation_guards_pass':True,'all_child_groups_gone':True,'native_phase_cap_seconds':300,
 'observed_completed_pairs':len(completed),'observed_pair_counts':counts,'positive_gap_lower_bound_clear_pairs':positive_lower_bounds,
 'total_planned_queries':len(queries),'uncompleted_queries_derived_from_plan':pending,'interrupted_query_id':started[-1],
 'not_started_query_count':len(queries)-len(started),'observed_progress_records':len(events),'trailing_unparsed_progress_bytes':len(tail),
 'phase_flushed_records':phase['progress_flushed_records'],'phase_file_fsync_acknowledged_records':phase['progress_fsync_acknowledged_records'],
 'tail_uncertain':True,'final_unchecked_field_absent':True,'actual_native_cli_exit_unobserved':True,
 'terminal_seat_rows':seats,'diagnostic_contexts':controls,'observed_sample_count_sum':sum(q['result'].get('samples',0) for q in completed),
 'complete_world_stats_unavailable':True,'all_assembly_paths_checked':False,'physical_assembly_verified':False,'support_stability_verified':False,
 'limits':'Observed complete records in a retained interrupted prefix only. No verdict for the interrupted or unstarted48 queries. Terminal seat rows check no transient path; clear finite samples/bounds do not qualify physical assembly or continuous clearance.',
 'seals':{name:sha(base/name) for name in ('plan.json','source.json','report.json','phase.json','progress.jsonl')}}
print(json.dumps(summary,indent=2))
