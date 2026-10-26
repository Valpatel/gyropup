"""Gyropup as an mjlab entity, built from any design file.

        design JSON --(sim.model, main venv)--> rl/build/<design>/robot.xml + model.json --> mjlab EntityCfg

- The MJCF is the one sim/model.py writes for the CPU scenarios, so RL trains on the same masses, inertias and joint
    limits. The floor, light and the XML `motor` actuators are removed (mjlab adds its own terrain and actuators).
- The turret pan/tilt joints are removed, which welds the head to the body at pan 0, tilt 0 (mass kept).
- Hips and knees: mjlab `DcMotorActuator` (PD to a position target, then the linear torque-speed clip:
    full peak torque at standstill, zero at the no-load speed at the battery voltage). Wheels: the same actuator with
    kp = 0, i.e. a velocity loop (kd) inside the same torque-speed line. Peak torque, no-load speed and armature
    come from model.json, so every design gets its own motors.
- The initial state is sim.controller.place_standing at the baseline's 0.6 height: legs at the LQR controller's
    pose, whole robot tilted about the axle until the centre of mass is over it.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import mujoco

from mjlab.actuator import DcMotorActuatorCfg
from mjlab.entity import EntityArticulationInfoCfg, EntityCfg

RL_DIR = Path(__file__).resolve().parents[1]
REPO = RL_DIR.parent
MAIN_PY = REPO / '.venv' / 'bin' / 'python'

LEG_JOINTS = ('hip_l', 'knee_l', 'hip_r', 'knee_r')
WHEEL_JOINTS = ('wheel_l', 'wheel_r')
TURRET_JOINTS = ('turret_pan', 'turret_tilt')
STAND_FRAC = 0.6               # same default height as the LQR baseline (0 = deepest crouch, 1 = full stand)

# Physics / control rates shared by the env and the CPU playback.
PHYSICS_DT = 0.004             # s
DECIMATION = 5                 # policy at 50 Hz
MAX_DELAY_S = 0.020            # command latency randomised in [0, 20 ms]

# PD gains, scaled by each design's peak torque (same convention as sim/controller.py Gains).
LEG_KP_PER_NM = 2.5            # kp = 2.5 x peak (N m / rad): 150 N m/rad for the 60 N m default actuator
LEG_KD_PER_NM = 0.06           # kd = 0.06 x peak (N m s / rad)
WHEEL_KD = 1.0                 # N m per rad/s of wheel-speed error


def design_path() -> Path:
    """Design selected with GYROPUP_DESIGN (absolute, or relative to the repo root). Default: designs/default.json.

    GYROPUP_MODEL_DIR, if set, points at an already generated robot.xml + model.json and skips the build: use it to
    replay or export a policy on exactly the model it was trained on after the design has moved on.
    """
    p = Path(os.environ.get('GYROPUP_DESIGN', 'designs/default.json'))
    return p if p.is_absolute() else (REPO / p)


def build_model(design: Path | None = None, force: bool = False) -> Path:
    """Run sim.model in the main venv (CadQuery, node) into rl/build/<design>/ unless it is already up to date."""
    design = Path(design or design_path()).resolve()
    out = RL_DIR / 'build' / design.stem
    xml = out / 'robot.xml'
    sources = [design, REPO / 'sim' / 'model.py', REPO / 'tools' / 'derive.mjs']   # the design and the generator
    newest = max(f.stat().st_mtime for f in sources if f.exists())
    stale = not xml.exists() or not (out / 'model.json').exists() or xml.stat().st_mtime < newest
    if force or stale:
        if not MAIN_PY.exists():
            raise FileNotFoundError(f'{MAIN_PY} not found: the main venv builds the model (sim/model.py)')
        code = 'import sys; from pathlib import Path; from sim.model import build; build(Path(sys.argv[1]), Path(sys.argv[2]))'
        subprocess.run([str(MAIN_PY), '-c', code, str(design), str(out)], cwd=REPO, check=True)
    return out


@dataclass(frozen=True)
class GyropupSpec:
    design: str
    xml: str
    info: dict
    base_pos: tuple
    base_quat: tuple
    joint_pos: dict
    base_height: float           # hip-axis height when standing (m)
    wheel_radius: float
    track_half: float            # half the distance between the wheel centres (m)
    total_mass: float

    @property
    def leg(self) -> dict:
        return self.info['leg_actuator']

    @property
    def wheel(self) -> dict:
        return self.info['wheel_motor']


@lru_cache(maxsize=None)
def load(design: str | None = None) -> GyropupSpec:
    d = Path(design) if design else design_path()
    d = d if d.is_absolute() else REPO / d
    frozen = os.environ.get('GYROPUP_MODEL_DIR')     # a saved robot.xml + model.json (e.g. results/trained_model)
    out = Path(frozen).resolve() if frozen else build_model(d)
    xml = out / 'robot.xml'
    info = json.loads((out / 'model.json').read_text())
    # The standing pose from the baseline controller (sim/controller.py), computed on the full CPU model.
    sys.path.insert(0, str(REPO))
    try:
        from sim.controller import Robot, place_standing
    finally:
        sys.path.pop(0)
    m = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(m)
    rb = Robot(m, info)
    place_standing(rb, data, STAND_FRAC)
    q = data.qpos
    joint_pos = {n: float(q[rb.qadr[n]]) for n in LEG_JOINTS + WHEEL_JOINTS}
    L = info['layout_mm']
    return GyropupSpec(design=str(d), xml=str(xml), info=info,
                                          base_pos=tuple(float(v) for v in q[0:3]), base_quat=tuple(float(v) for v in q[3:7]),
                                          joint_pos=joint_pos, base_height=float(q[2]), wheel_radius=L['wheelR'] / 1000,
                                          track_half=L['wheelX'] / 1000, total_mass=rb.total_mass)


def robot_spec(xml: str) -> mujoco.MjSpec:
    """The generated MJCF without floor, light, XML actuators and turret joints."""
    spec = mujoco.MjSpec.from_file(xml)
    for a in list(spec.actuators):
        spec.delete(a)
    for g in list(spec.worldbody.geoms):          # the floor plane
        spec.delete(g)
    for lt in list(spec.worldbody.lights):
        spec.delete(lt)
    for j in list(spec.joints):
        if j.name in TURRET_JOINTS:
            spec.delete(j)
    return spec


def leg_gains(g: GyropupSpec) -> tuple[float, float]:
    return LEG_KP_PER_NM * g.leg['peak_nm'], LEG_KD_PER_NM * g.leg['peak_nm']


def robot_cfg(g: GyropupSpec) -> EntityCfg:
    kp, kd = leg_gains(g)
    lag = int(round(MAX_DELAY_S / PHYSICS_DT))
    legs = DcMotorActuatorCfg(
        target_names_expr=LEG_JOINTS,
        stiffness=kp, damping=kd,
        saturation_effort=g.leg['peak_nm'], effort_limit=g.leg['peak_nm'],     # peak is allowed; heat is a reward cost
        velocity_limit=g.leg['omega_max'],
        armature=g.leg['armature'] or None,
        delay_min_lag=0, delay_max_lag=lag, delay_update_period=DECIMATION,
    )
    wheels = DcMotorActuatorCfg(
        target_names_expr=WHEEL_JOINTS,
        stiffness=0.0, damping=WHEEL_KD,
        saturation_effort=g.wheel['peak_nm'], effort_limit=g.wheel['peak_nm'],
        velocity_limit=g.wheel['omega_max'],
        armature=g.wheel['armature'] or None,
        delay_min_lag=0, delay_max_lag=lag, delay_update_period=DECIMATION,
    )
    return EntityCfg(
        spec_fn=lambda: robot_spec(g.xml),
        init_state=EntityCfg.InitialStateCfg(pos=g.base_pos, rot=g.base_quat, joint_pos=dict(g.joint_pos),
                                                                                  joint_vel={'.*': 0.0}),
        articulation=EntityArticulationInfoCfg(actuators=(legs, wheels), soft_joint_pos_limit_factor=0.95),
    )


if __name__ == '__main__':
    g = load()
    print(json.dumps({k: v for k, v in g.__dict__.items() if k != 'info'}, indent=1))
    print('leg kp, kd:', leg_gains(g))
    s = robot_spec(g.xml)
    print('joints:', [j.name for j in s.joints], 'mass', g.total_mass, math.degrees(2 * math.asin(g.base_quat[2])))
