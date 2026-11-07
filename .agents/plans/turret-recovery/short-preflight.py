from pathlib import Path
import os,json,hashlib,subprocess,stat,importlib.util
ROOT=Path.cwd().resolve();OUT=Path(os.environ['FLEET_RUN_OUT']).resolve();IN=Path(os.environ['FLEET_RUN_IN'])/'connector-private'
assert not OUT.is_relative_to(ROOT) and not IN.resolve().is_relative_to(OUT)
HEAD=os.environ['GYROPUP_EXPECTED_HEAD']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2)+'\n')
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
assert 'GYROPUP_CAD_PARAMS' not in os.environ
EXPECTED_CONTEXT = {'tools/evidence/interfaces/check-carrier-connector-inputs.py': '6e2cc8af0bf757303092136af15116ac2ece46fc8949ce2d5dedf0be52494ccf', 'tools/evidence/interfaces/check-carrier-connector-pose.py': '464066db1cdaf9e84f5914c867784e2b97c43bb40d1b1e2fd225a9a8618063eb', 'tools/evidence/interfaces/check-carrier-connector-support.py': '2ea1f292653e1be41f96be44ac233536600edda63f9552d1d9148a7946d59c43', 'docs/research/carrier-service-connectors/private-inputs.json': 'db7318f705e1966a93b07bacbab153eaa5fa9bc03a3d6a8114fff3a573382348', 'docs/research/carrier-service-connectors/support-hardware-catalog.json': '61e5e3d8d6152d0e35ffdb77406a63fa8338879ffabb20bc4a155f0861cb717e', '.agents/plans/turret-recovery/cad-inputs-final.json': '75314ffe6bcd906e0d9e342633d35f28ec7272288e98589566623b58ac5384e9'}
EXPECTED_PRIVATE = {'vendor/molex-43020-1200/430201200.stp': {'bytes': 182800, 'sha256': '25dda729f39ad81389a81244c08fb0f2861a3ff0874eb429e954a6fabea9934d', 'runtime': 'hardware/vendor/molex-43020-1200/430201200.stp'}, 'vendor/molex-43025-1200/430251200.stp': {'bytes': 248693, 'sha256': '6bedba78a6d02e8cdec0fcb674d6a112a2b329a78610eb0ee70967ead8ff8f78', 'runtime': 'hardware/vendor/molex-43025-1200/430251200.stp'}, 'vendor/molex-43030-0010/430300010.stp': {'bytes': 212668, 'sha256': '81937008bcc8bc6181f357a6c0a8f58094c53e688c3e17ad1452a2e21a96493b', 'runtime': 'hardware/vendor/molex-43030-0010/430300010.stp'}, 'vendor/mcmaster/91290A113/91290A113.norm.step': {'bytes': 3106457, 'sha256': '4ac68e49d4435961b2295703fb854e8f09176a038d3ee8d63b7ee61010e5d289', 'runtime': 'hardware/vendor/mcmaster/91290A113/91290A113.norm.step'}, 'vendor/mcmaster/90592A085/90592A085.norm.step': {'bytes': 496989, 'sha256': '15e61a3d9e1c3159c501e6a714492eb8db30630879f2bcb73238d02469dd1c75', 'runtime': 'hardware/vendor/mcmaster/90592A085/90592A085.norm.step'}}
for n,h in EXPECTED_CONTEXT.items():assert sha(ROOT/n)==h,n
actual={}
for p in IN.rglob('*'):
 mode=p.lstat().st_mode
 if stat.S_ISDIR(mode):continue
 assert stat.S_ISREG(mode) and not p.is_symlink(),'nonregular staged input'
 actual[p.relative_to(IN).as_posix()]={'bytes':p.stat().st_size,'sha256':sha(p)}
assert actual=={n:{k:v[k] for k in ('bytes','sha256')} for n,v in EXPECTED_PRIVATE.items()},'exact staged set/size/hash mismatch'
spec=importlib.util.spec_from_file_location('preflight_provenance',ROOT/'hardware/cad/manufacturing/print_provenance.py');prov=importlib.util.module_from_spec(spec);spec.loader.exec_module(prov)
config=json.loads((ROOT/'.agents/plans/turret-recovery/cad-inputs-final.json').read_text())
frozen={'files':config['files'],'source_closure_sha256': 'f1a061f346ce7981612b3e2bd40519ac358c28b3e68c5456bd91172aea11dccc'}
assert subprocess.check_output(['git','rev-parse','HEAD:hardware'],text=True).strip()==config['hardware_tree']=='2aedbeccd42010f8c5a645dcadc2336e3997d720'
files={p.relative_to(ROOT).as_posix():sha(p) for p in prov.source_files(ROOT)}
assert len(files)==94 and files==frozen['files'] and prov.fingerprint(files)==frozen['source_closure_sha256']=='f1a061f346ce7981612b3e2bd40519ac358c28b3e68c5456bd91172aea11dccc'
# Actual moved-path reader must reject stale old input while current cache is absent.
spec=importlib.util.spec_from_file_location('private_reader',ROOT/'tools/evidence/interfaces/check-carrier-connector-inputs.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
entry=json.loads(reader.MANIFEST.read_text())['parts'][0];relative=entry['private_file'].removeprefix('references/vendor/')
stale=ROOT/'references/vendor'/relative
assert not stale.exists() and not (ROOT/'hardware/vendor'/relative).exists()
stale.parent.mkdir(parents=True,exist_ok=True)
stale.write_bytes((IN/'vendor'/relative).read_bytes())
try:
 try:reader.private_path(entry)
 except FileNotFoundError:rejected=True
 else:rejected=False
 assert rejected,'stale old-root source rescued missing current input'
finally:
 stale.unlink()
 for p in (stale.parent,*stale.parent.parents):
  if p==ROOT:break
  try:p.rmdir()
  except OSError:break
save('preflight.json',{'head':HEAD,'source_closure_sha256':frozen['source_closure_sha256'],'source_count':94,'context':EXPECTED_CONTEXT,'staged_private':actual,'stale_old_root_rejected':True,'dependencies_not_installed_yet':True})
print('Preflight passed: exact94 sources/context +5 staged private identities, actual stale-old rejection',flush=True)
