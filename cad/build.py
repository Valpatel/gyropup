"""Gyropup printed parts in CadQuery, from a design file.

    python cad/build.py [designs/default.json]

Link lengths, wheel size, motor size and the body/tray size come from the designer's layout (tools/derive.mjs), so
every design gets parts that fit it. Interfaces are in cad/parameters.json (values marked ASSUMED need checking).

Frame: x forward, y left, z up, origin on the hip axis (the same as the physics model). STEP files are in that frame
at the standing pose; STL files are in print orientation on z = 0. Writes exports/<part>.step/.stl,
exports/geometry-checks.json (the cad-agent parts file) and exports/mass-properties.json (CAD masses for sim/model.py).

Parts, per side where marked (x2):
  tray            battery tray and hip frame: hangs under the J501 box on its four stacking standoffs, holds the
                  FLEXVOLT pack(s) in their adapters (strapped), carries the hip yokes, face, cameras and the lidar
  hip_yoke  x2    C-yoke on the tray side: hip motor inboard, knee motor outboard, coaxial (Diablo layout)
  thigh     x2    bolts to the hip motor output; knee pivot at the far end
  shin      x2    knee bearings, a push-rod lever, and the BotWheel flange at the bottom
  knee_crank x2   on the knee motor output; drives the shin through the push-rod (a parallelogram four-bar)
  pushrod   x2    two 625 bearings, centres one thigh-length apart
  head_saddle     open frame on the J501 lid screws, raising the turret ring above the cooler grille
  face            eye window (DualEye LCD) and two headlight bosses, on the tray front
  camera_cradle x2  holds a D415 or D435 on its 1/4-20, front and rear
  lidar_hanger    holds the VLP-16 under the waist
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import cadquery as cq

from cadagent.geometry import export_print_stl, solid_report
from cadagent.robot import printed_part_body

R = Path(__file__).resolve().parents[1]
P = json.loads((R / 'cad/parameters.json').read_text())
OUT = R / 'exports'


def derive(design_path: Path) -> dict:
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design_path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# --------------------------------------------------------------------------- helpers

def bolt_circle(pcd, n, angle0=0.0):
    return [(pcd / 2 * math.cos(angle0 + 2 * math.pi * k / n), pcd / 2 * math.sin(angle0 + 2 * math.pi * k / n)) for k in range(n)]


def side_plate(profile: cq.Workplane) -> cq.Workplane:
    return profile


def link_xz(length, width, thick, end_r_top, end_r_bot, slot=True):
    """A link in the XZ plane (sagittal), thickness along y, centred on y = 0, from (0,0) down to (0,-length)."""
    wp = cq.Workplane('XZ')
    body = (wp.circle(end_r_top).extrude(thick / 2, both=True)
            .union(wp.center(0, -length).circle(end_r_bot).extrude(thick / 2, both=True))
            .union(wp.center(0, -length / 2).rect(width, length).extrude(thick / 2, both=True)))
    if slot and length > 2.4 * (end_r_top + end_r_bot):
        s_len = length - 1.2 * (end_r_top + end_r_bot)
        body = body.cut(cq.Workplane('XZ').center(0, -length / 2).slot2D(s_len, width * 0.36, angle=90).extrude(thick, both=True))
    return body


def holes_xz(body, pts, d, depth=None):
    """Through (or blind) holes along y at XZ points."""
    for (x, z) in pts:
        cyl = cq.Workplane('XZ').center(x, z).circle(d / 2).extrude(depth / 2 if depth else 200, both=True)
        body = body.cut(cyl)
    return body


# --------------------------------------------------------------------------- parts

def thigh(L):
    t, w = P['links']['thigh_thickness'], P['links']['thigh_width']
    hub_r = P['links']['hub_d'] / 2
    b = link_xz(L['thigh'], w, t, hub_r, 22.0)
    rs = P['rs03']
    b = holes_xz(b, bolt_circle(rs['output_pcd'], rs['output_holes']), 4.5)
    b = holes_xz(b, [(0, 0)], rs['output_pilot'] + 0.5)
    b = holes_xz(b, [(0, -L['thigh'])], P['knee']['pin_d'] + 0.3)
    return b


def shin(L):
    t, w = P['links']['shin_thickness'], P['links']['shin_width']
    k = P['knee']
    b = link_xz(L['shin'], w, t, 24.0, 36.0)
    lever_r = P['pushrod']['crank_r']
    # push-rod lever: a boss one crank radius forward of the knee, joined to the knee hub
    lever = (cq.Workplane('XZ').center(lever_r / 2, 0).rect(lever_r, 18).extrude(t / 2, both=True)
             .union(cq.Workplane('XZ').center(lever_r, 0).circle(11).extrude(t / 2, both=True)))
    b = b.union(lever)
    b = holes_xz(b, [(lever_r, 0)], 5.2)
    # two 6000 bearings, pressed in from each face, with a web between them (XZ extrudes along -y)
    r_b = k['bearing_od'] / 2 + 0.05
    b = b.cut(cq.Workplane('XZ', origin=(0, t / 2, 0)).circle(r_b).extrude(k['bearing_w']))
    b = b.cut(cq.Workplane('XZ', origin=(0, -t / 2, 0)).circle(r_b).extrude(-k['bearing_w']))
    b = holes_xz(b, [(0, 0)], 12.0)
    # BotWheel flange at the bottom: 4x M6 on the PCD, cable hole
    bw = P['botwheel']
    pts = [(x, z - L['shin']) for x, z in bolt_circle(bw['pcd'], bw['holes'], math.pi / 4)]
    b = holes_xz(b, pts, 6.4)
    b = holes_xz(b, [(0, -L['shin'])], bw['cable_hole'])
    return b


def knee_crank():
    rs = P['rs03']
    r = P['pushrod']['crank_r']
    b = (cq.Workplane('XZ').circle(28).extrude(5, both=True)
         .union(cq.Workplane('XZ').center(r / 2, 0).rect(r, 20).extrude(5, both=True))
         .union(cq.Workplane('XZ').center(r, 0).circle(11).extrude(5, both=True)))
    b = holes_xz(b, bolt_circle(rs['output_pcd'], rs['output_holes']), 4.5)
    b = holes_xz(b, [(0, 0)], rs['output_pilot'] + 0.5)
    return holes_xz(b, [(r, 0)], 5.2)


def pushrod(L):
    pr = P['pushrod']
    c = L['thigh']
    b = (cq.Workplane('XZ').circle(12).extrude(4, both=True)
         .union(cq.Workplane('XZ').center(0, -c).circle(12).extrude(4, both=True))
         .union(cq.Workplane('XZ').center(0, -c / 2).rect(14, c).extrude(4, both=True)))
    return holes_xz(b, [(0, 0), (0, -c)], pr['bearing_od'] + 0.05)


def hip_yoke(L):
    """C-yoke, left side, in the robot frame: inner plate on the tray wall, hip motor outboard of it, thigh hub, crank,
    knee motor, outer plate; a bridge over the top joins the plates."""
    y_p = P['yoke']
    rs = P['rs03']
    ml, md = L['motorL'], L['motorD']
    tray_half = L['tray']['width'] / 2
    pt = y_p['plate_t']
    y_in = tray_half                                     # inner plate's inner face on the tray wall
    y_hip_motor = y_in + pt                              # hip motor case face
    y_crank_end = y_hip_motor + ml + 3 + P['links']['hub_t'] + 2 + 10 + 2
    y_out = y_crank_end + ml                             # outer plate inner face
    size = y_p['plate_size']
    top = 62.0 + 10.0
    plate = lambda y0: (cq.Workplane('XZ', origin=(0, y0, 0)).center(0, 8).rect(size, size + 16).extrude(-pt))
    inner = plate(y_in + pt)
    outer = plate(y_out + pt)
    bridge = cq.Workplane('XY').box(80, (y_out + pt) - y_in, y_p['bridge_t']).translate((0, (y_in + y_out + pt) / 2, top))
    yoke = inner.union(outer).union(bridge)
    for y0 in (y_in, y_out):
        for (x, z) in bolt_circle(rs['case_pcd'], rs['case_holes'], math.pi / 8):
            yoke = yoke.cut(cq.Workplane('XZ', origin=(0, y0 + pt + 1, 0)).center(x, z).circle(2.25).extrude(pt + 2))
        yoke = yoke.cut(cq.Workplane('XZ', origin=(0, y0 + pt + 1, 0)).circle(22).extrude(pt + 2))
    # tray bolts (4x M5) through the inner plate
    for (x, z) in [(-45, 35), (45, 35), (-45, 62), (45, 62)]:
        yoke = yoke.cut(cq.Workplane('XZ', origin=(0, y_in + pt + 1, 0)).center(x, z).circle(2.75).extrude(pt + 2))
    return yoke, {'y_in': y_in, 'y_out': y_out + pt, 'leg_y': y_hip_motor + ml + 3 + P['links']['hub_t'] / 2,
                  'crank_y': y_hip_motor + ml + 3 + P['links']['hub_t'] + 2 + 5}


def tray(L):
    T = L['tray']
    W, D, H = T['width'], T['depth'], T['height']
    tp = P['tray']
    z0 = L['trayBottom']
    outer = cq.Workplane('XY').box(D, W, H).translate((0, 0, z0 + H / 2)).edges('|Z').fillet(10)
    inner = cq.Workplane('XY').box(D - 2 * tp['wall'], W - 2 * tp['wall'], H).translate((0, 0, z0 + tp['floor'] + H / 2)).edges('|Z').fillet(7)
    t = outer.cut(inner)
    n = (L.get('battery') or {}).get('packs', 1)
    for k in range(1, n):                      # dividers between packs
        y = k * W / n - W / 2
        t = t.union(cq.Workplane('XY').box(D - 2 * tp['wall'], tp['wall'], H - 20).translate((0, y, z0 + (H - 20) / 2)))
    # stacking columns under the J501 box's feet (M3 standoffs), J501 frame centred on the tray
    jb = P['j501_box']
    for (jx, jy) in jb['standoff_centers']:
        x = (jb['depth'] / 2 - jy)            # J501 y runs front to back; our x is forward
        y = (jx - jb['width'] / 2)
        col = cq.Workplane('XY').circle(6.5).extrude(H).translate((x, y, z0))
        t = t.union(col).cut(cq.Workplane('XY').circle(1.7).extrude(H + 2).translate((x, y, z0 - 1)))
    # strap slots in the floor, two per pack
    sw, sl = tp['strap_slot']
    for sy in [(k + 0.5) * W / n - W / 2 for k in range(n)]:
        for sx in (-D / 4, D / 4):
            t = t.cut(cq.Workplane('XY').box(sl, sw, 20).translate((sx, sy, z0)))
    # hip yoke bolt inserts (M5) in both side walls
    for side in (1, -1):
        for (x, z) in [(-45, 35), (45, 35), (-45, 62), (45, 62)]:
            t = t.cut(cq.Workplane('XZ', origin=(0, side * W / 2 + side * 1, 0)).center(x, z).circle(P['print']['insert_m5_pilot'] / 2)
                      .extrude(-side * 10))
    # front: face and front camera; back: rear camera (M4 inserts); bottom: lidar hanger (M4 inserts)
    for xs, pts in ((D / 2, [(-45, 20), (45, 20), (-45, 60), (45, 60)]), (-D / 2, [(-20, 12), (20, 12)])):
        for (y, z) in pts:
            t = t.cut(cq.Workplane('YZ', origin=(xs + math.copysign(1, xs), 0, 0)).center(y, z0 + z).circle(2.8)
                      .extrude(-math.copysign(10, xs)))
    for (x, y) in [(-30, -30), (30, -30), (-30, 30), (30, 30)]:
        t = t.cut(cq.Workplane('XY').circle(2.8).extrude(10).translate((x, y, z0 - 1)))
    t = t.cut(cq.Workplane('XY').circle(3.4).extrude(10).translate((0, 0, z0 - 1)))   # lidar cable
    return t


def head_saddle(L):
    """Open frame on the J501 lid screws; turret ring raised 20 mm so the cooler grille keeps breathing."""
    jb = P['j501_box']
    top = L['bodyTop']
    t = 6.0
    ring_z = top + 20
    rails = cq.Workplane('XY')
    pts = [((jb['depth'] / 2 - jy), (jx - jb['width'] / 2)) for jx, jy in jb['standoff_centers']]
    frame = None
    for (x, y) in pts:
        dist, ang = math.hypot(x, y), math.degrees(math.atan2(y, x))
        arm = cq.Workplane('XY').box(dist, 14, t).translate((dist / 2, 0, t / 2)).rotate((0, 0, 0), (0, 0, 1), ang).translate((0, 0, top))
        foot = cq.Workplane('XY').circle(9).extrude(t).translate((x, y, top))
        frame = arm.union(foot) if frame is None else frame.union(arm).union(foot)
    ring = cq.Workplane('XY').circle(57).circle(30).extrude(t).translate((0, 0, ring_z))
    legs = None
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        leg = cq.Workplane('XY').circle(6).extrude(ring_z - top).translate((44 * math.cos(a), 44 * math.sin(a), top))
        legs = leg if legs is None else legs.union(leg)
    s = frame.union(legs).union(ring)
    for (x, y) in pts:
        s = s.cut(cq.Workplane('XY').circle(1.7).extrude(30).translate((x, y, top - 5)))
    for (x, y) in [(40, 40), (40, -40), (-40, 40), (-40, -40)]:
        s = s.cut(cq.Workplane('XY').circle(P['print']['insert_m4_pilot'] / 2).extrude(t + 2).translate((x * 0.71, y * 0.71, ring_z - 1)))
    return s


def face(L):
    """Eye window and headlight bosses, bolted to the tray front."""
    D = L['tray']['depth']
    z0 = L['trayBottom']
    plate = cq.Workplane('YZ').center(0, z0 + 40).rect(140, 76).extrude(5).translate((D / 2, 0, 0)).edges('|X').fillet(8)
    plate = plate.cut(cq.Workplane('YZ').center(0, z0 + 60).rect(53, 22).extrude(10).translate((D / 2 - 1, 0, 0)))         # DualEye
    for y in (-50, 50):
        boss = cq.Workplane('YZ').center(y, z0 + 30).circle(14).extrude(14).translate((D / 2, 0, 0))
        plate = plate.union(boss).cut(cq.Workplane('YZ').center(y, z0 + 30).circle(4.2).extrude(30).translate((D / 2 - 1, 0, 0)))  # M8 pod bolt
    for (y, z) in [(-45, 20), (45, 20), (-45, 60), (45, 60)]:
        plate = plate.cut(cq.Workplane('YZ').center(y, z0 + z).circle(2.25).extrude(20).translate((D / 2 - 1, 0, 0)))
    return plate


def camera_cradle(L, front=True):
    D = L['tray']['depth']
    z0 = L['trayBottom']
    sgn = 1 if front else -1
    w, h, d = P['camera']['d435']
    base = cq.Workplane('XY').box(30, w + 16, 5).translate((sgn * (D / 2 + 17), 0, z0 + 2.5))
    back = cq.Workplane('XY').box(5, 60, 30).translate((sgn * (D / 2 + 2.5), 0, z0 + 15))
    lip = cq.Workplane('XY').box(4, w + 16, 12).translate((sgn * (D / 2 + 33), 0, z0 + 6))
    c = base.union(back).union(lip)
    c = c.cut(cq.Workplane('XY').circle(3.4).extrude(10).translate((sgn * (D / 2 + 17), 0, z0 - 1)))      # 1/4-20
    for y in (-20, 20):
        c = c.cut(cq.Workplane('YZ').center(y, z0 + 12).circle(2.25).extrude(20).translate((sgn * (D / 2 - 5), 0, 0)))
    return c


def lidar_hanger(L):
    z0 = L['trayBottom']
    lp = P['lidar']
    disc = cq.Workplane('XY').circle(52).extrude(8).translate((0, 0, z0 - 8))
    disc = disc.cut(cq.Workplane('XY').circle(3.4).extrude(20).translate((0, 0, z0 - 15)))
    for x in (-lp['pin_spacing'] / 2, lp['pin_spacing'] / 2):
        disc = disc.cut(cq.Workplane('XY').circle(lp['pin_d'] / 2).extrude(5).translate((x, 12, z0 - 8.5)))
    for (x, y) in [(-30, -30), (30, -30), (-30, 30), (30, 30)]:
        disc = disc.cut(cq.Workplane('XY').circle(2.25).extrude(20).translate((x, y, z0 - 15)))
    disc = disc.cut(cq.Workplane('XY').rect(10, 40).extrude(20).translate((0, -32, z0 - 15)))             # cable notch
    return disc


# --------------------------------------------------------------------------- assembly and export

def build(design_path: Path):
    ev = derive(design_path)
    L = ev['layout']
    yoke, Y = hip_yoke(L)
    hip_t = math.radians(0)
    # standing pose for the assembly: wheel under the hip at 60 % height
    a, b = L['thigh'], L['shin']
    lo, hi = math.radians(L['kneeMinDeg']), math.radians(L['kneeMaxDeg'])
    h = lambda g: math.sqrt(a * a + b * b - 2 * a * b * math.cos(g))
    hh = h(lo) + 0.6 * (h(hi) - h(lo))
    gamma = math.acos((a * a + b * b - hh * hh) / (2 * a * b))
    alpha = math.acos((a * a + hh * hh - b * b) / (2 * a * hh))
    knee_q = gamma - math.pi

    def place_leg(shape, side, y, rot_deg, at=(0, 0, 0)):
        s = shape.rotate((0, 0, 0), (0, 1, 0), rot_deg).translate((at[0], side * y, at[2]))
        return s

    parts, placed = {}, {}
    parts['tray'] = tray(L)
    for side, tag in ((1, 'l'), (-1, 'r')):
        yk = yoke if side == 1 else yoke.mirror('XZ')
        placed[f'hip_yoke_{tag}'] = yk
    parts['hip_yoke'] = yoke
    parts['thigh'] = thigh(L)
    parts['shin'] = shin(L)
    parts['knee_crank'] = knee_crank()
    parts['pushrod'] = pushrod(L)
    parts['head_saddle'] = head_saddle(L)
    parts['face'] = face(L)
    parts['camera_cradle'] = camera_cradle(L, True)
    parts['lidar_hanger'] = lidar_hanger(L)
    # legs at the standing pose (rotation about +y: thigh back by alpha; shin forward by knee_q)
    kx, kz = -a * math.sin(alpha), -a * math.cos(alpha)
    for side, tag in ((1, 'l'), (-1, 'r')):
        placed[f'thigh_{tag}'] = place_leg(parts['thigh'], side, Y['leg_y'], math.degrees(alpha))
        sh = parts['shin'].rotate((0, 0, 0), (0, 1, 0), math.degrees(alpha + knee_q)).translate((kx, side * (Y['leg_y'] + 20), kz))
        placed[f'shin_{tag}'] = sh
        placed[f'knee_crank_{tag}'] = place_leg(parts['knee_crank'], side, Y['crank_y'], 0)
    placed['tray'] = parts['tray']
    placed['head_saddle'] = parts['head_saddle']
    placed['face'] = parts['face']
    placed['camera_cradle_front'] = parts['camera_cradle']
    placed['camera_cradle_rear'] = camera_cradle(L, False)
    placed['lidar_hanger'] = parts['lidar_hanger']

    # print orientation: largest flat face down
    rot = {'thigh': ((1, 0, 0), 90), 'shin': ((1, 0, 0), 90), 'knee_crank': ((1, 0, 0), 90), 'pushrod': ((1, 0, 0), 90),
           'hip_yoke': ((1, 0, 0), -90), 'face': ((0, 1, 0), 90), 'head_saddle': ((1, 0, 0), 180), 'lidar_hanger': ((1, 0, 0), 180),
           'camera_cradle': None, 'tray': None}
    qty = {'thigh': 2, 'shin': 2, 'knee_crank': 2, 'pushrod': 2, 'hip_yoke': 2, 'camera_cradle': 2}
    materials = json.loads((R / 'catalog/materials.json').read_text())
    hot = {'hip_yoke', 'knee_crank'}         # touch the motor cases: PETG
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob('asm_*.step'):          # parts from an earlier design (e.g. a second battery) must not linger
        old.unlink()
    report, mass = {}, {}
    diagonal = {'thigh', 'shin', 'pushrod'}   # longer than the bed: print them corner to corner
    for name, shape in parts.items():
        solid = shape.val() if hasattr(shape, 'val') else shape
        cq.exporters.export(solid, str(OUT / f'{name}.step'))
        printable = solid.rotate((0, 0, 0), (0, 1, 0), 45) if name in diagonal else solid
        rep = export_print_stl(printable, OUT / f'{name}.stl', rotation=rot.get(name))
        rep.update(qty=qty.get(name, 1))
        report[name] = rep
        mat = 'petg' if name in hot else 'pla'
        body, mrep = printed_part_body(solid, materials[mat]['density_g_cm3'], wall_mm=2.0, infill=0.4, name=name)
        mass[name] = {**mrep, 'material': mat, 'qty': qty.get(name, 1), 'com_m': list(body.com)}
    # bought parts as simple envelopes at their real positions, so the assembly view shows the whole robot
    T, B = L['tray'], L['body']
    bought = {}
    bought['j501_box'] = cq.Workplane('XY').box(B['depth'], B['width'], B['height']).edges().fillet(6).translate((0, 0, L['bodyBottom'] + B['height'] / 2))
    if L.get('battery'):
        n, (bl, bw, bh) = L['battery']['packs'], L['battery']['dims']
        for i in range(n):
            y = (i + 0.5) * T['width'] / n - T['width'] / 2
            bought[f'battery_{i + 1}'] = cq.Workplane('XY').box(bl, bw, bh).edges('|X').fillet(8).translate((0, y, L['trayBottom'] + 6 + bh / 2))
    for side, tag in ((1, 'l'), (-1, 'r')):
        y0 = Y['y_in'] + P['yoke']['plate_t']
        bought[f'hip_motor_{tag}'] = cq.Workplane('XZ').circle(L['motorD'] / 2).extrude(-L['motorL']).translate((0, side * y0 if side > 0 else 0, 0)) if side > 0 else \
            cq.Workplane('XZ').circle(L['motorD'] / 2).extrude(L['motorL']).translate((0, -y0, 0))
        yk = Y['y_out'] - P['yoke']['plate_t']
        bought[f'knee_motor_{tag}'] = cq.Workplane('XZ').circle(L['motorD'] / 2).extrude(L['motorL']).translate((0, side * yk if side > 0 else 0, 0)) if side > 0 else \
            cq.Workplane('XZ').circle(L['motorD'] / 2).extrude(-L['motorL']).translate((0, -yk, 0))
        wy = side * (Y['leg_y'] + 20 + P['links']['shin_thickness'] / 2 + L['wheelW'] / 2)
        bought[f'wheel_{tag}'] = cq.Workplane('XZ').circle(L['wheelR']).circle(L['wheelR'] * 0.3).extrude(L['wheelW'] / 2, both=True).translate((0, wy, -hh))
    lz = L['trayBottom'] - 8 - 36
    bought['lidar'] = cq.Workplane('XY').circle(51.65).extrude(71.7).translate((0, 0, lz - 36))
    for name, x in (('camera_front', T['depth'] / 2 + 17), ('camera_rear', -(T['depth'] / 2 + 17))):
        bought[name] = cq.Workplane('XY').box(25, 90, 25).translate((x, 0, L['trayBottom'] + 5 + 12.5))
    for name, shape in bought.items():
        cq.exporters.export(shape.val(), str(OUT / f'asm_{name}.step'))

    # the assembly at the standing pose, for the 3D viewer and review
    asm = cq.Assembly()
    for name, shape in placed.items():
        asm.add(shape, name=name)
    asm.save(str(OUT / 'assembly.step'))
    for name, shape in placed.items():
        cq.exporters.export(shape.val() if hasattr(shape, 'val') else shape, str(OUT / f'asm_{name}.step'))
    (OUT / 'geometry-checks.json').write_text(json.dumps(report, indent=1) + '\n')
    total = sum(m['mass_g'] * m['qty'] for m in mass.values())
    (OUT / 'mass-properties.json').write_text(json.dumps({'design': str(Path(design_path).resolve().relative_to(R)), 'parts': mass,
                                                          'printed_total_g': round(total, 1), 'estimate': True,
                                                          'note': 'printed at 2 mm walls and 40 % infill; weigh the real parts'}, indent=1) + '\n')
    print(f"{len(parts)} part types, {sum(qty.get(n, 1) for n in parts)} printed parts, {total:.0f} g of filament (estimate)")
    for name, rep in report.items():
        print(f"  {name:14} x{rep['qty']}  {rep['print_bounds_mm']}  valid={rep['cad_valid']} solids={rep['solid_count']} watertight={rep['watertight']}")
    return report


if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else R / 'designs/default.json')
