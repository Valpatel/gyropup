"""Exercise the real committed collection, not synthetic stand-ins for geometry."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_data import sha

RECORDS=ROOT/'.agents/plans/robot-assembly'
ASSETS=ROOT/'software/site/assets/build-guides'

# Only live poster-binding metadata may advance after a genuine reviewed capture.
# The historical seals below still bind every other byte, including all PNGs/meshes.
TURRET='turret-wip-4866459e2abd'
PRIOR_VISUAL='6e012c3390e004f36669a7e69ef6efaca15d2226e8570cee05124e5d0e286f38'
CAPTURE_RECEIPT='f39c542df55683cd3fad921431f2704549c26d24236474ada2d13143db9250f6'
CAPTURE_SOURCE='84f8b9b91c4af99203005e5d976c3f58d3c8c355'

def current_visual_contract():
    return json.loads(subprocess.check_output(['node',str(ROOT/'tools/site/assembly/poster-contract.mjs')],cwd=ROOT))

def verify_capture_binding(receipt_blob,guide_blob,posters_blob,visual):
    assert hashlib.sha256(receipt_blob).hexdigest()==CAPTURE_RECEIPT,'Actual accepted receipt bytes changed'
    receipt=json.loads(receipt_blob);guide=json.loads(guide_blob);posters=json.loads(posters_blob)
    assert receipt['source_commit']==receipt['version']['revision']==CAPTURE_SOURCE,'Capture source changed'
    assert receipt['visual_sha256']==guide['source']['poster_visual_sha256']==posters['visual_sha256']==visual['visual_sha256'],'Current visual/capture/guide/poster binding mismatch'
    assert receipt['render']==visual['inputs']['render'],'Actual capture pose/render contract mismatch'

def verify_historical_member(name,blob,row,visual_sha):
    fields={TURRET+'/guide.json':'poster_visual_sha256',TURRET+'/posters.json':'visual_sha256'}
    if name in fields:
        # Restore exactly one reviewed scalar for comparison with immutable seals.
        # This does not exempt the file: every other byte must retain its old seal.
        field=fields[name];value=json.loads(blob)
        assert (value['source'][field] if field=='poster_visual_sha256' else value[field])==visual_sha,'Wrong live poster visual binding'
        pattern=rb'("'+field.encode()+rb'"\s*:\s*")'+visual_sha.encode()+rb'(")'
        blob,count=re.subn(pattern,lambda m:m[1]+PRIOR_VISUAL.encode()+m[2],blob)
        assert count==1,'Poster binding must occur exactly once'
    assert hashlib.sha256(blob).hexdigest()==row['sha256'],name+' changed outside reviewed poster binding'
    assert len(blob)==row['bytes'],name+' byte count changed'

def verify_live_index(index_blob,archived_blob,guide_blob):
    index=json.loads(index_blob);archived=json.loads(archived_blob)
    live=[r for r in index['snapshots'] if r['id']==TURRET]
    old=[r for r in archived['snapshots'] if r['id']==TURRET]
    assert len(live)==len(old)==1,'Exactly one turret index row required'
    assert live[0]['file']==TURRET+'/guide.json','Wrong turret guide target'
    assert live[0]['sha256']==hashlib.sha256(guide_blob).hexdigest(),'Index must bind actual live guide bytes'
    live[0]['sha256']=old[0]['sha256']
    assert index==archived,'Index changed outside reviewed turret guide digest'



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
        visual=current_visual_contract()
        verify_capture_binding((ROOT/'.agents/plans/versioned-build-guide-poster-capture-current.json').read_bytes(),(ASSETS/TURRET/'guide.json').read_bytes(),(ASSETS/TURRET/'posters.json').read_bytes(),visual)
        for name,row in seals.items():
            if name=='index.json':continue  # The new five-row index preserves these three old entries explicitly.
            verify_historical_member(name,(ASSETS/name).read_bytes(),row,visual['visual_sha256'])
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

    def test_live_poster_boundary_rejects_unreviewed_changes(self):
        seals=json.loads((ROOT/'.agents/plans/end-packs/guide-adoption/historical-guide-seals.json').read_bytes())
        visual=current_visual_contract();digest=visual['visual_sha256']
        guide=(ASSETS/TURRET/'guide.json').read_bytes();posters=(ASSETS/TURRET/'posters.json').read_bytes()
        receipt=(ROOT/'.agents/plans/versioned-build-guide-poster-capture-current.json').read_bytes()
        verify_capture_binding(receipt,guide,posters,visual)
        for name,blob in [(TURRET+'/guide.json',guide),(TURRET+'/posters.json',posters)]:
            verify_historical_member(name,blob,seals[name],digest)
            bad=json.loads(blob)
            if name.endswith('/guide.json'):bad['snapshot']['title']='unreviewed title'
            else:bad['frames']['step-01']['sha256']='0'*64
            with self.subTest(nonposter=name),self.assertRaises(AssertionError):
                verify_historical_member(name,json.dumps(bad,indent=2).encode()+b'\n',seals[name],digest)
            with self.subTest(wrongvisual=name),self.assertRaises(AssertionError):
                verify_historical_member(name,blob.replace(digest.encode(),b'0'*64),seals[name],digest)
        mesh=next(name for name in seals if name.startswith(TURRET+'/meshes/'))
        blob=(ASSETS/mesh).read_bytes();wrong=blob[:-1]+bytes([blob[-1]^1])
        with self.assertRaises(AssertionError):verify_historical_member(mesh,wrong,seals[mesh],digest)
        with self.assertRaises(AssertionError):verify_capture_binding(receipt,guide,posters.replace(digest.encode(),b'0'*64),visual)
        with self.assertRaises(AssertionError):verify_capture_binding(receipt.replace(CAPTURE_SOURCE.encode(),b'0'*40),guide,posters,visual)

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
