#!/usr/bin/env python3
"""The body sheet-metal study (issue #155): today's frame against three cheaper, simpler options, compared on cost,
parts, bends, PEM hardware, fasteners, mass, stiffness and strength, build steps and print hours.

    .venv/bin/python research/body-sheet-metal/study.py        # reads prices.json and fea/*/summary.json; writes study.json

Where each number comes from (the study page says the same per table):
  * prices        SendCutSend's instant quote page, read by quote.py on the date in prices.json (no account, no order)
  * bends, flanges, holes near bends, K, allowance
                  cad-agent v0.13.0: cadagent.manufacturing.sheet_metal.bend / flat_length and dfm.check("sheet-metal"),
                  with SendCutSend's own row where cad-agent's shop table has one (0.063, 0.090, 0.125 in 5052) and the
                  generic rules otherwise (0.100, 0.187 in: no shop row; a gap noted on the page)
  * PEM rules     SendCutSend's hardware catalogue (H hole, K edge, M spacing, min sheet; read 2026-11-01); cad-agent has
                  no PEM rules yet (a gap); Gyropup's own sheet checks (cad/body_sheet.SheetPart.checks) apply them
  * PEM strength  PennEngineering's nut bulletin (CL, dated 10/13/26: pushout, torque-out, averages) set beside
                  cadagent.mechanical.inserts.check_joint for the heat-set insert of the same thread in printed PA6-CF
  * rivets        IFI-114 (2015) minimum shear and tensile for 1/8 in aluminium / steel-mandrel blind rivets, as
                  printed in a distributor's catalogue page (Fastener SuperStore)
  * stiffness, strength
                  cadagent.fea (cad/body_studies.py's cases, run by fea.py on an x86 CAD host for every option)
  * mass          the parts' solids (cad/body_sheet.SheetPart) x density; printed parts from their volume at PA6-CF's
                  1.09 g/cm3 (cad-agent's material row) and today's print plan for the rest
  * print hours   today's print plan (exports/body/print-plan.json); new printed parts at its own PA6-CF rate (g/h)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parts as P  # noqa: E402

import body_params as bp  # noqa: E402

R = P.R
PRICES = HERE / 'prices.json'
OUT = HERE / 'study.json'
SCS_READ = '2026-11-01'

# PennEngineering, "Self-Clinching Nuts" bulletin CL (the PDF behind pemnet.com's SS-M5-0 product page, dated 10/13/26),
# Performance Data for S/CLS/SS/CLSS nuts, metric, shank code 0, test sheet 5052-H34 aluminium. "Other performance values
# reported are averages when all proper installation parameters and procedures are followed" (its note 1). The nut's
# material: heat-treated steel, 720 MPa yield (Table II of the axial-strength sheet, updated 10/28/21).
PEM_DATA = {'source': 'PennEngineering bulletin CL (self-clinching nuts), Performance Data, 10/13/26; averages',
            'url': 'https://www.pemnet.com/products/product-finder/ss-m5-0/ (Datasheets: the CL bulletin PDF)',
            'read_on': SCS_READ, 'sheet': '5052-H34 aluminium',
            'S-M3-0': {'pushout_n': 280, 'torque_out_nm': 0.9, 'install_kn': '6.7-8.9'},
            'S-M4-0': {'pushout_n': 300, 'torque_out_nm': 2.37, 'install_kn': '11.2-13.4'},
            'SS-M5-0': {'pushout_n': 300, 'torque_out_nm': 3.0, 'install_kn': '11.2-15.6'},
            'S-M6-0': {'pushout_n': 970, 'torque_out_nm': 7.9, 'install_kn': '18-32'},
            'nut_yield_mpa': 720}
# ISO 898-1 proof loads (N) of the class 8.8 / 12.9 screws the body uses, the limit when the load presses a PEM's
# head into the sheet (the direction SendCutSend's page asks for: "load pulls the nut into the part")
PROOF_N = {'M3': {'8.8': 2920, '12.9': 4380}, 'M4': {'8.8': 5100, '12.9': 7640}, 'M5': {'8.8': 8250, '12.9': 12400}}
# The same bulletin's rule (CL-17, "DON'T"): "DON'T install screw in the head side of fastener. Install from opposite side
# so that the fastener load is toward sheet. The clinching force is designed only to hold the fastener during handling
# and to resist torque during assembly." So pushout and torque-out are the hold in handling and assembly; loaded the
# right way the joint is as strong as the nut's thread or the screw. PennEngineering's "Axial Strength and Mating Screw
# Recommended Tightening Torque" sheet (updated 10/28/21) gives the nut's minimum axial strength with a 180 ksi screw
# and the recommended tightening torque, for unified sizes only: the nearest unified nut stands in for each metric one.
PEM_AXIAL = {'M3': {'unified': 'S-440-0', 'min_axial_n': round(988 * 4.4482), 'torque_grade5_nm': round(8.5 * 0.11298, 2)},
             'M4': {'unified': 'S-832-0', 'min_axial_n': round(1971 * 4.4482), 'torque_grade5_nm': round(25 * 0.11298, 2)},
             'M5': {'unified': 'SS-024-0', 'min_axial_n': round(2239 * 4.4482), 'torque_grade5_nm': round(33 * 0.11298, 2)},
             'source': 'PennEngineering, Axial Strength and Mating Screw Recommended Tightening Torque for PEM self-clinching '
                       'nuts (unified; 180 ksi screw; K = 0.20), updated 10/28/21, read 2026-11-01'}
HEADS = {'M3': (5.5, 3.4), 'M4': (7.0, 4.5), 'M5': (8.5, 5.5)}       # a washer face and clearance hole for the metal clamp
RIVET_DATA = {'size': '1/8 in aluminium body, steel mandrel, dome head (POP AD43BS class; grip 0.126-0.187 in)',
              'shear_n': round(170 * 4.4482), 'tensile_n': round(220 * 4.4482),
              'source': 'IFI-114 (2015) minimum ultimate loads, printed in Fastener SuperStore\'s rivet catalogue page '
                        '(fastenersuperstore.com/product_specs/rivets-blind-aluminum-steel-dome-standard), read 2026-11-01'}

PA6_DENSITY = 1.09                 # cad-agent's PA6-CF row (cadagent.fea.MATERIALS['pa6_cf_xy'])
PRINTED_T = {'deck': 8.0, 'tray': 8.0, 'pallet': 6.0, 'power_plate': 6.0}       # option C's plates, solid PA6-CF


def _cadagent():
    from cadagent.manufacturing import dfm
    from cadagent.manufacturing import sheet_metal as sm
    from cadagent.mechanical import inserts
    import cadagent
    return sm, dfm, inserts, cadagent


def mass_g(sp) -> float:
    return sp.solid().val().Volume() * bp.STOCK[sp.stock]['density'] / 1000.0


def _bend_zone_dist(sp, ft):
    """A feature's edge to the nearest edge of a bend zone, in the flat (mm): the strictest reading of 'hole to bend'."""
    regs = sp.flat_regions()
    x, y = sp.to_flat(ft)
    rad = max(ft.size[0], ft.size[1]) / 2 if ft.kind == 'slot' else ft.d / 2
    best = None
    for n, (a, b, c, d) in regs:
        if not n.startswith('bend_'):
            continue
        dx = max(a - x, 0.0, x - b)
        dy = max(c - y, 0.0, y - d)
        dd = math.hypot(dx, dy) - rad
        best = dd if best is None else min(best, dd)
    return best


def sheet_checks(sp) -> dict:
    """cad-agent's sheet-metal rules on one part: the bend (K, allowance, deduction, shortest flange, relief) from the
    shop's row or the generic rules, the flat length of each bent section, and dfm.check on the flanges, the holes
    nearest a bend and the smallest hole. Gyropup's own SendCutSend checks (PEM K/N/M, half-die) beside them."""
    sm, dfm, _, _ = _cadagent()
    s = bp.STOCK[sp.stock]
    out = {'part': sp.name, 'stock': sp.stock, 'gyropup_rules': sp.checks() or 'pass'}
    if not s['material'].startswith('5052') or not sp.flanges:
        out['cadagent'] = 'flat part: no bend rules apply' if sp.flanges == [] else f"{s['material']}: cad-agent has no profile for it"
        if not sp.flanges and s['material'].startswith(('5052', '6061')):
            holes = [f for f in sp.features if f.kind in ('hole', 'pem', 'csk')]
            if holes:
                feats = [dfm.Feature('smallest hole', 'hole', min(f.d for f in holes))]
                r = dfm.check('sheet-metal', feats, material='5052', thickness_mm=s['t'], shop=False)
                out['dfm'] = {'verdict': r['verdict'], 'rows': [(f['name'], f['verdict']) for f in r['features']]}
        return out
    t = s['t']
    b = sm.bend('5052', t)                            # the shop's row when it has one for this thickness
    out['bend'] = {'stock_row': b['stock'], 'radius_mm': b['radius_mm']['value'], 'radius_rule': b['radius_mm']['rule'],
                   'k': b['k']['value'], 'k_rule': b['k']['rule'], 'allowance_mm': b['allowance_mm'],
                   'deduction_mm': b['deduction_mm'], 'min_flange_mm': b['min_flange_mm']['value'],
                   'min_flange_rule': b['min_flange_mm']['rule'], 'relief_depth_mm': b['relief_depth_mm']['value']}
    gy = {'r_mm': s['r'], 'k': s['k'], 'bd_mm': s['bd']}
    out['bend']['gyropup_stock'] = {k: round(v, 3) for k, v in gy.items()}
    # the flat length across the two S/N flanges (the section that bends twice)
    legs = [sp.fl('S').length if sp.fl('S') else None, sp.H, sp.fl('N').length if sp.fl('N') else None]
    legs = [x for x in legs if x]
    if len(legs) >= 2:
        fl = sm.flat_length(legs, '5052', t)
        out['flat_length'] = {'legs_mm': legs, 'flat_mm': fl['flat_mm'], 'verdict': fl['verdict'], 'detail': fl['detail']}
    feats = [dfm.Feature(f'flange {f.edge}', 'flange', f.length) for f in sp.flanges]
    near = [(_bend_zone_dist(sp, f), f) for f in sp.features if f.kind in ('hole', 'pem', 'csk')]
    near = [(d, f) for d, f in near if d is not None]
    if near:
        d, f = min(near, key=lambda x: x[0])
        feats.append(dfm.Feature(f'nearest hole to a bend ({f.note[:40]})', 'hole-to-bend', max(d, 0.0)))
    holes = [f for f in sp.features if f.kind in ('hole', 'pem', 'csk')]
    if holes:
        feats.append(dfm.Feature('smallest hole', 'hole', min(f.d for f in holes)))
    corners = sp.corners()
    if corners:
        feats.append(dfm.Feature('corner relief (round, depth = its radius t)', 'relief-depth', t))
    r = dfm.check('sheet-metal', feats, material='5052', thickness_mm=t)
    out['dfm'] = {'verdict': r['verdict'], 'stock': r['stock'],
                  'rows': [{'name': f['name'], 'size': round(f['size'], 2), 'verdict': f['verdict'], 'detail': f['detail'],
                            'strictest_mm': f.get('strictest'), 'shop': f.get('shop'),
                            'rules': [(x['rule'], x.get('min'), x['verdict']) for x in f.get('rules', [])]} for f in r['features']]}
    return out


def joint_table() -> list:
    """The PEM nut's published pushout and torque-out beside cad-agent's check_joint capacity for the heat-set insert of
    the same thread in printed PA6-CF (humid) and PETG, upright (the insert's axis along the layers' normal)."""
    _, _, ins, _ = _cadagent()
    rows = []
    for thread, pem, insert in (('M3', 'S-M3-0', 'mcmaster-94459A140'), ('M4', 'S-M4-0', 'mcmaster-94459A160'),
                                ('M5', 'SS-M5-0', 'mcmaster-94459A775')):
        for mat in ('pa6-cf20-polymaker-wet', 'petg-bambu-basic'):
            # a metal part clamped on the insert (a plate onto a printed boss), class 8.8 screw, a small separating load
            # so the allowable rows are filled in; margin 2 (cad-agent's default)
            h, cl = HEADS[thread]
            r = ins.check_joint(insert=insert, material=mat, axis='upright', screw_class='8.8', pull_n=100.0, turn_nm=0.3,
                                head_mm=h, clearance_mm=cl, clamped={'material': 'metal', 'thickness_mm': 3.175})
            cap = r['capacity']
            lim = lambda name: next((c['limit'] for c in r['checks'] if c['check'] == name), None)
            rows.append({'thread': thread, 'insert': insert, 'material': mat,
                         'insert_pull_out_n': {k: round(v) for k, v in cap['pull_out'].items()},
                         'insert_torque_out_nm': {k: round(v, 2) for k, v in cap['torque_out'].items()},
                         'insert_allowable_pull_n': round(lim('pull-out')), 'insert_allowable_turn_nm': round(lim('torque-out'), 2),
                         'insert_tighten_nm': round(r['torque']['allowed_nm'], 2), 'insert_tighten_governed_by': r['torque']['governed_by'],
                         'insert_preload_n': {k: round(v) for k, v in r['torque']['preload_n'].items()},
                         'insert_verdict': r['verdict'], 'insert_margin': r['margin'],
                         'pem': pem, 'pem_pushout_n': PEM_DATA[pem]['pushout_n'], 'pem_torque_out_nm': PEM_DATA[pem]['torque_out_nm'],
                         'pem_axial_min_n': PEM_AXIAL[thread]['min_axial_n'], 'pem_axial_unified': PEM_AXIAL[thread]['unified'],
                         'pem_tighten_grade5_nm': PEM_AXIAL[thread]['torque_grade5_nm'],
                         'screw_8_8_proof_n': PROOF_N[thread]['8.8']})
    return rows


# ------------------------------------------------------------------------------------------- the options' bills

def printed_today() -> dict:
    pp = json.loads((R / 'exports/body/print-plan.json').read_text())
    return {k: {'qty': v['qty'], 'grams': v['grams'], 'hours': v['hours'], 'material': v['material']} for k, v in pp['parts'].items()}


RIVET_USD_EST = 0.12     # an estimate, not a quote: 1/8 in aluminium / steel blind rivets sell in 100s at about this price
                         # each (distributors' pages could not be read by script on 2026-11-01); a hand riveter is ~$25 once


def usd_per_g(material) -> float:
    """The print plan's own filament price (exports/body/print-plan.json by_material: cost / grams)."""
    pp = json.loads((R / 'exports/body/print-plan.json').read_text())['by_material']
    m = pp.get(material) or pp['pa6-cf']
    return m['cost_usd'] / m['grams']


def pa6_rate_g_per_h() -> float:
    pp = json.loads((R / 'exports/body/print-plan.json').read_text())
    m = pp['by_material']['pa6-cf']
    return m['grams'] / m['hours']


# Bought fasteners for the frame (exports/body/bom.json p1_frame_hardware and p2_head), and each option's change.
def fasteners_today() -> dict:
    d = json.loads((R / 'exports/body/bom.json').read_text())
    out = {}
    for sec in ('p1_frame_hardware', 'p2_head'):
        for v in d[sec]:
            if v['key'] == 'grommet_cable_pass':
                continue
            k = v['key']
            out[k] = out.get(k, 0) + v['qty']
    return out


DELTAS = {
    # option A: the turret plate's two end screws go; the plate posts' M5 x 10 become M5 x 12 (one length for every M5:
    # 12 - 2.54 = 9.5 mm into an 11 mm pilot through the power plate, 8.8 mm through the tray)
    'A': {'screw_m5x10_button': ('to', 'screw_m5x12_button')},
    # option B adds: the bay sides' ten screws into the old floor's flange nuts go, the rails' eight M4 x 20 into the belly
    # plate's nuts go (the rails screw to the keel's web, as they did to the side plates), 32 blind rivets join the straps
    'B': {'screw_m3x6': -10, 'screw_m4x20': -8, 'rivet_1_8': +32},
    # option C adds: the four printed plates' PEM nuts become heat-set inserts (the tray's 4 S-M4-0, the power plate's 10
    # F-M5-2 and 6 F-M4-2), the turret plate comes back with its two end screws, and each of the two split plates (deck,
    # tray) is joined by six M5 x 12 into inserts
    'C': {'insert_m4': +10, 'insert_m5': +10 + 12, 'screw_m5x12_button': +12 + 2},
}


def fasteners(option) -> dict:
    f = fasteners_today()
    chain = {'today': [], 'A': ['A'], 'B': ['A', 'B'], 'C': ['A', 'B', 'C']}[option]
    for o in chain:
        for k, v in DELTAS[o].items():
            if isinstance(v, tuple):
                f[v[1]] = f.get(v[1], 0) + f.pop(k, 0)
            else:
                f[k] = f.get(k, 0) + v
    if option in ('A', 'B'):                               # the turret plate's end screws were the two P2 M5 x 10
        f['screw_m5x12_button'] = f.get('screw_m5x12_button', 0) - 2
    return {k: v for k, v in f.items() if v > 0}


def printed(option, rate) -> dict:
    p = printed_today()
    if option == 'today':
        return p
    if option in ('B', 'C'):                               # the rails grow from 10 to 20 mm tall (option B's keel)
        for k in ('bay_rail_l', 'bay_rail_r'):
            p[k] = {**p[k], 'grams': 2 * p[k]['grams'], 'hours': 2 * p[k]['hours']}
    if option == 'C':
        m = P.options()['today']
        for name, key, t in (('deck', 'deck', PRINTED_T['deck']), ('tray', 'floor_tray', PRINTED_T['tray']),
                             ('pallet', 'compute_pallet', PRINTED_T['pallet']), ('power_plate', 'power_plate', PRINTED_T['power_plate'])):
            sp = m[key]
            area = sp.solid().val().Volume() / sp.t                       # its sheet area, lips included
            g = area * t * PA6_DENSITY / 1000.0
            halves = 2 if name in ('deck', 'tray') else 1
            p[f'{name}_printed'] = {'qty': halves, 'grams': round(g), 'hours': round(g / rate, 1), 'material': 'pa6-cf'}
        p.pop('isolator', None)                            # the printed pallet sits on the tray's inserts directly
    return p


def sheet_bill(option) -> list:
    pr = json.loads(PRICES.read_text()) if PRICES.exists() else {}
    rows = []
    for name, sp in P.options()[option].items():
        o = sp.order()
        q = pr.get(name, {})
        fin = q.get('final') or {}
        rows.append({'part': name, 'stock': sp.stock, 'material': o['material'], 'qty': sp.qty, 'bends': o['bends'],
                     'pem': sum(o['hardware'].values()), 'pem_types': o['hardware'], 'countersinks': sum(o['countersinks'].values()),
                     'flat_mm': o['flat_mm'], 'mass_g_each': round(mass_g(sp), 1),
                     'price_each': fin.get('each'), 'price_line': fin.get('subtotal'), 'price_read_on': q.get('read_on'),
                     'cut_only_each_qty1': (q.get('cut_only') or {}).get('each'),
                     'with_services_each_qty1': (q.get('with_services') or {}).get('each'),
                     'refused': q.get('refused') or None, 'quote_error': q.get('error')})
    return rows


def build_steps(sheet, fast, prin) -> dict:
    """What a builder does: parts to place, fasteners to drive (screws, nuts, standoffs), inserts to set, rivets to pull.
    The PEM nuts are pressed by SendCutSend and cost the builder nothing."""
    parts = sum(r['qty'] for r in sheet) + sum(v['qty'] for v in prin.values())
    screws = sum(v for k, v in fast.items() if k.startswith(('screw', 'turret_screw', 'nut', 'standoff')))
    ins = sum(v for k, v in fast.items() if k.startswith('insert'))
    riv = sum(v for k, v in fast.items() if k.startswith('rivet'))
    return {'parts': parts, 'screws_nuts_standoffs': screws, 'inserts': ins, 'rivets': riv, 'total': parts + screws + ins + riv}


def fea_rows():
    out = {}
    for opt in ('today', 'A', 'B', 'C'):
        f = HERE / 'fea' / opt / 'summary.json'
        if f.exists():
            d = json.loads(f.read_text())
            out[opt] = {'provenance': d.get('provenance'), 'results': {
                k: {'sf': v.get('sf_by_part') or v.get('sf_away_from_spacer_ends') or v.get('safety_factor'),
                    'sf_raw': v.get('safety_factor'), 'target': v.get('target_sf'), 'pass': v.get('pass'),
                    'max_displacement_mm': v.get('max_displacement_mm'), 'deflection_mm': v.get('deflection_mm'),
                    'twist_deg': v.get('twist_deg'), 'mesh_mm': (v.get('mesh') or {}).get('size_mm'),
                    'tets': (v.get('mesh') or {}).get('tets'), 'material': v.get('material'), 'picture': v.get('picture')}
                for k, v in d['results'].items()}}
    return out


def main():
    rate = pa6_rate_g_per_h()
    sm, dfm, ins, cadagent = _cadagent()
    opts = {}
    for opt in ('today', 'A', 'B', 'C'):
        sheet = sheet_bill(opt)
        fast = fasteners(opt)
        prin = printed(opt, rate)
        cost = [r['price_line'] for r in sheet]
        opts[opt] = {
            'sheet': sheet, 'fasteners': fast, 'printed': prin,
            'summary': {'plates_unique': len(sheet), 'plates_pieces': sum(r['qty'] for r in sheet),
                        'bends': sum(r['bends'] * r['qty'] for r in sheet), 'bent_parts_unique': sum(1 for r in sheet if r['bends']),
                        'max_bends_one_part': max(r['bends'] for r in sheet),
                        'pem': sum(r['pem'] * r['qty'] for r in sheet),
                        'unique_bought_fasteners': len(fast),
                        'sheet_usd': round(sum(cost), 2) if all(c is not None for c in cost) else None,
                        'sheet_mass_g': round(sum(r['mass_g_each'] * r['qty'] for r in sheet)),
                        'printed_g': round(sum(v['grams'] for v in prin.values())),
                        'print_hours': round(sum(v['hours'] for v in prin.values()), 1),
                        'printed_parts': sum(v['qty'] for v in prin.values()),
                        'build_steps': build_steps(sheet, fast, prin)}}
        s = opts[opt]['summary']
        s['frame_mass_g'] = s['sheet_mass_g'] + s['printed_g']
        s['printed_usd'] = round(sum(v['grams'] * usd_per_g(v['material']) for v in prin.values()), 2)
        s['rivets_usd_est'] = round(fast.get('rivet_1_8', 0) * RIVET_USD_EST, 2)
        if s['sheet_usd'] is not None:
            s['total_usd'] = round(s['sheet_usd'] + s['printed_usd'] + s['rivets_usd_est'], 2)
    checks = {}
    for opt, ps in P.options().items():
        for name, sp in ps.items():
            if name not in checks:
                checks[name] = sheet_checks(sp)
    import subprocess
    src = Path(cadagent.__file__).resolve().parents[2]
    sha = subprocess.run(['git', '-C', str(src), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    probes = {}
    if PRICES.exists():
        pr = json.loads(PRICES.read_text())
        g = lambda k: (pr.get(k) or {}).get('final', {}).get('each')
        if all(g(k) for k in ('probe_flat', 'probe_2b', 'probe_4pem', 'probe_12pem')):
            per = (g('probe_12pem') - g('probe_4pem')) / 8
            probes = {'plate': '200 x 150 mm, 1/8 in 5052, deburred, qty 1', 'flat': g('probe_flat'), 'two_bends': g('probe_2b'),
                      'four_pem': g('probe_4pem'), 'twelve_pem': g('probe_12pem'), 'per_pem_usd': round(per, 3),
                      'hardware_setup_usd': round(g('probe_4pem') - g('probe_flat') - 4 * per, 2),
                      'two_bends_usd': round(g('probe_2b') - g('probe_flat'), 2), 'read_on': pr['probe_flat']['read_on']}
    out = {'issue': 155, 'toolkit': {'cad_agent': 'v0.13.0', 'commit': sha[:7]}, 'pa6_rate_g_per_h': round(rate, 1),
           'options': opts, 'checks': checks, 'joints': joint_table(), 'pem_data': PEM_DATA, 'pem_axial': PEM_AXIAL, 'rivet': RIVET_DATA,
           'scs_price_probes': probes, 'fea': fea_rows()}
    OUT.write_text(json.dumps(out, indent=1, default=str) + '\n')
    for opt, o in opts.items():
        print(opt, json.dumps(o['summary']))


if __name__ == '__main__':
    main()
