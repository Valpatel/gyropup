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
//                  chirp(), motion({ wheelSpeed, servoSpeed, legSpeed }), turret }
//
// sfx.turret is the turret on the Orin AGX box (turret_bench.js), on the same chain and at the same levels:
//   frame({ spin, servo, dial })  every frame: the flywheels' speed (a fraction of the set speed: the hum follows it up,
//                                 holds, and falls with the brake), the aim servos' and the feed dial's speeds (rad/s)
//   brake()                       ARM released: the phase-short brake stops the wheels (D9)
//   dial(), drop(), shot({ power, nip })   a dial step, a ball dropping into the chute, the muzzle shot (no dial click)
//   hit('paper' | 'can' | 'plate', power), down(), can(speed), bounce(speed)   on the range
//   pile(), roll(s), nip(), bore(s), fly()  the journey's stages
//   slowmo(k)                     the journey's time scale: below 1 the turret's sounds play lower and longer
//   stop()                        leaving the turret: its continuous voices fall silent
// Only the turret mode touches these: its continuous voices are made the first time it sets them.

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
    if (ctx.state === 'suspended' || ctx.state === 'interrupted') ctx.resume().catch(() => {});   // interrupted: iOS (a call, the lock)
    return ctx;
  }
  // iOS starts audio only at the end of a tap (touchend, pointerup); desktop browsers on any gesture
  for (const ev of ['pointerdown', 'keydown', 'touchstart', 'pointerup', 'touchend']) window.addEventListener(ev, () => unlock(), { passive: true });
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

  // ---- the turret on the Orin AGX box (turret_bench.js). In the journey's slow motion (time scale k below 1) its
  // sounds play lower (pitch x sp(): k^0.2, not under 0.3) and longer (x sd()), with more room; at k = 1 they are as fast
  // as the robot's. tnoise and ttone are noise() and tone() in that time (the noise loops: slow motion outlasts 1 s).
  let slowK = 1;
  const sp = () => Math.min(1, Math.max(0.3, Math.pow(slowK, 0.2)));
  const sd = () => 1 / Math.pow(sp(), 1.25);
  const lowF = (f) => Math.max(Math.min(f, 34), f * sp());               // lower, but nothing sinks under 34 Hz
  const wetter = (wet) => Math.min(1, wet + 0.45 * (1 - sp()));
  function tnoise(t0, { type = 'bandpass', freq = 1200, q = 1, peak = 0.5, attack = 0.002, decay = 0.08, sweepTo = null, wet = 0 }) {
    const p = sp(), a = attack * sd(), dk = decay * sd();
    const src = ctx.createBufferSource();
    src.buffer = noiseBuf;
    src.loop = true;
    src.playbackRate.value = (0.8 + Math.random() * 0.4) * p;
    const f = ctx.createBiquadFilter();
    f.type = type;
    f.frequency.setValueAtTime(freq * p, t0);
    if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo * p, t0 + a + dk);
    f.Q.value = q;
    const g = ctx.createGain();
    env(g, t0, peak, a, dk);
    src.connect(f).connect(g);
    sends(g, wetter(wet));
    src.start(t0, Math.random() * 0.5);
    src.stop(t0 + a + dk + 0.05);
  }
  function ttone(t0, { type = 'sine', from = 440, to = null, peak = 0.3, attack = 0.003, decay = 0.1, wet = 0 }) {
    tone(t0, { type, from: lowF(from), to: to ? lowF(to) : null, peak, attack: attack * sd(), decay: decay * sd(), wet: wetter(wet) });
  }
  // a struck thin shell (an aluminium can): inharmonic partials [Hz, peak, decay s], each dying on its own
  function ring(t0, partials, g, wet) {
    for (const [f, pk, dk] of partials) { const fj = jitter(f, 0.03); ttone(t0, { from: fj, to: fj * 0.985, peak: pk * g, attack: 0.0015, decay: dk, wet }); }
  }
  // the continuous voices, made the first time the turret mode sets them
  const tv = { last: { spin: 0, t: 0, servoOn: false, servoT: 0, dialOn: false }, bounceT: -1 };
  function turretVoices() {
    if (tv.fly) return tv;
    const osc = (type, freq) => { const o = ctx.createOscillator(); o.type = type; o.frequency.value = freq; o.start(); return o; };
    const filt = (type, freq, q = 1) => { const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q; return f; };
    const amp = (v = 0) => { const g = ctx.createGain(); g.gain.value = v; return g; };
    const loop = () => { const s = ctx.createBufferSource(); s.buffer = noiseBuf; s.loop = true; s.start(0, Math.random() * 0.5); return s; };
    const voice = (type, freq, f, to) => { const o = osc(type, freq), g = amp(); o.connect(f).connect(g).connect(to); return { o, f, g }; };
    // the flywheels: the robot's hum (two beating sawtooths, a sub an octave down, the air they move), with the Snails'
    // electrical whine and the strain of a spin-up. A ball through the nip dips their pitch (detune) and puffs the air.
    const bus = amp(1);
    sends(bus, 0.15);
    tv.fly = [voice('sawtooth', 40, filt('lowpass', 2400), bus), voice('sawtooth', 40, filt('lowpass', 2400), bus)];
    tv.sub = voice('square', 20, filt('lowpass', 600), bus);
    tv.whine = voice('sine', 60, filt('lowpass', 6000), bus);
    tv.strain = voice('square', 60, filt('bandpass', 2500, 2), bus);
    tv.puff = amp(1);
    tv.air = { f: filt('bandpass', 400, 0.9), g: amp() };
    loop().connect(tv.air.f).connect(tv.air.g).connect(tv.puff).connect(bus);
    // the aim servos: a buzzing gear whine that climbs with the slew, fluttering as the pinion's teeth mesh, and the
    // grit of the printed pan gear
    tv.mesh = { am: amp(1), lfo: osc('sine', 10), depth: amp(0) };
    tv.mesh.lfo.connect(tv.mesh.depth).connect(tv.mesh.am.gain);
    tv.servo = voice('square', 260, filt('bandpass', 1300, 0.8), tv.mesh.am);
    tv.mesh.am.connect(out);
    tv.grit = { f: filt('bandpass', 3000, 2), g: amp() };
    loop().connect(tv.grit.f).connect(tv.grit.g).connect(out);
    // the feed dial's M2006 (36:1): a short gear buzz each step
    tv.feed = voice('sawtooth', 90, filt('bandpass', 1200, 1.5), out);
    tv.feed2 = voice('square', 180, filt('lowpass', 2600), out);
    return tv;
  }
  // a ball through the nip: the wheels dip (to `ratio` of their speed) and climb back, and the air puffs
  function load(t, ratio, d) {
    if (!tv.fly) return;
    const cents = 1200 * Math.log2(ratio);
    for (const v of [...tv.fly, tv.sub, tv.whine]) { v.o.detune.setTargetAtTime(cents, t, 0.01 * d); v.o.detune.setTargetAtTime(0, t + 0.06 * d, 0.09 * d); }
    tv.puff.gain.setTargetAtTime(2.3, t, 0.005 * d);
    tv.puff.gain.setTargetAtTime(1, t + 0.05 * d, 0.08 * d);
  }
  const turret = {
    /** The journey's time scale (1 = real time; 0.025 = 40 times slower): the turret's sounds follow it. */
    slowmo(k = 1) { slowK = Math.min(1, Math.max(1e-4, Number(k) || 1)); },
    /** Every frame: spin = the flywheels' speed over the set speed (0..1), servo = the aim servos' speed and dial = the
     *  feed dial's speed (rad/s, in the simulation's time). */
    frame({ spin = 0, servo = 0, dial = 0 } = {}) {
      const c = live(); if (!c) return;
      const v = turretVoices(), t = c.currentTime, p = sp(), L = v.last;
      const s = Math.max(0, Math.min(1.2, spin));
      const dt = Math.max(1e-3, t - (L.t || t - 0.016));
      const rising = (s - L.spin) / dt;
      const lvl = s > 0.002 ? Math.min(1, Math.pow(s, 0.6)) * (slowK < 1 ? 0.5 : 1) : 0;   // a softer drone under the journey
      const tau = s < L.spin - 1e-4 ? 0.012 : 0.03;                     // falling: as fast as the brake
      // the hum: pitch with the wheels' speed (the robot's 560 Hz at the set speed), louder as they come up
      const f0 = Math.max(40, 560 * s) * p;
      v.fly.forEach((w, i) => { w.o.frequency.setTargetAtTime(f0 + 7 * i * p * Math.min(1, s), t, tau); w.g.gain.setTargetAtTime(0.2 * lvl, t, tau); });
      v.sub.o.frequency.setTargetAtTime(f0 / 2, t, tau);
      v.sub.g.gain.setTargetAtTime(0.08 * lvl, t, tau);
      v.whine.o.frequency.setTargetAtTime(Math.max(60, 1395 * s) * p, t, tau);     // 7 pole pairs at 11,960 rpm
      v.whine.g.gain.setTargetAtTime(0.035 * lvl, t, tau);
      v.air.f.frequency.setTargetAtTime((400 + 2200 * Math.min(1, s)) * p, t, tau);
      v.air.g.gain.setTargetAtTime(0.14 * lvl, t, tau);
      v.strain.o.frequency.setTargetAtTime(Math.max(60, 700 * s) * p, t, 0.02);    // the ESCs push current to spin up
      v.strain.g.gain.setTargetAtTime(rising > 0.3 && lvl > 0 ? 0.06 * Math.min(1, rising / 3) : 0, t, 0.04);
      // the aim servos (the pan servo turns 3 times the turret)
      const ss = Math.min(8, Math.abs(servo)), on = ss > 0.06;
      const sl = on ? Math.min(1, Math.pow((ss - 0.06) / 1.6, 0.6)) : 0;
      v.servo.o.frequency.setTargetAtTime((260 + 110 * ss) * p, t, 0.03);
      v.servo.g.gain.setTargetAtTime(0.24 * sl, t, 0.03);
      v.mesh.lfo.frequency.setTargetAtTime(Math.max(2, 3.3 * ss) * p, t, 0.05);      // a 21-tooth pinion's mesh rate
      v.mesh.depth.gain.setTargetAtTime(0.35 * Math.min(1, sl * 2), t, 0.05);
      v.grit.g.gain.setTargetAtTime(0.07 * sl, t, 0.03);
      if (on !== L.servoOn && t - L.servoT > 0.08) {                   // the gears take up their backlash, and settle
        L.servoOn = on; L.servoT = t;
        tnoise(t, { type: 'highpass', freq: on ? 3200 : 2600, peak: on ? 0.09 : 0.06, decay: 0.012 });
      }
      // the feed dial: its motor buzzes while it turns (7.85 rad/s is 75 rpm), and the step lands with a clack
      const dw = Math.min(12, Math.abs(dial)), turning = dw > 0.2, fl = turning ? Math.min(1, dw / 7.85) : 0;
      v.feed.o.frequency.setTargetAtTime((90 + 290 * fl) * p, t, 0.015);
      v.feed.g.gain.setTargetAtTime(0.09 * fl, t, turning ? 0.012 : 0.02);
      v.feed2.o.frequency.setTargetAtTime((180 + 580 * fl) * p, t, 0.015);
      v.feed2.g.gain.setTargetAtTime(0.03 * fl, t, turning ? 0.012 : 0.02);
      if (!turning && L.dialOn) {
        const j = jitter(1, 0.06);
        ttone(t, { type: 'triangle', from: 1400 * j, to: 900 * j, peak: 0.12, decay: 0.03 });
        tnoise(t, { freq: 2600 * j, q: 2.5, peak: 0.16, decay: 0.02 });
      }
      L.dialOn = turning;
      L.spin = s; L.t = t;
    },
    /** ARM released: the phase short closes 10 ms later and stops the wheels (5 % at 45 ms): their whine drops away
     *  in a growl, the cage takes the braking torque with a knock, and the air stops. */
    brake() {
      const c = live(); if (!c) return;
      const v = turretVoices(), t = c.currentTime + 0.01, p = sp(), d = sd();
      const f0 = Math.max(80, v.fly[0].o.frequency.value);
      for (const w of [...v.fly, v.sub, v.whine]) { w.o.frequency.setTargetAtTime(30 * p, t, 0.012); w.g.gain.setTargetAtTime(0, t, 0.02); }
      v.air.g.gain.setTargetAtTime(0, t, 0.025);
      v.strain.g.gain.setTargetAtTime(0, t, 0.02);
      const o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      o.type = 'sawtooth';
      o.frequency.setValueAtTime(f0 * 2.5, t);
      o.frequency.exponentialRampToValueAtTime(35, t + 0.11 * d);
      f.type = 'bandpass'; f.Q.value = 2.5;
      f.frequency.setValueAtTime(2200 * p, t);
      f.frequency.exponentialRampToValueAtTime(180 * p, t + 0.12 * d);
      env(g, t, 0.42, 0.004, 0.13 * d);
      o.connect(f).connect(g);
      sends(g, wetter(0.3));
      o.start(t);
      o.stop(t + 0.2 * d);
      ttone(t, { type: 'square', from: Math.max(120, f0 * 2.5), to: 70, peak: 0.07, decay: 0.06 });     // the shorted windings buzz
      ttone(t + 0.008, { from: 130, to: 45, peak: 0.45, decay: 0.12, wet: 0.3 });                        // the knock through the cage
      tnoise(t, { freq: 1500, q: 1.1, peak: 0.2, decay: 0.09, sweepTo: 260 });                           // the air stops
    },
    /** The feed dial steps one pocket: the click and the pocket's tick of shot(), and the gears taking up. */
    dial() {
      const c = live(); if (!c) return;
      const t = c.currentTime, j = jitter(1, 0.07);
      ttone(t, { type: 'square', from: 760 * j, to: 430 * j, peak: 0.14, decay: 0.022 });
      tnoise(t, { type: 'highpass', freq: 3800, peak: 0.12, decay: 0.012 });
      tnoise(t, { freq: 1700 * j, q: 4, peak: 0.07, attack: 0.004, decay: 0.045 });
    },
    /** A ball drops out of its pocket through the exit hole: a hollow foam tok on the chute, and it rolls off round the bend. */
    drop() {
      const c = live(); if (!c) return;
      const t = c.currentTime, j = jitter(1, 0.08), d = sd();
      ttone(t, { type: 'triangle', from: 520 * j, to: 250 * j, peak: 0.34, decay: 0.05, wet: 0.2 });
      tnoise(t, { freq: 1150 * j, q: 1.6, peak: 0.3, decay: 0.035, wet: 0.2 });
      tnoise(t + 0.03 * d, { type: 'lowpass', freq: 650, peak: 0.09, attack: 0.012, decay: 0.07 });
    },
    /** The shot as it leaves the muzzle: shot() without the dial's click (dial() and drop() play that). power = the exit
     *  speed over the set speed (a ball the brake caught dribbles out); nip: false when nip() already played the squeeze. */
    shot({ power = 1, nip = true } = {}) {
      const c = live(); if (!c) return;
      const t = c.currentTime, p = jitter(1, 0.07), d = sd(), pw = Math.max(0, Math.min(1, power));
      if (pw < 0.15) {
        ttone(t, { type: 'triangle', from: 240 * p, to: 130, peak: 0.24, decay: 0.07 });
        tnoise(t, { freq: 900 * p, q: 1.3, peak: 0.12, decay: 0.05 });
        return;
      }
      const g = 0.35 + 0.65 * pw;
      tnoise(t, { type: 'highpass', freq: 2600 * p, q: 0.7, peak: 1.0 * g, attack: 0.0008, decay: 0.035, wet: 0.5 });   // crack
      ttone(t, { from: 160 * p, to: 42, peak: 1.0 * g, attack: 0.002, decay: 0.2 });                                     // thump
      if (nip) ttone(t, { type: 'triangle', from: 330 * p, to: 115, peak: 0.55 * g, decay: 0.09 });                     // squeeze
      tnoise(t + 0.006 * d, { freq: 3200 * p, q: 0.75, peak: 0.75 * g, decay: 0.26, sweepTo: 420, wet: 0.9 });          // whoosh
      tnoise(t + 0.01 * d, { type: 'highpass', freq: 5200, peak: 0.16 * g, decay: 0.05 });                              // tyre scuff
      if (nip) load(t, 0.72, d);
    },
    /** A ball hits: 'plate' (hit()'s bop and ring), 'paper' (a dry slap, the sheet's rattle, the board's thud) or 'can'
     *  (a hollow tonk and a thin tinny ring). power = the impact speed over about 15 m/s. */
    hit(kind = 'plate', power = 1) {
      const c = live(); if (!c) return;
      const t = c.currentTime, d = sd(), g = 0.45 + 0.55 * Math.max(0, Math.min(1, power));
      if (kind === 'paper') {
        tnoise(t, { type: 'highpass', freq: jitter(1700), q: 0.8, peak: 0.8 * g, attack: 0.0008, decay: 0.028, wet: 0.35 });
        tnoise(t + 0.003 * d, { freq: jitter(4300), q: 1.5, peak: 0.22 * g, decay: 0.07 });
        ttone(t, { type: 'triangle', from: jitter(190), to: 92, peak: 0.6 * g, decay: 0.1, wet: 0.3 });
        tnoise(t, { type: 'lowpass', freq: 520, peak: 0.35 * g, decay: 0.06 });
      } else if (kind === 'can') {
        tnoise(t, { freq: jitter(900), q: 1.4, peak: 0.55 * g, decay: 0.035, wet: 0.4 });
        ttone(t, { type: 'triangle', from: jitter(330), to: 210, peak: 0.32 * g, decay: 0.05 });
        ring(t, [[540, 0.22, 0.16], [1180, 0.2, 0.12], [1930, 0.16, 0.09], [2810, 0.12, 0.07], [3950, 0.08, 0.05]], g, 0.45);
      } else {
        tnoise(t, { freq: jitter(640), q: 1.3, peak: 0.95 * g, decay: 0.07, wet: 0.5 });
        ttone(t, { type: 'triangle', from: jitter(280), to: 140, peak: 0.7 * g, decay: 0.11 });
        ttone(t + 0.01 * d, { from: jitter(1250), to: 1150, peak: 0.14 * g, decay: 0.32, wet: 0.6 });
      }
    },
    /** A plate knocked over: down()'s clatter and thud, in the turret's time. */
    down() {
      const c = live(); if (!c) return;
      const t = c.currentTime, d = sd();
      let at = t, amp = 0.85;
      for (let k = 0; k < 5; k++) {
        tnoise(at, { freq: 700 + Math.random() * 900, q: 3, peak: amp, decay: 0.06, wet: 0.4 });
        ttone(at, { type: 'triangle', from: 240 + Math.random() * 140, peak: amp * 0.55, decay: 0.06 });
        at += (0.055 + Math.random() * 0.07) * d;
        amp *= 0.65;
      }
      ttone(t + 0.02 * d, { from: 110, to: 48, peak: 0.9, decay: 0.26, wet: 0.5 });
    },
    /** A can lands (speed: m/s down): the rim's clank, the hollow body, a tinny ring and a little clatter as it rolls. */
    can(speed = 2.5) {
      const c = live(); if (!c) return;
      const t = c.currentTime, d = sd(), g = Math.min(1, Math.max(0.15, speed / 3));
      tnoise(t, { freq: jitter(2400), q: 2, peak: 0.5 * g, decay: 0.03, wet: 0.35 });
      ttone(t, { type: 'triangle', from: jitter(230), to: 120, peak: 0.42 * g, decay: 0.07 });
      ring(t, [[1620, 0.16, 0.14], [2470, 0.14, 0.1], [3560, 0.11, 0.08], [4900, 0.07, 0.05]], g, 0.4);
      for (let k = 1; k <= 3; k++) tnoise(t + (0.05 + 0.045 * k + Math.random() * 0.03) * d, { freq: 2000 + Math.random() * 1800, q: 3, peak: 0.14 * g / k, decay: 0.02 });
    },
    /** A foam ball bouncing on the ground (speed: m/s down): a soft pok. */
    bounce(speed = 3) {
      const c = live(); if (!c) return;
      const t = c.currentTime;
      if (t - tv.bounceT < 0.03) return;
      tv.bounceT = t;
      const g = Math.min(1, speed / 6);
      ttone(t, { type: 'triangle', from: jitter(260), to: 140, peak: 0.26 * g, decay: 0.05 });
      tnoise(t, { freq: jitter(850), q: 1.5, peak: 0.2 * g, decay: 0.03, wet: 0.2 });
    },
    /** The journey, the hopper: the balls shift and settle as the cone stirs them. */
    pile() {
      const c = live(); if (!c) return;
      const t = c.currentTime, d = sd();
      let at = t;
      for (let k = 0; k < 10; k++) {
        tnoise(at, { freq: 800 + Math.random() * 900, q: 2.2, peak: 0.42 * (1 - k / 13), decay: 0.03, wet: 0.35 });
        if (k % 3 === 0) ttone(at, { type: 'triangle', from: 300 + Math.random() * 160, to: 180, peak: 0.14, decay: 0.04 });
        at += (0.05 + Math.random() * 0.12) * d;
      }
      tnoise(t, { type: 'lowpass', freq: 380, q: 0.7, peak: 0.1, attack: 0.25, decay: 0.9 });
    },
    /** The journey, the chute: the ball rolls round the bend for `seconds` (its seam knocking once a turn). */
    roll(seconds = 0.09) {
      const c = live(); if (!c) return;
      const t = c.currentTime, p = sp(), dur = Math.max(0.15, seconds);
      const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), am = ctx.createGain(), g = ctx.createGain();
      const lfo = ctx.createOscillator(), depth = ctx.createGain();
      src.buffer = noiseBuf; src.loop = true; src.playbackRate.value = 0.7 * p;
      f.type = 'lowpass'; f.frequency.value = 700 * Math.sqrt(p); f.Q.value = 0.9;        // above the slowed drone
      lfo.frequency.value = 9 * p; depth.gain.value = 0.5; am.gain.value = 0.6;
      lfo.connect(depth).connect(am.gain);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.26, t + Math.min(0.2, dur / 4));
      g.gain.setValueAtTime(0.26, t + dur * 0.8);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      src.connect(f).connect(am).connect(g);
      sends(g, wetter(0.25));
      src.start(t, Math.random() * 0.5); lfo.start(t);
      src.stop(t + dur + 0.05); lfo.stop(t + dur + 0.05);
    },
    /** The journey, the flywheels: the tyres grab the ball (the squeeze and a squeal) and the wheels dip under the load. */
    nip() {
      const c = live(); if (!c) return;
      const t = c.currentTime, j = jitter(1, 0.05), d = sd();
      ttone(t, { type: 'triangle', from: 330 * j, to: 115, peak: 0.55, decay: 0.09 });
      tnoise(t, { freq: 1900 * j, q: 6, peak: 0.24, attack: 0.004, decay: 0.12, sweepTo: 2700, wet: 0.3 });
      ttone(t, { from: 120 * j, to: 58, peak: 0.4, decay: 0.12 });
      load(t, 0.82, d);
    },
    /** The journey, the barrel: the air the ball pushes sings in the bore for `seconds`, rising as it goes. */
    bore(seconds = 0.006) {
      const c = live(); if (!c) return;
      const t = c.currentTime, p = sp(), dur = Math.max(0.2, seconds);
      const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      src.buffer = noiseBuf; src.loop = true; src.playbackRate.value = p;
      f.type = 'bandpass'; f.Q.value = 4;
      f.frequency.setValueAtTime(900 * Math.sqrt(p), t);                                  // above the slowed drone
      f.frequency.exponentialRampToValueAtTime(2200 * Math.sqrt(p), t + dur);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.4, t + dur * 0.85);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      src.connect(f).connect(g);
      sends(g, wetter(0.35));
      src.start(t, Math.random() * 0.5);
      src.stop(t + dur + 0.05);
    },
    /** The journey, the flight: the ball whooshes away, its seam whistling faintly. */
    fly() {
      const c = live(); if (!c) return;
      const t = c.currentTime, j = jitter(1, 0.06);
      tnoise(t, { freq: 2600 * j, q: 1.2, peak: 0.5, attack: 0.02, decay: 0.55, sweepTo: 450, wet: 0.8 });
      ttone(t, { from: 1700 * j, to: 1100 * j, peak: 0.05, attack: 0.02, decay: 0.45, wet: 0.6 });
    },
    /** Leaving the turret: its continuous voices fall silent. */
    stop() {
      if (!ctx || !tv.fly) return;
      const t = ctx.currentTime;
      for (const v of [...tv.fly, tv.sub, tv.whine, tv.strain, tv.air, tv.servo, tv.grit, tv.feed, tv.feed2]) v.g.gain.setTargetAtTime(0, t, 0.03);
      tv.mesh.depth.gain.setTargetAtTime(0, t, 0.03);
      tv.last.servoOn = tv.last.dialOn = false;
      tv.last.spin = 0;
    },
  };

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
    turret,
  };
}
