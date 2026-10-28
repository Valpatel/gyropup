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
    # the frame screw engages at least 90 % of the 7.9 mm insert (7.1 mm, 1.4 d of M5 thread: the insert's grip in the
    # plastic, not the thread, sets the pull-out) and does not bottom out in the 11 mm pilot
    t = bp.STOCK[bp.CHEEK]['t']
    engage = bp.FRAME_SCREW['length'] - t
    assert 0.9 * 7.9 <= engage <= m['depth'] - 1.0, (engage, m['depth'])


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


def test_no_internal_clashes():
    b = _body()
    assert b['internal_clashes'] == [], b['internal_clashes']


# ------------------------------------------------------------------------------------------- T5, T8: parts list, wiring

def test_every_bought_line_has_a_price_and_a_backup():
    f = R / 'exports' / 'body' / 'bom.json'
    if not f.exists():
        import pytest
        pytest.skip('exports/body/bom.json not built yet (cad/body_bom.py)')
    bom = json.loads(f.read_text())
    bad = []
    for k, rows in bom.items():
        if not isinstance(rows, list) or k.startswith(('to_source', 'made_to_order', 'not_')):
            continue
        for r in rows:
            s = r.get('sellers') or []
            if len(s) < 2 or not s[0].get('url') or (s[0].get('price_usd') is None and r.get('price_usd_each') is None):
                bad.append((k, r.get('key')))
    for m in bom['made_to_order']:                      # each with SendCutSend's instant price, read on a date (D58)
        if not (m.get('step') and m.get('dxf') and m.get('backup') and m.get('price_usd_each') is not None and m.get('price_read_on')):
            bad.append(('made_to_order', m['key'], m.get('price_note')))
    assert not bad, bad


AMPACITY_A = {8: 85, 10: 55, 12: 41, 14: 32, 18: 16, 22: 7}       # silicone, bundled in free air (the BNTECHGO class, 200 C)


def test_every_fuse_protects_its_wire():
    """No fuse on a wire is larger than the wire carries (docs/body-electrical.md)."""
    import re
    w = json.loads((R / 'exports' / 'body' / 'wiring.json').read_text())
    bad = []
    for r in w['wires']:
        m = re.search(r'(\d+(?:\.\d+)?) A', r['fuse'] or '')
        if m and not r['fuse'].startswith('('):
            if float(m.group(1)) > AMPACITY_A[r['awg']]:
                bad.append((r['id'], r['fuse'], r['awg']))
    assert not bad, bad


def test_no_live_pins_on_the_body():
    """Every connector on the body's side of a lead that is live with the pack in is a socket (hazard 11, D58): the
    charge port, the 48 V branch leads (XT60H-F) and the 24 V and 12 V ones (XT30U-F); the devices' leads carry the
    pins. The pack's XT90-S is the one exception: its female is on the pack, the robot's male is dead with the pack out.
    The order buys the sockets the wire list needs."""
    import re
    w = json.loads((R / 'exports' / 'body' / 'wiring.json').read_text())
    bad = []
    for r in w['wires']:
        for field in ('from', 'to', 'termination'):
            for m in re.finditer(r'\b(XT\d+[A-Z]*)(?:-S)?[- ](M|F|male|female)\b', r[field]):
                if m.group(1).startswith('XT90'):
                    continue
                if m.group(2) in ('M', 'male'):
                    bad.append((r['id'], field, m.group(0)))
    assert not bad, bad
    ends = {r['id']: r['termination'] for r in w['wires']}
    assert all('XT60H-F' in ends[k] for k in ('W10', 'W11', 'W12', 'W13', 'W14', 'W15')), ends
    assert all('XT30U-F' in ends[k] for k in ('W21', 'W24')), ends
    f = R / 'exports' / 'body' / 'bom.json'
    if f.exists():
        bom = json.loads(f.read_text())
        qty = {r['key']: r['qty'] for k, rows in bom.items() if isinstance(rows, list) and not k.startswith(('not_', 'to_source', 'made_to'))
               for r in rows if isinstance(r, dict) and 'key' in r}
        sockets_60 = 1 + sum(1 for k in ('W10', 'W11', 'W12', 'W13', 'W14', 'W15') if 'XT60H-F' in ends[k])     # + the charge port
        assert qty.get('xt60h_f', 0) >= sockets_60, (qty.get('xt60h_f'), sockets_60)
        assert qty.get('xt30_f', 0) >= 2, qty.get('xt30_f')


def test_body_loads_from_the_mount_plane():
    f = R / 'exports' / 'body' / 'leg-loads.json'
    d = json.loads(f.read_text())
    for k in ('rare_body', 'fault_body'):
        M, name = d[k]
        b = d['scenarios'][name]['body']
        assert 0 < b['peak_vertical_n'] < d['scenarios'][name]['peak_axle_force_n']
        assert abs(b['peak_vertical_n'] - b['peak_vertical_check_ballast_n']) < 0.05 * b['peak_vertical_n'] + 10, b


def test_lidar_ahead_of_the_pan_axis_by_143():
    """The turret's depression table is computed for the lidar's axis 143 mm ahead of the pan axis
    (docs/turret-next-plan.md 3.1): the body keeps that number."""
    assert abs(bp.lidar()['x'] - bp.tm()['pan_x'] - 143.0) < 1e-6


def test_turret_grommet_on_the_right_rear():
    """The turret's DT12 plug is on its right (-y): its pigtail drops through the deck at the right rear."""
    x, y = bp.TURRET_GROMMET
    assert x < bp.tm()['pan_x'] and y < 0


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q', '-s']))
