/** Exercise the published highlights player and real moving decoded pixels. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium, webkit, expect } from '@playwright/test';
import { parseHTML } from 'linkedom';
import { assertHighlightControls } from './highlight-control-contract.mjs';

const base = (process.env.SITE_URL || 'http://127.0.0.1:8899').replace(/\/$/, '');
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-highlight-video';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browserLabel = engine === webkit ? 'webkit' : process.env.PLAYWRIGHT_CHANNEL === 'chrome' ? 'chrome' : 'chromium';
const viewports = [[320, 568], [360, 800], [375, 812], [390, 844], [393, 852], [412, 915], [430, 932],
  [568, 320], [667, 375], [844, 390], [932, 430], [768, 1024], [1440, 900]];
const browser = await engine.launch({ headless: true, ...(engine === chromium ? {
  channel: process.env.PLAYWRIGHT_CHANNEL === 'chrome' ? 'chrome' : undefined,
  args: ['--no-sandbox'],
} : {}) });
const contextOptions = { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' };
const context = await browser.newContext(contextOptions);
const errors = [], cases = [], pages = [];
const movieURL = url => /\/web\/highlights\/gyropup-highlights\.(mp4|webm)$/.test(url.pathname);
const record = message => { cases.push(message); console.log('PASS ' + message); };
await mkdir(out, { recursive: true });
const initialPreferences = () => {
  localStorage.setItem('gyropup.probe', 'off');
  sessionStorage.setItem('gyropup.prototype-notice', '2026-10-29-v1');
};
await context.addInitScript(initialPreferences);
const json = async path => { const response = await context.request.get(base + path); assert.ok(response.ok(), path); return response.json(); };
const version = await json('/version.json');

async function pageFor({ motion = 'reduce', saveData = false, heroMode = 'failed', isolatedClock = false, setup = async () => {} } = {}) {
  // Playwright clocks belong to a BrowserContext, not just a Page. Reinstalling
  // in a reused WebKit context hit an undefined __pwClock controller before
  // navigation, and otherwise leaks virtual time into later unrelated cases.
  const pageContext = isolatedClock ? await browser.newContext(contextOptions) : context;
  if (isolatedClock) await pageContext.addInitScript(initialPreferences);
  const page = await pageContext.newPage(); pages.push(page);
  page.setDefaultTimeout(30000);
  page.on('pageerror', error => errors.push(error.message));
  page.mediaRequests = [];
  page.on('request', request => { if (movieURL(new URL(request.url()))) page.mediaRequests.push(request.url()); });
  await page.emulateMedia({ reducedMotion: motion });
  // Controlled hero states isolate the player; the integration harness loads real CAD.
  let heroFixtureHits = 0;
  await page.route(url => url.pathname === '/web/landing.js', route => {
    heroFixtureHits++;
    return route.fulfill({ contentType: 'text/javascript', body: heroMode === 'held' ?
      '// Intentionally pending hero fixture.' : 'throw new Error("Intentional hero failure in highlights test");' });
  });
  if (heroMode === 'missing') await page.route(base + '/', async route => {
    const response = await route.fetch();
    const { document } = parseHTML(await response.text());
    document.querySelector('#robot-preview').remove();
    for (const script of document.querySelectorAll('script')) if (script.textContent.includes('/web/landing.js')) script.remove();
    await route.fulfill({ response, body: document.toString() });
  });
  if (saveData) await page.addInitScript(() => {
    Object.defineProperty(navigator, 'connection', { value: { saveData: true, addEventListener() {} }, configurable: true });
  });
  await setup(page);
  await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
  await page.locator('.highlight-controls').waitFor({ state: 'visible' });
  await page.addStyleTag({ content: 'html{scroll-behavior:auto!important}' });
  await page.evaluate(() => document.fonts.ready);
  if (heroMode === 'missing') {
    assert.equal(await page.locator('#robot-preview').count(), 0, 'Missing-hero fixture really removes the hero');
    assert.equal(heroFixtureHits, 0, 'Missing-hero fixture removes its bootstrap as well');
  } else {
    await expect.poll(() => heroFixtureHits).toBe(1);
    await page.waitForFunction(expected => document.querySelector('#robot-preview').dataset.state === expected,
      heroMode === 'held' ? 'loading' : 'fallback');
    assert.notEqual(await page.locator('#robot-preview').getAttribute('data-ready'), 'true', 'The hero fixture did not accidentally load real CAD');
  }
  assert.equal(await page.locator('#highlight-video').getAttribute('src'), null, 'Initial page view does not assign a movie');
  assert.equal(page.mediaRequests.length, 0, 'Initial page view does not fetch a movie');
  return page;
}
async function show(page) {
  await page.locator('.highlight-card').evaluate(el => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
  // Let both IntersectionObservers run before asserting deliberate non-playback.
  await page.waitForTimeout(200);
}
async function waitPlaying(page) {
  await page.waitForFunction(() => {
    const host = document.querySelector('.highlight-card'), v = host.querySelector('video');
    if (host.dataset.state === 'error') throw new Error(host.querySelector('.highlight-status').textContent);
    return !v.paused && v.readyState >= 2 && v.currentTime > .15;
  });
}
async function assertMoving(page) {
  await waitPlaying(page);
  const evidence = await page.locator('#highlight-video').evaluate(async v => {
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 90;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const sample = () => {
      // Exclude edge titles/timecodes so changing labels cannot prove motion.
      ctx.drawImage(v, v.videoWidth * .15, v.videoHeight * .22, v.videoWidth * .7, v.videoHeight * .58, 0, 0, 160, 90);
      return ctx.getImageData(0, 0, 160, 90).data;
    };
    const before = sample(), time = v.currentTime, frames = v.getVideoPlaybackQuality().totalVideoFrames;
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('No advancing decoded video frame')), 10000);
      const frame = () => {
        if (v.currentTime > time + .7) { clearTimeout(timeout); resolve(); }
        else v.requestVideoFrameCallback(frame);
      };
      v.requestVideoFrameCallback(frame);
    });
    const after = sample(); let difference = 0;
    for (let i = 0; i < before.length; i += 4) for (let c = 0; c < 3; c++) difference += Math.abs(before[i + c] - after[i + c]);
    return { beforeTime: time, afterTime: v.currentTime, beforeFrames: frames, afterFrames: v.getVideoPlaybackQuality().totalVideoFrames, meanPixelDifference: difference / (160 * 90 * 3) };
  });
  assert.ok(evidence.afterFrames > evidence.beforeFrames, 'Decoded frame count advances');
  assert.ok(evidence.meanPixelDifference > .15, `Model region must move: ${JSON.stringify(evidence)}`);
  return evidence;
}
const paused = page => page.waitForFunction(() => document.querySelector('#highlight-video').paused);
async function hide(page) { await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' })); await paused(page); }
async function visibility(page, hidden) {
  // Deterministic lifecycle signal; headless browsers do not reliably hide tabs.
  await page.evaluate(hidden => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    document.dispatchEvent(new Event('visibilitychange'));
  }, hidden);
}
async function releaseHero(page, state = 'ready') {
  await page.locator('#robot-preview').evaluate((hero, state) => {
    if (state === 'ready') hero.dataset.ready = 'true';
    hero.dataset.state = state;
  }, state);
}
async function noMovie(page, message) {
  await page.waitForTimeout(200);
  assert.equal(page.mediaRequests.length, 0, message);
  assert.equal(await page.locator('#highlight-video').getAttribute('src'), null, message);
}
try {
  for (const [extension, type] of [['mp4', 'video/mp4'], ['webm', 'video/webm'], ['webp', 'image/webp']]) {
    const response = await context.request.head(`${base}/web/highlights/gyropup-highlights.${extension}`);
    assert.ok(response.ok()); assert.match(response.headers()['content-type'], new RegExp('^' + type));
  }
  const page = await pageFor(); await show(page);
  await assertHighlightControls(page, 'Play');
  assert.equal(page.mediaRequests.length, 0, 'Reduced motion does not preload a movie');
  const poster = await page.locator('.highlight-poster').evaluate(async image => {
    await image.decode(); return { width: image.naturalWidth, height: image.naturalHeight };
  });
  assert.deepEqual(poster, { width: 1280, height: 720 }, 'Poster decodes at the same 16:9 dimensions as the reel');
  assert.match(await page.locator('#highlight-description').innerText(), /archived leg-rig physics and historical static deformation/);
  const footageHref = await page.locator('.highlight-footage').getAttribute('href');
  const footageResponse = await context.request.get(new URL(footageHref, base).href);
  assert.ok(footageResponse.ok(), 'About the footage reaches its published document');
  assert.match(await footageResponse.text(), /Landing highlights reel/);
  await page.locator('.highlight-card').screenshot({ path: `${out}/${browserLabel}-poster.png` });
  record('WebP poster has the correct HTTP MIME type and decodes at 1280×720');
  await page.locator('.highlight-toggle').click();
  const motionEvidence = await assertMoving(page);
  const media = await page.locator('#highlight-video').evaluate(v => ({
    duration: v.duration, width: v.videoWidth, height: v.videoHeight, muted: v.muted,
    h264: v.canPlayType('video/mp4; codecs="avc1.64001f"'), vp9: v.canPlayType('video/webm; codecs="vp9"'), source: v.currentSrc,
  }));
  assert.ok(Math.abs(media.duration - 22) < .1, 'Published reel is 22 seconds');
  assert.equal(media.width, 1280); assert.equal(media.height, 720); assert.equal(media.muted, true);
  assert.ok(media.source.endsWith(media.h264 ? '.mp4' : '.webm'));
  assert.equal(new Set(page.mediaRequests.map(url => new URL(url).pathname)).size, 1, 'Only the chosen encoding is fetched');
  await page.waitForFunction(() => {
    const v = document.querySelector('#highlight-video');
    return Array.from({ length: v.buffered.length }, (_, i) => [v.buffered.start(i), v.buffered.end(i)])
      .some(([start, end]) => start <= v.currentTime && end - v.currentTime >= 3);
  });
  const pausedByDecoderWait = await page.locator('#highlight-video').evaluate(v => {
    // A decoder/seek can transiently lower readyState without losing buffered
    // bytes. The synthetic event isolates that distinction; real replay follows.
    Object.defineProperty(v, 'readyState', { configurable: true, get: () => 1 });
    v.dispatchEvent(new Event('waiting'));
    const paused = v.paused;
    delete v.readyState;
    return paused;
  });
  assert.equal(pausedByDecoderWait, false, 'A full buffer with transient decoder waiting must not force a pause');
  await page.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'playing');
  await page.locator('.highlight-toggle').click(); await paused(page);
  await assertHighlightControls(page, 'Play', { restart: true });
  record('Hero failure independence, one encoding, moving decoded pixels, and uninterrupted full-buffer decoder waiting');

  for (const [width, height] of viewports) {
    await page.setViewportSize({ width, height }); await show(page);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'No horizontal overflow');
    const screen = await page.locator('.highlight-screen').boundingBox();
    assert.ok(Math.abs(screen.width / screen.height - 16 / 9) < .01, 'Screen preserves 16:9');
    assert.ok(screen.x >= 0 && screen.x + screen.width <= width, 'Frame stays inside viewport');
    assert.ok(await page.locator('#highlight-description').evaluate(el => parseFloat(getComputedStyle(el).fontSize) >= 12), 'Footage context stays readable independently of source captions');
    for (const selector of ['.highlight-toggle', '.highlight-restart', '.highlight-footage']) {
      const bounds = await page.locator(selector).boundingBox();
      assert.ok(bounds.width >= 44 && bounds.height >= 44, '44px touch targets');
      assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width, 'Controls stay inside viewport');
      if (selector !== '.highlight-footage') assert.equal(await page.locator(selector).evaluate(el => !!el.closest('a')), false, 'Player controls are not nested in navigation');
    }
    if ([320, 390, 844, 1440].includes(width)) {
      await page.locator('.highlight-toggle').focus(); await page.keyboard.press('Space'); await waitPlaying(page);
      await page.keyboard.press('Space'); await paused(page);
    }
    await page.screenshot({ path: `${out}/${browserLabel}-${width}x${height}.png`, fullPage: false });
  }
  record('13 phone portrait/landscape, tablet and desktop viewports: 16:9 containment, 44px controls and keyboard activation');
  await page.locator('.highlight-restart').focus(); await page.keyboard.press('Enter'); await waitPlaying(page);
  assert.equal(await page.locator('.highlight-toggle').evaluate(button => document.activeElement === button), true, 'Restart hands keyboard focus to the persistent playback control');
  assert.ok(await page.locator('#highlight-video').evaluate(v => v.currentTime < 2), 'Restart returns unfinished playback to the start');
  await hide(page); await show(page); await paused(page);
  await page.waitForTimeout(250); assert.equal(await page.locator('#highlight-video').evaluate(v => v.paused), true);
  record('Reduced-motion playback stays manual after scrolling away and back');
  await page.close();

  const automatic = await pageFor({ motion: 'no-preference' });
  const approach = async distance => {
    await automatic.locator('.highlight-card').evaluate((el, distance) => window.scrollTo({ top: scrollY + el.getBoundingClientRect().top - innerHeight - distance, behavior: 'instant' }), distance);
    await automatic.waitForTimeout(200);
  };
  await approach(230); assert.equal(automatic.mediaRequests.length, 0, 'No body request outside the near-viewport margin');
  await approach(80); await automatic.waitForFunction(() => document.querySelector('#highlight-video').hasAttribute('src'));
  assert.equal(await automatic.locator('#highlight-video').evaluate(v => v.paused), true, 'Near-viewport preload does not play offscreen');
  await show(automatic); await waitPlaying(automatic);
  await hide(automatic); await show(automatic); await waitPlaying(automatic);
  await visibility(automatic, true); await paused(automatic);
  await visibility(automatic, false); await waitPlaying(automatic);
  await automatic.locator('.highlight-toggle').click(); await paused(automatic);
  await hide(automatic); await show(automatic); await visibility(automatic, true); await visibility(automatic, false);
  await automatic.waitForTimeout(300);
  assert.equal(await automatic.locator('#highlight-video').evaluate(v => v.paused), true, 'User pause survives viewport and visibility changes');
  await automatic.locator('.highlight-toggle').click(); await waitPlaying(automatic);
  await automatic.locator('#highlight-video').evaluate(v => { v.currentTime = v.duration - .25; });
  await automatic.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'ended');
  await assertHighlightControls(automatic, 'Replay');
  await hide(automatic); await show(automatic);
  assert.equal(await automatic.locator('#highlight-video').evaluate(v => v.paused), true, 'Ended reel never restarts on its own');
  await automatic.locator('.highlight-toggle').click(); await waitPlaying(automatic);
  assert.ok(await automatic.locator('#highlight-video').evaluate(v => v.currentTime < 2));
  await automatic.waitForFunction(() => !document.querySelector('.highlight-restart').hidden);
  await assertHighlightControls(automatic, 'Pause', { restart: true });
  await automatic.locator('.highlight-restart').focus();
  await automatic.locator('#highlight-video').evaluate(v => { v.currentTime = v.duration - .25; });
  await automatic.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'ended');
  await assertHighlightControls(automatic, 'Replay');
  assert.equal(await automatic.locator('.highlight-toggle').evaluate(button => document.activeElement === button), true, 'Natural completion transfers focus from Restart to Replay');
  await automatic.keyboard.press('Tab');
  assert.equal(await automatic.locator('.highlight-footage').evaluate(link => document.activeElement === link), true, 'Ended keyboard navigation skips the unavailable Restart action');
  await automatic.keyboard.press('Shift+Tab');
  assert.equal(await automatic.locator('.highlight-toggle').evaluate(button => document.activeElement === button), true, 'Keyboard navigation returns directly to the one Replay action');
  await automatic.keyboard.press('Space'); await waitPlaying(automatic);
  await automatic.keyboard.press('Space'); await paused(automatic);
  await assertHighlightControls(automatic, 'Play', { restart: true });
  record('Autoplay near viewport, offscreen/hidden suspension, preserved user pause, finite ending and deliberate replay'); await automatic.close();

  const saver = await pageFor({ motion: 'no-preference', saveData: true }); await show(saver);
  assert.equal(saver.mediaRequests.length, 0, 'Data Saver does not fetch video until play');
  await saver.locator('.highlight-toggle').click(); await waitPlaying(saver);
  record('Data Saver keeps playback and loading manual'); await saver.close();

  let held;
  const delayed = await pageFor({ setup: page => page.route(movieURL, route => { held = route; }) });
  await show(delayed);
  await delayed.locator('.highlight-toggle').click();
  await expect.poll(() => Boolean(held), { timeout: 30000 }).toBe(true);
  await assertHighlightControls(delayed, 'Pause');
  await delayed.locator('.highlight-toggle').click();
  await delayed.unroute(movieURL); await held.continue();
  await delayed.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'paused' && document.querySelector('#highlight-video').readyState >= 2);
  await delayed.waitForTimeout(200);
  assert.equal(await delayed.locator('#highlight-video').evaluate(v => v.paused), true, 'Late media cannot undo a loading-state user pause');
  await assertHighlightControls(delayed, 'Play');
  await delayed.locator('.highlight-toggle').click(); await waitPlaying(delayed);
  record('A pause during loading survives the delayed response and allows deliberate playback'); await delayed.close();

  for (const fault of ['http', 'invalid']) {
    const bad = await pageFor({ setup: page => page.route(movieURL, route => route.fulfill(fault === 'http' ? { status: 503, body: 'Unavailable' } : {
      contentType: route.request().url().endsWith('.mp4') ? 'video/mp4' : 'video/webm', body: 'Not a movie',
    })) });
    await show(bad); await bad.locator('.highlight-toggle').click();
    await bad.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'error');
    assert.ok(await bad.locator('.highlight-poster').isVisible(), 'Error retains poster');
    await assertHighlightControls(bad, 'Try again');
    assert.equal(await bad.locator('.highlight-toggle-label').innerText(), 'Try again');
    await bad.unroute(movieURL); await bad.locator('.highlight-toggle').click(); await assertMoving(bad);
    record(`${fault} media failure retains poster and an explicit retry restores decoded playback`); await bad.close();
  }

  for (const settled of ['ready', 'fallback']) {
    const heldHero = await pageFor({ motion: 'no-preference', heroMode: 'held' }); await show(heldHero);
    await heldHero.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
    await noMovie(heldHero, 'A nearby reel must not compete with pending hero downloads');
    await assertHighlightControls(heldHero, 'Pause');
    await releaseHero(heldHero, settled); await waitPlaying(heldHero);
    record(`Queued autoplay releases after hero ${settled}, without importing its renderer`); await heldHero.close();
  }
  const manualHero = await pageFor({ heroMode: 'held' }); await show(manualHero);
  await manualHero.locator('.highlight-toggle').click();
  await manualHero.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
  await noMovie(manualHero, 'Explicit Play also gives pending CAD downloads priority');
  await assertHighlightControls(manualHero, 'Pause');
  await manualHero.locator('.highlight-toggle').click(); await releaseHero(manualHero);
  await noMovie(manualHero, 'Cancelling manual queued playback survives the late hero completion');
  await manualHero.locator('.highlight-toggle').click(); await waitPlaying(manualHero);
  record('Manual playback queues clearly, remains cancellable, and rechecks an already-ready hero'); await manualHero.close();

  for (const cancellation of ['offscreen', 'hidden', 'preference']) {
    const cancelled = await pageFor({ motion: 'no-preference', heroMode: 'held' }); await show(cancelled);
    await cancelled.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
    if (cancellation === 'offscreen') await cancelled.evaluate(() => {
      // One task: the readiness callback runs before the observer can deliver
      // this scroll. Cached intersection flags alone must not authorize a GET.
      window.scrollTo({ top: 0, behavior: 'instant' });
      const hero = document.querySelector('#robot-preview');
      hero.dataset.ready = 'true'; hero.dataset.state = 'ready';
    });
    if (cancellation === 'hidden') await visibility(cancelled, true);
    if (cancellation === 'preference') await cancelled.emulateMedia({ reducedMotion: 'reduce' });
    if (cancellation !== 'offscreen') await releaseHero(cancelled);
    await noMovie(cancelled, `${cancellation} cancels queued autoplay before the hero finishes`);
    record(`${cancellation} cancels queued autoplay without a late movie request`); await cancelled.close();
  }
  const laggedPreference = await pageFor({ motion: 'no-preference', heroMode: 'held', setup: page => page.addInitScript(() => {
    const nativeMatchMedia = window.matchMedia.bind(window);
    window.__currentReducedMotion = false;
    window.matchMedia = query => {
      if (query !== '(prefers-reduced-motion: reduce)') return nativeMatchMedia(query);
      // Model the observed WebKit interval: new queries see the current setting,
      // while retained query objects have not received their change event yet.
      const captured = window.__currentReducedMotion;
      return { media: query, matches: captured, addEventListener() {}, removeEventListener() {} };
    };
  }) });
  await show(laggedPreference);
  await laggedPreference.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
  await laggedPreference.evaluate(() => {
    window.__currentReducedMotion = true;
    const hero = document.querySelector('#robot-preview'); hero.dataset.ready = 'true'; hero.dataset.state = 'ready';
  });
  await noMovie(laggedPreference, 'Current reduced motion wins before a retained query delivers its change event');
  record('A late MediaQueryList event cannot authorize a movie against the current motion preference'); await laggedPreference.close();
  const missingHero = await pageFor({ motion: 'no-preference', heroMode: 'missing' }); await show(missingHero); await waitPlaying(missingHero);
  assert.equal(await missingHero.locator('#robot-preview').count(), 0);
  record('A page without a hero starts the independent player normally'); await missingHero.close();

  const removedHero = await pageFor({ motion: 'no-preference', heroMode: 'held' }); await show(removedHero);
  await removedHero.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
  await removedHero.locator('.hero-scene').evaluate(el => el.remove()); await waitPlaying(removedHero);
  record('Removing a pending hero through an ancestor releases its queued reel'); await removedHero.close();

  const hungHero = await pageFor({ heroMode: 'held', isolatedClock: true, setup: page => page.clock.install() }); await show(hungHero);
  await hungHero.locator('.highlight-toggle').click();
  await hungHero.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'queued');
  await hungHero.clock.fastForward(60001);
  await hungHero.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'delayed');
  await noMovie(hungHero, 'An expired hero wait never silently begins a competing download');
  assert.equal(await hungHero.locator('#robot-preview').getAttribute('data-state'), 'loading', 'Timeout does not relabel the CAD as successful');
  assert.equal(await hungHero.locator('.highlight-toggle-label').innerText(), 'Play now');
  await hungHero.locator('.highlight-toggle').click(); await waitPlaying(hungHero);
  record('A hung hero has a bounded wait followed by an explicit, labelled manual choice'); await hungHero.context().close();

  const partial = await pageFor(); await show(partial);
  await partial.locator('#highlight-video').evaluate(video => {
    window.__highlightBufferRanges = [[0, .5], [10, 22]];
    Object.defineProperty(video, 'buffered', { get: () => ({
      length: window.__highlightBufferRanges.length,
      start: i => window.__highlightBufferRanges[i][0], end: i => window.__highlightBufferRanges[i][1],
    }) });
  });
  await partial.locator('.highlight-toggle').click();
  await partial.waitForFunction(() => document.querySelector('#highlight-video').readyState >= 2);
  await partial.waitForTimeout(200);
  assert.equal(await partial.locator('#highlight-video').evaluate(v => v.paused), true, 'A decoded first frame and a distant buffered range are insufficient');
  assert.equal(await partial.locator('.highlight-card').getAttribute('data-state'), 'buffering');
  await partial.locator('.highlight-toggle').click();
  await partial.evaluate(() => {
    window.__highlightBufferRanges = [[0, 22]];
    document.querySelector('#highlight-video').dispatchEvent(new Event('progress'));
  });
  await partial.waitForTimeout(200);
  assert.equal(await partial.locator('#highlight-video').evaluate(v => v.paused), true, 'Late buffer completion preserves a deliberate pause');
  await partial.locator('.highlight-toggle').click(); await waitPlaying(partial);
  record('Startup needs a contiguous buffer at currentTime; cancellation and cached resume do not depend on future events'); await partial.close();

  const frozenRecovery = await pageFor({ isolatedClock: true, setup: page => page.clock.install() }); await show(frozenRecovery);
  await frozenRecovery.locator('.highlight-toggle').click(); await waitPlaying(frozenRecovery);
  await frozenRecovery.waitForFunction(() => {
    const v = document.querySelector('#highlight-video');
    return v.buffered.length > 0 && v.buffered.end(0) - v.currentTime >= 3;
  });
  await frozenRecovery.locator('#highlight-video').evaluate(v => {
    // Deliver one seek-like frame, then no forward frame observations. This
    // isolates the watchdog without substituting a frozen file for the reel.
    Object.defineProperty(v, 'requestVideoFrameCallback', { value: callback => {
      window.__heldRecoveryFrame = callback; return 1;
    } });
    Object.defineProperty(v, 'cancelVideoFrameCallback', { value: () => {} });
    v.dispatchEvent(new Event('waiting'));
    window.__heldRecoveryFrame(performance.now(), { mediaTime: v.currentTime, presentedFrames: 1 });
  });
  await frozenRecovery.clock.fastForward(20001);
  await frozenRecovery.waitForFunction(() => document.querySelector('.highlight-card').dataset.state === 'error');
  await frozenRecovery.evaluate(() => window.__heldRecoveryFrame(performance.now(), { mediaTime: 5, presentedFrames: 20 }));
  assert.equal(await frozenRecovery.locator('.highlight-card').getAttribute('data-state'), 'error');
  assert.equal(await frozenRecovery.locator('#highlight-video').evaluate(v => v.paused), true, 'A stale recovery frame cannot revive the failed attempt');
  record('A lone seek frame cannot disarm the frozen-recovery watchdog, and its late callback stays invalid'); await frozenRecovery.context().close();

  assert.deepEqual(errors, []);
  assert.deepEqual(await json('/version.json'), version, 'Single published build throughout test');
  await writeFile(`${out}/${browserLabel}-report.json`, JSON.stringify({ base, browser: browserLabel, version, poster, media, motionEvidence, viewports, cases, errors }, null, 2));
} catch (error) {
  for (const [index, page] of pages.entries()) {
    if (page.isClosed()) continue;
    console.error('Highlight failure details', await page.locator('#highlight-video').evaluate(v => ({
      state: document.querySelector('.highlight-card').dataset.state, source: v.currentSrc, error: v.error && { code: v.error.code, message: v.error.message },
      readyState: v.readyState, networkState: v.networkState, paused: v.paused, time: v.currentTime, duration: v.duration,
      h264: v.canPlayType('video/mp4; codecs="avc1.64001f"'), vp9: v.canPlayType('video/webm; codecs="vp9"'),
    })).catch(() => null));
    await page.screenshot({ path: `${out}/${browserLabel}-failure-${index}.png` }).catch(() => {});
  }
  throw error;
} finally {
  await browser.close();
}
