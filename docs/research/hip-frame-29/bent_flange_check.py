#!/usr/bin/env python3
"""Issue #29's fallback: the hip frame's flanges as a bent 5052 part (SendCutSend) bolted to the web, checked against
cad-agent's sheet-metal rules (research/process-profiles.yaml, cad-agent #162) and against the body it bolts to.

    python research/hip-frame-29/bent_flange_check.py --profiles ../cad-agent/research/process-profiles.yaml

The part, per flange: a plate on the web's edge, running in y from the web to the body's centre plane, bent 90 deg
there into a tab on the centre plane that takes today's three M5 screws (fivebar.frame_mounts(): z +-70). The body
interface is fixed, so the question is where the plate must sit for those holes to keep each rule's distance from the
bend, and whether that still clears the body (the floor tray above, the cheeks' bottom flange below).

It is a geometry and rules check plus a beam estimate of the plate's bending stress; it does not model the screws into
the web or the plate's stiffness in the leg. Writes JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HOLE_D = 5.5                       # M5 clearance in the tab (as the cheeks: cad/body_frame.py)


def rule_values(profiles: dict, feature: str, T: float, R: float) -> list:
    """Every sheet-metal rule for a feature with a 'min' expression, evaluated at T and R: [(id, source, mm)]."""
    out = []
    for r in profiles['rules']:
        if r['process'] != 'sheet-metal' or r['feature'] != feature or r.get('min') is None:
            continue
        expr = str(r['min'])
        try:
            v = float(eval(expr, {'__builtins__': {}}, {'T': T, 'R': R, 'max': max, 'min': min}))
        except Exception:
            continue
        out.append((r['id'], r['source'], round(v, 2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profiles', type=Path, required=True, help="cad-agent's research/process-profiles.yaml")
    ap.add_argument('--root-mpa', type=float, default=12.9,
                    help="the printed flange's root stress the plate must carry: E1's peak at the bottom flange's root "
                         "(x 93, 4 mm mesh, corrected loads), which includes the sharp corner's concentration, so an upper bound")
    a = ap.parse_args()
    prof = yaml.safe_load(a.profiles.read_text())
    sys.path[:0] = [str(ROOT / 'cad'), str(ROOT)]
    import body_params as bp
    import fivebar as fb

    m = fb.frame_mounts()
    z_hole = max(z for _, z in m['inserts_xz'])                     # 70
    zt = bp.z_spine_top()                                           # the tray's underside, the cheeks' flange faces
    cheek_t = bp.STOCK[bp.CHEEK]['t']
    top_room, bottom_room = zt, zt - cheek_t                        # |z| the part's outer face must stay under
    today = fb.frame_ring_r() + fb.FLANGE_T                         # today's printed flange's outer face (75)
    sheets = []
    for tab in prof['shop_tables']:
        cols = tab['columns']
        for row in tab['rows']:
            d = dict(zip(cols, row))
            if '5052' in d['material']:
                sheets.append({'sku': d['sku'], 'T': d['T'], 'R': d['R'], 'K': d['K'], 'min_flange': d['min_flange_after_bend'],
                               'relief': d['relief_depth'], 'source': tab['source']})
    st = bp.STOCK['5052-0.187']                                     # gyropup's own 3/16 in row (the cheeks' stock)
    sheets.append({'sku': '5052-0.187 (gyropup body_params.STOCK)', 'T': st['t'], 'R': st['r'], 'K': st['k'],
                   'min_flange': st['min_flange'], 'relief': None, 'source': 'gyropup cad/body_params.py'})
    rows = []
    for s in sheets:
        T, R = s['T'], s['R']
        h2b = rule_values(prof, 'hole-to-bend', T, R)
        strict = max(v for _, _, v in h2b)
        lenient = min(v for _, _, v in h2b)
        out = {}
        for name, dist in (('strictest', strict), ('most_lenient', lenient)):
            # hole edge to the bend's inside tangent >= dist; the tab hangs from the bend towards the motors, so the plate's
            # outer face sits at z_hole + hole radius + dist + R + T
            z_face = z_hole + HOLE_D / 2 + dist + R + T
            out[name] = {'hole_to_bend_mm': dist, 'plate_outer_face_z_mm': round(z_face, 2),
                         'above_today_mm': round(z_face - today, 2),
                         'clears_tray': z_face <= top_room - 1.0, 'clears_cheek_flange': z_face <= bottom_room - 1.0}
        edge = max(v for _, _, v in rule_values(prof, 'hole-to-edge', T, R))
        for o in out.values():     # the tab, from the plate's outer face to its free edge past the lowest hole (z 70)
            o['tab_length_mm'] = round(o['plate_outer_face_z_mm'] - z_hole + HOLE_D / 2 + edge, 1)
            o['tab_meets_min_flange'] = o['tab_length_mm'] >= s['min_flange']
        rows.append({**s, 'hole_to_bend_rules': h2b, 'hole_to_edge_mm': edge, **out})
    # the plate's bending: the same root moment per unit width as the 13 mm printed flange -> sigma = 6 m / T^2 in the
    # plate, against 5052-H32's yield (static only; no fatigue, no screw joint)
    sig_pa6 = a.root_mpa
    m_w = sig_pa6 * fb.FLANGE_T ** 2 / 6                            # N mm / mm
    for r in rows:
        s_al = 6 * m_w / r['T'] ** 2
        r['plate_bending'] = {'mpa': round(s_al, 1), 'yield_mpa': 193.0, 'sf': round(193.0 / s_al, 2),
                              'stiffness_vs_printed': round(70300 * r['T'] ** 3 / (2400 * fb.FLANGE_T ** 3), 2)}
    print(json.dumps({'body': {'tray_underside_z_mm': top_room, 'cheek_bottom_flange_inner_z_mm': -bottom_room,
                               'inserts_xz': m['inserts_xz'], 'printed_flange_outer_z_mm': today},
                      'assumptions': ['the tab hangs from a bend at the plate towards the motors and carries the three holes '
                                      'at today\'s z +-70', 'hole-to-bend is measured from the hole edge to the bend\'s inside '
                                      'tangent', f'plate bending: the printed flange\'s root moment per unit width from E1\'s peak stress at its root '
                                      f'({sig_pa6} MPa on 13 mm, an upper bound), uniform across the width; 5052-H32 yield 193 MPa'],
                      'sheets': rows}, indent=1))


if __name__ == '__main__':
    main()
