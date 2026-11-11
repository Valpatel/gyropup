/** Observe the resize and draw lifecycle without changing the stage or checking model fit. */
export function observeTalkViewport({ width, height, settleMs }) {
  const { stage } = window.__talkDemo;
  const { renderer, camera } = stage;
  const canvas = renderer.domElement;
  let resizeAt = null, frameBeforeDraw = null;
  const sameSize = innerWidth === width && innerHeight === height;
  const viewportMatches = () => innerWidth === width && innerHeight === height;
  const dimensionsMatch = () => viewportMatches() && canvas.clientWidth === width && canvas.clientHeight === height
    && canvas.width === Math.floor(width * renderer.getPixelRatio())
    && canvas.height === Math.floor(height * renderer.getPixelRatio())
    && Math.abs(camera.aspect - width / height) < 1e-6
    && (!camera.view?.enabled || camera.view.fullWidth === width && camera.view.fullHeight === height);
  const resized = () => {
    if (!viewportMatches()) return;
    resizeAt = performance.now();
    window.removeEventListener('resize', resized);
  };
  const off = stage.onFrame(() => {
    if (resizeAt === null || performance.now() - resizeAt < settleMs || !dimensionsMatch()) return;
    frameBeforeDraw = renderer.info.render.frame;
    off();
  });
  const stop = () => { window.removeEventListener('resize', resized); off(); };
  window.__portalTalkViewport = {
    stop,
    read(details) {
      const frame = renderer.info.render.frame;
      const ready = frameBeforeDraw !== null && frame > frameBeforeDraw && dimensionsMatch();
      if (!details) return ready;
      return { ready, sameSize, resizeAt, frameBeforeDraw, frame, viewport: [innerWidth, innerHeight],
        css: [canvas.clientWidth, canvas.clientHeight], buffer: [canvas.width, canvas.height],
        aspect: camera.aspect, view: camera.view && { ...camera.view } };
    },
  };
  if (sameSize) resized();
  else window.addEventListener('resize', resized);
}

export function readTalkViewport(details = false) {
  return window.__portalTalkViewport?.read(details) ?? (details ? null : false);
}
