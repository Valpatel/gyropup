"""The foam-ball turret's stand: the turret as a robot of its own (D66), on its own battery, or on the bench before
Gyropup can carry it.

D66 (2026-10-27): the turret carries its own Jetson (the compute plinth under its pan base) and takes one XT30 input,
12-54 V. On the stand that is one DeWalt FLEXVOLT DCB609 in 20 V mode (15-20.5 V): the pack slides into the stand's
back onto a 20 V MAX dock adapter fixed under the top plate, as onto a drill, and rests on the floor; its leads go
through the stand's 20 A MINI fuse (58 V type) and the rocker switch to an XT30 lead out of the top plate's rear notch
to the plinth's XT30 input. The bench supply (Mean Well LRS-350-24 and the XT60E-M inlet) is gone; the box bench
(cad/build_turret_box.py) keeps its own.

Turret frame (cad/turret.py): x forward, y left, z up, origin on the pan axis at the TM mounting face. The stand's top
is that face (z = 0); the stand is a printed PETG box under it:

  stand_box (PETG, printed upside down)  the top plate with the turret's TM pattern (4 x M5 inserts on 80 x 80,
                                          2 x Ø5 dowel holes, the Ø45 cable hole), four walls, corner bosses with M3
                                          inserts for the bottom; the front panel has the 24 V XT60E-M inlet, a rocker
                                          switch, a 5 x 20 mm fuse holder and a keyed mini-XLR socket for the hold-to-run pendant;
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
W, D, H = 200.0, 200.0, 150.0         # x (front-back) x y (left-right) x height (mm): the FLEXVOLT inside (D66)
WALL, TOP, BOT = 4.0, 6.0, 4.0
BOSS_R = 6.0


def _box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
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
         ('switch', -10.0, -40.0, ('keyed', 20.2, 2.2), 2.5),       # DC-rated round snap-in rocker (D42): Bulgin R13244AAAA,
                                                                     # Ø20.2, panel 3 mm at most; the backup Switch Components
                                                                     # RA1-1A-DC-2-B-1 the same with a 2.2 mm key notch, 2-3 mm
         ('fuse', 28.0, -40.0, ('d', 12.75, 12.13), WALL),          # Littelfuse 345 panel holder: Ø12.70-12.83, a flat at
                                                                     # 12.07-12.19
         ('pendant', 60.0, -40.0, ('d', 11.3, 10.3), 2.0)]          # Switchcraft TB3M mini-XLR panel socket: its 7/16-32 bushing
                                                                     # (Ø11.10, a flat 10.2 across) in a D hole, nut and washer;
                                                                     # keyed, so no audio plug (headphones) can close the loop


# D66: the stand's front panel has no inlet and no panel fuse any more (the pack is inside, its fuse is a 58 V MINI on
# its lead): the rocker switch and the pendant socket (PANEL stays whole: the box's pod panel shares its holes)
STAND_PANEL = [p for p in PANEL if p[0] in ('switch', 'pendant')]
# the pack (catalog/power_electronics.json dewalt-dcb609: 157 x 92 x 110 mm envelope, 1.57 kg) slides in along x from
# the back wall's opening onto the dock adapter (dewalt-20v-dock-adapter-12awg, 80 x 65 x 30, est) under the top plate
PACK = {'L': 157.0, 'W': 92.0, 'H': 110.0, 'mass_g': 1565.0}
DOCK = {'L': 80.0, 'W': 65.0, 'H': 30.0, 'mass_g': 60.0}
PACK_X0 = -W / 2 + 2.0                       # the pack's back face, 2 mm inside the back wall's opening
DOCK_X0 = -W / 2 + WALL + 0.5                # the dock adapter, just inside the back wall (the pack's latch at the opening)
# the terminal board stands on the +y wall (bosses with M3 inserts), clear of the pack
BOARD_ON_WALL = {'x': (-40.0, 30.0), 'z': (-H + 25.0, -H + 75.0), 'y': D / 2 - WALL - 8.0}


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
    # the XT30 lead to the plinth leaves through a notch in the top plate's rear edge (no TM cable hole: the plinth closes it)
    s = s.cut(_box(x0 - 1, x0 + WALL + 10.0, -8.0, 8.0, -TOP - 1, 0.1))
    # the pack's opening in the back wall, and the dock's cradle under the top plate (two side rails and a front stop;
    # the adapter is screwed up into the plate with 2 x M3 through its base, drilled to suit on arrival)
    s = s.cut(_box(x0 - 1, x0 + WALL + 1, -PACK['W'] / 2 - 2.0, PACK['W'] / 2 + 2.0, -H - 1, -H + 4.0 + PACK['H'] + 2.0))
    dx0 = DOCK_X0
    for sy in (-1, 1):
        s = s.union(_box(dx0 + 4.0, dx0 + DOCK['L'] + 1.5, sy * (DOCK['W'] / 2), sy * (DOCK['W'] / 2 + 3.0), -TOP - DOCK['H'] + 6.0, -TOP + 0.5))
    s = s.union(_box(dx0 + DOCK['L'], dx0 + DOCK['L'] + 3.0, -DOCK['W'] / 2 - 3.0, DOCK['W'] / 2 + 3.0, -TOP - 12.0, -TOP + 0.5))
    # the dock's two M3 inserts from below: the short 94459A130 (4.3 mm) in 5.3 mm pilots, 0.7 mm of plate over them (the
    # 5.7 mm 94459A140 cannot seat in the 6 mm plate; the 4 mm pilots took neither, #137)
    for dy in (-15.0, 15.0):
        s = s.cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, -TOP - 0.01, -TOP + 5.3, dx0 + DOCK['L'] / 2, dy))
    # the terminal board's bosses on the +y wall
    bx, bz, by = BOARD_ON_WALL['x'], BOARD_ON_WALL['z'], BOARD_ON_WALL['y']
    for x in (bx[0] + 2.0, bx[1] - 2.0):
        for z in (bz[0] + 2.0, bz[1] - 2.0):
            boss = cq.Workplane('XZ', origin=(0, D / 2 - WALL + 0.01, 0)).center(x, z).circle(4.0).extrude(D / 2 - WALL - by)
            s = s.union(boss)
    # the front panel's cutouts, the wall thinned from inside where a part wants a thin panel
    for name, y, z, cut, t in STAND_PANEL:
        if t < WALL:
            s = s.cut(_box(x1 - WALL - 1, x1 - t, y - 13.0, y + 13.0, z - 13.0, z + 13.0))
        if cut[0] == 'rect':
            s = s.cut(_box(x1 - WALL - 1, x1 + 1, y - cut[1] / 2, y + cut[1] / 2, z - cut[2] / 2, z + cut[2] / 2))
            if name == 'xt60':
                for sy in (-1.0, 1.0):                                                     # slots: 18..28 mm spacing, M2.5 or M3
                    for dy in (9.0, 14.0):
                        s = s.cut(_cyl_x(1.6, x1 - WALL - 1, x1 + 1, y + sy * dy, z))
                    ya, yb = sorted((y + sy * 9.0, y + sy * 14.0))
                    s = s.cut(_box(x1 - WALL - 1, x1 + 1, ya, yb, z - 1.6, z + 1.6))
        elif cut[0] == 'keyed':                                                            # a round hole with a key notch at the top
            s = s.cut(_cyl_x(cut[1] / 2, x1 - WALL - 1, x1 + 1, y, z))
            s = s.cut(_box(x1 - WALL - 1, x1 + 1, y - cut[2] / 2, y + cut[2] / 2, z, z + cut[1] / 2 + 1.0))
        elif cut[0] == 'd':
            hole = _cyl_x(cut[1] / 2, x1 - WALL - 1, x1 + 1, y, z).cut(_box(x1 - WALL - 2, x1 + 2, y - 10, y + 10, z + cut[2] - cut[1] / 2, z + 10))
            s = s.cut(hole)
        else:
            s = s.cut(_cyl_x(cut[1] / 2, x1 - WALL - 1, x1 + 1, y, z))
    s = s.cut(_box(x0 - 1, x0 + WALL + 1, -76.0, -64.0, -H + 18.0, -H + 24.0))      # USB-C for the USB-CAN adapter, beside the pack
    s = s.cut(_box(-12.0, 12.0, y0 - 1, y0 + WALL + 1, -26.0, -TOP - 4.0))          # -y wall: the DT12 harness notch
    return s




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
    for sy in (-1, 1):                                                                 # two ribs the pack slides on
        p = p.union(_box(PACK_X0 + 10.0, PACK_X0 + PACK['L'] - 5.0, sy * 25.0 - 3.0, sy * 25.0 + 3.0, -H - 0.01, -H + 4.0))
    return p


def bought():
    """Envelopes of what goes in or on the stand: {name: (shape, mass_g, note)}."""
    x1 = W / 2
    out = {}
    out['usb_can'] = (_box(-W / 2 + WALL, -W / 2 + WALL + 50, -80.0, -60.0, -H, -H + 12), 20.0,
                      'USB-CAN adapter (CANable 2.0 class), USB-C at the back wall; on the floor against the wall on a '
                      'VHB pad (it floated 10 mm up: cadagent connectivity, 2026-10-28)')
    bx, bz, by = BOARD_ON_WALL['x'], BOARD_ON_WALL['z'], BOARD_ON_WALL['y']
    out['terminal_board'] = (_box(bx[0], bx[1], by - 1.6, by, bz[0], bz[1]), 30.0,
                             '70 x 50 board on the +y wall: the pack\'s fuse and switch to the XT30 lead, the pendant loop to the DT12 plug')
    zt = -TOP - DOCK['H']
    out['dock'] = (_box(DOCK_X0, DOCK_X0 + DOCK['L'], -DOCK['W'] / 2, DOCK['W'] / 2, zt, -TOP), DOCK['mass_g'],
                   'DeWalt 20 V MAX dock adapter, 12 AWG leads (a FLEXVOLT runs in its 20 V mode in it)')
    out['pack'] = (_box(PACK_X0, PACK_X0 + PACK['L'], -PACK['W'] / 2, PACK['W'] / 2, -H + 4.0, -H + 4.0 + PACK['H']), PACK['mass_g'],
                   'DeWalt DCB609 FLEXVOLT 9 Ah in 20 V mode (envelope)')
    for name, y, z, cut, _t in STAND_PANEL:
        d = {'switch': (25.0, 24.0, 24.0), 'pendant': (24.0, 12.5, 12.5)}[name]
        out[f'panel_{name}'] = (_box(x1 - WALL - d[0], x1 + 3.0, y - d[1] / 2, y + d[1] / 2, z - d[2] / 2, z + d[2] / 2), 10.0,
                                {'switch': 'DC rocker switch, Ø20.2 snap-in, 10 A 28 VDC (Bulgin R13244AAAA)',
                                 'pendant': 'TB3M mini-XLR panel socket (pendant; keyed, no audio plug fits)'}[name])
    for k, (x, y) in enumerate(((-W / 2 + 22, -D / 2 + 22), (W / 2 - 22, -D / 2 + 22), (-W / 2 + 22, D / 2 - 22), (W / 2 - 22, D / 2 - 22))):
        out[f'foot_{k + 1}'] = (_cyl_z(5.6, -H - BOT - 4.1, -H - BOT + 1.0, x, y), 2.0, 'rubber bumper foot, 3M SJ5003 Ø11.2 x 5.1')
    return out


PARTS = {'stand_box': ('petg', 1, 'printed PETG upside down; 4 x M5 + 4 x M3 inserts for the bottom, 2 x M3 x 4.3 (94459A130) for the dock, 4 x M3 for the board', ((1, 0, 0), 180)),
         'stand_bottom': ('petg', 1, 'printed PETG flat; 4 x M3 x 8 into the corner bosses; 4 rubber feet; two ribs the pack slides on', None)}


def parts():
    return {'stand_box': stand_box(), 'stand_bottom': stand_bottom()}
