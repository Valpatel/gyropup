"""Collect the existing genuine limits and complete turret-on-J501 scene; no adoption or physical qualification."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,stat,subprocess,sys,tarfile,time,signal,ctypes
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
sys.path.insert(0,str(ROOT));os.environ['PYTHONPATH']=str(Path(os.environ['CANONICAL_TOOLKIT_DIR']).resolve()/'src')+os.pathsep+str(ROOT)
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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
results={'source':args.head,'status':'FAILED','phases':{},'scope':'existing limits, complete box ball-path coverage and full 80-mesh bench scene only; immutable reference/browser/physical acceptance remains separate'}
initial=None;protected=None;replacement={};original=OUT/'original-targets';candidate=OUT/'candidate-targets'
ADAPTER=OUT/'adapter-produced';SCENE=OUT/'scene-produced'
LIMIT='hardware/exports/turret/limits.json'
BOX_REPORT='hardware/exports/turret/lidar/box.json'
BOX_PLOT='hardware/exports/turret/lidar/box-limit.png'
allowed=set();cfg=None;before_inputs=None

def archive_once(label,directory):
    if not directory.exists():return
    rows=inventory(directory);seal=OUT/(label+'-archive.json')
    if seal.exists():
        assert rows==json.loads((OUT/(label+'-inventory.json')).read_text()),'Preserved producer payload changed'
        assert sha(OUT/(label+'.tgz'))==json.loads(seal.read_text())['sha256'],'Sealed producer archive changed'
    else:archive(label,directory)

def collect_candidate():
    for directory,relative in ((ADAPTER,'hardware/exports/turret/box'),(SCENE,'hardware/exports/sim/turret_box')):
        if directory.exists():
            archive_once(directory.name,directory)
            for name in inventory(directory):
                target=candidate/relative/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(directory/name,target)
    for n,phase_name in ((LIMIT,'limits-generate'),(BOX_REPORT,'box-ball-path-generate'),(BOX_PLOT,'box-ball-path-generate')):
        if (original/n).is_file() and (ROOT/n).is_file() and phase_name in results['phases']:
            target=candidate/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
    if candidate.exists():archive_once('candidate-targets',candidate)

try:
    assert OUT.is_dir() and not OUT.is_relative_to(ROOT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
    assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
    assert 'GYROPUP_CAD_PARAMS' not in os.environ
    cfg=json.loads((ROOT/'.agents/plans/turret-recovery/scene-inputs.json').read_text())
    initial=tracked();save('tracked-before.json',initial)
    protected=inventory(ROOT/'hardware');save('hardware-before.json',protected)
    assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==cfg['hardware_tree']
    from hardware.cad.manufacturing import print_provenance as provenance
    before_inputs=provenance.snapshot(ROOT)
    assert before_inputs['files']==cfg['cad94'] and len(cfg['cad94'])==94
    assert provenance.fingerprint(cfg['cad94'])==cfg['cad94_fingerprint']
    for n,h in cfg['project_context'].items():assert sha(ROOT/n)==h,n
    for n,h in cfg['gate_products'].items():assert sha(ROOT/n)==h,n
    import cadagent
    kit=Path(os.environ['CANONICAL_TOOLKIT_DIR']).resolve()
    assert Path(cadagent.__file__).resolve().is_relative_to(kit/'src') and not kit.is_relative_to(ROOT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()=='2ad426943ce2c7232875e105e50810849f9a3e5e'
    assert before_inputs['toolkit_sources_sha256']=='c2941322d5f3d000d3777b0047567211d06855861fa5e14229d7d7519fef3ed3'
    assert before_inputs['versions']=={'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
    save('source-inputs-before.json',before_inputs)
    jroot=Path(os.environ['J501_DIR']).resolve()
    assert not jroot.is_relative_to(ROOT) and not jroot.is_relative_to(OUT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=jroot,text=True).strip()==cfg['j501']['revision']
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=jroot,text=True).strip()
    jinputs={**cfg['j501']['tracked_files'],**{n:r['sha256'] for n,r in cfg['j501']['view_files'].items()}}
    for n,h in jinputs.items():assert sha(jroot/n)==h,n
    save('j501-inputs-before.json',jinputs)
    import hardware.cad.turret.turret_gates as gates
    report=gates.stored();assert report['ok'] is True
    save('actual-current-gates.json',report)
    spec=importlib.util.spec_from_file_location('motion_reference',ROOT/'tools/engineering/turret/reference-turret-motion.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    allowed={LIMIT,BOX_REPORT,BOX_PLOT,*('hardware/exports/turret/box/'+n for n in (
        'bom.json','box.json','box_deck.step','box_deck.stl','intake_shroud.step','intake_shroud.stl','pod_cover.step','pod_cover.stl','print-plan.json')),
        'hardware/exports/sim/turret_box/manifest.json',*('hardware/exports/sim/turret_box/'+n+'.stl' for n in reference.OWNERS)}
    assert len(allowed)==93 and allowed<=set(initial)
    for n in sorted(allowed):
        target=original/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
    archive('original-targets',original)
    # This actual writer supplies the same JSON to both sims and the real builder.
    phase('limits-generate',[sys.executable,'-B','hardware/cad/turret/turret_limits.py'],timeout=120)
    replacement[LIMIT]=sha(ROOT/LIMIT)
    phase('limits-check',[sys.executable,'-B','hardware/cad/turret/turret_limits.py','--check'],timeout=120)
    junit=OUT/'limits-simulation-tests.xml'
    phase('limits-simulation-controls',[sys.executable,'-B','-m','pytest','software/simulation/test_turret_limits.py','-q','-p','no:cacheprovider','--junitxml='+str(junit)],timeout=120)
    import xml.etree.ElementTree as ET
    suites=ET.parse(junit).getroot();cases=list(suites.iter('testcase'));assert len(cases)==11
    assert not any(list(s.iter(tag)) for s in cases for tag in ('skipped','failure','error'))
    # This existing CLI writes only the box report and its plot; no robot/map outputs.
    phase('box-ball-path-generate',[sys.executable,'-B','hardware/cad/turret/turret_lidar.py','--scene','box'],timeout=600)
    replacement.update({n:sha(ROOT/n) for n in (BOX_REPORT,BOX_PLOT)})
    # Reject incomplete or narrowed evidence before the builder can publish its
    # height-only freshness claim. The identical durable consumer runs again on
    # the genuine manifest below. No synthetic report is supplied to the builder.
    shared_limits=json.loads((ROOT/LIMIT).read_text())
    box_report=json.loads((ROOT/BOX_REPORT).read_text())
    expected_range=[shared_limits['tilt_deg'][k] for k in ('min','max')]
    reference.box_path_coverage(box_report,{'limits':{'tilt_deg':expected_range},'z_tm':reference.PIVOTS['pan'][2]},shared_limits)
    try:
        phase('scene-generate',[sys.executable,'-B','hardware/cad/builders/build_turret_box.py','--out',str(ADAPTER),'--scene',str(SCENE)],timeout=1800)
    finally:
        if processes_quiescent:collect_candidate()
    assert set(inventory(candidate))==allowed
    assert len(inventory(ADAPTER))==9 and len(inventory(SCENE))==81
    manifest=json.loads((SCENE/'manifest.json').read_text())
    reference.manifest_parts(manifest)
    reference.box_path_coverage(box_report,manifest,shared_limits)
    assert manifest['box']['parts']==['base','cover','front_no_gmsl','rear_io','side_hatch']
    assert manifest['j501']['revision']=='0.9-g48r' and manifest['roof_z']==97
    assert manifest['j501']['meshes']=='exports/view (its view meshes)'
    for name in ('base','cover','front_no_gmsl','rear_io','side_hatch'):
        part=next(p for p in manifest['parts'] if p['name']=='j501_'+name)
        assert part['source']=='J501_DIR/exports/view/'+name+'.stl','Unpinned fallback J501 source'
    assert manifest['j501']['parameters_git']['head']==cfg['j501']['revision']
    assert manifest['j501']['parameters_git']['state']=='committed' and manifest['j501']['warning'] is None
    parts={p['name']:p for p in manifest['parts']}
    for name,part in parts.items():
        blob=(SCENE/part['file']).read_bytes();assert hashlib.sha256(blob).hexdigest()==part['sha256']
        points=reference.vertices(blob);reference.landmarks(points)
        if name.startswith('j501_'):
            target=24000 if name in ('j501_base','j501_cover') else 8000
            assert len(points)//3<=target,'Pinned decimation did not reach the existing phone payload target'
    clearance=manifest['checks']['clearance']
    assert clearance['antenna_tilt_up_deg'] and all(float(hi)>=12 for pan,hi in clearance['antenna_tilt_up_deg']), 'Fresh per-pan upper bound needs an actual consumer fix before adoption'
    assert manifest['checks']['design_gates']['ok'] is True
    assert 'assumed' in parts['laser']['role'] and 'actual label/class' in parts['laser']['role']
    muzzle=next(row for row in manifest['journey'] if row['id']=='muzzle')['text']
    assert '-25 to +12 deg' in muzzle and 'Firing is capped at 10 deg' in muzzle and 'pending bench' in muzzle
    assert 'positive tilt and intermediate poses were not checked' in manifest['checks']['exhaust']['note']
    save('actual-scene-observations.json',{'parts':80,'complete_j501_view':True,'limits':manifest['limits'],'checks':manifest['checks'],'immutable_reference_pending':True,'physical_qualification':False})
    # Supply actual outputs to the existing raw-geometry consumers. The new
    # immutable-reference binding test is a mandatory next DAG stage, not waived.
    for n in sorted(allowed):
        replacement[n]=sha(candidate/n);shutil.copyfile(candidate/n,ROOT/n)
    save('temporary-consumer-inputs.json',replacement)
    tests=['SceneFrames.test_all_meshes_valid_and_match_bounds','SceneFrames.test_rotors_are_centered_on_shafts_and_housings_do_not_spin',
           'SceneFrames.test_effects_follow_the_actual_geometry','SceneFrames.test_the_scene_is_one_full_build',
           'SceneFrames.test_ball_path_claim_has_complete_current_range_evidence','ReferenceInputGuards']
    phase('actual-geometry-and-parser-consumers',[sys.executable,'-B','tests/evidence/test-turret-frames.py',*tests],timeout=120)
    assert provenance.snapshot(ROOT)==before_inputs
    assert gates.stored()==report
    assert all(sha(ROOT/n)==h for n,h in cfg['project_context'].items())
    assert all(sha(ROOT/n)==h for n,h in cfg['gate_products'].items())
    assert all(sha(jroot/n)==h for n,h in jinputs.items())
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=jroot,text=True).strip()
    results['status']='PASS_SCOPED'
except BaseException as exc:
    results['original_error']=type(exc).__name__+': '+str(exc)
    raise
finally:
    original_error_active=sys.exc_info()[0] is not None
    errors=[]
    if not processes_quiescent:
        results['status']='FAILED';results['final_guard_errors']=['Owned process group not quiescent; do not race archives/restoration']
        errors.extend(results['final_guard_errors'])
    if processes_quiescent:
        try:collect_candidate()
        except BaseException as exc:errors.append('Complete producer archive: '+str(exc))
        try:
            observed=OUT/'final-observed-targets'
            for n in sorted(allowed):
                src=ROOT/n
                if src.is_file() and not src.is_symlink():
                    target=observed/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
            if observed.exists():archive_once('final-observed-targets',observed)
        except BaseException as exc:errors.append('Observed target archive: '+str(exc))
        try:
            if initial is not None:
                now=tracked();save('tracked-with-temporary-consumer-inputs.json',now)
                if now!=initial|replacement:errors.append('Unexpected tracked source/output mutation')
        except BaseException as exc:errors.append('Observation: '+str(exc))
        finally:
            for n in sorted(allowed):
                try:
                    if (original/n).is_file():shutil.copyfile(original/n,ROOT/n)
                except BaseException as exc:errors.append('Restore '+n+': '+str(exc))
        if initial is not None:
            try:
                final=tracked();save('tracked-final-restored.json',final)
                if final!=initial:errors.append('Full tracked source/products not restored')
            except BaseException as exc:errors.append('Final tracked identity: '+str(exc))
            try:
                restored=inventory(ROOT/'hardware');save('hardware-final-restored.json',restored)
                if restored!=protected:errors.append('Complete hardware membership/bytes changed')
            except BaseException as exc:errors.append('Final hardware identity: '+str(exc))
            try:
                status=subprocess.check_output(['git','status','--porcelain'],text=True).strip()
                save('source-status-final.json',{'porcelain':status})
                if status:errors.append('Checkout not clean after restoration')
            except BaseException as exc:errors.append('Final project status: '+str(exc))
        if cfg is not None and 'jinputs' in globals():
            actual_jinputs={}
            for n in jinputs:
                try:actual_jinputs[n]=sha(jroot/n)
                except BaseException as exc:errors.append('Final J501 input '+n+': '+str(exc))
            try:
                save('j501-inputs-final.json',actual_jinputs)
                if actual_jinputs!=jinputs:errors.append('J501 retained/tracked input changed')
            except BaseException as exc:errors.append('Final J501 identities: '+str(exc))
            try:
                status=subprocess.check_output(['git','status','--porcelain'],cwd=jroot,text=True).strip()
                save('j501-status-final.json',{'porcelain':status})
                if status:errors.append('J501 tracked source changed')
            except BaseException as exc:errors.append('Final J501 status: '+str(exc))
    if errors:results['status']='FAILED';results['final_guard_errors']=errors
    results['adoption_performed']=False;results['immutable_reference_and_browser_acceptance']='pending separate mandatory stage'
    try:save('result.json',results)
    except BaseException as exc:
        errors.append('Final result write: '+type(exc).__name__+': '+str(exc));results['status']='FAILED';results['final_guard_errors']=errors
        try:print('FINAL_RESULT_WRITE_FAILED '+json.dumps(results),flush=True)
        except BaseException:pass
    if errors and not original_error_active:raise RuntimeError('; '.join(errors))
