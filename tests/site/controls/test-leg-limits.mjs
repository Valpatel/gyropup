// designer/leg_limits.js: the playground's leg limits are the firmware's (docs/leg-protection.md).
//   node --test tools/test-leg-limits.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {createLegLimits, windowAt, yawLimitRadS, RATES, legRateMMPerS, vmaxMPerS} from '../../../software/site/designer/leg_limits.js';

const root = new URL('../../../', import.meta.url);
const limits = JSON.parse(await readFile(new URL('exports/leg/limits.json', root), 'utf8'));
const model = await readFile(new URL('firmware/balance/include/gp/gp_model.h', root), 'utf8');
const control = await readFile(new URL('firmware/balance/src/core/gp_control.c', root), 'utf8');
const manifest = JSON.parse(await readFile(new URL('exports/sim/v2/rig/manifest.json', root), 'utf8'));
const [hMin, hMax] = manifest.fivebar.h_range_mm;
const info = {hMin, hMax, v2: true};
const table = limits.command.window;
const def = (name) => Number(model.match(new RegExp(`#define ${name} (-?[0-9.]+)f`))[1]);

test('the rates are the firmware\'s', () => {
  assert.equal(RATES.heightFracPerS, def('GP_G_HEIGHT_RATE'));
  assert.equal(RATES.hMinM, def('GP_H_MIN_M'));
  assert.equal(RATES.hMaxM, def('GP_H_MAX_M'));
  assert.equal(RATES.accelMPerS2, def('GP_G_ACCEL'));
  assert.equal(RATES.speedMargin, def('GP_G_SPEED_MARGIN'));
  assert.equal(RATES.wheelWPerV, def('GP_WHEEL_W_PER_V'));
  assert.equal(RATES.wheelRM, def('GP_WHEEL_R_M'));
  assert.match(control, new RegExp(`const float dl = ${RATES.leanRadPerS}f \\* dt;`));
  assert.ok(Math.abs(legRateMMPerS - 114) < 0.01 && vmaxMPerS > 1.5, 'the sliders\' 1.5 m/s is inside vmax');
});

test('the reach table is the generated one and matches sim/leg_limits.py window_at', () => {
  assert.deepEqual(windowAt(table, 0), [0.107, 0.383]);
  const [a, b] = windowAt(table, -0.325);                     // halfway between the -0.35 and -0.3 rows
  const r35 = table.find((r) => r[0] === -0.35), r30 = table.find((r) => r[0] === -0.3);
  assert.ok(Math.abs(a - (r35[1] + r30[1]) / 2) < 1e-12 && Math.abs(b - (r35[2] + r30[2]) / 2) < 1e-12);
  assert.deepEqual(windowAt(table, -9), [table[0][1], table[0][2]]);
});

test('fit keeps both legs inside the window at any pose the sliders or a gamepad can ask for', () => {
  const L = createLegLimits({table});
  let seed = 7;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  let windowed = 0;
  for (let k = 0; k < 20000; k++) {
    const pose = {height: rnd() * 1.2 - 0.1, pitch: (rnd() - 0.5) * 0.7, rollMM: (rnd() - 0.5) * 160};
    const out = L.fit(pose, info);
    const [lo, hi] = windowAt(table, pose.pitch).map((v) => v * 1000);
    const h = hMin + (hMax - hMin) * out.height;
    for (const leg of [h + out.rollMM / 2, h - out.rollMM / 2]) {
      assert.ok(leg >= Math.max(lo, hMin) - 1e-9 && leg <= Math.min(hi, hMax) + 1e-9, JSON.stringify({pose, out}));
    }
    if (out.windowed) windowed++;
  }
  assert.ok(windowed > 1000, 'the extremes are clamped');
  // full height leaning back 0.35 rad is out of the five-bar's reach: fit lowers it to the window's top
  const back = L.fit({height: 1, pitch: -0.35, rollMM: 0}, info);
  assert.ok(back.windowed && Math.abs(hMin + (hMax - hMin) * back.height - windowAt(table, -0.35)[1] * 1000) < 1e-9);
  // upright, mid height, level: untouched
  assert.deepEqual(L.fit({height: 0.6, pitch: 0, rollMM: 0}, info), {height: 0.6, pitch: 0, rollMM: 0, windowed: false});
  // the legacy serial-leg robot (robot3d.js: no info.v2, up to 390.5 mm) is not held to the five-bar's window
  assert.deepEqual(L.fit({height: 1, pitch: -0.3, rollMM: 0}, {hMin: 150, hMax: 390.5}), {height: 1, pitch: -0.3, rollMM: 0, windowed: false});
});

test('step slews toward the targets no faster than the firmware', () => {
  const L = createLegLimits({table});
  assert.deepEqual(L.step({height: 0.2, pitch: 0, rollMM: 0, speed: 0}, 0.016, info),
                   {height: 0.2, pitch: 0, rollMM: 0, speed: 0, turn: 0, limited: false});        // the first frame is the start
  const dt = 1 / 60;
  let out;
  for (let k = 0; k < 60; k++) out = L.step({height: 1, pitch: 0.35, rollMM: 80, speed: 9}, dt, info);
  assert.ok(Math.abs((out.height - 0.2) * (hMax - hMin) - legRateMMPerS) < 1e-6, 'one second: 114 mm of leg');
  assert.ok(Math.abs(out.pitch - 0.35) < 1e-9, '0.35 rad in 0.7 s at 0.5 rad/s');
  assert.ok(Math.abs(out.rollMM - 80) < 1e-9);
  assert.ok(Math.abs(out.speed - RATES.accelMPerS2) < 1e-9 && out.limited, 'and the speed at 1.5 m/s^2 toward vmax');
  for (let k = 0; k < 120; k++) out = L.step({height: 1, pitch: 0.35, rollMM: 80, speed: 9}, dt, info);
  assert.ok(Math.abs(out.speed - vmaxMPerS) < 1e-9 && Math.abs(out.height - 1) < 1e-9 && !out.limited);
  // a paused frame (dt 0) holds
  assert.deepEqual(L.step({height: 0, pitch: 0, rollMM: 0, speed: 0}, 0, info), {...out, limited: false});
});

test('the turn is held to what the outer wheel and the legs take at the speed (gp_guard_yaw_rate)', () => {
  const yaw = limits.yaw, D = 180 / Math.PI;
  assert.ok(Math.abs(yawLimitRadS(0, yaw) - vmaxMPerS / yaw.half_track_m) < 1e-9);
  assert.ok(Math.abs(yawLimitRadS(1, yaw) - yaw.a_lat_m_s2) < 1e-9);
  for (const [v, w] of Object.entries(yaw.at_speed_rad_s_36v)) assert.ok(Math.abs(yawLimitRadS(Number(v), yaw) - w) < 0.006, v);
  const L = createLegLimits({table, yaw});
  const dt = 1 / 60;
  let out = L.step({height: 0.6, pitch: 0, rollMM: 0, speed: 0, turn: 90}, dt, info);
  assert.equal(out.turn, 90);                                        // the slider's 90 deg/s at a stand: untouched
  for (let k = 0; k < 120; k++) out = L.step({height: 0.6, pitch: 0, rollMM: 0, speed: 1.5, turn: 90}, dt, info);
  assert.ok(Math.abs(out.turn - yaw.a_lat_m_s2 / 1.5 * D) < 1e-9 && out.limited, 'full drive and full turn: a_lat');
  for (let k = 0; k < 240; k++) out = L.step({height: 0.6, pitch: 0, rollMM: 0, speed: -9, turn: -400}, dt, info);
  assert.ok(Math.abs(out.speed + vmaxMPerS) < 1e-9 && out.turn === 0, 'at vmax the outer wheel has nothing left');
  // the legacy view keeps its own turn
  assert.equal(createLegLimits({table, yaw}).step({speed: 1.5, turn: 90}, 0, {hMin: 150, hMax: 390.5}).turn, 90);
});

test('load reads the table from the served file and keeps the rates when it cannot', async () => {
  const ok = await createLegLimits().load('/', async (url) => {
    assert.equal(url, '/exports/leg/limits.json');
    return {ok: true, json: async () => limits};
  });
  assert.ok(ok.ready);
  const warn = console.warn; console.warn = () => {};
  try {
    const bad = await createLegLimits().load('/', async () => ({ok: false, status: 404}));
    assert.ok(!bad.ready);
    assert.deepEqual(bad.fit({height: 1, pitch: -0.35, rollMM: 0}, info), {height: 1, pitch: -0.35, rollMM: 0, windowed: false});
  } finally { console.warn = warn; }
});
