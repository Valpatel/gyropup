"""Bounded, output-preserving lug/support regeneration; no adoption or qualification."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tarfile, time, signal, ctypes

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
os.environ['PYTHONPATH'] = str(ROOT)
OUT = Path(os.environ['FLEET_RUN_OUT']).resolve()
PRIVATE = Path(os.environ['FLEET_RUN_IN']) / 'vendor'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def tracked():
    names = subprocess.check_output(['git','ls-files','-z'], text=True).split('\0')
    return {n: sha(ROOT/n) for n in names if n}

def inventory(directory):
    rows = {}
    for p in sorted(directory.rglob('*')):
        mode = p.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Nonregular output: '+p.relative_to(directory).as_posix())
        rows[p.relative_to(directory).as_posix()] = {'bytes':p.stat().st_size,'sha256':sha(p)}
    return rows

def preserve(label, directory):
    if not directory.exists():
        return
    rows = inventory(directory)
    save(label+'-inventory.json', rows)
    with tarfile.open(OUT/(label+'.tgz'),'w:gz') as archive:
        for n in rows:
            archive.add(directory/n, arcname=n, recursive=False)
    save(label+'-archive.json', {'sha256':sha(OUT/(label+'.tgz')),'files':len(rows)})

def settle_owned_group(proc):
    """Kill and reap our group even after its original leader has exited."""
    signalled=False;reaped=[]
    try:os.killpg(proc.pid,signal.SIGKILL);signalled=True
    except ProcessLookupError:pass
    proc.wait(timeout=5)
    deadline=time.monotonic()+3
    while True:
        while True:
            try:pid,status=os.waitpid(-proc.pid,os.WNOHANG)
            except ChildProcessError:break
            if pid==0:break
            reaped.append({'pid':pid,'status':status})
        try:os.killpg(proc.pid,0)
        except ProcessLookupError:return {'group_gone':True,'signalled':signalled,'reaped':reaped}
        if time.monotonic()>=deadline:return {'group_gone':False,'signalled':signalled,'reaped':reaped}
        time.sleep(.02)

libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(36,1,0,0,0)==0,'Linux child subreaper required'
def interrupted(signum,frame):raise KeyboardInterrupt('received signal '+str(signum))
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
processes_quiescent=True
def phase(name,command,expected=0,timeout=3600):
 global processes_quiescent
 start=time.monotonic();record={'command':command,'expected_exit':expected};child=None
 print('START '+name,flush=True)
 try:
  with (OUT/(name+'.log')).open('w') as stream:
   processes_quiescent=False
   blocked_before_spawn=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
   def child_unmask():signal.pthread_sigmask(signal.SIG_SETMASK,blocked_before_spawn)
   try:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                           start_new_session=True,preexec_fn=child_unmask)
   finally:
    # Deliver a pending interrupt only after the child handle is captured.
    signal.pthread_sigmask(signal.SIG_SETMASK,blocked_before_spawn)
   try:record['exit']=child.wait(timeout=timeout)
   except subprocess.TimeoutExpired:record['timed_out']=True
 except BaseException as exc:
  record['error']=type(exc).__name__+': '+str(exc)
  raise
 finally:
  # Cover every path after launch, including interruption before wait begins.
  if child is not None:
   cleanup=settle_owned_group(child)
   record['process_cleanup']=cleanup;processes_quiescent=cleanup['group_gone']
  record['seconds']=time.monotonic()-start;results['phases'][name]=record;save('result.json',results)
  print('END '+name+' '+json.dumps(record),flush=True)
  assert processes_quiescent,'Owned group not quiescent; do not race archive/restore'
 assert record.get('exit')==expected,name+' failed/incomplete; actual logs retained'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--head', required=True)
args = parser.parse_args()
results = {'source':args.head,'status':'FAILED','phases':{},'scope':'actual bounded geometry generation only; no adoption/physical qualification'}
initial = None
protected_before = None
lug = OUT/'lug-candidate'
support = OUT/'support-candidate'
replacement = {}
try:
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == args.head
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
    assert 'GYROPUP_CAD_PARAMS' not in os.environ
    initial = tracked()
    save('tracked-before.json', initial)
    protected_before = inventory(ROOT/'hardware')
    save('hardware-before.json',protected_before)
    from hardware.cad.manufacturing import print_provenance as provenance
    from hardware.cad.legs import rs04_lug_checks as lugs
    before = provenance.snapshot(ROOT)
    save('cad-inputs-before.json', before)
    config=json.loads((ROOT/'.agents/plans/turret-recovery/cad-inputs-final.json').read_text())
    frozen=config['files']
    assert len(before['files']) == len(frozen) == 94
    assert before['files'] == frozen
    assert provenance.fingerprint(frozen)==config['fingerprint']
    assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip() == config['hardware_tree']
    save('frozen-current-source.json',config)
    assert before['versions'] == {'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
    assert before['toolkit_sources_sha256'] == lugs.TOOLKIT_SOURCES
    assert before['GYROPUP_CAD_PARAMS_sha256'] is None
    assert set(inventory(PRIVATE)) == set(lugs.PRIVATE_FILES)
    assert lugs.private_inputs(PRIVATE) == lugs.PRIVATE_HASHES
    save('private-inputs.json', lugs.PRIVATE_HASHES)
    preserve('original-support-targets',ROOT/'docs/research/rs04-support/results')
    phase('lug-controls-before', [sys.executable,'-B','tests/hardware/interfaces/test-rs04-lug-stacks.py','--pure'], timeout=120)
    phase('support-controls-before', [sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--pure'], timeout=120)
    # Exit1 is expected only for the independently verified complete known-failing verdict below.
    try:
        phase('lug-generate',[sys.executable,'-B','hardware/cad/legs/rs04_lug_checks.py','--vendor-root',str(PRIVATE),'--out',str(lug),'--export'],expected=1,timeout=5400)
    finally:
        if processes_quiescent:preserve('lug-candidate',lug)
    data = json.loads((lug/'checks.json').read_text())
    assert lugs.validate_receipt(data,lug,ROOT)
    assert data['counts'] == {'pass':322,'warn':40,'fail':8}
    phase('lug-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-lug-stacks.py','--receipt',str(lug/'checks.json')],timeout=120)
    # Explicitly preserve the old/new geometric evidence even when export bytes drift.
    import numpy as np
    import trimesh
    old_lug = ROOT/'hardware/exports/leg/rs04-mounting-fit'
    old_report = json.loads((old_lug/'checks.json').read_text())
    # Native STEP serialization changed in retained job222 despite unchanged
    # native/mesh geometry. Preserve both real shape bindings for review; the
    # unchanged product validator and the geometric comparisons below still run.
    save('lug-old-new-shape-bindings.json',{'original':old_report['authored_shapes'],'candidate':data['authored_shapes']})
    metrics = {}
    for part in lugs.OUTPUT_PARTS:
        pair = []
        meshes = []
        for directory in (old_lug,lug):
            mesh = trimesh.load_mesh(directory/(part+'.stl'),process=False)
            vertices = np.unique(np.round(mesh.vertices,4),axis=0)
            row = {'bounds_mm':np.round(mesh.bounds,4).tolist(),'volume_mm3':float(mesh.volume),
                   'unique_vertices_0_0001_mm':len(vertices),
                   'vertices_sha256':hashlib.sha256(vertices.tobytes()).hexdigest()}
            pair.append(row);meshes.append(vertices)
        metrics[part] = {'historical':pair[0],'fresh':pair[1]}
        save('lug-old-new-geometry.json',metrics)
        assert pair[0]['bounds_mm']==pair[1]['bounds_mm']
        assert abs(pair[0]['volume_mm3']-pair[1]['volume_mm3']) <= max(1e-6,abs(pair[0]['volume_mm3'])*1e-9)
        assert np.array_equal(meshes[0],meshes[1]), 'Rounded unique mesh vertices changed'
    expected = {'checks.json',*(p+'.'+ext for p in lugs.OUTPUT_PARTS for ext in ('step','stl'))}
    assert set(inventory(lug)) == expected
    # Feed the REAL completed failing lug receipt to its unchanged support consumer.
    # This temporary clone replacement is explicitly recorded, not a repository adoption.
    target = ROOT/'hardware/exports/leg/rs04-mounting-fit'
    original = OUT/'original-lug-inputs'
    original.mkdir()
    for n in sorted(expected):
        assert (target/n).is_file()
        shutil.copyfile(target/n,original/n)
        replacement[(target/n).relative_to(ROOT).as_posix()] = sha(lug/n)
        shutil.copyfile(lug/n,target/n)
    preserve('original-lug-inputs',original)
    save('temporary-real-lug-inputs.json',replacement)
    try:
        phase('support-generate',[sys.executable,'-B','docs/research/rs04-support/probe.py','--vendor-root',str(PRIVATE),'--out',str(support)],timeout=3600)
    finally:
        if processes_quiescent:preserve('support-candidate',support)
    probe = json.loads((support/'probe.json').read_text())
    assert probe['probe_complete'] is True and probe['engineering_pass'] is False
    assert probe['source_inputs'] == probe['source_inputs_after']
    assert probe['source_inputs']['project'] == before
    assert set(inventory(support)) == {'probe.json',*(name+'.step' for name in probe['candidate_rings'])}
    assert len(probe['candidate_rings']) == 8
    # Actual pinned inventory consumer: a changed content identity is a failure pending review.
    phase('support-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--receipt',str(support/'probe.json')],timeout=120)
    assert provenance.snapshot(ROOT) == before
    results['status'] = 'PASS_SCOPED'
except BaseException as exc:
    results['error'] = type(exc).__name__+': '+str(exc)
    raise
finally:
    final_errors = []
    if not processes_quiescent:
        results['status']='FAILED'
        results['final_guard_errors']=['Owned group not quiescent; preserve working outputs without racing archive/restoration']
        save('result.json',results)
        raise RuntimeError(results['final_guard_errors'][0])
    if initial is not None:
        # Observation must never prevent restoration of our declared temporary inputs.
        try:
            current = tracked()
            save('tracked-after-with-temporary-lug-input.json',current)
            if current != initial | replacement:
                final_errors.append('Unexpected source/output mutation')
        except BaseException as exc:
            final_errors.append('Observation: '+type(exc).__name__+': '+str(exc))
        finally:
            for n in replacement:
                try:
                    shutil.copyfile(OUT/'original-lug-inputs'/Path(n).name,ROOT/n)
                except BaseException as exc:
                    final_errors.append('Restore '+n+': '+type(exc).__name__+': '+str(exc))
        try:
            final = tracked()
            save('tracked-final-restored.json',final)
            if final != initial:
                final_errors.append('Final tracked bytes not restored')
            else:
                results['final_tracked_identity_restored'] = True
            protected_after = inventory(ROOT/'hardware')
            save('hardware-final-restored.json',protected_after)
            if protected_after != protected_before:
                final_errors.append('Complete hardware path/byte set changed')
            else:
                results['complete_hardware_identity_restored'] = True
        except BaseException as exc:
            final_errors.append('Final guard: '+type(exc).__name__+': '+str(exc))
    if final_errors:
        results['status'] = 'FAILED'
        results['final_guard_errors'] = final_errors
    save('result.json',results)
    if final_errors:
        raise RuntimeError('; '.join(final_errors))
