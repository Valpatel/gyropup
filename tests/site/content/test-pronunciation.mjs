// The pronunciation key, browser side (designer/character/pronounce.js), and the recorded voice it feeds.
// node --test tools/test-pronunciation.mjs   (tools/test-pronunciation.py checks the Python side gives the same text)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { compileKey } from '../designer/character/pronounce.js';
import { fixedLines } from '../designer/character/lines.js';

const read = p => JSON.parse(readFileSync(new URL('../' + p, import.meta.url), 'utf8'));
const KEY = read('designer/character/pronunciation.json');
const say = compileKey(KEY);
const FIXTURE = { version: 9, protect: KEY.protect, entries: [
  { match: 'Gyropup', say: 'gyro pup' }, { match: ['cad-agent', 'cad agent'], say: 'cad agent' }, { match: 'cad', say: 'kad' },
  { match: 'cyan', say: 'sigh-an' },
] };

test('the key file examples', () => {
  for (const [written, spoken] of KEY.examples) assert.equal(say(written), spoken, written);
});

test('case, possessives, plurals, other words, URLs', () => {
  const f = compileKey(FIXTURE);
  const cases = {
    Gyropup: 'gyro pup', gyropup: 'gyro pup', GyroPup: 'gyro pup', 'GYROPUP!': 'gyro pup!',
    "Gyropup's": "gyro pup's", 'Gyropup’s': 'gyro pup’s', Gyropups: 'gyro pups', "Gyropups' legs": "gyro pups' legs",
    Gyropupper: 'Gyropupper', minigyropup: 'minigyropup', gyropup2: 'gyropup2', gyropup_v2: 'gyropup_v2',
    'Gyropup Gyropup': 'gyro pup gyro pup', '"Gyropup"': '"gyro pup"', 'Gyropup.': 'gyro pup.',
    'https://gyropup.com/Gyropup': 'https://gyropup.com/Gyropup', 'gyropup.com': 'gyropup.com',
    'www.gyropup.com/x Gyropup': 'www.gyropup.com/x gyro pup', 'pup@gyropup.dev': 'pup@gyropup.dev',
    'Run cad-agent, a CAD AGENT, in cad': 'Run cad agent, a cad agent, in kad', 'cadence and decade': 'cadence and decade',
  };
  for (const [written, spoken] of Object.entries(cases)) assert.equal(f(written), spoken, written);
});

test('an emphasis entry moves the stress by respelling', () => {
  assert.equal(compileKey(FIXTURE)('Cyan eyes, cyanide'), 'sigh-an eyes, cyanide');
  assert.equal(say('My eyes glow cyan.'), 'My eyes glow sigh-an.');
});

test('applying the key twice is the same as once', () => {
  const texts = KEY.examples.map(e => e[0]);
  for (const e of [...KEY.entries, ...FIXTURE.entries]) for (const m of [].concat(e.match)) texts.push(m, m + "'s", m + 's', e.say);
  for (const f of [say, compileKey(FIXTURE)]) for (const t of texts) assert.equal(f(f(t)), f(t), t);
  assert.equal(say('gyro pup'), 'gyro pup');
});

test('a malformed entry is refused, not silently skipped', () => {
  assert.throws(() => compileKey({ entries: [{ match: 'x', say: ' ' }] }), /needs a "match" and a "say"/);
});

test('every fixed line has a clip spoken as the key says', () => {
  const manifest = read('designer/character/voice/manifest.json');
  assert.equal(manifest.key_version, KEY.version);
  const lines = fixedLines();
  assert.deepEqual(Object.keys(manifest.lines).sort(), [...lines].sort(), 'run tools/render-voice.py');
  for (const line of lines) {
    assert.equal(manifest.lines[line].spoken, say(line.replace(/\s+/g, ' ').trim()), `${line}: run tools/render-voice.py`);
    assert.match(manifest.lines[line].clip, /^[0-9a-f]{16}\.mp3$/);
  }
  assert.ok(lines.some(l => /Gyropup/.test(l) && /gyro pup/.test(manifest.lines[l].spoken)));
});
