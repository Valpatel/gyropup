"""The browser kit's golden vectors are what the Python driver makes now, and the build profiles agree with their
sources. The JavaScript side of the vectors is designer/kit/rs04/rs04.test.mjs.

    python -m unittest rig.tests.test_rs04_vectors
"""
from __future__ import annotations

import copy
import unittest

from rig import rs04_profiles, rs04_vectors


class VectorTests(unittest.TestCase):
    def test_committed_vectors_are_current(self):
        self.assertEqual(rs04_vectors.OUT.read_text(), rs04_vectors.render(),
                         'designer/kit/rs04/vectors.json is stale: run python -m rig.rs04_vectors')

    def test_vectors_use_the_default_profile_limits(self):
        self.assertEqual(rs04_vectors.LIMITS, rs04_profiles.load('pla-bench')['limits'])


class ProfileTests(unittest.TestCase):
    def test_profiles_load_and_agree_with_their_sources(self):
        names = rs04_profiles.names()
        self.assertIn('pla-bench', names)
        self.assertIn('final', names)
        self.assertEqual(rs04_profiles.load()['id'], 'pla-bench')
        for n in names:
            self.assertEqual(rs04_profiles.check(rs04_profiles.load(n)), [], n)

    def test_the_index_lists_every_profile(self):
        import json
        index = json.loads((rs04_profiles.DIR / 'index.json').read_text())
        self.assertEqual(sorted(index['profiles']), rs04_profiles.names())

    def test_a_drifted_number_is_caught(self):
        p = copy.deepcopy(rs04_profiles.load('pla-bench'))
        p['limits']['limit_torque_nm'] = 13.0
        self.assertTrue(any('limit_torque_nm' in e for e in rs04_profiles.check(p)))
        p = copy.deepcopy(rs04_profiles.load('final'))
        p['motor_config']['canTimeout'] = 0
        self.assertTrue(any('canTimeout' in e for e in rs04_profiles.check(p)))

    def test_unsafe_limits_are_refused(self):
        for key, v in (('jog_torque_nm', 20.0), ('can_timeout_ticks', 0), ('jog_speed_rad_s', 30.0)):
            p = copy.deepcopy(rs04_profiles.load('pla-bench'))
            p['limits'][key] = v
            with self.assertRaises(ValueError, msg=key):
                rs04_profiles.validate(p)

    def test_pending_references_name_their_issue(self):
        for n in rs04_profiles.names():
            for ref in rs04_profiles.load(n).get('references', []):
                if not (rs04_profiles.ROOT / ref['file']).is_file():
                    self.assertRegex(ref.get('pending', ''), r'^#\d+$', ref['file'])


if __name__ == '__main__':
    unittest.main()
