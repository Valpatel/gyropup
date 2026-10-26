// Results page: every design × every scenario, with videos, motor usage and a link to replay the run in 3D.
import { mountAppNav } from './kit/appnav.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const getJson = async (u) => { const r = await fetch(u, { cache: 'no-store' }); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); };
const pct = (v) => `${Math.round(v * 100)}%`;
const tag = (ok) => `<span class="tag ${ok ? 'pass' : 'fail'}">${ok ? 'PASS' : 'FAIL'}</span>`;

await mountAppNav({ root: '../', current: 'results' });

// the overnight design loop's leaderboard (exports/iterate/leaderboard.json, mirrored from the machine running it)
try {
  const b = await getJson('../exports/iterate/leaderboard.json');
  const st = Object.entries(b.by_stage).map(([k, v]) => `${k} ${v}`).join(' · ');
  const base = b.baseline ? ` Today's design: ${b.baseline.model_mass_kg} kg.` : '';
  document.getElementById('loop-lede').insertAdjacentHTML('beforeend', `<br><b>${b.trials}</b> candidates so far, <b>${b.passing}</b> pass everything
    (updated ${esc(b.updated)}). Furthest stage reached: ${esc(st)}.${base}`);
  const f = (v, d = 2) => (v == null ? '—' : typeof v === 'number' ? v.toFixed(d) : esc(v));
  document.getElementById('loop').innerHTML = `<table class="cmp"><thead><tr><th>#</th><th>result</th><th>mass</th><th>min SF</th>
    <th>wheel defl.</th><th>print h</th><th>track</th><th>motor</th><th>thigh / shin</th><th>thigh box</th><th>shin box</th><th>yoke</th><th>crank</th><th>why not</th></tr></thead><tbody>`
    + b.best.slice(0, 15).map((r) => {
      const p = r.params || {};
      return `<tr><td>${r.trial}</td><td>${tag(r.ok)}</td><td>${f(r.model_mass_kg)} kg</td><td>${f(r.min_safety_factor)}</td><td>${f(r.wheel_deflection_mm)} mm</td><td>${f(r.print_hours, 0)}</td>`
        + `<td>${f(r.track_mm, 0)}</td><td>${esc((p.leg_actuator || '').replace('robstride-', '').toUpperCase())}</td><td>${p.thigh_mm ?? '—'} / ${p.shin_mm ?? '—'}</td>`
        + `<td>${f(p.link_w, 0)}×${f(p.link_t, 0)}×${f(p.wall, 1)}</td><td>${f(p.shin_w, 0)}×${f(p.shin_wall, 1)}</td><td>${f(p.yoke_t, 0)}/${f(p.yoke_depth, 0)}/${f(p.yoke_gusset, 0)}</td>`
        + `<td>${f(p.crank_r, 0)}</td><td class="why">${esc((r.reasons || [])[0] || '')}</td></tr>`;
    }).join('') + '</tbody></table>';
} catch { document.getElementById('loop').innerHTML = '<p class="hud-note">No design loop has run yet.</p>'; }
const designs = (await getJson('../exports/designs.json')).designs;
const sims = [];
for (const d of designs) {
  const stem = d.file.split('/').pop().replace(/\.json$/, '');
  try { sims.push({ d, stem, s: await getJson(`../exports/sim/${stem}/summary.json`) }); } catch { sims.push({ d, stem, s: null }); }
}

const scenarios = [...new Set(sims.flatMap((x) => (x.s ? Object.keys(x.s.scenarios) : [])))];
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
        + (r.top_speed_mps != null ? `<small>top speed ${r.top_speed_mps} m/s (limit ${r.speed_limit_mps})</small>` : '')
        + (r.turret ? `<small>darts: ${r.turret.hits}/${r.turret.shots} on target (${Math.round(r.turret.hit_rate * 100)}%)`
          + (r.turret.targets ? ` · ${r.turret.knocked_down}/${r.turret.targets} knocked down` : '') + '</small>' : '') + '</button>';
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
      ['distance', `${r.x_max_m} m`], ['energy', `${r.energy_j} J`],
      ...(r.turret ? [['darts on target', `${r.turret.hits} of ${r.turret.shots} (${Math.round(r.turret.hit_rate * 100)}%)`, r.turret.hit_rate >= 0.5 ? 'ok' : 'fail'],
                      ...(r.turret.targets ? [['targets knocked down', `${r.turret.knocked_down} of ${r.turret.targets}`, r.turret.knocked_down === r.turret.targets ? 'ok' : 'warn']] : []),
                      ...Object.entries(r.turret.by_target).map(([n, v]) => [n.replace('_', ' '), `${v.hits}/${v.shots}${v.knocked_down_s != null ? ` · down at ${v.knocked_down_s} s` : ''}`])] : []), ...rows.map(([n, a, b, l]) => [n, `${a} (${b})`, l])]
      .map(([k, v, l]) => `<div class="r ${l ?? ''}"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>`
    + `<p style="margin-top:12px"><a class="hud-btn primary" style="text-decoration:none" href="sim.html?design=${encodeURIComponent(x.d.file)}&run=${run}">Replay in 3D</a></p></div></div>`;
}
document.body.dataset.ready = '1';
