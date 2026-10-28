"""The body's P3 shell (milestone M5, B6; D61): the printed walls round the open frame, the bought parts they carry, and
the checks that the shell keeps fingers out and plugs in. Robot frame (mm), see cad/body_params.py.

    import body_shell as bs3
    parts = bs3.shell_parts()          # {name: body_frame.Part} at stage P3 (read by cad/build_body.py)

What it is (docs/body-safety.md, docs/body-thermal.md):
  - Side walls: 2 mm PETG with 1.6 mm ribs inside, 0.6 mm outside the tray's and deck's lips (|y| 127.6..129.6), from
    just under the tray's lip to the deck's top (z 77.7..216). The P1S bed is 256 mm, so each side is two halves
    joined at x = -8 by a splice tab with two M3 screws and nuts. Each half screws into its corner post (M3 x 16 into
    heat-set inserts in the post's side). Nothing of the legs comes above z +31 (the upper links' sweep), so the walls
    keep 46 mm from every moving part.
  - The rear halves carry B7's louvres (14 slots 4 x 46 mm a side: ISO 13857 admits no finger at 4 mm), the body's
    air inlet beside the cooler's fins (the fan blows up and out through the deck); the left rear one the J501's port hatch (its window from the mated plugs, cadagent.connectors);
    the right front one the service door over the power plate; the front halves the ear-pod brackets (PA6-CF, through
    the wall with M5 bolts and nyloc nuts; the SSC1's foot on a 5/16-18 nut; the pod's top at z 193, under the lidar's
    -15 deg beam). The left front half has a vent over the J501's converter.
  - Front face: the eyes alone (a window for the DualEye board). Below the tray, an apron (|y| <= 58: 25 mm inside
    the knee eyes' sweep at |y| >= 83) carries the front D435 low, its lens in a window, on a PA6-CF cradle.
  - Rear face: the rear D435 the same way; four RP-SMA bulkheads (D-flat holes); between the right rear post and the
    turret's harness drop, the main switch's 16 mm button, the radio-stop jack (a mini-XLR 4-pin) and the radio
    receiver's bay, printed with the face (D65: no charge port; the packs charge on DeWalt's chargers).
  - The battery bay is cad/body_battery.py's (D65), on the robot from P1.
  - The J501 fan's duct (B7): from the turret plate's opening down to 2 mm over the fan's frame. The fan blows up
    (j501-agx 94da39d): the duct carries its exhaust out through the deck's cells, so it never spills into the body and
    comes back round through the fins.
"""
from __future__ import annotations

import functools
import math

import cadquery as cq

import body_frame as bf
import body_params as bp
import body_sheet as bs

WALL_T = 2.0
RIB_T, RIB_D = 1.6, 3.5                   # 3.5 deep: clear of the J501's plug zones (to |y| 123.5)
FACE_RIB_D = 3.0                          # the faces' ribs: clear of the lidar box (from x -157)
YI = bp.BODY_HALF_Y + 0.6                 # side walls' inner face
YO = YI + WALL_T
XI = bp.BODY_X[1] + 0.6                   # front and rear faces' inner face
XO = XI + WALL_T
ZB = bp.z_tray_top() - bp.TRAY_LIP - 1.0  # the walls' lower edge, 1 mm under the tray's lips
ZT = bp.TOP
FACE_HALF_W = 124.0                       # the faces 248 wide (the P1S prints 250); the side walls' returns cover the corners
SPLIT_X = -8.0                            # clear of the J501 hatch (to x -10.3) and the ear bracket's bolts (x 0)
APRON = {'z0': 35.0, 'half_y': 58.0}      # below the tray: 25 mm inside the knee eyes (|y| >= 83, hazard 1)
RIBS_Z = (112.0, 140.0, 194.8)            # horizontal ribs: clear of the tray's lip (to 93.7) and under the deck's (from 196)
POST_Z_SIDE = (125.0, 185.0)              # the walls' screws into the posts' sides
POST_Z_FACE = (115.0, 175.0)              # the faces' screws into the posts' ends
SPLICE_Z, SPLICE_SCREWS_Z = (150.0, 190.0), (160.0, 180.0)   # the side walls' splice tab, above the J501 hatch
BOSS_D, SCREW_D = 10.0, 3.4
PAD_D = 3.5                               # the nut pads inside the walls: an M3 nut (2.4) in a 2.5 mm pocket
LOUVRE = {'n': 14, 'w': 4.0, 'h': 46.0, 'pitch': 7.0, 'x0': -112.0, 'z0': 148.0}    # B7: 2,576 mm2 a side
DDR_VENT = {'n': 6, 'w': 4.0, 'h': 46.0, 'pitch': 7.0, 'x0': 58.0, 'z0': 148.0}     # over the TRACO converter (right front, D65)
DOOR_SIDE = 'l'                           # D65: the converter stands at the plate's right edge, so the door moved to the left
DOOR = (70.0, 125.0, 98.0, 192.0)         # the left front half's service door (x0, x1, z0, z1): in front of the ear pod, its
                                          # screws clear of the corner post's (to x 125: at 148 it took the post's two screws away)
EAR = {'x': (-6.0, 55.0), 'top': 193.0, 'pod': (61.0, 50.8, 66.0), 'foot': 28.0,
       'shelf_z': (115.0, 127.0), 'plate_z': (85.0, 127.0), 'plate_t': 6.0, 'bolts_z': (100.0, 120.0)}
EYES = {'y': 0.0, 'z': 182.0, 'window': (46.0, 20.0, 4.0), 'board': (51.0, 20.0, 7.0)}
D435 = {'size': (25.0, 90.0, 25.0), 'z': (40.0, 65.0), 'window': (92.0, 27.0, 3.0), 'back_m3': 45.0}
RP_SMA = {'d': 6.5, 'flat': 5.8, 'at': [(-40.0, 150.0), (-15.0, 150.0), (-40.0, 180.0), (-15.0, 180.0)], 'depth': 12.0}
REAR_COLUMN_Y = -86.0                     # between the right rear post (|y| >= 98) and the turret's harness drop (y >= -72)
BUTTON = {'d': 16.2, 'y': -88.0, 'z': 104.0, 'depth': 30.0}
JACK = {'d': 11.3, 'y': REAR_COLUMN_Y, 'z': 124.0, 'depth': 22.0, 'part': 'Switchcraft TB4M (mini-XLR 4-pin, 7/16-32 bushing)'}
RECEIVER_BAY = {'x': 30.0, 'y': 22.0, 'z': (150.0, 194.0)}


def box(x0, x1, y0, y1, z0, z1):
    return bf.box(x0, x1, y0, y1, z0, z1)


def _v(s):
    return s.val() if hasattr(s, 'val') else s


def _slot_y(x, z, w, h, y0, y1, r=None):
    """A slot through a side wall (along y), w wide in x and h tall in z, its corners rounded."""
    r = min(r or w / 2 - 0.01, w / 2 - 0.01, h / 2 - 0.01)
    return (cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).rect(w, h).extrude(y1 - y0)
            .edges('|Y').fillet(r))


def _slot_x(y, z, w, h, x0, x1, r=None):
    r = min(r or w / 2 - 0.01, w / 2 - 0.01, h / 2 - 0.01)
    return (cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).rect(w, h).extrude(x1 - x0).edges('|X').fillet(r))


def _hole_y(x, z, d, y0, y1):
    return bf.cyl_y(d / 2, y0, y1, x, z)


def _hole_x(y, z, d, x0, x1):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(d / 2).extrude(x1 - x0)


# ------------------------------------------------------------------------------------------- the J501's port hatch

@functools.lru_cache(maxsize=1)
def j501_ports():
    """The J501's rear-edge ports a person plugs from outside (HDMI, USB-A, USB-C), with their mate specs and the
    panel frame on the left wall: u along the PCB's x (robot x - J501_AT x), v up from the PCB's underside, w out
    along +y from the PCB's y = 0 (the j501-agx project's own convention, cad/ports.py)."""
    from cadagent.connectors import PanelFrame
    j = bp.j501()
    st = bp.j501_stack()
    x0, y0 = bp.J501_AT
    frame = PanelFrame((x0, y0, st['pcb_bottom']), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    wall_w = (YI - y0, YO - y0)
    ports = {n: j['ports']['rear'][n]['mate'] for n in ('hdmi', 'usb_a', 'usb_c') if 'mate' in j['ports']['rear'][n]}
    return ports, frame, wall_w


@functools.lru_cache(maxsize=1)
def hatch_window():
    """The hatch's opening (robot x0, x1, z0, z1): the union of each port's window from its mated plug (the passing plug
    sections and the receptacle face, plus the mate's clearance), grown 3 mm for fingers and the cable's bend."""
    from cadagent.connectors import window
    ports, frame, wall_w = j501_ports()
    st = bp.j501_stack()
    x0 = bp.J501_AT[0]
    wins = {n: window(m, wall_w) for n, m in ports.items()}
    us = [w[0] for w in wins.values()] + [w[2] for w in wins.values()]
    vs = [w[1] for w in wins.values()] + [w[3] for w in wins.values()]
    g = 3.0
    return (x0 + min(us) - g, x0 + max(us) + g, st['pcb_bottom'] + min(vs) - g, st['pcb_bottom'] + max(vs) + g), wins


# ------------------------------------------------------------------------------------------- side walls

def _wall_half(side, half):
    """One side wall half (robot frame), with its ribs, post bosses and splice, before its openings."""
    sy = 1.0 if side == 'l' else -1.0
    xa, xb = ((SPLIT_X, XO) if half == 'front' else (-XO, SPLIT_X))
    ya, yb = sorted((sy * YI, sy * YO))
    s = box(xa, xb, ya, yb, ZB, ZT)
    ret = (XI, XO) if half == 'front' else (-XO, -XI)               # the return over the face's edge at the corner
    s = s.union(box(ret[0], ret[1], *sorted((sy * (FACE_HALF_W + 0.2), sy * YI)), ZB, ZT))
    ri, ro = sorted((sy * (YI - RIB_D), sy * YI))
    ra, rb = max(xa, -XI + 0.5) + 0.5, min(xb, XI - 0.5) - 0.5    # inside the faces
    for z in RIBS_Z:                                         # horizontal ribs inside
        s = s.union(box(ra, rb, ri, ro, z - RIB_T / 2, z + RIB_T / 2))
    ends = (ra + RIB_T / 2,) if half == 'rear' else (rb - RIB_T / 2,)     # the splice tab is the split's rib
    for x in ends:
        s = s.union(box(x - RIB_T / 2, x + RIB_T / 2, ri, ro, 95.0, 194.0))
    px = 142.0 if half == 'front' else -142.0                # the corner post's centre
    post_face = bp.POST_W / 2 + abs(bp.POSTS[0][1])          # |y| of the posts' outer faces
    for z in POST_Z_SIDE:
        s = s.union(bf.cyl_y(BOSS_D / 2, *sorted((sy * (post_face + 0.2), sy * YI)), px, z))
        s = s.cut(_hole_y(px, z, SCREW_D, *sorted((sy * (post_face - 1), sy * (YO + 1)))))
    if half == 'rear':                                       # the splice tab reaches into the front half
        t0, t1 = sorted((sy * (YI - 5.0), sy * YI))
        tab = box(SPLIT_X - 2.0, SPLIT_X + 14.0, t0, t1, *SPLICE_Z)               # above the J501 hatch
        for z in SPLICE_SCREWS_Z:
            tab = tab.cut(_hole_y(SPLIT_X + 7.0, z, SCREW_D, t0 - 1, t1 + 1))
            tab = tab.cut(bf.hexagon_y(6.4, *sorted((sy * (YI - PAD_D - 0.1), sy * (YI - 1.0))), SPLIT_X + 7.0, z))   # M3 nut, held
        s = s.union(tab)
    else:
        for z in SPLICE_SCREWS_Z:
            s = s.cut(_hole_y(SPLIT_X + 7.0, z, SCREW_D, *sorted((sy * (YI - 1), sy * (YO + 1)))))
    return s


def side_wall(side, half):
    """A finished side wall half: the louvres (rear halves), the port hatch (left rear), the door (right front), the
    ear bracket's bolt holes (front halves), the DDR-120C vent (left front)."""
    sy = 1.0 if side == 'l' else -1.0
    s = _wall_half(side, half)
    y0, y1 = sorted((sy * (YI - RIB_D - 1), sy * (YO + 1)))
    cut = None

    def add(c):
        nonlocal cut
        cut = c if cut is None else cut.union(c)
    if half == 'rear':
        L = LOUVRE
        for k in range(L['n']):
            add(_slot_y(L['x0'] + k * L['pitch'], L['z0'] + L['h'] / 2, L['w'], L['h'], y0, y1))
        if side == 'l':
            hx0, hx1, hz0, hz1 = hatch_window()[0]
            add(box(hx0, hx1, y0, y1, hz0, hz1).edges('|Y').fillet(2.0))
    else:
        if side == DOOR_SIDE:
            x0, x1, z0, z1 = DOOR
            add(box(x0, x1, y0, y1, z0, z1).edges('|Y').fillet(3.0))
        else:
            V = DDR_VENT
            for k in range(V['n']):
                add(_slot_y(V['x0'] + k * V['pitch'], V['z0'] + V['h'] / 2, V['w'], V['h'], y0, y1))
        for x in (EAR['x'][0] + 10.0, EAR['x'][1] - 10.0):
            for z in EAR['bolts_z']:
                add(_hole_y(x, z, 5.5, y0, y1))
    if cut is not None:
        s = s.cut(cut)
    if half == 'rear' and side == 'l':                       # a rim round the hatch for its two screws' nuts
        for x, z in hatch_screws():
            rim = box(x - 5, x + 5, *sorted((sy * (YI - PAD_D), sy * YI)), z - 5, z + 5)
            rim = rim.cut(_hole_y(x, z, SCREW_D, *sorted((sy * (YI - 6), sy * (YO + 1)))))
            rim = rim.cut(bf.hexagon_y(6.4, *sorted((sy * (YI - PAD_D - 0.1), sy * (YI - 1.0))), x, z))
            s = s.union(rim)
    if half == 'front' and side == DOOR_SIDE:                # the door's four screws: nut pads round the opening
        x0, x1, z0, z1 = DOOR
        for x, z in ((x0 - 6, z0 + 12), (x0 - 6, z1 - 12), (x1 + 6, z0 + 12), (x1 + 6, z1 - 12)):
            pad = box(x - 5, x + 5, *sorted((sy * (YI - PAD_D), sy * YI)), z - 5, z + 5)
            pad = pad.cut(_hole_y(x, z, SCREW_D, *sorted((sy * (YI - 6), sy * (YO + 1)))))
            pad = pad.cut(bf.hexagon_y(6.4, *sorted((sy * (YI - PAD_D - 0.1), sy * (YI - 1.0))), x, z))
            s = s.union(pad)
    for x, z in screw_holes_through(side, half):                # the door's and hatch's screws through the wall itself
        s = s.cut(_hole_y(x, z, SCREW_D, *sorted((sy * (YI - 1), sy * (YO + 1)))))
    return s


def door_screws():
    x0, x1, z0, z1 = DOOR
    return [(x0 - 6, z0 + 12), (x0 - 6, z1 - 12), (x1 + 6, z0 + 12), (x1 + 6, z1 - 12)]


def screw_holes_through(side, half):
    if side == DOOR_SIDE and half == 'front':
        return door_screws()
    if side == 'l' and half == 'rear':
        return hatch_screws()
    return []


def door():
    """The right side's service door: a 2 mm PETG plate 8 mm over the opening all round, four M3 x 16 into the wall's
    nut pads, its edges rounded 2 mm (hazard table)."""
    x0, x1, z0, z1 = DOOR
    sy = 1.0 if DOOR_SIDE == 'l' else -1.0
    d = box(x0 - 11, x1 + 11, *sorted((sy * (YO + WALL_T), sy * YO)), z0 - 8, z1 + 8).edges('|Y').fillet(4.0)
    for x, z in ((x0 - 6, z0 + 12), (x0 - 6, z1 - 12), (x1 + 6, z0 + 12), (x1 + 6, z1 - 12)):
        d = d.cut(_hole_y(x, z, SCREW_D, *sorted((sy * (YO + WALL_T + 1), sy * (YO - 1)))))
    return d


def hatch():
    """The J501 port hatch's cover (left rear): 8 mm over the opening, two M3 x 16 into the wall's nut pads."""
    hx0, hx1, hz0, hz1 = hatch_window()[0]
    h = box(hx0 - 11, min(hx1 + 3, SPLIT_X - 1.0), YO, YO + WALL_T, hz0 - 12, hz1 + 2).edges('|Y').fillet(3.0)
    for x, z in hatch_screws():
        h = h.cut(_hole_y(x, z, SCREW_D, YO - 1, YO + WALL_T + 1))
    return h


def hatch_screws():
    """The hatch cover's two screws: left of the window, and under its right end (the wall's split is just right of it)."""
    hx0, hx1, hz0, hz1 = hatch_window()[0]
    return [(hx0 - 6.0, (hz0 + hz1) / 2), (hx1 - 8.0, hz0 - 7.0)]


def ear_bracket(side):
    """The SSC1 pod's bracket (PA6-CF): a plate on the wall's outside, four M5 bolts through the wall with nyloc nuts
    inside, and a shelf the pod's 28 mm foot stands on (its 5/16-18 bolt down into a nut held in the shelf). The pod's
    top is at z 193: under the lidar's lowest beam (sim/robot_v2.py reports the margin)."""
    sy = 1.0 if side == 'l' else -1.0
    E = EAR
    t = E['plate_t']
    pa, pb = sorted((sy * YO, sy * (YO + t)))
    plate = box(E['x'][0], E['x'][1], pa, pb, *E['plate_z'])
    cx = (E['x'][0] + E['x'][1]) / 2
    foot_y = YO + E['pod'][1] / 2
    sa, sb = sorted((sy * YO, sy * (foot_y + E['foot'] / 2 + 2.0)))
    shelf = box(cx - E['foot'] / 2 - 2, cx + E['foot'] / 2 + 2, sa, sb, *E['shelf_z'])
    gus = box(cx - 3, cx + 3, sa, sb, E['plate_z'][0] + 10, E['shelf_z'][0])        # a web under the shelf
    s = plate.union(shelf).union(gus)
    for x in (E['x'][0] + 10.0, E['x'][1] - 10.0):
        for z in E['bolts_z']:
            s = s.cut(_hole_y(x, z, 5.5, pa - 1, pb + 1))
    fy = sy * foot_y
    s = s.cut(bf.cyl_z(8.1 / 2 + 0.1, E['shelf_z'][0] - 1, E['shelf_z'][1] + 1, cx, fy))           # the 5/16-18 bolt
    s = s.cut(bf.hexagon_z(12.7 + 0.3, E['shelf_z'][0] - 1, E['shelf_z'][0] + 7.0, cx, fy))          # its nut from below
    return s


def ear_pod(side):
    """The SSC1 pod's envelope on its bracket (for the checks and pictures)."""
    sy = 1.0 if side == 'l' else -1.0
    px, py, pz = EAR['pod']
    ya, yb = sorted((sy * YO, sy * (YO + py)))
    return box(EAR['x'][0], EAR['x'][1], ya, yb, EAR['top'] - pz, EAR['top'])


# ------------------------------------------------------------------------------------------- front and rear faces

def _face(front):
    """A face (front or rear) with its apron below the tray, its ribs and post bosses."""
    sx = 1.0 if front else -1.0
    xa, xb = sorted((sx * XI, sx * XO))
    W = FACE_HALF_W
    s = box(xa, xb, -W, W, ZB, ZT)
    s = s.union(box(xa, xb, -APRON['half_y'], APRON['half_y'], APRON['z0'], ZB + 1.0))
    ra, rb = sorted((sx * (XI - FACE_RIB_D), sx * XI))
    for z in RIBS_Z:
        s = s.union(box(ra, rb, -W + 8, W - 8, z - RIB_T / 2, z + RIB_T / 2))
    if not front:                                            # the rear column (button, jack, bezel, bay): no rib behind it
        s = s.cut(box(ra + 0.01, rb + 0.01, REAR_COLUMN_Y - 14, REAR_COLUMN_Y + 14, 95.0, 196.0))
    post_end = abs(bp.POSTS[0][0]) + bp.POST_W / 2
    for y in (bp.POSTS[0][1], -bp.POSTS[0][1]):
        for z in POST_Z_FACE:
            s = s.union(cq.Workplane('YZ', origin=(min(sx * (post_end + 0.2), sx * XI), 0, 0)).center(y, z).circle(BOSS_D / 2)
                        .extrude(abs(XI - post_end - 0.2)))
            s = s.cut(_hole_x(y, z, SCREW_D, min(sx * (post_end - 1), sx * (XO + 1)), max(sx * (post_end - 1), sx * (XO + 1))))
    # the D435's window in the apron, and its cradle's two feet's screws (M3 x 8 from outside into their inserts)
    wy, wz, wr = D435['window']
    zc = sum(D435['z']) / 2
    s = s.cut(_slot_x(0.0, zc, wy, wz, xa - 1, xb + 1, wr))
    for y, z in cradle_screws():
        s = s.cut(_hole_x(y, z, SCREW_D, xa - 1, xb + 1))
    if front:                                                # the eyes' clip: two bosses with M3 inserts beside the window
        for y, z in eyes_clip_screws():
            s = s.union(cq.Workplane('YZ', origin=(XI - EYES['board'][2], 0, 0)).center(y, z).circle(4.0).extrude(EYES['board'][2] + 0.01))
            s = s.cut(cq.Workplane('YZ', origin=(XI - EYES['board'][2] - 0.1, 0, 0)).center(y, z).circle(2.0).extrude(6.0))
    return s


def cradle_screws():
    """The D435 cradle's two feet's screws through the apron (y, z): at the feet's centres."""
    W = D435['size'][1]
    z0 = D435['z'][0]
    return [(y, z0 + 2.0) for y in (-W / 2 - 4, W / 2 + 4)]


def eyes_clip_screws():
    """The eyes' clip's two screws (y, z): beside the board, into bosses on the front face's inside."""
    bw = EYES['board'][0]
    return [(EYES['y'] + s * (bw / 2 + 6.0), EYES['z']) for s in (-1, 1)]


def eyes_clip():
    """A 2 mm PETG plate behind the DualEye board that holds it against the front face's window: two M3 x 6 into the
    face's bosses (their faces level with the board's back)."""
    bw, bh, bt = EYES['board']
    x1 = XI - bt
    c = box(x1 - 2.0, x1, EYES['y'] - bw / 2 - 11.0, EYES['y'] + bw / 2 + 11.0, EYES['z'] - bh / 2 - 2, EYES['z'] + bh / 2 + 2)
    for y, z in eyes_clip_screws():
        c = c.cut(_hole_x(y, z, SCREW_D, x1 - 3, x1 + 1))
    return c


def front_face():
    s = _face(True)
    ww, wh, wr = EYES['window']
    s = s.cut(_slot_x(EYES['y'], EYES['z'], ww, wh, XI - 1, XO + 1, wr))
    return s


def rear_face():
    s = _face(False)
    for (y, z) in RP_SMA['at']:                              # D-flat holes: the bulkhead's flat keys it
        h = _hole_x(y, z, RP_SMA['d'], -XO - 1, -XI + 1).intersect(box(-XO - 2, -XI + 2, y - 4, y + 4, z - 4, z - RP_SMA['d'] / 2 + RP_SMA['flat']))
        s = s.cut(h)
    s = s.cut(_hole_x(BUTTON['y'], BUTTON['z'], BUTTON['d'], -XO - 1, -XI + 1))
    s = s.cut(_hole_x(JACK['y'], JACK['z'], JACK['d'], -XO - 1, -XI + 1))
    return s.union(receiver_bay())                           # the receiver's bay printed with the face (it rises from the face)


def receiver_bay():
    """The radio stop receiver's bay (D37): a printed box on the rear face's inside for the ER3C-i and the Pololu RC
    switch, with a slot for the antenna's lead."""
    R_ = RECEIVER_BAY
    y = REAR_COLUMN_Y
    b = box(-XI, -XI + R_['x'], y - R_['y'] / 2, y + R_['y'] / 2, *R_['z'])
    return b.cut(box(-XI + 1.6, -XI + R_['x'] - 1.6, y - R_['y'] / 2 + 1.6, y + R_['y'] / 2 - 1.6, R_['z'][0] + 1.6, R_['z'][1] + 1))


def d435(front):
    """The D435's envelope behind its apron window, its glass flush with the face's outside."""
    sx = 1.0 if front else -1.0
    L, W, H = D435['size']
    xa, xb = sorted((sx * XO, sx * (XO - L)))
    return box(xa, xb, -W / 2, W / 2, *D435['z'])


def d435_cradle(front):
    """The D435's cradle (PA6-CF): a plate behind the camera on its two back M3 holes (45 mm apart) with two feet to
    the apron's inside, so the camera's glass sits in the window."""
    sx = 1.0 if front else -1.0
    L, W, H = D435['size']
    xb = sx * (XO - L)                                       # the camera's back face
    pa, pb = sorted((xb, xb - sx * 4.0))
    z0, z1 = D435['z']
    plate = box(pa, pb, -W / 2 - 8, W / 2 + 8, z0 - 2, z1 + 2)
    for y in (-W / 2 - 4, W / 2 + 4):                         # feet forward to the apron
        fa, fb = sorted((pb if sx > 0 else pa, sx * XI))
        plate = plate.union(box(fa, fb, y - 4, y + 4, z0 - 2, z0 + 6))
    for y in (-D435['back_m3'] / 2, D435['back_m3'] / 2):
        plate = plate.cut(_hole_x(y, (z0 + z1) / 2, SCREW_D, min(pa, pb) - 1, max(pa, pb) + 1))
    for y, z in cradle_screws():                              # M3 inserts in the feet's ends, from the apron
        plate = plate.cut(_hole_x(y, z, 4.0, *sorted((sx * XI, sx * (XI - 7.5)))))
    return plate


def eyes_board():
    """The DualEye board behind its window (its two round displays face out)."""
    bw, bh, bt = EYES['board']
    return box(XI - bt, XI, EYES['y'] - bw / 2, EYES['y'] + bw / 2, EYES['z'] - bh / 2, EYES['z'] + bh / 2)


# ------------------------------------------------------------------------------------------- the fan duct

DUCT_TAB_T = 3.0                              # an M3 x 6 then ends 0.2 mm under the deck
DUCT_TAB_ANGLES = (90.0, 210.0, 330.0)        # clear of the plate's nuts, the riser's screws and the plate's opening


def duct_tabs():
    """The fan duct's three screws (robot x, y): 5 mm outside its sleeve, under solid turret plate."""
    fx, fy = bp.j501_stack()['fan_xy']
    r = bf.INTAKE_R + 1.0 + 1.6 + 5.0
    return [(fx + r * math.cos(math.radians(a)), fy + r * math.sin(math.radians(a))) for a in DUCT_TAB_ANGLES]


def fan_duct():
    """The J501 fan's duct (PETG, B7): a sleeve from the turret plate's opening down to 2 mm over the fan's frame,
    round the field of the deck's cells. The fan blows up: the duct takes its exhaust straight out through the deck, so
    it does not spill into the body and come back through the fins (the J501 box re-breathed its exhaust, +3.5 K,
    without its skirt)."""
    st = bp.j501_stack()
    fx, fy = st['fan_xy']
    zp = bp.TOP - bp.STOCK[bp.DECK]['t'] - bp.STOCK[bf.TURRET_PLATE['stock']]['t']       # the plate's underside
    z0 = st['cooler_top'] + bp.j501()['cooler_clear_top']                                 # 2 mm over the fan
    r_in = bf.INTAKE_R + 1.0
    s = bf.cyl_z(r_in + 1.6, z0, zp, fx, fy)
    for x, y in duct_tabs():                                 # three tabs at the top, screwed up into the plate's tapped holes
        a = math.atan2(y - fy, x - fx)
        tab = bf.cyl_z(5.0, zp - DUCT_TAB_T, zp, x, y).union(
            bf.box(-0.1, 5.5, -5.0, 5.0, zp - DUCT_TAB_T, zp).rotate((0, 0, 0), (0, 0, 1), math.degrees(a)).translate(
                (fx + (r_in + 0.5) * math.cos(a), fy + (r_in + 0.5) * math.sin(a), 0)))
        s = s.union(tab.cut(bf.cyl_z(1.7, zp - DUCT_TAB_T - 1, zp + 1, x, y)))
    s = s.cut(bf.cyl_z(r_in, z0 - 1, zp + 1, fx, fy))
    for x, y in bf.turret_plate_end_holes():                 # clear of the plate's PEM nuts' bodies
        s = s.cut(bf.cyl_z(7.0, z0 - 1, zp + 1, x, y))
    for a, b in bf.RISER_FEET:                                # clear of the riser's screws' heads under the plate
        t = bp.tm()
        s = s.cut(bf.cyl_z(9.0, zp - 8.0, zp + 1, t['pan_x'] + a, b))
    return s


# ------------------------------------------------------------------------------------------- the parts

P3 = 'P3'


def shell_parts() -> dict:
    """Every P3 part as body_frame.Part (robot frame): printed PETG and PA6-CF, SendCutSend sheet, bought envelopes."""
    Part = bf.Part
    out = {}
    pet, pa6 = (0.80, 0.82, 0.86), (0.22, 0.24, 0.27)

    def pr(n, shape, mat, colour, note, rot=None, kind='printed'):
        out[n] = Part(n, kind, shape, 1, material=mat, colour=colour, note=note, print_rotation=rot, stage=P3)
    for side in ('l', 'r'):
        for half in ('front', 'rear'):
            pr(f'shell_side_{side}_{half}', side_wall(side, half), 'petg', pet,
               'PETG, 2 mm with 1.6 mm ribs; printed on its outer face', ((1, 0, 0), 90 if side == 'r' else -90))
        pr(f'ear_bracket_{side}', ear_bracket(side), 'pa6-cf', pa6, 'PA6-CF; four M5 x 14 through the wall, nyloc nuts inside')
    pr('shell_front', front_face(), 'petg', pet, 'PETG, 2 mm with ribs; printed on its outer face', ((0, 1, 0), -90))
    pr('shell_rear', rear_face(), 'petg', pet, 'PETG, 2 mm with ribs, the receiver\'s bay with it; printed on its outer face', ((0, 1, 0), 90))
    pr('shell_door', door(), 'petg', pet, 'PETG; four M3 x 16 into the wall\'s nuts', ((1, 0, 0), 90))
    pr('shell_hatch', hatch(), 'petg', pet, 'PETG; two M3 x 16 into the wall\'s nuts', ((1, 0, 0), -90))
    for front in (True, False):
        pr(f'd435_cradle_{"front" if front else "rear"}', d435_cradle(front), 'pa6-cf', pa6, 'PA6-CF; the D435 on its two back M3')
    pr('fan_duct', fan_duct(), 'petg', pet, 'PETG: the fan\'s exhaust goes only out through the deck; three M3 x 5 up into the turret plate')
    pr('eyes_clip', eyes_clip(), 'petg', pet, 'PETG: holds the DualEye board in its window; two M3 x 6 into the face\'s bosses')
    # bought parts the shell carries, as envelopes (masses in the ledger's shell rows)
    for side in ('l', 'r'):
        out[f'ear_pod_{side}'] = Part(f'ear_pod_{side}', 'bought', ear_pod(side), 1, colour=(0.23, 0.25, 0.29), note='Diode Dynamics SSC1', stage=P3)
    for front in (True, False):
        n = f'd435_{"front" if front else "rear"}'
        out[n] = Part(n, 'bought', d435(front), 1, colour=(0.16, 0.17, 0.19), note='Intel RealSense D435', stage=P3)
    out['eyes_board'] = Part('eyes_board', 'bought', eyes_board(), 1, colour=(0.05, 0.05, 0.07), note='Waveshare DualEye', stage=P3)
    return out


# ------------------------------------------------------------------------------------------- the checks

def port_check(parts=None):
    """B6: every port a person plugs through the hatch inserts and withdraws: cadagent.connectors' insertion sweep
    against the left rear wall (with its hatch cut) and the hatch's rim, with the windows actually cut."""
    from cadagent.connectors import check_ports
    ports, frame, wall_w = j501_ports()
    wall = _v((parts or {}).get('shell_side_l_rear').shape) if parts else _v(side_wall('l', 'rear'))
    (hx0, hx1, hz0, hz1), wins = hatch_window()
    x0 = bp.J501_AT[0]
    zb = bp.j501_stack()['pcb_bottom']
    cut = [hx0 - x0, hz0 - zb, hx1 - x0, hz1 - zb]
    return check_ports(ports, {n: frame for n in ports}, {'left rear wall': wall}, {n: wall_w for n in ports},
                       windows={n: cut for n in ports})


def ear_beam_margin():
    """How far each pod's top stays under the VLP-16's lowest beam (-15 deg) at its farthest corner (mm)."""
    lid = bp.lidar()
    oc = bp.TOP + lid['oc']
    tan = math.tan(math.radians(-lid['fov_v'][0]))
    out = []
    for side in ('l', 'r'):
        b = _v(ear_pod(side)).BoundingBox()
        far = max(math.hypot(x - lid['x'], y) for x in (b.xmin, b.xmax) for y in (b.ymin, b.ymax))
        out.append(round(oc - far * tan - b.zmax, 2))
    return min(out)
