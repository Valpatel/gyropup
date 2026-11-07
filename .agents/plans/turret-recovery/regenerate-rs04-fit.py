"""Replay the existing RS04 fit-job packager against immutable current inputs."""
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
            info=archive.gettarinfo(str(directory/n),arcname=n);info.uid=info.gid=0;info.uname=info.gname=''
            with (directory/n).open('rb') as source:archive.addfile(info,source)
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
 start=time.monotonic();record={'command':command,'expected_exit':expected};child=None;cleanup_errors=[]
 print('START '+name,flush=True)
 try:
  with (OUT/(name+'.log')).open('w') as stream:
   processes_quiescent=False
   blocked_before_spawn=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
   def child_unmask():signal.pthread_sigmask(signal.SIG_SETMASK,blocked_before_spawn)
   try:
    child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_unmask)
   finally:signal.pthread_sigmask(signal.SIG_SETMASK,blocked_before_spawn)
   try:record['exit']=child.wait(timeout=timeout)
   except subprocess.TimeoutExpired:record['timed_out']=True
 except BaseException as exc:
  record['original_error']=type(exc).__name__+': '+str(exc)
  raise
 finally:
  if child is not None:
   record['pid']=child.pid
   try:
    cleanup=settle_owned_group(child);record['process_cleanup']=cleanup;processes_quiescent=cleanup['group_gone']
   except BaseException as exc:
    processes_quiescent=False;cleanup_errors.append('Settle: '+type(exc).__name__+': '+str(exc))
  record['seconds']=time.monotonic()-start
  if cleanup_errors:record['cleanup_errors']=cleanup_errors
  results['phases'][name]=record
  try:save('result.json',results)
  except BaseException as exc:
   cleanup_errors.append('Phase record: '+type(exc).__name__+': '+str(exc));record['cleanup_errors']=cleanup_errors
  try:print('END '+name+' '+json.dumps(record),flush=True)
  except BaseException as exc:cleanup_errors.append('Phase log: '+type(exc).__name__+': '+str(exc))
 # An active original exception propagates through the non-raising finally above.
 if cleanup_errors:raise RuntimeError('; '.join(cleanup_errors))
 assert processes_quiescent,'Owned group not quiescent; do not race archive/restore'
 assert record.get('exit')==expected,name+' failed/incomplete; actual logs retained'

import tempfile
os.environ['PYTHONPATH']='/tmp/gyropup-223-reader-toolkit-2ad/src'+os.pathsep+str(ROOT)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
HEAD=args.head
results={'source':HEAD,'status':'FAILED','phases':{},'scope':'genuine existing packagers only; no CAD generation, printer connection or qualification'}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
subprocess.run(['git','diff','--quiet','HEAD','--'],check=True)
initial=tracked();save('tracked-before.json',initial)
hardware_before=inventory(ROOT/'hardware');save('hardware-before.json',hardware_before)
from cadagent import mesh3mf,slicer,_deps
spec=importlib.util.spec_from_file_location('fit',ROOT/'tools/evidence/manufacturing/package-fit-job.py');fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)
assert {m.__name__:sha(Path(m.__file__)) for m in (mesh3mf,slicer,_deps)}==fit.TOOLKIT_HELPERS
assert all(Path(m.__file__).resolve().is_relative_to(Path('/tmp/gyropup-223-reader-toolkit-2ad/src')) for m in (mesh3mf,slicer,_deps))
for line in (ROOT/'tools/evidence/manufacturing/fit-job-requirements.txt').read_text().splitlines():
 if line.strip() and not line.startswith('#'):
  import importlib.metadata
  package,version=line.split('==');assert importlib.metadata.version(package)==version
identity=fit.print_slicing.capture(**fit.PROFILES,overrides=fit.OVERRIDES)
assert identity==json.loads(Path('/tmp/gy-fit-wrapup-runtime/captured-identity.json').read_text())
save('engine-profiles-before.json',identity)
fit.input_identity(ROOT)
common=Path.home()/'snap/bambu-studio/common';assert common.is_dir()
NATIVE=Path(tempfile.mkdtemp(prefix='gyropup-hierarchy-fit-',dir=common))
save('owned-native-output.json',{'path':str(NATIVE),'preserve_on_failure':True})
for label,relative in [('rs04-original','hardware/exports/leg/rs04-fit-job')]:preserve(label,ROOT/relative)
old_zip=ROOT/'hardware/exports/leg/rs04-fit-job.zip'
assert old_zip.is_file() and not old_zip.is_symlink()
shutil.copyfile(old_zip,OUT/'rs04-original.zip')
save('original-zip.json',{'sha256':sha(old_zip),'bytes':old_zip.stat().st_size})
os.environ.pop('WAYLAND_DISPLAY',None)
assert all(Path(p).is_file() for p in ('/usr/bin/xvfb-run','/usr/bin/Xvfb','/usr/bin/dbus-run-session'))
os.environ['GDK_BACKEND']='x11'
deadline=time.monotonic()+90
cpus=','.join(str(n) for n in sorted(os.sched_getaffinity(0))[:2])
try:
 phase('rs04-original-current-verify',[sys.executable,'-B','tools/evidence/manufacturing/package-fit-job.py','--verify',str(ROOT/'hardware/exports/leg/rs04-fit-job')],expected=1,timeout=15)
 assert 'Input or retained-output identity changed' in (OUT/'rs04-original-current-verify.log').read_text(),'Unexpected original package rejection'
 for label,tool in [('rs04','package-fit-job.py')]:
  dest=NATIVE/label
  for mode in ('out','verify'):
   remaining=deadline-time.monotonic();assert remaining>0,'90-second transaction exhausted'
   phase(label+'-'+mode,['/usr/bin/xvfb-run','-a','--auth-file',str(NATIVE/'xauthority'),'-s','-screen 0 1024x768x24 -nolisten tcp','taskset','-c',cpus,sys.executable,'-B','tools/evidence/manufacturing/'+tool,'--'+mode,str(dest)],timeout=remaining)
 results['status']='PASS_SCOPED'
except BaseException as exc:
 results['original_error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 original_error_active=sys.exc_info()[0] is not None
 errors=[]
 if not processes_quiescent:
  results['status']='FAILED';errors.append('Owned native group not quiescent; no archive race')
 if processes_quiescent:
  for label in ('rs04',):
   try:
    preserve(label+'-current',NATIVE/label)
    if results['status']=='PASS_SCOPED':
     import zipfile
     rows=inventory(NATIVE/label);zip_path=OUT/(label+'-current.zip')
     with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
      for name in sorted(rows):bundle.write(NATIVE/label/name,arcname='rs04-fit-job/'+name)
     with zipfile.ZipFile(zip_path) as bundle:
      assert len(bundle.namelist())==len(set(bundle.namelist()))==len(rows)
      assert {name:{'bytes':len(bundle.read(name)),'sha256':hashlib.sha256(bundle.read(name)).hexdigest()} for name in bundle.namelist()}=={'rs04-fit-job/'+name:row for name,row in rows.items()}
     save(label+'-zip.json',{'sha256':sha(zip_path),'files':len(rows),'bytes':zip_path.stat().st_size})
   except BaseException as exc:errors.append('Archive '+label+': '+str(exc))
  try:
   after=fit.print_slicing.capture(**fit.PROFILES,overrides=fit.OVERRIDES);save('engine-profiles-after.json',after)
   assert after==identity,'Engine/profiles changed'
  except BaseException as exc:errors.append('Engine/profile guard: '+type(exc).__name__+': '+str(exc))
  try:
   final=tracked();save('tracked-after.json',final);assert final==initial,'Original source/packages changed'
  except BaseException as exc:errors.append('Tracked guard: '+type(exc).__name__+': '+str(exc))
  try:
   hardware_after=inventory(ROOT/'hardware');save('hardware-after.json',hardware_after);assert hardware_after==hardware_before,'Hardware changed'
  except BaseException as exc:errors.append('Hardware guard: '+type(exc).__name__+': '+str(exc))
 if errors:results['status']='FAILED';results['errors']=errors
 results['native_output_preserved']=True;results['adoption_performed']=False
 try:save('result.json',results)
 except BaseException as exc:
  errors.append('Final result write: '+type(exc).__name__+': '+str(exc));results['status']='FAILED';results['errors']=errors
  try:print('FINAL_RESULT_WRITE_FAILED '+json.dumps(results),flush=True)
  except BaseException:pass
 if errors and not original_error_active:raise RuntimeError('; '.join(errors))
