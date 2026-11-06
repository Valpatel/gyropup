"""The turret lids' snap latches (#131 wave 1) in the CAD: they exist with the sizes docs/research/snap-fits/snaps.yaml
declares to cad-agent, each lid seats with no interference, each barb catches its ridge by the declared undercut
once the lid lifts past the play, and the controls (the lids as they were, the catch parts without ridges) hold
nothing. Also the backing behind the thin walls, the hopper lid's rotation key, the hopper-full beam's keep-out, the
mass bounds the loads use, the print orientations (no support on a latch), the coupons, the neighbours and the hopper
lid as the turret's top (the reason R-fall up is excluded).

    .venv/bin/python -m pytest tests/hardware/turret/test_turret_snaps.py -q
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))


import math
import sys
from pathlib import Path

import cadquery as cq
import pytest
import yaml
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer

HERE = (Path(__file__).resolve().parents[3] / 'hardware/cad')
sys.path.insert(0, str(HERE))
import hardware.cad.turret.turret as tu  # noqa: E402
import hardware.cad.turret.turret_snaps as ts  # noqa: E402

SPEC = (HERE.parents[1] / 'docs/research/snap-fits/snaps.yaml')
TOL = 0.02          # mm, for sizes read off the solids


def _valid(shape) -> bool:
    v = shape.val() if hasattr(shape, 'val') else shape
    return BRepCheck_Analyzer(v.wrapped, True).IsValid()


def _vol(a, b) -> float:
    return a.val().intersect(b.val()).Volume()


@pytest.fixture(scope='module')
def P():
    G = tu.Geo()
    return {'G': G, 'hopper_lid': tu.hopper_lid(G), 'hopper_lid_old': tu.hopper_lid(G, latches=False), 'hopper': tu.hopper(G),
            'board_bay_lid': tu.board_bay_lid(G), 'board_bay_lid_old': tu.board_bay_lid(G, latches=False), 'board_bay': tu.board_bay(G)}


@pytest.fixture(scope='module')
def spec():
    return {s['name']: s for s in yaml.safe_load(SPEC.read_text())['snaps']}


def _section_hopper(shape, ang, z0=-1e3, z1=1e3, r0=0.0, r1=200.0):
    """The part cut by a thin radial slab at angle ang (deg): (r min, r max, z min, z max) of what is there."""
    slab = tu.box(r0, r1, -0.005, 0.005, z0, z1).rotate((0, 0, 0), (0, 0, 1), ang)
    c = shape.val().intersect(slab.val())
    if c.Volume() < 1e-9:
        return None
    c = c.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), -ang)
    bb = c.BoundingBox()
    return bb.xmin, bb.xmax, bb.zmin, bb.zmax


def _pieces_angles(shape, r, z0, z1):
    """The angular extents (deg) of the material a thin ring at radius r cuts from the part between z0 and z1."""
    ring = tu.ring_z(r + 0.005, r - 0.005, z0, z1)
    out = []
    for s in shape.val().intersect(ring.val()).Solids():
        a = sorted(math.degrees(math.atan2(v.Y, v.X)) % 360.0 for v in s.Vertices())
        out.append((a[0], a[-1]))
    return sorted(out)


def _measure_hopper(P):
    G, lid, hop = P['G'], P['hopper_lid'], P['hopper']
    r_w, z1 = G.dial_wall_r + tu.HOPPER_WALL, G.hopper_top
    a = tu.hopper_latch_angles(G)[1]                                     # at 120 deg: no wrap at 0
    mid = (a['root'] + a['barb']) / 2
    ri, ro, zb, zt = _section_hopper(lid, mid, r0=r_w + 0.5)                   # the tongue, clear of the disc's rim (0.4)
    pieces = [p for p in _pieces_angles(lid, r_w + 0.25, z1 - ts.HOPPER['s_hi'] + 0.1, z1 - 0.1)
              if a['start'] - 1.0 <= p[0] and p[1] <= a['end'] + 1.0]
    root_face, barb = pieces[0][1], pieces[1]
    r_mid = r_w + ts.TONGUE_N + ts.HOPPER['h'] / 2
    tip = _section_hopper(lid, a['barb'], z1=z1 - 0.1, r0=r_w + 0.01)[0]       # the barb's tip
    ridge = _section_hopper(hop, a['barb'], z1=z1 - 0.01, r0=r_w + 0.001)[1]  # the ridge's top
    return {'h': ro - ri, 'b': zt - zb, 'L': math.radians((barb[0] + barb[1]) / 2 - root_face) * r_mid, 'u': ridge - tip,
            'tongue_n': ri - r_w, 'barb_w': math.radians(barb[1] - barb[0]) * r_mid}


def _measure_bay(P):
    lid, bay = P['board_bay_lid'], P['board_bay']
    Y, z1 = tu.TB['y_out'], tu.TB['z'][1]
    x = tu.bay_latch_x(P['G'])
    xm = sum(x['tongue']) / 2
    c = lid.val().intersect(tu.box(xm - 0.005, xm + 0.005, -200, 0, z1 + 0.3, z1 + 20).val()).BoundingBox()
    probe = tu.box(-40, 40, -Y - 0.1, -Y + 20, z1 + 0.245, z1 + 0.255)
    pieces = sorted((s.BoundingBox().xmin, s.BoundingBox().xmax) for s in lid.val().intersect(probe.val()).Solids())
    root_face, barb = pieces[0][1], pieces[-1]
    xb = sum(x['barb']) / 2
    tip = lid.val().intersect(tu.box(xb - 0.005, xb + 0.005, -Y + 0.01, 0, z1 + 0.01, z1 + 20).val()).BoundingBox().zmin
    ridge = bay.val().intersect(tu.box(xb - 0.005, xb + 0.005, -200, 0, z1 + 0.001, z1 + 20).val()).BoundingBox().zmax
    return {'h': c.zlen, 'b': c.ylen, 'L': (barb[0] + barb[1]) / 2 - root_face, 'u': ridge - tip, 'tongue_n': c.zmin - z1,
            'barb_w': barb[1] - barb[0]}


# ------------------------------------------------------------------------------------------------ the latches exist

def test_constants_match_the_cad(P):
    G = P['G']
    assert ts.HOPPER_WALL_R == pytest.approx(G.dial_wall_r + tu.HOPPER_WALL, abs=1e-9)
    rot = {m[0]: m[5] for m in tu.MADE}
    for part, pr in ts.PRINT.items():
        want = None if pr['rotation'] is None else (tuple(pr['rotation'][0]), pr['rotation'][1])
        assert rot[part] == want, part
    # the spigot (the hopper's backing) is BACKING_DEPTH deep: the old lid has nothing else under its disc
    assert P['hopper_lid_old'].val().BoundingBox().zmin == pytest.approx(G.hopper_top - ts.BACKING_DEPTH, abs=1e-6)


@pytest.mark.parametrize('part', ['hopper_lid', 'board_bay_lid'])
def test_the_cad_is_what_cad_agent_checked(P, spec, part):
    """Every size of snaps.yaml read off the solids: the tongue's length to the barb's centre, its thickness and
    width, the undercut between the barb's tip and the ridge's top, and the root's fillet."""
    m = _measure_hopper(P) if part == 'hopper_lid' else _measure_bay(P)
    lat = ts.LATCHES[part]
    for mu in ('low', 'high'):
        s = spec[ts.snap_name(part, mu)]
        assert m['h'] == pytest.approx(s['section']['rect']['thickness_mm'], abs=TOL)
        assert m['b'] == pytest.approx(s['section']['rect']['width_mm'], abs=TOL)
        assert m['u'] == pytest.approx(s['undercut_mm'], abs=TOL)
        # the probe sits 1.25 mm inside the tongue's face, where the 0.6 h root fillet still adds a few hundredths
        assert m['L'] == pytest.approx(s['length_mm'], abs=0.15)
        assert m['L'] <= s['length_mm'] + 1e-6
    assert m['tongue_n'] == pytest.approx(ts.TONGUE_N, abs=TOL)
    assert m['barb_w'] == pytest.approx(lat['barb_w'], abs=0.05)
    radii = [BRepAdaptor_Surface(f.wrapped).Cylinder().Radius() for f in P[part].faces().vals() if f.geomType() == 'CYLINDER']
    assert any(abs(r - lat['root_r']) < 1e-6 for r in radii), 'the root fillet is missing'


def test_each_lid_is_one_valid_solid(P):
    for name in ('hopper_lid', 'board_bay_lid', 'hopper', 'board_bay'):
        v = P[name].val()
        assert _valid(v) and len(v.Solids()) == 1, name
    assert len(P['board_bay_lid_old'].val().Solids()) == 2          # the lip used to float 0.01 mm off the plate


def test_latch_count(P):
    """Three barbs on the hopper lid, one on each of the bay lid's top and bottom edges: at the barb's tip, only the
    barbs and the root blocks reach in to the wall, and the barbs are the narrow pieces."""
    G = P['G']
    r_w, z1 = G.dial_wall_r + tu.HOPPER_WALL, G.hopper_top
    b = ts.profile()['barb']
    r_mid = r_w + ts.TONGUE_N + ts.HOPPER['h'] / 2
    pieces = _pieces_angles(P['hopper_lid'], r_w + 0.25, z1 - b[2][0] + 0.05, z1 - b[1][0] - 0.05)
    widths = [math.radians(a1 - a0) * r_mid for a0, a1 in pieces]
    assert sum(abs(w - ts.HOPPER['barb_w']) < 0.05 for w in widths) == ts.HOPPER['n']
    assert len(pieces) == 2 * ts.HOPPER['n']
    Y, z1b, z0b = tu.TB['y_out'], tu.TB['z'][1], tu.TB['z'][0]
    for z in (z1b + 0.25, z0b - 0.25):
        s = P['board_bay_lid'].val().intersect(tu.box(-40, 40, -Y + b[1][0] + 0.05, -Y + b[2][0] - 0.05, z - 0.005, z + 0.005).val()).Solids()
        assert sum(abs(x.BoundingBox().xlen - ts.BAY['barb_w']) < 0.05 for x in s) == 1 and len(s) == 2


# ------------------------------------------------------------------------------------------------ closing and holding

@pytest.mark.parametrize('lid,catch,up', [('hopper_lid', 'hopper', (0, 0, 1)), ('board_bay_lid', 'board_bay', (0, -1, 0))])
def test_closed_and_caught(P, lid, catch, up):
    """Closed: no interference. Lifted less than the play: still none. Lifted past it: each barb is in its ridge, by
    the undercut (radially / in z) and nowhere else."""
    L, C = P[lid], P[catch]
    assert _vol(L, C) == 0.0
    lift = lambda d: L.translate(tuple(d * c for c in up))
    assert _vol(lift(ts.PLAY - 0.05), C) == 0.0
    hit = lift(ts.PLAY + 0.15).val().intersect(C.val())
    assert hit.Volume() > 0.05
    n = ts.LATCHES[lid]['n']
    assert len(hit.Solids()) == n, 'every latch catches'
    G = P['G']
    for s in hit.Solids():
        bb = s.BoundingBox()
        if lid == 'hopper_lid':
            rs = [math.hypot(v.X, v.Y) for v in s.Vertices()]
            r_w = G.dial_wall_r + tu.HOPPER_WALL
            assert min(rs) >= r_w + ts.WALL_CLEAR - 1e-6 and max(rs) <= r_w + ts.RIDGE_H + 1e-6
        else:
            z1, z0 = tu.TB['z'][1], tu.TB['z'][0]
            n_out = bb.zmin - z1 if bb.zmin > (z0 + z1) / 2 else z0 - bb.zmax
            assert n_out >= ts.WALL_CLEAR - 1e-6 and bb.zlen <= ts.UNDERCUT + 1e-6


def test_controls_hold_nothing(P):
    """The lids as they were hold nothing: lifted, they meet no part of the hopper or the bay. Without the ridges,
    the new lids hold nothing either."""
    G = P['G']
    for lid, catch, up in (('hopper_lid_old', 'hopper', (0, 0, 1)), ('board_bay_lid_old', 'board_bay', (0, -1, 0))):
        for d in (ts.PLAY + 0.15, 1.0, 3.0):
            assert _vol(P[lid].translate(tuple(d * c for c in up)), P[catch]) == 0.0, (lid, d)
    bare_hopper = P['hopper'].cut(tu.hopper_ridges(G))
    bare_bay = P['board_bay'].cut(tu.bay_ridges(G))
    assert _vol(P['hopper_lid'].translate((0, 0, ts.PLAY + 0.15)), bare_hopper) == 0.0
    assert _vol(P['board_bay_lid'].translate((0, -(ts.PLAY + 0.15), 0)), bare_bay) == 0.0


def test_walls_are_backed(P):
    """Behind each ridge the lid backs the thin wall: the hopper lid's spigot over the ridge's height, a pad on the bay
    lid's lip behind each of the bay's ridges."""
    G = P['G']
    s0, s1 = ts.profile()['ridge_s']
    assert ts.BACKING_DEPTH >= s1
    z1 = G.hopper_top
    for a in tu.hopper_latch_angles(G):
        sec = _section_hopper(P['hopper_lid'], a['barb'], z0=z1 - s1, z1=z1 - s0, r1=G.dial_wall_r)
        assert sec is not None and sec[1] == pytest.approx(G.dial_wall_r - 0.1, abs=1e-6)   # 0.1 inside the wall
        assert sec[2] <= z1 - s1 + 1e-6
    Y, (z0b, z1b), w = tu.TB['y_out'], tu.TB['z'], tu.TB['wall']
    x0, x1 = tu.bay_latch_x(G)['ridge']
    for xs, zface in (((x0, x1), z1b - w), ((-x1, -x0), z0b + w)):
        pad = tu.box(*xs, -Y + s0, -Y + s1, zface - 0.3, zface) if zface > 100 else tu.box(*xs, -Y + s0, -Y + s1, zface, zface + 0.3)
        assert _vol(pad, P['board_bay_lid']) == pytest.approx(pad.val().Volume(), rel=1e-6)


def test_the_hopper_full_beam_keeps_clear(P):
    """Nothing of the latches or ridges within 8 deg of the hopper-full beam's holes (90 and 270 deg), where its
    emitter and receiver sit outside the wall."""
    G = P['G']
    r_w = G.dial_wall_r + tu.HOPPER_WALL
    for c in (90.0, 270.0):
        keep = tu.sector_z(r_w + 0.01, 70.0, c - 8.0, c + 8.0, G.hopper_top - ts.HOPPER['s_hi'] - 5.0, G.hopper_top + 12.0)
        assert _vol(keep, P['hopper_lid']) == pytest.approx(_vol(keep, P['hopper_lid_old']), abs=1e-6)   # the disc's rim only
        assert _vol(keep, P['hopper']) == 0.0


def test_mass_bounds(P):
    G = P['G']
    d = ts.PETG_DENSITY / 1000
    lid = (P['hopper_lid'].val().Volume() + tu.hopper_flap(G).val().Volume()) * d + 1.0
    assert lid <= ts.HOPPER_LID_G < lid + 2.0
    bay = P['board_bay_lid'].val().Volume() * d
    assert bay <= ts.BAY_LID_G < bay + 1.0


def _rotate(v, axis, deg):
    """Rodrigues: v turned deg about the unit axis."""
    k = [a / math.sqrt(sum(c * c for c in axis)) for a in axis]
    t = math.radians(deg)
    cross = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]]
    dot = sum(a * b for a, b in zip(k, v))
    return [v[i] * math.cos(t) + cross[i] * math.sin(t) + k[i] * dot * (1 - math.cos(t)) for i in range(3)]


def test_print_orientation(P):
    """In each lid's print rotation the closing direction is the print's z, so the tongues (across it) lie in the
    bed plane and bend along the layers; the catch parts print with it vertical too."""
    rot = {m[0]: m[5] for m in tu.MADE}
    closing = {'hopper_lid': (0, 0, -1), 'hopper': (0, 0, -1), 'board_bay_lid': (0, 1, 0), 'board_bay': (0, 1, 0)}
    for part, v in closing.items():
        r = rot[part]
        w = v if r is None else _rotate(v, r[0], r[1])
        assert abs(abs(w[2]) - 1.0) < 1e-9, part
    # the bay lid lies on its plate; the hopper lid stands on the flap's hinge lugs alone (the latches' tops are
    # LATCH_DROP below them), so the print plan supports its disc and the latches' tops
    bed = lambda part: tu._print_pose(P[part], rot[part]).val().intersect(tu.box(-200, 200, -200, 200, -0.001, 0.01).val()).Volume()
    assert bed('board_bay_lid') > 20.0
    import hardware.cad.turret.turret_print as turret_print
    plan = {p[0]: p for p in turret_print.PARTS}
    lugs = 2 * 6.0 * 3.0 * 0.011
    assert 0.5 * lugs < bed('hopper_lid') < 1.01 * lugs and plan['hopper_lid'][5] is True     # the lugs alone
    assert plan['board_bay_lid'][5] is False and plan['board_bay'][5] is False and plan['hopper'][5] is False


def _posed_with(part_shape, piece, rot):
    """piece moved as part_shape is by _print_pose (turned by rot, then set on the bed)."""
    if rot:
        part_shape, piece = (s.rotate((0, 0, 0), rot[0], rot[1]) for s in (part_shape, piece))
    bb = part_shape.val().BoundingBox()
    return piece.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def _downward_faces(shape, steep=0.7):
    """(z min, z max, normal z) of the faces that look down more steeply than 45 deg from the vertical (these need
    support unless they lie on the bed)."""
    out = []
    for f in shape.val().Faces():
        nz = f.normalAt(f.Center()).z
        if nz < -steep:
            bb = f.BoundingBox()
            out.append((bb.zmin, bb.zmax, nz))
    return out


def test_the_bay_latch_prints_without_support(P):
    """In the bay lid's print pose every face of its latch that looks down lies on the bed. The barbs' return faces
    look down 30 deg from the vertical and print without."""
    rot = {m[0]: m[5] for m in tu.MADE}['board_bay_lid']
    down = _downward_faces(_posed_with(P['board_bay_lid'], tu.bay_latch(P['G']), rot))
    assert down and all(z1 < 1e-6 for z0, z1, nz in down), down


def test_supports_meet_only_the_hopper_latches_tops(P):
    """The hopper lid prints upside down on its lugs, the latches' tops LATCH_DROP above the bed. The only faces of a
    latch that look down and need support are those tops, flat at that height: the tongues' and root blocks' edges
    across the tongue's width. The faces the pull bends (the tongue's inner and outer faces) are vertical in the print
    and meet no support."""
    G = P['G']
    rot = {m[0]: m[5] for m in tu.MADE}['hopper_lid']
    for a in tu.hopper_latch_angles(G):
        down = _downward_faces(_posed_with(P['hopper_lid'], tu.hopper_latch(G, a), rot))
        assert down and all(nz < -0.999 and z0 == pytest.approx(ts.LATCH_DROP, abs=1e-3) and z1 == pytest.approx(ts.LATCH_DROP, abs=1e-3)
                            for z0, z1, nz in down), down


# ------------------------------------------------------------------------------------------------ the rotation key

def test_the_lid_goes_on_one_way(P):
    """Seated as built, the key's tab sits in the hopper's notch with no interference. Turned any other way (every
    10 deg, the 120 and 240 where its latches line up with the ridges among them) the lid meets the hopper (the tab on
    the rim, and off the ridges' angles the root blocks on the ridges): it cannot seat. Control: without the tab the
    lid seats flush at 120 and 240 deg, latched with the fill port 120 deg off the spout."""
    G, lid, hop = P['G'], P['hopper_lid'], P['hopper']
    K = ts.KEY
    assert _vol(lid, hop) == 0.0
    tab, notch = tu.hopper_key(G)
    wall = tu.ring_z(G.dial_wall_r + tu.HOPPER_WALL, G.dial_wall_r, G.hopper_top - 10.0, G.hopper_top)
    assert _vol(tab, hop) == 0.0 and _vol(tab, wall) > 1.0          # in the wall's thickness, where the notch is
    turn = lambda s, deg: s.rotate((0, 0, 0), (0, 0, 1), deg)
    for deg in range(30, 360, 30):
        assert _vol(turn(tab, deg), hop) > 1.0, deg                 # the tab alone lands on the rim
    for deg in range(10, 360, 10):
        assert _vol(turn(lid, deg), hop) > 1.0, deg
    bare = tu.hopper_lid(G, key=False)
    for deg in (120, 240):
        assert _vol(turn(bare, deg), hop) == 0.0, deg
    # the tab stays inside the wall's outer face; the front latch's tongue passes outside the notch, clear of it
    assert math.hypot(K['r_out'], K['w'] / 2) < G.dial_wall_r + tu.HOPPER_WALL
    front = tu.hopper_latch(G, tu.hopper_latch_angles(G)[0])
    assert _vol(front, notch) == 0.0 and _vol(front, tab) == 0.0


def _latch_clearance(turret, hopper):
    """For each tilt from 0 to the -25 deg stop: how far the highest hopper latch (built from hopper, a
    turret_snaps.HOPPER) stands below the top of everything else on the posed turret, upside down (the turret's top is
    what it lands on: z up here is down there)."""
    G = turret.G
    frame = next(m[2] for m in tu.MADE if m[0] == 'hopper_lid')
    old, hopper = dict(ts.HOPPER), dict(hopper)
    try:
        ts.HOPPER.clear(); ts.HOPPER.update(hopper)
        lid = tu.hopper_lid(G, latches=False)
        latches = [tu.hopper_latch(G, a) for a in tu.hopper_latch_angles(G)]
    finally:
        ts.HOPPER.clear(); ts.HOPPER.update(old)
    out = {}
    for tilt in [0.0] + [-2.5 * i for i in range(1, int(round(-G.tilt_min / 2.5)) + 1)]:
        posed = turret.posed(0.0, tilt, robot=False)
        rest = max([s.val().BoundingBox().zmax for k, s in posed.items() if k != 'hopper_lid']
                   + [turret.pose_shape(lid, frame, 0.0, tilt, robot=False).val().BoundingBox().zmax])
        top = max(turret.pose_shape(s, frame, 0.0, tilt, robot=False).val().BoundingBox().zmax for s in latches)
        out[tilt] = rest - top
    return out


def test_no_latch_is_first_contact(turret):
    """R-fall up is excluded because upside down the turret lands on its top (cad/turret_snaps.py INVERTED_REASON):
    at every tilt from 0 to the -25 deg stop, every hopper latch (tongue, root block and barb) stands at least
    FIRST_CONTACT_MARGIN below the rest of the turret, so the lugs and the flap meet the ground and the lid is pushed
    on, never a tongue. Control: the latches as reviewed at fa7e3c4 (one at the back, up to the lugs' height) are the
    turret's top at the stop."""
    now = _latch_clearance(turret, ts.HOPPER)
    assert -turret.G.tilt_min in [-t for t in now] and all(v >= ts.FIRST_CONTACT_MARGIN for v in now.values()), now
    then = _latch_clearance(turret, ts.FA7E3C4)
    assert then[turret.G.tilt_min] < -5.0 and min(then.values()) <= 0.0, then


def test_coupons(P):
    """One coupon per lid's latch and per catch, cut from the parent, in its print orientation, on the bed, within it;
    the latch coupons keep the whole latch."""
    G = P['G']
    cps = tu.snap_coupons(G)
    regions = tu.snap_coupon_regions(G)
    assert set(cps) == {f'coupon_{n}' for n in ('hopper_lid', 'hopper', 'board_bay_lid', 'board_bay')}
    for name, s in cps.items():
        v = s.val()
        bb = v.BoundingBox()
        part = name[len('coupon_'):]
        assert _valid(v) and len(v.Solids()) == 1, name
        assert bb.zmin == pytest.approx(0.0, abs=1e-6) and max(bb.xlen, bb.ylen) < min(tu.BED), name
        assert v.Volume() == pytest.approx(_vol(P[part], regions[part]), rel=1e-6), name
    a = tu.hopper_latch_angles(G)[0]
    latch = tu.hopper_latch(G, a)
    assert _vol(latch, regions['hopper_lid']) == pytest.approx(latch.val().Volume(), rel=1e-6)
    latch = tu.bay_latch(G)
    assert _vol(latch, regions['board_bay_lid']) == pytest.approx(latch.val().Volume(), rel=1e-6)


# ------------------------------------------------------------------------------------------------ the neighbours

@pytest.fixture(scope='module')
def turret():
    return tu.Turret({'bodyTop': 100.0})


def _boxes_meet(a, b, pad=0.0):
    return not (a.xmax + pad < b.xmin or b.xmax + pad < a.xmin or a.ymax + pad < b.ymin or b.ymax + pad < a.ymin
                or a.zmax + pad < b.zmin or b.zmax + pad < a.zmin)


def test_no_new_clash(turret):
    """The latched lids and the ridged parts stand clear of every other turret part over the pan and the tilt's range
    (their mates touch only at the seats: zero volume)."""
    names = ('hopper_lid', 'hopper', 'board_bay_lid', 'board_bay')
    for pan in (0.0, 90.0, 180.0, 270.0):
        for tilt in (0.0, -25.0):
            posed = turret.posed(pan, tilt, robot=False)
            for n in names:
                a = posed[n].val()
                ab = a.BoundingBox()
                for m, s in posed.items():
                    if m == n or (m in names and names.index(m) < names.index(n)):
                        continue
                    b = s.val()
                    if not _boxes_meet(ab, b.BoundingBox()):
                        continue
                    assert a.intersect(b).Volume() < 1e-6, f'{n} x {m} at pan {pan}, tilt {tilt}'
