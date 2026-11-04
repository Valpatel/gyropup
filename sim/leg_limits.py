"""The leg's protection limits: one source for the balance firmware (firmware/balance/tools/gen_limits.py writes
include/gp/gp_limits.h from the JSON), the leg rig's laptop controller (rig/leg_control.py), the simulations and the
browser playground (designer/leg_limits.js). docs/leg-protection.md is the audit these numbers come from.

    python -m sim.leg_limits                 # exports/leg/limits.json from the committed FEA, derating and jump sweep
    python -m sim.leg_limits --sweep         # also re-runs the jump at each cap in MuJoCo (sim/leg_rig.py), ~1 min

What is in it:

* **Torque, per build profile.** A motor's torque is limited by the weakest part it loads, at that part's safety
  factor (cad/leg_studies.py's targets: 2 every day, 1.2 for a rare event). The FEA is linear, so a row run at a
  motor torque T0 with factor SF carries T0 x SF / target at its target. Three numbers per profile:
  - `everyday_nm`: any pose, any time, including a motor driving its link into a stop post (E2, E3, E3o, E3i, the
    stop pin's bearing): the firmware's cap outside the jump's push;
  - `peak_nm`: the jump's push only (the legs mid-range, at least 15 deg from every stop, at most
    GP_JUMP_PUSH_MAX_S): the rare-event rows the push loads (a stalled leg at full torque R2, the hub's dowels, and
    the knees and links through the push's joint forces from the jump sweep), and the RS-04's own 120 N m peak;
  - `rms_nm`: the continuous limit, a mean square over the winding's time constant: the RS-04's stall table rated
    row (manual 1.3 item 14), as the motor heat model (sim/motor_thermal.py, issue #194/#195) takes it.
  The PLA bench leg's cap is the motor-day derating's (tools/motor_day.py: the PLA rows at every-day targets).
* **Soft stops.** Each motor's angle window inside its hard stop posts (+3 / -97 deg front, mirrored rear: D38):
  no torque into a stop past `soft_margin_deg` from it, and a braking torque when it approaches a stop faster than
  the stop can take at the every-day torque (the TPU sleeve's stiffness and the link's inertia, below).
* **A joint-angle window.** A motor measured further past its stop than the stop's own squeeze at the fault torque
  (a broken post, a slipped zero): the firmware goes limp.
* **The command window.** The leg length the controller may be asked for at each lean: inside the stop window with
  the soft margin, and at least `dead_point_min_deg` from a dead point (D38: 33 deg over 130-380 mm).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
for _p in (R, R / 'cad'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import fivebar as fb  # noqa: E402

OUT = R / 'exports' / 'leg' / 'limits.json'
FEA = R / 'exports' / 'leg' / 'fea' / 'summary.json'
DERATING = R / 'exports' / 'motor-day' / 'derating.json'
THERMAL = R / 'exports' / 'leg' / 'thermal' / 'motor_thermal.json'   # issue #195's model, once merged
SWEEP_CAPS = (30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0)
HALF_MASS = 18.75                 # kg a leg carries at D71's design mass
RS04_PEAK = 120.0                 # N m (catalog/leg_actuators.json, manual 1.3)
FEA_CAP, FEA_PEAK = 60.0, 120.0   # the motor torques the record's torque cases were run at (cad/leg_studies.py)
# The motor heat model's inputs (sim/motor_thermal.py INPUTS on the thermal/rs04-motor-heat branch, PR #195): used
# until exports/leg/thermal/motor_thermal.json is on dev, then read from it.
STALL_RATED_NM = 28.5             # manual 1.3 item 14: the stall table's rated (continuous) row
R_WC_K_PER_W = 0.4113             # winding to case, fitted to the manual's two ratings
C_W_J_PER_K = 73.4                # the winding's heat capacity, fitted to the overload table

SOFT_MARGIN_DEG = 2.0             # no torque into a stop inside this (the robot sits at 3.4 deg from its knee-out stops)
SOFT_ZONE_DEG = 10.0              # the approach-speed limit acts inside this distance from a stop
DEAD_POINT_MIN_DEG = 25.0         # the commanded pose's least angle from a dead point (D38's 33 at 130 mm, 30 at 380)
ANGLE_WINDOW_EXTRA_DEG = 2.0      # beyond the stop's squeeze at the fault torque: the measured-angle window
# The stop and the link as the leg rig's MuJoCo model has them (sim/leg_rig.py): the TPU sleeve's rotational stiffness
# at the motor, the rotor's reflected inertia (ARMATURE) and the upper link about its hub (cad mass properties).
STOP_K_NM_PER_RAD = 856.0
J_MOTOR_KG_M2 = 0.0243 + 0.0035   # armature + the upper link about its hub (0.65 kg, centre 55 mm, its own ~0.0015)


def load() -> dict:
    """exports/leg/limits.json, as committed."""
    return json.loads(OUT.read_text())


# ----------------------------------------------------------------------------------- torque per build profile

def _row(part, case, t0, sf, target, why):
    return {'part': part, 'case': case, 'at_nm': t0, 'sf': sf, 'target': target, 'nm': round(t0 * sf / target, 1), 'load': why}


def everyday_rows(fea: dict) -> list:
    """The record's every-day rows a motor's torque drives (target 2), each as the torque that leaves it at target."""
    res = {(r['part'], r['case']): r for r in fea['results']}
    t = fea['targets']['sf']
    rows = []
    for part, case, why in (('upper_link', 'E2', 'a motor at its cap against a stalled leg'),
                            ('upper_link', 'E3', 'a motor driving its link into a stop post'),
                            ('hip_frame', 'E3o', 'a motor into the knee-out stop post (its ear past the motor ring)'),
                            ('hip_frame', 'E3i', 'a motor into the knee-in stop post (between the motors)'),
                            ('output_adapter', 'E1', 'the cap through the 6061 adapter with a quarter of the landing moment')):
        r = res.get((part, case))
        if r:
            rows.append(_row(part, case, FEA_CAP, r['safety_factor'], t, why))
    sp = fea['joints']['stop_post']['E3']
    rows.append(_row('stop_post', 'E3 pin bearing', sp['stop_nm'], sp['bearing']['sf'], sp['bearing']['target'],
                     "the stop pin's bearing in the printed web"))
    rows.append(_row('stop_post', 'E3 pin bending', sp['stop_nm'], sp['pin']['sf'], sp['pin']['target'], 'the 52100 stop pin in bending'))
    return rows


def peak_torque_rows(fea: dict) -> list:
    """The rare-event rows the push's motor torque drives directly (target 1.2)."""
    res = {(r['part'], r['case']): r for r in fea['results']}
    t = fea['targets']['sf_rare']
    rows = [_row('rs04', 'peak', RS04_PEAK, 1.0, 1.0, "the RS-04's rated peak (manual 1.3; its stall table trips at 120 N m in 1 s)")]
    for part, case, why in (('upper_link', 'R2', 'a motor at full torque against a stalled leg'),
                            ('output_adapter', 'R2', 'the 6061 adapter at full torque against a stalled leg')):
        r = res.get((part, case))
        if r:
            rows.append(_row(part, case, FEA_PEAK, r['safety_factor'], t, why))
    j = fea['joints']['R1']
    for hub in ('hub_rear', 'hub_front'):
        for c in fea['joints']['checks']:
            if c['case'] == 'R1' and c['joint'] == hub and c['check'] == 'dowel bearing':
                rows.append(_row(f'AO-L {hub}', 'R1 dowel bearing', j[hub]['torque_nm'], c['sf'], 1.2,
                                 'the AO-L face: the hub torque through its dowels (the M5 clamp friction ignored)'))
    return rows


def knee_capacity(fea: dict) -> dict:
    """The knee force (N) the R1 rows driven by the knees' load can take at their targets: the record ran R1 at the
    rig's dynamic knee peak (cases.R1.from), so a row's capacity is that force x SF / target."""
    base = 574.0
    res = {(r['part'], r['case']): r for r in fea['results']}
    caps = []
    for part in ('front_link', 'leg', 'upper_link'):
        r = res.get((part, 'R1'))
        if r:
            caps.append({'row': f'{part} R1', 'n': round(base * r['safety_factor'] / r['target'], 1), 'sf': r['safety_factor'], 'target': r['target']})
    for c in fea['joints']['checks']:
        if c['case'] == 'R1' and c['joint'].startswith('knee_'):
            caps.append({'row': f"{c['joint']} {c['check']}", 'n': round(base * c['sf'] / c['target'], 1), 'sf': c['sf'], 'target': c['target']})
    caps.sort(key=lambda c: c['n'])
    return {'at_n': base, 'rows': caps, 'weakest': caps[0]}


def push_limited_peak(sweep: list, cap_n: float) -> dict:
    """The highest cap whose jump keeps the knees (push and landing) at or under cap_n, interpolated in the sweep."""
    pts = sorted(((r['cap_nm'], max(r['knee_push_n'], r['knee_after_n'])) for r in sweep))
    best = None
    for (c0, k0), (c1, k1) in zip(pts, pts[1:]):
        if k0 <= cap_n < k1:
            best = c0 + (c1 - c0) * (cap_n - k0) / (k1 - k0)
            break
    if best is None:
        best = pts[-1][0] if pts[-1][1] <= cap_n else (pts[0][0] if pts[0][1] > cap_n else None)
    return {'nm': round(best, 1) if best is not None else None, 'knee_limit_n': cap_n, 'governing': 'knee force in the push or the landing'}


def thermal_inputs() -> dict:
    if THERMAL.exists():
        d = json.loads(THERMAL.read_text())
        i = d['inputs']
        rated = i['stall_rated_nm']['v']
        cal = d.get('calibration', {})
        r_wc, c_w = cal.get('R_wc', R_WC_K_PER_W), cal.get('C_w', C_W_J_PER_K)
        return {'rms_nm': rated, 'tau_s': round(r_wc * c_w, 1), 'source': 'exports/leg/thermal/motor_thermal.json (sim/motor_thermal.py)',
                'pending': False}
    return {'rms_nm': STALL_RATED_NM, 'tau_s': round(R_WC_K_PER_W * C_W_J_PER_K, 1), 'pending': True,
            'source': "RS-04 manual 1.3 item 14 (the stall table's rated row) and the winding's fitted R_wc x C_w, as the motor "
                      'heat model takes them (sim/motor_thermal.py, PR #195, not yet merged: re-run this when it is)'}


def torque_profiles(fea: dict, derating: dict, sweep: list) -> dict:
    day = everyday_rows(fea)
    peak_rows = peak_torque_rows(fea)
    knees = knee_capacity(fea)
    knee_peak = push_limited_peak(sweep, knees['weakest']['n']) if sweep else {'nm': None}
    day_w = min(day, key=lambda r: r['nm'])
    pk = [{**r} for r in peak_rows]
    if knee_peak['nm'] is not None:
        pk.append({'part': knees['weakest']['row'].split()[0], 'case': 'R1 (knee force)', 'nm': knee_peak['nm'],
                   'load': f"the jump's knee force reaches the weakest knee-driven R1 row's {knees['weakest']['n']:.0f} N "
                           f"({knees['weakest']['row']}, SF {knees['weakest']['sf']} at {knees['at_n']:.0f} N, target {knees['weakest']['target']})"})
    pk_w = min(pk, key=lambda r: r['nm'])
    th = thermal_inputs()
    everyday = math.floor(day_w['nm'])
    peak = max(everyday, math.floor(pk_w['nm']))
    rows = derating['caps']
    caps = sorted(float(c) for c in rows)
    pla = derating['pla_cap_nm']
    nxt = next((c for c in caps if c > pla), None)
    first = rows[f'{nxt}']['worst'] if nxt is not None else None
    robot = {'title': "PA6-CF printed links and hip frame (D33, D38), CNC 6061 output adapters (D46): today's record",
             'everyday_nm': float(everyday), 'peak_nm': float(peak), 'rms_nm': th['rms_nm'], 'rms_tau_s': th['tau_s'],
             'peak_max_s': 0.35, 'motor_limit_torque_nm': float(peak),
             'everyday_governing': day_w, 'peak_governing': pk_w, 'everyday_rows': day, 'peak_rows': pk, 'knee_capacity': knees,
             'rms_source': th['source'], 'rms_pending': th['pending'],
             'source': 'exports/leg/fea/summary.json (cad/leg_studies.py), the jump sweep below'}
    bench = {'title': 'PLA bench leg on the boom stand (docs/motor-day.md)',
             'everyday_nm': float(pla), 'peak_nm': float(pla), 'rms_nm': th['rms_nm'], 'rms_tau_s': th['tau_s'],
             'peak_max_s': 0.35, 'motor_limit_torque_nm': float(pla),
             'first_failure': {'cap_nm': nxt, 'row': first,
                               'note': f'at {nxt:g} N m the weakest PLA row falls under its every-day target' if nxt else None},
             'rms_note': 'the PLA face, not the motor, sets the continuous limit on the bench: stop when a motor case passes 50 C '
                         '(sim/motor_thermal.py bench limits, PR #195); the firmware cannot see the case temperature',
             'source': 'exports/motor-day/derating.json (tools/motor_day.py: PLA strength 25 MPa, every-day targets at the stand mass)'}
    return {'pla_bench': bench, 'robot': robot}


# ----------------------------------------------------------------------------------- kinematic windows

def _deg(a):
    return round(math.degrees(a), 3)


def stops() -> dict:
    fo, fi, ro, ri = fb.stop_angles()
    return {'front': (fi, fo), 'rear': (ro, ri)}   # (lo, hi) per motor, radians: rear angles run -183 .. -83 deg


def dead_point_margin(phi1: float, phi2: float):
    """The least angle (deg) between a link pair that would line up at a dead point: each knee (upper vs lower link)
    and the apex (the two lower links). None if the lower links cannot meet."""
    j = fb.fk(phi1, phi2)
    if j is None:
        return None
    A, B, C, D, E = (j[k] for k in 'ABCDE')

    def ang(u, v):
        c = (u[0] * v[0] + u[1] * v[1]) / math.hypot(*u) / math.hypot(*v)
        return math.degrees(math.acos(max(-1.0, min(1.0, c))))
    a = [ang((C[0] - A[0], C[1] - A[1]), (E[0] - C[0], E[1] - C[1])), ang((D[0] - B[0], D[1] - B[1]), (E[0] - D[0], E[1] - D[1])),
         ang((C[0] - E[0], C[1] - E[1]), (D[0] - E[0], D[1] - E[1]))]
    return min(min(x, 180.0 - x) for x in a)


def box_survey(n: int = 120) -> dict:
    """Every pose the hard stops allow: reachable, never crossed (the front knee behind the rear), the least dead-point
    margin and where it is."""
    s = stops()
    (f0, f1), (r0, r1) = s['front'], s['rear']
    worst, crossed, unreachable, Ls = (180.0, None), 0, 0, []
    for i in range(n + 1):
        for k in range(n + 1):
            p1, p2 = f0 + (f1 - f0) * i / n, r0 + (r1 - r0) * k / n
            j = fb.fk(p1, p2)
            if j is None:
                unreachable += 1
                continue
            crossed += j['C'][0] < j['D'][0]
            Ls.append(math.hypot(*j['E']))
            m = dead_point_margin(p1, p2)
            if m < worst[0]:
                worst = (m, [_deg(p1), _deg(p2)])
    return {'unreachable': unreachable, 'crossed': crossed, 'L_mm': [round(min(Ls), 1), round(max(Ls), 1)],
            'dead_point_min_deg': round(worst[0], 1), 'dead_point_min_at_deg': worst[1]}


def pose_ok(L_m: float, lean: float, margin_rad: float, dead_min: float) -> bool:
    s = stops()
    q = fb.stance(L_m * 1000.0, math.degrees(lean))
    if q is None:
        return False
    (f0, f1), (r0, r1) = s['front'], s['rear']
    if not (f0 + margin_rad <= q[0] <= f1 - margin_rad and r0 + margin_rad <= q[1] <= r1 - margin_rad):
        return False
    m = dead_point_margin(*q)
    return m is not None and m >= dead_min


def command_window(leans=None, margin_deg: float = SOFT_MARGIN_DEG, dead_min: float = DEAD_POINT_MIN_DEG) -> list:
    """[lean rad, L_min m, L_max m] for each lean: the leg lengths the controller may be commanded (1 mm steps)."""
    leans = leans or [round(-0.5 + 0.05 * k, 2) for k in range(21)]
    out = []
    for lean in leans:
        ok = [L / 1000.0 for L in range(90, 400) if pose_ok(L / 1000.0, lean, math.radians(margin_deg), dead_min)]
        out.append([lean, round(min(ok), 3), round(max(ok), 3)] if ok else [lean, None, None])
    return out


def window_at(table: list, lean: float):
    """(L_min, L_max) at a lean, linear between the table's rows; the end rows outside them."""
    rows = [r for r in table if r[1] is not None]
    if lean <= rows[0][0]:
        return rows[0][1], rows[0][2]
    for a, b in zip(rows, rows[1:]):
        if a[0] <= lean <= b[0]:
            w = (lean - a[0]) / (b[0] - a[0])
            return a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2])
    return rows[-1][1], rows[-1][2]


# ----------------------------------------------------------------------------------- the soft stops (C: gp_limits.c)

def approach_limit(d: float, everyday_nm: float, k: float = STOP_K_NM_PER_RAD, J: float = J_MOTOR_KG_M2) -> float:
    """The fastest a motor may approach a stop d radians away (rad/s): it must reach the stop no faster than the stop
    takes at the every-day torque (1/2 J w^2 = T^2 / 2k), braking at the every-day torque on the way."""
    w_contact = everyday_nm / math.sqrt(k * J)
    return math.sqrt(w_contact ** 2 + 2.0 * (everyday_nm / J) * max(0.0, d))


def soft_stop(tau: float, phi: float, omega: float, lo: float, hi: float, everyday_nm: float,
              margin: float = math.radians(SOFT_MARGIN_DEG), zone: float = math.radians(SOFT_ZONE_DEG), kd: float = 20.0) -> float:
    """One motor's torque with the soft stops: inside `margin` of a stop no torque pushes further into it; inside
    `zone`, approaching a stop faster than approach_limit() brakes with kd x the excess speed (at most the every-day
    torque). + torque and + speed are towards `hi`."""
    for sgn, d in ((1.0, hi - phi), (-1.0, phi - lo)):         # towards hi: +, towards lo: -
        if d >= zone:
            continue
        if d < margin and tau * sgn > 0.0:
            tau = 0.0
        excess = omega * sgn - approach_limit(d - margin, everyday_nm)
        if excess > 0.0:                                        # at least this much braking, away from the stop
            tau = sgn * min(tau * sgn, -min(everyday_nm, kd * excess))
    return tau


def angle_window(profile: dict) -> float:
    """How far past a hard stop (rad) a motor may be measured before the firmware goes limp: the sleeve's squeeze at the
    fault case's stop torque (the rig's undamped power cut) plus ANGLE_WINDOW_EXTRA_DEG."""
    fea = json.loads(FEA.read_text())
    t_fault = fea['cases']['R3']['stop_nm']
    return t_fault / STOP_K_NM_PER_RAD + math.radians(ANGLE_WINDOW_EXTRA_DEG)


# ----------------------------------------------------------------------------------- the jump sweep (MuJoCo)

def jump_sweep(caps=SWEEP_CAPS, half_mass: float = HALF_MASS, motor_peak: float | None = None) -> list:
    """The rig's jump (sim/leg_rig.py) at each cap. motor_peak replaces the RS-04's 120 N m peak (same no-load speed):
    what a motor rated at the cap itself would do."""
    from sim import leg_rig as lr
    out = []
    keep = lr.LEG_PEAK
    for c in caps:
        sc = lr.Scenario('jump', f'jump at {c:g} N m', 3.0, cap=None if c >= lr.LEG_PEAK else c)
        try:
            if motor_peak:
                lr.LEG_PEAK = motor_peak
            r = lr.run(sc, half_mass)
        finally:
            lr.LEG_PEAK = keep
        ph = r['phase_peaks']
        p, a = ph.get('push', {}), ph.get('after', {})
        out.append({'cap_nm': c, **({'motor_peak_nm': motor_peak} if motor_peak else {}), 'jump_mm': r['jump_height_mm'], 'peak_motor_speed_rad_s': r['peak_motor_speed_rad_s'],
                    'gearbox_push_nm': p.get('gearbox_nm'), 'gearbox_after_nm': a.get('gearbox_nm'),
                    'knee_push_n': max(p.get('knee_f_n', 0), p.get('knee_r_n', 0)), 'knee_after_n': max(a.get('knee_f_n', 0), a.get('knee_r_n', 0)),
                    'hip_push_n': max(p.get('hip_f_n', 0), p.get('hip_r_n', 0)), 'apex_push_n': p.get('apex_n'),
                    'axle_peak_n': r['peak_axle_force_n'], 'L_range_mm': r['L_range_mm']})
        print(f"cap {c:5.1f}: jump {r['jump_height_mm']} mm, gearbox push {p.get('gearbox_nm')} / after {a.get('gearbox_nm')} N m, "
              f"knee push {out[-1]['knee_push_n']:.0f} / after {out[-1]['knee_after_n']:.0f} N", flush=True)
    return out


# ----------------------------------------------------------------------------------- the file

def build(sweep: list | None = None) -> dict:
    fea = json.loads(FEA.read_text())
    derating = json.loads(DERATING.read_text())
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    js = old.get('jump_sweep', {})
    sweep = sweep if sweep is not None else {'runs': js.get('runs', []), 'at_limits': js.get('at_limits', []), 'capped_motor': js.get('capped_motor', [])}
    prof = torque_profiles(fea, derating, sweep['runs'])
    s = stops()
    win = angle_window(prof['robot'])
    survey = box_survey()
    table = command_window()
    approach = {'stop_k_nm_per_rad': STOP_K_NM_PER_RAD, 'j_kg_m2': J_MOTOR_KG_M2,
                'contact_rad_s': {k: round(p['everyday_nm'] / math.sqrt(STOP_K_NM_PER_RAD * J_MOTOR_KG_M2), 2) for k, p in prof.items()},
                'stop_energy_j': {k: round(p['everyday_nm'] ** 2 / (2 * STOP_K_NM_PER_RAD), 2) for k, p in prof.items()}}
    return {
        'about': 'Generated by sim/leg_limits.py; docs/leg-protection.md explains every number. Regenerate, never edit.',
        'profiles': prof,
        'stops_deg': {k: [_deg(v[0]), _deg(v[1])] for k, v in s.items()},
        'soft_stop': {'margin_deg': SOFT_MARGIN_DEG, 'zone_deg': SOFT_ZONE_DEG, 'kd_nm_s_per_rad': 20.0, **approach},
        'angle_window_deg': round(math.degrees(win), 2),
        'stop_box': survey,
        'command': {'dead_point_min_deg': DEAD_POINT_MIN_DEG, 'margin_deg': SOFT_MARGIN_DEG, 'window': table,
                    'columns': ['lean rad (+ = wheel forward)', 'L_min m', 'L_max m']},
        'jump_sweep': {'half_mass_kg': HALF_MASS, 'bus_v': 36.0, 'source': 'sim/leg_rig.py jump at each cap (python -m sim.leg_limits --sweep)',
                       'runs': sweep['runs'], 'at_limits': sweep['at_limits'],
                       'capped_motor': sweep['capped_motor'],
                       'capped_motor_note': 'a motor whose peak is the cap itself (the RS-04 no-load speed): its torque falls '
                                            'from the cap at stall, where the capped RS-04 still has the cap up to half speed'},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--sweep', action='store_true', help='re-run the jump sweep in MuJoCo')
    a = ap.parse_args()
    sweep = None
    if a.sweep:
        runs = jump_sweep()
        prof = torque_profiles(json.loads(FEA.read_text()), json.loads(DERATING.read_text()), runs)['robot']
        sweep = {'runs': runs, 'at_limits': jump_sweep(sorted({prof['everyday_nm'], prof['peak_nm']})),
                 'capped_motor': jump_sweep((60.0,), motor_peak=60.0)}
    data = build(sweep)
    OUT.write_text(json.dumps(data, indent=1) + '\n')
    rb, pl = data['profiles']['robot'], data['profiles']['pla_bench']
    print(f"-> {OUT.relative_to(R)}: robot every day {rb['everyday_nm']:g} N m ({rb['everyday_governing']['part']} {rb['everyday_governing']['case']}), "
          f"peak {rb['peak_nm']:g} N m ({rb['peak_governing']['part']} {rb['peak_governing']['case']}), rms {rb['rms_nm']:g} N m; PLA bench {pl['everyday_nm']:g} N m")


if __name__ == '__main__':
    main()
