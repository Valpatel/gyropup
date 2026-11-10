"""Exercise the real committed collection, not synthetic stand-ins for geometry."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from export_robot_guide import generate
from robot_data import sha
from robot_manufacturing import mapping

RECORDS=ROOT/'.agents/plans/robot-assembly'
ASSETS=ROOT/'software/site/assets/build-guides'


class CurrentRobotSnapshots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection=json.loads((RECORDS/'collection-260.json').read_text())
        cls.entries=json.loads((RECORDS/'index-entries-260.json').read_text())

    def test_real_snapshot_identity_current_inputs_and_manufacturing_boundary(self):
        c=self.collection
        for file,digest in c['inputs'].items():
            self.assertEqual(sha(ROOT/file),digest,file)
        for row in self.entries:
            directory=ASSETS/row['id'];raw=(directory/'guide.json').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            g=json.loads(raw);model_raw=(directory/'view.json').read_bytes();model=json.loads(model_raw)
            self.assertEqual(g['snapshot']['source_commit'],c['source_commit'])
            self.assertEqual(g['model']['sha256'],hashlib.sha256(model_raw).hexdigest())
            expected_mapping=mapping(ROOT,[p['name'] for p in model['parts']],c)
            for p in model['parts']:
                file=(directory/p['file']).resolve()
                self.assertTrue(file.is_relative_to(ASSETS.resolve()))
                self.assertEqual(sha(file),p['sha256'],p['name'])
                manufacturing=g['source']['manufacturing_by_part'][p['name']]
                expected=expected_mapping[p['name']]
                self.assertEqual(manufacturing,expected)
                for original in manufacturing['originals']:
                    self.assertEqual(sha(ROOT/original['source_file']),original['sha256'])
                    self.assertNotIn('build-guides',original['source_file'])
            self.assertEqual(len(model['parts']),171 if row['assembly']=='robot' else 233)

    def test_real_export_is_reproducible_from_sealed_manifest_and_committed_meshes(self):
        c=self.collection
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'meshes').mkdir()
            for part in c['parts']:
                directory=ASSETS/next(r['id'] for r in self.entries
                                     if r['assembly']==('combined' if part['name'].startswith('turret.') else 'robot'))
                shutil.copyfile(directory/part['file'],folder/part['file'])
            boms={f:sha(ROOT/f) for f in ('hardware/exports/body/bom.json','hardware/exports/leg/bom.json',
                                         'hardware/exports/turret/bench/bom.json')}
            outputs=generate(c,folder,sha(ROOT/'tools/site/assembly/robot_recipe.py'),boms,
                             sha(RECORDS/'collection-260.json'),mapping(ROOT,[p['name'] for p in c['parts']],c))
            self.assertEqual(len(outputs),242)
            for name,data in outputs.items():
                actual=RECORDS/'index-entries-260.json' if name=='index-entries.json' else ASSETS/name
                self.assertEqual(actual.read_bytes(),data,name)

    def test_actual_exported_vertices_confirm_both_physical_sides_and_detect_wrong_frames(self):
        c=self.collection;robot=ASSETS/next(r['id'] for r in self.entries if r['assembly']=='robot')
        parts={p['name']:p for p in c['parts']};yo=c['datums']['y_off_mm']
        correct=[];mirror=[];units=[];double=[]
        def error(vertices,point):
            return min(sum((a-b)**2 for a,b in zip(v,point)) for v in vertices)**.5
        for name,ref in c['module_reference'].items():
            for side in ('L','R'):
                blob=(robot/parts[side+'.'+name]['file']).read_bytes()
                vertices={tuple(record[k:k+3]) for record in struct.iter_unpack('<12fH',blob[84:]) for k in (3,6,9)}
                for x,y,z in ref['local_landmarks_mm']:
                    expected=(x,y+yo,z) if side=='L' else (-x,-y-yo,z)
                    correct.append(error(vertices,expected))
                    units.append(error(vertices,tuple(v*1000 for v in expected)))
                    if side=='R':
                        mirror.append(error(vertices,(x,-y-yo,z)))
                        double.append(error(vertices,(x,y,z)))
        self.assertEqual(len(correct),88)
        self.assertLess(max(correct),.02)
        self.assertGreater(max(mirror),1)
        self.assertGreater(max(units),1)
        self.assertGreater(max(double),1)


if __name__=='__main__':unittest.main()
