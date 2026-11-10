"""Pure expected mechanical frames; no kernel, renderer or collector execution."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
OWNER=ROOT/'tools/site/assembly'
sys.path.insert(0,str(OWNER))
import robot_data as data


class PhysicalFrames(unittest.TestCase):
    def test_expected_physical_rotation_is_not_playground_reflection(self):
        source=[(17,11,-4),(-3,11,-4),(17,-9,-4),(17,11,16)]
        left=[(17,113.55,-4),(-3,113.55,-4),(17,93.55,-4),(17,113.55,16)]
        right=[(-17,-113.55,-4),(3,-113.55,-4),(-17,-93.55,-4),(-17,-113.55,16)]
        for side,want in [('L',left),('R',right)]:
            for actual,expected in zip([data.module_point(p,side,102.55) for p in source],want):
                for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=8)
        self.assertTrue(all(e<=.02 for e in data.nearest_errors(right,right)))
        for wrong in [[(x,-(y+102.55),z) for x,y,z in source],
                      [tuple(v/1000 for v in p) for p in right],
                      [data.module_point(p,'R',102.55) for p in right]]:
            self.assertTrue(any(e>.02 for e in data.nearest_errors(wrong,right)))

    def test_binary_stl_requires_exact_length_and_finite_vertices(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.stl'
            blob=b'\0'*80+struct.pack('<I',1)+struct.pack('<12fH',0,0,1,0,0,0,2,0,0,0,3,0,0)
            p.write_bytes(blob);self.assertEqual(data.bounds(p),[0,0,0,2,3,0])
            for bad in (blob[:-1],blob+b'x',blob[:80]+struct.pack('<I',999)+blob[84:],
                        blob[:84]+struct.pack('<12fH',0,0,1,float('nan'),0,0,2,0,0,0,3,0,0)):
                p.write_bytes(bad)
                with self.assertRaises(ValueError):data.vertices(p)

    def test_reference_landmarks_are_actual_and_noncoplanar(self):
        cloud=[(0,0,0),(2,0,0),(0,3,0),(0,0,4),(1,1,1)]
        points=data.landmarks(cloud)
        self.assertEqual(len(set(points)),4);self.assertTrue(all(p in cloud for p in points))
        with self.assertRaises(ValueError):data.landmarks([(0,0,0),(1,0,0),(0,1,0),(1,1,0)])

    def test_complete_inventory_rejects_symlink_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'part').write_bytes(b'a');(root/'dir').mkdir()
            self.assertEqual(set(data.inventory(root)),{'part'})
            (root/'alias').symlink_to(root/'dir',target_is_directory=True)
            with self.assertRaises(ValueError):data.inventory(root)

    def test_source_names_must_not_collide_after_filename_normalization(self):
        self.assertEqual(data.mesh_files(['L.hip_frame'])['L.hip_frame'],'meshes/L__hip_frame.stl')
        for names in (['L.part','L__part'],['../../outside'],['valid','valid']):
            with self.assertRaises(ValueError):data.mesh_files(names)

    def test_importing_worker_never_imports_native_kernel(self):
        before=set(sys.modules)
        spec=importlib.util.spec_from_file_location('robot_collect_safe',OWNER/'collect_robot_parts.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))
        added=set(sys.modules)-before
        self.assertFalse(any(n=='cadquery' or n.startswith(('hardware.','OCP.','vtk')) for n in added))


if __name__=='__main__':unittest.main()
