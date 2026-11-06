// An RS-04 bus client in the browser, the async counterpart of rig/rs04.py's RS04Bus and Motor: requests with their
// replies, scan, parameters, ids, zero, save, and the jog's MIT frames. Every frame goes through the safety guard
// (guard.js) first; a refused frame is never sent and the call rejects with the reason. MIT licensed.
import * as P from './protocol.js';
import { createGuard } from './guard.js';

export class NoReply extends Error {}
export class Refused extends Error { constructor(r) { super(r.why); this.code = r.code; } }

/** transport: see transports.js. limits: a build profile's limits (guard.js). */
export function createClient(transport, { limits, host = P.HOST_ID, clock = () => performance.now() / 1000, timeoutMs = 60 } = {}) {
  const guard = createGuard(limits, { clock });
  const waiters = new Set(), taps = new Set();
  const last = new Map(), faults = new Map();            // newest feedback and type-21 frame per motor
  let chain = Promise.resolve();

  const offFrame = transport.onFrame((f) => {
    guard.observe(f);
    const m = f.ext !== false ? P.parse(f.id, f.data) : null;
    if (m?.type === 'feedback') last.set(m.motor, { ...m, at: clock() });
    else if (m?.type === 'fault') faults.set(m.motor, { ...m, at: clock() });
    for (const tap of taps) tap(f, m);
    if (m) for (const w of [...waiters]) if (w.want(m)) { waiters.delete(w); clearTimeout(w.timer); w.resolve(m); }
  });

  function send(frame) {
    const r = guard.check(frame);
    if (!r.ok) throw new Refused(r);
    for (const tap of taps) tap(frame, null, 'out');
    transport.send(frame);
  }
  /** Send one frame and wait for the first reply `want` accepts. Requests run one at a time. */
  function request(frame, want, ms = timeoutMs) {
    const run = () => new Promise((resolve, reject) => {
      const w = { want, resolve, timer: setTimeout(() => { waiters.delete(w); reject(new NoReply(
        `no reply to a ${P.TYPE_NAMES[P.idFields(frame.id)[0]] || '?'} frame for motor ${P.idFields(frame.id)[2]} within ${ms} ms`)); }, ms) };
      waiters.add(w);
      try { send(frame); } catch (e) { waiters.delete(w); clearTimeout(w.timer); reject(e); }
    });
    const p = chain.then(run, run);
    chain = p.catch(() => {});
    return p;
  }
  const fb = (id) => (m) => m.type === 'feedback' && m.motor === id;

  const api = {
    guard, transport, last, faults, host,
    /** Watch every frame: cb(frame, parsed, 'out' | undefined). Returns an off function. */
    tap(cb) { taps.add(cb); return () => taps.delete(cb); },
    send, request,
    async scan({ first = 1, last: end = 127, ms = 25, onProgress } = {}) {
      const found = [];
      for (let i = first; i <= end; i++) {
        onProgress?.(i);
        try {
          const m = await request(P.packGetId(i, host), (m) => m.type === 'id' && m.motor === i, ms);
          found.push({ id: i, uid: P.hex(m.uid) });
        } catch (e) { if (!(e instanceof NoReply)) throw e; }
      }
      return found;
    },
    async read(id, name) {
      const p = P.param(name);
      const m = await request(P.packRead(id, p.index, host), (m) => m.type === 'param' && m.motor === id && m.index === p.index);
      if (!m.ok) throw new NoReply(`motor ${id} refused to read ${p.name}`);
      return P.value(m);
    },
    async readAll(id) {
      const out = {};
      for (const p of Object.values(P.PARAMS)) {
        try { out[p.name] = await api.read(id, p.name); } catch (e) { if (e instanceof Refused) throw e; out[p.name] = null; }
      }
      return out;
    },
    write: (id, name, v) => request(P.packWrite(id, name, v, host), fb(id)),
    /** Write, read back, and reject if the motor kept something else (rig/rs04.py write_check). */
    async writeCheck(id, name, v, tol = 1e-4) {
      await api.write(id, name, v);
      const got = await api.read(id, name);
      if (Math.abs(Number(got) - Number(v)) > tol * Math.max(1, Math.abs(Number(v)))) throw new Error(`motor ${id}: wrote ${name} = ${v}, read back ${got}`);
      return got;
    },
    save: (id) => request(P.packSave(id, host), fb(id)),
    zero: (id) => request(P.packZero(id, host), fb(id)),
    stop: (id, clearFault = false) => request(P.packStop(id, host, clearFault), fb(id)),
    enable: (id) => request(P.packEnable(id, host), fb(id)),
    mit: (id, p, v, kp, kd, t) => request(P.packMit(id, p, v, kp, kd, t), fb(id)),
    async version(id) { return (await request(P.packVersion(id, host), (m) => m.type === 'version' && m.motor === id)).version; },
    async uid(id) { return P.hex((await request(P.packGetId(id, host), (m) => m.type === 'id' && m.motor === id)).uid); },
    async setId(id, newId) {
      const m = await request(P.packSetId(id, newId, host), (m) => m.type === 'id' && m.motor === newId);
      return m.motor;
    },
    /** STOP: a stop frame to every motor seen (and the factory id) at once, past any queued request; the bridge does
     *  the same on its side. Never throws. */
    stopAll() {
      guard.disarm();
      try { transport.disarm?.(); } catch { /* best effort */ }
      const ids = guard.stopTargets();
      try { transport.stopAll?.(ids); } catch { /* best effort */ }
      for (const id of ids) { try { transport.send(P.packStop(id, host)); } catch { /* best effort */ } }
      return ids;
    },
    arm(ids) {
      const r = guard.arm(ids);
      if (!r.ok) throw new Refused(r);
      transport.arm?.(ids);
    },
    disarm(ids) { guard.disarm(ids); transport.disarm?.(ids ?? null); },
    close() { offFrame(); for (const w of waiters) clearTimeout(w.timer); waiters.clear(); },
  };
  return api;
}
