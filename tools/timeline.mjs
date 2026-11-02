/** "What changed": the design's own history, from git, when the site is built. Each change is one commit on the
 * integration branch's first-parent line (a merged pull request, or a direct commit) that changed the design: CAD
 * source, geometry, a render, a new record, a decision, or hardware. Its date is git's, its label the PR's title (or
 * the commit's subject) shortened, its subsystems come from the paths it touched, and when it changed a render the
 * build publishes that render before and after, straight from git's objects.
 *
 * tools/build-site.mjs writes the timeline into the landing page and Progress (<!-- timeline --> markers) and
 * /site/timeline.json. tools/test-timeline.mjs reads git again on its own and compares.
 */
import { execFileSync } from 'node:child_process';
import YAML from 'yaml';
import { shortDate } from './status-board.mjs';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const DESIGN_PATHS = ['cad', 'exports', 'hardware', 'research', 'firmware', 'docs/decisions.yaml'];
// Browser snapshots, logs and generated directory furniture are not design changes on their own.
const NOT_DESIGN = /^exports\/(sim|links)\/|\.log$/;

/** Which subsystem a path belongs to, first match wins; null for shared records. */
export const SUBSYSTEMS = [
  ['rig', /(^|\/)(rig|legrig)(\/|_|-)|leg[_-]rig|exports\/rig\//],
  ['wheels', /wheel/],
  ['electronics', /^hardware\/|fuse|wiring|carrier-pan|electr|firmware\/|protection/],
  ['turret', /turret|exports\/gates\/|dossier|hopper|flywheel|cartridge|barrel|pan_|tilt_|launcher/],
  ['leg', /(^|\/)leg|fivebar|rs04|hip_frame|hip-frame|upper_link|front_link|knee/],
  ['body', /body|chassis|battery|shell/],
];
export const subsystemOf = file => SUBSYSTEMS.find(([, re]) => re.test(file))?.[0] ?? null;
const RENDER = /\.(png|jpg|webp)$/;
const GEOMETRY = /\.(step|stp|stl|3mf|dxf)$/;

/** A short label: the first clause, at most `max` characters, cut at a word. */
export function shorten(title, max = 84) {
  const branch = title.match(/^Merge branch '([^']+)'/)?.[1];
  let t = title.replace(/^Merge (pull request #\d+ from \S+|branch '[^']+'( into \S+)?|[\w/.-]+( \(#\d+\))?:)\s*/, '').trim();
  if (!t && branch) t = `${branch} merged`;
  // The first clause: up to a "; ", " — " or ". " that is not inside parentheses.
  let depth = 0, end = t.length;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (c === '(') depth++;
    else if (c === ')') depth = Math.max(0, depth - 1);
    else if (!depth && (t.startsWith('; ', i) || t.startsWith(' — ', i) || t.startsWith('. ', i))) { end = i; break; }
  }
  t = t.slice(0, end).replace(/\s*\((?:#\d+(?:, )?)+\)\s*$/, '');
  t = t.charAt(0).toUpperCase() + t.slice(1);
  if (t.length <= max) return t;
  const cut = t.slice(0, max - 1);
  return cut.slice(0, cut.lastIndexOf(' ')).replace(/[,:;(]+$/, '') + '…';
}

/** The changes, newest first. `git(args)` runs git in the repository and returns its output. */
export function collectTimeline(git, { limit = 40, decisions = [] } = {}) {
  const log = git(['log', '--first-parent', '-m', '--format=@@%H%x1f%cI%x1f%s%x1f%b%x1e', '--name-status', 'HEAD', '--', ...DESIGN_PATHS]);
  const titles = Object.fromEntries(decisions.map(d => [d.id, d.title]));
  const events = [];
  for (const chunk of log.split('@@').slice(1)) {
    const [head, files = ''] = chunk.split('\x1e');
    const [sha, date, subject, body] = head.split('\x1f');
    const changes = files.trim().split('\n').filter(Boolean).map(l => { const [status, ...p] = l.split('\t'); return { status: status[0], file: p.at(-1) }; })
      .filter(c => !NOT_DESIGN.test(c.file));
    const pr = subject.match(/^Merge pull request #(\d+)/)?.[1] ?? null;
    const title = pr ? (body.trim().split('\n')[0] || subject) : subject;
    const touched = changes.some(c => c.file === 'docs/decisions.yaml') ? decisionChanges(git(['diff', '-U60', `${sha}^1`, sha, '--', 'docs/decisions.yaml'])) : [];
    const added = touched.map(d => d.id);
    const kinds = {
      cad: changes.filter(c => /^cad\//.test(c.file)).length,
      geometry: changes.filter(c => GEOMETRY.test(c.file)).length,
      renders: changes.filter(c => RENDER.test(c.file) && !/thumbs\//.test(c.file)).length,
      records: changes.filter(c => c.status === 'A' && /\.(json|csv)$/.test(c.file)).length,
      hardware: changes.filter(c => /^hardware\//.test(c.file)).length,
      decisions: touched.length,
    };
    // A design change touched CAD, geometry, a render, hardware, a decision, or added a record.
    if (!Object.values(kinds).some(Boolean)) continue;
    const counts = {};
    for (const c of changes) { const s = subsystemOf(c.file); if (s) counts[s] = (counts[s] || 0) + 1; }
    const subsystems = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([s]) => s).slice(0, 2);
    if (!subsystems.length) for (const id of added) { const s = subsystemOf((titles[id] || '').toLowerCase()); if (s && !subsystems.includes(s)) subsystems.push(s); }
    const image = pickRender(changes, subsystems[0]);
    events.push({ sha, date, pr, label: shorten(title), title, subsystems, kinds, files: changes.length,
      decisions: touched.map(d => ({ ...d, title: titles[d.id] ? shorten(titles[d.id], 90) : null })),
      image: image && { file: image.file, before: image.status === 'M', after: true } });
    if (events.length >= limit) break;
  }
  return events;
}

/** The decisions a diff of docs/decisions.yaml adds or revises, from enough context to see each entry's id. */
export function decisionChanges(diff) {
  const seen = new Map();
  let id = null;
  for (const line of diff.split('\n')) {
    if (line.startsWith('@@')) { id = null; continue; }
    const m = line.match(/^([ +-])- id: (D\d+)\s*$/);
    if (m) { id = m[2]; if (m[1] === '+') seen.set(id, 'new'); else if (m[1] === '-' && !seen.has(id)) seen.set(id, 'removed'); continue; }
    if (id && /^[+-]\s*\S/.test(line) && !seen.has(id)) seen.set(id, 'revised'); // blank lines are not revisions
  }
  // An id both removed and added in place is a revision.
  return [...seen].filter(([, change]) => change !== 'removed').map(([id, change]) => ({ id, change }));
}

/** The render that best shows a change: an assembly view, then a part render, then a study's still. */
function pickRender(changes, main) {
  const renders = changes.filter(c => (c.status === 'A' || c.status === 'M') && RENDER.test(c.file) && /^(exports|hardware)\//.test(c.file) && !/thumbs\//.test(c.file));
  const score = c => (/iso|exploded|side|front|stand|turret\.png|rig-/.test(c.file) ? 3 : 0) + (c.status === 'M' ? 2 : 0) + (/fea\//.test(c.file) ? 1 : 0) - (/critical-layers|flat-|board-level/.test(c.file) ? 2 : 0) + (main && subsystemOf(c.file) === main ? 2 : 0);
  return renders.sort((a, b) => score(b) - score(a) || a.file.localeCompare(b.file))[0] || null;
}

/** Decisions from docs/decisions.yaml text. */
export const parseDecisions = text => YAML.parse(text);

/** Run git in `root`, as text. */
export const gitIn = root => args => execFileSync('git', args, { cwd: root, maxBuffer: 64 << 20 }).toString();

const SUBSYSTEM_NAMES = { leg: 'Leg', turret: 'Turret', body: 'Body', wheels: 'Wheels', rig: 'Leg rig', electronics: 'Electronics' };
const KIND_WORDS = [['cad', 'CAD file'], ['geometry', 'model'], ['renders', 'render'], ['records', 'new record'], ['hardware', 'hardware file'], ['decisions', 'decision']];
const count = (n, noun) => `${n} ${noun}${n === 1 ? '' : 's'}`; // every noun here is its last word

/** The published image paths for an event (the build copies git's blobs there). */
export const imagePaths = e => e.image && { after: `/site/timeline/${e.sha.slice(0, 10)}-after.${e.image.file.split('.').pop()}`, before: e.image.before ? `/site/timeline/${e.sha.slice(0, 10)}-before.${e.image.file.split('.').pop()}` : null };

function eventHTML(e, i) {
  const img = imagePaths(e);
  const chips = e.subsystems.map(s => `<span class="tl-chip" data-subsystem="${s}">${SUBSYSTEM_NAMES[s]}</span>`).join('') || '<span class="tl-chip">Shared records</span>';
  const kinds = KIND_WORDS.filter(([k]) => e.kinds[k]).map(([k, w]) => count(e.kinds[k], w)).join(' · ');
  const decisions = e.decisions.length ? `<ul class="tl-decisions">${e.decisions.map(d => `<li><b>${esc(d.id)}</b>${d.change === 'revised' ? ' <em>revised</em>' : ''} ${esc(d.title || '')}</li>`).join('')}</ul>` : '';
  const pictures = img ? `<figure class="tl-pics${img.before ? ' has-before' : ''}">${img.before ? `<span class="tl-pic"><img src="${img.before}" alt="Before: ${esc(e.image.file)}" loading="lazy" decoding="async"><small>before</small></span><span class="tl-arrow" aria-hidden="true">→</span>` : ''}<span class="tl-pic"><img src="${img.after}" alt="${img.before ? 'After' : 'New'}: ${esc(e.image.file)}" loading="lazy" decoding="async"><small>${img.before ? 'after' : 'new'}</small></span><figcaption>${esc(e.image.file)}</figcaption></figure>` : '';
  const link = e.pr ? `<a href="https://github.com/Valpatel/gyropup/pull/${e.pr}">#${e.pr}</a>` : `<a href="https://github.com/Valpatel/gyropup/commit/${e.sha}">${e.sha.slice(0, 7)}</a>`;
  return `<li class="tl-event" style="--i:${i}"${img ? ' data-visual' : ''}><time datetime="${esc(e.date)}">${shortDate(e.date)}</time><div class="tl-card"><p class="tl-meta">${chips}<span class="tl-kinds">${kinds}</span></p>`
    + `<h3 class="tl-label">${esc(e.label)} <span class="tl-ref">${link}</span></h3>${decisions}${pictures}</div></li>`;
}

/** The timeline's HTML: the newest `show` changes; on Progress, the rest folded below. */
export function renderTimeline(events, { show = 6, more = 0, compact = false } = {}) {
  if (!events.length) return `<section id="changes" class="timeline" aria-labelledby="changes-title"><h2 id="changes-title">What changed</h2><p class="tl-empty">The change history is not available in this build.</p></section>`;
  const shown = events.slice(0, show), folded = events.slice(show, show + more);
  const days = new Set(events.map(e => e.date.slice(0, 10))).size;
  return `<section id="changes" class="timeline${compact ? ' is-compact' : ''}" aria-labelledby="changes-title" data-generated="tools/timeline.mjs">`
    + `<div class="tl-heading"><p class="eyebrow"><span class="status-dot"></span> FROM THE GIT HISTORY</p><h2 id="changes-title">What changed, <span>and when.</span></h2>`
    + `<p class="tl-lede">The last ${events.length} design changes over ${days} days: CAD, models, renders, records and decisions, newest first. Where a change re-rendered a part, its before and after.</p></div>`
    + `<ol class="tl-list">${shown.map(eventHTML).join('')}</ol>`
    + (folded.length ? `<details class="tl-more"><summary>${folded.length} earlier changes</summary><ol class="tl-list">${folded.map((e, i) => eventHTML(e, i + shown.length)).join('')}</ol></details>` : '')
    + (compact ? `<a class="tl-all" href="/designer/progress.html#changes">Every change on Progress →</a>` : '')
    + `</section>`;
}
