#!/usr/bin/env python3
"""Pre-print screen of Gyropup's leg (issue #29): what a first print and a first load test would show, found from CAD.

Kernel-free (no CadQuery, no cad-agent). It reads the repository's source constants, bound by pattern through
research/insert-joints/inventory.py's Repo (a change to a bound line fails the check and asks for a regeneration),
the leg's generated exports (print plan, print STLs, FEA summary, rig results), the insert-joint inventory and the
layer-check evidence. It screens every printed leg part and every leg joint across the failure modes in README.md and
writes screen.json, screen.md and the coupons' measurement sheets (sheets/*.csv) beside it.

    python3 research/leg-preprint/screen.py           # regenerate
    python3 research/leg-preprint/screen.py --check   # exit 1 if any output is stale

Every number is a screen with its assumption stated, not a qualification. CAD and FEA do not prove fit or strength:
the coupons in README.md and the proof loads in issue #29 do.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'research/insert-joints'))
from inventory import Repo, Stale  # noqa: E402  (the bound-source reader the insert inventory uses)

OUT_JSON = HERE / 'screen.json'
OUT_MD = HERE / 'screen.md'
SHEETS = HERE / 'sheets'
LAYER_EVIDENCE = 'research/fea-v060-29/evidence/leg-layer-check.json'
ORIENT_EVIDENCE = 'research/leg-preprint/evidence/orientation-screen.json'

SOURCES = {
    'bambu_tds': 'Bambu Lab PA6-CF technical data sheet V3.0 (catalog/materials.json pa6-cf source)',
    'cadagent_rows': "cad-agent v0.6.0 cadagent/simulation/fea.py MATERIALS pa6_cf_xy / pa6_cf_z (humid = Polymaker "
                     "PA6-CF20 wet / dry, x0.8 print)",
    'iso286': 'ISO 286-2 tolerance grades (F7, f9, n6, m6)',
    'din179': 'DIN 179 drill bushings: bore F7, outside n6 (catalog/hardware.json eye_sleeve tolerances)',
    'iso7379': 'ISO 7379 shoulder screws: shoulder f9',
    'iso5753': 'ISO 5753-1 radial internal clearance, group N',
    'skf6301': 'SKF 6301-2RSH product page (catalog/hardware.json bearing_6301: C0 4.15 kN, da min 17.6)',
    'lame': 'Lame thick-cylinder press fit, rigid steel insert: p = (delta / D) E / ((Do^2 + D^2) / (Do^2 - D^2) + nu)',
    'vdi2230': 'VDI 2230 joint diagram: preload lost = embedding x k_bolt k_clamp / (k_bolt + k_clamp)',
    'loctite638': 'Henkel LOCTITE 638 technical data sheet: "not normally recommended for use on plastics (particularly '
                  'thermoplastic materials where stress cracking of the plastic could result)"; inactive surfaces want Activator '
                  '7471 / 7649; bond gaps up to about 0.25 mm',
    'iso898': 'ISO 898-1 proof stress: 8.8 580 MPa (d <= 16: 600), 12.9 970 MPa; stress areas M4 8.78, M5 14.2, '
              'M6 20.1, M10 58.0 mm2',
}

# ---------------------------------------------------------------------------------------------------- basis
E_STEEL = 210000.0
NU = 0.35                     # PA6-CF (cad-agent row)
MU_PRESS = 0.25               # steel on printed PA6-CF, for press-in force (assumed; C1 measures it)
K_NUT = 0.2                   # as research/insert-joints (unstated condition)
PRINT_HOLE_ERR = (-0.20, -0.05)   # mm on a vertical printed hole's diameter against the CAD (it closes up): assumed band
                                  # until C1 measures this printer, this filament and this recipe
AS_MM2 = {4: 8.78, 5: 14.2, 6: 20.1, 10: 58.0}
PROOF_MPA = {'8.8': 600.0, '12.9': 970.0}
PRELOAD_OF_PROOF = 0.6        # a steel-on-steel joint's working preload, of the proof load
SPOOL_G = 1000.0              # a 1 kg spool
LONG_PRINT_H = 24.0
OVERHANG_NZ = -math.cos(math.radians(45.0))   # a face pointing down more than 45 deg from vertical wants support
CREEP_STEPS_MM = (0.05, 0.2)  # embedding + creep of the clamped plastic to screen (no creep data: C3 measures it)


def r(x, n=2):
    return None if x is None else round(float(x), n)


def annulus(od, idd):
    return math.pi / 4 * (od * od - idd * idd)


def proof_preload(d, grade):
    return PRELOAD_OF_PROOF * PROOF_MPA[grade] * AS_MM2[d]


def torque_for(f, d):
    return K_NUT * f * d / 1000.0


# ---------------------------------------------------------------------------------------------------- materials

def materials(repo):
    """The humid design rows (the leg records' cad-agent rows, carried in the layer-check evidence) and the dry TDS
    moduli the press fits see at assembly."""
    ev = repo.json(LAYER_EVIDENCE)
    md = next(row['material_data'] for row in ev['rows'] if row['material_data']['key'] == 'pa6_cf_xy')
    mz = next(row['material_data'] for row in ev['rows'] if row['material_data']['key'] == 'pa6_cf_z')
    tds = repo.json('catalog/materials.json')['pa6-cf']
    s_z = md['strength_z_mpa']
    return {
        'E_xy_humid': md['E_mpa'], 'E_z_humid': mz['E_mpa'],
        'E_xy_dry': tds['modulus_gpa'] * 1000.0, 'E_z_dry': 2170.0, 'S_xy_dry': float(tds['tensile_mpa']),
        'S_xy': md['strength_xy_mpa'], 'S_z': s_z, 'S_s': s_z / math.sqrt(3), 'S_s_half': s_z / 2,
        'density': tds['density_g_cm3'],
        'washer_mpa': repo.num('cad/studies.py', r"'washer_mpa': ([\d.]+),"),
        'bearing_humid_mpa': repo.num('cad/studies.py', r"'bearing_mpa': ([\d.]+),"),
        'source': f"{SOURCES['cadagent_rows']}; dry moduli {SOURCES['bambu_tds']} (X-Y {tds['modulus_gpa']:g} GPa, Z 2.17 GPa)",
    }


# ---------------------------------------------------------------------------------------------------- print STLs

def stl_triangles(path):
    b = path.read_bytes()
    if b[:5] == b'solid' and b'facet' in b[:400]:
        raise Stale(f'{path}: ASCII STL; the screen reads the binary exports')
    n = struct.unpack('<I', b[80:84])[0]
    for i in range(n):
        v = struct.unpack_from('<12f', b, 84 + 50 * i)
        yield v[3:6], v[6:9], v[9:12]


def stl_faces(path):
    """Bed contact (cm2), the area of faces pointing down more than 45 deg off vertical above the bed (cm2) by 1 mm
    height band, the height, and the bed footprint's bounding box."""
    bed = 0.0
    bands = {}
    zmax = 0.0
    xs, ys = [], []
    for a, b, c in stl_triangles(path):
        ux, uy, uz = (b[i] - a[i] for i in range(3))
        vx, vy, vz = (c[i] - a[i] for i in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        two = math.sqrt(nx * nx + ny * ny + nz * nz)
        if two == 0:
            continue
        zmax = max(zmax, a[2], b[2], c[2])
        xs += [a[0], b[0], c[0]]
        ys += [a[1], b[1], c[1]]
        if nz / two < OVERHANG_NZ:
            zc = (a[2] + b[2] + c[2]) / 3
            if zc < 0.05:
                bed += two / 2
            else:
                k = int(round(zc))
                bands[k] = bands.get(k, 0.0) + two / 2
    return {'bed_cm2': bed / 100, 'overhang_cm2': sum(bands.values()) / 100, 'height_mm': zmax,
            'bands': sorted(((k, a / 100) for k, a in bands.items()), key=lambda kv: -kv[1])}


def print_parts(repo, mat):
    plan = repo.json('exports/leg/print-plan.json')
    rot = {}
    text = repo.text('cad/build_leg.py')
    for name in plan['parts']:
        found = [d for d in ('DOWN_OUTER', 'DOWN_INNER') if f"'{name}': {d}" in text]
        if len(found) != 1:
            raise Stale(f"cad/build_leg.py: no single ROT entry for {name}; update research/leg-preprint/screen.py")
        repo.has('cad/build_leg.py', f"'{name}': {found[0]}")
        rot[name] = found[0]
    repo.has('cad/build_leg.py', "DOWN_OUTER = ((1, 0, 0), -90)        # the part's +y face on the bed")
    repo.has('cad/build_leg.py', "DOWN_INNER = ((1, 0, 0), 90)         # its -y face on the bed")
    rows = []
    for name, p in plan['parts'].items():
        stl = ROOT / 'exports/leg' / f'{name}.stl'
        f = stl_faces(stl) if stl.exists() else None
        flags = []
        if f and f['overhang_cm2'] > f['bed_cm2']:
            big_z, big_a = f['bands'][0]
            flags.append(('floats', f"more overhang ({f['overhang_cm2']:.0f} cm2) than bed contact ({f['bed_cm2']:.0f} cm2): "
                                    f"it stands on {f['bed_cm2']:.0f} cm2 and {big_a:.0f} cm2 of its underside hangs {big_z} mm up; "
                                    "it needs support under that or another orientation"))
        elif f and f['overhang_cm2'] > 10:
            flags.append(('supports', f"{f['overhang_cm2']:.0f} cm2 of overhang steeper than 45 deg; biggest at z "
                                      + ', '.join(f'{k} mm ({a:.0f} cm2)' for k, a in f['bands'][:3])))
        if p['grams_each'] * 1.05 > SPOOL_G:
            flags.append(('spool', f"{p['grams_each']} g + 5 % purge and brim is over a {SPOOL_G:.0f} g spool: a spool change "
                                   "mid-print; both spools dried together, the same lot"))
        if p['hours'] / max(p['qty'], 1) > LONG_PRINT_H:
            flags.append(('long', f"{p['hours'] / p['qty']:.0f} h a part: dry feed (< 20 % RH) for the whole print; "
                                   "the bed and enclosure at temperature throughout"))
        rows.append({'part': name, 'material': p['material'], 'qty': p['qty'], 'size_mm': p['size_mm'],
                     'placement': p['placement'], 'grams_each': p['grams_each'], 'hours_each': r(p['hours'] / p['qty'], 1),
                     'orientation': rot.get(name), 'stl': None if f is None else {
                         'bed_cm2': r(f['bed_cm2'], 1), 'overhang_cm2': r(f['overhang_cm2'], 1),
                         'height_mm': r(f['height_mm'], 1), 'top_bands': [[k, r(a, 1)] for k, a in f['bands'][:3]]},
                     'flags': [{'code': c, 'text': t} for c, t in flags]})
    return {'bed_mm': plan['bed_mm'], 'total_hours': plan['total_hours'], 'total_grams': plan['total_grams'], 'parts': rows}


# ---------------------------------------------------------------------------------------------------- layers

def layer_rows(repo, mat):
    """The record's layer check (cad-agent v0.6.0 Study.layer_check on the record's solves), and what each row needs."""
    ev = repo.json(LAYER_EVIDENCE)
    out = []
    for row in ev['rows']:
        lc = row['layer_check']
        w = lc['worst']
        sf, tgt = lc['safety_factor'], row['target']
        sn, tau = max(w['sigma_n_mpa'], 0.0), abs(w['tau_n_mpa'])
        lim = 1.0 / tgt
        need_ss = None
        if sn / mat['S_z'] < lim:
            need_ss = tau / math.sqrt(lim ** 2 - (sn / mat['S_z']) ** 2) if tau > 0 else 0.0
        reduce = tgt / sf if sf else None
        out.append({'part': row['part'], 'case': row['case'], 'target': tgt, 'gate_sf': row['gate_sf'], 'layer_sf': sf,
                    'layer_sf_at_half_sz': row['shear_half_sz']['safety_factor'], 'governed_by': lc['governed_by'],
                    'sigma_n_mpa': r(w['sigma_n_mpa'], 1), 'tau_mpa': r(w['tau_n_mpa'], 1),
                    'corner_mm': [r(v, 1) for v in w['corner_mm']], 'ok': sf >= tgt,
                    'stress_reduction_needed': None if sf >= tgt else r(reduce, 2),
                    'root_radius_factor_if_bending': None if sf >= tgt else r(reduce ** (1 / 3), 2),
                    'S_s_needed_mpa': None if sf >= tgt else (r(need_ss, 1) if need_ss is not None else 'none: sigma_n alone fails'),
                    'where': where(row['part'], w['corner_mm'], repo)})
    return {'source': LAYER_EVIDENCE, 'toolkit': ev.get('toolkit_version'), 'mesh_mm': ev.get('mesh_mm'),
            'source_revision': ev.get('source_revision'), 'rows': out}


def where(part, c, repo):
    """A plain name for a worst corner, from the part's own frame (each part's origin and axes as cad/fivebar.py)."""
    if getattr(repo, '_links', None) is None:      # bound once per repository object, not once per row
        repo._links = (repo.num('cad/fivebar.py', r"'D': [\d.]+, 'l1': ([\d.]+), 'l2'"),
                       repo.num('cad/fivebar.py', r"'D': [\d.]+, 'l1': [\d.]+, 'l2': ([\d.]+),"))
    l1, l2 = repo._links
    x, y, z = c
    if part == 'upper_link':
        rk = math.hypot(x - l1, z)
        if rk < 30 and y < 1:
            return f'knee eye stub root (r {rk:.1f} from the knee axis, {-y:.1f} mm into the stub)'
        rh = math.hypot(x, z)
        if abs(rh - 20.05) < 1.0:
            return f'hub, the Ø40 spigot recess\'s rim on the inner face (r {rh:.1f})'
        return f'hub (r {rh:.1f} from the motor axis), inner face'
    if part == 'front_link':
        ra = math.hypot(x - l2, z)
        if ra < 50:
            return f'apex eye ring (r {ra:.1f} from the apex axis, y {y:.1f})'
        return f'body at x {x:.0f}'
    if part == 'wheel_link':
        ra = math.hypot(x - l2, z)
        if ra < 40:
            return f'apex hub root (r {ra:.1f} from the apex axis, at the link\'s inner face y {y:.1f})'
        return f'knee boss root (r {math.hypot(x, z):.1f} from the knee axis, y {y:.1f})'
    if part == 'hip_frame':
        if abs(abs(z) - 63.5) < 2:
            return f'flange root, inner face (x {x:.0f}, y {y:.1f})'
        return f'web, motor side (x {x:.0f}, z {z:.0f})'
    return ''


def orientation(repo):
    p = ROOT / ORIENT_EVIDENCE
    if not p.exists():
        return None
    ev = repo.json(ORIENT_EVIDENCE)
    rows, seen = [], set()
    for row in ev['rows']:
        if (row['part'], row['case']) in seen:          # a study that solves a case twice (buckling, the R1w spike) repeats it
            continue
        seen.add((row['part'], row['case']))
        o = row['orientations']
        best = max(o, key=lambda k: o[k]['sf'])
        rows.append({'part': row['part'], 'case': row['case'], 'target': row['target'], 'gate_sf': row['gate_sf'],
                     'y': o['y']['sf'], 'z': o['z']['sf'], 'x': o['x']['sf'], 'best': best,
                     'best_ok': o[best]['sf'] >= row['target']})
    return {'source': ORIENT_EVIDENCE, 'toolkit': ev['toolkit'], 'mesh_mm': ev['mesh_mm'],
            'source_revision': ev['source_revision'], 'rows': rows}


# ---------------------------------------------------------------------------------------------------- fits

def lame(delta, d, do, e):
    """Interface pressure and bore hoop stress of a rigid insert pressed into a printed ring (MPa)."""
    if do is None:                                     # a hole in a wide plate
        k = 1.0
    else:
        k = (do * do + d * d) / (do * do - d * d)
    p = delta / d * e / (k + NU)
    return p, p * k


def fit_verdict(band, dry, press, s_dry):
    out = []
    if dry[1] > 0.5 * s_dry:
        out.append(f'too tight once printed: {dry[1]:.0f} MPa hoop at the tight end (> half the dry strength); open the hole')
    if press > 5000:
        out.append(f'{press / 1000:.0f} kN to press at the tight end: more than a bench vise')
    if band[0] < 0 < band[1]:
        out.append('from clearance to interference across the band: C1 sets the hole')
    elif band[1] <= 0:
        out.append('clearance across the band')
    return '; '.join(out) or 'within the band'


def fits(repo, mat):
    """Press and slide fits into printed holes: the CAD's hole, the part's tolerance, the interference band once the
    printed hole closes up by PRINT_HOLE_ERR, and what that does dry (at assembly) and humid (in service)."""
    eye_r = repo.num('cad/fivebar.py', r"'eye_r': ([\d.]+), 'eye_stub_fillet'")
    comp = repo.num('cad/fivebar.py', r'^PRINT_HOLE_COMP = ([\d.]+)')
    repo.has('cad/fivebar.py', 'u = u.cut(ycyl(EYE_SLEEVE[0] / 2 + PRINT_HOLE_COMP / 2, eye_sleeve_end(), t + 1, l1, 0))')
    sleeve_hole = repo.num('cad/fivebar.py', r'^EYE_SLEEVE = \(([\d.]+), ') + comp
    repo.has('cad/fivebar.py', "re, fe = P['eye_r'], P['eye_stub_fillet']")
    stub_in = repo.num('cad/fivebar.py', r"ycyl\(re - ([\d.]+), -EYE_BOSS, 0\.01, l1, 0\)")   # the eye stub's radius
    sl_len = repo.num('cad/fivebar.py', r'^EYE_SLEEVE = \([\d.]+, [\d.]+, ([\d.]+)\)')
    sl_n = repo.num('cad/fivebar.py', r'^EYE_SLEEVES = (\d+)')
    kc_od = repo.num('cad/fivebar.py', r"'bearing': '6301-2RS', 'bearing_od': ([\d.]+),")
    kc_hub = repo.num('cad/fivebar.py', r"'bearing_od': [\d.]+, 'bearing_w': [\d.]+, 'hub_od': ([\d.]+),")
    kc_w = repo.num('cad/fivebar.py', r"'bearing': '6301-2RS', 'bearing_od': [\d.]+, 'bearing_w': ([\d.]+),")
    kc_play = repo.num('cad/fivebar.py', r"c = ycyl\(bo / 2 \+ ([\d.]+), y0 - 0\.01, y0 \+ bw\)")
    ac = repo.json('cad/interfaces.json')['AC-L']
    ac_play = repo.num('cad/fivebar.py', r"f = f\.cut\(ycyl\(AC\['bearing_od'\] / 2 \+ ([\d.]+), ao\[0\], e1 \+ 1, l2\)\)")
    repo.has('cad/fivebar.py', "r_eye = AC['bearing_od'] / 2 + P['apex_wall']")
    ring_wall = repo.num('cad/fivebar.py', r"'apex_wall': ([\d.]+), 'front_eye_fillet'")
    dw = r'web = web\.cut\(ycyl\({} \+ PRINT_HOLE_COMP / 2 \+ {}, yf0 - 1, yf0 \+ {}, x, z\)\)'
    num, any_ = r'([\d.]+)', r'[\d.]+'
    dowel_r = repo.num('cad/fivebar.py', dw.format(num, any_, any_)) + comp / 2
    dowel_cut = -repo.num('cad/fivebar.py', dw.format(any_, num, any_))
    dowel_in = repo.num('cad/fivebar.py', dw.format(any_, any_, num))
    stop_d = repo.num('cad/fivebar.py', r'^STOP_PIN = \(([\d.]+), ')
    stop_play = repo.num('cad/fivebar.py', r'^STOP_HOLE_PLAY = ([\d.]+)')
    stop_in = repo.num('cad/fivebar.py', r'^STOP_PIN = \([\d.]+, [\d.]+, ([\d.]+)\)')
    journal = 2 * repo.num('cad/fivebar.py', r"\.union\(ycyl\(([\d.]+), h0, ab1 \+ 0\.01, l2\)\)")
    hw = {i['key']: i for i in repo.json('catalog/hardware.json')}
    sl_tol = hw['eye_sleeve']['specs']['od_tol_mm']
    rows = [
        # name, part, hole as drawn, the mating part's diameter band, ring OD (None: plate), engaged length, mouth on the bed?
        ('knee eye sleeves (2 x DIN 179 18 x 20)', 'upper_link', sleeve_hole, (18 + sl_tol[0], 18 + sl_tol[1]),
         2 * (eye_r - stub_in), sl_n * sl_len, True, 'pressed in from the outer face, which is on the bed (DOWN_OUTER)'),
        ('knee 6301 outer races', 'front_link / wheel_link', kc_od + 2 * kc_play, (kc_od - 0.011, kc_od), kc_hub, kc_w,
         True, 'one of the two seats opens on the bed face in each lower link'),
        ('apex 61812 outer races', 'front_link', ac['bearing_od'] + 2 * ac_play, (ac['bearing_od'] - 0.013, ac['bearing_od']),
         ac['bearing_od'] + 2 * ring_wall, ac['bearing_w'], True, 'the inner seat opens on the bed face (DOWN_INNER)'),
        ('RS-04 dowels (2 x 5 m6)', 'hip_frame', 2 * (dowel_r - dowel_cut), (5.004, 5.012), None, dowel_in, False,
         'blind from the motor side (the top as printed)'),
        ('stop pins (16 x 40, epoxy-bonded)', 'hip_frame', stop_d + 2 * stop_play, (stop_d + 0.007, stop_d + 0.018),
         None, stop_in, True, 'blind from the leg side, which is on the bed (DOWN_OUTER)'),
    ]
    out = []
    for name, part, hole, (lo, hi), do, L, bed, note in rows:
        drawn = (lo - hole, hi - hole)                       # + = interference (diameter)
        band = (drawn[0] - PRINT_HOLE_ERR[1], drawn[1] - PRINT_HOLE_ERR[0])
        dry = lame(max(band[1], 0.0), (lo + hi) / 2, do, mat['E_xy_dry'])
        hum = lame(max(band[1], 0.0), (lo + hi) / 2, do, mat['E_xy_humid'])
        press = MU_PRESS * dry[0] * math.pi * (lo + hi) / 2 * L
        out.append({'fit': name, 'part': part, 'hole_drawn_mm': r(hole, 3), 'mating_mm': [r(lo, 3), r(hi, 3)],
                    'ring_od_mm': do, 'length_mm': L,
                    'interference_drawn_mm': [r(drawn[0], 3), r(drawn[1], 3)],
                    'interference_printed_mm': [r(band[0], 3), r(band[1], 3)],
                    'at_max_dry': {'p_mpa': r(dry[0], 1), 'hoop_mpa': r(dry[1], 1), 'hoop_of_S_xy_dry': r(dry[1] / mat['S_xy_dry'], 2),
                                   'press_n': r(press, -1)},
                    'at_max_humid': {'p_mpa': r(hum[0], 1), 'hoop_mpa': r(hum[1], 1)},
                    'grip_lost_humid': r(1 - hum[0] / dry[0], 2) if dry[0] else None,
                    'mouth_on_bed': bed, 'note': note, 'verdict': fit_verdict(band, dry, press, mat['S_xy_dry'])})
    return {'basis': f"printed vertical hole {PRINT_HOLE_ERR[0]:+.2f} to {PRINT_HOLE_ERR[1]:+.2f} mm on the diameter against the "
                     f"CAD (assumed: C1 measures it); {SOURCES['lame']}; dry X-Y modulus {mat['E_xy_dry']:.0f} MPa at "
                     f"assembly, humid {mat['E_xy_humid']:.0f} in service; press force at mu {MU_PRESS}; hoop stress "
                     "against the dry X-Y TDS strength 102 MPa (the hoop runs in the layers)", 'rows': out}


# ---------------------------------------------------------------------------------------------------- clamps and preload

def clamp_row(name, d, grip_mm, area_mm2, preload_n, mat, bolt_len_mm, sleeve=False):
    """The clamped plastic's elastic squeeze and the preload a creep step takes, VDI 2230's joint diagram with the
    plastic as one prismatic member under the bearing area. VDI 2230's substitute cone (set by the member's own
    geometry) is left out, so k_clamp is understated and the preload a step takes is a lower bound. A fixed step is a
    different strain on each grip: compare joints by the strain they can take, not by the newtons one step costs."""
    k_b = E_STEEL * AS_MM2[d] / bolt_len_mm
    if sleeve:
        return {'joint': name, 'clamp': 'steel sleeve (the plastic is outside the clamp path)', 'k_bolt_kn_mm': r(k_b / 1000, 1),
                'preload_n': r(preload_n, -1), 'stress_mpa': None, 'squeeze_mm': None,
                'lost_n': {str(s): 0 for s in CREEP_STEPS_MM}, 'note': 'creep of the plastic does not reach the preload'}
    k_p = mat['E_z_humid'] * area_mm2 / grip_mm
    k = k_b * k_p / (k_b + k_p)
    s = preload_n / area_mm2
    return {'joint': name, 'clamp': f'{grip_mm:g} mm of PA6-CF across its layers under {area_mm2:.0f} mm2',
            'k_bolt_kn_mm': r(k_b / 1000, 1), 'k_plastic_kn_mm': r(k_p / 1000, 2), 'preload_n': r(preload_n, -1),
            'stress_mpa': r(s, 1), 'squeeze_mm': r(s / mat['E_z_humid'] * grip_mm, 2),
            'lost_n': {str(st): r(min(preload_n, st * k), -1) for st in CREEP_STEPS_MM},
            'lost_frac': {str(st): r(min(1.0, st * k / preload_n), 2) for st in CREEP_STEPS_MM}}


def preload_table(repo, mat, J):
    hub, lugs, wheel = J['leg.upper_link_hub'], J['leg.hip_frame_lugs'], J['leg.wheel_botwheel']
    hub_pre = repo.num('cad/leg_studies.py', r'^HUB_PRELOAD_N = ([\d.]+)')
    rows = [
        clamp_row('upper link hub, today (M5 head on the link)', 5, hub['clamp']['printed_mm'], hub['clamp']['bearing_area_mm2'],
                  hub_pre, mat, 40.0),
        clamp_row('hip frame lugs, today (M4 head on the web)', 4, lugs['clamp']['printed_mm'], lugs['clamp']['bearing_area_mm2'],
                  mat['washer_mpa'] * lugs['clamp']['bearing_area_mm2'], mat, 20.0),
        clamp_row('wheel foot, today (M6 head on the foot)', 6, wheel['clamp']['printed_mm'], wheel['clamp']['bearing_area_mm2'],
                  wheel['clamp']['preload_at_sustained_n'], mat, 30.0),
        clamp_row('upper link hub, 6061 clamp ring (per screw share)', 5, hub['clamp']['printed_mm'] - 4.0,
                  HUB_RING_AREA / 8, 4000.0, mat, 40.0),
        clamp_row('hip frame mount, through-bolt on the plastic', 5, FRAME_GRIP, annulus(15.0, 5.5), 3000.0, mat, FRAME_GRIP + 12),
        clamp_row('hip frame mount, sleeved through-bolt', 5, FRAME_GRIP, annulus(15.0, 5.5), proof_preload(5, '8.8'), mat,
                  FRAME_GRIP + 12, sleeve=True),
    ]
    return {'basis': f"{SOURCES['vdi2230']}; plastic modulus across the layers, humid: {mat['E_z_humid']:.0f} MPa "
                     f"(dry {mat['E_z_dry']:.0f}); creep steps {CREEP_STEPS_MM} mm are screens, not data: C3 measures them",
            'rows': rows}


HUB_RING_AREA = annulus(66.0, 41.0) - 8 * annulus(5.5, 0)     # a 6061 ring Ø66 / Ø41 under the 8 hub screws, less holes
# masses (g) for the mass column: estimates from steel volume (7.85 g/cm3), the catalogue's insert entry; mcmaster-parts
# replaces them with the chosen parts' masses in PR 2
SHCS_G = {'M5x90': 16.0, 'M5x16': 3.6}
WASHER_9021_M5_G = annulus(15.0, 5.3) * 1.2 * 7.85e-3    # DIN 9021 M5, 1.2 thick, steel
NUT_G = {'M5': 1.2}
INSERT_G = {'M5': 1.103}


def sleeve_g(length, density, od=8.0, idd=5.3):
    return annulus(od, idd) * length / 1000 * density
FRAME_GRIP = 81.3 - 4.5                                         # flange end (y -82.3) to the web's leg face (y -1.0), less a nut pocket


# ---------------------------------------------------------------------------------------------------- joints

def joints(repo, mat, layers):
    inv = repo.json('research/insert-joints/joints.json')
    J = {j['id']: j for j in inv['joints'] if j['id'].startswith('leg.')}
    S = repo.json('exports/leg/fea/summary.json')['joints']
    worst = {}
    for row in layers['rows']:
        k = (row['part'], row['where'].split(' (')[0])
        if k not in worst or row['layer_sf'] < worst[k]['layer_sf']:
            worst[k] = row
    out = []

    # 1. hip frame to the body cheek / rig plate
    hf = J['leg.hip_frame_mount']
    pull = hf['pullout_repo_n']
    fault = max(l['per_insert_n'] for l in hf['loads'])
    flange_t = repo.num('cad/fivebar.py', r'^FLANGE_T, FLANGE_X = ([\d.]+), ')
    knurl = repo.json('research/insert-joints/joints.json')['inserts']['insert_m5']['od_mm']
    wall = (flange_t - knurl) / 2             # the M5 insert's knurl (research/insert-joints) centred in the flange
    sleeved = proof_preload(5, '8.8')
    flange = [row for row in layers['rows'] if row['part'] == 'hip_frame' and row['where'].startswith('flange')]
    flange_root = min(flange, key=lambda x: x['layer_sf'] / x['target'])
    out.append(joint_entry(
        'leg.hip_frame_mount', hf['qty_robot'], 'the whole leg hangs on these six; the flange root is the frame\'s worst corner',
        today=f"M5 heat-set insert in each flange end, pilot Ø{hf['hole']['d']:g} x {hf['hole']['depth']:g}, its axis the build "
              f"direction; {wall:.2f} mm of wall each side in the {flange_t:g} mm flange; {hf['torque_nm']:g} N m",
        high=[f"fault tension {fault:.0f} N an insert against an estimated {pull:.0f} N pull-out (SF {pull / fault:.2f}), "
              "pulled across the layers",
              f"the assembly torque preloads it to {hf['preload_n'] / pull:.2f} x that (humid) pull-out if the cheek misses the "
              "insert's brass face; with the face bearing (the inventory's condition) the preload closes through the brass",
              f"the flange's layer check: {flange_root['case']} {flange_root['layer_sf']} against {flange_root['target']} "
              f"({flange_root['where']}), 6 mm past the inserts' pilots"],
        options={
            'insert': f"today; keep preload <= 0.5 x pull-out ({0.5 * pull:.0f} N, {torque_for(0.5 * pull, 5):.2f} N m) and the "
                      f"fault load ({fault:.0f} N) opens the joint; spin-out is not measured",
            'sleeved through-bolt': f"M5 8.8 through the flange's length and the web ({FRAME_GRIP:.1f} mm of steel sleeve, Ø8 x Ø5.3), "
                                    f"nut on a DIN 9021 M5 washer (Ø15) in a Ø15.5 pocket on the web's leg face, so the fault "
                                    f"tension bears on the web round the sleeve; head on the cheek / under the plate: preload "
                                    f"{sleeved:.0f} N ({torque_for(sleeved, 5):.1f} N m) in steel, {sleeved / fault:.1f} x the fault "
                                    "tension; no insert, no creep in the clamp",
            'threaded-rod tie': 'the same with M5 rod and two nuts where no head fits; no gain here (the cheek side takes a head)',
            'captive nut': f"a hex nut in a side pocket near the flange end: the {wall:.1f} mm walls either side of an 8 mm nut "
                           "split the flange; rejected",
            'through-bolt on the plastic': "no sleeve: the bolt precompresses the flange along its length (across the layers, "
                                           "the root's peel direction), but the preload creeps away (see preload)",
        },
        pick='sleeved through-bolt',
        why=f'D74: the leg\'s primary load path; the {fault:.0f} N fault tension is {fault / pull:.2f} x the insert\'s estimated '
            'humid pull-out, with no measured spin-out or creep (and up to 1.0 x at assembly if the cheek misses the brass '
            'face). The sleeve keeps the '
            'preload out of the plastic; the flange root is then judged without precompression (conservative).',
        pr2='cad/fivebar.py frame_mounts(): 6 x Ø8.1 sleeve bores through the flange and web, an M5 hex pocket on the leg face; '
            f'the Ø8.1 bore leaves {(flange_t - 8.1) / 2:.2f} mm walls in the {flange_t:g} mm flange, so the bolt line gets a local boss and the '
            'frame is re-run; the rig plate and the body cheek keep their Ø5.5 holes; screws M5 x ~90 (mcmaster-parts). Mass '
            f'with a 6061 sleeve; a steel one adds {6 * sleeve_g(FRAME_GRIP, 7.85) - 6 * sleeve_g(FRAME_GRIP, 2.70):.0f} g more',
        mass_g_per_leg=6 * (sleeve_g(FRAME_GRIP, 2.70) + SHCS_G['M5x90'] + NUT_G['M5'] + WASHER_9021_M5_G - SHCS_G['M5x16']
                            - INSERT_G['M5'])
        - 6 * annulus(8.1, 0) * FRAME_GRIP / 1000 * mat['density']))

    # 2. upper link hub on the machined adapter
    hub = J['leg.upper_link_hub']
    h1, h3 = S['R1']['hub_rear'], S['R3']['hub_rear']
    hub_pre = repo.num('cad/leg_studies.py', r'^HUB_PRELOAD_N = ([\d.]+)')
    ring_pre = 4000.0
    lift_ring = h1['edge_lifts_at_nm'] * 8 * ring_pre / (8 * hub_pre)
    out.append(joint_entry(
        'leg.upper_link_hub', hub['qty_robot'], 'the motor\'s torque and the leg\'s out-of-plane moment into the link',
        today=f"8 x M5 x 40 into the tapped 6061 adapter, heads on {hub['clamp']['printed_mm']:g} mm of PA6-CF (Ø8.5 heads, "
              f"no washer); {hub['torque_nm']:g} N m puts {hub['clamp']['bearing_mpa']:g} MPa under each head",
        high=[f"the hub's edge lifts at {h1['edge_lifts_at_nm']:g} N m (at {hub_pre:g} N a screw); R1 puts "
              f"{h1['out_of_plane_nm']:g} and R3 {h3['out_of_plane_nm']:g} N m on it",
              f"{hub['clamp']['bearing_mpa']:g} MPa under the heads against the {mat['washer_mpa']:g} MPa sustained screen"],
        options={
            'insert': 'n/a (the receiver is the machined adapter)',
            'sleeved through-bolt': 'a crush sleeve per screw keeps the preload, but then nothing clamps the printed face: '
                                    'the moment rocks the link on its sleeves; no',
            'clamp ring': f"a 6061 ring Ø66 / Ø41 x 4 under all 8 heads ({HUB_RING_AREA:.0f} mm2): {ring_pre:.0f} N a screw is "
                          f"{8 * ring_pre / HUB_RING_AREA:.1f} MPa on the plastic, the face stays shut to about "
                          f"{lift_ring:.0f} N m (the edge-lift moment scales with the clamp); layers in compression",
            'metal bushing': 'a machined hub insert: the adapter (D46) already is one; growing it is the fallback',
        },
        pick='clamp ring',
        why='D74: the clamp spreads over the hub so the screws can carry a real preload while the plastic stays under the '
            'sustained screen and in compression across its layers. Re-torque after 24 h and after the first humid week.',
        pr2='cad/fivebar.py upper_link(): a Ø66 / Ø41 x 4 recess at the counterbores\' floor for the ring; HUB_PRELOAD_N to the '
            'ring preload in cad/leg_studies.py; the ring as a made-to-order part with the adapter',
        mass_g_per_leg=2 * (HUB_RING_AREA * 4 / 1000 * 2.70 - HUB_RING_AREA * 4 / 1000 * mat['density'])))

    # 3. hip frame onto each RS-04
    lugs = J['leg.hip_frame_lugs']
    out.append(joint_entry(
        'leg.hip_frame_lugs', lugs['qty_robot'], 'holds each motor on the frame; the dowels carry its torque',
        today=f"10 x M4 x 20 12.9 into the RS-04 case (5 mm thread), heads on {lugs['clamp']['printed_mm']:g} mm of PA6-CF; "
              "no torque set (issue #116)",
        high=[lugs['notes'].split('. ')[1] if '. ' in lugs['notes'] else lugs['notes']],
        options={
            'insert': 'n/a (the receiver is the motor\'s case)',
            'sleeved through-bolt': f"a steel crush sleeve Ø7 x Ø4.3 x {lugs['clamp']['printed_mm']:g} under each head: the torque is "
                                    "then set by the motor's thread, not the plastic, and creep cannot loosen it",
            'clamp ring': 'one 6061 ring under the 10 heads: heavier and in the way of the counterbores; no',
        },
        pick='sleeved through-bolt',
        why='D74: the motor\'s mount; today the plastic limits each screw to about 565 N. Coordinate with the RS-04 support '
            'work (issue #116) and its fit job before changing the frame\'s lug ring.',
        pr2='recommended; held until issue #116\'s mounting stack is settled (its fit job prints this ring)',
        mass_g_per_leg=r(2 * 10 * (annulus(7.0, 4.3) * 7.85 - annulus(7.0, 4.5) * mat['density']) * lugs['clamp']['printed_mm'] / 1000, 0)))

    # 4. knee eye sleeves (upper link)
    ke = J['leg.knee_eye_sleeves']
    k3 = S['R3']['knee_rear']
    stub = min((row for row in layers['rows'] if row['part'] == 'upper_link' and row['where'].startswith('knee')),
               key=lambda x: x['layer_sf'] / x['target'])
    out.append(joint_entry(
        'leg.knee_eye_sleeves', ke['qty_robot'], 'the knee pin\'s moment into the upper link',
        today='two DIN 179 sleeves pressed into the eye (already metal bushings), the shoulder screw clamped by the M10 nyloc',
        high=[f"the eye stub's root: layer check {stub['case']} {stub['layer_sf']} against {stub['target']} (the worst in the leg)",
              f"R3: {k3['moment_at_sleeve_nm']:g} N m at the sleeves, {k3['eye_pressure']['mpa']:g} MPa on the eye "
              f"(SF {k3['eye_pressure']['sf']:g})"],
        options={
            'metal bushing': 'today\'s sleeves stay; the stub around them grows (diameter and root fillet) until its root '
                             'passes, judged by the layer check',
            'sleeved through-bolt': 'tie bolts through the stub into the link body (precompressing the root): they cross the '
                                    'sleeves\' bore; no room at Ø40',
            'metal eye': 'a machined 6061 eye block bolted to the link (the D46 pattern): the fallback if the stub cannot pass',
        },
        pick='metal bushing',
        why='The bushing is right; its plastic seat is not. A rounder, larger stub lowers the root\'s peel; orientation does '
            'not help it (orientation screen).',
        pr2='cad/fivebar.py: the stub\'s diameter and root fillet swept on the compute host; a 0.5 x 45 deg lead-in at the bed-face '
            'mouth; the outer sleeve 0.1-0.2 mm proud',
        mass_g_per_leg=None))

    # 5. knee bearings and spacer (lower links)
    ks = J['leg.knee_spacer']
    hw = {i['key']: i for i in repo.json('catalog/hardware.json')}
    da = hw['bearing_6301']['specs']['abutments_mm']
    out.append(joint_entry(
        'leg.knee_spacer', ks['qty_robot'], 'the inner races\' clamp at each knee',
        today='5/8 in 6061 tube between the two 6301 inner races, the 10 kN knee clamp through it',
        high=[f"its Ø15.9 face is under the 6301's da min {da['da_min']:g} mm: the clamp bears on the inner race's corner radius"],
        options={'metal bushing': f"a steel spacer Ø{da['da_min'] + 0.4:.0f}-{da['da_max']:g} x Ø12.1, faced to the measured web gap "
                                  "(+0 / +0.05)"},
        pick='metal bushing', why='SKF\'s abutment rule; the same part count',
        pr2='a McMaster steel spacer in the da window (mcmaster-parts), cut and faced', mass_g_per_leg=2 * 3.0))

    # 6. apex
    ax = S['R3']['apex_61812']
    hub_root = min((row for row in layers['rows'] if row['part'] == 'wheel_link' and row['where'].startswith('apex')),
                   key=lambda x: x['layer_sf'] / x['target'])
    ring = min((row for row in layers['rows'] if row['part'] == 'front_link'), key=lambda x: x['layer_sf'] / x['target'])
    # a 6061 hub in place of the printed one: the Ø60 journal from the hub's end (y -6) to the outer 61812's face (y 45)
    # and the Ø64 shoulder from there to the link's inner face (y 54), both round the Ø48 bore (cad/fivebar.py Stack)
    jr = repo.num('cad/fivebar.py', r"\.union\(ycyl\(([\d.]+), h0, ab1 \+ 0\.01, l2\)\)")
    sr = repo.num('cad/fivebar.py', r"k = k\.union\(ycyl\(([\d.]+), ab1, h1 \+ 0\.01, l2\)\)")
    br = repo.num('cad/fivebar.py', r"k = k\.cut\(ycyl\(([\d.]+), h0 - 1, h1 - 0\.01, l2\)\)")
    hub_mm3 = annulus(2 * jr, 2 * br) * (45.0 + 6.0) + annulus(2 * sr, 2 * br) * (54.0 - 45.0)
    apex_hub_g = hub_mm3 / 1000 * (2.70 - mat['density'])
    out.append(joint_entry(
        'leg.apex', 2, 'the wheel\'s load and out-of-plane moment between the two lower links',
        today='two 61812 in the front link\'s printed ring (6 mm wall) on the wheel link\'s printed Ø60 hub; DIN 471-60 '
              'circlip in a printed groove; a printed spacer',
        high=[f"the wheel link's hub root: layer check {hub_root['case']} {hub_root['layer_sf']} against {hub_root['target']}",
              f"the front link's apex ring: {ring['case']} {ring['layer_sf']} against {ring['target']}",
              f"bearings fine (s0 {ax['sf']:g} in R3)"],
        options={
            'printed, bigger': 'a root fillet at the Ø64 shoulder; the ring wall 6 -> 10-12 mm: lowest mass, may not reach 1.2',
            'metal bushing': 'a turned 6061 hub (journal, shoulder, circlip groove) clamped through the foot by the wheel\'s '
                             '4 x M6 (their heads then bear on metal, which also fixes the foot\'s crushed-plastic clamp); '
                             f'about +{apex_hub_g:.0f} g a leg (the Ø60 / Ø48 journal and the Ø64 shoulder in 6061 instead of '
                             'PA6-CF, from cad/fivebar.py\'s hub)',
            'split apex collar': 'the front link\'s inner half-eye as a separate printed collar, through-bolted to the link: '
                                 'the link then prints flat, and the bolts precompress the ring\'s layers',
        },
        pick='owner decision (mass)',
        why='The hub root needs its peel stress x0.6 and the ring x0.4. Metal is certain and costs mass; printed is light and '
            'needs the FEA to show it.',
        pr2='both swept on the compute host; the lighter one that passes is drawn',
        mass_g_per_leg=None))

    # 7. wheel foot
    wf = J['leg.wheel_botwheel']
    out.append(joint_entry(
        'leg.wheel_botwheel', wf['qty_robot'], 'the wheel on the leg',
        today=f"4 x M6 x 30 from inside the hub, heads on {wf['clamp']['printed_mm']:g} mm of PA6-CF; {wf['torque_nm']:g} N m "
              f"puts {wf['clamp']['bearing_mpa']:g} MPa under each head",
        high=[f"needs >= {max(l['per_insert_n'] for l in wf['loads']):.0f} N a screw; a bare head holds "
              f"{wf['clamp']['preload_at_sustained_n']:.0f} N at {mat['washer_mpa']:g} MPa"],
        options={'washer': 'a DIN 433 washer (fits inside the Ø48 bore): 1521 N, 1.14 x the need',
                 'metal bushing': 'the turned apex hub\'s floor under the heads (option 6): the clamp in metal'},
        pick='washer now; metal with the apex hub if chosen',
        why='The BotWheel foot is the rig\'s; D69\'s 10 in hub motor replaces it (W1, W2).',
        pr2='DIN 433 M6 washers under the heads; torque from the washer\'s plastic screen', mass_g_per_leg=4 * 0.7))

    # 8. stop posts
    out.append(joint_entry(
        'leg.stop_posts', 8, 'the knee-out / knee-in stops',
        today='Ø16 x 40 52100 pins 23 mm into blind Ø16.1 holes, retaining compound; TPU 95A sleeves',
        high=['the retaining compound: Henkel does not normally recommend LOCTITE 638 on plastics (stress cracking of '
              'thermoplastics), and the printed hole may close the gap it needs (fits)'],
        options={'insert': 'no (D53 replaced the M8 insert)', 'metal bushing': 'the pin is one'},
        pick='keep', why='Pins in blind holes carry the stop\'s bending into 23 mm of plastic',
        pr2='a 0.5 x 45 deg lead-in at the bed-face mouth; a structural epoxy in place of the anaerobic compound, its gap '
            'set from C1 (C1 also tries the compound with activator on a printed bore)',
        mass_g_per_leg=0))
    return out, J


def joint_entry(jid, qty, role, today, high, options, pick, why, pr2, mass_g_per_leg):
    return {'id': jid, 'qty_robot': qty, 'role': role, 'today': today, 'high_stress': bool(high), 'reasons': high,
            'options': options, 'pick': pick, 'why': why, 'pr2': pr2,
            'mass_g_per_leg': None if mass_g_per_leg is None else r(mass_g_per_leg, 0)}


# ---------------------------------------------------------------------------------------------------- five-bar play

def fivebar(repo):
    D = repo.num('cad/fivebar.py', r"'D': ([\d.]+), 'l1'")
    l1 = repo.num('cad/fivebar.py', r"'D': [\d.]+, 'l1': ([\d.]+), 'l2'")
    l2 = repo.num('cad/fivebar.py', r"'D': [\d.]+, 'l1': [\d.]+, 'l2': ([\d.]+),")
    repo.has('cad/fivebar.py', 'E = E1 if E1[1] < E2[1] else E2')
    return D, l1, l2


def meet(C, Dp, la, lb):
    """The lower of the two points la from C and lb from Dp (the apex: fivebar.fk's branch)."""
    vx, vz = Dp[0] - C[0], Dp[1] - C[1]
    d = math.hypot(vx, vz)
    a = (la * la - lb * lb + d * d) / (2 * d)
    h = math.sqrt(max(0.0, la * la - a * a))
    mx, mz = C[0] + a * vx / d, C[1] + a * vz / d
    p1 = (mx - h * vz / d, mz + h * vx / d)
    p2 = (mx + h * vz / d, mz - h * vx / d)
    return p1 if p1[1] < p2[1] else p2


def ik(x, z, D, l1, l2):
    out = []
    for (px, side) in ((D / 2, 1), (-D / 2, -1)):
        vx, vz = x - px, z
        d = math.hypot(vx, vz)
        a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        h = math.sqrt(max(0.0, l1 * l1 - a * a))
        mx, mz = px + a * vx / d, a * vz / d
        c1, c2 = (mx - h * vz / d, mz + h * vx / d), (mx + h * vz / d, mz - h * vx / d)
        C = c1 if (c1[0] - c2[0]) * side > 0 else c2
        out.append(math.atan2(C[1], C[0] - px))
    return out


def play_sensitivity(repo):
    """How far the wheel's axle moves for 0.1 mm of radial play at each joint and 0.1 deg at each motor, with the
    motors held, at the leg lengths the pictures use (cad/build_leg.py: crouch 130, stand 300, tall 380)."""
    D, l1, l2 = fivebar(repo)
    poses = {}
    for h in (130.0, 300.0, 380.0):
        p1, p2 = ik(0.0, -h, D, l1, l2)
        A, B = (D / 2, 0.0), (-D / 2, 0.0)

        def foot(p1_, p2_, dc=(0, 0), dd=(0, 0), la=l2, lb=l2):
            C = (A[0] + l1 * math.cos(p1_) + dc[0], l1 * math.sin(p1_) + dc[1])
            Dq = (B[0] + l1 * math.cos(p2_) + dd[0], l1 * math.sin(p2_) + dd[1])
            return meet(C, Dq, la, lb)

        E = foot(p1, p2)
        dirs = [(math.cos(t), math.sin(t)) for t in [k * math.pi / 8 for k in range(16)]]
        e = 0.1
        knee_f = max(math.dist(foot(p1, p2, dc=(e * u[0], e * u[1])), E) for u in dirs)
        knee_r = max(math.dist(foot(p1, p2, dd=(e * u[0], e * u[1])), E) for u in dirs)
        # the apex: the wheel link (from the rear knee) may sit e from where the front link's end puts it
        apex = max(math.dist(foot(p1, p2, la=l2 + s * e), E) for s in (-1, 1))
        dphi = math.radians(0.1)
        mot = max(math.dist(foot(p1 + dphi, p2), E), math.dist(foot(p1, p2 + dphi), E))
        poses[str(int(h))] = {'phi_deg': [r(math.degrees(p1), 1), r(math.degrees(p2), 1)], 'axle': [r(E[0], 1), r(E[1], 1)],
                              'per_0.1mm_front_knee': r(knee_f, 3), 'per_0.1mm_rear_knee': r(knee_r, 3),
                              'per_0.1mm_apex': r(apex, 3), 'per_0.1deg_motor': r(mot, 3)}
    plays = {
        'knee pin in the DIN 179 sleeves (F7 / f9)': [0.032 / 2, 0.093 / 2],
        'knee pin in the 6301 bore (0/-0.008 / f9)': [0.008 / 2, 0.059 / 2],
        '6301 radial clearance (group N, 10-18 mm bore)': [0.003 / 2, 0.018 / 2],
        'apex 61812 inner races on the printed Ø60 journal (B0 hub_stub sets it)': [0.0, 0.10],
    }
    return {'basis': f"{SOURCES['iso286']}; {SOURCES['din179']}; {SOURCES['iso7379']}; {SOURCES['iso5753']}; radial play = "
                     "half the diametral clearance; the motors' backlash is measured on the rig (B1)",
            'poses_mm': poses, 'radial_play_mm': plays}


# ---------------------------------------------------------------------------------------------------- impact

def impact(repo):
    rig = repo.json('exports/leg/rig-results.json')['scenarios']
    S = repo.json('exports/leg/fea/summary.json')['joints']
    rows = []
    for n in ('drop_150', 'jump_peak', 'power_off', 'power_off_damped'):
        s = rig[n]
        rows.append({'scenario': n, 'axle_n': s['peak_axle_force_n'], 'knee_pin_n': s['peak_knee_pin_n'],
                     'stop_nm': s['peak_stop_nm'], 'gearbox_nm': s['peak_gearbox_nm']})
    k3 = S['R3']['knee_rear']
    return {'scenarios': rows,
            'undamped_over_damped_knee': r(rig['power_off']['peak_knee_pin_n'] / rig['power_off_damped']['peak_knee_pin_n'], 1),
            'r3_knee': {'bearing_s0': k3['bearing']['sf'], 'pin_sf': k3['pin']['sf'], 'eye_sf': k3['eye_pressure']['sf']},
            'note': 'every R3 margin is the undamped cut onto the stops; the RS-04\'s power-off damping as the rig assumes it '
                    '(20 % of shorted phases, not measured: B1 measures it) divides the knee load by the ratio above; no rig '
                    'scenario models the bumper'}


# ---------------------------------------------------------------------------------------------------- coupons

COUPONS = [
    {'id': 'C1', 'name': 'bore and press-fit gauge', 'prints': 'one block a variant (-0.1 / 0 / +0.1 mm), PA6-CF, the leg recipe, '
     'bores vertical as in the parts, half the mouths chamfered 0.5 x 45 deg on the bed face',
     'features': 'a 6301 seat (12 mm deep, Ø31 shoulder), a DIN 179 sleeve bore 40 mm long, a Ø16.1 x 23 blind stop-pin hole, '
                 'two Ø4.94 x 12 dowel holes, a 61812 seat segment (10 mm)',
     'settles': 'PRINT_HOLE_ERR for this printer (the hole each fit is drawn at), the press force and the grip dry and after a '
                'humid week, elephant\'s foot at the mouths, the epoxy bond in printed bores',
     'sheet': 'c1-bores.csv',
     'columns': ['variant', 'feature', 'mouth', 'd_mouth_0deg_mm', 'd_mouth_90deg_mm', 'd_mid_0deg_mm', 'd_mid_90deg_mm',
                 'press_force_n', 'pushout_dry_n', 'pushout_humid_7d_n', 'mass_dry_g', 'mass_humid_7d_g', 'notes'],
     'rows': [[v, f, m] for v in ('m01', 'nom', 'p01') for f in ('6301_seat', 'sleeve_bore', 'stop_pin_hole', 'dowel_hole_a',
                                                                 'dowel_hole_b', '61812_seat') for m in ('plain', 'chamfer')]},
    {'id': 'C2', 'name': 'insert pull-out and spin-out in the real wall (B4a)', 'prints': 'three flange-end slices of the hip frame '
     '(13 mm flange, Ø14 boss, the real 2.94 mm walls), printed as the frame (insert axis vertical)',
     'features': 'the M5 insert at the frame\'s depth; a Ø15 bearing washer under the puller',
     'settles': 'the insert\'s pull-out across the layers in this wall (the 1500 N estimate) and its spin-out torque: the numbers '
                'the insert option is judged on, kept even if the mount goes to through-bolts (other leg and body inserts)',
     'sheet': 'c2-insert.csv',
     'columns': ['sample', 'torque_nm', 'tension_n', 'spinout_nm', 'pullout_n', 'failure_mode', 'notes'],
     'rows': [[s] for s in ('s1', 's2', 's3')]},
    {'id': 'C3', 'name': 'sleeved through-bolt joint, against the plastic clamp', 'prints': 'four 13 x 40 x 60 flange blocks, layers '
     'across the bolt as in the frame (coupon_c3_sleeved, coupon_c3_plain), and two 30 x 30 wheel-foot blocks, the 20.8 mm '
     'the BotWheel\'s M6 clamps (coupon_c3_wheel)',
     'features': 'two with an Ø8.1 bore and a steel sleeve flush, its nut on a DIN 9021 (Ø15) washer that reaches the '
                 'plastic round the sleeve; two with an Ø5.5 bore (bolt on the plastic, a Ø15 washer); M5 8.8 through the B4 '
                 'load cell; after the creep readings, load each sleeved joint in tension to the fault tension (851 N) '
                 'through the load cell, the block held at its far face, and check that the washer carries it into the '
                 'plastic round its pocket: the joint stays closed and the pocket does not crush. The wheel blocks: M6 x 30 '
                 'on a DIN 433 at 1.8 N m with threadlocker into a 5 mm steel plate (the BotWheel\'s flange), through the '
                 'load cell: the clamp left after creep against the 1331 N the wheel\'s flange needs',
     'settles': 'preload kept over 30 min, 24 h, 7 days and a humid week, sleeved against plain; the creep step the preload '
                'table screens; the re-torque schedule. A block clamps 13 mm of plastic, the frame\'s through-bolt about 77 mm: '
                'report the creep as mm per mm of clamped plastic and scale it to the frame (the washer\'s pocket and the '
                'frame\'s 2.45 mm walls are not in the block: B4 checks those on the frame)',
     'sheet': 'c3-through-bolt.csv',
     'columns': ['sample', 'kind', 'clamped_length_mm', 'torque_nm', 'preload_0_n', 'preload_30min_n', 'preload_24h_n', 'preload_7d_n',
                 'preload_humid_7d_n', 'retorque_nm', 'notes'],
     'rows': [[s, k] for s, k in (('a', 'sleeved'), ('b', 'sleeved'), ('c', 'plastic'), ('d', 'plastic'), ('e', 'wheel'),
                                  ('f', 'wheel'))]},
    {'id': 'C4', 'name': 'boss-root layer coupon (the knee eye\'s stub)', 'prints': 'the upper link\'s knee end, cut 90 mm back from the '
     'knee, printed as the link (stub up): coupon_c4_today (dev\'s stub) and coupon_c4_pr2 (the drawn one), two each',
     'features': 'conditioned humid before the test, as the prediction assumes (c4_fea.py uses the humid PA6-CF rows): '
                 'weighed dry, then held over water (or at 70 C / 62 % RH, ISO 1110) until the mass stops rising, and weighed '
                 'again; a dry coupon reads about 2 x the prediction and must not be compared with it. The two DIN 179 sleeves '
                 'bonded in and the Ø12 knee pin through them; the arm\'s last 20 mm clamped square in the press cage; the load '
                 'on the pin at the knee boss\'s mid-plane (26 mm past the link\'s outer face), in the direction c4_fea.py '
                 'finds weakest',
     'settles': 'the load at which the stub\'s root peels (or the arm breaks) against c4_fea.py\'s prediction for the same '
                'coupon (docs/leg-print-package.md section 8): measured over predicted is the factor on the S_z and S_s the layer check assumes',
     'sheet': 'c4-boss-root.csv',
     'columns': ['sample', 'stub', 'mass_dry_g', 'mass_conditioned_g', 'conditioning', 'load_at_first_whitening_n',
                 'load_at_failure_n', 'failure_plane', 'pin_deflection_at_1kn_mm', 'notes'],
     'rows': [[s, g] for s, g in (('a', 'today'), ('b', 'today'), ('c', 'pr2'), ('d', 'pr2'))]},
]


def coupon_sheets():
    out = {}
    for c in COUPONS:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow(c['columns'])
        for row in c['rows']:
            w.writerow(row + [''] * (len(c['columns']) - len(row)))
        out[c['sheet']] = buf.getvalue()
    return out


# ---------------------------------------------------------------------------------------------------- the document

def document(repo):
    mat = materials(repo)
    layers = layer_rows(repo, mat)
    jrows, J = joints(repo, mat, layers)
    doc = {
        'schema': 1,
        'generator': 'research/leg-preprint/screen.py',
        'status': 'screen: nothing here has been printed or tested; the coupons and the proof loads decide',
        'materials': {k: (r(v, 2) if isinstance(v, float) else v) for k, v in mat.items()},
        'parts': print_parts(repo, mat),
        'layers': layers,
        'orientation': orientation(repo),
        'joints': jrows,
        'fits': fits(repo, mat),
        'preload': preload_table(repo, mat, J),
        'play': play_sensitivity(repo),
        'impact': impact(repo),
        'coupons': [{k: v for k, v in c.items() if k not in ('rows', 'columns')} for c in COUPONS],
        'sources': SOURCES,
        'bindings': repo.bindings,
    }
    return doc


def md_table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join('' if c is None else str(c) for c in row) + ' |' for row in rows]
    return '\n'.join(out)


def markdown(doc):
    L = ['# Leg pre-print screen', '',
         'Generated by `research/leg-preprint/screen.py` (do not edit; run the generator). A screen with its assumptions '
         'stated, not a qualification: nothing here has been printed or tested. [README.md](README.md) reads it.', '']
    p = doc['parts']
    L += ['## Printed parts', '',
          f"Bed {p['bed_mm'][0]} x {p['bed_mm'][1]} x {p['bed_mm'][2]} mm; one leg {p['total_hours']} h, {p['total_grams']} g "
          '(exports/leg/print-plan.json). Overhang: faces pointing down more than 45 deg off vertical, above the bed.', '',
          md_table(['Part', 'Qty', 'Size (mm)', 'On the bed', 'h each', 'g each', 'Bed contact cm2', 'Overhang cm2', 'Flags'],
                   [[f"`{x['part']}`", x['qty'], ' x '.join(map(str, x['size_mm'])), f"{x['orientation']} ({x['placement']})",
                     x['hours_each'], x['grams_each'], x['stl'] and x['stl']['bed_cm2'], x['stl'] and x['stl']['overhang_cm2'],
                     '; '.join(f"**{f['code']}**: {f['text']}" for f in x['flags']) or '-'] for x in p['parts']]), '']
    ly = doc['layers']
    L += ['## Layer check (the record)', '',
          f"cad-agent {ly['toolkit']} `Study.layer_check()` on the record's solves ({ly['mesh_mm']} mm mesh, source "
          f"{ly['source_revision'][:7]}), each part's layers stacked along its y. S_s = S_z / sqrt(3) "
          f"({doc['materials']['S_s']} MPa), and at S_z / 2. A row below its target needs its peak stress cut by the "
          '"x" factor; a bending-loaded root needs its radius times the cube root of it; "S_s needed" is the interlayer '
          'shear strength that would pass the row unchanged.', '',
          md_table(['Part', 'Case', 'Target', 'Gate SF', 'Layer SF', 'at S_z/2', 'sigma_n / tau MPa', 'Where', 'x', 'S_s needed'],
                   [[f"`{x['part']}`", x['case'], x['target'], x['gate_sf'], f"**{x['layer_sf']}**" if not x['ok'] else x['layer_sf'],
                     x['layer_sf_at_half_sz'], f"{x['sigma_n_mpa']} / {x['tau_mpa']}", x['where'],
                     x['stress_reduction_needed'] or '-', x['S_s_needed_mpa'] or '-'] for x in ly['rows']]), '']
    o = doc['orientation']
    if o:
        L += ['## Print orientation (layer check on three layer planes)', '',
              f"`orientation_screen.py` on the compute host (cad-agent {o['toolkit']['version']}, {o['mesh_mm']} mm mesh, source "
              f"{o['source_revision'][:7]}): the same solves, the layers on the y (today), z (on edge) and x (on end) planes.", '',
              md_table(['Part', 'Case', 'Target', 'y (today)', 'z (on edge)', 'x (on end)', 'Best'],
                       [[f"`{x['part']}`", x['case'], x['target'], x['y'], x['z'], x['x'],
                         f"{x['best']}{'' if x['best_ok'] else ' (short)'}"] for x in o['rows']]), '']
    L += ['## Joints', '', 'D74: a joint is high-stress when any reason below holds; it then gets a metal sleeve or bushing '
          'through the plastic, clamped by a through-bolt or rod and a nut, preloaded so the layers stay in compression. '
          'Heat-set inserts stay where the loads allow.', '']
    for j in doc['joints']:
        L += [f"### `{j['id']}` ({j['qty_robot']} on the robot): {j['role']}", '', f"Today: {j['today']}.", '']
        if j['reasons']:
            L += ['High-stress because:', ''] + [f'- {x}' for x in j['reasons']] + ['']
        L += [md_table(['Option', 'Screen'], [[k, v] for k, v in j['options'].items()]), '',
              f"**Pick: {j['pick']}.** {j['why']}", '', f"PR 2: {j['pr2']}." + (
                  f" Mass {j['mass_g_per_leg']:+.0f} g a leg." if j['mass_g_per_leg'] is not None else ''), '']
    f = doc['fits']
    L += ['## Press and slide fits in printed holes', '', f['basis'] + '.', '',
          md_table(['Fit', 'Part', 'Hole drawn', 'Mating', 'Interference drawn', 'As printed', 'Dry: p / hoop MPa, press N',
                    'Humid p', 'Mouth on the bed', 'Verdict'],
                   [[x['fit'], x['part'], x['hole_drawn_mm'], ' - '.join(map(str, x['mating_mm'])),
                     ' to '.join(map(str, x['interference_drawn_mm'])), ' to '.join(map(str, x['interference_printed_mm'])),
                     f"{x['at_max_dry']['p_mpa']} / {x['at_max_dry']['hoop_mpa']}, {x['at_max_dry']['press_n']:g}",
                     x['at_max_humid']['p_mpa'], 'yes: chamfer' if x['mouth_on_bed'] else 'no', x['verdict']] for x in f['rows']]), '']
    pr = doc['preload']
    L += ['## Clamped plastic and preload', '', pr['basis'] + '.', '',
          md_table(['Joint', 'Clamp', 'Preload N', 'MPa', 'Squeeze mm', 'Lost at 0.05 mm', 'Lost at 0.2 mm'],
                   [[x['joint'], x['clamp'], x['preload_n'], x['stress_mpa'], x['squeeze_mm'],
                     x['lost_n']['0.05'], x['lost_n']['0.2']] for x in pr['rows']]), '']
    pl = doc['play']
    L += ['## Five-bar play', '', pl['basis'] + '.', '',
          md_table(['Leg (mm)', 'Motors (deg)', 'per 0.1 mm front knee', 'rear knee', 'apex', 'per 0.1 deg motor'],
                   [[h, ', '.join(map(str, v['phi_deg'])), v['per_0.1mm_front_knee'], v['per_0.1mm_rear_knee'],
                     v['per_0.1mm_apex'], v['per_0.1deg_motor']] for h, v in pl['poses_mm'].items()]), '',
          md_table(['Play source', 'Radial mm'], [[k, f'{v[0]:.3f}-{v[1]:.3f}'] for k, v in pl['radial_play_mm'].items()]), '']
    im = doc['impact']
    L += ['## Falls and the stops', '', im['note'] + f" (x{im['undamped_over_damped_knee']}).", '',
          md_table(['Scenario', 'Axle N', 'Knee pin N', 'Stop N m', 'Gearbox N m'],
                   [[x['scenario'], x['axle_n'], x['knee_pin_n'], x['stop_nm'], x['gearbox_nm']] for x in im['scenarios']]), '']
    L += ['## Print-first coupons', '',
          md_table(['Id', 'Coupon', 'Prints', 'Features', 'Settles', 'Sheet'],
                   [[c['id'], c['name'], c['prints'], c['features'], c['settles'], f"[sheets/{c['sheet']}](sheets/{c['sheet']})"]
                    for c in doc['coupons']]), '']
    L += ['## Sources', ''] + [f'- {k}: {v}' for k, v in doc['sources'].items()] + ['']
    return '\n'.join(L)


PACKAGE_DOC = 'docs/leg-print-package.md'
FINAL_LAYER = 'research/leg-preprint/evidence/leg-layer-check-print-ready.json'
FINAL_GATE = 'exports/leg/fea/summary.json'
BLOCK = ('<!-- gen:final-record -->', '<!-- /gen:final-record -->')


C4_EVIDENCE = 'research/leg-preprint/evidence/c4-fea.json'
HIP_MESH = 'research/leg-preprint/evidence/hip-frame-print-ready.json'
ROBOT_KG = 38.69      # the robot with this branch (docs/leg-print-package.md section 9: the ledger's 38.56 + 2 x 64 g)


def c4_prediction(repo):
    """Each C4 stub's predicted peel load: the weakest direction at the 2 mm mesh, and the same at 1.5 mm."""
    ev = repo.json(C4_EVIDENCE)
    out = {}
    for stub in ('today', 'pr2'):
        rows = [x for x in ev['rows'] if x['stub'] == stub]
        coarse = min((x for x in rows if x['mesh_mm'] == 2.0), key=lambda x: x['predicted_peel_n'])
        fine = next(x for x in rows if x['mesh_mm'] == 1.5 and x['direction'] == coarse['direction'])
        out[stub] = {'direction': coarse['direction'], 'peel_n': coarse['predicted_peel_n'], 'peel_n_fine': fine['predicted_peel_n'],
                     'bulk_n': coarse['predicted_bulk_n'], 'governed_by': coarse['layer_check_at_1kn']['governed_by']}
    return out


def final_record(repo, mat):
    """The leg record before (the v0.6.0 layer-check evidence of dev's leg) and after the print-ready changes (the
    rerun record and its layer check), each printed part's case against its target, and what settles each short row."""
    before = {(x['part'], x['case']): x for x in repo.json(LAYER_EVIDENCE)['rows']}
    ev = repo.json(FINAL_LAYER)
    gate = {(x['part'], x['case']): x for x in repo.json(FINAL_GATE)['results']}
    rows = []
    for x in ev['rows']:
        k = (x['part'], x['case'])
        lc, b = x['layer_check'], before.get(k)
        tgt, sf = x['target'], lc['safety_factor']
        w = lc['worst']
        sn, tau = max(w['sigma_n_mpa'], 0.0), abs(w['tau_n_mpa'])
        lim = 1.0 / tgt
        need = None
        if sf < tgt:
            # Shear-limited: the S_s that passes at the assumed S_z. Tension-limited (σn alone fails at the assumed S_z):
            # the S_z that passes with S_s scaled with it (S_z / sqrt(3)), which is S_z x target / SF.
            need = ({'S_s': r(tau / math.sqrt(lim ** 2 - (sn / mat['S_z']) ** 2), 1)} if sn / mat['S_z'] < lim
                    else {'S_z': r(mat['S_z'] * tgt / sf, 1)})
        g = gate[k]['safety_factor']
        masked = {name: gate[k][m] for m, name in (('safety_factor_with_pad_rim', 'pad rim'),
                                                   ('safety_factor_with_pin_band', 'pin band')) if m in gate[k]}
        rows.append({'part': x['part'], 'case': x['case'], 'target': tgt, 'left_out': masked,
                     'gate_before': b['gate_sf'] if b else None, 'gate_now': g,
                     'layer_before': b['layer_check']['safety_factor'] if b else None, 'layer_now': sf,
                     'S_s_needed_mpa': need, 'where': where(x['part'], w['corner_mm'], repo)})
    design_kg = repo.num('cad/leg_studies.py', r'^ROBOT_KG = ([\d.]+)')
    for x in rows:
        x['gate_at_robot_mass'] = r(x['gate_now'] * design_kg / ROBOT_KG, 2)
    hf = repo.json(HIP_MESH)['meshes']
    mesh_check = [{'case': c['case'], 'sf_4': c['safety_factor'],
                   'sf_3': next(d['safety_factor'] for d in hf['3.0']['cases'] if d['case'] == c['case']),
                   'target': c['target']} for c in hf['4.0']['cases']]
    return {'design_kg': design_kg, 'robot_kg': ROBOT_KG, 'c4': c4_prediction(repo), 'hip_mesh': mesh_check,
            'S_z_assumed_mpa': r(mat['S_z'], 2), 'source_revision': ev['source_revision'], 'toolkit': ev['toolkit_version'], 'mesh_mm': ev['mesh_mm'],
            'S_s_assumed_mpa': r(mat['S_s'], 2), 'rows': rows}


def mat_sz(fr):
    return fr['S_z_assumed_mpa']


def final_block(fr):
    n = len(fr['rows'])
    gb = sum(1 for x in fr['rows'] if x['gate_before'] is not None and x['gate_before'] >= x['target'])
    gn = sum(1 for x in fr['rows'] if x['gate_now'] >= x['target'])
    lb = sum(1 for x in fr['rows'] if x['layer_before'] is not None and x['layer_before'] >= x['target'])
    ln = sum(1 for x in fr['rows'] if x['layer_now'] >= x['target'])
    at_mass = [x for x in fr['rows'] if x['gate_now'] >= x['target'] > x['gate_at_robot_mass']]
    c4 = fr['c4']
    out = [BLOCK[0], '',
           f"Generated by `research/leg-preprint/screen.py` from `{FINAL_GATE}` and `{FINAL_LAYER}` (cad-agent "
           f"{fr['toolkit']}, {fr['mesh_mm']:g} mm mesh, source {fr['source_revision'][:7]}), against dev's record "
           f"(`{LAYER_EVIDENCE}`). The printed parts' rows are below.", '',
           f"- **Isotropic gate:** {gn} of {n} rows at target, against {gb} before.",
           f"- **Layer check:** {ln} of {n} rows at target, against {lb} before. It assumes the interlayer shear strength S_s = S_z / sqrt(3) = "
           f"{fr['S_s_assumed_mpa']:g} MPa; nobody has measured it.",
           f"- **Mass basis:** the loads are the {fr['design_kg']:g} kg design robot's (`cad/leg_studies.py` ROBOT_KG). At the "
           f"{fr['robot_kg']:g} kg this branch weighs (section 9) every SF falls by {fr['design_kg'] / fr['robot_kg']:.3f}: "
           + (' and '.join(f"{x['part']} {x['case']} {x['gate_now']:g} → **{x['gate_at_robot_mass']:g}** (target {x['target']:g})"
                           for x in at_mass)
              + (' would then miss their targets. They are counted at target above, but they sit at the limit.' if len(at_mass) > 1
                 else ' would then miss its target. It is counted at target above, but it sits at the limit.') if at_mass
              else 'no row that is at target drops under it.'),
           f"- **Mesh check (the hip frame, `{HIP_MESH}`):** the gate at 4 mm and at 3 mm: "
           + ', '.join(f"{c['case']} {c['sf_4']:g} → " + (f"**{c['sf_3']:g}**" if c['sf_3'] < c['target'] else f"{c['sf_3']:g}")
                       for c in fr['hip_mesh'])
           + '. The gate is not converged, so read every frame row as a screen; bold rows miss their target at 3 mm.', '',
           '| Part | Case | Target | Gate: before → now | Layer check: before → now | Printed strength that would pass (MPa) | Worst corner |',
           '|---|---|---|---|---|---|---|']
    for x in fr['rows']:
        mark = lambda v: f"**{v:g}**" if v is not None and v < x['target'] else ('-' if v is None else f'{v:g}')
        nd = x['S_s_needed_mpa']
        need = '' if nd is None else (
            f"S_s ≥ {nd['S_s']:g} ({nd['S_s'] / fr['S_s_assumed_mpa']:.1f}× assumed)" if 'S_s' in nd
            else f"S_z ≥ {nd['S_z']:g} ({nd['S_z'] / fr['S_z_assumed_mpa']:.1f}× assumed; tension)")
        out.append(f"| {x['part']} | {x['case']} | {x['target']:g} | {mark(x['gate_before'])} → {mark(x['gate_now'])} | "
                   f"{mark(x['layer_before'])} → {mark(x['layer_now'])} | {need} | {x['where']} |")
    left = [x for x in fr['rows'] if any(v < x['target'] for v in x['left_out'].values())]
    out += ['', f"Bold: under target. The strength column is what coupon C4 has to show for the row to pass as drawn: an "
            f"interlayer shear strength S_s (with S_z at the assumed {mat_sz(fr):g} MPa), or, where through-layer tension "
            f"alone fails, a through-layer strength S_z (with S_s scaled with it). A row whose number C4 does not reach needs "
            f"geometry or metal (section 10); a row that needs more than about twice the assumed value is unlikely to pass, so "
            f"read those as the parts most likely to need it. Each number holds at the row's worst corner only, so it is a "
            f"lower bound.", '',
            '**Left out of the gate, as the records do.** Two contact edges the linear model cannot resolve are not judged: '
            'the upper link\'s bonded pad rim (the adapter\'s edge on the hub face) and the hip frame\'s band round a stop pin '
            '(the pin bearing on its hole). Counted, they would read:', '',
            '| Part | Case | Target | Gate as judged | With the left-out edge |', '|---|---|---|---|---|']
    for x in left:
        out.append(f"| {x['part']} | {x['case']} | {x['target']:g} | {x['gate_now']:g} | "
                   + ', '.join(f"{k} **{v:g}**" if v < x['target'] else f'{k} {v:g}' for k, v in x['left_out'].items()) + ' |')
    out += ['', 'The plots in the summary show these edges red. Bench test B4b (the hub on its adapter) and proof load P2 '
            '(the pins, section 7) are the physical checks.', '',
            f"**Coupon C4's prediction** (`{C4_EVIDENCE}`, `research/leg-preprint/c4_fea.py`: the coupon itself at 1 kN, "
            "held at its cut face 90 mm back, loaded through the knee bore at the knee boss's mid-plane):", '',
            '| Stub | Weakest direction | Predicted peel load (2 mm / 1.5 mm mesh) | Governed by | Bulk (in-layer) load |',
            '|---|---|---|---|---|']
    for stub, name in (('today', "dev's (coupon_c4_today)"), ('pr2', 'drawn (coupon_c4_pr2)')):
        c = c4[stub]
        out.append(f"| {name} | {c['direction']} | {c['peel_n']:,} N / {c['peel_n_fine']:,} N | {c['governed_by']} | {c['bulk_n']:,} N |")
    out += ['', 'The prediction uses the humid PA6-CF rows, so condition C4 humid first (its sheet says how): a dry coupon '
            'reads about twice the prediction. Load it in the weakest direction. The measured peel load over the predicted one '
            'is the factor on the assumed S_z and S_s for every row above; the two stubs check that the drawn one gains what '
            'the FEA says.', '', BLOCK[1]]
    return '\n'.join(out)


PROOF = ('<!-- gen:proof -->', '<!-- /gen:proof -->')


def proof_block(repo, fr):
    """The proof loads, and what the folded-posture rows (R3) predict at them: linear, so each SF scales by R3's axle
    load over the proof load."""
    cases = repo.json(FINAL_GATE)['cases']
    r3 = cases['R3']['Fw3'][2]
    p1, p2 = cases['E1']['Fw3'][2], cases['R1']['Fw3'][2]
    rows = [x for x in fr['rows'] if x['case'] in ('R3K', 'R3KF', 'R3o')]
    out = [PROOF[0], '',
           '| Step | Load at the axle | Hold | Pass |', '|---|---|---|---|',
           f"| P1 | {p1:.0f} N vertical (E1's axle load: 2.5 x standing) | 10 min | after the seating cycle, it returns to within "
           '0.05 mm of its start; no whitening, cracking or creaking |',
           f"| P2 | {p2:.0f} N vertical (R1's axle load, applied in the folded posture) | 1 min | set after unloading under 0.1 mm; "
           'the same visual checks; the torque marks have not moved |',
           '| P3 | 10 % of P2 sideways, at the tyre\'s mid-plane | 1 min | the same |', '',
           f"In the folded posture the axle load goes where R3's does, and P2 is {p2 / r3:.2f} of R3's {r3:.0f} N. Scaled from "
           'the R3 rows (generated by `screen.py` from the same record):', '',
           '| Part | Case | Gate at P2 | Layer check at P2 | Left-out edge at P2 |', '|---|---|---|---|---|']
    for x in rows:
        k = r3 / p2
        edge = ', '.join(f"{n} {v * k:.2f}" for n, v in x['left_out'].items()) or '-'
        out.append(f"| {x['part']} | {x['case']} | {x['gate_now'] * k:.2f} | {x['layer_now'] * k:.2f} | {edge} |")
    out += ['', 'So P2 brings the knee stubs and the stop pins\' bands near SF 1 in the folded posture: apply it in steps of '
            'a quarter, listening and watching the indicator, and stop at the first whitening.', '', PROOF[1]]
    return '\n'.join(out)


GLANCE = ('<!-- gen:glance -->', '<!-- /gen:glance -->')


def glance_block(fr):
    n, rows = len(fr['rows']), fr['rows']
    count = lambda k: sum(1 for x in rows if x[k] is not None and x[k] >= x['target'])
    better = lambda b, a: sum(1 for x in rows if x[b] is not None and x[a] > x[b])
    return '\n'.join([
        GLANCE[0], '',
        'The chart is `research/leg-preprint/figure.py`, drawn from the same rows as the table in section 8 '
        '(generated by `screen.py`).', '',
        '| | Isotropic gate | Layer check (S_s assumed) |', '|---|---|---|',
        f"| Rows at target, dev's record | {count('gate_before')} of {n} | {count('layer_before')} of {n} |",
        f"| Rows at target, this branch | {count('gate_now')} of {n} | {count('layer_now')} of {n} |",
        f"| Rows that went up | {better('gate_before', 'gate_now')} of {n} | {better('layer_before', 'layer_now')} of {n} |",
        '', 'Coupon C4 decides the layer rows (section 8). The mass is in section 9 and the open decisions in section 10.',
        '', GLANCE[1]])


def splice(text, marks, block):
    s, e = text.index(marks[0]), text.index(marks[1]) + len(marks[1])
    return text[:s] + block + text[e:]


def package_doc(repo, mat):
    """docs/leg-print-package.md with its generated blocks rewritten (the rest is written by hand)."""
    fr = final_record(repo, mat)
    text = splice(splice(repo.text(PACKAGE_DOC), BLOCK, final_block(fr)), GLANCE, glance_block(fr))
    return splice(text, PROOF, proof_block(repo, fr))


def outputs(repo):
    doc = document(repo)
    files = {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + '\n', OUT_MD: markdown(doc)}
    files[ROOT / PACKAGE_DOC] = package_doc(repo, materials(repo))
    for name, text in coupon_sheets().items():
        files[SHEETS / name] = text
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 if any output is stale')
    a = ap.parse_args(argv)
    files = outputs(Repo(ROOT))
    if a.check:
        stale = [str(p.relative_to(ROOT)) for p, t in files.items() if not p.exists() or p.read_text() != t]
        if stale:
            print('stale: ' + ', '.join(stale) + ' (run research/leg-preprint/screen.py)')
            return 1
        print('leg pre-print screen: current')
        return 0
    SHEETS.mkdir(exist_ok=True)
    for p, t in files.items():
        p.write_text(t)
        print(p.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
