// The real CAD on the 3D pages: the meshes cad/build.py exports per link (exports/links/), posed by the physics joint
// angles. CAD frame: millimetres, x forward, y left, z up, origin on the hip axis, legs hanging straight down; this
// page's frame is (y, z, x) in metres. The right leg is the left one mirrored.
//
//   const rig = await loadCadRig('../', 'designs/default.json');   // null when the CAD was built from another design
//   base.add(rig.group); rig.set('l', hip, knee, wheel);            // joint angles as in the physics model
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const TO_PAGE = new THREE.Matrix4().set(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1).multiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));

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

export async function loadCadRig(root, designFile) {
  let man;
  try {
    const r = await fetch(`${root}exports/links/manifest.json`, { cache: 'no-store' });
    if (!r.ok) return null;
    man = await r.json();
  } catch { return null; }
  if (man.design !== designFile) return null;
  const loader = new STLLoader();
  const geo = {};
  await Promise.all(Object.values(man.links).flat().map(async (p) => {
    try {                                                       // 'local' meshes (vendor models) exist only where they were built
      const g = await loader.loadAsync(`${root}exports/links/${p.file}`);
      g.applyMatrix4(TO_PAGE);
      g.computeVertexNormals();
      geo[p.file] = g;
    } catch { if (!p.local) console.warn('missing mesh', p.file); }
  }));
  for (const k of Object.keys(man.links)) man.links[k] = man.links[k].filter((p) => geo[p.file]);
  const a = man.thigh_mm / 1000, b = man.shin_mm / 1000, r = man.crank_r_mm / 1000;
  const beta = ((man.lever_beta_deg ?? 0) * Math.PI) / 180;
  const x0 = r * Math.cos(beta), z0 = r * Math.sin(beta);       // the crank pin at the zero pose (CAD x forward, z up)
  const mat = (c) => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.42, metalness: /#(9a|b8|c9|d6|5a)/i.test(c) ? 0.55 : 0.05, clearcoat: 0.2 });
  const mesh = (p, side) => {
    const m = new THREE.Mesh(side === 'r' ? mirrored(geo[p.file]) : geo[p.file], mat(p.color));
    m.castShadow = m.receiveShadow = true;
    m.name = `${p.name}${side ? `_${side}` : ''}`;
    return m;
  };
  const group = new THREE.Group();
  for (const p of man.links.body) {                            // fixed to the body; the leg-module parts on both sides
    for (const side of p.side ? ['l', 'r'] : [null]) group.add(mesh(p, side));
  }
  const legs = {};
  for (const side of ['l', 'r']) {
    const add = (parent, link, offset = [0, 0, 0]) => {
      const holder = new THREE.Group();
      holder.position.set(...offset);
      for (const p of man.links[link]) holder.add(mesh(p, side));
      parent.add(holder);
    };
    const thigh = new THREE.Group();                            // turns about the hip axis
    add(thigh, 'thigh');
    const knee = new THREE.Group();                             // the knee pin, a thigh-length down the thigh
    knee.position.set(0, -a, 0);
    add(knee, 'shin', [0, a, 0]);
    const wheel = new THREE.Group();                            // the axle, a shin-length down the shin
    wheel.position.set(0, -b, 0);
    add(wheel, 'wheel', [0, a + b, 0]);
    knee.add(wheel);
    thigh.add(knee);
    const crank = new THREE.Group();                            // on the knee motor's output: turns by hip + knee
    add(crank, 'crank');
    const rod = new THREE.Group();                              // the push-rod: rides on the crank pin, parallel to the thigh
    add(rod, 'rod', [0, -z0, -x0]);
    group.add(thigh, crank, rod);
    legs[side] = { thigh, knee, wheel, crank, rod };
  }
  // the turret's meshes, each set re-centred on its pivot (pan axis, tilt axis), for robot3d to put in its turret's groups
  let turret = null;
  if (man.turret && (man.links.turret_pan?.length || man.links.turret_tilt?.length)) {
    const pv = (p) => new THREE.Vector3(p[1] / 1000, p[2] / 1000, p[0] / 1000);       // robot mm -> page m
    const pan = pv(man.turret.pan_mm), tilt = pv(man.turret.tilt_mm);
    const set = (link, origin) => {
      const g = new THREE.Group();
      for (const p of man.links[link] ?? []) { const m = mesh(p, null); m.position.sub(origin); g.add(m); }
      return g;
    };
    turret = { base: set('turret_base', new THREE.Vector3()), pan: set('turret_pan', pan), tilt: set('turret_tilt', tilt),
               panPivot: pan, tiltPivot: tilt, muzzle: pv(man.turret.muzzle_mm) };
  }
  group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return {
    group, manifest: man, turret,
    /** Joint angles as in the physics model (radians, right-hand rule about the robot's +y). */
    set(side, hip, knee, wheel = 0) {
      const L = legs[side];
      L.thigh.rotation.x = hip;
      L.knee.rotation.x = knee;
      L.wheel.rotation.x = wheel;
      const th = hip + knee;
      L.crank.rotation.x = th;
      L.rod.position.set(0, -x0 * Math.sin(th) + z0 * Math.cos(th), x0 * Math.cos(th) + z0 * Math.sin(th));   // the crank pin
      L.rod.rotation.x = hip;
    },
  };
}
