"""Collect three public authored-geometry packages at the frozen CAD input set."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,stat,subprocess,sys,tarfile,time,signal,ctypes
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
sys.path.insert(0,str(ROOT));os.environ['PYTHONPATH']=str(ROOT)
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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
PIN='2ad426943ce2c7232875e105e50810849f9a3e5e'
results={'source':args.head,'status':'FAILED','phases':{},'scope':'authored interface reservations, insert specimens and survey gauge only; no adoption or physical qualification'}
initial=None;replacement={};original=OUT/'original-consumer-inputs';original.mkdir()
groups={'interfaces':(OUT/'interfaces','hardware/exports/turret/base-board-service/interfaces'),
        'insert-fit':(OUT/'insert-fit','hardware/exports/turret/carrier-insert-fit'),
        'ordered-gauge':(OUT/'ordered-gauge','hardware/exports/turret/ordered-motor-fit')}
def supply_to_current_consumer(label):
    candidate,relative=groups[label];target=ROOT/relative
    names=set(inventory(candidate));assert names=={p.name for p in target.iterdir()}
    for name in sorted(names):
        identity=relative+'/'+name;old=original/identity;old.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/identity,old)
        replacement[identity]=sha(candidate/name)
        shutil.copyfile(candidate/name,ROOT/identity)
    save('temporary-consumer-inputs.json',replacement)
try:
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
    assert 'GYROPUP_CAD_PARAMS' not in os.environ
    initial=tracked();save('tracked-before.json',initial)
    protected_before=inventory(ROOT/'hardware');save('hardware-before.json',protected_before)
    import cadagent
    kit=Path(os.environ['GYROPUP_TOOLKIT_DIR']).resolve()
    assert not kit.is_relative_to(ROOT)
    assert Path(cadagent.__file__).resolve().is_relative_to(kit/'src')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()==PIN
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=kit,text=True).strip()
    from hardware.cad.manufacturing import print_provenance as provenance
    before=provenance.snapshot(ROOT);frozen=json.loads((ROOT/'.agents/plans/owning-hierarchy/geometry-inputs-frozen.json').read_text())
    assert before['files']==frozen['files'] and len(before['files'])==92
    assert provenance.fingerprint(before['files'])==frozen['source_closure_sha256']
    assert before['versions']=={'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
    assert before['toolkit_sources_sha256']=='c2941322d5f3d000d3777b0047567211d06855861fa5e14229d7d7519fef3ed3'
    assert before['GYROPUP_CAD_PARAMS_sha256'] is None
    save('cad-inputs-before.json',before)
    save('toolkit-origin.json',{'revision':PIN,'module':'src/cadagent/__init__.py','source_fingerprint':before['toolkit_sources_sha256']})
    for candidate,_ in groups.values():assert not candidate.exists()
    try:
        phase('interfaces-generate',[sys.executable,'-B','hardware/cad/turret/check_base_board_interfaces.py','--out',str(groups['interfaces'][0])],timeout=900)
    finally:
        if processes_quiescent:preserve('interfaces',groups['interfaces'][0])
    data=json.loads((groups['interfaces'][0]/'interfaces.json').read_text())
    previous=json.loads((ROOT/groups['interfaces'][1]/'interfaces.json').read_text())
    assert {r['id'] for r in data['checks']}=={r['id'] for r in previous['checks']}
    assert len(data['checks'])==len(previous['checks'])
    assert data['bounded_reservation_checks_pass'] is True and data['readiness'] is False and data['physical_fit_verified'] is False
    assert data['inputs']==before
    supply_to_current_consumer('interfaces')
    phase('interfaces-real-controls',[sys.executable,'-B','tests/hardware/interfaces/test-base-board-interface-geometry.py'],timeout=120)
    phase('interfaces-receipt-controls',[sys.executable,'-B','tests/hardware/interfaces/test-base-board-interfaces.py'],timeout=120)
    try:
        phase('insert-fit-generate',[sys.executable,'-B','docs/research/carrier-insert-fit/generate.py','--out',str(groups['insert-fit'][0])],timeout=900)
    finally:
        if processes_quiescent:preserve('insert-fit',groups['insert-fit'][0])
    phase('insert-fit-real-consumer',[sys.executable,'-B','docs/research/carrier-insert-fit/verify.py',str(groups['insert-fit'][0])],timeout=120)
    # Existing measurements are evidence, not a template to be reset by relocation.
    assert (groups['insert-fit'][0]/'measurements.csv').read_bytes()==(ROOT/groups['insert-fit'][1]/'measurements.csv').read_bytes()
    supply_to_current_consumer('insert-fit')
    phase('insert-fit-corruption-controls',[sys.executable,'-B','docs/research/carrier-insert-fit/test_guards.py'],timeout=120)
    try:
        phase('ordered-gauge-generate',[sys.executable,'-B','docs/research/ordered-turret-motor/gauge.py','--out',str(groups['ordered-gauge'][0])],timeout=900)
    finally:
        if processes_quiescent:preserve('ordered-gauge',groups['ordered-gauge'][0])
    gauge=json.loads((groups['ordered-gauge'][0]/'checks.json').read_text())
    assert gauge['pass'] is True and gauge['counts']=={'pass':12,'warn':0,'fail':0}
    assert gauge['toolkit_revision']==PIN and gauge['project_revision']==args.head
    assert gauge['source_sha256']=={n:sha(ROOT/n) for n in ('docs/research/ordered-turret-motor/gauge.py','docs/research/ordered-turret-motor/seller-claims.json')}
    assert all(gauge.get(n) is False for n in ('physical_fit_verified','slicer_run','print_release','mount_design_released','hub_design_released','powered_operation_qualified'))
    assert set(inventory(groups['ordered-gauge'][0]))=={'checks.json','shaft-clearance-survey.step','shaft-clearance-survey.stl'}
    for n,h in gauge['artifact_sha256'].items():assert sha(groups['ordered-gauge'][0]/n)==h
    assert provenance.snapshot(ROOT)==before
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()==PIN
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=kit,text=True).strip()
    results['status']='PASS_SCOPED'
except BaseException as exc:
    results['error']=type(exc).__name__+': '+str(exc)
    raise
finally:
    errors=[]
    if not processes_quiescent:
        results['status']='FAILED';results['final_guard_errors']=['Owned group not quiescent; preserve working outputs without racing archive/restore']
        save('result.json',results);raise RuntimeError(results['final_guard_errors'][0])
    if initial is not None:
        try:
            current=tracked();save('tracked-after-with-temporary-consumer-inputs.json',current)
            if current!=initial|replacement:errors.append('Unexpected source/output mutation')
            preserve('original-consumer-inputs',original)
        except BaseException as exc:errors.append('Observation: '+type(exc).__name__+': '+str(exc))
        finally:
            for identity in replacement:
                try:shutil.copyfile(original/identity,ROOT/identity)
                except BaseException as exc:errors.append('Restore '+identity+': '+type(exc).__name__+': '+str(exc))
        try:
            final=tracked();save('tracked-final-restored.json',final)
            if final!=initial:errors.append('Tracked source/input restoration failed')
            protected_after=inventory(ROOT/'hardware');save('hardware-final-restored.json',protected_after)
            if protected_after!=protected_before:errors.append('Complete hardware path/byte membership differs')
        except BaseException as exc:errors.append('Final guard: '+type(exc).__name__+': '+str(exc))
    if errors:results['status']='FAILED';results['final_guard_errors']=errors
    save('result.json',results)
    if errors:raise RuntimeError('; '.join(errors))
