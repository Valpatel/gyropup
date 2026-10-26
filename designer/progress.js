// Progress page: the status and log (docs/progress.json, written as the work goes), the leg pictures, the strength
// studies with their overload videos, the physics scenario videos, the print plan and the motor order.
import { mountAppNav } from './kit/appnav.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const getJson = async (u) => { try { const r = await fetch(u, { cache: 'no-store' }); return r.ok ? r.json() : null; } catch { return null; } };
const $ = (id) => document.getElementById(id);
const tag = (ok, warn) => `<span class="tag ${ok ? 'pass' : warn ? 'warn' : 'fail'}">${ok ? 'PASS' : warn ? 'CLOSE' : 'FAIL'}</span>`;

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

// the leg explained
const ex = [['leg-module.png', 'The leg module', 'Two motors side by side on the hip axis'],
  ['leg-motors.mp4', 'Both motors at work', 'Hip alone, knee alone, then both: crouch to stand'],
  ['leg-hip.png', 'Hip motor', 'The whole leg swings; the push-rod keeps the knee angle'],
  ['leg-knee.png', 'Knee motor', 'Crank -> push-rod -> the shin folds']];
$('explain').innerHTML = ex.map(([f, t, c]) => `<figure>${f.endsWith('.mp4')
  ? `<video src="../exports/explain/${f}" controls loop muted playsinline></video>` : `<a href="../exports/explain/${f}"><img src="../exports/explain/${f}" alt="${esc(t)}"></a>`}`
  + `<figcaption><b>${esc(t)}</b> ${esc(c)}</figcaption></figure>`).join('');

// strength
const fea = await getJson('../exports/fea/summary.json');
if (fea) {
  const T = fea.targets || { sf: 2, sf_fall: 1.2 };
  const v = fea.verdict?.all || {};
  const rows = fea.results.map((r) => {
    const fall = r.case.endsWith('fall');
    const need = fall ? T.sf_fall : T.sf;
    const ok = r.safety_factor >= need;
    return { r, ok, warn: !ok && r.safety_factor >= 0.8 * need, need };
  });
  $('fea').innerHTML = `<table class="cmp"><thead><tr><th>part</th><th>case</th><th>material</th><th>SF</th><th>need</th><th>deflection</th><th></th></tr></thead><tbody>`
    + rows.map(({ r, ok, warn, need }, i) => `<tr class="click" data-i="${i}"><td>${esc(r.part)}</td><td>${esc(r.case)}</td><td>${esc(r.material)}</td>`
      + `<td>${r.safety_factor}</td><td>${need}</td><td>${r.probe_displacement_mm ? Math.hypot(...r.probe_displacement_mm).toFixed(2) : '—'} mm</td><td>${tag(ok, warn)}</td></tr>`).join('')
    + `<tr><td colspan="3">leg deflection at the wheel</td><td colspan="2">${v.wheel_deflection_mm} mm</td><td>≤ ${T.wheel_deflection_mm} mm</td><td>${tag(v.wheel_deflection_mm <= T.wheel_deflection_mm)}</td></tr>`
    + (fea.output_joint ? `<tr><td colspan="3">motor output joint (${esc(fea.output_joint.screws)})</td><td>${fea.output_joint.sf}</td><td>${T.sf}</td><td>${esc(fea.output_joint.capacity_nm)} N·m held</td><td>${tag(fea.output_joint.sf >= T.sf)}</td></tr>` : '')
    + (fea.rod ? `<tr><td colspan="3">push-rod (${fea.rod.force_n} N)</td><td>${fea.rod.buckling_sf}</td><td>3</td><td>buckling</td><td>${tag(fea.rod.buckling_sf >= 3)}</td></tr>` : '')
    + '</tbody></table>';
  const show = (i) => {
    const r = rows[i].r;
    if (r.animation) { $('feavid').src = `../${r.animation}`; $('feavid').play().catch(() => {}); }
    else { $('feavid').removeAttribute('src'); $('feavid').poster = `../${r.png}`; }
    $('feanote').textContent = `${r.part} ${r.case}: ${r.load_from}. ${r.material_note || ''}`;
  };
  document.querySelectorAll('#fea tr.click').forEach((tr) => tr.addEventListener('click', () => show(+tr.dataset.i)));
  const worst = rows.reduce((a, b, i) => (b.r.safety_factor / b.need < rows[a].r.safety_factor / rows[a].need ? i : a), 0);
  show(worst);
}

// physics
const designs = (await getJson('../exports/designs.json'))?.designs || [];
const stem = 'default';
const sim = await getJson(`../exports/sim/${stem}/summary.json`);
if (sim) {
  $('simlede').innerHTML = `Today's design (<b>${esc(designs.find((d) => d.file.endsWith('default.json'))?.name || 'Gyropup')}</b>, ${sim.mass_kg} kg in the model):
    <b>${sim.passed}/${sim.total}</b> scenarios pass. Videos are rendered from the physics (simple shapes; the 3D page shows the CAD).`;
  $('sims').innerHTML = Object.entries(sim.scenarios).map(([n, r]) => {
    const worst = Object.entries(r.motors || {}).reduce((a, [k, m]) => (m.of_peak > a[1] ? [k, m.of_peak] : a), ['', 0]);
    return `<figure>${r.video ? `<video src="../exports/sim/${stem}/${esc(r.video)}" controls loop muted playsinline preload="metadata"></video>` : ''}`
      + `<figcaption>${tag(r.pass)} <b>${esc(n)}</b> lean ${r.max_theta_deg}°, hardest motor ${esc(worst[0])} at ${Math.round(worst[1] * 100)}% of its limit`
      + ` · <a href="sim.html?design=${encodeURIComponent('designs/default.json')}&run=${encodeURIComponent(n)}">3D</a></figcaption></figure>`;
  }).join('');
}

// print plan
const pp = await getJson('../exports/print-plan.json');
if (pp) {
  const bm = Object.entries(pp.by_material).map(([m, t]) => `${m}: ${(t.grams / 1000).toFixed(2)} kg, ~${Math.round(t.hours)} h, $${Math.round(t.cost_usd)}`).join(' · ');
  $('printlede').innerHTML = `${pp.too_big.length ? `<b class="tag fail">TOO BIG: ${esc(pp.too_big.join(', '))}</b> ` : 'Every part fits the 256 mm bed. '}`
    + `Total ~<b>${Math.round(pp.total_hours)} h</b> of printing (${esc(bm)}). Hours are rough.`;
  $('print').innerHTML = `<table class="cmp"><thead><tr><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>placement</th><th>g each</th><th>hours (all)</th><th>infill</th><th>how</th></tr></thead><tbody>`
    + Object.entries(pp.parts).sort((a, b) => b[1].hours - a[1].hours).map(([n, r]) => `<tr><td><a href="../exports/${esc(n)}.stl">${esc(n)}</a></td><td>${esc(r.material)}</td><td>${r.qty}</td>`
      + `<td>${r.size_mm.join(' × ')}</td><td>${esc(r.placement)}</td><td>${r.grams_each}</td><td>${r.hours}</td><td>${esc(r.infill)}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>';
}
