from pathlib import Path
import collections, hashlib, json, stat, tarfile, sys

p=Path(sys.argv[1])/'out'
b=p/'pair-study'
load=lambda f:json.loads(f.read_bytes())
sha=lambda x:hashlib.sha256(x).hexdigest()
f=load(p/'final-result.json'); manifest=load(p/'pair-study-members.json')
assert f['status']=='FAILED_OR_INCOMPLETE_NATIVE_PAIR_STUDY' and not f['adoption_approved']
assert f['source']=='542b9a40396845708139e95e6b77f4a4e975fb36'
assert f['core']=='5c29c9e2abf2562baa72a05248f23de054b8241e'
assert f['recipe_sha256']=='f243cff65a834e0368ffad6f1d38b954849c41309cdb9cdf83f5a1531a9651c4'
assert len(f['guards'])==10 and all(f['guards'].values()) and not f['errors'] and f['processes_quiescent']
assert f['phases']['native-pairs']['timed_out'] and f['phases']['native-pairs']['timeout_seconds']==300
assert all(v['process_cleanup']['group_gone'] for v in f['phases'].values())
for role in ('runtime','toolkit','candidate','guides','frame-input','input-seals','hardware','tracked','playback-core'):
    assert load(p/f'{role}-before.json')==load(p/f'{role}-after.json'),role
archive=p/'pair-study-produced.tgz'
assert sha(archive.read_bytes())==f['pair_archive_sha256']=='b5da76d4908f60f78f9d3ddfbb81ebd4e482c6e2ae17cd889d9f2153a4f3f31b'
seen=set()
with tarfile.open(archive) as t:
    for m in t:
        assert m.isfile() and m.name not in seen and not m.name.startswith('/') and '..' not in Path(m.name).parts
        data=t.extractfile(m).read(); local=b/m.name
        assert manifest[m.name]==dict(sha256=sha(data),bytes=len(data),mode=m.mode)
        assert m.mode==0o600 and local.is_file() and not local.is_symlink()
        assert stat.S_IMODE(local.stat().st_mode)==0o640 and data==local.read_bytes()
        seen.add(m.name)
assert seen==set(manifest)=={x.relative_to(b).as_posix() for x in b.rglob('*') if x.is_file()}
original=load(Path(sys.argv[2]))
for name,row in original.items():
    data=(b/'inputs'/name).read_bytes()
    assert sha(data)==row['sha256'] and len(data)==row['bytes']
plan=load(b/'plan.json'); source=load(b/'source.json'); report=load(b/'report.json'); phase=load(b/'phase.json')
assert sha((b/'plan.json').read_bytes())==source['plan_sha256']=='1316f2e4e315ee2cd45ed805d92ee219699a311bf09bb8d106148145fb8a96cc'
assert (b/'plan.json').read_bytes()==Path(sys.argv[3]).read_bytes()
assert not report['complete'] and not report['pass'] and phase['state']=='running'
assert all(report[x] is False for x in ('all_assembly_paths_checked','physical_assembly_verified','support_stability_verified'))
raw=(b/'progress.jsonl').read_bytes();assert raw.endswith(b'\n')
events=[json.loads(x) for x in raw.splitlines()]
assert [x['sequence'] for x in events]==list(range(1,len(events)+1))
assert all(x['inputs']==source for x in events)
pair=[x['core_event'] for x in events if x['core_event']['event']=='pair']
assert len(pair)%2==1
done=[]
for i in range(0,len(pair)-1,2):
    start,end=pair[i:i+2]; index=i//2; q=plan['queries'][index]
    assert start['state']=='starting' and end['state']=='complete'
    for event in (start,end):
        assert event['pair_index']==index and event['instance']==q['moving'] and event['obstacle']==q['fixed']
        assert event['project_study']==dict(query_id=q['id'],contexts=q['contexts'])
    r=report['queries'][index]
    assert r['id']==q['id'] and r['result']==end['result']
    assert r['terminal_only']==(r['result']['state']=='seat') and r['transient_path_complete']==(r['result']['state']=='clear')
    done.append(r)
assert len(done)==len(report['queries'])==phase['completed_pairs']==42
assert pair[-1]['state']=='starting' and pair[-1]['project_study']['query_id']==plan['queries'][42]['id']==phase['current_query']
assert len(events)==553 and phase['progress_flushed_records']==552 and phase['progress_fsync_acknowledged_records']==512 and phase['progress_tail_uncertain']
assert not (b/'native-cli-exit.json').exists() and 'unchecked_queries' not in report
assert len(plan['queries'])==90
observed={r['id']:r['result'] for r in done}
counts=dict(collections.Counter(r['result']['state'] for r in done))
assert counts=={'clear':36,'seat':6}
unchecked=[q['id'] for q in plan['queries'] if q['id'] not in observed]
unexecuted_controls=[c for c in plan['controls'] if c['query'] not in observed]
assert len(unchecked)==48
result=dict(artifact_audit_pass=True,study_complete=False,source=f['source'],core=f['core'],archive_sha256=f['pair_archive_sha256'],files=len(seen),original_input_files=len(original),completed=len(done),counts=counts,unchecked=unchecked,interrupted=phase['current_query'],unexecuted_controls=unexecuted_controls,progress_records=len(events),phase_flushed=552,phase_fsync_acknowledged=512,tail_uncertain=True,all_assembly_paths_checked=False,support_stability_verified=False,physical_assembly_verified=False)
if len(sys.argv)>4:
    with Path(sys.argv[4]).open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('unchecked','unexecuted_controls')}))
