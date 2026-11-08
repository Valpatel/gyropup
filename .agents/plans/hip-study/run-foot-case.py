"""Run the existing geometry producer with same-process retained-runtime observations."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import runpy
import sys
import traceback


def load(path):
    spec = importlib.util.spec_from_file_location('foot_runtime_identity', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'runtime', 'contract', 'config', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('study_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if any(name.startswith('GYROPUP_') for name in os.environ):
        raise ValueError('Inherited product parameters before native geometry')
    root = args.root.resolve()
    runtime = json.loads(args.runtime.read_text())
    contract = json.loads(args.contract.read_text())
    config = json.loads(args.config.read_text())
    assert args.report.parent.is_dir() and not args.report.resolve().is_relative_to(root)
    sys.path[:0] = [str(root), str(Path(runtime['toolkit']) / 'src')]
    guard = load(root / '.agents/plans/hip-study/inspect-step-worker.py')
    record = {'pid': os.getpid(), 'scope': 'Geometry-only process; no FEA', 'status': 'FAILED'}
    primary = None

    def save():
        args.report.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')

    try:
        _, record['before'] = guard.runtime_identity(contract, runtime, config['module_inputs'])
        save()
        tail = args.study_args[1:] if args.study_args[:1] == ['--'] else args.study_args
        sys.argv = [str(root / 'tools/engineering/legs/hip-frame-study.py'), *tail]
        runpy.run_path(sys.argv[0], run_name='__main__')
        record['status'] = 'RETURNED_GEOMETRY_ONLY'
    except BaseException as error:
        primary = error
        record['original_error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        errors = []
        try:
            _, record['after'] = guard.runtime_identity(contract, runtime, config['module_inputs'])
        except BaseException as error:
            errors.append('Runtime-after: ' + type(error).__name__ + ': ' + str(error))
        if errors:
            record.update(status='FAILED', final_errors=errors)
        try:
            save()
        except BaseException as error:
            errors.append('Runtime report: ' + type(error).__name__ + ': ' + str(error))
            traceback.print_exc()
        if errors and primary is None:
            raise RuntimeError('; '.join(errors))


if __name__ == '__main__':
    main()
