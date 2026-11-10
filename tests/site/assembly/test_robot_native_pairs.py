"""Selected-study contracts; dependency doubles never establish CAD evidence."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
import robot_native_pairs as study
from robot_native_playback import IDENTITY,bind_inputs,digest,encode


def declared_operations(guide,order,refs):
    """Explicit pure rule double; production always calls the pinned core API."""
    prior=[];rows=[]
    for step in guide['steps']:
        if step['id'] in refs:continue
        present=prior[:]
        for name in order[step['id']]:
            rows.append({'instance':name,'installed':present[:],'offset_mm':step['offsets_mm'].get(name,[0,0,0]),'step_id':step['id']})
            present.append(name)
        prior=step['parts'][:]
    return rows


def guide_for(order):
    parts=[];steps=[{'id':'overview','parts':[],'offsets_mm':{}}];install={'overview':[]}
    for i,name in enumerate(order):
        parts.append(name);step='s'+str(i)
        steps.append({'id':step,'parts':parts[:],'offsets_mm':{name:[0,60,0]}});install[step]=[name]
    return {'snapshot':{'id':'fixture','source_commit':'a'*40},'model':{'file':'view.json'},
            'source':{'install_order_by_step':install},'steps':steps}


class PairStudy(unittest.TestCase):
    def fixture(self):
        current=guide_for(['fixed','extra','moving']);baseline=guide_for(['fixed','moving','extra'])
        frames=[{'instance':'fixed','cad_bounds_mm':[0,20,0,10,30,10]},
                {'instance':'extra','cad_bounds_mm':[1000,0,0,1010,10,10]},
                {'instance':'moving','cad_bounds_mm':[0,0,0,10,10,10]}]
        witness={'candidate_pairs':[{'moving':'moving'}],'cases':[
            {'id':'hip-after-motor-outward-L','moving':'moving','fixed':'fixed','offset_mm':[0,60,0],
             'max_preterminal_witnesses':0,'terminal_witnesses':0},
            {'id':'motor-through-installed-hip-L','moving':'moving','fixed':'fixed','offset_mm':[0,60,0],
             'max_preterminal_witnesses':1,'terminal_witnesses':0}]}
        return current,frames,witness,baseline

    def test_dedupe_requires_full_installed_context_and_keeps_exclusions(self):
        plan=study.make_plan(*self.fixture(),declared_operations)
        self.assertEqual((len(plan['predecessor_rows']),plan['candidate_rows'],plan['excluded_rows']),(2,1,1))
        self.assertEqual(len(plan['queries']),2)
        self.assertEqual({tuple(q['installed_set']) for q in plan['queries']},{('extra','fixed'),('fixed',)})
        self.assertEqual(len(plan['queries'][0]['contexts']),2)
        self.assertEqual(plan['predecessor_rows'][1]['fixed'],'extra')
        self.assertGreater(max(plan['predecessor_rows'][1]['axis_gap_lower_bounds_mm']),.01)

    def test_direction_and_authored_order_negatives(self):
        current,frames,witness,baseline=self.fixture()
        reversed_case=copy.deepcopy(witness['cases'][0]);reversed_case.update(id='hip-wrong-inward-through-motor-L',offset_mm=[0,-60,0])
        witness['cases'].append(reversed_case)
        plan=study.make_plan(current,frames,witness,baseline,declared_operations)
        self.assertEqual(len(plan['queries']),3)
        self.assertEqual(plan['queries'][-1]['direction'],[0,1,0]);self.assertEqual(plan['queries'][-1]['travel_mm'],60)
        bad=copy.deepcopy(witness);bad['cases'][-1]['offset_mm']=[0,60,0]
        with self.assertRaisesRegex(ValueError,'authored/reversed'):study.make_plan(current,frames,bad,baseline,declared_operations)
        bad_baseline=guide_for(['moving','fixed','extra'])
        with self.assertRaisesRegex(ValueError,'not installed'):study.make_plan(current,frames,witness,bad_baseline,declared_operations)
        frames[0]['cad_bounds_mm'][0]=float('nan')
        with self.assertRaisesRegex(ValueError,'frame bounds'):study.make_plan(current,frames,witness,baseline,declared_operations)

    def test_actual_project_plan_includes_both_cad_only_candidates(self):
        base=ROOT/'.agents/plans/assembly-staging'
        guide=json.loads((ROOT/'software/site/assets/build-guides/combined-wip-540056ba4e59/guide.json').read_text())
        frame=json.loads((base/'native-263/frame-report.json').read_text())
        witness=json.loads((base/'arrival-witnesses.json').read_text());baseline=json.loads((base/'pair-study/baseline-guide.json').read_text())
        self.assertEqual(witness['baseline_guide_sha256'],digest((base/'pair-study/baseline-guide.json').read_bytes()))
        plan=study.make_plan(guide,frame['frames'],witness,baseline,declared_operations)
        self.assertEqual((len(plan['predecessor_rows']),plan['candidate_rows'],plan['excluded_rows'],len(plan['controls']),len(plan['queries'])),(1126,74,1052,22,90))
        candidates={(p['moving'],p['fixed']) for p in plan['predecessor_rows'] if p['candidate']}
        mesh={(p['moving'],p['fixed']) for p in witness['candidate_pairs']}
        self.assertEqual(candidates-mesh,{('L.hip_frame','spacer_screws'),('R.hip_frame','spacer_screws')})
        self.assertEqual(mesh-candidates,set())
        ids={c['case_id']:c for c in plan['controls']}
        queries={q['id']:q for q in plan['queries']}
        for side in ('L','R'):
            old=queries[ids['motor-through-installed-hip-'+side]['query']]
            self.assertIn(side+'.hip_frame',old['installed_set'])
            current=[q for q in plan['queries'] if q['moving']==side+'.motor_front' and any(c['kind']=='candidate' for c in q['contexts'])]
            self.assertTrue(current);self.assertTrue(all(side+'.hip_frame' not in q['installed_set'] for q in current))

    def test_explicit_unperformed_control_selection_preserves_full_plan_and_identity(self):
        base=ROOT/'.agents/plans/assembly-staging'
        guide=json.loads((ROOT/'software/site/assets/build-guides/combined-wip-540056ba4e59/guide.json').read_text())
        frame=json.loads((base/'native-263/frame-report.json').read_text());witness=json.loads((base/'arrival-witnesses.json').read_text())
        baseline=json.loads((base/'pair-study/baseline-guide.json').read_text())
        plan=study.make_plan(guide,frame['frames'],witness,baseline,declared_operations)
        cases={c['case_id']:c['query'] for c in plan['controls']}
        labels=['motor-through-installed-hip-L','motor-wrong-inward-through-cheek-L']
        selection={'schema':'gyropup.native-pair-selection/1','full_plan_sha256':digest(encode(plan)),
                   'query_ids':[cases[c] for c in labels],'case_ids':labels}
        selected=study.select_plan(plan,selection)
        self.assertEqual(len(plan['queries']),90);self.assertEqual(len(selected['queries']),2)
        self.assertEqual(len(selected['selection']['unselected_query_ids']),88)
        self.assertEqual(selected['predecessor_rows'],plan['predecessor_rows'])
        observed={q['id'] for q in json.loads((base/'native-264/report.json').read_text())['queries']}
        self.assertTrue(observed.isdisjoint(selection['query_ids']))
        original={q['id']:q for q in plan['queries']}
        self.assertEqual(selected['queries'],[original[i] for i in selection['query_ids']])
        for fault in ('plan','duplicate','unknown','label','direction'):
            wrong=copy.deepcopy(selection);value=copy.deepcopy(plan)
            if fault=='plan':wrong['full_plan_sha256']='0'*64
            elif fault=='duplicate':wrong['query_ids']=[selection['query_ids'][0]]*2
            elif fault=='unknown':wrong['query_ids'][0]='0'*64
            elif fault=='label':wrong['case_ids'][0]='unrelated-case'
            else:value['queries'][0]['direction'][1]*=-1
            with self.subTest(fault=fault),self.assertRaises(ValueError):study.select_plan(value,wrong)

    def test_failed_progress_stops_and_retains_earlier_result_and_primary_error(self):
        current,frames,witness,baseline=self.fixture();plan=study.make_plan(current,frames,witness,baseline,declared_operations)
        plan['queries'].append({**plan['queries'][-1],'id':'third-query-not-reached'})
        boxes={f['instance']:f['cad_bounds_mm'] for f in frames};world=SimpleNamespace(names=list(boxes),box=boxes.__getitem__,stats={'kernel_queries':2})
        calls=[]
        def sweep(*args,**kwargs):
            calls.append(args)
            return {'state':'clear'} if len(calls)==1 else {'state':'unknown','bad':object()}
        core=SimpleNamespace(tol=None,load_world=lambda *args:world,sweep_pair=sweep)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            with self.assertRaises(TypeError):study.execute_plan(plan,{}, {},frames,core,out,{'fixture':'explicit non-CAD double'},None)
            report=json.loads((out/'report.json').read_text());phase=json.loads((out/'phase.json').read_text())
            self.assertEqual(len(calls),2);self.assertEqual(len(report['queries']),1)
            self.assertEqual(report['queries'][0]['result']['state'],'clear');self.assertFalse(report['complete']);self.assertFalse(report['pass'])
            self.assertEqual(len(report['unchecked_queries']),2)
            self.assertEqual(phase['state'],'incomplete');self.assertTrue(phase['progress_tail_uncertain'])
            self.assertEqual((phase['progress_flushed_records'],phase['progress_fsync_acknowledged_records']),(3,0))

    def test_final_phase_storage_failure_cannot_leave_a_passing_report(self):
        current,frames,witness,baseline=self.fixture();plan=study.make_plan(current,frames,witness,baseline,declared_operations)
        boxes={f['instance']:f['cad_bounds_mm'] for f in frames};world=SimpleNamespace(names=list(boxes),box=boxes.__getitem__,stats={})
        core=SimpleNamespace(tol=None,load_world=lambda *args:world,sweep_pair=lambda *args,**kwargs:{'state':'clear'})
        real=study.write_json;failed=[]
        def write(path,value):
            if path.name=='phase.json' and value.get('state')=='complete' and not failed:
                failed.append(True);raise OSError('explicit final-phase storage fault')
            real(path,value)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(study,'write_json',write):
            out=Path(tmp)
            with self.assertRaisesRegex(OSError,'final-phase storage fault'):
                study.execute_plan(plan,{}, {},frames,core,out,{'fixture':'non-CAD storage control'},None)
            report=json.loads((out/'report.json').read_text());phase=json.loads((out/'phase.json').read_text())
            self.assertFalse(report['pass']);self.assertFalse(report['complete']);self.assertEqual(phase['state'],'incomplete')

    def test_real_cli_dependency_double_returns_nonzero_and_preserves_blocked_report(self):
        # The full entry point executes. These explicitly fake payloads/world
        # check exit/report/guard plumbing, never native geometry behavior.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);frame=root/'frame';frame.mkdir();names=['fixed','moving']
            collection={'source_commit':'a'*40,'producer_inputs':{'fixture':'non-CAD double'},'native_geometry':{'hash_platform':{'fixture':'synthetic'}},
                        'parts':[{'name':name,'sha256':digest(name.encode()),'native_geometry':{'sha256':digest((name+'-not-BREP').encode()),'shape_sha256':'c'*64,'matrix':IDENTITY}} for name in names]}
            raw=encode(collection);guide=guide_for(names);guide['source']['collection_sha256']=digest(raw)
            model=encode({'parts':[{'name':p['name'],'sha256':p['sha256']} for p in collection['parts']]});guide['model']['sha256']=digest(model)
            files={'fixture/guide.json':encode(guide),'fixture/view.json':model};bundle=SimpleNamespace(path='fixture/guide.json',files=files)
            def binder(bundle,payloads,*,producer_hash_platform):
                return {'guide_sha256':digest(bundle.files[bundle.path]),'model_sha256':digest(model),
                        'instances':{n:{'brep_sha256':digest(b),'shape_sha256':'c'*64,'mesh_sha256':digest(n.encode()),'matrix':IDENTITY} for n,b in payloads.items()},'hash_platform':producer_hash_platform}
            payloads={n:(n+'-not-BREP').encode() for n in names};rows,outputs=bind_inputs(collection,digest(raw),[bundle],payloads,binder)
            outputs['source-collection.json']=raw
            outputs['inputs.json']=encode({'collection_sha256':digest(raw),'guides':rows})
            frames=[{'instance':n,'cad_bounds_mm':[0,0,0,10,10,10]} for n in names]
            report={'gate':'assembly-playback-preflight','pass':True,'operations':[],'limits':{'paths_checked':False,'progress_complete':True},
                    'inputs':{'guide_sha256':digest(files[bundle.path]),'model_sha256':digest(model),'source_commit':'a'*40,'producer_hash_platform':collection['native_geometry']['hash_platform']},'frames':frames}
            outputs['reports/fixture.json']=encode(report)
            for name,data in outputs.items():
                path=frame/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(0o600)
            manifest=study.inventory(frame)
            for path in frame.rglob('*'):
                if path.is_file():path.chmod(0o640)
            mp=root/'members.json';mp.write_bytes(encode(manifest));baseline=root/'baseline.json';baseline.write_bytes(encode(guide))
            witness={'baseline_guide_sha256':digest(baseline.read_bytes()),'candidate_pairs':[{'moving':'moving','mesh_sha256':{'moving':digest(b'moving'),'fixed':digest(b'fixed')}}],
                     'cases':[{'id':'hip-after-motor-outward-L','moving':'moving','fixed':'fixed','offset_mm':[0,60,0],
                               'mesh_sha256':{'moving':digest(b'moving'),'fixed':digest(b'fixed')},'max_preterminal_witnesses':0,'terminal_witnesses':0}]}
            wp=root/'witness.json';wp.write_bytes(encode(witness));core=root/'core';package=core/'software/cadagent'
            for relative in ('__init__.py','publish/__init__.py','review/__init__.py','review/gates/__init__.py'):
                path=package/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
            (package/'publish/guides.py').write_text("from types import SimpleNamespace\ndef collect_guides(root,paths):\n return [SimpleNamespace(path=p,files={f.relative_to(root).as_posix():f.read_bytes() for f in root.rglob('*') if f.is_file()}) for p in paths]\n")
            # Reuse the explicit local doubles' source as a dependency module.
            import inspect
            projection=inspect.getsource(declared_operations).replace('declared_operations','playback_operations',1)
            binder_source='''def bind_playback_breps(bundle,payloads,*,producer_hash_platform):
 model=json.loads(bundle.files['fixture/view.json'])
 return {'guide_sha256':digest(bundle.files[bundle.path]),'model_sha256':digest(bundle.files['fixture/view.json']),
 'instances':{n:{'brep_sha256':digest(b),'shape_sha256':'c'*64,'mesh_sha256':digest(n.encode()),'matrix':IDENTITY} for n,b in payloads.items()},'hash_platform':producer_hash_platform}
def _load_world(*args):
 return SimpleNamespace(names=['fixed','moving'],box=lambda n:[0,0,0,10,10,10],stats={'kernel_queries':1})
'''
            (package/'review/gates/playback.py').write_text("import json,hashlib\nfrom types import SimpleNamespace\nIDENTITY="+repr(IDENTITY)+"\ndigest=lambda x:hashlib.sha256(x).hexdigest()\n"+projection+binder_source)
            (package/'review/gates/assembly.py').write_text("class AccessOptions:\n def __init__(self,**kwargs):pass\ndef sweep_pair(*args,**kwargs):return {'state':'blocked','overlap_mm3':1,'fixture':'explicit non-CAD dependency double'}\n")
            (package/'review/gates/relations.py').write_text('class Tolerances:touch_mm=0.01\n')
            subprocess.check_call(['git','init','-q',str(core)]);subprocess.check_call(['git','-C',str(core),'add','.'])
            subprocess.check_call(['git','-C',str(core),'-c','core.hooksPath=/dev/null','-c','user.name=Fixture','-c','user.email=fixture@example.com','commit','-qm','Explicit non-CAD study double'])
            revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
            command=[sys.executable,'-B',str(ROOT/'tools/site/assembly/robot_native_pairs.py'),'--frame-bundle',str(frame),
                     '--frame-manifest',str(mp),'--frame-manifest-sha',digest(mp.read_bytes()),'--frame-report-sha',digest(encode(report)),
                     '--witnesses',str(wp),'--witnesses-sha',digest(wp.read_bytes()),'--baseline-guide',str(baseline),
                     '--toolkit',str(core),'--toolkit-revision',revision,'--out',str(root/'result'),'--execute']
            result=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr);self.assertIn('Selected pair study complete',result.stdout)
            saved=json.loads((root/'result/report.json').read_text());self.assertTrue(saved['complete']);self.assertFalse(saved['pass'])
            self.assertEqual(saved['counts'],{'blocked':1});self.assertFalse(saved['queries'][0]['transient_path_complete'])
            self.assertFalse(saved['all_assembly_paths_checked']);self.assertEqual((root/'result/inputs/source-collection.json').read_bytes(),raw)
            full_plan=json.loads((root/'result/plan.json').read_text())
            selection={'schema':'gyropup.native-pair-selection/1','full_plan_sha256':digest(encode(full_plan)),
                       'query_ids':[full_plan['queries'][0]['id']],'case_ids':['hip-after-motor-outward-L']}
            sp=root/'selection.json';sp.write_bytes(encode(selection));selected=command[:]
            selected[selected.index('--out')+1]=str(root/'selected')
            selected+=['--query-selection',str(sp),'--query-selection-sha',digest(sp.read_bytes())]
            result=subprocess.run(selected,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            saved=json.loads((root/'selected/report.json').read_text())
            self.assertEqual(saved['selection']['selected_query_ids'],selection['query_ids'])
            self.assertEqual(saved['selection']['full_query_count'],1);self.assertTrue(saved['complete']);self.assertFalse(saved['pass'])
            self.assertEqual((root/'selected/selection.json').read_bytes(),sp.read_bytes())
            self.assertEqual((root/'selected/plan.json').read_bytes(),(root/'result/plan.json').read_bytes())
            # Fail a real pre-query hash guard through the same entry point.
            wrong=command[:];wrong[wrong.index('--frame-report-sha')+1]='0'*64;wrong[wrong.index('--out')+1]=str(root/'wrong-result')
            result=subprocess.run(wrong,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertIn('Changed accepted frame report',result.stderr);self.assertFalse((root/'wrong-result').exists())
            # Exercise an external stop of the actual CLI while a dependency
            # double is inside one query; the prefix must not claim close/fsync.
            (package/'review/gates/assembly.py').write_text("import time\nclass AccessOptions:\n def __init__(self,**kwargs):pass\ndef sweep_pair(*args,**kwargs):time.sleep(60);return {'state':'clear'}\n")
            subprocess.check_call(['git','-C',str(core),'add','.'])
            subprocess.check_call(['git','-C',str(core),'-c','core.hooksPath=/dev/null','-c','user.name=Fixture','-c','user.email=fixture@example.com','commit','-qm','Explicit interrupt-prefix dependency double'])
            revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
            stopped=command[:];stopped[stopped.index('--toolkit-revision')+1]=revision;stopped[stopped.index('--out')+1]=str(root/'stopped')
            proc=subprocess.Popen(stopped,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                progress=root/'stopped/progress.jsonl';deadline=time.monotonic()+5
                while not progress.exists() or not progress.stat().st_size:
                    if proc.poll() is not None:self.fail(proc.communicate())
                    self.assertLess(time.monotonic(),deadline,'Explicit query double did not start');time.sleep(.02)
            finally:
                proc.kill();proc.communicate(timeout=5)
            phase=json.loads((root/'stopped/phase.json').read_text());saved=json.loads((root/'stopped/report.json').read_text())
            self.assertEqual(phase['state'],'running');self.assertTrue(phase['progress_tail_uncertain'])
            self.assertEqual(phase['progress_fsync_acknowledged_records'],0);self.assertFalse(saved['complete']);self.assertFalse(saved['pass'])
            prefix=[json.loads(line) for line in progress.read_text().splitlines()]
            self.assertEqual(prefix[-1]['core_event']['state'],'starting');self.assertEqual(len(prefix),1)

    @unittest.skipUnless(os.environ.get('ROBOT_PLAYBACK_NATIVE')=='1','Explicit optional native fixture only')
    def test_real_core_pair_paths_and_sample_cap(self):
        toolkit=Path(os.environ['ROBOT_PLAYBACK_TOOLKIT']);revision=os.environ['ROBOT_PLAYBACK_TOOLKIT_REVISION']
        self.assertEqual(study.git(toolkit,'rev-parse','HEAD'),revision);self.assertEqual(study.git(toolkit,'status','--porcelain'),'')
        sys.path.insert(0,str(toolkit/'software'))
        import cadquery as cq
        from cadagent.review.evidence import shape_brep_text,brep_content_hash
        from cadagent.review.gates.playback import _load_world
        from cadagent.review.gates.assembly import sweep_pair,AccessOptions
        from cadagent.review.gates.relations import Tolerances
        shapes={'moving':cq.Workplane().box(10,10,10).val(),'fixed':cq.Workplane().box(10,10,10).translate((0,30,0)).val(),
                'seat':cq.Workplane().box(10,10,10).val()}
        payloads={n:shape_brep_text(s) for n,s in shapes.items()}
        binding={'instances':{n:{'matrix':IDENTITY,'shape_sha256':brep_content_hash(b)} for n,b in payloads.items()}}
        frames=[]
        for n,s in shapes.items():
            b=s.BoundingBox();frames.append({'instance':n,'cad_bounds_mm':[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]})
        queries=[{'id':'blocked','moving':'moving','fixed':'fixed','direction':[0,-1,0],'travel_mm':60,'contexts':[]},
                 {'id':'wrong-side-clear','moving':'moving','fixed':'fixed','direction':[0,1,0],'travel_mm':60,'contexts':[]},
                 {'id':'terminal-seat','moving':'moving','fixed':'seat','direction':[0,-1,0],'travel_mm':60,'contexts':[]}]
        for query in queries:query['id']=digest(query['id'].encode())
        core=SimpleNamespace(load_world=_load_world,sweep_pair=sweep_pair,tol=Tolerances())
        with tempfile.TemporaryDirectory() as tmp:
            report=study.execute_plan({'queries':queries},binding,payloads,frames,core,Path(tmp),{'fixture':'actual simple native boxes, never product CAD'},AccessOptions(max_samples=256))
            self.assertTrue(report['complete']);self.assertFalse(report['pass'])
            self.assertEqual([q['result']['state'] for q in report['queries']],['blocked','clear','seat'])
            self.assertTrue(report['queries'][2]['terminal_only']);self.assertFalse(report['queries'][2]['transient_path_complete'])
        full={'queries':queries};selection={'schema':'gyropup.native-pair-selection/1','full_plan_sha256':digest(encode(full)),
                                            'query_ids':[q['id'] for q in queries[:2]]}
        with tempfile.TemporaryDirectory() as tmp:
            report=study.execute_plan(study.select_plan(full,selection),binding,payloads,frames,core,Path(tmp),
                                      {'fixture':'actual simple boxes, explicit2-of3 identity selection'},AccessOptions(max_samples=256))
            self.assertTrue(report['complete']);self.assertFalse(report['pass'])
            self.assertEqual([q['result']['state'] for q in report['queries']],['blocked','clear'])
            self.assertEqual(report['selection']['unselected_query_ids'],[queries[2]['id']])
        with tempfile.TemporaryDirectory() as tmp:
            report=study.execute_plan({'queries':queries[:1]},binding,payloads,frames,core,Path(tmp),{'fixture':'actual native sample-cap control'},AccessOptions(max_samples=1))
            self.assertEqual(report['queries'][0]['result']['state'],'unchecked');self.assertFalse(report['pass'])


if __name__=='__main__':unittest.main()
