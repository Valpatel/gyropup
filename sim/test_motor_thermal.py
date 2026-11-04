#!/usr/bin/env python3
"""Checks of the RS-04 motor thermal model (sim/motor_thermal.py, issue #194): golden vectors for its equations, a hand
check of a calibration case, the network solver against closed forms, the bench re-fit on a synthetic log, and the
committed JSON and page against a fresh run. Standard library only (CadQuery only for the geometry cross-check).

    python3 sim/test_motor_thermal.py            # or: .venv/bin/python -m pytest sim/test_motor_thermal.py -q
"""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import motor_thermal as mt  # noqa: E402

M = json.loads(mt.OUT.read_text())


class Losses(unittest.TestCase):
    def test_copper_loss_golden(self):
        """1.5 I^2 R_line: 40 N m / 2.1 = 19.048 A rms; 1.5 x 362.81 x 0.16 = 87.07 W at 25 C; R x (1 + 0.00393 x 120)
        = x 1.4716 at the 145 C limit: 128.13 W."""
        self.assertAlmostEqual(mt.copper_loss(40.0, 25.0), 87.075, places=2)
        self.assertAlmostEqual(mt.copper_loss(40.0, 145.0), 128.14, places=1)
        self.assertAlmostEqual(mt.copper_loss(-40.0, 25.0), mt.copper_loss(40.0, 25.0))      # the sign of the torque

    def test_resistance_tempco(self):
        self.assertAlmostEqual(mt.r_line(100.0), 0.16 * (1 + 0.00393 * 75), places=9)
        self.assertAlmostEqual(mt.r_line(25.0), 0.16, places=12)

    def test_drag_and_driver(self):
        """kt I0 omega: 2.1 x 0.7 x (200 rpm = 20.944 rad/s) = 30.79 W; the driver 2 W + 3 x (10 A)^2 x 4 mohm = 3.2 W."""
        self.assertAlmostEqual(mt.drag_loss(200.0), 30.788, places=2)
        self.assertEqual(mt.drag_loss(0.0), 0.0)
        self.assertAlmostEqual(mt.driver_loss(21.0), 3.2, places=9)


class HeatTransfer(unittest.TestCase):
    def test_vertical_plate_hand_check(self):
        """Churchill-Chu by hand, L 0.1 m, 60 C wall, 20 C air (film 40 C): k 0.02714, nu 1.69e-5, beta 1/313.15;
        Ra = 9.81 x 40 x 1e-3 / (313.15 x 2.856e-10) x 0.71 = 3.115e6; Ra^(1/6) = 12.09; the Pr term 1.1929;
        Nu = (0.825 + 0.387 x 12.09 / 1.1929)^2 = 22.54; h = 22.54 x 0.02714 / 0.1 = 6.12 W/m2K."""
        self.assertAlmostEqual(mt.h_vertical(0.1, 60.0, 20.0), 6.12, delta=0.02)

    def test_cylinder_and_horizontal(self):
        h = mt.h_cylinder(0.12, 80.0, 25.0)
        self.assertTrue(5.0 < h < 7.5, h)                            # a O120 can, 55 K over the air: textbook 5-7 W/m2K
        up, down = mt.h_horizontal(0.1, 60.0, 20.0, 'up'), mt.h_horizontal(0.1, 60.0, 20.0, 'down')
        self.assertGreater(up, 1.8 * down)                           # a hot face down sheds about half

    def test_radiation_golden(self):
        """eps sigma (Ts^2 + Ta^2)(Ts + Ta) at 100 C to 0 C, eps 1: 5.670e-8 x 213852 x 646.3 = 7.837 W/m2K."""
        self.assertAlmostEqual(mt.h_radiation(1.0, 100.0, 0.0), 7.837, places=2)
        self.assertAlmostEqual(mt.h_radiation(0.1, 100.0, 0.0), 0.7837, places=3)

    def test_spreading_limits(self):
        """Song-Lee-Au: a source as large as the plate has no spreading, only t / (k A); a small source on a thin plate
        spreads more than a large one."""
        t, k, A = 0.006, 167.0, 0.01
        self.assertAlmostEqual(mt.spreading_resistance(k, t, A, A, 20.0), t / (k * A), places=9)
        self.assertGreater(mt.spreading_resistance(k, t, 0.001, A, 20.0), mt.spreading_resistance(k, t, 0.004, A, 20.0))


class Solver(unittest.TestCase):
    def test_one_node_closed_form(self):
        """C dT/dt = P - G (T - Ta): steady Ta + P / G; after one time constant 63.2 % of the rise (backward Euler,
        dt = tau / 200: within 0.3 %)."""
        net = mt.Network(20.0)
        net.node('n', 1000.0)
        net.link('n', 'amb', 2.0)
        net.source('n', 50.0)
        self.assertAlmostEqual(net.steady()['n'], 45.0, places=6)
        tau = 500.0
        r = net.transient(tau, tau / 200, record=[tau])
        self.assertAlmostEqual((r['samples'][tau]['n'] - 20.0) / 25.0, 1 - math.exp(-1), delta=0.003)

    def test_two_nodes_in_series(self):
        net = mt.Network(0.0)
        net.node('a', 10.0)
        net.node('b', 10.0)
        net.link('a', 'b', 0.5)
        net.link('b', 'amb', 0.25)
        net.source('a', 3.0)
        T = net.steady()
        self.assertAlmostEqual(T['b'], 12.0, places=6)
        self.assertAlmostEqual(T['a'], 18.0, places=6)

    def test_hot_spot_excess(self):
        """A held motor's hottest phase: (f - 1) P_cu R_wc over the winding node at steady state; none when turning."""
        cal = mt.cal_of(M['calibration'])
        tau = 16.0
        held, face = mt.leg_network(cal, 'B_pa6cf', {'tau': tau, 'rpm': 0.0}, 2.0, 25.0)
        T = held.steady()
        self.assertAlmostEqual(T['X'], mt.copper_loss(tau, T['W']) * cal['r_wc'], delta=0.05)
        turning, _ = mt.leg_network(cal, 'B_pa6cf', {'tau': tau, 'rpm': 30.0}, 1.0, 25.0)   # a turning motor: f = 1
        Tt = turning.steady()
        self.assertAlmostEqual(Tt['X'], 0.0, places=6)
        self.assertGreater(Tt['C'], T['C'])                                   # its drag loss warms the case


class Calibration(unittest.TestCase):
    def test_rating_a_hand_check(self):
        """The 345 mm rating by hand from the fitted R_wc: P_cu at 145 C = 128.13 W, the drag 2.1 x 0.7 x 5.236 = 7.70 W,
        the driver 2 + 3 x 19.05^2 x 0.004 = 6.35 W: 142.2 W. The winding is P_cu x R_wc over the case, so the case
        is 145 - 128.13 x R_wc."""
        c = M['calibration']
        self.assertAlmostEqual(c['rating_a']['winding_c'], 145.0, delta=0.05)
        self.assertAlmostEqual(c['rating_a']['loss_w'], 128.13 + 7.70 + 6.35, delta=0.15)
        self.assertAlmostEqual(c['rating_a']['case_c'], 145.0 - 128.13 * c['r_wc_k_per_w'], delta=0.15)

    def test_fit_is_physical(self):
        c = M['calibration']
        self.assertTrue(0.3 < c['r_wc_k_per_w'] < 0.5, c)
        self.assertTrue(50.0 < c['c_w_j_per_k'] < 130.0, c)        # 0.13-0.34 kg of copper
        self.assertLess(abs(c['rating_b']['winding_c'] - 145.0), 5.0)
        self.assertLess(c['overload_rms_log_error'], 0.25)

    def test_emissivity_bound_is_the_conservative_end(self):
        """The fit's emissivity sits at its bound; any less emissive test plate gives a lower R_wc and cooler windings."""
        c = M['calibration']
        for s in M['calibration_spread']:
            if s['eps_fixed'] is not None:
                self.assertLess(s['r_wc_k_per_w'], c['r_wc_k_per_w'])
                self.assertLess(s['worst_winding_c']['B_pa6cf'], M['results'][M['worst_case']]['B_pa6cf']['steady']['winding_c'])

    def test_stall_ceiling_is_the_firmware(self):
        """The heat alone would allow more than the stall table's 28.5 N m: the locked-rotor protection is the limit,
        and every robot case holds under it."""
        self.assertLess(M['calibration']['stall_rated_model_winding_c'], 145.0)
        for c in M['loads']['cases'].values():
            self.assertLess(max(c['tau_front'], c['tau_rear']), mt.v('stall_rated_nm'))


class Inputs(unittest.TestCase):
    def test_horizontal_plates_use_area_over_perimeter(self):
        """Incropera 9.30-9.32: L = A / P; the tray 320 x 254 mm gives 70.8 mm."""
        tray = [s for s in mt.v('body_surfaces') if s[0].startswith('tray')][0]
        self.assertAlmostEqual(tray[2], 0.320 * 0.254 / (2 * (0.320 + 0.254)), places=9)
        self.assertAlmostEqual(tray[2], 0.0708, places=4)

    def test_drive_force_at_the_contact_patch(self):
        """A fore-aft tyre force on a hub-motor wheel adds its moment about the axle: the driving case's torque is
        above the vertical load's alone at the same leg length (recorded by loads(), at_axle=False)."""
        d = M['loads']['cases']['drive']
        self.assertGreater(max(d['tau_front'], d['tau_rear']), 18.0)
        self.assertGreater(d['tau_front'], d['tau_rear'])
        for i, key in enumerate(('tau_front', 'tau_rear')):     # the recorded parts rebuild the case (the sensitivity uses them)
            self.assertAlmostEqual(math.hypot(d['tau_static'][i], d['dtau_dfx'][i] * d['fx_n']), d[key], delta=0.01)

    def test_stand_blocks_the_whole_rear_face(self):
        """On the stand the plywood covers the whole O94 rear face; on the robot the cheek covers its overlap only: the
        stand's case sheds less at the same temperature."""
        cal = mt.cal_of(M['calibration'])
        T = {'C': 70.0, 'amb': 25.0}
        g = {}
        for mount in ('stand', 'body'):
            net, _ = mt.leg_network(cal, 'A_pla', {'tau': 8.0, 'rpm': 0.0}, 2.0, 25.0, mount)
            g[mount] = [f(T) for a, b, f in net.links if (a, b) == ('C', 'amb')][0]
        hf = mt.h_vertical(mt.v('rear_cover_d_m'), 70.0, 25.0) + mt.h_radiation(mt.v('eps_case'), 70.0, 25.0)
        self.assertAlmostEqual(g['body'] - g['stand'],
                               hf * (mt.can_areas()['rear_face'] - mt.v('rear_overlap_m2')), places=9)


class Results(unittest.TestCase):
    def test_ordering(self):
        """Metal beats printed; PLA is the warmest; the pad heats the body more than the isolated plate."""
        for ck, r in M['results'].items():
            w = {o: r[o]['steady']['winding_c'] for o in r}
            self.assertGreater(w['A_pla'], w['B_pa6cf'], ck)
            self.assertGreater(w['B_pa6cf'], w['C_al_plate'], ck)
            self.assertGreater(r['D_pa6cf_pad']['steady']['body_c'], r['E_al_plate_black_iso']['steady']['body_c'], ck)

    def test_recommendation(self):
        rec = M['recommendation']
        self.assertEqual(rec['choice'], 'E_al_plate_black_iso')
        rows = {r['option']: r for r in rec['rows']}
        self.assertFalse(rows['B_pa6cf']['passes'])
        self.assertLessEqual(rows['E_al_plate_black_iso']['winding_c'], rec['target_winding_c'])

    def test_bench_limit_is_consistent(self):
        """At the fitted continuous limit the PLA face sits at 50 C; the limit falls as the room warms."""
        cal = mt.cal_of(M['calibration'])
        lim = {x['room_c']: x['torque_nm'] for x in M['bench']['limits']}
        self.assertAlmostEqual(mt.bench_face(cal, lim[25.0], 25.0), 50.0, delta=0.3)
        self.assertGreater(lim[20.0], lim[25.0])
        self.assertGreater(lim[25.0], lim[30.0])
        cap = M['bench']['runs']['cap']
        self.assertGreater(cap['steady']['face_c'], 50.0)
        self.assertIsNotNone(cap['t_face_limit_s'])


class Refit(unittest.TestCase):
    def test_recovers_known_numbers(self):
        """A synthetic bench log made with known numbers (case convection x 0.8, face contact 1500 W/m2K, R_wc 0.45):
        the fit finds them again."""
        cal = mt.cal_of(M['calibration'])
        true = {'can_air_factor': 0.8, 'h_contact_polymer': 1500.0, 'r_wc': 0.45}
        saved = {k: mt.INPUTS[k]['v'] for k in ('can_air_factor', 'h_contact_polymer')}
        rows = [{'t_s': float(t), 'tau_nm': 9.0 if t < 1800 else 0.0, 'room_c': 24.0, 'motor_c': None, 'case_c': 24.0,
                 'face_c': None} for t in range(0, 3001, 60)]
        try:
            mt.INPUTS['can_air_factor']['v'] = true['can_air_factor']
            mt.INPUTS['h_contact_polymer']['v'] = true['h_contact_polymer']
            sim = mt.simulate_log(dict(cal, r_wc=true['r_wc']), rows)
        finally:
            for k, x in saved.items():
                mt.INPUTS[k]['v'] = x
        for r, s in zip(rows, sim):
            r['motor_c'], r['case_c'], r['face_c'] = s
        fit = mt.refit(rows, cal)
        self.assertAlmostEqual(fit['can_air_factor'], 0.8, delta=0.04)
        self.assertAlmostEqual(fit['r_wc_k_per_w'], 0.45, delta=0.03)
        self.assertLess(fit['rms_k']['case'], 0.1)
        self.assertLess(fit['rms_k']['face'], 0.1)


class Geometry(unittest.TestCase):
    def test_inputs_match_the_cad(self):
        """The model's leg geometry is what cad/fivebar.py draws (skipped without CadQuery)."""
        try:
            sys.path.insert(0, str(HERE.parent / 'cad'))
            import fivebar as fb
        except ImportError:
            self.skipTest('CadQuery not installed')
        y0, y1 = fb.Y['frame']
        self.assertAlmostEqual(mt.v('web_t_m'), (y1 - y0) / 1000, places=4)
        self.assertAlmostEqual(mt.v('flange_len_m'), (y0 - fb.Y['centre_plane']) / 1000, places=4)
        self.assertAlmostEqual(mt.v('flange_x_m'), fb.FLANGE_X / 1000, places=6)
        self.assertEqual(mt.v('flange_t_m'), (fb.HIP['top_t'] / 1000, fb.HIP['bottom_t'] / 1000))
        self.assertAlmostEqual(mt.v('rear_gap_m'), (fb.Y['motor'][0] - fb.Y['centre_plane']) / 1000, places=4)
        self.assertAlmostEqual(mt.v('face_bore_d_m'), (fb.AC['bearing_od'] + 0.6) / 1000, places=6)


class Regeneration(unittest.TestCase):
    def test_committed_json_and_page_are_current(self):
        """exports/leg/thermal/motor_thermal.json and docs/motor-thermal.md equal a fresh run on the JSON's own loads."""
        m = mt._plain(mt.model(M['loads']))
        self.assertEqual(m, M, 'stale JSON: run .venv/bin/python sim/motor_thermal.py')
        self.assertEqual(mt.DOC.read_text(), mt.render(m), 'stale page: run .venv/bin/python sim/motor_thermal.py')


if __name__ == '__main__':
    unittest.main(verbosity=2)
