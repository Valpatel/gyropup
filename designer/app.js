// The designer UI: loads the catalog, walks through the chapters, and keeps the robot sheet live.

import { evaluate, indexCatalog } from './model.js';
import { visibleChapters, COLORS } from './chapters.js';
import { robotSvg } from './robot-svg.js';
import { mountAppNav } from './kit/appnav.js';

const STORE = 'gyropup-design-v1';
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const usd = (v) => (v == null ? '—' : '$' + Math.round(v).toLocaleString('en-US'));
const kg = (g) => (g == null ? '—' : (g / 1000).toFixed(2) + ' kg');
const clone = (o) => JSON.parse(JSON.stringify(o));

let catalog, items, materials, defaults, state;

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function load() {
  await mountAppNav({ root: '../', current: 'design' });
  const index = await getJson('../catalog/index.json');
  const lists = await Promise.all(index.files.map((f) => getJson(`../catalog/${f}`)));
  items = lists.flat();
  catalog = indexCatalog(lists);
  materials = await getJson('../catalog/materials.json');
  defaults = await getJson('../designs/default.json');
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(STORE) || 'null'); } catch { /* private window */ }
  state = { design: saved?.schema === defaults.schema ? saved : clone(defaults), chapter: 0, crouch: 0.35 };
  const hash = location.hash.slice(1);
  render();
  if (hash) go(hash);
}

function save() {
  try { localStorage.setItem(STORE, JSON.stringify(state.design)); } catch { /* storage blocked */ }
}

function result(design = state.design) {
  return evaluate(design, catalog, materials);
}

function go(id) {
  const chs = visibleChapters(state.design, catalog, result());
  const i = chs.findIndex((c) => c.id === id);
  if (i >= 0) { state.chapter = i; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
}

// ----------------------------------------------------------------------------- option cards

function specChips(item) {
  const s = item.specs ?? {};
  const c = [];
  const add = (v, f) => { if (v != null) c.push(f(v)); };
  switch (item.category) {
    case 'leg_actuator':
      add(s.peak_torque_nm, (v) => `${v} N·m peak`); add(s.rated_torque_nm, (v) => `${v} N·m rated`);
      add(s.no_load_speed_rpm, (v) => `${v} rpm`); add(s.gear_ratio, (v) => `${v}:1`); add(s.interface, (v) => v); break;
    case 'wheel_motor':
      add(s.peak_torque_nm, (v) => `${v} N·m peak`); add(s.diameter_mm ?? s.tyre_diameter_mm, (v) => `⌀${v} mm`);
      add(s.encoder, (v) => v); add(s.integrated_driver, (v) => (v ? 'driver built in' : 'needs a driver')); break;
    case 'battery':
      add(s.voltage_nominal_v, (v) => `${v} V`); add(s.energy_wh, (v) => `${v} Wh`); add(s.max_continuous_a, (v) => `${v} A`); break;
    default:
      add(s.power_typical_w, (v) => `${v} W`); add(s.interface, (v) => v); add(s.voltage_range_v, (v) => `${v[0]}–${v[1]} V`);
  }
  add(s.mass_g, (v) => `${v} g`);
  return c.slice(0, 6).map((t) => `<span class="chip">${esc(t)}</span>`).join('');
}

function deltaChips(base, cand) {
  const out = [];
  const d = (v, fmt, invert = false, eps = 0.5) => {
    if (v == null || Number.isNaN(v)) return;
    const cls = Math.abs(v) < eps ? 'zero' : (v > 0) !== invert ? 'up' : 'down';
    out.push(`<span class="delta ${cls}">${fmt(v)}</span>`);
  };
  d(cand.cost.total_usd - base.cost.total_usd, (v) => `${v >= 0 ? '+' : '−'}${usd(Math.abs(v))}`);
  d((cand.mass.total_kg - base.mass.total_kg) * 1000, (v) => `${v >= 0 ? '+' : '−'}${Math.abs(v / 1000).toFixed(2)} kg`, false, 5);
  if (cand.legs.peak_margin != null && base.legs.peak_margin != null) {
    d(cand.legs.peak_margin - base.legs.peak_margin, (v) => `leg margin ${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}×`, true, 0.05);
  }
  if (cand.wheels.catch_lean_deg != null && base.wheels.catch_lean_deg != null) {
    d(cand.wheels.catch_lean_deg - base.wheels.catch_lean_deg, (v) => `catch ${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(0)}°`, true, 0.5);
  }
  const fails = cand.checks.filter((c) => c.level === 'fail').length;
  if (fails) out.push(`<span class="chip bad">${fails} problem${fails > 1 ? 's' : ''}</span>`);
  return out.join('');
}

function slotOptions(ch) {
  const base = result();
  const list = items.filter(ch.filter).sort((a, b) => (b.preferred === true) - (a.preferred === true) || (a.price_usd ?? 1e9) - (b.price_usd ?? 1e9));
  const cards = list.map((item) => {
    const cand = clone(state.design); cand.parts[ch.slot] = item.id;
    const r = result(cand);
    const selected = state.design.parts[ch.slot] === item.id;
    const buy = item.buy?.[0];
    return `<button class="card" data-slot="${ch.slot}" data-id="${esc(item.id)}" aria-pressed="${selected}">
      <div>${item.preferred ? '<span class="badge">preferred</span> ' : ''}<span class="vendor">${esc(item.vendor)}</span></div>
      <h3>${esc(item.model)}</h3>
      <div class="price">${usd(item.price_usd)}</div>
      <div class="chips">${specChips(item)}</div>
      ${item.notes ? `<p class="blurb">${esc(item.notes).slice(0, 220)}</p>` : ''}
      <div class="deltas">${selected ? '<span class="chip good">in your build</span>' : deltaChips(base, r)}</div>
      <div class="links">${buy ? `<a href="${esc(buy.url)}" target="_blank" rel="noopener">${esc(buy.seller)}</a>${buy.in_stock === false ? ' · out of stock' : ''}` : ''}
        ${item.price_checked ? ` · checked ${esc(item.price_checked)}` : ''}</div>
    </button>`;
  });
  if (ch.optional !== false && ch.optional) {
    const cand = clone(state.design); cand.parts[ch.slot] = null;
    cards.push(`<button class="card" data-slot="${ch.slot}" data-id="" aria-pressed="${!state.design.parts[ch.slot]}">
      <h3>None</h3><p class="blurb">Leave it off this build.</p><div class="deltas">${deltaChips(base, result(cand))}</div></button>`);
  }
  return `<div class="cards">${cards.join('') || '<p>No parts in the catalog for this yet.</p>'}</div>`;
}

function designOptions(ch) {
  const base = result();
  return `<div class="cards">${ch.options().map((o) => {
    const cand = clone(state.design); o.apply(cand);
    const sel = o.selected(state.design);
    return `<button class="card" data-opt="${esc(o.id)}" aria-pressed="${sel}">
      <h3>${esc(o.name)}</h3><p class="blurb">${esc(o.blurb)}</p>
      ${o.chips ? `<div class="chips">${o.chips.map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</div>` : ''}
      <div class="deltas">${sel ? '<span class="chip good">in your build</span>' : deltaChips(base, result(cand))}</div></button>`;
  }).join('')}</div>`;
}

// ----------------------------------------------------------------------------- special chapters

function materialsPage(r) {
  const filaments = Object.entries(materials).filter(([, m]) => m.kind === 'filament');
  const rows = r.parts.map((p) => {
    const opts = filaments.map(([id, m]) => `<option value="${id}" ${id === p.material ? 'selected' : ''}>${esc(m.name)}</option>`).join('');
    const stress = p.stress_mpa != null ? `${p.stress_mpa.toFixed(1)} / ${p.allowable_mpa.toFixed(1)} MPa` : '';
    const lvl = r.checks.find((c) => c.id === `strength-${p.id}` || c.id === `heat-${p.id}`)?.level ?? 'ok';
    return `<tr><td>${esc(p.name)}</td><td class="r">${p.qty}</td><td class="r">${Math.round(p.mass_g)} g <span class="est">est.</span></td>
      <td><select data-part="${p.id}">${opts}</select></td><td class="r">${usd(p.filament_usd * p.qty)}</td>
      <td><span class="chip ${lvl === 'ok' ? 'good' : lvl === 'warn' ? 'meh' : 'bad'}">${lvl}</span> ${stress}</td></tr>`;
  }).join('');
  return `<div class="tablewrap"><table><thead><tr><th>Part</th><th class="r">Qty</th><th class="r">Each</th><th>Material</th><th class="r">Filament</th><th>Check</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function characterPage() {
  const d = state.design;
  return `<h3>Colour</h3><div class="swatches">${COLORS.map((c) => `<button class="swatch" title="${esc(c.name)}" data-color="${c.hex}" style="background:${c.hex}" aria-pressed="${d.character.color === c.hex}"></button>`).join('')}</div>
    <h3>Name</h3><input type="text" id="robot-name" value="${esc(d.name)}" maxlength="40" aria-label="Robot name">`;
}

function bomTable(r, group, title) {
  const lines = r.lines.filter((l) => l.group === group);
  const rows = lines.map((l) => `<tr><td>${esc(l.name)}${l.estimate ? ' <span class="est">est.</span>' : ''}</td><td class="r">${l.qty}</td>
    <td class="r">${usd(l.unit_usd)}</td><td class="r">${usd((l.unit_usd ?? 0) * l.qty)}</td><td class="r">${kg((l.mass_g ?? 0) * l.qty)}</td>
    <td>${l.source ? `<a href="${esc(l.source)}" target="_blank" rel="noopener">source</a>` : ''}</td></tr>`).join('');
  const sub = lines.reduce((s, l) => s + (l.unit_usd ?? 0) * l.qty, 0);
  return `<h3>${title}</h3><div class="tablewrap"><table><thead><tr><th>Item</th><th class="r">Qty</th><th class="r">Each</th><th class="r">Total</th><th class="r">Mass</th><th></th></tr></thead>
    <tbody>${rows}<tr><td><b>Subtotal</b></td><td></td><td></td><td class="r"><b>${usd(sub)}</b></td><td></td><td></td></tr></tbody></table></div>`;
}

function summaryPage(r) {
  const perf = [
    ['Standing hip height', `${Math.round(r.legs.stand_hip_mm)} mm`], ['Crouched hip height', `${Math.round(r.legs.crouch_hip_mm)} mm`],
    ['Leg torque, deep crouch (each)', `${r.legs.static_torque_nm.toFixed(1)} N·m`], ['Leg torque, dynamic (each)', `${r.legs.dynamic_torque_nm.toFixed(1)} N·m est.`],
    ['Jump height', r.legs.jump_height_mm != null ? `${Math.round(r.legs.jump_height_mm)} mm est.` : '—'],
    ['Top speed', r.wheels.top_speed_kmh != null ? `${r.wheels.top_speed_kmh.toFixed(1)} km/h` : '—'],
    ['Lean it can catch', r.wheels.catch_lean_deg != null ? `${r.wheels.catch_lean_deg.toFixed(0)}°` : '—'],
    ['Steepest slope (rated torque)', r.wheels.max_slope_deg != null ? `${r.wheels.max_slope_deg.toFixed(0)}°` : '—'],
    ['Average power', r.power.average_w != null ? `${Math.round(r.power.average_w)} W est.` : '—'],
    ['Runtime', r.power.runtime_min != null ? `${Math.round(r.power.runtime_min)} min est.` : '—'],
  ];
  return bomTable(r, 'sensors_compute', 'Sensors &amp; compute') + bomTable(r, 'chassis_actuators', 'Chassis &amp; actuators')
    + `<h3>What it can do</h3><div class="tablewrap"><table><tbody>${perf.map(([k, v]) => `<tr><td>${k}</td><td class="r">${v}</td></tr>`).join('')}</tbody></table></div>
    <div class="nextbar"><button class="btn" id="dl-design">Download design.json</button><button class="btn" id="dl-bom">Download BOM (CSV)</button><button class="btn" id="reset">Start over</button></div>
    <p class="blurb">Build the CAD and the simulation model from this design: <code>tools/build.sh design.json</code>.</p>`;
}

// ----------------------------------------------------------------------------- render

function render() {
  const r = result();
  const chs = visibleChapters(state.design, catalog, r);
  state.chapter = Math.min(state.chapter, chs.length - 1);
  const ch = chs[state.chapter];
  $('#chapters').innerHTML = chs.map((c, i) => `<button data-go="${c.id}" ${i === state.chapter ? 'aria-current="step"' : ''} class="${i < state.chapter ? 'done' : ''}">${i + 1}. ${esc(c.title)}</button>`).join('');
  let body = '';
  if (ch.slot) body = slotOptions(ch);
  else if (ch.options) body = designOptions(ch);
  else if (ch.kind === 'materials') body = materialsPage(r);
  else if (ch.kind === 'character') body = characterPage();
  else if (ch.kind === 'summary') body = summaryPage(r);
  const prev = chs[state.chapter - 1], next = chs[state.chapter + 1];
  $('#page').innerHTML = `<div class="kicker">Chapter ${state.chapter + 1}</div><h2>${esc(ch.title)}</h2>
    <p class="story">${esc(ch.story(state.design, r))}</p>${body}
    <div class="nextbar">${prev ? `<button class="btn" data-go="${prev.id}">← ${esc(prev.title)}</button>` : '<span></span>'}
    ${next ? `<button class="btn primary" data-go="${next.id}">${esc(next.title)} →</button>` : ''}</div>`;
  renderSheet(r);
  history.replaceState(null, '', `#${ch.id}`);
}

function renderSheet(r) {
  const d = state.design;
  const stat = (num, lbl, est) => `<div class="stat"><span class="num">${num}</span><span class="lbl">${lbl}${est ? ' <span class="est">est.</span>' : ''}</span></div>`;
  const order = { fail: 0, warn: 1, ok: 2 };
  const checks = [...r.checks].sort((a, b) => order[a.level] - order[b.level]).slice(0, 7);
  $('#sheet').innerHTML = `<h2 class="name">${esc(d.name)}</h2>
    <div class="view">${robotSvg(d, catalog, { crouch: state.crouch, color: d.character.color })}</div>
    <label class="slider">stand <input type="range" min="0" max="1" step="0.01" value="${state.crouch}" id="crouch" aria-label="Crouch"> crouch</label>
    <div class="money"><div><span>Sensors &amp; compute</span><span>${usd(r.cost.sensors_compute_usd)}</span></div>
      <div><span>Chassis &amp; actuators</span><span>${usd(r.cost.chassis_actuators_usd)}</span></div>
      <div class="total"><span>Total</span><span>${usd(r.cost.total_usd)}</span></div></div>
    <div class="stats">${stat(r.mass.total_kg.toFixed(1) + ' kg', 'mass')}${stat(Math.round(r.legs.stand_hip_mm) + ' mm', 'hip height')}
      ${stat(r.legs.peak_margin != null ? r.legs.peak_margin.toFixed(1) + '×' : '—', 'leg torque margin', true)}
      ${stat(r.wheels.catch_lean_deg != null ? r.wheels.catch_lean_deg.toFixed(0) + '°' : '—', 'lean it can catch')}
      ${stat(r.power.runtime_min != null ? Math.round(r.power.runtime_min) + ' min' : '—', 'runtime', true)}
      ${stat(r.legs.jump_height_mm != null ? Math.round(r.legs.jump_height_mm) + ' mm' : '—', 'jump', true)}</div>
    <ul class="checks">${checks.map((c) => `<li class="${c.level}">${esc(c.text)}</li>`).join('')}</ul>`;
}

function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function bomCsv(r) {
  const q = (s) => `"${String(s ?? '').replace(/"/g, '""')}"`;
  const rows = [['group', 'item', 'qty', 'unit_usd', 'total_usd', 'mass_g_each', 'price_checked', 'source', 'estimate']];
  for (const l of r.lines) rows.push([l.group, l.name, l.qty, l.unit_usd?.toFixed(2), ((l.unit_usd ?? 0) * l.qty).toFixed(2), l.mass_g?.toFixed(0), l.price_checked, l.source, l.estimate ? 'yes' : '']);
  return rows.map((r) => r.map(q).join(',')).join('\n') + '\n';
}

document.addEventListener('click', (e) => {
  const t = e.target.closest('button');
  if (!t) return;
  const d = state.design;
  if (t.dataset.go) return go(t.dataset.go);
  if (t.dataset.slot) { d.parts[t.dataset.slot] = t.dataset.id || null; }
  else if (t.dataset.opt) {
    const ch = visibleChapters(d, catalog, result())[state.chapter];
    ch.options().find((o) => o.id === t.dataset.opt)?.apply(d);
  } else if (t.dataset.color) { d.character.color = t.dataset.color; }
  else if (t.id === 'dl-design') return download(`${d.name.replace(/\W+/g, '-').toLowerCase() || 'gyropup'}.design.json`, JSON.stringify(d, null, 2) + '\n', 'application/json');
  else if (t.id === 'dl-bom') return download('gyropup-bom.csv', bomCsv(result()), 'text/csv');
  else if (t.id === 'reset') { state.design = clone(defaults); }
  else return;
  save(); render();
});

document.addEventListener('input', (e) => {
  if (e.target.id === 'crouch') { state.crouch = Number(e.target.value); renderSheet(result()); }
  else if (e.target.id === 'robot-name') { state.design.name = e.target.value; save(); renderSheet(result()); }
});

document.addEventListener('change', (e) => {
  if (e.target.dataset.part) {
    state.design.materials.parts[e.target.dataset.part] = e.target.value;
    save(); render();
  }
});

load().catch((err) => {
  $('#page').innerHTML = `<h2>Could not load the catalog</h2><p>${esc(err.message)}</p><p>Serve the repository root (for example <code>cad-agent serve</code>) and open <code>/designer/</code>.</p>`;
});
