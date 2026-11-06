"""The RS-04 configuration tool's bridge: a SocketCAN bus to the browser over a websocket, with the tool's safety rules
(rig/rs04_guard.py) on every frame it puts on the bus. The browser cannot open a CAN adapter; this can. A PEAK
PCAN-USB (Linux: peak_usb), a CANable on candleLight (gs_usb) or any SocketCAN interface works the same.

    sudo ip link set can0 up type can bitrate 1000000
    python -m rig.rs04_bridge --iface can0                    # then open http://127.0.0.1:8765/
    python -m rig.rs04_bridge --iface emu --emu-ids 127       # a software motor at the factory id, no hardware
    python -m rig.rs04_bridge --iface can0 --lan --token-file /etc/gyropup/bridge-token   # on the robot, opt-in

It serves the tool's page (designer/motor-tool.html and designer/kit/rs04/) and nothing else of the repository, and
takes one browser tab at a time. By default it listens on 127.0.0.1 only. --lan listens on every interface and then
requires a token (in the page's address: ?token=...); a websocket from another site's page is always refused (its
Origin must be this bridge's own address), so a web page you happen to visit cannot reach the motors.

When the tab closes, its connection drops or it goes quiet for QUIET_S while a motor is armed, the bridge sends a
stop to every motor it has seen. The motors' own canTimeout (kept on by the guard) stops them too.

Standard library only (Python 3.10, JetPack 6's), so the robot needs nothing installed beyond this repository.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from rig import rs04 as P
from rig import rs04_profiles
from rig.rs04_guard import Guard

ROOT = Path(__file__).resolve().parents[1]
PAGE = '/designer/motor-tool.html'
SERVED = ('designer/motor-tool.html', 'designer/motor-tool.js', 'designer/kit/rs04/', 'hardware/actuators/rs04/profiles/', 'web/icon.svg',
          'web/theme.js', 'web/theme.css',
          'exports/motor-day/derating.json', 'exports/leg/thermal/motor_thermal.json')
WS_GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_MESSAGE = 1 << 16
LOOPBACK = ('127.0.0.1', 'localhost', '::1')
QUIET_S = 1.0             # armed and no message from the tab for this long: stop everything
READER_JOIN_S = 5.0        # a stuck receive must fail shutdown, never report a clean exit
VERSION = 1


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------------- a minimal RFC 6455 server side
async def ws_read(reader: asyncio.StreamReader):
    """One message: (opcode, payload). Fragmented messages are refused (the tool never sends them)."""
    b0, b1 = await reader.readexactly(2)
    op, n = b0 & 0x0F, b1 & 0x7F
    if not b0 & 0x80:
        raise ConnectionError('fragmented websocket messages are not accepted')
    if not b1 & 0x80:
        raise ConnectionError('an unmasked frame from a client')
    if n == 126:
        n = int.from_bytes(await reader.readexactly(2), 'big')
    elif n == 127:
        n = int.from_bytes(await reader.readexactly(8), 'big')
    if n > MAX_MESSAGE:
        raise ConnectionError('message too large')
    mask = await reader.readexactly(4)
    data = bytearray(await reader.readexactly(n))
    for i in range(n):
        data[i] ^= mask[i & 3]
    return op, bytes(data)


def ws_frame(op: int, payload: bytes) -> bytes:
    n = len(payload)
    head = bytes((0x80 | op,)) + (bytes((n,)) if n < 126 else bytes((126,)) + n.to_bytes(2, 'big') if n < 65536
                                  else bytes((127,)) + n.to_bytes(8, 'big'))
    return head + payload


def http_response(code: int, reason: str, body: bytes = b'', ctype: str = 'text/plain; charset=utf-8', extra=()) -> bytes:
    head = [f'HTTP/1.1 {code} {reason}', f'Content-Type: {ctype}', f'Content-Length: {len(body)}',
            'Cache-Control: no-store', 'X-Content-Type-Options: nosniff', "Content-Security-Policy: default-src 'self'; "
            "connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; img-src 'self' data:", 'Connection: close', *extra]
    return ('\r\n'.join(head) + '\r\n\r\n').encode() + body


def served_file(path: str) -> Optional[Path]:
    """The file for a request path, only inside the tool's own files (never ../, never the rest of the repository)."""
    rel = path.lstrip('/')
    if not rel or '..' in rel.split('/') or '\\' in rel or not any(rel == s or (s.endswith('/') and rel.startswith(s)) for s in SERVED):
        return None
    f = (ROOT / rel).resolve()
    try:
        f.relative_to(ROOT)
    except ValueError:
        return None
    return f if f.is_file() else None


class Bridge:
    def __init__(self, transport, profile: dict, iface: str, kind: str, token: Optional[str] = None,
                 allow_origins=(), clock=time.monotonic):
        self.t = transport
        self.profile = profile
        self.iface, self.kind = iface, kind
        self.token = token
        self.allow_origins = set(allow_origins)
        self.guard = Guard(profile['limits'], clock=clock)
        self.clock = clock
        self.client = None                    # (writer, queue) of the one connected tab
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.lock = threading.Lock()          # the guard is touched by the CAN reader thread and the event loop
        self.running = True
        self.last_msg = clock()
        self.stops_sent = 0

    # ------------------------------------------------------------------ the bus side
    def reader_thread(self):
        while self.running:
            try:
                f = self.t.recv(0.05)
            except OSError as e:
                log('CAN receive failed:', e)
                time.sleep(0.5)
                continue
            if f is None:
                continue
            cid, data, ext = f
            with self.lock:
                self.guard.observe(cid, data, ext)
            if self.loop and self.client:
                msg = json.dumps({'op': 'frame', 'id': cid, 'data': bytes(data).hex(), 'ext': ext})
                self.loop.call_soon_threadsafe(self._push, msg)

    def _push(self, msg: str):
        if self.client:
            try:
                self.client[1].put_nowait(msg)
            except asyncio.QueueFull:
                pass                           # a slow tab loses telemetry, never a stop

    def stop_all(self, why: str, extra=()):
        with self.lock:
            self.guard.disarm()
            ids = sorted(set(self.guard.stop_targets()) | {int(i) for i in extra if 0 < int(i) < 128})
        for i in ids:
            try:
                self.t.send(*P.pack_stop(i), True)
                self.stops_sent += 1
            except OSError as e:
                log('stop to motor', i, 'failed:', e)
        log(f'STOP all ({why}): motors {ids}')
        return ids

    # ------------------------------------------------------------------ the browser side
    def origin_ok(self, headers: dict) -> bool:
        """The page must be this bridge's own (or an --allow-origin one). Without a token the address must also be this
        computer's loopback, so a site that points its own name at 127.0.0.1 (DNS rebinding) is refused too."""
        origin, host = headers.get('origin'), headers.get('host', '')
        if origin is None:
            return False
        if self.token is None and urlsplit(f'http://{host}').hostname not in LOOPBACK:
            return False
        return origin in self.allow_origins or origin == f'http://{host}'

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            writer.close()
            return
        lines = raw.decode('latin-1').split('\r\n')
        try:
            method, target, _ = lines[0].split(' ', 2)
        except ValueError:
            writer.close()
            return
        headers = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(':') for ln in lines[1:] if ln)}
        url = urlsplit(target)
        query = parse_qs(url.query)
        try:
            if url.path == '/ws' and headers.get('upgrade', '').lower() == 'websocket':
                await self.websocket(reader, writer, headers, query)
            elif method not in ('GET', 'HEAD'):
                writer.write(http_response(405, 'Method Not Allowed', b'GET only'))
            elif url.path == '/':
                tok = query.get('token', [''])[0]
                loc = PAGE + '?bridge=1' + (f'&token={tok}' if tok and re.fullmatch(r'[A-Za-z0-9_-]+', tok) else '')
                writer.write(http_response(302, 'Found', extra=(f'Location: {loc}',)))
            else:
                f = served_file(url.path)
                if f is None:
                    writer.write(http_response(404, 'Not Found', b'not part of the motor tool'))
                else:
                    ctype = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
                    if f.suffix in ('.js', '.mjs'):
                        ctype = 'text/javascript'
                    body = f.read_bytes()
                    writer.write(http_response(200, 'OK', b'' if method == 'HEAD' else body,
                                               ctype + ('; charset=utf-8' if ctype.startswith('text/') else '')))
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def websocket(self, reader, writer, headers, query):
        if not self.origin_ok(headers):
            log('refused a websocket from origin', headers.get('origin'))
            writer.write(http_response(403, 'Forbidden', b'origin not allowed'))
            return
        if self.token is not None and not hmac.compare_digest(query.get('token', [''])[0].encode(), self.token.encode()):
            log('refused a websocket without the token')
            writer.write(http_response(403, 'Forbidden', b'token required'))
            return
        if self.client is not None:
            writer.write(http_response(409, 'Conflict', b'another tab holds the bridge: close it first'))
            return
        key = headers.get('sec-websocket-key', '').encode()
        accept = base64.b64encode(hashlib.sha1(key + WS_GUID).digest()).decode()
        writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                      f'Sec-WebSocket-Accept: {accept}\r\n\r\n').encode())
        queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.client = (writer, queue)
        self.last_msg = self.clock()
        peer = writer.get_extra_info('peername')
        log('tab connected from', peer[0] if peer else '?')
        await queue.put(json.dumps({'op': 'hello', 'version': VERSION, 'iface': self.iface, 'kind': self.kind,
                                    'profile': self.profile['id'], 'profile_version': self.profile['version'],
                                    'limits': self.profile['limits']}))
        sender = asyncio.ensure_future(self._sender(writer, queue))
        watchdog = asyncio.ensure_future(self._quiet_watch())
        why = 'the tab closed'
        try:
            while True:
                op, payload = await ws_read(reader)
                self.last_msg = self.clock()
                if op == 8:
                    break
                if op == 9:
                    await queue.put(('pong', payload))
                    continue
                if op != 1:
                    continue
                await self.message(payload, queue)
        except (asyncio.IncompleteReadError, ConnectionError) as e:
            why = f'the connection dropped ({e.__class__.__name__})'
        finally:
            self.client = None
            sender.cancel()
            watchdog.cancel()
            try:
                self.stop_all(why)
                log('tab disconnected')
            finally:
                results = await asyncio.gather(sender, watchdog, return_exceptions=True)
                for result in results:
                    if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                        raise result

    async def _sender(self, writer, queue):
        try:
            while True:
                m = await queue.get()
                if isinstance(m, tuple):
                    writer.write(ws_frame(10, m[1]))
                else:
                    writer.write(ws_frame(1, m.encode()))
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass

    async def _quiet_watch(self):
        while True:
            await asyncio.sleep(0.2)
            if self.guard.armed and self.clock() - self.last_msg > QUIET_S:
                self.stop_all(f'the tab was quiet for {QUIET_S:g} s while armed')

    async def message(self, payload: bytes, queue):
        try:
            m = json.loads(payload)
        except ValueError:
            return
        op = m.get('op')
        if op == 'send':
            try:
                cid, data, ext = int(m['id']), bytes.fromhex(m['data']), bool(m.get('ext', True))
                if len(data) > 8 or not 0 <= cid < (1 << 29):
                    raise ValueError('bad frame')
            except (KeyError, ValueError, TypeError):
                await queue.put(json.dumps({'op': 'refused', 'code': 'bad-frame', 'why': 'not a CAN frame'}))
                return
            with self.lock:
                ok, code, why = self.guard.check(cid, data, ext)
            if not ok:
                log('refused:', why)
                await queue.put(json.dumps({'op': 'refused', 'id': cid, 'data': data.hex(), 'code': code, 'why': why}))
                return
            try:
                self.t.send(cid, data, ext)
            except OSError as e:
                await queue.put(json.dumps({'op': 'refused', 'id': cid, 'data': data.hex(), 'code': 'bus', 'why': str(e)}))
        elif op == 'stop_all':
            self.stop_all('STOP from the tab', m.get('ids') or ())
        elif op == 'arm':
            with self.lock:
                ok, code, why = self.guard.arm([int(i) for i in m.get('ids', [])])
            if not ok:
                await queue.put(json.dumps({'op': 'refused', 'code': code, 'why': why}))
        elif op == 'disarm':
            with self.lock:
                self.guard.disarm(None if m.get('ids') is None else [int(i) for i in m['ids']])
        # 'ping' and anything else: only refreshes last_msg


def make_transport(iface: str, emu_ids):
    if iface == 'emu':
        from rig.canio import VirtualBus
        from rig.rs04_emu import EmulatedRS04
        vb = VirtualBus()
        motors = [EmulatedRS04(i) for i in emu_ids]
        for m in motors:
            vb.attach(m.handle)
        port = vb.port()
        port.motors = motors
        return port, 'virtual'
    from rig.canio import SocketCan
    return SocketCan(iface), 'hardware'


async def serve(bridge: Bridge, bind: str, port: int, ready=None):
    """Own this server's connections, reader and transport, but not the caller's loop."""
    bridge.loop = asyncio.get_running_loop()
    server, th = None, None
    handlers, writers = set(), set()
    closing = False

    async def handle(reader, writer):
        try:
            await bridge.handle(reader, writer)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            finally:
                writers.discard(writer)

    def finished(task):
        handlers.discard(task)
        if not task.cancelled() and task.exception() is not None:
            bridge.loop.call_exception_handler({'message': 'RS-04 connection handler failed',
                                                'exception': task.exception(), 'task': task})

    def connected(reader, writer):
        if closing:
            writer.transport.abort()
            return
        # Register synchronously: cancellation can precede the coroutine's first step.
        writers.add(writer)
        task = bridge.loop.create_task(handle(reader, writer))
        handlers.add(task)
        task.add_done_callback(finished)

    try:
        th = threading.Thread(target=bridge.reader_thread, daemon=True)
        th.start()
        server = await asyncio.start_server(connected, bind, port, limit=1 << 16)
        if ready:
            ready(server.sockets[0].getsockname())
        # start_server already accepts connections. In Python 3.12 serve_forever's
        # cancellation waits for clients before our finally can close those clients.
        await asyncio.Future()
    finally:
        closing = True
        if server is not None:
            server.close()
        bridge.running = False
        errors = []
        try:
            bridge.stop_all('the bridge is shutting down')
        except BaseException as error:
            errors.append(error)
        # No final telemetry flush may delay a motor STOP or keep a client alive.
        for writer in tuple(writers):
            writer.transport.abort()
        owned = tuple(handlers)
        for task in owned:
            task.cancel()
        results = await asyncio.gather(*owned, return_exceptions=True)
        errors.extend(error for error in results if isinstance(error, BaseException)
                      and not isinstance(error, asyncio.CancelledError))
        if th is not None and th.ident is not None:
            await asyncio.to_thread(th.join, READER_JOIN_S)
            if th.is_alive():
                errors.append(TimeoutError('RS-04 reader did not stop before transport closure'))
        try:
            bridge.t.close()
        except BaseException as error:
            errors.append(error)
        if th is not None and th.is_alive():
            # Closing may wake a stuck transport. Even if it does, retain the timeout failure.
            await asyncio.to_thread(th.join, READER_JOIN_S)
        if server is not None:
            await server.wait_closed()  # Python 3.12 includes accepted connections in this wait.
        if errors:
            raise errors[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.rs04_bridge', description=__doc__.split('\n\n')[0])
    ap.add_argument('--iface', default='can0', help="SocketCAN interface, or 'emu' for software motors")
    ap.add_argument('--emu-ids', type=int, nargs='*', default=[127], help='ids of the software motors (--iface emu)')
    ap.add_argument('--profile', default=None, help=f'build profile ({", ".join(rs04_profiles.names())}); the default one when omitted')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--bind', default='127.0.0.1', help='address to listen on (127.0.0.1: this computer only)')
    ap.add_argument('--lan', action='store_true', help='listen on every interface; needs --token-file (or makes a token)')
    ap.add_argument('--token-file', help='a file holding the token the page must present (?token=...)')
    ap.add_argument('--allow-origin', action='append', default=[], help='another page origin allowed to connect')
    a = ap.parse_args(argv)
    profile = rs04_profiles.load(a.profile)
    token = None
    if a.token_file:
        token = Path(a.token_file).read_text().strip()
        if len(token) < 16:
            ap.error('the token must be at least 16 characters')
    if a.lan:
        a.bind = '0.0.0.0'
        if token is None:
            token = secrets.token_urlsafe(18)
            log('LAN mode without --token-file: this run\'s token is', token)
    elif a.bind not in ('127.0.0.1', '::1', 'localhost') and token is None:
        ap.error('listening beyond this computer needs --lan with a token')
    transport, kind = make_transport(a.iface, a.emu_ids)
    bridge = None
    runtime_started = False
    try:
        bridge = Bridge(transport, profile, a.iface, kind, token=token, allow_origins=a.allow_origin)
        shown = '127.0.0.1' if a.bind in ('0.0.0.0', '127.0.0.1') else a.bind

        async def run():
            nonlocal runtime_started
            runtime_started = True
            await serve(bridge, a.bind, a.port, lambda addr: log(
                f'open http://{shown}:{addr[1]}/{"?token=" + token if token and not a.lan else ""}'
                + ('  (LAN: use the robot\'s address and ?token=)' if a.lan else '')))

        log(f'RS-04 bridge on {a.iface} ({kind}), profile {profile["id"]} v{profile["version"]}: cap '
            f'{profile["limits"]["limit_torque_nm"]:g} N m, jog {profile["limits"]["jog_torque_nm"]:g} N m')
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    finally:
        if not runtime_started:
            try:
                if bridge is not None:
                    bridge.running = False
                    bridge.stop_all('the bridge could not start')
            finally:
                transport.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
