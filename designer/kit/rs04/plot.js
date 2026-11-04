// A small strip chart on a canvas: one trace, a window of the last N seconds, a value readout and optional limit
// lines. No dependencies. MIT licensed (LICENSE in this folder).

export function createStrip(parent, { title, unit = '', windowS = 10, min = null, max = null, limits = [], digits = 2 } = {}) {
  const box = document.createElement('figure');
  box.className = 'rs04-strip';
  box.innerHTML = `<figcaption><span class="rs04-strip-title"></span><output></output></figcaption><canvas></canvas>`;
  box.querySelector('.rs04-strip-title').textContent = title;
  parent.append(box);
  const canvas = box.querySelector('canvas'), out = box.querySelector('output');
  const pts = [];
  let lims = limits, dirty = true;

  function push(t, v) {
    if (!Number.isFinite(v)) return;
    pts.push([t, v]);
    while (pts.length && pts[0][0] < t - windowS) pts.shift();
    out.textContent = `${v.toFixed(digits)} ${unit}`;
    dirty = true;
  }
  function setLimits(l) { lims = l; dirty = true; }
  function clear() { pts.length = 0; out.textContent = '–'; dirty = true; later(); }
  const later = () => globalThis.requestAnimationFrame?.(() => draw());

  function draw() {
    if (!dirty || !canvas.isConnected) return;
    dirty = false;
    const dpr = globalThis.devicePixelRatio || 1, w = canvas.clientWidth || 300, h = canvas.clientHeight || 90;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    const g = canvas.getContext('2d');
    if (!g) return;
    const css = getComputedStyle(box);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const vals = pts.map(p => p[1]).concat(lims.map(l => l.value));
    let lo = min ?? Math.min(...vals, 0), hi = max ?? Math.max(...vals, 0);
    if (!(hi > lo)) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    const t1 = pts.length ? pts[pts.length - 1][0] : 0, t0 = t1 - windowS;
    const x = t => ((t - t0) / windowS) * w, y = v => h - ((v - lo) / (hi - lo)) * h;
    g.strokeStyle = css.getPropertyValue('--rs04-grid') || '#8884'; g.lineWidth = 1;
    g.beginPath(); g.moveTo(0, y(0)); g.lineTo(w, y(0));
    for (let s = Math.ceil(t0 / 2) * 2; s <= t1; s += 2) { g.moveTo(x(s), 0); g.lineTo(x(s), h); }   // a line every 2 s
    g.stroke();
    if (!pts.length) {
      g.fillStyle = css.getPropertyValue('--rs04-dim') || '#888'; g.font = '12px system-ui, sans-serif';
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(`no data yet: the last ${windowS} s show here`, w / 2, h / 2 - 12);
    }
    for (const l of lims) {
      g.strokeStyle = css.getPropertyValue('--rs04-limit') || '#d33'; g.setLineDash([4, 4]);
      g.beginPath(); g.moveTo(0, y(l.value)); g.lineTo(w, y(l.value)); g.stroke(); g.setLineDash([]);
    }
    g.strokeStyle = css.getPropertyValue('--rs04-trace') || '#2a8'; g.lineWidth = 1.6;
    g.beginPath();
    pts.forEach(([t, v], i) => (i ? g.lineTo(x(t), y(v)) : g.moveTo(x(t), y(v))));
    g.stroke();
  }
  later();
  return { push, clear, draw, setLimits, element: box };
}
