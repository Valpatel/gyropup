/** Design-note pages (tools/doc-page.mjs): the same words as the Markdown, shown with a lead card, status strips
 * counted from the note's own tables, and folds. Browser tests use SITE_URL, or serve dist/ (run `npm run build`). */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { marked } from 'marked';
import { parseHTML } from 'linkedom';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { enhanceDocument, isCaveat, statusKind, tableStates } from './doc-page.mjs';
import { subsystemOf } from './timeline.mjs';

const root = path.resolve(import.meta.dirname, '..');
const dist = path.join(root, 'dist');
const norm = s => s.replace(/\s+/g, ' ').trim();
const fragment = html => parseHTML(`<!doctype html><html><body><article>${html}</article></body></html>`).document.querySelector('article');
const status = JSON.parse(readFileSync(path.join(dist, 'site/status.json'), 'utf8'));
const pages = readdirSync(path.join(dist, 'site/pages')).filter(f => f.endsWith('.html'));
const slug = p => p.toLowerCase().replace(/[^a-z0-9]+/g, '-');
const sources = new Map(['README.md', 'catalog/SCHEMA.md', ...['docs', 'research', 'hardware'].flatMap(function walk(dir) {
  return readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(`${dir}/${e.name}`) : e.name.endsWith('.md') ? [`${dir}/${e.name}`] : []);
})].map(f => [`${slug(f)}.html`, f]));
const WORST = ['docs-carrier-service-connectors-md', 'docs-leg-bench-tests-md', 'docs-requirements-md', 'docs-mechanical-readiness-md', 'docs-body-fuse-board-md', 'docs-body-frame-md', 'docs-turret-bench-tests-md'];

test('status words: a scale the page can colour honestly', () => {
  for (const [w, k] of [['done', 'good'], ['pass', 'good'], ['implemented', 'good'], ['open', 'todo'], ['check', 'todo'], ['fix', 'bad'], ['fail', 'bad'],
    ['ongoing', 'work'], ['owner', 'work'], ['note', 'note'], ['dropped', 'muted'], ['armed', 'other']]) assert.equal(statusKind(w), k, w);
});

const table = (head, rows) => fragment(`<div class="table-scroll"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`).querySelector('table');
test('a strip only for a real status column of short words, counted row by row', () => {
  const states = tableStates(table(['#', 'Status'], [['R1', 'done'], ['R2', 'open'], ['R3', 'open; waiting on parts'], ['R4', 'dropped'], ['R5', 'Done (PR 3)']]));
  assert.deepEqual(states.states.map(s => [s.key, s.n, s.kind]), [['done', 2, 'good'], ['open', 2, 'todo'], ['dropped', 1, 'muted']]);
  assert.equal(states.rows, 5);
  // A blank status is counted as not stated, so the bar covers every row.
  const blanks = tableStates(table(['#', 'Status'], [['R1', 'done'], ['R2', ''], ['R3', 'open'], ['R4', 'done'], ['R5', ''], ['R6', 'open']]));
  assert.equal(blanks.rows, 6);
  assert.deepEqual(blanks.states.map(s => [s.key, s.n, s.kind]), [['done', 2, 'good'], ['open', 2, 'todo'], ['no status', 2, 'todo']]);
  assert.equal(tableStates(table(['Status'], [['done'], ['open'], ['done']])), null, 'too few rows');
  assert.equal(tableStates(table(['State', 'Draw'], [['safe', '1'], ['armed', '2'], ['firing', '3'], ['docked', '4']])), null, 'names of states are not a scale');
  assert.equal(tableStates(table(['Verdict'], [['8'], ['2'], ['6'], ['1']])), null, 'numbers are not a scale');
  assert.equal(tableStates(table(['Item', 'Notes'], [['a', 'done'], ['b', 'done'], ['c', 'done'], ['d', 'done']])), null, 'no status column');
});

const longDoc = ['# A long note', 'The lede.', '## One', ...Array(7).fill('Words '.repeat(120)), '[Part STEP](/exports/part.step)', ...Array(3).fill('Words '.repeat(120)), '**Not qualified for fabrication.** Measure it first.', ...Array(4).fill('Words '.repeat(120)), '![a render](/x.png)', 'After the picture.',
  ...Array.from({ length: 12 }, (_, i) => `## Part ${i}\n\n${'More words here. '.repeat(90)}\n\n### Detail ${i}\n\nThe last fact of part ${i}.`)].join('\n\n');
test('folds keep every word, every id, and never fold a picture', async () => {
  const raw = await marked.parse(longDoc, { renderer: Object.assign(new marked.Renderer(), { heading({ tokens, depth }) { const t = this.parser.parseInline(tokens); return `<h${depth} id="${t.toLowerCase().replace(/\W+/g, '-')}">${t}</h${depth}>`; } }) });
  const { html, folds } = enhanceDocument(raw, { file: 'docs/long.md' });
  const out = fragment(html), before = fragment(raw);
  assert.ok(folds >= 10);
  for (const el of before.querySelectorAll('p, li, h2, h3')) assert.ok(norm(out.textContent).includes(norm(el.textContent)), norm(el.textContent).slice(0, 40));
  for (const el of before.querySelectorAll('[id]')) assert.equal(out.querySelectorAll(`#${el.id}`).length, 1, el.id);
  assert.equal(out.querySelectorAll('details img, details pre.mermaid, details .doc-strip').length, 0);
  assert.ok(out.querySelector('img:not(details img)'));
  // A link to a model is an action (web/model-links.js adds "Preview in 3D"): it stays in view.
  assert.ok(out.querySelector('a[href="/exports/part.step"]'));
  assert.equal(out.querySelector('a[href="/exports/part.step"]').closest('details'), null, 'a model link is never folded');
  // A paragraph that opens with a bold limit stays in view too.
  assert.equal([...out.querySelectorAll('p')].find(p => p.textContent.startsWith('Not qualified')).closest('details'), null, 'a caveat is never folded');
  assert.ok(out.querySelector('details.doc-section > summary > h2#part-3'), 'a section folds behind its own heading');
  assert.equal(out.querySelector('h1 + p').textContent, 'The lede.', 'the lede stays in view');
  assert.ok(out.querySelector('aside.doc-card'));
});

test('every built note keeps its Markdown’s words, under a lead card', async () => {
  let checked = 0, previews = 0;
  for (const page of pages) {
    const file = sources.get(page);
    if (!file) continue;
    const doc = parseHTML(readFileSync(path.join(dist, 'site/pages', page), 'utf8')).document;
    const article = doc.querySelector('main.document article');
    assert.ok(article.querySelector('aside.doc-card'), page);
    for (const preview of article.querySelectorAll('a[data-model-preview]')) preview.remove(); // web/model-links.js adds "Preview 3D"
    const text = norm(article.textContent).replace(/ \(historical file\)/g, ''); // the build marks two retired catalogue links
    const raw = fragment(await marked.parse(readFileSync(path.join(root, file), 'utf8')));
    for (const el of raw.querySelectorAll('p, li, td, th, h2, h3, h4')) if (!el.querySelector('img') && norm(el.textContent)) assert.ok(text.includes(norm(el.textContent)), `${file}: "${norm(el.textContent).slice(0, 60)}"`);
    assert.equal(article.querySelectorAll('details.doc-fold img, details.doc-fold video, details.doc-fold .doc-strip, details.doc-fold code.language-mermaid').length, 0, `${page}: a picture is folded`);
    // A link to a model gets a "Preview in 3D" action (web/model-links.js): in a table, a list or prose, it stays in view.
    const own = a => /\.(step|stp|stl|3mf|glb|gltf)([?#].*)?$/i.test(a.getAttribute('href')) && !/^(https?:)?\/\//.test(a.getAttribute('href'));
    // A table of models may fold; its summary then counts the models inside.
    const folded = [...article.querySelectorAll('details.doc-fold a[href]')].filter(own).filter(a => !a.closest('table'));
    assert.equal(folded.length, 0, `${page}: a model's preview is folded: ${folded[0]?.getAttribute('href')}`);
    const caveat = [...article.querySelectorAll('details.doc-fold > p')].find(isCaveat);
    assert.equal(caveat, undefined, `${page}: a caveat is folded: "${caveat?.textContent.slice(0, 60)}"`);
    for (const fold of article.querySelectorAll('details.doc-fold')) {
      const n = [...fold.querySelectorAll('a[href]')].filter(own).length;
      if (n) assert.match(norm(fold.querySelector('summary').textContent), new RegExp(`\\b${n} 3D models?\\b`), `${page}: a fold says how many models it holds`);
    }
    previews += [...article.querySelectorAll('a[href]')].filter(own).length;
    const ids = [...article.querySelectorAll('[id]')].map(el => el.id);
    assert.equal(new Set(ids).size, ids.length, `${page}: ids are unique`);
    checked++;
  }
  assert.ok(checked >= 100, `${checked} notes`);
  assert.ok(previews >= 50, `${previews} model links checked`);
});

test('strips agree with a recount of their own table', () => {
  let strips = 0;
  for (const page of pages) {
    const doc = parseHTML(readFileSync(path.join(dist, 'site/pages', page), 'utf8')).document;
    for (const strip of doc.querySelectorAll('figure.doc-strip')) {
      const t = strip.nextElementSibling?.querySelector('table');
      assert.ok(t, `${page}: a strip sits on its table`);
      const head = [...t.querySelectorAll('thead th')].map(th => th.textContent.trim().toLowerCase());
      const col = head.findIndex(h => ['status', 'verdict', 'result', 'state'].includes(h));
      const cells = [...t.querySelectorAll('tbody tr')].map(tr => norm(tr.children[col].textContent).toLowerCase());
      const legend = [...strip.querySelectorAll('.doc-strip-legend li')].map(li => [norm(li.querySelector('b').textContent), norm(li.textContent).replace(/^\d+ /, '')]);
      assert.equal(legend.reduce((n, [c]) => n + Number(c), 0), cells.length, page);
      for (const [n, key] of legend) assert.equal(cells.filter(c => key === 'no status' ? c === '' : c === key || c.startsWith(key + ' ') || c.startsWith(key + ';') || c.startsWith(key + ',') || c.startsWith(key + ' (')).length, Number(n), `${page}: ${key}`);
      assert.match(strip.querySelector('figcaption').textContent, new RegExp(`^${cells.length} rows by ${head[col]}`));
      strips++;
    }
  }
  const requirements = parseHTML(readFileSync(path.join(dist, 'site/pages/docs-requirements-md.html'), 'utf8')).document;
  assert.ok(requirements.querySelector('figure.doc-strip'), 'the requirements table gets its strip');
  assert.ok(strips >= 3);
});

test('a note about one subsystem leads with that subsystem’s render and readings from the status board', () => {
  let live = 0;
  for (const page of pages) {
    const file = sources.get(page);
    if (!file) continue;
    const doc = parseHTML(readFileSync(path.join(dist, 'site/pages', page), 'utf8')).document;
    const card = doc.querySelector('.doc-card .doc-live');
    const panel = status.panels.find(p => p.id === subsystemOf(file) && p.image);
    assert.equal(!!card, !!panel, `${file}: ${subsystemOf(file)}`);
    if (!card) continue;
    assert.equal(card.querySelector('img').getAttribute('src').split('?')[0], panel.image.src);
    const shown = [...card.querySelectorAll('.doc-meters li b')].map(b => b.textContent);
    assert.deepEqual(shown, panel.meters.filter(m => m.bar).slice(0, 3).map(m => m.value), file);
    live++;
  }
  assert.ok(live >= 20);
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

test('the worst notes fit from 320 to 1440 px, and a link into a fold opens it', async () => {
  for (const [width, height] of [[320, 640], [390, 844], [768, 1024], [1440, 1000]]) {
    const context = await browser.newContext({ viewport: { width, height } });
    await acknowledgePrototypeNotice(context);
    const page = await context.newPage();
    for (const name of WORST) {
      await page.goto(`${base}/site/pages/${name}.html`, { waitUntil: 'load' });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), 0, `${name} at ${width}px`);
    }
    await context.close();
  }
  const context = await browser.newContext({ viewport: { width: 1366, height: 800 } });
  await acknowledgePrototypeNotice(context);
  const page = await context.newPage();
  let note, target;
  for (const name of ['docs-turret-plan-md', 'docs-body-next-plan-md', ...WORST]) {
    await page.goto(`${base}/site/pages/${name}.html`, { waitUntil: 'load' });
    target = await page.evaluate(() => [...document.querySelectorAll('details.doc-fold:not([open]) [id]')].find(el => !el.closest('summary'))?.id);
    if (target) { note = name; break; }
  }
  assert.ok(target, 'a heading sits in a fold');
  await page.goto('about:blank');
  await page.goto(`${base}/site/pages/${note}.html#${target}`, { waitUntil: 'load' });
  await page.waitForFunction(id => document.getElementById(id).closest('details').open, target);
  assert.ok(await page.locator(`[id="${target}"]`).isVisible());
  await context.close();
});

test('the Markdown route keeps folded words', async () => {
  const md = await (await fetch(`${base}/site/pages/docs-mechanical-readiness-md.md`)).text();
  assert.match(md, /Branch and release closure/);
  assert.match(md, /No unresolved critical load path, missing retention, impossible insertion/);
  assert.match(md, /```mermaid/);
});
