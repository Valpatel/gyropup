"""The fuse board's numbers: the copper of every branch against its fuse's rating, the main path at its duty, the
copper against a fault's let-through, the INA228's error budget, and the board's mass.

    python3 hardware/fuse-board/analysis.py        # -> reports/analysis.json, and a summary on stdout

Reads design.py and reports/board-facts.json (measure.py, from the filled board). Plain Python; every constant carries
its source. docs/body-fuse-board.md quotes these tables.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(HERE))
import design as D  # noqa: E402

T_MM = D.COPPER_UM / 1000.0                  # 2 oz finished outer copper, 70 um
MIL = 0.0254                                 # mm
RHO_CU = 1.72e-8                             # ohm m at 20 C
CV_CU = 3.45e6                               # J / (m^3 K), copper's volumetric heat capacity

# ------------------------------------------------------------------------------------------ IPC-2221 (external)
# IPC-2221B 6.2 (fig. 6-4), external conductors: I = 0.048 dT^0.44 A^0.725, I in A, dT in C, A in mil^2. Its charts
# stop at 35 A, 400 mil (10.2 mm) and 3 oz; inside those limits it is conservative for a board like this (IPC-2152's
# measurements for external traces on 1.6 mm FR-4 in still air give equal or lower rises). Beyond 35 A per conductor it
# is extrapolated and labelled so.
IPC_LIMIT_A, IPC_LIMIT_W_MM = 35.0, 10.16


def ipc_dt(i_amps, width_mm):
    """IPC-2221 external temperature rise (C) of one conductor of width_mm in 2 oz carrying i_amps."""
    a_mil2 = (width_mm / MIL) * (T_MM / MIL)
    return (i_amps / (0.048 * a_mil2 ** 0.725)) ** (1 / 0.44)


def ipc_width(i_amps, dt=20.0):
    """IPC-2221 external width (mm, 2 oz) for i_amps at dt."""
    a_mil2 = (i_amps / (0.048 * dt ** 0.44)) ** (1 / 0.725)
    return a_mil2 / (T_MM / MIL) * MIL


def adiabatic_dt(i_amps, area_mm2, t_s):
    """Copper heated with no time to lose heat: dT = J^2 rho t / cv."""
    j = i_amps / (area_mm2 * 1e-6)
    return j * j * RHO_CU * t_s / CV_CU


def withstand_i2t(area_mm2, t0=60.0, t1=200.0):
    """Adiabatic I^2t (A^2 s) that takes copper of area_mm2 from t0 to t1 C (IEC 60949's K for copper, beta 234.5)."""
    k = 226.0 * math.sqrt(math.log((234.5 + t1) / (234.5 + t0)))
    return (k * area_mm2) ** 2


# Littelfuse MINI 58V (0997) datasheet (rev 11/18/2025): typical pre-arcing I^2t, cold resistance, voltage drop at rating
FUSE = {5: {'i2t': 25, 'r_mohm': 17.75, 'vdrop_mv': 129}, 7.5: {'i2t': 68, 'r_mohm': 10.85, 'vdrop_mv': 135}, 10: {'i2t': 93, 'r_mohm': 7.42, 'vdrop_mv': 108},
        20: {'i2t': 380, 'r_mohm': 3.21, 'vdrop_mv': 96}, 30: {'i2t': 1100, 'r_mohm': 1.85, 'vdrop_mv': 87}}
HOLDER = {'part': 'Littelfuse 178.6764.0001 (MINI FL1)', 'continuous_a': 22, 'fuse_max_a': 30, 'v_dc': 58,
          'source': 'littelfuse.com product page, read 2026-10-27 (datasheet rev 111616 lists 125 V, 30 A)'}
KEYSTONE_3568 = {'continuous_a': 20, 'v': '500 V AC (no DC rating)', 'source': 'Keystone catalogs M55 (2006) and M60 (2013) p. 40, '
                 'TME listing 2026-10-27; some distributors list 30 A without a source; Keystone\'s drawing rev C (2019) states none'}


def branches():
    rows = []
    neck_w, neck_l = D.OUT_NECK
    for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
        rating = amps or 30                   # the spare is sized for the largest fuse the holder takes
        per_layer = rating / 2.0              # both layers, joined at the holder's pin and the stud's via ring
        run_w = neck_w if ref == 'F12' else D.OUT_W
        need = ipc_width(per_layer, 20.0)
        r_neck = RHO_CU * neck_l * 1e-3 / (neck_w * 1e-3 * T_MM * 1e-3)
        p_neck = per_layer ** 2 * r_neck                          # W in one layer's neck
        k_cu = 390.0
        dt_neck = p_neck * neck_l * 1e-3 / (8 * k_cu * neck_w * 1e-3 * T_MM * 1e-3)  # a short bar heated along its length, ends held
        s_neck = 2 * neck_w * T_MM
        f = FUSE.get(rating if rating in FUSE else 30)
        rows.append({
            'holder': ref, 'branch': label, 'wire': wire, 'fuse_a': amps, 'design_a': rating,
            'run_width_mm_each_layer': run_w, 'layers': 2,
            'ipc2221_width_needed_mm_each_layer_dt20': round(need, 2),
            'ipc2221_dt_run_c': round(ipc_dt(per_layer, run_w), 1),
            'neck_mm': [neck_w, neck_l], 'neck_rise_over_ends_c': round(dt_neck, 2),
            'within_ipc2221_limits': per_layer <= IPC_LIMIT_A and run_w <= IPC_LIMIT_W_MM,
            'fuse_power_w_at_rating': round(rating * f['vdrop_mv'] / 1000.0, 2),
            'fault': {'copper_withstand_a2s_neck': round(withstand_i2t(s_neck)), 'fuse_i2t_typ_a2s': f['i2t'],
                      'margin': round(withstand_i2t(s_neck) / f['i2t'], 1)},
            'holder_ok': rating <= HOLDER['fuse_max_a'],
            'holder_continuous_a': HOLDER['continuous_a'],
        })
    return rows


def main_path(facts):
    """The 80 A path: J1 -> +BAT_IN pour -> the shunt -> +BUS band; both layers stitched beside the shunt's pads."""
    sections = [
        ('+BAT_IN pour, J1 to the shunt (12.0 mm wide, both layers)', 12.0),
        ('+BUS band, its narrowest section beside the shunt (14.4 mm, both layers)', 14.4),
        ('+BUS band toward the holders (30 mm, both layers)', 30.0),
    ]
    out = []
    for name, w in sections:
        both = 'both layers' in name
        layers = 2 if both else 1
        a = w * T_MM * layers
        row = {'section': name, 'width_mm': w, 'layers': layers, 'area_mm2': round(a, 2)}
        for i in (40.0, 80.0):
            per = i / layers
            row[f'ipc2221_dt_at_{int(i)}a_c'] = round(ipc_dt(per, w), 1)
            row[f'ipc2221_valid_at_{int(i)}a'] = per <= IPC_LIMIT_A and w <= IPC_LIMIT_W_MM
        row['pulse_80a_0p3s_adiabatic_dt_c'] = round(adiabatic_dt(80.0, a, 0.3), 2)
        out.append(row)
    # the shunt's pads are on the top only: the bottom layer's half comes up through the stitching vias beside them
    n_bat = sum(1 for x, y in D.STITCH['+BAT_IN'])
    n_bus = sum(1 for x, y in D.STITCH['+BUS'] if x < 24.0)
    vias = {'beside_pad1_+BAT_IN': n_bat, 'beside_pad4_+BUS': n_bus, 'via': '0.4 mm drill, 0.95 mm pad, 18 um plating (JLCPCB average)',
            'amps_each_at_40a': round(20.0 / min(n_bat, n_bus), 2), 'amps_each_at_80a_pulse': round(40.0 / min(n_bat, n_bus), 2),
            'note': 'a 0.4 mm plated via carries about 2 A for a 10 C rise (IPC-2152\'s via data); the 80 A pulse is 0.3 s'}
    # the shunt (Bourns CSS2H-3920R-1L00F): 8 W at 70 C terminals, 5x rated power for 5 s (datasheet)
    shunt = {'part': 'Bourns CSS2H-3920R-1L00F', 'r_mohm': 1.0, 'tol_pct': 1.0, 'tcr_ppm': 100, 'p_rated_w': 8.0,
             'p_at_40a_w': 1.6, 'p_at_80a_w': 6.4, 'pulse_80a_0p3s_j': 1.92, 'overload_rating': '5 x 8 W for 5 s (40 W)',
             'element_rise_at_40a_c': round(1.6 * (170 - 70) / 8.0, 1)}
    # the board as one lump: still air, both faces, natural convection + radiation ~12 W/(m^2 K)
    area = facts['board_area_mm2'] * 1e-6 * 2
    h = 12.0
    rows = []
    for i in (20.0, 40.0, 80.0):
        p_shunt = i * i * 1e-3
        p_fuses = sum(min(i, b['design_a']) ** 2 * FUSE[b['design_a'] if b['design_a'] in FUSE else 30]['r_mohm'] * 1e-3 * 1.3
                      for b in branches()[:1])           # the current passes one fuse at most at this level (worst: one branch)
        p_cu = i * i * 0.4e-3                            # ~0.4 mOhm of board copper on the way (pours, both layers)
        p = p_shunt + p_fuses + p_cu
        rows.append({'current_a': i, 'power_w': round(p, 2), 'board_mean_rise_c': round(p / (h * area), 1)})
    local = {'note': 'the shunt heats about 20 cm^2 of pour on each face before the rest of the board: R ~ 1/(12 W/m2K x 40 cm2) ~ 21 K/W',
             'shunt_terminal_rise_at_40a_c': round(1.6 * 21.0, 1), 'shunt_terminal_rise_at_80a_continuous_c': round(6.4 * 21.0, 1)}
    rail = {'section': '+12V pour, J14 to F11 and F12 (12.6 mm, both layers, 6 vias)', 'current_a': 12.5,
            'note': 'the TRACO TEP 150-4812WI\'s full 12.5 A', 'ipc2221_dt_c': round(ipc_dt(12.5 / 2, 12.6), 1),
            'stud': 'M4 (J14) with a 14 AWG #8 ring: a ring rated 16-14 AWG carries it'}
    return {'sections': out, 'rail_12v': rail, 'vias': vias, 'shunt': shunt, 'board_lump': rows, 'shunt_local': local,
            'rating': {'continuous_a': 40, 'pulse': '80 A for 0.3 s (the jump) at any duty that keeps the RMS under 40 A; '
                                                   '80 A for up to 30 s',
                       'why': 'the copper is good for more (IPC-2221 under 7 C at 40 A, extrapolated about 30 C at 80 A); '
                              'the shunt\'s terminals must stay under 70 C for its 8 W rating, and 80 A continuous would put '
                              'about 130 C on them in a 35 C body'}}


def ina228_budget():
    """% of reading. TI SLYS021A (INA228): gain error 0.05 % max, gain drift 20 ppm/C max, offset 1 uV max, offset drift
    10 nV/C max, CMRR 154 dB min, R_DIFF 92 kOhm typ. Bourns CSS2H-3920R-1L00F: 1 %, TCR 100 ppm/C with copper terminals."""
    dT_amb = 30.0                         # calibrated at 25 C, used 15-55 C on the board
    v_cm = 41.0                          # D65: 10S, 41 V charged
    items = {
        'shunt tolerance': {'pct': 1.0, 'calibrated_out': True},
        'Kelvin taps (2-terminal part sensed at Bourns\' measurement points; pad and solder)': {'pct': 0.5, 'calibrated_out': True},
        'INA228 gain error': {'pct': 0.05, 'calibrated_out': True},
        '10 Ohm input resistors against R_DIFF 92 kOhm (systematic -0.022 %)': {'pct': 0.022, 'calibrated_out': True},
        'shunt TCR, ambient 15-55 C (100 ppm/C x 30 C)': {'pct': 100e-6 * dT_amb * 100, 'calibrated_out': False},
        'INA228 gain drift (20 ppm/C x 30 C)': {'pct': 20e-6 * dT_amb * 100, 'calibrated_out': False},
    }
    offset_uv = 1.0 + 0.010 * dT_amb + v_cm * 10 ** (-154 / 20) * 1e6 + 2.0 * 1.5   # offset, its drift, CMRR, thermal EMF (2 uV/C x 1.5 C)
    def self_heat(i):
        """TCR x the element's rise above its terminals: steady state up to 40 A (12.5 C/W, from 8 W between 70 and 170 C);
        80 A only as the 0.3 s jump pulse, where the element (about 0.25 g of Cu-Mn, 0.41 J/(g C)) heats adiabatically."""
        rise = i * i * 1e-3 * (170 - 70) / 8.0 if i <= 40 else (i * i * 1e-3 * 0.3) / (0.25 * 0.41)
        return 100e-6 * rise * 100
    meter = 0.3                                                                      # the calibrating meter (DMM 10 A range, <= 0.3 %)
    res = []
    for i in (1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0):
        off = offset_uv / (i * 1e3) * 100            # uV over (i x 1 mOhm in uV) -> %
        unc_items = [v['pct'] for v in items.values()] + [off, self_heat(i)]
        cal_items = [v['pct'] for v in items.values() if not v['calibrated_out']] + [off, self_heat(i), meter]
        res.append({'current_a': i, 'uncalibrated_worst_pct': round(sum(unc_items), 2),
                    'uncalibrated_rss_pct': round(math.sqrt(sum(x * x for x in unc_items)), 2),
                    'calibrated_worst_pct': round(sum(cal_items), 2),
                    'calibrated_rss_pct': round(math.sqrt(sum(x * x for x in cal_items)), 2)})
    ok = [r for r in res if r['calibrated_worst_pct'] <= 1.0]
    lo = min(r['current_a'] for r in ok)
    worst = max(r['calibrated_worst_pct'] for r in ok)
    unc = (min(r['uncalibrated_worst_pct'] for r in res), max(r['uncalibrated_worst_pct'] for r in res),
           min(r['uncalibrated_rss_pct'] for r in res), max(r['uncalibrated_rss_pct'] for r in res))
    floor_ma = offset_uv / 1e3 * 1e3                       # uV over 1 mOhm -> mA
    return {'items': {k: round(v['pct'], 3) for k, v in items.items()}, 'offset_uv_total': round(offset_uv, 2),
            'calibration': 'one point at 25 C, 5-10 A through the shunt from a bench supply, read on a meter with <= 0.3 % '
                           'on its 10 A range: SHUNT_CAL (or the firmware\'s scale) set so the INA228 agrees; VBUS the same '
                           'against the meter\'s DC volts (the 4.7 kOhm against the 1 MOhm VBUS input is -0.47 %)',
            'by_current': res,
            'result': f'within 1 % of reading from {lo:g} A to 80 A after the one-point calibration (worst case {worst:.2f} %); '
                      f'not within 1 % uncalibrated ({unc[0]:.1f}-{unc[1]:.1f} % worst case, {unc[2]:.1f}-{unc[3]:.1f} % RSS: the '
                      f'shunt\'s own 1 % and the Kelvin layout are most of it); below {lo:g} A the error is about +-{floor_ma:.0f} mA '
                      f'plus 0.7 % of reading'}


def mass(facts):
    a_board = facts['board_area_mm2'] - facts['hole_area_mm2']
    g = {
        'FR-4 (1.6 mm, 1.85 g/cm3)': a_board * 1.6 * 1.85e-3,
        'copper (70 um, 8.96 g/cm3)': (facts['copper_area_mm2']['top'] + facts['copper_area_mm2']['bottom']) * 0.070 * 8.96e-3,
        'solder mask, HASL, silk (est)': 1.5,
        '12 x Littelfuse MINI FL1 holder (est 1.6 g, PBT and copper alloy)': 12 * 1.6,
        '10 x MINI 58V fuse (0.57 g, datasheet)': 10 * 0.57,
        'shunt, passives, GH (est)': 0.8,
        'INA228 or Adafruit 5832 (3.3 g, catalog)': 3.3,
        '15 x M4 x 12 socket head + nyloc (est 1.9 + 0.9 g)': 15 * 2.8,
        'M6 x 12 socket head + nyloc (est 4.6 + 2.0 g)': 6.6,
        'M5 x 14 socket head, plate bond (est)': 3.4,
        '17 printed standoffs and 3 tie blocks, PA6-GF 1.35 g/cm3 (est 1.3 g each)': 20 * 1.3,
    }
    total = sum(g.values())
    return {'items_g': {k: round(v, 1) for k, v in g.items()}, 'total_g': round(total, 1),
            'board_alone_g': round(sum(v for k, v in g.items() if k.startswith(('FR-4', 'copper', 'solder', '12 x', 'shunt'))), 1)}


def main():
    facts = json.loads((HERE / 'reports' / 'board-facts.json').read_text())
    out = {'branches': branches(), 'main_path': main_path(facts), 'ina228': ina228_budget(), 'mass': mass(facts),
           'holder': HOLDER, 'keystone_3568': KEYSTONE_3568,
           'method': 'IPC-2221B external-conductor curve per layer (both layers carry half), with its limits flagged; '
                     'adiabatic heating for the 0.3 s jump pulse and for a fault\'s let-through (IEC 60949 K for copper, 60 to '
                     '200 C); the board as one lump in still air for the continuous rating'}
    (HERE / 'reports' / 'analysis.json').write_text(json.dumps(out, indent=1) + '\n')
    print(f"{'holder':5} {'branch':13} {'fuse':>5} {'run mm':>7} {'need mm':>8} {'dT run':>7} {'neck dT':>8} {'fault margin':>12}")
    for b in out['branches']:
        print(f"{b['holder']:5} {b['branch']:13} {str(b['fuse_a'] or '-'):>5} {b['run_width_mm_each_layer']:7.1f} "
              f"{b['ipc2221_width_needed_mm_each_layer_dt20']:8.2f} {b['ipc2221_dt_run_c']:7.1f} {b['neck_rise_over_ends_c']:8.2f} "
              f"{b['fault']['margin']:12.1f}")
    for s in out['main_path']['sections']:
        print(s)
    for r in out['ina228']['by_current']:
        print(r)
    print('mass', out['mass']['total_g'], 'g;', out['mass']['board_alone_g'], 'g board alone')


if __name__ == '__main__':
    main()
