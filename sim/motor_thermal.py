"""The RS-04 leg motors' thermal model (issue #194): their losses, how the heat reaches the hip frame, the body and the
air, and which hip frame keeps them cool enough.

    .venv/bin/python sim/motor_thermal.py           # -> exports/leg/thermal/motor_thermal.json and docs/motor-thermal.md
    python3 sim/motor_thermal.py --check            # recompute from the JSON's recorded loads (no CAD): exit 1 if stale

Pattern as cad/body_thermal.py: one script writes generated JSON (and here the page that reads it); regenerate, never
edit. The thermal core is the standard library only, so the check and the tests run anywhere; only `loads()` reads the
CAD (cad/fivebar.py) and the rig (sim/leg_rig.py, exports/leg/rig-results.json), and the JSON records what it found.

The network, per motor (a lumped thermal-RC model):

    winding --R_wc-- case --contact-- hip frame (layers through the web, or a plate) --flanges / posts-- body frame
                      |  \\--rear cover, 2 mm air gap or a gap pad, to the cheek-------------------------/      |
                      +-- air (natural convection + radiation)                    air <-- frame faces    air <-+

It is calibrated on the RS-04's own ratings: the winding reaches the firmware's 145 C limit at 40 N m on a 345 x 345 mm
aluminium plate and at 35.5 N m on 220 x 200 mm (two equations: the winding-to-case resistance and the test plate's
emissivity), and on the manual's overload table (the winding's heat capacity).

Every input names its source: 'manual' (RS04 User Manual 260713, the RobStride repository; a local reference copy,
not committed: references/vendor/robstride-rs-04/SOURCE.txt), 'spec book' (RobStride's RS-series specification book of
2026-10-09, the RS04 pages, same repository), 'owner' (a measurement by the owner, dated), 'CAD' (this repository),
'catalog' (catalog/materials.json), 'textbook' (a named correlation), or 'assumed' (an engineering estimate, with the
range the sensitivity table sweeps; replace it with a bench measurement, section 'acceptance').
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'leg' / 'thermal' / 'motor_thermal.json'
DOC = R / 'docs' / 'motor-thermal.md'
SIGMA = 5.670374e-8
ZERO_C = 273.15
G0 = 9.81

# ------------------------------------------------------------------------------------------------------------- inputs
# One dict; each entry {'v': value, 'src': where it comes from, optional 'range': (lo, hi) for the sensitivity table}.
INPUTS = {
    # the motor (RobStride RS-04)
    'kt_nm_per_arms': {'v': 2.1, 'src': 'manual 1.3 item 11 and spec book: torque constant at the output, N m per A rms'},
    'r_line_ohm': {'v': 0.16, 'range': (0.144, 0.176),
                   'src': 'spec book RS04 page: line (phase-to-phase) resistance 0.16 ohm +-10 %; taken at 25 C (the book '
                          'states no temperature: assumed)'},
    'alpha_cu_per_k': {'v': 0.00393, 'src': 'textbook: annealed copper, +0.393 %/K'},
    'i_noload_arms': {'v': 0.7, 'range': (0.7, 2.0),
                      'src': 'spec book: no-load current 0.7 A rms at 200 rpm (the manual says 2 A rms: the range); '
                             'drag torque = kt x I0 at any speed (friction + iron)'},
    'p_standby_w': {'v': 2.0, 'src': 'manual 2.1: standby <= 40 mA at 48 V (1.9 W); the driver\'s own idle loss'},
    'r_driver_ohm': {'v': 0.004, 'range': (0.002, 0.008),
                     'src': 'assumed: the drive stage\'s conduction, 4 mohm per phase leg (3 x I^2 x R)'},
    'winding_limit_c': {'v': 145.0, 'src': 'manual 1.3 item 13: the firmware\'s calculated winding limit ("the '
                                           'constraint temperature; the actual temperature is 180 C"); its thermistor fault is also 145'},
    'winding_target_c': {'v': 120.0, 'src': 'this model\'s margin: 10 K under insulation Class B (130 C, manual 1.2 item 11), '
                                            '25 K under the firmware\'s 145 C cut'},
    'stall_rated_nm': {'v': 28.5, 'src': 'manual 1.3 item 14: the stall table\'s rated (continuous) row; the firmware\'s '
                                         'locked-rotor protection (fault bit 14) trips sooner than the heat alone (section 2)'},
    'stall_factor': {'v': 2.0, 'range': (1.414, 2.0),
                     'src': 'a held motor\'s hottest phase carries the peak current, I_pk^2 = 2 I_rms^2; the manual\'s text '
                            'says 1.414, its stall table (40 / 28.5)^2 = 1.97: 2.0 taken'},
    'mass_kg': {'v': 1.51, 'src': 'owner 2026-11-03: four boxed motors 7 kg, about 1.51 kg each with leads; the spec book\'s '
                                  '1510 +- 20 g (the manual says 1420). Not a ledger change'},
    'c_mix_j_per_kgk': {'v': 632.0, 'range': (550.0, 720.0),
                        'src': 'assumed mix: 40 % aluminium (900), 45 % steel (470), 10 % copper (385), 5 % magnets (450)'},
    'eps_case': {'v': 0.8, 'range': (0.3, 0.9), 'src': 'assumed: an anodised or painted housing'},
    'can_air_factor': {'v': 1.0, 'src': 'a multiplier on the case\'s convection and radiation: 1 until the bench fit '
                                        '(--fit) measures it'},
    'od_m': {'v': 0.120, 'src': 'manual 1.1 drawing: housing O120'},
    'body_len_m': {'v': 0.039, 'src': 'manual 1.1 drawing: body 39 mm'},
    'rear_cover_d_m': {'v': 0.094, 'src': 'manual 1.1 drawing: rear cover O94 x 13.2'},
    'rear_cover_len_m': {'v': 0.0132, 'src': 'manual 1.1 drawing'},
    'face_bore_d_m': {'v': 0.0786, 'src': 'CAD: the hip frame\'s 61812 bore (O78 + 0.6), inside the motor\'s face annulus'},
    'face_bolts': {'v': 10, 'src': 'CAD / manual: 10 x M4 on O106 (clearance O4.5 each)'},
    # the manufacturer's ratings (the calibration)
    'rating_a': {'v': {'tau': 40.0, 'rpm': 50.0, 'plate_m': (0.345, 0.345)},
                 'src': 'spec book: rated 40 N m measured at 50 rpm on a 345 x 345 mm aluminium plate (manual 1.2: '
                        'GB/T 30549-2014, 25 C ambient; the manual says 100 rpm)'},
    'rating_b': {'v': {'tau': 35.5, 'rpm': 40.0, 'plate_m': (0.220, 0.200)},
                 'src': 'spec book: the thermal-equilibrium T-N table on a 220 x 200 mm aluminium plate, 35.5 N m at 40 rpm'},
    'rating_b_curve': {'v': [(30.1, 150.0), (31.8, 115.0), (32.45, 80.0), (30.0, 191.0)],
                       'src': 'spec book: the rest of that table (validation, not fitted)'},
    'overload_table': {'v': [(120, 3), (115, 9), (110, 10), (105, 13), (100, 15), (90, 24), (80, 38), (70, 61), (60, 108),
                             (50, 324)],
                       'src': 'manual 1.3 item 13: N m and seconds to the limit at 50 rpm, 345 x 345 plate, 25 C (from cold: '
                              'assumed). Rows >= 115 N m are the drive\'s peak-current timer, not heat: not fitted'},
    'stall_table': {'v': [(120, 1), (110, 1), (100, 1.5), (90, 3), (80, 6), (70, 10), (60, 33), (50, 74), (40, 130)],
                    'src': 'manual 1.3 item 14: stalled, N m and seconds to the protection'},
    'test_plate_t_m': {'v': 0.008, 'range': (0.006, 0.015),
                       'src': 'assumed: the test plates\' thickness (GB/T 30549-2014 not read)'},
    'h_contact_metal': {'v': 2000.0, 'range': (1000.0, 5000.0),
                        'src': 'assumed: dry bolted aluminium faces, light pressure (Madhusudana, Thermal Contact '
                               'Conductance: 1-5 kW/m2K)'},
    'h_contact_polymer': {'v': 1000.0, 'range': (500.0, 3000.0),
                          'src': 'assumed: a printed face on the motor\'s machined face under 10 x M4'},
    # materials
    'pla': {'v': {'k': 0.13, 'rho': 1240.0, 'cp': 1800.0, 'eps': 0.9, 'face_limit_c': 50.0, 'service_c': 54.0},
            'src': 'catalog pla (density, max service 54 C); k 0.13 W/mK and cp assumed (printed PLA 0.12-0.20); the '
                   'face limit 50 C is the owner\'s (PLA softens at about 55-60 C)'},
    'pa6cf': {'v': {'k': 0.4, 'rho': 1090.0, 'cp': 1500.0, 'eps': 0.9, 'face_limit_c': 80.0, 'service_c': 164.0},
              'src': 'catalog pa6-cf (density, max service 164 C); k 0.4 W/mK assumed (printed CF nylon 0.25-0.8); face '
                     'limit 80 C assumed: the bolted, preloaded joint creeps long before the HDT'},
    'al6061': {'v': {'k': 167.0, 'rho': 2700.0, 'cp': 896.0, 'eps': 0.1}, 'src': 'textbook 6061-T6; eps 0.1 bare (mill) assumed'},
    'al5052': {'v': {'k': 138.0, 'rho': 2680.0, 'cp': 900.0, 'eps': 0.1}, 'src': 'textbook 5052-H32; eps 0.1 bare assumed'},
    'gap_pad': {'v': {'k': 3.0, 't': 0.002}, 'range': (1.5, 6.0),
                'src': 'assumed: a 2.5 mm silicone gap pad of 3 W/mK compressed to the 2.0 mm gap (k swept 1.5-6)'},
    'k_air': {'v': 0.027, 'src': 'textbook: air at about 40 C, W/mK'},
    # the leg and the body (CAD; checked against cad/fivebar.py by the test when CadQuery is present)
    'web_t_m': {'v': 0.0241, 'src': 'CAD fivebar.Y[\'frame\']: the hip frame\'s web, y -25.1..-1.0'},
    'flange_len_m': {'v': 0.0572, 'src': 'CAD: web (y -25.1) to the mount plane (fivebar.Y[\'centre_plane\'] -82.3)'},
    'flange_x_m': {'v': 0.095, 'src': 'CAD fivebar.FLANGE_X: each flange 190 mm long, half of it per motor'},
    'flange_t_m': {'v': (0.013, 0.018), 'src': 'CAD fivebar.HIP: top 13, bottom 18 mm'},
    'rear_gap_m': {'v': 0.002, 'src': 'CAD: the rear cover (y -80.3) to the cheek\'s or the stand\'s face (y -82.3)'},
    'rear_overlap_m2': {'v': 0.00503, 'src': 'CAD: the O94 rear cover face where the cheek (x <= 92) is behind it, the '
                                             'motor at x 75 (a circle minus its segment beyond the chord at 17 mm)'},
    'can_side_exposed': {'v': {'printed': 0.5, 'plate': 0.85}, 'range': (0.3, 0.9),
                         'src': 'assumed: the share of the O120 side in free air; a printed frame\'s flanges cover its top '
                                'and bottom 3.5 mm away, a flat plate leaves it open'},
    'web_leg_face_m2': {'v': 0.0110, 'src': 'CAD (approximate): per motor, the web\'s leg-side face from the hub\'s O80 to '
                                            'the frame\'s half outline (95 x 158 mm), less the stop bosses'},
    'plate': {'v': {'t': 0.00635, 'w': 0.190, 'h': 0.158, 'posts': 6, 'post_d': 0.016, 'post_hole_d': 0.0055},
              'src': 'option C, assumed: a SendCutSend 1/4 in 6061-T6 plate the web\'s outline (190 x 158 mm), the motors on '
                     'its inner face, held off the cheek by six O16 6061 spacers 57.2 mm long at the frame\'s six M5 '
                     'positions (x 0, +-83; z +-70) on through M5 screws'},
    'plate_black': {'v': {'eps': 0.85, 'spacer_k': 0.3},
                    'src': 'option E, assumed: black anodising eps 0.85 (textbook 0.8-0.9); the six spacers G10/FR4 '
                           '(k 0.3 W/mK through the laminate) instead of aluminium, a thermal break to the cheek'},
    'body_parts_kg': {'v': {'cheeks': 0.984, 'floor_tray': 0.753, 'belly_plate': 0.247},
                      'src': 'CAD docs/body-sections.md: 2 x 492 g cheeks (5052 3/16 in), the tray 753 g (5052 1/8 in), the '
                             'belly 247 g (6061 0.100 in)'},
    'body_surfaces': {'v': [('cheek faces, open share', 'vert', 0.181, 4 * 0.184 * 0.181 * 0.35),
                            ('tray underside, open share', 'down', 0.320 * 0.254 / (2 * (0.320 + 0.254)), 0.320 * 0.254 * 0.6),
                            ('belly top, open share', 'up', 0.320 * 0.116 / (2 * (0.320 + 0.116)), 0.320 * 0.116 * 0.3)],
                      'src': 'CAD dimensions (docs/body-frame.md; length: a vertical face\'s height, a horizontal one\'s area / perimeter, Incropera 9.30-9.32); the open shares (35 %, 60 %, 30 %) assumed: the motors '
                             'and frames cover the cheeks\' outer faces, the gap between them is 31 mm and closed, the '
                             'battery bay hangs under the belly'},
    'tray_top_m2': {'v': 0.320 * 0.254 * 0.7, 'L_m': 0.320 * 0.254 / (2 * (0.320 + 0.254)),
                    'src': 'CAD: the tray\'s top in the body\'s air (70 % open: the pallet, the power plate on posts)'},
    'body_air': {'v': {'rise_k': 2.59, 'mcp_w_per_k': 6.84, 'budget_k': 3.0},
                 'src': 'exports/body/thermal/hand_model.json (cad/body_thermal.py, P1 deck): the cooler\'s inlet 2.59 K over '
                        'the room at 21.1 m3/h (m cp 6.84 W/K); D61\'s budget 3 K'},
    'ambient_c': {'v': 25.0, 'src': 'the manual\'s standard 25 C'},
    'ambient_hot_c': {'v': 35.0, 'src': 'assumed: a warm day (the RS-04 allows -20..50 C)'},
    'drive_fx_g': {'v': 0.25, 'range': (0.1, 0.4),
                   'src': 'assumed: driving and balancing as a fore-aft force at the tyre of 0.25 g rms of the leg\'s load'},
    'jump_period_s': {'v': 10.0, 'src': 'the owner\'s case: a jump every 10 s'},
}


def v(key):
    return INPUTS[key]['v']


# ------------------------------------------------------------------------------------------ heat transfer (textbook)
def air_props(t_film_c):
    """Dry air at 1 atm, linear fits over 0-150 C (Incropera, Table A.4): k W/mK, nu m2/s, Pr, beta 1/K."""
    k = 0.0241 + 7.6e-5 * t_film_c
    nu = 1.33e-5 + 9.0e-8 * t_film_c
    return k, nu, 0.71, 1.0 / (t_film_c + ZERO_C)


def rayleigh(length, dt, t_film_c):
    k, nu, pr, beta = air_props(t_film_c)
    return G0 * beta * max(abs(dt), 1e-3) * length ** 3 / nu ** 2 * pr, k, pr


def h_vertical(height, t_s, t_a):
    """Churchill & Chu (1975), a vertical plate, all Ra: W/m2K."""
    ra, k, pr = rayleigh(height, t_s - t_a, (t_s + t_a) / 2)
    nu = (0.825 + 0.387 * ra ** (1 / 6) / (1 + (0.492 / pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return nu * k / height


def h_cylinder(d, t_s, t_a):
    """Churchill & Chu (1975), a long horizontal cylinder: W/m2K."""
    ra, k, pr = rayleigh(d, t_s - t_a, (t_s + t_a) / 2)
    nu = (0.60 + 0.387 * ra ** (1 / 6) / (1 + (0.559 / pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return nu * k / d


def h_horizontal(length, t_s, t_a, facing):
    """A horizontal plate (Incropera 9.30-9.32, L = area / perimeter): 'up' is the hot face up (0.54 / 0.15 Ra^n),
    'down' the hot face down (0.27 Ra^1/4, the weak one)."""
    ra, k, pr = rayleigh(length, t_s - t_a, (t_s + t_a) / 2)
    if facing == 'up':
        nu = 0.54 * ra ** 0.25 if ra < 1e7 else 0.15 * ra ** (1 / 3)
    else:
        nu = 0.27 * ra ** 0.25
    return nu * k / length


def h_radiation(eps, t_s, t_a):
    """Linearised grey radiation to surroundings at the air's temperature: W/m2K."""
    a, b = t_s + ZERO_C, t_a + ZERO_C
    return eps * SIGMA * (a * a + b * b) * (a + b)


def spreading_resistance(k, t, a_source, a_plate, h_eff):
    """Song, Lee & Au (1994): a centred source on a finite plate cooled on its far face with h_eff, K/W: the
    spreading AND the 1D conduction t / (k A_plate) (psi contains it: a source as large as the plate gives exactly
    t / (k A)), not the film. As cad-agent's cadagent.thermal.heatsink.PlateFin._spread (v0.18.1), copied: gyropup's CI
    does not install cad-agent (whose resistance() adds t / (k A) a second time: negligible for thin bases)."""
    a, b = math.sqrt(a_source / math.pi), math.sqrt(a_plate / math.pi)
    eps, tau = a / b, t / b
    bi = h_eff * b / k
    lam = math.pi + 1 / (math.sqrt(math.pi) * eps)
    phi = (math.tanh(lam * tau) + lam / bi) / (1 + lam / bi * math.tanh(lam * tau))
    psi = eps * tau / math.sqrt(math.pi) + (1 - eps) * phi / math.sqrt(math.pi)
    return psi / (k * a * math.sqrt(math.pi))


def plate_to_air(k, t, a_source, w, h, t_p, t_a, eps, faces=2.0, exposed=1.0):
    """Source (centred) to air through a vertical plate w x h cooled on `faces` faces (exposed share of each):
    spreading + 1D + film, K/W."""
    hp = h_vertical(h, t_p, t_a) + h_radiation(eps, t_p, t_a)
    ap = w * h
    h_eff = faces * exposed * hp
    return spreading_resistance(k, t, a_source, ap, h_eff) + 1 / (h_eff * ap)


# ------------------------------------------------------------------------------------------------------ the losses
def r_line(t_w):
    return v('r_line_ohm') * (1 + v('alpha_cu_per_k') * (t_w - 25.0))


def current_arms(tau):
    return abs(tau) / v('kt_nm_per_arms')


def copper_loss(tau, t_w):
    """3 I^2 R_phase = 1.5 I^2 R_line, R_line at the winding's temperature (W)."""
    i = current_arms(tau)
    return 1.5 * i * i * r_line(t_w)


def drag_loss(rpm):
    """The no-load loss at the output speed: kt x I0 x omega (friction and iron), W."""
    return v('kt_nm_per_arms') * v('i_noload_arms') * abs(rpm) * 2 * math.pi / 60


def driver_loss(tau):
    i = current_arms(tau)
    return v('p_standby_w') + 3 * i * i * v('r_driver_ohm')


# --------------------------------------------------------------------------------------------- the network solver
class Network:
    """Nodes with heat capacities; links with conductances that may depend on the temperatures (convection); sources
    that may too (copper). Node 'amb' is fixed. Steady: fixed point; transient: backward Euler, conductances and
    sources taken at the step's start."""

    def __init__(self, t_amb):
        self.names, self.cap, self.links, self.src, self.fixed = [], [], [], [], {'amb': t_amb}
        self.init = {}                                  # nodes that do not start at the ambient (the hot-spot excess)

    def node(self, name, cap):
        self.names.append(name)
        self.cap.append(cap)
        return name

    def link(self, a, b, g):
        """g: a number (W/K) or a function of the temperature dict."""
        self.links.append((a, b, g if callable(g) else (lambda T, g=g: g)))

    def source(self, name, p):
        self.src.append((name, p if callable(p) else (lambda T, p=p: p)))

    def _system(self, T, extra_diag=None, extra_rhs=None):
        n = len(self.names)
        idx = {k: i for i, k in enumerate(self.names)}
        A = [[0.0] * n for _ in range(n)]
        b = [0.0] * n
        for a_, b_, g in self.links:
            gv = g(T)
            for p, q in ((a_, b_), (b_, a_)):
                if p in idx:
                    A[idx[p]][idx[p]] += gv
                    if q in idx:
                        A[idx[p]][idx[q]] -= gv
                    else:
                        b[idx[p]] += gv * self.fixed[q]
        for name, p in self.src:
            b[idx[name]] += p(T)
        if extra_diag:
            for i in range(n):
                A[i][i] += extra_diag[i]
                b[i] += extra_rhs[i]
        return A, b

    @staticmethod
    def solve(A, b):
        n = len(b)
        M = [row[:] + [b[i]] for i, row in enumerate(A)]
        for c in range(n):
            p = max(range(c, n), key=lambda r: abs(M[r][c]))
            M[c], M[p] = M[p], M[c]
            for r in range(c + 1, n):
                f = M[r][c] / M[c][c]
                if f:
                    for k in range(c, n + 1):
                        M[r][k] -= f * M[c][k]
        x = [0.0] * n
        for r in range(n - 1, -1, -1):
            x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
        return x

    def temps(self, x):
        T = dict(zip(self.names, x))
        T.update(self.fixed)
        return T

    def steady(self, guess=60.0):
        x = [guess] * len(self.names)
        for _ in range(400):
            T = self.temps(x)
            A, b = self._system(T)
            y = self.solve(A, b)
            if max(abs(p - q) for p, q in zip(x, y)) < 1e-7:
                return self.temps(y)
            x = [0.5 * p + 0.5 * q for p, q in zip(x, y)]
        raise RuntimeError('steady state did not converge')

    def start(self, t0=None):
        x0 = t0 if t0 is not None else self.fixed['amb']
        return [self.init.get(n, x0) for n in self.names]

    def step(self, x, dt):
        """One backward-Euler step of dt s from the node temperatures x (a list in self.names order)."""
        d = [c / dt for c in self.cap]
        A, b = self._system(self.temps(x), d, [c * xi for c, xi in zip(d, x)])
        return self.solve(A, b)

    def transient(self, t_end, dt, t0=None, stop=None, record=None):
        """From every node at t0 (the ambient) to t_end s. stop(T) -> True ends it; record: sample times (s)."""
        x = self.start(t0)
        t, out, rec = 0.0, None, sorted(record or [])
        samples = {}
        while t < t_end - 1e-9:
            x = self.step(x, dt)
            t += dt
            T = self.temps(x)
            while rec and rec[0] <= t + 1e-9:
                samples[rec.pop(0)] = dict(T)
            if stop and stop(T):
                out = t
                break
        return {'t_stop': out, 'T': self.temps(x), 'samples': samples, 't': t}


# --------------------------------------------------------------------------------------------- the motor's pieces
def can_areas():
    od, L = v('od_m'), v('body_len_m')
    dr, Lr = v('rear_cover_d_m'), v('rear_cover_len_m')
    a_face = math.pi / 4 * (od ** 2 - v('face_bore_d_m') ** 2) - v('face_bolts') * math.pi / 4 * 0.0045 ** 2
    return {'side': math.pi * od * L, 'rear_side': math.pi * dr * Lr, 'shoulder': math.pi / 4 * (od ** 2 - dr ** 2),
            'rear_face': math.pi / 4 * dr ** 2, 'mount_face': a_face}


def motor_caps(c_w):
    c_total = v('mass_kg') * v('c_mix_j_per_kgk')
    return c_w, c_total - c_w


def add_motor(net, cal, P, stall_f=1.0, exposure=1.0, rear_free=True):
    """The winding and case nodes, their losses and the case's own convection. P: dict tau (N m), rpm. The winding
    node is the firmware's per-phase estimate: a held motor's hottest phase runs (f - 1) x P_cu x R_wc above the mean
    at steady state (the hot-spot excess; a node of the winding's capacity, coupled to nothing else)."""
    c_w, c_c = motor_caps(cal['c_w'])
    net.node('W', c_w)
    net.node('C', c_c)
    net.node('X', c_w)                        # the hot-spot excess over W, referenced to 0 (see hot())
    net.fixed['zero'] = 0.0
    net.init['X'] = 0.0
    r_wc = cal['r_wc']
    net.link('W', 'C', 1 / r_wc)
    net.link('X', 'zero', 1 / r_wc)
    net.source('W', lambda T: copper_loss(P['tau'], T['W'] + T['X']))   # (the excess's copper is second order)
    net.source('X', lambda T: (stall_f - 1) * copper_loss(P['tau'], T['W']))
    net.source('C', lambda T: drag_loss(P['rpm']) + driver_loss(P['tau']))
    ar = can_areas()
    od, eps = v('od_m'), v('eps_case')

    def g_can(T):
        tc, ta = T['C'], T['amb']
        h_side = h_cylinder(od, tc, ta) + h_radiation(eps, tc, ta)
        h_face = h_vertical(v('rear_cover_d_m'), tc, ta) + h_radiation(eps, tc, ta)
        a = exposure * ar['side'] + ar['rear_side'] + 0.5 * ar['shoulder']
        a_face = ar['rear_face'] if rear_free else ar['rear_face'] - v('rear_overlap_m2')
        return v('can_air_factor') * (h_side * a + h_face * a_face)
    net.link('C', 'amb', g_can)
    return net


def hot(T):
    return T['W'] + T['X']


# ------------------------------------------------------------------------------------- the manufacturer's test rig
def test_rig(cal, tau, rpm, plate_m, eps_plate, stall_f=1.0, t_amb=25.0):
    """The RS-04 on an aluminium plate (its rating test): the face bolted on (metal contact), the plate vertical and
    cooled on both faces, the motor otherwise in free air."""
    net = Network(t_amb)
    add_motor(net, cal, {'tau': tau, 'rpm': rpm}, stall_f=stall_f, exposure=1.0)
    w, h = plate_m
    t = cal.get('t_plate', v('test_plate_t_m'))
    al = v('al6061')
    net.node('P', w * h * t * al['rho'] * al['cp'])
    a_face = can_areas()['mount_face']
    hc = v('h_contact_metal')

    def g_cp(T):
        hp = h_vertical(h, T['P'], T['amb']) + h_radiation(eps_plate, T['P'], T['amb'])
        r = 1 / (hc * a_face) + spreading_resistance(al['k'], t, a_face, w * h, 2 * hp)
        return 1 / r
    net.link('C', 'P', g_cp)
    net.link('P', 'amb', lambda T: 2 * w * h * (h_vertical(h, T['P'], T['amb']) + h_radiation(eps_plate, T['P'], T['amb']))
             - a_face * (h_vertical(h, T['P'], T['amb'])))      # the face under the motor is covered on one side
    return net


def bisect(f, lo, hi, n=60):
    flo = f(lo)
    for _ in range(n):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def calibrate(t_plate=None, eps_fixed=None):
    """Fit R_wc and the test plates' emissivity to the two continuous ratings (the winding at 145 C in both), then C_w
    to the overload table (50-110 N m, least squares in log time). Returns the fit and its residuals."""
    lim = v('winding_limit_c')
    ra, rb = v('rating_a'), v('rating_b')
    base = {'c_w': 80.0, 't_plate': t_plate or v('test_plate_t_m')}

    def r_wc_for(eps):
        def f(r):
            T = test_rig(dict(base, r_wc=r), ra['tau'], ra['rpm'], ra['plate_m'], eps).steady()
            return hot(T) - lim
        return bisect(f, 0.01, 3.0, 50)

    def err_b(eps):
        r = r_wc_for(eps)
        T = test_rig(dict(base, r_wc=r), rb['tau'], rb['rpm'], rb['plate_m'], eps).steady()
        return hot(T) - lim
    lo_e, hi_e = 0.05, 0.95
    e_lo, e_hi = (0.0, 0.0) if eps_fixed else (err_b(lo_e), err_b(hi_e))
    if eps_fixed:
        eps, bound = eps_fixed, f'emissivity fixed at {eps_fixed}: R_wc from the first rating alone'
    elif (e_lo > 0) != (e_hi > 0):
        eps = bisect(err_b, lo_e, hi_e, 30)
        bound = None
    else:
        eps = lo_e if abs(e_lo) < abs(e_hi) else hi_e
        bound = 'emissivity at its bound: the two ratings are not met together'
    r_wc = r_wc_for(eps)
    cal = dict(base, r_wc=r_wc, eps_plate=eps)
    Ta = test_rig(cal, ra['tau'], ra['rpm'], ra['plate_m'], eps).steady()
    Tb = test_rig(cal, rb['tau'], rb['rpm'], rb['plate_m'], eps).steady()

    rows = [(t, s) for t, s in v('overload_table') if t <= 110]

    def time_to_limit(c, tau, rpm, stall_f=1.0, t_max=4000.0):
        net = test_rig(dict(cal, c_w=c), tau, rpm, ra['plate_m'], eps, stall_f=stall_f)
        dt = 0.1 if tau >= 70 else 0.5
        r = net.transient(t_max, dt, stop=lambda T: hot(T) >= lim)
        return r['t_stop']

    def sse(c):
        e = 0.0
        for tau, s in rows:
            t = time_to_limit(c, tau, ra['rpm']) or 4000.0
            e += math.log(t / s) ** 2
        return e / len(rows)
    a, b = 30.0, 250.0                         # golden section on C_w
    g = (math.sqrt(5) - 1) / 2
    c1, c2 = b - g * (b - a), a + g * (b - a)
    f1, f2 = sse(c1), sse(c2)
    for _ in range(14):
        if f1 < f2:
            b, c2, f2 = c2, c1, f1
            c1 = b - g * (b - a)
            f1 = sse(c1)
        else:
            a, c1, f1 = c1, c2, f2
            c2 = a + g * (b - a)
            f2 = sse(c2)
    c_w = round((a + b) / 2, 1)
    cal['c_w'] = c_w
    overload = [{'tau_nm': tau, 'manual_s': s, 'model_s': round(time_to_limit(c_w, tau, ra['rpm']) or float('inf'), 1),
                 'fitted': tau <= 110} for tau, s in v('overload_table')]
    stall = [{'tau_nm': tau, 'manual_s': s,
              'model_s': (lambda x: round(x, 1) if x else None)(time_to_limit(c_w, tau, 0.0, v('stall_factor'), 3000.0))}
             for tau, s in v('stall_table')]
    t_rated_stall = test_rig(cal, v('stall_rated_nm'), 0.0, ra['plate_m'], eps, stall_f=v('stall_factor')).steady()
    curve = []
    for tau, rpm in v('rating_b_curve'):
        T = test_rig(cal, tau, rpm, rb['plate_m'], eps).steady()
        curve.append({'tau_nm': tau, 'rpm': rpm, 'model_winding_c': round(hot(T), 1)})
    return {'r_wc_k_per_w': round(r_wc, 4), 'eps_test_plate': round(eps, 3), 'c_w_j_per_k': c_w,
            'c_case_j_per_k': round(motor_caps(c_w)[1], 1), 't_test_plate_m': cal['t_plate'], 'bound': bound,
            'rating_a': {'winding_c': round(hot(Ta), 2), 'case_c': round(Ta['C'], 1), 'plate_c': round(Ta['P'], 1),
                         'loss_w': round(copper_loss(ra['tau'], Ta['W']) + drag_loss(ra['rpm']) + driver_loss(ra['tau']), 1)},
            'rating_b': {'winding_c': round(hot(Tb), 2), 'case_c': round(Tb['C'], 1), 'plate_c': round(Tb['P'], 1),
                         'loss_w': round(copper_loss(rb['tau'], Tb['W']) + drag_loss(rb['rpm']) + driver_loss(rb['tau']), 1)},
            'rating_b_curve': curve, 'overload': overload, 'stall': stall,
            'stall_rated_model_winding_c': round(hot(t_rated_stall), 1),
            'overload_rms_log_error': round(math.sqrt(sse(c_w)), 3)}


def cal_of(c):
    return {'r_wc': c['r_wc_k_per_w'], 'c_w': c['c_w_j_per_k'], 't_plate': c['t_test_plate_m'], 'eps_plate': c['eps_test_plate']}


# ----------------------------------------------------------------------------------------------- the leg's options
OPTIONS = {
    'A_pla': 'A. Printed PLA hip frame (the bench build): 24.1 mm web, flanges to the cheek',
    'B_pa6cf': 'B. Printed PA6-CF hip frame (the current design), as A',
    'C_al_plate': 'C. Flat 1/4 in 6061-T6 plate in the frame\'s place, on six O16 6061 spacers to the 5052 cheek',
    'D_pa6cf_pad': 'D. PA6-CF frame as B, plus a 3 W/mK gap pad from each rear cover to the cheek (2.0 mm gap)',
    'E_al_plate_black_iso': 'E. The 6061 plate of C, black anodised (eps 0.85), on G10 spacers: its heat to the open air, '
                            'not into the body',
}


def add_body(net, n_motors, t_amb):
    """The body frame's aluminium (cheeks, tray, belly) as one node; this motor's share is 1 / n_motors of it (every
    motor alike). Its open faces to the room; the tray's top to the body's air (the room + the cooler's inlet rise)."""
    m = v('body_parts_kg')
    c = sum(m.values()) * v('al5052')['cp'] / n_motors
    net.node('B', c)
    eps = v('al5052')['eps']

    def g(T):
        tb, ta = T['B'], T['amb']
        tot = 0.0
        for _, kind, L, a in v('body_surfaces'):
            hc = h_vertical(L, tb, ta) if kind == 'vert' else h_horizontal(L, tb, ta, kind)
            tot += a * (hc + h_radiation(eps, tb, ta))
        return tot / n_motors
    net.link('B', 'amb', g)
    net.fixed['body_air'] = t_amb + v('body_air')['rise_k']
    a_top = v('tray_top_m2')
    net.link('B', 'body_air', lambda T: a_top * (h_horizontal(INPUTS['tray_top_m2']['L_m'], T['B'], T['body_air'], 'up')
                                                + h_radiation(eps, T['B'], T['body_air'])) / n_motors)
    return net


def add_printed_frame(net, mat, mount, n_layers=6):
    """The web as n layers through its thickness over the motor's face annulus (1D: no sideways spreading, which
    keeps the face warm: conservative for the face), the contact on the motor side, the leg-side face to the air,
    and the flanges to the cheek (mount 'body') or nothing (mount 'stand': a plywood end plate)."""
    m = v(mat)
    a = can_areas()['mount_face']
    a_leg = v('web_leg_face_m2')
    dx = v('web_t_m') / n_layers
    names = [net.node(f'F{i}', a * dx * m['rho'] * m['cp']) for i in range(n_layers)]
    net.link('C', names[0], 1 / (1 / (v('h_contact_polymer') * a) + dx / 2 / (m['k'] * a)))
    for p, q in zip(names, names[1:]):
        net.link(p, q, m['k'] * a / dx)
    net.link(names[-1], 'amb', lambda T, n=names[-1]: 1 / (dx / 2 / (m['k'] * a) + 1 / (a_leg * (
        h_vertical(0.158, T[n], T['amb']) + h_radiation(m['eps'], T[n], T['amb'])))))
    if mount == 'body':
        fl_a = v('flange_x_m') * sum(v('flange_t_m'))
        r_fl = v('flange_len_m') / (m['k'] * fl_a) + 1 / (v('h_contact_polymer') * v('flange_x_m') * sum(v('flange_t_m')))
        net.link(names[n_layers // 2], 'B', 1 / r_fl)
    return names[0]


def add_al_plate(net, mount, eps=None, post_k=None):
    p = v('plate')
    al = dict(v('al6061'))
    if eps is not None:
        al['eps'] = eps
    w, h, t = p['w'] / 2, p['h'], p['t']                    # this motor's half of the plate
    a_face = can_areas()['mount_face']
    od = v('od_m')
    open_inner = w * h - math.pi / 4 * od ** 2                # the motor side, outside the motor's footprint
    open_outer = w * h - math.pi / 4 * v('face_bore_d_m') ** 2
    net.node('F0', w * h * t * al['rho'] * al['cp'])

    def g_air(T):
        # the outer (leg-side) face sees the room; the inner face looks at the cheek 57 mm away, a bare aluminium sheet
        # near the plate's temperature: convection only there (its radiation to the cheek left out: conservative)
        hcv = h_vertical(h, T['F0'], T['amb'])
        return hcv * (open_inner + open_outer) + h_radiation(al['eps'], T['F0'], T['amb']) * open_outer

    def g_cp(T):
        h_eff = g_air(T) / (w * h)
        return 1 / (1 / (v('h_contact_metal') * a_face) + spreading_resistance(al['k'], t, a_face, w * h, h_eff))
    net.link('C', 'F0', g_cp)
    net.link('F0', 'amb', g_air)
    if mount == 'body':
        a_post = math.pi / 4 * (p['post_d'] ** 2 - p['post_hole_d'] ** 2)
        r_post = v('flange_len_m') / ((post_k or al['k']) * a_post) + 2 / (v('h_contact_metal') * a_post)
        net.link('F0', 'B', p['posts'] / 2 / r_post)         # half the posts per motor
    return 'F0'


def add_rear(net, pad, mount):
    """The rear cover to the cheek across the 2.0 mm gap: still air and radiation, or a gap pad."""
    if mount != 'body':
        return
    a = v('rear_overlap_m2')
    gap = v('rear_gap_m')
    if pad:
        gp = v('gap_pad')
        net.link('C', 'B', 1 / (gp['t'] / (gp['k'] * a) + 2 / (5000.0 * a)))    # two pad contacts, 5 kW/m2K each (assumed)
    else:
        e1, e2 = v('eps_case'), v('al5052')['eps']
        net.link('C', 'B', lambda T: a * (v('k_air') / gap + h_radiation(1 / (1 / e1 + 1 / e2 - 1), T['C'], T['B'])))


def leg_network(cal, option, P, stall_f, t_amb, mount='body', n_motors=4):
    net = Network(t_amb)
    printed = option in ('A_pla', 'B_pa6cf', 'D_pa6cf_pad')
    plate_kw = {'eps': v('plate_black')['eps'], 'post_k': v('plate_black')['spacer_k']} if option == 'E_al_plate_black_iso' else {}
    add_motor(net, cal, P, stall_f=stall_f, exposure=v('can_side_exposed')['printed' if printed else 'plate'],
              rear_free=False)                     # the cheek, or the stand's plywood, 2 mm behind its rear cover
    if mount == 'body':
        add_body(net, n_motors, t_amb)
    if printed:
        face = add_printed_frame(net, 'pla' if option == 'A_pla' else 'pa6cf', mount)
    else:
        face = add_al_plate(net, mount, **plate_kw)
    add_rear(net, option == 'D_pa6cf_pad', mount)
    return net, face


def face_limit(option):
    if option == 'A_pla':
        return v('pla')['face_limit_c']
    if option in ('B_pa6cf', 'D_pa6cf_pad'):
        return v('pa6cf')['face_limit_c']
    return None


# ----------------------------------------------------------------------------------------------- the duty cases
def loads():
    """The cases' torques from the CAD's five-bar and the rig (needs CadQuery and MuJoCo: the CAD venv). Recorded in
    the JSON; the check and the tests read them from there."""
    sys.path[:0] = [str(R / 'cad'), str(R)]
    import fivebar as fb
    from sim import leg_rig as lr
    m = lr.HALF_MASS
    m_wheel = lr.WHEEL['mass_g'] / 1000
    f_axle = (m - m_wheel) * G0                     # the wheel's own weight is not the motors' (the links' is: conservative)

    def taus(h, fx=0.0, fz=f_axle):
        # at the contact patch: the wheel is a hub motor whose stator is fixed to the wheel link, so a fore-aft tyre
        # force's moment about the axle reaches the leg (the vertical load gives the same torques either way)
        pf = lr.pin_forces(*fb.stance(h, 0.0), (fx, fz), at_axle=False)
        return abs(float(pf['tau_front'])), abs(float(pf['tau_rear']))

    def dtau_dfx(h):
        a, b = taus(h, 1.0, 0.0)
        return a, b
    out = {'half_mass_kg': float(m), 'wheel_kg': float(m_wheel), 'axle_force_n': round(f_axle, 1),
           'basis': 'quasi-static: sim.leg_rig.pin_forces on cad.fivebar.stance(h), the axle carrying the leg\'s design load '
                    'less its wheel (D71: 18.75 kg a leg); front and rear are the two hip motors (the five-bar has no '
                    'knee motor)'}
    cases = {}
    for key, h, title in (('stand', 300.0, 'Standing at the design stance (300 mm leg)'),
                          ('crouch', 185.0, 'Holding the lowest controlled crouch (185 mm leg, D71)')):
        tf, tr = taus(h)
        cases[key] = {'title': title, 'leg_mm': h, 'tau_front': round(tf, 2), 'tau_rear': round(tr, 2), 'rpm': 0.0,
                      'stall': True}
    # driving and balancing: legs held (stalled), a fore-aft force at the tyre, rms
    h = 260.0
    t0 = taus(h)
    k = dtau_dfx(h)
    fx = v('drive_fx_g') * m * G0
    tr = [math.sqrt(t0[i] ** 2 + (k[i] * fx) ** 2) for i in range(2)]
    cases['drive'] = {'title': f'Driving and balancing at 260 mm: {v("drive_fx_g")} g rms fore-aft at the tyre (assumed)',
                      'leg_mm': h, 'tau_front': round(tr[0], 2), 'tau_rear': round(tr[1], 2), 'rpm': 0.0, 'stall': True}
    # jumps: the rig's jump at the 60 N m cap (exports/leg/rig-results.json, 18.75 kg), every period, standing between
    rig = json.loads((R / 'exports' / 'leg' / 'rig-results.json').read_text())
    sc = rig['scenarios']['jump']
    s = sc['series']
    t = s['t']
    ts, tsf = cases['stand']['tau_front'], cases['stand']['tau_rear']
    e2 = [0.0, 0.0]
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        for j, key in enumerate(('tau_f', 'tau_r')):
            e2[j] += dt * (s[key][i] ** 2 + s[key][i - 1] ** 2) / 2
    dur = t[-1] - t[0]
    # the leg's travel through the jump (|d phi| summed), for the drag loss: from the rig's leg length series
    rot = 0.0
    prev = None
    for L in s['L_mm']:
        p = [float(x) for x in fb.stance(min(max(L, 140.0), 380.0), 0.0)]
        if prev:
            rot += max(abs(p[0] - prev[0]), abs(p[1] - prev[1]))
        prev = p
    period = v('jump_period_s')
    tau2 = [(e2[0] + ts ** 2 * (period - dur)) / period, (e2[1] + tsf ** 2 * (period - dur)) / period]
    cases['jumps'] = {'title': f'A jump every {period:.0f} s (the rig\'s jump at the 60 N m cap), standing between',
                      'leg_mm': 300.0, 'tau_front': round(math.sqrt(tau2[0]), 2), 'tau_rear': round(math.sqrt(tau2[1]), 2),
                      'rpm': round(rot / period * 60 / (2 * math.pi), 3), 'stall': True,
                      'jump': {'window_s': round(dur, 2), 'int_tau2_front': round(e2[0], 1), 'int_tau2_rear': round(e2[1], 1),
                               'peak_nm': sc['peak_motor_nm'], 'travel_rad': round(rot, 2),
                               'source': 'exports/leg/rig-results.json scenarios.jump (18.75 kg, the 60 N m cap)'}}
    out['cases'] = cases
    out['rig_stand_check'] = {'rig_stand_up_hold_nm': abs(rig['scenarios']['stand_up']['series']['tau_f'][-1]),
                              'model_stand_nm': cases['stand']['tau_front'],
                              'note': 'the rig\'s stand_up ends holding at 300 mm; this model\'s figure is the higher (conservative)'}
    md = json.loads((R / 'exports' / 'motor-day' / 'derating.json').read_text())
    out['bench'] = {'cap_nm': md['pla_cap_nm'], 'hold_nm': md['stand_runs']['stand_up']['peak_motor_nm'],
                    'stand_kg': md['mass']['stand_scale_kg'],
                    'source': 'exports/motor-day/derating.json: the PLA cap (pla_cap_nm) and the motor-day stand-up\'s peak '
                              'motor torque (stand_runs.stand_up); the stand\'s 11.89 kg at the foot'}
    return out


# ------------------------------------------------------------------------------------------------------ results
SAMPLES = [60, 300, 600, 1200, 1800, 3600, 7200]


def run_case(cal, option, tau, rpm, stall, t_amb, mount='body', t_end=7200.0):
    f = v('stall_factor') if stall else 1.0
    net, face = leg_network(cal, option, {'tau': tau, 'rpm': rpm}, f, t_amb, mount)
    T = net.steady()
    lim = face_limit(option)
    w_target = v('winding_target_c')
    tr = net.transient(t_end, 2.0, record=SAMPLES)
    # times to the limits (a second pass with a stop, only when the steady state passes them)
    t_face = None
    if lim is not None and T[face] > lim:
        n2, f2 = leg_network(cal, option, {'tau': tau, 'rpm': rpm}, f, t_amb, mount)
        t_face = n2.transient(6 * 3600.0, 2.0, stop=lambda Tn: Tn[f2] >= lim)['t_stop']
    t_w = None
    if hot(T) > w_target:
        n3, _ = leg_network(cal, option, {'tau': tau, 'rpm': rpm}, f, t_amb, mount)
        t_w = n3.transient(6 * 3600.0, 2.0, stop=lambda Tn: hot(Tn) >= w_target)['t_stop']
    loss = copper_loss(tau, T['W']) + drag_loss(rpm) + driver_loss(tau)
    res = {'tau_nm': tau, 'current_arms': round(current_arms(tau), 2), 'loss_w': round(loss, 1),
           'steady': {'winding_c': round(hot(T), 1), 'case_c': round(T['C'], 1), 'face_c': round(T[face], 1)},
           'transient': {str(s): {'winding_c': round(hot(x), 1), 'case_c': round(x['C'], 1), 'face_c': round(x[face], 1)}
                         for s, x in tr['samples'].items()},
           'face_limit_c': lim, 't_face_limit_s': None if t_face is None else round(t_face),
           't_winding_target_s': None if t_w is None else round(t_w)}
    if mount == 'body':
        res['steady']['body_c'] = round(T['B'], 1)
        res['body_heat_w'] = round(_flow_into(net, T, 'B'), 2)
        res['into_body_air_w_all_motors'] = round(4 * _flow(net, T, 'B', 'body_air'), 2)
    return res


def _flow(net, T, a, b):
    for p, q, g in net.links:
        if (p, q) == (a, b):
            return g(T) * (T[a] - T[b])
        if (p, q) == (b, a):
            return g(T) * (T[b] - T[a])
    return 0.0


def _flow_into(net, T, node):
    s = 0.0
    for p, q, g in net.links:
        if q == node and p != 'amb' and p != 'body_air':
            s += g(T) * (T[p] - T[q])
        elif p == node and q not in ('amb', 'body_air'):
            s += g(T) * (T[q] - T[p])
    return s


def bench_face(cal, tau, t_amb):
    net, face = leg_network(cal, 'A_pla', {'tau': tau, 'rpm': 0.0}, v('stall_factor'), t_amb, mount='stand')
    return net.steady()[face]


def bench_limit(cal, t_amb):
    """The continuous torque that holds the PLA frame's face at the owner's 50 C on the motor-day stand (the plywood
    end plate: no path to a body), at room t_amb."""
    lim = v('pla')['face_limit_c']
    return bisect(lambda t: bench_face(cal, t, t_amb) - lim, 0.0, 30.0, 40)


def model(ld):
    """Everything from the recorded loads `ld` (loads()); the calibration inside."""
    cal_fit = calibrate()
    cal = cal_of(cal_fit)
    t_amb, t_hot = v('ambient_c'), v('ambient_hot_c')
    results = {}
    for ck, c in ld['cases'].items():
        tau = max(c['tau_front'], c['tau_rear'])
        results[ck] = {o: run_case(cal, o, tau, c['rpm'], c['stall'], t_amb) for o in OPTIONS}
    worst_key = max(ld['cases'], key=lambda k: results[k]['B_pa6cf']['steady']['winding_c'])
    wc = ld['cases'][worst_key]
    hot_day = {o: run_case(cal, o, max(wc['tau_front'], wc['tau_rear']), wc['rpm'], wc['stall'], t_hot) for o in OPTIONS}
    # the jump's own pulse over the mean (all of its copper loss into the winding alone: an upper bound)
    j = ld['cases']['jumps']['jump']
    e2 = max(j['int_tau2_front'], j['int_tau2_rear'])
    pulse_k = 1.5 * e2 / v('kt_nm_per_arms') ** 2 * r_line(120.0) / cal['c_w']
    b = ld['bench']
    bench = {'face_limit_c': v('pla')['face_limit_c'], 'stand_kg': b['stand_kg'], 'cap_nm': b['cap_nm'],
             'hold_nm': b['hold_nm'], 'limits': [], 'runs': {}}
    for room in (20.0, 25.0, 30.0):
        tl = bench_limit(cal, room)
        bench['limits'].append({'room_c': room, 'torque_nm': round(tl, 1), 'current_arms': round(current_arms(tl), 2),
                                'current_apk': round(current_arms(tl) * math.sqrt(2), 1)})
    # the same with the case bare and shaded (eps_case and can_side_exposed at the low ends of their ranges): the
    # limit to use until the bench fit has measured the case's convection
    saved = {k: copy.deepcopy(INPUTS[k]['v']) for k in ('eps_case', 'can_side_exposed')}
    try:
        INPUTS['eps_case']['v'] = INPUTS['eps_case']['range'][0]
        INPUTS['can_side_exposed']['v'] = dict(saved['can_side_exposed'], printed=INPUTS['can_side_exposed']['range'][0])
        bench['limits_low'] = []
        for room in (20.0, 25.0, 30.0):
            tl = bench_limit(cal, room)
            bench['limits_low'].append({'room_c': room, 'torque_nm': round(tl, 1), 'current_arms': round(current_arms(tl), 2),
                                        'current_apk': round(current_arms(tl) * math.sqrt(2), 1)})
        bench['hold_low'] = run_case(cal, 'A_pla', b['hold_nm'], 0.0, True, t_amb, mount='stand', t_end=2.0)['steady']
    finally:
        for k, x in saved.items():
            INPUTS[k]['v'] = x
    crouch = max(ld['cases']['crouch']['tau_front'], ld['cases']['crouch']['tau_rear'])
    for name, tau in (('cap', b['cap_nm']), ('hold', b['hold_nm']), ('robot_crouch', crouch)):
        bench['runs'][name] = run_case(cal, 'A_pla', tau, 0.0, True, t_amb, mount='stand')
    # the plates' thickness the calibration assumed: the fit and the worst case again at its range's ends
    spread = []
    for tp, ef in [(tp, None) for tp in INPUTS['test_plate_t_m']['range']] + [(None, 0.1), (None, 0.5)]:
        cf = calibrate(t_plate=tp, eps_fixed=ef)
        cl = cal_of(cf)
        spread.append({'t_test_plate_m': cf['t_test_plate_m'], 'eps_fixed': ef,
                       'rating_b_miss_k': round(cf['rating_b']['winding_c'] - v('winding_limit_c'), 1), 'r_wc_k_per_w': cf['r_wc_k_per_w'], 'eps_test_plate': cf['eps_test_plate'],
                       'c_w_j_per_k': cf['c_w_j_per_k'],
                       'worst_winding_c': {o: run_case(cl, o, max(wc['tau_front'], wc['tau_rear']), wc['rpm'], wc['stall'],
                                                       t_amb, t_end=2.0)['steady']['winding_c'] for o in ('B_pa6cf', 'E_al_plate_black_iso')}})
    return {'about': 'RS-04 leg motor thermal model (issue #194); generated by sim/motor_thermal.py: regenerate, never edit',
            'inputs': {k: {'v': _plain(x['v']), 'src': x['src'], **({'range': list(x['range'])} if 'range' in x else {})}
                       for k, x in INPUTS.items()},
            'loads': ld, 'calibration': cal_fit, 'calibration_spread': spread, 'options': OPTIONS, 'results': results,
            'worst_case': worst_key, 'hot_day': {'ambient_c': t_hot, 'case': worst_key, 'results': hot_day},
            'jump_pulse_k': round(pulse_k, 1), 'bench': bench, 'sensitivity': sensitivity(ld, cal, worst_key),
            'recommendation': recommend(hot_day)}


def _plain(x):
    return json.loads(json.dumps(x))


def recommend(hot_day):
    """Each option in the worst realistic case (the worst duty on a hot day): the winding against the 120 C target,
    the frame's face against its material's limit, the body frame's temperature and the heat into the body's air."""
    rows = []
    budget = v('body_air')
    for o in OPTIONS:
        r = hot_day[o]
        lim = face_limit(o)
        air_k = r['into_body_air_w_all_motors'] / budget['mcp_w_per_k']
        rows.append({'option': o, 'winding_c': r['steady']['winding_c'], 'face_c': r['steady']['face_c'],
                     'face_limit_c': lim, 'body_c': r['steady']['body_c'],
                     'into_body_air_w': r['into_body_air_w_all_motors'], 'cooler_inlet_k': round(budget['rise_k'] + air_k, 2),
                     'pass_winding': r['steady']['winding_c'] <= v('winding_target_c'),
                     'pass_face': lim is None or r['steady']['face_c'] <= lim,
                     'pass_body_air': budget['rise_k'] + air_k <= budget['budget_k']})
    for r in rows:                       # the motor's own limits decide; the body's air is a reported side effect
        r['passes'] = r['pass_winding'] and r['pass_face']
    passing = [r for r in rows if r['passes']]
    best = min(passing, key=lambda r: (r['into_body_air_w'], r['winding_c']))['option'] if passing else None
    return {'target_winding_c': v('winding_target_c'), 'rows': rows, 'choice': best,
            'rule': 'passes: the winding at or under the target and the face at or under its material\'s limit; of those, '
                    'the least heat into the body\'s air'}


def sensitivity(ld, cal, worst_key):
    """The worst case's steady winding and face, options B and E, with each ranged input at its ends."""
    c = ld['cases'][worst_key]
    tau = max(c['tau_front'], c['tau_rear'])
    out = []
    for key in ('r_line_ohm', 'stall_factor', 'eps_case', 'can_side_exposed', 'h_contact_polymer', 'h_contact_metal',
                'c_mix_j_per_kgk', 'i_noload_arms', 'r_driver_ohm', 'drive_fx_g'):
        rng = INPUTS[key].get('range')
        row = {'input': key, 'range': list(rng)}
        for end, val in zip(('lo', 'hi'), rng):
            saved = copy.deepcopy(INPUTS[key]['v'])
            if key == 'can_side_exposed':
                INPUTS[key]['v'] = {'printed': val, 'plate': min(1.0, val + 0.35)}
            else:
                INPUTS[key]['v'] = val
            try:
                t = tau
                if key == 'drive_fx_g':           # rescale the driving case's fore-aft part
                    s = ld['cases']['stand']['tau_front']
                    t = math.sqrt(s ** 2 + (tau ** 2 - s ** 2) * (val / saved) ** 2) if worst_key == 'drive' else tau
                row[end] = {o: [r['winding_c'], r['face_c']] for o in ('B_pa6cf', 'E_al_plate_black_iso')
                            for r in [run_case(cal, o, t, c['rpm'], c['stall'], v('ambient_c'), t_end=2.0)['steady']]}
            finally:
                INPUTS[key]['v'] = saved
        out.append(row)
    return out


# --------------------------------------------------------------------------------------------- re-fit to a bench log
FIT_COLUMNS = ('t_s', 'tau_nm', 'room_c', 'motor_c', 'case_c', 'face_c')


def simulate_log(cal, rows, option='A_pla', mount='stand', dt=2.0):
    """Run the network through a logged duty (rows: dicts of FIT_COLUMNS; the torque held from each row to the next),
    from the first row's readings. Returns the model's (winding, case, face) at each row's time."""
    P = {'tau': rows[0]['tau_nm'], 'rpm': 0.0}
    net, face = leg_network(cal, option, P, v('stall_factor'), rows[0]['room_c'], mount)
    x = net.start(rows[0]['case_c'])
    out, t = [], rows[0]['t_s']
    for i, r in enumerate(rows):
        while t < r['t_s'] - 1e-9:
            h = min(dt, r['t_s'] - t)
            x = net.step(x, h)
            t += h
        T = net.temps(x)
        out.append((hot(T), T['C'], T[face]))
        P['tau'] = r['tau_nm']
        net.fixed['amb'] = r['room_c']
    return out


def refit(rows, cal, option='A_pla', mount='stand'):
    """Fit three numbers to a bench log, one reading each: the case's convection (can_air_factor) to the case
    thermocouple, the face contact (h_contact_polymer, or _metal) to the face thermocouple, and R_wc to the motor's
    own reported temperature (taken as its winding estimate). Coordinate descent, golden section in log space."""
    hkey = 'h_contact_polymer' if option in ('A_pla', 'B_pa6cf', 'D_pa6cf_pad') else 'h_contact_metal'
    saved = {k: INPUTS[k]['v'] for k in ('can_air_factor', hkey)}
    params = {'can_air_factor': 1.0, hkey: INPUTS[hkey]['v'], 'r_wc': cal['r_wc']}
    which = {'can_air_factor': 1, hkey: 2, 'r_wc': 0}

    def sse(p):
        INPUTS['can_air_factor']['v'] = p['can_air_factor']
        INPUTS[hkey]['v'] = p[hkey]
        sim = simulate_log(dict(cal, r_wc=p['r_wc']), rows, option, mount)
        cols = ('motor_c', 'case_c', 'face_c')
        return [sum((s[k] - r[cols[k]]) ** 2 for s, r in zip(sim, rows) if r.get(cols[k]) is not None) for k in range(3)]
    try:
        for _ in range(3):
            for key in ('can_air_factor', hkey, 'r_wc'):
                lo, hi = math.log(params[key] / 4), math.log(params[key] * 4)
                g = (math.sqrt(5) - 1) / 2

                def f(u):
                    return sse(dict(params, **{key: math.exp(u)}))[which[key]]
                a, b = lo, hi
                c1, c2 = b - g * (b - a), a + g * (b - a)
                f1, f2 = f(c1), f(c2)
                for _ in range(22):
                    if f1 < f2:
                        b, c2, f2 = c2, c1, f1
                        c1 = b - g * (b - a)
                        f1 = f(c1)
                    else:
                        a, c1, f1 = c1, c2, f2
                        c2 = a + g * (b - a)
                        f2 = f(c2)
                params[key] = math.exp((a + b) / 2)
        res = sse(params)
    finally:
        for k, x in saved.items():
            INPUTS[k]['v'] = x
    n = len(rows)
    return {'can_air_factor': round(params['can_air_factor'], 3), hkey: round(params[hkey], 1),
            'r_wc_k_per_w': round(params['r_wc'], 4),
            'rms_k': {c: round(math.sqrt(e / n), 2) for c, e in zip(('motor', 'case', 'face'), res)}}


def read_log(path):
    import csv
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            rows.append({k: (float(r[k]) if r.get(k) not in (None, '') else None) for k in FIT_COLUMNS})
    return rows


# ------------------------------------------------------------------------------------------------------ the page
def fmt_t(s):
    if s is None:
        return 'never'
    return f'{s / 60:.0f} min' if s >= 120 else f'{s:.0f} s'


SHORT = {'A_pla': 'A PLA', 'B_pa6cf': 'B PA6-CF', 'C_al_plate': 'C 6061 plate', 'D_pa6cf_pad': 'D PA6-CF + pad',
         'E_al_plate_black_iso': 'E black 6061, isolated'}


def render(m):
    """docs/motor-thermal.md from the JSON (regenerate, never edit)."""
    cal, ld, res, rec, bn = m['calibration'], m['loads'], m['results'], m['recommendation'], m['bench']
    I = m['inputs']
    hot_c = m['hot_day']['ambient_c']
    wk = m['worst_case']
    L = []
    w = L.append
    w('# RS-04 leg motors: heat into the hip frame and the body')
    w('')
    w('<!-- Generated by sim/motor_thermal.py from exports/leg/thermal/motor_thermal.json: regenerate, never edit. -->')
    w('')
    w('The owner asked on 2026-11-03 for "a model for motor heat dissipation into the body so we make sure we properly '
      'heat sink them" ([issue #194](https://github.com/Valpatel/gyropup/issues/194)). This page is that model\'s '
      'output: each leg motor\'s losses in the robot\'s duty cases, where the heat goes, the temperatures for five hip '
      'frame options, a limit for the PLA bench legs, and what to log on the first powered runs to correct it. Numbers: '
      '`sim/motor_thermal.py` → `exports/leg/thermal/motor_thermal.json`; tests: `sim/test_motor_thermal.py`. It is a '
      'lumped model calibrated on the manufacturer\'s ratings, not a measurement: the bench logs in section 7 are its '
      'acceptance.')
    w('')
    ch = rec['choice']
    rows = {r['option']: r for r in rec['rows']}
    w('**In short**')
    w('')
    w(f'- **The printed frames insulate the motors.** A PA6-CF hip frame (today\'s design) leaves each motor to cool '
      f'itself: in the worst case ({ld["cases"][wk]["title"].lower()}, {hot_c:.0f} °C room) the winding settles at '
      f'**{rows["B_pa6cf"]["winding_c"]:.0f} °C** (target {rec["target_winding_c"]:.0f}) and the frame\'s face at '
      f'**{rows["B_pa6cf"]["face_c"]:.0f} °C** (PA6-CF limit taken {rows["B_pa6cf"]["face_limit_c"]:.0f}).')
    if ch:
        r = rows[ch]
        w(f'- **Recommended: option {ch[0]}** ({OPTIONS[ch][3].lower() + OPTIONS[ch][4:]}): winding {r["winding_c"]:.0f} °C, plate '
          f'{r["face_c"]:.0f} °C, body frame {r["body_c"]:.0f} °C in the same case; the body\'s air gets '
          f'{r["into_body_air_w"]:.1f} W (the cooler\'s inlet {r["cooler_inlet_k"]:.1f} K over the room, D61\'s budget '
          f'{m["inputs"]["body_air"]["v"]["budget_k"]:.0f}).')
    w(f'- **Do not use the body as the heat sink.** The body frame has the mass to soak up a few minutes of heat but '
      f'little open area, inside a shell that the J501\'s cooler breathes from: a gap pad from the rear covers to the '
      f'cheeks (D) cools the windings as well as a plate but runs the body frame at {rows["D_pa6cf_pad"]["body_c"]:.0f} °C '
      f'and puts {rows["D_pa6cf_pad"]["into_body_air_w"]:.0f} W into the body\'s air.')
    lim25 = next(x for x in bn['limits'] if x['room_c'] == 25.0)
    low25 = next(x for x in bn['limits_low'] if x['room_c'] == 25.0)
    w(f'- **PLA bench: stop when a motor\'s case passes {bn["face_limit_c"]:.0f} °C** (the PLA face runs a few kelvin under '
      f'it). In a 25 °C room the face stays under {bn["face_limit_c"]:.0f} °C indefinitely below **{lim25["torque_nm"]:.1f} '
      f'N m ({lim25["current_arms"]:.1f} A rms)** held per motor, or **{low25["torque_nm"]:.1f} N m '
      f'({low25["current_arms"]:.1f} A rms)** if the case turns out bare and shaded; the stand\'s own hold '
      f'({bn["hold_nm"]:.1f} N m) settles at {bn["runs"]["hold"]["steady"]["face_c"]:.0f} °C (or '
      f'{bn["hold_low"]["face_c"]:.0f} °C). At the PLA cap ({bn["cap_nm"]:.0f} N m) held without a break it passes '
      f'{bn["face_limit_c"]:.0f} °C after **{fmt_t(bn["runs"]["cap"]["t_face_limit_s"])}**.')
    w('')
    w('## 1. The heat path')
    w('')
    w('```mermaid')
    w('flowchart LR')
    w('    W["winding<br/>(copper I²R)"] -->|R_wc| C["case<br/>(drag, driver)"]')
    w('    C -->|"O106 face, 10 x M4<br/>contact"| F["hip frame<br/>(web or plate)"]')
    w('    C -->|"convection + radiation"| A(("room air"))')
    w('    F -->|"leg-side face"| A')
    w('    F -->|"flanges or spacers"| B["body frame<br/>cheeks, tray, belly"]')
    w('    C -->|"rear cover, 2 mm gap<br/>(air, or a pad)"| B')
    w('    B --> A')
    w('    B -->|"tray top"| J(("body air<br/>J501 cooler inlet"))')
    w('```')
    w('')
    w('Each motor is a winding node and a case node (the housing, stator iron, gears and the driver: '
      f'{I["mass_kg"]["v"]} kg, {cal["c_w_j_per_k"] + cal["c_case_j_per_k"]:.0f} J/K). The case touches the hip frame '
      'on its O106 face annulus under the ten M4 lug screws, sits 3.5 mm under the printed frame\'s flanges (they '
      'shade half its side from the air) and 2.0 mm from the cheek behind its rear cover. A printed web is six layers '
      'through its 24.1 mm thickness; a plate is one node with the Song-Lee-Au spreading resistance from the face. The '
      'body frame (both cheeks, the tray, the belly: '
      f'{sum(I["body_parts_kg"]["v"].values()):.2f} kg) is one node shared by the four motors. Natural convection '
      'is Churchill-Chu (vertical plates, horizontal cylinders) and Incropera\'s horizontal plates, with linearised '
      'radiation; every surface\'s coefficient follows its temperature.')
    w('')
    w('A held leg motor is a **stalled** motor: its hottest phase carries the peak current, so the firmware\'s '
      f'per-phase winding estimate runs (f - 1) x P_cu x R_wc over the mean with f = {I["stall_factor"]["v"]} '
      '(the hot-spot term). Every robot case here holds the legs still; the motors\' speed loss only matters in the '
      'jumps.')
    w('')
    w('## 2. Calibration on the RS-04\'s own ratings')
    w('')
    ra, rb = I['rating_a']['v'], I['rating_b']['v']
    w('| | Manufacturer | Model |')
    w('|---|---|---|')
    w(f'| 40 N m at 50 rpm on 345 x 345 mm aluminium | winding at 145 °C | {cal["rating_a"]["winding_c"]} °C '
      f'(case {cal["rating_a"]["case_c"]}, plate {cal["rating_a"]["plate_c"]}; {cal["rating_a"]["loss_w"]} W) |')
    w(f'| 35.5 N m at 40 rpm on 220 x 200 mm | winding at 145 °C | {cal["rating_b"]["winding_c"]} °C '
      f'(case {cal["rating_b"]["case_c"]}; {cal["rating_b"]["loss_w"]} W) |')
    for c in cal['rating_b_curve']:
        w(f'| {c["tau_nm"]} N m at {c["rpm"]:.0f} rpm on 220 x 200 mm (not fitted) | 145 °C | {c["model_winding_c"]} °C |')
    w(f'| 28.5 N m stalled (the stall table\'s rated row) | 145 °C | {cal["stall_rated_model_winding_c"]} °C |')
    w('')
    w(f'Fitted: **R_wc = {cal["r_wc_k_per_w"]} K/W** winding to case, the test plates\' emissivity '
      f'{cal["eps_test_plate"]} ({cal["t_test_plate_m"] * 1000:.0f} mm plates assumed)'
      + (f' — {cal["bound"]}: the second rating comes out {cal["rating_b"]["winding_c"] - 145:.1f} K high' if cal['bound'] else '')
      + f', and **C_w = {cal["c_w_j_per_k"]} J/K** for the winding from the overload table (rms error '
      f'{cal["overload_rms_log_error"]} in log time over 50-110 N m). The emissivity is not known (GB/T 30549-2014 '
      'was not read): the fit runs to the bound because the smaller plate\'s rating asks for a plate that sheds well. '
      'That bound is the conservative end for the windings here: a less emissive test plate would mean a better heat '
      'path inside the motor (a lower R_wc) and cooler windings in every case below:')
    w('')
    sp = m['calibration_spread']
    w('| Test plates | R_wc, K/W | The 220 x 200 rating misses by | Worst case\'s winding, B / E (25 °C) |')
    w('|---|---|---|---|')
    for x in sp:
        lab = (f'{x["t_test_plate_m"] * 1000:.0f} mm, emissivity fitted ({x["eps_test_plate"]})' if x['eps_fixed'] is None
               else f'{x["t_test_plate_m"] * 1000:.0f} mm, emissivity fixed at {x["eps_fixed"]}')
        w(f'| {lab} | {x["r_wc_k_per_w"]} | {x["rating_b_miss_k"]:+.1f} K | {x["worst_winding_c"]["B_pa6cf"]:.0f} / '
          f'{x["worst_winding_c"]["E_al_plate_black_iso"]:.0f} °C |')
    w(f'| **{cal["t_test_plate_m"] * 1000:.0f} mm, fitted ({cal["eps_test_plate"]}): used** | {cal["r_wc_k_per_w"]} | '
      f'{cal["rating_b"]["winding_c"] - 145:+.1f} K | {res[wk]["B_pa6cf"]["steady"]["winding_c"]:.0f} / '
      f'{res[wk]["E_al_plate_black_iso"]["steady"]["winding_c"]:.0f} °C |')
    w('')
    w('| N m (50 rpm) | ' + ' | '.join(str(o['tau_nm']) for o in cal['overload']) + ' |')
    w('|---|' + '---|' * len(cal['overload']))
    w('| manual, s | ' + ' | '.join(str(o['manual_s']) for o in cal['overload']) + ' |')
    w('| model, s | ' + ' | '.join(f'{o["model_s"]}' + ('' if o['fitted'] else '*') for o in cal['overload']) + ' |')
    w('')
    w('\\* not fitted: at 115-120 N m the drive\'s peak-current timer acts first. What the calibration cannot see:')
    w('')
    short = [145 - c['model_winding_c'] for c in cal['rating_b_curve']]
    w(f'- **The speed loss is too low at speed.** The 220 x 200 table at 80-191 rpm should reach 145 °C; the model '
      f'stops {min(short):.0f}-{max(short):.0f} K short, so the drag grows faster than kt x I0 x omega (iron loss). The '
      'held legs do not turn; do not use this model for fast cycling without a speed test.')
    ratio = [x['model_s'] / x['manual_s'] for x in cal['stall'] if x['tau_nm'] >= 70 and x['model_s']]
    w(f'- **The firmware\'s stall protection is stricter than the heat.** Stalled, the manual\'s times are '
      f'{min(ratio):.0f}-{max(ratio):.0f} times shorter than the model at 70-120 N m, and its rated stall torque (28.5 N m) '
      'leaves the modelled winding at '
      f'{cal["stall_rated_model_winding_c"]} °C: a locked-rotor protection (fault bit 14) acts on the current. Treat '
      '**28.5 N m per motor as the holding ceiling** whatever the temperature; every case below holds well under it.')
    w('')
    w('## 3. The duty cases: torque, current and loss per motor')
    w('')
    w(f'At the design mass (D71: {ld["half_mass_kg"]} kg a leg; the axle carries {ld["axle_force_n"]} N, the wheel\'s '
      f'{ld["wheel_kg"]} kg taken off). The five-bar\'s two motors are both at the hip: **front** and **rear**, no knee '
      f'motor. The rig\'s own stand-up ends holding {ld["rig_stand_check"]["rig_stand_up_hold_nm"]:.1f} N m at 300 mm '
      f'against this model\'s {ld["rig_stand_check"]["model_stand_nm"]} (conservative: the links\' weight is in it).')
    w('')
    w('| Case | Front N m | Rear N m | Current, A rms | Loss, W (PA6-CF, steady) |')
    w('|---|---|---|---|---|')
    for ck, c in ld['cases'].items():
        r = res[ck]['B_pa6cf']
        w(f'| {c["title"]} | {c["tau_front"]} | {c["tau_rear"]} | {r["current_arms"]} | {r["loss_w"]} |')
    j = ld['cases']['jumps']['jump']
    w('')
    w(f'The jumps are the rig\'s jump at the 60 N m cap ({j["window_s"]} s from standing at 300 mm through the crouch, push and landing, '
      f'{j["int_tau2_front"]:.0f} N²m²s of torque squared on the front motor) every '
      f'{I["jump_period_s"]["v"]:.0f} s, as an rms torque; each jump\'s own pulse adds at most {m["jump_pulse_k"]} K to '
      'the winding over that mean. Driving and balancing are an assumed fore-aft force at the tyre '
      f'({I["drive_fx_g"]["v"]} g rms of the leg\'s load) on a held leg at 260 mm.')
    w('')
    w('## 4. Temperatures: each case and option at a 25 °C room')
    w('')
    w('Steady winding (the firmware\'s estimate) / case / mounting face, °C; the time to the face\'s limit where it '
      'passes it.')
    w('')
    w('| Case | ' + ' | '.join(SHORT[o] for o in OPTIONS) + ' |')
    w('|---|' + '---|' * len(OPTIONS))
    for ck in res:
        cells = []
        for o in OPTIONS:
            r = res[ck][o]
            s = r['steady']
            t = f' (face limit in {fmt_t(r["t_face_limit_s"])})' if r['t_face_limit_s'] else ''
            cells.append(f'{s["winding_c"]:.0f} / {s["case_c"]:.0f} / {s["face_c"]:.0f}{t}')
        w(f'| {ld["cases"][ck]["title"]} | ' + ' | '.join(cells) + ' |')
    w('')
    w(f'**The worst realistic case on a {hot_c:.0f} °C day** ({ld["cases"][wk]["title"].lower()}):')
    w('')
    w('| Option | Winding °C (target 120) | Face °C (limit) | Body frame °C | Into the body\'s air, W (4 motors) | '
      'Cooler inlet over the room, K (budget 3) | Passes |')
    w('|---|---|---|---|---|---|---|')
    for r in rec['rows']:
        lim = '-' if r['face_limit_c'] is None else f'{r["face_limit_c"]:.0f}'
        w(f'| {OPTIONS[r["option"]]} | {r["winding_c"]:.0f} | {r["face_c"]:.0f} ({lim}) | {r["body_c"]:.0f} | '
          f'{r["into_body_air_w"]:.1f} | {r["cooler_inlet_k"]:.2f} | {"yes" if r["passes"] else "no"} |')
    w('')
    cr = res['crouch']
    w('How fast it gets there (the crouch held from cold, 25 °C room; winding / face, °C):')
    w('')
    w('| Option | 1 min | 5 min | 10 min | 30 min | 1 h | 2 h | steady |')
    w('|---|---|---|---|---|---|---|---|')
    for o in OPTIONS:
        tr = cr[o]['transient']
        w(f'| {SHORT[o]} | ' + ' | '.join(f'{tr[str(s)]["winding_c"]:.0f} / {tr[str(s)]["face_c"]:.0f}'
                                          for s in (60, 300, 600, 1800, 3600, 7200)) +
          f' | {cr[o]["steady"]["winding_c"]:.0f} / {cr[o]["steady"]["face_c"]:.0f} |')
    w('')
    w('The motors and frames take an hour or more to settle: short sessions run cooler than the steady figures, and '
      'the steady figures are what a robot left standing reaches.')
    w('')
    w('## 5. The PLA bench (motor day)')
    w('')
    rc = bn['runs']['cap']['steady']
    w(f'The motor-day leg: a PLA hip frame on the stand\'s plywood end plate (no metal behind the motors; the rear '
      f'covers face the plywood 2 mm away and lose nothing there), {bn["stand_kg"]} kg at the foot, the firmware capped '
      f'at {bn["cap_nm"]:.0f} N m. Agents run no powered tests: these are the limits for the owner\'s runs.')
    w('')
    w(f'**The rule that does not depend on the model\'s assumptions: stop when a motor\'s case passes '
      f'{bn["face_limit_c"]:.0f} °C.** PLA conducts almost nothing, so the face runs a few kelvin under the case '
      f'({rc["case_c"] - rc["face_c"]:.0f} K at the cap\'s steady state); a thermocouple on the case (or the motor\'s '
      'own temperature, once the bench fit has related the two) is the stop. Stopping when the cases pass 40 °C is '
      'inside it. The torques below are for planning a session:')
    w('')
    w('| Room | Continuous limit per motor (PLA face <= 50 °C) | The same with the case bare and shaded (`eps_case` 0.3, '
      '`can_side_exposed` 0.3) |')
    w('|---|---|---|')
    for x, y in zip(bn['limits'], bn['limits_low']):
        w(f'| {x["room_c"]:.0f} °C | {x["torque_nm"]:.1f} N m = {x["current_arms"]:.2f} A rms ({x["current_apk"]:.1f} A peak) | '
          f'{y["torque_nm"]:.1f} N m = {y["current_arms"]:.2f} A rms ({y["current_apk"]:.1f} A peak) |')
    w('')
    w('| Held torque per motor, from cold at 25 °C | Face after 10 min | 30 min | 1 h | Steady face | Face passes 50 °C after |')
    w('|---|---|---|---|---|---|')
    for name, label in (('cap', f'the PLA cap, {bn["cap_nm"]:.0f} N m'), ('hold', f'the stand\'s hold, {bn["hold_nm"]} N m'),
                        ('robot_crouch', f'the robot\'s crouch, {bn["runs"]["robot_crouch"]["tau_nm"]} N m (not for PLA)')):
        r = bn['runs'][name]
        tr = r['transient']
        w(f'| {label} | {tr["600"]["face_c"]:.0f} °C | {tr["1800"]["face_c"]:.0f} °C | {tr["3600"]["face_c"]:.0f} °C | '
          f'{r["steady"]["face_c"]:.0f} °C | {fmt_t(r["t_face_limit_s"])} |')
    w('')
    l30 = next(x for x in bn['limits'] if x['room_c'] == 30.0)
    w(f'A warm room or a bare case cuts the margin: at 30 °C the limit is {l30["torque_nm"]:.1f} N m, '
      + ('under' if bn['hold_nm'] > l30['torque_nm'] else 'over')
      + f' the stand\'s own hold of {bn["hold_nm"]} N m, and with a bare, shaded case the hold settles at '
      f'{bn["hold_low"]["face_c"]:.0f} °C even at 25 °C. The first logged hold (section 7) settles which column applies.')
    w('')
    w('## 6. Recommendation')
    w('')
    if ch:
        w(f'**Option {ch[0]}: a flat 6061-T6 plate as the motors\' mounting web, black anodised, with a thermal break '
          f'to the body.** It keeps the windings at {rows[ch]["winding_c"]:.0f} °C in the worst realistic case at '
          f'{hot_c:.0f} °C ({rec["target_winding_c"] - rows[ch]["winding_c"]:.0f} K under the target, '
          f'{145 - rows[ch]["winding_c"]:.0f} K under the firmware\'s cut), the body frame at '
          f'{rows[ch]["body_c"]:.0f} °C and the least heat into the body\'s air of the options that pass.')
        if not rows[ch]['pass_body_air']:
            pr = rows['B_pa6cf']
            w('')
            w(f'One thing it does not fix: the rear covers sit 2.0 mm from the cheeks, and that still air carries heat into '
              f'the body frame with every option. With E the body\'s air gets {rows[ch]["into_body_air_w"]:.1f} W and the '
              f'J501 cooler\'s inlet comes out {rows[ch]["cooler_inlet_k"]:.2f} K over the room against D61\'s '
              f'{m["inputs"]["body_air"]["v"]["budget_k"]:.0f} K (today\'s PA6-CF frame: {pr["cooler_inlet_k"]:.2f} K). The '
              f'body model\'s 2.59 K is itself high (its walls lose nothing), and B16\'s thermometer is that budget\'s '
              f'acceptance; a thinner metal web would also move the motors off the cheek (the follow-up\'s geometry).')
    w('')
    tp, ta = rows[ch]['face_c'], hot_c
    hc_, hb, hk = h_vertical(I['plate']['v']['h'], tp, ta), h_radiation(I['al6061']['v']['eps'], tp, ta), \
        h_radiation(I['plate_black']['v']['eps'], tp, ta)
    w(f'- The metal face takes the case\'s heat into a plate that sees the open air on both sides. Anodising takes it '
      f'from {hc_ + hb:.1f} to {hc_ + hk:.1f} W/m²K at {tp:.0f} °C (convection {hc_:.1f}, radiation {hb:.1f} bare, '
      f'{hk:.1f} black): that is what lets E drop the aluminium spacers into the body and stay within '
      f'{rows[ch]["winding_c"] - rows["C_al_plate"]["winding_c"]:.0f} K of C\'s winding.')
    w(f'- The plain plate on aluminium spacers (C) runs the windings {rows[ch]["winding_c"] - rows["C_al_plate"]["winding_c"]:.0f} K '
      f'cooler but puts {rows["C_al_plate"]["into_body_air_w"]:.0f} W into the body\'s air against E\'s '
      f'{rows[ch]["into_body_air_w"]:.0f}, with the body frame at {rows["C_al_plate"]["body_c"]:.0f} °C; the gap pad (D) does too. '
      'The body frame has little open area and is the floor of the shell the J501 cooler breathes from, and the '
      'battery bay hangs under it: keep the motors\' heat out of it.')
    tb = min(res[k]['B_pa6cf']['t_face_limit_s'] or 1e9 for k in res)
    w(f'- The printed frames (A, B) fail on the face: PA6-CF\'s preloaded lug joint would sit at '
      f'{res["crouch"]["B_pa6cf"]["steady"]["face_c"]:.0f} °C in a long crouch at 25 °C. They warm slowly: B reaches its {rows["B_pa6cf"]["face_limit_c"]:.0f} °C after {fmt_t(tb)} in the worst case '
      'from cold (section 4), long enough for the first powered work on the robot.')
    w('- How to build E (a plate on G10 spacers, or a 6061 web bolted into printed PA6-CF flanges that are the thermal '
      'break) is a CAD and strength question: a follow-up issue, not this change.')
    w('')
    w('## 7. Acceptance: what to log on the first bench runs')
    w('')
    w('Log at 1 Hz on every powered run, with the room temperature:')
    w('')
    w('1. **Each RS-04\'s own temperature** from its feedback frame (communication type 2, bytes 6-7, °C x 10; the '
      'manual does not say if it is the thermistor or the winding estimate) and the board temperature parameter '
      '`boardTemp` (0x3020, x 10), with the torque (bytes 4-5) or `iq` (0x3021).')
    w('2. **A thermocouple on the case** (the O120 side, mid-length, taped and shaded).')
    w('3. **A thermocouple on the mounting face**: under a lug screw\'s head on the frame\'s face, or in a 1 mm groove '
      'at the motor\'s face edge.')
    w('')
    w('The most useful run: hold a known torque (the stand\'s hold) for 30 minutes from cold, then 20 minutes off. '
      'Save it as CSV with the columns `' + ', '.join(FIT_COLUMNS) + '` and run')
    w('')
    w('    python3 sim/motor_thermal.py --fit bench-run.csv            # option A on the stand; --option/--mount for others')
    w('')
    w('It fits three numbers, one reading each: the case\'s convection (`can_air_factor`, to the case thermocouple), '
      'the face contact (`h_contact_polymer`, to the face thermocouple) and R_wc (to the motor\'s own reading), and '
      'prints the rms errors. Put the fitted values into `INPUTS` with the run\'s date as their source and regenerate.')
    w('')
    w('## 8. Sensitivity')
    w('')
    w(f'The worst case ({wk}, 25 °C), steady winding / face °C for B (PA6-CF) and E (the recommendation), with each '
      'ranged input at its ends:')
    w('')
    w('| Input | Range | B low | B high | E low | E high |')
    w('|---|---|---|---|---|---|')
    for s in m['sensitivity']:
        b_lo, b_hi = s['lo']['B_pa6cf'], s['hi']['B_pa6cf']
        e_lo, e_hi = s['lo']['E_al_plate_black_iso'], s['hi']['E_al_plate_black_iso']
        w(f'| `{s["input"]}` | {s["range"][0]} - {s["range"][1]} | {b_lo[0]:.0f} / {b_lo[1]:.0f} | {b_hi[0]:.0f} / '
          f'{b_hi[1]:.0f} | {e_lo[0]:.0f} / {e_lo[1]:.0f} | {e_hi[0]:.0f} / {e_hi[1]:.0f} |')
    w('')
    e_max = max((s[e]['E_al_plate_black_iso'][0], s['input'], e) for s in m['sensitivity'] for e in ('lo', 'hi'))
    b_min = min((s[e]['B_pa6cf'][0], s['input'], e) for s in m['sensitivity'] for e in ('lo', 'hi'))
    w(f'E\'s warmest winding across these ranges is {e_max[0]:.0f} °C (`{e_max[1]}` at its {"high" if e_max[2] == "hi" else "low"} '
      f'end), at 25 °C; B\'s coolest is {b_min[0]:.0f} °C (`{b_min[1]}`). The driving force is the largest lever and an '
      'assumption: log the motors\' torque while driving and balancing (section 7) before trusting the hot-day '
      'margin. The case\'s emissivity and how much of it is shaded move the printed frames most; the bench fit '
      'measures those. The heat capacity and the no-load current do not move a steady state of a held leg (they '
      'shape the transients and the jumps).')
    w('')
    w('## 9. Inputs and their sources')
    w('')
    w('| Input | Value | Source |')
    w('|---|---|---|')
    for k, x in I.items():
        val = x['v']
        sval = json.dumps(val) if not isinstance(val, (int, float)) else f'{val:g}'
        if len(sval) > 60:
            sval = sval[:57] + '...'
        w(f'| `{k}` | {sval.replace("|", "/")} | {x["src"].replace("|", "/")} |')
    w('')
    w('Discovery (adopt or build): cad-agent\'s `cadagent.thermal.heatsink` has the Song-Lee-Au spreading resistance '
      '(adopted, copied: gyropup\'s CI does not install cad-agent) and forced-convection fins; it has no natural '
      'convection, lumped RC network or motor loss model, so those are built here (candidates to move upstream).')
    w('')
    w('Related: [body thermal](body-thermal.md) (the J501 cooler, whose inlet budget this uses), '
      '[body frame](body-frame.md), [RS-04 mounting fit](rs04-mounting-fit.md), [leg bench tests](leg-bench-tests.md).')
    return '\n'.join(L) + '\n'


# ------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='recompute from the JSON\'s recorded loads; exit 1 if stale')
    ap.add_argument('--fit', help='a bench log (CSV: ' + ', '.join(FIT_COLUMNS) + '): fit the case, face and winding numbers')
    ap.add_argument('--option', default='A_pla', choices=list(OPTIONS))
    ap.add_argument('--mount', default='stand', choices=('stand', 'body'))
    a = ap.parse_args(argv)
    if a.fit:
        cal = cal_of(json.loads(OUT.read_text())['calibration'])
        print(json.dumps(refit(read_log(a.fit), cal, a.option, a.mount), indent=1))
        return 0
    if a.check:
        old = json.loads(OUT.read_text())
        m = _plain(model(old['loads']))
        ok = m == old and DOC.read_text() == render(m)
        print('motor thermal model: ' + ('current' if ok else 'STALE: run .venv/bin/python sim/motor_thermal.py'))
        return 0 if ok else 1
    m = _plain(model(loads()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, indent=1) + '\n')
    DOC.write_text(render(m))
    rec = m['recommendation']
    for r in rec['rows']:
        print(f"{r['option']}: winding {r['winding_c']} C, face {r['face_c']} C, body {r['body_c']} C, "
              f"body air {r['into_body_air_w']} W: {'pass' if r['passes'] else 'FAIL'}")
    print('choice:', rec['choice'], '| PLA bench limits:', m['bench']['limits'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
