"""Strength of the turret's printed parts (cadagent.fea) under slewing, a push on the barrel, and a fall.

    .venv/bin/python cad/turret_studies.py [--mesh 2.5] [--no-anim] [--only tilt_yoke pan_ring]

Every printed part that carries load is meshed from cad/turret.py's solid (in its build frame), held where its bolts
and seats hold it, loaded where its neighbours push, and solved with cadagent.fea (P2 tetrahedra, linear elastic).
Targets as for the leg (cad/leg_studies.py): SF 2 for everyday loads, 1.2 for rare ones.

Two safety factors for every printed part (plan N2, docs/turret-next-plan.md 1.3-1.4):
  - isotropic: the element von Mises against one allowable, humid printed PA6-CF (cadagent.fea MATERIALS: 49 MPa along
    the layers, 23 MPa across them, Bambu's dry data x0.6 for humidity and x0.8 for print defects) or PETG (20 MPa
    across its layers). `safety_factor` keeps v0's per-case choice of allowable (along or across, by how the part is
    printed and which way its peak was judged to run); `sf_isotropic_weak` charges every printed part's von Mises
    against the across-layer allowable, the reading that condemned v0's cradle.
  - layer-aware (`layer_aware`, the verdict's): a printed part is not isotropic. After each solve the stress tensor at
    every element corner is split by the part's layers, whose normal comes from its print rotation in cad/turret.py's
    MADE: the tension across the layers (against 23 MPa; compression across them does not open a layer), the
    interlaminar shear (against 11.5 MPa, half the across-layer strength: the studies' own rule) and the von Mises of the
    in-plane components (against 49 MPa). Each is a maximum-stress check with its peak, place and 99th percentile; the
    part's SF is the smallest of the three. PETG: 20 across, 10 shear, 29 along (its TDS's 51 along with the same
    knock-down as its 35 across). Why: the plain von Mises against 23 MPa condemns a part whose stress runs in its layers
    (the cradle's in-plane stresses were 28-40 MPa against 49), while von Mises against 49 misses a peak that crosses
    them (the cradle's real failure: the hub root in tension across its layers, the lug root in interlaminar shear).
    The same post-process applies to the leg's printed parts (cad/leg_studies.py), not done here.
The aluminium parts (the pan clamp, the cradle plates, the stop lug: SendCutSend 6061-T6) are isotropic: von Mises
against 276 MPa yield.

Loads (masses from cad/turret.py's mass_properties at run time, written to summary.json):
  E-cap    everyday: the pan servo at its firmware cap, 50 % of its 2.94 N m stall, through the 21:63 gears
  E-push   everyday: a hand pushes the muzzle up or down with 50 N; the cradle's lug meets the 0 or -25 deg stop
           (a push sideways back-drives the pan servo at its cap: E-cap)
  R-stall  rare: the pan servo at its full stall (the cap failed, or it is forced)
  R-fall   rare: 30 g on everything (the TM interface's design load, docs/cad-plan.md section 5): straight down, and
           sideways (the robot falling over), each part loaded by what it carries
Parts: the tilt yoke, the turntable and its teeth, the pinion, the pan base, the cradle's rail frame, the cartridge,
the dial, and the aluminium parts: the pan clamp, the cradle's two cheek plates and the stop lug (D48). Each result
also gives where its peak is and the 99th percentile of the element stresses (p99): a peak at a sharp re-entrant
corner of the model is softened in a print.
Writes exports/turret/fea/<part>-<case>.png (+ .mp4 overload video and .json for the interactive viewer, unless
--no-anim) and summary.json. Parts too small or simple for a mesh (the barrel tube, the flywheel hub at speed, the
journal's lip under the circlip, the fasteners, the board bay, the cradle's horn boss and pivot land) are checked by
hand in hand_checks() with their inputs.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import turret as tu  # noqa: E402
from cadagent.fea import MATERIALS, Study  # noqa: E402

OUT = R / 'exports' / 'turret' / 'fea'
TARGETS = {'sf': 2.0, 'sf_rare': 1.2}
G0 = 9.81
FALL_G = 30.0
SERVO_STALL = 2.94                 # N m, STS3215 at 12 V (Feetech datasheet)
CAP = 0.5                          # the firmware's torque cap on the pan servo
PUSH_N = 50.0                      # a hand on the muzzle
VIEWS = {'tilt_yoke': (20, -35), 'pan_ring': (35, -60), 'pan_pinion': (40, -60), 'pan_base': (30, -60), 'cradle': (25, -50),
         'cartridge_body': (30, -60), 'pan_clamp': (40, -60), 'dial': (40, -60), 'cradle_plate_l': (15, -80), 'cradle_plate_r': (15, -100),
         'stop_lug': (10, -95)}
# the layer-aware allowables (MPa), by printed material: along the layers, tension across them, interlaminar shear
LAYER_ALLOW = {'pa6-cf': {'along': MATERIALS['pa6_cf_xy'].strength_mpa, 'across': MATERIALS['pa6_cf_z'].strength_mpa,
                          'shear': 0.5 * MATERIALS['pa6_cf_z'].strength_mpa},
               'petg': {'along': 29.0, 'across': MATERIALS['petg'].strength_mpa, 'shear': 0.5 * MATERIALS['petg'].strength_mpa}}
PRINTED = {'pa6_cf_xy': 'pa6-cf', 'pa6_cf_z': 'pa6-cf', 'petg': 'petg'}       # FEA material -> printed material (others: metal)
# the cradle's group (D48): what the cradle carries is the cartridge; these turn with it but are the cradle's own
CRADLE_GROUP = ('cradle', 'cradle_plate_l', 'cradle_plate_r', 'stop_lug', 'horn_boss', 'pivot_spacer', 'laser_mount', 'laser',
                'tilt_bearing_inner', 'shoulder_screw')


def _rot(axis, deg):
    """The rotation matrix about `axis` by `deg` (right hand), as CadQuery's rotate() turns a part."""
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def layer_normal(part):
    """The layers' normal in the part's build frame (where these studies mesh it), from its print rotation in
    cad/turret.py MADE: the bed's z axis taken back through that rotation."""
    rot = next((m[5] for m in tu.MADE if m[0] == part), None)
    n = np.array([0.0, 0.0, 1.0])
    if rot:
        n = _rot(*rot).T @ n
    return n / np.linalg.norm(n)


def corner_stress(st):
    """The stress tensor at every element's four corners, (3, 3, elements, 4), as cadagent.fea's solve computes the von
    Mises it reports (the P2 strain is linear in a tet: its extremes are at the corners)."""
    from skfem import Basis, ElementTetP2, ElementVector
    from skfem.models.elasticity import lame_parameters
    lam, mu = lame_parameters(st.material.E_mpa, st.material.nu)
    Xv = np.array([[0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
    vb = Basis(st._m, ElementVector(ElementTetP2()), quadrature=(Xv, np.full(4, 1.0 / 24)))
    gd = vb.interpolate(st._u).grad
    eps = 0.5 * (gd + np.transpose(gd, (1, 0, 2, 3)))
    tr = eps[0, 0] + eps[1, 1] + eps[2, 2]
    sig = 2 * mu * eps
    for i in range(3):
        sig[i, i] += lam * tr
    return sig


def layer_aware(st, n, allow):
    """The layer-aware check of a solved study: each element corner's stress split by the layers (normal n) into the
    tension across them, the interlaminar shear and the in-plane von Mises, each against its allowable, over the
    elements that touch no clamp or load patch (as the isotropic design stress). Returns each component's peak, place,
    99th percentile and SF, and the part's SF (the smallest)."""
    sig = corner_stress(st)
    n = np.asarray(n, float) / np.linalg.norm(n)
    e1 = np.cross(n, [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    pr = lambda u, v: np.einsum('i,ijkl,j->kl', u, sig, v)
    snn, t1, t2, s11, s22, s12 = pr(n, n), pr(e1, n), pr(e2, n), pr(e1, e1), pr(e2, e2), pr(e1, e2)
    comps = {'in_plane': (np.sqrt(s11 ** 2 - s11 * s22 + s22 ** 2 + 3 * s12 ** 2), 'von Mises in the layers\' plane', allow['along']),
             'across': (np.maximum(snn, 0.0), 'tension across the layers', allow['across']),
             'shear': (np.sqrt(t1 ** 2 + t2 ** 2), 'interlaminar shear', allow['shear'])}
    free = ~st._touches_bc
    if not free.any():
        free = np.ones_like(free)
    cent = st.points[st.tets].mean(axis=1)
    out = {'layer_normal': [round(float(c), 3) for c in n], 'allowables_mpa': allow}
    for key, (val, what, a) in comps.items():
        ae = val.max(axis=1)
        k = int(np.argmax(np.where(free, ae, -1e9)))
        v = float(ae[k])
        out[key] = {'what': what, 'peak_mpa': round(v, 2), 'at_mm': [round(float(c), 1) for c in cent[k]], 'allowable_mpa': a,
                    'sf': round(a / v, 2) if v > 1e-9 else None, 'p99_mpa': round(float(np.percentile(ae[free], 99.0)), 2)}
    sfs = {k: out[k]['sf'] for k in comps if out[k]['sf'] is not None}
    out['governs'] = min(sfs, key=sfs.get) if sfs else None
    out['sf'] = sfs[out['governs']] if sfs else None
    return out
# what each study reads from the build (masses) is the turret as built now: cad/turret.py's mass_properties


def masses():
    """Group masses (kg) from the build summary (exports/turret/turret.json), with the 30 balls."""
    j = json.loads((R / 'exports/turret/turret.json').read_text())
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})
    rows, tot, com = tu.mass_properties(T, 0.0, with_balls=True)
    grp = {'tilt': 0.0, 'pan': 0.0, 'base': 0.0}
    for n, r in rows.items():
        fr = T.frame.get(n, 'pan' if n == 'not_modelled' else 'tilt')
        fr = 'base' if fr == 'pinion' else fr
        grp[fr] += r['mass_g'] * r['qty'] / 1000
    grp['tilt'] += 0.0
    cart = sum(rows[n]['mass_g'] * rows[n]['qty'] for n in rows if T.frame.get(n) == 'tilt' and n not in CRADLE_GROUP) / 1000
    cart += rows['balls_30']['mass_g'] / 1000
    zsum = {'tilt': [0.0, 0.0], 'pan': [0.0, 0.0]}
    for n, r in rows.items():
        fr = T.frame.get(n, 'pan' if n == 'not_modelled' else 'tilt')
        if fr in ('tilt', 'pan'):
            zsum[fr][0] += r['mass_g'] * r['qty']
            zsum[fr][1] += r['mass_g'] * r['qty'] * r['com_mm'][2]
    zsum['tilt'][0] += rows['balls_30']['mass_g']
    zsum['tilt'][1] += rows['balls_30']['mass_g'] * rows['balls_30']['com_mm'][2]
    z_pan = (zsum['tilt'][1] + zsum['pan'][1]) / (zsum['tilt'][0] + zsum['pan'][0])
    return {'tilt_kg': grp['tilt'], 'pan_kg': grp['pan'] + grp['tilt'], 'total_kg': tot / 1000, 'cartridge_kg': cart,
            'com_mm': com, 'pan_group_com_z_mm': z_pan, 'mass_g_with_balls': j.get('mass_g_with_balls'),
            'pan_ring_kg': rows['pan_ring']['mass_g'] / 1000}


def run(mesh, anim=True, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    G = tu.Geo()
    M = masses()
    results = []

    def study(part, case, shape, mat, setup, rare, why, mesh_mm=None, layers_of=None):
        """layers_of: the MADE part whose print rotation gives the layers (default: `part`)."""
        if only and part not in only:
            return None
        t0 = time.time()
        st = Study(shape, MATERIALS[mat], mesh_mm=mesh_mm or mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        if r['safety_factor'] is None or not np.isfinite(r['von_mises_design_mpa']):
            raise RuntimeError(f'{part} {case}: no finite stress (a degenerate element in the mesh? check the part for slivers)')
        png = OUT / f'{part}-{case}.png'
        disp = r['probe_displacement_mm'] and round(float(np.linalg.norm(r['probe_displacement_mm'])), 3)
        target = TARGETS['sf_rare' if rare else 'sf']
        free = ~st._touches_bc
        k = int(np.argmax(np.where(free, st.vm_elem, -1.0)))
        r['peak_at_mm'] = [round(float(c), 1) for c in st.points[st.tets[k]].mean(axis=0)]          # where the design stress is
        r['p99_mpa'] = round(float(np.percentile(st.vm_elem[free], 99.0)), 2) if free.any() else None
        pm = PRINTED.get(mat)
        if pm:                                       # a printed part: both columns, the verdict on the layer-aware one
            la = layer_aware(st, layer_normal(layers_of or part), LAYER_ALLOW[pm])
            weak = LAYER_ALLOW[pm]['across']
            r.update(layer_aware=la, sf_layer_aware=la['sf'], sf_isotropic_weak=round(weak / r['von_mises_design_mpa'], 2),
                     ok_isotropic=r['safety_factor'] >= target, verdict_sf=la['sf'], verdict_on='layer-aware')
        else:
            r.update(layer_aware=None, sf_layer_aware=None, sf_isotropic_weak=None, ok_isotropic=r['safety_factor'] >= target,
                     verdict_sf=r['safety_factor'], verdict_on='isotropic (metal: yield)')
        r.update(part=part, case=case, material_id=mat, load_from=why, png=str(png.relative_to(R)), target=target,
                 ok=r['verdict_sf'] >= target, seconds=round(time.time() - t0, 1))
        sf_txt = f"SF {r['safety_factor']}" + (f", layer-aware {r['sf_layer_aware']}" if pm else '')
        st.render(png, view=VIEWS.get(part, (25, -60)), title=f"{part} {case} ({MATERIALS[mat].name}): {sf_txt}, {disp} mm at the load")
        if anim:
            r['animation'] = str(st.animate(OUT / f'{part}-{case}.mp4', view=VIEWS.get(part, (25, -60)), title=f'{part} {case}: {MATERIALS[mat].name}').relative_to(R))
            r['viewer'] = str(st.export_viewer(OUT / f'{part}-{case}.json').relative_to(R))
        results.append(r)
        la_txt = ''
        if pm:
            la = r['layer_aware']
            la_txt = (f"  | layer-aware {la['sf']} ({la['governs']}: in-plane {la['in_plane']['peak_mpa']}, across {la['across']['peak_mpa']}, "
                      f"shear {la['shear']['peak_mpa']} MPa; weak-isotropic {r['sf_isotropic_weak']})")
        print(f"  {part:15} {case:12} {mat:9} SF {r['safety_factor']:6} (>= {target})  {r['von_mises_design_mpa']:7} MPa at {r['peak_at_mm']} "
              f"(p99 {r['p99_mpa']})  {disp} mm  ({r['mesh']['tets']} tets, {r['seconds']} s){la_txt}", flush=True)
        return r

    near = lambda v, w, t=0.6: abs(v - w) < t
    cyl = lambda f, r, t=0.25: f.kind == 'Cylinder' and f.radius is not None and abs(f.radius - r) < t

    # ---------------------------------------------------------------- the tilt yoke (T frame)
    zt = G.tilt_t
    a0, a1 = G.arm_y
    b0, b1 = G.bridge_z
    yoke = tu.tilt_yoke(G)
    base_fix = lambda f: (f.kind == 'Plane' and near(f.bbox[2], b0, 0.05) and near(f.bbox[5], b0, 0.05)) or \
        (cyl(f, tu.FAST['M4']['clear'] / 2) and f.bbox[5] < b1 + 0.1)
    mr_bore = lambda f: cyl(f, tu.MR126['D'] / 2) and f.center[1] < 0
    mr_floor = lambda f: f.kind == 'Plane' and near(f.center[1], -a0 - tu.MR126['B'], 0.05) and f.bbox[5] - f.bbox[2] < 14
    servo_seat = lambda f: (f.kind == 'Plane' and f.center[1] > a1 - 0.1 and f.bbox[1] > a1 - 0.1 and
                            abs(f.center[0]) < 14 and zt - 40 < f.center[2] < zt + 15)
    servo_screws = lambda f: cyl(f, 2.1) and f.center[1] > 0 and f.center[1] < a1
    m_tilt = M['tilt_kg']
    W30 = m_tilt * G0 * FALL_G
    study('tilt_yoke', 'R-fall-down', yoke, 'pa6_cf_xy',
          lambda st: (st.fix(base_fix), st.force(mr_bore, (0, 0, -W30 / 2)), st.force(servo_seat, (0, 0, -W30 / 2), probe=False)),
          True, f'30 g down on the tilting group ({m_tilt:.2f} kg): {W30:.0f} N, half at each arm (the MR126 bore, the servo pocket)')
    study('tilt_yoke', 'R-fall-side', yoke, 'pa6_cf_xy',
          lambda st: (st.fix(base_fix), st.force(mr_floor, (0, -W30, 0))),
          True, f'30 g sideways (-y): the tilting group {W30:.0f} N through the cradle spacer and the MR126 into its seat floor')
    study('tilt_yoke', 'R-fall-side+', yoke, 'pa6_cf_xy',
          lambda st: (st.fix(base_fix), st.force(servo_screws, (0, W30, 0))),
          True, f'30 g sideways (+y): {W30:.0f} N pulls the tilt servo off the arm, on its 4 M2 screw heads')
    lever = (G.barrel_x1 - G.tilt_x) / np.mean(G.stop_r)
    F_stop = PUSH_N * lever
    study('tilt_yoke', 'E-push-up', yoke, 'pa6_cf_xy',
          lambda st: (st.fix(base_fix), st.force(_sel_stop(G, zt, upper=True), (_stop_dir(G, upper=True)[0] * F_stop, 0, _stop_dir(G, upper=True)[1] * F_stop)),
                      # the pivot carries the rest (the cradle in balance), all of it on this arm's bore (conservative)
                      st.force(mr_bore, (-F_stop * _stop_dir(G, upper=True)[0], 0, PUSH_N - F_stop * _stop_dir(G, upper=True)[1]), probe=False)),
          False, f'{PUSH_N:.0f} N up at the muzzle ({G.barrel_x1 - G.tilt_x:.0f} mm from the tilt axis) holds the cradle on the 0 deg stop: '
                 f'{F_stop:.0f} N on the stop sector at r {np.mean(G.stop_r):.0f}')

    # ---------------------------------------------------------------- the turntable (pan_ring, T frame)
    z0g, z1g = G.turntable_z
    ring = tu.pan_ring(G)
    journal = lambda f: cyl(f, tu.BRG['d'] / 2) and f.bbox[2] >= G.brg_z - 0.1
    land = lambda f: f.kind == 'Plane' and near(f.bbox[2], G.brg_z + tu.BRG['B'], 0.05) and near(f.bbox[5], G.brg_z + tu.BRG['B'], 0.05) and f.bbox[3] < 27
    groove_top = lambda f: f.kind == 'Plane' and near(f.center[2], tu.circlip_z(G)[1], 0.05) and f.bbox[3] < 25.5
    yoke_holes = lambda f: cyl(f, tu.FAST['M4']['insert_pilot'] / 2) and f.center[2] > z0g
    m_up = M['pan_kg'] - M['pan_ring_kg']
    h = M['pan_group_com_z_mm'] - z1g
    Fs = m_up * G0 * FALL_G
    study('pan_ring', 'R-fall-down', ring, 'pa6_cf_z',
          lambda st: (st.fix(lambda f: journal(f) or land(f)), st.force(yoke_holes, (0, 0, -Fs))),
          True, f'30 g down: what stands on the turntable ({m_up:.2f} kg) pushes {Fs:.0f} N on the yoke bolts; the bearing holds the land and journal')
    study('pan_ring', 'R-fall-side', ring, 'pa6_cf_z',
          lambda st: (st.fix(lambda f: journal(f) or land(f) or groove_top(f)), st.force(yoke_holes, (Fs, 0, 0)),
                      st.torque(yoke_holes, (0, 0, z1g), (0, 1, 0), Fs * h / 1000, probe=False)),
          True, f'30 g sideways: {Fs:.0f} N at the yoke bolts and its {Fs * h / 1000:.1f} N m about the turntable top '
                f'(the panning mass {h:.0f} mm above it); the bearing holds the journal, the land and the circlip groove')
    # its teeth: a +-15 deg sector round the mesh, cut off at the web
    import cadquery as cq
    sx, sy = G.servo_pan_xy
    rp_ring = G.gear['m'] * G.gear['z_ring'] / 2
    wedge = tu.sector_z(rp_ring - 10.0, rp_ring + 3.0, 165.0, 195.0, z0g - 1, z1g + 1, n=12)
    sector = ring.intersect(wedge)
    cut_faces = lambda f: f.kind == 'Plane' and abs(abs(math.degrees(math.atan2(f.center[1], f.center[0]))) - 165.0) < 0.5 or \
        (f.kind == 'Cylinder' and f.radius is not None and abs(f.radius - (rp_ring - 10.0)) < 0.3)
    mesh_tooth = lambda f: (f.kind in ('Plane', 'BSpline surface') and f.center[0] < -rp_ring + 1.2 and abs(f.center[1]) < 2.2
                            and z0g + 0.5 < f.center[2] < z1g - 0.5 and f.center[0] > -rp_ring - G.gear['m'] - 0.2)
    for case, frac, rare in (('E-cap', CAP, False), ('R-stall', 1.0, True)):
        Ft = frac * SERVO_STALL / (G.gear['m'] * G.gear['z_pinion'] / 2000)
        Fr = Ft * math.tan(math.radians(20.0))
        study('pan_ring', f'{case}-teeth', sector, 'pa6_cf_xy',
              lambda st, Ft=Ft, Fr=Fr: (st.fix(cut_faces), st.force(mesh_tooth, (Fr, Ft, 0))),
              rare, f'the pan servo at {frac * 100:.0f} % of its stall: {Ft:.0f} N on the tooth at the mesh (+{Fr:.0f} N radial, 20 deg); '
                    f'a +-15 deg sector of the ring held at its cuts', mesh_mm=0.7)
    # ---------------------------------------------------------------- the pinion (frame: pinion, T at pan 0)
    pin = tu.pan_pinion(G)
    zp0 = G.servo_z0 + tu.SERVO['H'] + tu.SERVO['horn_t']
    horn_fix = lambda f: (cyl(f, tu.FAST['M3']['clear'] / 2) and f.bbox[2] < zp0 + 1.0) or \
        (f.kind == 'Plane' and near(f.bbox[2], zp0, 0.05) and near(f.bbox[5], zp0, 0.05))
    rpp = G.gear['m'] * G.gear['z_pinion'] / 2
    pin_tooth = lambda f: (f.kind in ('Plane', 'BSpline surface') and f.center[0] > sx + rpp - 1.2 and abs(f.center[1] - sy) < 2.2
                           and f.center[2] > zp0 + 1.5)
    for case, frac, rare in (('E-cap', CAP, False), ('R-stall', 1.0, True)):
        Ft = frac * SERVO_STALL / (rpp / 1000)
        Fr = Ft * math.tan(math.radians(20.0))
        study('pan_pinion', case, pin, 'pa6_cf_xy',
              lambda st, Ft=Ft, Fr=Fr: (st.fix(horn_fix), st.force(pin_tooth, (-Fr, -Ft, 0))),
              rare, f'the pan servo at {frac * 100:.0f} % of its stall: {Ft:.0f} N on one tooth at the pitch line (+{Fr:.0f} N radial); '
                    f'held by its 4 M3 screws and its flange on the horn', mesh_mm=0.6)

    # ---------------------------------------------------------------- the pan base (T frame, printed on its foot)
    base = tu.pan_base(G)
    foot = lambda f: f.kind == 'Plane' and near(f.bbox[2], 0.0, 0.05) and near(f.bbox[5], 0.0, 0.05)
    shoulder = lambda f: f.kind == 'Plane' and near(f.bbox[2], G.brg_z, 0.05) and near(f.bbox[5], G.brg_z, 0.05) and f.bbox[3] < 33.5
    seat = lambda f: cyl(f, tu.BRG['D'] / 2) and f.bbox[2] >= G.brg_z - 0.1
    m_pan = M['pan_kg']
    Fp = m_pan * G0 * FALL_G
    hb = M['pan_group_com_z_mm'] - (G.brg_z + tu.BRG['B'] / 2)
    study('pan_base', 'R-fall-down', base, 'pa6_cf_xy',
          lambda st: (st.fix(foot), st.force(shoulder, (0, 0, -Fp))),
          True, f'30 g down: the panning group ({m_pan:.2f} kg) {Fp:.0f} N through the 6810\'s outer race onto the Ø62 shoulder; the foot on the head ring')
    study('pan_base', 'R-fall-side', base, 'pa6_cf_z',
          lambda st: (st.fix(foot), st.force(seat, (Fp, 0, 0)), st.torque(seat, (0, 0, G.brg_z), (0, 1, 0), Fp * hb / 1000, probe=False)),
          True, f'30 g sideways: {Fp:.0f} N at the bearing seat and {Fp * hb / 1000:.1f} N m (the panning mass {hb:.0f} mm above the bearing); '
                f'the housing tube bends across its layers')
    sx, sy = G.servo_pan_xy
    W, L, sft = tu.SERVO['W'], tu.SERVO['L'], tu.SERVO['shaft_from_end']
    px0, py1 = sx - W / 2 - 0.3, sy + L - sft + 0.3
    end_wall = lambda f: f.kind == 'Plane' and near(f.center[1], py1, 0.1) and px0 - 0.1 < f.center[0] < sx + W / 2 + 0.4
    out_wall = lambda f: f.kind == 'Plane' and near(f.center[0], px0, 0.1) and sy - sft - 0.4 < f.center[1] < py1 + 0.1
    for case, frac, rare in (('E-cap', CAP, False), ('R-stall', 1.0, True)):
        Ft = frac * SERVO_STALL / (G.gear['m'] * G.gear['z_pinion'] / 2000)
        Fr = Ft * math.tan(math.radians(20.0))
        study('pan_base', f'{case}-servo', base, 'pa6_cf_xy',
              lambda st, Ft=Ft, Fr=Fr: (st.fix(foot), st.force(end_wall, (0, Ft, 0)), st.force(out_wall, (-Fr, 0, 0), probe=False)),
              rare, f'the pan servo at {frac * 100:.0f} % of its stall pushes its pocket: {Ft:.0f} N along it (the mesh\'s tangential force) '
                    f'and {Fr:.0f} N outwards (the separating force)')

    # ---------------------------------------------------------------- the pan clamp (T frame)
    clamp = tu.pan_clamp(G)
    ear_holes = lambda f: cyl(f, tu.FAST['M3']['clear'] / 2)
    clamp_bore = lambda f: cyl(f, 30.5)
    study('pan_clamp', 'R-fall-up', clamp, 'al6061',
          lambda st: (st.fix(ear_holes), st.force(clamp_bore, (0, 0, Fp))),
          True, f'30 g with the turret upside down (or the robot lifted by its turret): the panning group\'s {Fp:.0f} N lifts the '
                f'6810\'s outer race against the clamp (SendCutSend 6061-T6, 0.125 in), held by its 5 M3 screws (the load on the bore\'s '
                f'edge, where the race bears)', mesh_mm=1.0)

    # ---------------------------------------------------------------- the cradle (D48: a rail frame and two aluminium plates)
    xt, zc = G.tilt_x, G.tilt_c
    p0, p1 = G.plate_y
    fx0, fx1 = tu.PLATE['foot_x']
    ct_d, ct_l = tu.ct_points(G)
    m_cart = M['cartridge_kg']
    Fc = m_cart * G0 * FALL_G
    arm_push = G.barrel_x1 - G.tilt_x
    d_front, d_rear = ct_d[1][0] - xt, xt - ct_d[0][0]
    # the cartridge passes the push's moment to the cradle as a couple on its two dowels: up at the front, down at the rear
    F_front = (PUSH_N * arm_push + PUSH_N * d_rear) / (d_front + d_rear)
    F_rear = F_front - PUSH_N
    # the rail frame (printed flat: its layers are x-y planes), held where the plates hold it, loaded through the CT
    # The frame is held by its eight M3 x 8: clamped under each screw (a Ø9 spot of the rebate's face round each insert,
    # imprinted as a 0.3 mm pad so it can be held) and at the insert; the rest of the rebate face is left free. Holding
    # the whole rebate face bonded (the first run) put a peak at that face's rear edge that the part does not have (40.7
    # MPa against a 99th percentile of 10.5): the plate only bears on it.
    zf = (G.foot_z[0] + G.rail_z[1]) / 2
    frame = tu.cradle(G)
    for sgn in (1, -1):
        for x in tu.PLATE['foot_holes_x']:
            y0, y1 = (p0, p0 + 0.3) if sgn > 0 else (-p0 - 0.3, -p0)
            frame = frame.union(tu.cyl_y(4.5, y0, y1, x, zf).cut(tu.cyl_y(tu.FAST['M3']['insert_pilot'] / 2, y0 - 1, y1 + 1, x, zf)))
    spots = lambda f: f.kind == 'Plane' and near(abs(f.center[1]), p0 + 0.3, 0.05)
    inserts = lambda f: cyl(f, tu.FAST['M3']['insert_pilot'] / 2) and abs(f.center[1]) > 46.0 and fx0 < f.center[0] < fx1
    held = lambda f: spots(f) or inserts(f)
    dowels = lambda f: cyl(f, 2.0) and abs(f.center[1]) < 46.0 and f.center[2] < zc
    front_dowel = lambda f: dowels(f) and near(f.center[0], ct_d[1][0], 0.5)
    rear_dowel = lambda f: dowels(f) and near(f.center[0], ct_d[0][0], 0.5)
    latch = lambda f: cyl(f, tu.FAST['M4']['clear'] / 2) and near(f.center[0], ct_l[0], 0.5)
    study('cradle', 'R-fall-down', frame, 'pa6_cf_xy',
          lambda st: (st.fix(held), st.force(lambda f: dowels(f) or latch(f), (0, 0, -Fc))),
          True, f'30 g down: the cartridge ({m_cart:.2f} kg with 30 balls) {Fc:.0f} N through its CT dowels and latch; the rail frame held '
                f'by the two aluminium plates\' 6 x M3 x 8 (clamped under each screw)')
    study('cradle', 'R-fall-side', frame, 'pa6_cf_xy',
          lambda st: (st.fix(held), st.force(dowels, (0, -Fc, 0))),
          True, f'30 g sideways (-y): the cartridge\'s {Fc:.0f} N through the two CT dowels; the frame held by the plates')
    study('cradle', 'E-push-up', frame, 'pa6_cf_xy',
          lambda st: (st.fix(held), st.force(front_dowel, (0, 0, F_front)), st.force(rear_dowel, (0, 0, -F_rear), probe=False)),
          False, f'{PUSH_N:.0f} N up at the muzzle ({arm_push:.0f} mm from the tilt axis) reaches the frame through the cartridge as '
                 f'{F_front:.0f} N up at the front CT dowel and {F_rear:.0f} N down at the rear one; the plates hold the frame (the lug '
                 f'on the -y plate holds the 0 deg stop)')
    # each cheek plate (SendCutSend 6061-T6, 0.125 in), held at its joint at the tilt axis and loaded at its foot's three
    # screws with the cartridge's whole 30 g load (the two plates share it: one carrying all of it is the bound). The joint
    # is what clamps the plate: on the +y plate the horn boss's Ø20 face and its 4 x M3 x 14; on the -y plate the pivot
    # spacer's Ø18 face and the shoulder screw in the tapped hole. So that face can be held, the plate gets a 0.5 mm pad
    # of that outline on its outer face (held, so its own stiffness does not matter). Out of its plane the -y joint is a
    # pivot that carries no moment (the frame passes it to the +y side): there the case bounds the plate itself.
    foot_holes = lambda f: cyl(f, tu.FAST['M3']['clear'] / 2) and f.center[2] < G.foot_z[1] + 0.5
    plates = {}
    for nm, side in (('cradle_plate_l', 1), ('cradle_plate_r', -1)):
        yo = side * p1                                                  # the plate's outer face
        y0, y1 = sorted((yo, yo + side * 0.5))
        if side > 0:
            pad = tu.cyl_y(tu.HORN_BOSS['d'] / 2, y0, y1, xt, zc).cut(tu.cyl_y(3.25, y0 - 1, y1 + 1, xt, zc))
            for k in range(4):
                hx, hz = tu.polar(tu.SERVO['horn_pcd'] / 2, math.pi / 4 + k * math.pi / 2)
                pad = pad.cut(tu.cyl_y(tu.FAST['M3']['clear'] / 2, y0 - 1, y1 + 1, xt + hx, zc + hz))
            holes = lambda f: (f.kind in ('Cylinder', 'Cone') and math.hypot(f.center[0] - xt, f.center[2] - zc) < 9.0 and not cyl(f, 3.25))
            how = 'held at the horn boss\'s Ø20 face and the 4 x M3 x 14 into the servo horn'
        else:
            pad = tu.cyl_y(tu.PIVOT['boss_d'] / 2, y0, y1, xt, zc).cut(tu.cyl_y(tu.FAST['M5']['tap'] / 2, y0 - 1, y1 + 1, xt, zc))
            holes = lambda f: cyl(f, tu.FAST['M5']['tap'] / 2)
            how = 'held at the pivot spacer\'s Ø18 face and the shoulder screw (as if the pivot carried the moment: a bound)'
        shape = tu.cradle_plate(G, side).union(pad)
        face = lambda f, ye=yo + side * 0.5: f.kind == 'Plane' and near(f.center[1], ye, 0.05)
        joint = lambda f, h=holes, fc=face: fc(f) or h(f)
        plates[nm] = shape
        study(nm, 'R-fall-out', shape, 'al6061',
              lambda st, jt=joint, sd=side: (st.fix(jt), st.force(foot_holes, (0, -sd * Fc, 0))),
              True, f'30 g sideways: the cartridge\'s {Fc:.0f} N out of the plate\'s plane at its foot\'s 3 screws; {how}', mesh_mm=1.0)
        study(nm, 'R-fall-down', shape, 'al6061',
              lambda st, jt=joint: (st.fix(jt), st.force(foot_holes, (0, 0, -Fc))),
              True, f'30 g down: the cartridge\'s {Fc:.0f} N in the plate\'s plane at its foot\'s 3 screws; {how}', mesh_mm=1.0)
    plate_r = tu.cradle_plate(G, -1)
    lug_holes = lambda f: (f.kind in ('Cylinder', 'Cone') and any(math.hypot(f.center[0] - hx, f.center[2] - hz) < 0.6 for hx, hz in tu.lug_screws(G)))
    foot_c = np.mean(tu.PLATE['foot_holes_x'])
    M_push = PUSH_N * (G.barrel_x1 - foot_c) / 1000
    study('cradle_plate_r', 'E-push-up', plate_r, 'al6061',
          lambda st: (st.fix(lambda f: lug_holes(f) or cyl(f, tu.FAST['M5']['tap'] / 2)), st.force(foot_holes, (0, 0, PUSH_N)),
                      st.torque(foot_holes, (foot_c, -p1, G.foot_z[0] + tu.PLATE['foot_h'] / 2), (0, -1, 0), M_push, probe=False)),
          False, f'{PUSH_N:.0f} N up at the muzzle, all through the -y plate (the servo\'s side ignored): {PUSH_N:.0f} N and {M_push:.1f} N m at '
                 f'its foot\'s 3 screws from the frame, held by the stop lug\'s 2 screws and the pivot', mesh_mm=1.0)
    # the stop lug (SendCutSend 6061-T6, 0.100 in) in the push: the yoke's upper sector on its band's edge
    lug = tu.stop_lug(G)
    w = tu.STOP_HALF_DEG
    a_up = math.radians(-90 + w)
    F_lug = PUSH_N * (G.barrel_x1 - G.tilt_x) / np.mean(G.stop_r)

    def lug_face(f):
        if f.kind != 'Plane':
            return False
        a = math.degrees(math.atan2(f.center[2] - zc, f.center[0] - xt))
        return abs(a - (-90 + w)) < 2.5 and 23.5 < math.hypot(f.center[0] - xt, f.center[2] - zc) < 32.5
    study('stop_lug', 'E-push-up', lug, 'al6061',
          lambda st: (st.fix(lambda f: cyl(f, tu.FAST['M3']['tap'] / 2)), st.force(lug_face, (F_lug * math.sin(a_up), 0, -F_lug * math.cos(a_up)))),
          False, f'{PUSH_N:.0f} N up at the muzzle holds the lug on the yoke\'s upper sector: {F_lug:.0f} N on its band\'s edge at r '
                 f'{np.mean(G.stop_r):.0f}, in its own plane; held by its 2 tapped M3 holes alone (the CA ignored)', mesh_mm=0.8)

    # ---------------------------------------------------------------- the cartridge (C frame, printed on its base)
    cart = tu.cartridge_body(G)
    ct_fix = lambda f: (cyl(f, 2.0) and f.center[2] < G.base_z0 + 3) or (cyl(f, tu.FAST['M4']['insert_pilot'] / 2) and near(f.center[0], ct_l[0], 0.5))
    motor_holes = lambda f: cyl(f, tu.FAST['M3']['clear'] / 2) and G.plate_z0 - 0.5 < f.center[2] < G.plate_z1 + 0.5 and abs(f.center[0] - G.wheel_x) < 12
    servo_holes = lambda f: cyl(f, 1.2) and G.floor_z - G.floor_t - 1 < f.center[2] < G.floor_z + 0.5 and math.hypot(*f.center[:2]) < 32
    housing_top = lambda f: f.kind == 'Plane' and near(f.bbox[2], G.housing_top, 0.05) and near(f.bbox[5], G.housing_top, 0.05)
    post_tops = lambda f: f.kind == 'Plane' and near(f.bbox[2], G.plate_z1 + tu.CART_BOARD['boss_h'] + tu.CART_BOARD['standoff'], 0.05)
    g30 = G0 * FALL_G / 1000
    hub_tyre_g = 5.2 + 4.5                                          # the hub and the Ø34 tyre (cad/turret.py mass_properties)
    F_mot = 2 * (tu.MOTOR['mass_g'] + hub_tyre_g) * g30              # the X2216s with their adapters, hubs and tyres
    F_feed = (tu.SERVO['mass_g'] + 48.0) * g30                      # the feed servo and the dial
    F_hop = (44.5 + 16.8 + 55.0) * g30                              # the hopper, its lid and 30 balls
    F_brd = (tu.CART_BOARD['mass_g'] + 2 * tu.AM32['mass_g']) * g30  # the cartridge board and the two ESCs on its posts
    study('cartridge_body', 'R-fall-down', cart, 'pa6_cf_z',
          lambda st: (st.fix(ct_fix), st.force(motor_holes, (0, 0, -F_mot)), st.force(servo_holes, (0, 0, -F_feed), probe=False),
                      st.force(housing_top, (0, 0, -F_hop), probe=False), st.force(post_tops, (0, 0, -F_brd), probe=False)),
          True, f'30 g down on what the cartridge carries: the X2216s and wheels {F_mot:.0f} N under the cage plate, the feed servo and dial '
                f'{F_feed:.0f} N on the floor\'s four M2 holes, the hopper, lid and 30 balls {F_hop:.0f} N on the housing, the cartridge board '
                f'and ESCs {F_brd:.0f} N on its posts; held at the CT dowels and latch')
    left = lambda f: motor_holes(f) and f.center[1] > 0
    right = lambda f: motor_holes(f) and f.center[1] < 0
    # a shot's loads from the launch physics (sim/turret_launch3d.py at the set speed), scaled to the fastest ball the
    # bench lets through (the chronograph's 66 fps line): the nip's squeeze on each tyre and the recoil on the cage
    rec = json.loads((R / 'exports/turret/launch/launch3d.json').read_text())['recoil']
    k_fast = 66.0 / 52.0
    F_sq = rec['peak_normal_per_tyre_n'] * k_fast
    F_rc = rec['peak_force_on_cage_n'] * k_fast / 2
    study('cartridge_body', 'E-recoil', cart, 'pa6_cf_z',
          lambda st: (st.fix(ct_fix), st.force(left, (-F_rc, F_sq, 0)), st.force(right, (-F_rc, -F_sq, 0), probe=False)),
          False, f'a shot at 66 fps (the bench\'s trip line; the launch physics at 52 fps x 66 / 52): {F_sq:.0f} N squeezing each tyre apart '
                 f'and {2 * F_rc:.0f} N of recoil, on the motors\' mounts')

    # ---------------------------------------------------------------- the dial (C frame, PETG), on the feed servo's horn
    dial = tu.dial(G)
    horn_z = G.feed_face + tu.SERVO['horn_t']
    on_horn = lambda f: (cyl(f, tu.FAST['M3']['clear'] / 2) and math.hypot(*f.center[:2]) < 9) or \
        (f.kind == 'Plane' and near(f.bbox[2], horn_z, 0.05) and near(f.bbox[5], horn_z, 0.05) and math.hypot(*f.center[:2]) < 11.5)
    a_sp = math.radians(22.5)

    def spoke_face(f):
        if f.kind != 'Plane':
            return False
        r = math.hypot(f.center[0], f.center[1])
        a = math.degrees(math.atan2(f.center[1], f.center[0]))
        return G.dial_hub_r + 2 < r < G.dial_wall_r - 2 and 22.5 - 6.0 < a < 22.5 - 1.0 and G.dial_z0 + 2 < f.center[2] < G.dial_z0 + G.dial_h - 3
    stall = 2.94                                                       # STS3215 at 12 V
    for case, T_jam, rare, why in (('E-jam-capped', 0.3 * stall, False, 'the firmware\'s 30 % torque limit (docs/turret-firmware.md)'),
                                   ('R-jam-stall', stall, True, 'the servo\'s full stall (the torque limit not set)')):
        F_jam = T_jam / (G.rp / 1000)
        study('dial', case, dial, 'petg',
              lambda st, F_jam=F_jam: (st.fix(on_horn), st.force(spoke_face, (-F_jam * math.sin(a_sp), F_jam * math.cos(a_sp), 0))),
              rare, f'a jam at {why} ({T_jam:.2f} N m) with one spoke on a ball: {F_jam:.0f} N at the pocket radius {G.rp} mm; '
                    f'held on the horn (its four M3 screws and the boss\'s face)', mesh_mm=1.5)

    summary = {'targets': TARGETS, 'mesh_mm': mesh, 'masses': M, 'results': results}
    if not only:
        summary['hand_checks'] = hand_checks(G, M)
        summary['verdict'] = {
            'on': 'the layer-aware SF for printed parts (N2), the yield SF for the aluminium parts; the isotropic columns are reported with each result',
            'min_sf_everyday': min((r['verdict_sf'] for r in results if r['case'].startswith('E')), default=None),
            'min_sf_rare': min((r['verdict_sf'] for r in results if r['case'].startswith('R')), default=None),
            'all_ok': all(r['ok'] for r in results),
            'weakest': (lambda w: f"{w['part']} {w['case']}")(min(results, key=lambda r: r['verdict_sf'] / r['target'])) if results else None,
            'below_target': [f"{r['part']} {r['case']}: {r['verdict_sf']} < {r['target']}" for r in results if not r['ok']]}
        summary['table'] = [{'part': r['part'], 'case': r['case'], 'target': r['target'], 'sf_as_v0': r['safety_factor'],
                             'sf_isotropic_weak': r['sf_isotropic_weak'], 'sf_layer_aware': r['sf_layer_aware'],
                             'governs': (r['layer_aware'] or {}).get('governs'), 'verdict_sf': r['verdict_sf'], 'ok': r['ok']} for r in results]
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)) + '\n')
    return summary


def _stop_dir(G, upper=True):
    """Unit (x, z) direction of the force the cradle's lug puts on a yoke stop face (tangential at the stop radius):
    the lug sits at -90 deg; pushing the nose up turns it towards the upper stop at -90 + w."""
    w = tu.STOP_HALF_DEG
    a = math.radians(-90 + w if upper else -90 + G.tilt_min - w)
    # tangent pointing the way the lug moves into the stop
    t = (-math.sin(a), math.cos(a)) if upper else (math.sin(a), -math.cos(a))
    return t


def _stop_face(f, zt, G, upper=True):
    w = tu.STOP_HALF_DEG
    a = math.radians(-90 + w) if upper else math.radians(-90 + G.tilt_min - w)
    r = np.mean(G.stop_r)
    px, pz = r * math.cos(a), zt + r * math.sin(a)
    return abs(f.center[0] - px) < 2.0 and abs(f.center[2] - pz) < 2.5


def _sel_stop(G, zt, upper=True):
    a0 = G.arm_y[0]
    return lambda f: f.kind == 'Plane' and -a0 < f.center[1] < -a0 + tu.YOKE_STOP_PROUD + 0.1 and _stop_face(f, zt, G, upper)


def hand_checks(G, M):
    """Checks by formula, with their inputs."""
    out = {}
    # the barrel (PETG tube) as a cantilever from its socket, a hand pulling the muzzle down with 100 N (rare)
    D, d = G.barrel_od, G.bore
    Z = math.pi * (D ** 4 - d ** 4) / (32 * D)
    Lb = G.barrel_x1 - G.socket_x1
    sig = 100.0 * Lb / Z
    out['barrel'] = {'case': 'R: 100 N down at the muzzle', 'section_modulus_mm3': round(Z), 'lever_mm': Lb, 'stress_mpa': round(sig, 2),
                     'allowable_mpa': MATERIALS['petg'].strength_mpa, 'sf': round(MATERIALS['petg'].strength_mpa / sig, 1)}
    # the flywheel hub's rim at speed: a thin rotating ring, sigma = rho w^2 r^2; the no-load speed on a +5 % motor and +4 % rail
    rho = tu.DENS['pa6-cf'] * 1000
    w = 875 * 12 * 1.05 * 1.04 * 2 * math.pi / 60
    r_rim = (G.wheel_d / 2 - G.tyre_t) / 1000
    sig_rim = rho * w ** 2 * r_rim ** 2 / 1e6
    # the stretched tyre squeezes the rim: hoop tension sigma_t = E eps over its thickness, a pressure p = sigma_t t / r
    E_tpu, eps = 30.0, tu.TYRE_STRETCH
    p_tyre = E_tpu * eps * G.tyre_t / (r_rim * 1000)
    sig_hoop = p_tyre * r_rim * 1000 / 3.0
    # how far the tyre's bore grows at that speed (TPU 95A, soft end E 10 MPa): the grip left of the 4 % stretch
    grow = tu.DENS['tpu95'] * 1000 * w ** 2 * (r_rim) ** 2 / 10e6
    out['flywheel_hub'] = {'case': 'R: the no-load speed on a fast motor and a high rail', 'rpm': round(w * 60 / (2 * math.pi)),
                           'rim_radius_mm': r_rim * 1000, 'rim_hoop_stress_mpa': round(sig_rim, 2), 'tyre_squeeze_on_rim_mpa': round(sig_hoop, 2),
                           'allowable_mpa': MATERIALS['pa6_cf_xy'].strength_mpa, 'sf': round(MATERIALS['pa6_cf_xy'].strength_mpa / (sig_rim + sig_hoop), 1),
                           'tyre_bore_growth_pct': round(grow * 100, 1), 'stretch_pct': round(eps * 100, 1),
                           'grip_left': grow < eps, 'note': 'TPU E 10-30 MPa (docs/turret-physics.md finding 5); the bore grows less than the stretch'}
    # the journal's lip under the DIN 471 circlip: shear of the lip (6 mm long) over the groove's Ø47 when the turret hangs
    # upside down at 30 g (the panning group pulls the turntable out of the bearing)
    F_up = M['pan_kg'] * G0 * FALL_G
    A_lip = math.pi * 47.0 * tu.JOURNAL_LIP
    tau = F_up / A_lip
    out['journal_lip'] = {'case': 'R: 30 g with the turret upside down', 'force_n': round(F_up), 'shear_area_mm2': round(A_lip), 'shear_mpa': round(tau, 2),
                          'allowable_mpa': round(0.5 * MATERIALS['pa6_cf_z'].strength_mpa, 1), 'sf': round(0.5 * MATERIALS['pa6_cf_z'].strength_mpa / tau, 1),
                          'note': 'shear allowable taken as half the across-layer tensile strength'}
    # the TM bolts: the sideways fall's moment over the 80 x 80 pattern, two bolts in tension
    F_side = M['total_kg'] * G0 * FALL_G
    mom = F_side * M['com_mm'][2] / 1000
    T_bolt = mom / (0.080 * 2)
    out['tm_bolts'] = {'case': 'R: 30 g sideways on the whole turret', 'moment_nm': round(mom, 1), 'tension_per_bolt_n': round(T_bolt),
                       'm5_insert_pullout_n_est': 1500, 'sf': round(1500 / T_bolt, 1), 'note': 'M5 heat-set insert in PA6-CF/PETG: ~1.5 kN pull-out (est, CNC Kitchen tests)'}
    # the yoke's four M4 inserts in the turntable: the upper panning group's sideways fall
    m_up = M['pan_kg'] - M['pan_ring_kg']
    mom_y = m_up * G0 * FALL_G * (M['pan_group_com_z_mm'] - G.turntable_z[1]) / 1000
    T_y = mom_y / (0.056 * 2)
    out['yoke_inserts'] = {'case': 'R: 30 g sideways on the yoke and all it carries', 'moment_nm': round(mom_y, 1), 'tension_per_insert_n': round(T_y),
                           'm4_insert_pullout_n_est': 1100, 'sf': round(1100 / T_y, 1)}
    # the turret bay: the boards and tray hanging off the -y arm at 30 g, on 4 x M3 flat heads 43 mm apart
    m_bay = (tu.TB['mass_g'] + 37.4) / 1000
    F_bay = m_bay * G0 * FALL_G
    arm_bay = (tu.TB['y_out'] - G.arm_y[1]) / 2 / 1000
    T_bay = F_bay * arm_bay / 0.043 / 2
    out['board_bay'] = {'case': 'R: 30 g down on the bay', 'force_n': round(F_bay), 'tension_per_screw_n': round(T_bay),
                        'm3_insert_pullout_n_est': 700, 'sf': round(700 / max(T_bay, 1e-6), 1)}
    # ---- the cradle's joints (D48)
    Fc = M['cartridge_kg'] * G0 * FALL_G
    F_lug = PUSH_N * (G.barrel_x1 - G.tilt_x) / np.mean(G.stop_r)
    # the horn: 4 x M3 x 14 flat heads (ISO 10642, 8.8) through the +y plate (3.175) and the horn boss (9.0) into the horn's
    # tapped flange: 1.8 mm of thread. Stripping the horn's internal thread (aluminium, shear 0.6 x ~200 MPa, area
    # pi x d_minor 2.46 x engagement x 0.75); the side fall pulls the boss off the horn with the cradle's whole share
    eng = tu.PLATE['horn_screw_l'] - SHEET_T - (G.arm_y[1] - tu.SERVO['horn_t'] - G.plate_y[1])
    strip = 0.6 * 200.0 * math.pi * 2.46 * eng * 0.75
    out['horn_screws'] = {'case': 'R: 30 g sideways, the cradle pulled off the horn (all of it on this side)', 'engagement_mm': round(eng, 2),
                          'threads_engaged': round(eng / 0.5, 1), 'tension_per_screw_n': round(Fc / 4), 'strip_n_per_screw_est': round(strip),
                          'sf': round(strip / (Fc / 4), 1), 'note': 'the screw tips stop 0.7 mm short of the flange\'s back (the servo\'s face)'}
    # the stop lug's 2 x M3 x 6 flat heads (A2-70, shank shear 0.6 x 700 MPa on Ø2.4 at the thread root) carry the push's
    # 262 N in shear (the CA ignored); bearing in the 3.175 plate and the 2.54 lug
    tau = F_lug / 2 / (math.pi / 4 * 2.39 ** 2)
    brg = F_lug / 2 / (3.0 * tu.SHEET['al6061_100']['thickness_mm'])
    out['lug_screws'] = {'case': f'E: the 50 N push on the muzzle, {F_lug:.0f} N on the lug', 'shear_mpa': round(tau, 1), 'shear_allowable_mpa': 420,
                         'sf_shear': round(420 / tau, 1), 'bearing_in_lug_mpa': round(brg, 1), 'bearing_allowable_mpa': 276,
                         'sf_bearing': round(276 / brg, 1)}
    # the pivot spacer's land (PA6-CF, Ø6.8 x 1) on the MR126's inner race (Ø6.0..6.8 in contact) in the -y side fall, with
    # the cradle's whole share on this side; and the shoulder screw's step on its inner part (Ø5.3..6.0): snug only
    a_race = math.pi / 4 * (tu.PIVOT['land_d'] ** 2 - 6.0 ** 2)
    a_step = math.pi / 4 * (6.0 ** 2 - tu.PIVOT['bore'] ** 2)
    allow_c = 40.0                    # MPa, humid printed PA6-CF in compression along its build direction (est, half of dry)
    out['pivot_land'] = {'case': 'R: 30 g sideways (-y), the cradle into the MR126 through the land', 'force_n': round(Fc),
                         'contact_on_race_mm2': round(a_race, 1), 'stress_mpa': round(Fc / a_race, 1), 'allowable_mpa_est': allow_c,
                         'sf': round(allow_c * a_race / Fc, 1),
                         'shoulder_step_preload_max_n': round(0.5 * allow_c * a_step),
                         'note': 'tighten the shoulder screw snug (about 0.15 N m, a drop of CA gel on the thread): at half the allowable the step may '
                                 f'press the land with {0.5 * allow_c * a_step:.0f} N; the shank carries the pivot, the thread only retains it'}
    # the -y plate out of its plane, as it really is held: its pivot is a bearing and carries no moment, so a sideways load
    # at the foot is reacted there as a force and the frame takes the moment at the foot's screws; the plate's largest
    # bending is then where the 44 mm cheek meets the foot, not at the pivot (the FEA case clamps the pivot: a bound)
    h = tu.Geo().tilt_c - G.foot_z[1]
    sig_r = 6 * Fc * h / (2 * tu.PLATE['half_w'] * SHEET_T ** 2)
    out['plate_r_out_of_plane'] = {'case': 'R: 30 g sideways, the -y plate pinned at its pivot, the frame holding its foot', 'force_n': round(Fc),
                                   'lever_mm': round(h, 1), 'section_mm': [2 * tu.PLATE['half_w'], SHEET_T], 'stress_mpa': round(sig_r, 1),
                                   'yield_mpa': 276, 'sf': round(276 / sig_r, 1),
                                   'note': 'cradle_plate_r R-fall-out clamps the pivot as if it carried the moment (a bound on the plate)'}
    # the plates on the rail frame: 4 x M3 inserts a side (in the rebate, along y); the side fall pulls the +y plate's foot
    out['plate_inserts'] = {'case': 'R: 30 g sideways, the frame pulling one plate\'s foot', 'tension_per_insert_n': round(Fc / 4),
                            'm3_insert_pullout_n_est': 700, 'sf': round(700 / (Fc / 4), 1),
                            'note': 'the other plate takes the same load in bearing on the rebate\'s face'}
    # the shoulder screw's M5 x 0.8 in the -y plate's 3.175 mm tapped 6061-T6: what holds the screw in
    a_thr = math.pi * 4.13 * SHEET_T * 0.75
    out['pivot_thread'] = {'case': 'retention: the M5 thread in the tapped plate', 'engagement_mm': SHEET_T, 'threads': round(SHEET_T / 0.8, 1),
                           'strip_n_est': round(0.6 * 200.0 * a_thr), 'note': 'it only retains the screw: the -y load goes through the land, '
                                                                             'the radial load through the shank in the MR126'}
    return out


SHEET_T = 3.175          # the cheek plates' 0.125 in


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mesh', type=float, default=2.5)
    ap.add_argument('--no-anim', action='store_true')
    ap.add_argument('--only', nargs='+')
    a = ap.parse_args()
    run(a.mesh, anim=not a.no_anim, only=a.only)
