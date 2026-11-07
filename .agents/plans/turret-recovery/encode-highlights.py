"""Encode the genuine sealed current capture with the existing movie CLI; no capture or solver."""
from pathlib import Path,PurePosixPath
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
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:(_ for _ in ()).throw(KeyboardInterrupt('received signal '+str(signum))))
results={'source':args.head,'status':'FAILED','adoption_approved':False,'phases':{},'scope':'existing full660-frame/22s encoder, actual full decode/fault/E1/historical-companion guards; no capture/solver/physical qualification'}
processes_quiescent=True;initial=None;hw=None;frame_rows=None;errors=[]
frames=OUT/'frames';candidate=OUT/'candidate';stage=Path(os.environ['FLEET_RUN_IN'])/'current-frames'
def archive_once(label,directory):
 if not directory.exists():return
 rows=inventory(directory);seal=OUT/(label+'-archive.json')
 if seal.exists():assert rows==json.loads((OUT/(label+'-inventory.json')).read_text()) and sha(OUT/(label+'.tgz'))==json.loads(seal.read_text())['sha256']
 else:archive(label,directory)
try:
 assert OUT.is_dir() and not OUT.is_relative_to(ROOT)
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
 initial=tracked();hw=inventory(ROOT/'hardware');save('tracked-before.json',initial);save('hardware-before.json',hw)
 cfg=json.loads((ROOT/'.agents/plans/turret-recovery/highlights-frame-inputs.json').read_text());assert cfg['schema']=='gyropup.highlights-frame-inputs/1'
 assert inventory(stage)==cfg['staged_files']
 frame_rows=json.loads((stage/'frames-inventory.json').read_text());assert len(frame_rows)==481
 assert set(cfg['staged_files'])=={'frames/'+n for n in frame_rows}|{'frames-inventory.json','capture-stage-source-bindings.json'}
 frames.mkdir()
 for name,row in frame_rows.items():
  path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts and str(path)==name
  source=stage/'frames'/name;assert stat.S_ISREG(source.lstat().st_mode)
  assert {'bytes':source.stat().st_size,'sha256':sha(source)}==row
  target=frames/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);target.chmod(0o400)
 assert inventory(frames)==frame_rows
 for tool in ('ffmpeg','ffprobe'):assert shutil.which(tool)
 encoders=subprocess.check_output(['ffmpeg','-hide_banner','-encoders'],text=True,stderr=subprocess.STDOUT);assert all(n in encoders for n in ('libx264','libvpx-vp9','libwebp'))
 filters=subprocess.check_output(['ffmpeg','-hide_banner','-filters'],text=True,stderr=subprocess.STDOUT);assert 'drawtext' in filters
 spec=importlib.util.spec_from_file_location('actual_encoder',ROOT/'tools/evidence/media/encode-highlights.py');encoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoder)
 spec=importlib.util.spec_from_file_location('highlight_prerequisites',ROOT/'tools/evidence/media/highlight_prerequisites.py');prerequisites=importlib.util.module_from_spec(spec);spec.loader.exec_module(prerequisites)
 capture=json.loads((frames/'capture-receipt.json').read_text());assert capture['sourceRevision']==cfg['capture_revision'] and capture['servedVersion']['revision']==cfg['capture_revision']
 for revision in prerequisites.historical_revisions(encoder.check,cfg['capture_revision']):
  if subprocess.run(['git','cat-file','-e',revision+'^{commit}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:phase('source-object-'+revision[:8],['git','fetch','--depth','1','--no-tags','origin',revision],timeout=180)
  assert subprocess.check_output(['git','rev-parse',revision+'^{commit}'],text=True).strip()==revision
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 spec=importlib.util.spec_from_file_location('actual_study_check',ROOT/'tools/evidence/media/check-study-media.py');study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
 study.validate(decode=False)
 manifest=encoder.frame_manifest(frames);assert sum(map(len,manifest['shots'].values()))==480
 source_hashes={n:sha(ROOT/n) for n in sorted(encoder.check.expected_sources(capture))};encoder.check.validate_source_bindings(args.head,source_hashes,capture)
 declared=json.loads((stage/'capture-stage-source-bindings.json').read_text());changed_e1=prerequisites.validate_recorded_stage(encoder.check,declared,source_hashes,cfg['capture_revision'])
 save('actual-source-frame-proof.json',{'capture_job':cfg['capture_job'],'capture_source':cfg['capture_revision'],'encoding_source':args.head,'accepted_capture_archive_sha256':cfg['source_frame_archive']['sha256'],'transport':'unpacked481 regular files; actual bytes checked against staged inventory and frozen config','frame_records':481,'all_current_capture_inputs_exact':True,'historical_stage_source_hashes_verified':True,'updated_E1_insert_paths':changed_e1,'source_hashes':source_hashes})
 original=OUT/'original-highlights';original.mkdir()
 for name in inventory(ROOT/'software/site/assets/highlights'):shutil.copyfile(ROOT/'software/site/assets/highlights'/name,original/name)
 assert len(inventory(original))==6;archive('original-highlights',original)
 phase('actual-encode-and-full-guard',[sys.executable,'-B','tools/evidence/media/encode-highlights.py','--frames',str(frames),'--output',str(candidate),'--threads','4'],timeout=900)
 assert set(inventory(candidate))==prerequisites.candidate_names(encoder.check)
 assert inventory(frames)==frame_rows and tracked()==initial and inventory(ROOT/'hardware')==hw
 results['status']='PASS_SCOPED'
except BaseException as exc:results['original_error']=type(exc).__name__+': '+str(exc);raise
finally:
 for label,call,expected in [('tracked-final.json',tracked,initial),('hardware-final.json',lambda:inventory(ROOT/'hardware'),hw)]:
  try:
   actual=call();save(label,actual);assert expected is None or actual==expected
  except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
 try:
  if frame_rows is not None:assert inventory(frames)==frame_rows;save('frames-final.json',frame_rows)
 except BaseException as exc:errors.append('Frame preservation: '+type(exc).__name__+': '+str(exc))
 try:
  status=subprocess.check_output(['git','status','--porcelain'],text=True);save('source-status-final.json',{'porcelain':status});assert not status.strip()
 except BaseException as exc:errors.append('Project status: '+type(exc).__name__+': '+str(exc))
 if processes_quiescent:
  try:
   if candidate.exists():archive_once('candidate',candidate)
  except BaseException as exc:errors.append('Candidate preservation: '+type(exc).__name__+': '+str(exc))
 else:errors.append('Nonquiescent owned group; candidate not archived')
 if errors:results['status']='FAILED';results['final_guard_errors']=errors
 try:save('result.json',results)
 except BaseException as exc:errors.append('Final result write: '+type(exc).__name__+': '+str(exc));print(errors[-1],file=sys.stderr);results['status']='FAILED'
 if errors and 'original_error' not in results:raise RuntimeError('; '.join(errors))
print(json.dumps(results,indent=2))
