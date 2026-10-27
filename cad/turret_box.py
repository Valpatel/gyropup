"""The foam-ball turret on the Orin AGX compute box: a printed adapter that carries the turret's TM face on the lid of the
J501 enclosure (~/Code/j501-agx, Rev 0.8), so the turret can be aimed and fired from the computer that will drive it.

Box frame (mm): x forward (the turret's forward at pan 0, out over the J501's front plate), y left, z up, origin on the
desk under the pan axis. The J501's own frame (x across its width, y from its front plate to its rear plate, z up from
its floor) maps to it by x = 96 - y_j, y = x_j - 103, z = z_j: the pan axis stands over the middle of the box.

Why it is shaped this way (the J501's cad/parameters.json):
  - the cooler's 8015 fan breathes in through the roof's hex cells INSIDE a Ø80 ring under the roof, and its hot exhaust
    leaves through the cells AROUND that ring. A plate laid over the roof would make the fan breathe its own exhaust.
    So the deck stands 36 mm above the roof and an intake shroud keeps the two apart: a collar over the ring's cells,
    fed by a duct from a grille at the front. The exhaust leaves under the deck at the two sides; the front corners are
    walled so it cannot curl round into the grille.
  - nothing is drilled in the box: the four legs stand on the lid's four screw corners with a spigot in each screw
    counterbore, and longer screws (M3 x 35 for the M3 x 16) clamp leg, lid and base into the same heat-set inserts.

Parts (PETG: a bench part on a 40 C exhaust, not a robot part):
  box_deck       printed upside down, on its top face: the deck with the turret's TM pattern (4 x M5 inserts on 80 x 80,
                 2 x Ø5 dowel holes, a Ø45 recess: the turret's harness leaves from its side, so nothing passes the TM
                 hole and nothing falls through it into the fan), the four hollow legs, the front skirt each side of the
                 grille, and the control pod under the rear overhang (24 V XT60 in, rocker switch, fuse, 3.5 mm jack for
                 the hold-to-run pendant, the USB-CAN cable out to the J501's rear USB, the DT12 harness in on the -y wall)
  intake_shroud  printed on its floor: a floor with a Ø80 hole over the ring's cells, the collar, the duct walls, the
                 grille bars; 6 tabs with M3 screws up into the deck; 1.5 mm foam tape under the floor round the hole
  pod_cover      printed flat: closes the pod from below (4 x M3 into inserts)
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import cadquery as cq

import gmi
import turret as tu

FAST = gmi.FAST
J501_DIR = Path(os.environ.get('J501_DIR', Path.home() / 'Code' / 'j501-agx'))


def _j501():
    """The J501 enclosure's sizes this adapter depends on, from its parameters.json (the fallbacks are Rev 0.8's)."""
    p = {'width': 206.0, 'front_y': 5.5, 'rear_y': 186.5, 'roof_z': 92.0, 'lid_screws': [[8.8, 30.0], [8.8, 162.0], [197.2, 30.0], [197.2, 162.0]],
         'counterbore_d': 6.4, 'screw_head_z': 78.0, 'lid_screw_len': 16.0, 'fan_xy': [105.0, 105.5], 'ring_d': 80.0, 'ring_wall': 1.6,
         'hex_field': [16.0, 13.5, 190.0, 178.5], 'bulkheads': [['left', 46.5], ['left', 145.5], ['right', 46.5], ['right', 145.5]],
         'bulkhead_z': 62.0, 'revision': '0.8 (built-in fallback)', 'source': None}
    f = J501_DIR / 'cad' / 'parameters.json'
    if f.exists():
        P = json.loads(f.read_text())
        E, C = P['enclosure'], P['cooler']
        ab = E['antenna_bulkheads']
        p.update({'width': E['width'], 'front_y': E['front_y'], 'rear_y': E['rear_y'], 'roof_z': E['height'],
                  'lid_screws': E['lid_screw_centers'], 'counterbore_d': E['lid_counterbore_diameter'], 'screw_head_z': E['lid_screw_head_z'],
                  'lid_screw_len': float(E['lid_screw'].split('x')[1].split()[0]),
                  'fan_xy': [C['center_in_pcb'][0] + E['pcb_margin'], C['center_in_pcb'][1] + E['pcb_margin']],
                  'ring_d': E['fan_duct']['inner_diameter'], 'ring_wall': E['fan_duct']['wall'], 'hex_field': E['hex_field'],
                  'bulkheads': [[b['side'], b['y']] for b in ab['positions']], 'bulkhead_z': ab['z'],
                  'revision': P.get('revision'), 'source': str(f)})
    return p


J = _j501()
TC = (J['width'] / 2, (J['front_y'] + J['rear_y']) / 2)          # the pan axis over the middle of the box (J501 frame)


def to_box(xj, yj, zj=0.0):
    """A J501-frame point (mm) in the box frame."""
    return (TC[1] - yj, xj - TC[0], zj)


ROOF = J['roof_z']                       # the lid's top face
GAP = 36.0                               # roof to the deck's underside: the duct's height (+ floor and gasket)
DECK_T = 8.0
Z_TM = ROOF + GAP + DECK_T               # the turret's TM face (the turret's mount_z in this frame)
DECK_Z0 = Z_TM - DECK_T
FRONT_X = TC[1] - J['front_y']           # the box's front face (+x) and rear face (-x)
REAR_X = TC[1] - J['rear_y']
SIDE_Y = J['width'] / 2
DECK_X = (REAR_X - 25.5, FRONT_X)        # the deck overhangs the rear by 25.5 mm to carry the control pod
CORNER_R = 8.0
LEGS = [to_box(x, y)[:2] for x, y in J['lid_screws']]
LEG_OD, LEG_BORE, PAD_T = 14.0, 7.0, 5.0
SPIGOT_D, SPIGOT_L = J['counterbore_d'] - 0.4, 10.0
LID_SCREW_TIP = J['screw_head_z'] - J['lid_screw_len']           # where the J501's own lid screw ends (full insert)
LID_SCREW_LEN = ROOF + PAD_T - LID_SCREW_TIP                      # the longer screw through a leg: same tip
FAN = to_box(*J['fan_xy'])[:2]
RING_R = J['ring_d'] / 2                 # the intake cells are inside this radius
SH_WALL, SH_FLOOR_T, SH_GAP = 2.5, 2.0, 1.0
SH_Z0 = ROOF + SH_GAP                    # the shroud's floor rests on 1.5 mm foam tape, 1 mm above the roof
SH_R = RING_R + SH_WALL                  # collar outer radius = the duct's half-width outside
POD_X = (DECK_X[0], -56.0)
POD_Y = 62.0
POD_WALL = 3.0
POD_Z0 = ROOF + 5.0                      # the pod's walls end 5 mm above the roof; the cover is 3 mm, so 2 mm of air
SKIRT_T = 2.5
MOUTH_HALF = 62.0                        # the duct flares from the collar's width to 124 mm at the grille: slower air
TAB_X = (FAN[0] - 30.0, 30.0, 78.0)      # the shroud's six M3 tabs (each side), at these x


def wall_y(x, r=SH_R, mouth=MOUTH_HALF + SH_WALL):
    """Half-width of the shroud's plan at x (about FAN[1]): the collar behind the fan centre, the flare in front."""
    if x <= FAN[0]:
        return math.sqrt(max(0.0, r * r - (x - FAN[0]) ** 2))
    return r + (mouth - r) * (x - FAN[0]) / (FRONT_X - FAN[0])


SHROUD_TABS = [(x, FAN[1] + sy * (wall_y(x) + 4.5)) for x in TAB_X for sy in (1, -1)]
POD_BOSSES = [(POD_X[0] + POD_WALL + 4.0, POD_Y - POD_WALL - 4.0), (POD_X[0] + POD_WALL + 4.0, -POD_Y + POD_WALL + 4.0),
              (POD_X[1] - POD_WALL - 4.0, POD_Y - POD_WALL - 4.0), (POD_X[1] - POD_WALL - 4.0, -POD_Y + POD_WALL + 4.0)]
# the pod's rear panel (-x face), left to right seen from behind: (name, y, z, cutout)
POD_ZC = (POD_Z0 + DECK_Z0) / 2
PANEL = [('xt60', -42.0, POD_ZC, ('rect', 16.6, 8.6)),          # Amass XT60E-F panel socket (2 x M2.5 on 28 mm)
         ('switch', -14.0, POD_ZC, ('rect', 21.2, 15.2)),       # KCD1-type rocker, 16 A
         ('fuse', 12.0, POD_ZC, ('round', 12.6)),               # 5 x 20 mm panel fuse holder, 5 A slow-blow
         ('pendant', 30.0, POD_ZC, ('round', 6.2)),             # 3.5 mm panel jack for the hold-to-run pendant
         ('usb', 47.0, POD_ZC, ('rect', 12.0, 7.0))]            # the USB-CAN adapter's cable out to the J501's rear USB
DT_NOTCH = (-86.0, POD_ZC, 13.0)                                # x, z, Ø: the turret's DT12 harness into the pod (-y wall)
# what the antennas on the J501's RP-SMA bulkheads might be (no part chosen yet): a swivel dipole, upright
ANTENNA = {'hinge_out': 14.0, 'whip_d': 10.0, 'whip_len': 108.0, 'note': 'typical 2.4 GHz swivel dipole, Ø10 x 108 (est; none chosen)'}


def _box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def _cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


def _cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def _funnel(r, mouth, x_front, z0, z1):
    """The shroud's plan: the collar disc (radius r) round the fan, and a flare from its width to `mouth` (half-width)
    at x_front."""
    fx, fy = FAN
    flare = cq.Workplane('XY').workplane(offset=z0).polyline([(fx, fy - r), (x_front, fy - mouth), (x_front, fy + mouth), (fx, fy + r)]).close().extrude(z1 - z0)
    return _cyl_z(r, z0, z1, fx, fy).union(flare)


def box_deck():
    """The deck, its legs, the front skirt and the control pod, in one PETG print (on the deck's top face)."""
    x0, x1 = DECK_X
    s = _box(x0, x1, -SIDE_Y, SIDE_Y, DECK_Z0, Z_TM).edges('|Z').fillet(CORNER_R)
    # the legs: hollow columns to the lid's screw corners, a pad on the roof and a spigot in the counterbore
    for (x, y) in LEGS:
        s = s.union(_cyl_z(LEG_OD / 2, ROOF, DECK_Z0 + 0.01, x, y))
        s = s.union(_cyl_z(SPIGOT_D / 2, ROOF - SPIGOT_L, ROOF + 0.01, x, y).faces('<Z').chamfer(0.6))
    # front skirt each side of the grille: the exhaust leaves at the sides, never next to the intake
    fy = FAN[1]
    yc = SIDE_Y - CORNER_R
    for ya, yb in ((-yc, fy - MOUTH_HALF - SH_WALL - 0.4), (fy + MOUTH_HALF + SH_WALL + 0.4, yc)):
        s = s.union(_box(FRONT_X - SKIRT_T, FRONT_X, ya, yb, ROOF + 1.0, DECK_Z0 + 0.01))
    for sy in (1, -1):                                                                      # round the front corners
        ring = _cyl_z(CORNER_R - 0.05, ROOF + 1.0, DECK_Z0 + 0.5, FRONT_X - CORNER_R, sy * yc).cut(
            _cyl_z(CORNER_R - SKIRT_T, ROOF, DECK_Z0 + 1, FRONT_X - CORNER_R, sy * yc))
        s = s.union(ring.intersect(_box(FRONT_X - CORNER_R, FRONT_X, sy * yc, sy * SIDE_Y, ROOF, DECK_Z0 + 1)))
    # the control pod under the rear overhang
    px0, px1 = POD_X
    pod = _box(px0 + 1.0, px1, -POD_Y, POD_Y, POD_Z0, DECK_Z0 + 0.01)
    pod = pod.cut(_box(px0 + 1.0 + POD_WALL, px1 - POD_WALL, -POD_Y + POD_WALL, POD_Y - POD_WALL, POD_Z0 - 1, DECK_Z0))
    s = s.union(pod)
    for (x, y) in POD_BOSSES:
        s = s.union(_cyl_z(4.5, POD_Z0, POD_Z0 + 10.0, x, y))
    # TM insert bosses under the deck (M5 x 8 inserts need a 9 mm pilot) and the shroud's insert bosses
    for (x, y) in tu.TM_BOLTS:
        s = s.union(_cyl_z(6.5, DECK_Z0 - 2.0, DECK_Z0 + 0.01, x, y))
    # ---- cuts
    for (x, y) in LEGS:
        s = s.cut(_cyl_z(LEG_BORE / 2, ROOF + PAD_T, Z_TM + 1, x, y))                      # key and head from above
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2 + 0.1, ROOF - SPIGOT_L - 1, ROOF + PAD_T + 0.1, x, y))
    for (x, y) in tu.TM_BOLTS:
        s = s.cut(_cyl_z(FAST['M5']['insert_pilot'] / 2, Z_TM - 9.0, Z_TM + 0.1, x, y))
    for (x, y) in tu.TM_DOWELS:
        s = s.cut(_cyl_z(2.5 - 0.03, Z_TM - 7.0, Z_TM + 0.1, x, y))
    s = s.cut(_cyl_z(tu.TM_HOLE / 2, Z_TM - 3.0, Z_TM + 0.1))
    for (x, y) in SHROUD_TABS:                                                               # M3 x 4 inserts from below
        s = s.cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, DECK_Z0 - 0.1, DECK_Z0 + 5.0, x, y))
    for (x, y) in POD_BOSSES:
        s = s.cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, POD_Z0 - 0.1, POD_Z0 + 8.0, x, y))
    for name, y, z, cut in PANEL:
        if cut[0] == 'rect':
            s = s.cut(_box(px0 - 1, px0 + 1.0 + POD_WALL + 1, y - cut[1] / 2, y + cut[1] / 2, z - cut[2] / 2, z + cut[2] / 2))
            if name == 'xt60':
                for dy in (-14.0, 14.0):
                    s = s.cut(_cyl_x(1.35, px0 - 1, px0 + 1.0 + POD_WALL + 1, y + dy, z))
        else:
            s = s.cut(_cyl_x(cut[1] / 2, px0 - 1, px0 + 1.0 + POD_WALL + 1, y, z))
    nx, nz, nd = DT_NOTCH
    s = s.cut(_cyl_y(nd / 2, -POD_Y - 1, -POD_Y + POD_WALL + 1, nx, nz))
    return s


def intake_shroud():
    """The intake shroud, PETG on its floor: floor (Ø80 hole over the ring's cells), collar and duct walls up to the
    deck, grille bars across the mouth, six tabs (45 deg undersides, no support) for M3 screws up into the deck."""
    z0, z1 = SH_Z0, DECK_Z0 - 0.2
    outer = _funnel(SH_R, MOUTH_HALF + SH_WALL, FRONT_X - 0.6, z0, z1)
    inner = _funnel(RING_R, MOUTH_HALF + (MOUTH_HALF - RING_R) * 1.6 / (FRONT_X - FAN[0]), FRONT_X + 1.0, z0 + SH_FLOOR_T, z1 + 1.0)
    s = outer.cut(inner)
    s = s.cut(_cyl_z(RING_R, z0 - 1, z0 + SH_FLOOR_T + 0.1, *FAN))                        # the intake hole
    bar, pitch = 2.0, 8.0                                                                   # the grille
    n = int((2 * MOUTH_HALF) // pitch)
    for k in range(n):
        y = FAN[1] - (n - 1) * pitch / 2 + k * pitch
        s = s.union(_box(FRONT_X - 3.0, FRONT_X - 0.6, y - bar / 2, y + bar / 2, z0 + SH_FLOOR_T - 0.01, z1))
    for (x, y) in SHROUD_TABS:
        side = 1 if y > FAN[1] else -1
        yw, yo = FAN[1] + side * (wall_y(x) - 0.8), y + side * 5.0
        drop = abs(yo - yw)                                     # a 45 deg gusset under the tab: prints without support
        prof = [(yw, z1 - 6.0 - drop), (yw, z1), (yo, z1), (yo, z1 - 6.0)]
        s = s.union(cq.Workplane('YZ', origin=(x - 5.0, 0, 0)).polyline(prof).close().extrude(10.0))
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2, z1 - 7.0, z1 + 1.0, x, y))
    for (x, y) in tu.TM_BOLTS:                                  # notches under the deck's TM insert bosses
        s = s.cut(_cyl_z(7.2, DECK_Z0 - 2.6, z1 + 1.0, x, y))
    return s


def pod_cover():
    """The pod's bottom, PETG: 3 mm, 4 x M3 x 6 into the pod's inserts."""
    px0, px1 = POD_X
    s = _box(px0 + 1.0, px1, -POD_Y, POD_Y, POD_Z0 - 3.0, POD_Z0).edges('|Z').fillet(3.0)
    for (x, y) in POD_BOSSES:
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2, POD_Z0 - 4.0, POD_Z0 + 1.0, x, y)).cut(_cyl_z(3.2, POD_Z0 - 4.0, POD_Z0 - 1.6, x, y))
    return s


PARTS = {'box_deck': ('petg', 1, 'PETG upside down on the deck face; 4 x M5 x 8 inserts (TM), 6 + 4 x M3 inserts; no supports '
                                 '(the leg shelves are 7 mm bridges)', ((1, 0, 0), 180)),
         'intake_shroud': ('petg', 1, 'PETG on its floor; 6 x M3 x 8 button heads up into the deck; foam tape under the hole rim', None),
         'pod_cover': ('petg', 1, 'PETG flat; 4 x M3 x 6', None)}


def parts():
    return {'box_deck': box_deck(), 'intake_shroud': intake_shroud(), 'pod_cover': pod_cover()}


def bought():
    """What goes in or on the adapter, as envelopes: {name: (shape, mass_g, note)}."""
    out = {}
    px0 = POD_X[0] + 1.0
    for name, y, z, cut in PANEL:
        d = {'xt60': (18.0, 30.0, 11.0), 'switch': (25.0, 24.0, 18.0), 'fuse': (35.0, 16.0, 16.0), 'pendant': (14.0, 9.0, 9.0),
             'usb': (50.0, 20.0, 12.0)}[name]
        note = {'xt60': 'Amass XT60E-F panel socket: 24 V in (the J501 takes 12-36 V, so one 24 V supply can feed both)',
                'switch': 'KCD1 rocker switch, 16 A', 'fuse': '5 x 20 mm panel fuse holder, 5 A slow-blow',
                'pendant': '3.5 mm panel jack: the hold-to-run pendant (the safety line: nothing spins or feeds unless it is held)',
                'usb': 'USB-CAN adapter (CANable 2.0 class): CAN to the turret, USB to the J501\'s rear USB-A'}[name]
        x_in = px0 + POD_WALL - (3.0 if name != 'usb' else 0.0)
        out[f'pod_{name}'] = (_box(px0 - 3.0 if name != 'usb' else px0 + POD_WALL, x_in + d[0], y - d[1] / 2, y + d[1] / 2, z - d[2] / 2, z + d[2] / 2),
                              {'usb': 20.0}.get(name, 10.0), note)
    out['pod_wago'] = (_box(-80.0, -62.0, -50.0, -10.0, POD_Z0 + 1.0, POD_Z0 + 9.0), 15.0,
                       'WAGO 221 lever connectors: 24 V and 0 V to the DT12 power pins, the pendant loop to its safety pins')
    for k, (x, y) in enumerate(LEGS):
        out[f'lid_screw_{k + 1}'] = (_cyl_z(2.75, ROOF + PAD_T, ROOF + PAD_T + 3.0, x, y).union(_cyl_z(1.5, LID_SCREW_TIP, ROOF + PAD_T, x, y)),
                                     1.5, f'M3 x {LID_SCREW_LEN:.0f} ISO 4762 socket head, in place of the J501\'s M3 x {J["lid_screw_len"]:.0f}')
    return out


def antennas():
    """Upright swivel dipoles on the J501's four RP-SMA bulkheads (if fitted): [(name, base xyz, top xyz, Ø)]."""
    out = []
    for side, yj in J['bulkheads']:
        xj = 0.0 if side == 'left' else J['width']
        x, y, _ = to_box(xj, yj)
        out_dir = -1.0 if y < 0 else 1.0
        yc = y + out_dir * ANTENNA['hinge_out']
        z0 = J['bulkhead_z']
        out.append((f'antenna_{side}_{yj:g}', (x, yc, z0), (x, yc, z0 + ANTENNA['whip_len']), ANTENNA['whip_d']))
    return out


def airflow_estimate(q_m3h=12.94, dp_fan_pa=10.14, dp0_pa=15.2, q0_m3h=38.9):
    """The duct's cost to the J501 fan, by hand (losses K x dynamic pressure; check it in the J501's CFD before trusting
    it). Default operating point: the J501 Rev 0.8 CFD (exports/thermal/cooled-0.8.json there: 12.94 m3/h at 10.14 Pa,
    not converged)."""
    rho = 1.2
    q = q_m3h / 3600
    h = (DECK_Z0 - SH_Z0 - SH_FLOOR_T) / 1000
    v_mouth = q / (2 * MOUTH_HALF / 1000 * h * 0.75)        # through the grille (bars 2 on 8: 75 % open)
    v_throat = q / (2 * RING_R / 1000 * h)                  # where the flare meets the collar
    dp = 1.0 * 0.5 * rho * v_mouth ** 2 + 1.0 * 0.5 * rho * v_throat ** 2   # entry + grille, the turn down (K est)
    w, v = 2 * MOUTH_HALF / 1000, v_mouth
    # a linear fan curve through (0, dp0) and (q0, 0); the box's own resistance as k_sys q^2 through the operating point
    ksys = dp_fan_pa / q_m3h ** 2
    kadd = dp / q_m3h ** 2
    a, b, c = ksys + kadd, dp0_pa / q0_m3h, -dp0_pa
    q_new = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    return {'mouth_mm': [round(w * 1000), round(h * 1000)], 'throat_mm': [round(2 * RING_R), round(h * 1000)],
            'air_speed_mps': {'grille': round(v_mouth, 2), 'throat': round(v_throat, 2)}, 'loss_pa': round(dp, 2),
            'flow_before_m3h': q_m3h, 'flow_after_m3h': round(q_new, 2), 'flow_drop_pct': round(100 * (1 - q_new / q_m3h), 1),
            'note': 'hand estimate (K = 1 at the grille, K = 1 for the turn into the collar; a linear 8015 fan curve, 15.2 Pa '
                    '/ 38.9 m3/h, through the J501 CFD operating point); the J501 CFD '
                    '(tools/thermal.py there) should check it with the deck and shroud in the domain'}
