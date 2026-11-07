"""Real source-identity fault controls; no CAD kernel or browser is imported."""
from pathlib import Path
import ast
import copy
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
M = runpy.run_path(str(ROOT / 'tools/engineering/robot/readme_design.py'))
CONFIG = json.loads((ROOT / M['CONFIG']).read_text())
ART = Path(os.environ['README_DESIGN_CANDIDATE']) if os.environ.get('README_DESIGN_CANDIDATE') else ROOT / CONFIG['artifacts']['scene_directory']


class DesignIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gyropup-design-identity-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in CONFIG['source']['files']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def change_geometry(self):
        path = self.root / 'hardware/cad/robot/parameters.json'
        data = json.loads(path.read_text())
        data['j501_box']['width'] += 1
        path.write_text(json.dumps(data))

    def test_actual_current_inputs(self):
        self.assertEqual(M['verify_inputs'](self.root, CONFIG), CONFIG['source']['files'])

    def test_published_frame_reader_uses_the_canonical_package(self):
        # Exercise the actual function body without importing a CAD kernel.
        tree = ast.parse((ROOT / 'hardware/cad/body/body_layout.py').read_text())
        reader = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'frame_boxes')
        params = types.SimpleNamespace(z_tray_top=lambda: 5, TOP=30, STOCK={'deck': {'t': 2}},
                                       DECK='deck', POSTS=[], BODY_X=(0, 10), BODY_HALF_Y=8)
        scope = {'bp': params, 'PLATE_H': 12}
        exec(compile(ast.Module(body=[reader], type_ignores=[]), 'current-frame-reader', 'exec'), scope)
        frame = types.ModuleType('hardware.cad.body.body_frame')
        frame.PLATE_STANDOFFS = [(3, 4)]
        frame.PLATE_POST_W = 2
        with patch.object(sys, 'path', [str(ROOT), *sys.path]), \
                patch.dict('sys.modules', {'hardware.cad.body.body_frame': frame}):
            self.assertEqual(scope['frame_boxes']()[-1], ('plate_post_1', (2, 4, 3, 5, 5, 17)))
            self.assertNotIn('cadquery', sys.modules)

    def test_local_parameter_override_rejects_before_reading_it(self):
        with patch.dict(os.environ, {'GYROPUP_LEG_PARAMS': 'not-a-published-input'}):
            with self.assertRaisesRegex(ValueError, 'cannot use GYROPUP_'):
                M['verify_inputs'](self.root, CONFIG)

    def test_geometry_constant_change_rejects(self):
        self.change_geometry()
        with self.assertRaisesRegex(ValueError, 'Recorded CAD inputs changed'):
            M['verify_inputs'](self.root, CONFIG)

    def test_new_effective_input_rejects(self):
        (self.root / 'hardware/cad/new-effective-input.py').write_text('WIDTH_MM = 101\n')
        with self.assertRaisesRegex(ValueError, 'Recorded CAD inputs changed'):
            M['verify_inputs'](self.root, CONFIG)

    def test_missing_current_with_valid_legacy_copy_rejects(self):
        current = self.root / M['SOURCE_CONTEXT']
        legacy = self.root / 'tools/robot_view.py'
        shutil.copyfile(current, legacy)
        current.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or nonregular current input'):
            M['verify_inputs'](self.root, CONFIG)

    def test_supplemental_hardware_data_cannot_escape_the_tree_guard(self):
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, stderr=subprocess.DEVNULL).strip()
        extra = self.root / 'hardware/fuse-board/analysis.json'
        extra.parent.mkdir(parents=True)
        extra.write_text('{"width": 100}\n')
        git('init', '-q')
        git('add', 'hardware')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'source fixture')
        cfg = copy.deepcopy(CONFIG)
        cfg['source']['hardware_tree'] = git('rev-parse', 'HEAD:hardware')
        M['verify_public_tree'](self.root, cfg)
        extra.write_text('{"width": 101}\n')
        with self.assertRaisesRegex(ValueError, 'Unpublished hardware edits'):
            M['verify_public_tree'](self.root, cfg)
        git('add', 'hardware')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'changed source fixture')
        with self.assertRaisesRegex(ValueError, 'Recorded hardware tree changed'):
            M['verify_public_tree'](self.root, cfg)

    def test_rebinding_requested_inputs_cannot_reseal_old_scene(self):
        scene = json.loads((ART / M['NAMES'][0]).read_text())
        self.change_geometry()
        rebound = copy.deepcopy(CONFIG)
        rebound['source']['files'] = M['inputs'](self.root)
        M['verify_inputs'](self.root, rebound)
        with self.assertRaisesRegex(ValueError, 'Stale extracted scene'):
            M['render_svg'](scene, rebound, Path('must-not-load-a-renderer'))

    def test_camera_and_runtime_changes_require_extraction(self):
        scene = json.loads((ART / M['NAMES'][0]).read_text())
        for field in ('projection', 'runtime'):
            cfg = copy.deepcopy(CONFIG)
            if field == 'projection':
                cfg[field]['view'][0] += 0.1
            else:
                cfg[field]['numpy'] = 'not-the-captured-runtime'
            with self.assertRaisesRegex(ValueError, 'Stale extracted scene'):
                M['render_svg'](scene, cfg, Path('must-not-load-a-renderer'))

    def test_real_renderer_survives_scene_dictionary_roundtrip(self):
        scene = json.loads((ART / M['NAMES'][0]).read_text())
        # Recreate the actual extraction's nonalphabetical paint-role insertion
        # order from job237. Geometry and source binding remain untouched.
        for part in scene['parts']:
            part['regions'] = {role: part['regions'][role]
                               for role in CONFIG['projection']['roles_order']
                               if role in part['regions']}
        loaded = json.loads(json.dumps(scene, sort_keys=True))
        self.assertNotEqual(list(scene['parts'][0]['regions']), list(loaded['parts'][0]['regions']))
        profile = Path(os.environ.get('README_ART_PROFILE', ROOT / '.readme-profile'))
        self.assertEqual(M['bundle'](scene, CONFIG, profile, None),
                         M['bundle'](loaded, CONFIG, profile, None))


if __name__ == '__main__':
    unittest.main()
