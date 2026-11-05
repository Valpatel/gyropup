// Actions bound to gamepad buttons and axes: defaults, validation, persistence and reading values from a pad.
// No dependencies; the page defines its own actions. MIT licensed (LICENSE in this folder).
import { AXES, BUTTONS, LABELS } from './gamepad.js';

/**
 * An action is { label, kind: 'button' | 'axis', default: binding, hold?, help? }.
 *
 * A binding is one of:
 * - { button: 'A' }                       a button; reads 0..1 (analogue triggers read their travel)
 * - { axis: 'LeftY', invert: true }       a stick axis; reads -1..1 (invert flips it for this action only)
 * - { positive: 'RT', negative: 'LT' }    two buttons as one axis; reads positive - negative (-1..1)
 * - null                                  unbound
 *
 * A 'button' action takes a button binding; an 'axis' action takes an axis or a button pair.
 */
export function validBinding(binding, kind) {
  if (binding === null) return true;
  if (!binding || typeof binding !== 'object') return false;
  if (kind === 'button') return Object.keys(binding).length === 1 && BUTTONS.includes(binding.button);
  if ('axis' in binding) return AXES.includes(binding.axis) && Object.keys(binding).every((k) => k === 'axis' || (k === 'invert' && typeof binding.invert === 'boolean'));
  if ('positive' in binding || 'negative' in binding) {
    return Object.keys(binding).every((k) => k === 'positive' || k === 'negative')
      && [binding.positive, binding.negative].every((b) => b === undefined || b === null || BUTTONS.includes(b))
      && (binding.positive || binding.negative) && binding.positive !== binding.negative;
  }
  return false;
}

/** The inputs a binding uses (button and axis names). */
export function bindingInputs(binding) {
  if (!binding) return [];
  if (binding.button) return [binding.button];
  if (binding.axis) return [binding.axis];
  return [binding.positive, binding.negative].filter(Boolean);
}

/** A short readable name for a binding: "A", "Left stick ↕ (inverted)", "Right trigger − Left trigger". */
export function describeBinding(binding) {
  if (!binding) return 'not bound';
  if (binding.button) return LABELS[binding.button];
  if (binding.axis) return LABELS[binding.axis] + (binding.invert ? ' (inverted)' : '');
  return [binding.positive && LABELS[binding.positive], binding.negative && `− ${LABELS[binding.negative]}`].filter(Boolean).join(' ');
}

/** The value of one binding on one pad snapshot: 0..1 for a button, -1..1 for an axis or a pair. */
export function readBinding(binding, pad) {
  if (!binding || !pad) return 0;
  if (binding.button) return pad.buttons[binding.button]?.value ?? 0;
  if (binding.axis) { const v = pad.axes[binding.axis] ?? 0; return binding.invert ? -v || 0 : v; }
  const p = binding.positive ? pad.buttons[binding.positive]?.value ?? 0 : 0;
  const n = binding.negative ? pad.buttons[binding.negative]?.value ?? 0 : 0;
  return p - n;
}

/** localStorage, or a stand-in when storage is blocked (private modes, sandboxed frames, tests). */
export function safeStorage() {
  try {
    const s = globalThis.localStorage;
    const probe = '__gamepad_probe__';
    s.setItem(probe, '1'); s.removeItem(probe);
    return s;
  } catch {
    const mem = new Map();
    return { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k) };
  }
}

/**
 * createBindings({ actions, storageKey, storage }) -> the action map.
 *
 * Bindings and tuning are stored together as JSON under storageKey. Every read and write is wrapped in try/catch:
 * a full or blocked store, or a corrupt or older record, falls back to the defaults for whatever cannot be used.
 */
export function createBindings({ actions, storageKey = 'gamepad-bindings-v1', storage = safeStorage() }) {
  if (!actions || typeof actions !== 'object') throw new Error('createBindings needs an actions object');
  for (const [name, a] of Object.entries(actions)) {
    if (a.kind !== 'button' && a.kind !== 'axis') throw new Error(`Action ${name}: kind must be 'button' or 'axis'`);
    if (!validBinding(a.default ?? null, a.kind)) throw new Error(`Action ${name}: invalid default binding`);
  }
  const defaults = () => Object.fromEntries(Object.entries(actions).map(([n, a]) => [n, a.default ? structuredClone(a.default) : null]));
  let map = defaults(), tuning = null;
  const listeners = new Set();

  function load() {
    let stored = null;
    try { stored = JSON.parse(storage.getItem(storageKey) ?? 'null'); } catch { stored = null; }
    map = defaults(); tuning = null;
    if (stored && typeof stored === 'object' && stored.version === 1) {
      for (const [name, binding] of Object.entries(stored.bindings ?? {})) {
        if (Object.hasOwn(actions, name) && validBinding(binding, actions[name].kind)) map[name] = binding === null ? null : structuredClone(binding);
      }
      if (stored.tuning && typeof stored.tuning === 'object') tuning = stored.tuning;
    }
  }
  const notify = () => { for (const fn of [...listeners]) { try { fn(get()); } catch (err) { console.error(err); } } };
  function save() {
    try { storage.setItem(storageKey, JSON.stringify({ version: 1, bindings: map, ...(tuning ? { tuning } : {}) })); } catch { /* storage full or blocked */ }
    notify();
  }
  const get = () => structuredClone(map);
  load();

  return {
    actions,
    get: (name) => (name ? structuredClone(map[name] ?? null) : get()),
    set(name, binding) {
      if (!Object.hasOwn(actions, name)) throw new Error(`Unknown action: ${name}`);
      if (!validBinding(binding, actions[name].kind)) throw new Error(`Invalid binding for ${name}`);
      map[name] = binding === null ? null : structuredClone(binding);
      save();
    },
    /** Other actions that use any input of this binding. */
    conflicts(name, binding = map[name]) {
      const inputs = new Set(bindingInputs(binding));
      return Object.keys(actions).filter((other) => other !== name && bindingInputs(map[other]).some((i) => inputs.has(i)));
    },
    reset() { map = defaults(); tuning = null; try { storage.removeItem(storageKey); } catch { /* blocked */ } notify(); },
    /** The stored tuning (or null), kept beside the bindings so one reset clears both. */
    get tuning() { return tuning ? structuredClone(tuning) : null; },
    setTuning(value) { tuning = value ? structuredClone(value) : null; save(); },
    read(name, pad) { return readBinding(map[name], pad); },
    reload: load,
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
  };
}
