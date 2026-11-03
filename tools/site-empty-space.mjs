/** Empty space: no published page may show a reader a large blank stretch as they scroll, at any screen size.
 * The owner (2026-11-03): gyropup.com "has large empty sections of the screen … on mobile"; wanted: "generalized
 * 'empty space' type tests for all resolutions to make sure our pages are well balanced visually and don't have odd
 * large empty spaces when scrolling down them." tools/test-empty-space.mjs runs these measures on every page in dist/
 * at a phone, an iPhone, a tablet, a small laptop and a desktop, in the light and the dark theme.
 *
 * Three findings, each named by the elements around it so a failure says where to look:
 *
 *  gap      The longest vertical band of the page with nothing in it, as a fraction of the screen's height. The page
 *           is scrolled one screen at a time first, like a reader, so lazy pictures load. Content is what a reader
 *           can see: text, <img>, <svg>, <video>, <canvas>, <iframe>, form controls, [data-visual], and boxes painted
 *           with a picture (a background url()). Borders, rules, flat fills, gradients and the dark theme's
 *           graph-paper grid are not content, and neither is anything thinner than MIN_THICKNESS (a hairline rule
 *           drawn as an <svg> or a 1 px column). The page is measured from its top, so a fixed or sticky header
 *           counts where a reader first meets it (on a page that does not scroll, like the simulator, the fixed layer
 *           is the page); fixed and sticky elements are hidden for the screenshots, since they float over every band.
 *           Inside a sideways scroller (a wide table) the columns off to the side still count for the rows' height.
 *           A band the DOM calls empty is then checked in a screenshot: a row of
 *           pixels is busy when it has at least BUSY_EDGES sharp left-to-right colour changes (text, a picture), so a
 *           pseudo-element drawing or a background the DOM cannot see keeps the band from failing. Flat fills,
 *           gradients, 1 px rules and the 3.5 %-alpha grid make no sharp changes, so they never hide a gap. A gap
 *           fails only when both say it is empty over the limit.
 *  blank    An <img>, <video> or <canvas> at least MEDIA_MIN px on each side, scrolled into view, whose painted pixels
 *           are one flat colour (FLAT_SHARE of them within FLAT_TOLERANCE of the commonest colour): a picture box a
 *           reader sees as empty. An image that never loads once in view counts too.
 *  column   Text squeezed into a box narrower than NARROW_SHARE of the screen that wraps to about one word a line
 *           (at least three lines, at most WORDS_PER_LINE words a line), like a link column beside an empty area.
 *           Table cells are left out: a table sizes its columns by their content and scrolls sideways when it must.
 *
 * The limits, as a fraction of the screen's height (innerHeight), from all 117 pages measured before and after the
 * change that added this. Before, the landing page's section joins were the worst band at every size: 0.24-0.29 of a
 * phone screen and 0.26-0.35 of a wider one, and they read as empty screens. Ordinary spacing everywhere else (a
 * heading's margins, the top of a document under the app bar, the last fold above the footer) measured 0.09-0.15, the
 * same on all 112 design-note pages; after the fix the landing page's joins measure 0.13-0.16 on phones and 0.12-0.19
 * wider. A phone screen is short, so the same band is a larger share of it and reads as emptier; a wider screen shows
 * more beside the band. So phones fail over 0.18 and wider screens over 0.22: both sit between the ordinary spacing and
 * the joins the owner saw, with room for font and engine differences on either side.
 */

export const SIZES = [
  { name: 'phone-360', limit: 0.18, context: { viewport: { width: 360, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } },
  { name: 'iphone-13', limit: 0.18, device: 'iPhone 13' },
  { name: 'tablet-768', limit: 0.22, context: { viewport: { width: 768, height: 1024 }, deviceScaleFactor: 1, hasTouch: true } },
  { name: 'laptop-1024', limit: 0.22, context: { viewport: { width: 1024, height: 768 }, deviceScaleFactor: 1 } },
  { name: 'desktop-1440', limit: 0.22, context: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 } },
];
export const SCHEMES = ['light', 'dark'];

export const MIN_THICKNESS = 8;   // px: a box thinner than this in either direction is a rule, not content
export const BUSY_EDGES = 10;     // sharp colour changes in one row of pixels that make it a row with something in it
export const EDGE_STEP = 28;      // a sharp change: this much (0-255) on one channel between neighbouring pixels
export const MEDIA_MIN = 64;      // px: smaller pictures are icons
export const FLAT_SHARE = 0.995;  // a picture is blank when this share of its pixels ...
export const FLAT_TOLERANCE = 12; // ... is within this much (0-255, per channel) of its commonest colour
export const NARROW_SHARE = 0.2;  // a text box narrower than this share of the screen's width ...
export const WORDS_PER_LINE = 1.5; // ... wrapping to at most this many words a line (three lines or more)

/** Run in the page (page.evaluate(scanLayout, options)): where the content is, the gaps between it, the pictures to
 * check for blank paint and the squeezed text columns. Coordinates are CSS px from the top of the document. */
export function scanLayout({ minThickness, narrowShare, wordsPerLine, mediaMin, minGap }) {
  scrollTo(0, 0);
  // Measured from the top of the page, so a fixed or sticky header sits where a reader first sees it, above the content
  // it later floats over (and on a page that does not scroll, like the simulator, the fixed layer is the page).
  const vw = innerWidth, vh = innerHeight, sy = 0, sx = 0;
  const docH = Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight || 0);
  const named = (el, words = true) => {
    if (!el || el.nodeType !== 1) return '(page edge)';
    const cls = [...el.classList].slice(0, 2).map(c => '.' + c).join('');
    const text = words ? (el.getAttribute('alt') || el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40) : '';
    return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${cls}${text ? ` "${text}"` : ''}`;
  };
  const style = new Map(), css = el => { let s = style.get(el); if (!s) style.set(el, s = getComputedStyle(el)); return s; };
  // What an element's content is clipped to: every ancestor that hides its overflow.
  const clipCache = new Map();
  const clipOf = el => {
    if (!el || el === document.documentElement || el === document.body) return [-1e9, -1e9, 1e9, 1e9];
    if (clipCache.has(el)) return clipCache.get(el);
    let c = clipOf(el.parentElement);
    const s = css(el);
    if (s.overflowX !== 'visible' || s.overflowY !== 'visible' || (s.clip && s.clip !== 'auto') || /paint|strict|content/.test(s.contain)) {
      // A sideways scroller (a wide table) hides columns the reader scrolls to, and its rows are as tall as their
      // tallest cell: what it holds counts for its height, not its width.
      const r = el.getBoundingClientRect(), sideways = /auto|scroll/.test(s.overflowX);
      c = [sideways ? c[0] : Math.max(c[0], r.left), Math.max(c[1], r.top), sideways ? c[2] : Math.min(c[2], r.right), Math.min(c[3], r.bottom)];
    }
    clipCache.set(el, c); return c;
  };
  const seen = el => el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true, checkOpacity: true, checkVisibilityCSS: true });
  const boxes = [];
  const add = (el, r, clipEl) => {
    const c = clipOf(clipEl);
    const left = Math.max(r.left, c[0]), right = Math.min(r.right, c[2]), top = Math.max(r.top, c[1]), bottom = Math.min(r.bottom, c[3]);
    if (right - left < minThickness || bottom - top < minThickness / 2) return;
    if (right <= -sx || left >= document.documentElement.scrollWidth) return;
    boxes.push({ top: top + sy, bottom: bottom + sy, el });
  };
  // Text.
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: n => /\S/.test(n.data) && !n.parentElement.closest('script,style,noscript,template,title') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
  });
  const range = document.createRange();
  const texts = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!seen(el) || css(el).color === 'rgba(0, 0, 0, 0)') continue;
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    // a glyph is never a rule, however narrow
    const c = clipOf(el), top = Math.max(r.top, c[1]), bottom = Math.min(r.bottom, c[3]);
    if (bottom - top < 4 || Math.min(r.right, c[2]) - Math.max(r.left, c[0]) < 2) continue;
    boxes.push({ top: top + sy, bottom: bottom + sy, el });
    texts.push(n);
  }
  // Pictures, controls, and anything that says it is a picture.
  const MEDIA = 'img, svg, video, canvas, iframe, object, embed, input:not([type=hidden]), select, textarea, button, progress, meter, [data-visual], .cad-diagram';
  const media = [];
  for (const el of document.body.querySelectorAll(MEDIA)) {
    if (el.matches("svg *") || !seen(el)) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    add(el, r, el.parentElement);
    // What of it can show: inside its clipping ancestors (a sideways scroller shows a few of its pictures) and the screen.
    const c = clipOf(el.parentElement);
    const left = Math.max(r.left, c[0], 0), right = Math.min(r.right, c[2], vw), top = Math.max(r.top, c[1]), bottom = Math.min(r.bottom, c[3]);
    if (el.matches('img, video, canvas') && right - left >= mediaMin && bottom - top >= mediaMin) {
      const loaded = el.tagName === 'IMG' ? el.complete && el.naturalWidth > 0 : el.tagName === 'VIDEO' ? el.readyState >= 2 || !!el.getAttribute('poster') : el.width > 0 && el.height > 0;
      media.push({ top: top + sy, left: left + sx, width: right - left, height: bottom - top, loaded, name: named(el), src: (el.currentSrc || el.getAttribute('src') || '').split('/').pop().slice(0, 60) });
    }
  }
  // Boxes painted with a picture (a background url(), not a gradient).
  for (const el of document.body.querySelectorAll('*')) {
    const bg = css(el).backgroundImage;
    if (!bg || bg === 'none' || !bg.includes('url(') || !seen(el)) continue;
    add(el, el.getBoundingClientRect(), el.parentElement);
  }
  // The gaps between them.
  boxes.sort((a, b) => a.top - b.top);
  const gaps = [];
  let at = 0, last = null;
  for (const b of boxes) {
    if (b.top - at >= minGap) gaps.push({ from: at, to: b.top, above: last, below: b.el });
    if (b.bottom > at) { at = b.bottom; last = b.el; }
  }
  if (docH - at >= minGap) gaps.push({ from: at, to: docH, above: last, below: null });
  const heading = y => {
    const hs = [...document.querySelectorAll('h1, h2, h3, .eyebrow')].filter(h => seen(h) && h.getBoundingClientRect().top + sy <= y + 1);
    return hs.at(-1)?.textContent.trim().replace(/\s+/g, ' ').slice(0, 60) || '(top)';
  };
  // Squeezed text: about one word a line in a box narrower than narrowShare of the screen.
  const columns = [];
  const blockOf = el => { while (el && el !== document.body && /^inline|^contents$/.test(css(el).display) && css(el).display !== 'inline-block' && css(el).display !== 'inline-flex' && css(el).display !== 'inline-grid') el = el.parentElement; return el; };
  const reported = new Set();
  for (const n of texts) {
    const words = n.data.match(/[\p{L}\p{N}][\p{L}\p{N}'’.\-]*/gu) || [];
    if (words.length < 3) continue;
    const box = blockOf(n.parentElement);
    // A table's columns are sized by its content, and it scrolls sideways when it must: a tall cell is the table's
    // trade-off, not text squeezed beside an empty area.
    if (!box || reported.has(box) || box.closest('td, th, caption')) continue;
    const width = box.getBoundingClientRect().width;
    if (width >= narrowShare * vw) continue;
    range.selectNodeContents(n);
    const tops = [];
    for (const r of range.getClientRects()) if (r.width > 0 && !tops.some(t => Math.abs(t - r.top) < 3)) tops.push(r.top);
    if (tops.length < 3 || words.length / tops.length > wordsPerLine) continue;
    reported.add(box);
    const r = box.getBoundingClientRect();
    columns.push({ top: r.top + sy, left: r.left + sx, width: Math.round(width), height: Math.round(r.height), lines: tops.length, words: words.length, name: named(box), heading: heading(r.top + sy) });
  }
  return {
    vw, vh, docH, scrolls: docH > vh + 1, contentBoxes: boxes.length, media, columns,
    gaps: gaps.map(g => ({ from: Math.round(g.from), to: Math.round(g.to), size: Math.round(g.to - g.from), above: named(g.above), below: g.below ? named(g.below) : '(page end)', heading: heading(g.from) })),
  };
}

/** Run in a blank page (analysis.evaluate(paintedPixels, {png, jobs, ...})): decode a screenshot and answer, for each
 * job, either the longest run of quiet rows in a band ({band:[y0, y1]}) or whether a box is one flat colour
 * ({box:[x, y, w, h]}). Coordinates are CSS px in the screenshot (taken with scale: 'css'). */
export async function paintedPixels({ png, jobs, busyEdges, edgeStep, flatTolerance }) {
  const bytes = Uint8Array.from(atob(png), c => c.charCodeAt(0));
  const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
  const W = bitmap.width, H = bitmap.height;
  const canvas = new OffscreenCanvas(W, H), g = canvas.getContext('2d', { willReadFrequently: true });
  g.drawImage(bitmap, 0, 0);
  const px = g.getImageData(0, 0, W, H).data;
  const out = [];
  for (const job of jobs) {
    if (job.band) {
      const y0 = Math.max(0, Math.round(job.band[0])), y1 = Math.min(H, Math.round(job.band[1]));
      let run = 0, best = 0, bestFrom = y0;
      for (let y = y0; y < y1; y++) {
        let edges = 0;
        for (let x = 1, i = (y * W + 1) * 4; x < W; x++, i += 4) {
          if (Math.max(Math.abs(px[i] - px[i - 4]), Math.abs(px[i + 1] - px[i - 3]), Math.abs(px[i + 2] - px[i - 2])) > edgeStep && ++edges >= busyEdges) break;
        }
        if (edges >= busyEdges) run = 0;
        else if (++run > best) { best = run; bestFrom = y - run + 1; }
      }
      out.push({ quiet: best, from: bestFrom });
    } else {
      // inset 2 px: a rounded corner or a border is not the picture
      const x0 = Math.max(0, Math.round(job.box[0]) + 2), y0 = Math.max(0, Math.round(job.box[1]) + 2);
      const x1 = Math.min(W, Math.round(job.box[0] + job.box[2]) - 2), y1 = Math.min(H, Math.round(job.box[1] + job.box[3]) - 2);
      const counts = new Map();
      for (let y = y0; y < y1; y++) for (let x = x0, i = (y * W + x) * 4; x < x1; x++, i += 4) {
        const k = (px[i] >> 3) << 10 | (px[i + 1] >> 3) << 5 | px[i + 2] >> 3;
        counts.set(k, (counts.get(k) || 0) + 1);
      }
      let mode = 0, most = -1;
      for (const [k, n] of counts) if (n > most) { most = n; mode = k; }
      const c = [((mode >> 10) & 31) * 8 + 4, ((mode >> 5) & 31) * 8 + 4, (mode & 31) * 8 + 4];
      let near = 0, all = 0;
      for (let y = y0; y < y1; y++) for (let x = x0, i = (y * W + x) * 4; x < x1; x++, i += 4, all++)
        if (Math.abs(px[i] - c[0]) <= flatTolerance && Math.abs(px[i + 1] - c[1]) <= flatTolerance && Math.abs(px[i + 2] - c[2]) <= flatTolerance) near++;
      out.push({ flat: all ? near / all : 1, colour: `rgb(${c.join(',')})` });
    }
  }
  return out;
}

