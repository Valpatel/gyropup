"""Strength of the turret's printed parts (cadagent.fea) under slewing, a push on the barrel, and a fall.

    .venv/bin/python cad/turret_studies.py [--mesh 2.5] [--no-anim] [--only tilt_yoke pan_ring]

Every printed part that carries load is meshed from cad/turret.py's solid (in its build frame), held where its bolts
and seats hold it, loaded where its neighbours push, and solved with cadagent.fea (P2 tetrahedra, linear elastic).
The safety factor uses humid printed PA6-CF (cadagent.fea MATERIALS: 49 MPa along the layers, 23 MPa across them,
both x0.6 for humidity and x0.8 for print defects on Bambu's dry data) or PETG (20 MPa across its layers); the
material is chosen per part and case by how the part is printed and which way its peak stress runs. Targets as for
the leg (cad/leg_studies.py): SF 2 for everyday loads, 1.2 for rare ones.

Loads (masses from cad/turret.py's build: the tilting group 640 g with 30 balls, the panning group 1.05 kg, the
turret 1.34 kg):
  E-cap    everyday: the pan servo at its firmware cap, 50 % of its 2.94 N m stall, through the 21:63 gears
  E-push   everyday: a hand pushes the muzzle up or down with 50 N; the cradle's lug meets the 0 or -25 deg stop
           (a push sideways back-drives the pan servo at its cap: E-cap)
  R-stall  rare: the pan servo at its full stall (the cap failed, or it is forced)
  R-fall   rare: 30 g on everything (the TM interface's design load, docs/cad-plan.md section 5): straight down, and
           sideways (the robot falling over), each part loaded by what it carries
Writes exports/turret/fea/<part>-<case>.png (+ .mp4 overload video and .json for the interactive viewer) and
summary.json. Parts too small or simple for a mesh (the barrel tube, the flywheel hub at speed, the journal's lip
under the circlip, the fasteners) are checked by hand in hand_checks() with their inputs.
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
         'cartridge_body': (30, -60), 'pan_clamp': (40, -60), 'dial': (40, -60)}


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
    cart = sum(rows[n]['mass_g'] * rows[n]['qty'] for n in rows if T.frame.get(n) == 'tilt' and n not in ('cradle', 'laser_mount', 'laser',
                                                                                                         'tilt_bearing_inner', 'shoulder_screw')) / 1000
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

    def study(part, case, shape, mat, setup, rare, why, mesh_mm=None):
        if only and part not in only:
            return None
        t0 = time.time()
        st = Study(shape, MATERIALS[mat], mesh_mm=mesh_mm or mesh, name=f'{part} {case}')
        setup(st)
        r = st.solve()
        png = OUT / f'{part}-{case}.png'
        disp = r['probe_displacement_mm'] and round(float(np.linalg.norm(r['probe_displacement_mm'])), 3)
        st.render(png, view=VIEWS.get(part, (25, -60)), title=f"{part} {case} ({MATERIALS[mat].name}): SF {r['safety_factor']}, {disp} mm at the load")
        if anim:
            r['animation'] = str(st.animate(OUT / f'{part}-{case}.mp4', view=VIEWS.get(part, (25, -60)), title=f'{part} {case}: {MATERIALS[mat].name}').relative_to(R))
            r['viewer'] = str(st.export_viewer(OUT / f'{part}-{case}.json').relative_to(R))
        target = TARGETS['sf_rare' if rare else 'sf']
        r.update(part=part, case=case, material_id=mat, load_from=why, png=str(png.relative_to(R)), target=target,
                 ok=r['safety_factor'] >= target, seconds=round(time.time() - t0, 1))
        results.append(r)
        print(f"  {part:15} {case:12} {mat:9} SF {r['safety_factor']:6} (>= {target})  {r['von_mises_design_mpa']:7} MPa  "
              f"{disp} mm  ({r['mesh']['tets']} tets, {r['seconds']} s)", flush=True)
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

    summary = {'targets': TARGETS, 'mesh_mm': mesh, 'masses': M, 'results': results}
    if not only:
        summary['hand_checks'] = hand_checks(G, M)
        summary['verdict'] = {
            'min_sf_everyday': min((r['safety_factor'] for r in results if r['case'].startswith('E')), default=None),
            'min_sf_rare': min((r['safety_factor'] for r in results if r['case'].startswith('R')), default=None),
            'all_ok': all(r['ok'] for r in results),
            'weakest': (lambda w: f"{w['part']} {w['case']}")(min(results, key=lambda r: r['safety_factor'] / r['target'])) if results else None}
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)) + '\n')
    return summary


def _stop_dir(G, upper=True):
    """Unit (x, z) direction of the force the cradle's lug puts on a yoke stop face (tangential at the stop radius):
    the lug sits at -90 deg; pushing the nose up turns it towards the upper stop at -90 + w."""
    a = math.radians(-90 + 7.5 if upper else -90 + G.tilt_min - 7.5)
    # tangent pointing the way the lug moves into the stop
    t = (-math.sin(a), math.cos(a)) if upper else (math.sin(a), -math.cos(a))
    return t


def _stop_face(f, zt, G, upper=True):
    a = math.radians(-90 + 7.5) if upper else math.radians(-90 + G.tilt_min - 7.5)
    r = np.mean(G.stop_r)
    px, pz = r * math.cos(a), zt + r * math.sin(a)
    return abs(f.center[0] - px) < 2.0 and abs(f.center[2] - pz) < 2.5


def _sel_stop(G, zt, upper=True):
    a0 = G.arm_y[0]
    return lambda f: f.kind == 'Plane' and -a0 < f.center[1] < -a0 + 2.6 and _stop_face(f, zt, G, upper)


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
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mesh', type=float, default=2.5)
    ap.add_argument('--no-anim', action='store_true')
    ap.add_argument('--only', nargs='+')
    a = ap.parse_args()
    run(a.mesh, anim=not a.no_anim, only=a.only)
