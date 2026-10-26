"""Gyropup's foam-ball turret (head payload), in CadQuery: every made part printed (D33), the bought parts as envelopes.

    .venv/bin/python cad/turret.py [designs/default.json] [--no-render]

The concept is research/turret-launcher-study.md section 8 and docs/cad-plan.md section 4: Rival-size foam balls, a
gravity hopper over an 8-pocket dial on a DJI M2006 P36, twin Snail 2305 flywheels in the horizontal plane, a 100 mm
barrel, an aiming laser on the cradle, an STS3215 ring-gear pan on a 61810-2RS bearing and an STS3215 tilt with a hard
stop at 0 deg (the barrel can never point above horizontal: kid-safety rule S5 / study 6.3).

Frames (mm). Robot frame: x forward, y left, z up, origin on the hip axis. The turret is built in its own frame T (the
same axes, origin on the pan axis at the top face of the head's turret ring = the TM mounting face) and moved up by
mount_z = bodyTop + 20 + SADDLE_T. The parts that tilt are built in the cartridge frame C (x along the barrel, the ball
path on z = 0, the dial axis on x = 0); at tilt 0 C sits PATH_T above the mount face. Pan turns about the T z axis,
tilt about a y axis through (0, PATH_T + TILT_C). Negative tilt = muzzle down; the hard stops allow 0 .. -25 deg.

How the ball moves (turret-section.png): hopper (30 balls) -> dial pocket -> a hole in the dial-housing floor -> a
curved chute that turns it forward -> the nip of the two flywheels -> the barrel. With the dial parked (a spoke over the
hole) no ball can reach the wheels.

Made parts (one function each; PA6-CF = loaded, 100 % solid; PETG = 2 mm walls, 40 % infill; TPU 95A):
  pan_base (PA6-CF)        on the TM pattern; holds the 61810 outer race, the pan servo, the DT receptacle, the pan
                           hard-stop post, the bumper tabs
  pan_clamp (PA6-CF)       clamps the 61810 outer race down (3 x M3 into inserts)
  pan_ring (PA6-CF)        the turntable: 63 T m1.25 spur gear on its rim, journal through the inner race (DIN 471-50
                           circlip below), 40 mm open centre for the cable, pan stop finger; the yoke bolts on top
  pan_pinion (PA6-CF)      21 T m1.25 on the pan servo's horn (63:21 = 3:1)
  tilt_yoke (PA6-CF)       bridge + two arms; tilt servo on the +y arm, MR126 on the -y arm, hard stops at 0 / -25 deg
  cradle (PA6-CF)          cheeks on the tilt axis, rails the cartridge sits on (CT: 2 dowels + a thumbscrew), laser tab
  cartridge_body (PA6-CF)  dial housing, drop chute, flywheel cage (motors hang under its top plate), barrel socket
  flywheel (PA6-CF)        hub on the Snail shaft; flywheel_tyre (TPU 95A) Ø40 tyre over it
  dial (PETG)              8 pockets, stirring cone, on the M2006 shaft
  hopper, hopper_lid, hopper_flap (PETG, translucent)  30 balls; fill port with a sprung flap for the dock spout
  barrel (PETG, orange tip)  Ø30 x 100, bore = ball + 1.5, two chronograph gates
  laser_mount (PETG)       ring with three M3 boresight screws, on the cradle
  bumper_ring (TPU 95A)    around the pan base
head_ring_tm(L) is the proposed replacement for the ring of build.py's head_saddle (see its docstring).
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import gmi  # noqa: E402

FAST = gmi.FAST
BED = gmi.STD['print']['bed_mm']
INSERT_DEPTH = 8.0

# ------------------------------------------------------------------------------------------------ fixed sizes (mm)
SADDLE_T = 8.0            # proposed head ring thickness (M5 inserts need 8 mm)
TM_BOLTS = [(40.0, 40.0), (-40.0, 40.0), (-40.0, -40.0), (40.0, -40.0)]      # 4 x M5 on 80 x 80
TM_DOWELS = [(52.0, 0.0), (0.0, -52.0)]                                     # 2 x Ø5, not symmetric: one way only
TM_HOLE = 45.0
# 61810-2RS (SKF): 50 x 65 x 7, 52 g. MR126-2RS: 6 x 12 x 4.
BRG = {'d': 50.0, 'D': 65.0, 'B': 7.0, 'mass_g': 52.0}
MR126 = {'d': 6.0, 'D': 12.0, 'B': 4.0, 'mass_g': 2.0}
# Feetech STS3215 (catalog feetech-sts3215-c018-12v): case 45.2 x 24.7 x 35; output centred on the 24.7 width,
# 12.35 from one end (est from the drawing: verify on a real servo); disc horn Ø20 x 3 (est).
SERVO = {'L': 45.2, 'W': 24.7, 'H': 35.0, 'shaft_from_end': 12.35, 'horn_d': 20.0, 'horn_t': 3.0, 'mass_g': 89.0}
# Snail 2305 (catalog dji-robomaster-snail-2305): Ø29, shaft 2.95; height and the 16 x 16 M3 base pattern are est.
SNAIL = {'d': 29.0, 'bell_h': 17.5, 'base_d': 25.0, 'base_h': 4.0, 'shaft_d': 2.95, 'shaft_l': 9.0, 'mass_g': 27.8}
# M2006 P36 (catalog dji-robomaster-m2006-p36, 90 g): body Ø24 x 44.5 incl. the gearbox, output shaft Ø8 x 12 (est).
M2006 = {'d': 24.0, 'L': 44.5, 'shaft_d': 8.0, 'shaft_l': 12.0, 'mass_g': 90.0}
C610 = {'size': (32.0, 49.5, 12.7), 'mass_g': 13.3}                   # x, y, z (est)
AM32 = {'size': (25.0, 13.0, 5.0), 'mass_g': 5.0}                     # catalog repeat-robotics-am32-35a-esc
LASER = {'d': 12.0, 'L': 40.0, 'mass_g': 16.0}                        # Picotronic DD520-1-24(12x40)
# Deutsch DT04-12PA-L012 flange receptacle and its DT06-12SA plug (est; check against the TE drawings)
DT = {'flange': (46.0, 3.2, 30.0), 'body': (35.0, 22.0, 22.0), 'front': (33.0, 28.0, 21.0), 'plug': (37.0, 52.0, 24.0),
      'sweep': 30.0, 'mass_g': 15.0}
NOT_MODELLED_G = {'wiring and the cable loops': 50, 'head MCU + IMU + CAN transceiver': 15, '24 -> 12 V buck': 10,
                  'chronograph emitters/receivers + hopper-full beam': 10, 'LEDs and buzzer': 15,
                  'screws, inserts, dowels, circlips, shoulder screw, springs': 35, 'CT pogo connector pair': 10}
DENS = {k: v['density_g_cm3'] for k, v in json.loads((R / 'catalog/materials.json').read_text()).items()}
PRINT_RATE_CM3_H = {'pa6-cf': 14.0, 'petg': 20.0, 'tpu95': 8.0}       # same rates as build.py's print plan


class Geo:
    """Every size that follows from the ball. ball_d: Rival rounds are 22.2-22.8 mm (study 2.1); 22.7 is the design
    ball. Bores and pockets are ball + 1.5 mm."""

    def __init__(self, ball_d: float = 22.7, wheel_d: float = 40.0, crush: float = 0.12):
        self.ball = ball_d
        self.bore = ball_d + 1.5
        self.br = self.bore / 2
        self.wall = 2.5
        # dial: 8 pockets, spokes 4 mm; pitch radius so the gap between spokes >= the bore
        self.n_pockets = 8
        self.spoke_w = 4.0
        self.rp = math.ceil((self.bore + self.spoke_w + 0.5) * self.n_pockets / (2 * math.pi))
        self.dial_hub_r = self.rp - self.br                      # inner wall of the ball channel
        self.dial_wall_r = self.rp + self.br                     # outer wall (housing / hopper inside)
        self.housing_r = self.dial_wall_r + self.wall
        self.floor_z = 10.0                                      # top of the dial-housing floor (C frame)
        self.floor_t = 3.0
        self.dial_z0 = self.floor_z + 0.75
        self.dial_h = 20.0
        self.housing_top = 35.0
        self.hopper_top = 70.0
        self.exit_x = float(self.rp)                             # the exit hole under the front pocket
        self.ball_z_dial = self.floor_z + ball_d / 2             # ball centre in a pocket
        self.chute_r = self.ball_z_dial                          # the chute turns the ball down to the path (z = 0)
        self.chute_cx = self.exit_x + self.chute_r               # centre of the turn, at (chute_cx, chute_r)
        # flywheels: crush ~12 % of the ball (2.7 mm on 22.7)
        self.wheel_d = wheel_d
        self.wheel_c = wheel_d + ball_d * (1 - crush)            # centre distance (60 for 40 mm wheels)
        self.wheel_y = self.wheel_c / 2
        self.tyre_w = 12.0
        nip = math.sqrt((wheel_d / 2) ** 2 - ((self.wheel_c - ball_d) / 2) ** 2)   # ball touches both wheels here
        self.wheel_x = math.ceil(self.chute_cx + nip + 2.0)
        self.cav_r = wheel_d / 2 + 2.0
        self.cage_x0 = self.wheel_x - self.cav_r - self.wall
        self.cage_x1 = self.wheel_x + self.cav_r + self.wall
        self.cage_y = self.wheel_y + self.cav_r + self.wall      # half-width of the cartridge
        self.base_z0 = -(self.br + 3.0)                          # underside of the cartridge base
        self.bell_z0 = 10.0                                      # motors hang under the cage top plate
        self.plate_z0 = self.bell_z0 + SNAIL['bell_h'] + SNAIL['base_h']
        self.plate_z1 = self.plate_z0 + 3.5
        self.barrel_od = 30.0
        self.barrel_len = 100.0
        self.socket_x0 = self.cage_x1 + 1.5                      # barrel shoulder
        self.socket_x1 = self.socket_x0 + 14.0
        self.barrel_x0 = self.socket_x0
        self.barrel_x1 = self.barrel_x0 + self.barrel_len
        # tilt and pan
        self.tilt_c = 15.0                                       # tilt axis above the ball path, on the dial axis
        self.cheek_y = (self.cage_y + 1.5, self.cage_y + 6.5)
        self.arm_y = (self.cheek_y[1] + 4.0, self.cheek_y[1] + 12.0)
        self.rail_y = (self.cage_y - 10.5, self.cheek_y[1])
        self.rail_z = (self.base_z0 - 5.0, self.base_z0)
        self.stop_r = (24.0, 32.0)
        self.tilt_min = -25.0
        # pan stack (T frame, mount face z = 0)
        self.foot_t = 5.0
        self.brg_z = 31.0                                        # bottom of the 61810
        self.housing_r_out = 37.0
        self.turntable_z = (44.0, 60.0)
        self.gear = {'m': 1.25, 'z_ring': 63, 'z_pinion': 21}
        self.centre_d = self.gear['m'] * (self.gear['z_ring'] + self.gear['z_pinion']) / 2 + 0.15
        self.servo_pan_xy = (-self.centre_d, 0.0)
        self.servo_z0 = self.foot_t
        self.base_r = 72.0
        self.bridge_z = (self.turntable_z[1], self.turntable_z[1] + 8.0)
        self.post_r = (68.5, 74.0)
        self.post_top = 50.0
        self.dt_y = 73.0                                         # DT pad face (flange seat)
        self.bumper_r = (80.0, 86.0)
        self.bumper_z = (4.0, 20.0)
        # height of the ball path above the mount face: the M2006 (under the dial) must clear the yoke bridge
        m2006_bottom = self.floor_z - self.floor_t - M2006['L']
        self.path_t = math.ceil(self.bridge_z[1] + 2.5 - m2006_bottom)
        self.tilt_t = self.path_t + self.tilt_c


# ------------------------------------------------------------------------------------------------ small helpers

def box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').circle(r).extrude(z1 - z0).translate((x, y, z0))


def ring_z(ro, ri, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').circle(ro).circle(ri).extrude(z1 - z0).translate((x, y, z0))


def cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


def sector_y(r0, r1, a0, a1, y0, y1, cx=0.0, cz=0.0, n=24):
    """An annular sector in the x-z plane (angles in degrees from +x towards +z) between y0 and y1."""
    a = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    pts = [(cx + r1 * math.cos(t), cz + r1 * math.sin(t)) for t in a] + [(cx + r0 * math.cos(t), cz + r0 * math.sin(t)) for t in reversed(a)]
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(pts).close().extrude(y1 - y0)


def polar(r, a):
    return (r * math.cos(a), r * math.sin(a))


def gear_profile(m, z, backlash=0.15, n=6):
    """Involute spur gear outline (20 deg pressure angle, addendum m, dedendum 1.25 m) as one closed polyline.
    backlash thins every tooth at the pitch circle (printed gears)."""
    alpha = math.radians(20.0)
    rp, ra, rf = m * z / 2, m * z / 2 + m, m * z / 2 - 1.25 * m
    rb = rp * math.cos(alpha)
    inv = lambda x: math.tan(x) - x
    psi = (math.pi * m / 2 - backlash) / (2 * rp) + inv(alpha)
    r0 = max(rb, rf)
    flank = [(r, psi - inv(math.acos(min(1.0, rb / r)))) for r in (r0 + (ra - r0) * k / n for k in range(n + 1))]
    pitch = 2 * math.pi / z
    pts = []
    for i in range(z):
        c = i * pitch
        if rf < rb:
            pts.append(polar(rf, c - flank[0][1]))
        pts += [polar(r, c - f) for r, f in flank]
        pts += [polar(r, c + f) for r, f in reversed(flank)]
        if rf < rb:
            pts.append(polar(rf, c + flank[0][1]))
        pts.append(polar(rf, c + pitch / 2))
    return pts


def spur(m, z, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').polyline(gear_profile(m, z)).close().extrude(z1 - z0).translate((x, y, z0))


def insert_hole(x, y, z_top, size='M3', depth=INSERT_DEPTH):
    """Pilot for a heat-set insert, from a top face down."""
    return cyl_z(FAST[size]['insert_pilot'] / 2, z_top - depth, z_top + 0.1, x, y)


def through_z(x, y, d, z0=-50.0, z1=400.0):
    return cyl_z(d / 2, z0, z1, x, y)


def servo_envelope(G, shaft_xyz, axis):
    """STS3215: case + horn. The horn faces along `axis` ('+z' for the pan servo, '-y' for the tilt servo); the case
    runs 12.35 one way and 32.85 the other along its length (+y for the pan servo, -z for the tilt servo)."""
    L, W, H = SERVO['L'], SERVO['W'], SERVO['H']
    s = SERVO['shaft_from_end']
    x, y, z = shaft_xyz
    if axis == '+z':
        case = box(x - W / 2, x + W / 2, y - s, y + L - s, z - H, z)
        horn = cyl_z(SERVO['horn_d'] / 2, z, z + SERVO['horn_t'], x, y)
    else:                                   # horn towards -y, length downwards
        case = box(x - W / 2, x + W / 2, y, y + H, z - (L - s), z + s)
        horn = cyl_y(SERVO['horn_d'] / 2, y - SERVO['horn_t'], y, x, z)
    return case.union(horn)


# ------------------------------------------------------------------------------------------------ fixed (pan base) parts

def pan_base(G):
    """The fixed base, printed PA6-CF on its foot (100 % solid): a Ø144 x 5 foot on the TM pattern (4 x M5 x 16
    counterbored through it into the head ring's inserts, 2 x Ø5 dowel holes, Ø45 centre hole, six lightening
    windows), a housing tube holding the 61810 outer race (Ø65 seat on a Ø62 shoulder; the pan_clamp holds it down
    with 3 x M3 into the housing ears), the STS3215 pan servo standing in a pocket (2 x M2.5 through the floor, est),
    a 2.5 mm drip skirt, a flat pad with the DT04-12PA flange receptacle on the -y side (window for its body, 2 x M3
    inserts), a window into the housing for the cable, the pan hard-stop post at the front (the turntable's finger
    meets it at +-173.5 deg), and 5 tabs with M3 inserts that carry the TPU bumper ring."""
    t = G.foot_t
    hz1 = G.brg_z + BRG['B']
    s = cyl_z(G.base_r, 0, t)
    s = s.union(ring_z(G.base_r, G.base_r - 2.5, 0, 18))                                    # drip skirt
    s = s.union(ring_z(35.5, 32.5, 0, G.brg_z - 2))                                         # housing tube
    s = s.union(ring_z(G.housing_r_out, (BRG['D'] - 3) / 2, G.brg_z - 2, hz1))              # bearing seat ring
    for a in (0, 90, 270):                                                                  # clamp ears
        ear = box(G.housing_r_out - 0.5, 42.0, -7, 7, hz1 - 4, hz1).rotate((0, 0, 0), (0, 0, 1), a)
        s = s.union(ear).union(cyl_z(7.0, hz1 - 4, hz1, *polar(42.0, math.radians(a))))
    # pan servo pocket (walls 3 mm, 20 mm tall, servo + 0.3 mm)
    sx, sy = G.servo_pan_xy
    W, L, sft = SERVO['W'], SERVO['L'], SERVO['shaft_from_end']
    px0, px1, py0, py1 = sx - W / 2 - 0.3, sx + W / 2 + 0.3, sy - sft - 0.3, sy + L - sft + 0.3
    s = s.union(box(px0 - 3, px1 + 5.5, py0 - 3, py1 + 3, 0, t + 20))       # inner wall runs into the housing tube
    s = s.cut(box(px0, px1, py0, py1, t, t + 30))
    s = s.union(box(-24, 24, -G.dt_y, -(G.base_r - 8), 0, 36))                             # DT pad (-y)
    s = s.union(box(G.post_r[0], G.post_r[1], -4, 4, 0, G.post_top))                        # hard-stop post (front)
    for a in BUMPER_TABS:
        s = s.union(box(G.base_r - 1, G.bumper_r[1], -6, 6, 0, G.bumper_z[0]).rotate((0, 0, 0), (0, 0, 1), a))
    # --- cuts
    s = s.cut(cyl_z(BRG['D'] / 2, G.brg_z, hz1 + 1))                                       # bearing seat
    s = s.cut(cyl_z(TM_HOLE / 2, -1, t + 1))
    for (x, y) in TM_BOLTS:
        s = s.cut(through_z(x, y, FAST['M5']['clear'], -1, 60)).cut(cyl_z(5.0, t - 0.01, 60, x, y))
    for (x, y) in TM_DOWELS:
        s = s.cut(cyl_z(2.5, -1, t - 1.0, x, y))
    for a in (22.5, 67.5, 112.5, 247.5, 292.5, 337.5):                                     # foot windows
        s = s.cut(sector_z(40.0, 63.0, a - 10, a + 10, -1, t + 1))
    for a in (0, 90, 270):
        x, y = polar(42.0, math.radians(a))
        s = s.cut(insert_hole(x, y, hz1, 'M3', 6.0))
    for dy in (-12.0, 12.0):                                                                # pan servo floor screws
        s = s.cut(through_z(sx, sy + 10 + dy * 0.5, 2.9, -1, t + 1))
    b, f = DT['body'], DT['flange']
    s = s.cut(box(-b[0] / 2 - 0.3, b[0] / 2 + 0.3, -G.dt_y - 1, -(G.base_r - 30), DT_Z - b[2] / 2 - 0.3, DT_Z + b[2] / 2 + 0.3))
    for x in (-f[0] / 2 + 4, f[0] / 2 - 4):
        s = s.cut(cyl_y(FAST['M3']['insert_pilot'] / 2, -G.dt_y - 0.1, -G.dt_y + 6.0, x, DT_Z + 11.0))
    s = s.cut(box(-10, 10, -40, 0, t, t + 18))                                              # cable window (-y)
    for a in BUMPER_TABS:
        x, y = polar(sum(G.bumper_r) / 2, math.radians(a))
        s = s.cut(insert_hole(x, y, G.bumper_z[0], 'M3', 4.0))
    return s


BUMPER_TABS = (0, 60, 120, 240, 300)
DT_Z = 15.0


def sector_z(r0, r1, a0, a1, z0, z1, n=16):
    """An annular sector about the z axis (angles in degrees)."""
    a = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    pts = [polar(r1, t) for t in a] + [polar(r0, t) for t in reversed(a)]
    return cq.Workplane('XY').polyline(pts).close().extrude(z1 - z0).translate((0, 0, z0))


def pan_clamp(G):
    """Printed PA6-CF clamp ring, 3 mm: its Ø61 bore overlaps the 61810's outer race by 1.5 mm and holds it down
    (3 x M3 x 8 into the housing ears); the turntable's shoulder passes through it with 2.5 mm to spare."""
    z0 = G.brg_z + BRG['B']
    s = ring_z(39.0, 30.5, z0, z0 + 3)
    for a in (0, 90, 270):
        lug = box(0, 46.0, -7, 7, z0, z0 + 3).rotate((0, 0, 0), (0, 0, 1), a)
        s = s.union(lug.cut(cyl_z(39.0, z0 - 1, z0 + 4)).union(cyl_z(7.0, z0, z0 + 3, *polar(42.0, math.radians(a)))))
        s = s.cut(through_z(*polar(42.0, math.radians(a)), FAST['M3']['clear']))
    s = s.cut(cyl_z(30.5, z0 - 1, z0 + 4))
    return s


def pan_pinion(G):
    """21 T module 1.25 spur pinion (printed PA6-CF, 12 mm face) on a Ø20 flange that screws to the STS3215's disc
    horn (4 x M2 on Ø14, est). 63 : 21 = 3 : 1, so the 2.94 N·m servo gives 8.8 N·m at the turntable; at stall the
    tooth stress is about 40 MPa (Lewis), so cap the servo at 50 % torque in firmware."""
    m = G.gear
    x, y = G.servo_pan_xy
    z0 = G.servo_z0 + SERVO['H'] + SERVO['horn_t']
    s = spur(m['m'], m['z_pinion'], z0 + 1.0, z0 + 13.0, x, y).union(cyl_z(10.0, z0, z0 + 1.0, x, y))
    s = s.cut(cyl_z(1.6, z0 - 1, z0 + 14, x, y))                                         # horn screw
    for k in range(4):
        hx, hy = polar(7.0, math.pi / 4 + k * math.pi / 2)
        s = s.cut(cyl_z(1.1, z0 - 1, z0 + 14, x + hx, y + hy))
    return s


def bumper_ring(G):
    """TPU 95A ring, 6 mm wide and 16 mm tall, around the pan base on its five tabs (M3 screws with washers); a gap
    on -y lets the DT plug in. It takes the knocks before the pan base does."""
    s = ring_z(G.bumper_r[1], G.bumper_r[0], *G.bumper_z)
    s = s.cut(box(-24, 24, -120, -50, 0, 40))
    for a in BUMPER_TABS:
        s = s.cut(through_z(*polar(sum(G.bumper_r) / 2, math.radians(a)), FAST['M3']['clear']))
    return s


# ------------------------------------------------------------------------------------------------ pan parts (turn with pan)

def pan_ring(G):
    """The turntable, printed PA6-CF upside down (100 % solid): a 63 T module 1.25 spur gear (16 mm face) with a
    Ø40 open centre, a shoulder that sits on the 61810's inner race, a Ø50 journal through it with a DIN 471-50
    circlip groove under the race, 4 x M4 inserts for the tilt yoke, and the pan stop finger at the rear (reaches over
    the pinion and meets the base's post at +-173.5 deg; software limit +-170)."""
    z0, z1 = G.turntable_z
    m = G.gear
    s = spur(m['m'], m['z_ring'], z0, z1)
    s = s.union(ring_z(28.0, 20.0, G.brg_z + BRG['B'], z0 + 0.01))                         # shoulder on the inner race
    s = s.union(ring_z(BRG['d'] / 2, 20.0, G.brg_z - 5.0, G.brg_z + BRG['B'] + 0.01))       # journal
    s = s.union(box(-G.post_r[1], -30.0, -4, 4, z1 - 3.5, z1))                              # stop finger: arm over the pinion
    s = s.union(box(-G.post_r[1], -G.post_r[0], -4, 4, z0, z1))                             # ... and down beside it
    s = s.cut(cyl_z(20.0, z0 - 30, z1 + 1))
    s = s.cut(ring_z(BRG['d'] / 2 + 1, 23.5, G.brg_z - 2.15, G.brg_z))                     # circlip groove
    for (x, y) in YOKE_BOLTS:
        s = s.cut(insert_hole(x, y, z1, 'M4'))
    return s


YOKE_BOLTS = [(10.0, 28.0), (-10.0, 28.0), (10.0, -28.0), (-10.0, -28.0)]


def tilt_yoke(G):
    """Printed PA6-CF on its back (layers run along the arms): an 8 mm bridge on the turntable (4 x M4) and two 8 mm
    arms up to the tilt axis. +y arm: a pocket for the STS3215 tilt servo on its outer face (2 x M2.5 each side, est),
    its horn through a Ø26 hole. -y arm: the MR126 seat on the inner face, a Ø6.5 hole for the ISO 7379 6 x 12
    shoulder screw. The hard stop: two sectors on the -y arm's inner face that the cradle's lug hits at tilt 0
    (barrel horizontal; it cannot go above) and at -25 deg."""
    zt = G.tilt_t
    b0, b1 = G.bridge_z
    a0, a1 = G.arm_y
    s = box(-20, 20, -a1, a1, b0, b1)
    for sgn in (1, -1):
        y0, y1 = (a0, a1) if sgn > 0 else (-a1, -a0)
        arm = box(-20, 20, y0, y1, b0, zt).union(cyl_y(20.0, y0, y1, 0, zt))
        s = s.union(arm)
    # tilt servo pocket on the +y arm (servo + 0.3, walls 3, 15 deep)
    W, L, sft = SERVO['W'], SERVO['L'], SERVO['shaft_from_end']
    pocket = box(-W / 2 - 3.3, W / 2 + 3.3, a1, a1 + 15, zt - (L - sft) - 3.3, zt + sft + 3.3)
    s = s.union(pocket).cut(box(-W / 2 - 0.3, W / 2 + 0.3, a1, a1 + 16, zt - (L - sft) - 0.3, zt + sft + 0.3))
    for x in (-W / 2 - 3.3, W / 2 + 0.3):
        for z in (zt - 20, zt + 2):
            s = s.cut(cq.Workplane('YZ', origin=(x - 0.1, 0, 0)).center(a1 + 9, z).circle(1.25).extrude(3.5))
    # hard stops on the -y arm's inner face; the lug sits at -90 deg at tilt 0 and sweeps to -115 at -25
    w = 7.5
    up_face, low_face = -90 + w, -90 + G.tilt_min - w
    s = s.union(sector_y(G.stop_r[0], G.stop_r[1], up_face, up_face + 30, -a0, -a0 + 2.5, 0, zt))
    s = s.union(sector_y(G.stop_r[0], G.stop_r[1], low_face - 30, low_face, -a0, -a0 + 2.5, 0, zt))
    # holes
    for sgn in (1, -1):
        s = s.cut(box(-12, 12, sgn * (a0 - 1) if sgn > 0 else -a1 - 1, sgn * (a1 + 1) if sgn > 0 else -a0 + 1, b1 + 6, zt - 38.0))
        s = s.cut(box(-12, 12, sgn * 36 if sgn > 0 else -57, sgn * 57 if sgn > 0 else -36, b0 - 1, b1 + 1))
    s = s.cut(cyl_y(13.0, a0 - 1, a1 + 1, 0, zt))                                           # servo horn
    s = s.cut(cyl_y(MR126['D'] / 2, -a0 - MR126['B'], -a0 + 3, 0, zt))                      # MR126 seat (inner face)
    s = s.cut(cyl_y(3.25, -a1 - 1, -a0, 0, zt))
    s = s.cut(cyl_z(15.0, b0 - 1, b1 + 1))                                                  # cable
    for (x, y) in YOKE_BOLTS:
        s = s.cut(through_z(x, y, FAST['M4']['clear'], b0 - 1, b1 + 1)).cut(cyl_z(4.0, b1 - 4, b1 + 1, x, y))
    return s


# ------------------------------------------------------------------------------------------------ tilting parts (C frame)

def cradle(G):
    """Printed PA6-CF flat (100 % solid). Two 5 mm cheeks on the tilt axis and two 17 mm rails under the cartridge,
    joined by a rear cross bar (the latched cartridge ties the front; nothing hangs low at the nose when it tilts). +y cheek: a Ø20 hub bolted to the tilt servo's horn (4 x M2, est). -y cheek: an M5 insert
    for the shoulder screw through the MR126, a Ø8 spacer on the inner race, and the hard-stop lug. Rails: the CT
    interface (2 x Ø4 dowel holes and an M4 insert for the captive thumbscrew from below). A tab at the front left
    carries the laser mount (2 x M3 inserts)."""
    zt = G.tilt_c
    c0, c1 = G.cheek_y
    r0, r1 = G.rail_y
    z0, z1 = G.rail_z
    xr0, xr1 = -(G.housing_r + 2.0), G.socket_x0 - 2.0
    s = None
    for sgn in (1, -1):
        ya, yb = (c0, c1) if sgn > 0 else (-c1, -c0)
        cheek = box(-22, 22, ya, yb, z0, zt).union(cyl_y(22.0, ya, yb, 0, zt))
        ra, rb = (r0, r1) if sgn > 0 else (-r1, -r0)
        rail = box(xr0, xr1, ra, rb, z0, z1)
        part = cheek.union(rail)
        s = part if s is None else s.union(part)
    s = s.union(box(xr0, xr0 + 8, -r1, r1, z0, z1))                                              # rear cross bar
    s = s.union(box(xr1 - 8, LASER_X[1] + 2, -r1 + 7, -22.0, z0, z1))                            # laser tab
    s = s.union(cyl_y(10.0, c1, G.arm_y[0] + 1.0, 0, zt))                                         # servo hub
    s = s.union(cyl_y(5.5, -G.arm_y[0] + 1.0, -c1, 0, zt))                                         # insert boss
    s = s.union(cyl_y(4.0, -G.arm_y[0], -G.arm_y[0] + 1.0, 0, zt))                                 # spacer on the race
    s = s.union(sector_y(G.stop_r[0], G.stop_r[1], -97.5, -82.5, -c1 - 2.5, -c1, 0, zt))          # stop lug
    # holes
    s = s.cut(cyl_y(FAST['M5']['insert_pilot'] / 2, -G.arm_y[0] - 1, -c0 + 0.01, 0, zt))
    s = s.cut(cyl_y(1.6, c0 - 1, G.arm_y[0] + 2, 0, zt))
    for k in range(4):
        hx, hz = polar(7.0, math.pi / 4 + k * math.pi / 2)
        s = s.cut(cyl_y(1.1, c0 - 1, G.arm_y[0] + 2, hx, zt + hz))
    for (x, y) in CT_DOWELS:
        s = s.cut(cyl_z(2.0, z0 - 1, z1 + 1, x, y))
    s = s.cut(through_z(*CT_LATCH, FAST['M4']['clear'], z0 - 1, z1 + 1))
    for x in (LASER_X[0] + 4, LASER_X[1] - 4):
        s = s.cut(through_z(x, LASER_Y, FAST['M3']['clear'], z0 - 1, z1 + 1))
    # lightening windows in the rails
    for sgn in (1, -1):
        for xa in (-30.0, 30.0):
            s = s.cut(box(xa - 12, xa + 12, sgn * (r0 + r1) / 2 - 3, sgn * (r0 + r1) / 2 + 3, z0 - 1, z1 + 1))
    return s


CT_DOWELS = [(-20.0, 49.0), (75.0, -49.0)]
CT_LATCH = (20.0, -49.0)
LASER_X = (106.0, 126.0)
LASER_Y = -32.0


def cartridge_body(G):
    """The ball cartridge, printed PA6-CF on its base (100 % solid, 2.5 mm walls): a base plate on the cradle rails
    (CT dowels, thumbscrew insert), the dial housing (floor with the M2006 face mount and the exit hole; a window at
    the rear for the C610), the chute that drops the ball out of the dial and turns it forward onto the path, the
    flywheel cage (two shells round the wheels and the hanging motors, a top plate the motors screw under with
    4 x M3 on 16 x 16, est; the AM32 ESCs sit on it), the ball channel and the barrel socket (M3 insert on top)."""
    br, w = G.br, G.wall
    hr = G.housing_r
    fz = G.floor_z
    bz0 = G.base_z0
    # base plate (windowed) under everything
    s = box(-hr - 2.0, G.cage_x1, -G.cage_y, G.cage_y, bz0, bz0 + 3)
    s = s.cut(box(-36, 26, -34, 34, bz0 - 1, bz0 + 4))
    # dial housing: wall from the base to the top, floor, flange lugs for the hopper
    s = s.union(ring_z(hr, G.dial_wall_r, bz0 + 3, G.housing_top))
    s = s.union(cyl_z(G.dial_wall_r, fz - G.floor_t, fz))
    for a in HOPPER_LUGS:
        lug = cyl_z(5.0, G.housing_top - 6, G.housing_top, *polar(hr + 3.5, math.radians(a)))
        s = s.union(lug.union(box(hr - 1.0, hr + 3.5, -5.0, 5.0, G.housing_top - 6, G.housing_top).rotate((0, 0, 0), (0, 0, 1), a)))
    s = s.cut(box(-hr - 3, -24, -32, 32, bz0 + 3, fz - G.floor_t - 0.5))                  # C610 window (rear)
    for sy in (1, -1):
        s = s.cut(box(-20, 20, sy * 20, sy * 60, -5, fz - G.floor_t - 3))                   # side windows
    # chute and channel walls
    chute = cq.Workplane('XY').add(cq.Solid.makeTorus(G.chute_r, br + w, cq.Vector(G.chute_cx, 0, G.chute_r), cq.Vector(0, 1, 0)))
    quad = box(G.exit_x - br - w - 1, G.chute_cx, -br - w - 1, br + w + 1, -br - w - 1, fz - G.floor_t + 0.5)
    s = s.union(chute.intersect(quad))
    s = s.union(cyl_x(br + w, G.chute_cx, G.socket_x0))
    s = s.union(box(G.exit_x - 4, G.chute_cx, -br - w + 1.5, br + w - 1.5, bz0, 0))        # web under the chute
    # flywheel cage: two shells, plates, socket
    for sy in (1, -1):
        s = s.union(ring_z(G.cav_r + w, G.cav_r, bz0, G.plate_z1, G.wheel_x, sy * G.wheel_y))
    plate = cyl_z(G.cav_r + w, 0, 1, G.wheel_x, G.wheel_y).union(cyl_z(G.cav_r + w, 0, 1, G.wheel_x, -G.wheel_y)) \
        .union(box(G.cage_x0, G.cage_x1, -G.wheel_y, G.wheel_y, 0, 1))
    s = s.union(_slab(plate, G.plate_z0, G.plate_z1))
    s = s.union(_slab(plate, bz0, bz0 + 3))
    s = s.union(box(G.cage_x1 - w, G.cage_x1 + 1.5, -br - w - 3, br + w + 3, bz0, br + w + 3))   # front wall
    s = s.union(cyl_x(br + 6.0, G.socket_x0 - 1.5, G.socket_x1))                            # barrel socket
    s = s.union(box(G.socket_x0 + 3, G.socket_x0 + 11, -5, 5, 0, br + 8.5))                 # socket screw boss
    # cuts: cavities, ball path, mounts
    for sy in (1, -1):
        s = s.cut(cyl_z(G.cav_r, -8.0, G.bell_z0 - 0.5, G.wheel_x, sy * G.wheel_y))
        s = s.cut(cyl_z(SNAIL['d'] / 2 + 2.0, G.bell_z0 - 0.6, G.plate_z0, G.wheel_x, sy * G.wheel_y))
        s = s.cut(cyl_z(4.0, G.plate_z0 - 1, G.plate_z1 + 1, G.wheel_x, sy * G.wheel_y))
        for k in range(4):
            hx, hy = polar(8.0 * math.sqrt(2), math.pi / 4 + k * math.pi / 2)
            s = s.cut(through_z(G.wheel_x + hx, sy * G.wheel_y + hy, FAST['M3']['clear'], G.plate_z0 - 1, G.plate_z1 + 1))
    s = s.cut(ball_path(G))
    s = s.cut(cyl_x(G.barrel_od / 2 + 0.1, G.socket_x0, G.socket_x1 + 1))
    s = s.cut(insert_hole(G.socket_x0 + 7, 0, br + 8.5, 'M3', 8.0 - 0.5))
    s = s.cut(cyl_z(M2006['shaft_d'] / 2 + 1.0, fz - G.floor_t - 1, fz + 1))                # M2006 face
    for k in range(4):
        hx, hy = polar(9.0, math.pi / 4 + k * math.pi / 2)
        s = s.cut(through_z(hx, hy, FAST['M3']['clear'], fz - G.floor_t - 1, fz + 1))
    for (x, y) in CT_DOWELS:
        s = s.cut(cyl_z(2.0, bz0 - 1, bz0 + 2.5, x, y))
    s = s.union(cyl_z(5.0, bz0, bz0 + 9, *CT_LATCH))
    s = s.cut(cyl_z(FAST['M4']['insert_pilot'] / 2, bz0 - 1, bz0 + 8.0, *CT_LATCH))       # insert from below
    for a in HOPPER_LUGS:
        s = s.cut(insert_hole(*polar(hr + 3.5, math.radians(a)), G.housing_top, 'M3', 6.0))
    return s


HOPPER_LUGS = (0.0, 135.0, 225.0)


def _slab(plate, z0, z1):
    """The outline of `plate` (built 0..1 thick, z from 0) as a slab from z0 to z1."""
    face = plate.faces('<Z').val()
    return cq.Workplane('XY').add(cq.Solid.extrudeLinear(face, cq.Vector(0, 0, z1 - z0))).translate((0, 0, z0 - face.Center().z))


def ball_path(G):
    """The ball's free space (bore = ball + 1.5): from a dial pocket down through the floor, round the chute, along the
    path between the wheels and up to the barrel socket."""
    br = G.br
    up = cyl_z(br, G.chute_r, G.housing_top, G.exit_x, 0)
    t = cq.Workplane('XY').add(cq.Solid.makeTorus(G.chute_r, br, cq.Vector(G.chute_cx, 0, G.chute_r), cq.Vector(0, 1, 0)))
    quad = box(G.exit_x - br - 1, G.chute_cx, -br - 1, br + 1, -br - 1, G.chute_r)
    return up.union(t.intersect(quad)).union(cyl_x(br, G.chute_cx, G.socket_x0 + 0.5))


def flywheel(G):
    """Flywheel hub, printed PA6-CF (100 % solid): Ø32 rim, web, a Ø10 boss with a Ø3 bore for the Snail's 2.95 mm
    shaft and an M3 grub screw (tapped). The TPU tyre (flywheel_tyre) brings it to Ø40; the wheel diameter is the
    bench-tuned speed limit (study 8.3)."""
    x, y = G.wheel_x, G.wheel_y
    s = ring_z(16.0, 13.0, -G.tyre_w / 2, G.tyre_w / 2, x, y)
    s = s.union(cyl_z(16.0, -3, 3, x, y)).union(cyl_z(5.0, -3, G.bell_z0 - 1.0, x, y))
    s = s.cut(cyl_z(1.5, 1.0, G.bell_z0, x, y))
    s = s.cut(cyl_x(1.25, x, x + 6, y, 5.0))
    for k in range(5):
        hx, hy = polar(9.5, k * 2 * math.pi / 5)
        s = s.cut(cyl_z(2.5, -4, 4, x + hx, y + hy))
    return s


def flywheel_tyre(G):
    """TPU 95A tyre, Ø40 x 12 over the Ø32 hub rim."""
    return ring_z(G.wheel_d / 2, 16.0, -G.tyre_w / 2, G.tyre_w / 2, G.wheel_x, G.wheel_y)


def dial(G):
    """The feed dial, printed PETG: a shelled Ø50 hub (2 mm rim, 2 mm top, four ribs to a Ø14 boss), 8 spokes 4 mm
    thick that push one ball per pocket round the housing to the exit hole, and a cone on top that stirs the hopper.
    Ø8 bore with a flat for the M2006 shaft (est) and an M3 grub screw. Park it with a spoke over the exit hole: the
    path is blocked with the motor off."""
    z0, h = G.dial_z0, G.dial_h
    s = ring_z(G.dial_hub_r, G.dial_hub_r - 2.0, z0, z0 + h).union(cyl_z(G.dial_hub_r, z0 + h - 2, z0 + h))
    s = s.union(cyl_z(7.0, z0, z0 + h))
    for k in range(4):
        s = s.union(box(5.0, G.dial_hub_r - 1.0, -1.25, 1.25, z0, z0 + h).rotate((0, 0, 0), (0, 0, 1), 45 + 90 * k))
    s = s.union(cq.Workplane('XY').circle(G.dial_hub_r).workplane(offset=6).circle(8.0).loft().translate((0, 0, z0 + h)))
    for k in range(G.n_pockets):
        a = (k + 0.5) * 360 / G.n_pockets
        sp = box(G.dial_hub_r - 1, G.dial_wall_r - 0.75, -G.spoke_w / 2, G.spoke_w / 2, z0, z0 + h - 2)
        s = s.union(sp.rotate((0, 0, 0), (0, 0, 1), a))
    shaft = cyl_z(M2006['shaft_d'] / 2 + 0.1, z0 - 1, z0 + M2006['shaft_l'] + 2).cut(box(M2006['shaft_d'] / 2 - 0.8, 10, -10, 10, z0 - 2, z0 + 20))
    s = s.cut(shaft)
    s = s.cut(cyl_x(1.25, 0, 8, 0, z0 + 6))
    return s


def hopper(G):
    """The hopper, printed PETG (translucent, so the balls show): a Ø102 tube from the dial housing to z = 70 in the
    cartridge frame (about 0.3 L above the dial: 30 balls), three lugs that screw to the housing (M3), and two Ø5
    holes for the hopper-full IR beam near the top."""
    r_in, r_out = G.dial_wall_r, G.dial_wall_r + 2.0
    z0, z1 = G.housing_top, G.hopper_top
    s = ring_z(r_out, r_in, z0, z1)
    for a in HOPPER_LUGS:
        x, y = polar(G.housing_r + 3.5, math.radians(a))
        lug = cyl_z(5.0, z0, z0 + 3, x, y).union(box(r_out - 1.0, G.housing_r + 3.5, -5.0, 5.0, z0, z0 + 3).rotate((0, 0, 0), (0, 0, 1), a))
        s = s.union(lug)
        s = s.cut(through_z(x, y, FAST['M3']['clear'], z0 - 1, z0 + 4))
    s = s.cut(cyl_y(2.5, -r_out - 1, r_out + 1, 0, z1 - 6))
    return s


def hopper_lid(G):
    """Lid, printed PETG: a 3 mm disc with a spigot into the hopper, a Ø32 fill port where the dock's spout pushes the
    sprung flap open, and two hinge lugs for the flap (Ø2 steel pin, torsion spring)."""
    z1 = G.hopper_top
    r = G.dial_wall_r + 2.0
    s = cyl_z(r, z1, z1 + 3).union(ring_z(G.dial_wall_r - 0.1, G.dial_wall_r - 2.1, z1 - 4, z1 + 0.01))
    s = s.cut(sector_z(12.0, G.dial_wall_r - 3, 30, 150, z1 - 1, z1 + 1.0)).cut(sector_z(12.0, G.dial_wall_r - 3, 210, 330, z1 - 1, z1 + 1.0))
    s = s.cut(cyl_z(16.0, z1 - 5, z1 + 4, FILL_PORT[0], 0))
    for y in (-12.0, 9.0):
        s = s.union(box(FILL_PORT[0] - 22, FILL_PORT[0] - 16, y, y + 3, z1 + 3, z1 + 9))
    s = s.cut(cyl_y(1.05, -15, 15, FILL_PORT[0] - 19, z1 + 6))
    return s


FILL_PORT = (-20.0, 0.0)


def hopper_flap(G):
    """The fill-port flap, printed PETG: a Ø36 x 2 disc and a hinge knuckle between the lid's lugs."""
    z = G.hopper_top + 3
    s = cyl_z(18.0, z, z + 2, FILL_PORT[0], 0)
    s = s.union(box(FILL_PORT[0] - 21, FILL_PORT[0] - 16, -8.6, 8.6, z, z + 2)).union(cyl_y(3.0, -8.6, 8.6, FILL_PORT[0] - 19, z + 3))
    s = s.cut(cyl_y(1.05, -10, 10, FILL_PORT[0] - 19, z + 3))
    return s


def barrel(G):
    """Barrel, printed PETG standing up: Ø30 x 100 with a bore of ball + 1.5 mm, 14 mm in the socket (M3 screw). Two
    chronograph gates 50 mm apart (Ø3.2 holes across for IR emitter and receiver, on small bosses). The last 15 mm
    printed in blaze orange (15 U.S.C. 5001)."""
    x0, x1 = G.barrel_x0, G.barrel_x1
    s = cyl_x(G.barrel_od / 2, x0, x1)
    for xg in (x0 + 30, x0 + 80):
        s = s.union(cyl_y(4.5, -G.barrel_od / 2 - 2.5, G.barrel_od / 2 + 2.5, xg, 0))
        s = s.cut(cyl_y(1.6, -30, 30, xg, 0))
    s = s.cut(cyl_x(G.br, x0 - 1, x1 + 1))
    return s


def laser_mount(G):
    """Laser holder, printed PETG: a ring round the Ø12 laser (Ø16 bore with an O-ring at the back) and three M3
    boresight screws at 120 deg (tapped), on a foot screwed to the cradle's tab (2 x M3). It stays on the cradle when
    a cartridge is swapped, so the boresight holds."""
    x0, x1 = LASER_X
    y = LASER_Y
    s = cyl_x(11.0, x0, x1, y, 0).union(box(x0, x1, y - 11, y + 11, G.rail_z[1], -4))
    s = s.cut(cyl_x(8.0, x0 - 1, x1 + 1, y, 0))
    for k in range(3):
        s = s.cut(_radial_hole(G, (x0 + x1) / 2, y, math.radians(90 + 120 * k)))
    for x in (x0 + 4, x1 - 4):
        s = s.cut(cyl_z(1.25, G.rail_z[1] - 1, G.rail_z[1] + 6, x, y))
    return s


def _radial_hole(G, x, y, a):
    d = cq.Workplane('XY').circle(1.25).extrude(12).translate((0, 0, 6))
    return d.rotate((0, 0, 0), (1, 0, 0), math.degrees(a) - 90).translate((x, y, 0))


# ------------------------------------------------------------------------------------------------ the head ring (proposal)

def head_ring_tm(L, G=None):
    """PROPOSED replacement for the ring of build.py head_saddle() so the TM interface of docs/cad-plan.md is met
    (today: Ø114/Ø60 x 6 at bodyTop + 20 with 4 x M4 inserts at (+-28.4, +-28.4), legs at r = 44 on the diagonals).
    Change: Ø132 OD (Ø60 ID kept, so the Ø45 TM hole is clear), 8 mm thick (bodyTop + 20 .. + 28), 4 x M5 inserts on
    80 x 80 (Ø6.4 x 8), 2 x Ø5 H7 holes for 5 x 12 dowel pins at (52, 0) and (0, -52), and the four legs moved to
    (+-40, +-40), Ø16, so the bolt loads go straight down; print it in PA6-CF (it now carries the turret's fall load).
    Robot frame."""
    top = L['bodyTop']
    z0, z1 = top + 20.0, top + 20.0 + SADDLE_T
    s = ring_z(66.0, 30.0, z0, z1)
    for (x, y) in TM_BOLTS:
        s = s.union(cyl_z(8.0, top, z0 + 0.01, x, y))
        s = s.cut(cyl_z(FAST['M5']['insert_pilot'] / 2, z1 - 8.0, z1 + 1, x, y))
    for (x, y) in TM_DOWELS:
        s = s.cut(cyl_z(2.5, z0 - 1, z1 + 1, x, y))
    return s


# ------------------------------------------------------------------------------------------------ bought parts

def bought_parts(G):
    """Envelopes of the bought parts with their real (or catalogue) sizes, each in its build frame. Returns
    {name: (shape, frame, mass_g, note)} with frame 'base' (T), 'pan' (T, turns with pan) or 'tilt' (C)."""
    out = {}
    sx, sy = G.servo_pan_xy
    out['pan_servo'] = (servo_envelope(G, (sx, sy, G.servo_z0 + SERVO['H']), '+z'), 'base', SERVO['mass_g'],
                        'Feetech STS3215 12 V; horn up, pinion on the horn')
    out['pan_bearing'] = (ring_z(BRG['D'] / 2, BRG['d'] / 2, G.brg_z, G.brg_z + BRG['B']), 'base', BRG['mass_g'], '61810-2RS (50 x 65 x 7)')
    yb = G.dt_y
    f, b, fr, pl = DT['flange'], DT['body'], DT['front'], DT['plug']
    zc = DT_Z
    flip = lambda w: w.rotate((0, 0, 0), (0, 0, 1), 180)                  # built on +y, mounted on -y
    dt = box(-f[0] / 2, f[0] / 2, yb, yb + f[1], zc - f[2] / 2, zc + f[2] / 2)
    dt = dt.union(box(-b[0] / 2, b[0] / 2, yb - b[1], yb, zc - b[2] / 2, zc + b[2] / 2))
    dt = dt.union(box(-fr[0] / 2, fr[0] / 2, yb + f[1], yb + f[1] + fr[1], zc - fr[2] / 2, zc + fr[2] / 2))
    out['dt_receptacle'] = (flip(dt), 'base', DT['mass_g'], 'Deutsch DT04-12PA-L012 flange receptacle (TM: 24 V, CAN, e-stop loop, ID); envelope est')
    out['dt_plug'] = (flip(box(-pl[0] / 2, pl[0] / 2, yb + f[1], yb + f[1] + pl[1], zc - pl[2] / 2, zc + pl[2] / 2)), 'base', 0.0,
                      'DT06-12SA plug on the robot harness (robot side; use a 90 deg boot so the harness turns down)')
    a0, a1 = G.arm_y
    out['tilt_servo'] = (servo_envelope(G, (0, a1, G.tilt_t), '-y'), 'pan', SERVO['mass_g'], 'Feetech STS3215 12 V on the +y arm')
    out['tilt_bearing'] = (ring_z(MR126['D'] / 2, MR126['d'] / 2, 0, MR126['B']).rotate((0, 0, 0), (1, 0, 0), 90)
                           .translate((0, -a0, G.tilt_t)), 'pan', MR126['mass_g'], 'MR126-2RS (6 x 12 x 4)')
    # tilting (C frame)
    for sgn, nm in ((1, 'flywheel_motor_l'), (-1, 'flywheel_motor_r')):
        x, y = G.wheel_x, sgn * G.wheel_y
        m = cyl_z(SNAIL['d'] / 2, G.bell_z0, G.bell_z0 + SNAIL['bell_h'], x, y)
        m = m.union(cyl_z(SNAIL['base_d'] / 2, G.bell_z0 + SNAIL['bell_h'], G.plate_z0, x, y))
        m = m.union(cyl_z(SNAIL['shaft_d'] / 2, G.bell_z0 - SNAIL['shaft_l'], G.bell_z0, x, y))
        out[nm] = (m, 'tilt', SNAIL['mass_g'], 'DJI RoboMaster Snail 2305, hangs under the cage plate (base pattern est)')
    for sgn, nm in ((1, 'esc_l'), (-1, 'esc_r')):
        ex, ey, ez = AM32['size']
        out[nm] = (box(G.wheel_x - 8, G.wheel_x - 8 + ex, sgn * 1.0 if sgn > 0 else -1.0 - ey, sgn * (1.0 + ey) if sgn > 0 else -1.0,
                       G.plate_z1, G.plate_z1 + ez), 'tilt', AM32['mass_g'], 'Repeat Robotics AM32 35 A, on the cage plate')
    fz0 = G.floor_z - G.floor_t
    shaft = cyl_z(M2006['shaft_d'] / 2, fz0, G.dial_z0 + M2006['shaft_l']).cut(box(M2006['shaft_d'] / 2 - 0.9, 10, -10, 10, fz0 - 1, 60))
    m2 = cyl_z(M2006['d'] / 2, fz0 - M2006['L'], fz0).union(shaft)
    out['feed_motor'] = (m2, 'tilt', M2006['mass_g'], 'DJI M2006 P36 under the dial (envelope est)')
    cx, cy, cz = C610['size']
    out['feed_esc'] = (box(-15 - cx, -15, -cy / 2, cy / 2, G.base_z0 + 3, G.base_z0 + 3 + cz), 'tilt', C610['mass_g'], 'DJI C610 (CAN) under the dial floor')
    out['laser'] = (cyl_x(LASER['d'] / 2, LASER_X[0] - 2, LASER_X[0] - 2 + LASER['L'], LASER_Y, 0), 'tilt', LASER['mass_g'],
                    'Picotronic DD520-1-24(12x40), 520 nm Class 2')
    return out


def balls(G, n_hopper=22):
    """Balls for the pictures (not checked for clashes): the dial pockets, the chute, the nip, and a pile in the
    hopper."""
    r = G.ball / 2
    pts = []
    for k in range(G.n_pockets):
        a = math.radians(k * 360 / G.n_pockets)
        if k == 0:
            continue
        pts.append((G.rp * math.cos(a), G.rp * math.sin(a), G.ball_z_dial))
    t = math.radians(45)
    pts.append((G.chute_cx - G.chute_r * math.cos(t), 0, G.chute_r - G.chute_r * math.sin(t)))
    pts.append((G.wheel_x - 7.0, 0, 0))
    z = G.dial_z0 + G.dial_h + r + 3
    rings = [(0, 1), (G.rp - 4, 7), (G.dial_wall_r - r - 1, 10)]
    while len(pts) < G.n_pockets + 1 + n_hopper:
        for rr, n in rings:
            for k in range(n):
                a = 2 * math.pi * k / n + z * 0.05
                pts.append((rr * math.cos(a), rr * math.sin(a), z))
        z += G.ball * 0.9
    return [cq.Workplane('XY').sphere(r).translate(p) for p in pts[:G.n_pockets + 1 + n_hopper]]


# ------------------------------------------------------------------------------------------------ assembly

MADE = [
    # name, function, frame, material, qty, print rotation, note
    ('pan_base', pan_base, 'base', 'pa6-cf', 1, None, 'PA6-CF on its foot; 4 x M5 x 16 into the head ring, 2 x Ø5 dowels'),
    ('pan_clamp', pan_clamp, 'base', 'pa6-cf', 1, None, 'PA6-CF; 3 x M3 x 8 into inserts'),
    ('pan_ring', pan_ring, 'pan', 'pa6-cf', 1, ((1, 0, 0), 180), 'PA6-CF upside down; DIN 471-50 circlip; 4 x M4 inserts'),
    ('pan_pinion', pan_pinion, 'pinion', 'pa6-cf', 1, None, 'PA6-CF; 4 x M2 to the horn; turns -3 x pan about the servo axis'),
    ('tilt_yoke', tilt_yoke, 'pan', 'pa6-cf', 1, ((0, 1, 0), 90), 'PA6-CF on its back; 4 x M4 x 12 to the turntable'),
    ('cradle', cradle, 'tilt', 'pa6-cf', 1, None, 'PA6-CF flat; ISO 7379 6 x 12 shoulder screw (M5) in an insert'),
    ('cartridge_body', cartridge_body, 'tilt', 'pa6-cf', 1, None, 'PA6-CF on its base; supports under the chute'),
    ('flywheel', flywheel, 'tilt', 'pa6-cf', 2, None, 'PA6-CF hub; M3 grub screw'),
    ('flywheel_tyre', flywheel_tyre, 'tilt', 'tpu95', 2, None, 'TPU 95A tyre'),
    ('dial', dial, 'tilt', 'petg', 1, None, 'PETG; M3 grub screw on the flat'),
    ('hopper', hopper, 'tilt', 'petg', 1, None, 'translucent PETG; 3 x M3 to the housing'),
    ('hopper_lid', hopper_lid, 'tilt', 'petg', 1, ((1, 0, 0), 180), 'PETG'),
    ('hopper_flap', hopper_flap, 'tilt', 'petg', 1, None, 'PETG; Ø2 pin + torsion spring'),
    ('barrel', barrel, 'tilt', 'petg', 1, ((0, 1, 0), -90), 'PETG standing; last 15 mm blaze orange'),
    ('laser_mount', laser_mount, 'tilt', 'petg', 1, None, 'PETG; 3 x M3 boresight, 2 x M3 to the cradle'),
    ('bumper_ring', bumper_ring, 'base', 'tpu95', 1, None, 'TPU 95A; 5 x M3 with washers'),
]


class Turret:
    """Builds every part once in its own frame and poses them for any pan/tilt."""

    def __init__(self, L, ball_d=22.7):
        self.L = L
        self.G = Geo(ball_d)
        self.mount_z = L['bodyTop'] + 20.0 + SADDLE_T
        self.local = {}
        self.frame = {}
        self.meta = {}
        for name, fn, frame, mat, qty, rot, note in MADE:
            self.local[name] = fn(self.G)
            self.frame[name] = frame
            self.meta[name] = {'material': mat, 'qty': qty, 'note': note, 'solid': mat == 'pa6-cf', 'frame': frame,
                               'print_rotation': rot, 'doc': (fn.__doc__ or '').split('\n')[0].strip()}
        self.bought = bought_parts(self.G)
        for name, (shape, frame, _, _) in self.bought.items():
            self.local[name] = shape
            self.frame[name] = frame

    def pose_shape(self, shape, frame, pan=0.0, tilt=0.0, robot=True):
        G = self.G
        s = shape
        if frame == 'pinion' and pan:              # meshes with the ring: turns -63/21 x pan about the servo shaft
            x, y = G.servo_pan_xy
            s = s.rotate((x, y, 0), (x, y, 1), -pan * G.gear['z_ring'] / G.gear['z_pinion'])
        if frame == 'tilt':
            s = s.translate((0, 0, G.path_t))
            if tilt:
                s = s.rotate((0, 0, G.tilt_t), (0, 1, G.tilt_t), -tilt)
        if frame in ('pan', 'tilt') and pan:
            s = s.rotate((0, 0, 0), (0, 0, 1), pan)
        if robot:
            s = s.translate((0, 0, self.mount_z))
        return s

    def posed(self, pan=0.0, tilt=0.0, names=None, robot=True):
        names = names or list(self.local)
        return {n: self.pose_shape(self.local[n], self.frame[n], pan, tilt, robot) for n in names}

    def point(self, p, frame, pan=0.0, tilt=0.0, robot=True):
        """A point from a build frame to the robot (or T) frame."""
        v = cq.Vertex.makeVertex(*p)
        s = self.pose_shape(cq.Workplane('XY').add(v), frame, pan, tilt, robot)
        q = s.val()
        return (round(q.X, 2), round(q.Y, 2), round(q.Z, 2))


# designed contacts (bought part in its seat, plug on its receptacle): checked, but only flagged above the threshold
SKIP_PAIRS = {frozenset(p) for p in [('dt_plug', 'dt_receptacle')]}
# parts in different motion groups that touch by design: bearings on their journals and spacers, the horns on the
# pinion and on the cradle hub, the gear mesh (0.15 mm backlash per flank)
DESIGNED_CONTACTS = {frozenset(p) for p in [('pan_bearing', 'pan_ring'), ('tilt_bearing', 'cradle'), ('tilt_servo', 'cradle'),
                                            ('pan_ring', 'pan_pinion'), ('pan_servo', 'pan_pinion')]}


def clashes(T: Turret, tilts=(0.0, -20.0, -25.0), pans=(0.0, 90.0, -90.0, 170.0, -170.0), min_mm3=10.0, verbose=False,
            gaps=None, min_gap=1.0):
    """Pairs of turret parts (made and bought) that overlap by more than min_mm3, like leg.clashes_for_design. Parts in
    the same rigid group are checked once; base-pan pairs at every pan angle; pan-tilt pairs at every tilt; base-tilt
    pairs at every pan x tilt; the pinion turns with the ring (-3 x pan). Includes the proposed head ring and the DT
    plug's 30 mm withdrawal path (against fixed parts only: plug it in with the turret parked). Returns [[part, part, mm3, pan, tilt], ...]."""
    G = T.G
    names = list(T.local)
    extra = {'head_ring': (head_ring_tm(T.L).translate((0, 0, -T.mount_z)), 'base')}
    pl, f = DT['plug'], DT['flange']
    sweep = box(-pl[0] / 2, pl[0] / 2, -(G.dt_y + f[1] + pl[1] + DT['sweep']), -(G.dt_y + f[1] + pl[1]), DT_Z - pl[2] / 2, DT_Z + pl[2] / 2)
    local = dict(T.local)
    frame = dict(T.frame)
    for n, (s, fr) in extra.items():
        local[n], frame[n] = s, fr
        names.append(n)
    local['dt_plug_sweep'], frame['dt_plug_sweep'] = sweep, 'base'
    out = []
    cache = {}

    def get(n, pan, tilt):
        fr = frame[n]
        key = (n, pan if fr != 'base' else 0.0, tilt if fr == 'tilt' else 0.0)
        if key not in cache:
            s = T.pose_shape(local[n], fr, key[1], key[2], robot=False)
            v = s.val() if hasattr(s, 'val') else s
            cache[key] = (v, v.BoundingBox())
        return cache[key]

    def vol(a, b):
        try:
            return a.intersect(b).Volume()
        except Exception:
            return 0.0

    checked = set()
    allnames = names + ['dt_plug_sweep']
    for pan in pans:
        for tilt in tilts:
            for n1, n2 in itertools.combinations(allnames, 2):
                if frozenset((n1, n2)) in SKIP_PAIRS or {n1, n2} == {'dt_plug_sweep', 'dt_plug'}:
                    continue
                fs = {'pan' if frame[n] == 'pinion' else frame[n] for n in (n1, n2)}
                if 'dt_plug_sweep' in (n1, n2) and fs != {'base'}:
                    continue                              # the plug goes in with the turret parked: fixed parts only
                if 'pinion' in (frame[n1], frame[n2]):
                    key = (n1, n2, pan, tilt if 'tilt' in fs else 0.0)      # the pinion turns with pan
                elif len(fs) == 1:
                    key = (n1, n2, 0.0, 0.0)              # same rigid group: once
                elif fs == {'base', 'pan'}:
                    key = (n1, n2, pan, 0.0)
                elif fs == {'pan', 'tilt'}:
                    key = (n1, n2, 0.0, tilt)
                else:
                    key = (n1, n2, pan, tilt)
                if key in checked:
                    continue
                checked.add(key)
                a, ba = get(n1, key[2], key[3])
                b, bb = get(n2, key[2], key[3])
                g = min_gap if gaps is not None and frame[n1] != frame[n2] and frozenset((n1, n2)) not in DESIGNED_CONTACTS else 0.0
                if ba.xmax + g < bb.xmin or bb.xmax + g < ba.xmin or ba.ymax + g < bb.ymin or bb.ymax + g < ba.ymin or \
                        ba.zmax + g < bb.zmin or bb.zmax + g < ba.zmin:
                    continue
                v = vol(a, b)
                if g and v <= min_mm3:                    # moving past each other: how close?
                    dmin = a.distance(b)
                    if dmin < min_gap:
                        gaps.append([n1, n2, round(dmin, 2), key[2], key[3]])
                if verbose and v > 0.5:
                    print(f'    {n1} x {n2}: {v:.1f} mm3 at pan {key[2]}, tilt {key[3]}')
                if v > min_mm3:
                    out.append([n1, n2, round(v, 1), key[2], key[3]])
    return out


def mass_properties(T: Turret, tilt=0.0, with_balls=True, pan=0.0):
    """Mass and centre of mass of every part (printed parts by cadagent's printed-part model: PA6-CF 100 % solid,
    PETG and TPU 2 mm walls + 40 % infill) and of the whole turret, in the T frame (relative to the mount point:
    the pan axis on the TM face). Bought parts: catalogue mass at the envelope's centroid."""
    from cadagent.robot import printed_part_body
    rows = {}
    for name, m in T.meta.items():
        s = T.pose_shape(T.local[name], T.frame[name], pan, tilt, robot=False)
        v = s.val()
        wall, infill = (500.0, 1.0) if m['solid'] else (2.0, 0.4)
        body, rep = printed_part_body(v, DENS[m['material']], wall_mm=wall, infill=infill, name=name)
        com = [c * 1000 for c in body.com]
        rows[name] = {'mass_g': rep['mass_g'], 'qty': m['qty'], 'com_mm': com, 'volume_cm3': rep['volume_cm3'],
                      'material': m['material'], 'made': True}
        if m['qty'] == 2:                    # the second flywheel and tyre: mirror in y (in the cartridge frame)
            c2 = T.pose_shape(T.local[name].mirror('XZ'), T.frame[name], pan, tilt, robot=False).val()
            rows[name]['com_mm_2'] = [c * 1000 for c in printed_part_body(c2, DENS[m['material']], wall_mm=wall, infill=infill)[0].com]
    for name, (shape, frame, mass, note) in T.bought.items():
        if mass <= 0:
            continue
        c = cq.Shape.centerOfMass(T.pose_shape(shape, frame, pan, tilt, robot=False).val())
        rows[name] = {'mass_g': mass, 'qty': 1, 'com_mm': [c.x, c.y, c.z], 'made': False, 'note': note}
    G = T.G
    other_z = G.turntable_z[1]
    rows['not_modelled'] = {'mass_g': float(sum(NOT_MODELLED_G.values())), 'qty': 1, 'com_mm': [0.0, 0.0, other_z], 'made': False,
                            'note': '; '.join(f'{k} {v} g' for k, v in NOT_MODELLED_G.items()) + ' (est, at the turntable)'}
    if with_balls:
        bm = 30 * 1.83
        c = T.point((0, 0, (G.dial_z0 + G.hopper_top) / 2 - 8), 'tilt', pan, tilt, robot=False)
        rows['balls_30'] = {'mass_g': bm, 'qty': 1, 'com_mm': list(c), 'made': False, 'note': '30 Rival rounds x 1.83 g'}
    tot, mom = 0.0, [0.0, 0.0, 0.0]
    for r in rows.values():
        coms = [r['com_mm']] + ([r['com_mm_2']] if 'com_mm_2' in r else [r['com_mm']] * (r['qty'] - 1))
        for c in coms:
            tot += r['mass_g']
            mom = [m + r['mass_g'] * ci for m, ci in zip(mom, c)]
    com = [m / tot for m in mom]
    return rows, tot, com


def turret_parts(L, ball_d=22.7, pan=0.0, tilt=0.0):
    """The turret for the robot build, in the robot frame (x forward, y left, z up; mm), posed at (pan, tilt).

    Returns (made, meta, bought, info):
      made   {name: shape}  printed parts (qty in meta; the two flywheels/tyres: the +y one, mirror for the other)
      meta   {name: {material, qty, note, solid, frame, print_rotation}}  frame: 'base' fixed to the head, 'pan' turns
             about the pan axis, 'tilt' turns about the tilt axis too, 'pinion' turns -3 x pan about the pan servo's
             shaft (it meshes with the pan ring)
      bought {name: shape}  envelopes (servos, bearings, motors, ESCs, laser, DT receptacle and plug)
      info   {mount, pan_axis, tilt_axis, muzzle, muzzle_dir, tilt_range_deg, pan_range_deg, mass_estimate_g, com,
              head_ring, ...}"""
    T = Turret(L, ball_d)
    G = T.G
    P = T.posed(pan, tilt)
    made = {n: P[n] for n in T.meta}
    bought = {n: P[n] for n in T.bought}
    meta = {n: {k: v for k, v in m.items()} for n, m in T.meta.items()}
    rows, tot, com = mass_properties(T, tilt, pan=pan)
    rad = math.radians
    a = rad(tilt)
    d = (math.cos(a) * math.cos(rad(pan)), math.cos(a) * math.sin(rad(pan)), math.sin(a))
    info = {
        'mount': {'point': [0.0, 0.0, T.mount_z], 'interface': 'TM: 4 x M5 on 80 x 80, 2 x Ø5 dowels at (52, 0) and (0, -52), Ø45 centre hole',
                  'needs': 'head_ring_tm(L) in place of the head_saddle ring (see its docstring)'},
        'pan_axis': {'point': [0.0, 0.0, T.mount_z], 'dir': [0, 0, 1]},
        'tilt_axis': {'point': list(T.point((0, 0, G.tilt_c), 'tilt', pan, 0.0)), 'dir': [-math.sin(rad(pan)), math.cos(rad(pan)), 0.0]},
        'muzzle': list(T.point((G.barrel_x1, 0, 0), 'tilt', pan, tilt)),
        'muzzle_dir': [round(c, 4) for c in d],
        'laser_origin': list(T.point((LASER_X[1], LASER_Y, 0), 'tilt', pan, tilt)),
        'tilt_range_deg': [G.tilt_min, 0.0], 'pan_range_deg': [-170.0, 170.0], 'pan_hard_stop_deg': 173.5,
        'mass_estimate_g': round(tot, 1),
        'com': [round(c, 1) for c in (com[0], com[1], com[2] + T.mount_z)],
        'com_above_mount_mm': round(com[2], 1),
        'ball_d': ball_d, 'bore': G.bore, 'pose': {'pan': pan, 'tilt': tilt},
        'head_ring': head_ring_tm(L),
    }
    return made, meta, bought, info


# ------------------------------------------------------------------------------------------------ main

def derive(design: Path) -> dict:
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)['layout']


def print_fit(shape, rotation):
    s = shape
    if rotation:
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(*rotation[0]), rotation[1])
    bb = s.BoundingBox()
    dims = sorted((bb.xlen, bb.ylen), reverse=True) + [bb.zlen]
    return [round(d, 1) for d in dims], dims[0] <= BED[0] - 6 and dims[1] <= BED[1] - 6 and dims[2] <= BED[2] - 6


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    design = Path(args[0]) if args else R / 'designs/default.json'
    L = derive(design)
    out = R / 'exports' / 'turret'
    out.mkdir(parents=True, exist_ok=True)
    T = Turret(L)
    G = T.G
    print(f'turret on {design.name}: mount face at z = {T.mount_z:.1f} (bodyTop {L["bodyTop"]} + 20 + {SADDLE_T:.0f}); '
          f'ball path {G.path_t} mm and tilt axis {G.tilt_t} mm above it; ball Ø{G.ball}, bore Ø{G.bore}')

    # validity, bed fit, masses
    rows, tot, com = mass_properties(T, 0.0)
    _, tot_empty, com_empty = mass_properties(T, 0.0, with_balls=False)
    from cadagent.geometry import export_print_stl
    print('\nMADE PARTS (printed)')
    print(f'  {"part":16} {"qty":>3}  {"material":8} {"g each":>7} {"g total":>8} {"hours":>6}  {"bed (mm)":>18}  valid')
    made_g = made_h = 0.0
    summary = {'parts': {}, 'bought': {}}
    for name, m in T.meta.items():
        v = T.local[name].val()
        valid = v.isValid() and len(T.local[name].solids().vals()) == 1
        dims, fits = print_fit(v, m['print_rotation'])
        g = rows[name]['mass_g']
        hrs = g * m['qty'] / DENS[m['material']] / PRINT_RATE_CM3_H[m['material']]
        made_g += g * m['qty']
        made_h += hrs
        print(f'  {name:16} {m["qty"]:>3}  {m["material"]:8} {g:7.1f} {g * m["qty"]:8.1f} {hrs:6.1f}  {str(dims):>18}  '
              f'{"ok" if valid else "INVALID"}{"" if fits else "  DOES NOT FIT THE BED"}')
        summary['parts'][name] = {**{k: v for k, v in m.items() if k != 'print_rotation'}, 'mass_g_each': g, 'print_h': round(hrs, 1),
                                  'bed_mm': dims, 'fits_bed': fits, 'valid_single_solid': valid}
        posed = T.pose_shape(T.local[name], T.frame[name], robot=True).val()
        cq.exporters.export(posed, str(out / f'{name}.step'))
        export_print_stl(v, out / f'{name}.stl', rotation=m['print_rotation'])
    print(f'  {"made total":16} {"":>3}  {"":8} {"":>7} {made_g:8.1f} {made_h:6.1f}')
    print('\nBOUGHT PARTS (envelopes)')
    bought_g = 0.0
    for name, (shape, frame, mass, note) in T.bought.items():
        print(f'  {name:18} {mass:6.1f} g  {note}')
        bought_g += mass
        summary['bought'][name] = {'mass_g': mass, 'note': note, 'frame': frame}
        cq.exporters.export(T.pose_shape(shape, frame, robot=True).val(), str(out / f'asm_{name}.step'))
    nm = sum(NOT_MODELLED_G.values())
    print(f'  {"not modelled":18} {nm:6.1f} g  ' + ', '.join(f'{k} {v}' for k, v in NOT_MODELLED_G.items()))
    cq.exporters.export(head_ring_tm(L).val(), str(out / 'head_ring_tm.step'))
    print(f'\nTURRET: {tot / 1000:.3f} kg with 30 balls ({tot_empty / 1000:.3f} kg empty): made {made_g:.0f} g, bought {bought_g:.0f} g, '
          f'not modelled {nm} g, balls 55 g')
    print(f'  centre of mass from the mount point (pan axis on the TM face): x {com[0]:+.1f}, y {com[1]:+.1f}, z {com[2]:+.1f} mm '
          f'(empty: {com_empty[0]:+.1f}, {com_empty[1]:+.1f}, {com_empty[2]:+.1f})')
    # tilt balance: the moving group's centre of mass about the tilt axis
    tilt_names = [n for n in T.local if T.frame[n] == 'tilt']
    tm = sum(rows[n]['mass_g'] * rows[n].get('qty', 1) for n in tilt_names if n in rows) + rows['balls_30']['mass_g']
    tx = (sum(rows[n]['mass_g'] * (rows[n]['com_mm'][0] + (rows[n].get('com_mm_2') or rows[n]['com_mm'])[0] * (rows[n]['qty'] - 1))
              for n in tilt_names if n in rows) + rows['balls_30']['mass_g'] * rows['balls_30']['com_mm'][0]) / tm
    print(f'  tilting group {tm:.0f} g, centre {tx:+.1f} mm ahead of the tilt axis: holding torque {tm / 1000 * 9.81 * tx / 1000:.2f} N·m '
          f'(STS3215 stall 2.94); unpowered it rests on the -25 deg stop')

    # clash check
    print('\nCLASH CHECK (tilt 0, -20, -25 deg x pan 0, +-90, +-170 deg; incl. the proposed head ring and the DT plug path)')
    gaps = []
    cl = clashes(T, verbose=True, gaps=gaps)
    print('  no clashes' if not cl else '\n'.join(f'  CLASH {a} x {b}: {v} mm3 at pan {p}, tilt {t}' for a, b, v, p, t in cl))
    stop = lambda a, b, t: {a, b} == {'tilt_yoke', 'cradle'} and t in (0.0, G.tilt_min)
    print('  moving parts closer than 1 mm (designed contacts excluded): ' +
          ('none' if not gaps else '; '.join(f'{a} x {b} {d} mm at pan {p}, tilt {t}' + (' (the tilt hard stop, touching by design)' if stop(a, b, t) else '')
                                            for a, b, d, p, t in gaps)))
    made, meta, bought, info = turret_parts(L)
    info_out = {k: v for k, v in info.items() if k != 'head_ring'}
    print('\nINFO', json.dumps(info_out, indent=None)[:1500])
    summary.update({'info': info_out, 'clashes': cl, 'gaps_under_1mm': gaps, 'mass_g_with_balls': round(tot, 1), 'mass_g_empty': round(tot_empty, 1),
                    'com_from_mount_mm': [round(c, 1) for c in com], 'not_modelled_g': NOT_MODELLED_G,
                    'print_hours': round(made_h, 1), 'made_g': round(made_g, 1)})
    (out / 'turret.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    if '--no-render' not in sys.argv:
        render(T, L, out)


COL = {
    'pan_base': (0.30, 0.32, 0.35), 'pan_clamp': (0.40, 0.42, 0.45), 'pan_ring': (0.85, 0.42, 0.10), 'pan_pinion': (0.95, 0.62, 0.30),
    'tilt_yoke': (0.35, 0.37, 0.40), 'cradle': (0.20, 0.45, 0.75), 'cartridge_body': (0.45, 0.47, 0.50),
    'flywheel': (0.25, 0.25, 0.27), 'flywheel_tyre': (0.10, 0.10, 0.10), 'dial': (0.95, 0.80, 0.20),
    'hopper': (0.70, 0.85, 0.95, 0.35), 'hopper_lid': (0.70, 0.85, 0.95, 0.6), 'hopper_flap': (0.70, 0.85, 0.95, 0.8),
    'barrel': (0.95, 0.45, 0.10), 'laser_mount': (0.30, 0.65, 0.35), 'bumper_ring': (0.15, 0.15, 0.17),
    'pan_servo': (0.12, 0.12, 0.14), 'tilt_servo': (0.12, 0.12, 0.14), 'pan_bearing': (0.75, 0.75, 0.78),
    'tilt_bearing': (0.75, 0.75, 0.78), 'dt_receptacle': (0.55, 0.55, 0.20), 'dt_plug': (0.55, 0.55, 0.20, 0.5),
    'flywheel_motor_l': (0.65, 0.15, 0.15), 'flywheel_motor_r': (0.65, 0.15, 0.15), 'esc_l': (0.1, 0.35, 0.15), 'esc_r': (0.1, 0.35, 0.15),
    'feed_motor': (0.25, 0.25, 0.60), 'feed_esc': (0.1, 0.35, 0.15), 'laser': (0.15, 0.6, 0.15),
    'head_ring': (0.80, 0.82, 0.85, 0.5), 'j501_top': (0.80, 0.82, 0.85, 0.25), 'ball': (0.98, 0.55, 0.10),
}


def _shape_items(P, extra=()):
    items = []
    for n, s in P.items():
        if n == 'flywheel' or n == 'flywheel_tyre':
            items.append((s.val(), COL[n]))
            items.append((s.mirror('XZ').val(), COL[n]))
            continue
        items.append((s.val() if hasattr(s, 'val') else s, COL.get(n, (0.6, 0.6, 0.6))))
    items += list(extra)
    return items


def _place_labels(items, view, top=150, bottom=950, x_left=40, x_right=1080):
    """Callouts without crossing leaders: project each anchor along the camera direction (parallel projection, as the
    renderer does), send it to the left or right column by its screen x, order each column by screen y, and number
    them in reading order. items: [(text, world_point)]."""
    d = view
    n = math.sqrt(sum(c * c for c in d))
    f = [-c / n for c in d]                                     # looking direction
    up = (0.0, 0.0, 1.0)
    right = (f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0])
    rn = math.sqrt(sum(c * c for c in right))
    right = [c / rn for c in right]
    upv = (right[1] * f[2] - right[2] * f[1], right[2] * f[0] - right[0] * f[2], right[0] * f[1] - right[1] * f[0])
    proj = [(sum(a * b for a, b in zip(pt, right)), -sum(a * b for a, b in zip(pt, upv)), text, pt) for text, pt in items]
    order = sorted(proj, key=lambda q: q[0])                    # the left half of the anchors goes to the left column
    half = (len(order) + 1) // 2
    cols = [sorted(order[:half], key=lambda q: q[1]), sorted(order[half:], key=lambda q: q[1])]
    out, k = [], 1
    for col, x in zip(cols, (x_left, x_right)):
        step = (bottom - top) / max(1, len(col) - 1) if len(col) > 1 else 0
        for i, (_, _, text, pt) in enumerate(col):
            out.append((str(k), text, pt, (x, int(top + i * step))))
            k += 1
    return out


def render(T, L, out):
    from cadagent.render import Renderer
    G = T.G
    r = Renderer(out, size=(1600, 1150), subtitle='Gyropup foam-ball turret (Rival rounds Ø22.7): every part printed, bought parts as envelopes')
    P = T.posed(0.0, 0.0)
    B = L['body']
    j501 = box(-B['depth'] / 2, B['depth'] / 2, -B['width'] / 2, B['width'] / 2, L['bodyTop'] - 40, L['bodyTop'])
    extra = [(head_ring_tm(L).val(), COL['head_ring']), (j501.val(), COL['j501_top'])]
    p = lambda pt, fr='tilt': T.point(pt, fr, 0.0, 0.0)
    mz = T.mount_z
    view = (0.45, -1.0, 0.5)
    labels = _place_labels([
        ('hopper, 30 balls (translucent PETG)', p((-30, -G.dial_wall_r - 2, 55))),
        ('fill port + sprung flap (dock spout)', p((FILL_PORT[0], 0, G.hopper_top + 3))),
        ('tilt yoke; hard stops at 0 and -25 deg inside', (0, -G.arm_y[1], mz + G.tilt_t - 40)),
        ('M2006 dial motor (under the dial floor)', p((0, -M2006['d'] / 2, 0))),
        ('pan servo STS3215 + 21 T pinion', (G.servo_pan_xy[0], -16.0, mz + 20)),
        ('pan base on the TM pattern', (30, -64, mz + 12)),
        ('proposed head ring: 4 x M5 inserts', (60, -20, mz - 4)),
        ('Snail 2305 motors hang under this plate', p((G.wheel_x, -G.wheel_y, G.plate_z1))),
        ('cartridge: dial housing, chute, flywheel cage', p((G.wheel_x, -G.cage_y, 10))),
        ('barrel Ø30, bore ball + 1.5, orange tip', p((G.barrel_x1 - 20, -G.barrel_od / 2, 0))),
        ('aiming laser (on the cradle)', p((LASER_X[1] + 10, LASER_Y - 6, 0))),
        ('cradle: cartridge on 2 dowels + thumbscrew', p((40, -G.cheek_y[1], G.rail_z[0] + 2))),
        ('pan ring: 63 T gear on the 61810', (0, -40, mz + 52)),
        ('DT 12-way receptacle (head <-> turret)', (0, -(G.dt_y + 20), mz + DT_Z)),
        ('TPU bumper ring', (60, -55, mz + 12)),
    ], view)
    r.render('turret.png', shapes=_shape_items(P, extra), view=view, labels=labels, zoom=0.86,
             caption='The turret at tilt 0: pan base, yoke, cradle and ball cartridge',
             note=f'Mount face at bodyTop + 28 mm. Pan +-170 deg (hard stops at +-173.5), tilt 0 .. -25 deg; the barrel cannot point above horizontal.')
    # section through the ball path (y = 0), with balls
    bl = [(T.pose_shape(b, 'tilt').val(), COL['ball']) for b in balls(G)]
    Ps = {n: s for n, s in P.items() if n not in ('hopper_lid', 'hopper_flap', 'dt_plug')}
    items = [(sh, (*c[:3], 1.0)) for sh, c in _shape_items(Ps, [(head_ring_tm(L).val(), COL['head_ring'])])] + bl
    lab = _place_labels([
        ('hopper: balls fall into the dial pockets', p((-30, 0, 55))),
        ('dial (8 pockets) on the M2006', p((-G.rp, 0, G.dial_z0 + 10))),
        ('exit hole: the ball drops ...', p((G.exit_x, 0, G.floor_z))),
        ('... and the chute turns it forward', p((G.chute_cx - 15, 0, 3))),
        ('flywheel nip (crush 2.7 mm)', p((G.wheel_x, 4, 0))),
        (f'barrel, bore Ø{G.bore:.1f}', p((G.barrel_x0 + 50, 0, G.br))),
        ('tilt axis (on the dial axis)', p((0, 0, G.tilt_c))),
        ('M2006 + C610 under the dial floor', p((-25, 0, -5))),
        ('pan: 61810 bearing, 40 mm open centre', (0, 0, mz + G.brg_z + 3)),
        ('pan stop post (finger meets it at +-173.5 deg)', (G.post_r[0] + 2, 0, mz + 30)),
    ], (0.0, -1.0, 0.0), top=170, bottom=900)
    r.render('turret-section.png', shapes=items, view='section', labels=lab, zoom=1.0, clip=((0, 0.01, 0), (0, 1, 0)),
             caption='Section on the ball path (y = 0): hopper -> dial -> chute -> flywheels -> barrel',
             note=f'Ball Ø{G.ball} in a Ø{G.bore} path (+1.5 mm). The dial parks with a spoke over the exit hole, so nothing reaches the wheels with the motor off.')


if __name__ == '__main__':
    main()
