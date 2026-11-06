"""Continue the required support producer from reviewed, committed fleet222 lug files."""
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

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--head',required=True)
args=parser.parse_args()
LUG_FILES = {'checks.json': {'bytes': 860119, 'sha256': '9f01cea13904f9b892b9e13629ea0f1cbd70b018ae3fd3434af3ecd5b1522fe7'}, 'coupon_frame_ring_nom.step': {'bytes': 163102, 'sha256': '902b078c19360c9dacf762cd290efbc956efcbd5d8caa2d40c07e40df9fd8dca'}, 'coupon_frame_ring_nom.stl': {'bytes': 583684, 'sha256': '4b2b5efee4d0504ddf80f7efd25a679fca5be77d994928b1e2ff554e39d80a23'}, 'dyno_lug_plate.step': {'bytes': 258982, 'sha256': '7cd1d97654640d0d6c92b1875ede4dfd0bb8113e5a8af62c6a5825e71b6b2024'}, 'dyno_lug_plate.stl': {'bytes': 614884, 'sha256': 'ce7b8cf46b6ff804f388fae00d2a67fcc5a36d6a53fdc49d32b90cce71630a4f'}, 'hip_frame.step': {'bytes': 3139533, 'sha256': 'c63562aa659cc96a163717620dfd4f6193d44c9d40d72eae0e74abbfd127efd2'}, 'hip_frame.stl': {'bytes': 1483884, 'sha256': 'f15c00497974e3f78d3fdc9ca60ef958ebff4d3537556d98c7c6828e6ec103de'}}
results={'source':args.head,'status':'FAILED','phases':{},'scope':'actual support producer using reviewed retained222 lug inputs; no lug replay/adoption/qualification'}
initial=protected_before=None
support=OUT/'support-candidate'
try:
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
    assert 'GYROPUP_CAD_PARAMS' not in os.environ
    initial=tracked();save('tracked-before.json',initial)
    protected_before=inventory(ROOT/'hardware');save('hardware-before.json',protected_before)
    from hardware.cad.manufacturing import print_provenance as provenance
    from hardware.cad.legs import rs04_lug_checks as lugs
    before=provenance.snapshot(ROOT);save('cad-inputs-before.json',before)
    frozen=json.loads((ROOT/'.agents/plans/owning-hierarchy/geometry-inputs-frozen.json').read_text())
    assert len(before['files'])==frozen['source_members']==92
    assert before['files']==frozen['files']
    assert provenance.fingerprint(before['files'])==frozen['source_closure_sha256']
    assert before['versions']=={'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
    assert before['toolkit_sources_sha256']==lugs.TOOLKIT_SOURCES
    assert before['GYROPUP_CAD_PARAMS_sha256'] is None
    assert set(inventory(PRIVATE))==set(lugs.PRIVATE_FILES)
    assert lugs.private_inputs(PRIVATE)==lugs.PRIVATE_HASHES
    save('private-inputs.json',lugs.PRIVATE_HASHES)
    baseline=ROOT/'hardware/exports/leg/rs04-mounting-fit'
    assert inventory(baseline)==LUG_FILES,'Reviewed retained222 input bytes changed'
    data=json.loads((baseline/'checks.json').read_text())
    assert lugs.validate_receipt(data,baseline,ROOT)
    assert data['counts']=={'pass':322,'warn':40,'fail':8}
    assert data['pass'] is False
    save('retained-lug-inputs.json',LUG_FILES)
    phase('lug-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-lug-stacks.py','--receipt',str(baseline/'checks.json')],timeout=120)
    phase('support-controls-before',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--pure'],timeout=120)
    spec=importlib.util.spec_from_file_location('support_continuation_probe',ROOT/'docs/research/rs04-support/probe.py')
    probe_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe_module)
    context=provenance.context_snapshot(ROOT,[ROOT/p for p in probe_module.CONTEXT])
    save('support-context-before.json',context)
    try:
        phase('support-generate',[sys.executable,'-B','docs/research/rs04-support/probe.py','--vendor-root',str(PRIVATE),'--out',str(support)],timeout=3600)
    finally:
        if processes_quiescent:preserve('support-candidate',support)
    probe=json.loads((support/'probe.json').read_text())
    assert probe['probe_complete'] is True and probe['engineering_pass'] is False
    assert probe['source_inputs']==probe['source_inputs_after']
    assert probe['source_inputs']['project']==before
    assert probe['source_inputs']['context']==context
    assert set(inventory(support))=={'probe.json',*(name+'.step' for name in probe['candidate_rings'])}
    assert len(probe['candidate_rings'])==8
    phase('support-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--receipt',str(support/'probe.json')],timeout=120)
    assert provenance.snapshot(ROOT)==before
    assert provenance.context_snapshot(ROOT,[ROOT/p for p in probe_module.CONTEXT])==context
    results['status']='PASS_SCOPED'
except BaseException as exc:
    results['error']=type(exc).__name__+': '+str(exc)
    raise
finally:
    errors=[]
    if not processes_quiescent:
        results['status']='FAILED';results['final_guard_errors']=['Owned group not quiescent; do not race inventory/archive']
        save('result.json',results)
        raise RuntimeError(results['final_guard_errors'][0])
    if initial is not None:
        try:
            final=tracked();save('tracked-final.json',final)
            if final!=initial:errors.append('Tracked bytes changed')
            else:results['final_tracked_identity_unchanged']=True
            final_hardware=inventory(ROOT/'hardware');save('hardware-final.json',final_hardware)
            if final_hardware!=protected_before:errors.append('Complete hardware path/byte set changed')
            else:results['complete_hardware_identity_unchanged']=True
        except BaseException as exc:errors.append(type(exc).__name__+': '+str(exc))
    if errors:
        results['status']='FAILED';results['final_guard_errors']=errors
    save('result.json',results)
    if errors:raise RuntimeError('; '.join(errors))
