"""The turret's design gates, on cad-agent's integrity gates (cadagent.gates, docs/gates.md in the toolkit): a model
that is not physically coherent fails the build instead of reaching a page.

    connectivity  cadagent.gates.connectivity on the whole turret at home (pan 0, tilt 0), the settled hopper load in
                  it: every part grounded through contacts, declared fasteners and joints that are measured to hold;
                  each moving body (pan, pinion, tilt, dial, each flywheel, the fill flap) hangs on its joint; no
                  floating part. The relation table under it is cached (.cadagent-cache/gates, or $CADAGENT_GATE_CACHE).
    hopper        cadagent.gates.containment: the 30 balls of the physics-settled pile (sim/turret_feed.py --pile,
                  exports/turret/feed/pile.json) inside the hopper's registered @cavity, none in a wall, none in
                  another ball, each resting on the cavity or a ball below it.
    path          cadagent.gates.containment: a design ball every 2 mm from the exit pocket round the chute, through
                  the nip and the barrel to the muzzle, each inside the path's @cavity (the ball's free space; the
                  tyres squeeze the ball by design, so they are not cut from it).
    sweep         the relation table on the posed turret: the hopper's balls against every part that moves relative
                  to them (base, pinion, pan) at 8 pans x 5 tilts: no shared volume.
    ammo_range    D67: the biggest accepted round (22.8 mm) through the same two containment checks, and the smallest
                  (22.2 mm) still one to a pocket and still squeezed at the nip; the bore's play for both.

Each gate writes a cadagent verdict (schema cadagent.gate/1) to exports/turret/gates/<gate>.json (connectivity also
a Graphviz .dot); exports/turret/gates.json holds the summary with a fingerprint of what they depend on (the CAD, the
pile and the toolkit's gate code), which cad/build_turret_box.py reads.

Frames: the assembly is the T frame (mm, mount face z = 0, robot=False) with every part placed by its build frame's
rigid motion (Turret.pose_shape as a gp_Trsf), so a pose only changes placements and the pair cache stays warm.

    .venv/bin/python cad/turret_gates.py          (exit 1 when a gate fails)
    .venv/bin/python cad/turret_gates.py --dossier   (path + ammo range for cad-agent check: exports/gates/turret-*.json)
    gp-remote --host gb10-02 --pull exports/turret/gates.json --pull exports/turret/gates/ -- \\
        env CADAGENT_GATE_CACHE=$HOME/gyropup-compute/cache/turret-gates python -u cad/turret_gates.py
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import cadquery as cq
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from cadagent.gates import Assembly, Check, PairCache, Tolerances, relation_table, verdict, write_verdict
from cadagent.gates.connectivity import Declarations, connectivity_gate as ca_connectivity_gate
from cadagent.gates.containment import containment_gate
from cadagent.gates.fasteners import FastenerOptions, FastenerSpec, fastener_gate
from cadagent.gates.motion import motion_gate

sys.path.insert(0, str(Path(__file__).resolve().parent))
import turret as tu  # noqa: E402

R = Path(__file__).resolve().parents[1]
PILE = R / 'exports' / 'turret' / 'feed' / 'pile.json'
LAUNCH = R / 'exports' / 'turret' / 'launch' / 'launch3d.json'      # sim/turret_launch3d.py: the speed ceiling's corners
OUT = R / 'exports' / 'turret' / 'gates.json'
VERDICTS = R / 'exports' / 'turret' / 'gates'
CACHE = Path(os.environ.get('CADAGENT_GATE_CACHE') or (R / '.cadagent-cache' / 'gates'))


class GateFailure(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------ declarations

# moving bodies: the build frame says most of it (base is the static frame); these split the tilt frame's turning parts
TILT_MOVERS = {'dial': 'dial', 'flywheel': 'wheel_l', 'flywheel_tyre': 'wheel_l', 'flywheel_m': 'wheel_r',
               'flywheel_tyre_m': 'wheel_r', 'hopper_flap': 'flap'}
TILT_FAMILY = ('tilt', 'dial', 'wheel_l', 'wheel_r', 'flap')
GROUNDED = ['compute_tray']                  # the plinth's floor, bolted to the head's TM face (or the stand)
FREE = {'ball': 'a loose round: the settled hopper load (sim/turret_feed.py --pile), held by the hopper\'s cavity',
        'dt_plug': 'the robot\'s harness plug: a separate cable, plugged into the receptacle (absent on the stand)'}
# one bought part drawn as two solids for colour: merged into one node for the gates (a disjoint two-solid compound)
MERGED = {'slip_ring_rotor': ['ring_leads_rotor']}
# the joints between moving bodies (cadagent: moving instance held by its fixed instance within 1 mm, or within the
# clearance of the interface with the joint's id)
JOINTS = {
    'pan': {'kind': 'revolute', 'moving': 'pan_bearing_inner', 'fixed': 'pan_bearing',
            'how': 'the 61810 pan bearing: outer race in the base, inner race on the turntable'},
    'slip_ring': {'kind': 'revolute', 'moving': 'slip_ring_rotor', 'fixed': 'slip_ring',
                  'how': 'the slip ring\'s own rotor in its stator', 'intended_contacts': [['ring_coupling', 'slip_ring']]},
    'pan_drive': {'kind': 'revolute', 'moving': 'pan_pinion', 'fixed': 'pan_servo',
                  'how': 'the pinion on the pan servo\'s horn'},
    'tilt': {'kind': 'revolute', 'moving': 'tilt_bearing_inner', 'fixed': 'tilt_bearing',
             'how': 'the 126 tilt bearing: outer race in the yoke, inner race on the shoulder screw',
             'intended_contacts': [['shoulder_screw', 'tilt_yoke'], ['shoulder_screw', 'tilt_bearing']]},
    'tilt_drive': {'kind': 'revolute', 'moving': 'horn_boss', 'fixed': 'tilt_servo',
                   'how': 'the tilt servo\'s horn on the cradle\'s horn boss'},
    'feed': {'kind': 'revolute', 'moving': 'dial', 'fixed': 'feed_motor', 'how': 'the dial on the feed servo\'s horn'},
    'wheel_l': {'kind': 'revolute', 'moving': 'flywheel', 'fixed': 'flywheel_motor_l',
                'how': 'the left flywheel on its X2216\'s prop adapter'},
    'wheel_r': {'kind': 'revolute', 'moving': 'flywheel_m', 'fixed': 'flywheel_motor_r',
                'how': 'the right flywheel on its X2216\'s prop adapter'},
    'flap': {'kind': 'revolute', 'moving': 'hopper_flap', 'fixed': 'hopper_lid',
             'how': 'the fill flap on its Ø2 hinge pin in the lid\'s lugs'},
}
INTERFACES = [
    {'id': 'mesh', 'between': ['pan_pinion', 'pan_ring'], 'kind': 'gear', 'clearance': 0.5,
     'note': 'the m1.25 mesh, 0.15 mm backlash a flank'},
    {'id': 'pan', 'between': ['pan_bearing_inner', 'pan_bearing'], 'kind': 'revolute'},
    {'id': 'slip_ring', 'between': ['slip_ring_rotor', 'slip_ring'], 'kind': 'revolute'},
    {'id': 'pan_drive', 'between': ['pan_pinion', 'pan_servo'], 'kind': 'revolute'},
    {'id': 'tilt', 'between': ['tilt_bearing_inner', 'tilt_bearing'], 'kind': 'revolute'},
    {'id': 'tilt_drive', 'between': ['horn_boss', 'tilt_servo'], 'kind': 'revolute'},
    {'id': 'feed', 'between': ['dial', 'feed_motor'], 'kind': 'revolute'},
    {'id': 'wheel_l', 'between': ['flywheel', 'flywheel_motor_l'], 'kind': 'revolute'},
    {'id': 'wheel_r', 'between': ['flywheel_m', 'flywheel_motor_r'], 'kind': 'revolute'},
    {'id': 'flap', 'between': ['hopper_flap', 'hopper_lid'], 'kind': 'revolute'},
]
# the pile from MuJoCo settles with soft contacts: whole balls sit up to 0.15 mm into a wall or a neighbour (a foam
# round squashes far more than that under its own weight). The hopper's containment reads contact at 0.2 mm and allows
# 1 mm^3 (a 0.12-0.15 mm cap on a Ø22.7 ball; the old gate's limit) outside the cavity or shared; 0.2 mm^3 of
# integration noise against the 35,600 mm^3 hopper (a 0.16 mm^3 mismatch read 'unknown')
PILE_TOL = Tolerances(touch_mm=0.2, overlap_mm3=1.0, contain_mm3=1.0, volume_check_mm3=0.2)
GEOM_TOL = Tolerances()                      # everything placed by geometry: cadagent's defaults
CONNECT_TOL = Tolerances(touch_mm=0.05, volume_check_mm3=0.2)    # parts drawn on their seats: 0.05 mm reads as touching;
#                                       0.2 mm3 of integration noise on curved booleans (a tapped ring; a ball on the hopper)
AMMO_D = (22.2, 22.8)          # D67: any Rival-compatible round 22.2-22.8 mm (1.6-2.0 g: the mass is the launch ceiling's)


def geometry_fingerprint():
    """What the gates depend on: the CAD source, the settled pile and the toolkit's gate code. A stored result is
    current when this matches."""
    import cadagent.gates as cg
    h = hashlib.sha256()
    gdir = Path(cg.__file__).parent
    for f in [R / 'cad' / 'turret.py', Path(__file__), PILE, LAUNCH] + sorted(gdir.glob('*.py')):
        h.update(f.read_bytes() if f.exists() else b'-')
    return h.hexdigest()[:16]


# ------------------------------------------------------------------------------------------------ frames as rigid motions

def _rot(p, d, deg):
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(*p), gp_Dir(*d)), math.radians(deg))
    return t


def _tr(v):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*v))
    return t


def _mul(*ts):
    """ts[0] * ts[1] * ...: the last is applied first."""
    out = gp_Trsf()
    for t in ts:
        out = out.Multiplied(t)
    return out


def motion(G, frame, pan=0.0, tilt=0.0):
    """The rigid motion of a build frame from home (pan 0, tilt 0) to (pan, tilt), in the T frame (robot=False):
    what Turret.pose_shape does beyond the home placement."""
    if frame == 'pinion':
        x, y = G.servo_pan_xy
        return _rot((x, y, 0), (0, 0, 1), -pan * G.gear['z_ring'] / G.gear['z_pinion'])
    if frame == 'pan':
        return _rot((0, 0, 0), (0, 0, 1), pan)
    if frame == 'tilt':
        return _mul(_rot((0, 0, 0), (0, 0, 1), pan), _rot((0, 0, G.tilt_t), (0, 1, 0), -tilt))
    return gp_Trsf()


def home(G, frame):
    """The home placement of a build frame in T (the tilt frame's C origin sits at (-tilt_x, 0, path_t))."""
    return _tr((-G.tilt_x, 0, G.path_t)) if frame == 'tilt' else gp_Trsf()


def _solid(s):
    return s.val() if hasattr(s, 'val') else s


def sphere(r):
    """A whole ball. (CadQuery's makeSphere defaults to angles 0..90, the upper hemisphere: the turret's old gates
    (cad/gates.py, before 2026-10-28) checked half balls that way, and the support check found it.)"""
    return cq.Solid.makeSphere(r, cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), -90, 90, 360)


def rot_z(p, deg):
    a = math.radians(deg)
    return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a), p[2])


# ------------------------------------------------------------------------------------------------ the pile and the path

def load_pile(G):
    """The settled hopper (pile.json): pockets in the dial's frame at its zero, the pile in C; the park angle."""
    if not PILE.exists():
        raise GateFailure(f'no settled pile: run gp-remote --pull exports/turret/feed/ -- python sim/turret_feed.py --pile ({PILE})')
    d = json.loads(PILE.read_text())
    if abs(d['ball_d_mm'] - G.ball) > 1e-6 or len(d['pockets']) + len(d['pile']) != d['balls']:
        raise GateFailure('pile.json is for another ball or lost balls: rerun sim/turret_feed.py --pile')
    return d


def hopper_balls(pile):
    """The 30 ball centres in C: the pockets turned to the park angle, then the pile."""
    return [rot_z(p, pile['park_deg']) for p in pile['pockets']] + [tuple(p) for p in pile['pile']]


def ball_path(G, step=2.0):
    """The ball's centre from the exit pocket to the muzzle, every `step` mm (C frame): the chute's quarter bend from
    the pocket down to the path, then straight along it through the nip and the barrel."""
    pts = []
    n = max(2, int(math.ceil(G.chute_r * math.pi / 2 / step)))
    for k in range(n + 1):
        th = math.pi + k * (math.pi / 2) / n
        pts.append((G.chute_cx + G.chute_r * math.cos(th), 0.0, G.chute_r + G.chute_r * math.sin(th)))
    x = G.chute_cx + step
    while x <= G.barrel_x1 - G.ball / 2:
        pts.append((x, 0.0, 0.0))
        x += step
    return pts


def _cut_all(env, solids):
    bb = env.BoundingBox()
    for s in solids:
        sb = s.BoundingBox()
        if sb.xmin > bb.xmax or sb.xmax < bb.xmin or sb.ymin > bb.ymax or sb.ymax < bb.ymin or sb.zmin > bb.zmax or sb.zmax < bb.zmin:
            continue
        env = env.cut(s)
    return env.clean()


def hopper_cavity(T, dial_deg):
    """The hopper's free space in C: the Ø(dial wall) cylinder from the housing floor to the lid's underside, less every
    tilt-frame solid in it (the dial at dial_deg with its cone and fins, the baffle, the lid's spigot)."""
    G = T.G
    env = _solid(tu.cyl_z(G.dial_wall_r, G.floor_z, G.hopper_top))
    return _cut_all(env, [_solid(s) for s in tilt_local(T, dial_deg).values()])


def path_cavity(T):
    """The ball's free space from the exit pocket to the muzzle in C: turret.ball_path (the drop, the chute, the path
    to the nip at ball + 1.5 and on to the socket at ball + 2.0) and the barrel's bore to its end, less every tilt-frame
    solid except the flywheels and their tyres (they squeeze the ball by design), the dial at its zero (a pocket over
    the exit hole, as it stands while a ball drops)."""
    G = T.G
    env = _solid(tu.ball_path(G)).fuse(_solid(tu.cyl_x(G.br_out, G.socket_x0, G.barrel_x1)))
    keep = ('flywheel', 'flywheel_tyre', 'flywheel_m', 'flywheel_tyre_m')
    return _cut_all(env, [_solid(s) for n, s in tilt_local(T, 0.0).items() if n not in keep])


def tilt_local(T, dial_deg=0.0):
    """Every part of the tilt frame in C (the second flywheel and tyre mirrored), the dial turned by dial_deg."""
    out = {}
    for n, fr in T.frame.items():
        if fr != 'tilt':
            continue
        s = T.local[n]
        out[n] = s.rotate((0, 0, 0), (0, 0, 1), dial_deg) if (n == 'dial' and dial_deg) else s
        if n in ('flywheel', 'flywheel_tyre'):
            out[n + '_m'] = s.mirror('XZ')
    return out


# ------------------------------------------------------------------------------------------------ the assembly

def parts_local(T, dial_deg):
    """{name: (local shape, build frame)}: every part, the mirrored flywheel pair added, the rotor's leads merged
    into the rotor (MERGED), the dial at dial_deg."""
    out = {}
    for n, fr in T.frame.items():
        s = T.local[n]
        if n == 'dial' and dial_deg:
            s = s.rotate((0, 0, 0), (0, 0, 1), dial_deg)
        out[n] = (s, fr)
        if n in ('flywheel', 'flywheel_tyre'):
            out[n + '_m'] = (s.mirror('XZ'), fr)
    for into, extra in MERGED.items():
        sh = [_solid(out[into][0])] + [_solid(out.pop(e)[0]) for e in extra]
        out[into] = (cq.Compound.makeCompound(sh), out[into][1])
    return out


def body_of(name, frame):
    return TILT_MOVERS.get(name, frame)


def build_assembly(T, pile=None, dial_deg=0.0, balls=True, ball_d=None, bodies=None):
    """The turret at home in T: every part placed by its frame, the hopper's cavity registered on the hopper, and the
    settled pile as instances ball#0.. (the pockets with the dial, the rest with the tilt frame)."""
    G = T.G
    asm = Assembly()
    for n, (s, fr) in parts_local(T, dial_deg).items():
        asm.add(n, _solid(s), home(G, fr), body=(bodies or body_of)(n, fr), group=fr)
    asm.add_cavity('hopper_cavity', hopper_cavity(T, dial_deg), part='hopper', location=home(G, 'tilt'))
    if balls and pile is not None:
        r = (ball_d or G.ball) / 2
        np_ = len(pile['pockets'])
        for k, c in enumerate(hopper_balls(pile)):
            asm.add(f'ball#{k}', sphere(r), _mul(home(G, 'tilt'), _tr(c)), body='dial' if k < np_ else 'tilt', group='tilt')
    return asm


def declarations(asm):
    return Declarations(grounded=GROUNDED, free=FREE, interfaces=INTERFACES,
                        joints={k: {kk: vv for kk, vv in v.items() if kk != 'how'} for k, v in JOINTS.items()},
                        fasteners=connect_fasteners(), touch_mm=CONNECT_TOL.touch_mm,
                        contains=[{'what': 'ball', 'cavity': 'hopper_cavity', 'container': 'hopper', 'free': True}])


def connect_fasteners():
    """Fasteners that carry a part whose own solid touches nothing else that holds it (modelled solids: each must
    touch what it clamps and what it threads into)."""
    return {'laser_screws': {'clamps': 'laser', 'into': 'laser_mount'}}


# ------------------------------------------------------------------------------------------------ the gates

def connectivity(T, asm, cache):
    decl = declarations(asm)
    return ca_connectivity_gate(asm, decl, tol=CONNECT_TOL, cache=cache, out=VERDICTS / 'connectivity.json')


def hopper_gate(asm, cache, out='hopper.json', count=30):
    decl = [{'container': 'hopper', 'cavity': 'hopper_cavity', 'what': 'ball', 'count': count,
             'closed_by': ['cartridge_body', 'hopper_lid']}]
    # probe=False: the pile's balls touch the dial's cone and fins and each other everywhere (a physics settle), and the
    # surface probe against a cavity cut by every tilt-frame solid takes ~30 s a ball; PILE_TOL's 0.5 mm^3 already
    # accepts the settle's soft-contact penetration, which is deeper than what the probe exists to find
    # support 'report' (a warning): the settle itself is the stability proof (MuJoCo, friction 0.4-1.0, the slowest
    # ball 0.0009 m/s at rest); the static test only looks straight down, so a ball held in an arch by its neighbours'
    # friction reads as resting on nothing. support_mm 0.5: with PILE_TOL's 1 mm^3 a 0.05 mm drop is below the threshold
    return containment_gate(asm, decl, tol=PILE_TOL, cache=cache, support='report', support_mm=0.5, probe=False,
                            out=VERDICTS / out)


def path_assembly(T, ball_d):
    """The path check's own assembly: the cartridge and the barrel at home, the path's cavity on the cartridge body,
    and one ball at each path point (each its own declaration: neighbours 2 mm apart overlap by design)."""
    G = T.G
    asm = Assembly()
    loc = home(G, 'tilt')
    for n in ('cartridge_body', 'barrel'):
        asm.add(n, _solid(T.local[n]), loc, body='tilt', group='tilt')
    asm.add_cavity('path_cavity', path_cavity(T), part='cartridge_body', location=loc)
    names = []
    for k, c in enumerate(ball_path(G)):
        nm = f'path{k:03d}'
        asm.add(nm, sphere(ball_d / 2), _mul(loc, _tr(c)), body='tilt', group='tilt')
        names.append(nm)
    return asm, names


def path_gate(T, cache, ball_d, out):
    asm, names = path_assembly(T, ball_d)
    decl = [{'container': 'cartridge_body', 'cavity': 'path_cavity', 'what': n, 'count': 1, 'closed_by': ['barrel']}
            for n in names]
    return containment_gate(asm, decl, tol=GEOM_TOL, cache=cache, support='off', out=VERDICTS / out)


SWEEP_PANS = (0.0, 45.0, 90.0, 135.0, 180.0, -135.0, -90.0, -45.0)


def sweep_gate(T, asm, cache, pans=SWEEP_PANS, tilts=tu.SWEEP_TILTS):
    """The hopper's balls against every part that moves relative to them (the base, the pinion, the pan frame) at
    every pan and tilt: the relation table with only the balls queried, ball/ball and ball/tilt-family pairs skipped
    (the containment gate checks those)."""
    G = T.G
    balls = [n for n in asm if n.startswith('ball#')]
    tiltish = [n for n in asm if asm[n].body in TILT_FAMILY and not n.startswith('ball#')]
    skip = [(a, b) for i, a in enumerate(balls) for b in balls[i + 1:]] + [(a, b) for a in balls for b in tiltish]
    checks, stats = [], {'poses': 0, 'candidates': 0, 'kernel_queries': 0}
    for p in pans:
        for t in tilts:
            posed = asm
            for b in {asm[n].body for n in asm}:
                fr = 'tilt' if b in TILT_FAMILY else b
                if fr in ('pan', 'pinion', 'tilt'):
                    posed = posed.posed(b, motion(G, fr, p, t))
            tab = relation_table(posed, GEOM_TOL, cache=cache, only=balls, skip_pairs=skip)
            stats['poses'] += 1
            stats['candidates'] += tab.stats['candidates']
            stats['kernel_queries'] += tab.stats['kernel_queries']
            bad = [r for r in tab.interferences() if (r.a.startswith('ball#')) != (r.b.startswith('ball#'))]
            unk = [r for r in tab.by_state('unknown')]
            cid = f'sweep:pan{p:+.0f}:tilt{t:+.1f}'
            if bad or unk:
                checks.append(Check(cid, 'fail', '; '.join(f'{r.a} in {r.b}: {r.overlap_mm3:.3g} mm3' for r in bad) +
                                    ''.join(f'; {r.a}/{r.b} undecided' for r in unk),
                                    sorted({x for r in bad + unk for x in (r.a, r.b)}),
                                    {'interferences': [r.to_dict() for r in bad]}))
            else:
                near = sorted((r for r in tab if r.state in ('apart', 'touching') and r.gap_mm is not None), key=lambda r: r.gap_mm)
                checks.append(Check(cid, 'pass', f'{tab.stats["candidates"]} ball/part pairs near, none shared' +
                                    (f'; closest {near[0].a}/{near[0].b} {near[0].gap_mm:.2f} mm' if near else ''),
                                    [], {'closest': near[0].to_dict() if near else None}))
    data = verdict('turret-sweep', checks, assumptions=[
        'the settled pile rides with the tilt frame (the pockets with the dial, parked); the base, pinion and pan '
        'frame are posed by the rigid motions of cad/turret.py pose_shape',
        'a static check at each pose of the grid, not a swept volume between poses',
        'the model is checked, not the print: no tolerance stack, shrink or deflection'],
        limits={'pans_deg': list(pans), 'tilts_deg': list(tilts), 'overlap_mm3': GEOM_TOL.overlap_mm3}, extra={'stats': stats})
    write_verdict(VERDICTS / 'sweep.json', data)
    return data


def ammo_gate(T, pile, cache):
    """D67's range through the feed and the bore: the biggest accepted ball along the whole path and in every pocket
    (cadagent containment against the same cavities), the smallest still one to a pocket (the gap between spokes at the
    pitch radius under two balls) and still squeezed at the nip, and the bore's play for both."""
    G = T.G
    dmin, dmax = AMMO_D
    big_path = path_gate(T, cache, dmax, 'ammo_path_22.8.json')
    # the big round seated in each pocket: on the floor (its centre dmax/2 up) at the settled ball's bearing, its radius
    # from the dial's axis held between the hub and the housing wall (the settle's centres are for a 22.7 mm ball)
    seated = []
    for (x, y, _) in pile['pockets']:
        r = math.hypot(x, y)
        rr = min(max(r, G.dial_hub_r + dmax / 2), G.dial_wall_r - dmax / 2)
        seated.append((x * rr / r, y * rr / r, G.floor_z + dmax / 2))
    asm = build_assembly(T, {**pile, 'pockets': seated, 'pile': []}, dial_deg=pile['park_deg'], ball_d=dmax)
    big_pockets = containment_gate(asm, [{'container': 'hopper', 'cavity': 'hopper_cavity', 'what': 'ball',
                                          'count': len(pile['pockets']), 'closed_by': ['cartridge_body', 'hopper_lid']}],
                                   tol=PILE_TOL, cache=cache, support='off', probe=False, out=VERDICTS / 'ammo_pockets_22.8.json')
    gap = 2 * math.pi * G.rp / G.n_pockets - G.spoke_w                    # the pocket's length along the pitch circle
    nip_gap = G.wheel_c - G.wheel_d                                        # between the tyres
    checks = [Check('ammo:biggest_along_the_path', 'pass' if big_path['pass'] else 'fail',
                    f'{dmax} mm ball at {len(big_path["declarations"])} path points: {big_path["counts"]}', []),
              Check('ammo:biggest_in_the_pockets', 'pass' if big_pockets['pass'] else 'fail',
                    f'{dmax} mm balls in the {len(pile["pockets"])} pockets: {big_pockets["counts"]}', []),
              Check('ammo:one_ball_a_pocket', 'pass' if gap < 2 * dmin else 'fail',
                    f'pocket {gap:.2f} mm along the pitch circle against two {dmin} mm balls', []),
              Check('ammo:squeezed', 'pass' if nip_gap < dmin else 'fail',
                    f'nip gap {nip_gap:.2f} mm: {100 * (1 - nip_gap / dmax):.1f}-{100 * (1 - nip_gap / dmin):.1f} % squeeze', []),
              _ceiling_check(),
              Check('ammo:bore_play', 'pass' if G.bore - dmax >= 1.0 else 'fail',
                    f'feed and chute {G.bore - dmax:.2f}-{G.bore - dmin:.2f} mm, barrel {G.bore_out - dmax:.2f}-{G.bore_out - dmin:.2f} mm', [])]
    data = verdict('turret-ammo', checks, assumptions=[
        'the biggest round is checked at the design pile\'s pocket positions and on the path\'s centre line',
        'the smallest round\'s checks are arithmetic on the pitch circle and the nip gap',
        'the model is checked, not the print: no tolerance stack, shrink or deflection'],
        limits={'diameters_mm': list(AMMO_D)},
        extra={'pocket_length_mm': round(gap, 2), 'nip_gap_mm': round(nip_gap, 2),
               'smallest_squeezed_pct': round(100 * (1 - nip_gap / dmin), 1), 'biggest_squeezed_pct': round(100 * (1 - nip_gap / dmax), 1),
               'bore_play_mm': {'feed_and_chute': [round(G.bore - dmax, 2), round(G.bore - dmin, 2)],
                                'barrel': [round(G.bore_out - dmax, 2), round(G.bore_out - dmin, 2)]}})
    write_verdict(VERDICTS / 'ammo_range.json', data)
    return data


def _ceiling_check():
    """D67 x D68: the launch ceiling's corners (sim/turret_launch3d.py) span the accepted masses, the lightest round
    (1.6 g) is the fastest and stays at or under 105 fps, and the densest stays under ASTM F963's 2,500 J/m^2."""
    if not LAUNCH.exists():
        return Check('ammo:speed_ceiling', 'fail', f'no launch results ({LAUNCH.relative_to(R)}): run sim/turret_launch3d.py', [])
    c = json.loads(LAUNCH.read_text())['ceiling']
    worst, dense = c['worst_corner'], c['densest_ball']
    ok = c['highest_fps_any_case'] <= 105.0 and '-m1.6-' in worst and '-m2-' in dense and c['densest_ked_j_m2'] < c['astm_ked_j_m2']
    return Check('ammo:speed_ceiling', 'pass' if ok else 'fail',
                 f'fastest accepted round {c["highest_fps_any_case"]} fps ({worst}: the lightest, 1.6 g) <= 105; densest '
                 f'{c["densest_ked_j_m2"]} J/m^2 ({dense}) < {c["astm_ked_j_m2"]:.0f}', [],
                 {'worst_corner': worst, 'fps': c['highest_fps_any_case'], 'densest': dense, 'ked_j_m2': c['densest_ked_j_m2']})


# ------------------------------------------------------------------------------------------------ motion

def _pt(G, frame, p):
    v = gp_Pnt(*p).Transformed(home(G, frame))
    return (v.X(), v.Y(), v.Z())


# pairs in different bodies that touch by design (turret.py DESIGNED_CONTACTS, the tilt stop's lug on the yoke)
MOTION_CONTACTS = [sorted(p) for p in tu.DESIGNED_CONTACTS] + [sorted(tu.STOP_PAIR)]


def motion_pan_tilt(T, cache, pans=35, tilts=6):
    """cadagent.gates.motion over the aim: the pan joint (+-170 deg) carrying the tilt joint (0 to -25 deg: a turn of
    0..25 deg about +y at the tilt axis) on one grid; the dial, the flywheels and the flap ride with the tilt frame at
    home. The pinion is held still and its mesh with the ring is left to turret.pinion_check (the gate has no gear
    coupling). No balls (the containment gates hold them)."""
    G = T.G
    asm = build_assembly(T, None, dial_deg=0.0, balls=False,
                         bodies=lambda n, fr: 'tilt' if fr == 'tilt' else fr)
    joints = {'pan': {'kind': 'revolute', 'moving': 'pan_bearing_inner', 'fixed': 'pan_bearing',
                      'axis': ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)), 'range': [-170.0, 170.0], 'unit': 'deg', 'samples': pans},
              'tilt': {'kind': 'revolute', 'moving': 'tilt_bearing_inner', 'fixed': 'tilt_bearing',
                       'axis': ((0.0, 0.0, G.tilt_t), (0.0, 1.0, 0.0)), 'range': [0.0, -G.tilt_min], 'unit': 'deg',
                       'samples': tilts}}
    return motion_gate(asm, joints, tol=CONNECT_TOL, cache=cache, max_step_deg=12.0, intended_contacts=MOTION_CONTACTS,
                       ignore_pairs=[('pan_pinion', 'pan_ring')], out=VERDICTS / 'motion_aim.json')


def motion_mechanisms(T, cache):
    """cadagent.gates.motion over the mechanisms with the aim at home: the feed dial through 90 deg (two steps; its
    spokes repeat every 45 deg and its fins every 90), each flywheel a full turn, the fill flap open to 70 deg, and the
    pinion a full turn on its servo."""
    G = T.G
    asm = build_assembly(T, None, dial_deg=0.0, balls=False)
    sx, sy = G.servo_pan_xy
    hinge = _pt(G, 'tilt', (tu.FILL_PORT[0] - 19, 0.0, G.hopper_top + 6))
    joints = {'feed': {'kind': 'revolute', 'moving': 'dial', 'fixed': 'feed_motor',
                       'axis': (_pt(G, 'tilt', (0, 0, 0)), (0, 0, 1)), 'range': [0.0, 90.0], 'unit': 'deg', 'samples': 16},
              'wheel_l': {'kind': 'revolute', 'moving': 'flywheel', 'fixed': 'flywheel_motor_l',
                          'axis': (_pt(G, 'tilt', (G.wheel_x, G.wheel_y, 0)), (0, 0, 1)), 'range': [0.0, 360.0], 'unit': 'deg',
                          'samples': 13},
              'wheel_r': {'kind': 'revolute', 'moving': 'flywheel_m', 'fixed': 'flywheel_motor_r',
                          'axis': (_pt(G, 'tilt', (G.wheel_x, -G.wheel_y, 0)), (0, 0, 1)), 'range': [0.0, 360.0], 'unit': 'deg',
                          'samples': 13},
              'flap': {'kind': 'revolute', 'moving': 'hopper_flap', 'fixed': 'hopper_lid',
                       'axis': (hinge, (0, 1, 0)), 'range': [-70.0, 0.0], 'unit': 'deg', 'samples': 8},
              'pan_drive': {'kind': 'revolute', 'moving': 'pan_pinion', 'fixed': 'pan_servo',
                            'axis': ((sx, sy, 0.0), (0, 0, 1)), 'range': [0.0, 360.0], 'unit': 'deg', 'samples': 13}}
    return motion_gate(asm, joints, tol=CONNECT_TOL, cache=cache, max_step_deg=30.0, intended_contacts=MOTION_CONTACTS,
                       ignore_pairs=[('pan_pinion', 'pan_ring')], out=VERDICTS / 'motion_mechanisms.json')


# ------------------------------------------------------------------------------------------------ fasteners

TOOLS = {'hex 2.5': {'envelope_d': 3.0, 'length': 60.0}}      # a straight 2.5 mm hex key (or a ball driver's shaft)


def fastener_specs(T):
    """cad/turret.py GATED_SCREWS as FastenerSpecs in the T frame: M3 x 0.5 socket heads (Ø5.5 x 3), axes down."""
    G = T.G
    out = {}
    for name, g in tu.GATED_SCREWS.items():
        if name == 'hopper_screws':
            pts = [(*tu.polar(G.housing_r + 3.5, math.radians(a)), G.housing_top + 3.0) for a in tu.HOPPER_LUGS]
            ins_top = G.housing_top
        else:
            pts = [(x, y, g['seat_z']) for x, y in g['xy']]
            ins_top = tu.SOCKET_PAD_Z
        axes = [(_pt(G, 'tilt', p), (0.0, 0.0, -1.0)) for p in pts]
        out[name] = FastenerSpec(name=name, clamps=g['clamps'], into=g['into'], axes=axes, key=g['key'], tool='hex 2.5',
                                 length_mm=g['length_mm'], diameter_mm=3.0, pitch_mm=0.5,
                                 thread_start_mm=round(pts[0][2] - ins_top, 3), head_d_mm=5.5, head_h_mm=3.0)
    return out


def fasteners(T, asm, cache):
    """cadagent.gates.fasteners on the screws cad/turret.py places with their receivers (GATED_SCREWS): seat, stack,
    holes, engagement in the modelled insert, tip, length, and the hex key's straight reach. The steps: the screws go in
    before the cartridge board and its ESCs (the board's front edge is over the front hopper lug)."""
    steps = [{'order': 1, 'fit': ['hopper', 'laser_mount'], 'fasteners': list(tu.GATED_SCREWS), 'tool': 'hex 2.5'},
             {'order': 2, 'fit': ['cartridge_board', 'esc_l', 'esc_r']}]
    return fastener_gate(asm, fastener_specs(T), steps=steps, tools=TOOLS, tol=CONNECT_TOL, cache=cache,
                         out=VERDICTS / 'fasteners.json')


def _summary(v):
    out = {'ok': bool(v['pass']), 'status': v['status'], 'counts': v['counts'],
           'findings': [{'id': c['id'], 'status': c['status'], 'message': c['message'][:300]} for c in v['findings'][:20]]}
    for k in ('floating', 'unrealised'):
        if k in v:
            out[k] = v[k]
    return out


def run(T=None, write=True):
    t0 = time.time()
    T = T or tu.Turret({'bodyTop': 100.0})
    VERDICTS.mkdir(parents=True, exist_ok=True)
    cache = PairCache(CACHE)
    pile = load_pile(T.G)
    asm = build_assembly(T, pile, dial_deg=pile['park_deg'])
    res, secs = {}, {}
    for name, fn in (('connectivity', lambda: connectivity(T, asm, cache)),
                     ('hopper', lambda: hopper_gate(asm, cache)),
                     ('path', lambda: path_gate(T, cache, T.G.ball, 'path.json')),
                     ('sweep', lambda: sweep_gate(T, asm, cache)),
                     ('ammo_range', lambda: ammo_gate(T, pile, cache)),
                     ('fasteners', lambda: fasteners(T, asm, cache)),
                     ('motion_mechanisms', lambda: motion_mechanisms(T, cache)),
                     ('motion_aim', lambda: motion_pan_tilt(T, cache))):
        t1 = time.time()
        v = fn()
        secs[name] = round(time.time() - t1, 1)
        res[name] = _summary(v)
        print(f'  {name:13s} {v["status"]:5s} {v["counts"]} ({secs[name]} s)', flush=True)
        for c in v['findings'][:12]:
            print(f'      {c["status"]} {c["id"]}: {c["message"][:220]}', flush=True)
    out = {'toolkit': 'cadagent.gates (connectivity, containment, relation table, fasteners, motion)', 'fingerprint': geometry_fingerprint(),
           'pile': str(PILE.relative_to(R)), 'verdicts': str(VERDICTS.relative_to(R)), 'seconds': secs,
           'ok': all(v['ok'] for v in res.values()), 'gates': res}
    if write:
        OUT.write_text(json.dumps(out, indent=1, default=float) + '\n')
    return out


def require(results):
    """Raise GateFailure naming every gate that failed."""
    failed = {k: v for k, v in results.items() if not v.get('ok')}
    if failed:
        msg = '; '.join(f'{k}: ' + str([f['id'] for f in v.get('findings', []) if f['status'] == 'fail'])[:400] for k, v in failed.items())
        raise GateFailure(f'{len(failed)} design gate(s) failed: {msg}')


def stored(require_current=True):
    """The stored gate result for a build to read (cad/build_turret_box.py): raises GateFailure when it is missing,
    stale (the CAD, the pile or the toolkit's gates changed since) or failing."""
    if not OUT.exists():
        raise GateFailure(f'no gate result: run cad/turret_gates.py ({OUT})')
    d = json.loads(OUT.read_text())
    if 'toolkit' not in d:
        raise GateFailure('the gate result predates the cadagent gates: rerun cad/turret_gates.py')
    if require_current and d.get('fingerprint') != geometry_fingerprint():
        raise GateFailure('the gate result is stale (cad/turret.py, the pile or cadagent.gates changed): rerun cad/turret_gates.py')
    require(d['gates'])
    return d


DOSSIER_RECORD = R / 'exports' / 'dossier-geometry.json'
DOSSIER_GATES = R / 'exports' / 'gates'


def dossier_gates(cache=None):
    """The turret's own gates for cad-agent's process (docs/turret-dossier.md): the ball path and D67's ammo range,
    written as exports/gates/turret-path.json and turret-ammo.json (+ .md) and bound to the dossier's geometry record,
    so `cad-agent check` and the dossier lint (gate:turret-path, gate:turret-ammo) read them like the toolkit's gates
    and fail them when the record changes. Refuses to bind unless the record is the geometry cad/turret_dossier.py
    registers from this turret (the same digest, rebuilt here without writing)."""
    from cadagent import dossier as cd
    from cadagent.gates.run import write_outputs
    from cadagent.gates.verdict import bind_inputs, geometry_digest
    import turret_dossier as td
    if not DOSSIER_RECORD.exists():
        raise GateFailure(f'no geometry record ({DOSSIER_RECORD.relative_to(R)}): run cad-agent gates --build first')
    record = json.loads(DOSSIER_RECORD.read_text())
    T = td.T
    pile = load_pile(T.G)
    with cd.use_registry() as reg:
        td.register(reg, T, pile)
        mine = reg.build(write=False, root=R).geometry
    if geometry_digest(mine) != geometry_digest(record):
        raise GateFailure(f'{DOSSIER_RECORD.relative_to(R)} is not the turret this source builds: rerun cad-agent gates --build')
    cache = cache or PairCache(CACHE)
    DOSSIER_GATES.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (('turret-path', lambda: path_gate(T, cache, T.G.ball, 'path.json')),
                     ('turret-ammo', lambda: ammo_gate(T, pile, cache))):
        t1 = time.time()
        data = dict(fn(), gate=name)
        bind_inputs(data, record, record_file=str(DOSSIER_RECORD.relative_to(R)))
        write_outputs(DOSSIER_GATES, data)
        out[name] = data
        print(f'  {name:12s} {data["status"]:5s} {data["counts"]} ({time.time() - t1:.1f} s) -> exports/gates/{name}.json', flush=True)
        for c in data['findings'][:12]:
            print(f'      {c["status"]} {c["id"]}: {c["message"][:220]}', flush=True)
    return out


def main():
    if '--dossier' in sys.argv:
        res = dossier_gates()
        sys.exit(0 if all(v['pass'] for v in res.values()) else 1)
    d = run()
    print(f'gates {"pass" if d["ok"] else "FAIL"} in {sum(d["seconds"].values()):.0f} s -> {OUT}')
    sys.exit(0 if d['ok'] else 1)


if __name__ == '__main__':
    main()
