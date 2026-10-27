"""How fast a Rival ball leaves the turret's twin flywheels, and what holds it at or under 70 fps.

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
The two sides are symmetric, so the ball does not spin. Each wheel (the Snail's rotor, the printed hub and the tyre)
is driven by its motor through an ESC: duty 0..1 of the supply V on the motor's back-EMF, phase-to-phase resistance,
a current limit, the motor's own friction; a PI loop holds the set speed, or the duty is 1 (100 % throttle: the
hardware ceiling). The shot ends when the ball loses both contacts; its speed then is the muzzle speed (the barrel
and the air take a little more off over the next 0.1 m; that is ignored, which is the conservative side).

Everything the model needs is in BALLS, SNAIL, WHEEL and the study's sweeps, each with its source; the foam's
stiffness and the tyre-foam friction are not published for Rival balls, so they are swept over a wide range and the
design is chosen to hold the cap at the worst corner of it.
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
CAP_FPS = 70.0
CAP = CAP_FPS * FPS                          # 21.336 m/s

# DJI RoboMaster Snail 2305 user guide (references/vendor/dji-robomaster-snail-2305)
SNAIL = {'kv_rpm_v': 875.0, 'kt': 0.0109, 'r_phase': 0.1815, 'rotor_kg_m2': 1.84e-6, 'i0_a': 0.4, 'i0_at_rpm': 21000.0}


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
    r_eff_ohm: float = 2 * SNAIL['r_phase']   # two phases conduct (AM32 drives trapezoidally)
    i_max_a: float = 10.0         # the ESC's current limit (set in AM32)
    wheel_I: float = 4.6e-6       # rotor + hub + tyre about the axis (kg m^2): from cad/turret.py's parts
    kp: float = 2e-3              # speed loop: A per rad/s ...
    ki: float = 0.5               # ... and A per rad
    v_in: float = 0.5             # m/s: the ball arrives from the chute (sim/turret_feed.py)


def no_load_speed(L: Launcher, kv_scale=1.0, v_scale=1.0):
    """rad/s at 100 % duty: back-EMF + friction balance the supply."""
    ke = 60.0 / (2 * math.pi * SNAIL['kv_rpm_v'] * kv_scale)
    w0 = L.supply_v * v_scale / ke
    # friction from the no-load current (0.4 A at 21000 rpm, taken proportional to speed)
    tf_per_w = SNAIL['kt'] * SNAIL['i0_a'] / (SNAIL['i0_at_rpm'] * 2 * math.pi / 60)
    # V - ke w = R i, kt i = tf_per_w w  ->  w = V / (ke + R tf_per_w / kt)
    return L.supply_v * v_scale / (ke + L.r_eff_ohm * tf_per_w / SNAIL['kt'])


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
    ke = 60.0 / (2 * math.pi * SNAIL['kv_rpm_v'] * kv_scale)
    kt = SNAIL['kt'] / kv_scale
    tf_per_w = SNAIL['kt'] * SNAIL['i0_a'] / (SNAIL['i0_at_rpm'] * 2 * math.pi / 60)
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

# Rival-size rounds on sale (research, 2026-10-27; sources in exports/turret/launch/launch.json 'ball_sources'):
# Hasbro 22.5-23.5 mm (patent US10648765B2), 22.9 mm measured; Worker Cheetah 22.7 mm, 1.75 g; Dart Zone Powerstrike
# 22.8 mm, 1.85 g; Hasbro mass 1.85 g mean, SD 0.13-0.16, 1.53-2.10 g (Blaster Labs, n = 18 and 12); rebound about
# half the impact speed (Blaster Labs). Foam stiffness and tyre friction are not published: swept.
BALL_D = (22.5, 23.5)
BALL_M = (1.53, 2.10)
BALL_E = (0.75, 3.0)            # MPa, the foam's effective modulus (Hertz fit; Hasbro's '1.5-2.1 kg' hardness brackets it)
BALL_MU = (0.6, 1.0)            # TPU 95A on foam
REAL_ETA = (0.40, 0.75)         # ball speed / wheel surface speed measured on Rival flywheel blasters (hobby builds, Hasbro)
DESIGN = {'wheel_d_mm': 36.0, 'crush': 0.25, 'supply_v': 12.0, 'set_fps': 55.0, 'nominal': Ball('nominal Rival', 22.9, 1.85, 1.5, 0.2, 0.5, 0.8)}
TOL = {'kv': 1.05, 'v': 1.04, 'note': 'motor KV +5 % (DJI gives no tolerance: est), the Pololu regulator +4 % (est from its data sheet class)'}


def launcher_for(wheel_d, crush, ball_d=22.7, supply_v=12.0, wheel_I=None):
    gap = ball_d * (1 - crush)
    I = wheel_I if wheel_I is not None else wheel_inertia(wheel_d)
    return Launcher(wheel_d_mm=wheel_d, gap_mm=gap, supply_v=supply_v, wheel_I=I)


TYRE_T = 4.0                    # mm of TPU 95A on the printed hub's rim (cad/turret.py Geo.tyre_t)


def wheel_inertia(wheel_d):
    """The Snail's rotor (DJI: 1.84 kg mm^2) + the printed PA6-CF hub (its rim 3 mm under the tyre, ~7 g, cad/turret.py)
    + the TPU tyre (TYRE_T thick, 12 mm wide, 1.22 g/cm^3)."""
    rt = wheel_d / 2000
    ri = rt - TYRE_T / 1000
    m_t = 1.22e3 * math.pi * (rt ** 2 - ri ** 2) * 0.012
    I_t = 0.5 * m_t * (rt ** 2 + ri ** 2)
    I_h = 0.5 * 0.007 * (ri - 0.0015) ** 2               # the hub: most of its mass in the rim
    return SNAIL['rotor_kg_m2'] + I_h + I_t


def population(n=400, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        d = rng.uniform(*BALL_D)
        m = float(np.clip(rng.normal(1.85, 0.15), *BALL_M))
        E = float(np.exp(rng.uniform(math.log(BALL_E[0]), math.log(BALL_E[1]))))
        mu = rng.uniform(*BALL_MU)
        out.append(Ball(f'b{k}', d, m, E, 0.2, 0.5, mu))
    return out


def study():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    res = {'model': __doc__.split('\n\n')[1], 'snail': SNAIL, 'tolerances': TOL, 'cap_fps': CAP_FPS,
           'ball_ranges': {'d_mm': BALL_D, 'm_g': BALL_M, 'E_mpa': BALL_E, 'mu': BALL_MU, 'restitution': 0.5},
           'measured_eta_on_rival_blasters': REAL_ETA}
    # 1. efficiency against crush, foam and grip (the 12 V, Ø40 wheel the CAD first had)
    cal = []
    for crush in (0.12, 0.18, 0.25, 0.32, 0.40):
        for E in (0.75, 1.5, 3.0):
            for mu in (0.6, 0.8, 1.0):
                L = launcher_for(40.0, crush)
                r = shot(Ball('c', 22.7, 1.85, E, 0.2, 0.5, mu), L, full_throttle=True)
                cal.append({'crush': crush, 'E_mpa': E, 'mu': mu, 'fps': round(r['fps'], 1), 'eta': round(r['eta'], 3),
                            'rejected': r['v_exit'] < 1.0, 'peak_normal_n': round(r['peak_normal_n'], 1)})
    res['efficiency_map'] = cal
    by_crush = {}
    for c in cal:
        by_crush.setdefault(c['crush'], []).append(c)
    res['efficiency_by_crush'] = {str(k): {'eta_min': min(x['eta'] for x in v), 'eta_max': max(x['eta'] for x in v),
                                           'rejections': sum(x['rejected'] for x in v)} for k, v in by_crush.items()}
    # 2. the hardware ceiling for each wheel size at 100 % throttle: the worst ball (largest, lightest, stiffest, grippiest)
    #    on a fast motor and a high regulator
    worst = Ball('worst', BALL_D[1], BALL_M[0], BALL_E[1], 0.2, 0.5, BALL_MU[1])
    ceil = []
    for wd in (34.0, 36.0, 38.0, 40.0, 42.0):
        L = launcher_for(wd, DESIGN['crush'], ball_d=22.7)
        r = shot(worst, L, full_throttle=True, kv_scale=TOL['kv'], v_scale=TOL['v'])
        rn = shot(DESIGN['nominal'], L, full_throttle=True)
        ceil.append({'wheel_d_mm': wd, 'worst_fps_at_full_throttle': round(r['fps'], 1), 'nominal_fps_at_full_throttle': round(rn['fps'], 1),
                     'no_load_rpm': round(no_load_speed(L) * 60 / (2 * math.pi))})
    res['ceiling_by_wheel'] = ceil
    # 3. the design: set speed for the nominal ball at set_fps; the population at that speed; the worst case at 100 %
    D = DESIGN
    L = launcher_for(D['wheel_d_mm'], D['crush'])
    w_set = set_speed_for(D['nominal'], L, D['set_fps'] * FPS)
    w0 = no_load_speed(L)
    pop = population()
    speeds = [shot(b, L, w_set)['fps'] for b in pop]
    full = [shot(b, L, full_throttle=True, kv_scale=TOL['kv'], v_scale=TOL['v'])['fps'] for b in pop]
    rn = shot(D['nominal'], L, w_set, record=True)
    trace = rn.pop('trace')
    wc = shot(worst, L, full_throttle=True, kv_scale=TOL['kv'], v_scale=TOL['v'])
    res['design'] = {
        'wheel_d_mm': D['wheel_d_mm'], 'crush': D['crush'], 'gap_mm_for_22_7': round(22.7 * (1 - D['crush']), 2), 'supply_v': D['supply_v'],
        'wheel_I_kg_m2': L.wheel_I, 'no_load_rpm': round(w0 * 60 / (2 * math.pi)), 'set_rpm': round(w_set * 60 / (2 * math.pi)),
        'set_fraction_of_no_load': round(w_set / w0, 3),
        'nominal_shot': {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rn.items()},
        'population_at_set_speed_fps': {'n': len(speeds), 'mean': round(float(np.mean(speeds)), 1), 'sd': round(float(np.std(speeds)), 1),
                                        'p1': round(float(np.percentile(speeds, 1)), 1), 'p99': round(float(np.percentile(speeds, 99)), 1),
                                        'max': round(max(speeds), 1)},
        'population_at_full_throttle_fps': {'mean': round(float(np.mean(full)), 1), 'max': round(max(full), 1),
                                            'note': 'every ball at 100 % throttle on a +5 % motor and a +4 % regulator: the hardware ceiling'},
        'worst_ball_full_throttle_fps': round(wc['fps'], 1),
        'margin_fps': round(CAP_FPS - max(max(full), wc['fps']), 1),
    }
    # 4. how the speed moves with one property at a time (the nominal ball at the set speed)
    sens = {}
    for key, vals in (('d_mm', (22.5, 22.9, 23.5)), ('m_g', (1.53, 1.85, 2.10)), ('E_mpa', (0.75, 1.5, 3.0)), ('mu', (0.6, 0.8, 1.0))):
        row = []
        for v in vals:
            b = replace(D['nominal'], **{key: v})
            row.append({'value': v, 'fps': round(shot(b, L, w_set)['fps'], 1)})
        sens[key] = row
    sens['wet'] = {'value': 'soaked: twice the mass (Blaster Labs)', 'fps': round(shot(replace(D['nominal'], m_g=3.7), L, w_set)['fps'], 1)}
    sens['worn_soft'] = {'value': 'worn: half the stiffness', 'fps': round(shot(replace(D['nominal'], E_mpa=0.75), L, w_set)['fps'], 1)}
    res['sensitivity'] = sens
    # 5. a burst: 8 balls at 10/s; the wheel's speed sag and recovery on the ESC's 10 A limit
    burst = []
    w = w_set
    for k in range(8):
        r = shot(D['nominal'], L, w)
        burst.append({'shot': k + 1, 'w_rpm': round(w * 60 / (2 * math.pi)), 'fps': round(r['fps'], 1)})
        # recover over the 0.1 s to the next ball: the PI loop at the current limit
        w = recover(L, r['w_end'], w_set, 0.1 - r['contact_ms'] / 1000)
    res['burst_10_per_s'] = burst
    # 6. recoil
    m = D['nominal'].m_g / 1000
    v = rn['v_exit']
    res['recoil'] = {'per_shot_ns': round(m * v, 4), 'at_cap_ns': round(0.0021 * CAP, 4), 'burst_8_ns': round(8 * m * v, 3),
                     'peak_force_on_the_cage_n': round(2 * rn['peak_normal_n'], 1),
                     'note': 'impulse = the ball momentum at the muzzle; the at-cap figure takes the heaviest ball (2.10 g) at 70 fps'}
    (OUT / 'launch.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    # plots
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4), dpi=130)
    for crush in (0.12, 0.25, 0.40):
        xs = [c for c in cal if c['crush'] == crush]
        ax[0].scatter([c['E_mpa'] * (1 + 0.04 * (c['mu'] - 0.8) / 0.2) for c in xs], [c['eta'] for c in xs], label=f'crush {int(crush * 100)} %', s=18)
    ax[0].axhspan(*REAL_ETA, color='#64748b', alpha=0.12, label='measured on Rival blasters')
    ax[0].set_xscale('log')
    ax[0].set_xlabel("foam modulus E (MPa; dots spread by friction 0.6-1.0)")
    ax[0].set_ylabel('ball speed / tyre surface speed')
    ax[0].set_title('Launch efficiency at 100 % throttle (Ø40, 12 V)', fontsize=9)
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    ax[1].hist(speeds, bins=30, color='#2563eb', alpha=0.75, label=f"at the set speed ({D['set_fps']:.0f} fps nominal)")
    ax[1].hist(full, bins=30, color='#c2410c', alpha=0.55, label='100 % throttle, fast motor, high rail')
    ax[1].axvline(CAP_FPS, color='k', lw=1.5)
    ax[1].text(CAP_FPS - 0.5, ax[1].get_ylim()[1] * 0.9, '70 fps cap', ha='right', fontsize=8)
    ax[1].set_xlabel('muzzle speed (fps)')
    ax[1].set_title(f"{len(pop)} Rival balls (sourced size/mass spread, foam and grip swept): Ø{D['wheel_d_mm']:.0f}, crush {int(D['crush'] * 100)} %, {D['supply_v']:.0f} V", fontsize=9)
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
    ax.set_title('One shot through the flywheels (nominal ball, set speed)', fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / 'launch-shot.png')
    plt.close(fig)
    return res


def recover(L, w, w_set, seconds, dt=1e-5):
    ke = 60.0 / (2 * math.pi * SNAIL['kv_rpm_v'])
    tf_per_w = SNAIL['kt'] * SNAIL['i0_a'] / (SNAIL['i0_at_rpm'] * 2 * math.pi / 60)
    for _ in range(int(seconds / dt)):
        i = min(L.i_max_a, (L.supply_v - ke * w) / L.r_eff_ohm, max(0.0, (w_set - w) * L.kp * 1000 + 1.0))
        w += (SNAIL['kt'] * i - tf_per_w * w) / L.wheel_I * dt
        w = min(w, w_set * 1.002)
    return w


if __name__ == '__main__':
    r = study()
    print(json.dumps({k: r[k] for k in ('efficiency_by_crush', 'ceiling_by_wheel', 'design', 'sensitivity', 'burst_10_per_s', 'recoil')}, indent=1))
