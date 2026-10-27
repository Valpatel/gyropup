// Progress page: the status and log (docs/progress.json, written as the work goes), leg v2 (pictures, the test rig's
// physics, the strength studies with their overload videos and 3D viewer, what to print and what to buy).
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
  $('rigtable').innerHTML = `<table class="cmp"><thead><tr><th>scenario</th><th>motor peak</th><th>wheel force</th><th>front link</th><th>knee pin</th><th>stop</th><th>leg range</th><th>jump</th></tr></thead><tbody>`
    + Object.values(S).map((r) => `<tr><td><b>${esc(r.scenario)}</b><br><span style="color:var(--muted)">${esc(r.title)}</span></td><td>${r.peak_motor_nm} N·m</td><td>${r.peak_wheel_force_n} N</td>`
      + `<td>${r.peak_front_link_n} N</td><td>${r.peak_knee_pin_n} N</td><td>${r.peak_stop_nm} N·m</td><td>${r.L_range_mm.join('-')} mm</td><td>${r.jump_height_mm != null ? r.jump_height_mm + ' mm' : '—'}</td></tr>`).join('')
    + '</tbody></table>';
  $('rig').innerHTML = Object.values(S).map((r) => `<figure><video src="${LEG}rig_${esc(r.scenario)}.mp4" controls loop muted playsinline preload="metadata"></video>`
    + `<figcaption><b>${esc(r.scenario)}</b> ${esc(r.title)}</figcaption></figure>`).join('');
}

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
    + (fea.joints ? [['knee 6201 (static rating)', fea.joints.knee_6201, `${fea.joints.knee_6201.load_n} N`],
                     ['knee pin, 12.9 steel', fea.joints.knee_pin, `${fea.joints.knee_pin.stress_mpa} MPa`],
                     ['upper link eye on the pin', fea.joints.upper_eye_pressure, `${fea.joints.upper_eye_pressure.mpa} MPa`],
                     ['apex 61812 (static rating)', fea.joints.apex_61812, `${fea.joints.apex_61812.load_n} N`]]
      .map(([n, j, v]) => `<tr><td colspan="3">${esc(n)} (R1)</td><td>${j.sf}</td><td>1.2</td><td>${esc(v)}</td><td>${tag(j.sf >= 1.2)}</td><td></td></tr>`).join('') : '')
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

// what to print and what to buy (cad/build_leg.py)
const pp = await getJson(`${LEG}print-plan.json`);
if (pp) {
  const bm = Object.entries(pp.by_material).map(([m, t]) => `${m}: ${(t.grams / 1000).toFixed(2)} kg, ~${Math.round(t.hours)} h, $${Math.round(t.cost_usd)}`).join(' · ');
  $('printlede').innerHTML = `${pp.too_big.length ? `<b class="tag fail">TOO BIG: ${esc(pp.too_big.join(', '))}</b> ` : 'Every part fits the 256 mm bed. '}`
    + `One leg: ~<b>${Math.round(pp.total_hours)} h</b> of printing (${esc(bm)}). Hours are rough.`;
  $('print').innerHTML = `<table class="cmp"><thead><tr><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>placement</th><th>g each</th><th>hours (all)</th><th>infill</th><th>how</th></tr></thead><tbody>`
    + Object.entries(pp.parts).sort((a, b) => b[1].hours - a[1].hours).map(([n, r]) => `<tr><td><a href="${LEG}${esc(n)}.stl">${esc(n)}</a></td><td>${esc(r.material)}</td><td>${r.qty}</td>`
      + `<td>${r.size_mm.join(' × ')}</td><td>${esc(r.placement)}</td><td>${r.grams_each}</td><td>${r.hours}</td><td>${esc(r.infill)}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>';
}
const bom = await getJson(`${LEG}bom.json`);
if (bom) {
  $('buylede').innerHTML = `About <b>$${Math.round(bom.price_usd_per_leg)}</b> per leg for what has a price.`
    + (bom.to_source.length ? ` <span class="tag warn">TO SOURCE</span> ${esc(bom.to_source.join(', '))}` : ' Every part has a part number.');
  $('buy').innerHTML = `<table class="cmp"><thead><tr><th>part</th><th>part number</th><th>qty</th><th>each</th><th>mass</th><th>for</th></tr></thead><tbody>`
    + bom.per_leg.map((r) => `<tr><td>${esc(r.name || r.key)}</td><td>${r.part_number ? (r.vendor === 'McMaster-Carr' ? `<a href="https://www.mcmaster.com/${esc(r.part_number)}/">${esc(r.part_number)}</a>` : esc(r.part_number)) : '<span class="tag warn">TO SOURCE</span>'}</td>`
      + `<td>${r.qty}</td><td>${r.price_usd_each != null ? '$' + Number(r.price_usd_each).toFixed(2) : '—'}</td><td>${r.mass_g_each != null ? Math.round(r.mass_g_each) + ' g' : '—'}</td><td>${esc(r.for)}</td></tr>`).join('')
    + '</tbody></table>';
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
  $('turretbuy').innerHTML = `<table class="cmp"><thead><tr><th>what to buy</th><th>qty</th><th>each</th><th>for</th></tr></thead><tbody>`
    + tbom.bench_turret.map((r) => `<tr><td>${esc(r.item)}</td><td>${r.qty}</td><td>${r.price_usd_each != null ? '$' + Number(r.price_usd_each).toFixed(2) : '—'}</td><td>${esc(r.for)}</td></tr>`).join('')
    + `</tbody></table><p class="lede">${esc(tbom.note || '')}${tpp ? ` Print plan: ${Object.keys(tpp.parts).length} printed parts, ~${Math.round(tpp.total_hours)} h.` : ''}</p>`;
}
