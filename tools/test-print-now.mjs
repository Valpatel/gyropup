// The Build page's "Print these now" card (designer/print-now.js) against the real print list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { parseCsv, steps, mountPrintNow } from '../designer/print-now.js';

const csv = fs.readFileSync(new URL('../exports/motor-day/prints.csv', import.meta.url), 'utf8');

test('quoted CSV fields keep their commas and quotes', () => {
  const rows = parseCsv('a,b\n1,"x, ""y"""\n');
  assert.deepEqual(rows, [{ a: '1', b: 'x, "y"' }]);
});

test('every print step from prints.csv, in order, with the plan\'s totals', () => {
  const s = steps(parseCsv(csv));
  assert.deepEqual(s.map((x) => x.order), [...s.keys()].map((i) => i + 1), 'orders run 1..n with no gaps');
  const rows = parseCsv(csv);
  const minutes = rows.reduce((a, r) => a + Number(r.qty) * Number(r.minutes_each), 0);
  assert.ok(Math.abs(s.reduce((a, x) => a + x.minutes, 0) - minutes) < 1e-6, 'no row dropped');
  assert.equal(s[0].items[0].key, 'coupon_frame_ring_nom', 'the case-fit coupon prints first');
  const sumBy = (f) => rows.filter(f).reduce((a, r) => a + Number(r.qty) * Number(r.grams_each), 0);
  assert.ok(Math.abs(s.reduce((a, x) => a + x.grams, 0) - sumBy((r) => r.recipe !== 'tpu')) < 1e-6, 'PLA grams');
  assert.ok(Math.abs(s.reduce((a, x) => a + x.tpu, 0) - sumBy((r) => r.recipe === 'tpu')) < 1e-6, 'TPU grams');
  assert.deepEqual(s.filter((x) => x.fit).map((x) => x.order), [...new Set(rows.filter((r) => r.phase === '0').map((r) => Number(r.order)))],
    'the fit-check tag follows phase 0, not the position');
});

test('the card\'s totals are the ones docs/motor-day.md publishes', async () => {
  const doc = fs.readFileSync(new URL('../docs/motor-day.md', import.meta.url), 'utf8');
  const host = { innerHTML: '', dataset: {}, id: 'print-now' };
  await mountPrintNow(host, async () => ({ ok: true, text: async () => csv }));
  const [, h, kg, tpu] = /<li class="pn-tot">.*?class="pn-t">([\d.]+) h<.*?class="pn-g">([\d.]+) kg PLA(?: \+ (\d+) g TPU)?/.exec(host.innerHTML) || [];
  assert.ok(h && kg, 'the card shows a total');
  for (const v of [`${h} h`, `${kg} kg`]) assert.ok(doc.includes(v), `docs/motor-day.md states ${v}`);
  if (tpu) assert.ok(doc.includes(`${tpu} g`), `docs/motor-day.md states ${tpu} g TPU`);
});

test('a row with an empty or non-positive order is not a step', () => {
  const s = steps(parseCsv('order,key,qty,phase,minutes_each,grams_each,file\n,stray,1,0,10,1,a.stl\n0,zero,1,0,10,1,b.stl\n1,real,1,1b,60,5,c.stl\n'));
  assert.deepEqual(s.map((x) => x.items[0].key), ['real']);
  assert.equal(s[0].fit, false);
});

test('the card renders a row per step and survives a failed fetch', async () => {
  const host = { innerHTML: '', dataset: {} };
  await mountPrintNow(host, async () => ({ ok: true, text: async () => csv }));
  const n = steps(parseCsv(csv)).length;
  assert.equal((host.innerHTML.match(/<li data-order=/g) || []).length, n);
  assert.match(host.innerHTML, /motor-day-package\.zip/);
  for (const fail of [async () => ({ ok: false, status: 404 }), async () => { throw new TypeError('network'); }]) {
    const bad = { innerHTML: '', dataset: {} };
    await mountPrintNow(bad, fail);
    assert.match(bad.innerHTML, /docs-motor-day-md\.html/);
    assert.match(bad.innerHTML, /motor-day-package\.zip/);
    assert.doesNotMatch(bad.innerHTML, /<ol/);
    assert.doesNotMatch(bad.innerHTML, /Print in this order/, 'no order sentence without a list');
    assert.equal(bad.dataset.ready, '1');
  }
});
