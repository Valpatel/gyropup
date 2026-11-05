"""The RS-04 bridge (rig/rs04_bridge.py) on software motors: what it serves, who may connect, that the guard holds on
the bus side, and that a closed or quiet tab stops the motors.

    python -m unittest rig.tests.test_rs04_bridge
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import threading
import time
import unittest

from rig import rs04 as P
from rig import rs04_bridge as B
from rig import rs04_profiles


class Server:
    """A bridge on software motors, on an ephemeral port, in its own thread."""

    def __init__(self, ids=(1,), token=None):
        self.transport, kind = B.make_transport('emu', list(ids))
        self.bridge = B.Bridge(self.transport, rs04_profiles.load('pla-bench'), 'emu', kind, token=token)
        self.addr = None
        ready = threading.Event()

        def run():
            self.loop = asyncio.new_event_loop()
            self.loop.run_until_complete(self._start(ready))
            self.loop.run_forever()

        threading.Thread(target=run, daemon=True).start()
        ready.wait(5)

    async def _start(self, ready):
        self.bridge.loop = asyncio.get_running_loop()
        threading.Thread(target=self.bridge.reader_thread, daemon=True).start()
        self.server = await asyncio.start_server(self.bridge.handle, '127.0.0.1', 0)
        self.addr = self.server.sockets[0].getsockname()
        ready.set()

    @property
    def motors(self):
        return self.transport.motors

    def close(self):
        self.bridge.running = False

        async def shutdown():
            self.server.close()
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.loop.stop()

        asyncio.run_coroutine_threadsafe(shutdown(), self.loop)


def status(ws):
    ws.close()
    return ws.status


def http(addr, path, headers=None):
    s = socket.create_connection(addr, timeout=3)
    h = {'Host': f'127.0.0.1:{addr[1]}', **(headers or {})}
    s.sendall((f'GET {path} HTTP/1.1\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in h.items()) + '\r\n').encode())
    data = b''
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    head, _, body = data.partition(b'\r\n\r\n')
    return int(head.split()[1]), head.decode('latin-1'), body


class WS:
    """A minimal websocket client (masked text frames), enough to drive the bridge as the page does."""

    def __init__(self, addr, origin=None, path='/ws', host=None):
        self.s = socket.create_connection(addr, timeout=3)
        key = base64.b64encode(os.urandom(16)).decode()
        host = host or f'127.0.0.1:{addr[1]}'
        origin = origin if origin is not None else f'http://{host}'
        self.s.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
                        + (f'Origin: {origin}\r\n' if origin else '') + '\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            c = self.s.recv(1)
            if not c:
                break
            head += c
        self.status = int(head.split()[1]) if head else 0
        self.buf = b''

    def send(self, obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytes((0x81,)) + (bytes((0x80 | n,)) if n < 126 else bytes((0x80 | 126,)) + n.to_bytes(2, 'big'))
        self.s.sendall(hdr + mask + bytes(b ^ mask[i & 3] for i, b in enumerate(payload)))

    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c:
                raise ConnectionError('closed')
            self.buf += c
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        b0, b1 = self._read(2)
        n = b1 & 0x7F
        if n == 126:
            n = int.from_bytes(self._read(2), 'big')
        return json.loads(self._read(n))

    def until(self, pred, timeout=2.0):
        end = time.monotonic() + timeout
        self.s.settimeout(timeout)
        while time.monotonic() < end:
            m = self.recv()
            if pred(m):
                return m
        raise AssertionError('no such message')

    def frame(self, f):
        self.send({'op': 'send', 'id': f[0], 'data': bytes(f[1]).hex(), 'ext': True})

    def close(self):
        self.s.close()


def is_reply(kind, motor=None, index=None):
    def pred(m):
        if m.get('op') != 'frame':
            return False
        r = P.parse(m['id'], bytes.fromhex(m['data']))
        return isinstance(r, kind) and (motor is None or r.motor == motor) and (index is None or r.index == index)
    return pred


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.srv = Server(ids=(1,))
        self.addr = self.srv.addr

    def tearDown(self):
        self.srv.close()

    def test_serves_the_tool_and_nothing_else(self):
        code, head, _ = http(self.addr, '/')
        self.assertEqual(code, 302)
        self.assertIn('Location: /designer/motor-tool.html?bridge=1', head)
        self.assertEqual(http(self.addr, '/designer/kit/rs04/protocol.js')[0], 200)
        self.assertEqual(http(self.addr, '/hardware/actuators/rs04/profiles/pla-bench.json')[0], 200)
        for path in ('/rig/rs04.py', '/designer/kit/rs04/../../../rig/rs04.py', '/designer/kit/stage.js', '/.git/config',
                     '/designer/kit/rs04/%2e%2e/x', '/etc/passwd'):
            self.assertEqual(http(self.addr, path)[0], 404, path)
        code, head, _ = http(self.addr, '/?token=a%0d%0aSet-Cookie:x')
        self.assertNotIn('Set-Cookie', head)

    def test_refuses_other_origins_and_a_second_tab(self):
        self.assertEqual(status(WS(self.addr, origin='https://example.com')), 403)
        self.assertEqual(status(WS(self.addr, origin='')), 403)
        # DNS rebinding: a site's own name pointed at 127.0.0.1 has a matching Origin and Host, but not a loopback name
        self.assertEqual(status(WS(self.addr, host=f'evil.example:{self.addr[1]}')), 403)
        a = WS(self.addr)
        self.assertEqual(a.status, 101)
        hello = a.recv()
        self.assertEqual((hello['op'], hello['kind'], hello['profile']), ('hello', 'virtual', 'pla-bench'))
        self.assertEqual(hello['limits']['limit_torque_nm'], 12.0)
        self.assertEqual(status(WS(self.addr)), 409)
        a.close()

    def test_token_mode(self):
        srv = Server(ids=(1,), token='t' * 20)
        try:
            host = f'robot.local:{srv.addr[1]}'
            self.assertEqual(status(WS(srv.addr, host=host, path='/ws')), 403)
            self.assertEqual(status(WS(srv.addr, host=host, path='/ws?token=' + 'u' * 20)), 403)
            w = WS(srv.addr, host=host, path='/ws?token=' + 't' * 20)
            self.assertEqual(w.status, 101)
            w.close()
        finally:
            srv.close()

    def test_guard_on_the_bus_side_and_stop_on_close(self):
        w = WS(self.addr)
        w.recv()
        w.frame(P.pack_get_id(1))
        w.until(is_reply(P.DeviceId, 1))
        w.frame(P.pack_write(1, 'limit_torque', 60.0))
        r = w.until(lambda m: m.get('op') == 'refused')
        self.assertEqual(r['code'], 'cap')
        self.assertEqual(self.srv.motors[0].params['limit_torque'], 120.0)     # never reached the motor
        w.frame(P.pack_enable(1))
        self.assertEqual(w.until(lambda m: m.get('op') == 'refused')['code'], 'not-armed')
        for name, v in (('run_mode', 0), ('canTimeout', 2000), ('limit_torque', 3.0)):
            w.frame(P.pack_write(1, name, v))
            w.until(is_reply(P.Feedback, 1))
            w.frame(P.pack_read(1, name))
            w.until(is_reply(P.ParamReply, 1, P.PARAMS[name].index))
        w.send({'op': 'arm', 'ids': [1]})
        w.frame(P.pack_enable(1))
        fb = w.until(is_reply(P.Feedback, 1))
        self.assertEqual(P.parse(fb['id'], bytes.fromhex(fb['data'])).mode, 2)
        self.assertEqual(self.srv.motors[0].mode, 2)
        w.frame(P.pack_mit(1, 0.0, 0.0, 0.0, 0.0, 10.0))
        self.assertEqual(w.until(lambda m: m.get('op') == 'refused')['code'], 'jog-torque')
        w.close()                                                   # the tab closes: the bridge stops every motor
        end = time.monotonic() + 2
        while self.srv.motors[0].mode != 0 and time.monotonic() < end:
            time.sleep(0.02)
        self.assertEqual(self.srv.motors[0].mode, 0)
        self.assertFalse(self.srv.bridge.guard.armed)

    def test_a_quiet_tab_stops_an_armed_motor(self):
        w = WS(self.addr)
        w.recv()
        w.frame(P.pack_get_id(1))
        w.until(is_reply(P.DeviceId, 1))
        w.send({'op': 'arm', 'ids': [1]})
        time.sleep(0.1)
        self.assertTrue(self.srv.bridge.guard.armed)
        time.sleep(B.QUIET_S + 0.5)                                 # no message at all
        self.assertFalse(self.srv.bridge.guard.armed)
        self.assertGreater(self.srv.bridge.stops_sent, 0)
        w.close()

    def test_stop_all_reaches_every_motor_seen(self):
        srv = Server(ids=(1, 2))
        try:
            w = WS(srv.addr)
            w.recv()
            for i in (1, 2):
                w.frame(P.pack_get_id(i))
                w.until(is_reply(P.DeviceId, i))
            before = [m.frames_seen for m in srv.motors]
            w.send({'op': 'stop_all'})
            end = time.monotonic() + 2
            while any(m.frames_seen == b for m, b in zip(srv.motors, before)) and time.monotonic() < end:
                time.sleep(0.02)
            self.assertTrue(all(m.frames_seen > b for m, b in zip(srv.motors, before)))
            w.close()
        finally:
            srv.close()


if __name__ == '__main__':
    unittest.main()
