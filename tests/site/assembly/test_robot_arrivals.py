"""Actual mesh arrival witnesses and scoped recipe dependencies, not fit proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from recipe_path_screen import axial_intervals, screen, topology, triangles
from robot_recipe import robot_operations
spec=importlib.util.spec_from_file_location('arrival_evidence',ROOT/'.agents/plans/assembly-staging/screen-arrivals.py')
evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)


class ArrivalWitnesses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The archived540 screen and its recorded pair inventory are immutable.
        # Today's body recipe is a different source; never regenerate history with it.
        file=ROOT/'.agents/plans/assembly-staging/arrival-witnesses.json'
        assert hashlib.sha256(file.read_bytes()).hexdigest()=='d7126ece3eaf1baea6360666c237360b929778b7db9f62ad5874c07bed1ed315'
        cls.report=json.loads(file.read_bytes())
        cls.cases={case['id']:case for case in cls.report['cases']}

    def test_real_bound_report_is_reproducible_and_retains_limitations(self):
        self.assertEqual(hashlib.sha256(evidence.MODEL.read_bytes()).hexdigest(),self.report['model_sha256'])
        self.assertEqual(hashlib.sha256((ROOT/'tools/site/assembly/recipe_path_screen.py').read_bytes()).hexdigest(),self.report['screen_sha256'])
        cache={}
        def mesh(name):
            if name not in cache:
                part=evidence.PARTS[name];file=evidence.FOLDER/part['file']
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),part['sha256'])
                cache[name]=triangles(file)
                self.assertEqual({'mesh_sha256':part['sha256'],**topology(cache[name])},self.report['mesh_topology'][name])
            return cache[name]
        # Recompute every actual recorded witness using original mesh bytes and
        # the unchanged current screen, without old recipe execution/Git/network.
        for row in self.report['cases']+self.report['candidate_pairs']:
            actual=screen(mesh(row['moving']),mesh(row['fixed']),row['offset_mm'][1])
            if 'samples'not in row:actual.pop('samples')
            for key,value in actual.items():self.assertEqual(value,row[key],(row['moving'],row['fixed'],key))
        self.assertIn('Zero witnesses do not prove',self.report['limits'])
        self.assertEqual(len(self.report['mesh_topology']),42)
        self.assertTrue(all(t['closed_oriented_edges'] for t in self.report['mesh_topology'].values()))
        for case in self.cases.values():
            self.assertEqual(case['unknown_rays'],0,case['id'])
            self.assertEqual(case['surface_samples'],128)
            self.assertEqual(case['sampled_positions'],21)

    def test_old_order_wrong_side_and_terminal_only_checks_fail(self):
        for side in ('L','R'):
            for label in ('motor-through-installed-hip','motor-wrong-inward-through-cheek',
                          'hip-wrong-inward-through-motor','output-screws-after-upper',
                          'wheel-washers-outward-through-hub'):
                case=self.cases[label+'-'+side]
                self.assertGreater(case['max_preterminal_witnesses'],20,case['id'])
                self.assertEqual(case['terminal_witnesses'],0,case['id'])
            for label in ('hip-after-motor-outward','upper-after-output-screws','wheel-washers-inward'):
                case=self.cases[label+'-'+side]
                self.assertEqual(case['max_preterminal_witnesses'],0,case['id'])

    def test_knee_two_sided_obstruction_and_circlip_overlap_stay_unresolved(self):
        for side in ('L','R'):
            for label in ('inboard-bearing-outward-through-shoulder','inboard-bearing-inward-through-upper-eye'):
                self.assertGreater(self.cases[label+'-'+side]['max_preterminal_witnesses'],20)
            self.assertGreater(self.cases['circlip-outward-and-final-overlap-'+side]['terminal_witnesses'],20)

    def test_changed_arrivals_screen_all_installed_obstacle_candidates(self):
        pairs=self.report['candidate_pairs']
        self.assertEqual(len(pairs),72)
        remaining={(p['moving'],p['fixed']) for p in pairs
                   if p['max_preterminal_witnesses'] or p['terminal_witnesses'] or p['unknown_rays']}
        expected={(side+'.'+moving,side+'.'+fixed) for side in ('L','R') for moving,fixed in
                  [('screws_outputs','motor_front'),('screws_outputs','motor_rear'),
                   ('screws_wheel','wheel_link'),('screws_wheel','wheel_hub')]}
        self.assertEqual(remaining,expected)
        # These are existing final envelope/thread contacts, retained for native
        # review; they prevent interpreting this screen as assembly acceptance.
        for pair in pairs:
            self.assertEqual(pair['unknown_rays'],0)
            if (pair['moving'],pair['fixed']) in expected:
                self.assertGreater(pair['terminal_witnesses'],0)

    def test_narrow_recipe_changes_follow_source_supported_dependencies(self):
        operations=robot_operations();flat=[name for op in operations for name in op['additions']]
        for side in ('L','R'):
            for before,after in [('motor_front','hip_frame'),('hip_frame','screws_lugs'),
                                 ('output_adapter_front','screws_outputs'),('screws_outputs','upper_link_front'),
                                 ('washers_wheel','screws_wheel')]:
                self.assertLess(flat.index(side+'.'+before),flat.index(side+'.'+after))
            wheel=next(op for op in operations if side+'.wheel_hub' in op['additions'])
            for name in ('washers_wheel','screws_wheel'):
                self.assertEqual(wheel['offsets'][side+'.'+name],[0,-60 if side=='L' else 60,0])

    def test_degenerate_ray_and_bad_screen_are_unknown_or_rejected(self):
        # A single open face cannot establish an interior; do not call it empty.
        triangle=(((0,0,0),(1,0,0),(0,0,1)),)
        self.assertFalse(topology(triangle)['closed_oriented_edges'])
        self.assertIsNone(axial_intervals((.2,0,.2),triangle,1))
        self.assertIsNone(axial_intervals((0,0,0),triangle,1))
        with self.assertRaises(ValueError):screen(triangle,triangle,0)

if __name__=='__main__':unittest.main()
