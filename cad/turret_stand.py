"""The foam-ball turret's bench stand: the turret on its own, before there is a robot to carry it (M4).

Turret frame (cad/turret.py): x forward, y left, z up, origin on the pan axis at the TM mounting face. The stand's top
is that face (z = 0); the stand is a printed PETG box under it:

  stand_box (PETG, printed upside down)  the top plate with the turret's TM pattern (4 x M5 inserts on 80 x 80,
                                          2 x Ø5 dowel holes, the Ø45 cable hole), four walls, corner bosses with M3
                                          inserts for the bottom; the front panel has the 24 V XT60E-M inlet, a rocker
                                          switch, a 5 x 20 mm fuse holder and a 3.5 mm jack for the hold-to-run pendant;
                                          the back has a slot for the USB-CAN adapter's USB-C; the -y wall a notch with
                                          a grommet for the turret's DT12 harness, which leaves the turret's plug and
                                          turns down outside the stand
  stand_bottom (PETG)                     bolts into the corner bosses; recesses for 4 rubber feet; two slotted tabs
                                          so the stand can be clamped to a bench (the turret slews 1.5 kg); four
                                          bosses with M3 inserts carry the terminal board, so the box drops over it

What is inside (bought, as envelopes): the USB-CAN adapter (the laptop talks to the turret's own MCU over CAN, as the
robot's Jetson will), a small terminal board that takes 24 V through the fuse and switch to the DT12 plug's power pins,
and the pendant's loop to the plug's safety-line pins: the turret will not spin its flywheels or feed a ball unless the
pendant's button is held (the safety line of docs/head-payload.md, on the bench).
"""
from __future__ import annotations

import math

import cadquery as cq

import gmi
import turret as tu

FAST = gmi.FAST
W, D, H = 180.0, 200.0, 100.0         # x (front-back) x y (left-right) x height (mm)
WALL, TOP, BOT = 4.0, 6.0, 4.0
BOSS_R = 6.0


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def _cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def _cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


# front panel (+x) items: (name, y, z, cutout, panel thickness there); cutout = ('rect', w, h), ('round', d) or
# ('d', d, across the flat). The holes are the makers' panel cutouts, not the parts' bezels (catalog/sourcing.json risk):
PANEL = [('xt60', -50.0, -40.0, ('rect', 16.6, 8.6), WALL),         # Amass XT60E-M panel plug (the supply's lead brings the
                                                                     # female, so no live pin is ever bare); 2 x M2.5, their
                                                                     # spacing not published: slotted 18..28 mm, M2.5 or M3
         ('switch', -10.0, -40.0, ('rect', 19.4, 13.0), 2.5),       # KCD1-class rocker (E-Switch RCA1913): 19.2-19.8 x 13.0
                                                                     # snap-in, panel 3 mm at most
         ('fuse', 28.0, -40.0, ('d', 12.75, 12.13), WALL),          # Littelfuse 345 panel holder: Ø12.70-12.83, a flat at
                                                                     # 12.07-12.19
         ('pendant', 60.0, -40.0, ('round', 6.35), 2.0)]            # Switchcraft 35PM2A 3.5 mm jack: Ø6.35 in a 2 mm panel


def stand_box():
    """Top plate, walls and corner bosses in one PETG part, printed upside down (on its top plate)."""
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    outer = _box(x0, x1, y0, y1, -H, 0.0)
    inner = _box(x0 + WALL, x1 - WALL, y0 + WALL, y1 - WALL, -H - 1, -TOP)
    s = outer.cut(inner).edges('|Z').fillet(6.0)
    for (x, y) in ((x0 + WALL + BOSS_R - 1, y0 + WALL + BOSS_R - 1), (x1 - WALL - BOSS_R + 1, y0 + WALL + BOSS_R - 1),
                   (x0 + WALL + BOSS_R - 1, y1 - WALL - BOSS_R + 1), (x1 - WALL - BOSS_R + 1, y1 - WALL - BOSS_R + 1)):
        s = s.union(_cyl_z(BOSS_R, -H, -TOP, x, y)).cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, -H - 1, -H + 8, x, y))
    # the turret's TM pattern: M5 inserts from above, dowel holes, the cable hole
    for (x, y) in tu.TM_BOLTS:
        s = s.union(_cyl_z(7.0, -TOP - 8.0, -TOP + 0.01, x, y))                       # insert bosses under the plate
        s = s.cut(_cyl_z(FAST['M5']['insert_pilot'] / 2, -TOP - 8.0, 0.1, x, y))
    for (x, y) in tu.TM_DOWELS:
        s = s.cut(_cyl_z(2.5 - 0.03, -TOP - 1, 0.1, x, y))
    s = s.cut(_cyl_z(tu.TM_HOLE / 2, -TOP - 1, 0.1))
    # the front panel's cutouts, the wall thinned from inside where a part wants a thin panel
    for name, y, z, cut, t in PANEL:
        if t < WALL:
            s = s.cut(_box(x1 - WALL - 1, x1 - t, y - 12.0, y + 12.0, z - 9.0, z + 9.0))
        if cut[0] == 'rect':
            s = s.cut(_box(x1 - WALL - 1, x1 + 1, y - cut[1] / 2, y + cut[1] / 2, z - cut[2] / 2, z + cut[2] / 2))
            if name == 'xt60':
                for sy in (-1.0, 1.0):                                                     # slots: 18..28 mm spacing, M2.5 or M3
                    for dy in (9.0, 14.0):
                        s = s.cut(_cyl_x(1.6, x1 - WALL - 1, x1 + 1, y + sy * dy, z))
                    ya, yb = sorted((y + sy * 9.0, y + sy * 14.0))
                    s = s.cut(_box(x1 - WALL - 1, x1 + 1, ya, yb, z - 1.6, z + 1.6))
        elif cut[0] == 'd':
            hole = _cyl_x(cut[1] / 2, x1 - WALL - 1, x1 + 1, y, z).cut(_box(x1 - WALL - 2, x1 + 2, y - 10, y + 10, z + cut[2] - cut[1] / 2, z + 10))
            s = s.cut(hole)
        else:
            s = s.cut(_cyl_x(cut[1] / 2, x1 - WALL - 1, x1 + 1, y, z))
    s = s.cut(_box(x0 - 1, x0 + WALL + 1, -6.0, 6.0, -H + 18.0, -H + 24.0))          # USB-C for the USB-CAN adapter
    s = s.cut(_box(-12.0, 12.0, y0 - 1, y0 + WALL + 1, -26.0, -TOP - 4.0))          # -y wall: the DT12 harness notch
    return s


# the terminal board's bosses stand on the bottom plate (a 70 x 50 perfboard, its corner holes drilled out to Ø3.2 at
# 66 x 46, 2 mm in from the edges); the box drops over it
BOARD_HOLES = ((-60.0, -23.0), (-60.0, 23.0), (6.0, -23.0), (6.0, 23.0))


def stand_bottom():
    """The bottom plate: 4 x M3 into the corner bosses, recesses for 4 rubber feet, two slotted clamp tabs."""
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    p = _box(x0, x1, y0, y1, -H - BOT, -H).edges('|Z').fillet(6.0)
    for s_ in (-1, 1):                                                                 # clamp tabs, left and right
        tab = _box(-30.0, 30.0, s_ * D / 2 - (0 if s_ > 0 else 20.0), s_ * D / 2 + (20.0 if s_ > 0 else 0), -H - BOT, -H)
        ya, yb = sorted((s_ * (D / 2 + 5.0), s_ * (D / 2 + 15.0)))
        p = p.union(tab).cut(_box(-12.0, 12.0, ya, yb, -H - BOT - 1, -H + 1))                  # a slot for a bench clamp
    for (x, y) in ((x0 + WALL + BOSS_R - 1, y0 + WALL + BOSS_R - 1), (x1 - WALL - BOSS_R + 1, y0 + WALL + BOSS_R - 1),
                   (x0 + WALL + BOSS_R - 1, y1 - WALL - BOSS_R + 1), (x1 - WALL - BOSS_R + 1, y1 - WALL - BOSS_R + 1)):
        p = p.cut(_cyl_z(FAST['M3']['clear'] / 2, -H - BOT - 1, -H + 1, x, y)).cut(_cyl_z(3.2, -H - BOT - 1, -H - BOT + 1.8, x, y))
    for (x, y) in ((x0 + 22, y0 + 22), (x1 - 22, y0 + 22), (x0 + 22, y1 - 22), (x1 - 22, y1 - 22)):
        p = p.cut(_cyl_z(6.6, -H - BOT - 1, -H - BOT + 1.0, x, y))                   # rubber feet (3M SJ5003 Ø11.2, 1 mm recess)
    for (x, y) in BOARD_HOLES:                                                         # the terminal board's bosses, M3 inserts
        p = p.union(_cyl_z(4.0, -H - 0.01, -H + 12.0, x, y)).cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, -H + 5.0, -H + 12.1, x, y))
    return p


def bought():
    """Envelopes of what goes in or on the stand: {name: (shape, mass_g, note)}."""
    x1 = W / 2
    out = {}
    out['usb_can'] = (_box(-W / 2 + WALL + 1, -W / 2 + WALL + 51, -10.0, 10.0, -H + BOT + 10, -H + BOT + 22), 20.0,
                      'USB-CAN adapter (CANable 2.0 class), USB-C at the back wall')
    out['terminal_board'] = (_box(-62.0, 8.0, -25.0, 25.0, -H + 12.0, -H + 13.6), 30.0,
                             '70 x 50 board: 24 V terminal block, fuse/switch wiring to the DT12 plug, the pendant loop')
    for name, y, z, cut, _t in PANEL:
        d = {'xt60': (18.0, 30.0, 11.0), 'switch': (25.0, 21.0, 15.0), 'fuse': (35.0, 16.0, 16.0), 'pendant': (14.0, 9.0, 9.0)}[name]
        out[f'panel_{name}'] = (_box(x1 - WALL - d[0], x1 + 3.0, y - d[1] / 2, y + d[1] / 2, z - d[2] / 2, z + d[2] / 2), 10.0,
                                {'xt60': 'Amass XT60E-M panel plug (24 V in)', 'switch': 'KCD1 rocker switch, 16 A',
                                 'fuse': '5 x 20 mm panel fuse holder + a DC-rated 5 A time-lag fuse', 'pendant': '3.5 mm panel jack (pendant)'}[name])
    for k, (x, y) in enumerate(((-W / 2 + 22, -D / 2 + 22), (W / 2 - 22, -D / 2 + 22), (-W / 2 + 22, D / 2 - 22), (W / 2 - 22, D / 2 - 22))):
        out[f'foot_{k + 1}'] = (_cyl_z(5.6, -H - BOT - 4.1, -H - BOT + 1.0, x, y), 2.0, 'rubber bumper foot, 3M SJ5003 Ø11.2 x 5.1')
    return out


PARTS = {'stand_box': ('petg', 1, 'printed PETG upside down; 4 x M5 + 4 x M3 inserts', ((1, 0, 0), 180)),
         'stand_bottom': ('petg', 1, 'printed PETG flat; 4 x M3 x 8 into the corner bosses; 4 rubber feet; 4 x M3 inserts for the board', None)}


def parts():
    return {'stand_box': stand_box(), 'stand_bottom': stand_bottom()}
