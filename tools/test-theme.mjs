/** The site's light and dark themes (web/theme.css, web/theme.js): matching token sets, contrast of the key pairs in
 * both themes, the header button and its stored choice, no flash of the wrong theme, the WebGL scenes and diagrams
 * following the page, and no sideways scrolling on a phone. Browser tests use SITE_URL, or serve dist/
 * (run `npm run build`). */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';

const root = path.resolve(import.meta.dirname, '..');
const dist = path.join(root, 'dist');
const css = readFileSync(path.join(root, 'web/theme.css'), 'utf8');
const block = re => Object.fromEntries([...css.match(re)[1].matchAll(/(--gp-[\w-]+):([^;]+)/g)].map(m => [m[1], m[2].trim()]));
const light = block(/^:root\{([^}]*)\}/m);
const darkMedia = block(/@media\(prefers-color-scheme:dark\)\{:root:not\(\[data-theme=light\]\)\{([^}]*)\}\}/);
const darkChosen = block(/^:root\[data-theme=dark\]\{([^}]*)\}/m);
const THEMES = { light, dark: darkChosen };

const rgb = v => {
  if (/^#/.test(v)) { const h = v.slice(1); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); }
  return v.split(/\s+/).map(Number);
};
const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= .03928 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };

test('the light and dark sets name the same tokens, and the two dark blocks are the same', () => {
  assert.ok(Object.keys(light).length > 50, 'the light set');
  assert.deepEqual(Object.keys(darkMedia).sort(), Object.keys(light).sort());
  assert.deepEqual(darkMedia, darkChosen, 'the system dark block and the chosen dark block');
  for (const [name, value] of Object.entries(light)) assert.match(value, /^#[0-9a-f]{6}$|^\d+ \d+ \d+$/, name);
  assert.match(css, /^:root\{[^}]*color-scheme:light\}/m);
  assert.match(css, /^:root\[data-theme=dark\]\{[^}]*color-scheme:dark\}/m);
});

// Text on the surfaces it is used on: 4.5:1 for text, 3:1 for the focus ring.
const SURFACES = ['page', 'page-2', 'card', 'card-2', 'soft'];
const TEXT = ['ink', 'ink-teal', 'text-2', 'muted', 'muted-2', 'link', 'accent-2', 'sky-ink', 'green-ink', 'good', 'warn', 'bad', 'bad-2', 'deep', 'brown'];
const PAIRS = [
  ...SURFACES.flatMap(s => TEXT.map(t => [t, s, 4.5])),
  ...['sage', 'mint', 'peach', 'peach-2', 'peach-3', 'cream', 'yellow', 'blue', 'sky-a'].flatMap(s => ['ink', 'ink-teal', 'text-2', 'link'].map(t => [t, s, 4.5])),
  ['sky-ink', 'sky-a', 4.5], ['sky-ink', 'blue', 4.5], ['good-ink', 'sage', 4.5], ['warn-ink', 'cream', 4.5], ['warn-ink', 'yellow', 4.5],
  ['purple-ink', 'lilac', 4.5], ['brown', 'peach', 4.5], ['deep', 'peach-2', 4.5], ['ink-teal', 'card-2', 4.5],
  ['teal', 'page', 3], ['teal', 'card', 3], ['teal', 'card-2', 3],
];
test('key text and background pairs keep 4.5:1 (3:1 for the focus ring) in both themes', () => {
  const failures = [];
  for (const [theme, set] of Object.entries(THEMES)) {
    for (const [fg, bg, min] of PAIRS) {
      const r = ratio(rgb(set[`--gp-${fg}`]), rgb(set[`--gp-${bg}`]));
      if (r < min) failures.push(`${theme}: ${fg} on ${bg} ${r.toFixed(2)}`);
    }
    // White text on the fills that stay saturated or dark in both themes.
    for (const fill of ['accent-fill', 'ink-fill']) {
      const r = ratio([255, 255, 255], rgb(set[`--gp-${fill}`]));
      if (r < 4.5) failures.push(`${theme}: white on ${fill} ${r.toFixed(2)}`);
    }
  }
  assert.deepEqual(failures, []);
});

test('every page loads web/theme.js and then web/theme.css before its other stylesheets; the script sends nothing', () => {
  const pages = [];
  (function walk(dir) {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p); else if (e.name.endsWith('.html')) pages.push(p);
    }
  })(dist);
  assert.ok(pages.length > 100, 'the built pages');
  for (const file of pages) {
    const head = readFileSync(file, 'utf8').split('</head>')[0];
    const script = head.search(/<script src="\/web\/theme\.js(?:\?v=[^"]*)?"><\/script>/), sheet = head.search(/<link rel="stylesheet" href="\/web\/theme\.css(?:\?v=[^"]*)?">/);
    const firstSheet = head.search(/<link rel="stylesheet"/);
    assert.ok(script >= 0 && sheet > script && sheet === firstSheet, path.relative(dist, file));
    assert.ok(head.search(/<script(?![^>]*src="\/web\/theme\.js)/) === -1 || head.search(/<script(?![^>]*src="\/web\/theme\.js)/) > script, `${path.relative(dist, file)}: theme.js is the first script`);
  }
  const js = readFileSync(path.join(root, 'web/theme.js'), 'utf8');
  assert.doesNotMatch(js, /fetch\(|XMLHttpRequest|sendBeacon|WebSocket|import\(|navigator\.|document\.cookie|https?:/);
  assert.match(js, /localStorage/);
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
async function open(route, { scheme = 'light', width = 1366, height = 900, stored, context } = {}) {
  context ??= await browser.newContext({ viewport: { width, height }, colorScheme: scheme, reducedMotion: 'reduce' });
  await acknowledgePrototypeNotice(context);
  if (stored) await context.addInitScript(value => { if (!sessionStorage.getItem('theme-test')) { localStorage.setItem('gyropup-theme', value); sessionStorage.setItem('theme-test', '1'); } }, stored);
  await context.route('https://cad-agent.gyropup.com/**', r => r.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + route, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  return { context, page, errors };
}
const state = page => page.evaluate(() => ({
  attr: document.documentElement.dataset.theme ?? null,
  scheme: getComputedStyle(document.documentElement).colorScheme,
  page: getComputedStyle(document.documentElement).getPropertyValue('--gp-page').trim(),
  stored: localStorage.getItem('gyropup-theme'),
  pressed: [...document.querySelectorAll('.theme-toggle')].filter(b => b.getClientRects().length).map(b => b.getAttribute('aria-pressed')),
}));
const PAGE = { light: light['--gp-page'], dark: darkChosen['--gp-page'] };

test('the header button switches the theme, keeps the choice across pages, and forgets it when it matches the system', async () => {
  for (const scheme of ['light', 'dark']) {
    const other = scheme === 'light' ? 'dark' : 'light';
    const { context, page, errors } = await open('/', { scheme });
    let s = await state(page);
    assert.deepEqual([s.attr, s.scheme, s.page, s.stored, s.pressed], [null, scheme, PAGE[scheme], null, [String(scheme === 'dark')]], `follows a ${scheme} system`);
    await page.getByRole('button', { name: 'Dark theme' }).click();
    s = await state(page);
    assert.deepEqual([s.attr, s.scheme, s.page, s.stored, s.pressed], [other, other, PAGE[other], other, [String(other === 'dark')]], `pressed on a ${scheme} system`);
    // The next page, drawn by the app bar module, starts in the chosen theme with the button pressed to match.
    await page.goto(base + '/designer/progress.html', { waitUntil: 'load' });
    await page.locator('.appnav .theme-toggle:not([hidden])').waitFor();
    s = await state(page);
    assert.deepEqual([s.attr, s.scheme, s.stored, s.pressed], [other, other, other, [String(other === 'dark')]], 'kept on the next page');
    await page.locator('.appnav .theme-toggle').click();
    s = await state(page);
    assert.deepEqual([s.attr, s.scheme, s.stored], [null, scheme, null], 'pressing back to the system forgets the choice');
    await page.reload({ waitUntil: 'load' });
    assert.equal((await state(page)).scheme, scheme);
    assert.deepEqual(errors, []);
    await context.close();
  }
});

test('no flash: the stored theme is on <html> before any page stylesheet arrives', async () => {
  for (const [route, held] of [['/', '/web/landing.css'], ['/designer/build.html', '/designer/kit/hud.css'], ['/site/', '/web/portal.css']]) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'light' });
    await context.addInitScript(() => localStorage.setItem('gyropup-theme', 'dark'));
    await acknowledgePrototypeNotice(context);
    let release, seen = 0;
    const gate = new Promise(r => { release = r; });
    await context.route(url => new URL(url).pathname === held, async r => { seen++; await gate; await r.continue(); });
    const page = await context.newPage();
    const loaded = page.goto(base + route, { waitUntil: 'load' });
    await page.waitForFunction(() => document.documentElement && document.readyState !== 'uninitialized');
    await page.waitForFunction(() => getComputedStyle(document.documentElement).getPropertyValue('--gp-page').trim() !== '');
    const early = await page.evaluate(() => ({ attr: document.documentElement.dataset.theme, scheme: getComputedStyle(document.documentElement).colorScheme, page: getComputedStyle(document.documentElement).getPropertyValue('--gp-page').trim() }));
    assert.ok(seen >= 1, `${held} was held`);
    assert.deepEqual(early, { attr: 'dark', scheme: 'dark', page: PAGE.dark }, route);
    release(); await loaded; await context.close();
  }
});

// Visible text against what is behind it (each stop of a gradient counts), in each theme.
async function contrastProblems(page) {
  return page.evaluate(() => {
    const parse = c => { const m = c.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]; return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
    const over = (top, bottom) => ({ r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 });
    const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
    const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
    const pageBg = parse(getComputedStyle(document.documentElement).backgroundColor);
    // Every candidate background: the solid colours and gradient stops from the element up to the first opaque one.
    const backgrounds = el => {
      let options = [[]];
      for (let node = el; node; node = node.parentElement) {
        const s = getComputedStyle(node), c = parse(s.backgroundColor);
        const stops = s.backgroundImage.includes('gradient') ? (s.backgroundImage.match(/rgba?\([^)]*\)/g) || []).map(parse).filter(x => x.a > 0.5) : [];
        if (stops.length) { options = options.flatMap(o => stops.map(stop => [...o, { ...stop, a: 1 }])); if (c.a === 0) break; }
        if (c.a > 0) options = options.map(o => [...o, c]);
        if (c.a === 1 || stops.length) break;
      }
      return options.map(o => o.reverse().reduce((under, top) => over(top, under), pageBg.a ? pageBg : { r: 255, g: 255, b: 255, a: 1 }));
    };
    const out = [];
    for (const el of document.body.querySelectorAll('*')) {
      if (!el.checkVisibility?.({ opacityProperty: true, visibilityProperty: true }) || el.closest('svg,canvas,video,.vh,.visually-hidden,[aria-hidden=true],.cad-diagram-view,.skip')) continue;
      if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      const s = getComputedStyle(el), rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2 || parseFloat(s.fontSize) < 1 || s.clip !== 'auto' || s.clipPath.startsWith('inset(50%')) continue;
      const fgRaw = parse(s.color); if (fgRaw.a < 0.05) continue;
      const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.6 && +s.fontWeight >= 700);
      for (const bg of backgrounds(el)) {
        const r = contrast(over(fgRaw, bg), bg);
        if (r < (large ? 3 : 4.5)) { out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} "${el.textContent.trim().slice(0, 28)}" ${r.toFixed(2)}`); break; }
      }
    }
    return [...new Set(out)];
  });
}

const ROUTES = ['/', '/designer/progress.html', '/designer/build.html', '/site/', '/site/pages/docs-body-fuse-board-md.html', '/site/pages/docs-motor-day-md.html'];
test('text keeps its contrast, and nothing scrolls sideways at phone width, in both themes', async () => {
  const problems = [];
  for (const scheme of ['light', 'dark']) {
    for (const [width, height] of [[360, 760], [1366, 900]]) {
      const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme, reducedMotion: 'reduce' });
      for (const route of ROUTES) {
        const { page, errors } = await open(route, { context });
        await page.waitForTimeout(400);
        const s = await state(page);
        if (s.scheme !== scheme) problems.push(`${scheme} ${width} ${route}: color-scheme ${s.scheme}`);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        if (overflow > 0) problems.push(`${scheme} ${width} ${route}: scrolls sideways by ${overflow}px`);
        for (const p of await contrastProblems(page)) problems.push(`${scheme} ${width} ${route}: ${p}`);
        if (errors.length) problems.push(`${scheme} ${width} ${route}: ${errors.join('; ')}`);
        await page.close();
      }
      await context.close();
    }
  }
  assert.deepEqual(problems, []);
});

test('the WebGL scenes and the file viewer follow the theme, and diagrams are drawn in the page theme', async () => {
  // The playground's sky and yard (designer/kit/stage.js, designer/sim.js).
  const { context, page } = await open('/designer/sim.html', { scheme: 'dark', width: 1100, height: 800 });
  await page.waitForFunction(() => window.__sim?.stage);
  const sky = () => page.evaluate(() => window.__sim.stage.scene.background.getHexString());
  const dark = await sky();
  assert.ok(lum(rgb('#' + dark)) < 0.05, `dark sky #${dark}`);
  await page.locator('.appnav .theme-toggle').click();
  await page.waitForFunction(d => window.__sim.stage.scene.background.getHexString() !== d, dark);
  assert.ok(lum(rgb('#' + await sky())) > 0.6, 'light sky after the button');
  await context.close();
  // The original-file viewer: Gyropup's dark palette, back to light with the button.
  const viewer = await open('/designer/kit/file-viewer.html?file=/exports/barrel.stl', { scheme: 'dark', width: 390, height: 844 });
  await viewer.page.waitForFunction(() => window.__fileViewer?.root.dataset.state === 'ready', null, { timeout: 60000 });
  const look = () => viewer.page.evaluate(() => ({ theme: window.__fileViewer.root.dataset.fileTheme, canvas: window.__fileViewer.stage.scene.background.getHexString() }));
  assert.deepEqual(await look(), { theme: 'dark', canvas: '1b3440' });
  await viewer.page.locator('.file-nav .theme-toggle').click();
  assert.deepEqual(await look(), { theme: 'light', canvas: 'd9edf3' });
  assert.ok(await viewer.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await viewer.context.close();
  // A Mermaid diagram on a design note, redrawn when the theme changes.
  const doc = await open('/site/pages/docs-architecture-md.html', { scheme: 'dark' });
  const figure = doc.page.locator('.cad-diagram').first();
  await doc.page.waitForFunction(() => document.querySelector('.cad-diagram')?.dataset.state === 'ready', null, { timeout: 30000 });
  assert.equal(await figure.getAttribute('data-theme'), 'dark');
  const before = await figure.locator('svg').innerHTML();
  await doc.page.locator('.appnav .theme-toggle').click();
  await doc.page.waitForFunction(() => { const f = document.querySelector('.cad-diagram'); return f.dataset.theme === 'light' && f.dataset.state === 'ready'; });
  await doc.page.waitForFunction(b => document.querySelector('.cad-diagram svg')?.innerHTML !== b, before);
  assert.equal(await figure.evaluate(f => getComputedStyle(f).backgroundColor), 'rgb(255, 255, 255)');
  await doc.context.close();
});
