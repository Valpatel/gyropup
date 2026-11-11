"""Exercise the real committed collection, not synthetic stand-ins for geometry."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_data import sha

RECORDS=ROOT/'.agents/plans/robot-assembly'
ASSETS=ROOT/'software/site/assets/build-guides'


class HistoricalRobotSnapshots(unittest.TestCase):
    """Dated260/540 artifact integrity; never a current-source regeneration."""
    @classmethod
    def setUpClass(cls):
        cls.collection=json.loads((RECORDS/'collection-260.json').read_text())
        cls.entries=json.loads((RECORDS/'index-entries-260.json').read_text())

    def test_archived_bytes_and_manufacturing_remain_exact(self):
        file=ROOT/'.agents/plans/end-packs/guide-adoption/historical-guide-seals.json'
        self.assertEqual(sha(file),'f75342059c76b0126ca73e2cf8c702890d64066646c0bd96d90fc30c9321f4d7')
        seals=json.loads(file.read_bytes())
        self.assertEqual(len(seals),316)
        for name,row in seals.items():
            if name=='index.json':continue  # The new five-row index preserves these three old entries explicitly.
            self.assertEqual(sha(ASSETS/name),row['sha256'],name)
            self.assertEqual((ASSETS/name).stat().st_size,row['bytes'],name)
        for row in self.entries:
            directory=ASSETS/row['id'];g=json.loads((directory/'guide.json').read_bytes())
            self.assertEqual(sha(directory/'guide.json'),row['sha256'])
            self.assertEqual(g['snapshot']['source_commit'],self.collection['source_commit'])
            model=json.loads((directory/'view.json').read_bytes())
            self.assertEqual(sha(directory/'view.json'),g['model']['sha256'])
            self.assertEqual(len(model['parts']),171 if row['assembly']=='robot' else 233)
            prepared=[]
            for part in model['parts']:
                self.assertEqual(sha((directory/part['file']).resolve()),part['sha256'])
                manufacturing=g['source']['manufacturing_by_part'][part['name']]
                if manufacturing['geometry_match']['status']=='matched':prepared.append(part['name'])
                for original in manufacturing['originals']:
                    self.assertEqual(sha(ROOT/original['source_file']),original['sha256'])
            self.assertEqual(sorted(prepared),['L.hip_frame','R.hip_frame'])

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
