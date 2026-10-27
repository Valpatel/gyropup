"""The five-bar leg (leg v2): both leg motors in the body, the wheel at the apex of the linkage.

One leg module, built for the LEFT side. Module frame: x forward, y outwards (away from the body), z up. The two motor
axes are parallel to y at (+D/2, 0) (front motor) and (-D/2, 0) (rear motor); y = 0 is their standard output face
(GMI AO-L), so the motors and the hip frame are at y < 0 and the linkage and the wheel at y > 0.

    front motor A --- upper link L1 --- knee C --- front lower link L2 ---.
                                                                          apex E = wheel axle
    rear motor  B --- upper link L1 --- knee D --- wheel link L2 ---------'

The linkage is a symmetric five-bar (research/wheel-legged-survey-2026-10-26.md, tools/leg_synthesis.py): two motors
D apart drive two equal upper links; two equal lower links meet at the wheel axle. The wheel link carries the wheel
on a hollow hub; the front lower link rides on that hub on a 61812. Its numbers came from a sweep of 330 printable geometries (tools/leg_synthesis.py):
the most vertical force at a 60 N m motor cap over the whole working region (leg 130-380 mm, +-20 deg lean at
220-340 mm), every joint at least 33 deg from a dead point, the knees below the hip line, the lower links short
enough to print on a 256 mm bed.

Layers along y, from the output face outwards (mm):
    0 .. 26     upper links (on the AO faces)
    28 .. 44    front lower link (its knee boss reaches out to 70)
    46 .. 70    wheel link (its knee boss reaches in to 28; its hub points in through the front link's apex eye)
    64.8        the BotWheel's boss face, in a recess in the wheel link's outer face; tyre 72.3 .. 116.9
    0 .. 44     the front link's apex eye (two 61812 28 mm apart on the wheel link's hub)
The wheel link is the outer one so the wheel sits right against it (37 mm from its middle to the wheel's), which keeps
the wheel's out-of-plane moment small where it is largest. Both knees are the same cartridge (two 6201-2RS in the lower
link, a 12 mm ISO 7379 shoulder screw clamped in the upper link by an M10 nut in a pocket). The apex is two 61812 in the
front link on the wheel link's hollow hub, held by a DIN 471 circlip: it carries moment, so the wheel's out-of-plane
load is shared by both sides of the loop, and the wheel's cable and a hex key for its four M6 screws come through the
middle.
"""
from __future__ import annotations

import functools
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq

import gmi

STD = gmi.STD
MOTOR = 'robstride-rs-04'
WHEEL = 'odrive-botwheel'

PARAMS = {
    'D': 150.0, 'l1': 150.0, 'l2': 250.0,              # five-bar: motor spacing, upper links, lower links
    'upper_t': 30.0, 'upper_w0': 46.0, 'upper_w1': 36.0,     # upper link: thickness (y), depth at the hub and at the knee
    'wheel_t': 26.0, 'wheel_w0': 42.0, 'wheel_w1': 36.0,     # wheel link: thickness, depth at the apex and at the knee
    'front_t': 20.0, 'front_w': 30.0,                    # front lower link (thickness: the leg's out-of-plane stiffness)
    'gap': 2.0,                                          # between layers (a DIN 433 M12 washer at each knee)
    'knee_out_deg': 3.0, 'knee_in_deg': -97.0,           # the front upper link's stops (from +x, ccw); the rear mirrors
    'stop_r': 58.0,                                      # stop posts: radius from the motor axis (between the lug screws)
    'hollow': False, 'skin': 5.0,                        # links as closed boxes (cavity, 'skin' walls): tried 2026-10-26, it
                                                         # weakened the wheel link and the leg too much (cad/leg_studies.py); solid
}
if os.environ.get('GYROPUP_LEG_PARAMS'):
    PARAMS.update(json.loads(Path(os.environ['GYROPUP_LEG_PARAMS']).read_text()))
P = PARAMS

KC = {**STD['KC'], 'bearing': '6201-2RS', 'bearing_od': 32.0, 'bearing_w': 10.0, 'hub_od': 46.0,
      'shoulder_d': 27.0}                                 # the knees: 6201s (C0 3.1 kN), the outer races' shoulder Ø27
AC = STD['AC-L']
FAST = STD['fasteners']
ISO7379_HEAD = {12: (18.0, 9.0), 10: (16.0, 7.0)}       # shoulder d: head diameter, head height (McMaster 92981A408 / A303)
M10_NUT = (17.0, 10.0)                                   # nyloc M10: across flats, height (DIN 985 is 10 mm)
TPU_SLEEVE = (18.0, 10.0)                                # stop sleeve OD on a 10 mm shoulder
EYE_SLEEVE = (18.0, 12.0, 20.0)                          # the steel sleeves pressed into each upper link's knee eye: OD, ID,
                                                         # length (McMaster 96990A403, DIN 179 12 x 18 x 20, HRC 61)
EYE_SLEEVES = 2                                          # two, end to end, 40 mm: the knee pin cantilevers out to the lower
                                                         # link's bearings (their mid-plane 46 mm from the sleeves' middle),
                                                         # so the eye carries that moment as bearing pressure along the sleeves;
                                                         # one 20 mm sleeve put 110 MPa on the plastic in a collapse onto the
                                                         # stops (1.8 kN at the knee), two 31 MPa (cad/leg_studies.py)
EYE_BOSS = 20.0                                          # the eye stands this proud of the link's inner face (the sleeves, then
                                                         # the nut's pocket)



# ----------------------------------------------------------------------------------- kinematics

def motors():
    return (P['D'] / 2, 0.0), (-P['D'] / 2, 0.0)


def fk(phi1: float, phi2: float):
    """Joint points (x, z) in mm for motor angles phi1 (front) and phi2 (rear), radians from +x, ccw seen from +y...
    i.e. in the x-z plane with z up. Returns dict A, B, C, D, E or None when the lower links cannot meet."""
    (ax, az), (bx, bz) = motors()
    l1, l2 = P['l1'], P['l2']
    C = (ax + l1 * math.cos(phi1), az + l1 * math.sin(phi1))
    Dp = (bx + l1 * math.cos(phi2), bz + l1 * math.sin(phi2))
    vx, vz = C[0] - Dp[0], C[1] - Dp[1]
    r = math.hypot(vx, vz)
    if r > 2 * l2 or r < 1e-9:
        return None
    mx, mz = (C[0] + Dp[0]) / 2, (C[1] + Dp[1]) / 2
    h = math.sqrt(l2 * l2 - r * r / 4)
    nx, nz = -vz / r, vx / r
    E1, E2 = (mx + h * nx, mz + h * nz), (mx - h * nx, mz - h * nz)
    E = E1 if E1[1] < E2[1] else E2
    return {'A': (ax, az), 'B': (bx, bz), 'C': C, 'D': Dp, 'E': E}


def ik(x: float, z: float):
    """Motor angles (phi1, phi2) that put the wheel axle at (x, z), knees out; None if out of reach."""
    l1, l2 = P['l1'], P['l2']
    out = []
    for (px, pz), side in zip(motors(), (1, -1)):
        vx, vz = x - px, z - pz
        r = math.hypot(vx, vz)
        if r > l1 + l2 or r < abs(l1 - l2):
            return None
        a = (l1 * l1 - l2 * l2 + r * r) / (2 * r)
        h = math.sqrt(max(0.0, l1 * l1 - a * a))
        mx, mz = px + a * vx / r, pz + a * vz / r
        c1 = (mx - h * vz / r, mz + h * vx / r)
        c2 = (mx + h * vz / r, mz - h * vx / r)
        C = c1 if (c1[0] - c2[0]) * side > 0 else c2
        a = math.atan2(C[1] - pz, C[0] - px)
        if side < 0 and a > 0:                    # the rear link's angles run continuously from -183 to -83 deg
            a -= 2 * math.pi
        out.append(a)
    return tuple(out)


def stance(height_mm: float, lean_deg: float = 0.0):
    """Motor angles for a leg length (hip line to axle) and a lean (+ = wheel forward)."""
    a = math.radians(lean_deg)
    return ik(height_mm * math.sin(a), -height_mm * math.cos(a))


def jacobian(phi1: float, phi2: float, eps: float = 1e-6):
    """d(E)/d(phi) (mm/rad) by central differences."""
    J = [[0.0, 0.0], [0.0, 0.0]]
    for k in range(2):
        p = [phi1, phi2]
        p[k] += eps
        a = fk(*p)
        p[k] -= 2 * eps
        b = fk(*p)
        J[0][k] = (a['E'][0] - b['E'][0]) / (2 * eps)
        J[1][k] = (a['E'][1] - b['E'][1]) / (2 * eps)
    return J


def stop_angles():
    """(front out, front in, rear out, rear in) in radians: the rear mirrors the front about x = 0."""
    fo, fi = math.radians(P['knee_out_deg']), math.radians(P['knee_in_deg'])
    return fo, fi, -math.pi - fo, -math.pi - fi       # rear: continuous angles (-183 .. -83 deg), not wrapped


# ----------------------------------------------------------------------------------- the stack

@dataclass
class Stack:
    y: dict
    notes: list


def stack() -> Stack:
    _, ad = gmi.output_adapter(MOTOR, 'L')
    _, pl = gmi.motor_plate(MOTOR, 'L')
    mi = gmi.motor_interface(MOTOR)
    g = P['gap']
    y = {}
    y['ao_face'] = 0.0
    y['motor_out'] = -ad['z_face']                                       # the motor's output face
    y['frame'] = (y['motor_out'] + pl['z'][0], y['motor_out'] + pl['z'][1])   # lug face .. leg-side face
    y['bearing'] = (y['motor_out'] + pl['bearing_z'][0], y['motor_out'] + pl['bearing_z'][1])
    y['motor'] = (y['motor_out'] - mi['length'], y['motor_out'])
    y['upper'] = (0.0, P['upper_t'])
    y['front_link'] = (y['upper'][1] + g, y['upper'][1] + g + P['front_t'])
    y['wheel_link'] = (y['front_link'][1] + g, y['front_link'][1] + g + P['wheel_t'])
    y['knee_boss'] = (y['front_link'][0], y['wheel_link'][1])          # both lower links' knee bosses span both layers
    y['apex_eye'] = (0.0, y['front_link'][1])                            # the front link's apex eye reaches in over the
                                                                         # upper links' layer (nothing comes near the axle there)
    y['hub'] = (y['apex_eye'][0] - 6.0, y['wheel_link'][0])              # the wheel link's hub, pointing in through that eye;
                                                                         # 6 mm past it: a land for the circlip (DIN 471 >= 4.5)
    y['apex_bearing'] = (y['front_link'][0] + 3.0, y['front_link'][0] + 13.0)     # outer 61812
    y['apex_bearing_in'] = (3.0, 13.0)                                   # inner 61812: 28 mm apart, so the apex carries moment
    y['circlip'] = (0.8, 2.95)                                           # DIN 471-60 groove, inboard of the inner bearing
    w = gmi.motor_interface(WHEEL)
    boss_h = w['case']['spigot_h'] or 5.0
    y['wheel_boss'] = y['wheel_link'][1] - boss_h - 0.2                 # the BotWheel's boss face, in a recess in the outer face
    y['tyre'] = (y['wheel_boss'] + 7.5, y['wheel_boss'] + 7.5 + 44.6)    # BotWheel drawing: boss face 7.5 inboard of the tyre
    y['wheel'] = sum(y['tyre']) / 2
    y['centre_plane'] = y['motor'][0] - 2.0                              # where the two legs' frames meet in the body
    notes = []
    return Stack(y, notes)


S = stack()
Y = S.y


# ----------------------------------------------------------------------------------- helpers

def ycyl(r, y0, y1, x=0.0, z=0.0):
    """A cylinder along y from y0 to y1 centred at (x, z)."""
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def yslab(points, y0, y1):
    """A prism from an x-z outline, from y0 to y1."""
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(points).close().extrude(y1 - y0)


def boss_fillet(outline, face_y, side, r=None, f=6.0, cx=0.0, arm_dir=1):
    """A fillet ring where a boss (radius r, round (cx, 0)) stands out of a link's face at face_y and runs on towards
    side = -1 (smaller y) or +1: those sharp inside corners carried the links' peak stresses (cad/leg_studies.py: the
    wheel link's knee boss in R1, the upper link's eye boss in the collapse). Clipped to the link's outline and to the
    arm's side of the boss (arm_dir = +1: the arm runs towards +x), so it is only where the face is."""
    r = KC['hub_od'] / 2 if r is None else r
    s = side
    ring = (cq.Workplane('XY').moveTo(r, face_y + s * f).lineTo(r, face_y).lineTo(r + f, face_y)
            .threePointArc((r + 0.2929 * f, face_y + s * 0.2929 * f), (r, face_y + s * f)).close()
            .revolve(360, (0, 0, 0), (0, 1, 0))).translate((cx, 0, 0))
    lo, hi = sorted((face_y, face_y + s * f))
    w = r + f + 2
    arm = cq.Workplane('XY').box(w, hi - lo + 0.02, 2 * w).translate((cx + arm_dir * w / 2, (lo + hi) / 2, 0))
    return ring.intersect(yslab(outline, lo - 0.01, hi + 0.01)).intersect(arm)


def link_outline(p0, p1, w0, w1, r0, r1, n=24):
    """A tapered link from p0 to p1 (x, z): end circles r0, r1 joined by tangent-ish straight sides of width w0 -> w1."""
    (x0, z0), (x1, z1) = p0, p1
    L = math.hypot(x1 - x0, z1 - z0)
    ux, uz = (x1 - x0) / L, (z1 - z0) / L
    nx, nz = -uz, ux
    pts = []
    for k in range(n + 1):                          # far end, half circle
        a = -math.pi / 2 + math.pi * k / n
        pts.append((x1 + r1 * (math.cos(a) * ux + math.sin(a) * nx), z1 + r1 * (math.cos(a) * uz + math.sin(a) * nz)))
    pts.append((x1 + w1 / 2 * nx - 0 * ux, z1 + w1 / 2 * nz))
    for k in range(n + 1):                          # near end, the other half
        a = math.pi / 2 + math.pi * k / n
        pts.append((x0 + r0 * (math.cos(a) * ux + math.sin(a) * nx), z0 + r0 * (math.cos(a) * uz + math.sin(a) * nz)))
    return _hull(pts + [(x0 + w0 / 2 * nx, z0 + w0 / 2 * nz), (x0 - w0 / 2 * nx, z0 - w0 / 2 * nz),
                        (x1 + w1 / 2 * nx, z1 + w1 / 2 * nz), (x1 - w1 / 2 * nx, z1 - w1 / 2 * nz)])


def _hull(pts):
    pts = sorted(set((round(x, 4), round(z, 4)) for x, z in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def cavity(L, r0, r1, y0, y1, keep0, keep1, skin=None):
    """A closed internal cavity in a link built from (0, 0) to (L, 0) as the hull of end circles r0 and r1: it leaves
    'skin' mm of wall on both faces and both edges, and the ends solid (keep0, keep1 mm from the joint centres). The
    link stays a closed box, which is what carries the leg's out-of-plane bending and twist for the least plastic;
    the bridge over the cavity is printed (about 20-30 mm wide)."""
    t = skin if skin is not None else P['skin']
    a, b = keep0, L - keep1
    if b - a < 10 or (y1 - y0) < 2 * t + 4:
        return None
    hw = lambda x: r0 + (r1 - r0) * x / L - t
    pts = [(a, -hw(a)), (b, -hw(b)), (b, hw(b)), (a, hw(a))]
    return yslab(pts, y0 + t, y1 - t)


def knee_cartridge_cut(y0, y1):
    """The knee seats in a lower link's knee boss (y0..y1), at the local origin: a 6201 at each end, a Ø27 web between."""
    bo, bw = KC['bearing_od'], KC['bearing_w']
    c = ycyl(bo / 2 + 0.02, y0 - 0.01, y0 + bw).union(ycyl(bo / 2 + 0.02, y1 - bw, y1 + 0.01))
    return c.union(ycyl(KC['shoulder_d'] / 2, y0 - 1, y1 + 1))


# ----------------------------------------------------------------------------------- printed parts

RS04_LUG0, RS04_DOWELS = -15.0, (3.0, 183.0)     # in the vendor STEP's own frame: first M4 lug, the two Ø5 locating holes


def lug_angles(front: bool = True):
    """The 10 lug screws' angles (deg, from +x, ccw in x-z) round the front or rear motor; the rear mirrors the front."""
    th0, _ = lug_clock()
    a = [th0 + 36 * j for j in range(10)]
    return a if front else [180.0 - v for v in a]


def dowel_angles(front: bool = True):
    """The motor's two Ø5 locating holes (deg) at the same clocking: a placed STEP angle a shows at -(a + turn)."""
    th0, _ = lug_clock()
    turn = -RS04_LUG0 - th0
    a = [-(d + turn) for d in RS04_DOWELS]
    return a if front else [180.0 - v for v in a]


def step_turn(front: bool = True):
    """How far to turn the vendor STEP about its own axis so its lugs land on lug_angles()."""
    th0 = lug_angles(front)[0]
    return -RS04_LUG0 - th0


@functools.lru_cache(maxsize=1)
def lug_clock():
    """The motors' lug pattern rotation (deg) that puts both stop posts between lug screws (10 x M4 on PCD 106)."""
    a_out, a_in = stop_post_angles()
    best = None
    for k in range(360):
        th = k * 0.5
        lugs = [th + 36 * j for j in range(10)]
        gap = min(min(abs(((a - l) + 180) % 360 - 180) for l in lugs) for a in (a_out, a_in))
        if best is None or gap > best[0]:
            best = (gap, th)
    return best[1], best[0]


UPPER_HUB_R, UPPER_EYE_R = 36.0, 20.0


def upper_half_width(r: float) -> float:
    """The upper link's half-width at a distance r from the motor axis: its outline is the hull of the hub and eye
    circles (and the w0/w1 sides), so near the hub the circle's tangent sets it."""
    L, r0, r1 = P['l1'], UPPER_HUB_R, UPPER_EYE_R
    sb = (r0 - r1) / L                                    # the external tangent's slope
    tangent = (r0 - (r0 - r1) * r / L) / math.sqrt(1 - sb * sb)
    sides = P['upper_w0'] / 2 + (P['upper_w1'] - P['upper_w0']) / 2 * r / L
    return max(tangent, sides)


def stop_post_angles():
    """Where the front motor's two stop posts sit (deg from +x about A): the sleeve (radius s) on a post at radius r
    touches the link's edge when r sin(t) = half_width(r cos(t)) + s, t from the link's axis; solved by bisection."""
    r, sr = P['stop_r'], TPU_SLEEVE[0] / 2
    lo, hi = 0.0, math.pi / 2
    for _ in range(60):
        t = (lo + hi) / 2
        if r * math.sin(t) < upper_half_width(r * math.cos(t)) + sr:
            lo = t
        else:
            hi = t
    half = math.degrees(hi)
    return P['knee_out_deg'] + half, P['knee_in_deg'] - half


def hip_frame():
    """The hip frame (printed PA6-CF): one web holding both motors on their output-side lugs (10 x M4) and a 61812
    support bearing each around the output adapters' journals, so leg bending goes into the frame, not into the
    motors' 61810. Flanges top and bottom run inwards to the body's centre plane and carry it (6 x M5 inserts in
    their ends: the body, or the test rig's carriage). Four stop posts (M8 inserts) with TPU sleeves limit the upper
    links. A cable pass between the motors for the wheel and motor leads. Printed web-down: it fits the bed turned
    45 deg."""
    yf0, yf1 = Y['frame']
    mi = gmi.motor_interface(MOTOR)
    b = mi['case']['bolts']
    ring_r = max(b['pcd'] / 2 + gmi.clear(b['thread']) + 4.5, AC['bearing_od'] / 2 + 6)
    (ax, _), (bx, _) = motors()
    fl_t, fl_x = 7.0, 95.0
    web = ycyl(ring_r, yf0, yf1, ax).union(ycyl(ring_r, yf0, yf1, bx)).union(
        cq.Workplane('XY').box(2 * ax, yf1 - yf0, 2 * ring_r).translate((0, (yf0 + yf1) / 2, 0)))
    zf = ring_r                                              # flanges: z from ring_r .. ring_r + fl_t (above the motors' Ø120)
    web = web.union(cq.Workplane('XY').box(2 * fl_x, yf1 - yf0, 2 * (zf + fl_t)).translate((0, (yf0 + yf1) / 2, 0)))
    yc = Y['centre_plane']
    for s in (1, -1):
        fl = cq.Workplane('XY').box(2 * fl_x, yf0 - yc, fl_t).translate((0, (yf0 + yc) / 2, s * (zf + fl_t / 2)))
        web = web.union(fl)
        for x in (-fl_x + 12, 0.0, fl_x - 12):                # end bosses with M5 inserts (the body or the rig)
            zb = s * (zf + fl_t / 2 + 1.5)
            boss = ycyl(7.0, yc, yc + 12.0, x, zb)
            web = web.union(boss).cut(ycyl(FAST['M5']['insert_pilot'] / 2, yc - 1, yc + 11.0, x, zb))
        # a gusset between the motors (x = 0, where no motor is) from the flange down the web's inner face
        web = web.union(yslab([(-3.5, s * zf), (3.5, s * zf), (3.5, s * (zf - 34)), (-3.5, s * (zf - 34))], yf0 - 0.01, yf0 + 0.01))
        g = cq.Workplane('YZ', origin=(-3.5, 0, 0)).polyline([(yf0 + 0.01, s * zf), (yc + 18, s * zf), (yf0 + 0.01, s * (zf - 34))]).close().extrude(7.0)
        web = web.union(g)
    for (px, pz) in stop_posts():                             # bosses round the stop posts (they sit at the web's edge)
        web = web.union(ycyl(11.0, yf0, yf1, px, pz))
    # the motors: lug screws (counterbored from the leg side, deep so a stocked length engages), the bore
    for mx, front in ((ax, True), (bx, False)):
        for a in lug_angles(front):
            x, z = mx + b['pcd'] / 2 * math.cos(math.radians(a)), b['pcd'] / 2 * math.sin(math.radians(a))
            web = web.cut(ycyl(gmi.clear(b['thread']) / 2, yf0 - 1, yf1 + 1, x, z))
            web = web.cut(ycyl(gmi.clear(b['thread']) * 0.95, yf1 - LUG_CB, yf1 + 1, x, z))
        for a in dowel_angles(front):                        # Ø5 steel dowels into the motor's locating holes
            x, z = mx + b['pcd'] / 2 * math.cos(math.radians(a)), b['pcd'] / 2 * math.sin(math.radians(a))
            web = web.cut(ycyl(2.5 - 0.03, yf0 - 1, yf0 + 12.0, x, z))
        web = web.cut(ycyl(AC['bearing_od'] / 2 + 0.3, yf0 - 1, Y['bearing'][0], mx))          # the 61812 slides in from the
        web = web.cut(ycyl(AC['bearing_od'] / 2, Y['bearing'][0] - 0.01, Y['bearing'][1], mx))   # motor side, is pressed for its
        web = web.cut(ycyl(AC['lip_d'] / 2, Y['bearing'][1] - 0.01, yf1 + 1, mx))              # last 10 mm, stops on the lip
    # stop posts: M8 heat-set inserts for 10 mm shoulder screws, at the four stop positions
    for (px, pz) in stop_posts():
        web = web.cut(ycyl(4.8, yf1 - 16.0, yf1 + 1, px, pz))        # M8 insert (94459A778, 12.7 long): Ø9.6, 16 deep
    web = web.cut(ycyl(9.0, yf0 - 1, yf1 + 1, 0.0, 0.0))                # cable pass between the motors
    return web


def stop_posts():
    """(x, z) of the four stop posts on the frame."""
    (ax, _), (bx, _) = motors()
    a_out, a_in = stop_post_angles()
    r = P['stop_r']
    pts = []
    for a in (a_out, a_in):
        pts.append((ax + r * math.cos(math.radians(a)), r * math.sin(math.radians(a))))
        pts.append((bx - r * math.cos(math.radians(a)), r * math.sin(math.radians(a))))   # mirrored about x = 0
    return pts


def upper_link():
    """Upper link (printed PA6-CF, flat): the AO-L face at the motor (8 x M5 from the outer face, heads proud), and
    at the knee an eye boss standing EYE_BOSS proud of the inner face: two steel sleeves end to end for the knee's
    shoulder screw, then a pocket for its M10 nyloc. Built for the front motor, pointing along +x from the origin (the
    rear one is the same part)."""
    l1, t = P['l1'], P['upper_t']
    out = link_outline((0, 0), (l1, 0), P['upper_w0'], P['upper_w1'], UPPER_HUB_R, UPPER_EYE_R)
    u = yslab(out, 0.0, t).union(ycyl(UPPER_EYE_R - 0.5, -EYE_BOSS, 0.01, l1, 0))   # inside the outline's polygon: no slivers
    u = u.union(boss_fillet(out, 0.0, -1, r=UPPER_EYE_R - 0.5, f=5.0, cx=l1, arm_dir=-1))   # where the arm meets the boss
    u = u.cut(gmi.place(gmi.std_face_mate('L', depth=t + 2), (0, 0, 0), (0, 1, 0)))
    # the 8 M5 heads sit proud on the hub's outer face (no lower link ever passes over a hub: build_leg's clash
    # sweep), so the hub keeps its full thickness where the leg's out-of-plane moment is largest
    u = u.cut(ycyl(EYE_SLEEVE[0] / 2 - 0.02, eye_sleeve_end(), t + 1, l1, 0))   # the steel sleeves, pressed in from outside
                                                                              # (the inner one's end in the nut pocket: the nut clamps steel)
    u = u.cut(ycyl(6.03, -EYE_BOSS - 1, t + 1, l1, 0))                     # the shoulder: 12 mm (through the nut pocket)
    if P['hollow']:
        cv = cavity(l1, UPPER_HUB_R, UPPER_EYE_R, 0.0, t, UPPER_HUB_R + 10.0, UPPER_EYE_R + 10.0)
        u = u.cut(cv) if cv is not None else u
        if cv is not None:                                                   # the wheel's cable (used on the rear link)
            u = u.cut(cq.Workplane('XY').box(CABLE_EXIT[0], t / 2, CABLE_EXIT[1]).translate((l1 - UPPER_EYE_R - 14.0, t * 0.75, 0)))
            u = u.cut(cq.Workplane('XY').box(CABLE_EXIT[0], t / 2, CABLE_EXIT[1]).translate((CABLE_OUT_R, t * 0.25, 0)))
    top = eye_sleeve_end() + 0.5                                           # the pocket reaches just past the sleeve's end
    hexa = cq.Workplane('XZ', origin=(0, top, 0)).center(l1, 0).polygon(6, M10_NUT[0] / math.cos(math.pi / 6) + 0.3).extrude(top + EYE_BOSS + 0.5)
    return u.cut(hexa)


def eye_sleeve_end():
    """y of the inner end of an upper link's eye sleeves: where the knee's nut bears."""
    return P['upper_t'] - EYE_SLEEVES * EYE_SLEEVE[2]


def front_link():
    """Front lower link (printed PA6-CF, flat on its inner face): the knee boss with two 6201s reaching out over the
    wheel link's layer, a 16 mm body, and the apex eye reaching in over the upper links' layer with two 61812s 28 mm
    apart on the wheel link's hub (each pressed against a central web), so the apex carries the wheel's out-of-plane
    moment into both sides of the loop. Built from the knee (origin) towards +x."""
    l2 = P['l2']
    y0, y1 = Y['front_link']
    e0, e1 = Y['apex_eye']
    kb0, kb1 = Y['knee_boss']
    r_eye = AC['bearing_od'] / 2 + 6.0
    outline = link_outline((0, 0), (l2, 0), P['front_w'], P['front_w'] + 12, KC['hub_od'] / 2, r_eye)
    f = yslab(outline, y0, y1)
    f = f.union(ycyl(KC['hub_od'] / 2, kb0, kb1)).union(boss_fillet(outline, y1, +1)).union(ycyl(r_eye, e0, e1, l2))
    f = f.cut(knee_cartridge_cut(kb0, kb1))
    ao, ai = Y['apex_bearing'], Y['apex_bearing_in']
    f = f.cut(ycyl(36.0, e0 - 1, e1 + 1, l2, 0))                            # Ø72 web between the seats: the outer races' shoulders
    f = f.cut(ycyl(AC['bearing_od'] / 2 + 0.02, ao[0], e1 + 1, l2))          # outer 61812, pressed from the outer side
    f = f.cut(ycyl(AC['bearing_od'] / 2 + 0.02, e0 - 1, ai[1], l2))          # inner 61812, pressed from the inner side
    if P['hollow']:
        cv = cavity(l2, KC['hub_od'] / 2, r_eye, y0, y1, KC['hub_od'] / 2 + 10.0, r_eye + 10.0)
        f = f.cut(cv) if cv is not None else f
    return f


def wheel_link():
    """Wheel link (printed PA6-CF, flat on its outer face): the knee boss with two 6201s reaching in over the front
    link's layer, a 24 mm body, and the apex foot: the BotWheel's Ø50 boss in a recess in the outer face, its 4 x M6 x 40
    through the foot from the inner side (heads inside the hub), and the hollow hub pointing in through the front link's
    apex eye: Ø60 for the 61812's inner race against a Ø64 shoulder, a DIN 471-60 circlip groove at its end, Ø48 inside
    so the wheel's cable and a hex key pass. Built from the knee (origin) towards +x."""
    l2 = P['l2']
    y0, y1 = Y['wheel_link']
    kb0, kb1 = Y['knee_boss']
    w = gmi.motor_interface(WHEEL)
    r_foot = 42.0
    outline = link_outline((0, 0), (l2, 0), P['wheel_w1'], P['wheel_w0'], KC['hub_od'] / 2, r_foot)
    k = yslab(outline, y0, y1)
    k = k.union(ycyl(KC['hub_od'] / 2, kb0, kb1)).union(boss_fillet(outline, y0, -1))   # the boss reaches in, filleted
    k = k.cut(knee_cartridge_cut(kb0, kb1))
    h0, h1 = Y['hub']
    ab0, ab1 = Y['apex_bearing']
    k = k.union(ycyl(32.0, ab1, h1 + 0.01, l2)).union(ycyl(30.0, h0, ab1 + 0.01, l2))   # Ø64 shoulder, then the Ø60 journal
    c0, c1 = Y['circlip']
    k = k.cut(ycyl(31.0, c0, c1, l2).cut(ycyl(28.5, c0 - 1, c1 + 1, l2)))                 # the circlip groove (Ø57)
    k = k.cut(ycyl(24.0, h0 - 1, h1 - 0.01, l2))                                            # Ø48 bore: cable and hex key
    boss = w['case']['boss_d'] or 50.0
    k = k.cut(ycyl(boss / 2 + 0.03, Y['wheel_boss'], y1 + 1, l2))
    bw = w['case']['bolts']
    for (x, z) in gmi.circle_pts(bw['pcd'], bw['count'] or 4, 45.0):
        k = k.cut(ycyl(gmi.clear('M6') / 2, h1 - 1, y1 + 1, l2 + x, z))                     # heads on the foot's inner face
    k = k.cut(ycyl(11.0, h1 - 1, y1 + 1, l2))                                               # the cable: Ø22 through the foot
    if P['hollow']:
        cv = cavity(l2, KC['hub_od'] / 2, r_foot, y0, y1, KC['hub_od'] / 2 + 10.0, r_foot + 10.0)
        k = k.cut(cv) if cv is not None else k
        yc = (y0 + y1) / 2
        k = k.cut(cq.Workplane('YZ', origin=(l2 - r_foot - 14.0, 0, 0)).center(yc, 0).circle(CABLE_PASS / 2).extrude(r_foot + 14.0))   # foot hole -> cavity
        k = k.cut(cq.Workplane('XY').box(CABLE_EXIT[0], y1 - y0, CABLE_EXIT[1]).translate((CABLE_EXIT_X, (y0 + yc) / 2 - 1, 0)))       # out of the inner face
    return k


def apex_spacer():
    """The ring between the two apex 61812s' inner races (printed PA6-CF): with the hub's shoulder and the circlip it
    holds both inner races in place. On the apex axis, at the origin."""
    a, b = Y['apex_bearing_in'][1], Y['apex_bearing'][0]
    return ycyl(33.0, a + 0.1, b - 0.1).cut(ycyl(30.1, a - 1, b + 1))


# the BotWheel's cable (phases 3 x 18 AWG in a sleeve + the hall/encoder lead): through the wheel link's cavity, round the
# rear knee, through the rear upper link's cavity, into the body past the hip frame's edge
CABLE_D = 9.0                                             # the two leads together, sleeved (interfaces.json cables: 7.5 + 4.5)
CABLE_PASS = 18.0                                         # the channel from the foot's centre hole into the wheel link's cavity
CABLE_EXIT = (22.0, 16.0)                                 # slots through a link's wall (along the link, across it)
CABLE_EXIT_X = 23.0 + 22.0                                # the wheel link's exit, from the knee
CABLE_OUT_R = 90.0                                        # where the cable leaves the rear upper link for the body: past
                                                         # the stop posts (58) and the frame's edge (62)


def cable(phi1: float, phi2: float):
    """The wheel's cable at a pose, as a swept tube clipped along the outside of the loop: out of the hub's inner end
    at the axle, out under the apex eye, along the wheel link's outer edge, round the outside of the rear knee (on the
    bisector of the knee's outside angle, clear of both eyes at any knee angle), along the rear upper link's outer edge,
    and into the body 90 mm from the hip axis (past the stop posts and the frame's edge). The wrap at the knee and the
    loop at the hip take the joints' swing: a route to try on the rig."""
    fr, j = link_frames(phi1, phi2)
    loop = [j[k] for k in 'ACEDB']                                  # the loop's outline, x-z
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(loop, loop[1:] + loop[:1]))
    turn = 1.0 if area > 0 else -1.0                                # +1: counter-clockwise in x-z

    def unit(v):
        n = math.hypot(*v)
        return (v[0] / n, v[1] / n)

    def outward(p, q):
        """The outward normal of the loop's edge p -> q (the side away from the loop's inside)."""
        d = unit((q[0] - p[0], q[1] - p[1]))
        return (turn * d[1], -turn * d[0]), d

    E, D, B = j['E'], j['D'], j['B']
    n_w, d_w = outward(E, D)                                        # the wheel link, traversed apex -> knee
    n_u, d_u = outward(D, B)                                        # the rear upper link, knee -> hip
    bis = (n_w[0] + n_u[0], n_w[1] + n_u[1])
    if math.hypot(*bis) < 0.3:                                      # folded flat: straight past the knee's tip
        bis = (d_w[0] - d_u[0], d_w[1] - d_u[1])
    bis = unit(bis)
    l1, l2 = P['l1'], P['l2']
    w0, w1 = Y['wheel_link']
    wm = (w0 + w1) / 2
    hw = lambda x: KC['hub_od'] / 2 + (42.0 - KC['hub_od'] / 2) * x / l2     # the wheel link's half-width, x from the knee
    r = CABLE_D / 2 + 2.0
    r_knee = max(KC['hub_od'] / 2, UPPER_EYE_R) + r + 4.0           # round the knee, clear of the boss and the eye

    def on(p0, d, s, n, off, y):
        return cq.Vector(p0[0] + s * d[0] + off * n[0], y, p0[1] + s * d[1] + off * n[1])
    y_hub = Y['hub'][0] - 4.0
    pts = [cq.Vector(E[0], y_hub, E[1]),
           on(E, d_w, 0.0, n_w, AC['bearing_od'] / 2 + 12.0, y_hub),
           on(E, d_w, 30.0, n_w, hw(l2 - 30) + r, wm),
           on(E, d_w, l2 / 2, n_w, hw(l2 / 2) + r, wm),
           on(E, d_w, l2 - 45.0, n_w, hw(45.0) + r, wm),
           on(D, d_w, 0.0, n_w, r_knee, wm),
           on(D, d_w, 0.0, bis, r_knee, (Y['upper'][1] + w0) / 2),
           on(D, d_u, 0.0, n_u, r_knee, P['upper_t'] / 2),
           on(D, d_u, 40.0, n_u, upper_half_width(l1 - 40.0) + r, P['upper_t'] / 2),
           on(D, d_u, l1 - CABLE_OUT_R - 10.0, n_u, upper_half_width(CABLE_OUT_R + 10.0) + r, P['upper_t'] / 2),
           on(D, d_u, l1 - CABLE_OUT_R - 5.0, n_u, upper_half_width(CABLE_OUT_R + 5.0) + r, -20.0),
           on(D, d_u, l1 - CABLE_OUT_R, n_u, upper_half_width(CABLE_OUT_R) + r, -60.0)]
    path = cq.Workplane('XY').spline([(p.x, p.y, p.z) for p in pts], includeCurrent=False)
    prof = cq.Workplane(cq.Plane(origin=pts[0], xDir=cq.Vector(1, 0, 0), normal=(pts[1] - pts[0]).normalized())).circle(CABLE_D / 2)
    return prof.sweep(path, transition='round')


def cable_check(heights=(105, 130, 170, 220, 270, 320, 370, 390), min_mm3=5.0):
    """Where the drawn cable route runs into a part, at a few stances: {height: [[part, mm3], ...]}. A real cable gives
    way a little; a route that cuts through a link at some stance needs moving there."""
    out = {}
    for h in heights:
        phi = stance(h)
        c = cable(*phi)
        hits = []
        for n, (sh, _) in assembly(*phi).items():
            if sh is None or n in ('wheel_cable', 'wheel_hub') or n.startswith('motor'):
                continue
            try:
                v = c.intersect(sh).val().Volume()
            except Exception:
                v = 0.0
            if v > min_mm3:
                hits.append([n, round(v)])
        out[h] = hits
    return out


KNEE_PIN_STOCK = (50, 55, 60, 70, 80, 90, 100)             # ISO 7379 Ø12 shoulder lengths McMaster stocks (mm)
LUG_CB = 10.0                                            # the hip frame's M4 counterbores: an M4 x 20 then takes 5.9 mm of
                                                         # the RS-04's 7 mm lug threads (8 mm left it 3.9)


def knee_pin_length():
    """The knee's shoulder screw: the longest stocked shoulder that still lets the nut clamp the stack (head on the
    outer washer, nut on the eye sleeve's end), and how far the shoulder's end sits from the nut (the thread reaches through it)."""
    room = Y['knee_boss'][1] + 2.0 - eye_sleeve_end()                 # from the head's washer to the nut's face (the sleeves' end)
    L = max(l for l in KNEE_PIN_STOCK if l <= room - 0.5)
    return L, round(room - L, 2)


def stop_sleeve():
    """TPU 95A sleeve on a stop post's shoulder: the upper link lands on it."""
    od, idd = TPU_SLEEVE
    return ycyl(od / 2, 0.0, 19.0).cut(ycyl(idd / 2 + 0.1, -1, 20.0))


# ----------------------------------------------------------------------------------- bought parts (envelopes)

def bearing(d, D, w, y0, x=0.0, z=0.0):
    return ycyl(D / 2, y0, y0 + w, x, z).cut(ycyl(d / 2, y0 - 1, y0 + w + 1, x, z))


def shoulder_screw(d, length, thread_len, head_y, x, z, inward=True):
    """ISO 7379 envelope: head outboard at head_y, shoulder and thread towards -y."""
    hd, hh = ISO7379_HEAD[int(d)]
    td = {12: 10.0, 10: 8.0}[int(d)]
    s = ycyl(hd / 2, head_y, head_y + hh, x, z).union(ycyl(d / 2, head_y - length, head_y, x, z))
    return s.union(ycyl(td / 2, head_y - length - thread_len, head_y - length, x, z))


def botwheel():
    """The BotWheel from its drawing (no STEP without an Onshape login): tyre Ø171.3 x 44.6, a closed hub, the stator
    boss Ø50 x 5 on the inner side."""
    w = gmi.motor_interface(WHEEL)
    od = w['od'] or 171.3
    t0, t1 = Y['tyre']
    tyre = ycyl(od / 2, t0, t1).cut(ycyl(od / 2 - 16, t0 - 1, t1 + 1))
    hub = ycyl(od / 2 - 16, t0 + 3, t1 - 3).union(ycyl(32.0, Y['wheel_boss'] + 5.0, t0 + 3))
    boss = ycyl(25.0, Y['wheel_boss'], Y['wheel_boss'] + 5.0)
    return tyre, hub.union(boss)


@dataclass
class Leg:
    parts: dict          # printed, in their own frames (see the builders)
    meta: dict
    bought: dict         # name -> (shape in its link frame, link, mass_g, note)


@functools.lru_cache(maxsize=1)
def leg_parts() -> Leg:
    parts, meta = {}, {}

    def add(name, shape, material, qty, note, fea='pa6_cf_xy', solid=True):
        parts[name], meta[name] = shape, {'material': material, 'qty': qty, 'note': note, 'fea_material': fea, 'solid': solid}

    ad, adi = gmi.output_adapter(MOTOR, 'L')
    add('hip_frame', hip_frame(), 'pa6-cf', 1, 'printed PA6-CF web-down (turned 45 deg on the bed), 100 % solid; '
        '20 x M4 into the motors, 2 x 61812 pressed in (6 x M3 + washers), 6 x M5 inserts in the flange ends, 4 x M8 inserts for the stop posts')
    add('output_adapter', gmi.place(ad, (0, Y['motor_out'], 0), (0, 1, 0)), 'pa6-cf', 2, adi['note'], fea='pa6_cf_z')
    add('upper_link', upper_link(), 'pa6-cf', 2, f"printed PA6-CF flat, {P['upper_t']:.0f} mm, 100 % solid; 8 x M5 into the adapter; "
        'the knee shoulder screw clamped by an M10 nyloc in a pocket')
    add('front_link', front_link(), 'pa6-cf', 1, f"printed PA6-CF flat on its inner face, {P['front_t']:.0f} mm body; two 6201-2RS at the knee, "
        'two 61812 at the apex (pressed against a central web)')
    add('wheel_link', wheel_link(), 'pa6-cf', 1, f"printed PA6-CF flat on its outer face, {P['wheel_t']:.0f} mm body; two 6201-2RS at the knee; "
        'the BotWheel in its outer face (4 x M6 from inside the hub), the hub for the apex 61812 (DIN 471-60 circlip)')
    add('apex_spacer', apex_spacer(), 'pa6-cf', 1, 'printed PA6-CF ring between the apex 61812s\' inner races', fea=None)
    add('stop_sleeve', stop_sleeve(), 'tpu95', 4, 'printed TPU 95A, on the stop posts', fea=None, solid=True)
    bought = {}
    return Leg(parts, meta, bought)


# ----------------------------------------------------------------------------------- posing

LINKS = ('frame', 'upper_front', 'upper_rear', 'front_link', 'wheel_link', 'wheel')


def link_frames(phi1: float, phi2: float):
    """Where each moving link is: origin (x, z) and rotation (deg about +y as cadquery turns it) for each link."""
    j = fk(phi1, phi2)
    (ax, az), (bx, bz) = j['A'], j['B']
    C, Dp, E = j['C'], j['D'], j['E']
    deg = math.degrees
    # cadquery's rotation about +y turns +x towards -z, so a link pointing at angle a (ccw from +x in x-z) is turned -a
    ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
    return {
        'upper_front': ((ax, az), -deg(ang((ax, az), C))),
        'upper_rear': ((bx, bz), -deg(ang((bx, bz), Dp))),
        'front_link': (C, -deg(ang(C, E))),
        'wheel_link': (Dp, -deg(ang(Dp, E))),
        'wheel': (E, 0.0),
    }, j


def place(shape, origin, rot_deg):
    s = shape.rotate((0, 0, 0), (0, 1, 0), rot_deg) if rot_deg else shape
    return s.translate((origin[0], 0, origin[1]))


def assembly(phi1: float, phi2: float, with_bought: bool = True):
    """Every part of the leg at motor angles phi1, phi2: {name: (shape, material/kind)} in the module frame."""
    L = leg_parts()
    fr, j = link_frames(phi1, phi2)
    out = {}
    out['hip_frame'] = (L.parts['hip_frame'], 'made')
    (ax, _), (bx, _) = motors()
    out['output_adapter_front'] = (L.parts['output_adapter'].translate((ax, 0, 0)), 'made')
    out['output_adapter_rear'] = (L.parts['output_adapter'].translate((bx, 0, 0)), 'made')
    out['upper_link_front'] = (place(L.parts['upper_link'], *fr['upper_front']), 'made')
    out['upper_link_rear'] = (place(L.parts['upper_link'], *fr['upper_rear']), 'made')
    out['front_link'] = (place(L.parts['front_link'], *fr['front_link']), 'made')
    out['wheel_link'] = (place(L.parts['wheel_link'], *fr['wheel_link']), 'made')
    for k, (px, pz) in enumerate(stop_posts()):
        out[f'stop_sleeve_{k + 1}'] = (L.parts['stop_sleeve'].translate((px, 0, pz)), 'made')
    out['apex_spacer'] = (L.parts['apex_spacer'].translate((j['E'][0], 0, j['E'][1])), 'made')
    if with_bought:
        for name, (shape, kind) in bought_parts(fr, j).items():
            out[name] = (shape, kind)
    return out


@functools.lru_cache(maxsize=1)
def motor_model():
    """The RS-04 (vendor STEP when here, slow to load: cached)."""
    return gmi.motor_body(MOTOR)


def _phis(j):
    """The motor angles back from a joint dict (for helpers that take angles)."""
    (ax, az), (bx, bz) = j['A'], j['B']
    return (math.atan2(j['C'][1] - az, j['C'][0] - ax), _rear(math.atan2(j['D'][1] - bz, j['D'][0] - bx)))


def _rear(a):
    return a - 2 * math.pi if a > 0 else a


def screw(d, length, head_d, head_h, at, axis_y_sign, x, z):
    """A socket head cap screw: head from 'at' outwards (-axis), shank 'length' along axis_y_sign."""
    if axis_y_sign < 0:
        return ycyl(head_d / 2, at, at + head_h, x, z).union(ycyl(d / 2, at - length, at, x, z))
    return ycyl(head_d / 2, at - head_h, at, x, z).union(ycyl(d / 2, at, at + length, x, z))


SCREWS = {   # what each screw group is, its size, and where its head seats (catalog/hardware.json keys)
    'lugs': ('screw_m4x20', 'M4 x 20 into the motors\' lugs, heads 10 mm down in the hip frame'),
    'links': ('screw_m5x40', 'M5 x 40 through the upper links\' hubs into the adapters\' inserts, heads proud'),
    'outputs': ('screw_m5x30', 'M5 x 30 through the adapters into the motors\' output flanges'),
    'wheel': ('screw_m6x30', 'M6 x 30 from inside the hub into the BotWheel\'s flange'),
}


def screw_groups(fr, j):
    """Every screw of the leg as one envelope per group."""
    out = {}
    (ax, _), (bx, _) = motors()
    yf0, yf1 = Y['frame']
    b = gmi.motor_interface(MOTOR)['case']['bolts']
    lugs = None
    for mx, front in ((ax, True), (bx, False)):
        for a in lug_angles(front):
            x, z = mx + b['pcd'] / 2 * math.cos(math.radians(a)), b['pcd'] / 2 * math.sin(math.radians(a))
            sc = screw(4.0, 20.0, 7.0, 4.0, yf1 - LUG_CB, -1, x, z)
            lugs = sc if lugs is None else lugs.union(sc)
    out['screws_lugs'] = lugs
    ao = STD['AO-L']
    links = None
    for key in ('upper_front', 'upper_rear'):
        (ox, oz), rot = fr[key]
        for (x, z) in gmi.circle_pts(ao['pcd'], ao['bolts'], 360.0 / ao['bolts'] / 2):
            sc = screw(5.0, 40.0, 8.5, 5.0, P['upper_t'], -1, ox + x, oz + z)
            links = sc if links is None else links.union(sc)
    out['screws_links'] = links
    ex, ez = j['E']
    wheel = None
    for (x, z) in gmi.circle_pts(36.0, 4, 45.0):
        sc = screw(6.0, 30.0, 10.0, 6.0, Y['wheel_link'][0], 1, ex + x, ez + z)
        wheel = sc if wheel is None else wheel.union(sc)
    out['screws_wheel'] = wheel
    return out


def bought_parts(fr, j):
    """The bought parts, placed: motors (vendor STEP when here), bearings, shoulder screws, nuts, the wheel."""
    out = {}
    (ax, _), (bx, _) = motors()
    body, how = motor_model()
    for name, mx, front in (('motor_front', ax, True), ('motor_rear', bx, False)):
        m = body.rotate((0, 0, 0), (0, 0, 1), step_turn(front)) if how == 'step' else body
        out[name] = (gmi.place(m, (mx, Y['motor_out'], 0), (0, 1, 0)), 'bought')
        out[f'bearing_61812_{name[6:]}'] = (bearing(60, 78, 10, Y['bearing'][0], mx), 'bought')
    kb0, kb1 = Y['knee_boss']
    for key, (p, _) in (('front', fr['front_link']), ('rear', fr['wheel_link'])):
        x, z = p
        out[f'knee_6201_{key}_in'] = (bearing(12, 32, 10, kb0, x, z), 'bought')
        out[f'knee_6201_{key}_out'] = (bearing(12, 32, 10, kb1 - 10, x, z), 'bought')
        out[f'knee_pin_{key}'] = (shoulder_screw(12, knee_pin_length()[0], 16, kb1 + 2.0, x, z), 'bought')
        out[f'knee_washer_{key}'] = (bearing(13, 20, 2, kb1, x, z).union(bearing(13, 20, 2, P['upper_t'], x, z)), 'bought')   # DIN 433 M12
        out[f'knee_spacer_{key}'] = (bearing(12.6, 15.9, kb1 - kb0 - 2 * KC['bearing_w'], kb0 + KC['bearing_w'], x, z), 'bought')   # 6061 tube
    for key in ('upper_front', 'upper_rear'):                       # the steel sleeves in the upper links' knee eyes
        (ox, oz), rot = fr[key]
        a = math.radians(-rot)
        out[f'eye_sleeve_{key[6:]}'] = (bearing(EYE_SLEEVE[1], EYE_SLEEVE[0], EYE_SLEEVES * EYE_SLEEVE[2], eye_sleeve_end(),
                                                ox + P['l1'] * math.cos(a), oz + P['l1'] * math.sin(a)), 'bought')
        nut_face = eye_sleeve_end()                                    # the nut bears on the sleeves' end, steel on steel
        nut = (cq.Workplane('XZ', origin=(0, nut_face, 0)).center(P['l1'], 0).polygon(6, M10_NUT[0] / math.cos(math.pi / 6))
               .extrude(M10_NUT[1]).cut(ycyl(5.0, nut_face - M10_NUT[1] - 1, nut_face + 1, P['l1'], 0)))
        out[f'knee_nut_{key}'] = (place(nut, (ox, oz), rot), 'bought')   # in its link's hex pocket, turned with it
    ex, ez = j['E']
    out['apex_61812'] = (bearing(60, 78, 10, Y['apex_bearing'][0], ex, ez).union(bearing(60, 78, 10, Y['apex_bearing_in'][0], ex, ez)), 'bought')
    out['apex_circlip'] = (bearing(57.0, 66.0, 2.0, Y['circlip'][0] + 0.05, ex, ez), 'bought')
    for (px, pz) in stop_posts():
        out.setdefault('stop_posts', (None, 'bought'))
        s = shoulder_screw(10, 20, 13, 19.5, px, pz)
        out['stop_posts'] = (s if out['stop_posts'][0] is None else out['stop_posts'][0].union(s), 'bought')
    for name, shape in screw_groups(fr, j).items():
        out[name] = (shape, 'bought')
    try:
        out['wheel_cable'] = (cable(*[math.atan2(fr['upper_front'][0][1], 1) * 0 + v for v in _phis(j)]), 'bought')
    except Exception:                                    # a sweep that does not close is drawn without the cable
        pass
    tyre, hub = botwheel()
    out['wheel_tyre'] = (tyre.translate((ex, 0, ez)), 'bought')
    out['wheel_hub'] = (hub.translate((ex, 0, ez)), 'bought')
    return out


STATIC = ('hip_frame', 'output_adapter', 'motor_', 'bearing_61812', 'stop_')     # fixed to the frame (the adapters turn
                                                                                 # in place: mated to their motors)


def clashes(heights=(130, 200, 260, 320, 380), leans=(-20, 0, 20), min_mm3=5.0, with_bought=True):
    """Pairs of parts that overlap at a set of stances. Returns [[a, b, mm3, (height, lean)], ...]. The motors are
    their envelopes here (the vendor model is slow to intersect and nothing that moves comes near them); two fixed
    parts are checked once."""
    import itertools
    out = []
    real = gmi.STEP_FRAMES.pop(MOTOR, None)
    motor_model.cache_clear()
    try:
        first = True
        for h in heights:
            for lean in (leans if 200 <= h <= 340 else (0,)):
                phi = stance(h, lean)
                fo, fi, ro, ri = stop_angles()
                if phi is None or not (fi <= phi[0] <= fo) or not (ro <= phi[1] <= ri):
                    out.append(['out of range', '', 0, (h, lean)])       # past a stop: the stop is doing its job
                    continue
                asm = {n: s for n, (s, _) in assembly(*phi, with_bought=with_bought).items()
                       if s is not None and n != 'wheel_cable'}                  # the cable has its own check: cable_check()
                boxes = {n: (s.val() if hasattr(s, 'val') else s).BoundingBox() for n, s in asm.items()}
                for (n1, s1), (n2, s2) in itertools.combinations(asm.items(), 2):
                    if not first and n1.startswith(STATIC) and n2.startswith(STATIC):
                        continue
                    b1, b2 = boxes[n1], boxes[n2]
                    if b1.xmax < b2.xmin or b2.xmax < b1.xmin or b1.ymax < b2.ymin or b2.ymax < b1.ymin or b1.zmax < b2.zmin or b2.zmax < b1.zmin:
                        continue
                    if _mated(n1, n2):
                        continue
                    try:
                        v = s1.intersect(s2).val().Volume()
                    except Exception:
                        v = 0.0
                    if v > min_mm3:
                        out.append([n1, n2, round(v, 1), (h, lean)])
                first = False
    finally:
        if real:
            gmi.STEP_FRAMES[MOTOR] = real
        motor_model.cache_clear()
    return out


MATES = [('output_adapter_front', 'motor_front'), ('output_adapter_rear', 'motor_rear'), ('hip_frame', 'motor_front'),
         ('hip_frame', 'motor_rear'), ('hip_frame', 'bearing_61812_front'), ('hip_frame', 'bearing_61812_rear'),
         ('output_adapter_front', 'bearing_61812_front'), ('output_adapter_rear', 'bearing_61812_rear'),
         ('wheel_link', 'apex_61812'), ('front_link', 'apex_61812'), ('wheel_link', 'wheel_hub'), ('wheel_link', 'apex_circlip'),
         ('wheel_link', 'apex_spacer'), ('apex_spacer', 'apex_61812'),
         ('hip_frame', 'stop_posts'), ('stop_sleeve', 'stop_posts'), ('hip_frame', 'screws_lugs'), ('motor_', 'screws_lugs'),
         ('upper_link', 'screws_links'), ('output_adapter', 'screws_links'), ('wheel_link', 'screws_wheel'), ('wheel_hub', 'screws_wheel'),
         ('wheel_link', 'wheel_cable'),
         ('wheel_hub', 'wheel_cable'),
         ('upper_link', 'eye_sleeve'), ('eye_sleeve', 'knee_pin')]


def _mated(a, b):
    for x, y in MATES:
        if (a.startswith(x) and b.startswith(y)) or (a.startswith(y) and b.startswith(x)):
            return True
    for key in ('front', 'rear'):                      # each knee's own cartridge parts touch their links by design
        owners = {'front': ('upper_link_front', 'front_link'), 'rear': ('upper_link_rear', 'wheel_link')}[key]
        kparts = (f'knee_6201_{key}', f'knee_pin_{key}', f'knee_washer_{key}', f'knee_nut_{key}', f'knee_spacer_{key}')
        if (a.startswith(kparts) and b.startswith(owners + kparts)) or (b.startswith(kparts) and a.startswith(owners + kparts)):
            return True
    return False
