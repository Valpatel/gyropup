// Ways for the tool to reach a CAN bus, all with the same small interface:
//   { kind: 'emulator' | 'hardware', label, send(frame), onFrame(cb) -> off, onClose(cb), close(),
//     stopAll?(ids), arm?(ids), disarm?() }
// - createBridgeTransport: the SocketCAN bridge (rig/rs04_bridge.py) over a websocket. A PEAK PCAN-USB, a CANable on
//   candleLight (gs_usb) or any SocketCAN adapter: the browser cannot open them, the bridge can. The primary path.
// - createEmulatorTransport: software motors (emulator.js) in the page: demos and tests, no hardware.
// - createSlcanTransport: Web Serial to an adapter running slcan (Lawicel) firmware, e.g. a CANable on its slcan
//   build. Optional and untested on hardware (see README.md).
// MIT licensed (LICENSE in this folder).
import * as P from './protocol.js';
import { EmulatedRS04, VirtualBus } from './emulator.js';

function listeners() {
  const set = new Set();
  return { add(cb) { set.add(cb); return () => set.delete(cb); }, emit(...a) { for (const cb of [...set]) cb(...a); } };
}

/** Software motors on an in-page bus. motors: [{ id, uid? }]; returns the transport plus .bus for tests and demos. */
export function createEmulatorTransport({ motors = [{ id: P.FACTORY_ID }], clock = () => performance.now() / 1000, tickMs = 10 } = {}) {
  const bus = new VirtualBus(), frames = listeners(), closed = listeners();
  for (const m of motors) bus.attach(new EmulatedRS04({ clock, ...m }));
  bus.onFrame(f => queueMicrotask(() => frames.emit(f)));
  const timer = tickMs ? setInterval(() => bus.tick(clock()), tickMs) : null;
  return {
    kind: 'emulator', label: `emulator: ${motors.length} software RS-04${motors.length === 1 ? '' : 's'}`, bus,
    send(f) { bus.send({ id: f.id, data: Uint8Array.from(f.data), ext: f.ext !== false }); },
    onFrame: frames.add, onClose: closed.add,
    close() { if (timer) clearInterval(timer); closed.emit('closed'); },
  };
}

/**
 * The SocketCAN bridge. url: ws://127.0.0.1:8765/ws (the page served by the bridge passes its own address and token).
 * Resolves once the bridge has said hello: { iface, profile, kind: 'hardware' | 'virtual' }.
 */
export function createBridgeTransport(url, { WebSocketImpl = globalThis.WebSocket, timeoutMs = 3000 } = {}) {
  const frames = listeners(), closed = listeners(), refused = listeners();
  return new Promise((resolve, reject) => {
    const ws = new WebSocketImpl(url);
    const timer = setTimeout(() => { reject(new Error(`no answer from the bridge at ${url}`)); ws.close(); }, timeoutMs);
    let hello = null;
    const msg = (o) => { if (ws.readyState === 1) ws.send(JSON.stringify(o)); };
    ws.onerror = () => { if (!hello) { clearTimeout(timer); reject(new Error(`could not reach the bridge at ${url}`)); } };
    ws.onclose = (e) => { clearTimeout(timer); if (!hello) reject(new Error(e.reason || 'the bridge closed the connection')); else closed.emit(e.reason || 'closed'); };
    ws.onmessage = (e) => {
      let m; try { m = JSON.parse(e.data); } catch { return; }
      if (m.op === 'hello') {
        clearTimeout(timer);
        hello = m;
        resolve({
          kind: m.kind === 'virtual' ? 'emulator' : 'hardware', hello: m,
          label: m.kind === 'virtual' ? `bridge ${m.iface} (its software motors)` : `bridge on ${m.iface} (real CAN bus)`,
          send(f) { msg({ op: 'send', id: f.id, data: P.hex(f.data), ext: f.ext !== false }); },
          stopAll(ids = []) { msg({ op: 'stop_all', ids }); },
          arm(ids) { msg({ op: 'arm', ids }); }, disarm(ids = null) { msg({ op: 'disarm', ids }); },
          onFrame: frames.add, onClose: closed.add, onRefused: refused.add,
          close() { ws.close(1000, 'closed by the tool'); },
        });
      } else if (m.op === 'frame') frames.emit({ id: m.id, data: P.unhex(m.data), ext: m.ext !== false });
      else if (m.op === 'refused') refused.emit(m);
    };
  });
}

// ------------------------------------------------------------------------------- slcan (Lawicel ASCII) over Web Serial
/** One frame as an slcan command: 'T' + 8 hex id + length + data (extended) or 't' + 3 hex id (standard), then CR. */
export function slcanEncode({ id, data, ext = true }) {
  const d = Array.from(data);
  if (d.length > 8) throw new RangeError('a classic CAN frame carries at most 8 bytes');
  return (ext ? 'T' + (id >>> 0).toString(16).toUpperCase().padStart(8, '0') : 't' + (id & 0x7FF).toString(16).toUpperCase().padStart(3, '0'))
    + d.length + P.hex(d).toUpperCase() + '\r';
}
/** One received slcan line (without its CR) -> a frame, or null for anything else (acks, errors, remote frames). */
export function slcanDecode(line) {
  const m = /^(T)([0-9A-Fa-f]{8})([0-8])([0-9A-Fa-f]*)$/.exec(line) || /^(t)([0-9A-Fa-f]{3})([0-8])([0-9A-Fa-f]*)$/.exec(line);
  if (!m) return null;
  const n = Number(m[3]);
  if (m[4].length < 2 * n) return null;
  return { id: parseInt(m[2], 16) & (m[1] === 'T' ? 0x1FFFFFFF : 0x7FF), data: P.unhex(m[4].slice(0, 2 * n)), ext: m[1] === 'T' };
}
/** Splits a byte stream into slcan lines; returns { push(bytes) -> [lines] }. */
export function slcanLines() {
  let buf = '';
  return { push(bytes) {
    buf += String.fromCharCode(...bytes);
    const parts = buf.split(/[\r\x07]/);
    buf = parts.pop();
    return parts.filter(Boolean);
  } };
}

/**
 * A serial port (navigator.serial.requestPort() in the page) running slcan firmware, at 1 Mbit/s CAN ('S8').
 * Resolves with the transport once the channel is open.
 */
export async function createSlcanTransport(port, { baudRate = 115200 } = {}) {
  const frames = listeners(), closed = listeners();
  await port.open({ baudRate });
  const writer = port.writable.getWriter(), enc = new TextEncoder();
  const write = (s) => writer.write(enc.encode(s));
  await write('\rC\r');            // flush, close the channel if it was open
  await write('S8\r');             // 1 Mbit/s
  await write('O\r');              // open
  let open = true;
  const lines = slcanLines();
  (async () => {
    const reader = port.readable.getReader();
    try {
      while (open) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const line of lines.push(value)) { const f = slcanDecode(line); if (f) frames.emit(f); }
      }
    } catch (e) { /* the port went away */ } finally { reader.releaseLock(); open = false; closed.emit('the serial port closed'); }
  })();
  return {
    kind: 'hardware', label: 'Web Serial slcan adapter (real CAN bus)',
    send(f) { if (open) write(slcanEncode(f)); },
    onFrame: frames.add, onClose: closed.add,
    async close() { open = false; try { await write('C\r'); writer.releaseLock(); await port.close(); } catch { /* already gone */ } },
  };
}
