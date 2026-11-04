"""Golden vectors for the RS-04 protocol, its safety rules and the software motor, generated from the Python driver
(rig/rs04.py, rig/rs04_guard.py, rig/rs04_emu.py) for the browser port in designer/kit/rs04/ to be tested against.

    python -m rig.rs04_vectors            # rewrite designer/kit/rs04/vectors.json
    python -m rig.rs04_vectors --check    # exit 1 if the committed file is not what the Python makes now

Both sides are tested on the same file: rig/tests/test_rs04_vectors.py (it is current) and
designer/kit/rs04/rs04.test.mjs (the JavaScript gives the same frames, values and verdicts).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from rig import rs04 as P
from rig.rs04_emu import EmulatedRS04
from rig.rs04_guard import Guard

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'designer' / 'kit' / 'rs04' / 'vectors.json'
LIMITS = {'limit_torque_nm': 12.0, 'jog_torque_nm': 3.0, 'jog_speed_rad_s': 1.0, 'jog_kp_max': 20.0, 'jog_kd_max': 1.0,
          'can_timeout_ticks': 2000, 'can_timeout_max_ticks': 2000}


def fr(f):
    cid, data = f
    return {'id': cid, 'data': bytes(data).hex()}


def plain(m):
    """A parsed reply as the JavaScript returns it."""
    if m is None:
        return None
    if isinstance(m, P.Feedback):
        return {'type': 'feedback', 'motor': m.motor, 'host': m.host, 'mode': m.mode, 'faults': m.faults, 'p': m.p,
                'v': m.v, 't': m.t, 'tempC': m.temp_c, 'raw': list(m.raw)}
    if isinstance(m, P.Version):
        return {'type': 'version', 'motor': m.motor, 'host': m.host, 'version': m.version}
    if isinstance(m, P.ParamReply):
        return {'type': 'param', 'motor': m.motor, 'host': m.host, 'index': m.index, 'ok': m.ok, 'raw': list(m.raw)}
    if isinstance(m, P.DeviceId):
        return {'type': 'id', 'motor': m.motor, 'uid': list(m.uid)}
    if isinstance(m, P.FaultFrame):
        return {'type': 'fault', 'motor': m.motor, 'host': m.host, 'fault': m.fault, 'warning': m.warning}
    raise TypeError(m)


def plain_req(r):
    if r is None:
        return None
    f = {k: (list(v) if isinstance(v, (tuple, bytes)) else v) for k, v in r.fields.items()}
    return {'kind': r.kind, 'motor': r.motor, 'host': r.host, 'fields': f}


def scaling():
    out = []
    r = P.RS04
    for lo, hi in ((-r.p, r.p), (-r.v, r.v), (-r.t, r.t), (0.0, r.kp), (0.0, r.kd)):
        for x in (lo - 1, lo, lo / 3, -1e-9, 0.0, 1e-9, 0.1, hi / 7, hi * 0.999999, hi, hi + 1):
            if lo <= -1e-9 or x >= 0 or x == lo - 1:
                out.append({'fn': 'f2u', 'x': x, 'lo': lo, 'hi': hi, 'u': P.f2u(x, lo, hi)})
        for u in (0, 1, 32767, 32768, 65534, 65535):
            out.append({'fn': 'u2f', 'u': u, 'lo': lo, 'hi': hi, 'x': P.u2f(u, lo, hi)})
    return out


def requests():
    """Every host frame the tool can send, with its arguments, the frame and how a motor decodes it."""
    cases = [
        ('packGetId', [1]), ('packGetId', [127, 0xFD]), ('packEnable', [3]), ('packStop', [4]),
        ('packStop', [4, 0xFD, True]), ('packVersion', [2]), ('packZero', [1]), ('packSetId', [127, 3]),
        ('packSetId', [5, 1, 0xAA]), ('packSave', [2]), ('packReport', [1, True]), ('packReport', [1, False]),
        ('packBaud', [1, 1]),
        ('packMit', [1, 0.0, 0.0, 0.0, 0.0, 0.0]), ('packMit', [2, 1.2345, -0.5, 20.0, 1.0, 2.5]),
        ('packMit', [3, -13.0, 16.0, 6000.0, 101.0, -130.0]), ('packMit', [4, math.pi, 0.999, 19.99, 0.01, -2.999]),
    ]
    for p in P.PARAMS.values():
        cases.append(('packRead', [1, p.name]))
    for name, v in (('limit_torque', 12.0), ('limit_torque', 60.0), ('canTimeout', 2000), ('zero_sta', 1),
                    ('damper', 0), ('run_mode', 0), ('EPScan_time', 5), ('add_offset', -0.7853981633974483),
                    ('spd_ref', 3.3), ('limit_cur', 23.0), ('cur_filt_gain', 0.1)):
        cases.append(('packWrite', [2, name, v]))
    py = {'packGetId': P.pack_get_id, 'packEnable': P.pack_enable, 'packStop': P.pack_stop, 'packVersion': P.pack_version,
          'packZero': P.pack_zero, 'packSetId': P.pack_set_id, 'packSave': P.pack_save, 'packReport': P.pack_report,
          'packBaud': P.pack_baud, 'packMit': P.pack_mit, 'packRead': P.pack_read, 'packWrite': P.pack_write}
    out = []
    for fn, args in cases:
        f = py[fn](*args)
        out.append({'fn': fn, 'args': args, 'frame': fr(f), 'request': plain_req(P.parse_request(*f))})
    return out


def replies():
    uid = bytes.fromhex('a1b2c3d4e5f60718')
    frames = [
        P.encode_feedback(1, 0xFD, 2, 0, 0.0, 0.0, 0.0, 28.0),
        P.encode_feedback(2, 0xFD, 0, 0b100101, -1.5, 3.25, -7.5, 41.25),
        P.encode_feedback(3, 0xFD, 2, 0, 20.0, -20.0, 200.0, 12.35),
        P.encode_feedback(4, 0xFD, 1, 0, 0.1, 0.2, 0.3, 0.05, kind=P.REPORT),
        P.encode_feedback(4, 0xFD, 0, 0, 0.0, 0.0, 0.0, 22.45),
        P.encode_param_reply(1, 0xFD, 0x700B, P.pack_value(P.PARAMS['limit_torque'], 12.0)),
        P.encode_param_reply(1, 0xFD, 0x7028, P.pack_value(P.PARAMS['canTimeout'], 2000)),
        P.encode_param_reply(2, 0xFD, 0x7005, P.pack_value(P.PARAMS['run_mode'], 0)),
        P.encode_param_reply(2, 0xFD, 0x7029, P.pack_value(P.PARAMS['zero_sta'], 1)),
        P.encode_param_reply(3, 0xFD, 0x7026, P.pack_value(P.PARAMS['EPScan_time'], 513)),
        P.encode_param_reply(3, 0xFD, 0x1234, bytes(4), ok=False),
        P.encode_id_reply(127, uid), P.encode_id_reply(1, uid[:5]),
        P.encode_fault(1, 0xFD, (1 << 0) | (1 << 14) | (1 << 16), 1),
        (P.can_id(P.FEEDBACK, 2, 0xFD), b'\x00\xc4\x56\x00\x04\x01\x18\x00'),
        (P.can_id(P.ENABLE, 0xFD, 1), bytes(8)),            # a host frame: parse() ignores it
    ]
    out = []
    for f in frames:
        m = P.parse(*f)
        row = {'frame': fr(f), 'parsed': plain(m)}
        if isinstance(m, P.ParamReply) and m.index in P.BY_INDEX:
            row['value'] = m.value
        out.append(row)
    return out


def values():
    out = []
    for p in P.PARAMS.values():
        samples = [0, 1, 255] if p.kind == 'B' else [0, 513, 65535] if p.kind == 'H' else [0, 2000, 4294967295] \
            if p.kind == 'I' else [0.0, 12.0, -0.1, 3.4028234663852886e38, 1e-7]
        for v in samples:
            raw = P.pack_value(p, v)
            out.append({'name': p.name, 'value': v, 'raw': raw.hex(), 'back': P.unpack_value(p, raw)})
    return out


def guard_scenarios():
    """Steps against a Guard with a fake clock: what the bus says, what is armed, what the tool asks to send."""
    uid = bytes(8)

    def rb(m, name, v):
        return ('in', P.encode_param_reply(m, 0xFD, P.PARAMS[name].index, P.pack_value(P.PARAMS[name], v)))

    confirm = [rb(1, 'run_mode', 0), rb(1, 'limit_torque', 3.0), rb(1, 'canTimeout', 2000)]
    scenarios = {
        'refusals before a scan': [
            ('out', P.pack_enable(1)), ('arm', [1]), ('out', P.pack_read(1, 'VBUS')), ('out', P.pack_get_id(1)),
            ('out', P.pack_baud(1, 2)), ('out', (P.can_id(P.SET_PROTOCOL, 0xFD, 1), bytes((1, 2, 3, 4, 5, 6, 0, 0)))),
            ('out_std', (0x110, bytes(8))), ('out', (P.can_id(9, 0xFD, 1), bytes(8))),
        ],
        'writes and the profile cap': [
            ('in', P.encode_id_reply(1, uid)),
            ('out', P.pack_write(1, 'limit_torque', 12.0)), ('out', P.pack_write(1, 'limit_torque', 12.5)),
            ('out', P.pack_write(1, 'limit_torque', 120.0)), ('out', P.pack_write(1, 'canTimeout', 0)),
            ('out', P.pack_write(1, 'canTimeout', 2001)), ('out', P.pack_write(1, 'canTimeout', 1000)),
            ('out', P.pack_write(1, 'run_mode', 2)), ('out', P.pack_write(1, 'run_mode', 0)),
            ('out', P.pack_write(1, 'spd_ref', 5.0)), ('out', P.pack_write(1, 'iq_ref', 0.0)),
            ('out', P.pack_write(1, 'zero_sta', 1)), ('out', P.pack_write(1, 'cur_filt_gain', 1.5)),
            ('out', (P.can_id(P.WRITE_PARAM, 0xFD, 1), bytes((0x19, 0x70, 0, 0, 0, 0, 0, 0)))),
            ('out', (P.can_id(P.WRITE_PARAM, 0xFD, 1), bytes((0x34, 0x12, 0, 0, 0, 0, 0, 0)))),
            ('out', P.pack_zero(1)), ('out', P.pack_save(1)), ('out', P.pack_version(1)),
        ],
        'arming needs fresh read-backs under the jog limits': [
            ('in', P.encode_id_reply(1, uid)), ('in', P.encode_id_reply(2, uid)),
            ('out', P.pack_enable(1)), ('arm', [1, 3]), ('arm', [1]), ('out', P.pack_enable(1)),
            rb(1, 'run_mode', 0), rb(1, 'limit_torque', 12.0), rb(1, 'canTimeout', 2000),
            ('out', P.pack_enable(1)), rb(1, 'limit_torque', 3.0), ('out', P.pack_enable(1)),
            ('out', P.pack_mit(1, 0.5, 0.5, 20.0, 1.0, 0.0)), ('out', P.pack_mit(1, 0.5, 0.0, 0.0, 0.0, 3.5)),
            ('out', P.pack_mit(1, 0.5, 1.5, 0.0, 0.0, 0.0)), ('out', P.pack_mit(1, 0.5, 0.0, 30.0, 1.0, 0.0)),
            ('out', P.pack_mit(1, 0.5, 0.0, 10.0, 2.0, 0.0)), ('out', P.pack_mit(2, 0.0, 0.0, 0.0, 0.0, 0.0)),
            ('out', P.pack_write(1, 'zero_sta', 1)), ('out', P.pack_zero(1)), ('out', P.pack_save(1)),
            ('out', P.pack_version(1)), ('out', P.pack_stop(1)), ('out', P.pack_set_id(1, 4)),
            ('wait', 11.0), ('out', P.pack_enable(1)), *confirm, ('out', P.pack_enable(1)),
            ('out', P.pack_write(1, 'limit_torque', 2.0)), ('disarm', None), ('out', P.pack_write(1, 'limit_torque', 2.0)),
            ('arm', [1]), ('out', P.pack_enable(1)), rb(1, 'limit_torque', 2.0), ('out', P.pack_enable(1)),
            rb(1, 'canTimeout', 0), ('out', P.pack_enable(1)), rb(1, 'canTimeout', 2000), rb(1, 'run_mode', 2),
            ('out', P.pack_enable(1)),
        ],
        'renumbering': [
            ('in', P.encode_id_reply(127, uid)), ('in', P.encode_id_reply(1, uid)),
            ('out', P.pack_set_id(127, 1)), ('out', P.pack_set_id(127, 2)), ('in', P.encode_id_reply(2, uid)),
            ('out', P.pack_set_id(1, 127)),
            ('out', (P.can_id(P.SET_ID, (0 << 8) | 0xFD, 2), bytes(8))),        # id 0 (broadcast): refused
            ('out', (P.can_id(P.SET_ID, (0xFD << 8) | 0xFD, 2), bytes(8))),     # the host's id: refused
            ('out', (P.can_id(P.SET_ID, (0x80 << 8) | 0xFD, 2), bytes(8))),     # over 127: refused
            ('stop_targets', None),
        ],
        'a NaN read-back does not arm': [
            ('in', P.encode_id_reply(1, uid)), ('arm', [1]),
            rb(1, 'run_mode', 0), rb(1, 'limit_torque', float('nan')), rb(1, 'canTimeout', 2000),
            ('out', P.pack_enable(1)), rb(1, 'limit_torque', 3.0), ('out', P.pack_enable(1)),
        ],
    }
    out = {}
    for name, steps in scenarios.items():
        now = [100.0]
        g = Guard(LIMITS, clock=lambda: now[0])
        rows = []
        for op, arg in steps:
            if op == 'in':
                g.observe(*arg, True)
                rows.append({'op': 'in', 'frame': fr(arg)})
            elif op in ('out', 'out_std'):
                ok, code, why = g.check(arg[0], arg[1], op == 'out')
                rows.append({'op': 'out', 'frame': fr(arg), 'ext': op == 'out', 'ok': ok, 'code': code})
            elif op == 'arm':
                ok, code, _ = g.arm(arg)
                rows.append({'op': 'arm', 'ids': arg, 'ok': ok, 'code': code})
            elif op == 'disarm':
                g.disarm()
                rows.append({'op': 'disarm'})
            elif op == 'wait':
                now[0] += arg
                rows.append({'op': 'wait', 's': arg})
            elif op == 'stop_targets':
                rows.append({'op': 'stop_targets', 'ids': g.stop_targets()})
            now[0] += 0.01
        out[name] = rows
    return {'limits': LIMITS, 'scenarios': out}


def emulator_script():
    """A software motor's replies to a fixed sequence (its own plant off, then on), on a fake clock."""
    runs = {}
    for plant in (None, 'inertia'):
        now = [0.0]
        m = EmulatedRS04(127, uid=bytes.fromhex('0011223344556677'), clock=lambda: now[0], plant=plant)
        steps = [(0.0, P.pack_get_id(127)), (0.01, P.pack_version(127)), (0.01, P.pack_set_id(127, 1)),
                 (0.01, P.pack_read(1, 'limit_torque')), (0.01, P.pack_write(1, 'limit_torque', 3.0)),
                 (0.01, P.pack_read(1, 'limit_torque')), (0.01, P.pack_write(1, 'canTimeout', 2000)),
                 (0.01, P.pack_write(1, 'zero_sta', 1)), (0.01, P.pack_save(1)), (0.01, P.pack_enable(1))]
        steps += [(0.02, P.pack_mit(1, 0.02 * (i + 1), 1.0, 20.0, 1.0, 0.0)) for i in range(20)]
        steps += [(0.3, P.pack_read(1, 'mechPos')), (0.01, P.pack_enable(1)), (0.01, P.pack_stop(1)),
                  (0.01, P.pack_zero(1)), (0.01, P.pack_read(1, 'mechPos')), (0.01, P.pack_read(1, 'VBUS')),
                  (0.01, P.pack_read(1, 0x1234)), (0.01, P.pack_get_id(5)), (0.01, P.pack_stop(1, clear_fault=True))]
        rows = []
        for dt, f in steps:
            now[0] += dt
            rows.append({'dt': dt, 'send': fr(f), 'reply': [fr((c, d)) for c, d, *_ in m.handle(f[0], f[1], True)]})
        runs['plant' if plant else 'no_plant'] = rows
    return runs


def build() -> dict:
    return {
        'about': 'Generated by python -m rig.rs04_vectors from rig/rs04.py, rig/rs04_guard.py and rig/rs04_emu.py: '
                 'regenerate, never edit. designer/kit/rs04/rs04.test.mjs checks the JavaScript port against it.',
        'ranges': {'p': P.RS04.p, 'v': P.RS04.v, 't': P.RS04.t, 'kp': P.RS04.kp, 'kd': P.RS04.kd},
        'params': [{'name': p.name, 'index': p.index, 'kind': p.kind, 'writable': p.writable, 'unit': p.unit,
                    'lo': p.lo, 'hi': p.hi} for p in P.PARAMS.values()],
        'scaling': scaling(), 'requests': requests(), 'replies': replies(), 'values': values(),
        'guard': guard_scenarios(), 'emulator': emulator_script(),
    }


def render() -> str:
    return json.dumps(build(), indent=1) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    text = render()
    if a.check:
        if not OUT.is_file() or OUT.read_text() != text:
            print(f'{OUT.relative_to(ROOT)} is stale: run python -m rig.rs04_vectors')
            return 1
        print(f'{OUT.relative_to(ROOT)} is current')
        return 0
    OUT.write_text(text)
    print(f'wrote {OUT.relative_to(ROOT)} ({len(text)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
