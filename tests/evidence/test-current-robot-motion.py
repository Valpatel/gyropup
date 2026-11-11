"""Pure actual-source oracle checks, not a renderer capture or acceptance."""
import argparse
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('current_motion',ROOT/'tools/engineering/robot/current_motion.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--candidate',type=Path);parser.add_argument('--toolkit',type=Path);parser.add_argument('--toolkit-revision')
args,remaining=parser.parse_known_args()


@unittest.skipUnless(args.candidate and args.toolkit and args.toolkit_revision,'Explicit accepted data/shared toolkit identities required')
class CurrentSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motion=oracle.load_motion(args.toolkit,args.toolkit_revision)
        cls.reference=oracle.build_reference(args.candidate,cls.motion)
        cls.source=oracle.source_fivebar(ROOT)

    def test_all224_originals_four_partitions_and_frozen_live_membership(self):
        ref=self.reference;records=ref['component_observations']
        self.assertEqual(len(records),228)
        self.assertEqual(len({r['source_part']for r in records.values()}),224)
        self.assertEqual(sum(bool(r['partition'])for r in records.values()),8)
        self.assertEqual(len(ref['rigid']['contract']['components']),128)
        self.assertEqual(len(ref['live']),15)
        self.assertEqual(sum(len(p['required_poses'])for p in ref['live']),945)
        self.assertEqual(len(ref['helper_observations']),8)
        self.assertEqual(ref['tolerance_mm'],.02)
        self.assertFalse(ref['engineering']['mechanical_ownership_complete'])
        self.assertNotIn('cadquery',sys.modules);self.assertNotIn('OCP',sys.modules)

    def test_home_uses_original_points_without_any_animation_frame(self):
        home=self.reference['live'][0]
        self.assertEqual(home['id'],'home')
        for name,record in self.reference['component_observations'].items():
            actual=home['contract']['components'][name]['points']
            self.assertEqual(len(actual),4)
            for observed,original in zip(actual,record['points']):self.assertLess(math.dist(observed,original),1e-9,name)

    def test_existing_shared_closed_loop_poses_agree_with_the_CAD_source_kinematics(self):
        frames,_=self.source['link_frames'](*self.source['stance'](300))
        self.assertEqual(len(self.reference['rigid']['required_poses']),51)
        for pose in self.reference['rigid']['required_poses']:
            for side in ('L','R'):
                front=math.radians(-frames['upper_front'][1]-pose[side+'.upper_front'])
                rear=math.radians(-frames['upper_rear'][1]-pose[side+'.upper_rear'])
                current,j=self.source['link_frames'](front,rear)
                self.assertIsNotNone(j)
                for lower,upper in [('front_link','upper_front'),('wheel_link','upper_rear')]:
                    wanted=(current[lower][1]-current[upper][1])-(frames[lower][1]-frames[upper][1])
                    error=(pose[side+'.'+lower]-wanted+180)%360-180
                    self.assertLess(abs(error),1e-7,(side,lower))

    def test_symmetric_home_does_not_hide_right_rotation_and_nonhome_source_motion(self):
        record=self.reference['component_observations']['R.upper_link_front']
        home=self.reference['live'][0]['contract']['components']['R.upper_link_front']['points']
        moved=oracle.source_points(record,{'leg_mm':300,'pitch_deg':5,'roll_mm':0,'wheel_deg':0},self.source)
        self.assertGreater(max(math.dist(a,b)for a,b in zip(home,moved)),1)
        wrong=[[-p[0],p[1],p[2]]for p in home]
        self.assertGreater(max(math.dist(a,b)for a,b in zip(home,wrong)),100)


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining])
