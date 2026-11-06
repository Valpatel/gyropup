"""Render the historical E1 static field after its source-path migration; no solver."""
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
results={'source':args.head,'status':'FAILED','phases':{},'scope':'new presentation of unchanged historical static field only; no solver, dynamics or physical qualification'}
NAMES=['hardware/exports/leg/fea/hip-frame-e1-media/'+n for n in ('hip-frame-e1.mp4','hip-frame-e1.webm','hip-frame-e1-poster.png','video-receipt.json')]+['hardware/exports/leg/fea/media.json']
SOURCE=['tools/engineering/legs/render-hip-frame-e1.py','hardware/cad/locations.py','hardware/exports/leg/fea/hip-frame-e1-media/field-receipt.json','hardware/exports/leg/fea/hip-frame-e1-media/hip_frame-E1.json','hardware/exports/leg/fea/summary.json','docs/research/leg-preprint/evidence/hip-frame-print-ready.json']
original=OUT/'original-targets';original.mkdir();initial=None;protected_before=None
candidate=OUT/'candidate-targets'
def copy_targets(directory):
 directory.mkdir(exist_ok=True)
 for n in NAMES:
  path=directory/n;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,path)
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
 import importlib.metadata as metadata
 assert {name:metadata.version(name) for name in ('numpy','pyvista','vtk','matplotlib','pillow')}=={'numpy':'2.5.4','pyvista':'0.49.1','vtk':'9.6.2','matplotlib':'3.11.2','pillow':'13.0.0'}
 save('renderer-runtime.json',{'packages':{name:metadata.version(name) for name in ('numpy','pyvista','vtk','matplotlib','pillow')},'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],'ffprobe':subprocess.check_output(['ffprobe','-version'],text=True).splitlines()[0],'node':subprocess.check_output(['node','--version'],text=True).strip()})
 initial=tracked();save('tracked-before.json',initial);protected_before=inventory(ROOT/'hardware');save('hardware-before.json',protected_before)
 source_before={n:sha(ROOT/n) for n in SOURCE};save('render-inputs-before.json',source_before)
 copy_targets(original);preserve('original-targets',original)
 spec=importlib.util.spec_from_file_location('e1_guard',ROOT/'tools/evidence/media/check-study-media.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
 try:guard.validate(decode=False)
 except ValueError as exc:
  assert str(exc)=='Incomplete renderer inputs',str(exc);save('original-stale-control.json',{'rejected':str(exc)})
 else:raise AssertionError('Original moved-input media unexpectedly current')
 phase('render',[sys.executable,'-B','tools/engineering/legs/render-hip-frame-e1.py'],timeout=900)
 copy_targets(candidate);preserve('candidate-targets',candidate)
 receipt=json.loads((ROOT/NAMES[3]).read_text());assert receipt['source_revision']==args.head and receipt['source_hashes']==source_before
 assert receipt['transient_simulation'] is False and len(receipt['timeline'])==288
 phase('real-media-check',[sys.executable,'-B','tools/evidence/media/check-study-media.py'],timeout=240)
 phase('actual-corruption-tests',[sys.executable,'-B','tests/evidence/test-study-media.py'],timeout=360)
 assert {n:sha(ROOT/n) for n in SOURCE}==source_before
 actual=tracked();allowed=set(NAMES)
 assert actual.keys()==initial.keys() and {n:h for n,h in actual.items() if n not in allowed}=={n:h for n,h in initial.items() if n not in allowed}
 results['status']='PASS_SCOPED'
except BaseException as exc:
 results['error']=type(exc).__name__+': '+str(exc);raise
finally:
 errors=[]
 if not processes_quiescent:
  results['status']='FAILED';results['final_guard_errors']=['Owned group not quiescent; no archive or restore race'];save('result.json',results);raise RuntimeError(results['final_guard_errors'][0])
 if initial is not None:
  try:
   observed=OUT/'final-observed-targets';copy_targets(observed);preserve('final-observed-targets',observed)
   save('tracked-after-before-restore.json',tracked())
  except BaseException as exc:errors.append('observation: '+repr(exc))
  finally:
   for n in NAMES:
    try:shutil.copyfile(original/n,ROOT/n)
    except BaseException as exc:errors.append('restore '+n+': '+repr(exc))
  try:
   final=tracked();save('tracked-final-restored.json',final);assert final==initial,'Tracked source/artifacts not restored'
   hardware_final=inventory(ROOT/'hardware');save('hardware-final-restored.json',hardware_final);assert hardware_final==protected_before,'Complete hardware file set/hash not restored'
  except BaseException as exc:errors.append('final guard: '+repr(exc))
 if errors:results['status']='FAILED';results['final_guard_errors']=errors
 save('result.json',results)
 if errors:raise RuntimeError('; '.join(errors))
