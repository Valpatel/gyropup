"""Kernel-free source-closure and surface fault controls for the hip original."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_print_match import correspondence,hip_to_print,point_triangle_distance2,source_guard
from robot_manufacturing import hip_geometry_match


class HipOriginalMatch(unittest.TestCase):
    def test_triangle_distance_regions_and_actual_orientation(self):
        triangle=((0.,0.,0.),(2.,0.,0.),(0.,2.,0.))
        for point,distance in (((.5,.5,1),1),((-1,0,0),1),((1,1,0),0),((3,0,0),1)):
            self.assertAlmostEqual(point_triangle_distance2(point,triangle),distance)
        self.assertEqual(hip_to_print((0,-1,-81.5)),(137,0.,0))
        positive=correspondence([triangle],[triangle],.001)
        self.assertLess(positive['a_to_b']['max_distance_mm'],1e-12)
        wrong=[tuple((p[0],p[1],p[2]+1) for p in triangle)]
        with self.assertRaises(ValueError):correspondence([triangle],wrong,.3011)

    def test_archived_guard_rejects_current_body_without_fallback(self):
        # Complete archival checker/package positives live in the mandatory
        # test_retained_fit_history.py --full job. The default root stays strict.
        collection=json.loads((ROOT/'.agents/plans/robot-assembly/collection-260.json').read_text())
        with self.assertRaisesRegex(ValueError,'Source/context closure changed'):
            source_guard(ROOT,collection)
        self.assertIsNone(hip_geometry_match(ROOT,collection,'L.hip_frame'))


if __name__=='__main__':unittest.main()
