/** Exercise real replay switches without replacing the scene, character, or player conversation. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8878').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel: 'chrome', headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : { headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, deviceScaleFactor: 1 });
const page = await context.newPage(), errors = [];
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-sim-transitions';
await mkdir(out, { recursive: true });
page.on('pageerror', error => errors.push(error.message));
await context.addInitScript(() => {
  localStorage.setItem('gyropup.probe', 'off');
  window.GYROPUP_BRAIN = { base: location.origin + '/test-brain', model: 'test-conversation' };
});
let releaseReply, requestBody;
await page.route('**/test-brain/models', route => route.fulfill({ json: { data: [{ id: 'test-conversation' }] } }));
await page.route('**/test-brain/chat/completions', async route => {
  requestBody = route.request().postDataJSON();
  await new Promise(resolve => { releaseReply = resolve; });
  await route.fulfill({ json: { choices: [{ message: { content: '[happy] I remember our foam robot adventure. Ready for the next round!' } }] } });
});
try {
  await page.goto(base + '/designer/sim.html?sound=0', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.body.dataset.ready === '1');
  await page.evaluate(() => {
    const s = window.__sim;
    window.original = { canvas: s.stage.renderer.domElement, scene: s.stage.scene, robot: s.state.robot,
      eyes: s.eyes, talk: s.talk, dock: s.talk.dock.el, target: s.props.get('target_a') };
    window.original.scales = new Map();
    s.state.robot.group.traverse(o => window.original.scales.set(o, o.scale.toArray()));
    s.talk.ask('Remember our foam robot adventure?', { speak: false });
  });
  await page.waitForFunction(() => document.querySelector('.gp-bubble').classList.contains('thinking'));
  // Changing activities while a reply is in flight must not replace its thinking bubble or abort it.
  await page.screenshot({ path: `${out}/${engine.name()}-before-stage.png` });
  await page.selectOption('#run-select', 'v2/drive');
  await page.waitForFunction(() => window.__sim.state.replay?.key === 'v2/drive');
  assert.equal(await page.evaluate(() => window.__sim.state.transition !== null), true);
  await page.waitForFunction(() => window.__sim.state.transition === null);
  assert.equal(await page.locator('.gp-bubble').evaluate(el => el.classList.contains('thinking')), true);
  await page.screenshot({ path: `${out}/${engine.name()}-after-stage.png` });
  assert.equal(await page.evaluate(() => window.original.target.visible), false, 'Pooled targets are hidden outside their activity');
  assert.ok(releaseReply, 'Mock conversation request reached the brain');
  releaseReply();
  await page.waitForFunction(() => window.__sim.talk.conversation.length === 2);
  assert.equal(requestBody.messages.at(-1).content, 'Remember our foam robot adventure?');
  await page.waitForFunction(() => !document.querySelector('.gp-bubble').classList.contains('typing'));
  const reply = await page.locator('.gp-text').textContent();
  await page.selectOption('#run-select', 'v2/targets');
  await page.waitForFunction(() => window.__sim.state.replay?.key === 'v2/targets' && !window.__sim.state.transition);
  assert.equal(await page.locator('.gp-text').textContent(), reply, 'Activity hint must not interrupt the answer');
  assert.ok(await page.evaluate(() => {
    const s = window.__sim, o = window.original;
    return s.stage.renderer.domElement === o.canvas && s.stage.scene === o.scene && s.state.robot === o.robot &&
      s.eyes === o.eyes && s.talk === o.talk && s.talk.dock.el === o.dock && s.props.get('target_a') === o.target;
  }), 'Same scene, renderer, character and target mesh after switching away and back');
  const scales = await page.evaluate(() => {
    window.__sim.state.robot.turret?.step(10);
    return [...window.original.scales].filter(([o, scale]) => o.scale.toArray().some((v, i) => Math.abs(v-scale[i]) > 1e-6)).map(([o]) => o.name || o.type);
  });
  assert.deepEqual(scales, [], 'Model descendants must not shrink during transitions');
  // Wrap from the end of a recording: first frame must blend, not teleport or greet again.
  await page.evaluate(() => {
    window.motion = [];
    const s = window.__sim;
    s.stage.onFrame(() => { if(s.state.transition) window.motion.push({ p: s.state.robot.base.getWorldPosition(s.state.robot.base.position.clone()).toArray(), camera: s.stage.camera.position.toArray() }); });
    const R = s.state.replay; R.t = R.run.frames.qpos.length / R.run.frames.fps - .002; R.playing = true; });
  await page.waitForFunction(() => window.__sim.state.transition !== null);
  await page.waitForFunction(() => window.__sim.state.transition === null);
  assert.equal(await page.locator('.gp-text').textContent(), reply);
  assert.equal(await page.evaluate(() => window.__sim.talk.conversation.length), 2);
  const motion = await page.evaluate(() => window.motion);
  assert.ok(motion.length > 5, 'Transition renders intermediate frames');
  for(let i=1;i<motion.length;i++) assert.ok(Math.hypot(...motion[i].p.map((v,k)=>v-motion[i-1].p[k])) < .15, 'Robot moves continuously through the loop');
  await page.screenshot({ path: `${out}/${engine.name()}-after-loop.png` });
  // A slower earlier fetch must never override a newer choice; loading leaves the old replay alive.
  let releaseRun;
  await page.route('**/exports/sim/v2/squat.json', async route => { await new Promise(resolve => { releaseRun = resolve; }); await route.continue(); });
  await page.selectOption('#run-select', 'v2/squat');
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => window.__sim.state.replay.key), 'v2/targets');
  await page.selectOption('#run-select', 'v2/drive');
  await page.waitForFunction(() => window.__sim.state.replay?.key === 'v2/drive');
  assert.ok(releaseRun); releaseRun();
  await page.waitForTimeout(200);
  assert.equal(await page.evaluate(() => window.__sim.state.replay.key), 'v2/drive');
  await page.selectOption('#run-select', '');
  await page.waitForFunction(() => !window.__sim.state.replay && !window.__sim.state.transition);
  // Hardware changes reuse previously loaded robot views and keep the same conversation.
  await page.selectOption('#design-select', 'designs/default.json');
  await page.waitForFunction(() => window.__sim.state.modelKey === 'designs/default.json');
  await page.selectOption('#design-select', 'v2');
  await page.waitForFunction(() => window.__sim.state.modelKey === 'v2' && !window.__sim.state.transition);
  assert.ok(await page.evaluate(() => window.__sim.state.robot === window.original.robot && window.__sim.talk === window.original.talk));
  for (const [width, height] of [[320,568], [375,667], [390,844], [430,932], [568,320], [667,375], [844,390], [932,430]]) {
    await page.setViewportSize({ width, height });
    if (width < 900) {
      const handle = page.locator('#drawer-handle');
      if (await handle.getAttribute('aria-expanded') !== 'true') await handle.click();
    }
    await page.locator('.hud-slider').first().scrollIntoViewIfNeeded();
    const metric = await page.locator('.hud-slider').first().evaluate(label => {
      const input = label.querySelector('input'), row = label.querySelector('.row');
      const a = input.getBoundingClientRect(), b = row.getBoundingClientRect();
      return { width: a.width, height: a.height, below: a.top >= b.bottom - 1, overflow: document.documentElement.scrollWidth > innerWidth + 1,
        track: getComputedStyle(input, '::-webkit-slider-runnable-track').backgroundColor };
    });
    assert.ok(metric.width > 160 && metric.height >= 40 && metric.below && !metric.overflow, JSON.stringify({width,height,metric}));
    await page.locator('.hud-slider input').first().fill('0.25');
    assert.equal(await page.evaluate(() => window.__sim.state.height), .25);
    if (width === 390) await page.screenshot({ path: `${out}/${engine.name()}-phone-sliders.png` });
  }
  await page.selectOption('#design-select', 'turret-box');
  await page.waitForFunction(() => window.__sim.state.bench);
  const resetStart = await page.evaluate(() => {
    const api = window.__sim.bench().api, targets = api.targets;
    window.benchTargets = targets;
    targets.plates[0].th = 1; targets.plates[0].hinge.rotation.x = -1;
    targets.cans[0].m.position.x += .4;
    const before = targets.cans[0].m.position.x;
    api.resetTargets();
    return { before, after: targets.cans[0].m.position.x, angle: targets.plates[0].th };
  });
  assert.equal(resetStart.before, resetStart.after, 'Reset starts without a can teleport');
  assert.equal(resetStart.angle, 1, 'Reset starts without a plate teleport');
  await page.waitForFunction(() => !window.__sim.bench().api.targets.resetting);
  assert.ok(await page.evaluate(() => {
    const s = window.__sim, targets = s.bench().api.targets;
    return targets.cans === window.benchTargets.cans && targets.plates === window.benchTargets.plates &&
      targets.cans.every(c => c.m.position.distanceTo(c.home) < .001) && s.talk === window.original.talk &&
      s.talk.conversation.length === 2 && s.stage.scene === window.original.scene;
  }), 'Targets return home in the same scene and conversation');
  assert.equal(await page.evaluate(() => document.body.dataset.stageError), undefined);
  assert.deepEqual(errors, []);
  console.log(`PASS ${engine.name()}: scene/robot/target identity, pending reply and history, loop blending, latest replay selection, cached hardware views, target re-rack, 8 slider layouts. Screenshots ${out}`);
} finally { releaseReply?.(); await browser.close(); }
