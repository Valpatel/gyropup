/** Real browser cache across releases; no routing, interception, or cache disabling. */
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { versionSiteAssets } from './site-cache.mjs';

const root = await mkdtemp(path.join(os.tmpdir(), 'gyropup-cache-'));
const requests = [];
let legacyHeaders = true;
const server = createSiteServer(root);
server.prependListener('request', (req, res) => {
  const original = res.writeHead;
  res.writeHead = function(status, headers) {
    if (legacyHeaders && !req.url.startsWith('/index.html')) headers['Cache-Control'] = 'public, max-age=14400, must-revalidate';
    requests.push({url:req.url, conditional:req.headers['if-none-match'], status});
    return original.call(this, status, headers);
  };
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = process.env.PLAYWRIGHT_BROWSER === 'webkit'
  ? await webkit.launch() : await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome', headless:true});
try {
  // Build validation catches the exact failure that blanks a page when a new
  // relative dependency exists locally but was omitted from git ls-files.
  for (const source of [
    "import './missing.js';",
    "import { createControls } from './missing.js';",
    "export { createControls } from './missing.js';",
    "const controls = await import('./missing.js');",
  ]) {
    await writeFile(path.join(root, 'entry.js'), source);
    await assert.rejects(versionSiteAssets(root), /Missing relative module: entry\.js imports \.\/missing\.js/);
  }
  await writeFile(path.join(root, 'present.js'), 'export const value = 1;');
  await writeFile(path.join(root, 'entry.js'), [
    "import './present.js?v=old#fixture';",
    "import { value } from 'an-import-map-alias';",
    "import { remote } from 'https://example.com/remote.js';",
    "// import './comment-only.js';",
    "/* export { example } from './comment-only.js'; */",
    'const example = "import(\'./string-only.js\')";',
    "const url = './computed.js'; const computed = import(url);",
  ].join('\n'));
  await versionSiteAssets(root); // Queries, comments, strings, aliases and remote URLs are supported.
  await rm(path.join(root, 'present.js'));
  async function release(name, versioned) {
    const files = {
      'index.html': '<!doctype html><html><head><link rel="stylesheet" href="./style.css"><script type="importmap">{"imports":{"three":"./vendor/core.js","three/addons/":"./vendor/addons/"}}</script></head><body><p>Cache fixture</p><script type="module" src="./entry.js"></script></body></html>',
      'entry.js': `import {deep} from './nested.js'; import {core} from 'three';
        const {lazy} = await import('./lazy.js'); const {addon} = await import('three/addons/example.js');
        const link = document.createElement('link'); link.rel='stylesheet';
        const css = new URL('./runtime.css', import.meta.url); css.search = new URL(import.meta.url).search;
        link.href=css.href; document.head.append(link); window.result={deep,core,lazy,addon};`,
      'nested.js': "export {deep} from './deep.js';",
      'deep.js': `export const deep=${JSON.stringify(name)};`,
      'lazy.js': `export const lazy=${JSON.stringify(name)};`,
      'vendor/core.js': `export const core=${JSON.stringify(name)};`,
      'vendor/addons/example.js': `export const addon=${JSON.stringify(name)};`,
      'style.css': `@import url('./nested.css'); body{--entry:${name}}`,
      'nested.css': `body{--nested:${name}}`,
      'runtime.css': `body{--runtime:${name}}`,
      'data.json': JSON.stringify({release:name}),
    };
    for (const [file, data] of Object.entries(files)) {
      await mkdir(path.dirname(path.join(root,file)), {recursive:true});
      await writeFile(path.join(root,file),data);
    }
    return versioned ? versionSiteAssets(root) : null;
  }
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function state() {
    await page.waitForFunction(() => window.result && getComputedStyle(document.body).getPropertyValue('--runtime'));
    return page.evaluate(() => ({...window.result, entry:getComputedStyle(document.body).getPropertyValue('--entry').trim(), nested:getComputedStyle(document.body).getPropertyValue('--nested').trim(), runtime:getComputedStyle(document.body).getPropertyValue('--runtime').trim()}));
  }
  const expected = value => Object.fromEntries(['deep','core','lazy','addon','entry','nested','runtime'].map(k=>[k,value]));
  await release('old',false);
  await page.goto(base+'/index.html');
  assert.deepEqual(await state(),expected('old'));
  // Seed JSON as an old public asset too, then prove the static-data fetch option.
  assert.equal(await page.evaluate(async()=> (await (await fetch('/data.json')).json()).release), 'old');
  legacyHeaders=false;
  await release('new',false);
  await page.reload();
  assert.deepEqual(await state(),expected('old'), 'headers alone cannot evict old fresh assets');
  const firstKey = await release('new',true);
  await page.reload();
  assert.deepEqual(await state(),expected('new'), 'ordinary reload migrates the entire module/CSS graph');
  assert.equal(await page.evaluate(async()=> (await (await fetch('/data.json',{cache:'no-cache'})).json()).release), 'new');
  const secondKey = await release('edited',true);
  assert.notEqual(firstKey,secondKey,'editing bytes without a git commit changes the key');
  await page.reload();
  assert.deepEqual(await state(),expected('edited'));
  const repeatKey = await release('edited',true);
  assert.equal(secondKey,repeatKey,'identical build inputs have a stable key');
  requests.length=0;
  await page.reload();
  assert.deepEqual(await state(),expected('edited'));
  assert.ok(requests.some(r=>r.url.includes('deep.js') && r.conditional && r.status===304),'unchanged nested modules revalidate with HTTP 304');
  assert.ok(requests.some(r=>r.url.includes('nested.css') && r.conditional && r.status===304),'unchanged nested CSS revalidates with HTTP 304');
  assert.deepEqual(errors,[]);
  const response = await fetch(base+'/deep.js');
  assert.match(response.headers.get('cache-control'), /\bno-cache\b/);
  assert.match(response.headers.get('cache-control'), /max-age=0/);
  console.log(JSON.stringify({browser:process.env.PLAYWRIGHT_BROWSER || 'chromium',migration:'old → new → edited',firstKey,secondKey,revalidations:requests.filter(r=>r.status===304).map(r=>r.url),errors},null,2));
  await context.close();
  // Check the actual generated Cloudflare config too, not just the local server.
  const headers = await readFile(new URL('../dist/_headers',import.meta.url),'utf8');
  assert.match(headers,/\/\*\n  Cache-Control: public, no-cache, max-age=0, must-revalidate\n/);
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
  await rm(root,{recursive:true,force:true});
}
