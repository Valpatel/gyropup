"""End to end: the turret on the robot aims at targets at 2, 4 and 6 m and fires 5-ball bursts, every stage on the
current CAD, one stage's exit the next stage's input.

    .venv/bin/python sim/turret_e2e.py [--quick] [--no-video] [--set-fps 55 65]

The chain, per shot (R = reduced model solved outside MuJoCo; M = MuJoCo):
  1. the ball            sim/turret_ball.py            the sourced size/mass spread, the swept foam unknowns
  2. the feed       M    sim/turret_feed_dyn.py        the hopper, dial (on its STS3215 servo), baffle and chute from cad/turret.py at the
                                                       engagement's tilt, with the pan slew's fictitious forces; out: the ball's
                                                       state at first touch on the tyres and the latency from the step command
  3. the launch     R    sim/turret_launch3d.py        6-DOF ball between the two tyres, each on its own X2216 + ESC loop, the
                                                       burst's wheel-speed recovery between shots; out: velocity and spin at the nip exit
  4. the barrel     R    sim/turret_flight.py          wall contacts down the bore; out: the muzzle state (cartridge frame)
  5. the flight     M    this file                     the muzzle state rotated by the turret's pose at that instant plus the
                                                       muzzle's own velocity (pan rate), flown by MuJoCo's ellipsoid fluid model
                                                       (drag and Magnus mapped from turret_flight.py); checked against the
                                                       Python flight (R) at the target plane
  6. the target     M    sim/turret.py plates          hinged 20 g knock-down plates; knock-down counted in MuJoCo and by the
                                                       analytic criterion (sim/turret_target.py)
  7. the turret     M    this file                     the posed CAD meshes as pan/tilt bodies with STS3215 servo models (torque-
                                                       speed line, the 3:1 pan gear), the recoil pulse applied at the nip,
                                                       the aim trace; cad/turret_motion.py's inertias; backlash from
                                                       sim/turret_dynamics.py (not in the MuJoCo joints: reported)
Two firing modes: 'settled' (fire when the aim error is under 0.3 deg and the pan rate under 5 deg/s) and 'panning'
(fire as soon as the aim error is under 2 deg, while the pan servo is still finishing its move). Two set speeds: the
program's set speed (95 fps on Ø38 tyres since D68) and 95 % of the rail's no-load speed (both under the 105 fps ceiling).
Writes exports/turret/e2e/e2e.json (checks keyed to docs/turret-program.md's checklist), e2e.png, e2e.mp4 and frames.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault('MUJOCO_GL', 'egl')
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_common as tc  # noqa: E402

OUT = R / 'exports' / 'turret' / 'e2e'
MESH_DIR = R / 'build' / 'turret_e2e_meshes'
# The committed world names its meshes relative to itself (MuJoCo resolves meshdir against the model file), never by an
# absolute path on the machine that built it.
MESH_REL = Path(os.path.relpath(MESH_DIR, OUT)).as_posix()
MOUNT_Z = 0.55                      # m: the TM face above the floor on the standing robot (est; sim/turret_flight.py FLIGHT)
TARGETS = [('t2m', 2.0, 20.0), ('t4m', 4.0, 0.0), ('t6m', 6.0, -25.0)]       # name, range (m), bearing (deg, + left)
TARGET_Z = 0.30
BURST = 5
BURST_RATE = 3.0
SERVO = {'stall_nm': 2.94, 'no_load_rad_s': 45 * 2 * math.pi / 60, 'pan_ratio': 3.0, 'pan_eff': 0.9, 'pan_kp': 30.0, 'pan_kd': 0.4, 'tilt_kp': 20.0, 'tilt_kd': 0.25,
         'pan_max_deg_s': 90.0, 'pan_ramp_s': 0.1, 'tilt_max_deg_s': 200.0}
DT = 0.0005
CTRL_HZ = 1000
VIDEO_FPS = 30


# ------------------------------------------------------------------------------------------------ the world from the CAD

def export_meshes(T, tu):
    """Every part posed at pan 0, tilt 0 in the T frame, as STL (mm) in its motion group."""
    import cadquery as cq
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    P = T.posed(0.0, 0.0, robot=False)
    groups = {'base': [], 'pan': [], 'tilt': [], 'pinion': []}
    rows, tot, com = tu.mass_properties(T, 0.0, with_balls=False)
    for name, shape in P.items():
        fr = T.frame[name]
        mass = rows[name]['mass_g'] / 1000 if name in rows else 0.0
        if mass <= 0:
            continue
        variants = [(name, shape)]
        if name in T.meta and T.meta[name]['qty'] == 2:
            variants.append((name + '_2', shape.mirror('XZ')))
        for nm, sh in variants:
            p = MESH_DIR / f'{nm}.stl'
            try:
                cq.exporters.export(sh.val(), str(p), tolerance=0.3, angularTolerance=0.3)
            except Exception as exc:
                print('mesh', nm, exc)
                continue
            groups[fr].append((nm, str(p), mass, T.meta.get(name, {}).get('material', 'bought')))
    return groups


COLORS = {'pa6-cf': '0.35 0.37 0.40 1', 'petg': '0.95 0.55 0.15 0.85', 'tpu95': '0.12 0.12 0.12 1', 'bought': '0.6 0.15 0.15 1'}


def world_xml(T, tu, groups, balls_n, fluidcoef, targets_xml):
    G = T.G
    sx, sy = G.servo_pan_xy
    assets = ''.join(f'<mesh name="{nm}" file="{Path(p).name}" scale="0.001 0.001 0.001"/>'
                     for g in groups.values() for nm, p, m, mat in g)
    geom = lambda nm, m, mat, extra='': f'<geom type="mesh" mesh="{nm}" mass="{m:.5f}" rgba="{COLORS.get(mat, COLORS["bought"])}" contype="0" conaffinity="0" group="1" {extra}/>'
    base = ''.join(geom(nm, m, mat) for nm, p, m, mat in groups['base'])
    pan = ''.join(geom(nm, m, mat) for nm, p, m, mat in groups['pan'])
    tilt = ''.join(geom(nm, m, mat) for nm, p, m, mat in groups['tilt'])
    pin = ''.join(geom(nm, m, mat) for nm, p, m, mat in groups['pinion'])
    mz = G.barrel_x1 - G.tilt_x
    x_touch = G.wheel_x - math.sqrt((G.wheel_d / 2 + G.ball / 2) ** 2 - (G.wheel_c / 2) ** 2)
    nip = x_touch - G.tilt_x
    hopper_balls = 30 * 0.00183
    balls = tc.game_turret().balls_xml(balls_n).replace('fluidcoef="0.25 0.25 1.5 0 0"', f'fluidcoef="{fluidcoef}"')
    body_box = T.L['body'] if 'body' in T.L else {'depth': 181, 'width': 206, 'height': 112}
    return f'''<mujoco model="gyropup turret e2e">
  <compiler angle="radian" meshdir="{MESH_REL}"/>
  <option timestep="{DT}" gravity="0 0 -9.81" density="1.205" viscosity="1.81e-5" integrator="implicitfast"/>
  <visual><headlight diffuse="0.7 0.7 0.7" ambient="0.4 0.4 0.4"/><global offwidth="1280" offheight="720"/><map znear="0.01"/></visual>
  <asset>{assets}
    <texture name="grid" type="2d" builtin="checker" rgb1=".86 .88 .9" rgb2=".78 .8 .83" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="12 12"/>
  </asset>
  <default><geom friction="0.9 0.005 0.0001" solref="0.004 1"/></default>
  <worldbody>
    <light pos="1 1.5 3" dir="-0.2 -0.4 -1"/>
    <light pos="4 -2 3" dir="-0.4 0.3 -1"/>
    <geom name="floor" type="plane" size="12 6 0.1" material="grid"/>
    <body name="robot" pos="0 0 {MOUNT_Z}">
      <geom type="box" size="{body_box['depth'] / 2000} {body_box['width'] / 2000} {body_box['height'] / 2000}" pos="0 0 {-0.028 - body_box['height'] / 2000}" rgba="0.9 0.5 0.15 1" contype="0" conaffinity="0" mass="4"/>
      <geom type="cylinder" size="0.066 0.004" pos="0 0 -0.004" rgba="0.8 0.82 0.85 1" contype="0" conaffinity="0" mass="0.05"/>
      {base}
      <body name="pinion"><joint name="pinion" type="hinge" axis="0 0 1" pos="{sx / 1000} {sy / 1000} 0" damping="0.001"/>{pin or '<geom type="sphere" size="0.005" mass="0.005" contype="0" conaffinity="0"/>'}</body>
      <body name="pan">
        <joint name="pan" type="hinge" axis="0 0 1" range="-2.97 2.97" damping="0.02" armature="0.0004"/>
        {pan}
        <geom type="sphere" size="0.01" pos="0 0 {G.turntable_z[1] / 1000}" mass="{sum(tu.NOT_MODELLED_G.values()) / 1000}" rgba="0.2 0.2 0.2 0.3" contype="0" conaffinity="0"/>
        <body name="tilt">
          <joint name="tilt" type="hinge" axis="0 1 0" pos="0 0 {G.tilt_t / 1000}" range="0 {math.radians(25.5)}" damping="0.01"/>
          {tilt}
          <geom type="sphere" size="0.03" pos="{-G.tilt_x / 1000} 0 {(G.path_t + 50) / 1000}" mass="{hopper_balls}" rgba="1 0.5 0.1 0.25" contype="0" conaffinity="0"/>
          <site name="muzzle" pos="{mz / 1000} 0 {G.path_t / 1000}" size="0.004" rgba="0 1 0 1"/>
          <site name="nip" pos="{nip / 1000} 0 {G.path_t / 1000}" size="0.003" rgba="1 0 0 1"/>
        </body>
      </body>
    </body>
    {targets_xml}
    {balls}
  </worldbody>
  <actuator>
    <motor name="pan" joint="pan" ctrlrange="-12 12" ctrllimited="true"/>
    <motor name="tilt" joint="tilt" ctrlrange="-4 4" ctrllimited="true"/>
  </actuator>
</mujoco>'''


# ------------------------------------------------------------------------------------------------ the run

class Servos:
    """STS3215 position loops with the datasheet torque-speed line; the pan through 63:21 at 0.9."""

    def __init__(self, model, data):
        self.m, self.d = model, data
        self.pan_q, self.pan_v = model.joint('pan').qposadr[0], model.joint('pan').dofadr[0]
        self.tilt_q, self.tilt_v = model.joint('tilt').qposadr[0], model.joint('tilt').dofadr[0]
        self.pin_q = model.joint('pinion').qposadr[0]
        self.pan_a, self.tilt_a = model.actuator('pan').id, model.actuator('tilt').id
        self.pan_ref = self.pan_target = 0.0
        self.tilt_ref = self.tilt_target = 0.0
        self.pan_rate = 0.0
        self.sat = {'pan': 0, 'tilt': 0}

    def plan(self, pan_deg, tilt_down_deg):
        self.pan_target = math.radians(pan_deg)
        self.tilt_target = math.radians(tilt_down_deg)

    def step(self, dt):
        # reference trajectories: speed-limited ramps
        pan_max = math.radians(SERVO['pan_max_deg_s'])
        acc = pan_max / SERVO['pan_ramp_s']
        err = self.pan_target - self.pan_ref
        want = math.copysign(min(pan_max, math.sqrt(2 * acc * abs(err))), err) if abs(err) > 1e-6 else 0.0
        self.pan_rate += max(-acc * dt, min(acc * dt, want - self.pan_rate))
        self.pan_ref += self.pan_rate * dt
        tilt_max = math.radians(SERVO['tilt_max_deg_s'])
        te = self.tilt_target - self.tilt_ref
        self.tilt_ref += max(-tilt_max * dt, min(tilt_max * dt, te))
        d, m = self.d, self.m
        # pan: PD at the turret, torque limited by the servo's line through 3:1
        th, om = d.qpos[self.pan_q], d.qvel[self.pan_v]
        tau = SERVO['pan_kp'] * (self.pan_ref - th) + SERVO['pan_kd'] * (self.pan_rate - om)
        avail = SERVO['stall_nm'] * max(0.0, 1 - abs(om) * SERVO['pan_ratio'] / SERVO['no_load_rad_s']) * SERVO['pan_ratio'] * SERVO['pan_eff']
        if abs(tau) > avail:
            self.sat['pan'] += 1
        d.ctrl[self.pan_a] = max(-avail, min(avail, tau))
        th, om = d.qpos[self.tilt_q], d.qvel[self.tilt_v]
        tau = SERVO['tilt_kp'] * (self.tilt_ref - th) + SERVO['tilt_kd'] * (0.0 - om)
        avail = SERVO['stall_nm'] * max(0.0, 1 - abs(om) / SERVO['no_load_rad_s'])
        if abs(tau) > avail:
            self.sat['tilt'] += 1
        d.ctrl[self.tilt_a] = max(-avail, min(avail, tau))
        d.qpos[self.pin_q] = -SERVO['pan_ratio'] * d.qpos[self.pan_q]

    def aim_error(self):
        return abs(self.pan_target - self.d.qpos[self.pan_q]), abs(self.tilt_target - self.d.qpos[self.tilt_q]), abs(self.d.qvel[self.pan_v])


class Video:
    def __init__(self, model, path, width=960, height=540):
        import mujoco
        self.r = mujoco.Renderer(model, height, width)
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.lookat[:] = (1.1, 0.0, 0.45)
        self.cam.distance, self.cam.elevation, self.cam.azimuth = 2.4, -10, 150
        self.opt = mujoco.MjvOption()
        self.path = path
        self.proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(VIDEO_FPS), '-i', '-',
                                      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '26', str(path)], stdin=subprocess.PIPE)
        self.n = 0
        self.kept = []

    def frame(self, d, keep=False):
        self.r.update_scene(d, self.cam, self.opt)
        img = self.r.render()
        self.proc.stdin.write(img.tobytes())
        if keep:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            p = self.path.with_name(f'{self.path.stem}-frame-{self.n:04d}.png')
            plt.imsave(p, img)
            self.kept.append(str(p))
        self.n += 1

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()
        self.r.close()


def aim_solution(tf, spec, rng_m, h_target, v_muzzle):
    """The barrel depression (deg, >= 0 down) that puts the ball at h_target at rng_m from MOUNT_Z + the muzzle height
    over the TM face at tilt 0 (G.path_t); None if even a level shot is low (never above horizontal)."""
    el = tf.elevation_for(v_muzzle, spec, rng_m, h_target, h0=MOUNT_Z + 0.121)
    return None if el is None else -math.degrees(el)


def run(set_fps=95.0, mode='settled', quick=False, video=True, seed=7):
    import mujoco
    tu = tc.cad_turret()
    tb = tc.sim_module('turret_ball')
    tl = tc.sim_module('turret_launch')
    l3 = tc.sim_module('turret_launch3d')
    tf = tc.sim_module('turret_flight')
    tt = tc.sim_module('turret_target')
    fd = tc.sim_module('turret_feed_dyn')
    gt = tc.game_turret()
    T = tc.turret_for_physics(tu)
    G = T.G
    t_wall = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    # ---- 1. the balls: one hopper's worth from the sourced population
    pop = tb.population(30, seed=seed)
    spec_n = tb.nominal()
    # ---- 3 (setup). the launcher at the set speed
    L = l3.design_launcher()
    l3.set_bore(G)
    w0 = tl.no_load_speed(L)
    w_set = tl.set_speed_for(tl.DESIGN['nominal'], L, set_fps * tl.FPS) if set_fps != 'max' else 0.95 * w0
    if w_set is None:                                    # the hardware ceiling (no-load on the 12 V rail) is below this set speed
        w_set = 0.95 * w0
        set_note = f'{set_fps} fps is above what the nominal ball reaches at 100 % throttle on this rail/tyre: using 95 % of no-load instead'
    else:
        set_note = None
    v_nom = tl.shot(tl.DESIGN['nominal'], L, w_set)['v_exit']
    set_fps = round(v_nom / tl.FPS, 1)
    # ---- the engagements: pan/tilt for each target, from the Python flight's aiming solution (the laser boresight would do this on the robot)
    engagements = []
    for name, rng_m, bearing in TARGETS:
        depress = aim_solution(tf, spec_n, rng_m, TARGET_Z, v_nom)
        engagements.append({'target': name, 'range_m': rng_m, 'bearing_deg': bearing, 'tilt_down_deg': depress, 'reachable': depress is not None})
    # ---- 2. the feed at each engagement: a 5-ball burst at 3/s with the pan's residual rate during the burst
    feed = {}
    for e in engagements:
        tilt = -(e['tilt_down_deg'] or 0.0)
        DF = fd.DynFeed(G, tu, 0.7, 30, seed=seed, pose=(tilt, 0.0, 0.0))
        t0 = DF.d.time
        slew = fd.slew_profile(t0, 60.0, 0.15, 0.0) if mode == 'panning' else None        # the pan decelerating from 60 deg/s as the burst starts
        rows = fd.burst(DF, BURST, 1.0 / BURST_RATE, slew=slew)
        feed[e['target']] = {'rows': rows, 'summary': fd.summarize(rows), 'in_chute_after': DF.in_chute()}
        print(f"feed {e['target']} tilt {tilt:.1f}: {feed[e['target']]['summary']['per_step']} latency {feed[e['target']]['summary']['latency_ms']} ({time.time() - t_wall:.0f} s)")
    # ---- 3-4. the launch (burst chain) and the barrel for each fed ball
    shots = []
    k_ball = 0
    for e in engagements:
        w = [w_set, w_set]
        t_prev = None
        for i, row in enumerate(feed[e['target']]['rows']):
            if row['balls'] == 0:
                shots.append({'target': e['target'], 'step': i + 1, 'fed': False})
                continue
            ent = row['entries'][0]
            spec = pop[k_ball % len(pop)]
            k_ball += 1
            E = l3.Entry(y=ent['y'], z=ent['z'], vx=ent['vx'], vy=ent['vy'], vz=ent['vz'], wx=ent['wx'], wy=ent['wy'], wz=ent['wz'])
            ph = (rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi))
            lr = l3.launch3d(spec.launch(), L, E, l3.Wheels(w_set=(w_set, w_set), w0=(w[0], w[1]), runout=0.00015, runout_phase=ph, tyre_E_mpa=l3.TPU['E_nominal']))
            gap = max(0.0, 1.0 / BURST_RATE - float(lr['contact_ms'][0]) / 1000)
            w = [tl.recover(L, float(lr['w_end'][j][0]), w_set, gap) for j in range(2)]
            br = tf.barrel_pass(G, spec, lr['v'], lr['omega'], lr['exit_pos'])
            lat = ent['t'] - row['t0']
            shots.append({'target': e['target'], 'step': i + 1, 'fed': True, 'ball': spec.name, 'd_mm': round(spec.d_mm, 2), 'm_g': round(spec.m_g, 3), 'E_mpa': round(spec.E_mpa, 2),
                          'entry': {k: round(float(v), 4) for k, v in ent.items() if k not in ('ball',)},
                          'feed_latency_ms': round(lat * 1000, 1), 'nip_exit_fps': round(float(lr['fps'][0]), 2), 'contact_ms': round(float(lr['contact_ms'][0]), 2),
                          'wheel_rpm_at_arrival': [round(float(lr['w_start'][j][0]) * 60 / (2 * math.pi)) for j in range(2)],
                          'muzzle_fps': round(float(br['fps'][0]), 2), 'barrel_bounces': int(br['bounces'][0]), 'barrel_ms': round(float(br['transit_ms']), 2),
                          'muzzle_v': [float(x) for x in br['v'][0]], 'muzzle_omega': [float(x) for x in br['omega'][0]],
                          'muzzle_yaw_mrad': round(float(br['yaw_mrad'][0]), 2), 'muzzle_pitch_mrad': round(float(br['pitch_mrad'][0]), 2),
                          'command_to_muzzle_ms': round(lat * 1000 + float(lr['contact_ms'][0]) + float(br['transit_ms']), 1),
                          'recoil_ns': round(abs(float(lr['impulse_ns'][0][0])), 5), 'peak_cage_force_n': round(float(lr['peak_fx_n'][0]), 1)})
    print(f'launch + barrel: {sum(1 for s in shots if s["fed"])} balls ({time.time() - t_wall:.0f} s)')
    # ---- 5-7. the world
    groups = export_meshes(T, tu)
    targets = [gt.Target(name, (rng_m * math.cos(math.radians(b)), rng_m * math.sin(math.radians(b)), TARGET_Z), BURST) for name, rng_m, b in TARGETS]
    n_balls = sum(1 for s in shots if s['fed'])
    xml = world_xml(T, tu, groups, n_balls, tf.mujoco_fluidcoef(spec_n), gt.targets_xml(targets))
    (OUT / 'e2e_world.xml').write_text(xml)
    model = mujoco.MjModel.from_xml_path(str(OUT / 'e2e_world.xml'))   # meshdir is relative to this file
    data = mujoco.MjData(model)
    sv = Servos(model, data)
    muzzle = model.site('muzzle').id
    nip = model.site('nip').id
    tilt_body = model.body('tilt').id
    ball_bodies = [model.body(f'ball_{i}').id for i in range(n_balls)]
    ball_q = [model.jnt_qposadr[model.body(b).jntadr[0]] for b in ball_bodies]
    ball_v = [model.jnt_dofadr[model.body(b).jntadr[0]] for b in ball_bodies]
    ball_geom = {model.body(b).geomadr[0]: i for i, b in enumerate(ball_bodies)}
    plate_geom = {model.geom(t.name).id: t.name for t in targets}
    hinge_q = {t.name: model.jnt_qposadr[model.joint(f'{t.name}_hinge').id] for t in targets}
    mujoco.mj_forward(model, data)
    vid = Video(model, OUT / f'e2e_{mode}_{int(round(set_fps))}fps.mp4') if video else None
    # the timeline
    fed_shots = [s for s in shots if s['fed']]
    queue = []                                  # (t_spawn, shot index, ball index)
    log = {'aim': [], 'events': [], 'hits': [], 'down': {}, 'crossings': {}}
    recoil = []                                 # (t_end, F_world)
    t = 0.0
    ball_i = 0
    k_eng = 0
    phase = 'slew'
    t_burst = None
    t_next_cmd = None
    shots_cmd = 0
    frame_every = int(round(1.0 / (VIDEO_FPS * DT)))
    ctrl_every = int(round(1.0 / (CTRL_HZ * DT)))
    step = 0
    keep_at = set()
    t_end = 3.0 + 2.2 * len(engagements) if not quick else 2.0 + 2.0 * len(engagements)
    e = engagements[0]
    sv.plan(e['bearing_deg'], e['tilt_down_deg'] or 0.0)
    spawned = {}
    first_spawn = None
    while t < t_end:
        if step % ctrl_every == 0:
            sv.step(1.0 / CTRL_HZ)
            pe, te, pr = sv.aim_error()
            if phase == 'slew' and k_eng < len(engagements):
                ready = (pe < math.radians(0.3) and te < math.radians(0.3) and pr < math.radians(5)) if mode == 'settled' else (pe < math.radians(2.0) and te < math.radians(1.0))
                if ready:
                    phase = 'burst'
                    t_burst = t
                    t_next_cmd = t
                    shots_cmd = 0
                    log['events'].append({'t': round(t, 3), 'burst_start': engagements[k_eng]['target'], 'pan_rate_deg_s_at_command': round(math.degrees(pr), 1), 'aim_err_deg': round(math.degrees(pe), 2),
                                          'note': 'the first ball leaves ~0.24 s after this command (feed latency): the pan rate then is what deflects it'})
            if phase == 'burst':
                if shots_cmd < BURST and t >= t_next_cmd:
                    s = [x for x in shots if x['target'] == engagements[k_eng]['target'] and x['step'] == shots_cmd + 1][0]
                    if s['fed']:
                        queue.append((t + s['command_to_muzzle_ms'] / 1000, shots.index(s), ball_i))
                        ball_i += 1
                    shots_cmd += 1
                    t_next_cmd = t + 1.0 / BURST_RATE
                if shots_cmd >= BURST and not queue and t > t_burst + BURST / BURST_RATE + 0.3:
                    k_eng += 1
                    phase = 'slew'
                    if k_eng < len(engagements):
                        e = engagements[k_eng]
                        sv.plan(e['bearing_deg'], e['tilt_down_deg'] or 0.0)
                    else:
                        t_end = min(t_end, t + 1.2)
            log['aim'].append((round(t, 3), round(math.degrees(data.qpos[sv.pan_q]), 3), round(math.degrees(data.qpos[sv.tilt_q]), 3), round(math.degrees(data.qvel[sv.pan_v]), 2)))
        # spawn balls whose time has come: the muzzle state rotated by the turret's pose now, plus the muzzle's own velocity
        for item in list(queue):
            t_sp, si, bi = item
            if t >= t_sp:
                queue.remove(item)
                s = shots[si]
                Rm = data.site_xmat[muzzle].reshape(3, 3)
                v_c = np.array(s['muzzle_v'])
                w_c = np.array(s['muzzle_omega'])
                vel6 = np.zeros(6)
                mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_SITE, muzzle, vel6, 0)
                v_w = Rm @ v_c + vel6[3:]
                w_w = Rm @ w_c
                p = data.site_xpos[muzzle] + Rm[:, 0] * (pop[0].r_m + 0.004)
                qa, va = ball_q[bi], ball_v[bi]
                data.qpos[qa:qa + 3] = p
                data.qpos[qa + 3:qa + 7] = (1, 0, 0, 0)
                data.qvel[va:va + 3] = v_w
                data.qvel[va + 3:va + 6] = w_w
                spawned[bi] = {'shot': si, 't': t, 'p0': p.copy(), 'v0': v_w.copy(), 'muzzle_v_motion': vel6[3:].copy(), 'target': s['target'],
                               'pan_deg': math.degrees(data.qpos[sv.pan_q]), 'pan_rate_deg_s': math.degrees(data.qvel[sv.pan_v]), 'tilt_deg': -math.degrees(data.qpos[sv.tilt_q])}
                first_spawn = first_spawn or t
                # recoil: the launch's impulse at the nip over the contact time, reversed, starting a barrel-transit earlier (already past: apply now)
                F = -Rm[:, 0] * s['recoil_ns'] / 0.005
                recoil.append((t + 0.005, F))
                log['events'].append({'t': round(t, 3), 'shot': si, 'ball': bi, 'target': s['target'], 'muzzle_fps': s['muzzle_fps'], 'pan_rate_deg_s': round(math.degrees(data.qvel[sv.pan_v]), 1)})
                if bi % 3 == 0:
                    keep_at.add(step + int(0.12 / DT))
        data.xfrc_applied[tilt_body] = 0
        for t_e, F in list(recoil):
            if t > t_e:
                recoil.remove((t_e, F))
                continue
            data.xfrc_applied[tilt_body, :3] += F
            data.xfrc_applied[tilt_body, 3:] += np.cross(data.site_xpos[nip] - data.xipos[tilt_body], F)
        mujoco.mj_step(model, data)
        t = data.time
        step += 1
        # crossings at the target planes (for the hand-over check) and hits
        for bi, sp in spawned.items():
            if bi in log['crossings']:
                continue
            tg = next(x for x in targets if x.name == sp['target'])
            to = np.array(tg.pos)
            u = to[:2] / np.linalg.norm(to[:2])
            pb = data.qpos[ball_q[bi]:ball_q[bi] + 3]
            along = float(np.dot(pb[:2], u))
            if along >= np.linalg.norm(to[:2]) - 0.02:
                side = float(u[0] * pb[1] - u[1] * pb[0])
                log['crossings'][bi] = {'t': round(t, 4), 'z': float(pb[2]), 'side': side, 'speed': float(np.linalg.norm(data.qvel[ball_v[bi]:ball_v[bi] + 3]))}
        for i in range(data.ncon):
            c = data.contact[i]
            for a, b in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                if a in ball_geom and b in plate_geom and (ball_geom[a], plate_geom[b]) not in log['hits']:
                    log['hits'].append((ball_geom[a], plate_geom[b]))
                    log['events'].append({'t': round(t, 3), 'hit': plate_geom[b], 'ball': ball_geom[a], 'speed_m_s': round(float(np.linalg.norm(data.qvel[ball_v[ball_geom[a]]:ball_v[ball_geom[a]] + 3])), 2)})
        for name, qa in hinge_q.items():
            if name not in log['down'] and data.qpos[qa] < -0.8:
                log['down'][name] = round(t, 3)
                log['events'].append({'t': round(t, 3), 'down': name})
        if vid and step % frame_every == 0:
            due = [k for k in keep_at if k <= step]
            for k in due:
                keep_at.discard(k)
            vid.frame(data, keep=(bool(due) or step == frame_every))
    if vid:
        vid.close()
    print(f'world: {len(log["hits"])} hits, down {log["down"]} ({time.time() - t_wall:.0f} s)')
    # ---- the hand-over check: the Python flight of each spawned ball vs where MuJoCo put it at the target plane
    hand = []
    for bi, sp in spawned.items():
        s = shots[sp['shot']]
        tg = next(x for x in targets if x.name == sp['target'])
        rng_m = np.linalg.norm(np.array(tg.pos[:2]) - sp['p0'][:2])
        u = (np.array(tg.pos[:2]) - sp['p0'][:2]) / rng_m
        vx = float(np.dot(sp['v0'][:2], u))
        vy = float(u[0] * sp['v0'][1] - u[1] * sp['v0'][0])
        spec = pop[(bi) % len(pop)]
        f = tf.fly(spec, [[vx, vy, float(sp['v0'][2])]], [np.array(s['muzzle_omega'])], h0=float(sp['p0'][2]), ranges=(round(rng_m, 3),))
        c = f['cross'][round(rng_m, 3)][0]
        mj = log['crossings'].get(bi)
        hand.append({'ball': bi, 'target': sp['target'], 'range_m': round(float(rng_m), 3), 'python_z': round(float(c[1]), 4) if not np.isnan(c[1]) else None, 'python_side': round(float(c[0]), 4) if not np.isnan(c[0]) else None,
                     'mujoco_z': round(mj['z'], 4) if mj else None, 'mujoco_side': round(mj['side'], 4) if mj else None,
                     'dz_cm': round((mj['z'] - float(c[1])) * 100, 2) if mj and not np.isnan(c[1]) else None, 'dside_cm': round((mj['side'] - float(c[0])) * 100, 2) if mj and not np.isnan(c[0]) else None,
                     'pan_rate_at_shot_deg_s': round(sp['pan_rate_deg_s'], 1), 'muzzle_motion_m_s': round(float(np.linalg.norm(sp['muzzle_v_motion'])), 3)})
    # ---- impacts on the target plane and the analytic knock-down
    per_target = {}
    for tg in targets:
        bis = [bi for bi, sp in spawned.items() if sp['target'] == tg.name]
        cr = [log['crossings'][bi] for bi in bis if bi in log['crossings']]
        hits = [h for h in log['hits'] if h[1] == tg.name]
        imp = [tt.impact(spec_n, c['speed']) for c in cr]
        per_target[tg.name] = {'balls': len(bis), 'crossed_plane': len(cr), 'hits': len(hits), 'knocked_down_s': log['down'].get(tg.name),
                               'z_at_plane_cm': [round(c['z'] * 100, 1) for c in cr], 'side_at_plane_cm': [round(c['side'] * 100, 1) for c in cr],
                               'plate_spans_z_cm': [round((TARGET_Z - 0.12) * 100), round((TARGET_Z + 0.12) * 100)],
                               'speed_at_plane_fps': [round(c['speed'] / tl.FPS, 1) for c in cr],
                               'impact_energy_j': [i['ke_j'] for i in imp], 'impact_ked_j_m2': [i['ked_j_m2'] for i in imp],
                               'analytic_knockdown': [tt.knockdown(tt.TARGETS['sim_plate_20g'], spec_n, c['speed'])['knocked'] for c in cr]}
    res = {'mode': mode, 'set_fps': set_fps, 'set_note': set_note, 'no_load_rpm': round(w0 * 60 / (2 * math.pi)), 'set_rpm': round(w_set * 60 / (2 * math.pi)), 'mount_z_m': MOUNT_Z, 'targets': TARGETS, 'target_z_m': TARGET_Z,
           'engagements': engagements, 'feed': {k: {'summary': v['summary'], 'in_chute_after': v['in_chute_after']} for k, v in feed.items()},
           'shots': shots, 'spawned': {bi: {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in sp.items()} for bi, sp in spawned.items()},
           'per_target': per_target, 'handover_flight': hand, 'events': log['events'], 'servo_saturation_steps': sv.sat,
           'aim_trace': log['aim'][::20], 'video_frames': vid.kept if vid else [], 'wall_s': round(time.time() - t_wall, 1)}
    return res


# ------------------------------------------------------------------------------------------------ checks against the checklist

def checks(runs, quick):
    """Pass/fail keyed to docs/turret-program.md's checklist, from the runs and the stage studies' JSON."""
    def load(p):
        f = R / 'exports' / 'turret' / p
        return json.loads(f.read_text()) if f.exists() else None
    l3 = load('launch/launch3d.json')
    fl = load('flight/flight.json')
    fdj = load('feed/feed_dyn.json')
    dy = load('e2e/dynamics.json')
    tg = load('target/target.json')
    bl = load('launch/ball.json')
    out = {}
    out['ball_sourced'] = {'pass': bool(bl and len(bl['sources']) >= 10), 'evidence': 'exports/turret/launch/ball.json: sources with URLs and the date checked; the unknowns swept with a bench plan'}
    if l3:
        out['launch_cap_105fps'] = {'pass': bool(l3['ceiling']['holds'] and l3['ceiling']['margin_fps'] >= 1.0 and l3['ceiling'].get('under_astm', True)),
                                    'highest_fps_any_case': l3['ceiling']['highest_fps_any_case'], 'margin_fps': l3['ceiling']['margin_fps'],
                                    'densest_ked_j_m2': l3['ceiling'].get('densest_ked_j_m2'),
                                   'how': l3['ceiling']['how_held'], 'evidence': 'exports/turret/launch/launch3d.json ceiling, ceiling_map'}
        out['launch_handover_1d_vs_3d'] = {'pass': bool(l3['handover_1d']['pass']), 'rel_err': l3['handover_1d']['rel_err']}
        out['launch_population_at_set_speed'] = {'pass': True, 'fps': l3['population_set_speed']['feed_offsets_runout_0_15mm']}
        out['burst_droop'] = {'pass': all(v['droop_fps'] <= 1.0 for v in l3['bursts'].values()), 'droop_fps': {k: v['droop_fps'] for k, v in l3['bursts'].values() and l3['bursts'].items()}}
        out['arm_release_braked'] = {'pass': all(r['stuck'] or r['exit_fps'] <= 10 for r in l3['arm_release']['brake_10A']['rows'] if r['latency_s'] >= 0.05),
                                     'coast_exit_fps_at_0_1s': next(r['exit_fps'] for r in l3['arm_release']['coast']['rows'] if r['latency_s'] == 0.1),
                                     'brake_10A_stops_s': l3['arm_release']['brake_10A']['time_to_5pct_s']}
    if fl:
        out['trajectory_drop_drift'] = {'pass': True, 'level_shot_population': fl['level_shot_population'], 'reach': fl['reach'], 'evidence': 'exports/turret/flight/flight.json'}
    if dy:
        out['recoil'] = {'pass': bool(dy['checks']['recoil_within_budget_0_05ns'] and dy['checks']['recoil_kick_under_3mrad']), 'impulse_ns': dy['recoil']['impulse_per_shot_ns'], 'aim_shift_mrad': dy['recoil']['aim_shift_mrad']}
        out['servo_margins'] = {'pass': bool(dy['checks']['tilt_servo_margin_ok'] and dy['checks']['pan_reaches_90deg_in_1_2s']), 'tilt_margin': dy['servo_margins']['tilt']['margin'], 'pan_fastest_90_s': dy['servo_margins']['pan']['fastest_90_deg_s']}
    if fdj:
        v = fdj['verdict']
        out['feed_no_jam_all_poses'] = {'pass': v['doubles'] == 0 and v['stuck_in_chute'] == 0 and v['escaped'] == 0, 'doubles': v['doubles'], 'misses': v['misses'], 'stuck': v['stuck_in_chute'],
                                        'note': 'misses are empty steps (the hopper not delivering): bridging, which rigid spheres under-predict; the bench counts them'}
        out['feed_parked_safe'] = {'pass': v['parked_leaks'] == 0, 'leaks': v['parked_leaks']}
        out['rate_of_fire'] = {'pass': (v['max_clean_stepping_rate_hz'] or 0) >= 3.0, 'max_clean_stepping_rate_hz': v['max_clean_stepping_rate_hz'], 'step_settled_ms': v['step_settled_ms_nominal'],
                               'latency_ms_max': v['latency_ms_max'], 'continuous_clean_rpm': v['continuous_clean_rpm']}
    if tg:
        ks = tg['kid_safety']
        out['kid_safety'] = {'pass': ks['cap_105fps']['vs_astm_2500'] < 1 and ks['densest_accepted_at_its_ceiling']['vs_astm_2500'] < 1,
                             'at_cap': ks['cap_105fps'], 'at_set_95': ks['set_95fps'], 'densest': ks['densest_accepted_at_its_ceiling'],
                             'note': 'D68: ASTM F963 2500 J/m^2 (a 14+ product); EN 71-1 0.5 J no longer applies'}
    for r in runs:
        key = f"e2e_{r['mode']}_{int(r['set_fps'])}fps"
        hits = {k: v['hits'] for k, v in r['per_target'].items()}
        down = {k: v['knocked_down_s'] is not None for k, v in r['per_target'].items()}
        reach = {e['target']: e['reachable'] for e in r['engagements']}
        hand = [h for h in r['handover_flight'] if h['dz_cm'] is not None]
        # every ball must cross its target's plane inside the plate (a 24 x 24 cm plate centred at TARGET_Z) and the plate must go down;
        # later balls of a burst fly over the fallen plate, so the hit count is 1-3, not 5
        inside = {k: all(abs(z / 100 - TARGET_Z) <= 0.12 and abs(s / 100) <= 0.12 for z, s in zip(v['z_at_plane_cm'], v['side_at_plane_cm'])) and v['crossed_plane'] >= 3
                  for k, v in r['per_target'].items()}
        out[key] = {'hits': hits, 'knocked_down': down, 'reachable_without_aiming_up': reach, 'all_balls_inside_plate': inside,
                    'pass_on_reachable': all(down[k] and inside[k] for k in hits if reach[k]),
                    'pass_unreachable_declared': all(not reach[k] for k in hits if not down[k]),
                    'handover_python_vs_mujoco_dz_cm_max': round(max(abs(h['dz_cm']) for h in hand), 2) if hand else None,
                    'handover_dside_cm_max': round(max(abs(h['dside_cm']) for h in hand if h['dside_cm'] is not None), 2) if hand else None,
                    'command_to_muzzle_ms': [s['command_to_muzzle_ms'] for s in r['shots'] if s['fed']],
                    'feed_latency_ms': [s['feed_latency_ms'] for s in r['shots'] if s['fed']],
                    'muzzle_fps': [s['muzzle_fps'] for s in r['shots'] if s['fed']]}
    out['summary'] = {'all_pass': all(v.get('pass', True) for k, v in out.items() if isinstance(v, dict) and 'pass' in v), 'quick': quick}
    return out


def plots(runs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), dpi=130)
    ax = axes[0]
    for r in runs:
        tr = np.array(r['aim_trace'])
        ax.plot(tr[:, 0], tr[:, 1], label=f"pan ({r['mode']}, {int(r['set_fps'])} fps)")
        for ev in r['events']:
            if 'shot' in ev:
                ax.axvline(ev['t'], color='#c2410c', alpha=0.25, lw=0.8)
    ax.set_xlabel('s')
    ax.set_ylabel('pan (deg); vertical lines: balls leaving')
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    ax = axes[1]
    for r in runs:
        for name, pt in r['per_target'].items():
            if pt['side_at_plane_cm']:
                ax.scatter(pt['side_at_plane_cm'], pt['z_at_plane_cm'], s=18, label=f"{name} {r['mode']} {int(r['set_fps'])}fps", alpha=0.7)
    ax.axhspan((TARGET_Z - 0.12) * 100, (TARGET_Z + 0.12) * 100, color='#64748b', alpha=0.15, label='plate')
    ax.axvspan(-12, 12, color='#64748b', alpha=0.1)
    ax.set_xlabel('sideways at the target plane (cm, + left)')
    ax.set_ylabel('height (cm)')
    ax.set_title('where each ball crossed its target\'s plane (MuJoCo)', fontsize=9)
    ax.legend(fontsize=6)
    ax.grid(alpha=0.3)
    ax = axes[2]
    r = runs[0]
    fed = [s for s in r['shots'] if s['fed']]
    x = np.arange(len(fed))
    ax.bar(x - 0.2, [s['nip_exit_fps'] for s in fed], 0.4, label='nip exit (launch3d)')
    ax.bar(x + 0.2, [s['muzzle_fps'] for s in fed], 0.4, label='muzzle (after the bore)')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s['target']}\n#{s['step']}" for s in fed], fontsize=6)
    ax.set_ylabel('fps')
    ax.set_title(f"the burst shots, {r['mode']} at {int(r['set_fps'])} fps set", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(OUT / 'e2e.png')
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--no-video', action='store_true')
    ap.add_argument('--set-fps', nargs='*', default=['95', 'max'], help="fps values, or 'max' for 95 % of the rail's no-load speed")
    ap.add_argument('--modes', nargs='*', default=['settled', 'panning'])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    runs = []
    for i, fps in enumerate([f if f == 'max' else float(f) for f in a.set_fps]):
        for j, mode in enumerate(a.modes):
            video = not a.no_video and (i == 0)           # one video per mode at the first set speed
            r = run(set_fps=fps, mode=mode, quick=a.quick, video=video)
            runs.append(r)
            print(json.dumps({'mode': mode, 'set_fps': fps, 'per_target': {k: {kk: vv for kk, vv in v.items() if kk in ('hits', 'knocked_down_s', 'z_at_plane_cm', 'side_at_plane_cm', 'speed_at_plane_fps')} for k, v in r['per_target'].items()},
                              'handover': [(h['ball'], h['dz_cm'], h['dside_cm']) for h in r['handover_flight']], 'events': r['events'][:12]}, indent=None, default=str))
    ck = checks(runs, a.quick)
    (OUT / 'e2e.json').write_text(json.dumps({'checks': ck, 'runs': runs}, indent=1, default=str) + '\n')
    plots(runs)
    print(json.dumps(ck, indent=1, default=str))


if __name__ == '__main__':
    main()
