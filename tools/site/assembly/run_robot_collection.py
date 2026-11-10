"""ONE bounded source-pinned Robot assembly collection; no adoption or publication.

The phase/reaper functions below are byte-for-byte source copies of the prior
reviewed model collector. This module is import-safe; main is explicit.
"""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,pwd,signal,stat,subprocess,sys,tarfile,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_runtime import tree,fingerprint
from robot_data import inventory
ROOT=None;OUT=None;WORK_DEADLINE=0;processes_quiescent=True;results={}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

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

def phase(name,command,expected=0,timeout=120):
 global processes_quiescent
 timeout=min(timeout,WORK_DEADLINE-time.monotonic());assert timeout>0,'Work deadline reached before '+name
 start=time.monotonic();record={'command':command,'expected_exit':expected,'timeout_seconds':timeout};child=None;cleanup_errors=[]
 print('START '+name,flush=True)
 try:
  with (OUT/(name+'.log')).open('x') as stream:
   processes_quiescent=False
   blocked_before_spawn=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
   def child_unmask():signal.pthread_sigmask(signal.SIG_SETMASK,blocked_before_spawn)
   try:child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_unmask)
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
  try:save('phase-results.json',results)
  except BaseException as exc:cleanup_errors.append('Phase record: '+type(exc).__name__+': '+str(exc))
  try:print('END '+name+' '+json.dumps(record),flush=True)
  except BaseException as exc:cleanup_errors.append('Phase log: '+type(exc).__name__+': '+str(exc))
 if cleanup_errors:raise RuntimeError('; '.join(cleanup_errors))
 assert processes_quiescent,'Owned group not quiescent; no archive'
 assert record.get('exit')==expected,name+' failed/incomplete; retain actual logs'

def main(argv=None):
 global ROOT,OUT,WORK_DEADLINE,processes_quiescent,results
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--contract-json',required=True);p.add_argument('--source',required=True)
 a=p.parse_args(argv);cfg=json.loads(a.contract_json)
 ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
 os.umask(0o077);sys.dont_write_bytecode=True
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',GIT_OPTIONAL_LOCKS='0',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
 assert OUT.is_dir() and not OUT.is_relative_to(ROOT) and not ROOT.is_relative_to(OUT)
 assert pwd.getpwuid(os.getuid()).pw_name==cfg['slot_user'],'Unexpected runtime-sharing job slot'
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==a.source
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],text=True).strip()
 assert os.environ.get('SLURM_CPUS_PER_TASK')=='4','Four scheduler CPUs must be requested'
 allowed=sorted(os.sched_getaffinity(0));assert len(allowed)>=4
 os.sched_setaffinity(0,set(allowed[:4]));assert len(os.sched_getaffinity(0))==4
 assert not os.environ.get('LD_PRELOAD') and not os.environ.get('LD_LIBRARY_PATH')
 assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
 def interrupted(n,f):raise KeyboardInterrupt('received signal '+str(n))
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
 WORK_DEADLINE=time.monotonic()+1140
 results={'status':'FAILED_OR_INCOMPLETE','adoption_approved':False,'phases':{},'guards':{},'errors':[],'source':a.source}
 venv=Path(cfg['venv']);toolkit=Path(cfg['toolkit']);candidate=OUT/'candidate'
 before={};primary=None;passed=False
 try:
  for role,path in (('runtime',venv),('toolkit',toolkit)):
   before[role]=tree(path);save(role+'-before.json',before[role])
   assert fingerprint(before[role])==cfg[role+'_fingerprint'],role+' differs from reviewed retained identity'
  before['tracked']=inventory(ROOT/'hardware');save('hardware-before.json',before['tracked'])
  before['source']={x:sha(ROOT/x) for x in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if x}
  save('tracked-before.json',before['source'])
  phase('collect',[str(venv/'bin/python'),'-I','-B',str(ROOT/'tools/site/assembly/collect_robot_parts.py'),'--out',str(candidate),'--toolkit',str(toolkit)],timeout=600)
  phase('generate',[str(venv/'bin/python'),'-I','-B',str(ROOT/'tools/site/assembly/export_robot_guide.py'),'--collection',str(candidate/'collection.json'),'--out',str(OUT/'guides')],timeout=90)
  passed=True
 except BaseException as exc:
  primary=exc;results['original_error']=type(exc).__name__+': '+str(exc);raise
 finally:
  # Every guard is attempted independently after native children have settled.
  if processes_quiescent:
   checks=(('runtime',lambda:tree(venv),before.get('runtime')),('toolkit',lambda:tree(toolkit),before.get('toolkit')),
           ('hardware',lambda:inventory(ROOT/'hardware'),before.get('tracked')),
           ('tracked',lambda:{x:sha(ROOT/x) for x in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if x},before.get('source')))
   for role,capture,original in checks:
    try:
     value=capture();save(role+'-after.json',value);results['guards'][role]=original is not None and value==original
    except BaseException as exc:results['errors'].append(role+': '+str(exc));results['guards'][role]=False
   try:
    status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],text=True).strip()
    results['guards']['clean_source']=not status;save('source-status-after.json',status)
   except BaseException as exc:results['errors'].append('Source status: '+str(exc))
   for label,path in (('candidate',candidate),('guides',OUT/'guides')):
    if not path.exists():continue
    try:
     members=inventory(path)
     assert len(members)<=1000 and sum(p['bytes'] for p in members.values())<=512*1024*1024
     save(label+'-members.json',members)
     archive=OUT/(label+'-produced.tgz')
     with tarfile.open(archive,'w:gz') as tar:
      for name in sorted(members):
       info=tar.gettarinfo(str(path/name),arcname=name);info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
       with (path/name).open('rb') as stream:tar.addfile(info,stream)
     results[label+'_archive_sha256']=sha(archive)
    except BaseException as exc:results['errors'].append(label+' archive: '+str(exc))
  else:results['errors'].append('Owned groups not quiescent; no archive raced them')
  results['processes_quiescent']=processes_quiescent
  ok=passed and processes_quiescent and not results['errors'] and set(results['guards'])=={'runtime','toolkit','hardware','tracked','clean_source'} and all(results['guards'].values())
  results['status']='PASS_SCOPED_COLLECTION' if ok else 'FAILED_OR_INCOMPLETE'
  try:save('final-result.json',results);print(json.dumps(results),flush=True)
  except BaseException:
   if primary is None:raise
  if not ok and primary is None:raise SystemExit(1)


if __name__=='__main__':main()
