"""Refresh the existing current-CAD README illustration in an isolated fleet checkout; no adoption."""
from pathlib import Path
import argparse,hashlib,json,os,runpy,shutil,stat,subprocess,sys,tarfile,time,signal,ctypes
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

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

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
PROFILE=Path(os.environ['README_ART_PROFILE']).resolve();TOOLKIT=Path(os.environ['README_ART_TOOLKIT']).resolve()
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt('received signal '+str(signum))))
processes_quiescent=True
results={'source':args.head,'status':'FAILED','adoption_approved':False,'phases':{}};before=None;hw=None;cfg=None;errors=[]
def snapshot():
 rows={}
 for n in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0'):
  if not n:continue
  path=ROOT/n;s=path.lstat();assert stat.S_ISREG(s.st_mode)
  rows[n]={'sha256':sha(path),'bytes':s.st_size,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'mode':stat.S_IMODE(s.st_mode)}
 return rows
try:
 assert OUT.is_dir() and not OUT.is_relative_to(ROOT)
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
 assert not any(k.startswith('GYROPUP_') for k in os.environ)
 before=snapshot();hw=inventory(ROOT/'hardware');save('project-before.json',before);save('hardware-before.json',hw)
 helper=runpy.run_path(str(ROOT/'tools/engineering/robot/readme_design.py'));cfg=json.loads((ROOT/helper['CONFIG']).read_text())
 helper['verify_inputs'](ROOT,cfg);helper['verify_public_tree'](ROOT,cfg)
 assert len(cfg['source']['files'])==95
 # The isolated worker is depth1 at executed HEAD; retain the distinct recorded
 # source as an exact object before inspecting its immutable blobs.
 if subprocess.run(['git','cat-file','-e',cfg['source']['revision']+'^{commit}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
  phase('recorded-source-fetch',['git','fetch','--depth','1','--no-tags','origin',cfg['source']['revision']],timeout=180)
 assert subprocess.check_output(['git','rev-parse',cfg['source']['revision']+'^{commit}'],text=True).strip()==cfg['source']['revision']
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
 for n,h in cfg['source']['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',cfg['source']['revision']+':'+n])).hexdigest()==h
 assert subprocess.check_output(['git','rev-parse',cfg['source']['revision']+':hardware'],text=True).strip()==cfg['source']['hardware_tree']
 original=OUT/'original-artifacts';original.mkdir()
 for source,name in ((ROOT/'tools/engineering/robot/current-design.scene.json','current-design.scene.json'),(ROOT/'docs/img/hero/current-design.svg','current-design.svg'),(ROOT/'tools/engineering/robot/current-design.receipt.json','current-design.receipt.json')):shutil.copyfile(source,original/name)
 archive('original-artifacts',original)
 save('input-preflight.json',{'executed_checkout':args.head,'recorded_source':cfg['source'],'helper_sha256':sha(ROOT/'tools/engineering/robot/readme_design.py'),'config_sha256':sha(ROOT/helper['CONFIG']),'profile':cfg['profile'],'toolkit':cfg['toolkit']})
 for role,directory,repository,revision,sparse in [('profile',PROFILE,'https://github.com/mvalancy/mvalancy.git',cfg['profile']['revision'],'tools/hero'),('toolkit',TOOLKIT,'https://github.com/Valpatel/cad-agent.git',cfg['toolkit']['revision'],'software/cadagent')]:
  assert not directory.exists() and not directory.is_relative_to(ROOT)
  phase(role+'-init',['git','init','-q',str(directory)],timeout=30)
  phase(role+'-remote',['git','-C',str(directory),'remote','add','origin',repository],timeout=30)
  phase(role+'-fetch',['git','-C',str(directory),'fetch','-q','--depth','1','origin',revision],timeout=180)
  phase(role+'-sparse-init',['git','-C',str(directory),'sparse-checkout','init','--cone'],timeout=30)
  phase(role+'-sparse-set',['git','-C',str(directory),'sparse-checkout','set',sparse],timeout=30)
  phase(role+'-checkout',['git','-C',str(directory),'checkout','-q','--detach','FETCH_HEAD'],timeout=30)
  assert subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()==revision
  assert not subprocess.check_output(['git','-C',str(directory),'status','--porcelain'],text=True).strip()
 for name,h in cfg['profile']['files'].items():assert sha(PROFILE/'tools/hero'/name)==h
 import tomllib
 assert tomllib.loads((TOOLKIT/'pyproject.toml').read_text())['project']['version']=='0.23.1'
 assert (TOOLKIT/'software/cadagent/__init__.py').is_file()
 phase('dependencies',[sys.executable,'-m','pip','install','-q','cadquery==2.8.0','cadquery-ocp==7.9.3.1.1','numpy==2.5.4','vtk==9.6.2','trimesh==5.2.0','PyYAML==6.0.3','scipy==1.18.1','matplotlib==3.11.2','pillow==13.0.0'],timeout=720)
 phase('runtime-freeze',[sys.executable,'-m','pip','freeze'],timeout=30)
 phase('extract',[sys.executable,'-B','tools/engineering/robot/readme_design.py','extract','--profile',str(PROFILE),'--toolkit',str(TOOLKIT),'--out',str(OUT/'figure')],timeout=1500)
 phase('pure-parity',[sys.executable,'-B','tools/engineering/robot/readme_design.py','check','--profile',str(PROFILE),'--candidate',str(OUT/'figure/candidate')],timeout=120)
 os.environ['README_DESIGN_CANDIDATE']=str(OUT/'figure/candidate')
 phase('ten-existing-controls',[sys.executable,'-B','tests/evidence/media/test-readme-design.py'],timeout=120)
 assert set(inventory(OUT/'figure/candidate'))=={'current-design.scene.json','current-design.svg','current-design.receipt.json'}
 results['status']='PASS_CANDIDATE_ONLY'
except BaseException as exc:results['original_error']=type(exc).__name__+': '+str(exc);raise
finally:
 # All independent identity observations are attempted even if an earlier one fails.
 for label,call,expected in [('project-after.json',snapshot,before),('hardware-after.json',lambda:inventory(ROOT/'hardware'),hw)]:
  try:
   actual=call();save(label,actual);assert expected is None or actual==expected
  except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
 try:
  status=subprocess.check_output(['git','status','--porcelain'],text=True);save('project-status-after.json',{'porcelain':status});assert not status.strip()
 except BaseException as exc:errors.append('Project status: '+type(exc).__name__+': '+str(exc))
 for role,directory in [('profile',PROFILE),('toolkit',TOOLKIT)]:
  try:
   if (directory/'.git').exists():
    head=subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip();status=subprocess.check_output(['git','-C',str(directory),'status','--porcelain'],text=True)
    save(role+'-final.json',{'head':head,'porcelain':status});assert not status.strip()
    if cfg is not None:assert head==cfg[role]['revision']
  except BaseException as exc:errors.append(role+': '+type(exc).__name__+': '+str(exc))
 # Seal a partial or complete genuine extraction independently of identity errors.
 if processes_quiescent:
  try:
   if (OUT/'figure').exists():archive('figure-produced',OUT/'figure')
  except BaseException as exc:errors.append('Figure archive: '+type(exc).__name__+': '+str(exc))
 else:errors.append('Nonquiescent owned process group; figure not archived')
 if errors:results['final_guard_errors']=errors;results['status']='FAILED'
 try:save('result.json',results)
 except BaseException as exc:
  errors.append('Final result write: '+type(exc).__name__+': '+str(exc));results['status']='FAILED';print(errors[-1],file=sys.stderr)
 if errors and 'original_error' not in results:raise RuntimeError('; '.join(errors))
print(json.dumps(results,indent=2))
