"""The foam-dart turret in the physics simulation: aiming, firing real dart bodies, recoil and hits.

- **Servos:** pan and tilt are joint PDs on the turret's motors, clipped to their torque.
- **Aiming:** from the muzzle site to the target, with a drop allowance for the dart's flight (no drag in the aim,
  so long shots fall short a little, as they would). Kid-safety rule from research/turret-and-safety.md: the barrel
  never points above horizontal *in the world frame*, so the body's lean is taken out of the tilt command; a target
  that would need an upward shot is not engaged.
- **Firing:** only when settled on target (aim error and turret speed small), at up to 5 shots per second. Each shot
  takes a parked dart body (1 g, 24 m/s, air drag from MuJoCo's fluid model), places it at the muzzle along the barrel,
  and applies the reaction impulse to the launcher.
- **Hits:** dart-to-target contacts, each dart counted once. A target is done when its plate is knocked over.
- **Laser:** off at the start and while slewing between targets; on once the turret is close to on target, and it stays
  on for a moment before the first shot (a visible "about to fire" warning). Off again when the target goes down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import mujoco
import numpy as np

G = 9.81
DART_MASS = 0.001
DART_SPEED = 24.0            # m/s, 80 fps: the kid-safety cap
DART_HALF = 0.0225           # capsule half-length (a 45 mm short dart)
DART_R = 0.0065


@dataclass
class Target:
    name: str
    pos: tuple                # centre of the face, world frame (m)
    shots: int = 8
    window: tuple = (0.0, 1e9)  # engage between these times (s)


def targets_xml(targets: List[Target]) -> str:
    """Knock-down targets: a light foam plate (20 g) hinged along its bottom edge, its weight 4 mm forward of the hinge so
    it rests 4° towards the shooter against a stop, on a post. A dart hit knocks it over backwards (negative hinge angle), as on a real foam-dart range."""
    out = []
    for t in targets:
        x, y, z = t.pos
        yaw = math.atan2(-y, -x)                                   # face back towards the origin
        q = (math.cos(yaw / 2), 0, 0, math.sin(yaw / 2))
        hinge_z = z - 0.12
        out.append(f'<body name="{t.name}_stand" pos="{x} {y} 0" quat="{q[0]} {q[1]} {q[2]} {q[3]}">'
                   f'<geom name="{t.name}_post" type="box" size="0.015 0.015 {hinge_z / 2}" pos="-0.03 0 {hinge_z / 2}" rgba="0.08 0.08 0.09 1"/>'
                   f'<geom name="{t.name}_foot" type="box" size="0.08 0.08 0.006" pos="-0.03 0 0.006" rgba="0.95 0.8 0.05 1"/>'
                   f'<body name="{t.name}_plate" pos="0 0 {hinge_z}">'
                   f'<joint name="{t.name}_hinge" type="hinge" axis="0 1 0" range="-1.65 0.07" damping="0.0004"/>'
                   f'<geom name="{t.name}" type="box" size="0.006 0.12 0.12" pos="0.004 0 0.12" mass="0.02" rgba="1 0.3 0 1" solref="0.01 1"/>'
                   f'<geom name="{t.name}_ring" type="cylinder" size="0.085 0.0015" pos="0.0105 0 0.12" quat="0.7071 0 0.7071 0" rgba="0.03 0.03 0.04 1" contype="0" conaffinity="0" mass="0"/>'
                   f'<geom name="{t.name}_bull" type="cylinder" size="0.035 0.002" pos="0.0112 0 0.12" quat="0.7071 0 0.7071 0" rgba="1 0.98 0.9 1" contype="0" conaffinity="0" mass="0"/>'
                   f'</body></body>')
    return ''.join(out)


def darts_xml(n: int) -> str:
    """n parked darts, resting off to the side until fired. Each is a light foam body with a heavier rubber tip ahead
    of it (0.45 g + 0.55 g), so the centre of mass is forward and drag on the body keeps it flying nose-first."""
    return ''.join(f'<body name="dart_{i}" pos="{-2 - 0.05 * (i % 12)} {3 + 0.05 * (i // 12)} {DART_R + 0.0005}" quat="0.7071 0 0.7071 0">'
                   f'<freejoint name="dart_{i}"/>'
                   f'<geom name="dart_{i}" type="capsule" size="{DART_R} {DART_HALF * 0.8}" pos="0 0 -0.004" mass="0.00045" '
                   f'fluidshape="ellipsoid" fluidcoef="0.5 0.25 1.5 0 0" rgba="1 0.48 0.1 1" friction="0.9 0.01 0.001" solref="0.012 1"/>'
                   f'<geom name="dart_{i}_tip" type="sphere" size="{DART_R}" pos="0 0 {DART_HALF}" mass="0.00055" rgba="0.17 0.42 1 1" '
                   f'friction="0.9 0.01 0.001" solref="0.012 1"/></body>' for i in range(n))


def fluid_option(xml: str) -> str:
    """Air for the darts (MuJoCo's ellipsoid fluid model)."""
    return xml.replace('<option ', '<option density="1.2" viscosity="0.000018" ', 1)


# drag-only flight (no lift): deceleration = K v^2, K = 0.5 rho C A / m with MuJoCo's blunt-drag coefficient
K_DRAG = 0.5 * 1.2 * 0.5 * math.pi * DART_R ** 2 / DART_MASS


def fly(elev: float, horiz: float, v0: float = DART_SPEED, dt: float = 0.002):
    """Height change when the dart has travelled `horiz` metres horizontally, launched at `elev` (rad, + up)."""
    x = z = 0.0
    vx, vz = v0 * math.cos(elev), v0 * math.sin(elev)
    for _ in range(2000):
        v = math.hypot(vx, vz)
        vx -= K_DRAG * v * vx * dt
        vz -= (G + K_DRAG * v * vz) * dt
        x += vx * dt
        z += vz * dt
        if x >= horiz:
            return z
        if vx < 0.5:
            break
    return -1e9          # never gets there


def elevation_for(horiz: float, dz: float) -> Optional[float]:
    """Launch elevation (rad) that lands the dart dz metres above the muzzle at horiz metres, by bisection."""
    lo, hi = -0.6, 0.6
    if fly(hi, horiz) < dz:
        return None
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fly(mid, horiz) < dz else (lo, mid)
    return (lo + hi) / 2


def quat_from_z(d: np.ndarray) -> np.ndarray:
    """Quaternion (w x y z) turning +z onto the unit vector d."""
    z = np.array([0.0, 0.0, 1.0])
    c = float(np.dot(z, d))
    if c < -0.999999:
        return np.array([0.0, 1.0, 0.0, 0.0])
    axis = np.cross(z, d)
    q = np.array([1.0 + c, *axis])
    return q / np.linalg.norm(q)


@dataclass
class TurretController:
    model: mujoco.MjModel
    data: mujoco.MjData
    targets: List[Target] = field(default_factory=list)
    kp_pan: float = 18.0
    kd_pan: float = 0.6
    kp_tilt: float = 14.0
    kd_tilt: float = 0.4
    rate_hz: float = 5.0
    tol_rad: float = 0.012

    def __post_init__(self):
        m = self.model
        self.has = all(n in [m.joint(i).name for i in range(m.njnt)] for n in ('turret_pan', 'turret_tilt'))
        if not self.has:
            return
        j = lambda n: m.joint(n)
        self.pan_q, self.pan_v = j('turret_pan').qposadr[0], j('turret_pan').dofadr[0]
        self.tilt_q, self.tilt_v = j('turret_tilt').qposadr[0], j('turret_tilt').dofadr[0]
        self.pan_a, self.tilt_a = m.actuator('turret_pan').id, m.actuator('turret_tilt').id
        self.pan_lim, self.tilt_lim = m.actuator_ctrlrange[self.pan_a][1], m.actuator_ctrlrange[self.tilt_a][1]
        self.muzzle = m.site('muzzle').id
        self.tilt_body = m.body('turret_tilt').id
        self.base = m.body('base').id
        names = [m.body(i).name for i in range(m.nbody)]
        self.darts = [i for i, n in enumerate(names) if n.startswith('dart_')]
        self.dart_geoms = {m.body(b).geomadr[0] + k: b for b in self.darts for k in range(m.body(b).geomnum[0])}
        self.dart_qadr = {b: m.jnt_qposadr[m.body(b).jntadr[0]] for b in self.darts}
        self.dart_vadr = {b: m.jnt_dofadr[m.body(b).jntadr[0]] for b in self.darts}
        self.target_geoms = {m.geom(t.name).id: t.name for t in self.targets if t.name in [m.geom(g).name for g in range(m.ngeom)]}
        jn = [m.joint(j).name for j in range(m.njnt)]
        self.hinge_q = {t.name: m.jnt_qposadr[m.joint(f'{t.name}_hinge').id] for t in self.targets if f'{t.name}_hinge' in jn}
        self.down = {}
        self.next_dart = 0
        self.last_shot = -1e9
        self.fired = {t.name: 0 for t in self.targets}
        self.events, self.hits, self.hit_darts = [], [], set()
        self.recoil_steps = 0
        self.recoil_force = np.zeros(3)
        self.pan_cmd, self.tilt_cmd = 0.0, 0.05
        self.aim_err = 0.0
        self.in_range = True
        self.unreachable = set()        # targets that were out of range at some point (reported, not skipped)
        # walking shots in: per target elevation and bearing corrections learned from where earlier darts went
        self.correction = {t.name: [0.0, 0.0] for t in self.targets}
        self.in_flight = []          # (dart body, target, muzzle position at the shot)
        self.laser = False
        self.laser_since = 0.0
        self.engaged = None          # the target being aimed at
    laser_near_rad: float = 0.08     # aim error below which the laser comes on
    laser_warn_s: float = 0.35       # laser on at least this long before the first shot at a target

    def set_laser(self, t: float, on: bool, target: Optional[str] = None):
        if on != self.laser:
            self.laser = on
            self.laser_since = t
            self.events.append({'t': round(t, 3), 'type': 'laser_on' if on else 'laser_off', **({'target': target} if target else {})})

    # --- aiming
    def aim(self, target: Target):
        d, m = self.data, self.model
        mz = d.site_xpos[self.muzzle]
        to = np.array(target.pos) - mz
        R = d.xmat[self.base].reshape(3, 3)
        yaw = math.atan2(R[1, 0], R[0, 0])
        pitch = -math.asin(max(-1.0, min(1.0, R[2, 0])))           # body nose-down positive
        horiz = math.hypot(to[0], to[1])
        elev = elevation_for(horiz, to[2])                          # needed barrel elevation, world frame (+ = up), with drag
        pan = (math.atan2(to[1], to[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
        if elev is None:
            elev = 0.0
        elev += self.correction[target.name][0]
        pan += self.correction[target.name][1]
        self.in_range = elev <= 0.0
        if not self.in_range:
            self.unreachable.add(target.name)                       # would need an upward shot: track it, but hold fire
            elev = 0.0
        # tilt joint: + = barrel down relative to the body; world elevation = -(tilt + body pitch)
        return pan, -elev - pitch

    pause_after_down_s: float = 0.6  # a beat between targets (laser off) after one goes down

    def current_target(self, t: float) -> Optional[Target]:
        if self.down and t - max(self.down.values()) < self.pause_after_down_s:
            return None
        for tg in self.targets:
            if tg.window[0] <= t <= tg.window[1] and self.fired[tg.name] < tg.shots and tg.name not in self.down:
                return tg
        return None

    def step(self, t: float, dt: float):
        if not self.has:
            return
        d = self.data
        tg = self.current_target(t)
        if tg is not None:
            self.pan_cmd, self.tilt_cmd = self.aim(tg)
        else:
            self.pan_cmd, self.tilt_cmd = 0.0, 0.05
        pe = self.pan_cmd - d.qpos[self.pan_q]
        te = self.tilt_cmd - d.qpos[self.tilt_q]
        # PD plus the model's gravity and coriolis terms, so the launcher does not sag off target
        d.ctrl[self.pan_a] = float(np.clip(self.kp_pan * pe - self.kd_pan * d.qvel[self.pan_v] + d.qfrc_bias[self.pan_v], -self.pan_lim, self.pan_lim))
        d.ctrl[self.tilt_a] = float(np.clip(self.kp_tilt * te - self.kd_tilt * d.qvel[self.tilt_v] + d.qfrc_bias[self.tilt_v], -self.tilt_lim, self.tilt_lim))
        self.aim_err = math.hypot(pe, te)
        name = tg.name if tg is not None else None
        if name != self.engaged:                                  # new target (or none): laser off while slewing
            self.set_laser(t, False)
            self.engaged = name
        if tg is not None and not self.laser and self.aim_err < self.laser_near_rad and self.in_range:
            self.set_laser(t, True, tg.name)
        settled = self.aim_err < self.tol_rad and abs(d.qvel[self.pan_v]) < 0.1 and abs(d.qvel[self.tilt_v]) < 0.1
        warned = self.laser and t - self.laser_since >= self.laser_warn_s
        if tg is not None and settled and warned and self.in_range and t - self.last_shot >= 1.0 / self.rate_hz and self.next_dart < len(self.darts):
            self.fire(t, tg)
        # recoil: the reaction impulse on the launcher, spread over a 2 ms shot
        d.xfrc_applied[self.tilt_body] = 0
        if self.recoil_steps > 0:
            d.xfrc_applied[self.tilt_body, :3] = self.recoil_force
            arm = d.site_xpos[self.muzzle] - d.xipos[self.tilt_body]
            d.xfrc_applied[self.tilt_body, 3:] = np.cross(arm, self.recoil_force)
            self.recoil_steps -= 1
        self.check_hits(t)
        self.observe()
        for name, qa in self.hinge_q.items():                     # knocked down: the plate has flipped back
            if name not in self.down and d.qpos[qa] < -0.8:
                self.down[name] = round(t, 3)
                self.events.append({'t': round(t, 3), 'type': 'down', 'target': name})

    def observe(self):
        """When a dart reaches its target's distance (or lands), note how far above/below and left/right it passed, and
        correct the aim for the next shot, as a spotter or the turret camera would."""
        d = self.data
        still = []
        for b, tg, origin in self.in_flight:
            qa = self.dart_qadr[b]
            p = d.qpos[qa:qa + 3]
            to_t = np.array(tg.pos) - origin
            dist = math.hypot(to_t[0], to_t[1])
            u = np.array([to_t[0], to_t[1], 0.0]) / max(dist, 1e-6)
            along = float(np.dot((p - origin)[:2], u[:2]))
            landed = p[2] < 0.02 and np.linalg.norm(d.qvel[self.dart_vadr[b]:self.dart_vadr[b] + 3]) < 3.0
            if along >= dist or landed or b in self.hit_darts:
                if b not in self.hit_darts:
                    if along >= dist:     # passed the target's distance: the vertical miss there is the error
                        de = -math.atan2(p[2] - tg.pos[2], dist)
                    else:                 # landed short: aim a little higher, more for a bigger shortfall (capped)
                        de = min(0.03, 0.25 * (dist - along) / dist)
                    side = float(np.cross(u, (p - origin))[2]) / max(along, 0.5)        # + = passed to the left
                    c = self.correction[tg.name]
                    c[0] = max(-0.1, min(0.1, c[0] + 0.8 * de))
                    c[1] = max(-0.1, min(0.1, c[1] - 0.8 * side))
            else:
                still.append((b, tg, origin))
        self.in_flight = still

    def fire(self, t: float, tg: Target):
        d, m = self.data, self.model
        b = self.darts[self.next_dart]
        self.next_dart += 1
        R = d.site_xmat[self.muzzle].reshape(3, 3)
        direction = R[:, 0] / np.linalg.norm(R[:, 0])              # the barrel is the tilt link's +x
        qa, va = self.dart_qadr[b], self.dart_vadr[b]
        d.qpos[qa:qa + 3] = d.site_xpos[self.muzzle] + direction * (DART_HALF + DART_R + 0.004)
        d.qpos[qa + 3:qa + 7] = quat_from_z(direction)
        base_v = np.zeros(6)
        mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_SITE, self.muzzle, base_v, 0)
        d.qvel[va:va + 3] = direction * DART_SPEED + base_v[3:]
        d.qvel[va + 3:va + 6] = 0
        steps = max(1, int(round(0.002 / m.opt.timestep)))
        self.recoil_force = -direction * DART_MASS * DART_SPEED / (steps * m.opt.timestep)
        self.recoil_steps = steps
        self.last_shot = t
        self.fired[tg.name] += 1
        self.in_flight.append((b, tg, d.site_xpos[self.muzzle].copy()))
        self.events.append({'t': round(t, 3), 'type': 'shot', 'target': tg.name, 'dart': m.body(b).name})

    def check_hits(self, t: float):
        d = self.data
        for i in range(d.ncon):
            c = d.contact[i]
            for dg, tgm in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                if dg in self.dart_geoms and tgm in self.target_geoms:
                    b = self.dart_geoms[dg]
                    if b not in self.hit_darts:
                        self.hit_darts.add(b)
                        name = self.target_geoms[tgm]
                        self.hits.append(name)
                        self.events.append({'t': round(t, 3), 'type': 'hit', 'target': name, 'dart': self.model.body(b).name})

    def summary(self):
        shots = sum(1 for e in self.events if e['type'] == 'shot')
        return {'shots': shots, 'hits': len(self.hits), 'hit_rate': round(len(self.hits) / shots, 3) if shots else 0.0,
                'by_target': {t.name: {'shots': self.fired[t.name], 'hits': self.hits.count(t.name), 'knocked_down_s': self.down.get(t.name)} for t in self.targets},
                'knocked_down': len(self.down), 'targets': len(self.targets),
                'out_of_range_at_times': sorted(self.unreachable)}
