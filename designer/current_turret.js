// The current public turret, using the same committed, hashed geometry as the
// Orin bench. Its origin is the TM mounting plane; the box and adapter stay on
// the bench. The independent CAD motion reference validates these local frames.
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { buildTurret, ballMesh } from './turret3d.js';

const M = .001, D2R = Math.PI / 180;
const point = p => new THREE.Vector3(p[1] * M, p[2] * M, p[0] * M);
const TO_PAGE = new THREE.Matrix4().set(0,1,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,1).multiply(new THREE.Matrix4().makeScale(M,M,M));
const JOINTS = new Set(['base','pan','tilt','pinion','dial','wheel_l','wheel_r','flap']);

export async function buildCurrentTurret(root, { color = 0xf5b82e } = {}) {
  const source = `${root}exports/sim/turret_box/`, response = await fetch(source + 'manifest.json', { cache:'no-store' });
  if (!response.ok) throw new Error(`Current turret manifest: ${response.status}`);
  const manifest = await response.json(), turret = buildTurret(color), mount = point(manifest.pivots.pan);
  // Keep the effect objects/API while replacing every procedural solid.
  const placeholders=[];
  turret.group.traverse(o => { if(o.isMesh && !o.userData.keep) placeholders.push(o); });
  placeholders.forEach(o => o.removeFromParent());
  turret.pan.position.set(0,0,0);
  turret.tilt.position.copy(point(manifest.pivots.tilt));
  const groups = { base:new THREE.Group(), pan:turret.pan, tilt:turret.tilt };
  turret.group.add(groups.base);
  for(const name of ['pinion','dial','wheel_l','wheel_r','flap']) {
    const group=groups[name]=new THREE.Group();
    group.position.copy(point(manifest.pivots[name]));
    if(name==='pinion') { group.position.sub(mount); turret.group.add(group); }
    else turret.tilt.add(group);
  }
  const loader=new STLLoader(), parts=[];
  await Promise.all(manifest.parts.filter(p=>JOINTS.has(p.group)).map(async entry=>{
    const geometry=await loader.loadAsync(source+entry.file+(entry.sha256?`?v=${entry.sha256}`:''));
    geometry.applyMatrix4(TO_PAGE);
    if(entry.group==='base') geometry.translate(-mount.x,-mount.y,-mount.z);
    if(entry.group==='pinion') { const p=point(manifest.pivots.pinion); geometry.translate(-p.x,-p.y,-p.z); }
    geometry.computeVertexNormals();
    const opacity=entry.opacity??1;
    const material=new THREE.MeshPhysicalMaterial({color:entry.color,roughness:.45,metalness:/#(c9|bf|75|cc)/i.test(entry.color)?.55:.05,
      clearcoat:.15,transparent:opacity<1,opacity,depthWrite:opacity>=1,side:THREE.FrontSide});
    const mesh=new THREE.Mesh(geometry,material); mesh.name=`turret_${entry.name}`;
    mesh.userData.part=entry; mesh.castShadow=opacity>=1; mesh.receiveShadow=true;
    groups[entry.group].add(mesh);
    parts.push({entry,mesh,group:groups[entry.group],explode:point(entry.explode??[0,0,0])});
  }));
  const balls=[];
  for(const [centers,parent] of [[manifest.pockets,groups.dial],[manifest.pile.slice(0,30-manifest.pockets.length),groups.tilt]]) {
    for(const center of centers) {const {g}=ballMesh();g.position.copy(point(center));parent.add(g);balls.push({g,home:g.position.clone(),parent});}
  }
  const currentMuzzle=point(manifest.muzzle),currentLaser=point(manifest.laser);
  let recorded=null,mode='current',exploded=0,wheel=0,dial=0,dialTo=0,spinFor=0,reloadFor=0;
  const originalFlash=turret.flash,originalStep=turret.step;
  function setExplode(value) {
    exploded=Math.max(0,Math.min(1,Number.isFinite(+value)?+value:0));
    for(const p of parts)p.mesh.position.copy(p.explode).multiplyScalar(.6*exploded);
    for(const b of balls){
      const holder=parts.find(p=>p.entry.part===(b.parent===groups.dial?'dial':'hopper'));
      b.g.position.copy(b.home).addScaledVector(holder?.explode??new THREE.Vector3(),.6*exploded);
    }
  }
  function poseMechanism(a) {
    turret.pan.rotation.y=a.pan??turret.pan.rotation.y;
    turret.tilt.rotation.x=-(a.tilt??-turret.tilt.rotation.x);
    groups.pinion.rotation.y=a.pinion??manifest.pivots.pinion_ratio*turret.pan.rotation.y;
    groups.dial.rotation.y=a.dial??dial;
    groups.wheel_l.rotation.y=a.wheel_l??wheel;
    groups.wheel_r.rotation.y=-(a.wheel_r??wheel);
    groups.flap.rotation.x=-(a.flap??0);
  }
  function setSnapshot(next) {
    if(next!=='current'&&next!=='recorded')throw new Error(`Unknown turret presentation: ${next}`);
    if(next==='recorded'&&!recorded)throw new Error('Recorded turret presentation not registered');
    mode=next;setExplode(0);
    const current=mode==='current';
    for(const p of parts)p.mesh.visible=current;
    for(const b of balls)b.g.visible=current;
    if(recorded) for(const group of recorded.groups)group.visible=!current;
    turret.tilt.position.copy(current?point(manifest.pivots.tilt):recorded.tilt);
    turret.muzzle.position.copy(current?currentMuzzle:recorded.muzzle);
    turret.laserOrigin.position.copy(current?currentLaser:recorded.laser);
    turret.flashMesh.position.copy(turret.muzzle.position).add(new THREE.Vector3(0,0,.006));
    turret.muzzle.userData.launchSpeed=current?manifest.mechanics.ball.speed_mps:recorded.launchSpeed;
    turret.laser.visible=false;
  }
  Object.assign(turret,{
    setExplode,poseMechanism,
    registerRecorded(snapshot){recorded=snapshot;setSnapshot(mode);},setSnapshot,
    flash(){setExplode(0);if(mode==='current'){dialTo+=45*D2R;spinFor=.65;}originalFlash();},
    reload(){setExplode(0);if(mode==='current')reloadFor=1;},
    step(dt){
      originalStep(dt);if(mode!=='current')return;
      spinFor=Math.max(0,spinFor-dt);wheel+=Math.min(40,spinFor*120)*dt;
      dial+=Math.min(Math.max(0,dialTo-dial),190*D2R*dt);
      reloadFor=Math.max(0,reloadFor-dt);
      poseMechanism({flap:Math.sin(Math.PI*reloadFor)*110*D2R});
    },
    model:{id:'turret-box-v2',source:source+'manifest.json',parts,groups,mount,manifest},
  });
  Object.defineProperties(turret,{launchSpeed:{get:()=>turret.muzzle.userData.launchSpeed},presentation:{get:()=>mode}});
  setSnapshot('current');
  return turret;
}
