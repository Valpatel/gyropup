#!/usr/bin/env python3
"""Check the shipped meshes, not just manifest declarations; no CAD kernel needed."""
import hashlib
import copy
import importlib.util
import json
import math
from pathlib import Path
import struct
import unittest

ROOT = (Path(__file__).resolve().parents[2])
SCENE = (ROOT / 'hardware/exports/sim/turret_box')
MAN = json.loads((SCENE / 'manifest.json').read_text())
PARTS = {p['name']: p for p in MAN['parts']}
SPEC = importlib.util.spec_from_file_location('turret_reference', ROOT/'tools/engineering/turret/reference-turret-motion.py')
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)


def vertices(path):
    data = path.read_bytes()
    count, = struct.unpack_from('<I', data, 80)
    assert len(data) == 84 + 50 * count
    return [struct.unpack_from('<3f', data, 84 + t * 50 + 12 + v * 12) for t in range(count) for v in range(3)]


class SceneFrames(unittest.TestCase):
    def test_reference_is_bound_to_the_actual_current_scene(self):
        fixture = json.loads((ROOT/'tests/fixtures/turret-motion-reference.json').read_text())
        self.assertIn('source', fixture, 'Regenerate the reference from the reviewed immutable full scene')
        self.assertEqual(fixture['source']['manifest_sha256'], hashlib.sha256((SCENE/'manifest.json').read_bytes()).hexdigest())
        self.assertEqual(fixture['source']['ball_path_sha256'], hashlib.sha256((ROOT/'hardware/exports/turret/lidar/box.json').read_bytes()).hexdigest())
        self.assertEqual(fixture['source']['limits_sha256'], hashlib.sha256((ROOT/'hardware/exports/turret/limits.json').read_bytes()).hexdigest())
        for name, digest in fixture['source']['cad_source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(set(fixture['source']['parts']), set(REFERENCE.OWNERS))
        for name, binding in fixture['source']['parts'].items():
            self.assertEqual(binding['group'], REFERENCE.OWNERS[name])
            self.assertEqual(binding['file'], name+'.stl')
            self.assertEqual(PARTS[name]['group'], binding['group'])
            self.assertEqual(PARTS[name]['file'], binding['file'])
            self.assertEqual(binding['sha256'], hashlib.sha256((SCENE/binding['file']).read_bytes()).hexdigest())
            self.assertEqual(fixture['contract']['components'][name]['joint'],
                             binding['group'] if binding['group'] in REFERENCE.JOINTS else None)

    def test_ball_path_claim_has_complete_current_range_evidence(self):
        report=json.loads((ROOT/'hardware/exports/turret/lidar/box.json').read_text())
        limits=json.loads((ROOT/'hardware/exports/turret/limits.json').read_text())
        self.assertTrue(REFERENCE.box_path_coverage(report, MAN, limits))
        self.assertTrue(MAN['checks']['ball_path']['current'])
        self.assertTrue(MAN['checks']['ball_path']['clear'])

    def test_all_meshes_valid_and_match_bounds(self):
        self.assertEqual(len(PARTS), 80)
        for part in PARTS.values():
            with self.subTest(part=part['name']):
                points = vertices(SCENE / part['file'])
                self.assertEqual(part['sha256'], hashlib.sha256((SCENE / part['file']).read_bytes()).hexdigest())
                self.assertTrue(all(math.isfinite(n) for p in points for n in p))
                bounds = [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]
                self.assertLessEqual(max(abs(a-b) for a,b in zip(bounds,part['bbox'])), .051)

    def test_rotors_are_centered_on_shafts_and_housings_do_not_spin(self):
        # Independent mechanical datums: Geo.wheel_x73 - Geo.tilt_x48, y=wheel_c/2=±25.81;
        # dial axis C(0,0), transformed by pose_shape; flap FILL_PORT.x-19=-39.
        self.assertEqual(MAN['pivots']['dial'], [-48, 0, 0])
        self.assertEqual(MAN['pivots']['wheel_l'], [25, 25.81, 0])
        self.assertEqual(MAN['pivots']['wheel_r'], [25, -25.81, 0])
        self.assertEqual(MAN['pivots']['flap'], [-87, 0, 91])
        for name in ['dial', 'flywheel', 'flywheel_m', 'flywheel_tyre', 'flywheel_tyre_m']:
            p = vertices(SCENE / PARTS[name]['file'])
            for axis in [0, 1]:
                self.assertAlmostEqual((min(v[axis] for v in p) + max(v[axis] for v in p))/2, 0, delta=.001)
        for name in ['feed_motor', 'flywheel_motor_l', 'flywheel_motor_r']:
            self.assertEqual(PARTS[name]['group'], 'tilt')
        for name in ['flywheel_motor_l', 'flywheel_motor_r']:
            points = vertices(SCENE / PARTS[name]['file'])
            self.assertAlmostEqual((min(p[0] for p in points)+max(p[0] for p in points))/2, 25, delta=.001)

    def test_effects_follow_the_actual_geometry(self):
        barrel = vertices(SCENE / 'barrel.stl')
        self.assertAlmostEqual(MAN['muzzle'][0], max(p[0] for p in barrel), delta=.001)
        for axis in [1, 2]:
            self.assertAlmostEqual(MAN['muzzle'][axis], (min(p[axis] for p in barrel) + max(p[axis] for p in barrel))/2, delta=.001)
        laser = vertices(SCENE / 'laser.stl')
        self.assertAlmostEqual(MAN['laser'][0], max(p[0] for p in laser), delta=.001)
        self.assertEqual(MAN['ball_path'][-1], MAN['muzzle'])
        self.assertEqual([MAN['ball_path'][i][0] for i in [17, 18]], [72,132])
        self.assertEqual(MAN['pivots']['dial'][0] + MAN['pockets'][0][0], MAN['ball_path'][0][0])
        self.assertEqual(MAN['scene_frame_version'], 2)

    def test_the_scene_is_one_full_build(self):
        # The scene comes from cad/build_turret_box.py (D76 turret, no compute plinth), not from
        # tools/reframe-turret-scene.py, which only migrated the October snapshot. Every file is in the manifest.
        self.assertEqual({p.name for p in SCENE.iterdir()} - {'manifest.json'}, {p['file'] for p in PARTS.values()})
        self.assertTrue(MAN['built'])
        for name in PARTS:
            self.assertNotRegex(name, r'(?i)plinth|compute|j4012|xt30|ethernet')


class ReferenceInputGuards(unittest.TestCase):
    def test_box_path_guard_rejects_real_old_and_incomplete_coverage(self):
        # Byte-exact published b61f0cd4 report, not a fabricated stale example.
        raw=(ROOT/'tests/fixtures/turret-box-ball-path-before-elevation.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'e6b4b3807f381ce9d1c073e7db1dea7a593c67c05aacceeb8fb63a1c4e45faab')
        old=json.loads(raw)
        scene=copy.deepcopy(MAN);scene['limits']['tilt_deg']=[-25,12]
        limits={'tilt_deg':{'min':-25,'max':12}}
        with self.assertRaisesRegex(ValueError,'current mechanical range'):
            REFERENCE.box_path_coverage(old,scene,limits)
        # Explicit guard fixture only; no positive-angle geometry is inferred.
        candidate=copy.deepcopy(old);candidate['turret']['tilt_range_deg']=[-25,12]
        candidate['elevation_limited_pans_deg']=None
        for row in candidate['per_pan']: row['max_elevation_deg']=12
        for row in candidate['firmware_table']: row['max_tilt_deg']=12
        self.assertTrue(REFERENCE.box_path_coverage(candidate,scene,limits))
        for kind in ('missing-upper','lower-narrowed','upper-narrowed','missing-pan','duplicate-pan','firmware-upper','margin','ball','height','scene-range'):
            bad=copy.deepcopy(candidate)
            if kind=='missing-upper': bad['per_pan'][0].pop('max_elevation_deg')
            elif kind=='lower-narrowed': bad['per_pan'][0]['max_depression_deg']=-20
            elif kind=='upper-narrowed': bad['per_pan'][0]['max_elevation_deg']=10
            elif kind=='missing-pan': bad['per_pan'].pop()
            elif kind=='duplicate-pan': bad['per_pan'][1]['pan']=bad['per_pan'][0]['pan']
            elif kind=='firmware-upper': bad['firmware_table'][0].pop('max_tilt_deg')
            elif kind=='margin': bad['margin_mm']=5
            elif kind=='ball': bad['ball']['d_mm']=22.7
            elif kind=='height': bad['obstacles'][0]['lo'][2]-=1
            else: scene_bad=copy.deepcopy(scene);scene_bad['limits']['tilt_deg']=[-25,0];
            if kind=='scene-range':
                with self.assertRaises(ValueError): REFERENCE.box_path_coverage(bad,scene_bad,limits)
                continue
            with self.subTest(kind=kind), self.assertRaises(ValueError): REFERENCE.box_path_coverage(bad,scene,limits)

    def test_actual_parser_rejects_display_ownership_and_identity_corruption(self):
        # Explicit input-validator fixture, not a fresh scene or geometry claim.
        candidate = copy.deepcopy(MAN)
        candidate['limits']['tilt_deg'] = [-25, 12]
        candidate['limits']['fire_tilt_max_deg'] = 10
        self.assertEqual(set(REFERENCE.manifest_parts(candidate)), set(REFERENCE.OWNERS))
        for kind in ('units', 'frame', 'missing', 'duplicate', 'foreign', 'file', 'motor-owner', 'boolean-pivot'):
            bad = copy.deepcopy(candidate)
            if kind == 'units': bad['units'] = 'm'
            elif kind == 'frame': bad['scene_frame_version'] = 1
            elif kind == 'missing': bad['parts'].pop()
            elif kind == 'duplicate': bad['parts'][0] = copy.deepcopy(bad['parts'][1])
            elif kind == 'foreign': bad['parts'][0]['name'] = 'foreign-part'
            elif kind == 'file': bad['parts'][0]['file'] = '../other.stl'
            elif kind == 'motor-owner':
                next(p for p in bad['parts'] if p['name'] == 'flywheel_motor_l')['group'] = 'wheel_l'
            else: bad['pivots']['pan'][0] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError): REFERENCE.manifest_parts(bad)

    def test_actual_stl_parser_rejects_truncation_nonfinite_and_planar_landmarks(self):
        data = (SCENE/'barrel.stl').read_bytes()
        points = REFERENCE.vertices(data)
        self.assertEqual(len(REFERENCE.landmarks(points)), 4)
        bad = bytearray(data)
        struct.pack_into('<f', bad, 84+12, float('nan'))
        for payload in (data[:83], data[:-1], bytes(bad)):
            with self.assertRaises(ValueError): REFERENCE.vertices(payload)
        with self.assertRaises(ValueError): REFERENCE.landmarks([[x,y,0] for x,y,z in points])


if __name__ == '__main__':
    unittest.main()
