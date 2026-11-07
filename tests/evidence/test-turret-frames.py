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
        self.assertEqual(set(fixture['source']['parts']), set(REFERENCE.OWNERS))
        for name, binding in fixture['source']['parts'].items():
            self.assertEqual(binding['group'], REFERENCE.OWNERS[name])
            self.assertEqual(binding['file'], name+'.stl')
            self.assertEqual(PARTS[name]['group'], binding['group'])
            self.assertEqual(PARTS[name]['file'], binding['file'])
            self.assertEqual(binding['sha256'], hashlib.sha256((SCENE/binding['file']).read_bytes()).hexdigest())
            self.assertEqual(fixture['contract']['components'][name]['joint'],
                             binding['group'] if binding['group'] in REFERENCE.JOINTS else None)

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
