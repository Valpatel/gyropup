// A 3D Gyropup built from a design: body (compute box), battery tray, hip motors, backward-bending legs that keep the
// wheel under the hip, wheels sized by the chosen motor, lidar in its crown, depth cameras and the DualEye screens.
// Everything is to scale (metres, y up, z forward). Rebuild it whenever the design changes.
import * as THREE from 'three';
import { legPose, effectiveDesign, resolvePart, layout } from './model.js';

const M = 0.001;

function mat(color, extra = {}) {
  return new THREE.MeshPhysicalMaterial({ color, roughness: 0.5, clearcoat: 0.25, clearcoatRoughness: 0.6, ...extra });
}
const DARK = () => mat(0x2f343c, { roughness: 0.7, clearcoat: 0.1 });
const STEEL = () => new THREE.MeshStandardMaterial({ color: 0x8a9099, roughness: 0.35, metalness: 0.6 });
const RUBBER = () => new THREE.MeshStandardMaterial({ color: 0x1d2025, roughness: 0.95 });
function shadowed(o) { o.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } }); return o; }
function box(w, h, d, material, r = 0) {
  const g = new THREE.BoxGeometry(w, h, d, 1, 1, 1);
  return new THREE.Mesh(g, material);
}
function cylX(radius, length, material, seg = 40) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, seg), material);
  m.rotation.z = Math.PI / 2;
  return m;
}

/** Inverse leg: knee interior angle that gives a hip height h (mm) above the axle. */
export function kneeFor(a, b, h) {
  const c = (a * a + b * b - h * h) / (2 * a * b);
  return Math.acos(Math.max(-1, Math.min(1, c)));
}

/**
 * buildRobot(design, catalog, { eyes }) -> { group, setPose(p), info }
 * setPose({ height: 0..1 (crouch..stand), pitch: rad, rollMM: left-right leg difference, wheel: rad })
 */
export function buildRobot(design, catalog, { eyes } = {}) {
  const d = effectiveDesign(design, catalog);
  const g = d.geometry, part = (slot) => resolvePart(d.parts[slot], catalog);
  const color = new THREE.Color(d.character?.color ?? '#f5b82e');
  const a = g.thigh_mm, b = g.shin_mm, r = g.wheel_diameter_mm / 2;
  const hMin = legPose(a, b, g.knee_min_deg).hip_height;
  const hMax = legPose(a, b, g.knee_max_deg).hip_height;
  const L0 = layout(design, catalog);
  const lw = L0.linkW, ld = L0.linkD, motorD = L0.motorD, motorL = L0.motorL, wheelW = L0.wheelW;
  const B = g.body, hipX = L0.hipX, wheelX = L0.wheelX;
  const act = part('leg_actuator');

  const group = new THREE.Group();
  const base = new THREE.Group();                                   // hip axis frame: moves with height, pitches the body
  group.add(base);
  const body = new THREE.Group();
  base.add(body);

  // body: battery tray + compute box, hip axis at y = 0
  const trayH = L0.trayH;
  const tray = box(B.width_mm * M, trayH * M, B.depth_mm * M, DARK());
  tray.position.y = (-25 + trayH / 2) * M;
  const shell = box(B.width_mm * M, B.height_mm * M, B.depth_mm * M, mat(color));
  const bodyBottom = L0.bodyBottom;
  shell.position.y = (bodyBottom + B.height_mm / 2) * M;
  body.add(tray, shell);
  const top = bodyBottom + B.height_mm;

  // hip motor stacks (hip + knee actuators side by side, Diablo style)
  for (const s of [-1, 1]) {
    for (const k of [0, 1]) {
      const m = cylX(motorD / 2 * M, motorL / 2 * M, STEEL());
      m.position.set(s * (B.width_mm / 2 + motorL / 4 + k * motorL / 2) * M, 0, 0);
      body.add(m);
    }
  }

  // lidar in its crown (or on a mast, or under the body)
  const lidar = part('lidar');
  if (lidar) {
    const mount = d.lidar_mount ?? 'top';
    const puck = new THREE.Group();
    const can = new THREE.Mesh(new THREE.CylinderGeometry(0.0515, 0.0515, 0.0717, 48), mat(0x3b3f46, { roughness: 0.4 }));
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.0518, 0.0518, 0.022, 48), new THREE.MeshPhysicalMaterial({ color: 0x0b0d10, roughness: 0.08, clearcoat: 1 }));
    band.position.y = 0.006;
    puck.add(can, band);
    if (mount === 'under') {
      puck.position.y = (-25 - 4) * M - 0.036;
    } else {
      const lift = mount === 'mast' ? 0.05 : 0.008;
      puck.position.y = top * M + lift + 0.036;
      if (mount === 'mast') {
        const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, lift, 16), STEEL());
        mast.position.y = top * M + lift / 2;
        body.add(mast);
      }
      const crown = new THREE.Group();                             // a ring with four arches: the fall guard
      const ringMat = mat(color);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.066, 0.006, 12, 48), ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 0.044;
      crown.add(ring);
      for (let i = 0; i < 4; i++) {
        const arch = new THREE.Mesh(new THREE.TorusGeometry(0.066, 0.005, 10, 24, Math.PI / 2), ringMat);
        arch.rotation.y = (i * Math.PI) / 2;
        arch.rotation.z = Math.PI / 2;
        arch.position.y = -0.022;
        arch.scale.set(1, 1, 1);
        crown.add(arch);
      }
      crown.position.y = puck.position.y - 0.036;
      body.add(crown);
    }
    body.add(puck);
  }

  // depth cameras, front and back
  const cam = (z, flip) => {
    const c = new THREE.Group();
    c.add(box(0.09, 0.025, 0.025, mat(0x2a2d33, { roughness: 0.35 })));
    for (const x of [-0.025, 0, 0.025]) {
      const lens = new THREE.Mesh(new THREE.CircleGeometry(0.0045, 20), new THREE.MeshPhysicalMaterial({ color: 0x050608, roughness: 0.05, clearcoat: 1 }));
      lens.position.set(x, 0, 0.0126);
      c.add(lens);
    }
    c.position.set(0, (bodyBottom + 14) * M, z);
    if (flip) c.rotation.y = Math.PI;
    body.add(c);
  };
  if (part('depth_front')) cam((B.depth_mm / 2 + 13) * M, false);
  if (part('depth_rear')) cam(-(B.depth_mm / 2 + 13) * M, true);

  // eyes: the DualEye module (two 18 mm round screens, 31 mm apart) behind small lenses
  const eyeMeshes = [];
  if (part('eyes')) {
    const bezel = box(0.062, 0.03, 0.004, new THREE.MeshPhysicalMaterial({ color: 0x0b0e12, roughness: 0.3, clearcoat: 1 }));
    const eyeY = (bodyBottom + B.height_mm * 0.62) * M, z = (B.depth_mm / 2 + 2) * M;
    bezel.position.set(0, eyeY, z);
    body.add(bezel);
    for (const [s, tex] of [[-1, eyes?.left?.texture], [1, eyes?.right?.texture]]) {
      const screen = new THREE.Mesh(new THREE.CircleGeometry(0.0095, 40),
        new THREE.MeshBasicMaterial({ map: tex ?? null, color: tex ? 0xffffff : 0x55e9ff }));
      screen.position.set(s * 0.0155, eyeY, z + 0.0022);
      const lens = new THREE.Mesh(new THREE.SphereGeometry(0.0105, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.6),
        new THREE.MeshPhysicalMaterial({ color: 0xffffff, transmission: 1, roughness: 0.02, thickness: 0.004, transparent: true, opacity: 0.35 }));
      lens.rotation.x = Math.PI / 2;
      lens.position.copy(screen.position).add(new THREE.Vector3(0, 0, -0.004));
      body.add(screen, lens);
      eyeMeshes.push(screen);
    }
  }

  // legs
  const legMat = mat(color.clone().multiplyScalar(0.85));
  const legs = [-1, 1].map((s) => {
    const hip = new THREE.Group();
    hip.position.set(s * hipX * M, 0, 0);
    const thigh = box(lw * M, a * M, ld * M, legMat);
    thigh.position.y = -a / 2 * M;
    const knee = new THREE.Group();
    knee.position.y = -a * M;
    const kneeCap = cylX(ld / 2 * M, (lw + 6) * M, STEEL());
    const shin = box(lw * 0.85 * M, b * M, ld * 0.85 * M, legMat);
    shin.position.y = -b / 2 * M;
    const ankle = new THREE.Group();
    ankle.position.set(s * (wheelX - hipX) * M, -b * M, 0);
    const wheel = new THREE.Group();
    const tyre = cylX(r * M, wheelW * M, RUBBER(), 56);
    const hub = cylX(r * 0.62 * M, (wheelW + 2) * M, STEEL(), 40);
    wheel.add(tyre, hub);
    for (let i = 0; i < 3; i++) {
      const spoke = box((wheelW + 3) * M, r * 1.15 * M, 6 * M, DARK());
      spoke.rotation.x = (i * Math.PI) / 3;
      wheel.add(spoke);
    }
    ankle.add(wheel);
    knee.add(kneeCap, shin, ankle);
    hip.add(thigh, knee);
    base.add(hip);
    return { hip, knee, ankle, wheel, side: s };
  });

  shadowed(group);
  eyeMeshes.forEach((m) => { m.castShadow = false; });

  // pose: height 0..1, pitch (rad, body nose-down positive), rollMM (left leg longer +), wheel angle (rad)
  function setPose({ height = 0.65, pitch = 0, rollMM = 0, wheel = 0 } = {}) {
    const h = hMin + (hMax - hMin) * height;
    const hs = [h + rollMM / 2, h - rollMM / 2].map((x) => Math.max(hMin, Math.min(hMax, x)));
    legs.forEach((L, i) => {
      const hh = hs[i], gamma = kneeFor(a, b, hh);
      const alpha = Math.acos(Math.max(-1, Math.min(1, (a * a + hh * hh - b * b) / (2 * a * hh))));
      // legs keep the wheel under the hip in the world frame, so they counter the body pitch
      L.hip.rotation.x = alpha - pitch;
      L.knee.rotation.x = gamma - Math.PI;
      L.ankle.rotation.x = Math.PI - gamma - alpha;              // undo the leg's rotation: the axle frame stays level
      L.wheel.rotation.x = wheel;
    });
    const hAvg = (hs[0] + hs[1]) / 2;
    base.position.y = (r + hAvg) * M;
    base.rotation.x = pitch;
    base.rotation.z = Math.atan2(hs[0] - hs[1], 2 * wheelX);
    return { hipHeightMM: hAvg + r, kneeDeg: kneeFor(a, b, hAvg) * 180 / Math.PI };
  }
  setPose();

  // Replay a MuJoCo state: qpos = [x y z, qw qx qy qz, hip_l knee_l wheel_l, hip_r knee_r wheel_r] in MuJoCo's frame
  // (x forward, y left, z up). This page's frame is x left, y up, z forward, a proper rotation of it: (y, z, x).
  // legs[1] (x > 0) is the robot's left leg.
  function setFromQpos(q) {
    base.position.set(q[1], q[2], q[0]);
    base.quaternion.set(q[5], q[6], q[4], q[3]);
    const sides = [[legs[1], 7], [legs[0], 10]];
    for (const [L, i] of sides) {
      L.hip.rotation.x = q[i];
      L.knee.rotation.x = q[i + 1];
      L.ankle.rotation.x = -(q[i] + q[i + 1]);
      L.wheel.rotation.x = q[i + 2];
    }
    group.position.set(0, 0, 0);
  }
  const heightM = (r + hMax + top + (lidar ? 90 : 0)) * M;
  return { group, setPose, setFromQpos, base, info: { heightM, hMin, hMax, wheelR: r, trackMM: 2 * wheelX } };
}
