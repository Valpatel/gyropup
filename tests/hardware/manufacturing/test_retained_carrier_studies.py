"""Run the unchanged dated study suites with verified captured data inputs."""
import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.evidence.manufacturing.retained_fit_history import captured_inputs
from tools.evidence.manufacturing.retained_study_inputs import bound_bytes, copy_bound_inputs, study_inputs

INVENTORY = Path('docs/research/insert-joints')
# Public inputs and generated reports match the captured CAD source snapshot.
INVENTORY_EXTRA = {
    'docs/legs/leg-rig-assembly.md': '757af8eead8cf476d6bdf2c912f64654f212c56bd9fa35545b03bfaafe4f9c0a',
    'hardware/exports/body/fea/summary.json': '0bb53d57463cbeb4f8dae9cc27719496b0dc758e0f19f72087c8bd1427e5ba8d',
    'hardware/exports/body/integrity.json': 'a994b37b28472c888afe6b5e84289dc235eeed8d51816c045cba06ed63fd6c82',
    'hardware/exports/body/leg-loads.json': '21b576f2c5a9224a14b233203343cdce59603a87b239ee4b0c2bdffa1156e768',
    'hardware/exports/body/print-plan.json': '268f3210ea0ba5fd31d4d73e5c73bdded8d3f00c1ac43ddb66d1f0b8042b3e8d',
    'hardware/exports/body/shell/print-plan.json': 'c949ece7f07e59e5bf5faa09b93a21d793fc5339973f72e31c0f5d6103930b79',
    'hardware/exports/leg/fea/summary.json': '1488c5f62b90fd44162140ba1cb7adf8f52135a727cd37b6f08f4d2794000a39',
    'hardware/exports/turret/fea/summary.json': '49ac98a970aa06d0160021415cd78a41fdcf3a74cff09f432257271bdb271b48',
    'hardware/exports/turret/mount.json': 'd0c3bda29655cde5e108e60d64d4e1e43172aa1e57fdfdbef7543811c0066ab0',
}
INVENTORY_OWNER = {
    'inventory.py': 'ac0c4c875e466224267c35e5d1a0ee52905858094d3f7ed097a023d7f75d0ee9',
    'test_inventory.py': '5d504147751a8241692db4f850c72dba3be42d44365e0e583e2466a2f65ce6d0',
    'joints.json': '407f0fc4f7b295042ab28bdab8fa6b29f1d1fcdfd0173405a1b4a635c28262cc',
    'joints.md': '09cf67443dba0165e26536726850e68a401e9745f62dd17d6f17df173909770f',
}


def load_tests(relative):
    # Only the currently checked-in test and checker code execute. The captured
    # directory is an input root and never enters the Python import path.
    path = ROOT / relative
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('dated_study_suite', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_suite(module):
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.testsRun > 0 and result.wasSuccessful() and not result.skipped


def carrier_fit():
    with study_inputs('carrier-insert-fit') as inputs:
        module = load_tests('docs/research/carrier-insert-fit/test_guards.py')
        with unittest.TestCase().assertRaisesRegex(ValueError, 'CAD/config/catalog inputs changed'):
            module.check()
        report = module.check(inputs)
        if report['physical_fit_verified'] is not False or report['release_ready'] is not False:
            raise ValueError('Dated insert specimen qualification changed')
        module.ROOT = inputs
        return run_suite(module)


def insert_inventory():
    for name, digest in INVENTORY_OWNER.items():
        bound_bytes(INVENTORY / name, digest)
    module = load_tests(INVENTORY / 'test_inventory.py')
    with unittest.TestCase().assertRaisesRegex(module.inv.Stale, r'body_battery\.py: no match for.*RAIL_W'):
        module.generate()
    with captured_inputs() as inputs:
        copy_bound_inputs(inputs, INVENTORY_EXTRA)
        module.inv.ROOT = inputs
        return run_suite(module)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', choices=('carrier-insert-fit', 'insert-inventory'))
    args = parser.parse_args()
    passed = carrier_fit() if args.study == 'carrier-insert-fit' else insert_inventory()
    sys.exit(0 if passed else 1)
