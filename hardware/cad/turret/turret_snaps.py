"""The turret's two snap-fit lids (#131 wave 1): every snap dimension hardware/cad/turret/turret.py builds them from, the loads they
hold and their declaration for cad-agent's snap-fit calculator. Plain Python (no CAD kernel), so the declaration and
its checks run anywhere.

    python3 docs/research/snap-fits/snaps.py --cad-agent PATH      # snaps.yaml, cad-agent's snapfit.json, summary.json

Two lids, both PETG, both opened again and again:
  board_bay_lid  two latches, one on its top edge and one on its bottom edge (the same latch turned 180 deg about the
                 bay's axis, so the lid fits either way up); dust cover, opened for board service
  hopper_lid     three latches round the rim (0, 120 and 240 deg); holds the 30 balls in when the robot falls

Each latch is a cantilever tongue lying in the lid's plane, outside the wall it catches, with a barb on its free end
that hooks a ridge on the outside of that wall. The lids print flat (the bay lid on its plate, the hopper lid upside
down), so every tongue lies in the bed plane and bends in it: the bending stress runs along the layers ('along').
The root is not all along the layers, though: each tongue is wider (along the closing direction, the print's z) than
the plate it springs from is thick, so its root block hands the tongue's moment to the plate across layer lines, as
a twist and a peel of the block's layers. docs/research/snap-fits/snaps.py checks both by hand, with the tongue's own
bending out of its plane (the pull at the barb) added to its in-plane strain at the root's corner. The barb and the
ridge are both 30 deg ramps (lead and return), so the lid pushes on and pulls off by hand with no tool and no release
to find: a detent, not a lock. Both ramps print without support (30 deg from the vertical on every part).

The profile is the same on every latch, drawn in (s, n): s is the depth past the seat plane in the closing direction
(the bay's rim, the hopper's top edge; the lid's plate is s -2..0) and n the distance out from the caught wall's outer
face. The tongue's length, thickness, width (its s extent) and root block and the number of latches differ.

Material: Bambu PETG, declared as cad-agent's 'petg-bambu-basic'. The print plan uses Bambu PETG HF
(hardware/cad/turret/turret_print.py FILAMENT['petg']) and the catalogue lists PETG Basic (hardware/catalog/materials.json 'petg'); Basic's two
data-sheet editions bound HF on all three quantities the check uses (allowable strain 1.28 % against 1.30 % along
the layers, mating modulus 2780 against 1810 MPa, retention modulus 1460 against 1810 MPa), so a pass holds for either
spool.
"""
from __future__ import annotations

import math

MATERIAL = 'petg-bambu-basic'
ORIENTATION = 'along'
PROCESS = 'fdm'
PETG_DENSITY = 1.25                    # g/cm3, hardware/catalog/materials.json 'petg'

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
    solid hardware/cad/turret/turret.py extrudes or revolves."""
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
    # where the barb bears on the ridge as it holds and as it is pulled off: the return face at the ridge's mid-height
    contact = ret_line((WALL_CLEAR + RIDGE_H) / 2)
    return {'ridge': ridge, 'barb': barb, 'ridge_s': (s0, s_end), 'barb_s': (b0, b3), 'contact_s': contact,
            'lead_travel': (TONGUE_N - WALL_CLEAR) / _t(LEAD_DEG)}


def tongue_s(lat):
    """The tongue's s extent: from s_lo (at or above the plate's top, -PLATE_T) to s_hi (at or past the barb's end)."""
    return lat['s_lo'], lat['s_hi']


def tongue_width(lat):
    """b: the tongue's size across its bending plane, along the closing direction (the print's z on both lids)."""
    s0, s1 = tongue_s(lat)
    return s1 - s0


def root_section(lat):
    """The root block's section where it leaves the plate (a layer plane, s 0): root_w along the tongue by c across
    it, from the barb's clearance off the wall to the block's outer face (the tongue's outer face + root_out)."""
    return lat['root_w'], TONGUE_N - WALL_CLEAR + lat['h'] + lat['root_out']


# ---- the latches. L: the root (the root block's face) to the barb's centre, along the tongue (for the hopper's
# curved tongues, the arc at the tongue's mid-thickness); h: the tongue's thickness in the lid's plane (the bending
# thickness); s_lo..s_hi: the tongue's extent along the closing direction (b = s_hi - s_lo, its width: wide, so the
# pull at the barb bends it little out of its plane); barb_w: the barb's and the ridge's width along the tongue, the
# ridge 1.5 longer each side; root_w: the root block along the tongue, root_out: the block's thickness outside the
# tongue's outer face (both size the block's layers against the twist and the peel; snaps.py).
# The sizes until the review of PR #181 (OLD) bent the tongues out of their plane enough that, added to the in-plane
# strain at the root's corner, the strain passed the allowable at the high friction bound, and twisted the root
# block's layers to 9 MPa against 10: docs/research/snap-fits/test_snaps.py keeps them as the control. Now the tongues are
# wider (b 24 and 12.5 against 8.6), the hopper's thinner and the root blocks bigger.
# The hopper's latches: centres_deg are the middles of their footprints (root block to barb): one at the front, over
# the key, and two 120 deg round, none at the back. Upside down the turret lands on its top, and the latches must not
# be what it lands on (INVERTED_REASON): tilted back towards the -25 deg stop the lid's back rises first, and a latch
# there stood 6 mm above everything else (the review of PR #181), so the back is left to the flap's hinge lugs. Each
# latch, with its ridge, stays more than 8 deg clear of the hopper-full beam's holes at 90 and 270 deg (its emitter and
# receiver sit outside them) and clear of the cartridge board in front (tests/hardware/turret/test_turret_snaps.py).
# The tongues are b 24 wide along the closing direction (the width that keeps the out-of-plane bending and the
# tongue's twist low: an arc's tip lies inside its root's tangent) and their tops stand LATCH_DROP below the lugs'
# tops, so over the whole tilt range the lugs and the flap meet the ground first (FIRST_CONTACT_MARGIN; tested).
# The hopper lid prints upside down on those lugs; the disc, the root blocks' and the tongues' tops print on supports.
# Those top faces are the tongues' edges across their width, lightly loaded: the pull bends the tongue's inner and
# outer faces; at its top edge only the out-of-plane bending peaks, at 1.93 MPa (about 0.07 %; per_latch
# bending_mpa in docs/research/snap-fits/summary.json).
LID_LUG_PROUD = 7.0     # the flap's hinge lugs above the hopper lid's disc (hardware/cad/turret/turret.py hopper_lid)
LATCH_DROP = 2.5        # the hopper latches' tops below the lugs' tops
FIRST_CONTACT_MARGIN = 1.0   # mm: every latch at least this far below the turret's top, upside down, at every tilt
_HOPPER_B = 24.0
HOPPER = {'part': 'hopper_lid', 'catch': 'hopper', 'n': 3, 'centres_deg': (0.0, 120.0, 240.0),
          'L': 26.0, 'h': 2.0, 's_lo': -(PLATE_T + LID_LUG_PROUD - LATCH_DROP),
          's_hi': -(PLATE_T + LID_LUG_PROUD - LATCH_DROP) + _HOPPER_B, 'barb_w': 5.0, 'ridge_extra': 1.5,
          'root_w': 8.0, 'root_out': 3.0,
          'curved': True,         # its tongues are arcs round the hopper: docs/research/snap-fits/snaps.py corrects the straight beam
          'cycles': 2000, 'cycles_basis': 'opened for every manual refill: about 5 a day of play, 200 days a year, 2 years (est)'}
BAY = {'part': 'board_bay_lid', 'catch': 'board_bay', 'n': 2,
       'L': 32.5, 'h': 3.0, 's_lo': -PLATE_T, 's_hi': 10.5, 'barb_w': 6.0, 'ridge_extra': 1.5,
       'root_w': 12.0, 'root_out': 0.0, 'x_root': -14.0,
       'cycles': 100, 'cycles_basis': 'opened for board service and bring-up: about 100 over the turret\'s life (est)'}
# FA7E3C4: the hopper latches as reviewed at fa7e3c4 (60, 180 and 300 deg, up to the lugs' height), the control for
# the first-contact test: their back latch is the turret's top at the -25 deg stop.
FA7E3C4 = dict(HOPPER, centres_deg=(60.0, 180.0, 300.0), s_lo=-(PLATE_T + LID_LUG_PROUD), s_hi=15.0)
OLD = {'hopper_lid': dict(HOPPER, L=27.5, h=3.0, s_lo=-PLATE_T, s_hi=profile()['barb_s'][1], root_w=6.0, root_out=0.0),
       'board_bay_lid': dict(BAY, L=25.0, h=2.5, s_lo=-PLATE_T, s_hi=profile()['barb_s'][1], root_w=5.0, root_out=0.0,
                             x_root=-15.0)}
# The catch walls are thin (the hopper's 1.6, the bay's 1.2), so the lid backs each from inside over the ridge: the
# hopper lid's spigot (4 deep, 0.1 inside the wall) and two pads on the bay lid's lip behind the bay's ridges. Through
# the pull-off the barb's contact runs from the ridge's back face up to its top (s 1.9 + PLAY) while the lid lifts
# lead_travel: the backing reaches it all the way (tests/hardware/turret/test_turret_snaps.py).
BACKING_DEPTH = 4.0     # s; the hopper lid's spigot is G.hopper_top - 4 .. G.hopper_top
# The hopper lid goes on one way only: a tab on its spigot drops into a notch in the hopper's rim, so the fill port
# sits over the dock's spout and the barbs over their ridges. Turned any other way the tab stands on the rim and the
# lid stands depth proud, unlatched and plainly not seated (tests/hardware/turret/test_turret_snaps.py). At 0 deg (the front), under the
# front latch's tongue, which stands outside the wall clear of the notch; inside the wall's outer face, so nothing
# shows outside it.
KEY = {'deg': 0.0, 'w': 4.0, 'depth': 3.0, 'r_in': 48.0, 'r_out': 50.4, 'clear': 0.3}
BAY_PAD_T = 1.0         # the bay lid's pads, inside the walls: 1.3 clear of the level-2 board's envelope
HOPPER_WALL_R = 50.7    # the hopper's outside radius (hardware/cad/turret/turret.py Geo.dial_wall_r + HOPPER_WALL), checked by the CAD
# Each part's print orientation: the rotation is hardware/cad/turret/turret.py MADE's (checked there). Both lids lie with the tongues in
# the bed plane, so they bend along the layers; both catch parts print with the closing direction vertical.
PRINT = {'hopper_lid': {'rotation': [[1, 0, 0], 180], 'how': 'upside down: the tongues lie in the bed plane; it stands on the '
                                                              'flap\'s hinge lugs, 7 mm proud of the disc; the disc and the '
                                                              'latches\' tops (2.5 mm below the lugs) print on supports '
                                                              '(hardware/cad/turret/turret_print.py), which touch only those top faces, the '
                                                              'tongues\' edges across their width; the barbs\' return faces '
                                                              'overhang 30 deg from the vertical'},
         'hopper': {'rotation': None, 'how': 'standing on its bottom rim and the baffle: the ridges\' undersides overhang 30 deg '
                                             'from the vertical'},
         'board_bay_lid': {'rotation': [[1, 0, 0], 90], 'how': 'flat, the plate on the bed: the tongues lie in the bed plane; '
                                                               'the barbs\' return faces overhang 30 deg from the vertical'},
         'board_bay': {'rotation': [[1, 0, 0], -90], 'how': 'on its back, the open face up: the ridges\' back faces overhang '
                                                           '30 deg from the vertical'}}
for _L in (HOPPER, BAY, FA7E3C4, *OLD.values()):
    _L['root_r'] = round(ROOT_RATIO * _L['h'], 3)

# ---- the loads (N): what each lid must hold and the most a hand should need
G0 = 9.81
FALL_G = 30.0           # hardware/cad/turret/turret_studies.py FALL_G: the TM interface's 30 g design load (docs/architecture/cad-plan.md section 5)
TILT_DEG = 25.0         # the tilt's -25 deg hard stop (hardware/cad/turret/turret.py TILT_STOP_DEG)
BALLS = 30
BALL_G = 1.83           # hardware/cad/turret/turret.py mass_properties: 30 Rival rounds x 1.83 g (software/simulation/turret_ball.py 'hasbro')
SF_RETENTION = 1.2      # hardware/cad/turret/turret_studies.py TARGETS['sf_rare'], the turret's target for the rare R-fall case
HAND_N = 50.0           # hardware/cad/turret/turret_studies.py PUSH_N: the hand load the turret's structure is checked for (E-push)
# Masses the latches must hold, upper bounds checked against the CAD (tests/hardware/turret/test_turret_snaps.py): each part solid
# (PETG at 1.25 g/cm3; printed at 40 % infill inside 2 mm walls it is lighter), the fill flap with its pin and spring
HOPPER_LID_G = 32.0     # hopper_lid + hopper_flap solid (30.1 g), + 1 g for the Ø2 pin and the torsion spring
BAY_LID_G = 14.5        # board_bay_lid solid (13.95 g)
# PETG's friction is not in the guide's Table 3. Its polyester neighbour PBT is 0.35-0.40 against steel; the table's
# factor for a plastic on itself is 1.0-2.0 (1.5 for PP, POM and PA). The bounds: 0.35 for retention (the least that
# holds) and 0.40 x 1.5 = 0.60 for the push and the pull (the most a hand must give). A coupon decides.
FRICTION = {'low': 0.35, 'high': 0.60,
            'source': "Covestro, Snap-Fit Joints for Plastics - A Design Guide, Table 3 (cad-agent "
                      "research/compliant-mechanisms.md section 4): PETG is not listed; PBT, its polyester neighbour, "
                      "is 0.35-0.40 against steel; low = 0.35, high = 0.40 x 1.5 (the table's same-material factor for "
                      "PP, POM and PA)"}
# layer-aware PETG allowables of the turret's FEA (hardware/cad/turret/turret_studies.py LAYER_ALLOW['petg']): along the layers, and
# interlaminar shear (0.5 x the 20 MPa across)
PETG_ALONG_MPA = 29.0
PETG_ACROSS_MPA = 20.0
PETG_SHEAR_MPA = 10.0


def hopper_load():
    """The hopper lid's design load: a forward fall with the barrel at its -25 deg stop. The R-fall case loads every
    part with 30 g straight down or sideways (hardware/cad/turret/turret_studies.py); straight down presses the balls onto the dial,
    away from the lid. Sideways, the hopper's axis leans 25 deg forward at the stop, so a forward fall drives the balls
    and the lid along it towards the lid with 30 g x sin 25 deg = 12.7 g. Recoil (0.039 N s a shot, along the barrel,
    docs/research/turret-launcher-study.md) acts across the hopper's axis: nothing towards the lid. Upside down (R-fall up)
    is excluded, with its reason: load_cases()."""
    n_g = FALL_G * math.sin(math.radians(TILT_DEG))
    m_g = BALLS * BALL_G + HOPPER_LID_G
    f = m_g / 1000 * G0 * n_g
    return {'case': 'R-fall sideways (forward fall) at the -25 deg tilt stop', 'accel_g': n_g, 'mass_g': m_g,
            'balls_g': BALLS * BALL_G, 'lid_g': HOPPER_LID_G, 'force_n': f, 'sf': SF_RETENTION,
            'required_n': SF_RETENTION * f,
            'source': 'hardware/cad/turret/turret_studies.py R-fall (FALL_G 30, the TM design load of docs/architecture/cad-plan.md section 5); '
                      'the hopper axis leans 25 deg at the stop (hardware/cad/turret/turret.py tilt_min)'}


def bay_load():
    """The bay lid's design load: R-fall's 30 g on the lid's own mass, along its normal (pan turns the bay to face any
    side, so a sideways fall can pull it straight off)."""
    f = BAY_LID_G / 1000 * G0 * FALL_G
    return {'case': 'R-fall sideways, along the lid\'s normal', 'accel_g': FALL_G, 'mass_g': BAY_LID_G,
            'force_n': f, 'sf': SF_RETENTION, 'required_n': SF_RETENTION * f,
            'source': 'hardware/cad/turret/turret_studies.py R-fall (FALL_G 30)'}


def hopper_inverted_load():
    """R-fall with the turret upside down: 30 g along the hopper's axis, the balls and the lid towards the lid."""
    m_g = BALLS * BALL_G + HOPPER_LID_G
    f = m_g / 1000 * G0 * FALL_G
    return {'case': 'R-fall up: upside down, 30 g along the hopper\'s axis towards the lid', 'accel_g': FALL_G,
            'mass_g': m_g, 'force_n': f, 'sf': SF_RETENTION, 'required_n': SF_RETENTION * f,
            'source': 'hardware/cad/turret/turret_studies.py R-fall (FALL_G 30)'}


INVERTED_REASON = ('excluded: the latches do not hold it, and need not. Upside down, the turret lands on its top: the '
                   'flap\'s hinge lugs on the lid and the flap between them, at every tilt from 0 to the -25 deg stop. '
                   'Every latch stands at least 1 mm below them there (FIRST_CONTACT_MARGIN; '
                   'tests/hardware/turret/test_turret_snaps.py test_no_latch_is_first_contact), so the ground pushes the lid on through '
                   'its lugs and its disc, not through a tongue, while the balls stop against it. That holds for a '
                   'square landing (no roll). Rolled about 4 deg or more, a side latch at 120 or 240 deg becomes the '
                   'top (the lugs sit about 12 mm off the roll axis, those latches about 48 mm), and an off-square '
                   'landing on it can break that latch: a printed part to replace, not a hazard. Left is a landing '
                   'with the lid hanging free (the robot on its back with the turret over an edge): a detent that '
                   'holds the case\'s load at the low bound pulls off at the high bound with a fixed multiple of it '
                   '(the modulus bounds x the friction bounds, docs/research/snap-fits/summary.json), over the 50 N a hand '
                   'gives; a lock with a release would be a tool or a catch to find on every refill. If it opens, 30 '
                   'foam rounds spill: no hazard, no damage, a refill.')


def load_cases(part):
    """Every load case the lid was weighed against: 'design' (the one its latches are sized for), 'included' (held,
    no more than the design case) and 'excluded' (not held, with the reason). docs/research/snap-fits/snaps.py checks
    each against the latches' retention."""
    if part == 'hopper_lid':
        return [dict(hopper_load(), status='design'),
                {'case': 'R-fall down: upright, 30 g along the hopper\'s axis away from the lid', 'status': 'included',
                 'force_n': 0.0, 'required_n': 0.0, 'basis': 'presses the balls onto the dial, away from the lid'},
                {'case': 'R-fall sideways with the barrel level (tilt 0)', 'status': 'included', 'force_n': 0.0,
                 'required_n': 0.0, 'basis': 'across the hopper\'s axis: the balls bear on the wall, not the lid'},
                {'case': 'recoil', 'status': 'included', 'force_n': 0.0, 'required_n': 0.0,
                 'basis': 'along the barrel, across the hopper\'s axis (0.039 N s a shot, '
                          'docs/research/turret-launcher-study.md)'},
                dict(hopper_inverted_load(), status='excluded', reason=INVERTED_REASON)]
    return [dict(bay_load(), status='design'),
            {'case': 'R-fall in any other direction', 'status': 'included', 'force_n': bay_load()['force_n'],
             'required_n': bay_load()['required_n'],
             'basis': 'the lid\'s own mass at 30 g: its component along the lid\'s normal is at most the design '
                      'case\'s (the bay holds no loose load against the lid)'}]


LOADS = {'hopper_lid': hopper_load, 'board_bay_lid': bay_load}
LATCHES = {'hopper_lid': HOPPER, 'board_bay_lid': BAY}


def snap_name(part, mu):
    return f'{part}-latch-mu-{mu}'


def spec():
    """The cad-agent snapfit declaration: each latch twice, at the low and the high friction bound. The low row holds
    the retention minimum (the least the latch holds), the high row the mating maximum (the most a hand pushes); the
    pull-off at the high bound (not a row the toolkit checks) is checked in docs/research/snap-fits/snaps.py."""
    snaps = []
    for part, lat in LATCHES.items():
        load = LOADS[part]()
        for mu in ('low', 'high'):
            s = {'name': snap_name(part, mu), 'material': MATERIAL, 'process': PROCESS, 'orientation': ORIENTATION,
                 'repeated': True, 'design': 1, 'length_mm': lat['L'], 'undercut_mm': UNDERCUT,
                 'section': {'rect': {'width_mm': round(tongue_width(lat), 4), 'thickness_mm': lat['h']}},
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


HEADER = ('# The turret lids\' snap fits (#131 wave 1). Generated from hardware/cad/turret/turret_snaps.py, the constants hardware/cad/turret/turret.py\n'
          '# builds the latches from: do not edit; run python3 docs/research/snap-fits/snaps.py --cad-agent PATH.\n'
          '#   cad-agent snapfit docs/research/snap-fits/snaps.yaml --output docs/research/snap-fits/snapfit.json\n')


def yaml_text():
    """snaps.yaml, written without a YAML library (block style, one snap per list item) so the check runs anywhere."""
    lines = [HEADER.rstrip('\n'), 'snaps:']
    for s in spec()['snaps']:
        body = _emit(s, 4)
        body[0] = '  - ' + body[0][4:]
        lines += body
    return '\n'.join(lines) + '\n'
