"""The turret firing over the VLP-16 lidar in front of it: clearance of the barrel, the cartridge and the ball's path at
every pan and tilt, the pan-dependent depression limit that keeps them clear, and where the lidar may sit.

    .venv/bin/python cad/turret_lidar.py [--x 150] [--top 43.7] [--margin 10] [--map]   # the robot: over its lidar
    .venv/bin/python cad/turret_lidar.py --scene box                                       # the Orin box: its deck, antennas

The same check serves any mount: a scene is a list of obstacles (vertical cylinders and boxes), each with or without
the ball path (scene_robot, scene_box). Points that can never come within the margin at any pan and tilt are dropped
first (a lower bound over the pose), which leaves a few thousand of the parts' points to pose.

The layout (user, 2026-10-26): on the robot the turret sits behind the VLP-16 on the top deck and fires over it. The
body is not designed yet, so the lidar's place is a parameter: its centre `x` mm ahead of the pan axis on the
turret's centre line, its top `top` mm above the turret's mounting face (TM). Baseline: the lidar stands on the body's
top deck and the turret on a 30 mm printed riser there (decided 2026-10-27), so the lidar's top is 71.7 - 30 = 41.7 mm
above the TM face, and its centre is as close behind the turret's TPU bumper ring (R 86) as a 10 mm gap allows:
x = 86 + 51.65 + 10 = 148 mm.

What is checked, for pan -180..180 deg (2 deg steps) and tilt 0..-25 deg (0.5 deg steps):
  - every part that pans or tilts (sampled over its surface every ~1.2 mm, so flat faces count, not just their
    corners), against the lidar's cylinder (VLP-16: Ø103.3 x 71.7, Velodyne VLP-16 user manual), at least `margin`;
  - the ball's path from the muzzle: a ball of the largest Rival size (Ø22.8) along the barrel's axis turned down a
    further 2 deg (a wild shot), dropping under gravity at the slowest speed it can leave at (the 11 m/s stray-ball
    clear, research/turret-launcher-study.md section 4), until it is past the lidar: at least `margin` too.
The fixed parts (pan base, bumper) are checked once. Writes exports/turret/lidar/: lidar.json (the limit for every pan,
the pan window where it applies, a firmware table), lidar-limit.png (the limit against pan), lidar-map.png (the
depression the worst pan allows, for the lidar anywhere from 120 to 260 mm ahead and its top from -40 to +80 mm),
lidar-side.png (the turret over the lidar at the limit).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402

OUT = R / 'exports' / 'turret' / 'lidar'
LIDAR = {'d': 103.3, 'h': 71.7, 'model': 'Velodyne VLP-16 (Puck)', 'source': 'VLP-16 user manual: Ø103.3 x 71.7 mm'}
DECK_BELOW_TM = 30.0                          # the turret stands on a 30 mm printed riser on the top deck (D41, 2026-10-27)
BUMPER_R = 86.0
BALL_MAX_D = 22.8                             # the largest Rival-size round on sale (Dart Zone Powerstrike, study 2.1)
WILD_DEG = 2.0                                # a ball leaving 2 deg low of the barrel's axis
SLOW_MS = 11.0                                # the stray-ball clear fires at about 36 fps (S-Core, study section 4)
G_MM_S2 = 9810.0


def surface_points(shape, spacing=1.2, tol=0.2):
    """Points over a part's whole surface: the tessellation's vertices plus points spread over every triangle so that
    no point of a face is more than about `spacing` from a sample."""
    v = shape.val() if hasattr(shape, 'val') else shape
    verts, tris = v.tessellate(tol, 0.3)
    P = np.array([(p.x, p.y, p.z) for p in verts])
    T = np.array(tris, dtype=np.int64)
    out = [P]
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    longest = np.max(np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)]), axis=0)
    n = np.maximum(1, np.ceil(longest / spacing)).astype(int)
    for k in np.unique(n):
        if k <= 1:
            continue
        sel = n == k
        ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij')
        m = (ii + jj) <= k
        u, w = ii[m] / k, jj[m] / k
        A, B, C = a[sel], b[sel], c[sel]
        pts = A[:, None, :] + u[None, :, None] * (B - A)[:, None, :] + w[None, :, None] * (C - A)[:, None, :]
        out.append(pts.reshape(-1, 3))
    return np.unique(np.round(np.concatenate(out), 2), axis=0)


def pose_points(T, P, frame, pan, tilt):
    """cad/turret.py's pose_shape for a point cloud (T frame, mm): C frame -> tilt -> pan."""
    G = T.G
    Q = P.copy()
    if frame == 'tilt':
        Q = Q + np.array([-G.tilt_x, 0.0, G.path_t])
        a = math.radians(-tilt)                             # nose down = rotation by -tilt about +y through the tilt axis
        x, z = Q[:, 0], Q[:, 2] - G.tilt_t
        Q = np.stack([x * math.cos(a) + z * math.sin(a), Q[:, 1], -x * math.sin(a) + z * math.cos(a) + G.tilt_t], axis=1)
    if frame in ('pan', 'tilt') and pan:
        c, s = math.cos(math.radians(pan)), math.sin(math.radians(pan))
        Q = np.stack([Q[:, 0] * c - Q[:, 1] * s, Q[:, 0] * s + Q[:, 1] * c, Q[:, 2]], axis=1)
    return Q


def cyl_distance(Q, x0, y0, r, z0, z1):
    """Signed distance from points to a vertical cylinder (negative inside)."""
    rho = np.hypot(Q[:, 0] - x0, Q[:, 1] - y0)
    dr = rho - r
    dz = np.maximum(z0 - Q[:, 2], Q[:, 2] - z1)
    out = np.where((dr > 0) | (dz > 0), np.hypot(np.maximum(dr, 0), np.maximum(dz, 0)), np.maximum(dr, dz))
    return out


def ball_path(T, pan, tilt, n=60):
    """Centres of the ball from the muzzle until it is past the lidar's far edge, aimed WILD_DEG under the barrel, at
    SLOW_MS: (points, ball radius)."""
    G = T.G
    m0 = np.array(T.point((G.barrel_x1, 0, 0), 'tilt', pan, tilt, robot=False))
    el = math.radians(tilt - WILD_DEG)
    d = np.array([math.cos(el) * math.cos(math.radians(pan)), math.cos(el) * math.sin(math.radians(pan)), math.sin(el)])
    t = np.linspace(0.0, 0.040, n)                      # 40 ms: 440 mm at 11 m/s, past any lidar here
    pts = m0[None, :] + SLOW_MS * 1000.0 * t[:, None] * d[None, :]
    pts[:, 2] -= 0.5 * G_MM_S2 * t ** 2
    return pts, BALL_MAX_D / 2


def box_distance(Q, lo, hi):
    """Signed distance from points to an axis-aligned box (negative inside)."""
    d = np.maximum(np.asarray(lo) - Q, Q - np.asarray(hi))
    out = np.linalg.norm(np.maximum(d, 0.0), axis=1)
    return np.where((d > 0).any(axis=1), out, d.max(axis=1))


def obstacle_distance(Q, ob):
    if ob['kind'] == 'cyl':
        return cyl_distance(Q, ob['x'], ob['y'], ob['r'], ob['z0'], ob['z1'])
    return box_distance(Q, ob['lo'], ob['hi'])


def ring_bound(rho, z, ob):
    """A lower bound of the distance to the obstacle from a point that turns on a circle of radius rho at height z about
    the pan axis, over every pan: what lets the study drop the points that can never come near."""
    if ob['kind'] == 'cyl':
        d = math.hypot(ob['x'], ob['y'])
        h = np.maximum(0.0, np.abs(rho - d) - ob['r'])
        v = np.maximum(0.0, np.maximum(ob['z0'] - z, z - ob['z1']))
    else:
        lo, hi = ob['lo'], ob['hi']
        cx, cy = min(max(0.0, lo[0]), hi[0]), min(max(0.0, lo[1]), hi[1])
        dmin = math.hypot(cx, cy)
        dmax = max(math.hypot(x, y) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]))
        h = np.maximum(0.0, np.maximum(dmin - rho, rho - dmax))
        v = np.maximum(0.0, np.maximum(lo[2] - z, z - hi[2]))
    return np.hypot(h, v)


def prune(T, clouds, obstacles, margin, tilt_min):
    """The moving parts' points that can come within margin + 2 mm of an obstacle at some pan and tilt (the rest are
    dropped: at least the margin away whatever the pose). Tilting parts are bounded at seven tilts, less the arc a
    point can sweep between them."""
    G = T.G
    out = {}
    samples = np.linspace(tilt_min, 0.0, 7)
    step = math.radians(abs(samples[1] - samples[0]))
    for name, (fr, P) in clouds.items():
        if fr == 'base' or not obstacles:
            continue
        keep = np.zeros(len(P), bool)
        if fr == 'pan':
            rho, z = np.hypot(P[:, 0], P[:, 1]), P[:, 2]
            for ob in obstacles:
                keep |= ring_bound(rho, z, ob) <= margin + 2.0
        else:
            Q0 = P + np.array([-G.tilt_x, 0.0, G.path_t])
            slack = np.hypot(Q0[:, 0], Q0[:, 2] - G.tilt_t) * step / 2
            for t in samples:
                Q = pose_points(T, P, fr, 0.0, float(t))
                rho, z = np.hypot(Q[:, 0], Q[:, 1]), Q[:, 2]
                for ob in obstacles:
                    keep |= ring_bound(rho, z, ob) - slack <= margin + 2.0
        if keep.any():
            out[name] = (fr, P[keep])
    return out


def study(T, clouds, obstacles, margin, pans, tilts, ball=True):
    """For every pan, the deepest tilt (most negative) at which every moving part keeps `margin` from every obstacle
    and, with `ball`, the ball's path from the muzzle keeps it from the obstacles marked 'ball'. Tilts are checked from
    0 down and the first failure ends a pan's search (clearance shrinks as the barrel drops)."""
    near = prune(T, clouds, obstacles, margin, min(tilts))
    rows = []
    for pan in pans:
        best, last = None, None
        for tilt in tilts:
            dmin, who = 1e9, None
            for name, (frame, P) in near.items():
                Q = pose_points(T, P, frame, pan, tilt)
                for ob in obstacles:
                    d = float(obstacle_distance(Q, ob).min())
                    if d < dmin:
                        dmin, who = d, f'{name} / {ob["name"]}'
            if ball:
                bp, br = ball_path(T, pan, tilt)
                for ob in obstacles:
                    if ob.get('ball', True):
                        d = float(obstacle_distance(bp, ob).min()) - br
                        if d < dmin:
                            dmin, who = d, f'ball path / {ob["name"]}'
            if dmin < margin:
                break
            best, last = tilt, (who, round(dmin, 1))
        rows.append({'pan': pan, 'max_depression_deg': best if best is not None else 'none: blocked at tilt 0', 'closest_at_limit': last})
    return rows, {k: len(P) for k, (_, P) in near.items()}


def scene_robot(x_l, top):
    """The robot: the VLP-16 in front of the turret on the deck below."""
    return [{'name': 'VLP-16', 'kind': 'cyl', 'x': x_l, 'y': 0.0, 'r': LIDAR['d'] / 2, 'z0': top - LIDAR['h'], 'z1': top, 'ball': True}]


def scene_box():
    """The Orin AGX box (cad/turret_box.py): the deck and the box under it as one block, the four upright antennas on the
    J501's bulkheads (if fitted), in the turret's frame (z up from the TM face, which is the deck's top)."""
    import turret_box as tb
    zt = tb.Z_TM
    obs = [{'name': 'deck and box', 'kind': 'box', 'lo': (tb.DECK_X[0], -tb.SIDE_Y, -zt), 'hi': (tb.DECK_X[1], tb.SIDE_Y, 0.0), 'ball': True}]
    for name, b, t, d in tb.antennas():
        obs.append({'name': name, 'kind': 'cyl', 'x': b[0], 'y': b[1], 'r': d / 2, 'z0': b[2] - zt, 'z1': t[2] - zt, 'ball': True})
    return obs


def keep_out_fire(pans, scene):
    """Pans where the turret may aim but must not fire. On the box the operator stands behind it (-x): no fire within
    60 deg of straight back. On the robot it is the body's business (the body is not designed yet)."""
    if scene == 'box':
        return [p for p in pans if abs(((p + 180.0) % 360.0) - 180.0) >= 120.0]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', choices=('robot', 'box'), default='robot')
    ap.add_argument('--x', type=float, default=None, help='robot: lidar centre ahead of the pan axis, mm')
    ap.add_argument('--top', type=float, default=LIDAR['h'] - DECK_BELOW_TM, help='robot: lidar top above the TM face, mm')
    ap.add_argument('--margin', type=float, default=10.0)
    ap.add_argument('--map', action='store_true', help='robot: the placement map (the lidar anywhere in front)')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
    G = T.G
    clouds = {}
    for name in list(T.meta) + list(T.bought):
        fr = T.frame[name]
        if name in ('dt_plug',):
            continue
        if fr == 'pinion':
            fr = 'base'                                          # the pinion stays inside the pan base's footprint
        clouds[name] = (fr, surface_points(T.local[name]))
    npts = sum(len(P) for _, P in clouds.values())
    tilts = [round(-0.5 * k, 1) for k in range(int(-G.tilt_min / 0.5) + 1)]
    pans = [float(p) for p in range(-180, 181, 2)]
    if a.scene == 'robot':
        x_l = a.x if a.x is not None else BUMPER_R + LIDAR['d'] / 2 + 10.0
        obstacles = scene_robot(x_l, a.top)
    else:
        obstacles = scene_box()
    static = {f'{k} / {ob["name"]}': round(float(obstacle_distance(P, ob).min()), 1) for k, (fr, P) in clouds.items() if fr == 'base'
              for ob in obstacles if ob['kind'] == 'cyl'}
    rows, kept = study(T, clouds, obstacles, a.margin, pans, tilts)
    limited = [r for r in rows if r['max_depression_deg'] != G.tilt_min]
    worst = max((r for r in limited if isinstance(r['max_depression_deg'], float)), key=lambda r: r['max_depression_deg'], default=None)
    window = [min(r['pan'] for r in limited), max(r['pan'] for r in limited)] if limited else None
    # a firmware table: the limit every 5 deg of pan, rounded towards safety (the shallower of the neighbours)
    table = []
    for p in range(-180, 181, 5):
        near = [r['max_depression_deg'] for r in rows if abs(r['pan'] - p) <= 5.0]
        near = [v if isinstance(v, float) else 0.0 for v in near]
        table.append({'pan_deg': p, 'min_tilt_deg': max(near) if near else G.tilt_min})
    res = {'scene': a.scene, 'obstacles': obstacles, 'margin_mm': a.margin, 'ball': {'d_mm': BALL_MAX_D, 'wild_deg': WILD_DEG, 'slowest_m_s': SLOW_MS},
           'turret': {'tilt_axis_above_tm_mm': G.tilt_t, 'ball_path_above_tm_mm': G.path_t, 'muzzle_ahead_of_pan_axis_mm': G.barrel_x1 - G.tilt_x,
                      'tilt_range_deg': [G.tilt_min, 0.0]},
           'fixed_parts_to_obstacles_mm': static, 'limited_pan_window_deg': window, 'worst': worst, 'firmware_table': table,
           'keep_out_fire_pan_deg': keep_out_fire(pans, a.scene), 'per_pan': rows,
           'points': {'sampled': npts, 'near_enough_to_check': kept},
           'how': 'surface samples of every panning and tilting part (~1.2 mm apart), the ones that can come within the margin at some '
                  'pose kept (a lower bound over pan and tilt), and the ball path; the limit is the deepest tilt in 0.5 deg steps that keeps the margin',
           'seconds': round(time.time() - t0)}
    if a.scene == 'robot':
        res['lidar'] = {**LIDAR, 'centre_x_mm': round(obstacles[0]['x'], 1), 'top_above_tm_mm': a.top, 'base_above_tm_mm': round(a.top - LIDAR['h'], 1)}
        if a.map:
            res['placement_map'] = placement_map(T, clouds, a.margin)
    name = 'lidar' if a.scene == 'robot' else 'box'
    (OUT / f'{name}.json').write_text(json.dumps(res, indent=1) + '\n')
    plots(T, res, name)
    print(f"{a.scene}: {len(obstacles)} obstacles; {npts} surface points, {sum(kept.values())} near enough to check; "
          f"limited at pans {window}; worst {worst}; {res['seconds']} s -> {OUT / (name + '.json')}")


def placement_map(T, clouds, margin):
    """The worst pan's depression limit for the lidar anywhere in front: x 120..260 mm, top -40..+80 mm."""
    xs = list(range(120, 261, 20))
    tops = list(range(-40, 81, 10))
    pans = [float(p) for p in range(-30, 31, 6)]
    tilts = [round(-1.0 * k, 1) for k in range(26)]
    grid = []
    for top in tops:
        row = []
        for x in xs:
            rows, _ = study(T, clouds, scene_robot(float(x), float(top)), margin, pans, tilts)
            row.append(max((r['max_depression_deg'] if isinstance(r['max_depression_deg'], float) else 0.0) for r in rows))
        grid.append(row)
        print(f'  map: top {top:+4d} mm -> ' + ' '.join(f'{v:6.1f}' for v in row), flush=True)
    return {'x_mm': xs, 'top_above_tm_mm': tops, 'worst_pan_limit_deg': grid,
            'note': 'the depression the worst pan in -30..30 deg allows (1 deg steps); -25 = no limit'}


def plots(T, res, name):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    G = T.G
    rows = res['per_pan']
    val = lambda v: v if isinstance(v, float) else 2.0
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
    ax.plot([r['pan'] for r in rows], [val(r['max_depression_deg']) for r in rows], color='#c2410c', lw=2)
    ax.axhline(G.tilt_min, color='#64748b', lw=1, ls='--')
    ax.axhline(0.0, color='#64748b', lw=1)
    for p in res.get('keep_out_fire_pan_deg', []):
        ax.axvspan(p - 1, p + 1, color='#dc2626', alpha=0.08, lw=0)
    ax.set_xlim(-180, 180)
    ax.set_ylim(G.tilt_min - 2, 2)
    ax.set_xlabel('pan (deg, 0 = forward)')
    ax.set_ylabel('deepest allowed tilt (deg)')
    if name == 'lidar':
        L = res['lidar']
        title = (f"Depression limit over the VLP-16 (centre {L['centre_x_mm']:.0f} mm ahead, top {L['top_above_tm_mm']:+.1f} mm; "
                 f"margin {res['margin_mm']:.0f} mm)")
    else:
        title = f"Depression limit on the Orin box (deck, antennas; margin {res['margin_mm']:.0f} mm); red: no firing (the operator's side)"
    ax.set_title(title, fontsize=9)
    ax.fill_between([r['pan'] for r in rows], [val(r['max_depression_deg']) for r in rows], 2, color='#16a34a', alpha=0.12, label='allowed')
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / f'{name}-limit.png')
    plt.close(fig)
    if 'placement_map' in res:
        m = res['placement_map']
        fig, ax = plt.subplots(figsize=(7.5, 5), dpi=130)
        A = np.array(m['worst_pan_limit_deg'])
        im = ax.imshow(A, origin='lower', aspect='auto', cmap='RdYlGn_r', vmin=G.tilt_min, vmax=0,
                       extent=[m['x_mm'][0] - 10, m['x_mm'][-1] + 10, m['top_above_tm_mm'][0] - 5, m['top_above_tm_mm'][-1] + 5])
        for i, top in enumerate(m['top_above_tm_mm']):
            for j, x in enumerate(m['x_mm']):
                ax.text(x, top, f'{A[i, j]:.0f}', ha='center', va='center', fontsize=7)
        ax.set_xlabel('lidar centre ahead of the pan axis (mm)')
        ax.set_ylabel('lidar top above the TM face (mm)')
        ax.set_title('Deepest tilt allowed at the worst pan (deg; -25 = the full range)', fontsize=9)
        fig.colorbar(im, ax=ax, label='deg')
        fig.tight_layout()
        fig.savefig(OUT / 'lidar-map.png')
        plt.close(fig)


if __name__ == '__main__':
    main()
