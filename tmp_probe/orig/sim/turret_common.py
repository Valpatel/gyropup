"""Shared bits for the turret physics modules: loading the CAD (cad/turret.py) beside the game module (sim/turret.py),
which share a file name, and loading the program agent's feed/launch modules by path."""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def cad_turret():
    """cad/turret.py as a module, whatever else is on sys.path (sim/turret.py has the same name). Raises if the CAD
    is mid-edit and will not import; callers retry."""
    m = sys.modules.get('turret')
    if m is not None and hasattr(m, 'Geo'):
        return m
    if m is not None:
        del sys.modules['turret']
    cad = str(R / 'cad')
    while cad in sys.path:
        sys.path.remove(cad)
    sys.path.insert(0, cad)
    m = importlib.import_module('turret')
    if not hasattr(m, 'Geo'):
        raise ImportError(f'{m.__file__} is not the CAD turret module')
    return m


def game_turret():
    """sim/turret.py (the game-level scene bits: targets_xml, balls_xml, Target), under its own module name."""
    if 'game_turret' in sys.modules:
        return sys.modules['game_turret']
    spec = importlib.util.spec_from_file_location('game_turret', R / 'sim' / 'turret.py')
    m = importlib.util.module_from_spec(spec)
    sys.modules['game_turret'] = m
    spec.loader.exec_module(m)
    return m


def sim_module(name):
    """A module from sim/ by name (turret_feed, turret_launch, ...) with sim/ on the path but cad/ kept first."""
    sim = str(R / 'sim')
    if sim not in sys.path:
        sys.path.append(sim)
    return importlib.import_module(name)


def turret_for_physics(tu=None):
    """The CAD turret at the convention cad/turret_motion.py uses: mount face at z = 0 of the T frame."""
    tu = tu or cad_turret()
    return tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
