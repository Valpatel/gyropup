"""The wheel harness through the five-bar leg (leg v2, cad/fivebar.py), checked over the leg's range of motion
(docs/mechanical-interfaces.md, cable rules).

Harnesses (left leg; the right is the mirror image):
  wheel        the BotWheel's phases (3 x 18 AWG) and hall/encoder lead, sleeved together (fivebar.CABLE_D). Its route is
               fivebar.cable(): out of the hub's inner end at the axle, out under the apex eye, along the wheel
               link's outer edge, round the outside of the rear knee, along the rear upper link's outer edge, and into
               the body 90 mm from the hip axis, past the stop posts and the hip frame's edge. The wrap at the knee and
               the loop where it leaves the rear upper link take the joints' swing.
  front, rear  each RS-04's power (XT30) and CAN leave its rear cover on the hip frame. The motors do not move with the
               links, so neither lead crosses a moving joint.

For each stance from crouch to tall (fivebar.stance) it measures the wheel harness's length along its route (the spread
is what the knee wrap and the hip loop must give) and its tightest bend against 10 x the conductor's OD (rule 3).
With --clash it also sweeps the cable and lists the parts it runs into (fivebar.cable_check, a few minutes of CAD).
Writes exports/leg/cables.json and exports/leg/cables.png (side views at three stances).

    .venv/bin/python tools/leg_cables.py [--clash]

The route is a drawn spline to try on the rig, not a measured cable: a real harness finds its own path, and the
clips (rule 4) are not drawn. cad/cables.py is the serial leg's check (the harness inside the thigh and shin boxes,
rev 0.1, historical); its numbers stay in docs/mechanical-interfaces.md's rev 0.2 results. This one lives in tools/
because receipts pin cad/'s sources (tools/test-rs04-lug-stacks.py and the carrier checks).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import fivebar as fb  # noqa: E402

CONDUCTOR_OD = {'wheel': 2.0}           # 18 AWG silicone phase wire, the thickest single conductor in the harness
SAMPLES = 2000                          # points along the route (by length) for its bends
CLASH_HEIGHTS = (105, 130, 170, 220, 270, 320, 370, 390)


def heights(n=7):
    """n stances from just above the lowest the stops allow to just under the highest (mm, hip line to axle)."""
    lo = -fb.fk(*fb.stop_angles()[0::2])['E'][1]
    hi = -fb.fk(*fb.stop_angles()[1::2])['E'][1]
    lo, hi = math.ceil(lo + 2.0), math.floor(hi - 2.0)
    return [round(lo + (hi - lo) * k / (n - 1), 1) for k in range(n)]


def cable_points(phi):
    """The waypoints of the spline fivebar.cable() sweeps at a pose, [(x, y, z)] in mm. fivebar.py draws them inside
    cable() and receipts pin that file's hash (exports/sim/v2/leg-attachments, exports/leg/rs04-mounting-fit), so the
    route is read from the call rather than split out of it: the same route the clash check sweeps, by construction."""
    import cadquery as cq
    seen = []
    spline = cq.Workplane.spline

    def spy(self, points, *args, **kwargs):
        seen.append([tuple(float(v) for v in p) for p in points])
        return spline(self, points, *args, **kwargs)
    cq.Workplane.spline = spy
    try:
        fb.cable(*phi)
    except Exception:                    # a sweep that does not close: the route was still drawn
        pass
    finally:
        cq.Workplane.spline = spline
    if len(seen) != 1:
        raise RuntimeError(f'fivebar.cable() drew {len(seen)} splines, expected one: update cable_points() in tools/leg_cables.py')
    return seen[0]


def route(h):
    """The harness at a stance: the joint positions (x, z), the waypoints, points sampled along the spline (mm), its
    length and its tightest bend (OCC's curvature along the spline, SAMPLES points by length)."""
    import cadquery as cq
    phi = fb.stance(h)
    if phi is None:
        raise ValueError(f'no stance at {h} mm')
    _, j = fb.link_frames(*phi)
    pts = cable_points(phi)
    edge = cq.Edge.makeSpline([cq.Vector(*p) for p in pts])
    ts = np.linspace(0.0, 1.0, SAMPLES)
    samples = np.array([edge.positionAt(t).toTuple() for t in ts])
    k = np.array([edge.curvatureAt(t) for t in ts])
    i = int(np.argmax(k))
    return {'phi': phi, 'joints': j, 'waypoints': np.array(pts), 'samples': samples,
            'length': float(edge.Length()), 'min_bend_r': float(1.0 / k[i]) if k[i] > 0 else math.inf, 'tightest_at': samples[i]}


def check(clash=False):
    rows = []
    for h in heights():
        r = route(h)
        rmin, at = r['min_bend_r'], r['tightest_at']
        rows.append({'height_mm': h, 'phi_deg': [round(math.degrees(v), 1) for v in r['phi']], 'length_mm': round(r['length'], 1),
                     'min_bend_radius_mm': round(rmin, 1), 'tightest_at_mm': [round(float(v), 1) for v in at], '_r': r})
    lengths = [x['length_mm'] for x in rows]
    need = 10 * CONDUCTOR_OD['wheel']
    tightest = min(x['min_bend_radius_mm'] for x in rows)
    # Where the tightest bend is, from the route itself: at how many stances its nearest waypoint is the third from the
    # end (where the route turns off the rear upper link into the body), and how far the waypoints either side are.
    n_end, gaps = 0, []
    for x in rows:
        wp, at = x['_r']['waypoints'], np.asarray(x['_r']['tightest_at'])
        k = int(np.argmin(np.linalg.norm(wp - at, axis=1)))
        n_end += k == len(wp) - 3
        gaps.append([np.linalg.norm(wp[k] - wp[k - 1]) if k else 0.0, np.linalg.norm(wp[k + 1] - wp[k]) if k + 1 < len(wp) else 0.0])
    gaps = np.array(gaps)
    res = {
        'leg': 'five-bar (leg v2, cad/fivebar.py): l1 {l1:.0f} mm, l2 {l2:.0f} mm, motors {D:.0f} mm apart'.format(**fb.P),
        'wheel': {
            'route': 'hub (inner end, at the axle) -> under the apex eye -> along the wheel link\'s outer edge -> round the '
                     'outside of the rear knee -> along the rear upper link\'s outer edge -> into the body 90 mm from the '
                     'hip axis (fivebar.cable)',
            'cable_d_mm': fb.CABLE_D,
            'stances': [{k: v for k, v in x.items() if k != '_r'} for x in rows],
            'length_mm': {'min': min(lengths), 'max': max(lengths), 'slack_needed_mm': round(max(lengths) - min(lengths), 1),
                          'note': 'the spread over the stances: what the knee wrap and the loop at the hip must give'},
            'bend_radius': {'min_mm': tightest, 'needed_mm': need, 'ok': tightest >= need,
                            'note': 'the drawn spline\'s tightest bend, against 10 x the 18 AWG conductor (rule 3, flexing). At '
                                    f'{n_end} of {len(rows)} stances it is at fivebar.cable()\'s third waypoint from the end, '
                                    'where the route turns off the rear upper link\'s edge into the body (the waypoints '
                                    f'either side are {gaps[:, 0].min():.1f} and {gaps[:, 1].min():.1f} mm from it, at the '
                                    'closest): the drawn route needs a wider turn there before it is a harness drawing'},
            'lead_length': {'botwheel_lead_mm': 300, 'route_max_mm': max(lengths),
                            'note': 'the BotWheel\'s own lead is 300 mm; the route ends where it enters the body, so the '
                                    'run on to the motor driver inside is extra'},
        },
        'front': {'route': 'rear cover (XT30 + CAN) on the hip frame -> into the body', 'crosses_joint': False},
        'rear': {'route': 'rear cover (XT30 + CAN) on the hip frame -> into the body', 'crosses_joint': False},
        'limits': 'a drawn route, not a measured cable: clips are not drawn, and the rig decides (docs/mechanical-interfaces.md)',
    }
    if clash:
        hits = fb.cable_check(CLASH_HEIGHTS)
        res['wheel']['clash'] = {'heights_mm': list(CLASH_HEIGHTS), 'hits': {str(h): v for h, v in hits.items()},
                                 'ok': not any(hits.values()),
                                 'note': 'parts the swept Ø{:.0f} cable runs into (> 5 mm3), motors and the hub left out'.format(fb.CABLE_D)}
    exports = (Path(os.environ['GYROPUP_EXPORTS']).resolve() if os.environ.get('GYROPUP_EXPORTS') else R / 'exports') / 'leg'
    exports.mkdir(parents=True, exist_ok=True)
    (exports / 'cables.json').write_text(json.dumps(res, indent=1) + '\n')
    _plot(rows, exports / 'cables.png')
    return res


def _plot(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    picks = (rows[0], rows[len(rows) // 2], rows[-1])
    fig, axs = plt.subplots(1, 3, figsize=(12, 5.2), dpi=96)
    wheel_r = (fb.gmi.motor_interface(fb.WHEEL)['od'] or 171.3) / 2
    for ax, x in zip(axs, picks):
        r = x['_r']
        j = r['joints']
        for a, b in (('A', 'C'), ('B', 'D')):
            ax.plot([j[a][0], j[b][0]], [j[a][1], j[b][1]], color='#f5b82e', lw=9, solid_capstyle='round', alpha=0.75)
        for a, b in (('C', 'E'), ('D', 'E')):
            ax.plot([j[a][0], j[b][0]], [j[a][1], j[b][1]], color='#e9a21f', lw=7, solid_capstyle='round', alpha=0.75)
        ax.plot([], [], color='#f5b82e', lw=6, label='upper links (on the motors)')
        ax.plot([], [], color='#e9a21f', lw=5, label='front and wheel links (to the axle)')
        for m in ('A', 'B'):
            ax.add_patch(plt.Circle(j[m], 60, fill=False, color='#888', ls='--'))
        ax.add_patch(plt.Circle(j['E'], wheel_r, fill=False, color='#333'))
        s = r['samples']
        ax.plot(s[:, 0], s[:, 2], color='#00a0c0', lw=2, label='wheel harness')
        ax.scatter(*x['tightest_at_mm'][0::2], color='#ff2a6d', zorder=5, s=22, label='tightest bend')
        ax.set_aspect('equal')
        ax.set_title(f"height {x['height_mm']:.0f} mm: {x['length_mm']:.0f} mm, bend r {x['min_bend_radius_mm']:.1f} mm", fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_xlim(-260, 260)
        ax.set_ylim(-500, 120)
    axs[0].legend(loc='lower left', fontsize=7)
    fig.suptitle('Wheel harness along the five-bar leg (side view, x forward, z up); dashed: the two hip motors')
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--clash', action='store_true', help='also sweep the cable and list the parts it runs into (slow)')
    w = check(clash=ap.parse_args().clash)['wheel']
    print('length', w['length_mm'])
    print('bend radius', w['bend_radius'])
    if 'clash' in w:
        print('clash', 'none' if w['clash']['ok'] else w['clash']['hits'])
