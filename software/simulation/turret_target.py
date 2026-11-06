"""The target: what a ball does when it arrives, whether it knocks a game target over, and what it would do to a kid.

    .venv/bin/python sim/turret_target.py      # writes exports/turret/target/target.json and a plot

Impact: momentum m v and energy 1/2 m v^2 at the target (the flight stage's speed there), the energy density over the
ball's cross-section (the toy standards' measure), compared with EN 71-1's 0.5 J for resilient projectiles and ASTM
F963's 2500 J/m^2, and with a stock Rival blaster (Hasbro: 90-100 fps; BlasterHub measured 97 fps average).

Knock-over, two kinds of target:
  - a hinged plate (the game's knock-down target, sim/turret.py targets_xml(): a 20 g, 240 mm plate hinged along its
    bottom edge, resting 4 deg towards the shooter against a stop): the ball's impulse at height h gives the plate
    angular speed w = J h / I; it goes over if 1/2 I w^2 > m g r_cm (1 - cos(lean)). The impulse a ball delivers to a
    heavy plate is (1 + e) m_b v_b / (1 + m_b h^2 / I) (a plate much heavier than the ball takes nearly (1 + e) m v).
  - a free-standing block or bottle on a table: it tips about its far base edge if the impulse's energy lifts the
    centre of mass over that edge: 1/2 I_edge w^2 > m g (sqrt(a^2 + h_cm^2) - h_cm), w = J h_hit / I_edge.
Both are reduced models (rigid bodies, an instantaneous impulse at one point); sim/turret_e2e.py checks the hinged
plate in MuJoCo with the ball bodies, and the bench plan counts real knock-overs.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'sim'))
import turret_ball as tb  # noqa: E402
import turret_launch as tl  # noqa: E402

OUT = R / 'exports' / 'turret' / 'target'
G = 9.81
LIMITS = {
    'en71_resilient_j': {'value': 0.5, 'source': 'EN 71-1 4.17.3 (https://law.resource.org/pub/eu/toys/en.71.1.2014.html): 0.5 J for resilient projectiles', 'checked': '2026-10-25 (research/turret-and-safety.md)'},
    'astm_ked_j_m2': {'value': 2500.0, 'source': 'ASTM F963 4.21.2.3 / 8.14.6: kinetic energy per unit area <= 2500 J/m^2 above 0.08 J (research/turret-and-safety.md)', 'checked': '2026-10-25'},
    'stock_rival_fps': {'value': (90.0, 100.0), 'source': 'Hasbro Rival claims 90-100 fps (research/turret-launcher-study.md 6.1); BlasterHub measured 97 fps average over 100 shots', 'checked': '2026-10-27'},
}
# game targets (the first is the simulator's plate; the others are what a kid's game might use; est where marked)
TARGETS = {
    'sim_plate_20g': {'kind': 'hinged', 'mass_kg': 0.020, 'height_m': 0.24, 'lean_deg': 4.0, 'hit_h_m': 0.12, 'note': 'sim/turret.py targets_xml(): 20 g foam-board plate, 240 mm, hinged at the bottom, 4 deg rest lean'},
    'plywood_plate_150g': {'kind': 'hinged', 'mass_kg': 0.150, 'height_m': 0.20, 'lean_deg': 4.0, 'hit_h_m': 0.10, 'note': 'est: 3 mm plywood 200 x 200 on a hinge'},
    'plywood_plate_150g_lean10': {'kind': 'hinged', 'mass_kg': 0.150, 'height_m': 0.20, 'lean_deg': 10.0, 'hit_h_m': 0.10, 'note': 'the same plate with a 10 deg rest lean (harder)'},
    'soda_can_empty': {'kind': 'free', 'mass_kg': 0.015, 'height_m': 0.122, 'base_half_m': 0.033, 'hit_h_m': 0.08, 'note': 'an empty 330 ml can on a table: 15 g, 66 mm diameter, 122 mm tall'},
    'bottle_500ml_quarter': {'kind': 'free', 'mass_kg': 0.145, 'height_m': 0.21, 'base_half_m': 0.032, 'hit_h_m': 0.12, 'cm_h_m': 0.06, 'note': 'est: a 500 ml bottle with 125 ml of water (CoM low)'},
    'cardboard_box_200g': {'kind': 'free', 'mass_kg': 0.200, 'height_m': 0.20, 'base_half_m': 0.075, 'hit_h_m': 0.15, 'note': 'est: a 150 x 150 x 200 box, 200 g, uniform'},
}


def impact(spec: tb.BallSpec, v):
    """Momentum (N s), energy (J) and energy density (J/m^2) of the ball at speed v, with the safety comparisons."""
    ke, ked = tb.energy(spec, v)
    stock = [tb.energy(spec, f * tl.FPS)[0] for f in LIMITS['stock_rival_fps']['value']]
    return {'v_m_s': round(v, 3), 'fps': round(v / tl.FPS, 2), 'momentum_ns': round(spec.m_kg * v, 5), 'ke_j': round(ke, 4), 'ked_j_m2': round(ked, 1),
            'vs_en71_0_5j': round(ke / LIMITS['en71_resilient_j']['value'], 3), 'vs_astm_2500': round(ked / LIMITS['astm_ked_j_m2']['value'], 3),
            'vs_stock_rival_90_100fps': [round(ke / s, 3) for s in stock]}


def ball_impulse(m_b, v_b, e, m_eff):
    """Impulse (N s) a ball of mass m_b at v_b leaves on a target whose effective mass at the hit point is m_eff
    (hinged plate: I / h^2), with restitution e: J = (1 + e) m_b v_b / (1 + m_b / m_eff)."""
    return (1 + e) * m_b * v_b / (1 + m_b / m_eff)


def knockdown(target: dict, spec: tb.BallSpec, v, e=None):
    """Does one ball at speed v knock this target over? Returns the impulse needed, the one delivered, and the margin."""
    e = spec.e if e is None else e
    m, H, h = target['mass_kg'], target['height_m'], target['hit_h_m']
    if target['kind'] == 'hinged':
        I = m * H ** 2 / 3                                         # a thin plate about its bottom edge
        r_cm = H / 2
        lean = math.radians(target['lean_deg'])
        need_w = math.sqrt(2 * m * G * r_cm * (1 - math.cos(lean)) / I)
        J_need = need_w * I / h
    else:
        a = target['base_half_m']
        h_cm = target.get('cm_h_m', H / 2)
        I = m * ((2 * a) ** 2 + H ** 2) / 12 + m * (a ** 2 + h_cm ** 2)    # a box about its far base edge
        rise = math.sqrt(a ** 2 + h_cm ** 2) - h_cm
        need_w = math.sqrt(2 * m * G * rise / I)
        J_need = need_w * I / h
    m_eff = I / h ** 2
    J = ball_impulse(spec.m_kg, v, e, m_eff)
    return {'impulse_needed_ns': round(J_need, 5), 'impulse_delivered_ns': round(J, 5), 'margin': round(J / J_need, 2), 'knocked': J >= J_need,
            'target_effective_mass_kg': round(m_eff, 4)}


def max_plate_mass(J, H=0.2, lean_deg=4.0, hit_frac=0.5):
    """The heaviest hinged plate (kg) of height H and rest lean that impulse J at hit_frac * H tips over."""
    lean = math.radians(lean_deg)
    h = hit_frac * H
    # 1/2 (J h)^2 / I >= m g (H/2) (1 - cos lean), I = m H^2 / 3  ->  m^2 <= 3 J^2 h^2 / (g H^3 (1 - cos lean))
    return math.sqrt(3 * J ** 2 * h ** 2 / (G * H ** 3 * (1 - math.cos(lean))))


def study(speeds_by_range=None):
    """speeds_by_range: {range_m: v} from the flight stage; defaults to the D68 set speed (95 fps) with the standard drag."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    spec = tb.nominal()
    if speeds_by_range is None:
        import turret_flight as tf
        speeds_by_range = tf.speed_at_ranges(tl.DESIGN['set_fps'] * tl.FPS, spec)
    res = {'limits': LIMITS, 'targets': TARGETS, 'ball': spec.__dict__,
           'impact_by_range': {f'{d:g}_m': impact(spec, v) for d, v in speeds_by_range.items()},
           'impact_at_muzzle': {f'{f}_fps': impact(spec, f * tl.FPS) for f in (55, 70, 95, 100, 105)},
           'knockdown': {}}
    for name, t in TARGETS.items():
        res['knockdown'][name] = {f'{d:g}_m': knockdown(t, spec, v) for d, v in speeds_by_range.items()}
    worst = tb.worst_for_cap()
    # D67's densest accepted round (2.0 g on 22.2 mm), stiff and grippy, at its own ceiling: exports/turret/launch/launch.json
    densest = tb.BallSpec('densest-accepted', 'spec', tl.BALL_D[0], tl.BALL_M[1], tl.BALL_E[1], tl.BALL_RESTITUTION[1], tl.BALL_MU[1], 0.7, tb.RANGES['nu'])
    lj = R / 'exports' / 'turret' / 'launch' / 'launch.json'
    trim = json.loads(lj.read_text()).get('trim', {}) if lj.exists() else {}
    dense_v = math.sqrt(2 * trim['densest_ked_j_m2'] * densest.area_m2 / densest.m_kg) if trim.get('densest_ked_j_m2') else tl.CAP
    ft = trim.get('hasbro_full_throttle_fps', tl.TARGET_FPS[1])
    res['knockdown_soft_slow_ball'] = {f'{d:g}_m': knockdown(TARGETS['sim_plate_20g'], tb.BallSpec('soft', 'x', 22.5, 1.6, 0.75, 0.45, 0.6, 0.4), v * 0.9, e=0.45)
                                       for d, v in speeds_by_range.items()}
    res['max_hinged_plate_mass_kg'] = {f'{d:g}_m': {f'lean_{l}_deg': round(max_plate_mass(ball_impulse(spec.m_kg, v, spec.e, 1.0), 0.2, l), 3) for l in (2, 4, 10, 20)}
                                       for d, v in speeds_by_range.items()}
    cap, setp, full, dense = impact(spec, tl.CAP), impact(spec, tl.DESIGN['set_fps'] * tl.FPS), impact(spec, ft * tl.FPS), impact(densest, dense_v)
    res['kid_safety'] = {'cap_105fps': cap, 'set_95fps': setp, 'full_throttle': full, 'densest_accepted_at_its_ceiling': dense,
                         'worst_ball_at_cap': impact(worst, tl.CAP),
                         'verdict': (f'D68 (a 14+ product like Hasbro\'s Rival blasters; EN 71-1\'s 0.5 J is for toys for under-14s): at the 105 fps ceiling '
                                     f'the Hasbro ball carries {cap["ke_j"]:.2f} J and {cap["ked_j_m2"]:.0f} J/m^2 ({100 * cap["vs_astm_2500"]:.0f} % of ASTM F963); '
                                     f'flat out on the trimmed rail ({ft:.1f} fps) {full["ke_j"]:.2f} J, {full["ked_j_m2"]:.0f} J/m^2; the densest accepted round '
                                     f'(2.0 g on 22.2 mm) at its own ceiling ({dense["fps"]:.1f} fps) {dense["ke_j"]:.2f} J, {dense["ked_j_m2"]:.0f} J/m^2 '
                                     f'({100 * dense["vs_astm_2500"]:.0f} % of ASTM): the trim holds it there. A stock Rival blaster at 97 fps is '
                                     f'{impact(spec, 97 * tl.FPS)["ke_j"]:.2f} J. Eye protection is recommended, as Hasbro does')}
    (OUT / 'target.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    fig, ax = plt.subplots(1, 2, figsize=(11, 4), dpi=130)
    ds = sorted(speeds_by_range)
    ax[0].plot(ds, [impact(spec, speeds_by_range[d])['ke_j'] for d in ds], 'o-', label=f"Gyropup, {tl.DESIGN['set_fps']:.0f} fps set speed")
    ax[0].axhline(impact(spec, tl.CAP)['ke_j'], color='#c2410c', ls='--', label='at the 105 fps ceiling (muzzle)')
    ax[0].axhline(impact(spec, 97 * tl.FPS)['ke_j'], color='#7c3aed', ls=':', label='stock Rival, 97 fps (muzzle)')
    ax[0].axhline(0.5, color='k', lw=1, label='EN 71-1 resilient 0.5 J')
    ax[0].set_xlabel('range (m)')
    ax[0].set_ylabel('ball energy (J)')
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    for l in (2, 4, 10, 20):
        ax[1].plot(ds, [max_plate_mass(ball_impulse(spec.m_kg, speeds_by_range[d], spec.e, 1.0), 0.2, l) * 1000 for d in ds], 'o-', label=f'rest lean {l} deg')
    ax[1].set_xlabel('range (m)')
    ax[1].set_ylabel('heaviest 200 mm hinged plate knocked over (g)')
    ax[1].set_yscale('log')
    ax[1].legend(fontsize=7)
    ax[1].grid(alpha=0.3, which='both')
    fig.tight_layout()
    fig.savefig(OUT / 'target.png')
    plt.close(fig)
    return res


if __name__ == '__main__':
    r = study()
    print(json.dumps({k: r[k] for k in ('impact_by_range', 'kid_safety', 'max_hinged_plate_mass_kg')}, indent=1))
    print({k: {d: v['knocked'] for d, v in x.items()} for k, x in r['knockdown'].items()})
