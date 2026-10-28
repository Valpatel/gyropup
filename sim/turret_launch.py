"""How fast a Rival ball leaves the turret's twin flywheels, and what holds it at or under 105 fps (D68).

    .venv/bin/python sim/turret_launch.py            # the study: writes exports/turret/launch/launch.json and plots

The model (one shot, 1 us steps). Two equal wheels of radius R spin in opposite directions about vertical axes c apart
(cad/turret.py: the ball path on the line between them). The ball, radius r and mass m, arrives from the chute at
v_in and is squeezed in the gap c - 2R < 2r. On each side:
  - the overlap delta = R + r - |ball centre - wheel centre| is taken by the foam (the TPU 95A tyre is ~30 times
    stiffer than the ball's foam and is treated as rigid);
  - the normal force is a Hertz law for the foam sphere on the tyre, F = 4/3 E* sqrt(R_eff) delta^1.5 (E* = E/(1-nu^2),
    R_eff from the ball's and the tyre's curvatures), with Hunt-Crossley damping chosen so that a ball bounced at
    3 m/s on a hard floor comes back at the measured coefficient of restitution e;
  - friction along the tyre's surface is Coulomb with coefficient mu (regularised over 0.05 m/s of slip), pulling the
    ball forward while the tyre moves faster than the ball and holding it back once the ball is the faster;
  - the normal force pushes the ball back on the way in and forward on the way out.
The two sides are symmetric, so the ball does not spin. Each wheel (the motor's rotor, the printed hub and the tyre)
is driven by its motor through an ESC: duty 0..1 of the supply V on the motor's back-EMF, phase-to-phase resistance,
a current limit, the motor's own friction; a PI loop holds the set speed, or the duty is 1 (100 % throttle: the
hardware ceiling). The shot ends when the ball loses both contacts; its speed then is the muzzle speed (the barrel
and the air take a little more off over the next 0.1 m; that is ignored, which is the conservative side).

Two regimes follow from Coulomb friction. With too little crush the ball slips on the tyre all the way through the
nip and leaves at a speed set by the grip (mu times the squeeze, integrated along the path), whatever the wheel speed;
with enough crush it catches the tyre and leaves at about the tyre's surface speed. D68's target (a Hasbro Rival
round at 95-100 fps, every accepted ball at or under 105) needs the second regime for the typical ball, and the
ceiling is then the tyre's surface speed at the rail's no-load speed: the stiff, grippy, light corner ball leaves at
0.97-0.98 of it, whatever its foam.

Everything the model needs is in BALLS, MOTOR, WHEEL and the study's sweeps, each with its source; the foam's
stiffness and the tyre-foam friction are not published for Rival balls, so they are swept over a wide range and the
design is chosen to hold the ceiling at the worst corner of it.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'turret' / 'launch'
FPS = 0.3048
CAP_FPS = 105.0                              # D68: no accepted ball may leave faster (0.94 J for a 1.6 g ball)
CAP = CAP_FPS * FPS                          # 32.004 m/s
TARGET_FPS = (95.0, 100.0)                   # D68: a Hasbro Rival round at full throttle (Nemesis 94-101, Prometheus 100)

# The flywheel motor (D68; D42 had the 880 KV of the same motor): SunnySky X2216 1400KV V3, short shaft. The same can,
# stator, shaft, prop adapter and 72 g as the 880 KV (SunnySky's table, en.rcsunnysky.com X2216 page, read 2026-10-27):
# 1400 rpm/V, kt = 60 / (2 pi KV); 55 mOhm between two leads (two phases in series, so r_phase is half of it); 1.3 A at
# no load at 10 V (14,000 rpm); rated 2-4S, 33 A for 30 s, 540 W. The rotor's inertia is not published: est 4.8 kg mm^2
# (+-30 %) from the drawing (the steel can Ø27.7 x 0.8 x 24.5, 13.4 g at r 13.45; 14 magnets ~15 g at r 12; the end cap),
# the same for every KV of this can.
MOTOR = {'name': 'SunnySky X2216 1400KV V3', 'kv_rpm_v': 1400.0, 'kt': 60.0 / (2 * math.pi * 1400.0), 'r_phase': 0.0275, 'rotor_kg_m2': 4.8e-6,
         'i0_a': 1.3, 'i0_at_rpm': 14000.0, 'pole_pairs': 7}
# the X2216 short-shaft variants SunnySky USA sells (sunnyskyusa.com/products/sunnysky-x2216, $24.99 each, read
# 2026-10-27; 950 and 2600 KV are also listed) with SunnySky's table: ohm between leads, no-load A at 10 V; all 2-4S
X2216_KV = {880: (0.117, 0.5), 1100: (0.073, 0.85), 1250: (0.063, 1.05), 1400: (0.055, 1.3)}
MOTOR_RATED_V = 16.8                          # 4S full: the top of every X2216's rating


def motor_for(kv):
    """MOTOR's dict for another X2216 KV (the route comparison)."""
    r_ll, i0 = X2216_KV[kv]
    return {**MOTOR, 'name': f'SunnySky X2216 {kv}KV V3', 'kv_rpm_v': float(kv), 'kt': 60.0 / (2 * math.pi * kv), 'r_phase': r_ll / 2,
            'i0_a': i0, 'i0_at_rpm': 10.0 * kv}


@dataclass
class Ball:
    name: str
    d_mm: float = 22.7
    m_g: float = 1.83
    E_mpa: float = 1.0            # the foam's effective Young's modulus (swept)
    nu: float = 0.2
    e: float = 0.6                # coefficient of restitution at 3 m/s on a hard floor (swept)
    mu: float = 0.8               # TPU-foam friction (swept)


@dataclass
class Launcher:
    wheel_d_mm: float = 40.0
    gap_mm: float = 19.98         # c - 2R: cad/turret.py crushes the 22.7 mm ball 12 % (to 19.98 mm)
    crown_r_mm: float = 1e3       # the tyre's crown radius across its width (flat tyre: large)
    supply_v: float = 12.0
    r_eff_ohm: float = 2 * MOTOR['r_phase']   # two phases conduct (AM32 drives trapezoidally)
    i_max_a: float = 10.0         # the ESC's current limit (set in AM32)
    wheel_I: float = 4.6e-6       # rotor + hub + tyre about the axis (kg m^2): from cad/turret.py's parts
    kp: float = 2e-3              # speed loop: A per rad/s ...
    ki: float = 0.5               # ... and A per rad
    v_in: float = 0.5             # m/s: the ball arrives from the chute (sim/turret_feed.py)


def no_load_speed(L: Launcher, kv_scale=1.0, v_scale=1.0):
    """rad/s at 100 % duty: back-EMF + friction balance the supply."""
    ke = 60.0 / (2 * math.pi * MOTOR['kv_rpm_v'] * kv_scale)
    w0 = L.supply_v * v_scale / ke
    # friction from the no-load current (0.4 A at 21000 rpm, taken proportional to speed)
    tf_per_w = MOTOR['kt'] * MOTOR['i0_a'] / (MOTOR['i0_at_rpm'] * 2 * math.pi / 60)
    # V - ke w = R i, kt i = tf_per_w w  ->  w = V / (ke + R tf_per_w / kt)
    return L.supply_v * v_scale / (ke + L.r_eff_ohm * tf_per_w / MOTOR['kt'])


def shot(ball: Ball, L: Launcher, w_set=None, full_throttle=False, kv_scale=1.0, v_scale=1.0, dt=1e-6, record=False):
    """One shot. w_set: the wheels' speed (rad/s) when the ball arrives (they start there); full_throttle: duty held at
    1 (the hardware ceiling) and the wheels start at their no-load speed. Returns a dict."""
    m = ball.m_g / 1000
    r = ball.d_mm / 2000
    Rw = L.wheel_d_mm / 2000
    c = (L.wheel_d_mm + L.gap_mm) / 1000
    Es = ball.E_mpa * 1e6 / (1 - ball.nu ** 2)
    # sphere on a tyre: curvature radii r (ball) with Rw in the plane, and r with the crown across it
    R1 = 1 / (1 / r + 1 / Rw)
    R2 = 1 / (1 / r + 1 / (L.crown_r_mm / 1000))
    Reff = math.sqrt(R1 * R2)
    K = 4.0 / 3.0 * Es * math.sqrt(Reff)
    # Hunt-Crossley alpha for restitution e at 3 m/s (alpha ~ 3(1-e)/(2 v))
    alpha = 3 * (1 - ball.e) / (2 * 3.0)
    ke = 60.0 / (2 * math.pi * MOTOR['kv_rpm_v'] * kv_scale)
    kt = MOTOR['kt'] / kv_scale
    tf_per_w = MOTOR['kt'] * MOTOR['i0_a'] / (MOTOR['i0_at_rpm'] * 2 * math.pi / 60)
    V = L.supply_v * v_scale
    w0 = no_load_speed(L, kv_scale, v_scale)
    w = w0 if full_throttle else w_set
    target = w0 if full_throttle else w_set
    # the ball starts just touching the tyres
    x = -math.sqrt(max(0.0, (Rw + r) ** 2 - (c / 2) ** 2)) - 1e-5
    v = L.v_in
    integ = 0.0
    t = 0.0
    peak_fn = peak_ft = 0.0
    impulse = 0.0
    slip_e = 0.0                                   # energy lost to slip (J)
    touched = False
    rec = [] if record else None
    for _ in range(200000):
        D = math.hypot(x, c / 2)
        delta = Rw + r - D
        if delta > 0:
            touched = True
            nx = x / D
            tx = (c / 2) / D
            vn = -v * nx                           # the overlap's growth rate (ball moving into the wheel)
            Fn = K * delta ** 1.5 * (1 + alpha * vn)
            Fn = max(Fn, 0.0)
            vs = w * (Rw - 0 * delta) - v * tx     # tyre surface minus ball, along the tangent
            Ft = ball.mu * Fn * math.tanh(vs / 0.05)
            Fx = 2 * (Fn * nx + Ft * tx)
            tau_load = Ft * Rw
            slip_e += abs(Ft * vs) * 2 * dt
            peak_fn, peak_ft = max(peak_fn, Fn), max(peak_ft, abs(Ft))
        else:
            if touched and x > 0:
                break
            Fx = 0.0
            tau_load = 0.0
        # the motor: PI speed loop on the current, limited; or full duty
        if full_throttle:
            duty = 1.0
            i = (V * duty - ke * w) / L.r_eff_ohm
            i = min(i, L.i_max_a)
        else:
            err = target - w
            integ += err * dt
            i_cmd = L.kp * err * 1000 + L.ki * integ * 1000
            i_cmd = max(-L.i_max_a, min(L.i_max_a, i_cmd))
            i_avail = (V - ke * w) / L.r_eff_ohm  # the most the supply can push at this speed
            i = min(i_cmd, i_avail)
        tau = kt * i - tf_per_w * w
        w += (tau - tau_load) / L.wheel_I * dt
        a = Fx / m
        v += a * dt
        x += v * dt
        impulse += Fx * dt
        t += dt
        if rec is not None and int(t / dt) % 20 == 0:
            rec.append((t, x, v, w, delta if delta > 0 else 0.0))
    out = {'v_exit': v, 'fps': v / FPS, 'contact_ms': t * 1000, 'w_start': (w0 if full_throttle else w_set), 'w_end': w,
           'surface_m_s': (w0 if full_throttle else w_set) * Rw, 'eta': v / ((w0 if full_throttle else w_set) * Rw),
           'speed_drop_pct': 100 * (1 - w / (w0 if full_throttle else w_set)), 'peak_normal_n': peak_fn, 'peak_friction_n': peak_ft,
           'impulse_ns': impulse, 'slip_loss_j': slip_e, 'ball_ke_j': 0.5 * m * v ** 2}
    if rec is not None:
        out['trace'] = rec
    return out


def set_speed_for(ball, L, v_target, kv_scale=1.0, v_scale=1.0):
    """The wheel speed (rad/s) that gives v_target, by bisection, or None if even the no-load speed falls short."""
    w0 = no_load_speed(L, kv_scale, v_scale)
    if shot(ball, L, w0 * 0.999, kv_scale=kv_scale, v_scale=v_scale)['v_exit'] < v_target:
        return None
    lo, hi = 0.2 * w0, w0 * 0.999
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if shot(ball, L, mid, kv_scale=kv_scale, v_scale=v_scale)['v_exit'] < v_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ------------------------------------------------------------------------------------------------ the study

# The accepted ammo (D67): Hasbro Nerf Rival rounds and off-brand Rival-compatible rounds of 22.2-22.8 mm and 1.6-2.0 g
# (the design ball: 22.7 mm, 1.83 g, Hasbro's average measured mass). Foam stiffness, restitution and tyre friction are
# not published: swept (bands as sim/turret_ball.py RANGES).
BALL_D = (22.2, 22.8)
BALL_M = (1.6, 2.0)
BALL_E = (0.75, 3.0)            # MPa, the foam's effective modulus (Hertz fit; Hasbro's '1.5-2.1 kg' hardness brackets it)
BALL_MU = (0.6, 1.0)            # TPU 95A on foam
BALL_RESTITUTION = (0.45, 0.75)
REAL_ETA = (0.40, 0.75)         # ball speed / wheel surface speed measured on Rival flywheel blasters (hobby builds, Hasbro)
HASBRO = Ball('Hasbro Rival', 22.7, 1.83, 1.2, 0.2, 0.6, 0.8)   # the design ball (D67) with sim/turret_ball.py's nominal foam
# D68 sizing (cad/turret.py Geo): Ø38 tyres crushing the 22.7 mm ball 40 %, so the motors' axes are 38 + 22.7 x 0.6 =
# 51.62 mm apart and the cage stays as wide as it was (Ø36 at 25 % had them 53.0 apart: the same outer width within 0.3 mm)
CAGE_C_MM = 38.0 + 22.7 * (1 - 0.40)


def corners():
    """Every corner of the accepted range (D67) and the swept foam: the ceiling's balls (32)."""
    return [Ball(f'd{d:g}-m{m:g}-E{E:g}-mu{mu:g}-e{e:g}', d, m, E, 0.2, e, mu)
            for d in BALL_D for m in BALL_M for E in BALL_E for mu in BALL_MU for e in BALL_RESTITUTION]


# The tolerance stack on the ceiling (D68). The flywheel rail is a TDK-Lambda i6A4W020A033V buck (catalog
# tdk-lambda-i6a4w020a033v-001-r) whose output is set by one fixed resistor, chosen per turret at the bench so that the
# faster motor's no-load speed at 100 % throttle is N_TRIM (docs/turret-plan.md 2.10, bench test 4.1): the motor's KV
# spread and the converter's +-4 % set-point tolerance are measured out. What remains:
#   kv: +1.8 %   the magnets 15 C warmer than at the trim (NdFeB Br -0.12 %/C: a warm motor turns faster); the trim is
#                done after a 3 minute spin, so 15 C is a 20 C trim used at 35 C ambient
#   v : +2.0 %   the rail's drift after the trim: line 0.3 % (15-42 V in) + load 0.6 % (half the 1.2 % for 0-20 A) +
#                temperature 0.6 % (est 0.02 %/C over 30 C), and the eRPM telemetry's reading at the trim, 0.5 %
# and, untrimmed (a fixed set point, the stack D41's 12 V design used): the KV +5 % (SunnySky gives no tolerance: est)
# and the converter's +4 % set point.
TOL = {'kv': 1.018, 'v': 1.020, 'note': 'trimmed per turret: the magnets +15 C (KV +1.8 %), the rail +2.0 % (line, load, temperature, the eRPM reading)'}
TOL_UNTRIMMED = {'kv': 1.05 * 1.018, 'v': 1.04, 'note': 'a fixed set point: KV +5 % (est) and +1.8 % warm, the converter +4 %'}
CEIL_AIM_FPS = 104.0            # the trim aims the worst corner here: 1 fps under the ceiling for the 3D model's runout
# D68 cites ASTM F963's 2500 J/m^2 (kinetic energy over the ball's cross-section). For the design ball that is 109 fps,
# but D67 accepts a 2.0 g ball as small as 22.2 mm, which reaches it at 102.1 fps: at the 104 fps trim that corner (stiff,
# grippy) leaves at 102.8 fps with 2540 J/m^2. So the trim also aims the densest accepted ball 1 % under ASTM's limit,
# which binds first (the fastest ball then leaves at ~102.6, the Hasbro ball at ~97)
ASTM_KED = 2500.0               # J/m^2, ASTM F963 4.21.2.3 / 8.14.6 (sim/turret_target.py LIMITS)
KED_AIM = 2475.0
# RAIL_V_TRIM: the rail that gives a nominal 1400 KV motor the trim speed (each turret's own rail is RAIL_V_TRIM / its
# measured KV ratio); set from trim_rail() (study 'trim')
RAIL_V_TRIM = 11.31
DESIGN = {'wheel_d_mm': 38.0, 'crush': 0.40, 'supply_v': RAIL_V_TRIM, 'set_fps': 95.0, 'nominal': HASBRO}


def cage_crush(wheel_d, ball_d=22.7):
    """The crush a tyre of this diameter gives on this cage (the axes CAGE_C_MM apart)."""
    return 1 - (CAGE_C_MM - wheel_d) / ball_d


def launcher_for(wheel_d, crush, ball_d=22.7, supply_v=None, wheel_I=None):
    gap = ball_d * (1 - crush)
    I = wheel_I if wheel_I is not None else wheel_inertia(wheel_d)
    return Launcher(wheel_d_mm=wheel_d, gap_mm=gap, supply_v=RAIL_V_TRIM if supply_v is None else supply_v, wheel_I=I,
                    r_eff_ohm=2 * MOTOR['r_phase'])


TYRE_T = 4.0                    # mm of TPU 95A on the printed hub's rim (cad/turret.py Geo.tyre_t)


def wheel_inertia(wheel_d):
    """The motor's rotor (MOTOR) + its bolt-on prop adapter, washer and nut (aluminium flange Ø17 and steel, ~4 g inside
    r 8.5: 0.13 kg mm^2, est) + the printed PA6-CF hub (cad/turret.py flywheel: a rim 3 mm thick and 12 wide under the
    tyre and a web 5.5 thick, 1.09 g/cm^3) + the TPU tyre (TYRE_T thick, 12 mm wide, 1.22 g/cm^3)."""
    rt = wheel_d / 2000
    ri = rt - TYRE_T / 1000
    m_t = 1.22e3 * math.pi * (rt ** 2 - ri ** 2) * 0.012
    I_t = 0.5 * m_t * (rt ** 2 + ri ** 2)
    r_o, r_i = ri, ri - 0.003
    r_w = r_i + 0.0001
    m_rim = 1.09e3 * math.pi * (r_o ** 2 - r_i ** 2) * 0.012
    m_web = 1.09e3 * math.pi * r_w ** 2 * 0.0055
    I_h = 0.5 * m_rim * (r_o ** 2 + r_i ** 2) + 0.5 * m_web * r_w ** 2
    return MOTOR['rotor_kg_m2'] + 0.13e-6 + I_h + I_t


def population(n=400, seed=1):
    """Accepted rounds (D67): size uniform over the range, mass about Hasbro's 1.83 g (SD 0.1) clipped to the range,
    the foam swept."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        d = rng.uniform(*BALL_D)
        m = float(np.clip(rng.normal(1.83, 0.10), *BALL_M))
        E = float(np.exp(rng.uniform(math.log(BALL_E[0]), math.log(BALL_E[1]))))
        mu = rng.uniform(*BALL_MU)
        e = rng.uniform(*BALL_RESTITUTION)
        out.append(Ball(f'b{k}', d, m, E, 0.2, e, mu))
    return out


def ked(ball, v):
    """Kinetic energy over the ball's cross-section (J/m^2) at v m/s: ASTM F963's measure."""
    return 0.5 * ball.m_g / 1000 * v ** 2 / (math.pi * (ball.d_mm / 2000) ** 2)


def worst_corner(L, tol=None, balls=None):
    """The corners at 100 % throttle with the tolerance stack: (the fastest's fps, its name, its peak normal N, the
    highest energy density J/m^2, that ball's name)."""
    tol = tol or TOL
    best, dense = None, None
    for b in balls or corners():
        r = shot(b, L, full_throttle=True, kv_scale=tol['kv'], v_scale=tol['v'])
        if best is None or r['fps'] > best[0]:
            best = (r['fps'], b.name, r['peak_normal_n'])
        k = ked(b, r['v_exit'])
        if dense is None or k > dense[0]:
            dense = (k, b.name)
    return best + dense


def trim_rail(wheel_d=None, crush=None, aim=CEIL_AIM_FPS, tol=None, lo=6.0, hi=24.0, ked_aim=KED_AIM):
    """The rail (nominal KV) at which the worst corner, with the tolerance stack, leaves at `aim` fps or the densest
    reaches `ked_aim` J/m^2, whichever comes first (None: speed only)."""
    wheel_d = wheel_d or DESIGN['wheel_d_mm']
    crush = DESIGN['crush'] if crush is None else crush
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        w = worst_corner(launcher_for(wheel_d, crush, supply_v=mid), tol)
        if w[0] > aim or (ked_aim and w[3] > ked_aim):
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def rpm(w):
    return w * 60 / (2 * math.pi)


def routes(n_trim_rpm):
    """D68's two routes to the same no-load speed: a higher rail on the 880 KV, or a higher-KV X2216 on a lower rail.
    For each KV, the rail that gives n_trim_rpm (the friction's share included) and what it needs."""
    global MOTOR
    keep = MOTOR
    rows = []
    try:
        for kv in sorted(X2216_KV):
            MOTOR = motor_for(kv)
            L = launcher_for(DESIGN['wheel_d_mm'], DESIGN['crush'], supply_v=12.0)
            v = 12.0 * n_trim_rpm / rpm(no_load_speed(L))
            v_hi = v * 1.05                                            # the rail a slow (-5 % KV) motor is trimmed to
            rows.append({'kv': kv, 'rail_v_nominal_motor': round(v, 2), 'rail_v_trim_range': [round(v / 1.05, 2), round(v_hi, 2)],
                         'inside_motor_rating_2_4s': v_hi <= MOTOR_RATED_V, 'buck_from_15v_pack': v_hi <= 13.0,
                         'no_load_a_at_speed_est': round(MOTOR['i0_a'] * n_trim_rpm / MOTOR['i0_at_rpm'], 2)})
    finally:
        MOTOR = keep
    return rows


def study():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    D = DESIGN
    res = {'model': __doc__.split('\n\n')[1], 'motor': MOTOR, 'tolerances': TOL, 'tolerances_untrimmed': TOL_UNTRIMMED, 'cap_fps': CAP_FPS,
           'target_fps': TARGET_FPS, 'ball_ranges': {'d_mm': BALL_D, 'm_g': BALL_M, 'E_mpa': BALL_E, 'mu': BALL_MU, 'restitution': BALL_RESTITUTION},
           'measured_eta_on_rival_blasters': REAL_ETA, 'cage_c_mm': round(CAGE_C_MM, 2)}
    # 1. efficiency against crush, foam and grip at the design tyre and rail: the grip-limited and the wheel-limited regimes
    cal = []
    for crush in (0.25, 0.32, 0.36, 0.40, 0.44):
        for E in (0.75, 1.5, 3.0):
            for mu in (0.6, 0.8, 1.0):
                L = launcher_for(D['wheel_d_mm'], crush)
                r = shot(Ball('c', 22.7, 1.83, E, 0.2, 0.6, mu), L, full_throttle=True)
                cal.append({'crush': crush, 'E_mpa': E, 'mu': mu, 'fps': round(r['fps'], 1), 'eta': round(r['eta'], 3),
                            'rejected': r['v_exit'] < 1.0, 'peak_normal_n': round(r['peak_normal_n'], 1)})
    res['efficiency_map'] = cal
    by_crush = {}
    for c in cal:
        by_crush.setdefault(c['crush'], []).append(c)
    res['efficiency_by_crush'] = {str(k): {'eta_min': min(x['eta'] for x in v), 'eta_max': max(x['eta'] for x in v),
                                           'rejections': sum(x['rejected'] for x in v)} for k, v in by_crush.items()}
    # 2. the crush: the Hasbro ball at 100 % against the worst corner, at the design tyre and trim rail
    cr = []
    for crush in (0.32, 0.36, 0.38, 0.40, 0.42, 0.44):
        L = launcher_for(D['wheel_d_mm'], crush)
        rn = shot(HASBRO, L, full_throttle=True)
        wc = worst_corner(L)
        rs = [shot(b, L, full_throttle=True) for b in corners()]
        cr.append({'crush': crush, 'hasbro_full_throttle_fps': round(rn['fps'], 1), 'hasbro_eta': round(rn['eta'], 3),
                   'worst_corner_fps': round(wc[0], 1), 'worst_corner_ball': wc[1], 'worst_over_hasbro': round(wc[0] / rn['fps'], 4),
                   'slowest_corner_fps': round(min(r['fps'] for r in rs), 1), 'stuck_corners': sum(r['v_exit'] < 1.0 for r in rs),
                   'hasbro_peak_normal_n': round(rn['peak_normal_n'], 1), 'worst_peak_normal_n': round(max(r['peak_normal_n'] for r in rs), 1)})
    res['crush_choice'] = cr
    # 3. the trim: the rail for the ceiling aim, and the same with a fixed (untrimmed) set point
    v_trim = trim_rail()
    v_speed = trim_rail(ked_aim=None)
    wc_speed = worst_corner(launcher_for(D['wheel_d_mm'], D['crush'], supply_v=v_speed))
    L = launcher_for(D['wheel_d_mm'], D['crush'], supply_v=v_trim)
    w_trim = no_load_speed(L)
    rn = shot(HASBRO, L, full_throttle=True)
    wc = worst_corner(L)
    v_fix = trim_rail(tol=TOL_UNTRIMMED, ked_aim=None)
    rnf = shot(HASBRO, launcher_for(D['wheel_d_mm'], D['crush'], supply_v=v_fix), full_throttle=True)
    lo, hi = 6.0, 24.0                                             # untrimmed: the rail the Hasbro ball needs for 95 fps
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        if shot(HASBRO, launcher_for(D['wheel_d_mm'], D['crush'], supply_v=mid), full_throttle=True)['fps'] < TARGET_FPS[0]:
            lo = mid
        else:
            hi = mid
    v_need = 0.5 * (lo + hi)
    wcf = worst_corner(launcher_for(D['wheel_d_mm'], D['crush'], supply_v=v_need), TOL_UNTRIMMED)
    res['trim'] = {'rail_v_nominal_motor': round(v_trim, 3), 'rail_v_in_use': RAIL_V_TRIM, 'n_trim_rpm': round(rpm(w_trim)),
                   'n_trim_erpm': round(rpm(w_trim) * MOTOR['pole_pairs']), 'surface_m_s': round(w_trim * D['wheel_d_mm'] / 2000, 2),
                   'rail_v_for_kv_minus5_plus5': [round(v_trim * 1.05, 2), round(v_trim / 1.05, 2)],
                   'hasbro_full_throttle_fps': round(rn['fps'], 1), 'worst_corner_fps': round(wc[0], 2), 'worst_corner_ball': wc[1],
                   'densest_ked_j_m2': round(wc[3]), 'densest_ball': wc[4], 'astm_ked_j_m2': ASTM_KED,
                   'n_105_rpm': round(rpm(w_trim) * TOL['kv'] * TOL['v'] * CAP_FPS / wc[0]),
                   'n_astm_rpm': round(rpm(w_trim) * TOL['kv'] * TOL['v'] * math.sqrt(ASTM_KED / wc[3])),
                   'speed_only_trim': {'rail_v': round(v_speed, 3), 'densest_ked_j_m2': round(wc_speed[3]), 'densest_ball': wc_speed[4],
                                       'hasbro_full_throttle_fps': round(shot(HASBRO, launcher_for(D['wheel_d_mm'], D['crush'], supply_v=v_speed), full_throttle=True)['fps'], 1)},
                   'note': 'n_105 / n_astm: the no-load speeds at which the worst corner reaches 105 fps / the densest reaches 2500 J/m^2 (both scale with the wheel speed)',
                   'untrimmed': {'rail_v_for_104_worst': round(v_fix, 3), 'hasbro_fps_then': round(rnf['fps'], 1),
                                 'rail_v_for_hasbro_95': round(v_need, 3), 'worst_corner_fps_then': round(wcf[0], 1),
                                 'verdict': 'impossible: a fixed set point holds the worst corner at 104 only with the Hasbro ball at '
                                            f'{rnf["fps"]:.1f} fps, and 95 fps for the Hasbro ball lets the worst corner reach {wcf[0]:.1f}'}}
    # 4. the two routes: the 880 KV on a higher rail against a higher-KV X2216 on a lower one
    res['routes'] = routes(rpm(w_trim))
    # 5. the ceiling for each tyre on this cage, at the trim rail
    ceil = []
    for wd in (36.0, 38.0, 40.0):
        Lw = launcher_for(wd, cage_crush(wd))
        w = worst_corner(Lw)
        ceil.append({'wheel_d_mm': wd, 'crush_on_this_cage': round(cage_crush(wd), 3), 'worst_fps_at_full_throttle': round(w[0], 1),
                     'hasbro_fps_at_full_throttle': round(shot(HASBRO, Lw, full_throttle=True)['fps'], 1), 'no_load_rpm': round(rpm(no_load_speed(Lw)))})
    res['ceiling_by_wheel'] = ceil
    # 6. the design: the Hasbro ball at the set speed and at 100 %; the population; the worst corner at 100 %
    L = launcher_for(D['wheel_d_mm'], D['crush'])
    w_set = set_speed_for(HASBRO, L, D['set_fps'] * FPS)
    w0 = no_load_speed(L)
    pop = population()
    speeds = [shot(b, L, w_set)['fps'] for b in pop]
    full = [shot(b, L, full_throttle=True, kv_scale=TOL['kv'], v_scale=TOL['v'])['fps'] for b in pop]
    full_nom = [shot(b, L, full_throttle=True)['fps'] for b in pop]
    rn = shot(HASBRO, L, w_set, record=True)
    trace = rn.pop('trace')
    rft = shot(HASBRO, L, full_throttle=True)
    wc = worst_corner(L)
    res['design'] = {
        'wheel_d_mm': D['wheel_d_mm'], 'crush': D['crush'], 'gap_mm_for_22_7': round(22.7 * (1 - D['crush']), 2), 'supply_v': D['supply_v'],
        'wheel_I_kg_m2': L.wheel_I, 'no_load_rpm': round(rpm(w0)), 'set_rpm': round(rpm(w_set)) if w_set else None, 'set_fps': D['set_fps'],
        'set_fraction_of_no_load': round(w_set / w0, 3) if w_set else None,
        'hasbro_full_throttle': {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rft.items()},
        'nominal_shot': {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rn.items()},
        'population_at_set_speed_fps': {'n': len(speeds), 'mean': round(float(np.mean(speeds)), 1), 'sd': round(float(np.std(speeds)), 1),
                                        'p1': round(float(np.percentile(speeds, 1)), 1), 'p99': round(float(np.percentile(speeds, 99)), 1),
                                        'max': round(max(speeds), 1)},
        'population_at_full_throttle_fps': {'mean': round(float(np.mean(full_nom)), 1), 'p1': round(float(np.percentile(full_nom, 1)), 1),
                                            'max': round(max(full_nom), 1), 'max_with_tolerances': round(max(full), 1),
                                            'note': 'every ball at 100 % throttle on the trimmed rail; with tolerances: magnets +15 C, rail +2 %'},
        'worst_corner_full_throttle_fps': round(wc[0], 1), 'worst_corner_ball': wc[1], 'densest_ked_j_m2': round(wc[3]), 'densest_ball': wc[4],
        'margin_fps': round(CAP_FPS - max(max(full), wc[0]), 1),
    }
    # 7. how the speed moves with one property at a time (the Hasbro ball at 100 %)
    sens = {}
    for key, vals in (('d_mm', (22.2, 22.7, 22.8)), ('m_g', (1.6, 1.83, 2.0)), ('E_mpa', (0.75, 1.2, 3.0)), ('mu', (0.6, 0.8, 1.0)), ('e', (0.45, 0.6, 0.75))):
        row = []
        for v in vals:
            b = replace(HASBRO, **{key: v})
            row.append({'value': v, 'fps': round(shot(b, L, full_throttle=True)['fps'], 1)})
        sens[key] = row
    sens['wet'] = {'value': 'soaked: twice the mass (Blaster Labs)', 'fps': round(shot(replace(HASBRO, m_g=3.7), L, full_throttle=True)['fps'], 1)}
    sens['worn_soft'] = {'value': 'worn: 40 % softer', 'fps': round(shot(replace(HASBRO, E_mpa=0.72), L, full_throttle=True)['fps'], 1)}
    res['sensitivity_full_throttle'] = sens
    # 8. a burst: 8 balls at 10/s at the set speed; the wheel's speed sag and recovery on the ESC's 10 A limit
    burst = []
    w = w_set
    for k in range(8):
        r = shot(HASBRO, L, w)
        burst.append({'shot': k + 1, 'w_rpm': round(rpm(w)), 'fps': round(r['fps'], 1)})
        w = recover(L, r['w_end'], w_set, 0.1 - r['contact_ms'] / 1000)
    res['burst_10_per_s'] = burst
    # 9. recoil
    m = HASBRO.m_g / 1000
    v = rft['v_exit']
    res['recoil'] = {'per_shot_ns': round(m * v, 4), 'at_cap_ns': round(BALL_M[1] / 1000 * CAP, 4), 'burst_8_ns': round(8 * m * v, 3),
                     'peak_force_on_the_cage_n': round(2 * rft['peak_normal_n'], 1),
                     'note': 'impulse = the ball momentum at the muzzle (the Hasbro ball at 100 %); the at-cap figure takes the heaviest accepted ball (2.0 g) at 105 fps'}
    (OUT / 'launch.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    # plots
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4), dpi=130)
    xs = [c['crush'] for c in cr]
    ax[0].plot(xs, [c['hasbro_full_throttle_fps'] for c in cr], 'o-', label='Hasbro ball (22.7 mm, 1.83 g)')
    ax[0].plot(xs, [c['worst_corner_fps'] for c in cr], 's-', label='worst accepted corner, with the tolerances')
    ax[0].axhspan(*TARGET_FPS, color='#16a34a', alpha=0.12, label='D68 target 95-100 fps')
    ax[0].axhline(CAP_FPS, color='k', lw=1.2)
    ax[0].set_xlabel('crush (share of the 22.7 mm ball)')
    ax[0].set_ylabel('fps at 100 % throttle')
    ax[0].set_title(f"Ø{D['wheel_d_mm']:.0f} tyres on the trimmed rail ({MOTOR['name']})", fontsize=9)
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    ax[1].hist(full_nom, bins=30, color='#2563eb', alpha=0.75, label='100 % throttle, trimmed rail')
    ax[1].hist(full, bins=30, color='#c2410c', alpha=0.55, label='+ warm magnets, rail drift')
    ax[1].axvline(CAP_FPS, color='k', lw=1.5)
    ax[1].text(CAP_FPS - 0.5, ax[1].get_ylim()[1] * 0.9, '105 fps ceiling', ha='right', fontsize=8)
    ax[1].set_xlabel('muzzle speed (fps)')
    ax[1].set_title(f"{len(pop)} accepted rounds (D67, foam and grip swept): Ø{D['wheel_d_mm']:.0f}, crush {int(D['crush'] * 100)} %", fontsize=9)
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / 'launch.png')
    plt.close(fig)
    t, x, vv, ww, dl = zip(*trace)
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=130)
    ax.plot(np.array(t) * 1000, np.array(vv) / FPS, label='ball (fps)')
    ax.plot(np.array(t) * 1000, np.array(ww) * L.wheel_d_mm / 2000 / FPS, label='tyre surface (fps)')
    ax.plot(np.array(t) * 1000, np.array(dl) * 1e4, label='foam squeeze per side (x0.1 mm)')
    ax.set_xlabel('ms from first touch')
    ax.set_title('One shot through the flywheels (Hasbro ball, set speed)', fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / 'launch-shot.png')
    plt.close(fig)
    return res


def recover(L, w, w_set, seconds, dt=1e-5):
    ke = 60.0 / (2 * math.pi * MOTOR['kv_rpm_v'])
    tf_per_w = MOTOR['kt'] * MOTOR['i0_a'] / (MOTOR['i0_at_rpm'] * 2 * math.pi / 60)
    for _ in range(int(seconds / dt)):
        i = min(L.i_max_a, (L.supply_v - ke * w) / L.r_eff_ohm, max(0.0, (w_set - w) * L.kp * 1000 + 1.0))
        w += (MOTOR['kt'] * i - tf_per_w * w) / L.wheel_I * dt
        w = min(w, w_set * 1.002)
    return w


if __name__ == '__main__':
    r = study()
    print(json.dumps({k: r[k] for k in ('crush_choice', 'trim', 'routes', 'ceiling_by_wheel', 'design', 'sensitivity_full_throttle', 'burst_10_per_s', 'recoil')}, indent=1))
