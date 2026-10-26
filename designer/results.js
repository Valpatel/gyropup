// Results page: every design × every scenario, with videos, motor usage and a link to replay the run in 3D.
import { mountAppNav } from './kit/appnav.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const getJson = async (u) => { const r = await fetch(u, { cache: 'no-store' }); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); };
const pct = (v) => `${Math.round(v * 100)}%`;

await mountAppNav({ root: '../', current: 'results' });
const designs = (await getJson('../exports/designs.json')).designs;
const sims = [];
for (const d of designs) {
  const stem = d.file.split('/').pop().replace(/\.json$/, '');
  try { sims.push({ d, stem, s: await getJson(`../exports/sim/${stem}/summary.json`) }); } catch { sims.push({ d, stem, s: null }); }
}

const scenarios = [...new Set(sims.flatMap((x) => (x.s ? Object.keys(x.s.scenarios) : [])))];
const tag = (ok) => `<span class="tag ${ok ? 'pass' : 'fail'}">${ok ? 'PASS' : 'FAIL'}</span>`;
document.getElementById('compare').innerHTML = `<table class="cmp"><thead><tr><th>Scenario</th>${sims.map((x) => `<th>${esc(x.d.name)}</th>`).join('')}</tr></thead><tbody>`
  + scenarios.map((n) => `<tr><td>${esc(n)}</td>${sims.map((x) => {
    const r = x.s?.scenarios?.[n];
    return `<td>${r ? `${tag(r.pass)} lean ${r.max_theta_deg}°` : '—'}</td>`;
  }).join('')}</tr>`).join('')
  + `<tr><td>mass</td>${sims.map((x) => `<td>${x.s ? `${x.s.mass_kg} kg` : '—'}</td>`).join('')}</tr>`
  + `<tr><td>passed</td>${sims.map((x) => `<td>${x.s ? `${x.s.passed}/${x.s.total}` : 'not simulated'}</td>`).join('')}</tr></tbody></table>`;

const host = document.getElementById('designs');
for (const x of sims) {
  const el = document.createElement('section');
  el.className = 'design';
  el.id = x.stem;
  if (!x.s) {
    el.innerHTML = `<h2>${esc(x.d.name)}</h2><p class="meta">Not simulated yet: <code>tools/simulate.py ${esc(x.d.file)} --video</code></p>`;
    host.appendChild(el);
    continue;
  }
  const sc = x.s.scenarios;
  el.innerHTML = `<h2>${esc(x.d.name)}</h2><div class="meta">${x.s.mass_kg} kg in the model · ${x.s.passed}/${x.s.total} scenarios pass · `
    + `<code>${esc(x.d.file)}</code> · <a href="sim.html?design=${encodeURIComponent(x.d.file)}">open in the simulator</a></div>`
    + `<div class="tiles">${Object.entries(sc).map(([n, r]) => {
      const worst = Object.entries(r.motors).sort((a, b) => b[1].of_peak - a[1].of_peak)[0];
      return `<button class="tile" data-run="${n}">${tag(r.pass)}<b>${esc(r.title)}</b>`
        + `<small>max lean ${r.max_theta_deg}° · ${worst[0]} ${pct(worst[1].of_peak)} of peak</small>`
        + (r.top_speed_mps != null ? `<small>top speed ${r.top_speed_mps} m/s (limit ${r.speed_limit_mps})</small>` : '') + '</button>';
    }).join('')}</div><div class="detail-host"></div>`;
  host.appendChild(el);
  el.querySelectorAll('.tile').forEach((b) => b.addEventListener('click', () => show(el, x, b.dataset.run)));
  show(el, x, Object.keys(sc).find((n) => !sc[n].pass) ?? Object.keys(sc)[0]);
}

function show(el, x, run) {
  el.querySelectorAll('.tile').forEach((b) => b.classList.toggle('on', b.dataset.run === run));
  const r = x.s.scenarios[run];
  const rows = Object.entries(r.motors).map(([n, m]) => [n, `${m.peak_torque_nm} N·m`, `${pct(m.of_peak)} of peak · ${pct(m.of_rated)} of rated`,
    m.of_peak >= 0.99 ? 'fail' : m.of_rated > 1 ? 'warn' : 'ok']);
  el.querySelector('.detail-host').innerHTML = `<div class="detail"><div>`
    + (r.video ? `<video src="../exports/sim/${x.stem}/${r.video}" controls autoplay muted loop playsinline></video>` : '<p class="hud-note">No video: run with --video.</p>')
    + `</div><div><h3 style="margin:0 0 6px">${esc(r.title)} ${tag(r.pass)}</h3>`
    + (r.reasons?.length ? `<p class="why">${r.reasons.map(esc).join('; ')}</p>` : '')
    + `<div class="hud-readouts">${[['max lean', `${r.max_theta_deg}°`], ['lean RMS', `${r.theta_rms_deg}°`], ['speed tracking RMS', `${r.speed_rms_mps} m/s`],
      ['distance', `${r.x_max_m} m`], ['energy', `${r.energy_j} J`], ...rows.map(([n, a, b, l]) => [n, `${a} (${b})`, l])]
      .map(([k, v, l]) => `<div class="r ${l ?? ''}"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>`
    + `<p style="margin-top:12px"><a class="hud-btn primary" style="text-decoration:none" href="sim.html?design=${encodeURIComponent(x.d.file)}&run=${run}">Replay in 3D</a></p></div></div>`;
}
document.body.dataset.ready = '1';
