// The Gyropup simulator page: the robot built from any design, posed live, with eyes, telemetry and (when a physics run
// exists for the design) a replay of it. Parts and dimensions come from the design file and the catalog, so swapping a
// motor or a battery in the designer changes what you see here.
import * as THREE from 'three';
import { createStage } from './kit/stage.js';
import { mountAppNav } from './kit/appnav.js';
import { section, slider, chips, readouts, toggle, collapsiblePanel, overlayInsets } from './kit/panel.js';
import { buildRobot, kneeFor } from './robot3d.js';
import { buildRobotV2 } from './robot_v2.js';
import { loadCadRig } from './cadrig.js';
import { createEyes, eyesGlyph } from './character/eyes.js';
import { BALL, BALL_SPIN, ballMesh, createBalls } from './turret3d.js';
import { evaluate, indexCatalog, legPose, effectiveDesign, resolvePart } from './model.js';
import { createSfx } from './sfx.js';
import { createRobotActions } from './robot_actions.js';
import { createLoadingStatus } from './kit/loading.js';
import { createDataReader } from './kit/portal-data.js';

const $ = (s) => document.querySelector(s);
const dataReader = createDataReader(fetch);
const getJson = u => dataReader.json(u);
const STORE = 'gyropup-design-v1';
const startupMessage = text => { const message=$('#sim-startup .gp-loading-message'); if(message)message.textContent=text; };

await mountAppNav({ root: '../', current: 'simulate' });
const q = new URLSearchParams(location.search);
startupMessage('Loading the parts catalogue…');
const index = await getJson('../catalog/index.json');
const catalog = indexCatalog(await Promise.all(index.files.map((f) => getJson(`../catalog/${f}`))));
const materials = await getJson('../catalog/materials.json');
// one robot (D36): v2 with the five-bar legs (sim/robot_v2.py, an interim body until M5); the first, serial-leg robot
// stays as a legacy view
// the turret has its own group: on the Orin AGX compute box (the J501 enclosure), aimed and fired by hand, with its
// mechanism laid open (turret_bench.js, from cad/build_turret_box.py)
const designs = [{ group: 'Gyropup', name: 'Gyropup v2 (five-bar)', file: 'v2' }, { group: 'Gyropup', name: 'Gyropup v1 (serial legs, legacy)', file: 'designs/default.json' },
                 { group: 'Turret', name: 'Turret on the Orin AGX box', file: 'turret-box' }];
const fromDesigner = null;

const sel = $('#design-select');
sel.innerHTML = [...new Set(designs.map((d) => d.group))].map((g) => `<optgroup label="${g}">`
  + designs.filter((d) => d.group === g).map((d) => `<option value="${d.file}">${d.name}</option>`).join('') + '</optgroup>').join('');
sel.value = q.get('design') && designs.some((d) => d.file === q.get('design')) ? q.get('design') : 'v2';
const runSel = $('#run-select');

const eyes = createEyes({ iris: '#55e9ff' });
const stage = createStage($('#app'), { height: 0.75, screenshots: true });
// phones and tablets: a lighter render (fewer pixels, no shadow maps; set before the first frame compiles anything)
const phone = matchMedia('(max-width: 899px)');
if (phone.matches || matchMedia('(pointer: coarse)').matches) {
  stage.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  stage.renderer.shadowMap.enabled = false;
}
const state = { transition: null, height: 0.6, pitch: 0, rollMM: 0, speed: 0, wheel: 0, alive: true, design: null, robot: null, result: null, replay: null };
const terrain = new THREE.Group();
stage.root.add(terrain);
// an outdoor yard: ground that takes light (headlight pools, the laser dot) and a few props
const yard = new THREE.Mesh(new THREE.CircleGeometry(18, 72), new THREE.MeshStandardMaterial({ color: 0xb8cba0, roughness: 1 }));
yard.rotation.x = -Math.PI / 2;
yard.position.y = 0.0004;
yard.receiveShadow = true;
stage.root.add(yard);
const balls = createBalls(stage.root);
// laserMode: 'auto' (on while getting ready to fire, off between targets and at the start), 'on' or 'off'
const gun = { pan: 0, tilt: -0.05, mag: BALL.hopper, capacity: BALL.hopper, queue: [], attached: true, showFov: false, lastShot: -1, laserMode: 'auto', laserOn: false,
              armedUntil: 0, headlights: true };
const sfx = createSfx();
let talk = null;            // speech bubbles and voice (character/talk.js), when loaded
const reactionMood = mood => { if (!talk?.isBusy()) eyes.set(mood); };
const react = (ev) => { try { talk?.react?.(ev); } catch { /* the voice is optional */ } };

// ---- layout: keep the robot out from under the panels
const hud = $('#hud');
// A body-level overlay stays above speech bubbles without raising the whole HUD.
const sceneLoading = createLoadingStatus(document.body, { overlay:true, id:'sim-loading' });
sceneLoading.element.style.position='fixed';
function positionLoadStatus() {
  const area=$('#stage-overlay').getBoundingClientRect(), top=area.top+8;
  const actions=document.getElementById(state.bench?'tb-actions':'robot-actions');
  const actionBox=actions&&!actions.hidden&&actions.offsetParent?actions.getBoundingClientRect():null;
  Object.assign(sceneLoading.element.style,{top:`${top}px`,left:`${area.left+area.width/2}px`,
    maxWidth:`${Math.max(0,area.width-16)}px`,maxHeight:`${Math.max(44,(actionBox?.top??area.bottom)-top-8)}px`,overflow:'auto'});
}
function beginLoad(message) {
  if (!document.body.dataset.ready) { startupMessage(message); return null; }
  positionLoadStatus();
  return sceneLoading.begin(message, {onCancel:cancelPendingLoad});
}
function cancelPendingLoad() {
  ++designRequest; ++replayRequest;
  sceneLoading.dismiss();
  sel.value = state.bench ? 'turret-box' : state.modelKey;
  runSel.value = state.replay?.key ?? '';
  state.robot?.setPresentation?.(state.replay ? 'recorded' : 'current');
}
function finishLoad(token, request, type='design') {
  if (token===null) return;
  // The new model must actually draw before its loading message disappears.
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if (request === (type==='design' ? designRequest : replayRequest)) sceneLoading.ready(token);
  }));
}
const updateInsets = () => {
  const ins = overlayInsets(hud);
  // The stats card is a floating overlay. Folding it must not change projection
  // insets or restart automatic camera framing.
  const dock = document.querySelector('.gp-dock-body');                  // the talk dock along the bottom
  const dockRoot = dock?.closest('.gp-dock');
  // Both overlays load their CSS asynchronously. Their temporary normal-flow
  // rectangles are not canvas coverage and must never become camera insets.
  const dr = dock?.offsetParent && getComputedStyle(dockRoot).position !== 'static' ? dock.getBoundingClientRect() : null;
  if (dr?.height && !dock.closest('.gp-dock')?.classList.contains('collapsed')) ins.bottom = Math.max(ins.bottom, window.innerHeight - dr.top + 8);
  const bar = document.getElementById(state.bench ? 'tb-actions' : 'robot-actions');
  const br = bar && !bar.hidden && bar.offsetParent && getComputedStyle(bar).position !== 'static' ? bar.getBoundingClientRect() : null;
  if (br?.height) ins.bottom = Math.max(ins.bottom, window.innerHeight - br.top + 6);
  stage.setInsets(ins);
  positionLoadStatus();
};
const panelFold = collapsiblePanel(hud, $('#panel'), { key: 'gyropup-sim-panel', onChange: () => { updateInsets(); if (state.replay) frameReplay(); } });
[...$('#topbar').querySelectorAll('.hud-pill')].filter((b) => /PANEL/.test(b.textContent)).forEach((b) => b.classList.add('panel-pill'));
// on a phone the panel is a drawer along the bottom (sim-layout.css): a handle opens and closes it, closed at first
const drawerBtn = document.createElement('button');
drawerBtn.id = 'drawer-handle';
drawerBtn.type = 'button';
drawerBtn.innerHTML = '<span class="grip"></span>CONTROLS<span class="caret"></span>';
$('#panel').prepend(drawerBtn);
function setDrawer(open) {
  // A desktop collapse preference must never hide the only controls on a phone.
  if (phone.matches && panelFold.collapsed()) panelFold.set(false);
  hud.classList.toggle('drawer-closed', !open);
  document.body.classList.toggle('drawer-open', open && phone.matches);
  drawerBtn.setAttribute('aria-expanded', String(open));
  requestAnimationFrame(() => {
    document.documentElement.style.setProperty('--drawer-h', `${Math.round($('#panel').getBoundingClientRect().height)}px`);
    updateInsets();
  });
}
drawerBtn.onclick = () => setDrawer(hud.classList.contains('drawer-closed'));
setDrawer(!phone.matches);
phone.addEventListener('change', () => setDrawer(!phone.matches));
window.addEventListener('resize', () => { updateInsets(); if (phone.matches) document.documentElement.style.setProperty('--drawer-h', `${Math.round($('#panel').getBoundingClientRect().height)}px`); });
const soundBtn = document.createElement('button');
soundBtn.className = 'hud-pill';
const paintSound = () => { soundBtn.innerHTML = `<span class="dot"></span>SOUND ${sfx.enabled ? 'ON' : 'OFF'}`; soundBtn.classList.toggle('on', sfx.enabled); };
soundBtn.onclick = () => { sfx.setEnabled(!sfx.enabled); paintSound(); };
sfx.onChange(audio => { paintSound(); talk?.setAudio(audio); });
paintSound();
$('#topbar').insertBefore(soundBtn, $('#alive'));
// The default tour uses today's model and live ball physics. Recorded runs remain explicit archive choices.
const demo = { on: q.get('demo') !== '0' && (!q.has('run') || q.get('run') === 'none' && q.get('demo') === '1'),
  playing: true, t: 0, phase: 'Meet Gyropup', cycle: 0, shots: 0, hits: 0, nextShot: 0, anchor: 0 };
let robotActions = null;
const demoBtn = document.createElement('button');
demoBtn.className = 'hud-pill';
demoBtn.disabled = true;
const paintDemo = () => { demoBtn.innerHTML = `<span class="dot"></span>DEMO ${demo.on ? 'ON' : 'OFF'}`; demoBtn.classList.toggle('on', demo.on); };
demoBtn.title = 'Watch the current robot play live';
demoBtn.onclick = toggleDemo;
function toggleDemo() { setDemo(!demo.on); }
function setDemo(on, cancelPending = true) {
  if (cancelPending) cancelPendingLoad();
  if (!on) { takeControl(); return; }
  if (state.replay) stopReplay(); else ++replayRequest;
  demo.on = true; demo.playing = true;
  demo.anchor = state.robot?.group.position.z ?? 0;
  demo.t = 0; demo.nextShot = 0; demo.cycle = 0; demo.phase = 'Meet Gyropup'; demo.reloaded = false;
  state.speed = 0; gun.queue = [];
  state.robot?.setPresentation?.('current');
  state.robot?.setExplode?.(0);
  beginTransition();
  setupLiveRange();
  const z = demo.anchor;
  glideCamera(() => stage.fitView([new THREE.Vector3(-.55,0,z-.35),new THREE.Vector3(.55,state.robot.info.heightM,z+.35),
    ...liveTargets.map(p=>new THREE.Vector3(p.pos[1],p.pos[2],p.pos[0]))],
    {direction:new THREE.Vector3(.45,.38,-1),target:new THREE.Vector3(0,.55,z+1.1),margin:1.12}));
  runSel.value = '';
  paintDemo(); paintRobotActions();
}
paintDemo();
$('#topbar').insertBefore(demoBtn, soundBtn);

// ---- the turret on the Orin AGX box: its own scene, panel sections and action bar (loaded the first time it is picked)
let bench = null, benchLoading = null, designRequest = 0;
const robotCache = new Map();
async function enterBench(request, token) {
  if (!bench) {
    const loading = benchLoading ??= import('./turret_bench.js').then(module => module.createTurretBench({ stage, sfx, panel: $('#panel'), root: '../', onLayout: () => updateInsets() }));
    try {
      bench = await loading;
    } catch (err) {
      if (benchLoading === loading) benchLoading = null; // A transient failure must be retryable.
      if (request === designRequest) {
        if (!state.robot && !state.bench) throw err;
        sel.value = state.modelKey;
        sceneLoading.fail('The turret could not finish loading. Your game is still here.', {token,
          onRetry:()=>loadDesign('turret-box'),onCancel:cancelPendingLoad});
      }
      console.warn('Turret view unavailable:', err.message);
      return;
    }
  }
  if (request !== designRequest) return;
  stopReplay();
  state.bench = true;
  paintRobotActions();
  // A darker range makes the flight guide readable; keep the robot's daylight
  // preference separate so switching modes restores its original appearance.
  stage.setSceneLight(0.5);
  stage.setSceneBackground(0x294044, 0x071115);
  yard.material.color.setHex(0x304447);
  if (state.robot) { state.robot.group.visible = false; if (state.robot.turret) state.robot.turret.laser.visible = false; }
  for (const l of state.robot?.lights ?? []) l.spot.visible = false;
  setLaser(false);
  document.body.classList.add('bench-mode');
  for (const s of robotSections) s.hidden = true;
  for (const el of [runSel, demoBtn, $('#alive')]) el.style.display = 'none';
  const sm = bench.summary();
  $('#summary').classList.remove('min');
  $('#summary').innerHTML = `<h2 class="fold" title="Show or hide the details">${sm.title}<span class="chev"></span></h2><div class="hud-readouts">`
    + sm.rows.map(([k, v]) => `<div class="r"><span>${k}</span><b>${v}</b></div>`).join('') + '</div>';
  $('#summary .fold').onclick = () => { $('#summary').classList.toggle('min'); };
  glideCamera(() => bench.enter());
  updateInsets();
  finishLoad(token,request);
}
function leaveBench() {
  if (!state.bench) return;
  state.bench = false;
  bench?.exit();
  stage.setSceneLight(daylight);
  stage.setSceneBackground();
  yard.material.color.setHex(0xb8cba0);
  document.body.classList.remove('bench-mode');
  for (const s of robotSections) if (s !== replayPanel) s.hidden = false;
  for (const el of [runSel, demoBtn, $('#alive')]) el.style.display = '';
  paintRobotActions();
}

async function loadDesign(value) {
  const request = ++designRequest;
  ++replayRequest; // An old model's recording must not arrive on the newly selected robot.
  state.robot?.setPresentation?.(state.replay ? 'recorded' : 'current');
  if (value === state.modelKey && !state.bench) { sceneLoading.dismiss(); return; }
  const name = designs.find(d=>d.file===value)?.name ?? 'robot';
  const token = beginLoad(value==='turret-box' ? 'Loading the turret and its parts…' : `Loading ${name}…`);
  if (value === 'turret-box') { await enterBench(request,token); return; }
  // Build each hardware view once; leave the current activity and conversation running while it loads.
  if (!robotCache.has(value)) robotCache.set(value, (async () => {
    const v2 = value === 'v2';
    const design = v2 ? { name: 'Gyropup v2 (five-bar)' } : value === '@designer' ? fromDesigner : await getJson(`../${value}`);
    let robot;
    if (v2) robot = await buildRobotV2('../', { eyes });
    else {
      let mech = null;
      try { const ml = await getJson('../exports/mech-layout.json'); if (ml.design === value) mech = ml; } catch { /* no CAD yet */ }
      const cad = value === '@designer' ? null : await loadCadRig('../', value);
      robot = buildRobot(design, catalog, { eyes, mech, cad });
    }
    return { design, v2, summary:null, robot, result: v2 ? null : evaluate(design, catalog, materials) };
  })());
  let next;
  try { next = await robotCache.get(value); }
  catch (error) {
    robotCache.delete(value);
    if (request !== designRequest) return;
    if (!state.robot && !state.bench) throw error;
    if (request === designRequest) {
      sel.value = state.bench ? 'turret-box' : state.modelKey;
      sceneLoading.fail('That robot could not load. Your current view is still here.', {token,
        onRetry:()=>loadDesign(value),onCancel:cancelPendingLoad});
    }
    return;
  }
  if (request !== designRequest) return;
  leaveBench();
  stopReplay();
  const previous = state.robot;
  if (previous) {
    previous.group.visible = false;
    if (previous.turret) previous.turret.laser.visible = false;
    for (const light of previous.lights) light.spot.visible = false;
  }
  Object.assign(state, next, { modelKey: value, modelMass: next.summary?.mass_kg ?? null });
  state.robot.group.visible = true;
  if (!state.robot.group.parent) stage.root.add(state.robot.group);
  glideCamera(() => stage.frame(state.robot.info.heightM));
  state.robot.fov.visible = gun.showFov;
  if (state.robot.turret) stage.root.add(state.robot.turret.laser);
  for (const l of state.robot.lights) { l.spot.visible = gun.headlights; l.lens.material.emissiveIntensity = gun.headlights ? 1.6 : 0.05; }
  setDaylight(daylight);
  if (state.robot.turret) {
    gun.capacity = BALL.hopper;           // the CAD turret's hopper; the payload interface asks for 24 shots or more
    gun.mag = gun.capacity;
    state.robot.turret.group.visible = gun.attached;
  }
  renderGun();
  renderSummary();
  telemetry(state.robot.setPose({ height: state.height }));
  beginTransition();
  if(token===null)startupMessage('Loading recorded activities…');else sceneLoading.update('Loading recorded activities…',token);
  const runsReady = await listRuns(value, request, token);
  if (request === designRequest && demo.on) setDemo(true,false);
  if (runsReady) finishLoad(token,request);
  paintRobotActions();
}

// ---- replays of physics runs (exports/sim/<design>/<scenario>.json)
async function listRuns(value, request, token) {
  runSel.innerHTML = '<option value="">Drive & play (current robot)</option>';
  if (value === '@designer') return true;
  const stem = value.split('/').pop().replace(/\.json$/, '');
  try {
    // Metadata has its own retry path; do not cache a malformed list with usable geometry.
    const sm = await getJson(`../exports/sim/${stem}/summary.json`);
    if (request !== designRequest) return;
    if (!sm || !sm.scenarios || typeof sm.scenarios !== 'object' || Array.isArray(sm.scenarios) ||
      !Object.values(sm.scenarios).every(r=>r&&typeof r.title==='string'&&typeof r.pass==='boolean') ||
      !Number.isInteger(sm.total)||sm.total<0||!Number.isInteger(sm.passed)||sm.passed<0||sm.passed>sm.total ||
      (sm.mass_kg!==undefined&&(!Number.isFinite(sm.mass_kg)||sm.mass_kg<=0))) throw new Error('Invalid recording list');
    state.summary = sm;
    state.modelMass = sm.mass_kg ?? state.modelMass;
    runSel.innerHTML += Object.entries(sm.scenarios).map(([n, r]) => `<option value="${stem}/${n}">Recorded: ${r.title} — ${r.pass ? 'pass' : 'FAIL'}</option>`).join('');
    runSel.value=state.replay?.key ?? '';
    renderSummary();
    return true;
  } catch {
    if (request !== designRequest) return false;
    state.summary=null;renderSummary();
    const failureToken=token??sceneLoading.begin('Loading recordings…');
    sceneLoading.fail('The robot is ready, but its recordings could not load.', {token:failureToken,
      onRetry:async()=>{ const next=sceneLoading.begin('Loading recordings…',{onCancel:cancelPendingLoad});
        if(await listRuns(value,request,next))sceneLoading.ready(next); },onCancel:cancelPendingLoad});
    return false;
  }
}

const propMeshes = new Map(), propPool = new Map(), ballPool = new Map(), runCache = new Map();
let replayBalls = [], replayRequest = 0;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
function glideCamera(change) {
  const from = { position: stage.camera.position.clone(), center: stage.controls.target.clone() };
  change();
  if (!document.body.dataset.ready) return;
  state.cameraTransition = { ...from, toPosition: stage.camera.position.clone(), toCenter: stage.controls.target.clone(), elapsed: 0 };
  stage.camera.position.copy(from.position); stage.controls.target.copy(from.center);
  stage.controls.update();
}
function stepCamera(dt) {
  const T = state.cameraTransition;
  if (!T) return;
  T.elapsed += dt;
  const x = Math.min(1, T.elapsed / (reducedMotion.matches ? .18 : .85)), a = x * x * (3 - 2 * x);
  stage.camera.position.lerpVectors(T.position, T.toPosition, a);
  stage.controls.target.lerpVectors(T.center, T.toCenter, a);
  if (x === 1) state.cameraTransition = null;
}
function capturePose(object) {
  return { position: object.position.clone(), quaternion: object.quaternion.clone(), scale: object.scale.clone() };
}
function transitionObjects() {
  const objects = [...propPool.values(), ...ballPool.values()].flatMap(o => o.g ? [o.g] : [o]);
  state.robot?.group.traverse(o => objects.push(o));
  return objects;
}
function beginTransition() {
  if (!document.body.dataset.ready) return;
  state.transition = { elapsed: 0, duration: reducedMotion.matches ? .18 : .85,
    from: new Map(transitionObjects().filter(o => o.visible).map(o => [o, capturePose(o)])) };
}
function blendTransition(dt) {
  const T = state.transition;
  if (!T) return;
  T.elapsed += dt;
  const fraction = Math.min(1, T.elapsed / T.duration), alpha = fraction * fraction * (3 - 2 * fraction);
  for (const object of transitionObjects()) {
    const from = T.from.get(object);
    if (from) {
      object.position.lerpVectors(from.position, object.position, alpha);
      // The destination is this quaternion; avoid aliasing slerpQuaternions' output with its second input.
      object.quaternion.slerp(from.quaternion, 1 - alpha);
      object.scale.lerpVectors(from.scale, object.scale, alpha);
    } else if (object.userData.replayProp || object.userData.replayBall) object.scale.multiplyScalar(alpha);
  }
  if (fraction === 1) {
    state.transition = null;
    for (const mesh of propPool.values()) mesh.visible = mesh.userData.active;
  }
}
function poseProps(R) {
  for (const mesh of propPool.values()) {
    const rest = mesh.userData.replayPose;
    mesh.position.copy(rest.position); mesh.quaternion.copy(rest.quaternion);
    mesh.scale.setScalar(mesh.userData.active ? 1 : 0);
    mesh.visible = mesh.userData.active || !!state.transition;
  }
  for (const mv of R?.movers ?? []) {
    const rotation = new THREE.Quaternion().setFromAxisAngle(mv.axis, R.qpos?.[mv.adr] ?? 0);
    for (const mesh of mv.meshes) {
      mesh.position.sub(mv.origin).applyQuaternion(rotation).add(mv.origin);
      mesh.quaternion.premultiply(rotation);
    }
  }
}
function reconcileProps(run) {
  propMeshes.clear();
  for (const mesh of propPool.values()) mesh.userData.active = false;
  for (const p of run.props ?? []) {
    const key = JSON.stringify([p.name, p.type, p.size, p.rgba]);
    let mesh = propPool.get(key);
    if (!mesh) { mesh = propMesh(p); if (!mesh) continue; propPool.set(key, mesh); terrain.add(mesh); }
    mesh.position.set(p.pos[1], p.pos[2], p.pos[0]);
    mesh.quaternion.set(p.quat[2], p.quat[3], p.quat[1], p.quat[0]);
    mesh.userData.replayPose = capturePose(mesh);
    mesh.userData.active = true;
    propMeshes.set(p.name, mesh);
  }
  return (run.movers ?? []).map(mv => ({
    origin: new THREE.Vector3(mv.pivot[1], mv.pivot[2], mv.pivot[0]),
    meshes: mv.geoms.map(name => propMeshes.get(name)).filter(Boolean),
    adr: mv.qpos, axis: new THREE.Vector3(mv.axis[1], mv.axis[2], mv.axis[0]).normalize(),
  }));
}
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
  mesh.userData.replayProp = true;
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}
// The foam balls as simulated (sim/turret.py): one mesh per ball body, posed from the recorded frames, with a motion
// streak while it flies. Matched flywheels launch a ball with almost no spin, so in flight its seam turns by a cosmetic
// spin, from the frame it leaves the muzzle to its first contact (a plate or the ground: a jump in its velocity);
// after that it turns as the physics rolls it. Older runs fired dart bodies: those are drawn as balls too.
const UP = new THREE.Vector3(0, 1, 0), spinQ = new THREE.Quaternion();
function replayBall(run, name) {
  const { g, streak } = ballPool.get(name) ?? ballMesh();
  const adr = run.qpos_layout[name], F = run.frames, n = F.qpos.length;
  const shot = (run.events ?? []).find((e) => e.type === 'shot' && (e.ball ?? e.dart) === name)?.t;
  let flight = null;
  if (shot != null) {
    const z = (k) => F.qpos[k][adr + 2];
    const v = (k) => [0, 1, 2].map((c) => (F.qpos[k + 1][adr + c] - F.qpos[k][adr + c]) * F.fps);
    let i = Math.max(0, Math.floor(shot * F.fps) - 3);
    while (i < n - 1 && z(i) < 2 * BALL.d) i++;                // parked until this frame: it leaves the muzzle
    const start = i;
    for (i = start + 1; i < n - 2; i++) {
      const a = v(i - 1), b = v(i);
      if (z(i) < BALL.d || Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) > 3) break;   // drag and gravity alone: < 1.5 m/s a frame
    }
    flight = [start / F.fps, i / F.fps];                       // in the replay's clock (frames / fps)
  }
  g.userData.replayBall = true;
  return { name, adr, g, streak, flight };
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
function ringFlash(pos, color, size = 1, life = 0.45) {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.05 * size, 0.07 * size, 32), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
  m.position.copy(pos);
  m.lookAt(stage.camera.position);
  stage.root.add(m);
  bits.push({ m, v: new THREE.Vector3(), life, life0: life, ring: true });
}
function stepBits(dt) {
  for (let i = bits.length - 1; i >= 0; i--) {
    const b = bits[i];
    b.life -= dt;
    if (b.ring) { b.m.scale.multiplyScalar(1 + dt * 7); b.m.material.opacity = Math.max(0, b.life / b.life0); }
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

function validateRecording(run) {
  const vector=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
  const list=(items,check)=>items===undefined||(Array.isArray(items)&&items.every(check));
  const frames=run?.frames, width=frames?.qpos?.[0]?.length;
  if (!frames || !Number.isFinite(frames.fps) || frames.fps<=0 || !(width>=7) ||
    !Array.isArray(frames.qpos) || !frames.qpos.every(f=>vector(f,width)&&Math.hypot(...f.slice(3,7))>0)) throw new Error('Invalid recording frames');
  const layout=run.qpos_layout;
  if (!layout || Array.isArray(layout) || typeof layout!=='object' || !Object.entries(layout).every(([name,index])=>
    Number.isInteger(index)&&index>=0&&index+(/^(root$|ball_|dart_)/.test(name)?7:1)<=width)) throw new Error('Invalid recording joints');
  if (!list(run.props,p=>p&&typeof p.name==='string'&&[2,3,5,6].includes(p.type)&&vector(p.pos,3)&&
    vector(p.quat,4)&&Math.hypot(...p.quat)>0&&vector(p.size,3)&&p.size.every(v=>v>=0)&&vector(p.rgba,4))) throw new Error('Invalid recording scenery');
  const names=new Set((run.props??[]).map(p=>p.name));
  if (!list(run.movers,m=>m&&vector(m.pivot,3)&&vector(m.axis,3)&&Math.hypot(...m.axis)>0&&
    Number.isInteger(m.qpos)&&m.qpos>=0&&m.qpos<width&&Array.isArray(m.geoms)&&m.geoms.every(n=>names.has(n)))) throw new Error('Invalid recording motion');
  if (!list(run.events,e=>e&&typeof e.type==='string'&&Number.isFinite(e.t)&&e.t>=0)||
    !list(run.reasons,r=>typeof r==='string')) throw new Error('Invalid recording events');
}

async function startReplay(key) {
  const request = ++replayRequest;
  if (!key) { stopReplay(); return; }
  ++designRequest;
  sel.value=state.modelKey;
  state.robot?.setPresentation?.(state.replay ? 'recorded' : 'current');
  const token=beginLoad('Loading the recording…');
  let run;
  try {
    // No reset while loading. A late response must not replace a newer player choice.
    if (!runCache.has(key)) runCache.set(key, getJson(`../exports/sim/${key}.json`));
    run = await runCache.get(key);
    // Validate every field used by scene construction before switching the robot presentation.
    validateRecording(run);
  } catch (error) {
    runCache.delete(key);
    if (request === replayRequest) {
      runSel.value = state.replay?.key ?? '';
      sceneLoading.fail('That recording could not load. You can keep playing.', {token,
        onRetry:()=>startReplay(key),onCancel:cancelPendingLoad});
    }
    return;
  }
  if (request !== replayRequest || state.bench) return;
  if(token===null)startupMessage('Loading the recorded robot…');else sceneLoading.update('Loading the recorded robot…',token);
  try { await state.robot.setPresentation?.('recorded'); }
  catch (error) { if (request === replayRequest) { runSel.value = state.replay?.key ?? ''; sceneLoading.fail('The recorded robot could not load. Your current view is still here.',
    {token,onRetry:()=>startReplay(key),onCancel:cancelPendingLoad}); } return; }
  if (request !== replayRequest || state.bench) return;
  demo.on = false; paintDemo();
  gun.queue = []; // No latent live burst may fire after watching a recording.
  for (const ball of balls.active) ball.g.visible = false;
  state.cameraTransition = null;
  beginTransition();
  const movers = reconcileProps(run);
  for (const b of ballPool.values()) { b.g.visible = false; b.streak.visible = false; }
  replayBalls = Object.keys(run.qpos_layout ?? {}).filter(n => /^(ball|dart)_/.test(n)).map(name => {
    const ball = replayBall(run, name);
    ballPool.set(name, ball); ball.g.visible = true;
    if (!ball.g.parent) stage.root.add(ball.g, ball.streak);
    return ball;
  });
  const laserEvents = (run.events ?? []).filter(e => e.type === 'laser_on' || e.type === 'laser_off');
  state.replay = { run, key, t: 0, playing: true, rate: 1, focus: null, movers, laserEvents,
    targets: (run.props ?? []).filter(p => /^target_[a-z]+$/.test(p.name)).map(p => new THREE.Vector3(p.pos[1], p.pos[2], p.pos[0])) };
  const replay = state.replay;
  setTimeout(() => { if (state.replay === replay) introLine(replay); }, 400);
  if ($('#summary') && replay.targets.length) $('#summary').classList.add('min');
  updateInsets();
  // The first frame is composed before the canvas appears. Later changes always glide.
  if (document.body.dataset.ready) replay.autoCam = true;
  else frameReplay();
  replayPanel.hidden = false;
  scrub.input.max = String(run.frames.qpos.length - 1);
  scrub.set(0);
  replayInfo.set([['model', 'Recorded physics · earlier turret snapshot'], ['scenario', run.title], ['result', run.pass ? 'pass' : `FAIL: ${(run.reasons??[]).join('; ')}`, run.pass ? 'ok' : 'fail'],
                  ['max lean', `${run.max_theta_deg}°`], ['frames', `${run.frames.qpos.length} at ${run.frames.fps} fps`]]);
  paintRobotActions(); renderGun();
  finishLoad(token,request,'replay');
}

// Frame the robot and every target in the part of the screen the panels leave free: from behind and above the robot,
// a little to the side, so the balls fly away from the camera towards the targets.
// Activity hints are optional banter: never interrupt a question or greet again on every loop.
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
  try { talk?.announce?.(line, { mood: 'happy' }); } catch { /* the voice is optional */ }

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
  if (!document.body.dataset.ready) stage.fitView(shot.pts, shot);
  R.autoCam = true;
}
function followReplay(R) {
  if (!R.autoCam) return;
  const shot = replayShot(R);
  const want = stage.fitView(shot.pts, { ...shot, apply: false });
  stage.camera.position.lerp(want.position, 0.06);
  stage.controls.target.lerp(want.center, 0.06);
}
stage.controls.addEventListener('start', () => { state.cameraTransition = null; if (state.replay) state.replay.autoCam = false; });   // the user took the camera

function stopReplay() {
  ++replayRequest;
  beginTransition();
  // Keep the range and targets where the player left them in Drive & play.
  for (const mesh of propPool.values()) mesh.userData.replayPose = capturePose(mesh);
  state.replay = null;
  state.robot?.setPresentation?.('current');
  for (const ball of balls.active) ball.g.visible = true;
  for (const b of replayBalls) { b.g.visible = false; b.streak.visible = false; }
  replayBalls = [];
  if (typeof replayPanel !== 'undefined') replayPanel.hidden = true;
  paintRobotActions();
}

function renderSummary() {
  if (state.v2) {
    const i = state.robot.info, sm = state.summary;
    $('#summary').innerHTML = `<h2 class="fold" title="Show or hide the details">Gyropup v2 (five-bar)<span class="chev"></span></h2>`
      + `<div class="hud-readouts">`
      + [['recorded rig mass', `${(i.massKg ?? state.modelMass ?? 0).toFixed(1)} kg (earlier physics snapshot)`], ['legs', `five-bar, 2 x RS-04 each, ${Math.round(i.hMin)}-${Math.round(i.hMax)} mm`],
         ['track', `${Math.round(i.trackMM)} mm`], ['recorded physics', sm ? `${sm.passed}/${sm.total} earlier scenarios pass` : 'reports unavailable'],
         ['top deck', i.deck ? `lidar in front, turret behind: ${i.deck.tilt_max_forward_deg}° down over it, ${i.deck.lidar_hidden_deg}° hidden` : 'turret'],
         ['body', 'interim placeholder until M5']]
        .map(([k, v]) => `<div class="r"><span>${k}</span><b>${v}</b></div>`).join('') + '</div>';
    $('#summary .fold').onclick = () => { $('#summary').classList.toggle('min'); };
    return;
  }
  const r = state.result, d = state.design;
  $('#summary').innerHTML = `<h2 class="fold" title="Show or hide the details">${d.name ?? 'Gyropup'}<span class="chev"></span></h2>`
    + `<div class="hud-readouts">`
    + [['mass', state.modelMass ? `${state.modelMass.toFixed(1)} kg (with the CAD parts)` : `${r.mass.total_kg.toFixed(1)} kg (estimate)`], ['chassis & actuators', `$${Math.round(r.cost.chassis_actuators_usd).toLocaleString()}`],
       ['leg torque margin', r.legs.peak_margin ? `${r.legs.peak_margin.toFixed(1)}×` : '—'],
       ['lean it can catch', r.wheels.catch_lean_deg ? `${r.wheels.catch_lean_deg.toFixed(0)}°` : '—'],
       ['runtime', r.power.runtime_min ? `${Math.round(r.power.runtime_min)} min` : '—'],
       ['checks', `${r.checks.filter((c) => c.level === 'fail').length} problems · ${r.checks.filter((c) => c.level === 'warn').length} warnings`]]
      .map(([k, v]) => `<div class="r"><span>${k}</span><b>${v}</b></div>`).join('') + '</div>';
  $('#summary .fold').onclick = () => { $('#summary').classList.toggle('min'); };
}

// ---- panel
const panel = $('#panel');
const pose = section(panel, 'Pose', { note: 'legs keep the wheels under the hips' });
const sh = slider(pose, { label: 'Height', min: 0, max: 1, step: 0.01, value: state.height, fmt: (v) => `${Math.round(v * 100)}%`, onInput: (v) => { takeControl(); state.height = v; } });
const pitchSlider = slider(pose, { label: 'Body pitch', min: -20, max: 20, step: 0.5, value: 0, unit: '°', onInput: (v) => { takeControl(); state.pitch = v * Math.PI / 180; } });
const rollSlider = slider(pose, { label: 'Leg difference (lean sideways)', min: -80, max: 80, step: 1, value: 0, unit: ' mm', onInput: (v) => { takeControl(); state.rollMM = v; } });
const driveSlider = slider(pose, { label: 'Drive speed', min: -1.5, max: 1.5, step: 0.05, value: 0, unit: ' m/s', fmt: (v) => `${v.toFixed(2)} m/s`, onInput: (v) => { takeControl(); state.speed = v; } });

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
const panSlider = slider(gunSec, { label: 'Pan', min: -180, max: 180, step: 1, value: 0, unit: '°', onInput: (v) => { takeControl(); gun.pan = v * Math.PI / 180; } });
const tiltSlider = slider(gunSec, { label: 'Tilt (never above horizontal)', min: -20, max: 0, step: 0.5, value: -3, unit: '°', onInput: (v) => { takeControl(); gun.tilt = v * Math.PI / 180; } });
const gunRow = document.createElement('div');
gunRow.className = 'hud-chips';
for (const [label, fn] of [['FIRE', () => queueShots(1)], ['BURST 8', () => queueShots(8)],
  ['RELOAD', reloadRobot]]) {
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

function stopDemoAutomation() {
  if (demo.on) { gun.queue = []; gun.armedUntil = 0; state.speed = 0; setLaser(false); }
  demo.on = false; demo.playing = true; paintDemo();
}
function takeControl() {
  cancelPendingLoad();
  stopDemoAutomation();
  runSel.value = '';
  if (state.replay) stopReplay(); else { ++replayRequest; state.robot?.setPresentation?.('current'); }
  paintRobotActions();
}
function reloadRobot() {
  takeControl(); gun.mag = gun.capacity; gun.queue = [];
  state.robot?.setExplode?.(0); state.robot?.turret?.reload?.();
  sfx.reload(); react('reload'); renderGun();
}
function queueShots(n) {
  if (!state.robot?.turret || !gun.attached) return;
  takeControl();
  state.robot.setExplode?.(0);
  scheduleShots(n);
}
function scheduleShots(n) {
  const now = performance.now() / 1000;
  // in auto, the laser comes on and the flywheels spin up first: a visible and audible "about to fire" warning
  const start = Math.max(now, gun.queue.at(-1) ?? 0) + (gun.laserMode === 'auto' && !gun.laserOn ? 0.4 : 0);
  for (let k = 0; k < n; k++) gun.queue.push(start + k / 10);     // 10 shots per second
  gun.armedUntil = Math.max(gun.armedUntil, start + n / 10 + 1.2);
}
function renderGun() {
  paintRobotActions();
  const t = state.robot?.turret;
  gunInfo.set(t ? [['hopper', `${gun.mag} / ${gun.capacity} balls`, gun.mag ? 'ok' : 'fail'],
                   ['ammo', `foam balls, Ø${(BALL.d * 1000).toFixed(1)} mm, ${(BALL.mass * 1000).toFixed(2)} g`],
                   ['ball speed', `${t.launchSpeed ?? BALL.speed} m/s (${BALL.fps} fps cap)`],
                   ['status', gun.attached ? (gun.mag ? 'ready' : 'empty: press RELOAD') : 'removed']]
                 : [['turret', 'none: this design has no head payload']]);
}
function shoot() {
  const t = state.robot?.turret;
  if (!t || !gun.attached || gun.mag <= 0) return false;
  balls.fire(t.muzzle);
  t.flash();
  sfx.shot();
  gun.mag -= 1;
  if (demo.on) demo.shots++;
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
const aliveToggle = toggle(scene, 'Liveliness (idle motion, blinks, moods)', true, (on) => { state.alive = on; $('#alive').classList.toggle('on', on); });
$('#alive').onclick = () => { state.alive = !state.alive; aliveToggle.checked = state.alive; $('#alive').classList.toggle('on', state.alive); };
const robotSections = [...$('#panel').querySelectorAll('details.hud-section')];     // hidden while the turret bench is up
const soundSection = section(panel, 'Sound', { note: 'effects + voice' }); // Shared by robot and bench modes.
slider(soundSection, { label: 'Volume', min: 0, max: 1, step: 0.01, value: sfx.volume,
  fmt: value => `${Math.round(value * 100)}%`, onInput: value => sfx.setVolume(value) });

// headlights: dim in daylight (as eyes see them), full strength at dusk
let daylight = 1;
function setDaylight(v) {
  daylight = v;
  for (const l of state.robot?.lights ?? []) l.spot.intensity = (l.spot.userData.full ?? 70) * (0.12 + 0.88 * (1 - v) ** 1.5);
}

function telemetry(p) {
  if (state.v2) {
    const i = state.robot.info;
    tele.set([['leg length', `${Math.round(p.legMM)} mm (hip line to axle)`], ['hip height', `${Math.round(p.hipHeightMM)} mm`],
              ['wheel speed', `${Math.round(Math.abs(state.speed) / (i.wheelR / 1000) * 60 / (2 * Math.PI))} rpm`],
              ['track width', `${Math.round(i.trackMM)} mm`], ['recorded rig mass', `${(i.massKg ?? 0).toFixed(1)} kg`]]);
    return;
  }
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

// The live showcase is a kinematic play sequence, not a new recorded physics result.
const liveTargets = [-.65, 0, .65].map((x, i) => ({ name: `target_${String.fromCharCode(97 + i)}`, type: 5,
  size: [.17, .018, 0], pos: [3, x, .55], quat: [Math.SQRT1_2, 0, Math.SQRT1_2, 0],
  rgba: [[.15,.63,.63,1],[.95,.35,.15,1],[.36,.52,.8,1]][i] }));
function setupLiveRange() {
  for (const target of liveTargets) target.pos[0] = demo.anchor + 3;
  reconcileProps({ props: liveTargets.flatMap(p => [p, { name: p.name + '_stand', type: 6,
    size: [.025,.025,.25], pos: [p.pos[0],p.pos[1],.25], quat: [1,0,0,0], rgba: [.3,.4,.36,1] }]) });
}
function stepDemo(dt) {
  demo.t += dt;
  const cycle = Math.floor(demo.t / 24), time = demo.t % 24;
  const phase = time < 4 ? 'Meet Gyropup' : time < 10 ? 'Make a move' : time < 20 ? 'Target practice' : 'Ready again';
  if (phase !== demo.phase) { demo.phase = phase; paintRobotActions(); }
  if (cycle !== demo.cycle) { demo.cycle = cycle; demo.nextShot = 0; }
  state.height = .6 + (time < 4 ? .12 * Math.sin(Math.PI * time / 2) : 0);
  state.pitch = 0; state.rollMM = time < 4 ? 12 * Math.sin(Math.PI * time / 2) : 0;
  // A smooth out-and-back move stays close to the same range, without teleporting at the edge.
  const driveTime = Math.max(0, Math.min(6, time - 4));
  state.speed = time >= 4 && time < 10 ? .3 * Math.sin(Math.PI * driveTime / 3) : 0;
  if (time >= 10 && time < 20) {
    const target = liveTargets[Math.min(2, Math.floor((time - 10) / 3.3))];
    const muzzle = state.robot.turret?.muzzle;
    if (muzzle) {
      const origin = muzzle.getWorldPosition(new THREE.Vector3());
      const dx = target.pos[1] - origin.x, dz = target.pos[0] - origin.z, distance = Math.hypot(dx,dz);
      const speed = state.robot.turret.launchSpeed ?? BALL.speed;
      gun.pan = Math.atan2(dx,dz);
      gun.tilt = Math.min(0, Math.atan2(target.pos[2] - origin.y + 9.81 * distance * distance / (2 * speed * speed), distance));
    }
    if (demo.t >= demo.nextShot && time > 10.8 && gun.mag > 0 && !gun.queue.length) {
      scheduleShots(1); demo.nextShot = demo.t + 1.25;
    }
  } else { gun.pan = .28 * Math.sin(time * .65); gun.tilt = -.05; }
  if (time >= 20 && !demo.reloaded) {
    gun.mag = gun.capacity; gun.queue = []; state.robot.turret?.reload?.(); sfx.reload(); renderGun(); demo.reloaded = true;
  }
  if (time < 20) demo.reloaded = false;
}
function syncLiveControls() {
  // Update on animation frames, after input callbacks have stored the player's choice.
  // Programmatic set() paints the control without dispatching another input event.
  for (const [control, value] of [[sh,state.height],[pitchSlider,state.pitch*180/Math.PI],
    [rollSlider,state.rollMM],[driveSlider,state.speed],[panSlider,gun.pan*180/Math.PI],[tiltSlider,gun.tilt*180/Math.PI]]) {
    const step = +control.input.step, rounded = Math.round(value/step)*step;
    if (Math.abs(control.get()-rounded) > step/10) control.set(rounded);
  }
}
const liveHitRay = new THREE.Raycaster();
function stepLiveBalls(dt) {
  if (!dt) return;
  const previous = new Map(balls.active.filter(b => !b.resting).map(b => [b,b.g.position.clone()]));
  balls.step(dt);
  for (const [ball, from] of previous) {
    const delta = ball.g.position.clone().sub(from), distance = delta.length();
    if (!distance || ball.hitTarget) continue;
    liveHitRay.set(from,delta.divideScalar(distance));liveHitRay.far = distance + BALL.d / 2;
    const hit = liveHitRay.intersectObjects([...propMeshes.values()].filter(m=>m.visible),false)[0];
    if (!hit) continue;
    const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
    if (normal.dot(ball.v) > 0) normal.negate();
    ball.g.position.copy(hit.point).addScaledVector(normal,BALL.d / 2);
    ball.v.reflect(normal).multiplyScalar(.2);ball.hitTarget = true;
    hit.object.material.emissive.set(0x67e7b2);hit.object.userData.glowT = .7;
    demo.hits++;sfx.hit();react('hit');ringFlash(hit.point,0x8bf1b7,.5,.3);
  }
  for (const mesh of propMeshes.values()) if (mesh.userData.glowT > 0) {
    mesh.userData.glowT -= dt;
    if (mesh.userData.glowT <= 0) mesh.material.emissive.copy(mesh.userData.baseEmissive ?? new THREE.Color(0));
  }
}

// ---- animation
let teleT = 0;
const prevTurret = { pan: 0, tilt: 0 };
stage.onFrame((t, dt) => {
  stepCamera(dt);
  paintRobotActions();
  if (state.bench) { bench?.step(t, dt); return; }
  if (!state.robot) return;
  if (state.replay) {
    const R = state.replay, F = R.run.frames;
    if (R.playing && !state.transition) {
      const dur = F.qpos.length / F.fps, nt = R.t + dt * R.rate;
      if (nt >= dur) { beginTransition(); R.t = 0; R.lastT = -1; }
      else R.t = nt;
    }
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
    R.qpos = qp;
    poseProps(R);
    for (const b of replayBalls) {                             // physics balls, from MuJoCo
      const a = b.adr;
      b.g.scale.setScalar(1);
      b.g.position.set(qp[a + 1], qp[a + 2], qp[a]);
      b.g.quaternion.set(qp[a + 5], qp[a + 6], qp[a + 4], qp[a + 3]).normalize();
      if (b.flight) b.g.quaternion.multiply(spinQ.setFromAxisAngle(UP, BALL_SPIN * Math.min(Math.max(R.t - b.flight[0], 0), b.flight[1] - b.flight[0])));
      const v = new THREE.Vector3(B[a + 1] - A[a + 1], B[a + 2] - A[a + 2], B[a] - A[a]).multiplyScalar(F.fps);
      const sp = v.length();
      b.streak.visible = !state.transition && sp > 4 && sp < 40;                    // only in flight (not when parked or teleported)
      if (b.streak.visible) {
        const len = Math.min(0.4, sp * 0.016), dir = v.divideScalar(sp);
        b.streak.scale.set(1, len, 1);
        b.streak.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir.clone().negate());
        b.streak.position.copy(b.g.position).addScaledVector(dir, -BALL.d / 2 - len / 2);
      }
    }
    const lay = R.run.qpos_layout ?? {};
    const pan = qp[lay.turret_pan] ?? 0, tilt = qp[lay.turret_tilt] ?? 0;
    // the drive's speed along the heading (signed, m/s) and the fastest leg motor (signed, rad/s), from the frames
    const yaw = Math.atan2(2 * (A[3] * A[6] + A[4] * A[5]), 1 - 2 * (A[5] * A[5] + A[6] * A[6]));
    const bv = ((B[0] - A[0]) * Math.cos(yaw) + (B[1] - A[1]) * Math.sin(yaw)) * F.fps;
    R.legKeys ??= Object.keys(lay).filter((n) => /^(motor_[fr]_[lr]|hip_[lr]|knee_[lr])$/.test(n));
    let legSpeed = 0;
    for (const n of R.legKeys) { const w = (B[lay[n]] - A[lay[n]]) * F.fps; if (Math.abs(w) > Math.abs(legSpeed)) legSpeed = w; }
    sfx.motion({ wheelSpeed: R.playing ? bv : 0, legSpeed: R.playing ? legSpeed : 0,
                 servoSpeed: R.playing && dt > 0 ? Math.hypot(pan - prevTurret.pan, tilt - prevTurret.tilt) / dt : 0 });
    prevTurret.pan = pan; prevTurret.tilt = tilt;
    const tt = R.t;
    for (const ev of R.run.events ?? []) {
      const passed = ev.t <= tt && (R.lastT ?? -1) < ev.t;
      if (!passed || !R.playing || state.transition || tt - ev.t > 0.25) continue;     // seeking: skip the effects of events jumped over
      if (ev.type === 'shot') {
        state.robot.turret?.flash();
        if (R.playing) { sfx.shot(); react('fire'); }
        if (!replayBalls.length && state.robot.turret) balls.fire(state.robot.turret.muzzle);   // impulse-only runs
      } else if (ev.type === 'hit') {
        const m = propMeshes.get(ev.target);
        if (m) { m.material.emissive.set(0x00f0ff); m.userData.glowT = 0.35; }
        const ball = replayBalls.find((b) => b.name === (ev.ball ?? ev.dart));
        if (ball) { ringFlash(ball.g.position, BALL.color, 0.4, 0.25); burst(ball.g.position, 0xfff1a8, 6, 0.9); }   // a foam "boop"
        if (R.playing) sfx.hit();
        reactionMood('happy');                                      // a hit makes Gyropup happy for a moment
        R.moodUntil = tt + 0.8;
        react('hit');
      } else if (ev.type === 'fall') {
        reactionMood('surprised');
        R.moodUntil = tt + 3;
        react('fall');
        setTimeout(() => sfx.down(), 500);
      } else if (ev.type === 'push') {
        reactionMood('surprised');
        R.moodUntil = tt + 0.9;
      } else if (ev.type === 'down') {
        const m = propMeshes.get(ev.target);
        if (m) { const p = m.getWorldPosition(new THREE.Vector3()); burst(p, 0x00f0ff, 22, 2.2); ringFlash(p, 0x00f0ff); }
        if (R.playing) { sfx.down(); setTimeout(() => sfx.chirp(), 260); }
        reactionMood('happy');
        R.moodUntil = tt + 1.4;
        react('down');
      }
      if (ev.type === 'shot' && !(R.moodUntil > tt)) reactionMood('focused');
    }
    for (const m of propMeshes.values()) if (m.userData.glowT > 0) { m.userData.glowT -= dt; if (m.userData.glowT <= 0) m.material.emissive.copy(m.userData.baseEmissive ?? new THREE.Color(0)); }
    if (R.moodUntil && tt > R.moodUntil) { reactionMood('neutral'); R.moodUntil = 0; }
    R.lastT = tt;
    const laserNow = replayLaser(R, tt);
    if (laserNow !== gun.laserOn) {
      if (R.playing) { setLaser(laserNow); if (laserNow && Math.random() < 0.35) react('banter'); } else gun.laserOn = laserNow;
    }
    if (state.robot.turret) { state.robot.turret.step(dt); state.robot.turret.updateLaser([...propMeshes.values()], gun.laserOn); }
    balls.step(dt);
    stepBits(dt);
    blendTransition(dt);
    followReplay(R);
    eyes.step(t, dt);
    eyes.draw();
    return;
  }
  const paused = demo.on && !demo.playing;
  const motionDt = paused ? 0 : dt;
  if (demo.on && demo.playing) stepDemo(dt);
  syncLiveControls();
  poseProps(null);
  let height = state.height, pitch = state.pitch;
  const liveTime = demo.on ? demo.t : t;
  if (state.alive) {
    height = Math.min(1, Math.max(0, height + 0.025 * Math.sin(liveTime * 1.3)));         // breathing bob
    pitch += 0.012 * Math.sin(liveTime * 0.7) + 0.006 * Math.sin(liveTime * 2.3);                 // balance sway
    if (!talk?.isBusy() && (!state.lastExpr || performance.now() - state.lastExpr > 9000)) {             // an occasional mood
      if (Math.random() < dt * 0.15) { const n = ['neutral', 'happy', 'curious', 'thinking', 'neutral'][Math.floor(Math.random() * 5)]; eyes.set(n); eyeChips.mark(n); }
    }
  }
  pitch += -state.speed * 0.05;                                                       // lean into the drive
  state.wheel += (state.speed / state.robot.info.wheelR * 1000) * motionDt;
  const p = state.robot.setPose({ height, pitch, rollMM: state.rollMM, wheel: state.wheel });
  if (state.robot.turret) {
    state.robot.turret.setAim(gun.pan, Math.max(gun.tilt, -tiltLimit(gun.pan)), pitch);
    const now = performance.now() / 1000;
    setLaser(!paused && (gun.laserMode === 'on' || (gun.laserMode === 'auto' && gun.attached && (gun.queue.length > 0 || now < gun.armedUntil))));
    state.robot.turret.updateLaser([...propMeshes.values()], gun.laserOn);
    const legSpeed = dt > 0 ? ((height - (state.prevHeight ?? height)) / dt) * 3 : 0;   // live pose: the height's rate (~rad/s)
    state.prevHeight = height;
    sfx.motion({ wheelSpeed: paused ? 0 : state.speed, legSpeed: paused ? 0 : legSpeed, servoSpeed: paused ? 0 : dt > 0 ? Math.hypot(gun.pan - prevTurret.pan, gun.tilt - prevTurret.tilt) / dt : 0 });
    prevTurret.pan = gun.pan; prevTurret.tilt = gun.tilt;
    while (!paused && gun.queue.length && gun.queue[0] <= now) { gun.queue.shift(); if (!shoot()) { gun.queue = []; break; } }
    state.robot.turret.step(motionDt);
  }
  stepLiveBalls(motionDt);
  stepBits(motionDt);
  state.robot.group.position.z += state.speed * motionDt;
  if (!demo.on && Math.abs(state.robot.group.position.z) > 2.5) state.robot.group.position.z *= -0.98;
  blendTransition(motionDt);
  eyes.step(t, dt);
  eyes.draw();
  if ((teleT += dt) > 0.2) { teleT = 0; telemetry(p); }
});

// v2: the most the barrel may depress at a pan (rad), from the model's table (the lidar sits in front of the turret)
function tiltLimit(pan) {
  const tb = state.robot?.info?.deck?.tilt_max_deg;
  if (!tb?.length) return Infinity;
  const d = ((pan * 180 / Math.PI + 540) % 360) - 180;
  const i = tb.findIndex((r) => r[0] >= d);
  if (i <= 0) return tb[i < 0 ? tb.length - 1 : 0][1] * Math.PI / 180;
  const [p0, t0] = tb[i - 1], [p1, t1] = tb[i];
  return (t0 + (t1 - t0) * (d - p0) / (p1 - p0)) * Math.PI / 180;
}

function paintRobotActions() {
  robotActions?.paint({ hidden: !!state.bench, demoOn: demo.on, replay: !!state.replay, playing: state.replay ? state.replay.playing : demo.playing, demoPhase: demo.phase, legacy: !state.v2,
    scenario: state.replay?.key?.split('/').pop(), mag: gun.mag, capacity: gun.capacity, attached: !!state.robot?.turret && gun.attached });
}
robotActions = createRobotActions({ parent: $('#stage-overlay'), onDemo: toggleDemo,
  onPlay: () => { if (state.replay) state.replay.playing = !state.replay.playing; else if (demo.on) { demo.playing = !demo.playing; if (!demo.playing) { gun.queue = []; setLaser(false); } } paintRobotActions(); },
  onActivity: async (activity) => {
    if (activity === 'live') { takeControl(); return; }
    if (activity === 'demo') setDemo(true);
    else {
      stopDemoAutomation();
      const key = [...runSel.options].find(o => o.value.endsWith(`/${activity}`))?.value;
      if (key) { runSel.value = key; await startReplay(key); }
    }
    paintRobotActions();
  }, onFire: queueShots, onReload: reloadRobot, onLayout: updateInsets });
$('#robot-actions').inert = true;
paintRobotActions();
window.__sim = { state, stage, eyes, gun, demo, sfx, balls, get talk() { return talk; }, get props() { return propMeshes; }, setHeight: (v) => { state.height = v; sh.set(v); }, bench: () => bench };
sel.onchange = () => loadDesign(sel.value);
runSel.onchange = () => { stopDemoAutomation(); if (!runSel.value) takeControl(); else startReplay(runSel.value); };
await loadDesign(sel.value);
// Gyropup's voice: speech bubbles over its head, spoken lines, a talk dock (character/talk.js)
try {
  talk = (await import('./character/talk.js')).mountTalk({ stage, eyes, audio: { enabled: sfx.enabled, volume: sfx.volume }, getHead: () => state.robot?.turret?.group ?? state.robot?.base });
  const dockEl = document.querySelector('.gp-dock');
  if (dockEl) {
    new MutationObserver(updateInsets).observe(dockEl, { attributes: true, attributeFilter: ['class'] });
    // Updating the canvas during ResizeObserver delivery can trigger another
    // layout delivery in WebKit. Coalesce measurements into the next frame.
    let dockLayoutFrame = 0;
    const dockResize = new ResizeObserver(() => {
      if (!dockLayoutFrame) dockLayoutFrame = requestAnimationFrame(() => { dockLayoutFrame = 0; updateInsets(); });
    });
    dockResize.observe(dockEl);
    dockResize.observe(dockEl.querySelector('.gp-dock-body'));
    document.querySelector('link[data-gyropup-talk]')?.addEventListener('load', updateInsets, { once: true });
  }
  // on a phone the dock starts folded to its Talk tab in the corner (unless the visitor chose otherwise before)
  let chose = null;
  try { chose = localStorage.getItem('gyropup.dockCollapsed'); } catch { /* storage blocked */ }
  if (phone.matches && chose === null) talk?.dock?.collapse(true);
} catch (err) { console.warn('talk unavailable', err); }
// the orbit hint: worded for touch on a touch screen; it fades after a few seconds or the first drag, pinch or scroll
{
  const hint = $('.hud-hint');
  if (hint) {
    if (matchMedia('(pointer: coarse)').matches) hint.textContent = 'DRAG · ORBIT // PINCH · ZOOM // TWO FINGERS · PAN';
    const fade = () => { hint.classList.add('faded'); stage.controls.removeEventListener('start', fade); };
    setTimeout(fade, 6000);
    stage.renderer.domElement.addEventListener('pointerdown', fade, { once: true });
    stage.controls.addEventListener('start', fade); // Includes the smoothed wheel gesture.
  }
}
updateInsets();
// no render until the opening shot is framed (the replay below sets it): the camera never jumps at the start
const canvas = stage.renderer.domElement;
canvas.style.opacity = '0';
if (q.get('panel') === '0') panelFold.set(true);
if (q.has('sound')) { sfx.setEnabled(q.get('sound') !== '0'); paintSound(); }
setTimeout(() => { if (!state.replay && !state.bench) react(Math.random() < 0.5 ? 'hello' : 'banter'); }, 1200);   // replays greet with their own line
// ?cam=side|front|iso and ?height=0..1 for screenshots and docs; ?run=<scenario> starts a replay
const camAt = { side: [1, 0.35, 0], front: [0, 0.35, 1], iso: [0.6, 0.45, 1], back: [0, 0.35, -1] }[q.get('cam')];
if (camAt) { const dist = state.robot.info.heightM * 2.4; stage.camera.position.set(...camAt.map((v) => v * dist)); stage.controls.target.set(0, state.robot.info.heightM * 0.45, 0); }
if (q.has('height')) window.__sim?.setHeight?.(+q.get('height'));
if (q.get('alive') === '0') { state.alive = false; aliveToggle.checked = false; $('#alive').classList.remove('on'); }
if (q.get('demo') === '1') { demo.on = true; paintDemo(); }
if (q.has('light')) { if (!state.bench) stage.setSceneLight(+q.get('light'), true); setDaylight(+q.get('light')); }
if (q.get('fov') === '1') { gun.showFov = true; fovToggle.checked = true; if (state.robot) state.robot.fov.visible = true; }
// Only explicit run links show historical physics. Fresh visits demonstrate the current robot live.
const runName = q.get('run') ?? 'none';
const runKey = `${sel.value.split('/').pop().replace(/\.json$/, '')}/${runName}`;
if (runName !== 'none' && sel.value !== '@designer' && !state.bench && [...runSel.options].some((o) => o.value === runKey)) {
  const key = runKey;
  runSel.value = key;
  await startReplay(key);
  if (q.has('t') && state.replay) { state.replay.t = +q.get('t'); state.replay.playing = q.get('play') === '1'; }
}
if (q.has('fire')) queueShots(+q.get('fire') || 1);
paintRobotActions();
stage.start();                                         // the camera is where it will stay: show the stage
requestAnimationFrame(() => {
  canvas.style.transition = 'opacity .35s ease'; canvas.style.opacity = '1';
  const startup=$('#sim-startup');if(startup){startup.hidden=true;startup.setAttribute('aria-busy','false');}
  sel.disabled=runSel.disabled=demoBtn.disabled=false;
  $('#panel').inert=false;$('#robot-actions').inert=false;
});
document.body.dataset.ready = '1';

