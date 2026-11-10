"""Pure byte/report audit of frame-only artifacts; no CAD import or query."""
from pathlib import Path
import collections,hashlib,json,math,stat,struct,sys,tarfile
fetch=Path(sys.argv[1]);repo=Path(sys.argv[2]);out=fetch/'out';base=out/'frame-preflight'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
final=read(out/'final-result.json');assert final['status']=='PASS_SCOPED_NATIVE_FRAME_PREFLIGHT'
assert final['source']=='6acc8fda343b1f27679a4c3ae84e859b1714ca36' and final['core']=='5c29c9e2abf2562baa72a05248f23de054b8241e'
assert final['input_job']==261 and final['paths_requested'] is False and final['adoption_approved'] is False
assert len(final['guards'])==8 and all(final['guards'].values()) and not final['errors'] and final['processes_quiescent']
assert set(final['phases'])=={'core-init','core-origin','core-fetch','core-sparse','core-checkout','native-frame'}
assert all(p['exit']==0 and p['process_cleanup']['group_gone'] for p in final['phases'].values())
for role in ('runtime','toolkit','candidate','guides','hardware','tracked','playback-core'):
 assert read(out/(role+'-before.json'))==read(out/(role+'-after.json')),role
for role in ('candidate','guides'):
 original=read(repo/'.agents/plans/assembly-staging/native-261'/(role+'-members.json'));actual=read(out/(role+'-before.json'))
 assert set(actual)==set(original)
 assert all(original[k]['mode']==0o600 and actual[k]=={**original[k],'mode':0o640} for k in actual)
 receipt=read(out/(role+'-input-validation.json'));assert receipt['members']==len(actual) and receipt['content_and_membership_equal']
manifest=read(out/'frame-preflight-members.json');archive=out/'frame-preflight-produced.tgz'
assert sha(archive.read_bytes())==final['frame_archive_sha256']
seen=set()
with tarfile.open(archive,'r:gz') as tar:
 for item in tar:
  assert item.isfile() and item.name in manifest and item.name not in seen
  assert not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
  row=manifest[item.name];payload=tar.extractfile(item).read();assert row=={'sha256':sha(payload),'mode':item.mode,'bytes':len(payload)}
  seen.add(item.name)
assert seen==set(manifest)
actual={}
for p in base.rglob('*'):
 mode=p.lstat().st_mode
 if stat.S_ISDIR(mode):continue
 assert stat.S_ISREG(mode)
 payload=p.read_bytes();actual[p.relative_to(base).as_posix()]={'sha256':sha(payload),'bytes':len(payload),'mode':stat.S_IMODE(mode)}
assert set(actual)==set(manifest)
assert all(manifest[k]['mode']==0o600 and actual[k]=={**manifest[k],'mode':0o640} for k in actual)
inputs=read(base/'inputs.json');collection=read(base/'source-collection.json')
assert sha((base/'source-collection.json').read_bytes())=='94ea324e5ee710a174dd67b5545c62ba5365e8ea29ebac2f317391c4c88f980b'
assert inputs['playback_toolkit_revision']==final['core'] and inputs['source_commit']==collection['source_commit']=='e5b3089277448e5ae3d546fc36c549a62949856b'
assert inputs['adapter_sha256']==sha((repo/'tools/site/assembly/robot_native_playback.py').read_bytes())
assert inputs['source_producer_inputs']==collection['producer_inputs']
assert len(inputs['guides'])==1;row=inputs['guides'][0];binding=read(base/row['binding'])
assert sha((base/row['binding']).read_bytes())==row['binding_sha256']=='ccce5798a6cd220a8ba9935468f34cd619a2db26b4d386ccc1b34c28fcf3590c'
assert (base/row['binding']).read_bytes()==(repo/'.agents/plans/assembly-staging/native-261/combined-binding.json').read_bytes()
guide_path=base/'captured-guides'/row['guide'];guide=read(guide_path);model_path=guide_path.parent/guide['model']['file'];model=read(model_path)
assert sha(guide_path.read_bytes())==row['guide_sha256']=='044a5a4ca3c2f3e238cbfdf6dba3412a095223ae76e98505ef8d698ba9d4516a'
assert sha(model_path.read_bytes())==guide['model']['sha256']
parts={p['name']:p for p in model['parts']};originals={p['name']:p for p in collection['parts']}
assert len(parts)==233 and set(parts)==set(originals)==set(binding['instances'])==set(row['breps'])
triangles=0;mesh_bounds={}
for name,part in parts.items():
 source=originals[name];entry=binding['instances'][name];native=source['native_geometry'];payload=(base/row['breps'][name]).read_bytes()
 assert sha(payload)==native['sha256']==entry['brep_sha256'] and entry['shape_sha256']==native['shape_sha256'] and entry['matrix']==native['matrix']
 mesh=(model_path.parent/part['file']).resolve();assert mesh.is_relative_to((base/'captured-guides').resolve())
 data=mesh.read_bytes();assert sha(data)==part['sha256']==source['sha256']==entry['mesh_sha256']
 count=struct.unpack_from('<I',data,80)[0];assert count>0 and len(data)==84+50*count;triangles+=count
 low=[math.inf]*3;high=[-math.inf]*3
 for i in range(count):
  values=struct.unpack_from('<12fH',data,84+50*i);assert all(math.isfinite(v) for v in values[:12])
  for j in (3,6,9):
   for axis in range(3):low[axis]=min(low[axis],values[j+axis]);high[axis]=max(high[axis],values[j+axis])
 mesh_bounds[name]=low+high
report_path=base/'reports/combined-wip-e5b308927744.json';report=read(report_path);phase=read(base/'reports/combined-wip-e5b308927744.phase.json')
assert report['gate']=='assembly-playback-preflight' and report['pass'] is True and report['status']=='warn'
assert report['operations']==[] and report['limits']['paths_checked'] is False and report['limits']['progress_complete'] is True
assert report['limits']['support_stability_verified'] is False and report['limits']['physical_assembly_verified'] is False
assert report['world_stats']=={'kernel_queries':0,'memo_hits':0,'cache_hits':0,'tool_sweeps':0}
assert {r['instance'] for r in report['frames']}==set(parts) and len(report['frames'])==233
for frame in report['frames']:
 name=frame['instance'];assert frame['mesh_bounds_mm']==mesh_bounds[name] and frame['model_bounds_mm']==parts[name]['bounds_mm']
 cm=max(abs(a-b) for a,b in zip(frame['cad_bounds_mm'],mesh_bounds[name]));mm=max(abs(a-b) for a,b in zip(mesh_bounds[name],parts[name]['bounds_mm']))
 assert cm==frame['cad_mesh_max_error_mm']<=report['limits']['bounds_tolerance_mm']
 assert mm==frame['mesh_model_max_error_mm']<=report['limits']['model_bounds_rounding_allowance_mm']
assert report['inputs']['guide_sha256']==row['guide_sha256'] and report['inputs']['producer_hash_platform']==inputs['original_hash_platform']==binding['hash_platform']
events=[json.loads(line) for line in (base/'progress/combined-wip-e5b308927744.jsonl').read_text().splitlines()]
assert len(events)==941 and [e['sequence'] for e in events]==list(range(1,942))
assert all(e['schema']=='gyropup.native-playback-progress/1' and e['inputs']==phase['inputs'] for e in events)
assert all(e['core_event']['event'] not in ('pair','operation') for e in events)
counts=collections.Counter((e['core_event']['event'],e['core_event'].get('phase'),e['core_event'].get('state')) for e in events)
for stage in ('load','frame'):
 for state in ('starting','complete'):
  names=[e['core_event']['instance'] for e in events if e['core_event'].get('phase')==stage and e['core_event'].get('state')==state and 'instance' in e['core_event']]
  assert len(names)==233 and set(names)==set(parts)
last=events[-1]['core_event'];assert last['event']=='preflight' and last['state']=='complete' and last['inputs']==report['inputs'] and last['frames']==report['frames']
assert phase['state']=='complete' and phase['gate_pass'] is True and phase['progress_tail_uncertain'] is False
assert phase['progress_flushed_records']==phase['progress_fsync_acknowledged_records']==len(events)
summary={'schema':'gyropup.native-frame-artifact-audit/1','job':263,'input_job':261,'source':final['source'],'core':final['core'],'pass':True,'gate_status':report['status'],'scope':'original-byte hashes and actual CAD/STL/model frame bounds only','archive_sha256':final['frame_archive_sha256'],'archive_members':len(manifest),'actual_output_files':len(actual),'instances':len(parts),'triangles_parsed':triangles,'original_brep_bytes_preserved':True,'combined_binding_equals_independently_accepted_pure261':True,'source_identities_preserved':True,'cad_mesh_max_error_mm':max(f['cad_mesh_max_error_mm'] for f in report['frames']),'mesh_model_max_error_mm':max(f['mesh_model_max_error_mm'] for f in report['frames']),'progress_records':len(events),'progress_flushed_records':phase['progress_flushed_records'],'progress_fsync_acknowledged_records':phase['progress_fsync_acknowledged_records'],'all_preservation_guards':True,'all_child_groups_gone':True,'paths_checked':False,'kernel_pair_queries':0,'support_stability_verified':False,'physical_assembly_verified':False,'seals':{'report':sha(report_path.read_bytes()),'progress':sha((base/'progress/combined-wip-e5b308927744.jsonl').read_bytes()),'phase':sha((base/'reports/combined-wip-e5b308927744.phase.json').read_bytes()),'inputs':sha((base/'inputs.json').read_bytes()),'archive_members':sha((out/'frame-preflight-members.json').read_bytes())}}
print(json.dumps(summary,indent=2))
