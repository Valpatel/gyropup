// The RS-04 tool's safety rules on every frame a host sends, the same rules as the bridge's rig/rs04_guard.py (whose
// docstring lists them). The tool runs them on every transport (the bridge runs them again on the real bus), and both
// are checked against the scenarios in vectors.json. MIT licensed (LICENSE in this folder).
import * as P from './protocol.js';

export const CONFIRM_S = 10.0;
const COMMANDS = ['iq_ref', 'spd_ref', 'loc_ref'];
const OK = Object.freeze({ ok: true, code: 'ok', why: '' });
const no = (code, why) => ({ ok: false, code, why });
const g = (v) => String(Number(v.toPrecision(6)));

/** limits: { limit_torque_nm, jog_torque_nm, jog_speed_rad_s, jog_kp_max, jog_kd_max, can_timeout_max_ticks }. */
export function createGuard(limits, { clock = () => performance.now() / 1000 } = {}) {
  const lim = { ...limits };
  const seen = new Set(), armed = new Set(), confirmed = new Map();

  function observe({ id, data, ext = true }) {
    if (!ext) return;
    const m = P.parse(id, data);
    if (m?.type === 'id') seen.add(m.motor);
    else if (m?.type === 'param' && m.ok && P.BY_INDEX[m.index]) {
      const name = P.BY_INDEX[m.index].name;
      if (['run_mode', 'limit_torque', 'canTimeout'].includes(name)) {
        if (!confirmed.has(m.motor)) confirmed.set(m.motor, {});
        confirmed.get(m.motor)[name] = [Number(P.value(m)), clock()];
      }
    }
  }
  function arm(ids) {
    const missing = ids.filter(i => !seen.has(i));
    if (missing.length) return no('not-seen', `motor ${missing[0]} has not answered a scan in this session`);
    ids.forEach(i => armed.add(i));
    return OK;
  }
  function disarm(ids) { if (ids == null) armed.clear(); else ids.forEach(i => armed.delete(i)); }
  const stopTargets = () => [...new Set([...seen, ...armed, P.FACTORY_ID])].sort((a, b) => a - b);

  function ready(motor) {
    if (!seen.has(motor)) return no('not-seen', `motor ${motor} has not answered a scan in this session`);
    if (!armed.has(motor)) return no('not-armed', `motor ${motor} is not armed: arm it first`);
    const c = confirmed.get(motor) || {}, now = clock();
    for (const name of ['run_mode', 'limit_torque', 'canTimeout'])
      if (!c[name] || now - c[name][1] > CONFIRM_S) return no('not-confirmed', `motor ${motor}: read ${name} back just before arming`);
    if (c.run_mode[0] !== 0) return no('mode', `motor ${motor} is in run_mode ${g(c.run_mode[0])}: the tool runs MIT (0) only`);
    if (c.limit_torque[0] > lim.jog_torque_nm + 1e-6)
      return no('jog-torque', `motor ${motor} holds limit_torque ${g(c.limit_torque[0])} N m: over the profile's jog torque ${g(lim.jog_torque_nm)} N m`);
    const to = c.canTimeout[0];
    if (to < 1 || to > lim.can_timeout_max_ticks)
      return no('watchdog', `motor ${motor} has canTimeout ${g(to)}: it must be on (1..${lim.can_timeout_max_ticks})`);
    return OK;
  }

  function write(motor, index, v) {
    const p = P.BY_INDEX[index];
    if (!p) return no('unknown', `parameter 0x${index.toString(16).toUpperCase().padStart(4, '0')} is not in the RS-04 table`);
    if (!p.writable) return no('read-only', `${p.name} is read-only`);
    v = Number(v);
    if (!Number.isFinite(v)) return no('range', `${p.name}: not a number`);
    if ((p.lo != null && v < p.lo - 1e-6) || (p.hi != null && v > p.hi + 1e-6))
      return no('range', `${p.name} ${g(v)} is outside the manual's ${p.lo}..${p.hi}`);
    if (p.name === 'limit_torque' && v > lim.limit_torque_nm + 1e-6)
      return no('cap', `limit_torque ${g(v)} N m is over the profile's cap ${g(lim.limit_torque_nm)} N m`);
    if (p.name === 'canTimeout' && !(v >= 1 && v <= lim.can_timeout_max_ticks))
      return no('watchdog', `canTimeout ${g(v)} would turn the watchdog off or past ${lim.can_timeout_max_ticks} (the tool keeps it on)`);
    if (p.name === 'run_mode' && v !== 0) return no('mode', 'the tool runs MIT mode (run_mode 0) only');
    if (COMMANDS.includes(p.name) && v !== 0) return no('command', `${p.name} is a motion command: the tool moves motors only by its limited jog`);
    if (['run_mode', 'limit_torque', 'canTimeout'].includes(p.name)) delete (confirmed.get(motor) || {})[p.name];
    return OK;
  }

  /** May this frame go on the bus? { ok, code, why }. A refused frame must not be sent. */
  function check({ id, data, ext = true }) {
    if (!ext) return no('not-rs04', 'only 29-bit RS-04 frames are sent');
    const req = P.parseRequest(id, data);
    if (!req) return no('unknown', `not an RS-04 request (type ${P.idFields(id)[0]})`);
    const k = req.kind, m = req.motor;
    if (k === P.SET_BAUD || k === P.SET_PROTOCOL) return no('forbidden', 'bit-rate and protocol changes are not sent by this tool');
    if (k === P.GET_ID || k === P.READ_PARAM || k === P.REPORT) return OK;
    if (k === P.STOP) return req.fields.version && armed.has(m) ? no('armed', `motor ${m} is armed: disarm before reading the version`) : OK;
    if (k === P.ENABLE) return ready(m);
    if (k === P.MIT) {
      const r = ready(m);
      if (!r.ok) return r;
      const f = req.fields;
      if (Math.abs(f.t) > lim.jog_torque_nm + 0.01) return no('jog-torque', `feed-forward ${f.t.toFixed(2)} N m is over the jog torque ${g(lim.jog_torque_nm)} N m`);
      if (Math.abs(f.v) > lim.jog_speed_rad_s + 0.01) return no('jog-speed', `speed ${f.v.toFixed(2)} rad/s is over the jog speed ${g(lim.jog_speed_rad_s)} rad/s`);
      if (f.kp > lim.jog_kp_max + 0.1 || f.kd > lim.jog_kd_max + 0.01)
        return no('jog-gain', `Kp ${f.kp.toFixed(1)} / Kd ${f.kd.toFixed(2)} over the profile's ${g(lim.jog_kp_max)} / ${g(lim.jog_kd_max)}`);
      return OK;
    }
    if (armed.has(m)) return no('armed', `motor ${m} is armed: disarm before writing, zeroing, renumbering or saving`);
    if (k === P.SET_ID) {
      const nw = req.fields.new_id;
      if (seen.has(nw) && nw !== m) return no('id-taken', `id ${nw} already answers on this bus`);
      seen.delete(m); confirmed.delete(m);
      return OK;
    }
    if (k === P.SET_ZERO || k === P.SAVE) return OK;
    if (k === P.WRITE_PARAM) return write(m, req.fields.index, req.fields.value);
    return no('unknown', `type ${k} is not sent by this tool`);
  }

  return { observe, check, arm, disarm, ready, stopTargets, limits: lim,
    get armed() { return [...armed]; }, get seen() { return [...seen]; } };
}
