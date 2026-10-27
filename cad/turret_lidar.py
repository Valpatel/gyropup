"""The turret firing over the VLP-16 lidar in front of it: clearance of the barrel, the cartridge and the ball's path at
every pan and tilt, the pan-dependent depression limit that keeps them clear, and where the lidar may sit.

    .venv/bin/python cad/turret_lidar.py [--x 150] [--top 43.7] [--margin 10]

The layout (user, 2026-10-26): on the robot the turret sits behind the VLP-16 on the top deck and fires over it. The
body is not designed yet, so the lidar's place is a parameter: its centre `x` mm ahead of the pan axis on the
turret's centre line, its top `top` mm above the turret's mounting face (TM). Baseline: the lidar stands on the body's
top deck, which is the head ring's 28 mm below the TM face (cad/turret.py: mount_z = bodyTop + 20 + 8), so its top is
71.7 - 28 = 43.7 mm above the TM face, and its centre is as close behind the turret's TPU bumper ring (R 86) as a
10 mm gap allows: x = 86 + 51.65 + 10 = 148 mm.

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
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402

OUT = R / 'exports' / 'turret' / 'lidar'
LIDAR = {'d': 103.3, 'h': 71.7, 'model': 'Velodyne VLP-16 (Puck)', 'source': 'VLP-16 user manual: Ø103.3 x 71.7 mm'}
DECK_BELOW_TM = 20.0 + tu.SADDLE_T            # the head ring raises the TM face 28 mm above the body's top deck
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


def _corners(P):
    lo, hi = P.min(axis=0), P.max(axis=0)
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def study(T, clouds, x_l, top, margin, pans, tilts):
    """For every pan, the deepest tilt (most negative) at which every moving part and the ball path keep `margin`
    from the lidar; also the closest part at that limit. Tilts are checked from 0 down and the first failure ends a
    pan's search (clearance shrinks as the barrel drops). A part whose posed bounding box is farther than the margin
    plus 20 mm is not sampled point by point (its box bounds it)."""
    r_l, z0, z1 = LIDAR['d'] / 2, top - LIDAR['h'], top
    moving = {k: (fr, P, _corners(P)) for k, (fr, P) in clouds.items() if fr != 'base'}
    rows = []
    for pan in pans:
        best = 0.0
        last = None
        for tilt in tilts:
            dmin, who = 1e9, None
            for name, (frame, P, box8) in moving.items():
                Bq = pose_points(T, box8, frame, pan, tilt)
                lo, hi = Bq.min(axis=0), Bq.max(axis=0)
                # distance from the lidar cylinder's bounding box to the part's: a lower bound
                gap = max(lo[0] - (x_l + r_l), (x_l - r_l) - hi[0], lo[1] - r_l, -r_l - hi[1], lo[2] - z1, z0 - hi[2], 0.0)
                if gap > margin + 20.0:
                    if gap < dmin:
                        dmin, who = gap, name + ' (box)'
                    continue
                Q = pose_points(T, P, frame, pan, tilt)
                d = float(cyl_distance(Q, x_l, 0.0, r_l, z0, z1).min())
                if d < dmin:
                    dmin, who = d, name
            bp, br = ball_path(T, pan, tilt)
            db = float(cyl_distance(bp, x_l, 0.0, r_l, z0, z1).min()) - br
            if db < dmin:
                dmin, who = db, 'ball path'
            if dmin < margin:
                break
            best, last = tilt, (who, round(dmin, 1))
        rows.append({'pan': pan, 'max_depression_deg': best, 'closest_at_limit': last})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--x', type=float, default=None, help='lidar centre ahead of the pan axis, mm')
    ap.add_argument('--top', type=float, default=LIDAR['h'] - DECK_BELOW_TM, help='lidar top above the TM face, mm')
    ap.add_argument('--margin', type=float, default=10.0)
    ap.add_argument('--no-map', action='store_true')
    a = ap.parse_args()
    x_l = a.x if a.x is not None else BUMPER_R + LIDAR['d'] / 2 + 10.0
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
    print(f'lidar {LIDAR["model"]} Ø{LIDAR["d"]} x {LIDAR["h"]} at x = {x_l:.1f} mm, top {a.top:+.1f} mm from the TM face; '
          f'{len(clouds)} parts, {npts} surface points; margin {a.margin} mm')
    r_l = LIDAR['d'] / 2
    static = {k: round(float(cyl_distance(P, x_l, 0.0, r_l, a.top - LIDAR['h'], a.top).min()), 1) for k, (fr, P) in clouds.items() if fr == 'base'}
    print('fixed parts to the lidar (mm):', static)
    tilts = [round(-0.5 * k, 1) for k in range(int(-G.tilt_min / 0.5) + 1)]
    pans = [float(p) for p in range(-180, 181, 2)]
    rows = study(T, clouds, x_l, a.top, a.margin, pans, tilts)
    limited = [r for r in rows if r['max_depression_deg'] > G.tilt_min]
    if limited:
        window = [min(r['pan'] for r in limited), max(r['pan'] for r in limited)]
        worst = max(limited, key=lambda r: r['max_depression_deg'])
    else:
        window, worst = None, None
    print(f"full depression ({G.tilt_min:.0f} deg) everywhere except pan {window}; at pan {worst['pan'] if worst else '-'} "
          f"only to {worst['max_depression_deg'] if worst else '-'} deg ({worst['closest_at_limit'] if worst else ''})")
    # a firmware table: the limit every 5 deg of pan inside the window, rounded towards safety (up) to 0.5 deg
    table = []
    if limited:
        for p in range(int(math.floor(window[0] / 5.0)) * 5 - 5, int(math.ceil(window[1] / 5.0)) * 5 + 10, 5):
            near = [r['max_depression_deg'] for r in rows if abs(r['pan'] - p) <= 5.0]
            table.append({'pan_deg': p, 'min_tilt_deg': max(near) if near else G.tilt_min})
    res = {'lidar': {**LIDAR, 'centre_x_mm': round(x_l, 1), 'top_above_tm_mm': a.top, 'base_above_tm_mm': round(a.top - LIDAR['h'], 1)},
           'margin_mm': a.margin, 'ball': {'d_mm': BALL_MAX_D, 'wild_deg': WILD_DEG, 'slowest_m_s': SLOW_MS},
           'turret': {'tilt_axis_above_tm_mm': G.tilt_t, 'ball_path_above_tm_mm': G.path_t, 'muzzle_ahead_of_pan_axis_mm': G.barrel_x1 - G.tilt_x,
                      'tilt_range_deg': [G.tilt_min, 0.0]},
           'fixed_parts_to_lidar_mm': static, 'limited_pan_window_deg': window, 'worst': worst, 'firmware_table': table, 'per_pan': rows,
           'how': 'surface samples of every panning and tilting part (~1.2 mm apart) and the ball path, distance to the lidar cylinder; '
                  'the limit is the deepest tilt in 0.5 deg steps that keeps the margin'}
    if not a.no_map:
        res['placement_map'] = placement_map(T, clouds, a.margin)
    (OUT / 'lidar.json').write_text(json.dumps(res, indent=1) + '\n')
    plots(T, res)
    print('wrote', OUT / 'lidar.json')


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
            rows = study(T, clouds, float(x), float(top), margin, pans, tilts)
            row.append(max(r['max_depression_deg'] for r in rows))
        grid.append(row)
        print(f'  map: top {top:+4d} mm -> ' + ' '.join(f'{v:6.1f}' for v in row))
    return {'x_mm': xs, 'top_above_tm_mm': tops, 'worst_pan_limit_deg': grid,
            'note': 'the depression the worst pan in -30..30 deg allows (1 deg steps); -25 = no limit'}


def plots(T, res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    G = T.G
    rows = res['per_pan']
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
    ax.plot([r['pan'] for r in rows], [r['max_depression_deg'] for r in rows], color='#c2410c', lw=2)
    ax.axhline(G.tilt_min, color='#64748b', lw=1, ls='--')
    ax.axhline(0.0, color='#64748b', lw=1)
    ax.set_xlim(-180, 180)
    ax.set_ylim(G.tilt_min - 2, 2)
    ax.set_xlabel('pan (deg, 0 = straight over the lidar)')
    ax.set_ylabel('deepest allowed tilt (deg)')
    L = res['lidar']
    ax.set_title(f"Depression limit over the VLP-16 (centre {L['centre_x_mm']:.0f} mm ahead, top {L['top_above_tm_mm']:+.1f} mm; margin {res['margin_mm']:.0f} mm)", fontsize=9)
    ax.fill_between([r['pan'] for r in rows], [r['max_depression_deg'] for r in rows], 2, color='#16a34a', alpha=0.12, label='allowed')
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / 'lidar-limit.png')
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
