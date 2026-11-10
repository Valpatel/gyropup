// Existing product sensor effects; each complete model supplies its own CAD datums.
import * as THREE from 'three';
const M=.001, at=p=>new THREE.Vector3(p[1]*M,p[2]*M,p[0]*M);

export function buildRobotSensors(base,mounts,eyes){
  // the eyes on the front face (the DualEye board) and the headlights on the side walls, like ears. No two faces in
  // one plane: the bezel straddles the shell's face (1.5 mm in, 1.5 mm out), the screens stand 1 mm proud of the bezel,
  // and each lens is a 3 mm plate half sunk in its pod, so its glowing face is 1.5 mm in front of the pod's
  const em = at(mounts.eyes);
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
  for (const p of mounts.headlights) {
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
    lines.position.copy(at(mounts.camera_front));
    fov.add(lines);
  }
  base.add(fov);

  return {head,lights,fov};
}
