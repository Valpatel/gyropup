#!/usr/bin/env python3
"""Adversarial print identity/transaction tests; no CAD solve or real slicer."""
import ast
import contextlib
import importlib.machinery
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cad'))
import print_provenance as provenance
import print_slicing
import turret_print
REPO = Path(__file__).resolve().parents[1]


class PrintSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'cad').mkdir()
        (self.root/'cad/model.py').write_text('wall_mm = 3\n')
        (self.root/'catalog').mkdir()
        (self.root/'catalog/parts.json').write_text('{"diameter_mm":38}')
        (self.root/'docs').mkdir()
        self.directory = self.root/'exports/turret'
        self.directory.mkdir(parents=True)
        self.out = self.directory/'print'
        self.mesh = self.directory/'flywheel_tyre.stl'
        self.mesh.write_bytes(b'fixture mesh bytes; no geometry claim')
        self.second = self.directory/'second.stl'
        self.second.write_bytes(b'second fixture')
        self.parts = [('first', self.mesh.name, 'petg', 1, turret_print.PETG, False, 'flat', ''),
                      ('second', self.second.name, 'petg', 2, turret_print.PETG, False, 'flat', '')]
        # Actual file-based profile resolution, with a fake executable (never invoked).
        self.profiles = self.root/'bambu-profiles'
        for kind, name in [('machine', turret_print.PRINTER), ('process', turret_print.PROCESS),
                           ('filament', turret_print.FILAMENT['petg'])]:
            folder = self.profiles/kind
            folder.mkdir(parents=True)
            (folder/'base.json').write_text(json.dumps({'name': 'Base', 'filament_density': ['1.25']}))
            (folder/'child.json').write_text(json.dumps({'name': name, 'inherits': 'Base'}))
        self.exe = self.root/'fake-bambu'
        self.exe.write_bytes(b'fake executable revision one')
        slicer = types.ModuleType('cadagent.slicer')
        slicer.executable = lambda: str(self.exe)
        slicer.profile_root = lambda: self.profiles
        package = types.ModuleType('cadagent')
        package.__spec__ = importlib.machinery.ModuleSpec('cadagent', loader=None)
        package.slicer = slicer
        self.slicer = slicer
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {'cadagent': package, 'cadagent.slicer': slicer}).start()
        self.inputs = provenance.snapshot(self.root)
        provenance.write_receipt(self.root, self.directory, [self.mesh, self.second], self.inputs)
        self.writes = []

    def package(self, args=(), mutate=None, slice_result=None):
        def writer(name, mesh, output):
            self.writes.append(name)
            path = output/f'{name}.3mf'
            path.write_bytes(b'3MF fixture: '+mesh.read_bytes())
            if mutate:
                mutate(name, mesh, output)
            return {'file': f'exports/turret/print/{name}.3mf', 'ok': True, 'size_mm': [1, 1, 1]}
        with patch.multiple(turret_print, R=self.root, OUT=self.out, WORK=self.root/'scratch', PARTS=self.parts), \
             patch.object(turret_print, 'make_3mf', side_effect=writer), \
             patch.object(turret_print, 'slice_one', return_value=slice_result or
                          {'grams': 12.5, 'minutes': 20., 'exit_code': 0, 'return_code': 0, 'error': None}), \
             patch.object(sys, 'argv', ['turret_print', *args]), contextlib.redirect_stdout(io.StringIO()):
            turret_print.main()
        return json.loads((self.out/'print.json').read_text())

    def published(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for parent in (self.out, self.root/'docs')
                for p in parent.rglob('*') if p.is_file()}

    def current_rows(self, rows):
        with patch.object(turret_print, 'PARTS', self.parts):
            return provenance.current_slice_rows(self.root, rows, provenance.snapshot(self.root))

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
        design.write_text('{"size":2}')
        with self.assertRaisesRegex(ValueError, 'selected design differs'):
            provenance.validate_mesh(self.root, self.mesh, self.inputs)

    def test_no_slice_has_geometry_coverage_but_no_estimates(self):
        report = self.package(['--no-slice'])
        self.assertTrue(report['complete'])
        self.assertFalse(report['slice_complete'])
        self.assertFalse(report['physical_fit_verified'])
        self.assertIsNone(report['total_grams'])
        self.assertEqual(self.current_rows(report['parts']), {})

    def test_partial_package_refuses_changed_retained_output_before_writes(self):
        self.package(['--no-slice'])
        (self.out/'second.3mf').write_bytes(b'changed output')
        before = self.published()
        self.writes.clear()
        with self.assertRaisesRegex(ValueError, 'retained print output is stale'):
            self.package(['--only', 'first', '--no-slice'])
        self.assertEqual(self.writes, [])
        self.assertEqual(self.published(), before)

    def test_packaging_mutations_preserve_previous_generation_and_document(self):
        self.package(['--no-slice'])
        design = self.root/'trial.json'
        design.write_text('{"size":1}')
        provenance.write_receipt(self.root, self.directory, [self.mesh, self.second], self.inputs,
                                 context=provenance.context_snapshot(self.root, [design]))
        targets = {'original mesh': self.mesh, 'CAD source': self.root/'cad/model.py', 'selected design': design}
        for label, target in targets.items():
            with self.subTest(mutation=label):
                original = target.read_bytes()
                before = self.published()
                def mutate(name, mesh, output):
                    if name == 'first': target.write_bytes(b'changed during packaging')
                with self.assertRaises(ValueError): self.package(['--no-slice'], mutate=mutate)
                self.assertEqual(self.published(), before)
                target.write_bytes(original)
        for label in ('staged mesh', 'earlier staged output'):
            with self.subTest(mutation=label):
                before = self.published()
                def mutate(name, mesh, output):
                    if label == 'staged mesh': mesh.write_bytes(b'changed staged mesh')
                    elif name == 'second': (output/'first.3mf').write_bytes(b'changed staged output')
                with self.assertRaises(ValueError): self.package(['--no-slice'], mutate=mutate)
                self.assertEqual(self.published(), before)

    def test_actual_inherited_profile_and_executable_changes_reject_partial_reuse(self):
        self.package()
        for target in (self.profiles/'filament/base.json', self.exe):
            original = target.read_bytes()
            before = self.published()
            target.write_text('{"name":"Base","filament_density":["9.0"]}' if target.suffix == '.json' else 'new executable')
            self.writes.clear()
            with self.assertRaisesRegex(ValueError, 'retained print output is stale'):
                self.package(['--only', 'first'])
            self.assertEqual(self.writes, [])
            self.assertEqual(self.published(), before)
            self.assertEqual(self.current_rows(json.loads((self.out/'print.json').read_text())['parts']), {})
            target.write_bytes(original)

    def test_profile_changes_during_packaging_do_not_publish(self):
        self.package()
        before = self.published()
        def mutate(name, mesh, output):
            (self.profiles/'filament/base.json').write_text('{"name":"Base","filament_density":["9.0"]}')
        with self.assertRaisesRegex(ValueError, 'slicer inputs changed'):
            self.package(mutate=mutate)
        self.assertEqual(self.published(), before)

    def test_failed_or_invalid_slicer_results_never_publish_or_reuse(self):
        report = self.package()
        before = self.published()
        changes = [{'exit_code': 9}, {'return_code': 1}, {'exit_code': None}, {'error': 'failed'},
                   {'grams': -1}, {'grams': math.nan}, {'grams': math.inf}, {'minutes': 0}]
        for delta in changes:
            with self.subTest(result=delta):
                result = {'grams': 12.5, 'minutes': 20., 'exit_code': 0, 'return_code': 0, 'error': None} | delta
                with self.assertRaisesRegex(ValueError, 'slicer failed'):
                    self.package(slice_result=result)
                self.assertEqual(self.published(), before)
                rows = {'first': report['parts']['first'] | delta}
                self.assertEqual(self.current_rows(rows), {})

    def test_bench_summary_uses_only_accepted_rows_not_old_totals(self):
        report = self.package()
        self.assertEqual(set(self.current_rows(report['parts'])), {'first', 'second'})
        # Execute the real production summary statements without a full geometry build.
        tree = ast.parse((REPO/'cad/build_turret.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        index = next(i for i,n in enumerate(main.body) if isinstance(n, ast.Assign) and
                     any(isinstance(t, ast.Name) and t.id == 'totals' for t in n.targets))
        block = compile(ast.Module(body=main.body[index:index+2], type_ignores=[]), 'production-summary', 'exec')
        (self.out/'print.json').write_text(json.dumps(report | {'total_grams': 1234, 'total_hours': 88}))
        (self.out/'second.3mf').write_bytes(b'stale')
        accepted = self.current_rows(report['parts'])
        scope = {'print_provenance': provenance, 'sliced': accepted, 'plan': {'first': {}, 'second': {}}, 'summary': {}}
        exec(block, scope)
        self.assertEqual(scope['summary']['sliced']['grams'], 12.5)
        self.assertFalse(scope['summary']['sliced']['complete'])
        scope.update(sliced={}, summary={})
        exec(block, scope)
        self.assertNotIn('sliced', scope['summary'])

    def test_valid_partial_rerun_and_no_slice_mode_do_not_mix(self):
        full = self.package()
        partial = self.package(['--only', 'first'])
        self.assertTrue(partial['slice_complete'])
        self.assertEqual(full['parts']['second'], partial['parts']['second'])
        before = self.published()
        with self.assertRaisesRegex(ValueError, 'retained print output is stale'):
            self.package(['--only', 'first', '--no-slice'])
        self.assertEqual(self.published(), before)

    def test_retained_display_and_quantity_fields_must_match_canonical_recipe(self):
        original = self.package()
        changes = {'copies': 200, 'material': 'tpu95', 'settings': {}, 'filament_profile': 'incorrect profile',
                   'orientation': 'incorrect orientation', 'note': 'incorrect instructions'}
        for key, value in changes.items():
            with self.subTest(field=key):
                report = json.loads(json.dumps(original))
                report['parts']['second'][key] = value
                (self.out/'print.json').write_text(json.dumps(report))
                before = self.published()
                self.writes.clear()
                with self.assertRaisesRegex(ValueError, 'retained print output is stale'):
                    self.package(['--only', 'first'])
                self.assertEqual(self.writes, [])
                self.assertEqual(self.published(), before)
                self.assertEqual(set(self.current_rows(report['parts'])), {'first'})
        (self.out/'print.json').write_text(json.dumps(original))

    def test_profile_cycles_and_duplicate_names_fail_closed(self):
        base = self.profiles/'filament/base.json'
        base.write_text(json.dumps({'name': 'Base', 'inherits': turret_print.FILAMENT['petg']}))
        with self.assertRaisesRegex(ValueError, 'Cyclic'): self.package()
        base.write_text('{"name":"Base"}')
        (base.parent/'duplicate.json').write_text('{"name":"Base"}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'): self.package()

    def test_slicer_uses_and_retains_captured_effective_profiles(self):
        identity = print_slicing.capture(turret_print.PRINTER, turret_print.PROCESS, turret_print.FILAMENT['petg'],
                                         {'wall_loops': '5'})
        self.slicer._read_result = lambda _: {'grams': 12.5, 'seconds': 120, 'return_code': 0}
        work = self.root/'slicer-job'
        def fake_process(cmd, **kwargs):
            for kind, expected in identity['effective_profiles'].items():
                self.assertEqual(json.loads((work/f'{kind}.json').read_text()), expected)
            self.assertIn(str(self.mesh.resolve()), cmd)
            return types.SimpleNamespace(returncode=0, stdout='slice complete', stderr='')
        with patch.object(print_slicing.subprocess, 'run', side_effect=fake_process):
            result = print_slicing.run(self.mesh, work, identity)
        self.assertEqual(result['minutes'], 2.)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual((work/'slicer.log').read_text(), 'slice complete')
        self.assertEqual(json.loads((work/'process.json').read_text())['wall_loops'], '5')
        work = self.root/'tampered-slicer-job'
        def change_settings(cmd, **kwargs):
            (work/'process.json').write_text('{}')
            return types.SimpleNamespace(returncode=0, stdout='unexpected settings mutation', stderr='')
        with patch.object(print_slicing.subprocess, 'run', side_effect=change_settings):
            with self.assertRaisesRegex(ValueError, 'Captured slicer settings changed'):
                print_slicing.run(self.mesh, work, identity)

    def test_included_templates_override_parent_before_explicit_child(self):
        folder = self.profiles/'machine'
        (folder/'base.json').write_text(json.dumps({'name': 'Base', 'machine_start_gcode': 'M109 S205', 'a': 'base'}))
        (folder/'one.json').write_text(json.dumps({'name': 'Start', 'machine_start_gcode': 'M109 S[nozzle_temperature_initial_layer]', 'a': 'one'}))
        (folder/'two.json').write_text(json.dumps({'name': 'End', 'machine_end_gcode': 'M104 S0', 'a': 'two'}))
        (folder/'child.json').write_text(json.dumps({'name': turret_print.PRINTER, 'inherits': 'Base', 'include': ['Start', 'End'], 'a': 'child'}))
        profile, files = print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)
        self.assertEqual(profile['machine_start_gcode'], 'M109 S[nozzle_temperature_initial_layer]')
        self.assertEqual(profile['machine_end_gcode'], 'M104 S0')
        self.assertEqual(profile['a'], 'child')
        self.assertNotIn('include', profile)
        self.assertEqual(set(files), {'machine/'+n for n in ('base.json', 'one.json', 'two.json', 'child.json')})
        original = files['machine/one.json']
        (folder/'one.json').write_text(json.dumps({'name': 'Start', 'machine_start_gcode': 'changed'}))
        self.assertNotEqual(original, print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)[1]['machine/one.json'])

    def test_profile_labels_with_slashes_are_not_interpreted_as_paths(self):
        folder = self.profiles/'machine'
        (folder/'support.json').write_text(json.dumps({'name': 'Support For PA/PET', 'support_setting': 'included'}))
        (folder/'child.json').write_text(json.dumps({'name': turret_print.PRINTER, 'include': 'Support For PA/PET'}))
        profile, files = print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)
        self.assertEqual(profile['support_setting'], 'included')
        self.assertEqual(set(files), {'machine/child.json', 'machine/support.json'})

    def test_missing_cyclic_invalid_and_escaping_includes_fail_closed(self):
        child = self.profiles/'machine/child.json'
        for include in (['missing'], [turret_print.PRINTER], ['../outside'], [''], [3], {'invalid': 'type'}):
            child.write_text(json.dumps({'name': turret_print.PRINTER, 'inherits': 'Base', 'include': include}))
            with self.subTest(include=include), self.assertRaises(ValueError):
                print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)
        child.write_text(json.dumps({'name': turret_print.PRINTER, 'include': 'Base'}))
        (self.profiles/'machine/base.json').write_text(json.dumps({'name': 'Base', 'inherits': turret_print.PRINTER}))
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)
        outside = self.root/'outside.json'
        outside.write_text('{"name":"Outside"}')
        (self.profiles/'machine/escape.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            print_slicing._profile(self.profiles, 'machine', turret_print.PRINTER)

    def test_publication_error_rolls_back_output_and_document(self):
        self.package(['--no-slice'])
        before = self.published()
        original = Path.replace
        def fail_document(path, target):
            if path.name == 'turret-print.md': raise OSError('injected document publication failure')
            return original(path, target)
        with patch.object(Path, 'replace', fail_document):
            with self.assertRaisesRegex(OSError, 'injected'): self.package(['--no-slice'])
        self.assertEqual(self.published(), before)
        self.assertFalse(self.out.with_name('print-previous-generation').exists())


if __name__ == '__main__':
    unittest.main()
