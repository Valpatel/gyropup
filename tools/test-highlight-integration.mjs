/**
 * Cold, real landing-page integration: the hero and reel share one connection.
 * No routes, mocked models, forced media sources or altered hero state are used.
 *
 * Chrome defaults to both cases at 150 ms / 1.6 Mbps down / 750 kbps up.
 * HIGHLIGHT_INTEGRATION_CASE=auto|manual selects one case. WebKit has no CDP
 * network shaping and defaults to one unthrottled automatic case.
 */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';

const base = (process.env.SITE_URL || 'http://127.0.0.1:8899').replace(/\/$/, '');
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-highlight-integration';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browserLabel = engine === webkit ? 'webkit' : process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? 'chromium' : 'chrome';
const selection = process.env.HIGHLIGHT_INTEGRATION_CASE || (engine === webkit ? 'auto' : 'all');
assert.ok(['all', 'auto', 'manual'].includes(selection), 'HIGHLIGHT_INTEGRATION_CASE must be all, auto or manual');
const cases = selection === 'all' ? ['auto', 'manual'] : [selection];
const viewport = { width: 390, height: 844 };
const network = engine === chromium ? { latencyMs: 150, downloadBytesPerSecond: 200000, uploadBytesPerSecond: 93750 } : null;
const movieURL = value => /\/web\/highlights\/gyropup-highlights\.(mp4|webm)$/.test(new URL(value).pathname);
const relevantAsset = value => {
  const url = new URL(value);
  return url.origin === new URL(base).origin && (movieURL(value) || /^\/(designer|exports\/sim)\//.test(url.pathname));
};
const browser = await engine.launch({ headless: true, ...(engine === chromium ? {
  channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome',
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
} : {}) });
await mkdir(out, { recursive: true });
const reports = [];

function installProbe() {
  localStorage.setItem('gyropup.probe', 'off');
  localStorage.setItem('gyropup-sfx', '0');
  sessionStorage.setItem('gyropup.prototype-notice', '2026-10-29-v1');
  const probe = window.__highlightIntegrationProbe = {
    timeOrigin: performance.timeOrigin, heroReadyAt: null, heroStates: [],
    sources: [], events: [], firstDecodedFrame: null,
  };
  document.addEventListener('DOMContentLoaded', () => {
    const video = document.querySelector('#highlight-video');
    const hero = document.querySelector('#robot-preview');
    const buffered = () => Array.from({ length: video.buffered.length }, (_, i) => [video.buffered.start(i), video.buffered.end(i)]);
    const heroChanged = () => {
      const state = { at: performance.now(), state: hero.dataset.state, ready: hero.dataset.ready === 'true' };
      probe.heroStates.push(state);
      if (state.ready && probe.heroReadyAt === null) probe.heroReadyAt = state.at;
    };
    const sourceChanged = () => {
      const src = video.getAttribute('src');
      if (src) probe.sources.push({ at: performance.now(), src, heroReady: hero.dataset.ready === 'true' });
    };
    new MutationObserver(heroChanged).observe(hero, { attributes: true, attributeFilter: ['data-ready', 'data-state'] });
    new MutationObserver(sourceChanged).observe(video, { attributes: true, attributeFilter: ['src'] });
    heroChanged(); sourceChanged();
    for (const type of ['loadstart', 'loadedmetadata', 'loadeddata', 'play', 'playing', 'waiting', 'stalled', 'pause', 'ended', 'error']) {
      video.addEventListener(type, () => probe.events.push({
        type, at: performance.now(), mediaTime: video.currentTime,
        readyState: video.readyState, networkState: video.networkState, buffered: buffered(),
        error: video.error && { code: video.error.code, message: video.error.message },
      }));
    }
    video.requestVideoFrameCallback((now, metadata) => {
      probe.firstDecodedFrame = {
        at: now, epochMs: performance.timeOrigin + now, mediaTime: metadata.mediaTime,
        presentedFrames: metadata.presentedFrames, buffered: buffered(),
        heroReady: hero.dataset.ready === 'true',
      };
    });
  }, { once: true });
}

async function version(context) {
  const response = await context.request.get(base + '/version.json');
  assert.ok(response.ok(), 'Published build metadata is available');
  return response.json();
}

async function state(page) {
  return page.evaluate(() => {
    const video = document.querySelector('#highlight-video');
    const hero = window.__heroPreview;
    const quality = video.getVideoPlaybackQuality();
    return {
      at: performance.now(),
      hero: {
        state: document.querySelector('#robot-preview').dataset.state,
        ready: document.querySelector('#robot-preview').dataset.ready === 'true',
        canvas: !!document.querySelector('#robot-preview canvas'),
        renderCalls: hero?.renderer.info.render.calls, triangles: hero?.renderer.info.render.triangles,
        soundEnabled: hero?.sfx.enabled, loadingHidden: document.querySelector('#hero-loading').hidden,
      },
      video: {
        state: document.querySelector('.highlight-card').dataset.state, source: video.currentSrc,
        time: video.currentTime, duration: Number.isFinite(video.duration) ? video.duration : null,
        paused: video.paused, ended: video.ended, muted: video.muted,
        width: video.videoWidth, height: video.videoHeight,
        decodedFrames: quality.totalVideoFrames, droppedFrames: quality.droppedVideoFrames,
        buffered: Array.from({ length: video.buffered.length }, (_, i) => [video.buffered.start(i), video.buffered.end(i)]),
        error: video.error && { code: video.error.code, message: video.error.message },
      },
    };
  });
}

async function movingPixels(page) {
  return page.locator('#highlight-video').evaluate(async video => {
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 90;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const sample = () => {
      // Exclude the baked titles: text changing cannot establish robot motion.
      ctx.drawImage(video, video.videoWidth * .15, video.videoHeight * .22, video.videoWidth * .7, video.videoHeight * .58, 0, 0, 160, 90);
      return ctx.getImageData(0, 0, 160, 90).data;
    };
    const before = sample(), time = video.currentTime, frames = video.getVideoPlaybackQuality().totalVideoFrames;
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Decoded frames did not advance')), 10000);
      const frame = () => {
        if (video.currentTime > time + .7) { clearTimeout(timeout); resolve(); }
        else video.requestVideoFrameCallback(frame);
      };
      video.requestVideoFrameCallback(frame);
    });
    const after = sample(); let difference = 0;
    for (let i = 0; i < before.length; i += 4) for (let c = 0; c < 3; c++) difference += Math.abs(before[i + c] - after[i + c]);
    return {
      beforeTime: time, afterTime: video.currentTime,
      beforeFrames: frames, afterFrames: video.getVideoPlaybackQuality().totalVideoFrames,
      meanPixelDifference: difference / (160 * 90 * 3),
    };
  });
}

function summarize(report) {
  const probe = report.probe;
  const movie = report.resources?.find(resource => movieURL(resource.name));
  const first = probe?.firstDecodedFrame;
  const events = probe?.events || [];
  const playing = events.find(event => event.type === 'playing');
  const ended = events.find(event => event.type === 'ended');
  const stalls = [];
  for (const [index, event] of events.entries()) {
    if (event.type !== 'waiting' || !playing || event.at <= playing.at || (ended && event.at >= ended.at)) continue;
    const next = events.slice(index + 1).find(event => ['playing', 'ended', 'error'].includes(event.type));
    stalls.push({ at: event.at, mediaTime: event.mediaTime, until: next?.type, durationMs: next ? next.at - event.at : null });
  }
  const summary = {
    heroReadyMs: probe?.heroReadyAt,
    movieRequestAfterHeroReadyMs: movie && probe?.heroReadyAt != null ? movie.startTime - probe.heroReadyAt : null,
    requestToFirstDecodedFrameMs: first && movie ? first.at - movie.startTime : null,
    requestToFirstPlayingMs: playing && movie ? playing.at - movie.startTime : null,
    requestToEndedMs: ended && movie ? ended.at - movie.startTime : null,
    firstDecodedFrameBuffered: first?.buffered, firstPlaying: playing,
    movieResource: movie, stalls, totalStallMs: stalls.reduce((sum, stall) => sum + (stall.durationMs || 0), 0),
  };
  if (first && report.cdpMedia.length) {
    const media = report.cdpMedia[0];
    summary.chromeBodyBytesAtFirstFrame = media.data.filter(chunk => chunk.epochMs <= first.epochMs)
      .reduce((sum, chunk) => ({ payload: sum.payload + chunk.dataLength, encoded: sum.encoded + chunk.encodedDataLength }), { payload: 0, encoded: 0 });
    summary.chromeMovieTransfer = media.finished;
  }
  return summary;
}

async function run(mode) {
  const context = await browser.newContext({ viewport, reducedMotion: 'no-preference' });
  await context.addInitScript(installProbe);
  const page = await context.newPage(); page.setDefaultTimeout(90000);
  const report = {
    mode, browser: browserLabel, browserVersion: browser.version(), base, viewport, network,
    notes: [
      'Each case uses a fresh browser context with no request interception or forced media source.',
      'The real hero, source media and playback controls run together; saved notice and sound-off preferences are set normally.',
      'Headless desktop browser at a phone viewport, not a real-device performance guarantee.',
      'Chrome CDP transfer totals include protocol overhead; Resource Timing also records encoded movie body bytes.',
    ],
    pageErrors: [], consoleWarnings: [], failedRequests: [], badResponses: [],
    movieRequests: [], cdpMedia: [], snapshots: [], passed: false,
  };
  reports.push(report);
  const pending = [], requests = new Map();
  page.on('pageerror', error => report.pageErrors.push(error.message));
  page.on('console', message => {
    if (['warning', 'error'].includes(message.type())) report.consoleWarnings.push({ type: message.type(), text: message.text() });
  });
  page.on('requestfailed', request => report.failedRequests.push({ url: request.url(), failure: request.failure() }));
  page.on('request', request => {
    if (!movieURL(request.url())) return;
    const entry = { url: request.url(), method: request.method() };
    requests.set(request, entry); report.movieRequests.push(entry);
    pending.push(request.allHeaders().then(headers => { entry.requestHeaders = Object.fromEntries(Object.entries(headers).filter(([key]) => ['range', 'if-range'].includes(key))); }).catch(error => { entry.requestHeadersError = error.message; }));
  });
  page.on('response', response => {
    if (response.status() >= 400) report.badResponses.push({ url: response.url(), status: response.status() });
    const entry = requests.get(response.request());
    if (!entry) return;
    entry.status = response.status();
    pending.push(response.allHeaders().then(headers => { entry.responseHeaders = Object.fromEntries(Object.entries(headers).filter(([key]) => ['content-type', 'content-length', 'content-range', 'accept-ranges'].includes(key))); }).catch(error => { entry.responseHeadersError = error.message; }));
  });
  page.on('requestfinished', request => {
    const entry = requests.get(request);
    if (entry) pending.push(request.sizes().then(sizes => { entry.sizes = sizes; }).catch(error => { entry.sizesError = error.message; }));
  });
  if (network) {
    const cdp = await context.newCDPSession(page), media = new Map();
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false, latency: network.latencyMs,
      downloadThroughput: network.downloadBytesPerSecond, uploadThroughput: network.uploadBytesPerSecond,
    });
    cdp.on('Network.requestWillBeSent', event => {
      if (!movieURL(event.request.url)) return;
      const entry = { url: event.request.url, requestEpochMs: event.wallTime * 1000, requestTimestamp: event.timestamp, data: [] };
      media.set(event.requestId, entry); report.cdpMedia.push(entry);
    });
    cdp.on('Network.dataReceived', event => {
      const entry = media.get(event.requestId);
      if (entry) entry.data.push({
        afterRequestMs: (event.timestamp - entry.requestTimestamp) * 1000,
        epochMs: entry.requestEpochMs + (event.timestamp - entry.requestTimestamp) * 1000,
        dataLength: event.dataLength, encodedDataLength: event.encodedDataLength,
      });
    });
    cdp.on('Network.loadingFinished', event => {
      const entry = media.get(event.requestId);
      if (entry) entry.finished = { afterRequestMs: (event.timestamp - entry.requestTimestamp) * 1000, encodedDataLength: event.encodedDataLength };
    });
  }
  let deadline;
  console.log(`RUN ${browserLabel} ${mode}: normal hero + reel${network ? ', 150 ms / 1.6 Mbps down' : ', unthrottled'}`);
  try {
    await Promise.race([
      (async () => {
        report.version = await version(context);
        await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
        await page.locator('.highlight-controls').waitFor({ state: 'visible' });
        await page.addStyleTag({ content: 'html{scroll-behavior:auto!important}' });
        await page.locator('.highlight-card').evaluate(el => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
        if (mode === 'manual') {
          // Let the viewport observer run. Cancel its automatic intent first,
          // then deliberately Play using the real, visible control. This keeps
          // the normal motion preference and does not synthesize an offscreen
          // click merely to beat the automatic queue.
          await page.waitForTimeout(150);
          if (/pause|cancel/i.test(await page.locator('.highlight-toggle').getAttribute('aria-label'))) {
            await page.locator('.highlight-toggle').click();
            report.cancelledAutoplayBeforeManual = true;
          }
          report.manualBeforeClick = await state(page);
          if (network) assert.equal(report.manualBeforeClick.hero.ready, false, 'Cold manual case reaches the control while the hero is loading');
          await page.locator('.highlight-toggle').click();
          report.manualAfterClick = await state(page);
          if (network) {
            assert.equal(await page.locator('#highlight-video').getAttribute('src'), null, 'An early manual Play does not compete with hero downloads');
            assert.match(await page.locator('.highlight-toggle').getAttribute('aria-label'), /pause|cancel/i, 'Queued manual playback remains cancellable');
          }
        }
        report.snapshots.push({ label: 'near-reel', ...await state(page) });
        await page.waitForFunction(() => {
          const hero = document.querySelector('#robot-preview'), video = document.querySelector('#highlight-video');
          if (hero.dataset.state === 'fallback') throw new Error(document.querySelector('#hero-loading-message').textContent);
          if (video.error || document.querySelector('.highlight-card').dataset.state === 'error') throw new Error(video.error?.message || document.querySelector('.highlight-status').textContent);
          return hero.dataset.ready === 'true' && !video.paused && video.currentTime > .2;
        });
        report.snapshots.push({ label: 'hero-ready-and-playing', ...await state(page) });
        report.motion = await movingPixels(page);
        assert.ok(report.motion.afterFrames > report.motion.beforeFrames, 'Real decoded frame count advances');
        assert.ok(report.motion.meanPixelDifference > .15, 'The model region moves, independently of baked captions');
        await page.waitForFunction(() => {
          const video = document.querySelector('#highlight-video');
          if (video.error) throw new Error(video.error.message);
          return video.ended;
        });
        report.snapshots.push({ label: 'natural-end', ...await state(page) });
        const completed = report.snapshots.at(-1);
        assert.ok(Math.abs(completed.video.duration - 22) < .1, 'Complete 22-second reel plays without a seek');
        assert.ok(completed.video.decodedFrames >= 600, 'The complete reel decodes frames, not only its first shot');
        assert.equal(completed.video.width, 1280); assert.equal(completed.video.height, 720);
        assert.equal(completed.video.muted, true);
        assert.equal(completed.hero.ready, true); assert.equal(completed.hero.canvas, true);
        assert.ok(completed.hero.renderCalls > 0); assert.ok(completed.hero.triangles > 0);
        assert.equal(completed.hero.soundEnabled, false);
        assert.equal(completed.hero.loadingHidden, true);
        await page.locator('.highlight-replay').click();
        await page.waitForFunction(() => {
          const video = document.querySelector('#highlight-video');
          return !video.paused && video.currentTime > .7 && video.currentTime < 5;
        });
        report.snapshots.push({ label: 'replay-with-hero-ready', ...await state(page) });
        await page.locator('.highlight-toggle').click();
        await page.screenshot({ path: `${out}/${browserLabel}-${mode}-390x844.png` });
        report.endVersion = await version(context);
        assert.deepEqual(report.endVersion, report.version, 'One published build throughout the cold integration case');
      })(),
      new Promise((resolve, reject) => {
        deadline = setTimeout(() => {
          report.timedOut = true;
          void context.close();
          reject(new Error('Cold hero/reel integration exceeded its 120-second case budget'));
        }, 120000);
      }),
    ]);
    clearTimeout(deadline);
    report.probe = await page.evaluate(() => window.__highlightIntegrationProbe);
    report.resources = await page.evaluate(() => performance.getEntriesByType('resource').map(resource => ({
      name: resource.name, startTime: resource.startTime, responseStart: resource.responseStart, responseEnd: resource.responseEnd,
      duration: resource.duration, transferSize: resource.transferSize, encodedBodySize: resource.encodedBodySize, decodedBodySize: resource.decodedBodySize,
    })));
    await Promise.allSettled(pending);
    report.summary = summarize(report);
    assert.deepEqual(report.pageErrors, [], 'No page errors with the normal hero and reel');
    assert.deepEqual(report.failedRequests.filter(request => relevantAsset(request.url)), [], 'No failed hero or media requests');
    assert.deepEqual(report.badResponses.filter(response => relevantAsset(response.url)), [], 'No bad hero or media responses');
    assert.ok(!report.probe.heroStates.some(state => state.state === 'fallback'), 'Hero never falls back while the reel is loading');
    assert.ok(report.probe.sources.length > 0, 'Normal player selects its own source');
    assert.ok(report.probe.sources.every(source => source.heroReady), 'Every movie source assignment follows hero readiness');
    // MutationObserver timestamps are collected after the readiness mutation.
    // The Boolean at source assignment is the causal assertion; 50 ms permits
    // observer delivery without treating a scheduling difference as contention.
    assert.ok(report.summary.movieRequestAfterHeroReadyMs >= -50, 'Movie request starts after hero readiness');
    assert.ok(report.probe.firstDecodedFrame?.heroReady, 'Hero is ready before the first decoded movie frame');
    assert.equal(new Set(report.movieRequests.map(request => new URL(request.url).pathname)).size, 1, 'The normal player fetches one encoding');
    const firstPlaying = report.summary.firstPlaying;
    assert.ok(firstPlaying, 'Playback starts normally');
    const playable = firstPlaying.buffered.find(([start, end]) => start <= firstPlaying.mediaTime + .05 && end >= firstPlaying.mediaTime);
    assert.ok(playable && playable[1] - firstPlaying.mediaTime >= 2.8, 'Initial playback has approximately three seconds buffered');
    assert.ok(report.summary.stalls.every(stall => stall.durationMs !== null), 'Every playback wait recovers');
    assert.ok(report.summary.totalStallMs <= 1000, `No meaningful repeated stalls under the recorded conditions: ${report.summary.totalStallMs.toFixed(1)} ms`);
    report.passed = true;
    console.log(`PASS ${browserLabel} ${mode}: hero ${Math.round(report.summary.heroReadyMs)} ms; request→frame ${Math.round(report.summary.requestToFirstDecodedFrameMs)} ms; ${report.summary.stalls.length} waits / ${Math.round(report.summary.totalStallMs)} ms; real motion and full playback/replay`);
  } catch (error) {
    report.failure = error.stack;
    report.probe ??= await page.evaluate(() => window.__highlightIntegrationProbe).catch(() => null);
    report.snapshots.push({ label: 'failure', ...await state(page).catch(() => ({ unavailable: true })) });
    report.resources ??= await page.evaluate(() => performance.getEntriesByType('resource').map(resource => ({
      name: resource.name, startTime: resource.startTime, responseEnd: resource.responseEnd,
      duration: resource.duration, transferSize: resource.transferSize, encodedBodySize: resource.encodedBodySize, decodedBodySize: resource.decodedBodySize,
    }))).catch(() => []);
    report.summary = summarize(report);
    await page.screenshot({ path: `${out}/${browserLabel}-${mode}-failure.png`, timeout: 5000 }).catch(() => {});
    console.error(`FAIL ${browserLabel} ${mode}: ${error.message}`);
  } finally {
    clearTimeout(deadline);
    await Promise.allSettled(pending);
    await writeFile(`${out}/${browserLabel}-${mode}-report.json`, JSON.stringify(report, null, 2));
    await context.close();
  }
}

try {
  for (const mode of cases) await run(mode);
  await writeFile(`${out}/${browserLabel}-summary.json`, JSON.stringify({ base, browser: browserLabel, network, cases: reports.map(report => ({ mode: report.mode, passed: report.passed, version: report.version, summary: report.summary, failure: report.failure })) }, null, 2));
  assert.ok(reports.every(report => report.passed), `Integration failed; inspect ${out}/${browserLabel}-*-report.json`);
} finally {
  await browser.close();
}
