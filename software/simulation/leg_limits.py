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
  - `peak_nm`: the jump's push only (D78, 2026-11-04: the every-day cap; `push_allows_nm` is what the push rows
    would allow) (the legs mid-range, at least 15 deg from every stop, at most
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

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[2]))


import argparse
import json
import math
import re
import sys
from pathlib import Path

R = (Path(__file__).resolve().parents[2])
for _p in (R, (R / 'hardware/cad')):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import hardware.cad.legs.fivebar as fb  # noqa: E402

OUT = (R / 'hardware/exports/leg/limits.json')
FEA = (R / 'hardware/exports/leg/fea/summary.json')
DERATING = (R / 'hardware/exports/motor-day/derating.json')
THERMAL = (R / 'hardware/exports/leg/thermal/motor_thermal.json')   # the motor heat model (#195)
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
DEAD_POINT_MIN_DEG = 25.0         # the commanded pose's least angle from a dead point (D38's 33 at 130 mm, 30 at 380)
ANGLE_WINDOW_EXTRA_DEG = 2.0      # beyond the stop's squeeze at the fault torque: the measured-angle window
DEAD_LIMP_DEG = 3.0               # a measured pose this close to a dead point: limp (the stops alone leave 6.1 deg)
PEAK_IS_EVERYDAY = True           # D78 (the owner, 2026-11-04): no push window above the every-day cap
JUMP_HOT_SHARE = 0.8              # no jump while a motor's rms torque is over this share of the rms limit
SOFT_KD = 20.0                    # N m s/rad of approach speed over the limit: the soft stop's brake
# The stop as the leg rig's MuJoCo model has it (sim/leg_rig.py): the TPU sleeve's rotational stiffness at the motor.
# The inertia a motor drives into it is not the rotor and its upper link alone (0.0278 kg m^2): through the five-bar it
# also swings the lower links and the 4 kg wheel. inertia_survey() takes the rig model's mass matrix over the whole stop
# box (python -m sim.leg_limits --sweep) and the soft stops use its worst pose, as committed in limits.json.
STOP_K_NM_PER_RAD = 856.0
NO_LOAD_RAD_S = 15.71             # the RS-04's no-load speed at 36 V (sim/leg_rig.py LEG_OMEGA)
J_ROTOR_LINK_KG_M2 = 0.0243 + 0.0035   # armature + the upper link about its hub: the part that is always there
_J = None


def j_leg() -> float:
    """The inertia (kg m^2) the soft stops assume behind a stop: the survey's bound, as committed."""
    global _J
    if _J is None:
        _J = json.loads(OUT.read_text())['soft_stop']['j_kg_m2']
    return _J


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


def r1_knee_force(fea: dict) -> float:
    """The knee force (N) the FEA record ran its R1 case at, from the record itself (cases.R1.from)."""
    m = re.search(r'knees at ([0-9.]+) N', fea['cases']['R1'].get('from', ''))
    if not m:
        raise ValueError('exports/leg/fea/summary.json cases.R1.from no longer names the knee force R1 was run at')
    return float(m.group(1))


def hip_capacity(fea: dict) -> dict:
    """The hip bearing force (N) the hip frame's R1 row takes at its target. The upper link is a two-pin member with a
    couple at its hub, so the hub's force is the knee's: the record ran R1 at r1_knee_force() on the hips too."""
    base = r1_knee_force(fea)
    r = next(x for x in fea['results'] if x['part'] == 'hip_frame' and x['case'] == 'R1')
    return {'row': 'hip_frame R1', 'at_n': base, 'n': round(base * r['safety_factor'] / r['target'], 1), 'sf': r['safety_factor'], 'target': r['target']}


def knee_capacity(fea: dict) -> dict:
    """The knee force (N) the R1 rows driven by the knees' load can take at their targets: the record ran R1 at the
    rig's dynamic knee peak (cases.R1.from), so a row's capacity is that force x SF / target."""
    base = r1_knee_force(fea)
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


def push_limited_peak(sweep: list, cap_n: float, key: str = 'knee') -> dict:
    """The highest cap whose jump keeps the knees (or the hips: key='hip'), push and landing, at or under cap_n,
    interpolated in the sweep."""
    pts = sorted(((r['cap_nm'], max(r[f'{key}_push_n'], r.get(f'{key}_after_n', 0.0))) for r in sweep))
    best = None
    for (c0, k0), (c1, k1) in zip(pts, pts[1:]):
        if k0 <= cap_n < k1:
            best = c0 + (c1 - c0) * (cap_n - k0) / (k1 - k0)
            break
    if best is None:
        best = pts[-1][0] if pts[-1][1] <= cap_n else (pts[0][0] if pts[0][1] > cap_n else None)
    return {'nm': round(best, 1) if best is not None else None, f'{key}_limit_n': cap_n, 'governing': f'{key} force in the push or the landing'}


def thermal_inputs() -> dict:
    """The continuous limit and its time constant from the motor heat model (sim/motor_thermal.py, merged in #195), and
    what it says about each build's frame; the manual's numbers if the model's file is absent."""
    if THERMAL.exists():
        d = json.loads(THERMAL.read_text())
        cal = d.get('calibration', {})
        r_wc, c_w = cal.get('r_wc_k_per_w', R_WC_K_PER_W), cal.get('c_w_j_per_k', C_W_J_PER_K)
        rec = {r['option']: r for r in d.get('recommendation', {}).get('rows', [])}
        hot = d.get('hot_day', {})
        b = rec.get('B_pa6cf', {})
        passing = [o for o, r in rec.items() if r.get('pass_winding') and r.get('pass_face')]
        bench = d.get('bench', {})
        lim25 = next((x for x in bench.get('limits', []) if x.get('room_c') == 25.0), None)
        cap_run = bench.get('runs', {}).get('cap', {})
        return {'rms_nm': d['inputs']['stall_rated_nm']['v'], 'tau_s': round(r_wc * c_w, 1), 'pending': False,
                'source': "exports/leg/thermal/motor_thermal.json (sim/motor_thermal.py, #195): the RS-04 manual 1.3 item 14 "
                          "stall table's rated row, and the winding's fitted R_wc x C_w",
                'frame': {'case': hot.get('case'), 'ambient_c': hot.get('ambient_c'), 'target_winding_c': d['recommendation']['target_winding_c'],
                          'pa6cf_winding_c': b.get('winding_c'), 'pa6cf_face_c': b.get('face_c'), 'pa6cf_face_limit_c': b.get('face_limit_c'),
                          'options_passing': passing},
                'bench': {'face_limit_c': bench.get('face_limit_c'), 'hold_nm_25c': lim25 and lim25['torque_nm'],
                          'cap_nm': bench.get('cap_nm'), 'cap_face_limit_min': cap_run.get('t_face_limit_s') and round(cap_run['t_face_limit_s'] / 60)}}
    return {'rms_nm': STALL_RATED_NM, 'tau_s': round(R_WC_K_PER_W * C_W_J_PER_K, 1), 'pending': True, 'frame': None, 'bench': None,
            'source': "RS-04 manual 1.3 item 14 (the stall table's rated row) and the winding's fitted R_wc x C_w, as the motor "
                      'heat model takes them (sim/motor_thermal.py, #195: absent here, re-run when it is present)'}


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
    hip = hip_capacity(fea)
    hip_peak = push_limited_peak(sweep, hip['n'], 'hip') if sweep else {'nm': None}
    if hip_peak['nm'] is not None:
        pk.append({'part': 'hip_frame', 'case': 'R1 (hip force)', 'nm': hip_peak['nm'],
                   'load': f"the jump's hip bearing force reaches the hip frame's R1 allowable {hip['n']:.0f} N (SF {hip['sf']} at "
                           f"{hip['at_n']:.0f} N, target {hip['target']}); 120 means the sweep never reaches it"})
    pk_w = min(pk, key=lambda r: r['nm'])
    th = thermal_inputs()
    everyday = math.floor(day_w['nm'])
    # The owner's decision (D78, 2026-11-04): the every-day cap everywhere, the jump's push and each motor's own
    # limit_torque too. The rare-event rows would allow more in the push (push_allows_nm); that headroom is kept.
    push_allows = max(everyday, math.floor(pk_w['nm']))
    peak = everyday if PEAK_IS_EVERYDAY else push_allows
    rows = derating['caps']
    caps = sorted(float(c) for c in rows)
    pla = derating['pla_cap_nm']
    nxt = next((c for c in caps if c > pla), None)
    first = rows[f'{nxt}']['worst'] if nxt is not None else None
    robot = {'title': "PA6-CF printed links and hip frame (D33, D38), CNC 6061 output adapters (D46): today's record",
             'everyday_nm': float(everyday), 'peak_nm': float(peak), 'rms_nm': th['rms_nm'], 'rms_tau_s': th['tau_s'],
             'peak_max_s': 0.35, 'motor_limit_torque_nm': float(peak), 'push_allows_nm': float(push_allows),
             'peak_note': 'the every-day cap in the push too, by the owner\'s decision (D78, 2026-11-04): the push rows would '
                          f'allow {push_allows} N m for {push_allows - everyday} N m more and about 4 mm of jump',
             'everyday_governing': day_w, 'peak_governing': pk_w, 'everyday_rows': day, 'peak_rows': pk, 'knee_capacity': knees, 'hip_capacity': hip,
             'rms_source': th['source'], 'rms_pending': th['pending'], 'thermal_frame': th['frame'],
             'rms_note': "the motor's own continuous rating: the heat model finds the PA6-CF hip frame insulates the motor so that "
                         'even driving and balancing (under 20 N m rms) overheats it on a hot day, a design fix (an aluminium frame '
                         "plate, #195's options C or E), not a torque cap below the standing torque; the firmware's motor "
                         'temperature sit (80 C) and jump refusal (70 C) cover it until then',
             'source': 'exports/leg/fea/summary.json (cad/leg_studies.py), the jump sweep below'}
    bench = {'title': 'PLA bench leg on the boom stand (docs/motor-day.md)',
             'everyday_nm': float(pla), 'peak_nm': float(pla), 'rms_nm': th['rms_nm'], 'rms_tau_s': th['tau_s'],
             'peak_max_s': 0.35, 'motor_limit_torque_nm': float(pla),
             'first_failure': {'cap_nm': nxt, 'row': first,
                               'note': f'at {nxt:g} N m the weakest PLA row falls under its every-day target' if nxt else None},
             'rms_note': 'the PLA face, not the motor, sets the continuous limit on the bench: stop when a motor case passes 50 C '
                         '(sim/motor_thermal.py bench limits, #195); the firmware cannot see the case temperature',
             'thermal_bench': th['bench'],
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


_TABLE = None


def clamp_L(L_m: float, lean: float, lean_measured: float | None = None, table: list | None = None) -> float:
    """A commanded leg length clamped to the window at its commanded lean and, given it, at the leg's measured lean:
    their overlap, so the target is inside the stops whichever lean the leg is at (C: gp_guard_clamp_L)."""
    global _TABLE
    if table is None:
        if _TABLE is None:
            _TABLE = load()['command']['window']
        table = _TABLE
    lo, hi = window_at(table, lean)
    if lean_measured is not None:
        lo2, hi2 = window_at(table, lean_measured)
        lo, hi = max(lo, lo2), min(hi, hi2)
    return min(hi, max(lo, L_m))


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

def approach_limit(d: float, everyday_nm: float, k: float = STOP_K_NM_PER_RAD, J: float | None = None) -> float:
    """The fastest a motor may approach a stop d radians away (rad/s): it must reach the stop no faster than the stop
    takes at the every-day torque (1/2 J w^2 = T^2 / 2k, so its peak is T), braking at the every-day torque on the
    way. J: the leg's worst-case inertia at the motor (j_leg())."""
    J = j_leg() if J is None else J
    w_contact = everyday_nm / math.sqrt(k * J)
    return math.sqrt(w_contact ** 2 + 2.0 * (everyday_nm / J) * max(0.0, d))


def soft_stop(tau: float, phi: float, omega: float, lo: float, hi: float, everyday_nm: float,
              margin: float = math.radians(SOFT_MARGIN_DEG), kd: float = SOFT_KD, J: float | None = None) -> float:
    """One motor's torque with the soft stops: inside `margin` of a stop no torque pushes further into it; anywhere,
    approaching a stop faster than approach_limit() brakes with kd x the excess speed (at most the every-day torque).
    + torque and + speed are towards `hi`. Far from a stop the limit is above anything the motor reaches, so mid-range
    is untouched unless the leg is racing towards a stop it could not stop short of."""
    for sgn, d in ((1.0, hi - phi), (-1.0, phi - lo)):         # towards hi: +, towards lo: -
        if d < margin and tau * sgn > 0.0:
            tau = 0.0
        excess = omega * sgn - approach_limit(d - margin, everyday_nm, J=J)
        if excess > 0.0:                                        # at least this much braking, away from the stop
            tau = sgn * min(tau * sgn, -min(everyday_nm, kd * excess))
    return tau


def angle_window(profile: dict) -> float:
    """How far past a hard stop (rad) a motor may be measured before the firmware goes limp: the sleeve's squeeze at the
    fault case's stop torque (the rig's undamped power cut) plus ANGLE_WINDOW_EXTRA_DEG."""
    fea = json.loads(FEA.read_text())
    t_fault = fea['cases']['R3']['stop_nm']
    return t_fault / STOP_K_NM_PER_RAD + math.radians(ANGLE_WINDOW_EXTRA_DEG)


# ----------------------------------------------------------------------------------- the turn (yaw rate)

MODEL_H = (R / 'software/firmware/balance/include/gp/gp_model.h')
SIM_V2 = (R / 'hardware/exports/body/sim-v2.json')
G = 9.81


def _model_define(name: str) -> float:
    m = re.search(rf'#define {name} ([-0-9.e]+)f?', MODEL_H.read_text())
    if not m:
        raise ValueError(f'{MODEL_H.name}: no #define {name}')
    return float(m.group(1))


def yaw_limits(everyday_nm: float, table: list | None = None) -> dict:
    """The turn the robot may be commanded at a speed (C: gp_guard_yaw_rate), from the wheel and leg limits:

    * the outer wheel: |v| + |w| W/2 at most the speed clamp's vmax (GP_G_SPEED_MARGIN of the wheel's no-load
      speed), the headroom the balance keeps on each wheel;
    * the lateral acceleration |v w|: the outer leg's load m g/2 + m a h/W at most what the leg holds at the every-day
      torque (the five-bar's Jacobian over the upright window), and the inner wheel keeping at least half its load
      (a <= g (W/2) / 2h, the tip-over margin of 2); the lower of the two.

    h is the hips' height at full height, above the centre of mass (conservative); m the whole robot."""
    track = json.loads(SIM_V2.read_text())['track_mm'] / 1000.0
    mass = _model_define('GP_MODEL_MASS_KG')
    r = _model_define('GP_WHEEL_R_M')
    ff = _model_define('GP_ROBOT_LEG_FF_N')
    h = _model_define('GP_H_MAX_M') + r
    table = table if table is not None else command_window()
    lo, hi = window_at(table, 0.0)
    cap, at = None, None
    for L in range(round(lo * 1000), round(hi * 1000) + 1):
        q = fb.stance(float(L), 0.0)
        J = fb.jacobian(*q)
        f = everyday_nm / (max(abs(J[1][0]), abs(J[1][1])) / 1000.0)
        if cap is None or f < cap:
            cap, at = f, L
    a_leg = (cap - ff) * track / (mass * h)
    a_tip = G * (track / 2) / (2 * h)
    a_lat = math.floor(min(a_leg, a_tip) * 100) / 100
    vmax = _model_define('GP_G_SPEED_MARGIN') * _model_define('GP_WHEEL_W_PER_V') * 36.0 * r
    return {'half_track_m': round(track / 2, 5), 'a_lat_m_s2': a_lat,
            'a_lat_governing': 'the inner wheel keeping half its load' if a_tip <= a_leg else "the outer leg at the every-day torque",
            'a_leg_m_s2': round(a_leg, 2), 'a_tip_half_m_s2': round(a_tip, 2),
            'leg_force_cap_n': round(cap, 1), 'leg_force_cap_at_mm': at, 'leg_ff_n': round(ff, 1), 'mass_kg': mass,
            'com_h_m': round(h, 3),
            'turn_in_place_rad_s_36v': round(vmax / (track / 2), 2),
            'at_speed_rad_s_36v': {f'{v:g}': round(yaw_rate_limit(v, vmax, track / 2, a_lat), 2) for v in (0.5, 1.0, 1.5, 2.0)},
            'source': 'firmware/balance/include/gp/gp_model.h (mass, wheel, heights, feed-forward), exports/body/sim-v2.json (track)'}


def yaw_rate_limit(v: float, vmax: float, half_track: float, a_lat: float) -> float:
    """The largest |yaw rate| (rad/s) at ground speed v (the larger of the commanded and the measured): the outer wheel
    inside vmax and the lateral acceleration inside a_lat (C: gp_guard_yaw_rate)."""
    v = abs(v)
    w = max(0.0, vmax - v) / half_track
    if v > 1e-6:
        w = min(w, a_lat / v)
    return w


def clamp_yaw(yaw_rate: float, v: float, vmax: float, yaw: dict | None = None) -> float:
    """A commanded yaw rate clamped (never refused) to yaw_rate_limit."""
    y = yaw or load()['yaw']
    w = yaw_rate_limit(v, vmax, y['half_track_m'], y['a_lat_m_s2'])
    return max(-w, min(w, yaw_rate))


# ----------------------------------------------------------------------------------- the jump sweep (MuJoCo)

def jump_sweep(caps=SWEEP_CAPS, half_mass: float = HALF_MASS, motor_peak: float | None = None) -> list:
    """The rig's jump (sim/leg_rig.py) at each cap. motor_peak replaces the RS-04's 120 N m peak (same no-load speed):
    what a motor rated at the cap itself would do."""
    from software.simulation import leg_rig as lr
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
                    'hip_push_n': max(p.get('hip_f_n', 0), p.get('hip_r_n', 0)), 'hip_after_n': max(a.get('hip_f_n', 0), a.get('hip_r_n', 0)),
                    'apex_push_n': p.get('apex_n'),
                    'axle_peak_n': r['peak_axle_force_n'], 'L_range_mm': r['L_range_mm']})
        print(f"cap {c:5.1f}: jump {r['jump_height_mm']} mm, gearbox push {p.get('gearbox_nm')} / after {a.get('gearbox_nm')} N m, "
              f"knee push {out[-1]['knee_push_n']:.0f} / after {out[-1]['knee_after_n']:.0f} N", flush=True)
    return out


# ----------------------------------------------------------------------------------- the leg's inertia at a motor (MuJoCo)

def _rig(half_mass: float = HALF_MASS):
    import mujoco
    from software.simulation import leg_rig as lr
    xml, _ = lr.mjcf(half_mass)
    m = mujoco.MjModel.from_xml_string(xml)
    return mujoco, lr, m, mujoco.MjData(m), lr.Leg(m)


def _put(mujoco, m, d, leg, p1, p2, rail=0.6):
    """The rig at motor angles (p1, p2), its knees closing the loop, the carriage at `rail`, at rest."""
    j = fb.fk(p1, p2)
    if j is None:
        return False
    rp = leg.rp
    ang = lambda p, q: math.atan2(q[1] - p[1], q[0] - p[0])
    d.qpos[:] = 0
    d.qpos[leg.q['motor_f']] = p1 - rp['phi1']
    d.qpos[leg.q['motor_r']] = p2 - rp['phi2']
    d.qpos[leg.q['knee_f']] = (ang(j['C'], j['E']) - p1) - (rp['af'] - rp['phi1'])
    d.qpos[leg.q['knee_r']] = (ang(j['D'], j['E']) - p2) - (rp['aw'] - rp['phi2'])
    d.qpos[leg.q['rail']] = rail
    d.qvel[:] = 0
    mujoco.mj_forward(m, d)
    return True


def _j_eff(mujoco, m, d, leg, motor: str, wheel_free: bool = True) -> float:
    """The inertia (kg m^2) one motor drives with the other motor and the hips held: the mass matrix on the five-bar's
    one-motor velocity field (the knees from the apex's closure); with the wheel free to spin, less the wheel's spin,
    and with it locked to its link (the hub motor holding, braking or shorted), all of it."""
    import numpy as np
    rows = [k for k in range(d.nefc) if d.efc_type[k] == mujoco.mjtConstraint.mjCNSTR_EQUALITY]
    Jc = d.efc_J.reshape(d.nefc, m.nv)[rows]
    v = np.zeros(m.nv)
    mi = leg.v[motor]
    v[mi] = 1.0
    kn = [leg.v['knee_f'], leg.v['knee_r']]
    v[kn] = np.linalg.lstsq(Jc[:, kn], -Jc[:, mi], rcond=None)[0]
    if np.linalg.norm(Jc @ v) > 1e-6:
        return float('nan')
    Mv, e, Me = np.zeros(m.nv), np.zeros(m.nv), np.zeros(m.nv)
    mujoco.mj_mulM(m, d, Mv, v)
    if not wheel_free:
        return float(v @ Mv)
    e[leg.v['wheel']] = 1.0
    mujoco.mj_mulM(m, d, Me, e)
    return float(v @ Mv) - float(e @ Mv) ** 2 / float(e @ Me)


def inertia_survey(n: int = 41) -> dict:
    """Each motor's inertia over the whole stop box (n x n poses), the worst near each of its stops and the bound the
    soft stops use: the worst anywhere with the wheel free or locked, rounded up to the next 0.001 kg m^2."""
    mujoco, lr, m, d, leg = _rig()
    fo, fi, ro, ri = fb.stop_angles()
    worst, near, locked = {}, {}, {}
    near_band = math.radians(SOFT_MARGIN_DEG + 1.0)
    for a in [fi + (fo - fi) * k / (n - 1) for k in range(n)]:
        for b in [ro + (ri - ro) * k / (n - 1) for k in range(n)]:
            if not _put(mujoco, m, d, leg, a, b):
                continue
            for motor, phi, lo, hi in (('motor_f', a, fi, fo), ('motor_r', b, ro, ri)):
                J = _j_eff(mujoco, m, d, leg, motor)
                if J != J:
                    continue
                if J > worst.get(motor, (0,))[0]:
                    worst[motor] = (J, [_deg(a), _deg(b)])
                Jl = _j_eff(mujoco, m, d, leg, motor, wheel_free=False)
                if Jl > locked.get(motor, (0,))[0]:
                    locked[motor] = (Jl, [_deg(a), _deg(b)])
                J = max(J, Jl)
                for side, dist in (('lo', phi - lo), ('hi', hi - phi)):
                    if dist <= near_band and J > near.get((motor, side), (0,))[0]:
                        near[(motor, side)] = (J, [_deg(a), _deg(b)])
    top = max(v[0] for v in list(worst.values()) + list(locked.values()))
    _put(mujoco, m, d, leg, *fb.stance(300.0))
    return {'bound_kg_m2': math.ceil(top * 1000) / 1000, 'rotor_and_upper_link_kg_m2': round(J_ROTOR_LINK_KG_M2, 4),
            'worst': {k: {'kg_m2': round(v[0], 4), 'at_deg': v[1]} for k, v in worst.items()},
            'worst_wheel_locked': {k: {'kg_m2': round(v[0], 4), 'at_deg': v[1]} for k, v in locked.items()},
            'at_stops': {f'{k[0]} {k[1]}': {'kg_m2': round(v[0], 4), 'at_deg': v[1]} for k, v in sorted(near.items())},
            'stance_300mm': {mo: round(_j_eff(mujoco, m, d, leg, mo), 4) for mo in ('motor_f', 'motor_r')},
            'basis': 'sim/leg_rig.py model: the rotor, upper link, lower links and wheel, the hips and the other motor held, '
                     'the wheel free on its bearing or locked to its link (the bound covers both; near the stops the larger '
                     'of the two); the other motor free or the hips moving would lower it. A loaded leg '
                     '(the wheel on the ground) adds the body: that is the landing and power-cut cases (R1, R3), not this one'}


def free_swing(profiles: dict, J: float, t_end: float = 1.2) -> list:
    """Each motor driven at its build's every-day torque from its far stop into the near one, the carriage held up and
    the other motor holding its angle, with the soft stops and without: the stop's peak torque and the contact speed.
    Both motors follow the RS-04's torque-speed line at 36 V (sim/leg_control.py clip_motor, as the jump sweep)."""
    from software.simulation import leg_control as lc
    mujoco, lr, m, d, leg = _rig()
    fo, fi, ro, ri = fb.stop_angles()
    dt = m.opt.timestep
    out = []
    for build in ('robot', 'pla_bench'):
        T = profiles[build]['everyday_nm']
        for motor, (lo, hi), other in (('motor_f', (fi, fo), (ro + ri) / 2), ('motor_r', (ro, ri), (fi + fo) / 2)):
            for target in ('hi', 'lo'):
                for guard in (True, False):
                    start = lo + math.radians(SOFT_MARGIN_DEG + 1) if target == 'hi' else hi - math.radians(SOFT_MARGIN_DEG + 1)
                    p = (start, other) if motor == 'motor_f' else (other, start)
                    _put(mujoco, m, d, leg, *p)
                    rail = d.qpos[leg.q['rail']]
                    sgn = 1.0 if target == 'hi' else -1.0
                    peak, w_contact, touched = 0.0, 0.0, False
                    om_name = 'motor_r' if motor == 'motor_f' else 'motor_f'
                    for _ in range(int(t_end / dt)):
                        p1, p2 = leg.phi(d)
                        ph, ph_o = (p1, p2) if motor == 'motor_f' else (p2, p1)
                        om = d.qvel[leg.v[motor]]
                        tau = sgn * T
                        if guard:
                            tau = soft_stop(tau, ph, om, lo, hi, T, J=J)
                        om_o = d.qvel[leg.v[om_name]]
                        tau_o = lc.clip_motor(400.0 * (other - ph_o) - 20.0 * om_o, om_o, RS04_PEAK, NO_LOAD_RAD_S, T)
                        d.ctrl[leg.a[motor]] = lc.clip_motor(tau, om, RS04_PEAK, NO_LOAD_RAD_S, T)
                        d.ctrl[leg.a[om_name]] = tau_o
                        d.ctrl[leg.a['wheel']] = 0.0
                        for n, phn, l_, h_ in (('motor_f', p1, fi, fo), ('motor_r', p2, ro, ri)):
                            d.qfrc_applied[leg.v[n]] = lr.stop_torque(phn, d.qvel[leg.v[n]], l_, h_)
                        ts = abs(d.qfrc_applied[leg.v[motor]])
                        if ts > 0 and not touched:
                            touched, w_contact = True, abs(om)
                        peak = max(peak, ts)
                        mujoco.mj_step(m, d)
                        d.qpos[leg.q['rail']] = rail              # the carriage held: the leg swings free in the air
                        d.qvel[leg.v['rail']] = 0.0
                    out.append({'build': build, 'motor': motor, 'stop': target, 'soft_stops': guard, 'drive_nm': T,
                                'contact_rad_s': round(w_contact, 2), 'peak_stop_nm': round(peak, 1)})
                    print(f"free swing {build:9s} {motor} -> {target}: soft stops {'on ' if guard else 'off'} contact "
                          f"{w_contact:5.2f} rad/s, stop peak {peak:6.1f} N m (drive {T:g})", flush=True)
    return out


# ----------------------------------------------------------------------------------- the file

def build(sweep: dict | None = None, inertia: dict | None = None, swing: list | None = None) -> dict:
    """limits.json from the records; the MuJoCo parts (the jump sweep, the inertia survey, the free swing) from the
    committed file unless given (python -m sim.leg_limits --sweep re-runs them)."""
    fea = json.loads(FEA.read_text())
    derating = json.loads(DERATING.read_text())
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    inertia = inertia if inertia is not None else old['inertia']
    swing = swing if swing is not None else old.get('free_swing', [])
    J = inertia['bound_kg_m2']
    js = old.get('jump_sweep', {})
    sweep = sweep if sweep is not None else {'runs': js.get('runs', []), 'at_limits': js.get('at_limits', []), 'capped_motor': js.get('capped_motor', [])}
    prof = torque_profiles(fea, derating, sweep['runs'])
    s = stops()
    win = angle_window(prof['robot'])
    survey = box_survey()
    table = command_window()
    approach = {'stop_k_nm_per_rad': STOP_K_NM_PER_RAD, 'j_kg_m2': J,
                'contact_rad_s': {k: round(p['everyday_nm'] / math.sqrt(STOP_K_NM_PER_RAD * J), 2) for k, p in prof.items()},
                'stop_energy_j': {k: round(p['everyday_nm'] ** 2 / (2 * STOP_K_NM_PER_RAD), 2) for k, p in prof.items()},
                'brake_from_no_load_deg': {k: round(SOFT_MARGIN_DEG + math.degrees((NO_LOAD_RAD_S ** 2 - (p['everyday_nm'] / math.sqrt(STOP_K_NM_PER_RAD * J)) ** 2)
                                                                                    / (2 * p['everyday_nm'] / J)), 1) for k, p in prof.items()}}
    return {
        'about': 'Generated by sim/leg_limits.py; docs/leg-protection.md explains every number. Regenerate, never edit.',
        'profiles': prof,
        'stops_deg': {k: [_deg(v[0]), _deg(v[1])] for k, v in s.items()},
        'soft_stop': {'margin_deg': SOFT_MARGIN_DEG, 'kd_nm_s_per_rad': SOFT_KD, **approach},
        'inertia': inertia,
        'free_swing': swing,
        'angle_window_deg': round(math.degrees(win), 2),
        'dead_limp_deg': DEAD_LIMP_DEG,
        'jump_hot_share': JUMP_HOT_SHARE,
        'yaw': yaw_limits(prof['robot']['everyday_nm'], table),
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
    sweep = inertia = swing = None
    if a.sweep:
        global _J
        inertia = inertia_survey()
        _J = inertia['bound_kg_m2']                 # the soft stops in the sweep below run on the new bound
        print(f"inertia at a motor: worst {max(v['kg_m2'] for v in inertia['worst'].values())} kg m^2 (wheel free), "
              f"{max(v['kg_m2'] for v in inertia['worst_wheel_locked'].values())} (locked) -> bound {_J}", flush=True)
        runs = jump_sweep()
        prof = torque_profiles(json.loads(FEA.read_text()), json.loads(DERATING.read_text()), runs)['robot']
        sweep = {'runs': runs, 'at_limits': jump_sweep(sorted({prof['everyday_nm'], prof['peak_nm']})),
                 'capped_motor': jump_sweep((60.0,), motor_peak=60.0)}
        prof_all = torque_profiles(json.loads(FEA.read_text()), json.loads(DERATING.read_text()), runs)
        swing = free_swing(prof_all, _J)
    data = build(sweep, inertia, swing)
    OUT.write_text(json.dumps(data, indent=1) + '\n')
    rb, pl = data['profiles']['robot'], data['profiles']['pla_bench']
    print(f"-> {OUT.relative_to(R)}: robot every day {rb['everyday_nm']:g} N m ({rb['everyday_governing']['part']} {rb['everyday_governing']['case']}), "
          f"peak {rb['peak_nm']:g} N m (the push rows would allow {rb['push_allows_nm']:g}: {rb['peak_governing']['part']} {rb['peak_governing']['case']}), rms {rb['rms_nm']:g} N m; PLA bench {pl['everyday_nm']:g} N m")


if __name__ == '__main__':
    main()
