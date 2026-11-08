"""Collect one retained STEP topology inspection; no builder, FEA or adoption."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,stat,subprocess,sys,tarfile,time,signal,ctypes
ROOT=None;OUT=None
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


def tracked(root):
    rows={}
    for name in subprocess.check_output(['git','ls-files','-z'],cwd=root,text=True).split('\0'):
        if not name:continue
        path=root/name;mode=path.lstat().st_mode
        assert stat.S_ISREG(mode),'Tracked nonregular file'
        rows[name]={'sha256':sha(path),'bytes':path.stat().st_size,'mode':stat.S_IMODE(mode)}
    return rows


def runtime_snapshot(runtime):
    v=Path(runtime['venv']);toolkit=Path(runtime['toolkit']);rows={}
    for q in sorted(v.rglob('*')):
        mode=q.lstat().st_mode
        if stat.S_ISDIR(mode):continue
        key=q.relative_to(v).as_posix()
        if stat.S_ISLNK(mode):
            rows[key]={'link':os.readlink(q),'kind':'directory' if q.is_dir() else 'file'}
            if q.is_file():rows[key].update(sha256=sha(q),bytes=q.stat().st_size)
        else:
            assert stat.S_ISREG(mode),'Nonregular retained environment entry'
            rows[key]={'sha256':sha(q),'bytes':q.stat().st_size}
    return {'venv':rows,'interpreter_sha256':sha(v/'bin/python'),
            'toolkit_python':{q.relative_to(toolkit/'src/cadagent').as_posix():sha(q)for q in sorted((toolkit/'src/cadagent').rglob('*.py'))},
            'toolkit_head':subprocess.check_output(['git','-C',str(toolkit),'rev-parse','HEAD'],text=True).strip(),
            'toolkit_status':subprocess.check_output(['git','-C',str(toolkit),'status','--porcelain'],text=True),
            'libraries':{name:sha(Path(path))for name,path in runtime['libraries'].items()}}


def final_observations(result, observations, archive_call, quiescent):
    """Independent guarded observations; no operational code extraction in tests."""
    errors=[]
    if quiescent:
        try:archive_call()
        except BaseException as exc:errors.append('Diagnostic archive: '+type(exc).__name__+': '+str(exc))
    else:errors.append('Nonquiescent group: no archive attempted')
    for label,call,expected in observations:
        try:
            actual=call();save(label,actual);assert actual==expected
        except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
    if errors:result.update(status='FAILED',final_guard_errors=errors)
    try:save('result.json',result)
    except BaseException as exc:
        errors.append('Final result write: '+type(exc).__name__+': '+str(exc))
        result.update(status='FAILED',final_guard_errors=errors)
        try:print(errors[-1],file=sys.stderr)
        except BaseException:pass
    if errors and 'original_error' not in result:raise RuntimeError('; '.join(errors))


def main():
    global ROOT,OUT,results,processes_quiescent
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);p.add_argument('--runtime',type=Path,required=True);args=p.parse_args()
    ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
    # Refuse before installing handlers or entering any finally that writes OUT.
    assert OUT.is_dir() and not OUT.is_relative_to(ROOT) and OUT.stat().st_uid==os.getuid(),'Invalid owned output directory'
    assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt('received signal '+str(signum))))
    processes_quiescent=True
    results={'source':args.head,'status':'FAILED','adoption_approved':False,'phases':{},
             'scope':'Retained STEP import/topology only; no source builder, interfaces, FEA or physical qualification'}
    before=hw=runtime_before=runtime=cfg=None;observations=[]
    diagnostic=OUT/'diagnostic'
    try:
        assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
        assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
        assert not any(k.startswith('GYROPUP_')for k in os.environ)
        assert subprocess.check_output(['git','remote','get-url','origin'],text=True).strip()=='https://github.com/Valpatel/gyropup.git'
        cfg=json.loads((ROOT/'.agents/plans/hip-study/topology-inputs.json').read_text())
        contract_path=ROOT/'.agents/plans/leg-control/e1-runtime-contract.json'
        assert sha(contract_path)==cfg['runtime_contract_sha256'];contract=json.loads(contract_path.read_text())
        assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==cfg['hardware_tree']
        assert len(cfg['cad_sources'])==94
        pins={**cfg['cad_sources'],cfg['step']['path']:cfg['step']['sha256'],cfg['receipt']['path']:cfg['receipt']['sha256'],cfg['worker']['path']:cfg['worker']['sha256']}
        for name,value in pins.items():
            assert sha(ROOT/name)==value,name
            assert hashlib.sha256(subprocess.check_output(['git','show',args.head+':'+name])).hexdigest()==value
        assert subprocess.check_output(['git','rev-parse',args.head+':'+cfg['step']['path']],text=True).strip()==cfg['step']['git_blob']
        assert subprocess.check_output(['git','rev-parse',args.head+':'+cfg['receipt']['path']],text=True).strip()==cfg['receipt']['git_blob']
        runtime=json.loads(args.runtime.read_text());assert set(runtime)=={'venv','toolkit','libraries'}
        assert set(runtime['libraries'])==set(contract['mapped_libraries'])
        for key in ('venv','toolkit'):
            assert Path(runtime[key]).is_absolute() and not Path(runtime[key]).resolve().is_relative_to(ROOT)
        before=tracked(ROOT);save('project-before.json',before)
        hw=inventory(ROOT/'hardware');save('hardware-before.json',hw)
        runtime_before=runtime_snapshot(runtime);save('runtime-before.json',runtime_before)
        assert hashlib.sha256(json.dumps(runtime_before,sort_keys=True,separators=(',',':')).encode()).hexdigest()==cfg['retained_runtime_snapshot_sha256'],'Retained runtime differs from the accepted genuine field run'
        assert runtime_before['toolkit_python']==contract['toolkit_python']
        assert runtime_before['toolkit_head']==contract['toolkit_revision'] and not runtime_before['toolkit_status'].strip()
        assert runtime_before['libraries']==contract['mapped_libraries']
        assert set(cfg['module_inputs'])=={'cadquery','gmsh'}
        for declared in cfg['module_inputs'].values():
            row=runtime_before['venv'][declared['venv_path']]
            assert row['sha256']==declared['sha256']
            assert ('file-symlink' if 'link'in row else 'regular')==declared['kind']
            if 'link'in row:assert hashlib.sha256(row['link'].encode()).hexdigest()==declared['link_target_sha256']
        native_env=dict(os.environ)
        for name in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'):native_env.pop(name,None)
        native_env.update(LD_PRELOAD=':'.join(runtime['libraries'][n]for n in ('libcrypto.so.3','libssl.so.3')),
                          PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONPATH=str(ROOT)+os.pathsep+str(Path(runtime['toolkit'])/'src'),
                          OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_MAX_THREADS='1',
                          MPLBACKEND='Agg',MPLCONFIGDIR=str(OUT/'matplotlib-cache'))
        os.environ.clear();os.environ.update(native_env)
        python=str(Path(runtime['venv'])/'bin/python')
        command=['prlimit','--as=25769803776','--cpu=2400:2410','--',python,'-B',cfg['worker']['path'],
                 '--root',str(ROOT),'--config',str(ROOT/'.agents/plans/hip-study/topology-inputs.json'),
                 '--runtime',str(args.runtime),'--contract',str(contract_path),'--out',str(diagnostic)]
        phase('retained-step-import',command,timeout=600)
        report=json.loads((diagnostic/'worker-result.json').read_text())
        assert report['status']=='PASS_IMPORT_TOPOLOGY_ONLY' and report['step_sha256']==cfg['step']['sha256']
        identities=json.loads((diagnostic/'worker-runtime.json').read_text())
        assert set(identities)=={'before','after'}
        for identity in identities.values():
            assert set(identity['module_origins'])==set(cfg['module_inputs'])
            for name,origin in identity['module_origins'].items():
                assert origin['path']==cfg['module_inputs'][name]['venv_path']
                assert origin['kind']==cfg['module_inputs'][name]['kind']
                assert origin['resolved_path_sha256']==cfg['module_inputs'][name]['resolved_path_sha256']
                assert runtime_before['venv'][origin['path']]['sha256']==origin['sha256']
            for name,value in identity['mapped_venv_libraries'].items():
                assert runtime_before['venv'][name]['sha256']==value
        assert set(inventory(diagnostic))=={'worker-runtime.json','topology.json','worker-result.json'}
        assert sum(x['bytes']for x in inventory(diagnostic).values())<=64*1024**2,'Output bound exceeded; no truncation'
        results.update(status='PASS_IMPORT_TOPOLOGY_ONLY',step=cfg['step'],receipt=cfg['receipt'],baseline=cfg['published_baseline'])
    except BaseException as exc:
        results['original_error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if before is not None:observations.append(('project-after.json',lambda:tracked(ROOT),before))
        if hw is not None:observations.append(('hardware-after.json',lambda:inventory(ROOT/'hardware'),hw))
        if runtime_before is not None:observations.append(('runtime-after.json',lambda:runtime_snapshot(runtime),runtime_before))
        observations.append(('project-status-after.json',lambda:subprocess.check_output(['git','status','--porcelain'],text=True),''))
        def seal():
            if diagnostic.exists():archive('diagnostic',diagnostic)
        final_observations(results,observations,seal,processes_quiescent)
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
