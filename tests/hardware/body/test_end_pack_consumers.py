"""Real caller/metadata flow with explicit non-CAD, non-browser, non-solver doubles.

These controls do not establish native geometry, optical calibration or physics.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub(name, **attrs):
    module = ModuleType(name)
    module.__dict__.update(attrs)
    return module


@contextmanager
def module_doubles(mapping):
    with ExitStack() as stack:
        # from-package imports may use existing parent attributes, not sys.modules.
        for name, value in mapping.items():
            parent, _, child = name.rpartition('.')
            if parent:
                owner = mapping.get(parent) or importlib.import_module(parent)
                stack.enter_context(patch.object(owner, child, value, create=True))
        stack.enter_context(patch.dict(sys.modules, mapping))
        yield


def forbidden(*args, **kwargs):
    raise AssertionError('Browser, native CAD or solver execution forbidden in consumer controls')


def actual_v2_helpers():
    path = ROOT/'software/simulation/robot_v2.py'
    names = {'_configure_output', 'generated_file', 'sensor_mounts'}
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    module = stub('software.simulation.robot_v2', Path=Path, R=ROOT)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), module.__dict__)
    return module


def actual_sensor_source():
    """Actual source constants/functions, capturing boxes as numbers, not solids."""
    path = ROOT/'hardware/cad/body/body_shell.py'
    assignments = {'WALL_T', 'XI', 'XO', 'EYES', 'D435'}
    functions = {'d435_face_x', 'd435', 'eyes_board'}
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in assignments for t in n.targets)) or
             (isinstance(n, ast.FunctionDef) and n.name in functions)]
    module = stub('hardware.cad.body.body_shell', bp=SimpleNamespace(BODY_X=(-160., 160.)), box=lambda *v: v)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), module.__dict__)
    return module


@pytest.mark.parametrize('selected,needs_mounts', [('bus_bar', False), ('end_pack_holder', False), ('floor_tray', True)])
def test_actual_quote_entry_uses_current_factories_without_browser_or_solids(tmp_path, selected, needs_mounts):
    calls, quoted = [], []
    mounts = {'test': 'explicit non-CAD mounts'}
    def factory(name):
        def make(*args):
            calls.append((name, args))
            return SimpleNamespace(features=[])
        return make
    frame = stub('hardware.cad.body.body_frame', **{name: factory(name) for name in
                 ['cheek_part', 'tray_part', 'belly_part', 'deck_part', 'pallet_part', 'power_plate_part', 'bus_bar_part', 'turret_plate_part']})
    battery = stub('hardware.cad.body.body_battery', holder_part=factory('holder_part'))  # deliberately no retired factories
    layout = stub('hardware.cad.body.body_layout', layout=lambda: {'mounts': mounts})
    sheet = stub('hardware.cad.body.body_sheet', dxf_geometry_sha1=lambda _: 'explicit-fixture-digest')
    class Context:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    playwright = stub('playwright', __path__=[])
    api = stub('playwright.sync_api', sync_playwright=lambda: Context())
    body, out = tmp_path/'body.json', tmp_path/'prices.json'
    body.write_text(json.dumps({'sheet': {name: {'dxf': name+'.dxf'} for name in ['bus_bar', 'end_pack_holder', 'floor_tray']}}))
    with module_doubles({frame.__name__: frame, battery.__name__: battery, layout.__name__: layout,
                         sheet.__name__: sheet, 'playwright': playwright, api.__name__: api}):
        quote = load('end_pack_quote_control', 'tools/acquisition/sendcutsend_quote.py')
        fake_app = SimpleNamespace(close=lambda: None)
        def fake_quote(app, path, order):
            quoted.append(path.name)
            return {'final': {'each': 1, 'subtotal': 1}}
        with patch.object(quote, 'App', return_value=fake_app), patch.object(quote, 'quote', side_effect=fake_quote), \
             patch.object(quote, 'order_of', return_value={'qty': 1}), \
             patch.object(sys, 'argv', ['quote', '--body', str(body), '--out', str(out), '--only', selected]):
            quote.main()
    assert list(json.loads(out.read_text())) == [selected]
    assert quoted == [selected+'.dxf']
    assert len(calls) == 1
    assert calls[0][1] == ((mounts,) if needs_mounts else ())
    assert calls[0][0] == {'bus_bar': 'bus_bar_part', 'end_pack_holder': 'holder_part', 'floor_tray': 'tray_part'}[selected]


def fixture_result():
    return {'pass': False, 'reasons': ['Explicit non-physics control'], 'max_theta_deg': 0., 'top_speed_mps': 0.,
            'x_max_m': 0., 'motors': {'wheel_l': {'of_peak': .1, 'peak_torque_nm': 1., 'saturated_s': 0.}}}


def candidate_builder(v2, calls, *, model='different/model.xml'):
    def build(out):
        v2._configure_output(out)  # actual fresh-root guard, before any fixture files
        calls.append(Path(out))
        root = Path(out)
        files = {'model': model, 'rig_manifest': 'different/rig/manifest.json', 'model_info': 'different/info.json'}
        for name in (files['rig_manifest'], files['model_info']):
            file = root/name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('explicit non-native fixture')
        if not Path(model).is_absolute() and '..' not in Path(model).parts:
            file = root/model; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('not MJCF: fixture only')
        return {'files': files, 'design': 'fixture', 'name': 'Explicit non-native fixture', 'total_mass_kg': 1.,
                'mass_reconciles': True, 'estimates': ['fixture only'], 'wheel_motor': {'peak_nm': 10.}}
    return build


def test_actual_simulate_cli_propagates_fresh_output_and_returned_paths(tmp_path):
    v2 = actual_v2_helpers(); calls, runs = [], []
    v2.build = candidate_builder(v2, calls)
    scenarios = stub('software.simulation.scenarios', SCENARIOS={'stand': object()}, recoil_scenario=forbidden,
                     run=lambda xml, info, scenario, **kw: (runs.append((xml, kw)) or fixture_result()))
    with module_doubles({'software.simulation.robot_v2': v2, 'software.simulation.scenarios': scenarios,
                         'software.simulation.model': stub('software.simulation.model', build=forbidden)}):
        sim = load('end_pack_simulate_control', 'tools/engineering/robot/simulate.py')
        root = tmp_path/'candidate'
        with patch.object(sys, 'argv', ['simulate', '--v2', '--out', str(root), '--only', 'stand', '--video']), \
             patch.dict('os.environ', {'GYROPUP_EXPORTS': str(ROOT/'hardware/exports')}):
            assert sim.main() == 1  # fake failing scenario remains failing
        assert calls == [root]
        assert runs == [(root/'different/model.xml', {'video': root/'scenarios/stand.mp4'})]
        summary = json.loads((root/'scenarios/summary.json').read_text())
        assert summary['passed'] == 0 and summary['physical_test'] is False
        assert summary['model_files']['rig_manifest'] == 'different/rig/manifest.json'
        assert (root/'evidence/body/sim-v2.json').is_file()
        with pytest.raises(ValueError, match='fresh --out'):
            sim.simulate(None, v2=True)
        with patch.object(sys, 'argv', ['simulate', '--v2']), pytest.raises(SystemExit) as failure:
            sim.main()
        assert failure.value.code == 2


@pytest.mark.parametrize('bad', ['../historical/model.xml', '/outside/model.xml', 'missing/model.xml'])
def test_simulate_rejects_unsafe_or_missing_returned_candidate_files(tmp_path, bad):
    v2 = actual_v2_helpers(); calls=[]
    v2.build = candidate_builder(v2, calls, model=bad)
    scenarios = stub('software.simulation.scenarios', SCENARIOS={'stand': object()}, recoil_scenario=forbidden, run=forbidden)
    with module_doubles({'software.simulation.robot_v2': v2, 'software.simulation.scenarios': scenarios,
                         'software.simulation.model': stub('software.simulation.model', build=forbidden)}):
        sim = load('end_pack_invalid_simulate', 'tools/engineering/robot/simulate.py')
        if bad == 'missing/model.xml':
            wrapped=v2.build
            def without_model(out):
                info=wrapped(out); (Path(out)/bad).unlink(); return info
            v2.build=without_model
        with pytest.raises(ValueError, match='candidate'):
            sim.simulate(None, v2=True, out=tmp_path/'candidate')


def test_actual_wheel_curb_cli_uses_fresh_per_model_output(tmp_path):
    v2=actual_v2_helpers(); calls=[]; runs=[]
    v2.build=candidate_builder(v2,calls)
    scenarios=stub('software.simulation.scenarios', Scenario=lambda *a, **k: (a,k), curb=lambda x:x,
                   run=lambda xml, info, sc, **kw:(runs.append((xml,kw)) or fixture_result()))
    with module_doubles({'software.simulation.robot_v2':v2, 'software.simulation.scenarios':scenarios,
                         'software.simulation.controller':stub('software.simulation.controller',Command=lambda **kw:kw)}):
        wheel=load('end_pack_wheel_control','software/simulation/wheel_study.py')
        root=tmp_path/'study'
        with patch.object(wheel,'patch_rig',return_value=SimpleNamespace(WHEEL_R=.127)), patch.object(wheel,'_patch_cad',return_value=None):
            assert wheel.main(['curb','--out',str(root),'--wheels','hb10','--heights','25','--video']) == 0
        assert calls == [root/'models/hb10']
        assert runs == [(root/'models/hb10/different/model.xml',{'video':root/'results/curb_hb10_25.0.mp4'})]
        assert (root/'results/summary_curb.json').is_file()
        row=json.loads((root/'results/curb_hb10.json').read_text())
        assert row['heights']['25.0']['pass'] is False and row['physical_test'] is False
        with pytest.raises(ValueError,match='fresh --out'): wheel.curb(['hb10'],[25],.6)


def test_historical_pad_study_rejects_current_model_before_reads_or_subprocess(tmp_path):
    tree=ast.parse((ROOT/'hardware/cad/body/body_battery.py').read_text())
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAD' for t in n.targets))
    battery=stub('hardware.cad.body.body_battery',PAD=ast.literal_eval(assignment.value))
    with module_doubles({'hardware.cad.body.body_battery':battery,'mujoco':stub('mujoco',mj_step=forbidden),'numpy':stub('numpy'),
                         'software.simulation.scenarios':stub('software.simulation.scenarios')}):
        study=load('end_pack_old_pad_control','software/simulation/bay_pad_study.py')
        with patch('subprocess.run',side_effect=forbidden), patch.object(study,'BUILD',tmp_path/'missing-old-model'), \
             pytest.raises(ValueError,match='original immutable source/model'):
            study.depth()
        with pytest.raises(ValueError,match='original immutable source/model'): study.main()


def test_actual_manifest_writer_uses_cad_sensor_frames_not_battery_extent():
    v2=actual_v2_helpers(); shell=actual_sensor_source()
    tree=ast.parse((ROOT/'software/simulation/robot_v2.py').read_text())
    build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
    writer=next(n for n in build.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name)
                and n.value.func.value.id=='man' and n.value.func.attr=='update')
    code=compile(ast.Module(body=[writer],type_ignores=[]),'actual rig manifest writer','exec')
    def write(extent):
        scope={'man':{'turret':{}},'info':{'fivebar':{},'track_mm':434.1,'total_mass_kg':1,'mass_split_kg':{}},
               'wr':.127,'TOP':216.,'hl':[],'x_l':103.,'x_p':-40.,'top':400.,'table':[],'view':{'pan0_all':[]},'fwd':0.,
               'T':SimpleNamespace(mount_z=246.,G=SimpleNamespace(tilt_t=50.,barrel_x1=0.),point=lambda *a:(0,0,0)),
               'B':{'x':(-extent,extent)},'sensor_mounts':v2.sensor_mounts}
        exec(code,scope);return scope['man']['mounts']
    with module_doubles({'hardware.cad.body.body_shell':shell}):
        normal=write(292.775)
        assert normal == write(10000.)
        assert normal['camera_front'] == [192.6,0.,142.5]
        assert normal['camera_rear'] == [-192.6,0.,142.5]
        assert normal['eyes'] == [162.6,0.,182.]
        eye=shell.eyes_board(); camera=shell.d435(True)
        assert normal['eyes_board_front'] == [eye[1],(eye[2]+eye[3])/2,(eye[4]+eye[5])/2]
        assert normal['camera_front'] == [camera[1],0.,(camera[4]+camera[5])/2]
        assert normal['camera_front'][0] != 292.775+2  # retained original wrong-extent control
        shell.D435={**shell.D435,'z':(111.,139.),'stand_off':40.}
        shell.EYES={**shell.EYES,'y':7.,'z':177.}
        changed=write(20000.)
        assert changed['camera_front'] == [202.6,0.,125.]
        assert changed['eyes'] == [162.6,7.,177.]
