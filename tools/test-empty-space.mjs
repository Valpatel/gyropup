/** The empty-space gate: every published page, at a phone, an iPhone, a tablet, a small laptop and a desktop, in the
 * light and the dark theme, scrolled one screen at a time like a reader. It fails on a blank band taller than the
 * size's limit, a picture box painted blank, or text squeezed to one word a line. The measures and their limits are
 * in tools/site-empty-space.mjs.
 *
 *   npm run build && npm run test:empty-space        # serves dist/ on a test-owned listener
 *   SITE_URL=http://127.0.0.1:8879 npm run test:empty-space
 *   node tools/test-empty-space.mjs --report         # every page's worst gap per size, worst first; never fails
 *   node tools/test-empty-space.mjs --pages=/,/site/ --sizes=iphone-13 --schemes=light
 *
 * Before the site, the measures run on planted defects (a tall empty band crossed by hairline rules, a blank picture,
 * a blank canvas, a squeezed link column) and must catch each one, so a broken measure cannot pass every page.
 * On a failure it saves a screenshot with the finding outlined in test-results/empty-space/, and it writes every
 * page's numbers to test-results/empty-space/results.json. */
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium, devices } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { sitePages } from './site-walls.mjs';
import {
  BUSY_EDGES, EDGE_STEP, FLAT_SHARE, FLAT_TOLERANCE, MEDIA_MIN, MIN_THICKNESS, NARROW_SHARE, SCHEMES, SIZES, WORDS_PER_LINE,
  paintedPixels, scanLayout,
} from './site-empty-space.mjs';

const root = path.resolve(import.meta.dirname, '..');
const out = path.join(root, 'test-results/empty-space');
const arg = name => process.argv.find(a => a.startsWith(`--${name}=`))?.split('=')[1];
const report = process.argv.includes('--report');
const pick = (all, name) => { const want = arg(name)?.split(','); return want ? all.filter(x => want.includes(x.name ?? x)) : all; };
const sizes = pick(SIZES, 'sizes'), schemes = pick(SCHEMES, 'schemes');
const workers = Number(arg('workers') || process.env.EMPTY_SPACE_WORKERS || 3);
const problems = [], rows = [];
const started = Date.now();

let server, base = process.env.SITE_URL?.replace(/\/$/, '');
if (!base) {
  server = createSiteServer(path.join(root, 'dist'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
}
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});

/** A context for one screen size: the reader has acknowledged the prototype notice, and no live data is fetched. */
async function contextFor(size) {
  const { defaultBrowserType, ...device } = size.device ? devices[size.device] : {};
  const context = await browser.newContext({ ...device, ...size.context, colorScheme: 'light', reducedMotion: 'reduce' });
  await acknowledgePrototypeNotice(context);
  await context.route('https://cad-agent.gyropup.com/**', route => route.abort());
  return context;
}

/** Open a page and wait for what draws itself: diagrams, the portal reports, fonts. */
async function load(page, route) {
  await page.goto(base + route, { waitUntil: 'load' });
  await page.waitForFunction(() => !document.querySelector('pre.mermaid, pre > code.language-mermaid') &&
    [...document.querySelectorAll('.cad-diagram')].every(f => f.dataset.state === 'ready' || f.dataset.state === 'error')
    && (!/^\/designer\/(progress|build|sim)\.html$/.test(location.pathname) || document.body.dataset.ready === '1'), null, { timeout: 30000 })
    .catch(() => problems.push(`empty-space ${route}: diagrams or reports did not finish loading`));
  await page.evaluate(() => document.fonts.ready);
}

/** Wait (up to `ms`) for the pictures on screen to load, then for two frames. */
const settle = (page, ms = 3000) => page.evaluate(ms => new Promise(resolve => {
  const onScreen = el => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.width > 0; };
  const pending = () => [...document.images].filter(i => onScreen(i) && !i.complete).length;
  const end = Date.now() + ms;
  (function wait() {
    if (pending() && Date.now() < end) return setTimeout(wait, 50);
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  })();
}), ms);

/** Scroll the whole page one screen at a time, as a reader does, so lazy pictures load; then back to the top. */
async function scrollThrough(page) {
  for (let y = 0, i = 0; i < 200; i++) {
    await page.evaluate(y => scrollTo(0, y), y);
    await settle(page);
    const { height, vh } = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, vh: innerHeight }));
    y += vh;
    if (y >= height) break;
  }
  await page.evaluate(() => scrollTo(0, 0));
  await settle(page, 500);
}

const pixels = async (analysis, png, jobs) => analysis.evaluate(paintedPixels, { png: png.toString('base64'), jobs, busyEdges: BUSY_EDGES, edgeStep: EDGE_STEP, flatTolerance: FLAT_TOLERANCE });
const slug = s => s.replace(/^\/|\/$/g, '').replace(/[^a-z0-9]+/gi, '-') || 'home';

/** Elements that stay on screen (fixed, sticky) would cover a band in a screenshot: hide them while it is taken. */
const hideFloating = page => page.evaluate(() => {
  if (document.documentElement.scrollHeight <= innerHeight + 1) return;  // nothing scrolls under them
  for (const el of document.querySelectorAll('body *')) if (/fixed|sticky/.test(getComputedStyle(el).position)) el.dataset.esHidden = el.style.visibility || '-', el.style.visibility = 'hidden';
});
const showFloating = page => page.evaluate(() => {
  for (const el of document.querySelectorAll('[data-es-hidden]')) { el.style.visibility = el.dataset.esHidden === '-' ? '' : el.dataset.esHidden; delete el.dataset.esHidden; }
});

/** A screenshot of the screen with a box outlined, for the report. */
async function evidence(page, file, box) {
  await page.evaluate(([x, y, w, h]) => {
    const o = Object.assign(document.createElement('div'), { id: 'empty-space-outline' });
    o.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;outline:3px dashed #e0115f;outline-offset:-3px;background:#e0115f1f;z-index:2147483647;pointer-events:none`;
    document.body.append(o);
  }, box);
  await page.screenshot({ path: path.join(out, file), scale: 'css' });
  await page.evaluate(() => document.getElementById('empty-space-outline')?.remove());
  return path.relative(root, path.join(out, file));
}

/** Every finding on the page as it is now: [{kind, at, text, ...}], and the page's worst gap. */
async function audit(page, analysis, size, scheme, route) {
  const vh = await page.evaluate(() => innerHeight);
  const limit = size.limit * vh, tag = `${slug(route)}-${size.name}-${scheme}`;
  const scan = await page.evaluate(scanLayout, { minThickness: MIN_THICKNESS, narrowShare: NARROW_SHARE, wordsPerLine: WORDS_PER_LINE, mediaMin: MEDIA_MIN, minGap: Math.min(60, limit) });
  const findings = [];
  let worst = { size: 0, quiet: 0 };
  // Gaps: the DOM's candidates, each confirmed in a screenshot of the screen it shows on.
  const candidates = scan.gaps.sort((a, b) => b.size - a.size);
  for (const gap of candidates) {
    if (gap.size < limit && gap.size <= worst.size) continue;
    const span = Math.min(gap.size, vh);
    const y = Math.max(0, Math.round(gap.from - (vh - span) / 2));
    await page.evaluate(y => scrollTo(0, y), y);
    await settle(page, 1000);
    const at = await page.evaluate(() => scrollY);
    await hideFloating(page);
    const [band] = await pixels(analysis, await page.screenshot({ scale: 'css' }), [{ band: [gap.from - at, gap.to - at] }]);
    if (gap.size > worst.size) worst = { ...gap, quiet: band.quiet };
    if (gap.size >= limit && band.quiet >= limit) {
      const file = await evidence(page, `gap-${tag}-${gap.from}.png`, [0, at + band.from, scan.vw, band.quiet]);
      findings.push({ kind: 'gap', at, from: gap.from, to: gap.to, text: `${band.quiet}px blank (${(band.quiet / vh).toFixed(2)} of the screen; limit ${size.limit}) at ${gap.from}-${gap.to}px, scrolled to ${at}px, between ${gap.above} and ${gap.below}, under "${gap.heading}"`, file });
    }
    await showFloating(page);
  }
  // Pictures: each scrolled into view, then its painted pixels.
  const media = scan.media.sort((a, b) => a.top - b.top);
  for (let i = 0; i < media.length;) {
    const y = Math.max(0, Math.round(media[i].top - Math.max(0, (vh - media[i].height) / 2)));
    await page.evaluate(y => scrollTo(0, y), y);
    await settle(page);
    const at = await page.evaluate(() => scrollY);
    const batch = [];
    while (i < media.length && media[i].top >= at - 1 && media[i].top + Math.min(media[i].height, vh) <= at + vh + 1) batch.push(media[i++]);
    if (!batch.length) batch.push(media[i++]);  // taller than the screen and not at its top: check what shows
    const states = await page.evaluate(boxes => boxes.map(b => {
      const el = [...document.querySelectorAll('img, video, canvas')].find(e => { const r = e.getBoundingClientRect(); return r.top + scrollY <= b.top + 2 && r.bottom + scrollY >= b.top + b.height - 2 && r.left + scrollX <= b.left + 2 && r.right + scrollX >= b.left + b.width - 2; });
      return !el ? null : el.tagName === 'IMG' ? el.complete && el.naturalWidth > 0 : el.tagName === 'VIDEO' ? el.readyState >= 2 || !!el.getAttribute('poster') : true;
    }), batch);
    await hideFloating(page);
    const shot = await page.screenshot({ scale: 'css' });
    const looks = await pixels(analysis, shot, batch.map(m => ({ box: [m.left, m.top - at, m.width, Math.min(m.height, vh - (m.top - at))] })));
    await showFloating(page);
    for (const [k, m] of batch.entries()) {
      if (states[k] === null) continue;  // moved since the scan (a carousel, a re-render): the next scan has it
      const blank = states[k] === false ? 'never loaded' : looks[k].flat >= FLAT_SHARE ? `painted one flat colour (${(looks[k].flat * 100).toFixed(1)}% ${looks[k].colour})` : null;
      if (!blank) continue;
      const file = await evidence(page, `blank-${tag}-${Math.round(m.top)}.png`, [m.left, m.top, m.width, m.height]);
      findings.push({ kind: 'blank', at, text: `${m.name} (${Math.round(m.width)}x${Math.round(m.height)}, ${m.src || 'no src'}) at ${Math.round(m.top)}px is ${blank}`, file, name: m.name });
    }
  }
  // Squeezed text.
  for (const c of scan.columns) {
    const at = Math.max(0, Math.round(c.top - vh / 3));
    await page.evaluate(y => scrollTo(0, y), at);
    const file = await evidence(page, `column-${tag}-${Math.round(c.top)}.png`, [c.left, c.top, c.width, c.height]);
    findings.push({ kind: 'column', at, text: `${c.name} is ${c.width}px wide (${(c.width / scan.vw * 100).toFixed(0)}% of the screen) and wraps ${c.words} words onto ${c.lines} lines, at ${Math.round(c.top)}px under "${c.heading}"`, file, name: c.name });
  }
  await page.evaluate(() => scrollTo(0, 0));
  return { findings, worst, vh, docH: scan.docH, boxes: scan.contentBoxes, media: scan.media.length };
}

const analysisContext = await browser.newContext();
const newAnalysis = () => analysisContext.newPage();

/** Planted defects on a real page: each must be found, so the measures are tested on every run. */
async function controls() {
  const size = SIZES[0], context = await contextFor(size), page = await context.newPage(), analysis = await newAnalysis();
  const failed = [];
  try {
    await load(page, '/');
    await scrollThrough(page);
    await page.evaluate(() => {
      const after = document.querySelector('#meet') || document.querySelector('main > *');
      const solid = (() => { const c = document.createElement('canvas'); c.width = c.height = 4; const g = c.getContext('2d'); g.fillStyle = '#8fb7c4'; g.fillRect(0, 0, 4, 4); return c.toDataURL(); })();
      after.insertAdjacentHTML('afterend', `<div id="planted" style="padding:0 20px">
        <p>Planted: the paragraph above the empty band.</p>
        <div id="planted-gap" style="height:55vh;position:relative"><hr style="margin:20vh 0 0"><svg width="2" height="300" style="position:absolute;left:30%;top:0"><rect width="2" height="300" fill="#333"/></svg></div>
        <p>Planted: the paragraph below the empty band.</p>
        <p><img id="planted-blank" src="${solid}" width="300" height="200" alt="planted blank picture"></p>
        <p><canvas id="planted-canvas" width="280" height="160" style="background:#eee8dc"></canvas></p>
        <div style="display:flex;gap:16px;align-items:flex-start"><a id="planted-column" href="#planted" style="width:60px;font:700 13px/1.4 sans-serif">Explore the design ↗</a><div style="flex:1"></div></div>
        <p>Planted: the end.</p></div>`);
      // a full-height hairline down the whole page must not hide any gap
      document.body.insertAdjacentHTML('beforeend', `<svg id="planted-rule" width="2" height="${document.documentElement.scrollHeight}" style="position:absolute;left:12px;top:0"><rect width="2" height="100%" fill="#555"/></svg>`);
    });
    await settle(page);
    for (const scheme of SCHEMES) {
      await page.emulateMedia({ colorScheme: scheme });
      await settle(page, 300);
      const gap = await page.evaluate(() => { const r = document.getElementById('planted-gap').getBoundingClientRect(); return [r.top + scrollY, r.bottom + scrollY]; });
      const { findings } = await audit(page, analysis, size, `control-${scheme}`, '/');
      const has = (kind, test) => findings.some(f => f.kind === kind && test(f));
      if (!has('gap', f => f.from <= gap[0] + 30 && f.to >= gap[1] - 30)) failed.push(`${scheme}: the planted ${Math.round(gap[1] - gap[0])}px empty band (crossed by a rule and a hairline) was not found`);
      if (!has('blank', f => f.name.includes('#planted-blank'))) failed.push(`${scheme}: the planted flat picture was not found`);
      if (!has('blank', f => f.name.includes('#planted-canvas'))) failed.push(`${scheme}: the planted blank canvas was not found`);
      if (!has('column', f => f.name.includes('#planted-column'))) failed.push(`${scheme}: the planted one-word-a-line link column was not found`);
      if (has('gap', f => f.from < gap[0] - 200 && f.to > gap[1] + 200)) failed.push(`${scheme}: the planted hairline was not ignored`);
    }
  } finally { await context.close(); await analysis.close(); }
  return failed;
}

try {
  const dist = path.join(root, 'dist');
  const files = (await readdir(dist, { recursive: true })).map(f => f.split(path.sep).join('/'));
  const all = sitePages(files);
  if (all.length < 60) throw new Error(`only ${all.length} pages found in dist/: run npm run build first`);
  const pages = arg('pages') ? arg('pages').split(',') : all;
  if (!report && !arg('pages')) {
    const failed = await controls();
    for (const f of failed) problems.push(`empty-space control ${f}`);
    console.log(`empty-space controls: ${failed.length ? `${failed.length} planted defects missed` : 'the planted gap, blank picture, blank canvas and squeezed column were each caught, in light and dark'}`);
  }
  // Every (size, page) is a job; a few workers share them, each with a context per size.
  const jobs = sizes.flatMap(size => pages.map(route => ({ size, route })));
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(workers, jobs.length) }, async () => {
    const contexts = new Map(), analysis = await newAnalysis();
    try {
      while (next < jobs.length) {
        const { size, route } = jobs[next++];
        if (!contexts.has(size.name)) { const c = await contextFor(size); contexts.set(size.name, { context: c, page: await c.newPage() }); }
        const { page } = contexts.get(size.name);
        try {
          await page.emulateMedia({ colorScheme: schemes[0] });
          await load(page, route);
          await scrollThrough(page);
          for (const scheme of schemes) {
            await page.emulateMedia({ colorScheme: scheme });
            await settle(page, 300);
            const r = await audit(page, analysis, size, scheme, route);
            rows.push({ route, size: size.name, scheme, vh: r.vh, docH: r.docH, worstGap: r.worst.size, worstShare: +(r.worst.size / r.vh).toFixed(3), quietShare: +(r.worst.quiet / r.vh).toFixed(3), worstAt: r.worst.from, between: r.worst.size ? `${r.worst.above} | ${r.worst.below}` : '', findings: r.findings });
            for (const f of r.findings) problems.push(`empty-space ${f.kind} ${route} ${size.name} ${scheme}: ${f.text} -> ${f.file}`);
          }
        } catch (e) { problems.push(`empty-space ${route} ${size.name}: ${e.message.split('\n')[0]}`); }
      }
    } finally { for (const { context } of contexts.values()) await context.close(); await analysis.close(); }
  }));
} finally {
  await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
}

rows.sort((a, b) => b.worstShare - a.worstShare);
await writeFile(path.join(out, 'results.json'), JSON.stringify(rows, null, 1));
const seconds = Math.round((Date.now() - started) / 1000);
if (report) {
  for (const r of rows) console.log(`${r.worstShare.toFixed(2)} (${String(r.worstGap).padStart(4)}px, pixels ${r.quietShare.toFixed(2)})  ${r.size.padEnd(12)} ${r.scheme.padEnd(5)} ${r.route}  ${r.findings.length} findings  [${r.between}]`);
  for (const r of rows) for (const f of r.findings) console.log(`  ${f.kind} ${r.route} ${r.size} ${r.scheme}: ${f.text}`);
  console.log(`${rows.length} page views in ${seconds}s`);
} else {
  const sum = rows.reduce((n, r) => n + r.findings.length, 0);
  console.log(`empty-space: ${new Set(rows.map(r => r.route)).size} pages x ${sizes.length} sizes x ${schemes.length} themes = ${rows.length} views in ${seconds}s; ${sum} findings`);
  for (const s of sizes) { const w = rows.filter(r => r.size === s.name)[0]; if (w) console.log(`  ${s.name.padEnd(12)} worst gap ${w.worstShare.toFixed(2)} of the screen (limit ${s.limit}) on ${w.route} ${w.scheme}`); }
  if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
}
