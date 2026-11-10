"""Kernel-free source-closure and surface fault controls for the hip original."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_print_match import correspondence,hip_to_print,point_triangle_distance2,source_guard
from robot_manufacturing import hip_geometry_match


class HipOriginalMatch(unittest.TestCase):
    def test_triangle_distance_regions_and_actual_orientation(self):
        triangle=((0.,0.,0.),(2.,0.,0.),(0.,2.,0.))
        for point,distance in (((.5,.5,1),1),((-1,0,0),1),((1,1,0),0),((3,0,0),1)):
            self.assertAlmostEqual(point_triangle_distance2(point,triangle),distance)
        self.assertEqual(hip_to_print((0,-1,-81.5)),(137,0.,0))
        positive=correspondence([triangle],[triangle],.001)
        self.assertLess(positive['a_to_b']['max_distance_mm'],1e-12)
        wrong=[tuple((p[0],p[1],p[2]+1) for p in triangle)]
        with self.assertRaises(ValueError):correspondence([triangle],wrong,.3011)

    def test_actual_receipt_rejects_stale_receipt_code_and_original(self):
        collection=json.loads((ROOT/'.agents/plans/robot-assembly/collection-260.json').read_text())
        receipt=source_guard(ROOT,collection)
        self.assertEqual(receipt['status'],'fail')
        self.assertEqual(receipt['counts']['fail'],8)
        self.assertFalse(receipt['physical_fit_verified'])
        files=set(collection['inputs'])|set(receipt['source_inputs']['context_files'])
        base='hardware/exports/leg/rs04-mounting-fit/'
        files.add(base+'checks.json');files.add('hardware/exports/leg/hip_frame.stl')
        files.update(base+name+'.'+ext for name,row in receipt['artifacts'].items() for ext in row['files'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for file in files:
                dest=root/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,dest)
            source_guard(root,collection)
            proof_file='.agents/plans/robot-assembly/hip-print-match.json'
            proof=json.loads((ROOT/proof_file).read_text())
            # A test-only review URL exercises the gate; it is never exported.
            proof['review_url']='https://github.com/Valpatel/gyropup/pull/270#test-only'
            (root/proof_file).parent.mkdir(parents=True,exist_ok=True)
            (root/proof_file).write_text(json.dumps(proof))
            sampler=root/'tools/site/assembly/robot_print_match.py';sampler.parent.mkdir(parents=True)
            shutil.copyfile(ROOT/'tools/site/assembly/robot_print_match.py',sampler)
            self.assertEqual(hip_geometry_match(root,collection,'L.hip_frame')['status'],'matched')
            self.assertIsNone(hip_geometry_match(root,collection,'L.upper_link_front'))
            bad=json.loads(json.dumps(collection))
            next(p for p in bad['parts'] if p['name']=='L.hip_frame')['sha256']='0'*64
            self.assertIsNone(hip_geometry_match(root,bad,'L.hip_frame'))
            stale=dict(proof,receipt_sha256='0'*64)
            (root/proof_file).write_text(json.dumps(stale))
            self.assertIsNone(hip_geometry_match(root,collection,'L.hip_frame'))
            (root/proof_file).write_text(json.dumps(proof))
            for file,mutation in ((base+'checks.json',b' '),('hardware/cad/legs/fivebar.py',b'\n# changed\n'),
                                  ('hardware/exports/leg/hip_frame.stl',b'changed geometry')):
                path=root/file;old=path.read_bytes()
                if file.endswith('checks.json'):
                    data=json.loads(old);data['source_inputs']['project']['files']['hardware/cad/legs/fivebar.py']='0'*64
                    path.write_text(json.dumps(data))
                else:path.write_bytes(old+mutation)
                with self.subTest(file=file),self.assertRaises(ValueError):source_guard(root,collection)
                self.assertIsNone(hip_geometry_match(root,collection,'L.hip_frame'))
                path.write_bytes(old)


if __name__=='__main__':unittest.main()
