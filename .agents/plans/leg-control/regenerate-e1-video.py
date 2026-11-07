"""Genuine standard E1 presentation from the committed field; no solver or adoption."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,ctypes,signal
ROOT=None;OUT=None

def rig_history_revisions(record):
 """Derive both immutable objects consumed by the real rig companion check."""
 if not isinstance(record,dict)or not isinstance(record.get('derivation'),dict):
  raise ValueError('Missing historical rig source identities')
 revisions=(record.get('producer_revision'),record['derivation'].get('converter_revision'))
 if not all(isinstance(v,str)and len(v)==40 and all(c in '0123456789abcdef'for c in v)for v in revisions):
  raise ValueError('Use immutable rig producer and converter revisions')
 return tuple(dict.fromkeys(revisions))

def main():
 global ROOT,OUT
 ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True);args=p.parse_args()
 helper_path=ROOT/'.agents/plans/leg-control/regenerate-e1-field.py'
 spec=importlib.util.spec_from_file_location('e1_owned_lifecycle',helper_path);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 h.ROOT=ROOT;h.OUT=OUT;h.processes_quiescent=True
 result={'source':args.head,'status':'FAILED','adoption_approved':False,'phases':{},'scope':'Standard static-field E1 video only; no native solve or physical qualification'};h.results=result
 assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
 def interrupted(signum,frame):raise KeyboardInterrupt('received signal '+str(signum))
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,interrupted)
 sha=lambda p:h.sha(Path(p));save=h.save;phase=h.phase
 def tracked():return {n:sha(ROOT/n)for n in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0')if n}
 cfg=None;before=None;hw=None;original=None;errors=[];source_before=None;context_before=None
 def copy_targets(directory):
  directory.mkdir(exist_ok=False)
  for n in cfg['targets']:
   target=directory/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
 try:
  assert OUT.is_dir()and not OUT.is_relative_to(ROOT)
  assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
  assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
  assert not any(n.startswith('GYROPUP_')for n in os.environ)
  cfg=json.loads((ROOT/'.agents/plans/leg-control/e1-video-inputs.json').read_text())
  assert sha(helper_path)==cfg['lifecycle_sha256']
  assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==cfg['hardware_tree']
  assert len(cfg['inputs'])==6 and len(cfg['targets'])==5
  for n,digest in cfg['inputs'].items():
   assert sha(ROOT/n)==digest and hashlib.sha256(subprocess.check_output(['git','show',args.head+':'+n])).hexdigest()==digest
  for n,digest in cfg['original_targets'].items():assert sha(ROOT/n)==digest
  for n,digest in cfg['test_context'].items():
   assert sha(ROOT/n)==digest and hashlib.sha256(subprocess.check_output(['git','show',args.head+':'+n])).hexdigest()==digest
  before=tracked();hw=h.inventory(ROOT/'hardware');source_before={n:sha(ROOT/n)for n in cfg['inputs']}
  context_before={n:sha(ROOT/n)for n in cfg['test_context']}
  save('project-before.json',before);save('hardware-before.json',hw);save('render-inputs-before.json',source_before);save('test-context-before.json',context_before)
  original=OUT/'original-targets';copy_targets(original);h.archive('original-targets',original)
  field=json.loads((ROOT/'hardware/exports/leg/fea/hip-frame-e1-media/field-receipt.json').read_text())
  revision=field['source_revision'];assert revision==cfg['field_source']
  rig=json.loads((ROOT/'hardware/exports/leg/rig-media.json').read_text())
  for historical in dict.fromkeys((revision,*rig_history_revisions(rig))):
   if subprocess.run(['git','cat-file','-e',historical+'^{commit}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    phase('actual-source-object-'+historical[:8],['git','fetch','--depth','1','--no-tags','origin',historical],timeout=180)
   assert subprocess.check_output(['git','rev-parse',historical+'^{commit}'],text=True).strip()==historical
  assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==args.head
  assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
  phase('committed-field-check',[sys.executable,'-B','tools/evidence/media/check-study-media.py','--field-only'],timeout=60)
  for tool in ('ffmpeg','ffprobe','node'):assert shutil.which(tool)
  assert subprocess.check_output(['node','--version'],text=True).startswith('v22.')
  phase('actual-rig-historical-preflight',['node','--input-type=module','-e',"import{verifyRigFiles}from'./tools/evidence/media/rig-media.mjs';await verifyRigFiles(process.cwd(),{historical:true,decode:false});console.log('PASS: actual rig producer/converter identities verified before rendering');"],timeout=60)
  assert sha('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')==cfg['font_sha256']
  encoders=subprocess.check_output(['ffmpeg','-hide_banner','-encoders'],text=True,stderr=subprocess.STDOUT);assert 'libx264'in encoders and'libvpx-vp9'in encoders
  phase('owned-render-dependencies',[sys.executable,'-m','pip','install','--disable-pip-version-check',*[n+'=='+v for n,v in cfg['packages'].items()]],timeout=720)
  import importlib.metadata as metadata
  assert {n:metadata.version(n)for n in cfg['packages']}==cfg['packages']
  save('renderer-runtime.json',{'packages':cfg['packages'],'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],'ffprobe':subprocess.check_output(['ffprobe','-version'],text=True).splitlines()[0],'ffmpeg_sha256':sha(shutil.which('ffmpeg')),'ffprobe_sha256':sha(shutil.which('ffprobe'))})
  phase('genuine-standard-render',[sys.executable,'-B','tools/engineering/legs/render-hip-frame-e1.py'],timeout=300)
  candidate=OUT/'candidate-targets';copy_targets(candidate);h.archive('candidate-targets',candidate)
  video=json.loads((ROOT/'hardware/exports/leg/fea/hip-frame-e1-media/video-receipt.json').read_text())
  assert video['source_revision']==args.head and video['source_hashes']==source_before
  assert video['transient_simulation']is False and len(video['timeline'])==288
  phase('actual-full-media-guard',[sys.executable,'-B','tools/evidence/media/check-study-media.py'],timeout=240)
  phase('actual-full-corruption-controls',[sys.executable,'-B','tests/evidence/test-study-media.py'],timeout=360)
  assert {n:sha(ROOT/n)for n in cfg['inputs']}==source_before
  after=tracked();allowed=set(cfg['targets']);assert before.keys()==after.keys()and {n:v for n,v in before.items()if n not in allowed}=={n:v for n,v in after.items()if n not in allowed}
  result['status']='PASS_VIDEO_CANDIDATE_ONLY'
 except BaseException as exc:
  result['original_error']=type(exc).__name__+': '+str(exc);raise
 finally:
  if h.processes_quiescent:
   try:
    if original is not None and original.is_dir():
     observed=OUT/'observed-targets';copy_targets(observed);h.archive('observed-targets',observed)
   except BaseException as exc:errors.append('Observed archive: '+type(exc).__name__+': '+str(exc))
   if original is not None:
    for n in cfg['targets']:
     try:
      if (original/n).is_file():shutil.copyfile(original/n,ROOT/n)
     except BaseException as exc:errors.append('Restore '+n+': '+type(exc).__name__+': '+str(exc))
  else:errors.append('Nonquiescent group; no archive or restore attempted')
  for label,call,expected in [('project-after.json',tracked,before),('hardware-after.json',lambda:h.inventory(ROOT/'hardware'),hw),('render-inputs-after.json',lambda:{n:sha(ROOT/n)for n in cfg['inputs']},source_before),('test-context-after.json',lambda:{n:sha(ROOT/n)for n in cfg['test_context']},context_before)]:
   try:
    if expected is not None:
     actual=call();save(label,actual);assert actual==expected
   except BaseException as exc:errors.append(label+': '+type(exc).__name__+': '+str(exc))
  try:
   status=subprocess.check_output(['git','status','--porcelain'],text=True);save('project-status-after.json',{'porcelain':status});assert not status.strip()
  except BaseException as exc:errors.append('Project status: '+type(exc).__name__+': '+str(exc))
  if errors:result['status']='FAILED';result['final_guard_errors']=errors
  try:save('result.json',result)
  except BaseException as exc:
   errors.append('Final result write: '+type(exc).__name__+': '+str(exc));result['status']='FAILED';print(errors[-1],file=sys.stderr)
  if errors and 'original_error'not in result:raise RuntimeError('; '.join(errors))
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
