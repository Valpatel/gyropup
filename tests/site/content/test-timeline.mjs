/** "What changed" (tools/timeline.mjs): the published timeline against git, read again here by its own commands, and
 * its layout, motion and Markdown. Browser tests use SITE_URL, or serve dist/ (run `npm run build` first). */
import {prepareStaticMotionDocument,isStaticMotionChangeRequest} from '../models/current-motion-static.mjs';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, mkdtempSync, mkdirSync, writeFileSync, renameSync, rmSync } from 'node:fs';
import os from 'node:os';
import { publicForSource } from '../../../tools/site/source-layout.mjs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { parseHTML } from 'linkedom';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from '../../../tools/site/serve-site.mjs';
import { acknowledgePrototypeNotice } from '../assembly/build-prototype-session.mjs';
import { DESIGN_PATHS, SYNTHETIC_MERGE, changeUnits, collectTimeline, decisionChanges, gitIn, imagePaths, previewPaths, renderTimeline, shorten, subsystemOf } from '../../../tools/site/timeline.mjs';
import { shortDate } from '../../../tools/site/status-board.mjs';

const root = path.resolve(import.meta.dirname, '../../..');
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

test('CI\'s synthetic merge is opened into the pull request\'s commits, never shown as "Merge <sha> into <sha>"', () => {
  const h = c => c.repeat(40);
  const synth = `Merge ${h('a')} into ${h('b')}`;
  assert.ok(SYNTHETIC_MERGE.test(synth));
  for (const s of ['Merge pull request #12 from fork/topic', "Merge branch 'dev' into fix/x", `Merge ${h('a').slice(7)} into ${h('b')}`, `${synth} (edited)`])
    assert.ok(!SYNTHETIC_MERGE.test(s), s);
  // A fake history: base B0, the pull request's commits P1 and P2, and CI's merge M of P2 into B0.
  const rec = (sha, parents, date, subject) => [sha, parents, date, subject, ''].join('\x1f') + '\x1e';
  const logs = {
    HEAD: rec('M', 'B0 P2', '2026-11-03T10:00:00Z', synth) + rec('B0', 'B', '2026-11-01T10:00:00Z', 'Body: the base'),
    'B0..P2': rec('P2', 'P1', '2026-11-02T12:00:00Z', 'Rig: the second step') + rec('P1', 'B0', '2026-11-02T11:00:00Z', 'Rig: the first step'),
  };
  const fake = args => {
    if (args.includes('--merges')) return ''; // the pull request's branch carries no pull-request merges of its own
    return logs[args.at(-1)] ?? '';
  };
  const units = changeUnits(fake, 'HEAD');
  assert.deepEqual(units.map(u => u.sha), ['P2', 'P1', 'B0']);
  assert.ok(units.every(u => !SYNTHETIC_MERGE.test(u.subject)));
  // Without the rule this merge would have been one unit with the synthetic subject.
  assert.ok(!units.some(u => u.sha === 'M'));
});

test('decisions: added ones are new, edited ones revised, from the diff’s context', () => {
  const diff = ['--- a/docs/decisions.yaml', '+++ b/docs/decisions.yaml', '@@ -1,9 +1,13 @@', ' - id: D1', '   title: A', '- decision: old', '+ decision: new',
    ' - id: D2', '   title: B', '-', '+- id: D3', '+  title: C', ' - id: D4', '   title: D'].join('\n');
  assert.deepEqual(decisionChanges(diff), [{ id: 'D1', change: 'revised' }, { id: 'D3', change: 'new' }]);
  assert.deepEqual(decisionChanges(''), []);
  // A decision moved within the file is revised, not new; one only removed is not listed.
  const moved = ['@@ -1,6 +1,6 @@', '-- id: D9', '-  title: Moved', ' - id: D2', '   title: B', '+- id: D9', '+  title: Moved', '-- id: D5', '-  title: Gone'].join('\n');
  assert.deepEqual(decisionChanges(moved), [{ id: 'D9', change: 'revised' }]);
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

test('the open list ends on a picture; the text-only changes after it fold away, on Progress and the home page', () => {
  const ev = (n, image) => ({ sha: String(n).repeat(40).slice(0, 40), date: '2026-11-01T00:00:00Z', pr: n, label: `L${n}`, subsystems: [], decisions: [],
    image: image ? { file: 'exports/x.png', before: false } : null, kinds: {} });
  const events = [ev(1, true), ev(2, true), ev(3, false), ev(4, false), ev(5, false), ev(6, true)];
  const open = html => html.split('<details')[0].match(/pull\/\d+/g);
  const progress = renderTimeline(events, { show: 5, more: events.length });
  assert.deepEqual(open(progress), ['pull/1', 'pull/2']);
  assert.match(progress, /<summary>4 earlier changes</);
  const home = renderTimeline(events, { show: 4, compact: true });
  assert.deepEqual(open(home), ['pull/1', 'pull/2'], 'the home page folds its text-only tail too');
  assert.match(home, /<summary>2 earlier changes</);
  assert.match(home, /Every change on Progress/);
  assert.equal(open(renderTimeline(events, { show: 2, compact: true })).length, 2, 'a list that ends on a picture is kept whole');
  assert.doesNotMatch(renderTimeline(events, { show: 2, compact: true }), /<details/, 'with nothing after the picture, nothing folds');
});

test('a run of text-only changes at the top (data-only commits) folds in place, and the next picture is shown open', () => {
  const ev = (n, image) => ({ sha: String(n).repeat(40).slice(0, 40), date: '2026-11-01T00:00:00Z', pr: n, label: `L${n}`, subsystems: [], decisions: [],
    image: image ? { file: 'exports/x.png', before: false } : null, kinds: { records: 1 } });
  // The cards outside any fold, in page order, and the order of every card on the page.
  const outside = html => html.replace(/<details[\s\S]*?<\/details>/g, '').match(/pull\/\d+/g);
  const order = html => html.match(/pull\/\d+(?=")/g);
  // receipt, fit-job and probe commits on top, then pictured changes: the case that tripped tools/test-walls.mjs on #181
  const events = [ev(1), ev(2), ev(3), ev(4), ev(5), ev(6, true), ev(7, true), ev(8)];
  const all = events.map(e => `pull/${e.pr}`);
  const progress = renderTimeline(events, { show: 5, more: events.length });
  assert.deepEqual(outside(progress), ['pull/1', 'pull/6'], 'the newest change, then the next one with a picture');
  assert.match(progress, /<summary>4 changes without a picture<\/summary><ol class="tl-list">.*pull\/2".*pull\/5".*<\/ol><\/details><ol class="tl-list">.*pull\/6"/s);
  assert.match(progress, /<summary>2 earlier changes</);
  assert.deepEqual(order(progress), all, 'every change is on Progress once, in order');
  const home = renderTimeline(events, { show: 4, compact: true });
  assert.deepEqual(outside(home), ['pull/1', 'pull/6'], 'the home page reaches past its four for the picture');
  assert.deepEqual(order(home), all.slice(0, 6));
  assert.doesNotMatch(home, /earlier change/);
  // One text-only change on top needs no fold: the picture right after it is simply shown.
  const one = renderTimeline([ev(1), ev(2, true), ev(3)], { show: 4, compact: true });
  assert.deepEqual(outside(one), ['pull/1', 'pull/2']);
  assert.doesNotMatch(one, /without a picture/);
  // With no picture anywhere there is nothing to end on: the newest stays open and the rest fold.
  const none = renderTimeline(events.map(e => ({ ...e, image: null })), { show: 5, more: 8 });
  assert.deepEqual(outside(none), ['pull/1']);
  assert.match(none, /<summary>7 earlier changes</);
});

test('subsystems come from paths', () => {
  assert.equal(subsystemOf('cad/fivebar.py'), 'leg');
  assert.equal(subsystemOf('exports/gates/wall.json'), 'turret');
  assert.equal(subsystemOf('docs/carrier-service-connectors.md'), 'turret', 'the removable carrier sits on the turret pan base');
  assert.equal(subsystemOf('hardware/carrier-pan-protection/README.md'), 'electronics');
  assert.equal(subsystemOf('exports/rig/rig-side.png'), 'rig');
  assert.equal(subsystemOf('hardware/fuse-board/design.py'), 'electronics');
  assert.equal(subsystemOf('exports/wheels/summary_curb.json'), 'wheels');
  assert.equal(subsystemOf('exports/body/mass.json'), 'body');
  assert.equal(subsystemOf('docs/decisions.yaml'), null);
});

test('actual ownership rename stays out of design history; a subsequent CAD edit remains visible', () => {
  const repo=mkdtempSync(path.join(os.tmpdir(),'gyropup-timeline-rename-'));
  const invoke=args=>execFileSync('git',args,{cwd:repo,stdio:['ignore','pipe','pipe']}).toString();
  const commit=title=>invoke(['-c','user.name=Timeline control','-c','user.email=timeline@example.invalid','commit','-m',title]);
  try {
    invoke(['init','-q']); mkdirSync(path.join(repo,'cad'));
    writeFileSync(path.join(repo,'cad/fivebar.py'),'LENGTH = 100\n');
    invoke(['add','.']);commit('Initial CAD control');
    mkdirSync(path.join(repo,'hardware/cad/legs'),{recursive:true});
    renameSync(path.join(repo,'cad/fivebar.py'),path.join(repo,'hardware/cad/legs/fivebar.py'));
    invoke(['add','-A']);commit('Move unchanged CAD to its owning home');
    assert.match(invoke(['diff','--name-status','--find-renames','HEAD^','HEAD']),/^R100\t/);
    assert.deepEqual(collectTimeline(invoke,{limit:1}),[]);
    // A planted old no-renames implementation would fabricate a design event.
    const noRenames=args=>invoke(args.map(a=>a==='--find-renames'?'--no-renames':a));
    assert.equal(collectTimeline(noRenames,{limit:1}).length,1);
    writeFileSync(path.join(repo,'hardware/cad/legs/fivebar.py'),'LENGTH = 101\n');
    invoke(['add','.']);commit('Change the actual CAD control');
    const [event]=collectTimeline(invoke,{limit:1});
    assert.equal(event.kinds.cad,1);assert.equal(event.kinds.hardware,0);
    assert.deepEqual(event.subsystems,['leg']);
  } finally { rmSync(repo,{recursive:true,force:true}); }
});

// Read again here, by its own commands: the merges that carry pull requests (a release from dev into main, a sync back)
// are opened up, so each change is a pull request's merge or a direct commit, never a release.
// CI's own merge of a pull request into its base ("Merge <sha> into <sha>") is opened the same way.
const isIntegration = sha => {
  const [parents, subject] = git('show', '-s', '--format=%P%x1f%s', sha).toString().trim().split('\x1f');
  const [p1, p2] = parents.split(' ');
  return !!p2 && (/^Merge [0-9a-f]{40} into [0-9a-f]{40}$/.test(subject)
    || /^Merge pull request #\d+ /m.test(git('log', '--first-parent', '--merges', '--format=%s', `${p1}..${p2}`).toString()));
};
/** The generator's rule, written out again: what a commit changed against its first parent decides if it shows. */
const designIdentity = f => publicForSource(f) || (f.startsWith('hardware/cad/') ? f.replace(/^hardware\/cad\//,'cad/') : f==='hardware/__init__.py' ? 'cad/__init__.py' : f);
const designChange = sha => {
  const changed = git('diff', '--name-status', '--find-renames', `${sha}^1`, sha, '--', ...DESIGN_PATHS).toString().trim().split('\n').filter(Boolean)
    .map(l => { const [st, ...p] = l.split('\t'); return [st, designIdentity(p.at(-1))]; }).filter(([st, f]) => st!=='R100' && !/^exports\/(sim|links)\/|\.log$/.test(f));
  const decisions = /^[+-](?![+-]{2} )\s*\S/m.test(git('diff', `${sha}^1`, sha, '--', 'docs/decisions.yaml', 'docs/program/decisions.yaml').toString());
  return decisions || changed.some(([st, f]) => /^(cad|hardware)\//.test(f) || /\.(step|stp|stl|3mf|dxf)$/.test(f)
    || (/\.(png|jpg|webp)$/.test(f) && !/thumbs\//.test(f)) || (st[0] === 'A' && /\.(json|csv)$/.test(f)));
};

test('every published change is a pull request or a direct commit that changed the design, newest first, with git’s date', () => {
  const reachable = new Set(git('rev-list', 'HEAD').toString().trim().split('\n'));
  assert.ok(events.length >= 10, 'the history has design changes');
  let last = Infinity;
  for (const e of events) {
    assert.ok(reachable.has(e.sha), e.sha);
    assert.ok(!isIntegration(e.sha), `${e.sha.slice(0, 7)} is a release or sync merge; its pull requests show instead`);
    assert.doesNotMatch(e.label, /^Release\b/);
    const [date, subject] = git('show', '-s', '--format=%cI%x1f%s', e.sha).toString().trim().split('\x1f');
    assert.equal(e.date, date);
    assert.ok(Date.parse(date) <= last, 'newest first'); last = Date.parse(date);
    assert.ok(designChange(e.sha), `${e.sha} changed the design`);
    if (e.pr) assert.match(subject, new RegExp(`^Merge pull request #${e.pr} `));
    const yamlDiff = git('diff', '-U60', `${e.sha}^1`, e.sha, '--', 'docs/decisions.yaml', 'docs/program/decisions.yaml').toString();
    const then = e.decisions.length ? ['docs/program/decisions.yaml','docs/decisions.yaml'].map(f=>{try{return git('show',`${e.sha}:${f}`).toString();}catch{return '';}}).find(Boolean) : '';
    for (const d of e.decisions) {
      if (d.change === 'new') { assert.match(yamlDiff, new RegExp(`^\\+- id: ${d.id}$`, 'm'), `${e.sha} adds ${d.id}`); assert.doesNotMatch(yamlDiff, new RegExp(`^-- id: ${d.id}$`, 'm')); }
      else assert.match(yamlDiff, new RegExp(`^[ +-]- id: ${d.id}$(\\n[ +-](?!- id:).*)*?\\n[+-]\\s*\\S`, 'm'), `${e.sha} revises ${d.id}`);
      // The title is the one the decision had in that commit.
      if (d.title) assert.ok(then.includes(d.title.replace(/…$/, '').slice(0, 40)), `${e.sha} ${d.id}: "${d.title}"`);
    }
  }
});

test('nothing is skipped: every change in the span that changed the design is on the timeline', () => {
  const shas = new Set(events.map(e => e.sha)), since = Date.parse(events.at(-1).date);
  // Every commit of the main line, and of every branch an integration merge brings in (its first parent up to its
  // second), each once: pull request merges, other merges and direct commits alike.
  const units = new Set(), seen = new Set(), ranges = [['HEAD']];
  while (ranges.length) {
    for (const line of git('log', '--first-parent', '--format=%H %P%x1f%cI', ...ranges.pop()).toString().trim().split('\n')) {
      const [ids, date] = line.split('\x1f'), [sha, p1, p2] = ids.split(' ');
      if (seen.has(sha) || Date.parse(date) < since) continue;
      seen.add(sha);
      if (isIntegration(sha)) ranges.push([`${p1}..${p2}`]);
      else units.add(sha);
    }
  }
  const mainLine = new Set(git('rev-list', '--first-parent', 'HEAD').toString().trim().split('\n'));
  let checked = 0, opened = 0;
  for (const sha of units) {
    if (!designChange(sha)) continue;
    checked++;
    if (!mainLine.has(sha)) opened++;
    assert.ok(shas.has(sha), `${sha.slice(0, 7)} changed the design but is not on the timeline`);
  }
  assert.ok(checked >= 10, `only ${checked} changes checked`);
  assert.ok(opened > 0, 'the changes inside opened branches were checked too');
});

test('the public site, built from main, shows the same pull requests, never a release', { skip: !git('branch', '-r', '--list', 'origin/main').toString().trim() && 'no origin/main here' }, () => {
  const main = collectTimeline(gitIn(root), { head: 'origin/main', limit: 12 });
  assert.ok(main.length > 0);
  for (const e of main) {
    assert.doesNotMatch(e.label, /^Release\b/);
    assert.doesNotMatch(e.title, /from Valpatel\/dev$/, `${e.sha.slice(0, 7)} is a release merge`);
    assert.ok(!isIntegration(e.sha), `${e.sha.slice(0, 7)} is a merge that carries pull requests`);
  }
});

test('before and after originals remain Git blobs and card previews derive from each exact original', async () => {
  let pairs = 0;
  for (const e of events.filter(e => e.image)) {
    const img = imagePaths(e), previews = previewPaths(e);
    for (const side of ['after', 'before']) {
      if (!img[side]) continue;
      const original = readFileSync(path.join(dist, img[side]));
      const preview = readFileSync(path.join(dist, previews[side]));
      const meta = await sharp(preview).metadata();
      assert.equal(meta.format, 'webp');
      assert.ok(meta.width <= 480 && meta.height <= 330, `${e.sha} ${side} card dimensions`);
      const expected = await sharp(original).resize({ width: 480, height: 330, fit: 'inside', withoutEnlargement: true }).webp({ quality: 85 }).toBuffer();
      assert.deepEqual(preview, expected, `${e.sha} ${side} preview belongs to its original`);
    }
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

test('Progress carries the complete timeline; Home links to it without embedding history', () => {
  const p = progress.querySelectorAll('#changes .tl-event');
  assert.equal(landing.querySelectorAll('.tl-event').length, 0);
  assert.equal(p.length, events.length);
  assert.equal(landing.querySelector('a#changes').getAttribute('href'), '/designer/progress.html#changes');
  for (const [i, el] of [...p].entries()) {
    const e = events[i];
    assert.equal(el.querySelector('time').getAttribute('datetime'), e.date);
    assert.equal(text(el.querySelector('time')), shortDate(e.date));
    assert.ok(text(el.querySelector('.tl-label')).startsWith(e.label));
  }
  for (const d of [landing, progress]) for (const img of d.querySelectorAll('#changes img')) {
    const preview = img.getAttribute('src').split('?')[0], original = img.closest('a').getAttribute('href').split('?')[0];
    assert.ok(existsSync(path.join(dist, preview)), preview);
    assert.ok(existsSync(path.join(dist, original)), original);
    assert.equal(preview, original.replace(/\.[^.]+$/, '-preview.webp'));
  }
});

let browser, server, base;
const unsupportedLiveRequests=[];
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
  assert.deepEqual(unsupportedLiveRequests,[],'Static fixture never requests an unsupported development endpoint');
});
async function open(route, { width = 1440, height = 1000, reducedMotion = 'no-preference', javaScriptEnabled = true } = {}) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion, javaScriptEnabled });
  if (/^(127\.0\.0\.1|localhost|\[::1\])$/.test(new URL(base).hostname)) await context.addInitScript(prepareStaticMotionDocument,new URL(base).origin);
  context.on('request',request=>{if(isStaticMotionChangeRequest(request.url(),new URL(base).origin))unsupportedLiveRequests.push(request.url());});
  await acknowledgePrototypeNotice(context, base);
  await context.route('https://cad-agent.gyropup.com/**', r => r.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + route, { waitUntil: 'load' });
  return { context, page, errors };
}

test('no overflow from 320 to 1440 px; changes slide in, and stay put with reduced motion or no script', async () => {
  // Laid out at rest: with motion, a change that has not come into view yet waits 14 px to the left.
  for (const route of ['/designer/progress.html']) for (const [width, height] of [[320, 640], [390, 844], [768, 1024], [1440, 1000]]) {
    const { context, page, errors } = await open(route, { width, height, reducedMotion: 'reduce' });
    // Progress can fold twice: the text-only run before the anchor and the earlier changes (tools/timeline.mjs). Open
    // every fold, so all of them are laid out and checked, whatever the newest commits happen to be.
    if (route.includes('progress')) for (const summary of await page.locator('#changes .tl-more > summary').all()) await summary.click();
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
