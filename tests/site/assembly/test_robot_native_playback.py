"""Original-byte provenance negatives; no synthetic fixture is native evidence."""
import copy
import os
import json
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_native_playback import native_parts,bind_inputs,native_report,ProgressWriter,encode,digest,IDENTITY


class OriginalNativeBytes(unittest.TestCase):
    def fixture(self,folder):
        raw=b'not a CAD solid: pure serializer fixture only';(folder/'breps').mkdir();(folder/'breps/part.brep').write_bytes(raw)
        c={'producer_inputs':{'fixture':'explicit test-double metadata, never native evidence'},'schema':'gyropup.robot-assembly-parts/1','units':'mm','up':'z','source_commit':'a'*40,'parts':[{'name':'part','sha256':'b'*64,
           'native_geometry':{'file':'breps/part.brep','sha256':digest(raw),'shape_sha256':'c'*64,'matrix':IDENTITY[:]} }],
           'native_geometry':{'schema':'gyropup.robot-native-parts/1','units':'mm','up':'z','frame':'assembled robot CAD mm/Z-up',
                              'format':'OCCT BREP v1 without triangulation or normals',
                              'hash_platform':{'machine':'synthetic-fixture','system':'synthetic-fixture'},'source_correspondence':'Synthetic fixture, never native evidence'}}
        return c,raw

    def bundle(self,c):
        model=encode({'parts':[{'name':'part','sha256':'b'*64}]})
        g={'snapshot':{'id':'fixture','source_commit':c['source_commit']},'source':{'collection_sha256':'d'*64},
           'model':{'file':'view.json'}}
        return SimpleNamespace(path='fixture/guide.json',files={'fixture/guide.json':encode(g),'fixture/view.json':model})

    def test_actual_payload_tamper_and_missing_or_aliased_identity_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);c,raw=self.fixture(folder);self.assertEqual(native_parts(c,folder),{'part':raw})
            for fault in ('digest','matrix','missing','units','duplicate','escape'):
                value=copy.deepcopy(c);part=value['parts'][0]
                if fault=='digest':part['native_geometry']['sha256']='0'*64
                elif fault=='matrix':part['native_geometry']['matrix'][3]=2
                elif fault=='missing':part.pop('native_geometry')
                elif fault=='units':value['native_geometry']['units']='m'
                elif fault=='duplicate':value['parts'].append(copy.deepcopy(part))
                else:part['native_geometry']['file']='breps/../breps/part.brep'
                with self.subTest(fault=fault),self.assertRaises(ValueError):native_parts(value,folder)
            (folder/'breps/part.brep').write_bytes(raw+b'changed')
            with self.assertRaises(ValueError):native_parts(c,folder)

    def test_binding_keeps_original_bytes_hashes_platform_and_frozen_guide_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);c,raw=self.fixture(folder);bundle=self.bundle(c);calls=[]
            def bind(b,payloads,*,producer_hash_platform):
                calls.append((b,payloads,producer_hash_platform))
                return {'instances':{'part':{'brep_sha256':digest(raw),'shape_sha256':'c'*64,'matrix':IDENTITY[:]} }}
            rows,outputs=bind_inputs(c,'d'*64,[bundle],{'part':raw},bind)
            self.assertEqual(calls[0][1],{'part':raw});self.assertEqual(calls[0][2],c['native_geometry']['hash_platform'])
            self.assertEqual(outputs[rows[0]['breps']['part']],raw)
            for fault in ('collection','source','mesh','shape','placement'):
                value=copy.deepcopy(c)
                if fault=='source':value['source_commit']='e'*40
                elif fault=='mesh':value['parts'][0]['sha256']='e'*64
                elif fault=='shape':value['parts'][0]['native_geometry']['shape_sha256']='e'*64
                elif fault=='placement':value['parts'][0]['native_geometry']['matrix'][3]=2
                with self.subTest(fault=fault),self.assertRaises(ValueError):
                    bind_inputs(value,'e'*64 if fault=='collection' else 'd'*64,[bundle],{'part':raw},bind)

    def test_committed_stl_only_collection_cannot_claim_native_validation(self):
        import json
        collection=json.loads((ROOT/'.agents/plans/robot-assembly/collection-260.json').read_text())
        with self.assertRaises(ValueError):native_parts(collection,ROOT/'.agents/plans/robot-assembly')

    def test_actual_cli_preserves_failed_verdict_and_nonzero_exit_without_cad(self):
        # A dependency double exercises the real script entry point/process. It
        # deliberately proves no CAD behavior; ordinary CI must still catch an
        # entry point which drops main()'s failed-gate return value.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/'native';native.mkdir();c,raw=self.fixture(native)
            (native/'collection.json').write_bytes(encode(c));guides=root/'guides';guides.mkdir()
            bundle=self.bundle(c)
            guide=json.loads(bundle.files['fixture/guide.json'])
            guide['source']['collection_sha256']=digest(encode(c))
            guide['source']['install_order_by_step']={'fixture':['part']}
            bundle.files['fixture/guide.json']=encode(guide)
            for file,data in bundle.files.items():
                path=guides/file;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
            core=root/'core';package=core/'software/cadagent'
            for relative in ('__init__.py','publish/__init__.py','review/__init__.py','review/gates/__init__.py'):
                path=package/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
            (package/'publish/guides.py').write_text("from types import SimpleNamespace\ndef collect_guides(root,paths):\n return [SimpleNamespace(path=p,files={f.relative_to(root).as_posix():f.read_bytes() for f in root.rglob('*') if f.is_file()}) for p in paths]\n")
            (package/'review/gates/playback.py').write_text("""import hashlib
IDENTITY="""+repr(IDENTITY)+"""
def bind_playback_breps(bundle,breps,*,producer_hash_platform):
 return {'instances':{n:{'brep_sha256':hashlib.sha256(raw).hexdigest(),'shape_sha256':'c'*64,'matrix':IDENTITY} for n,raw in breps.items()},'hash_platform':producer_hash_platform}
def playback_gate(bundle,binding,breps,*,preflight_only=False,on_progress=None,**kwargs):
 on_progress({'schema':'cad-agent.playback-progress/1','event':'phase','phase':'load','state':'starting'})
 if preflight_only:
  on_progress({'schema':'cad-agent.playback-progress/1','event':'preflight','state':'complete'})
  return {'schema':'cadagent.gate/1','gate':'assembly-playback-preflight','pass':True,'status':'warn','limits':{'progress_complete':True,'paths_checked':False}}
 on_progress({'schema':'cad-agent.playback-progress/1','event':'pair','state':'complete','result':{'state':'overlapping'}})
 return {'schema':'cadagent.gate/1','gate':'assembly-playback','pass':False,'status':'fail','findings':[{'id':'explicit-test-double-failure'}],'limits':{'progress_complete':True,'paths_checked':True}}
""")
            subprocess.check_call(['git','init','-q',str(core)])
            subprocess.check_call(['git','-C',str(core),'add','.'])
            subprocess.check_call(['git','-C',str(core),'-c','core.hooksPath=/dev/null','-c','user.name=Fixture','-c','user.email=fixture@example.com','commit','-qm','Explicit non-CAD CLI dependency double'])
            revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
            command=[sys.executable,'-B',str(ROOT/'tools/site/assembly/robot_native_playback.py'),
                     '--collection',str(native/'collection.json'),'--guides-root',str(guides),
                     '--guide','fixture/guide.json','--toolkit',str(core),'--toolkit-revision',revision,
                     '--out',str(root/'result'),'--validate']
            completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(completed.returncode,1,completed.stdout+completed.stderr)
            self.assertIn('blocked or undecided',completed.stdout,completed.stderr)
            report=json.loads((root/'result/reports/fixture.json').read_text())
            self.assertIs(report['pass'],False);self.assertEqual(report['status'],'fail')
            self.assertTrue((root/'result/inputs.json').is_file())
            self.assertFalse(json.loads((root/'result/reports.json').read_text())[0]['pass'])
            phase=json.loads((root/'result/reports/fixture.phase.json').read_text());self.assertEqual(phase['state'],'complete');self.assertFalse(phase['gate_pass'])
            progress=[json.loads(line) for line in (root/'result/progress/fixture.jsonl').read_text().splitlines()]
            self.assertEqual(len(progress),2);self.assertEqual(progress[-1]['core_event']['result']['state'],'overlapping')
            self.assertEqual([r['sequence'] for r in progress],[1,2])
            preflight=command[:];preflight[preflight.index('--out')+1]=str(root/'preflight');preflight.remove('--validate');preflight.append('--preflight-only')
            completed=subprocess.run(preflight,capture_output=True,text=True,timeout=10)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            report=json.loads((root/'preflight/reports/fixture.json').read_text())
            self.assertEqual(report['gate'],'assembly-playback-preflight');self.assertFalse(report['limits']['paths_checked'])
            progress=[json.loads(line)['core_event'] for line in (root/'preflight/progress/fixture.jsonl').read_text().splitlines()]
            self.assertFalse(any(r['event'] in ('pair','operation') for r in progress))
            self.assertEqual(progress[-1]['event'],'preflight')
            invalid=command[:];invalid[invalid.index('--out')+1]=str(root/'over-budget');invalid+=['--max-samples','5001']
            completed=subprocess.run(invalid,capture_output=True,text=True,timeout=10)
            self.assertEqual(completed.returncode,2);self.assertFalse((root/'over-budget').exists())

    def test_failed_progress_serialization_preserves_prefix_report_and_incomplete_phase(self):
        # A callback storage/serialization failure must not become a completed
        # native phase or discard already-recorded collision evidence.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/'native';native.mkdir();c,raw=self.fixture(native);bundle=self.bundle(c)
            guide=json.loads(bundle.files[bundle.path]);guide['source']['install_order_by_step']={'fixture':['part']};bundle.files[bundle.path]=encode(guide)
            out=root/'result';out.mkdir();row={'guide':bundle.path,'guide_sha256':digest(bundle.files[bundle.path]),'binding_sha256':'e'*64}
            def gate(bundle,binding,breps,*,preflight_only,on_progress,**kwargs):
                on_progress({'schema':'cad-agent.playback-progress/1','event':'pair','state':'complete','result':{'state':'overlapping','witness':'retained-control'}})
                try:on_progress({'schema':'cad-agent.playback-progress/1','event':'pair','state':'complete','result':{'gap_mm':float('nan')}})
                except ValueError:
                    return {'gate':'assembly-playback','pass':False,'limits':{'progress_complete':False,'paths_checked':False},'findings':[{'id':'progress','witness':'retained-control'}]}
                self.fail('Nonfinite callback data was silently accepted')
            with self.assertRaises(ValueError):
                native_report(out,bundle,row,{'instances':{'part':{}}},{'part':raw},gate,preflight_only=False,core_revision='f'*40)
            phase=json.loads((out/'reports/fixture.phase.json').read_text());self.assertEqual(phase['state'],'incomplete')
            self.assertEqual(phase['progress_flushed_records'],1)
            self.assertEqual(phase['progress_fsync_acknowledged_records'],0)
            self.assertTrue(phase['progress_tail_uncertain'])
            report=json.loads((out/'reports/fixture.json').read_text());self.assertEqual(report['findings'][0]['witness'],'retained-control')
            progress=[json.loads(line) for line in (out/'progress/fixture.jsonl').read_text().splitlines()]
            self.assertEqual(len(progress),1);self.assertEqual(progress[0]['core_event']['result']['witness'],'retained-control')

    def test_storage_failure_does_not_certify_the_flushed_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'progress.jsonl';writer=ProgressWriter(path,{'fixture':'no CAD'})
            writer({'schema':'cad-agent.playback-progress/1','event':'preflight','state':'complete'})
            self.assertEqual(writer.synced,1)
            writer({'schema':'cad-agent.playback-progress/1','event':'pair','state':'complete'})
            with mock.patch('robot_native_playback.os.fsync',side_effect=OSError('intentional fsync failure')):
                with self.assertRaises(OSError):
                    writer({'schema':'cad-agent.playback-progress/1','event':'operation','state':'complete'})
                error=writer.finish()
            self.assertIsInstance(error,OSError);self.assertEqual(writer.count,3);self.assertEqual(writer.synced,1)
            self.assertEqual(len(path.read_text().splitlines()),3,'Flushed bytes may exist without acknowledged tail fsync')

    @unittest.skipUnless(os.environ.get('ROBOT_PLAYBACK_NATIVE')=='1','Explicit real native fixture preflight requested separately')
    def test_actual_failed_native_three_box_cli_exits_nonzero_and_retains_report(self):
        toolkit=Path(os.environ['ROBOT_PLAYBACK_TOOLKIT']).resolve()
        revision=os.environ['ROBOT_PLAYBACK_TOOLKIT_REVISION']
        sys.path.insert(0,str(toolkit/'software'))
        from cadagent.review.gates.playback import bind_playback_geometry
        fixture=runpy.run_path(str(toolkit/'tests/review/test_gate_assembly.py'))['captured_playback_fixture']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);guides=root/'guides';guides.mkdir();native=root/'native';(native/'breps').mkdir(parents=True)
            bundle,assembly=fixture(guides,native=True);binding,breps=bind_playback_geometry(assembly,bundle)
            model=json.loads((guides/'view.json').read_text());parts=[]
            for part in model['parts']:
                name=part['name'];entry=binding['instances'][name];file='breps/'+name+'.brep';(native/file).write_bytes(breps[name])
                parts.append({'name':name,'sha256':part['sha256'],'native_geometry':{'file':file,'sha256':entry['brep_sha256'],'shape_sha256':entry['shape_sha256'],'matrix':entry['matrix']}})
            c={'schema':'gyropup.robot-assembly-parts/1','units':'mm','up':'z','source_commit':'a'*40,'producer_inputs':{'fixture':'actual three-box control, never Gyropup geometry evidence'},'parts':parts,
               'native_geometry':{'schema':'gyropup.robot-native-parts/1','units':'mm','up':'z','frame':'assembled robot CAD mm/Z-up','format':'OCCT BREP v1 without triangulation or normals','hash_platform':binding['hash_platform'],'source_correspondence':'Explicit real three-box review fixture; never Gyropup native evidence.'}}
            raw=encode(c);(native/'collection.json').write_bytes(raw)
            guide=json.loads((guides/'guide.json').read_text());guide['source']['collection_sha256']=digest(raw);(guides/'guide.json').write_bytes(encode(guide))
            command=[sys.executable,'-B',str(ROOT/'tools/site/assembly/robot_native_playback.py'),'--collection',str(native/'collection.json'),'--guides-root',str(guides),'--guide','guide.json','--toolkit',str(toolkit),'--toolkit-revision',revision,'--out',str(root/'result'),'--validate']
            completed=subprocess.run(command,env=os.environ,capture_output=True,text=True,timeout=30)
            report=json.loads((root/'result/reports/fixture.json').read_text())
            self.assertIs(report['pass'],False);self.assertEqual(report['status'],'fail')
            self.assertEqual(completed.returncode,1,completed.stdout+completed.stderr)
            self.assertIn('blocked or undecided',completed.stdout)
            self.assertTrue((root/'result/inputs.json').is_file())
            preflight=command[:];preflight[preflight.index('--out')+1]=str(root/'preflight');preflight.remove('--validate');preflight.append('--preflight-only')
            completed=subprocess.run(preflight,env=os.environ,capture_output=True,text=True,timeout=30)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            report=json.loads((root/'preflight/reports/fixture.json').read_text())
            self.assertEqual(report['gate'],'assembly-playback-preflight');self.assertIs(report['pass'],True)
            self.assertIs(report['limits']['paths_checked'],False)
            progress=[json.loads(line)['core_event'] for line in (root/'preflight/progress/fixture.jsonl').read_text().splitlines()]
            self.assertFalse(any(r['event'] in ('pair','operation') for r in progress))

    @unittest.skipUnless(os.environ.get('ROBOT_PLAYBACK_TOOLKIT'),'Explicit reviewed core checkout needed for optional cross-API preflight')
    def test_real_core_original_byte_helper_contract_without_native_evidence(self):
        toolkit=Path(os.environ['ROBOT_PLAYBACK_TOOLKIT']).resolve()
        revision=os.environ.get('ROBOT_PLAYBACK_TOOLKIT_REVISION','')
        self.assertRegex(revision,r'^[0-9a-f]{40}$')
        self.assertEqual(subprocess.check_output(['git','-C',str(toolkit),'rev-parse','HEAD'],text=True).strip(),revision)
        self.assertEqual(subprocess.check_output(['git','-C',str(toolkit),'status','--porcelain'],text=True).strip(),'')
        sys.path.insert(0,str(toolkit/'software'))
        from cadagent.review.gates.playback import bind_playback_breps
        import cadagent
        self.assertTrue(Path(cadagent.__file__).resolve().is_relative_to(toolkit/'software/cadagent'))
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);c,raw=self.fixture(folder)
            # Explicit non-CAD/non-STL bytes test only the pure interface and
            # capture/provenance contract; they cannot enter a native query.
            mesh=b'SYNTHETIC non-STL interface fixture, never native evidence'
            mesh_sha=digest(mesh);c['parts'][0]['sha256']=mesh_sha
            c['parts'][0]['native_geometry']['shape_sha256']=digest(raw)
            model=encode({'units':'mm','up':'z','parts':[{'name':'part','file':'part.stl','sha256':mesh_sha}]})
            guide=encode({'snapshot':{'id':'fixture','source_commit':c['source_commit']},
                          'source':{'collection_sha256':'d'*64},'model':{'file':'view.json','sha256':digest(model)}})
            bundle=SimpleNamespace(path='fixture/guide.json',files={'fixture/guide.json':guide,'fixture/view.json':model,'fixture/part.stl':mesh})
            rows,outputs=bind_inputs(c,'d'*64,[bundle],native_parts(c,folder),bind_playback_breps)
            binding=__import__('json').loads(outputs[rows[0]['binding']])
            self.assertEqual(binding['hash_platform'],c['native_geometry']['hash_platform'])
            self.assertEqual(binding['instances']['part']['brep_sha256'],digest(raw))
            self.assertEqual(outputs[rows[0]['breps']['part']],raw)

    def test_native_cli_help_does_not_import_kernel(self):
        value=subprocess.check_output([sys.executable,'-I','-S','-B',str(ROOT/'tools/site/assembly/robot_native_playback.py'),'--help'],text=True,timeout=5)
        self.assertIn('--validate',value)
        value=subprocess.check_output([sys.executable,'-I','-S','-B',str(ROOT/'tools/site/assembly/collect_robot_parts.py'),'--help'],text=True,timeout=5)
        self.assertIn('--emit-brep',value)

if __name__=='__main__':unittest.main()
