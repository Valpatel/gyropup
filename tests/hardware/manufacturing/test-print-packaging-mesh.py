#!/usr/bin/env python3
"""Small real STL→3MF round trip and mutation rejection; CAD environment required."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import trimesh
from cadagent.mesh3mf import read_3mf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'cad'))
import print_provenance as provenance
import turret_print


class RealMeshPackaging(unittest.TestCase):
    def test_round_trip_and_changed_mesh_do_not_replace_valid_package(self):
        with tempfile.TemporaryDirectory(prefix='gyropup-real-print-') as temporary:
            root = Path(temporary)
            (root/'cad').mkdir()
            (root/'cad/model.py').write_text('cube_mm = 1\n')
            (root/'docs').mkdir()
            directory = root/'exports/turret'
            directory.mkdir(parents=True)
            mesh = directory/'cube.stl'
            trimesh.creation.box(extents=[1, 1, 1]).export(mesh)
            original_mesh = mesh.read_bytes()
            inputs = provenance.snapshot(root)
            provenance.write_receipt(root, directory, [mesh], inputs)
            out = directory/'print'
            part = [('cube', 'cube.stl', 'petg', 1, turret_print.PETG, False, 'flat', '')]
            original_writer = turret_print.make_3mf
            with patch.multiple(turret_print, R=root, OUT=out, WORK=root/'scratch', PARTS=part), \
                 patch.object(sys, 'argv', ['turret_print', '--no-slice']), contextlib.redirect_stdout(io.StringIO()):
                turret_print.main()
                vertices, _ = read_3mf(out/'cube.3mf')
                self.assertEqual((vertices.max(axis=0)-vertices.min(axis=0)).tolist(), [1., 1., 1.])
                before = {p: p.read_bytes() for p in [out/'cube.3mf', out/'print.json', root/'docs/turret-print.md']}
                report = json.loads(before[out/'print.json'])
                self.assertEqual(report['parts']['cube']['source']['sha256'], provenance.digest(mesh))
                self.assertEqual(report['parts']['cube']['sha256'], provenance.digest(out/'cube.3mf'))
                self.assertFalse(report['slice_complete'])
                for change_original in (False, True):
                    with self.subTest(change_original=change_original):
                        def mutate(name, staged_mesh, output):
                            trimesh.creation.box(extents=[2, 2, 2]).export(mesh if change_original else staged_mesh)
                            return original_writer(name, staged_mesh, output)
                        with patch.object(turret_print, 'make_3mf', side_effect=mutate), self.assertRaises(ValueError):
                            turret_print.main()
                        self.assertEqual({p: p.read_bytes() for p in before}, before)
                        mesh.write_bytes(original_mesh)


if __name__ == '__main__':
    unittest.main()
