import assert from 'node:assert/strict';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { observeTalkViewport, readTalkViewport } from './talk-viewport-observation.mjs';

function fixture(expected = [568, 320]) {
  let now = 0;
  const resizeListeners = new Set(), frameCallbacks = new Set();
  const canvas = { clientWidth: 390, clientHeight: 844, width: 390, height: 844 };
  const renderer = { domElement: canvas, getPixelRatio: () => 1, info: { render: { frame: 15 } } };
  const camera = { aspect: 390 / 844, view: { enabled: true, fullWidth: 390, fullHeight: 844 } };
  const stage = { renderer, camera, onFrame(cb) { frameCallbacks.add(cb); return () => frameCallbacks.delete(cb); } };
  const window = { __talkDemo: { stage }, addEventListener: (_, cb) => resizeListeners.add(cb), removeEventListener: (_, cb) => resizeListeners.delete(cb) };
  const env = { window, innerWidth: 390, innerHeight: 844, performance: { now: () => now } };
  runInNewContext(`(${observeTalkViewport})({width:${expected[0]},height:${expected[1]},settleMs:800})`, env);
  return { env, canvas, renderer, camera, resizeListeners, frameCallbacks,
    at: ms => { now = ms; },
    cssLandscape() { env.innerWidth = canvas.clientWidth = 568; env.innerHeight = canvas.clientHeight = 320; },
    resized() { for (const cb of [...resizeListeners]) cb(); },
    projection() { canvas.width = 568; canvas.height = 320; camera.aspect = 568 / 320; camera.view.fullWidth = 568; camera.view.fullHeight = 320; },
    draw(render = true) { for (const cb of [...frameCallbacks]) cb(); if (render) renderer.info.render.frame++; },
    ready: () => runInNewContext(`(${readTalkViewport})()`, env),
    stop: () => window.__portalTalkViewport.stop(),
  };
}

test('new CSS dimensions alone cannot certify a Talk resize or a new projection', () => {
  const f = fixture();
  f.cssLandscape(); f.at(1500); f.draw();
  assert.equal(f.ready(), false, 'A real render without the resize event is insufficient');
  f.resized(); f.at(2300); f.draw();
  assert.equal(f.ready(), false, 'The old canvas buffer and projection are still visible to the observer');
  f.canvas.width = 568; f.canvas.height = 320; f.draw();
  assert.equal(f.ready(), false, 'A new buffer still needs the new camera projection');
  f.projection(); f.draw(false);
  assert.equal(f.ready(), false, 'Matching dimensions without the actual draw are insufficient');
  f.draw();
  assert.equal(f.ready(), true);
  assert.equal(f.resizeListeners.size, 0);
  assert.equal(f.frameCallbacks.size, 0);
});

test('the existing settle time starts at the matching resize and also applies at the same size', () => {
  const f = fixture();
  f.resized();
  assert.equal(f.resizeListeners.size, 1, 'An unrelated resize does not consume the witness');
  f.at(1000); f.cssLandscape(); f.projection(); f.resized();
  f.at(1799); f.draw(); assert.equal(f.ready(), false);
  f.at(1800); f.draw(); assert.equal(f.ready(), true);
  const same = fixture([390, 844]);
  assert.equal(same.resizeListeners.size, 0);
  same.at(799); same.draw(); assert.equal(same.ready(), false);
  same.at(800); assert.equal(same.ready(), false);
  same.draw(); assert.equal(same.ready(), true);
});

test('cancelling removes the pending resize and stage callbacks', () => {
  const f = fixture();
  f.stop();
  assert.equal(f.resizeListeners.size, 0);
  assert.equal(f.frameCallbacks.size, 0);
  f.cssLandscape(); f.projection(); f.resized(); f.at(3000); f.draw();
  assert.equal(f.ready(), false);
});
