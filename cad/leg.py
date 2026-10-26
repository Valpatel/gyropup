"""The leg module, built on the GMI standard faces (docs/mechanical-interfaces.md, cad/gmi.py).

Robot frame: x forward, y left, z up; the hip axis is the y axis. Parts are built for the LEFT leg at the zero pose
(thigh and shin hanging straight down); the right leg is the mirror image (y -> -y).

The stack across the hip, from the body outwards (all from the motors' drawings and cad/interfaces.json):
  tray wall | hip bracket | hip motor (rear inboard) | hip motor plate (61812) | hip output adapter | thigh |
  push-rod plane | knee crank | knee output adapter | knee motor plate (61812) | knee motor (rear outboard)
Three spacer posts join the two motor plates above the axis, where the leg never swings. The knee is a passive pivot
(KC cartridge in the shin); the knee motor drives the shin through the push-rod (a parallelogram). The wheel adapter
(WH) sits on the shin's outer face; the wheel motor's cable comes out of the middle of its boss, through the adapter.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq

import gmi

STD = gmi.STD
# Sizes the optimiser varies (tools/iterate.py). Defaults are the current design; GYROPUP_CAD_PARAMS names a JSON file
# that overrides any of them for one trial.
PARAMS = {
    'link_w': 60.0, 'link_t': 44.0, 'wall': 5.0,      # thigh: a closed printed box section, x by y, wall (sized by the FEA)
    'shin_w': 50.0, 'shin_wall': 4.0,                 # the shin carries less
    'yoke_t': 8.0, 'yoke_depth': 50.0, 'yoke_gusset': 80.0,   # the yoke: wall thickness, side-flange depth, gusset length
    'crank_t': 14.0,                                  # knee crank thickness
    'crank_r': STD['PR']['crank_r'],
    'lever_beta_deg': STD['PR']['lever_beta_deg'],   # crank and lever direction, from the forward perpendicular (- = towards the foot)
}
if os.environ.get('GYROPUP_CAD_PARAMS'):
    PARAMS.update(json.loads(Path(os.environ['GYROPUP_CAD_PARAMS']).read_text()))
LINK_W, LINK_T, WALL = PARAMS['link_w'], PARAMS['link_t'], PARAMS['wall']
SHIN_W, SHIN_WALL = PARAMS['shin_w'], PARAMS['shin_wall']
CRANK_T = PARAMS['crank_t']
YOKE_T, YOKE_DEPTH, YOKE_GUSSET = PARAMS['yoke_t'], PARAMS['yoke_depth'], PARAMS['yoke_gusset']
CABLE_PASSES = [(-40.0, 20.0), (40.0, 0.0)]   # through the yoke's wall plate and the chassis side: wheel harness, motor leads


@dataclass
class Stack:
    y: dict          # named y positions (mm), left leg
    track: float     # wheel centre to wheel centre (mm)
    notes: list
    hip: dict        # motor interfaces
    knee: dict
    wheel: dict


def lever_pin(r: float = None, beta_deg: float = None):
    """(x, z) of the crank pin from the hip axis, and of the lever pin from the knee pin, at the zero pose."""
    r = PARAMS['crank_r'] if r is None else r
    b = math.radians(PARAMS['lever_beta_deg'] if beta_deg is None else beta_deg)
    return r * math.cos(b), r * math.sin(b)


def transmission(knee_min_deg: float, knee_max_deg: float, beta_deg: float = None, n: int = 60):
    """The push-rod's transmission: sin(angle between rod and lever) = |cos(q - beta)| with q = knee interior angle - 180°.
    Returns (smallest sin over the knee range, the interior knee angle where it happens). 0 is a dead point."""
    b = math.radians(PARAMS['lever_beta_deg'] if beta_deg is None else beta_deg)
    worst = (2.0, None)
    for k in range(n + 1):
        g = math.radians(knee_min_deg + (knee_max_deg - knee_min_deg) * k / n)
        sphi = abs(math.cos(g - math.pi - b))
        if sphi < worst[0]:
            worst = (sphi, math.degrees(g))
    return worst


def _ycyl(r, y0, y1, x=0.0, z=0.0):
    """A cylinder along y from y0 to y1, centred at (x, z)."""
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def stack(L: dict, hip_id: str, knee_id: str, wheel_id: str) -> Stack:
    hip, knee = gmi.motor_interface(hip_id), gmi.motor_interface(knee_id)
    wheel = gmi.motor_interface(wheel_id)
    _, had = gmi.output_adapter(hip_id, 'L')
    _, hpl = gmi.motor_plate(hip_id, 'L')
    hip['plate'] = hpl
    _, kad = gmi.output_adapter(knee_id, 'L')
    _, kpl = gmi.motor_plate(knee_id, 'L')
    knee['plate'] = kpl
    pr, kc, wh = STD['PR'], STD['KC'], STD['WH']
    y = {}
    y['wall'] = L['tray']['width'] / 2 + 1.0
    y['bracket'] = (y['wall'], y['wall'] + YOKE_T)
    y['hip_out'] = y['bracket'][1] + 2.0 + hip['length']                 # the hip motor's output face
    y['hip_motor'] = (y['hip_out'] - hip['length'], y['hip_out'])
    y['hip_plate'] = (y['hip_out'] + hpl['z'][0], y['hip_out'] + hpl['z'][1])
    y['hip_face'] = y['hip_out'] + had['z_face']                          # the standard AO face
    y['hip_tab'] = (y['hip_out'] + hpl['tab_z'][0], y['hip_out'] + hpl['tab_z'][1])   # the plate's top tab (bracket bolts)
    y['thigh'] = (y['hip_face'], y['hip_face'] + LINK_T)
    y['rod'] = (y['thigh'][1] + 1.5, y['thigh'][1] + 1.5 + pr['rod_end_ball_w'])
    y['crank'] = (y['rod'][1] + 1.5, y['rod'][1] + 1.5 + CRANK_T)
    y['knee_face'] = y['crank'][1]
    y['knee_out'] = y['knee_face'] + kad['z_face']                        # the knee motor's output face (it faces -y)
    y['knee_plate'] = (y['knee_out'] - kpl['z'][1], y['knee_out'] - kpl['z'][0])
    y['knee_motor'] = (y['knee_out'], y['knee_out'] + knee['length'])
    y['knee_tab'] = (y['knee_out'] - kpl['tab_z'][1], y['knee_out'] - kpl['tab_z'][0])   # mirrored: the tab's motor side faces +y
    y['posts'] = (y['hip_plate'][1], y['knee_plate'][0])
    y['shin'] = (y['crank'][0], y['crank'][0] + max(28.0, kc['spacing'] + kc['bearing_w']))
    y['wheel_adapter'] = (y['shin'][1], y['shin'][1] + wh['plate_t'])
    boss_h = wheel['case']['spigot_h'] or 5.0
    y['wheel_mount'] = y['wheel_adapter'][1]                                # the wheel's boss face
    tyre0 = y['wheel_mount'] + 7.5                                          # BotWheel drawing: boss face 7.5 outboard of the tyre side
    y['wheel'] = (tyre0, tyre0 + 44.6)
    y['wheel_centre'] = sum(y['wheel']) / 2
    notes = []
    if y['knee_plate'][0] - y['crank'][1] < 0.5:
        notes.append('the crank touches the knee motor plate')
    r_need = (wheel['od'] or 171.3) / 2 + (knee['od'] or 100) / 2 + 6
    y['min_hip_to_axle'] = r_need
    if y['wheel'][0] < y['knee_motor'][1] and y['wheel'][1] > y['knee_motor'][0]:
        a, b = L['thigh'], L['shin']
        g = 2 * math.degrees(math.asin(min(1.0, r_need / (2 * min(a, b)))))
        y['min_knee_deg'] = g
        notes.append(f'the wheel passes under the knee motor: hip-to-axle at least {r_need:.0f} mm, so the knee stops at {g:.0f}° or more')
    sphi, at = transmission(L['kneeMinDeg'], L['kneeMaxDeg'])
    y['min_sin_phi'], y['min_sin_phi_at_knee_deg'] = round(sphi, 3), round(at, 1)
    if sphi < 0.5:
        notes.append(f'the push-rod nears its dead point: sin phi {sphi:.2f} at a {at:.0f}° knee (keep >= 0.5)')
    return Stack(y, 2 * y['wheel_centre'], notes, hip, knee, wheel)


# ----------------------------------------------------------------------------------- the yoke

def hm_holes():
    """The HM pattern on the chassis side (x, z): 6 x M6 in two rows 60 mm apart, low enough to land on the chassis."""
    w, h = STD['HM']['rect']
    return [(x, z) for x in (-w / 2, 0, w / 2) for z in (0.0, h)]


def hm_dowels():
    return [(-STD['HM']['rect'][0] / 4, STD['HM']['rect'][1] / 2), (STD['HM']['rect'][0] / 4, STD['HM']['rect'][1] / 2)]


def yoke_bracket(S: Stack, L: dict):
    """The yoke: a printed PA6-CF hat channel (walls YOKE_T thick). A deck over both motors, two deep side flanges
    (front and back, YOKE_DEPTH deep) that carry the leg's out-of-plane moment, gusseted down to a wall flange on the
    chassis side (HM: 6 x M6 through-bolts with nuts inside the chassis, 2 dowels, and the cable passes), and two drop
    walls screwed to the top tabs of the hip and knee motor plates (3 x M5 into inserts each). With the three posts
    between the plates it closes a box around the joint. Printed on its wall flange."""
    ac = STD['AC-L']
    t, H, G = YOKE_T, YOKE_DEPTH, YOKE_GUSSET
    tab_top = max(S.hip['plate']['tab_top'], S.knee['plate']['tab_top'])
    ydh = S.y['hip_tab'][0]                       # hip drop: on the motor side (-y) of the hip plate's tab
    ydk = S.y['knee_tab'][1]                      # knee drop: on the motor side (+y) of the knee plate's tab
    y0, y1 = S.y['bracket'][0], ydk + t
    deck_z = tab_top + 4 + 1 + t / 2              # the plate tabs reach 4 mm above tab_top; the deck clears them by 1 mm
    top = deck_z + t / 2
    # wide enough that the side flanges clear the bigger of the two motors and the motor plates' tabs and rings
    ring = max(S.hip['plate'].get('ring_r', 58.0), S.knee['plate'].get('ring_r', 58.0))
    od = max(S.hip['od'] or 100.0, S.knee['od'] or 100.0)
    W = 2 * (max(55.0, od / 2 + 4.0, ring + 3.0) + t)
    z_low = -12.0                                 # the wall flange reaches down the chassis side (HM rows at z = 0 and 60)
    wall = cq.Workplane('XY').box(W, t, top - z_low).translate((0, y0 + t / 2, (top + z_low) / 2))
    deck = cq.Workplane('XY').box(W, y1 - y0, t).translate((0, (y0 + y1) / 2, deck_z))
    post_top = ac['post_r'] + ac['post_d'] / 2 + 4                       # the top post's boss
    dz0 = post_top + 1.0                                                  # drops stop just above it
    drops = (cq.Workplane('XY').box(W, t, top - dz0).translate((0, ydh - t / 2, (top + dz0) / 2))
             .union(cq.Workplane('XY').box(W, t, top - dz0).translate((0, ydk + t / 2, (top + dz0) / 2))))
    flanges = None
    for x in (-W / 2 + t / 2, W / 2 - t / 2):     # side flanges: full height at the wall, tapering to H over G
        prof = [(y0, z_low), (y0 + G, top - H), (y1, top - H), (y1, top), (y0, top)]
        f = cq.Workplane('YZ', origin=(x - t / 2, 0, 0)).polyline(prof).close().extrude(t)
        flanges = f if flanges is None else flanges.union(f)
    b = wall.union(deck).union(drops).union(flanges)
    for (x, z) in hm_holes():
        b = b.cut(_ycyl(gmi.clear(STD['HM']['thread']) / 2, y0 - 1, y0 + t + 1, x, z))
    for (x, z) in hm_dowels():
        b = b.cut(_ycyl(STD['HM']['dowel_d'] / 2 + 0.02, y0 - 1, y0 + t + 1, x, z))
    for k in range(ac['bracket_bolts']):
        x = (k - (ac['bracket_bolts'] - 1) / 2) * ac['plate_r'] * 0.4
        b = b.cut(_ycyl(gmi.clear(ac['bracket_thread']) / 2, ydh - t - 1, ydh + 1, x, S.hip['plate']['tab_top'] - gmi.BRACKET_DROP))
        b = b.cut(_ycyl(gmi.clear(ac['bracket_thread']) / 2, ydk - 1, ydk + t + 1, x, S.knee['plate']['tab_top'] - gmi.BRACKET_DROP))
    for (x, z) in CABLE_PASSES:                    # the same holes as the chassis wall
        b = b.cut(_ycyl(STD['CP']['grommet_hole'] / 2, y0 - 1, y0 + t + 1, x, z))
    return b                                      # (no deck windows: in plastic their corners start the cracks)


def posts(S: Stack):
    """Three spacer posts between the motor plates (bought: Ø10 aluminium round standoffs, M5 both ends; M5 screws
    through the printed plates with washers)."""
    ac = STD['AC-L']
    out = None
    for ang in ac['post_deg']:
        x, z = ac['post_r'] * math.cos(math.radians(ang)), ac['post_r'] * math.sin(math.radians(ang))
        p = _ycyl(ac['post_d'] / 2, *S.y['posts'], x, z)
        out = p if out is None else out.union(p)
    return out


# ----------------------------------------------------------------------------------- links

def _box_link(y0, y1, length, w, wall, end0_r, end1_r):
    """A closed box beam along -z from z = 0 to z = -length, solid round bosses at both ends (hollow in between, so
    cables can run inside)."""
    t = y1 - y0
    outer = cq.Workplane('XY').box(w, t, length).translate((0, (y0 + y1) / 2, -length / 2))
    inner = cq.Workplane('XY').box(w - 2 * wall, t - 2 * wall, length - end0_r - end1_r - 6).translate(
        (0, (y0 + y1) / 2, -(end0_r + 3) - (length - end0_r - end1_r - 6) / 2))
    return (outer.cut(inner).union(_ycyl(end0_r, y0, y1)).union(_ycyl(end1_r, y0, y1, 0, -length)))


def thigh(S: Stack, a: float):
    """Thigh: a closed printed box (LINK_W x LINK_T, WALL walls, PA6-CF printed flat so bending runs along the
    layers) from the hip's standard face to the knee pin. M5 screws from inside the hub into the adapter's inserts.
    The wheel's cables run inside it, in and out through grommeted holes near each end."""
    y0, y1 = S.y['thigh']
    kc = STD['KC']
    t = _box_link(y0, y1, a, LINK_W, WALL, 36.0, kc['hub_od'] / 2)
    # flare the box into the hip hub (in plastic the step from a 72 mm hub to the box is where it cracks)
    flare = (cq.Workplane('XZ', origin=(0, y1, 0)).polyline([(-36.0, 0.0), (36.0, 0.0), (LINK_W / 2, -36.0 - 45.0), (-LINK_W / 2, -36.0 - 45.0)])
             .close().extrude(y1 - y0))
    t = t.union(flare.cut(cq.Workplane('XY').box(LINK_W - 2 * WALL, y1 - y0 - 2 * WALL, 45.0).translate((0, (y0 + y1) / 2, -36.0 - 3 - 22.5 - 0.01))))
    face = 10.0                                   # the hub keeps a 10 mm face on the AO side; hollow behind it (screw heads)
    t = t.cut(_ycyl(36.0 - WALL - 1, y0 + face, y1 + 1))
    t = t.cut(gmi.place(gmi.std_face_mate('L', depth=y1 - y0 + 2), (0, y0, 0), (0, 1, 0)))
    t = t.cut(_ycyl(kc['pin_d'] / 2 + 0.01, y0 - 1, y1 + 1, 0, -a))
    for z in (-36.0 - 18, -a + kc['hub_od'] / 2 + 18):                  # cable ports on the back face (-x)
        t = t.cut(cq.Workplane('YZ', origin=(-LINK_W / 2 - 1, 0, 0)).center((y0 + y1) / 2, z).rect(12, 16).extrude(WALL + 2))
    return t


def shin(S: Stack, b: float, crank_r: float):
    """Shin: a closed printed box (SHIN_W x the KC width, SHIN_WALL walls); the KC hub (two 6001s pressed in) and the
    push-rod lever at the knee, the WH face (M5 inserts) on the outer side at the axle. The wheel's cable comes through
    the WH bore into the box and up to a port near the knee."""
    y0, y1 = S.y['shin']
    kc, wh = STD['KC'], STD['WH']
    s = _box_link(y0, y1, b, SHIN_W, SHIN_WALL, kc['hub_od'] / 2, wh['plate_d'] / 2)
    yl = S.y['rod'][1] + 1.5                                    # lever in the crank's plane, next to the rod end
    lx, lz = lever_pin(crank_r)
    beta = PARAMS['lever_beta_deg']
    arm = cq.Workplane('XY').box(crank_r, 12, 30).translate((crank_r / 2, yl + 6, 0)).rotate((0, 0, 0), (0, 1, 0), -beta)
    s = s.union(arm).union(_ycyl(15, yl, yl + 12, lx, lz))
    s = s.cut(_ycyl(4.1, yl - 1, yl + 14, lx, lz))                                           # M8 bolt + nut through the lever
    s = s.cut(_ycyl(kc['bearing_od'] / 2 + 0.02, y0 - 0.01, y0 + kc['bearing_w']))
    s = s.cut(_ycyl(kc['bearing_od'] / 2 + 0.02, y1 - kc['bearing_w'], y1 + 0.01))
    s = s.cut(_ycyl(kc['pin_d'] / 2 + 1.0, y0 - 1, y1 + 1))
    s = s.union(_ycyl(wh['plate_d'] / 2 + 6, y0, y1, 0, -b))                                 # a solid printed foot round the WH face
    s = s.cut(_ycyl(wh['pilot_d'] / 2 + 0.05, y1 - 3, y1 + 1, 0, -b))
    for (x, z) in gmi.circle_pts(wh['pcd'], wh['bolts'], 30):
        s = s.cut(_ycyl(gmi.FAST[wh['thread']]['insert_pilot'] / 2, y1 - 12, y1 + 1, x, -b + z))   # heat-set inserts
    s = s.cut(_ycyl(wh['cable_bore'] / 2, y0 + WALL, y1 + 1, 0, -b))
    s = s.cut(cq.Workplane('YZ', origin=(-SHIN_W / 2 - 1, 0, 0)).center((y0 + y1) / 2, -kc['hub_od'] / 2 - 18).rect(12, 16).extrude(SHIN_WALL + 2))
    return s


def crank(S: Stack, crank_r: float):
    """Knee crank (printed PA6-CF, CRANK_T thick) on the knee's standard face, an M8 bolt for the rod end at the
    crank radius."""
    y0, y1 = S.y['crank']
    lx, lz = lever_pin(crank_r)
    arm = cq.Workplane('XY').box(crank_r, y1 - y0, 32).translate((crank_r / 2, (y0 + y1) / 2, 0)).rotate((0, 0, 0), (0, 1, 0), -PARAMS['lever_beta_deg'])
    c = _ycyl(36.0, y0, y1).union(arm).union(_ycyl(16, y0, y1, lx, lz))
    c = c.cut(gmi.place(gmi.std_face_mate('L', depth=y1 - y0 + 2), (0, y1, 0), (0, -1, 0)))
    return c.cut(_ycyl(4.1, y0 - 1, y1 + 1, lx, lz))


def pushrod(S: Stack, a: float, crank_r: float):
    """Push-rod envelope: two female M8 rod ends on an M8 threaded rod, centres one thigh-length apart (bought)."""
    y0, y1 = S.y['rod']
    pr = STD['PR']
    yc = (y0 + y1) / 2
    lx, lz = lever_pin(crank_r)
    eye = lambda z: _ycyl(12, y0, y1, lx, z).cut(_ycyl(4.0, y0 - 1, y1 + 1, lx, z))
    w = cq.Workplane('XY').circle(pr['tube_od'] / 2)
    tube = (w.circle(pr['tube_id'] / 2) if pr.get('tube_id') else w).extrude(a - 56).translate((lx, yc, lz - a + 28))
    return eye(lz).union(eye(lz - a)).union(tube)


def wheel_adapter(S: Stack, b: float):
    """Wheel adapter (printed PA6-CF): WH face to the shin; the wheel motor's flange pattern and boss recess on the
    other side; the wheel's cable comes out of the middle of its boss and goes through here into the shin."""
    y0, y1 = S.y['wheel_adapter']
    wh, w = STD['WH'], S.wheel['case']
    boss = w['boss_d'] or 50.0
    d = max(wh['plate_d'], boss + 12)
    p = _ycyl(d / 2, y0, y1, 0, -b).union(_ycyl(wh['pilot_d'] / 2, y0 - 2.5, y0, 0, -b))
    p = p.cut(_ycyl(boss / 2 + 0.03, y1 - (w['spigot_h'] or 5.0) + 0.01 if False else y1 - 1.5, y1 + 0.01, 0, -b))
    for (x, z) in gmi.circle_pts(wh['pcd'], wh['bolts'], 30):
        p = p.cut(_ycyl(gmi.clear(wh['thread']) / 2, y0 - 3, y1 + 1, x, -b + z))
        p = p.cut(_ycyl(gmi.clear(wh['thread']) * 0.95, y1 - 3.5, y1 + 1, x, -b + z))
    bw = w['bolts']
    for (x, z) in gmi.circle_pts(bw['pcd'], angles=bw['angles']):
        p = p.cut(_ycyl(gmi.clear(bw['thread']) / 2, y0 - 3, y1 + 1, x, -b + z))
    return p.cut(_ycyl(wh['cable_bore'] / 2, y0 - 3, y1 + 1, 0, -b))


def leg_parts(L: dict, hip_id: str, knee_id: str, wheel_id: str, crank_r: float = None):
    """All the leg module's parts (left leg, zero pose), the bought envelopes, the stack, and what each part is."""
    S = stack(L, hip_id, knee_id, wheel_id)
    a, b = L['thigh'], L['shin']
    cr = crank_r or PARAMS['crank_r']
    parts, meta = {}, {}

    def add(name, shape, material, note, fea='pa6_cf_xy'):
        parts[name] = shape
        meta[name] = {'material': material, 'qty': 2, 'note': note, 'fea_material': fea, 'solid': True}

    ha, hai = gmi.output_adapter(hip_id, 'L')
    hp, _ = gmi.motor_plate(hip_id, 'L')
    ka, _ = gmi.output_adapter(knee_id, 'L')
    kp, _ = gmi.motor_plate(knee_id, 'L')
    _, hpi = gmi.motor_plate(hip_id, 'L')
    _, hai = gmi.output_adapter(hip_id, 'L')
    add('yoke_bracket', yoke_bracket(S, L), 'pa6-cf', 'printed PA6-CF on its wall flange; 6 x M6 through the chassis wall with nuts, 3 x M5 into each plate tab', fea='pa6_cf_z')
    add('hip_motor_plate', gmi.place(hp, (0, S.y['hip_out'], 0), (0, 1, 0)), 'pa6-cf', hpi['note'])
    add('hip_output_adapter', gmi.place(ha, (0, S.y['hip_out'], 0), (0, 1, 0)), 'pa6-cf', hai['note'], fea='pa6_cf_z')
    add('knee_output_adapter', gmi.place(ka, (0, S.y['knee_out'], 0), (0, -1, 0)), 'pa6-cf', hai['note'], fea='pa6_cf_z')
    add('knee_motor_plate', gmi.place(kp, (0, S.y['knee_out'], 0), (0, -1, 0)), 'pa6-cf', hpi['note'])
    add('thigh', thigh(S, a), 'pa6-cf', f'printed PA6-CF flat, {LINK_W:.0f} x {LINK_T:.0f} box, {WALL} mm walls, 100 % solid; 8 x M5 into the hip adapter; cables inside')
    add('shin', shin(S, b, cr).translate((0, 0, -a)), 'pa6-cf', f'printed PA6-CF flat, {SHIN_W:.0f} mm box, {SHIN_WALL} mm walls; two 6001-2RS pressed in; M5 inserts at the wheel; cables inside')
    add('knee_crank', crank(S, cr), 'pa6-cf', f'printed PA6-CF flat, {CRANK_T:.0f} mm; 8 x M5 into the knee adapter; M8 bolt for the rod end')
    add('wheel_adapter', wheel_adapter(S, b).translate((0, 0, -a)), 'pa6-cf', f"printed PA6-CF flat, {STD['WH']['plate_t']:.0f} mm", fea='pa6_cf_z')
    bought = {
        'posts': posts(S),
        'pushrod': pushrod(S, a, cr),
        'hip_motor': gmi.place(gmi.motor_body(hip_id)[0], (0, S.y['hip_out'], 0), (0, 1, 0)),
        'knee_motor': gmi.place(gmi.motor_body(knee_id)[0], (0, S.y['knee_out'], 0), (0, -1, 0)),
        'wheel': _ycyl((S.wheel['od'] or 171) / 2, *S.y['wheel'], 0, -a - b).cut(_ycyl(30, S.y['wheel'][0] - 1, S.y['wheel'][1] + 1, 0, -a - b))
                 .union(_ycyl(25, S.y['wheel_mount'], S.y['wheel'][0], 0, -a - b)),
    }
    assumed = sorted({m['id'] for m in (S.hip, S.knee, S.wheel) if m['assumed']})
    return parts, meta, bought, S, assumed


ROTATES = {'thigh': 'hip', 'hip_output_adapter': 'hip', 'shin': 'knee', 'wheel_adapter': 'knee', 'wheel': 'knee',
           'knee_crank': 'crank', 'knee_output_adapter': 'crank', 'pushrod': 'rod'}


def pose(shape, part: str, hip_rad: float, knee_rad: float, a: float, crank_r: float):
    """Turn a left-leg part from the zero pose: + hip swings the thigh forward (about +y, x towards -z... i.e. the
    right-hand rule about +y), + knee folds the shin about the knee pin. The crank turns by hip + knee (parallelogram),
    and the push-rod translates with it, staying parallel to the thigh."""
    deg = math.degrees
    kind = ROTATES.get(part)
    if kind == 'hip':
        return shape.rotate((0, 0, 0), (0, 1, 0), deg(hip_rad))
    if kind == 'knee':
        return shape.rotate((0, 0, -a), (0, 1, -a), deg(knee_rad)).rotate((0, 0, 0), (0, 1, 0), deg(hip_rad))
    if kind == 'crank':
        return shape.rotate((0, 0, 0), (0, 1, 0), deg(hip_rad + knee_rad))
    if kind == 'rod':
        th = hip_rad + knee_rad                     # the crank pin turns by this; the rod stays parallel to the thigh
        x0, z0 = lever_pin(crank_r)
        px, pz = x0 * math.cos(th) + z0 * math.sin(th), -x0 * math.sin(th) + z0 * math.cos(th)
        s = shape.translate((px - x0, 0, pz - z0))
        return s.rotate((px, 0, pz), (px, 1, pz), deg(hip_rad))
    return shape


def clashes_for_design(design_file: str, heights=(0.0, 0.5, 1.0), min_mm3: float = 10.0):
    """Pairs of leg parts that overlap by more than min_mm3 at three heights from crouch to stand (the motors as
    envelopes, or the vendor STEP where it is on this machine). Returns [[part, part, mm3, height], ...]."""
    import itertools
    import subprocess as sp
    from sim.controller import hip_for, knee_for
    R = Path(__file__).resolve().parents[1]
    d = json.loads((R / design_file if not Path(design_file).is_absolute() else Path(design_file)).read_text())
    L = json.loads(sp.run(['node', str(R / 'tools/derive.mjs'), str(R / design_file)], capture_output=True, text=True, check=True).stdout)['layout']
    parts, meta, bought, S, _ = leg_parts(L, d['parts']['leg_actuator'], d['parts']['leg_actuator'], d['parts']['wheel_motor'])
    a, b = L['thigh'] / 1000, L['shin'] / 1000
    lo, hi = math.radians(L['kneeMinDeg']), math.radians(L['kneeMaxDeg'])
    hmin, hmax = (math.sqrt(a * a + b * b - 2 * a * b * math.cos(g)) for g in (lo, hi))
    out = []
    allp = {**parts, **bought}
    for i, frac in enumerate(heights):
        h = hmin + (hmax - hmin) * frac
        hip, knee = hip_for(a, b, h), knee_for(a, b, h) - math.pi
        placed = {n: pose(sh, n, hip, knee, L['thigh'], PARAMS['crank_r']) for n, sh in allp.items()}
        boxes = {n: s.val().BoundingBox() for n, s in placed.items()}
        for (n1, s1), (n2, s2) in itertools.combinations(placed.items(), 2):
            if i > 0 and n1 not in ROTATES and n2 not in ROTATES:
                continue                                   # two fixed parts: checked once is enough
            b1, b2 = boxes[n1], boxes[n2]
            if b1.xmax < b2.xmin or b2.xmax < b1.xmin or b1.ymax < b2.ymin or b2.ymax < b1.ymin or b1.zmax < b2.zmin or b2.zmax < b1.zmin:
                continue                                   # bounding boxes apart: no overlap possible
            try:
                v = s1.intersect(s2).val().Volume()
            except Exception:
                v = 0.0
            if v > min_mm3:
                out.append([n1, n2, round(v), frac])
    return out
