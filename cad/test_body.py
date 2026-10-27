"""Checks on the body's numbers and parts (milestone M5).

    .venv/bin/python -m pytest cad/test_body.py -q          # or: .venv/bin/python cad/test_body.py

T1: the three interfaces the body takes from elsewhere match their sources (the hip frame's six inserts measured from
cad/fivebar.py's solid, the turret's TM pattern from cad/turret.py, the J501's holes from the j501-agx project), and
the track and Y_OFF print from the one constant. T2 adds the frame's own checks when exports/body/body.json exists.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))

import body_params as bp  # noqa: E402


def test_frame_mounts_from_the_frame():
    import fivebar as fb
    import gmi
    m = bp.frame_mounts()
    holes = m['holes']
    assert len(holes) == 6, holes
    assert abs(m['pilot_d'] - gmi.FAST['M5']['insert_pilot']) < 1e-9
    assert abs(m['centre_plane_y'] - fb.Y['centre_plane']) < 1e-9
    # two rows, symmetric fore and aft and top to bottom (the frame mirrors about x = 0 and z = 0)
    pts = {(round(x, 2), round(z, 2)) for x, z in holes}
    assert pts == {(round(-x, 2), round(z, 2)) for x, z in holes}
    assert pts == {(round(x, 2), round(-z, 2)) for x, z in holes}
    # each hole lies in a flat face of the centre plane, with room for the screw's head and washer around it
    for x, z in holes:
        assert any(f[0] <= x - 5 and x + 5 <= f[1] and f[2] <= z - 5 and z + 5 <= f[3] for f in m['face']), (x, z)
    assert m['depth'] >= 10.0, m['depth']
    # when the leg publishes its interface (fivebar.frame_mounts), the solid must agree with it
    assert sorted(tuple(round(v, 2) for v in h) for h in m['measured_holes']) == sorted(tuple(round(v, 2) for v in h) for h in holes)
    # the frame screw engages the insert fully and does not bottom out
    t = bp.STOCK[bp.CHEEK]['t']
    engage = bp.FRAME_SCREW['length'] - t
    assert 7.9 <= engage <= m['depth'] - 1.0, (engage, m['depth'])


def test_tm_pattern_is_the_turrets():
    import turret as tu
    t = bp.tm()
    assert t['bolts'] == [tuple(p) for p in tu.TM_BOLTS]
    assert t['dowels'] == [tuple(p) for p in tu.TM_DOWELS]
    assert t['hole_d'] == tu.TM_HOLE
    assert abs(t['pan_x'] - (bp.lidar()['x'] - bp.LIDAR_TO_PAN)) < 1e-9


def test_j501_from_its_project():
    P = json.loads((bp.J501_DIR / 'cad' / 'parameters.json').read_text())
    j = bp.j501()
    assert j['holes'] == [tuple(h) for h in P['pcb']['mount_holes']]
    assert j['module_holes'] == [tuple(h) for h in P['pcb']['module_mount_centers']]
    assert j['cooler'] == tuple(P['cooler']['size'])
    # the module tie-down pattern is the 92 x 79 rectangle the plan names
    xs = sorted({h[0] for h in j['module_holes']})
    ys = sorted({h[1] for h in j['module_holes']})
    assert (xs[-1] - xs[0], ys[-1] - ys[0]) == (92, 79)


def test_lidar_from_the_catalogue():
    lid = bp.lidar()
    (x0, y0), (x1, y1) = lid['pins']
    assert abs((x1 - x0) - 88.9) < 1e-6 and y0 == y1 == 0.0
    assert abs((x0 + x1) / 2 - lid['x']) < 1e-6
    assert lid['x'] + lid['d'] / 2 <= bp.BODY_X[1] + 1e-6              # never past the deck's front edge
    assert bp.BODY_X[1] - (lid['x'] + lid['d'] / 2) < 6.0               # and no further back than the bend rule needs
    st = bp.STOCK[bp.DECK]
    bend_c = bp.BODY_X[1] - st['ossb'] + st['ba'] / 2
    assert bend_c - (x1 + lid['pin_hole_d'] / 2) >= st['half_die'] - 0.05


def test_sendcutsend_bend_numbers():
    for key, s in bp.STOCK.items():
        if s['bend']:
            assert abs(s['bd'] / bp.IN - s['bd_in']) < 0.003, (key, s['bd'] / bp.IN)


def test_spine_top_rules():
    s = bp.STOCK[bp.CHEEK]
    m = bp.frame_mounts()
    zt = bp.z_spine_top()
    z_hole_edge = max(z for _, z in m['holes']) + 5.5 / 2
    flat_end = zt - s['ossb']                                  # where the cheek's flat ends below the bend
    assert (flat_end - z_hole_edge) + s['ba'] / 2 >= s['half_die'] - 1e-6
    z_boss = max(f[3] for f in m['face'])
    assert zt - s['t'] >= z_boss + 2.0                          # the flange's inner face clears the insert bosses
    # the C-channel is bendable: base at least twice the flange
    assert 2 * zt >= bp.SCS_RULES['channel_base_to_flange'] * bp.CHEEK_FLANGE
    assert bp.CHEEK_FLANGE >= s['min_flange']


def test_track_and_y_off_print():
    s = bp.summary()
    print('\nbody numbers:', json.dumps(s))
    assert abs(s['track_mm'] - 2 * (s['y_off_mm'] + s['wheel_y_module_mm'])) < 0.01
    assert abs(bp.to_robot((0.0, bp._fivebar().Y['centre_plane'], 0.0))[1] - bp.SPINE_W / 2) < 1e-9
    assert abs(bp.to_robot((0.0, bp._fivebar().Y['centre_plane'], 0.0), 'right')[1] + bp.SPINE_W / 2) < 1e-9


# ------------------------------------------------------------------------------------------- T2: the frame's parts

BODY_JSON = R / 'exports' / 'body' / 'body.json'


def _body():
    if not BODY_JSON.exists():
        import pytest
        pytest.skip('exports/body/body.json not built yet (cad/build_body.py)')
    return json.loads(BODY_JSON.read_text())


def test_cheek_holes_on_the_frames_inserts():
    b = _body()
    for side in ('left', 'right'):
        got = sorted(tuple(p) for p in b['interface']['cheek_holes'][side])
        want = sorted(tuple(bp.to_robot((x, bp.frame_mounts()['centre_plane_y'], z), side)) for x, z in bp.frame_mounts()['holes'])
        assert len(got) == len(want) and all(math.dist(g, w) < 0.02 for g, w in zip(got, want)), (side, got, want)


def test_sheet_rules():
    b = _body()
    bad = {n: p['rule_violations'] for n, p in b['sheet'].items() if p['rule_violations']}
    assert not bad, bad


def test_no_clash_with_the_legs():
    b = _body()
    c = b.get('clash_sweep')
    if c is None:
        import pytest
        pytest.skip('the clash sweep was not run (cad/build_body.py --no-clash)')
    assert c['clashes'] == [], c['clashes'][:10]


def test_printed_parts_fit_the_bed():
    b = _body()
    assert b['print']['too_big'] == []


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q', '-s']))
