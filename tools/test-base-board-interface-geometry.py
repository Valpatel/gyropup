"""Small real-BREP failure controls for the carrier's numerical predicates.

Run with CAD dependencies and the reviewed cad-agent v0.4.2 source on PYTHONPATH.
Does not generate a turret or use private hardware models.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cad'))
import cadquery as cq
from OCP.TopoDS import TopoDS_Shell,TopoDS_Solid
from OCP.BRep import BRep_Builder
from cadagent.gates import Relation
import cadagent.gates.relations as relations
import check_base_board_interfaces as checker


def invalid_open_solid():
    builder=BRep_Builder();shell=TopoDS_Shell();builder.MakeShell(shell)
    builder.Add(shell,cq.Face.makePlane(2,2).wrapped)
    solid=TopoDS_Solid();builder.MakeSolid(solid);builder.Add(solid,shell)
    return cq.Shape.cast(solid)


class NumericalPredicates(unittest.TestCase):
    def setUp(self):
        self.a=cq.Solid.makeBox(2,2,2)
        self.b=cq.Solid.makeBox(2,2,2,cq.Vector(1,0,0))

    def test_actual_overlap_and_clear_control(self):
        self.assertAlmostEqual(checker.overlap(self.a,self.b),4.)
        self.assertEqual(checker.overlap(self.a,self.b.translate((5,0,0))),0.)
        region=cq.Solid.makeBox(5,5,5,cq.Vector(-1,-1,-1))
        self.assertTrue(checker.preserved_region(self.a,self.a,region)[0])
        self.assertFalse(checker.preserved_region(self.a,self.b,region)[0])

    def test_invalid_zero_mass_boolean_cannot_become_clearance(self):
        bad=invalid_open_solid()
        self.assertFalse(bad.isValid())
        self.assertEqual(bad.Volume(),0.)  # reproduce the dangerous old predicate
        original=relations._boolean
        def failed_common(kind,a,b):
            return bad.wrapped if kind=='common' else original(kind,a,b)
        with patch.object(relations,'_boolean',side_effect=failed_common):
            with self.assertRaisesRegex(ValueError,'Undecidable.*invalid BREP'):
                checker.overlap(self.a,self.b)

    def test_small_pair_overlaps_cannot_expand_aggregate_budget(self):
        containing=cq.Workplane('XY').box(2,2,2).val()
        def tiny(volume,x):
            edge=volume**(1/3)
            return cq.Workplane('XY').box(edge,edge,edge).val().translate((x,0,0))
        obstacles=[tiny(.6e-6,x) for x in (-.5,.5)]
        self.assertAlmostEqual(sum(containing.intersect(b).Volume() for b in obstacles),1.2e-6,places=12)
        self.assertEqual(sum(checker.overlap(containing,b) for b in obstacles),0.)
        clear,evidence=checker.clear_of_all(containing,obstacles)
        self.assertFalse(clear)
        self.assertLess(2*evidence['per_pair_overlap_budget_mm3'],1e-6)
        smaller=[tiny(.2e-6,x) for x in (-.5,.5)]
        self.assertTrue(checker.clear_of_all(containing,smaller)[0])
        self.assertTrue(checker.clear_of_all(containing,[b.translate((5,0,0)) for b in obstacles])[0])
        with self.assertRaisesRegex(ValueError,'explicit obstacles'):
            checker.clear_of_all(containing,[])

    def test_invalid_clipped_region_cannot_prove_unchanged_mount(self):
        with patch.object(cq.Shape,'intersect',return_value=invalid_open_solid()):
            with self.assertRaisesRegex(ValueError,'Undecidable.*invalid BREP'):
                checker.preserved_region(self.a,self.a,self.b)

    def test_numerically_unknown_relation_fails_closed(self):
        for reason in ('volumes disagree','volume uncertainty straddles threshold'):
            with self.subTest(reason=reason),patch.object(checker,'relate',return_value=Relation('a','b','unknown',error=reason)):
                with self.assertRaisesRegex(ValueError,'Undecidable'):
                    checker.overlap(self.a,self.b)

    def test_measured_uncertainty_consumes_the_allocated_budget(self):
        # Feed controlled integration estimates through the actual relation
        # policy, rather than injecting a preclassified unknown Relation.
        estimate=relations._VolumeEstimate
        values=[estimate(8,0,0,0),estimate(8,0,0,0),
                estimate(.4e-6,.2e-6,.2e-6,0),estimate(8-.4e-6,0,0,0)]
        with patch.object(relations,'_measure_volume',side_effect=values):
            with self.assertRaisesRegex(ValueError,'straddles'):
                checker.clear_of_all(self.a,[self.a,self.a])

    def test_protected_region_retains_strict_total_difference_boundary(self):
        # Controlled exact mass estimates reproduce the old '< 1e-6' boundary;
        # this is a numerical decision control, not a claimed physical collision.
        region=cq.Solid.makeBox(5,5,5,cq.Vector(-1,-1,-1))
        estimate=relations._VolumeEstimate
        for outside,expected in ((.5e-6,False),(.4e-6,True)):
            values=[estimate(2e-6,0,0,0),estimate(2e-6,0,0,0),
                    estimate(2e-6-outside,0,0,0),estimate(outside,0,0,0),estimate(outside,0,0,0)]
            with self.subTest(total_difference=2*outside),patch.object(relations,'_measure_volume',side_effect=values):
                self.assertEqual(checker.preserved_region(self.a,self.a,region)[0],expected)


if __name__=='__main__':
    unittest.main(verbosity=2)
