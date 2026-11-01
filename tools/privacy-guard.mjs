// Privacy guard: this repository and gyropup.com are public. Absolute home-directory paths, fleet compute host names,
// private or tailnet addresses and private repository names must never be committed or published.
//
//   node tools/privacy-guard.mjs            report the tracked files and the built dist/ (exit 1 on a violation)
//   node tools/privacy-guard.mjs --tracked  tracked files only
//   npm run test:privacy                     the CI check (tools/test-privacy.mjs), after `npm run build`
//
// Reports name the file, line and kind of string, never the string itself: CI logs of a public repository are public too.
// Findings that cannot be fixed yet live in tools/privacy-ratchet.txt, one file per line, which may only shrink.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const RATCHET = 'tools/privacy-ratchet.txt';

// The project's GitHub accounts. A repository slug under one of them must be a public repository listed here.
// Add a slug only after checking that its repository is public.
export const PUBLIC_REPOS = {
  'valpatel/gyropup': 'this repository',
  'valpatel/wobbit': "this repository's name before the rename to gyropup (requirements R5, R18)",
  'valpatel/cad-agent': 'the public CAD toolkit',
  'mvalancy/moxie-robot-saver': 'the public Moxie simulator the character and HUD code adapt',
  'mvalancy/j501-agx-orin': 'the public J501 enclosure project',
};
const OWNERS = ['valpatel', 'mvalancy', 'graphdone'];

const IPV4_PRIVATE = String.raw`(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}`;

export const RULES = [
  { kind: 'home-path', fix: 'use a repository-relative path, or a placeholder such as <cad-agent checkout>',
    // with or without a trailing slash, under /var/home too, and folded into a folder name (/-home-<name>-...)
    patterns: [/(?<![\w.-])(?:\/var)?\/(?:home|Users)\/[A-Za-z_][\w.-]*/g, /(?<=\/)-(?:home|Users)-[A-Za-z_][\w.]*-/g,
      /\b[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[A-Za-z_][\w.-]*(?:\\\\|\\)/g] },
  { kind: 'fleet-host', fix: 'say "the recording compute host" or "a CAD host"; the hardware family alone (a GB10) is fine',
    // a hardware family plus a node number, or a GPU model written as a lowercase host name
    patterns: [/\b(?:gb10|dgx|spark|thor|orin|jetson|agx)-\d{1,3}\b/gi, /\brtx\d{4}\b/g] },
  { kind: 'private-ip', fix: 'use a documentation address (192.0.2.0/24) or a name such as voice-host',
    patterns: [new RegExp(String.raw`(?<![\w.])${IPV4_PRIVATE}(?!\.?\d)`, 'g'), /\bfd7a:115c:a1e0:[0-9a-f:]*/gi] },
  { kind: 'tailnet-name', fix: 'name the role of the machine, not its tailnet name',
    patterns: [/\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)?[a-z0-9-]+\.ts\.net\b/gi] },
  { kind: 'private-repo', fix: 'describe the repository, or list it in PUBLIC_REPOS once it is public' },
];
export const KINDS = RULES.map(r => r.kind);

// Paths skipped whole: { glob, reason }. Kept empty on purpose: a vendored file whose own strings match is better
// listed in ALLOWED with exact counts, so a later edit that adds a finding still fails.
export const EXEMPT = [];

// Findings that are public facts, not private details. Counts are per file; a new finding in the same file still fails.
export const ALLOWED = [
  { paths: ['catalog/sensors_compute.json', 'research/sensors-compute.md', 'site/pages/research-sensors-compute-md.html',
    'site/pages/research-sensors-compute-md.md'], counts: { 'private-ip': 1 },
    reason: "the lidar's factory-default address, quoted from the manufacturer's public manual" },
  { paths: ['designer/kit/vendor/occt-import-js/occt-import-js.js'], counts: { 'home-path': 2 },
    reason: "Emscripten's virtual file system home for its web_user, a constant of every Emscripten build, in the "
    + 'unmodified upstream release recorded in file-viewer-sources.json' },
  { paths: ['tools/test-service-discovery.mjs'], counts: { 'private-ip': 4, 'tailnet-name': 1 },
    reason: 'fixture hosts for the test that proves the hosted simulator never probes private networks' },
];

// Skipped without reading; any other file is scanned unless its first 8 KB hold a NUL byte (ASCII STEP and STL are text).
const BINARY = /\.(?:png|jpe?g|gif|webp|avif|ico|mp4|webm|mov|mp3|wav|ogg|glb|bin|3mf|npz|npy|onnx|pt|zip|gz|xz|pdf|woff2?|ttf|otf|wasm)$/i;

function globRegex(glob) {
  const src = glob.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*\*\//g, '\u0000').replace(/\*/g, '[^/]*')
    .replace(/\u0000/g, '(?:.*/)?');
  return new RegExp(`^${src}$`);
}
const exemptRes = EXEMPT.map(e => ({ ...e, re: globRegex(e.glob) }));
export const isExempt = rel => exemptRes.some(e => e.re.test(rel));

function words(names) {
  return [...new Set(names.map(n => n.trim()).filter(Boolean))].map(n => new RegExp(
    String.raw`(?<![\w-])${n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\w-])`, 'gi'));
}

// Optional extra private names (a newline or comma separated list in GYROPUP_PRIVATE_NAMES), for checks run where the
// names are known; they are never written into the repository.
export function privateNames(env = process.env) {
  return (env.GYROPUP_PRIVATE_NAMES || '').split(/[\n,]/);
}

const lineOf = (text, index) => { let n = 1; for (let i = text.indexOf('\n'); i !== -1 && i < index; i = text.indexOf('\n', i + 1)) n++; return n; };

/** Every private finding in a text: [{kind, line, index}], without the matched text. */
export function scanText(text, { names = [] } = {}) {
  const found = [];
  const add = (kind, index) => found.push({ kind, index, line: lineOf(text, index) });
  for (const rule of RULES) for (const re of rule.patterns || []) for (const m of text.matchAll(re)) add(rule.kind, m.index);
  const slug = new RegExp(String.raw`(?<![\w.-])(${OWNERS.join('|')})/([A-Za-z0-9_.-]+)`, 'gi');
  for (const m of text.matchAll(slug)) {
    const repo = m[2].replace(/\.git$/i, '').replace(/[._-]+$/, '');
    if (!PUBLIC_REPOS[`${m[1]}/${repo}`.toLowerCase()]) add('private-repo', m.index);
  }
  for (const re of words(names)) for (const m of text.matchAll(re)) add('private-repo', m.index);
  return found.sort((a, b) => a.index - b.index);
}

function readText(file) {
  if (BINARY.test(file)) return null;
  const data = readFileSync(file);
  if (data.subarray(0, 8192).includes(0)) return null;
  return data.toString('utf8');
}

/** {relative path: [findings]} for the files given (relative to base); exempt and binary files are skipped. */
export function scanFiles(base, files, options = {}) {
  const out = {};
  for (const rel of files) {
    if (isExempt(rel)) continue;
    const text = readText(path.join(base, rel));
    if (text === null) continue;
    const found = scanText(text, options);
    if (found.length) out[rel] = found;
  }
  return out;
}

export function trackedFiles(root = ROOT) {
  return execFileSync('git', ['ls-files', '-z'], { cwd: root, maxBuffer: 64 << 20 }).toString().split('\0')
    .filter(f => f && existsSync(path.join(root, f)));
}

export function walk(dir, base = dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full, base));
    else if (entry.isFile()) out.push(path.relative(base, full).split(path.sep).join('/'));
  }
  return out.sort();
}

export const scanTracked = (root = ROOT, options = {}) => scanFiles(root, trackedFiles(root), options);
export const scanDist = (dist = path.join(ROOT, 'dist'), options = {}) => scanFiles(dist, walk(dist), options);

export const countKinds = found => found.reduce((c, f) => ({ ...c, [f.kind]: (c[f.kind] || 0) + 1 }), {});

/** The ratchet's lines, `path | kind=count, kind=count | reason`, as {entries: [{path, counts, reason, line}]}. */
export function parseRatchet(text) {
  const entries = [];
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const [file, counts = '', ...reason] = line.split(' | ');
    entries.push({ path: file.trim(), line: i + 1, reason: reason.join(' | ').trim(),
      counts: Object.fromEntries(counts.split(',').filter(c => c.trim()).map(c => {
        const [kind, n] = c.split('=').map(s => s.trim());
        return [kind, /^\d+$/.test(n || '') ? Number(n) : NaN];
      })) });
  });
  return { entries };
}

export function loadRatchet(root = ROOT) {
  return parseRatchet(readFileSync(path.join(root, RATCHET), 'utf8'));
}

/**
 * Judge findings against the allowed list and the ratchet. In the tracked tree a ratchet entry must match its file's
 * findings exactly (lower it as strings are removed; delete it when none are left). In dist/ a published copy of a
 * ratcheted or allowed file may carry at most the recorded counts. Returns a list of problems (strings, no secrets).
 */
export function judge(findings, { ratchet, tree }) {
  const problems = [];
  const allowed = new Map();
  for (const a of ALLOWED) for (const p of a.paths) allowed.set(p, a.counts);
  const ratcheted = new Map(ratchet.entries.map(e => [e.path, e.counts]));
  for (const [rel, found] of Object.entries(findings)) {
    const counts = countKinds(found);
    const permitted = { ...(allowed.get(rel) || {}) };
    for (const [kind, n] of Object.entries(ratcheted.get(rel) || {})) permitted[kind] = (permitted[kind] || 0) + n;
    for (const [kind, n] of Object.entries(counts)) {
      if (n <= (permitted[kind] || 0)) continue;
      const lines = [...new Set(found.filter(f => f.kind === kind).map(f => f.line))].slice(0, 12).join(', ');
      const fix = RULES.find(r => r.kind === kind).fix;
      problems.push(`${tree}: ${rel} has ${n} ${kind} finding(s), ${permitted[kind] || 0} permitted (lines ${lines}): ${fix}`);
    }
  }
  if (tree === 'tracked') {
    // a ratchet line must match its file exactly, so fixes show up as a shorter ratchet
    for (const entry of ratchet.entries) {
      const counts = countKinds(findings[entry.path] || []), allow = allowed.get(entry.path) || {};
      const net = kind => Math.max(0, (counts[kind] || 0) - (allow[kind] || 0));
      const left = Object.keys(entry.counts).reduce((sum, kind) => sum + net(kind), 0);
      for (const [kind, recorded] of Object.entries(entry.counts)) {
        if (net(kind) >= recorded) continue;
        problems.push(`ratchet: ${entry.path} now has ${net(kind)} ${kind} finding(s) and line ${entry.line} of ${RATCHET} `
          + `records ${recorded}: ${left ? 'lower the count' : 'delete the line'}`);
      }
    }
  }
  return problems;
}

/** Structural rules for the ratchet itself: known kinds, positive counts, a reason, no duplicates, no exempt paths. */
export function ratchetProblems(ratchet) {
  const problems = [], seen = new Set();
  for (const e of ratchet.entries || []) {
    if (seen.has(e.path)) problems.push(`ratchet: ${e.path} is listed twice`);
    seen.add(e.path);
    if (!e.reason || e.reason.trim().length < 20) problems.push(`ratchet: ${e.path} needs a reason`);
    if (!e.counts || !Object.keys(e.counts).length) problems.push(`ratchet: ${e.path} records no counts`);
    for (const [kind, n] of Object.entries(e.counts || {})) {
      if (!KINDS.includes(kind)) problems.push(`ratchet: ${e.path} has an unknown kind ${kind}`);
      if (!Number.isInteger(n) || n < 1) problems.push(`ratchet: ${e.path} ${kind} must be a positive count`);
    }
    if (isExempt(e.path)) problems.push(`ratchet: ${e.path} is exempt already`);
  }
  return problems;
}

/** The ratchet may only shrink: every entry must exist in the base ratchet with at least the same counts. */
export function growthProblems(ratchet, base) {
  const before = new Map(base.entries.map(e => [e.path, e.counts]));
  const problems = [];
  for (const e of ratchet.entries) {
    const was = before.get(e.path);
    if (!was) { problems.push(`ratchet: ${e.path} is new; fix the file instead of adding it`); continue; }
    for (const [kind, n] of Object.entries(e.counts)) {
      if (n > (was[kind] || 0)) problems.push(`ratchet: ${e.path} ${kind} grew from ${was[kind] || 0} to ${n}`);
    }
  }
  return problems;
}

/** The ratchet on the branch this change goes into (null when there is none or no history is available). */
export function baseRatchet(root = ROOT, env = process.env) {
  const git = (...args) => execFileSync('git', args, { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
  let ref = env.PRIVACY_RATCHET_BASE;
  try {
    if (ref) ref = git('rev-parse', '--verify', `${ref}^{commit}`);   // an override that names no commit is no base
    if (!ref && env.GITHUB_EVENT_NAME === 'push') ref = git('rev-parse', 'HEAD^1');
    if (!ref) ref = git('merge-base', 'HEAD', `origin/${env.GITHUB_BASE_REF || 'dev'}`);
  } catch { return { ref: null, ratchet: null }; }
  try { return { ref, ratchet: parseRatchet(git('show', `${ref}:${RATCHET}`)) }; } catch { return { ref, ratchet: null }; }
}

function report(title, findings, problems) {
  const files = Object.keys(findings);
  console.log(`${title}: ${files.length} file(s) with findings, ${problems.length} problem(s)`);
  for (const rel of files) console.log(`  ${rel}: ${Object.entries(countKinds(findings[rel])).map(([k, n]) => `${k} ${n}`).join(', ')}`);
  for (const p of problems) console.log(`  PROBLEM ${p}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const options = { names: privateNames() };
  const ratchet = loadRatchet();
  const tracked = scanTracked(ROOT, options);
  const problems = [...ratchetProblems(ratchet), ...judge(tracked, { ratchet, tree: 'tracked' })];
  report('tracked', tracked, problems);
  let failed = problems.length > 0;
  if (!process.argv.includes('--tracked')) {
    const dist = path.join(ROOT, 'dist');
    if (!existsSync(path.join(dist, 'version.json'))) { console.log('dist: not built (npm run build)'); failed = true; } else {
      const built = scanDist(dist, options), distProblems = judge(built, { ratchet, tree: 'dist' });
      report('dist', built, distProblems);
      failed ||= distProblems.length > 0;
    }
  }
  process.exitCode = failed ? 1 : 0;
}
