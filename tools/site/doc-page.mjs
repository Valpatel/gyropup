/** Design-note pages without walls of text. tools/build-site.mjs renders each docs/research/hardware Markdown file with
 * marked and then passes the HTML through enhanceDocument(), which changes how it is shown, never what it says:
 *
 * - A lead card under the title: when the note was last changed (git), how long it is, its sections as jump links,
 *   and, for a note about one subsystem, that subsystem's render and its first readings from the status board
 *   (tools/status-board.mjs), so the page opens on the real part and its real numbers.
 * - Status strips: a table with a Status, Verdict, Result or State column of short values gets a bar of how many rows
 *   are in each state, counted from the table itself, above it.
 * - Folds: a long run of prose with nothing to look at keeps its opening and folds the rest into a <details> that
 *   says what is in it. Pictures, diagrams and strips are never folded; every word stays on the page and in its
 *   Markdown route. A link to a folded heading opens its fold (the frame's script).
 *
 * tools/test-doc-pages.mjs tests it on fixtures and on the built pages.
 */
import { parseHTML } from 'linkedom';
import { shortDate } from './status-board.mjs';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const words = text => (text.match(/\S+/g) || []).length;
const plural = (n, noun) => `${n} ${noun}${n === 1 ? '' : 's'}`;

// The page's measure (web/portal.css: 1100 px column, 15 px Inter, 1.8 line height) as a rough layout model: enough
// to decide what to fold. tools/test-walls.mjs measures the real result in a browser.
const LINE = 27, CHARS = 125;
export const KEEP_PX = 520;   // a run keeps about this much of its opening in view
export const FOLD_PX = 900;   // and folds only when it runs on past this
const VISUAL = 'img, svg, video, canvas, picture, iframe, figure, .cad-diagram, [data-visual], pre.mermaid, code.language-mermaid';

/** Estimated height in px of one top-level block as laid out, 0 for a visual. */
export function blockHeight(el) {
  const tag = el.tagName.toLowerCase();
  if (isVisual(el)) return 0;
  const text = el.textContent.replace(/\s+/g, ' ').trim();
  const lines = s => Math.max(1, Math.ceil(s.length / CHARS));
  if (/^h[1-6]$/.test(tag)) return tag === 'h2' ? 80 : 56;
  if (tag === 'pre') return el.textContent.split('\n').length * 20 + 40;
  if (el.classList?.contains('table-scroll')) {
    const rows = [...el.querySelectorAll('tr')];
    const cols = Math.max(1, rows[0]?.children.length || 1);
    return 40 + rows.reduce((h, tr) => h + 21 + 18 * Math.max(...[...tr.children].map(td => Math.ceil(td.textContent.trim().length / Math.max(14, 150 / cols)))), 0);
  }
  if (tag === 'ul' || tag === 'ol') return [...el.children].reduce((h, li) => h + lines(li.textContent.trim()) * LINE + 4, 15);
  if (tag === 'hr') return 40;
  return lines(text) * LINE + 15;
}
const isVisual = el => el.matches?.(VISUAL) || !!el.querySelector?.(VISUAL);
const MODEL_FILE = /\.(step|stp|stl|3mf|glb|gltf)(?:[?#].*)?$/i;
const modelLinks = el => [...el.querySelectorAll?.('a[href]') || []].filter(a => isModelLink(a.getAttribute('href'))).length;
/** Prose or a list that links a model: web/model-links.js gives each such link a "Preview in 3D" action, so the block stays
 * in view. A table of models may fold, and its fold's summary counts the models inside. */
export const isModelAction = el => !el.classList?.contains('table-scroll') && el.tagName !== 'TABLE' && modelLinks(el) > 0;
/** A paragraph that opens with a bold caveat ("**Not qualified for fabrication.**", "**Never …**"): a limit is never folded away. */
export const isCaveat = el => el.tagName === 'P' && el.firstChild?.tagName === 'STRONG' && CAVEAT.test(el.firstChild.textContent.trim());
const CAVEAT = /^(not|no|never|do not|don't|unsafe|warning|caution|danger|until|nothing)\b|\bnot (yet )?(structurally |physically )?(qualified|approved|recommended|tested|printed|validated|verified|safe|released|evidence|for fabrication)\b/i;
/** Kept in view where it stands: a model's preview action, or a caveat. */
const isKept = el => isModelAction(el) || isCaveat(el);
/** A link to one of this site's own model files (model-links.js previews only those, never another site's). */
export const isModelLink = href => MODEL_FILE.test(href) && !/^([a-z][a-z0-9+.-]*:|\/\/)/i.test(href);

// ---- status strips ----------------------------------------------------------------------------------------------
const STATE_COLUMN = /^(status|verdict|result|state)$/i;
/** The kind of a short status word, for its colour: good, work, bad, todo, muted, or other. */
export function statusKind(word) {
  const w = word.toLowerCase();
  if (/^(done|pass(ed|es)?|met|ok|implemented|closed|decided|verified|clear|ordered|bought|received|complete[d]?|yes|resolved|built|green|fixed)\b/.test(w)) return 'good';
  if (/^(fail(ed|s)?|fix|block(ed|s)?|rejected|unsafe|no|red|below|missing|broken|over)\b/.test(w)) return 'bad';
  if (/^(partial|warn(ing)?|specified|ongoing|in progress|draft|pending|candidate|amber|review|checking|started|wip|provisional|held|owner)\b/.test(w)) return 'work';
  if (/^(open|todo|to do|planned|not (yet|started|measured|done)|unknown|tbd|next|proposed|check)\b/.test(w)) return 'todo';
  if (/^(dropped|superseded|historical|archived|n\/a|withdrawn|retired|replaced|deferred|moot)\b/.test(w)) return 'muted';
  if (/^(note[ds]?|info|noted)\b/.test(w)) return 'note';
  return 'other';
}
/** A row's state: its status cell's first clause, lower case, if it is short. */
export const statusKey = cell => cell.replace(/\s+/g, ' ').trim().split(/[;:,(—–.]| - /)[0].trim().toLowerCase().replace(/[*`_]/g, '');

/** Counts for a table with a state column of short values, or null. */
export function tableStates(table) {
  const head = [...(table.querySelector('thead tr') || table.querySelector('tr'))?.children || []].map(th => th.textContent.trim());
  const col = head.findIndex(h => STATE_COLUMN.test(h));
  if (col < 0) return null;
  const cells = [...table.querySelectorAll('tbody tr')].map(tr => tr.children[col]?.textContent || '');
  const keys = cells.filter(s => s.trim()).map(statusKey), blank = cells.length - keys.length;
  if (keys.length < 4) return null;
  if (keys.some(k => !k || k.split(' ').length > 3 || k.length > 24)) return null;
  const counts = new Map();
  for (const k of keys) counts.set(k, (counts.get(k) || 0) + 1);
  if (counts.size > 7) return null;
  // Only a real status scale: at least three rows in four use a word the scale knows (done, open, pass, fail...).
  // A table of states that are names (safe, armed, firing) or numbers is not counted.
  if (keys.filter(k => statusKind(k) !== 'other').length < 0.75 * keys.length) return null;
  const order = ['good', 'note', 'work', 'other', 'todo', 'bad', 'muted'];
  const states = [...counts].map(([key, n]) => ({ key, n, kind: statusKind(key) }));
  // A row with no status is counted too, as one not yet stated, so the bar covers the whole table.
  if (blank) states.push({ key: 'no status', n: blank, kind: 'todo' });
  states.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind) || b.n - a.n);
  return { column: head[col], rows: cells.length, states };
}
function stripHTML({ column, rows, states }) {
  return `<figure class="doc-strip" data-visual data-generated="tools/doc-page.mjs"><figcaption><b>${plural(rows, 'row')}</b> by ${esc(column.toLowerCase())}, counted from the table below</figcaption>`
    + `<div class="doc-strip-bar" aria-hidden="true">${states.map(s => `<i data-k="${s.kind}" style="--w:${(100 * s.n / rows).toFixed(2)}%" title="${esc(s.key)}: ${s.n}"></i>`).join('')}</div>`
    + `<ul class="doc-strip-legend">${states.map(s => `<li data-k="${s.kind}"><b>${s.n}</b> ${esc(s.key)}</li>`).join('')}</ul></figure>`;
}

// ---- the lead card ------------------------------------------------------------------------------------------------
const meterHTML = m => {
  const of = m.bar?.of || 0;
  const bar = of ? m.bar.segments.map(s => `<i data-k="${s.k}" style="--w:${(100 * s.n / of).toFixed(2)}%"></i>`).join('') : '<i data-k="unknown" style="--w:100%"></i>';
  return `<li data-state="${esc(m.state)}"><span class="doc-meter-label">${esc(m.label)}</span> <b>${esc(m.value)}</b> <small>${esc(m.unit || '')}</small><span class="doc-meter-bar" aria-hidden="true">${bar}</span></li>`;
};
function cardHTML({ file, changed, text, sections, figures, tables, panel }) {
  const minutes = Math.max(1, Math.round(words(text) / 230));
  const facts = [
    changed ? `Changed <time datetime="${esc(changed.date)}">${shortDate(changed.date)}</time> · <a href="https://github.com/Valpatel/gyropup/commit/${esc(changed.commit)}">${esc(changed.commit.slice(0, 7))}</a>` : null,
    `${minutes} min read`, sections.length ? plural(sections.length, 'section') : null, figures ? plural(figures, 'picture') : 'no pictures yet', tables ? plural(tables, 'table') : null,
    `<a href="https://github.com/Valpatel/gyropup/blob/main/${esc(file)}">${esc(file)}</a>`,
  ].filter(Boolean);
  const jump = sections.length > 1 && !sections.every(s => s.outline) ? `<nav class="doc-sections" aria-label="Sections">${sections.map(s => `<a href="#${esc(s.id)}"${s.folded ? ' data-folded' : ''}>${esc(s.title)}</a>`).join('')}</nav>` : '';
  const live = panel ? `<div class="doc-live"><a class="doc-live-shot" href="/designer/progress.html#board-${esc(panel.id)}"><img src="${esc(panel.image.src)}" width="${panel.image.width}" height="${panel.image.height}" alt="${esc(panel.image.alt)}" loading="lazy" decoding="async"></a>`
    + `<div><p class="doc-live-title"><b>${esc(panel.name)} today</b>, from its records${panel.changed ? ` (changed ${shortDate(panel.changed.date)})` : ''}</p><ul class="doc-meters">${panel.meters.filter(m => m.bar).slice(0, 3).map(meterHTML).join('')}</ul>`
    + `<a class="doc-live-more" href="/designer/progress.html#board-${esc(panel.id)}">The ${esc(panel.name.toLowerCase())} on the status board →</a></div></div>` : '';
  return `<aside class="doc-card${panel ? ' has-live' : ''}" data-generated="tools/doc-page.mjs"><p class="doc-facts">${facts.map(f => `<span>${f}</span>`).join('')}</p>${jump}${live}</aside>`;
}

// ---- folds --------------------------------------------------------------------------------------------------------
// A stretch is the run of prose between two pictures, across section headings. Each stretch is shown at the lightest
// level that brings it under TARGET_PX: 0 keeps each section's opening (up to KEEP_PX) and folds the rest; 1 keeps
// only a short first paragraph; 2 keeps only the section's heading, as the fold's summary.
export const TARGET_PX = 880;
const SUMMARY_PX = 62, H2_PX = 80, SHORT_PX = 150;
const textHeight = blocks => blocks.reduce((h, el) => h + blockHeight(el), 0);
const isHeading = el => /^H[3-6]$/.test(el.tagName);
/** How many of a piece's blocks stay in view at a level. */
function keepCount(piece, level) {
  const { blocks } = piece;
  if (level === 2 && piece.h2 && !piece.section.actions) return 0;
  if (level === 2) level = 1; // the note's own opening, before its first section, keeps a short first paragraph
  if (level === 1) return blocks[0]?.tagName === 'P' && words(blocks[0].textContent) >= 8 && blockHeight(blocks[0]) <= SHORT_PX && textHeight(blocks) > SHORT_PX + 200 ? 1 : (textHeight(blocks) <= SHORT_PX ? blocks.length : 0);
  if (textHeight(blocks) <= FOLD_PX) return blocks.length;
  let kept = 0, i = 0;
  while (i < blocks.length) {
    const h = blockHeight(blocks[i]);
    if (i > 0 && kept + h > KEEP_PX) break;
    if (i === 0 && h > KEEP_PX && (blocks[i].tagName === 'PRE' || blocks[i].classList.contains('table-scroll'))) break;
    kept += h; i++;
  }
  while (i > 0 && isHeading(blocks[i - 1])) i--;
  return textHeight(blocks.slice(i)) < 200 ? blocks.length : i;
}
function pieceHeight(piece, level) {
  const n = keepCount(piece, level), folded = n < piece.blocks.length;
  if (level === 2 && piece.h2 && !piece.section.actions) return piece.blocks.length ? 56 : H2_PX;
  return (piece.h2 ? H2_PX : 0) + textHeight(piece.blocks.slice(0, n)) + (folded ? SUMMARY_PX : 0);
}
const describe = (blocks, { headings = true } = {}) => {
  const text = blocks.map(el => el.textContent).join(' ');
  const tables = blocks.filter(el => el.classList.contains('table-scroll')).length;
  const heads = blocks.filter(isHeading).map(el => el.textContent.trim());
  const models = blocks.reduce((n, el) => n + modelLinks(el), 0);
  return [plural(words(text), 'word'), tables ? plural(tables, 'table') : null, models ? `${models} 3D ${models === 1 ? 'model' : 'models'}` : null, headings && heads.length ? heads.slice(0, 3).join(' · ') + (heads.length > 3 ? ' …' : '') : null].filter(Boolean).join(' · ');
};
function foldPiece(document, piece, level) {
  const n = keepCount(piece, level), rest = piece.blocks.slice(n);
  if (!rest.length) return false;
  const details = document.createElement('details');
  if (level === 2 && piece.h2 && !piece.section.actions) {
    // The heading is the summary: the section reads as one line of an outline until opened.
    details.className = 'doc-fold doc-section';
    piece.h2.before(details);
    const summary = document.createElement('summary');
    summary.append(piece.h2);
    summary.insertAdjacentHTML('beforeend', `<small>${esc(describe(rest, { headings: false }))}</small>`);
    details.append(summary);
  } else {
    details.className = 'doc-fold';
    details.innerHTML = `<summary><span class="doc-fold-label">${n || piece.h2 ? 'The rest of' : 'Show'}</span> <b>${esc(piece.title)}</b> <small>${esc(describe(rest))}</small></summary>`;
    rest[0].before(details);
  }
  for (const el of rest) details.append(el);
  return true;
}

/** The enhanced article HTML and a summary of what changed in its presentation. */
/** Notes shown whole: a safety note's rules and emergency steps are never one click away. */
export const SHOWN_WHOLE = /(^|\/)[^/]*safety[^/]*\.md$/i;

export function enhanceDocument(html, { file, changed = null, panel = null } = {}) {
  const { document } = parseHTML(`<!doctype html><html><body><article>${html}</article></body></html>`);
  const article = document.querySelector('article');
  // Strips first, so they count as pictures when stretches are cut.
  let strips = 0;
  for (const scroll of article.querySelectorAll('.table-scroll')) {
    const states = tableStates(scroll.querySelector('table'));
    if (!states) continue;
    scroll.insertAdjacentHTML('beforebegin', stripHTML(states));
    strips++;
  }
  const blocks = [...article.children];
  const h1 = blocks.findIndex(el => el.tagName === 'H1');
  const title = (h1 >= 0 ? blocks[h1].textContent.trim() : '') || file;
  const lede = /^(P|BLOCKQUOTE)$/.test(blocks[h1 + 1]?.tagName) && !isVisual(blocks[h1 + 1]) ? blocks[h1 + 1] : null;
  // Pieces: the blocks of one section between pictures; stretches: the pieces between pictures.
  const sections = [], stretches = [[]];
  let section = { title, id: null }, piece = null;
  const open = h2 => { piece = { title: section.title, section, h2, blocks: [] }; stretches.at(-1).push(piece); };
  for (const [i, el] of blocks.entries()) {
    if (i <= h1 || el === lede) continue;
    if (el.tagName === 'H2') { section = { title: el.textContent.trim(), id: el.id }; sections.push(section); open(el); continue; }
    if (isVisual(el)) { piece = null; stretches.push([]); continue; }
    // Stays in place and ends the piece before it; its height still counts against the stretch it sits in.
    if (isKept(el)) { piece = null; section.actions = true; stretches.at(-1).kept = (stretches.at(-1).kept || 0) + blockHeight(el); continue; }
    if (!piece) open(null);
    piece.blocks.push(el);
  }
  // The title, lede and card open the first stretch, unless the card shows the part.
  const head = H2_PX + (lede ? blockHeight(lede) : 0) + (panel ? -Infinity : 170);
  let folds = 0;
  const whole = SHOWN_WHOLE.test(file || '');
  for (const [n, stretch] of whole ? [] : stretches.entries()) {
    const base = n === 0 ? Math.max(0, head) : 0;
    const level = [0, 1, 2].find(l => base + (stretch.kept || 0) + stretch.reduce((h, p) => h + pieceHeight(p, l), 0) <= TARGET_PX) ?? 2;
    for (const p of stretch) if (foldPiece(document, p, level)) { folds++; p.section.folded = true; if (level === 2 && p.h2 && !p.section.actions) p.section.outline = true; }
  }
  // Four or more folded sections in a row read as an outline: laid out two to a row on a wide screen (web/doc-page.css).
  let outline = [];
  const wrap = () => {
    if (outline.length >= 4) { const grid = document.createElement('div'); grid.className = 'doc-outline'; outline[0].before(grid); grid.append(...outline); }
    outline = [];
  };
  for (const el of [...article.children]) { if (el.matches('details.doc-section')) outline.push(el); else wrap(); }
  wrap();
  const text = article.textContent;
  const figures = article.querySelectorAll('img, video, pre.mermaid, code.language-mermaid').length;
  const tables = article.querySelectorAll('table').length;
  const card = cardHTML({ file, changed, text, sections, figures, tables, panel });
  const anchor = lede || blocks[h1];
  if (anchor) anchor.insertAdjacentHTML('afterend', card); else article.insertAdjacentHTML('afterbegin', card);
  return { html: article.innerHTML, folds, strips, sections: sections.length, live: !!panel };
}

/** The frame's script: a link or address to a folded heading opens its fold. */
export const OPEN_FOLDS = `const openTo=id=>{let k=id;try{k=decodeURIComponent(id);}catch{}const t=k&&document.getElementById(k);for(let d=t?.closest('details');d;d=d.parentElement.closest('details'))d.open=true;return t;};const go=()=>{const t=openTo(location.hash.slice(1));if(t)t.scrollIntoView();};addEventListener('hashchange',go);if(location.hash)go();`;
