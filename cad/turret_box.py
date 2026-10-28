"""The foam-ball turret on the Orin AGX compute box: a printed adapter that carries the turret's TM face on the lid of the
J501 enclosure (~/Code/j501-agx, Rev 0.9 with the tower cooler), so the turret can be aimed and fired from the computer
that will drive it (decision D50).

Box frame (mm): x forward (the turret's forward at pan 0, out over the J501's front plate), y left, z up, origin on the
desk under the pan axis. The J501's own frame (x across its width, y from its front plate to its rear plate, z up from
its floor) maps to it by x = 96 - y_j, y = x_j - 103, z = z_j: the pan axis stands over the middle of the box.

Why it is shaped this way (the J501's cad/parameters.json, Rev 0.9 "0.9-g48r"):
  - the cooler is the Seeed reComputer mini J501 heatsink (SKU 100099421): a heat-pipe tower with a 9215 fan (92 x 92 x
    15, 12 V) on top, blowing down, its centre at box (+10.5, 0). Over the fan the roof (97 high) is cut to a flush 3 mm
    grille (openings inside Ø89) on the fan's octagonal outline; a skirt round the fan frame and a band of closed cells
    frame it, and outside them the roof's hex cells let the hot exhaust out. A plate laid over the roof would make the
    fan breathe its own exhaust. So the deck stands 36 mm above the roof and an intake shroud keeps the two apart: a
    Ø104 collar round the grille, on the roof's open-cell boundary (the fan's octagon grown by the grille's clearance,
    the skirt wall and 1 mm), fed by a duct from a grille at the front, 160 mm wide (the plan's 124 mm would cost the
    fan 15 % of its flow at the J501's latest CFD point: airflow_estimate). The shroud's floor reaches in over the
    roof's solid band as a lip, and a ring of foam tape under the lip seals on that band, between the grille's
    openings and the first open cell: no exhaust cell opens inside the ring, whatever the tape's placement to a
    millimetre. The exhaust leaves under the deck at the two sides; the front corners are walled so it cannot curl
    round into the grille.
  - nothing is drilled in the box: the four legs stand on the lid's four screw corners with a spigot in each screw
    counterbore, and longer screws (M3 x 40 for the J501's M3 x 16: the roof + 5 mm pad - the screw's tip at z 62)
    clamp leg, lid and base into the same heat-set inserts.
  - the J501's sizes are read from its parameters at build time (J501_DIR, default ~/Code/j501-agx). The adapter was
    drawn for BUILT_FOR; `revision_warning()` says when the file holds another revision (rebuild and re-check before
    printing: the J501's Rev 0.9 is uncommitted and the fan centre is +-3 mm from a photo). Rev 0.8 (the WS-RDN-601
    cooler, its 8015 fan under a Ø80 duct ring in a 92 mm roof) still builds as the fallback: the collar on the ring.

Parts (PETG: a bench part on a 40 C exhaust, not a robot part):
  box_deck       printed upside down, on its top face: the deck with the turret's TM pattern (4 x M5 inserts on 80 x 80
                 wholly in the 8 mm deck for the turret's 4 x M5 x 12, 2 x Ø5 x 10 dowels, a Ø45 recess: the turret's harness
                 leaves from its side, so nothing passes the TM hole and nothing falls through it into the fan), the
                 four hollow legs, the front skirt each side of the grille, and the control pod under the rear overhang
                 with the bench stand's panel (cad/turret_stand.py PANEL): the XT60E-M 24 V inlet, the Ø20.2 keyed DC
                 rocker (D42), the 5 x 20 fuse holder, the keyed TB3M mini-XLR socket for the hold-to-run pendant (D47),
                 the USB-CAN cable out to the J501's rear USB, the DT12 harness in on the -y wall
  intake_shroud  printed on its floor: the floor (its lip and hole over the grille), the collar, the duct walls, the
                 front grille's bars; 6 tabs (45 deg gussets, no support) with M3 x 10 up into the deck; foam tape
                 under the lip
  pod_cover      printed flat: closes the pod from below (4 x M3 x 6 flat heads, countersunk, into inserts)
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path

import cadquery as cq

import gmi
import turret as tu
import turret_stand as ts

FAST = gmi.FAST
J501_DIR = Path(os.environ.get('J501_DIR', Path.home() / 'Code' / 'j501-agx'))
BUILT_FOR = '0.9-g48r'                   # the J501 revision this adapter is drawn for: the build warns when the file differs

# the J501's own fan curves and CFD operating points, for when its files do not give them (its thermal.fan and its
# exports/thermal/cooled-<rev>.json, each a straight-line fan curve through an actuator disc)
_FAN_CURVE = {'0.8': {'dp0_pa': 15.2, 'q_free_m3h': 38.9, 'note': '8015 PWM fan, 5 V, 2300 rpm: 22.9 CFM free air, 1.55 mmH2O at '
                                                                 'zero flow (its datasheet)'},
              '0.9': {'dp0_pa': 28.1, 'q_free_m3h': 93.9, 'note': '9215-Y at full speed (12 V, 4000 rpm): 55.26 CFM free air, 2.87 '
                                                                 'mmH2O at zero flow (S06 p.2)'}}
_CFD_POINT = {'0.8': {'q_m3h': 12.94, 'dp_pa': 10.14, 'converged': False, 'note': 'the J501 Rev 0.8 CFD as the adapter first read it'},
              '0.9': {'q_m3h': 27.54, 'dp_pa': 19.86, 'converged': False, 'note': 'the J501 Rev 0.9 CFD (bare box, 40 W), stopped '
                                                                                 'unconverged at 43 min'}}


def _major(rev):
    m = re.match(r'(\d+\.\d+)', rev or '')
    return m.group(1) if m else None


def _git(*args):
    """A read-only git query in the J501 repo (rev-parse, hash-object without -w, tag --points-at write nothing)."""
    try:
        r = subprocess.run(['git', '-C', str(J501_DIR), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _provenance(f):
    """The parameters file's state in the J501 repo: committed at HEAD, modified (uncommitted) or untracked."""
    top = _git('rev-parse', '--show-toplevel')
    if top is None or Path(top).resolve() != J501_DIR.resolve():
        return {'state': 'not in a git repository of its own', 'head': None}
    rel = f.resolve().relative_to(J501_DIR.resolve()).as_posix()
    blob_head, blob_now = _git('rev-parse', f'HEAD:{rel}'), _git('hash-object', rel)
    state = 'untracked' if blob_head is None else 'committed' if blob_head == blob_now else 'modified (uncommitted)'
    return {'state': state, 'head': _git('rev-parse', 'HEAD'), 'branch': _git('rev-parse', '--abbrev-ref', 'HEAD'),
            'tags_at_head': (_git('tag', '--points-at', 'HEAD') or '').split(), 'file': rel}


def _operating_point(rev):
    """The fan's flow and pressure rise in the bare box, from the J501's own CFD for this revision when it is there."""
    major = _major(rev)
    f = J501_DIR / 'exports' / 'thermal' / f'cooled-{major}.json'
    if major and f.exists():
        d = json.loads(f.read_text())
        fan = (d.get('fans') or {}).get('fan') or next(iter((d.get('fans') or {}).values()), None)
        if fan and fan.get('flow_m3h') and fan.get('pressure_rise_pa') is not None:
            return {'q_m3h': fan['flow_m3h'], 'dp_pa': fan['pressure_rise_pa'], 'fraction_of_free_air': fan.get('fraction_of_free_air'),
                    'air_into_fan_c': fan.get('air_through_fan_c'), 'converged': d.get('converged'), 'case_revision': d.get('revision'),
                    'source': str(f), 'note': 'the J501\'s CFD of the bare box at 40 W in 25 C air'}
    p = dict(_CFD_POINT.get(major) or _CFD_POINT['0.8'])
    p['source'] = 'built-in (no ' + f.name + ' in the J501 tree)'
    return p


def _j501():
    """The J501 enclosure's sizes this adapter depends on, from its parameters.json (the fallbacks are Rev 0.8's)."""
    p = {'width': 206.0, 'front_y': 5.5, 'rear_y': 186.5, 'roof_z': 92.0, 'roof_t': 4.5,
         'lid_screws': [[8.8, 30.0], [8.8, 162.0], [197.2, 30.0], [197.2, 162.0]], 'counterbore_d': 6.4, 'screw_head_z': 78.0,
         'lid_screw_len': 16.0, 'fan_xy': [105.0, 105.5], 'intake': {'kind': 'ring', 'ring_d': 80.0, 'ring_wall': 1.6},
         'hex': {'af': 10.0, 'web': 1.8, 'field': [16.0, 13.5, 190.0, 178.5]},
         'bulkheads': [['left', 46.5], ['left', 145.5], ['right', 46.5], ['right', 145.5]], 'bulkhead_z': 62.0,
         'cooler': 'Seeed WS-RDN-601 heatsink with an 8015 fan (Rev 0.8)', 'fan_model': '8015 PWM fan, 5 V',
         'fan_curve': dict(_FAN_CURVE['0.8']), 'criteria': {'max_intake_rise_c': 3.0, 'min_fan_fraction_of_free_air': 0.1},
         'revision': '0.8 (built-in fallback)', 'source': None, 'git': None}
    f = J501_DIR / 'cad' / 'parameters.json'
    if f.exists():
        P = json.loads(f.read_text())
        E, C, T = P['enclosure'], P['cooler'], P.get('thermal') or {}
        ab = E['antenna_bulkheads']
        p.update({'width': E['width'], 'front_y': E['front_y'], 'rear_y': E['rear_y'], 'roof_z': E['height'],
                  'roof_t': E.get('roof_thickness', p['roof_t']),
                  'lid_screws': E['lid_screw_centers'], 'counterbore_d': E['lid_counterbore_diameter'], 'screw_head_z': E['lid_screw_head_z'],
                  'lid_screw_len': float(E['lid_screw'].split('x')[1].split()[0]),
                  'fan_xy': [C['center_in_pcb'][0] + E['pcb_margin'], C['center_in_pcb'][1] + E['pcb_margin']],
                  'hex': {'af': E.get('hex_across_flats', 10.0), 'web': E.get('hex_web', 1.8), 'field': E.get('hex_field', p['hex']['field'])},
                  'bulkheads': [[b['side'], b['y']] for b in ab['positions']], 'bulkhead_z': ab['z'],
                  'cooler': C.get('model', p['cooler']), 'revision': P.get('revision'), 'source': str(f), 'git': _provenance(f)})
        if E.get('fan_grille') and C.get('fan'):          # Rev 0.9: a flush grille over the fan, on its octagonal outline
            g, fan = E['fan_grille'], C['fan']
            p['intake'] = {'kind': 'grille', 'frame': fan['frame'], 'corner_chamfer': fan['corner_chamfer'], 'clearance': g['clearance'],
                           'skirt_wall': g['skirt_wall'], 'thickness': g['thickness'], 'hub_d': g['hub_diameter'],
                           # the grille's openings end at the blade circle + 0.4 (the J501's cad/build.py fan_grille_openings)
                           'open_r': fan['blade_diameter'] / 2 + 0.4}
            p['fan_model'] = fan.get('model', '9215 fan')
        elif E.get('fan_duct'):                            # Rev 0.8: a duct ring under the roof round the fan
            p['intake'] = {'kind': 'ring', 'ring_d': E['fan_duct']['inner_diameter'], 'ring_wall': E['fan_duct']['wall']}
        else:
            p['intake'] = dict(p['intake'], note='neither fan_grille nor fan_duct in the file: the Rev 0.8 ring assumed')
        fc = T.get('fan') or {}
        if fc.get('dp0_pa') and fc.get('q_free_m3h'):
            p['fan_curve'] = {'dp0_pa': fc['dp0_pa'], 'q_free_m3h': fc['q_free_m3h'], 'note': fc.get('note', '')}
        else:
            p['fan_curve'] = dict(_FAN_CURVE.get(_major(p['revision'])) or _FAN_CURVE['0.8'])
        p['criteria'].update({k: v for k, v in (T.get('criteria') or {}).items() if k in ('max_intake_rise_c', 'min_fan_fraction_of_free_air')})
    p['operating_point'] = _operating_point(p['revision'])
    return p


J = _j501()
TC = (J['width'] / 2, (J['front_y'] + J['rear_y']) / 2)          # the pan axis over the middle of the box (J501 frame)


def revision_warning():
    """None when the J501 file is the revision this adapter was drawn for and committed there; else what to do."""
    rev, g = J['revision'], J.get('git') or {}
    if rev != BUILT_FOR:
        return (f'the J501 parameters say revision {rev!r}, the adapter was drawn for {BUILT_FOR!r}: check the collar, the '
                f'heights and the airflow in box.json before printing, and set BUILT_FOR once they hold')
    if g.get('state') != 'committed':
        return (f'the J501 parameters ({rev}) are {g.get("state", "unknown")} in the J501 repo: rebuild this adapter when '
                f'Rev {rev.split("-")[0]} is tagged there, before printing it')
    return None


def to_box(xj, yj, zj=0.0):
    """A J501-frame point (mm) in the box frame."""
    return (TC[1] - yj, xj - TC[0], zj)


ROOF = J['roof_z']                       # the lid's top face
GAP = 40.0                               # roof to the deck's underside: the duct's height (+ floor and gasket); 40 since the
#                                          J501's committed Rev 0.9 (the fan re-centred on the module, 38.8 m3/h at its CFD point):
#                                          36 cost 10.9 % of the fan's flow
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
# the TM face: on the box the turret goes on with 4 x M5 x 12 button heads (7 mm past its 5 mm foot) into M5 inserts
# (7.9 mm) wholly inside the 8 mm deck, so nothing hangs below the deck: with the J501's fan re-centred 9.5 mm behind
# the pan axis, the Ø105 collar round its grille reaches the 80 x 80 pattern, and bosses for the stand's M5 x 16 stood in
# its way. Its dowels stand at most 4 mm proud (the pan base's holes are 4 deep): Ø5 x 10 pins 6.5 mm into blind holes
TM_SCREW_LEN = 12.0
TM_SCREW_REACH = TM_SCREW_LEN - tu.Geo().foot_t
TM_PILOT_DEPTH = DECK_T + 0.1                                     # through the deck: the insert fills it, the screw ends 1 mm short
TM_BOSS_R, TM_BOSS_Z0 = 0.0, DECK_Z0                              # no bosses below the deck
DOWEL_HOLE_DEPTH = 6.5
FAN = to_box(*J['fan_xy'])[:2]
SH_WALL, SH_FLOOR_T, SH_GAP = 2.5, 2.0, 1.0
SH_Z0 = ROOF + SH_GAP                    # the shroud's floor rests on 1.5 mm foam tape, 1 mm above the roof
MOUTH_HALF = 79.0                        # the duct's mouth: 158 mm wide (the walls 3.7 mm off the nearer front leg: the fan is
#                                          2 mm off the box's centre line), as wide back
#                                          to the fan's centre (airflow_estimate: 124 mm costs 15 % of the flow at the J501's
#                                          latest CFD point, 160 mm under 10 % at both)
TAPE_W = 3.0                             # the foam ring under the floor's lip
CLEAR = 3.5                              # the collar's wall to the deck's TM insert bosses (the check asks 3)
GRILLE = {'bar': 2.0, 'depth': 4.0, 'pitch': 14.0}               # the front grille: 12 mm gaps keep a 22.7 ball out

_I = J['intake']
if _I['kind'] == 'grille':
    # the J501 roof (cad/build.py there): the grille's openings inside OPEN_R; the pocket, the skirt's top and a band of
    # closed cells round it are solid on top; the first open hex cell lies outside the fan's octagon grown by the
    # grille's clearance + the skirt wall + 1 mm, whose inscribed circle is CELLS_R. The tape rides the middle of that band.
    OPEN_R = _I['open_r']
    CELLS_R = _I['frame'] / 2 + _I['clearance'] + _I['skirt_wall'] + 1.0
    _mid = (OPEN_R + CELLS_R) / 2
    TAPE_R = (_mid - TAPE_W / 2, _mid + TAPE_W / 2)
    HOLE_R = TAPE_R[0] - 0.5
    # the collar's inner face on the open-cell boundary, outside the tape
    COLLAR_R = max(CELLS_R, TAPE_R[1] + 1.0)                     # nothing hangs below the deck in its way
else:
    # Rev 0.8: the intake cells inside the duct ring; the floor's hole is the ring, the tape round it under the floor,
    # the collar's face 0.5 mm outside it (a face on the hole's own circle defeats the solid modeller's booleans)
    OPEN_R = CELLS_R = HOLE_R = _I['ring_d'] / 2
    TAPE_R = (HOLE_R, HOLE_R + TAPE_W)
    COLLAR_R = HOLE_R + 0.5
POD_X = (DECK_X[0], -56.0)
POD_Y = 62.0
POD_WALL = 3.0
POD_Z0 = ROOF + 5.0                      # the pod's walls end 5 mm above the roof; the cover is 3 mm, so 2 mm of air
SKIRT_T = 2.5
TAB_X = (FAN[0] - 30.0, 30.0, 50.0)      # the shroud's six M3 tabs (each side), at these x: the front pair clears the front legs
TAB_T = 6.0                              # the tab's thickness under the deck: the M3 x 10's head seats under it


def _box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def _cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


def _cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def _plan(z0, x1, w=0.0):
    """The shroud's plan at height z0 as a pending wire, grown by w (w = 0: the duct's inner face): the collar's circle
    round the fan and the duct, as wide as the mouth from the fan's centre forward to x1, joined to the circle by
    tangents (the hull of the two)."""
    fx, fy = FAN
    r, h = COLLAR_R, MOUTH_HALF
    th = math.acos(min(1.0, r / h))
    tx, ty = fx - r * math.sin(th), r * math.cos(th)
    wp = (cq.Workplane('XY').workplane(offset=z0).moveTo(x1, fy - h).lineTo(fx, fy - h).lineTo(tx, fy - ty)
          .threePointArc((fx - r, fy), (tx, fy + ty)).lineTo(fx, fy + h).lineTo(x1, fy + h).close())
    return wp.offset2D(w, 'arc') if w else wp


def _outline_points(w, n=2400):
    """Points along the shroud's plan grown by w (box frame, [(x, y)])."""
    wire = _plan(0.0, FRONT_X + 1.0, w).val()
    return [(p.x, p.y) for p in (wire.positionAt(k / n) for k in range(n))]


_OUTER = _outline_points(SH_WALL)


def outer_half(x, half_span=0.4, pick=max):
    """The shroud's outer half-width about the fan's y at x (from the grown plan); with half_span, the widest (pick=max)
    or narrowest (pick=min) along x +- half_span, as a tab 2 x half_span wide sees the wall where it curves."""
    return pick(abs(py - FAN[1]) for px, py in _OUTER if abs(px - x) <= half_span)


SHROUD_TABS = [(x, FAN[1] + sy * (outer_half(x, 5.0) + 4.5)) for x in TAB_X for sy in (1, -1)]
POD_BOSSES = [(POD_X[0] + POD_WALL + 4.0, POD_Y - POD_WALL - 4.0), (POD_X[0] + POD_WALL + 4.0, -POD_Y + POD_WALL + 4.0),
              (POD_X[1] - POD_WALL - 4.0, POD_Y - POD_WALL - 4.0), (POD_X[1] - POD_WALL - 4.0, -POD_Y + POD_WALL + 4.0)]
# the pod's rear panel (-x face): (name, y, z, cutout, panel thickness). The cutouts and thinned panels are the bench
# stand's (cad/turret_stand.py PANEL: the makers' panel holes, D42 and D47), so the two panels take the same parts and
# follow each other; the USB-CAN adapter's cable leaves through the last hole to the J501's rear USB
POD_ZC = (POD_Z0 + DECK_Z0) / 2
_STAND = {n: (cut, t) for n, _y, _z, cut, t in ts.PANEL}
PANEL = [('xt60', -42.0, POD_ZC, _STAND['xt60'][0], min(_STAND['xt60'][1], POD_WALL)),
         ('switch', -12.0, POD_ZC, _STAND['switch'][0], min(_STAND['switch'][1], POD_WALL)),
         ('fuse', 13.0, POD_ZC, _STAND['fuse'][0], min(_STAND['fuse'][1], POD_WALL)),
         ('pendant', 31.0, POD_ZC, _STAND['pendant'][0], min(_STAND['pendant'][1], POD_WALL)),
         ('usb', 48.0, POD_ZC, ('rect', 12.0, 7.0), POD_WALL)]
POCKET = {'switch': 13.0, 'pendant': 10.0}                        # half-size of the thinned panel round a part (the nut)
# what sits in each cutout: catalogue key, envelope behind the panel (depth x width x height), grams, what it is
POD_PARTS = {
    'xt60': ('amass-xt60e-m', (18.0, 30.0, 11.0), 10.0,
             'Amass XT60E-M panel plug: 24 V in (the supply\'s lead carries the female, so no live pin is ever bare; the J501 '
             'takes 12-36 V, so one 24 V supply can feed both)'),
    'switch': ('bulgin-r13244aaaa', (25.0, 24.0, 24.0), 10.0,
               'Bulgin R13244AAAA DC rocker (D42): Ø20.2 snap-in with a key notch, 10 A 28 VDC: turret power'),
    'fuse': ('fuse-holder-5x20-panel', (35.0, 16.0, 16.0), 10.0,
             'Littelfuse 345 panel holder with a DC-rated 5 A time-lag fuse (0477005.MXP)'),
    'pendant': ('switchcraft-tb3m', (24.0, 12.5, 12.5), 10.0,
                'Switchcraft TB3M mini-XLR socket (D47) for the hold-to-run pendant: the safety line, nothing spins or feeds '
                'unless it is held; keyed, so no audio plug (headphones) can close the loop'),
    'usb': ('usb-can-canable2', (50.0, 20.0, 12.0), 20.0,
            'USB-CAN adapter (CANable 2.0 class): CAN to the turret, USB to the J501\'s rear USB-A'),
}
DT_NOTCH = (-86.0, POD_ZC, 13.0)                                # x, z, Ø: the turret's DT12 harness into the pod (-y wall);
#                                                                 its edges chamfered in the print instead of a grommet
# what the antennas on the J501's RP-SMA bulkheads might be (no part chosen yet): a swivel dipole, upright
ANTENNA = {'hinge_out': 14.0, 'whip_d': 10.0, 'whip_len': 108.0, 'note': 'typical 2.4 GHz swivel dipole, Ø10 x 108 (est; none chosen)'}


def _panel_cut(s, name, y, z, cut, t, x0, wall):
    """One cutout in a panel whose outer face is at x0 (the -x side) and inner face at x0 + wall, as the stand cuts its
    own (cad/turret_stand.py stand_box), the wall thinned from inside to t round parts that want a thinner panel."""
    xa, xb = x0 - 1.0, x0 + wall + 1.0
    if t < wall - 1e-6:
        hh = POCKET.get(name, 13.0)
        s = s.cut(_box(x0 + t, xb, y - hh, y + hh, z - hh, z + hh))
    if cut[0] == 'rect':
        s = s.cut(_box(xa, xb, y - cut[1] / 2, y + cut[1] / 2, z - cut[2] / 2, z + cut[2] / 2))
        if name == 'xt60':
            for sy in (-1.0, 1.0):                                   # slots: the screws' spacing is 18..28 mm, M2.5 or M3
                for dy in (9.0, 14.0):
                    s = s.cut(_cyl_x(1.6, xa, xb, y + sy * dy, z))
                ya, yb = sorted((y + sy * 9.0, y + sy * 14.0))
                s = s.cut(_box(xa, xb, ya, yb, z - 1.6, z + 1.6))
    elif cut[0] == 'keyed':                                          # a round hole with a key notch at the top
        s = s.cut(_cyl_x(cut[1] / 2, xa, xb, y, z))
        s = s.cut(_box(xa, xb, y - cut[2] / 2, y + cut[2] / 2, z, z + cut[1] / 2 + 1.0))
    elif cut[0] == 'd':                                              # a D hole: the flat at the top
        s = s.cut(_cyl_x(cut[1] / 2, xa, xb, y, z).cut(_box(xa - 1, xb + 1, y - 10, y + 10, z + cut[2] - cut[1] / 2, z + 10)))
    else:
        s = s.cut(_cyl_x(cut[1] / 2, xa, xb, y, z))
    return s


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
    # ---- cuts
    for (x, y) in LEGS:
        s = s.cut(_cyl_z(LEG_BORE / 2, ROOF + PAD_T, Z_TM + 1, x, y))                      # key and head from above
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2 + 0.1, ROOF - SPIGOT_L - 1, ROOF + PAD_T + 0.1, x, y))
    for (x, y) in tu.TM_BOLTS:
        s = s.cut(_cyl_z(FAST['M5']['insert_pilot'] / 2, Z_TM - TM_PILOT_DEPTH, Z_TM + 0.1, x, y))
    for (x, y) in tu.TM_DOWELS:                                                              # Ø5 x 10 pins, 3.5 proud
        s = s.cut(_cyl_z(2.5 - 0.03, Z_TM - DOWEL_HOLE_DEPTH, Z_TM + 0.1, x, y))
    s = s.cut(_cyl_z(tu.TM_HOLE / 2, Z_TM - 3.0, Z_TM + 0.1))
    for (x, y) in SHROUD_TABS:                                                               # M3 x 4.3 inserts from below
        s = s.cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, DECK_Z0 - 0.1, DECK_Z0 + 5.0, x, y))
    for (x, y) in POD_BOSSES:
        s = s.cut(_cyl_z(FAST['M3']['insert_pilot'] / 2, POD_Z0 - 0.1, POD_Z0 + 8.0, x, y))
    for name, y, z, cut, t in PANEL:
        s = _panel_cut(s, name, y, z, cut, t, px0 + 1.0, POD_WALL)
    nx, nz, nd = DT_NOTCH                                       # the harness's hole, its edges chamfered 1 mm both sides
    s = s.cut(_cyl_y(nd / 2, -POD_Y - 1, -POD_Y + POD_WALL + 1, nx, nz))
    for y0, dy in ((-POD_Y - 0.5, 1.0), (-POD_Y + POD_WALL + 0.5, -1.0)):
        s = s.cut(cq.Workplane('XY').add(cq.Solid.makeCone(nd / 2 + 1.5, nd / 2, 1.5, cq.Vector(nx, y0, nz), cq.Vector(0, dy, 0))))
    return s


def grille_bars():
    """The front grille's bar centres (y) across the mouth and the share of the mouth they leave open."""
    n = int((2 * MOUTH_HALF) // GRILLE['pitch'])
    ys = [FAN[1] - (n - 1) * GRILLE['pitch'] / 2 + k * GRILLE['pitch'] for k in range(n)]
    return ys, 1.0 - n * GRILLE['bar'] / (2 * MOUTH_HALF)


def intake_shroud():
    """The intake shroud, PETG on its floor: the floor (its lip and hole over the fan's grille), the collar and the
    duct's walls up to the deck, the front grille's bars, six tabs (45 deg undersides, no support) with M3 x 10 up into
    the deck (each counterbored from below through its gusset, the head on 6 mm of tab)."""
    z0, z1 = SH_Z0, DECK_Z0 - 0.2
    s = _plan(z0, FRONT_X + 1.0, SH_WALL).extrude(z1 - z0).intersect(_box(FAN[0] - 200, FRONT_X - 0.6, -200, 200, z0 - 1, z1 + 1))
    drops = []
    for (x, y) in SHROUD_TABS:
        side = 1 if y > FAN[1] else -1
        yw, yo = FAN[1] + side * (outer_half(x, 5.0, min) - 0.8), y + side * 5.0       # into the wall all along the tab
        drop = abs(yo - yw)                                     # a 45 deg gusset under the tab: prints without support
        drops.append(drop)
        prof = [(yw, z1 - TAB_T - drop), (yw, z1), (yo, z1), (yo, z1 - TAB_T)]
        s = s.union(cq.Workplane('YZ', origin=(x - 5.0, 0, 0)).polyline(prof).close().extrude(10.0))
    inner = _plan(z0 + SH_FLOOR_T, FRONT_X + 2.0).extrude(z1 - z0)
    hole = _cyl_z(HOLE_R, z0 - 1, z0 + SH_FLOOR_T + 0.1, *FAN)                             # the intake hole
    s = s.cut(inner.union(hole))            # one cut: it also trims the gussets flush inside the wall
    for (x, y), drop in zip(SHROUD_TABS, drops):
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2, z1 - TAB_T - 1.0, z1 + 1.0, x, y))
        s = s.cut(_cyl_z(3.3, z1 - TAB_T - drop - 1.0, z1 - TAB_T, x, y))                  # the head's way in from below
    for y in grille_bars()[0]:                                                              # the front grille
        s = s.union(_box(FRONT_X - 0.6 - GRILLE['depth'], FRONT_X - 0.6, y - GRILLE['bar'] / 2, y + GRILLE['bar'] / 2,
                         z0 + SH_FLOOR_T - 0.01, z1))
    return s


def pod_cover():
    """The pod's bottom, PETG: 3 mm, 4 x M3 x 6 flat heads (countersunk flush) into the pod's inserts."""
    px0, px1 = POD_X
    z0 = POD_Z0 - 3.0
    s = _box(px0 + 1.0, px1, -POD_Y, POD_Y, z0, POD_Z0).edges('|Z').fillet(3.0)
    for (x, y) in POD_BOSSES:
        s = s.cut(_cyl_z(FAST['M3']['clear'] / 2, z0 - 1.0, POD_Z0 + 1.0, x, y))
        s = s.cut(cq.Workplane('XY').add(cq.Solid.makeCone(3.5, 0.0, 3.5, cq.Vector(x, y, z0 - 0.1))))   # 90 deg: Ø7 at the face
    return s


PARTS = {'box_deck': ('petg', 1, 'PETG upside down on the deck face; 4 x M5 x 8 inserts (TM), 6 + 4 x M3 inserts, 2 x Ø5 x 10 '
                                 'dowels pressed in; no supports (the leg shelves are 7 mm bridges)', ((1, 0, 0), 180)),
         'intake_shroud': ('petg', 1, 'PETG on its floor; 6 x M3 x 10 socket heads up into the deck; a 3 mm ring of foam tape '
                                      'under the floor\'s lip', None),
         'pod_cover': ('petg', 1, 'PETG flat; 4 x M3 x 6 flat heads, countersunk', None)}


def parts():
    return {'box_deck': box_deck(), 'intake_shroud': intake_shroud(), 'pod_cover': pod_cover()}


def bought():
    """What goes in or on the adapter, as envelopes: {name: (shape, mass_g, note)}."""
    out = {}
    px0 = POD_X[0] + 1.0
    for name, y, z, cut, t in PANEL:
        _key, d, mass, note = POD_PARTS[name]
        x0, x1 = (px0 + POD_WALL, px0 + POD_WALL + d[0]) if name == 'usb' else (px0 - 3.0, px0 + d[0])
        out[f'pod_{name}'] = (_box(x0, x1, y - d[1] / 2, y + d[1] / 2, z - d[2] / 2, z + d[2] / 2), mass, note)
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


# ------------------------------------------------------------------------------------------------ the J501's roof cells

def _octagon(d, centre):
    """The J501 build's fan_outline(d): the fan frame's octagon (square with 45 deg corner chamfers) grown by d, about
    `centre` (J501 frame)."""
    a = _I['frame'] / 2 + d
    k = _I['corner_chamfer'] + 2 * d - d * math.sqrt(2)
    pts = [(a, -(a - k)), (a, a - k), (a - k, a), (-(a - k), a), (-a, a - k), (-a, -(a - k)), (-(a - k), -a), (a - k, -a)]
    return [(centre[0] + x, centre[1] + y) for x, y in pts]


def _inside(x, y, poly):
    return all((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1) >= 0 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))


def roof_cells():
    """The J501 roof's open hex cells (its cad/build.py roof_cells: every cell of the hex field that clears the fan's
    skirt), each as its six corners in the box frame; None for the Rev 0.8 ring roof."""
    if _I['kind'] != 'grille':
        return None
    H = J['hex']
    s = H['af']
    pitch, rh = s + H['web'], s / math.sqrt(3)
    x0, y0, x1, y1 = H['field']
    dx = pitch * math.sqrt(3) / 2
    nx, ny = int((x1 - x0 - 2 * rh) // dx), int((y1 - y0 - s) // pitch)
    ox, oy = (x0 + x1) / 2 - nx * dx / 2, (y0 + y1) / 2 - ny * pitch / 2
    keep_out = _octagon(_I['clearance'] + _I['skirt_wall'] + rh + 1.0, J['fan_xy'])
    cells = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = ox + i * dx, oy + j * pitch + (pitch / 2 if i % 2 else 0)
            if x - rh >= x0 - 1e-6 and x + rh <= x1 + 1e-6 and y - s / 2 >= y0 - 1e-6 and y + s / 2 <= y1 + 1e-6 and not _inside(x, y, keep_out):
                cells.append([to_box(x + rh * math.cos(math.radians(60 * k)), y + rh * math.sin(math.radians(60 * k)))[:2] for k in range(6)])
    return cells


def intake_seal():
    """Where the foam ring sits on the J501's roof: the grille's openings inside it, the nearest open cell outside it,
    and how many open cells the shroud's floor covers (they then vent only through the 1 mm under the floor)."""
    cells = roof_cells()
    base = {'hole_r_mm': round(HOLE_R, 2), 'tape_r_mm': [round(r, 2) for r in TAPE_R], 'collar_r_mm': round(COLLAR_R, 2),
            'collar_d_mm': round(2 * COLLAR_R, 1), 'intake': _I['kind']}
    if cells is None:
        return dict(base, note='Rev 0.8: the floor\'s hole on the duct ring, the tape round it under the floor (as first drawn)')

    def seg_dist(px, py, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
        return math.hypot(px - ax - t * vx, py - ay - t * vy)
    fx, fy = FAN
    near = min(min(seg_dist(fx, fy, *c[k], *c[(k + 1) % 6]) for k in range(6)) for c in cells)
    from matplotlib.path import Path as MPath
    under = MPath(_OUTER).contains_points([(sum(p[0] for p in c) / 6, sum(p[1] for p in c) / 6) for c in cells])
    return dict(base, grille_open_r_mm=round(OPEN_R, 2), first_open_cell_r_mm=round(near, 2),
                tape_margin_mm={'to_the_grille_openings': round(TAPE_R[0] - OPEN_R, 2), 'to_the_first_open_cell': round(near - TAPE_R[1], 2)},
                open_cells=len(cells), open_cells_under_the_shroud=int(under.sum()),
                note='the J501 roof is solid on top from the grille\'s openings out to its first open hex cell (the grille\'s rim, the '
                     'skirt\'s top, a band of cells closed by a 1.2 mm skin: its cad/build.py); the foam ring lies in the middle of that '
                     'band, so no exhaust cell opens inside it. The open cells under the shroud\'s floor vent through the 1 mm under it')


# ------------------------------------------------------------------------------------------------ airflow

def _kirschmer(bar, gap):
    """A bar screen's loss on the approach speed (Kirschmer, rectangular bars across the flow: beta 2.42)."""
    return 2.42 * (bar / gap) ** (4 / 3)


def _roof_exit_extra(q):
    """Upper bound of what covering roof cells adds on the exhaust side (Pa) at q (m3/s): as if all the box's air left
    through its open roof cells (an exit K of 1.3 on their speed), with and without the ones under the shroud's floor."""
    seal = intake_seal()
    if 'open_cells' not in seal:
        return None
    a_cell = math.sqrt(3) / 2 * (J['hex']['af'] / 1000) ** 2
    n, n_under = seal['open_cells'], seal['open_cells_under_the_shroud']
    return 1.3 * 0.5 * 1.2 * ((q / ((n - n_under) * a_cell)) ** 2 - (q / (n * a_cell)) ** 2)


def airflow_estimate(k_open=1.0, k_mouth=0.0, k_turn=1.0, open_frac=None, mouth_w=None, throat_w=None, dp_extra=0.0, op=None,
                     sensitivity=True):
    """The duct's cost to the J501's fan, by hand: the duct's losses (K x dynamic pressure) in series with the box's own
    resistance (k q^2 through the J501 CFD's operating point), on the fan's straight-line curve (its thermal.fan).

    The method (as the Rev 0.8 adapter was checked): K = 1 on the speed through the front grille's gaps (entry and
    bars together) and K = 1 for the turn down into the fan on the speed across the duct over the fan's centre, the whole
    flow through it (half of it has already gone down into the grille's front half: conservative). The J501's CFD has
    no option for an attached part, so the proof is the thermometer on the box (bench_proof).

    Why the mouth is 160 mm, not the plan's 124: the J501's Rev 0.9 CFD moved from 27.5 m3/h at 19.9 Pa (a run stopped at
    729 iterations) to 36.5 at 17.2 (2,000 iterations, still settling); through 124 mm that flow costs 15 %. 160 mm (as
    wide as the front legs allow) keeps it under 10 % at both points; its floor covers more of the roof's exhaust cells,
    which the bound in the sensitivity puts below the duct loss it saves."""
    op, fc = op or J['operating_point'], J['fan_curve']
    q_m3h, dp_fan, dp0, q0 = op['q_m3h'], op['dp_pa'], fc['dp0_pa'], fc['q_free_m3h']
    rho = 1.2
    q = q_m3h / 3600
    h = (DECK_Z0 - SH_Z0 - SH_FLOOR_T) / 1000
    ys, f_open = grille_bars()
    f = open_frac or f_open
    w_mouth = (mouth_w or 2 * MOUTH_HALF) / 1000
    w_throat = (throat_w or mouth_w or 2 * MOUTH_HALF) / 1000  # the duct is as wide as the mouth over the fan's centre
    v_mouth = q / (w_mouth * h)
    v_gaps = v_mouth / f
    v_throat = q / (w_throat * h)
    dp_grille = k_open * 0.5 * rho * v_gaps ** 2 + k_mouth * 0.5 * rho * v_mouth ** 2
    dp_turn = k_turn * 0.5 * rho * v_throat ** 2
    dp = dp_grille + dp_turn + dp_extra
    ksys, kadd = dp_fan / q_m3h ** 2, dp / q_m3h ** 2
    a, b, c = ksys + kadd, dp0 / q0, -dp0
    q_new = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
    drop = 100 * (1 - q_new / q_m3h)
    out = {'mouth_mm': [round(w_mouth * 1000), round(h * 1000)], 'throat_mm': [round(w_throat * 1000), round(h * 1000)],
           'grille': {'bars': len(ys), 'bar_mm': GRILLE['bar'], 'pitch_mm': GRILLE['pitch'], 'gap_mm': GRILLE['pitch'] - GRILLE['bar'],
                      'open_fraction': round(f, 3)},
           'air_speed_mps': {'mouth': round(v_mouth, 2), 'grille': round(v_gaps, 2), 'throat': round(v_throat, 2)},
           'losses_pa': {'grille': round(dp_grille, 2), 'turn': round(dp_turn, 2)}, 'loss_pa': round(dp, 2),
           'flow_before_m3h': round(q_m3h, 2), 'flow_after_m3h': round(q_new, 2), 'flow_drop_pct': round(drop, 1),
           'fan_fraction_of_free_air_after': round(q_new / q0, 3)}
    if not sensitivity:
        return out
    gap = GRILLE['pitch'] - GRILLE['bar']
    first = dict(_CFD_POINT.get(_major(J['revision'])) or {})
    sens = {
        'the plan\'s duct: a 124 mm mouth flaring from the Ø%.0f collar, 2 mm bars on 8' % (2 * COLLAR_R):
            airflow_estimate(mouth_w=124.0, throat_w=2 * COLLAR_R, open_frac=1 - 2.0 / 8.0, sensitivity=False)['flow_drop_pct'],
        'a 124 mm mouth with this grille, as wide back to the fan': airflow_estimate(mouth_w=124.0, sensitivity=False)['flow_drop_pct'],
        'K = 1.5 for the turn': airflow_estimate(k_turn=1.5, sensitivity=False)['flow_drop_pct'],
        'Idelchik: a sharp inlet (0.5) and the bars by Kirschmer (%.2f) on the mouth speed, the turn K = 1' % _kirschmer(GRILLE['bar'], gap):
            airflow_estimate(k_open=0.0, k_mouth=0.5 + _kirschmer(GRILLE['bar'], gap), sensitivity=False)['flow_drop_pct']}
    extra = _roof_exit_extra(q)
    if extra is not None:
        sens['with the roof cells the floor covers, as if all the air left through the roof (upper bound)'] = \
            airflow_estimate(dp_extra=extra, sensitivity=False)['flow_drop_pct']
    if first and abs(first['q_m3h'] - q_m3h) > 0.05:
        sens['at the J501\'s first Rev %s point (%.1f m3/h at %.1f Pa, the plan\'s)' % (_major(J['revision']), first['q_m3h'], first['dp_pa'])] = \
            airflow_estimate(op=first, sensitivity=False)['flow_drop_pct']
        sens['the plan\'s duct at that point'] = airflow_estimate(mouth_w=124.0, throat_w=2 * COLLAR_R, open_frac=1 - 2.0 / 8.0, op=first,
                                                                  sensitivity=False)['flow_drop_pct']
    out.update({
        'limit_pct': 10.0, 'ok': drop <= 10.0,
        'fan': {'model': J['fan_model'], **fc},
        'operating_point': op,
        'method': 'losses K x 0.5 rho v^2 (rho 1.2): K = 1 through the grille\'s gaps (the entry and the bars), K = 1 for the turn '
                  'down into the fan on the whole flow across the duct over the fan\'s centre; the box\'s own resistance as k q^2 '
                  'through the J501 CFD\'s operating point; the fan\'s straight-line curve from its J501 parameters (dp0, q_free); '
                  'the new flow where the two meet',
        'sensitivity_flow_drop_pct': sens,
        'not_modelled': 'the open roof cells the shroud\'s floor covers (they vent through the 1 mm under it: intake_seal; bounded in '
                        'the sensitivity), the deck over the exhaust, the fan\'s swirl',
        'bench_proof': (f'the thermometer, as the J501\'s own criterion: the box at 40 W (a 40 W nvpmodel under load) with the adapter '
                        f'on and the turret parked, a thermocouple in the collar 10 mm over the grille and one in the room 0.5 m away at '
                        f'the same height, logged for 30 min: the intake within {J["criteria"]["max_intake_rise_c"]:g} K of the room, and '
                        f'the module\'s temperatures from tegrastats no worse than for the same 30 min without the adapter (task N17)'),
        'note': f'hand estimate on the J501 {J["revision"]} fan and its CFD\'s operating point (not converged: rerun this build when it '
                f'settles); the mouth is as wide as the deck\'s front legs allow'})
    return out
