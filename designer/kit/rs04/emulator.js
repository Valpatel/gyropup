// A software RS-04 in the browser: a port of rig/rs04_emu.py (whose docstring lists what is assumed), so the tool
// can be tried, demonstrated and tested with no motor. It answers the private protocol the way the manual describes,
// runs the MIT law clipped to limit_torque in run mode, drops to reset when canTimeout passes without a frame, and has
// a small built-in plant (reflected rotor inertia and friction). Checked against vectors.json. MIT licensed.
import * as P from './protocol.js';

export const DEFAULTS = Object.freeze({ run_mode: 0, iq_ref: 0.0, spd_ref: 0.0, limit_torque: 120.0, cur_kp: 0.17,
  cur_ki: 0.012, cur_filt_gain: 0.1, loc_ref: 0.0, limit_spd: 10.0, limit_cur: 23.0, iqf: 0.0, loc_kp: 60.0,
  spd_kp: 6.0, spd_ki: 0.02, spd_filt_gain: 0.1, acc_rad: 15.0, vel_max: 10.0, acc_set: 10.0, EPScan_time: 1,
  canTimeout: 0, zero_sta: 0, damper: 0, add_offset: 0.0, alveolous_open: 0, iq_test: 0, dcc_set: 10.0 });
const VEL_KP = 10.0, VEL_KI = 200.0, KT_OUT = 2.1;
const sign = (x) => (x > 0 ? 1 : x < 0 ? -1 : 0);
/** Python's a % b (the sign of b), which the angle wrap uses. */
const pymod = (a, b) => a - b * Math.floor(a / b);

export class EmulatedRS04 {
  constructor({ id = P.FACTORY_ID, host = P.HOST_ID, uid = null, clock = () => performance.now() / 1000, plant = 'inertia',
    inertia = 3.0e-4 * 81, friction = 0.3, viscous = 0.05, vbus = 48.0, load = null, version = [0, 4, 1, 24] } = {}) {
    this.id = id; this.host = host;
    this.uid = uid ? Array.from(uid) : Array.from({ length: 8 }, () => Math.floor(Math.random() * 256));
    this.clock = clock; this.plant = plant;
    this.J = inertia; this.coulomb = friction; this.b = viscous;
    this.mode = 0; this.params = { ...DEFAULTS }; this.saved = { ...DEFAULTS };
    this.angle = 0.0; this.speed = 0.0; this.offset = 0.0; this.temp_c = 28.0; this.vbus = vbus; this.fault_word = 0;
    this.cmd = [0.0, 0.0, 0.0, 0.0, 0.0]; this.applied = 0.0;
    this.last_rx = clock(); this.last_step = clock();
    this.version = version; this.frames_seen = 0; this.mute = false; this.load = load; this.vint = 0.0;
  }

  get position() {
    const p = this.angle - this.offset + this.params.add_offset, lim = 4 * Math.PI;
    return pymod(p + lim, 2 * lim) - lim;
  }
  feedbackFaults() {
    let bits = 0;
    if (this.fault_word & (1 << 2)) bits |= 1 << 0;
    if (this.fault_word & ((1 << 4) | (1 << 5) | (1 << 16))) bits |= 1 << 1;
    if (this.fault_word & 1) bits |= 1 << 2;
    if (this.fault_word & (1 << 14)) bits |= 1 << 4;
    if (this.fault_word & (1 << 7)) bits |= 1 << 5;
    return bits;
  }
  _feedback() {
    return P.encodeFeedback(this.id, this.host, this.mode, this.feedbackFaults(), this.position, this.speed, this.applied, this.temp_c);
  }
  watchdog(now) {
    const to = this.params.canTimeout;
    if (to && this.mode === 2 && now - this.last_rx > to / P.TIMEOUT_TICKS_PER_S) { this.mode = 0; this.applied = 0.0; }
  }
  torque(now = this.clock()) {
    this.watchdog(now);
    if (this.vbus > 60.0) this.fault_word |= 1 << 3;
    if (this.mode !== 2 || this.fault_word) { this.applied = 0.0; return 0.0; }
    let lim = Math.min(Number(this.params.limit_torque), P.RS04.t);
    if (this.params.run_mode === 2) {
      const tau = VEL_KP * (Number(this.params.spd_ref) - this.speed) + this.vint;
      lim = Math.min(lim, Number(this.params.limit_cur) * KT_OUT);
      this.applied = Math.max(-lim, Math.min(lim, tau));
      return this.applied;
    }
    const [p, v, kp, kd, t] = this.cmd;
    const tau = kd * (v - this.speed) + kp * (p - this.position) + t;
    this.applied = Math.max(-lim, Math.min(lim, tau));
    return this.applied;
  }
  step(now = this.clock()) {
    const dt = Math.max(0.0, now - this.last_step);
    this.last_step = now;
    if (this.plant !== 'inertia' || dt === 0.0) return;
    const n = Math.max(1, Math.trunc(dt / 2e-4)), h = dt / n;
    for (let i = 0; i < n; i++) {
      const tau = this.torque(now);
      if (this.mode === 2 && !this.fault_word && this.params.run_mode === 2) {
        const lim = Math.min(Number(this.params.limit_torque), Number(this.params.limit_cur) * KT_OUT);
        this.vint = Math.max(-lim, Math.min(lim, this.vint + VEL_KI * (Number(this.params.spd_ref) - this.speed) * h));
      } else this.vint = 0.0;
      let fr = this.coulomb * sign(this.speed) + this.b * this.speed;
      if (this.load) fr += this.load(this.speed);
      if (this.speed === 0.0 && Math.abs(tau) <= this.coulomb) continue;
      this.speed += (tau - fr) / this.J * h;
      this.angle += this.speed * h;
    }
  }

  /** A frame on the bus -> the frames this motor answers with. */
  handle({ id, data, ext = true }) {
    if (!ext || this.mute) return [];
    const req = P.parseRequest(id, data);
    if (!req || req.motor !== this.id) return [];
    const now = this.clock();
    this.step(now);
    this.last_rx = now;
    this.frames_seen += 1;
    const k = req.kind;
    if (k === P.GET_ID) return [P.encodeIdReply(this.id, this.uid)];
    if (k === P.ENABLE) { if (!this.fault_word) this.mode = 2; return [this._feedback()]; }
    if (k === P.STOP) {
      if (req.fields.version) return [{ id: P.canId(P.FEEDBACK, this.id, this.host), data: Uint8Array.from([0, 0xC4, 0x56, ...this.version, 0]), ext: true }];
      this.mode = 0; this.applied = 0.0;
      if (req.fields.clear_fault) this.fault_word = 0;
      return [this._feedback()];
    }
    if (k === P.SET_ZERO) {
      if (this.params.run_mode !== 1 && req.fields.zero) {
        this.offset = this.angle + this.params.add_offset;
        this.cmd = [0.0, this.cmd[1], this.cmd[2], this.cmd[3], this.cmd[4]];
      }
      return [this._feedback()];
    }
    if (k === P.SET_ID) { this.id = req.fields.new_id; return [P.encodeIdReply(this.id, this.uid)]; }
    if (k === P.MIT) {
      const f = req.fields;
      this.cmd = [f.p, f.v, f.kp, f.kd, f.t];
      this.torque(now);
      return [this._feedback()];
    }
    if (k === P.READ_PARAM) {
      const p = P.BY_INDEX[req.fields.index];
      if (!p) return [P.encodeParamReply(this.id, this.host, req.fields.index, [0, 0, 0, 0], false)];
      const live = { mechPos: this.position, mechVel: this.speed, VBUS: this.vbus, iqf: this.applied / KT_OUT };
      const v = p.name in live ? live[p.name] : (this.params[p.name] ?? 0);
      return [P.encodeParamReply(this.id, this.host, p.index, P.packValue(p, v))];
    }
    if (k === P.WRITE_PARAM) {
      const p = P.BY_INDEX[req.fields.index];
      if (p && p.writable) {
        let v = req.fields.value;
        if (p.lo != null) v = Math.max(p.lo, v);
        if (p.hi != null) v = Math.min(p.hi, v);
        this.params[p.name] = v;
      }
      return [this._feedback()];
    }
    if (k === P.SAVE) { this.saved = { ...this.params }; return [this._feedback()]; }
    return [this._feedback()];
  }

  powerCycle() {
    this.params = { ...this.saved }; this.mode = 0; this.applied = 0.0; this.cmd = [0.0, 0.0, 0.0, 0.0, 0.0];
  }
}

/** An in-memory bus of software motors; what a host sends reaches every motor, and their answers come back at once. */
export class VirtualBus {
  constructor() { this.motors = []; this.listeners = new Set(); this.log = null; }
  attach(motor) { this.motors.push(motor); return motor; }
  onFrame(cb) { this.listeners.add(cb); return () => this.listeners.delete(cb); }
  send(frame) {
    if (this.log) this.log.push(frame);
    for (const m of this.motors)
      for (const reply of m.handle(frame)) for (const cb of this.listeners) cb(reply);
  }
  /** Advance every motor's plant (the page calls it on a timer, so a motor coasts and its watchdog runs). */
  tick(now) { for (const m of this.motors) { m.step(now); m.watchdog(now ?? m.clock()); } }
}
