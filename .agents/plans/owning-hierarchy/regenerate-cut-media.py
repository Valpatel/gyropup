"""Generate explicit cut/thumbnail inputs before conservative CAD receipts; no adoption."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tarfile, time, signal
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
  for n in rows:tar.add(directory/n,arcname=n,recursive=False)
 save(label+'-archive.json',{'sha256':sha(OUT/(label+'.tgz')),'files':len(rows)})
def phase(name,command):
 start=time.monotonic();record={'command':command}
 print('START '+name,flush=True)
 with (OUT/(name+'.log')).open('w') as stream:
  child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   try:
    record['exit']=child.wait(timeout=900)
   except subprocess.TimeoutExpired:
    record['timed_out']=True
  finally:
   # Reap owned descendants even if their leader exits before them.
   try:os.killpg(child.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    child.wait(timeout=5)
   # The leader may already be reaped while an owned descendant remains.
   try:os.killpg(child.pid,signal.SIGKILL)
   except ProcessLookupError:pass
 record['seconds']=time.monotonic()-start;result['phases'][name]=record;save('result.json',result)
 print('END '+name+' '+json.dumps(record),flush=True)
 assert record.get('exit')==0,name+' failed/incomplete; actual logs retained'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
result={'status':'FAILED','source':args.head,'phases':{},'scope':'genuine cut geometry and thumbnails only; no adoption or physical qualification'}
before=None;original=OUT/'original-targets';candidate=OUT/'candidate-targets';allowed=set();replacement={}
try:
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
 assert 'GYROPUP_CAD_PARAMS' not in os.environ
 before=tracked();save('tracked-before.json',before)
 hardware_before=inventory(ROOT/'hardware');save('hardware-before.json',hardware_before)
 old_receipt=json.loads((ROOT/'hardware/catalog/designed-media-validation.json').read_text())
 old_images=json.loads((ROOT/'hardware/catalog/images.json').read_text())
 keys=set(old_receipt['parts']);assert len(keys)==29
 cut_names={'pan_clamp','cradle_plate_l','cradle_plate_r','stop_lug'}
 allowed={'hardware/catalog/images.json','hardware/catalog/designed-media-validation.json','hardware/exports/turret/component-preview/manifest.json',
          *('hardware/exports/turret/component-preview/'+n+'.'+ext for n in cut_names for ext in ('step','stl')),
          *('hardware/exports/thumbs/'+key.replace('/','--')+'.png' for key in keys)}
 assert len(allowed)==40 and allowed<=set(before)
 for name in sorted(allowed):
  target=original/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 archive('original-targets',original)
 from hardware.cad.manufacturing import print_provenance as provenance
 inputs_before=provenance.snapshot(ROOT);save('cad-inputs-before.json',inputs_before)
 assert len(inputs_before['files'])==92
 assert inputs_before['versions']=={'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
 assert inputs_before['toolkit_sources_sha256']=='c2941322d5f3d000d3777b0047567211d06855861fa5e14229d7d7519fef3ed3'
 assert inputs_before['GYROPUP_CAD_PARAMS_sha256'] is None
 phase('cut-generate',[sys.executable,'-B','tools/engineering/turret/export-turret-cut-previews.py'])
 spec=importlib.util.spec_from_file_location('actual_part_media',ROOT/'tools/evidence/media/part-media-generation.py')
 media=importlib.util.module_from_spec(spec);spec.loader.exec_module(media)
 assert set(media.sources())==keys
 phase('media-generate-check',[sys.executable,'-B','tools/evidence/media/part-media-generation.py','--render','--check','--date','2026-11-06'])
 # Preserve ALL genuine outputs before any additional acceptance assertions.
 for name in sorted(allowed):
  target=candidate/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
 archive('candidate-targets',candidate)
 phase('actual-media-consumers',['node','--test','tests/site/media/test-part-media.mjs'])
 receipt=json.loads((ROOT/'hardware/catalog/designed-media-validation.json').read_text())
 images=json.loads((ROOT/'hardware/catalog/images.json').read_text())
 scoped=keys|{k.split('/')[1] for k in ['leg/output_adapter','rig/carriage_plate','turret/pan_clamp']}
 assert {k:v for k,v in images.items() if k not in scoped}=={k:v for k,v in old_images.items() if k not in scoped}
 assert receipt['counts']==old_receipt['counts']=={'body_first_frame':13,'machined_and_cut':16}
 inputs_after=provenance.snapshot(ROOT);save('cad-inputs-after-media.json',inputs_after)
 changed={n for n in inputs_before['files'] if inputs_before['files'][n]!=inputs_after['files'].get(n)}
 assert set(inputs_before['files'])==set(inputs_after['files'])
 assert changed=={'hardware/catalog/images.json','hardware/catalog/designed-media-validation.json'}
 result['catalog_inputs_requiring_subsequent_cad_generation']=sorted(changed)
 result['status']='PASS_SCOPED'
except BaseException as exc:
 result['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 errors=[]
 if before is not None:
  try:
   current=tracked();save('tracked-after-generation.json',current)
   replacement={n:current[n] for n in allowed if n in current}
   if current!=before|replacement:errors.append('Unexpected tracked output/source mutation')
   # Retain even failed or partially generated targets, without calling them accepted.
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
