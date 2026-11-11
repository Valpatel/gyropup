import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { PUBLIC_DESIGNS, LEGACY_DESIGN, LEGACY_UNAVAILABLE, resolvePublicDesign } from '../../../software/site/designer/sim_designs.js';

test('public availability keeps current robot and turret, disables v1', () => {
  assert.deepEqual(PUBLIC_DESIGNS.filter(d => d.available).map(d => d.file), ['v2', 'turret-box']);
  assert.equal(PUBLIC_DESIGNS.find(d => d.file === LEGACY_DESIGN).available, false);
  assert.match(LEGACY_UNAVAILABLE, /v1.*unavailable.*current Gyropup/);
});
test('links and restored values cannot opt into the retired loader', () => {
  for (const value of [LEGACY_DESIGN, '@designer', 'v1', '../designs/default.json', '', null, undefined]) {
    assert.equal(resolvePublicDesign(value), 'v2', String(value));
  }
  for (const value of ['v2', 'turret-box']) assert.equal(resolvePublicDesign(value), value);
});
test('v1 design and procedural research source remain available', async () => {
  const design = JSON.parse(await readFile(new URL('../../../hardware/designs/default.json', import.meta.url)));
  assert.ok(design.name);
  const source = await readFile(new URL('../../../software/site/designer/robot3d.js', import.meta.url), 'utf8');
  assert.match(source, /export function buildRobot/);
});
