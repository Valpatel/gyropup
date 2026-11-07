"""Collect one genuine E1 field with the retained read-only runtime; no adoption."""
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

def worker_preflight_code():
    """Return the exact native-worker identity probe, without executing it."""
    return "import hashlib,json,platform,sys\nfrom pathlib import Path\nfrom importlib.metadata import version\nimport gmsh,cadquery,cadagent\ncontract=json.loads(Path(sys.argv[1]).read_text());runtime=json.loads(Path(sys.argv[2]).read_text())\nassert platform.machine()==contract['platform'] and platform.python_version()==contract['python_version']\nassert Path(cadagent.__file__).resolve().is_relative_to(Path(runtime['toolkit']).resolve()/'src/cadagent')\nactual={name:(gmsh.__version__ if name=='gmsh' else version(name)) for name in contract['versions']}\nassert actual==contract['versions']\nmapped={}\nfor line in Path('/proc/self/maps').read_text().splitlines():\n path=Path(line.split()[-1])\n if path.name in contract['mapped_libraries']:\n  assert path.resolve()==Path(runtime['libraries'][path.name]).resolve()\n  mapped.setdefault(path.name,set()).add(hashlib.sha256(path.read_bytes()).hexdigest())\nassert mapped=={n:{h} for n,h in contract['mapped_libraries'].items()}\nprint(json.dumps({'versions':actual,'mapped_libraries':{n:list(v)[0] for n,v in mapped.items()},'python_version':platform.python_version(),'architecture':platform.machine(),'module_origin_verified':True}))\n\n"


def main():
    global ROOT,OUT,processes_quiescent,results
    ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);p.add_argument('--runtime',required=True);args=p.parse_args()
    assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt('received signal '+str(signum))))
    processes_quiescent=True
    results={'source':args.head,'status':'FAILED','adoption_approved':False,'phases':{},'scope':'One 4mm P2 hip_frame/E1 static field; video, strength qualification and broader issue criteria remain separate'}
    errors=[];before=None;hw=None;runtime_before=None;runtime=None;original=None;cfg=None
    MEDIA=ROOT/'hardware/exports/leg/fea/hip-frame-e1-media'

    def tracked():
        return {n:{'sha256':sha(ROOT/n),'bytes':(ROOT/n).stat().st_size} for n in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0') if n}

    def runtime_snapshot():
        v=Path(runtime['venv']);toolkit=Path(runtime['toolkit']);libs=runtime['libraries'];rows={}
        # Existing environment links are recorded, not followed as directories; file
        # links also bind their actual resolved bytes. No runtime file is written.
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
        py={q.relative_to(toolkit/'src/cadagent').as_posix():sha(q) for q in sorted((toolkit/'src/cadagent').rglob('*.py'))}
        return {'venv':rows,'interpreter_sha256':sha(v/'bin/python'),'toolkit_python':py,
                'toolkit_head':subprocess.check_output(['git','-C',str(toolkit),'rev-parse','HEAD'],text=True).strip(),
                'toolkit_status':subprocess.check_output(['git','-C',str(toolkit),'status','--porcelain'],text=True),
                'libraries':{name:sha(Path(path)) for name,path in libs.items()}}

    try:
        assert OUT.is_dir() and not OUT.is_relative_to(ROOT)
        assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
        assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
        assert not any(k.startswith('GYROPUP_') for k in os.environ)
        cfg=json.loads((ROOT/'.agents/plans/leg-control/e1-field-inputs.json').read_text())
        contract_path=ROOT/'.agents/plans/leg-control/e1-runtime-contract.json'
        assert sha(contract_path)==cfg['runtime_contract_sha256'];contract=json.loads(contract_path.read_text())
        assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==cfg['hardware_tree']
        assert len(cfg['inputs'])==101
        for n,h in cfg['inputs'].items():
            assert sha(ROOT/n)==h
            assert hashlib.sha256(subprocess.check_output(['git','show',args.head+':'+n])).hexdigest()==h
        for n,h in cfg['original_targets'].items():assert sha(ROOT/n)==h
        runtime=json.loads(Path(args.runtime).read_text())
        assert set(runtime)=={'venv','toolkit','libraries'}
        assert set(runtime['libraries'])==set(contract['mapped_libraries'])
        assert Path(runtime['venv']).is_absolute() and Path(runtime['toolkit']).is_absolute()
        assert not Path(runtime['venv']).is_relative_to(ROOT) and not Path(runtime['toolkit']).is_relative_to(ROOT)
        before=tracked();hw=inventory(ROOT/'hardware');runtime_before=runtime_snapshot()
        save('project-before.json',before);save('hardware-before.json',hw);save('runtime-before.json',runtime_before)
        assert runtime_before['toolkit_python']==contract['toolkit_python']
        assert runtime_before['toolkit_head']==contract['toolkit_revision'] and not runtime_before['toolkit_status'].strip()
        assert runtime_before['libraries']==contract['mapped_libraries']
        original=OUT/'original-media';shutil.copytree(MEDIA,original);archive('original-media',original)
        # Process-local loading is selected before Python/hashlib starts. No install,
        # chmod, user desktop or mutable shared checkout is involved.
        native_env=dict(os.environ)
        native_env.update(LD_PRELOAD=':'.join(runtime['libraries'][n] for n in ('libcrypto.so.3','libssl.so.3')),
                          PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONPATH=str(ROOT),
                          OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_MAX_THREADS='1',
                          MPLBACKEND='Agg',MPLCONFIGDIR=str(OUT/'matplotlib-cache'))
        os.environ.clear();os.environ.update(native_env)
        python=str(Path(runtime['venv'])/'bin/python')
        # This worker preflight imports the actual packages and hashes the libraries
        # mapped in that very process. Filesystem discovery alone is not acceptance.
        code=worker_preflight_code()
        phase('actual-worker-runtime',[python,'-B','-c',code,str(contract_path),args.runtime],timeout=90)
        phase('six-path-controls',[python,'-B','tests/evidence/test-study-media.py','ProducerPaths','RendererPaths'],timeout=60)
        phase('genuine-field',['prlimit','--as=25769803776','--cpu=3600:3610','--',python,'-B','tools/engineering/legs/export-hip-frame-e1.py'],timeout=900)
        # No historical object fetch is needed: the fresh receipt must bind the
        # actual clean executed HEAD already present in this immutable checkout.
        receipt=json.loads((MEDIA/'field-receipt.json').read_text())
        assert receipt['source_revision']==args.head and receipt['source_hashes']==cfg['inputs']
        assert receipt['toolkit_sources_sha256']==contract['toolkit_python']
        assert receipt['versions']=={k:contract['versions'][k] for k in receipt['versions']}
        assert {x['name']:x['sha256'] for x in receipt['mapped_runtime_libraries']}==contract['mapped_libraries']
        assert len(receipt['mapped_runtime_libraries'])==4
        phase('actual-field-validator',[python,'-B','tools/evidence/media/check-study-media.py','--field-only'],timeout=90)
        phase('eight-path-stage-controls',[python,'-B','tests/evidence/test-study-media.py','ProducerPaths','RendererPaths','FieldStage'],timeout=90)
        candidate=OUT/'candidate';candidate.mkdir()
        for n in cfg['targets']:shutil.copyfile(ROOT/n,candidate/Path(n).name)
        assert set(inventory(candidate))=={'field-receipt.json','hip_frame-E1.json','hip_frame-E1.png'}
        archive('candidate',candidate);results['status']='PASS_FIELD_CANDIDATE_ONLY'
    except BaseException as exc:
        results['original_error']=type(exc).__name__+': '+str(exc);raise
    finally:
        # Independent final observations, including when an earlier capture fails.
        if processes_quiescent:
            try:
                if original is not None:
                    partial=OUT/'observed-media';shutil.copytree(MEDIA,partial);archive('observed-media',partial)
            except BaseException as exc:errors.append('Observed archive: '+type(exc).__name__+': '+str(exc))
            try:
                if original is not None:
                    assert MEDIA==ROOT/'hardware/exports/leg/fea/hip-frame-e1-media'
                    shutil.rmtree(MEDIA);shutil.copytree(original,MEDIA)
            except BaseException as exc:errors.append('Restore: '+type(exc).__name__+': '+str(exc))
        else:errors.append('Nonquiescent group: no archive/restore attempted')
        for label,call,expected in [('project-after.json',tracked,before),('hardware-after.json',lambda:inventory(ROOT/'hardware'),hw),('runtime-after.json',runtime_snapshot,runtime_before)]:
            try:
                if expected is not None:
                    actual=call();save(label,actual);assert actual==expected
            except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
        try:
            status=subprocess.check_output(['git','status','--porcelain'],text=True);save('project-status-after.json',{'porcelain':status});assert not status.strip()
        except BaseException as exc:errors.append('Project status: '+type(exc).__name__+': '+str(exc))
        if errors:results['final_guard_errors']=errors;results['status']='FAILED'
        try:save('result.json',results)
        except BaseException as exc:
            errors.append('Final result write: '+type(exc).__name__+': '+str(exc));results['status']='FAILED';print(errors[-1],file=sys.stderr)
        if errors and 'original_error' not in results:raise RuntimeError('; '.join(errors))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
