"""The ball feed in physics: 30 Rival balls in the hopper, the dial stepping them to the exit, at every pose.

    .venv/bin/python sim/turret_feed.py [--quick] [--video]

MuJoCo, in the cartridge frame of cad/turret.py (x along the barrel, z up through the dial axis; metres), with the
CAD's own numbers (cad/turret.py Geo): the dial-housing floor with its exit opening under the front pocket, the
housing and hopper wall, the lid, the dial (hub, stirring cone, 8 spokes) on a hinge driven like the feed servo (a
stiff position loop; sim/turret_feed_dyn.py has the STS3215's own profile and torque line), the exit baffle in the hopper's bottom, and 30 balls (Ø22.7, 1.83 g). Below the opening the
chute's bend (its outer wall as plates on the CAD's arc) and the straight run to the flywheels; a ball is counted (and
taken away) when it reaches the tyres, where the spinning wheels take it.

What it shows (exports/turret/feed/feed.json):
  1. feeding: the dial steps 45 deg per shot (a cosine move, then a dwell). At every pose and rate, each step must
     deliver exactly one ball while the hopper has balls (no double feed, no miss) until it runs dry;
  2. parked: the dial holds with a pocket over the exit (under the baffle) while the cartridge is tilted to every
     corner of its gravity range and shaken (5 m/s^2, 8-25 Hz, the robot driving over rough ground): no ball may
     leave. Then the same with the motor unpowered (the dial held only by the gearbox's friction, est);
  3. the time from the start of a step to the ball leaving the floor: the shot latency the firmware waits for.
Poses: the cartridge's own tilt 0 and -25 deg, plus the body's lean taken into the cartridge frame (pitch -10/+10,
roll -15/+15: the turret panned sideways on a leaning robot). Friction ball-ball and ball-plastic 0.4, 0.7 and 1.0:
foam is grippy, and higher friction is the harder case for bridging. Rigid spheres cannot show the tackiness that
makes real foam bridge (the Hasbro patent's concern), so the bench test plan repeats this with real balls.
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
OUT = R / 'exports' / 'turret' / 'feed'

BALL_M = 0.00183
FILL_TOP = 190.0                  # mm: the fill tube above the hopper while the balls settle
TIMESTEP = 0.0005


def geo():
    import turret as tu
    G = tu.Geo()
    return G, tu


def xml(G, tu, mu=0.7, n_balls=30, wall_n=40, seed=0, baffle='flat', tent=None):
    tent = tent or {'r_in': 14.0, 'slope_deg': 35.0}
    m = lambda v: v / 1000.0
    r = G.ball / 2
    fz, ft = G.floor_z, G.floor_t
    rw = G.dial_wall_r
    top = G.hopper_top
    g = []
    # floor pieces round the exit opening (under the front pocket: x from the hub's edge to the wall, |y| < bore/2)
    ox0, oy = G.dial_hub_r + 2.0, G.br
    for (x0, x1, y0, y1) in ((-rw - 3, ox0, -rw - 3, rw + 3), (ox0, rw + 3, oy, rw + 3), (ox0, rw + 3, -rw - 3, -oy)):
        g.append(f'<geom type="box" size="{m(x1 - x0) / 2} {m(y1 - y0) / 2} {m(ft) / 2}" pos="{m(x0 + x1) / 2} {m(y0 + y1) / 2} {m(fz - ft / 2)}" rgba=".55 .57 .6 1"/>')
    # the chute as cad/turret.py draws it: the ball's centre follows a quarter circle (centre (chute_cx, chute_r), radius
    # chute_r) from the pocket down to the path, then runs straight to the flywheels. Its outer wall (bore/2 from the
    # path) exists below the floor only (above it the dial's hub is that wall); plates stand in for it, with side walls
    cx, cz, rp = G.chute_cx, G.chute_r, G.chute_r
    ro = rp + G.br
    n = 10
    th0 = math.pi + math.asin(min(1.0, (cz - (fz - ft)) / ro))         # where the outer wall comes out under the floor
    th1 = 1.5 * math.pi
    for k in range(n):
        ta, tb = th0 + (th1 - th0) * k / n, th0 + (th1 - th0) * (k + 1) / n
        tc = 0.5 * (ta + tb)
        half = (ro + 1.5) * (tb - ta) / 2 + 0.4
        px, pz = cx + (ro + 1.5) * math.cos(tc), cz + (ro + 1.5) * math.sin(tc)
        g.append(f'<geom type="box" size="{m(half)} {m(oy + 1.5)} 0.0015" pos="{m(px)} 0 {m(pz)}" euler="0 {-(tc + math.pi / 2)} 0" rgba=".5 .5 .55 .8"/>')
    x_nip = G.wheel_x - math.sqrt((G.wheel_d / 2) ** 2 - ((G.wheel_c - G.ball) / 2) ** 2)
    g.append(f'<geom type="box" size="{m(x_nip + 6 - cx) / 2} {m(oy + 1.5)} 0.0015" pos="{m((cx + x_nip + 6) / 2)} 0 {m(-G.br - 1.5)}" rgba=".5 .5 .55 .8"/>')
    for sy in (1, -1):
        g.append(f'<geom type="box" size="{m(x_nip + 6 - ox0) / 2} 0.0015 {m(fz - ft + 20) / 2}" pos="{m((ox0 + x_nip + 6) / 2)} {sy * m(oy + 1.5)} {m(fz - ft - 20) / 2}" rgba=".5 .5 .55 .25"/>')
    # housing + hopper wall: a polygon of boxes, inner face at the channel's outer radius
    w = 2 * rw * math.tan(math.pi / wall_n) + 0.6
    zc, hz = (fz + FILL_TOP) / 2, (FILL_TOP - fz + 6) / 2         # filled through a taller tube; the lid comes down after
    for k in range(wall_n):
        a = 2 * math.pi * k / wall_n
        rc = rw + 1.5
        z_lo = fz - ft
        if math.cos(a) > 0 and abs(rc * math.sin(a)) < oy + 6:          # the chute torus notches the wall foot here (24.2 wide)
            z_lo = G.chute_r + 1.0
        zc_k, hz_k = (z_lo + FILL_TOP) / 2, (FILL_TOP - z_lo + 6) / 2
        g.append(f'<geom type="box" size="0.0015 {m(w) / 2} {m(hz_k)}" pos="{m(rc * math.cos(a))} {m(rc * math.sin(a))} {m(zc_k)}" euler="0 0 {a}" rgba=".7 .85 .95 .15"/>')
    lid = f'<body name="lid" mocap="true" pos="0 0 {m(FILL_TOP + 2)}"><geom type="cylinder" size="{m(rw - 0.3)} 0.0015" pos="0 0 0.0015" rgba=".7 .85 .95 .3"/></body>'
    # the exit baffle over the front pocket, its underside at the housing top: a flat +-24 deg sector, or a tent
    # (ridged along the centre line, its faces falling to both edges) that sheds balls sideways into open pockets
    B = getattr(tu, 'BAFFLE')
    z0 = G.housing_top
    assets = ''
    if baffle == 'flat':
        for ring in ((B['r0'], (B['r0'] + rw) / 2), ((B['r0'] + rw) / 2, rw)):
            for k in range(6):
                a = math.radians(-B['half_deg'] + (2 * k + 1) * B['half_deg'] / 6)
                half = ring[0] * math.tan(math.radians(B['half_deg'] / 6)) + 0.2
                rc = (ring[0] + ring[1]) / 2
                g.append(f'<geom type="box" size="{m(ring[1] - ring[0]) / 2} {m(half)} {m(B["t"]) / 2}" pos="{m(rc * math.cos(a))} {m(rc * math.sin(a))} {m(z0 + B["t"] / 2)}" euler="0 0 {a}" rgba=".3 .6 .9 .6"/>')
    else:
        ri, ro, ph = tent['r_in'], rw + 0.5, math.radians(B['half_deg'])
        ta = math.tan(math.radians(tent['slope_deg']))
        verts = []
        for rr in (ri, ro):
            w = rr * math.sin(ph)
            verts += [(rr * math.cos(ph), w, z0), (rr * math.cos(ph), -w, z0), (rr, 0, z0), (rr, 0, z0 + B['t'] + w * ta)]
        assets = '<asset><mesh name="tent" vertex="' + ' '.join(f'{m(x)} {m(y)} {m(z)}' for x, y, z in verts) + '"/></asset>'
        g.append('<geom type="mesh" mesh="tent" rgba=".3 .6 .9 .6"/>')
    # the dial
    d = []
    d.append(f'<geom type="cylinder" size="{m(G.dial_hub_r)} {m(G.dial_h) / 2}" pos="0 0 {m(G.dial_z0 + G.dial_h / 2)}" rgba=".95 .8 .2 1"/>')
    zc = G.dial_z0 + G.dial_h
    for k, rr in enumerate((G.dial_hub_r * 0.8, G.dial_hub_r * 0.55, 8.0)):
        d.append(f'<geom type="cylinder" size="{m(rr)} 0.001" pos="0 0 {m(zc + 1 + 2 * k)}" rgba=".95 .8 .2 1"/>')
    for k in range(G.n_pockets):
        a = math.radians((k + 0.5) * 360 / G.n_pockets)
        r0, r1 = G.dial_hub_r - 1, G.dial_wall_r - 0.75
        rc = (r0 + r1) / 2
        h = G.dial_h - 2
        d.append(f'<geom type="box" size="{m(r1 - r0) / 2} {m(G.spoke_w) / 2} {m(h) / 2}" pos="{m(rc * math.cos(a))} {m(rc * math.sin(a))} {m(G.dial_z0 + h / 2)}" euler="0 0 {a}" rgba=".95 .8 .2 1"/>')
    # balls: dropped into the hopper in a loose column
    rng = np.random.default_rng(seed)
    balls = []
    for i in range(n_balls):
        lay, j = divmod(i, 7)
        a = 2 * math.pi * j / 7 + lay * 0.45
        rr = 0 if j == 0 else (rw - r - 1.5) * 0.75
        x, y = rr * math.cos(a), rr * math.sin(a)
        z = G.dial_z0 + G.dial_h + r + 4 + lay * (G.ball + 1.5)
        x, y = x + rng.uniform(-1, 1), y + rng.uniform(-1, 1)
        balls.append(f'<body name="b{i}" pos="{m(x)} {m(y)} {m(z)}"><freejoint/><geom type="sphere" size="{m(r)}" mass="{BALL_M}" rgba="1 .45 .05 1"/></body>')
    return f'''<mujoco model="turret feed">
  <compiler angle="radian"/>
  <option timestep="{TIMESTEP}" gravity="0 0 -9.81" integrator="implicitfast" cone="elliptic" impratio="2"/>
  <default><geom friction="{mu} 0.005 0.0002" solref="0.004 1" solimp="0.9 0.95 0.001" condim="4"/></default>
  <visual><global offwidth="960" offheight="720"/></visual>
  {assets}
  <worldbody>
    <light pos="0 -0.3 0.4" dir="0 0.6 -0.8"/>
    {''.join(g)}
    <body name="dial" pos="0 0 0">
      <joint name="dial" type="hinge" axis="0 0 1" damping="0.002" frictionloss="0" armature="0.001"/>
      {''.join(d)}
    </body>
    {''.join(balls)}
    {lid}
  </worldbody>
  <actuator><position name="dial" joint="dial" kp="20" kv="0.3" forcerange="-1 1"/></actuator>
</mujoco>'''


class Feed:
    def __init__(self, G, tu, mu=0.7, n_balls=30, seed=0, baffle='flat', tent=None):
        import mujoco
        self.mj = mujoco
        self.G = G
        self.model = mujoco.MjModel.from_xml_string(xml(G, tu, mu, n_balls, seed=seed, baffle=baffle, tent=tent))
        self.data = mujoco.MjData(self.model)
        self.balls = [self.model.body(f'b{i}').id for i in range(n_balls)]
        self.qadr = [self.model.jnt_qposadr[self.model.body_jntadr[b]] for b in self.balls]
        self.vadr = [self.model.jnt_dofadr[self.model.body_jntadr[b]] for b in self.balls]
        self.gone = set()
        self.dial_j = self.model.joint('dial').id
        self.t_out = []
        self.frames = []
        self.escaped = []
        self.x_nip = G.wheel_x - math.sqrt((G.wheel_d / 2) ** 2 - ((G.wheel_c - G.ball) / 2) ** 2)    # first touch on the tyres
        self.lid = self.model.body('lid').mocapid[0]

    def set_gravity(self, tilt_deg=0.0, pitch_deg=0.0, roll_deg=0.0):
        """Gravity in the cartridge frame for the cartridge's tilt (nose down negative) plus the body's pitch (nose
        down positive) and roll (left side down positive), pan taken as 0 (roll covers the sideways case)."""
        a = math.radians(-tilt_deg + pitch_deg)               # total nose-down angle of the cartridge's x axis
        b = math.radians(roll_deg)
        gv = np.array([math.sin(a), 0.0, -math.cos(a)]) * 9.81
        Rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
        self.model.opt.gravity[:] = Rx @ gv

    def run(self, seconds, dial_target=None, shake=None, frame_every=None):
        """Advance; dial_target(t) -> rad or None (motor off: the actuator is disabled and the gearbox friction holds
        it). shake = (amplitude m/s^2, freq Hz) added to gravity. Returns the balls that left in this window."""
        mj, d = self.mj, self.data
        n = int(round(seconds / TIMESTEP))
        left = []
        g0 = self.model.opt.gravity.copy()
        for k in range(n):
            t = d.time
            if dial_target is None:
                d.ctrl[0] = d.qpos[self.model.jnt_qposadr[self.dial_j]]
                self.model.actuator_gainprm[0, 0] = 0.0
                self.model.actuator_biasprm[0, 1] = 0.0
                self.model.dof_frictionloss[self.model.jnt_dofadr[self.dial_j]] = 0.02     # the gearbox's drag, est
            else:
                self.model.actuator_gainprm[0, 0] = 20.0
                self.model.actuator_biasprm[0, 1] = -20.0
                self.model.dof_frictionloss[self.model.jnt_dofadr[self.dial_j]] = 0.0
                d.ctrl[0] = dial_target(t)
            if shake:
                amp, f = shake
                self.model.opt.gravity[:] = g0 + amp * np.array([math.sin(2 * math.pi * f * t), math.sin(2 * math.pi * f * 1.37 * t + 1), 0.5 * math.sin(2 * math.pi * f * 0.71 * t + 2)])
            mj.mj_step(self.model, d)
            for i, (qa, va) in enumerate(zip(self.qadr, self.vadr)):
                if i in self.gone:
                    continue
                x, y, z = d.qpos[qa:qa + 3]
                fed = x > self.x_nip / 1000.0 and z < (self.G.floor_z - self.G.floor_t) / 1000.0         # down the chute, at the wheels
                outside = math.hypot(x, y) > (self.G.dial_wall_r + 5) / 1000.0 and z > (self.G.floor_z - self.G.floor_t) / 1000.0
                lost = z < -0.05 or (outside and not fed)        # over the top or through the wall: not by the chute
                if fed or lost:
                    self.gone.add(i)
                    if lost and not fed:
                        self.escaped.append((i, round(t, 4)))           # left round the outside: a rig error
                    else:
                        left.append((i, round(t, 4)))
                    d.qpos[qa:qa + 3] = (0.3 + 0.03 * i, 0.3, 0.05)      # out of the way
                    d.qvel[va:va + 6] = 0
            if frame_every and k % frame_every == 0:
                self.frames.append(d.qpos.copy())
        self.model.opt.gravity[:] = g0
        return left

    def settle(self, seconds=1.5):
        """Let the balls fall in through the fill tube, then bring the lid down to the hopper's top over 0.5 s.
        Returns the balls that left and how many ball centres stood higher than the lid allows before it came down."""
        park = self.data.qpos[self.model.jnt_qposadr[self.dial_j]]
        left = self.run(seconds, lambda t: park)
        zmax = (self.G.hopper_top - self.G.ball / 2) / 1000.0
        over = sum(1 for i, qa in enumerate(self.qadr) if i not in self.gone and self.data.qpos[qa + 2] > zmax + 0.0005)
        z0, z1 = (FILL_TOP + 2) / 1000.0, self.G.hopper_top / 1000.0
        n = int(0.5 / TIMESTEP)
        for k in range(n):
            self.data.mocap_pos[self.lid][2] = z0 + (z1 - z0) * (k + 1) / n
            left += self.run(TIMESTEP, lambda t: park)
        left += self.run(0.3, lambda t: park)
        self.overfull = over
        return left


def step_profile(start_t, a0, move_s, dwell_s):
    """45 deg cosine move from a0 starting at start_t."""
    da = math.radians(45.0)

    def f(t):
        u = (t - start_t) / move_s
        if u <= 0:
            return a0
        if u >= 1:
            return a0 + da
        return a0 + da * 0.5 * (1 - math.cos(math.pi * u))
    return f


RELEVEL = {'below_deg': -12.0, 'hold_s': 0.4}       # firmware: after an empty step this deep, lift to 0 deg and retry


def feed_test(G, tu, pose, mu, rate_hz, move_s=0.04, seed=0, n_balls=30, max_steps=40, baffle='flat', tent=None, relevel=True):
    F = Feed(G, tu, mu, n_balls, seed, baffle, tent)
    F.set_gravity(*pose)
    early = F.settle(1.5)
    per_step, latency = [], []
    a = F.data.qpos[F.model.jnt_qposadr[F.dial_j]]
    period = 1.0 / rate_hz
    empty_run = 0
    relevels = 0
    for k in range(max_steps):
        t0 = F.data.time
        out = F.run(period, step_profile(t0, a, move_s, period - move_s))
        a += math.radians(45.0)
        per_step.append(len(out))
        latency += [round((t - t0) * 1000, 1) for _, t in out]
        if relevel and not out and pose[0] - pose[1] <= RELEVEL['below_deg'] and len(F.gone) < n_balls:
            F.set_gravity(0.0, pose[1], pose[2])             # the barrel lifted to 0 deg for a moment
            park = a
            F.run(RELEVEL['hold_s'], lambda t: park)
            F.set_gravity(*pose)
            relevels += 1
        if len(out) == 0:
            empty_run += 1
            if empty_run >= 8 and len(F.gone) >= n_balls - 1:
                break
        else:
            empty_run = 0
        if len(F.gone) == n_balls:
            break
    fed = len(F.gone)
    doubles = sum(1 for n in per_step if n > 1)
    first_empty = next((i for i, n in enumerate(per_step) if n == 0), None)
    misses = sum(1 for i, n in enumerate(per_step) if n == 0 and i < (first_empty or len(per_step)) and len(F.gone) < n_balls)
    # a miss = a step that brought no ball while balls were still left in the hopper and later steps fed again
    gaps = [i for i, n in enumerate(per_step) if n == 0 and any(m > 0 for m in per_step[i + 1:])]
    return {'pose': {'tilt': pose[0], 'pitch': pose[1], 'roll': pose[2]}, 'mu': mu, 'rate_hz': rate_hz, 'fed': fed - len(F.escaped),
            'balls': n_balls, 'left_while_settling': len(early), 'over_the_lid_before_closing': F.overfull, 'escaped': len(F.escaped),
            'steps': len(per_step), 'per_step': per_step,
            'double_feeds': doubles, 'empty_steps_before_dry': len(gaps), 'relevels': relevels, 'latency_ms': latency,
            'latency_ms_max': max(latency) if latency else None}


def park_test(G, tu, pose, mu, powered=True, seed=0, n_balls=30):
    F = Feed(G, tu, mu, n_balls, seed)
    F.set_gravity(*pose)
    F.settle(1.5)
    park = F.data.qpos[F.model.jnt_qposadr[F.dial_j]]
    left = []
    for f in (8.0, 15.0, 25.0):
        left += F.run(1.0, (lambda t: park) if powered else None, shake=(5.0, f))
    turned = math.degrees(F.data.qpos[F.model.jnt_qposadr[F.dial_j]] - park)
    return {'pose': {'tilt': pose[0], 'pitch': pose[1], 'roll': pose[2]}, 'mu': mu, 'powered': powered, 'balls_left': len(left),
            'escaped': len(F.escaped), 'dial_turned_deg': round(turned, 2)}


POSES = [(0, 0, 0), (-25, 0, 0), (0, -10, 0), (-25, 10, 0), (0, 0, 15), (-25, 0, -15), (-12.5, 10, 15)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--video', action='store_true')
    a = ap.parse_args()
    G, tu = geo()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = {'geometry': {'ball_mm': G.ball, 'bore_mm': G.bore, 'pockets': G.n_pockets, 'pitch_r_mm': G.rp, 'baffle': tu.BAFFLE,
                        'opening': 'x from the hub + 2 mm to the wall, |y| < bore/2 (the CAD chute torus cuts a U-shaped slot there)'},
           'feeding': [], 'parked': []}
    poses = POSES[:2] if a.quick else POSES
    mus = [0.7] if a.quick else [0.4, 0.7, 1.0]
    for pose in poses:
        for mu in mus:
            for rate in ((3.0,) if a.quick else (3.0, 8.0)):
                r = feed_test(G, tu, pose, mu, rate, seed=int(abs(pose[0]) + 10 * mu))
                res['feeding'].append(r)
                print(f"feed  tilt {pose[0]:6} pitch {pose[1]:4} roll {pose[2]:4} mu {mu} {rate:3.0f}/s: fed {r['fed']}/{r['balls']} in {r['steps']} steps, "
                      f"doubles {r['double_feeds']}, empty steps {r['empty_steps_before_dry']}, latency max {r['latency_ms_max']} ms, "
                      f"relevels {r['relevels']}, over the lid {r['over_the_lid_before_closing']}, escaped {r['escaped']}, early {r['left_while_settling']}  ({time.time() - t0:.0f} s)")
        for powered in (True, False):
            r = park_test(G, tu, pose, 0.7, powered)
            res['parked'].append(r)
            print(f"park  tilt {pose[0]:6} pitch {pose[1]:4} roll {pose[2]:4} {'powered' if powered else 'motor off'}: {r['balls_left']} balls left, "
                  f"{r['escaped']} escaped, dial turned {r['dial_turned_deg']} deg")
    feeds = res['feeding']
    res['verdict'] = {
        'double_feeds': sum(r['double_feeds'] for r in feeds), 'empty_steps_before_dry': sum(r['empty_steps_before_dry'] for r in feeds),
        'balls_fed': [r['fed'] for r in feeds], 'parked_leaks': sum(r['balls_left'] for r in res['parked']),
        'latency_ms_max': max((r['latency_ms_max'] or 0) for r in feeds),
        'cases': len(feeds) + len(res['parked'])}
    (OUT / 'feed.json').write_text(json.dumps(res, indent=1) + '\n')
    print('verdict', res['verdict'])
    if a.video:
        video(G, tu)


def video(G, tu):
    import mujoco
    F = Feed(G, tu, 0.7, 30, 1)
    F.set_gravity(-25, 0, 0)
    F.settle(1.0)
    a = F.data.qpos[F.model.jnt_qposadr[F.dial_j]]
    renderer = mujoco.Renderer(F.model, 720, 960)
    cam = mujoco.MjvCamera()
    cam.lookat[:] = (0.02, 0, 0.03)
    cam.distance, cam.azimuth, cam.elevation = 0.28, -60, -30
    frames = []
    for k in range(10):
        t0 = F.data.time
        prof = step_profile(t0, a, 0.04, 0.29)
        for j in range(int(0.333 / TIMESTEP)):
            F.data.ctrl[0] = prof(F.data.time)
            mujoco.mj_step(F.model, F.data)
            if j % 33 == 0:
                renderer.update_scene(F.data, cam)
                frames.append(renderer.render())
        a += math.radians(45)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for i in (0, len(frames) // 2, len(frames) - 1):
        plt.imsave(OUT / f'feed-frame-{i:03d}.png', frames[i])
    try:
        import subprocess
        tmp = OUT / 'frames'
        tmp.mkdir(exist_ok=True)
        for i, fr in enumerate(frames):
            plt.imsave(tmp / f'{i:04d}.png', fr)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', str(tmp / '%04d.png'), '-pix_fmt', 'yuv420p', str(OUT / 'feed.mp4')], check=True)
        for f in tmp.glob('*.png'):
            f.unlink()
        tmp.rmdir()
    except Exception as exc:
        print('video:', exc)


if __name__ == '__main__':
    main()
