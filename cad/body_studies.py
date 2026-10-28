"""Strength and stiffness of the body's frame (milestone M5, task T6), cadagent.fea on the frame's real solids.

    .venv/bin/python cad/body_studies.py [--mesh 4] [--no-anim] [--only S1 D1]

Loads come from the leg rig at the body's real half mass (cad/body_legloads.py -> exports/body/leg-loads.json, D56):
each leg's vertical force and roll moment where it enters the body, at the hip frame's mount plane, taken every step
by d'Alembert on the leg module (the axle's peak is mostly the wheel and links decelerating on the ground, and never
reaches the body). The rare case is the largest roll moment of the jumps and the drop, with that scenario's largest
vertical force; the fault case the undamped power cut (D39); both with a 10 % sideways grip of the ground force at the
contact patch. In S1 both legs land and the payload's inertia reacts on the tray and the belly; in S1b one leg's load
crosses the box to the other cheek, clamped (a bound).

The parts are bonded where they bolt (the M5 joints at 4-5 kN of preload do not slip under these loads: friction
0.3 x preload is above the largest bolt shear found); the cheeks, tray and belly plate are one solid for the mesher.
Aluminium is isotropic and its yield is known, so the targets are yield-based (the plan's): safety factor >= 2 on
yield at the rare peaks for every sheet part (5052-H32 193 MPa is used for the whole box: the weaker alloy),
the deck <= 0.5 mm under a 300 N hand load, the twist between the two hip faces <= 0.1 deg under one leg's 80 N m.

Cases
  S1 landing   both legs at the rare load (above); S1F the same at the fault load (SF >= 1.2); S1b one leg, the other clamped
  S2 twist     one leg's 80 N m roll moment (the HM budget, docs/mechanical-interfaces.md): stiffness and twist
  S3 pitch     the two motors' 60 N m caps reacted as one 120 N m couple about y, plus the HM budget's 600 N fore-aft
  D1 hand      300 N down on the deck at its front edge over the lidar (the cantilever) and at the riser
  D2 turret    a 30 g fall of the 1.70 kg head budget, its centre 100 mm above the TM face (a tip-over: SF >= 1.2)
  T1 tray      the battery cassette and the compute at 5 g on the floor tray (a landing)
Writes exports/body/fea/<case>.png (+ .mp4 overload video, .json for the viewer) and summary.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_frame as bf  # noqa: E402
import body_params as bp  # noqa: E402
from cadagent.fea import Material, Study, any_of, cylinder_at, in_box, plane_at  # noqa: E402

OUT = Path(os.environ.get('GYROPUP_BODY_FEA_OUT') or (R / 'exports' / 'body' / 'fea'))     # a study sweep writes elsewhere
AL5052 = Material('5052-H32 aluminium', 70300.0, 0.33, 193.0, 2.68, 'yield strength (ASM); used for the whole box (6061-T6 parts are stronger)')
AL6061 = Material('6061-T6 aluminium', 68900.0, 0.33, 276.0, 2.70, 'yield strength')
TARGETS = {'sf': 2.0, 'sf_fault': 1.2, 'deck_mm': 0.5, 'twist_deg': 0.1, 'sf_turret_fall': 2.0}    # D59: the turret's tip-over at 2.0
G = 9.81
ROBOT_KG = 29.5                  # the plan's estimate until T3's ledger (exports/body/mass.json) is in


def _rel(p):
    """A path relative to the repository when it is in it."""
    p = Path(p)
    return str(p.relative_to(R)) if p.is_relative_to(R) else str(p)


def _wheel_r_mm():
    """D69's 10 in tyre's radius (cad/body_params.py D69_WHEEL_CAD; the BotWheel's 85.65 mm before D69)."""
    return bp.D69_WHEEL_CAD['od_mm'] / 2


def _tyre_y_module_mm():
    """D69's tyre centre plane in the left module's frame (the leg's foot face + 7.5 + half the tyre)."""
    fb = bp._fivebar()
    return fb.Y['wheel_boss'] + 7.5 + bp.D69_WHEEL_CAD['tyre_width_mm'] / 2


def rare_leg_load(kind='rare'):
    """The leg's load on the body for a case: 'rare' (the jumps and the drop) or 'fault' (the undamped power cut), from
    exports/body/leg-loads.json (the rig at the body's real half mass, cad/body_legloads.py). What reaches the body is
    taken at the hip frame's mount plane (the leg's own mass decelerates on the ground force directly): the largest
    roll moment of the case's scenarios, with the largest vertical force of the same scenario (the two peaks combined),
    plus a 10 % sideways grip of the ground force at the contact patch. Returns the vertical force and the robot y of
    the line it acts on (left leg) so that it carries the roll moment."""
    f = R / 'exports/body/leg-loads.json'
    d = json.loads(f.read_text())
    fb = bp._fivebar()
    M, name = d[kind + '_body']
    sc = d['scenarios'][name]
    b = sc['body']
    Fz = max(b['peak_vertical_n'], b['with_vertical_n'])
    y_mount = bp.to_robot((0.0, fb.Y['centre_plane'], 0.0), 'left')[1]
    L = b['at_L_mm']
    hm = d['half_mass_kg']
    Fg = b['with_ground_n']
    return {'scenario': name, 'Fz': Fz, 'M_roll': M, 'y_line': y_mount + 1000.0 * M / Fz, 'L_mm': L,
            'y_wheel': bp.y_off() + _tyre_y_module_mm(), 'z_patch': -(L + _wheel_r_mm()), 'Fx': 0.0, 'Fy': 0.10 * Fg,
            'half_mass_kg': hm, 'kind': kind, 'axle_n': sc['peak_axle_force_n'],
            'from': (f"rig '{name}' at {hm} kg a leg (axle {sc['peak_axle_force_n']:.0f} N): {M:.0f} N m roll and {Fz:.0f} N up at "
                     f"the hip frame's mount plane, plus 10 % of the {Fg:.0f} N ground force sideways at the contact patch")}


# ------------------------------------------------------------------------------------------- the models

def spine_box():
    """The two cheeks, the six standoffs (as solid bars) and the tray and belly plates' middle strips, fused: the
    box that carries one leg's load to the other. Robot frame."""
    import cadquery as cq
    parts = bf.frame_parts()
    s = parts['cheek_left'].shape.union(parts['cheek_right'].shape)
    for x, z in bf.SPACERS_XZ:
        s = s.union(bf.hexagon_y(bf.SPACER_HEX, -bf.GAP_Y - 0.5, bf.GAP_Y + 0.5, x, z))
    zt = bf.ZT
    ttr, tbe = bp.STOCK[bp.TRAY]['t'], bp.STOCK[bp.BELLY]['t']
    x0, x1 = bp.SPINE_X[0] - 30.0, bp.SPINE_X[1] + 30.0
    half = bf.PEM_Y + 14.0
    tray = bf.box(x0, x1, -half, half, zt - 0.05, zt + ttr)
    belly = bf.box(x0, x1, -bp.BELLY_HALF_Y, bp.BELLY_HALF_Y, -zt - tbe, -zt + 0.05)
    for x in bf.FLANGE_NUT_X:                             # the screws' holes through the plates (stress raisers)
        for sy in (1, -1):
            tray = tray.cut(bf.cyl_z(2.75, zt - 1, zt + ttr + 1, x, sy * bf.PEM_Y))
            belly = belly.cut(bf.cyl_z(2.75, -zt - tbe - 1, -zt + 1, x, sy * bf.PEM_Y))
    s = s.union(tray).union(belly)
    return s.clean()


def iface(side='left'):
    """Selectors for one cheek's frame interface: the six bolt holes and the two bearing strips on its outer face."""
    m = bp.frame_mounts()
    sy = 1 if side == 'left' else -1
    yf = sy * bf.FACE_Y
    holes = [bp.to_robot((x, m['centre_plane_y'], z), side) for x, z in m['holes']]
    sel_holes = any_of(*[cylinder_at((p[0], yf, p[2]), (0, 1, 0), radius_max=3.0, tol=0.6) for p in holes])
    zlo = min(f[2] for f in m['face'])
    zhi = max(f[3] for f in m['face'])
    xb = max(abs(f[0]) for f in m['face'])
    # the cheek's outer face where the frame's flange ends bear (z 60..74 both rows): planar faces in y = yf within the box
    sel_face = lambda f: (f.kind == 'Plane' and abs(f.bbox[1] - yf) < 0.05 and abs(f.bbox[4] - yf) < 0.05
                          and f.bbox[0] >= -xb - 1 and f.bbox[3] <= xb + 1)
    return sel_holes, sel_face, holes


PAYLOAD_BELLY_SHARE = 0.20      # the battery's share of the body's mass hangs under the belly plate; the rest sits on the tray
SPACER_SKIP_MM = 4.0             # the bonded standoff-to-cheek corners are singular in a linear model: their stress is
                                 # reported apart, and the standoffs are checked as bolted pins by hand


def away_from_spacers(st, r):
    """The design stress again without the elements within SPACER_SKIP_MM of a standoff's end (the bonded corner), and
    the standoffs' own peak."""
    c = st.points[st.tets].mean(axis=1)
    near = np.zeros(len(c), bool)
    for x, z in bf.SPACERS_XZ:
        for sy in (1, -1):
            d = np.sqrt((c[:, 0] - x) ** 2 + (c[:, 2] - z) ** 2)
            near |= (d < 3.5 + SPACER_SKIP_MM) & (np.abs(c[:, 1] - sy * bf.GAP_Y) < SPACER_SKIP_MM)
    ok = ~near & ~st._touches_bc
    vm = float(st.vm_elem[ok].max()) if ok.any() else None
    vs = float(st.vm_elem[near].max()) if near.any() else None
    return {'design_stress_away_from_spacer_ends_mpa': round(vm, 1) if vm else None,
            'sf_away_from_spacer_ends': round(st.material.strength_mpa / vm, 2) if vm else None,
            'spacer_end_peak_mpa': round(vs, 1) if vs else None}


def symmetric_landing(st, leg):
    """Both legs land: each cheek takes its leg's vertical force on the wheel's mid-plane line and its 10 % sideways
    grip (outwards) at the contact patch; the payload's inertia reacts the vertical force on the tray (the compute,
    the power bay, the deck through the posts) and the belly (the battery). These balance exactly; the fore-aft grip
    and its pitch moment are S3's (here only the anchor would react them)."""
    for side, sy in (('left', 1.0), ('right', -1.0)):
        h, f, _ = iface(side)
        force_at(st, any_of(h, f), (0.0, 0.0, leg['Fz']), (0.0, sy * leg['y_line'], 0.0), probe=(side == 'left'))
        force_at(st, any_of(h, f), (0.0, sy * leg['Fy'], 0.0), (0.0, sy * leg['y_wheel'], leg['z_patch']), probe=False)
    zt, tt, tb = bf.ZT, bp.STOCK[bp.TRAY]['t'], bp.STOCK[bp.BELLY]['t']
    share = PAYLOAD_BELLY_SHARE
    st.force(lambda f: f.kind == 'Plane' and abs(f.bbox[2] - (zt + tt)) < 0.05 and abs(f.bbox[5] - (zt + tt)) < 0.05,
             (0.0, 0.0, -2 * leg['Fz'] * (1 - share)), probe=False)
    st.force(lambda f: f.kind == 'Plane' and abs(f.bbox[2] - (-zt - tb)) < 0.05 and abs(f.bbox[5] - (-zt - tb)) < 0.05,
             (0.0, 0.0, -2 * leg['Fz'] * share), probe=False)


def hot_spots(st, n=6):
    """Where the highest stresses are (away from the loaded and fixed faces): [[MPa, x, y, z, region]]."""
    c = st.points[st.tets].mean(axis=1)
    ok = ~st._touches_bc
    idx = np.argsort(-np.where(ok, st.vm_elem, 0))[:200]
    out, seen = [], []
    for i in idx:
        p = c[i]
        if any(np.linalg.norm(p - q) < 12.0 for q in seen):
            continue
        seen.append(p)
        x, y, z = (float(v) for v in p)
        reg = ('plates' if abs(z) > bf.ZT - 0.1 else 'spacer' if abs(y) < bf.GAP_Y - 0.1 else
               'cheek flange' if abs(y) > bf.FACE_Y + 0.1 else 'cheek web' if abs(z) < 74.6 else 'cheek bend')
        out.append([round(float(st.vm_elem[i]), 1), round(x, 1), round(y, 1), round(z, 1), reg])
        if len(out) >= n:
            break
    return out


def centroid(st, sel):
    tags = set(st.select(sel))
    fs = [f for f in st.faces if f.tag in tags]
    return sum(f.center * f.area for f in fs) / sum(f.area for f in fs)


def force_at(st, sel, F_n, P_mm, probe=True):
    """A force whose line of action passes through P (mm), carried by the selected faces: an even traction plus the
    couple of its offset from their centroid."""
    Gc = centroid(st, sel)
    st.force(sel, tuple(float(v) for v in F_n), probe=probe)
    M = np.cross(np.asarray(P_mm, float) - Gc, np.asarray(F_n, float)) / 1000.0
    for i in range(3):
        if abs(M[i]) > 0.05:
            e = [0.0, 0.0, 0.0]
            e[i] = 1.0
            st.torque(sel, tuple(Gc), tuple(e), float(M[i]), probe=False)
    return Gc, M


# ------------------------------------------------------------------------------------------- the cases

def run(mesh=4.0, anim=True, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    if only and (OUT / 'summary.json').exists():          # a partial rerun keeps the other cases' results
        results = {k: v for k, v in json.loads((OUT / 'summary.json').read_text()).get('results', {}).items() if k.split('-')[0] not in only}

    def record(case, st, rare, why, extra=None, view=(25, -60)):
        r = st.solve()
        r.update({'case': case, 'rare': rare, 'why': why})
        if extra:
            r.update(extra(st, r) if callable(extra) else extra)
        png = OUT / f'{case}.png'
        st.render(png, view=view, title=f"{case}: {st.material.name}, SF {r['safety_factor']}, max {r['max_displacement_mm']} mm")
        r['picture'] = _rel(png)
        if anim:
            try:
                r['animation'] = _rel(st.animate(OUT / f'{case}.mp4', view=view, title=f'{case}: {st.material.name}'))
                r['viewer'] = _rel(st.export_viewer(OUT / f'{case}.json'))
            except Exception as e:                      # a video failing does not lose the result
                r['animation_error'] = str(e)
        target = TARGETS['sf_fault'] if rare == 'fault' else TARGETS['sf_turret_fall'] if rare == 'D2' else TARGETS['sf']
        sf = r.get('sf_by_part') or r.get('sf_away_from_spacer_ends') or r['safety_factor'] or 0
        r['target_sf'] = target
        r['pass'] = bool(sf >= target and r.get('post_corner_pass', True))
        r['hot_spots'] = hot_spots(st)
        results[case] = r
        print(f"  {case}: SF {r['safety_factor']} ({r.get('sf_away_from_spacer_ends')} away from the standoffs' ends), max {r['max_displacement_mm']} mm, design stress {r['von_mises_design_mpa']} MPa; hot {r['hot_spots'][:3]}"
              + (f", {r.get('twist_deg')} deg" if 'twist_deg' in r else '') + f" ({r['mesh']['tets']} tets)")
        (OUT / 'summary.json').write_text(json.dumps({'targets': TARGETS, 'results': results}, indent=1, default=str) + '\n')
        return r

    want = lambda c: only is None or c in only
    box = None
    if any(want(c) for c in ('S1', 'S2', 'S3')):
        box = spine_box()
    leg = rare_leg_load('rare')
    if want('S1'):                                      # both legs land: each cheek takes its leg's force and roll moment;
        st = Study(box, AL5052, mesh_mm=mesh, name='spine S1 landing')   # the payload's inertia reacts on the tray and belly
        F, P = (leg['Fx'], leg['Fy'], leg['Fz']), None
        symmetric_landing(st, leg)
        zt, tb = bf.ZT, bp.STOCK[bp.BELLY]['t']
        # the loads balance: one screw hole in the belly strip holds the model still (its reaction is ~0)
        st.fix(cylinder_at((bf.FLANGE_NUT_X[1], bf.PEM_Y, -zt - tb / 2), (0, 0, 1), radius_max=3.0, tol=0.6))
        record('S1-landing', st, True, leg['from'] + ' on BOTH legs; the payload\'s inertia on the tray (80 %) and the belly (20 %)',
               away_from_spacers)
    if want('S1F'):                                     # the undamped power cut (D39's fault case), both legs, SF >= 1.2
        fl = rare_leg_load('fault')
        st = Study(box, AL5052, mesh_mm=mesh, name='spine S1F collapse')
        symmetric_landing(st, fl)
        zt, tb = bf.ZT, bp.STOCK[bp.BELLY]['t']
        st.fix(cylinder_at((bf.FLANGE_NUT_X[1], bf.PEM_Y, -zt - tb / 2), (0, 0, 1), radius_max=3.0, tol=0.6))
        record('S1F-collapse', st, 'fault', fl['from'] + ' on BOTH legs (the undamped power cut, D39); payload inertia as S1',
               away_from_spacers)
        st = Study(box, AL5052, mesh_mm=mesh, name='spine S1b one leg')
        hr, fr, _ = iface('right')
        st.fix(any_of(hr, fr))
        hl, fl, holes = iface('left')
        force_at(st, any_of(hl, fl), (0.0, 0.0, leg['Fz']), (0.0, leg['y_line'], 0.0))
        force_at(st, any_of(hl, fl), (leg['Fx'], leg['Fy'], 0.0), (0.0, leg['y_wheel'], leg['z_patch']), probe=False)
        record('S1b-one-leg-bound', st, True, leg['from'] + ' on ONE leg, the other cheek clamped: every newton crosses the gap '
               '(a bound: in a one-wheel landing the body\'s inertia takes most of it)', away_from_spacers)
    if want('S2'):
        st = Study(box, AL5052, mesh_mm=mesh, name='spine S2 twist')
        hr, fr, _ = iface('right')
        st.fix(any_of(hr, fr))
        hl, fl, _ = iface('left')
        Gc = centroid(st, any_of(hl, fl))
        st.torque(any_of(hl, fl), tuple(Gc), (1, 0, 0), 80.0)

        def twist(st, r):
            k = r.get('torsional_stiffness_nm_per_deg')
            return {'twist_deg': round(80.0 / k, 4) if k else None, 'pass_twist': bool(k and 80.0 / k <= TARGETS['twist_deg'])}
        record('S2-twist', st, False, "one leg's 80 N m roll moment (the HM budget) against the other's", twist)
    if want('S3'):
        st = Study(box, AL5052, mesh_mm=mesh, name='spine S3 pitch')
        hr, fr, _ = iface('right')
        st.fix(any_of(hr, fr))
        hl, fl, _ = iface('left')
        Gc = centroid(st, any_of(hl, fl))
        st.force(any_of(hl, fl), (600.0, 0.0, 0.0))
        st.torque(any_of(hl, fl), tuple(Gc), (0, 1, 0), 120.0, probe=False)
        record('S3-pitch', st, False, "the two motors' 60 N m caps reacted as one 120 N m couple about y, and 600 N fore-aft (the HM budget)")
    if want('D1') or want('D2'):
        deck_cases(record, mesh, want)
    if want('T1'):
        tray_case(record, mesh)
    return results


POST_SKIP_MM = 4.0    # the deck's rigid post pads: their corners are reported apart (see by_part)
LOAD_PAD_T = 1.0      # a 1 mm disc the size of the lidar's foot, bonded on the deck: the D1 hand load's patch


def deck_cases(record, mesh, want):
    """The deck on its four posts (clamped at the posts' tops), with the riser bonded on."""
    parts = bf.frame_parts()
    deck = parts['deck'].shape
    t = bp.tm()
    ris = parts['riser'].shape
    lid = bp.lidar()
    pad = bf.cyl_z(lid['d'] / 2 - 2.0, bp.TOP, bp.TOP + LOAD_PAD_T, lid['x'], 0.0)     # the lidar's foot: where a hand's push lands
    zd = bp.TOP - bp.STOCK[bp.DECK]['t']
    for x, y in bp.POSTS:              # the posts' tops as 1 mm pads under the deck: their undersides are the supports
        pad = pad.union(bf.box(x - bp.POST_W / 2, x + bp.POST_W / 2, y - bp.POST_W / 2, y + bp.POST_W / 2, zd - LOAD_PAD_T, zd))
    model = deck.union(ris).union(pad)
    plate = parts.get('turret_plate')
    # each screw joining the plates, with its clamped zone's diameter: under a riser foot the deck is sandwiched between the
    # Ø36 foot and the plate by the M5's preload (~5 kN), so the whole foot clamps; at the plate's two end nuts, the M5's own
    # zone (Ø14: the head's and the nut's cones)
    plate_screws = ([(bp.tm()['pan_x'] + a, b, 2 * bf.RISER_FOOT_R) for a, b in bf.RISER_FEET]
                    + [(x, y, PLATE_CLAMP_D) for x, y in bf.turret_plate_end_holes()])
    if plate is not None:                       # D59: the turret mount plate under the deck (two plates in bending)
        # A bolted joint, not a bond: the plate hangs PLATE_GAP_MM under the deck, joined only by a clamp pad (the
        # screw's clamped zone, Ø PLATE_CLAMP_D) at each of its six screws (the riser's four feet, its two end nuts).
        # Bonded over its whole face, its outer corners pried against the deck and their stress rose with every mesh
        # refinement (exports/body/fea/D2-convergence.json, 2026-10-28): the real plate is free to part from the deck there.
        t = bp.tm()
        model = model.union(plate.shape.translate((0, 0, -PLATE_GAP_MM)))
        for x, y, d in plate_screws:
            model = model.union(bf.cyl_z(d / 2, zd - PLATE_GAP_MM - 0.01, zd + 0.01, x, y))
    model = model.clean()

    def by_part(st, r):
        """With the plate on, each part judged by its own yield: the deck (and riser) 5052-H32's 193 MPa, the plate
        6061-T6's 276 MPa; the elements below the deck's underside are the plate's."""
        if plate is None:
            return {}
        c = st.points[st.tets].mean(axis=1)
        ok = ~st._touches_bc
        # the deck rests on rigid 22 mm pads standing in for the printed posts: the pads' corners are singular in a linear
        # model (the same as the standoffs' ends in S1), so the elements within POST_SKIP_MM of a pad's footprint are
        # reported apart and judged against the abuse target (the real post is PA6-CF and gives; its M5 is checked by hand)
        h = bp.POST_W / 2 + POST_SKIP_MM
        near = np.zeros(len(c), bool)
        for x, y in bp.POSTS:
            near |= (np.abs(c[:, 0] - x) < h) & (np.abs(c[:, 1] - y) < h)
        # the plate's six clamp pads (a bolted joint, see the model) are rigid discs bonded to both plates: their edges are
        # singular in the same way (D2's convergence run: their peak rose 155 -> 191 MPa from 3 to 2 mm). The elements within
        # POST_SKIP_MM of a pad's rim are reported apart and judged against the abuse target, like the posts' corners; the
        # screw's own bearing and the PEM's push-out are hand checks (docs/body-next-plan.md 10.6)
        clamp = np.zeros(len(c), bool)
        for x, y, d in plate_screws:
            clamp |= np.hypot(c[:, 0] - x, c[:, 1] - y) < d / 2 + POST_SKIP_MM
        vk = float(st.vm_elem[clamp & ok].max()) if (clamp & ok).any() else 0.0
        near |= clamp
        in_plate = (c[:, 2] < zd - 0.05) & ok & ~near
        in_deck = (c[:, 2] >= zd - 0.05) & ok & ~near
        vd = float(st.vm_elem[in_deck].max()) if in_deck.any() else 0.0
        at_d = [round(float(v), 1) for v in c[in_deck][int(np.argmax(st.vm_elem[in_deck]))]] if in_deck.any() else None
        vp = float(st.vm_elem[in_plate].max()) if in_plate.any() else 0.0
        vc = float(st.vm_elem[near & ok].max()) if (near & ok).any() else 0.0
        sfd, sfp = (AL5052.strength_mpa / vd if vd else None), (AL6061.strength_mpa / vp if vp else None)
        sfc = AL5052.strength_mpa / vc if vc else None
        sf = min(v for v in (sfd, sfp) if v)
        return {'deck_peak_mpa': round(vd, 1), 'deck_peak_at_mm': at_d, 'deck_sf': round(sfd, 2) if sfd else None, 'plate_peak_mpa': round(vp, 1),
                'plate_sf': round(sfp, 2) if sfp else None, 'sf_by_part': round(sf, 2),
                'post_corner_peak_mpa': round(vc, 1), 'post_corner_sf': round(sfc, 2) if sfc else None,
                'post_corner_pass': bool((sfc is None or sfc >= TARGETS['sf_fault'])
                                         and (not vk or AL5052.strength_mpa / vk >= TARGETS['sf_fault'])),
                'plate_clamp_peak_mpa': round(vk, 1), 'plate_clamp_sf': round(AL5052.strength_mpa / vk, 2) if vk else None,
                'note_by_part': 'the deck and riser at 5052-H32\'s 193 MPa, the turret plate at 6061-T6\'s 276 MPa; the deck '
                                f'within {POST_SKIP_MM:.0f} mm of a post pad (a rigid-clamp corner) reported apart, against the '
                                f'abuse target {TARGETS["sf_fault"]}'}

    def post_faces(f):
        return (f.kind == 'Plane' and abs(f.bbox[2] - (zd - LOAD_PAD_T)) < 0.05 and abs(f.bbox[5] - (zd - LOAD_PAD_T)) < 0.05
                and any(abs(f.center[0] - x) < bp.POST_W and abs(f.center[1] - y) < bp.POST_W for x, y in bp.POSTS))
    if want('D1'):
        for tag, (x, y, r) in (('front', (lid['x'], 0.0, 30.0)), ('riser', (t['pan_x'], 0.0, 50.0))):
            st = Study(model, AL5052, mesh_mm=mesh, name=f'deck D1 {tag}')
            st.fix(post_faces)
            if tag == 'front':
                sel = lambda f: (f.kind == 'Plane' and abs(f.bbox[5] - (bp.TOP + LOAD_PAD_T)) < 0.05 and abs(f.bbox[2] - (bp.TOP + LOAD_PAD_T)) < 0.05)
            else:
                sel = lambda f: f.kind == 'Plane' and abs(f.bbox[2] - (bp.TOP + bp.RISER_H)) < 0.05 and abs(f.bbox[5] - (bp.TOP + bp.RISER_H)) < 0.05
            st.force(sel, (0.0, 0.0, -300.0))

            def defl(st, r):
                d = r.get('probe_displacement_mm')
                return {'deflection_mm': round(abs(d[2]), 3) if d else None, 'pass_deflection': bool(d and abs(d[2]) <= TARGETS['deck_mm']),
                        **by_part(st, r)}
            record(f'D1-hand-{tag}', st, False, f'300 N down on the deck at the {tag} (a child leaning on it)'
                   + (', the turret plate under the riser (D59)' if plate is not None else ''), defl, view=(30, -50))
    if want('D2'):
        st = Study(model, AL5052, mesh_mm=mesh, name='deck D2 turret fall')
        st.fix(post_faces)
        tm_face = lambda f: f.kind == 'Plane' and abs(f.bbox[2] - (bp.TOP + bp.RISER_H)) < 0.05 and abs(f.bbox[5] - (bp.TOP + bp.RISER_H)) < 0.05
        m, hcom = t['mass_kg'], t['com_above_face_mm']      # the head budget (1.70 kg, 100 mm), or the turret's mount.json
        F = 30 * G * m
        Gc = force_at(st, tm_face, (F * 0.7071, 0.0, -F * 0.7071), (t['pan_x'], 0.0, bp.TOP + bp.RISER_H + hcom))
        record('D2-turret-fall', st, 'D2', f'a 30 g fall of the {m:.2f} kg head (the turret plan\'s budget) at 45 deg, its centre {hcom:.0f} mm '
               'above the TM face: a tip-over' + (', the turret plate under the riser (D59: SF >= 2.0, the everyday target)'
                                                  if plate is not None else ' (SF >= 1.2, the abuse target)'), by_part, view=(30, -50))


PLATE_GAP_MM = 0.5          # D2's model: the turret plate's face this far under the deck, away from its screws
PLATE_CLAMP_D = 14.0        # an M5's clamped zone between the plates (about 2.8 d: the head's and the nut's cone)


def body_g():
    """The body's peak load factor in a landing (g): both legs' largest vertical force at the mount plane over the
    body's own mass (the ledger's robot less its legs), plus gravity's 1 g already in it."""
    d = json.loads((R / 'exports/body/leg-loads.json').read_text())
    _, name = d['rare_body']
    F = d['scenarios'][name]['body']['peak_vertical_n']
    m = json.loads((R / 'exports/body/mass.json').read_text())['P3']
    return round(2 * F / (m['body_and_head_kg'] * G), 2)


def tray_case(record, mesh):
    """The floor tray bearing on the cheeks' upper flanges, with what stands on it at the landing's
    load factor: the compute through its four isolators, the power skid through its four posts, the DDR-120C on its
    rail, the deck, lidar and turret through the four deck posts."""
    import body_layout as bl
    parts = bf.frame_parts()
    zt = bf.ZT
    top = bp.z_tray_top()
    n_g = body_g()
    L = bl.layout()
    mass = {it.name: it.mass_g for it in L['items'] if not it.keepout}
    fm = json.loads((R / 'exports/body/body.json').read_text())['mass_g']['frame_parts']          # the frame parts' CAD masses
    part_g = lambda n: fm.get(n) or 0.0
    compute = sum(g for n, g in mass.items() if n.startswith(('j501', 'agx'))) + part_g('compute_pallet')
    skid = (sum(g for n, g in mass.items() if n.startswith('plate_') or n == 'power_dcdc') + part_g('power_plate')
            + part_g('dcdc_bracket') + 400.0)     # + its wiring; D65's TRACO stands on the plate's bracket
    deck = sum(g for n, g in mass.items() if n in ('vlp16', 'turret', 'lidar_box', 'lidar_coil')) + part_g('deck') + part_g('riser')
    supports = [('compute', compute, [(x, y, bf.ISOLATOR_D / 2) for x, y in bf.ISOLATORS]),
                ('power skid', skid, [(x, y, bf.PLATE_POST_W / 2) for x, y in bf.PLATE_STANDOFFS]),
                ('deck, lidar, turret', deck, [(x, y, bp.POST_W / 2) for x, y in bp.POSTS])]
    # (D65: the DDR-120C-24 that stood on the tray is gone; its TRACO successor is on the power plate, in the skid above)
    model = parts['floor_tray'].shape                  # each support as a 1 mm pad on the tray: its top face takes the load
    for _, _, pts in supports:
        for (x, y, r) in pts:
            model = model.union(bf.cyl_z(r, top, top + LOAD_PAD_T, x, y))
    # the tray bears on the cheeks' upper flanges (their whole width, y from the cheeks' faces to the flanges' edges, x over
    # the cheeks' length): 1 mm pads under it there, their undersides held (the screws only keep it from lifting)
    y0, y1 = bf.FACE_Y, bf.GAP_Y + bp.CHEEK_FLANGE
    for sy in (1, -1):
        model = model.union(bf.box(bp.SPINE_X[0], bp.SPINE_X[1], min(sy * y0, sy * y1), max(sy * y0, sy * y1), zt - LOAD_PAD_T, zt))
    st = Study(model.clean(), AL5052, mesh_mm=mesh, name='tray T1')
    st.fix(lambda f: f.kind == 'Plane' and abs(f.bbox[2] - (zt - LOAD_PAD_T)) < 0.05 and abs(f.bbox[5] - (zt - LOAD_PAD_T)) < 0.05)
    for name, g, pts in supports:
        for (x, y, r) in pts:
            sel = lambda f, x=x, y=y, r=r: (f.kind == 'Plane' and abs(f.bbox[5] - (top + LOAD_PAD_T)) < 0.05 and abs(f.bbox[2] - (top + LOAD_PAD_T)) < 0.05
                                            and math.hypot(f.center[0] - x, f.center[1] - y) < r)
            st.force(sel, (0.0, 0.0, -n_g * G * g / 1000.0 / len(pts)), probe=False)
    record('T1-tray', st, True, f'what stands on the floor tray at {n_g} g (the body\'s landing peak from the rig): the compute '
           f'{compute / 1000:.2f} kg on its isolators, the power skid {skid / 1000:.2f} kg on its posts, the deck with the lidar and '
           f'turret {deck / 1000:.2f} kg on the deck posts, the DDR-120C; the tray held by its screws', view=(30, -50))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mesh', type=float, default=4.0)
    ap.add_argument('--no-anim', action='store_true')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    t0 = time.time()
    res = run(a.mesh, not a.no_anim, set(a.only) if a.only else None)
    print(f'{len(res)} cases in {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
