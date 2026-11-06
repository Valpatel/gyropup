"""Wheel study (issue #18): the leg rig and the full robot with an air-tyre hub motor in place of the BotWheel.

    python -m sim.wheel_study rig  [--wheels hb10 ...] [--half-mass 16.25] [--only jump drop_150] [--v-static 38]
    python -m sim.wheel_study curb [--wheels hb10 ...] [--heights 25 40 50 60 80 100] [--speed 0.6]
    python -m sim.wheel_study fit  [--wheels hb10 ...]              # the wheel's reach at every stance (geometry only)

Nothing in sim/leg_rig.py, cad/fivebar.py or rig/ is edited: the candidate wheel is put into sim.leg_rig's module
state (WHEEL, WHEEL_R, TYRE_SOLREF, ROTOR_SHARE) before the model is built, the way the first sweep in #18 was made.
The wheels come from sim/wheel_candidates.json. Results: exports/wheels/<mode>_<wheel>.json and summary.json.

The tyre: MuJoCo's contact is a spring-damper with time constant tau on the mass behind it, so stiffness goes as
1/tau^2. The rig's solid BotWheel is 7.7 ms / 0.7 (an estimated 150-250 N/mm). A pneumatic tyre of radial stiffness
k_p gets tau_p = 7.7 ms x sqrt(k_solid / k_p) with k_solid = 200 N/mm, and a lower damping ratio (0.5): the same
convention as research/leg-suspension.md's `tyre_pneumatic` (13 ms / 0.5). The stiffness itself is derived in
research/air-tyre-hub-wheels.md (membrane model calibrated on measured bicycle and wheelchair tyres).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
if str(R) not in sys.path:
    sys.path.insert(0, str(R))
sys.path.insert(0, str(R / 'cad'))       # fivebar, gmi (as sim/leg_rig.py does)
os.environ.setdefault('MUJOCO_GL', 'egl')

OUT = R / 'exports' / 'wheels'
CANDIDATES = json.loads((R / 'sim' / 'wheel_candidates.json').read_text())
K_SOLID = 200.0            # N/mm, the rig's solid tyre (sim/leg_rig.py's estimate, mid-range)
TAU_SOLID = 0.0077         # s


def solref_for(k_n_per_mm: float | None, damp: float = 0.5) -> str:
    if not k_n_per_mm:
        return '0.0077 0.7'                                   # the solid BotWheel as the rig has it
    return f'{TAU_SOLID * math.sqrt(K_SOLID / k_n_per_mm):.4f} {damp}'


def patch_rig(w: dict):
    """Put a candidate wheel into sim.leg_rig's module state and drop its cached mass model."""
    from sim import leg_rig as lr
    spec = dict(lr.WHEEL)
    spec.update({'mass_g': w['mass_g'], 'peak_torque_nm': w['peak_torque_nm'], 'rated_torque_nm': w['rated_torque_nm'],
                 'no_load_speed_rpm': w['no_load_speed_rpm'], 'voltage_nominal_v': w['voltage_nominal_v'],
                 'kt_nm_per_a': w['kt_nm_per_a'], 'peak_current_a': w['peak_current_a']})
    lr.WHEEL = spec
    lr.WHEEL_R = w['od_mm'] / 2000
    lr.TYRE_SOLREF = solref_for(w.get('tyre_k_n_per_mm'), w.get('tyre_damp', 0.5))
    lr.ROTOR_SHARE = w.get('rotor_share', 0.6)
    lr.mass_props.cache_clear()
    return lr


def rig(wheels, half_mass: float, only, v_static: float, rate: float = 500.0, r_int: float = 0.10) -> dict:
    """rig/run.py's scenarios (its controller, 500 Hz, a tick of latency, the FLEXVOLT pair) for each wheel. The leg
    carries half_mass plus the wheel's extra mass over the BotWheel, as the first sweep in #18 did."""
    from rig import run as rr
    from rig import leg_control as lc
    tests = only or ['stand_up', 'squat', 'jump', 'jump_peak', 'drop_150', 'power_off', 'power_off_damped']
    out = {}
    for name in wheels:
        w = CANDIDATES[name]
        lr = patch_rig(w)
        hm = half_mass + (w['mass_g'] - 2200) / 1000
        row = {'wheel': w, 'half_mass_kg': round(hm, 3), 'tyre_solref': lr.TYRE_SOLREF, 'wheel_r_m': lr.WHEEL_R, 'tests': {}}
        print(f'== {name}: {w["title"]}  r {lr.WHEEL_R * 1000:.1f} mm, {w["mass_g"]} g, tyre solref {lr.TYRE_SOLREF}, leg carries {hm:.2f} kg')
        for test in tests:
            if test not in lc.SCENARIOS:
                continue
            pack = rr.pack_for(test, r_int, v_static=v_static)
            rail = rr.BUMPER_CONTACT_M if not test.startswith('power_off') else lc.SCENARIOS[test].rail_low
            t0 = time.time()
            o = rr.run_sim(test, hm, rate, pack, 1, rail_low=rail, save=False)
            res = o['results']
            keys = ('jump_height_mm', 'peak_motor_nm', 'peak_gearbox_nm', 'gearbox_over_peak_ms', 'peak_knee_pin_n', 'peak_wheel_force_n',
                    'peak_axle_force_n', 'axle_force_at_peak_n', 'peak_front_link_n', 'peak_stop_nm', 'L_range_mm', 'peak_joint_force_n')
            row['tests'][test] = {k: res.get(k) for k in keys}
            row['tests'][test]['pack'] = {'v_oc': pack.v_oc, 'r_int': pack.r_int}
            row['tests'][test]['wall_s'] = round(time.time() - t0, 1)
            print(f"  {test:17} jump {res.get('jump_height_mm')}  motor {res['peak_motor_nm']}  gearbox {res['peak_gearbox_nm']}  "
                  f"knee {res['peak_knee_pin_n']}  wheel {res['peak_wheel_force_n']}  axle {res['peak_axle_force_n']}  ({row['tests'][test]['wall_s']} s)")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f'rig_{name}.json').write_text(json.dumps(row, indent=1) + '\n')
        out[name] = row
    return out


def _patch_cad(w: dict):
    """The candidate wheel's solid in place of fb.botwheel(): a tyre ring, a hub drum, the single-sided axle into the foot."""
    import cadquery as cq
    import fivebar as fb

    def wheel():
        od, width, hub_d, hub_w = w['od_mm'], w['tyre_width_mm'], w['hub_od_mm'], w['hub_width_mm']
        y_in = fb.Y['wheel_boss'] + 7.5                              # the tyre's inner face, where the BotWheel's was
        yc = y_in + width / 2
        tyre = fb.ycyl(od / 2, yc - width / 2, yc + width / 2).cut(fb.ycyl(od / 2 - w['tyre_section_mm'], yc - width / 2 - 1, yc + width / 2 + 1))
        hub = fb.ycyl(hub_d / 2, yc - hub_w / 2, yc + hub_w / 2)
        axle = fb.ycyl(w['axle_d_mm'] / 2, fb.Y['hub'][0] + 2.0, yc - hub_w / 2 + 0.01)   # through the foot's bore
        return tyre, hub.union(axle)
    fb.botwheel = wheel
    fb.leg_parts.cache_clear()
    return fb


def fit(wheels) -> dict:
    """Geometry only (no solids): where the tyre reaches at every stance, against the hip axis, the stop posts and the
    body's belly; the track; the standing hip height. The solid clash sweep is cad/wheel_fit.py (slow)."""
    import fivebar as fb
    out = {}
    fo, fi, ro, ri = fb.stop_angles()
    posts = fb.stop_posts()
    for name in wheels:
        w = CANDIDATES[name]
        r = w['od_mm'] / 2
        rows = []
        for h in (101.5, 110, 130, 160, 200, 250, 300, 350, 392):
            for lean in (-20, 0, 20):
                phi = fb.stance(h, lean)
                if phi is None or not (fi <= phi[0] <= fo) or not (ro <= phi[1] <= ri):
                    continue
                j = fb.fk(*phi)
                ex, ez = j['E']
                top = ez + r                                             # the tyre's top, from the hip axis (z up)
                near_post = min(math.hypot(ex - px, ez - pz) - r for px, pz in posts)
                near_motor = math.hypot(ex - fb.P['D'] / 2, ez) - r - 60.0   # the RS-04's Ø120 case, same x-z, other y
                rows.append({'L_mm': h, 'lean_deg': lean, 'E_mm': [round(ex, 1), round(ez, 1)], 'tyre_top_above_hip_mm': round(top, 1),
                             'tyre_to_stop_post_xz_mm': round(near_post, 1), 'tyre_to_motor_case_xz_mm': round(near_motor, 1)})
        y_in = fb.Y['wheel_boss'] + 7.5
        out[name] = {'wheel': w, 'rows': rows, 'tyre_y_band_mm': [round(y_in, 1), round(y_in + w['tyre_width_mm'], 1)],
                     'botwheel_y_band_mm': [round(fb.Y['tyre'][0], 1), round(fb.Y['tyre'][1], 1)],
                     'leg_outer_face_mm': round(fb.Y['wheel_link'][1], 1), 'motor_y_band_mm': [round(fb.Y['motor'][0], 1), round(fb.Y['motor'][1], 1)],
                     'hip_height_standing_300_mm': round(300 + r, 1), 'hip_height_botwheel_mm': 385.65,
                     'leg_for_same_hip_height_mm': round(385.65 - r, 1)}
        print(f"{name}: tyre y {out[name]['tyre_y_band_mm']} (BotWheel {out[name]['botwheel_y_band_mm']}); hip at 300 mm leg: {300 + r:.0f} mm; "
              f"worst tyre top above hip {max(x['tyre_top_above_hip_mm'] for x in rows):.0f} mm; "
              f"closest to a stop post {min(x['tyre_to_stop_post_xz_mm'] for x in rows):.0f} mm (other y plane)")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fit.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


def curb(wheels, heights, speed: float, video: bool = False) -> dict:
    """The full robot (sim/robot_v2.py, its balance controller) driving at a kerb of each height with each wheel."""
    from sim import scenarios as S
    from sim.controller import Command
    out = {}
    for name in wheels:
        w = CANDIDATES[name]
        lr = patch_rig(w)
        _patch_cad(w)
        import sim.robot_v2 as rv
        info = rv.build()
        xml = R / 'build' / 'sim' / 'v2' / 'robot.xml'
        row = {'wheel': w, 'model_mass_kg': round(info['total_mass_kg'], 2), 'wheel_motor': info['wheel_motor'], 'speed_mps': speed, 'heights': {}}
        print(f"== {name}: robot {info['total_mass_kg']:.2f} kg, wheel r {lr.WHEEL_R * 1000:.0f} mm, wheel peak {info['wheel_motor']['peak_nm']} N m")
        for h in heights:
            sc = S.Scenario(f'curb{h}', f'Drive up a {h} mm kerb at {speed} m/s', 9.0,
                            lambda t, v=speed: Command(height=0.6, speed=S.ramp_profile(t, 1, 1.0, v) if t < 6 else 0.0),
                            terrain=S.curb(h / 1000), must_reach_x=1.5)
            t0 = time.time()
            res = S.run(xml, info, sc, video=(OUT / f'curb_{name}_{h}.mp4') if video else None)
            wl = res['motors']['wheel_l']
            row['heights'][str(h)] = {'pass': res['pass'], 'reasons': res['reasons'], 'x_max_m': res['x_max_m'], 'max_theta_deg': res['max_theta_deg'],
                                      'fell_at': res.get('fell_at'), 'wheel_peak_nm': wl['peak_torque_nm'], 'wheel_of_peak': wl['of_peak'],
                                      'wheel_saturated_s': wl['saturated_s'], 'body_impact_peak_n': res.get('body_impact_peak_n'),
                                      'wall_s': round(time.time() - t0, 1)}
            print(f"  kerb {h:3} mm: {'PASS' if res['pass'] else 'FAIL'}  x_max {res['x_max_m']:.2f} m  lean {res['max_theta_deg']:.1f} deg  "
                  f"wheel {wl['peak_torque_nm']:.1f} N m ({wl['of_peak'] * 100:.0f} % of peak, saturated {wl['saturated_s']} s)  {res['reasons']}")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f'curb_{name}.json').write_text(json.dumps(row, indent=1) + '\n')
        out[name] = row
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('rig', 'curb', 'fit'))
    ap.add_argument('--wheels', nargs='*', default=list(CANDIDATES))
    ap.add_argument('--half-mass', type=float, default=16.25, help='kg a leg carries with the BotWheel (D65: 16.25); the extra wheel mass is added')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--v-static', type=float, default=38.0)
    ap.add_argument('--heights', nargs='*', type=float, default=[25, 40, 50, 60, 80, 100])
    ap.add_argument('--speed', type=float, default=0.6)
    ap.add_argument('--video', action='store_true')
    a = ap.parse_args(argv)
    if a.mode == 'rig':
        res = rig(a.wheels, a.half_mass, a.only, a.v_static)
    elif a.mode == 'curb':
        res = curb(a.wheels, a.heights, a.speed, a.video)
    else:
        res = fit(a.wheels)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f'summary_{a.mode}.json'
    prev = json.loads(f.read_text()) if f.is_file() else {}
    prev.update(res)
    f.write_text(json.dumps(prev, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
