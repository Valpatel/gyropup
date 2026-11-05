// A live Xbox-layout controller diagram in SVG: pressed buttons light up, sticks move, triggers fill.
// Drawn here from simple shapes (no external artwork) and styled from gamepad.css custom properties.
// MIT licensed (LICENSE in this folder).
import { BUTTONS } from './gamepad.js';

const NS = 'http://www.w3.org/2000/svg';
const STICK_TRAVEL = 13;
let serial = 0;   // unique clip ids; never Math.random, so seeded pages keep their random sequence

// Layout in a 400 x 260 view box: left stick high and D-pad low on the left, ABXY high and right stick low on the
// right, as on an Xbox controller.
const FACE = { A: [292, 138, 'a'], B: [316, 114, 'b'], X: [268, 114, 'x'], Y: [292, 90, 'y'] };
const BODY = 'M120 58C82 58 52 74 39 110C23 160 15 214 41 237C63 255 93 236 112 206C122 190 140 182 160 182H240'
  + 'C260 182 278 190 288 206C307 236 337 255 359 237C385 214 377 160 361 110C348 74 318 58 280 58C256 58 244 66 200 66'
  + 'C156 66 144 58 120 58Z';

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  parent?.appendChild(node);
  return node;
}

/** createDiagram({ title }) -> { element, update(pad | null), highlight(inputs) } */
export function createDiagram({ title = 'Controller' } = {}) {
  const svg = el('svg', { viewBox: '0 0 400 260', class: 'gpad-diagram gpad-diagram--idle', role: 'img', 'aria-label': `${title} diagram` });
  el('title', {}, svg).textContent = `${title}: live buttons, sticks and triggers`;
  const parts = {};
  const mark = (node, input) => { node.dataset.input = input; parts[input] = node; return node; };

  for (const [side, x] of [['LT', 76], ['RT', 266]]) {
    const g = mark(el('g', { class: 'gpad-trigger' }, svg), side);
    el('rect', { x, y: 12, width: 58, height: 26, rx: 8, class: 'gpad-shape' }, g);
    const clip = el('clipPath', { id: `gpad-clip-${side}-${++serial}` }, svg);
    el('rect', { x, y: 12, width: 58, height: 26, rx: 8 }, clip);
    g.fill = el('rect', { x, y: 38, width: 58, height: 0, class: 'gpad-fill', 'clip-path': `url(#${clip.id})` }, g);
    el('text', { x: x + 29, y: 30, class: 'gpad-label' }, g).textContent = side;
  }
  for (const [side, x] of [['LB', 70], ['RB', 258]]) {
    const g = mark(el('g', { class: 'gpad-button' }, svg), side);
    el('rect', { x, y: 42, width: 72, height: 14, rx: 7, class: 'gpad-shape' }, g);
    el('text', { x: x + 36, y: 52.5, class: 'gpad-label gpad-label--small' }, g).textContent = side;
  }
  el('path', { d: BODY, class: 'gpad-body' }, svg);

  const sticks = {};
  for (const [stick, cx, cy, click] of [['Left', 110, 114, 'LS'], ['Right', 250, 168, 'RS']]) {
    el('circle', { cx, cy, r: 29, class: 'gpad-well' }, svg);
    const knob = mark(el('g', { class: 'gpad-stick' }, svg), click);
    el('circle', { cx, cy, r: 18, class: 'gpad-shape' }, knob);
    el('circle', { cx, cy, r: 3, class: 'gpad-dot' }, knob);
    sticks[stick] = knob;
  }
  for (const [dir, x, y] of [['Up', 141, 141], ['Down', 141, 177], ['Left', 123, 159], ['Right', 159, 159]]) {
    const g = mark(el('g', { class: 'gpad-button gpad-dpad' }, svg), dir);
    el('rect', { x, y, width: 18, height: 18, rx: 3, class: 'gpad-shape' }, g);
  }
  el('rect', { x: 141, y: 159, width: 18, height: 18, class: 'gpad-dpad-hub' }, svg);
  for (const [name, [cx, cy, cls]] of Object.entries(FACE)) {
    const g = mark(el('g', { class: `gpad-button gpad-face gpad-face--${cls}` }, svg), name);
    el('circle', { cx, cy, r: 12, class: 'gpad-shape' }, g);
    el('text', { x: cx, y: cy + 4.5, class: 'gpad-label' }, g).textContent = name;
  }
  for (const [name, x] of [['View', 168], ['Menu', 220]]) {
    const g = mark(el('g', { class: 'gpad-button gpad-small' }, svg), name);
    el('rect', { x, y: 106, width: 12, height: 12, rx: 6, class: 'gpad-shape' }, g);
  }
  const guide = mark(el('g', { class: 'gpad-button gpad-guide' }, svg), 'Guide');
  el('circle', { cx: 200, cy: 86, r: 12, class: 'gpad-shape' }, guide);

  function update(pad) {
    svg.classList.toggle('gpad-diagram--idle', !pad);
    for (const name of BUTTONS) {
      const node = parts[name], b = pad?.buttons[name];
      node?.classList.toggle('on', !!b?.pressed);
      if (node?.fill) {
        const h = 26 * (b?.value ?? 0);
        node.fill.setAttribute('y', String(38 - h)); node.fill.setAttribute('height', String(h));
      }
    }
    for (const [stick, knob] of Object.entries(sticks)) {
      const x = pad?.axes[`${stick}X`] ?? 0, y = pad?.axes[`${stick}Y`] ?? 0;
      knob.setAttribute('transform', `translate(${(x * STICK_TRAVEL).toFixed(2)} ${(y * STICK_TRAVEL).toFixed(2)})`);
      knob.classList.toggle('moved', Math.hypot(x, y) > 0);
    }
  }
  /** Outline the inputs of one binding (while choosing or rebinding it). */
  function highlight(inputs = []) {
    const set = new Set(inputs.map((i) => (/^Left[XY]$/.test(i) ? 'LS' : /^Right[XY]$/.test(i) ? 'RS' : i)));
    for (const [name, node] of Object.entries(parts)) node.classList.toggle('focus', set.has(name));
  }
  update(null);
  return { element: svg, update, highlight };
}
