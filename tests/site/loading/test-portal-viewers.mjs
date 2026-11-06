import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
/** Public CAD/FEA/character routes must have a useful entry point and reachable phone controls. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : { headless: true });
const context = await browser.newContext({ viewport: { width: 320, height: 568 } });
await acknowledgePrototypeNotice(context);
await context.addInitScript(() => { localStorage.setItem('gyropup.probe', 'off'); localStorage.setItem('gyropup-sfx', '0'); });
const page = await context.newPage(), errors = [], missing = [], results = [];
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-portal-viewers';
await mkdir(out, { recursive: true });
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => { if (response.status() >= 400 && response.url().startsWith(base) && !response.url().includes('/_cadagent/')) missing.push(response.url()); });
const portrait = [[320, 568], [360, 640], [375, 667], [390, 844], [393, 852], [412, 915], [414, 896], [430, 932], [480, 960]];
const sizes = [...portrait, ...portrait.map(([w, h]) => [h, w]), [768, 1024], [1024, 768], [1440, 900]];
async function settle() { await page.waitForTimeout(800); }
async function visibleModel(key, minimumHeight = 35, targetPage = page) {
  const bounds = await targetPage.evaluate(async key => {
    const THREE = await import('/designer/kit/vendor/three/three.module.min.js');
    const s = window[key].stage, canvas = s.renderer.domElement.getBoundingClientRect();
    s.root.updateMatrixWorld(true); s.camera.updateMatrixWorld(true);
    const points = [], v = new THREE.Vector3();
    s.root.traverseVisible(o => {
      if (!o.isMesh || !o.geometry.attributes.position) return;
      const p = o.geometry.attributes.position;
      for (let i = 0; i < p.count; i += Math.max(1, Math.floor(p.count / 2000))) {
        v.fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld).project(s.camera);
        points.push({ x: canvas.left + (v.x + 1) * canvas.width / 2, y: canvas.top + (1 - v.y) * canvas.height / 2 });
      }
    });
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const top = document.querySelector('#topbar').getBoundingClientRect().bottom;
    const status = document.querySelector('.fea-status'), legend = document.querySelector('.fea-legend');
    const dock = document.querySelector('.gp-dock');
    const min=values=>values.reduce((a,b)=>Math.min(a,b),Infinity),max=values=>values.reduce((a,b)=>Math.max(a,b),-Infinity);
    return { x: min(xs), right: max(xs), y: min(ys), bottom: max(ys),
      freeTop: status?.offsetParent ? Math.max(top, status.getBoundingClientRect().bottom) : top,
      freeBottom: legend?.offsetParent ? legend.getBoundingClientRect().top : dock ? dock.getBoundingClientRect().top : innerHeight,
      width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth,
      obstacles: [...document.querySelectorAll('#topbar, #panel, .fea-status, .fea-legend, .gp-dock, .gp-bubble:not(.hidden):not(.off-stage)')].filter(el => el.getClientRects().length && getComputedStyle(el).visibility!=='hidden' && getComputedStyle(el).opacity!=='0').map(el => {
        const r = el.getBoundingClientRect(); return { name: el.className || el.id, x: r.left, right: r.right, y: r.top, bottom: r.bottom };
      }) };
  }, key);
  assert.ok(bounds.scrollWidth <= bounds.width + 1, 'No horizontal page overflow');
  assert.ok(bounds.bottom - bounds.y >= minimumHeight, `Model has a useful visible size: ${JSON.stringify(bounds)}`);
  for (const obstacle of bounds.obstacles) {
    const overlapX = Math.min(bounds.right, obstacle.right) - Math.max(bounds.x, obstacle.x);
    const overlapY = Math.min(bounds.bottom, obstacle.bottom) - Math.max(bounds.y, obstacle.y);
    assert.ok(overlapX <= 4 || overlapY <= 4, `Model stays clear of ${obstacle.name}: ${JSON.stringify(bounds)}`);
  }
  assert.ok(bounds.x >= -4 && bounds.right <= bounds.width + 4, `Model stays on screen: ${JSON.stringify(bounds)}`);
  return bounds;
}
async function wheel(key) {
  const before = await page.evaluate(key => {
    const s = window[key].stage, d = s.camera.position.distanceTo(s.controls.target);
    s.renderer.domElement.dispatchEvent(new WheelEvent('wheel', { deltaY: 120, bubbles: true, cancelable: true }));
    return { d, immediate: s.camera.position.distanceTo(s.controls.target) };
  }, key);
  assert.equal(before.d, before.immediate, 'Wheel changes ease in without an immediate jump');
  await page.waitForFunction(({ key, d }) => window[key].stage.camera.position.distanceTo(window[key].stage.controls.target) > d * 1.01, { key, d: before.d });
  await page.waitForTimeout(700);
  const after = await page.evaluate(key => window[key].stage.camera.position.distanceTo(window[key].stage.controls.target), key);
  const ratio = after / before.d;
  assert.ok(ratio > 1.01 && ratio < 1.02, `Fine wheel step: ${ratio}`);
  return ratio;
}
try {
  await page.goto(`${base}/designer/kit/viewer.html`, { waitUntil: 'networkidle' });
  await page.waitForURL(url=>/\/designer\/sim(?:\.html)?$/.test(url.pathname)&&url.searchParams.get('run')==='none');
  await page.waitForFunction(() => window.__sim && document.body.dataset.ready === '1');
  assert.ok(!missing.some(u => u.includes('/exports/view/')), 'Default viewer never requests an absent export');
  results.push({ route: 'default CAD viewer', destination: '/designer/sim.html?run=none' });

  // Exercise the reusable viewer with a genuine published STL; only its small manifest is a test fixture.
  const manifest = await (await context.request.get(`${base}/exports/sim/turret_box/manifest.json`)).json();
  const part = manifest.parts.find(p => p.name === 'pan_base');
  await page.route('**/__portal_audit__/view.json', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ title: 'Published pan base',
    parts: [{ name: part.name, file: `${base}/exports/sim/turret_box/${part.file}`, color: part.color, bounds_mm: part.bbox }] }) }));
  await page.goto(`${base}/designer/kit/viewer.html?manifest=/__portal_audit__/view.json&explode=0.4&section=0.7`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__viewer);
  assert.equal(await page.locator('input[type=range]').nth(0).inputValue(), '0.4');
  assert.equal(await page.locator('input[type=range]').nth(1).inputValue(), '0.7');
  await page.locator('#panel input[type=checkbox]').first().uncheck();
  assert.equal(await page.evaluate(() => window.__viewer.parts[0].mesh.visible), false);
  assert.match(await page.locator('.hud-readouts').innerText(), /parts shown\s+0/);
  await page.locator('#panel input[type=checkbox]').first().check();
  assert.match(await page.locator('.hud-readouts').innerText(), /parts shown\s+1/);
  results.push({ route: 'explicit CAD manifest', wheelRatio: await wheel('__viewer'), parts: 1 });

  await page.goto(`${base}/designer/kit/fea.html`, { waitUntil: 'networkidle' });
  assert.ok(await page.getByRole('link', { name: 'Latest structural reports', exact: true }).isVisible());
  assert.ok(await page.getByRole('link', { name: 'Explore the earlier thigh study in 3D', exact: true }).isVisible());
  assert.match(await (await context.request.get(`${base}/designer/kit/fea.md`)).text(), /Latest structural reports/);
  assert.match(await (await context.request.get(`${base}/designer/kit/viewer.md`)).text(), /playground/);
  await page.goto(`${base}/designer/kit/fea.html?case=../../exports/fea/thigh-T1.json`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__fea);
  assert.ok(await page.getByRole('button', { name: 'SHOW PANEL', exact: true }).isVisible(), 'Phone FEA opens with the model visible');
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height }); await settle();
    results.push({ route: 'FEA', width, height, bounds: await visibleModel('__fea') });
  }
  await page.setViewportSize({ width: 320, height: 568 }); await settle();
  await page.screenshot({ path: `${out}/fea-phone.png` });
  await page.getByRole('button', { name: 'SHOW PANEL', exact: true }).click();
  await page.locator('[data-a=max]').click();
  assert.notEqual(await page.locator('.hud-slider').first().locator('input').inputValue(), '1');
  await page.locator('[data-a=design]').click();
  assert.equal(await page.locator('.hud-slider').first().locator('input').inputValue(), '1');
  await page.locator('[data-a=play]').click();
  await page.waitForFunction(() => document.querySelector('[data-a=play]').textContent.toUpperCase().includes('PAUSE'));
  await page.locator('[data-a=play]').click();
  for (const field of ['ratio', 'stress', 'sf', 'disp']) {
    await page.locator(`[data-f=${field}]`).click();
    assert.match(await page.locator(`[data-f=${field}]`).getAttribute('class'), /\bon\b/);
  }
  await page.getByRole('button', { name: 'HIDE PANEL', exact: true }).click(); await settle();
  await visibleModel('__fea');
  results.push({ route: 'FEA controls', wheelRatio: await wheel('__fea') });

  await page.goto(`${base}/designer/character/talk-demo.html`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__talkDemo);
  await page.evaluate(() => window.__talk.dock.collapse(false));
  await page.waitForFunction(()=>{const b=document.querySelector('.gp-bubble');return b?.textContent.includes('target game')&&!b.classList.contains('typing');});
  for (const [width, height] of [[320, 568], [390, 844], [568, 320], [844, 390], [1440, 900]]) {
    await page.setViewportSize({ width, height }); await settle();
    results.push({ route: 'Talk demo', width, height, bounds: await visibleModel('__talkDemo') });
    if(width===568)await page.screenshot({path:`${out}/talk-landscape.png`});
  }
  await page.setViewportSize({ width: 320, height: 568 }); await settle();
  await page.screenshot({ path: `${out}/talk-phone.png` });
  await page.getByRole('button', { name: 'SHOW PANEL', exact: true }).click();
  await page.getByRole('button', { name: 'curious', exact: true }).click();
  assert.equal(await page.evaluate(() => document.body.dataset.mood), 'curious');
  assert.equal(await page.evaluate(() => window.__talk.dock.isCollapsed()), true, 'Event controls leave room for the model');
  await page.getByRole('button', { name: 'Talk', exact: true }).click();
  await page.waitForFunction(() => window.__talkDemo.controlsPanel.collapsed());
  await page.getByRole('textbox', { name: 'Message to Gyropup' }).fill('Hello!');
  await page.getByTitle('Ask Gyropup', { exact: true }).click();
  await page.waitForFunction(() => window.__talk.conversation.some(m => m.role === 'assistant'));
  results.push({ route: 'Talk controls and conversation', wheelRatio: await wheel('__talkDemo') });
  // Start wide landscape with fresh storage: resizing from a portrait page can
  // accidentally preserve its collapsed panel and hide a real startup problem.
  const freshContext=await browser.newContext({viewport:{width:844,height:390},reducedMotion:'reduce'});
await acknowledgePrototypeNotice(freshContext);
  await freshContext.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');});
  const fresh=await freshContext.newPage();fresh.on('pageerror',e=>errors.push(e.message));
  await fresh.goto(`${base}/designer/character/talk-demo.html`,{waitUntil:'networkidle'});
  await fresh.waitForFunction(()=>window.__talkDemo);
  await fresh.waitForFunction(()=>{const b=document.querySelector('.gp-bubble');return b?.textContent.includes('target game')&&!b.classList.contains('typing');});
  assert.ok(await fresh.evaluate(()=>window.__talkDemo.controlsPanel.collapsed()),'Fresh short landscape opens with model space');
  const freshBounds=await visibleModel('__talkDemo',100,fresh);
  assert.ok(freshBounds.right-freshBounds.x>=60,'Fresh landscape model is not squeezed into a thumbnail by the desktop panel');
  await fresh.screenshot({path:`${out}/talk-fresh-landscape.png`});
  await fresh.getByRole('button',{name:'SHOW PANEL',exact:true}).click();
  await fresh.waitForFunction(()=>window.__talk.dock.isCollapsed());
  await fresh.getByRole('button',{name:'Talk',exact:true}).click();
  await fresh.waitForFunction(()=>window.__talkDemo.controlsPanel.collapsed());
  await fresh.waitForTimeout(800);
  await visibleModel('__talkDemo',100,fresh);
  results.push({route:'Fresh talk landscape',width:844,height:390,bounds:freshBounds});await freshContext.close();
  assert.deepEqual(errors, [], 'No browser exceptions');
  assert.deepEqual(missing, [], 'No missing published assets');
  await writeFile(`${out}/report.json`, JSON.stringify({ checkedAt: new Date().toISOString(), base, results, errors, missing }, null, 2));
  console.log(`PASS portal viewers: default/explicit CAD, ${sizes.length} FEA sizes, 5 talk sizes, controls, conversation, fine wheel zoom. ${base}`);
} finally { await browser.close(); }
