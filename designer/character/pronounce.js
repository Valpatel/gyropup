// Gyropup's pronunciation key, the browser side: what text is sent to a voice. The key is pronunciation.json (next to
// this file); tools/pronunciation.py applies the same file the same way for the Piper sidecar and the clip renderer,
// and both run the key's examples in CI (tools/test-pronunciation.mjs, tools/test-pronunciation.py).
//
//   import { compileKey, loadPronouncer } from './pronounce.js';
//   const say = await loadPronouncer();   say("Gyropup's turret")  // "gyro pup's turret"
//
// An entry's `match` (a string or a list) is found case-insensitively as a whole word, optionally followed by 's, ’s,
// s', s’ or s, which are kept; text inside the key's `protect` pattern (URLs, e-mail addresses, domain names) is never
// changed; all entries are replaced in one pass, so applying the key twice gives the same text as once.

const SUFFIX = "'s|’s|s'|s’|s";      // keep in step with tools/pronunciation.py
const WORD = String.raw`A-Za-z0-9_\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F`;   // Latin letters too (not × or ÷): never inside another word
const SPACE = String.raw`\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff`;   // \s, spelled out so tools/pronunciation.py splits text the same
const norm = s => String(s).trim().toLowerCase().replace(/\s+/g, ' ');
const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** compileKey(key) -> (text) => text as a voice should be sent it. */
export function compileKey(key) {
  const say = new Map();
  for (const [i, e] of (key?.entries ?? []).entries()) {
    if (!e?.match || typeof e.say !== 'string' || !e.say.trim()) throw new Error(`pronunciation entry ${i} needs a "match" and a "say"`);
    for (const m of [].concat(e.match)) say.set(norm(m), e.say);
  }
  const alts = [...say.keys()].sort((a, b) => b.length - a.length);
  const body = alts.map(m => m.split(' ').map(escape).join(`[${SPACE}]+`)).join('|');
  const words = alts.length ? new RegExp(`(^|[^${WORD}])(${body})(${SUFFIX})?(?![${WORD}])`, 'gi') : null;
  const protect = key?.protect ? new RegExp(key.protect, 'gi') : null;
  const apply = text => words ? text.replace(words, (_, pre, m, suf) => pre + say.get(norm(m)) + (suf ?? '')) : text;
  return text => {
    text = String(text ?? '');
    if (!protect) return apply(text);
    let out = '', at = 0;
    for (const m of text.matchAll(protect)) { out += apply(text.slice(at, m.index)) + m[0]; at = m.index + m[0].length; }
    return out + apply(text.slice(at));
  };
}

let loading = null;
/** The repository's key, fetched once next to this module; on any failure the text is spoken as written. */
export function loadPronouncer() {
  loading ??= (async () => {
    try {
      const url = new URL('./pronunciation.json', import.meta.url);
      url.search = new URL(import.meta.url).search;            // carry the built module's cache key
      const r = await fetch(url);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return compileKey(await r.json());
    } catch (e) {
      console.warn('[talk] no pronunciation key, speaking text as written:', e.message);
      return text => String(text ?? '');
    }
  })();
  return loading;
}
