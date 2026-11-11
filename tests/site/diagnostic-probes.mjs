/** Temporary, test-only observations. They never decide whether a product gate passed. */
import {safeReadinessURL} from './layout/readiness-diagnostics.mjs';

export const setupDiagnosticScope = (ci, sizes, route) => ci === 'true' &&
  ['phone-360', 'tablet-768'].includes(sizes) && route === '/designer/sim.html';
const bounded = async (operation, ms, label) => {
  let timer;
  try { return await Promise.race([operation, new Promise((_, reject) => {
    timer = setTimeout(() => reject(Error(label)), ms);
  })]); } finally { clearTimeout(timer); }
};

/** Installed before navigation; the wrapper forwards even invalid calls unchanged. */
export function installSetupProbe(enabled) {
  if (!enabled || location.pathname !== '/designer/sim.html') return;
  const prototype = HTMLCanvasElement.prototype, descriptor = Object.getOwnPropertyDescriptor(prototype, 'getContext');
  const calls = [], heartbeat = []; let callCount = 0, beats = 0, stopped = null;
  const now = () => performance.now();
  const original = descriptor?.value;
  function getContext(...args) {
    const start = now(); let result, threw = true;
    try { result = Reflect.apply(original, this, args); threw = false; return result; }
    finally {
      callCount++;
      if (calls.length < 32) calls.push({start, end: now(), kind: ['2d', 'webgl', 'webgl2', 'bitmaprenderer'].includes(args[0]) ? args[0] : 'other', threw, returnedNull: !threw && result === null});
    }
  }
  const wrapped = typeof original === 'function' && descriptor.configurable;
  if (wrapped) Object.defineProperty(prototype, 'getContext', {...descriptor, value: getContext});
  const interval = setInterval(() => { beats++; if (heartbeat.length < 256) heartbeat.push(now()); }, 250);
  const stop = () => {
    if (stopped) return stopped;
    clearInterval(interval); clearTimeout(watchdog);
    const owned = Object.getOwnPropertyDescriptor(prototype, 'getContext')?.value === getContext;
    if (owned) Object.defineProperty(prototype, 'getContext', descriptor);
    stopped = {timeOrigin: performance.timeOrigin, stoppedAt: now(), wrapped, restored: owned,
      calls: [...calls], callCount, callsDropped: callCount - calls.length,
      heartbeat: [...heartbeat], beats, heartbeatDropped: beats - heartbeat.length};
    return stopped;
  };
  const watchdog = setTimeout(stop, 60000);
  window.__gy315SetupProbe = {stop};
}

const labels = new Set(['(idle)', '(program)', '(garbage collector)', '(root)']);
/** No raw profile/string payload escapes this reducer. Durations are sampled wall intervals, not CPU claims. */
export function summarizeProfile(profile, origin) {
  if (!Array.isArray(profile?.nodes) || !Array.isArray(profile.samples) || !Array.isArray(profile.timeDeltas))
    return {available: false, incomplete: true, reason: 'missing-profile-arrays'};
  if (profile.nodes.length > 20000 || profile.samples.length > 120000 || profile.timeDeltas.length > 120000)
    return {available: false, incomplete: true, reason: 'profile-cap'};
  if (profile.nodes.some(node => !node || !Array.isArray(node.children ?? [])))
    return {available: false, incomplete: true, reason: 'invalid-profile-node'};
  if (profile.nodes.reduce((total, node) => total + (node.children?.length ?? 0), 0) > 120000)
    return {available: false, incomplete: true, reason: 'profile-edge-cap'};
  const nodes = new Map(profile.nodes.map(node => [node.id, node])), parent = new Map(), locations = new Map(), stacks = new Map();
  for (const node of profile.nodes) for (const child of (node.children ?? [])) parent.set(child, node.id);
  const location = node => {
    if (!node) return 'missing';
    if (locations.has(node.id)) return locations.get(node.id);
    const frame = node.callFrame ?? {}, url = safeReadinessURL(frame.url, origin);
    const result = url.startsWith('/') ? `${url.slice(0, 180)}:${Number.isInteger(frame.lineNumber) ? frame.lineNumber + 1 : 0}:${Number.isInteger(frame.columnNumber) ? frame.columnNumber + 1 : 0}`
      : labels.has(frame.functionName) ? frame.functionName : frame.url ? 'unowned-script' : 'native-or-unknown';
    locations.set(node.id, result); return result;
  };
  const stackFor = id => {
    if (stacks.has(id)) return stacks.get(id);
    const sample = id;
    const stack = [], seen = new Set();
    while (id !== undefined && stack.length < 6 && !seen.has(id)) {
      seen.add(id); const node = nodes.get(id); stack.push(location(node)); id = parent.get(id);
    }
    const result = stack.join(' <- '); stacks.set(sample, result); return result;
  };
  const count = Math.min(profile.samples.length, profile.timeDeltas.length), totals = new Map(), buckets = new Map();
  let elapsedUs = 0, invalid = 0;
  for (let i = 0; i < count; i++) {
    const delta = profile.timeDeltas[i];
    if (!Number.isFinite(delta) || delta < 0) { invalid++; continue; }
    elapsedUs += delta;
    const bucket = Math.floor(elapsedUs / 1000000);
    if (bucket >= 60) { invalid++; continue; }
    const stack = stackFor(profile.samples[i]);
    totals.set(stack, (totals.get(stack) ?? 0) + 1);
    if (!buckets.has(bucket)) buckets.set(bucket, new Map());
    const rows = buckets.get(bucket); rows.set(stack, (rows.get(stack) ?? 0) + 1);
  }
  const top = (rows, limit) => [...rows].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([stack, samples]) => ({stack, samples}));
  const result = {available: true, incomplete: invalid > 0 || profile.samples.length !== profile.timeDeltas.length,
    samplingIntervalUs: 5000, samples: count, invalidOrBeyond60s: invalid, elapsedUs,
    attribution: 'Sampled stacks and wall intervals; native, idle, missing and scheduling waits remain ambiguous.',
    top: top(totals, 12), buckets: [...buckets].map(([second, rows]) => ({second, top: top(rows, 3)})),
    distinctStacks: totals.size, omittedTopStacks: Math.max(0, totals.size - 12)};
  return JSON.stringify(result).length <= 131072 ? result : {available: false, incomplete: true, reason: 'summary-cap'};
}

/** One profile for the existing page only; setup failures leave the original gate in charge. */
export async function startSetupDiagnostic(page, origin, {setupMs = 1000, finishMs = 1800} = {}) {
  let session, active = true, started = false, finishPromise, watchdog, detachPromise;
  const errors = [], nodeStartedAt = Date.now();
  const note = phase => errors.push({phase, incomplete: true});
  const detach = () => {
    if (detachPromise) return detachPromise;
    if (!session) return Promise.resolve();
    const owned = session; session = null;
    detachPromise = Promise.resolve().then(() => owned.detach()).catch(() => note('detach'));
    return detachPromise;
  };
  const setup = (async () => {
    const attached = await page.context().newCDPSession(page);
    if (!active) { try { await attached.detach(); } catch { note('late-detach'); } return; }
    session = attached;
    for (const [method, args] of [['Profiler.enable', undefined], ['Profiler.setSamplingInterval', {interval: 5000}], ['Profiler.start', undefined]]) {
      if (!active) return;
      await attached.send(method, args);
      if (method === 'Profiler.start') started = true;
    }
  })();
  try { await bounded(setup, setupMs, 'setup-bound'); }
  catch { active = false; note('setup'); void detach(); }
  const finish = () => {
    if (finishPromise) return finishPromise;
    active = false; clearTimeout(watchdog);
    const result = {observerPerturbation: true, nodeStartedAt, nodeFinishedAt: null,
      profile: {available: false, incomplete: true, reason: 'not-started'}, probe: null, errors};
    const collect = (async () => {
      try {
        await Promise.all([
          (async () => { if (session && started) { try { const {profile} = await session.send('Profiler.stop'); result.profile = summarizeProfile(profile, origin); } catch { note('profile-stop'); } } })(),
          (async () => { try { result.probe = await page.evaluate(() => window.__gy315SetupProbe?.stop() ?? null); if (!result.probe) note('probe-unavailable'); } catch { note('probe-stop'); } })(),
        ]);
      } finally { await detach(); result.nodeFinishedAt = Date.now(); }
    })();
    finishPromise = bounded(collect, finishMs, 'finish-bound').catch(() => { note('finish-bound'); void detach(); return result; }).then(() => result);
    return finishPromise;
  };
  if (active) watchdog = setTimeout(() => { void finish(); }, Math.max(0, 60000 - (Date.now() - nodeStartedAt)));
  return {finish};
}

/** Runs on the exact summary; numeric observations do not dispatch or await a frame. */
export function installSummaryProbe(element) {
  window.__gy315SummaryProbe?.stop();
  let samples = [], total = 0, stopped;
  const read = () => {
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element), ancestors = [], path = [];
    for (let node = element; node?.parentElement && path.length < 16; node = node.parentElement)
      path.push(Array.prototype.indexOf.call(node.parentElement.children ?? [], node));
    for (let node = element.parentElement; node && ancestors.length < 8; node = node.parentElement) {
      if (node.tagName === 'DETAILS') ancestors.push({open: node.open, hidden: node.hidden, inert: node.inert});
    }
    const explorer = document.querySelector('#assembly-explorer'), active = document.activeElement;
    return {at: performance.now(), connected: element.isConnected, rect: [rect.x, rect.y, rect.width, rect.height],
      display: style.display !== 'none', visibility: style.visibility === 'visible', enabled: !element.matches(':disabled'),
      path, ancestors, explorerHidden: explorer?.hidden ?? null, scroll: [scrollX, scrollY, explorer?.scrollTop ?? null],
      documentTimeOrigin: performance.timeOrigin, documentState: document.readyState, visible: document.visibilityState === 'visible',
      documentToken: /^[a-f0-9-]{36}$/.test(window.__workspaceDocumentToken ?? '') ? window.__workspaceDocumentToken : null,
      focused: document.hasFocus(), targetFocused: active === element, activeTag: ['BODY', 'BUTTON', 'SUMMARY', 'INPUT', 'SELECT', 'CANVAS'].includes(active?.tagName) ? active.tagName : 'other'};
  };
  const before = read();
  const interval = setInterval(() => { total++; if (samples.length < 128) samples.push(read()); }, 250);
  const stop = () => {
    if (!stopped) { clearInterval(interval); clearTimeout(watchdog); stopped = {before, after: read(), samples, total, dropped: total - samples.length}; }
    return stopped;
  };
  const watchdog = setTimeout(stop, 34000);
  window.__gy315SummaryProbe = {stop};
}

export async function observedSummaryClick(page, summary, action, observations, {boundMs = 1800, part = null, ancestorStep = null} = {}) {
  const row = {case: 'native summary action observation', observerPerturbation: true,
    part: ['L.hip_frame', 'R.hip_frame', 'L.upper_link_front'].includes(part) ? part : null,
    ancestorStep: Number.isInteger(ancestorStep) && ancestorStep >= 0 && ancestorStep < 16 ? ancestorStep : null,
    samples: null, diagnosticErrors: []};
  observations.push(row);
  try { await bounded(summary.evaluate(installSummaryProbe), boundMs, 'before-bound'); }
  catch { row.diagnosticErrors.push('before-unavailable'); }
  try { return await action(); }
  finally {
    try { row.samples = await bounded(page.evaluate(() => window.__gy315SummaryProbe?.stop() ?? null), boundMs, 'after-bound'); }
    catch { row.diagnosticErrors.push('after-unavailable'); }
  }
}
