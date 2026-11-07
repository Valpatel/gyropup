"""Shared bits for the turret physics modules: loading the CAD (cad/turret.py) beside the game module (sim/turret.py),
which share a file name, and loading the program agent's feed/launch modules by path."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

R = (Path(__file__).resolve().parents[2])


LIMITS_JSON = R / 'hardware' / 'exports' / 'turret' / 'limits.json'


def tilt_stops_deg(path: Path = LIMITS_JSON) -> tuple:
    """Return the CAD hard stops in degrees, with positive tilt pointing the muzzle up."""
    limits = json.loads(Path(path).read_text())['tilt_deg']
    return float(limits['min']), float(limits['max'])


def cad_turret():
    """Load this checkout's CAD turret without colliding with the game module."""
    module = importlib.import_module('hardware.cad.turret.turret')
    if not hasattr(module, 'Geo'):
        raise ImportError(f'{module.__file__} is not the CAD turret module')
    return module


def game_turret():
    """Load the game-level scene module under its actual software namespace."""
    return importlib.import_module('software.simulation.turret')


def sim_module(name):
    """Load a sibling simulation module through the selected checkout package."""
    return importlib.import_module('software.simulation.' + name)


def turret_for_physics(tu=None):
    """The CAD turret at the convention cad/turret_motion.py uses: mount face at z = 0 of the T frame."""
    tu = tu or cad_turret()
    return tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
