/** Walls of text: the longest vertical stretch of a page's content with no picture, diagram, chart or render in it,
 * measured in a real browser. The owner (2026-11-01): "too much of our gyropup site looks like run on AI commentary.
 * We want diagrams, graphics, status bars that show real designs and when they are changing."
 * tools/test-walls.mjs runs it on every published page at 1366 x 800 and holds each page under WALL_LIMIT, except the
 * pages in tools/wall-backlog.json, which may only shrink. The measure follows cad-agent's (its #179,
 * tests/site-walls.mjs), so both sites hold the same line.
 *
 * What counts as something to look at: an <img>, <svg>, <video>, <canvas>, <picture>, <iframe>, a rendered Mermaid
 * diagram (.cad-diagram), or anything marked [data-visual] (a status bar, a chart drawn in HTML), at least 120 x 80
 * px as laid out. An icon or a badge does not count, and a picture folded away in a closed <details> is not seen.
 * The content is a document page's <article>, else the page's <main>. A stretch runs from the content's top to the
 * first picture, between pictures (overlapping ones merge), and from the last picture to the content's end. The site
 * header and footer are outside the content, so they never count.
 */

export const VIEWPORT = { width: 1366, height: 800 };
export const WALL_LIMIT = 1.5 * VIEWPORT.height;      // 1200 px: about one and a half screens of reading, no picture
// A backlog page must leave the list once it measures under 1080 px. The band keeps a page from bouncing on and off
// the list with each small edit, and absorbs the engines' layout differences.
export const WALL_CLEARED = 0.9 * WALL_LIMIT;
export const VISUAL = 'img, svg, video, canvas, picture, iframe, .cad-diagram, [data-visual]';

/** Run in the page (page.evaluate(longestStretch, VISUAL)): { worst, from, to, after, visuals, height } in CSS px,
 * `from`/`to` from the content's top, `after` the last heading above the stretch (to say where to look). */
export function longestStretch(selector) {
  const content = document.querySelector('main.document article') || document.querySelector('article.prose') || document.querySelector('main');
  const box = content.getBoundingClientRect(), top = box.top + scrollY, bottom = box.bottom + scrollY;
  // Folded away: inside a closed <details> and not in its summary. Chrome can lay such content out (it is hidden by
  // content-visibility), so its size alone does not say the reader cannot see it.
  const folded = el => {
    for (let d = el.closest('details:not([open])'); d; d = d.parentElement?.closest('details:not([open])'))
      if (!d.querySelector(':scope > summary')?.contains(el)) return true;
    return false;
  };
  const hidden = el => { for (let n = el; n && n !== content; n = n.parentElement) { const s = getComputedStyle(n); if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return true; } return false; };
  const spans = [...content.querySelectorAll(selector)]
    .filter(el => (!el.parentElement.closest(selector) || el.matches('.cad-diagram')) && !folded(el) && !hidden(el))
    .map(el => el.getBoundingClientRect()).filter(r => r.width >= 120 && r.height >= 80)
    .map(r => [r.top + scrollY, r.bottom + scrollY]).sort((a, b) => a[0] - b[0]);
  let at = top, worst = 0, from = top;
  for (const [start, end] of spans) {
    if (start - at > worst) { worst = start - at; from = at; }
    at = Math.max(at, end);
  }
  if (bottom - at > worst) { worst = bottom - at; from = at; }
  const heads = [...content.querySelectorAll('h1, h2, h3')].filter(h => h.getBoundingClientRect().top + scrollY <= from + 1);
  return { worst: Math.round(worst), from: Math.round(from - top), to: Math.round(from - top + worst), visuals: spans.length,
    height: Math.round(bottom - top), after: heads.at(-1)?.textContent.trim().replace(/\s+/g, ' ').slice(0, 60) || '(top)' };
}

/** Run in the page: planted articles with known geometry, so the measure itself is tested on every run. */
export function plantedStretches(selector, longestStretch) {
  const make = html => {
    const host = Object.assign(document.createElement('main'), { className: 'document', style: 'position:absolute;left:0;top:0;width:800px;margin:0;padding:0' });
    host.innerHTML = `<article style="margin:0;padding:0">${html}</article>`;
    document.body.prepend(host);
    return host;
  };
  const text = px => `<p style="height:${px}px;margin:0">words</p>`;
  const pic = (w, h) => `<img alt="" width="${w}" height="${h}" style="display:block;width:${w}px;height:${h}px">`;
  const cases = {
    // 300 text, a picture, 1500 text, a picture, 200 text: the middle stretch decides
    between: [text(300) + pic(400, 200) + text(1500) + pic(400, 200) + text(200), 1500],
    // a 24 px icon and a 100 x 60 badge are not pictures, so the whole 2000 px (with their 84) is one stretch
    small: [text(900) + pic(24, 24) + pic(100, 60) + text(1016), 2000],
    // a picture folded away in a closed <details> is not seen; one in its summary is
    open: [text(700) + `<details open><summary style="height:20px;display:block">more</summary>${pic(400, 300)}</details>` + text(1000), 1000],
    folded: [text(700) + `<details><summary style="height:20px;display:block">more</summary>${pic(400, 300)}</details>` + text(700), 1420],
    summary: [text(700) + `<details><summary style="display:block">${pic(120, 90)}</summary>${pic(400, 300)}</details>` + text(600), 700],
    // a status strip drawn in HTML counts when it says so, once, however many bars it holds
    visual: [text(500) + `<div data-visual style="height:200px"><div data-visual style="height:90px"></div></div>` + text(800), 800],
  };
  const out = {};
  for (const [name, [html, want]] of Object.entries(cases)) {
    const host = make(html);                                      // first in the document, so it is the one measured
    out[name] = { got: longestStretch(selector).worst, want };
    host.remove();
  }
  return out;
}

/** The expression page.evaluate runs for plantedStretches, with longestStretch passed in. */
export const plantedScript = () => `(${plantedStretches})(${JSON.stringify(VISUAL)}, ${longestStretch})`;

/** Every published HTML page in dist/ that a reader opens: the entry pages and the design notebook's documents.
 * Generated directory listings and downloadable HTML artifacts are files, not pages. */
export function sitePages(files) {
  const entry = ['index.html', 'designer/progress.html', 'designer/build.html', 'designer/sim.html', 'site/index.html'];
  return [...entry.filter(f => files.includes(f)), ...files.filter(f => /^site\/pages\/[^/]+\.html$/.test(f)).sort()].map(f => '/' + f.replace(/(^|\/)index\.html$/, '$1'));
}
