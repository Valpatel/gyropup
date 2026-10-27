"""The RS-04 driver against the manual's own worked frames, the 16-bit end points, every frame type round-tripped, and
the driver and command line against the software RS-04 (no hardware).

    .venv/bin/python -m pytest rig/tests -q
"""
from __future__ import annotations

import math
import random
import struct

import pytest

from rig import canio
from rig import rs04 as P
from rig.rs04_emu import EmulatedRS04

R = P.RS04


# ----------------------------------------------------------------------------------- the manual's worked frames

def test_manual_read_example_loc_kp():
    """Manual 4.1.14: read loc_kp from motor 0x7F as host 0xFD; the motor answers 30.0 (F0 41 = 0x41F00000)."""
    assert P.pack_read(0x7F, 'loc_kp', 0xFD) == (0x1100FD7F, bytes.fromhex('1e70000000000000'))
    m = P.parse(0x11007FFD, bytes.fromhex('1e7000000000f041'))
    assert isinstance(m, P.ParamReply)
    assert (m.motor, m.host, m.index, m.ok) == (0x7F, 0xFD, 0x701E, True)
    assert m.value == pytest.approx(30.0)


def test_manual_type18_example_run_mode():
    """Manual 3.2: the upper computer's frame 41 54 | 90 07 e8 0c | 08 | 05 70 00 00 01 00 00 00 | 0d 0a is a type-18
    write of run_mode = 1 from host 0xFD to motor 1 (the adapter shifts the 29-bit id left by 3 and sets 0b100)."""
    serial = bytes.fromhex('4154' '9007e80c' '08' '0570000001000000' '0d0a')
    raw_id = int.from_bytes(serial[2:6], 'big')
    cid = raw_id >> 3
    assert cid == 0x1200FD01
    assert raw_id & 0b111 == 0b100
    assert P.pack_write(1, 'run_mode', 1, host=0xFD) == (cid, serial[7:15])
    req = P.parse_request(cid, serial[7:15])
    assert (req.kind, req.motor, req.host, req.fields['index'], req.fields['value']) == (P.WRITE_PARAM, 1, 0xFD, 0x7005, 1)


def test_manual_c_sample_float_to_uint():
    """Manual 4.4: float_to_uint(x, min, max, 16) = (int)((x - min) * 65535 / (max - min)), clamped."""
    def c_sample(x, lo, hi):
        x = min(max(x, lo), hi)
        return int((x - lo) * float((1 << 16) - 1) / (hi - lo))
    rnd = random.Random(1)
    for lo, hi in ((-R.t, R.t), (-R.v, R.v), (-R.p, R.p), (0.0, R.kp), (0.0, R.kd)):
        for _ in range(500):
            x = rnd.uniform(lo * 1.2 - 1, hi * 1.2 + 1)
            assert P.f2u(x, lo, hi) == c_sample(x, lo, hi)


# ----------------------------------------------------------------------------------- end points and layout

def test_end_points_exact():
    for lo, hi in ((-R.t, R.t), (-R.v, R.v), (-R.p, R.p), (0.0, R.kp), (0.0, R.kd)):
        assert P.f2u(lo, lo, hi) == 0 and P.f2u(hi, lo, hi) == 0xFFFF
        assert P.f2u(lo - 1e3, lo, hi) == 0 and P.f2u(hi + 1e3, lo, hi) == 0xFFFF
        assert P.u2f(0, lo, hi) == lo and P.u2f(0xFFFF, lo, hi) == hi
    assert P.f2u(0.0, -R.t, R.t) == 32767                           # the C sample truncates 32767.5
    with pytest.raises(ValueError):
        P.f2u(float('nan'), -R.t, R.t)
    with pytest.raises(ValueError):
        P.pack_mit(1, 0.0, 0.0, 0.0, 0.0, float('inf'))


def test_mit_frame_layout_at_the_rs04_ranges():
    """4.1.2: torque in id bits 23-8, then angle, speed, Kp, Kd big-endian; the RS-04's +-4pi, +-15, +-120, 5000, 100."""
    assert P.pack_mit(1, 4 * math.pi, 15.0, 5000.0, 100.0, 120.0) == (0x01FFFF01, b'\xff' * 8)
    assert P.pack_mit(1, -4 * math.pi, -15.0, 0.0, 0.0, -120.0) == (0x01000001, bytes(8))
    assert P.pack_mit(2, 0.0, 0.0, 0.0, 0.0, 0.0) == (0x017FFF02, bytes.fromhex('7fff7fff00000000'))
    cid, data = P.pack_mit(1, 1.0, -2.0, 10.0, 1.0, 12.5)
    assert P.id_fields(cid) == (P.MIT, P.f2u(12.5, -120, 120), 1)
    assert struct.unpack('>HHHH', data) == (P.f2u(1.0, -R.p, R.p), P.f2u(-2.0, -15, 15), P.f2u(10.0, 0, 5000), P.f2u(1.0, 0, 100))


def test_feedback_layout_by_hand():
    """4.1.2 type 2: mode in id bits 23-22, faults 21-16, motor 15-8, host 7-0; angle, speed, torque, temp x10."""
    cid = (2 << 24) | (2 << 22) | (1 << 18) | (1 << 8) | 0xFD            # run mode, over-temperature, motor 1 -> host FD
    data = struct.pack('>HHHH', 0xFFFF, 0, 32768, 456)
    fb = P.parse(cid, data)
    assert isinstance(fb, P.Feedback)
    assert (fb.motor, fb.host, fb.mode_name, fb.fault_names) == (1, 0xFD, 'run', ['over-temperature'])
    assert fb.p == pytest.approx(4 * math.pi) and fb.v == pytest.approx(-15.0) and fb.t == pytest.approx(240 / 65535 / 2, abs=4e-3)
    assert fb.temp_c == pytest.approx(45.6)


def test_param_table_matches_the_manual_and_robstride_sample():
    manual = {'run_mode': 0x7005, 'iq_ref': 0x7006, 'spd_ref': 0x700A, 'limit_torque': 0x700B, 'cur_kp': 0x7010,
              'cur_ki': 0x7011, 'cur_filt_gain': 0x7014, 'loc_ref': 0x7016, 'limit_spd': 0x7017, 'limit_cur': 0x7018,
              'mechPos': 0x7019, 'iqf': 0x701A, 'mechVel': 0x701B, 'VBUS': 0x701C, 'loc_kp': 0x701E, 'spd_kp': 0x701F,
              'spd_ki': 0x7020, 'spd_filt_gain': 0x7021, 'acc_rad': 0x7022, 'vel_max': 0x7024, 'acc_set': 0x7025,
              'EPScan_time': 0x7026, 'canTimeout': 0x7028, 'zero_sta': 0x7029, 'damper': 0x702A, 'add_offset': 0x702B,
              'alveolous_open': 0x702C, 'iq_test': 0x702D, 'dcc_set': 0x702E}
    assert {k: v.index for k, v in P.PARAMS.items()} == manual
    sizes = {'B': 1, 'H': 2, 'I': 4, 'f': 4}
    assert sizes[P.PARAMS['EPScan_time'].kind] == 2 and sizes[P.PARAMS['canTimeout'].kind] == 4
    assert P.PARAMS['damper'].kind == 'B' and P.PARAMS['zero_sta'].kind == 'B' and P.PARAMS['VBUS'].kind == 'f'
    assert not P.PARAMS['VBUS'].writable and not P.PARAMS['mechPos'].writable


def test_python_sample_scaling_differs_by_at_most_one_count():
    """RobStride's Python_Sample scales by (x / max + 1) * 0x7FFF; the manual by 65535 / span. One count at most."""
    for lim in (R.t, R.v, R.p):
        for k in range(-1000, 1001):
            x = lim * k / 1000
            sdk = min(0xFFFF, max(0, int((x / lim + 1.0) * 0x7FFF)))
            assert abs(sdk - P.f2u(x, -lim, lim)) <= 1


# ----------------------------------------------------------------------------------- every frame type round-trips

def test_request_round_trips():
    rnd = random.Random(7)
    for _ in range(200):
        m, h = rnd.randint(1, 127), rnd.choice((0xFD, 0xFF, 0x00, 0x10))
        assert P.parse_request(*P.pack_enable(m, h)) == P.Request(P.ENABLE, m, h)
        assert P.parse_request(*P.pack_get_id(m, h)) == P.Request(P.GET_ID, m, h)
        assert P.parse_request(*P.pack_stop(m, h)).fields == {'clear_fault': False}
        assert P.parse_request(*P.pack_stop(m, h, True)).fields == {'clear_fault': True}
        assert P.parse_request(*P.pack_version(m, h)).fields == {'version': True}
        assert P.parse_request(*P.pack_zero(m, h)).fields == {'zero': True}
        n = rnd.randint(1, 127)
        assert P.parse_request(*P.pack_set_id(m, n, h)).fields == {'new_id': n}
        r = P.parse_request(*P.pack_save(m, h))
        assert r.kind == P.SAVE and r.motor == m
        r = P.parse_request(*P.pack_report(m, True, h))
        assert r.kind == P.REPORT and r.fields['f_cmd'] == 1 and r.fields['magic_ok']
        assert P.parse_request(*P.pack_baud(m, 2, h)).fields['f_cmd'] == 2
        x = [rnd.uniform(-R.p, R.p), rnd.uniform(-R.v, R.v), rnd.uniform(0, R.kp), rnd.uniform(0, R.kd), rnd.uniform(-R.t, R.t)]
        q = P.parse_request(*P.pack_mit(m, *x))
        assert q.kind == P.MIT and q.motor == m
        for k, v, span in zip(('p', 'v', 'kp', 'kd', 't'), x, (2 * R.p, 2 * R.v, R.kp, R.kd, 2 * R.t)):
            assert abs(q.fields[k] - v) <= span / 65535 * 1.0001
        for name in P.PARAMS:
            q = P.parse_request(*P.pack_read(m, name, h))
            assert (q.kind, q.motor, q.host, q.fields['index']) == (P.READ_PARAM, m, h, P.PARAMS[name].index)
        for name, val in (('limit_torque', 60.0), ('run_mode', 0), ('EPScan_time', 3), ('canTimeout', 2000),
                          ('damper', 1), ('zero_sta', 1), ('add_offset', -0.25)):
            q = P.parse_request(*P.pack_write(m, name, val, h))
            assert q.fields['value'] == pytest.approx(val)


def test_reply_round_trips():
    rnd = random.Random(3)
    for _ in range(200):
        m, h = rnd.randint(1, 127), 0xFD
        p, v, t, temp = rnd.uniform(-R.p, R.p), rnd.uniform(-R.v, R.v), rnd.uniform(-R.t, R.t), rnd.uniform(0, 140)
        mode, faults = rnd.choice((0, 1, 2)), rnd.randint(0, 63)
        fb = P.parse(*P.encode_feedback(m, h, mode, faults, p, v, t, temp))
        assert (fb.motor, fb.host, fb.mode, fb.faults) == (m, h, mode, faults)
        assert abs(fb.p - p) <= 2 * R.p / 65535 * 1.0001 and abs(fb.v - v) <= 2 * R.v / 65535 * 1.0001
        assert abs(fb.t - t) <= 2 * R.t / 65535 * 1.0001 and fb.temp_c == pytest.approx(round(temp * 10) / 10)
        rp = P.parse(*P.encode_param_reply(m, h, 0x701C, struct.pack('<f', 51.25)))
        assert (rp.motor, rp.host, rp.index, rp.ok, rp.value) == (m, h, 0x701C, True, 51.25)
        assert P.parse(*P.encode_param_reply(m, h, 0x701C, bytes(4), ok=False)).ok is False
        uid = bytes(rnd.getrandbits(8) for _ in range(8))
        di = P.parse(*P.encode_id_reply(m, uid))
        assert (di.motor, di.uid) == (m, uid)
    ff = P.parse(*P.encode_fault(5, 0xFD, (1 << 3) | (1 << 14), 1))
    assert ff.names == ['over-voltage (60 V)', 'stall overload', 'over-temperature warning (135 C)']


def test_host_frames_are_not_taken_for_motor_frames():
    """A host's MIT/enable/write frames must not parse as feedback; 11-bit frames are not RS-04 frames."""
    for f in (P.pack_mit(1, 0, 0, 0, 0, 0), P.pack_enable(1), P.pack_write(1, 'limit_torque', 60.0), P.pack_stop(1)):
        assert not isinstance(P.parse(*f), (P.Feedback, P.FaultFrame, P.DeviceId))


# ----------------------------------------------------------------------------------- SocketCAN struct

def test_socketcan_struct():
    raw = canio.encode_frame(0x0300FD01, bytes(8))
    assert len(raw) == 16 and struct.unpack('=I', raw[:4])[0] == 0x0300FD01 | canio.CAN_EFF_FLAG
    assert canio.decode_frame(raw) == (0x0300FD01, bytes(8), True)
    raw = canio.encode_frame(0x700, b'\x01\x02', extended=False)
    assert canio.decode_frame(raw) == (0x700, b'\x01\x02', False)
    err = struct.pack('=IB3x8s', 0x20000004 | canio.CAN_EFF_FLAG, 8, bytes(8))
    assert canio.decode_frame(err) is None
    with pytest.raises(ValueError):
        canio.encode_frame(1, bytes(9))


# ----------------------------------------------------------------------------------- the driver on a software motor

class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def rig_bus(ids=(1, 2), clock=None, plant=None):
    vb = canio.VirtualBus(log=True)
    motors = {i: EmulatedRS04(i, clock=clock or Clock(), plant=plant) for i in ids}
    for m in motors.values():
        vb.attach(m.handle)
    return vb, P.RS04Bus(vb.port()), motors


def test_scan_enable_mit_stop():
    vb, bus, emu = rig_bus()
    found = bus.scan(range(1, 10), timeout=0.005)
    assert sorted(found) == [1, 2] and found[1] == emu[1].uid
    m1 = bus.motor(1)
    assert m1.enable().mode_name == 'run'
    fb = m1.mit(t=5.0)
    assert emu[1].applied == pytest.approx(5.0, abs=4e-3) and fb.t == pytest.approx(5.0, abs=8e-3)
    assert m1.stop().mode_name == 'reset' and emu[1].applied == 0.0


def test_limit_torque_written_read_back_and_enforced():
    vb, bus, emu = rig_bus()
    m = bus.motor(2)
    assert m.write_check('limit_torque', 60.0) == pytest.approx(60.0)
    m.enable()
    m.mit(t=100.0)
    assert emu[2].applied == pytest.approx(60.0)


def test_watchdog_drops_the_motor_to_reset():
    clk = Clock()
    vb, bus, emu = rig_bus(clock=clk)
    m = bus.motor(1)
    assert m.set_watchdog(0.1) == 2000                              # 20000 = 1 s (3.3.6)
    m.enable()
    m.mit(t=3.0)
    clk.t += 0.05
    assert emu[1].torque() == pytest.approx(3.0, abs=4e-3)          # 50 ms after the last frame: still running
    clk.t += 0.06
    assert emu[1].torque() == 0.0 and emu[1].mode == 0              # 110 ms: the motor stopped itself


def test_fault_clear_zero_setid_version_save():
    vb, bus, emu = rig_bus(ids=(127,))
    m = bus.motor(127)
    emu[127].fault_word = 1 << 3
    assert 'over-current' not in m.stop().fault_names
    assert m.enable().mode_name == 'reset'                          # a faulted motor does not enable
    m.stop(clear_fault=True)
    assert emu[127].fault_word == 0 and m.enable().mode_name == 'run'
    m.stop()
    emu[127].angle = 1.234
    assert m.zero().p == pytest.approx(0.0, abs=4e-4)
    assert m.version() == '0.4.1.24'
    assert m.set_id(1) == 1 and emu[127].id == 1 and m.id == 1
    m.write('zero_sta', 1)
    m.save()
    emu[127].power_cycle()
    assert m.read('zero_sta') == 1


def test_exchange_two_motors_and_a_missing_one():
    vb, bus, emu = rig_bus()
    for i in (1, 2):
        bus.motor(i).enable()
    got = bus.exchange([(1, 0, 0, 0, 0, 2.0), (2, 0, 0, 0, 0, -3.0)], timeout=0.01)
    assert set(got) == {1, 2} and got[1].t == pytest.approx(2.0, abs=8e-3) and got[2].t == pytest.approx(-3.0, abs=8e-3)
    emu[2].mute = True
    got = bus.exchange([(1, 0, 0, 0, 0, 0.0), (2, 0, 0, 0, 0, 0.0)], timeout=0.003)
    assert set(got) == {1}


def test_rig_node_frames_pass_through_and_are_ignored_by_motors():
    seen = []
    vb, bus, emu = rig_bus()
    bus.on_other = lambda cid, data, ext: seen.append((cid, ext))
    other = vb.port()
    other.send(0x700, b'\x01', extended=False)                     # the rig node's RUN frame (11-bit)
    bus.drain(0.001)
    assert seen == [(0x700, False)] and all(e.frames_seen == 0 for e in emu.values())


def test_command_line_on_the_software_bus():
    lines = []
    assert P.main(['--iface', 'emu', '--timeout', '0.002', 'scan'], out=lines.append) == 0
    assert len([s for s in lines if s.startswith('motor ')]) == 2 and 'VBUS 48.0 V' in lines[0]
    vb, bus, emu = rig_bus()
    t = vb.port()
    lines.clear()
    assert P.main(['--id', '1', 'param', 'limit_torque', '60'], transport=t, out=lines.append) == 0
    assert emu[1].params['limit_torque'] == 60.0 and 'limit_torque = 60 ' in lines[0]
    assert P.main(['--id', '1', 'param', 'canTimeout', '2000'], transport=t, out=lines.append) == 0
    assert emu[1].params['canTimeout'] == 2000
    assert P.main(['--id', '1', 'enable'], transport=t, out=lines.append) == 0 and emu[1].mode == 2
    assert P.main(['--id', '1', 'stop'], transport=t, out=lines.append) == 0 and emu[1].mode == 0
    assert P.main(['--id', '1', 'param'], transport=t, out=lines.append) == 0
    assert P.main(['--id', '9', 'enable'], transport=t, out=lines.append) == 2 and lines[-1].startswith('error: no reply')
