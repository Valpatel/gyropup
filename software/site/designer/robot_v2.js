// Gyropup v2 on the 3D pages: the CAD meshes sim/robot_v2.py exports (exports/sim/v2/rig/), posed exactly as the
// physics model is: every leg joint is a hinge about the robot's y axis, so a link's angle is its reference angle plus
// the joint angles along its chain, the same numbers MuJoCo uses. Frames: CAD and MuJoCo x forward, y left, z up (mm or
// m); this page is (y, z, x) in metres. The right leg is the left one mirrored.
//
//   const robot = await buildRobotV2('../', { eyes });   // { group, base, setPose, setFromQpos, turret, lights, fov, info }
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { buildCurrentTurret } from './current_turret.js';
import { BALL, buildTurret } from './turret3d.js';
import { fiveBar } from './robot_kinematics.js';
import { buildRobotSensors } from './robot_sensors.js';
import { buildCurrentRobot } from './current_robot.js';
import { composeRobotPresentations } from './robot_presentations.js';
import { CURRENT_ROBOT_SOURCE } from './robot_current_source.js';
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

async function buildRigRobotV2(root, { eyes, color = 0xf5b82e, recordedOnly=false, signal } = {}) {
  const geometryResources=new Set(),materialResources=new Set(),lifetime=new AbortController();
  let disposed=false,turret;
  const cancel=()=>lifetime.abort(signal?.reason);signal?.addEventListener('abort',cancel,{once:true});if(signal?.aborted)cancel();
  function dispose(){
    if(disposed)return;disposed=true;lifetime.abort();signal?.removeEventListener('abort',cancel);turret?.dispose?.();
    for(const geometry of geometryResources)geometry.dispose();for(const material of materialResources)material.dispose();geometryResources.clear();materialResources.clear();
  }
  try{
  const base0 = `${root}exports/sim/v2/rig/`;
  const reader=createDataReader((url,options)=>fetch(url,{...options,signal:AbortSignal.any([lifetime.signal,options.signal])})),part=p=>isRecord(p)&&typeof p.file==='string'&&p.file.length>0&&typeof p.name==='string'&&p.name.length>0;
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
  const attachmentNames=['output_adapter',...Array.from({length:9},(_,i)=>'output_screw_'+(i+1))];
  const archivedNames=['adapter_f_l','adapter_f_r','adapter_r_l','adapter_r_r'];
  const archivedEntries=man.body.filter(p=>/^adapter_[fr]_[lr]$/.test(p.name));
  const modernEntries=man.links.upper.filter(p=>/^(output_adapter|output_screw_\d+)$/.test(p.name));
  const complete=(entries,names)=>entries.length===names.length&&names.every(name=>entries.filter(p=>p.name===name).length===1);
  // Readiness requires one complete representation. An absent/partial legacy
  // set must not silently take the modern path and omit every hip adapter.
  if(archivedEntries.length){
    if(!complete(archivedEntries,archivedNames)||modernEntries.length)throw new Error('Incomplete, duplicate or mixed archived output-adapter set');
  }else if(!complete(modernEntries,attachmentNames))throw new Error('Incomplete or duplicate upper-link attachment set');
  const loader = new STLLoader();
  const files = new Set([...man.body.filter(p=>!p.name.startsWith('turret_')).map(p=>p.file), ...Object.values(man.links).flat().map(p=>p.file)]);
  const geo={},loading=new Map();
  function loadGeometry(file){
    if(geo[file])return Promise.resolve(geo[file]);
    if(!loading.has(file))loading.set(file,reader.bytes(base0+file,{label:'Robot part '+file}).then(bytes=>{
      if(disposed)throw new Error('Recorded robot disposed during loading');
      validateSTLBytes(bytes);const g=loader.parse(bytes);geometryResources.add(g);validateGeometry(g);
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
    const material=matCache.get(k);materialResources.add(material);return material;
  };
  const mesh = (p, mirror = false) => {
    if (!geo[p.file]) return null;
    const geometry=mirror?mirrored(geo[p.file]):geo[p.file];geometryResources.add(geometry);
    const m = new THREE.Mesh(geometry, mat(p.color, p.opacity ?? 1));
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
  // The committed interim rig put adapters on the fixed body. Keep that exact
  // snapshot for recorded playback; current presentation uses separately
  // versioned, joint-local attachments. New CAD exports already own them in upper.
  const legacyAdapters=base.children.filter(m=>/^adapter_[fr]_[lr]$/.test(m.name));
  const legHardware={current:[],recorded:legacyAdapters,source:base0+'manifest.json',manifest:null};
  if(legacyAdapters.length&&!recordedOnly){
    const source=base0+'../leg-attachments/manifest.json';
    const attachments=await reader.json(source,{label:'Upper-link attachments',validate:a=>isRecord(a)&&a.schema_version===1&&a.units==='mm'
      &&Array.isArray(a.parts)&&a.parts.every(part)&&complete(a.parts,attachmentNames)});
    const entries=attachments.parts.map(p=>({...p,file:'../leg-attachments/'+p.file}));
    await Promise.all(entries.map(p=>loadGeometry(p.file)));
    for(const [side,leg] of Object.entries(legs))for(const [end,owner] of [['f','upperF'],['r','upperR']])for(const entry of entries){
      const object=mesh(entry,side==='r');object.name=entry.name+'_'+end+'_'+side;
      leg[owner].add(object);legHardware.current.push({name:object.name,entry,mesh:object});
    }
    legHardware.source=source;legHardware.manifest=attachments;
  }else if(!recordedOnly){
    for(const [side,leg] of Object.entries(legs))for(const [end,owner] of [['f','upperF'],['r','upperR']])for(const object of leg[owner].children){
      if(!/^(output_adapter|output_screw_\d+)$/.test(object.name))continue;
      const entry=man.links.upper.find(p=>p.name===object.name);object.name+='_'+end+'_'+side;
      legHardware.current.push({name:object.name,entry,mesh:object});
    }
  }
  function setLegPresentation(mode){
    if(!legacyAdapters.length)return;
    legacyAdapters.forEach(m=>m.visible=mode==='recorded');
    legHardware.current.forEach(p=>p.mesh.visible=mode==='current');
  }
  setLegPresentation(recordedOnly?'recorded':'current');
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
  turret = recordedOnly ? buildTurret(color,{geometry:false}) : await buildCurrentTurret(root, { color });
  if(recordedOnly){
    turret.setExplode=()=>{}; // no current submechanism offsets enter an archive
    turret.setSnapshot=mode=>{if(mode!=='recorded')throw new Error('Archived rig cannot select a current turret');};
    turret.registerRecorded=snapshot=>{
      turret.tilt.position.copy(snapshot.tilt);turret.muzzle.position.copy(snapshot.muzzle);turret.laserOrigin.position.copy(snapshot.laser);
      turret.flashMesh.position.copy(snapshot.muzzle).add(new THREE.Vector3(0,0,.006));turret.muzzle.userData.launchSpeed=snapshot.launchSpeed;
    };
    Object.defineProperties(turret,{presentation:{get:()=> 'recorded'},launchSpeed:{get:()=>turret.muzzle.userData.launchSpeed}});
  }else for(const part of turret.model.parts){geometryResources.add(part.mesh.geometry);materialResources.add(part.mesh.material);}
  const T=man.turret,panP=at(T.pan_mm),tiltP=at(T.tilt_mm);
  turret.group.position.copy(panP);base.add(turret.group);
  let recordedReady=false,recordedLoading=null,presentationRequest=0;
  async function loadRecorded(){
    if(recordedReady)return;
    if(!recordedLoading)recordedLoading=(async()=>{
      const definitions=[...man.body.filter(p=>p.name.startsWith('turret_')),...(T.pan??[]),...(T.tilt??[])];
      await Promise.all(definitions.map(p=>loadGeometry(p.file)));
      if(disposed)throw new Error('Recorded robot disposed during loading');
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

  const {head,lights,fov}=buildRobotSensors(base,man.mounts,eyes);

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
    if(disposed)throw new Error('Recorded robot is disposed');
    if(recordedOnly&&mode!=='recorded')throw new Error('Archived rig requires complete recorded presentation');
    const request=++presentationRequest;setExplode(0);
    // Current takes effect synchronously for firing; archived downloads never
    // replace a newer user choice or discard the existing usable model.
    if(mode==='current'){turret.setSnapshot(mode);setLegPresentation(mode);return;}
    await loadRecorded();if(request===presentationRequest){turret.setSnapshot(mode);setLegPresentation(mode);}
  }
  group.traverse((o) => { if (o.isMesh && o.material?.transparent) o.castShadow = false; });
  setPose();
  if(recordedOnly)await setPresentation('recorded');
  const currentHeightMM = recordedOnly?man.height_mm:T.pan_mm[2] + turret.model.manifest.pivots.tilt[2] + Math.max(...turret.model.parts.filter(p=>p.entry.group==='tilt').map(p=>p.entry.bbox[5]));
  // Sensor effects own their geometry/materials, but eyes textures are external.
  for(const object of [head,...lights.map(p=>p.lens),fov])object.traverse(o=>{if(o.geometry)geometryResources.add(o.geometry);if(o.material)materialResources.add(o.material);});
  for(const o of base.children)if(o.isMesh&&!man.body.some(p=>p.name===o.name)){geometryResources.add(o.geometry);materialResources.add(o.material);}
  const heightM = (wheelR + hMax + Math.max(man.height_mm,currentHeightMM)) * M;
  return { group, base, head, setPose, setFromQpos, turret, lights, fov, legs, legHardware, setExplode, setPresentation, dispose,
           get presentation(){return {mode:turret.presentation,robotId:'gyropup-v2-rig',turretId:turret.presentation==='current'?'turret-box-v2':'v2-recorded-turret',
             bodySource:base0+'manifest.json',legSource:turret.presentation==='current'?legHardware.source:base0+'manifest.json',
             turretSource:turret.presentation==='current'?turret.model.source:base0+'manifest.json'};},
           info: { heightM, hMin, hMax, wheelR, trackMM: man.track_mm, massKg: man.mass_kg, massBasis:recordedOnly?'Recorded v2 physics snapshot; geometry/qpos/mass remain archival.':'recorded v2 physics snapshot; current turret presentation has not rerun full-robot physics', currentTurretMassKg:recordedOnly?null:turret.model.manifest.masses_g.turret_with_balls/1000, massSplit: man.mass_split_kg, deck: man.deck, legRef, v2: true } };
  }catch(error){dispose();throw error;}
}

// The null staging authority deliberately keeps the existing route unchanged
// until reviewed artifact adoption. An explicit current binding never falls
// back to the archive when loading or validation fails.
export async function buildRobotV2(root,{presentationSource=CURRENT_ROBOT_SOURCE,...options}={}){
  if(presentationSource===null)return buildRigRobotV2(root,options);
  const current=await buildCurrentRobot(root,{...options,source:presentationSource});
  return composeRobotPresentations(current,({signal})=>buildRigRobotV2(root,{...options,signal,recordedOnly:true}),{signal:options.signal});
}
