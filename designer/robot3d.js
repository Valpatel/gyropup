// A 3D Gyropup built from a design: body (compute box), battery tray, hip motors, backward-bending legs that keep the
// wheel under the hip, wheels sized by the chosen motor, lidar in its crown, depth cameras and the DualEye screens.
// Everything is to scale (metres, y up, z forward). Rebuild it whenever the design changes.
import * as THREE from 'three';
import { legPose, effectiveDesign, resolvePart, layout } from './model.js';
import { buildTurret } from './turret3d.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

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

// ---- sensor fields of view, from the catalog's numbers
export function parseFov(item) {
  const sp = item?.specs ?? {};
  if (sp.fov_h_deg) return { h: sp.fov_h_deg, v: sp.fov_v_deg, range: Math.min(sp.range_max_m ?? 2, 2) };   // drawn to 2 m
  let f = sp.depth_fov_deg ?? sp.fov_deg;
  if (f && typeof f === 'object') f = Object.values(f)[0];
  const m = String(f ?? '').match(/(\d+(?:\.\d+)?)\s*H\s*x\s*(\d+(?:\.\d+)?)\s*V/i);
  if (!m) return null;
  let ideal = sp.ideal_range_m;
  if (ideal && !Array.isArray(ideal)) ideal = Object.values(ideal)[0];
  return { h: +m[1], v: +m[2], range: Math.min(ideal?.[1] ?? 2, 2) };
}

function fovMaterial(color) {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.045, side: THREE.DoubleSide, depthWrite: false });
}

/** A camera's viewing pyramid, looking along +z from its origin. */
function frustum(f, color) {
  const g = new THREE.Group();
  const hw = Math.tan((f.h / 2) * Math.PI / 180) * f.range, hh = Math.tan((f.v / 2) * Math.PI / 180) * f.range;
  const geo = new THREE.BufferGeometry();
  const P = [0, 0, 0, -hw, -hh, f.range, hw, -hh, f.range, hw, hh, f.range, -hw, hh, f.range];
  geo.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  geo.setIndex([0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1]);
  g.add(new THREE.Mesh(geo, fovMaterial(color)));
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.7 }));
  g.add(edges);
  return g;
}

/** A spinning lidar's band: the surface between its lowest and highest beams, all the way round. */
function lidarBand(f, color) {
  const g = new THREE.Group();
  const [lo, hi] = Array.isArray(f.v) ? f.v : [-f.v / 2, f.v / 2];
  for (const a of [lo, hi]) {
    const pts = [new THREE.Vector2(0.05, 0), new THREE.Vector2(f.range * Math.cos(a * Math.PI / 180), f.range * Math.sin(a * Math.PI / 180))];
    const cone = new THREE.Mesh(new THREE.LatheGeometry(pts, 72), fovMaterial(color));
    g.add(cone);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(f.range * Math.cos(lo * Math.PI / 180), 0.004, 6, 96),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35 }));
  ring.rotation.x = Math.PI / 2;
  ring.position.y = f.range * Math.sin(lo * Math.PI / 180);
  g.add(ring);
  return g;
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
export function buildRobot(design, catalog, { eyes, mech } = {}) {
  const d = effectiveDesign(design, catalog);
  const g = d.geometry, part = (slot) => resolvePart(d.parts[slot], catalog);
  const color = new THREE.Color(d.character?.color ?? '#f5b82e');
  const a = g.thigh_mm, b = g.shin_mm, r = g.wheel_diameter_mm / 2;
  const hMin = legPose(a, b, g.knee_min_deg).hip_height;
  const hMax = legPose(a, b, g.knee_max_deg).hip_height;
  const L0 = layout(design, catalog);
  const lw = L0.linkW, ld = L0.linkD, motorD = L0.motorD, motorL = L0.motorL, wheelW = L0.wheelW;
  const B = { width_mm: L0.body.width, depth_mm: L0.body.depth, height_mm: L0.body.height };
  // the CAD's real stack across the hip (exports/mech-layout.json), when the page has it for this design
  const hipX = mech?.hip_y_mm ?? L0.hipX, wheelX = mech?.wheel_y_mm ?? L0.wheelX;
  const motorY = mech ? [mech.stack_mm.hip_motor, mech.stack_mm.knee_motor].map(([a, b]) => (a + b) / 2) : null;
  const FW = L0.frameWidth;
  const act = part('leg_actuator');

  const group = new THREE.Group();
  const base = new THREE.Group();                                   // hip axis frame: moves with height, pitches the body
  group.add(base);
  const body = new THREE.Group();
  base.add(body);

  // body: battery tray + compute box, hip axis at y = 0
  const trayH = L0.trayH;
  // the battery tray: an open frame sized to the pack(s), with the packs visible inside
  const T = L0.tray;
  const tray = new THREE.Group();
  const floor = box((T.width - 4) * M, 6 * M, (T.depth - 4) * M, DARK());
  floor.position.y = (-25 + 3) * M;
  tray.add(floor);
  for (const sx of [-1, 1]) {
    const rail = box(8 * M, (trayH - 2) * M, (T.depth - 4) * M, DARK());
    rail.position.set(sx * (T.width / 2 - 6) * M, (-25 + trayH / 2) * M, 0);
    tray.add(rail);
  }
  if (L0.battery) {
    const [len, wid, hgt] = L0.battery.dims, n = L0.battery.packs;
    const dewalt = /dewalt/i.test(L0.battery.vendor);
    for (let i = 0; i < n; i++) {
      const pack = new THREE.Group();
      const shellMat = mat(dewalt ? 0xfdb913 : 0x2b3a55), capMat = mat(0x1d2025);
      const main = box((wid - 4) * M, (hgt * 0.7) * M, len * M, shellMat);
      main.position.y = hgt * 0.35 * M;
      const cap = box((wid - 2) * M, (hgt * 0.3) * M, len * 0.85 * M, capMat);
      cap.position.y = hgt * 0.85 * M;
      pack.add(main, cap);
      pack.position.set(((i + 0.5) * T.width / n - T.width / 2) * M, (-25 + 6) * M, 0);
      tray.add(pack);
    }
  }
  // the printed shell around the compute box: rounded edges, like the j501 enclosure it wraps
  const shell = new THREE.Mesh(new RoundedBoxGeometry(B.width_mm * M, B.height_mm * M, B.depth_mm * M, 5, 14 * M), mat(color));
  const bodyBottom = L0.bodyBottom;
  shell.position.y = (bodyBottom + B.height_mm / 2) * M;
  body.add(tray, shell);
  const top = bodyBottom + B.height_mm;

  // hip motor stacks (hip + knee actuators side by side, Diablo style)
  for (const s of [-1, 1]) {
    for (const k of [0, 1]) {
      const m = cylX(motorD / 2 * M, (motorL / 2 - 1) * M, STEEL());
      m.position.set(s * (motorY ? motorY[k] : FW / 2 + 3 + motorL / 4 + k * motorL / 2) * M, 0, 0);
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
  const cam = (z, flip, item) => {
    const [cw, ch, cdp] = (item?.specs?.dimensions_mm ?? [90, 25, 25]).map((v) => v * M);
    const c = new THREE.Group();
    c.add(box(cw, ch, cdp, mat(0x2a2d33, { roughness: 0.35 })));
    for (const x of [-cw * 0.28, 0, cw * 0.28]) {
      const lens = new THREE.Mesh(new THREE.CircleGeometry(Math.min(ch, cdp) * 0.18, 20), new THREE.MeshPhysicalMaterial({ color: 0x050608, roughness: 0.05, clearcoat: 1 }));
      lens.position.set(x, 0, cdp / 2 + 0.0006);
      c.add(lens);
    }
    c.position.set(0, (bodyBottom + 14) * M, z);
    if (flip) c.rotation.y = Math.PI;
    body.add(c);
  };
  if (part('depth_front')) cam((B.depth_mm / 2 + 13) * M, false, part('depth_front'));
  if (part('depth_rear')) cam(-(B.depth_mm / 2 + 13) * M, true, part('depth_rear'));

  // headlights: two forward LED pods under the eyes, with real spotlights
  const lights = [];
  const hl = part('headlights');
  if (hl) {
    for (const sx of [-1, 1]) {
      const pod = new THREE.Group();
      const can = new THREE.Mesh(new THREE.CylinderGeometry(17 * M, 19 * M, 22 * M, 24), mat(0x2a2d33, { roughness: 0.35 }));
      can.rotation.x = Math.PI / 2;
      const lens = new THREE.Mesh(new THREE.CircleGeometry(15 * M, 24), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4d6, emissiveIntensity: 1.6 }));
      lens.position.z = 11.2 * M;
      const spot = new THREE.SpotLight(0xfff1d8, 70, 12, 0.42, 0.45, 1.6);   // physical units: a bright LED pod (pages dim it in daylight)
      spot.userData.full = 70;
      spot.position.z = 12 * M;
      const aimAt = new THREE.Object3D();
      aimAt.position.set(0, -0.35, 3);
      spot.target = aimAt;
      pod.add(can, lens, spot, aimAt);
      pod.position.set(sx * (B.width_mm / 2 - 30) * M, (bodyBottom + 22) * M, (B.depth_mm / 2 + 11) * M);
      body.add(pod);
      lights.push({ spot, lens });
    }
  }

  // fields of view (toggle with robot.fov.visible)
  const fov = new THREE.Group();
  fov.visible = false;
  for (const [slot, z, flip] of [['depth_front', (B.depth_mm / 2 + 26) * M, false], ['depth_rear', -(B.depth_mm / 2 + 26) * M, true]]) {
    const f = parseFov(part(slot));
    if (!f) continue;
    const fr = frustum(f, 0x00f0ff);
    fr.position.set(0, (bodyBottom + 14) * M, z);
    if (flip) fr.rotation.y = Math.PI;
    fov.add(fr);
  }
  {
    const f = parseFov(part('lidar'));
    if (f) {
      const lb = lidarBand(f, 0x05ffa1);
      const mount = d.lidar_mount ?? 'top';
      lb.position.y = mount === 'under' ? (-25 - 4) * M - 0.036 : (top + (mount === 'mast' ? 50 : 8)) * M + 0.036;
      fov.add(lb);
    }
  }
  body.add(fov);

  // the turret on the head plate (the head payload), removable
  let turret = null;
  if (d.head_payload?.mass_g) {
    turret = buildTurret(color.getHex());
    turret.group.position.y = top * M;
    body.add(turret.group);
  }

  // eyes: the DualEye module (two 18 mm round screens, 31 mm apart) behind small lenses
  const eyeMeshes = [];
  if (part('eyes')) {
    const bezel = box(0.062, 0.03, 0.004, new THREE.MeshPhysicalMaterial({ color: 0x0b0e12, roughness: 0.3, clearcoat: 1 }));
    const eyeY = (bodyBottom + B.height_mm * 0.62) * M, z = (B.depth_mm / 2 + 3.5) * M;
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
    const hub = cylX(r * 0.62 * M, (wheelW + 8) * M, STEEL(), 40);
    wheel.add(tyre, hub);
    for (let i = 0; i < 3; i++) {
      const spoke = box((wheelW + 16) * M, r * 1.15 * M, 6 * M, DARK());
      spoke.rotation.x = (i * Math.PI) / 3;
      wheel.add(spoke);
    }
    ankle.add(wheel);
    knee.add(kneeCap, shin, ankle);
    const drv = part('motor_driver');                      // a wheel motor driver rides on each shin
    if (drv) {
      const [dl, dw, dh] = [drv.specs?.length_mm ?? 46, drv.specs?.width_mm ?? 46, drv.specs?.height_mm ?? 10];
      const pcb = box((dh + 4) * M, dl * M, dw * M, mat(0x1d5c3a, { roughness: 0.6 }));
      pcb.position.set(s * (lw * 0.43 + dh / 2 + 2) * M, -b * 0.62 * M, 0);
      knee.add(pcb);
    }
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
  function setFromQpos(q, layout) {
    if (turret && layout && layout.turret_pan != null) {
      turret.pan.rotation.y = q[layout.turret_pan];
      turret.tilt.rotation.x = q[layout.turret_tilt];
    }
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
  return { group, setPose, setFromQpos, base, fov, turret, lights, info: { heightM, hMin, hMax, wheelR: r, trackMM: 2 * wheelX } };
}
