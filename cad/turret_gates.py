"""The turret's design gates: cad/gates.py's generic checks run on the turret's own parts, so that a model that is not
physically coherent fails the build instead of reaching a page.

    balls       every ball the pages draw (the settled pile, the dial's pockets, the ball's path from the exit to the
                muzzle) inside its cavity: each sphere against every solid under 1 mm^3, no two balls overlapping more
                than 0.1 mm. The pile is sim/turret_feed.py's physics settle (exports/turret/feed/pile.json).
    connected   one connected body per moving group (base, pinion, pan, tilt, dial, each flywheel, the fill flap), and
                every joint between them closed (a bearing on its race, the dial on its servo horn...).
    sweep       the hopper's balls clear of every part that moves relative to them, at every pan and tilt of the sweep.

All in the cartridge frame C (mm: x along the barrel, the dial axis at x = y = 0, the ball path at z = 0) for the tilt
group, and in each part's own build frame posed by Turret.pose_shape for the sweep.

    .venv/bin/python cad/turret_gates.py          (writes exports/turret/gates.json; exit 1 when a gate fails)
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates  # noqa: E402
import turret as tu  # noqa: E402

R = Path(__file__).resolve().parents[1]
PILE = R / 'exports' / 'turret' / 'feed' / 'pile.json'
OUT = R / 'exports' / 'turret' / 'gates.json'

# rigid groups: which parts move together (the build frames say most of it; these split the tilt frame's turning parts)
TILT_MOVERS = {'dial': 'dial', 'flywheel': 'wheel_l', 'flywheel_tyre': 'wheel_l', 'flywheel_m': 'wheel_r',
               'flywheel_tyre_m': 'wheel_r', 'hopper_flap': 'flap'}
NOT_RIGID = {'dt_plug'}                      # the robot's harness plug: a separate cable, plugged in
# joints between moving bodies: each pair must be within gates.connectivity's joint_mm
JOINTS = [('pan_bearing', 'pan_bearing_inner', 'the 61810 pan bearing (outer race in the base, inner on the turntable)'),
          ('pan_pinion', 'pan_servo', 'the pinion on the pan servo\'s horn'),
          ('pan_pinion', 'pan_ring', 'the gear mesh (0.15 mm backlash a flank)'),
          ('tilt_bearing', 'tilt_bearing_inner', 'the MR126 tilt bearing (outer in the yoke, inner on the shoulder screw)'),
          ('tilt_servo', 'horn_boss', 'the tilt servo\'s horn on the cradle\'s horn boss'),
          ('dial', 'feed_motor', 'the dial on the feed servo\'s horn'),
          ('flywheel', 'flywheel_motor_l', 'the left flywheel on its X2216\'s prop adapter'),
          ('flywheel_m', 'flywheel_motor_r', 'the right flywheel on its X2216\'s prop adapter'),
          ('hopper_flap', 'hopper_lid', 'the fill flap on its hinge pin in the lid\'s lugs')]
# fastened pairs whose solids do not touch in the CAD (the fastener is not modelled as a solid): (a, b, how)
LINKS = [('laser', 'laser_mount', 'three M3 nylon-tip boresight screws hold it 2 mm clear of the ring\'s bore (it is aimed by them)'),
         ('ring_leads_rotor', 'slip_ring_rotor', 'the rotor\'s own leads: one bought part with the ring\'s rotor')]


def geometry_fingerprint():
    """What the gates depend on: the CAD source and the settled pile. A stored result is current when this matches."""
    h = hashlib.sha256()
    for f in (R / 'cad' / 'turret.py', R / 'cad' / 'gates.py', Path(__file__), PILE):
        h.update(f.read_bytes() if f.exists() else b'-')
    return h.hexdigest()[:16]


def ball_path(G, step=2.0):
    """The ball's centre from the exit pocket to the muzzle, every `step` mm (C frame): the chute's quarter bend from
    the pocket down to the path, then straight along it through the nip and the barrel."""
    pts = []
    n = max(2, int(math.ceil(G.chute_r * math.pi / 2 / step)))
    for k in range(n + 1):
        th = math.pi + k * (math.pi / 2) / n
        pts.append((G.chute_cx + G.chute_r * math.cos(th), 0.0, G.chute_r + G.chute_r * math.sin(th)))
    x = G.chute_cx + step
    while x <= G.barrel_x1:
        pts.append((x, 0.0, 0.0))
        x += step
    return pts


def load_pile(G):
    """The settled hopper (pile.json): pockets in the dial's frame at its zero, the pile in C; the park angle."""
    if not PILE.exists():
        raise gates.GateFailure(f'no settled pile: run gp-remote --pull exports/turret/feed/ -- python sim/turret_feed.py --pile ({PILE})')
    d = json.loads(PILE.read_text())
    if abs(d['ball_d_mm'] - G.ball) > 1e-6 or len(d['pockets']) + len(d['pile']) != d['balls']:
        raise gates.GateFailure('pile.json is for another ball or lost balls: rerun sim/turret_feed.py --pile')
    return d


def rot_z(p, deg):
    a = math.radians(deg)
    return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a), p[2])


def tilt_solids(T, dial_deg=0.0):
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


def ball_gates(T, pile):
    G = T.G
    rb = G.ball / 2
    park = pile['park_deg']
    hopper = [rot_z(p, park) for p in pile['pockets']] + [tuple(p) for p in pile['pile']]
    labels = [f'pocket {k}' for k in range(len(pile['pockets']))] + [f'pile {k}' for k in range(len(pile['pile']))]
    parked = tilt_solids(T, park)
    res = {'hopper_in_cavity': gates.spheres_in_cavities(hopper, rb, parked, labels=labels),
           'hopper_overlap': gates.sphere_overlaps(hopper, rb, 0.1, labels=labels)}
    # the path: the dial stands with a pocket over the exit hole while the ball drops (its zero); the tyres squeeze
    # the ball by design, so they may touch it
    path = ball_path(G)
    stepping = tilt_solids(T, 0.0)
    nip = [i for i, p in enumerate(path) if abs(p[0] - G.wheel_x) < G.wheel_d / 2 + rb and abs(p[2]) < 1e-6]
    allow = [(i, n) for i in nip for n in ('flywheel_tyre', 'flywheel_tyre_m', 'flywheel', 'flywheel_m')]
    res['path_in_cavity'] = gates.spheres_in_cavities(path, rb, stepping, allow=allow,
                                                      labels=[f'path x {p[0]:.0f} z {p[2]:.0f}' for p in path])
    return res, hopper


AMMO_D = (22.2, 22.8)          # D67: any Rival-compatible round 22.2-22.8 mm (1.6-2.0 g: the mass is the launch ceiling's)


def ammo_gate(T, pile):
    """The accepted ammo range (D67) through the feed and the bore: the biggest ball along the whole path and in every
    pocket clear of the solids, the smallest ball still one to a pocket (the gap between spokes at the pitch radius
    under two balls) and still squeezed at the nip, and the bore's play for both."""
    G = T.G
    dmin, dmax = AMMO_D
    path = ball_path(G)
    nip = [i for i, p in enumerate(path) if abs(p[0] - G.wheel_x) < G.wheel_d / 2 + dmax / 2 and abs(p[2]) < 1e-6]
    allow = [(i, n) for i in nip for n in ('flywheel_tyre', 'flywheel_tyre_m', 'flywheel', 'flywheel_m')]
    big_path = gates.spheres_in_cavities(path, dmax / 2, tilt_solids(T, 0.0), allow=allow)
    pockets = [rot_z(p, pile['park_deg']) for p in pile['pockets']]
    big_pockets = gates.spheres_in_cavities(pockets, dmax / 2, tilt_solids(T, pile['park_deg']))
    gap = 2 * math.pi * G.rp / G.n_pockets - G.spoke_w                    # the pocket's length along the pitch circle
    nip_gap = G.wheel_c - G.wheel_d                                        # between the tyres
    out = {'diameters_mm': list(AMMO_D), 'biggest_along_the_path': {k: big_path[k] for k in ('ok', 'violations', 'tightest')},
           'biggest_in_the_pockets': {k: big_pockets[k] for k in ('ok', 'violations', 'tightest')},
           'pocket_length_mm': round(gap, 2), 'one_ball_a_pocket': gap < 2 * dmin,
           'nip_gap_mm': round(nip_gap, 2), 'smallest_squeezed_pct': round(100 * (1 - nip_gap / dmin), 1),
           'biggest_squeezed_pct': round(100 * (1 - nip_gap / dmax), 1), 'squeezed': nip_gap < dmin,
           'bore_play_mm': {'feed_and_chute': [round(G.bore - dmax, 2), round(G.bore - dmin, 2)],
                            'barrel': [round(G.bore_out - dmax, 2), round(G.bore_out - dmin, 2)]}}
    out['ok'] = big_path['ok'] and big_pockets['ok'] and out['one_ball_a_pocket'] and out['squeezed'] and G.bore - dmax >= 1.0
    out['violations'] = big_path['violations'] + big_pockets['violations'] + \
        ([] if out['one_ball_a_pocket'] else ['two small balls fit a pocket']) + ([] if out['squeezed'] else ['the smallest ball passes the nip unsqueezed'])
    return out


def connectivity_gate(T):
    solids, groups = {}, {}
    for n, fr in T.frame.items():
        if n in NOT_RIGID:
            continue
        s = T.pose_shape(T.local[n], fr, 0.0, 0.0, robot=False)
        solids[n], groups[n] = s, TILT_MOVERS.get(n, fr)
        if n in ('flywheel', 'flywheel_tyre'):
            solids[n + '_m'] = T.pose_shape(T.local[n].mirror('XZ'), fr, 0.0, 0.0, robot=False)
            groups[n + '_m'] = TILT_MOVERS[n + '_m']
    return gates.connectivity(solids, groups, links=LINKS, joints=JOINTS)


def sweep_gate(T, hopper, pans=(0.0, 45.0, 90.0, 135.0, 180.0, -135.0, -90.0, -45.0), tilts=tu.SWEEP_TILTS):
    """The hopper's balls (one compound, with the tilt group) against every part outside the tilt group."""
    rb = T.G.ball / 2
    balls = cq.Compound.makeCompound([cq.Solid.makeSphere(rb, cq.Vector(*p)) for p in hopper])
    others = [n for n, fr in T.frame.items() if fr != 'tilt']
    poses = [(p, t) for p in pans for t in tilts]
    return gates.clear_over_poses(lambda pt: T.pose_shape(balls, 'tilt', pt[0], pt[1], robot=False),
                                  lambda pt: {n: T.pose_shape(T.local[n], T.frame[n], pt[0], pt[1], robot=False) for n in others},
                                  poses)


def run(T=None, write=True):
    t0 = time.time()
    T = T or tu.Turret({'bodyTop': 100.0})
    pile = load_pile(T.G)
    res, hopper = ball_gates(T, pile)
    res['ammo_range'] = ammo_gate(T, pile)
    res['connected'] = connectivity_gate(T)
    res['sweep_with_balls'] = sweep_gate(T, hopper)
    out = {'fingerprint': geometry_fingerprint(), 'pile': str(PILE.relative_to(R)), 'seconds': round(time.time() - t0),
           'ok': all(v['ok'] for v in res.values()), 'gates': res}
    if write:
        OUT.write_text(json.dumps(out, indent=1, default=float) + '\n')
    return out


def stored(require_current=True):
    """The stored gate result for a build to read (cad/build_turret_box.py): raises GateFailure when it is missing,
    stale (the CAD or the pile changed since) or failing."""
    if not OUT.exists():
        raise gates.GateFailure(f'no gate result: run gp-remote --pull exports/turret/ -- python cad/turret_gates.py ({OUT})')
    d = json.loads(OUT.read_text())
    if require_current and d.get('fingerprint') != geometry_fingerprint():
        raise gates.GateFailure('the gate result is stale (cad/turret.py or the pile changed): rerun cad/turret_gates.py')
    gates.require(d['gates'])
    return d


def main():
    d = run()
    for k, v in d['gates'].items():
        extra = ''
        if k == 'ammo_range':
            extra = (f'{v["diameters_mm"]} mm: pocket {v["pocket_length_mm"]} (one ball each), nip squeeze {v["biggest_squeezed_pct"]}-'
                     f'{v["smallest_squeezed_pct"]} %, bore play {v["bore_play_mm"]}' + ''.join(f'\n      {x}' for x in v['violations'][:8]))
        elif 'violations' in v:
            extra = f'{len(v["violations"])} violations' + (f', tightest {v["tightest"][:2]}' if v.get('tightest') else '') + \
                    (f', worst overlap {v["worst_overlap_mm"]} mm' if 'worst_overlap_mm' in v else '')
            for x in v['violations'][:12]:
                extra += f'\n      {x}'
        else:
            extra = ', '.join(f'{g}: {x["bodies"]} bodies' + (f' floating {x["floating"]}' if x['floating'] else '') for g, x in v['groups'].items())
            extra += ''.join(f'\n      joint {j["a"]} - {j["b"]}: {j["gap_mm"]} mm' for j in v['joints'] if not j['ok'])
        print(f'  {k:18s} {"ok  " if v["ok"] else "FAIL"} {extra}')
    print(f'gates {"pass" if d["ok"] else "FAIL"} in {d["seconds"]} s -> {OUT}')
    sys.exit(0 if d['ok'] else 1)


if __name__ == '__main__':
    main()
