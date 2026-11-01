// npm run test:privacy (after npm run build): no absolute home paths, fleet host names, private or tailnet addresses or
// private repository names in the tracked files or the built site, beyond the shrink-only ratchet (issue #141).
// Samples below are assembled at run time, so this file holds none of the strings it looks for.
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import {
  ALLOWED, EXEMPT, ROOT, RATCHET, baseRatchet, growthProblems, isExempt, judge, loadRatchet, parseRatchet, privateNames,
  ratchetProblems, scanDist, scanText, scanTracked, trackedFiles,
} from './privacy-guard.mjs';

const j = (...parts) => parts.join('');
const kinds = text => scanText(text).map(f => f.kind);
const names = { names: privateNames() };

test('each kind of private string is caught, without reporting the string', () => {
  const cases = {
    'home-path': [j('mesh: "/', 'home/', 'alice/Code/x.stl"'), j('cd /', 'Users/bob/src'), j('file:///', 'home/carol/a'),
      j('cd /', 'home/', 'frank'), j('/var', '/home/', 'gina/x'), j('/tmp/x/-', 'home-', 'hank-Code/y'),
      j('C:\\', 'Users\\', 'dave\\x'), j('"C:\\\\', 'Users\\\\', 'erin\\\\x"')],
    'fleet-host': [j('run on gb10', '-99'), j('THOR', '-42 run'), j('ssh jetson', '-3'), j('ssh rtx', '1234', ' hostname')],
    'private-ip': [j('10.', '1.2.3'), j('http://192', '.168.0.9:8081'), j('172', '.20.1.1'), j('100', '.100.1.2'),
      j('fd7a:115c', ':a1e0::1')],
    'tailnet-name': [j('robot.', 'example-net', '.ts.net'), j('https://', 'example-net', '.ts.net/'),
      j('*.', 'example-net', '.ts.net')],
    'private-repo': [j('github.com/Valpatel/', 'some-private-tool'), j('see mvalancy/', 'notes')],
  };
  for (const [kind, samples] of Object.entries(cases)) {
    for (const sample of samples) {
      const found = scanText(`intro\n${sample}\n`);
      assert.deepEqual(found.map(f => f.kind), [kind], `${kind}: sample ${samples.indexOf(sample)}`);
      assert.equal(found[0].line, 2);
      assert.deepEqual(Object.keys(found[0]).sort(), ['index', 'kind', 'line']);
    }
  }
});

test('public look-alikes pass', () => {
  for (const ok of [
    'https://example.com/home/alice/page', 'https://www.example.com/media/catalog/x.png', 'cd ~/Code/gyropup', '$HOME/.config',
    'run it on a GB10', 'an RTX 4090 and an RTX4090 GPU', 'AGX Thor', 'orin-32gb', 'Jetson-AGX', 'manual 10.2.3.3.9',
    'v10.1.2.3', '192.0.2.20', '8.8.8.8', '127.0.0.1', '172.32.0.1', '100.128.0.1', '100.64/10 and *.ts.net',
    'github.com/Valpatel/gyropup/issues/1', 'Valpatel/cad-agent.', 'mvalancy/moxie-robot-saver', 'valpatel.com/about',
  ]) assert.deepEqual(kinds(ok), [], ok);
});

test('extra private names come from the environment only', () => {
  const name = j('secret', '-tool');
  assert.deepEqual(scanText(`uses ${name} daily`, { names: [name] }).map(f => f.kind), ['private-repo']);
  assert.deepEqual(scanText(`uses ${name}s and pre-${name}`, { names: [name] }), []);
  assert.deepEqual(privateNames({ GYROPUP_PRIVATE_NAMES: 'a, b\nc' }).map(s => s.trim()), ['a', 'b', 'c']);
});

test('exemptions and allowances are narrow and still needed', () => {
  const tracked = trackedFiles();
  for (const e of EXEMPT) {
    assert.ok(e.reason.length > 40, e.glob);
    const files = tracked.filter(isExempt);
    assert.ok(files.length, `${e.glob} matches no tracked file`);
    for (const f of files) assert.ok(scanText(readFileSync(path.join(ROOT, f), 'utf8')).length, `${f} no longer needs its exemption`);
  }
  assert.ok(isExempt('designer/kit/vendor/occt-import-js/occt-import-js.js'));
  assert.ok(!isExempt('designer/kit/vendor/mermaid/mermaid.min.js'));
  assert.ok(!isExempt('designer/kit/vendor/occt-import-js/other.js'));
  assert.ok(!isExempt('designer/kit/vendor/file-viewer-sources.json'));
  assert.ok(!isExempt('designer/kit/vendor-notes.js'));
  const found = scanTracked(ROOT, names);
  for (const a of ALLOWED) {
    assert.ok(a.reason.length > 40);
    const live = a.paths.filter(p => tracked.includes(p));
    assert.ok(live.length, `allowed entry for ${a.paths[0]} names no tracked file`);
    for (const p of live) assert.ok(found[p], `${p} no longer needs its allowance`);
  }
});

test('the ratchet parses one line per file', () => {
  const r = parseRatchet('# note\n\na/b.json | home-path=2, fleet-host=1 | why it waits | with a bar\n');
  assert.deepEqual(r.entries, [{ path: 'a/b.json', line: 3, reason: 'why it waits | with a bar',
    counts: { 'home-path': 2, 'fleet-host': 1 } }]);
  assert.match(ratchetProblems(parseRatchet('a | home-path=x | short')).join('\n'), /reason[\s\S]*positive count/);
  assert.match(ratchetProblems(parseRatchet('a | nope=1 | a reason long enough to pass')).join('\n'), /unknown kind/);
});

test('the ratchet is exact: fixing a file without updating it fails, and so does a new finding', () => {
  const finding = kind => ({ kind, line: 1, index: 0 });
  const ratchet = { entries: [{ path: 'x.json', line: 7, counts: { 'home-path': 2 }, reason: 'r' }] };
  assert.deepEqual(judge({ 'x.json': [finding('home-path'), finding('home-path')] }, { ratchet, tree: 'tracked' }), []);
  assert.match(judge({ 'x.json': [finding('home-path')] }, { ratchet, tree: 'tracked' })[0], /lower the count/);
  assert.match(judge({}, { ratchet, tree: 'tracked' })[0], /delete the line/);
  assert.match(judge({ 'x.json': [1, 2, 3].map(() => finding('home-path')) }, { ratchet, tree: 'tracked' })[0], /3 home-path/);
  assert.match(judge({ 'y.md': [finding('fleet-host')] }, { ratchet, tree: 'tracked' })[0], /y\.md has 1 fleet-host/);
  // a published copy may carry at most what its source is permitted, and fewer is fine
  assert.deepEqual(judge({ 'x.json': [finding('home-path')] }, { ratchet, tree: 'dist' }), []);
});

test('the ratchet only shrinks', () => {
  const base = parseRatchet('a | home-path=2 | a reason long enough\nb | fleet-host=1 | a reason long enough');
  assert.deepEqual(growthProblems(parseRatchet('a | home-path=1 | a reason long enough'), base), []);
  assert.match(growthProblems(parseRatchet('a | home-path=3 | a reason long enough'), base)[0], /grew/);
  assert.match(growthProblems(parseRatchet('c | home-path=1 | a reason long enough'), base)[0], /is new/);
  assert.match(growthProblems(parseRatchet('a | fleet-host=1 | a reason long enough'), base)[0], /grew from 0/);
});

test(`${RATCHET} is well formed and no larger than on the base branch`, t => {
  const ratchet = loadRatchet();
  assert.deepEqual(ratchetProblems(ratchet), []);
  const { ref, ratchet: base } = baseRatchet();
  // in CI a missing base is a broken checkout, not a pass; locally (no origin/dev, a shallow clone) it is a skip
  if (!ref) assert.ok(process.env.GITHUB_ACTIONS !== 'true', 'cannot find the base commit to compare the ratchet with');
  if (!base) return t.skip(`no ratchet on the base (${ref || 'no history'}); this change introduces it`);
  assert.deepEqual(growthProblems(ratchet, base), [], `compared with ${ref}`);
});

test('tracked files hold no private details beyond the ratchet', () => {
  assert.deepEqual(judge(scanTracked(ROOT, names), { ratchet: loadRatchet(), tree: 'tracked' }), []);
});

test('the built site holds none either', () => {
  const dist = path.join(ROOT, 'dist');
  assert.ok(existsSync(path.join(dist, 'version.json')), 'build the site first: npm run build');
  const built = JSON.parse(readFileSync(path.join(dist, 'version.json'), 'utf8'));
  assert.ok(built.revision || built.source, 'dist/version.json names its source revision');
  const findings = scanDist(dist, names);
  assert.deepEqual(judge(findings, { ratchet: loadRatchet(), tree: 'dist' }), []);
  // only copies of ratcheted or allowed files may carry anything at all
  const permitted = new Set([...loadRatchet().entries.map(e => e.path), ...ALLOWED.flatMap(a => a.paths)]);
  assert.deepEqual(Object.keys(findings).filter(p => !permitted.has(p)), []);
});
