// The foam-ball turret on the Orin AGX compute box, on the 3D game page: the turret's CAD on its adapter on the J501
// box, as cad/build_turret_box.py exports it (exports/sim/turret_box/: every part an STL in its moving group's frame,
// manifest.json with the pivots, the ball path, the callouts, the journey and the numbers). You aim it by hand and it
// fires only while ARM is held: ARM is the hold-to-run safety line (the bench pendant; the radio stop on the robot).
// The mechanism, part by part: X-ray, a section through the ball path, an exploded view, callouts, and one ball's
// journey from the hopper to a target in slow motion. Its sounds are sfx.turret's (sfx.js): the flywheels' hum follows
// their speed and brakes on release, and the journey plays each stage's sound in its slow motion.
//
//   const bench = await createTurretBench({ stage, sfx, panel, root: '../', onLayout });
//   bench.enter();   // shows its scene, panel sections and action bar (built once, by createTurretBench)
//   stage.onFrame((t, dt) => { if (bench.active) bench.step(t, dt); });
//   bench.exit();
//
// Frames: the box frame (mm: x forward at pan 0, y left, z up, origin on the desk under the pan axis); this page is
// (y, z, x) in metres. The box stands on a 0.3 m crate, so the barrel is at about the robot's turret height.
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { BALL, ballMesh } from './turret3d.js';
import { section, slider, chips, readouts, toggle } from './kit/panel.js';
import { createReloadEffect, RELOAD_OPEN_ANGLE } from './turret_reload.js';

const M = 0.001;
const D2R = Math.PI / 180;
const TO_PAGE = new THREE.Matrix4().set(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1).multiply(new THREE.Matrix4().makeScale(M, M, M));
const P = (p) => new THREE.Vector3(p[1] * M, p[2] * M, p[0] * M);           // box mm -> page m
const CRATE = { w: 0.48, d: 0.62, h: 0.30 };                                   // under the J501 box
const K_DRAG = 0.5 * 1.2 * BALL.cd * Math.PI * (BALL.d / 2) ** 2 / BALL.mass;
const SPREAD_DEG = 0.5, SPEED_SPREAD = 0.015;        // shot-to-shot spread: assumed until the chronograph and the paper say
const SPIN_UP_S = 0.3, DIAL_DEG_S = 190;             // the firmware's 300 ms ramp; the feed servo's 45° step in ~235 ms (3 balls/s at most)
const BRAKE_DELAY_S = 0.008, BRAKE_TAU_S = 0.0127;   // D9: the short closes ~8 ms after ARM drops (5-14); 5 % at ~48 ms (turret-physics.md section 5)
const BALL_R = BALL.d / 2;
// the parts that are see-through in the X-ray view (the rest, the mechanism, stays solid)
const SHELL = new Set(['pan_base', 'pan_clamp', 'bumper_ring', 'cartridge_body', 'cradle', 'tilt_yoke', 'hopper', 'hopper_lid', 'hopper_flap',
  'barrel', 'laser_mount', 'pan_ring', 'box_deck', 'intake_shroud', 'pod_cover', 'base', 'cover', 'front_no_gmsl', 'rear_io', 'side_hatch',
  'dt_plug', 'dt_receptacle']);
const INNER = new Set(['dial', 'feed_motor', 'flywheel_tyre', 'pan_bearing', 'pan_ring', 'cartridge_body']);   // callouts shown only when you can see in
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

export async function createTurretBench({ stage, sfx, panel, root = '../', onLayout = () => {} }) {
  const base = `${root}exports/sim/turret_box/`;
  const res = await fetch(`${base}manifest.json`, { cache: 'no-store' });
  if (!res.ok) throw new Error('no turret_box export: run .venv/bin/python cad/build_turret_box.py');
  const man = await res.json();
  const vector = (v,n=3) => Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
  if (!Array.isArray(man.parts) || !man.parts.length || !man.pivots ||
      !['pan','tilt','pinion','dial','wheel_l','wheel_r','flap'].every(k=>vector(man.pivots[k])) ||
      !(man.mechanics?.ball?.speed_mps>0) ||
      !man.parts.every(p=>p&&typeof p.file==='string'&&typeof p.group==='string')) throw new Error('Invalid turret manifest');
  const mech = man.mechanics;
  const launchSpeed = mech.ball.speed_mps;
  const coarse = matchMedia('(pointer: coarse)').matches;

  // ------------------------------------------------------------------------------------------------ the scene
  const scene = new THREE.Group();                    // everything of this mode, in the page frame
  scene.visible = false;
  stage.root.add(scene);
  const world = new THREE.Group();                    // the box frame, on top of the crate
  world.position.y = CRATE.h;
  scene.add(world);
  const groups = { j501: new THREE.Group(), adapter: new THREE.Group(), base: new THREE.Group() };
  const panPivot = new THREE.Group(), tiltPivot = new THREE.Group(), pinionPivot = new THREE.Group();
  const dialPivot = new THREE.Group(), wheelL = new THREE.Group(), wheelR = new THREE.Group(), flapPivot = new THREE.Group();
  panPivot.position.copy(P(man.pivots.pan));
  tiltPivot.position.copy(P(man.pivots.tilt));
  pinionPivot.position.copy(P(man.pivots.pinion));
  dialPivot.position.copy(P(man.pivots.dial));
  wheelL.position.copy(P(man.pivots.wheel_l));
  wheelR.position.copy(P(man.pivots.wheel_r));
  flapPivot.position.copy(P(man.pivots.flap));
  panPivot.add(tiltPivot);
  tiltPivot.add(dialPivot, wheelL, wheelR, flapPivot);
  world.add(groups.j501, groups.adapter, groups.base, pinionPivot, panPivot);
  Object.assign(groups, { pinion: pinionPivot, pan: panPivot, tilt: tiltPivot, dial: dialPivot, wheel_l: wheelL, wheel_r: wheelR, flap: flapPivot });

  // All angles are joint-local radians; this same path drives live animation and
  // the rendered-vertex regression (including independent and compound poses).
  function poseMechanism(a) {
    panPivot.rotation.y = a.pan;
    tiltPivot.rotation.x = -a.tilt;
    pinionPivot.rotation.y = a.pinion;
    dialPivot.rotation.y = a.dial;
    wheelL.rotation.y = a.wheel_l;
    wheelR.rotation.y = -a.wheel_r;
    flapPivot.rotation.x = -a.flap;
  }

  // the crate the box stands on
  {
    const wood = new THREE.MeshStandardMaterial({ color: 0x8a6a45, roughness: 0.9 });
    const crate = new THREE.Mesh(new THREE.BoxGeometry(CRATE.w, CRATE.h, CRATE.d), wood);
    crate.position.y = CRATE.h / 2;
    crate.castShadow = crate.receiveShadow = true;
    const slats = new THREE.Mesh(new THREE.BoxGeometry(CRATE.w + 0.004, 0.018, CRATE.d + 0.004), new THREE.MeshStandardMaterial({ color: 0x6d5236, roughness: 0.95 }));
    for (const y of [0.06, 0.15, 0.24]) { const s = slats.clone(); s.position.y = y; scene.add(s); }
    scene.add(crate);
  }

  stage.renderer.localClippingEnabled = true;
  const loader = new STLLoader();
  const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
  const parts = [];                                   // { e (manifest entry), mesh, cap, mat, group, offset }
  const capColor = new THREE.Color();
  const loaded = await Promise.allSettled(man.parts.map(async (e) => {
    if (!groups[e.group]) throw new Error(`Unknown turret part group: ${e.group}`);
    const meshURL = base + e.file + (e.sha256 ? `?v=${e.sha256}` : '');
    const geo = await loader.loadAsync(meshURL);
    const positions=geo.getAttribute('position');
    if (!positions || positions.count<3 || !positions.array.every(Number.isFinite)) { geo.dispose(); throw new Error(`Invalid turret mesh: ${e.file}`); }
    geo.applyMatrix4(TO_PAGE);
    const offset = new THREE.Vector3();
    if (e.group === 'pinion') { offset.copy(P(man.pivots.pinion)).negate(); geo.translate(offset.x, offset.y, offset.z); }
    geo.computeVertexNormals();
    const j501 = e.group === 'j501';
    const op = e.opacity ?? 1;
    const mat = new THREE.MeshPhysicalMaterial({ color: e.color, roughness: j501 ? 0.7 : 0.45, metalness: /#(c9|bf|75|cc)/i.test(e.color) ? 0.55 : 0.05,
      clearcoat: j501 ? 0 : 0.15, transparent: op < 1, opacity: op, depthWrite: op >= 1, side: j501 ? THREE.DoubleSide : THREE.FrontSide });
    mat.userData.base = { opacity: op, transparent: op < 1, depthWrite: op >= 1 };
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = op >= 1;
    mesh.receiveShadow = true;
    mesh.name = e.name;
    capColor.set(e.color).multiplyScalar(0.55);
    const cap = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: capColor.clone(), side: THREE.BackSide, clippingPlanes: [clipPlane] }));
    cap.visible = false;
    cap.raycast = () => {};
    mesh.add(cap);
    mesh.userData.part = e;
    groups[e.group].add(mesh);
    parts.push({ e, mesh, cap, mat, group: groups[e.group], offset, shell: SHELL.has(e.part), explode: P(e.explode ?? [0, 0, 0]) });
  }));
  const failed = loaded.filter(result=>result.status==='rejected');
  if (failed.length) {
    // Wait for every part request before disposing, so late completions cannot
    // leave orphan meshes or turn a failed attempt into a partial ready scene.
    const geometry=new Set(),materials=new Set();
    scene.traverse(object=>{if(object.geometry)geometry.add(object.geometry);if(object.material)for(const m of [].concat(object.material))materials.add(m);});
    geometry.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());scene.removeFromParent();
    throw new Error(`${failed.length} required turret part(s) could not load: ${failed[0].reason.message}`);
  }
  const pickable = () => parts.filter((p) => p.mesh.visible).map((p) => p.mesh);

  // antennas on the J501's RP-SMA bulkheads (shown when "antennas fitted" is on): they limit the barrel's depression
  const antennas = new THREE.Group();
  antennas.visible = false;
  for (const a of man.antennas) {
    const b = P(a.base), t = P(a.top);
    const whip = new THREE.Mesh(new THREE.CylinderGeometry(a.d / 2 * M, a.d / 2 * M * 0.8, b.distanceTo(t), 16), new THREE.MeshStandardMaterial({ color: 0x15171b, roughness: 0.6 }));
    whip.position.copy(b).lerp(t, 0.5);
    const hinge = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.016, 12), new THREE.MeshStandardMaterial({ color: 0x9a9da3, metalness: 0.6, roughness: 0.3 }));
    hinge.rotation.x = Math.PI / 2;
    hinge.rotation.z = Math.PI / 2;
    hinge.position.copy(b).add(new THREE.Vector3(-Math.sign(b.x) * 0.007, 0, 0));
    antennas.add(whip, hinge);
  }
  world.add(antennas);

  // the balls inside: a full hopper (the pile in the tilt frame, one in each dial pocket), and the ball path
  const BALLS = 30;
  // the balls inside get their own materials, so the section can cut them (and a cap shows their cut face); they ride
  // on the dial and the hopper, so they come apart with them in the exploded view
  const foam = new THREE.MeshStandardMaterial({ color: BALL.color, roughness: 0.9 }), seam = new THREE.MeshStandardMaterial({ color: BALL.seam, roughness: 0.8 });
  const foamCap = new THREE.MeshBasicMaterial({ color: 0xc9a414, side: THREE.BackSide });
  const pileFoam = foam.clone(), pileSeam = seam.clone(), pileCap = foamCap.clone();     // the pile fades in the inside views
  const ballMats = [foam, seam, foamCap, pileFoam, pileSeam, pileCap];
  function innerBall(pile = false) {
    const { g } = ballMesh();
    g.traverse((o) => { if (o.isMesh) o.material = o.geometry.type === 'TorusGeometry' ? (pile ? pileSeam : seam) : (pile ? pileFoam : foam); });
    const cap = new THREE.Mesh(g.children[0].geometry, pile ? pileCap : foamCap);
    cap.raycast = () => {};
    g.add(cap);
    return g;
  }
  const holder = (name, fallback) => parts.find((p) => p.e.part === name && !p.e.name.endsWith('_m'))?.mesh ?? fallback;
  const pocketBalls = man.pockets.map((p) => { const g = innerBall(); g.position.copy(P(p)); holder('dial', dialPivot).add(g); return g; });
  const pileBalls = man.pile.slice(0, BALLS - pocketBalls.length).map((p) => { const g = innerBall(true); g.position.copy(P(p)); holder('hopper', tiltPivot).add(g); return g; });
  const path = man.ball_path.map(P);                  // tilt frame: exit pocket -> chute -> nip -> muzzle
  const cum = [0];
  for (let i = 1; i < path.length; i++) cum.push(cum[i - 1] + path[i].distanceTo(path[i - 1]));
  // path points (cad/build_turret_box.py): 0 the exit pocket, 1-12 the chute's quarter bend, 13-15 the nip (in, middle,
  // out), 16 the barrel socket, 17-18 the chronograph gates, 19 the muzzle
  const IX = { arcEnd: 12, nipIn: 13, nipC: 14, nipOut: 15, gate1: 17, gate2: 18, muzzle: path.length - 1 };
  const iNip0 = IX.nipIn;
  const chuteR = path[0].y - path[IX.arcEnd].y;
  const segS = { chute: [0, cum[IX.arcEnd]], run: [cum[IX.arcEnd], cum[iNip0]], barrel: [cum[iNip0], cum[IX.muzzle]] };
  const pathAt = (s, out = new THREE.Vector3()) => {
    s = Math.max(0, Math.min(cum[cum.length - 1], s));
    let i = 1;
    while (i < cum.length - 1 && cum[i] < s) i++;
    const w = (s - cum[i - 1]) / Math.max(1e-9, cum[i] - cum[i - 1]);
    return out.copy(path[i - 1]).lerp(path[i], w);
  };
  const pathLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([...path, P([man.muzzle[0] + 60, 0, man.muzzle[2]])]),
    new THREE.LineDashedMaterial({ color: 0xffd21a, dashSize: 0.004, gapSize: 0.003, transparent: true, opacity: 0.9, depthTest: false }));
  pathLine.computeLineDistances();
  pathLine.renderOrder = 10;
  pathLine.visible = false;
  tiltPivot.add(pathLine);
  const muzzle = new THREE.Object3D();
  muzzle.position.copy(P(man.muzzle));
  const laserO = new THREE.Object3D();
  laserO.position.copy(P(man.laser));
  tiltPivot.add(muzzle, laserO);
  const flash = new THREE.Mesh(new THREE.SphereGeometry(0.014, 12, 8), new THREE.MeshBasicMaterial({ color: 0xfff1a8, transparent: true, opacity: 0, depthWrite: false }));
  flash.position.copy(muzzle.position).add(new THREE.Vector3(0, 0, 0.008));
  tiltPivot.add(flash);
  // the chronograph's two IR gates in the barrel: they blink as a ball passes
  const gateMat = new THREE.MeshBasicMaterial({ color: 0xff3355, transparent: true, opacity: 0.0 });
  const gates = [IX.gate1, IX.gate2].map((i) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.0016, 0.0016, 0.036, 8), gateMat.clone()); m.rotation.z = Math.PI / 2; m.position.copy(path[i] ?? path[path.length - 2]); tiltPivot.add(m); return m; });

  // the laser: a thin glowing rod from the laser to the first thing it meets, and its dot
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.0012, 0.0012, 1, 6, 1, true),
    new THREE.MeshBasicMaterial({ color: 0xff6048, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped:false }));
  beam.frustumCulled = false;
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.009, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff9266, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped:false }));
  dot.add(new THREE.PointLight(0x39ff6a, 0.4, 0.6));
  const laser = new THREE.Group();
  laser.add(beam, dot);
  laser.visible = false;
  scene.add(laser);
  // where the ball will land (the trajectory with drag and gravity, from the barrel as it points now)
  const impact = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.045, 32), new THREE.MeshBasicMaterial({ color: 0xb9ff77, transparent: true, opacity: 0.95, side: THREE.DoubleSide, depthWrite: false, toneMapped:false }));
  impact.renderOrder = 5;
  // Cylinders give the ballistic guide a visible width on every WebGL backend;
  // native THREE.Line is usually limited to one pixel even with linewidth set.
  const arcLine = new THREE.InstancedMesh(new THREE.CylinderGeometry(1,1,1,6),
    new THREE.MeshBasicMaterial({color:0xb9ff77,depthWrite:false,toneMapped:false}),300);
  const arcHalo=new THREE.InstancedMesh(arcLine.geometry,
    new THREE.MeshBasicMaterial({color:0x65ff77,transparent:true,opacity:.18,blending:THREE.AdditiveBlending,depthWrite:false,toneMapped:false}),300);
  arcHalo.count=0;arcHalo.frustumCulled=false;arcHalo.renderOrder=3;arcLine.renderOrder=4;
  arcLine.count=0;
  arcLine.frustumCulled = false;
  scene.add(impact, arcHalo, arcLine);

  // airflow under the deck: the J501's intake (blue) from the front grille into the fan, its exhaust (orange) out at
  // the sides; arrows move along these lines (box frame mm)
  const fan = man.fan, zd = (fan.duct_z[0] + fan.duct_z[1]) / 2, roof = man.roof_z;
  const flows = [];
  for (const dy of [-40, 0, 40]) flows.push({ c: 0x3fb7ff, pts: [[fan.grille_x + 70, fan.xy[1] + dy * 1.4, zd + 10], [fan.grille_x, fan.xy[1] + dy, zd], [fan.xy[0] + 20, fan.xy[1] + dy * 0.4, zd], [fan.xy[0], fan.xy[1] + dy * 0.15, roof + 2], [fan.xy[0], fan.xy[1] + dy * 0.15, roof - 22]] });
  for (const sy of [1, -1]) for (const x of [-60, 10, 60]) flows.push({ c: 0xff8a3d, pts: [[x, sy * 62, roof - 10], [x, sy * 62, roof + 14], [x + 5, sy * 112, roof + 18], [x + 8, sy * 128, roof + 70]] });
  const flowGroup = new THREE.Group();
  flowGroup.visible = false;
  world.add(flowGroup);
  const arrowGeo = new THREE.ConeGeometry(0.0045, 0.013, 10);
  arrowGeo.rotateX(Math.PI / 2);
  for (const f of flows) {
    const curve = new THREE.CatmullRomCurve3(f.pts.map(P));
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)), new THREE.LineBasicMaterial({ color: f.c, transparent: true, opacity: 0.45, depthTest: false }));
    line.renderOrder = 9;
    flowGroup.add(line);
    f.curve = curve;
    f.heads = [0, 1, 2].map((k) => {
      const m = new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({ color: f.c, depthTest: false }));
      m.renderOrder = 10;
      m.userData.u = k / 3;
      flowGroup.add(m);
      return m;
    });
  }

  // ------------------------------------------------------------------------------------------------ the range
  const range = new THREE.Group();
  scene.add(range);
  const boxPt = (x, y, h = 0) => new THREE.Vector3(y, h, x);        // box-frame metres on the ground -> page
  const obstacles = [];                                            // { kind, mesh/obj, half, onHit }
  const plates = [];
  const plateGeo = new THREE.BoxGeometry(0.24, 0.24, 0.012);
  function makePlate(x, y, name) {
    const stand = new THREE.Group();
    const at = boxPt(x, y);
    stand.position.copy(at);
    stand.rotation.y = Math.atan2(-at.x, -at.z);                  // its face towards the turret
    const hingeY = 0.30 - 0.12;
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.03, hingeY, 0.03), new THREE.MeshStandardMaterial({ color: 0x15161a }));
    post.position.set(0, hingeY / 2, -0.03);
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.012, 0.16), new THREE.MeshStandardMaterial({ color: 0xf2cc0d }));
    foot.position.set(0, 0.006, -0.03);
    const hinge = new THREE.Group();
    hinge.position.y = hingeY;
    const face = new THREE.Mesh(plateGeo, new THREE.MeshStandardMaterial({ color: 0xff4d00, roughness: 0.6 }));
    face.position.set(0, 0.12, 0.004);
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.06, 0.085, 40), new THREE.MeshBasicMaterial({ color: 0x0a0a0c }));
    ring.position.set(0, 0.12, 0.0105);
    const bull = new THREE.Mesh(new THREE.CircleGeometry(0.035, 32), new THREE.MeshBasicMaterial({ color: 0xfffbe6 }));
    bull.position.set(0, 0.12, 0.011);
    hinge.add(face, ring, bull);
    stand.add(post, foot, hinge);
    [post, foot, face].forEach((m) => { m.castShadow = m.receiveShadow = true; });
    range.add(stand);
    const p = { name, stand, hinge, face, th: -4 * D2R, w: 0, down: false, mass: 0.02 };
    p.I = p.mass * (0.24 * 0.24 / 3 + 0.012 * 0.012 / 3);
    plates.push(p);
    obstacles.push({ kind: 'plate', obj: face, half: new THREE.Vector3(0.12, 0.12, 0.006), plate: p });
    obstacles.push({ kind: 'box', obj: post, half: new THREE.Vector3(0.015, hingeY / 2, 0.015) });
  }
  [[2.2, 0.8, 'A'], [2.8, -0.5, 'B'], [3.6, 0.3, 'C'], [4.4, -1.2, 'D']].forEach(([x, y, n]) => makePlate(x, y, n));
  // a can pyramid on a small crate
  const cans = [];
  {
    const at = boxPt(3.0, 1.5);
    const cr = new THREE.Mesh(new THREE.BoxGeometry(0.40, 0.30, 0.30), new THREE.MeshStandardMaterial({ color: 0x8a6a45, roughness: 0.9 }));
    cr.position.copy(at).setY(0.15);
    cr.rotation.y = Math.atan2(-at.x, -at.z);
    cr.castShadow = cr.receiveShadow = true;
    range.add(cr);
    obstacles.push({ kind: 'box', obj: cr, half: new THREE.Vector3(0.20, 0.15, 0.15) });
    const canGeo = new THREE.CylinderGeometry(0.033, 0.033, 0.122, 24);
    const colors = [0xd7263d, 0x1b998b, 0xf46036, 0x2e86ab, 0xc5d86d, 0xe2c044];
    const rows = [[-1, 0, 1], [-0.5, 0.5], [0]];
    let k = 0;
    const right = new THREE.Vector3(Math.cos(cr.rotation.y), 0, -Math.sin(cr.rotation.y));
    rows.forEach((row, level) => row.forEach((u) => {
      const m = new THREE.Mesh(canGeo, new THREE.MeshStandardMaterial({ color: colors[k % colors.length], metalness: 0.6, roughness: 0.35 }));
      const pos = cr.position.clone().addScaledVector(right, u * 0.07).setY(0.30 + 0.061 + level * 0.1225);
      m.position.copy(pos);
      m.castShadow = m.receiveShadow = true;
      range.add(m);
      cans.push({ m, home: pos.clone(), level, u, dyn: false, v: new THREE.Vector3(), w: new THREE.Vector3(), rest: false, t: 0 });
      k++;
    }));
    for (const c of cans) c.on = cans.filter((o) => o.level === c.level - 1 && Math.abs(o.u - c.u) < 0.6);      // what it rests on
  }
  // a paper target on a board: hits leave marks, so the group shows the turret's spread
  const paper = (() => {
    const at = boxPt(3.2, -1.6);
    const g = new THREE.Group();
    g.position.copy(at);
    g.rotation.y = Math.atan2(-at.x, -at.z);
    const cv = document.createElement('canvas');
    cv.width = cv.height = 512;
    const ctx = cv.getContext('2d');
    const draw = () => {
      ctx.fillStyle = '#f4f1e6';
      ctx.fillRect(0, 0, 512, 512);
      for (const [r, c] of [[230, '#f4f1e6'], [200, '#1c1c1c'], [150, '#f4f1e6'], [100, '#1c1c1c'], [50, '#e63b2e']]) {
        ctx.beginPath(); ctx.arc(256, 256, r, 0, 2 * Math.PI); ctx.fillStyle = c; ctx.fill();
      }
      ctx.strokeStyle = '#888'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(256, 20); ctx.lineTo(256, 492); ctx.moveTo(20, 256); ctx.lineTo(492, 256); ctx.stroke();
    };
    draw();
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    const board = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.012), [0, 0, 0, 0, 0, 0].map((_, i) => (i === 4 ? new THREE.MeshStandardMaterial({ map: tex, roughness: 0.9 })
      : new THREE.MeshStandardMaterial({ color: 0x9c7b52, roughness: 0.9 }))));
    board.position.y = 0.45;
    const legs = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.22, 0.02), new THREE.MeshStandardMaterial({ color: 0x5b4632 }));
    legs.position.set(0, 0.11, -0.02);
    board.castShadow = board.receiveShadow = legs.castShadow = true;
    g.add(board, legs);
    range.add(g);
    const hits = [];
    return { g, board, tex, ctx, draw, hits, mark(local) {
      const u = 256 + (local.x / 0.25) * 256, v = 256 - (local.y / 0.25) * 256;
      hits.push([local.x, local.y]);
      ctx.fillStyle = '#2b2b2b'; ctx.beginPath(); ctx.arc(u, v, 9, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = '#ffd21a'; ctx.lineWidth = 2; ctx.stroke();
      tex.needsUpdate = true;
    }, clear() { hits.length = 0; draw(); tex.needsUpdate = true; } };
  })();
  obstacles.push({ kind: 'paper', obj: paper.board, half: new THREE.Vector3(0.25, 0.25, 0.006) });
  obstacles.push({ kind: 'box', obj: (() => { const m = new THREE.Object3D(); m.position.set(0, CRATE.h / 2, 0); scene.add(m); return m; })(), half: new THREE.Vector3(CRATE.w / 2, CRATE.h / 2, CRATE.d / 2) });
  {                                                                // the J501 box and the deck, as boxes
    const b = man.box, d = man.deck;
    const add = (x, y, z) => {
      const o = new THREE.Object3D();
      o.position.copy(P([(x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2]));
      world.add(o);
      obstacles.push({ kind: 'box', obj: o, half: new THREE.Vector3((y[1] - y[0]) / 2 * M, (z[1] - z[0]) / 2 * M, (x[1] - x[0]) / 2 * M) });
    };
    add(b.x, b.y, b.z);
    add(d.x, d.y, d.z);
  }
  const hitTargets = () => [...plates.map((p) => p.face), ...cans.map((c) => c.m), paper.board, ...obstacles.filter((o) => o.kind === 'box').map((o) => o.obj).filter((o) => o.isMesh)];

  // ------------------------------------------------------------------------------------------------ state
  const lim = man.limits;
  const S = {
    active: false, pan: 0, tilt: -3 * D2R, panCmd: 0, tiltCmd: -3 * D2R, keys: new Set(),
    arm: new Set(), trigger: false, queue: 0, nextAt: 0, rate: 3, rpm: 0, laserOn: false, wasArmed: false,
    phi: man.dial_park_deg * D2R, phiCmd: man.dial_park_deg * D2R, pockets: man.pockets.map(() => true), pile: pileBalls.length,
    transit: [], flying: [], shots: 0, hits: 0, lastSpeed: null, view: 'solid', explode: 0, explodeCmd: 0,
    labels: true, airflow: false, antennas: false, marker: true, laserReference:false, timeScale: 1, journey: null, selected: null, wheelAng: 0,
    flapAngle: 0, reloading: null, offFor: 0,
  };
  const hopperCount = () => S.pockets.filter(Boolean).length + S.pile;
  // CAD FILL_PORT: 19 mm forward and 6 mm below the flap's hinge, in the tilt frame.
  const refill = createReloadEffect(tiltPivot,P(man.pivots.flap).add(new THREE.Vector3(0,-.006,.019)));

  // ------------------------------------------------------------------------------------------------ the HUD
  const hud = document.getElementById('hud');
  const overlay = document.getElementById('stage-overlay');
  const bar = document.createElement('div');
  bar.id = 'tb-actions';
  bar.hidden = true;
  bar.innerHTML = `
    <button type="button" class="tb-arm" aria-label="Arm: hold to run (the safety line)"><span class="tb-led"></span><b>ARM</b><small>${coarse ? 'hold' : 'hold SPACE'}</small></button>
    <div class="tb-views" role="group" aria-label="View">
      <button type="button" data-view="solid" class="on" title="Solid (the look)">SOLID</button><button type="button" data-view="xray" title="See through the shells (X)">X-RAY</button><button type="button" data-view="section" title="Cut through the ball path (C)">CUT</button><button type="button" data-view="explode" title="Pull it apart: how it goes together (E)">APART</button>
    </div>
    <button type="button" class="tb-journey" title="One ball's journey, hopper to target, in slow motion (J)">JOURNEY</button>
    <button type="button" class="tb-reload" aria-label="Reload hopper"><b>RELOAD</b><small>30 / 30 · R</small></button>
    <button type="button" class="tb-fire" aria-label="Fire (hold for automatic)"><b>FIRE</b><small>${coarse ? 'tap / hold' : 'F / ENTER'}</small></button>`;
  overlay.appendChild(bar);
  new ResizeObserver(() => { if (!bar.hidden) hud.style.setProperty('--tb-actions-h', `${Math.ceil(bar.getBoundingClientRect().height)}px`); }).observe(bar);
  const armBtn = bar.querySelector('.tb-arm'), fireBtn = bar.querySelector('.tb-fire');
  const reloadBtn=bar.querySelector('.tb-reload');
  reloadBtn.addEventListener('click',reload);
  const holdBtn = (btn, down, up) => {
    btn.addEventListener('pointerdown', (ev) => { ev.preventDefault(); btn.setPointerCapture?.(ev.pointerId); down(); });
    for (const t of ['pointerup', 'pointercancel', 'lostpointercapture']) btn.addEventListener(t, () => up());
    btn.addEventListener('keydown', ev => {
      if (ev.key !== ' ' && ev.key !== 'Enter') return;
      ev.preventDefault(); if (!ev.repeat && !btn.disabled) down();
    });
    btn.addEventListener('keyup', ev => {
      if (ev.key !== ' ' && ev.key !== 'Enter') return;
      ev.preventDefault(); up();
    });
    btn.addEventListener('blur', up);
    btn.addEventListener('contextmenu', (ev) => ev.preventDefault());
  };
  holdBtn(armBtn, () => S.arm.add('button'), () => S.arm.delete('button'));
  holdBtn(fireBtn, () => pullTrigger(true), () => pullTrigger(false));
  bar.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  bar.querySelector('.tb-journey').addEventListener('click', () => (S.journey ? stopJourney() : startJourney()));

  const toast = document.createElement('div');
  toast.id = 'tb-toast';
  overlay.appendChild(toast);
  let toastT = 0;
  function say(text, ms = 2200) { toast.textContent = text; toast.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => toast.classList.remove('show'), ms); }

  const card = document.createElement('div');
  card.id = 'tb-card';
  card.className = 'hud-card';
  card.hidden = true;
  overlay.appendChild(card);
  const jcard = document.createElement('div');
  jcard.id = 'tb-journey-card';
  jcard.className = 'hud-card';
  jcard.hidden = true;
  overlay.appendChild(jcard);
  const keyHint = document.createElement('div');
  keyHint.className = 'hud-hint tb-keys';
  keyHint.textContent = coarse ? 'TAP THE RANGE · AIM THERE // HOLD ARM + TAP FIRE // TAP A PART · WHAT IT DOES // DRAG · ORBIT'
    : 'SPACE (hold) · ARM // F · FIRE // ARROWS · AIM // CLICK THE RANGE · AIM THERE // CLICK A PART · WHAT IT DOES // DRAG · ORBIT';
  keyHint.hidden = true;
  overlay.appendChild(keyHint);

  // callouts: a layer over the canvas (under the HUD) with numbered labels and leader lines
  const callLayer = document.createElement('div');
  callLayer.id = 'tb-callouts';
  callLayer.hidden = true;
  callLayer.innerHTML = '<svg></svg>';
  document.body.appendChild(callLayer);
  const svg = callLayer.querySelector('svg');
  const callouts = parts.filter((p) => p.e.callout && p.e.anchor).sort((a, b) => a.e.title.localeCompare(b.e.title)).map((p, i) => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'tb-label';
    el.innerHTML = `<i>${i + 1}</i><span>${esc(p.e.title)}</span>`;
    el.addEventListener('click', () => select(p));
    callLayer.appendChild(el);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    svg.appendChild(line);
    return { p, el, line, n: i + 1, local: P(p.e.anchor).add(p.offset) };
  });

  // ---- the panel (its own sections, shown in this mode only)
  const secs = [];
  const sec = (title, opts) => { const body = section(panel, title, opts); secs.push(body.parentElement); body.parentElement.hidden = true; return body; };
  const fireSec = sec('Fire control', { note: 'ARM = the hold-to-run safety line' });
  const fireInfo = readouts(fireSec);
  slider(fireSec, { label: 'Rate of fire (FIRE held)', min: 1, max: 3, step: 1, value: S.rate, fmt: (v) => `${v} balls/s`, onInput: (v) => { S.rate = v; } });
  const fr = document.createElement('div');
  fr.className = 'hud-chips';
  for (const [label, fn] of [['RELOAD 30', reload], ['RESET TARGETS', resetTargets], ['CLEAR BALLS', clearBalls]]) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'hud-btn'; b.textContent = label; b.onclick = fn; fr.appendChild(b);
  }
  fireSec.appendChild(fr);
  const aimSec = sec('Aim', { note: coarse ? 'or tap the range' : 'or click the range, or the arrow keys' });
  const panSl = slider(aimSec, { label: 'Pan', min: lim.pan_deg[0], max: lim.pan_deg[1], step: 1, value: 0, unit: '°', onInput: (v) => { S.panCmd = v * D2R; } });
  const tiltSl = slider(aimSec, { label: 'Tilt (0 = level; it never points up)', min: lim.tilt_deg[0], max: 0, step: 0.5, value: -3, unit: '°', onInput: (v) => { S.tiltCmd = v * D2R; } });
  toggle(aimSec, 'Show curved shot guide', S.marker, (on) => { S.marker = on; });
  toggle(aimSec, 'Show straight laser reference', S.laserReference, (on) => { S.laserReference = on; });
  toggle(aimSec, 'Antennas fitted on the J501 (upright)', S.antennas, (on) => { S.antennas = on; antennas.visible = on; if (on) say(`Upright antennas limit the depression to ${Math.min(...man.checks.clearance.antenna_tilt_max_deg.map((r) => r[1]))}° over the box corners`, 3500); });
  const camRow = document.createElement('div');
  camRow.className = 'hud-chips';
  for (const [label, id] of [['RANGE VIEW', 'range'], ['TURRET', 'turret'], ['FROM THE SIDE', 'side'], ['BEHIND', 'back']]) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'hud-btn'; b.textContent = label; b.onclick = () => frame(id); camRow.appendChild(b);
  }
  aimSec.appendChild(camRow);
  const mechSec = sec('Mechanism', { note: 'how it works, part by part' });
  const viewChips = chips(mechSec, [{ id: 'solid', html: 'SOLID', title: 'Solid' }, { id: 'xray', html: 'X-RAY', title: 'See through the shells' },
    { id: 'section', html: 'CUT', title: 'A section through the ball path' }, { id: 'explode', html: 'APART', title: 'Exploded: how it goes together' }], (id) => setView(id));
  mechSec.querySelectorAll('.hud-chip').forEach((b) => { b.style.width = 'auto'; b.style.minWidth = '56px'; b.style.font = '600 10px var(--font-mono)'; });
  viewChips.mark('solid');
  const explSl = slider(mechSec, { label: 'Exploded', min: 0, max: 1, step: 0.01, value: 0, fmt: (v) => `${Math.round(v * 100)} %`, onInput: (v) => { if (S.journey) stopJourney(); S.explodeCmd = v; } });
  const labelsT = toggle(mechSec, 'Callouts (numbered labels)', S.labels, (on) => { S.labels = on; });
  toggle(mechSec, 'Airflow of the J501 under the deck', S.airflow, (on) => { S.airflow = on; flowGroup.visible = on; if (on && S.view === 'solid') setView('xray'); });
  const jb = document.createElement('button');
  jb.type = 'button';
  jb.className = 'hud-btn primary';
  jb.textContent = 'A BALL\'S JOURNEY (slow motion)';
  jb.onclick = () => (S.journey ? stopJourney() : startJourney());
  mechSec.appendChild(jb);
  const partSel = document.createElement('select');
  partSel.className = 'tb-parts';
  partSel.setAttribute('aria-label', 'Part');
  const seen = new Set();
  const listed = parts.filter((p) => { const k = p.e.part; if (seen.has(k)) return false; seen.add(k); return true; });
  const kinds = [['made', 'Turret: printed parts'], ['bought', 'Bought parts'], ['adapter', 'The adapter on the box'], ['j501', 'The J501 box']];
  partSel.innerHTML = '<option value="">Pick a part…</option>' + kinds.map(([k, label]) => `<optgroup label="${label}">`
    + listed.filter((p) => p.e.kind === k).map((p) => `<option value="${esc(p.e.name)}">${esc(p.e.title)}</option>`).join('') + '</optgroup>').join('');
  partSel.onchange = () => { const p = parts.find((q) => q.e.name === partSel.value); select(p ?? null, !!p); };
  mechSec.appendChild(partSel);
  const liveSec = sec('Live', { note: 'what the turret is doing' });
  const live = readouts(liveSec);
  const numSec = sec('The numbers', { note: 'from the CAD and the catalogue', open: false });
  const nums = readouts(numSec);
  const fl = mech.flywheel, tm = mech.timing, pn = mech.pan, tl = mech.tilt, fd = mech.feed, bl = mech.ball;
  const r3 = mech.flight_level.rows.find((r) => r[0] === 3) ?? mech.flight_level.rows.at(-1);
  nums.set([
    ['ball', `Ø${bl.d_mm} mm, ${bl.mass_g} g, ${bl.speed_mps} m/s (${bl.fps} fps nominal; ${bl.cap_fps} fps cap), ${bl.energy_j} J`],
    ['flywheels', `Ø${fl.d_mm}, ${fmt(fl.rpm)} rpm (${fl.throttle_pct} % of no-load), squeeze ${fl.crush_mm} mm`],
    ['flywheel energy', `${fl.energy_j_each} J each; a shot costs ${fl.speed_drop_per_shot_pct} % speed, back in ${fl.recovery_ms} ms`],
    ['feed', `${fd.pockets} pockets on the feed servo (STS3215, ${fd.ratio}:1); a 45° step in ~${fd.step_ms_est} ms; up to ${fd.max_rate_per_s}/s, paced on gate 1`],
    ['command to muzzle', `${tm.trigger_to_muzzle_ms} ms (dial ${tm.dial_to_exit_ms}, chute ${tm.chute_ms}, barrel ${tm.nip_to_muzzle_ms})`],
    ['pan', `${pn.pinion_teeth}:${pn.ring_teeth} gear = ${pn.ratio}x; ${pn.ring_stall_nm} N·m stall (cap 50 %), ${pn.max_deg_s}°/s`],
    ['pan resolution', `${pn.encoder_counts_per_turret_deg} encoder counts per degree of turret`],
    ['tilt', `direct, ${tl.max_deg_s}°/s; ${tl.group_mass_g} g tilting, holds with ${tl.holding_nm} N·m (${tl.margin}x margin)`],
    ['level shot at 3 m', `drops ${r3[2]} mm, ${r3[3]} m/s, ${r3[1]} s`],
    ['assumed', `exit = ${fl.efficiency_assumed} x tyre speed; spread ${SPREAD_DEG}° and ±${SPEED_SPREAD * 100} % speed`],
  ]);
  const chkSec = sec('Checks', { note: 'the adapter on the J501', open: false });
  const chk = readouts(chkSec);
  const C = man.checks, cl = C.clearance, air = C.airflow, tip = C.tipping;
  const antMin = Math.min(...Object.values(cl.antenna_min_gap_mm));
  chk.set([
    ['under the turret', `${cl.deck_min_gap_mm} mm least gap to the deck (pan ${cl.deck_worst_pose_deg?.[0]}°, tilt ${cl.deck_worst_pose_deg?.[1]}°)`, cl.deck_min_gap_mm > 3 ? 'ok' : 'fail'],
    ['ball way out', `the muzzle is ${C.muzzle_outside_deck_mm} mm or more past the deck's edge at -25°`, C.muzzle_outside_deck_mm > 0 ? 'ok' : 'fail'],
    ['upright antennas', antMin < 3 ? `the barrel hits them (${antMin} mm): depression ≤ ${Math.min(...cl.antenna_tilt_max_deg.map((r) => r[1]))}° at pans ${(cl.antenna_limited_pans_deg ?? []).map(([a, b]) => `${a}..${b}°`).join(', ')}` : 'clear', antMin < 3 ? 'warn' : 'ok'],
    ['J501 fan', `-${air.flow_drop_pct} % flow through the shroud (${air.loss_pa} Pa, est); intake and exhaust kept apart`, air.flow_drop_pct < 10 ? 'ok' : 'warn'],
    ['tipping', `${tip.total_kg} kg; a ${tip.push_to_tip_n} N push at the tilt axis tips the box over`, tip.push_to_tip_n > 15 ? 'ok' : 'warn'],
    ['speed cap', `hardware: on the fixed 12 V rail the X2216s throw at most ${C.overspeed.physics_ceiling_fps} fps flat out (cap 70); the chronograph trips over 66`, C.overspeed.physics_ceiling_fps <= 70 ? 'ok' : 'fail'],
    ['ARM released', `a dropped ball still fires within ${C.release.after_drop_ms} ms; the phase-short brake stops the flywheels to 5 % in ~${C.release.brake_to_5pct_ms} ms (${C.release.coast_s} s unbraked)`, 'ok'],
    ['lid screws', C.lid_screw],
  ]);

  // ------------------------------------------------------------------------------------------------ controls
  function pullTrigger(on) {
    if(S.reloading){S.trigger=false;return;}
    S.trigger = on;
    if (on) {
      if (S.arm.size) S.queue = Math.max(S.queue, 1);
      if (!S.arm.size) { say('Hold ARM first: nothing spins or feeds unless the safety line is held'); }
      else if (S.rpm < 0.95 * fl.rpm) say('Flywheels spinning up…', 900);
      if (!hopperCount()) say('Hopper empty: RELOAD (R)');
    }
  }
  function reload() {
    if(S.reloading)return false;
    if(hopperCount()>=BALLS){say('Hopper full · 30 / 30 balls');return false;}
    if(S.journey)stopJourney();
    S.arm.clear();S.trigger=false;S.queue=0;S.phiCmd=S.phi;
    S.reloading={elapsed:0,delivered:0,missing:BALLS-hopperCount(),reduced:matchMedia('(prefers-reduced-motion: reduce)').matches};
    if(S.view==='explode')setView('solid');
    S.explodeCmd=0;explSl.set(0);
    armBtn.disabled=fireBtn.disabled=reloadBtn.disabled=true;
    reloadBtn.setAttribute('aria-busy','true');
    say('Reloading · opening flap',1200);
    // A close inspection can crop the jar above the hopper. Ease out only when
    // its travel would leave the viewport; normal range views stay untouched.
    if(!S.reloading.reduced){
      tiltPivot.updateWorldMatrix(true,false);
      const b=refill.bounds,pts=Array.from({length:8},(_,i)=>tiltPivot.localToWorld(new THREE.Vector3(i&1?b.max.x:b.min.x,i&2?b.max.y:b.min.y,i&4?b.max.z:b.min.z)));
      if(pts.some(p=>{const v=p.clone().project(stage.camera);return Math.abs(v.x)>.9||Math.abs(v.y)>.85||v.z>1;})){
        const box=new THREE.Box3().setFromPoints(pts);
        for(const p of parts)if(p.mesh.visible)box.expandByObject(p.mesh);
        const fit=stage.fitView(box,{direction:stage.camera.position.clone().sub(stage.controls.target),margin:1.08,apply:false});
        cam.to={target:fit.center,pos:fit.position};
      }
    }
    sfx.reload();
    return true;
  }
  function stepReload(dt){
    const r=S.reloading;if(!r)return;
    r.elapsed+=dt;
    const status=refill.step(r.elapsed,r.missing,r.reduced);
    S.flapAngle=status.open*RELOAD_OPEN_ANGLE;
    while(r.delivered<status.delivered){
      const empty=S.pockets.indexOf(false);
      if(empty>=0)S.pockets[empty]=true;
      else S.pile=Math.min(pileBalls.length,S.pile+1);
      r.delivered++;
    }
    reloadBtn.querySelector('b').textContent=status.phase;
    if(status.done){
      S.reloading=null;S.flapAngle=0;refill.hide();
      armBtn.disabled=fireBtn.disabled=reloadBtn.disabled=false;
      reloadBtn.removeAttribute('aria-busy');reloadBtn.querySelector('b').textContent='RELOAD';
      say('Ready! 30 / 30 balls',1600);
    }
  }
  let targetReset = null;
  function resetTargets() {
    // Re-rack the existing range. Keep the scene, flying balls and conversation alive.
    targetReset = { elapsed: 0, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? .18 : .85,
      plates: plates.map(p => p.th), cans: cans.map(c => ({ position: c.m.position.clone(), quaternion: c.m.quaternion.clone() })) };
    for (const p of plates) { p.w = 0; p.down = false; }
    for (const c of cans) { c.dyn = false; c.rest = false; c.v.set(0, 0, 0); c.w.set(0, 0, 0); }
    paper.clear();
    S.hits = 0;
  }
  function stepTargetReset(dt) {
    const reset = targetReset;
    if (!reset) return;
    reset.elapsed += dt;
    const x = Math.min(1, reset.elapsed / reset.duration), a = x * x * (3 - 2 * x);
    plates.forEach((p, i) => { p.th = THREE.MathUtils.lerp(reset.plates[i], -4 * D2R, a); p.hinge.rotation.x = -p.th; });
    cans.forEach((c, i) => { c.m.position.lerpVectors(reset.cans[i].position, c.home, a); c.m.quaternion.copy(reset.cans[i].quaternion).slerp(new THREE.Quaternion(), a); });
    if (x === 1) targetReset = null;
  }
  function clearBalls() { for (const b of S.flying) scene.remove(b.g, b.streak); S.flying = []; }

  const onKey = (ev, down) => {
    if (!S.active) return;
    const k = ev.key.toLowerCase();
    // Release held shortcuts even if focus moved into a native control meanwhile.
    if (!down) {
      S.keys.delete(k);
      if (k === ' ') S.arm.delete('key');
      if (k === 'f' || k === 'enter') pullTrigger(false);
    }
    if (ev.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable=false])')) return;
    if ((k === ' ' || k === 'enter') && ev.target?.closest?.('button, a, [role=button]')) return;
    if (k === ' ') { ev.preventDefault(); if (down && !S.reloading) S.arm.add('key'); else S.arm.delete('key'); return; }
    if (k === 'enter' && ev.target?.closest?.('button, a')) return;
    if (k === 'f' || k === 'enter') { ev.preventDefault(); if (down && !ev.repeat) pullTrigger(true); if (!down) pullTrigger(false); return; }
    if (['arrowleft', 'arrowright', 'arrowup', 'arrowdown', 'a', 'd', 'w', 's'].includes(k)) { ev.preventDefault(); if (down) S.keys.add(k); else S.keys.delete(k); return; }
    if (!down || ev.repeat) return;
    if (k === 'r') reload();
    else if (k === 't') resetTargets();
    else if (k === 'x') setView(S.view === 'xray' ? 'solid' : 'xray');
    else if (k === 'c') setView(S.view === 'section' ? 'solid' : 'section');
    else if (k === 'e') setView(S.view === 'explode' ? 'solid' : 'explode');
    else if (k === 'l') { S.labels = !S.labels; labelsT.checked = S.labels; }
    else if (k === 'j') (S.journey ? stopJourney() : startJourney());
    else if (k === 'escape') { if (S.journey) stopJourney(); select(null); }
  };
  const kd = (e) => onKey(e, true), ku = (e) => onKey(e, false);
  const blur = () => { S.arm.clear(); S.trigger = false; S.keys.clear(); };

  // click / tap: a part -> what it does; the range -> aim there (a drag still orbits the camera)
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let downAt = null;
  const pointers = new Set();
  const canvas = stage.renderer.domElement;
  const onDown = (ev) => {
    pointers.add(ev.pointerId);
    downAt = pointers.size === 1 && ev.button === 0 ? { id:ev.pointerId,x:ev.clientX,y:ev.clientY,t:performance.now() } : null;
  };
  const onCancel = ev => {pointers.delete(ev.pointerId);downAt=null;};
  const onUp = (ev) => {
    const eligible = pointers.size===1 && downAt?.id===ev.pointerId;
    pointers.delete(ev.pointerId);
    if (!S.active || !eligible) {downAt=null;return;}
    const moved = Math.hypot(ev.clientX - downAt.x, ev.clientY - downAt.y), dt = performance.now() - downAt.t;
    downAt = null;
    if (moved > 8 || dt > 600) return;
    const r = canvas.getBoundingClientRect();
    ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, stage.camera);
    const sect = S.view === 'section';
    const hit = ray.intersectObjects(pickable(), false).find((h) => h.object.visible && (!sect || clipPlane.distanceToPoint(h.point) >= 0) && h.object.material.opacity > 0.3);
    const far = ray.intersectObjects([...hitTargets(), ground], false)[0];
    if (hit && (!far || hit.distance <= far.distance + 1e-3)) { const p = parts.find((q) => q.mesh === hit.object); if (p) { select(p); return; } }
    if (far) aimAt(far.point);
  };
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ visible: false }));
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  // ------------------------------------------------------------------------------------------------ the aim solver
  const tmpV = new THREE.Vector3(), tmpQ = new THREE.Quaternion();
  // the muzzle and its direction (page, world) at a pan and tilt, without moving the turret
  function muzzleAt(pan, tilt, out, dir) {
    const sp = panPivot.rotation.y, st = tiltPivot.rotation.x;
    panPivot.rotation.y = pan; tiltPivot.rotation.x = -tilt;
    panPivot.updateMatrixWorld(true);
    muzzle.getWorldPosition(out);
    muzzle.getWorldQuaternion(tmpQ);
    dir.set(0, 0, 1).applyQuaternion(tmpQ);
    panPivot.rotation.y = sp; tiltPivot.rotation.x = st;
    panPivot.updateMatrixWorld(true);
  }
  // fly a ball from p with velocity v until it is `dist` m from the pan axis horizontally; its height there
  function heightAt(p0, v0, dist, axis) {
    const p = p0.clone(), v = v0.clone(), h = 0.002;
    for (let i = 0; i < 4000; i++) {
      const sp = v.length();
      v.y -= 9.81 * h; v.addScaledVector(v, -K_DRAG * sp * h);
      p.addScaledVector(v, h);
      if (Math.hypot(p.x - axis.x, p.z - axis.z) >= dist) return p.y;
      if (p.y < -1) return -1;
    }
    return p.y;
  }
  function tiltMax(panRad) {                       // the most depression allowed at this pan (deg, positive)
    let m = -lim.tilt_deg[0];
    if (S.antennas) {
      const tb = man.checks.clearance.antenna_tilt_max_deg, d = ((panRad / D2R + 540) % 360) - 180;
      let best = tb[0];
      for (const r of tb) if (Math.abs(r[0] - d) < Math.abs(best[0] - d)) best = r;
      m = Math.min(m, best[1]);
    }
    return m;
  }
  function aimAt(pt) {
    const axis = new THREE.Vector3();
    panPivot.getWorldPosition(axis);
    let pan = Math.atan2(pt.x - axis.x, pt.z - axis.z);
    if (Math.abs(pan) > lim.pan_deg[1] * D2R) { say(`Out of the pan range (±${lim.pan_deg[1]}°: the cables wind up past that)`); pan = Math.sign(pan) * lim.pan_deg[1] * D2R; }
    const dist = Math.hypot(pt.x - axis.x, pt.z - axis.z);
    const p0 = new THREE.Vector3(), d0 = new THREE.Vector3();
    const miss = (tilt) => { muzzleAt(pan, tilt, p0, d0); return heightAt(p0, d0.multiplyScalar(launchSpeed), dist, axis) - pt.y; };
    let lo = -tiltMax(pan) * D2R, hi = 0;
    let tilt;
    if (miss(hi) < 0) { tilt = 0; say('Too far for a level shot: the barrel never points above level, so the ball falls short', 2600); }
    else if (miss(lo) > 0) { tilt = lo; say(`Too close and low: the tilt stops at ${(-lo / D2R).toFixed(1)}°`, 2200); }
    else { for (let k = 0; k < 22; k++) { const mid = (lo + hi) / 2; if (miss(mid) > 0) hi = mid; else lo = mid; } tilt = (lo + hi) / 2; }
    S.panCmd = pan; S.tiltCmd = tilt;
    panSl.set(Math.round(pan / D2R)); tiltSl.set(+(tilt / D2R).toFixed(1));
  }

  // ------------------------------------------------------------------------------------------------ views
  function setView(v) {
    if (v === 'explode' && S.journey) stopJourney();
    if (v === 'explode') { S.explodeCmd = Math.max(S.explodeCmd, 1); explSl.set(S.explodeCmd); }
    else if (S.view === 'explode') { S.explodeCmd = 0; explSl.set(0); }
    S.view = v;
    viewChips.mark(v);
    bar.querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('on', b.dataset.view === v));
    const xr = v === 'xray' || v === 'section';
    for (const p of parts) {
      const m = p.mat, b = m.userData.base;
      const see = v === 'xray' && p.shell;
      m.transparent = see || b.transparent;
      m.opacity = see ? (p.e.group === 'j501' ? 0.08 : 0.14) : b.opacity;
      m.depthWrite = !see && b.depthWrite;
      m.clippingPlanes = v === 'section' ? [clipPlane] : null;
      m.clipShadows = true;
      m.needsUpdate = true;
      p.mesh.castShadow = !see && b.opacity >= 1;
      p.cap.visible = v === 'section';
    }
    for (const m of ballMats) { m.clippingPlanes = v === 'section' ? [clipPlane] : null; m.needsUpdate = true; }
    for (const m of [pileFoam, pileSeam, pileCap]) { m.transparent = xr; m.opacity = xr ? 0.28 : 1; m.depthWrite = !xr; }
    pathLine.visible = xr;
    if (v === 'section' && !S.journey) say('Cut through the ball path: look from the turret\'s left', 1800);
    if (v === 'explode') setTimeout(() => { if (S.view === 'explode' && !S.journey) frameAll(); }, 700);
    onLayout();
  }
  // the camera on everything of the turret and the box as they are now (exploded or not), from where it looks now
  function frameAll() {
    const b = new THREE.Box3();
    for (const p of parts) if (p.mesh.visible) b.expandByObject(p.mesh);
    const dir = stage.camera.position.clone().sub(stage.controls.target).normalize();
    stage.fitView(b, { direction: dir, margin: 1.06 });
  }
  function highlight(names, on = true) {
    const set = new Set(names);
    for (const p of parts) {
      const lit = on && set.has(p.e.part);
      p.mat.emissive.set(lit ? 0x00f0ff : 0x000000);
      p.mat.emissiveIntensity = lit ? 0.55 : 0;
    }
  }
  function select(p, frameIt = false) {
    S.selected = p;
    highlight(p ? [p.e.part] : []);
    if (!p) { card.hidden = true; partSel.value = ''; return; }
    partSel.value = p.e.name;
    const e = p.e;
    const facts = [];
    if (e.material) facts.push(`${e.material.toUpperCase()}${e.mass_g ? `, ${fmt(e.mass_g, 0)} g` : ''}${e.qty > 1 ? ` (x${e.qty})` : ''}${e.print_h ? `, ~${e.print_h} h to print` : ''}`);
    else if (e.mass_g) facts.push(`${fmt(e.mass_g, 1)} g, bought`);
    if (e.how) facts.push(e.how);
    if (e.note) facts.push(e.note);
    card.innerHTML = `<button type="button" class="tb-x" aria-label="Close">×</button><h3>${esc(e.title)}</h3><p>${esc(e.role || e.doc || '')}</p>`
      + facts.map((f) => `<p class="tb-fact">${esc(f)}</p>`).join('') + (e.doc && e.role ? `<p class="tb-doc">${esc(e.doc)}</p>` : '');
    card.querySelector('.tb-x').onclick = () => select(null);
    card.hidden = false;
    if (frameIt) {
      if (S.view === 'solid' && !p.shell && p.e.group !== 'j501') setView('xray');       // an inner part: see in
      const c = new THREE.Box3().setFromObject(p.mesh).getCenter(new THREE.Vector3());
      ease(c, Math.max(0.18, new THREE.Box3().setFromObject(p.mesh).getSize(new THREE.Vector3()).length() * 1.6));
    }
  }

  // camera: named shots, and an eased glide for the journey and picks
  const cam = { to: null };
  function frame(id) {
    stopCamEase();
    const axis = new THREE.Vector3();
    panPivot.getWorldPosition(axis);
    const top = axis.clone().add(new THREE.Vector3(0, 0.2, 0));
    const box = [new THREE.Vector3(-0.105, CRATE.h, -0.12), new THREE.Vector3(0.105, CRATE.h, 0.1), new THREE.Vector3(0, CRATE.h + 0.33, 0)];
    if (id === 'range') {                                          // over the turret's shoulder, down the range
      const tall = stage.camera.aspect < 1;                      // a phone held upright: further back, the turret centred
      stage.camera.position.copy(axis).add(new THREE.Vector3(...(tall ? [0.1, 0.75, -1.75] : [0.3, 0.5, -1.2])));
      stage.controls.target.copy(axis).add(new THREE.Vector3(...(tall ? [0, -0.12, 1.5] : [-0.05, -0.15, 2.0])));
      stage.controls.update();
    } else if (id === 'turret') {
      stage.fitView([...box, top], { direction: new THREE.Vector3(0.9, 0.55, 0.85), target: axis.clone().add(new THREE.Vector3(0, -0.02, 0.01)), margin: 1.05 });
    } else if (id === 'side') {
      stage.fitView([axis.clone().add(new THREE.Vector3(0, -0.06, -0.08)), axis.clone().add(new THREE.Vector3(0, 0.2, 0.22))], { direction: new THREE.Vector3(1, 0.18, 0.08), target: axis.clone().add(new THREE.Vector3(0, 0.08, 0.05)), margin: 1.1 });
    } else if (id === 'back') {
      stage.fitView([...box, top], { direction: new THREE.Vector3(-0.35, 0.45, -1), target: axis.clone().add(new THREE.Vector3(0, -0.04, 0)), margin: 1.08 });
    }
  }
  function ease(target, dist, dir = null) {
    const d = dir ?? stage.camera.position.clone().sub(stage.controls.target).normalize();
    cam.to = { target: target.clone(), pos: target.clone().addScaledVector(d, dist) };
  }
  function stopCamEase() { cam.to = null; }
  const onCamStart = () => { if (!S.journey?.auto) stopCamEase(); };

  // ------------------------------------------------------------------------------------------------ the journey
  const J = man.journey;
  function startJourney() {
    if(S.reloading){say('Finishing reload first…');return;}
    if (S.journey) stopJourney();
    select(null);
    for (const b of S.flying) b.demo = false;
    S.journey = { step: 0, t: 0, ball: null, auto: true, pocket: null, labels: S.labels, reassembling: S.explode > 1e-4 };
    S.explodeCmd = 0; explSl.set(0);
    setView('section');
    S.labels = false; labelsT.checked = false;
    jcard.hidden = false;
    document.body.classList.add('tb-journey-on');
    S.panCmd = S.pan; S.tiltCmd = Math.min(S.tilt, -2 * D2R);
    sfx.turret.slowmo(1);
    sfx.turret.pile();                                // the first stage, the hopper (gotoStep plays the others)
    renderJourney();
    onLayout();
  }
  function stopJourney() {
    const jy = S.journey;
    S.journey = null;
    S.timeScale = 1;
    const park = man.dial_park_deg;
    S.phi = S.phiCmd = (Math.ceil((S.phi / D2R - park) / 45 - 1e-6) * 45 + park) * D2R;     // park: a spoke over the exit
    if (jy?.ball) { tiltPivot.remove(jy.ball.g); }
    for (const b of S.flying) b.demo = false;
    if (jy) { S.labels = jy.labels; labelsT.checked = jy.labels; }
    highlight([]);
    jcard.hidden = true;
    document.body.classList.remove('tb-journey-on');
    setView('solid');
    frame('turret');
    onLayout();
  }
  function renderJourney() {
    const jy = S.journey, st = J[jy.step];
    jcard.innerHTML = `<div class="tb-jhead"><b>${esc(st.title)}</b><span>${jy.step + 1} / ${J.length}</span><button type="button" class="tb-x" aria-label="Close">×</button></div>`
      + `<p>${esc(st.text)}</p><div class="tb-jnav"><button type="button" data-j="prev">◂ PREV</button><button type="button" data-j="play">${jy.auto ? 'PAUSE' : 'PLAY'}</button><button type="button" data-j="next">NEXT ▸</button></div>`
      + `<div class="tb-jdots">${J.map((_, i) => `<i class="${i === jy.step ? 'on' : i < jy.step ? 'done' : ''}"></i>`).join('')}</div>`;
    jcard.querySelector('.tb-x').onclick = stopJourney;
    jcard.querySelectorAll('[data-j]').forEach((b) => { b.onclick = () => journeyNav(b.dataset.j); });
    highlight(st.parts);
  }
  function journeyNav(what) {
    const jy = S.journey;
    if (!jy) return;
    if (what === 'play') { jy.auto = !jy.auto; if (!jy.auto) stopCamEase(); renderJourney(); return; }
    const to = Math.max(0, Math.min(J.length - 1, (jy.pendingStep ?? jy.step) + (what === 'next' ? 1 : -1)));
    gotoStep(to);
  }
  // each step: where the camera looks, how fast time runs, what the ball does
  // the ball moves at `vis` m/s on the screen whatever its real speed; everything else runs at the matching slow motion,
  // so in the nip the wheels' surfaces and the ball move as they really do relative to each other
  const STEP = {
    hopper: { scale: 1, dwell: 4.5, dist: 0.34, view: 'section', dir: [1, 0.45, -0.2] },
    dial: { scale: 0.025, dist: 0.26, view: 'xray', dir: [-1, 0.75, 0.3] },          // from the right: the tilt servo is on the left
    exit: { vis: 0.006, dist: 0.2, view: 'section', dir: [1, 0.25, -0.1] },
    chute: { vis: 0.012, dist: 0.17, view: 'section', dir: [1, 0.2, -0.05] },
    nip: { vis: 0.005, dist: 0.16, view: 'xray', dir: [-0.62, -0.34, 0.25] },        // from below on the right, under the cage
    barrel: { vis: 0.04, dist: 0.24, view: 'section', dir: [1, 0.3, 0.1] },
    muzzle: { vis: 0.02, dwell: 2.2, dist: 0.22, view: 'section', dir: [1, 0.35, 0.45] },
    flight: { scale: 0.12, dist: 0, view: 'solid' },
  };
  // where the ball is at the start and the end of each step (metres along the path)
  const JWIN = { exit: [0, segS.chute[1] * 0.25], chute: [segS.chute[1] * 0.25, cum[IX.nipIn] - 0.004], nip: [cum[IX.nipIn] - 0.004, cum[IX.nipOut] + 0.006],
    barrel: [cum[IX.nipOut] + 0.006, cum[IX.muzzle] - 0.006], muzzle: [cum[IX.muzzle] - 0.006, cum[IX.muzzle] + 0.03] };
  function gotoStep(i) {
    const jy = S.journey;
    if (jy.reassembling) { jy.pendingStep = i; return; }
    jy.step = i;
    jy.t = 0;
    jy.landed = null;
    jy.flashed = jy.nipped = false;
    const id = J[i].id;
    // rewind or fast-forward the demonstration ball to where this step starts
    if (['hopper', 'dial'].includes(id)) {
      if (jy.ball) { tiltPivot.remove(jy.ball.g); jy.ball = null; }
      S.phi = S.phiCmd = Math.round((S.phi / D2R - man.dial_park_deg) / 45) * 45 * D2R + man.dial_park_deg * D2R;
      const k = pocketAtExitNext();
      if (k != null) S.pockets[k] = true;
      jy.pocket = k;
      if (id === 'dial') S.phiCmd = S.phi + 22.5 * D2R;
    } else if (['exit', 'chute', 'nip', 'barrel', 'muzzle'].includes(id)) {
      if (!jy.ball) { const { g } = ballMesh(); tiltPivot.add(g); jy.ball = { g, s: 0 }; }
      jy.ball.s = JWIN[id][0];
      jy.ball.g.visible = true;
    } else if (id === 'flight') {
      if (jy.ball) { tiltPivot.remove(jy.ball.g); jy.ball = null; }
      for (const b of S.flying) b.demo = false;
      launch(true);
    }
    // each stage's sound, in its slow motion (the nip and the muzzle sound when the ball gets there: stepJourney)
    sfx.turret.slowmo(stageScale(id));
    if (id === 'hopper') sfx.turret.pile();
    else if (id === 'dial') sfx.turret.dial();
    else if (id === 'exit') sfx.turret.drop();
    else if (id === 'chute') sfx.turret.roll((JWIN.chute[1] - JWIN.chute[0]) / STEP.chute.vis);
    else if (id === 'barrel') sfx.turret.bore((JWIN.barrel[1] - JWIN.barrel[0]) / STEP.barrel.vis);
    else if (id === 'flight') sfx.turret.fly();
    stepJourney(0); // Place the new stage immediately, including when manually stepping while paused.
    renderJourney();
  }
  // the time scale a stage starts at (stepJourney keeps it up to date as the ball goes)
  const stageScale = (id) => STEP[id].scale ?? (JWIN[id] ? STEP[id].vis / Math.max(0.05, speedAt(JWIN[id][0])) : 1);
  function pocketAtExitNext() {                       // the pocket that reaches the exit next as the dial turns forward
    let best = null, bestA = 1e9;
    S.pockets.forEach((_, k) => {
      const a = (((45 * k + S.phi / D2R) % 360) + 360) % 360;
      const toGo = (360 - a) % 360;
      if (toGo > 1e-3 && toGo < bestA) { bestA = toGo; best = k; }
    });
    return best;
  }
  function stepJourney(dtReal) {
    const jy = S.journey;
    if (jy.reassembling) {
      S.timeScale = 1;
      if (S.explode > 1e-4) return;
      jy.reassembling = false;
      const pending = jy.pendingStep ?? 0; delete jy.pendingStep;
      gotoStep(pending);
      return;
    }
    const st = J[jy.step], cfg = STEP[st.id];
    S.timeScale = cfg.scale ?? 1;
    if (cfg.scale != null) sfx.turret.slowmo(cfg.scale);      // the ball's stages set it as the ball goes (below)
    jy.t += dtReal;
    if (cfg.view && S.view !== cfg.view) setView(cfg.view);
    let done = false;
    if (st.id === 'hopper') done = jy.t > cfg.dwell;
    else if (st.id === 'dial') done = Math.abs(S.phiCmd - S.phi) < 1e-4 && jy.t > 0.5;
    else if (['exit', 'chute', 'nip', 'barrel', 'muzzle'].includes(st.id)) {
      const b = jy.ball;
      const end = JWIN[st.id][1];
      S.timeScale = cfg.vis / Math.max(0.05, speedAt(b.s));
      sfx.turret.slowmo(S.timeScale);
      b.s = Math.min(end, b.s + cfg.vis * dtReal);
      pathAt(b.s, b.g.position);
      if (b.s > segS.barrel[1]) b.g.position.copy(muzzle.position).add(new THREE.Vector3(0, 0, b.s - segS.barrel[1]));
      squash(b.g, b.s);
      gateBlink(b.s);
      if (st.id === 'nip' && b.s >= cum[IX.nipIn] && !jy.nipped) { jy.nipped = true; sfx.turret.nip(); }
      if (st.id === 'muzzle' && b.s >= segS.barrel[1] && !jy.flashed) { jy.flashed = true; flashT = 0.06; sfx.turret.shot({ nip: false }); }
      done = b.s >= end - 1e-6 && (st.id !== 'muzzle' || jy.t > cfg.dwell);
    } else if (st.id === 'flight') {                             // over a moment after it lands or hits something
      const b = S.flying.find((q) => q.demo);
      if (b && (b.hitOnce || b.rolling || b.g.position.y <= BALL_R + 1e-3) && jy.landed == null) jy.landed = jy.t;
      done = (jy.landed != null && jy.t > jy.landed + 1.6) || jy.t > 8;
    }
    // the camera: close on the step's place in the turret, from its left (the cut side), a little above
    if (st.focus) {
      const f = P(st.focus);
      if (jy.ball && ['exit', 'chute', 'nip', 'barrel', 'muzzle'].includes(st.id)) f.lerp(jy.ball.g.position, 0.5);
      const w = tiltPivot.localToWorld(f.clone());
      const dir = new THREE.Vector3(...(cfg.dir ?? [1, 0.42, -0.18])).applyQuaternion(panPivot.getWorldQuaternion(tmpQ)).normalize();
      ease(w, cfg.dist, dir);
    } else {
      const b = S.flying.find((q) => q.demo);
      if (b) { const dir = new THREE.Vector3(0.9, 0.55, -0.55).normalize(); ease(b.g.position.clone().lerp(new THREE.Vector3(0, 0.4, 1.5), 0.3), 1.6, dir); }
    }
    if (done && jy.auto) {
      if (jy.step < J.length - 1) gotoStep(jy.step + 1); else if (jy.t > 2.5) stopJourney();
    }
  }
  // the ball's speed along the path (m/s, real time): falling round the chute, then rolling, then flying out
  function speedAt(s) {
    if (s < segS.chute[1]) return Math.sqrt(0.0025 + 2 * 9.81 * chuteR * Math.sin((s / segS.chute[1]) * Math.PI / 2));
    if (s < segS.run[1]) return mech.timing.speed_into_nip_mps;
    const u = (s - segS.barrel[0]) / 0.0145;                    // through the nip (about 14.5 mm of contact) it gets up to speed
    if (u < 1) return Math.max(mech.timing.speed_into_nip_mps, launchSpeed * Math.min(1, u * u));
    return launchSpeed;
  }
  function squash(g, s) {                                       // squeezed 2.7 mm between the tyres at the nip
    const nipC = cum[IX.nipC], half = (cum[IX.nipOut] - cum[IX.nipIn]) / 2, x = Math.abs(s - nipC);
    const sq = x < half ? (1 - fl.crush_mm / BALL.d / 1000 * (1 - x / half)) : 1;
    g.scale.set(sq, 1, 1 / Math.sqrt(sq));
  }
  let gateT = [0, 0];
  function gateBlink(s) { [IX.gate1, IX.gate2].forEach((i, k) => { if (Math.abs(s - cum[i]) < 0.004) gateT[k] = 0.2; }); }

  // ------------------------------------------------------------------------------------------------ firing
  let flashT = 0;
  function launch(demo = false) {
    const p = new THREE.Vector3(), d = new THREE.Vector3();
    muzzle.getWorldPosition(p);
    muzzle.getWorldQuaternion(tmpQ);
    d.set(0, 0, 1).applyQuaternion(tmpQ);
    const ang = (demo ? 0 : SPREAD_DEG) * D2R * Math.sqrt(-2 * Math.log(Math.max(1e-6, Math.random()))), az = Math.random() * 2 * Math.PI;
    const perp1 = new THREE.Vector3().crossVectors(d, new THREE.Vector3(0, 1, 0)).normalize(), perp2 = new THREE.Vector3().crossVectors(perp1, d);
    d.addScaledVector(perp1, Math.cos(az) * Math.tan(ang)).addScaledVector(perp2, Math.sin(az) * Math.tan(ang)).normalize();
    // A narrated flight demonstrates nominal speed even after manual stage skips.
    const v = demo ? launchSpeed : launchSpeed * (1 + SPEED_SPREAD * (Math.random() * 2 - 1)) * (S.rpm > 0 ? Math.min(1, S.rpm / fl.rpm) : 1);
    const { g, streak } = ballMesh();
    g.position.copy(p);
    scene.add(g, streak);
    S.flying.push({ g, streak, v: d.multiplyScalar(v), age: 0, rolling: false, resting: false, demo, trail: demo ? [] : null, hitOnce: false });
    if (S.flying.length > 80) { const o = S.flying.shift(); scene.remove(o.g, o.streak); }
    S.lastSpeed = v;
    S.shots += 1;
    flashT = 0.06;
    if (!demo) sfx.turret.shot({ power: v / launchSpeed });       // the journey's muzzle stage plays its own
  }
  function stepTransit(dt) {
    const tmT = (mech.timing.chute_ms + mech.timing.to_nip_ms) / 1000;
    for (let i = S.transit.length - 1; i >= 0; i--) {
      const b = S.transit[i];
      b.t += dt;
      // pace: the chute and the roll to the nip by the computed times, then the barrel at the ball's speed
      let s;
      if (b.t < tmT) s = segS.run[1] * Math.min(1, (b.t / tmT) ** 1.6);
      else s = segS.run[1] + (b.t - tmT) * launchSpeed;
      pathAt(Math.min(s, segS.barrel[1]), b.g.position);
      squash(b.g, s);
      gateBlink(s);
      if (s >= segS.barrel[1]) { tiltPivot.remove(b.g); S.transit.splice(i, 1); launch(); }
    }
  }

  // ------------------------------------------------------------------------------------------------ physics
  const inv = new THREE.Quaternion(), lp = new THREE.Vector3(), n = new THREE.Vector3(), wq = new THREE.Quaternion(), wp = new THREE.Vector3();
  function collideObb(b, o) {
    o.obj.getWorldPosition(wp);
    o.obj.getWorldQuaternion(wq);
    inv.copy(wq).invert();
    lp.copy(b.g.position).sub(wp).applyQuaternion(inv);
    const h = o.half, c = new THREE.Vector3(Math.max(-h.x, Math.min(h.x, lp.x)), Math.max(-h.y, Math.min(h.y, lp.y)), Math.max(-h.z, Math.min(h.z, lp.z)));
    const dv = lp.clone().sub(c), dist = dv.length();
    if (dist > BALL_R) return false;
    if (dist > 1e-6) n.copy(dv).divideScalar(dist);
    else {                                                       // inside: out along the nearest face
      const px = h.x - Math.abs(lp.x), py = h.y - Math.abs(lp.y), pz = h.z - Math.abs(lp.z);
      n.set(0, 0, 0);
      if (px < py && px < pz) n.x = Math.sign(lp.x) || 1; else if (py < pz) n.y = Math.sign(lp.y) || 1; else n.z = Math.sign(lp.z) || 1;
    }
    const contactLocal = c.clone();
    n.applyQuaternion(wq);
    b.g.position.copy(c.applyQuaternion(wq).add(wp)).addScaledVector(n, BALL_R + 1e-4);
    const vn = b.v.dot(n);
    if (vn < 0) {
      const e = o.kind === 'paper' ? 0.15 : 0.32;
      const j = -(1 + e) * vn;                                    // per unit ball mass
      b.v.addScaledVector(n, j);
      const vt = b.v.clone().addScaledVector(n, -b.v.dot(n));
      b.v.addScaledVector(vt, -0.25);
      if (o.kind === 'plate' && !o.plate.down) hitPlate(o.plate, contactLocal, j * BALL.mass);
      if (o.kind === 'paper' && !b.hitOnce) { b.hitOnce = true; paper.mark(contactLocal); S.hits += 1; sfx.turret.hit('paper', -vn / 15); }
      if (o.kind === 'plate' && !b.hitOnce) { b.hitOnce = true; S.hits += 1; sfx.turret.hit('plate', -vn / 15); ringAt(b.g.position, 0xfff1a8); }
    }
    return true;
  }
  function hitPlate(p, local, J) {
    // the impulse is along the face normal (local +z towards the shooter) at height local.y + 0.12 above the hinge
    const lever = local.y + 0.12;
    p.w += (J * lever) / p.I;
  }
  function stepPlates(dt) {
    if (targetReset) return;
    for (const p of plates) {
      if (p.down) continue;
      const beta = Math.atan2(0.004, 0.12), L = Math.hypot(0.004, 0.12);
      const tq = p.mass * 9.81 * L * Math.sin(p.th - beta);
      p.w += (tq / p.I) * dt - p.w * 0.6 * dt;
      p.th += p.w * dt;
      if (p.th < -4 * D2R) { p.th = -4 * D2R; p.w = Math.max(0, -p.w * 0.2); }
      if (p.th >= 88 * D2R) { p.th = 88 * D2R; p.w = 0; p.down = true; sfx.turret.down(); burstAt(p.face.getWorldPosition(new THREE.Vector3()), 0xff6a13); if (plates.every((q) => q.down)) { setTimeout(() => sfx.chirp(), 300); say('All four plates down!'); } }
      p.hinge.rotation.x = -p.th;
    }
  }
  function hitCan(c, b) {
    const n2 = c.m.position.clone().sub(b.g.position);
    n2.y = 0;
    if (n2.lengthSq() < 1e-9) n2.set(b.v.x, 0, b.v.z);
    n2.normalize();
    const vn = b.v.dot(n2);
    if (vn <= 0) return;
    const j = (1 + 0.35) * vn;
    b.v.addScaledVector(n2, -j);
    wake(c, n2.clone().multiplyScalar(j * BALL.mass / 0.014).add(new THREE.Vector3(0, 0.4, 0)));
    if (!b.hitOnce) { b.hitOnce = true; S.hits += 1; sfx.turret.hit('can', vn / 15); }
  }
  function wake(c, v) {
    if (targetReset) return;
    if (c.dyn) { c.v.add(v); return; }
    c.dyn = true;
    c.v.copy(v);
    c.w.set((Math.random() - 0.5) * 18, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 18);
    for (const o of cans) if (o.on.includes(c)) setTimeout(() => wake(o, new THREE.Vector3((Math.random() - 0.5) * 0.4, 0.1, (Math.random() - 0.5) * 0.4)), 40);
  }
  function stepCans(dt) {
    if (targetReset) return;
    for (const c of cans) {
      if (!c.dyn || c.rest) continue;
      c.v.y -= 9.81 * dt;
      c.m.position.addScaledVector(c.v, dt);
      const wl = c.w.length();
      if (wl > 1e-4) c.m.quaternion.premultiply(tmpQ.setFromAxisAngle(tmpV.copy(c.w).divideScalar(wl), wl * dt));
      if (c.m.position.y < 0.033) {
        c.m.position.y = 0.033;
        if (c.v.y < -0.35) sfx.turret.can(-c.v.y);                  // it lands (and bounces once, softer)
        c.v.y = Math.abs(c.v.y) > 0.6 ? -c.v.y * 0.25 : 0;
        c.v.x *= 1 - 3 * dt; c.v.z *= 1 - 3 * dt;
        c.w.multiplyScalar(1 - 4 * dt);
        const up = tmpV.set(0, 1, 0).applyQuaternion(c.m.quaternion);   // settle on its side
        if (c.v.lengthSq() < 0.01 && c.w.lengthSq() < 0.5) {
          const side = new THREE.Quaternion().setFromUnitVectors(up, new THREE.Vector3(up.x, 0, up.z).normalize());
          c.m.quaternion.premultiply(side);
          c.rest = true;
        }
      }
    }
  }
  function stepBalls(dt) {
    const plateObs = obstacles.filter((o) => o.kind === 'plate'), staticObs = obstacles.filter((o) => o.kind !== 'plate');
    for (const b of S.flying) {
      b.age += dt;
      if (b.resting) continue;
      const n2 = Math.max(1, Math.ceil(b.v.length() * dt / 0.01));
      const h = dt / n2;
      for (let k = 0; k < n2; k++) {
        b.v.y -= 9.81 * h;
        b.v.addScaledVector(b.v, -K_DRAG * b.v.length() * h);
        b.g.position.addScaledVector(b.v, h);
        for (const o of plateObs) if (!o.plate.down) collideObb(b, o);
        for (const o of staticObs) collideObb(b, o);
        for (const c of cans) {
          const d = c.m.position;
          if (!c.dyn) {
            if (Math.abs(b.g.position.y - d.y) < 0.061 + BALL_R && Math.hypot(b.g.position.x - d.x, b.g.position.z - d.z) < 0.033 + BALL_R) hitCan(c, b);
          } else if (b.g.position.distanceTo(d) < 0.05 + BALL_R) hitCan(c, b);
        }
        if (b.g.position.y <= BALL_R) {
          b.g.position.y = BALL_R;
          if (b.v.y < -1) { sfx.turret.bounce(-b.v.y); b.v.y *= -0.3; b.v.x *= 0.5; b.v.z *= 0.5; } else { b.v.y = 0; b.rolling = true; }
        }
      }
      if (b.rolling) b.v.multiplyScalar(Math.max(0, 1 - 4 * dt));
      if (b.rolling && b.v.lengthSq() < 0.0025) { b.resting = true; b.age = 0; }
      const sp = b.v.length();
      b.streak.visible = sp > 4;
      if (b.streak.visible) {
        const len = Math.min(0.4, sp * 0.016), dir = b.v.clone().divideScalar(sp);
        b.streak.scale.set(1, len, 1);
        b.streak.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir.clone().negate());
        b.streak.position.copy(b.g.position).addScaledVector(dir, -BALL_R - len / 2);
      }
      if (b.trail && !b.resting && b.trail.length < 400) b.trail.push(b.g.position.clone());
    }
    for (let i = S.flying.length - 1; i >= 0; i--) {
      const b = S.flying[i];
      if (b.resting && b.age > 20) { scene.remove(b.g, b.streak); S.flying.splice(i, 1); }
    }
  }
  const fx = [];
  function ringAt(pos, color) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.02, 0.03, 24), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    m.position.copy(pos);
    m.lookAt(stage.camera.position);
    scene.add(m);
    fx.push({ m, life: 0.35, life0: 0.35, ring: true });
  }
  function burstAt(pos, color) {
    for (let k = 0; k < 16; k++) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.005, 6, 4), new THREE.MeshBasicMaterial({ color, transparent: true }));
      m.position.copy(pos);
      scene.add(m);
      fx.push({ m, v: new THREE.Vector3(Math.random() - 0.5, Math.random() * 0.9 + 0.2, Math.random() - 0.5).normalize().multiplyScalar(1.5 * (0.4 + Math.random())), life: 0.6 });
    }
    ringAt(pos, color);
  }
  function stepFx(dt) {
    for (let i = fx.length - 1; i >= 0; i--) {
      const f = fx[i];
      f.life -= dt;
      if (f.ring) { f.m.scale.multiplyScalar(1 + dt * 6); f.m.material.opacity = Math.max(0, f.life / f.life0); }
      else { f.v.y -= 9.81 * dt; f.m.position.addScaledVector(f.v, dt); f.m.material.opacity = Math.min(1, f.life * 3); }
      if (f.life <= 0) { scene.remove(f.m); f.m.geometry.dispose(); f.m.material.dispose(); fx.splice(i, 1); }
    }
  }

  // the predicted arc and the impact ring (10 times a second)
  let predT = 0;
  const arcPts = [];
  function predict() {
    const p = new THREE.Vector3(), d = new THREE.Vector3();
    muzzle.getWorldPosition(p);
    muzzle.getWorldQuaternion(tmpQ);
    const v = d.set(0, 0, 1).applyQuaternion(tmpQ).multiplyScalar(launchSpeed);
    arcPts.length = 0;
    arcPts.push(p.clone());
    const objs = hitTargets();
    const r2 = new THREE.Raycaster();
    let hit = null;
    for (let i = 0; i < 300 && !hit; i++) {
      const h = 0.006, q = p.clone();
      const sp = v.length();
      v.y -= 9.81 * h; v.addScaledVector(v, -K_DRAG * sp * h);
      p.addScaledVector(v, h);
      const seg = p.clone().sub(q), len = seg.length();
      r2.set(q, seg.normalize());
      r2.far = len;
      const hh = r2.intersectObjects(objs, false)[0];
      if (hh) hit = { point: hh.point, normal: hh.face ? hh.face.normal.clone().transformDirection(hh.object.matrixWorld) : new THREE.Vector3(0, 1, 0) };
      else if (p.y <= 0) hit = { point: p.clone().setY(0.001), normal: new THREE.Vector3(0, 1, 0) };
      arcPts.push((hit ? hit.point : p).clone());
    }
    if (hit) {
      impact.position.copy(hit.point).addScaledVector(hit.normal, 0.002);
      impact.lookAt(impact.position.clone().add(hit.normal));
    }
    impact.visible = !!hit && S.marker && !S.journey;
    const part=new THREE.Object3D(),up=new THREE.Vector3(0,1,0),delta=new THREE.Vector3();
    const pixelScale=2*Math.tan(stage.camera.fov*Math.PI/360)/Math.max(1,canvas.clientHeight);
    arcLine.count=arcPts.length-1;
    arcHalo.count=arcLine.count;
    for(let i=0;i<arcLine.count;i++){
      delta.subVectors(arcPts[i+1],arcPts[i]);const length=delta.length();
      part.position.copy(arcPts[i]).lerp(arcPts[i+1],.5);
      part.quaternion.setFromUnitVectors(up,delta.normalize());
      const radius=Math.max(.001,stage.camera.position.distanceTo(part.position)*pixelScale*1.7);
      part.scale.set(radius,length,radius);part.updateMatrix();arcLine.setMatrixAt(i,part.matrix);
      part.scale.set(radius*2.4,length,radius*2.4);part.updateMatrix();arcHalo.setMatrixAt(i,part.matrix);
    }
    arcLine.instanceMatrix.needsUpdate=true;
    arcHalo.instanceMatrix.needsUpdate=true;
    arcLine.visible = S.marker && !S.journey;
    arcHalo.visible=arcLine.visible;
  }
  function stepLaser() {
    laser.visible = S.laserReference && S.laserOn && scene.visible;
    if (!laser.visible) return;
    const o = new THREE.Vector3(), d = new THREE.Vector3();
    laserO.getWorldPosition(o);
    laserO.getWorldQuaternion(tmpQ);
    d.set(0, 0, 1).applyQuaternion(tmpQ).normalize();
    let len = 25;
    if (d.y < -1e-4) len = Math.min(len, -o.y / d.y);
    ray.set(o, d);
    ray.far = len;
    const h = ray.intersectObjects(hitTargets(), false)[0];
    if (h && h.distance < len) len = h.distance;
    beam.position.copy(o).addScaledVector(d, len / 2);
    beam.scale.set(1, len, 1);
    beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d);
    dot.position.copy(o).addScaledVector(d, len);
    ray.far = Infinity;
  }

  // ------------------------------------------------------------------------------------------------ callouts
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const tbox = new THREE.Box3(), corner = new THREE.Vector3();
  let tboxT = 0;
  function layoutCallouts() {
    let show = S.labels && !S.journey && S.active;
    const r = canvas.getBoundingClientRect();
    // the turret's outline on the screen (refreshed now and then): labels hug it, and only when it is big enough to label
    if (show && (tboxT++ % 10 === 0 || tbox.isEmpty())) {
      tbox.makeEmpty();
      for (const p of parts) if (p.e.group !== 'j501' && p.mesh.visible) tbox.expandByObject(p.mesh);
    }
    let sx0 = Infinity, sx1 = -Infinity, sy0 = Infinity, sy1 = -Infinity;
    for (let i = 0; i < 8; i++) {
      corner.set(i & 1 ? tbox.max.x : tbox.min.x, i & 2 ? tbox.max.y : tbox.min.y, i & 4 ? tbox.max.z : tbox.min.z).project(stage.camera);
      const x = r.left + (corner.x + 1) / 2 * r.width, y = r.top + (1 - corner.y) / 2 * r.height;
      sx0 = Math.min(sx0, x); sx1 = Math.max(sx1, x); sy0 = Math.min(sy0, y); sy1 = Math.max(sy1, y);
    }
    // labels in the inside views; in the solid view only up close (not over the shoulder down the range)
    const near = stage.camera.position.distanceTo(panPivot.getWorldPosition(corner)) < 1.0;
    if (sy1 - sy0 < 170 || (S.view === 'solid' && !near)) show = false;
    callLayer.hidden = !show;
    if (!show) return;
    const narrow = r.width < 700;
    const see = S.view !== 'solid';
    const cx = (sx0 + sx1) / 2;
    const items = [];
    for (const c of callouts) {
      const w = c.p.mesh.parent.localToWorld(c.local.clone().add(c.p.mesh.position));
      const vis = c.p.mesh.visible && (see || !INNER.has(c.p.e.part)) && !(S.view === 'section' && clipPlane.distanceToPoint(w) < -0.002);
      const s = w.clone().project(stage.camera);
      const x = r.left + (s.x + 1) / 2 * r.width, y = r.top + (1 - s.y) / 2 * r.height;
      const on = vis && s.z < 1 && x > r.left && x < r.right && y > r.top + 40 && y < r.bottom - 10;
      c.el.hidden = !on;
      c.line.style.display = on ? '' : 'none';
      if (on) items.push({ c, x, y });
    }
    if (narrow) {                                          // phones: numbered dots on the parts; tap for the card
      for (const it of items) { it.c.el.classList.add('dot'); it.c.el.style.transform = `translate(${it.x - 11}px, ${it.y - 11}px)`; it.c.line.style.display = 'none'; }
      return;
    }
    const pr = hud.classList.contains('panel-collapsed') ? null : document.getElementById('panel')?.getBoundingClientRect();
    const rightLimit = (pr?.width ? pr.left : r.right) - 10;
    const sm = document.getElementById('summary')?.getBoundingClientRect();
    const left = items.filter((i) => i.x < cx).sort((a, b) => a.y - b.y), right = items.filter((i) => i.x >= cx).sort((a, b) => a.y - b.y);
    const place = (col, xEdge, side) => {
      const smTop = side < 0 && sm?.height && sm.right > xEdge - 160 ? sm.bottom + 10 : r.top + 64;
      const top = Math.max(r.top + 64, smTop), bottom = r.bottom - 120, gap = 26;
      let y = top;
      const ys = col.map((it) => { y = Math.max(y, clamp(it.y, top, bottom)); const out = y; y += gap; return out; });
      const over = (ys.at(-1) ?? 0) - bottom;
      if (over > 0) for (let i = ys.length - 1, push = over; i >= 0 && push > 0; i--) { const room = i ? ys[i] - ys[i - 1] - gap : ys[i] - top; const mv = Math.min(push, Math.max(0, room)); for (let j = i; j < ys.length; j++) ys[j] -= mv; push -= mv; }
      col.forEach((it, i) => {
        const el = it.c.el;
        el.classList.remove('dot');
        el.classList.toggle('left', side < 0);
        const w = el.offsetWidth || 140;
        const lx = side < 0 ? xEdge : xEdge - w;
        el.style.transform = `translate(${lx}px, ${ys[i] - 11}px)`;
        const ax = side < 0 ? lx + w : lx;
        it.c.line.setAttribute('d', `M${ax},${ys[i]} L${ax + side * -14},${ys[i]} L${it.x},${it.y}`);
      });
    };
    place(left, Math.max(r.left + 14, sx0 - 200), -1);
    place(right, Math.min(rightLimit, sx1 + 200), 1);
  }

  // ------------------------------------------------------------------------------------------------ the frame
  let liveT = 0;
  const prevAim = { pan: 0, tilt: 0 };
  const PAN_GEAR = Math.abs(man.pivots.pinion_ratio || 3);
  function step(t, dtReal) {
    if (!S.active) return;
    const paused = S.journey && !S.journey.auto;
    if (paused) { if (S.journey.reassembling) stepJourney(0); S.timeScale = 0; }
    else if (S.journey) stepJourney(dtReal);
    else { S.timeScale = 1; sfx.turret.slowmo(1); }
    const motionDt = paused ? 0 : dtReal;
    const dt = motionDt * S.timeScale;
    // aim: keys slew the command; the servos follow at their top speeds
    const kp = (S.keys.has('arrowleft') || S.keys.has('a') ? 1 : 0) - (S.keys.has('arrowright') || S.keys.has('d') ? 1 : 0);
    const kt = (S.keys.has('arrowup') || S.keys.has('w') ? 1 : 0) - (S.keys.has('arrowdown') || S.keys.has('s') ? 1 : 0);
    if (kp || kt) {
      S.panCmd = clamp(S.panCmd + kp * 60 * D2R * dtReal, lim.pan_deg[0] * D2R, lim.pan_deg[1] * D2R);
      S.tiltCmd = clamp(S.tiltCmd + kt * 15 * D2R * dtReal, -tiltMax(S.panCmd) * D2R, 0);
      panSl.set(Math.round(S.panCmd / D2R)); tiltSl.set(+(S.tiltCmd / D2R).toFixed(1));
    }
    const tmin = -tiltMax(S.pan) * D2R;
    S.tiltCmd = clamp(S.tiltCmd, -25 * D2R, 0);
    const mv = (cur, cmd, rate) => cur + clamp(cmd - cur, -rate * dt, rate * dt);
    S.pan = mv(S.pan, S.panCmd, lim.pan_rate_deg_s * D2R);
    S.tilt = clamp(mv(S.tilt, S.tiltCmd, lim.tilt_rate_deg_s * D2R), tmin, 0);
    // the safety line: ARM held = flywheels up, laser on; released = no feed, and the phase-short brake stops the
    // flywheels (5 % speed ~48 ms after release; unbraked they would coast for 1.1 s)
    const armed = !S.reloading && (S.arm.size > 0 || !!S.journey);
    if (armed !== S.wasArmed) {
      S.wasArmed = armed;
      armBtn.classList.toggle('on', armed);
      if (!armed) { S.queue = 0; S.offFor = 0; if (S.rpm > 0.05 * fl.rpm) sfx.turret.brake(); }
    }
    if (armed) S.rpm = Math.min(fl.rpm, S.rpm + fl.rpm / SPIN_UP_S * dt);
    else if ((S.offFor += dt) > BRAKE_DELAY_S) S.rpm = S.rpm < 0.5 ? 0 : S.rpm * Math.exp(-dt / BRAKE_TAU_S);
    const laserOn = armed && !S.journey;
    if (laserOn !== S.laserOn) { S.laserOn = laserOn; sfx.laser(laserOn); }
    if (!S.journey && (S.trigger || S.queue > 0) && armed && S.explodeCmd > 0) {
      S.explodeCmd = 0; explSl.set(0);
      if (S.view === 'explode') setView('solid');
      say('Reassembling before firing…', 1200);
    }
    const ready = armed && S.rpm >= 0.95 * fl.rpm && hopperCount() > 0 && S.explode < 1e-4;
    fireBtn.classList.toggle('ready', ready);
    const now = performance.now() / 1000;
    if (!S.journey && (S.trigger || S.queue > 0) && ready && Math.abs(S.phiCmd - S.phi) < 1e-6 && now >= S.nextAt) {
      S.phiCmd = S.phi + 45 * D2R;
      S.nextAt = now + 1 / S.rate;
      S.queue = Math.max(0, S.queue - 1);
      sfx.turret.dial();
    }
    if (!armed && !S.journey) S.phiCmd = S.phi;          // released: the dial stops where it is
    // the dial: pockets that pass the exit drop their ball into the chute; empty ones refill from the pile
    const phi0 = S.phi;
    S.phi = mv(S.phi, S.phiCmd, DIAL_DEG_S * D2R);
    const dialSpeed = dt > 0 ? Math.abs(S.phi - phi0) / dt : 0;
    if (S.phi !== phi0) {
      S.pockets.forEach((full, k) => {
        const a0 = 45 * k + phi0 / D2R + 1e-6, a1 = 45 * k + S.phi / D2R + 1e-6;
        if (Math.floor(a0 / 360) !== Math.floor(a1 / 360) && full) {
          S.pockets[k] = false;
          if (S.journey) { const jy = S.journey; if (!jy.ball) { const { g } = ballMesh(); tiltPivot.add(g); jy.ball = { g, s: 0 }; } pathAt(0, jy.ball.g.position); }
          else { const { g } = ballMesh(); tiltPivot.add(g); pathAt(0, g.position); S.transit.push({ g, t: 0 }); sfx.turret.drop(); }   // the journey's exit stage plays its own
        }
        if (Math.floor((a0 - 120) / 360) !== Math.floor((a1 - 120) / 360) && !S.pockets[k] && S.pile > 0) { S.pockets[k] = true; S.pile -= 1; }
      });
    }
    stepReload(dtReal);
    pocketBalls.forEach((g, k) => { g.visible = S.pockets[k]; });
    pileBalls.forEach((g, k) => { g.visible = k < S.pile; });
    // flywheels: drawn turning at the real speed in slow motion, a readable spin otherwise
    const w = (S.rpm / 60) * 2 * Math.PI * S.timeScale;
    S.wheelAng += Math.min(w, 40) * dtReal;
    // the fill flap opens for a reload
    poseMechanism({ pan: S.pan, tilt: S.tilt, pinion: man.pivots.pinion_ratio * S.pan,
      dial: S.phi, wheel_l: S.wheelAng, wheel_r: S.wheelAng, flap: S.flapAngle });
    stepTransit(dt);
    stepBalls(dt);
    stepTargetReset(motionDt);
    stepPlates(dt);
    stepCans(dt);
    stepFx(motionDt);
    flashT = Math.max(0, flashT - Math.max(dt, motionDt * 0.2));      // in slow motion the flash still fades in a moment
    flash.material.opacity = flashT > 0 ? 0.9 : 0;
    flash.scale.setScalar(1 + 6 * flashT);
    gateT = gateT.map((g) => Math.max(0, g - motionDt));
    gates.forEach((m, k) => { m.material.opacity = gateT[k] > 0 ? 0.9 : (S.view !== 'solid' ? 0.25 : 0); });
    // the explode slider eases; parts move along their offsets in their groups
    S.explode += (S.explodeCmd - S.explode) * (1 - Math.exp(-dtReal * 6));
    if (S.explodeCmd === 0 && S.explode < 1e-4) S.explode = 0;
    if (Math.abs(S.explode - (S.lastExplode ?? -1)) > 1e-4 || (S.explode === 0 && S.lastExplode !== 0)) {
      S.lastExplode = S.explode;
      for (const p of parts) p.mesh.position.copy(p.explode).multiplyScalar(0.6 * S.explode);
    }
    // the section: the plane through the pan axis along the barrel; the turret's left half is cut away
    panPivot.updateMatrixWorld(true);
    const nrm = new THREE.Vector3(-1, 0, 0).applyQuaternion(panPivot.getWorldQuaternion(tmpQ));
    clipPlane.setFromNormalAndCoplanarPoint(nrm, panPivot.getWorldPosition(tmpV));
    // airflow arrows
    if (flowGroup.visible) for (const f of flows) for (const h of f.heads) {
      h.userData.u = (h.userData.u + dtReal * 0.35) % 1;
      f.curve.getPointAt(h.userData.u, h.position);
      h.lookAt(world.localToWorld(f.curve.getPointAt(Math.min(1, h.userData.u + 0.01))));
    }
    stepLaser();
    if ((predT += dtReal) > 0.1) { predT = 0; predict(); }
    // the sound: the robot's motors stay quiet here; the turret's flywheels, aim servos (at the servos: the pan servo
    // turns 3 times the turret through its gear) and feed dial
    const servoSpeed = dt > 0 && S.timeScale >= 1 ? Math.hypot(PAN_GEAR * (S.pan - prevAim.pan), S.tilt - prevAim.tilt) / dt : 0;
    prevAim.pan = S.pan; prevAim.tilt = S.tilt;
    sfx.motion({ wheelSpeed: 0, legSpeed: 0, servoSpeed: 0 });
    sfx.turret.frame({ spin: paused ? 0 : S.rpm / fl.rpm, servo: servoSpeed, dial: dialSpeed });
    // the camera glide
    if (cam.to) {
      const k = 1 - Math.exp(-dtReal * 3.2);
      stage.camera.position.lerp(cam.to.pos, k);
      stage.controls.target.lerp(cam.to.target, k);
      if (!S.journey && stage.camera.position.distanceTo(cam.to.pos) < 0.002) cam.to = null;
    }
    layoutCallouts();
    if ((liveT += dtReal) > 0.2) { liveT = 0; paintLive(armed, ready); }
  }

  function paintLive(armed, ready) {
    const n2 = hopperCount();
    reloadBtn.querySelector('small').textContent=`${n2} / ${BALLS}${S.reloading?'':' · R'}`;
    reloadBtn.classList.toggle('empty',n2===0);
    fireInfo.set([['safety line', armed ? (S.journey ? 'demonstration' : 'HELD: armed') : 'open: safe', armed ? 'warn' : 'ok'],
      ['flywheels', `${fmt(S.rpm, 0)} / ${fmt(fl.rpm, 0)} rpm`, ready ? 'ok' : ''],
      ['hopper', `${n2} / ${BALLS} balls`, n2 ? 'ok' : 'fail'],
      ['last ball', S.lastSpeed ? `${S.lastSpeed.toFixed(1)} m/s (chronograph)` : '—']]);
    const down = plates.filter((p) => p.down).length, knocked = cans.filter((c) => c.dyn).length;
    let group = '—';
    if (paper.hits.length > 1) {
      let m = 0;
      for (const a of paper.hits) for (const b of paper.hits) m = Math.max(m, Math.hypot(a[0] - b[0], a[1] - b[1]));
      group = `${(m * 100).toFixed(1)} cm across ${paper.hits.length} hits`;
    }
    live.set([['pan', `${(S.pan / D2R).toFixed(1)}° (servo ${(3 * S.pan / D2R).toFixed(0)}°)`],
      ['tilt', `${(S.tilt / D2R).toFixed(1)}°  (limit -${tiltMax(S.pan).toFixed(1)}°)`],
      ['dial', `${(((S.phi / D2R) % 360) + 360) % 360 | 0}° · ${Math.abs(S.phiCmd - S.phi) > 1e-6 ? 'feeding' : 'parked: spoke over the exit'}`],
      ['laser', S.laserOn ? 'on (Class 2, 650 nm red)' : 'off'],
      ['shots', `${S.shots}`], ['hits', `${S.hits}`], ['plates down', `${down} / ${plates.length}`], ['cans knocked', `${knocked} / ${cans.length}`],
      ['paper group', group]]);
  }

  // ------------------------------------------------------------------------------------------------ enter / exit
  function enter() {
    S.active = true;
    scene.visible = true;
    bar.hidden = false;
    keyHint.hidden = false;
    for (const s of secs) s.hidden = false;
    document.body.classList.add('tb-mode');
    window.addEventListener('keydown', kd);
    window.addEventListener('keyup', ku);
    window.addEventListener('blur', blur);
    prevAim.pan = S.pan; prevAim.tilt = S.tilt;              // no servo whine for where it already points
    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('pointercancel', onCancel);
    stage.controls.addEventListener('start', onCamStart);
    setView(S.view);
    frame('range');
    onLayout();
  }
  function exit() {
    if (S.journey) stopJourney();
    S.active = false;
    scene.visible = false;
    laser.visible = false;
    bar.hidden = true;
    keyHint.hidden = true;
    card.hidden = true;
    callLayer.hidden = true;
    for (const s of secs) s.hidden = true;
    document.body.classList.remove('tb-mode');
    S.arm.clear(); S.trigger = false; S.keys.clear();
    if (S.wasArmed) { S.wasArmed = false; if (S.rpm > 0.05 * fl.rpm) sfx.turret.brake(); }
    S.rpm = 0;
    sfx.turret.stop();
    sfx.turret.slowmo(1);
    if (S.laserOn) { S.laserOn = false; sfx.laser(false); }
    window.removeEventListener('keydown', kd);
    window.removeEventListener('keyup', ku);
    window.removeEventListener('blur', blur);
    canvas.removeEventListener('pointerdown', onDown);
    canvas.removeEventListener('pointerup', onUp);
    canvas.removeEventListener('pointercancel', onCancel);
    pointers.clear();downAt=null;
    stage.controls.removeEventListener('start', onCamStart);
  }
  function summary() {
    const ms = man.masses_g;
    return {
      title: 'Turret on the Orin AGX box',
      rows: [['turret', `${(ms.turret_with_balls / 1000).toFixed(2)} kg with 30 balls`], ['adapter', `${ms.adapter} g PETG on the J501 lid's 4 screw corners`],
        ['TM face', `${man.z_tm - man.roof_z} mm over the roof; intake kept apart from the exhaust`],
        ['launch', `${bl.speed_mps} m/s (${bl.fps} fps nominal; ${bl.cap_fps} fps cap), ${fmt(fl.rpm)} rpm flywheels`], ['fire', 'only while ARM (the safety line) is held']],
    };
  }

  return {
    enter, exit, step, frame, summary, manifest: man,
    get active() { return S.active; },
    // for tests and screenshots
    api: {
      state: S, poseMechanism, get mechanism() { return { scene, world, groups, parts, pocketBalls, pileBalls, path, gates, muzzle, laserOrigin: laserO, refill }; },
      get prediction(){return {points:arcPts.map(p=>p.clone()),arc:arcLine,impact,laser};},
      get targets() { return { plates, cans, resetting: !!targetReset }; }, arm(on) { if (on && !S.reloading) S.arm.add('api'); else S.arm.delete('api'); }, fire(n = 1) { if(!S.reloading)S.queue += n; },
      aim(panDeg, tiltDeg) { S.panCmd = panDeg * D2R; S.tiltCmd = tiltDeg * D2R; S.pan = S.panCmd; S.tilt = S.tiltCmd; panSl.set(panDeg); tiltSl.set(tiltDeg); },
      view: setView, journey: (i = 0) => { startJourney(); if (i && S.journey) gotoStep(i); }, select: (name) => select(parts.find((p) => p.e.part === name) ?? null, true),
      labels(on) { S.labels = on; labelsT.checked = on; }, airflow(on) { S.airflow = on; flowGroup.visible = on; }, antennas(on) { S.antennas = on; antennas.visible = on; },
      reload, resetTargets, explode(v) { if(S.journey)stopJourney(); S.explodeCmd = v; explSl.set(v); },
    },
  };
}
