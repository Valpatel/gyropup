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
HEAD=os.environ['GYROPUP_EXPECTED_HEAD'];PIN='2ad426943ce2c7232875e105e50810849f9a3e5e'
results={'source':HEAD,'status':'FAILED','phases':{},'scope':'three existing genuine connector producers; no adoption, service/strength/physical qualification'}
CANDIDATE=OUT/'connector3';CANDIDATE.mkdir()
IN=Path(os.environ['FLEET_RUN_IN'])/'connector-private'
preflight=json.loads((OUT/'preflight.json').read_text())
initial=tracked();save('tracked-before.json',initial)
original_hardware=inventory(ROOT/'hardware');save('hardware-before.json',original_hardware)
original=OUT/'original-consumer-inputs';original.mkdir()
replacements={};private_copies=[];before=None
REL='docs/research/carrier-service-connectors/'
RECEIPTS=('private-input-diagnosis.json','external-pose.json','support-candidate.json')
PUBLIC={'carrier-support-candidate.step','C3-support-candidate.step','C3-support-layout.step'}
def preserve_once(label,directory):
 if directory==CANDIDATE:
  rows=inventory(directory)
  allowed=set(RECEIPTS)|{'public/'+n for n in PUBLIC}
  assert set(rows)<=allowed,'Unexpected candidate member: retain remote for private inspection'
  private_hashes={r['sha256'] for r in preflight['staged_private'].values()}
  assert not any(r['sha256'] in private_hashes for r in rows.values()),'Raw private payload cannot be archived'
 if (OUT/(label+'-inventory.json')).exists():
  assert inventory(directory)==json.loads((OUT/(label+'-inventory.json')).read_text()),'preserved output changed'
 else:preserve(label,directory)
def replace(identity,candidate):
 old=original/identity;old.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/identity,old)
 replacements[identity]=sha(candidate);shutil.copyfile(candidate,ROOT/identity)
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
 assert 'GYROPUP_CAD_PARAMS' not in os.environ
 import cadagent
 from hardware.cad.manufacturing import print_provenance as provenance
 kit=Path(os.environ['GYROPUP_TOOLKIT_DIR']).resolve();assert not kit.is_relative_to(ROOT)
 assert Path(cadagent.__file__).resolve().is_relative_to(kit/'src/cadagent')
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()==PIN
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=kit,text=True).strip()
 before=provenance.snapshot(ROOT)
 config=json.loads((ROOT/'.agents/plans/turret-recovery/cad-inputs-scene-final.json').read_text())
 frozen={'files':config['files'],'source_closure_sha256': 'a510bd881217d91015769fbecbbfcabffa8db5f96d1909d3f8d8de0aac91609d'}
 assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==config['hardware_tree']=='e1ee146e4261ab4f2cc33d57ffc7b6659e89d0e9'
 assert before['files']==frozen['files'] and len(before['files'])==94
 assert provenance.fingerprint(before['files'])==frozen['source_closure_sha256']=='a510bd881217d91015769fbecbbfcabffa8db5f96d1909d3f8d8de0aac91609d'
 assert before['versions']=={'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
 assert before['toolkit_sources_sha256']=='c2941322d5f3d000d3777b0047567211d06855861fa5e14229d7d7519fef3ed3'
 assert before['GYROPUP_CAD_PARAMS_sha256'] is None
 save('cad-inputs-before.json',before)
 for n,row in preflight['staged_private'].items():
  source=IN/n;assert source.is_file() and not source.is_symlink() and sha(source)==row['sha256'] and source.stat().st_size==row['bytes']
  target=ROOT/'hardware'/n;assert not target.exists()
  target.parent.mkdir(parents=True,exist_ok=True);private_copies.append(target);shutil.copyfile(source,target)
 assert len(private_copies)==5
 for label,tool,report in [('inputs','inputs',RECEIPTS[0]),('pose','pose',RECEIPTS[1]),('support','support',RECEIPTS[2])]:
  command=[sys.executable,'-B','tools/evidence/interfaces/check-carrier-connector-'+tool+'.py','--out',str(CANDIDATE/report)]
  if label=='support':command+=['--public-out',str(CANDIDATE/'public')]
  phase('connector-'+label,command,timeout=900)
  assert provenance.snapshot(ROOT)==before
 # Preserve complete normal product BEFORE any consumer assertions or source replacement.
 preserve_once('connector3-produced',CANDIDATE)
 expected=set(RECEIPTS)|{'public/'+n for n in PUBLIC};assert set(inventory(CANDIDATE))==expected
 for n in RECEIPTS:
  receipt=json.loads((CANDIDATE/n).read_text());assert receipt['inputs']==before and receipt['readiness'] is False
 support=json.loads((CANDIDATE/RECEIPTS[2]).read_text())
 assert support['bounded_geometry_checks_pass'] is True and len(support['checks'])==58 and all(c['pass'] is True for c in support['checks'])
 assert support['panel_retention_qualified'] is False and support['load_screen']['structural_readiness'] is False
 assert support['rigid_module_hardware_complete'] is False
 assert set(support['public_artifact_sha256'])==PUBLIC
 for n,h in support['public_artifact_sha256'].items():assert sha(CANDIDATE/'public'/n)==h
 for n in RECEIPTS:replace(REL+n,CANDIDATE/n)
 for n in PUBLIC:replace('hardware/exports/turret/base-board-service/connectors/'+n,CANDIDATE/'public'/n)
 save('temporary-consumer-inputs.json',replacements)
 for label in ('inputs','pose','support'):
  phase('connector-'+label+'-actual-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-carrier-connector-'+label+'.py'],timeout=180)
 assert provenance.snapshot(ROOT)==before
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()==PIN
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=kit,text=True).strip()
 results['status']='PASS_SCOPED'
except BaseException as exc:
 results['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 errors=[]
 if not processes_quiescent:
  results['status']='FAILED';results['final_guard_errors']=['Owned group not quiescent: do not race output archival/restoration'];save('result.json',results)
  raise RuntimeError(results['final_guard_errors'][0])
 try:preserve_once('connector3-produced',CANDIDATE)
 except BaseException as exc:errors.append('Candidate archive: '+str(exc))
 try:
  current=tracked();save('tracked-before-restoration.json',current)
  if current!=initial|replacements:errors.append('Unexpected tracked source/output mutation')
  preserve_once('original-consumer-inputs',original)
 except BaseException as exc:errors.append('Observation: '+str(exc))
 finally:
  for identity in replacements:
   try:shutil.copyfile(original/identity,ROOT/identity)
   except BaseException as exc:errors.append('Restore: '+identity+': '+str(exc))
  for path in reversed(private_copies):
   try:path.unlink()
   except FileNotFoundError:pass
   except BaseException as exc:errors.append('Private cleanup: '+path.relative_to(ROOT).as_posix()+': '+str(exc))
 try:
  final=tracked();save('tracked-final-restored.json',final)
  if final!=initial:errors.append('Tracked restoration failed')
  hardware_after=inventory(ROOT/'hardware');save('hardware-final-restored.json',hardware_after)
  if hardware_after!=original_hardware:errors.append('Complete hardware membership/bytes changed')
  if before is not None and provenance.snapshot(ROOT)!=before:errors.append('Final CAD94/toolkit identity differs')
 except BaseException as exc:errors.append('Final guard: '+str(exc))
 if errors:results['status']='FAILED';results['final_guard_errors']=errors
 results['adoption_performed']=False;results['private_payloads_archived']=False
 save('result.json',results)
 if errors:raise RuntimeError('; '.join(errors))
