/** Gamepad control in the playground and the kit's demo page, with navigator.getGamepads mocked. */
import assert from 'node:assert/strict';
import { readFile,mkdir,writeFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
import {checkHopProgress,HOP_LIMITS,pollHop,readHopSample} from './hop-budget.mjs';
import { acknowledgePrototypeNotice } from '../content/test-prototype-session.mjs';

const base = (process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : { headless: true });

// A fake standard-mapping pad the page reads through navigator.getGamepads; tests drive it with window.__fakePads.
const mockPads = () => {
  const NAMES = ['A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'View', 'Menu', 'LS', 'RS', 'Up', 'Down', 'Left', 'Right', 'Guide'];
  const slots = [null, null, null, null];
  const make = (index) => ({ index, id: `Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13) #${index}`, mapping: 'standard',
    connected: true, timestamp: 0, axes: [0, 0, 0, 0], buttons: NAMES.map(() => ({ pressed: false, touched: false, value: 0 })),
    vibrationActuator: { type: 'dual-rumble', effects: [], playEffect(type, params) { this.effects.push([type, params]); return Promise.resolve('complete'); } } });
  window.__fakePads = {
    slots,
    connect(index = 0) { slots[index] = make(index); window.dispatchEvent(Object.assign(new Event('gamepadconnected'), { gamepad: slots[index] })); return slots[index]; },
    disconnect(index = 0) { const pad = slots[index]; slots[index] = null; window.dispatchEvent(Object.assign(new Event('gamepaddisconnected'), { gamepad: pad })); },
    axes(index, values) { slots[index].axes = values.slice(); slots[index].timestamp++; },
    button(index, name, value) { const b = slots[index].buttons[NAMES.indexOf(name)]; b.value = value; b.pressed = value > 0.1; slots[index].timestamp++; },
  };
  Object.defineProperty(Navigator.prototype, 'getGamepads', { configurable: true, value() { return slots.slice(); } });
};

const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await acknowledgePrototypeNotice(context);
await context.addInitScript(() => { localStorage.setItem('gyropup.probe', 'off'); localStorage.setItem('gyropup-sfx', '0'); });
await context.addInitScript(mockPads);
const page = await context.newPage(), errors = [];
page.on('pageerror', (e) => errors.push(e.message));
const pad = (fn, ...args) => page.evaluate(([fn, args]) => window.__fakePads[fn](...args), [fn, args]);
const sim = (expr) => page.evaluate(expr);
const until = (fn, arg, timeout = 15000) => page.waitForFunction(fn, arg, { timeout });
// Software rendering can take longer than a short press between frames: hold until a poll has seen it.
const seen = (name, pressed) => until(([n, p]) => (window.__sim?.gamepad.control.pads()[0]?.buttons[n].pressed ?? !p) === p, [name, pressed]);
async function tap(name) { await pad('button', 0, name, 1); await seen(name, true); await pad('button', 0, name, 0); await seen(name, false); }

async function openSim(query = 'run=none&demo=0&sound=0') {
  await page.goto(`${base}/designer/sim.html?${query}`);
  await until(() => document.body.dataset.ready === '1' && !!window.__sim?.state.robot && !!window.__sim.gamepad, null, 90000);
}

try {
  // ---- no pad: the page is unchanged apart from the panel section; the pill stays hidden
  await openSim();
  assert.equal(await page.locator('#gamepad-pill').isHidden(), true, 'No pad: no topbar pill');
  assert.match(await page.locator('.gp-pad-status').textContent(), /Connect an Xbox-layout controller/);

  // ---- hot-plug
  await pad('connect', 0);
  await until(() => !document.getElementById('gamepad-pill').hidden);
  assert.match(await page.locator('.gp-pad-status').textContent(), /Connected: Xbox Wireless Controller/);

  // ---- left stick: drive (absolute) and turn; the demo hands over control
  await sim(() => { window.__sim.command.speed(0); });
  await pad('axes', 0, [0, -1, 0, 0]);
  await until(() => window.__sim.state.speed > 1.4 && !window.__sim.demo.on);
  assert.ok(await sim(() => window.__sim.state.speed <= 1.5), 'Drive is clamped to the slider range');
  await pad('axes', 0, [0, 0, 0, 0]);
  await until(() => window.__sim.state.speed === 0);
  // a resting pad never fights the slider
  await page.locator('#panel input[type=range]').nth(3).evaluate((el) => { el.value = '0.5'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.waitForTimeout(300);
  assert.equal(await sim(() => window.__sim.state.speed), 0.5, 'Slider keeps working beside an idle pad');
  await sim(() => window.__sim.command.speed(0));
  const yaw0 = await sim(() => window.__sim.state.yaw);
  await pad('axes', 0, [1, 0, 0, 0]);
  await until(() => window.__sim.state.turn > 80);
  await until((y) => window.__sim.state.yaw < y - 0.2, yaw0);
  await pad('axes', 0, [0, 0, 0, 0]);
  await until(() => window.__sim.state.turn === 0);

  // ---- right stick: pan and tilt rates, clamped to the sliders' ranges and the deck limit
  const pan0 = await sim(() => window.__sim.gun.pan);
  await pad('axes', 0, [0, 0, 1, 0]);
  await until((p) => window.__sim.gun.pan < p - 0.3, pan0);
  await pad('axes', 0, [0, 0, 0, -1]);
  const tiltMax = await sim(() => +[...document.querySelectorAll('#panel .hud-slider')].find((l) => /^Tilt/.test(l.textContent)).querySelector('input').max);
  await until((m) => Math.abs(window.__sim.gun.tilt * 180 / Math.PI - m) < 1e-6, tiltMax);
  // Set up the lower-stop check separately. The stick uses clamped stage dt,
  // so traversing the entire range also measures the software renderer's frame rate.
  await pad('axes', 0, [0, 0, 0, 0]);
  await until(() => window.__sim.gamepad.control.value('tilt') === 0);
  const downStart = await sim(() => {
    const s = window.__sim;
    const slider = [...document.querySelectorAll('#panel .hud-slider')].find((l) => /^Tilt/.test(l.textContent)).querySelector('input');
    const limit = Math.max(+slider.min, -s.tiltLimitDeg());
    s.command.tiltDeg(limit + 4);
    return { tilt: s.gun.tilt * 180 / Math.PI, limit };
  });
  assert.ok(Math.abs(downStart.tilt - downStart.limit - 4) < 1e-6, 'Lower-stop setup leaves four degrees for the stick to move');
  const tiltTrace = await page.evaluateHandle(() => {
    const s = window.__sim, axis = () => window.__fakePads.slots[0]?.axes[3];
    let frames = 0, downFrames = 0, simulatedS = 0;
    const off = s.stage.onFrame((_, dt) => {
      frames++;
      if (axis() === 1) { downFrames++; simulatedS += dt; }
    });
    return () => {
      off();
      return { tilt: s.gun.tilt * 180 / Math.PI, pan: s.gun.pan * 180 / Math.PI, axis: axis(), input: s.gamepad.control.value('tilt'),
        frames, downFrames, simulatedS, visibility: document.visibilityState, stageError: document.body.dataset.stageError || null };
    };
  });
  let tiltError;
  try {
    await pad('axes', 0, [0, 0, 0, 1]);
    await until(() => { const s = window.__sim, slider = [...document.querySelectorAll('#panel .hud-slider')].find((l) => /^Tilt/.test(l.textContent)).querySelector('input');
      return s.gamepad.control.value('tilt') === -1 && Math.abs(s.gun.tilt * 180 / Math.PI - Math.max(+slider.min, -s.tiltLimitDeg())) < 1e-6; });
  } catch (error) {
    tiltError = error;
    throw error;
  } finally {
    let observed;
    try { observed = await tiltTrace.evaluate(finish => finish()); await tiltTrace.dispose(); }
    catch (error) { if (!tiltError) throw error; observed = { observationError: error.message }; }
    if (tiltError) console.error('Lower tilt stop failure state:', JSON.stringify({ start: downStart, observed }));
  }
  const { tilt, limit } = await sim(() => {
    const s = window.__sim;
    const slider = [...document.querySelectorAll('#panel .hud-slider')].find((l) => /^Tilt/.test(l.textContent)).querySelector('input');
    return { tilt: s.gun.tilt * 180 / Math.PI, limit: Math.max(+slider.min, -s.tiltLimitDeg()) };
  });
  assert.ok(Math.abs(tilt - limit) < 1e-6, `Held down, tilt ${tilt} stops at the slider/deck limit (${limit})`);
  await pad('axes', 0, [0, 0, 0, 0]);

  // ---- triggers: body height
  await sim(() => window.__sim.command.height(0.5));
  await pad('button', 0, 'RT', 1);
  await until(() => window.__sim.state.height === 1);
  await pad('button', 0, 'RT', 0);
  await pad('button', 0, 'LT', 1);
  await until(() => window.__sim.state.height < 0.7);
  await pad('button', 0, 'LT', 0);

  // ---- fire needs ARM held; ARM is a hold
  await sim(() => window.__sim.command.reload());
  const mag0 = await sim(() => window.__sim.gun.mag);
  await tap('B');
  await page.waitForTimeout(700);
  assert.equal(await sim(() => window.__sim.gun.mag), mag0, 'FIRE without ARM does nothing');
  assert.match(await page.locator('#gamepad-pill').textContent(), /HOLD Y TO ARM/);
  await pad('button', 0, 'Y', 1);
  await until(() => window.__sim.gun.armHeld && window.__sim.gun.laserOn);
  await tap('B');
  await until((m) => window.__sim.gun.mag === m - 1, mag0);
  assert.ok((await sim(() => window.__fakePads.slots[0].vibrationActuator.effects.length)) > 0, 'A shot rumbles a pad that supports it');
  await pad('button', 0, 'RB', 1); await seen('RB', true);
  await until((m) => window.__sim.gun.queue.length > 0 || window.__sim.gun.mag < m - 1, mag0);
  await pad('button', 0, 'RB', 0);
  await pad('button', 0, 'Y', 0);
  await until(() => !window.__sim.gun.armHeld && window.__sim.gun.queue.length === 0);
  // losing focus disarms, and ARM stays off until it is let go and pressed again (hold-to-run)
  await pad('button', 0, 'Y', 1);
  await until(() => window.__sim.gun.armHeld);
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await until(() => !window.__sim.gun.armHeld);
  await page.evaluate(() => new Promise((r) => { let n = 0; const f = () => (++n > 8 ? r() : requestAnimationFrame(f)); requestAnimationFrame(f); }));
  assert.equal(await sim(() => window.__sim.gun.armHeld), false, 'Still held after blur: ARM does not come back by itself');
  await pad('button', 0, 'Y', 0); await seen('Y', false);
  await pad('button', 0, 'Y', 1);
  await until(() => window.__sim.gun.armHeld);
  await pad('button', 0, 'Y', 0);
  await until(() => !window.__sim.gun.armHeld);
  // a pad unplugged while ARM is held disarms
  await pad('button', 0, 'Y', 1);
  await until(() => window.__sim.gun.armHeld);
  await pad('disconnect', 0);
  await until(() => !window.__sim.gun.armHeld && document.getElementById('gamepad-pill').hidden);
  await pad('connect', 0);
  await until(() => !document.getElementById('gamepad-pill').hidden);

  // ---- jump: input/start and real airborne geometry retain their15s response bounds.
  // Landing follows actual clamped stage dt, with separate wall/stalled-render limits.
  const hopGuard=await page.evaluateHandle('('+checkHopProgress.toString()+')'),hopSample=await page.evaluateHandle('('+readHopSample.toString()+')');
  await sim(()=>{
    window.__hopTrace={frames:0,rows:[],started:false,simulatedS:0,maxY:0};
    window.__hopTraceOff=window.__sim.stage.onFrame((t,dt)=>{
      const s=window.__sim,r=window.__hopTrace,now=performance.now();
      if(!r.started&&s.state.jump){r.started=true;r.startedAt=now;}
      if(!r.started)return;
      r.frames++;r.simulatedS+=dt;r.lastFrameAt=now;r.maxY=Math.max(r.maxY,s.state.robot.group.position.y);
      r.rows.push({t,dt,wall:now,jump:s.state.jump?{...s.state.jump}:null,y:s.state.robot.group.position.y,paused:s.demo.on&&!s.demo.playing,demoOn:s.demo.on,playing:s.demo.playing,replay:!!s.state.replay,visibility:document.visibilityState,stageError:document.body.dataset.stageError||null});
      if(r.rows.length>512)r.rows.shift();
    });
  });
  let hopError;
  try {
    await pad('button',0,'A',1);
    await until(()=>!!window.__sim.state.jump);
    await pad('button',0,'A',0);
    await until(()=>window.__sim.state.robot.group.position.y>.12);
    await page.waitForFunction(pollHop,{guard:hopGuard,readSample:hopSample,limits:HOP_LIMITS},{timeout:HOP_LIMITS.wallMs,polling:100});
  }catch(error){hopError=error;throw error;}finally{
    await Promise.all([hopGuard.dispose(),hopSample.dispose()]);
    try{
      const trace=await sim(()=>{window.__hopTraceOff();return{modelKey:window.__sim.state.modelKey,frameTrace:window.__hopTrace,jump:window.__sim.state.jump,y:window.__sim.state.robot.group.position.y};});
      const out=process.env.TEST_OUTPUT||'/tmp/gyropup-gamepad';await mkdir(out,{recursive:true});await writeFile(`${out}/${engine.name()}-hop.json`,JSON.stringify({engine:engine.name(),browser:browser.version(),limits:HOP_LIMITS,error:hopError?String(hopError):null,...trace},null,2));
      if(hopError)console.error('Hop landing failure state:',JSON.stringify(trace));
    }catch(error){if(!hopError)throw error;console.error('Hop diagnostic unavailable:',error.message);}
  }

  // ---- Menu: the settings dialog, live diagram, actions suspended, rebind persisted, reset
  await tap('Menu');
  await until(() => document.querySelector('dialog.gpad-config')?.open);
  await pad('axes', 0, [0, -1, 0, 0]);
  await pad('button', 0, 'A', 1);
  await until(() => document.querySelector('.gpad-diagram [data-input=A]').classList.contains('on'));
  await page.waitForTimeout(200);
  assert.equal(await sim(() => window.__sim.state.speed), 0, 'Actions are suspended while the settings are open');
  assert.equal(await sim(() => window.__sim.state.jump), null);
  await pad('axes', 0, [0, 0, 0, 0]); await pad('button', 0, 'A', 0);
  await page.locator('tr[data-action=jump] .gpad-rebind').click();
  await until(() => document.querySelector('tr[data-action=jump]').classList.contains('capturing'));
  await tap('X');
  await until(() => /^X/.test(document.querySelector('tr[data-action=jump] .gpad-binding').textContent));
  assert.match(await page.locator('tr[data-action=jump] .gpad-binding').textContent(), /also Reload/, 'A clash is shown');
  const deadZone = page.locator('.gpad-config input[data-tuning=stickDeadZone]');
  await deadZone.evaluate((el) => { el.value = '0.3'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  const stored = JSON.parse(await sim(() => localStorage.getItem('gyropup.gamepad.v1')));
  assert.deepEqual(stored.bindings.jump, { button: 'X' });
  assert.equal(stored.tuning.stickDeadZone, 0.3);
  await page.keyboard.press('Escape');
  await until(() => !document.querySelector('dialog.gpad-config').open);

  // ---- persisted across a reload; reset restores the defaults
  await openSim();
  await pad('connect', 0);
  await until(() => window.__sim.gamepad.control.connected);
  assert.deepEqual(await sim(() => window.__sim.gamepad.control.bindings.get('jump')), { button: 'X' });
  await page.locator('#panel summary', { hasText: 'Gamepad' }).click();
  await page.getByRole('button', { name: 'Gamepad settings' }).click();
  await until(() => document.querySelector('dialog.gpad-config')?.open);
  await page.getByRole('button', { name: 'Reset to defaults' }).click();
  assert.deepEqual(await sim(() => window.__sim.gamepad.control.bindings.get('jump')), { button: 'A' });
  assert.equal(await sim(() => localStorage.getItem('gyropup.gamepad.v1')), null);
  // Menu on the pad closes it, and that press does not reopen it
  await pad('button', 0, 'Menu', 1);
  await until(() => !document.querySelector('dialog.gpad-config').open);
  await page.waitForTimeout(200); await pad('button', 0, 'Menu', 0); await seen('Menu', false);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(r)))));
  assert.equal(await sim(() => document.querySelector('dialog.gpad-config').open), false, 'The closing press does not reopen the dialog');

  // ---- the keyboard still works with a pad connected
  const height = page.locator('#panel .hud-slider', { hasText: 'Height' }).locator('input');
  await height.focus();
  const h0 = await sim(() => window.__sim.state.height);
  await page.keyboard.press('ArrowLeft');
  await until((h) => window.__sim.state.height < h, h0);

  // ---- the turret bench: right stick aims, ARM is held through the bench's own safety line
  await page.selectOption('#design-select', 'turret-box');
  await until(() => window.__sim.bench()?.active, null, 90000);
  const panCmd0 = await sim(() => window.__sim.bench().api.state.panCmd);
  await pad('axes', 0, [0, 0, -1, 0]);
  await until((p) => window.__sim.bench().api.state.panCmd > p + 0.2, panCmd0);
  await pad('axes', 0, [0, 0, 0, 0]);
  await pad('button', 0, 'Y', 1);
  await until(() => window.__sim.bench().api.state.arm.has('pad'));
  await pad('button', 0, 'Y', 0);
  await until(() => !window.__sim.bench().api.state.arm.has('pad'));

  // ---- the live hop's apex is the leg rig's simulated jump
  const rig = JSON.parse(await readFile(new URL('../../../hardware/exports/leg/rig-results.json', import.meta.url), 'utf8'));
  const apex = +(await readFile(new URL('../../../software/site/designer/sim.js', import.meta.url), 'utf8')).match(/apexM: ([0-9.]+)/)[1];
  assert.ok(Math.abs(apex * 1000 - rig.scenarios.jump.jump_height_mm) < 5,
    `The live hop (${apex * 1000} mm) matches the rig's jump (${rig.scenarios.jump.jump_height_mm} mm); update JUMP.apexM in designer/sim.js`);
  // From every start height the hip tops out JUMP.apexM above where it stood, and the wheels leave the ground
  // without the legs snapping (jumpPose run on its own, with the v2 leg range).
  const simSrc = await readFile(new URL('../../../software/site/designer/sim.js', import.meta.url), 'utf8');
  const jumpSrc = simSrc.match(/const JUMP = \{[^}]*\};/)[0], at = simSrc.indexOf('function jumpPose');
  let depth = 0, end = simSrc.indexOf('{', at);
  for (; end < simSrc.length; end++) { if (simSrc[end] === '{') depth++; if (simSrc[end] === '}' && --depth === 0) break; }
  const jumpPose = new Function('state', `${jumpSrc}\n${simSrc.slice(at, end + 1)}\nreturn jumpPose;`)({ robot: { info: { hMin: 150, hMax: 375 } } });
  const legM = (h) => 0.15 + 0.225 * h, dt = 1 / 2000;
  for (const from of [0, 0.2, 0.4, 0.6, 1]) {
    let top = 0, lift = 0, rate = 0, prev = null;
    for (const J = { t: 0, from }; ; J.t += dt) {
      const p = jumpPose(J); if (!p) break;
      top = Math.max(top, legM(p.height) + p.lift); lift = Math.max(lift, p.lift);
      if (prev) rate = Math.max(rate, Math.abs(legM(p.height) - legM(prev.height)) / dt);
      prev = p;
    }
    assert.ok(Math.abs((top - legM(from)) - apex) < 0.002, `hop from ${from}: hip apex ${((top - legM(from)) * 1000).toFixed(1)} mm above standing`);
    assert.ok(lift > 0.1 && rate < 3, `hop from ${from}: wheels ${(lift * 1000).toFixed(0)} mm up, legs at most ${rate.toFixed(2)} m/s`);
  }

  // ---- the kit's own demo page
  const demo = await context.newPage();
  demo.on('pageerror', (e) => errors.push(e.message));
  await demo.goto(`${base}/designer/kit/gamepad/demo.html`);
  await demo.waitForFunction(() => !!window.__gamepadDemo);
  await demo.evaluate(() => window.__fakePads.connect(1));
  await demo.waitForFunction(() => /2: Xbox/.test(document.getElementById('status').textContent));
  await demo.evaluate(() => window.__fakePads.axes(1, [0.9, 0, 0, 0]));
  await demo.waitForFunction(() => document.querySelector('#actions meter').value > 0.8);
  await demo.close();

  assert.deepEqual(errors, []);
  console.log('gamepad: hot-plug, drive/turn, aim limits, height, hold-to-ARM fire, jump, settings, rebind, persistence, keyboard, bench and demo OK');
} finally {
  await browser.close();
}
