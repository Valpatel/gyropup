// The playground's leg limits (docs/leg-protection.md): the same command clamps and rates the balance firmware runs,
// so the sliders and the gamepad can only ask the 3D pup for what the real legs would do.
//
//   const limits = createLegLimits();            // the rates at once; the reach table once load() has read it
//   limits.load('../');                          // exports/leg/limits.json (python -m sim.leg_limits)
//   const cmd = limits.step(state, dt, robot.info); // the targets in state -> { height, pitch, rollMM, speed }, slewed
//   robot.setPose({ ...limits.fit({ height, pitch, rollMM: cmd.rollMM }, robot.info), wheel });
//
// Both inputs feed state.height (0..1), state.pitch (rad, nose-down +), state.rollMM (left leg longer +) and
// state.speed (m/s). step() moves the output toward them no faster than the firmware does; fit() then keeps each leg's
// length inside the commanded window at that lean: inside the hard stops by the soft margin and away from the
// five-bar's dead points (the firmware's gp_guard_clamp_L). It clamps; nothing is refused, as on the robot.
//
// The rates are firmware/balance/include/gp/gp_model.h's (tools/test-leg-limits.mjs checks they still are).

export const RATES = Object.freeze({
  heightFracPerS: 0.6,          // GP_G_HEIGHT_RATE: the controller's height (0..1 of H_MIN..H_MAX) per second
  hMinM: 0.185, hMaxM: 0.375,   // GP_H_MIN_M, GP_H_MAX_M: that height's span, so the rate in metres is the robot's
  leanRadPerS: 0.5,             // gp_ctl_step's look slew
  accelMPerS2: 1.5,             // GP_G_ACCEL
  speedMargin: 0.5,             // GP_G_SPEED_MARGIN x the wheel's no-load speed at the bus voltage
  wheelWPerV: 0.959931089,      // GP_WHEEL_W_PER_V
  wheelRM: 0.127,               // GP_WHEEL_R_M
  busV: 36,                     // the pack's nominal voltage (the rig and the jump sweep's)
});

export const legRateMMPerS = RATES.heightFracPerS * (RATES.hMaxM - RATES.hMinM) * 1000;   // 114 mm/s
export const vmaxMPerS = RATES.speedMargin * RATES.wheelWPerV * RATES.busV * RATES.wheelRM;  // 2.19 m/s

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const toward = (from, to, step) => from + clamp(to - from, -step, step);
const finite = (v, d) => (Number.isFinite(v) ? v : d);

// (L_min, L_max) in metres at a lean, linear between the table's rows; the end rows outside them (sim/leg_limits.py
// window_at). The table is [lean rad, L_min m, L_max m]; rows the leg cannot reach at all carry nulls.
export function windowAt(table, lean) {
  const rows = (table || []).filter((r) => r[1] != null);
  if (!rows.length) return null;
  if (lean <= rows[0][0]) return [rows[0][1], rows[0][2]];
  for (let k = 1; k < rows.length; k++) {
    const a = rows[k - 1], b = rows[k];
    if (lean <= b[0]) {
      const w = (lean - a[0]) / (b[0] - a[0]);
      return [a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2])];
    }
  }
  const z = rows[rows.length - 1];
  return [z[1], z[2]];
}

export function createLegLimits({ table = null } = {}) {
  let window = table, out = null;
  const api = {
    get ready() { return !!window; },
    get window() { return window; },
    // read the generated limits; a missing or bad file leaves the rates on and the reach unclamped (logged once)
    async load(root = '../', fetcher = globalThis.fetch) {
      try {
        const r = await fetcher(`${root}exports/leg/limits.json`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        const w = d?.command?.window;
        if (!Array.isArray(w) || !w.some((row) => Array.isArray(row) && row[1] != null)) throw new Error('no command window');
        window = w;
      } catch (e) { console.warn('leg limits: the reach table could not be read; rates only', e); }
      return api;
    },
    reset() { out = null; },
    // the targets -> the commanded pose, slewed at the firmware's rates in metres (info: the robot's hMin, hMax in mm;
    // the first call takes the targets as they are)
    step(target, dt = 0, info = null) {
      const t = {
        height: clamp(finite(target.height, 0.6), 0, 1),
        pitch: finite(target.pitch, 0),
        rollMM: finite(target.rollMM, 0),
        speed: clamp(finite(target.speed, 0), -vmaxMPerS, vmaxMPerS),
      };
      if (!out || !(dt > 0)) { out = out || { ...t }; return { ...out, limited: false }; }
      const span = info?.hMax - info?.hMin > 0 ? info.hMax - info.hMin : (RATES.hMaxM - RATES.hMinM) * 1000;   // this robot's 0..1 in mm
      const next = {
        height: toward(out.height, t.height, legRateMMPerS * dt / span),
        pitch: toward(out.pitch, t.pitch, RATES.leanRadPerS * dt),
        rollMM: toward(out.rollMM, t.rollMM, 2 * legRateMMPerS * dt),   // one leg up, the other down: each at the rate
        speed: toward(out.speed, t.speed, RATES.accelMPerS2 * dt),
      };
      const limited = next.height !== t.height || next.pitch !== t.pitch || next.rollMM !== t.rollMM || next.speed !== t.speed;
      out = next;
      return { ...next, limited };
    },
    // a pose -> the same pose with each leg inside the window at its lean (robot.info: hMin, hMax in mm)
    fit({ height, pitch = 0, rollMM = 0 }, info) {
      const hMin = info?.hMin, hMax = info?.hMax;
      const w = window && Number.isFinite(hMin) && Number.isFinite(hMax) ? windowAt(window, pitch) : null;
      if (!w) return { height, pitch, rollMM, windowed: false };
      const lo = Math.max(hMin, w[0] * 1000), hi = Math.min(hMax, w[1] * 1000);
      const h = hMin + (hMax - hMin) * height;
      const l = clamp(h + rollMM / 2, lo, hi), r = clamp(h - rollMM / 2, lo, hi);
      const windowed = l !== h + rollMM / 2 || r !== h - rollMM / 2;
      return { height: ((l + r) / 2 - hMin) / (hMax - hMin), pitch, rollMM: l - r, windowed };
    },
  };
  return api;
}
