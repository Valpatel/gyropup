"""Pictures that explain the leg module: how its two motors move the leg (docs/mechanical-interfaces.md).

    .venv/bin/python tools/leg_explainer.py [designs/default.json] [--actuator robstride-rs-04] [--video]

Writes exports/explain/leg-module.png (labelled, standing), leg-hip.png / leg-knee.png (what each motor does) and,
with --video, leg-motors.mp4: the hip motor alone, then the knee motor alone, then both (crouch to stand).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import gmi  # noqa: E402
import leg  # noqa: E402
from cadagent.render import Renderer  # noqa: E402

OUT = R / 'exports' / 'explain'
COL = {
    'hip_motor': (0.85, 0.42, 0.10), 'knee_motor': (0.13, 0.45, 0.80),
    'hip_motor_plate': (0.55, 0.57, 0.60), 'knee_motor_plate': (0.55, 0.57, 0.60), 'posts': (0.40, 0.42, 0.45),
    'yoke_bracket': (0.45, 0.47, 0.50), 'hip_output_adapter': (0.95, 0.62, 0.30), 'knee_output_adapter': (0.40, 0.65, 0.95),
    'thigh': (0.95, 0.62, 0.30), 'knee_crank': (0.40, 0.65, 0.95), 'pushrod': (0.20, 0.55, 0.95),
    'shin': (0.30, 0.70, 0.95), 'wheel_adapter': (0.30, 0.70, 0.95), 'wheel': (0.16, 0.17, 0.19),
    'chassis_wall': (0.80, 0.82, 0.85, 0.35),
}
VIEW = (1.0, 0.42, 0.28)          # from the front, a little outside and above the left leg: both motors in a row


def setup(design: Path, actuator: str | None):
    d = json.loads(design.read_text())
    act = actuator or d['parts']['leg_actuator']
    L = json.loads(subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True).stdout)['layout']
    parts, meta, bought, S, _ = leg.leg_parts(L, act, act, d['parts']['wheel_motor'])
    env = {'hip_motor': gmi.place(_envelope(act), (0, S.y['hip_out'], 0), (0, 1, 0)),
           'knee_motor': gmi.place(_envelope(act), (0, S.y['knee_out'], 0), (0, -1, 0))}
    shapes = {**parts, **env, 'posts': bought['posts'], 'pushrod': bought['pushrod'], 'wheel': bought['wheel']}
    import cadquery as cq
    T = L['tray']
    shapes['chassis_wall'] = cq.Workplane('XY').box(T['depth'], 4, 110).translate((0, S.y['wall'] - 2, 30))
    return L, S, shapes, act


def _envelope(part_id):
    mi = gmi.motor_interface(part_id)
    od, Lm = mi['od'] or 100.0, mi['length'] or 50.0
    off = mi['output']['face_offset'] if mi['output'] else 0.0
    front = mi['case']['spigot_d'] or od * 0.7
    body = gmi._cyl(od / 2, -Lm, -off).union(gmi._cyl(front / 2, -off, 0.0))
    return body.edges('%CIRCLE').fillet(2.0) if False else body


def posed(L, shapes, hip, knee):
    return {n: leg.pose(s, n, hip, knee, L['thigh'], leg.PARAMS['crank_r']) for n, s in shapes.items()}


def stand(L, frac):
    from sim.controller import hip_for, knee_for
    a, b = L['thigh'] / 1000, L['shin'] / 1000
    lo, hi = math.radians(L['kneeMinDeg']), math.radians(L['kneeMaxDeg'])
    hmin, hmax = (math.sqrt(a * a + b * b - 2 * a * b * math.cos(g)) for g in (lo, hi))
    h = hmin + frac * (hmax - hmin)
    return hip_for(a, b, h), knee_for(a, b, h) - math.pi


def items(P, dim=()):
    out = []
    for n, s in P.items():
        c = COL.get(n, (0.6, 0.6, 0.6))
        if n in dim:
            c = (*c[:3], 0.18)
        out.append((s.val() if hasattr(s, 'val') else s, c))
    return out


def label_points(L, S, hip, knee):
    """World points to point the callouts at, posed."""
    a = L['thigh']
    cr = leg.PARAMS['crank_r']
    x0, z0 = leg.lever_pin(cr)
    th = hip + knee
    pin = (x0 * math.cos(th) + z0 * math.sin(th), -x0 * math.sin(th) + z0 * math.cos(th))
    rot = lambda x, z, q: (x * math.cos(q) + z * math.sin(q), -x * math.sin(q) + z * math.cos(q))
    kx, kz = rot(0, -a, hip)
    mid_rod = (pin[0] + kx / 2 + 0, sum(S.y['rod']) / 2, pin[1] + kz / 2)
    tx, tz = rot(0, -a * 0.55, hip)
    sx, sz = rot(*rot(0, -L['shin'] * 0.5, knee), hip)
    wx, wz = rot(*rot(0, -L['shin'], knee), hip)
    od = S.hip['od'] or 106
    return {
        'hip': (od / 2 * 0.85, sum(S.y['hip_motor']) / 2, -od / 4),
        'knee': (0, sum(S.y['knee_motor']) / 2, od / 2),
        'crank': (pin[0], sum(S.y['crank']) / 2, pin[1]),
        'rod': mid_rod,
        'thigh': (tx, sum(S.y['thigh']) / 2, tz),
        'shin': (kx + sx, sum(S.y['shin']) / 2, kz + sz),
        'wheel': (kx + wx, S.y['wheel'][1], kz + wz),
        'yoke': (0, S.y['bracket'][1] + 30, (S.hip['plate']['tab_top'] or 100) + 12),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?', default=str(R / 'designs/default.json'))
    ap.add_argument('--actuator')
    ap.add_argument('--video', action='store_true')
    a = ap.parse_args()
    L, S, shapes, act = setup(Path(a.design).resolve(), a.actuator)
    model = act.replace('robstride-', '').upper()
    r = Renderer(OUT, size=(1600, 1150), subtitle=f'Gyropup left leg module, {model} motors (hip and knee on one axis)')
    hip, knee = stand(L, 0.6)
    P = posed(L, shapes, hip, knee)
    pts = label_points(L, S, hip, knee)
    labels = [
        ('1', f'HIP motor ({model}): swings the whole leg', pts['hip'], (40, 400)),
        ('2', f'KNEE motor ({model}): same axis, outboard', pts['knee'], (1010, 150)),
        ('3', 'yoke + 3 posts tie both motors to the body', pts['yoke'], (40, 150)),
        ('4', 'knee crank (on the knee motor)', pts['crank'], (1060, 420)),
        ('5', 'push-rod: crank -> shin lever', pts['rod'], (1060, 560)),
        ('6', 'thigh (bolted to the hip motor)', pts['thigh'], (40, 560)),
        ('7', 'shin: pivots on the knee pin', pts['shin'], (40, 760)),
        ('8', 'wheel (its own hub motor)', pts['wheel'], (1060, 860)),
    ]
    r.render('leg-module.png', shapes=items(P), view=VIEW, labels=labels, zoom=0.92,
             caption='Two motors per leg, side by side on the hip axis',
             note='Both motors sit at the hip, so the leg itself stays light. Hip motor: leg forward/back. Knee motor: crank -> push-rod -> shin.')
    # what each motor does on its own: ghost of the start pose under the moved pose
    for name, dq, cap, note in (
            ('leg-hip.png', (0.45, 0.0), 'The HIP motor turns: thigh, shin and wheel swing together',
             'The knee motor and its crank stay put, so the push-rod keeps the knee angle as the leg swings (a parallelogram).'),
            ('leg-knee.png', (0.0, 0.6), 'The KNEE motor turns: crank -> push-rod -> the shin folds',
             'The hip motor holds the thigh still; only the crank, the rod, the shin and the wheel move.')):
        h1, k1 = hip + dq[0], knee + dq[1] - (dq[0] if name == 'leg-hip.png' else 0)
        # with the hip alone, the crank stays: knee joint angle changes by -dhip (the parallelogram holds the crank still)
        P1 = posed(L, shapes, h1, k1)
        ghost = {f'{n}_ghost': s for n, s in P.items() if n in leg.ROTATES or n == 'pushrod' or n == 'wheel'}
        its = items(P1) + [(s.val() if hasattr(s, 'val') else s, (0.6, 0.6, 0.6, 0.15)) for s in ghost.values()]
        r.render(name, shapes=its, view=VIEW, caption=cap, note=note, zoom=0.95)
    if a.video:
        video(L, S, shapes, r, hip, knee, model)


def video(L, S, shapes, r, hip, knee, model):
    import shutil
    frames = OUT / 'frames'
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    rr = Renderer(frames, size=(1280, 920), subtitle=f'Gyropup leg module, {model} x 2')
    seq = []
    n = 24
    for k in range(n):                                    # hip motor alone (the crank stays: knee = -dhip)
        t = math.sin(math.pi * 2 * k / n) * 0.45
        seq.append((hip + t, knee - t, 'HIP motor turns (knee motor holds): the whole leg swings, the knee angle is kept'))
    for k in range(n):                                    # knee motor alone
        t = math.sin(math.pi * 2 * k / n) * 0.55
        seq.append((hip, knee + t, 'KNEE motor turns (hip motor holds): crank -> push-rod -> shin folds'))
    for k in range(n):                                    # both: crouch to stand, wheel under the hip
        fr = 0.5 - 0.5 * math.cos(math.pi * 2 * k / n)
        h, q = stand(L, fr)
        seq.append((h, q, 'BOTH together: crouch to stand with the wheel under the hip'))
    for i, (h, q, cap) in enumerate(seq):
        rr.render(f'f{i:03d}.png', shapes=items(posed(L, shapes, h, q)), view=VIEW, caption=cap, zoom=0.95)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '8', '-i', str(frames / 'f%03d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '26', str(OUT / 'leg-motors.mp4')], check=True)
    shutil.rmtree(frames, ignore_errors=True)
    print(OUT / 'leg-motors.mp4')


if __name__ == '__main__':
    main()
