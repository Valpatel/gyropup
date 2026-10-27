"""Single-leg test rig: one five-bar leg module (cad/fivebar.py) on a vertical rail, in MuJoCo.

    python -m sim.leg_rig [--video] [--only stand_up squat jump drop_150 power_off] [--half-mass 11]

The rig is what we will build first: a carriage on a vertical rail (one slide joint, a rubber stop at the bottom)
carries the hip frame, both RS-04s and a dummy mass for half the body; the leg stands on the floor and can crouch,
stand, jump and land, and its wheel can spin. The model comes from the CAD: every printed part's mass, centre of mass
and inertia from its solid, the bought parts from their datasheets; the five-bar is closed by an equality constraint at
the wheel axle, the upper links' stops are joint limits as stiff as their TPU sleeves.

The controller is the virtual-model control the RoboMaster balance robots use: a spring-damper on the virtual leg
(hip centre to wheel axle: length and lean) with gravity feed-forward, mapped to the two motors by the five-bar's
Jacobian, each torque clipped to the motor's torque-speed line and the firmware cap.

Writes exports/leg/rig-results.json (peaks per scenario, the loads for the FEA) and, with --video, rig_<name>.mp4.
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')
import mujoco  # noqa: E402
import numpy as np  # noqa: E402

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402
from sim.leg_control import Gains, clip_motor, polar, vmc_from_state  # noqa: E402  (the controller, simulator-free)

OUT = R / 'exports' / 'leg'
G = 9.81
FPS = 30
CAT = {it['id']: it for f in ('leg_actuators.json', 'wheel_motors.json') for it in json.loads((R / 'catalog' / f).read_text())}
MOTOR = CAT[fb.MOTOR]['specs']
WHEEL = CAT[fb.WHEEL]['specs']
BUS_V = 54.0                                     # FLEXVOLT in 60 V mode, nominal
HALF_MASS = 14.75                                  # kg one leg carries: half the robot's 29.5 kg (docs/body-plan.md's
                                                   # budget with its real parts; 28.5 kg is the target; sim/robot_v2.py
                                                   # had 26.2 with an interim body).
                                                   # The ballast is its own welded body: the carriage's explicit
                                                   # <inertial> made MuJoCo drop a geom mass there (the rig carried 8.5 kg
                                                   # of a meant 11 until 2026-10-27; found by the spring study)
LEG_PEAK = MOTOR['peak_torque_nm']               # 120 N m
LEG_CAP = 60.0                                   # firmware cap (designs/default.json leg_torque_limit_nm)
LEG_OMEGA = MOTOR['no_load_speed_rpm'] * BUS_V / MOTOR['voltage_nominal_v'] * 2 * math.pi / 60
ROTOR_SHARE = 0.6                                # of the BotWheel's mass that spins (estimate, as sim/model.py)
WHEEL_R = (fb.gmi.motor_interface(fb.WHEEL)['od'] or 171.3) / 2000
# RS-04 rotor inertia is not published (the manual has none): ~3e-4 kg m^2 (a ~150 g rotor ring at r 45 mm, an
# estimate) x 9^2 reflected. It sets how hard a landing is: the motors' rotors are most of the leg's moving mass.
ARMATURE = 3.0e-4 * MOTOR['gear_ratio'] ** 2
# the stop: a TPU 95A sleeve (fivebar.TPU_SLEEVE: an 8 mm wall, ~18 x 11 mm contact) at 58 mm: k = E A / t, as a joint
# stiffness k r^2; E is the filament maker's (catalog/materials.json tpu95: Bambu TPU 95A HF, 9.8 MPa). Until
# 2026-10-27 the rig used an unsourced 40 MPa and a 4 mm wall: four times too stiff, with too little travel.
# the BotWheel's tyre: solid rubber with a tread (estimate ~150-250 N/mm radially): MuJoCo's contact as a 7.7 ms,
# 0.7-damped spring on the few kg behind it
TYRE_SOLREF = '0.0077 0.7'
TPU_E = json.loads((R / 'catalog/materials.json').read_text())['tpu95']['modulus_gpa'] * 1e9
OFF_DAMPING = 0.2 * (MOTOR['kt_nm_per_a'] / MOTOR['gear_ratio']) ** 2 / 0.15 * MOTOR['gear_ratio'] ** 2   # N m s/rad, see run()
TPU_WALL = (fb.TPU_SLEEVE[0] - fb.TPU_SLEEVE[1]) / 2 / 1000          # m
STOP_TRAVEL = (TPU_WALL - 0.5e-3) / (fb.P['stop_r'] / 1000)          # rad: the sleeve squeezed to 0.5 mm; then the steel post
STOP_K = TPU_E * (18e-3 * 11e-3) / TPU_WALL * (fb.P['stop_r'] / 1000) ** 2
STOP_B = 0.6 * math.sqrt(STOP_K * 0.1)   # N m s/rad: ~0.3 of critical for ~0.1 kg m^2 behind the stop


# ----------------------------------------------------------------------------------- the model

@functools.lru_cache(maxsize=1)
def mass_props():
    """Body of every moving group in its own link frame (SI), from the CAD solids."""
    from cadagent.robot import Body, solid_mass_properties, cylinder_body, combine
    mats = json.loads((R / 'catalog/materials.json').read_text())
    L = fb.leg_parts()
    sm = lambda name: solid_mass_properties(L.parts[name].val(), mats[L.meta[name]['material']]['density_g_cm3'], 1.0, name)
    l2 = fb.P['l2'] / 1000
    yb = fb.Y
    # bearings, pins, nuts (datasheet masses): 6001 22 g, 61812 110 g, ISO 7379 12x60 75 g, M10 nyloc 11 g
    kc = Body(2 * 0.022 + 0.075 + 0.011 + 0.008, (0.0, 0.05, 0.0), name='knee cartridge')
    ad = sm('output_adapter')                                    # built on the motor axis: already in the link frame (6061, D46)
    head_y = (fb.Y['motor_out'] + fb.gmi.output_adapter(fb.MOTOR, 'L')[1]['z_head_seat']) / 1000
    upper = combine([sm('upper_link'), ad, Body(0.008 * 8, (0.0, 0.015, 0.0), name='M5 x 8'),
                     Body(0.005 * 9, (0.0, head_y - 0.010, 0.0), name='9 x M5 x 25 into the motor')])
    front = combine([sm('front_link'), Body(0.110, (l2, 0.062, 0.0), name='61812'), kc])
    stator_kg = WHEEL['mass_g'] / 1000 * (1 - ROTOR_SHARE)
    wheel_link = combine([sm('wheel_link'), kc, Body(stator_kg, (l2, yb['wheel'] / 1000, 0.0), name='BotWheel stator'),
                          Body(4 * 0.015, (l2, 0.05, 0.0), name='M6 x 40')])
    rotor = cylinder_body(WHEEL['mass_g'] / 1000 * ROTOR_SHARE, WHEEL_R, 0.0446, axis='y', hollow_radius=0.6 * WHEEL_R,
                          center=(0.0, yb['wheel'] / 1000, 0.0), name='BotWheel rotor')
    frame = combine([sm('hip_frame'), Body(2 * MOTOR['mass_g'] / 1000, (0.0, (yb['motor'][0] + yb['motor'][1]) / 2000, 0.0), name='2 x RS-04'),
                     Body(2 * 0.110, (0.0, -0.006, 0.0), name='2 x 61812')])
    return {'upper': upper, 'front': front, 'wheel_link': wheel_link, 'rotor': rotor, 'frame': frame}


def _inertial(b, frame_shift=(0.0, 0.0, 0.0)):
    c = [b.com[i] - frame_shift[i] for i in range(3)]
    I = b.inertia
    full = f'{I[0][0]:.6g} {I[1][1]:.6g} {I[2][2]:.6g} {I[0][1]:.6g} {I[0][2]:.6g} {I[1][2]:.6g}'
    return f'<inertial pos="{c[0]:.5f} {c[1]:.5f} {c[2]:.5f}" mass="{b.mass:.4f}" fullinertia="{full}"/>'


def _q(phi):
    """MuJoCo quaternion turning a frame by phi (rad) about -y: its +x then points at angle phi in the x-z plane."""
    return f'{math.cos(phi / 2):.6f} 0 {-math.sin(phi / 2):.6f} 0'


REF_H = 300.0                                     # the model is built standing at this leg length (all joints 0)


def ref_pose():
    phi = fb.stance(REF_H)
    j = fb.fk(*phi)
    ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
    return {'phi1': phi[0], 'phi2': phi[1], 'af': ang(j['C'], j['E']), 'aw': ang(j['D'], j['E']), 'j': j}


def mjcf(half_mass: float, meshes: dict | None = None, rail_low: float = 0.115) -> tuple[str, dict]:
    """The rig as MJCF and its numbers. half_mass: what the leg carries (kg), its own parts included; rail_low: the leg
    length (m) at which the carriage lands on the rail's bottom stop."""
    mp = mass_props()
    rp = ref_pose()
    l1, l2 = fb.P['l1'] / 1000, fb.P['l2'] / 1000
    ax = fb.P['D'] / 2000
    moving = mp['upper'].mass * 2 + mp['front'].mass + mp['wheel_link'].mass + mp['rotor'].mass
    dummy = max(0.0, half_mass - moving - mp['frame'].mass)
    carriage_z = REF_H / 1000 + WHEEL_R
    fo, fi, ro, ri = fb.stop_angles()
    lim1 = (fi - rp['phi1'] - STOP_TRAVEL, fo - rp['phi1'] + STOP_TRAVEL)     # front: knees in .. knees out, plus the TPU
    lim2 = (ro - rp['phi2'] - STOP_TRAVEL, ri - rp['phi2'] + STOP_TRAVEL)     # rear (continuous angles)
    # the TPU sleeves are springs in the control loop (stop_torque); the joint's own limit is the steel post behind them
    stop = 'limited="true"'
    vis = lambda name, rgba: (f'<geom type="mesh" mesh="{name}" rgba="{rgba}" contype="0" conaffinity="0" group="1" mass="0"/>'
                              if meshes and name in meshes else '')
    asset = ''.join(f'<mesh name="{n}" file="{p}" scale="0.001 0.001 0.001"/>' for n, p in (meshes or {}).items())
    yw = fb.Y['wheel'] / 1000
    xml = f"""<mujoco model="gyropup_leg_rig">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="0.0005" gravity="0 0 -9.81" integrator="implicitfast"/>
  <visual><headlight diffuse="0.6 0.6 0.6" ambient="0.35 0.35 0.35"/><global offwidth="1280" offheight="720"/></visual>
  <asset>{asset}
    <texture name="grid" type="2d" builtin="checker" rgb1=".86 .88 .9" rgb2=".78 .8 .83" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="8 8"/>
  </asset>
  <default><geom friction="1.0 0.005 0.0001" solref="0.004 1"/></default>
  <worldbody>
    <light pos="0.6 1.2 1.6" dir="-0.3 -0.6 -1"/>
    <geom name="floor" type="plane" size="2 2 0.1" material="grid"/>
    <geom name="rail" type="box" size="0.012 0.012 0.55" pos="0 -0.10 0.55" rgba=".55 .58 .62 1" contype="0" conaffinity="0"/>
    <body name="carriage" pos="0 0 {carriage_z:.5f}">
      <joint name="rail" type="slide" axis="0 0 1" range="{rail_low + WHEEL_R - carriage_z:.4f} 0.6" damping="2" frictionloss="2"
             solreflimit="0.006 0.6"/>
      {_inertial(mp['frame'])}
      <body name="ballast" pos="0 -0.12 0">
        <inertial pos="0 0 0" mass="{max(dummy, 1e-3):.3f}" diaginertia="{max(dummy, 1e-3) * (0.04 ** 2 + 0.12 ** 2) / 12:.6g} {max(dummy, 1e-3) * 0.12 ** 2 / 6:.6g} {max(dummy, 1e-3) * (0.12 ** 2 + 0.04 ** 2) / 12:.6g}"/>
        <geom type="box" size="0.06 0.02 0.06" mass="0" rgba=".3 .32 .36 1" contype="0" conaffinity="0"/>
      </body>
      {vis('hip_frame', '.4 .43 .48 1')}
      <geom type="cylinder" size="0.06 0.028" pos="{ax} {fb.Y['motor'][0] / 2000 + fb.Y['motor'][1] / 2000:.4f} 0" euler="1.5708 0 0" rgba=".16 .17 .19 1" contype="0" conaffinity="0" mass="0"/>
      <geom type="cylinder" size="0.06 0.028" pos="{-ax} {fb.Y['motor'][0] / 2000 + fb.Y['motor'][1] / 2000:.4f} 0" euler="1.5708 0 0" rgba=".16 .17 .19 1" contype="0" conaffinity="0" mass="0"/>
      <body name="upper_f" pos="{ax} 0 0" quat="{_q(rp['phi1'])}">
        <joint name="motor_f" type="hinge" axis="0 -1 0" armature="{ARMATURE:.4f}" damping="0.05" frictionloss="0.4" range="{lim1[0]:.4f} {lim1[1]:.4f}" {stop}/>
        {_inertial(mp['upper'])}
        {vis('upper_link', '.96 .72 .16 1')}
        <body name="lower_f" pos="{l1} 0 0" quat="{_q(rp['af'] - rp['phi1'])}">
          <joint name="knee_f" type="hinge" axis="0 -1 0" damping="0.02"/>
          {_inertial(mp['front'])}
          {vis('front_link', '.96 .72 .16 1')}
        </body>
      </body>
      <body name="upper_r" pos="{-ax} 0 0" quat="{_q(rp['phi2'])}">
        <joint name="motor_r" type="hinge" axis="0 -1 0" armature="{ARMATURE:.4f}" damping="0.05" frictionloss="0.4" range="{lim2[0]:.4f} {lim2[1]:.4f}" {stop}/>
        {_inertial(mp['upper'])}
        {vis('upper_link', '.96 .72 .16 1')}
        <body name="lower_r" pos="{l1} 0 0" quat="{_q(rp['aw'] - rp['phi2'])}">
          <joint name="knee_r" type="hinge" axis="0 -1 0" damping="0.02"/>
          {_inertial(mp['wheel_link'])}
          {vis('wheel_link', '.93 .62 .12 1')}
          <body name="wheel" pos="{l2} 0 0">
            <joint name="wheel" type="hinge" axis="0 -1 0" damping="0.01"/>
            {_inertial(mp['rotor'])}
            <geom name="tyre" type="cylinder" size="{WHEEL_R:.4f} 0.0223" pos="0 {yw:.4f} 0" euler="1.5708 0 0" rgba=".1 .1 .11 1" mass="0"
                  solref="{TYRE_SOLREF}"/>
            <geom type="cylinder" size="{WHEEL_R - 0.016:.4f} 0.0226" pos="0 {yw:.4f} 0" euler="1.5708 0 0" rgba=".33 .35 .38 1" contype="0" conaffinity="0" mass="0"/>
            <geom type="box" size="0.05 0.0228 0.006" pos="0 {yw:.4f} 0" rgba=".8 .3 .1 1" contype="0" conaffinity="0" mass="0"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <equality><connect name="apex" body1="lower_f" body2="lower_r" anchor="{l2} 0 0" solref="0.002 1"/></equality>
  <contact><exclude body1="carriage" body2="upper_f"/><exclude body1="carriage" body2="upper_r"/><exclude body1="lower_f" body2="lower_r"/></contact>
  <actuator>
    <motor name="motor_f" joint="motor_f" ctrlrange="-{LEG_PEAK} {LEG_PEAK}"/>
    <motor name="motor_r" joint="motor_r" ctrlrange="-{LEG_PEAK} {LEG_PEAK}"/>
    <motor name="wheel" joint="wheel" ctrlrange="-{WHEEL['peak_torque_nm']} {WHEEL['peak_torque_nm']}"/>
  </actuator>
</mujoco>"""
    info = {'half_mass_kg': half_mass, 'dummy_kg': round(dummy, 3), 'moving_kg': round(moving, 3), 'frame_kg': round(mp['frame'].mass, 3),
            'carriage_kg': round(mp['frame'].mass + dummy, 3), 'armature': ARMATURE, 'stop_k_nm_per_rad': round(STOP_K),
            'ref': {k: (v if not isinstance(v, float) else round(v, 5)) for k, v in rp.items() if k != 'j'}}
    return xml, info


def export_meshes(folder: Path) -> dict:
    """STL meshes of the printed parts in their link frames (mm), for the video."""
    import cadquery as cq
    folder.mkdir(parents=True, exist_ok=True)
    L = fb.leg_parts()
    out = {}
    for name in ('hip_frame', 'upper_link', 'front_link', 'wheel_link'):
        p = folder / f'{name}.stl'
        cq.exporters.export(L.parts[name].val(), str(p), tolerance=0.3, angularTolerance=0.3)
        out[name] = str(p)
    return out


# ----------------------------------------------------------------------------------- the leg's state and control

class Leg:
    def __init__(self, m: mujoco.MjModel):
        self.m = m
        self.rp = ref_pose()
        j = lambda n: m.joint(n)
        self.q = {n: j(n).qposadr[0] for n in ('rail', 'motor_f', 'motor_r', 'knee_f', 'knee_r', 'wheel')}
        self.v = {n: j(n).dofadr[0] for n in self.q}
        self.a = {n: m.actuator(n).id for n in ('motor_f', 'motor_r', 'wheel')}
        self.jid = {n: j(n).id for n in self.q}
        self.wheel_body = m.body('wheel').id

    def phi(self, d):
        return d.qpos[self.q['motor_f']] + self.rp['phi1'], d.qpos[self.q['motor_r']] + self.rp['phi2']

    def polar(self, d):
        """Virtual leg: length (m), lean (rad, + = wheel forward), their rates, the Jacobian d(x,z)/d(phi) (m/rad)."""
        p1, p2 = self.phi(d)
        return polar(p1, p2, d.qvel[self.v['motor_f']], d.qvel[self.v['motor_r']])

    def set_height(self, d, h_mm, rail_z=None):
        """Put the leg at a length (joints consistent with the closed loop) and the carriage on the floor (or at rail_z)."""
        phi = fb.stance(h_mm)
        j = fb.fk(*phi)
        ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
        d.qpos[self.q['motor_f']] = phi[0] - self.rp['phi1']
        d.qpos[self.q['motor_r']] = phi[1] - self.rp['phi2']
        d.qpos[self.q['knee_f']] = (ang(j['C'], j['E']) - phi[0]) - (self.rp['af'] - self.rp['phi1'])
        d.qpos[self.q['knee_r']] = (ang(j['D'], j['E']) - phi[1]) - (self.rp['aw'] - self.rp['phi2'])
        z0 = self.m.body('carriage').pos[2]
        target = (h_mm / 1000 + WHEEL_R) if rail_z is None else rail_z
        d.qpos[self.q['rail']] = target - z0
        d.qvel[:] = 0
        mujoco.mj_forward(self.m, d)


def stop_torque(phi, omega, lo, hi):
    """The TPU sleeve's push (N m) on an upper link that has gone past a stop angle (lo .. hi, rad): a spring with
    some damping, pushing only."""
    if phi > hi:
        return min(0.0, -STOP_K * (phi - hi) - STOP_B * omega)
    if phi < lo:
        return max(0.0, STOP_K * (lo - phi) - STOP_B * omega)
    return 0.0


def vmc(leg: Leg, d, L_cmd, th_cmd=0.0, ff=0.0, g: Gains = Gains(), force=None):
    """Motor torques for a virtual spring-damper leg (or a straight force push, force=N along the leg): the
    simulator-free law (sim/leg_control.py) on the simulated hips' angles and rates."""
    return vmc_from_state(leg.phi(d), (d.qvel[leg.v['motor_f']], d.qvel[leg.v['motor_r']]), L_cmd, th_cmd, ff, g, force)


# ----------------------------------------------------------------------------------- scenarios

@dataclass
class Scenario:
    name: str
    title: str
    duration: float
    start_h: float = 300.0
    start_rail: float | None = None       # the carriage held up (m) for a drop
    cap: float | None = LEG_CAP
    rail_low: float = 0.115               # the rail's bottom stop as a leg length (m); below the leg's own stops for power_off


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


SCENARIOS = {
    'stand_up': Scenario('stand_up', 'Stand up from the deepest crouch in 1 s and hold', 3.0, start_h=140.0),
    'squat': Scenario('squat', 'Three squats, 300 to 150 mm at 0.5 Hz', 6.5),
    'jump': Scenario('jump', 'Crouch, push off at the 60 N m cap, tuck in the air, land', 3.0),
    'jump_peak': Scenario('jump_peak', 'The same jump at the motors\' full 120 N m (no cap)', 3.0, cap=None),
    'drop_150': Scenario('drop_150', 'Dropped with the wheel 150 mm off the floor, the leg holding 300 mm', 2.0, start_rail=None),
    'power_off': Scenario('power_off', 'Standing, then the motors lose power (no damping): the leg folds onto its own stops', 2.5, rail_low=0.06),
    'power_off_damped': Scenario('power_off_damped', "The same, with the RS-04's power-off anti-backdrive damping (assumed 20 % of shorted phases)",
                                 2.5, rail_low=0.06),
}


def command(sc: Scenario, t: float, state: dict):
    """(L_cmd mm, mode) for a scenario at time t; mode 'pd', 'push', 'off'."""
    if sc.name == 'stand_up':
        return 140 + (300 - 140) * smooth((t - 0.3) / 1.0), 'pd'
    if sc.name == 'squat':
        return 225 + 75 * math.cos(2 * math.pi * 0.5 * max(0.0, t - 0.25)), 'pd'
    if sc.name in ('jump', 'jump_peak'):
        if t < 0.6:
            return 300 - 150 * smooth(t / 0.5), 'pd'
        if not state.get('pushed'):
            return None, 'push'
        return 250, 'pd'
    if sc.name == 'drop_150':
        return 300, 'pd'
    if sc.name.startswith('power_off'):
        return (300, 'pd') if t < 0.6 else (None, 'off')
    return 300, 'pd'


def run(sc: Scenario, half_mass: float, video: Path | None = None, meshes: dict | None = None) -> dict:
    xml, info = mjcf(half_mass, meshes, sc.rail_low)
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    leg = Leg(m)
    if sc.name == 'drop_150':
        leg.set_height(d, 300.0, rail_z=(300 + 150) / 1000 + WHEEL_R)
    else:
        leg.set_height(d, sc.start_h)
    ff = half_mass * G - (mass_props()['rotor'].mass + mass_props()['wheel_link'].mass * 0.5) * G   # what the leg holds up
    g = Gains()
    rec = []
    state = {}
    vw = None
    if video:
        vw = VideoWriter(m, video)
    steps = int(sc.duration / m.opt.timestep)
    every = max(1, int(round(1 / (FPS * m.opt.timestep))))
    rail0 = d.qpos[leg.q['rail']]
    top = rail0
    gear = {'motor_f': 0.0, 'motor_r': 0.0}          # the gearboxes' peak torque, every step (a landing's spike is ~ms)
    over = {'motor_f': 0.0, 'motor_r': 0.0}          # and the time each spends past the RS-04's peak rating
    joint = {'knee_f': 0.0, 'knee_r': 0.0, 'hip_f': 0.0, 'hip_r': 0.0, 'apex': 0.0}   # the joints' real forces, every step: in a landing
    jb = {'knee_f': m.body('lower_f').id, 'knee_r': m.body('lower_r').id,  # the links' own inertia takes much of the axle's
          'hip_f': m.body('upper_f').id, 'hip_r': m.body('upper_r').id}    # spike, so statics on the axle force overstates them
    for k in range(steps):
        t = k * m.opt.timestep
        L_cmd, mode = command(sc, t, state)
        L, th, dL, dth, J, (x, z) = leg.polar(d)
        if mode == 'push':
            tau = vmc(leg, d, None, 0.0, force=5000.0, g=g)          # as hard as the motors allow
            if L > 0.31 or (state.get('t_push') and t - state['t_push'] > 0.35):    # stop pushing well before full extension
                state['pushed'] = True
            state.setdefault('t_push', t)
        elif mode == 'off':
            # the RS-04's documented power-off anti-backdrive damping (manual 4.2.5): magnitude unknown; shorted phases would
            # give ~29 N m s/rad at the output (kt 0.233 N m/A x ke / ~0.15 ohm x 9^2); assumed 20 % of that
            b = OFF_DAMPING if sc.name == 'power_off_damped' else 0.0
            tau = np.array([-b * d.qvel[leg.v['motor_f']], -b * d.qvel[leg.v['motor_r']]])
        else:
            contact = wheel_force(m, d, leg)[1] > 1.0
            gg = g if (contact or sc.name not in ('jump', 'jump_peak') or not state.get('pushed')) else Gains(kp_L=3000, kd_L=260)   # tuck
            tau = vmc(leg, d, L_cmd / 1000, 0.0, ff=ff if contact or not state.get('pushed') else 0.0, g=gg)
        for i, (n, a) in enumerate((('motor_f', 'motor_f'), ('motor_r', 'motor_r'))):
            om = d.qvel[leg.v[n]]
            d.ctrl[leg.a[a]] = float(tau[i]) if mode == 'off' else clip_motor(float(tau[i]), om, LEG_PEAK, LEG_OMEGA, sc.cap)
        d.ctrl[leg.a['wheel']] = 0.0
        p1, p2 = leg.phi(d)
        fo, fi, ro, ri = fb.stop_angles()
        for n, ph, lo, hi in (('motor_f', p1, fi, fo), ('motor_r', p2, ro, ri)):
            ts = stop_torque(ph, d.qvel[leg.v[n]], lo, hi)
            d.qfrc_applied[leg.v[n]] = ts
            state['stop_' + n] = ts
        mujoco.mj_step(m, d)
        top = max(top, d.qpos[leg.q['rail']])
        for n in gear:                                # the gearbox carries the motor's torque less what turns its rotor
            v = leg.v[n]
            tg = abs(float(d.actuator_force[leg.a[n]] - m.dof_armature[v] * d.qacc[v] - m.dof_damping[v] * d.qvel[v]))
            gear[n] = max(gear[n], tg)
            over[n] += m.opt.timestep if tg > LEG_PEAK else 0.0
        mujoco.mj_rnePostConstraint(m, d)
        for n, b in jb.items():                       # the force from the parent through the joint (world frame)
            joint[n] = max(joint[n], float(np.linalg.norm(d.cfrc_int[b][3:6])))
        fa = [d.efc_force[i] for i in range(d.nefc) if d.efc_type[i] == mujoco.mjtConstraint.mjCNSTR_EQUALITY]
        joint['apex'] = max(joint['apex'], float(np.linalg.norm(fa)) if fa else 0.0)   # the apex's connect: the lower links' push
        if k % 4 == 0:
            rec.append(sample(m, d, leg, t, state))
        if vw and k % every == 0:
            vw.frame(d)
    if vw:
        vw.close()
    res = summarise(sc, rec, info)
    res['jump_height_mm'] = round((top - rail0) * 1000, 1) if sc.name.startswith('jump') else None
    res['peak_gearbox_nm'] = round(max(gear.values()), 1)          # the rotor's inertia shows here, not in the motor torque
    res['gearbox_over_peak_ms'] = round(max(over.values()) * 1000, 1)
    res['peak_joint_force_n'] = {k: round(v, 1) for k, v in joint.items()}          # dynamic, every step
    return res


def wheel_force(m, d, leg):
    """Ground force on the wheel (world x, z), N."""
    f = np.zeros(6)
    tot = np.zeros(3)
    for i in range(d.ncon):
        c = d.contact[i]
        b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
        if leg.wheel_body not in (b1, b2):
            continue
        mujoco.mj_contactForce(m, d, i, f)
        fr = c.frame.reshape(3, 3)
        w = fr.T @ f[:3]                              # contact frame -> world
        tot += w if b2 == leg.wheel_body else -w
    return tot[0], tot[2]


def pin_forces(phi1, phi2, Fw, tau_wheel=0.0, at_axle=False):
    """Quasi-static loads in the linkage for a force Fw = (Fx, Fz) on the tyre's contact point, or (at_axle) on the
    axle (N): the front lower link's axial force (+ = compression), the knee pin forces (on the lower links, N) and the
    motor torques."""
    j = fb.fk(phi1, phi2)
    A, B, C, D, E = (np.array(j[k]) / 1000 for k in 'ABCDE')
    P = E if at_axle else E + np.array([0.0, -WHEEL_R])
    u = (E - C) / np.linalg.norm(E - C)
    cr = lambda a, b: a[0] * b[1] - a[1] * b[0]
    Fw = np.array(Fw)
    f = -cr(P - D, Fw) / cr(E - D, u)                 # moments about D on the wheel link + wheel
    FD = -(Fw + f * u)                                # on the wheel link at D, from the rear upper link
    t1 = cr(C - A, f * u)
    t2 = cr(D - B, -FD)
    return {'front_axial_n': f, 'knee_front_n': f * u, 'knee_rear_n': FD, 'tau_front': t1, 'tau_rear': t2,
            'apex_n': f * u}


def limit_torque(d, jid):
    """The torque a joint's stop (limit constraint) puts on it, N m."""
    tot = 0.0
    for i in range(d.nefc):
        if d.efc_type[i] == mujoco.mjtConstraint.mjCNSTR_LIMIT_JOINT and d.efc_id[i] == jid:
            tot += d.efc_force[i]
    return tot


def axle_force(m, d, leg):
    """The force the wheel puts on the wheel link at the axle (world x, z), N: the ground's push less what the wheel's
    own mass takes to stop or lift it (a landing's contact spike is mostly the wheel's)."""
    mujoco.mj_rnePostConstraint(m, d)
    f = d.cfrc_int[leg.wheel_body][3:6]                 # on the wheel, from its parent (the wheel link)
    return -f[0], -f[2]


def sample(m, d, leg, t, state=None):
    L, th, dL, dth, J, (x, z) = leg.polar(d)
    fx, fz = wheel_force(m, d, leg)
    ax, az = axle_force(m, d, leg)
    p1, p2 = leg.phi(d)
    pf = pin_forces(p1, p2, (ax, az), at_axle=True)
    state = state or {}
    stop_f = state.get('stop_motor_f', 0.0) + limit_torque(d, leg.jid['motor_f'])     # the TPU, plus the post if it got there
    stop_r = state.get('stop_motor_r', 0.0) + limit_torque(d, leg.jid['motor_r'])
    return {'t': t, 'L_mm': L * 1000, 'lean_deg': math.degrees(th), 'rail_mm': d.qpos[leg.q['rail']] * 1000,
            'tau_f': float(d.actuator_force[leg.a['motor_f']]), 'tau_r': float(d.actuator_force[leg.a['motor_r']]),
            'w_f': float(d.qvel[leg.v['motor_f']]), 'w_r': float(d.qvel[leg.v['motor_r']]),
            'Fx': fx, 'Fz': fz, 'Ax': ax, 'Az': az, 'front_axial': pf['front_axial_n'], 'knee_front': float(np.linalg.norm(pf['knee_front_n'])),
            'knee_rear': float(np.linalg.norm(pf['knee_rear_n'])), 'stop_f': float(stop_f), 'stop_r': float(stop_r),
            'phi1': p1, 'phi2': p2}


def summarise(sc, rec, info):
    pk = lambda k: max(abs(r[k]) for r in rec)
    i_wheel = max(range(len(rec)), key=lambda i: rec[i]['Fz'])
    i_axle = max(range(len(rec)), key=lambda i: math.hypot(rec[i]['Ax'], rec[i]['Az']))
    stops = [r for r in rec if abs(r['stop_f']) > 1.0 or abs(r['stop_r']) > 1.0]
    out = {'scenario': sc.name, 'title': sc.title, 'cap_nm': sc.cap,
           'peak_motor_nm': round(max(pk('tau_f'), pk('tau_r')), 1),
           'peak_motor_speed_rad_s': round(max(pk('w_f'), pk('w_r')), 2),
           'peak_wheel_force_n': round(rec[i_wheel]['Fz'], 1),
           'pose_at_peak_wheel_force': {'L_mm': round(rec[i_wheel]['L_mm'], 1), 'phi_deg': [round(math.degrees(rec[i_wheel]['phi1']), 1), round(math.degrees(rec[i_wheel]['phi2']), 1)]},
           'peak_axle_force_n': round(math.hypot(rec[i_axle]['Ax'], rec[i_axle]['Az']), 1),
           'axle_force_at_peak_n': [round(rec[i_axle]['Ax'], 1), round(rec[i_axle]['Az'], 1)],
           'pose_at_peak_axle_force': {'L_mm': round(rec[i_axle]['L_mm'], 1), 'phi_deg': [round(math.degrees(rec[i_axle]['phi1']), 1), round(math.degrees(rec[i_axle]['phi2']), 1)]},
           'peak_front_link_n': round(pk('front_axial'), 1), 'front_link_compression_n': round(max(r['front_axial'] for r in rec), 1),
           'front_link_tension_n': round(-min(r['front_axial'] for r in rec), 1),
           'peak_knee_pin_n': round(max(pk('knee_front'), pk('knee_rear')), 1),
           'peak_stop_nm': round(max([0.0] + [max(abs(r['stop_f']), abs(r['stop_r'])) for r in stops]), 1),
           'stop_hits': len(stops) > 0,
           'L_range_mm': [round(min(r['L_mm'] for r in rec), 1), round(max(r['L_mm'] for r in rec), 1)],
           'rig': info}
    out['series'] = {k: [round(r[k], 3) for r in rec[::5]] for k in ('t', 'L_mm', 'rail_mm', 'tau_f', 'tau_r', 'Fz', 'Az', 'front_axial', 'stop_f', 'stop_r')}
    return out


class VideoWriter:
    def __init__(self, model, path: Path, width=960, height=540):
        self.r = mujoco.Renderer(model, height, width)
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.lookat[:] = (0.0, 0.0, 0.33)
        self.cam.distance, self.cam.elevation, self.cam.azimuth = 1.25, -8, 70
        self.opt = mujoco.MjvOption()
        self.proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                                      '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '26', str(path)],
                                     stdin=subprocess.PIPE)

    def frame(self, d):
        self.r.update_scene(d, self.cam, self.opt)
        self.proc.stdin.write(self.r.render().tobytes())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()
        self.r.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--video', action='store_true')
    ap.add_argument('--half-mass', type=float, default=HALF_MASS, help='what one leg carries, kg (half the robot)')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    meshes = export_meshes(OUT / 'rig_meshes') if a.video else None
    results = {}
    f = OUT / 'rig-results.json'
    if f.exists() and a.only:
        results = json.loads(f.read_text()).get('scenarios', {})
    for name, sc in SCENARIOS.items():
        if a.only and name not in a.only:
            continue
        r = run(sc, a.half_mass, OUT / f'rig_{name}.mp4' if a.video else None, meshes)
        results[name] = r
        print(f"{name:10} gearbox {r['peak_gearbox_nm']:6.1f} N m ({r['gearbox_over_peak_ms']:.1f} ms > {LEG_PEAK} N m)  motor {r['peak_motor_nm']:6.1f} N m  wheel {r['peak_wheel_force_n']:7.1f} N  axle {r['peak_axle_force_n']:7.1f} N  front link {r['peak_front_link_n']:7.1f} N  "
              f"knee pin {r['peak_knee_pin_n']:7.1f} N (dynamic {max(r['peak_joint_force_n']['knee_f'], r['peak_joint_force_n']['knee_r']):.0f})  stop {r['peak_stop_nm']:6.1f} N m  L {r['L_range_mm']}"
              + (f"  jump {r['jump_height_mm']} mm" if r.get('jump_height_mm') is not None else ''))
    f.write_text(json.dumps({'half_mass_kg': a.half_mass, 'model': {'leg_peak_nm': LEG_PEAK, 'leg_cap_nm': LEG_CAP, 'leg_omega_rad_s': round(LEG_OMEGA, 2),
                                                                     'armature_kg_m2': round(ARMATURE, 5), 'stop_k_nm_per_rad': round(STOP_K)},
                             'scenarios': results}, indent=1) + '\n')


if __name__ == '__main__':
    main()
