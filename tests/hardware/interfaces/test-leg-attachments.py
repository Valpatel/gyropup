#!/usr/bin/env python3
"""Check shipped attachment geometry against pinned CAD and stock dimensions."""
import ast
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import types
import unittest

ROOT = (Path(__file__).resolve().parents[3])
sys.path.insert(0, str(ROOT))
from tools.site.source_layout import CONTRACT_FILE, source_file
OUT = (ROOT / 'hardware/exports/sim/v2/leg-attachments')
MAN = json.loads((OUT / 'manifest.json').read_text())
REF = json.loads(((ROOT / 'tests/fixtures/leg-attachment-motion.json')).read_text())



def pinned_source_bytes(name, digest):
    """Keep historical pins while permitting only the exact owning-path edits.

    The manifest's source_revision predates its later source-pin updates. The
    published migration baseline contains those exact pinned bytes; neither
    the manifest nor the meshes are regenerated or relabelled here.
    """
    current = source_file(ROOT, name).read_bytes()
    if name not in ('cad/fivebar.py', 'cad/gmi.py'):
        return current
    baseline = json.loads(CONTRACT_FILE.read_text())['baseline']
    original = subprocess.check_output(['git', 'show', f'{baseline}:{name}'], cwd=ROOT)
    if hashlib.sha256(original).hexdigest() != digest:
        raise AssertionError(f'{name}: the immutable baseline does not match the retained source pin')
    expected = original.decode()
    def relocate(old, new, count=1):
        nonlocal expected
        if expected.count(old) != count:
            raise AssertionError(f'{name}: unexpected relocation replacement count')
        expected = expected.replace(old, new)
    if name == 'cad/fivebar.py':
        relocate('from __future__ import annotations\n', 'from __future__ import annotations\n\n'
            "# Support direct-file CLI execution as well as checkout package imports.\n"
            "if __package__ in (None, ''):\n"
            "    import sys as _checkout_sys\n"
            "    from pathlib import Path as _CheckoutPath\n"
            "    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))\n\n")
        relocate('\nimport gmi\n', '\nimport hardware.cad.robot.gmi as gmi\n')
    else:
        for old, new, count in [
            ('R = Path(__file__).resolve().parents[1]', 'R = (Path(__file__).resolve().parents[3])', 1),
            ("(R / 'cad/interfaces.json')", "((R / 'hardware/cad/robot/interfaces.json'))", 1),
            ("(R / 'catalog/interfaces.json')", "((R / 'hardware/catalog/interfaces.json'))", 2),
            ("R / 'references/vendor'", "(R / 'hardware/vendor')", 2),
        ]:
            relocate(old, new, count)
    if current != expected.encode():
        raise AssertionError(f'{name}: changes beyond the exact source relocation; regenerate/review the attachment evidence')
    return original


def points(file):
    data = file.read_bytes(); count = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84+count*50
    return [struct.unpack_from('<3f', data, 84+t*50+12+v*12) for t in range(count) for v in range(3)]


class Attachments(unittest.TestCase):
    def test_source_and_published_geometry_are_pinned(self):
        for name, digest in {**MAN['source_hashes'], **REF['source_hashes']}.items():
            self.assertEqual(hashlib.sha256(pinned_source_bytes(name, digest)).hexdigest(), digest, name)
        for p in MAN['parts']:
            self.assertEqual(hashlib.sha256((OUT/p['file']).read_bytes()).hexdigest(), p['sha256'])
        self.assertEqual(len(MAN['parts']), 10)

    def test_adapter_is_only_reframed_original_project_geometry(self):
        original = points((ROOT / 'hardware/exports/sim/v2/rig/body__adapter_f_l.stl'))
        current = points(OUT / 'output_adapter.stl')
        self.assertEqual(len(original), len(current))
        self.assertLess(max(abs(a-b-o) for p,q in zip(original,current) for a,b,o in zip(p,q,[75.,82.3,0.])), .00001)

    def test_all_nine_stock_screw_seats_match_the_adapter_interface(self):
        hardware = next(p for p in json.loads(((ROOT / 'hardware/catalog/hardware.json')).read_text()) if p['key']=='screw_m5x25')
        spec=hardware['specs']
        self.assertEqual((spec['length_mm'],spec['head_d_mm'],spec['head_height_mm']),(25.,8.5,5.))
        angles = [45.,75.,105.,165.,195.,225.,285.,315.,345.]
        for i, angle in enumerate(angles,1):
            ps = points(OUT/f'output_screw_{i}.stl')
            # Stock25 mm shank below seat y=-5.6; 5 mm head extends to y=-0.6.
            self.assertAlmostEqual(min(p[1] for p in ps), -30.6, delta=.00001)
            self.assertAlmostEqual(max(p[1] for p in ps), -.6, delta=.00001)
            cx,cz = 18*math.cos(math.radians(angle)),-18*math.sin(math.radians(angle))
            for p in ps:
                radius = math.hypot(p[0]-cx,p[2]-cz)
                self.assertLessEqual(radius,4.25001)
            self.assertAlmostEqual(max(math.hypot(p[0]-cx,p[2]-cz) for p in ps),4.25,delta=.00001)

    def test_future_export_assigns_adapter_and_screws_to_upper_links(self):
        # Execute the real exporter with tiny stand-in solids: this checks output
        # ownership without building the robot or copying its classification logic.
        class Shape:
            def translate(self,*args): return self
        shape=Shape()
        fb=types.SimpleNamespace(leg_parts=lambda:types.SimpleNamespace(parts={k:shape for k in ['hip_frame','upper_link','output_adapter','front_link','wheel_link']}),
            P={'D':150.},Y={'motor_out':-24.6},MOTOR='rs04',botwheel=lambda:(shape,shape),
            upper_output_screws=lambda:[(f'output_screw_{i}',shape) for i in range(1,10)])
        tree=ast.parse(((ROOT / 'software/simulation/robot_v2.py')).read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_rig')
        gmi=types.SimpleNamespace(motor_interface=lambda _: {'od':120,'length':55.7},_cyl=lambda *a:types.SimpleNamespace(union=lambda _:shape),place=lambda *a:shape)
        scope={'fb':fb,'gmi':gmi,'Y_OFF':82.3,'COLORS':dict.fromkeys(['frame','motor','adapter','lidar','link','wheel_link','tyre','hub'],'#fff'),
               'lidar_shape':lambda *a:shape,'_put':lambda group,name,shape,color,**kw:{'name':name,'group':group,'color':color}}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'export_rig','exec'),scope)
        man=scope['export_rig']({'parts':{},'L':{'items':[]}},None,None,[],{})
        self.assertFalse(any('adapter' in p['name'] or 'screw' in p['name'] for p in man['body']))
        self.assertEqual([p['name'] for p in man['links']['upper']],['upper_link','output_adapter',*[f'output_screw_{i}' for i in range(1,10)]])


if __name__=='__main__': unittest.main()
