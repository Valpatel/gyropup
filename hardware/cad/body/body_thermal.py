"""The body's thermal hand model (milestone M5, B7; D61): the J501's G48R cooler and its 9215 fan in the closed P3 body.

    .venv/bin/python cad/body_thermal.py        # -> exports/body/thermal/hand_model.json (read by docs/body-thermal.md)

The fan blows UP (the j501-agx project, 94da39d, from the user's look at the fitted cooler): it draws air in through
the fin block's open +-y sides and blows it out of its top. In the body that air comes in through the side walls'
louvres, crosses the body (picking up the power supplies' and boards' heat), goes through the fins and the fan, up the
fan duct, through the deck's cells and the turret plate's opening, and out of the riser's open sides under the turret.

What it answers: where the fan works once the shell closes the body; how much back-pressure the body's inlet (the
side walls' louvres) and outlet (the deck's cells, the riser's open sides) add; the louvre and cell areas that keep
that under 5 Pa; the air temperatures at 40 W (the cooler's inlet over the room: the other loads' heat is in it); and
the plate's temperature, labelled as the estimate it is. The CFD (the j501-agx project's tools/thermal.py on cadagent.cfd) is run only once the J501's
own Rev 0.9-g48r case reports itself calibrated and steady (exports/simulation-checks.json today: the fins not
calibrated): until then a thermometer on the robot (B16) is the acceptance (D61).

Every number says where it comes from: 'J501' (~/Code/j501-agx cad/parameters.json thermal, read only), 'CAD' (this
body's), 'Idelchik' (I. E. Idel'chik, Handbook of Hydraulic Resistance: thin perforated plates and grilles), 'assumed'
(an engineering estimate to replace with a measurement).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_params as bp  # noqa: E402

OUT = R / 'exports' / 'body' / 'thermal'
RHO, CP = 1.16, 1006.0                     # air at 30 C (kg/m3, J/kg K)
M3H = 1 / 3600.0                           # m3/h -> m3/s
BUDGET_PA = 5.0                            # D61 / the plan: the body may add at most this much back-pressure at the fan
ROOM_C = 25.0
LOADS_W = {'agx_module': (40.0, 'the AGX Orin at its 40 W mode (J501 thermal.module.power_modes_w)'),
           'j501_carrier': (5.0, 'assumed: the carrier\'s regulators, NVMe, Ethernet'),
           'tep150_12': (8.7, 'the TRACO TEP 150-4812WI at about 70 W out (the J501 45 W, lidar, lights at 50 %, 5 V rail), 89 % efficient (D65)'),
           'vescs_mcu': (4.0, 'assumed: two Flipsky 75100 idling and driving gently, the MCU board, the VN-100')}


def fan_curve():
    """The 9215-Y at full speed as the J501 project models it: a straight line from dp0 at no flow to free air."""
    f = bp.j501_params()['thermal']['fan']
    return {'dp0_pa': f['dp0_pa'], 'q_free_m3h': f['q_free_m3h'], 'basis': 'J501 thermal.fan: ' + f['note']}


def j501_operating_point():
    """The J501 box's CFD operating point (exports/simulation-checks.json 'fan operating point': 16.21 CFM, 0.293 of free
    air): the pressure the fan makes there is the cooler's own resistance plus the box's; all of it is given to the
    cooler here (its resistance is overstated, which lowers the robot's flow: conservative)."""
    q = 16.21 * 1.699                                       # CFM -> m3/h
    f = fan_curve()
    dp = f['dp0_pa'] * (1 - q / f['q_free_m3h'])
    return {'q_m3h': round(q, 2), 'dp_pa': round(dp, 2), 'k_cooler': dp / q ** 2,
            'basis': 'J501 exports/simulation-checks.json (CFD, Rev 0.9-g48r, fins not calibrated): 16.21 CFM'}


def zeta_perforated(phi):
    """Idelchik's thin perforated plate, sharp-edged holes: the loss coefficient on the velocity IN the holes."""
    return (0.707 * (1 - phi) ** 0.375 + 1 - phi) ** 2


def dp_opening(q_m3h, area_mm2, zeta):
    v = q_m3h * M3H / (area_mm2 * 1e-6)
    return zeta * 0.5 * RHO * v * v, v


def intake_cells():
    """The deck's intake cells as cut (body_frame.intake_cells: 8 mm squares, 1.5 mm corner radius, on an 11 mm pitch)."""
    import body_frame as bf
    cells = bf.intake_cells()
    a1 = bf.INTAKE_CELL ** 2 - (4 - math.pi) * 1.5 ** 2
    return {'n': len(cells), 'area_mm2': round(len(cells) * a1, 1), 'phi': round(a1 / bf.INTAKE_PITCH ** 2, 3),
            'cell_mm': bf.INTAKE_CELL, 'pitch_mm': bf.INTAKE_PITCH}


def rev_b_cells(pitch=10.54, r_field=None):
    """A Rev B deck's intake field: 8 mm cells on the sheet's minimum web (2.54 mm: the 0.100 in deck's thickness) over
    the fan's whole circle (blades + 2 mm), clear of the riser's feet by its foot and 3 mm (as the P1 field)."""
    import body_frame as bf
    t = bp.tm()
    fx, fy = bp.j501_stack()['fan_xy']
    r_field = r_field or bf.INTAKE_R
    half = bf.INTAKE_CELL * 0.71
    n = int(r_field // pitch) + 1
    out = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = fx + i * pitch, fy + j * pitch
            if math.hypot(x - fx, y - fy) + half > r_field:
                continue
            if any(math.hypot(x - (t['pan_x'] + a), y - b) < bf.RISER_FOOT_R + 3.0 + half for a, b in bf.RISER_FEET):
                continue
            out.append((round(x, 2), round(y, 2)))
    a1 = bf.INTAKE_CELL ** 2 - (4 - math.pi) * 1.5 ** 2
    return {'n': len(out), 'area_mm2': round(len(out) * a1, 1), 'phi': round(a1 / pitch ** 2, 3), 'pitch_mm': pitch,
            'cells': out}


def riser_sides():
    """The riser's four open sides under its ring: between its legs (Ø18) at the feet 80 mm apart, the deck to the
    ring's underside."""
    import body_frame as bf
    h = bp.RISER_H - bf.RISER_TOP_T
    w = 80.0 - 2 * bf.RISER_LEG_R
    return {'area_mm2': round(4 * w * h, 1), 'each_mm': [w, h]}


def operating_point(k_c, outlet, inlet):
    """The fan's flow where its curve meets the cooler plus the body (bisection): q (m3/h) and the pressures. `outlet`
    carries the whole flow (the deck's cells, the riser's sides); `inlet` is each side's louvres (half the flow each)."""
    f = fan_curve()

    def body(q):
        return sum(dp_opening(q, a, z)[0] for a, z in outlet) + sum(dp_opening(q / 2, a, z)[0] for a, z in inlet)
    lo, hi = 0.0, f['q_free_m3h']
    for _ in range(80):
        q = (lo + hi) / 2
        if f['dp0_pa'] * (1 - q / f['q_free_m3h']) > k_c * q * q + body(q):
            lo = q
        else:
            hi = q
    q = (lo + hi) / 2
    return {'q_m3h': round(q, 2), 'q_cfm': round(q / 1.699, 2), 'fan_pa': round(f['dp0_pa'] * (1 - q / f['q_free_m3h']), 2),
            'cooler_pa': round(k_c * q * q, 2), 'body_pa': round(body(q), 2),
            'deck_outlet_pa': round(sum(dp_opening(q, a, z)[0] for a, z in outlet), 2),
            'louvre_inlet_pa': round(sum(dp_opening(q / 2, a, z)[0] for a, z in inlet), 2)}


def area_for(q_m3h, dp_pa, zeta):
    """The open area (mm2) that passes q at dp through openings of this loss coefficient."""
    return q_m3h * M3H / math.sqrt(dp_pa / (zeta * 0.5 * RHO)) * 1e6


LOUVRE_ZETA = 2.0          # side-wall louvres as the inlet: plain 4 mm slots in a 2 mm wall (Idelchik's grilles, 1.6-2.4 on the slot velocity)
INLET_RISE_K = 3.0         # D61: the cooler's inlet within 3 K of the room
EXHAUST_C = 45.0           # D61: the exhaust (now out of the riser's sides, under the turret) at most 45 C


def model():
    op = j501_operating_point()
    k_c = op['k_cooler']
    cells = intake_cells()
    sides = riser_sides()
    z_cells = zeta_perforated(cells['phi'])
    z_sides = 1.5                                            # out of the cells, a 90 deg turn under the ring and out: assumed
    q_ref = op['q_m3h']
    # the louvres each side carry half the flow; size them so the inlet adds half the 5 Pa budget at the J501's flow
    louvre_side_mm2 = area_for(q_ref / 2, BUDGET_PA / 2, LOUVRE_ZETA)            # what half the budget asks for
    import body_shell as bs3                                                     # what the walls have (B6: one source)
    LV = bs3.LOUVRE
    n_slots = LV['n']
    louvre_mm2 = round(n_slots * (LV['w'] * LV['h'] - (4 - math.pi) * (LV['w'] / 2) ** 2), 1)
    # the outlet: the P1 deck as cut, and a Rev B deck with cells over the fan's whole circle on the minimum web
    rb = rev_b_cells()
    pl = rev_b_cells(r_field=60.0)                           # a plenum: the shroud flares out under the deck to r 60
    cases = {}
    for name, cell_area, zc in (('P1 deck as cut, P3 louvres', cells['area_mm2'], z_cells),
                                ('Rev B deck (lever 3), P3 louvres', rb['area_mm2'], zeta_perforated(rb['phi'])),
                                ('Rev B deck with a plenum to r 60, P3 louvres', pl['area_mm2'], zeta_perforated(pl['phi']))):
        outlet = [(cell_area, zc), (sides['area_mm2'], z_sides)]
        inlet = [(louvre_mm2, LOUVRE_ZETA)]
        o = operating_point(k_c, outlet, inlet)
        heat = sum(w for w, _ in LOADS_W.values())
        mdot_cp = RHO * CP * o['q_m3h'] * M3H
        # every watt but the module's goes into the body's air before the fins draw it (the walls lose some: conservative)
        o['cooler_inlet_rise_k'] = round((heat - LOADS_W['agx_module'][0]) / mdot_cp, 2)
        o['air_rise_through_cooler_k'] = round(LOADS_W['agx_module'][0] / mdot_cp, 2)
        o['exhaust_at_riser_c'] = round(ROOM_C + heat / mdot_cp, 1)
        o['budget_pa'] = BUDGET_PA
        o['pass_budget'] = o['body_pa'] <= BUDGET_PA
        o['pass_inlet'] = o['cooler_inlet_rise_k'] <= INLET_RISE_K
        o['pass_exhaust'] = o['exhaust_at_riser_c'] <= EXHAUST_C
        cases[name] = o
    # the plate (TTP): a heat-pipe tower of this size runs about 0.45-0.6 K/W at 15-20 CFM (assumed: Seeed publishes no
    # curve), plus the pad and spreader about 0.15 K/W (J501 thermal.module tim_k 6 W/mK over the 0.5 mm pad, assumed)
    r_hs, r_tim = 0.6, 0.15
    best = cases['P1 deck as cut, P3 louvres']             # the deck as ordered: the warmest case
    ttp = ROOM_C + best['cooler_inlet_rise_k'] + best['air_rise_through_cooler_k'] / 2 + (r_hs + r_tim) * LOADS_W['agx_module'][0]
    return {
        'inputs': {'fan': fan_curve(), 'j501_operating_point': {k: v for k, v in op.items() if k != 'k_cooler'},
                   'cooler_k_pa_per_m3h2': round(k_c, 6), 'air': {'rho': RHO, 'cp': CP, 'room_c': ROOM_C},
                   'loads_w': {k: {'w': w, 'basis': b} for k, (w, b) in LOADS_W.items()},
                   'deck_cells': cells, 'riser_sides': sides,
                   'zeta': {'cells': round(z_cells, 3), 'cells_basis': 'Idelchik thin perforated plate at the cells\' open ratio',
                            'riser_sides': z_sides, 'riser_sides_basis': 'assumed (a 90 deg turn)', 'louvres': LOUVRE_ZETA,
                            'louvres_basis': 'Idelchik louvred grilles (1.6-2.4); the top of the range'}},
        'design': {'louvres_each_side_mm2': louvre_mm2, 'louvre_slots_each_side': n_slots, 'louvre_slot_mm': (LV['w'], LV['h']),
                   'louvre_pitch_mm': LV['pitch'], 'louvres_needed_for_half_the_budget_mm2': round(louvre_side_mm2, 0),
                   'louvres_where': f"the body's air inlet: each side wall's rear half beside the cooler's fins (x {LV['x0']:.0f}..{LV['x0'] + (LV['n'] - 1) * LV['pitch']:.0f}), "
                                    f"z {LV['z0']:.0f}..{LV['z0'] + LV['h']:.0f} (under the deck's lip), above the J501's port hatch; "
                                    '4 mm slots: ISO 13857 admits no finger (cad/body_shell.py LOUVRE)',
                   'rev_b_deck_cells_open_mm2': rb['area_mm2'], 'rev_b_deck_cells_n': rb['n'], 'rev_b_deck_cells_xy': rb['cells'],
                   'plenum_cells_open_mm2': pl['area_mm2'], 'plenum_cells_n': pl['n'],
                   'rev_b_deck_cells': 'cells 8 mm square on a 10.54 mm pitch (2.54 mm webs: the sheet\'s thickness, SendCutSend\'s '
                                       'minimum) over the fan\'s whole circle (r 46), clear of the riser\'s feet; the turret plate\'s '
                                       'opening follows it',
                   'fan_duct': 'a printed PETG duct from the fan frame (2 mm clear of the fan, the J501\'s minimum_fan_clearance) up to '
                               'the turret plate\'s opening, so the fan\'s exhaust leaves through the deck and does not spill back into the '
                               'body to come round through the fins again (the J501 box re-breathed +3.5 K without its skirt)',
                   'flow_direction': 'up: louvres -> body -> fins -> fan -> duct -> deck cells -> riser sides (j501-agx 94da39d)'},
        'cases': cases,
        'plate': {'ttp_estimate_c': round(ttp, 1), 'limit_c': 70.0, 'r_heatsink_k_per_w': r_hs, 'r_tim_k_per_w': r_tim,
                  'basis': 'assumed thermal resistances (no published G48R curve): the thermometer test (B16) is the acceptance'},
        'cfd': 'not run: the J501 project\'s own Rev 0.9-g48r case is not calibrated (exports/simulation-checks.json: fins not '
               'calibrated, plate margin unknown); run it (j501-agx tools/thermal.py) once that case reports calibrated and steady, '
               'one heavy solver at a time on this machine (D61)',
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = model()
    (OUT / 'hand_model.json').write_text(json.dumps(m, indent=1) + '\n')
    for n, c in m['cases'].items():
        print(f"{n}: {c['q_cfm']} CFM; the body adds {c['body_pa']} Pa (deck outlet {c['deck_outlet_pa']}, louvre inlet "
              f"{c['louvre_inlet_pa']}; budget {c['budget_pa']}): {'pass' if c['pass_budget'] else 'OVER'}; the cooler's inlet "
              f"{c['cooler_inlet_rise_k']} K over the room ({'pass' if c['pass_inlet'] else 'OVER'} 3 K); the air rises "
              f"{c['air_rise_through_cooler_k']} K through the cooler; {c['exhaust_at_riser_c']} C out of the riser")
    d = m['design']
    print(f"louvres: {d['louvre_slots_each_side']} slots {d['louvre_slot_mm']} mm each side ({d['louvres_each_side_mm2']} mm2; half the "
          f"budget asks {d['louvres_needed_for_half_the_budget_mm2']:.0f}); "
          f"a Rev B deck's field: {d['rev_b_deck_cells_n']} cells, {d['rev_b_deck_cells_open_mm2']:.0f} mm2 (the P1 deck has "
          f"{m['inputs']['deck_cells']['n']} cells, {m['inputs']['deck_cells']['area_mm2']} mm2)")
    print(f"plate about {m['plate']['ttp_estimate_c']} C (limit 70; assumed resistances)")


if __name__ == '__main__':
    main()
