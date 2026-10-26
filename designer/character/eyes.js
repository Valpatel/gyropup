// Gyropup's eyes: one canvas texture per round screen (the Waveshare DualEye module has two 160×160 displays).
// Expressions ease into each other, the eyes blink and drift their gaze. The same parameters can later drive the
// real screens from the eye controller.
//
// Expression set and easing adapted from the Moxie simulator's moxie/face.js (mvalancy/moxie-robot-saver, MIT,
// © 2026 moxie-robot-parent-app contributors). No mouth: Gyropup speaks with its eyes and its body.
import * as THREE from 'three';

// eyeW/eyeH: iris size; lid: upper lid closure (0 open, 1 shut); lower: lower lid (happy squint);
// tilt: lid slant (+ = inner corners down, cross; - = inner corners up, sad); pupilX/Y: gaze; glow: brightness.
export const EXPRESSIONS = {
  neutral:   { eyeW: 1.00, eyeH: 1.00, lid: 0.12, lower: 0.00, tilt: 0.0, pupilX: 0.0, pupilY: 0.0, glow: 1.0 },
  happy:     { eyeW: 1.05, eyeH: 0.95, lid: 0.05, lower: 0.55, tilt: 0.0, pupilX: 0.0, pupilY: -0.1, glow: 1.15 },
  curious:   { eyeW: 1.12, eyeH: 1.12, lid: 0.00, lower: 0.00, tilt: -0.2, pupilX: 0.25, pupilY: -0.2, glow: 1.1 },
  sleepy:    { eyeW: 1.00, eyeH: 1.00, lid: 0.72, lower: 0.10, tilt: 0.0, pupilX: 0.0, pupilY: 0.3, glow: 0.7 },
  sad:       { eyeW: 0.95, eyeH: 0.95, lid: 0.35, lower: 0.00, tilt: -0.6, pupilX: 0.0, pupilY: 0.45, glow: 0.8 },
  grumpy:    { eyeW: 1.00, eyeH: 0.90, lid: 0.40, lower: 0.15, tilt: 0.7, pupilX: 0.0, pupilY: 0.15, glow: 1.0 },
  surprised: { eyeW: 1.25, eyeH: 1.25, lid: 0.00, lower: 0.00, tilt: 0.0, pupilX: 0.0, pupilY: 0.0, glow: 1.3 },
  focused:   { eyeW: 0.85, eyeH: 0.85, lid: 0.30, lower: 0.20, tilt: 0.25, pupilX: 0.0, pupilY: 0.0, glow: 1.1 },
  thinking:  { eyeW: 0.95, eyeH: 0.95, lid: 0.25, lower: 0.0, tilt: -0.15, pupilX: 0.55, pupilY: -0.55, glow: 0.95 },
};

const SIZE = 256;

/** createEyes({ iris = '#55e9ff' }) -> { left, right, set(name), step(t, dt), draw(), params, expressions } */
export function createEyes(opts = {}) {
  const iris = new THREE.Color(opts.iris ?? '#55e9ff');
  const params = { ...EXPRESSIONS.neutral }, target = { ...EXPRESSIONS.neutral };
  const blink = { active: false, phase: 0, next: 2 + Math.random() * 3 };
  const gaze = { x: 0, y: 0, tx: 0, ty: 0, next: 1 };
  const make = () => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = SIZE;
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return { canvas, ctx: canvas.getContext('2d'), texture };
  };
  const left = make(), right = make();

  function step(t, dt) {
    const f = 1 - Math.exp(-dt * 8);
    for (const k of Object.keys(params)) params[k] += (target[k] - params[k]) * f;
    if (blink.active) {
      blink.phase += dt / 0.2;
      if (blink.phase >= 1) { blink.active = false; blink.next = t + (Math.random() < 0.15 ? 0.25 : 1.6 + Math.random() * 4); }
    } else if (t > blink.next) { blink.active = true; blink.phase = 0; }
    if (t > gaze.next) { gaze.tx = (Math.random() - 0.5) * 0.7; gaze.ty = (Math.random() - 0.5) * 0.4; gaze.next = t + 1 + Math.random() * 3; }
    const g = 1 - Math.exp(-dt * 6);
    gaze.x += (gaze.tx - gaze.x) * g;
    gaze.y += (gaze.ty - gaze.y) * g;
  }

  function drawOne({ ctx, texture }, side) {
    const P = params, c = SIZE / 2, R = SIZE / 2;
    const col = (k) => `rgb(${Math.round(255 * Math.min(1, iris.r * k))},${Math.round(255 * Math.min(1, iris.g * k))},${Math.round(255 * Math.min(1, iris.b * k))})`;
    ctx.fillStyle = '#05080b';
    ctx.fillRect(0, 0, SIZE, SIZE);
    const blinkF = blink.active ? Math.sin(Math.PI * blink.phase) : 0;
    const x = c + (P.pupilX + gaze.x) * 26, y = c + (P.pupilY + gaze.y) * 22;
    const rx = R * 0.5 * P.eyeW, ry = R * 0.58 * P.eyeH;
    ctx.save();
    ctx.shadowColor = col(1);
    ctx.shadowBlur = 30 * P.glow;
    const grad = ctx.createRadialGradient(x - rx * 0.25, y - ry * 0.3, 4, x, y, Math.max(rx, ry));
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.25, col(1.25 * P.glow));
    grad.addColorStop(1, col(0.55 * P.glow));
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    ctx.fillStyle = 'rgba(255,255,255,0.9)';          // shine
    ctx.beginPath();
    ctx.ellipse(x - rx * 0.3, y - ry * 0.35, rx * 0.18, ry * 0.14, -0.5, 0, Math.PI * 2);
    ctx.fill();
    // lids: dark shapes that close over the iris; tilt slants the upper lid toward the nose (side = -1 left, +1 right)
    const lid = Math.min(1, P.lid + blinkF * (1 - P.lid));
    const tilt = P.tilt * 40 * side;
    ctx.fillStyle = '#05080b';
    ctx.beginPath();
    ctx.moveTo(-10, -10); ctx.lineTo(SIZE + 10, -10);
    ctx.lineTo(SIZE + 10, y - ry + lid * 2.2 * ry - tilt);
    ctx.quadraticCurveTo(c, y - ry + lid * 2.2 * ry - ry * 0.25 * (1 - lid), -10, y - ry + lid * 2.2 * ry + tilt);
    ctx.closePath();
    ctx.fill();
    const low = P.lower + blinkF * 0.4;
    ctx.beginPath();
    ctx.moveTo(-10, SIZE + 10); ctx.lineTo(SIZE + 10, SIZE + 10);
    ctx.lineTo(SIZE + 10, y + ry - low * 1.2 * ry);
    ctx.quadraticCurveTo(c, y + ry - low * 1.2 * ry - ry * 0.6 * low, -10, y + ry - low * 1.2 * ry);
    ctx.closePath();
    ctx.fill();
    // round screen edge
    const v = ctx.createRadialGradient(c, c, R * 0.7, c, c, R);
    v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.85)');
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, SIZE, SIZE);
    texture.needsUpdate = true;
  }

  return {
    left, right, params, expressions: Object.keys(EXPRESSIONS), step,
    draw() { drawOne(left, -1); drawOne(right, 1); },
    set(name) { Object.assign(target, EXPRESSIONS[name] ?? EXPRESSIONS.neutral); },
  };
}

/** A small SVG of an expression (both eyes), for buttons. */
export function eyesGlyph(name) {
  const P = EXPRESSIONS[name] ?? EXPRESSIONS.neutral;
  let s = '';
  for (const side of [-1, 1]) {
    const cx = 50 + side * 24 + P.pupilX * 6, cy = 50 + P.pupilY * 6, rx = 15 * P.eyeW, ry = 18 * P.eyeH;
    const top = cy - ry + P.lid * 2.2 * ry, bottom = cy + ry - P.lower * 1.2 * ry, tilt = P.tilt * 10 * side;
    s += `<clipPath id="c${name}${side}"><path d="M0 ${top + tilt} L100 ${top - tilt} L100 ${bottom} L0 ${bottom} Z"/></clipPath>`
      + `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="currentColor" clip-path="url(#c${name}${side})"/>`;
  }
  return `<svg viewBox="10 20 80 60" aria-hidden="true">${s}</svg>`;
}
