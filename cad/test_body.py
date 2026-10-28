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
    P = bp.j501_params()
    j = bp.j501()
    assert j['holes'] == [tuple(h) for h in P['pcb']['mount_holes']]
    assert j['module_holes'] == [tuple(h) for h in P['pcb']['module_mount_centers']]
    assert j['cooler'] == tuple(P['cooler']['size'])
    # the module tie-down pattern is the 92 x 79 rectangle the plan names
    xs = sorted({h[0] for h in j['module_holes']})
    ys = sorted({h[1] for h in j['module_holes']})
    assert (xs[-1] - xs[0], ys[-1] - ys[0]) == (92, 79)


def test_j501_snapshot_is_the_live_file():
    """B10: the body builds from references/vendor/j501/ when the j501-agx project is not on the machine (CI, the
    GB10s); when it is, every part of it the body reads must equal the snapshot, so a moved cooler centre or a changed
    port fails here until the snapshot is updated on purpose (.venv/bin/python cad/body_params.py --snapshot-j501)."""
    snap = json.loads(bp.J501_SNAPSHOT.read_text())
    src = json.loads(bp.J501_SNAPSHOT_SOURCE.read_text())
    import hashlib
    assert hashlib.sha1(bp.J501_SNAPSHOT.read_bytes()).hexdigest() == src['sha1'], 'the snapshot was edited by hand'
    live = bp.J501_DIR / 'cad' / 'parameters.json'
    if not live.exists():
        import pytest
        pytest.skip('the j501-agx project is not on this machine: the body uses the snapshot')
    a, b = bp.j501_used(json.loads(live.read_text())), bp.j501_used(snap)
    changed = [k for k in a if a[k] != b[k]]
    assert not changed, f'the J501 project changed {changed} since the snapshot of {src["copied_on"]} ({src["commit"][:8]}): check the body, then snapshot'


def test_j501_without_the_project():
    """The body's J501 numbers are the same from the snapshot alone (a fresh interpreter with J501_DIR pointing nowhere)."""
    import os
    import subprocess
    code = ('import sys, json; sys.path.insert(0, "cad"); import body_params as bp; '
            'print(json.dumps({"src": bp.j501()["source"], "stack": bp.j501_stack(), "holes": bp.j501()["holes"]}))')
    env = dict(os.environ, J501_DIR='/nonexistent-j501')
    out = json.loads(subprocess.run([sys.executable, '-c', code], cwd=R, env=env, capture_output=True, text=True, check=True).stdout)
    assert out['src'].startswith('references/vendor/j501/'), out['src']
    assert out['stack'] == json.loads(json.dumps(bp.j501_stack())) and out['holes'] == json.loads(json.dumps(bp.j501()['holes']))


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
            assert abs(s['bd'] / bp.IN - s['bd_in']) < 0.004, (key, s['bd'] / bp.IN)      # SendCutSend's table rounds


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


def test_frame_out_of_the_keepouts():
    """No frame part in a keep-out zone: the J501's plugs, the cooler's exhaust, the turret's plug and its sweep, its
    harness drop, the cable slot (build_body.FRAME_ZONE_OK lists the contacts that are by design)."""
    b = _body()
    if 'in_keepouts' not in b:
        import pytest
        pytest.skip('body.json from before the keep-out check')
    assert b['in_keepouts'] == [], b['in_keepouts']


def test_turret_plate():
    """D59: the turret mount plate passes the sheet rules (test_sheet_rules), covers none of the deck's intake cells,
    and adds no more than the plan's 135 g to the ledger."""
    b = _body()
    if 'turret_plate' not in b['sheet']:
        import pytest
        pytest.skip('body.json from before the turret plate')
    tp = b['turret_plate']
    assert tp['cells'] > 0 and tp['cells_covered'] == 0, tp
    assert b['mass_g']['frame_parts']['turret_plate'] <= 135.0, b['mass_g']['frame_parts']['turret_plate']
    assert b['sheet']['turret_plate']['hardware'] == {'SS-M5-0': 2}


def test_frame_strength_cases():
    """Every strength case of cad/body_studies.py passes its target (exports/body/fea/summary.json): SF >= 2 on yield
    in the rare landings, 1.2 in the fault cases, D2 (the turret's tip-over) >= 2.0 with the mount plate (D59), the deck
    <= 0.5 mm under a hand at the load, the twist <= 0.1 deg; the loads at the design mass (D57)."""
    s = json.loads((R / 'exports' / 'body' / 'fea' / 'summary.json').read_text())['results']
    bad = {k: (r.get('sf_by_part') or r.get('sf_away_from_spacer_ends') or r['safety_factor'], r.get('target_sf'))
           for k, r in s.items() if not r['pass'] or r.get('pass_deflection') is False or r.get('pass_twist') is False}
    assert not bad, bad
    d2 = s['D2-turret-fall']
    assert d2['target_sf'] >= 2.0, d2['target_sf']
    loads = json.loads((R / 'exports' / 'body' / 'leg-loads.json').read_text())
    assert loads['half_mass_kg'] >= 16.25 - 1e-9, loads['half_mass_kg']


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


AMPACITY_A = {8: 85, 10: 55, 12: 41, 14: 32, 16: 22, 18: 16, 22: 7}       # silicone, bundled in free air (the BNTECHGO class, 200 C)


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
    bus branch leads (XT60H-F, the turret's XT30U-F) and the 12 V ones (XT30U-F); the devices' leads carry the
    pins. The bay's XT90-S: its female is on the bay's lead, the robot's male is dead with the packs out.
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
    assert all('XT30U-F' in ends[k] for k in ('W21', 'W24', 'W34')), ends
    f = R / 'exports' / 'body' / 'bom.json'
    if f.exists():
        bom = json.loads(f.read_text())
        qty = {r['key']: r['qty'] for k, rows in bom.items() if isinstance(rows, list) and not k.startswith(('not_', 'to_source', 'made_to'))
               for r in rows if isinstance(r, dict) and 'key' in r}
        sockets_60 = sum(1 for k in ('W10', 'W11', 'W12', 'W13', 'W14', 'W15') if 'XT60H-F' in ends[k])     # D65: no charge port
        assert qty.get('xt60h_f', 0) >= sockets_60, (qty.get('xt60h_f'), sockets_60)
        assert qty.get('xt30_f', 0) >= 3, qty.get('xt30_f')


def test_body_loads_from_the_mount_plane():
    f = R / 'exports' / 'body' / 'leg-loads.json'
    d = json.loads(f.read_text())
    for k in ('rare_body', 'fault_body'):
        M, name = d[k]
        b = d['scenarios'][name]['body']
        assert 0 < b['peak_vertical_n'] < d['scenarios'][name]['peak_axle_force_n']
        assert abs(b['peak_vertical_n'] - b['peak_vertical_check_ballast_n']) < 0.05 * b['peak_vertical_n'] + 10, b


import pytest  # noqa: E402


@pytest.mark.xfail(strict=True, reason='D69: with the 10 in hub wheels at their listed 3.53 kg the P3 ledger is 36.05 kg with '
                   'every scheduled lever, 1.05 kg over the 35.0 kg ceiling; the on-call levers and their owners are in issue #10 '
                   'and docs/body-sections.md 6. strict: this fails loudly once it passes')
def test_the_mass_ledger_under_the_ceiling():
    """D69: the robot is designed for 35.5 kg and held under 35.0 kg as built. The P3 ledger, with every scheduled lever
    of docs/body-next-plan.md 2.3 that is not in the CAD yet taken at its planned grams, stays under 35.0 kg, each leg
    under 10.85 and the body and head under 13.3; once every scheduled lever is in the CAD the ledger itself must be."""
    m = json.loads((R / 'exports' / 'body' / 'mass.json').read_text())['P3']
    g = m['gate']
    open_ = [l['key'] for l in m['levers'] if l['kind'] == 'scheduled' and l['status'] == 'open']
    print(f"\nmass ledger P3 {m['total_kg']} kg (ceiling {g['ceiling_kg']}, gap {g['gap_kg']:+.3f} kg); legs {g['leg_each_kg']} kg each; "
          f"with the open scheduled levers {open_} ({g['open_scheduled_g']} g): {g['with_scheduled_levers_kg']} kg")
    assert m['budget']['robot_kg'] == 35.0 and m['budget']['design_mass_kg'] == 35.5 and m['budget']['legs_kg_each'] == 10.85
    assert g['pass'], g
    if not open_:
        assert m['total_kg'] <= g['ceiling_kg'], (m['total_kg'], g)


def test_the_ledger_carries_the_d69_wheel():
    """D69: each wheel is the 10 in hub motor at its listed mass (until the leg's BOM carries it), and the design mass is
    35.5 kg (17.75 kg a leg)."""
    import body_layout as bl
    m = json.loads((R / 'exports' / 'body' / 'mass.json').read_text())['P3']
    w = {r['name']: r['mass_g'] for r in m['rows'] if r['name'].endswith(('wheel_tyre', 'wheel_hub'))}
    assert abs(w['L.wheel_tyre'] + w['L.wheel_hub'] - bl.wheel_g()) < 1.0, w
    assert bl.wheel_g() >= 3500.0
    assert m['budget']['design_half_mass_kg'] == 17.75


def test_the_gate_catches_a_ledger_over_the_ceiling():
    """The gate itself: a ledger over 35.0 kg with every scheduled lever taken fails it, as does a leg over 10.85 kg; the
    open scheduled levers' grams count toward it."""
    import body_layout as bl
    taken = [dict(l, status='taken') for l in bl.levers()]
    assert not bl.gate({'total_kg': 35.05, 'body_and_head_kg': 13.2, 'legs_kg': 21.6, 'levers': taken})['pass']
    assert not bl.gate({'total_kg': 34.9, 'body_and_head_kg': 13.2, 'legs_kg': 21.72, 'levers': taken})['pass']     # 10.86 a leg
    assert bl.gate({'total_kg': 34.9, 'body_and_head_kg': 13.25, 'legs_kg': 21.6, 'levers': taken})['pass']
    opened = [dict(l, status='open') for l in bl.levers()]                    # -705 g still to come
    assert bl.gate({'total_kg': 35.6, 'body_and_head_kg': 13.9, 'legs_kg': 21.6, 'levers': opened})['pass']
    assert not bl.gate({'total_kg': 35.8, 'body_and_head_kg': 14.1, 'legs_kg': 21.6, 'levers': opened})['pass']


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


def test_integrity_every_joint_and_no_floating_part():
    """cad/body_joints.py (run by cad/build_body.py): every screw's stack reads true through the CAD (the head on its face,
    the stack touching, the holes, the thread engaged, the tip clear), every part on the robot reaches the cheeks through
    cad-agent's connectivity gate (issue #14), and no two body parts interfere."""
    f = R / 'exports' / 'body' / 'integrity.json'
    d = json.loads(f.read_text())['summary']
    assert not d['joints_with_problems'], d['joints_with_problems']
    assert not d['floating'], d['floating']
    assert not d.get('clashes'), d.get('clashes')
    assert d.get('connectivity_pass') and all(d['connectivity_pass'].values()), d.get('connectivity_pass')   # cad-agent's gate (#14)


def test_pack_and_adapter_are_marked_envelopes_until_measured():
    """Issue #20: the DCB609 and its rail adapter stay labelled boxes until a real pack and adapter are measured; the
    ledger's rows say so, so nobody reads them as modelled interfaces."""
    import body_battery as bb
    for spec in (bb.PACK, bb.ADAPTER):
        assert spec.get('envelope') and '#20' in spec.get('blocked_by', ''), spec
    m = json.loads((R / 'exports' / 'body' / 'mass.json').read_text())['P3']
    rows = [r for r in m['rows'] if r['name'].startswith('battery_')]
    assert rows and all(r['basis'].startswith('ENVELOPE') for r in rows), [(r['name'], r['basis'][:40]) for r in rows]
