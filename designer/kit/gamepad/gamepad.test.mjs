// Unit tests for the gamepad component's logic (no browser): node --test designer/kit/gamepad/gamepad.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { BUTTONS, DEFAULT_TUNING, createGamepads, normalizeTuning, readPad, rumble, shapeStick, shapeTrigger } from './gamepad.js';
import { createBindings, describeBinding, readBinding, validBinding } from './bindings.js';
import { createGamepadControl } from './control.js';

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

/** A fake pad as the browser reports it: standard mapping, 17 buttons, 4 axes. */
function fakePad(index = 0, { id = 'Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)', mapping = 'standard' } = {}) {
  return { index, id, mapping, connected: true, timestamp: 0, axes: [0, 0, 0, 0],
    buttons: BUTTONS.map(() => ({ pressed: false, value: 0 })),
    press(name, value = 1) { const b = this.buttons[BUTTONS.indexOf(name)]; b.value = value; b.pressed = value > 0; return this; },
    release(name) { const b = this.buttons[BUTTONS.indexOf(name)]; b.value = 0; b.pressed = false; return this; } };
}
function memoryStorage() {
  const m = new Map();
  return { m, getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
}

test('radial dead zone keeps direction and does not snap diagonals', () => {
  assert.deepEqual(shapeStick(0.1, 0.1, { stickDeadZone: 0.15, stickOuter: 1, curve: 1 }), [0, 0]);
  const [x, y] = shapeStick(0.3, 0.3, { stickDeadZone: 0.15, stickOuter: 1, curve: 1 });
  near(x, y);                                                 // still exactly diagonal
  near(Math.hypot(x, y), (Math.hypot(0.3, 0.3) - 0.15) / 0.85);
  // an axial dead zone would have zeroed this small x; the radial one keeps it
  const [sx] = shapeStick(0.1, 0.9, { stickDeadZone: 0.15, stickOuter: 1, curve: 1 });
  assert.ok(sx > 0.05);
});

test('outer dead zone reaches full scale and the curve softens the centre', () => {
  const [x] = shapeStick(0.96, 0, { stickDeadZone: 0.1, stickOuter: 0.95, curve: 2 });
  near(x, 1);
  const [lin] = shapeStick(0.5, 0, { stickDeadZone: 0, stickOuter: 1, curve: 1 });
  const [sq] = shapeStick(0.5, 0, { stickDeadZone: 0, stickOuter: 1, curve: 2 });
  near(lin, 0.5); near(sq, 0.25);
  assert.deepEqual(shapeStick(NaN, undefined), [0, 0]);
});

test('triggers ignore rest travel and rescale to 1', () => {
  assert.equal(shapeTrigger(0.04, 0.06), 0);
  near(shapeTrigger(1, 0.06), 1);
  near(shapeTrigger(0.53, 0.06), 0.5);
  assert.equal(shapeTrigger(-1), 0);
});

test('tuning is range-checked and per-axis inversion applies', () => {
  const t = normalizeTuning({ stickDeadZone: 5, stickOuter: 0, curve: 'x', invert: { RightY: true, Bogus: true } });
  assert.equal(t.stickDeadZone, 0.9);
  assert.ok(t.stickOuter > t.stickDeadZone);
  assert.equal(t.curve, DEFAULT_TUNING.curve);
  assert.deepEqual(t.invert, { LeftX: false, LeftY: false, RightX: false, RightY: true });
  const pad = fakePad(); pad.axes = [0, 0, 0, 1];
  assert.equal(readPad(pad, { ...t, stickDeadZone: 0, stickOuter: 1, curve: 1 }).axes.RightY, -1);
});

test('readPad names the standard mapping and flags non-standard pads', () => {
  const s = readPad(fakePad().press('A').press('RT', 0.8));
  assert.equal(s.standard, true);
  assert.equal(s.buttons.A.pressed, true);
  assert.ok(s.buttons.RT.value > 0.7 && s.buttons.RT.pressed);
  assert.equal(s.buttons.B.pressed, false);
  assert.equal(readPad(fakePad(0, { mapping: '' })).standard, false);
  // short button arrays (some pads report fewer) read as released
  assert.equal(readPad({ index: 0, axes: [], buttons: [] }).buttons.Guide.pressed, false);
});

test('hot-plug: connect, several pads, disconnect releases held buttons', () => {
  let list = [];
  const pads = createGamepads({ source: () => list, autoStart: false, target: null });
  const log = [];
  pads.on('connect', (p) => log.push(`+${p.index}`));
  pads.on('disconnect', (p) => log.push(`-${p.index}`));
  pads.on('button', (e) => log.push(`${e.index}:${e.button}:${e.pressed ? 'down' : 'up'}`));
  pads.poll();
  const a = fakePad(0), b = fakePad(1);
  list = [a, null, b];                        // browsers leave holes in the list
  pads.poll();
  a.press('Y'); pads.poll();
  list = [null, null, b];
  pads.poll();
  assert.deepEqual(log, ['+0', '+1', '0:Y:down', '0:Y:up', '-0']);
  assert.deepEqual(pads.pads().map((p) => p.index), [1]);
  // the same slot reused by a different controller releases what the old one held, then disconnects and connects
  b.press('A'); pads.poll();
  list = [null, fakePad(1, { id: 'Other pad' })];
  log.length = 0; pads.poll();
  assert.deepEqual(log, ['1:A:up', '-1', '+1']);
  pads.destroy();
});

test('a throwing or missing source is treated as no pads', () => {
  const pads = createGamepads({ source: () => { throw new Error('blocked'); }, autoStart: false, target: null });
  assert.deepEqual(pads.poll(), []);
});

test('rumble is feature-checked and never throws', () => {
  assert.equal(rumble(fakePad()), false);
  const calls = [];
  const pad = fakePad(); pad.vibrationActuator = { type: 'dual-rumble', playEffect: (type, p) => { calls.push([type, p]); return Promise.reject(new Error('no')); } };
  assert.equal(rumble(pad, { duration: 99, weak: 2, strong: -1 }), true);
  assert.deepEqual(calls[0], ['dual-rumble', { startDelay: 0, duration: 99, weakMagnitude: 1, strongMagnitude: 0 }]);
  const legacy = fakePad(); legacy.hapticActuators = [{ pulse: () => { throw new Error('denied'); } }];
  assert.equal(rumble(legacy), false);
});

const ACTIONS = {
  drive: { label: 'Drive', kind: 'axis', default: { axis: 'LeftY', invert: true } },
  height: { label: 'Height', kind: 'axis', default: { positive: 'RT', negative: 'LT' } },
  jump: { label: 'Jump', kind: 'button', default: { button: 'A' } },
  arm: { label: 'Arm', kind: 'button', hold: true, default: { button: 'Y' } },
  menu: { label: 'Menu', kind: 'button', default: { button: 'Menu' } },
};

test('bindings validate, describe and read', () => {
  assert.ok(validBinding({ button: 'A' }, 'button'));
  assert.ok(!validBinding({ axis: 'LeftY' }, 'button'));
  assert.ok(validBinding({ positive: 'RT', negative: 'LT' }, 'axis'));
  assert.ok(!validBinding({ positive: 'RT', negative: 'RT' }, 'axis'));
  assert.ok(!validBinding({ axis: 'Nope' }, 'axis'));
  assert.ok(validBinding(null, 'axis'));
  assert.equal(describeBinding({ axis: 'LeftY', invert: true }), 'Left stick ↕ (inverted)');
  const pad = readPad(Object.assign(fakePad().press('RT', 1).press('LT', 0.53), {}), { ...DEFAULT_TUNING, triggerDeadZone: 0.06 });
  near(readBinding({ positive: 'RT', negative: 'LT' }, pad), 0.5);
  assert.equal(readBinding(null, pad), 0);
});

test('bindings persist, survive corrupt storage and reset to defaults', () => {
  const storage = memoryStorage();
  const b = createBindings({ actions: ACTIONS, storageKey: 'k', storage });
  b.set('jump', { button: 'B' });
  b.setTuning({ stickDeadZone: 0.3 });
  const again = createBindings({ actions: ACTIONS, storageKey: 'k', storage });
  assert.deepEqual(again.get('jump'), { button: 'B' });
  assert.equal(again.tuning.stickDeadZone, 0.3);
  assert.deepEqual(again.conflicts('drive', { axis: 'LeftY' }), []);
  again.set('arm', { button: 'B' });
  assert.deepEqual(again.conflicts('arm'), ['jump']);
  again.reset();
  assert.deepEqual(again.get('jump'), { button: 'A' });
  assert.equal(storage.m.has('k'), false);
  storage.setItem('k', '{not json');
  assert.deepEqual(createBindings({ actions: ACTIONS, storageKey: 'k', storage }).get('jump'), { button: 'A' });
  storage.setItem('k', JSON.stringify({ version: 1, bindings: { jump: { axis: 'LeftX' }, drive: { axis: 'RightY' }, ghost: { button: 'A' } } }));
  const mixed = createBindings({ actions: ACTIONS, storageKey: 'k', storage });
  assert.deepEqual(mixed.get('jump'), { button: 'A' });           // wrong kind: default kept
  assert.deepEqual(mixed.get('drive'), { axis: 'RightY' });
  storage.setItem('k', JSON.stringify({ version: 1, bindings: { constructor: { button: 'A' }, toString: null } }));
  const proto = createBindings({ actions: ACTIONS, storageKey: 'k', storage });
  assert.equal(Object.hasOwn(proto.get(), 'constructor'), false, 'inherited names are not actions');
  assert.throws(() => proto.set('constructor', { button: 'A' }));
  const blocked = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('full'); }, removeItem() { throw new Error('denied'); } };
  const safe = createBindings({ actions: ACTIONS, storageKey: 'k', storage: blocked });
  safe.set('jump', { button: 'X' }); safe.reset();
  assert.deepEqual(safe.get('jump'), { button: 'A' });
  assert.throws(() => createBindings({ actions: { bad: { kind: 'button', default: { axis: 'LeftX' } } } }));
});

function rig(pads = [fakePad(0)], extra = {}) {
  let list = pads;
  const control = createGamepadControl({ actions: ACTIONS, storageKey: 't', storage: memoryStorage(), autoStart: false, target: null,
    source: () => list, ...extra });
  return { control, set: (l) => { list = l; } };
}

test('actions: values, holds and edges, the strongest of several pads', () => {
  const a = fakePad(0), b = fakePad(1);
  const { control } = rig([a, b]);
  control.setTuning({ stickDeadZone: 0, stickOuter: 1, curve: 1 });
  const events = [];
  control.on('action', (e) => events.push(`${e.name}:${e.pressed}`));
  a.axes[1] = -0.4; b.axes[1] = -0.9;
  a.press('A');
  control.poll();
  near(control.value('drive'), 0.9);                 // forward is up the stick: inverted
  assert.ok(control.held('jump') && control.pressed('jump'));
  control.poll();
  assert.ok(control.held('jump') && !control.pressed('jump'));
  a.release('A'); control.poll();
  assert.ok(control.released('jump') && !control.held('jump'));
  assert.deepEqual(events, ['jump:true', 'jump:false']);
});

test('suspend releases holds; a disconnected pad releases ARM', () => {
  const a = fakePad(0);
  const { control, set } = rig([a]);
  a.press('Y'); control.poll();
  assert.ok(control.held('arm'));
  const resume = control.suspend(); control.poll();
  assert.ok(!control.held('arm') && control.released('arm'));
  resume(); control.poll();
  assert.ok(control.held('arm'));
  set([]); control.poll();
  assert.ok(!control.held('arm'));
});

test('capture ignores inputs already held and reports the next one', async () => {
  const a = fakePad(0);
  const { control } = rig([a]);
  a.press('A'); control.poll();
  const c = control.capture({ kinds: ['button'] });
  control.poll();
  assert.ok(control.capturing, 'A was held at the start: not captured');
  assert.equal(control.value('jump'), 0, 'actions are suspended while capturing');
  a.release('A'); control.poll();
  a.press('X'); control.poll();
  assert.deepEqual(await c.promise, { type: 'button', button: 'X', index: 0 });
  a.axes[2] = -0.9;
  const s = control.capture({ kinds: ['axis'] });
  control.poll();
  assert.deepEqual(await s.promise, { type: 'axis', axis: 'RightX', sign: -1, index: 0 });
  // the press that finished a capture does not also fire its action, even after the caller resumes
  const events = [];
  control.on('action', (e) => events.push(`${e.name}:${e.pressed}`));
  a.axes[2] = 0; control.poll();
  const j = control.capture({ kinds: ['button'] });
  a.press('A'); control.poll();
  assert.deepEqual(await j.promise, { type: 'button', button: 'A', index: 0 });
  control.poll(); control.poll();
  assert.deepEqual(events, [], 'the rebind press is not a jump');
  assert.ok(control.suspended);
  a.release('A'); control.poll();
  assert.ok(!control.suspended);
  a.press('A'); control.poll();
  assert.deepEqual(events, ['jump:true']);
  a.release('A'); control.poll();
  const cancelled = control.capture();
  cancelled.cancel();
  assert.equal(await cancelled.promise, null);
  assert.ok(!control.suspended);
});

test('own requestAnimationFrame loop polls until stopped', () => {
  const frames = [];
  const control = createGamepadControl({ actions: ACTIONS, storage: memoryStorage(), target: null, source: () => [fakePad()],
    raf: (fn) => { frames.push(fn); return frames.length; }, caf: () => {} });
  let polled = 0; control.on('frame', () => polled++);
  frames.shift()(); frames.shift()();
  assert.equal(polled, 2);
  control.stop();
  frames.shift()?.();
  assert.equal(polled, 2);
  control.destroy();
});

test('tuning persists with the bindings and reset clears it', () => {
  const storage = memoryStorage();
  const one = createGamepadControl({ actions: ACTIONS, storageKey: 'p', storage, autoStart: false, target: null, source: () => [] });
  one.setTuning({ stickDeadZone: 0.25, invert: { RightY: true } });
  const two = createGamepadControl({ actions: ACTIONS, storageKey: 'p', storage, autoStart: false, target: null, source: () => [] });
  assert.equal(two.tuning.stickDeadZone, 0.25);
  assert.equal(two.tuning.invert.RightY, true);
  two.reset();
  assert.equal(two.tuning.stickDeadZone, DEFAULT_TUNING.stickDeadZone);
  assert.equal(two.tuning.invert.RightY, false);
});
