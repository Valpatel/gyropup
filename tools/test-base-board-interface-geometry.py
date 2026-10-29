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

    def test_invalid_clipped_region_cannot_prove_unchanged_mount(self):
        with patch.object(cq.Shape,'intersect',return_value=invalid_open_solid()):
            with self.assertRaisesRegex(ValueError,'Undecidable.*invalid BREP'):
                checker.preserved_region(self.a,self.a,self.b)

    def test_numerically_unknown_relation_fails_closed(self):
        for reason in ('volumes disagree','volume uncertainty straddles threshold'):
            with self.subTest(reason=reason),patch.object(checker,'relate',return_value=Relation('a','b','unknown',error=reason)):
                with self.assertRaisesRegex(ValueError,'Undecidable'):
                    checker.overlap(self.a,self.b)


if __name__=='__main__':
    unittest.main(verbosity=2)
