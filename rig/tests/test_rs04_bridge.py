"""The RS-04 bridge (rig/rs04_bridge.py) on software motors: what it serves, who may connect, that the guard holds on
the bus side, and that a closed or quiet tab stops the motors.

    python -m unittest rig.tests.test_rs04_bridge
"""
from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import errno
import json
import os
import socket
import subprocess
import sys
import textwrap
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


class MainTests(unittest.TestCase):
    def test_initialization_error_closes_the_created_transport(self):
        transport, kind = B.make_transport('emu', [127])
        error = ValueError('injected bridge initialization failure')
        with patch.object(B, 'make_transport', return_value=(transport, kind)), \
                patch.object(B, 'Bridge', side_effect=error), \
                patch.object(transport, 'close', wraps=transport.close) as close:
            with self.assertRaises(ValueError) as caught:
                B.main(['--iface', 'emu', '--emu-ids', '127', '--port', '0'])
            self.assertIs(caught.exception, error)
            close.assert_called_once_with()

    def test_sigint_main_waits_for_its_real_reader(self):
        # Signal only this software-only child, after its real listener/reader start.
        script = textwrap.dedent('''\
            import json, os, signal, threading
            from unittest.mock import patch
            from rig import rs04_bridge as B
            entered, release, ready, returned = (threading.Event() for _ in range(4))
            transport, kind = B.make_transport('emu', [127])
            recv, close, log, bridge_type = transport.recv, transport.close, B.log, B.Bridge
            readers, bridges, closure, observation, errors = [], [], [], [], []
            def held_recv(timeout):
                if not readers:
                    readers.append(threading.current_thread())
                entered.set()
                if not release.wait(3):
                    errors.append('reader gate was not released')
                return recv(timeout)
            def closed():
                closure.append((readers[0].is_alive(), bridges[0].loop.is_closed()))
                close()
            def created(*args, **kwargs):
                bridge = bridge_type(*args, **kwargs)
                bridges.append(bridge)
                return bridge
            def logged(*args):
                log(*args)
                if args and str(args[0]).startswith('open http'):
                    ready.set()
            def interrupt():
                try:
                    assert entered.wait(2) and ready.wait(2), 'runtime did not become ready'
                    os.kill(os.getpid(), signal.SIGINT)
                    observation.append(returned.wait(0.05))
                except BaseException as exc:
                    errors.append(repr(exc))
                finally:
                    release.set()
            def software_only(iface, ids):
                assert iface == 'emu' and ids == [127]
                return transport, kind
            transport.recv, transport.close = held_recv, closed
            coordinator = threading.Thread(target=interrupt)
            try:
                with patch.object(B, 'make_transport', software_only), patch.object(B, 'Bridge', created), patch.object(B, 'log', logged):
                    coordinator.start()
                    result = B.main(['--iface', 'emu', '--emu-ids', '127', '--port', '0'])
                    reader_alive_at_return = readers[0].is_alive()
                    returned.set()
            finally:
                release.set()
                coordinator.join(3)
                for reader in readers:
                    reader.join(3)
                close()
            assert not errors, errors
            assert observation == [False], 'main returned while recv was held'
            assert result == 0 and not reader_alive_at_return
            assert closure == [(False, False)], closure
            assert bridges[0].loop.is_closed() and not bridges[0].running
            assert not coordinator.is_alive() and not any(t.is_alive() for t in readers)
            print('PASS real SIGINT: reader finished before transport/loop closure')
        ''')
        result = subprocess.run([sys.executable, '-W', 'error::ResourceWarning', '-c', script],
                                cwd=B.ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS real SIGINT', result.stdout)
        self.assertNotIn('ResourceWarning', result.stderr)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    """Exercise production serve(), including resources the older test server did not own."""

    async def asyncSetUp(self):
        self.transport, kind = B.make_transport('emu', [1])
        self.bridge = B.Bridge(self.transport, rs04_profiles.load('pla-bench'), 'emu', kind)
        self.runtime = None
        self.reader = None
        self.releases = []
        self.closed = []
        self.before_tasks = asyncio.all_tasks()
        self.sentinel = asyncio.create_task(asyncio.Event().wait())
        original_reader, original_close = self.bridge.reader_thread, self.transport.close

        def reader():
            self.reader = threading.current_thread()
            original_reader()

        def close():
            self.closed.append((self.bridge.stops_sent, self.bridge.loop.is_closed()))
            original_close()

        self.bridge.reader_thread = reader
        self.transport.close = close
        # Let the real emulated reply identify a motor to the production reader.
        self.transport.send(*P.pack_get_id(1), True)

    async def asyncTearDown(self):
        for release in self.releases:
            release.set()
        self.bridge.running = False
        if self.runtime is not None:
            if not self.runtime.done():
                self.runtime.cancel()
            await asyncio.gather(self.runtime, return_exceptions=True)
        self.transport.close()
        if self.reader is not None:
            await asyncio.to_thread(self.reader.join, 2)
            self.assertFalse(self.reader.is_alive(), 'test cleanup left its own reader alive')
        self.sentinel.cancel()
        await asyncio.gather(self.sentinel, return_exceptions=True)

    async def start(self, port=0, ready=None):
        address = asyncio.get_running_loop().create_future()

        def listening(addr):
            if ready is not None:
                ready(addr)
            address.set_result(addr)

        self.runtime = asyncio.create_task(B.serve(self.bridge, '127.0.0.1', port, listening))
        done, _ = await asyncio.wait((address, self.runtime), timeout=2, return_when=asyncio.FIRST_COMPLETED)
        if self.runtime in done:
            await self.runtime
        self.assertIn(address, done, 'production listener did not become ready')
        return address.result()

    def assert_finished(self):
        self.assertFalse(self.bridge.running)
        self.assertIsNone(self.bridge.client)
        self.assertFalse(self.reader.is_alive())
        self.assertEqual(len(self.closed), 1)
        self.assertFalse(self.closed[0][1], 'the transport closed after its loop')
        self.assertFalse(self.sentinel.done(), 'serve cancelled an unrelated caller task')
        self.assertFalse(asyncio.get_running_loop().is_closed())
        remaining = asyncio.all_tasks() - self.before_tasks - {asyncio.current_task(), self.sentinel}
        self.assertFalse(remaining, f'production cleanup left tasks: {remaining}')

    async def test_cancel_waits_for_reader_before_closing_transport(self):
        await self.start()
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        original = self.transport.recv

        def held_recv(timeout):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test reader gate was not released')
            return original(timeout)

        with patch.object(self.transport, 'recv', held_recv):
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            self.runtime.cancel()
            try:
                done, _ = await asyncio.wait((self.runtime,), timeout=0.05)
                self.assertFalse(done, 'serve returned while its transport reader was held')
                self.assertFalse(self.closed, 'transport closed before the reader finished')
                self.assertGreater(self.bridge.stops_sent, 0, 'STOP must precede the reader wait')
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await self.runtime
        self.assert_finished()

    async def test_cancel_finishes_live_websocket_children_and_partial_http(self):
        entered, release = asyncio.Event(), asyncio.Event()
        self.releases.append(release)
        original = self.bridge._quiet_watch

        async def held_child():
            try:
                await original()
            finally:
                entered.set()
                await release.wait()

        with patch.object(self.bridge, '_quiet_watch', held_child):
            addr = await self.start()
            websocket = await asyncio.to_thread(WS, addr)
            reader, writer = await asyncio.open_connection(*addr[:2])
            try:
                await asyncio.to_thread(websocket.recv)
                writer.write(b'GET / HTTP/1.1\r\n')
                await writer.drain()
                self.runtime.cancel()
                await asyncio.wait_for(entered.wait(), 2)
                try:
                    done, _ = await asyncio.wait((self.runtime,), timeout=0.05)
                    self.assertFalse(done, 'serve returned before the real watchdog finalizer')
                    self.assertFalse(self.closed)
                    self.assertGreater(self.bridge.stops_sent, 0)
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await self.runtime
                try:
                    self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
                except ConnectionResetError:
                    pass  # An accepted socket with unread HTTP bytes may close with RST.
                self.assert_finished()
            finally:
                release.set()
                websocket.close()
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionResetError:
                    pass

    async def test_bind_failure_preserves_error_and_finishes_reader(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            with self.assertRaises(OSError) as error:
                await self.start(port=occupied.getsockname()[1])
        self.assertEqual(error.exception.errno, errno.EADDRINUSE)
        self.assert_finished()

    async def test_ready_callback_failure_preserves_original_error(self):
        error = ValueError('injected ready failure')

        def fail(_):
            raise error

        with self.assertRaises(ValueError) as caught:
            await self.start(ready=fail)
        self.assertIs(caught.exception, error)
        self.assert_finished()

    async def test_reader_timeout_is_not_reported_as_success(self):
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        original_recv, original_close = self.transport.recv, self.transport.close

        def held_recv(timeout):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test timeout gate was not released')
            return original_recv(timeout)

        def close_wakes_reader():
            release.set()
            original_close()

        with patch.object(self.transport, 'recv', held_recv), \
                patch.object(self.transport, 'close', close_wakes_reader), \
                patch.object(B, 'READER_JOIN_S', 0.03):
            await self.start()
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            self.runtime.cancel()
            with self.assertRaisesRegex(TimeoutError, 'reader did not stop'):
                await self.runtime
        self.assert_finished()

    async def test_stop_error_still_finishes_owned_resources_and_propagates(self):
        await self.start()
        error = ValueError('injected STOP failure')
        with patch.object(self.bridge, 'stop_all', side_effect=error):
            self.runtime.cancel()
            with self.assertRaises(ValueError) as caught:
                await self.runtime
        self.assertIs(caught.exception, error)
        self.assert_finished()


if __name__ == '__main__':
    unittest.main()
