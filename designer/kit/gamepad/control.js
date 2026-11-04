// The gamepad controller a page uses: pads + action bindings + persistence + rebinding capture, read once a
// frame. No dependencies on the page. MIT licensed (LICENSE in this folder).
import { AXES, BUTTONS, DEFAULT_TUNING, createGamepads, normalizeTuning } from './gamepad.js';
import { createBindings, safeStorage } from './bindings.js';

/**
 * createGamepadControl(options) -> controller
 *
 * options:
 * - actions: { name: { label, kind: 'button' | 'axis', default, hold?, help? } } (see bindings.js)
 * - storageKey: where bindings and tuning persist (localStorage; a blocked store falls back to memory)
 * - autoStart: poll on requestAnimationFrame by itself (default true); pass false and call poll() from your frame
 * - source, target, raf, caf, storage: injection points for tests
 *
 * Reading, after each poll: value(name) (-1..1 or 0..1), held(name), pressed(name) / released(name) (this frame
 * only). Events: 'action' ({ name, pressed, value }) on every button-action edge, 'connect', 'disconnect', 'frame'.
 * Several pads work at once: each action reads whichever connected pad pushes it furthest.
 */
export function createGamepadControl({ actions, storageKey = 'gamepad-control-v1', autoStart = true, source, target, raf, caf,
  storage = safeStorage(), holdThreshold = 0.5 } = {}) {
  const bindings = createBindings({ actions, storageKey, storage });
  const pads = createGamepads({ source, target, raf, caf, autoStart: false, tuning: normalizeTuning(bindings.tuning ?? DEFAULT_TUNING) });
  const requestFrame = raf ?? (typeof requestAnimationFrame === 'function' ? requestAnimationFrame : (fn) => setTimeout(() => fn(Date.now()), 16));
  const cancelFrame = caf ?? (typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : clearTimeout);
  const names = Object.keys(actions);
  const values = Object.fromEntries(names.map((n) => [n, 0]));
  const holds = new Set(), down = new Set(), up = new Set();
  const listeners = new Map();
  let suspended = 0, capture = null, frame = 0, running = false;

  const emit = (type, payload) => { for (const fn of [...(listeners.get(type) ?? [])]) { try { fn(payload); } catch (err) { console.error(err); } } };
  const on = (type, fn) => {
    if (type === 'connect' || type === 'disconnect' || type === 'button') return pads.on(type, fn);
    if (!listeners.has(type)) listeners.set(type, new Set());
    listeners.get(type).add(fn);
    return () => listeners.get(type)?.delete(fn);
  };

  function update(list) {
    down.clear(); up.clear();
    for (const name of names) {
      let best = 0;
      if (!suspended) for (const pad of list) { const v = bindings.read(name, pad); if (Math.abs(v) > Math.abs(best)) best = v; }
      values[name] = best;
      if (actions[name].kind !== 'button') continue;
      const isHeld = best >= holdThreshold, was = holds.has(name);
      if (isHeld === was) continue;
      if (isHeld) { holds.add(name); down.add(name); } else { holds.delete(name); up.add(name); }
      emit('action', { name, pressed: isHeld, value: best });
    }
  }

  function stepCapture(list) {
    if (!capture) return;
    const c = capture;
    for (const pad of list) {
      for (const button of BUTTONS) {
        const key = `${pad.index}:${button}`, pressed = pad.buttons[button].pressed;
        if (!pressed) { c.blocked.delete(key); continue; }
        if (c.blocked.has(key)) continue;
        if (c.kinds.includes('button')) return finishCapture({ type: 'button', button, index: pad.index });
      }
      if (!c.kinds.includes('axis')) continue;
      for (const axis of AXES) {
        const key = `${pad.index}:${axis}`, v = pad.axes[axis];
        if (Math.abs(v) < 0.25) { c.blocked.delete(key); continue; }
        if (c.blocked.has(key)) continue;
        if (Math.abs(v) >= c.axisThreshold) return finishCapture({ type: 'axis', axis, sign: Math.sign(v), index: pad.index });
      }
    }
    if (c.deadline && now() >= c.deadline) finishCapture(null);
  }
  const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
  function finishCapture(result) {
    const c = capture;
    if (!c) return;
    capture = null; suspended -= 1;
    c.resolve(result);
  }

  function poll() {
    const list = pads.poll();
    stepCapture(list);
    update(list);
    emit('frame', list);
    return list;
  }
  const loop = () => { if (!running) return; poll(); frame = requestFrame(loop); };

  if (autoStart) { running = true; frame = requestFrame(loop); }

  return {
    actions, bindings, on, poll,
    start() { if (running) return; running = true; frame = requestFrame(loop); },
    stop() { running = false; if (frame) cancelFrame(frame); frame = 0; },
    pads: () => pads.pads(),
    get connected() { return pads.pads().length > 0; },
    value: (name) => values[name] ?? 0,
    held: (name) => holds.has(name),
    pressed: (name) => down.has(name),
    released: (name) => up.has(name),
    /** Stop actions while something else owns the pad (a menu, a rebind). Holds release at the next poll. */
    suspend() { suspended += 1; let done = false; return () => { if (!done) { done = true; suspended -= 1; } }; },
    get suspended() { return suspended > 0; },
    /**
     * Wait for the next input to bind: { kinds: ['button'] | ['axis'] | ['button', 'axis'], timeoutMs }.
     * Inputs already held when capture starts are ignored until released. Resolves with
     * { type: 'button', button } or { type: 'axis', axis, sign }, or null on cancel or timeout. Actions are
     * suspended meanwhile, so a rebind press never also drives the page.
     */
    capture({ kinds = ['button', 'axis'], timeoutMs = 10000, axisThreshold = 0.6 } = {}) {
      if (capture) finishCapture(null);
      const blocked = new Set();
      for (const pad of pads.pads()) {
        for (const b of BUTTONS) if (pad.buttons[b].pressed) blocked.add(`${pad.index}:${b}`);
        for (const a of AXES) if (Math.abs(pad.axes[a]) >= 0.25) blocked.add(`${pad.index}:${a}`);
      }
      suspended += 1;
      let resolve;
      const promise = new Promise((r) => { resolve = r; });
      capture = { kinds, blocked, axisThreshold, resolve, deadline: timeoutMs ? now() + timeoutMs : 0 };
      return { promise, cancel: () => { if (capture?.resolve === resolve) finishCapture(null); } };
    },
    get capturing() { return !!capture; },
    get tuning() { return pads.tuning; },
    setTuning(partial) { const t = pads.setTuning(partial); bindings.setTuning(t); emit('tuning', t); return t; },
    /** Defaults for every binding and the tuning; clears the stored record. */
    reset() { bindings.reset(); const t = pads.setTuning(structuredClone(DEFAULT_TUNING)); emit('tuning', t); },
    canRumble: () => pads.pads().some((p) => pads.canRumble(p.index)),
    /** Rumble every pad that supports it; returns how many accepted the effect. */
    rumble: (effect) => pads.pads().filter((p) => pads.rumble(p.index, effect)).length,
    destroy() { this.stop(); if (capture) finishCapture(null); pads.destroy(); listeners.clear(); },
  };
}
