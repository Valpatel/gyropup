// The Gyropup simulator page: the robot built from any design, posed live, with eyes, telemetry and (when a physics run
// exists for the design) a replay of it. Parts and dimensions come from the design file and the catalog, so swapping a
// motor or a battery in the designer changes what you see here.
import * as THREE from 'three';
import { createStage } from './kit/stage.js';
import { mountAppNav } from './kit/appnav.js';
import { section, slider, chips, readouts, toggle, collapsiblePanel, overlayInsets } from './kit/panel.js';
import { buildRobot, kneeFor } from './robot3d.js';
import { loadCadRig } from './cadrig.js';
import { createEyes, eyesGlyph } from './character/eyes.js';
import { createDarts } from './turret3d.js';
import { evaluate, indexCatalog, legPose, effectiveDesign, resolvePart } from './model.js';
import { createSfx } from './sfx.js';

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
// Gyropup (designs/default.json) first and selected; the designer's working copy last
designs.sort((x, y) => (y.file === 'designs/default.json') - (x.file === 'designs/default.json'));
sel.innerHTML = designs.map((d) => `<option value="${d.file}">${d.name}</option>`).join('')
  + (fromDesigner ? '<option value="@designer">From the designer (your current build)</option>' : '');
if (q.get('design') && designs.some((d) => d.file === q.get('design'))) sel.value = q.get('design');
else if (designs.some((d) => d.file === 'designs/default.json')) sel.value = 'designs/default.json';   // Gyropup on one 60 V FLEXVOLT
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
// laserMode: 'auto' (on while getting ready to fire, off between targets and at the start), 'on' or 'off'
const gun = { pan: 0, tilt: -0.05, mag: 24, capacity: 24, queue: [], attached: true, showFov: false, lastShot: -1, laserMode: 'auto', laserOn: false,
              armedUntil: 0, headlights: true };
const sfx = createSfx();
let talk = null;            // speech bubbles and voice (character/talk.js), when loaded
const react = (ev) => { try { talk?.react?.(ev); } catch { /* the voice is optional */ } };

// ---- layout: keep the robot out from under the panels
const hud = $('#hud');
const updateInsets = () => {
  const ins = overlayInsets(hud);
  const card = $('#summary');
  if (card?.classList.contains('min')) ins.top += card.getBoundingClientRect().height + 16;
  const dock = document.querySelector('.gp-dock-body');                  // the talk dock along the bottom
  const dr = dock?.offsetParent ? dock.getBoundingClientRect() : null;
  if (dr?.height && !dock.closest('.gp-dock')?.classList.contains('collapsed')) ins.bottom = Math.max(ins.bottom, window.innerHeight - dr.top + 8);
  stage.setInsets(ins);
};
const panelFold = collapsiblePanel(hud, $('#panel'), { key: 'gyropup-sim-panel', onChange: () => { updateInsets(); if (state.replay) frameReplay(); } });
window.addEventListener('resize', () => updateInsets());
const soundBtn = document.createElement('button');
soundBtn.className = 'hud-pill';
const paintSound = () => { soundBtn.innerHTML = `<span class="dot"></span>SOUND ${sfx.enabled ? 'ON' : 'OFF'}`; soundBtn.classList.toggle('on', sfx.enabled); };
soundBtn.onclick = () => { sfx.setEnabled(!sfx.enabled); paintSound(); };
paintSound();
$('#topbar').insertBefore(soundBtn, $('#alive'));

async function loadDesign(value) {
  const design = value === '@designer' ? fromDesigner : await getJson(`../${value}`);
  state.design = design;
  state.result = evaluate(design, catalog, materials);
  state.modelMass = null;                              // the physics model's mass (CAD parts), when there is a run
  if (value !== '@designer') {
    try { state.modelMass = (await getJson(`../exports/sim/${value.split('/').pop().replace(/\.json$/, '')}/summary.json`)).mass_kg; } catch { /* not simulated */ }
  }
  if (state.robot) { stage.root.remove(state.robot.group); if (state.robot.turret) stage.root.remove(state.robot.turret.laser); }
  let mech = null;                                     // the real stack from the CAD, if it was built from this design
  try { const ml = await getJson('../exports/mech-layout.json'); if (ml.design === value) mech = ml; } catch { /* no CAD yet */ }
  const cad = value === '@designer' ? null : await loadCadRig('../', value);   // the real CAD meshes, posed by the joints
  state.robot = buildRobot(design, catalog, { eyes, mech, cad });
  stage.root.add(state.robot.group);
  stage.frame(state.robot.info.heightM);
  state.robot.fov.visible = gun.showFov;
  if (state.robot.turret) stage.root.add(state.robot.turret.laser);
  for (const l of state.robot.lights) { l.spot.visible = gun.headlights; l.lens.material.emissiveIntensity = gun.headlights ? 1.6 : 0.05; }
  setDaylight(daylight);
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
  if (/^target_[a-z]+(_ring|_bull)?$/.test(p.name)) {         // targets glow a little so they read at any light level
    mesh.userData.baseEmissive = new THREE.Color(r, g, b).multiplyScalar(0.18);
    material.emissive.copy(mesh.userData.baseEmissive);
    material.roughness = 0.5;
  }
  mesh.position.set(p.pos[1], p.pos[2], p.pos[0]);
  mesh.quaternion.set(p.quat[2], p.quat[3], p.quat[1], p.quat[0]);
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}
// A short foam dart as simulated (sim/turret.py): a 38 mm foam body with a hollow tail and a rubber tip, nose along +y
// (MuJoCo's +z). Plus a motion streak drawn behind it while it flies.
const DART = {
  foam: new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.85 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x2b6cff, roughness: 0.5 }),
  hollow: new THREE.MeshStandardMaterial({ color: 0x7a3305, roughness: 1 }),
  streak: new THREE.MeshBasicMaterial({ color: 0xffc58a, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }),
};
const dartGeo = {
  body: new THREE.CylinderGeometry(0.0065, 0.0065, 0.036, 16),
  tail: new THREE.CircleGeometry(0.0042, 16),
  tip: new THREE.CylinderGeometry(0.0062, 0.0068, 0.008, 16),
  nose: new THREE.SphereGeometry(0.0062, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2),
  streak: new THREE.CylinderGeometry(0.0045, 0.0005, 1, 8, 1, true),
};
function dartMesh() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(dartGeo.body, DART.foam);
  body.position.y = -0.004;
  const tail = new THREE.Mesh(dartGeo.tail, DART.hollow);
  tail.rotation.x = Math.PI / 2;
  tail.position.y = -0.0221;
  const tip = new THREE.Mesh(dartGeo.tip, DART.rubber);
  tip.position.y = 0.018;
  const nose = new THREE.Mesh(dartGeo.nose, DART.rubber);
  nose.position.y = 0.022;
  g.add(body, tail, tip, nose);
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  const streak = new THREE.Mesh(dartGeo.streak, DART.streak);
  streak.visible = false;
  streak.frustumCulled = false;
  return { g, streak };
}

// little bursts of foam bits and sparks for hits and knock-downs
const bits = [];
const bitGeo = new THREE.SphereGeometry(0.006, 6, 4);
function burst(pos, color, n = 14, speed = 1.6) {
  for (let k = 0; k < n; k++) {
    const m = new THREE.Mesh(bitGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1 }));
    m.position.copy(pos);
    const v = new THREE.Vector3(Math.random() - 0.5, Math.random() * 0.9 + 0.2, Math.random() - 0.5).normalize().multiplyScalar(speed * (0.4 + Math.random()));
    stage.root.add(m);
    bits.push({ m, v, life: 0.5 + Math.random() * 0.3 });
  }
}
function ringFlash(pos, color) {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.05, 0.07, 32), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
  m.position.copy(pos);
  m.lookAt(stage.camera.position);
  stage.root.add(m);
  bits.push({ m, v: new THREE.Vector3(), life: 0.45, ring: true });
}
function stepBits(dt) {
  for (let i = bits.length - 1; i >= 0; i--) {
    const b = bits[i];
    b.life -= dt;
    if (b.ring) { b.m.scale.multiplyScalar(1 + dt * 7); b.m.material.opacity = Math.max(0, b.life / 0.45); }
    else { b.v.y -= 9.81 * dt; b.m.position.addScaledVector(b.v, dt); if (b.m.position.y < 0.004) { b.m.position.y = 0.004; b.v.multiplyScalar(0.3); } b.m.material.opacity = Math.min(1, b.life * 3); }
    if (b.life <= 0) { stage.root.remove(b.m); b.m.material.dispose(); bits.splice(i, 1); }
  }
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
  // knock-down plates: their geoms hang from a pivot group that turns with the hinge angle in each frame
  const movers = (run.movers ?? []).map((mv) => {
    const pivot = new THREE.Group();
    pivot.position.set(mv.pivot[1], mv.pivot[2], mv.pivot[0]);
    terrain.add(pivot);
    for (const name of mv.geoms) {
      const mesh = propMeshes.get(name);
      if (mesh) { pivot.add(mesh); mesh.position.sub(pivot.position); }
    }
    return { pivot, adr: mv.qpos, axis: new THREE.Vector3(mv.axis[1], mv.axis[2], mv.axis[0]).normalize() };
  });
  // physics darts: one mesh per dart body, posed from the recorded frames
  replayDarts = Object.keys(run.qpos_layout ?? {}).filter((n) => n.startsWith('dart_')).map((n) => {
    const { g, streak } = dartMesh();
    stage.root.add(g, streak);
    return { name: n, adr: run.qpos_layout[n], g, streak };
  });
  const laserEvents = (run.events ?? []).filter((e) => e.type === 'laser_on' || e.type === 'laser_off');
  state.replay = { run, key, t: 0, playing: true, rate: 1, focus: null, movers, laserEvents, targets: [] };
  setTimeout(() => { if (state.replay?.run === run) introLine(state.replay); }, 400);
  state.replay.targets = (run.props ?? []).filter((p) => /^target_[a-z]+$/.test(p.name)).map((p) => new THREE.Vector3(p.pos[1], p.pos[2], p.pos[0]));
  if ($('#summary') && state.replay.targets.length) $('#summary').classList.add('min');   // room for the range
  updateInsets();
  frameReplay();
  replayPanel.hidden = false;
  scrub.input.max = String(run.frames.qpos.length - 1);
  replayInfo.set([['scenario', run.title], ['result', run.pass ? 'pass' : `FAIL: ${run.reasons.join('; ')}`, run.pass ? 'ok' : 'fail'],
                  ['max lean', `${run.max_theta_deg}°`], ['frames', `${run.frames.qpos.length} at ${run.frames.fps} fps`]]);
}

// Frame the robot and every target in the part of the screen the panels leave free: from behind and above the robot,
// a little to the side, so the darts fly away from the camera towards the targets.
// what Gyropup says as each demo starts (and again each time it loops)
const INTRO = {
  stand: ['Hi! Watch me balance!', 'Hello! Standing still is harder than it looks!'],
  squat: ['Hi! Squats, here we go!', 'Hello! Down... and up!'],
  push: ['Hi! Go on, give me a shove!', 'Hello! Push me, I dare you!'],
  drive: ['Hi! Zoom zoom, here I go!', 'Hello! Time for a drive!'],
  slope: ['Hi! Uphill, here I come!', 'Hello! A hill? No problem... I hope.'],
  curb: ['Hi! A kerb ahead. Hup!', 'Hello! Watch me hop this step!'],
  recoil: ['Hi! Brace for recoil!', 'Hello! Big burst coming, hold on!'],
  look: ['Hi! What is up there?', 'Hello! Let me look up at the sky!'],
  targets: ['Hi! Target practice time! I promise to aim for the legs!', 'Hello! Five targets? Easy peasy!', 'Hi! Safety glasses on? Let us knock them down!'],
};
function introLine(R) {
  const lines = INTRO[R.run.scenario ?? R.key?.split('/').pop()] ?? ['Hi! Watch this!'];
  const line = lines[(R.introCount = (R.introCount ?? -1) + 1) % lines.length];
  try { talk?.say?.(line, { mood: 'happy' }); } catch { /* the voice is optional */ }
  if (sfx) setTimeout(() => sfx.chirp(), 120);
}

function replayShot(R) {
  const b = state.robot.base.position, r = 0.28;
  const pts = [new THREE.Vector3(b.x, state.robot.info.heightM * 1.05, b.z)];
  for (const [dx, dz] of [[r, r], [r, -r], [-r, r], [-r, -r]]) pts.push(new THREE.Vector3(b.x + dx, 0, b.z + dz));
  if (!R.targets.length) return { pts, direction: new THREE.Vector3(1, 0.5, 1.6), target: null, margin: 1.15 };
  for (const t of R.targets) pts.push(t.clone().setY(0), t.clone().setY(0.45));
  const c = R.targets.reduce((a, t) => a.add(t), new THREE.Vector3()).divideScalar(R.targets.length);
  const fwd = c.clone().setY(0).sub(new THREE.Vector3(b.x, 0, b.z)).normalize();
  const side = new THREE.Vector3(-fwd.z, 0, fwd.x);
  // over the shoulder: look at a point part of the way to the targets, so the robot stays big in the foreground
  const target = new THREE.Vector3(b.x, 0, b.z).lerp(c.clone().setY(0), 0.4).setY(0.3);
  return { pts, direction: fwd.clone().multiplyScalar(-1).addScaledVector(side, 0.35).add(new THREE.Vector3(0, 0.5, 0)), target, margin: 1.06 };
}
// Frame the robot and every target in the part of the screen the panels leave free; the camera keeps doing this as
// the robot drives (smoothly) until you orbit or zoom it yourself.
function frameReplay() {
  const R = state.replay;
  if (!R) return;
  const shot = replayShot(R);
  stage.fitView(shot.pts, shot);
  R.autoCam = true;
}
function followReplay(R) {
  if (!R.autoCam) return;
  const shot = replayShot(R);
  const want = stage.fitView(shot.pts, { ...shot, apply: false });
  stage.camera.position.lerp(want.position, 0.06);
  stage.controls.target.lerp(want.center, 0.06);
}
stage.controls.addEventListener('start', () => { if (state.replay) state.replay.autoCam = false; });   // the user took the camera

function stopReplay() {
  state.replay = null;
  terrain.clear();
  for (const d of replayDarts) stage.root.remove(d.g, d.streak);
  replayDarts = [];
  if (typeof replayPanel !== 'undefined') replayPanel.hidden = true;
}

function renderSummary() {
  const r = state.result, d = state.design;
  $('#summary').innerHTML = `<h2 class="fold" title="Show or hide the details">${d.name ?? 'Gyropup'}<span class="chev"></span></h2>`
    + `<div class="hud-readouts">`
    + [['mass', state.modelMass ? `${state.modelMass.toFixed(1)} kg (with the CAD parts)` : `${r.mass.total_kg.toFixed(1)} kg (estimate)`], ['chassis & actuators', `$${Math.round(r.cost.chassis_actuators_usd).toLocaleString()}`],
       ['leg torque margin', r.legs.peak_margin ? `${r.legs.peak_margin.toFixed(1)}×` : '—'],
       ['lean it can catch', r.wheels.catch_lean_deg ? `${r.wheels.catch_lean_deg.toFixed(0)}°` : '—'],
       ['runtime', r.power.runtime_min ? `${Math.round(r.power.runtime_min)} min` : '—'],
       ['checks', `${r.checks.filter((c) => c.level === 'fail').length} problems · ${r.checks.filter((c) => c.level === 'warn').length} warnings`]]
      .map(([k, v]) => `<div class="r"><span>${k}</span><b>${v}</b></div>`).join('') + '</div>';
  $('#summary .fold').onclick = () => { $('#summary').classList.toggle('min'); updateInsets(); if (state.replay) frameReplay(); };
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
for (const [label, fn] of [['FIRE', () => queueShots(1)], ['BURST 8', () => queueShots(8)],
  ['RELOAD', () => { gun.mag = gun.capacity; gun.queue = []; sfx.reload(); react('reload'); renderGun(); }]]) {
  const b = document.createElement('button');
  b.className = 'hud-btn' + (label === 'FIRE' ? ' primary' : '');
  b.textContent = label;
  b.onclick = fn;
  gunRow.appendChild(b);
}
gunSec.appendChild(gunRow);
toggle(gunSec, 'Turret attached', true, (on) => { gun.attached = on; if (state.robot?.turret) state.robot.turret.group.visible = on; renderGun(); });
const laserRow = document.createElement('div');
laserRow.innerHTML = '<p class="hud-note" style="margin:10px 0 4px">Green aiming laser: AUTO turns it on while getting ready to fire, off between targets</p>';
gunSec.appendChild(laserRow);
const laserChips = chips(laserRow, [{ id: 'auto', html: 'AUTO', title: 'On when getting ready to fire; off between targets and at the start' },
  { id: 'on', html: 'ON', title: 'Always on' }, { id: 'off', html: 'OFF', title: 'Always off' }], (id) => { gun.laserMode = id; laserChips.mark(id); });
laserChips.mark('auto');
const fovToggle = toggle(gunSec, 'Show sensor fields of view', false, (on) => { gun.showFov = on; if (state.robot) state.robot.fov.visible = on; });

function queueShots(n) {
  const now = performance.now() / 1000;
  // in auto, the laser comes on and the flywheels spin up first: a visible and audible "about to fire" warning
  const start = Math.max(now, gun.queue.at(-1) ?? 0) + (gun.laserMode === 'auto' && !gun.laserOn ? 0.4 : 0);
  for (let k = 0; k < n; k++) gun.queue.push(start + k / 10);     // 10 shots per second
  gun.armedUntil = Math.max(gun.armedUntil, start + n / 10 + 1.2);
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
  sfx.shot();
  gun.mag -= 1;
  if (gun.mag === 0) react('empty');
  renderGun();
  return true;
}

const eyePanel = section(panel, 'Eyes', { note: 'DualEye screens' });
const eyeChips = chips(eyePanel, eyes.expressions.map((n) => ({ id: n, html: eyesGlyph(n), title: n })), (n) => { eyes.set(n); state.lastExpr = performance.now(); });
eyeChips.mark('neutral');
const scene = section(panel, 'Scene');
toggle(scene, 'Headlights', true, (on) => { gun.headlights = on; for (const l of state.robot?.lights ?? []) { l.spot.visible = on; l.lens.material.emissiveIntensity = on ? 1.6 : 0.05; } });
slider(scene, { label: 'Daylight (lower it for dusk)', min: 0, max: 1, step: 0.01, value: 1, fmt: (v) => v.toFixed(2), onInput: (v) => { stage.setSceneLight(v); setDaylight(v); } });
toggle(scene, 'Liveliness (idle motion, blinks, moods)', true, (on) => { state.alive = on; $('#alive').classList.toggle('on', on); });
$('#alive').onclick = () => { state.alive = !state.alive; $('#alive').classList.toggle('on', state.alive); };

// headlights: dim in daylight (as eyes see them), full strength at dusk
let daylight = 1;
function setDaylight(v) {
  daylight = v;
  for (const l of state.robot?.lights ?? []) l.spot.intensity = (l.spot.userData.full ?? 70) * (0.12 + 0.88 * (1 - v) ** 1.5);
}

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

// ---- laser and flywheels: switch with sound
function setLaser(on) {
  if (on === gun.laserOn) return;
  gun.laserOn = on;
  sfx.laser(on);
  sfx.flywheels(on);
}
function replayLaser(R, tt) {
  if (gun.laserMode !== 'auto') return gun.laserMode === 'on';
  if (!R.laserEvents.length) return (R.run.events ?? []).some((e) => e.type === 'shot' && e.t - 0.6 <= tt && tt <= e.t + 0.4);   // older runs
  let on = false;
  for (const e of R.laserEvents) { if (e.t > tt) break; on = e.type === 'laser_on'; }
  return on;
}

// ---- animation
let teleT = 0;
const prevTurret = { pan: 0, tilt: 0 };
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
    for (const mv of R.movers) mv.pivot.quaternion.setFromAxisAngle(mv.axis, qp[mv.adr]);
    for (const d of replayDarts) {                             // physics darts, from MuJoCo
      const a = d.adr;
      d.g.position.set(qp[a + 1], qp[a + 2], qp[a]);
      d.g.quaternion.set(qp[a + 5], qp[a + 6], qp[a + 4], qp[a + 3]).normalize();
      const v = new THREE.Vector3(B[a + 1] - A[a + 1], B[a + 2] - A[a + 2], B[a] - A[a]).multiplyScalar(F.fps);
      const sp = v.length();
      d.streak.visible = sp > 4 && sp < 40;                    // only in flight (not when parked or teleported)
      if (d.streak.visible) {
        const len = Math.min(0.45, sp * 0.018), dir = v.divideScalar(sp);
        d.streak.scale.set(1, len, 1);
        d.streak.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir.clone().negate());
        d.streak.position.copy(d.g.position).addScaledVector(dir, -0.022 - len / 2);
      }
    }
    const lay = R.run.qpos_layout ?? {};
    const pan = qp[lay.turret_pan] ?? 0, tilt = qp[lay.turret_tilt] ?? 0;
    const bv = Math.hypot(B[0] - A[0], B[1] - A[1]) * F.fps;
    sfx.motion({ wheelSpeed: R.playing ? bv : 0, servoSpeed: R.playing && dt > 0 ? Math.hypot(pan - prevTurret.pan, tilt - prevTurret.tilt) / dt : 0 });
    prevTurret.pan = pan; prevTurret.tilt = tilt;
    const tt = R.t;
    for (const ev of R.run.events ?? []) {
      const passed = ev.t <= tt && (R.lastT ?? -1) < ev.t;
      if (!passed || !R.playing || tt - ev.t > 0.25) continue;     // seeking: skip the effects of events jumped over
      if (ev.type === 'shot') {
        state.robot.turret?.flash();
        if (R.playing) { sfx.shot(); react('fire'); }
        if (!replayDarts.length && state.robot.turret) darts.fire(state.robot.turret.muzzle);   // impulse-only runs
      } else if (ev.type === 'hit') {
        const m = propMeshes.get(ev.target);
        if (m) { m.material.emissive.set(0x00f0ff); m.userData.glowT = 0.35; }
        const dart = replayDarts.find((d) => d.name === ev.dart);
        if (dart) burst(dart.g.position, 0xffa04a, 10, 1.2);
        if (R.playing) sfx.hit();
        eyes.set('happy');                                      // a hit makes Gyropup happy for a moment
        R.moodUntil = tt + 0.8;
        react('hit');
      } else if (ev.type === 'fall') {
        eyes.set('surprised');
        R.moodUntil = tt + 3;
        react('fall');
        setTimeout(() => sfx.down(), 500);
      } else if (ev.type === 'push') {
        eyes.set('surprised');
        R.moodUntil = tt + 0.9;
      } else if (ev.type === 'down') {
        const m = propMeshes.get(ev.target);
        if (m) { const p = m.getWorldPosition(new THREE.Vector3()); burst(p, 0x00f0ff, 22, 2.2); ringFlash(p, 0x00f0ff); }
        if (R.playing) { sfx.down(); setTimeout(() => sfx.chirp(), 260); }
        eyes.set('happy');
        R.moodUntil = tt + 1.4;
        react('down');
      }
      if (ev.type === 'shot' && !(R.moodUntil > tt)) eyes.set('focused');
    }
    for (const m of propMeshes.values()) if (m.userData.glowT > 0) { m.userData.glowT -= dt; if (m.userData.glowT <= 0) m.material.emissive.copy(m.userData.baseEmissive ?? new THREE.Color(0)); }
    if (R.moodUntil && tt > R.moodUntil) { eyes.set('neutral'); R.moodUntil = 0; }
    if (tt < (R.lastT ?? 0)) { darts.clear(); if (R.playing) introLine(R); }      // looped: say hello again
    R.lastT = tt;
    const laserNow = replayLaser(R, tt);
    if (laserNow !== gun.laserOn) {
      if (R.playing) { setLaser(laserNow); if (laserNow && Math.random() < 0.35) react('banter'); } else gun.laserOn = laserNow;
    }
    if (state.robot.turret) { state.robot.turret.step(dt); state.robot.turret.updateLaser([terrain], gun.laserOn); }
    darts.step(dt);
    stepBits(dt);
    followReplay(R);
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
    const now = performance.now() / 1000;
    setLaser(gun.laserMode === 'on' || (gun.laserMode === 'auto' && gun.attached && (gun.queue.length > 0 || now < gun.armedUntil)));
    state.robot.turret.updateLaser([terrain], gun.laserOn);
    sfx.motion({ wheelSpeed: state.speed, servoSpeed: dt > 0 ? Math.hypot(gun.pan - prevTurret.pan, gun.tilt - prevTurret.tilt) / dt : 0 });
    prevTurret.pan = gun.pan; prevTurret.tilt = gun.tilt;
    while (gun.queue.length && gun.queue[0] <= now) { gun.queue.shift(); if (!shoot()) { gun.queue = []; break; } }
    state.robot.turret.step(dt);
  }
  darts.step(dt);
  stepBits(dt);
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
// Gyropup's voice: speech bubbles over its head, spoken lines, a talk dock (character/talk.js)
try {
  talk = (await import('./character/talk.js')).mountTalk({ stage, eyes, getHead: () => state.robot?.turret?.group ?? state.robot?.base });
  const dockEl = document.querySelector('.gp-dock');
  if (dockEl) new MutationObserver(() => { updateInsets(); if (state.replay?.autoCam) frameReplay(); }).observe(dockEl, { attributes: true, attributeFilter: ['class'] });
} catch (err) { console.warn('talk unavailable', err); }
updateInsets();
stage.start();
if (q.get('panel') === '0') panelFold.set(true);
if (q.get('sound') === '0') { sfx.setEnabled(false); paintSound(); talk?.setMuted?.(true); }
setTimeout(() => { if (!state.replay) react(Math.random() < 0.5 ? 'hello' : 'banter'); }, 1200);   // replays greet with their own line
// ?cam=side|front|iso and ?height=0..1 for screenshots and docs; ?run=<scenario> starts a replay
const camAt = { side: [1, 0.35, 0], front: [0, 0.35, 1], iso: [0.6, 0.45, 1], back: [0, 0.35, -1] }[q.get('cam')];
if (camAt) { const dist = state.robot.info.heightM * 2.4; stage.camera.position.set(...camAt.map((v) => v * dist)); stage.controls.target.set(0, state.robot.info.heightM * 0.45, 0); }
if (q.has('height')) window.__sim?.setHeight?.(+q.get('height'));
if (q.get('alive') === '0') { state.alive = false; $('#alive').classList.remove('on'); }
if (q.has('fire')) queueShots(+q.get('fire') || 1);
if (q.has('light')) { stage.setSceneLight(+q.get('light'), true); setDaylight(+q.get('light')); }
if (q.get('fov') === '1') { gun.showFov = true; fovToggle.checked = true; if (state.robot) state.robot.fov.visible = true; }
// target practice is the default view; ?run=none for the live pose
const runName = q.get('run') ?? 'targets';
const runKey = `${sel.value.split('/').pop().replace(/\.json$/, '')}/${runName}`;
if (runName !== 'none' && sel.value !== '@designer' && [...runSel.options].some((o) => o.value === runKey)) {
  const key = runKey;
  runSel.value = key;
  await startReplay(key);
  if (q.has('t') && state.replay) { state.replay.t = +q.get('t'); state.replay.playing = q.get('play') === '1'; }
}
document.body.dataset.ready = '1';

