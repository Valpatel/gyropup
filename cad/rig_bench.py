"""Bench fixtures and fit coupons for the first leg (docs/leg-prototype-plan.md task T4, section 5), printed while the
parts ship:

    .venv/bin/python cad/rig_bench.py          # exports/rig/bench/: <part>.step + print-ready .stl, print-plan.json

  dyno_lug_plate x 2   PETG    an RS-04 on its 10 x M4 output-side lugs (M4 x 20, the leg's screw), standing on a board
  dyno_hub x 2         PETG    on each motor's output (3 pin sockets, 9 x M5 x 25, the leg's D46 screw), three jaws
  dyno_spider x 2      TPU     between the two hubs' jaws: B1 back-drives one motor with the other through it, and the
                               spider takes the two axes' misalignment that would otherwise show as drag
  press_cage x 1       PETG    B3, B4: a frame round the S-type load cell on the press's axis (the cell hangs from the top
                               beam; what is tested comes up from the bottom beam)
  press_base, press_slider     B3: an M12 x 80 bolt through the base's nut lifts the slider
  sleeve_block x 1     PA6-CF  B3: a real stop post (the Ø16 pin) in a blind hole as the hip frame's, its TPU sleeve
                               under sleeve_anvil (the link's edge)
  sleeve_anvil x 1     PA6-CF  hung from the cell's lower thread
  puller_m5 x 3        PA6-CF  B4: a heat-set insert as the hip frame has it (axis along the print's z), hung from
                               the cell; the screw under test comes up into it
  bearing_disc x 3     PA6-CF  B4: the upper link's material under an M5 head
  (B5, the tyre, runs on the rig with the leg: docs/leg-bench-tests.md)
  coupon_* (x 3 each)  PA6-CF  the leg's seats at -0.1, 0 and +0.1 mm: the hip frame's motor ring and 61812 seat, the
                               upper link's hub face (D46 pattern), its knee eye (an eye sleeve), the lower links' knee
                               boss (a 6201), the front link's apex eye (a 61812), the wheel link's hub journal (a 61812's
                               inner race) with its circlip groove

Every coupon carries its variant engraved (-0.1 / 0 / +0.1, the change to the seat's diameter from the leg's CAD).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402
import gmi  # noqa: E402
import printplan  # noqa: E402

OUT = R / 'exports' / 'rig' / 'bench'
FAST = gmi.FAST
MI = gmi.motor_interface(fb.MOTOR)
VARIANTS = (-0.1, 0.0, 0.1)
# D46 (main session, 2026-10-27): the machined adapter's face: 8 x M5 tapped at these angles and 2 x Ø5 H7 dowels, PCD 50
D46_BOLTS_DEG = (0, 30, 90, 120, 180, 210, 270, 300)
D46_DOWELS_DEG = (60, 150)
D46_SPIGOT_RECESS = 40.1


def zc(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def bx(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def pts(pcd, angles):
    return [(pcd / 2 * math.cos(math.radians(a)), pcd / 2 * math.sin(math.radians(a))) for a in angles]


def engrave(s, text, x, y, z_top, size=5.0, depth=0.6):
    """Cut a label into the face at z_top."""
    try:
        t = cq.Workplane('XY').workplane(offset=z_top - depth).center(x, y).text(text, size, depth + 0.2, combine=False, halign='center', valign='center')
        return s.cut(t)
    except Exception:
        return s


def label(v: float) -> str:
    return '0' if v == 0 else f'{v:+.1f}'


# ----------------------------------------------------------------------------------- the dyno (B1, B2)

DYNO_AXIS_Z = 90.0                   # the motors' axis above the board
LUG_T = 14.0                         # main ring; thickening this whole face would intersect the rotating hub disc
LUG_HEAD_BOSS_H = 1.6                # local seats: 15.6 mm grip with M4 x 20 gives 4.4 mm nominal penetration
LUG_HEAD_BOSS_R = 5.0                # centred at r53, clears the rotating r45 disc by 3 mm radially
DYNO_DISC_RELIEF_R = 46.0
DYNO_DISC_RELIEF_Y = 13.0            # disc rear face is nominally y14; 0.7 mm gap at output offset 0.2 mm


def lug_screw_seat_y():
    return LUG_T + LUG_HEAD_BOSS_H


def dyno_lug_plate():
    """PETG: a ring round the motor's lug circle (the output-side lug face against its back, y = 0; the output flange
    in the central hole, 0.5 mm proud of the lug face) on two legs and a foot with four slots for M6 bolts through the
    board. Local raised screw seats preserve the rotating hub's path; the central
    front relief provides nominal axial disc clearance. Printed on its foot.
    Printed dimensions and thread engagement require measurement before use."""
    b = MI['case']['bolts']
    ring = cq.Workplane('XZ', origin=(0, LUG_T, 0)).center(0, DYNO_AXIS_Z).circle(66.0).circle(29.0).extrude(LUG_T)
    s = ring
    for sx in (-1, 1):                                                               # legs to the foot
        s = s.union(bx(sx * 50 - 9, sx * 50 + 9, 0, LUG_T, 0, DYNO_AXIS_Z - 20))
        g = cq.Workplane('YZ', origin=(sx * 50 - 4, 0, 0)).polyline([(-55, 8), (0, 8), (0, 60)]).close().extrude(8)
        s = s.union(g)
    s = s.union(bx(-75, 75, -60, LUG_T, 0, 8))                                       # foot (behind: the motor's side)
    for (x, z) in pts(b['pcd'], [fb.RS04_LUG0 + 36 * k for k in range(10)]):
        s = s.union(cq.Workplane('XZ', origin=(0, lug_screw_seat_y(), 0))
                    .center(x, DYNO_AXIS_Z + z).circle(LUG_HEAD_BOSS_R).extrude(LUG_HEAD_BOSS_H + 0.01))
        s = s.cut(cq.Workplane('XZ', origin=(0, lug_screw_seat_y() + 1, 0))
                  .center(x, DYNO_AXIS_Z + z).circle(gmi.clear('M4') / 2).extrude(lug_screw_seat_y() + 2))
    s = s.cut(cq.Workplane('XZ', origin=(0, LUG_T + 1, 0)).center(0, DYNO_AXIS_Z)
              .circle(DYNO_DISC_RELIEF_R).extrude(LUG_T + 1 - DYNO_DISC_RELIEF_Y))
    for a in fb.RS04_DOWELS:                                                         # Ø5 x 16 dowels into the motor's holes
        x, z = b['pcd'] / 2 * math.cos(math.radians(a)), b['pcd'] / 2 * math.sin(math.radians(a))
        s = s.cut(cq.Workplane('XZ', origin=(0, 6.0, 0)).center(x, DYNO_AXIS_Z + z).circle(2.5 - 0.03).extrude(7.0))
    for x in (-62, 62):
        for y in (-48, -20):
            s = s.cut(cq.Workplane('XY').workplane(offset=-1).center(x, y).slot2D(14, 6.8, 90).extrude(10))
    return s


def dyno_hub():
    """PETG, one on each motor's output: a boss through the lug plate's hole onto the output flange (3 pin sockets, 9 x
    M5 x 25 counterbored from the jaw side), a disc, three 45 deg jaws at r 26-44. Built along +z from the output face."""
    o = MI['output']
    s = zc(27.0, 0.0, 13.5).union(zc(45.0, 13.5, 23.5))
    for k in range(3):                                                               # jaws
        a0 = 120 * k - 22.5
        jaw = (cq.Workplane('XY').workplane(offset=23.5).moveTo(26 * math.cos(math.radians(a0)), 26 * math.sin(math.radians(a0)))
               .lineTo(44 * math.cos(math.radians(a0)), 44 * math.sin(math.radians(a0)))
               .threePointArc((44 * math.cos(math.radians(a0 + 22.5)), 44 * math.sin(math.radians(a0 + 22.5))),
                              (44 * math.cos(math.radians(a0 + 45)), 44 * math.sin(math.radians(a0 + 45))))
               .lineTo(26 * math.cos(math.radians(a0 + 45)), 26 * math.sin(math.radians(a0 + 45)))
               .threePointArc((26 * math.cos(math.radians(a0 + 22.5)), 26 * math.sin(math.radians(a0 + 22.5))),
                              (26 * math.cos(math.radians(a0)), 26 * math.sin(math.radians(a0)))).close().extrude(20.0))
        s = s.union(jaw)
    for (x, y) in pts(o['bolts']['pcd'], o['bolts']['angles']):
        s = s.cut(zc(gmi.clear('M5') / 2, -1, 24, x, y)).cut(zc(4.75, 23.5 - 4.5, 45, x, y))
    for (x, y) in pts(o['dowels']['pcd'], o['dowels']['angles']):
        s = s.cut(zc(o['dowels']['d'] / 2 + 0.03, -1, (o['dowels']['protrusion'] or 3.0) + 0.5, x, y))
    return s


def dyno_spider():
    """TPU 95A: six 13.5 deg arms (r 26.3-43.7) on a ring, filling the gaps between the two hubs' interleaved jaws."""
    s = zc(25.8, 0.0, 19.5).cut(zc(22.0, -1, 21))
    for k in range(6):
        c = 60 * k + 30.0                                                            # between a jaw (centred 0, 120, 240) and the
        a0, a1 = c - 6.6, c + 6.6                                                     # other hub's (60, 180, 300)
        arm = (cq.Workplane('XY').moveTo(25.0 * math.cos(math.radians(a0)), 25.0 * math.sin(math.radians(a0)))
               .lineTo(43.7 * math.cos(math.radians(a0)), 43.7 * math.sin(math.radians(a0)))
               .threePointArc((43.7 * math.cos(math.radians(c)), 43.7 * math.sin(math.radians(c))),
                              (43.7 * math.cos(math.radians(a1)), 43.7 * math.sin(math.radians(a1))))
               .lineTo(25.0 * math.cos(math.radians(a1)), 25.0 * math.sin(math.radians(a1))).close().extrude(19.5))
        s = s.union(arm)
    return s


# ----------------------------------------------------------------------------------- B3, B4: the press cage

# One printed frame holds the S-type load cell on the press's axis for both tests (docs/leg-bench-tests.md):
#   B4  the cell hangs from the top beam; an M12 x 80 stud from its lower thread carries a puller (an insert coupon,
#       insert facing down, keyed against turning by its wings on the side walls); the screw under test comes up through
#       the bottom beam into the insert, so its tension IS the cell's reading (torque-tension, proof load, pull-out);
#   B3  the same cell, now pushed: an M12 x 80 hex bolt through a nut in the press base lifts a slider carrying the
#       stop post (in its own M8 insert) and TPU sleeve against the anvil hung from the cell by an M12 x 30 screw.
# The cell: Phidgets 3140_0 (S-type, 500 kg, M12 x 1.75 both ends, 51 x 76 x 19/26 mm), its 51 mm width across the
# frame's depth so the cable gland points out of the front. Frame coordinates: the press axis along +y at x = 0,
# z = CAGE_D / 2; y = 0 the frame's bottom face. It lies flat to print (z up) and on its side on the bench in use.
CELL = {'w': 51.0, 'h': 76.0, 't': 26.0}
CAGE_IN = 37.0                       # half the window's width
CAGE_WALL = 10.0
CAGE_D = 50.0
CAGE_BOT, CAGE_WIN, CAGE_TOP = 32.0, 182.0, 28.0
CAGE_H = CAGE_BOT + CAGE_WIN + CAGE_TOP
Y_WIN0, Y_WIN1 = CAGE_BOT, CAGE_BOT + CAGE_WIN          # 32, 214
Y_CELL0 = Y_WIN1 - CELL['h']                             # the cell's lower face, 138
CBORE_UNDER = (33.0, 14.0)           # under the bottom beam: the test screws' washer (the 3/8 in one is 31.75) and head
CBORE_TOP = (20.0, 13.0)             # on the top beam: the M12 x 30 into the cell's upper thread
PULLER_H, PULLER_GAP = 60.0, 5.0     # the puller's insert face 5 mm above the bottom beam
NUT12 = (19.4, 11.2)                 # an M12 nut's pocket: across flats, thickness


def _ycyl(r, y0, y1, x=0.0, z=CAGE_D / 2):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def _hex_pts(af, cx, cy):
    """A hexagon's corners, flats normal to the first axis (so it slides along the second)."""
    r = af / 2 / math.cos(math.radians(30))
    return [(cx + r * math.cos(math.radians(30 + 60 * k)), cy + r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]


def press_cage():
    """PETG: the frame (x +-47, y 0-242, z 0-50). Bottom beam y 0-32: the M12 x 80 press bolt or the screw under test
    through Ø13, a Ø33 x 14 counterbore from below for its head and washer. Top beam y 214-242: the M12 x 30 into the
    cell's upper thread through Ø13, its head in a Ø20 x 13 counterbore. Walls 10 mm; the window 74 x 182."""
    o = CAGE_IN + CAGE_WALL
    s = bx(-o, o, 0, CAGE_H, 0, CAGE_D).cut(bx(-CAGE_IN, CAGE_IN, Y_WIN0, Y_WIN1, -1, CAGE_D + 1))
    s = s.cut(_ycyl(6.5, -1, Y_WIN0 + 1)).cut(_ycyl(CBORE_UNDER[0] / 2, -1, CBORE_UNDER[1]))
    s = s.cut(_ycyl(6.5, Y_WIN1 - 1, CAGE_H + 1)).cut(_ycyl(CBORE_TOP[0] / 2, CAGE_H - CBORE_TOP[1], CAGE_H + 1))
    for sx in (-1, 1):                                                               # 8 mm gussets in the top corners (the
        x0 = sx * CAGE_IN                                                            # base and slider fill the bottom ones)
        g = cq.Workplane('XY').polyline([(x0, Y_WIN1), (x0 - sx * 8, Y_WIN1), (x0, Y_WIN1 - 8)]).close().extrude(CAGE_D)
        s = s.union(g)
    return s


def press_base():
    """PETG: on the bottom beam inside the window (73 x 20 x 50); the press bolt's M12 nut in a pocket slid in from the
    front, 3 mm above the beam (the bolt's thrust goes straight into the beam)."""
    s = bx(-CAGE_IN + 0.5, CAGE_IN - 0.5, 0, 20, 0, CAGE_D)
    s = s.cut(_ycyl(6.5, -1, 21))
    s = s.cut(_hex_pocket(3.0, 3.0 + NUT12[1]))
    return s


def _hex_pocket(y0, y1, x=0.0, zc_=CAGE_D / 2):
    """An M12 nut's pocket round the press axis between y0 and y1, flats normal to x, run out of the front (z = CAGE_D)."""
    af = NUT12[0]
    h = cq.Workplane('XZ', origin=(0, y1, 0)).polyline(_hex_pts(af, x, zc_)).close().extrude(y1 - y0)
    return h.union(bx(x - af / 2, x + af / 2, y0, y1, zc_, CAGE_D + 1))


def press_slider():
    """PETG: rides on the press bolt's tip (an M12 washer in the Ø24.5 recess underneath), 73 wide so the walls keep it
    square; the tab out of the front is for the dial indicator's tip."""
    s = bx(-CAGE_IN + 0.5, CAGE_IN - 0.5, 0, 10, 0, CAGE_D)
    s = s.cut(_ycyl(12.25, -1, 2.5))
    s = s.union(bx(20, 34, 0, 10, CAGE_D - 1, CAGE_D + 20))
    return s


def sleeve_block():
    """PA6-CF: an L standing on the slider against the left wall: the upright (x -36.5 to -10, 40 tall) holds a stop
    post (D53: the Ø16 x 40 pin) in a blind hole on its +x face, 25 mm up, drawn and printed as the hip frame's (the
    same diameter, depth and orientation of the hole to the layers), so the pin's free 17 mm lies across the press axis
    with its TPU sleeve on it; the foot runs under the sleeve to x +25 so the anvil's push lands inside the block's
    footprint. The pin goes in as in the leg (pressed, the same compound)."""
    d, _, depth = fb.STOP_PIN
    up = bx(-CAGE_IN + 0.5, -10.0, 0, 40, 5, CAGE_D - 5)
    foot = bx(-10.0, 25.0, 0, 25.0 - fb.TPU_SLEEVE[0] / 2 - 1.0, 5, CAGE_D - 5)   # 1 mm under the sleeve: the load goes
    s = up.union(foot)                                                          # through the pin, not the foot
    s = s.cut(cq.Workplane('YZ', origin=(-10.0 + 0.01, 0, 0)).center(25.0, CAGE_D / 2)
              .circle(d / 2 + fb.STOP_HOLE_PLAY).extrude(-depth - 0.01))
    return s


def sleeve_anvil():
    """PA6-CF: a 30 x 30 flat face (like the upper link's edge) pressed onto the sleeve; on top, a Ø20 x 13 socket for
    the head of the M12 x 30 that hangs it from the cell's lower thread. Printed face down."""
    s = bx(-15, 15, 0, 18, CAGE_D / 2 - 15, CAGE_D / 2 + 15)
    s = s.cut(_ycyl(10.0, 18 - 13.0, 19))
    return s


def puller(size: str):
    """PA6-CF, printed with the insert's axis along z as in the hip frame (insert face up on the bed's far side). In
    the cage it hangs insert-down from the M12 x 80 stud: the stud's nut in a pocket slid in from the side, the wings
    (73 wide) against the side walls take the test screw's torque. M5: Ø6.4 x 11 pilot (the leg's only inserts since
    D53 turned the M8 stop posts into Ø16 pins)."""
    pilot, depth, clear = {'M5': (6.4, 11.0, 5.5)}[size]
    H = PULLER_H
    s = bx(-15, 15, -15, 15, 0, H).union(bx(-CAGE_IN + 0.5, CAGE_IN - 0.5, -15, 15, 0, 10))
    s = s.cut(zc(6.25, -1, 8.8))                                                     # the stud's way in
    nut = cq.Workplane('XY').workplane(offset=8.8).polyline(_hex_pts(NUT12[0], 0, 0)).close().extrude(NUT12[1])
    nut = nut.union(bx(-NUT12[0] / 2, NUT12[0] / 2, 0, 16, 8.8, 8.8 + NUT12[1]))    # slid in from +y
    s = s.cut(nut)
    s = s.cut(zc(6.25, 8.8 + NUT12[1] - 0.1, 34.0))                                   # the stud's end, below the nut
    s = s.cut(zc(pilot / 2, H - depth, H + 1)).cut(zc(clear / 2, 38.0 if size == 'M5' else 36.0, H - depth + 0.1))
    return s


def bearing_disc():
    """PA6-CF, B4: the upper link's material under an M5 head (Ø20 x 6, Ø5.5), printed flat as the link's outer face;
    in the cage it sits on an M6 oversized washer, as the link sits on the adapter's face."""
    return zc(10.0, 0, 6.0).cut(zc(gmi.clear('M5') / 2, -1, 7))


def cage_stack():
    """The B3 and B4 heights in the frame's coordinates (mm), for the doc and the checks."""
    head_engaged = 15.0                                                              # M12 x 30 into the cell, assumed
    cell_low = Y_CELL0
    shcs_head_low = cell_low - (30.0 - head_engaged) - 12.0                          # M12 SHCS head: 18 x 12
    post_axis = 52.0 + 10.0 + 25.0                                                   # base top 52, slider 10, insert 25 up
    od = fb.TPU_SLEEVE[0]
    anvil_face = post_axis + od / 2
    socket_floor = anvil_face + 18.0 - 13.0
    stud_end = cell_low + head_engaged - 80.0
    insert_face = Y_WIN0 + PULLER_GAP
    nut_low = insert_face + PULLER_H - 8.8 - NUT12[1]
    roof = CBORE_UNDER[1]
    return {'cell': (cell_low, Y_WIN1), 'b3_slack_mm': round(shcs_head_low - socket_floor, 1), 'b3_sleeve_od': od,
            'b4_stud_end': stud_end, 'b4_nut': (nut_low, nut_low + NUT12[1]), 'b4_nut_engaged': stud_end <= nut_low,
            'b4_insert_face': insert_face,
            'b4_reach': {'M5 x 40 + 1.6 washer': round(roof - 1.6 + 40 - insert_face, 1),
                         'M5 x 40 + 6 disc + 1.6 washer': round(roof - 7.6 + 40 - insert_face, 1),
                         'M8 x 40 + 2.4 washer': round(roof - 2.4 + 40 - insert_face, 1)}}


def _steel_cyl(d, y0, y1, x=0.0):
    return _ycyl(d / 2, y0, y1, x)


def _hex_y(af, y0, y1):
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(_hex_pts(af, 0, CAGE_D / 2)).close().extrude(y1 - y0)


def press_scenes() -> dict:
    """The press cage set up for B4 (an M5 insert under test) and for B3 (a stop sleeve), in the frame's coordinates,
    bought parts as simple stand-ins: {scene: [(name, shape, colour)]}."""
    PETG, CF, TPU, STEEL, CELLC, BRASS = (0.93, 0.93, 0.9), (0.22, 0.22, 0.24), (0.95, 0.55, 0.15), (0.62, 0.64, 0.68), (0.35, 0.47, 0.62), (0.82, 0.66, 0.3)
    st = cage_stack()
    c0, c1 = st['cell']
    cell = bx(-CELL['t'] / 2, CELL['t'] / 2, c0, c1, CAGE_D / 2 - CELL['w'] / 2, CAGE_D / 2 + CELL['w'] / 2)
    for sx, yy in ((1, c0 + 22), (-1, c1 - 22)):                                     # the S's two slots
        za, zb = CAGE_D / 2 - sx * (CELL['w'] / 2 + 1), CAGE_D / 2 + sx * 10
        cell = cell.cut(bx(-CELL['t'] / 2 - 1, CELL['t'] / 2 + 1, yy - 2.5, yy + 2.5, min(za, zb), max(za, zb)))
    top_screw = _steel_cyl(12, c1 - 15, CAGE_H - CBORE_TOP[1]).union(_steel_cyl(18, CAGE_H - CBORE_TOP[1], CAGE_H - CBORE_TOP[1] + 12))
    common = [('press_cage', press_cage(), PETG), ('load cell', cell, CELLC), ('M12 x 30 (top)', top_screw, STEEL)]
    # B4: the puller hung on the stud, an M5 x 40 and its washer from below
    ins = st['b4_insert_face']
    pul = puller('M5').rotate((0, 0, 0), (1, 0, 0), 90).translate((0, ins + PULLER_H, CAGE_D / 2))
    stud = _steel_cyl(12, st['b4_stud_end'], st['b4_stud_end'] + 80)
    nut = _hex_y(NUT12[0] - 0.4, st['b4_nut'][0] + 0.2, st['b4_nut'][1] - 0.2).cut(_steel_cyl(12, 0, CAGE_H))
    roof = CBORE_UNDER[1]
    washer = _steel_cyl(18, roof - 1.6, roof).cut(_steel_cyl(6.4, 0, CAGE_H))
    screw = _steel_cyl(5, roof - 1.6, roof - 1.6 + 40).union(_steel_cyl(8.5, roof - 6.6, roof - 1.6))
    insert = _steel_cyl(6.4, ins, ins + 7.9).cut(_steel_cyl(5, 0, CAGE_H))
    b4 = common + [('puller (PA6-CF)', pul, CF), ('M12 x 80 stud', stud, STEEL), ('M12 nut', nut, STEEL),
                   ('M5 insert', insert, BRASS), ('M5 x 40 under test', screw, STEEL), ('washer', washer, STEEL)]
    # B3: base, bolt, slider, block with the post and its sleeve, the anvil on the M12 x 30 in the cell's lower thread
    od = fb.TPU_SLEEVE[0]
    y_slider, y_block = 52.0, 62.0
    axis = y_block + 25.0
    anvil_y = axis + od / 2
    low_screw = _steel_cyl(12, c0 - 15, c0 + 15).union(_steel_cyl(18, c0 - 27, c0 - 15))
    bolt = _steel_cyl(12, y_slider - 80, y_slider).union(_hex_y(18, y_slider - 87.5, y_slider - 80))
    nut3 = _hex_y(NUT12[0] - 0.4, 3.2 + Y_WIN0, 3.0 + NUT12[1] - 0.2 + Y_WIN0).cut(_steel_cyl(12, 0, CAGE_H))
    pd, pl, pdepth = fb.STOP_PIN
    post = cq.Workplane('YZ', origin=(-10.0 - pdepth, 0, 0)).center(axis, CAGE_D / 2).circle(pd / 2).extrude(pl)
    sleeve = (cq.Workplane('YZ', origin=(-10.0, 0, 0)).center(axis, CAGE_D / 2).circle(od / 2).circle(pd / 2)   # on the block's
              .extrude(fb.STOP_SLEEVE_TOP - fb.Y['frame'][1]))                                                # face, as on the frame's
    b3 = common + [('press_base', press_base().translate((0, Y_WIN0, 0)), PETG), ('M12 nut', nut3, STEEL),
                   ('M12 x 80 press bolt', bolt, STEEL), ('press_slider', press_slider().translate((0, y_slider, 0)), PETG),
                   ('sleeve_block', sleeve_block().translate((0, y_block, 0)), CF), ('stop post', post, STEEL),
                   ('TPU sleeve', sleeve, TPU), ('sleeve_anvil', sleeve_anvil().translate((0, anvil_y, 0)), CF),
                   ('M12 x 30 (lower)', low_screw, STEEL)]
    return {'b4': b4, 'b3': b3}


def render_setups() -> list:
    """exports/rig/bench/press-b4.png and press-b3.png: the press axis up, seen through the open front of the window."""
    from cadagent.render import Renderer
    r = Renderer(OUT, size=(1100, 1300), subtitle='GYROPUP LEG RIG | BENCH')
    out = []
    captions = {'b4': ('B4: an insert under test', 'The cell hangs from the top beam; the screw under test comes up into the puller'),
                'b3': ('B3: a stop sleeve', 'The press bolt lifts the slider; the sleeve meets the anvil hung from the cell')}
    for k, items in press_scenes().items():
        shapes = [((sh.rotate((0, 0, 0), (1, 0, 0), 90)).val(), col) for _, sh, col in items]
        f = f'press-{k}.png'
        r.render(f, shapes=shapes, view=(0.45, -1.0, 0.3), caption=captions[k][0], note=captions[k][1], zoom=0.95)
        out.append(OUT / f)
    return out


# ----------------------------------------------------------------------------------- fit coupons (PA6-CF)

def coupon_frame_ring_parent(frame=None):
    """Exact front motor ring cut from the parent, still in the parent's coordinates.

    Keep screw seats, dowels and the full lug stack; a bearing-seat-only ring cannot
    validate motor mounting. Pass an already-built frame to avoid rebuilding it.
    """
    frame = fb.hip_frame() if frame is None else frame
    mx = fb.motors()[0][0]
    yf0, yf1 = fb.Y['frame']
    return frame.intersect(fb.ycyl(62.0, yf0, yf1, mx))


def coupon_frame_ring(dv: float):
    """The hip frame round one motor, the part next to the leg: the 61812's lead-in from the motor side, its seat
    (Ø78 + dv, 10 mm) and the lip (Ø73) it stops on. The nominal one is the frame's whole lug ring (Ø124) with the 10 M4
    lug holes and actual counterbores cut directly from the parent, plus the two
    Ø5 dowel holes. Its outer/lip face goes DOWN, as in build_leg.ROT['hip_frame'].
    The -0.1 / +0.1 variants are bearing-seat-only rings, not motor-mount specimens."""
    if dv == 0:
        mx = fb.motors()[0][0]
        return (coupon_frame_ring_parent().rotate((0, 0, 0), (1, 0, 0), -90)
                .translate((-mx, 0, fb.Y['frame'][1])))
    yf1 = fb.Y['frame'][1]
    yb0, yb1 = fb.Y['bearing']
    z0 = yb0 - 2.0
    h = yf1 - z0
    ring = fb.AC['bearing_od'] / 2 + 6.0
    s = zc(ring, 0, h)
    s = s.cut(zc(fb.AC['bearing_od'] / 2 + 0.3, -1, yb0 - z0))
    s = s.cut(zc(fb.AC['bearing_od'] / 2 + dv / 2, yb0 - z0 - 0.01, yb1 - z0))
    s = s.cut(zc(fb.AC['lip_d'] / 2, yb1 - z0 - 0.01, h + 1))
    return engrave(s, label(dv), 0, -(fb.AC['lip_d'] / 2 + 1.6), h, 3.0)


def coupon_hub_face(dv: float):
    """The upper link's hub against the machined adapter (D46): the Ø40.1 + dv spigot recess (3.3 deep), 8 x M5
    clearance and 2 x Ø5 dowel holes on PCD 50 at D46's angles. Printed outer face down, as the link."""
    t = 6.0
    s = zc(fb.UPPER_HUB_R, 0, t)
    s = s.cut(zc((D46_SPIGOT_RECESS + dv) / 2, t - 3.3, t + 1))
    for (x, y) in pts(50.0, D46_BOLTS_DEG):
        s = s.cut(zc(gmi.clear('M5') / 2, -1, t + 1, x, y))
    for (x, y) in pts(50.0, D46_DOWELS_DEG):
        s = s.cut(zc(2.5 + 0.02 + dv / 2, -1, t + 1, x, y))
    return engrave(s, label(dv), 0, 0, t - 3.3, 4)


def coupon_knee_eye(dv: float):
    """The upper link's knee eye: one DIN 179 12 x 18 x 20 sleeve pressed into Ø(18 - 0.04 + dv), 22 mm of boss."""
    s = zc(fb.UPPER_EYE_R, 0, 22.0).union(bx(-fb.UPPER_EYE_R, 0, -14, 14, 0, 22.0))
    s = s.cut(zc(fb.EYE_SLEEVE[0] / 2 - 0.02 + dv / 2, -1, 23))
    return engrave(s, label(dv), -13.0, 0, 22.0, 4)


def coupon_knee_boss(dv: float):
    """A lower link's knee boss: a 6201 seat (Ø32.04 + dv, 10 mm) on the Ø27 web, Ø46 outside."""
    bo = fb.KC['bearing_od']
    s = zc(fb.KC['hub_od'] / 2, 0, 12.0)
    s = s.cut(zc(bo / 2 + 0.02 + dv / 2, 2.0, 13)).cut(zc(fb.KC['shoulder_d'] / 2, -1, 3))
    return engrave(s.union(bx(fb.KC['hub_od'] / 2 - 3, fb.KC['hub_od'] / 2 + 12, -7, 7, 0, 6)), label(dv), fb.KC['hub_od'] / 2 + 5.5, 0, 6, 3.5)


def coupon_apex_eye(dv: float):
    """The front link's apex eye: a 61812 seat (Ø78.04 + dv, 10 mm) against the Ø72 web, Ø90 outside."""
    ao = fb.AC['bearing_od']
    s = zc(ao / 2 + 6.0, 0, 13.0)
    s = s.cut(zc(ao / 2 + 0.02 + dv / 2, 3.0, 14)).cut(zc(36.0, -1, 4))
    return engrave(s, label(dv), 0, -(ao / 2 + 3.0), 13.0, 3.0)


def coupon_hub_stub(dv: float):
    """The wheel link's hub: the Ø60 + dv journal for a 61812's inner race against the Ø64 shoulder, the DIN 471-60
    groove (Ø57 x 2.15) at the journal's end, the Ø48 bore. Printed shoulder down, as the wheel link."""
    y0, y1 = fb.Y['circlip']
    s = zc(32.0, 0, 4.0).union(zc(30.0 + dv / 2, 4.0, 4.0 + 13.0 + 3.0 + 3.0))
    top = 4.0 + 13.0 + 3.0 + 3.0
    g0 = top - 3.0 - (y1 - y0)                                                       # the groove 3 mm from the end (the hub's land)
    s = s.cut(zc(31.0, g0, g0 + (y1 - y0)).cut(zc(28.5, g0 - 1, g0 + (y1 - y0) + 1)))
    s = s.cut(zc(24.0, -1, top + 1))
    return engrave(s, label(dv), 0, -28.0, 4.0, 3.0)


# ----------------------------------------------------------------------------------- the list

FIXTURES = {   # name: (builder, material, qty, note)
    'dyno_lug_plate': (dyno_lug_plate, 'petg', 2, 'PETG, 6 walls, 60 % gyroid; on a 19 mm plywood board, 4 x M6 through bolts each (B1, B2)'),
    'dyno_hub': (dyno_hub, 'petg', 2, 'PETG, 100 %; 9 x M5 x 25 into the output (the leg\'s D46 screw), 3 pin sockets'),
    'dyno_spider': (dyno_spider, 'tpu95', 2, 'TPU 95A, 100 %; one spare'),
    'press_cage': (press_cage, 'petg', 1, 'PETG, 6 walls, 40 % gyroid; flat (B3, B4)'),
    'press_base': (press_base, 'petg', 1, 'PETG, 6 walls, 40 % gyroid (B3)'),
    'press_slider': (press_slider, 'petg', 1, 'PETG, 6 walls, 40 % gyroid (B3)'),
    'sleeve_block': (sleeve_block, 'pa6-cf', 1, 'PA6-CF, 100 %; a real stop post (Ø16 pin) in its blind hole and TPU sleeve (B3)'),
    'sleeve_anvil': (sleeve_anvil, 'pa6-cf', 1, 'PA6-CF, 100 %, face down (B3)'),
    'puller_m5': (lambda: puller('M5'), 'pa6-cf', 3, 'PA6-CF, 6 walls, 60 % gyroid, insert face up (B4: two to 3.5 kN, one for the head test)'),
    'bearing_disc': (bearing_disc, 'pa6-cf', 3, 'PA6-CF, 100 %, flat (B4: the link under an M5 head)'),
}
COUPONS = {'coupon_frame_ring': coupon_frame_ring, 'coupon_hub_face': coupon_hub_face, 'coupon_knee_eye': coupon_knee_eye,
           'coupon_knee_boss': coupon_knee_boss, 'coupon_apex_eye': coupon_apex_eye, 'coupon_hub_stub': coupon_hub_stub}


def parts() -> dict:
    out = {}
    for name, (fn, mat, qty, note) in FIXTURES.items():
        out[name] = (fn(), mat, qty, note)
    for name, fn in COUPONS.items():
        for dv in VARIANTS:
            tag = {-0.1: 'm01', 0.0: 'nom', 0.1: 'p01'}[dv]
            out[f'{name}_{tag}'] = (fn(dv), 'pa6-cf', 1, f'PA6-CF, 100 %, dried; the seat at {label(dv)} mm on the leg\'s')
    return out


def main():
    if '--render' in sys.argv:
        for f in render_setups():
            print(f.relative_to(R))
        return
    from cadagent.geometry import export_print_stl
    OUT.mkdir(parents=True, exist_ok=True)
    mats = json.loads((R / 'catalog/materials.json').read_text())
    plan, report = {}, {}
    for name, (shape, mat, qty, note) in parts().items():
        s = shape.val()
        cq.exporters.export(s, str(OUT / f'{name}.step'))
        rep = export_print_stl(s, OUT / f'{name}.stl')
        g = s.Volume() / 1000 * mats[mat]['density_g_cm3'] * (1.0 if '100 %' in note else 0.6)
        plan[name] = printplan.row(s, None, mat, qty, g, '100 %' in note, note)
        report[name] = {'valid': s.isValid(), 'solids': len(shape.solids().vals()), 'watertight': rep.get('watertight'),
                        'fits': plan[name]['fits'], 'grams': plan[name]['grams']}
    too_big = printplan.write(OUT / 'print-plan.json', plan, note='bench fixtures and fit coupons (task T4)')
    stack = cage_stack()
    (OUT / 'bench.json').write_text(json.dumps({'parts': report, 'too_big': too_big, 'variants_mm': list(VARIANTS), 'press_cage': stack,
                                                'd46_face': {'bolts_deg': D46_BOLTS_DEG, 'dowels_deg': D46_DOWELS_DEG, 'spigot_recess': D46_SPIGOT_RECESS}},
                                               indent=1) + '\n')
    bad = [n for n, r in report.items() if not (r['valid'] and r['solids'] == 1 and r['fits'] and r['watertight'] is not False)]
    tot = json.loads((OUT / 'print-plan.json').read_text())
    print(f"bench: {len(report)} parts, {tot['total_hours']} h, {tot['total_grams']} g; problems: {bad or 'none'}")
    print(f"  press cage: {stack}")
    for f in render_setups():
        print(f'  {f.relative_to(R)}')
    for n, r in report.items():
        print(f"  {n:24} {r['grams']:5d} g  valid {r['valid']}  solids {r['solids']}  fits {r['fits']}")


if __name__ == '__main__':
    main()
