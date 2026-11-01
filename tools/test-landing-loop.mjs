/** The landing page's cad-agent loop section: its numbers against the committed records, its live line, and its layout.
 * Evidence checks read the repository. Browser checks use SITE_URL, or serve dist/ (run `npm run build` first) on a
 * test-owned listener that is closed in teardown. Requests to cad-agent.gyropup.com are always intercepted. */
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { parseHTML } from 'linkedom';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { describe as describeLive, SOURCE } from '../web/cad-agent-live.js';

const root = path.resolve(import.meta.dirname, '..');
const read = file => readFile(path.join(root, file), 'utf8');
const json = async file => JSON.parse(await read(file));
const source = await read('index.html');
const { document } = parseHTML(source);
const loop = document.querySelector('#loop');
const text = el => el.textContent.replace(/\s+/g, ' ').trim();
const card = tag => [...loop.querySelectorAll('.loop-card')].find(c => text(c.querySelector('.loop-tag')).startsWith(tag));
const LIVE = { revision: '9eb33cff57ceb424e1628dc123da9cb9f7af7cb3', built: '2026-11-01T08:27:46-08:00', pages: 64, items: 179 };

test('the section sits right after the hero and its ticker, and links to cad-agent without script', () => {
  assert.ok(loop, '#loop exists');
  assert.ok(loop.previousElementSibling.classList.contains('ticker'));
  assert.equal(loop.previousElementSibling.previousElementSibling.className.split(' ')[0], 'hero');
  const cta = loop.querySelector('a.loop-cta');
  assert.equal(cta.getAttribute('href'), 'https://cad-agent.gyropup.com');
  assert.match(text(cta), /^Explore cad-agent/);
  assert.equal(loop.getAttribute('aria-labelledby'), 'loop-title');
  assert.equal(loop.querySelector('.loop-live').dataset.state, 'static');
  assert.equal(loop.querySelectorAll('.loop-steps > li').length, 4);
  // linkedom, like browsers, drops a stray end tag; the source itself must not have one.
  assert.doesNotMatch(source, /<\/a>\s*<\/a>/);
});

test('FEA card: the v0.6.0 re-run counts and toolkit come from research/fea-v060-29', async () => {
  const comparison = await json('research/fea-v060-29/comparison.json');
  const runs = (await json('research/fea-v060-29/evidence/record-runs-provenance.json')).runs;
  const { before, after: afterCount, studies } = comparison.counts.below_target;
  const fea = card('FEA RE-RUN');
  const bars = [...fea.querySelectorAll('.loop-bar')].map(b => Number(b.getAttribute('style').match(/--n:(\d+)/)[1]));
  assert.deepEqual(bars, [before, afterCount]);
  assert.deepEqual([...fea.querySelectorAll('.loop-bars b')].map(text), [String(before), String(afterCount)]);
  assert.match(text(fea.querySelector('.loop-bars small')), new RegExp(`^of ${studies} `));
  assert.match(await read('web/landing.css'), new RegExp(`calc\\(var\\(--n\\) / ${studies} \\* 100%\\)`));
  // The drawing is hidden from assistive technology and Markdown; one sentence carries the same numbers.
  assert.equal(fea.querySelector('.loop-bars').getAttribute('aria-hidden'), 'true');
  assert.equal(text(fea.querySelector('.loop-bars').previousElementSibling),
    `Studies below their own target: ${before} of ${studies} on cad-agent v0.4.2’s material data, ${afterCount} of ${studies} after the re-run on v0.6.0.`);
  assert.equal(comparison.toolkit.before.split(' ')[1], text(fea.querySelectorAll('.loop-bars > span:not(.loop-bar)')[0]));
  assert.equal(comparison.toolkit.after, 'cad-agent v0.6.0 (50d4921)');
  for (const run of [runs.l1, runs.t1]) {
    assert.equal(run.toolkit.tag, 'v0.6.0');
    assert.ok(run.toolkit.commit.startsWith('50d4921'));
  }
  assert.match(text(fea), /Run record: v0\.6\.0, 50d4921/);
  assert.match(text(fea), /cad-agent v0\.6\.0 brought/);
});

test('gates card: every turret gate verdict matches exports/gates', async () => {
  const files = { fasteners: 'fasteners', 'ball path': 'turret-path', 'ammo range': 'turret-ammo', motion: 'motion',
    containment: 'containment', connectivity: 'connectivity', assembly: 'assembly', wall: 'wall', 'dossier lint': 'dossier-lint' };
  const gates = card('TURRET GATES');
  const pills = [...gates.querySelectorAll('.loop-gates li')];
  // Every verdict file is on the card: a new gate cannot leave "9 gates" stale.
  const records = (await readdir(path.join(root, 'exports/gates'))).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5)).sort();
  assert.deepEqual(Object.values(files).sort(), records);
  assert.equal(pills.length, records.length);
  let pass = 0;
  for (const pill of pills) {
    const name = text(pill).replace(/^[✓!✕]/, '').replace(/\s*\(.*\)$/, '');
    const record = await json(`exports/gates/${files[name]}.json`);
    assert.equal(pill.dataset.status, record.status, name);
    assert.equal(record.physical_fit_verified, false, name);
    if (record.pass) pass++;
  }
  assert.equal(text(gates.querySelector('h3')), `${pills.length} gates: ${pass} pass, ${pills.length - pass} to fix`);
  const motion = await json('exports/gates/motion.json');
  const poses = motion.checks.find(c => c.status === 'pass' && c.evidence?.poses).evidence.poses;
  assert.match(text(gates), new RegExp(poses.toLocaleString('en-US') + ' poses'));
  // The verdict files carry no date: the run date is the one docs/turret-sections.md records for them.
  const sections = await read('docs/turret-sections.md');
  assert.match(sections, /\*\*Results \(run 3, [^)]*2026-10-28/);
  assert.match(text(gates), /RUN OF 28 OCT 2026/);
  assert.match(sections, /run 2 found the flap's knuckle on the lid at 51\.1 deg/);
  assert.match(text(gates), /hinge hitting its lid at 51\.1°; it was fixed/);
});

test('motion card and joint audit: the quoted receipts are in the published docs', async () => {
  const current = await read('docs/validation/current-model.md');
  assert.match(current, /48 components × 46 independent required poses \+ 90 operating frames passed; maximum landmark error 0\.000010 mm at 0\.02 mm tolerance/);
  const motion = card('MOTION TRACES');
  assert.equal(text(motion.querySelector('.loop-metric b')), '0.00001 mm');
  assert.match(text(motion.querySelector('.loop-metric span')), /48 parts × 46 poses \(limit 0\.02 mm\)/);
  assert.match(await read('docs/validation/turret-motion.md'), /At 180 degrees their centers moved 96 mm/);
  assert.match(text(motion), /96 mm off at 180°/);
  const audit = card('JOINT AUDIT');
  assert.equal(text(audit.querySelector('.loop-status')), 'In progress');
  assert.equal(audit.querySelector('.loop-links a').getAttribute('href'), 'https://github.com/Valpatel/cad-agent/issues/230');
  // CFD is not claimed: Gyropup's body thermal case has not run it (docs/body-thermal.md).
  assert.doesNotMatch(text(loop), /\bCFD\b/);
});

test('live line: only well-formed version.json fields are shown', () => {
  assert.equal(SOURCE, 'https://cad-agent.gyropup.com/version.json');
  assert.deepEqual(describeLive(LIVE), { revision: LIVE.revision, date: '1 Nov 2026', pages: 64, items: 179 });
  for (const bad of [null, 'x', {}, { ...LIVE, revision: 'main' }, { ...LIVE, revision: LIVE.revision.toUpperCase() },
    { ...LIVE, built: 'yesterday' }, { ...LIVE, built: 0 }, { ...LIVE, pages: '64' }, { ...LIVE, items: 0 }, { ...LIVE, items: 1.5 }]) {
    assert.equal(describeLive(bad), null, JSON.stringify(bad));
  }
});

let browser, server, base;
before(async () => {
  base = process.env.SITE_URL?.replace(/\/$/, '');
  if (!base) {
    server = createSiteServer(path.join(root, 'dist'));
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    base = `http://127.0.0.1:${server.address().port}`;
  }
  browser = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? await webkit.launch({ headless: true })
    : await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true });
});
after(async () => {
  await browser?.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

/** A page whose cad-agent requests are answered by `answer` once `release` resolves; nothing reaches the network. */
async function open({ width = 1440, height = 1000, answer = 'live', javaScriptEnabled = true, reducedMotion = 'no-preference', near = true } = {}) {
  const context = await browser.newContext({ viewport: { width, height }, javaScriptEnabled, reducedMotion });
  await acknowledgePrototypeNotice(context);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const asked = [];
  await context.route('https://cad-agent.gyropup.com/**', async route => {
    if (!route.request().url().endsWith('/version.json')) return route.fulfill({ status: 200, contentType: 'text/html', body: '<title>cad-agent</title>' });
    asked.push(route.request().headers());
    await gate;
    if (answer === 'live') return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(LIVE) });
    if (answer === 'bad') return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ ...LIVE, revision: '<b>x</b>' }) });
    return route.abort();
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => document.fonts.ready);
  // The live request starts only as the section comes near the viewport.
  if (near) await page.locator('#loop').scrollIntoViewIfNeeded();
  return { context, page, release, errors, asked };
}
const box = (page, selector) => page.locator(selector).evaluate(el => { const r = el.getBoundingClientRect(); return { top: r.top + scrollY, height: r.height, width: r.width }; });

test('live data fills the reserved line without moving anything, at phone, tablet and desktop widths', async () => {
  for (const [width, height] of [[320, 640], [360, 740], [390, 844], [768, 1024], [1440, 1000]]) {
    const { context, page, release, errors, asked } = await open({ width, height });
    const line = page.locator('.loop-live');
    assert.equal(await line.getAttribute('data-state'), 'static');
    const beforeLine = await box(page, '.loop-live'), beforeFigure = await box(page, '.loop-figure'), beforeLoop = await box(page, '#loop');
    release();
    await page.waitForSelector('.loop-live[data-state="live"]');
    assert.equal((await line.innerText()).trim(), 'Live: 179 catalogue entries · 64 pages · updated 1 Nov 2026');
    assert.equal(await line.locator('a').getAttribute('href'), 'https://github.com/Valpatel/cad-agent/commit/' + LIVE.revision);
    assert.equal(await line.locator('a').getAttribute('aria-label'), 'cad-agent commit 9eb33cf, built 1 Nov 2026');
    assert.equal(asked.length, 1);
    assert.equal(asked[0].referer, undefined, 'no referrer is sent');
    assert.deepEqual(await box(page, '.loop-live'), beforeLine, `live line moved at ${width}px`);
    assert.deepEqual(await box(page, '.loop-figure'), beforeFigure, `figure moved at ${width}px`);
    assert.deepEqual(await box(page, '#loop'), beforeLoop, `section moved at ${width}px`);
    const overflow = await page.evaluate(() => {
      const section = document.querySelector('#loop').getBoundingClientRect();
      const out = [...document.querySelectorAll('#loop *')].filter(el => {
        const r = el.getBoundingClientRect();
        return r.width && !el.closest('.vh') && (r.left < section.left - 1 || r.right > section.right + 1);
      }).map(el => el.className || el.tagName);
      return { page: document.documentElement.scrollWidth - innerWidth, out };
    });
    assert.equal(overflow.page, 0, `page overflows at ${width}px`);
    assert.deepEqual(overflow.out, [], `section content overflows at ${width}px`);
    assert.deepEqual(errors, []);
    await context.close();
  }
});

test('a blocked, failed or malformed reply keeps the complete static line', async () => {
  for (const answer of ['abort', 'bad']) {
    const { context, page, release, errors } = await open({ answer });
    release();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('.loop-live').getAttribute('data-state'), 'static', answer);
    assert.match(await page.locator('.loop-live').innerText(), /open source \(MIT\)/);
    assert.equal(await page.locator('.loop-live a').count(), 0);
    assert.deepEqual(errors, []);
    await context.close();
  }
});

test('without script the section and its link are complete', async () => {
  const { context, page } = await open({ javaScriptEnabled: false, width: 390, height: 844 });
  const cta = page.getByRole('link', { name: 'Explore cad-agent', exact: true });
  assert.ok(await cta.isVisible());
  assert.equal(await cta.getAttribute('href'), 'https://cad-agent.gyropup.com');
  assert.ok(await page.getByRole('region', { name: 'Checks that make two projects better.' }).isVisible());
  assert.match(await page.locator('.loop-live').innerText(), /cad-agent\.gyropup\.com · open source/);
  await context.close();
});

test('keyboard reaches and follows the link; reduced motion stops the pulses', async () => {
  const { context, page, release } = await open({ reducedMotion: 'reduce' });
  release();
  let focused = '';
  for (let i = 0; i < 60 && !focused.includes('loop-cta'); i++) {
    await page.keyboard.press('Tab');
    focused = await page.evaluate(() => document.activeElement?.className || '');
  }
  assert.match(focused, /loop-cta/, 'Tab reaches Explore cad-agent');
  assert.notEqual(await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle), 'none');
  const motion = await page.evaluate(() => [getComputedStyle(document.querySelector('.loop-status'), '::before').animationName,
    getComputedStyle(document.querySelector('.loop-live .status-dot')).animationName]);
  assert.deepEqual(motion, ['none', 'none']);
  await Promise.all([page.waitForURL('https://cad-agent.gyropup.com/'), page.keyboard.press('Enter')]);
  await context.close();
});

test('text in the section has at least 4.5:1 contrast against its background', async () => {
  const { context, page, release } = await open();
  release();
  await page.waitForSelector('.loop-live[data-state="live"]');
  const failures = await page.evaluate(() => {
    const parse = c => { const m = c.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]; return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
    const over = (top, bottom) => ({ r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 });
    const background = el => {
      const layers = [];
      for (let node = el; node; node = node.parentElement) {
        const c = parse(getComputedStyle(node).backgroundColor);
        if (c.a > 0) layers.push(c);
        if (c.a === 1) break;
      }
      return layers.reverse().reduce((under, top) => over(top, under), { r: 255, g: 255, b: 255, a: 1 });
    };
    const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
    const out = [];
    for (const el of document.querySelectorAll('#loop *')) {
      if (el.closest('[aria-hidden="true"], .vh') || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      const fg = over(parse(getComputedStyle(el).color), background(el));
      const [a, b] = [lum(fg), lum(background(el))].sort((x, y) => y - x);
      const ratio = (a + .05) / (b + .05);
      if (ratio < 4.5) out.push(`${el.tagName}.${el.className} "${el.textContent.trim().slice(0, 30)}" ${ratio.toFixed(2)}`);
    }
    return out;
  });
  assert.deepEqual(failures, []);
  await context.close();
});

test('every link in the section resolves, including anchors, and llms.txt names cad-agent', async () => {
  const hrefs = [...new Set([...loop.querySelectorAll('a[href]')].map(a => a.getAttribute('href')))];
  for (const href of hrefs) {
    if (/^https:\/\//.test(href)) {
      assert.match(href, /^https:\/\/(cad-agent\.gyropup\.com$|github\.com\/Valpatel\/(gyropup|cad-agent)(\/|$))/, href);
      continue;
    }
    const [pathname, hash] = href.split('#');
    const response = await fetch(base + pathname);
    assert.equal(response.status, 200, href);
    if (hash) assert.ok((await response.text()).includes(`id="${hash}"`), href);
  }
  const llms = await (await fetch(base + '/llms.txt')).text();
  assert.match(llms, /\[cad-agent\]\(https:\/\/cad-agent\.gyropup\.com\)/);
  assert.match(llms, /general-purpose CAD toolkit/);
  const overview = await (await fetch(base + '/index.md')).text();
  const section = overview.slice(overview.indexOf('ALWAYS IMPROVING'), overview.indexOf('physical tests are still ahead'));
  assert.match(section, /\[Explore cad-agent\]\(https:\/\/cad-agent\.gyropup\.com\/?\) \[Source on GitHub/);
  assert.match(section, /Studies below their own target: 2 of 54 on cad-agent v0\.4\.2’s material data, 16 of 54 after the re-run on v0\.6\.0\./);
  assert.doesNotMatch(section, /v0\.4\.2 \*\*2\*\*/, 'the drawn bars stay out of Markdown');
  assert.match(section, /\*\*Fix Gyropup\*\* – its parts and records/);
  assert.match(section, /fasteners \(pass\)/);
  assert.match(section, /motion \(pass, with a warning\)/);
  assert.doesNotMatch(section, / :/, 'no space before a colon');
  assert.doesNotMatch(section, /\)\[/, 'links are separated');
});
