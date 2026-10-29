// Deliberately independent of the 3D hero and its imports.
const card = document.querySelector('.highlight-card');
if (card) {
  const video = card.querySelector('video');
  const toggle = card.querySelector('.highlight-toggle');
  const label = card.querySelector('.highlight-toggle-label');
  const icon = card.querySelector('.highlight-toggle-icon');
  const replay = card.querySelector('.highlight-replay');
  const status = card.querySelector('.highlight-status');
  const time = card.querySelector('.highlight-time');
  const progress = card.querySelector('.highlight-progress span');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection;
  const manualOnly = () => reducedMotion.matches || connection?.saveData === true;
  let visible = false, ready = false, loading = false, failed = false;
  let userPaused = false, manualPlay = false, finished = false;
  let pendingPlay = false, attempt = 0, timeout;
  video.muted = true;
  const shouldPlay = () => visible && !document.hidden && !failed && !finished &&
    !userPaused && (manualPlay || !manualOnly());
  const formatTime = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
  const paintTime = () => {
    if (!Number.isFinite(video.duration)) return;
    time.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
    progress.style.width = `${video.duration ? video.currentTime / video.duration * 100 : 0}%`;
  };
  const paint = () => {
    const playing = !video.paused && !finished;
    card.dataset.state = failed ? 'error' : loading ? 'loading' : finished ? 'ended' : playing ? 'playing' : ready ? 'paused' : 'idle';
    card.dataset.ready = String(ready && !failed);
    const action = failed ? 'Try again' : playing || (loading && shouldPlay()) ? 'Pause' : finished ? 'Replay' : 'Play';
    label.textContent = action;
    icon.textContent = action === 'Pause' ? 'Ⅱ' : action === 'Try again' || action === 'Replay' ? '↻' : '▶';
    toggle.setAttribute('aria-label', failed ? 'Try loading highlights again' : `${action} highlights`);
    replay.disabled = !ready || failed;
    status.textContent = failed ? 'The reel couldn’t load. Try again.' : loading ? 'Loading the highlights…' :
      finished ? 'That’s a glimpse. Explore the simulator for more.' : playing ? 'Playing · no sound' :
      ready ? 'Paused · no sound' : manualOnly() ? 'Press play when you’re ready · no sound' : 'Silent highlights from the workshop.';
    paintTime();
  };
  const stop = () => {
    attempt++;
    pendingPlay = false;
    if (ready) { clearTimeout(timeout); loading = false; }
    video.pause();
    paint();
  };
  const fail = () => {
    clearTimeout(timeout);
    failed = true; loading = false; manualPlay = false;
    stop();
  };
  const armTimeout = () => {
    clearTimeout(timeout);
    timeout = setTimeout(fail, 20000);
  };
  const load = () => {
    if (video.hasAttribute('src') || failed) return;
    // Match the actual AVC High 3.1 encoding, not a generic MP4 container.
    const extension = video.canPlayType('video/mp4; codecs="avc1.64001f"') ? 'mp4' :
      video.canPlayType('video/webm; codecs="vp9"') ? 'webm' : null;
    if (!extension) { fail(); return; }
    loading = true;
    video.preload = 'auto';
    video.src = `/web/highlights/gyropup-highlights.${extension}`;
    video.load();
    armTimeout();
    paint();
  };
  const sync = () => {
    if (!shouldPlay()) { stop(); return; }
    load();
    if (failed || pendingPlay || !video.paused) return;
    const currentAttempt = ++attempt;
    pendingPlay = true;
    video.play().then(() => {
      if (currentAttempt !== attempt) { if (!shouldPlay()) video.pause(); return; }
      pendingPlay = false;
      if (!shouldPlay()) video.pause();
      paint();
    }).catch(error => {
      if (currentAttempt !== attempt) return;
      pendingPlay = false;
      if (video.error || error.name === 'NotSupportedError') { fail(); return; }
      // Autoplay policies can still veto a muted clip. A real click can retry.
      userPaused = true; manualPlay = false;
      video.pause();
      paint();
    });
  };
  const playFromStart = (restart = false) => {
    if (failed) {
      failed = false; ready = false; loading = false;
      video.removeAttribute('src');
      video.load();
    }
    if (restart || finished) video.currentTime = 0;
    finished = false; userPaused = false; manualPlay = true;
    // A focused, deliberately activated control is itself visible interaction.
    visible = true;
    sync();
  };
  toggle.addEventListener('click', () => {
    if (!failed && (!video.paused || (loading && shouldPlay()))) {
      userPaused = true; manualPlay = false; stop();
    } else playFromStart();
  });
  replay.addEventListener('click', () => playFromStart(true));
  video.addEventListener('loadeddata', () => {
    if (failed) return;
    if (!Number.isFinite(video.duration) || video.duration <= 0) { fail(); return; }
    clearTimeout(timeout); ready = true; loading = false;
    paint(); sync();
  });
  video.addEventListener('playing', () => {
    if (!shouldPlay()) { stop(); return; }
    clearTimeout(timeout); ready = true; loading = false; paint();
  });
  video.addEventListener('pause', paint);
  video.addEventListener('timeupdate', paintTime);
  video.addEventListener('ended', () => {
    finished = true; manualPlay = false; loading = false;
    clearTimeout(timeout); paint();
  });
  video.addEventListener('error', () => { if (video.hasAttribute('src') && video.error) fail(); });
  video.addEventListener('waiting', () => { if (shouldPlay()) { loading = true; armTimeout(); paint(); } });
  const preferencesChanged = () => {
    if (manualOnly()) { manualPlay = false; stop(); }
    else sync();
    paint();
  };
  reducedMotion.addEventListener('change', preferencesChanged);
  connection?.addEventListener('change', preferencesChanged);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && manualOnly()) manualPlay = false;
    sync();
  });
  card.querySelector('.highlight-controls').hidden = false;
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !manualOnly() && !document.hidden) load();
    }, { rootMargin: '180px 0px' }).observe(card);
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (!visible && manualOnly()) manualPlay = false;
      sync();
    }).observe(card);
  }
  // Without IntersectionObserver the poster remains available for manual play.
  paint();
}
