"""Cable routing for the leg, checked over the leg's whole range of motion (docs/mechanical-interfaces.md, rules).

Harnesses (left leg; the right is the mirror image):
  wheel   the wheel motor's phases (3 x 18 AWG) and hall/encoder lead. It leaves the middle of the wheel's boss, goes
          through the wheel adapter into the shin box, up inside it to a port on the shin's back face near the knee,
          across the knee in a service loop to a port on the thigh's back face, up inside the thigh to a port near
          the hip, across the hip in a second loop into the yoke below and behind the axis (the spacer posts are all
          above it), round the back of the hip motor plate and along the hip motor to the cable pass in the wall. The BotWheel's own lead is 300 mm, so an extension joins it at the shin port (its JST WPJ
          3-pin and JWPF 8-pin waterproof connectors sit inside the shin's top end).
  hip     the hip motor's power (XT30) and CAN (GH1.25): its connectors are on the rear cover, inboard, so the lead
          goes straight through the body wall's cable pass; it never crosses a moving joint.
  knee    the knee motor's power and CAN: from its rear cover (outboard) up and over under the yoke deck to the
          cable pass; fixed to the yoke, so it never crosses a moving joint either.

Checks over the whole range (stand to full crouch, with the look-up lean): the length change across each joint
(the service loop must take it), the loop's bend radius against each conductor's minimum, and the clearance from
every part the cable does not ride on. Writes exports/cables.json and exports/cables.png (side views of the
routes at three poses).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import leg  # noqa: E402

CABLES = leg.STD['cables']
# the thickest single conductor in each harness sets the flexing bend radius (rule 3: 10 x OD)
CONDUCTOR_OD = {'wheel': 2.0, 'hip': 3.2, 'knee': 3.2}      # 18 AWG silicone; 14 AWG silicone
CP_Z = 20.0          # the cable pass through the yoke wall plate and the tray wall: (x = -40, z = 20), Ø18 grommet


def rot_y(p, c, ang):
    """Rotate points p (N x 3) about the axis through c along +y by ang (the same sense as the CAD's rotate)."""
    p = np.asarray(p, float) - c
    ca, sa = math.cos(ang), math.sin(ang)
    # CadQuery's rotate about +y: x' = x cos + z sin, z' = -x sin + z cos
    out = np.stack([p[:, 0] * ca + p[:, 2] * sa, p[:, 1], -p[:, 0] * sa + p[:, 2] * ca], axis=1)
    return out + c


def route(S, L, hip, knee):
    """Waypoints of the wheel harness in the robot frame at a pose (hip, knee in radians, the CAD's sense)."""
    a, b = L['thigh'], L['shin']
    yt, ys = sum(S.y['thigh']) / 2, sum(S.y['shin']) / 2
    xb = -leg.LINK_W / 2 + 6                                   # inside the box, near its back wall
    kc = leg.STD['KC']['hub_od'] / 2
    shin_pts = np.array([[0, S.y['wheel_mount'], -a - b], [0, S.y['shin'][1] - 4, -a - b], [xb, ys, -a - b + 30],
                         [xb, ys, -a - kc - 18], [-leg.LINK_W / 2 - 4, ys, -a - kc - 18]])          # ... out of the shin port
    thigh_pts = np.array([[-leg.LINK_W / 2 - 4, yt, -a + kc + 18], [xb, yt, -a + kc + 18],
                          [xb, yt, -36 - 18], [-leg.LINK_W / 2 - 4, yt, -36 - 18]])                  # ... out of the hip port
    # into the yoke below and behind the axis (the posts are all above it), round the back of the hip motor plate,
    # along the hip motor and into the low cable pass in the yoke's wall plate
    yoke_pts = np.array([[-72, S.y['hip_plate'][1] + 6, -35], [-72, S.y['hip_plate'][0] - 6, -35],
                         [-62, S.y['bracket'][1] + 2, CP_Z], [-40, S.y['bracket'][0], CP_Z]])
    # shin points: knee rotation then hip; thigh points: hip; yoke points: fixed to the body
    sp = rot_y(rot_y(shin_pts, np.array([0, 0, -a]), knee), np.zeros(3), hip)
    tp = rot_y(thigh_pts, np.zeros(3), hip)
    return {'shin': sp, 'thigh': tp, 'yoke': yoke_pts}


def poses(L, n=7):
    from sim.controller import hip_for, knee_for
    a, b = L['thigh'] / 1000, L['shin'] / 1000
    lo, hi = math.radians(L['kneeMinDeg']), math.radians(L['kneeMaxDeg'])
    hmin = math.sqrt(a * a + b * b - 2 * a * b * math.cos(lo))
    hmax = math.sqrt(a * a + b * b - 2 * a * b * math.cos(hi))
    out = []
    for k in range(n):
        h = hmin + (hmax - hmin) * k / (n - 1)
        for look in (0.0, 0.35):                               # the look-up lean adds to the hip angle
            out.append((k / (n - 1), look, hip_for(a, b, h) + look, knee_for(a, b, h) - math.pi))
    return out


def check(design: Path):
    L = json.loads(subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True).stdout)['layout']
    d = json.loads(design.read_text())
    parts, meta, bought, S, _ = leg.leg_parts(L, d['parts']['leg_actuator'], d['parts']['leg_actuator'], d['parts']['wheel_motor'])
    a = L['thigh']
    knee_cross, hip_cross, samples = [], [], []
    for frac, look, hip, knee in poses(L):
        r = route(S, L, hip, knee)
        knee_cross.append(float(np.linalg.norm(r['shin'][-1] - r['thigh'][0])))     # straight distance between the ports
        hip_cross.append(float(np.linalg.norm(r['thigh'][-1] - r['yoke'][0])))
        samples.append((frac, look, hip, knee, r))
    # a loose loop around each joint: its radius is set by the ports' distance from the axis
    kc = leg.STD['KC']['hub_od'] / 2
    knee_r = math.hypot(leg.LINK_W / 2 + 4, kc + 18)
    hip_r = math.hypot(leg.LINK_W / 2 + 4, 36 + 18)
    res = {
        'wheel': {
            'route': 'wheel boss -> wheel adapter -> inside the shin -> shin port -> knee loop -> thigh port -> inside the thigh -> hip port -> hip loop -> under the yoke deck -> body cable pass',
            'knee': {'port_distance_mm': round(knee_r, 1), 'straight_min_mm': round(min(knee_cross), 1), 'straight_max_mm': round(max(knee_cross), 1),
                     'slack_needed_mm': round(max(knee_cross) - min(knee_cross), 1),
                     'loop': f'a loose loop of about {round(max(knee_cross) + 20)} mm between the ports, around the knee hub'},
            'hip': {'port_distance_mm': round(hip_r, 1), 'straight_min_mm': round(min(hip_cross), 1), 'straight_max_mm': round(max(hip_cross), 1),
                    'slack_needed_mm': round(max(hip_cross) - min(hip_cross), 1),
                    'loop': f'a loose loop of about {round(max(hip_cross) + 20)} mm between the thigh port and the yoke clip'},
            'bend_radius': {'loop_radius_mm': round(min(knee_r, hip_r), 1), 'needed_mm': 10 * CONDUCTOR_OD['wheel'],
                            'ok': min(knee_r, hip_r) >= 10 * CONDUCTOR_OD['wheel'],
                            'note': 'conductors loose (not a stiff jacketed cable) through the loops; a jacketed 10 mm cable would need 75-100 mm'},
            'lead_length': {'botwheel_lead_mm': 300, 'path_mm': None, 'extension': None},
        },
        'hip': {'route': 'rear cover connectors -> body wall cable pass', 'crosses_joint': False},
        'knee': {'route': 'rear cover connectors (outboard) -> up the knee plate -> under the yoke deck -> body cable pass', 'crosses_joint': False},
    }
    # the harness length at the standing pose, to size the extension from the BotWheel's 300 mm lead
    stand = [s for s in samples if s[0] == 1.0 and s[1] == 0.0][0][4]
    pts = np.vstack([stand['shin'], stand['thigh'], stand['yoke']])
    path = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))) + 2 * 20       # plus the two loops' extra
    res['wheel']['lead_length'].update(path_mm=round(path), extension=f'{round(path - 300 + 150, -1):.0f} mm extension (to the driver in the body, with 150 mm spare), joined inside the shin top')
    # clearance from parts the cable does not ride inside: sample the joint-crossing loops against the meshes
    import trimesh
    meshes = {}
    for name in ('knee_crank', 'pushrod', 'yoke_bracket', 'hip_motor_plate', 'knee_motor_plate', 'posts'):
        shp = parts.get(name) if name in parts else bought.get(name)
        if shp is None:
            continue
        vs, fs = shp.val().tessellate(0.5, 0.3)
        meshes[name] = trimesh.Trimesh([(v.x, v.y, v.z) for v in vs], fs)
    import leg as _leg
    worst = {}
    for frac, look, hip, knee, r in samples:
        segs = [r['shin'][-1], r['thigh'][0], r['thigh'][-1], r['yoke'][0]]
        line = np.vstack([np.linspace(segs[0], segs[1], 12), np.linspace(segs[2], segs[3], 12)])
        for name, m in meshes.items():
            mp = _leg.pose(_shape_of(name, parts, bought), name, math.radians(0) + hip, knee, a, leg.STD['PR']['crank_r']) if name in ('knee_crank', 'pushrod') else None
            mm = m
            if mp is not None:
                vs, fs = mp.val().tessellate(0.5, 0.3)
                mm = trimesh.Trimesh([(v.x, v.y, v.z) for v in vs], fs)
            dist = trimesh.proximity.ProximityQuery(mm).signed_distance(line)
            dmin = float(-dist.max())                          # trimesh: positive inside, so the clearance is -max
            if name not in worst or dmin < worst[name]['clearance_mm']:
                worst[name] = {'clearance_mm': round(dmin, 1), 'at': {'height': round(frac, 2), 'look_up': look}}
    res['wheel']['clearance'] = worst
    res['wheel']['clearance_ok'] = all(v['clearance_mm'] >= 5 for v in worst.values())
    out = R / 'exports' / 'cables.json'
    out.write_text(json.dumps(res, indent=1) + '\n')
    _plot(samples, S, L, R / 'exports' / 'cables.png')
    return res


def _shape_of(name, parts, bought):
    return parts.get(name) if name in parts else bought.get(name)


def _plot(samples, S, L, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a, b = L['thigh'], L['shin']
    fig, axs = plt.subplots(1, 3, figsize=(12, 5), dpi=110)
    picks = [s for s in samples if s[1] == 0.0]
    for ax, s in zip(axs, (picks[0], picks[len(picks) // 2], picks[-1])):
        frac, look, hip, knee, r = s
        knee_pt = rot_y(np.array([[0, 0, -a]]), np.zeros(3), hip)[0]
        wheel_pt = rot_y(rot_y(np.array([[0, 0, -a - b]]), np.array([0, 0, -a]), knee), np.zeros(3), hip)[0]
        ax.plot([0, knee_pt[0], wheel_pt[0]], [0, knee_pt[2], wheel_pt[2]], color='#f5b82e', lw=10, solid_capstyle='round', alpha=0.6, label='thigh and shin')
        ax.add_patch(plt.Circle((wheel_pt[0], wheel_pt[2]), L['wheelR'], fill=False, color='#333'))
        ax.add_patch(plt.Circle((0, 0), 50, fill=False, color='#888', ls='--'))
        pts = np.vstack([r['shin'], r['thigh'], r['yoke']])
        ax.plot(pts[:, 0], pts[:, 2], color='#00a0c0', lw=2, label='wheel harness')
        ax.scatter([r['shin'][-1][0], r['thigh'][0][0], r['thigh'][-1][0]], [r['shin'][-1][2], r['thigh'][0][2], r['thigh'][-1][2]], color='#ff2a6d', zorder=5, s=18, label='ports (loops between)')
        ax.set_aspect('equal'); ax.set_title(f'height {frac:.0%}'); ax.grid(alpha=0.3)
        ax.set_xlim(-250, 250); ax.set_ylim(-480, 150)
    axs[0].legend(loc='lower left', fontsize=7)
    fig.suptitle('Wheel harness through the leg (side view, x forward, z up); dashed: the hip motor')
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    r = check(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else R / 'designs/default.json')
    w = r['wheel']
    print('knee loop slack', w['knee']['slack_needed_mm'], 'mm; hip loop slack', w['hip']['slack_needed_mm'], 'mm')
    print('bend radius', w['bend_radius'])
    print('lead', w['lead_length'])
    print('clearance', w['clearance'], 'ok' if w['clearance_ok'] else 'TOO CLOSE')
