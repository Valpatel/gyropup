// Gyropup's sound effects, synthesised with Web Audio (no sound files): the ball launcher's flywheels spinning up, the
// feed dial and the shot, foam balls bopping a plate, a plate clattering over, the laser arming, the turret servos, the
// wheel motors, the dock pouring balls into the hopper, and the pup's little victory chirp.
//
// The turret is the loudest thing on the page (the voice plays under it, character/talk.js): the effects go through a
// gentle glue compressor and a brick-wall limiter at full level, and the launcher's sounds also feed a short synthetic
// room, so a shot has a crack, a thump, the squeeze through the wheels and a whoosh that carries.
//
// Browsers only start audio after a click or key press, so the context is created on the first gesture.
// createSfx() -> { enabled, setEnabled(on), unlock(), shot(), hit(), down(), laser(on), flywheels(on), reload(),
//                  chirp(), motion({ wheelSpeed, servoSpeed, legSpeed }) }

export function createSfx({ key = 'gyropup-sfx', volume = 1.0 } = {}) {
  let ctx = null, out = null, room = null, noiseBuf = null, enabled = true;
  try { enabled = localStorage.getItem(key) !== '0'; } catch { /* storage blocked */ }
  const hum = {};     // continuous voices: flywheels, servos, wheel motors

  function unlock() {
    if (!enabled) return null;
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      // glue (slow, gentle) then a brick wall, so the shots can be loud without clipping
      const glue = ctx.createDynamicsCompressor();
      glue.threshold.value = -10; glue.ratio.value = 3; glue.attack.value = 0.004; glue.release.value = 0.18; glue.knee.value = 8;
      const wall = ctx.createDynamicsCompressor();
      wall.threshold.value = -1.5; wall.ratio.value = 20; wall.attack.value = 0.001; wall.release.value = 0.06; wall.knee.value = 0;
      out = ctx.createGain();
      out.gain.value = volume;
      out.connect(glue).connect(wall).connect(ctx.destination);
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const ch = noiseBuf.getChannelData(0);
      for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
      room = makeRoom();
      startHums();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  for (const ev of ['pointerdown', 'keydown', 'touchstart']) window.addEventListener(ev, () => unlock(), { passive: true });
  const live = () => (enabled && ctx && ctx.state === 'running' ? ctx : null);

  // a short room (0.7 s, stereo, darkening as it decays): the launcher's sounds send to it
  function makeRoom() {
    const len = Math.floor(ctx.sampleRate * 0.7);
    const ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = ir.getChannelData(c);
      let lp = 0;
      for (let i = 0; i < len; i++) {
        const k = i / len;
        lp += (Math.random() * 2 - 1 - lp) * (0.6 - 0.45 * k);            // darker as it fades
        d[i] = lp * Math.pow(1 - k, 2.4) * (i < 90 ? i / 90 : 1);
      }
    }
    const conv = ctx.createConvolver();
    conv.buffer = ir;
    const g = ctx.createGain();
    g.gain.value = 0.32;
    conv.connect(g).connect(out);
    return conv;
  }

  // ---- building blocks
  function env(g, t0, peak, attack, decay) {
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0002), t0 + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + decay);
  }
  function sends(g, wet) {
    g.connect(out);
    if (wet && room) { const s = ctx.createGain(); s.gain.value = wet; g.connect(s).connect(room); }
  }
  function noise(t0, { type = 'bandpass', freq = 1200, q = 1, peak = 0.5, attack = 0.002, decay = 0.08, sweepTo = null, wet = 0 }) {
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
    src.connect(f).connect(g);
    sends(g, wet);
    src.start(t0, Math.random() * 0.5);
    src.stop(t0 + attack + decay + 0.05);
  }
  function tone(t0, { type = 'sine', from = 440, to = null, peak = 0.3, attack = 0.003, decay = 0.1, wet = 0 }) {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(from, t0);
    if (to) o.frequency.exponentialRampToValueAtTime(to, t0 + attack + decay);
    const g = ctx.createGain();
    env(g, t0, peak, attack, decay);
    o.connect(g);
    sends(g, wet);
    o.start(t0);
    o.stop(t0 + attack + decay + 0.05);
  }
  function startHums() {
    const voice = (type, freq, cutoff, wet = 0) => {
      const o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      o.type = type;
      o.frequency.value = freq;
      f.type = 'lowpass';
      f.frequency.value = cutoff;
      g.gain.value = 0;
      o.connect(f).connect(g);
      sends(g, wet);
      o.start();
      return { o, f, g };
    };
    // the two flywheels a little apart (they beat), a sub an octave down, and the air they move
    hum.fly = [voice('sawtooth', 90, 2400, 0.15), voice('sawtooth', 91.5, 2400, 0.15)];
    hum.flySub = voice('square', 45, 600);
    const air = ctx.createBufferSource(), af = ctx.createBiquadFilter(), ag = ctx.createGain();
    air.buffer = noiseBuf; air.loop = true;
    af.type = 'bandpass'; af.frequency.value = 900; af.Q.value = 0.9;
    ag.gain.value = 0;
    air.connect(af).connect(ag).connect(out);
    air.start();
    hum.air = { f: af, g: ag };
    hum.servo = voice('square', 520, 2200);
    // the hub motors: a beating sawtooth pair through a resonant filter, a third harmonic, and road rumble
    hum.wheel = [voice('sawtooth', 70, 900), voice('sawtooth', 71.3, 900)];
    for (const v of hum.wheel) v.f.Q.value = 6;
    hum.wheel3 = voice('sine', 210, 4000);
    const rum = ctx.createBufferSource(), rf = ctx.createBiquadFilter(), rg = ctx.createGain();
    rum.buffer = noiseBuf; rum.loop = true; rum.playbackRate.value = 0.5;
    rf.type = 'lowpass'; rf.frequency.value = 180; rg.gain.value = 0;
    rum.connect(rf).connect(rg).connect(out);
    rum.start();
    hum.rumble = rg;
    // the leg motors (RS-04, a 9:1 planetary): gear whine that climbs with the joints' speed
    hum.leg = [voice('sawtooth', 180, 1800), voice('square', 361, 2600)];
    hum.last = { wheel: 0, leg: 0, t: 0 };
  }
  const jitter = (v, p = 0.06) => v * (1 + (Math.random() * 2 - 1) * p);

  return {
    get enabled() { return enabled; },
    setEnabled(on) {
      enabled = Boolean(on);
      try { localStorage.setItem(key, enabled ? '1' : '0'); } catch { /* storage blocked */ }
      if (enabled) unlock(); else ctx?.suspend();
    },
    unlock,
    /** The shot: the dial clicks a ball into the wheels, they crack and thump it out with a squeeze, it whooshes away
     *  into the room, and the flywheels' whine dips and climbs back. Each shot a little different. */
    shot() {
      const c = live(); if (!c) return;
      const t = c.currentTime, p = jitter(1, 0.07);
      tone(t, { type: 'square', from: 760 * p, to: 430 * p, peak: 0.14, decay: 0.022 });                // the dial steps
      noise(t, { type: 'highpass', freq: 3800, peak: 0.12, decay: 0.012 });                               // the pocket's tick
      const s = t + 0.028;
      noise(s, { type: 'highpass', freq: 2600 * p, q: 0.7, peak: 1.0, attack: 0.0008, decay: 0.035, wet: 0.5 });   // crack
      tone(s, { from: 160 * p, to: 42, peak: 1.0, attack: 0.002, decay: 0.2 });                            // thump
      tone(s, { type: 'triangle', from: 330 * p, to: 115, peak: 0.55, decay: 0.09 });                      // the squeeze
      noise(s + 0.006, { freq: 3200 * p, q: 0.75, peak: 0.75, decay: 0.26, sweepTo: 420, wet: 0.9 });     // whoosh
      noise(s + 0.01, { type: 'highpass', freq: 5200, peak: 0.16, decay: 0.05 });                         // tyre scuff
      for (const v of hum.fly ?? []) {                                                                    // the wheels dip and recover
        const f0 = v.o.frequency.value;
        v.o.frequency.setTargetAtTime(f0 * 0.72, s, 0.01);
        v.o.frequency.setTargetAtTime(f0, s + 0.06, 0.09);
      }
      if (hum.air) { hum.air.g.gain.setTargetAtTime(0.32, s, 0.005); hum.air.g.gain.setTargetAtTime(0.14, s + 0.05, 0.08); }
    },
    /** A foam ball bopping a plate: a hollow bop and a thud, and the plate rings. */
    hit() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      noise(t, { freq: jitter(640), q: 1.3, peak: 0.95, decay: 0.07, wet: 0.5 });
      tone(t, { type: 'triangle', from: jitter(280), to: 140, peak: 0.7, decay: 0.11 });
      tone(t + 0.01, { from: jitter(1250), to: 1150, peak: 0.14, decay: 0.32, wet: 0.6 });               // the plate rings
    },
    /** A plate knocked over: a clatter of knocks, then a thud that carries. */
    down() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      let at = t, amp = 0.85;
      for (let k = 0; k < 5; k++) {
        noise(at, { freq: 700 + Math.random() * 900, q: 3, peak: amp, decay: 0.06, wet: 0.4 });
        tone(at, { type: 'triangle', from: 240 + Math.random() * 140, peak: amp * 0.55, decay: 0.06 });
        at += 0.055 + Math.random() * 0.07;
        amp *= 0.65;
      }
      tone(t + 0.02, { from: 110, to: 48, peak: 0.9, decay: 0.26, wet: 0.5 });
    },
    /** Laser arming (rising blip) or off (falling). */
    laser(on) {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      if (on) { tone(t, { from: 1500, to: 2600, peak: 0.16, decay: 0.07 }); tone(t + 0.08, { from: 2600, peak: 0.09, decay: 0.05 }); }
      else tone(t, { from: 1800, to: 900, peak: 0.1, decay: 0.08 });
    },
    /** Flywheels spinning up (a rising, beating whine with a sub and rushing air) or coasting down. */
    flywheels(on) {
      const c = live(); if (!c || !hum.fly) return;
      const t = c.currentTime;
      const ramp = (param, to, dt, lin = false) => {
        param.cancelScheduledValues(t);
        param.setValueAtTime(param.value, t);
        if (lin) param.linearRampToValueAtTime(to, t + dt); else param.exponentialRampToValueAtTime(Math.max(to, 0.0001), t + dt);
      };
      for (const [i, v] of hum.fly.entries()) {
        if (on) { ramp(v.o.frequency, 560 + 7 * i, 0.55); ramp(v.g.gain, 0.2, 0.25, true); }
        else { ramp(v.o.frequency, 55, 1.8); ramp(v.g.gain, 0, 1.8, true); }
      }
      if (on) { ramp(hum.flySub.o.frequency, 280, 0.55); ramp(hum.flySub.g.gain, 0.08, 0.3, true); ramp(hum.air.f.frequency, 2600, 0.55); ramp(hum.air.g.gain, 0.14, 0.3, true); }
      else { ramp(hum.flySub.o.frequency, 28, 1.8); ramp(hum.flySub.g.gain, 0, 1.6, true); ramp(hum.air.f.frequency, 400, 1.8); ramp(hum.air.g.gain, 0, 1.6, true); }
    },
    /** Refill at the dock: balls tumble into the hopper (a patter of soft knocks), then the fill flap snaps shut. */
    reload() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      let at = t;
      for (let k = 0; k < 16; k++) {
        noise(at, { freq: 900 + Math.random() * 1100, q: 2.5, peak: 0.45 * (1 - k / 22), decay: 0.03, wet: 0.3 });
        at += 0.025 + Math.random() * 0.04;
      }
      tone(at + 0.06, { type: 'square', from: 900, to: 500, peak: 0.25, decay: 0.035 });
    },
    /** The pup's happy chirp. */
    chirp() {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      tone(t, { from: 900, to: 1700, peak: 0.14, decay: 0.08 });
      tone(t + 0.1, { from: 1300, to: 2300, peak: 0.14, decay: 0.07 });
      tone(t + 0.19, { from: 2000, to: 1500, peak: 0.12, decay: 0.09 });
    },
    /** Continuous motor sounds, with a kick when they bite: wheel speed in m/s (signed), turret servo speed and the leg
     *  joints' speed in rad/s. Call every frame. */
    motion({ wheelSpeed = 0, servoSpeed = 0, legSpeed = 0 } = {}) {
      const c = live(); if (!c || !hum.wheel) return;
      const t = c.currentTime, ws = Math.min(2.5, Math.abs(wheelSpeed)), ss = Math.min(6, Math.abs(servoSpeed));
      const ls = Math.min(12, Math.abs(legSpeed));
      const dt = Math.max(1e-3, t - (hum.last.t || t - 0.016));
      // the drive: pitch with speed, louder and brighter as it goes
      for (const [i, v] of hum.wheel.entries()) {
        v.o.frequency.setTargetAtTime((62 + 230 * ws) * (1 + 0.018 * i), t, 0.04);
        v.f.frequency.setTargetAtTime(500 + 1600 * Math.min(1, ws), t, 0.06);
        v.g.gain.setTargetAtTime(0.16 * Math.min(1, ws * 1.4), t, 0.06);
      }
      hum.wheel3.o.frequency.setTargetAtTime(3 * (62 + 230 * ws), t, 0.04);
      hum.wheel3.g.gain.setTargetAtTime(0.05 * Math.min(1, ws * 1.4), t, 0.06);
      hum.rumble.gain.setTargetAtTime(0.22 * Math.min(1, ws), t, 0.1);
      // the kick: a hard change of wheel speed (or a leg reversing) thumps through the frame, with a gear clack
      const acc = Math.abs(wheelSpeed - hum.last.wheel) / dt;
      if (acc > 1.6 && t - (hum.last.kick || 0) > 0.25) {
        hum.last.kick = t;
        const k = Math.min(1, acc / 5);
        tone(t, { from: 95, to: 38, peak: 0.55 * k + 0.2, attack: 0.003, decay: 0.16, wet: 0.2 });
        noise(t, { freq: 1300, q: 2, peak: 0.25 * k + 0.08, decay: 0.03 });
      }
      if (Math.sign(legSpeed) !== Math.sign(hum.last.leg) && Math.abs(hum.last.leg) > 1.5 && t - (hum.last.legKick || 0) > 0.2) {
        hum.last.legKick = t;
        tone(t, { type: 'triangle', from: 140, to: 60, peak: 0.3, decay: 0.08 });
        noise(t, { freq: 2200, q: 3, peak: 0.12, decay: 0.02 });
      }
      for (const [i, v] of hum.leg.entries()) {
        v.o.frequency.setTargetAtTime((170 + 95 * ls) * (i ? 2 : 1), t, 0.03);
        v.g.gain.setTargetAtTime(ls > 0.3 ? (i ? 0.035 : 0.09) * Math.min(1, ls / 4) : 0, t, 0.04);
      }
      hum.servo.o.frequency.setTargetAtTime(380 + 180 * ss, t, 0.03);
      hum.servo.g.gain.setTargetAtTime(ss > 0.15 ? 0.06 * Math.min(1, ss / 2) : 0, t, 0.03);
      Object.assign(hum.last, { wheel: wheelSpeed, leg: legSpeed, t });
    },
  };
}
