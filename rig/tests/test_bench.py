"""The bench scripts (B1 back-drive, B2 spin-down, the calibration, the parameter fits) against the software RS-04, on
a simulated clock so they run in a moment.

    .venv/bin/python -m pytest rig/tests -q
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from rig import canio
from rig import rs04 as P
from rig.bench import backdrive, fit_params, spin_down
from rig.rs04_emu import EmulatedRS04


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, dt):
        self.t += dt


def one_motor(mid=2, clock=None, **kw):
    vb = canio.VirtualBus()
    emu = EmulatedRS04(mid, **(dict(kw, clock=clock) if clock else kw))
    vb.attach(emu.handle)
    return P.RS04Bus(vb.port()), emu


# ----------------------------------------------------------------------------------- B1

def drag_load(c=0.8, b=3.0):
    return lambda w: c * (1 if w > 0 else -1 if w < 0 else 0) + b * w


def test_backdrive_sweep_and_fit_recover_the_coupled_motors_drag():
    """The driver's own friction (spider out), then the driver turning a motor whose drag is 0.8 sign(w) + 3 w: the
    difference is the drag, both ways, and the fit gives back c and b."""
    speeds = (1.0, 4.0, 10.0)
    clk = Clock()
    bus, emu = one_motor(clock=clk)
    friction = backdrive.sweep(bus, 2, speeds, settle=0.5, hold=0.3, clock=clk, sleep=clk.sleep)
    assert [r['speed_cmd'] for r in friction] == [1.0, 4.0, 10.0, -1.0, -4.0, -10.0]
    for r in friction:                                      # the driver alone: its own friction, 0.3 + 0.05 w
        assert r['speed'] == pytest.approx(r['speed_cmd'], abs=0.01)
        assert r['torque'] == pytest.approx(math.copysign(0.3 + 0.05 * abs(r['speed']), r['speed']), abs=0.02)
    clk2 = Clock()
    bus2, emu2 = one_motor(clock=clk2, load=drag_load())
    coupled = backdrive.sweep(bus2, 2, speeds, settle=0.5, hold=0.3, clock=clk2, sleep=clk2.sleep)
    for r in backdrive.drag(coupled, friction):
        assert r['drag_nm'] == pytest.approx(drag_load()(r['speed']), abs=0.03)
    f = backdrive.fit(coupled, friction)
    assert f['coulomb_nm'] == pytest.approx(0.8, abs=0.03) and f['b_nm_s_rad'] == pytest.approx(3.0, abs=0.01)
    assert emu2.mode == 0 and emu2.params['run_mode'] == 0  # left stopped and back in MIT mode


def test_backdrive_stops_a_direction_once_the_drag_passes_the_limit():
    clk = Clock()
    bus, emu = one_motor(clock=clk, load=drag_load(0.0, 8.0))
    rows = backdrive.sweep(bus, 2, (1.0, 4.0, 10.0), settle=0.5, hold=0.3, stop_nm=20.0, clock=clk, sleep=clk.sleep)
    assert [r['speed_cmd'] for r in rows] == [1.0, 4.0, -1.0, -4.0]     # 4 rad/s is 32 N m: 10 rad/s never runs


# ----------------------------------------------------------------------------------- B2

def test_spin_down_fit_recovers_inertia_and_friction():
    clk = Clock()
    bus, emu = one_motor(mid=1, clock=clk, inertia=0.0243, friction=0.3, viscous=0.05)
    rec = spin_down.record(bus, 1, tau=2.0, clock=clk, step=clk.sleep)
    assert max(abs(w) for w in rec['w']) < 9.0               # the push ended at 8 rad/s: clear of the 15 rad/s field limit
    f = spin_down.fit(rec)
    assert f['J_kg_m2'] == pytest.approx(0.0243, rel=0.03)
    assert f['coulomb_nm'] == pytest.approx(0.3, abs=0.03) and f['viscous_nm_s_rad'] == pytest.approx(0.05, abs=0.01)
    assert emu.mode == 0


# ----------------------------------------------------------------------------------- the calibration

def calibration_bus(dirs=(1, -1), starts=(0.7, -1.1), error_deg=0.0):
    from rig import calibrate as C
    vb = canio.VirtualBus()
    emus = {1: EmulatedRS04(1, plant=None), 2: EmulatedRS04(2, plant=None)}
    for e in emus.values():
        vb.attach(e.handle)
    fo, fi, ro, ri = C.bare_stop_angles()
    script = [(1, starts[0]), (1, starts[0] + dirs[0] * (fi - fo + math.radians(error_deg))),
              (2, starts[1]), (2, starts[1] + dirs[1] * (ri - ro))]
    prompts = []

    def ask(msg):                                           # the operator moves the link to where the prompt says
        mid, a = script[len(prompts)]
        prompts.append(msg)
        emus[mid].angle = a
        return ''
    return P.RS04Bus(vb.port()), emus, ask, prompts, (fo, fi, ro, ri)


def test_calibrate_zeroes_on_the_bare_posts_and_finds_each_direction():
    from rig import calibrate as C
    bus, emus, ask, prompts, (fo, fi, ro, ri) = calibration_bus()
    lines = []
    cal = C.calibrate(bus, 1, 2, ask=ask, out=lines.append)
    assert len(prompts) == 4 and 'knee-out' in prompts[0] and 'knee-in' in prompts[1]
    assert (cal.front.dir, cal.rear.dir) == (1, -1)
    assert cal.front.phi_zero == pytest.approx(fo) and cal.rear.phi_zero == pytest.approx(ro)
    for mid, mc, want in ((1, cal.front, fi), (2, cal.rear, ri)):  # the reading at the knee-in post maps to its angle
        assert mc.to_leg(P.Motor(bus, mid).read('mechPos')) == pytest.approx(want, abs=1e-3)
        assert emus[mid].saved['zero_sta'] == 1             # written and saved: a power-on angle reads -pi..pi


def test_calibrate_stops_when_the_travel_disagrees_with_the_cad():
    from rig import calibrate as C
    bus, emus, ask, prompts, _ = calibration_bus(error_deg=5.0)
    with pytest.raises(RuntimeError, match='between the posts'):
        C.calibrate(bus, 1, 2, ask=ask, out=lambda s: None)


def test_calibration_round_trips_through_its_file(tmp_path):
    from rig import calibrate as C
    bus, emus, ask, prompts, _ = calibration_bus()
    lines = []
    assert C.main(['--file', str(tmp_path / 'cal.json')], transport=bus.t, ask=ask, out=lines.append) == 0
    d = json.loads((tmp_path / 'cal.json').read_text())
    assert d['front']['dir'] == 1 and d['rear']['dir'] == -1 and lines[-1].startswith('wrote ')


# ----------------------------------------------------------------------------------- the fits

def test_fit_params_reads_the_sheets_and_the_scripts_results(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_params, 'BENCH', tmp_path)
    monkeypatch.setattr(fit_params, 'SHEETS', tmp_path / 'sheets')
    assert fit_params.main(['--templates']) == 0
    assert (tmp_path / 'sheets' / 'b3.csv').read_text().startswith('cycle,force_n,deflection_mm')
    # B3: a 300 N/mm sleeve, 2 cycles, 0.2 mm set
    lines = ['cycle,force_n,deflection_mm']
    for c, z in ((1, 0.0), (2, 0.2)):
        lines += [f'{c},{f},{z + f / 300.0:.4f}' for f in range(0, 2001, 200)]
    (tmp_path / 'sheets' / 'b3.csv').write_text('\n'.join(lines) + '\n')
    # B4: M5 at 1000 N per N m, pull-out 2600 / 2800 N
    (tmp_path / 'sheets' / 'b4.csv').write_text('size,sample,torque_nm,tension_n,pullout_n\n'
                                                'M5,1,1.0,1000,\nM5,1,2.0,2000,\nM5,1,,,2600\nM5,2,,,2800\n')
    # B6: 54 V open, 52.8 V across 10 ohm -> 0.227 ohm
    (tmp_path / 'sheets' / 'b6.csv').write_text('v_open,v_loaded,r_load_ohm\n54.0,52.8,10\n')
    # B1 and B2 as the scripts write them
    clk = Clock()
    bus, _ = one_motor(clock=clk)
    fr = backdrive.sweep(bus, 2, (2.0, 8.0), settle=0.5, hold=0.2, clock=clk, sleep=clk.sleep)
    clk2 = Clock()
    bus2, _ = one_motor(clock=clk2, load=drag_load(0.5, 2.0))
    co = backdrive.sweep(bus2, 2, (2.0, 8.0), settle=0.5, hold=0.2, clock=clk2, sleep=clk2.sleep)
    (tmp_path / 'b1-friction.json').write_text(json.dumps({'condition': 'friction', 'rows': fr}))
    (tmp_path / 'b1-unpowered_damper0.json').write_text(json.dumps({'condition': 'unpowered_damper0', 'rows': co}))
    (tmp_path / 'b2-motor1.json').write_text(json.dumps({'J_kg_m2': 0.026}))
    assert fit_params.main([]) == 0
    doc = json.loads((tmp_path / 'sim-params.json').read_text())
    b3 = doc['B3_sleeve']
    assert b3['k_n_per_mm'] == pytest.approx(300.0, rel=1e-3) and b3['permanent_set_mm'] == pytest.approx(0.2)
    assert b3['STOP_K'] == pytest.approx(300e3 * doc['sim_assumes']['stop_r_m'] ** 2, rel=1e-4)
    m5 = doc['B4_inserts']['M5']
    assert m5['n_per_nm'] == pytest.approx(1000.0) and m5['torque_for_preload_nm'] == pytest.approx(1.2)
    assert m5['nut_factor_K'] == pytest.approx(0.2) and m5['pass_pullout_2x_preload'] is True
    assert doc['B6_pack']['r_int_ohm'] == pytest.approx(0.2273, abs=1e-3)
    b1 = doc['B1_backdrive']['unpowered_damper0']
    assert b1['coulomb_nm'] == pytest.approx(0.5, abs=0.03) and b1['b_nm_s_rad'] == pytest.approx(2.0, abs=0.01)
    assert doc['B2_inertia']['J_kg_m2'] == 0.026 and doc['B5_tyre'] == {}


# ----------------------------------------------------------------------------------- C6

def test_jitter_counts_every_tick_and_stops_the_motors():
    from rig.bench import jitter

    class Creep(Clock):                                     # every look at the clock costs 10 us
        def __call__(self):
            self.t += 1e-5
            return self.t
    clk = Creep()
    vb = canio.VirtualBus()
    emus = {i: EmulatedRS04(i, clock=clk) for i in (1, 2)}
    for e in emus.values():
        vb.attach(e.handle)
    tm = jitter.run(P.RS04Bus(vb.port()), [1, 2], rate=500.0, seconds=0.2, clock=clk, sleep=clk.sleep)
    s = tm.summary()
    assert s['ticks'] == 100 and s['missed'] == 0 and s['within_0p3ms'] == 1.0
    assert all(e.mode == 0 for e in emus.values())
    real = emus[2].handle                                   # motor 2 stops answering its MIT frames (type 1)
    vb.handlers[1] = lambda cid, data, ext=True: [] if (cid >> 24) == P.MIT else real(cid, data, ext)
    tm = jitter.run(P.RS04Bus(vb.port()), [1, 2], rate=500.0, seconds=0.02, clock=clk, sleep=clk.sleep)
    assert tm.missed == 10 and len(tm.rtt_ms) == 0


# ----------------------------------------------------------------------------------- the rig node's firmware

def test_the_node_firmware_packs_frames_as_the_laptop_reads_them():
    import importlib.util
    from rig import node as N
    spec = importlib.util.spec_from_file_location('rig_frames', Path(__file__).resolve().parents[1] / 'firmware' / 'feather_rig' / 'rig_frames.py')
    F = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(F)
    assert (F.RUN, F.SENSE, F.VBUS, F.HOST, F.RUN_CLOSED) == (N.RUN, N.SENSE, N.VBUS, N.HOST, N.RUN_CLOSED)
    for args in ((True, 7, 0b1011), (False, 300, 0)):
        assert F.pack_run(*args) == N.pack_run(*args)
    for args in ((412, 0, 151.26, 9), (70000, 4, -4000.0, 260), (0, 255, 3276.8, 1)):
        assert F.pack_sense(*args) == N.pack_sense(*args)
    assert F.pack_vbus(57.9, 50.1, 54.04, 3) == N.pack_vbus(57.9, 50.1, 54.04, 3)
    st = N.NodeState()
    assert st.take(F.SENSE, F.pack_sense(412, 0, 151.26, 9), 1.0) and st.height_mm == 412 and st.force_n == pytest.approx(151.3)
    assert st.take(F.RUN, F.pack_run(True, 1, 1), 1.0) and st.run_fresh(1.02)
