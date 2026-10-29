// OrbitControls r160 damps rotation and pan, but applies wheel dolly immediately.
// Preserve its orbit/pan/pinch gestures and ease only wheel distance in log space.
export function smoothWheelZoom(controls, element, { speed = 0.25, response = 14 } = {}) {
  const camera = controls.object;
  const offset = camera.position.clone();
  let target = null, lastRadius = null, ownStart = false;
  const radius = () => camera.position.distanceTo(controls.target);
  const clamp = value => Math.max(controls.minDistance, Math.min(controls.maxDistance, value));
  function cancel() { target = null; lastRadius = null; }
  function onStart() { if (!ownStart) cancel(); }
  function wheel(event) {
    if (!controls.enabled || !controls.enableZoom || !camera.isPerspectiveCamera || !Number.isFinite(event.deltaY) || !event.deltaY) return;
    event.preventDefault();
    event.stopImmediatePropagation(); // Prevent a second, immediate dolly from OrbitControls.
    const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight : 1);
    const current = radius();
    // Another camera command may have moved the camera since the previous frame.
    if (lastRadius !== null && Math.abs(current - lastRadius) > Math.max(1e-7, current * 1e-5)) cancel();
    ownStart = true;
    controls.dispatchEvent({ type: 'start' });
    ownStart = false;
    const delta = Math.max(-1200, Math.min(1200, pixels));
    target = clamp((target ?? current) * Math.exp(delta * Math.log(1 / 0.95) * speed / 100));
    lastRadius = current;
    controls.dispatchEvent({ type: 'end' });
  }
  function step(dt) {
    if (target === null) return;
    const current = radius();
    if (!controls.enabled || !controls.enableZoom || current <= 0 ||
        Math.abs(current - lastRadius) > Math.max(1e-7, current * 1e-5)) { cancel(); return; }
    target = clamp(target); // Limits may change when selecting a different model.
    const error = Math.log(target / current);
    const next = Math.abs(error) < 1e-7 ? target : clamp(current * Math.exp(error * (1 - Math.exp(-response * dt))));
    offset.copy(camera.position).sub(controls.target).setLength(next);
    camera.position.copy(controls.target).add(offset);
    lastRadius = next;
    if (next === target) cancel();
  }
  element.addEventListener('wheel', wheel, { capture: true, passive: false });
  controls.addEventListener('start', onStart);
  return { step, cancel, dispose() {
    cancel(); element.removeEventListener('wheel', wheel, true); controls.removeEventListener('start', onStart);
  } };
}
