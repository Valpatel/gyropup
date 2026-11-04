"""How far up the turret's barrel can physically tilt: the reachable tilt range set by the parts themselves, not by a rule.

    .venv/bin/python cad/turret_tilt_range.py [--up 45] [--step 2.5] [--pan-step 10] [--margin 3]

Until #201 the upper hard stop sat at 0 deg to enforce "the barrel never points above horizontal". The owner removed
that rule on 2026-11-03 (docs/decisions.yaml D77): the limits are to be the real mechanical stops. This study finds
where the mechanism itself runs out of room above level, so the upper stop can be placed there with margin:

  - every part that tilts (the cradle, cartridge, hopper, dial, feed servo, barrel, laser, and the reserved envelope of
    the planned laser rangefinder, RANGEFINDER, #203) against every part that only pans (the yoke and its arms, the
    bridge, the pan ring and the board bay) at each tilt from 0 to `--up` deg, and against every fixed part (the pan base,
    the pan pinion, the bumper, the DT receptacle and plug) at every pan in `--pan-step` steps;
  - the tilt hard-stop pair (the yoke's stop sectors and the cradle's stop lug, cad/turret.py STOP_PAIR) is left out:
    it is the thing to be moved. Its own room is reported separately (`stop_room`): how far the -y arm's stop
    annulus lets the upper sector move before it runs off the arm;
  - the rangefinder's beam: a 5 x 7 mm aperture (grown 2 mm for its divergence over the turret) along the barrel from
    the envelope's front face, checked against every non-tilting part at every pan and tilt (it must leave the turret
    unobstructed, as the ball does).

Points are sampled over each part's surface every ~1.2 mm (cad/turret_lidar.py surface_points) and the clearance is
the nearest point pair, so a figure is good to about the sampling (+-1 mm); a contact is any pair closer than 0.5 mm.
The robot's body (the lidar ahead, the deck) is checked at elevation by cad/turret_lidar.py over the same tilt range;
it depends on the mount height that #196 (D76) changes, so it is run on the merged geometry.

Writes exports/turret/tilt-range.json: per tilt, the nearest approach and the pair; the first tilt at which any pair
comes within the margin, and within contact, at any pan, refined to 0.25 deg; the stop's room on the arm; the
rangefinder envelope's own clearances and its beam.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402
import turret_lidar as tl  # noqa: E402

OUT = R / 'exports' / 'turret'
CONTACT_MM = 0.5
# The planned laser rangefinder (#203): ERDI SPD1200Z2, 905 nm, UART: 7.2 x 14.8 x 28.2 mm and about 6 g, its 5 x 7 mm
# aperture facing forward. The reserved envelope adds a bracket and boresight adjustment (36 x 20 x 13.2 mm against the
# module's 28.2 x 14.8 x 7.2): a box on the cartridge's front face beside the barrel, on +y, its aperture's centre 30 mm off the
# bore's axis at the bore's height (a 36 mm parallax, boresighted at the bench). C frame (mm).
RANGEFINDER = {'model': 'ERDI SPD1200Z2 (905 nm, UART), planned in #203; not integrated',
               'module_mm': [28.2, 14.8, 7.2], 'mass_g': 6.0, 'mass_allowance_g': 15.0,
               'box_c': {'x': [98.0, 134.0], 'y': [25.6, 45.6], 'z': [-6.6, 6.6]},
               'aperture_mm': [5.0, 7.0], 'aperture_c': [134.0, 35.6, 0.0], 'beam_growth_mm': 2.0}


def rangefinder_solid():
    b = RANGEFINDER['box_c']
    return tu.box(b['x'][0], b['x'][1], b['y'][0], b['y'][1], b['z'][0], b['z'][1])


def beam_solid(length=320.0):
    """The rangefinder's beam inside the turret's reach: the aperture grown by beam_growth_mm, along +x (C frame)."""
    (w, h), g = RANGEFINDER['aperture_mm'], RANGEFINDER['beam_growth_mm']
    x0, y0, z0 = RANGEFINDER['aperture_c']
    return tu.box(x0, x0 + length, y0 - w / 2 - g, y0 + w / 2 + g, z0 - h / 2 - g, z0 + h / 2 + g)


def clouds(T, spacing=1.2):
    """{name: (frame, points)} for every part, the reserved envelope and its beam (frames as cad/turret.py)."""
    out = {}
    for name, shape in T.local.items():
        out[name] = (T.frame[name], tl.surface_points(shape, spacing))
    out['rangefinder_envelope'] = ('tilt', tl.surface_points(rangefinder_solid(), spacing))
    out['rangefinder_beam'] = ('tilt', tl.surface_points(beam_solid(), 2.0))
    return out


def into_pan_frame(T, P, frame, pan):
    """A fixed or pinion part's points seen from the pan group at this pan (so the tilting parts need posing only once
    per tilt)."""
    Q = tl.pose_points(T, P, 'base', 0.0, 0.0)
    if frame == 'pinion' and pan:
        x, y = T.G.servo_pan_xy
        a = math.radians(-pan * T.G.gear['z_ring'] / T.G.gear['z_pinion'])
        c, s = math.cos(a), math.sin(a)
        Q = np.stack([x + (Q[:, 0] - x) * c - (Q[:, 1] - y) * s, y + (Q[:, 0] - x) * s + (Q[:, 1] - y) * c, Q[:, 2]], axis=1)
    if pan:
        c, s = math.cos(math.radians(-pan)), math.sin(math.radians(-pan))
        Q = np.stack([Q[:, 0] * c - Q[:, 1] * s, Q[:, 0] * s + Q[:, 1] * c, Q[:, 2]], axis=1)
    return Q


def nearest(trees, others, reach):
    """The nearest approach (mm) between each tilting part and each other part's points (within reach), as
    {(tilting, other): mm}."""
    out = {}
    for tn, (tree, lo, hi) in trees.items():
        for on, Q in others.items():
            m = np.all((Q > lo - reach) & (Q < hi + reach), axis=1)
            if not m.any():
                continue
            d, _ = tree.query(Q[m], k=1, distance_upper_bound=reach)
            d = d[np.isfinite(d)]
            if len(d):
                out[(tn, on)] = float(d.min())
    return out


def skip(a, b):
    return frozenset((a, b)) == tu.STOP_PAIR or frozenset((a, b)) in tu.DESIGNED_CONTACTS or frozenset((a, b)) in tu.SKIP_PAIRS


def at_tilt(T, C, tilt, pans, reach):
    """The nearest approach of every tilting part to every other part at one tilt, over the pans: [(mm, tilting, other,
    pan)] sorted, pairs within reach only."""
    tilting = {n: tl.pose_points(T, P, 'tilt', 0.0, tilt) for n, (fr, P) in C.items() if fr == 'tilt'}
    trees = {n: (cKDTree(P), P.min(axis=0), P.max(axis=0)) for n, P in tilting.items() if n != 'rangefinder_beam'}
    beam = {'rangefinder_beam': tilting['rangefinder_beam']}
    rows = []
    pan_parts = {n: tl.pose_points(T, P, 'pan', 0.0, 0.0) for n, (fr, P) in C.items() if fr == 'pan'}
    fixed = {n: (fr, P) for n, (fr, P) in C.items() if fr in ('base', 'pinion')}
    for (a, b), d in nearest(trees, pan_parts, reach).items():
        if not skip(a, b):
            rows.append((d, a, b, None))
    btree = {'rangefinder_beam': (cKDTree(beam['rangefinder_beam']), beam['rangefinder_beam'].min(axis=0), beam['rangefinder_beam'].max(axis=0))}
    for (a, b), d in nearest(btree, pan_parts, reach).items():
        rows.append((d, a, b, None))
    for pan in pans:
        others = {n: into_pan_frame(T, P, fr, pan) for n, (fr, P) in fixed.items()}
        for (a, b), d in nearest(trees, others, reach).items():
            if not skip(a, b):
                rows.append((d, a, b, pan))
        for (a, b), d in nearest(btree, others, reach).items():
            rows.append((d, a, b, pan))
    # the envelope against the other tilting parts (it must fit on the cradle at all), and its beam against them
    for n, P in tilting.items():
        if n in ('rangefinder_envelope', 'rangefinder_beam'):
            continue
        for k in ('rangefinder_envelope', 'rangefinder_beam'):
            src = trees['rangefinder_envelope'] if k == 'rangefinder_envelope' else btree['rangefinder_beam']
            r = nearest({k: src}, {n: P}, reach)
            for (a, b), d in r.items():
                rows.append((d, a, b, 'same group'))
    rows.sort(key=lambda r: r[0])
    return rows


def limiting(rows, base, margin):
    """The rows that limit the tilt: closer than the margin and closer than the same pair was at level (by more than the
    sampling's 0.25 mm). Pairs that sit close by design about the tilt axis (the bearing and its spacer, a
    plate beside the arm) keep their distance as the cradle turns and so never limit it."""
    out = []
    for d, a, b, p in rows:
        if p == 'same group':
            continue
        d0 = base.get((a, b, p), math.inf)
        if d < margin and d < d0 - 0.25:
            out.append((d, a, b, p))
    return out


def baseline(T, C, pans, reach):
    return {(a, b, p): d for d, a, b, p in at_tilt(T, C, 0.0, pans, reach)}


def first_limit(T, C, tilts, pans, reach, margin, base):
    """Walk up the tilts; return (per-tilt summary, first coarse tilt with a limiting pair, first in contact)."""
    summary, within, contact = [], None, None
    for t in tilts:
        rows = [r for r in at_tilt(T, C, t, pans, reach) if r[3] != 'same group']
        lim = limiting(rows, base, margin)
        moved = [r for r in rows if r[0] < base.get((r[1], r[2], r[3]), math.inf) - 0.25]
        best = moved[0] if moved else (reach, None, None, None)
        summary.append({'tilt_deg': t, 'nearest_closing_mm': round(best[0], 2), 'pair': [best[1], best[2]], 'pan_deg': best[3],
                        'limiting': [[round(d, 2), a, b, p] for d, a, b, p in lim][:8]})
        if within is None and lim:
            within = t
        if contact is None and any(r[0] < CONTACT_MM for r in lim):
            contact = t
            break
    return summary, within, contact


def refine(T, C, lo, hi, pans, reach, margin, base, contact=False, step=0.25):
    """The last tilt in [lo, hi] (0.25 deg steps) with no limiting pair (contact only, with `contact`), and the pair that
    ends it."""
    last, why = lo, None
    t = lo
    while t <= hi + 1e-9:
        rows = [r for r in at_tilt(T, C, t, pans, reach) if r[3] != 'same group']
        lim = [r for r in limiting(rows, base, margin) if not contact or r[0] < CONTACT_MM]
        if lim:
            why = [round(lim[0][0], 2), lim[0][1], lim[0][2], lim[0][3]]
            break
        last = t
        t = round(t + step, 4)
    return last, why


def stop_room(G):
    """The -y arm's stop annulus (r G.stop_r) runs between the arm's edges (x = +-20 mm in the arm's own frame, about the
    tilt axis): the angles there, where the stop lug (+-STOP_HALF_DEG) sweeps, and how far up the upper sector's face can
    move while keeping its current 30 deg of face (or a 15 deg minimum) on the arm."""
    half_x = 20.0
    r_out = G.stop_r[1]
    edge = math.degrees(math.acos(half_x / r_out))                 # angle from straight down where r_out meets the edge
    lo_edge, hi_edge = -90.0 - (90.0 - edge), -90.0 + (90.0 - edge)
    w = tu.STOP_HALF_DEG
    face_now = -90.0 + w                                           # the upper sector's face at tilt_max = 0
    return {'arm_half_width_mm': half_x, 'stop_r_mm': list(G.stop_r), 'outer_annulus_on_arm_deg': [round(lo_edge, 1), round(hi_edge, 1)],
            'lug_half_deg': w, 'upper_face_now_deg': face_now, 'lower_face_now_deg': -90.0 + G.tilt_min - w,
            'upper_stop_max_keeping_30deg_sector': round(hi_edge - 30.0 - face_now, 1),
            'upper_stop_max_keeping_15deg_sector': round(hi_edge - 15.0 - face_now, 1),
            'note': 'beyond these the stop needs its geometry changed (a narrower lug, the stop annulus at a smaller radius, the '
                    'lug rotated on its plate or a wider arm foot), not only its angle: CAD work after #196 merges'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--up', type=float, default=45.0)
    ap.add_argument('--step', type=float, default=2.5)
    ap.add_argument('--pan-step', type=float, default=10.0)
    ap.add_argument('--margin', type=float, default=3.0)
    a = ap.parse_args()
    t0 = time.time()
    L = tu.derive(R / 'designs/default.json')
    T = tu.Turret(L)
    G = T.G
    C = clouds(T)
    print(f'clouds: {sum(len(P) for _, P in C.values())} points in {len(C)} parts ({time.time() - t0:.0f} s)')
    pans = [float(p) for p in np.arange(0.0, 360.0, a.pan_step)]
    tilts = [round(float(t), 3) for t in np.arange(0.0, a.up + 1e-9, a.step)]
    reach = a.margin + 12.0
    base = baseline(T, C, pans, reach)
    summary, within, contact = first_limit(T, C, tilts, pans, reach, a.margin, base)
    for s in summary:
        print(f"  tilt {s['tilt_deg']:+6.2f}: nearest closing {s['nearest_closing_mm']:6.2f} mm  {s['pair']} at pan {s['pan_deg']}  "
              f"limiting {s['limiting'][:2]}")
    res = {'what': 'the reachable tilt range above level (cad/turret_tilt_range.py, #201)',
           'frame': 'tilt + = muzzle up (cad/turret.py); pans in deg about the pan axis',
           'stops_now_deg': [G.tilt_min, G.tilt_max], 'margin_mm': a.margin, 'contact_mm': CONTACT_MM,
           'pans_deg': pans, 'step_deg': a.step, 'sampling_mm': 1.2, 'rangefinder': RANGEFINDER,
           'per_tilt': summary, 'stop_room': stop_room(G)}
    below = lambda t: max(0.0, t - a.step)
    if within is not None:
        res['last_tilt_with_margin_deg'], res['margin_ended_by'] = refine(T, C, below(within), within, pans, reach, a.margin, base)
    else:
        res['last_tilt_with_margin_deg'], res['margin_ended_by'] = a.up, None
    if contact is not None:
        res['first_contact_deg'], res['contact_by'] = refine(T, C, below(contact), contact, pans, reach, a.margin, base, contact=True)
    else:
        res['first_contact_deg'], res['contact_by'] = None, None
    # the envelope's fit on the cradle and its beam, at level
    same = [r for r in at_tilt(T, C, 0.0, pans, reach) if r[3] == 'same group']
    res['rangefinder_on_cradle_at_0'] = [[round(d, 2), a_, b] for d, a_, b, _ in same[:6]]
    res['seconds'] = round(time.time() - t0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tilt-range.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: res[k] for k in ('last_tilt_with_margin_deg', 'margin_ended_by', 'first_contact_deg', 'contact_by', 'stop_room',
                                          'rangefinder_on_cradle_at_0', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
