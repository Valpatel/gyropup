"""The actual existing-toolkit project and meaningful corruption controls."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_project import NS,ORIGINAL,RECEIPT,prepared,verify


class HipGeometryProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record=json.loads((ROOT/RECEIPT).read_text());cls.project=ROOT/cls.record['project']['source_file']

    def test_actual_file_units_topology_original_pose_and_generic_bounds(self):
        result=verify(self.project,ROOT/ORIGINAL)
        self.assertEqual(result,self.record['checks'])
        self.assertEqual(result['triangles'],29676)
        self.assertTrue(result['edge_manifold'])
        self.assertLess(result['max_coordinate_error_mm'],.000051)
        self.assertEqual(result['bounds_mm'],[3.3916,3.3916,0.,252.6084,252.6084,81.3])
        self.assertFalse(result['actual_printer_fit_verified'])
        self.assertFalse(result['slice_verified'])
        self.assertEqual(hashlib.sha256((ROOT/'hardware/exports/leg/hip_frame.3mf').read_bytes()).hexdigest(),
                         self.record['retained_3mf_sha256'])
        sha=self.record['project']['source_original_sha256']
        self.assertEqual(len(prepared(ROOT,sha)),1)
        self.assertEqual(prepared(ROOT,'0'*64),[])

    def test_changed_project_units_vertices_triangles_build_and_nan_reject(self):
        with zipfile.ZipFile(self.project) as z:members={n:z.read(n) for n in z.namelist()}
        for mutation in ('units','vertex','triangle','build','nan'):
            xml=ET.fromstring(members['3D/3dmodel.model']);ns={'m':NS}
            if mutation=='units':xml.set('unit','inch')
            elif mutation in ('vertex','nan'):
                vertex=xml.find('.//m:vertex',ns);vertex.set('x','nan' if mutation=='nan' else str(float(vertex.get('x'))+1))
            elif mutation=='triangle':xml.find('.//m:triangle',ns).set('v1','999999999')
            else:xml.find('m:build/m:item',ns).set('transform','1 0 0 0 1 0 0 0 1 1 0 0')
            with tempfile.TemporaryDirectory() as tmp:
                file=Path(tmp)/'bad.3mf'
                with zipfile.ZipFile(file,'w') as z:
                    for name,data in members.items():z.writestr(name,ET.tostring(xml) if name=='3D/3dmodel.model' else data)
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):verify(file,ROOT/ORIGINAL)

    def test_mutated_original_or_project_never_remains_an_immutable_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for file in (ORIGINAL,RECEIPT,self.record['project']['source_file']):
                p=root/file;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,p)
            sha=self.record['project']['source_original_sha256']
            self.assertEqual(len(prepared(root,sha)),1)
            for file in (ORIGINAL,self.record['project']['source_file']):
                p=root/file;old=p.read_bytes();p.write_bytes(old+b'changed')
                self.assertEqual(prepared(root,sha),[])
                p.write_bytes(old)


if __name__=='__main__':unittest.main()
