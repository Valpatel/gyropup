"""B8's acceptance in the HIL (docs/body-next-plan.md 4.1): the firmware's host build against the leg rig's emulated
RS-04s and MuJoCo rig (hil/harness.py).

    cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host
    python -m pytest firmware/balance/hil -q                 # needs MuJoCo, CadQuery and the rig package

  1. stand_up replayed within 5 % of leg length and lean of sim/leg_rig.py run() at 16.25 kg and 36 V;
  2. the 10S windows (D65, gp_config.h) on a falling pack: the warning at 35.0 V, the jump gate closing at 34.0 V, the
     sit at 32.0 V (resting), the cut-off at 30.0 V (under load, latched); and the cut-off on a sudden drop while standing;
  3. the jump gate: full jumps at 41.0 V, a current-limited one at 36.0 and 34.1 V (the bus kept over the 31 V floor),
     none at 33.9 V; the bus current limit holding a jump's push under a lowered peak;
  4. the radio stop, the Jetson's heartbeat, people near;
  5. the robot profile balancing sim/robot_v2.py's model like sim/controller_v2.py (hil/sil_robot.py).
Each test writes its numbers into hil/hil-results.json. Skipped (with the reason) when the `rig` package (legrig/program,
GYROPUP_RIG_DIR) or the host library is not there; CI builds and unit-tests the firmware but does not run these.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fwlib  # noqa: E402

if fwlib.find_library() is None:
    pytest.skip('libgp_host.so is not built (cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host)',
                allow_module_level=True)
try:
    import mujoco  # noqa: F401
    import harness  # noqa: E402
    harness.import_rig()
except ImportError as e:  # pragma: no cover
    pytest.skip(f'the HIL needs MuJoCo and the leg rig package (legrig/program, GYROPUP_RIG_DIR): {e}', allow_module_level=True)

RESULTS = HERE / 'hil-results.json'
MODE = {n: i for i, n in enumerate(fwlib.MODES)}


def record(key: str, value) -> None:
    doc = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    doc[key] = value
    doc['made_by'] = 'python -m pytest firmware/balance/hil (firmware/balance/hil/test_hil.py)'
    doc['conditions'] = {'half_mass_kg': harness.DESIGN_HALF_MASS, 'bus_v': harness.DESIGN_BUS_V, 'pack_r_int_ohm': harness.R_PACK,
                         'loop_hz': 1000, 'legs': 'two rigs (sim/leg_rig.py through rig/sim_bus.py), one per bus'}
    RESULTS.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')


def first(log: dict, pred, start: int = 0):
    return next((k for k in range(start, len(log['t'])) if pred(k)), None)


# ---------------------------------------------------------------------------------------------- 1. stand_up

def test_stand_up_matches_the_simulation():
    ref = harness.reference_stand_up()
    h = harness.Hil('stand_up')
    run = h.run(3.0)
    left = harness.compare(run, ref)
    right = harness.compare({'t': run['t'], 'L': run['L_r'], 'lean': run['lean_r']}, ref)
    rigc = harness.compare(harness.rig_controller_stand_up(), ref)
    s = h.fw.snapshot()
    record('stand_up', {'firmware_left_leg': left, 'firmware_right_leg': right, 'rig_controller_same_hil': rigc,
                        'boot_ms': h.boot_ticks, 'tx_drops': s.tx_drops, 'misses': list(s.misses),
                        'criterion': 'worst |dL| / L_ref <= 0.05 and worst |d lean| <= 0.05 rad (the axle 5 % of the leg off line)'})
    assert s.tx_drops == 0 and max(s.misses) == 0
    for r in (left, right, rigc):
        assert r['worst_L_rel'] <= 0.05, r
        assert r['worst_lean_rad'] <= 0.05, r


# ---------------------------------------------------------------------------------------------- 2. the 10S windows

def test_windows_trip_at_their_numbers_on_a_falling_pack():
    """D65's windows on a pack falling 0.2 V/s from 35.7 V: warn 35.0, no jump under 34.0, sit 32.0 (resting), and the
    cut-off at 30.0 V under load, which latches in idle until the power cycle."""
    rate, v0, v_end, t0 = 0.2, 35.7, 29.6, 2.0     # V/s; the resting filter lags rate x 1 s = 0.2 V, the cut-off's 0.02 V

    def each(h, t, _):
        if t >= t0:
            h.v_oc = max(v_end, v0 - rate * (t - t0))

    h = harness.Hil('stand_up', bus_v=v0)
    log = h.run(t0 + (v0 - v_end) / rate + 1.0, each=each)
    start = first(log, lambda k: log['t'][k] >= t0)
    warn = first(log, lambda k: log['flags'][k] & fwlib.FLAG_UVLO_WARN, start)
    jump_off = first(log, lambda k: not log['flags'][k] & fwlib.FLAG_JUMP_OK, start)
    sit = first(log, lambda k: log['mode'][k] == MODE['sit'], start)
    idle = first(log, lambda k: log['mode'][k] == MODE['idle'], start)
    cut = first(log, lambda k: log['cutoff'][k], start)
    out = {}
    # the resting windows against the pack's open-circuit voltage, the cut-off against the bus on the wire (under load)
    for name, k, thr, key, ref, lag in (('warn', warn, 35.0, 'vrest', 'v_oc', 0.25), ('jump_refused', jump_off, 34.0, 'vrest', 'v_oc', 0.25),
                                        ('sit', sit, 32.0, 'vrest', 'v_oc', 0.25), ('cutoff', cut, 30.0, 'vload', 'vbus', 0.05)):
        assert k is not None, name
        out[name] = {'threshold_v': thr, 'firmware_estimate': key, 'estimate_v': round(log[key][k], 4),
                     'estimate_v_tick_before': round(log[key][k - 1], 4), 'pack_open_circuit_v': round(log['v_oc'][k], 4),
                     'bus_v_on_the_wire': round(log['vbus'][k], 3), 't_s': round(log['t'][k], 3), 'mode': fwlib.MODES[log['mode'][k]]}
        assert log[key][k] < thr <= log[key][k - 1], (name, out[name])
        assert thr - lag <= log[ref][k] <= thr, (name, out[name])
    assert log['reason'][sit] == 4                              # UVLO
    assert idle is not None and log['L'][idle] < 0.16           # sat on the rig's 150 mm, then the motors stopped
    assert not log['mcu_run'][sit]
    assert idle < cut and log['mode'][-1] == MODE['idle'] and log['cutoff'][-1]
    out['sat_leg_mm'] = round(log['L'][idle] * 1000, 1)
    out['ramp_v_per_s'] = rate
    out['note'] = ('warn, jump and sit trip on the resting estimate (V + I x 0.100 ohm, 1 s filter), which on a falling '
                   'pack lags by ramp x 1 s; the cut-off on the loaded bus (0.1 s filter)')
    record('uvlo', out)


def test_cutoff_under_load_sits_and_latches_until_power_cycle():
    """A pack that drops from 34.0 V to 29.5 V while standing (a dock's contact, a collapsing cell): the cut-off trips
    at 30.0 V under load before the resting estimate (1 s) reaches the sit, sits, stops the motors and stays latched;
    a fresh pack and a new RUN from the Jetson do not stand it up."""
    st = {}

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            h.v_oc = 29.5
            st['k'] = len(seen)
        if t >= 4.0 and 'fresh' not in st:
            h.v_oc = 41.0                                     # a fresh pack on the wire, the Jetson tries again
            h.jetson.run = False
            st['fresh'] = True
        if t >= 5.0 and 'rerun' not in st:
            h.jetson.run = True
            st['rerun'] = True
        seen.append(t)

    seen = []
    h = harness.Hil('stand_up', bus_v=34.0)
    log = h.run(6.5, each=each)
    k = st['k']
    cut = first(log, lambda j: log['cutoff'][j], k)
    idle = first(log, lambda j: log['mode'][j] == MODE['idle'], k)
    res = {'trip_after_drop_ms': round((log['t'][cut] - log['t'][k]) * 1000, 1), 'vload_at_trip': round(log['vload'][cut], 3),
           'vload_tick_before': round(log['vload'][cut - 1], 3), 'vrest_at_trip': round(log['vrest'][cut], 3),
           'reason': fwlib.REASONS[log['reason'][idle]], 'motors_stopped_ms': round((log['t'][idle] - log['t'][k]) * 1000, 1),
           'leg_at_stop_mm': round(log['L'][idle] * 1000, 1), 'mode_at_end': fwlib.MODES[log['mode'][-1]],
           'mcu_run_at_end': bool(log['mcu_run'][-1])}
    record('cutoff', res)
    assert log['vload'][cut] < 30.0 <= log['vload'][cut - 1]
    assert log['vrest'][cut] > 32.0                            # the resting estimate had not sat it yet
    assert res['reason'] == 'cut-off' and res['leg_at_stop_mm'] < 165.0
    assert res['mode_at_end'] == 'idle' and not res['mcu_run_at_end'] and log['cutoff'][-1]


# ---------------------------------------------------------------------------------------------- 3. the jump gate

@pytest.mark.parametrize('v', [41.0, 36.0, 34.1, 33.9])
def test_jump_gate(v):
    st, cur = {}, []

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            st['k'] = len(seen)
            h.jetson.jump(15)
        seen.append(t)
        cur.append(h.ibus)

    seen = []
    h = harness.Hil('stand_up', bus_v=v)
    log = h.run(4.2, each=each)
    k = st['k']
    rise = max(log['rail_mm'][k:]) - log['rail_mm'][k]
    s = h.fw.snapshot()
    res = {'jumped': bool(s.jumps), 'refused': fwlib.JUMP_REFUSALS[s.jump_refusal] if s.jumps_refused else None,
           'scale': round(s.jump_scale, 4), 'push_bus_current_limit_a': round(s.push_ilimit, 2),
           'rise_above_standing_mm': round(rise, 1), 'bus_v_min_in_the_jump': round(min(log['vbus'][k:]), 2),
           'bus_a_max_in_the_jump': round(max(cur[k:]), 1), 'cutoff': bool(s.cutoff), 'mode_after': fwlib.MODES[s.mode]}
    doc = json.loads(RESULTS.read_text()).get('jump_gate', {}) if RESULTS.exists() else {}
    doc = {key: val for key, val in doc.items() if float(key.split()[0]) < 42.0}     # the 13S entries are gone
    doc[f'{v:.1f} V'] = res
    record('jump_gate', doc)
    if v >= 34.0:
        assert s.jumps == 1 and s.jumps_refused == 0
        assert rise > 80.0
        assert res['bus_v_min_in_the_jump'] > 30.7               # the 31 V floor, a sample's lag under it at most
        assert abs(s.jump_scale - fwlib.Firmware.jump_scale(h.fw, v)) < 0.01
        assert not s.cutoff and res['mode_after'] == 'run'
    else:
        assert s.jumps == 0 and s.jumps_refused == 1 and s.jump_refusal == 2
        assert rise < 5.0


def test_bus_current_limit_scales_a_jump_rather_than_tripping():
    """The INA228's bus current limit with GP_BUS_I_PEAK_A lowered to 50 A: a full-pack jump (72 A unlimited) is held
    at the limit by scaling the motors' commands (ms_over_the_limit: the samples a few % over it as it regulates);
    it still jumps, nothing trips."""
    st, cur = {}, []

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            st['k'] = len(seen)
            h.jetson.jump(15)
        seen.append(t)
        cur.append(h.ibus)

    seen = []
    h = harness.Hil('stand_up', bus_v=41.0, i_peak=50.0)
    log = h.run(4.2, each=each)
    k = st['k']
    s = h.fw.snapshot()
    rise = max(log['rail_mm'][k:]) - log['rail_mm'][k]
    over = [c for c in cur[k:] if c > 50.0]
    res = {'i_peak_a': 50.0, 'bus_a_max': round(max(cur[k:]), 1), 'ms_over_the_limit': len(over),
           'bus_scale_min': round(min(log['bus_scale'][k:]), 3), 'rise_above_standing_mm': round(rise, 1),
           'mode_after': fwlib.MODES[s.mode], 'reason': fwlib.REASONS[s.reason]}
    record('bus_current_limit', res)
    assert s.jumps == 1 and rise > 80.0 and res['mode_after'] == 'run'
    assert res['bus_a_max'] < 50.0 * 1.05                    # it regulates at the limit, an INA228 sample (2 ms) behind
    assert res['bus_scale_min'] < 1.0


# ---------------------------------------------------------------------------------------------- 4. the stop, the link, people

def test_radio_stop_sits_within_half_a_second_and_opens_mcu_run():
    st = {}

    def each(h, t, _):
        if t >= 2.0:
            h.stop_run = False
            st.setdefault('k', len(seen))
        seen.append(t)

    seen = []
    h = harness.Hil('stand_up')
    log = h.run(3.0, each=each)
    k = st['k']
    off = first(log, lambda j: not log['mcu_run'][j], k)
    idle = first(log, lambda j: log['mode'][j] == MODE['idle'], k)
    res = {'mcu_run_open_ms': round((log['t'][off] - log['t'][k]) * 1000, 1), 'motors_stopped_ms': round((log['t'][idle] - log['t'][k]) * 1000, 1),
           'leg_at_stop_mm': round(log['L'][idle] * 1000, 1), 'reason': fwlib.REASONS[log['reason'][idle]]}
    record('radio_stop', res)
    assert res['mcu_run_open_ms'] <= 3.0
    assert res['motors_stopped_ms'] <= 500.0 and res['leg_at_stop_mm'] < 165.0 and res['reason'] == 'stop'


def test_heartbeat_lost_balances_two_seconds_then_sits():
    st = {}

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            h.jetson.link = False
            st['k'] = len(seen)
        seen.append(t)

    seen = []
    h = harness.Hil('stand_up')
    log = h.run(5.5, each=each)
    k = st['k']
    sit = first(log, lambda j: log['mode'][j] == MODE['sit'], k)
    res = {'sit_after_last_setpoint_s': round(log['t'][sit] - log['t'][k], 3), 'reason': fwlib.REASONS[log['reason'][sit]]}
    record('heartbeat', res)
    assert res['reason'] == 'link' and 2.18 <= res['sit_after_last_setpoint_s'] <= 2.22


def test_people_near_refuses_jumps_and_sits_after_two_seconds():
    st = {}

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            h.jetson.people = True
            st['k'] = len(seen)
        if t >= 2.5 and 'j' not in st:
            h.jetson.jump(15)
            st['j'] = True
        seen.append(t)

    seen = []
    h = harness.Hil('stand_up')
    log = h.run(5.0, each=each)
    k = st['k']
    sit = first(log, lambda j: log['mode'][j] == MODE['sit'], k)
    s = h.fw.snapshot()
    res = {'jump_refused': fwlib.JUMP_REFUSALS[s.jump_refusal], 'sit_after_s': round(log['t'][sit] - log['t'][k], 3),
           'reason': fwlib.REASONS[log['reason'][sit]]}
    record('people_near', res)
    assert s.jumps == 0 and res['jump_refused'] == 'people near'
    assert res['reason'] == 'people' and 1.99 <= res['sit_after_s'] <= 2.03


def test_bridge_carries_frames_both_ways():
    """The transport swap: devices on a VirtualBus reach another transport through a Bridge (here a second VirtualBus
    standing in for SocketCan('can0') on a USB-CAN adapter)."""
    from rig.canio import VirtualBus
    from rig.rs04 import pack_enable
    from rig.rs04_emu import EmulatedRS04
    devices, wire = VirtualBus(), VirtualBus()
    devices.attach(EmulatedRS04(1).handle)
    br = harness.Bridge(devices.port(), wire.port())
    host = wire.port()
    host.send(*pack_enable(1), True)
    br.pump()
    br.pump()
    f = host.recv(0)
    assert f is not None and (f[0] >> 24) == 2 and br.count == [1, 1]


# ---------------------------------------------------------------------------------------------- 5. the whole robot

def test_robot_balances_like_the_simulations_controller():
    """The robot profile on sim/robot_v2.py's model (hil/sil_robot.py): stand, drive 0.5 m/s, stop, crouch, against
    sim/controller_v2.py on the same model; the leg rig cannot check the LQR, the pendulum estimate or the wheel signs."""
    import sil_robot
    if not (sil_robot.BUILD / 'robot.xml').exists():
        pytest.skip('build/sim/v2 is missing: python -m sim.robot_v2')
    res = sil_robot.summary(sil_robot.run_firmware(), sil_robot.run_python())
    record('robot_sil', res)
    assert not res['fell'] and res['final_mode'] == 'run'
    assert res['worst_diff_x'] < 0.05 and res['worst_diff_v'] < 0.05 and res['worst_diff_L'] < 0.005
    assert res['worst_diff_theta'] < 1.0 and res['theta_estimate_error_deg'] < 0.2
    assert res['imu_pitch_rate_error'] < 0.05                # rad/s: the emulated gyro agrees with its own attitude
    assert res['at_3.9s']['v_fw'] > 0.4                     # it drove forward when asked to
