// Build page: everything to order and to print for the first physical prototype: one leg on its single-leg test rig
// (milestone M3, docs/leg-prototype-plan.md), the turret v0 on its bench stand (docs/turret-prototype-plan.md), and the
// body's first frame (docs/body-plan.md) once its files exist. Generated on every load from the repo's own data:
//   parts lists    exports/leg/bom.json (per_leg, made_to_order), exports/turret/bench/bom.json (bench_turret,
//                  bench_stand, tools; ordered_to_drawing), exports/rig/bom.json and exports/body/bom.json when present
//   print plans    exports/*/print-plan.json (parts, by_material)
//   catalogue      catalog/*.json (names, prices, packs, buy links), images.json (pictures), alternates.json,
//                  sourcing.json (plain-text lines, hard-to-buy notes, parts not in a catalogue file yet),
//                  materials.json (filament by the kilogram)
//   plans          the Primary column of the plans' parts tables picks an alternate seller over the catalogue's
//                  (Bearings Direct, VXB); docs/leg-prototype-plan.md 6.2 sets the leg's (and rig's) print order
// A line's picture, part number, buy link and alternates resolve as on the progress page (designer/progress.js:
// keysOf, thumb, altList and riskTag are copied from there). Nothing here is typed in by hand: no price, quantity,
// lead time or seller.
import { mountAppNav } from './kit/appnav.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// a file not generated yet answers 404: its short body is read so the request ends (an unread body keeps it open)
const fetchOk = async (u) => { try { const r = await fetch(u, { cache: 'no-store' }); if (r.ok) return r; await r.arrayBuffer(); return null; } catch { return null; } };
const getJson = async (u) => { const r = await fetchOk(u); try { return r ? await r.json() : null; } catch { return null; } };
const getText = async (u) => { const r = await fetchOk(u); try { return r ? await r.text() : null; } catch { return null; } };
const $ = (id) => document.getElementById(id);
const R = '../';                                            // the project root, from designer/
const round2 = (v) => Math.round(v * 100) / 100;            // cents: each line, then each seller, then the total
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const usd = (v) => (v == null ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const unit$ = (v) => (v == null ? '—' : v >= 1 ? usd(v) : `$${v.toFixed(4).replace(/(\.\d\d\d?)0+$/, '$1')}`);
const kg = (g) => (g / 1000).toFixed(2);
const plural = (n, w, p = `${w}s`) => `${n} ${n === 1 ? w : p}`;
const docPage = (f) => `${R}site/pages/${f.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}.html`;   // cad-agent site's slug
const mdSlug = (t) => t.normalize('NFKD').replace(/[^\x00-\x7f]/g, '').replace(/[^\w\s-]/g, '').trim().toLowerCase().replace(/[-\s]+/g, '-');

await mountAppNav({ root: R, current: 'build' });

// ------------------------------------------------------------------------------------------------ the workstreams
// The first prototype's three workstreams (the rig is the leg's, kept apart because its files come from its own branch).
const STREAMS = [
  { id: 'leg', title: 'One leg (milestone M3)', plan: 'docs/leg-prototype-plan.md', sec: '6.1', bom: 'exports/leg/bom.json',
    print: ['exports/leg/print-plan.json'], order62: true,
    lists: { per_leg: 'leg' }, about: 'Leg v2: the hip frame, the links, two RS-04s and the BotWheel; qty for one leg.' },
  { id: 'rig', title: 'The single-leg test rig', plan: 'docs/leg-prototype-plan.md', sec: '6.1', bom: 'exports/rig/bom.json',
    print: ['exports/rig/print-plan.json', 'exports/rig/bench/print-plan.json'], order62: true, lists: {},
    about: 'The rail, post, base, carriage plate, bench fixtures and the electronics the leg is tested with.',
    pending: 'exports/rig/bom.json, print-plan.json, catalog/rig.json and docs/leg-rig-orders.md come from the rig workstream (plan section 7, T1 to T5).' },
  { id: 'turret', title: 'Turret v0 on its bench stand', plan: 'docs/turret-prototype-plan.md', sec: '3.3', bom: 'exports/turret/bench/bom.json',
    print: ['exports/turret/bench/print-plan.json'], lists: { bench_turret: 'turret', bench_stand: 'stand', tools: 'tools' },
    about: 'The turret with its stand, inlet, fuse, switch, USB-CAN and hold-to-run pendant; qty for one turret.' },
  { id: 'body', title: "The body's first frame", plan: 'docs/body-plan.md', sec: '8', bom: 'exports/body/bom.json',
    print: ['exports/body/print-plan.json'], lists: {},
    about: 'The spine, floor tray, deck and belly plates, the battery and power parts (P0 the power skid, P1 the open frame).',
    pending: 'exports/body/bom.json and print-plan.json come from the body workstream (plan section 5, T8).' },
];
const SKIP_LIST = /^(v1|not_|no_|to_source|cad_pending|made_to_order|ordered_to_drawing)/;   // not bought for this build
const FAB = /sendcutsend|jlccnc|xometry|jlcpcb|pcbway/i;    // custom parts ordered from our files (D40)

for (const s of STREAMS) {
  s.bomData = await getJson(R + s.bom);
  s.plans = [];
  for (const f of s.print) {
    if (f.includes('/bench/print-plan') && s.id === 'rig' && !s.plans.length && !s.bomData) continue;   // only once the rig exists
    const p = await getJson(R + f);
    if (p) s.plans.push({ file: f, data: p });
  }
  s.present = !!(s.bomData || s.plans.length);
}
const turretJson = STREAMS.find((s) => s.id === 'turret').present ? await getJson(`${R}exports/turret/turret.json`) : null;
// the turret's own STEP and STL files are written by cad/turret.py and not kept in git: the local server's listing of
// exports/turret/ says which are on this machine, so the page links only those
const turretFiles = new Set(turretJson ? [...((await getText(`${R}exports/turret/`)) || '').matchAll(/href="([^"?#]+\.(?:stl|step))"/gi)]
  .map((m) => decodeURIComponent(m[1])) : []);

// ------------------------------------------------------------------------------------------------ the catalogue
const media = await (async () => {
  const [images, alternates, sourcing, index, materials] = await Promise.all(['images', 'alternates', 'sourcing', 'index', 'materials']
    .map((f) => getJson(`${R}catalog/${f}.json`)));
  const files = new Set(['hardware.json', ...((index && index.files) || [])]);
  if (STREAMS.find((s) => s.id === 'rig').present) files.add('rig.json');            // the rig's parts (its task T1)
  const items = {};
  for (const list of await Promise.all([...files].map((f) => getJson(`${R}catalog/${f}`)))) {
    for (const it of Array.isArray(list) ? list : []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = it;
  }
  for (const it of (sourcing && sourcing.parts) || []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = { ...it, pending: true };
  return { images: images || {}, alternates: alternates || {}, sourcing: sourcing || {}, materials: materials || {}, items };
})();

// a parts-list line -> its catalogue keys (progress.js keysOf)
const keysOf = (r) => {
  if (r.media_key) return [r.media_key, ...(r.also || []).map((a) => a.media_key)];
  for (const c of [r.key, r.id]) if (c && media.items[c]) return [c];
  const names = media.sourcing.names || {};
  for (const c of [r.item, r.name, r.for, r.key]) if (c && names[c] !== undefined) return [].concat(names[c]);
  return [];
};

// ------------------------------------------------------------------------------------------------ the plans
// Markdown tables with the heading they sit under: the plans' parts tables (a Primary column) and the leg's print days.
const mdTables = (md) => {
  const out = [];
  let heading = '', cur = null;
  for (const line of (md || '').split('\n')) {
    const h = /^#{1,6}\s+(.*)$/.exec(line);
    if (h) { heading = h[1].trim(); cur = null; continue; }
    const t = line.trim();
    if (!t.startsWith('|')) { cur = null; continue; }
    const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
    if (!cur) { cur = { heading, header: cells.map((c) => c.toLowerCase()), rows: [] }; out.push(cur); }
    else if (!cells.every((c) => /^:?-{3,}:?$/.test(c))) cur.rows.push(cells);
  }
  return out;
};
const words = (s) => ` ${String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()} `;
const plans = {};
for (const f of [...new Set(STREAMS.map((s) => s.plan))]) plans[f] = { md: await getText(R + f) };
for (const p of Object.values(plans)) p.tables = mdTables(p.md);
const secOf = (heading) => (/^(\d+(?:\.\d+)*)\.?\s/.exec(heading) || [])[1] || '';
const secLink = (f, sec) => {
  const t = (plans[f] && plans[f].md ? plans[f].md.split('\n') : []).map((l) => /^#{1,6}\s+(.*)$/.exec(l)).find((m) => m && secOf(m[1].trim()) === sec);
  return `${docPage(f)}${t ? `#${mdSlug(t[1].trim())}` : ''}`;
};

// The plan's Primary column names one of a part's alternates (catalog/alternates.json) when it starts with (or names)
// that seller and the row names that alternate's part number: the order list buys from it.
const planPref = {};
for (const [f, p] of Object.entries(plans)) {
  for (const t of p.tables) {
    const pi = t.header.indexOf('primary');
    if (pi < 0) continue;
    for (const row of t.rows) {
      const prim = words(row[pi]), both = words(`${row[0]} ${row[pi]}`);
      for (const [key, alts] of Object.entries(media.alternates)) {
        for (const a of alts || []) {
          const sup = words(a.supplier), pn = words(a.part_number);
          if (sup.trim() && pn.trim() && prim.includes(sup) && both.includes(pn) && !planPref[key]) {
            planPref[key] = { alt: a, doc: f, heading: t.heading, sec: secOf(t.heading), row: row[0] };
          }
        }
      }
    }
  }
}
if (Object.values(media.alternates).some((l) => (l || []).some((a) => a.preferred))) {          // a preferred flag in the file wins
  for (const [key, alts] of Object.entries(media.alternates)) {
    const a = (alts || []).find((x) => x.preferred);
    if (a) planPref[key] = { alt: a, doc: 'catalog/alternates.json', heading: 'preferred', sec: '', row: key };
  }
}

// docs/leg-prototype-plan.md 6.2: the print days; a part whose name the Prints cell holds takes that row's place.
const legPlan = plans['docs/leg-prototype-plan.md'] || {};
const printDays = ((legPlan.tables || []).find((t) => secOf(t.heading) === '6.2' && t.header.includes('prints')) || { header: [], rows: [] });
const dayRow = (name) => {
  const n = words(name.replace(/_/g, ' ')).trim();
  const pi = printDays.header.indexOf('prints');
  return printDays.rows.findIndex((r) => { const c = words(r[pi]); return c.includes(` ${n} `) || c.includes(` ${n}s `) || c.includes(` ${n}es `); });
};

// ------------------------------------------------------------------------------------------------ pictures
let noPic = new Set();
window.__thumbMissing = (img) => {
  const a = img.closest('.thumb');
  a.classList.add('missing');
  a.removeAttribute('href');
  a.title = `No picture for ${a.dataset.key} on this machine (bought parts' photos are not in git): run tools/part_images.py`;
  noPic.add(a.dataset.key);
  const el = $('nopic');
  if (el) el.innerHTML = noPicNote();
  img.remove();
};
const noPicNote = () => (noPic.size ? `<span class="tag fail">${noPic.size} WITHOUT A PICTURE</span> <span class="dim small">${esc([...noPic].join(', '))}`
  + ' (tools/part_images.py fetches and renders them)</span>' : '');
const thumb = (key, label, small = false) => {
  const im = key ? media.images[key] : null;
  const cls = `thumb${small ? ' sm' : ''}`;
  if (!im || !im.path) {
    noPic.add(key || label);
    return `<div class="${cls} missing" title="${esc(`No picture for ${key || label}: run tools/part_images.py`)}"></div>`;
  }
  const href = im.kind === 'render' ? `${R}${im.path}` : (im.source_url || `${R}${im.path}`);
  const tip = im.kind === 'render' ? `${key}: a render of our CAD` : `${key}: picture from ${im.seller || ''} ${im.source_url || ''} (${im.fetched || ''})`;
  return `<a class="${cls}" href="${esc(href)}" title="${esc(tip)}" data-key="${esc(key)}">`
    + `<img src="${R}${esc(im.path)}" alt="${esc(label || key)}" loading="lazy" onerror="__thumbMissing(this)"></a>`;
};

// ------------------------------------------------------------------------------------------------ the lines to buy
// Where a part is bought, at what price and in what packs: the plan's choice of an alternate, else the parts list's
// own sellers (newer lists carry them), else the catalogue (McMaster-Carr by its part number, others by their first
// buy link). Packs: pack_qty / pack_price_usd, or "$N per K-pack" in the catalogue's price note; a minimum order
// ("minimum order N") from the same note; pieces cut from a stocked length ("(cut N per length)" in the list's name).
const chooseSeller = (k, rows) => {
  const it = media.items[k] || {};
  const r0 = rows[0] || {};
  const pref = planPref[k];
  if (pref) {
    const a = pref.alt, pack = a.pack_qty || 1;
    return { via: 'plan', plan: pref, alt: a, seller: a.supplier, url: a.url || null, pn: a.part_number || null, each: a.price_usd_each ?? null,
      pack, packPrice: a.price_usd_each != null ? a.price_usd_each * pack : null, priceText: a.price, stock: a.stock || null, checked: a.checked };
  }
  const lr = rows.find((r) => Array.isArray(r.sellers) && r.sellers.length && (r.sellers[0].url || r.sellers[0].seller));
  if (lr) {
    const x = lr.sellers[0], pack = x.pack_qty || lr.pack_qty || 1;
    const packPrice = x.price_usd ?? (lr.price_usd_each != null ? lr.price_usd_each * pack : null);
    return { via: 'list', seller: x.seller, url: x.url || lr.url || null, pn: lr.part_number || it.model || null, sku: x.seller_pn || null,
      each: packPrice != null ? packPrice / pack : null, pack, packPrice, stock: x.stock || null, inStock: x.in_stock, shipsFrom: x.ships_from || null, checked: x.read_on };
  }
  if (media.items[k]) {
    const buy = (it.buy || [])[0] || {};
    const src = (rows.find((r) => r.source) || {}).source || {};
    const mc = it.vendor === 'McMaster-Carr';
    const each = it.price_usd ?? r0.price_usd_each ?? null;
    let pack = it.pack_qty || null, packPrice = it.pack_price_usd ?? null, packNote = null;
    if (!pack) {
      const m = /\$\s?([\d,]+(?:\.\d+)?)\s+per\s+(\d+)-pack/i.exec(it.price_note || '');
      if (m) { pack = +m[2]; packPrice = +m[1].replace(/,/g, ''); packNote = m[0]; }
    }
    pack = pack || 1;
    if (packPrice == null && each != null) packPrice = each * pack;
    const moq = /minimum(?: order)?\s+(\d+)/i.exec(it.price_note || '');
    const im = media.images[k] || {};
    return { via: 'catalogue', seller: mc ? 'McMaster-Carr' : (buy.seller || src.seller || it.vendor || r0.vendor || null),
      url: mc && it.model ? `https://www.mcmaster.com/${it.model}/` : (buy.url || r0.url || src.url || null), pn: it.model || r0.part_number || null,
      each, pack, packPrice, packNote, moq: moq ? +moq[1] : 0, moqNote: moq ? moq[0] : null, priceNote: it.price_note || null, checked: it.price_checked,
      stock: it.stock || null, inStock: buy.in_stock, shipsFrom: buy.ships_from || null, avail: im.availability || null, availDate: im.fetched || null, pending: !!it.pending };
  }
  const each = r0.price_usd_each ?? null;
  return { via: 'list', seller: r0.vendor || null, url: r0.url || null, pn: r0.part_number || null, each, pack: r0.pack_qty || 1,
    packPrice: each != null ? each * (r0.pack_qty || 1) : null };
};

// the seller a line is ordered from: grouped by the buy link's site (one cart per site), named from the data
const hostOf = (u) => {
  try {
    const h = new URL(u).hostname.replace(/^www\./, '');
    return /amazonaws\.com$|cloudfront\.net$|githubusercontent\.com$/.test(h) || /\.pdf(\?|$)/i.test(u) ? null : h;
  } catch { return null; }
};
const sellerName = (name, host) => {
  const parts = String(name || '').split(/\s+\/\s+/).map((p) => p.replace(/\s*\([^)]*\)\s*/g, ' ').trim()).filter(Boolean);
  if (parts.length > 1 && host) {
    const hit = parts.find((p) => host.replace(/[^a-z0-9]/g, '').includes(p.toLowerCase().split(/\s+/)[0].replace(/[^a-z0-9]/g, '')));
    return hit || host;
  }
  return parts[0] || host || null;
};
const isMotor = (l) => /^(leg_actuator|wheel_motor|motor_driver)$/.test(l.category) || /\bmotors?\b|servo|\besc\b|speed controller|botwheel/i.test(l.name);
const isBearing = (l) => l.category === 'bearing' || /bearing/i.test(l.name);

// every bought line of the included workstreams, merged by catalogue key (one order line per part)
const LIST_LABEL = (s, list) => s.lists[list] || (list === 'per_leg' ? 'leg' : list.replace(/_/g, ' '));
const collect = (included) => {
  const uses = {}, made = [];
  for (const s of STREAMS.filter((x) => x.present && included.has(x.id))) {
    const bom = s.bomData || {};
    const rows = [];
    for (const [list, arr] of Object.entries(bom)) {
      if (!Array.isArray(arr) || SKIP_LIST.test(list)) continue;
      for (const r of arr) if (r && typeof r === 'object' && +r.qty > 0 && (r.key || r.id || r.item || r.name)) rows.push({ s, list, r });
    }
    // bought parts the turret's CAD draws that its list leaves out (as on the progress page)
    if (s.id === 'turret' && turretJson && bom.bench_turret) {
      const listed = new Set(bom.bench_turret.map((r) => r.for));
      const skip = new Set(media.sourcing.skip || []);
      for (const n of Object.keys(turretJson.bought || {})) {
        if (!listed.has(n) && !skip.has(n) && !(bom.ordered_to_drawing || {})[n]) rows.push({ s, list: 'bench_turret', r: { item: n, for: `${n}: drawn in cad/turret.py, not on the bench list yet`, qty: 1 } });
      }
    }
    // made to order: the list's machined parts, its parts cut to our drawings, and any line a fab service makes
    for (const r of bom.made_to_order || []) made.push({ s, kind: 'cnc', key: r.key, qty: r.qty, r });
    for (const [n, d] of Object.entries(bom.ordered_to_drawing || {})) {
      const i = rows.findIndex((x) => x.r.for === n);
      const line = i >= 0 ? rows.splice(i, 1)[0].r : null;
      made.push({ s, kind: 'sheet', key: n, qty: line ? +line.qty : 1, r: d, line, sheet: ((turretJson && turretJson.sheet) || {})[n] || null });
    }
    for (let i = rows.length - 1; i >= 0; i--) {
      const k = keysOf(rows[i].r)[0];
      const it = media.items[k] || {};
      if (!FAB.test(`${it.vendor || ''} ${rows[i].r.vendor || ''}`)) continue;
      const x = rows.splice(i, 1)[0];
      made.push({ s, kind: 'fab', key: k || x.r.for || x.r.item, qty: +x.r.qty, r: null, line: x.r });
    }
    for (const { s: st, list, r } of rows) {
      const ks = keysOf(r);
      for (const k of (ks.length ? ks : [`?${r.item || r.name || r.key}`])) {
        (uses[k] = uses[k] || []).push({ stream: st.id, label: LIST_LABEL(st, list), qty: +r.qty, for: r.for, r });
      }
    }
  }
  const lines = Object.entries(uses).map(([k, us]) => {
    const rows = us.map((u) => u.r);
    const it = media.items[k] || {};
    const s = k.startsWith('?') ? { via: 'none', seller: null, url: null, pn: null, each: null, pack: 1, packPrice: null } : chooseSeller(k, rows);
    const cut = Math.max(1, ...rows.map((r) => +((/\(cut (\d+) per length\)/i.exec(r.name || r.item || '') || [])[1] || 1)));
    const need = sum(us.map((u) => u.qty));
    const units = Math.ceil(need / cut);
    const packs = Math.ceil(Math.max(units, s.moq || 0) / s.pack);
    const order = s.packPrice != null ? round2(packs * s.packPrice) : null;
    const used = s.each != null ? round2((need / cut) * s.each) : null;
    const name = it.name || (it.vendor && it.model ? `${it.vendor} ${it.model}` : null) || rows[0].name || rows[0].item || k.replace(/^\?/, '');
    const host = hostOf(s.url);
    return { key: k, it, s, uses: us, need, cut, units, packs, order, used, name, category: it.category || '', host,
      sellerName: sellerName(s.seller, host), risk: (media.sourcing.risk || {})[k] || null };
  });
  return { lines, made };
};

// filament: whole kilograms of each material the included print plans use, at the catalogue's price per kg
const filamentLines = (included) => {
  const g = {}, cost = {};                                   // grams, and the print plans' own cost of them
  for (const s of STREAMS.filter((x) => x.present && included.has(x.id))) {
    for (const p of s.plans) {
      for (const [m, t] of Object.entries(p.data.by_material || {})) { g[m] = (g[m] || 0) + (t.grams || 0); cost[m] = (cost[m] || 0) + (t.cost_usd || 0); }
    }
  }
  return Object.entries(g).map(([m, grams]) => {
    const mat = media.materials[m] || {};
    const url = (mat.source || []).find((u) => /store|shop/.test(u) && !/\.pdf/i.test(u)) || null;
    const each = mat.price_usd_per_kg ?? null;
    const packs = Math.ceil(grams / 1000);
    const host = hostOf(url);
    return { key: `filament:${m}`, filament: true, material: m, it: mat, name: mat.name || m, need: grams, packs, cut: 1,
      s: { via: 'catalogue', seller: 'Bambu Lab store', url, pn: m, each, pack: 1, packPrice: each, checked: mat.price_checked },
      order: each != null ? round2(packs * each) : null, used: cost[m] ? round2(cost[m]) : (each != null ? round2((grams / 1000) * each) : null),
      uses: [], category: 'filament', host, sellerName: (mat.name || '').split(/\s+/).slice(0, 2).join(' ') || 'filament', risk: null };
  });
};

const groupLines = (lines) => {
  const groups = {};
  for (const l of lines) {
    const gk = l.filament ? 'filament' : (l.host || (l.sellerName ? l.sellerName.toLowerCase() : 'no seller'));
    const g = groups[gk] = groups[gk] || { key: gk, lines: [], names: [] };
    g.lines.push(l);
    if (l.sellerName) g.names.push(l.sellerName);
  }
  for (const g of Object.values(groups)) {
    g.filament = g.key === 'filament';
    g.none = g.key === 'no seller';
    g.name = g.filament ? 'Filament (Bambu Lab store)' : g.none ? 'No seller yet' : g.key === 'mcmaster.com' ? 'McMaster-Carr' : g.names[0] || g.key;
    g.url = g.filament || g.none ? null : (g.lines.find((l) => l.host) ? `https://${g.key}/` : null);
    g.total = round2(sum(g.lines.map((l) => l.order || 0)));
    g.used = round2(sum(g.lines.map((l) => l.used || 0)));
    g.unpriced = g.lines.filter((l) => l.order == null).length;
    g.rank = g.key === 'mcmaster.com' ? 0 : g.filament ? 4 : g.none ? 5 : g.lines.some(isMotor) ? 1 : g.lines.every(isBearing) ? 2 : 3;
    g.lines.sort((a, b) => (g.rank === 0 ? a.key.localeCompare(b.key) : (b.order || 0) - (a.order || 0) || a.key.localeCompare(b.key)));
  }
  return Object.values(groups).sort((a, b) => a.rank - b.rank || b.total - a.total || a.name.localeCompare(b.name));
};

// ------------------------------------------------------------------------------------------------ lead times
// Only what the data says: a seller's stock line, the catalogue's price note, McMaster's delivery line, the
// made-to-order note; "N days/weeks" in them is the lead time. Shipping from China, out of stock or backordered, a
// hard-to-buy note (catalog/sourcing.json risk) and made to order put a line on the day-1 list.
const leadOf = (texts) => {
  let best = null;
  for (const x of texts) {
    if (!x.t) continue;
    const t = String(x.t).replace(/more in [^;,)]*/gi, '');
    const m = /(\d+)(?:\s*[-–]\s*(\d+))?\s*(?:business\s+|working\s+)?(day|week)s?\b(?:\s+lead(?:\s+time)?)?/i.exec(t);
    if (!m) continue;
    const days = +(m[2] || m[1]) * (m[3].toLowerCase() === 'week' ? 7 : 1);
    if (!best || days > best.days) best = { days, phrase: m[0], src: x.src, date: x.date };
  }
  return best;
};
const lineLead = (l) => {
  const s = l.s;
  return leadOf([{ t: s.stock, src: `${l.sellerName || 'seller'}: stock`, date: s.checked },
    { t: s.via === 'catalogue' ? s.priceNote : null, src: 'catalogue price note', date: s.checked },
    { t: s.avail, src: 'McMaster product page', date: s.availDate }]);
};
const RISK = { high: ['fail', 'HARD TO BUY'], medium: ['warn', 'CHECK STOCK'], cost: ['warn', 'CHEAPER OPTION'],
  fit: ['fail', "DOESN'T FIT AS DRAWN"], missing: ['fail', 'PARTS MISSING'], check: ['warn', 'TO CHECK'] };
const riskTag = (rk) => {
  if (!rk) return '';
  const [cls, label] = RISK[rk.level] || ['warn', String(rk.level || 'NOTE').toUpperCase()];
  return `<div class="risk"><span class="tag ${cls}">${label}</span> ${esc(rk.note)}${rk.checked ? ` <span class="chk">(${esc(rk.checked)})</span>` : ''}</div>`;
};
// out of stock or backordered at the chosen seller: its flag, or its stock line (one that starts "in stock" is in stock,
// whatever else it mentions)
const notInStock = (s) => s.inStock === false
  || (/backorder|out of stock|pre-?order|unavailable/i.test(s.stock || '') && !/^\s*in\s?stock/i.test(s.stock || ''));
// [tag class, label, severity, shown by the risk note already]
const day1Reasons = (l) => {
  const s = l.s, why = [];
  if (notInStock(s)) why.push(['fail', 'OUT OF STOCK / BACKORDERED', 3]);
  if (l.risk && l.risk.level === 'high') why.push(['fail', 'HARD TO BUY', 3, true]);
  if (l.risk && l.risk.level === 'medium') why.push(['warn', 'CHECK STOCK', 2, true]);
  if (s.shipsFrom === 'CN' || /ships from china/i.test(s.stock || '')) why.push(['warn', 'SHIPS FROM CHINA', 2]);
  return why;
};

// ------------------------------------------------------------------------------------------------ rendering
const included = new Set(STREAMS.filter((s) => s.present).map((s) => s.id));
const altList = (l) => {
  const s = l.s, it = l.it || {};
  const alts = [];
  if (s.via === 'plan' && media.items[l.key] && it.model) {             // the catalogue's own choice, when a plan overrides it
    const buy = (it.buy || [])[0] || {};
    const mc = it.vendor === 'McMaster-Carr';
    alts.push({ supplier: `${mc ? 'McMaster-Carr' : buy.seller || it.vendor} (the catalogue's)`, part_number: it.model,
      url: mc ? `https://www.mcmaster.com/${it.model}/` : buy.url, drop_in: true, checked: it.price_checked,
      price: it.pack_price_usd != null && (it.pack_qty || 1) > 1 ? `${usd(it.pack_price_usd)} / pack of ${it.pack_qty}` : (it.price_usd != null ? `${usd(it.price_usd)} each` : null) });
  }
  for (const a of media.alternates[l.key] || []) if (a !== s.alt) alts.push(a);
  for (const r of l.uses.map((u) => u.r)) {
    for (const x of (Array.isArray(r.sellers) ? r.sellers.slice(1) : [])) {
      alts.push({ supplier: x.seller, part_number: x.seller_pn, url: x.url, drop_in: true, checked: x.read_on, stock: x.stock,
        price: x.price_usd != null ? `${usd(x.price_usd)}${(x.pack_qty || 1) > 1 ? ` / ${x.pack_qty}` : ''}` : null });
    }
  }
  if (!alts.length) return '<span class="tag fail">NO ALTERNATE</span>';
  const n = alts.filter((a) => a.drop_in).length;
  return `<details class="alts"><summary>${plural(alts.length, 'alternate')} · ${n ? `${n} drop-in` : 'none drop-in'}</summary><ul>`
    + alts.map((a) => `<li>${a.drop_in ? '<span class="tag pass">DROP-IN</span>' : '<span class="tag warn">CHANGES</span>'} <b>${esc(a.supplier)}</b> `
      + `${a.url ? `<a href="${esc(a.url)}">${esc(a.part_number || 'product page')}</a>` : esc(a.part_number || '')}`
      + `${a.price ? ` · ${esc(a.price)}` : ''}${a.stock ? ` · <span style="color:var(--mint)">${esc(a.stock)}</span>` : ''}`
      + `${a.changes ? `<div class="chg">${esc(a.changes)}</div>` : ''}<div class="chk">checked ${esc(a.checked || '?')}</div></li>`).join('')
    + '</ul></details>';
};
const byMaterialStreams = (m) => {                          // grams of a material per included workstream
  const out = {};
  for (const s of STREAMS.filter((x) => x.present && included.has(x.id))) {
    for (const p of s.plans) { const t = (p.data.by_material || {})[m]; if (t) out[s.id] = (out[s.id] || 0) + (t.grams || 0); }
  }
  return out;
};
const forText = (l) => (l.filament
  ? `${esc(kg(l.need))} kg in the included print plans: ${esc(Object.entries(byMaterialStreams(l.material)).map(([sid, g]) => `${sid} ${kg(g)} kg`).join(' · '))}`
  : l.uses.map((u) => `<div><i>${esc(u.label)} ×${u.qty}</i> ${esc(u.for || '')}</div>`).join(''));
const qtyCell = (l) => {
  const s = l.s;
  const buy = [];
  if (l.filament) buy.push(`buy ${l.packs} kg`);
  else if (l.cut > 1) buy.push(`buy ${plural(l.units, 'length')}, cut ${l.cut} per length`);
  if (!l.filament && s.pack > 1) buy.push(`buy ${l.packs} ${s.packNote ? `× ${s.packNote.replace(/^.*per\s+/i, '')}` : `pack${l.packs > 1 ? 's' : ''} of ${s.pack}`}`);
  if (s.moq && s.moq > l.units) buy.push(`buy ${Math.max(s.moq, l.packs * s.pack)}: ${esc(s.moqNote)}`);
  return `<span class="lbl">qty</span>${l.filament ? `${kg(l.need)} kg` : l.need}${buy.length ? `<small>${buy.join('<br>')}</small>` : ''}`;
};
const unitCell = (l) => {
  const s = l.s;
  if (s.each == null) return '<span class="lbl">each</span><span class="tag fail">NO PRICE</span>';
  return `<span class="lbl">each</span>${unit$(s.each)}${l.filament ? ' / kg' : l.cut > 1 ? ' / length' : ''}`
    + `${s.pack > 1 ? `<small>${usd(s.packPrice)} per ${s.packNote ? esc(s.packNote.replace(/^.*per\s+/i, '')) : s.pack}</small>` : ''}`
    + `${l.cut > 1 ? `<small>${unit$(s.each / l.cut)} a piece</small>` : ''}`;
};
const lineCell = (l) => (l.order == null ? '<span class="lbl">line</span>—'
  : `<span class="lbl">line</span><b>${usd(l.order)}</b>${l.used != null && Math.abs(l.used - l.order) >= 0.005 ? `<small>used ${usd(l.used)}</small>` : ''}`);
const pnCell = (l) => {
  const s = l.s;
  if (!s.pn && !s.url) return '<span class="tag fail">NO PART NUMBER</span>';
  const av = s.avail ? `<span class="avail" title="the product page on ${esc(s.availDate)}">${esc(s.avail)} <span style="color:var(--dim)">(${esc(s.availDate)})</span></span>` : '';
  const bad = notInStock(s);
  const stock = s.stock ? `<span class="avail${bad ? ' bad' : ''}">${esc(s.stock)}${s.checked ? ` <span style="color:var(--dim)">(${esc(s.checked)})</span>` : ''}</span>`
    : (s.inStock === false ? '<span class="avail bad">out of stock (catalogue)</span>' : '');
  return `${s.url ? `<a href="${esc(s.url)}">${esc(s.pn || 'product page')}</a>` : esc(s.pn)}${s.pn ? '' : ' <span class="tag fail">NO PART NUMBER</span>'}`
    + `${s.sku ? `<small>seller's no. ${esc(s.sku)}</small>` : ''}<br><span style="color:var(--muted)">${esc(l.sellerName || s.seller || '')}</span>`
    + `${s.shipsFrom && s.shipsFrom !== 'US' ? ` <span style="color:var(--dim)">ships from ${esc(s.shipsFrom)}</span>` : ''}`
    + `${s.url ? '' : ' <span class="tag fail">NO BUY LINK</span>'}${av}${stock}`;
};
const mainCell = (l) => {
  const s = l.s, it = l.it || {};
  const plan = s.via === 'plan' ? `<div class="for">the plan's seller (<a href="${esc(secLink(s.plan.doc, s.plan.sec))}">${esc(s.plan.doc)} ${esc(s.plan.sec)}</a>,`
    + ` Primary) instead of the catalogue's ${esc(it.vendor || '')} ${esc(it.model || '')}</div>` : '';
  const flags = [s.pending ? '<span class="tag warn" title="chosen in catalog/sourcing.json, not in a catalogue file yet">PROPOSED</span>' : '',
    l.key.startsWith('?') ? '<span class="tag fail">NO CATALOGUE KEY</span>' : ''].filter(Boolean).join(' ');
  // a "cheaper option" note is moot once a plan buys the cheaper option
  const risk = s.via === 'plan' && l.risk && l.risk.level === 'cost' ? '' : riskTag(l.risk);
  return `<b>${esc(s.via === 'plan' ? `${s.pn} (${s.seller})` : l.name)}</b><span class="key">${esc(l.filament ? l.material : l.key)}</span>`
    + `<div class="for">${forText(l)}</div>${plan}${flags ? `<div class="flags">${flags}</div>` : ''}${risk}`;
};
const orderRow = (l) => `<div class="orow" data-key="${esc(l.key)}" data-order="${l.order ?? ''}">`
  + `<div class="t">${thumb(l.filament ? null : l.key, l.name)}</div><div class="m">${mainCell(l)}</div><div class="p">${pnCell(l)}</div>`
  + `<div class="stats"><div class="q">${qtyCell(l)}</div><div class="u">${unitCell(l)}</div><div class="l">${lineCell(l)}</div></div>`
  + `<div class="a">${l.filament ? '<span class="dim small">any brand of the same material</span>' : altList(l)}</div></div>`;
const ORDER_HEAD = '<div class="orow head"><div class="t">picture</div><div class="m">part (and what it is for)</div><div class="p">part number, seller</div>'
  + '<div class="q">qty</div><div class="u">each</div><div class="l">line</div><div class="a">alternates (click)</div></div>';

const render = () => {
  noPic = new Set();
  const { lines: bought, made } = collect(included);
  const fil = filamentLines(included);
  const lines = [...bought, ...fil];
  const groups = groupLines(lines);
  const total = round2(sum(groups.map((g) => g.total)));
  const usedTotal = round2(sum(groups.map((g) => g.used)));
  const unpricedBought = lines.filter((l) => l.order == null);
  const madeRows = made.map(madeInfo);
  const madeEst = round2(sum(madeRows.map((m) => m.total || 0)));
  const madeUnpriced = madeRows.filter((m) => m.total == null);
  const prints = printQueue();
  const hours = sum(prints.mats.map((m) => m.hours));
  const grams = sum(prints.mats.map((m) => m.grams));
  const sellers = groups.filter((g) => !g.none).length;

  // the one-line summary
  $('summary').innerHTML = `To order: <b id="sum-total" data-usd="${total}">${usd(total)}</b> from <b>${sellers}</b> sellers`
    + ` (<b>${lines.length}</b> lines, whole packs and spools)`
    + `${!madeRows.length ? '' : madeUnpriced.length === madeRows.length
      ? ` + <b id="sum-made" data-usd="0">${plural(madeRows.length, 'part')}</b> machined or cut to order (not priced yet)`
      : ` + <b id="sum-made" data-usd="${madeEst}">~${usd(madeEst)}</b> machined or cut to order (estimate)`}`
    + ` · <b id="sum-hours" data-h="${hours.toFixed(1)}">~${hours.toFixed(1)} h</b> of printing (${kg(grams)} kg)`
    + ` · <b id="sum-unpriced" data-n="${unpricedBought.length + madeUnpriced.length}">${unpricedBought.length + madeUnpriced.length}</b>`
    + ` ${unpricedBought.length + madeUnpriced.length === 1 ? 'line' : 'lines'} still without a price.`;

  // the workstreams
  $('streams').innerHTML = STREAMS.map((s) => {
    const bom = s.bomData;
    const planLink = `<a href="${esc(secLink(s.plan, s.sec))}">${esc(s.plan)} ${esc(s.sec)}</a>`;
    if (!s.present) {
      return `<div class="card stream off"><b>${esc(s.title)}</b><span class="tag warn">NOT GENERATED YET</span>`
        + `<p>${esc(s.about)} ${planLink} lists it. ${esc(s.pending || '')}</p></div>`;
    }
    const files = [s.bom, ...s.plans.map((p) => p.file)].filter((f, i) => i > 0 || bom)
      .map((f) => `<li><a href="${R}${esc(f)}">${esc(f)}</a></li>`).join('');
    const own = bom && bom.price_usd_per_leg != null ? `bom.json's own figure: ${usd(bom.price_usd_per_leg)} per leg at catalogue prices, pieces used`
      : bom && bom.price_usd_known ? `bom.json's own figure: ${Object.entries(bom.price_usd_known).map(([k, v]) => `${k} ${usd(v)}`).join(', ')} at catalogue prices, pieces used` : '';
    const ph = sum(s.plans.map((p) => p.data.total_hours || 0));
    const nParts = sum(s.plans.map((p) => Object.keys(p.data.parts || {}).length));
    return `<div class="card stream${included.has(s.id) ? '' : ' off'}"><b>${esc(s.title)}</b><span class="tag pass">FROM THE DATA</span>`
      + `<p>${esc(s.about)} Plan: ${planLink}.</p>`
      + `<p>${s.plans.length ? `${plural(nParts, 'printed part')}, ~${ph.toFixed(1)} h. ` : 'No print plan yet. '}${esc(own)}${own ? '.' : ''}</p>`
      + `<ul class="files">${files}</ul>`
      + `<label class="inc"><input type="checkbox" data-stream="${esc(s.id)}"${included.has(s.id) ? ' checked' : ''}> include in the lists and totals</label></div>`;
  }).join('');
  document.querySelectorAll('#streams input[data-stream]').forEach((cb) => cb.addEventListener('change', () => {
    if (cb.checked) included.add(cb.dataset.stream); else included.delete(cb.dataset.stream);
    render();
  }));

  // day 1: the long poles
  const cands = [];
  for (const l of bought) {
    const why = day1Reasons(l), lead = lineLead(l);
    if (why.length || (lead && lead.days >= 7)) cands.push({ l, why, lead, sev: Math.max(0, ...why.map((w) => w[2])) });
  }
  for (const m of madeRows) cands.push({ m, why: [['info', 'MADE TO ORDER', 1]], lead: m.lead, sev: 1 });
  cands.sort((a, b) => ((b.lead ? b.lead.days : -1) - (a.lead ? a.lead.days : -1)) || b.sev - a.sev
    || ((b.l ? b.l.order : b.m.total) || 0) - ((a.l ? a.l.order : a.m.total) || 0));
  $('daylede').innerHTML = `What to order first, so nothing waits on it: lines that ship from China, are out of stock or backordered, are hard to buy,`
    + ` or are made to order, and any line whose data records a lead time of a week or more. A lead time is shown only where the data`
    + ` records one (a seller's stock line, the catalogue's price note, the made-to-order note), with where it came from.`;
  $('day1').innerHTML = cands.length ? `<div class="glist"><div class="grow drow head"><div>#</div><div></div><div>part</div><div>seller</div><div>lead time (as recorded)</div></div>`
    + cands.map((c, i) => {
      const lead = c.lead ? `<span class="lead">${esc(c.lead.phrase)}</span> <span class="dim small">(${esc(c.lead.src)}${c.lead.date ? `, ${esc(c.lead.date)}` : ''})</span>`
        : '<span class="lead none">lead time not recorded</span>';
      const tags = c.why.filter((w) => !w[3]).map(([cls, t]) => `<span class="tag ${cls}">${t}</span>`).join(' ');
      if (c.m) {
        return `<div class="grow drow"><div class="num">${i + 1}</div><div>${thumb(c.m.picKey, c.m.name, true)}</div>`
          + `<div><b>${esc(c.m.name)}</b> <span class="dim">×${c.m.qty}</span><div class="flags" style="margin-top:4px">${tags}</div></div>`
          + `<div class="mono"><span class="lbl">from</span>${c.m.vendorHtml}</div><div><span class="lbl">lead</span>${lead}</div></div>`;
      }
      const l = c.l;
      return `<div class="grow drow"><div class="num">${i + 1}</div><div>${thumb(l.key, l.name, true)}</div>`
        + `<div><b>${esc(l.s.via === 'plan' ? `${l.s.pn} (${l.s.seller})` : l.name)}</b> <span class="dim">×${l.need}</span>`
        + `${tags ? `<div class="flags" style="margin-top:4px">${tags}</div>` : ''}${riskTag(l.risk)}</div>`
        + `<div class="mono"><span class="lbl">from</span>${l.s.url ? `<a href="${esc(l.s.url)}">${esc(l.sellerName || l.s.seller || '?')}</a>` : esc(l.sellerName || '?')}`
        + `${l.s.shipsFrom ? ` <span class="dim">(ships from ${esc(l.s.shipsFrom)})</span>` : ''}</div><div><span class="lbl">lead</span>${lead}</div></div>`;
    }).join('') + '</div>' : '<p class="lede">Nothing in the included lists ships from China, is backordered, or records a long lead time.</p>';

  // the order list
  const planned = lines.filter((l) => l.s.via === 'plan');
  $('orderlede').innerHTML = `Every bought line of the included workstreams, merged by part (one line per part, with what each workstream uses it for)`
    + ` and grouped by the site you order from: McMaster-Carr, then the motor and wheel makers' stores, the bearing sellers, the electronics`
    + ` distributors and the rest, then the filament. <b>qty</b> is what this build uses; <b>line</b> is what the order costs in whole packs`
    + ` (McMaster's pack sizes, the catalogue's pack notes, minimum orders, tube bought by the length), with the cost of the pieces used beneath it.`
    + `${planned.length ? ` ${plural(planned.length, 'line')} buy${planned.length === 1 ? 's' : ''} from the seller a plan's Primary column names (${esc(planned.map((l) => `${l.s.pn} at ${l.s.seller}`).join(', '))}), not the catalogue's.` : ''}`
    + ` <span id="nopic"></span>`;
  $('sellers').innerHTML = `<div class="tablewrap"><table class="cmp" id="sellertable"><thead><tr><th>seller</th><th class="n">lines</th><th class="n">to order</th><th class="n wide">pieces used</th><th>no price</th></tr></thead><tbody>`
    + groups.map((g) => `<tr data-seller="${esc(g.key)}" data-usd="${g.total}"><td><a href="#g-${esc(g.key.replace(/[^a-z0-9]+/gi, '-'))}">${esc(g.name)}</a></td>`
      + `<td class="n">${g.lines.length}</td><td class="n">${usd(g.total)}</td><td class="n wide">${usd(g.used)}</td>`
      + `<td>${g.unpriced ? `<span class="tag fail">${g.unpriced}</span>` : ''}</td></tr>`).join('')
    + `<tr class="tot"><td>total</td><td class="n">${lines.length}</td><td class="n" id="grand-usd" data-usd="${total}">${usd(total)}</td><td class="n wide">${usd(usedTotal)}</td>`
    + `<td>${unpricedBought.length ? `<span class="tag fail">${unpricedBought.length}</span>` : ''}</td></tr></tbody></table></div>`;
  $('orders').innerHTML = groups.map((g) => {
    const paste = g.lines.filter((l) => l.s.pn && l.order != null && !l.filament);
    return `<section class="seller" id="g-${esc(g.key.replace(/[^a-z0-9]+/gi, '-'))}"><header><h3>${g.url ? `<a href="${esc(g.url)}">${esc(g.name)}</a>` : esc(g.name)}</h3>`
      + `<span class="why">${plural(g.lines.length, 'line')}${g.unpriced ? ` · <span class="tag fail">${g.unpriced} WITHOUT A PRICE</span>` : ''}`
      + `${g.filament ? ' · whole kilograms of what the print plans weigh, no allowance for reprints' : ''}</span>`
      + `<span class="sub">${usd(g.total)}</span></header><div class="olist">${ORDER_HEAD}${g.lines.map(orderRow).join('')}</div>`
      + `${paste.length > 2 ? `<footer><details class="paste"><summary>part numbers and packs to paste into the order form</summary>`
        + `<textarea readonly rows="${Math.min(paste.length, 12)}">${esc(paste.map((l) => `${l.s.pn}\t${l.packs}`).join('\n'))}</textarea></details></footer>` : ''}</section>`;
  }).join('')
    + `<div class="grand"><span>Total to order</span><b>${usd(total)}</b><span class="dim">${plural(lines.length, 'line')} from ${sellers} sellers;`
    + ` the pieces used cost ${usd(usedTotal)}${unpricedBought.length ? `; ${plural(unpricedBought.length, 'line')} without a price are not in it` : ''}.</span></div>`;

  // made to order
  $('madelede').innerHTML = madeRows.length ? `Custom parts ordered online from our files at an instant price (docs/decisions.yaml D40, D46): upload the STEP or DXF,`
    + ` enter the callouts the order form asks for (threads, fits, tolerances), and attach the callouts page as the drawing. Prices here are`
    + ` estimates until the instant price is read on upload: <b>~${usd(madeEst)}</b>${madeUnpriced.length ? `, and ${plural(madeUnpriced.length, 'part')} with no estimate` : ''}.`
    : 'No machined or cut parts in the included workstreams.';
  $('made').innerHTML = madeRows.length ? `<div class="glist"><div class="grow mrow head"><div>picture</div><div>part</div><div>files</div><div>qty</div><div>order from</div><div>estimate</div></div>`
    + madeRows.map((m) => `<div class="grow mrow" data-made="${esc(m.key)}"><div>${thumb(m.picKey, m.name)}</div>`
      + `<div><b>${esc(m.name)}</b><div class="dim small">${esc(m.desc)}</div><div class="dim small"><i>${esc(m.stream)}</i></div>`
      + `${m.callouts.length ? `<details class="callouts"><summary>${plural(m.callouts.length, 'callout')} for the order form</summary><ol>${m.callouts.map((c) => `<li>${esc(c)}</li>`).join('')}</ol></details>` : ''}</div>`
      + `<div class="mono"><span class="lbl">files</span>${m.files.map((f) => `<a href="${esc(f.href)}">${esc(f.label)}</a>`).join('<br>')}</div>`
      + `<div class="mono"><span class="lbl">qty</span>${m.qty}</div><div class="mono"><span class="lbl">from</span>${m.vendorHtml}</div>`
      + `<div class="est"><span class="lbl">estimate</span>${m.estHtml}</div></div>`).join('') + '</div>' : '';

  // the print queue
  $('printlede').innerHTML = `Every printed part of the included print plans, in printing order: the leg${STREAMS.find((s) => s.id === 'rig').present ? ' and its rig' : ''}`
    + ` in the order of <a href="${esc(secLink('docs/leg-prototype-plan.md', '6.2'))}">docs/leg-prototype-plan.md 6.2</a> (the day it names),`
    + ` everything else longest first. About <b>${hours.toFixed(1)} h</b> on one P1S; the plans' hours are rough (grams / density / a`
    + ` strength-holding volumetric rate). Filament cost is for the grams used; the order list buys whole kilograms.`;
  $('materials').innerHTML = `<div class="tablewrap"><table class="cmp" id="mattable"><thead><tr><th>material</th><th class="n">pieces</th><th class="n">kg</th><th class="n">hours</th>`
    + `<th class="n"><span class="wide">filament </span>used</th><th class="n">to buy</th></tr></thead><tbody>`
    + prints.mats.map((m) => `<tr data-mat="${esc(m.key)}" data-hours="${m.hours.toFixed(1)}" data-grams="${m.grams}" data-cost="${m.cost.toFixed(2)}">`
      + `<td><b>${esc(m.key)}</b> <span class="dim wide">${esc(m.name)}</span></td><td class="n">${m.parts}</td><td class="n">${kg(m.grams)}</td><td class="n">${m.hours.toFixed(1)}</td>`
      + `<td class="n">${usd(m.cost)}</td><td class="n">${m.buyKg} kg<span class="wide"> · </span><br class="narrow">${usd(m.buyUsd)}</td></tr>`).join('')
    + `<tr class="tot"><td>total</td><td class="n">${sum(prints.mats.map((m) => m.parts))}</td><td class="n">${kg(grams)}</td><td class="n" id="mat-hours">${hours.toFixed(1)}</td>`
    + `<td class="n">${usd(round2(sum(prints.mats.map((m) => m.cost))))}</td><td class="n">${usd(round2(sum(prints.mats.map((m) => m.buyUsd || 0))))}</td></tr></tbody></table></div>`;
  $('queue').innerHTML = prints.queues.map((q) => `<h3>${esc(q.title)} <span class="dim">${esc(q.how)}; ${plural(q.parts.length, 'part')}, ~${q.hours.toFixed(1)} h</span></h3>`
    + `<div class="glist"><div class="grow prow head"><div>#</div><div></div><div>part</div><div>material</div><div>qty</div><div>g (all)</div><div>h (all)</div><div>on the bed</div><div>${q.days ? 'plan day' : ''}</div></div>`
    + q.parts.map((p, i) => `<div class="grow prow" data-part="${esc(p.name)}"><div class="num">${i + 1}</div><div>${thumb(p.name, p.name, true)}</div>`
      + `<div><b>${p.stl ? `<a href="${esc(p.stl)}">${esc(p.name)}</a>` : esc(p.name)}</b>`
      + `${p.nostl ? ' <span class="tag warn" title="cad/turret.py writes the turret\'s STLs into exports/turret/ (not kept in git): run it for this one">NO STL ON THIS MACHINE</span>' : ''}`
      + `<div class="how">${esc(p.how || '')}${p.infill ? ` <span style="color:var(--dim)">(${esc(p.infill)})</span>` : ''}</div></div>`
      + `<div class="stats"><div class="mono"><span class="lbl">material</span>${esc(p.material)}</div><div class="mono"><span class="lbl">qty</span>${p.qty}</div>`
      + `<div class="mono"><span class="lbl">g (all)</span>${p.grams}</div><div class="mono"><span class="lbl">h (all)</span>${p.hours}</div>`
      + `<div class="mono"><span class="lbl">on the bed</span>${(p.size_mm || []).join(' × ')} mm${p.placement ? `, ${esc(p.placement)}` : ''}${p.fits === false ? ' <span class="tag fail">TOO BIG</span>' : ''}</div>`
      + `${q.days ? `<div class="mono"><span class="lbl">plan day</span>${p.day ? esc(p.day) : '<span class="dim">—</span>'}</div>` : ''}</div></div>`).join('') + '</div>').join('')
    || '<p class="lede">No print plan in the included workstreams.</p>';
  const el = $('nopic');
  if (el) el.innerHTML = noPicNote();
};

// a made-to-order part: its files, the order form's callouts, the vendor and its backup, the estimate and the lead
const domainLink = (text) => {
  const m = /\b([a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|io|co|de|cn))\b/i.exec(text || '');
  const name = String(text || '').replace(/\s*\(.*$/, '');
  return m ? `<a href="https://${esc(m[1])}/">${esc(name)}</a>` : esc(name);
};
const madeInfo = (m) => {
  const st = m.s.title;
  if (m.kind === 'cnc') {
    const r = m.r;
    const est = r.price_usd_each ?? r.price_estimate_usd_each ?? null;
    // the DXF first when there is one (sheet parts: SendCutSend takes it), then the STEP, then a callouts page
    const files = [r.dxf || r.drawing, r.step].filter((f, i, a) => f && a.indexOf(f) === i).map((f) => ({ href: `${R}${f}`, label: f.split('/').pop() }));
    if (/\/cnc\//.test(r.step || '')) files.push({ href: `${R}${r.step.replace(/[^/]+$/, 'README.md')}`, label: 'callouts page (README.md)' });
    return { key: r.key, name: r.key, picKey: r.key, stream: st, qty: m.qty, callouts: r.spec || [], files,
      desc: `${r.material || ''}${r.mass_g_each ? `, ${r.mass_g_each} g` : ''}${r.size_mm ? `, ${r.size_mm.join(' × ')} mm` : ''}`,
      vendorHtml: `${domainLink(r.vendor)}${r.backup ? `<br><span class="dim">backup ${domainLink(r.backup)}</span>` : ''}`,
      total: est != null ? round2(est * m.qty) : null,
      estHtml: est != null ? `${r.price_usd_each != null ? `${usd(r.price_usd_each)} each` : `~${usd(est)} each <span class="tag warn">ESTIMATE</span>`}<br>~${usd(round2(est * m.qty))} line`
        + `<div class="note">${esc(r.price_note || '')}</div>` : '<span class="tag fail">NO PRICE</span>',
      lead: leadOf([{ t: r.price_note, src: 'made-to-order note' }]) };
  }
  // cut to our drawing (ordered_to_drawing), or a list line a fab service makes (kind 'fab')
  const k = m.line ? keysOf(m.line)[0] : m.key;
  const it = media.items[k] || {};
  const d = m.r || {}, sh = m.sheet || {}, row = m.line || {};
  const files = [];
  const drawing = d.drawing || sh.dxf || row.drawing || null;
  if (drawing) files.push({ href: `${R}${drawing}`, label: drawing.split('/').pop() });
  const step = sh.step || row.step;
  if (step && (!step.startsWith('exports/turret/') || step.includes('/bench/') || turretFiles.has(step.split('/').pop()))) {
    files.push({ href: `${R}${step}`, label: step.split('/').pop() });
  }
  const buy = (it.buy || [])[0] || {};
  const url = d.url || buy.url || row.url || null, vendor = d.vendor || it.vendor || buy.seller || row.vendor || '?';
  const est = it.price_usd ?? row.price_usd_each ?? null;
  return { key: m.key, name: m.key, picKey: media.images[m.key] ? m.key : k, stream: st, qty: m.qty, callouts: [], files,
    desc: `${it.name || row.item || ''}${d.name ? ` (${d.name}${d.thickness_mm ? `, ${d.thickness_mm} mm` : ''})` : ''}${drawing ? '; the DXF is the drawing' : ''}`,
    vendorHtml: `${url ? `<a href="${esc(url)}">${esc(vendor)}</a>` : esc(vendor)}`
      + `<br><span class="dim">backup ${(media.alternates[k] || []).length ? esc(media.alternates[k][0].supplier) : 'not recorded'}</span>`,
    total: est != null ? round2(est * m.qty) : null,
    estHtml: `${est != null ? `${usd(est)} each` : '<span class="tag fail">NO PRICE</span>'}${it.price_note ? `<div class="note">${esc(it.price_note)}</div>` : ''}`,
    lead: leadOf([{ t: it.price_note, src: 'catalogue price note', date: it.price_checked }]) };
};

// the print queue: the leg and rig in the order of the leg plan's 6.2 (its day), the rest longest first
const printQueue = () => {
  const queues = [], mats = {};
  const tjParts = new Set(Object.keys((turretJson && turretJson.parts) || {}));
  const legLike = STREAMS.filter((s) => s.present && included.has(s.id) && s.order62 && s.plans.length);
  const others = STREAMS.filter((s) => s.present && included.has(s.id) && !s.order62 && s.plans.length);
  const partsOf = (s) => s.plans.flatMap((p) => Object.entries(p.data.parts || {}).map(([name, r]) => {
    const dir = p.file.replace(/[^/]+$/, '');                // a print plan's STLs sit beside it, in git
    if (s.id === 'turret' && tjParts.has(name)) {             // the turret's own parts: exports/turret/, when built here
      return { ...r, name, stream: s.id, stl: turretFiles.has(`${name}.stl`) ? `${R}exports/turret/${name}.stl` : null, nostl: !turretFiles.has(`${name}.stl`) };
    }
    return { ...r, name, stream: s.id, stl: `${R}${dir}${name}.stl` };
  }));
  if (legLike.length) {
    const parts = legLike.flatMap(partsOf).map((p) => {
      const i = dayRow(p.name);
      return { ...p, row: i, day: i >= 0 ? printDays.rows[i][printDays.header.indexOf('day')] : null };
    });
    parts.sort((a, b) => ((a.row < 0) - (b.row < 0)) || (a.row - b.row) || (b.hours - a.hours));
    queues.push({ title: legLike.map((s) => s.title).join(' + '), how: printDays.rows.length ? 'in the order of the leg plan 6.2' : 'longest first (the plan\'s 6.2 table was not found)',
      parts, days: parts.some((p) => p.day) });
  }
  for (const s of others) {
    const parts = partsOf(s).sort((a, b) => b.hours - a.hours || a.name.localeCompare(b.name));
    queues.push({ title: s.title, how: 'longest first', parts });
  }
  for (const q of queues) q.hours = sum(q.parts.map((p) => p.hours || 0));
  for (const s of [...legLike, ...others]) {
    for (const p of s.plans) {
      for (const [m, t] of Object.entries(p.data.by_material || {})) {
        const x = mats[m] = mats[m] || { key: m, name: (media.materials[m] || {}).name || m, grams: 0, hours: 0, cost: 0, parts: 0 };
        x.grams += t.grams || 0; x.hours += t.hours || 0; x.cost += t.cost_usd || 0; x.parts += t.parts || 0;
      }
    }
  }
  for (const x of Object.values(mats)) {
    x.hours = Math.round(x.hours * 10) / 10;
    const per = (media.materials[x.key] || {}).price_usd_per_kg;
    x.buyKg = Math.ceil(x.grams / 1000);
    x.buyUsd = per != null ? round2(x.buyKg * per) : null;
  }
  return { queues, mats: Object.values(mats).sort((a, b) => b.hours - a.hours) };
};

render();
