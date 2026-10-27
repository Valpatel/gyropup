"""Springs, struts and compliance on leg v2, measured in the single-leg rig (sim/leg_rig.py).

    python -m sim.leg_spring_study [--variants none torsion_mid ...] [--scenarios stand jump60 ...]
                                   [--sweep torsion strut] [--video] [--jobs 4] [--quick]

The rig's MJCF comes from sim.leg_rig.mjcf() unchanged; this module edits the XML per variant and runs the rig's
own controller (virtual-model control, torque-speed and firmware clipping, the TPU stops as spring torques) through
the same scenarios on every variant, recorded at the simulation's full rate (0.5 ms):

  torsion   torsion springs round both hips: hinge stiffness/springref on motor_f and motor_r
  tendon    an extension spring, a coil-over or a gas strut between two anchors: a spatial tendon whose force law
            (free length, initial tension, constant force with progression, end stops, damping) is applied in the
            loop from the tendon's length and Jacobian
  tyre      a softer tyre: the tyre contact's solref
  bushing   rubber mounts between the loop's apex and the wheel: a sprung planar carrier (two slide joints)
  firmware  no hardware: the leg retracts at touchdown, or the jump is capped

Scenarios: standing at three heights (motor torque and I^2R heat), a jump at the 60 N m cap and at the full 120 N m
(height, spring energy stored and returned), drops from 25 to 300 mm (axle force; the gearbox torque and the joints'
real forces exactly as sim/leg_rig.py records them, tau_gear = tau_motor - I_rotor * alpha - b * omega and cfrc_int
at the knees, hips and apex, every step; the quasi-static J^T F kept for reference), a moving belt with a bump or a
kerb at 1 and 2 m/s (body acceleration, wheel load), and power loss with and without the motors' damping (which stop
the leg falls onto, or whether the spring holds it up, and the knee force of that collapse: the knees' governing case).

The rig's dummy half-body mass sits on a geom whose mass MuJoCo ignores (the carriage has an explicit inertial), so the
rig carries 8.5 kg instead of 11; build_xml restores it (Variant.fix_mass), and 'none_rig85' keeps the rig as it is.

Writes exports/leg/springs/results.json (+ static curves and the landing limits), sweep-<family>.json, the plots, and
with --video a few videos.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict, replace
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')
import mujoco  # noqa: E402
import numpy as np  # noqa: E402

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from sim import leg_rig as rig  # noqa: E402

fb = rig.fb
OUT = R / 'exports' / 'leg' / 'springs'
G = rig.G
DT = 0.0005
KT_OUT = 2.1                 # N m / Arms at the output (RS-04 manual 1.3.11: 40 N m at 27 Apk = 19.1 Arms)
RATED_NM = 40.0              # the manual's rated load with its 345 mm heat sink
R_PHASE = 0.16               # ohm: NOT in the RS-04 manual; a reseller sheet lists "line resistance 0.16 ohm +-10 %" (openelab.io RS04 page,
                             # checked 2026-10-27), which may be line-to-line (then 0.08 per phase). Heat is also given as a fraction of the rated loss.
ARM = rig.ARMATURE           # reflected rotor inertia per hip (estimate, see leg_rig)
HALF_MASS = getattr(rig, 'HALF_MASS', 11.0)      # 13.1 kg since the rig's ballast became a welded body (half the 26.2 kg v2 robot)
L1, L2 = fb.P['l1'] / 1000, fb.P['l2'] / 1000


# ----------------------------------------------------------------------------------- the variants

@dataclass
class Variant:
    name: str
    title: str
    kind: str = 'none'            # none | torsion | tendon | tyre | bushing | firmware
    k: float = 0.0                # torsion: N m/rad per hip; tendon spring/coil: N/m
    rest_h: float = 250.0         # mm: where the spring carries `share` of the held weight (sets the preload)
    share: float = 1.0            # fraction of the held weight the spring carries at rest_h
    anchors: tuple = ()           # tendon: ((body, (x, z) in m), (body, (x, z) in m))
    law: str = 'spring'           # tendon: spring (extension, pulls above l0) | coil (compression, pushes below l0) | gas (constant push)
    l0: float | None = None       # tendon spring/coil free length (m); fitted from rest_h/share when None
    t_init: float = 0.0           # extension spring initial tension (N)
    f0: float | None = None       # gas strut force (N) at full extension; fitted from share when None
    stroke: float = 0.20          # gas strut stroke (m): the +20 % progression; also a coil-over's travel to coil bind
    l_ext: float | None = None    # gas strut extended length (m); default: its length at 392 mm (the leg's longest)
    lost_motion: bool = True      # gas strut: a pin-in-slot lower mount, so below its stroke it carries nothing (no bottoming)
    b: float = 0.0                # tendon damping (N s/m)
    tyre: str = rig.TYRE_SOLREF
    bush_k: float = 0.0           # bushing N/m (planar), bush_b N s/m
    bush_b: float = 0.0
    added_kg: float = 0.0         # hardware mass per leg, carried by the rig
    retract: float = 0.0          # firmware: leg shortening rate at touchdown in drops (m/s)
    crouch: float = 150.0         # jump: crouch depth (mm)
    comp: bool = False            # the controller knows the spring law and cancels it (feed-forward)
    fix_mass: bool = False        # restore a lost dummy mass (see build_xml): leg_rig.py carries its ballast itself since
                                  # 2026-10-27 (a welded body), so only for comparing with the old 8.5 kg runs
    loop_solref: str | None = None   # the apex loop constraint's solref (the rig's is '0.002 1'); a check on its softness
    site_y: float = 0.015         # tendon: where the spring's layer sits (m, for the picture; the planar dynamics do not care)
    k_tol: float = 1.0            # tendon spring: the built spring's rate and initial tension relative to the ones the free
    t_tol: float = 1.0            # length was fitted with (a +-10 % check on robustness)
    notes: str = ''


AXLE = ('lower_r', (L2, 0.0))                      # the apex E in the wheel link's frame
STRUT_TOP = ('carriage', (0.0, 0.060))             # a mount on the hip frame's top flange, between the motors
LINK_PIN = 0.100                                   # m from the hip: spring pins on the upper links

VARIANTS = {
    'none': Variant('none', 'Today: no spring, the solid BotWheel tyre'),
    'torsion_mid': Variant('torsion_mid', 'Torsion springs at the hips, 3.5 N m/rad, carrying the weight at 250 mm', 'torsion', k=3.5,
                           added_kg=0.6, notes='k = the gravity curve\'s own slope at 250 mm'),
    'torsion_stiff': Variant('torsion_stiff', 'Torsion springs, 10 N m/rad, carrying the weight at 250 mm', 'torsion', k=10.0, added_kg=0.9),
    'torsion_preload': Variant('torsion_preload', 'Torsion springs, 3.5 N m/rad, preloaded to 1.5 x the weight at 250 mm', 'torsion', k=3.5,
                               share=1.5, added_kg=0.6),
    'ext_links': Variant('ext_links', 'Extension spring between pins 100 mm out on both upper links, 2.3 N/mm, the weight at 250 mm',
                         'tendon', k=2300.0, anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring',
                         t_init=10.0, added_kg=0.35),
    'ext_links_soft': Variant('ext_links_soft', 'The same spring at half the rate (1.15 N/mm), the weight at 250 mm', 'tendon', k=1150.0,
                              anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring', t_init=10.0, added_kg=0.3),
    'strut_gas': Variant('strut_gas', 'Gas strut from the hip frame down to the wheel axle, 87 N (the whole held weight), 200 mm stroke on a slot', 'tendon',
                         anchors=(STRUT_TOP, AXLE), law='gas', share=1.0, b=20.0, added_kg=0.45,
                         notes='engaged from about 190 mm leg length up; below it the rod end rides in a slot'),
    'strut_gas70': Variant('strut_gas70', 'The same gas strut at 70 % of the weight (61 N)', 'tendon', anchors=(STRUT_TOP, AXLE), law='gas',
                           share=0.7, b=20.0, added_kg=0.45),
    'strut_gas130': Variant('strut_gas130', 'The same gas strut at 130 % of the weight (113 N): preloaded', 'tendon', anchors=(STRUT_TOP, AXLE),
                            law='gas', share=1.3, b=20.0, added_kg=0.45),
    'strut_coil': Variant('strut_coil', 'Coil-over on the same line, 1.5 N/mm, the weight at 300 mm, a 150 N s/m damper, 180 mm travel', 'tendon',
                          anchors=(STRUT_TOP, AXLE), law='coil', k=1500.0, rest_h=300.0, b=150.0, added_kg=0.6, stroke=0.18),
    'tyre_pneumatic': Variant('tyre_pneumatic', 'A pneumatic-stiffness tyre (about a third of the solid tyre\'s rate)', 'tyre', tyre='0.013 0.5'),
    'tyre_foam': Variant('tyre_foam', 'A soft foam tyre (about a fifth of the solid tyre\'s rate)', 'tyre', tyre='0.018 0.4'),
    'bushing': Variant('bushing', 'Rubber mounts between the apex and the wheel, 500 N/mm planar, +-6 mm', 'bushing', bush_k=5e5, bush_b=800.0,
                       added_kg=0.15),
    'bushing_soft': Variant('bushing_soft', 'Softer rubber mounts, 150 N/mm, +-8 mm', 'bushing', bush_k=1.5e5, bush_b=400.0, added_kg=0.15),
    'fw_retract': Variant('fw_retract', 'Firmware only: the leg retracts at 0.8 m/s through touchdown', 'firmware', retract=0.8),
    'fw_retract_tyre': Variant('fw_retract_tyre', 'Retracting touchdown on the pneumatic-stiffness tyre', 'tyre', tyre='0.013 0.5', retract=0.8),
    'strut_gas_c': Variant('strut_gas_c', 'The 87 N gas strut with the controller cancelling it (firmware knows the strut)', 'tendon',
                           anchors=(STRUT_TOP, AXLE), law='gas', share=1.0, b=20.0, added_kg=0.45, comp=True),
    'ext_links_c': Variant('ext_links_c', 'The 2.3 N/mm link spring with the controller cancelling it', 'tendon', k=2300.0,
                           anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring', t_init=10.0, added_kg=0.35, comp=True),
    'strut_gas_deep': Variant('strut_gas_deep', 'The 87 N gas strut, jumping from a 120 mm crouch (pre-compress and release)', 'tendon',
                              anchors=(STRUT_TOP, AXLE), law='gas', share=1.0, b=20.0, added_kg=0.45, crouch=120.0),
    'none_deep': Variant('none_deep', 'No spring, jumping from a 120 mm crouch', crouch=120.0),
    # real McMaster parts (pages read 2026-10-27, exports/leg/springs/mcmaster/*.page.json)
    'ext_5108N807': Variant('ext_5108N807', 'McMaster 5108N807 between pins 100 mm out on the upper links: 9 in x 1 in OD, 9 lbf/in (1.58 N/mm), '
                            '6.1 lb initial tension, 67.9 lb at 15.84 in', 'tendon', k=1576.0, l0=0.2286, t_init=27.2,
                            anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring', added_kg=0.30,
                            notes='spring steel, loop ends; stretched 47 mm at 300 mm leg, 118 mm at 140 mm (max 173 mm)'),
    'strut_coil_light': Variant('strut_coil_light', 'The same coil-over without the damper (20 N s/m seal friction)', 'tendon',
                                anchors=(STRUT_TOP, AXLE), law='coil', k=1500.0, rest_h=300.0, b=20.0, added_kg=0.5, stroke=0.18),
    'none_stiffloop': Variant('none_stiffloop', 'No spring, the apex loop constraint four times stiffer (0.5 ms): a check on the knee and gearbox spikes',
                              loop_solref='0.0005 1'),
    'ext_5108N807_c': Variant('ext_5108N807_c', 'McMaster 5108N807 with the controller cancelling it (the recommended pairing)', 'tendon', k=1576.0,
                              l0=0.2286, t_init=27.2, anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring', added_kg=0.30, comp=True),
    'strut_4138T168': Variant('strut_4138T168', 'McMaster 4138T168 gas spring on the virtual leg: 20 lbf, 18.5 in extended, 7.76 in stroke, 30,000 cycles',
                              'tendon', anchors=(STRUT_TOP, AXLE), law='gas', f0=89.0, stroke=0.197, l_ext=0.470, b=20.0, added_kg=0.45,
                              notes='26 lbf at full compression (+30 %); parked in its slot below a 213 mm leg length'),
}
KNEE = (('lower_f', (0.0, 0.0)), ('lower_r', (0.0, 0.0)))        # the knee axes (the lower links' origins)
KNEE_Y = 0.099                                                      # the spring's layer: on posts beyond the knee pins' heads (y 82-91)
for _k in (1.0, 1.4, 1.6, 2.0):
    VARIANTS[f'knee_k{_k:g}'] = Variant(f'knee_k{_k:g}', f'Knee-to-knee extension spring outboard of the knees (y 88), {_k:g} N/mm, 20 N initial tension, '
                                        'the weight at 300 mm', 'tendon', k=_k * 1000, anchors=KNEE, law='spring', t_init=20.0, rest_h=300.0,
                                        added_kg=0.45, site_y=KNEE_Y)
VARIANTS['knee_5108N794_link48'] = Variant('knee_5108N794_link48', 'McMaster 5108N794 (9 in, 1 in OD, 0.115 in wire, 5.8 lbf/in, 4.9-54.3 lb, 17.51 in max) '
                                           'with a 48 mm series link, knee to knee', 'tendon', k=1020.0, anchors=KNEE, law='spring', t_init=21.8, l0=0.269,
                                           added_kg=0.40, site_y=KNEE_Y, notes='coil stretch 70 mm at 300 mm, 181 mm at 105 (max 216); 207 N at the 450 mm span')
VARIANTS['knee_5108N807_link76'] = Variant('knee_5108N807_link76', 'McMaster 5108N807 (9 in, 1 in OD, 0.125 in wire, 9 lbf/in, 6.1-67.9 lb, 15.84 in max) with a 76 mm '
                                            'series link, knee to knee', 'tendon', k=1576.0, anchors=KNEE, law='spring', t_init=27.2, l0=0.297,
                                            added_kg=0.45, site_y=KNEE_Y, notes='coil stretch 50 mm at 300 mm, 153 at 105 (max 173); 269 N at the 450 mm span')
VARIANTS['knee_2x5108N78_link135'] = Variant('knee_2x5108N78_link135', 'Two McMaster 5108N78 side by side (7 in, 1 in OD, 0.105 in wire, 5 lbf/in, 3.8-42.25 lb, '
                                             '14.73 in max) each with a 135 mm series link', 'tendon', k=1760.0, anchors=KNEE, law='spring', t_init=33.8, l0=0.3055,
                                             added_kg=0.6, site_y=KNEE_Y, notes='coil stretch 34 mm at 300 mm, 145 at 105 (max 196); 288 N at the 450 mm span')
VARIANTS['knee_k1.6_c'] = replace(VARIANTS['knee_k1.6'], name='knee_k1.6_c', title='The 1.6 N/mm knee-to-knee spring, cancelled by the controller', comp=True)
for _kt, _tt, _tag in ((0.9, 1.0, 'kminus'), (1.1, 1.0, 'kplus'), (1.0, 0.9, 'tminus'), (1.0, 1.1, 'tplus'), (0.9, 0.9, 'both_minus'), (1.1, 1.1, 'both_plus')):
    VARIANTS[f'knee_k1.6_{_tag}'] = replace(VARIANTS['knee_k1.6'], name=f'knee_k1.6_{_tag}', title=f'The 1.6 N/mm knee spring built {_tag.replace("_", " ")} 10 %',
                                            k_tol=_kt, t_tol=_tt)
KNEE_MAIN = ['none', 'knee_k1', 'knee_k1.4', 'knee_k1.6', 'knee_k2', 'knee_5108N794_link48', 'knee_5108N807_link76', 'knee_2x5108N78_link135', 'knee_k1.6_c', 'knee_k1.6_kminus', 'knee_k1.6_kplus', 'knee_k1.6_tminus', 'knee_k1.6_tplus',
             'knee_k1.6_both_minus', 'knee_k1.6_both_plus']
MAIN = ['none', 'none_stiffloop', 'torsion_mid', 'torsion_stiff', 'torsion_preload', 'ext_links', 'ext_links_soft', 'ext_5108N807',
        'ext_5108N807_c', 'ext_links_c', 'strut_gas', 'strut_gas70', 'strut_gas130', 'strut_gas_c', 'strut_4138T168', 'strut_coil', 'strut_coil_light',
        'tyre_pneumatic', 'tyre_foam', 'bushing', 'bushing_soft', 'fw_retract', 'fw_retract_tyre', 'strut_gas_deep', 'none_deep']


# ----------------------------------------------------------------------------------- statics of the five-bar

def held_weight(half_mass: float) -> float:
    """What the leg holds up (N), as the rig's gravity feed-forward: the carried mass less the wheel and half the wheel link."""
    mp = rig.mass_props()
    return (half_mass - mp['rotor'].mass - mp['wheel_link'].mass * 0.5) * G


def hold_torque(h_mm: float, F: float, lean_deg: float = 0.0):
    """Motor torques (front, rear; N m) holding a vertical ground force F at a stance: the rig's vmc mapping."""
    phi = fb.stance(h_mm, lean_deg)
    J = np.array(fb.jacobian(*phi)) / 1000.0
    return J.T @ np.array([0.0, -F]), phi


def link_point(body: str, local, phi):
    """World (x, z) in m of a point given in a link's frame (m)."""
    j = fb.fk(*phi)
    P = {k: np.array(j[k]) / 1000.0 for k in 'ABCDE'}
    if body == 'carriage':
        return np.array(local, float)
    o, a = {'upper_f': (P['A'], P['C']), 'upper_r': (P['B'], P['D']), 'lower_f': (P['C'], P['E']), 'lower_r': (P['D'], P['E'])}[body]
    ang = math.atan2(a[1] - o[1], a[0] - o[0])
    c, s = math.cos(ang), math.sin(ang)
    return o + np.array([c * local[0] - s * local[1], s * local[0] + c * local[1]])


def tendon_length(anchors, phi) -> float:
    p, q = (link_point(b, l, phi) for b, l in anchors)
    return float(np.linalg.norm(p - q))


def tendon_dl(anchors, phi, eps=1e-5):
    """d(length)/d(phi1, phi2) in m/rad."""
    out = []
    for k in range(2):
        p = list(phi)
        p[k] += eps
        a = tendon_length(anchors, p)
        p[k] -= 2 * eps
        b = tendon_length(anchors, p)
        out.append((a - b) / (2 * eps))
    return np.array(out)


def tendon_force_law(v: Variant, design: dict, l: float, dl: float = 0.0) -> float:
    """Tension (N, + pulls the anchors together) of the tendon element at length l (m) and rate dl (m/s)."""
    T = 0.0
    if v.law == 'spring':
        x = l - design['l0']
        if x > 0:
            T = v.t_init * v.t_tol + v.k * v.k_tol * x
    elif v.law == 'coil':
        x = design['l0'] - l
        if x > 0:
            T = -v.k * x
        if l < design['l0'] - v.stroke:                                # coil bind
            T -= 2e5 * (design['l0'] - v.stroke - l)
    elif v.law == 'gas':
        le, st, f0 = design['l_ext'], v.stroke, design['f0']
        if l < le - st and v.lost_motion:                              # the slot: the strut is parked, no force
            return 0.0
        comp = max(0.0, min(st, le - l))
        T = -f0 * (1.0 + 0.2 * comp / st)
        if l > le:                                                     # the rod's end stop (an extended strut pulls)
            T += 2e5 * (l - le)
        if l < le - st:                                                # bottomed out
            T -= 2e5 * (le - st - l)
    return T + v.b * dl


def tendon_energy(v: Variant, design: dict, l: float) -> float:
    if v.law == 'spring':
        x = max(0.0, l - design['l0'])
        return 0.5 * v.k * v.k_tol * x * x + v.t_init * v.t_tol * x
    if v.law == 'coil':
        x = max(0.0, design['l0'] - l)
        return 0.5 * v.k * x * x
    if v.law == 'gas':
        c = max(0.0, min(v.stroke, design['l_ext'] - l))
        return design['f0'] * (c + 0.1 * c * c / v.stroke)      # what a lost-motion strut stores stays stored while parked
    return 0.0


def design(v: Variant, half_mass: float = HALF_MASS) -> dict:
    """The spring's numbers from the variant: preload angles, free length or strut force, from the held weight."""
    F = held_weight(half_mass)
    out = {'held_n': round(F, 1)}
    rp = rig.ref_pose()
    if v.kind == 'torsion':
        tau, phi = hold_torque(v.rest_h, F)
        q = (phi[0] - rp['phi1'], phi[1] - rp['phi2'])
        # MuJoCo: tau_s = -k (q - springref); want tau_s(q_rest) = share * tau_hold
        out['springref'] = (q[0] + v.share * tau[0] / v.k, q[1] + v.share * tau[1] / v.k)
        out['preload_nm'] = tuple(round(v.share * t, 2) for t in tau)
        out['k'] = v.k
    elif v.kind == 'tendon':
        tau, phi = hold_torque(v.rest_h, F)
        l = tendon_length(v.anchors, phi)
        dl = tendon_dl(v.anchors, phi)
        need = [-tau[i] / dl[i] for i in range(2) if abs(dl[i]) > 1e-9]     # tension that would hold each motor's share
        T_rest = v.share * float(np.mean(need))
        out['l_rest'] = l
        out['t_rest'] = T_rest
        if v.law == 'spring':
            out['l0'] = v.l0 if v.l0 is not None else l - max(0.0, T_rest - v.t_init) / v.k
        elif v.law == 'coil':
            out['l0'] = v.l0 if v.l0 is not None else l + (-T_rest) / v.k
        elif v.law == 'gas':
            out['f0'] = v.f0 if v.f0 is not None else -T_rest
            phi_long = fb.stance(392.0)
            out['l_ext'] = v.l_ext if v.l_ext is not None else tendon_length(v.anchors, phi_long) + 0.002
        lens = []
        for h in (101.5, 140, 200, 250, 300, 350, 392):
            p = fb.stance(h)
            if p:
                lens.append((h, round(tendon_length(v.anchors, p) * 1000, 1)))
        out['length_mm_vs_h'] = lens
    return out


def static_curves(v: Variant, half_mass: float = HALF_MASS, heights=range(110, 395, 10)) -> dict:
    """What the spring does at every height: motor torque to hold, spring torque, residual, the spring's vertical force
    at the axle and its stiffness along the leg, and the lean torque it makes at +-15 deg (what balance has to handle)."""
    F = held_weight(half_mass)
    d = design(v, half_mass)
    rp = rig.ref_pose()
    rows = []
    for h in heights:
        phi = fb.stance(h)
        if phi is None:
            continue
        tau, _ = hold_torque(h, F)
        ts = np.zeros(2)
        if v.kind == 'torsion':
            q = np.array([phi[0] - rp['phi1'], phi[1] - rp['phi2']])
            ts = -v.k * (q - np.array(d['springref']))
        elif v.kind == 'tendon':
            l = tendon_length(v.anchors, phi)
            T = tendon_force_law(v, d, l)
            ts = -T * tendon_dl(v.anchors, phi)
        J = np.array(fb.jacobian(*phi)) / 1000.0
        Fs = np.linalg.solve(J.T, ts)             # the spring's force on the ground at the axle (x, z)
        lean = {}
        for deg in (-15.0, 15.0):
            p2 = fb.stance(h, deg)
            if p2 is None:
                continue
            ts2 = np.zeros(2)
            if v.kind == 'torsion':
                q2 = np.array([p2[0] - rp['phi1'], p2[1] - rp['phi2']])
                ts2 = -v.k * (q2 - np.array(d['springref']))
            elif v.kind == 'tendon':
                l2 = tendon_length(v.anchors, p2)
                ts2 = -tendon_force_law(v, d, l2) * tendon_dl(v.anchors, p2)
            J2 = np.array(fb.jacobian(*p2)) / 1000.0
            F2 = np.linalg.solve(J2.T, ts2)
            th = math.radians(deg)
            uth = np.array([math.cos(th), math.sin(th)])
            lean[deg] = float(F2 @ uth * h / 1000)   # N m about the hip line
        rows.append({'h_mm': h, 'tau_hold': [round(float(x), 2) for x in tau], 'tau_spring': [round(float(x), 2) for x in ts],
                     'residual': [round(float(tau[i] - ts[i]), 2) for i in range(2)], 'Fz_spring': round(float(-Fs[1]), 1),
                     'lean_nm': {str(k): round(x, 2) for k, x in lean.items()}})
    # stiffness along the leg from the spring alone (N/m), by differences of its vertical force
    for i, r in enumerate(rows):
        if 0 < i < len(rows) - 1:
            r['k_leg_n_per_m'] = round((rows[i + 1]['Fz_spring'] - rows[i - 1]['Fz_spring']) / ((rows[i + 1]['h_mm'] - rows[i - 1]['h_mm']) / 1000), 0)
    return {'design': {k: (v_ if not isinstance(v_, float) else round(v_, 4)) for k, v_ in d.items()}, 'rows': rows}


# ----------------------------------------------------------------------------------- the model, edited per variant

@dataclass
class Scenario:
    name: str
    title: str
    duration: float
    start_h: float = 300.0
    drop: float = 0.0               # mm the wheel starts above the floor
    cap: float | None = rig.LEG_CAP
    rail_low: float = 0.115
    belt: tuple | None = None       # (kind 'bump'|'kerb', height m, speed m/s, t_hit s)


DROPS = (25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0)      # mm the wheel starts above the floor, the leg holding 300 mm
# The landing scorecard (main session, from the rig's drop_150 at 1602 N on the axle, FEA and bearing checks): everything
# scales with the peak axle force. 'crooked' = that landing with +10 % fore-aft and 10 % sideways force.
#   hip gearbox: J^T F through the rotors' inertia, 143 N m straight (162 crooked) against the RS-04's 120 N m peak
#   knee eye:    114 MPa bearing pressure on the printed upper link's eye at its steel sleeve (crooked) against 40 MPa
#   knee 6201s:  2.9 kN (crooked) against their 3.1 kN static rating
# Since bc63ce9 the rig records the gearbox torque and the joints' real (dynamic) forces every step, and the strength studies
# use those: the undamped power-off collapse gives 1.8 kN at the knee (the rig's 8.5 kg), with the 6201s at static safety
# 1.15 and the knee eye at SF 1.03-1.18. The limits below are on the same measures; J^T F of the axle force (the earlier,
# quasi-static measure, which overstates landing knee loads about 2x) is kept in the scan for reference only.
RIG_COLLAPSE_KNEE_N = 1800.0
LIMITS = {
    'gearbox_120nm': {'measure': 'gear_nm', 'limit': 120.0, 'note': 'the rig\'s gearbox torque, tau_motor - I_rotor * alpha - b * omega, every step, against the RS-04\'s 120 N m peak'},
    'knee_eye_sf1': {'measure': 'knee_n', 'limit': RIG_COLLAPSE_KNEE_N * 1.03, 'note': 'the rig\'s dynamic knee force; the knee eye is at SF 1.03 at the collapse\'s 1.8 kN (upper-link strength study)'},
    'knee_6201_s0_1': {'measure': 'knee_n', 'limit': RIG_COLLAPSE_KNEE_N * 1.15, 'note': 'the same force; the 6201s are at static safety 1.15 at 1.8 kN'},
    'gearbox_120nm_jtf_reference': {'measure': 'jtf_nm', 'limit': 120.0, 'note': 'reference only: quasi-static J^T F of the axle force (hips fixed), the earlier measure'},
}

SCENARIOS = {
    'stand': Scenario('stand', 'Hold 300 mm, then 200 mm, then 140 mm (1.5 s each)', 4.5),
    'crouch110': Scenario('crouch110', 'Hold 300 mm, then crouch to 110 mm (past the knee line\'s dead point) and hold', 3.5),
    'jump60': Scenario('jump60', 'Crouch, push off at the 60 N m cap, tuck, land', 3.0),
    'jump120': Scenario('jump120', 'The same jump at the full 120 N m', 3.0, cap=None),
}
for _h in DROPS:
    SCENARIOS[f'drop{_h:g}'] = Scenario(f'drop{_h:g}', f'Dropped with the wheel {_h:g} mm off the floor, the leg holding 300 mm',
                                        round(math.sqrt(2 * _h / 1000 / G) + 0.7, 2), drop=_h)
SCENARIOS.update({
    'bump20_1': Scenario('bump20_1', 'A 20 mm bump at 1 m/s', 2.6, belt=('bump', 0.020, 1.0, 1.2)),
    'bump40_1': Scenario('bump40_1', 'A 40 mm bump at 1 m/s', 2.6, belt=('bump', 0.040, 1.0, 1.2)),
    'bump20_2': Scenario('bump20_2', 'A 20 mm bump at 2 m/s', 2.6, belt=('bump', 0.020, 2.0, 1.2)),
    'bump40_2': Scenario('bump40_2', 'A 40 mm bump at 2 m/s', 2.6, belt=('bump', 0.040, 2.0, 1.2)),
    'kerb20_1': Scenario('kerb20_1', 'Up a 20 mm kerb at 1 m/s', 2.6, belt=('kerb', 0.020, 1.0, 1.2)),
    'kerb40_1': Scenario('kerb40_1', 'Up a 40 mm kerb at 1 m/s', 2.6, belt=('kerb', 0.040, 1.0, 1.2)),
    'kerb40_2': Scenario('kerb40_2', 'Up a 40 mm kerb at 2 m/s', 2.6, belt=('kerb', 0.040, 2.0, 1.2)),
    'off': Scenario('off', 'Standing, then the motors lose power (no damping)', 3.0, rail_low=0.06),
    'off_damped': Scenario('off_damped', "Power lost, with the RS-04's assumed anti-backdrive damping", 3.0, rail_low=0.06),
})
QUICK = ['stand', 'jump60', 'drop150', 'bump40_1', 'off']
RIDE = [n for n in SCENARIOS if SCENARIOS[n].belt]
DROP_NAMES = [f'drop{h:g}' for h in DROPS]


def landing_limits(scs: dict, half_mass: float) -> dict:
    """From a variant's drop scan: the peak axle force and J^T F against touchdown speed, and for each limit the
    touchdown speed and drop (or jump) height at which it is reached, by interpolation between the drops run."""
    pts = []
    for h in DROPS:
        r = scs.get(f'drop{h:g}')
        if not r or 'impact' not in r:
            continue
        pts.append({'drop_mm': h, 'touchdown_m_s': r['touchdown']['body_speed_m_s'], 'axle_n': r['impact']['peak_axle_n'],
                    'jtf_nm': r['impact']['peak_jtf_nm'], 'gear_nm': r['impact']['peak_gear_nm'], 'knee_n': r['impact']['peak_knee_n'],
                    'knee_quasistatic_n': r['impact']['peak_knee_quasistatic_n'], 'energy_j': round(half_mass * G * h / 1000, 1),
                    'bottomed': r['rail_bottomed']})
    out = {'scan': pts, 'limits': {}}
    if len(pts) < 2:
        return out
    hs = np.array([p['drop_mm'] for p in pts])
    for name, lim in LIMITS.items():
        y = np.array([p[lim['measure']] for p in pts])
        if np.all(y < lim['limit']):
            h_lim = float('inf')
        elif y[0] >= lim['limit']:
            h_lim = 0.0
        else:
            i = int(np.argmax(y >= lim['limit']))
            h_lim = float(hs[i - 1] + (lim['limit'] - y[i - 1]) / (y[i] - y[i - 1]) * (hs[i] - hs[i - 1]))
        v_lim = math.sqrt(2 * G * h_lim / 1000) if math.isfinite(h_lim) else float('inf')
        out['limits'][name] = {'measure': lim['measure'], 'limit': round(lim['limit'], 1), 'drop_mm': round(h_lim, 1) if math.isfinite(h_lim) else None,
                               'touchdown_m_s': round(v_lim, 2) if math.isfinite(v_lim) else None,
                               'energy_j': round(half_mass * G * h_lim / 1000, 1) if math.isfinite(h_lim) else None, 'note': lim['note']}
    return out


def build_xml(v: Variant, sc: Scenario, half_mass: float, meshes: dict | None = None) -> tuple[str, dict]:
    """The rig's MJCF with this variant's elements and this scenario's belt."""
    xml, info = rig.mjcf(half_mass + v.added_kg, meshes, sc.rail_low)
    root = ET.fromstring(xml)
    d = design(v, half_mass)
    carriage = root.find('.//body[@name="carriage"]')
    if carriage.find('body[@name="ballast"]') is not None:          # the rig since the fix: the ballast is a welded body, nothing to restore
        info['carried_kg'] = round(half_mass + v.added_kg, 3)
    elif v.fix_mass:
        # leg_rig.py gives the carriage an explicit <inertial> (the hip frame) and puts the dummy half-body mass on a box geom's
        # mass attribute, which MuJoCo then ignores (geom masses only count when a body has no inertial element): the rig
        # carries 8.5 kg instead of 11. Here the dummy goes into the carriage's inertial, where it was meant to be.
        from cadagent.robot import Body, combine
        box = carriage.find('geom[@mass]')
        dummy = float(box.get('mass'))
        pos = [float(x) for x in box.get('pos').split()]
        sz = [float(x) for x in box.get('size').split()]
        full = combine([rig.mass_props()['frame'], Body(dummy, tuple(pos), name='dummy')])
        inert = ET.fromstring(rig._inertial(full))
        # the box's own inertia about its centre (a solid block), added to the combined tensor
        Ib = [dummy / 3 * (sz[1] ** 2 + sz[2] ** 2), dummy / 3 * (sz[0] ** 2 + sz[2] ** 2), dummy / 3 * (sz[0] ** 2 + sz[1] ** 2)]
        fi = [float(x) for x in inert.get('fullinertia').split()]
        fi[0] += Ib[0]; fi[1] += Ib[1]; fi[2] += Ib[2]
        inert.set('fullinertia', ' '.join(f'{x:.6g}' for x in fi))
        old = carriage.find('inertial')
        carriage.remove(old)
        carriage.insert(1, inert)
        box.set('mass', '0')
        info['carried_kg'] = round(full.mass + info['moving_kg'], 3)
    else:
        info['carried_kg'] = round(info['frame_kg'] + info['moving_kg'], 3)
    if v.kind == 'torsion':
        for jn, s in zip(('motor_f', 'motor_r'), d['springref']):
            j = root.find(f'.//joint[@name="{jn}"]')
            j.set('stiffness', f'{v.k:.4f}')
            j.set('springref', f'{s:.6f}')
    if v.kind == 'tendon':
        for i, (body, (x, z)) in enumerate(v.anchors):
            b = root.find(f'.//body[@name="{body}"]')
            ET.SubElement(b, 'site', name=f'sp{i}', pos=f'{x:.5f} {v.site_y:.4f} {z:.5f}', size='0.006', rgba='0.9 0.2 0.2 1')
        t = ET.SubElement(root, 'tendon')
        sp = ET.SubElement(t, 'spatial', name='spring', width='0.006', rgba='0.85 0.15 0.15 1')
        ET.SubElement(sp, 'site', site='sp0')
        ET.SubElement(sp, 'site', site='sp1')
    if v.kind in ('tyre', 'firmware') or v.tyre != rig.TYRE_SOLREF:
        root.find('.//geom[@name="tyre"]').set('solref', v.tyre)
    if v.loop_solref:
        root.find('.//equality/connect[@name="apex"]').set('solref', v.loop_solref)
    if v.kind == 'bushing':
        lower = root.find('.//body[@name="lower_r"]')
        wheel = lower.find('body[@name="wheel"]')
        carrier = ET.Element('body', name='axle_carrier', pos=wheel.get('pos'))
        ET.SubElement(carrier, 'joint', name='bush_x', type='slide', axis='1 0 0', stiffness=f'{v.bush_k:.1f}', damping=f'{v.bush_b:.1f}',
                      range='-0.008 0.008', solreflimit='0.002 1')
        ET.SubElement(carrier, 'joint', name='bush_z', type='slide', axis='0 0 1', stiffness=f'{v.bush_k:.1f}', damping=f'{v.bush_b:.1f}',
                      range='-0.008 0.008', solreflimit='0.002 1')
        ET.SubElement(carrier, 'inertial', pos='0 0.08 0', mass='0.15', diaginertia='1e-4 1e-4 1e-4')
        lower.remove(wheel)
        wheel.set('pos', '0 0 0')
        carrier.append(wheel)
        lower.append(carrier)
    if sc.belt:
        kind, h, speed, t_hit = sc.belt
        root.find('.//geom[@name="floor"]').set('contype', '0')
        root.find('.//geom[@name="floor"]').set('conaffinity', '0')
        wb = root.find('worldbody')
        belt = ET.SubElement(wb, 'body', name='belt', pos='0 0 -0.05')
        ET.SubElement(belt, 'joint', name='belt', type='slide', axis='1 0 0')
        ET.SubElement(belt, 'geom', name='belt_top', type='box', size='9 0.5 0.05', mass='100', rgba='0.82 0.84 0.86 1')
        x0 = speed * t_hit
        if kind == 'bump':
            ET.SubElement(belt, 'geom', name='bump', type='box', size=f'0.03 0.5 {h / 2:.4f}', pos=f'{x0:.4f} 0 {0.05 + h / 2:.4f}', rgba='0.75 0.3 0.2 1')
        else:
            ET.SubElement(belt, 'geom', name='bump', type='box', size=f'2.0 0.5 {h / 2:.4f}', pos=f'{x0 + 2.0:.4f} 0 {0.05 + h / 2:.4f}', rgba='0.75 0.3 0.2 1')
        act = root.find('actuator')
        ET.SubElement(act, 'velocity', name='belt', joint='belt', kv='50000', ctrlrange='-5 5')
    info['design'] = {k: (round(x, 5) if isinstance(x, float) else x) for k, x in d.items()}
    return ET.tostring(root, encoding='unicode'), info


# ----------------------------------------------------------------------------------- running a scenario

def command(sc: Scenario, v: Variant, t: float, state: dict):
    """(L_cmd mm, mode): mode 'pd' | 'push' | 'off'."""
    s = rig.smooth
    if sc.name == 'stand':
        if t < 1.5:
            return 300.0, 'pd'
        if t < 3.0:
            return 300 - 100 * s((t - 1.5) / 0.6), 'pd'
        return 200 - 60 * s((t - 3.0) / 0.6), 'pd'
    if sc.name == 'crouch110':
        if t < 1.0:
            return 300.0, 'pd'
        return 300 - 190 * s((t - 1.0) / 1.0), 'pd'
    if sc.name.startswith('jump'):
        if not state.get('crouched'):
            if t >= 0.6 and (state.get('L_now', 999.0) <= v.crouch + 15.0 or t >= 1.2):
                state['crouched'] = True                 # the crouch is reached (or 1.2 s is up): push
            else:
                return 300 - (300 - v.crouch) * s(t / 0.5), 'pd'
        if not state.get('pushed'):
            return None, 'push'
        return 250.0, 'pd'
    if sc.name.startswith('drop'):
        if v.retract and state.get('t_touch') is None:
            # the leg shortens at v.retract through touchdown, starting 60 mm of travel before the expected touchdown
            t_td = math.sqrt(2 * (sc.drop / 1000) / G)
            t0 = t_td - 0.06 / v.retract
            if t > t0:
                return 300 - v.retract * 1000 * (t - t0), 'pd'
        if v.retract and state.get('t_touch') is not None:
            return max(150.0, state['L_touch'] - v.retract * 1000 * min(0.15, t - state['t_touch'])), 'pd'
        return 300.0, 'pd'
    if sc.name.startswith('off'):
        return (300.0, 'pd') if t < 0.6 else (None, 'off')
    return 300.0, 'pd'


def tendon_jacobian(m, d, sites) -> tuple[float, np.ndarray, float]:
    """Length (m), d(length)/dq (nv) and rate (m/s) of the straight line between two sites, from their Jacobians
    (MuJoCo's own ten_J layout differs between versions)."""
    p0, p1 = d.site_xpos[sites[0]], d.site_xpos[sites[1]]
    u = p1 - p0
    l = float(np.linalg.norm(u))
    u = u / l
    J0, J1 = np.zeros((3, m.nv)), np.zeros((3, m.nv))
    mujoco.mj_jacSite(m, d, J0, None, sites[0])
    mujoco.mj_jacSite(m, d, J1, None, sites[1])
    Jl = u @ (J1 - J0)
    return l, Jl, float(Jl @ d.qvel)


def spring_torques(v: Variant, dsg: dict, m, d, leg, sites, phi):
    """The passive spring's equivalent torques on the two hips with the loop closed (N m: what the controller sees
    and what the statics compare), its energy (J), the tendon's length and tension, and the generalized force to
    apply (nv): the tendon's force goes on the tree's own chain and the loop constraint shares it out."""
    if v.kind == 'torsion':
        q = np.array([d.qpos[leg.q['motor_f']], d.qpos[leg.q['motor_r']]])
        ts = -v.k * (q - np.array(dsg['springref']))
        return ts, float(0.5 * v.k * np.sum((q - np.array(dsg['springref'])) ** 2)), None, 0.0, None
    if v.kind == 'tendon':
        l, Jl, dl = tendon_jacobian(m, d, sites)
        T = tendon_force_law(v, dsg, l, dl)
        ts = -T * tendon_dl(v.anchors, phi)
        return ts, tendon_energy(v, dsg, l), l, T, -T * Jl
    return np.zeros(2), 0.0, None, 0.0, None


def run(v: Variant, sc: Scenario, half_mass: float = HALF_MASS, video: Path | None = None, meshes: dict | None = None,
        xml_cache: dict | None = None, raw: bool = False) -> dict:
    key = (v.name, sc.name)
    if xml_cache is not None and key in xml_cache:
        xml, info = xml_cache[key]
    else:
        xml, info = build_xml(v, sc, half_mass, meshes)
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    leg = rig.Leg(m)
    dsg = design(v, half_mass)
    sites = (m.site('sp0').id, m.site('sp1').id) if v.kind == 'tendon' else None
    bid = m.actuator('belt').id if sc.belt else None
    if sc.drop:
        leg.set_height(d, 300.0, rail_z=(300 + sc.drop) / 1000 + rig.WHEEL_R)
    else:
        leg.set_height(d, sc.start_h)
    ff = held_weight(half_mass)
    g = rig.Gains()
    steps = int(round(sc.duration / DT))
    rec = {k: np.zeros(steps) for k in ('t', 'L', 'th', 'rail', 'vrail', 'arail', 'tau_f', 'tau_r', 'w_f', 'w_r', 'qa_f', 'qa_r', 'Fx', 'Fz',
                                         'Ax', 'Az', 'ts_f', 'ts_r', 'E_spring', 'ten_l', 'ten_T', 'stop_f', 'stop_r', 'gear_f', 'gear_r',
                                         'jtf_f', 'jtf_r', 'cmd', 'knee_f', 'knee_r', 'knee_f_qs', 'knee_r_qs', 'hip_f', 'hip_r', 'apex')}
    jb = {'knee_f': m.body('lower_f').id, 'knee_r': m.body('lower_r').id, 'hip_f': m.body('upper_f').id, 'hip_r': m.body('upper_r').id}
    state = {}
    vw = rig.VideoWriter(m, video) if video else None
    every = max(1, int(round(1 / (rig.FPS * DT))))
    rail0 = d.qpos[leg.q['rail']]
    top = rail0
    fo, fi, ro, ri = fb.stop_angles()
    dof_f, dof_r = leg.v['motor_f'], leg.v['motor_r']
    for k in range(steps):
        t = k * DT
        L, th, dL, dth, J, (x, z) = leg.polar(d)
        state['L_now'] = L * 1000
        L_cmd, mode = command(sc, v, t, state)
        fx, fz = rig.wheel_force(m, d, leg)
        contact = fz > 1.0
        if contact and state.get('t_touch') is None and (sc.drop or state.get('pushed')):
            state['t_touch'], state['L_touch'] = t, L * 1000
        ts, E_s, ten_l, ten_T, ten_qf = spring_torques(v, dsg, m, d, leg, sites, leg.phi(d))
        if mode == 'push':
            tau = rig.vmc(leg, d, None, 0.0, force=5000.0, g=g)
            if L > 0.31 or (state.get('t_push') and t - state['t_push'] > 0.35):
                state['pushed'] = True
            state.setdefault('t_push', t)
        elif mode == 'off':
            b = rig.OFF_DAMPING if sc.name == 'off_damped' else 0.0
            tau = np.array([-b * d.qvel[dof_f], -b * d.qvel[dof_r]])
        else:
            airborne = sc.name.startswith('jump') and state.get('pushed') and not contact
            gg = g if not airborne else rig.Gains(kp_L=3000, kd_L=260)
            tau = rig.vmc(leg, d, L_cmd / 1000, 0.0, ff=0.0 if airborne else ff, g=gg)
        if v.comp and mode != 'off':
            tau = tau - ts                                   # the controller cancels the known spring torque
        for i, n in enumerate(('motor_f', 'motor_r')):
            om = d.qvel[leg.v[n]]
            d.ctrl[leg.a[n]] = float(tau[i]) if mode == 'off' else rig.clip_motor(float(tau[i]), om, rig.LEG_PEAK, rig.LEG_OMEGA, sc.cap)
        d.ctrl[leg.a['wheel']] = 0.0
        if bid is not None:
            d.ctrl[bid] = -sc.belt[2]
        p1, p2 = leg.phi(d)
        d.qfrc_applied[:] = 0.0
        if ten_qf is not None:
            d.qfrc_applied[:] = ten_qf
        st_f = rig.stop_torque(p1, d.qvel[dof_f], fi, fo)
        st_r = rig.stop_torque(p2, d.qvel[dof_r], ro, ri)
        d.qfrc_applied[dof_f] += st_f
        d.qfrc_applied[dof_r] += st_r
        mujoco.mj_step(m, d)
        # the record: the state before this step's integration, its accelerations from this step
        top = max(top, d.qpos[leg.q['rail']])
        ax_, az_ = rig.axle_force(m, d, leg)
        tf, tr = float(d.actuator_force[leg.a['motor_f']]), float(d.actuator_force[leg.a['motor_r']])
        qa_f, qa_r = float(d.qacc[dof_f]), float(d.qacc[dof_r])
        jtf = J.T @ np.array([ax_, az_])
        # the joints' real forces, as sim/leg_rig.py records them: the force from the parent through each joint (cfrc_int,
        # world frame, after the same post-constraint pass as the axle force) and the apex's connect constraint; beside them
        # the quasi-static mapping of the axle force (rig.pin_forces), which the strength studies used before
        for jn, b in jb.items():
            rec[jn][k] = float(np.linalg.norm(d.cfrc_int[b][3:6]))
        fa = [d.efc_force[i] for i in range(d.nefc) if d.efc_type[i] == mujoco.mjtConstraint.mjCNSTR_EQUALITY]
        rec['apex'][k] = float(np.linalg.norm(fa)) if fa else 0.0
        pq = rig.pin_forces(p1, p2, (ax_, az_), at_axle=True)
        r = rec
        r['knee_f_qs'][k] = float(np.linalg.norm(pq['knee_front_n'])); r['knee_r_qs'][k] = float(np.linalg.norm(pq['knee_rear_n']))
        r['t'][k] = t; r['L'][k] = L * 1000; r['th'][k] = math.degrees(th); r['rail'][k] = d.qpos[leg.q['rail']] * 1000
        r['vrail'][k] = d.qvel[leg.v['rail']]; r['arail'][k] = d.qacc[leg.v['rail']]
        r['tau_f'][k] = tf; r['tau_r'][k] = tr; r['w_f'][k] = d.qvel[dof_f]; r['w_r'][k] = d.qvel[dof_r]; r['qa_f'][k] = qa_f; r['qa_r'][k] = qa_r
        r['Fx'][k] = fx; r['Fz'][k] = fz; r['Ax'][k] = ax_; r['Az'][k] = az_
        r['ts_f'][k] = ts[0]; r['ts_r'][k] = ts[1]; r['E_spring'][k] = E_s; r['ten_l'][k] = ten_l if ten_l is not None else 0.0; r['ten_T'][k] = ten_T
        r['stop_f'][k] = st_f + rig.limit_torque(d, leg.jid['motor_f']); r['stop_r'][k] = st_r + rig.limit_torque(d, leg.jid['motor_r'])
        r['gear_f'][k] = tf - m.dof_armature[dof_f] * qa_f - m.dof_damping[dof_f] * d.qvel[dof_f]     # the rig's gearbox torque
        r['gear_r'][k] = tr - m.dof_armature[dof_r] * qa_r - m.dof_damping[dof_r] * d.qvel[dof_r]
        r['jtf_f'][k] = jtf[0]; r['jtf_r'][k] = jtf[1]
        r['cmd'][k] = L_cmd if L_cmd is not None else 0.0
        if vw and k % every == 0:
            vw.frame(d)
    if vw:
        vw.close()
    res = summarise(v, sc, rec, info, state, ff)
    if sc.name.startswith('jump'):
        res['jump_height_mm'] = round((top - rail0) * 1000, 1)
    if raw:
        res['raw'] = rec
    return res


def _pk(a):
    return float(np.max(np.abs(a)))


def summarise(v: Variant, sc: Scenario, r: dict, info: dict, state: dict, ff: float) -> dict:
    t = r['t']
    out = {'variant': v.name, 'scenario': sc.name, 'title': sc.title, 'cap_nm': sc.cap, 'design': info.get('design'),
           'peak_motor_nm': round(max(_pk(r['tau_f']), _pk(r['tau_r'])), 1),
           'peak_axle_n': round(float(np.max(np.hypot(r['Ax'], r['Az']))), 1),
           'peak_wheel_n': round(float(np.max(r['Fz'])), 1),
           'peak_gear_nm': round(max(_pk(r['gear_f']), _pk(r['gear_r'])), 1),
           'peak_jtf_nm': round(max(_pk(r['jtf_f']), _pk(r['jtf_r'])), 1),
           'peak_stop_nm': round(max(_pk(r['stop_f']), _pk(r['stop_r'])), 1),
           'peak_spring_nm': round(max(_pk(r['ts_f']), _pk(r['ts_r'])), 1),
           'L_range_mm': [round(float(r['L'].min()), 1), round(float(r['L'].max()), 1)],
           'rail_bottomed': bool(r['L'].min() < sc.rail_low * 1000 + 2.0),
           # the rig's own measures (sim/leg_rig.py run()), every step
           'peak_gearbox_nm': round(max(_pk(r['gear_f']), _pk(r['gear_r'])), 1),
           'gearbox_over_peak_ms': round(float(np.sum(np.maximum(np.abs(r['gear_f']), np.abs(r['gear_r'])) > rig.LEG_PEAK)) * DT * 1000, 1),
           'peak_joint_force_n': {k: round(_pk(r[k]), 1) for k in ('knee_f', 'knee_r', 'hip_f', 'hip_r', 'apex')},
           'peak_knee_n': round(max(_pk(r['knee_f']), _pk(r['knee_r'])), 1),
           'peak_knee_quasistatic_n': round(max(_pk(r['knee_f_qs']), _pk(r['knee_r_qs'])), 1)}
    if sc.name in ('stand', 'crouch110'):
        holds = {}
        for h, (a, b) in ((('300', (1.0, 1.5)), ('200', (2.5, 3.0)), ('140', (4.0, 4.5))) if sc.name == 'stand' else (('300', (0.5, 1.0)), ('110', (3.0, 3.5)))):
            w = (t >= a) & (t < b)
            tf, tr = float(np.mean(np.abs(r['tau_f'][w]))), float(np.mean(np.abs(r['tau_r'][w])))
            I = np.array([tf, tr]) / KT_OUT
            holds[h] = {'tau_nm': [round(tf, 2), round(tr, 2)], 'I_rms_a': [round(float(x), 2) for x in I],
                        'copper_w_per_motor_at_R': [round(3 * float(x) ** 2 * R_PHASE, 2) for x in I],
                        'fraction_of_rated_loss': [round((x / RATED_NM) ** 2, 4) for x in (tf, tr)],
                        'spring_nm': [round(float(np.mean(r['ts_f'][w])), 2), round(float(np.mean(r['ts_r'][w])), 2)],
                        'L_mm': round(float(np.mean(r['L'][w])), 1)}
        out['holds'] = holds
    if sc.name.startswith('jump'):
        i_push = int(round(state.get('t_push', 0.6) / DT))
        lift = np.where((t > t[i_push]) & (r['Fz'] < 1.0))[0]
        i_lift = int(lift[0]) if len(lift) else i_push
        land = np.where((t > t[i_lift] + 0.05) & (r['Fz'] > 1.0))[0]
        out['t_push_s'] = round(float(t[i_push]), 3)
        i_land = int(land[0]) if len(land) else None
        w_push = slice(i_push, i_lift)
        motor_work = float(np.sum((r['tau_f'] * r['w_f'] + r['tau_r'] * r['w_r'])[w_push]) * DT)
        out['push'] = {'E_spring_crouch_j': round(float(r['E_spring'][i_push]), 2), 'E_spring_liftoff_j': round(float(r['E_spring'][i_lift]), 2),
                       'E_spring_returned_j': round(float(r['E_spring'][i_push] - r['E_spring'][i_lift]), 2),
                       'motor_work_j': round(motor_work, 2), 'push_s': round(float(t[i_lift] - t[i_push]), 3),
                       'liftoff_speed_m_s': round(float(r['vrail'][i_lift]), 2), 'L_liftoff_mm': round(float(r['L'][i_lift]), 1)}
        if i_land is not None:
            w = slice(i_land, min(len(t), i_land + int(0.3 / DT)))
            out['landing'] = {'touchdown_speed_m_s': round(float(-r['vrail'][i_land]), 2), 'peak_axle_n': round(float(np.max(np.hypot(r['Ax'][w], r['Az'][w]))), 1),
                              'peak_gear_nm': round(max(_pk(r['gear_f'][w]), _pk(r['gear_r'][w])), 1),
                              'peak_jtf_nm': round(max(_pk(r['jtf_f'][w]), _pk(r['jtf_r'][w])), 1), 'L_min_mm': round(float(r['L'][w].min()), 1),
                              'peak_knee_n': round(max(_pk(r['knee_f'][w]), _pk(r['knee_r'][w])), 1),
                              'peak_joint_force_n': {k: round(_pk(r[k][w]), 1) for k in ('knee_f', 'knee_r', 'hip_f', 'hip_r', 'apex')}}
    if sc.name.startswith('drop'):
        i_td = np.where(r['Fz'] > 1.0)[0]
        i_td = int(i_td[0]) if len(i_td) else 0
        out['touchdown'] = {'t_s': round(float(t[i_td]), 4), 'body_speed_m_s': round(float(-r['vrail'][i_td]), 2),
                            'wheel_speed_m_s': round(float(-r['vrail'][i_td] - (r['L'][i_td] - r['L'][max(0, i_td - 20)]) / 1000 / (20 * DT)), 2),
                            'L_mm': round(float(r['L'][i_td]), 1)}
        w = slice(i_td, min(len(t), i_td + int(0.4 / DT)))
        i_ax = i_td + int(np.argmax(np.hypot(r['Ax'][w], r['Az'][w])))
        i_g = i_td + int(np.argmax(np.maximum(np.abs(r['gear_f'][w]), np.abs(r['gear_r'][w]))))
        out['impact'] = {'peak_axle_n': round(float(np.hypot(r['Ax'][i_ax], r['Az'][i_ax])), 1), 't_peak_axle_ms': round(float(t[i_ax] - t[i_td]) * 1000, 1),
                         'peak_gear_nm': round(max(abs(r['gear_f'][i_g]), abs(r['gear_r'][i_g])), 1), 't_peak_gear_ms': round(float(t[i_g] - t[i_td]) * 1000, 1),
                         'peak_jtf_nm': round(max(_pk(r['jtf_f'][w]), _pk(r['jtf_r'][w])), 1),
                         'peak_motor_nm': round(max(_pk(r['tau_f'][w]), _pk(r['tau_r'][w])), 1),
                         'peak_knee_n': round(max(_pk(r['knee_f'][w]), _pk(r['knee_r'][w])), 1),
                         'peak_knee_quasistatic_n': round(max(_pk(r['knee_f_qs'][w]), _pk(r['knee_r_qs'][w])), 1),
                         'peak_joint_force_n': {k: round(_pk(r[k][w]), 1) for k in ('knee_f', 'knee_r', 'hip_f', 'hip_r', 'apex')},
                         'L_min_mm': round(float(r['L'][w].min()), 1), 'peak_body_g': round(float(np.max(r['arail'][w])) / G, 2),
                         'gear_over_120': bool(max(_pk(r['gear_f'][w]), _pk(r['gear_r'][w])) > 120.0)}
    if sc.belt:
        kind, h, speed, t_hit = sc.belt
        w = (t >= t_hit - 0.15) & (t < t_hit + 1.0)
        a = r['arail'][w]
        air = float(np.sum(r['Fz'][w] < 10.0) * DT)
        out['ride'] = {'peak_body_g': round(float(np.max(np.abs(a))) / G, 2), 'rms_body_g': round(float(np.sqrt(np.mean(a ** 2))) / G, 3),
                       'body_rise_mm': round(float(r['rail'][w].max() - r['rail'][w][0]), 1), 'Fz_min_n': round(float(r['Fz'][w].min()), 1),
                       'Fz_max_n': round(float(r['Fz'][w].max()), 1), 'airborne_s': round(air, 3), 'peak_gear_nm': round(max(_pk(r['gear_f'][w]), _pk(r['gear_r'][w])), 1),
                       'lean_peak_deg': round(float(np.max(np.abs(r['th'][w]))), 1), 'passed': bool(r['L'][w].min() > sc.rail_low * 1000 + 2 and air < 0.5)}
    if sc.name.startswith('off'):
        w = t > 0.6
        Lmin, Lmax = float(r['L'][w].min()), float(r['L'][w].max())
        onto = 'the knee-out stops (folded)' if Lmin < 110 else ('the knee-in stops (fully extended)' if Lmax > 385 else 'nothing: it stays up on the spring')
        out['power_off'] = {'rest_L_mm': round(float(np.mean(r['L'][-200:])), 1), 'L_min_mm': round(Lmin, 1), 'L_max_mm': round(Lmax, 1), 'falls_onto': onto,
                            'peak_stop_nm': round(max(_pk(r['stop_f'][w]), _pk(r['stop_r'][w])), 1), 'peak_axle_n': round(float(np.max(np.hypot(r['Ax'][w], r['Az'][w]))), 1),
                            'peak_knee_n': round(max(_pk(r['knee_f'][w]), _pk(r['knee_r'][w])), 1), 'peak_gearbox_nm': round(max(_pk(r['gear_f'][w]), _pk(r['gear_r'][w])), 1),
                            'peak_joint_force_n': {k: round(_pk(r[k][w]), 1) for k in ('knee_f', 'knee_r', 'hip_f', 'hip_r', 'apex')},
                            'peak_body_speed_m_s': round(float(np.max(np.abs(r['vrail'][w]))), 2), 'settled': bool(np.std(r['L'][-400:]) < 0.5)}
    dec = 10
    out['series'] = {k: [round(float(x), 3) for x in r[k][::dec]] for k in ('t', 'L', 'rail', 'tau_f', 'tau_r', 'Fz', 'Az', 'gear_f', 'gear_r', 'ts_f', 'ts_r', 'E_spring', 'arail', 'stop_f', 'stop_r', 'knee_f', 'knee_r')}
    return out


# ----------------------------------------------------------------------------------- sweeps and the driver

def sweep_family(family: str) -> list[Variant]:
    out = []
    if family == 'torsion':
        for k in (2.0, 3.5, 6.0, 10.0, 15.0):
            for share in (0.5, 0.75, 1.0, 1.25, 1.5):
                out.append(Variant(f'tor_k{k:g}_s{share:g}', f'torsion {k:g} N m/rad, {share:g} x weight at 250 mm', 'torsion', k=k, share=share, added_kg=0.6))
    elif family == 'strut':
        for k in (0.0, 0.5, 1.0, 2.0, 4.0):           # N/mm; 0 = a gas strut
            for share in (0.5, 0.75, 1.0, 1.25, 1.5):
                if k == 0.0:
                    out.append(Variant(f'strut_k0_s{share:g}', f'gas strut {share:g} x weight', 'tendon', anchors=(STRUT_TOP, AXLE), law='gas', share=share, b=20.0, added_kg=0.45))
                else:
                    out.append(Variant(f'strut_k{k:g}_s{share:g}', f'coil-over {k:g} N/mm, {share:g} x weight at 250 mm', 'tendon', anchors=(STRUT_TOP, AXLE), law='coil',
                                       k=k * 1000, share=share, rest_h=250.0, b=20.0, added_kg=0.6))
    elif family == 'knee':
        for k in (0.8, 1.0, 1.2, 1.4, 1.6, 2.0):
            for share in (0.8, 0.9, 1.0, 1.1, 1.2):
                out.append(Variant(f'knee_k{k:g}_s{share:g}', f'knee spring {k:g} N/mm, {share:g} x weight at 300 mm', 'tendon', k=k * 1000, anchors=KNEE,
                                   law='spring', share=share, rest_h=300.0, t_init=20.0, added_kg=0.45, site_y=KNEE_Y))
    elif family == 'ext':
        for k in (1.0, 1.5, 2.3, 3.5, 5.0):
            for share in (0.5, 0.75, 1.0, 1.25, 1.5):
                out.append(Variant(f'ext_k{k:g}_s{share:g}', f'link spring {k:g} N/mm, {share:g} x weight at 250 mm', 'tendon', k=k * 1000,
                                   anchors=(('upper_f', (LINK_PIN, 0.0)), ('upper_r', (LINK_PIN, 0.0))), law='spring', share=share, t_init=10.0, added_kg=0.35))
    return out


def _job(args):
    vname, scname, half_mass, xml, info, video, vdict = args
    v = Variant(**vdict)
    sc = SCENARIOS[scname]
    t0 = time.time()
    res = run(v, sc, half_mass, Path(video) if video else None, None, xml_cache={(v.name, sc.name): (xml, info)})
    res['wall_s'] = round(time.time() - t0, 1)
    return vname, scname, res


def run_matrix(variants: list[Variant], scenarios: list[str], half_mass: float, jobs: int, meshes=None, video_for=()) -> dict:
    """Every variant x scenario, the XML built here once (the CAD-derived model), the runs in worker processes."""
    import multiprocessing as mp
    work = []
    for v in variants:
        for s in scenarios:
            xml, info = build_xml(v, SCENARIOS[s], half_mass, meshes if (v.name, s) in video_for else None)
            vid = str(OUT / f'{v.name}_{s}.mp4') if (v.name, s) in video_for else None
            work.append((v.name, s, half_mass, xml, info, vid, asdict(v)))
    out = {}
    if jobs > 1:
        with mp.get_context('fork').Pool(jobs) as pool:
            for vname, scname, res in pool.imap_unordered(_job, work):
                out.setdefault(vname, {})[scname] = res
                print(f'  {vname:18} {scname:10} {_line(res)}', flush=True)
    else:
        for w in work:
            vname, scname, res = _job(w)
            out.setdefault(vname, {})[scname] = res
            print(f'  {vname:18} {scname:10} {_line(res)}', flush=True)
    return out


def _line(res: dict) -> str:
    s = f"motor {res['peak_motor_nm']:6.1f}  axle {res['peak_axle_n']:7.0f} N  gear {res['peak_gear_nm']:6.1f} N m  JtF {res['peak_jtf_nm']:6.1f}  L {res['L_range_mm']}"
    if 'jump_height_mm' in res:
        s += f"  jump {res['jump_height_mm']} mm  spring returned {res['push']['E_spring_returned_j']} J"
    if 'impact' in res:
        s += f"  impact gear {res['impact']['peak_gear_nm']} N m at {res['impact']['t_peak_gear_ms']} ms"
    if 'ride' in res:
        s += f"  body {res['ride']['peak_body_g']} g pk / {res['ride']['rms_body_g']} g rms  Fz {res['ride']['Fz_min_n']}..{res['ride']['Fz_max_n']}  air {res['ride']['airborne_s']} s"
    if 'power_off' in res:
        s += f"  rest {res['power_off']['rest_L_mm']} mm  stop {res['power_off']['peak_stop_nm']} N m"
    if 'holds' in res:
        s += '  hold ' + ' '.join(f"{h}:{v['tau_nm'][0]:.1f}/{v['tau_nm'][1]:.1f}" for h, v in res['holds'].items())
    return s + f"  ({res.get('wall_s', 0)} s)"


def table(results: dict, statics: dict) -> list[dict]:
    """One row per variant: the numbers the study compares."""
    rows = []
    for vname, scs in results.items():
        v = VARIANTS.get(vname)
        row = {'variant': vname, 'title': v.title if v else vname, 'added_kg': v.added_kg if v else None}
        st = scs.get('stand', {}).get('holds')
        if st:
            row['stand_300_nm'] = max(st['300']['tau_nm'])
            row['stand_200_nm'] = max(st['200']['tau_nm'])
            row['stand_140_nm'] = max(st['140']['tau_nm'])
            row['stand_300_w_per_motor'] = max(st['300']['copper_w_per_motor_at_R'])
            row['stand_300_frac_rated_loss'] = max(st['300']['fraction_of_rated_loss'])
        for j in ('jump60', 'jump120'):
            if j in scs:
                row[f'{j}_mm'] = scs[j].get('jump_height_mm')
                row[f'{j}_spring_j'] = scs[j]['push']['E_spring_returned_j']
                row[f'{j}_land_gear_nm'] = scs[j].get('landing', {}).get('peak_gear_nm')
        for dname in ('drop150', 'drop300'):
            if dname in scs:
                im = scs[dname]['impact']
                row[f'{dname}_axle_n'] = im['peak_axle_n']
                row[f'{dname}_gear_nm'] = im['peak_gear_nm']
                row[f'{dname}_jtf_nm'] = im['peak_jtf_nm']
                row[f'{dname}_bottomed'] = scs[dname]['rail_bottomed']
        ll = landing_limits(scs, HALF_MASS)
        for lname, lim in ll.get('limits', {}).items():
            row[f'limit_{lname}_drop_mm'] = lim['drop_mm']
            row[f'limit_{lname}_m_s'] = lim['touchdown_m_s']
        for rname in RIDE:
            if rname in scs:
                rd = scs[rname]['ride']
                row[f'{rname}_body_g'] = rd['peak_body_g']
                row[f'{rname}_rms_g'] = rd['rms_body_g']
                row[f'{rname}_Fz_min'] = rd['Fz_min_n']
                row[f'{rname}_air_s'] = rd['airborne_s']
        for oname in ('off', 'off_damped'):
            if oname in scs:
                po = scs[oname]['power_off']
                row[f'{oname}_rest_mm'] = po['rest_L_mm']
                row[f'{oname}_stop_nm'] = po['peak_stop_nm']
                row[f'{oname}_axle_n'] = po['peak_axle_n']
                row[f'{oname}_knee_n'] = po.get('peak_knee_n')
                row[f'{oname}_gearbox_nm'] = po.get('peak_gearbox_nm')
                row[f'{oname}_falls_onto'] = po.get('falls_onto')
        for dname in ('drop150', 'drop300'):
            if dname in scs:
                row[f'{dname}_knee_n'] = scs[dname]['impact'].get('peak_knee_n')
        if 'jump60' in scs and 'landing' in scs['jump60']:
            row['jump60_land_knee_n'] = scs['jump60']['landing'].get('peak_knee_n')
            row['jump60_land_gear_nm'] = scs['jump60']['landing'].get('peak_gear_nm')
        worst = max(((s_, r_['peak_knee_n']) for s_, r_ in scs.items() if 'peak_knee_n' in r_), key=lambda x: x[1], default=(None, None))
        row['worst_knee_case'], row['worst_knee_n'] = worst
        worst_g = max(((s_, r_['peak_gearbox_nm']) for s_, r_ in scs.items() if 'peak_gearbox_nm' in r_), key=lambda x: x[1], default=(None, None))
        row['worst_gearbox_case'], row['worst_gearbox_nm'] = worst_g
        s = statics.get(vname)
        if s:
            r300 = next((r for r in s['rows'] if r['h_mm'] == 300), None)
            if r300:
                row['spring_k_leg_n_per_m_300'] = r300.get('k_leg_n_per_m')
                row['spring_lean_nm_15deg_300'] = r300['lean_nm'].get('15.0')
            row['max_residual_nm_150_340'] = max(max(abs(x) for x in r['residual']) for r in s['rows'] if 150 <= r['h_mm'] <= 340)
        rows.append(row)
    return rows


def meshes_for_video() -> dict:
    """The printed parts' STL meshes in their link frames: the rig's own export when it is there, else ours."""
    folder = rig.OUT / 'rig_meshes'
    names = ('hip_frame', 'upper_link', 'front_link', 'wheel_link')
    if all((folder / f'{n}.stl').exists() for n in names):
        return {n: str(folder / f'{n}.stl') for n in names}
    return rig.export_meshes(OUT / 'meshes')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--variants', nargs='*', default=None)
    ap.add_argument('--scenarios', nargs='*', default=None)
    ap.add_argument('--sweep', nargs='*', default=[], help='families: torsion strut ext knee')
    ap.add_argument('--knee', action='store_true', help='the knee-to-knee follow-up: its variants, robustness grid and scenarios')
    ap.add_argument('--clash', action='store_true', help='3-D clash check of the knee-to-knee spring and its boot against the CAD, 105-390 mm')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--video', action='store_true', help='short videos of a few runs')
    ap.add_argument('--half-mass', type=float, default=HALF_MASS)
    ap.add_argument('--no-main', action='store_true', help='only the sweeps')
    ap.add_argument('--plots-only', action='store_true')
    ap.add_argument('--tag', default='', help='suffix for results-<tag>.json, sweep-<family>-<tag>.json and the figures (a separate run)')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.plots_only:
        plots(OUT, a.tag)
        return
    if a.clash:
        knee_spring_clash()
        return
    t0 = time.time()
    rig.mass_props()
    print(f'model from the CAD in {time.time() - t0:.0f} s; held weight {held_weight(a.half_mass):.1f} N', flush=True)
    sfx = f'-{a.tag}' if a.tag else ''
    results_path = OUT / f'results{sfx}.json'
    prev = json.loads(results_path.read_text()) if results_path.exists() else {}
    if not a.no_main:
        names = a.variants or (KNEE_MAIN if a.knee else (['none', 'torsion_mid', 'strut_gas', 'tyre_pneumatic', 'fw_retract'] if a.quick else MAIN))
        variants = [VARIANTS[n] for n in names]
        scen = a.scenarios or (['stand', 'crouch110', 'jump60', 'jump120', 'drop150', 'drop300', 'bump20_1', 'bump40_1', 'kerb40_2', 'off', 'off_damped'] if a.knee
                               else (QUICK if a.quick else list(SCENARIOS)))
        statics = dict(prev.get('static', {}))
        for v in variants:
            statics[v.name] = static_curves(v, a.half_mass)
            print(f"{v.name:18} {v.title}\n{'':18} design {json.dumps(statics[v.name]['design'])}", flush=True)
        video_for = set()
        meshes = None
        if a.video:
            meshes = meshes_for_video()
            video_for = {('none', 'jump60'), ('ext_5108N807_c', 'jump60'), ('none', 'drop150'), ('tyre_pneumatic', 'drop150'), ('none', 'off'),
                         ('ext_5108N807', 'off'), ('none', 'bump40_2'), ('tyre_pneumatic', 'bump40_2')}
            video_for = {(vn, s) for vn, s in video_for if vn in names and s in scen}
        res = run_matrix(variants, scen, a.half_mass, a.jobs, meshes, video_for)
        merged = dict(prev.get('scenarios', {}))
        for vn, scs in res.items():
            merged.setdefault(vn, {}).update(scs)
        rows = table(merged, statics)
        out = {'half_mass_kg': a.half_mass, 'held_n': round(held_weight(a.half_mass), 1),
               'model': {'armature_kg_m2': ARM, 'kt_out_nm_per_arms': KT_OUT, 'r_phase_ohm_assumed': R_PHASE, 'rated_nm': RATED_NM, 'dt_s': DT,
                         'leg_cap_nm': rig.LEG_CAP, 'leg_peak_nm': rig.LEG_PEAK},
               'limits': LIMITS, 'landing': {vn: landing_limits(scs, a.half_mass) for vn, scs in merged.items()},
               'variants': {n: asdict(VARIANTS[n]) for n in merged if n in VARIANTS}, 'static': statics, 'table': rows, 'scenarios': merged}
        results_path.write_text(json.dumps(out, indent=1) + '\n')
        print(f'wrote {results_path} ({time.time() - t0:.0f} s)', flush=True)
    for fam in a.sweep:
        variants = sweep_family(fam)
        scen = ['stand', 'jump60', 'drop150', 'off', 'off_damped', 'bump40_1']
        statics = {v.name: static_curves(v, a.half_mass) for v in variants}
        res = run_matrix(variants, scen, a.half_mass, a.jobs)
        rows = []
        for v in variants:
            scs = res[v.name]
            st = scs['stand']['holds']
            rows.append({'variant': v.name, 'k': v.k, 'share': v.share, 'design': scs['stand']['design'],
                         'stand_300_nm': max(st['300']['tau_nm']), 'stand_200_nm': max(st['200']['tau_nm']), 'stand_140_nm': max(st['140']['tau_nm']),
                         'max_residual_nm_150_340': max(max(abs(x) for x in r['residual']) for r in statics[v.name]['rows'] if 150 <= r['h_mm'] <= 340),
                         'jump60_mm': scs['jump60']['jump_height_mm'], 'jump60_spring_j': scs['jump60']['push']['E_spring_returned_j'],
                         'jump60_land_gear_nm': scs['jump60'].get('landing', {}).get('peak_gear_nm'),
                         'drop150_axle_n': scs['drop150']['impact']['peak_axle_n'], 'drop150_gear_nm': scs['drop150']['impact']['peak_gear_nm'],
                         'off_rest_mm': scs['off_damped']['power_off']['rest_L_mm'], 'off_stop_nm': scs['off_damped']['power_off']['peak_stop_nm'],
                         'off_axle_n': scs['off_damped']['power_off']['peak_axle_n'],
                         'collapse_knee_n': scs['off']['power_off']['peak_knee_n'], 'collapse_stop_nm': scs['off']['power_off']['peak_stop_nm'],
                         'collapse_falls_onto': scs['off']['power_off']['falls_onto'],
                         'drop150_knee_n': scs['drop150']['impact']['peak_knee_n'],
                         'bump40_1_body_g': scs['bump40_1']['ride']['peak_body_g'], 'bump40_1_rms_g': scs['bump40_1']['ride']['rms_body_g'],
                         'k_leg_300': next((r.get('k_leg_n_per_m') for r in statics[v.name]['rows'] if r['h_mm'] == 300), None)})
        (OUT / f'sweep-{fam}{sfx}.json').write_text(json.dumps({'family': fam, 'rows': rows, 'scenarios': {v.name: {s: {k: x for k, x in r.items() if k != 'series'} for s, r in res[v.name].items()} for v in variants}}, indent=1) + '\n')
        print(f'wrote sweep-{fam}{sfx}.json ({time.time() - t0:.0f} s)', flush=True)
    try:
        plots(OUT, a.tag)
    except Exception as exc:                          # plots are a convenience; the numbers are in the JSON
        print(f'plots skipped: {exc!r}')


# ----------------------------------------------------------------------------------- figures

# categorical slots in a fixed order (the dataviz reference palette, validated for adjacent pairs), one per variant family
PAL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
SEQ = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#2a78d6', '#1c5cab', '#104281', '#0d366b']
INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
FAMILY_COLOUR = {'none': PAL[0], 'none_rig85': PAL[0], 'torsion': PAL[1], 'ext': PAL[2], 'strut': PAL[3], 'tyre': PAL[4], 'bushing': PAL[5], 'fw': PAL[6]}


def _family(name: str) -> str:
    for key in ('none_rig85', 'none', 'torsion', 'ext', 'strut', 'tyre', 'bushing', 'fw'):
        if name.startswith(key):
            return key
    return 'none'


def _style(ax, title: str, xlabel: str = '', ylabel: str = ''):
    ax.set_facecolor(SURF)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, axis='y', color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=10, loc='left')
    ax.set_xlabel(xlabel, color=INK2, fontsize=8)
    ax.set_ylabel(ylabel, color=INK2, fontsize=8)


def _bars(ax, names, values, title, ylabel, limit=None, fmt='{:.0f}'):
    cols = [FAMILY_COLOUR[_family(n)] for n in names]
    x = np.arange(len(names))
    vals = [0.0 if v is None else float(v) for v in values]
    ax.bar(x, vals, color=cols, width=0.62)
    for i, v in enumerate(vals):
        ax.text(i, v, fmt.format(v), ha='center', va='bottom', fontsize=7, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=50, ha='right', fontsize=7, color=INK2)
    if limit is not None:
        ax.axhline(limit[0], color='#e34948', linewidth=1.2, linestyle='--')
        ax.text(len(names) - 0.5, limit[0], limit[1], ha='right', va='bottom', fontsize=7, color='#e34948')
    _style(ax, title, '', ylabel)


def plots(out: Path, tag: str = ''):
    """The study's figures from results.json and the sweeps: the static spring curves, the scorecard bars, the
    drop scan against the landing limits, the impact time series, the ride, and the sweep maps."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 8, 'figure.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK})
    sfx = f'-{tag}' if tag else ''
    res = json.loads((out / f'results{sfx}.json').read_text())
    scs, statics, landing = res['scenarios'], res['static'], res['landing']
    rows = {r['variant']: r for r in res['table']}
    names = [n for n in (MAIN + KNEE_MAIN) if n in scs]
    names = list(dict.fromkeys(names))

    # 1. what each spring does at every height: hold torque, spring torque, residual; its leg stiffness
    fig, axs = plt.subplots(1, 3, figsize=(13, 4))
    picks = [n for n in ('torsion_mid', 'torsion_stiff', 'ext_links', 'ext_5108N807', 'strut_gas', 'strut_4138T168', 'knee_k1.6', 'knee_5108N807_link76',
                         'knee_2x5108N78_link135', 'knee_k1') if n in statics][:7]
    base = statics.get('none') or next(iter(statics.values()))
    h = [r['h_mm'] for r in base['rows']]
    axs[0].plot(h, [abs(r['tau_hold'][0]) for r in base['rows']], color=INK, linewidth=2, label='to hold the weight')
    for i, n in enumerate(picks):
        axs[0].plot(h, [abs(r['tau_spring'][0]) for r in statics[n]['rows']], color=PAL[(i + 1) % 8], linewidth=1.6, label=n)
        axs[1].plot(h, [r['residual'][0] for r in statics[n]['rows']], color=PAL[(i + 1) % 8], linewidth=1.6, label=n)
        axs[2].plot(h, [r['Fz_spring'] for r in statics[n]['rows']], color=PAL[(i + 1) % 8], linewidth=1.6, label=n)
    axs[1].axhline(0, color=GRID)
    axs[2].axhline(res['held_n'], color=INK, linewidth=1, linestyle='--')
    axs[2].text(h[-1], res['held_n'], 'held weight', ha='right', va='bottom', fontsize=7, color=INK2)
    _style(axs[0], 'Front hip torque to hold the leg, and what each spring gives', 'leg length (mm)', 'N m')
    _style(axs[1], 'Left for the motor (hold minus spring)', 'leg length (mm)', 'N m')
    _style(axs[2], "The spring's vertical force at the axle", 'leg length (mm)', 'N')
    axs[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out / f'static-curves{sfx}.png', dpi=130)
    plt.close(fig)

    # 2. the scorecard: standing torque, jump height, landing loads, power-off
    fig, axs = plt.subplots(3, 3, figsize=(16, 12))
    _bars(axs[0, 0], names, [rows[n].get('stand_300_nm') for n in names], 'Standing at 300 mm: motor torque', 'N m per motor', fmt='{:.1f}')
    _bars(axs[0, 1], names, [rows[n].get('jump60_mm') for n in names], 'Jump at the 60 N m cap', 'mm')
    _bars(axs[0, 2], names, [rows[n].get('jump120_mm') for n in names], 'Jump at 120 N m', 'mm')
    _bars(axs[1, 0], names, [rows[n].get('drop150_axle_n') for n in names], 'Drop 150 mm: peak axle force', 'N')
    _bars(axs[1, 1], names, [rows[n].get('drop150_gear_nm') for n in names], 'Drop 150 mm: gearbox torque', 'N m', limit=(120, 'RS-04 peak'))
    _bars(axs[1, 2], names, [rows[n].get('drop150_knee_n') for n in names], 'Drop 150 mm: knee force (dynamic)', 'N',
          limit=(LIMITS['knee_eye_sf1']['limit'], 'knee eye SF 1'))
    _bars(axs[2, 0], names, [rows[n].get('off_rest_mm') for n in names], 'Power off, undamped: where the leg comes to rest', 'mm')
    _bars(axs[2, 1], names, [rows[n].get('off_knee_n') for n in names], 'Power off, undamped: knee force in the collapse', 'N',
          limit=(LIMITS['knee_eye_sf1']['limit'], 'knee eye SF 1'))
    _bars(axs[2, 2], names, [rows[n].get('off_stop_nm') for n in names], 'Power off, undamped: stop torque', 'N m')
    fig.tight_layout()
    fig.savefig(out / f'scorecard{sfx}.png', dpi=130)
    plt.close(fig)

    # 3. the drop scan: axle force, J^T F and dynamic gearbox torque against touchdown speed, with the limits
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.2))
    picks = [n for n in ('none', 'tyre_pneumatic', 'tyre_foam', 'bushing_soft', 'fw_retract', 'fw_retract_tyre', 'strut_gas', 'knee_k1.6', 'knee_5108N807_link76') if n in landing]
    for i, n in enumerate(picks):
        sc = landing[n]['scan']
        v = [p['touchdown_m_s'] for p in sc]
        axs[0].plot(v, [p['axle_n'] for p in sc], marker='o', markersize=4, linewidth=1.6, color=PAL[i % 8], label=n)
        axs[1].plot(v, [p['gear_nm'] for p in sc], marker='o', markersize=4, linewidth=1.6, color=PAL[i % 8], label=n)
        axs[2].plot(v, [p['knee_n'] for p in sc], marker='o', markersize=4, linewidth=1.6, color=PAL[i % 8], label=n)
    for ax, key, lab in ((axs[1], 'gearbox_120nm', 'RS-04 120 N m'), (axs[2], 'knee_eye_sf1', 'knee eye SF 1 (collapse 1.8 kN x 1.03)'),
                         (axs[2], 'knee_6201_s0_1', '6201 s0 = 1')):
        ax.axhline(LIMITS[key]['limit'], color='#e34948', linewidth=1.2, linestyle='--')
        ax.text(0.05, LIMITS[key]['limit'], lab, fontsize=7, color='#e34948', va='bottom')
    _style(axs[0], 'Peak axle force at touchdown', 'touchdown speed (m/s)', 'N')
    _style(axs[1], "Torque through the gearbox (the rig's measure)", 'touchdown speed (m/s)', 'N m')
    _style(axs[2], "Knee force (the rig's dynamic measure)", 'touchdown speed (m/s)', 'N')
    axs[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out / f'drop-scan{sfx}.png', dpi=130)
    plt.close(fig)

    # 4. the impact itself, 150 mm drop: force and gearbox torque in the first 40 ms
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    picks = [n for n in ('none', 'tyre_pneumatic', 'bushing_soft', 'fw_retract', 'strut_gas') if n in scs and 'drop150' in scs[n]]
    for i, n in enumerate(picks):
        s = scs[n]['drop150']['series']
        t0 = scs[n]['drop150']['touchdown']['t_s']
        t = [(x - t0) * 1000 for x in s['t']]
        w = [j for j, x in enumerate(t) if -5 <= x <= 60]
        axs[0].plot([t[j] for j in w], [s['Az'][j] for j in w], color=PAL[i % 8], linewidth=1.6, label=n)
        axs[1].plot([t[j] for j in w], [abs(s['gear_r'][j]) for j in w], color=PAL[i % 8], linewidth=1.6, label=n)
    _style(axs[0], 'Vertical axle force after touchdown (150 mm drop, 5 ms samples)', 'ms after touchdown', 'N')
    _style(axs[1], 'Rear hip gearbox torque', 'ms after touchdown', 'N m')
    axs[0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out / f'impact-150{sfx}.png', dpi=130)
    plt.close(fig)

    # 5. the ride: body acceleration over bumps and kerbs
    ride = [r for r in RIDE if any(r in scs[n] for n in names)]
    if ride:
        fig, axs = plt.subplots(1, 2, figsize=(13, 4.2))
        picks = [n for n in ('none', 'torsion_mid', 'ext_links', 'ext_links_c', 'strut_gas', 'strut_gas_c', 'tyre_pneumatic', 'bushing_soft') if n in scs]
        x = np.arange(len(ride))
        wdt = 0.8 / max(1, len(picks))
        for i, n in enumerate(picks):
            pk = [scs[n].get(r, {}).get('ride', {}).get('peak_body_g', 0) for r in ride]
            rm = [scs[n].get(r, {}).get('ride', {}).get('rms_body_g', 0) for r in ride]
            axs[0].bar(x + (i - len(picks) / 2 + 0.5) * wdt, pk, width=wdt * 0.9, color=PAL[i % 8], label=n)
            axs[1].bar(x + (i - len(picks) / 2 + 0.5) * wdt, rm, width=wdt * 0.9, color=PAL[i % 8], label=n)
        for ax in axs:
            ax.set_xticks(x)
            ax.set_xticklabels(ride, fontsize=7, color=INK2)
        _style(axs[0], 'Peak body acceleration over the obstacle', '', 'g')
        _style(axs[1], 'RMS body acceleration, 1.15 s window', '', 'g')
        axs[0].legend(fontsize=7, frameon=False, ncol=2)
        fig.tight_layout()
        fig.savefig(out / f'ride{sfx}.png', dpi=130)
        plt.close(fig)

    # 6. the sweeps: rate x preload maps
    for fam in ('torsion', 'strut', 'ext', 'knee'):
        f = out / f'sweep-{fam}{sfx}.json'
        if not f.exists():
            continue
        sw = json.loads(f.read_text())['rows']
        ks = sorted({r['k'] for r in sw})
        ss = sorted({r['share'] for r in sw})
        fields = [('stand_300_nm', 'standing torque at 300 mm (N m)'), ('max_residual_nm_150_340', 'worst motor torque left, 150-340 mm (N m)'),
                  ('jump60_mm', 'jump at 60 N m (mm)'), ('collapse_knee_n', 'undamped power-off collapse: knee force (N)'), ('off_rest_mm', 'power-off rest length, damped (mm)'),
                  ('bump40_1_body_g', '40 mm bump at 1 m/s: peak body g')]
        fig, axs = plt.subplots(2, 3, figsize=(14, 8))
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list('seq', SEQ)
        for ax, (key, title) in zip(axs.flat, fields):
            grid = np.full((len(ss), len(ks)), np.nan)
            for r in sw:
                v = r.get(key)
                if v is not None:
                    grid[ss.index(r['share']), ks.index(r['k'])] = v
            im = ax.imshow(grid, origin='lower', cmap=cmap, aspect='auto')
            for i in range(len(ss)):
                for j in range(len(ks)):
                    if not np.isnan(grid[i, j]):
                        ax.text(j, i, f'{grid[i, j]:.0f}' if abs(grid[i, j]) >= 10 else f'{grid[i, j]:.1f}', ha='center', va='center', fontsize=7,
                                color=INK if grid[i, j] < np.nanmax(grid) * 0.6 + np.nanmin(grid) * 0.4 else SURF)
            ax.set_xticks(range(len(ks)))
            ax.set_xticklabels([f'{k:g}' for k in ks], fontsize=7)
            ax.set_yticks(range(len(ss)))
            ax.set_yticklabels([f'{s:g}' for s in ss], fontsize=7)
            unit = {'torsion': 'N m/rad', 'strut': 'N/m (0 = gas strut)', 'ext': 'N/m', 'knee': 'N/m'}[fam]
            _style(ax, title, f'rate ({unit})', 'preload (x held weight at 250 mm)')
            ax.grid(False)
        fig.suptitle(f'{fam} family sweep', color=INK, fontsize=11, x=0.02, ha='left')
        fig.tight_layout()
        fig.savefig(out / f'sweep-{fam}{sfx}.png', dpi=130)
        plt.close(fig)


# ----------------------------------------------------------------------------------- the knee-to-knee spring in 3-D

def knee_spring_clash(y_c: float = KNEE_Y * 1000, d_coil: float = 25.4, d_boot: float = 32.0, hook: float = 12.0,
                      heights=(105, 110, 115, 120, 130, 150, 180, 210, 250, 300, 330, 360, 375, 390)) -> dict:
    """Where a knee-to-knee spring (a coil of d_coil, in a boot of d_boot, centred at y_c mm on the knee axes, its loops
    reaching `hook` mm past each knee axis) runs into the leg's own parts (cad/fivebar.py assembly at each leg length),
    and its clearance over the tyre. Writes exports/leg/springs/knee-spring-clash.json and a figure."""
    import cadquery as cq
    gmi = fb.gmi
    real = gmi.STEP_FRAMES.pop(fb.MOTOR, None)              # the motors as envelopes (the vendor model is slow to intersect)
    fb.motor_model.cache_clear()
    out = {'y_centre_mm': y_c, 'coil_od_mm': d_coil, 'boot_od_mm': d_boot, 'hook_mm': hook, 'heights': {}}
    anchors = ('knee_pin', 'knee_washer', 'knee_nut', 'knee_spacer', 'knee_6201')     # the anchors themselves
    try:
        for h in heights:
            phi = fb.stance(h)
            j = fb.fk(*phi)
            C, D, E = j['C'], j['D'], j['E']
            span = math.hypot(C[0] - D[0], C[1] - D[1])
            ang = math.degrees(math.atan2(C[1] - D[1], C[0] - D[0]))
            mid = ((C[0] + D[0]) / 2, (C[1] + D[1]) / 2)
            envs = {}
            for name, d in (('coil', d_coil), ('boot', d_boot)):
                L = span + 2 * hook
                cyl = cq.Workplane('YZ', origin=(-L / 2, 0, 0)).circle(d / 2).extrude(L)      # along +x, centred
                envs[name] = cyl.rotate((0, 0, 0), (0, 1, 0), -ang).translate((mid[0], y_c, mid[1]))
            asm = fb.assembly(*phi, with_bought=True)
            hits = {'coil': [], 'boot': []}
            for pname, (shape, kind) in asm.items():
                if shape is None or pname.startswith(anchors) or pname == 'wheel_cable':
                    continue
                for ename, env in envs.items():
                    try:
                        vol = env.intersect(shape).val().Volume()
                    except Exception:
                        vol = 0.0
                    if vol > 5.0:
                        hits[ename].append([pname, round(vol)])
            tyre_top = E[1] + rig.WHEEL_R * 1000
            tyre_y = fb.Y['tyre']
            overlap_y = max(0.0, min(tyre_y[1], y_c + d_boot / 2) - max(tyre_y[0], y_c - d_boot / 2))
            gap = (min(C[1], D[1]) - d_boot / 2) - tyre_top
            out['heights'][str(h)] = {'span_mm': round(span, 1), 'knee_z_mm': round(C[1], 1), 'tyre_top_z_mm': round(tyre_top, 1),
                                      'boot_to_tyre_gap_mm': round(gap, 1), 'boot_tyre_y_overlap_mm': round(overlap_y, 1),
                                      'coil_hits': hits['coil'], 'boot_hits': hits['boot']}
            print(f"{h:4d} mm: span {span:6.1f}  boot-tyre gap {gap:6.1f} mm  coil hits {hits['coil']}  boot hits {hits['boot']}", flush=True)
    finally:
        if real:
            gmi.STEP_FRAMES[fb.MOTOR] = real
        fb.motor_model.cache_clear()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'knee-spring-clash.json').write_text(json.dumps(out, indent=1) + '\n')
    # the picture: the leg's links, the tyre and the spring envelope in the leg's plane at four lengths, and the layers
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 5, figsize=(18, 4.2))
    for ax, h in zip(axs[:4], (105, 150, 300, 390)):
        phi = fb.stance(h)
        j = fb.fk(*phi)
        for a, b in (('A', 'C'), ('C', 'E'), ('B', 'D'), ('D', 'E')):
            ax.plot([j[a][0], j[b][0]], [j[a][1], j[b][1]], color=INK, linewidth=3, solid_capstyle='round')
        ax.add_patch(plt.Circle(j['E'], rig.WHEEL_R * 1000, fill=False, color=PAL[0], linewidth=1.5))
        for (px, pz) in fb.stop_posts():
            ax.add_patch(plt.Circle((px, pz), 9, color=INK2, fill=False))
        C, D = j['C'], j['D']
        ux, uz = (C[0] - D[0]), (C[1] - D[1])
        n = math.hypot(ux, uz)
        nx, nz = -uz / n * d_boot / 2, ux / n * d_boot / 2
        ax.fill([D[0] + nx, C[0] + nx, C[0] - nx, D[0] - nx], [D[1] + nz, C[1] + nz, C[1] - nz, D[1] - nz], color=PAL[1], alpha=0.5, label='spring + boot')
        ax.set_aspect('equal')
        ax.set_xlim(-280, 280)
        ax.set_ylim(-480, 110)
        _style(ax, f'leg {h} mm: knees {math.hypot(ux, uz):.0f} mm apart', 'x (mm)', 'z (mm)')
    ax = axs[4]
    ty = fb.Y['tyre']
    for name, (y0, y1), col in (('upper links', fb.Y['upper'], INK2), ('front link', fb.Y['front_link'], INK2), ('wheel link', fb.Y['wheel_link'], INK2),
                                ('knee pin head', (fb.Y['knee_boss'][1] + 2, fb.Y['knee_boss'][1] + 11), INK), ('tyre', ty, PAL[0])):
        ax.barh(name, y1 - y0, left=y0, color=col, height=0.6)
    ax.barh('spring + boot', d_boot, left=y_c - d_boot / 2, color=PAL[1], height=0.6)
    _style(ax, 'the layers along y (mm, outwards)', 'y (mm)', '')
    ax.grid(True, axis='x', color=GRID)
    fig.tight_layout()
    fig.savefig(OUT / 'knee-spring-layout.png', dpi=130)
    return out


if __name__ == '__main__':
    main()
