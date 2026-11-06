"""The launch in 3D: a foam ball between two tyres, each on its own motor, with slip, spin and lateral forces.

    .venv/bin/python sim/turret_launch3d.py [--quick]      # writes exports/turret/launch/launch3d.json and plots

This extends sim/turret_launch.py (the program agent's 1D model, which it imports for the motor, the Hertz foam law and
the ball/launcher definitions) to six degrees of freedom. It is a REDUCED MODEL solved outside MuJoCo (1 us explicit
steps, vectorised over a population of balls); MuJoCo's soft contacts cannot hold a 25 % foam crush at 18 m/s surface
speed without tuning that would hide the physics. What it adds over the 1D model:

  - two independent wheels (+y and -y), each with its own motor (sim/turret_launch.py MOTOR) + ESC loop, so mismatched set speeds, a lagging
    wheel in a burst, or one wheel at 100 % throttle give the ball spin about z (yaw spin -> a sideways Magnus curve);
  - the ball's position in y and z at the nip (from the feed stage: the bore's 0.75 mm play, the chute floor), the
    tyre's edges (12 mm wide), and tyre runout (a printed TPU tyre is not round: est 0.15 mm, swept), which modulates
    the two normal forces at the wheels' spin frequency and leaves the ball a lateral velocity: the launch's own
    contribution to dispersion;
  - the ball's spin from the chute (it arrives rolling), and the friction torque that spins it up or down;
  - the reaction forces on the cage (recoil: the sum of the tyre forces on the ball, reversed) and the torque pulse the
    two motors see.

Contact law per tyre (foam sphere on a rigid cylinder): overlap delta = R + r - |ball centre - wheel axis| (flat tyre, so
the normal is radial in the xy plane); F_n = K delta^1.5 (1 + alpha d(delta)/dt) with K = 4/3 E* sqrt(R_eff) and the
Hunt-Crossley alpha for the ball's restitution (both from sim/turret_launch.py); Coulomb friction mu F_n on the slip
between the tyre surface and the ball's surface (translation + spin), regularised over 0.05 m/s. The tyre is treated as
rigid (TPU 95A at ~25 MPa is 10-30x stiffer than the foam). Beyond the tyre's edge (|z| > 6 mm) the contact is lost.

Hand-over check: with both wheels at the same speed, the ball centred and no runout, this model must match the 1D model
within 1 %; `check_against_1d()` does that and the e2e pipeline asserts it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
sys.path.insert(0, str(R / 'cad'))
import turret_launch as tl  # noqa: E402  (the program agent's 1D model: MOTOR, Ball, Launcher, shot, no_load_speed, ...)

OUT = R / 'exports' / 'turret' / 'launch'
FPS = tl.FPS
CAP = tl.CAP
CAP_FPS = tl.CAP_FPS
MOTOR = tl.MOTOR
V_REG = 0.05                    # m/s: the slip speed over which Coulomb friction is regularised (as in the 1D model)
DT = 1e-6
T_MAX = 0.03                    # s: a ball still in the nip after this is counted as stuck (rejected)


@dataclass
class Entry:
    """The ball's state when it first touches the tyres (the feed stage's exit), in the cartridge frame: the ball path is
    the x axis, y left, z up; the origin on the wheel axes' midpoint. Arrays or scalars (a population)."""
    y: float = 0.0              # m: lateral offset of the ball centre from the path (bore play: +-0.75 mm)
    z: float = -0.00075         # m: the ball rests on the channel floor, 0.75 mm under the tyre mid-plane
    vx: float = 0.5             # m/s: arriving from the chute (rolling)
    vy: float = 0.0
    vz: float = 0.0
    wx: float = 0.0             # rad/s: spin (a ball rolling forward on the floor spins about +y at vx / r)
    wy: float | None = None     # None -> rolling: vx / r
    wz: float = 0.0


@dataclass
class Wheels:
    """What each wheel is doing when the ball arrives. Speeds are magnitudes (rad/s); the +y wheel spins +z, the -y wheel
    -z, so both inner surfaces move +x. runout: the tyre's radial runout (peak, m) with a random phase per shot."""
    w_set: tuple = (900.0, 900.0)       # the ESC set speeds (rad/s), or the no-load speeds when full_throttle
    w0: tuple | None = None             # the speeds at the ball's arrival (None: at the set speeds)
    full_throttle: bool = False
    kv_scale: tuple = (1.0, 1.0)        # motor KV tolerance per wheel
    v_scale: float = 1.0                # supply tolerance
    runout: float = 0.0                 # m
    runout_phase: tuple = (0.0, 0.0)    # rad
    tyre_E_mpa: float | None = None     # the TPU tyre's modulus: it grows at speed (tyre_growth; None: rigid)
    tyre_bonded: bool | None = None     # None: TYRE_BONDED; False: the free ring (a tyre come loose)
    ramp_s: float = 0.0                 # the set speed ramps 0 -> w_set over this (the plan's 200 ms soft start); 0: constant
    t_offset: float = 0.0               # where in the ramp the ball arrives (s)
    brake: bool = False                 # the phases are shorted (the release brake): i = -ke w / R, no drive


# the phase-short brake as built (docs/turret-wiring.md 3.3): three IRLZ44N per motor from each phase to GND, gates at
# ~4.5 V; the short's loop adds two FETs and the 22 AWG taps to the motor's own 55 mOhm (the 1400 KV, D68), and the
# winding's inductance limits the current at speed (the X2216's is not published: 35 uH between leads est for the 880 KV,
# so 35 x (880/1400)^2 = 14 uH for the 1400 KV, the turns being in proportion to 1/KV; swept 0-50 uH in release_window)
BRAKE = {'r_fet_ohm': 0.025,        # IRLZ44N R_DS(on) max at V_GS 5 V (Infineon datasheet; 0.035 at 4 V)
         'r_taps_ohm': 0.006,       # 2 x 60 mm of 22 AWG (53 mOhm/m)
         'l_ll_h': 35e-6 * (880.0 / MOTOR['kv_rpm_v']) ** 2,   # between two leads, est
         'pole_pairs': 7}


def brake_current(ke, w, L, l_ll_h=None):
    """The in-phase braking current with the phases shorted through the FETs: E R / (R^2 + (w_e L)^2), where E = ke w."""
    r = L.r_eff_ohm + 2 * BRAKE['r_fet_ohm'] + BRAKE['r_taps_ohm']
    lh = BRAKE['l_ll_h'] if l_ll_h is None else l_ll_h
    xl = BRAKE['pole_pairs'] * w * lh
    return ke * w * r / (r * r + xl * xl)


TPU = {'rho': 1220.0, 'E_mpa': (10.0, 30.0), 'E_nominal': 20.0,
       'source': 'TPU 95A: 1.22 g/cm^3; printed modulus 9.8 MPa (Bambu TPU 95A HF TDS) to 26 (NinjaTek Cheetah) and 33.6 (Polymaker PolyFlex) '
                 'at low strain, 67 (Ultimaker, D3039); the growth of a spinning elastomer tyre is real (Hasbro US11719504B1: ~4 mm in diameter); '
                 'sim/turret_ball.py SOURCES, checked 2026-10-27'}


TYRE_BONDED = True              # D68: the tyre is bonded to the hub's rim (cad/turret.py TYRE_SET note); False: a free ring


def tyre_growth(w, Rw, E_mpa, bonded=None, t=None, nu=0.45):
    """Radial growth (m) of the spinning TPU tyre's outer surface at w rad/s. Bonded (TYRE_BONDED): a plane-stress
    rotating annulus, inner radius Rw - t held by the rigid hub (u = 0), outer face free: u(r) = C1 r + C2 / r - k r^3,
    k = (1 - nu^2) rho w^2 / (8 E). Not bonded: a free thin ring, rho w^2 R^3 / E (what the stretch fit becomes once the
    tyre's own bore grows past its 4 % interference, ~2.5 % at 10,500 rpm and ~12 % at 16,000 on a 10 MPa TPU)."""
    bonded = TYRE_BONDED if bonded is None else bonded
    E = E_mpa * 1e6
    if not bonded:
        return TPU['rho'] * w ** 2 * Rw ** 3 / E
    a, b = Rw - (t if t is not None else tl.TYRE_T / 1000), Rw
    k = (1 - nu ** 2) * TPU['rho'] * w ** 2 / (8 * E)
    # u(a) = 0: C1 a + C2 / a = k a^3;  sigma_r(b) = 0: C1 (1 + nu) - C2 (1 - nu) / b^2 = (3 + nu) k b^2
    det = a * (-(1 - nu) / b ** 2) - (1 / a) * (1 + nu)
    C1 = (k * a ** 3 * (-(1 - nu) / b ** 2) - (1 / a) * (3 + nu) * k * b ** 2) / det
    C2 = (a * (3 + nu) * k * b ** 2 - (1 + nu) * k * a ** 3) / det
    return C1 * b + C2 / b - k * b ** 3


def _arr(v, n):
    return np.full(n, float(v)) if np.isscalar(v) or v is None else np.asarray(v, dtype=float)


MU_BORE = 0.5                   # foam on the PA6-CF channel floor at the nip (est; sim/turret_ball.py RANGES mu_plastic)
BORE_R_M = None                 # the channel radius from the CAD (set_bore); launch3d's default when given 'default'


def set_bore(G):
    """Take the ball channel's radius from the CAD's Geo (bore = ball + 1.5 mm)."""
    global BORE_R_M
    BORE_R_M = G.br / 1000
    return BORE_R_M


def launch3d(balls, L: tl.Launcher, entry: Entry = Entry(), wheels: Wheels = Wheels(), dt=DT, record=False, bore_r='default'):
    """Fire a population of balls (a list of tl.Ball, or one) through the launcher L. Every Entry/Wheels field may be an
    array over the population. bore_r: the ball channel's radius (m) through the nip (cad/turret.py Geo.br): its floor
    and ceiling confine the ball (the same Hertz + Coulomb law as sim/turret_flight.py's barrel); None: no channel (the
    1D model's assumption, for the hand-over check). Returns a dict of arrays (per ball) plus scalars; v/omega are
    3-vectors (n, 3)."""
    if isinstance(bore_r, str):
        bore_r = BORE_R_M
    single = not isinstance(balls, (list, tuple))
    balls = [balls] if single else list(balls)
    n = len(balls)
    m = np.array([b.m_g for b in balls]) / 1000
    r = np.array([b.d_mm for b in balls]) / 2000
    Es = np.array([b.E_mpa for b in balls]) * 1e6 / (1 - np.array([b.nu for b in balls]) ** 2)
    e = np.array([b.e for b in balls])
    mu = np.array([b.mu for b in balls])
    Rw = L.wheel_d_mm / 2000
    c = (L.wheel_d_mm + L.gap_mm) / 1000
    R1 = 1 / (1 / r + 1 / Rw)
    R2 = 1 / (1 / r + 1 / (L.crown_r_mm / 1000))
    K = 4.0 / 3.0 * Es * np.sqrt(np.sqrt(R1 * R2))
    alpha = 3 * (1 - e) / (2 * 3.0)
    I_ball = 0.4 * m * r ** 2
    half_w = 0.006                                     # the tyre's half width (cad/turret.py Geo.tyre_w = 12)
    # motors
    kv1, kv2 = (_arr(wheels.kv_scale[0], n), _arr(wheels.kv_scale[1], n))
    V = L.supply_v * wheels.v_scale
    ke = [60.0 / (2 * math.pi * MOTOR['kv_rpm_v'] * kv) for kv in (kv1, kv2)]
    kt = [MOTOR['kt'] / kv for kv in (kv1, kv2)]
    tf_per_w = MOTOR['kt'] * MOTOR['i0_a'] / (MOTOR['i0_at_rpm'] * 2 * math.pi / 60)
    w0 = [np.array([tl.no_load_speed(L, float(k), wheels.v_scale) for k in kv]) for kv in (kv1, kv2)]
    w_set = [_arr(wheels.w_set[i], n) if not wheels.full_throttle else w0[i] for i in range(2)]
    w = [w_set[i].copy() if wheels.w0 is None else _arr(wheels.w0[i], n) for i in range(2)]
    integ = [np.zeros(n), np.zeros(n)]
    sign = (1.0, -1.0)
    yw = (c / 2, -c / 2)
    ro = _arr(wheels.runout, n)
    ph = [_arr(wheels.runout_phase[i], n) for i in range(2)]
    ang = [np.zeros(n), np.zeros(n)]                   # each wheel's rotation since the ball arrived (for the runout)
    # the ball: first touch at x0 for a centred ball (y = 0); start 10 um before it
    x = -np.sqrt(np.maximum(0.0, (Rw + r) ** 2 - (c / 2) ** 2)) - 1e-5
    y, z = _arr(entry.y, n), _arr(entry.z, n)
    vx, vy, vz = _arr(entry.vx, n), _arr(entry.vy, n), _arr(entry.vz, n)
    wx, wz = _arr(entry.wx, n), _arr(entry.wz, n)
    wy = vx / r if entry.wy is None else _arr(entry.wy, n)
    touched = np.zeros(n, bool)
    done = np.zeros(n, bool)
    t_exit = np.full(n, np.nan)
    peak_fn = np.zeros(n)
    peak_fx = np.zeros(n)
    impulse = np.zeros(3)                              # on the population mean ball (recoil), N s per ball
    imp = np.zeros((n, 3))
    slip_e = np.zeros(n)
    contact_t = np.zeros(n)
    rec = [] if record else None
    t = 0.0
    steps = int(T_MAX / dt)
    zero = np.zeros(n)
    if bore_r:
        Rc = 1 / (1 / r - 1 / bore_r)
        K_w = 4 / 3 * Es * np.sqrt(np.sqrt(Rc * r))
        play = bore_r - r
    wall_t = np.zeros(n)
    for k in range(steps):
        live = ~done
        Fx, Fy, Fz = zero.copy(), zero.copy(), zero.copy()
        Tx, Ty, Tz = zero.copy(), zero.copy(), zero.copy()
        any_contact = np.zeros(n, bool)
        load = [zero.copy(), zero.copy()]
        if bore_r:                                                 # the channel's floor and ceiling (and sides) through the nip
            rho = np.sqrt(y * y + z * z) + 1e-12
            dw = rho - play
            incw = (dw > 0) & live
            if incw.any():
                ny_w, nz_w = -y / rho, -z / rho                    # from the wall towards the axis
                vn_w = -(vy * ny_w + vz * nz_w)
                Fw = np.where(incw, np.clip(K_w * np.clip(dw, 0, None) ** 1.5 * (1 + alpha * vn_w), 0, None), 0.0)
                # the ball's surface at the wall contact: v + omega x (-r n), n = (0, ny, nz)
                cx_, cy_, cz_ = 0.0, -r * ny_w, -r * nz_w
                bsx = vx + (wy * cz_ - wz * cy_)
                bsy = vy + (wz * cx_ - wx * cz_)
                bsz = vz + (wx * cy_ - wy * cx_)
                sx, sy, sz = -bsx, -bsy, -bsz
                sn = sy * ny_w + sz * nz_w
                sy, sz = sy - sn * ny_w, sz - sn * nz_w
                smag = np.sqrt(sx * sx + sy * sy + sz * sz) + 1e-12
                Ftw = MU_BORE * Fw * np.tanh(smag / V_REG)
                fx_, fy_, fz_ = Ftw * sx / smag, Ftw * sy / smag, Ftw * sz / smag
                Fx += fx_
                Fy += Fw * ny_w + fy_
                Fz += Fw * nz_w + fz_
                Tx += cy_ * fz_ - cz_ * fy_
                Ty += cz_ * fx_ - cx_ * fz_
                Tz += cx_ * fy_ - cy_ * fx_
                wall_t += np.where(incw, dt, 0.0)
        for i in range(2):
            dx, dy = x, y - yw[i]
            D = np.sqrt(dx * dx + dy * dy)
            Reff_i = Rw + ro * np.cos(ang[i] + ph[i])          # runout: the tyre's radius at the contact varies as it turns
            Rs_i = Rw
            if wheels.tyre_E_mpa:
                g_i = tyre_growth(w[i], Rw, wheels.tyre_E_mpa, bonded=wheels.tyre_bonded)
                Reff_i = Reff_i + g_i
                Rs_i = Rw + g_i                                # the grown tyre's surface moves faster
            delta = Reff_i + r - D
            inc = (delta > 0) & (np.abs(z) < half_w) & live
            if not inc.any():
                continue
            any_contact |= inc
            nx, ny = dx / D, dy / D
            vn = -(vx * nx + vy * ny)                           # overlap growth rate
            Fn = np.where(inc, np.clip(K * np.clip(delta, 0, None) ** 1.5 * (1 + alpha * vn), 0, None), 0.0)
            # tyre surface velocity at the contact: omega_i z x (R n) = s_i w_i R (-ny, nx, 0)
            tvx, tvy = -sign[i] * w[i] * Rs_i * ny, sign[i] * w[i] * Rs_i * nx
            # ball surface velocity at the contact point (-r n from its centre): v + omega x (-r n), n = (nx, ny, 0)
            bsx = vx + wz * r * ny
            bsy = vy - wz * r * nx
            bsz = vz - wx * r * ny + wy * r * nx
            sx, sy, sz = tvx - bsx, tvy - bsy, -bsz
            sn = sx * nx + sy * ny
            sx, sy = sx - sn * nx, sy - sn * ny
            smag = np.sqrt(sx * sx + sy * sy + sz * sz) + 1e-12
            Ft = mu * Fn * np.tanh(smag / V_REG)
            ftx, fty, ftz = Ft * sx / smag, Ft * sy / smag, Ft * sz / smag
            Fx += Fn * nx + ftx
            Fy += Fn * ny + fty
            Fz += ftz
            # torque on the ball: (-r n) x Ft
            Tx += (-r * ny) * ftz
            Ty += (r * nx) * ftz
            Tz += (-r * nx) * fty + (r * ny) * ftx
            # the wheel: torque about z from -Ft at R n:  (R n x -Ft)_z = R (-nx fty + ny ftx); positive load slows it
            load[i] = np.where(inc, -sign[i] * Rw * (-nx * fty + ny * ftx), 0.0)
            slip_e += Ft * smag * dt
            peak_fn = np.maximum(peak_fn, Fn)
        for i in range(2):                                        # the motors run every step, loaded or not
            if wheels.brake:
                cur = -brake_current(ke[i], w[i], L)
            elif wheels.full_throttle:
                cur = np.minimum((V - ke[i] * w[i]) / L.r_eff_ohm, L.i_max_a)
            else:
                tgt = w_set[i] * min(1.0, (t + wheels.t_offset) / wheels.ramp_s) if wheels.ramp_s else w_set[i]
                err = tgt - w[i]
                integ[i] += err * dt
                cur = np.clip(L.kp * err * 1000 + L.ki * integ[i] * 1000, -L.i_max_a, L.i_max_a)
                cur = np.minimum(cur, (V - ke[i] * w[i]) / L.r_eff_ohm)
            tau = kt[i] * cur - tf_per_w * w[i]
            w[i] = w[i] + (tau - load[i]) / L.wheel_I * dt
            ang[i] += w[i] * dt
        touched |= any_contact
        peak_fx = np.maximum(peak_fx, Fx)
        vx = np.where(live, vx + Fx / m * dt, vx)
        vy = np.where(live, vy + Fy / m * dt, vy)
        vz = np.where(live, vz + (Fz / m - 9.81) * dt, vz)
        wx = np.where(live, wx + Tx / I_ball * dt, wx)
        wy = np.where(live, wy + Ty / I_ball * dt, wy)
        wz = np.where(live, wz + Tz / I_ball * dt, wz)
        x = np.where(live, x + vx * dt, x)
        y = np.where(live, y + vy * dt, y)
        z = np.where(live, z + vz * dt, z)
        imp[:, 0] += Fx * dt
        imp[:, 1] += Fy * dt
        imp[:, 2] += Fz * dt
        contact_t += np.where(any_contact, dt, 0.0)
        t += dt
        newly = live & touched & ~any_contact & (x > 0)
        t_exit[newly] = t
        done |= newly
        if rec is not None and k % 20 == 0:
            rec.append((t, float(x[0]), float(vx[0]), float(w[0][0]), float(w[1][0]), float(wz[0])))
        if done.all():
            break
    v = np.stack([vx, vy, vz], 1)
    om = np.stack([wx, wy, wz], 1)
    speed = np.linalg.norm(v, axis=1)
    out = {'v': v, 'omega': om, 'speed': speed, 'fps': speed / FPS, 'exit_pos': np.stack([x, y, z], 1),
           'rejected': ~done, 'contact_ms': contact_t * 1000, 't_exit': t_exit, 'w_end': (w[0], w[1]), 'w_start': (w_set[0], w_set[1]),
           'peak_normal_n': peak_fn, 'peak_fx_n': peak_fx, 'impulse_ns': imp, 'slip_loss_j': slip_e,
           'spin_z_rad_s': wz, 'spin_y_rad_s': wy, 'yaw_mrad': np.arctan2(vy, vx) * 1000,
           'pitch_mrad': np.arctan2(vz, vx) * 1000, 'ke_j': 0.5 * m * speed ** 2, 'bore_wall_ms': wall_t * 1000}
    if rec is not None:
        out['trace'] = rec
    return out


# ------------------------------------------------------------------------------------------------ the hardware ceiling, ARM release

def _tol_wheels(tol, **kw):
    return Wheels(full_throttle=True, kv_scale=(tol['kv'], tol['kv']), v_scale=tol['v'], **kw)


def ceiling_balls(balls):
    """The ceiling's balls: the corners of the accepted range (D67, tl.corners) and the population clipped into it."""
    return [replace(b, d_mm=float(np.clip(b.d_mm, *tl.BALL_D)), m_g=float(np.clip(b.m_g, *tl.BALL_M))) for b in balls]


def ceiling_at(balls, L, tol=None, seed=5, bonded=None):
    """The fastest accepted ball at 100 % throttle with the tolerance stack (tl.TOL: trimmed), the feed's offsets, 0.15 mm
    runout and the soft tyre's growth (bonded unless told): the population and the 32 corners. Returns (top fps,
    population mean fps, the corners' top fps, the corner, the highest energy density J/m^2, that ball)."""
    tol = tol or tl.TOL
    rng = np.random.default_rng(seed)
    n = len(balls)
    ent = Entry(y=rng.uniform(-0.00075, 0.00075, n), z=-0.00075 + rng.uniform(-0.0003, 0.0003, n), vx=rng.uniform(0.4, 0.8, n))
    phases = (rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n))
    r = launch3d(balls, L, ent, _tol_wheels(tol, runout=0.00015, runout_phase=phases, tyre_E_mpa=TPU['E_mpa'][0], tyre_bonded=bonded))
    cs = tl.corners()
    nc = len(cs)
    rc = launch3d(cs, L, Entry(z=0.0, wy=0.0), _tol_wheels(tol, runout=0.00015, runout_phase=(np.zeros(nc), np.full(nc, math.pi / 2)),
                                                           tyre_E_mpa=TPU['E_mpa'][0], tyre_bonded=bonded))
    ok, okc = ~r['rejected'], ~rc['rejected']
    k = int(np.argmax(np.where(okc, rc['fps'], -1)))
    kd = [tl.ked(b, float(v)) if o else 0.0 for b, v, o in zip(list(balls) + cs, np.concatenate([r['speed'], rc['speed']]), np.concatenate([ok, okc]))]
    j = int(np.argmax(kd))
    return (max(float(r['fps'][ok].max()), float(rc['fps'][okc].max())), float(r['fps'][ok].mean()), float(rc['fps'][k]), cs[k].name,
            kd[j], (list(balls) + cs)[j].name)


def ceiling_map(balls, rails=(10.5, 11.0, tl.RAIL_V_TRIM, 12.0, 12.5), wheels=(36.0, 38.0, 40.0), crush=None, seed=5):
    """The hardware ceiling for each rail voltage (a nominal-KV motor; with the per-turret trim this is the trimmed
    no-load speed) and tyre diameter: ceiling_at, with each tyre at its crush on this cage (the motors' axes
    tl.CAGE_C_MM apart) unless a crush is given. The Hasbro ball at 100 % with no tolerance beside it."""
    balls = ceiling_balls(balls)
    rows = []
    for V in rails:
        for D in wheels:
            cr = tl.cage_crush(D) if crush is None else crush
            L = tl.launcher_for(D, cr, supply_v=V)
            top, mean, _, corner, kd, kball = ceiling_at(balls, L, seed=seed)
            hb = launch3d(tl.HASBRO, L, Entry(z=0.0, wy=0.0), Wheels(full_throttle=True))
            w0 = tl.no_load_speed(L)
            rows.append({'rail_v': round(V, 3), 'wheel_d_mm': D, 'crush': round(cr, 3), 'no_load_rpm': round(tl.rpm(w0)),
                         'no_load_rpm_tol': round(tl.rpm(tl.no_load_speed(L, tl.TOL['kv'], tl.TOL['v']))), 'surface_m_s_tol': round(tl.no_load_speed(L, tl.TOL['kv'], tl.TOL['v']) * D / 2000, 2),
                         'ceiling_fps': round(top, 1), 'worst_corner': corner, 'hasbro_full_throttle_fps': round(float(hb['fps'][0]), 1),
                         'population_mean_fps': round(mean, 1), 'margin_fps': round(CAP_FPS - top, 1), 'densest_ked_j_m2': round(kd),
                         'holds': top <= CAP_FPS, 'under_astm': kd <= tl.ASTM_KED})
    return rows


def wheel_decay(L, w0, t_end=1.5, i_brake=None, dt=1e-4, delay=0.0, l_ll_h=None):
    """Wheel speed vs time after the ESC drops drive: coast (friction only) or dynamic braking with the phase current
    limited to i_brake (the ESC shorts or regenerates: i = min(i_brake, ke w / R_eff)); i_brake = 'short' is the
    phase-short FETs (brake_current: the motor's resistance, the FETs' and the taps', and the winding's inductance),
    closing `delay` s after the release. Returns (t, w) arrays."""
    ke = 60.0 / (2 * math.pi * MOTOR['kv_rpm_v'])
    tf_per_w = MOTOR['kt'] * MOTOR['i0_a'] / (MOTOR['i0_at_rpm'] * 2 * math.pi / 60)
    n = int(t_end / dt)
    t = np.arange(n) * dt
    w = np.empty(n)
    x = w0
    for k in range(n):
        w[k] = x
        tau = -tf_per_w * x
        if i_brake and t[k] >= delay:
            ib = brake_current(ke, x, L, l_ll_h) if i_brake == 'short' else min(i_brake, ke * x / L.r_eff_ohm)
            tau -= MOTOR['kt'] * ib
        x = max(0.0, x + tau / L.wheel_I * dt)
    return t, w


def brake_time_constant(L, with_circuit=True):
    """tau = I R / (ke kt) of the phase-short brake at low speed (where the inductance no longer limits the current),
    from the model's inertia and the short's resistance: the motor's own, plus the FETs' and the taps' (with_circuit)."""
    ke = 60.0 / (2 * math.pi * MOTOR['kv_rpm_v'])
    r = L.r_eff_ohm + ((2 * BRAKE['r_fet_ohm'] + BRAKE['r_taps_ohm']) if with_circuit else 0.0)
    return L.wheel_I * r / (ke * MOTOR['kt'])


def release_window(ball, L, w_set, delay=0.010, latencies_ms=range(0, 301, 10)):
    """The plan's V14: the line drops at t = 0, the phases are shorted at `delay`; a ball already dropped reaches the
    nip `latency` later. For each latency: the wheel speed then and the ball's exit speed (or that it rests)."""
    t, w = wheel_decay(L, w_set, i_brake='short', delay=delay, t_end=0.4)
    rows = []
    for ms in latencies_ms:
        wl = float(np.interp(ms / 1000, t, w))
        if wl < 0.01 * w_set:
            rows.append({'latency_ms': ms, 'wheel_rpm': round(wl * 60 / (2 * math.pi)), 'exit_fps': 0.0, 'rests': True})
            continue
        r = launch3d(ball, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(wl, wl), w0=(wl, wl), brake=True))
        v = float(r['speed'][0])
        rows.append({'latency_ms': ms, 'wheel_rpm': round(wl * 60 / (2 * math.pi)), 'exit_fps': round(v / FPS, 1), 'rests': bool(r['rejected'][0] or v < 1.0)})
    pct5 = float(t[np.argmax(w < 0.05 * w_set)]) if (w < 0.05 * w_set).any() else None
    sens = {}
    for lh in (0.0, 20e-6, 35e-6, 50e-6):                 # the winding inductance is not published: how much it matters
        ts, ws = wheel_decay(L, w_set, i_brake='short', delay=delay, t_end=0.4, l_ll_h=lh)
        p5 = float(ts[np.argmax(ws < 0.05 * w_set)]) if (ws < 0.05 * w_set).any() else None
        sens[f'{lh * 1e6:g}uH'] = {'speed_5pct_at_ms': round(p5 * 1000, 1) if p5 else None,
                                   'speed_at_96ms_pct': round(100 * float(np.interp(0.096, ts, ws)) / w_set, 3)}
    return {'short_delay_ms': delay * 1000, 'tau_ms_model': round(brake_time_constant(L) * 1000, 2),
            'tau_ms_motor_only': round(brake_time_constant(L, with_circuit=False) * 1000, 2), 'tau_ms_plan': 12.0,
            'circuit': {**BRAKE, 'loop_ohm': round(L.r_eff_ohm + 2 * BRAKE['r_fet_ohm'] + BRAKE['r_taps_ohm'], 4)},
            'speed_5pct_at_ms': round(pct5 * 1000, 1) if pct5 else None,
            'speed_at_96ms_pct': round(100 * float(np.interp(0.096, t, w)) / w_set, 3), 'inductance_sensitivity': sens, 'rows': rows,
            'worst_exit_fps': max(r['exit_fps'] for r in rows), 'worst_latency_ms': max((r['latency_ms'] for r in rows if r['exit_fps'] > 20), default=None)}


def stray_ball_rearm(ball, L, w_set, runout=0.00015, ramp_s=0.2):
    """A ball resting at the nip (touching both stopped tyres, as the release case leaves it) when the next arm spins
    the wheels up: a 200 ms ramp or a stepped spin-up on the 10 A limit. The tyres' runout engages the ball; the
    exit speed is whatever the wheels have when it goes."""
    out = {}
    for label, rs in (('ramp_200ms', ramp_s), ('stepped_10A_limit', 0.0)):
        r = launch3d(ball, L, Entry(z=0.0, vx=0.0, wy=0.0), Wheels(w_set=(w_set, w_set), w0=(1.0, 1.0), ramp_s=rs, runout=runout, runout_phase=(0.0, math.pi / 3)))
        v = float(r['speed'][0])
        out[label] = {'exit_fps': round(v / FPS, 1), 'leaves_after_ms': round(float(r['t_exit'][0]) * 1000, 1) if not np.isnan(r['t_exit'][0]) else None,
                      'wheel_rpm_when_it_leaves': [round(float(r['w_end'][i][0]) * 60 / (2 * math.pi)) for i in range(2)], 'rests': bool(r['rejected'][0] or v < 1.0)}
    r = launch3d(ball, L, Entry(z=0.0, vx=0.0, wy=0.0), Wheels(w_set=(0.15 * w_set, 0.15 * w_set), w0=(1.0, 1.0), ramp_s=0.1, runout=runout, runout_phase=(0.0, math.pi / 3)))
    out['stray_clear_at_15pct'] = {'exit_fps': round(float(r['speed'][0]) / FPS, 1), 'note': 'a deliberate low-speed clear (15 % set speed, muzzle down) before arming for real'}
    out['dial_reverse'] = {'possible': False, 'why': 'the resting ball sits at the first-touch point, 21 mm ahead of and 21 mm below the dial pocket it fell from (cad/turret.py: exit_x 37, '
                                                    'chute_r 21.35, first touch at x 58.4): nothing on the dial reaches past the chute bend, so it cannot be pulled back'}
    return out


def fault_input(balls, L, volts=(20.5,)):
    """The converter bypassed or failed short, so the ESCs see the turret's input (plan V13): every ball at 100 % throttle.
    20.5 V is one DCB609 full (standing alone; the AM32 ESCs are rated to 25.2 V, so they run); Gyropup's 30-42 V bus
    is over the ESCs' rating and would destroy them before a ball is fed."""
    out = {}
    for v in volts:
        Lf = tl.Launcher(wheel_d_mm=L.wheel_d_mm, gap_mm=L.gap_mm, supply_v=v, wheel_I=L.wheel_I, r_eff_ohm=L.r_eff_ohm)
        r = launch3d(balls, Lf, Entry(z=0.0, wy=0.0), Wheels(full_throttle=True))
        ok = ~r['rejected']
        out[f'{v:g}_v'] = {'population_fps': {'mean': round(float(r['fps'][ok].mean()), 1), 'min': round(float(r['fps'][ok].min()), 1), 'max': round(float(r['fps'][ok].max()), 1)},
                           'no_load_rpm': round(tl.rpm(tl.no_load_speed(Lf))), 'no_load_erpm': round(tl.rpm(tl.no_load_speed(Lf)) * MOTOR['pole_pairs']),
                           'surface_m_s': round(tl.no_load_speed(Lf) * L.wheel_d_mm / 2000, 1)}
    return out


def chronograph(G, fps_cases=(95.0, 100.0, 105.0, 110.0, 175.0), spacings_mm=(50.0, 60.0), beam_mm=1.0, edge_jitter_us=30.0, trip_fps=105.0):
    """Gate transit times for the trip window (plan 2.10): two IR gates in the barrel. Also what the bore does between
    the gates (the barrel model loses ~1.4 fps over 111 mm: 0.6 fps over 50 mm) and the timing error budget."""
    out = {'cad_gates_from_socket_mm': [30.0, 80.0], 'cad_spacing_mm': 50.0, 'barrel_len_mm': G.barrel_len, 'socket_mm': 14.0, 'orange_tip_mm': 15.0,
           'trip_fps': trip_fps}
    for s in spacings_mm:
        rows = {}
        for f in fps_cases:
            v = f * FPS
            dt_us = s / 1000 / v * 1e6
            rows[f'{f:g}_fps'] = {'transit_us': round(dt_us, 1), 'ball_occludes_gate_us': round((G.ball + beam_mm) / 1000 / v * 1e6, 1), 'beam_crossing_us': round(beam_mm / 1000 / v * 1e6, 1)}
        vt = trip_fps * FPS
        win = s / 1000 / vt
        err_fps = edge_jitter_us * 1e-6 / win * trip_fps
        out[f'spacing_{s:g}_mm'] = {'rows': rows, 'trip_window_us': round(win * 1e6, 1), 'fps_error_from_30us_edge_jitter': round(err_fps, 2),
                                     'fps_error_from_1pct_rc_window': round(0.01 * trip_fps, 2), 'bore_loss_between_gates_fps': round(1.4 * s / 111, 2)}
    w60 = 0.060 / (trip_fps * FPS) * 1e6
    out['recommendation'] = (f'the CAD\'s two gates 60 mm apart (x0 + 22 and x0 + 82: 8 mm past the socket, 18 mm before the muzzle, clear of the orange tip\'s '
                             f'boss): a {w60:.0f} us window at {trip_fps:g} fps, so a 30 us edge jitter is {edge_jitter_us * 1e-6 / (w60 * 1e-6) * trip_fps:.1f} fps and a 1 % timing part '
                             f'{0.01 * trip_fps:.1f} fps: the latch trips within {edge_jitter_us / w60 * trip_fps + 0.01 * trip_fps:.1f} fps of {trip_fps:g} (the Hasbro ball leaves at 95-100, the worst accepted '
                             f'corner at 104); slit the Ø3.2 cross holes to a 1 mm beam (crossed in 31 us at 32 m/s) so both gates see the same sharp edge. A bypassed '
                             f'converter (the ESCs on the 20.5 V pack) throws ~175 fps and crosses in 1.1 ms, unmistakable, but it has already left: the pre-feed '
                             f'eRPM check (refuse to feed above the bench\'s n_105) is what stops the first fault ball')
    return out


def exit_vs_wheel_speed(ball, L, w_set, fractions=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)):
    """Exit speed when the ball meets the tyres at a fraction of the set speed (the ESC not driving: the wheels keep
    only their inertia). A ball under 1 m/s is counted as stuck in the nip."""
    rows = []
    for f in fractions:
        w = w_set * f
        r = launch3d(ball, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w, w), w0=(w, w)))
        v = float(r['speed'][0])
        rows.append({'fraction': f, 'rpm': round(w * 60 / (2 * math.pi)), 'surface_fps': round(w * L.wheel_d_mm / 2000 / FPS, 1), 'exit_fps': round(v / FPS, 1), 'stuck': bool(r['rejected'][0] or v < 1.0)})
    return rows


def arm_release(ball, L, w_set, latencies=(0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 1.4)):
    """A ball that was already dropped when ARM opened reaches the nip `latency` seconds later: what speed it leaves at,
    with the wheels coasting or braked (dynamic braking at 10 A and 20 A phase current)."""
    out = {}
    for mode, ib in (('coast', None), ('brake_10A', 10.0), ('brake_20A', 20.0)):
        t, w = wheel_decay(L, w_set, i_brake=ib)
        rows = []
        for lat in latencies:
            wl = float(np.interp(lat, t, w))
            if wl < 0.02 * w_set:
                rows.append({'latency_s': lat, 'wheel_rpm': round(wl * 60 / (2 * math.pi)), 'exit_fps': 0.0, 'stuck': True})
                continue
            r = launch3d(ball, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(wl, wl), w0=(wl, wl)))
            v = float(r['speed'][0])
            rows.append({'latency_s': lat, 'wheel_rpm': round(wl * 60 / (2 * math.pi)), 'exit_fps': round(v / FPS, 1), 'stuck': bool(r['rejected'][0] or v < 1.0)})
        stop = float(t[np.argmax(w < 0.05 * w_set)]) if (w < 0.05 * w_set).any() else None
        out[mode] = {'time_to_5pct_s': round(stop, 3) if stop is not None else None, 'rows': rows}
    return out


def validate_nuaa_mismatch():
    """The NUAA friction-wheel guide's test: a deliberate 1000 rpm mismatch between two Ø60 PU wheels moved the 17 mm
    3.2 g TPU ball only ~13 cm at 15 m. Our chain: 3D launch (spin from the mismatch) -> flight (Magnus) -> drift at
    15 m; also the no-slip (Nathan) spin for comparison. Ball: est E 15 MPa (solid TPU 90A), e 0.7, mu 0.6; wheels
    Ø60 with 2.8 mm of crush (gap 14 mm, Luo 2025), 3e-5 kg m^2 each (est, an aluminium core), 24 V."""
    import turret_flight as tf
    rm = tl.Ball('rm17', 16.8, 3.2, 15.0, 0.4, 0.7, 0.6)
    L = tl.launcher_for(60.0, 1 - 14.0 / 16.8, ball_d=16.8, supply_v=24.0, wheel_I=3e-5)
    w = tl.set_speed_for(rm, L, 15.7)
    out = {'wheel_rpm': round(w * 60 / (2 * math.pi)), 'surface_m_s': round(w * 0.03, 2)}
    dw = 1000 * 2 * math.pi / 60
    r0 = launch3d(rm, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w, w)), bore_r=None)
    r1 = launch3d(rm, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w + dw / 2, w - dw / 2)), bore_r=None)
    spin = float(r1['spin_z_rad_s'][0])
    nathan = dw * 0.03 / (2 * 0.0084)
    spec = __import__('turret_ball').BallSpec('rm17', 'rm', 16.8, 3.2, 15.0, 0.7, 0.6, 0.5)
    v = float(r1['speed'][0])
    # a lofted shot that reaches 15 m (the robots fire upwards at distant plates); the drift is what the spin does on the way
    f = tf.fly(spec, [[v, 0, 0]], [[0, 0, spin]], h0=0.5, elev_rad=math.radians(25), ranges=(10, 15))
    f7 = tf.fly(spec, [[v, 0, 0]], [[0, 0, spin / 7]], h0=0.5, elev_rad=math.radians(25), ranges=(10, 15))
    out.update({'exit_m_s_matched': round(float(r0['speed'][0]), 2), 'exit_m_s_mismatched': round(v, 2),
                'ball_spin_rad_s_model': round(abs(spin), 1), 'ball_spin_rad_s_no_slip_nathan': round(nathan, 1), 'spin_fraction_of_no_slip': round(abs(spin) / nathan, 3),
                'flight_time_to_15m_s': round(float(f['cross'][15][0, 3]), 2) if not np.isnan(f['cross'][15][0, 3]) else None,
                'drift_cm_at_15m_if_1000_rpm_mechanical': round(abs(float(f['cross'][15][0, 0])) * 100, 1) if not np.isnan(f['cross'][15][0, 0]) else None,
                'drift_cm_at_15m_if_1000_rpm_is_erpm_7_pole_pairs': round(abs(float(f7['cross'][15][0, 0])) * 100, 1) if not np.isnan(f7['cross'][15][0, 0]) else None,
                'published_cm': 13.0,
                'reading': 'the guide does not say whether its "1000 rpm" is mechanical or the ESC\'s electrical rpm (a 7-pole-pair motor turns 143 rpm at 1000 eRPM); '
                           'the model agrees with the guide under the eRPM reading and is ~7x over under the mechanical one. Either way the chain (slip -> spin -> Magnus) is the '
                           'right order of magnitude, and Gyropup\'s PI-matched wheels sit far below either: a 2 % mismatch is 120 rpm of ball spin',
                'source': 'NUAA friction-wheel design guide (sim/turret_flight.py FLIGHT validation_sources)'})
    return out


# ------------------------------------------------------------------------------------------------ checks and the study

def check_against_1d(ball=None, L=None, w=None):
    """Same ball, same wheel speed, centred, no runout: 3D vs 1D exit speed. Returns (fps_3d, fps_1d, rel_err)."""
    ball = ball or tl.DESIGN['nominal']
    L = L or tl.launcher_for(tl.DESIGN['wheel_d_mm'], tl.DESIGN['crush'])
    w = w or tl.set_speed_for(ball, L, tl.DESIGN['set_fps'] * FPS)
    r1 = tl.shot(ball, L, w)
    r3 = launch3d(ball, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w, w)), bore_r=None)
    return float(r3['fps'][0]), r1['fps'], abs(float(r3['fps'][0]) - r1['fps']) / r1['fps']


def design_launcher():
    D = tl.DESIGN
    return tl.launcher_for(D['wheel_d_mm'], D['crush'])


def study(quick=False, seed=1):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    try:
        import turret_ball as tb
        pop = tb.population(120 if quick else 400, seed=seed)
        balls = ceiling_balls([b.launch() for b in pop])           # accepted rounds only (D67): clipped to 22.2-22.8 mm, 1.6-2.0 g
        ball_src = 'sim/turret_ball.py'
    except Exception as exc:                                   # the ball module is mine too, but keep this runnable alone
        pop = None
        balls = tl.population(120 if quick else 400, seed=seed)    # already the accepted range
        ball_src = f'sim/turret_launch.py population ({exc})'
    OUT.mkdir(parents=True, exist_ok=True)
    import turret_common as tc
    Gc = tc.cad_turret().Geo()
    set_bore(Gc)
    D = tl.DESIGN
    L = design_launcher()
    nominal = D['nominal']
    w_set = tl.set_speed_for(nominal, L, D['set_fps'] * FPS)
    w0 = tl.no_load_speed(L)
    res = {'model': __doc__.split('\n\n')[1].strip(), 'balls_from': ball_src, 'bore_r_mm': round(BORE_R_M * 1000, 3), 'design': {'wheel_d_mm': D['wheel_d_mm'], 'crush': D['crush'], 'supply_v': D['supply_v'],
           'set_rpm': round(w_set * 60 / (2 * math.pi)), 'no_load_rpm': round(w0 * 60 / (2 * math.pi)), 'set_fps_nominal': D['set_fps']}}
    f3, f1, err = check_against_1d(nominal, L, w_set)
    res['handover_1d'] = {'fps_3d': round(f3, 2), 'fps_1d': round(f1, 2), 'rel_err': round(err, 4), 'pass': err < 0.01}
    rng = np.random.default_rng(seed)
    n = len(balls)
    # 1. the population at the set speed, centred, then with the feed's offsets and tyre runout
    base = launch3d(balls, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w_set, w_set)))
    ent = Entry(y=rng.uniform(-0.00075, 0.00075, n), z=-0.00075 + rng.uniform(-0.0003, 0.0003, n), vx=rng.uniform(0.4, 0.8, n),
                vy=rng.normal(0, 0.05, n), vz=rng.normal(0, 0.05, n))
    real = launch3d(balls, L, ent, Wheels(w_set=(w_set, w_set), runout=0.00015, runout_phase=(rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n))))
    worn = launch3d(balls, L, ent, Wheels(w_set=(w_set, w_set), runout=0.0003, runout_phase=(rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n))))

    def stats(r, key='fps'):
        v = r[key][~r['rejected']] if key in r else None
        return {'n': int((~r['rejected']).sum()), 'rejected': int(r['rejected'].sum()), 'mean': round(float(np.mean(v)), 2), 'sd': round(float(np.std(v)), 2),
                'p1': round(float(np.percentile(v, 1)), 2), 'p99': round(float(np.percentile(v, 99)), 2), 'min': round(float(v.min()), 2), 'max': round(float(v.max()), 2)}

    def disp(r):
        ok = ~r['rejected']
        return {'yaw_mrad_sd': round(float(np.std(r['yaw_mrad'][ok])), 3), 'yaw_mrad_p99abs': round(float(np.percentile(np.abs(r['yaw_mrad'][ok]), 99)), 3),
                'pitch_mrad_sd': round(float(np.std(r['pitch_mrad'][ok])), 3), 'spin_z_rad_s_sd': round(float(np.std(r['spin_z_rad_s'][ok])), 1),
                'spin_y_rad_s_mean': round(float(np.mean(r['spin_y_rad_s'][ok])), 1), 'spin_y_rad_s_sd': round(float(np.std(r['spin_y_rad_s'][ok])), 1)}
    phases = (rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n))
    grown = launch3d(balls, L, ent, Wheels(w_set=(w_set, w_set), runout=0.00015, runout_phase=phases, tyre_E_mpa=TPU['E_mpa'][0]))
    Rw = L.wheel_d_mm / 2000
    wt = w0 * tl.TOL['kv'] * tl.TOL['v']
    res['tyre_growth_mm'] = {'at_set_speed': {f'E_{E:g}_MPa': round(tyre_growth(w_set, Rw, E) * 1000, 3) for E in TPU['E_mpa']},
                             'at_no_load_plus_tolerance': {f'E_{E:g}_MPa': round(tyre_growth(wt, Rw, E) * 1000, 3) for E in TPU['E_mpa']},
                             'if_not_bonded_at_no_load_plus_tolerance': {f'E_{E:g}_MPa': round(tyre_growth(wt, Rw, E, bonded=False) * 1000, 3) for E in TPU['E_mpa']},
                             'bonded': TYRE_BONDED,
                             'bore_strain_free_pct_at_no_load_plus_tolerance': {f'E_{E:g}_MPa': round(100 * TPU['rho'] * (wt * (Rw - tl.TYRE_T / 1000)) ** 2 / (E * 1e6), 1) for E in TPU['E_mpa']},
                             'source': TPU['source'], 'note': 'radial growth per tyre; the crush grows by twice this'}
    res['population_set_speed'] = {'centred_no_runout': {**stats(base), **disp(base)},
                                   'feed_offsets_runout_0_15mm': {**stats(real), **disp(real)},
                                   'feed_offsets_runout_0_30mm': {**stats(worn), **disp(worn)},
                                   'feed_offsets_runout_soft_tyre_growth_10mpa': {**stats(grown), **disp(grown)},
                                   'contact_ms_mean': round(float(np.mean(real['contact_ms'])), 3)}
    # 2. the hardware ceiling: 100 % throttle on the trimmed rail with the remaining tolerances (tl.TOL: the magnets +15 C,
    #    the rail +2 %), the feed's offsets, 0.15 mm runout, the soft tyre's growth (bonded), the population and the 32
    #    corners of the accepted range; then the same untrimmed (a fixed set point) and with a tyre come loose
    top, mean, ctop, corner, kd, kball = ceiling_at(balls, L, seed=seed)
    topu, _, ctopu, corneru, kdu, _ = ceiling_at(balls, L, tol=tl.TOL_UNTRIMMED, seed=seed)
    topd, _, ctopd, cornerd, kdd, _ = ceiling_at(balls, L, seed=seed, bonded=False)
    ceil = launch3d(balls, L, ent, _tol_wheels(tl.TOL, runout=0.00015, runout_phase=phases, tyre_E_mpa=TPU['E_mpa'][0]))
    hb = launch3d(nominal, L, Entry(z=0.0, wy=0.0), Wheels(full_throttle=True))
    pop_ft = launch3d(balls, L, ent, Wheels(full_throttle=True, runout=0.00015, runout_phase=phases, tyre_E_mpa=TPU['E_mpa'][1]))
    n105 = tl.rpm(w0 * tl.TOL['kv'] * tl.TOL['v']) * CAP_FPS / top
    nastm = tl.rpm(w0 * tl.TOL['kv'] * tl.TOL['v']) * math.sqrt(tl.ASTM_KED / kd)
    res['ceiling'] = {'population_full_throttle': stats(ceil), 'worst_corner_fps': round(ctop, 2), 'worst_corner': corner,
                      'densest_ked_j_m2': round(kd), 'densest_ball': kball, 'astm_ked_j_m2': tl.ASTM_KED, 'under_astm': bool(kd <= tl.ASTM_KED),
                      'n_astm_rpm': round(nastm),
                      'hasbro_full_throttle_fps': round(float(hb['fps'][0]), 2), 'population_full_throttle_no_tolerance': stats(pop_ft),
                      'untrimmed': {'highest_fps': round(topu, 2), 'worst_corner': corneru, 'densest_ked_j_m2': round(kdu), 'tolerances': tl.TOL_UNTRIMMED['note']},
                      'tyre_come_loose': {'highest_fps': round(topd, 2), 'worst_corner': cornerd, 'densest_ked_j_m2': round(kdd),
                                          'note': 'the tyre debonded and floating on its 4 % stretch fit (the free ring, E 10 MPa): a failure the bench spin test (4.1) and the chronograph trip catch'},
                      'cap_fps': CAP_FPS, 'highest_fps_any_case': round(top, 2), 'margin_fps': round(CAP_FPS - top, 2), 'holds': bool(top <= CAP_FPS),
                      'tolerances': tl.TOL['note'], 'n_trim_rpm': round(tl.rpm(w0)), 'n_105_rpm': round(n105),
                      'how_held': (f'the trimmed flywheel rail ({D["supply_v"]:.2f} V for a nominal motor; each turret\'s set by one fixed resistor so the faster '
                                   f'motor turns {tl.rpm(w0):,.0f} rpm at no load, warm) + the {tl.MOTOR["name"]} ({tl.MOTOR["kv_rpm_v"]:.0f} rpm/V) + the bonded '
                                   f'Ø{D["wheel_d_mm"]:.0f} tyre ({w0 * D["wheel_d_mm"] / 2000:.1f} m/s surface): even 100 % throttle with the magnets 15 C warmer and the rail '
                                   f'2 % high leaves the fastest accepted ball at the figure above and the densest under ASTM F963\'s 2500 J/m^2; the firmware '
                                   f'cannot raise the rail, refuses to feed above {min(n105, nastm):,.0f} rpm (where a ball could pass either), and the '
                                   f'chronograph latches SAFE on any ball over {CAP_FPS:.0f} fps')}
    # 3. mismatched wheels: one wheel slow by 2, 5, 10 %, and one wheel at the set speed with the other at no-load
    mis = []
    for pct in (0.0, 2.0, 5.0, 10.0):
        r = launch3d(nominal, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w_set, w_set * (1 - pct / 100))))
        mis.append({'slow_wheel_pct': pct, 'fps': round(float(r['fps'][0]), 2), 'spin_z_rad_s': round(float(r['spin_z_rad_s'][0]), 1),
                    'spin_rpm': round(float(r['spin_z_rad_s'][0]) * 60 / (2 * math.pi)), 'yaw_mrad': round(float(r['yaw_mrad'][0]), 3),
                    'spin_parameter': round(float(abs(r['spin_z_rad_s'][0]) * nominal.d_mm / 2000 / r['speed'][0]), 4)})
    r = launch3d(nominal, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w0 * 0.999, w_set)))
    mis.append({'slow_wheel_pct': 'one wheel at no-load, one at set', 'fps': round(float(r['fps'][0]), 2), 'spin_z_rad_s': round(float(r['spin_z_rad_s'][0]), 1),
                'spin_rpm': round(float(r['spin_z_rad_s'][0]) * 60 / (2 * math.pi)), 'yaw_mrad': round(float(r['yaw_mrad'][0]), 3),
                'spin_parameter': round(float(abs(r['spin_z_rad_s'][0]) * nominal.d_mm / 2000 / r['speed'][0]), 4)})
    res['mismatch'] = mis
    # 4. a burst: 8 balls at the rates the feed allows; the ESC loop recovers between shots
    bursts = {}
    for rate in (3.0, 5.0, 8.0, 10.0):
        w = [w_set, w_set]
        rows = []
        for k in range(8 if not quick else 5):
            r = launch3d(nominal, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w_set, w_set), w0=(w[0], w[1])))
            rows.append({'shot': k + 1, 'w_rpm': [round(w[0] * 60 / (2 * math.pi)), round(w[1] * 60 / (2 * math.pi))], 'fps': round(float(r['fps'][0]), 2)})
            gap = 1.0 / rate - float(r['contact_ms'][0]) / 1000
            w = [tl.recover(L, float(r['w_end'][i][0]), w_set, gap) for i in range(2)]
        bursts[f'{rate:g}_per_s'] = {'shots': rows, 'fps_min': min(x['fps'] for x in rows), 'fps_first': rows[0]['fps'],
                                     'droop_fps': round(rows[0]['fps'] - min(x['fps'] for x in rows), 2)}
    res['bursts'] = bursts
    # 5. recoil and cage loads from the nominal shot
    rn = launch3d(nominal, L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w_set, w_set)), record=True)
    trace = rn.pop('trace')
    res['recoil'] = {'impulse_ns': [round(float(v), 5) for v in rn['impulse_ns'][0]], 'peak_force_on_cage_n': round(float(rn['peak_fx_n'][0]), 1),
                     'peak_normal_per_tyre_n': round(float(rn['peak_normal_n'][0]), 1), 'contact_ms': round(float(rn['contact_ms'][0]), 3),
                     'ball_ke_j': round(float(rn['ke_j'][0]), 4), 'slip_loss_j': round(float(rn['slip_loss_j'][0]), 4),
                     'wheel_speed_drop_pct': [round(100 * (1 - float(rn['w_end'][i][0]) / w_set), 2) for i in range(2)]}
    # 6. the hardware ceiling over the rail voltage and the tyre diameter (the coordinator's item 1), and the firmware's
    #    set speed; ARM release (item 2): a dropped ball meeting coasting or braked wheels
    res['ceiling_map'] = ceiling_map(balls[:60] if quick else balls[:150])
    res['exit_vs_wheel_speed'] = exit_vs_wheel_speed(nominal, L, w_set)
    res['arm_release'] = arm_release(nominal, L, w_set)
    res['arm_release']['note'] = ('the wheels at the set speed when ARM opens; a ball already past the dial reaches the nip 0.1-0.3 s later (the feed stage\'s latency); '
                                  'coast: friction only (time constant I / (kt i0 / w0) ~ 2 s); brake: AM32 dynamic braking at the given phase current')
    res['validation_nuaa_mismatch'] = validate_nuaa_mismatch()
    # 7. the plan's V13 / V14: the converter bypassed, the chronograph gates, the phase-short release window, the stray ball on re-arm,
    #    and the ceiling with the 200 ms ramp active (it cannot raise it: the ramp ends at the same set speed)
    res['fault_input_on_the_esc'] = fault_input(balls[:60], L)
    res['chronograph'] = chronograph(Gc)
    res['release_phase_short'] = release_window(nominal, L, w_set)
    res['stray_ball_rearm'] = stray_ball_rearm(nominal, L, w_set)
    rr = launch3d(balls[:60], L, Entry(z=0.0, wy=0.0), Wheels(w_set=(w_set, w_set), ramp_s=0.2, t_offset=0.2))   # at the ramp's end the wheels are at the set speed
    res['ramp_active_at_set_speed'] = {'fps_max': round(float(rr['fps'][~rr['rejected']].max()), 2), 'note': 'the first ball fired as the 200 ms ramp ends: the same set speed, so the same ceiling'}
    (OUT / 'launch3d.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    # plots
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), dpi=130)
    ok = ~real['rejected']
    ax[0].hist(base['fps'][~base['rejected']], bins=30, alpha=0.6, label='centred, true tyres')
    ax[0].hist(real['fps'][ok], bins=30, alpha=0.6, label='feed offsets + 0.15 mm runout')
    ax[0].hist(ceil['fps'][~ceil['rejected']], bins=30, alpha=0.6, label='100 % throttle, trimmed rail, magnets +15 C, rail +2 %')
    ax[0].axvline(CAP_FPS, color='k', lw=1.5)
    ax[0].set_xlabel('muzzle speed at the nip exit (fps)')
    ax[0].set_title(f'{n} accepted balls, Ø{D["wheel_d_mm"]:.0f} tyres, crush {int(D["crush"] * 100)} %, {D["supply_v"]:.2f} V (trimmed)', fontsize=9)
    ax[0].legend(fontsize=7)
    ax[1].scatter(real['yaw_mrad'][ok], real['pitch_mrad'][ok], s=6, alpha=0.6, label='0.15 mm runout')
    ax[1].scatter(worn['yaw_mrad'][~worn['rejected']], worn['pitch_mrad'][~worn['rejected']], s=6, alpha=0.4, label='0.30 mm runout')
    ax[1].set_xlabel('yaw at the nip exit (mrad)')
    ax[1].set_ylabel('pitch (mrad)')
    ax[1].set_title('the launch\'s own dispersion (before the barrel)', fontsize=9)
    ax[1].legend(fontsize=7)
    ax[1].grid(alpha=0.3)
    tt, xx, vv, w1, w2, sz = zip(*trace)
    ax[2].plot(np.array(tt) * 1000, np.array(vv) / FPS, label='ball (fps)')
    ax[2].plot(np.array(tt) * 1000, np.array(w1) * L.wheel_d_mm / 2000 / FPS, label='+y tyre surface (fps)')
    ax[2].plot(np.array(tt) * 1000, np.array(w2) * L.wheel_d_mm / 2000 / FPS, '--', label='-y tyre surface (fps)')
    ax[2].set_xlabel('ms from first touch')
    ax[2].set_title('nominal shot, both wheels at the set speed', fontsize=9)
    ax[2].legend(fontsize=7)
    ax[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / 'launch3d.png')
    plt.close(fig)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    r = study(quick=a.quick)
    print(json.dumps({k: r[k] for k in ('handover_1d', 'population_set_speed', 'ceiling', 'mismatch', 'bursts', 'recoil')}, indent=1))
