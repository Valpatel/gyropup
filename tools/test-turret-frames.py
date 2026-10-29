#!/usr/bin/env python3
"""Check the shipped meshes, not just manifest declarations; no CAD kernel needed."""
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / 'exports/sim/turret_box'
MAN = json.loads((SCENE / 'manifest.json').read_text())
PARTS = {p['name']: p for p in MAN['parts']}


def vertices(path):
    data = path.read_bytes()
    count, = struct.unpack_from('<I', data, 80)
    assert len(data) == 84 + 50 * count
    return [struct.unpack_from('<3f', data, 84 + t * 50 + 12 + v * 12) for t in range(count) for v in range(3)]


class SceneFrames(unittest.TestCase):
    def test_all_meshes_valid_and_match_bounds(self):
        self.assertEqual(len(PARTS), 66)
        for part in PARTS.values():
            with self.subTest(part=part['name']):
                points = vertices(SCENE / part['file'])
                self.assertTrue(all(math.isfinite(n) for p in points for n in p))
                bounds = [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]
                self.assertLessEqual(max(abs(a-b) for a,b in zip(bounds,part['bbox'])), .051)

    def test_rotors_are_centered_on_shafts_and_housings_do_not_spin(self):
        # Independent mechanical datums: Geo.wheel_x71 - Geo.tilt_x48, y=±26.5125;
        # dial axis C(0,0), transformed by pose_shape; flap FILL_PORT.x-19=-39.
        self.assertEqual(MAN['pivots']['dial'], [-48, 0, 0])
        self.assertEqual(MAN['pivots']['wheel_l'], [23, 26.5125, 0])
        self.assertEqual(MAN['pivots']['wheel_r'], [23, -26.5125, 0])
        self.assertEqual(MAN['pivots']['flap'], [-87, 0, 91])
        for name in ['dial', 'flywheel', 'flywheel_m', 'flywheel_tyre', 'flywheel_tyre_m']:
            p = vertices(SCENE / PARTS[name]['file'])
            for axis in [0, 1]:
                self.assertAlmostEqual((min(v[axis] for v in p) + max(v[axis] for v in p))/2, 0, delta=.001)
        for name in ['feed_motor', 'flywheel_motor_l', 'flywheel_motor_r']:
            self.assertEqual(PARTS[name]['group'], 'tilt')
        for name in ['flywheel_motor_l', 'flywheel_motor_r']:
            points = vertices(SCENE / PARTS[name]['file'])
            self.assertAlmostEqual((min(p[0] for p in points)+max(p[0] for p in points))/2, 23, delta=.001)

    def test_effects_follow_the_actual_geometry(self):
        barrel = vertices(SCENE / 'barrel.stl')
        self.assertAlmostEqual(MAN['muzzle'][0], max(p[0] for p in barrel), delta=.001)
        laser = vertices(SCENE / 'laser.stl')
        self.assertAlmostEqual(MAN['laser'][0], max(p[0] for p in laser), delta=.001)
        self.assertEqual(MAN['ball_path'][-1], MAN['muzzle'])
        self.assertEqual([MAN['ball_path'][i][0] for i in [17, 18]], [69,129])
        self.assertEqual(MAN['pivots']['dial'][0] + MAN['pockets'][0][0], MAN['ball_path'][0][0])
        self.assertEqual(MAN['scene_frame_version'], 2)

    def test_coordinate_regeneration_is_reproducible(self):
        spec = importlib.util.spec_from_file_location('reframe', ROOT/'tools/reframe-turret-scene.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            module.regenerate(output)
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (SCENE/path.name).read_bytes(), path.name)
            module.regenerate(output)
            self.assertEqual((output/'manifest.json').read_bytes(), (SCENE/'manifest.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
