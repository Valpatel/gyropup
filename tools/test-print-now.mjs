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
});

test('the card renders a row per step and survives a failed fetch', async () => {
  const host = { innerHTML: '', dataset: {} };
  await mountPrintNow(host, async () => ({ ok: true, text: async () => csv }));
  const n = steps(parseCsv(csv)).length;
  assert.equal((host.innerHTML.match(/<li data-order=/g) || []).length, n);
  assert.match(host.innerHTML, /motor-day-package\.zip/);
  const bad = { innerHTML: '', dataset: {} };
  await mountPrintNow(bad, async () => ({ ok: false, status: 404 }));
  assert.match(bad.innerHTML, /docs-motor-day-md\.html/);
  assert.doesNotMatch(bad.innerHTML, /<ol/);
});
