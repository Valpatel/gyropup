// The same CAD model as the simulator, with no backend or physics process required.
const preview = document.querySelector('#robot-preview');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
async function showRobot() {
  try {
    const [THREE, { OrbitControls }, { buildRobotV2 }, { createEyes }] = await Promise.all([
      import('three'), import('three/addons/controls/OrbitControls.js'),
      import('../designer/robot_v2.js'), import('../designer/character/eyes.js'),
    ]);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.4;
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xa89c80, 2.8));
    const light = new THREE.DirectionalLight(0xfff4df, 3.5); light.position.set(3, 5, 4); scene.add(light);
    const fill = new THREE.DirectionalLight(0xffffff, 2); fill.position.set(-3, 2, -1); scene.add(fill);
    const eyes = createEyes({ iris: '#70d8cc' });
    const robot = await buildRobotV2('/', { eyes });
    scene.add(robot.group); robot.setPose({ height: .6 });
    // Hidden FOV and laser helpers extend metres beyond the body; frame only visible meshes.
    robot.group.updateMatrixWorld(true);
    const box = new THREE.Box3();
    robot.group.traverseVisible(object => {
      if (!object.isMesh) return;
      object.geometry.computeBoundingBox();
      box.union(object.geometry.boundingBox.clone().applyMatrix4(object.matrixWorld));
    });
    const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    const camera = new THREE.PerspectiveCamera(34, 1, .01, 100);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = false; controls.enablePan = false; controls.enableDamping = true;
    controls.autoRotate = !reduceMotion.matches; controls.autoRotateSpeed = .45;
    controls.target.copy(center);
    controls.minPolarAngle = .65; controls.maxPolarAngle = 1.6;
    const resize = () => {
      const w = preview.clientWidth, h = preview.clientHeight;
      renderer.setSize(w, h); camera.aspect = w/h;
      const distance = Math.max(size.y, size.x/camera.aspect) / (2*Math.tan(17*Math.PI/180)) * 1.15;
      camera.position.copy(center).add(new THREE.Vector3(1.2,.5,1.8).normalize().multiplyScalar(distance));
      camera.updateProjectionMatrix(); controls.update();
    };
    preview.querySelector('img').hidden = true;
    preview.append(renderer.domElement); resize(); new ResizeObserver(resize).observe(preview);
    document.querySelector('#preview-hint').textContent = 'Drag to say hello · interactive CAD preview';
    let visible = true;
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }).observe(preview);
    controls.addEventListener('start', () => { controls.autoRotate = false; });
    reduceMotion.addEventListener('change', () => { controls.autoRotate = !reduceMotion.matches; });
    renderer.setAnimationLoop(() => { if (!visible || document.hidden) return; controls.update(); renderer.render(scene, camera); });
    preview.dataset.ready = 'true';
  } catch (error) {
    console.warn('3D preview unavailable; showing the CAD illustration.', error.message);
    document.querySelector('#preview-hint').textContent = 'Explore the CAD and simulation in the workshop.';
  }
}
showRobot();
const video = document.querySelector('.sim-window video');
new IntersectionObserver(([entry]) => {
  if (entry.isIntersecting && !reduceMotion.matches) video.play().catch(() => {});
  else video.pause();
}).observe(video);
