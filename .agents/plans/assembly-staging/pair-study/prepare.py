"""Reproduce the pure study plan with all native imports forbidden."""
from pathlib import Path
import argparse,builtins,hashlib,json,runpy,sys
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('checkout',type=Path);p.add_argument('frame_bundle',type=Path)
p.add_argument('toolkit',type=Path);p.add_argument('out',type=Path)
a=p.parse_args();root=a.checkout.resolve();plans=root/'.agents/plans/assembly-staging'
assert not a.out.exists()
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
core='5c29c9e2abf2562baa72a05248f23de054b8241e'
sys.argv=[str(root/'tools/site/assembly/robot_native_pairs.py'),
 '--frame-bundle',str(a.frame_bundle),'--frame-manifest',str(plans/'native-263/frame-members.json'),
 '--frame-manifest-sha',sha(plans/'native-263/frame-members.json'),
 '--frame-report-sha',sha(plans/'native-263/frame-report.json'),
 '--witnesses',str(plans/'arrival-witnesses.json'),'--witnesses-sha',sha(plans/'arrival-witnesses.json'),
 '--baseline-guide',str(plans/'pair-study/baseline-guide.json'),
 '--toolkit',str(a.toolkit),'--toolkit-revision',core,'--out',str(a.out)]
original=builtins.__import__
def no_native(name,*args,**kwargs):
 if name.split('.')[0] in ('cadquery','OCP','vtk','vtkmodules'):
  raise AssertionError('Pure study attempted native import: '+name)
 return original(name,*args,**kwargs)
builtins.__import__=no_native
try:
 try:runpy.run_path(sys.argv[0],run_name='__main__')
 except SystemExit as exc:assert exc.code==0
finally:builtins.__import__=original
plan=json.loads((a.out/'plan.json').read_text())
assert (len(plan['predecessor_rows']),plan['candidate_rows'],plan['excluded_rows'],len(plan['controls']),len(plan['queries']))==(1126,74,1052,22,90)
receipt={'schema':'gyropup.native-pair-pure-preflight/1','date':'2026-11-10','pass':True,
 'native_import_guard':'cadquery/OCP/vtk/vtkmodules imports forbidden throughout actual CLI execution',
 'native_queries':False,'frame_job':263,'plan_sha256':sha(a.out/'plan.json'),
 'source_receipt_sha256':sha(a.out/'source.json'),'helper_sha256':sha(root/'tools/site/assembly/robot_native_pairs.py'),
 'preparation_harness_sha256':sha(Path(__file__)),'core':core,'predecessor_rows':1126,'cad_candidates':74,
 'cad_exclusions':1052,'labelled_controls':22,'unique_query_contexts':90,
 'qualification':'Exact staged helper/input bytes; no immutable executed implementation commit claimed. No native path verdict.'}
(a.out/'pure-preflight.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
