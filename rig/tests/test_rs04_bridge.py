"""The RS-04 bridge (rig/rs04_bridge.py) on software motors: what it serves, who may connect, that the guard holds on
the bus side, and that a closed or quiet tab stops the motors.

    python -m unittest rig.tests.test_rs04_bridge
"""
from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

from rig import rs04 as P
from rig import rs04_bridge as B
from rig import rs04_profiles


class Server:
    """A bridge on software motors, on an ephemeral port, in its own thread."""

    def __init__(self, ids=(1,), token=None):
        self.transport, kind = B.make_transport('emu', list(ids))
        self.bridge = B.Bridge(self.transport, rs04_profiles.load('pla-bench'), 'emu', kind, token=token)
        self.addr = None
        self.writers = set()
        self.closed = False
        ready = threading.Event()

        def run():
            self.loop = asyncio.new_event_loop()
            self.loop.run_until_complete(self._start(ready))
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        if not ready.wait(5):
            raise TimeoutError('test bridge did not start')

    async def _start(self, ready):
        self.bridge.loop = asyncio.get_running_loop()
        self.reader_thread = threading.Thread(target=self.bridge.reader_thread, daemon=True)
        self.reader_thread.start()
        self.server = await asyncio.start_server(self._handle, '127.0.0.1', 0)
        self.addr = self.server.sockets[0].getsockname()
        ready.set()

    async def _handle(self, reader, writer):
        self.writers.add(writer)
        try:
            await self.bridge.handle(reader, writer)
        finally:
            # Cancellation while reading an incomplete HTTP header also owns a socket.
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            self.writers.remove(writer)

    @property
    def motors(self):
        return self.transport.motors

    def close(self):
        if self.closed:
            return
        self.bridge.running = False

        async def shutdown():
            self.server.close()
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Python 3.12 also waits for accepted clients: finish their handlers first.
            await self.server.wait_closed()
            for result in results:
                if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                    raise result
        # Deliver the coroutine's result before stopping its event loop.
        completion = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
        cleanup_error = None
        try:
            completion.result(timeout=5)
        except BaseException as exc:
            if not completion.done():
                raise  # Incomplete cleanup must never look like a successful close.
            cleanup_error = exc
        self.reader_thread.join(5)
        if self.reader_thread.is_alive():
            raise TimeoutError('test bridge reader did not stop')
        self.transport.close()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        if self.thread.is_alive():
            raise TimeoutError('test bridge event loop did not stop')
        self.loop.close()
        self.closed = True
        if cleanup_error is not None:
            raise cleanup_error


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

    def assert_closed(self):
        self.assertFalse(self.srv.thread.is_alive())
        self.assertFalse(self.srv.reader_thread.is_alive())
        self.assertTrue(self.srv.loop.is_closed())
        self.assertFalse(self.srv.server.is_serving())
        self.assertFalse(self.srv.writers)
        self.assertFalse(asyncio.all_tasks(self.srv.loop))

    def test_close_waits_for_the_actual_websocket_finalizer(self):
        w = WS(self.addr)
        self.addCleanup(w.close)
        w.recv()
        entered, release = threading.Event(), threading.Event()
        original = B.log

        def held_log(*args):
            if args == ('tab disconnected',):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('test did not release the disconnect finalizer')
            original(*args)

        with patch.object(B, 'log', held_log), ThreadPoolExecutor(max_workers=1) as pool:
            closing = pool.submit(self.srv.close)
            try:
                self.assertTrue(entered.wait(2), 'the real websocket finalizer was reached')
                with self.assertRaises(FutureTimeout, msg='close returned before its disconnect log finished'):
                    closing.result(timeout=0.05)
            finally:
                release.set()
                closing.result(timeout=6)
        self.assertEqual(w.s.recv(1), b'')
        self.assert_closed()
        self.srv.close()  # A completed teardown is safe to repeat.

    def test_close_waits_for_the_transport_reader(self):
        entered, release = threading.Event(), threading.Event()
        original = self.srv.transport.recv

        def held_recv(timeout):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test did not release the transport reader')
            return original(timeout)

        with patch.object(self.srv.transport, 'recv', held_recv), ThreadPoolExecutor(max_workers=1) as pool:
            self.assertTrue(entered.wait(2), 'the actual transport reader entered recv')
            closing = pool.submit(self.srv.close)
            try:
                # Wait for the listener to close so this checks reader completion, not scheduling.
                deadline = time.monotonic() + 2
                while self.srv.server.is_serving() and time.monotonic() < deadline:
                    time.sleep(0.001)
                self.assertFalse(self.srv.server.is_serving(), 'shutdown reached the closed listener')
                with self.assertRaises(FutureTimeout, msg='close returned while its reader was still blocked'):
                    closing.result(timeout=0.05)
            finally:
                release.set()
                closing.result(timeout=6)
        self.assert_closed()

    def test_close_finishes_an_incomplete_http_connection(self):
        client = socket.create_connection(self.addr, timeout=3)
        self.addCleanup(client.close)
        client.sendall(b'GET / HTTP/1.1\r\n')

        async def accepted():
            while not self.srv.writers:
                await asyncio.sleep(0)
        asyncio.run_coroutine_threadsafe(accepted(), self.srv.loop).result(timeout=2)
        self.srv.close()
        self.assertEqual(client.recv(1), b'')
        self.assert_closed()

    def test_close_reports_cleanup_errors_after_finishing_resources(self):
        entered = threading.Event()

        async def failing_cleanup():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise ValueError('deliberate cleanup failure')
        pending = asyncio.run_coroutine_threadsafe(failing_cleanup(), self.srv.loop)
        self.assertTrue(entered.wait(2))
        with self.assertRaisesRegex(ValueError, 'deliberate cleanup failure'):
            self.srv.close()
        self.assert_closed()
        with self.assertRaisesRegex(ValueError, 'deliberate cleanup failure'):
            pending.result(timeout=0)

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
