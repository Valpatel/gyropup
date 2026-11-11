"""Bounded numeric controls before native end-pack geometry is accepted.

No solids are constructed here. Actual CAD, collision, support and consumer
adoption retain separately reviewed native/browser evidence requirements.
"""
from __future__ import annotations

import hashlib
import ast
import json
import math
from pathlib import Path
import subprocess

import pytest

from hardware.cad.body import body_battery as battery

ROOT = Path(__file__).resolve().parents[3]
FRAME = {'belly_z': -93.04, 'body_x': (-160.0, 160.0), 'support_t': 3.175}


def test_default_is_dcb609_with_dated_nominal_and_unmeasured_interface():
    spec = battery.pack_profile()
    assert spec['profile'] == 'DCB609'
    assert [spec[k] for k in ('L', 'W', 'H')] == [137.0, 97.0, 91.0]
    assert spec['published_mass_g'] == 1450.0 and spec['mass_g'] == 1565.0
    assert spec['source'].endswith('.pdf#page=8')
    assert spec['envelope'] and not spec['interface_measured'] and not spec['physical_fit_verified']
    assert battery.SUPPORTED_OUTLINE_MM == (138.0, 97.0, 97.0)
    selected = battery.SELECTED_ADAPTER
    assert selected['asin'] == 'B0CDGR4Y8K'
    assert selected['mount_holes'] is None and selected['rail'] is None and selected['latch'] is None
    assert not selected['electrical_ratings_verified']


def test_independent_world_bounds_and_same_upward_removal_on_both_ends():
    g = battery.end_pack_geometry(**FRAME)
    assert g['packs']['front'] == pytest.approx((195.775, 286.775, -48.5, 48.5, -87.04, 49.96))
    assert g['packs']['rear'] == pytest.approx((-286.775, -195.775, -48.5, 48.5, -87.04, 49.96))
    assert g['clearance_packs']['front'] == pytest.approx((195.775, 292.775, -48.5, 48.5, -88.04, 49.96))
    assert g['removal_offset_mm'] == (0.0, 0.0, 188.0)
    assert g['insertion_direction'] == (0.0, 0.0, -1.0)
    for end, inward in [('front', -1.0), ('rear', 1.0)]:
        m = g['transforms'][end]
        assert (m[0], m[4], m[8]) == (0.0, 0.0, 1.0)  # common local rail direction -> up
        assert (m[2], m[6], m[10]) == (inward, 0.0, 0.0)
        det = (m[0] * (m[5]*m[10]-m[6]*m[9]) -
               m[1] * (m[4]*m[10]-m[6]*m[8]) + m[2] * (m[4]*m[9]-m[5]*m[8]))
        assert det == 1.0  # no reflected manufacturer's interface
        b, removal, adapter = g['clearance_packs'][end], g['removal_volumes'][end], g['adapters'][end]
        assert b[4] == pytest.approx(FRAME['belly_z'] + 5.0)
        assert removal[:5] == b[:5] and removal[5] == pytest.approx(b[5] + 188.0)
        assert b[4] + 188.0 - adapter[5] == pytest.approx(50.0)
    assert g['packs']['front'][0] > 162.6 and g['packs']['rear'][1] < -162.6


def test_smaller_envelope_keeps_adapter_and_full_rigid_datum():
    large = battery.end_pack_geometry(**FRAME)
    smaller = battery.end_pack_geometry('DCB606', **FRAME)
    custom = battery.end_pack_geometry({'L': 110, 'W': 80, 'H': 65, 'mass_g': 850}, **FRAME)
    for g in (smaller, custom):
        assert g['transforms'] == large['transforms']
        assert g['adapters'] == large['adapters']
        assert g['clearance_packs'] == large['clearance_packs']
        assert g['removal_volumes'] == large['removal_volumes']
        for end in ('front', 'rear'):
            assert g['packs'][end][4] > large['packs'][end][4]
        assert not g['profile']['physical_fit_verified']
    # Returned dictionaries cannot change subsequent selections.
    smaller['profile']['L'] = 999
    assert battery.pack_profile('DCB606')['L'] == 124.0


@pytest.mark.parametrize('field', ['L', 'W', 'H', 'mass_g'])
@pytest.mark.parametrize('bad', [0, -1, math.nan, math.inf, -math.inf, True, '97', 10**400])
def test_nonphysical_or_nonfinite_variant_is_rejected(field, bad):
    custom = {'L': 124, 'W': 84, 'H': 91, 'mass_g': 1000}
    custom[field] = bad
    with pytest.raises(ValueError, match='finite and positive'):
        battery.end_pack_geometry(custom, **FRAME)


@pytest.mark.parametrize('field,oversize', [('L', 138.01), ('W', 97.01), ('H', 97.01)])
def test_oversize_needs_new_clearance_work(field, oversize):
    custom = {'L': 124, 'W': 84, 'H': 91, 'mass_g': 1000, field: oversize}
    with pytest.raises(ValueError, match='exceeds the supported'):
        battery.end_pack_geometry(custom, **FRAME)


@pytest.mark.parametrize('change', [{'belly_z': math.nan}, {'body_x': (160, -160)},
                                  {'body_x': (0, math.inf)}, {'support_t': 0}, {'support_t': True}, {'belly_z': 10**400}])
def test_invalid_frame_cannot_produce_placement(change):
    with pytest.raises(ValueError, match='frame needs finite'):
        battery.end_pack_geometry(**(FRAME | change))


@pytest.mark.parametrize('profile', ['unknown', {}, {'L': 100, 'W': 80, 'H': 80},
    {'L': 100, 'W': 80, 'H': 80, 'mass_g': 900, 'rail_scale': .8},
    {'L': 100, 'W': 80, 'H': 80, 'mass_g': 900, 'name': ''},
    {'L': 100, 'W': 80, 'H': 80, 'mass_g': 900, 'source': None}])
def test_missing_or_invented_custom_specification_is_rejected(profile):
    with pytest.raises(ValueError):
        battery.end_pack_geometry(profile, **FRAME)


def test_printed_leg_source_and_manufacturing_originals_remain_exact():
    baseline = json.loads((ROOT / '.agents/plans/end-packs/baseline.json').read_text())
    for file, expected in baseline['protected_leg_sources_sha256'].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == expected, file
    for path, expected in [('hardware/cad/legs', baseline['main_leg_cad_tree']),
                           ('hardware/exports/leg', baseline['main_leg_exports_tree'])]:
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD:' + path], cwd=ROOT, text=True).strip() == expected
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all', '--', path], cwd=ROOT, text=True)
    # This source-only guard does not substitute for the fresh collection's 80 mesh comparisons.
    assert len(baseline['collection261_leg_mesh_sha256']) == 80


def test_rigid_end_feet_do_not_inherit_the_old_pad_law():
    assert battery.PAD['lowest_leg_mm'] == 185.0 and battery.PAD['wheel_r'] == 127.0
    assert battery.END_FOOT['sit_leg_mm'] == 101.5
    assert not battery.END_FOOT['compliance_qualified'] and battery.END_FOOT['force_curve'] is None
    g = battery.end_pack_geometry(**FRAME)
    g.update(foot_bottom_z=-228.5, holder_half_y=54.5, base_bottom_z=-96.215)
    for end in ('front', 'rear'):
        boxes = battery.foot_collision_boxes(end, g)
        assert len(boxes) == 4 and min(b[4] for b in boxes) == -228.5
        assert all(b[2] >= -54.5 and b[3] <= 54.5 for b in boxes)
    assert 185.0 + 127.0 - 228.5 == 83.5
    assert 300.0 + 127.0 - 228.5 == 198.5
    assert 185.0 + 127.0 + FRAME['belly_z'] > 218.0  # centre clearance differs from localized feet


def test_archived_rig_and_pad_reports_are_not_replaced_by_current_geometry():
    protected = json.loads((ROOT / '.agents/plans/end-packs/history-protection.json').read_text())
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD:hardware/exports/sim/v2'], cwd=ROOT, text=True).strip() == protected['recorded_sim_tree']
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all', '--', 'hardware/exports/sim/v2'], cwd=ROOT, text=True)
    for file, expected in protected['historical_pad_reports_sha256'].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == expected, file


def test_new_physics_output_cannot_overwrite_the_recorded_rig(tmp_path):
    # Execute the actual filesystem guard without importing native physics/CAD.
    path = ROOT / 'software/simulation/robot_v2.py'
    tree = ast.parse(path.read_text())
    guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_configure_output')
    scope = {'Path': Path, 'R': ROOT}
    exec(compile(ast.Module(body=[guard], type_ignores=[]), str(path), 'exec'), scope)
    for bad in (None, ROOT/'new-physics', tmp_path):
        with pytest.raises(ValueError):
            scope['_configure_output'](bad)
    fresh = tmp_path/'fresh-candidate'
    scope['_configure_output'](fresh)
    assert fresh.is_dir()
    assert scope['OUT_BUILD'] == fresh/'build' and scope['OUT_RIG'] == fresh/'rig'
    with pytest.raises(ValueError):
        scope['_configure_output'](fresh)
