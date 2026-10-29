// The landing character uses the same current CAD builder and master audio preferences as the playground.
const preview = document.querySelector('#robot-preview');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
const hint = document.querySelector('#preview-hint');
const inspectButton = document.querySelector('#hero-inspect');
const soundButton = document.querySelector('#hero-sound');
const volumeInput = document.querySelector('#hero-volume');
const REFERENCE_FOV = 34;
async function showRobot() {
  let renderer;
  try {
    const [THREE, { OrbitControls }, { buildRobotV2 }, { createEyes }, { mountTalk }, { createSfx }] = await Promise.all([
      import('three'), import('three/addons/controls/OrbitControls.js'),
      import('../designer/robot_v2.js'), import('../designer/character/eyes.js'),
      import('../designer/character/talk.js'), import('../designer/sfx.js'),
    ]);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.4;
    renderer.domElement.setAttribute('aria-label', 'Gyropup robot: drag to turn');
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0x708c98, 2.8));
    const light = new THREE.DirectionalLight(0xfff4df, 3.5); light.position.set(3, 5, 4); scene.add(light);
    const fill = new THREE.DirectionalLight(0xffffff, 2); fill.position.set(-3, 2, -1); scene.add(fill);
    const eyes = createEyes({ iris: '#70d8cc' });
    const robot = await buildRobotV2('/', { eyes });
    scene.add(robot.group); robot.setPose({ height: .6 }); eyes.draw();
    // Ignore invisible metre-long sensor helpers. The fixed reference camera is
    // shared with the transparent square poster; only FOV changes with aspect.
    robot.group.updateMatrixWorld(true);
    const box = new THREE.Box3();
    robot.group.traverseVisible(object => {
      if (!object.isMesh) return;
      object.geometry.computeBoundingBox();
      box.union(object.geometry.boundingBox.clone().applyMatrix4(object.matrixWorld));
    });
    const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    const camera = new THREE.PerspectiveCamera(REFERENCE_FOV, 1, .01, 100);
    const distance = Math.max(size.y, size.x) / (2 * Math.tan(REFERENCE_FOV * Math.PI / 360)) * 1.24;
    const homePosition = center.clone().add(new THREE.Vector3(1.2, .5, 1.8).normalize().multiplyScalar(distance));
    camera.position.copy(homePosition);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = false; controls.enablePan = false; controls.enableDamping = true;
    controls.autoRotate = false; controls.autoRotateSpeed = .45;
    controls.target.copy(center);
    controls.minPolarAngle = .65; controls.maxPolarAngle = 1.6;
    const resize = () => {
      const w = preview.clientWidth, h = preview.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h;
      camera.fov = 2 * Math.atan(Math.tan(REFERENCE_FOV * Math.PI / 360) * Math.max(1, 1 / camera.aspect)) * 180 / Math.PI;
      camera.updateProjectionMatrix(); controls.update();
    };
    preview.append(renderer.domElement); resize();
    new ResizeObserver(resize).observe(preview);
    // Never hide the poster until a complete first frame actually exists.
    renderer.render(scene, camera);
    preview.dataset.ready = 'true';
    preview.dataset.state = 'ready';
    hint.textContent = finePointer.matches ? 'Drag to turn · hover to peek inside' : 'Drag to turn · tap Peek inside';
    inspectButton.disabled = false; soundButton.disabled = false; volumeInput.disabled = false;

    let visible = true, interacted = false, userOrbited = false, pinned = false, hovering = false, explode = 0;
    const callbacks = [];
    const sfx = createSfx();
    const talk = mountTalk({ stage: { camera, renderer, onFrame: fn => callbacks.push(fn) }, eyes,
      getHead: () => robot.head ?? robot.base, root: '/', dock: false, audio: { enabled: false, volume: sfx.volume } });
    // Keep greetings in the reserved caption band, clear of the detailed turret.
    preview.parentElement.append(document.querySelector('.gp-bubble'));
    const paintSound = () => {
      soundButton.textContent = `Sound ${sfx.enabled ? 'on' : 'off'}`;
      soundButton.setAttribute('aria-pressed', String(sfx.enabled));
      volumeInput.value = String(sfx.volume);
      volumeInput.nextElementSibling.textContent = `${Math.round(sfx.volume * 100)}%`;
      talk.setAudio({ enabled: interacted && sfx.enabled, volume: sfx.volume });
    };
    sfx.onChange(paintSound); paintSound();
    const interact = () => { if (interacted) return; interacted = true; paintSound(); };
    document.addEventListener('pointerdown', interact, { once: true });
    document.addEventListener('keydown', interact, { once: true });
    soundButton.onclick = () => { interact(); sfx.setEnabled(!sfx.enabled); };
    volumeInput.oninput = () => { interact(); sfx.setVolume(+volumeInput.value); };
    const setInspect = () => {
      inspectButton.setAttribute('aria-pressed', String(pinned));
      inspectButton.textContent = pinned ? 'Put me together' : 'Peek inside';
    };
    inspectButton.onclick = () => { pinned = !pinned; setInspect(); };
    preview.addEventListener('pointerenter', event => { if (finePointer.matches && event.pointerType !== 'touch') hovering = true; });
    preview.addEventListener('pointerleave', () => { hovering = false; });
    finePointer.addEventListener('change', () => { hovering = false; });
    controls.addEventListener('start', () => { userOrbited = true; controls.autoRotate = false; hovering = false; });
    reduceMotion.addEventListener('change', () => { if (reduceMotion.matches) controls.autoRotate = false; });
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (!visible) talk.stop();
    }).observe(preview);
    document.addEventListener('visibilitychange', () => { if (document.hidden) talk.stop(); });
    const lines = [
      ['Hi! I’m Gyropup. Ready for a backyard adventure?', 'happy'],
      ['Want to see how I work? Take a peek inside!', 'curious'],
      ['My next big idea? A ridiculously good foam-ball battle.', 'happy'],
      ['I’m still taking shape. Come try my playground!', 'curious'],
    ];
    let line = 0, activeTime = 0, nextLine = 3, previous = performance.now();
    const revealedAt = previous;
    renderer.setAnimationLoop(now => {
      const dt = Math.min((now - previous) / 1000, .05); previous = now;
      if (!visible || document.hidden) return;
      const presented = now - revealedAt > 350;
      if (presented) {
        const target = pinned || hovering ? .45 : 0;
        explode = reduceMotion.matches ? target : explode + (target - explode) * (1 - Math.exp(-dt * 5));
        if (Math.abs(explode - target) < .0001) explode = target;
        robot.setExplode?.(explode);
        controls.autoRotate = !reduceMotion.matches && !userOrbited && !pinned && !hovering;
        if (!reduceMotion.matches) {
          eyes.step(activeTime, dt);
          robot.setPose({ height: .6 + .012 * Math.sin(activeTime * 1.2) });
        }
        activeTime += dt;
        if (activeTime >= nextLine) {
          const [text, mood] = lines[line++ % lines.length];
          talk.announce(text, { mood, hold: 5000 });
          nextLine = activeTime + 35;
        }
      }
      eyes.draw(); controls.update();
      for (const callback of callbacks) callback(activeTime, dt);
      renderer.render(scene, camera);
    });
    // Deterministic export hook for the checked-in poster and geometry assertions.
    // This captures the actual renderer; it does not synthesize a second illustration.
    window.__heroPreview = { renderer, scene, camera, controls, robot, eyes, talk, sfx,
      get inspection() { return { pinned, hovering, amount: explode }; },
      get activity() { return { seconds: activeTime, announcements: line }; },
      captureFrame() { renderer.render(scene, camera); return renderer.domElement.toDataURL('image/png'); },
      capturePoster(size = 1024) {
        const pixelRatio = renderer.getPixelRatio();
        renderer.setPixelRatio(1); renderer.setSize(size, size, false);
        camera.aspect = 1; camera.fov = REFERENCE_FOV; camera.position.copy(homePosition); controls.target.copy(center);
        controls.autoRotate = false; controls.update(); camera.updateProjectionMatrix();
        robot.setExplode?.(0); robot.setPose({ height: .6 }); eyes.draw();
        renderer.render(scene, camera);
        const image = renderer.domElement.toDataURL('image/png');
        renderer.setPixelRatio(pixelRatio); resize();
        return image;
      },
    };
  } catch (error) {
    renderer?.dispose(); renderer?.domElement.remove();
    delete preview.dataset.ready; preview.dataset.state = 'fallback';
    console.warn('3D preview unavailable; showing the CAD poster.', error.message);
    hint.textContent = 'Meet Gyropup in the playground.';
  }
}
showRobot();
const video = document.querySelector('.sim-window video');
new IntersectionObserver(([entry]) => {
  if (entry.isIntersecting && !reduceMotion.matches) video.play().catch(() => {});
  else video.pause();
}).observe(video);
