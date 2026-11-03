"""The turret's two snap-fit lids (#131 wave 1): every snap dimension cad/turret.py builds them from, the loads they
hold and their declaration for cad-agent's snap-fit calculator. Plain Python (no CAD kernel), so the declaration and
its checks run anywhere.

    python3 research/snap-fits/snaps.py --cad-agent PATH      # snaps.yaml, cad-agent's snapfit.json, summary.json

Two lids, both PETG, both opened again and again:
  board_bay_lid  two latches, one on its top edge and one on its bottom edge (the same latch turned 180 deg about the
                 bay's axis, so the lid fits either way up); dust cover, opened for board service
  hopper_lid     three latches round the rim (60, 180 and 300 deg); holds the 30 balls in when the robot falls

Each latch is a cantilever tongue lying in the lid's plane, outside the wall it catches, with a barb on its free end
that hooks a ridge on the outside of that wall. The lids print flat (the bay lid on its plate, the hopper lid upside
down), so every tongue lies in the bed plane and bends in it: the bending stress runs along the layers ('along'),
and no layer line crosses the root. The barb and the ridge are both 30 deg ramps (lead and return), so the lid pushes
on and pulls off by hand with no tool and no release to find: a detent, not a lock. Both ramps print without support
(30 deg from the vertical on every part).

The profile is the same on every latch, drawn in (s, n): s is the depth past the seat plane in the closing direction
(the bay's rim, the hopper's top edge; the lid's plate is s -2..0) and n the distance out from the caught wall's outer
face. Only the tongue's length, thickness and the number of latches differ.

Material: Bambu PETG, declared as cad-agent's 'petg-bambu-basic'. The print plan uses Bambu PETG HF
(cad/turret_print.py FILAMENT['petg']) and the catalogue lists PETG Basic (catalog/materials.json 'petg'); Basic's two
data-sheet editions bound HF on all three quantities the check uses (allowable strain 1.28 % against 1.30 % along
the layers, mating modulus 2780 against 1810 MPa, retention modulus 1460 against 1810 MPa), so a pass holds for either
spool.
"""
from __future__ import annotations

import math

MATERIAL = 'petg-bambu-basic'
ORIENTATION = 'along'
PROCESS = 'fdm'
PETG_DENSITY = 1.25                    # g/cm3, catalog/materials.json 'petg'

# ---- the profile, shared by every latch (mm, deg)
UNDERCUT = 1.0          # u: the barb's overlap with the ridge, the deflection the tongue takes to pass it
WALL_CLEAR = 0.2        # the barb's tip clear of the caught wall's face
TONGUE_GAP = 0.3        # the tongue's inner face clear of the ridge's top
LEAD_DEG = 30.0         # the barb's lead face, from the closing direction (the guide's alpha)
RETURN_DEG = 30.0       # the barb's return face and the ridge's back face, parallel (the guide's alpha')
RIDGE_LEAD_DEG = 45.0   # the ridge's entry face: steeper than the barb's lead, so the barb's 30 deg face is what rides
RIDGE_START = 0.3       # the ridge starts this far past the seat plane (the lid's plate never touches it)
RIDGE_LAND = 0.4        # flat top of the ridge
BARB_LAND = 0.4         # flat tip of the barb (a printed knife edge would round off)
PLAY = 0.3              # in the closed pose the barb's return face sits this far past the ridge's (along s): no preload
PLATE_T = 2.0           # both lids' plates (the hopper lid's disc, the bay lid's plate)
RIDGE_H = WALL_CLEAR + UNDERCUT          # the ridge stands 1.2 off the wall
TONGUE_N = RIDGE_H + TONGUE_GAP          # the tongue's inner face, 1.5 off the wall
ROOT_RATIO = 0.6                         # root fillet R = 0.6 h (the guide's Fig. 9: no gain beyond)


def _t(deg):
    return math.tan(math.radians(deg))


def profile():
    """The ridge and the barb in (s, n), closed pose, and the s-extents that follow. Every point is a corner of the
    solid cad/turret.py extrudes or revolves."""
    s0 = RIDGE_START
    s_top0 = s0 + RIDGE_H / _t(RIDGE_LEAD_DEG)
    s_top1 = s_top0 + RIDGE_LAND
    s_end = s_top1 + RIDGE_H / _t(RETURN_DEG)
    ridge = [(s0, 0.0), (s_top0, RIDGE_H), (s_top1, RIDGE_H), (s_end, 0.0)]
    # the barb's return face: the ridge's back face moved PLAY along s, from the tongue (n = TONGUE_N) to the tip
    ret_line = lambda n: s_top1 + PLAY + (RIDGE_H - n) / _t(RETURN_DEG)
    b0 = ret_line(TONGUE_N)
    b1 = ret_line(WALL_CLEAR)
    b2 = b1 + BARB_LAND
    b3 = b2 + (TONGUE_N - WALL_CLEAR) / _t(LEAD_DEG)
    barb = [(b0, TONGUE_N), (b1, WALL_CLEAR), (b2, WALL_CLEAR), (b3, TONGUE_N)]
    return {'ridge': ridge, 'barb': barb, 'ridge_s': (s0, s_end), 'tongue_s': (-PLATE_T, b3),
            'lead_travel': (TONGUE_N - WALL_CLEAR) / _t(LEAD_DEG)}


def tongue_width():
    """b: the tongue's size across its bending plane, along the closing direction (the print's z on both lids)."""
    s0, s1 = profile()['tongue_s']
    return s1 - s0


# ---- the latches. L: the root (the root block's face) to the barb's centre, along the tongue (for the hopper's
# curved tongues, the arc at the tongue's mid-thickness); h: the tongue's thickness in the lid's plane (the bending
# thickness); barb_w: the barb's and the ridge's width along the tongue, the ridge 1.5 longer each side.
# The hopper's latches: centres_deg are the middles of their footprints (root block to barb), 60 deg either side of the
# fill flap's hinge at the back: each stays 10 deg or more clear of the hopper-full beam's holes at 90 and 270 deg
# (its emitter and receiver sit outside them) and of the cartridge board in front.
HOPPER = {'part': 'hopper_lid', 'catch': 'hopper', 'n': 3, 'centres_deg': (60.0, 180.0, 300.0),
          'L': 27.5, 'h': 3.0, 'barb_w': 5.0, 'ridge_extra': 1.5, 'root_w': 6.0,
          'cycles': 2000, 'cycles_basis': 'opened for every manual refill: about 5 a day of play, 200 days a year, 2 years (est)'}
BAY = {'part': 'board_bay_lid', 'catch': 'board_bay', 'n': 2,
       'L': 25.0, 'h': 2.5, 'barb_w': 6.0, 'ridge_extra': 1.5, 'root_w': 5.0, 'x_root': -15.0,
       'cycles': 100, 'cycles_basis': 'opened for board service and bring-up: about 100 over the turret\'s life (est)'}
# The catch walls are thin (the hopper's 1.6, the bay's 1.2), so the lid backs each from inside over the ridge: the
# hopper lid's spigot (4 deep, 0.1 inside the wall) and two pads on the bay lid's lip behind the bay's ridges. Through
# the pull-off the barb's contact runs from the ridge's back face up to its top (s 1.9 + PLAY) while the lid lifts
# lead_travel: the backing reaches it all the way (cad/test_turret_snaps.py).
BACKING_DEPTH = 4.0     # s; the hopper lid's spigot is G.hopper_top - 4 .. G.hopper_top
BAY_PAD_T = 1.0         # the bay lid's pads, inside the walls: 1.3 clear of the level-2 board's envelope
HOPPER['curved'] = True  # its tongues are arcs round the hopper: research/snap-fits/snaps.py corrects the straight beam
HOPPER_WALL_R = 50.7    # the hopper's outside radius (cad/turret.py Geo.dial_wall_r + HOPPER_WALL), checked by the CAD
# Each part's print orientation: the rotation is cad/turret.py MADE's (checked there). Both lids lie with the tongues in
# the bed plane, so they bend along the layers; both catch parts print with the closing direction vertical.
PRINT = {'hopper_lid': {'rotation': [[1, 0, 0], 180], 'how': 'upside down: the tongues lie in the bed plane; it stands on the '
                                                              'flap\'s hinge lugs, 7 mm proud of the disc, so the disc and the '
                                                              'latches print on supports (cad/turret_print.py); the barbs\' '
                                                              'return faces overhang 30 deg from the vertical'},
         'hopper': {'rotation': None, 'how': 'standing on its bottom rim and the baffle: the ridges\' undersides overhang 30 deg '
                                             'from the vertical'},
         'board_bay_lid': {'rotation': [[1, 0, 0], 90], 'how': 'flat, the plate on the bed: the tongues lie in the bed plane; '
                                                               'the barbs\' return faces overhang 30 deg from the vertical'},
         'board_bay': {'rotation': [[1, 0, 0], -90], 'how': 'on its back, the open face up: the ridges\' back faces overhang '
                                                           '30 deg from the vertical'}}
for _L in (HOPPER, BAY):
    _L['root_r'] = round(ROOT_RATIO * _L['h'], 3)

# ---- the loads (N): what each lid must hold and the most a hand should need
G0 = 9.81
FALL_G = 30.0           # cad/turret_studies.py FALL_G: the TM interface's 30 g design load (docs/cad-plan.md section 5)
TILT_DEG = 25.0         # the tilt's -25 deg hard stop (cad/turret.py TILT_STOP_DEG)
BALLS = 30
BALL_G = 1.83           # cad/turret.py mass_properties: 30 Rival rounds x 1.83 g (sim/turret_ball.py 'hasbro')
SF_RETENTION = 1.2      # cad/turret_studies.py TARGETS['sf_rare'], the turret's target for the rare R-fall case
HAND_N = 50.0           # cad/turret_studies.py PUSH_N: the hand load the turret's structure is checked for (E-push)
# Masses the latches must hold, upper bounds checked against the CAD (cad/test_turret_snaps.py): each part solid
# (PETG at 1.25 g/cm3; printed at 40 % infill inside 2 mm walls it is lighter), the fill flap with its pin and spring
HOPPER_LID_G = 25.0     # hopper_lid + hopper_flap solid (23.7 g), + 1 g for the Ø2 pin and the torsion spring
BAY_LID_G = 11.5        # board_bay_lid solid (10.9 g)
# PETG's friction is not in the guide's Table 3. Its polyester neighbour PBT is 0.35-0.40 against steel; the table's
# factor for a plastic on itself is 1.0-2.0 (1.5 for PP, POM and PA). The bounds: 0.35 for retention (the least that
# holds) and 0.40 x 1.5 = 0.60 for the push and the pull (the most a hand must give). A coupon decides.
FRICTION = {'low': 0.35, 'high': 0.60,
            'source': "Covestro, Snap-Fit Joints for Plastics - A Design Guide, Table 3 (cad-agent "
                      "research/compliant-mechanisms.md section 4): PETG is not listed; PBT, its polyester neighbour, "
                      "is 0.35-0.40 against steel; low = 0.35, high = 0.40 x 1.5 (the table's same-material factor for "
                      "PP, POM and PA)"}
# layer-aware PETG allowables of the turret's FEA (cad/turret_studies.py LAYER_ALLOW['petg']): along the layers, and
# interlaminar shear (0.5 x the 20 MPa across)
PETG_ALONG_MPA = 29.0
PETG_SHEAR_MPA = 10.0


def hopper_load():
    """The hopper lid's design load: a forward fall with the barrel at its -25 deg stop. The R-fall case loads every
    part with 30 g straight down or sideways (cad/turret_studies.py); straight down presses the balls onto the dial,
    away from the lid. Sideways, the hopper's axis leans 25 deg forward at the stop, so a forward fall drives the balls
    and the lid along it towards the lid with 30 g x sin 25 deg = 12.7 g. Recoil (0.039 N s a shot, along the barrel,
    research/turret-launcher-study.md) acts across the hopper's axis: nothing towards the lid."""
    n_g = FALL_G * math.sin(math.radians(TILT_DEG))
    m_g = BALLS * BALL_G + HOPPER_LID_G
    f = m_g / 1000 * G0 * n_g
    return {'case': 'R-fall sideways (forward fall) at the -25 deg tilt stop', 'accel_g': n_g, 'mass_g': m_g,
            'balls_g': BALLS * BALL_G, 'lid_g': HOPPER_LID_G, 'force_n': f, 'sf': SF_RETENTION,
            'required_n': SF_RETENTION * f,
            'source': 'cad/turret_studies.py R-fall (FALL_G 30, the TM design load of docs/cad-plan.md section 5); '
                      'the hopper axis leans 25 deg at the stop (cad/turret.py tilt_min)'}


def bay_load():
    """The bay lid's design load: R-fall's 30 g on the lid's own mass, along its normal (pan turns the bay to face any
    side, so a sideways fall can pull it straight off)."""
    f = BAY_LID_G / 1000 * G0 * FALL_G
    return {'case': 'R-fall sideways, along the lid\'s normal', 'accel_g': FALL_G, 'mass_g': BAY_LID_G,
            'force_n': f, 'sf': SF_RETENTION, 'required_n': SF_RETENTION * f,
            'source': 'cad/turret_studies.py R-fall (FALL_G 30)'}


LOADS = {'hopper_lid': hopper_load, 'board_bay_lid': bay_load}
LATCHES = {'hopper_lid': HOPPER, 'board_bay_lid': BAY}


def snap_name(part, mu):
    return f'{part}-latch-mu-{mu}'


def spec():
    """The cad-agent snapfit declaration: each latch twice, at the low and the high friction bound. The low row holds
    the retention minimum (the least the latch holds), the high row the mating maximum (the most a hand pushes); the
    pull-off at the high bound (not a row the toolkit checks) is checked in research/snap-fits/snaps.py."""
    snaps = []
    for part, lat in LATCHES.items():
        load = LOADS[part]()
        for mu in ('low', 'high'):
            s = {'name': snap_name(part, mu), 'material': MATERIAL, 'process': PROCESS, 'orientation': ORIENTATION,
                 'repeated': True, 'design': 1, 'length_mm': lat['L'], 'undercut_mm': UNDERCUT,
                 'section': {'rect': {'width_mm': round(tongue_width(), 4), 'thickness_mm': lat['h']}},
                 'root_radius_mm': lat['root_r'], 'lead_deg': LEAD_DEG, 'return_deg': RETURN_DEG,
                 'friction': FRICTION[mu]}
            if mu == 'low':
                s['min_retention_n'] = round(load['required_n'] / lat['n'], 4)
            else:
                s['max_mating_n'] = round(HAND_N / lat['n'], 4)
            snaps.append(s)
    return {'snaps': snaps}


def _scalar(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    v = str(v)
    return v if v.replace('-', '').replace('_', '').isalnum() else '"' + v.replace('"', '\\"') + '"'


def _emit(obj, indent=0):
    pad = ' ' * indent
    out = []
    for k, v in obj.items():
        if isinstance(v, dict):
            out.append(f'{pad}{k}:')
            out += _emit(v, indent + 2)
        else:
            out.append(f'{pad}{k}: {_scalar(v)}')
    return out


HEADER = ('# The turret lids\' snap fits (#131 wave 1). Generated from cad/turret_snaps.py, the constants cad/turret.py\n'
          '# builds the latches from: do not edit; run python3 research/snap-fits/snaps.py --cad-agent PATH.\n'
          '#   cad-agent snapfit research/snap-fits/snaps.yaml --output research/snap-fits/snapfit.json\n')


def yaml_text():
    """snaps.yaml, written without a YAML library (block style, one snap per list item) so the check runs anywhere."""
    lines = [HEADER.rstrip('\n'), 'snaps:']
    for s in spec()['snaps']:
        body = _emit(s, 4)
        body[0] = '  - ' + body[0][4:]
        lines += body
    return '\n'.join(lines) + '\n'
