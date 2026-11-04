// "Print these now": the motor-day print order (exports/motor-day/prints.csv, written by tools/motor_day.py) as a card at
// the top of the Build page, so the files to print are one click from the site's front door. Self-contained and
// fail-soft: if the CSV cannot be read, the card still links the plan and the package.
const R = '../';
const PLAN = `${R}site/pages/docs-motor-day-md.html`;
const ZIP = `${R}exports/motor-day/motor-day-package.zip`;
const CSV = `${R}exports/motor-day/prints.csv`;

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// RFC 4180 CSV: quoted fields may hold commas, doubled quotes and newlines.
export function parseCsv(text) {
  const rows = []; let row = [], field = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; } else if (c === '"') q = false; else field += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.some((f) => f !== '')) rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field); if (row.some((f) => f !== '')) rows.push(row);
  const [head = [], ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, j) => [h, r[j] ?? ''])));
}

const label = (key) => key.replace(/_pla$/, '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
const hours = (min) => `${(min / 60).toFixed(1)} h`;

// One line per print step: rows that share an `order` (the C1 coupons) become one line with every file listed.
export function steps(rows) {
  const by = new Map();
  for (const r of rows) {
    const n = Number(r.order); if (!Number.isFinite(n)) continue;
    const qty = Number(r.qty) || 1, min = Number(r.minutes_each) || 0, g = Number(r.grams_each) || 0;
    const s = by.get(n) || { order: n, items: [], minutes: 0, grams: 0, tpu: 0, phase: r.phase };
    s.items.push({ key: r.key, qty, file: r.file, how: r.how });
    s.minutes += qty * min;
    if (r.recipe === 'tpu') s.tpu += qty * g; else s.grams += qty * g;
    by.set(n, s);
  }
  return [...by.values()].sort((a, b) => a.order - b.order);
}

function name(s) {
  if (s.items.length > 1) {
    const base = s.items[0].key.startsWith('coupon_') ? 'Bore-fit coupons (C1)' : label(s.items[0].key);
    return `${base} ×${s.items.reduce((a, i) => a + i.qty, 0)}`;
  }
  const i = s.items[0];
  return `${label(i.key)}${i.qty > 1 ? ` ×${i.qty}` : ''}`;
}

function files(s) {
  if (s.items.length === 1) return `<a href="${esc(R + s.items[0].file)}" download>${esc(s.items[0].file.split('/').pop())}</a>`;
  return `<details><summary>${s.items.length} files</summary>${s.items.map((i) =>
    `<a href="${esc(R + i.file)}" download>${esc(i.file.split('/').pop())}</a>`).join('<br>')}</details>`;
}

export async function mountPrintNow(host, fetchImpl = fetch) {
  if (!host) return;
  const links = `<p class="print-now-links"><a href="${PLAN}">The motor-day plan (fit checks, assembly, tests) ↗</a>`
    + `<a href="${ZIP}" download>All print files (.zip)</a><a href="${CSV}" download>prints.csv</a></p>`;
  let body = '';
  try {
    const res = await fetchImpl(CSV, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const list = steps(parseCsv(await res.text()));
    if (!list.length) throw new Error('no rows');
    const tot = list.reduce((a, s) => ({ m: a.m + s.minutes, g: a.g + s.grams, t: a.t + s.tpu }), { m: 0, g: 0, t: 0 });
    body = `<ol class="print-now-list">`
      + list.map((s) => `<li data-order="${s.order}"><span class="num">${s.order}</span><span class="pn-part">${esc(name(s))}`
        + `${s.order <= 2 ? ' <span class="tag info">fit check</span>' : ''}</span><span class="pn-t">${hours(s.minutes)}</span>`
        + `<span class="pn-g">${s.tpu ? `${Math.round(s.tpu)} g TPU` : `${Math.round(s.grams)} g`}</span><span class="pn-f">${files(s)}</span></li>`).join('')
      + `<li class="pn-tot"><span></span><span class="pn-part">Total</span><span class="pn-t">${hours(tot.m)}</span>`
      + `<span class="pn-g">${(tot.g / 1000).toFixed(2)} kg PLA${tot.t ? ` + ${Math.round(tot.t)} g TPU` : ''}</span><span></span></li></ol>`;
  } catch (error) {
    body = '<p class="dim">The print list could not be loaded just now; the plan and the package above have every file.</p>';
  }
  host.innerHTML = `<div class="sec">Print these now: the first leg in PLA</div>`
    + `<p class="lede">The RS-04 motors are in. Print in this order: the two fit checks first, then the coupons, then the hip frame `
    + `once both fits pass. The plan says what to check after each print.</p>${links}${body}`;
  host.dataset.ready = '1';
}
