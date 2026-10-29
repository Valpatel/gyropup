// Deliberately independent of the 3D hero's imports and rendering code.
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
  const hero = document.querySelector('#robot-preview');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection;
  const manualOnly = () => reducedMotion.matches || connection?.saveData === true;
  const heroLoading = () => hero?.isConnected && hero.dataset.state === 'loading' && hero.dataset.ready !== 'true';
  const STARTUP_SECONDS = 3, HERO_WAIT_MS = 60000, MEDIA_WAIT_MS = 20000;
  let near = false, visible = false, ready = false, buffering = false, failed = false;
  let userPaused = false, manualPlay = false, finished = false, preloadCancelled = false;
  let pendingPlay = false, attempt = 0, mediaTimer, heroTimer;
  let heroWaitExpired = false, heroBypassed = false;
  video.muted = true;

  const wantsPlayback = () => visible && !document.hidden && !failed && !finished &&
    !userPaused && (manualPlay || !manualOnly());
  const wantsDownload = () => !document.hidden && !failed && !finished && !userPaused &&
    ((manualPlay && visible) || (near && !manualOnly() && !preloadCancelled));
  const waitsForHero = () => !video.hasAttribute('src') && heroLoading() && !heroBypassed;
  const queued = () => wantsPlayback() && waitsForHero() && !heroWaitExpired;
  const clearHeroTimer = () => { clearTimeout(heroTimer); heroTimer = undefined; };
  const clearMediaTimer = () => { clearTimeout(mediaTimer); mediaTimer = undefined; };
  const formatTime = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
  const paintTime = () => {
    if (!Number.isFinite(video.duration)) return;
    time.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
    progress.style.width = `${video.duration ? video.currentTime / video.duration * 100 : 0}%`;
  };
  const paint = () => {
    const playing = !video.paused && !finished;
    const waiting = queued();
    const delayed = heroWaitExpired && waitsForHero();
    card.dataset.state = failed ? 'error' : delayed ? 'delayed' : waiting ? 'queued' :
      buffering ? 'buffering' : finished ? 'ended' : playing ? 'playing' : ready || userPaused ? 'paused' : 'idle';
    card.dataset.ready = String(ready && !failed);
    const action = failed ? 'Try again' : delayed ? 'Play now' :
      playing || waiting || (buffering && wantsPlayback()) ? 'Pause' : finished ? 'Replay' : 'Play';
    label.textContent = action;
    icon.textContent = action === 'Pause' ? 'Ⅱ' : action === 'Try again' || action === 'Replay' ? '↻' : '▶';
    toggle.setAttribute('aria-label', failed ? 'Try loading highlights again' : delayed ?
      'Play highlights while the robot is still loading' : `${action} highlights`);
    replay.disabled = !ready || failed;
    status.textContent = failed ? 'The reel couldn’t load. Try again.' : delayed ?
      'The robot is still loading. Play now to load the reel too.' : waiting ?
      'The robot is loading. Your reel will play next.' : buffering ? 'Getting the reel ready for playback…' :
      finished ? 'That’s a glimpse. Explore the simulator for more.' : playing ? 'Playing · no sound' :
      ready || userPaused ? 'Paused · no sound' : manualOnly() ? 'Press play when you’re ready · no sound' :
      'Silent highlights from the workshop.';
    paintTime();
  };
  const pauseMedia = () => {
    attempt++;
    pendingPlay = false;
    video.pause();
  };
  const stop = () => {
    clearHeroTimer(); clearMediaTimer(); buffering = false;
    pauseMedia(); paint();
  };
  const fail = () => {
    failed = true; manualPlay = false;
    stop();
  };
  const waitForMedia = () => {
    if (mediaTimer === undefined) mediaTimer = setTimeout(fail, MEDIA_WAIT_MS);
  };
  const bufferReady = () => {
    if (!ready || video.readyState < 2 || !Number.isFinite(video.duration)) return false;
    const required = Math.min(STARTUP_SECONDS, video.duration - video.currentTime);
    for (let i = 0; i < video.buffered.length; i++) {
      if (video.buffered.start(i) <= video.currentTime + .05 &&
          video.buffered.end(i) - video.currentTime >= required - .05) return true;
    }
    return false;
  };
  const load = () => {
    if (video.hasAttribute('src') || failed) return;
    // Match the actual AVC High 3.1 encoding, not a generic MP4 container.
    const extension = video.canPlayType('video/mp4; codecs="avc1.64001f"') ? 'mp4' :
      video.canPlayType('video/webm; codecs="vp9"') ? 'webm' : null;
    if (!extension) { fail(); return; }
    video.preload = 'auto';
    video.src = `/web/highlights/gyropup-highlights.${extension}`;
    video.load();
  };
  const sync = () => {
    if (video.ended) { finished = true; manualPlay = false; }
    if (!heroLoading()) heroWaitExpired = false;
    if (waitsForHero() && (wantsDownload() || wantsPlayback()) && !heroWaitExpired) {
      // Neither automatic nor deliberate playback competes with pending CAD loads.
      if (heroTimer === undefined) heroTimer = setTimeout(() => {
        heroTimer = undefined;
        if (!waitsForHero()) { sync(); return; }
        heroWaitExpired = true; userPaused = true; manualPlay = false;
        stop();
      }, HERO_WAIT_MS);
      pauseMedia(); paint(); return;
    }
    clearHeroTimer();
    if (!waitsForHero() && wantsDownload()) load();
    if (!wantsPlayback() || waitsForHero() || failed) { stop(); return; }
    if (pendingPlay || !video.paused) return;
    if (!bufferReady()) {
      buffering = true; waitForMedia(); paint(); return;
    }
    clearMediaTimer(); buffering = false;
    const currentAttempt = ++attempt;
    pendingPlay = true;
    video.play().then(() => {
      if (currentAttempt !== attempt) { if (!wantsPlayback()) video.pause(); return; }
      pendingPlay = false;
      if (!wantsPlayback()) video.pause();
      paint();
    }).catch(error => {
      if (currentAttempt !== attempt) return;
      pendingPlay = false;
      if (video.error || error.name === 'NotSupportedError') { fail(); return; }
      // Autoplay policies can still veto a muted clip. A real click can retry.
      userPaused = true; manualPlay = false; stop();
    });
  };
  const playFromStart = (restart = false) => {
    if (heroWaitExpired && heroLoading()) heroBypassed = true;
    if (failed) {
      failed = false; ready = false; buffering = false;
      video.removeAttribute('src'); video.load();
    }
    if (restart || finished || video.ended) video.currentTime = 0;
    finished = false; userPaused = false; manualPlay = true; preloadCancelled = false;
    // A focused, deliberately activated control is itself visible interaction.
    visible = true;
    sync();
  };
  toggle.addEventListener('click', () => {
    if (!failed && (!video.paused || queued() || (buffering && wantsPlayback()))) {
      userPaused = true; manualPlay = false; stop();
    } else playFromStart();
  });
  replay.addEventListener('click', () => playFromStart(true));
  video.addEventListener('loadeddata', () => {
    if (failed) return;
    if (!Number.isFinite(video.duration) || video.duration <= 0) { fail(); return; }
    ready = true; sync(); paint();
  });
  for (const event of ['progress', 'canplay', 'canplaythrough']) video.addEventListener(event, sync);
  video.addEventListener('playing', () => {
    if (!wantsPlayback()) { stop(); return; }
    clearMediaTimer(); ready = true; buffering = false; paint();
  });
  video.addEventListener('pause', paint);
  video.addEventListener('timeupdate', paintTime);
  video.addEventListener('ended', () => {
    finished = true; manualPlay = false; buffering = false;
    clearMediaTimer(); paint();
  });
  video.addEventListener('error', () => { if (video.hasAttribute('src') && video.error) fail(); });
  video.addEventListener('waiting', () => {
    if (!wantsPlayback()) return;
    // Refill the same modest buffer after a real underrun instead of chattering.
    pauseMedia(); buffering = true; waitForMedia(); paint();
  });
  const cancelQueuedPlayback = () => {
    if (card.dataset.state === 'queued' || buffering) { manualPlay = false; preloadCancelled = true; }
    if (manualOnly()) manualPlay = false;
  };
  const preferencesChanged = () => {
    if (manualOnly()) { manualPlay = false; preloadCancelled = true; }
    else if (visible) preloadCancelled = false;
    sync();
  };
  reducedMotion.addEventListener('change', preferencesChanged);
  connection?.addEventListener('change', preferencesChanged);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelQueuedPlayback();
    else if (visible) preloadCancelled = false;
    sync();
  });
  if (hero) {
    new MutationObserver(sync).observe(hero, { attributes: true, attributeFilter: ['data-ready', 'data-state'] });
    // Removing a hero is equivalent to a page that has no hero at all.
    if (hero.parentElement) new MutationObserver(sync).observe(hero.parentElement, { childList: true });
  }
  card.querySelector('.highlight-controls').hidden = false;
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      near = entry.isIntersecting;
      sync();
    }, { rootMargin: '180px 0px' }).observe(card);
    new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) cancelQueuedPlayback();
      visible = entry.isIntersecting;
      if (visible) preloadCancelled = false;
      sync();
    }).observe(card);
  }
  // Without IntersectionObserver the poster remains available for manual play.
  paint();
}
