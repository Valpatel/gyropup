// Offline provenance/identity checks. Availability and visual inspections have dated evidence in the report.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
const root = fileURLToPath(new URL('../', import.meta.url));
const read = name => JSON.parse(readFileSync(new URL('../' + name, import.meta.url), 'utf8'));
const images = read('catalog/images.json');
const report = read('catalog/vendor-media-verification.json');

test('all current made-to-order and first-frame thumbnails retain exact geometry/output receipts', () => {
  const run = spawnSync('python3', ['tools/part-media-generation.py', '--check'], { cwd: root, encoding: 'utf8' });
  assert.equal(run.status, 0, run.stdout + run.stderr);
});

test('only source-linked, visually inspected, decoded vendor images are promoted for public display', () => {
  for (const [key, record] of Object.entries(report.records)) {
    const image = images[key];
    assert.equal(image?.verification?.status, record.status, key + ' status drift');
    if (record.status !== 'verified') {
      assert.equal(record.usable, false, key);
      continue;
    }
    assert.equal(record.usable, true, key);
    assert.equal(record.http_status, 200, key);
    assert.equal(record.source_http_status, 200, key);
    assert.equal(record.image_link_in_source, true, key);
    assert.match(record.content_type, /^image\//, key);
    assert.ok(record.dimensions.every(n => Number.isInteger(n) && n >= 32), key);
    assert.match(record.sha256, /^[0-9a-f]{64}$/, key);
    assert.ok(record.visual_inspection?.length > 20 && record.match_evidence?.length > 20, key);
    assert.equal(image.path, null, key + ' must not depend on ignored vendor files');
    assert.equal(image.image_url, record.image_url, key);
    assert.equal(image.source_url, record.source_url, key);
    assert.equal(image.verification.image_sha256, record.sha256, key);
    assert.equal(new URL(image.image_url).protocol, 'https:', key + ' must not cause mixed content');
    assert.equal(new URL(image.source_url).protocol, 'https:', key);
    if (record.catalog_scope) {
      const scoped = read(record.catalog_scope.file).find(p => p.key === record.catalog_scope.key);
      assert.equal(scoped?.vendor, record.catalog_scope.vendor, key);
      assert.equal(scoped?.model, record.catalog_scope.model, key);
      assert.deepEqual(image.catalog_scope, record.catalog_scope, key);
    }
  }
});

test('all used filament variants use genuine spool evidence and gyroid shares the TPU material', () => {
  const parts = read('exports/body/print-plan.json').parts;
  for (const material of new Set(Object.values(parts).map(p => p.material))) {
    assert.equal(images[material].verification.status, 'verified', material);
    assert.match(report.records[material].match_evidence, /spool/i, material);
  }
  assert.equal(images['tpu95-gyroid'].alias_of, 'tpu95');
  assert.equal(images['tpu95-gyroid'].image_url, images.tpu95.image_url);
});
