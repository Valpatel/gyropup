"""Cached-input guards and real shared projection on synthetic tetrahedra only."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import runpy
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
M = runpy.run_path(str(ROOT / 'tools/engineering/robot/readme_design.py'))
CONFIG = json.loads((ROOT / M['CONFIG']).read_text())
PROFILE = Path(os.environ.get('README_ART_PROFILE', ROOT / '.readme-profile'))


def tetra(offset):
    vertices = [(offset, 0, 0), (offset+12, 0, 0), (offset, 12, 0), (offset, 0, 12)]
    faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    return b'SYNTHETIC TEST ONLY'.ljust(80, b'\0') + struct.pack('<I', 4) + b''.join(
        struct.pack('<12fH', 0, 0, 0, *(v for i in face for v in vertices[i]), 0) for face in faces)


class CachedInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='readme-cached-fixture-')
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root, self.collection, self.out = [base / n for n in ('source', 'collection', 'output')]
        for p in (self.root, self.collection / 'meshes', self.out):
            p.mkdir(parents=True)
        for name, content in {
            M['DECODER']: (ROOT / M['DECODER']).read_text(),
            M['SOURCE_CONTEXT']: 'raise AssertionError("CAD source must never be imported")\n',
            'hardware/cad/manufacturing/print_provenance.py':
                'def source_files(root):\n return [root / "hardware/fixture.txt"]\n',
            'hardware/fixture.txt': 'synthetic source only\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.cfg = copy.deepcopy(CONFIG)
        self.cfg.pop('collection', None)
        files = M['inputs'](self.root)
        parts = []
        for i, name in enumerate(('L.fixture', 'body_fixture', 'turret.fixture', 'R.fixture')):
            file = 'meshes/' + name + '.stl'
            (self.collection / file).write_bytes(tetra(i*15))
            parts.append({'name': name, 'file': file, 'sha256': M['digest'](self.collection / file), 'source_group': 'frame'})
        baseline = {'collection261_leg_mesh_sha256': {p['name']: p['sha256'] for p in parts if p['name'].startswith(('L.', 'R.'))},
                    'protected_leg_sources_sha256': {'hardware/fixture.txt': files['hardware/fixture.txt']}}
        path = self.root / M['LEG_BASELINE']
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(baseline))
        M['git'](self.root, 'init', '-q')
        self.commit()
        self.cfg['source'] = {'repository': 'synthetic-fixture-only', 'revision': M['git'](self.root, 'rev-parse', 'HEAD'),
                              'published_baseline': 'synthetic-fixture-only', 'files': files,
                              'hardware_tree': M['git'](self.root, 'rev-parse', 'HEAD:hardware')}
        self.cfg['runtime'] = {'numpy': 'original-native-fixture-version', 'cadquery': 'not-imported'}
        self.data = {'schema': 'gyropup.robot-assembly-parts/1', 'units': 'mm', 'up': 'z',
                     'frame': 'robot: x forward,y left,z up; hip-axis origin', 'source_commit': self.cfg['source']['revision'],
                     'inputs': files, 'hardware_tree': self.cfg['source']['hardware_tree'], 'runtime': self.cfg['runtime'],
                     'native_geometry': {'units': 'mm', 'up': 'z', 'frame': 'assembled robot CAD mm/Z-up',
                                         'hash_platform': {'fixture': 'original native producer, not projection'}},
                     'producer_inputs': {M['DECODER']: 'original-producer-decoder-is-distinct'}, 'parts': parts}
        self.seal()

    def commit(self):
        M['git'](self.root, 'add', '.')
        M['git'](self.root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'synthetic fixture')

    def seal(self):
        (self.collection / 'collection.json').write_text(json.dumps(self.data))
        self.sha = M['digest'](self.collection / 'collection.json')

    def bind(self):
        _, binding = M['collection_binding'](self.root, self.cfg, self.collection, self.sha)
        self.cfg['collection'] = binding
        return binding

    def test_exact_binding_keeps_original_and_consumer_identities_separate(self):
        b = self.bind()
        self.assertEqual(b['parts'], 4)
        self.assertEqual(b['triangles'], dict.fromkeys(M['GROUPS'], 4))
        self.assertEqual(b['native_producer_inputs_sha256'], M['fingerprint'](self.data['producer_inputs']))
        self.assertEqual(b['decoder']['sha256'], M['digest'](self.root / M['DECODER']))
        self.assertNotIn('cadquery', sys.modules)

    def test_byte_seal_and_source_runtime_frame_faults_reject(self):
        with self.assertRaisesRegex(ValueError, 'Collection byte identity'):
            M['collection_binding'](self.root, self.cfg, self.collection, '0'*64)
        for key, bad in [('units', 'm'), ('up', 'y'), ('frame', 'viewer'), ('hardware_tree', 'wrong'),
                         ('inputs', {}), ('runtime', {})]:
            with self.subTest(field=key):
                old = self.data[key]
                self.data[key] = bad
                self.seal()
                with self.assertRaisesRegex(ValueError, 'source/runtime/frame'):
                    self.bind()
                self.data[key] = old
        self.seal()

    def test_duplicate_names_files_membership_and_unsafe_paths_reject(self):
        for field in ('name', 'file'):
            old = self.data['parts'][1][field]
            self.data['parts'][1][field] = self.data['parts'][0][field]
            self.seal()
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                self.bind()
            self.data['parts'][1][field] = old
        self.seal()
        extra = self.collection / 'meshes/extra.stl'
        extra.write_bytes(tetra(0))
        with self.assertRaisesRegex(ValueError, 'membership'):
            self.bind()
        extra.unlink()
        missing = self.collection / self.data['parts'][1]['file']
        original = missing.read_bytes()
        missing.unlink()
        with self.assertRaisesRegex(ValueError, 'membership'):
            self.bind()
        missing.write_bytes(original)
        for name in ('../outside', '/absolute', 'meshes/../collection.json', './collection.json'):
            with self.subTest(path=name), self.assertRaisesRegex(ValueError, 'Unsafe'):
                M['regular_member'](self.collection, name)

    def test_symlink_root_and_member_reject(self):
        alias = self.collection.parent / 'alias'
        alias.symlink_to(self.collection, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Nonregular collection directory'):
            M['collection_binding'](self.root, self.cfg, alias, self.sha)
        mesh = self.collection / self.data['parts'][0]['file']
        outside = self.collection.parent / 'outside.stl'
        mesh.rename(outside)
        mesh.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.bind()

    def test_mesh_bytes_framing_and_nonfinite_reject_even_after_reseal(self):
        mesh = self.collection / self.data['parts'][1]['file']
        original = mesh.read_bytes()
        mesh.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError, 'mesh byte identity'):
            self.bind()
        for payload, message in [(original[:-1], 'count/length'),
                                 (original[:84] + struct.pack('<f', float('nan')) + original[88:], 'Nonfinite')]:
            mesh.write_bytes(payload)
            self.data['parts'][1]['sha256'] = M['digest'](mesh)
            self.seal()
            with self.assertRaisesRegex(ValueError, message):
                self.bind()

    def test_protected_mesh_and_source_cannot_be_rebound(self):
        mesh = self.collection / self.data['parts'][0]['file']
        original_mesh = mesh.read_bytes()
        for field in ('mesh', 'source'):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                if field == 'mesh':
                    row = self.data['parts'][0]
                    mesh = self.collection / row['file']
                    mesh.write_bytes(tetra(100))
                    row['sha256'] = M['digest'](mesh)
                else:
                    self.data['inputs']['hardware/fixture.txt'] = 'changed'
                    self.cfg['source']['files'] = copy.deepcopy(self.data['inputs'])
                self.seal()
                with self.assertRaisesRegex(ValueError, 'Protected leg'):
                    self.bind()
                self.data = data
                mesh.write_bytes(original_mesh)

    def test_new_decoder_and_changed_cached_tolerance_require_new_binding(self):
        self.bind()
        self.cfg['projection']['mesh']['tol'] = 0.1
        with self.assertRaisesRegex(ValueError, 'different tolerance'):
            M['extract_collection'](self.root, self.cfg, Path('must-not-load'), self.collection, self.out)
        self.cfg['projection']['mesh']['tol'] = 0.25
        path = self.root / M['DECODER']
        path.write_text(path.read_text() + '\n# Changed synthetic consumer\n')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Recorded collection binding differs'):
            M['extract_collection'](self.root, self.cfg, Path('must-not-load'), self.collection, self.out)

    def test_old_geometry_cannot_be_restamped_with_new_headers(self):
        self.bind()
        scene = json.loads((ROOT / CONFIG['artifacts']['scene_directory'] / M['NAMES'][0]).read_text())
        scene.update(schema='gyropup.readme-design-collection/1', source=self.cfg['source'],
                     extract_key=M['extract_key'](self.cfg), collection=self.cfg['collection'], native_runtime=self.cfg['runtime'])
        with self.assertRaisesRegex(ValueError, 'membership'):
            M['render_svg'](scene, self.cfg, Path('must-not-load-renderer'))
        # Also reject the actual old 233-part product scene against the new
        # 224-part collection, even if someone replaces every binding header.
        if CONFIG.get('collection'):
            scene.update(source=CONFIG['source'], extract_key=M['extract_key'](CONFIG),
                         collection=CONFIG['collection'], native_runtime=CONFIG['runtime'])
            old = json.loads((Path(__file__).parent / 'fixtures/old-readme-body-membership.json').read_text())
            self.assertEqual(len(old['body']['parts']), 91)
            scene['counts']['body'] = old['body']
            with self.assertRaisesRegex(ValueError, 'membership'):
                M['render_svg'](scene, CONFIG, Path('must-not-load-renderer'))

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'existing NumPy required for actual runtime control')
    def test_runtime_rejects_before_shared_projection(self):
        self.bind()
        self.cfg['projection_runtime'] = {'python': 'wrong', 'numpy': 'wrong'}
        with self.assertRaisesRegex(ValueError, 'Projection runtime differs'):
            M['extract_collection'](self.root, self.cfg, Path('must-not-load'), self.collection, self.out)

    def test_native_import_rejects_before_shared_projection(self):
        self.bind()
        with patch.dict(sys.modules, {'cadquery': object()}):
            with self.assertRaisesRegex(ValueError, 'without CAD modules'):
                M['extract_collection'](self.root, self.cfg, Path('must-not-load'), self.collection, self.out)

    @unittest.skipUnless(PROFILE.is_dir() and importlib.util.find_spec('numpy'), 'real pinned profile and existing NumPy required')
    def test_real_shared_projection_and_motif_preserve_all_inputs(self):
        import numpy as np
        self.bind()
        self.cfg['projection_runtime'] = {'python': f'{sys.version_info.major}.{sys.version_info.minor}', 'numpy': np.__version__}
        original = M['profile_module']
        def guarded_profile(profile, cfg, filename):
            shared = original(profile, cfg, filename)
            if filename == 'extract_mesh.py':
                shared.tessellate = lambda *a, **kw: self.fail('Cached path must not tessellate native geometry')
            return shared
        with patch.dict(M['extract_collection'].__globals__, {'profile_module': guarded_profile}):
            scene = M['extract_collection'](self.root, self.cfg, PROFILE, self.collection, self.out)
        self.assertEqual(scene['native_runtime'], self.data['runtime'])
        self.assertEqual(scene['runtime'], self.cfg['projection_runtime'])
        self.assertFalse(scene['source_policy']['native_construction'])
        self.assertEqual(scene['counts']['body']['triangles'], 4)
        a = M['bundle'](scene, self.cfg, PROFILE, None)
        b = M['bundle'](json.loads(json.dumps(scene, sort_keys=True)), self.cfg, PROFILE, None)
        self.assertEqual(a, b)
        self.assertIn(b'no new CAD construction', a[1])
        self.assertEqual(json.loads((self.out/'source-before.json').read_text()), json.loads((self.out/'source-after.json').read_text()))
        self.assertEqual(json.loads((self.out/'collection-before.json').read_text()), json.loads((self.out/'collection-after.json').read_text()))
        self.assertNotIn('cadquery', sys.modules)

    @unittest.skipUnless(PROFILE.is_dir() and importlib.util.find_spec('numpy'), 'real pinned profile and existing NumPy required')
    def test_projection_failure_survives_a_second_preservation_failure(self):
        import numpy as np
        self.bind()
        self.cfg['projection_runtime'] = {'python': f'{sys.version_info.major}.{sys.version_info.minor}', 'numpy': np.__version__}
        original = M['profile_module']
        def damaged_fixture_profile(profile, cfg, filename):
            shared = original(profile, cfg, filename)
            project = shared.group_drawing
            def damage_after_actual_projection(*args):
                project(*args)  # Exercise the existing projector on tiny real triangles.
                (self.collection / 'unexpected-fixture-output').write_text('synthetic damage')
                raise RuntimeError('primary synthetic projection failure')
            shared.group_drawing = damage_after_actual_projection
            return shared
        with patch.dict(M['extract_collection'].__globals__, {'profile_module': damaged_fixture_profile}):
            with self.assertRaisesRegex(RuntimeError, 'primary synthetic projection failure'):
                M['extract_collection'](self.root, self.cfg, PROFILE, self.collection, self.out)
        self.assertIn('preservation guard failed', (self.out / 'source-guard-error.txt').read_text())
        self.assertNotEqual(json.loads((self.out/'collection-before.json').read_text()), json.loads((self.out/'collection-after.json').read_text()))


if __name__ == '__main__':
    unittest.main()
