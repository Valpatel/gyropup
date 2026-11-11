"""Pure expected mechanical frames; no kernel, renderer or collector execution."""
import importlib.util
import ast
import contextlib
import io
import copy
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
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

    def test_retained_inventory_allows_only_exact_documented_freeze(self):
        producer = {'part': {'sha256': '0'*64, 'bytes': 3, 'mode': 0o600}}
        actual = {'part': {**producer['part'], 'mode': 0o640}}
        self.assertEqual(data.verify_frozen_inventory(actual, producer, 'fixture')['members'], 1)
        for field, value in [('sha256', '1'*64), ('bytes', 4),
                             *[('mode', m) for m in (0o600, 0o660, 0o644, 0o740, 0o1640)]]:
            with self.subTest(field=field, value=value):
                wrong = copy.deepcopy(actual);wrong['part'][field] = value
                with self.assertRaisesRegex(ValueError, 'content or frozen mode'):
                    data.verify_frozen_inventory(wrong, producer, 'fixture')
        for wrong in ({}, {**actual, 'extra': actual['part']}):
            with self.assertRaisesRegex(ValueError, 'membership'):
                data.verify_frozen_inventory(wrong, producer, 'fixture')
        wrong = copy.deepcopy(producer);wrong['part']['mode'] = 0o644
        with self.assertRaisesRegex(ValueError, 'unexpected producer mode'):
            data.verify_frozen_inventory(actual, wrong, 'fixture')

    def test_source_names_must_not_collide_after_filename_normalization(self):
        self.assertEqual(data.mesh_files(['L.hip_frame'])['L.hip_frame'],'meshes/L__hip_frame.stl')
        for names in (['L.part','L__part'],['../../outside'],['valid','valid']):
            with self.assertRaises(ValueError):data.mesh_files(names)

    def test_isolated_actual_cli_preflights_do_not_need_native_imports(self):
        for file in ('collect_robot_parts.py','export_robot_guide.py','run_robot_collection.py'):
            value=subprocess.check_output([sys.executable,'-I','-S','-B',str(OWNER/file),'--help'],text=True,timeout=5)
            self.assertIn('usage:',value)
            if file != 'export_robot_guide.py':
                self.assertIn('--emit-brep',value)

    def test_optional_payloads_capture_the_same_original_object_in_the_real_worker_loop(self):
        # Execute only the actual serialization loop with explicit non-CAD byte
        # doubles. This establishes control/data flow, never native equivalence.
        tree=ast.parse((OWNER/'collect_robot_parts.py').read_text())
        loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For)
                  and isinstance(n.iter,ast.Name) and n.iter.id=='rows')
        code=compile(ast.Module(body=[loop],type_ignores=[]),'collect_robot_parts serialization contract','exec')
        original=SimpleNamespace(Solids=lambda:[object()],isValid=lambda:True)
        raw=b'explicit non-CAD original-byte contract fixture'
        for enabled in (False,True):
            with self.subTest(enabled=enabled),tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp);(out/'meshes').mkdir();(out/'breps').mkdir();exported=[];captured=[]
                def export(shape,file,**kwargs):
                    self.assertIs(shape,original);exported.append(shape);Path(file).write_bytes(b'not an STL: explicit contract double')
                def capture(shape):
                    self.assertIs(shape,original);captured.append(shape);return raw
                scope={'args':SimpleNamespace(emit_brep=enabled),'rows':[('g','#fff','part',original,(0,0,0))],
                       'filenames':{'part':'meshes/part.stl'},'out':out,'parts':[],'Path':Path,
                       'cq':SimpleNamespace(exporters=SimpleNamespace(export=export)),
                       'bounds':lambda _: [0,0,0,1,1,1],'sha':data.sha,'shape_brep_text':capture,
                       'brep_content_hash':lambda value:'content:'+str(len(value))}
                with contextlib.redirect_stdout(io.StringIO()):exec(code,scope)
                self.assertEqual(exported,[original]);self.assertEqual(captured,[original] if enabled else [])
                part=scope['parts'][0]
                self.assertEqual('native_geometry' in part,enabled)
                if enabled:
                    native=part['native_geometry']
                    self.assertEqual((out/native['file']).read_bytes(),raw)
                    self.assertEqual(native['matrix'],[1,0,0,0,0,1,0,0,0,0,1,0])

    def test_importing_worker_never_imports_native_kernel(self):
        before=set(sys.modules)
        spec=importlib.util.spec_from_file_location('robot_collect_safe',OWNER/'collect_robot_parts.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))
        added=set(sys.modules)-before
        self.assertFalse(any(n=='cadquery' or n.startswith(('hardware.','OCP.','vtk')) for n in added))


if __name__=='__main__':unittest.main()
