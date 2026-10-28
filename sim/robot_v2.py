"""Gyropup v2 for the physics and the 3D game page: two five-bar legs (cad/fivebar.py), the foam-ball turret
(cad/turret.py) and the REAL BODY of milestone M5 (cad/body_*.py), as built (D62).

    python -m sim.robot_v2        # build/sim/v2/robot.xml + model.json; exports/sim/v2/rig/ (meshes + manifest.json)

Robot frame: x forward, y left, z up, origin on the hip axis between the two legs. The left leg is cad/fivebar.py's
module as built, its frame shifted out by the body's Y_OFF (cad/body_params.py: its centre-plane face on the left
cheek, the spine 40.5 mm wide); the right leg is its mirror image. Every leg joint is a hinge about the robot's y axis,
so the leg kinematics in the x-z plane are the same on both sides. Each five-bar is closed by an equality constraint at
the wheel axle (as sim/leg_rig.py); the TPU stops are spring torques in the controller (sim/controller_v2.py); the
RS-04s carry their reflected rotor inertia; the motors' speeds are the 10S pair's at its 36 V nominal (BUS_V, D65).

The body is cad/body_layout.py's P3 ledger, row for row (every mass and centre the body's own build writes to
exports/body/mass.json): the frame parts from their CAD solids (inertia included), each bought part as its box, the
estimates (harness, hardware, the shell's panels) where the ledger puts them; the legs carry exports/leg/leg.json's
total; the turret's moving groups come from cad/turret.py and the rest of the head budget (body_params.tm()) sits at
the head's centre, so the model's mass is the ledger's (mass_reconciles). It collides with the ground as the real
parts would: the cheeks, the floor tray, the deck with its lips, the belly plate, the battery bay (the lowest part),
the ear pods and the lidar. On the deck the VLP-16 and the turret's pan axis are where the body puts them (143 mm
apart, the turret on its 30 mm riser); over the lidar the turret's depression is limited by pan (computed here from
the meshes; model.json turret.tilt_max_deg).
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import cadquery as cq  # noqa: E402

import fivebar as fb  # noqa: E402
import gmi  # noqa: E402
from cadagent.robot import Body, combine, cylinder_body, box_body, solid_mass_properties  # noqa: E402
from sim import leg_rig as lr  # noqa: E402

import body_params as bp  # noqa: E402

M = 0.001
OUT_BUILD = R / 'build' / 'sim' / 'v2'
OUT_RIG = R / 'exports' / 'sim' / 'v2' / 'rig'
DESIGN = R / 'designs' / 'default.json'
Y_OFF = bp.y_off()                                  # the left module's y = 0 is the robot's y = Y_OFF (mm): the body's spine
BODY_X = bp.BODY_X                                  # the floor tray and deck (mm)
BUS_V = 36.0                                        # D65: two DCB609 packs in series, 10S, 36 V nominal: the motors' speed lines
GAP = 5.0                                           # kept between the lidar and any part of the turret, at any pan/tilt
EAR = {'size': (61.0, 50.8, 50.8), 'x': (-10.0, 51.0), 'top': 193.0}   # SSC1 pod (x, y, z) on each side wall (docs/body-plan.md 1.9)
TILT_STOP_DEG = 25.0                                # cad/turret.py's hard stops: 0 .. -25 deg (here + = barrel down)
PAN_STOP_DEG = 170.0
REF_H = 300.0                                       # the model's joints are zero standing at this leg length
H_RANGE = (180.0, 375.0)                            # leg length (mm) for the controller's height 0..1. Issue #19: the bay's 45 mm
                                                    # crush pads (cad/body_battery.py PAD) need the lowest height at 180 mm (it was
                                                    # 160) to keep D69's 40 mm under them; they touch the floor under a 140 mm leg
WHEEL_KEY = 'hb10'                                  # D69: sim/wheel_candidates.json's 10 in hub motor, at the ledger's wheel mass
_WHEEL = {}


def use_d69_wheel() -> dict:
    """D69's wheel in place of the BotWheel. sim/leg_rig.py and cad/fivebar.py (the leg core) carry the BotWheel until the
    leg's foot change (issue #25); the body's model puts the 10 in hub motor into their module state before it builds, as
    sim/wheel_study.py does: its motor and pneumatic tyre from sim/wheel_candidates.json, its mass the ledger's
    (cad/body_layout.py wheel_g(), so the model's mass reconciles). Called once, after the ledger is read (the ledger
    places the tyre's band itself)."""
    if _WHEEL:
        return _WHEEL
    import body_layout as bl
    from sim import wheel_study as ws
    w = dict(ws.CANDIDATES[WHEEL_KEY])
    w.update(mass_g=bl.wheel_g(), od_mm=bl.D69_WHEEL['od_mm'], tyre_width_mm=bl.D69_WHEEL['tyre_width_mm'],
             rotor_share=bl.D69_WHEEL['rotor_share'])
    ws.patch_rig(w)
    ws._patch_cad(w)
    _WHEEL.update(w)
    _WHEEL['y_mm'] = fb.Y['wheel_boss'] + 7.5 + w['tyre_width_mm'] / 2      # the tyre's centre plane (left module frame)
    return _WHEEL


def pads():
    """The battery bay's crush pads (issue #19; cad/body_battery.py PAD): [(name, box mm)], and the pad's numbers."""
    import body_battery as bb
    return [(f'pad_{i + 1}', b) for i, b in enumerate(bb.pad_boxes())], dict(bb.PAD)
COLORS = {'body': '#9fb4c7', 'frame': '#5f6670', 'motor': '#2a2d33', 'link': '#f5b82e', 'wheel_link': '#e9a21f',
          'adapter': '#c9ced6', 'tyre': '#1b1d21', 'hub': '#4a5058', 'battery': '#fdb913', 'compute': '#5a6b7c',
          'driver': '#2b6cb0', 'power': '#8f9aa7', 'lidar': '#2a2d33', 'camera': '#2a2d33', 'light': '#3a3f47',
          'turret': '#4a5058', 'barrel': '#ff6a13', 'hopper': '#9cc7e8'}


def lidar_spec():
    """The VLP-16 from catalog/sensors_compute.json: size, optical centre, vertical field of view, mass."""
    cat = json.loads((R / 'catalog/sensors_compute.json').read_text())
    s = next(c for c in cat if c['id'] == 'velodyne-vlp-16')['specs']
    return {'d': s['diameter_mm'], 'h': s['height_mm'], 'oc': s['optical_center_above_base_mm'], 'fov_v': s['fov_v_deg'],
            'mass_g': s['mass_g'], 'gland': 12.7,          # the datasheet's cable gland: <= 12.7 mm out, centred <= 12.7 up
            'mounting': s['mounting']}


# ----------------------------------------------------------------------------------- meshes as numbers

_STL = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def stl_tris(path):
    """An STL file's triangles, (n, 3, 3) in its units."""
    b = Path(path).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    if len(b) == 84 + 50 * n:
        return np.frombuffer(b[84:], dtype=_STL)['v'].astype(float)
    v = [list(map(float, l.split()[1:4])) for l in b.decode().splitlines() if l.strip().startswith('vertex')]
    return np.array(v).reshape(-1, 3, 3)


def stl_shift(path, d):
    """Move an STL file's mesh by d (binary out)."""
    t = stl_tris(path) + np.asarray(d, float)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    a = np.zeros(len(t), dtype=_STL)
    a['n'], a['v'] = n, t
    Path(path).write_bytes(b'gyropup v2 rig'.ljust(80, b' ') + struct.pack('<I', len(t)) + a.tobytes())


def surface_points(tris, step=6.0, grid=2.0):
    """Points on a mesh's surface no more than about `step` apart: its vertices and the centres of its triangles cut
    in half across their longest edge until no edge is longer than `step`; one point per `grid` mm cell."""
    out = [tris.reshape(-1, 3)]
    for _ in range(24):
        e = np.linalg.norm(tris - np.roll(tris, -1, axis=1), axis=2)          # edge k runs from corner k to k + 1
        k = e.argmax(axis=1)
        big = e[np.arange(len(tris)), k] > step
        out.append(tris[~big].mean(axis=1))
        tris = tris[big]
        if not len(tris):
            break
        k = k[big]
        i = np.arange(len(tris))
        a, b, c = tris[i, k], tris[i, (k + 1) % 3], tris[i, (k + 2) % 3]
        m = (a + b) / 2
        out.append(m)
        tris = np.concatenate([np.stack([a, m, c], axis=1), np.stack([m, b, c], axis=1)])
    return np.unique(np.round(np.concatenate(out) / grid) * grid, axis=0)


# ----------------------------------------------------------------------------------- the real body (M5)

def _hex(rgb):
    return '#' + ''.join(f'{int(round(255 * max(0.0, min(1.0, c)))):02x}' for c in rgb)


def ear_boxes():
    """The two SSC1 pods on their brackets (cad/body_shell.py): [(name, (x0, x1, y0, y1, z0, z1))]."""
    import body_shell as bs3
    out = []
    for side in ('l', 'r'):
        b = bs3._v(bs3.ear_pod(side)).BoundingBox()
        out.append((f'ear_{side}', (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)))
    return out


def real_body():
    """The body as cad/body_*.py builds it: the layout's items, the frame parts, the P3 ledger, and the boxes the model
    collides with. {'L', 'parts', 'ledger', 'collide': [(name, box)], 'B', 'bay'}"""
    import body_battery as bb
    import body_frame as bf
    import body_layout as bl
    import body_shell as bs3
    L = bl.layout()
    parts = {n: p for n, p in bf.all_parts(L['mounts']).items() if bf.on_robot(p, 'P3')}     # the robot as P3 builds it
    led = bl.ledger(L, parts, stage='P3')
    zt, zs = bp.z_tray_top(), bf.ZT
    tg = bb.geometry()
    tb, db, be = bp.STOCK[bp.TRAY]['t'], bp.STOCK[bp.DECK]['t'], bp.STOCK[bp.BELLY]['t']
    X, HY = bp.BODY_X, bp.BODY_HALF_Y
    collide = [
        ('cheek_l', (bp.SPINE_X[0], bp.SPINE_X[1], bf.GAP_Y, bf.GAP_Y + bp.CHEEK_FLANGE, -zs, zs)),
        ('cheek_r', (bp.SPINE_X[0], bp.SPINE_X[1], -bf.GAP_Y - bp.CHEEK_FLANGE, -bf.GAP_Y, -zs, zs)),
        ('floor_tray', (X[0], X[1], -HY, HY, zt - bp.TRAY_LIP, zt)),
        ('deck', (X[0], X[1], -HY, HY, bp.TOP - bp.DECK_LIP, bp.TOP)),
        ('belly_plate', (X[0], X[1], -bp.BELLY_HALF_Y, bp.BELLY_HALF_Y, -zs - be, -zs)),
        ('battery_bay', (tg['x_out'][0], tg['x_out'][1], -tg['side_out'], tg['side_out'], tg['z_floor'], tg['z_belly'])),   # the pads hang under
        ('shell_l', (-bs3.XO, bs3.XO, bs3.YI, bs3.YO, bs3.ZB, bs3.ZT)), ('shell_r', (-bs3.XO, bs3.XO, -bs3.YO, -bs3.YI, bs3.ZB, bs3.ZT)),
        ('shell_front', (bs3.XI, bs3.XO, -bs3.YI, bs3.YI, bs3.APRON['z0'], bs3.ZT)),
        ('shell_rear', (-bs3.XO, -bs3.XI, -bs3.YI, bs3.YI, bs3.APRON['z0'], bs3.ZT)),
    ] + ear_boxes()
    B = {'x': tuple(X), 'y': (-HY, HY), 'z': (round(tg['z_bottom'], 2), bp.TOP)}
    return {'L': L, 'parts': parts, 'ledger': led, 'collide': collide, 'B': B}


def body_bodies(rb, x_p, turret_extra):
    """The base's rigid bodies from the P3 ledger, row for row (SI): frame parts from their solids, items as their
    boxes, everything else a point mass where the ledger puts it; the turret's ledger row is left out (the turret's
    groups and turret_extra stand for it). Returns [Body]."""
    import body_layout as bl
    mats = json.loads((R / 'catalog/materials.json').read_text())
    items = {it.name: it for it in rb['L']['items'] if not it.keepout}
    out = []
    for r in rb['ledger']['rows']:
        if r['group'] == 'legs' or r['name'] == 'turret' or r['name'].startswith('frame.bay_skid_') or r['name'] == 'frame.bay_floor':
            # the pads are bodies of their own, and the bay's floor rides on them in the model (see build())
            continue
        g, c = r['mass_g'] / 1000.0, tuple(v * M for v in r['com_mm'])
        name = r['name']
        pn = name.split('.', 1)[1] if name.startswith(('frame.', 'shell.')) else None
        if pn in rb['parts']:
            p = rb['parts'][pn]
            v = p.shape.val() if hasattr(p.shape, 'val') else p.shape
            dens = (next(st['density'] for st in bp.STOCK.values() if st['material'] == p.material) if p.kind == 'sheet'
                    else mats[p.material]['density_g_cm3'])
            b = solid_mass_properties(v, dens, 1.0, name)
            out.append(Body(g, b.com, b.inertia, name))           # the ledger's mass, the solid's centre and inertia
        elif name in items and not items[name].cyl:
            x0, x1, y0, y1, z0, z1 = items[name].box
            out.append(box_body(g, ((x1 - x0) * M, (y1 - y0) * M, (z1 - z0) * M), center=c, name=name))
        elif name in items:
            cx, cy, rr = items[name].cyl
            z0, z1 = items[name].box[4:]
            out.append(cylinder_body(g, rr * M, (z1 - z0) * M, axis='z', center=c, name=name))
        elif name == 'shell_panels':                              # the shell's walls round the body (a box: an estimate)
            out.append(box_body(g, ((bp.BODY_X[1] - bp.BODY_X[0]) * M, 2 * bp.BODY_HALF_Y * M, 0.3), center=c, name=name))
        else:
            out.append(Body(g, c, name=name))
    if turret_extra[0] > 1e-6:
        out.append(Body(turret_extra[0], turret_extra[1], name='head budget beyond the turret\'s CAD'))
    return out


def lidar_shape(lid, at):
    """The puck on the deck (its base at `at`), with its cable gland out to the left (+y; its 0 deg axis), clear of
    the turret behind it; the two locating pins then lie fore and aft."""
    x, y, z = at
    puck = cq.Workplane('XY').workplane(offset=z).center(x, y).circle(lid['d'] / 2).extrude(lid['h'])
    gland = (cq.Workplane('XZ').workplane(offset=-(y + lid['d'] / 2 - 2.0)).center(x, z + lid['gland'])
             .circle(8.0).extrude(-(lid['gland'] + 2.0)))
    return puck.union(gland)


# ----------------------------------------------------------------------------------- mass properties

def leg_bodies():
    """Each moving group of the LEFT leg in its own link frame (SI), from the CAD solids plus datasheet masses."""
    dens = json.loads((R / 'catalog/materials.json').read_text())['pa6-cf']['density_g_cm3']
    L = fb.leg_parts()
    sm = lambda name: solid_mass_properties(L.parts[name].val(), dens, 1.0, name)
    l1, l2 = fb.P['l1'] / 1000, fb.P['l2'] / 1000
    yk = sum(fb.Y['knee_boss']) / 2000
    pin = Body(0.075 + 0.011, (l1, 0.03, 0.0), name='knee pin + nut')            # rides with the upper link
    ad = sm('output_adapter')
    mach = json.loads((R / 'exports/leg/leg.json').read_text())['mass_g'].get('machined_parts', {}).get('output_adapter')
    if mach:                                                      # machined 6061 (D46): its mass, the solid's shape
        k = mach / 1000.0 / ad.mass
        ad = Body(mach / 1000.0, ad.com, tuple(tuple(v * k for v in row) for row in ad.inertia), 'output adapter (machined 6061)')
    upper = combine([sm('upper_link'), ad, Body(8 * 0.006, (0.0, 0.03, 0.0), name='8 x M5'), pin], 'upper')
    knee_brg = Body(2 * 0.037 + 0.006, (0.0, yk, 0.0), name='2 x 6201 + washers')
    n_apex = 2 if 'apex_bearing_in' in fb.Y else 1
    front = combine([sm('front_link'), knee_brg, Body(n_apex * 0.097, (l2, 0.025, 0.0), name=f'{n_apex} x 61812')], 'front')
    w = use_d69_wheel()
    yw = w['y_mm'] / 1000
    stator_kg = lr.WHEEL['mass_g'] / 1000 * (1 - lr.ROTOR_SHARE)
    wheel_link = combine([sm('wheel_link'), knee_brg, Body(stator_kg, (l2, yw, 0.0), name='hub motor stator and shaft (D69)'),
                          Body(4 * 0.011 + 0.010, (l2, 0.05, 0.0), name='the foot\'s clamp screws')], 'wheel_link')
    rotor = cylinder_body(lr.WHEEL['mass_g'] / 1000 * lr.ROTOR_SHARE, lr.WHEEL_R, w['tyre_width_mm'] / 1000, axis='y',
                          hollow_radius=0.6 * lr.WHEEL_R, center=(0.0, yw, 0.0), name='hub motor rotor and tyre (D69)')
    frame = combine([sm('hip_frame'), Body(2 * lr.MOTOR['mass_g'] / 1000, (0.0, (fb.Y['motor'][0] + fb.Y['motor'][1]) / 2000, 0.0), name='2 x RS-04'),
                     Body(2 * 0.097, (0.0, -0.006, 0.0), name='2 x 61812'), Body(4 * 0.03, (0.0, 0.01, 0.0), name='stop posts')], 'hip module')
    return {'upper': upper, 'front': front, 'wheel_link': wheel_link, 'rotor': rotor, 'frame': frame}


def mirror_body(b: Body) -> Body:
    I = b.inertia
    Im = ((I[0][0], -I[0][1], I[0][2]), (-I[1][0], I[1][1], -I[1][2]), (I[2][0], -I[2][1], I[2][2]))
    return Body(b.mass, (b.com[0], -b.com[1], b.com[2]), Im, b.name)


def shift_y(b: Body, dy: float) -> Body:
    return Body(b.mass, (b.com[0], b.com[1] + dy, b.com[2]), b.inertia, b.name)


def shift_x(b: Body, dx: float) -> Body:
    return Body(b.mass, (b.com[0] + dx, b.com[1], b.com[2]), b.inertia, b.name)


def turret_groups(T):
    """The turret's fixed parts, pan link and tilt link as Bodies in the robot frame (SI) with the pan axis on x = 0,
    with the turret's shapes (build() moves both to the pan axis's place on the deck)."""
    import turret as tu
    from cadagent.robot import printed_part_body
    groups = {'base': [], 'pan': [], 'tilt': []}
    shapes = {'base': [], 'pan': [], 'tilt': []}
    frame_group = {'base': 'base', 'pinion': 'base', 'pan': 'pan', 'tilt': 'tilt'}
    for name, m in T.meta.items():
        sh = T.pose_shape(T.local[name], T.frame[name], 0.0, 0.0, robot=True)
        wall, infill = (500.0, 1.0) if m['solid'] else (2.0, 0.4)
        body, _ = printed_part_body(sh.val(), tu.DENS[m['material']], wall_mm=wall, infill=infill, name=name)
        gname = frame_group[T.frame[name]]
        for k in range(m['qty']):
            s = sh if k == 0 else T.pose_shape(T.local[name].mirror('XZ'), T.frame[name], 0.0, 0.0, robot=True)
            b = body if k == 0 else printed_part_body(s.val(), tu.DENS[m['material']], wall_mm=wall, infill=infill, name=name)[0]
            groups[gname].append(b)
            shapes[gname].append((name, s, COLORS['barrel'] if name == 'barrel' else COLORS['hopper'] if name.startswith('hopper') else COLORS['turret']))
    for name, (shape, frame, mass, note) in T.bought.items():
        sh = T.pose_shape(shape, frame, 0.0, 0.0, robot=True)
        gname = frame_group[frame]
        if mass > 0:
            c = cq.Shape.centerOfMass(sh.val())
            groups[gname].append(Body(mass / 1000, (c.x * M, c.y * M, c.z * M), name=name))
        shapes[gname].append((name, sh, COLORS['motor']))
    G = T.G
    groups['tilt'].append(Body(30 * 0.00183, (0.0, 0.0, (T.mount_z + G.path_t + (G.dial_z0 + G.hopper_top) / 2) * M), name='30 balls'))
    groups['pan'].append(Body(sum(tu.NOT_MODELLED_G.values()) / 1000, (0.0, 0.0, (T.mount_z + G.turntable_z[1]) * M), name='turret wiring, MCU, screws'))
    return {k: combine(v, f'turret {k}') for k, v in groups.items()}, shapes


# ----------------------------------------------------------------------------------- the lidar and the turret

def _rot_tilt(p, th):
    """Tilt-frame points (mm) turned by the tilt th (rad, + = barrel down) about the tilt axis (the frame's y)."""
    c, s = math.cos(th), math.sin(th)
    return np.stack([p[..., 0] * c + p[..., 2] * s, p[..., 1], -p[..., 0] * s + p[..., 2] * c], axis=-1)


def _rot_pan(p, ps):
    c, s = math.cos(ps), math.sin(ps)
    return np.stack([p[..., 0] * c - p[..., 1] * s, p[..., 0] * s + p[..., 1] * c, p[..., 2]], axis=-1)


def turret_clearance(pts, T, lid, lidar_z=None):
    """How far ahead of the pan axis the lidar's axis has to be (mm) for its cylinder to keep GAP from the turret's
    fixed base, from the pan group as it turns, and from the tilt group at tilt 0 as it turns. lidar_z: the lidar's
    base (the deck; the turret's TM face stands on the riser above it)."""
    r = lid['d'] / 2 + GAP
    top = (T.mount_z if lidar_z is None else lidar_z) + lid['h'] + GAP
    b = pts['base'][pts['base'][:, 2] <= top]
    b = b[np.abs(b[:, 1]) < r]
    out = {'base': float(np.max(b[:, 0] + np.sqrt(r * r - b[:, 1] ** 2))) if len(b) else 0.0}
    for g, z0 in (('pan', T.mount_z), ('tilt0', T.mount_z + T.G.tilt_t)):
        p = pts['pan' if g == 'pan' else 'tilt'] + (0.0, 0.0, z0)
        p = p[p[:, 2] <= top]
        out[g] = float(np.hypot(p[:, 0], p[:, 1]).max() + r) if len(p) else 0.0
    return out


def _obstacle_hits(p, obs, margin):
    """Which points (..., 3) lie within `margin` of any obstacle (the lidar's cylinder or a box)."""
    hit = np.zeros(p.shape[:-1], bool)
    for o in obs:
        if o['kind'] == 'cyl':
            hit |= ((np.hypot(p[..., 0] - o['c'][0], p[..., 1] - o['c'][1]) < o['r'] + margin)
                    & (p[..., 2] < o['z'][1] + margin) & (p[..., 2] > o['z'][0] - margin))
        else:
            hit |= np.all((p > np.asarray(o['lo']) - margin) & (p < np.asarray(o['hi']) + margin), axis=-1)
    return hit


def tilt_limits(tilt_pts, T, x_p, obs, ball_speed=21.3, pans=None, dz=0.0):
    """The most the barrel may depress (deg, + = down) at each pan (deg, every 2 deg over the pan stops) without the
    cradle, barrel or laser coming within GAP of the lidar, the deck or the ears, or the ball's path out of the muzzle
    (its first 400 mm, with gravity) coming within 3 mm of them. The cad/turret.py stops alone give 25 deg."""
    G = T.G
    tz = T.mount_z + G.tilt_t + dz                                  # dz: the turret raised on a riser (a study)
    front = tilt_pts[tilt_pts[:, 0] > 40.0]                        # the parts that reach forward and down
    s = np.arange(0.0, 400.0, 4.0)
    path = np.stack([G.barrel_x1 + s, np.zeros_like(s), np.full_like(s, -G.tilt_c)], axis=-1)
    drop = 0.5 * 9.81 * (s / 1000 / ball_speed) ** 2 * 1000

    def clear(pan, th):
        """For each tilt in th (rad): no part and no ball in the way at this pan (deg)."""
        ok = []
        for t in th:
            p = _rot_pan(_rot_tilt(front, t), math.radians(pan)) + (x_p, 0.0, tz)
            q = _rot_pan(_rot_tilt(path, t), math.radians(pan)) + (x_p, 0.0, tz)
            q[:, 2] -= drop
            ok.append(not (_obstacle_hits(p, obs, GAP).any() or _obstacle_hits(q, obs, G.ball / 2 + 3.0).any()))
        return ok
    table = []
    coarse = np.radians(np.arange(0.0, TILT_STOP_DEG + 0.01, 1.0))
    for pan in (np.arange(-PAN_STOP_DEG, PAN_STOP_DEG + 0.01, 2.0) if pans is None else pans):
        ok = clear(pan, coarse)
        if all(ok):
            table.append([float(pan), TILT_STOP_DEG])
            continue
        k = ok.index(False)                                         # the first coarse tilt in the way: refine below it
        fine = np.radians(np.arange(max(0.0, k - 1.0), k + 0.01, 0.1))
        best = 0.0
        for t, o in zip(fine, clear(pan, fine)):
            if not o:
                break
            best = math.degrees(t)
        table.append([float(pan), round(best, 1)])
    return table


def lidar_view(pts, T, x_p, lid, at, B, pans=(0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 170, -170), park_tilt=0.05):
    """What the turret hides from the lidar: per 1 deg of azimuth (0 = straight ahead, + = to the left), how many of
    its 16 beams (-15 .. +15 deg about the optical centre, 2 deg apart) meet the turret, treating the turret's outline
    at that azimuth as solid between its lowest and highest point. Also where the deck itself cuts the low beams."""
    o = np.array([at[0], at[1], at[2] + lid['oc']])
    beams = np.arange(lid['fov_v'][0], lid['fov_v'][1] + 0.01, 2.0)
    base = pts['base'] + (x_p, 0.0, 0.0)
    out = {}
    union_any, union_all = np.zeros(360, bool), np.zeros(360, bool)
    for pan in pans:
        ps = math.radians(pan)
        pg = _rot_pan(pts['pan'], ps) + (x_p, 0.0, T.mount_z)
        tg = _rot_pan(_rot_tilt(pts['tilt'], park_tilt), ps) + (x_p, 0.0, T.mount_z + T.G.tilt_t)
        p = np.concatenate([base, pg, tg]) - o
        az = (np.degrees(np.arctan2(p[:, 1], p[:, 0])) + 360.0) % 360.0
        el = np.degrees(np.arctan2(p[:, 2], np.hypot(p[:, 0], p[:, 1])))
        k = np.floor(az).astype(int)
        lo = np.full(360, np.inf)
        hi = np.full(360, -np.inf)
        np.minimum.at(lo, k, el)
        np.maximum.at(hi, k, el)
        n = np.array([np.sum((beams >= lo[i] - 1.0) & (beams <= hi[i] + 1.0)) for i in range(360)])
        out[pan] = n
        union_any |= n > 0
        union_all |= n == len(beams)

    def arcs(mask):
        """Runs of True as (from, to) in deg, -180..180 (+ = left)."""
        idx = [i for i in range(360) if mask[i]]
        if not idx:
            return []
        runs, start, prev = [], idx[0], idx[0]
        for i in idx[1:] + [None]:
            if i is None or i != prev + 1:
                runs.append((start, prev + 1))
                if i is not None:
                    start = i
            if i is not None:
                prev = i
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 360:
            runs = [(runs[-1][0], runs[0][1] + 360)] + runs[1:-1]
        wrap = lambda a: ((a + 180) % 360) - 180
        return [(wrap(a), wrap(b) if b % 360 else 180, b - a) for a, b in runs]
    # the deck: along each azimuth, how far the top surface reaches from under the optical centre; the low beams that
    # meet it before its edge are cut (the turret's sector aside)
    deck_cut = []
    for a in range(360):
        u = (math.cos(math.radians(a)), math.sin(math.radians(a)))
        reach = min([((B['x'][1] if u[0] > 0 else B['x'][0]) - at[0]) / u[0] if abs(u[0]) > 1e-9 else 1e9,
                     ((B['y'][1] if u[1] > 0 else B['y'][0]) - at[1]) / u[1] if abs(u[1]) > 1e-9 else 1e9])
        cut = sum(1 for e in beams if e < 0 and lid['oc'] / math.tan(math.radians(-e)) < reach)
        deck_cut.append(cut)
    deck_cut = np.array(deck_cut)
    return {'pan0_any': arcs(out[0] > 0), 'pan0_all': arcs(out[0] == len(beams)),
            'any_pan_any': arcs(union_any), 'any_pan_all': arcs(union_all),
            'deck_low_beams': arcs((deck_cut > 0) & ~union_any), 'deck_max_beams_cut': int(deck_cut[~union_any].max()) if (~union_any).any() else 0}


# ----------------------------------------------------------------------------------- the MJCF

def _inertial(b: Body, origin=(0.0, 0.0, 0.0)):
    c = [b.com[i] - origin[i] for i in range(3)]
    I = b.inertia
    return (f'<inertial pos="{c[0]:.5f} {c[1]:.5f} {c[2]:.5f}" mass="{b.mass:.4f}" '
            f'fullinertia="{I[0][0]:.6g} {I[1][1]:.6g} {I[2][2]:.6g} {I[0][1]:.6g} {I[0][2]:.6g} {I[1][2]:.6g}"/>')


def ref_pose():
    phi = fb.stance(REF_H)
    j = fb.fk(*phi)
    ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
    return {'phi1': phi[0], 'phi2': phi[1], 'af': ang(j['C'], j['E']), 'aw': ang(j['D'], j['E'])}


def _box_shape(size, centre):
    return cq.Workplane('XY').box(*size).translate(centre)


def _put(group, name, shape, color, opacity=1.0, mirror=False):
    f = f'{group}__{name}{"_m" if mirror else ""}.stl'
    s = shape.val() if hasattr(shape, 'val') else shape
    if mirror:
        s = s.mirror('XZ')
    cq.exporters.export(s, str(OUT_RIG / f), tolerance=0.35, angularTolerance=0.35)
    return {'file': f, 'name': name, 'color': color, 'opacity': opacity}


def export_turret(T, tshapes):
    """The turret's meshes: its fixed parts in the robot frame with the pan axis on x = 0 (build() moves them), its pan
    and tilt groups each in its joint's frame. Returns the manifest entries and the parts' surface points (mm)."""
    OUT_RIG.mkdir(parents=True, exist_ok=True)
    for f in OUT_RIG.glob('*.stl'):
        f.unlink()
    base = [_put('body', f'turret_{name}_{k}', sh, col) for k, (name, sh, col) in enumerate(tshapes['base'])]
    tz = T.mount_z + T.G.tilt_t
    groups = {}
    for gname, origin in (('pan', (0.0, 0.0, T.mount_z)), ('tilt', (0.0, 0.0, tz))):
        groups[gname] = [_put('turret', f'{gname}_{k}_{name}', sh.translate(tuple(-v for v in origin)), col)
                         for k, (name, sh, col) in enumerate(tshapes[gname])]
    pts = {'base': np.concatenate([surface_points(stl_tris(OUT_RIG / p['file'])) for p in base])}
    for g in ('pan', 'tilt'):
        pts[g] = np.concatenate([surface_points(stl_tris(OUT_RIG / p['file'])) for p in groups[g]])
    return base, groups, pts


def export_rig(rb, lid, lid_at, turret_base, turret_groups_):
    """STL meshes (mm) per moving group + the manifest, for MuJoCo's visuals and the 3D page: the hip modules, the body's
    frame parts (one mesh per colour), each bought part as its box, the ear pods, the lidar, the turret's fixed parts."""
    L = fb.leg_parts()
    man = {'units': 'mm', 'frame': 'robot: x forward, y left, z up, origin on the hip axis between the legs',
           'note': 'the body as built (milestone M5, cad/body_*.py): the P3 ledger\'s frame and parts; the shell is not drawn yet',
           'body': [], 'links': {}, 'turret': dict(turret_groups_)}
    frame = L.parts['hip_frame'].translate((0, Y_OFF, 0))
    man['body'].append(_put('body', 'hip_frame_l', frame, COLORS['frame']))
    man['body'].append(_put('body', 'hip_frame_r', frame, COLORS['frame'], mirror=True))
    mi = gmi.motor_interface(fb.MOTOR)
    motor = gmi._cyl((mi['od'] or 120) / 2, -(mi['length'] or 55.7), -0.5).union(gmi._cyl(25.0, -0.5, 0.0))
    for x in (fb.P['D'] / 2, -fb.P['D'] / 2):
        m = gmi.place(motor, (x, fb.Y['motor_out'] + Y_OFF, 0), (0, 1, 0))
        man['body'].append(_put('body', f'motor_{"f" if x > 0 else "r"}_l', m, COLORS['motor']))
        man['body'].append(_put('body', f'motor_{"f" if x > 0 else "r"}_r', m, COLORS['motor'], mirror=True))
        ad = gmi.place(gmi.output_adapter(fb.MOTOR, 'L')[0], (x, fb.Y['motor_out'] + Y_OFF, 0), (0, 1, 0))
        man['body'].append(_put('body', f'adapter_{"f" if x > 0 else "r"}_l', ad, COLORS['adapter']))
        man['body'].append(_put('body', f'adapter_{"f" if x > 0 else "r"}_r', ad, COLORS['adapter'], mirror=True))
    by_colour = {}                                               # the frame: one mesh per colour (fewer files to load)
    for n, prt in rb['parts'].items():
        if prt.shape is None:
            continue
        by_colour.setdefault(_hex(prt.colour), []).append(prt.shape.val() if hasattr(prt.shape, 'val') else prt.shape)
    for k, (c, shapes) in enumerate(sorted(by_colour.items())):
        man['body'].append(_put('body', f'frame_{k}', cq.Compound.makeCompound(shapes), c))
    for it in rb['L']['items']:                                  # the bought parts as their envelopes
        if it.keepout or not it.mass_g or it.name in ('vlp16', 'turret'):
            continue
        x0, x1, y0, y1, z0, z1 = it.box
        man['body'].append(_put('body', f'part_{it.name}', _box_shape((x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)),
                                _hex(it.rgb)))
    man['body'].append(_put('body', 'lidar', lidar_shape(lid, lid_at), COLORS['lidar']))
    man['body'] += turret_base
    # the leg links in their own frames (left as built; the page mirrors them for the right, MuJoCo uses _m copies)
    man['links']['upper'] = [_put('link', 'upper_link', L.parts['upper_link'], COLORS['link'])]
    man['links']['front'] = [_put('link', 'front_link', L.parts['front_link'], COLORS['link'])]
    man['links']['wheel_link'] = [_put('link', 'wheel_link', L.parts['wheel_link'], COLORS['wheel_link'])]
    tyre, hub = fb.botwheel()
    man['links']['wheel'] = [_put('link', 'tyre', tyre, COLORS['tyre']), _put('link', 'hub', hub, COLORS['hub'])]
    for key, parts in list(man['links'].items()):
        for p in parts:
            src = {'upper_link': L.parts['upper_link'], 'front_link': L.parts['front_link'], 'wheel_link': L.parts['wheel_link'],
                   'tyre': tyre, 'hub': hub}[p['name']]
            _put('link', p['name'], src, p['color'], mirror=True)
    return man


def build():
    """Write the MJCF and model.json (build/sim/v2/) and the 3D page's rig (exports/sim/v2/rig/). Returns the info."""
    import turret as tu
    OUT_BUILD.mkdir(parents=True, exist_ok=True)
    design = json.loads(DESIGN.read_text())
    lid = lidar_spec()
    lp, tmd = bp.lidar(), bp.tm()
    rb = real_body()
    wd69 = use_d69_wheel()                                           # after the ledger (it places the tyre's band itself)
    pad_boxes, PAD = pads()
    pad_g = {r['name'].split('.', 1)[1].replace('bay_skid_', 'pad_'): r['mass_g'] / 1000.0
             for r in rb['ledger']['rows'] if r['name'].startswith('frame.bay_skid_')}
    floor_g = next(r['mass_g'] for r in rb['ledger']['rows'] if r['name'] == 'frame.bay_floor') / 1000.0   # rides on the pads (numerics)
    B = rb['B']
    TOP = bp.TOP                                                     # the deck's top face (the lidar stands on it)
    T = tu.Turret({'bodyTop': tmd['face_z'] - 20.0 - tu.SADDLE_T})  # its TM face on the 30 mm riser (D41)
    tb, tshapes = turret_groups(T)
    turret_base, tgroups, tpts = export_turret(T, tshapes)
    # ---- the deck as the body builds it: the lidar 5.2 mm behind the front edge, the pan axis 143 mm behind it
    # (cad/body_params.py); the turret's own clearance needs are reported against that
    need = turret_clearance(tpts, T, lid, lidar_z=TOP)
    x_l, x_p = lp['x'], tmd['pan_x']
    d_lp = round(x_l - x_p, 2)
    lid_at = (x_l, 0.0, TOP)
    for p in turret_base:
        stl_shift(OUT_RIG / p['file'], (x_p, 0.0, 0.0))
    rear_overhang = max(0.0, B['x'][0] - (x_p + float(tpts['base'][:, 0].min())))     # the bumper ring past the deck's back
    # ---- the ears (SSC1 pods on the side walls): under the lidar's lowest beam (-15 deg)?
    ears_b = ear_boxes()
    oc_z = TOP + lid['oc']
    ear_margin = min(oc_z - math.hypot(max(abs(x - x_l) for x in b[:2]), max(abs(b[2]), abs(b[3]))) * math.tan(math.radians(-lid['fov_v'][0])) - b[5]
                     for _, b in ears_b)
    man = export_rig(rb, lid, lid_at, turret_base, tgroups)
    # ---- over the lidar: how far the barrel may depress by pan; what the turret hides from the lidar
    ears = [(n, (b[1] - b[0], b[3] - b[2], b[5] - b[4]), ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)) for n, b in ears_b]
    obs = [{'kind': 'cyl', 'c': (x_l, 0.0), 'r': lid['d'] / 2, 'z': (TOP, TOP + lid['h']), 'name': 'lidar'},
           {'kind': 'box', 'lo': (B['x'][0], B['y'][0], bp.z_tray_top()), 'hi': (B['x'][1], B['y'][1], TOP), 'name': 'deck'}]
    obs += [{'kind': 'box', 'lo': tuple(c[k] - s[k] / 2 for k in range(3)), 'hi': tuple(c[k] + s[k] / 2 for k in range(3)), 'name': n}
            for n, s, c in ears]
    table = tilt_limits(tpts['tilt'], T, x_p, obs)
    limited = [p for p, t in table if t < TILT_STOP_DEG - 1e-6]
    fwd = next(t for p, t in table if p == 0.0)
    # what a taller riser under the TM face would buy facing forward (the lidar stays on the deck)
    riser = {h: tilt_limits(tpts['tilt'], T, x_p, obs, pans=[0.0], dz=float(h))[0][1] for h in (10, 20, 30, 40)}
    view = lidar_view(tpts, T, x_p, lid, lid_at, B)
    # ---- the base: the body's P3 ledger row for row, both hip modules, the turret's fixed parts
    lb = leg_bodies()
    tb = {k: shift_x(v, x_p * M) for k, v in tb.items()}
    turret_cad_kg = tb['base'].mass + tb['pan'].mass + tb['tilt'].mass
    extra = (max(0.0, tmd['mass_kg'] - turret_cad_kg), (x_p * M, 0.0, (tmd['face_z'] + tmd['com_above_face_mm']) * M))
    parts = body_bodies(rb, x_p, extra)
    hip = [shift_y(lb['frame'], Y_OFF * M), mirror_body(shift_y(lb['frame'], Y_OFF * M))]
    leg_side = lb['frame'].mass + 2 * lb['upper'].mass + lb['front'].mass + lb['wheel_link'].mass + lb['rotor'].mass
    led = rb['ledger']
    led_kg = sum(r['mass_g'] for r in led['rows']) / 1000.0
    led_legs_side = sum(r['mass_g'] for r in led['rows'] if r['group'] == 'legs') / 2000.0
    leg_rest = led_legs_side - leg_side                            # leg.json counts parts the model leaves out (screws, ...)
    if abs(leg_rest) > 1e-4:                                       # at each hip module, where the ledger puts its own rest
        hip += [Body(leg_rest, (0.0, (Y_OFF + 30.0) * M, -0.1), name='rest of leg.json (left)'),
                Body(leg_rest, (0.0, -(Y_OFF + 30.0) * M, -0.1), name='rest of leg.json (right)')]
    parts += hip + [tb['base']]
    base = combine(parts, 'base')
    leg_kg = 2 * (2 * lb['upper'].mass + lb['front'].mass + lb['wheel_link'].mass + lb['rotor'].mass)
    total = base.mass + leg_kg + tb['pan'].mass + tb['tilt'].mass + sum(pad_g.values()) + floor_g
    reconciles = abs(total - led_kg) <= 0.002 * led_kg            # the model carries the ledger's mass
    rp = ref_pose()
    frame_shape = fb.leg_parts().parts['hip_frame'].translate((0, Y_OFF, 0))
    fbb = frame_shape.val().BoundingBox()
    leg_omega = lr.MOTOR['no_load_speed_rpm'] * BUS_V / lr.MOTOR['voltage_nominal_v'] * 2 * math.pi / 60
    # ---- MJCF
    l1, l2 = fb.P['l1'] / 1000, fb.P['l2'] / 1000
    ax = fb.P['D'] / 2000
    fo, fi, ro, ri = fb.stop_angles()
    st = lr.STOP_TRAVEL
    lim1 = (fi - rp['phi1'] - st, fo - rp['phi1'] + st)
    lim2 = (ro - rp['phi2'] - st, ri - rp['phi2'] + st)
    leg_peak = lr.LEG_PEAK
    wheel_peak = lr.WHEEL['peak_torque_nm']
    wr = lr.WHEEL_R
    yw = wd69['y_mm'] / 1000
    tyre_half_w = wd69['tyre_width_mm'] / 2000
    z0 = REF_H / 1000 + wr + 0.002
    q = lr._q
    rgba = lambda c, a=1.0: ' '.join(f'{int(c[i:i + 2], 16) / 255:.3f}' for i in (1, 3, 5)) + f' {a}'
    vis = lambda f, c, a=1.0: f'<geom type="mesh" mesh="{Path(f).stem}" rgba="{rgba(c, a)}" contype="0" conaffinity="0" group="1" mass="0"/>'
    assets = sorted({p['file'] for p in man['body']} | {p['file'] for v in man['links'].values() for p in v}
                    | {p['file'].replace('.stl', '_m.stl') for v in man['links'].values() for p in v}
                    | {p['file'] for v in tgroups.values() for p in v})
    asset_xml = ''.join(f'<mesh name="{Path(f).stem}" file="{f}" scale="0.001 0.001 0.001"/>' for f in assets)

    def leg(side, tag):
        y = side * Y_OFF * M
        mir = (lambda b: b) if side > 0 else mirror_body
        mf = '' if side > 0 else '_m'
        link = lambda key: man['links'][key]
        lv = lambda key: ''.join(vis(p['file'].replace('.stl', f'{mf}.stl'), p['color']) for p in link(key))
        # collision capsules along each link, at its layer (contype 4: the floor and balls, not each other or the body)
        cap = lambda length, r, yc: (f'<geom type="capsule" fromto="0.02 {side * yc:.4f} 0 {length - 0.02:.4f} {side * yc:.4f} 0" size="{r}" '
                                     f'contype="4" conaffinity="1" rgba="0 0 0 0" mass="0"/>')
        yu, yf, yw_ = sum(fb.Y['upper']) / 2000, sum(fb.Y['front_link']) / 2000, sum(fb.Y['wheel_link']) / 2000
        return f"""
      <body name="upper_f_{tag}" pos="{ax} {y:.5f} 0" quat="{q(rp['phi1'])}">
        <joint name="motor_f_{tag}" type="hinge" axis="0 -1 0" armature="{lr.ARMATURE:.4f}" damping="0.05" frictionloss="0.4" range="{lim1[0]:.4f} {lim1[1]:.4f}"/>
        {_inertial(mir(lb['upper']))}{lv('upper')}{cap(l1, 0.02, yu)}
        <body name="lower_f_{tag}" pos="{l1} 0 0" quat="{q(rp['af'] - rp['phi1'])}">
          <joint name="knee_f_{tag}" type="hinge" axis="0 -1 0" damping="0.02"/>
          {_inertial(mir(lb['front']))}{lv('front')}{cap(l2, 0.017, yf)}
        </body>
      </body>
      <body name="upper_r_{tag}" pos="{-ax} {y:.5f} 0" quat="{q(rp['phi2'])}">
        <joint name="motor_r_{tag}" type="hinge" axis="0 -1 0" armature="{lr.ARMATURE:.4f}" damping="0.05" frictionloss="0.4" range="{lim2[0]:.4f} {lim2[1]:.4f}"/>
        {_inertial(mir(lb['upper']))}{lv('upper')}{cap(l1, 0.02, yu)}
        <body name="lower_r_{tag}" pos="{l1} 0 0" quat="{q(rp['aw'] - rp['phi2'])}">
          <joint name="knee_r_{tag}" type="hinge" axis="0 -1 0" damping="0.02"/>
          {_inertial(mir(lb['wheel_link']))}{lv('wheel_link')}{cap(l2, 0.019, yw_)}
          <body name="wheel_{tag}" pos="{l2} 0 0">
            <joint name="wheel_{tag}" type="hinge" axis="0 1 0" damping="0.01" frictionloss="0.02"/>
            {_inertial(mir(lb['rotor']))}{lv('wheel')}
            <geom name="tyre_{tag}" type="cylinder" size="{wr:.4f} {tyre_half_w:.4f}" pos="0 {side * yw:.4f} 0" euler="1.5708 0 0" contype="4" conaffinity="1"
                  friction="1.0 0.02 0.001" solref="{lr.TYRE_SOLREF}" rgba="0 0 0 0" mass="0"/>
          </body>
        </body>
      </body>"""

    # ---- the crush pads (issue #19): each a body on a slide joint along the base's z under the bay's floor (0 = free, + =
    # pushed up into the floor). The joint carries the pad's damper c; its crush law (min(k x, the plateau), the lattice's
    # hysteresis unloading) is applied each step by sim/scenarios.py from model.json's pads; past the stroke the joint's
    # limit is the densified lattice (a stiff, critically damped stop). The pad's floor contact is stiff, so the pad's own
    # law is the compliance. Numerics: a 25 g pad on an 80 N/mm spring rings at 1.8 kHz, beyond the 1 ms step; the bay
    # floor's mass (it sits right over the pads) rides on the pads in the model instead, so each pad body carries a quarter
    # of floor and pads (the total is the ledger's).
    k_pad, c_pad, stroke = PAD['k_n_per_mm'] * 1000.0, PAD['c_ns_per_m'], PAD['stroke'] / 1000.0
    pad_each = (sum(pad_g.values()) + floor_g) / max(len(pad_g), 1)

    def pad_xml(name, b):
        x0, x1, y0, y1, z0_, z1_ = (v * M for v in b)
        sx, sy, sz = (x1 - x0) / 2, (y1 - y0) / 2, (z1_ - z0_) / 2
        m = pad_each
        I = (m * (sy * sy + sz * sz) / 3, m * (sx * sx + sz * sz) / 3, m * (sx * sx + sy * sy) / 3)
        return (f'<body name="{name}" pos="{(x0 + x1) / 2:.5f} {(y0 + y1) / 2:.5f} {z1_:.5f}">'
                f'<joint name="{name}" type="slide" axis="0 0 1" range="0 {stroke:.5f}" stiffness="0" damping="{c_pad:.1f}" '
                f'solreflimit="0.002 1"/>'
                f'<inertial pos="0 0 {-sz:.5f}" mass="{m:.4f}" diaginertia="{I[0]:.3g} {I[1]:.3g} {I[2]:.3g}"/>'
                f'<geom name="{name}" type="box" size="{sx:.5f} {sy:.5f} {sz:.5f}" pos="0 0 {-sz:.5f}" contype="2" conaffinity="1" '
                f'solref="0.004 1" friction="0.8 0.005 0.0001" rgba="0.15 0.15 0.17 1" group="1"/></body>')
    pads_xml = ''.join(pad_xml(n, b) for n, b in pad_boxes)
    tz = (T.mount_z + T.G.tilt_t) * M
    mz = [(v * M - o) for v, o in zip(T.point((T.G.barrel_x1, 0, 0), 'tilt', 0.0, 0.0), (0.0, 0.0, tz))]
    pan_o = (x_p * M, 0.0, T.mount_z * M)
    body_vis = ''.join(vis(p['file'], p['color'], p['opacity']) for p in man['body'])
    hb = (max(abs(fbb.xmin), abs(fbb.xmax)) / 1000, max(abs(fbb.ymin), abs(fbb.ymax)) / 1000, max(abs(fbb.zmin), abs(fbb.zmax)) / 1000)
    body_geoms = ''.join(f'<geom name="{n}" type="box" size="{(b[1] - b[0]) / 2000:.4f} {(b[3] - b[2]) / 2000:.4f} {(b[5] - b[4]) / 2000:.4f}" '
                         f'pos="{(b[0] + b[1]) / 2000:.4f} {(b[2] + b[3]) / 2000:.4f} {(b[4] + b[5]) / 2000:.4f}" contype="2" conaffinity="1" '
                         f'rgba="0 0 0 0" mass="0"/>' for n, b in rb['collide'])
    xml = f"""<mujoco model="gyropup_v2">
  <compiler angle="radian" autolimits="true" meshdir="{OUT_RIG}"/>
  <option timestep="0.001" gravity="0 0 -9.81" integrator="implicitfast"/>
  <visual><headlight diffuse="0.6 0.6 0.6" ambient="0.35 0.35 0.35"/><global offwidth="1280" offheight="720"/></visual>
  <asset>{asset_xml}
    <texture name="grid" type="2d" builtin="checker" rgb1=".86 .88 .9" rgb2=".78 .8 .83" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="12 12"/>
  </asset>
  <default><geom friction="1.0 0.005 0.0001"/></default>
  <worldbody>
    <light pos="1.5 1.5 3" dir="-0.4 -0.4 -1"/>
    <geom name="floor" type="plane" size="30 30 0.1" material="grid"/>
    <body name="base" pos="0 0 {z0:.4f}">
      <freejoint name="root"/>
      {_inertial(base)}
      <geom name="hip_block" type="box" size="{hb[0]:.4f} {hb[1]:.4f} {hb[2]:.4f}" contype="2" conaffinity="1" rgba="0 0 0 0" mass="0"/>
      <geom name="lidar" type="cylinder" size="{lid['d'] / 2000:.4f} {lid['h'] / 2000:.4f}" pos="{x_l / 1000:.4f} 0 {(TOP + lid['h'] / 2) / 1000:.4f}"
            contype="2" conaffinity="1" rgba="0 0 0 0" mass="0"/>
      {body_geoms}
      {body_vis}
      <site name="imu" pos="0 0 0.1"/>
      {leg(1, 'l')}
      {leg(-1, 'r')}
      {pads_xml}
      <body name="turret_pan" pos="{pan_o[0]:.4f} {pan_o[1]} {pan_o[2]:.4f}">
        <joint name="turret_pan" type="hinge" axis="0 0 1" range="{math.radians(-PAN_STOP_DEG):.4f} {math.radians(PAN_STOP_DEG):.4f}" damping="0.05" frictionloss="0.02" armature="0.002"/>
        {_inertial(tb['pan'], pan_o)}
        {''.join(vis(p['file'], p['color']) for p in tgroups['pan'])}
        <body name="turret_tilt" pos="0 0 {tz - pan_o[2]:.4f}">
          <joint name="turret_tilt" type="hinge" axis="0 1 0" range="-0.01 {math.radians(TILT_STOP_DEG):.4f}" damping="0.05" frictionloss="0.02" armature="0.001"/>
          {_inertial(tb['tilt'], (pan_o[0], 0.0, tz))}
          {''.join(vis(p['file'], p['color']) for p in tgroups['tilt'])}
          <geom type="box" size="0.1 0.06 0.06" pos="0.04 0 0" contype="2" conaffinity="1" rgba="0 0 0 0" mass="0"/>
          <site name="muzzle" pos="{mz[0]:.4f} {mz[1]:.4f} {mz[2]:.4f}"/>
        </body>
      </body>
    </body>
  </worldbody>
  <equality>
    <connect name="apex_l" body1="lower_f_l" body2="lower_r_l" anchor="{l2} 0 0" solref="0.002 1"/>
    <connect name="apex_r" body1="lower_f_r" body2="lower_r_r" anchor="{l2} 0 0" solref="0.002 1"/>
  </equality>
  <contact>
    <exclude body1="base" body2="upper_f_l"/><exclude body1="base" body2="upper_r_l"/><exclude body1="base" body2="upper_f_r"/><exclude body1="base" body2="upper_r_r"/>
    <exclude body1="lower_f_l" body2="lower_r_l"/><exclude body1="lower_f_r" body2="lower_r_r"/>
  </contact>
  <actuator>
    <motor name="motor_f_l" joint="motor_f_l" ctrlrange="-{leg_peak} {leg_peak}"/>
    <motor name="motor_r_l" joint="motor_r_l" ctrlrange="-{leg_peak} {leg_peak}"/>
    <motor name="wheel_l" joint="wheel_l" ctrlrange="-{wheel_peak} {wheel_peak}"/>
    <motor name="motor_f_r" joint="motor_f_r" ctrlrange="-{leg_peak} {leg_peak}"/>
    <motor name="motor_r_r" joint="motor_r_r" ctrlrange="-{leg_peak} {leg_peak}"/>
    <motor name="wheel_r" joint="wheel_r" ctrlrange="-{wheel_peak} {wheel_peak}"/>
    <motor name="turret_pan" joint="turret_pan" ctrlrange="-5 5"/>
    <motor name="turret_tilt" joint="turret_tilt" ctrlrange="-3 3"/>
  </actuator>
</mujoco>"""
    (OUT_BUILD / 'robot.xml').write_text(xml)

    def com_at_reference():
        """The whole robot's centre of mass (mm, robot frame) standing at REF_H, from the MJCF just written."""
        import mujoco
        mm = mujoco.MjModel.from_xml_path(str(OUT_BUILD / 'robot.xml'))
        dd = mujoco.MjData(mm)
        mujoco.mj_forward(mm, dd)
        b = mm.body('base').id
        return [round(float(v) * 1000, 1) for v in dd.subtree_com[b] - dd.xpos[b]]
    wheel_omega = lr.WHEEL['no_load_speed_rpm'] * BUS_V / lr.WHEEL['voltage_nominal_v'] * 2 * math.pi / 60
    lowest = round(B['z'][0], 1)                                    # the battery bay's skids
    span = f'{min(limited):.0f} .. {max(limited):.0f}' if limited else 'none'
    blocked = view['pan0_any'][0] if view['pan0_any'] else None
    tilt_note = (f'over the lidar the barrel may depress at most {fwd:.1f} deg facing forward (the stops allow {TILT_STOP_DEG:.0f}): the '
                 f'cradle\'s front edge and the barrel come within {GAP:.0f} mm of the lidar\'s top; limited between pan {span} deg '
                 f'(turret.tilt_max_deg); the controller lifts the barrel before panning over the lidar and the robot crouches to '
                 f'shoot ahead; a riser taller by ' + ', '.join(f'{h} mm -> {v:.1f} deg' for h, v in riser.items()))
    view_note = (f'the turret hides azimuth {blocked[0]} .. {blocked[1]} deg ({blocked[2]} deg) from the lidar at pan 0 '
                 f'(all 16 beams over {sum(a[2] for a in view["pan0_all"])} deg of it); up to {sum(a[2] for a in view["any_pan_any"])} deg '
                 f'as the turret pans' if blocked else 'the turret hides nothing from the lidar')
    info = {
        'kind': 'fivebar', 'design': 'v2', 'name': 'Gyropup v2 (five-bar)', 'total_mass_kg': round(total, 3),
        'mass_split_kg': {'base (hip modules, frame, electronics, battery, lidar, shell, turret base)': round(base.mass, 3),
                          'legs (links, adapters, bearings, wheels)': round(leg_kg, 3),
                          'turret pan + tilt': round(tb['pan'].mass + tb['tilt'].mass, 3)},
        'mass_reconciles': reconciles,
        'ledger': {'stage': 'P3', 'total_kg': round(led_kg, 3), 'groups_kg': led['groups_kg'], 'com_mm': led['com_mm'],
                   'source': 'cad/body_layout.py ledger() P3 (exports/body/mass.json); the legs to exports/leg/leg.json\'s total; '
                             'the head to body_params.tm()', 'legs_rest_kg_each': round(leg_rest, 4),
                   'head_beyond_turret_cad_kg': round(extra[0], 4)},
        'bus_v': BUS_V,
        'com_mm': com_at_reference(),
        'leg_actuator': {'peak_nm': leg_peak, 'rated_nm': lr.MOTOR['rated_torque_nm'], 'omega_max': leg_omega, 'armature': lr.ARMATURE,
                         'cap_nm': float(design.get('leg_torque_limit_nm') or lr.LEG_CAP)},
        'wheel_motor': {'peak_nm': wheel_peak, 'rated_nm': lr.WHEEL['rated_torque_nm'], 'omega_max': wheel_omega},
        'fivebar': {'D_mm': fb.P['D'], 'l1_mm': fb.P['l1'], 'l2_mm': fb.P['l2'], 'ref': rp, 'ref_h_mm': REF_H, 'h_range_mm': H_RANGE,
                    'stops_rad': list(fb.stop_angles()), 'y_off_mm': Y_OFF, 'stop_k': lr.STOP_K, 'stop_b': lr.STOP_B},
        'wheel_r_m': wr, 'head_payload': design.get('head_payload'), 'body_top_m': TOP * M,
        'body_mm': B,
        'turret': {'pan_effort_nm': 5.0, 'tilt_effort_nm': 3.0, 'magazine': 30, 'ball_speed_mps': 21.3, 'ball_mass_kg': 0.00183,
                   'tilt_positive': 'barrel down', 'from_cad': True, 'pan_axis_mm': [round(x_p, 2), 0.0, TOP],
                   'tilt_stop_deg': TILT_STOP_DEG, 'tilt_max_deg': table, 'tilt_max_rad': [[math.radians(p), math.radians(t)] for p, t in table],
                   'tilt_max_note': tilt_note, 'riser_study_deg_at_pan0': {str(h): v for h, v in riser.items()}},
        'lidar': {'model': 'Velodyne VLP-16', 'mount_mm': [round(x_l, 2), 0.0, TOP], 'optical_centre_mm': [round(x_l, 2), 0.0, round(TOP + lid['oc'], 1)],
                  'mass_g': lid['mass_g'], 'mounting': lid['mounting'], 'cable_exit': '+y (left), the locating pins fore and aft',
                  'clearance_to_turret_mm': GAP,
                  'turret_clearance_needs_mm': {k: round(v, 1) for k, v in need.items()}, 'axis_to_pan_axis_mm': d_lp,
                  'turret_rear_overhang_mm': round(rear_overhang, 1), 'blocked': view},
        'layout_mm': {'trayBottom': lowest + 80.0, 'lidarMount': 'top', 'wheelR': wr * 1000, 'bodyTop': TOP},
        'lowest_point_mm': lowest,
        'track_mm': round(2 * (wd69['y_mm'] + Y_OFF), 1),
        'wheel': {'decision': 'D69', 'key': WHEEL_KEY, 'od_mm': wd69['od_mm'], 'mass_g': wd69['mass_g'], 'tyre_width_mm': wd69['tyre_width_mm'],
                  'tyre_solref': lr.TYRE_SOLREF, 'peak_nm': wheel_peak, 'basis': 'sim/wheel_candidates.json hb10 at the ledger\'s mass'},
        'pads': {'names': [n for n, _ in pad_boxes], 'k_n_per_mm_each': PAD['k_n_per_mm'], 'c_ns_per_m_each': PAD['c_ns_per_m'],
                 'plateau_n_each': PAD['plateau_n'], 'unload_ratio': PAD['unload_ratio'], 'body_kg_each_in_model': round(pad_each, 4),
                 'stroke_mm': PAD['stroke'], 'h_mm': PAD['h'], 'mass_kg': {n: round(g, 4) for n, g in pad_g.items()},
                 'touch_leg_mm': round(-B['z'][0] - wr * 1000, 1), 'basis': 'cad/body_battery.py PAD (issue #19)'},
        'notes': [f'the body as built (M5): the P3 ledger, {led_kg:.2f} kg (cad/body_layout.py; the model {total:.2f} kg), the spine 40.5 mm wide '
                  f'(track {2 * (wd69["y_mm"] + Y_OFF):.1f} mm), the deck at z {TOP:.0f}, the battery bay\'s crush pads at z {lowest} (the lowest part)',
                  f'D69\'s wheels: 10 in hub motors, {wd69["mass_g"] / 1000:.2f} kg each, a pneumatic tyre (solref {lr.TYRE_SOLREF})',
                  f'the deck: the VLP-16 at x = {x_l:.1f} mm, the turret\'s pan axis {d_lp:.1f} mm behind it (x = {x_p:.1f} mm) on the 30 mm riser '
                  f'(TM face z {tmd["face_z"]:.0f}); the turret\'s clearance needs {max(need.values()):.1f} mm; its base overhangs the rear by {rear_overhang:.1f} mm',
                  tilt_note, view_note,
                  f'the ears (SSC1 pods on the side walls, x {EAR["x"][0]:.0f}..{EAR["x"][1]:.0f}, tops at z {EAR["top"]:.0f}) are {ear_margin:.1f} mm under '
                  'the lidar\'s lowest beam; the eyes alone on the face',
                  f'the motors\' speed lines at the 10S pair\'s {BUS_V} V nominal (D65)',
                  'RS-04 rotor inertia, the tyre stiffness, the harness, hardware and shell masses are estimates (the ledger says which)'],
        'estimates': ['RS-04 rotor inertia (armature)', 'the 10 in tyre\'s stiffness (60 N/mm at 35 psi, a membrane model)', 'the crush pads\' k and c (the coupon test)', 'the harness, hardware and shell panels (the ledger\'s estimate rows)',
                      'the G48R cooler\'s mass (450 g est)'],
    }
    (OUT_BUILD / 'model.json').write_text(json.dumps(info, indent=1) + '\n')
    hl = [[c[0] + s[0] / 2, c[1], c[2]] for n, s, c in sorted(ears, key=lambda e: -e[2][1])]
    import body_layout as bl
    shell = {n: c for n, g, c, b in bl.SHELL_ITEMS}                 # the P3 ledger's eyes and front camera
    top = max(float(tpts['base'][:, 2].max()), T.mount_z + float(tpts['pan'][:, 2].max()), T.mount_z + T.G.tilt_t + float(tpts['tilt'][:, 2].max()))
    man.update({'fivebar': info['fivebar'], 'wheel_r_mm': wr * 1000, 'track_mm': info['track_mm'], 'body_top_mm': TOP,
                'mounts': {'eyes': [B['x'][1] + 2.0, 0.0, shell['eyes'][2]],
                           'headlights': hl, 'camera_front': [B['x'][1] + 2.0, 0.0, shell['depth_camera_front'][2]],
                           'lidar': [x_l, 0.0, TOP]},
                'turret': {**man['turret'], 'pan_mm': [x_p, 0.0, T.mount_z], 'tilt_mm': [x_p, 0.0, T.mount_z + T.G.tilt_t],
                           'muzzle_mm': [x_p + v if i == 0 else v for i, v in enumerate(T.point((T.G.barrel_x1, 0, 0), 'tilt', 0.0, 0.0))]},
                'deck': {'tilt_max_forward_deg': fwd, 'lidar_hidden_deg': sum(a[2] for a in view['pan0_all']), 'tilt_max_deg': table},
                'height_mm': round(top, 1), 'mass_kg': info['total_mass_kg'], 'mass_split_kg': info['mass_split_kg']})
    (OUT_RIG / 'manifest.json').write_text(json.dumps(man, indent=1) + '\n')
    return info


if __name__ == '__main__':
    info = build()
    print(f"{info['name']}: {info['total_mass_kg']:.2f} kg  {info['mass_split_kg']}  track {info['track_mm']} mm  com {info['com_mm']} mm")
    for n in info['notes']:
        print(' -', n)
