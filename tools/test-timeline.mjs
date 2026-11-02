/** "What changed" (tools/timeline.mjs): the published timeline against git, read again here by its own commands, and
 * its layout, motion and Markdown. Browser tests use SITE_URL, or serve dist/ (run `npm run build` first). */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { parseHTML } from 'linkedom';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { DESIGN_PATHS, decisionChanges, imagePaths, renderTimeline, shorten, subsystemOf } from './timeline.mjs';
import { shortDate } from './status-board.mjs';

const root = path.resolve(import.meta.dirname, '..');
const dist = path.join(root, 'dist');
const git = (...args) => execFileSync('git', args, { cwd: root, maxBuffer: 64 << 20 });
const text = el => el.textContent.replace(/\s+/g, ' ').trim();
const doc = file => parseHTML(readFileSync(path.join(dist, file), 'utf8')).document;
const progress = doc('designer/progress.html'), landing = doc('index.html');
const published = JSON.parse(readFileSync(path.join(dist, 'site/timeline.json'), 'utf8'));
const events = published.events;

test('labels: the first clause, capitalised, no merge boilerplate, cut at a word', () => {
  assert.equal(shorten("Merge branch 'turret/program'"), 'Turret/program merged');
  assert.equal(shorten('Merge body/program: the P0 power skid and the P1 open frame, ready to order and cut'), 'The P0 power skid and the P1 open frame, ready to order and cut');
  assert.equal(shorten('Leg: fixes from the pre-order review (code; outputs rebuild next)'), 'Leg: fixes from the pre-order review (code; outputs rebuild next)');
  assert.equal(shorten('D71: design mass 37.5 kg; crush pads'), 'D71: design mass 37.5 kg');
  assert.equal(shorten('Merge body/program (#17): P0 shunt in the + lead (#11), fuse board on 10S (#12)'), 'P0 shunt in the + lead (#11), fuse board on 10S');
  const long = shorten('a '.repeat(80));
  assert.ok(long.length <= 84 && long.endsWith('…'));
});

test('decisions: added ones are new, edited ones revised, from the diff’s context', () => {
  const diff = ['--- a/docs/decisions.yaml', '+++ b/docs/decisions.yaml', '@@ -1,9 +1,13 @@', ' - id: D1', '   title: A', '- decision: old', '+ decision: new',
    ' - id: D2', '   title: B', '-', '+- id: D3', '+  title: C', ' - id: D4', '   title: D'].join('\n');
  assert.deepEqual(decisionChanges(diff), [{ id: 'D1', change: 'revised' }, { id: 'D3', change: 'new' }]);
  assert.deepEqual(decisionChanges(''), []);
});

test('without history the timeline says so; counts read as words', () => {
  assert.match(renderTimeline([]), /The change history is not available in this build/);
  const one = { sha: 'a'.repeat(40), date: '2026-11-01T00:00:00Z', pr: null, label: 'X', subsystems: [], decisions: [], image: null,
    kinds: { cad: 1, geometry: 2, renders: 0, records: 1, hardware: 0, decisions: 1 } };
  const html = renderTimeline([one]);
  assert.match(html, /1 CAD file · 2 models · 1 new record · 1 decision</);
  assert.match(html, /Shared records/);
  assert.match(html, /commit\/a{40}">aaaaaaa</);
});

test('subsystems come from paths', () => {
  assert.equal(subsystemOf('cad/fivebar.py'), 'leg');
  assert.equal(subsystemOf('exports/gates/wall.json'), 'turret');
  assert.equal(subsystemOf('exports/rig/rig-side.png'), 'rig');
  assert.equal(subsystemOf('hardware/fuse-board/design.py'), 'electronics');
  assert.equal(subsystemOf('exports/wheels/summary_curb.json'), 'wheels');
  assert.equal(subsystemOf('exports/body/mass.json'), 'body');
  assert.equal(subsystemOf('docs/decisions.yaml'), null);
});

test('every published change is a first-parent commit that changed the design, newest first, with git’s date', () => {
  const firstParent = new Set(git('rev-list', '--first-parent', 'HEAD').toString().trim().split('\n'));
  assert.ok(events.length >= 10, 'the history has design changes');
  let last = Infinity;
  for (const e of events) {
    assert.ok(firstParent.has(e.sha), e.sha);
    const [date, subject] = git('show', '-s', '--format=%cI%x1f%s', e.sha).toString().trim().split('\x1f');
    assert.equal(e.date, date);
    assert.ok(Date.parse(date) <= last, 'newest first'); last = Date.parse(date);
    const files = git('diff', '--name-only', `${e.sha}^1`, e.sha, '--', ...DESIGN_PATHS).toString().trim().split('\n').filter(Boolean);
    assert.ok(files.some(f => /^cad\/|^hardware\/|\.(step|stp|stl|3mf|dxf|png|jpg|webp)$|^docs\/decisions\.yaml$/.test(f) || /\.(json|csv)$/.test(f)), `${e.sha} changed the design`);
    if (e.pr) assert.match(subject, new RegExp(`^Merge pull request #${e.pr} `));
    const yamlDiff = git('diff', '-U60', `${e.sha}^1`, e.sha, '--', 'docs/decisions.yaml').toString();
    for (const d of e.decisions) {
      if (d.change === 'new') assert.match(yamlDiff, new RegExp(`^\\+- id: ${d.id}$`, 'm'), `${e.sha} adds ${d.id}`);
      else assert.match(yamlDiff, new RegExp(`^ - id: ${d.id}$(\\n[ +-](?!- id:).*)*?\\n[+-]\\s*\\S`, 'm'), `${e.sha} revises ${d.id}`);
    }
  }
  // Nothing is skipped between the first and the last shown: every first-parent design commit in that span is listed,
  // unless it only touched logs, browser snapshots or existing records.
  const shas = new Set(events.map(e => e.sha));
  const span = git('log', '--first-parent', '-m', '--format=%H', `${events.at(-1).sha}^1..HEAD`, '--', 'cad', 'docs/decisions.yaml', 'hardware').toString().trim().split('\n').filter(Boolean);
  for (const sha of new Set(span)) assert.ok(shas.has(sha), `${sha.slice(0, 7)} changed CAD, hardware or decisions but is not on the timeline`);
});

test('before and after renders are git’s own blobs, published under /site/timeline/', () => {
  let pairs = 0;
  for (const e of events.filter(e => e.image)) {
    const img = imagePaths(e);
    const after = readFileSync(path.join(dist, img.after));
    assert.equal(createHash('sha1').update(after).digest('hex'), createHash('sha1').update(git('show', `${e.sha}:${e.image.file}`)).digest('hex'), `${e.sha} after`);
    if (img.before) {
      pairs++;
      const before = readFileSync(path.join(dist, img.before));
      assert.equal(createHash('sha1').update(before).digest('hex'), createHash('sha1').update(git('show', `${e.sha}^1:${e.image.file}`)).digest('hex'), `${e.sha} before`);
    }
  }
  assert.ok(pairs >= 3, 'some changes show a before and an after');
});

test('both pages carry the timeline; the landing shows the newest and links to the rest', () => {
  const p = progress.querySelectorAll('#changes .tl-event'), l = landing.querySelectorAll('#changes .tl-event');
  assert.equal(p.length, events.length);
  assert.ok(l.length > 0 && l.length < p.length);
  assert.equal(landing.querySelector('#changes .tl-all').getAttribute('href'), '/designer/progress.html#changes');
  for (const [i, el] of [...p].entries()) {
    const e = events[i];
    assert.equal(el.querySelector('time').getAttribute('datetime'), e.date);
    assert.equal(text(el.querySelector('time')), shortDate(e.date));
    assert.ok(text(el.querySelector('.tl-label')).startsWith(e.label));
  }
  for (const d of [landing, progress]) for (const img of d.querySelectorAll('#changes img')) assert.ok(existsSync(path.join(dist, img.getAttribute('src').split('?')[0])), img.getAttribute('src'));
});

let browser, server, base;
before(async () => {
  base = process.env.SITE_URL?.replace(/\/$/, '');
  if (!base) {
    server = createSiteServer(dist);
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
async function open(route, { width = 1440, height = 1000, reducedMotion = 'no-preference', javaScriptEnabled = true } = {}) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion, javaScriptEnabled });
  await acknowledgePrototypeNotice(context);
  await context.route('https://cad-agent.gyropup.com/**', r => r.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + route, { waitUntil: 'load' });
  return { context, page, errors };
}

test('no overflow from 320 to 1440 px; changes slide in, and stay put with reduced motion or no script', async () => {
  // Laid out at rest: with motion, a change that has not come into view yet waits 14 px to the left.
  for (const route of ['/', '/designer/progress.html']) for (const [width, height] of [[320, 640], [390, 844], [768, 1024], [1440, 1000]]) {
    const { context, page, errors } = await open(route, { width, height, reducedMotion: 'reduce' });
    if (route.includes('progress')) await page.locator('#changes .tl-more > summary').click();
    const out = await page.evaluate(() => {
      const box = document.querySelector('#changes').getBoundingClientRect();
      return { page: document.documentElement.scrollWidth - innerWidth,
        out: [...document.querySelectorAll('#changes *')].filter(el => { const r = el.getBoundingClientRect(); return r.width && (r.left < box.left - 1 || r.right > box.right + 1); }).map(el => el.className || el.tagName) };
    });
    assert.equal(out.page, 0, `${route} ${width}px`);
    assert.deepEqual(out.out, [], `${route} ${width}px`);
    assert.deepEqual(errors, []);
    await context.close();
  }
  {
    const { context, page } = await open('/designer/progress.html');
    assert.ok(await page.locator('#changes.tl-armed').count());
    await page.locator('#changes .tl-event').first().scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('#changes .tl-event').classList.contains('is-in'));
    await context.close();
  }
  for (const options of [{ reducedMotion: 'reduce' }, { javaScriptEnabled: false }]) {
    const { context, page } = await open('/', options);
    assert.equal(await page.locator('#changes.tl-armed').count(), 0);
    assert.ok((await page.locator('#changes .tl-event').evaluateAll(els => els.map(e => getComputedStyle(e).opacity))).every(o => o === '1'));
    await context.close();
  }
});

test('Markdown keeps every change with its date and label', async () => {
  const md = await (await fetch(base + '/designer/progress.md')).text();
  for (const e of events) assert.ok(md.includes(e.label.replace(/[*_]/g, m => '\\' + m)) || md.includes(e.label), e.label);
});
