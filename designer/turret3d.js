// The foam-ball turret on Gyropup's head (a stand-in, built to the head payload budget in docs/head-payload.md; the
// CAD turret's meshes replace it when they exist), and the balls it fires.
//
// Concept from research/turret-launcher-study.md section 8, as cad/turret.py builds it: a pan ring on a quick-release
// plate, a cradle with twin brushless flywheels fed by a dial under a ball hopper, a 30 mm barrel. Rival-size foam balls
// leave at 21.3 m/s (70 fps, the safety cap for balls) and the launcher never tilts above horizontal in the world frame.
import * as THREE from 'three';

const M = 0.001;
const mat = (c, o = {}) => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.45, clearcoat: 0.3, ...o });
const MAX_TILT_UP = 0;           // rad: never above horizontal
const MAX_TILT_DOWN = -0.35;

/** The ammo, as cad/turret.py and sim/turret.py have it: Rival-size foam balls from a hopper of 30. */
export const BALL = {
  d: 0.0227,        // m (Rival rounds are 22.2-22.8 mm)
  mass: 0.00183,    // kg (Hasbro's own round averages 1.83 g)
  speed: 21.3,      // m/s: 70 fps, the kid-safety cap for balls (65 fps is the default setting)
  fps: 70,
  cd: 0.5,          // drag coefficient (a sphere)
  hopper: 30,
  color: 0xffd21a,
  seam: 0xe0700a,
};
// air drag: deceleration = K v^2 (K = 0.066 per metre: a ball loses about a quarter of its speed over 4 m)
const K_DRAG = 0.5 * 1.2 * BALL.cd * Math.PI * (BALL.d / 2) ** 2 / BALL.mass;
const UP = new THREE.Vector3(0, 1, 0);

const ballGeo = {
  ball: new THREE.SphereGeometry(BALL.d / 2, 20, 14),
  seam: new THREE.TorusGeometry(BALL.d / 2, BALL.d * 0.06, 6, 32),          // the moulding seam: shows the ball turning
  streak: new THREE.CylinderGeometry(BALL.d * 0.4, BALL.d * 0.05, 1, 10, 1, true),
};
const ballMat = {
  foam: new THREE.MeshStandardMaterial({ color: BALL.color, roughness: 0.9 }),
  seam: new THREE.MeshStandardMaterial({ color: BALL.seam, roughness: 0.8 }),
  streak: new THREE.MeshBasicMaterial({ color: 0xffe08a, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false }),
};

/** One foam ball: a sphere with its seam at a random tilt (`g`), and a motion streak to draw behind it (`streak`). */
export function ballMesh() {
  const g = new THREE.Group();
  const seam = new THREE.Mesh(ballGeo.seam, ballMat.seam);
  seam.rotation.set((Math.random() - 0.5) * 0.8, Math.random() * Math.PI, 0);    // about upright, so a spin about the vertical shows
  g.add(new THREE.Mesh(ballGeo.ball, ballMat.foam), seam);
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  const streak = new THREE.Mesh(ballGeo.streak, ballMat.streak);
  streak.visible = false;
  streak.frustumCulled = false;
  return { g, streak };
}

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
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(15 * M, 15 * M, 80 * M, 24), mat(0x2a2d33));   // Ø30, bore = ball + 1.5
  barrel.rotation.x = Math.PI / 2;
  barrel.position.z = 115 * M;
  const tip = new THREE.Mesh(new THREE.CylinderGeometry(16.5 * M, 16.5 * M, 12 * M, 24), mat(0xff2a6d));
  tip.rotation.x = Math.PI / 2;
  tip.position.z = 152 * M;
  // the hopper: a clear tube over the feed dial, with balls showing through
  const hopper = new THREE.Group();
  hopper.position.set(0, 28 * M, -25 * M);
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(51 * M, 51 * M, 64 * M, 36, 1, true),
    mat(0xdfe8f0, { transparent: true, opacity: 0.28, side: THREE.DoubleSide, depthWrite: false }));
  tube.position.y = 32 * M;
  hopper.add(tube);
  const r = BALL.d / 2, inHopper = [[0, 0], ...[0, 1, 2, 3, 4, 5].map((k) => [27 * M * Math.cos(k * Math.PI / 3), 27 * M * Math.sin(k * Math.PI / 3)])];
  for (const [i, [x, z]] of inHopper.entries()) {
    const b = new THREE.Mesh(ballGeo.ball, ballMat.foam);
    b.position.set(x, r + (i ? 0 : 2 * r * 0.85), z);
    hopper.add(b);
  }
  const muzzle = new THREE.Object3D();
  muzzle.position.z = 160 * M;
  // the green aiming laser, beside the barrel (real one: Class 1 or low-power Class 2, never aimed above horizontal)
  const laserBody = new THREE.Mesh(new THREE.CylinderGeometry(7 * M, 7 * M, 40 * M, 16), mat(0x1d2025));
  laserBody.rotation.x = Math.PI / 2;
  laserBody.position.set(-26 * M, -8 * M, 118 * M);
  const laserLens = new THREE.Mesh(new THREE.CircleGeometry(4 * M, 12), new THREE.MeshBasicMaterial({ color: 0x39ff6a }));
  laserLens.position.set(-26 * M, -8 * M, 138.5 * M);
  const laserOrigin = new THREE.Object3D();
  laserOrigin.position.set(-26 * M, -8 * M, 139 * M);
  const flash = new THREE.Mesh(new THREE.SphereGeometry(14 * M, 12, 8), new THREE.MeshBasicMaterial({ color: 0xfff1a8, transparent: true, opacity: 0 }));
  flash.position.z = 166 * M;
  flash.userData.keep = true;                         // an effect, not a stand-in: stays when the CAD turret replaces the rest
  tilt.add(body, cage, barrel, tip, hopper, muzzle, flash, laserBody, laserLens, laserOrigin);
  pan.add(ring, yokeL, yokeR, tilt);
  group.add(plate, latch, pan);
  group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  flash.castShadow = false;
  tube.castShadow = false;

  // the beam and the dot where it lands (in world space, added to the scene by the page)
  // a thin glowing rod, scaled to the beam's length each frame (a 1-pixel line is invisible on most screens)
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(1.2 * M, 1.2 * M, 1, 6, 1, true),
    new THREE.MeshBasicMaterial({ color: 0x39ff6a, transparent: true, opacity: 0.75, blending: THREE.AdditiveBlending, depthWrite: false }));
  const halo = new THREE.Mesh(new THREE.CylinderGeometry(4 * M, 4 * M, 1, 8, 1, true),
    new THREE.MeshBasicMaterial({ color: 0x39ff6a, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false }));
  beam.add(halo);
  const dot = new THREE.Mesh(new THREE.SphereGeometry(10 * M, 12, 8), new THREE.MeshBasicMaterial({ color: 0x8dff9f, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }));
  const dotGlow = new THREE.PointLight(0x39ff6a, 0.4, 0.6);
  dot.add(dotGlow);
  beam.frustumCulled = false;
  const laser = new THREE.Group();
  laser.add(beam, dot);
  const ray = new THREE.Raycaster();
  ray.far = 25;
  const o = new THREE.Vector3(), dir = new THREE.Vector3(), q = new THREE.Quaternion();

  let flashT = 0;
  return {
    group, pan, tilt, muzzle, laser, flashMesh: flash,
    /** Point the beam: from the laser along the barrel to the first thing it meets (`hitObjects`) or the ground. */
    updateLaser(hitObjects = [], on = true) {
      laser.visible = on && group.visible;
      if (!laser.visible) return;
      laserOrigin.getWorldPosition(o);
      laserOrigin.getWorldQuaternion(q);
      dir.set(0, 0, 1).applyQuaternion(q).normalize();
      let len = ray.far;
      if (dir.y < -1e-4) len = Math.min(len, -o.y / dir.y);   // the ground
      ray.set(o, dir);
      const hit = ray.intersectObjects(hitObjects, true)[0];
      if (hit && hit.distance < len) len = hit.distance;
      const end = o.clone().addScaledVector(dir, len);
      beam.position.copy(o).addScaledVector(dir, len / 2);
      beam.scale.set(1, len, 1);
      beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      dot.position.copy(end);
    },
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

/** A cosmetic spin in flight (rad/s about the vertical, ~5 turns a second): matched flywheels leave a real ball with
 *  almost none, but a seam that turns reads as a ball, not a bullet. */
export const BALL_SPIN = 32;

/** Foam balls in flight and on the ground: gravity and air drag, a soft bounce, then a roll to a stop. */
export function createBalls(scene) {
  const balls = [];
  const r = BALL.d / 2, w = new THREE.Vector3(), dq = new THREE.Quaternion();

  function fire(muzzle) {
    const { g } = ballMesh();
    const pos = new THREE.Vector3(), dir = new THREE.Vector3();
    muzzle.getWorldPosition(pos);
    muzzle.getWorldDirection(dir);
    g.position.copy(pos);
    scene.add(g);
    balls.push({ g, v: dir.multiplyScalar(BALL.speed), rolling: false, resting: false, age: 0 });
  }

  function step(dt) {
    for (const b of balls) {
      b.age += dt;
      if (b.resting) continue;
      b.v.y -= 9.81 * dt;
      b.v.addScaledVector(b.v, -K_DRAG * b.v.length() * dt);
      b.g.position.addScaledVector(b.v, dt);
      if (b.g.position.y <= r) {                               // the ground: a soft foam bounce, then rolling
        b.g.position.y = r;
        if (b.v.y < -1) { b.v.y *= -0.3; b.v.x *= 0.5; b.v.z *= 0.5; } else { b.v.y = 0; b.rolling = true; }
      }
      if (b.rolling) b.v.multiplyScalar(Math.max(0, 1 - 4 * dt));            // grass slows a rolling ball
      // turn the ball: spinning in flight, rolling without slipping on the ground
      if (b.rolling) w.crossVectors(UP, b.v).divideScalar(r); else w.set(0, BALL_SPIN, 0);
      const wl = w.length();
      if (wl > 1e-6) b.g.quaternion.premultiply(dq.setFromAxisAngle(w.divideScalar(wl), wl * dt));
      if (b.rolling && b.v.lengthSq() < 0.0025) { b.resting = true; b.age = 0; }
    }
    for (let i = balls.length - 1; i >= 0; i--) {
      if (balls[i].resting && balls[i].age > 12) { scene.remove(balls[i].g); balls.splice(i, 1); }
    }
  }
  function clear() { for (const b of balls) scene.remove(b.g); balls.length = 0; }
  return { fire, step, clear, get count() { return balls.length; } };
}
