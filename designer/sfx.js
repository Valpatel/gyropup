// Gyropup's sound effects, synthesised with Web Audio (no sound files): the ball launcher's flywheels spinning up, the
// feed dial and the shot, foam balls bopping a plate, a plate clattering over, the laser arming, the turret servos, the
// wheel motors, the dock pouring balls into the hopper, and the pup's little victory chirp.
//
// Browsers only start audio after a click or key press, so the context is created on the first gesture.
// createSfx() -> { enabled, setEnabled(on), unlock(), shot(), hit(), down(), laser(on), flywheels(on), reload(),
//                  chirp(), motion({ wheelSpeed, servoSpeed }) }

export function createSfx({ key = 'gyropup-sfx', volume = 0.55 } = {}) {
  let ctx = null, out = null, noiseBuf = null, enabled = true;
  try { enabled = localStorage.getItem(key) !== '0'; } catch { /* storage blocked */ }
  const hum = {};     // continuous voices: flywheels, servos, wheel motors

  function unlock() {
    if (!enabled) return null;
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      const comp = ctx.createDynamicsCompressor();
      comp.threshold.value = -14;
      comp.ratio.value = 6;
      out = ctx.createGain();
      out.gain.value = volume;
      out.connect(comp).connect(ctx.destination);
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const ch = noiseBuf.getChannelData(0);
      for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
      startHums();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  for (const ev of ['pointerdown', 'keydown']) window.addEventListener(ev, () => unlock(), { passive: true });
  const live = () => (enabled && ctx && ctx.state === 'running' ? ctx : null);

  // ---- building blocks
  function env(g, t0, peak, attack, decay) {
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + decay);
  }
  function noise(t0, { type = 'bandpass', freq = 1200, q = 1, peak = 0.5, attack = 0.002, decay = 0.08, sweepTo = null, dest = out }) {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuf;
    src.playbackRate.value = 0.8 + Math.random() * 0.4;
    const f = ctx.createBiquadFilter();
    f.type = type;
    f.frequency.setValueAtTime(freq, t0);
    if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t0 + attack + decay);
    f.Q.value = q;
    const g = ctx.createGain();
    env(g, t0, peak, attack, decay);
    src.connect(f).connect(g).connect(dest);
    src.start(t0, Math.random() * 0.5);
    src.stop(t0 + attack + decay + 0.05);
  }
  function tone(t0, { type = 'sine', from = 440, to = null, peak = 0.3, attack = 0.003, decay = 0.1, dest = out }) {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(from, t0);
    if (to) o.frequency.exponentialRampToValueAtTime(to, t0 + attack + decay);
    const g = ctx.createGain();
    env(g, t0, peak, attack, decay);
    o.connect(g).connect(dest);
    o.start(t0);
    o.stop(t0 + attack + decay + 0.05);
  }
  function startHums() {
    const voice = (type, freq, cutoff) => {
      const o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      o.type = type;
      o.frequency.value = freq;
      f.type = 'lowpass';
      f.frequency.value = cutoff;
      g.gain.value = 0;
      o.connect(f).connect(g).connect(out);
      o.start();
      return { o, f, g };
    };
    hum.fly = [voice('sawtooth', 90, 900), voice('sawtooth', 91.5, 900)];    // two flywheels, slightly apart
    hum.servo = voice('square', 520, 1400);
    hum.wheel = voice('triangle', 60, 500);
  }

  return {
    get enabled() { return enabled; },
    setEnabled(on) {
      enabled = Boolean(on);
      try { localStorage.setItem(key, enabled ? '1' : '0'); } catch { /* storage blocked */ }
      if (enabled) unlock(); else ctx?.suspend();
    },
    unlock,
    /** The shot: the feed dial steps a ball into the flywheels, they squeeze it with a round "pomp", and it whooshes out. */
    shot() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      tone(t, { type: 'square', from: 700, to: 420, peak: 0.07, decay: 0.025 });              // dial step (geared motor)
      noise(t, { type: 'highpass', freq: 3500, peak: 0.08, decay: 0.012 });                    // the pocket's tick
      tone(t + 0.03, { from: 210, to: 70, peak: 0.85, decay: 0.12 });                          // pomp: the ball through the wheels
      noise(t + 0.03, { freq: 1500, q: 0.8, peak: 0.45, decay: 0.09, sweepTo: 450 });          // whoosh
      noise(t + 0.035, { type: 'highpass', freq: 4200, peak: 0.08, decay: 0.04 });             // tyre scuff
      for (const v of hum.fly ?? []) {                                                          // the wheels dip as the ball passes
        v.o.frequency.setTargetAtTime(v.o.frequency.value * 0.76, t + 0.03, 0.012);
        v.o.frequency.setTargetAtTime(v.o.frequency.value, t + 0.08, 0.07);
      }
    },
    /** A foam ball bopping a plate: soft and hollow, and the plate rings a little. */
    hit() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      noise(t, { freq: 620, q: 1.3, peak: 0.6, decay: 0.06 });
      tone(t, { type: 'triangle', from: 260, to: 150, peak: 0.4, decay: 0.09 });
      tone(t + 0.01, { from: 1250, to: 1150, peak: 0.05, decay: 0.15 });                      // the plate
    },
    /** A plate knocked over: a clatter of knocks, then a thud. */
    down() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      let at = t, amp = 0.5;
      for (let k = 0; k < 4; k++) {
        noise(at, { freq: 700 + Math.random() * 900, q: 3, peak: amp, decay: 0.05 });
        tone(at, { type: 'triangle', from: 260 + Math.random() * 120, peak: amp * 0.5, decay: 0.05 });
        at += 0.06 + Math.random() * 0.07;
        amp *= 0.6;
      }
      tone(t + 0.02, { from: 95, to: 55, peak: 0.6, decay: 0.18 });
    },
    /** Laser arming (rising blip) or off (falling). */
    laser(on) {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      if (on) { tone(t, { from: 1500, to: 2600, peak: 0.12, decay: 0.07 }); tone(t + 0.08, { from: 2600, peak: 0.07, decay: 0.05 }); }
      else tone(t, { from: 1800, to: 900, peak: 0.08, decay: 0.08 });
    },
    /** Flywheels spinning up (on) or coasting down (off). */
    flywheels(on) {
      const c = live(); if (!c || !hum.fly) return;
      const t = c.currentTime;
      for (const [i, v] of hum.fly.entries()) {
        v.o.frequency.cancelScheduledValues(t);
        v.g.gain.cancelScheduledValues(t);
        v.o.frequency.setValueAtTime(v.o.frequency.value, t);
        v.g.gain.setValueAtTime(v.g.gain.value, t);
        if (on) {
          v.o.frequency.exponentialRampToValueAtTime(410 + 6 * i, t + 0.35);
          v.g.gain.linearRampToValueAtTime(0.05, t + 0.15);
        } else {
          v.o.frequency.exponentialRampToValueAtTime(60, t + 1.4);
          v.g.gain.linearRampToValueAtTime(0, t + 1.4);
        }
      }
    },
    /** Refill at the dock: balls tumble into the hopper (a patter of soft knocks), then the fill flap snaps shut. */
    reload() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      let at = t;
      for (let k = 0; k < 14; k++) {
        noise(at, { freq: 900 + Math.random() * 1100, q: 2.5, peak: 0.22 * (1 - k / 20), decay: 0.025 });
        at += 0.025 + Math.random() * 0.04;
      }
      tone(at + 0.06, { type: 'square', from: 900, to: 500, peak: 0.15, decay: 0.03 });
    },
    /** The pup's happy chirp. */
    chirp() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      tone(t, { from: 900, to: 1700, peak: 0.12, decay: 0.08 });
      tone(t + 0.1, { from: 1300, to: 2300, peak: 0.12, decay: 0.07 });
      tone(t + 0.19, { from: 2000, to: 1500, peak: 0.1, decay: 0.09 });
    },
    /** Continuous motor sounds: wheel speed in m/s, turret servo speed in rad/s. Call every frame. */
    motion({ wheelSpeed = 0, servoSpeed = 0 } = {}) {
      const c = live(); if (!c || !hum.wheel) return;
      const t = c.currentTime, ws = Math.min(2, Math.abs(wheelSpeed)), ss = Math.min(6, Math.abs(servoSpeed));
      hum.wheel.o.frequency.setTargetAtTime(55 + 140 * ws, t, 0.05);
      hum.wheel.g.gain.setTargetAtTime(0.05 * Math.min(1, ws * 1.5), t, 0.08);
      hum.servo.o.frequency.setTargetAtTime(380 + 160 * ss, t, 0.03);
      hum.servo.g.gain.setTargetAtTime(ss > 0.15 ? 0.018 * Math.min(1, ss / 2) : 0, t, 0.03);
    },
  };
}
