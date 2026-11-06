// RobStride RS-04: the private CAN protocol (29-bit extended frames, 1 Mbit/s) as plain functions on frames.
// A line-for-line port of the Python driver rig/rs04.py (where the sources and their differences are written down):
// the same communication types, parameter table, 16-bit scaling (the manual's float_to_uint) and frame layouts. Both
// are tested against the same golden vectors (vectors.json, generated from the Python by `python -m rig.rs04_vectors`).
// No dependencies, no DOM, nothing from the page that uses it. MIT licensed (LICENSE in this folder).
//
// A frame is { id, data, ext }: id the 29-bit identifier (a number), data a Uint8Array of up to 8 bytes, ext true.

// ------------------------------------------------------------------------------- communication types (manual 4.1)
export const GET_ID = 0, MIT = 1, FEEDBACK = 2, ENABLE = 3, STOP = 4, SET_ZERO = 6, SET_ID = 7;
export const READ_PARAM = 17, WRITE_PARAM = 18, FAULT = 21, SAVE = 22, SET_BAUD = 23, REPORT = 24, SET_PROTOCOL = 25;
export const TYPE_NAMES = Object.freeze({ [GET_ID]: 'get id', [MIT]: 'mit', [FEEDBACK]: 'feedback', [ENABLE]: 'enable',
  [STOP]: 'stop', [SET_ZERO]: 'set zero', [SET_ID]: 'set id', [READ_PARAM]: 'read', [WRITE_PARAM]: 'write',
  [FAULT]: 'fault', [SAVE]: 'save', [SET_BAUD]: 'baud', [REPORT]: 'report', [SET_PROTOCOL]: 'protocol' });

export const HOST_ID = 0xFD;        // the motors' default CAN_MASTER (manual 3.3)
export const FACTORY_ID = 0x7F;     // CAN_ID 127 out of the box
export const ID_REPLY_DEST = 0xFE;  // a type-0 reply is addressed to 0xFE (4.1.1)
export const MODES = Object.freeze({ 0: 'reset', 1: 'calibration', 2: 'run' });
export const RUN_MODES = Object.freeze({ 0: 'operation (MIT)', 1: 'position (PP)', 2: 'velocity', 3: 'current', 5: 'position (CSP)' });
export const BAUD_CODES = Object.freeze({ 1: 1000000, 2: 500000, 3: 250000, 4: 125000 });
export const TIMEOUT_TICKS_PER_S = 20000;

/** The 16-bit fields' full scale for the RS-04 (manual 4.1.2 and 4.4). */
export const RS04 = Object.freeze({ p: 4 * Math.PI, v: 15.0, t: 120.0, kp: 5000.0, kd: 100.0 });
export const FULL = 0xFFFF;

/** The manual's float_to_uint (4.4): clamp, scale to 0..65535, truncate. NaN and infinities are refused. */
export function f2u(x, lo, hi) {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite number: ${x}`);
  if (x <= lo) return 0;
  if (x >= hi) return FULL;
  return Math.trunc((x - lo) * FULL / (hi - lo));
}
/** The inverse: 0 -> lo, 65535 -> hi. */
export const u2f = (u, lo, hi) => lo + u * (hi - lo) / FULL;

/** A 29-bit id: type in bits 28-24, 'data area 2' in 23-8, the destination in 7-0. */
export const canId = (kind, data2, dest) => (((kind & 0x1F) << 24) | ((data2 & 0xFFFF) << 8) | (dest & 0xFF)) >>> 0;
/** [type, data area 2, destination] of a 29-bit id. */
export const idFields = (cid) => [(cid >>> 24) & 0x1F, (cid >>> 8) & 0xFFFF, cid & 0xFF];

// ------------------------------------------------------------------------------- the parameter table (manual 4.1.13)
const P = (name, index, kind, writable, unit = '', lo = null, hi = null, note = '') =>
  Object.freeze({ name, index, kind, writable, unit, lo, hi, note });
export const PARAMS = Object.freeze(Object.fromEntries([
  P('run_mode', 0x7005, 'B', true, '', 0, 5, '0 operation (MIT), 1 position PP, 2 velocity, 3 current, 5 position CSP'),
  P('iq_ref', 0x7006, 'f', true, 'A', -90, 90, 'current-mode command'),
  P('spd_ref', 0x700A, 'f', true, 'rad/s', -20, 20, 'velocity-mode command'),
  P('limit_torque', 0x700B, 'f', true, 'N m', 0, 120, 'torque limit (the rig sets 60: D38 cap, independent of the laptop)'),
  P('cur_kp', 0x7010, 'f', true, '', null, null, 'current loop Kp (default 0.17)'),
  P('cur_ki', 0x7011, 'f', true, '', null, null, 'current loop Ki (default 0.012)'),
  P('cur_filt_gain', 0x7014, 'f', true, '', 0, 1, 'current filter (default 0.1)'),
  P('loc_ref', 0x7016, 'f', true, 'rad', null, null, 'position-mode command'),
  P('limit_spd', 0x7017, 'f', true, 'rad/s', 0, 20, 'CSP speed limit'),
  P('limit_cur', 0x7018, 'f', true, 'A', 0, 90, 'velocity/position-mode current limit'),
  P('mechPos', 0x7019, 'f', false, 'rad', null, null, 'output angle'),
  P('iqf', 0x701A, 'f', false, 'A', -90, 90, 'filtered iq'),
  P('mechVel', 0x701B, 'f', false, 'rad/s', -15, 15, 'output speed'),
  P('VBUS', 0x701C, 'f', false, 'V', null, null, 'bus voltage'),
  P('loc_kp', 0x701E, 'f', true, '', null, null, 'position Kp (default 60)'),
  P('spd_kp', 0x701F, 'f', true, '', null, null, 'speed Kp (default 6)'),
  P('spd_ki', 0x7020, 'f', true, '', null, null, 'speed Ki (default 0.02)'),
  P('spd_filt_gain', 0x7021, 'f', true, '', null, null, 'speed filter (default 0.1)'),
  P('acc_rad', 0x7022, 'f', true, 'rad/s^2', null, null, 'velocity-mode acceleration (default 15)'),
  P('vel_max', 0x7024, 'f', true, 'rad/s', null, null, 'PP speed (default 10)'),
  P('acc_set', 0x7025, 'f', true, 'rad/s^2', null, null, 'PP acceleration (default 10)'),
  P('EPScan_time', 0x7026, 'H', true, '', 1, null, 'active report period: 1 = 10 ms, each +1 adds 5 ms'),
  P('canTimeout', 0x7028, 'I', true, '1/20000 s', 0, null, 'CAN watchdog: no frame for this long -> reset mode; 0 off (3.3.6)'),
  P('zero_sta', 0x7029, 'B', true, '', 0, 1, 'power-on angle range: 0 -> 0..2pi, 1 -> -pi..pi'),
  P('damper', 0x702A, 'B', true, '', 0, 1, 'power-off anti-backdrive damping: 0 on (default), 1 off (4.2.5)'),
  P('add_offset', 0x702B, 'f', true, 'rad', null, null, 'zero offset'),
  P('alveolous_open', 0x702C, 'B', true, '', 0, 1, 'cogging compensation'),
  P('iq_test', 0x702D, 'B', true, '', 0, 1, 'longer initialisation calibration'),
  P('dcc_set', 0x702E, 'f', true, 'rad/s^2', null, null, 'PP deceleration (default 10)'),
].map(p => [p.name, p])));
export const BY_INDEX = Object.freeze(Object.fromEntries(Object.values(PARAMS).map(p => [p.index, p])));
const SIZE = { B: 1, H: 2, I: 4, f: 4 };

/** A parameter by name (case-insensitive) or index; throws for an unknown one. */
export function param(nameOrIndex) {
  if (typeof nameOrIndex === 'number') {
    const p = BY_INDEX[nameOrIndex];
    if (!p) throw new RangeError(`unknown RS-04 parameter index 0x${nameOrIndex.toString(16)}`);
    return p;
  }
  if (PARAMS[nameOrIndex]) return PARAMS[nameOrIndex];
  const low = String(nameOrIndex).toLowerCase();
  const p = Object.values(PARAMS).find(q => q.name.toLowerCase() === low);
  if (!p) throw new RangeError(`unknown RS-04 parameter ${JSON.stringify(nameOrIndex)}`);
  return p;
}

/** Bytes 4-7 of a type-18 frame: little-endian, a one- or two-byte value padded with zeros (manual 4.4.4-4.4.5). */
export function packValue(p, value) {
  const out = new Uint8Array(4), dv = new DataView(out.buffer);
  if (p.kind === 'f') { dv.setFloat32(0, Number(value), true); return out; }
  const v = Math.trunc(Number(value));
  if (!Number.isFinite(v) || v < 0 || v >= 2 ** (8 * SIZE[p.kind])) throw new RangeError(`${p.name}: ${value} out of range for ${p.kind}`);
  if (p.kind === 'B') dv.setUint8(0, v); else if (p.kind === 'H') dv.setUint16(0, v, true); else dv.setUint32(0, v, true);
  return out;
}
export function unpackValue(p, raw) {
  const dv = new DataView(Uint8Array.from(raw).buffer);
  if (p.kind === 'f') return dv.getFloat32(0, true);
  return p.kind === 'B' ? dv.getUint8(0) : p.kind === 'H' ? dv.getUint16(0, true) : dv.getUint32(0, true);
}

// ------------------------------------------------------------------------------- host -> motor frames
const frame = (id, data) => ({ id, data: Uint8Array.from(data), ext: true });
const ZERO8 = [0, 0, 0, 0, 0, 0, 0, 0];
export const MAGIC = Object.freeze([1, 2, 3, 4, 5, 6]);   // the head of the type 22-25 frames (4.1.9-4.1.12)
const u16be = (...vals) => vals.flatMap(v => [(v >> 8) & 0xFF, v & 0xFF]);
const u16le = (v) => [v & 0xFF, (v >> 8) & 0xFF];

export const packGetId = (motor, host = HOST_ID) => frame(canId(GET_ID, host, motor), ZERO8);
export const packEnable = (motor, host = HOST_ID) => frame(canId(ENABLE, host, motor), ZERO8);
/** Stop (reset mode). Byte 0 = 1 also clears the faults; it must be 0 in normal running (4.1.4). */
export const packStop = (motor, host = HOST_ID, clearFault = false) => frame(canId(STOP, host, motor), [clearFault ? 1 : 0, 0, 0, 0, 0, 0, 0, 0]);
/** The firmware version request: a type-4 frame with 00 C4 (4.1.3). It stops the motor too, so only when idle. */
export const packVersion = (motor, host = HOST_ID) => frame(canId(STOP, host, motor), [0, 0xC4, 0, 0, 0, 0, 0, 0]);
/** Set the mechanical zero at the present angle (4.1.5; not in PP mode, 4.2.6). */
export const packZero = (motor, host = HOST_ID) => frame(canId(SET_ZERO, host, motor), [1, 0, 0, 0, 0, 0, 0, 0]);
/** Give a motor a new CAN id, at once (type 7: the new id in bits 23-16). */
export function packSetId(motor, newId, host = HOST_ID) {
  if (!(Number.isInteger(newId) && newId >= 1 && newId <= 0x7F)) throw new RangeError('a motor id is 1..127');
  return frame(canId(SET_ID, (newId << 8) | host, motor), ZERO8);
}
/** The operation-control (MIT) command (4.1.2): t_ref = Kd (v - w) + Kp (p - angle) + t. */
export function packMit(motor, p, v, kp, kd, t, r = RS04) {
  return frame(canId(MIT, f2u(t, -r.t, r.t), motor), u16be(f2u(p, -r.p, r.p), f2u(v, -r.v, r.v), f2u(kp, 0, r.kp), f2u(kd, 0, r.kd)));
}
export function packRead(motor, nameOrIndex, host = HOST_ID) {
  const idx = typeof nameOrIndex === 'number' ? nameOrIndex : param(nameOrIndex).index;
  return frame(canId(READ_PARAM, host, motor), [...u16le(idx), 0, 0, 0, 0, 0, 0]);
}
export function packWrite(motor, nameOrIndex, value, host = HOST_ID) {
  const p = param(nameOrIndex);
  if (!p.writable) throw new RangeError(`${p.name} is read-only`);
  return frame(canId(WRITE_PARAM, host, motor), [...u16le(p.index), 0, 0, ...packValue(p, value)]);
}
/** Keep the written parameters over a power cycle (type 22; data 01..08). */
export const packSave = (motor, host = HOST_ID) => frame(canId(SAVE, host, motor), [1, 2, 3, 4, 5, 6, 7, 8]);
/** Active reporting on/off (type 24; F_CMD in byte 6, byte 7 sent as 0). */
export const packReport = (motor, on, host = HOST_ID) => frame(canId(REPORT, host, motor), [...MAGIC, on ? 1 : 0, 0]);
export function packBaud(motor, code, host = HOST_ID) {
  if (!(code in BAUD_CODES)) throw new RangeError(`baud code ${code}: one of 1, 2, 3, 4`);
  return frame(canId(SET_BAUD, host, motor), [...MAGIC, code, 0]);
}

// ------------------------------------------------------------------------------- motor -> host frames
export const FEEDBACK_FAULTS = Object.freeze({ 16: 'under-voltage', 17: 'over-current', 18: 'over-temperature',
  19: 'magnetic encoder', 20: 'stall overload', 21: 'uncalibrated' });
export const FAULT_BITS = Object.freeze({ 0: 'over-temperature (145 C)', 1: 'driver chip', 2: 'under-voltage (12 V)',
  3: 'over-voltage (60 V)', 4: 'phase B over-current', 5: 'phase C over-current', 7: 'encoder uncalibrated',
  8: 'hardware identification', 9: 'position initialisation', 14: 'stall overload', 16: 'phase A over-current' });
export const WARNING_BITS = Object.freeze({ 0: 'over-temperature warning (135 C)' });

export const feedbackFaultNames = (faults) => Object.entries(FEEDBACK_FAULTS).filter(([b]) => (faults >> (b - 16)) & 1).map(([, n]) => n);
export const faultFrameNames = (fault, warning) => [
  ...Object.entries(FAULT_BITS).filter(([b]) => (fault >>> b) & 1).map(([, n]) => n),
  ...Object.entries(WARNING_BITS).filter(([b]) => (warning >>> b) & 1).map(([, n]) => n)];

/** Python's round(): halves to even (the temperature field uses it). */
function roundHalfEven(x) {
  const f = Math.floor(x), d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

/** What a motor sends (the software RS-04 in emulator.js uses it). kind FEEDBACK or REPORT. */
export function encodeFeedback(motor, host, mode, faults, p, v, t, tempC, r = RS04, kind = FEEDBACK) {
  const cid = canId(kind, ((mode & 3) << 14) | ((faults & 0x3F) << 8) | (motor & 0xFF), host);
  const temp = Math.max(0, Math.min(FULL, roundHalfEven(tempC * 10)));
  return frame(cid, u16be(f2u(p, -r.p, r.p), f2u(v, -r.v, r.v), f2u(t, -r.t, r.t), temp));
}
export function encodeParamReply(motor, host, index, raw4, ok = true) {
  const raw = [...raw4, 0, 0, 0, 0].slice(0, 4);
  return frame(canId(READ_PARAM, ((ok ? 0 : 1) << 8) | motor, host), [...u16le(index), 0, 0, ...raw]);
}
export const encodeIdReply = (motor, uid) => frame(canId(GET_ID, motor, ID_REPLY_DEST), [...uid, 0, 0, 0, 0, 0, 0, 0, 0].slice(0, 8));
export function encodeFault(motor, host, fault, warning = 0) {
  const d = new Uint8Array(8), dv = new DataView(d.buffer);
  dv.setUint32(0, fault >>> 0, true); dv.setUint32(4, warning >>> 0, true);
  return frame(canId(FAULT, motor, host), d);
}

const be16 = (d, i) => (d[i] << 8) | d[i + 1];
const le16 = (d, i) => d[i] | (d[i + 1] << 8);
const le32 = (d, i) => (d[i] | (d[i + 1] << 8) | (d[i + 2] << 16) | (d[i + 3] << 24)) >>> 0;
const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/**
 * A frame a motor sent -> one of
 *   { type: 'feedback', motor, host, mode, faults, p, v, t, tempC, raw: [pu, vu, tu, temp] }
 *   { type: 'version', motor, host, version }
 *   { type: 'param', motor, host, index, ok, raw: [4 bytes] }      (value(reply) decodes it)
 *   { type: 'id', motor, uid: [8 bytes] }
 *   { type: 'fault', motor, host, fault, warning }
 * or null for anything else (including the frames a host sends: see parseRequest).
 */
export function parse(cid, data, r = RS04) {
  const [kind, d2, dest] = idFields(cid);
  const d = Array.from(data);
  if ((kind === FEEDBACK || kind === REPORT) && d.length === 8) {
    const motor = d2 & 0xFF, faults = (d2 >> 8) & 0x3F, mode = (d2 >> 14) & 0x3;
    if (d[0] === 0x00 && d[1] === 0xC4 && d[2] === 0x56) return { type: 'version', motor, host: dest, version: d.slice(3, 7).join('.') };
    const pu = be16(d, 0), vu = be16(d, 2), tu = be16(d, 4), temp = be16(d, 6);
    return { type: 'feedback', motor, host: dest, mode, faults, p: u2f(pu, -r.p, r.p), v: u2f(vu, -r.v, r.v),
      t: u2f(tu, -r.t, r.t), tempC: temp / 10.0, raw: [pu, vu, tu, temp] };
  }
  if (kind === READ_PARAM && d.length === 8)
    return { type: 'param', motor: d2 & 0xFF, host: dest, index: le16(d, 0), ok: ((d2 >> 8) & 0xFF) === 0, raw: d.slice(4, 8) };
  if (kind === GET_ID && dest === ID_REPLY_DEST) return { type: 'id', motor: d2 & 0xFF, uid: d };
  if (kind === FAULT && d.length === 8) return { type: 'fault', motor: d2 & 0xFF, host: dest, fault: le32(d, 0), warning: le32(d, 4) };
  return null;
}
/** A parameter reply's value (null for an index the table does not have). */
export const value = (reply) => (BY_INDEX[reply.index] ? unpackValue(BY_INDEX[reply.index], reply.raw) : null);

/** A frame a host sent, decoded: { kind, motor, host, fields } or null (what the emulator and the bridge act on). */
export function parseRequest(cid, data, r = RS04) {
  const [kind, d2, dest] = idFields(cid);
  const d = [...Array.from(data), 0, 0, 0, 0, 0, 0, 0, 0].slice(0, 8);
  if (kind === MIT) {
    const pu = be16(d, 0), vu = be16(d, 2), kpu = be16(d, 4), kdu = be16(d, 6);
    return { kind, motor: dest, host: null, fields: { p: u2f(pu, -r.p, r.p), v: u2f(vu, -r.v, r.v), kp: u2f(kpu, 0, r.kp),
      kd: u2f(kdu, 0, r.kd), t: u2f(d2, -r.t, r.t), raw: [pu, vu, kpu, kdu, d2] } };
  }
  const host = d2 & 0xFF;
  if (kind === GET_ID && dest !== ID_REPLY_DEST) return { kind, motor: dest, host, fields: {} };
  if (kind === ENABLE) return { kind, motor: dest, host, fields: {} };
  if (kind === STOP) {
    if (d[0] === 0 && d[1] === 0xC4) return { kind, motor: dest, host, fields: { version: true } };
    return { kind, motor: dest, host, fields: { clear_fault: d[0] === 1 } };
  }
  if (kind === SET_ZERO) return { kind, motor: dest, host, fields: { zero: d[0] === 1 } };
  if (kind === SET_ID) return { kind, motor: dest, host, fields: { new_id: (d2 >> 8) & 0xFF } };
  if ((kind === READ_PARAM || kind === WRITE_PARAM) && ((d2 >> 8) & 0xFF) === 0 && dest !== ID_REPLY_DEST) {
    const index = le16(d, 0), fields = { index };
    if (kind === WRITE_PARAM) fields.value = BY_INDEX[index] ? unpackValue(BY_INDEX[index], d.slice(4, 8)) : d.slice(4, 8);
    return { kind, motor: dest, host, fields };
  }
  if (kind === SAVE || kind === SET_BAUD || kind === REPORT || kind === SET_PROTOCOL)
    return { kind, motor: dest, host, fields: { f_cmd: d[6], magic_ok: same(d.slice(0, 6), kind !== SAVE ? MAGIC : [1, 2, 3, 4, 5, 6]) } };
  return null;
}

// ------------------------------------------------------------------------------- small helpers for tools and logs
export const hex = (bytes) => Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
export const unhex = (s) => Uint8Array.from((String(s).match(/../g) || []).map(h => parseInt(h, 16)));
