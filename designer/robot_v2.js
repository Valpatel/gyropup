// Gyropup v2 on the 3D pages: the CAD meshes sim/robot_v2.py exports (exports/sim/v2/rig/), posed exactly as the
// physics model is: every leg joint is a hinge about the robot's y axis, so a link's angle is its reference angle plus
// the joint angles along its chain, the same numbers MuJoCo uses. Frames: CAD and MuJoCo x forward, y left, z up (mm or
// m); this page is (y, z, x) in metres. The right leg is the left one mirrored.
//
//   const robot = await buildRobotV2('../', { eyes });   // { group, base, setPose, setFromQpos, turret, lights, fov, info }
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { buildCurrentTurret } from './current_turret.js';
import { BALL } from './turret3d.js';
import { createDataReader, isRecord, validateSTLBytes, validateGeometry } from './kit/portal-data.js';

const M = 0.001;
const TO_PAGE = new THREE.Matrix4().set(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1).multiply(new THREE.Matrix4().makeScale(M, M, M));
const at = (p) => new THREE.Vector3(p[1] * M, p[2] * M, p[0] * M);          // robot mm -> page m

function mirrored(geo) {
  // y -> -y in the CAD is x -> -x here; swap two corners of every triangle so the faces still point outwards
  const g = geo.clone();
  g.scale(-1, 1, 1);
  const p = g.attributes.position.array;
  for (let i = 0; i < p.length; i += 9) {
    for (let k = 0; k < 3; k++) { const t = p[i + 3 + k]; p[i + 3 + k] = p[i + 6 + k]; p[i + 6 + k] = t; }
  }
  g.attributes.position.needsUpdate = true;
  g.computeVertexNormals();
  return g;
}

// the five-bar in the leg's plane (mm, x forward, z up): motors at (+-D/2, 0), upper links l1, lower links l2
function fiveBar(D, l1, l2) {
  const A = [D / 2, 0], B = [-D / 2, 0];
  const ik = (x, z) => {
    const out = [];
    for (const [P, side] of [[A, 1], [B, -1]]) {
      const vx = x - P[0], vz = z - P[1], r = Math.hypot(vx, vz);
      if (r > l1 + l2 || r < Math.abs(l1 - l2)) return null;
      const a = (l1 * l1 - l2 * l2 + r * r) / (2 * r), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
      const mx = P[0] + (a * vx) / r, mz = P[1] + (a * vz) / r;
      const c1 = [mx - (h * vz) / r, mz + (h * vx) / r], c2 = [mx + (h * vz) / r, mz - (h * vx) / r];
      const C = (c1[0] - c2[0]) * side > 0 ? c1 : c2;
      let ang = Math.atan2(C[1] - P[1], C[0] - P[0]);
      if (side < 0 && ang > 0) ang -= 2 * Math.PI;                    // the rear link's angles run continuously
      out.push({ ang, C });
    }
    return out;
  };
  return { A, B, ik };
}

export async function buildRobotV2(root, { eyes, color = 0xf5b82e } = {}) {
  const base0 = `${root}exports/sim/v2/rig/`;
  const reader=createDataReader(fetch),part=p=>isRecord(p)&&typeof p.file==='string'&&p.file.length>0&&typeof p.name==='string'&&p.name.length>0;
  const positive=n=>Number.isFinite(n)&&n>0,vector=(v,n=3)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
  const validFivebar=f=>isRecord(f)&&['D_mm','l1_mm','l2_mm'].every(k=>positive(f[k]))&&Number.isFinite(f.y_off_mm)
    &&isRecord(f.ref)&&['phi1','phi2','af','aw'].every(k=>Number.isFinite(f.ref[k]))
    &&vector(f.h_range_mm,2)&&f.h_range_mm[0]>0&&f.h_range_mm[1]>f.h_range_mm[0];
  const man=await reader.json(`${base0}manifest.json`,{label:'Robot manifest',validate:m=>isRecord(m)&&Array.isArray(m.body)&&m.body.length>0&&m.body.every(part)
    &&isRecord(m.links)&&['upper','front','wheel_link','wheel'].every(key=>Array.isArray(m.links[key])&&m.links[key].length>0&&m.links[key].every(part))
    &&Object.values(m.links).every(parts=>Array.isArray(parts)&&parts.every(part))&&validFivebar(m.fivebar)
    &&['wheel_r_mm','track_mm','height_mm','mass_kg'].every(key=>positive(m[key]))
    &&isRecord(m.mounts)&&vector(m.mounts.eyes)&&vector(m.mounts.camera_front)&&Array.isArray(m.mounts.headlights)&&m.mounts.headlights.every(p=>vector(p))
    &&isRecord(m.turret)&&['pan_mm','tilt_mm','muzzle_mm'].every(key=>vector(m.turret[key]))
    &&['pan','tilt'].every(key=>Array.isArray(m.turret[key])&&m.turret[key].length>0&&m.turret[key].every(part))});
  const loader = new STLLoader();
  const files = new Set([...man.body.filter(p=>!p.name.startsWith('turret_')).map(p=>p.file), ...Object.values(man.links).flat().map(p=>p.file)]);
  const geo={},loading=new Map();
  function loadGeometry(file){
    if(geo[file])return Promise.resolve(geo[file]);
    if(!loading.has(file))loading.set(file,reader.bytes(base0+file,{label:'Robot part '+file}).then(bytes=>{
      validateSTLBytes(bytes);const g=validateGeometry(loader.parse(bytes));
      g.applyMatrix4(TO_PAGE);g.computeVertexNormals();geo[file]=g;return g;
    }).catch(error=>{loading.delete(file);throw new Error(`Robot mesh ${file}: ${error.message}`);}));
    return loading.get(file);
  }
  await Promise.all([...files].map(loadGeometry));
  const matCache = new Map();
  const mat = (c, opacity = 1) => {
    const k = `${c}/${opacity}`;
    if (!matCache.has(k)) {
      // every rig mesh is a closed solid, so one side is enough: a see-through shell then shows its near outside and its
      // far inside, and never draws a face on top of a part that sits flush against it (no z-fighting there)
      matCache.set(k, new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.45, metalness: /#(c9|9a|8f)/i.test(c) ? 0.5 : 0.05, clearcoat: 0.15,
        transparent: opacity < 1, opacity, depthWrite: opacity >= 1, side: THREE.FrontSide }));
    }
    return matCache.get(k);
  };
  const mesh = (p, mirror = false) => {
    if (!geo[p.file]) return null;
    const m = new THREE.Mesh(mirror ? mirrored(geo[p.file]) : geo[p.file], mat(p.color, p.opacity ?? 1));
    m.castShadow = (p.opacity ?? 1) >= 1;
    m.receiveShadow = true;
    m.name = p.name;
    return m;
  };

  const group = new THREE.Group();
  const base = new THREE.Group();                                // posed by the free joint
  group.add(base);
  for (const p of man.body) { if (!p.name.startsWith('turret_')) { const m = mesh(p); if (m) base.add(m); } }

  // the legs: groups in the same tree as the MJCF (base > upper_f > lower_f; base > upper_r > lower_r > wheel)
  const fv = man.fivebar, ref = fv.ref, l1 = fv.l1_mm * M, l2 = fv.l2_mm * M;
  const fb = fiveBar(fv.D_mm, fv.l1_mm, fv.l2_mm);
  const legs = {};
  for (const [side, sgn] of [['l', 1], ['r', -1]]) {
    const mir = sgn < 0;
    const add = (g, key) => { for (const p of man.links[key]) { const m = mesh(p, mir); if (m) g.add(m); } };
    const upperF = new THREE.Group(), lowerF = new THREE.Group(), upperR = new THREE.Group(), lowerR = new THREE.Group(), wheel = new THREE.Group();
    upperF.position.copy(at([fv.D_mm / 2, sgn * fv.y_off_mm, 0]));
    upperR.position.copy(at([-fv.D_mm / 2, sgn * fv.y_off_mm, 0]));
    lowerF.position.set(0, 0, l1);
    lowerR.position.set(0, 0, l1);
    wheel.position.set(0, 0, l2);
    add(upperF, 'upper'); add(upperR, 'upper'); add(lowerF, 'front'); add(lowerR, 'wheel_link'); add(wheel, 'wheel');
    upperF.add(lowerF); upperR.add(lowerR); lowerR.add(wheel);
    base.add(upperF, upperR);
    legs[side] = { upperF, lowerF, upperR, lowerR, wheel };
  }
  // joint angles -> link rotations: the leg joints turn about the robot's -y (page -x), the wheel about +y (page +x)
  function setLeg(side, mf, kf, mr, kr, w) {
    const L = legs[side];
    L.upperF.rotation.x = -(ref.phi1 + mf);
    L.lowerF.rotation.x = -((ref.af - ref.phi1) + kf);
    L.upperR.rotation.x = -(ref.phi2 + mr);
    L.lowerR.rotation.x = -((ref.aw - ref.phi2) + kr);
    L.wheel.rotation.x = w;
  }
  // a leg at a length (mm) and lean (rad, + = wheel forward), joints consistent with the closed loop
  function legJoints(h, lean = 0) {
    const x = h * Math.sin(lean), z = -h * Math.cos(lean);
    const s = fb.ik(x, z);
    if (!s) return null;
    const [f, r] = s;
    const ang = (P, Q) => Math.atan2(Q[1] - P[1], Q[0] - P[0]);
    return { mf: f.ang - ref.phi1, mr: r.ang - ref.phi2,
             kf: (ang(f.C, [x, z]) - f.ang) - (ref.af - ref.phi1), kr: (ang(r.C, [x, z]) - r.ang) - (ref.aw - ref.phi2) };
  }

  // Current live presentation and recorded physics share the body, but retain
  // their own turret geometry. A recorded ball trajectory belongs to its original
  // muzzle; never move it onto a newer assembly and call that new physics.
  const turret = await buildCurrentTurret(root, { color });
  const T=man.turret,panP=at(T.pan_mm),tiltP=at(T.tilt_mm);
  turret.group.position.copy(panP);base.add(turret.group);
  let recordedReady=false,recordedLoading=null,presentationRequest=0;
  async function loadRecorded(){
    if(recordedReady)return;
    if(!recordedLoading)recordedLoading=(async()=>{
      const definitions=[...man.body.filter(p=>p.name.startsWith('turret_')),...(T.pan??[]),...(T.tilt??[])];
      await Promise.all(definitions.map(p=>loadGeometry(p.file)));
      const fixed=new THREE.Group(),pan=new THREE.Group(),tilt=new THREE.Group();
      fixed.position.copy(panP).negate();
      for(const p of man.body)if(p.name.startsWith('turret_')){const m=mesh(p);if(m)fixed.add(m);}
      for(const p of T.pan??[]){const m=mesh(p);if(m)pan.add(m);}
      for(const p of T.tilt??[]){const m=mesh(p);if(m)tilt.add(m);}
      const laser=tilt.children.find(m=>/_laser$/.test(m.name)),laserPoint=at(T.muzzle_mm).sub(tiltP);
      if(laser){laser.geometry.computeBoundingBox();laser.geometry.boundingBox.getCenter(laserPoint);laserPoint.z=laser.geometry.boundingBox.max.z;}
      turret.group.add(fixed);turret.pan.add(pan);turret.tilt.add(tilt);
      turret.registerRecorded({groups:[fixed,pan,tilt],tilt:tiltP.clone().sub(panP),muzzle:at(T.muzzle_mm).sub(tiltP),laser:laserPoint,launchSpeed:BALL.speed});
      recordedReady=true;
    })().catch(error=>{recordedLoading=null;throw error;});
    await recordedLoading;
  }

  // the eyes on the front face (the DualEye board) and the headlights on the side walls, like ears. No two faces in
  // one plane: the bezel straddles the shell's face (1.5 mm in, 1.5 mm out), the screens stand 1 mm proud of the bezel,
  // and each lens is a 3 mm plate half sunk in its pod, so its glowing face is 1.5 mm in front of the pod's
  const em = at(man.mounts.eyes);
  const head = new THREE.Object3D();head.position.copy(em);base.add(head);
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(0.062, 0.03, 0.003), new THREE.MeshPhysicalMaterial({ color: 0x0b0e12, roughness: 0.3, clearcoat: 1 }));
  bezel.position.copy(em);
  base.add(bezel);
  for (const [s, tex] of [[-1, eyes?.left?.texture], [1, eyes?.right?.texture]]) {
    const screen = new THREE.Mesh(new THREE.CircleGeometry(0.0095, 40), new THREE.MeshBasicMaterial({ map: tex ?? null, color: tex ? 0xffffff : 0x55e9ff }));
    screen.position.copy(em).add(new THREE.Vector3(s * 0.0155, 0, 0.0025));
    base.add(screen);
  }
  const lights = [];
  const lensGeo = (() => {
    const w = 0.044, r = 0.006, sh = new THREE.Shape();             // the SSC1's rounded-square lens, 44 mm
    sh.moveTo(-w / 2 + r, -w / 2);
    sh.lineTo(w / 2 - r, -w / 2); sh.quadraticCurveTo(w / 2, -w / 2, w / 2, -w / 2 + r);
    sh.lineTo(w / 2, w / 2 - r); sh.quadraticCurveTo(w / 2, w / 2, w / 2 - r, w / 2);
    sh.lineTo(-w / 2 + r, w / 2); sh.quadraticCurveTo(-w / 2, w / 2, -w / 2, w / 2 - r);
    sh.lineTo(-w / 2, -w / 2 + r); sh.quadraticCurveTo(-w / 2, -w / 2, -w / 2 + r, -w / 2);
    const g = new THREE.ExtrudeGeometry(sh, { depth: 0.003, bevelEnabled: false, curveSegments: 4 });
    g.translate(0, 0, -0.0015);
    return g;
  })();
  for (const p of man.mounts.headlights) {
    const pod = new THREE.Group();
    const lens = new THREE.Mesh(lensGeo, new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4d6, emissiveIntensity: 1.6 }));
    const spot = new THREE.SpotLight(0xfff1d8, 70, 12, 0.42, 0.45, 1.6);
    spot.userData.full = 70;
    spot.position.z = 0.002;
    const aimAt = new THREE.Object3D();
    aimAt.position.set(0, -0.6, 3);
    spot.target = aimAt;
    pod.add(lens, spot, aimAt);
    pod.position.copy(at(p));
    base.add(pod);
    lights.push({ spot, lens });
  }
  // the front depth camera's field of view (toggle with robot.fov.visible): a RealSense D435, 87 x 58 deg to 2 m
  const fov = new THREE.Group();
  fov.visible = false;
  {
    const r = 2, h = Math.tan((87 / 2) * Math.PI / 180) * r, v = Math.tan((58 / 2) * Math.PI / 180) * r;
    const pts = [[0, 0, 0], [-h, -v, r], [h, -v, r], [h, v, r], [-h, v, r]].map((q) => new THREE.Vector3(...q));
    const g = new THREE.BufferGeometry().setFromPoints([0, 1, 0, 2, 0, 3, 0, 4, 1, 2, 2, 3, 3, 4, 4, 1].map((i) => pts[i]));
    const lines = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.5 }));
    lines.position.copy(at(man.mounts.camera_front));
    fov.add(lines);
  }
  base.add(fov);

  const wheelR = man.wheel_r_mm;
  const [hMin, hMax] = fv.h_range_mm;
  const legRef = [hMin, hMax];
  // live pose (no replay): height 0..1, pitch (rad, nose-down positive), rollMM (left leg longer +), wheel angle (rad)
  function setPose({ height = 0.6, pitch = 0, rollMM = 0, wheel = 0 } = {}) {
    const h = hMin + (hMax - hMin) * height;
    const hs = { l: Math.min(hMax, Math.max(hMin, h + rollMM / 2)), r: Math.min(hMax, Math.max(hMin, h - rollMM / 2)) };
    for (const side of ['l', 'r']) {
      // the legs keep the wheels under the hips in the world, so they lean against the body's pitch
      const j = legJoints(hs[side], pitch);
      if (j) setLeg(side, j.mf, j.kf, j.mr, j.kr, wheel);
    }
    const hAvg = (hs.l + hs.r) / 2;
    base.position.set(0, (wheelR + hAvg) * M, 0);                // the legs lean so the wheels stay under the hips
    base.rotation.set(pitch, 0, Math.atan2(hs.l - hs.r, man.track_mm), 'YXZ');
    return { hipHeightMM: hAvg + wheelR, legMM: hAvg, kneeDeg: null };
  }
  // a MuJoCo state: qpos with the free joint first, the joints by name (qpos_layout)
  function setFromQpos(q, layout) {
    base.position.set(q[1], q[2], q[0]);
    base.quaternion.set(q[5], q[6], q[4], q[3]);
    for (const side of ['l', 'r']) {
      const g = (n) => q[layout[`${n}_${side}`]] ?? 0;
      setLeg(side, g('motor_f'), g('knee_f'), g('motor_r'), g('knee_r'), g('wheel'));
    }
    if (layout.turret_pan != null) {
      turret.pan.rotation.y = q[layout.turret_pan];
      turret.tilt.rotation.x = q[layout.turret_tilt];
    }
    group.position.set(0, 0, 0);
  }
  // Presentation-only offsets: leg/link kinematics and archived qpos remain
  // unchanged. Labels never attach to this exploded illustration.
  const roots=base.children.filter(child=>child!==turret.group&&child!==fov&&child!==head);
  const exploding=roots.map(object=>{
    const home=object.position.clone();
    const direction=home.clone();
    if(object.isMesh){object.geometry.computeBoundingBox();object.geometry.boundingBox.getCenter(direction);}
    direction.y-=.1;
    if(direction.length()<.01)direction.set(0,1,0);
    return {object,home,offset:direction.normalize().multiplyScalar(.075)};
  });
  function setExplode(amount=0){
    const value=Math.max(0,Math.min(1,Number.isFinite(+amount)?+amount:0));
    for(const item of exploding)item.object.position.copy(item.home).addScaledVector(item.offset,value);
    turret.group.position.copy(panP).add(new THREE.Vector3(0,.08*value,0));
    turret.setExplode(value);
  }
  async function setPresentation(mode='current'){
    if(mode!=='current'&&mode!=='recorded')throw new Error(`Unknown robot presentation: ${mode}`);
    const request=++presentationRequest;setExplode(0);
    // Current takes effect synchronously for firing; archived downloads never
    // replace a newer user choice or discard the existing usable model.
    if(mode==='current'){turret.setSnapshot(mode);return;}
    await loadRecorded();if(request===presentationRequest)turret.setSnapshot(mode);
  }
  group.traverse((o) => { if (o.isMesh && o.material?.transparent) o.castShadow = false; });
  setPose();
  const currentHeightMM = T.pan_mm[2] + turret.model.manifest.pivots.tilt[2] + Math.max(...turret.model.parts.filter(p=>p.entry.group==='tilt').map(p=>p.entry.bbox[5]));
  const heightM = (wheelR + hMax + Math.max(man.height_mm,currentHeightMM)) * M;
  return { group, base, head, setPose, setFromQpos, turret, lights, fov, legs, setExplode, setPresentation,
           get presentation(){return {mode:turret.presentation,robotId:'gyropup-v2-rig',turretId:turret.presentation==='current'?'turret-box-v2':'v2-recorded-turret',
             bodySource:base0+'manifest.json',turretSource:turret.presentation==='current'?turret.model.source:base0+'manifest.json'};},
           info: { heightM, hMin, hMax, wheelR, trackMM: man.track_mm, massKg: man.mass_kg, massBasis:'recorded v2 physics snapshot; current turret presentation has not rerun full-robot physics', currentTurretMassKg:turret.model.manifest.masses_g.turret_with_balls/1000, massSplit: man.mass_split_kg, deck: man.deck, legRef, v2: true } };
}
