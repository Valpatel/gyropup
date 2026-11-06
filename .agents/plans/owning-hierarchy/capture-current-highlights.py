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

p=argparse.ArgumentParser(description='Capture current simulator frames; encoding waits for separately reviewed E1 presentation.');p.add_argument('--head',required=True);args=p.parse_args()
results={'source':args.head,'status':'FAILED','phases':{},'scope':'actual480 browser frames and one source-matched static build only; no encoding, dynamics or physical qualification'}
initial=None;hardware_before=None;frames=OUT/'frames'
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
 assert subprocess.check_output(['git','rev-parse','--is-shallow-repository'],text=True).strip()=='false'
 assert os.environ.get('PLAYWRIGHT_CHANNEL')=='chromium'
 assert not os.environ.get('CAPTURE_SHOT') and not os.environ.get('CAPTURE_FRAMES')
 initial=tracked();save('tracked-before.json',initial);hardware_before=inventory(ROOT/'hardware');save('hardware-before.json',hardware_before)
 phase('build',['npm','run','build'],timeout=240)
 preserve('site',ROOT/'dist')
 phase('actual-markdown-consumer',['npm','run','test:markdown'],timeout=120)
 phase('actual-historical-note-consumers',['node','--test','--test-name-pattern=retired catalogue|built historical|every built note','tests/site/layout/test-doc-pages.mjs'],timeout=120)
 phase('privacy',['npm','run','test:privacy'],timeout=120)
 os.environ['CAPTURE_OUTPUT']=str(frames)
 script="""import {createSiteServer} from './tools/site/serve-site.mjs';
const server=createSiteServer();
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
process.env.SITE_URL=`http://127.0.0.1:${server.address().port}`;
try{await import('./tools/evidence/media/capture-highlights.mjs');}
finally{server.closeAllConnections();await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}
"""
 phase('actual-capture',['node','--input-type=module','-e',script],timeout=900)
 preserve('frames',frames)
 spec=importlib.util.spec_from_file_location('actual_encoder',ROOT/'tools/evidence/media/encode-highlights.py');encoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoder)
 capture=json.loads((frames/'capture-receipt.json').read_text());manifest=encoder.frame_manifest(frames)
 assert capture['sourceRevision']==args.head and capture['servedVersion']['revision']==args.head
 assert {r['id']:r['frames'] for r in capture['shots']}==encoder.check.CAPTURE_COUNTS
 assert sum(len(rows) for rows in manifest['shots'].values())==480
 source_hashes={n:sha(ROOT/n) for n in sorted(encoder.check.expected_sources(capture))}
 encoder.check.validate_source_bindings(args.head,source_hashes,capture)
 save('capture-frame-manifest.json',manifest);save('capture-stage-source-bindings.json',{'source':args.head,'source_hashes':source_hashes,'note':'Capture-time bindings only; later encoding must independently bind its actual E1 inputs and immutable encoding revision.'})
 assert tracked()==initial and inventory(ROOT/'hardware')==hardware_before
 results['status']='PASS_SCOPED'
except BaseException as exc:
 results['error']=type(exc).__name__+': '+str(exc);raise
finally:
 errors=[]
 if not processes_quiescent:
  results['status']='FAILED';results['final_guard_errors']=['Owned producer group not quiescent; preserve working files without racing archive'];save('result.json',results);raise RuntimeError(results['final_guard_errors'][0])
 try:
  if frames.exists():preserve('frames',frames)
 except BaseException as exc:errors.append('capture preservation: '+repr(exc))
 if initial is not None:
  try:
   final=tracked();save('tracked-final.json',final);assert final==initial,'Tracked source/artifact changed'
   hardware_final=inventory(ROOT/'hardware');save('hardware-final.json',hardware_final);assert hardware_final==hardware_before,'Complete hardware set/hash changed'
  except BaseException as exc:errors.append('final guard: '+repr(exc))
 if errors:results['status']='FAILED';results['final_guard_errors']=errors
 save('result.json',results)
 if errors:raise RuntimeError('; '.join(errors))
