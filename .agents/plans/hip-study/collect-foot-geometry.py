"""One bounded source geometry/interface collection; no FEA, exports adoption or qualification."""
from pathlib import Path
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import signal
import stat
import subprocess


def load(path):
    spec = importlib.util.spec_from_file_location('foot_collection_lifecycle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_input(path):
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError('Manufacturer input must be a regular owned staged file')
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size, 'mode': stat.S_IMODE(mode)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--head', required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--motor-step', type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    out = Path(os.environ['FLEET_RUN_OUT']).resolve()
    assert out.is_dir() and not out.is_relative_to(root) and out.stat().st_uid == os.getuid()
    life = load(root / '.agents/plans/hip-study/collect-step-topology.py')
    life.ROOT, life.OUT = root, out
    life.processes_quiescent = True
    result = {'source': args.head, 'status': 'FAILED', 'adoption_approved': False, 'phases': {},
              'scope': 'Finished geometry/interface/model-clearance screen only; no FEA or physical qualification'}
    life.results = result
    assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt('received signal ' + str(signum))))
    before = hw = runtime_before = runtime = private_before = failed_before = failed_source = None
    diagnostic = out / 'geometry'
    observations = []
    try:
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == args.head
        assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
        assert subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip() == 'https://github.com/Valpatel/gyropup.git'
        assert not any(name.startswith('GYROPUP_') for name in os.environ)
        config_path = root / '.agents/plans/hip-study/foot-geometry-inputs.json'
        config = json.loads(config_path.read_text())
        contract_path = root / '.agents/plans/leg-control/e1-runtime-contract.json'
        assert life.sha(contract_path) == config['runtime_contract_sha256']
        contract = json.loads(contract_path.read_text())
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD:hardware'], text=True).strip() == config['hardware_tree']
        assert len(config['cad_sources']) == 94
        for name, value in {**config['cad_sources'], **config['study_inputs'], **config['execution_sources']}.items():
            assert life.sha(root / name) == value, name
            assert hashlib.sha256(subprocess.check_output(['git', 'show', args.head + ':' + name])).hexdigest() == value
        assert not ('fault_diagnostic' in config and 'rejoin_diagnostic' in config)
        failed = config.get('rejoin_diagnostic', config.get('fault_diagnostic'))
        if failed is not None:
            if 'rejoin_diagnostic' in config:
                assert failed['run_name'] == '20261107-hip-foot-geometry-refine-80e49685-ready'
                assert failed['input_directory'] == '.agents/plans/hip-study/failed-rejoin'
            else:
                assert failed['run_name'] == '20261107-hip-foot-geometry-local-c90caf86'
                assert failed['input_directory'] == '.agents/plans/hip-study/failed-local-foot'
            failed_source = root / failed['input_directory']
            def failed_snapshot():
                return {name: private_input(failed_source / name) for name in failed['inputs']}
            failed_before = failed_snapshot()
            assert {name: row['sha256'] for name, row in failed_before.items()} == failed['inputs']
            life.save('failed-inputs-before.json', failed_before)
        private_before = private_input(args.motor_step)
        assert private_before['sha256'] == config['motor_step_sha256']
        life.save('private-input-before.json', private_before)
        runtime = json.loads(args.runtime.read_text())
        before = life.tracked(root); life.save('project-before.json', before)
        hw = life.inventory(root / 'hardware'); life.save('hardware-before.json', hw)
        runtime_before = life.runtime_snapshot(runtime); life.save('runtime-before.json', runtime_before)
        assert hashlib.sha256(json.dumps(runtime_before, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == config['retained_runtime_snapshot_sha256']
        assert runtime_before['toolkit_head'] == contract['toolkit_revision'] and not runtime_before['toolkit_status'].strip()
        assert runtime_before['toolkit_python'] == contract['toolkit_python']
        assert runtime_before['libraries'] == contract['mapped_libraries']
        assert set(config['module_inputs']) == {'cadquery', 'gmsh'}
        for declared in config['module_inputs'].values():
            row = runtime_before['venv'][declared['venv_path']]
            assert row['sha256'] == declared['sha256']
            assert ('file-symlink' if 'link' in row else 'regular') == declared['kind']
            if 'link' in row:
                assert hashlib.sha256(row['link'].encode()).hexdigest() == declared['link_target_sha256']
        native_env = dict(os.environ)
        for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS'):
            native_env.pop(name, None)
        native_env.update(LD_PRELOAD=':'.join(runtime['libraries'][n] for n in ('libcrypto.so.3', 'libssl.so.3')),
                          PYTHONPATH=str(root) + os.pathsep + str(Path(runtime['toolkit']) / 'src'),
                          PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', MPLBACKEND='Agg',
                          MPLCONFIGDIR=str(out / 'matplotlib-cache'), OMP_NUM_THREADS='1',
                          OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_MAX_THREADS='1')
        os.environ.clear(); os.environ.update(native_env)
        diagnostic.mkdir(mode=0o700)
        runner = root / '.agents/plans/hip-study/run-foot-case.py'
        prefix = ['prlimit', '--as=25769803776', '--cpu=2400:2410', '--',
                  str(Path(runtime['venv']) / 'bin/python'), '-B', str(runner), '--root', str(root),
                  '--runtime', str(args.runtime), '--contract', str(contract_path), '--config', str(config_path)]
        phases = [
            ('baseline', ['--geometry-only', '--out', str(diagnostic / 'baseline'), '--params',
                          str(root / '.agents/plans/hip-study/retained-foot-baseline.params.json')]),
            ('candidate', ['--geometry-only', '--out', str(diagnostic / 'candidate')]),
            ('comparison', ['--compare-geometry', str(diagnostic / 'baseline'), str(diagnostic / 'candidate'),
                            '--out', str(diagnostic / 'comparison'), '--motor-step', str(args.motor_step)])]
        if 'rejoin_diagnostic' in config:
            phases = [('rejoin-diagnostic', ['--diagnose-rejoin', str(failed_source),
                                            '--out', str(diagnostic / 'rejoin-diagnostic')])]
        elif failed_source is not None:
            phases = [('fault-diagnostic', ['--diagnose-foot', str(failed_source),
                                           '--out', str(diagnostic / 'fault-diagnostic')])]
        for name, tail in phases:
            report = diagnostic / (name + '-runtime.json')
            life.phase(name, [*prefix, '--report', str(report), '--', *tail], timeout=120 if 'rejoin_diagnostic' in config else 60 if failed_source is not None else 600)
            observed = json.loads(report.read_text())
            assert observed['status'] == 'RETURNED_GEOMETRY_ONLY' and not observed.get('final_errors')
            for identity in (observed['before'], observed['after']):
                assert set(identity['module_origins']) == set(config['module_inputs'])
                for module, row in identity['module_origins'].items():
                    declared = config['module_inputs'][module]
                    assert row['path'] == declared['venv_path'] and row['kind'] == declared['kind']
                    assert row['resolved_path_sha256'] == declared['resolved_path_sha256']
                    assert runtime_before['venv'][row['path']]['sha256'] == row['sha256']
                for path, value in identity['mapped_venv_libraries'].items():
                    assert runtime_before['venv'][path]['sha256'] == value
        if failed_source is not None:
            rejoin = 'rejoin_diagnostic' in config
            label = 'rejoin-diagnostic' if rejoin else 'fault-diagnostic'
            filename = 'rejoin-diagnostic.json' if rejoin else 'fillet-diagnostic.json'
            expected_status = 'COLLECTED_REJOIN_DIAGNOSTIC_ONLY' if rejoin else 'COLLECTED_KERNEL_DIAGNOSTIC_ONLY'
            report = json.loads((diagnostic / label / filename).read_text())
            assert report['status'] == expected_status
            assert report['input_sha256'] == failed['inputs'] and report['source_sha256'] == config['study_inputs']
            if not rejoin:
                assert report['radius_mm'] == 3.5
            assert report['fea_run'] is False and report['physical_qualification'] is False
            result.update(status=expected_status, diagnostic=report)
        else:
            for name in ('baseline', 'candidate'):
                row = json.loads((diagnostic / name / 'geometry.json').read_text())
                assert row['status'] == 'BUILT_ONLY' and row['inputs_sha256'] == config['study_inputs']
            report = json.loads((diagnostic / 'comparison/geometry-comparison.json').read_text())
            assert report['status'] == 'PASS_GEOMETRY_INTERFACE_SCREEN_ONLY'
            assert report['inputs_sha256'] == config['study_inputs'] and report['manufacturer_solids'] == 43
            assert report['actual_motor_step_sha256'] == config['motor_step_sha256']
            assert set(report['actual_finished_shape_negative_controls']) == {
                'connected_outside_foot', 'removed_retained_material', 'filled_actual_pilot'}
            if not rejoin:
                assert report['radius_mm'] == 3.5
            assert report['fea_run'] is False and report['physical_qualification'] is False
            assert sum(row['bytes'] for row in life.inventory(diagnostic).values()) <= 512 * 1024**2
            result.update(status='PASS_GEOMETRY_INTERFACE_SCREEN_ONLY', comparison=report)
    except BaseException as error:
        result['original_error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        if before is not None:
            observations.append(('project-after.json', lambda: life.tracked(root), before))
        if hw is not None:
            observations.append(('hardware-after.json', lambda: life.inventory(root / 'hardware'), hw))
        if runtime_before is not None:
            observations.append(('runtime-after.json', lambda: life.runtime_snapshot(runtime), runtime_before))
        if failed_before is not None:
            observations.append(('failed-inputs-after.json', failed_snapshot, failed_before))
        if private_before is not None:
            observations.append(('private-input-after.json', lambda: private_input(args.motor_step), private_before))
        observations.append(('project-status-after.json', lambda: subprocess.check_output(
            ['git', 'status', '--porcelain'], text=True), ''))
        def seal():
            if diagnostic.exists():
                life.archive('geometry', diagnostic)
        life.final_observations(result, observations, seal, life.processes_quiescent)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
