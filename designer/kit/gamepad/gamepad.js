// Gamepad input over the browser Gamepad API: hot-plug for several pads, the W3C "standard" mapping under Xbox
// names, radial stick dead zones with a response curve, trigger dead zones, per-axis inversion and rumble.
// No dependencies and no knowledge of the page that uses it. MIT licensed (LICENSE in this folder).

/** Buttons of the W3C standard gamepad mapping, in index order, named as on an Xbox controller. */
export const BUTTONS = Object.freeze(['A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'View', 'Menu', 'LS', 'RS',
  'Up', 'Down', 'Left', 'Right', 'Guide']);
/** Axes of the standard mapping, in index order. Y is positive downwards, as the browser reports it. */
export const AXES = Object.freeze(['LeftX', 'LeftY', 'RightX', 'RightY']);
/** The two sticks and their axes. */
export const STICKS = Object.freeze({ Left: ['LeftX', 'LeftY'], Right: ['RightX', 'RightY'] });
/** Readable names, for menus and prompts. */
export const LABELS = Object.freeze({ A: 'A', B: 'B', X: 'X', Y: 'Y', LB: 'Left bumper', RB: 'Right bumper',
  LT: 'Left trigger', RT: 'Right trigger', View: 'View', Menu: 'Menu', LS: 'Left stick click', RS: 'Right stick click',
  Up: 'D-pad up', Down: 'D-pad down', Left: 'D-pad left', Right: 'D-pad right', Guide: 'Xbox button',
  LeftX: 'Left stick ↔', LeftY: 'Left stick ↕', RightX: 'Right stick ↔', RightY: 'Right stick ↕' });

/**
 * Tuning, applied to every pad.
 * - stickDeadZone: radial dead zone of each stick (fraction of full deflection). Inside it the stick reads zero.
 * - stickOuter: deflection treated as full scale, so a worn stick still reaches 1.
 * - curve: response exponent applied to the rescaled magnitude (1 = linear, 2 = fine control near centre).
 * - triggerDeadZone: analogue trigger travel ignored at rest.
 * - invert: per axis, flip the sign the page sees.
 */
export const DEFAULT_TUNING = Object.freeze({ stickDeadZone: 0.15, stickOuter: 0.95, curve: 1.5, triggerDeadZone: 0.06,
  invert: Object.freeze({ LeftX: false, LeftY: false, RightX: false, RightY: false }) });

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const finite = (v, fallback) => (Number.isFinite(+v) ? +v : fallback);

/** A complete, range-checked tuning from any partial or stored object. */
export function normalizeTuning(input = {}) {
  const t = input && typeof input === 'object' ? input : {};
  const stickDeadZone = clamp(finite(t.stickDeadZone, DEFAULT_TUNING.stickDeadZone), 0, 0.9);
  const stickOuter = clamp(finite(t.stickOuter, DEFAULT_TUNING.stickOuter), stickDeadZone + 0.05, 1);
  const invert = {};
  for (const axis of AXES) invert[axis] = typeof t.invert?.[axis] === 'boolean' ? t.invert[axis] : DEFAULT_TUNING.invert[axis];
  return { stickDeadZone, stickOuter, curve: clamp(finite(t.curve, DEFAULT_TUNING.curve), 0.5, 4),
    triggerDeadZone: clamp(finite(t.triggerDeadZone, DEFAULT_TUNING.triggerDeadZone), 0, 0.9), invert };
}

/**
 * Shape one stick. The dead zone is radial (on the stick's distance from centre, not on each axis), so a diagonal
 * near the centre is not snapped to an axis; the magnitude is then rescaled from the dead zone to stickOuter and
 * passed through the response curve, keeping the stick's direction.
 */
export function shapeStick(x, y, { stickDeadZone = DEFAULT_TUNING.stickDeadZone, stickOuter = DEFAULT_TUNING.stickOuter,
  curve = DEFAULT_TUNING.curve } = {}) {
  x = finite(x, 0); y = finite(y, 0);
  const m = Math.hypot(x, y);
  if (m <= stickDeadZone || m === 0) return [0, 0];
  const scaled = clamp((m - stickDeadZone) / Math.max(1e-6, stickOuter - stickDeadZone), 0, 1) ** curve;
  return [x / m * scaled, y / m * scaled];
}

/** Shape one analogue trigger (0..1): the rest travel is ignored and the rest rescaled to reach 1. */
export function shapeTrigger(v, deadZone = DEFAULT_TUNING.triggerDeadZone) {
  v = clamp(finite(v, 0), 0, 1);
  return v <= deadZone ? 0 : clamp((v - deadZone) / Math.max(1e-6, 1 - deadZone), 0, 1);
}

/** A plain snapshot of one browser Gamepad object, shaped by the tuning. */
export function readPad(raw, tuning = DEFAULT_TUNING) {
  const t = normalizeTuning(tuning);
  const rawAxes = Array.from(raw.axes ?? [], (v) => finite(v, 0));
  const rawButtons = Array.from(raw.buttons ?? [], (b) => (typeof b === 'object' && b
    ? { pressed: !!b.pressed, value: finite(b.value, b.pressed ? 1 : 0) } : { pressed: !!b, value: b ? 1 : 0 }));
  const axes = {};
  for (const [stick, [ax, ay]] of Object.entries(STICKS)) {
    const i = stick === 'Left' ? 0 : 2;
    const [x, y] = shapeStick(rawAxes[i] ?? 0, rawAxes[i + 1] ?? 0, t);
    axes[ax] = t.invert[ax] ? -x : x;
    axes[ay] = t.invert[ay] ? -y : y;
  }
  for (const k of AXES) if (Object.is(axes[k], -0)) axes[k] = 0;
  const buttons = {};
  BUTTONS.forEach((name, i) => {
    const b = rawButtons[i] ?? { pressed: false, value: 0 };
    if (name === 'LT' || name === 'RT') {
      const value = shapeTrigger(b.value, t.triggerDeadZone);
      buttons[name] = { pressed: value > 0.5 || (b.pressed && value > 0), value };
    } else buttons[name] = { pressed: b.pressed, value: b.pressed ? (b.value > 0 ? clamp(b.value, 0, 1) : 1) : 0 };
  });
  return { index: raw.index, id: String(raw.id ?? ''), mapping: String(raw.mapping ?? ''), standard: raw.mapping === 'standard',
    connected: raw.connected !== false, timestamp: finite(raw.timestamp, 0), axes, buttons, raw: { axes: rawAxes, buttons: rawButtons } };
}

/** Whether a pad can rumble (dual-rumble effects or the older haptic actuators). */
export function canRumble(raw) {
  return !!(raw && (typeof raw.vibrationActuator?.playEffect === 'function' || typeof raw.hapticActuators?.[0]?.pulse === 'function'));
}

/**
 * Rumble a pad if the browser supports it. Returns true when an effect was requested. Never throws: a pad that
 * refuses the effect (or a page without permission) is ignored.
 */
export function rumble(raw, { duration = 140, weak = 0.6, strong = 0.4 } = {}) {
  if (!canRumble(raw)) return false;
  const params = { startDelay: 0, duration: clamp(finite(duration, 140), 0, 5000),
    weakMagnitude: clamp(finite(weak, 0.6), 0, 1), strongMagnitude: clamp(finite(strong, 0.4), 0, 1) };
  try {
    if (typeof raw.vibrationActuator?.playEffect === 'function') {
      const done = raw.vibrationActuator.playEffect(raw.vibrationActuator.type ?? 'dual-rumble', params);
      done?.catch?.(() => {});
    } else {
      const done = raw.hapticActuators[0].pulse(Math.max(params.weakMagnitude, params.strongMagnitude), params.duration);
      done?.catch?.(() => {});
    }
    return true;
  } catch { return false; }
}

const defaultSource = () => {
  try { return typeof navigator !== 'undefined' && navigator.getGamepads ? navigator.getGamepads() : []; } catch { return []; }
};

/**
 * createGamepads(options) -> the pads, polled once a frame.
 *
 * options:
 * - source: () => list of Gamepad objects (default navigator.getGamepads; tests pass a fake)
 * - tuning: initial tuning (see DEFAULT_TUNING)
 * - autoStart: poll on requestAnimationFrame by itself (default true). Pass false and call poll() from your own
 *   frame loop to keep input in step with your simulation.
 * - target: where connect/disconnect events are heard (default window)
 *
 * Events (on(type, fn) returns an unsubscribe function):
 * - 'connect' (pad snapshot), 'disconnect' ({ index, id }), 'frame' (array of snapshots, after each poll),
 *   'button' ({ index, button, pressed, value, pad }) on every press and release.
 *
 * Polling reads state only: it never calls preventDefault, never takes focus and never listens to keyboard or
 * mouse events, so the rest of the page's input keeps working.
 */
export function createGamepads({ source = defaultSource, tuning = DEFAULT_TUNING, autoStart = true,
  target = typeof window !== 'undefined' ? window : null, raf, caf } = {}) {
  const requestFrame = raf ?? (typeof requestAnimationFrame === 'function' ? requestAnimationFrame : (fn) => setTimeout(() => fn(Date.now()), 16));
  const cancelFrame = caf ?? (typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : clearTimeout);
  const listeners = new Map();
  const known = new Map();          // index -> { snapshot, raw }
  let current = normalizeTuning(tuning), frame = 0, running = false, destroyed = false;

  const emit = (type, payload) => { for (const fn of [...(listeners.get(type) ?? [])]) { try { fn(payload); } catch (err) { console.error(err); } } };
  const on = (type, fn) => {
    if (!listeners.has(type)) listeners.set(type, new Set());
    listeners.get(type).add(fn);
    return () => listeners.get(type)?.delete(fn);
  };

  function list() {
    let pads;
    try { pads = source() ?? []; } catch { pads = []; }
    return Array.from(pads).filter((p) => p && p.connected !== false);
  }

  function poll() {
    if (destroyed) return [];
    const seen = new Set();
    for (const raw of list()) {
      const index = Number.isInteger(raw.index) ? raw.index : seen.size;
      seen.add(index);
      // Gamepad fields are prototype getters: copy them by name rather than spreading the object.
      const snapshot = readPad({ index, axes: raw.axes, buttons: raw.buttons, id: raw.id, mapping: raw.mapping,
        timestamp: raw.timestamp, connected: raw.connected }, current);
      const before = known.get(index);
      if (before && before.snapshot.id !== snapshot.id) { known.delete(index); emit('disconnect', { index, id: before.snapshot.id }); }
      const previous = known.get(index)?.snapshot;
      known.set(index, { snapshot, raw });
      if (!previous) emit('connect', snapshot);
      for (const name of BUTTONS) {
        const was = previous?.buttons[name]?.pressed ?? false, now = snapshot.buttons[name].pressed;
        if (was !== now) emit('button', { index, button: name, pressed: now, value: snapshot.buttons[name].value, pad: snapshot });
      }
    }
    for (const [index, entry] of [...known]) {
      if (seen.has(index)) continue;
      known.delete(index);
      // A pad that vanished releases whatever it was holding (a held ARM must not stay held).
      for (const name of BUTTONS) if (entry.snapshot.buttons[name].pressed) emit('button', { index, button: name, pressed: false, value: 0, pad: entry.snapshot });
      emit('disconnect', { index, id: entry.snapshot.id });
    }
    const pads = [...known.values()].map((e) => e.snapshot).sort((a, b) => a.index - b.index);
    emit('frame', pads);
    return pads;
  }

  const loop = () => { if (!running) return; poll(); frame = requestFrame(loop); };
  function start() { if (running || destroyed) return; running = true; frame = requestFrame(loop); }
  function stop() { running = false; if (frame) cancelFrame(frame); frame = 0; }

  // The browser's own events make plugging in feel immediate; polling still catches pads that never announce
  // themselves (some browsers only expose a pad after a button press).
  const onConnect = () => { if (!running) poll(); };
  const onDisconnect = () => poll();
  target?.addEventListener?.('gamepadconnected', onConnect);
  target?.addEventListener?.('gamepaddisconnected', onDisconnect);
  if (autoStart) start();

  return {
    on, poll, start, stop,
    get running() { return running; },
    /** Snapshots of the connected pads, lowest index first (from the last poll). */
    pads: () => [...known.values()].map((e) => e.snapshot).sort((a, b) => a.index - b.index),
    pad: (index) => known.get(index)?.snapshot ?? null,
    get tuning() { return structuredClone(current); },
    setTuning(partial) { current = normalizeTuning({ ...current, ...partial, invert: { ...current.invert, ...(partial?.invert ?? {}) } }); return structuredClone(current); },
    canRumble: (index) => canRumble(known.get(index)?.raw),
    rumble: (index, effect) => rumble(known.get(index)?.raw, effect),
    destroy() {
      stop(); destroyed = true; listeners.clear(); known.clear();
      target?.removeEventListener?.('gamepadconnected', onConnect);
      target?.removeEventListener?.('gamepaddisconnected', onDisconnect);
    },
  };
}
