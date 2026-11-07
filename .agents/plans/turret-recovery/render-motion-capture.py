"""Run existing real two-engine turret motion and capture all480 highlights on one genuine build."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,stat,subprocess,sys,tarfile,time,signal,ctypes
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
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
TOOLKIT=Path(os.environ['MOTION_TOOLKIT_DIR']).resolve();TOOLKIT_REV='2ad426943ce2c7232875e105e50810849f9a3e5e'
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt('received signal '+str(signum))))
results={'source':args.head,'status':'FAILED','phases':{},'scope':'existing real two-engine turret motion/asset/fault/interlock controls and all480 browser highlight frames; no encode/adoption/physical qualification'}
processes_quiescent=True;initial=None;hw=None;errors=[]
frames=OUT/'frames';motion=OUT/'motion'
def archive_once(label,directory):
 if not directory.exists():return
 rows=inventory(directory);seal=OUT/(label+'-archive.json')
 if seal.exists():
  assert rows==json.loads((OUT/(label+'-inventory.json')).read_text())
  assert sha(OUT/(label+'.tgz'))==json.loads(seal.read_text())['sha256']
 else:archive(label,directory)
def hosted(module):
 return "import {createSiteServer} from './tools/site/serve-site.mjs';\nconst server=createSiteServer();\nawait new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});\nprocess.env.SITE_URL=`http://127.0.0.1:${server.address().port}`;\ntry{await import("+json.dumps('./'+module)+");}\nfinally{server.closeAllConnections();await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}\n"
try:
 assert OUT.is_dir() and not OUT.is_relative_to(ROOT)
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
 assert os.environ.get('PLAYWRIGHT_CHANNEL')=='chromium'
 assert not any(os.environ.get(n) for n in ('CAPTURE_SHOT','CAPTURE_FRAMES','GYROPUP_CAD_PARAMS'))
 initial=tracked();hw=inventory(ROOT/'hardware');save('tracked-before.json',initial);save('hardware-before.json',hw)
 for name in ('node','npm','ffmpeg','ffprobe'):assert shutil.which(name)
 assert subprocess.check_output(['node','--version'],text=True).strip()=='v22.23.4'
 assert subprocess.check_output(['npm','--version'],text=True).strip()=='10.9.9'
 fixture=json.loads((ROOT/'tests/fixtures/turret-motion-reference.json').read_text());assert fixture['source']['revision']=='ab493a369fa6ffa2eda29ae153a5db44b88a2b39'
 phase('current-nine-frame-consumers',[sys.executable,'-B','tests/evidence/test-turret-frames.py'],timeout=60)
 spec=importlib.util.spec_from_file_location('actual_highlight_guard',ROOT/'tools/evidence/media/check-highlights.py');check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
 required=check.required_capture_inputs();assert all(check.project_path(n.lstrip('/')).is_file() for n in required)
 save('predependency-bindings.json',{'source':args.head,'required_capture_inputs':{n:sha(check.project_path(n.lstrip('/'))) for n in sorted(required)},'fixture_sha256':sha(ROOT/'tests/fixtures/turret-motion-reference.json'),'package_lock_sha256':sha(ROOT/'package-lock.json')})
 if subprocess.check_output(['git','rev-parse','--is-shallow-repository'],text=True).strip()=='true':phase('full-history',['git','fetch','--unshallow','origin'],timeout=600)
 assert subprocess.check_output(['git','rev-parse','--is-shallow-repository'],text=True).strip()=='false'
 for revision in ('a12cf8e73f337274174c56e14c22832250acf284','e7b512870a39259a04a4930e2908af84001bc84e','e93b3bbce57ee36fc966e8ba4513f05273a75967'):
  if subprocess.run(['git','cat-file','-e',revision+'^{commit}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:phase('history-'+revision[:8],['git','fetch','--no-tags','origin',revision],timeout=180)
  subprocess.run(['git','cat-file','-e',revision+'^{commit}'],check=True)
 save('history-proof.json',{'full_history':True,'actual_historical_field_leg_converter_present':True})
 phase('npm-ci',['npm','ci','--no-audit','--no-fund'],timeout=600)
 phase('browser-downloads',['npx','--no-install','playwright','install','chromium','webkit'],timeout=600)
 preflight="import {chromium,webkit} from '@playwright/test';import assert from 'node:assert/strict';import{createRequire}from'node:module';const require=createRequire(import.meta.url);assert.equal(require('@playwright/test/package.json').version,'1.56.1');for(const [name,engine] of Object.entries({chromium,webkit})){const b=await engine.launch({headless:true,...(name==='chromium'?{args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{} )});try{assert.equal(b.version(),name==='chromium'?'141.0.7390.37':'26.0');console.log(JSON.stringify({name,version:b.version()}));}finally{await b.close();}}"
 phase('actual-browser-launches',['node','--input-type=module','-e',preflight],timeout=120)
 assert not TOOLKIT.exists() and not TOOLKIT.is_relative_to(ROOT)
 phase('toolkit-init',['git','init','-q',str(TOOLKIT)],timeout=30)
 phase('toolkit-remote',['git','-C',str(TOOLKIT),'remote','add','origin','https://github.com/Valpatel/cad-agent.git'],timeout=30)
 phase('toolkit-fetch',['git','-C',str(TOOLKIT),'fetch','-q','--depth','1','origin',TOOLKIT_REV],timeout=180)
 phase('toolkit-sparse-init',['git','-C',str(TOOLKIT),'sparse-checkout','init','--cone'],timeout=30)
 phase('toolkit-sparse-set',['git','-C',str(TOOLKIT),'sparse-checkout','set','src/cadagent'],timeout=30)
 phase('toolkit-checkout',['git','-C',str(TOOLKIT),'checkout','-q','--detach','FETCH_HEAD'],timeout=30)
 assert subprocess.check_output(['git','-C',str(TOOLKIT),'rev-parse','HEAD'],text=True).strip()==TOOLKIT_REV
 phase('trace-runtime',[sys.executable,'-m','pip','install','-q','numpy==2.5.4'],timeout=180)
 os.environ['PYTHONPATH']=str(TOOLKIT/'src')
 trace_runner=OUT/'trace-cli.py'
 trace_runner.write_text("import sys\nfrom pathlib import Path\nimport cadagent,cadagent.motion_trace as motion,numpy\nassert numpy.__version__=='2.5.4'\nassert Path(motion.__file__).resolve()==Path("+repr(str(TOOLKIT/'src/cadagent/motion_trace.py'))+").resolve()\nfrom cadagent.cli import main\nraise SystemExit(main(sys.argv[1:]))\n")
 save('reference-contract.json',fixture['contract'])
 phase('actual-required-poses',[sys.executable,'-B',str(trace_runner),'motion-trace',str(OUT/'reference-contract.json'),'--poses-only','--output',str(OUT/'required-poses.json')],timeout=30)
 assert json.loads((OUT/'required-poses.json').read_text())==fixture['poses']
 phase('build',['npm','run','build'],timeout=240)
 archive_once('site',ROOT/'dist')
 phase('actual-markdown-consumer',['npm','run','test:markdown'],timeout=120)
 phase('actual-historical-note-consumers',['node','--test','--test-name-pattern=retired catalogue|built historical|every built note','tests/site/layout/test-doc-pages.mjs'],timeout=120)
 phase('privacy',['npm','run','test:privacy'],timeout=120)
 for engine in ('chromium','webkit'):
  os.environ['PLAYWRIGHT_BROWSER']=engine;os.environ['TEST_OUTPUT']=str(motion/engine)
  phase('actual-motion-'+engine,['node','--input-type=module','-e',hosted('tests/site/models/test-turret-motion.mjs')],timeout=300)
  phase('actual-trace-cli-'+engine,[sys.executable,'-B',str(trace_runner),'motion-trace',str(motion/engine/'contract.json'),str(motion/engine/(engine+'-trace.json')),'--output',str(motion/engine/'motion-report.json'),'--tolerance-mm','.02'],timeout=60)
  report=json.loads((motion/engine/'motion-report.json').read_text());assert report['status']=='pass' and report['required_pose_count']==47 and report['sample_count']==47 and report['tolerance_mm']==.02
 archive_once('motion',motion)
 os.environ['PLAYWRIGHT_BROWSER']='chromium';os.environ['CAPTURE_OUTPUT']=str(frames)
 phase('actual480-capture',['node','--input-type=module','-e',hosted('tools/evidence/media/capture-highlights.mjs')],timeout=900)
 archive_once('frames',frames)
 spec=importlib.util.spec_from_file_location('actual_encoder',ROOT/'tools/evidence/media/encode-highlights.py');encoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoder)
 capture=json.loads((frames/'capture-receipt.json').read_text());manifest=encoder.frame_manifest(frames)
 assert capture['sourceRevision']==args.head and capture['servedVersion']['revision']==args.head
 assert {r['id']:r['frames'] for r in capture['shots']}==encoder.check.CAPTURE_COUNTS
 assert sum(len(rows) for rows in manifest['shots'].values())==480
 source_hashes={n:sha(ROOT/n) for n in sorted(encoder.check.expected_sources(capture))}
 encoder.check.validate_source_bindings(args.head,source_hashes,capture)
 save('capture-frame-manifest.json',manifest);save('capture-stage-source-bindings.json',{'source':args.head,'source_hashes':source_hashes,'note':'Actual complete capture bindings only; encode/full decode/fault checks remain separate.'})
 assert tracked()==initial and inventory(ROOT/'hardware')==hw
 results['status']='PASS_SCOPED'
except BaseException as exc:results['original_error']=type(exc).__name__+': '+str(exc);raise
finally:
 for label,call,expected in [('tracked-final.json',tracked,initial),('hardware-final.json',lambda:inventory(ROOT/'hardware'),hw)]:
  try:
   actual=call();save(label,actual);assert expected is None or actual==expected
  except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
 try:
  status=subprocess.check_output(['git','status','--porcelain'],text=True);save('source-status-final.json',{'porcelain':status});assert not status.strip()
 except BaseException as exc:errors.append('Project status: '+type(exc).__name__+': '+str(exc))
 try:
  if (TOOLKIT/'.git').exists():
   head=subprocess.check_output(['git','-C',str(TOOLKIT),'rev-parse','HEAD'],text=True).strip();status=subprocess.check_output(['git','-C',str(TOOLKIT),'status','--porcelain'],text=True);save('toolkit-status-final.json',{'head':head,'porcelain':status});assert head==TOOLKIT_REV and not status.strip()
 except BaseException as exc:errors.append('Toolkit status: '+type(exc).__name__+': '+str(exc))
 if processes_quiescent:
  for label,directory in [('site',ROOT/'dist'),('motion',motion),('frames',frames)]:
   try:archive_once(label,directory)
   except BaseException as exc:errors.append(label+' preservation: '+type(exc).__name__+': '+str(exc))
 else:errors.append('Nonquiescent owned process group; no archive writes')
 if errors:results['status']='FAILED';results['final_guard_errors']=errors
 try:save('result.json',results)
 except BaseException as exc:errors.append('Final result write: '+type(exc).__name__+': '+str(exc));print(errors[-1],file=sys.stderr);results['status']='FAILED'
 if errors and 'original_error' not in results:raise RuntimeError('; '.join(errors))
print(json.dumps(results,indent=2))
