// Progress page: the status and log (docs/progress.json, written as the work goes), leg v2 (pictures, the test rig's
// physics, the strength studies with their overload videos and 3D viewer, what to print and what to buy with a picture
// of every part and its alternate sources), the turret on its bench stand (the same for its parts).
import { mountAppNav } from './kit/appnav.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const getJson = async (u) => { try { const r = await fetch(u, { cache: 'no-store' }); return r.ok ? r.json() : null; } catch { return null; } };
const $ = (id) => document.getElementById(id);
const tag = (ok, warn) => `<span class="tag ${ok ? 'pass' : warn ? 'warn' : 'fail'}">${ok ? 'PASS' : warn ? 'CLOSE' : 'FAIL'}</span>`;
const LEG = '../exports/leg/';

await mountAppNav({ root: '../', current: 'progress' });

const prog = await getJson('../docs/progress.json');
if (prog) {
  $('updated').insertAdjacentHTML('beforeend', ` Last update: <b>${esc(prog.updated)}</b>.`);
  $('status').innerHTML = (prog.status || []).map((s) => `<div class="card"><b>${esc(s.title)}</b><div class="k">${esc(s.value)}</div><span>${esc(s.note || '')}</span></div>`).join('');
  $('log').innerHTML = (prog.log || []).slice().reverse().map((e) => `<li><time>${esc(e.time)}</time><b>${esc(e.title)}</b><p>${esc(e.text)}`
    + `${(e.links || []).map((l) => ` <a href="${esc(l.href)}">${esc(l.title)}</a>`).join(' ·')}</p></li>`).join('');
  $('shop').innerHTML = prog.shopping ? `<table class="cmp"><thead><tr><th>item</th><th>qty</th><th>each</th><th>total</th><th>notes</th></tr></thead><tbody>`
    + prog.shopping.items.map((i) => `<tr><td>${i.href ? `<a href="${esc(i.href)}">${esc(i.item)}</a>` : esc(i.item)}</td><td>${esc(i.qty)}</td><td>${esc(i.each)}</td><td>${esc(i.total)}</td><td>${esc(i.notes)}</td></tr>`).join('')
    + `</tbody></table><p class="lede">${esc(prog.shopping.note || '')}</p>` : '';
}

// leg v2: the pictures from cad/build_leg.py
const leg = await getJson(`${LEG}leg.json`);
if (leg) {
  const m = leg.mass_g;
  $('leglede').innerHTML = `Two RS-04s 150 mm apart in one printed hip frame drive two upper links; two lower links meet at the wheel's axle.`
    + ` Leg <b>${leg.leg_range_mm[0]}-${leg.leg_range_mm[1]} mm</b> (hip line to axle), track <b>${leg.track_mm_two_legs_back_to_back} mm</b> for two legs back to back,`
    + ` <b>${(m.total / 1000).toFixed(2)} kg</b> per leg (${(m.printed / 1000).toFixed(2)} kg printed).`
    + ` Clashes over the whole range: <b>${leg.clashes ? leg.clashes.filter((c) => c[0] !== 'out of range').length : '—'}</b>.`
    + ` <a href="../exports/leg/leg_stand.step">leg_stand.step</a> (bought parts as envelopes).`;
  const cap = { 'leg-stand-iso': 'Standing, 300 mm', 'leg-stand-outside': 'From outside: the five-bar', 'leg-stand-inside': 'From inside: both motors in the frame',
    'leg-stand-front': 'From the front: the layers', 'leg-exploded': 'Exploded: frame, bearings, links, knee cartridges, wheel',
    'leg-crouch-outside': 'Deepest crouch, 130 mm', 'leg-crouch-iso': 'Crouched', 'leg-tall-outside': 'Tallest, 380 mm' };
  $('leg').innerHTML = (leg.pictures || []).map((f) => `<figure><a href="${LEG}${esc(f)}"><img src="${LEG}${esc(f)}" alt="${esc(f)}"></a>`
    + `<figcaption><b>${esc(cap[f.replace('.png', '')] || f)}</b></figcaption></figure>`).join('');
}

// the test rig (sim/leg_rig.py)
const rig = await getJson(`${LEG}rig-results.json`);
if (rig) {
  const S = rig.scenarios;
  $('riglede').innerHTML = `One leg on a vertical rail carrying half the robot (<b>${rig.half_mass_kg} kg</b>), RS-04s capped at <b>${rig.model.leg_cap_nm} N·m</b>`
    + ` (peak ${rig.model.leg_peak_nm}), the stops as stiff as their TPU sleeves. The leg is driven like a RoboMaster balance robot's: a virtual spring on the hip-to-axle line.`;
  // the joints' real forces and the gearbox torque come from every step of the simulation; statics on the axle's peak
  // force (in grey) overstates a landing's knee load about twice: the links' and the body's inertia take the spike
  const jf = (r) => (r.peak_joint_force_n ? Math.round(Math.max(r.peak_joint_force_n.knee_f, r.peak_joint_force_n.knee_r)) : null);
  $('rigtable').innerHTML = `<table class="cmp"><thead><tr><th>scenario</th><th>motor peak</th><th>gearbox</th><th>wheel force</th><th>knee pin</th><th>stop</th><th>leg range</th><th>jump</th></tr></thead><tbody>`
    + Object.values(S).map((r) => `<tr><td><b>${esc(r.scenario)}</b><br><span style="color:var(--muted)">${esc(r.title)}</span></td><td>${r.peak_motor_nm} N·m</td>`
      + `<td>${r.peak_gearbox_nm != null ? `${r.peak_gearbox_nm} N·m ${tag(r.peak_gearbox_nm <= rig.model.leg_peak_nm)}` : '—'}</td><td>${r.peak_wheel_force_n} N</td>`
      + `<td>${jf(r) != null ? `${jf(r)} N <span style="color:var(--muted)">(statics ${Math.round(r.peak_knee_pin_n)})</span>` : `${r.peak_knee_pin_n} N`}</td>`
      + `<td>${r.peak_stop_nm} N·m</td><td>${r.L_range_mm.join('-')} mm</td><td>${r.jump_height_mm != null ? r.jump_height_mm + ' mm' : '—'}</td></tr>`).join('')
    + '</tbody></table>';
  $('rig').innerHTML = Object.values(S).map((r) => `<figure><video src="${LEG}rig_${esc(r.scenario)}.mp4" controls loop muted playsinline preload="metadata"></video>`
    + `<figcaption><b>${esc(r.scenario)}</b> ${esc(r.title)}</figcaption></figure>`).join('');
}

// the joints the whole-leg study bonds, checked on their own (cad/leg_studies.py joint_checks): each check's worst rare
// case against its own target (rolling bearings by their static safety s0 = C0/P0, printed parts and pins by SF)
const JOINT_NAMES = { knee_rear: 'rear knee', knee_front: 'front knee', apex_61812: 'apex 61812s', hub_rear: 'rear hub joint', hub_front: 'front hub joint' };
const jointValue = (j, c) => ({ '6201 s0': () => `${j['6201'].load_n} N`, pin: () => `${j.pin.stress_mpa} MPa`, 'eye pressure': () => `${j.eye_pressure.mpa} MPa`,
  s0: () => `${j.load_n} N`, tipping: () => `${j.out_of_plane_nm} N·m (tips at ${j.tips_at_nm})`, 'dowel bearing': () => `${j.dowel_bearing_mpa} MPa` }[c.check] || (() => ''))();
const jointRows = (J) => {
  const worst = {};
  for (const c of J.checks) { const k = `${c.joint}|${c.check}`; if (!worst[k] || c.sf / c.target < worst[k].sf / worst[k].target) worst[k] = c; }
  return Object.values(worst).map((c) => `<tr><td colspan="3">${esc(JOINT_NAMES[c.joint] || c.joint)}: ${esc(c.check)} (${esc(c.case)})</td><td>${c.sf}</td><td>${c.target}</td>`
    + `<td>${esc(jointValue(J[c.case][c.joint], c))}</td><td>${tag(c.sf >= c.target, c.sf < c.target && c.sf >= 0.8 * c.target)}</td><td></td></tr>`).join('');
};

// strength (cad/leg_studies.py)
const fea = await getJson(`${LEG}fea/summary.json`);
if (fea) {
  const rows = fea.results.map((r) => ({ r, ok: r.safety_factor >= r.target, warn: r.safety_factor < r.target && r.safety_factor >= 0.8 * r.target }));
  const viewerHref = (r) => (r.viewer ? `kit/fea.html?case=${encodeURIComponent(`../../${r.viewer}`)}&title=${encodeURIComponent(`${r.part} ${r.case}`)}&current=progress` : null);
  const b = fea.front_link_buckling;
  $('fea').innerHTML = `<table class="cmp"><thead><tr><th>part</th><th>case</th><th>material</th><th>SF</th><th>need</th><th>deflection</th><th></th><th>3D</th></tr></thead><tbody>`
    + rows.map(({ r, ok, warn }, i) => `<tr class="click" data-i="${i}"><td>${esc(r.part)}</td><td>${esc(r.case)}</td><td>${esc(r.material)}</td>`
      + `<td>${r.safety_factor}</td><td>${r.target}</td><td>${r.probe_displacement_mm ? Math.hypot(...r.probe_displacement_mm).toFixed(2) : '—'} mm</td><td>${tag(ok, warn)}</td>`
      + `<td>${viewerHref(r) ? `<a class="open3d" href="${esc(viewerHref(r))}" title="Interactive: load slider, hot spots, section cut">open ↗</a>` : '—'}</td></tr>`).join('')
    + (b ? `<tr><td colspan="3">front lower link, buckling (${esc(b.note)})</td><td>${b.sf}</td><td>3</td><td>${b.P_cr_n} N</td><td>${tag(b.sf >= 3)}</td><td></td></tr>` : '')
    + (fea.joints && fea.joints.checks ? jointRows(fea.joints) : '')
    + '</tbody></table>';
  const show = (i) => {
    const r = rows[i].r;
    if (r.animation) { $('feavid').src = `../${r.animation}`; $('feavid').play().catch(() => {}); }
    else { $('feavid').removeAttribute('src'); $('feavid').poster = `../${r.png}`; }
    const href = viewerHref(r);
    $('feanote').innerHTML = `${href ? `<a class="hud-btn primary" href="${esc(href)}">Open ${esc(r.part)} ${esc(r.case)} in 3D ↗</a> ` : ''}`
      + `${esc(r.part)} ${esc(r.case)}: ${esc(r.load_from)}.`;
    document.querySelectorAll('#fea tr.click').forEach((tr) => tr.classList.toggle('on', +tr.dataset.i === i));
  };
  document.querySelectorAll('#fea tr.click').forEach((tr) => tr.addEventListener('click', (e) => { if (!e.target.closest('a')) show(+tr.dataset.i); }));
  if (rows.length) show(rows.reduce((a, x, i) => (x.r.safety_factor / x.r.target < rows[a].r.safety_factor / rows[a].r.target ? i : a), 0));
}

// parts lists: a picture of every line (catalog/images.json, tools/part_images.py: product photos, renders of our printed
// parts), its part number and its alternate sources (catalog/alternates.json). A line that names its part in words gets
// its catalogue key from catalog/sourcing.json, which also holds the parts no catalogue file has yet.
const media = await (async () => {
  const [images, alternates, sourcing, index] = await Promise.all(['images', 'alternates', 'sourcing', 'index'].map((f) => getJson(`../catalog/${f}.json`)));
  const items = {};
  for (const list of await Promise.all([...new Set(['hardware.json', ...((index && index.files) || [])])].map((f) => getJson(`../catalog/${f}`)))) {
    for (const it of list || []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = it;
  }
  for (const it of (sourcing && sourcing.parts) || []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = { ...it, pending: true };
  return { images: images || {}, alternates: alternates || {}, sourcing: sourcing || {}, items };
})();
const keysOf = (r) => {
  if (r.media_key) return [r.media_key, ...(r.also || []).map((a) => a.media_key)];
  for (const c of [r.key, r.id]) if (c && media.items[c]) return [c];
  const names = media.sourcing.names || {};
  for (const c of [r.item, r.name, r.for, r.key]) if (c && names[c] !== undefined) return [].concat(names[c]);
  return [];
};
const money = (v) => (v != null ? `$${Number(v).toFixed(2)}` : '—');
const noPic = new Map();                                  // section -> keys without a picture (none, or it failed to load)
const showMissing = (sec) => {
  const el = $(`${sec}-nopic`);
  const ks = [...(noPic.get(sec) || [])];
  if (el) el.innerHTML = ks.length ? `<span class="tag fail">${ks.length} WITHOUT A PICTURE</span> ${esc(ks.join(', '))}`
    + ' <span style="color:var(--dim)">(tools/part_images.py fetches and renders them)</span>' : '';
};
const markMissing = (sec, key, now = false) => {
  if (!noPic.has(sec)) noPic.set(sec, new Set());
  noPic.get(sec).add(key);
  if (now) showMissing(sec);
};
window.__thumbMissing = (img) => {
  const a = img.closest('.thumb');
  a.classList.add('missing');
  a.removeAttribute('href');
  a.title = `No picture for ${a.dataset.key} on this machine (bought parts' photos are not in git): run tools/part_images.py`;
  markMissing(a.dataset.sec, a.dataset.key, true);
  img.remove();
};
const thumb = (sec, key, label, small = false) => {
  const im = key ? media.images[key] : null;
  const cls = `thumb${small ? ' sm' : ''}`;
  if (!im || !im.path) {
    markMissing(sec, key || label);
    return `<div class="${cls} missing" title="${esc(`No picture for ${key || label}: run tools/part_images.py`)}"></div>`;
  }
  const href = im.kind === 'render' ? `../${im.path}` : (im.source_url || `../${im.path}`);
  const tip = im.kind === 'render' ? `${key}: a render of our CAD (${im.source_url})` : `${key}: picture from ${im.seller || ''} ${im.source_url} (${im.fetched})`;
  return `<a class="${cls}" href="${esc(href)}" title="${esc(tip)}" data-sec="${esc(sec)}" data-key="${esc(key)}">`
    + `<img src="../${esc(im.path)}" alt="${esc(label || key)}" loading="lazy" onerror="__thumbMissing(this)"></a>`;
};
const partRef = (key, row = {}) => {
  const it = media.items[key] || {};
  const mc = it.vendor === 'McMaster-Carr';
  const pn = it.model || (row.key === key ? row.part_number : null) || null;
  const buy = (it.buy || [])[0] || {};
  const url = mc ? `https://www.mcmaster.com/${it.model}/` : (buy.url || null);
  const seller = mc ? 'McMaster-Carr' : (buy.seller || it.vendor || row.vendor || '');
  const av = (media.images[key] || {}).availability;
  if (!pn && !url) return '<span class="tag warn">TO SOURCE</span>';
  return `${url ? `<a href="${esc(url)}">${esc(pn || 'product page')}</a>` : esc(pn)}<br><span style="color:var(--muted)">${esc(seller)}</span>`
    + `${it.pending ? ' <span class="tag warn" title="chosen in catalog/sourcing.json, not in a catalogue file yet">PROPOSED</span>' : ''}`
    + `${av ? `<span class="avail" title="what the product page said on ${esc(media.images[key].fetched)}">${esc(av)} <span style="color:var(--dim)">(${esc(media.images[key].fetched)})</span></span>` : ''}`;
};
const altList = (key) => {
  const alts = media.alternates[key] || [];
  if (!alts.length) return '<span class="tag fail">NO ALTERNATE</span>';
  const n = alts.filter((a) => a.drop_in).length;
  return `<details class="alts"><summary>${alts.length} alternate${alts.length > 1 ? 's' : ''} · ${n ? `${n} drop-in` : 'none drop-in'}</summary><ul>`
    + alts.map((a) => `<li>${a.drop_in ? '<span class="tag pass">DROP-IN</span>' : '<span class="tag warn">CHANGES</span>'} <b>${esc(a.supplier)}</b> `
      + `${a.url ? `<a href="${esc(a.url)}">${esc(a.part_number || 'product page')}</a>` : esc(a.part_number || '')}`
      + `${a.price ? ` · ${esc(a.price)}` : ''}${a.stock ? ` · <span style="color:var(--mint)">${esc(a.stock)}</span>` : ''}`
      + `${a.changes ? `<div class="chg">${esc(a.changes)}</div>` : ''}<div class="chk">checked ${esc(a.checked || '?')}</div></li>`).join('')
    + '</ul></details>';
};
const RISK = { high: ['fail', 'HARD TO BUY'], medium: ['warn', 'CHECK STOCK'], cost: ['warn', 'CHEAPER OPTION'] };
const riskTag = (key) => {
  const rk = (media.sourcing.risk || {})[key];
  if (!rk) return '';
  const [cls, label] = RISK[rk.level] || ['warn', String(rk.level || 'NOTE').toUpperCase()];
  return `<div class="risk"><span class="tag ${cls}">${label}</span> ${esc(rk.note)}${rk.checked ? ` <span class="chk">(${esc(rk.checked)})</span>` : ''}</div>`;
};
const partRow = (sec, r) => {
  const keys = keysOf(r);
  const k = keys[0];
  const it = media.items[k] || {};
  const name = r.name || it.name || (it.vendor && it.model ? `${it.vendor} ${it.model}` : null) || r.item || r.key || '?';
  const each = r.price_usd_each != null ? r.price_usd_each : it.price_usd;
  const also = keys.slice(1).map((x) => `<div class="also"><b style="font:600 12px var(--font-ui)">+ ${esc((media.items[x] || {}).name || x)}</b><br>${partRef(x)}</div>`).join('');
  return `<div class="prow"><div class="t thumbs">${keys.length ? keys.map((x, i) => thumb(sec, x, x, i > 0)).join('') : thumb(sec, null, r.item || r.key)}</div>`
    + `<div class="m"><b>${esc(name)}</b><span class="key">${esc(keys.join(' + ') || 'no catalogue key')}</span><div class="for">${esc(r.for || '')}</div>`
      + `${keys.map(riskTag).join('')}</div>`
    + `<div class="p">${k ? partRef(k, r) : '<span class="tag warn">TO SOURCE</span>'}${also}</div>`
    + `<div class="q">${esc(r.qty)}</div>`
    + `<div class="c">${each != null ? money(each) : (it.pending && it.price_note ? `<small title="${esc(it.price_note)}">${esc(it.price_note.replace(/^[^:]*:\s*/, '').slice(0, 40))}</small>` : '—')}`
      + `${each != null && r.qty > 1 ? `<small>${money(each * r.qty)}</small>` : ''}</div>`
    + `<div class="a">${keys.length ? keys.map((x) => (keys.length > 1 ? `<div class="key">${esc(x)}</div>` : '') + altList(x)).join('') : '<span class="tag fail">NO KEY</span>'}</div></div>`;
};
const partList = (sec, rows) => `<div class="mediasum" id="${sec}-nopic"></div><div class="plist"><div class="prow head"><div class="t">picture</div><div class="m">part</div>`
  + '<div class="p">part number</div><div class="q">qty</div><div class="c">each / line</div><div class="a">alternates (click)</div></div>'
  + rows.map((r) => partRow(sec, r)).join('') + '</div>';
const coverage = (rows) => {
  const keys = [...new Set(rows.flatMap(keysOf))];
  const pics = keys.filter((k) => (media.images[k] || {}).path).length;
  const alts = keys.filter((k) => (media.alternates[k] || []).length).length;
  const noKey = rows.filter((r) => !keysOf(r).length).length;
  const hard = keys.filter((k) => ((media.sourcing.risk || {})[k] || {}).level === 'high');
  return `${keys.length} different parts: <b>${pics}</b> with a picture, <b>${alts}</b> with an alternate source`
    + `${noKey ? `, <span class="tag fail">${noKey} WITHOUT A CATALOGUE KEY</span>` : ''}.`
    + `${hard.length ? ` <span class="tag fail">${hard.length} HARD TO BUY</span> ${esc(hard.join(', '))}.` : ''}`;
};

// what to print and what to buy (cad/build_leg.py)
const pp = await getJson(`${LEG}print-plan.json`);
if (pp) {
  const bm = Object.entries(pp.by_material).map(([m, t]) => `${m}: ${(t.grams / 1000).toFixed(2)} kg, ~${Math.round(t.hours)} h, $${Math.round(t.cost_usd)}`).join(' · ');
  $('printlede').innerHTML = `${pp.too_big.length ? `<b class="tag fail">TOO BIG: ${esc(pp.too_big.join(', '))}</b> ` : 'Every part fits the 256 mm bed. '}`
    + `One leg: ~<b>${Math.round(pp.total_hours)} h</b> of printing (${esc(bm)}). Hours are rough.`;
  $('print').innerHTML = `<div class="mediasum" id="print-nopic"></div><table class="cmp"><thead><tr><th></th><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>placement</th><th>g each</th><th>hours (all)</th><th>infill</th><th>how</th></tr></thead><tbody>`
    + Object.entries(pp.parts).sort((a, b) => b[1].hours - a[1].hours).map(([n, r]) => `<tr><td class="th">${thumb('print', n, n, true)}</td><td><a href="${LEG}${esc(n)}.stl">${esc(n)}</a></td><td>${esc(r.material)}</td><td>${r.qty}</td>`
      + `<td>${r.size_mm.join(' × ')}</td><td>${esc(r.placement)}</td><td>${r.grams_each}</td><td>${r.hours}</td><td>${esc(r.infill)}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>';
  showMissing('print');
}
const bom = await getJson(`${LEG}bom.json`);
if (bom) {
  $('buylede').innerHTML = `About <b>$${Math.round(bom.price_usd_per_leg)}</b> per leg for what has a price. ${coverage(bom.per_leg)}`
    + (bom.to_source.length ? ` <span class="tag warn">TO SOURCE</span> ${esc(bom.to_source.join(', '))}` : ' Every part has a part number.')
    + ' Click a picture for the page it came from; open <b>alternates</b> for other places to buy each part and what would change.';
  $('buy').innerHTML = partList('buy', bom.per_leg);
  showMissing('buy');
}

// the turret on its bench stand (cad/build_turret.py)
const TB = '../exports/turret/bench/';
const tb = await getJson(`${TB}bench.json`);
const tbom = await getJson(`${TB}bom.json`);
const tpp = await getJson(`${TB}print-plan.json`);
if (tb) {
  $('turretlede').innerHTML = `The turret (cad/turret.py: a 30-ball hopper over an 8-pocket dial, twin flywheels, a 100 mm barrel that never points above level)`
    + ` on a printed stand (${tb.stand_mm.join(' × ')} mm) with a 24 V inlet, fuse and switch, a USB-CAN adapter for a laptop and a hold-to-run pendant:`
    + ` the turret will not spin up or feed a ball unless the pendant's button is held. <b>${(tb.printed_g / 1000).toFixed(2)} kg</b> printed, ~<b>${Math.round(tb.print_hours)} h</b>`
    + `${tb.too_big?.length ? ` <span class="tag fail">TOO BIG: ${esc(tb.too_big.join(', '))}</span>` : ', every part fits the bed'}.`;
  const caps = { 'turret-bench-level-iso': 'On the bench, level', 'turret-bench-level-front': 'From the front', 'turret-bench-aimed-iso': 'Panned 35°, tilted 20° down' };
  $('turret').innerHTML = (tb.pictures || []).map((f) => `<figure><a href="${TB}${esc(f)}"><img src="${TB}${esc(f)}" alt="${esc(f)}"></a>`
    + `<figcaption><b>${esc(caps[f.replace('.png', '')] || f)}</b></figcaption></figure>`).join('')
    + ['turret.png', 'turret-section.png'].map((f) => `<figure><a href="../exports/turret/${f}"><img src="../exports/turret/${f}" alt="${f}"></a>`
    + `<figcaption><b>${f === 'turret.png' ? 'Every part, labelled' : 'The ball path: hopper, dial, chute, flywheels, barrel'}</b></figcaption></figure>`).join('');
}
if (tbom) {
  const rows = tbom.bench_turret;
  // bought parts the turret's CAD draws (exports/turret/turret.json) that its list leaves out
  const tj = await getJson('../exports/turret/turret.json');
  const listed = new Set(rows.map((r) => r.for));
  const skip = new Set(media.sourcing.skip || []);
  const drawn = Object.keys((tj && tj.bought) || {}).filter((n) => !listed.has(n) && !skip.has(n));
  const all = [...rows, ...drawn.map((n) => ({ item: n, for: `${n}: drawn in cad/turret.py, not on the bench list yet`, qty: 1 }))];
  $('turretbuylede').innerHTML = `About <b>$${Math.round(tbom.price_usd_known)}</b> for what has a price. ${coverage(all)}`
    + (drawn.length ? ` <span class="tag warn">DRAWN, NOT ON THE LIST</span> ${esc(drawn.join(', '))}` : '')
    + ` ${esc(tbom.note || '')}`;
  $('turretbuy').innerHTML = partList('turretbuy', all);
  showMissing('turretbuy');
}
if (tpp) {
  $('turretprintlede').innerHTML = `${Object.keys(tpp.parts).length} printed parts for the turret and its stand, ~<b>${Math.round(tpp.total_hours)} h</b> of printing. Hours are rough.`;
  $('turretprint').innerHTML = `<div class="mediasum" id="turretprint-nopic"></div><table class="cmp"><thead><tr><th></th><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>g each</th><th>hours (all)</th><th>how</th></tr></thead><tbody>`
    + Object.entries(tpp.parts).map(([n, r]) => `<tr><td class="th">${thumb('turretprint', n, n, true)}</td><td>${esc(n)}</td><td>${esc(r.material)}</td><td>${r.qty}</td>`
      + `<td>${(r.size_mm || []).join(' × ')}</td><td>${r.grams_each}</td><td>${r.hours}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>';
  showMissing('turretprint');
}
