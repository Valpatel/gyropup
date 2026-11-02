/** The design status board (tools/status-board.mjs) against its records, on the landing page and Progress.
 * The evidence tests count each record again here, by their own simple loops, and compare with what the built pages
 * show; a board that drifts from its records fails. Browser tests use SITE_URL, or serve dist/ (run `npm run build`
 * first) on a test-owned listener closed in teardown. */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { parseHTML } from 'linkedom';
import { chromium, webkit } from '@playwright/test';
import { createSiteServer } from './serve-site.mjs';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { collectStatus, createReader, docPage, measuredColumns, renderBoard, sheetCount, shortDate } from './status-board.mjs';
import { ago } from '../web/status-board.js';

const root = path.resolve(import.meta.dirname, '..');
const dist = path.join(root, 'dist');
const json = file => JSON.parse(readFileSync(path.join(root, file), 'utf8'));
const text = el => el.textContent.replace(/\s+/g, ' ').trim();
const page = file => parseHTML(readFileSync(path.join(dist, file), 'utf8')).document;
const progress = page('designer/progress.html'), landing = page('index.html');
const published = JSON.parse(readFileSync(path.join(dist, 'site/status.json'), 'utf8'));
/** The meter `id` of panel `panel` on a page: { value, unit, state, note, widths }. */
const meter = (doc, panel, id) => {
  const el = doc.querySelector(`.sb-panel[data-subsystem="${panel}"] .sb-meter[data-meter="${id}"]`);
  assert.ok(el, `${panel}/${id} is on the page`);
  return { value: text(el.querySelector('.sb-value')), unit: text(el.querySelector('.sb-unit')), state: el.dataset.state, note: text(el.querySelector('.sb-note')),
    widths: [...el.querySelectorAll('.sb-bar i')].map(i => [i.dataset.k, Number(i.getAttribute('style').match(/--w:([\d.]+)%/)[1])]) };
};
const segmentsAddUp = m => assert.ok(Math.abs(m.widths.reduce((n, [, w]) => n + w, 0) - 100) < 0.01 || m.widths.length === 1, JSON.stringify(m.widths));

test('both pages carry the board at their marker; the landing shows three meters a panel and links to the rest', () => {
  for (const doc of [landing, progress]) {
    assert.equal(doc.querySelectorAll('#board').length, 1);
    assert.deepEqual([...doc.querySelectorAll('.sb-panel')].map(p => p.dataset.subsystem), ['leg', 'turret', 'body', 'wheels', 'rig', 'electronics']);
  }
  assert.ok(landing.querySelector('#board').classList.contains('is-compact'));
  assert.equal(landing.querySelector('#loop').nextElementSibling.querySelector('#board') !== null, true, 'the board follows the cad-agent loop');
  for (const panel of landing.querySelectorAll('.sb-panel')) {
    const full = progress.querySelectorAll(`.sb-panel[data-subsystem="${panel.dataset.subsystem}"] .sb-meter`).length;
    if (full > 3) assert.equal(panel.querySelector('.sb-more').getAttribute('href'), `/designer/progress.html#board-${panel.dataset.subsystem}`);
    assert.ok(progress.querySelector(`#board-${panel.dataset.subsystem}`), 'the "more" link lands on its panel');
  }
  assert.ok(progress.querySelector('.portal-jumps a[href="#board"]'));
  assert.equal(progress.querySelector('#latest').nextElementSibling.id, 'board', 'Progress: the board follows the latest work');
  for (const file of ['index.html', 'designer/progress.html']) assert.doesNotMatch(readFileSync(path.join(dist, file), 'utf8'), /<!-- status-board -->/);
});

test('FEA: every study counted against its own verdict, and those under 1.0 shown red', () => {
  for (const [panel, file] of [['leg', 'exports/leg/fea/summary.json'], ['turret', 'exports/turret/fea/summary.json'], ['body', 'exports/body/fea/summary.json']]) {
    const raw = json(file).results, results = Array.isArray(raw) ? raw : Object.values(raw);
    let pass = 0, under1 = 0;
    const failing = [];
    for (const r of results) {
      if (r.ok === true || r.pass === true) { pass++; continue; }
      const sf = r.sf_by_part ?? r.verdict_sf ?? r.safety_factor;
      if (sf < 1) under1++;
      failing.push({ name: `${r.part.replace(/_/g, ' ')} ${r.case}`, sf, target: r.target ?? r.target_sf });
    }
    const m = meter(progress, panel, 'fea');
    // The note names the lowest study under 1.0 when there is one, else the one with the least margin to its target.
    const reds = failing.filter(f => f.sf < 1).sort((a, b) => a.sf - b.sf);
    const named = reds[0] || failing.sort((a, b) => a.sf / a.target - b.sf / b.target)[0];
    if (named) assert.match(m.note, new RegExp(`${reds.length ? 'lowest' : 'least margin'}: ${named.name}, ${Number(named.sf).toFixed(2).replace(/\.?0+$/, '')} against`), panel);
    assert.equal(m.value, `${pass} of ${results.length}`, panel);
    assert.equal(m.state, under1 ? 'fail' : pass < results.length ? 'warn' : 'pass', panel);
    assert.deepEqual(m.widths.map(([k]) => k), ['pass', 'warn', 'fail'].filter((k, i) => [pass, results.length - pass - under1, under1][i] > 0));
    segmentsAddUp(m);
  }
  const all = ['leg', 'turret', 'body'].map(p => json(`exports/${p}/fea/summary.json`).results).flatMap(r => Array.isArray(r) ? r : Object.values(r));
  const strip = [...progress.querySelectorAll('.sb-stat')].find(s => /Strength studies/.test(text(s)));
  assert.equal(text(strip.querySelector('.sb-stat-value')), `${all.filter(r => r.ok ?? r.pass).length} of ${all.length}`);
});

test('turret gates: one pill a verdict file, in the counts', () => {
  const files = readdirSync(path.join(root, 'exports/gates')).filter(f => f.endsWith('.json'));
  const statuses = files.map(f => json(`exports/gates/${f}`).status);
  const pills = [...progress.querySelectorAll('.sb-panel[data-subsystem="turret"] .sb-gates li')];
  assert.equal(pills.length, files.length);
  assert.deepEqual(pills.map(p => p.dataset.status).sort(), statuses.slice().sort());
  const m = meter(progress, 'turret', 'gates');
  assert.equal(m.value, `${statuses.filter(s => s !== 'fail').length} of ${files.length}`);
  assert.equal(m.state, statuses.includes('fail') ? 'fail' : statuses.includes('warn') ? 'warn' : 'pass');
  for (const pill of pills) assert.ok(existsSync(path.join(dist, pill.querySelector('a').getAttribute('href'))), pill.textContent);
});

test('insert joints: each panel counts its assemblies’ joints by verdict, and every joint is on one panel', () => {
  const inventory = json('research/insert-joints/joints.json');
  const owners = { leg: ['leg'], turret: ['turret', 'turret stand'], body: ['body', 'body / turret'], rig: ['leg rig', 'J501 box'] };
  assert.deepEqual([...new Set(inventory.joints.map(j => j.assembly))].sort(), Object.values(owners).flat().sort(), 'a new assembly needs a panel');
  for (const [panel, assemblies] of Object.entries(owners)) {
    const joints = inventory.joints.filter(j => assemblies.includes(j.assembly));
    const m = meter(progress, panel, 'joints');
    assert.equal(m.value, String(joints.length));
    assert.match(m.unit, new RegExp(`${joints.reduce((n, j) => n + j.qty_robot, 0)} inserts`));
    const fix = joints.filter(j => j.verdict === 'fix').length;
    if (fix) { assert.equal(m.state, 'fail'); assert.match(m.note, new RegExp(`^needs a fix · ${fix} to fix`)); }
    const by = k => joints.filter(j => j.verdict === k).length;
    const expected = [['pass', by('ok')], ['note', by('note')], ['unknown', by('check')], ['warn', by('owner')], ['fail', by('fix')]].filter(([, n]) => n);
    assert.deepEqual(m.widths.map(([k, w]) => [k, Math.round(w * 1000)]), expected.map(([k, n]) => [k, Math.round(n / joints.length * 100000)]), panel);
    assert.match(m.note, new RegExp(inventory.status.split(':')[0]));
    segmentsAddUp(m);
  }
  const strip = [...progress.querySelectorAll('.sb-stat')].find(s => /fixes open/.test(text(s)));
  assert.equal(text(strip.querySelector('.sb-stat-value')), String(inventory.findings.filter(f => f.level === 'fix').length));
});

test('mass against D71: the P3 ledger, each leg and the body and head', () => {
  const p3 = json('exports/body/mass.json').P3;
  assert.equal(p3.budget.robot_kg, 37.0); assert.equal(p3.budget.design_mass_kg, 37.5);
  assert.match(readFileSync(path.join(root, 'docs/decisions.yaml'), 'utf8'), /id: D71[\s\S]*?37\.0 kg as-built gate/);
  const strip = progress.querySelector('.sb-mass');
  assert.equal(text(strip.querySelector('.sb-stat-value')), `${p3.total_kg} kg`);
  assert.match(text(strip), /Under D71’s 37\.0 kg as-built gate/);
  const d72 = Number(readFileSync(path.join(root, 'docs/decisions.yaml'), 'utf8').match(/- id: D72\n[\s\S]*?\(([\d.]+) kg\)/)[1]);
  assert.match(text(strip), new RegExp(`ceiling is ${d72.toFixed(2)} kg \\(D72\\)`));
  assert.equal(published.summary.mass.ceiling, d72);
  assert.equal(meter(progress, 'leg', 'mass').value, `${p3.gate.leg_each_kg} kg`);
  assert.equal(meter(progress, 'leg', 'mass').unit, `of ${p3.budget.legs_kg_each} kg`);
  assert.equal(meter(progress, 'body', 'mass').value, `${p3.body_and_head_kg} kg`);
  assert.equal(meter(progress, 'body', 'mass').state, p3.body_and_head_kg <= p3.budget.body_and_head_kg ? 'pass' : 'fail');
});

test('the leg’s pre-print screen, print plans and release flags', () => {
  const screen = json('research/leg-preprint/screen.json');
  const layers = meter(progress, 'leg', 'layers');
  assert.equal(layers.value, `${screen.layers.rows.filter(r => r.ok).length} of ${screen.layers.rows.length}`);
  assert.match(layers.note, new RegExp(`${screen.layers.rows.filter(r => !r.ok && r.layer_sf < 1).length} cases under 1\\.0`));
  const fits = meter(progress, 'leg', 'fits');
  assert.equal(fits.value, `${screen.fits.rows.filter(r => /too tight/.test(r.verdict)).length} of ${screen.fits.rows.length}`);
  for (const [panel, file] of [['leg', 'exports/leg/print-plan.json'], ['body', 'exports/body/print-plan.json'], ['rig', 'exports/rig/print-plan.json']]) {
    const plan = json(file), m = meter(progress, panel, 'print');
    const parts = Object.values(plan.parts);
    assert.equal(m.value, String(parts.length));
    assert.match(m.unit, new RegExp(`^designs?, ${parts.reduce((n, p) => n + p.qty, 0)} prints? · `));
    assert.match(m.note, new RegExp(`fit the ${[].concat(plan.bed_mm).join(' x ')} mm bed`));
    // The leg's release is a flag in its fit job; the body and the rig have no release record at all.
    const released = panel === 'leg' ? json('exports/leg/rs04-fit-job/job.json').qualification.full_leg_print_released : null;
    assert.equal(m.state, released ? 'pass' : 'unknown', panel);
    assert.match(m.note, released === null ? /no print release recorded/ : released ? /released for print/ : /not released for print/);
  }
  assert.equal(meter(progress, 'turret', 'print').value, json('exports/turret/print/print.json').publication.status);
});

test('measurement sheets: blank rows are "not yet measured", a filled row counts', () => {
  assert.deepEqual(sheetCount('slot,cad_nominal_width_mm,actual_mouth_width_mm,notes\n1,4.8,,\n2,5.0,,looks fine\n'), { rows: 2, columns: 1, measured: 0 });
  assert.deepEqual(sheetCount('slot,cad_nominal_width_mm,actual_mouth_width_mm,notes\n1,4.8,4.71,\n2,5.0,,\n'), { rows: 2, columns: 1, measured: 1 });
  assert.deepEqual(sheetCount('sample,torque_nm,failure_mode\ns1,,\ns2,1.5,\n'), { rows: 2, columns: 1, measured: 1 });
  assert.deepEqual(sheetCount('sample,mass_kg,speed_rpm\ns1,1.2,3000\n'), { rows: 1, columns: 2, measured: 1 }, 'kg and rpm are readings');
  assert.deepEqual(sheetCount('id,contact_or_surface_notes,seat_diameter_mm\n1,"rough, pitted",\n'), { rows: 1, columns: 1, measured: 0 }, 'a quoted comma stays in its cell');
  assert.deepEqual(sheetCount('id,calculated_penetration_mm,measurement_uncertainty_mm,gap_mm\n1,0.2,0.05,\n'), { rows: 1, columns: 1, measured: 0 }, 'calculations are not readings');
  // Every sheet the board reads has at least one reading column it recognises, so a new unit is classified on purpose.
  for (const m of published.panels.flatMap(p => p.meters).filter(m => m.id === 'bench' && m.data?.files))
    for (const f of m.data.files) {
      const head = readFileSync(path.join(root, f), 'utf8').split(/\r?\n/)[0].split(',');
      assert.ok(measuredColumns(head).some(Boolean), `${f}: no column the board reads as a measurement`);
    }
  const sheets = ['exports/leg/rs04-fit-job/measurements.csv', ...json('research/leg-preprint/screen.json').coupons.map(c => `research/leg-preprint/sheets/${c.sheet}`)];
  const rows = sheets.reduce((n, f) => n + readFileSync(path.join(root, f), 'utf8').trim().split('\n').length - 1, 0);
  const m = meter(progress, 'leg', 'bench');
  assert.equal(m.value, `0 of ${rows}`);
  assert.equal(m.state, 'unknown');
  assert.deepEqual(m.widths, [['unknown', 100]]);
});

test('wheels, rig and electronics read their records; what is not measured is grey', () => {
  const curb = json('exports/wheels/summary_curb.json').hb10;
  assert.match(readFileSync(path.join(root, 'docs/decisions.yaml'), 'utf8'), /the wheels stay 10 in \(D69\)/, 'the panel follows D69’s 10 in wheel');
  const heights = Object.values(curb.heights);
  assert.equal(meter(progress, 'wheels', 'kerb').value, `${heights.filter(h => h.pass).length} of ${heights.length}`);
  assert.equal(meter(progress, 'wheels', 'bench').state, 'unknown');
  const fit = json('exports/wheels/fit_clashes.json').hb10, clashes = fit.clashes.length + fit.wheel_clashes.length + fit.out_of_range.length;
  assert.equal(meter(progress, 'wheels', 'fit').value, String(clashes));
  assert.equal(meter(progress, 'wheels', 'fit').state, clashes ? 'fail' : 'pass');
  assert.match(meter(progress, 'wheels', 'fit').note, clashes ? /in the fit check/ : /No clash or out-of-range pose/);
  assert.equal(progress.querySelector('.sb-panel[data-subsystem="wheels"] .sb-blurb').textContent, curb.wheel.title, 'the record’s own caveat stays');
  const integrity = json('exports/rig/integrity.json');
  const rigScrews = meter(progress, 'rig', 'integrity');
  assert.equal(rigScrews.value, `${integrity.screws.filter(x => x.ok).length} of ${integrity.screws.length}`);
  assert.match(rigScrews.note, new RegExp(`${integrity.interference.poses} poses swept, ${integrity.interference.hits.length} hit`));
  const body = json('exports/body/integrity.json').summary;
  assert.equal(meter(progress, 'body', 'integrity').value, `${body.joints - body.joints_with_problems.length} of ${body.joints}`);
  assert.match(meter(progress, 'body', 'integrity').unit, new RegExp(`\\(${body.screws} screws\\)`));
  const branches = json('hardware/fuse-board/reports/analysis.json').branches;
  assert.equal(meter(progress, 'electronics', 'copper').value, `${branches.filter(b => b.within_ipc2221_limits === true).length} of ${branches.length}`);
  assert.ok(progress.querySelector('.sb-panel[data-subsystem="wheels"] .sb-noshot'), 'no render is drawn as missing, not borrowed');
  const runs = readdirSync(path.join(root, 'exports/rig/runs')).filter(f => f.endsWith('.json')).map(f => json(`exports/rig/runs/${f}`));
  assert.equal(meter(progress, 'rig', 'bench').value, String(runs.filter(r => r.meta.backend !== 'sim').length));
  const faults = Object.values(json('exports/rig/faults.json').faults);
  assert.equal(meter(progress, 'rig', 'faults').value, `${faults.filter(f => f.ok).length} of ${faults.length}`);
  const drc = readFileSync(path.join(root, 'hardware/fuse-board/reports/drc.rpt'), 'utf8');
  const found = [...drc.matchAll(/Found (\d+) (DRC violations|unconnected pads)/g)].reduce((n, m) => n + Number(m[1]), 0);
  assert.equal(meter(progress, 'electronics', 'drc').value, String(found));
  const pan = json('hardware/carrier-pan-protection/reports/calculations.json');
  assert.equal(meter(progress, 'electronics', 'pan').value, String(pan.unqualified.length));
  assert.equal(meter(progress, 'electronics', 'pan').state, 'unknown');
  for (const u of pan.unqualified) assert.ok(meter(progress, 'electronics', 'pan').note.includes(u.replace(/_/g, ' ')), u);
});

test('each panel’s date is git’s newest commit to its records, and its records cover every source it links', () => {
  const shallow = execFileSync('git', ['rev-parse', '--is-shallow-repository'], { cwd: root }).toString().trim() === 'true';
  assert.equal(published.history, !shallow);
  for (const panel of published.panels) {
    const el = progress.querySelector(`.sb-panel[data-subsystem="${panel.id}"] .sb-when`);
    if (shallow) { assert.equal(el.dataset.changed, ''); continue; }
    const [date, commit] = execFileSync('git', ['log', '-1', '--format=%cI %H', '--', ...panel.records], { cwd: root }).toString().trim().split(' ');
    assert.equal(el.dataset.changed, date, panel.id);
    assert.equal(text(el.querySelector('time')), shortDate(date));
    assert.equal(el.querySelector('a').getAttribute('href'), `https://github.com/Valpatel/gyropup/commit/${commit}`);
    for (const m of panel.meters) if (m.source) {
      const file = m.source.href.slice(1).replace(/\/$/, '');
      assert.ok(panel.records.some(r => file === r || file.startsWith(r + '/')), `${panel.id}/${m.id}: ${file} is not in its records, so its date would miss it`);
    }
  }
});

test('every image, model, document and source link on the board is published', () => {
  for (const doc of [landing, progress]) for (const a of doc.querySelectorAll('#board a[href^="/"], #board img')) {
    const href = (a.getAttribute('href') || a.getAttribute('src')).split('?')[0].split('#')[0];
    const file = path.join(dist, href.endsWith('/') ? href + 'index.html' : href);
    assert.ok(existsSync(file), href);
  }
  for (const panel of published.panels) assert.ok(existsSync(path.join(dist, docPage(panel.docs))), panel.docs);
});

test('a missing record and a shallow history are shown as such, not guessed', () => {
  const real = createReader(root, { git: false });
  const reader = { ...real, exists: p => p !== 'research/leg-preprint/screen.json' && real.exists(p) };
  const status = collectStatus(reader);
  const leg = status.panels.find(p => p.id === 'leg');
  assert.equal(leg.meters.find(m => m.id === 'layers').state, 'unknown');
  assert.ok(status.panels.every(p => p.changed === null));
  const { document } = parseHTML(`<main>${renderBoard(status)}</main>`);
  assert.equal(document.querySelectorAll('.sb-when time').length, 0);
  assert.match(text(document.querySelector('.sb-when')), /Change date not available/);
  assert.match(text(document.querySelector('[data-meter="layers"]')), /No pre-print screen in this revision/);
  // A DRC report the reader cannot parse is grey, never a green "NaN".
  const reworded = collectStatus({ ...real, text: p => p.endsWith('drc.rpt') ? 'Report changed its wording' : real.text(p) });
  assert.equal(reworded.panels.find(p => p.id === 'electronics').meters.find(m => m.id === 'drc').state, 'unknown');
  // The kerb note at the ends of the range.
  const curbs = heights => collectStatus({ ...real, json: p => { const v = real.json(p); return p.endsWith('summary_curb.json') ? { ...v, hb10: { ...v.hb10, heights } } : v; } })
    .panels.find(p => p.id === 'wheels').meters.find(m => m.id === 'kerb').note;
  assert.match(curbs({ 30: { pass: true }, 50: { pass: true } }), /^Clears every height up to 50 mm/);
  assert.match(curbs({ 30: { pass: false }, 50: { pass: false } }), /^Clears none of 30 mm, 50 mm/);
  // The bench summary follows its numbers: one reading turns it from grey to counted.
  const measured = renderBoard({ ...status, summary: { ...status.summary, bench: { rows: 70, measured: 1 } } });
  assert.doesNotMatch(measured, /no sheet has a reading yet/);
  assert.match(measured, /69 rows of the coupon and gauge sheets still blank/);
});

test('"how long ago" labels', () => {
  const now = Date.parse('2026-11-03T12:00:00Z');
  assert.deepEqual(ago('2026-11-03T08:00:00Z', now), { days: 0, text: 'today' });
  assert.deepEqual(ago('2026-11-02T08:00:00Z', now), { days: 1, text: 'yesterday' });
  assert.deepEqual(ago('2026-10-27T08:00:00Z', now), { days: 7, text: '7 days ago' });
  assert.equal(ago('2026-11-04T08:00:00Z', now), null);
  assert.equal(ago('nonsense', now), null);
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
  await page.evaluate(() => document.fonts.ready);
  return { context, page, errors };
}
const scales = page => page.locator('#board .sb-bar i').evaluateAll(bars => bars.map(b => getComputedStyle(b).transform));

test('no overflow at phone, tablet and desktop widths, on both pages', async () => {
  for (const route of ['/', '/designer/progress.html']) for (const [width, height] of [[320, 640], [360, 740], [390, 844], [768, 1024], [1440, 1000]]) {
    const { context, page, errors } = await open(route, { width, height });
    const out = await page.evaluate(() => {
      const board = document.querySelector('#board').getBoundingClientRect();
      const scroller = document.querySelector('#board.is-compact .sb-grid');
      const scrolls = scroller && getComputedStyle(scroller).overflowX === 'auto';
      return { page: document.documentElement.scrollWidth - innerWidth,
        out: [...document.querySelectorAll('#board *')].filter(el => {
          if (scrolls && scroller.contains(el)) return false;
          const r = el.getBoundingClientRect();
          return r.width && !el.closest('.vh') && (r.left < board.left - 1 || r.right > board.right + 1) && el !== scroller;
        }).map(el => el.className || el.tagName) };
    });
    assert.equal(out.page, 0, `${route} overflows at ${width}px`);
    assert.deepEqual(out.out, [], `${route} board content overflows at ${width}px`);
    assert.deepEqual(errors, []);
    await context.close();
  }
});

test('bars fill as the board comes into view; with reduced motion or no script they are drawn full at once', async () => {
  {
    const { context, page } = await open('/designer/progress.html');
    assert.ok(await page.locator('#board.sb-armed').count());
    await page.locator('#board-electronics').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#board-electronics .sb-bar i')).transform === 'none');
    assert.ok(await page.locator('#board-electronics.is-in').count());
    // Records changed within three days pulse; the label says how long ago.
    const recent = await page.locator('.sb-when').evaluateAll(els => els.map(e => [e.classList.contains('is-recent'), e.querySelector('.sb-ago')?.textContent || '']));
    for (const [isRecent, label] of recent) assert.match(label, isRecent ? /^ \((today|yesterday|2 days ago)\)$/ : /^ \(\d+ days ago\)$|^$/);
    await context.close();
  }
  for (const options of [{ reducedMotion: 'reduce' }, { javaScriptEnabled: false }]) {
    const { context, page } = await open('/', options);
    assert.equal(await page.locator('#board.sb-armed').count(), 0);
    assert.ok((await scales(page)).every(t => t === 'none'), JSON.stringify(options));
    const motion = await page.evaluate(() => [...document.querySelectorAll('#board *')].map(e => getComputedStyle(e).animationName).filter(n => n !== 'none'));
    if (options.reducedMotion) assert.deepEqual(motion, []);
    await context.close();
  }
});

test('text on the board has at least 4.5:1 contrast against its background', async () => {
  for (const route of ['/', '/designer/progress.html']) {
    const { context, page } = await open(route, { reducedMotion: 'reduce' });
    const failures = await page.evaluate(() => {
      const parse = c => { const m = c.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]; return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
      const over = (top, bottom) => ({ r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 });
      // A gradient background counts by its darkest stop's nearest solid colour: the strip's navy.
      const background = el => {
        const layers = [];
        for (let node = el; node; node = node.parentElement) {
          const s = getComputedStyle(node);
          if (s.backgroundImage.includes('gradient') && node.classList.contains('sb-stat')) { layers.push({ r: 19, g: 42, b: 52, a: 1 }); break; }
          const c = parse(s.backgroundColor);
          if (c.a > 0) layers.push(c);
          if (c.a === 1) break;
        }
        return layers.reverse().reduce((under, top) => over(top, under), { r: 255, g: 255, b: 255, a: 1 });
      };
      const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
      const out = [];
      for (const el of document.querySelectorAll('#board *')) {
        if (el.closest('.vh') || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
        const bg = background(el), fg = over(parse(getComputedStyle(el).color), bg);
        const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
        const ratio = (a + .05) / (b + .05);
        if (ratio < 4.5) out.push(`${el.tagName}.${el.className} "${el.textContent.trim().slice(0, 30)}" ${ratio.toFixed(2)}`);
      }
      return out;
    });
    assert.deepEqual(failures, [], route);
    await context.close();
  }
});

test('Markdown routes keep the board’s readings and drop its drawn bars', async () => {
  for (const route of ['/index.md', '/designer/progress.md']) {
    const md = await (await fetch(base + route)).text();
    const section = md.slice(md.indexOf('FROM THE RECORDS, AT BUILD'), md.indexOf('a green bar is not physical proof'));
    assert.ok(section.length > 500, route);
    assert.match(section, /Strength studies \*\*\d+ of \d+\*\* meet their own target/);
    if (route === '/index.md') assert.match(section, /\[4 more on Progress →\]\([^)]*\/designer\/progress\.html#board-leg\)/);
    else assert.match(section, /Bench coupons \*\*0 of \d+\*\* rows measured\s+not yet measured · No row filled in yet: the RS-04 seat coupon/);
    assert.doesNotMatch(section, /Meets its target\n/, 'the colour key is drawn, not read');
  }
});
