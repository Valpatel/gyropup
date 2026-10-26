// The Gyropup simulator page: the robot built from any design, posed live, with eyes, telemetry and (when a physics run
// exists for the design) a replay of it. Parts and dimensions come from the design file and the catalog, so swapping a
// motor or a battery in the designer changes what you see here.
import * as THREE from 'three';
import { createStage } from './kit/stage.js';
import { mountAppNav } from './kit/appnav.js';
import { section, slider, chips, readouts, toggle } from './kit/panel.js';
import { buildRobot, kneeFor } from './robot3d.js';
import { createEyes, eyesGlyph } from './character/eyes.js';
import { createDarts } from './turret3d.js';
import { evaluate, indexCatalog, legPose, effectiveDesign, resolvePart } from './model.js';

const $ = (s) => document.querySelector(s);
const getJson = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); };
const STORE = 'gyropup-design-v1';

await mountAppNav({ root: '../', current: 'simulate' });
const q = new URLSearchParams(location.search);
const index = await getJson('../catalog/index.json');
const catalog = indexCatalog(await Promise.all(index.files.map((f) => getJson(`../catalog/${f}`))));
const materials = await getJson('../catalog/materials.json');
let designs = [];
try { designs = (await getJson('../exports/designs.json')).designs.map((d) => ({ name: d.name, file: d.file })); } catch { /* no summaries yet */ }
if (!designs.length) designs = [{ name: 'Gyropup (default)', file: 'designs/default.json' }];
let fromDesigner = null;
try { fromDesigner = JSON.parse(localStorage.getItem(STORE) || 'null'); } catch { /* storage blocked */ }

const sel = $('#design-select');
sel.innerHTML = (fromDesigner ? '<option value="@designer">From the designer (your current build)</option>' : '')
  + designs.map((d) => `<option value="${d.file}">${d.name}</option>`).join('');
if (q.get('design') && designs.some((d) => d.file === q.get('design'))) sel.value = q.get('design');
const runSel = $('#run-select');

const eyes = createEyes({ iris: '#55e9ff' });
const stage = createStage($('#app'), { height: 0.75, screenshots: true });
const state = { height: 0.6, pitch: 0, rollMM: 0, speed: 0, wheel: 0, alive: true, design: null, robot: null, result: null, replay: null };
const terrain = new THREE.Group();
stage.root.add(terrain);
// an outdoor yard: ground that takes light (headlight pools, the laser dot) and a few props
const yard = new THREE.Mesh(new THREE.CircleGeometry(18, 72), new THREE.MeshStandardMaterial({ color: 0x24302a, roughness: 1 }));
yard.rotation.x = -Math.PI / 2;
yard.position.y = 0.0004;
yard.receiveShadow = true;
stage.root.add(yard);
const darts = createDarts(stage.root);
const gun = { pan: 0, tilt: -0.05, mag: 24, capacity: 24, queue: [], attached: true, showFov: false, lastShot: -1, laser: true, headlights: true };

async function loadDesign(value) {
  const design = value === '@designer' ? fromDesigner : await getJson(`../${value}`);
  state.design = design;
  state.result = evaluate(design, catalog, materials);
  if (state.robot) { stage.root.remove(state.robot.group); if (state.robot.turret) stage.root.remove(state.robot.turret.laser); }
  state.robot = buildRobot(design, catalog, { eyes });
  stage.root.add(state.robot.group);
  stage.frame(state.robot.info.heightM);
  state.robot.fov.visible = gun.showFov;
  if (state.robot.turret) stage.root.add(state.robot.turret.laser);
  for (const l of state.robot.lights) { l.spot.visible = gun.headlights; l.lens.material.emissiveIntensity = gun.headlights ? 1.6 : 0.05; }
  if (state.robot.turret) {
    gun.capacity = state.design.head_payload?.magazine_shots ?? 24;
    gun.mag = gun.capacity;
    state.robot.turret.group.visible = gun.attached;
  }
  renderGun();
  renderSummary();
  telemetry(state.robot.setPose({ height: state.height }));
  await listRuns(value);
}

// ---- replays of physics runs (exports/sim/<design>/<scenario>.json)
async function listRuns(value) {
  stopReplay();
  runSel.innerHTML = '<option value="">Live pose (no replay)</option>';
  if (value === '@designer') return;
  const stem = value.split('/').pop().replace(/\.json$/, '');
  try {
    const sm = await getJson(`../exports/sim/${stem}/summary.json`);
    runSel.innerHTML += Object.entries(sm.scenarios).map(([n, r]) => `<option value="${stem}/${n}">Replay: ${r.title} — ${r.pass ? 'pass' : 'FAIL'}</option>`).join('');
  } catch { /* not simulated yet */ }
}

const propMeshes = new Map();
let replayDarts = [];
// MuJoCo geom types: 2 sphere, 3 capsule, 5 cylinder, 6 box. World frame (x fwd, y left, z up) -> page (y, z, x).
function propMesh(p) {
  const [r, g, b, a] = p.rgba;
  const material = new THREE.MeshStandardMaterial({ color: new THREE.Color(r, g, b), roughness: 0.8, transparent: a < 1, opacity: a, emissive: 0x000000 });
  let geo;
  const s = p.size;
  if (p.type === 6) geo = new THREE.BoxGeometry(2 * s[1], 2 * s[2], 2 * s[0]);
  else if (p.type === 5) geo = new THREE.CylinderGeometry(s[0], s[0], 2 * s[1], 32);
  else if (p.type === 3) geo = new THREE.CapsuleGeometry(s[0], 2 * s[1], 6, 12);
  else if (p.type === 2) geo = new THREE.SphereGeometry(s[0], 16, 12);
  else return null;
  const mesh = new THREE.Mesh(geo, material);
  mesh.position.set(p.pos[1], p.pos[2], p.pos[0]);
  mesh.quaternion.set(p.quat[2], p.quat[3], p.quat[1], p.quat[0]);
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}
function dartMesh() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.0065, 0.045, 4, 10), new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.8 }));
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.0068, 10, 8), new THREE.MeshStandardMaterial({ color: 0x2b6cff, roughness: 0.6 }));
  tip.position.y = 0.024;
  g.add(body, tip);
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  return g;
}

function boxFromMjcf(attrs) {
  const num = (k) => attrs[k]?.split(/\s+/).map(Number);
  const [sx, sy, sz] = num('size'), [px, py, pz] = num('pos'), qq = num('quat') ?? [1, 0, 0, 0];
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(2 * sy, 2 * sz, 2 * sx),
    new THREE.MeshStandardMaterial({ color: 0x5b5547, roughness: 0.9 }));
  mesh.position.set(py, pz, px);
  mesh.quaternion.set(qq[2], qq[3], qq[1], qq[0]);
  mesh.receiveShadow = true;
  return mesh;
}

async function startReplay(key) {
  stopReplay();
  if (!key) return;
  const run = await getJson(`../exports/sim/${key}.json`);
  terrain.clear();
  propMeshes.clear();
  for (const p of run.props ?? []) {
    const mesh = propMesh(p);
    if (mesh) { terrain.add(mesh); propMeshes.set(p.name, mesh); }
  }
  // physics darts: one mesh per dart body, posed from the recorded frames
  replayDarts = Object.keys(run.qpos_layout ?? {}).filter((n) => n.startsWith('dart_')).map((n) => {
    const g = dartMesh();
    stage.root.add(g);
    return { name: n, adr: run.qpos_layout[n], g };
  });
  state.replay = { run, t: 0, playing: true, rate: 1, focus: null };
  // runs with targets: frame the robot and the targets together, from behind the robot
  const targetsOnly = (run.props ?? []).filter((p) => /^target_[a-z]+$/.test(p.name));
  if (targetsOnly.length) {
    const c = new THREE.Vector3();
    for (const p of targetsOnly) c.add(new THREE.Vector3(p.pos[1], p.pos[2], p.pos[0]));
    c.divideScalar(targetsOnly.length);
    const dir = c.clone().setY(0).normalize();
    state.replay.focus = c;
    stage.camera.position.copy(dir.clone().multiplyScalar(-2.2)).add(new THREE.Vector3(-0.9, 1.6, 0));
    stage.controls.target.copy(c.clone().multiplyScalar(0.45)).setY(0.35);
  }
  replayPanel.hidden = false;
  scrub.input.max = String(run.frames.qpos.length - 1);
  replayInfo.set([['scenario', run.title], ['result', run.pass ? 'pass' : `FAIL: ${run.reasons.join('; ')}`, run.pass ? 'ok' : 'fail'],
                  ['max lean', `${run.max_theta_deg}°`], ['frames', `${run.frames.qpos.length} at ${run.frames.fps} fps`]]);
}

function stopReplay() {
  state.replay = null;
  terrain.clear();
  for (const d of replayDarts) stage.root.remove(d.g);
  replayDarts = [];
  if (typeof replayPanel !== 'undefined') replayPanel.hidden = true;
}

function renderSummary() {
  const r = state.result, d = state.design;
  $('#summary').innerHTML = `<h2>${d.name ?? 'Gyropup'}</h2>`
    + `<div class="hud-readouts">`
    + [['mass', `${r.mass.total_kg.toFixed(1)} kg`], ['chassis & actuators', `$${Math.round(r.cost.chassis_actuators_usd).toLocaleString()}`],
       ['leg torque margin', r.legs.peak_margin ? `${r.legs.peak_margin.toFixed(1)}×` : '—'],
       ['lean it can catch', r.wheels.catch_lean_deg ? `${r.wheels.catch_lean_deg.toFixed(0)}°` : '—'],
       ['runtime', r.power.runtime_min ? `${Math.round(r.power.runtime_min)} min` : '—'],
       ['checks', `${r.checks.filter((c) => c.level === 'fail').length} problems · ${r.checks.filter((c) => c.level === 'warn').length} warnings`]]
      .map(([k, v]) => `<div class="r"><span>${k}</span><b>${v}</b></div>`).join('') + '</div>';
}

// ---- panel
const panel = $('#panel');
const pose = section(panel, 'Pose', { note: 'legs keep the wheels under the hips' });
const sh = slider(pose, { label: 'Height', min: 0, max: 1, step: 0.01, value: state.height, fmt: (v) => `${Math.round(v * 100)}%`, onInput: (v) => { state.height = v; } });
slider(pose, { label: 'Body pitch', min: -20, max: 20, step: 0.5, value: 0, unit: '°', onInput: (v) => { state.pitch = v * Math.PI / 180; } });
slider(pose, { label: 'Leg difference (lean sideways)', min: -80, max: 80, step: 1, value: 0, unit: ' mm', onInput: (v) => { state.rollMM = v; } });
slider(pose, { label: 'Drive speed', min: -1.5, max: 1.5, step: 0.05, value: 0, unit: ' m/s', fmt: (v) => `${v.toFixed(2)} m/s`, onInput: (v) => { state.speed = v; } });

const replaySec = section(panel, 'Replay', { note: 'physics run from MuJoCo' });
const replayPanel = replaySec.parentElement;
replayPanel.hidden = true;
const replayInfo = readouts(replaySec);
const scrub = slider(replaySec, { label: 'Frame', min: 0, max: 1, step: 1, value: 0, fmt: (v) => `${(v / 30).toFixed(1)} s`,
  onInput: (v) => { if (state.replay) { state.replay.t = v / state.replay.run.frames.fps; state.replay.playing = false; } } });
slider(replaySec, { label: 'Speed', min: 0.1, max: 2, step: 0.1, value: 1, fmt: (v) => `${v.toFixed(1)}×`, onInput: (v) => { if (state.replay) state.replay.rate = v; } });
const playBtn = document.createElement('button');
playBtn.className = 'hud-btn primary';
playBtn.textContent = 'Play / pause';
playBtn.onclick = () => { if (state.replay) state.replay.playing = !state.replay.playing; };
replaySec.appendChild(playBtn);
const tele = readouts(section(panel, 'Telemetry', { note: 'static, from the design' }));
const gunSec = section(panel, 'Turret', { note: 'removable head payload' });
const gunInfo = readouts(gunSec);
slider(gunSec, { label: 'Pan', min: -180, max: 180, step: 1, value: 0, unit: '°', onInput: (v) => { gun.pan = v * Math.PI / 180; } });
slider(gunSec, { label: 'Tilt (never above horizontal)', min: -20, max: 0, step: 0.5, value: -3, unit: '°', onInput: (v) => { gun.tilt = v * Math.PI / 180; } });
const gunRow = document.createElement('div');
gunRow.className = 'hud-chips';
for (const [label, fn] of [['FIRE', () => queueShots(1)], ['BURST 8', () => queueShots(8)], ['RELOAD', () => { gun.mag = gun.capacity; gun.queue = []; renderGun(); }]]) {
  const b = document.createElement('button');
  b.className = 'hud-btn' + (label === 'FIRE' ? ' primary' : '');
  b.textContent = label;
  b.onclick = fn;
  gunRow.appendChild(b);
}
gunSec.appendChild(gunRow);
toggle(gunSec, 'Turret attached', true, (on) => { gun.attached = on; if (state.robot?.turret) state.robot.turret.group.visible = on; renderGun(); });
toggle(gunSec, 'Green aiming laser', true, (on) => { gun.laser = on; });
const fovToggle = toggle(gunSec, 'Show sensor fields of view', false, (on) => { gun.showFov = on; if (state.robot) state.robot.fov.visible = on; });

function queueShots(n) {
  const now = performance.now() / 1000;
  for (let k = 0; k < n; k++) gun.queue.push(now + k / 10);     // 10 shots per second
}
function renderGun() {
  const t = state.robot?.turret;
  gunInfo.set(t ? [['magazine', `${gun.mag} / ${gun.capacity} darts`, gun.mag ? 'ok' : 'fail'], ['dart speed', '24 m/s (80 fps cap)'],
                   ['status', gun.attached ? (gun.mag ? 'armed' : 'empty: drive to the dock to reload') : 'removed']]
                 : [['turret', 'none: this design has no head payload']]);
}
function shoot() {
  const t = state.robot?.turret;
  if (!t || !gun.attached || gun.mag <= 0) return false;
  darts.fire(t.muzzle);
  t.flash();
  gun.mag -= 1;
  renderGun();
  return true;
}

const eyePanel = section(panel, 'Eyes', { note: 'DualEye screens' });
const eyeChips = chips(eyePanel, eyes.expressions.map((n) => ({ id: n, html: eyesGlyph(n), title: n })), (n) => { eyes.set(n); state.lastExpr = performance.now(); });
eyeChips.mark('neutral');
const scene = section(panel, 'Scene');
toggle(scene, 'Headlights', true, (on) => { gun.headlights = on; for (const l of state.robot?.lights ?? []) { l.spot.visible = on; l.lens.material.emissiveIntensity = on ? 1.6 : 0.05; } });
slider(scene, { label: 'Daylight (lower it for dusk)', min: 0, max: 1, step: 0.01, value: 1, fmt: (v) => v.toFixed(2), onInput: (v) => stage.setSceneLight(v) });
toggle(scene, 'Liveliness (idle motion, blinks, moods)', true, (on) => { state.alive = on; $('#alive').classList.toggle('on', on); });
$('#alive').onclick = () => { state.alive = !state.alive; $('#alive').classList.toggle('on', state.alive); };

function telemetry(p) {
  const d = effectiveDesign(state.design, catalog), g = d.geometry, r = state.result;
  const act = resolvePart(d.parts.leg_actuator, catalog);
  const hip = p.hipHeightMM - g.wheel_diameter_mm / 2;
  const lever = legPose(g.thigh_mm, g.shin_mm, p.kneeDeg).knee_lever;
  const perLeg = (r.mass.supported_kg * 9.81) / 2;
  const knee = (perLeg * lever) / 1000;
  const rated = act?.specs?.rated_torque_nm;
  const lvl = rated ? (knee > rated ? 'fail' : knee > 0.66 * rated ? 'warn' : 'ok') : '';
  tele.set([
    ['hip height', `${Math.round(p.hipHeightMM)} mm`], ['knee angle', `${p.kneeDeg.toFixed(0)}°`],
    ['knee holding torque', `${knee.toFixed(1)} N·m${rated ? ` / ${rated} rated` : ''}`, lvl],
    ['wheel speed', `${Math.round(Math.abs(state.speed) / (g.wheel_diameter_mm / 2000) * 60 / (2 * Math.PI))} rpm`],
    ['track width', `${Math.round(state.robot.info.trackMM)} mm`],
  ]);
}

// ---- animation
let teleT = 0;
stage.onFrame((t, dt) => {
  if (!state.robot) return;
  if (state.replay) {
    const R = state.replay, F = R.run.frames;
    if (R.playing) R.t = (R.t + dt * R.rate) % (F.qpos.length / F.fps);
    // blend between the recorded 30 fps frames so motion stays smooth at the screen's frame rate
    const f = Math.min(F.qpos.length - 1, R.t * F.fps), i = Math.floor(f), j = Math.min(F.qpos.length - 1, i + 1), w = f - i;
    const A = F.qpos[i], B = F.qpos[j];
    const qp = A.map((v, k) => v + (B[k] - v) * w);
    const dot = A[3] * B[3] + A[4] * B[4] + A[5] * B[5] + A[6] * B[6];
    if (dot < 0) for (let k = 3; k < 7; k++) qp[k] = A[k] - (B[k] + A[k]) * w;   // shortest path between orientations
    const n = Math.hypot(qp[3], qp[4], qp[5], qp[6]) || 1;
    for (let k = 3; k < 7; k++) qp[k] /= n;
    state.robot.setFromQpos(qp, R.run.qpos_layout);
    if (R.playing) scrub.set(i);
    for (const d of replayDarts) {                             // physics darts, from MuJoCo
      const a = d.adr;
      d.g.position.set(qp[a + 1], qp[a + 2], qp[a]);
      d.g.quaternion.set(qp[a + 5], qp[a + 6], qp[a + 4], qp[a + 3]).normalize();
    }
    const tt = R.t;
    for (const ev of R.run.events ?? []) {
      const passed = ev.t <= tt && (R.lastT ?? -1) < ev.t;
      if (!passed) continue;
      if (ev.type === 'shot') {
        state.robot.turret?.flash();
        if (!replayDarts.length && state.robot.turret) darts.fire(state.robot.turret.muzzle);   // impulse-only runs
      } else if (ev.type === 'hit') {
        const m = propMeshes.get(ev.target);
        if (m) { m.material.emissive.set(0x00f0ff); m.userData.glowT = 0.35; }
      }
    }
    for (const m of propMeshes.values()) if (m.userData.glowT > 0) { m.userData.glowT -= dt; if (m.userData.glowT <= 0) m.material.emissive.set(0x000000); }
    if (tt < (R.lastT ?? 0)) darts.clear();
    R.lastT = tt;
    if (state.robot.turret) { state.robot.turret.step(dt); state.robot.turret.updateLaser([terrain], gun.laser); }
    darts.step(dt);
    const b = state.robot.base.position;
    const follow = R.focus ? new THREE.Vector3(b.x, 0.3, b.z).lerp(R.focus, 0.45) : new THREE.Vector3(b.x, b.y * 0.8, b.z);
    stage.controls.target.lerp(follow, 0.1);
    eyes.step(t, dt);
    eyes.draw();
    return;
  }
  let height = state.height, pitch = state.pitch;
  if (state.alive) {
    height = Math.min(1, Math.max(0, height + 0.025 * Math.sin(t * 1.3)));         // breathing bob
    pitch += 0.012 * Math.sin(t * 0.7) + 0.006 * Math.sin(t * 2.3);                 // balance sway
    if (!state.lastExpr || performance.now() - state.lastExpr > 9000) {             // an occasional mood
      if (Math.random() < dt * 0.15) { const n = ['neutral', 'happy', 'curious', 'thinking', 'neutral'][Math.floor(Math.random() * 5)]; eyes.set(n); eyeChips.mark(n); }
    }
  }
  pitch += -state.speed * 0.05;                                                       // lean into the drive
  state.wheel += (state.speed / state.robot.info.wheelR * 1000) * dt;
  const p = state.robot.setPose({ height, pitch, rollMM: state.rollMM, wheel: state.wheel });
  if (state.robot.turret) {
    state.robot.turret.setAim(gun.pan, gun.tilt, pitch);
    state.robot.turret.updateLaser([terrain], gun.laser);
    const now = performance.now() / 1000;
    while (gun.queue.length && gun.queue[0] <= now) { gun.queue.shift(); if (!shoot()) { gun.queue = []; break; } }
    state.robot.turret.step(dt);
  }
  darts.step(dt);
  state.robot.group.position.z += state.speed * dt;
  if (Math.abs(state.robot.group.position.z) > 2.5) state.robot.group.position.z *= -0.98;
  eyes.step(t, dt);
  eyes.draw();
  if ((teleT += dt) > 0.2) { teleT = 0; telemetry(p); }
});

window.__sim = { state, stage, eyes, setHeight: (v) => { state.height = v; sh.set(v); } };
sel.onchange = () => loadDesign(sel.value);
runSel.onchange = () => startReplay(runSel.value);
await loadDesign(sel.value);
stage.start();
// ?cam=side|front|iso and ?height=0..1 for screenshots and docs; ?run=<scenario> starts a replay
const camAt = { side: [1, 0.35, 0], front: [0, 0.35, 1], iso: [0.6, 0.45, 1], back: [0, 0.35, -1] }[q.get('cam')];
if (camAt) { const dist = state.robot.info.heightM * 2.4; stage.camera.position.set(...camAt.map((v) => v * dist)); stage.controls.target.set(0, state.robot.info.heightM * 0.45, 0); }
if (q.has('height')) window.__sim?.setHeight?.(+q.get('height'));
if (q.get('alive') === '0') { state.alive = false; $('#alive').classList.remove('on'); }
if (q.has('fire')) queueShots(+q.get('fire') || 1);
if (q.has('light')) stage.setSceneLight(+q.get('light'), true);
if (q.get('fov') === '1') { gun.showFov = true; fovToggle.checked = true; if (state.robot) state.robot.fov.visible = true; }
if (q.get('run') && sel.value !== '@designer') {
  const key = `${sel.value.split('/').pop().replace(/\.json$/, '')}/${q.get('run')}`;
  runSel.value = key;
  await startReplay(key);
  if (q.has('t') && state.replay) { state.replay.t = +q.get('t'); state.replay.playing = q.get('play') === '1'; }
}
document.body.dataset.ready = '1';

