// Smoke test for the designer's logic (everything except the DOM): every chapter tells its story, offers options
// and can be chosen, the model evaluates every option, and the robot drawing renders.
//   node tools/test_designer.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { evaluate, indexCatalog } from '../designer/model.js';
import { CHAPTERS, visibleChapters } from '../designer/chapters.js';
import { robotSvg } from '../designer/robot-svg.js';

const root = new URL('..', import.meta.url).pathname;
const read = (p) => JSON.parse(readFileSync(root + p, 'utf8'));
const lists = read('catalog/index.json').files.map((f) => read(`catalog/${f}`));
const items = lists.flat();
const catalog = indexCatalog(lists);
const materials = read('catalog/materials.json');
const design = read('designs/default.json');
const clone = (o) => JSON.parse(JSON.stringify(o));

let evaluations = 0;
const r = evaluate(design, catalog, materials);
for (const ch of visibleChapters(design, catalog, r)) {
  assert.equal(typeof ch.story(design, r), 'string', `${ch.id}: story`);
  if (ch.slot) {
    const opts = items.filter(ch.filter);
    assert.ok(opts.length > 0 || ch.optional, `${ch.id}: no catalog options`);
    for (const it of opts) {
      const d = clone(design); d.parts[ch.slot] = it.id;
      const res = evaluate(d, catalog, materials); evaluations++;
      assert.ok(Number.isFinite(res.cost.total_usd) && Number.isFinite(res.mass.total_kg), `${ch.id}/${it.id}: totals`);
    }
  } else if (ch.options) {
    for (const o of ch.options()) { const d = clone(design); o.apply(d); evaluate(d, catalog, materials); evaluations++; }
  }
}
for (const c of [0, 0.5, 1]) assert.match(robotSvg(design, catalog, { crouch: c }), /^<svg/);
for (const p of r.parts) assert.ok(materials[p.material], `material ${p.material} for ${p.id}`);
console.log(`designer ok: ${CHAPTERS.length} chapters, ${evaluations} option evaluations, verdict ${r.verdict}`);
