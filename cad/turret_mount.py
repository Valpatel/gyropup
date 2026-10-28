"""The turret's interface file for the body: exports/turret/mount.json (docs/turret-next-plan.md section 3.1, task N5).

    .venv/bin/python cad/turret_mount.py            # build the turret and write exports/turret/mount.json
    .venv/bin/python cad/turret_mount.py --check    # read the file back against cad/turret.py's constants (no build)

cad/build_turret.py calls `write(T)` at the end of every bench build, so the file follows the CAD: the TM pattern, the
foot, the DT12 receptacle and its plug's boxes come from cad/turret.py, the mass and the centre from its
`mass_properties()`, the lidar clearance from exports/turret/lidar/lidar.json, the bank and the TM screws from
exports/turret/bench/bom.json, the ramp and the CAN set from the firmware reference (firmware/turret/config.py,
can_msgs.py), the spin-up current from exports/turret/e2e/power.json and the recoil from exports/turret/e2e/dynamics.json.
What no file holds (the harness's pinout, the safety contact's rating) is written here with the page it comes from.
Every block names its source. The body reads it (cad/body_params.py `tm()`, branch body/program): the top-level
`mass_kg` and `com_mm` are the turret with its 30 balls at pan 0, tilt 0.

The frame is the turret's T frame (cad/turret.py): x forward, y left, z up, mm, the origin on the pan axis in the TM
face (the foot's underside, the riser's top). On the robot the body puts that origin on its deck's centre line,
`lidar_clearance.made_for.lidar_to_pan_mm` behind the lidar's axis and `riser.height_mm` above the deck.

After writing, the file is read back and its TM pattern compared with cad/turret.py's TM_BOLTS, TM_DOWELS and TM_HOLE
(and DT_Z, the foot): any difference raises, so a file that does not round-trip is never left behind.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402

OUT = R / 'exports' / 'turret' / 'mount.json'
LIDAR_JSON = R / 'exports' / 'turret' / 'lidar' / 'lidar.json'
BOM_JSON = R / 'exports' / 'turret' / 'bench' / 'bom.json'
POWER_JSON = R / 'exports' / 'turret' / 'e2e' / 'power.json'
DYNAMICS_JSON = R / 'exports' / 'turret' / 'e2e' / 'dynamics.json'
RISER_H = 30.0                 # D41 (docs/body-plan.md 1.1): the turret on a 30 mm printed riser on the top deck
BACKSHELL = {'y': 22.0, 'down': 35.0}   # the 90 deg backshell as cad/turret.py bought_parts() draws it (est size)
# docs/turret-wiring.md 1.1 (the TM connector) and 4 (the protection behind it); on the robot pins 7-8 are the body's
# STOP contact instead of the pendant's loop (docs/turret-next-plan.md 3.2 item 3, D52)
HARNESS = [
    {'pins': [1, 2], 'signal': '+24 V', 'wire': '18 AWG PTFE, paralleled'},
    {'pins': [3, 4], 'signal': 'GND', 'wire': '18 AWG, paralleled'},
    {'pins': [5, 6], 'signal': 'CAN_H, CAN_L', 'wire': '24 AWG twisted pair'},
    {'pins': [7, 8], 'signal': 'SAFETY_A, SAFETY_B', 'wire': '24 AWG twisted pair: the dry safety loop, closed = run'},
    {'pins': [9, 10, 11, 12], 'signal': 'spare', 'wire': None},
]


def _fw(name: str):
    """A firmware reference module (pure Python) by file, under its own name, so cad/'s import path stays as it was."""
    key = f'_turret_fw_{name}'
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, R / 'firmware' / 'turret' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod                                 # a dataclass looks its module up while it is built
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _rel(path: Path) -> str:
    return str(path.relative_to(R))


def _r(v, n=2):
    return [_r(x, n) for x in v] if isinstance(v, (list, tuple)) else round(float(v), n)


def _box(lo, hi) -> dict:
    return {'min_mm': _r(lo), 'max_mm': _r(hi)}


def dt_boxes(G) -> dict:
    """The DT06 plug as cad/turret.py bought_parts() draws it (the plug body standing proud of the receptacle's flange and
    the 90 deg backshell turning the harness down), the 30 mm withdrawal box clashes() sweeps against the fixed parts,
    and the backshell's own path out (which the clash sweep leaves out: it is all below the turret, the body's side).
    Built on +y and flipped to the -y pad, as the CAD does: x and y change sign, so the boxes are written on -y."""
    f, pl, sw = tu.DT['flange'], tu.DT['plug'], tu.DT['sweep']
    y0 = G.dt_y + f[1]                                     # the flange's outer face, where the plug seats
    zc, hx = tu.DT_Z, pl[0] / 2
    body = ((-hx, -(y0 + pl[1]), zc - pl[2] / 2), (hx, -y0, zc + pl[2] / 2))
    shell = ((-hx, -(y0 + pl[1]), zc - pl[2] / 2 - BACKSHELL['down']), (hx, -(y0 + pl[1] - BACKSHELL['y']), zc))
    sweep = ((-hx, -(y0 + pl[1] + sw), zc - pl[2] / 2), (hx, -(y0 + pl[1]), zc + pl[2] / 2))
    shell_out = ((-hx, -(y0 + pl[1] + sw), shell[0][2]), (hx, shell[1][1], shell[1][2]))
    return {'plug_body': body, 'plug_backshell': shell, 'withdrawal_sweep': sweep, 'backshell_withdrawal': shell_out}


def _box_volume(b) -> float:
    return math.prod(hi - lo for lo, hi in zip(*b))


def _overlap(a, b) -> float:
    return math.prod(max(0.0, min(ah, bh) - max(al, bl)) for al, ah, bl, bh in zip(a[0], a[1], b[0], b[1]))


def _plug_matches_cad(T, boxes) -> dict:
    """The plug's two boxes against the plug cad/turret.py draws: the same bounding box and the same volume."""
    s = T.bought['dt_plug'][0]
    v = s.val() if hasattr(s, 'val') else s
    bb = v.BoundingBox()
    b, sh = boxes['plug_body'], boxes['plug_backshell']
    lo = [min(b[0][k], sh[0][k]) for k in range(3)]
    hi = [max(b[1][k], sh[1][k]) for k in range(3)]
    vol = _box_volume(b) + _box_volume(sh) - _overlap(b, sh)
    cad_lo, cad_hi = (bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax)
    ok = all(abs(p - q) < 0.01 for p, q in zip(lo + hi, cad_lo + cad_hi)) and abs(vol - v.Volume()) < 1.0
    return {'matches_cad': ok, 'volume_mm3': round(vol, 1), 'cad_volume_mm3': round(v.Volume(), 1)}


def _envelope(T, tol: float = 0.1) -> dict:
    """The turret's extent in the T frame, the robot's DT06 plug apart: the lowest point and the top (bounding boxes),
    and the largest radius from the pan axis of the fixed parts and of the parts that pan and tilt (their surfaces
    tessellated to `tol`, plus `tol`), the tilting ones at tilt 0 and -25 deg; each with the part that sets it."""
    ext = {'lowest': (1e9, None), 'top': (-1e9, None), 'fixed_r': (0.0, None), 'swept_r': (0.0, None)}
    for name in T.local:
        if name == 'dt_plug':
            continue
        fr = T.frame[name]
        for tilt in ((0.0, T.G.tilt_min) if fr == 'tilt' else (0.0,)):
            s = T.pose_shape(T.local[name], fr, 0.0, tilt, robot=False)
            v = s.val() if hasattr(s, 'val') else s
            bb = v.BoundingBox()
            r = max(math.hypot(p.x, p.y) for p in v.tessellate(tol, 0.1)[0]) + tol
            key = 'swept_r' if fr in ('pan', 'tilt') else 'fixed_r'
            if r > ext[key][0]:
                ext[key] = (r, name)
            if bb.zmin < ext['lowest'][0]:
                ext['lowest'] = (bb.zmin, name)
            if bb.zmax > ext['top'][0]:
                ext['top'] = (bb.zmax, name)
    return {'lowest_z_mm': round(ext['lowest'][0], 2), 'nothing_below_face': ext['lowest'][0] >= -0.01,
            'top_z_mm': round(ext['top'][0], 1), 'top_by': ext['top'][1],
            'fixed_r_mm': round(ext['fixed_r'][0], 1), 'fixed_r_by': ext['fixed_r'][1],
            'swept_r_mm': round(ext['swept_r'][0], 1), 'swept_r_by': ext['swept_r'][1],
            'how': 'every part in the T frame (tilting parts at 0 and -25 deg), the robot\'s DT06 plug apart: z from bounding '
                   'boxes, radii from the pan axis over the tessellated surfaces (0.1 mm, added)'}


def _bom_line(bom, line: str):
    for r in (bom or {}).get('bench_turret', []):
        if r.get('for') == line:
            return r
    return None


def _length(line, default: float) -> float:
    """A screw's or a pin's length from its catalogue key ('screw_m5x16' -> 16), else the default."""
    m = re.search(r'x(\d+(?:\.\d+)?)$', (line or {}).get('key') or '')
    return float(m.group(1)) if m else default


def mount(T) -> dict:
    """mount.json's content for the turret T (cad/turret.py Turret, any L: everything is in the T frame)."""
    G = T.G
    cfg, cm = _fw('config'), _fw('can_msgs')
    bom, power, dyn, lid = _read(BOM_JSON), _read(POWER_JSON), _read(DYNAMICS_JSON), _read(LIDAR_JSON)
    screw_l = _length(_bom_line(bom, 'hw_tm_screws'), 16.0)                        # screw_m5x16 (pan_base(): 4 x M5 x 16)
    dowel_l = _length(_bom_line(bom, 'hw_tm_dowels'), 16.0)                        # dowel_5x16
    dowel_in_foot = G.foot_t - 1.0                                                 # pan_base(): Ø5 from below, t - 1 deep
    caps = _bom_line(bom, 'el_capacitors')
    n_caps = caps['qty'] if caps else 2

    # ---- mass and centre (cad/turret.py mass_properties: printed parts by the printed-part model, bought at the catalogue)
    rows_b, m_b, c_b = tu.mass_properties(T, tilt=0.0, with_balls=True)
    _, m_e, c_e = tu.mass_properties(T, tilt=0.0, with_balls=False)
    _, m_d, c_d = tu.mass_properties(T, tilt=G.tilt_min, with_balls=True)
    balls = rows_b.get('balls_30', {})

    # ---- the DT12 and its plug
    boxes = dt_boxes(G)
    f = tu.DT['flange']
    plug = _plug_matches_cad(T, boxes)
    if not plug['matches_cad']:
        raise AssertionError(f'mount.json: the DT plug boxes no longer match cad/turret.py\'s plug: {plug}')

    # ---- power (the 300 ms ramp's row of the power model's sweep; the stepped start, never used)
    ramp = next((r for r in (power or {}).get('ramp_sweep', []) if abs(r['ramp_s'] - cfg.RAMP_S) < 1e-6), {})
    verdict = (power or {}).get('verdict', {})

    # ---- the lidar table
    lidar = None
    if lid:
        L = lid.get('lidar', {})
        worst = (lid.get('worst') or {}).get('max_depression_deg')
        at = [r['pan'] for r in lid.get('per_pan', []) if r.get('max_depression_deg') == worst]
        lidar = {'table_file': _rel(LIDAR_JSON), 'table_key': 'firmware_table', 'rows': len(lid.get('firmware_table', [])),
                 'made_for': {'lidar': L.get('model'), 'lidar_to_pan_mm': L.get('centre_x_mm'), 'lidar_top_above_tm_mm': L.get('top_above_tm_mm'),
                              'lidar_d_mm': L.get('d'), 'gap_to_bumper_mm': L.get('gap_to_bumper_mm'), 'margin_mm': lid.get('margin_mm'),
                              'ball': lid.get('ball')},
                 'limited_pan_window_deg': lid.get('limited_pan_window_deg'), 'worst': lid.get('worst'),
                 'worst_row': {'min_tilt_deg': worst, 'pans_deg': [min(at), max(at)] if at else None},
                 'firmware_default': 'firmware/turret/config.py ROBOT_DEPRESSION: the same table, which the firmware holds for '
                                     'mount robot while no table is loaded',
                 'keep_out_fire_pan_deg': lid.get('keep_out_fire_pan_deg'),
                 'rule': 'the table holds only for the lidar where made_for puts it: regenerate it (cad/turret_lidar.py --x '
                         '<lidar to pan>) when the lidar or the turret moves; the host loads it (firmware/turret/host.py --mount robot)',
                 'source': f'{_rel(LIDAR_JSON)} (cad/turret_lidar.py)'}

    tm = {'bolts_mm': [list(p) for p in tu.TM_BOLTS], 'bolt': 'M5', 'bolt_screw': f'M5 x {screw_l:g}, {len(tu.TM_BOLTS)} off',
          'dowels_mm': [list(p) for p in tu.TM_DOWELS], 'dowel_d_mm': 5.0,
          'dowel_pin': f'Ø5 x {dowel_l:g}, {len(tu.TM_DOWELS)} off: not symmetric, the turret goes on one way only',
          'hole_d_mm': tu.TM_HOLE, 'hole_use': 'unused on the robot: the harness leaves by the DT12, nothing passes the hole',
          'foot_d_mm': round(2 * tu.PLINTH['r'], 2), 'foot_t_mm': tu.PLINTH['tray_t'],
          'foot': 'D66: the compute plinth\'s floor (cad/turret.py compute_tray) flat on the head\'s TM face, no centre opening; '
                  f'the pan base sits {tu.PLINTH["h"]:g} mm above on the plinth\'s columns',
          'plinth': {'height_mm': tu.PLINTH['h'], 'd_mm': 2 * tu.PLINTH['r'], 'decision': 'D66: the turret\'s own Jetson (reComputer Mini J4012) inside',
                     'ports_side': '-x (the turret\'s back): the XT30 power input (12-54 V; the 10S bus through the body\'s fused branch) '
                                   'and the RJ-45 (Ethernet to the J501)',
                     'xt30_mm': [round(-math.sqrt(tu.PLINTH['r'] ** 2 - tu.PLINTH['xt30_y'] ** 2), 1), tu.PLINTH['xt30_y'], round(30.0 + tu.PLINTH['tray_t'], 1)],
                     'rj45_mm': [round(-math.sqrt(tu.PLINTH['r'] ** 2 - tu.PLINTH['eth_y'] ** 2), 1), tu.PLINTH['eth_y'], round(30.0 + tu.PLINTH['tray_t'], 1)],
                     'ports_frame': 'x, y on the pan axis, z above the head\'s TM face',
                     'mass_g_est': 780},
          'bumper_r_mm': G.bumper_r[1], 'bumper_lug_r_mm': tu.BUMPER_LUG[1], 'bumper_z_mm': list(G.bumper_z),
          'source': 'cad/turret.py TM_BOLTS, TM_DOWELS, TM_HOLE, Geo.base_r / foot_t / bumper_r, pan_base(); the screw and pin '
                    f'lengths from {_rel(BOM_JSON)} (hw_tm_screws, hw_tm_dowels)'}
    riser = {'height_mm': RISER_H, 'decision': 'D41: a printed riser on the top deck, open sides',
             'top_ring': 'solid under the four bolts and the two dowels; nothing of it inside the DT plug boxes (dt12.boxes)',
             'inserts': f'4 x M5 heat-set, {tu.INSERT_DEPTH:g} mm deep, pilot Ø{tu.FAST["M5"]["insert_pilot"]:g}',
             'screw_tip_below_face_mm': round(screw_l - G.foot_t, 1),
             'bolt_hole_depth_min_mm': round(screw_l - G.foot_t + 1.0, 1),
             'dowel_holes': f'2 x Ø5 H7 (reamed), at least {dowel_l - dowel_in_foot + 0.5:g} mm deep: {dowel_in_foot:g} mm of each '
                            f'{dowel_l:g} mm pin is in the foot',
             'source': 'docs/body-plan.md 1.1 (D41); the depths from the screw and pin lengths and cad/turret.py pan_base() '
                       '(the M5 heads on the 5 mm foot, the dowel holes 4 mm into it); cad/turret.py head_ring_tm() is the same '
                       'interface on the old head ring'}
    dt12 = {'receptacle': 'TE Deutsch DT04-12PA-L012 flange receptacle (te-dt04-12pa-l012)',
            'plug': 'DT06-12SA with its W12S wedge (te-dt06-12sa-kit), a 1011-248-1205 90 deg backshell turning the harness down',
            'side': '-y: the turret\'s right, which is the robot\'s right (the base does not pan)',
            'centre_mm': [0.0, -G.dt_y, tu.DT_Z], 'centre_above_tm_mm': tu.DT_Z,
            'pad_face_y_mm': -G.dt_y, 'flange_face_y_mm': round(-(G.dt_y + f[1]), 2),
            'plug_axis': [0.0, -1.0, 0.0], 'withdrawal_mm': tu.DT['sweep'],
            'boxes': {k: _box(*v) for k, v in boxes.items()},
            'box_notes': {'plug_body': 'the DT06 standing proud of the flange (cad/turret.py bought_parts dt_plug)',
                          'plug_backshell': 'the 90 deg backshell down to the deck (est size; cad/turret.py bought_parts dt_plug)',
                          'withdrawal_sweep': 'the plug body\'s 30 mm path out, which cad/turret.py clashes() sweeps against the fixed parts',
                          'backshell_withdrawal': 'the backshell\'s 30 mm path out: below the TM face, the body\'s side (riser, deck, '
                                                  'grommet); not in the turret\'s clash sweep'},
            'plug_check': plug,
            'plug_in_with': 'the turret parked and the body\'s 24 V branch off',
            'source': 'cad/turret.py DT, DT_Z, Geo.dt_y, bought_parts() (dt_receptacle, dt_plug), clashes() (the sweep box); '
                      'docs/turret-wiring.md 1.1'}
    harness = {'connector': 'DT12 (above)', 'pins': HARNESS,
               'in_the_turret': 'a 5 A MINI fuse (littelfuse-0297005-wxnv) in its in-line holder in the lead to the base board, '
                                'and D8 (1N5822) after it: a reversed supply blows the fuse',
               'safety_contact': 'across pins 7-8: a dry contact, closed = run, rated for 12 V at 2 mA (the base 555\'s pulse loop); '
                                 'opens on the radio stop, on the receiver\'s failsafe and when the robot sits (D37, D52)',
               'source': 'docs/turret-wiring.md 1.1, 3.1 and 4; docs/turret-next-plan.md 3.2 item 3'}
    mass = {'pose': 'pan 0, tilt 0 (the centre turns with pan about the pan axis)',
            'with_30_balls': {'mass_g': round(m_b, 1), 'com_mm': _r(c_b, 1)},
            'empty': {'mass_g': round(m_e, 1), 'com_mm': _r(c_e, 1)},
            'with_30_balls_at_tilt_min': {'tilt_deg': G.tilt_min, 'mass_g': round(m_d, 1), 'com_mm': _r(c_d, 1)},
            'balls': {'count': 30, 'mass_g': round(balls.get('mass_g', 0.0), 1), 'note': balls.get('note')},
            'com_off_pan_axis_mm': round(math.hypot(c_b[0], c_b[1]), 1),
            'com_above_deck_on_riser_mm': round(c_b[2] + RISER_H, 1),
            'budget': 'D49 (proposed): 1.70 kg with a full hopper, the centre at most 100 mm above the TM face',
            'source': 'cad/turret.py mass_properties() (printed parts by the printed-part model, bought parts at their catalogue '
                      'masses, the not-modelled allowance at the turntable)'}
    pw = {'supply_v': 24.0,
          'ramp_s': cfg.RAMP_S, 'ring_peak_a': ramp.get('ring_peak_a'), 'time_to_95pct_speed_s': ramp.get('time_to_95pct_speed_s'),
          'stepped_start_a': verdict.get('step_ring_peak_a'),
          'never_stepped': 'the firmware always ramps the flywheels (config.RAMP_S); a stepped start (stepped_start_a) is never used on the robot',
          'burst_peak_a': verdict.get('burst_ring_peak_a'), 'burst_rms_a': verdict.get('burst_ring_rms_a'),
          'game_average_a': 1.5, 'average_w_budget': 40.0,
          'bank_uf': 1000 * n_caps,
          'bank': f'{n_caps} x 1000 uF 35 V low ESR ({caps["key"] if caps else "panasonic-eeu-fr1v102"}) across the ring\'s +24 V on '
                  f'the turret boards\' level 1 (the power model in {_rel(POWER_JSON)} assumed 3 x 1,000 uF)',
          'hot_plug': 'plug and unplug the DT12 only with the body\'s 24 V branch off: the bank charges through the pins otherwise',
          'body_side': 'the body\'s 24 V branch with its own fuse, and the STOP relay\'s second pole in it (D52)',
          'source': f'{_rel(POWER_JSON)} (ramp_sweep at the firmware\'s RAMP_S, verdict), firmware/turret/config.py RAMP_S, '
                    f'docs/turret-wiring.md 4-5 (the game average <= 1.5 A at the ring, the bank), docs/head-payload.md (40 W '
                    f'average), {_rel(BOM_JSON)} (el_capacitors)'}
    can = {'standard': 'classic CAN (11-bit IDs, 8-byte frames)', 'bitrate': 1_000_000, 'pins': 'DT12 5-6',
           'termination': 'the turret\'s Feather M4 CAN terminates its own end (120 R); the body terminates its end at the J501\'s can1',
           'ids': {name: f'0x{cid:03X}' for cid, (name, _f, _x) in sorted(cm.MSGS.items())},
           'host_heartbeat_hz': 10, 'heartbeat_timeout_ms': round(cfg.HEARTBEAT_MAX_AGE_S * 1000),
           'host': 'firmware/turret/host.py: SocketCAN can1 on the Jetson (the J501\'s second port), a gs_usb USB-CAN as can0 on the laptop',
           'source': 'docs/turret-firmware.md 6, firmware/turret/can_msgs.py, firmware/turret/config.py HEARTBEAT_MAX_AGE_S'}
    rc = (dyn or {}).get('recoil', {})
    recoil = {'impulse_per_shot_ns': round(rc.get('impulse_per_shot_ns', 0.0), 3), 'impulse_hopper_ns': round(rc.get('impulse_30_hopper_ns', 0.0), 2),
              'peak_force_n': rc.get('peak_force_on_cage_n'), 'pulse_ms': rc.get('pulse_ms'),
              'peak_moment_about_tilt_axis_nm': rc.get('peak_moment_about_tilt_axis_nm'), 'pan_moment': rc.get('pan_moment'),
              'rate_max_per_s': cfg.RATE_MAX, 'mean_force_at_3_per_s_n': (rc.get('mean_force_in_burst_n') or {}).get('3_per_s'),
              'source': f'{_rel(DYNAMICS_JSON)} recoil (docs/turret-physics.md 8)'}
    aim = {'pan': 'continuous (the slip ring), at most 90 deg/s (the servo through 3:1)', 'pan_rate_max_deg_s': cfg.PAN_SPEED_MAX,
           'tilt_deg': [cfg.TILT_MIN_DEG, cfg.TILT_MAX_DEG], 'tilt_rule': 'never above level: the hard stop at 0 and every goal clamped to <= 0',
           'tilt_axis_above_tm_mm': G.tilt_t, 'ball_path_above_tm_mm': G.path_t, 'muzzle_ahead_of_pan_axis_mm': G.barrel_x1 - G.tilt_x,
           'fps_max': cfg.CAP_FPS, 'source': 'firmware/turret/config.py, cad/turret.py Geo'}
    return {'what': 'the turret\'s interface for the body (docs/turret-next-plan.md 3.1, task N5)',
            'frame': 'the turret frame T: x forward, y left, z up (mm), the origin on the pan axis in the TM face',
            'written_by': 'cad/build_turret.py through cad/turret_mount.py, from the CAD as built',
            'mass_kg': round(m_b / 1000.0, 4), 'com_mm': _r(c_b, 1),
            'tm': tm, 'riser': riser, 'dt12': dt12, 'harness': harness, 'mass': mass, 'power': pw, 'can': can,
            'lidar_clearance': lidar, 'recoil': recoil, 'aim': aim, 'envelope': _envelope(T),
            'round_trip': 'cad/turret_mount.py --check reads this file back against cad/turret.py\'s TM_BOLTS, TM_DOWELS, TM_HOLE'}


def check(path: Path = OUT) -> list:
    """Read mount.json back and compare it with cad/turret.py's constants. Returns the differences ([] = it round-trips)."""
    m = json.loads(Path(path).read_text())
    G = tu.Geo()
    want = {('tm', 'bolts_mm'): [list(p) for p in tu.TM_BOLTS], ('tm', 'dowels_mm'): [list(p) for p in tu.TM_DOWELS],
            ('tm', 'hole_d_mm'): tu.TM_HOLE, ('tm', 'foot_d_mm'): 2 * tu.PLINTH['r'], ('dt12', 'centre_above_tm_mm'): tu.DT_Z,
            ('dt12', 'pad_face_y_mm'): -G.dt_y, ('dt12', 'withdrawal_mm'): tu.DT['sweep']}
    bad = []
    for (blk, key), v in want.items():
        got = (m.get(blk) or {}).get(key)
        if got != v:
            bad.append(f'{blk}.{key}: file {got!r}, cad/turret.py {v!r}')
    if [tuple(p) for p in m['tm']['bolts_mm']] != tu.TM_BOLTS or [tuple(p) for p in m['tm']['dowels_mm']] != tu.TM_DOWELS:
        bad.append('tm: the bolt or dowel pattern does not read back as cad/turret.py\'s tuples')
    return bad


def write(T, path: Path = OUT) -> dict:
    """Write mount.json for the turret T and check that it reads back to cad/turret.py's TM constants (raises if not)."""
    m = mount(T)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(m, indent=1, ensure_ascii=False) + '\n')
    bad = check(path)
    if bad:
        raise AssertionError('mount.json does not round-trip: ' + '; '.join(bad))
    print(f"mount.json: {m['mass']['with_30_balls']['mass_g'] / 1000:.3f} kg with balls, {m['mass']['empty']['mass_g'] / 1000:.3f} empty, "
          f"centre {m['com_mm']}; the TM pattern round-trips -> {_rel(path)}")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true', help='only read the file back against cad/turret.py (no build)')
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    if a.check:
        bad = check(Path(a.out))
        print('\n'.join(bad) if bad else f'{a.out}: the TM pattern, the foot and the DT12 round-trip cad/turret.py')
        return 1 if bad else 0
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})            # the mount face at z = 0, as cad/build_turret.py builds it
    write(T, Path(a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
