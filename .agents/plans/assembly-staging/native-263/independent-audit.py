from pathlib import Path
import hashlib, io, json, math, struct, tarfile, collections, sys
import cadquery as cq

root=Path(sys.argv[1])/'out'
base=root/'frame-preflight'
prior=Path(sys.argv[2])/'.agents/plans/assembly-staging/native-261'
read=lambda p: json.loads(p.read_text())
digest=lambda b: hashlib.sha256(b).hexdigest()
final=read(root/'final-result.json')
assert final['source']=='6acc8fda343b1f27679a4c3ae84e859b1714ca36'
assert final['core']=='5c29c9e2abf2562baa72a05248f23de054b8241e'
assert final['status']=='PASS_SCOPED_NATIVE_FRAME_PREFLIGHT'
assert final['input_job']==261 and not final['paths_requested'] and not final['adoption_approved']
assert len(final['guards'])==8 and all(final['guards'].values()) and final['errors']==[]
assert final['processes_quiescent'] and len(final['phases'])==6
assert all(p['exit']==0 and p['process_cleanup']['group_gone'] for p in final['phases'].values())
for role in ['runtime','toolkit','candidate','guides','hardware','tracked','playback-core']:
    assert read(root/f'{role}-before.json')==read(root/f'{role}-after.json'),role
for role in ['candidate','guides']:
    old=read(prior/f'{role}-members.json'); retained=read(root/f'{role}-before.json')
    assert old.keys()==retained.keys()
    for name, entry in old.items():
        assert entry['mode']==0o600 and retained[name]==dict(entry,mode=0o640)

archive=root/'frame-preflight-produced.tgz'
assert digest(archive.read_bytes())==final['frame_archive_sha256']=='11ab77cded69bf6ba7f54b2ced0f9b43198d6fa0d8ca726daf378e7f51994e1b'
members=read(root/'frame-preflight-members.json')
seen=set()
with tarfile.open(archive) as tf:
    for entry in tf:
        assert entry.isfile() and entry.name not in seen
        p=Path(entry.name)
        assert not p.is_absolute() and '..' not in p.parts
        data=tf.extractfile(entry).read()
        assert members[entry.name]=={'sha256':digest(data),'bytes':len(data),'mode':entry.mode}
        actual=base/p
        assert not actual.is_symlink() and actual.read_bytes()==data
        assert entry.mode==0o600 and actual.stat().st_mode&0o777==0o640
        seen.add(entry.name)
assert seen==set(members)=={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}

inputs=read(base/'inputs.json'); row,=inputs['guides']
collection=read(base/'source-collection.json')
assert digest((base/'source-collection.json').read_bytes())==inputs['collection_sha256']=='94ea324e5ee710a174dd67b5545c62ba5365e8ea29ebac2f317391c4c88f980b'
bp=base/row['binding']; binding=read(bp)
assert bp.read_bytes()==(prior/'combined-binding.json').read_bytes()
assert digest(bp.read_bytes())==row['binding_sha256']=='ccce5798a6cd220a8ba9935468f34cd619a2db26b4d386ccc1b34c28fcf3590c'
gp=base/'captured-guides'/row['guide']; guide=read(gp)
assert digest(gp.read_bytes())==binding['guide_sha256']==row['guide_sha256']
mp=gp.parent/guide['model']['file']; model=read(mp)
assert digest(mp.read_bytes())==guide['model']['sha256']==binding['model_sha256']
originals={x['name']:x for x in collection['parts']}
report=read(base/'reports/combined-wip-e5b308927744.json')
frames={x['instance']:x for x in report['frames']}
assert len(model['parts'])==len(frames)==233
assert set(frames)==set(originals)==set(binding['instances'])==set(row['breps'])
triangles=0; native_errors=[]; frame_errors=[]
for part in model['parts']:
    name=part['name']; original=originals[name]; frame=frames[name]; bound=binding['instances'][name]
    raw=(base/row['breps'][name]).read_bytes()
    assert digest(raw)==original['native_geometry']['sha256']==bound['brep_sha256']
    assert bound['matrix']==[1,0,0,0,0,1,0,0,0,0,1,0]
    # Independent actual native import, not trusting the stored CAD bounding box.
    shape=cq.Shape.importBrep(io.BytesIO(raw)); box=shape.BoundingBox()
    actual_cad=[box.xmin,box.ymin,box.zmin,box.xmax,box.ymax,box.zmax]
    error=max(abs(a-b) for a,b in zip(actual_cad,frame['cad_bounds_mm']))
    assert error<1e-7,(name,error)
    native_errors.append(error)
    mesh=(mp.parent/part['file']).resolve(); assert mesh.is_relative_to(base.resolve())
    data=mesh.read_bytes()
    assert digest(data)==part['sha256']==original['sha256']==bound['mesh_sha256']
    n=struct.unpack_from('<I',data,80)[0]; assert len(data)==84+n*50 and n>0
    triangles+=n; low=[math.inf]*3; high=[-math.inf]*3
    for i in range(n):
        vertices=struct.unpack_from('<9f',data,84+i*50+12)
        for j,value in enumerate(vertices):
            assert math.isfinite(value)
            axis=j%3;low[axis]=min(low[axis],value); high[axis]=max(high[axis],value)
    bounds=low+high
    assert bounds==frame['mesh_bounds_mm']==part['bounds_mm']==frame['model_bounds_mm']
    delta=max(abs(a-b) for a,b in zip(actual_cad,bounds))
    assert abs(delta-frame['cad_mesh_max_error_mm'])<1e-7 and delta<=0.5
    frame_errors.append((delta,name))
assert report['gate']=='assembly-playback-preflight' and report['pass'] and report['status']=='warn'
assert report['operations']==[] and not report['physical_fit_verified']
assert not report['limits']['paths_checked'] and not report['limits']['physical_assembly_verified'] and not report['limits']['support_stability_verified']
assert all(v==0 for v in report['world_stats'].values())
events=[json.loads(line) for line in (base/'progress/combined-wip-e5b308927744.jsonl').read_text().splitlines()]
phase=read(base/'reports/combined-wip-e5b308927744.phase.json')
assert len(events)==941 and phase['state']=='complete' and phase['progress_tail_uncertain'] is False
assert phase['progress_flushed_records']==phase['progress_fsync_acknowledged_records']==941
assert [e['sequence'] for e in events]==list(range(1,942))
assert all(e['inputs']==phase['inputs'] for e in events)
for kind in ['load','frame']:
    for state in ['starting','complete']:
        names=[e['core_event']['instance'] for e in events if e['core_event'].get('phase')==kind and e['core_event'].get('state')==state and 'instance' in e['core_event']]
        assert len(names)==233 and set(names)==set(frames)
assert events[-1]['core_event']['frames']==report['frames']
assert not any(e['core_event']['event'] in ['pair','operation'] for e in events)
summary={'reviewer':'independent GPT-6','job':263,'source':final['source'],'core':final['core'],'pass_scoped_frame_audit':True,'actual_native_breps_reimported':233,'native_vs_report_max_error_mm':max(native_errors),'archive_and_actual_members':len(seen),'triangles_independently_parsed':triangles,'largest_cad_mesh_errors_mm':sorted(frame_errors,reverse=True)[:3],'progress_records':len(events),'paths_checked':False,'physics_or_manufacturing_qualified':False,'scope':'Original bytes, identity and actual native/mesh/model frame consistency; not insertion validation'}
if len(sys.argv)>3:
    with Path(sys.argv[3]).open('x') as stream:stream.write(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
