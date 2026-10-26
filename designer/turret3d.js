// The foam-dart turret on Gyropup's head (a stand-in for the separate turret project, built to the head payload
// budget in docs/head-payload.md), and the darts it fires.
//
// Concept from research/turret-and-safety.md: a pan ring on a quick-release plate, a launcher with twin brushless
// flywheels and a solenoid pusher, a drum magazine. Darts leave at 24 m/s (80 fps, the safety cap) and the launcher
// never tilts above horizontal in the world frame.
import * as THREE from 'three';

const M = 0.001;
const mat = (c, o = {}) => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.45, clearcoat: 0.3, ...o });
const DART_SPEED = 24;          // m/s (80 fps)
const MAX_TILT_UP = 0;           // rad: never above horizontal
const MAX_TILT_DOWN = -0.35;

export function buildTurret(color = 0xe8892b) {
  const group = new THREE.Group();                 // sits on the head plate, origin at the plate's top centre
  const plate = new THREE.Mesh(new THREE.BoxGeometry(110 * M, 6 * M, 110 * M), mat(0x2a2d33));
  plate.position.y = 3 * M;
  const latch = new THREE.Mesh(new THREE.BoxGeometry(24 * M, 8 * M, 10 * M), mat(0xff2a6d));   // quick-release latch
  latch.position.set(0, 6 * M, 58 * M);
  const pan = new THREE.Group();
  pan.position.y = 6 * M;
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(48 * M, 52 * M, 14 * M, 40), mat(0x3b3f46));
  ring.position.y = 7 * M;
  const yokeL = new THREE.Mesh(new THREE.BoxGeometry(8 * M, 60 * M, 40 * M), mat(color));
  const yokeR = yokeL.clone();
  yokeL.position.set(-52 * M, 44 * M, 0);
  yokeR.position.set(52 * M, 44 * M, 0);
  const tilt = new THREE.Group();
  tilt.position.y = 58 * M;
  const body = new THREE.Mesh(new THREE.BoxGeometry(92 * M, 56 * M, 150 * M), mat(color));
  const cage = new THREE.Mesh(new THREE.CylinderGeometry(30 * M, 30 * M, 70 * M, 32), mat(0x1d2025));
  cage.rotation.z = Math.PI / 2;
  cage.position.z = 45 * M;
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(9 * M, 9 * M, 80 * M, 24), mat(0x2a2d33));
  barrel.rotation.x = Math.PI / 2;
  barrel.position.z = 115 * M;
  const tip = new THREE.Mesh(new THREE.CylinderGeometry(11 * M, 11 * M, 12 * M, 24), mat(0xff2a6d));
  tip.rotation.x = Math.PI / 2;
  tip.position.z = 152 * M;
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(42 * M, 42 * M, 34 * M, 36), mat(0x3b3f46, { transparent: true, opacity: 0.85 }));
  drum.position.set(0, 46 * M, -25 * M);
  const muzzle = new THREE.Object3D();
  muzzle.position.z = 160 * M;
  const flash = new THREE.Mesh(new THREE.SphereGeometry(14 * M, 12, 8), new THREE.MeshBasicMaterial({ color: 0xfff1a8, transparent: true, opacity: 0 }));
  flash.position.z = 166 * M;
  tilt.add(body, cage, barrel, tip, drum, muzzle, flash);
  pan.add(ring, yokeL, yokeR, tilt);
  group.add(plate, latch, pan);
  group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  flash.castShadow = false;

  let flashT = 0;
  return {
    group, pan, tilt, muzzle,
    setAim(panRad, tiltRad, bodyPitch = 0) {
      pan.rotation.y = panRad;
      // the limit applies in the world frame: the body pitches, so subtract it
      const worldMax = MAX_TILT_UP - bodyPitch, worldMin = MAX_TILT_DOWN - bodyPitch;
      tilt.rotation.x = -Math.max(worldMin, Math.min(worldMax, tiltRad));
    },
    flash() { flashT = 0.06; },
    step(dt) { flashT = Math.max(0, flashT - dt); flash.material.opacity = flashT > 0 ? 0.9 : 0; flash.scale.setScalar(1 + 6 * flashT); },
  };
}

/** Darts in flight and on the ground. */
export function createDarts(scene) {
  const darts = [];
  const bodyGeo = new THREE.CylinderGeometry(6.5 * M, 6.5 * M, 45 * M, 14);
  const tipGeo = new THREE.SphereGeometry(6.8 * M, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  const foam = new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.8 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x2b6cff, roughness: 0.6 });
  const up = new THREE.Vector3(0, 1, 0);

  function fire(muzzle) {
    const g = new THREE.Group();
    const b = new THREE.Mesh(bodyGeo, foam);
    const t = new THREE.Mesh(tipGeo, rubber);
    t.position.y = 22.5 * M;
    g.add(b, t);
    g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
    const pos = new THREE.Vector3(), dir = new THREE.Vector3();
    muzzle.getWorldPosition(pos);
    muzzle.getWorldDirection(dir);
    g.position.copy(pos);
    scene.add(g);
    darts.push({ g, v: dir.multiplyScalar(DART_SPEED), landed: false, age: 0 });
  }

  function step(dt) {
    for (const d of darts) {
      d.age += dt;
      if (!d.landed) {
        d.v.y -= 9.81 * dt;
        d.v.multiplyScalar(1 - 0.35 * dt);           // foam darts slow down quickly in air (rough drag)
        d.g.position.addScaledVector(d.v, dt);
        d.g.quaternion.setFromUnitVectors(up, d.v.clone().normalize());
        if (d.g.position.y <= 0.0065) { d.g.position.y = 0.0065; d.landed = true; d.age = 0; d.g.rotation.set(0, Math.atan2(d.v.x, d.v.z), Math.PI / 2); }
      }
    }
    for (let i = darts.length - 1; i >= 0; i--) {
      if (darts[i].landed && darts[i].age > 12) { scene.remove(darts[i].g); darts.splice(i, 1); }
    }
  }
  function clear() { for (const d of darts) scene.remove(d.g); darts.length = 0; }
  return { fire, step, clear, get count() { return darts.length; } };
}
