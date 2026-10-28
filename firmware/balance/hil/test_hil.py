"""B8's acceptance in the HIL (docs/body-next-plan.md 4.1): the firmware's host build against the leg rig's emulated
RS-04s and MuJoCo rig (hil/harness.py).

    cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host
    python -m pytest firmware/balance/hil -q                 # needs MuJoCo, CadQuery and the rig package

  1. stand_up replayed within 5 % of leg length and lean of sim/leg_rig.py run() at 16.25 kg and 48.1 V;
  2. UVLO: the warning at 45.5 V, the jump gate closing at 44.0 V, the sit at 41.6 V (resting), on a falling pack;
  3. the jump gate: a jump at 48.1 V, a scaled one at 44.2 V, none at 43.9 V;
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
    for r in (left, right):
        assert r['worst_L_rel'] <= 0.05, r
        assert r['worst_lean_rad'] <= 0.05, r


# ---------------------------------------------------------------------------------------------- 2. UVLO

def test_uvlo_and_jump_gate_trip_at_their_numbers_on_a_falling_pack():
    rate, v0, t0 = 0.2, 46.2, 2.0          # V/s from 46.2 V once standing; the resting filter lags rate x 1 s = 0.2 V

    def each(h, t, _):
        if t >= t0:
            h.v_oc = max(41.2, v0 - rate * (t - t0))

    h = harness.Hil('stand_up', bus_v=v0)
    log = h.run(t0 + (v0 - 41.2) / rate + 2.0, each=each)
    start = first(log, lambda k: log['t'][k] >= t0)
    warn = first(log, lambda k: log['flags'][k] & fwlib.FLAG_UVLO_WARN, start)
    jump_off = first(log, lambda k: not log['flags'][k] & fwlib.FLAG_JUMP_OK, start)
    sit = first(log, lambda k: log['mode'][k] == MODE['sit'], start)
    idle = first(log, lambda k: log['mode'][k] == MODE['idle'], start)
    out = {}
    for name, k, thr in (('warn', warn, 45.5), ('jump_refused', jump_off, 44.0), ('sit', sit, 41.6)):
        assert k is not None, name
        out[name] = {'threshold_v': thr, 'resting_v_firmware': round(log['vrest'][k], 4),
                     'resting_v_firmware_tick_before': round(log['vrest'][k - 1], 4), 'pack_open_circuit_v': round(log['v_oc'][k], 4),
                     'bus_v_on_the_wire': round(log['vbus'][k], 3), 't_s': round(log['t'][k], 3)}
        assert log['vrest'][k] < thr <= log['vrest'][k - 1], (name, out[name])
        assert thr - 0.25 <= log['v_oc'][k] <= thr, (name, out[name])
    assert log['reason'][sit] == 4                              # UVLO
    assert idle is not None and log['L'][idle] < 0.16           # sat on the rig's 150 mm, then the motors stopped
    assert not log['mcu_run'][sit]
    out['sat_leg_mm'] = round(log['L'][idle] * 1000, 1)
    out['ramp_v_per_s'] = rate
    out['note'] = 'the firmware trips on its resting-voltage estimate (V + I x 0.112 ohm, 1 s filter); on a falling pack it lags by ramp x 1 s'
    record('uvlo', out)


# ---------------------------------------------------------------------------------------------- 3. the jump gate

@pytest.mark.parametrize('v', [48.1, 44.2, 43.9])
def test_jump_gate(v):
    st = {}

    def each(h, t, _):
        if t >= 2.0 and 'k' not in st:
            st['k'] = len(seen)
            h.jetson.jump(15)
        seen.append(t)

    seen = []
    h = harness.Hil('stand_up', bus_v=v)
    log = h.run(4.2, each=each)
    k = st['k']
    rise = max(log['rail_mm'][k:]) - log['rail_mm'][k]
    s = h.fw.snapshot()
    res = {'jumped': bool(s.jumps), 'refused': fwlib.JUMP_REFUSALS[s.jump_refusal] if s.jumps_refused else None,
           'takeoff_speed_cap_m_s': round(s.jump_v_target, 3), 'scale': round(s.jump_scale, 4),
           'rise_above_standing_mm': round(rise, 1), 'bus_v_min_in_the_jump': round(min(log['vbus'][k:]), 2)}
    doc = json.loads(RESULTS.read_text()).get('jump_gate', {}) if RESULTS.exists() else {}
    doc[f'{v:.1f} V'] = res
    record('jump_gate', doc)
    if v >= 44.0:
        assert s.jumps == 1 and s.jumps_refused == 0
        assert rise > 50.0
        assert res['bus_v_min_in_the_jump'] > 35.0
        assert abs(s.jump_scale - fwlib.Firmware.jump_scale(h.fw, v)) < 0.01
    else:
        assert s.jumps == 0 and s.jumps_refused == 1 and s.jump_refusal == 2
        assert rise < 5.0


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
    assert res['at_3.9s']['v_fw'] > 0.4                     # it drove forward when asked to
