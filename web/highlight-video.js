// Deliberately independent of the 3D hero's imports and rendering code.
const card = document.querySelector('.highlight-card');
if (card) {
  const video = card.querySelector('video');
  const toggle = card.querySelector('.highlight-toggle');
  const label = card.querySelector('.highlight-toggle-label');
  const icon = card.querySelector('.highlight-toggle-icon');
  const restart = card.querySelector('.highlight-restart');
  const status = card.querySelector('.highlight-status');
  const time = card.querySelector('.highlight-time');
  const progress = card.querySelector('.highlight-progress span');
  const hero = document.querySelector('#robot-preview');
  const motionQuery = '(prefers-reduced-motion: reduce)';
  const reducedMotion = matchMedia(motionQuery);
  const connection = navigator.connection;
  // WebKit can update a fresh query before delivering changes to retained lists.
  const manualOnly = () => matchMedia(motionQuery).matches || connection?.saveData === true;
  const heroLoading = () => hero?.isConnected && hero.dataset.state === 'loading' && hero.dataset.ready !== 'true';
  const STARTUP_SECONDS = 3, HERO_WAIT_MS = 60000, MEDIA_WAIT_MS = 20000;
  let near = false, visible = false, ready = false, buffering = false, failed = false;
  let userPaused = false, manualPlay = false, finished = false, preloadCancelled = false;
  let pendingPlay = false, attempt = 0, mediaTimer, heroTimer;
  let heroWaitExpired = false, heroBypassed = false, queuedForHero = false;
  let recoveryFrame, recoveryGeneration = 0;
  video.muted = true;

  const withinViewport = (margin = 0) => {
    // Hero completion can run before IntersectionObserver delivers a recent scroll.
    const bounds = card.getBoundingClientRect();
    return bounds.width > 0 && bounds.height > 0 && bounds.bottom > -margin &&
      bounds.top < innerHeight + margin && bounds.right > 0 && bounds.left < innerWidth;
  };
  const wantsPlayback = () => visible && withinViewport() && !document.hidden && !failed && !finished &&
    !userPaused && (manualPlay || !manualOnly());
  const wantsDownload = () => !document.hidden && !failed && !finished && !userPaused &&
    ((manualPlay && visible && withinViewport()) || (near && withinViewport(180) && !manualOnly() && !preloadCancelled));
  const waitsForHero = () => !video.hasAttribute('src') && heroLoading() && !heroBypassed;
  const queued = () => wantsPlayback() && waitsForHero() && !heroWaitExpired;
  // Replay belongs to the persistent primary control after completion. Restart
  // is a different action, useful only while there is an unfinished position.
  const canRestart = () => ready && !failed && !finished && !video.ended && video.currentTime > .05;
  const clearHeroTimer = () => { clearTimeout(heroTimer); heroTimer = undefined; };
  const clearMediaTimer = () => { clearTimeout(mediaTimer); mediaTimer = undefined; };
  const clearFrameRecovery = () => {
    recoveryGeneration++;
    if (recoveryFrame !== undefined) video.cancelVideoFrameCallback?.(recoveryFrame);
    recoveryFrame = undefined;
  };
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
    const restartAvailable = canRestart();
    // A disappearing auxiliary control must not strand keyboard focus on body.
    if (!restartAvailable && document.activeElement === restart) toggle.focus({ preventScroll: true });
    restart.hidden = !restartAvailable;
    restart.disabled = !restartAvailable;
    const statusText = failed ? 'The reel couldn’t load. Try again.' : delayed ?
      'The robot is still loading. Play now to load the reel too.' : waiting ?
      'The robot is loading. Your reel will play next.' : buffering ? 'Getting the reel ready for playback…' :
      finished ? 'That’s a glimpse. Explore the simulator for more.' : playing ? 'Playing · no sound' :
      ready || userPaused ? 'Paused · no sound' : manualOnly() ? 'Press play when you’re ready · no sound' :
      'Silent highlights from the workshop.';
    if (status.textContent !== statusText) status.textContent = statusText;
    paintTime();
  };
  const pauseMedia = () => {
    clearFrameRecovery();
    attempt++;
    pendingPlay = false;
    video.pause();
  };
  const stop = () => {
    clearHeroTimer(); clearMediaTimer(); buffering = false; queuedForHero = false;
    pauseMedia(); paint();
  };
  const fail = () => {
    failed = true; manualPlay = false;
    stop();
  };
  const waitForMedia = () => {
    if (mediaTimer === undefined) mediaTimer = setTimeout(fail, MEDIA_WAIT_MS);
  };
  const watchFrameRecovery = () => {
    clearFrameRecovery();
    if (video.paused || !video.requestVideoFrameCallback) return;
    const generation = recoveryGeneration, playbackAttempt = attempt, source = video.currentSrc, waitingTime = video.currentTime;
    let baseline;
    const frame = (now, metadata) => {
      if (generation !== recoveryGeneration || playbackAttempt !== attempt || source !== video.currentSrc || !wantsPlayback() || video.paused) return;
      recoveryFrame = undefined;
      // A full-buffer WebKit seek can resume frames without another playing
      // event. Require real frame progression; elapsed wall time alone cannot
      // cancel the watchdog for a genuinely frozen decoder.
      if (!video.seeking) {
        if (baseline && metadata.presentedFrames > baseline.presentedFrames &&
            metadata.mediaTime > baseline.mediaTime + .001 && metadata.mediaTime > waitingTime + .001) {
          clearFrameRecovery(); clearMediaTimer(); buffering = false; paint(); return;
        }
        baseline ??= { mediaTime: metadata.mediaTime, presentedFrames: metadata.presentedFrames };
      }
      recoveryFrame = video.requestVideoFrameCallback(frame);
    };
    recoveryFrame = video.requestVideoFrameCallback(frame);
  };
  const enoughBuffered = () => {
    if (!Number.isFinite(video.duration)) return false;
    const required = Math.min(STARTUP_SECONDS, video.duration - video.currentTime);
    for (let i = 0; i < video.buffered.length; i++) {
      if (video.buffered.start(i) <= video.currentTime + .05 &&
          video.buffered.end(i) - video.currentTime >= required - .05) return true;
    }
    return false;
  };
  const bufferReady = () => ready && video.readyState >= 2 && enoughBuffered();
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
    if (queuedForHero && !wantsPlayback()) {
      // Retain intent explicitly: live bounds may already be offscreen before
      // the observer callback arrives, so a derived queued() check is too late.
      manualPlay = false; preloadCancelled = true; queuedForHero = false;
    }
    if (!heroLoading()) heroWaitExpired = false;
    if (waitsForHero() && (wantsDownload() || wantsPlayback()) && !heroWaitExpired) {
      if (wantsPlayback()) queuedForHero = true;
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
    queuedForHero = false;
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
    clearFrameRecovery(); clearMediaTimer(); attempt++; pendingPlay = false;
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
  restart.addEventListener('click', () => { if (canRestart()) playFromStart(true); });
  video.addEventListener('loadeddata', () => {
    if (failed) return;
    if (!Number.isFinite(video.duration) || video.duration <= 0) { fail(); return; }
    ready = true; sync(); paint();
  });
  for (const event of ['progress', 'canplay', 'canplaythrough']) video.addEventListener(event, sync);
  video.addEventListener('seeking', () => {
    clearFrameRecovery(); clearMediaTimer(); attempt++; pendingPlay = false;
    buffering = wantsPlayback();
    if (buffering) waitForMedia();
    paint();
  });
  video.addEventListener('seeked', () => {
    sync();
    if (buffering && wantsPlayback() && !video.paused) watchFrameRecovery();
  });
  video.addEventListener('playing', () => {
    if (!wantsPlayback()) { stop(); return; }
    clearFrameRecovery(); clearMediaTimer(); ready = true; buffering = false; paint();
  });
  video.addEventListener('pause', paint);
  video.addEventListener('timeupdate', paint);
  video.addEventListener('ended', () => {
    finished = true; manualPlay = false; buffering = false;
    clearFrameRecovery(); clearMediaTimer(); paint();
  });
  video.addEventListener('error', () => { if (video.hasAttribute('src') && video.error) fail(); });
  video.addEventListener('waiting', () => {
    if (!wantsPlayback()) return;
    // WebKit can report waiting/low readyState while seeking within a complete
    // buffer. Pausing then interrupts native decode recovery. Refill only when
    // the contiguous bytes themselves are insufficient, regardless of readyState.
    if (!enoughBuffered()) pauseMedia();
    buffering = true; waitForMedia(); watchFrameRecovery(); paint();
  });
  const cancelQueuedPlayback = () => {
    if (queuedForHero || buffering) { manualPlay = false; preloadCancelled = true; }
    queuedForHero = false;
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
    const removalObserver = new MutationObserver(() => {
      if (!hero.isConnected) { removalObserver.disconnect(); sync(); }
    });
    removalObserver.observe(document.body, { childList: true, subtree: true });
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
