"""The barrel and the flight: wall contacts in the bore, then drag, Magnus lift and gravity out to 8 m.

    .venv/bin/python sim/turret_flight.py [--quick]    # writes exports/turret/flight/flight.json and plots

Barrel (a reduced model, vectorised over a population, 2 us steps): the ball leaves the nip with the launch stage's
velocity and spin (sim/turret_launch3d.py) in the cartridge frame, 111 mm before the muzzle, inside a bore of
ball + 1.5 mm (cad/turret.py Geo.bore: 0.75 mm of radial play). It flies free until its centre is 0.75 mm off the
axis, then meets the wall with the same Hertz + Hunt-Crossley normal law as the tyres (sphere inside a cylinder:
R_eff from the ball's and the bore's curvatures) and Coulomb friction on the PETG (mu_plastic from the ball). Each
bounce turns part of the lateral velocity back and costs some spin. The muzzle state is the exit of the bore.

Flight: m dv/dt = m g - 1/2 rho Cd A |v| v + 1/2 rho A C_L |v|^2 (w x v)/|w x v|, with
  - Cd from the sphere's subcritical plateau (Re = 1.5e4-3.5e4 here): 0.47 (smooth sphere); a fuzzy foam surface is
    swept 0.47-0.55 (FLIGHT['cd']);
  - the Magnus lift coefficient vs the spin parameter S = r w / v from baseball data (Nathan 2008: C_L = 1.5 S for
    S < 0.1, 0.09 + 0.6 S above), applied to the ball's spin vector; spin is assumed to persist over the 0.5 s flight;
  - air at 20 C: rho 1.204 kg/m^3, nu 1.5e-5 m^2/s.
It also gives the aiming solution (the tilt that drops the ball on a target) and the drop/drift/dispersion tables.
Validation: the range and drop of stock Rival blasters at their measured fps (FLIGHT['validation']).
The MuJoCo world in sim/turret_e2e.py flies the same balls with MuJoCo's ellipsoid fluid model; mujoco_fluidcoef()
maps these coefficients onto it, and the e2e checks the two agree on the drop at 4 m.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
sys.path.insert(0, str(R / 'cad'))
import turret_common as tc  # noqa: E402
import turret_ball as tb  # noqa: E402
import turret_launch as tl  # noqa: E402

OUT = R / 'exports' / 'turret' / 'flight'
G = 9.81
FLIGHT = {
    'rho': 1.205, 'nu_air': 1.506e-5,
    'air_source': 'air at 20 C, 1 atm: 1.205 kg/m^3 (https://www.engineeringtoolbox.com/air-properties-d_156.html), 15.06 cSt (https://www.engineeringtoolbox.com/air-absolute-kinematic-viscosity-d_601.html); checked 2026-10-27',
    'cd': 0.47, 'cd_range': (0.40, 0.55),
    'cd_source': 'sphere in the Newton regime: Cd 0.38 (Re 5e3) to 0.50 (Re 7e4), Clift-Gauvin fit within 6 % (https://arxiv.org/pdf/1810.08787, Morrison 2016 '
                 'https://pages.mtu.edu/~fmorriso/DataCorrelationForSphereDrag2016.pdf); a polystyrene foam ball fits Cd 0.4-0.5 (https://arxiv.org/pdf/1005.4086); '
                 'rough/napped spheres run 0.55-0.8 (https://ojs.ub.uni-konstanz.de/cpa/article/view/1221/1108); the RoboMaster wheel guide uses 0.50 for its 17 mm TPU ball. '
                 'Here Re = 1.5e4-3.3e4: 0.47 nominal (Clift-Gauvin gives 0.44-0.47), swept to 0.55 for a fuzzy foam surface; checked 2026-10-27',
    'cl': 'Nathan 2008 fit of Sawicki et al. (https://arxiv.org/pdf/physics/0605041): C_L = 1.5 S (S < 0.1), 0.09 + 0.6 S (S >= 0.1), S = r w / v; subcritical LES at Re 1e4 '
          'gives C_L ~ 0.17 at S = 0.1 (Muto et al., https://eprints.lib.hokudai.ac.jp/repo/huscap/all/53053/JoV15-3_261-268.pdf); the negative Magnus regime sits near the '
          'critical Re (4.6e4-2e5 for smooth spheres), above this ball\'s; checked 2026-10-27',
    'muzzle_height_m': 0.55,
    'muzzle_height_note': 'est: the standing robot\'s TM face ~0.33 m hip + 0.214 m (exports/turret/turret.json mount z); the game targets sit at 0.30 m',
    'validation_sources': {
        'nuaa_wheel_guide': 'NUAA friction-wheel design guide (RoboMaster forum, 2024.9, https://bbs-web-static.robomaster.com/bbs-prod/b98a53d00cb548a2a3d8346e48439cf0/%E6%91%A9%E6%93%A6%E8%BD%AE%E8%AE%BE%E8%AE%A1%E6%8C%87%E5%8D%97.pdf): '
                            'a deliberate 1000 rpm wheel mismatch moved the 17 mm ball only ~13 cm at 15 m; 0.1 m/s of speed noise moves the fall point > 10 cm; contact < 5 ms at 340 g; checked 2026-10-27',
        'nathan_two_wheel': 'Nathan (https://arxiv.org/pdf/physics/0605041): two-wheel pitching machine: ball speed = the mean of the two surface speeds, spin from their difference',
        'blasterhub': 'BlasterHub: Hasbro Rival rounds 97 fps average over 100 shots, none under 92 or over 101 (https://blasterhub.com/2017/12/adventure-force-tactical-strike-rounds-review/)'},
}
RANGES_M = (1, 2, 3, 4, 5, 6, 7, 8)


def cl_of_spin(S):
    S = np.asarray(S, float)
    return np.where(S < 0.1, 1.5 * S, 0.09 + 0.6 * S)


def cd_clift_gauvin(Re):
    """Sphere drag vs Reynolds number (Clift & Gauvin 1970; within 6 % of data for Re < 3e5)."""
    Re = np.asarray(Re, float)
    return 24 / Re * (1 + 0.15 * Re ** 0.687) + 0.42 / (1 + 42500 / Re ** 1.16)


def reynolds(v, d):
    return v * d / FLIGHT['nu_air']


# ------------------------------------------------------------------------------------------------ the barrel

def barrel_pass(G_cad, balls, v, omega, pos=None, dt=2e-6, record=False):
    """Carry a population through the bore from the nip exit to the muzzle. v, omega: (n, 3) in the cartridge frame
    (x along the bore). pos: (n, 3) with x measured from the wheel axes' midpoint (launch3d exit_pos) or None (on
    the axis). Returns the muzzle state and the wall-contact bookkeeping."""
    single = not isinstance(balls, (list, tuple))
    balls = [balls] if single else list(balls)
    n = len(balls)
    v = np.array(v, float).reshape(n, 3).copy()
    om = np.array(omega, float).reshape(n, 3).copy()
    p = np.zeros((n, 3)) if pos is None else np.array(pos, float).reshape(n, 3).copy()
    m = np.array([b.m_kg for b in balls])
    r = np.array([b.r_m for b in balls])
    E = np.array([b.E_mpa for b in balls]) * 1e6 / (1 - np.array([b.nu for b in balls]) ** 2)
    e = np.array([b.e for b in balls])
    mu = np.array([b.mu_plastic for b in balls])
    br = G_cad.br / 1000
    x_end = (G_cad.barrel_x1 - G_cad.wheel_x) / 1000        # the muzzle, from the wheel axes
    # sphere inside a cylinder: 1/R = 1/r - 1/br across, r along
    Rc = 1 / (1 / r - 1 / br)
    K = 4 / 3 * E * np.sqrt(np.sqrt(Rc * r))
    alpha = 3 * (1 - e) / (2 * 3.0)
    I = 0.4 * m * r ** 2
    play = br - r
    done = p[:, 0] >= x_end
    bounces = np.zeros(n, int)
    in_contact = np.zeros(n, bool)
    wall_t = np.zeros(n)
    peak_fn = np.zeros(n)
    t = 0.0
    rec = [] if record else None
    for k in range(int(0.03 / dt)):
        live = ~done
        rho = np.sqrt(p[:, 1] ** 2 + p[:, 2] ** 2) + 1e-12
        delta = rho - play
        inc = (delta > 0) & live
        F = np.zeros((n, 3))
        T = np.zeros((n, 3))
        if inc.any():
            nrm = -np.stack([np.zeros(n), p[:, 1] / rho, p[:, 2] / rho], 1)      # from the wall towards the axis
            vn = -(v * nrm).sum(1)                                            # the ball moving into the wall
            Fn = np.where(inc, np.clip(K * np.clip(delta, 0, None) ** 1.5 * (1 + alpha * vn), 0, None), 0.0)
            # the ball's surface velocity at the wall (the contact point is -r n from the centre)
            cp = -r[:, None] * nrm
            vs = v + np.cross(om, cp)
            s = -vs
            s = s - (s * nrm).sum(1)[:, None] * nrm
            smag = np.linalg.norm(s, axis=1) + 1e-12
            Ft = (mu * Fn * np.tanh(smag / 0.05))[:, None] * s / smag[:, None]
            F = Fn[:, None] * nrm + Ft
            T = np.cross(cp, Ft)
            bounces += (inc & ~in_contact)
            wall_t += np.where(inc, dt, 0.0)
            peak_fn = np.maximum(peak_fn, Fn)
        in_contact = inc
        a = F / m[:, None]
        a[:, 2] -= G
        v = np.where(live[:, None], v + a * dt, v)
        om = np.where(live[:, None], om + T / I[:, None] * dt, om)
        p = np.where(live[:, None], p + v * dt, p)
        t += dt
        done |= p[:, 0] >= x_end
        if rec is not None and k % 50 == 0:
            rec.append((t, p[0].copy(), v[0].copy()))
        if done.all():
            break
    speed = np.linalg.norm(v, axis=1)
    out = {'v': v, 'omega': om, 'pos': p, 'speed': speed, 'fps': speed / tl.FPS, 'bounces': bounces, 'wall_ms': wall_t * 1000,
           'yaw_mrad': np.arctan2(v[:, 1], v[:, 0]) * 1000, 'pitch_mrad': np.arctan2(v[:, 2], v[:, 0]) * 1000,
           'peak_wall_n': peak_fn, 'stuck': ~done, 'transit_ms': t * 1000}
    if rec is not None:
        out['trace'] = rec
    return out


# ------------------------------------------------------------------------------------------------ the flight

def fly(balls, v0, omega0=None, h0=None, cd=None, dt=5e-4, t_max=1.5, ranges=RANGES_M, elev_rad=0.0, side_v=0.0):
    """Fly a population from the muzzle (height h0) with velocity v0 (n, 3) in a frame where x is along the aim's
    ground projection, y left, z up; omega0 (n, 3) rad/s. Returns per-ball crossings at each range: z (height) and y
    (drift) and speed, plus the landing point. elev_rad rotates v0 up by the barrel elevation if v0 is given in the
    barrel frame; side_v adds the muzzle's own sideways velocity (pan slew)."""
    single = not isinstance(balls, (list, tuple))
    balls = [balls] if single else list(balls)
    n = len(balls)
    m = np.array([b.m_kg for b in balls])
    r = np.array([b.r_m for b in balls])
    A = np.pi * r ** 2
    rho = FLIGHT['rho']
    cd = FLIGHT['cd'] if cd is None else cd
    cd = np.full(n, cd) if np.isscalar(cd) else np.asarray(cd, float)
    v = np.array(v0, float).reshape(-1, 3)
    if v.shape[0] == 1 and n > 1:
        v = np.repeat(v, n, 0)
    v = v.copy()
    if elev_rad:
        c, s = math.cos(elev_rad), math.sin(elev_rad)
        v = np.stack([c * v[:, 0] - s * v[:, 2], v[:, 1], s * v[:, 0] + c * v[:, 2]], 1)
    v[:, 1] += side_v
    om = np.zeros((n, 3)) if omega0 is None else np.array(omega0, float).reshape(-1, 3)
    if om.shape[0] == 1 and n > 1:
        om = np.repeat(om, n, 0)
    h0 = FLIGHT['muzzle_height_m'] if h0 is None else h0
    p = np.zeros((n, 3))
    p[:, 2] = h0
    cross = {d: np.full((n, 4), np.nan) for d in ranges}         # y, z, speed, t at each range
    landed = np.full((n, 3), np.nan)
    t = 0.0
    live = np.ones(n, bool)
    for k in range(int(t_max / dt)):
        speed = np.linalg.norm(v, axis=1) + 1e-9
        drag = -0.5 * rho * cd * A * speed
        a = drag[:, None] * v / m[:, None]
        wxv = np.cross(om, v)
        wmag = np.linalg.norm(wxv, axis=1)
        S = np.linalg.norm(om, axis=1) * r / speed
        CL = cl_of_spin(S)
        lift = 0.5 * rho * A * CL * speed ** 2
        with np.errstate(invalid='ignore', divide='ignore'):
            a += np.where(wmag[:, None] > 1e-9, lift[:, None] * wxv / np.maximum(wmag, 1e-9)[:, None] / m[:, None], 0.0)
        a[:, 2] -= G
        p_new = p + v * dt + 0.5 * a * dt * dt
        v_new = v + a * dt
        for d in ranges:
            hit = live & (p[:, 0] < d) & (p_new[:, 0] >= d)
            if hit.any():
                f = (d - p[hit, 0]) / (p_new[hit, 0] - p[hit, 0])
                q = p[hit] + f[:, None] * (p_new[hit] - p[hit])
                vq = v[hit] + f[:, None] * (v_new[hit] - v[hit])
                cross[d][hit] = np.stack([q[:, 1], q[:, 2], np.linalg.norm(vq, axis=1), np.full(hit.sum(), t + f.mean() * dt)], 1)
        land = live & (p_new[:, 2] <= 0.0)
        if land.any():
            f = p[land, 2] / (p[land, 2] - p_new[land, 2])
            landed[land] = p[land] + f[:, None] * (p_new[land] - p[land])
            live &= ~land
        p = np.where(live[:, None], p_new, p)
        v = np.where(live[:, None], v_new, v)
        t += dt
        if not live.any():
            break
    return {'cross': cross, 'landed': landed, 'ranges': ranges}


def speed_at_ranges(v0, spec: tb.BallSpec, ranges=RANGES_M, elev_rad=0.0, h0=None):
    """{range: speed} for a level (or elev_rad) shot of one ball."""
    f = fly(spec, [[v0, 0, 0]], h0=h0, elev_rad=elev_rad, ranges=ranges)
    return {d: float(f['cross'][d][0, 2]) for d in ranges if not np.isnan(f['cross'][d][0, 2])}


def drop_at(v0, spec, d, elev_rad=0.0, h0=None, cd=None):
    """Height of the ball at range d (m) for a shot at elev_rad from height h0; NaN if it lands first."""
    f = fly(spec, [[v0, 0, 0]], h0=h0, elev_rad=elev_rad, ranges=(d,), cd=cd)
    return float(f['cross'][d][0, 1])


def elevation_for(v0, spec, d, z_target, h0=None, lo=-0.6, hi=0.0):
    """The barrel elevation (rad, <= 0: never above horizontal) that puts the ball at height z_target at range d, or
    None if even a level shot lands short/low."""
    h0 = FLIGHT['muzzle_height_m'] if h0 is None else h0
    z_level = drop_at(v0, spec, d, hi, h0)
    if np.isnan(z_level) or z_level < z_target:
        return None
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        z = drop_at(v0, spec, d, mid, h0)
        if np.isnan(z) or z < z_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def mujoco_fluidcoef(spec: tb.BallSpec, cd=None, cl_slope=1.5):
    """MuJoCo ellipsoid-fluid coefficients (blunt drag, slender drag, angular drag, Kutta lift, Magnus lift) that match
    this flight model for a sphere, measured on MuJoCo 3.17 (a free sphere, no gravity, 5 steps):
      - blunt drag: C_blunt rho A |v| v with no 1/2, so C_blunt = Cd / 2 (17.50 vs 17.48 m/s^2 at 16.8 m/s);
      - the spin lift comes out as (C_M - 0.5) rho V (w x v), V the ball's volume (the 0.5 is the added-mass term of a
        sphere), linear in C_M (ratios 0.50 at C_M 1 and 0.90 at C_M 5.06). Nathan's small-S lift 1/2 rho A (1.5 S) v^2
        is 1.5 * 3/8 rho V w v, so C_M = 0.5 + cl_slope * 3 / 8 = 1.0625."""
    cd = FLIGHT['cd'] if cd is None else cd
    return f'{cd / 2:.4f} 0 1.5 0 {0.5 + cl_slope * 3 / 8:.4f}'


# ------------------------------------------------------------------------------------------------ the study

def muzzle_state(G_cad, balls, launch_res):
    """The launch stage's exit (sim/turret_launch3d.py result) through the barrel: a dict with the muzzle velocity and
    spin per ball, plus the barrel's own numbers."""
    return barrel_pass(G_cad, balls, launch_res['v'], launch_res['omega'], launch_res['exit_pos'])


def study(quick=False, seed=3):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tu = tc.cad_turret()
    import turret_launch3d as l3
    OUT.mkdir(parents=True, exist_ok=True)
    Gc = tu.Geo()
    l3.set_bore(Gc)
    n = 120 if quick else 400
    pop = tb.population(n, seed=seed)
    balls = [b.launch() for b in pop]
    L = l3.design_launcher()
    D = tl.DESIGN
    w_set = tl.set_speed_for(D['nominal'], L, D['set_fps'] * tl.FPS)
    rng = np.random.default_rng(seed)
    ent = l3.Entry(y=rng.uniform(-0.00075, 0.00075, n), z=-0.00075 + rng.uniform(-0.0003, 0.0003, n), vx=rng.uniform(0.4, 0.8, n),
                   vy=rng.normal(0, 0.05, n), vz=rng.normal(0, 0.05, n))
    lr = l3.launch3d(balls, L, ent, l3.Wheels(w_set=(w_set, w_set), runout=0.00015, runout_phase=(rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n))))
    mz = muzzle_state(Gc, pop, lr)
    res = {'model': __doc__.split('\n\n')[1].strip(), 'flight': FLIGHT, 'bore_play_mm': round(Gc.br - Gc.ball / 2, 3), 'bore_length_from_nip_mm': round(Gc.barrel_x1 - Gc.wheel_x - 12.8, 1)}
    ok = ~mz['stuck']
    res['barrel'] = {'n': int(ok.sum()), 'stuck': int(mz['stuck'].sum()), 'balls_touching_wall': int((mz['bounces'] > 0).sum()), 'bounces_max': int(mz['bounces'].max()),
                     'muzzle_fps': {'mean': round(float(mz['fps'][ok].mean()), 2), 'sd': round(float(mz['fps'][ok].std()), 2), 'min': round(float(mz['fps'][ok].min()), 2), 'max': round(float(mz['fps'][ok].max()), 2)},
                     'nip_fps_mean': round(float(lr['fps'].mean()), 2), 'loss_in_bore_fps': round(float(lr['fps'].mean() - mz['fps'][ok].mean()), 3),
                     'exit_yaw_mrad': {'sd': round(float(mz['yaw_mrad'][ok].std()), 3), 'max_abs': round(float(np.abs(mz['yaw_mrad'][ok]).max()), 3)},
                     'exit_pitch_mrad': {'mean': round(float(mz['pitch_mrad'][ok].mean()), 3), 'sd': round(float(mz['pitch_mrad'][ok].std()), 3)},
                     'nip_yaw_mrad_sd': round(float(lr['yaw_mrad'].std()), 3), 'nip_pitch_mrad_mean': round(float(lr['pitch_mrad'].mean()), 3),
                     'spin_at_muzzle_rad_s': {'y_mean': round(float(mz['omega'][ok, 1].mean()), 1), 'z_sd': round(float(mz['omega'][ok, 2].std()), 1)},
                     'transit_ms': round(float(mz['transit_ms']), 2), 'peak_wall_n_max': round(float(mz['peak_wall_n'].max()), 2)}
    # a deliberately crooked entry: 2 deg yaw at the nip, to show what the bore does
    crooked = barrel_pass(Gc, pop[:20], np.stack([lr['v'][:20, 0], lr['v'][:20, 0] * math.tan(math.radians(2)), lr['v'][:20, 2]], 1), lr['omega'][:20], lr['exit_pos'][:20])
    res['barrel']['crooked_2deg_entry'] = {'exit_yaw_mrad_mean_abs': round(float(np.abs(crooked['yaw_mrad']).mean()), 2), 'bounces_mean': round(float(crooked['bounces'].mean()), 2),
                                           'fps_loss': round(float(lr['fps'][:20].mean() - crooked['fps'].mean()), 2)}
    # the bore's play: the ball rides the channel floor and bounces; how the muzzle scatter and the spin depend on it
    class _G:
        pass
    play_rows = {}
    for play in (0.25, 0.5, 0.75, 1.0):
        g2 = _G()
        g2.br = Gc.ball / 2 + play
        g2.barrel_x1, g2.wheel_x, g2.ball = Gc.barrel_x1, Gc.wheel_x, Gc.ball
        sub = pop[:40 if quick else 100]
        l3.BORE_R_M = g2.br / 1000
        lr2 = l3.launch3d([b.launch() for b in sub], L, l3.Entry(y=ent.y[:len(sub)], z=np.minimum(ent.z[:len(sub)], -play / 1000 + 0.0001), vx=ent.vx[:len(sub)], vy=ent.vy[:len(sub)], vz=ent.vz[:len(sub)]),
                          l3.Wheels(w_set=(w_set, w_set), runout=0.00015, runout_phase=(rng.uniform(0, 2 * np.pi, len(sub)), rng.uniform(0, 2 * np.pi, len(sub)))))
        b2 = barrel_pass(g2, sub, lr2['v'], lr2['omega'], lr2['exit_pos'])
        okk = ~b2['stuck']
        play_rows[f'play_{play:g}_mm'] = {'bore_mm': round(2 * g2.br, 2), 'muzzle_fps_mean': round(float(b2['fps'][okk].mean()), 2), 'loss_fps': round(float(lr2['fps'][okk].mean() - b2['fps'][okk].mean()), 2),
                                           'pitch_mrad_sd': round(float(b2['pitch_mrad'][okk].std()), 2), 'yaw_mrad_sd': round(float(b2['yaw_mrad'][okk].std()), 2),
                                           'spin_y_mean': round(float(b2['omega'][okk, 1].mean()), 1), 'spin_y_sd': round(float(b2['omega'][okk, 1].std()), 1), 'stuck': int(b2['stuck'].sum())}
    l3.set_bore(Gc)
    res['bore_play_sweep'] = {**play_rows, 'note': 'the CAD bore is ball + 1.5 mm (0.75 mm play); the entry state and the launch use the same bore'}
    # flight: the population, level, from the muzzle height; drop, drift, dispersion at each range
    spec_n = tb.nominal()
    f = fly(pop, mz['v'], mz['omega'])
    tabs = {}
    for d in RANGES_M:
        c = f['cross'][d]
        good = ~np.isnan(c[:, 0])
        if good.sum() < 3:
            continue
        y, z, s = c[good, 0], c[good, 1], c[good, 2]
        tabs[f'{d}_m'] = {'arrived': int(good.sum()), 'drop_cm_mean': round(float((FLIGHT['muzzle_height_m'] - z.mean()) * 100), 2), 'z_sd_cm': round(float(z.std() * 100), 2),
                          'drift_cm_mean': round(float(y.mean() * 100), 2), 'y_sd_cm': round(float(y.std() * 100), 2), 'speed_mean': round(float(s.mean()), 2), 'fps_mean': round(float(s.mean() / tl.FPS), 1),
                          'radius_68_cm': round(float(np.percentile(np.hypot(y - y.mean(), z - z.mean()), 68) * 100), 2), 'time_s': round(float(np.nanmean(c[good, 3])), 3)}
    res['level_shot_population'] = tabs
    res['ball_spread_only_vs_launch'] = 'the spread above is the ball population + the feed\'s entry offsets + 0.15 mm tyre runout through the bore; no aim error'
    # the nominal ball: drop vs range at 55 and 70 fps, Cd 0.47 and 0.55; the time of flight
    nom = {}
    for fps in (55, 70):
        for cd in (0.47, 0.55):
            fr = fly(spec_n, [[fps * tl.FPS, 0, 0]], cd=cd)
            nom[f'{fps}_fps_cd_{cd}'] = {f'{d}_m': {'drop_cm': round(float((FLIGHT['muzzle_height_m'] - fr['cross'][d][0, 1]) * 100), 1), 'fps': round(float(fr['cross'][d][0, 2] / tl.FPS), 1), 't_s': round(float(fr['cross'][d][0, 3]), 3)}
                                          for d in RANGES_M if not np.isnan(fr['cross'][d][0, 0])}
            nom[f'{fps}_fps_cd_{cd}']['lands_at_m'] = round(float(fr['landed'][0, 0]), 2) if not np.isnan(fr['landed'][0, 0]) else None
    res['nominal_drop'] = nom
    # the aiming solution: tilt for a 0.30 m target at each range, from 0.55 m, and the reach (never above horizontal)
    aim = {}
    for d in RANGES_M:
        el = elevation_for(55 * tl.FPS, spec_n, d, 0.30)
        aim[f'{d}_m'] = {'tilt_deg': round(math.degrees(el), 2) if el is not None else None}
    res['aim_for_0_30m_target'] = aim
    res['reach_level_m'] = {f'{fps}_fps': nom[f'{fps}_fps_cd_0.47']['lands_at_m'] for fps in (55, 70)}
    # the Magnus effect of the launch's spin and of a mismatched wheel pair: drift at 6 m
    mag = {}
    for rpm in (0, 300, 1000, 3000):
        w = rpm * 2 * math.pi / 60
        fr = fly(spec_n, [[55 * tl.FPS, 0, 0]], [[0, 0, w]])
        mag[f'spin_z_{rpm}_rpm'] = {'S': round(w * spec_n.r_m / (55 * tl.FPS), 4), 'drift_cm_at_6m': round(float(fr['cross'][6][0, 0] * 100), 2), 'drift_cm_at_4m': round(float(fr['cross'][4][0, 0] * 100), 2)}
    fr = fly(spec_n, [[55 * tl.FPS, 0, 0]], [[0, 34.5, 0]])
    fr0 = fly(spec_n, [[55 * tl.FPS, 0, 0]])
    mag['launch_topspin_34_rad_s'] = {'S': round(34.5 * spec_n.r_m / (55 * tl.FPS), 4),
                                      'extra_drop_cm_at_4m': round(float((fr0['cross'][4][0, 1] - fr['cross'][4][0, 1]) * 100), 2),
                                      'note': 'the ball leaves the nip with ~35-40 rad/s of topspin (it arrives rolling): a backspin-free launch would carry a little further; topspin pushes it down'}
    res['magnus'] = mag
    # the pan slew: the muzzle's own sideways velocity deflects the shot
    slew = {}
    r_muzzle = (Gc.barrel_x1 - Gc.tilt_x) / 1000
    for dps in (30, 90, 150):
        sv = math.radians(dps) * r_muzzle
        fr = fly(spec_n, [[55 * tl.FPS, 0, 0]], side_v=sv)
        slew[f'{dps}_deg_s'] = {'muzzle_side_v_m_s': round(sv, 3), 'deflection_deg': round(math.degrees(math.atan2(sv, 55 * tl.FPS)), 2),
                                'drift_cm': {f'{d}_m': round(float(fr['cross'][d][0, 0] * 100), 1) for d in (2, 4, 6) if not np.isnan(fr['cross'][d][0, 0])}}
    res['pan_slew_deflection'] = slew
    # the reach of a never-above-horizontal barrel: where a level shot from the muzzle height lands, and the farthest
    # 0.30 m target it can reach, at the set speed, the 65 fps default and the cap, from 0.55 m and from a taller stance
    reach = {}
    for h0 in (0.55, 0.70, 0.85):
        for fps in (55, 65, 70):
            fr = fly(spec_n, [[fps * tl.FPS, 0, 0]], h0=h0)
            lo, hi = 0.5, 12.0
            for _ in range(25):                                     # the farthest range where a level shot is still at 0.30 m
                mid = 0.5 * (lo + hi)
                z = drop_at(fps * tl.FPS, spec_n, mid, 0.0, h0)
                lo, hi = (mid, hi) if (not np.isnan(z) and z >= 0.30) else (lo, mid)
            reach[f'h{h0:g}_{fps}fps'] = {'lands_at_m': round(float(fr['landed'][0, 0]), 2), 'farthest_0_30m_target_m': round(lo, 2)}
    res['reach'] = reach
    # validation against stock Rival blasters (level shots from 1.5 m, shoulder height) at their measured fps
    val = {}
    for name, fps in (('Nemesis MXVII-10K (101 fps, Blaster Piece)', 101), ('Hasbro Rival rounds, BlasterHub (97 fps)', 97), ('Kronos (90 fps claim)', 90)):
        fr = fly(tb.nominal(), [[fps * tl.FPS, 0, 0]], h0=1.5, ranges=(4, 8, 10, 15))
        c = fr['cross']
        val[name] = {'fps': fps, 'level_range_to_ground_from_1_5m_m': round(float(fr['landed'][0, 0]), 1),
                     'drop_cm': {f'{d}_m': round(float((1.5 - c[d][0, 1]) * 100), 1) for d in (4, 8, 10, 15) if not np.isnan(c[d][0, 1])},
                     'speed_fps': {f'{d}_m': round(float(c[d][0, 2] / tl.FPS), 1) for d in (4, 8, 10, 15) if not np.isnan(c[d][0, 2])}}
    res['validation'] = val
    (OUT / 'flight.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    # plots
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), dpi=130)
    ds = [d for d in RANGES_M if f'{d}_m' in tabs]
    ax[0].plot(ds, [tabs[f'{d}_m']['drop_cm_mean'] for d in ds], 'o-', label='population mean (55 fps set, Cd 0.47)')
    ax[0].fill_between(ds, [tabs[f'{d}_m']['drop_cm_mean'] - 2 * tabs[f'{d}_m']['z_sd_cm'] for d in ds], [tabs[f'{d}_m']['drop_cm_mean'] + 2 * tabs[f'{d}_m']['z_sd_cm'] for d in ds], alpha=0.2, label='+-2 SD')
    for key, ls in (('70_fps_cd_0.47', '--'), ('55_fps_cd_0.55', ':')):
        dd = [d for d in RANGES_M if f'{d}_m' in nom[key]]
        ax[0].plot(dd, [nom[key][f'{d}_m']['drop_cm'] for d in dd], ls, label=key.replace('_', ' '))
    ax[0].invert_yaxis()
    ax[0].set_xlabel('range (m)')
    ax[0].set_ylabel('drop below the bore line (cm)')
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    for d, col in ((2, '#2563eb'), (4, '#c2410c'), (6, '#15803d')):
        c = f['cross'][d]
        good = ~np.isnan(c[:, 0])
        ax[1].scatter(c[good, 0] * 100, (c[good, 1] - FLIGHT['muzzle_height_m']) * 100, s=5, alpha=0.5, color=col, label=f'{d} m')
    ax[1].set_xlabel('drift left (cm)')
    ax[1].set_ylabel('height vs the bore line (cm)')
    ax[1].set_title('where the population lands on a vertical plane (no aim error)', fontsize=9)
    ax[1].legend(fontsize=7)
    ax[1].grid(alpha=0.3)
    ax[1].set_aspect('equal')
    ax[2].hist(mz['fps'][ok], bins=30, alpha=0.7, label='muzzle')
    ax[2].hist(lr['fps'], bins=30, alpha=0.5, label='nip exit')
    ax[2].set_xlabel('fps')
    ax[2].set_title('through the bore: wall contacts cost little', fontsize=9)
    ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / 'flight.png')
    plt.close(fig)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    r = study(quick=a.quick)
    print(json.dumps({k: r[k] for k in ('barrel', 'level_shot_population', 'aim_for_0_30m_target', 'reach_level_m', 'magnus', 'pan_slew_deflection', 'validation')}, indent=1))
