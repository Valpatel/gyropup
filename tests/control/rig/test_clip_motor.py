"""Actual shared clipping logic, without loading CAD, a simulator or a device."""
import importlib.abc
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[3]


def controller_without_unused_dependencies():
    """Import the complete library; reject use of its unrelated VMC dependencies."""
    class Unused(types.ModuleType):
        def __getattr__(self, name):
            raise AssertionError(f'Clipping invoked unused dependency {self.__name__}.{name}')

    class NoNative(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in {'cadquery', 'OCP', 'vtk', 'mujoco'}:
                raise AssertionError(f'Native import is outside this control test: {fullname}')

    names = ['hardware', 'hardware.cad', 'hardware.cad.legs',
             'hardware.cad.legs.fivebar', 'numpy', '_gyropup_clipping_test']
    previous = {name: sys.modules.get(name) for name in names}
    previous_path = sys.path[:]
    finder = NoNative()
    sys.meta_path.insert(0, finder)
    try:
        for name in names[:3]:
            package = types.ModuleType(name)
            package.__path__ = []
            sys.modules[name] = package
            if '.' in name:
                parent, attr = name.rsplit('.', 1)
                setattr(sys.modules[parent], attr, package)
        for name in ['hardware.cad.legs.fivebar', 'numpy']:
            dependency = Unused(name)
            sys.modules[name] = dependency
            if '.' in name:
                parent, attr = name.rsplit('.', 1)
                setattr(sys.modules[parent], attr, dependency)
        spec = importlib.util.spec_from_file_location(names[-1], ROOT / 'software/simulation/leg_control.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.meta_path.remove(finder)
        sys.path[:] = previous_path
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


class MotorClipping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = controller_without_unused_dependencies()

    def test_nonfinite_requested_torque_cannot_become_a_motor_command(self):
        for tau in (math.nan, math.inf, -math.inf):
            for omega in (-21., -10.5, 0., 10.5, 21.):
                for cap in (None, 0., 60.):
                    with self.subTest(tau=tau, omega=omega, cap=cap):
                        value = self.controller.clip_motor(tau, omega, 120., 21., cap)
                        self.assertTrue(math.isfinite(value))
                        self.assertEqual(value, 0.)

    def test_finite_driving_braking_and_cap_semantics_are_retained(self):
        cases = [(100., 0., 60., 60.), (50., 10.5, None, 50.),
                 (100., 10.5, None, 60.), (-100., 10.5, None, -100.),
                 (100., -10.5, None, 100.), (-100., -10.5, None, -60.),
                 (100., 21., None, 0.), (-100., -21., None, 0.),
                 (100., 0., 0., 100.), (0., 21., 60., 0.)]
        for tau, omega, cap, expected in cases:
            with self.subTest(tau=tau, omega=omega, cap=cap):
                self.assertEqual(self.controller.clip_motor(tau, omega, 120., 21., cap), expected)


if __name__ == '__main__':
    unittest.main()
