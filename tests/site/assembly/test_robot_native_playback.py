"""Original-byte provenance negatives; no synthetic fixture is native evidence."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_native_playback import native_parts,bind_inputs,encode,digest,IDENTITY


class OriginalNativeBytes(unittest.TestCase):
    def fixture(self,folder):
        raw=b'not a CAD solid: pure serializer fixture only';(folder/'breps').mkdir();(folder/'breps/part.brep').write_bytes(raw)
        c={'schema':'gyropup.robot-assembly-parts/1','units':'mm','up':'z','source_commit':'a'*40,'parts':[{'name':'part','sha256':'b'*64,
           'native_geometry':{'file':'breps/part.brep','sha256':digest(raw),'shape_sha256':'c'*64,'matrix':IDENTITY[:]} }],
           'native_geometry':{'schema':'gyropup.robot-native-parts/1','units':'mm','up':'z','frame':'assembled robot CAD mm/Z-up',
                              'format':'OCCT BREP v1 without triangulation or normals',
                              'hash_platform':{'fixture':True},'source_correspondence':'Synthetic fixture, never native evidence'}}
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

    def test_native_cli_help_does_not_import_kernel(self):
        value=subprocess.check_output([sys.executable,'-I','-S','-B',str(ROOT/'tools/site/assembly/robot_native_playback.py'),'--help'],text=True,timeout=5)
        self.assertIn('--validate',value)
        value=subprocess.check_output([sys.executable,'-I','-S','-B',str(ROOT/'tools/site/assembly/collect_robot_parts.py'),'--help'],text=True,timeout=5)
        self.assertIn('--emit-brep',value)

if __name__=='__main__':unittest.main()
