/** The wall-of-text gate: no published page has more than WALL_LIMIT (1200 px at 1366 x 800) of content with nothing
 * to look at, except the pages on tools/wall-backlog.json, which may only shrink. See tools/site-walls.mjs.
 *
 *   npm run build && npm run test:walls              # serves dist/ on a test-owned listener
 *   SITE_URL=http://127.0.0.1:8879 npm run test:walls
 *   node tools/test-walls.mjs --report               # every page's longest stretch, worst first; never fails
 *
 * A backlog page that measures under WALL_CLEARED must leave the list, a page may never join it, and the list may not
 * gain a page the base branch's list lacks (the same shrink-only rule as tools/privacy-ratchet.txt). */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from '../../../tools/site/serve-site.mjs';
import { renderTimeline } from '../../../tools/site/timeline.mjs';
import { acknowledgePrototypeNotice } from '../content/test-prototype-session.mjs';
import { installRenderedReadiness } from './test-rendered-readiness.mjs';
import { loadWallPage } from './test-wall-readiness.mjs';
import { wallReadinessControls } from './test-wall-readiness-controls.mjs';
import { VIEWPORT, VISUAL, WALL_CLEARED, WALL_LIMIT, longestStretch, plantedScript, sitePages } from '../../../tools/site/site-walls.mjs';

const root = path.resolve(import.meta.dirname, '../../..');
const BACKLOG = 'tools/wall-backlog.json';
const report = process.argv.includes('--report');
const backlog = JSON.parse(await readFile(path.join(root, BACKLOG), 'utf8'));
const problems = [];

// The list only shrinks. Its length is pinned, so a page joins it only with a visible edit to `left`, and a page the
// base branch's list does not have cannot join it at all.
const listed = Object.keys(backlog.pages);
if (listed.length !== backlog.left) problems.push(`${BACKLOG}: ${listed.length} pages but "left" says ${backlog.left}: ${listed.length < backlog.left ? `lower "left" to ${listed.length}` : 'the backlog only shrinks; break the page up instead'}`);
const git = (...args) => execFileSync('git', args, { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
let baseList = null, ref = null;
try { ref = process.env.WALLS_BASE_REF || git('merge-base', 'HEAD', `origin/${process.env.GITHUB_BASE_REF || 'dev'}`); }
catch { if (process.env.CI && !report) problems.push(`${BACKLOG}: no merge base with origin/${process.env.GITHUB_BASE_REF || 'dev'}, so the shrink-only check cannot run (fetch the full history)`); }
if (ref) {
  try { baseList = JSON.parse(git('show', `${ref}:${BACKLOG}`)).pages; }
  catch { /* the base has no backlog yet: this change adds it */ }
}
// A page may only come off the list, and its recorded stretch may only go down: never above the base's number.
if (baseList) for (const route of listed) {
  if (!(route in baseList)) problems.push(`${BACKLOG}: ${route} is not on the base branch's backlog; the list only shrinks`);
  else if (backlog.pages[route] > baseList[route]) problems.push(`${BACKLOG}: ${route} is recorded at ${backlog.pages[route]}px, above the base's ${baseList[route]}px; the numbers only go down`);
}
// The band absorbs layout differences between engines and runs; past it, a backlog page has grown.
export const GROWTH = 1.1;

let server, base = process.env.SITE_URL?.replace(/\/$/, '');
if (!base) {
  server = createSiteServer(path.join(root, 'dist'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
}
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true } : { headless: true });
const rows = [];
try {
  await wallReadinessControls(browser,base,root);
  const dist = path.join(root, 'dist');
  const files = (await readdir(dist, { recursive: true })).map(f => f.split(path.sep).join('/'));
  const pages = sitePages(files);
  assert.ok(pages.length > 60, `only ${pages.length} pages found in dist/: run npm run build first`);
  for (const route of listed) if (!pages.includes(route)) problems.push(`${BACKLOG}: ${route} is not a page; remove it`);
  const context = await browser.newContext({ viewport: VIEWPORT, reducedMotion: 'reduce' });
  await acknowledgePrototypeNotice(context);
  await installRenderedReadiness(context);
  // Live cad-agent data is never fetched by a test.
  await context.route('https://cad-agent.gyropup.com/**', route => route.abort());
  const reader = await context.newPage();
  await loadWallPage(reader,base,'/site/');
  // The measure itself, on planted articles of known geometry, so a broken measure cannot pass every page.
  for (const [name, { got, want }] of Object.entries(await reader.evaluate(plantedScript())))
    if (Math.abs(got - want) > 1) problems.push(`walls: the planted "${name}" article measures ${got}px, not ${want}px`);
  for (const route of pages) {
    await loadWallPage(reader,base,route);
    const wall = await reader.evaluate(longestStretch, VISUAL);
    rows.push({ route, ...wall });
    if (report) continue;
    const where = `${wall.worst}px with nothing to look at, ${wall.from}-${wall.to}px into the page, after "${wall.after}"`;
    if (route in backlog.pages) {
      if (wall.worst < WALL_CLEARED) problems.push(`walls ${route}: ${where}, under ${WALL_CLEARED}px: remove it from ${BACKLOG} and lower "left"`);
      else if (wall.worst > backlog.pages[route] * GROWTH) problems.push(`walls ${route}: ${where}, more than ${Math.round((GROWTH - 1) * 100)}% over the ${backlog.pages[route]}px recorded in ${BACKLOG}; a page on the backlog may not grow`);
    } else if (wall.worst > WALL_LIMIT) problems.push(`walls ${route}: ${where}; the limit is ${WALL_LIMIT}px. Lead with a diagram, a render, a chart from the page's own table or a status strip, or fold long evidence into <details>`);
  }
  // The change list on / and Progress, planted with this build's history but with the newest five changes text-only
  // (a pull request that ends on receipt, fit-job or probe commits, as #181 did): the open list must still end on a
  // picture, so neither page grows a wall whatever the git history looks like.
  // It serves the two pages from the local dist/, so it runs against SITE_URL too, as in CI.
  if (!report) {
    const { events } = JSON.parse(await readFile(path.join(dist, 'site/timeline.json'), 'utf8'));
    const quiet = events.map((e, i) => i < 5 ? { ...e, image: null } : e);
    const planted = await context.newPage();
    for (const [route, file, options] of [['/', 'index.html', { compact: true, show: 4 }], ['/designer/progress.html', 'designer/progress.html', { show: 5, more: quiet.length }]]) {
      const built = await readFile(path.join(dist, file), 'utf8'), changes = /<section id="changes"[\s\S]*?<\/section>/;
      if (!changes.test(built)) { problems.push(`walls ${file}: no <section id="changes"> to plant a text-only timeline into`); continue; }
      const html = built.replace(changes, renderTimeline(quiet, options));
      await planted.route(base + route, r => r.fulfill({ status: 200, contentType: 'text/html', body: html }));
      await loadWallPage(planted,base,route);
      const wall = await planted.evaluate(longestStretch, VISUAL);
      if (wall.worst > WALL_LIMIT) problems.push(`walls ${route} with the newest five changes text-only: ${wall.worst}px with nothing to look at, after "${wall.after}"; the change list must end on a picture (tools/timeline.mjs)`);
    }
  }
  await context.close();
} finally {
  await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
}
rows.sort((a, b) => b.worst - a.worst);
if (report) {
  for (const r of rows) console.log(`${String(r.worst).padStart(6)} px  ${String(r.visuals).padStart(3)} visuals  ${r.route}  (after "${r.after}")`);
  console.log(`${rows.length} pages, ${rows.filter(r => r.worst > WALL_LIMIT).length} over ${WALL_LIMIT}px`);
} else {
  console.log(`walls: ${rows.length} pages measured at ${VIEWPORT.width} x ${VIEWPORT.height}; ${rows.filter(r => r.worst > WALL_LIMIT).length} over ${WALL_LIMIT}px, ${listed.length} on the backlog`);
  if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
}
