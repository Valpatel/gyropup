"""Pure byte/closure controls, using explicitly synthetic non-CAD/non-capture data."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'tools/evidence/media/check-highlights.py'


class CurrentHighlightBindings(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('current_highlight_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.temp = tempfile.TemporaryDirectory(prefix='current-highlight-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.m.ROOT = self.root
        self.directory = self.root / 'software/site/assets/robot-current'
        self.directory.mkdir(parents=True)
        self.authority = self.root / 'software/site/designer/robot_current_source.js'
        self.authority.parent.mkdir(parents=True)
        self.inputs = {}
        self.conversion = {}
        for label, count, mapping in (('CAD', 95, self.inputs), ('conversion', 7, self.conversion)):
            for i in range(count):
                name = f'hardware/fixture/{label}-{i}.txt'
                self.write(name, 'SYNTHETIC non-CAD provenance fixture ' + name)
                mapping[name] = self.sha(self.root / name)
        names = [f'body-{i}' for i in range(82)] + [f'{s}.fixture-{i}' for s in ('L', 'R') for i in range(40)] + [f'turret.fixture-{i}' for i in range(62)]
        parts = []
        for name in names:
            file = 'meshes/' + name + '.stl'
            p = self.directory / file
            p.parent.mkdir(exist_ok=True)
            # These test bytes deliberately are not geometry; this suite checks
            # immutable byte identity, not STL validity or physical behavior.
            p.write_text('SYNTHETIC non-geometry byte fixture ' + name)
            parts.append(dict(name=name, file=file, sha256=self.sha(p)))
        self.collection = dict(schema='gyropup.robot-assembly-parts/1', units='mm', up='z',
            frame='robot: x forward,y left,z up; hip-axis origin', source_commit=self.m.CURRENT_NATIVE,
            inputs=self.inputs, runtime={'fixture': 'original native, not executed'}, producer_inputs={'fixture': 'original producer'}, parts=parts)
        self.model = dict(schema='gyropup.current-robot-presentation/1', units='mm', up='z',
            native_source=self.m.CURRENT_NATIVE, current_inputs=self.inputs, native_runtime=self.collection['runtime'],
            native_producer_inputs=self.collection['producer_inputs'], conversion={'inputs': self.conversion},
            ownership_counts={'body': 82, 'leg': 80, 'turret': 62}, parts=copy.deepcopy(parts))
        self.seal_fixture()

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def seal_fixture(self):
        # Only the synthetic test's external pins change here. Production pins
        # stay fixed to independently accepted collection266/presentation bytes.
        p = self.directory / 'collection.json'
        p.write_text(json.dumps(self.collection))
        self.m.CURRENT_COLLECTION = self.sha(p)
        self.model['collection_sha256'] = self.m.CURRENT_COLLECTION
        p = self.directory / 'manifest.json'
        p.write_text(json.dumps(self.model))
        self.m.CURRENT_SOURCE = {'file': 'web/robot-current/manifest.json', 'sha256': self.sha(p)}
        self.authority.write_text('export const CURRENT_ROBOT_SOURCE = ' + json.dumps(self.m.CURRENT_SOURCE) + ';\n')

    def contract(self):
        return self.m.current_robot_contract()

    def capture_fixture(self):
        current = self.contract()
        bench = self.root / 'hardware/exports/sim/turret_box/manifest.json'
        bench.parent.mkdir(parents=True)
        bench.write_text('{"parts": []}')
        required = self.m.required_capture_inputs(current)
        capture = dict(format=2, currentRobotSource=current['source'], sourceRevision='a'*40,
            servedVersion={'revision': 'a'*40}, width=1280, height=720, fps=30, inputs={}, locationContracts={})
        for public in required:
            path = self.m.project_path(public.lstrip('/'))
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SYNTHETIC source fixture ' + public)
            capture['inputs'][public] = dict(repoSha256=self.sha(path), servedSha256=self.sha(path))
        stage = self.m.project_path('designer/kit/stage.js')
        stage.write_text('const callbacks = [];')
        capture['inputs']['/designer/kit/stage.js'] = dict(repoSha256=self.sha(stage), servedSha256=hashlib.sha256(b'const callbacks = []; window.__captureCallbacks = callbacks;').hexdigest())
        for name in self.m.expected_sources(capture, current):
            path = self.root / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SYNTHETIC encoding/source fixture ' + name)
        capture['locationContracts'] = {n: self.sha(self.root/n) for n in self.m.CAPTURE_LOCATIONS}
        capture['recipeSha256'] = self.sha(self.root/self.m.CAPTURE_SCRIPT)
        hashes = {n: self.sha(self.root/n) for n in self.m.expected_sources(capture, current)}
        # Isolate byte/closure guards from Git history. This explicit resolver
        # double only accepts this one synthetic revision; no capture is claimed.
        def fixture_git(revision, name):
            if revision != 'a'*40:
                raise ValueError('Unknown synthetic Git revision')
            return self.sha(self.root/name)
        self.m.git_sha = fixture_git
        return current, capture, hashes

    def test_capture_location_inventory_binds_the_actual_guarded_helper(self):
        expected = ('tools/site/source-layout.mjs', 'tools/site/source-layout.json',
                    'tests/site/assembly/build-prototype-session.mjs')
        self.assertEqual(self.m.CAPTURE_LOCATIONS, expected)
        recorder = (ROOT / self.m.CAPTURE_SCRIPT).read_text()
        import ast
        import re
        match = re.search(r"^const locationFiles=(\[.*?\]);$", recorder, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(tuple(ast.literal_eval(match.group(1))), expected)
        current, capture, hashes = self.capture_fixture()
        self.m.validate_source_bindings('a'*40, hashes, capture, current)
        capture['locationContracts']['tests/site/content/test-prototype-session.mjs'] = capture['locationContracts'].pop(expected[-1])
        with self.assertRaisesRegex(ValueError, 'Incomplete capture location inputs'):
            self.m.validate_source_bindings('a'*40, hashes, capture, current)

    def test_exact_original_mesh_and_source_closure(self):
        c = self.contract()
        self.assertEqual(len(c['parts']), 224)
        self.assertEqual(len(c['turret_parts']), 62)
        self.assertEqual(len(c['asset_hashes']), 225)
        self.assertEqual(len(c['source_hashes']), 103)
        self.assertNotIn('web/robot-current/collection.json', c['asset_hashes'], 'Original collection is local provenance, not an invented browser response')

    def test_null_wrong_and_unparseable_authorities_reject(self):
        for literal in ('null', '{}', '{"file":"assets/robot-current/manifest.json","sha256":"wrong"}', 'someFunction()'):
            self.authority.write_text('export const CURRENT_ROBOT_SOURCE = ' + literal + ';\n')
            with self.subTest(authority=literal), self.assertRaises(ValueError):
                self.contract()

    def test_manifest_and_collection_bytes_cannot_be_resealed_by_the_capture(self):
        for name in ('manifest.json', 'collection.json'):
            p = self.directory/name
            original = p.read_bytes()
            p.write_bytes(original+b' ')
            with self.subTest(member=name), self.assertRaisesRegex(ValueError, 'bytes differ'):
                self.contract()
            p.write_bytes(original)

    def test_changed_mesh_missing_mesh_and_extra_mesh_reject(self):
        p = self.directory/self.model['parts'][0]['file']
        original = p.read_bytes()
        p.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError, 'mesh bytes differ'):
            self.contract()
        p.unlink()
        with self.assertRaisesRegex(ValueError, 'Nonregular'):
            self.contract()
        p.write_bytes(original)
        (p.parent/'extra.stl').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'membership differs'):
            self.contract()

    def test_duplicate_omitted_and_wrong_collection_members_reject_even_with_fixture_seals(self):
        for fault in ('duplicate', 'omitted', 'wrong-original'):
            before = copy.deepcopy(self.model)
            if fault == 'duplicate':
                self.model['parts'][1] = copy.deepcopy(self.model['parts'][0])
            elif fault == 'omitted':
                self.model['parts'].pop()
            else:
                self.model['parts'][0]['name'] = 'other-original'
            self.seal_fixture()
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'inventory required|original collection'):
                self.contract()
            self.model = before

    def test_wrong_frame_native_and_provenance_reject_with_fixture_seals(self):
        for field, value in (('units', 'm'), ('up', 'y'), ('native_source', 'b'*40), ('current_inputs', {}), ('native_runtime', {}), ('native_producer_inputs', {}), ('conversion', {'inputs': {}})):
            before = copy.deepcopy(self.model)
            self.model[field] = value
            self.seal_fixture()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity differs|provenance differs'):
                self.contract()
            self.model = before

    def test_original_collection_schema_and_frame_cannot_be_reinterpreted(self):
        for field in ('schema', 'frame'):
            original = self.collection[field]
            self.collection[field] = 'different coordinate/schema contract'
            self.seal_fixture()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity differs'):
                self.contract()
            self.collection[field] = original

    def test_changed_cad_and_conversion_source_bytes_reject(self):
        for name in (next(iter(self.inputs)), next(iter(self.conversion))):
            p = self.root/name
            original = p.read_bytes()
            p.write_bytes(original+b'changed')
            with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'source/conversion bytes differ'):
                self.contract()
            p.write_bytes(original)

    def test_escaping_and_symlink_meshes_reject(self):
        p = self.directory/self.model['parts'][0]['file']
        outside = self.root/'outside.stl'
        p.rename(outside)
        p.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Nonregular'):
            self.contract()
        p.unlink()
        outside.rename(p)
        self.model['parts'][0]['file'] = 'meshes/../manifest.json'
        self.seal_fixture()
        with self.assertRaisesRegex(ValueError, 'original collection|original directory'):
            self.contract()

    def test_new_modules_and_all_meshes_are_required_despite_optional_response_map(self):
        c, capture, hashes = self.capture_fixture()
        self.m.validate_source_bindings('a'*40, hashes, capture, c)
        for path in ('/designer/current_robot.js', '/designer/robot_current_source.js', '/designer/robot_identity.js', '/designer/robot_kinematics.js', '/designer/robot_presentations.js', '/designer/robot_sensors.js', '/designer/kit/assembly/guide.js', '/designer/kit/assembly/playback.js', '/' + next(k for k in c['asset_hashes'] if k.endswith('.stl'))):
            bad, bound = copy.deepcopy(capture), dict(hashes)
            bad['inputs'].pop(path)
            bound.pop(self.m.source_for_public(path.lstrip('/')))
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Required renderer or manifest-derived mesh missing'):
                self.m.validate_source_bindings('a'*40, bound, bad, c)

    def test_served_current_manifest_mesh_and_authority_faults_reject(self):
        c, capture, hashes = self.capture_fixture()
        for name in (c['source']['file'], next(k for k in c['asset_hashes'] if k.endswith('.stl'))):
            bad = copy.deepcopy(capture)
            bad['inputs']['/'+name]['servedSha256'] = '0'*64
            with self.subTest(asset=name), self.assertRaisesRegex(ValueError, 'Served current asset differs'):
                self.m.validate_source_bindings('a'*40, hashes, bad, c)
            bad['inputs']['/'+name]['repoSha256'] = '0'*64
            bound = dict(hashes)
            bound[self.m.source_for_public(name)] = '0'*64
            with self.subTest(self_consistent_asset=name), self.assertRaisesRegex(ValueError, 'Served current asset differs'):
                self.m.validate_source_bindings('a'*40, bound, bad, c)
        capture['currentRobotSource'] = {'file': 'web/old-body/manifest.json', 'sha256': '0'*64}
        with self.assertRaisesRegex(ValueError, 'authority differs'):
            self.m.validate_source_bindings('a'*40, hashes, capture, c)

    def test_source_conversion_and_original_collection_omission_reject(self):
        c, capture, hashes = self.capture_fixture()
        for name in (next(iter(self.inputs)), next(iter(self.conversion)), 'software/site/assets/robot-current/collection.json'):
            bound = dict(hashes)
            bound.pop(name)
            with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'Incomplete source closure'):
                self.m.validate_source_bindings('a'*40, bound, capture, c)
        capture['format'] = 1
        with self.assertRaisesRegex(ValueError, 'fresh complete-current capture'):
            self.m.validate_source_bindings('a'*40, hashes, capture, c)

    def test_actual_current_holder_and_every_frame_must_match_originals(self):
        c = self.contract()
        identity = dict(mode='current', robotId='collection266', nativeSource=self.m.CURRENT_NATIVE, collectionSha256=self.m.CURRENT_COLLECTION)
        identity.update({k: 'https://site.fixture.test/'+c['source']['file'] for k in ('bodySource','legSource','turretSource')})
        shot = dict(info=dict(parts=c['parts'], turretParts=c['turret_parts'], presentation=identity), observations=[{'current':dict(mode='current', nativeSource=self.m.CURRENT_NATIVE, collectionSha256=self.m.CURRENT_COLLECTION, parts=224)}])
        self.m.validate_current_shot(shot, c)
        for fault in ('legacy-body', 'legacy-turret-names', 'recorded-holder', 'wrong-native', 'frame-switch'):
            bad = copy.deepcopy(shot)
            if fault == 'legacy-body': bad['info']['parts'] = bad['info']['parts'][:-1]
            elif fault == 'legacy-turret-names': bad['info']['turretParts'] = [n.removeprefix('turret.') for n in c['turret_parts']]
            elif fault == 'recorded-holder': bad['info']['presentation']['robotId'] = 'gyropup-v2-rig'
            elif fault == 'wrong-native': bad['info']['presentation']['nativeSource'] = 'b'*40
            else: bad['observations'][0]['current']['mode'] = 'recorded'
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'snapshot|presentation'):
                self.m.validate_current_shot(bad, c)


if __name__ == '__main__':
    unittest.main()
