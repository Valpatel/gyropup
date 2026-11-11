import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {installSetupProbe, installSummaryProbe, setupDiagnosticScope, summarizeProfile, startSetupDiagnostic, observedSummaryClick} from './diagnostic-probes.mjs';

function browserFixture(native = () => ({}), pathname = '/designer/sim.html') {
  const intervals = new Map(), timers = new Map(); let next = 0, clock = 0;
  const prototype = {}; Object.defineProperty(prototype, 'getContext', {value: native, configurable: true, writable: true});
  const window = {}, fixture = {window, location: {pathname}, HTMLCanvasElement: {prototype},
    performance: {timeOrigin: 1000, now: () => ++clock},
    setInterval: (fn, ms) => {const id = ++next; intervals.set(id, {fn, ms}); return id;}, clearInterval: id => intervals.delete(id),
    setTimeout: (fn, ms) => {const id = ++next; timers.set(id, {fn, ms}); return id;}, clearTimeout: id => timers.delete(id)};
  return {fixture, prototype, window, intervals, timers, setClock: value => {clock = value;},
    install: enabled => vm.runInNewContext(`(${installSetupProbe})(${enabled})`, fixture)};
}
test('probe delegates original this/argument identities, object/null return and exact thrown exception', () => {
  const canvas = {}, options = {}, object = {}, exception = Error('same exception'); let mode = object;
  const seen = [], f = browserFixture(function (...args) {seen.push({self: this, args}); if (mode === exception) throw exception; return mode;});
  f.install(true); const wrapped = f.prototype.getContext;
  assert.equal(wrapped.call(canvas, 'webgl2', options), object);
  mode = null; assert.equal(wrapped.call(canvas, '2d', options), null);
  mode = exception; assert.throws(() => wrapped.call(canvas, 'unknown', options), error => error === exception);
  assert.ok(seen.every(call => call.self === canvas && call.args[1] === options));
  const result = f.window.__gy315SetupProbe.stop();
  assert.deepEqual(Array.from(result.calls, row => row.kind), ['webgl2', '2d', 'other']);
  assert.equal(result.calls[1].returnedNull, true); assert.equal(result.calls[2].threw, true);
  assert.ok(result.calls.every(row => row.end > row.start)); assert.equal(result.restored, true);
  assert.equal(f.intervals.size, 0); assert.equal(f.timers.size, 0);
});
test('probe is exact-route scoped, capped, owns restoration and uses one250ms heartbeat/60s watchdog', () => {
  const f = browserFixture(); f.install(true);
  assert.equal(f.intervals.size, 1); assert.equal([...f.intervals.values()][0].ms, 250);
  assert.equal([...f.timers.values()][0].ms, 60000);
  for (let i = 0; i < 40; i++) f.prototype.getContext('webgl');
  for (let i = 0; i < 300; i++) [...f.intervals.values()][0].fn();
  const replacement = () => null; f.prototype.getContext = replacement;
  const result = f.window.__gy315SetupProbe.stop();
  assert.equal(result.calls.length, 32); assert.equal(result.callsDropped, 8); assert.equal(result.heartbeat.length, 256); assert.equal(result.heartbeatDropped, 44);
  assert.equal(result.restored, false); assert.equal(f.prototype.getContext, replacement);
  assert.equal(f.window.__gy315SetupProbe.stop(), result);
  for (const [enabled, path] of [[false, '/designer/sim.html'], [true, '/designer/build.html']]) {
    const off = browserFixture(undefined, path), original = off.prototype.getContext; off.install(enabled);
    assert.equal(off.prototype.getContext, original); assert.equal(off.intervals.size, 0); assert.equal(off.timers.size, 0);
  }
});
test('missing native descriptor remains unmodified and reports unavailable wrapping', () => {
  const f = browserFixture(); delete f.prototype.getContext; f.install(true);
  assert.equal(f.prototype.getContext, undefined); assert.equal(f.window.__gy315SetupProbe.stop().wrapped, false);
});
test('scope and actual producers keep exact CI partitions, native actions and original deadlines', () => {
  for (const size of ['phone-360', 'tablet-768']) assert.equal(setupDiagnosticScope('true', size, '/designer/sim.html'), true);
  for (const args of [['false', 'phone-360', '/designer/sim.html'], ['true', 'iphone-13', '/designer/sim.html'], ['true', 'phone-360,tablet-768', '/designer/sim.html'], ['true', 'phone-360', '/designer/build.html']]) assert.equal(setupDiagnosticScope(...args), false);
  const load = readFileSync(new URL('./layout/test-empty-space.mjs', import.meta.url), 'utf8');
  assert.match(load, /setupDiagnosticScope\(process\.env\.GITHUB_ACTIONS,sizes\.length===1\?sizes\[0\]\.name:'',route\)/);
  assert.match(load, /timeout: 30000/); assert.match(load, /Promise\.all\(\[page\.evaluate\(readReadinessState\),diagnostic\]\)/);
  const print = readFileSync(new URL('./assembly/test-build-workspace.mjs', import.meta.url), 'utf8');
  assert.match(print, /scope==='print'&&process\.env\.PRINT_CASE==='current'/);
  assert.match(print, /observedSummaryClick\(p,summary,\(\)=>summary\.click\(\),observations,\{part:name,ancestorStep:i\}\)/);
  assert.match(print, /p\.setDefaultTimeout\(30000\)/); assert.match(print, /await button\.focus\(\);await p\.keyboard\.press\('Enter'\)/);
  assert.doesNotMatch(print, /force:\s*true/);
});
const profile = () => ({nodes: [
  {id: 1, callFrame: {functionName: '(root)', url: ''}, children: [2, 3, 4, 5, 6, 7]},
  {id: 2, callFrame: {functionName: '(idle)', url: ''}},
  {id: 3, callFrame: {functionName: '(program)', url: ''}},
  {id: 4, callFrame: {functionName: '(garbage collector)', url: ''}},
  {id: 5, callFrame: {functionName: 'private-secret', url: 'https://site.fixture/designer/kit/stage.js?token=secret', lineNumber: 37, columnNumber: 2}},
  {id: 6, callFrame: {functionName: 'private-secret', url: 'file:///tmp/private-session/key.json'}},
  {id: 7, callFrame: {functionName: 'native-secret', url: ''}},
], samples: [2, 3, 4, 5, 6, 7, 99], timeDeltas: [5000, 5000, 5000, 5000, 5000, 5000, 1000000]});
test('actual reducer preserves idle/program/GC/native/missing classification and owned stack locations only', () => {
  const result = summarizeProfile(profile(), 'https://site.fixture'), text = JSON.stringify(result);
  for (const label of ['(idle)', '(program)', '(garbage collector)', 'native-or-unknown', 'missing', '/designer/kit/stage.js:38:3']) assert.ok(text.includes(label), label);
  assert.doesNotMatch(text, /secret|private-session|key\.json|file:|token=|site\.fixture/);
  assert.equal(result.samplingIntervalUs, 5000); assert.equal(result.samples, 7); assert.equal(result.buckets.length, 2);
  assert.equal(summarizeProfile({nodes: []}, 'https://site.fixture').incomplete, true);
  assert.equal(summarizeProfile({nodes: [], samples: new Array(120001), timeDeltas: []}, 'https://site.fixture').reason, 'profile-cap');
  const invalid = profile(); invalid.timeDeltas[0] = NaN; assert.equal(summarizeProfile(invalid, 'https://site.fixture').incomplete, true);
});
function protocolFixture({send, attach} = {}) {
  const log = [], session = {send: async (method, args) => {log.push([method, args]); return send ? send(method, args) : {profile: profile()};}, detach: async () => {log.push(['detach']);}};
  const page = {context: () => ({newCDPSession: async () => {log.push(['attach']); return attach ? attach(session) : session;}}),
    evaluate: async () => ({wrapped: true, restored: true, calls: [], heartbeat: []})};
  return {page, log};
}
test('one5ms profile starts/stops/detaches once and finish is idempotent', async () => {
  const f = protocolFixture(), probe = await startSetupDiagnostic(f.page, 'https://site.fixture');
  const first = probe.finish(); assert.equal(probe.finish(), first); const result = await first;
  assert.deepEqual(f.log.map(row => row[0]), ['attach', 'Profiler.enable', 'Profiler.setSamplingInterval', 'Profiler.start', 'Profiler.stop', 'detach']);
  assert.equal(f.log[2][1].interval, 5000); assert.equal(result.profile.available, true); assert.equal(result.errors.length, 0);
});
test('setup rejection fails open and original diagnostic records remain usable', async () => {
  const f = protocolFixture({send: () => {throw Error('file:///tmp/private-session/key.json');}});
  const probe = await startSetupDiagnostic(f.page, 'https://site.fixture'), result = await probe.finish();
  assert.equal(result.errors[0].phase, 'setup'); assert.equal(result.profile.available, false);
  assert.equal(f.log.filter(row => row[0] === 'detach').length, 1); assert.doesNotMatch(JSON.stringify(result), /private-session|key\.json/);
});
test('late attach is detached without enabling or starting a profile after setup timeout', async () => {
  let release; const f = protocolFixture({attach: session => new Promise(resolve => {release = () => resolve(session);})});
  const probe = await startSetupDiagnostic(f.page, 'https://site.fixture', {setupMs: 1});
  release(); await new Promise(resolve => setImmediate(resolve)); await probe.finish();
  assert.deepEqual(f.log.map(row => row[0]), ['attach', 'detach']);
});
test('stalled stop is bounded, detached once and explicit incomplete evidence survives', async () => {
  const f = protocolFixture({send: method => method === 'Profiler.stop' ? new Promise(() => {}) : {}});
  const probe = await startSetupDiagnostic(f.page, 'https://site.fixture', {finishMs: 1}), result = await probe.finish();
  assert.ok(result.errors.some(row => row.phase === 'finish-bound')); assert.equal(result.profile.incomplete, true);
  assert.equal(f.log.filter(row => row[0] === 'detach').length, 1);
});
test('setup timeout during a command never sends the next command and detaches its owned session', async () => {
  let release; const f = protocolFixture({send: method => method === 'Profiler.enable' ? new Promise(resolve => {release = resolve;}) : {}});
  const probe = await startSetupDiagnostic(f.page, 'https://site.fixture', {setupMs: 1});
  release({}); await probe.finish();
  assert.deepEqual(f.log.map(row => row[0]), ['attach', 'Profiler.enable', 'detach']);
});
test('during-click sampler captures changing geometry/open/scroll and caps at128 without actions', () => {
  const f = browserFixture(); let x = 10, scroll = 0; const details = {tagName: 'DETAILS', open: false, hidden: false, inert: false, parentElement: null};
  const element = {parentElement: details, isConnected: true, getBoundingClientRect: () => ({x, y: 2, width: 100, height: 20}), matches: () => false};
  f.fixture.document = {querySelector: () => ({hidden: false, get scrollTop() {return scroll;}}), activeElement: {tagName: 'BODY'}, readyState: 'complete', visibilityState: 'visible', hasFocus: () => true};
  Object.assign(f.fixture, {scrollX: 0, scrollY: 3, getComputedStyle: () => ({display: 'block', visibility: 'visible'}), element});
  vm.runInNewContext(`(${installSummaryProbe})(element)`, f.fixture);
  const tick = [...f.intervals.values()][0]; assert.equal(tick.ms, 250);
  for (let i = 0; i < 140; i++) {x++; scroll++; details.open = true; tick.fn();}
  const result = f.window.__gy315SummaryProbe.stop();
  assert.equal(result.before.ancestors[0].open, false); assert.equal(result.samples[0].ancestors[0].open, true);
  assert.equal(result.samples[0].rect[0], 11); assert.equal(result.samples.length, 128); assert.equal(result.dropped, 12);
  assert.equal(result.after.scroll[2], 140); assert.equal(f.intervals.size, 0); assert.equal(f.timers.size, 0);
  assert.equal(element.isConnected, true); assert.equal(f.fixture.document.activeElement.tagName, 'BODY');
});
test('original native click failure is rethrown unchanged after one stop, despite observer failure', async () => {
  const original = Error('original native30000ms click failure'), observations = []; let actions = 0, stops = 0;
  const page = {evaluate: async () => {stops++; throw Error('private diagnostic failure');}}, summary = {evaluate: async () => {}};
  await assert.rejects(observedSummaryClick(page, summary, async () => {actions++; throw original;}, observations), error => error === original);
  assert.equal(actions, 1); assert.equal(stops, 1); assert.deepEqual(observations[0].diagnosticErrors, ['after-unavailable']);
  assert.doesNotMatch(JSON.stringify(observations), /private diagnostic/);
});
test('during-click observation starts before the one native action and stops after it', async () => {
  const log = [], observations = [], summary = {evaluate: async () => log.push('sampler-start')}, page = {evaluate: async () => {log.push('sampler-stop'); return {samples: [{rect: [1, 2, 3, 4]}]};}};
  assert.equal(await observedSummaryClick(page, summary, async () => {log.push('click'); return 7;}, observations), 7);
  assert.deepEqual(log, ['sampler-start', 'click', 'sampler-stop']); assert.equal(observations[0].samples.samples.length, 1);
});
test('stalled before/after observers cannot suppress or repeat the actual action', async () => {
  let actions = 0; const observations = [], page = {evaluate: () => new Promise(() => {})}, summary = {evaluate: () => new Promise(() => {})};
  await observedSummaryClick(page, summary, async () => {actions++;}, observations, {boundMs: 1, part: 'private-secret', ancestorStep: -1});
  assert.equal(actions, 1); assert.deepEqual(observations[0].diagnosticErrors, ['before-unavailable', 'after-unavailable']);
  assert.equal(observations[0].part, null); assert.equal(observations[0].ancestorStep, null);
  assert.doesNotMatch(JSON.stringify(observations), /private-secret/);
});
