"""Collect unchanged native turret design gates; no adoption or physical qualification."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tarfile, time, signal, ctypes
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
sys.path.insert(0,str(ROOT));os.environ['PYTHONPATH']=str(ROOT)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def tracked():return {n:sha(ROOT/n) for n in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if n}
def inventory(directory):
 rows={}
 for p in sorted(directory.rglob('*')):
  mode=p.lstat().st_mode
  if stat.S_ISDIR(mode):continue
  if not stat.S_ISREG(mode):raise ValueError('Nonregular output: '+p.relative_to(directory).as_posix())
  rows[p.relative_to(directory).as_posix()]={'bytes':p.stat().st_size,'sha256':sha(p)}
 return rows
def archive(label,directory):
 rows=inventory(directory);save(label+'-inventory.json',rows)
 with tarfile.open(OUT/(label+'.tgz'),'w:gz') as tar:
  for n in rows:
   info=tar.gettarinfo(str(directory/n),arcname=n);info.uid=info.gid=0;info.uname=info.gname=''
   with (directory/n).open('rb') as source:tar.addfile(info,source)
 save(label+'-archive.json',{'sha256':sha(OUT/(label+'.tgz')),'files':len(rows)})
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
# The fleet worker is Linux. Reap only this executor's orphaned descendants.
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(36,1,0,0,0)==0,'Linux child subreaper required'
def interrupted(signum,frame):raise KeyboardInterrupt('received signal '+str(signum))
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
processes_quiescent=True
def phase(name,command,expected=(0,),timeout=10500):
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
  record['seconds']=time.monotonic()-start;result['phases'][name]=record;save('result.json',result)
  print('END '+name+' '+json.dumps(record),flush=True)
  assert processes_quiescent,'Owned group not quiescent; do not race archive/restore'
 assert record.get('exit') in expected,name+' failed/incomplete; actual logs retained'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
result={'status':'FAILED','source':args.head,'phases':{},'scope':'actual native turret gates only; collection is not engineering acceptance or adoption'}
before=None;hardware_before=None
original=OUT/'original-targets';candidate=OUT/'candidate-targets';allowed=set()
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
 assert 'GYROPUP_CAD_PARAMS' not in os.environ
 before=tracked();save('tracked-before.json',before)
 hardware_before=inventory(ROOT/'hardware');save('hardware-before.json',hardware_before)
 allowed={'hardware/exports/turret/gates.json',*('hardware/exports/turret/gates/'+n for n in (
   'connectivity.json','connectivity.dot','hopper.json','path.json','sweep.json','ammo_range.json',
   'ammo_path_22.8.json','ammo_pockets_22.8.json','fasteners.json','fasteners.md','motion_aim.json','motion_mechanisms.json'))}
 assert len(allowed)==13 and allowed<=set(before)
 for name in sorted(allowed):
  target=original/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 archive('original-targets',original)
 import hardware.cad.turret.turret_gates as gates
 source_names=(*gates.GEOMETRY_SOURCES,'hardware/cad/turret/turret_gates.py',
               'hardware/exports/turret/feed/pile.json','hardware/exports/turret/launch/launch3d.json')
 bound={name:sha(ROOT/name) for name in source_names};save('actual-gate-inputs-before.json',bound)
 frozen=json.loads((ROOT/'.agents/plans/turret-recovery/native-gate-inputs.json').read_text())
 assert bound==frozen['files']
 fingerprint=gates.geometry_fingerprint();save('actual-gate-fingerprint.json',{'fingerprint':fingerprint})
 phase('actual-gate-source-contracts',[sys.executable,'-B','-m','pytest','tests/hardware/turret/test_turret_gate_sources.py','-q','-p','no:cacheprovider'],timeout=120)
 # This is the unchanged real CLI. Exit1 is retained as an engineering failure
 # only if the complete fresh report below proves every gate actually finished.
 phase('native-turret-gates',[sys.executable,'-B','hardware/cad/turret/turret_gates.py'],expected=(0,1))
 for name in sorted(allowed):
  target=candidate/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 archive('candidate-targets',candidate)
 report=json.loads((ROOT/'hardware/exports/turret/gates.json').read_text())
 required={'connectivity','hopper','path','sweep','ammo_range','fasteners','motion_mechanisms','motion_aim'}
 assert set(report['gates'])==set(report['seconds'])==required
 assert report['fingerprint']==gates.geometry_fingerprint()==fingerprint
 assert report['ok'] is all(item['ok'] for item in report['gates'].values())
 assert result['phases']['native-turret-gates']['exit']==(0 if report['ok'] else 1)
 assert {name:sha(ROOT/name) for name in source_names}==bound
 details={}
 for name in required:
  row=json.loads((ROOT/('hardware/exports/turret/gates/'+name+'.json')).read_text())
  assert row['schema']=='cadagent.gate/1' and row['physical_fit_verified'] is False
  assert row['pass'] is report['gates'][name]['ok']
  details[name]={'pass':row['pass'],'status':row['status'],'counts':row['counts']}
 aim=json.loads((ROOT/'hardware/exports/turret/gates/motion_aim.json').read_text())
 tilt_ranges=[density['range'] for group in aim['groups'] for density in group['density'] if density['joint']=='tilt']
 geometry=gates.tu.Geo()
 assert tilt_ranges==[[-geometry.tilt_max,-geometry.tilt_min]],'Actual aim gate did not cover both current mechanical stops'
 save('actual-aim-range.json',{'range_about_positive_y_deg':tilt_ranges,'model_upper_deg':geometry.tilt_max,'model_lower_deg':geometry.tilt_min})
 save('actual-gate-outcomes.json',details)
 if report['ok']:
  assert gates.stored()==report
  result['engineering_result']='all scoped model gates passed; no physical qualification'
 else:
  try:gates.stored()
  except gates.GateFailure as exc:result['strict_builder_rejection']=str(exc)
  else:raise AssertionError('Failing gate report escaped the unchanged strict builder reader')
  result['engineering_result']='completed model gate failure; block scene build and investigate actual findings'
 result['status']='COMPLETE_COLLECTION'
except BaseException as exc:
 result['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 errors=[]
 if not processes_quiescent:
  result['status']='FAILED';result['final_guard_errors']=['Owned process group not quiescent; no racing observation/archive/restoration']
  save('result.json',result)
  raise RuntimeError(result['final_guard_errors'][0])
 if before is not None:
  try:
   current=tracked();save('tracked-after-generation.json',current)
   replacement={n:current[n] for n in allowed if n in current}
   if current!=before|replacement:errors.append('Unexpected tracked output/source mutation')
   partial=OUT/'final-observed-targets'
   for name in sorted(allowed):
    if (ROOT/name).is_file() and not (ROOT/name).is_symlink():
     target=partial/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
   archive('final-observed-targets',partial)
  except BaseException as exc:errors.append('Observation: '+type(exc).__name__+': '+str(exc))
  finally:
   for name in sorted(allowed):
    try:
     if (original/name).is_file():shutil.copyfile(original/name,ROOT/name)
    except BaseException as exc:errors.append('Restore '+name+': '+type(exc).__name__+': '+str(exc))
  try:
   final=tracked();save('tracked-final-restored.json',final)
   if final!=before:errors.append('Tracked inputs not restored')
   protected=inventory(ROOT/'hardware');save('hardware-final-restored.json',protected)
   if protected!=hardware_before:errors.append('Complete hardware path/byte set changed')
  except BaseException as exc:errors.append('Final guard: '+type(exc).__name__+': '+str(exc))
 if errors:result['status']='FAILED';result['final_guard_errors']=errors
 save('result.json',result)
 if errors:raise RuntimeError('; '.join(errors))
