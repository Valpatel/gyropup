#!/usr/bin/env python3
"""Reject stale/mixed print inputs before packaging; no CAD generation or slicer."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cad'))
import print_provenance as provenance
import turret_print


class PrintSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'cad').mkdir()
        (self.root/'cad/model.py').write_text('wall_mm = 3\n')
        (self.root/'catalog').mkdir()
        (self.root/'catalog/parts.json').write_text('{"diameter_mm":38}')
        self.directory = self.root/'exports/turret'
        self.directory.mkdir(parents=True)
        self.mesh = self.directory/'flywheel_tyre.stl'
        self.mesh.write_bytes(b'fixture mesh bytes; no geometry claim')
        self.inputs = provenance.snapshot(self.root)
        provenance.write_receipt(self.root, self.directory, [self.mesh], self.inputs)

    def test_current_mesh_and_recorded_identity(self):
        got = provenance.validate_mesh(self.root, self.mesh, self.inputs)
        self.assertEqual(got['sha256'], provenance.digest(self.mesh))
        self.assertEqual(got['file'], 'exports/turret/flywheel_tyre.stl')
        self.assertEqual(next(p[1] for p in turret_print.PARTS if p[0]=='flywheel_tyre'), 'flywheel_tyre.stl')

    def test_changed_source_or_catalogue_requires_fresh_export(self):
        for relative in ['cad/model.py', 'catalog/parts.json', 'cad/new_module.py']:
            with self.subTest(input=relative):
                path = self.root/relative
                before = path.read_bytes() if path.exists() else None
                path.write_text('changed')
                with self.assertRaisesRegex(ValueError, 'inputs differ'):
                    provenance.validate_mesh(self.root, self.mesh, provenance.snapshot(self.root))
                if before is None: path.unlink()
                else: path.write_bytes(before)

    def test_missing_receipt_or_modified_mesh_cannot_be_packaged(self):
        self.mesh.write_bytes(b'different mesh')
        with self.assertRaisesRegex(ValueError, 'changed mesh'):
            provenance.validate_mesh(self.root, self.mesh, self.inputs)
        (self.directory/'print-meshes.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing source receipt'):
            provenance.validate_mesh(self.root, self.mesh, self.inputs)

    def test_changes_during_export_do_not_replace_receipt(self):
        receipt = self.directory/'print-meshes.json'
        original = receipt.read_bytes()
        (self.root/'cad/model.py').write_text('changed during export')
        with self.assertRaisesRegex(ValueError, 'during export'):
            provenance.write_receipt(self.root, self.directory, [self.mesh], self.inputs)
        self.assertEqual(receipt.read_bytes(), original)

    def test_selected_design_outside_standard_folders_still_bound(self):
        design = self.root/'selected-trial.json'
        design.write_text('{"size":1}')
        context = provenance.context_snapshot(self.root, [design])
        provenance.write_receipt(self.root, self.directory, [self.mesh], self.inputs, context=context)
        provenance.validate_mesh(self.root, self.mesh, self.inputs)
        design.write_text('{"size":2}')
        with self.assertRaisesRegex(ValueError, 'selected design differs'):
            provenance.validate_mesh(self.root, self.mesh, self.inputs)

    def test_partial_package_refuses_stale_retained_rows_before_writes(self):
        out = self.directory/'print'
        out.mkdir()
        second = self.directory/'second.stl'
        second.write_bytes(b'second fixture mesh')
        provenance.write_receipt(self.root, self.directory, [self.mesh, second], self.inputs)
        parts = [('first', self.mesh.name, 'petg', 1, turret_print.PETG, False, 'flat', ''),
                 ('second', second.name, 'petg', 1, turret_print.PETG, False, 'flat', '')]
        writes = []
        def fake_writer(name, mesh):
            writes.append(name)
            path = out/f'{name}.3mf'
            path.write_bytes(b'3MF stub; packaging logic only: '+name.encode())
            return {'file': path.relative_to(self.root).as_posix(), 'ok': True}
        with patch.multiple(turret_print, R=self.root, OUT=out, WORK=self.root/'scratch', PARTS=parts), \
             patch.object(turret_print, 'make_3mf', side_effect=fake_writer), \
             patch.object(turret_print, 'write_doc'), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(sys, 'argv', ['turret_print', '--no-slice']):
                turret_print.main()
            original = json.loads((out/'print.json').read_text())
            self.assertTrue(original['complete'])
            self.assertFalse(original['physical_fit_verified'])
            writes.clear()
            # A retained 3MF changed after its receipt was produced.
            (out/'second.3mf').write_bytes(b'changed output')
            before = (out/'first.3mf').read_bytes()
            with patch.object(sys, 'argv', ['turret_print', '--only', 'first', '--no-slice']):
                with self.assertRaisesRegex(ValueError, 'retained print output is stale'):
                    turret_print.main()
            self.assertEqual(writes, [])
            self.assertEqual((out/'first.3mf').read_bytes(), before)
            self.assertEqual(json.loads((out/'print.json').read_text()), original)
            # A rebuilt bench report may reuse only current, actually sliced rows.
            first = original['parts']['first'] | {'grams': 10.0, 'minutes': 20.0}
            second_row = original['parts']['second'] | {'grams': 5.0, 'minutes': 8.0}
            current = provenance.current_slice_rows(self.root, {'first': first, 'second': second_row}, self.inputs)
            self.assertEqual(set(current), {'first'})
            (self.root/'cad/model.py').write_text('new geometry')
            self.assertEqual(provenance.current_slice_rows(self.root, {'first': first}, provenance.snapshot(self.root)), {})


if __name__ == '__main__':
    unittest.main()
