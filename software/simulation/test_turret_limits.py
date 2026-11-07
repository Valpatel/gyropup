"""The turret sims take their tilt range from the hard stops, and their aiming works above level (#201, D77).

    .venv/bin/python -m pytest software/simulation/test_turret_limits.py -q

These tests check the committed hard-stop limits and independent raised/level-stop cases, preserving positive-elevation
solver coverage without claiming measured fit, feed performance or hardware qualification.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))
import software.simulation.turret_common as tc  # noqa: E402

LIMITS = json.loads((R / 'hardware' / 'exports' / 'turret' / 'limits.json').read_text())


def game():
    pytest.importorskip('mujoco')
    return tc.game_turret()


def flight():
    pytest.importorskip('numpy')
    return tc.sim_module('turret_flight')


def test_limits_file_is_the_cads():
    pytest.importorskip('cadquery')
    spec = importlib.util.spec_from_file_location('turret_limits', R / 'hardware' / 'cad' / 'turret' / 'turret_limits.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert (R / 'hardware' / 'exports' / 'turret' / 'limits.json').read_text() == m.text(), 'run hardware/cad/turret/turret_limits.py'


def test_every_sim_reads_the_same_stops():
    lo, hi = LIMITS['tilt_deg']['min'], LIMITS['tilt_deg']['max']
    assert lo < hi
    assert tc.tilt_stops_deg() == (lo, hi)
    g = game()
    assert (g.TILT_MIN_DEG, g.TILT_MAX_DEG) == (lo, hi)


def test_no_never_above_horizontal_rule_left_in_the_aiming():
    """The old rule lived in the aiming code as "elev <= 0" / "hi=0.0"; none of it may come back."""
    for f in ('software/simulation/turret.py', 'software/simulation/turret_flight.py', 'software/simulation/turret_e2e.py', 'software/site/designer/turret3d.js', 'software/site/designer/sim.js'):
        text = (R / f).read_text().lower()
        assert 'never above horizontal' not in text and 'never above level' not in text, f
    assert 'elev <= 0.0' not in (R / 'software/simulation/turret.py').read_text()
    assert 'MAX_TILT_UP' not in (R / 'software/site/designer/turret3d.js').read_text()


def test_joint_clamp_is_the_stops_not_the_world():
    g = game()
    # a target 10 deg up on a level body: inside a +20 deg stop, clipped by a 0 deg stop
    up = math.radians(10.0)
    t, inside = g.joint_tilt(up, 0.0, (-25.0, 20.0))
    assert inside and t == pytest.approx(-up)
    t, inside = g.joint_tilt(up, 0.0, (-25.0, 0.0))
    assert not inside and t == pytest.approx(0.0)
    # the stop is in the joint: a body pitched 5 deg nose up (pitch -5 deg) reaches 10 deg up with only 5 deg of joint
    t, inside = g.joint_tilt(up, math.radians(-5.0), (-25.0, 6.0))
    assert inside and t == pytest.approx(-math.radians(5.0))
    # the lower stop still holds
    t, inside = g.joint_tilt(math.radians(-40.0), 0.0, (-25.0, 20.0))
    assert not inside and t == pytest.approx(math.radians(25.0))


def test_game_solver_finds_upward_shots():
    g = game()
    el = g.elevation_for(6.0, 0.8)                 # 0.8 m above the muzzle at 6 m: an upward shot
    assert el is not None and el > 0.0
    assert g.fly(el, 6.0) == pytest.approx(0.8, abs=0.005)
    el = g.elevation_for(4.0, -0.25)               # below the muzzle: still the old downward solution
    assert el is not None and g.fly(el, 4.0) == pytest.approx(-0.25, abs=0.005)


def test_flight_solver_aims_up_within_a_raised_stop_and_not_past_it():
    tf, tb = flight(), tc.sim_module('turret_ball')
    tl = tc.sim_module('turret_launch')
    spec = tb.nominal()
    v0 = 55 * tl.FPS
    h0 = 0.55
    # a target 0.4 m above the muzzle at 4 m needs the barrel up
    el = tf.elevation_for(v0, spec, 4, h0 + 0.4, h0=h0, hi=math.radians(20.0))
    assert el is not None and el > 0.0
    assert tf.drop_at(v0, spec, 4, el, h0) == pytest.approx(h0 + 0.4, abs=0.01)
    # with the stop at level it is out of reach (None), as before
    assert tf.elevation_for(v0, spec, 4, h0 + 0.4, h0=h0, hi=0.0) is None
    # the default range is the stops' own
    lo, hi = (math.radians(a) for a in tc.tilt_stops_deg())
    el = tf.elevation_for(v0, spec, 2, 0.30, h0=h0)
    assert el is not None and lo <= el <= hi


def test_firing_limit_is_one_number_inside_the_stops():
    """D77: the barrel aims up to its stop; no shot above the feed's qualified elevation. One figure, from the feed study
    through limits.json, in the game sim and the firmware reference alike."""
    fire = LIMITS['fire_tilt_max_deg']
    assert LIMITS['tilt_deg']['min'] < 0.0 <= fire <= LIMITS['tilt_deg']['max']
    assert game().FIRE_TILT_MAX_DEG == fire
    feed = json.loads((R / 'hardware' / 'exports' / 'turret' / 'feed' / 'feed-elevated.json').read_text())
    assert min(feed['fire_tilt_max_deg'], LIMITS['tilt_deg']['max']) == fire
    cfg = (R / 'software' / 'firmware' / 'turret' / 'config.py').read_text()
    assert f'FIRE_TILT_MAX_DEG = {fire!r}' in cfg.replace('  ', ' ').replace('  ', ' ')


def test_limits_reader_requires_the_current_path_even_with_a_valid_legacy_copy(tmp_path, monkeypatch):
    """Current checkout identity and missing-current failure must survive a plausible old export."""
    assert Path(tc.__file__).resolve() == R / 'software/simulation/turret_common.py'
    assert tc.LIMITS_JSON == R / 'hardware/exports/turret/limits.json'
    assert tc.tilt_stops_deg.__defaults__ == (tc.LIMITS_JSON,)
    monkeypatch.chdir(tmp_path)
    assert tc.tilt_stops_deg() == (LIMITS['tilt_deg']['min'], LIMITS['tilt_deg']['max'])
    legacy = tmp_path / 'exports/turret/limits.json'
    current = tmp_path / 'hardware/exports/turret/limits.json'
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps(LIMITS))
    with pytest.raises(FileNotFoundError) as missing:
        tc.tilt_stops_deg(current)
    assert Path(missing.value.filename) == current
    current.parent.mkdir(parents=True)
    current.write_text(json.dumps(LIMITS))
    assert tc.tilt_stops_deg(current) == (LIMITS['tilt_deg']['min'], LIMITS['tilt_deg']['max'])


def test_actual_simulation_parser_requires_separate_firing_permission():
    """Execute the current parser body without importing MuJoCo or CAD."""
    import ast
    import copy
    tree = ast.parse((R / 'software/simulation/turret.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'read_stop_limits')
    scope = {'math': math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'actual-turret-limit-reader', 'exec'), scope)
    parse = scope['read_stop_limits']
    valid = {'tilt_deg': {'min': -25, 'max': 12}, 'fire_tilt_max_deg': 10}
    assert parse(valid) == (-25, 12, 10)
    missing = copy.deepcopy(valid)
    del missing['fire_tilt_max_deg']
    with pytest.raises(KeyError):
        parse(missing)
    for value in (float('nan'), float('inf'), -26, 13, '10', True):
        with pytest.raises(ValueError, match='Invalid turret firing limits'):
            parse({**valid, 'fire_tilt_max_deg': value})
    for stops in ({'min': 12, 'max': -25}, {'min': -25, 'max': float('inf')}):
        with pytest.raises(ValueError, match='Invalid turret firing limits'):
            parse({**valid, 'tilt_deg': stops})


def test_tilt_range_cli_derives_the_current_design_path(tmp_path):
    """Exercise the actual CLI argument expression before any CAD work; a legacy copy cannot select it."""
    import ast
    tree = ast.parse((R / 'hardware/cad/turret/turret_tilt_range.py').read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == 'tu' and n.func.attr == 'derive']
    assert len(calls) == 1
    argument = compile(ast.Expression(calls[0].args[0]), 'actual-tilt-range-design-input', 'eval')
    legacy = tmp_path / 'designs/default.json'
    current = tmp_path / 'hardware/designs/default.json'
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{}')
    selected = eval(argument, {'R': tmp_path})
    assert selected == current
    assert not selected.exists()
    current.parent.mkdir(parents=True)
    current.write_text('{}')
    assert selected.is_file()
    assert eval(argument, {'R': R}).is_file()
