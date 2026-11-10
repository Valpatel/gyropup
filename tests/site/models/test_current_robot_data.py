"""Current presentation ownership over actual accepted bytes, without CAD/browser.

The current renderer and independent motion captures are separate requirements.
This test does not qualify composite motor envelopes as resolved rigid owners.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('current_model',ROOT/'tools/site/robot_current_model.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--collection-folder',type=Path)
options,remaining=parser.parse_known_args()


class SourceContract(unittest.TestCase):
    def test_actual_current_pure_source_functions_keep_the_native_home(self):
        source=model.source_fivebar(ROOT)
        frames,joints=source['link_frames'](*source['stance'](300))
        self.assertAlmostEqual(joints['E'][0],0,places=9)
        self.assertAlmostEqual(joints['E'][1],-300,places=9)
        self.assertEqual(source['P']['D'],150)
        self.assertEqual(source['P']['l1'],150);self.assertEqual(source['P']['l2'],250)
        self.assertEqual(set(frames),{'upper_front','upper_rear','front_link','wheel_link','wheel'})
        self.assertNotIn('cadquery',sys.modules)

    def test_source_turret_declares_all_62_owners_and_fixed_housings(self):
        owners=model.turret_owners(ROOT)
        self.assertEqual(len(owners),62)
        for part,owner in [('pan_bearing','base'),('pan_bearing_inner','pan'),
                           ('tilt_bearing','pan'),('tilt_bearing_inner','tilt'),
                           ('pan_servo','base'),('flywheel_motor_l','tilt'),
                           ('flywheel','wheel_l'),('flywheel_2','wheel_r'),
                           ('base_board_screws','base'),('laser','tilt')]:
            self.assertEqual(owners[part],owner)

    def test_grouped_screw_region_rejects_ambiguous_or_straddling_geometry(self):
        for points in ([(0,0,0)]*3,[(75,0,0),(-75,0,0),(75,1,0)],
                       [(75,0,100)]*3,[(75,0,0)]*3,[(75,0,0)]*4):
            with self.subTest(points=points),self.assertRaises(ValueError):
                model.partition_screws(points,'L','screws_links',ROOT)


@unittest.skipUnless(options.collection_folder,'Explicit accepted266 actual bytes required')
class ActualCollection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=options.collection_folder.resolve()
        cls.collection=json.loads((cls.folder/'collection.json').read_bytes())
        with patch('subprocess.Popen',side_effect=AssertionError('No native, Git or network child')):
            cls.result=model.generate(ROOT,cls.collection,cls.folder)

    def test_exact224_inventory_and_original_geometry_identity(self):
        result=self.result
        self.assertEqual(result['ownership_counts'],{'body':82,'leg':80,'turret':62})
        originals={p['name']:p for p in self.collection['parts']}
        self.assertEqual({p['name'] for p in result['parts']},set(originals))
        self.assertEqual(len(result['parts']),224)
        for part in result['parts']:
            for key in ('file','sha256','bounds_mm'):
                self.assertEqual(part[key],originals[part['name']][key])
            points=model.vertices(self.folder/part['file'])
            self.assertEqual([points[i]for i in part['landmark_vertex_indices']],part['landmarks_mm'])
            if 'owner'in part:self.assertIn(part['owner'],result['owners'])
        self.assertFalse(result['moving_coverage']['mechanical_ownership_verified'])
        self.assertIn('L.wheel_hub',result['moving_coverage']['unresolved_composite_envelopes'])
        self.assertIsNone(result['engineering']['mass_kg']);self.assertFalse(result['engineering']['physics_current'])

    def test_original_triangle_records_partition_exactly_once_on_both_sides(self):
        groups=[p for p in self.result['parts']if 'partitions'in p]
        self.assertEqual({p['name']for p in groups},{s+'.'+g for s in ('L','R')for g in model.GROUPED})
        for group in groups:
            blob=(self.folder/group['file']).read_bytes();count=struct.unpack_from('<I',blob,80)[0]
            all_indices=[i for p in group['partitions']for i in p['triangle_indices']]
            self.assertEqual(sorted(all_indices),list(range(count)))
            reunion=b''.join(blob[84+50*i:84+50*(i+1)]for i in sorted(all_indices))
            self.assertEqual(reunion,blob[84:])
            self.assertEqual(hashlib.sha256(reunion).hexdigest(),group['triangle_records_sha256'])
            points=model.vertices(self.folder/group['file'])
            for p in group['partitions']:
                selected=[points[t*3+v]for t in p['triangle_indices']for v in range(3)]
                self.assertEqual([selected[i]for i in p['landmark_vertex_indices']],p['landmarks_mm'])
                self.assertEqual(len(p['landmarks_mm']),4)

    def test_right_module_is_a_rotation_and_all_sources_have_intended_owner(self):
        result=self.result;owners=result['owners'];parts={p['name']:p for p in result['parts']}
        self.assertEqual(owners['R.module']['axis'],[0,0,1])
        self.assertEqual(owners['R.module']['home_rad'],math.pi)
        self.assertEqual(owners['L.module']['origin_mm'],[0,102.5498,0])
        self.assertEqual(owners['R.module']['origin_mm'],[0,-102.5498,0])
        for side in ('L','R'):
            for part,key in [('motor_front','fixed'),('output_adapter_front','upper_front'),
                             ('knee_nut_upper_rear','upper_rear'),('front_link','front_link'),
                             ('wheel_link','wheel_link'),('knee_pin_front','knee_front_point'),
                             ('wheel_hub','apex_point'),('wheel_tyre','wheel')]:
                self.assertEqual(parts[side+'.'+part]['owner'],side+'.'+key)
        self.assertEqual(owners['turret.base']['origin_mm'],[-40.,0,246.])
        self.assertEqual(owners['turret.tilt']['origin_mm'],[0,0,140])
        self.assertEqual(owners['turret.tilt']['parent'],'turret.pan')
        # The old reflected82.3mm module/pan216 is not accepted current metadata.
        self.assertNotEqual(owners['R.module']['origin_mm'],[0,-82.3,0])

    def test_source_frame_effect_anchors_lie_on_actual_collected_owner_geometry(self):
        parts={p['name']:p for p in self.result['parts']};mounts=self.result['mounts']
        tolerance=.00002
        for key,name,axis,high in [('eyes','shell_front',0,True),('eyes_board_front','eyes_board',0,True),
                                    ('camera_front','d435_front',0,True),('camera_rear','d435_rear',0,False),
                                    ('muzzle','turret.barrel',0,True),('laser','turret.laser',0,True)]:
            bounds=parts[name]['bounds_mm'];point=mounts[key]
            self.assertLessEqual(abs(point[axis]-bounds[axis+(3 if high else 0)]),tolerance,key)
            for a in range(3):self.assertTrue(bounds[a]-tolerance<=point[a]<=bounds[a+3]+tolerance,key)
        for name,point in zip(('ear_pod_l','ear_pod_r'),mounts['headlights']):
            bounds=parts[name]['bounds_mm']
            self.assertAlmostEqual(point[0],bounds[3],places=4)
            self.assertAlmostEqual(point[1],(bounds[1]+bounds[4])/2,places=4)
            self.assertAlmostEqual(point[2],(bounds[2]+bounds[5])/2,places=4)

    def test_changed_current_collection_or_source_boundary_rejects(self):
        for field in ('source_commit','parts','inputs','datums'):
            changed=copy.deepcopy(self.collection)
            if field=='parts':changed[field].pop()
            elif field=='inputs':changed[field].pop(next(iter(changed[field])))
            elif field=='datums':changed[field]['y_off_mm']=82.3
            else:changed[field]='0'*40
            with self.subTest(field=field),self.assertRaises(ValueError):
                model.generate(ROOT,changed,self.folder)


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining])
