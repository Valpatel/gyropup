/** Build first. SITE_URL optionally checks the deployed routes instead of a local server. */
import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';
import { readFile, mkdir, mkdtemp, cp, writeFile, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { parseHTML } from 'linkedom';
import { marked } from 'marked';
import { htmlToMarkdown, renderPortal } from './site-markdown.mjs';

const root = path.resolve(import.meta.dirname, '..');
const out = path.join(root, 'dist');
const read = file => readFile(path.join(out, file), 'utf8');
const sha = value => createHash('sha256').update(value).digest('hex');
const { pages } = JSON.parse(await read('markdown-pages.json'));
let server;
let base = process.env.SITE_URL?.replace(/\/$/, '');
before(async () => {
  if (base) return;
  server = spawn(process.execPath, ['tools/serve-site.mjs'], { cwd: root, env: { ...process.env, PORT: '0' }, stdio: ['ignore', 'pipe', 'inherit'] });
  const timeout = setTimeout(() => server.kill(), 10_000);
  try {
    const [output] = await once(server.stdout, 'data');
    base = output.toString().match(/http:\/\/127\.0\.0\.1:\d+/)?.[0];
    assert.ok(base, 'local server must announce its listening address');
  } finally { clearTimeout(timeout); }
});
after(async () => {
  if (server && server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
});

test('every public page and agent counterpart includes the research warning', async () => {
  assert.ok(!pages.some(entry => entry.html === '/web/prototype-notice.html'), 'the injection template is not a standalone page');
  for (const entry of pages) {
    const { document } = parseHTML(await read(entry.html));
    assert.equal(document.querySelectorAll('#prototype-notice-dialog').length, 1, entry.html);
    assert.equal(document.querySelectorAll('#prototype-notice-footer').length, 1, entry.html);
    assert.ok(document.querySelector('script[src^="/web/prototype-notice.js"]'), entry.html);
    const text = await read(entry.markdown);
    assert.match(text, /will not be offered for sale/, entry.markdown);
    assert.match(text, /research purposes only/, entry.markdown);
  }
});

test('every generated HTML page advertises a current Markdown counterpart', async () => {
  assert.ok(pages.length > 100);
  const discovery = await read('llms.txt');
  for (const entry of pages) {
    const html = await read(entry.html);
    const md = await read(entry.markdown);
    assert.equal(sha(html), entry.htmlSha256, `${entry.html} changed after Markdown generation`);
    assert.equal(sha(md), entry.markdownSha256, `${entry.markdown} changed after generation`);
    const { document } = parseHTML(html);
    assert.equal(document.querySelector('link[rel="alternate"][type="text/markdown"]')?.getAttribute('href'), entry.markdown);
    assert.ok(discovery.includes('https://gyropup.com' + entry.markdown), entry.markdown);
    assert.equal(md, htmlToMarkdown(await renderPortal(html, entry.html.slice(1), out), entry.html.slice(1)), entry.markdown);
    assert.ok(md.length > 100 && !md.includes('<script'), entry.markdown);
  }
  assert.ok(!discovery.includes('handoff.md'));
  assert.ok(!pages.some(p => /(?:AGENTS|CLAUDE|\.agents)/.test(p.markdown)));
  assert.match(await read('_headers'), /\/\*\.md\n  Content-Type: text\/markdown; charset=utf-8/);
});

test('progress and build expose their data, tables, prices, and original downloads', async () => {
  const progress = JSON.parse(await read('docs/progress.json'));
  const md = await read('designer/progress.md');
  for (const status of progress.status) {
    assert.ok(md.includes(status.title), status.title);
    assert.ok(md.includes(status.value), status.value);
  }
  assert.ok(md.includes(progress.updated));
  assert.ok(md.includes(progress.log.at(-1).title));
  assert.match(md, /\|.*scenario/i);
  assert.match(md, /Watch the deformation animation/);
  assert.match(md, /static load scaling, not elapsed physical time/i);
  assert.match(md, /does not validate the 100 lb design target/);
  const build = await read('designer/build.md');
  assert.ok(!build.includes('Reading the parts lists'));
  const { document } = parseHTML(await renderPortal(await read('designer/build.html'), 'designer/build.html', out));
  const total = document.querySelector('#grand-usd').textContent.trim();
  assert.ok(build.includes(total), 'order total must match the browser renderer');
  assert.match(build, /\|.*Supplier part number/i);
  const tables = marked.lexer(build).filter(token => token.type === 'table');
  const orders = tables.find(table => table.header.some(cell => cell.text === 'Supplier part number'));
  assert.ok(orders?.rows.length > 1, 'order records remain parseable Markdown table rows');
  assert.equal(orders.header.length, 7, 'all order columns remain associated with their values');
  assert.ok(!tables.some(table => table.rows.some(row => row.length !== table.header.length)));
  assert.match(build, /https:\/\/gyropup.com\/exports\/leg\/bom.json/);
  assert.match(build, /https:\/\/gyropup.com\/exports\/[^)]+\.stl/);
  assert.match(build, /Preview 3D/);
  assert.match(build, /file-viewer\.html\?file=/);
});

test('a changed published status changes Markdown; local unpublished data is never read', async () => {
  const fixture = await mkdtemp(path.join(os.tmpdir(), 'gyropup-markdown-'));
  try {
    await mkdir(path.join(fixture, 'designer'), { recursive: true });
    await mkdir(path.join(fixture, 'docs'), { recursive: true });
    await mkdir(path.join(fixture,'site'));await writeFile(path.join(fixture,'site/models.json'),JSON.stringify({files:[]}));
    await cp(path.join(out, 'designer/progress.js'), path.join(fixture, 'designer/progress.js'));
    await mkdir(path.join(fixture,'designer/kit'),{recursive:true});
    await cp(path.join(out,'designer/kit/portal-data.js'),path.join(fixture,'designer/kit/portal-data.js'));
    await cp(path.join(out,'designer/kit/study-media.js'),path.join(fixture,'designer/kit/study-media.js'));
    const source = await read('designer/progress.html');
    const data = { updated: 'fixture-revision', status: [{ title: 'Published sentinel', value: 'Changed current data', note: 'Only this bundle is visible.' }], log: [] };
    await writeFile(path.join(fixture, 'docs/progress.json'), JSON.stringify(data));
    const markdown = htmlToMarkdown(await renderPortal(source, 'designer/progress.html', fixture), 'designer/progress.html');
    assert.ok(markdown.includes('Published sentinel'));
    assert.ok(markdown.includes('Changed current data'));
    assert.ok(!markdown.includes('bench tests next'), 'must not fall back to the checkout data');
    await mkdir(path.join(fixture,'exports/leg'),{recursive:true});
    await writeFile(path.join(fixture,'exports/leg/leg.json'),'<html>Not a report</html>');
    await assert.rejects(renderPortal(source,'designer/progress.html',fixture),/Incomplete Markdown data snapshot/);
    await rm(path.join(fixture,'exports/leg/leg.json'));
    // Missing required status must fail the build instead of publishing a blank portal.
    await rm(path.join(fixture, 'docs/progress.json'));
    await assert.rejects(renderPortal(source, 'designer/progress.html', fixture), /Empty Markdown data snapshot/);
  } finally { await rm(fixture, { recursive: true, force: true }); }
});

test('Markdown routes have the right MIME types and preserve HTML, downloads, HEAD, and real 404s', async () => {
  for (const route of ['/index.md', '/designer/progress.md', '/designer/build.md', '/designer/sim.md', '/site/index.md', '/site/pages/docs-leg-prototype-plan-md.md']) {
    const response = await fetch(base + route);
    assert.equal(response.status, 200, route);
    assert.match(response.headers.get('content-type'), /^text\/markdown\b/, route);
    assert.ok((await response.text()).includes('[HTML view]'), route);
    const head = await fetch(base + route, { method: 'HEAD' });
    assert.equal(head.status, 200, route);
    assert.equal(await head.text(), '');
  }
  const llms = await fetch(base + '/llms.txt');
  assert.match(llms.headers.get('content-type'), /^text\/plain\b/);
  assert.ok((await llms.text()).includes('/designer/progress.md'));
  const html = await fetch(base + '/');
  assert.match(html.headers.get('content-type'), /^text\/html\b/);
  const download = await fetch(base + '/exports/leg/leg_stand.step');
  assert.equal(download.status, 200);
  assert.ok((await download.text()).startsWith('ISO-10303-21;'));
  for (const route of ['/not-a-gyropup-page.md', '/not-a-gyropup-file.json']) {
    const response = await fetch(base + route, { headers: { Accept: 'text/markdown' } });
    assert.equal(response.status, 404, route);
  }
});
