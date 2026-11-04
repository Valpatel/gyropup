/** The RS-04 motor tool (designer/motor-tool.html) in a real browser: on the built site with its software motors, and
 * served by the SocketCAN bridge (rig/rs04_bridge.py) on software motors. Covers the brief's safety requirements:
 * the hardware/emulator banner, the always-visible STOP on Space/Esc, no enable without the arm step, writes held to the
 * profile's cap, and a closed tab stopping the motors.
 *
 *   npm run build && npm run test:motor-tool              # serves dist/ on a test-owned listener
 *   SITE_URL=http://127.0.0.1:8879 npm run test:motor-tool
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';

const root = path.resolve(import.meta.dirname, '..');
const out = process.env.TEST_OUTPUT || path.join(root, 'test-results', 'motor-tool');
await mkdir(out, { recursive: true });
let server, base = process.env.SITE_URL?.replace(/\/$/, '');
if (!base) {
  server = createSiteServer(path.join(root, 'dist'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
}
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true });
const errors = [];
const t = (name) => `[data-test="${name}"]`;
const logText = (page) => page.locator(t('log')).innerText();
const waitLog = (page, re, timeout = 8000) => page.waitForFunction((src) => new RegExp(src).test(document.querySelector('[data-test="log"]').innerText), re.source, { timeout });
const emuMotor = (page, i = 0) => page.evaluate((i) => { const m = window.gyropupMotorTool.client.transport.bus.motors[i]; return { id: m.id, mode: m.mode, params: { ...m.params }, saved: { ...m.saved }, angle: m.angle }; }, i);
async function confirm(page, re) {
  const dlg = page.locator(t('confirm'));
  await dlg.waitFor();
  if (re) assert.match(await dlg.innerText(), re);
  await dlg.locator(t('ok')).click();
}
async function stopVisible(page) {
  const box = await page.locator(t('stop')).boundingBox(), vp = page.viewportSize();
  assert.ok(box && box.y >= 0 && box.y + box.height <= vp.height && box.x + box.width <= vp.width, `STOP is on screen: ${JSON.stringify(box)}`);
}

try {
  // ------------------------------------------------------------------ the site page, software motors
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 }, acceptDownloads: true });
  await acknowledgePrototypeNotice(context);
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + '/designer/motor-tool.html');
  await page.waitForFunction(() => document.body.dataset.ready === '1');
  const options = await page.locator(`${t('transport')} option`).evaluateAll(os => os.map(o => o.value));
  assert.ok(!options.includes('bridge'), `the site page offers no bridge: ${options}`);
  assert.ok(options.includes('emu1') && options.includes('emu4'));
  assert.equal(await page.locator(t('profile')).inputValue(), 'pla-bench', 'the PLA bench profile is the default');
  assert.match(await page.locator(t('limits')).innerText(), /cap 12 N m · jog 3 N m, 1 rad\/s/);
  await stopVisible(page);

  await page.selectOption(t('transport'), 'emu1');
  await page.click(t('connect'));
  await page.waitForFunction(() => document.querySelector('.rs04-conn').dataset.kind === 'emulator');
  assert.match(await page.locator('.rs04-conn').innerText(), /EMULATOR.*nothing real moves/);
  await waitLog(page, /scan: id 127 \(uid [0-9a-f]{16}\)/);
  assert.match(await page.locator(t('motors')).innerText(), /CAN id 127[\s\S]*firmware 0\.4\.1\.24/);

  // parameters: a write inside the cap is volatile until Save; one over the cap never reaches the motor
  await page.click('[data-tab="parameters"]');
  await page.waitForFunction(() => document.querySelector('tr[data-param="limit_torque"] .rs04-val').textContent === '120');
  await page.fill('input[data-param="limit_torque"]', '13');
  await page.click('button[data-write="limit_torque"]');
  await waitLog(page, /refused, limit_torque 13 N m is over the profile's cap 12 N m/);
  assert.equal((await emuMotor(page)).params.limit_torque, 120, 'the refused write did not reach the motor');
  await page.fill('input[data-param="limit_torque"]', '10');
  await page.click('button[data-write="limit_torque"]');
  await waitLog(page, /motor 127: limit_torque = 10 \(volatile until Save\)/);
  assert.match(await page.locator(t('unsaved')).innerText(), /Unsaved writes on motor 127: limit_torque/);
  await page.fill('input[data-param="canTimeout"]', '0');
  await page.click('button[data-write="canTimeout"]');
  await waitLog(page, /refused, canTimeout 0 would turn the watchdog off/);
  await page.click(t('save'));
  await confirm(page, /kept over a power cycle/);
  await waitLog(page, /motor 127: saved/);
  assert.equal((await emuMotor(page)).saved.limit_torque, 10);

  // setid to a joint, then the profile's settings and the zero at a named pose
  await page.click('[data-tab="setup"]');
  await page.selectOption(t('joint'), '1');
  await page.click(t('setid'));
  await confirm(page, /becomes CAN id 1: Left leg, front hip/);
  await waitLog(page, /motor 127 is now CAN id 1 \(Left leg, front hip\)/);
  assert.equal((await emuMotor(page)).id, 1);
  await page.click(t('apply-profile'));
  await waitLog(page, /motor 1: pla-bench settings written and read back/);
  assert.deepEqual(Object.fromEntries(Object.entries((await emuMotor(page)).params).filter(([k]) => ['run_mode', 'limit_torque', 'canTimeout', 'zero_sta', 'damper'].includes(k))),
    { run_mode: 0, limit_torque: 10, canTimeout: 2000, zero_sta: 1, damper: 0 });
  await page.selectOption(t('pose'), 'knee-out-bare');
  await page.click(t('zero'));
  await confirm(page, /Upper link on its bare knee-out stop post[\s\S]*TPU sleeve is not on yet[\s\S]*rig\/calibrate\.py/);
  await waitLog(page, /zero set at "Upper link on its bare knee-out stop post"/);

  // the arm step: nothing enables without it, then a limited jog, then Space stops everything
  await page.click('[data-tab="jog"]');
  await page.click(t('arm'));
  await waitLog(page, /tick both checks before arming/);
  assert.equal((await emuMotor(page)).mode, 0, 'not enabled without the arm step');
  await page.check(t('check-0'));
  await page.check(t('check-1'));
  // STOP while the arm step's read-backs are in flight cancels it: the motor never enables
  const race = await page.evaluate(async () => {
    document.querySelector('[data-test="arm"]').click();
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true }));
    await new Promise(r => setTimeout(r, 1000));
    const tool = window.gyropupMotorTool;
    return { armed: tool.armed, mode: tool.client.transport.bus.motors[0].mode };
  });
  assert.deepEqual(race, { armed: [], mode: 0 }, 'STOP during the arm step leaves the motor disabled');
  await waitLog(page, /motor 1 not armed: STOP came first/);
  await page.click(t('arm'));
  await page.waitForFunction(() => document.querySelector('[data-test="jog-state"]').dataset.armed === 'true');
  const armed = await emuMotor(page);
  assert.equal(armed.mode, 2);
  assert.equal(armed.params.limit_torque, 3, 'armed at the jog torque');
  assert.equal(armed.params.canTimeout, 2000, 'armed with the watchdog on');
  const plus = page.locator(t('jog-plus'));
  const b = await plus.boundingBox();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(600);
  await page.mouse.up();
  await page.waitForTimeout(300);
  const moved = await emuMotor(page);
  assert.ok(moved.angle > 0.2 && moved.angle < 1.2, `the jog moved the motor at about 1 rad/s for 0.6 s: ${moved.angle}`);
  await page.screenshot({ path: path.join(out, 'armed.png') });
  await stopVisible(page);
  await page.locator('body').press('Space');
  await waitLog(page, /STOP \(Space\): stop sent to motors 1, 127/);
  assert.equal((await emuMotor(page)).mode, 0, 'Space stopped the motor');
  assert.equal(await page.locator(t('jog-state')).getAttribute('data-armed'), 'false');
  // after STOP the motor is disarmed again: an enable straight away is refused
  const refused = await page.evaluate(() => window.gyropupMotorTool.client.enable(1).then(() => 'sent', e => e.code));
  assert.equal(refused, 'not-armed');

  // config: export, edit, compare
  await page.click('[data-tab="config"]');
  const dl = page.waitForEvent('download');
  await page.click(t('export'));
  const file = await (await dl).path();
  const cfg = JSON.parse(await readFile(file, 'utf8'));
  assert.equal(cfg.schema, 'rs04-motor-config/1');
  assert.equal(cfg.can_id, 1); assert.equal(cfg.joint, 'left-front'); assert.equal(cfg.firmware, '0.4.1.24');
  assert.match(cfg.uid, /^[0-9a-f]{16}$/);
  assert.equal(cfg.params.limit_torque, 3, 'the jog torque is still in the motor (volatile)');
  assert.ok(cfg.unsaved.includes('zero'));
  assert.equal(cfg.zero.pose, 'Upper link on its bare knee-out stop post', 'the export names the zero pose (the inventory records it)');
  assert.equal(await page.locator(`${t('diff')} tr[data-param="limit_torque"]`).getAttribute('data-same'), 'false', 'the profile diff flags the jog torque');
  cfg.params.damper = 1;
  await page.fill(t('import-text'), JSON.stringify(cfg));
  await page.click(t('import'));
  await page.waitForFunction(() => document.querySelector('[data-test="diff"] tr[data-param="damper"]')?.dataset.same === 'false');
  assert.equal(await page.locator(`${t('diff')} tr[data-param="zero_sta"]`).getAttribute('data-same'), 'true');

  // Esc works too, from anywhere
  await page.keyboard.press('Escape');
  await waitLog(page, /STOP \(Esc\)/);
  await page.screenshot({ path: path.join(out, 'site-emulator.png'), fullPage: true });
  await context.close();

  // ------------------------------------------------------------------ served by the bridge (software motors)
  const bridge = spawn('python3', ['-m', 'rig.rs04_bridge', '--iface', 'emu', '--emu-ids', '127', '--port', '0'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  let blog = '';
  bridge.stdout.on('data', d => { blog += d; });
  bridge.stderr.on('data', d => { blog += d; });
  try {
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`the bridge did not start: ${blog}`)), 10000);
      const check = () => { const m = /open (http:\/\/127\.0\.0\.1:\d+\/)/.exec(blog); if (m) { clearTimeout(timer); resolve(m[1]); } };
      bridge.stdout.on('data', check);
    });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const p = await ctx.newPage();
    p.on('pageerror', e => errors.push(e.message));
    await p.goto(url);
    await p.waitForFunction(() => document.body.dataset.ready === '1');
    assert.equal(await p.locator(t('transport')).inputValue(), 'bridge', 'served by the bridge, the bridge is the default');
    await p.click(t('connect'));
    await waitLog(p, /scan: id 127/);
    assert.match(await p.locator('.rs04-conn').innerText(), /EMULATOR · bridge emu \(its software motors\)/);
    await p.click('[data-tab="parameters"]');
    await p.fill('input[data-param="limit_torque"]', '50');
    await p.click('button[data-write="limit_torque"]');
    await waitLog(p, /refused, limit_torque 50 N m is over the profile's cap 12 N m/);
    // a second tab is refused while this one holds the bridge
    const p2 = await ctx.newPage();
    await p2.goto(url);
    await p2.waitForFunction(() => document.body.dataset.ready === '1');
    await p2.click(t('connect'));
    await waitLog(p2, /could not connect/);
    await p2.close();
    await p.close();                                       // the tab closes: the bridge sends a stop to every motor seen
    for (let i = 0; i < 50 && !/STOP all \(the tab closed\): motors \[127\]/.test(blog); i++) await new Promise(r => setTimeout(r, 100));
    assert.match(blog, /STOP all \(the tab closed\): motors \[127\]/);
    await ctx.close();
  } finally { bridge.kill(); }

  assert.deepEqual(errors, [], 'no page errors');
  console.log('motor tool: site emulator and bridge flows pass');
} finally {
  await browser.close();
  server?.close();
}
