// The RS-04 configuration tool's page: scan, parameters, ids, zero, telemetry, a limited jog behind an arm step, and
// per-motor config files. It knows nothing about any robot: the page that mounts it passes the build profiles, the
// joints (name -> CAN id), the zero poses and the transports. MIT licensed (LICENSE in this folder).
//
//   mountMotorTool(el, { profiles, joints, poses, transports, describeProfile })
//
// Safety, whatever the page passes: nothing is enabled without the arm step; STOP (the button, Space or Esc) sends a
// stop to every motor seen; jog frames stay inside the profile's jog limits and every write inside its cap (guard.js,
// and the bridge's rig/rs04_guard.py again on a real bus); arming needs canTimeout on, so a closed tab stops a motor;
// hiding the tab or losing the connection stops everything.
import * as P from './protocol.js';
import { createClient, NoReply, Refused } from './client.js';
import { createStrip } from './plot.js';

const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v; else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v); else if (v !== false && v != null) el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null) el.append(c);
  return el;
};
const fmt = (v, p) => (v == null ? '–' : typeof v === 'number' ? (p?.kind === 'f' ? Number(v.toPrecision(6)).toString() : String(v)) : String(v));
const JOG_HZ = 50;
const POLL_MS = 100;
export const CONFIG_SCHEMA = 'rs04-motor-config/1';

/** The rows that differ between two parameter sets (only keys both have, or every key of `want`). */
export function diffParams(live, want, tol = 1e-4) {
  const rows = [];
  for (const [name, w] of Object.entries(want)) {
    if (!(name in P.PARAMS)) continue;
    const l = live?.[name];
    const same = l != null && w != null && Math.abs(Number(l) - Number(w)) <= tol * Math.max(1, Math.abs(Number(w)));
    rows.push({ name, live: l ?? null, want: w, same });
  }
  return rows;
}

export function mountMotorTool(root, { profiles, joints = [], poses = [], transports = {}, describeProfile = null,
  storage = globalThis.localStorage } = {}) {
  if (!profiles?.length) throw new Error('mountMotorTool needs at least one build profile');
  let profile = profiles.find(p => p.default) || profiles[0];
  let client = null, transport = null;
  const motors = new Map();            // id -> { id, uid, firmware, params, dirty: Set, telemetry }
  let selected = null, jog = null, polling = null, stopped = false;

  // ---------------------------------------------------------------- layout
  root.classList.add('rs04-tool');
  const conn = h('div', { class: 'rs04-conn', 'data-kind': 'none', role: 'status', 'aria-live': 'polite' }, 'NOT CONNECTED');
  const transportSel = h('select', { 'aria-label': 'Transport', 'data-test': 'transport' },
    Object.entries(transports).map(([k, t]) => h('option', { value: k, text: t.label })));
  const connectBtn = h('button', { 'data-test': 'connect', onclick: () => (client ? disconnect('disconnected') : connect(transportSel.value)) }, 'Connect');
  const profileSel = h('select', { 'aria-label': 'Build profile', 'data-test': 'profile', onchange: () => setProfile(profileSel.value) },
    profiles.map(p => h('option', { value: p.id, text: `${p.title} (v${p.version})` })));
  profileSel.value = profile.id;
  const limitsLine = h('span', { class: 'rs04-limits', 'data-test': 'limits' });
  const stopBtn = h('button', { class: 'rs04-stop', 'data-test': 'stop', title: 'Stop every motor (Space or Esc)', onclick: () => stopAll('STOP button') },
    h('strong', {}, 'STOP'), h('small', {}, 'Space / Esc'));
  const bar = h('header', { class: 'rs04-bar' }, conn,
    h('div', { class: 'rs04-bar-controls' }, h('label', {}, 'Transport ', transportSel), connectBtn,
      h('label', {}, 'Profile ', profileSel), limitsLine), stopBtn);

  const scanBtn = h('button', { 'data-test': 'scan', onclick: () => scan() }, 'Scan bus');
  const scanNote = h('p', { class: 'rs04-note', text: 'New motors all answer as 127: connect one at a time to give each its id.' });
  const list = h('ul', { class: 'rs04-motors', 'data-test': 'motors' });
  const side = h('aside', { class: 'rs04-side' }, h('h2', {}, 'Motors'), scanBtn, scanNote, list);

  const tabs = ['Telemetry', 'Parameters', 'Setup', 'Jog', 'Config'];
  const tabBar = h('nav', { class: 'rs04-tabs', role: 'tablist' });
  const panes = {};
  for (const t of tabs) {
    panes[t] = h('section', { class: 'rs04-pane', role: 'tabpanel', 'data-pane': t.toLowerCase(), hidden: t !== 'Telemetry' });
    tabBar.append(h('button', { role: 'tab', 'data-tab': t.toLowerCase(), 'aria-selected': String(t === 'Telemetry'), onclick: () => showTab(t) }, t));
  }
  const main = h('main', { class: 'rs04-main' }, h('h2', { class: 'rs04-selected', 'data-test': 'selected' }, 'No motor selected'), tabBar, ...Object.values(panes));
  const logBox = h('ol', { class: 'rs04-log', 'data-test': 'log', 'aria-live': 'polite' });
  root.replaceChildren(bar, h('div', { class: 'rs04-body' }, side, main), h('footer', { class: 'rs04-footer' }, h('h2', {}, 'Log'), logBox));

  function showTab(t) {
    for (const k of tabs) {
      panes[k].hidden = k !== t;
      tabBar.querySelector(`[data-tab="${k.toLowerCase()}"]`).setAttribute('aria-selected', String(k === t));
    }
  }
  function log(text, level = 'info') {
    const li = h('li', { 'data-level': level }, h('time', { text: new Date().toLocaleTimeString() }), ' ', text);
    logBox.prepend(li);
    while (logBox.children.length > 200) logBox.lastChild.remove();
    return li;
  }
  const busy = async (what, fn) => {
    try { return await fn(); } catch (e) {
      log(`${what}: ${e instanceof Refused ? 'refused, ' : ''}${e.message}`, e instanceof Refused ? 'refused' : 'error');
      return undefined;
    }
  };
  const confirmDialog = (title, body, okText = 'Yes, do it') => new Promise((resolve) => {
    const dlg = h('dialog', { class: 'rs04-dialog', 'data-test': 'confirm' }, h('h3', { text: title }), ...[].concat(body).map(t => (typeof t === 'string' ? h('p', { text: t }) : t)),
      h('menu', {}, h('button', { value: 'cancel', 'data-test': 'cancel', onclick: () => dlg.close('cancel') }, 'Cancel'),
        h('button', { value: 'ok', class: 'rs04-primary', 'data-test': 'ok', onclick: () => dlg.close('ok') }, okText)));
    dlg.addEventListener('close', () => { dlg.remove(); resolve(dlg.returnValue === 'ok'); });
    root.append(dlg);
    dlg.showModal();
  });

  // ---------------------------------------------------------------- profile
  async function setProfile(id) {
    if (jog) { await disarm('the profile changed'); }
    profile = profiles.find(p => p.id === id) || profile;
    profileSel.value = profile.id;
    const l = profile.limits;
    limitsLine.textContent = `cap ${l.limit_torque_nm} N m · jog ${l.jog_torque_nm} N m, ${l.jog_speed_rad_s} rad/s · canTimeout ${l.can_timeout_ticks / P.TIMEOUT_TICKS_PER_S} s`;
    if (client) {
      log(`profile ${profile.id}: reconnect to apply its limits to the guard`, 'warn');
      await disconnect('the profile changed');
    }
    renderProfileInfo();
  }
  const profileInfo = h('div', { class: 'rs04-profile-info', 'data-test': 'profile-info' });
  async function renderProfileInfo() {
    const lines = [...(profile.notes || [])];
    if (describeProfile) { try { lines.unshift(...(await describeProfile(profile))); } catch { /* optional */ } }
    profileInfo.replaceChildren(h('h3', { text: `${profile.title} · profile v${profile.version}` }), h('ul', {}, lines.map(t => h('li', { text: t }))));
  }

  // ---------------------------------------------------------------- connection
  async function connect(key) {
    const t = transports[key];
    if (!t) return;
    conn.dataset.kind = 'connecting'; conn.textContent = 'CONNECTING…';
    try { transport = await t.open(); } catch (e) {
      conn.dataset.kind = 'none'; conn.textContent = 'NOT CONNECTED';
      log(`could not connect: ${e.message}`, 'error');
      return;
    }
    const lim = transport.hello?.limits;
    if (lim && JSON.stringify(lim) !== JSON.stringify(profile.limits)) {
      const other = profiles.find(p => JSON.stringify(p.limits) === JSON.stringify(lim));
      log(`the bridge enforces profile ${transport.hello.profile}: the page follows it`, 'warn');
      if (other) { profile = other; profileSel.value = other.id; await setProfile(other.id); }
    }
    client = createClient(transport, { limits: profile.limits });
    transport.onClose?.((why) => disconnect(`the connection closed (${why})`));
    transport.onRefused?.((r) => log(`bridge refused: ${r.why}`, 'refused'));
    const real = transport.kind === 'hardware';
    conn.dataset.kind = real ? 'hardware' : 'emulator';
    conn.textContent = real ? `REAL HARDWARE · ${transport.label}` : `EMULATOR · ${transport.label} · nothing real moves`;
    connectBtn.textContent = 'Disconnect';
    transportSel.disabled = true;
    stopped = false;
    log(`connected: ${transport.label}`);
    polling = setInterval(poll, POLL_MS);
    await scan();
  }
  async function disconnect(why) {
    if (!client) return;
    stopAll(why);
    clearInterval(polling); polling = null;
    const c = client; client = null;
    c.close();
    try { transport.close(); } catch { /* gone */ }
    transport = null;
    conn.dataset.kind = 'none'; conn.textContent = 'NOT CONNECTED';
    connectBtn.textContent = 'Connect';
    transportSel.disabled = false;
    log(`disconnected: ${why}`);
  }

  // ---------------------------------------------------------------- STOP
  function stopAll(why) {
    if (jog) { clearInterval(jog.timer); jog = null; renderJog(); }
    if (!client) return;
    const ids = client.stopAll();
    stopped = true;
    log(`STOP (${why}): stop sent to motors ${ids.join(', ')}`, 'stop');
    renderMotors();
  }
  const onKey = (e) => {
    if (!client) return;                 // nothing to stop: leave the keys to the page
    if (e.key === 'Escape' || (e.code === 'Space' && !(e.target instanceof HTMLTextAreaElement))) {
      e.preventDefault();
      stopAll(e.key === 'Escape' ? 'Esc' : 'Space');
    }
  };
  const onHide = () => { if (document.hidden && jog) stopAll('the tab was hidden'); };
  document.addEventListener('keydown', onKey, true);
  document.addEventListener('visibilitychange', onHide);
  const onUnload = () => { try { client?.stopAll(); } catch { /* closing */ } };
  globalThis.addEventListener?.('pagehide', onUnload);

  // ---------------------------------------------------------------- motors
  const jointOf = (id) => joints.find(j => j.id === id);
  function motor(id) {
    if (!motors.has(id)) motors.set(id, { id, uid: null, firmware: null, params: {}, dirty: new Set(), fb: null });
    return motors.get(id);
  }
  function renderMotors() {
    list.replaceChildren(...[...motors.values()].sort((a, b) => a.id - b.id).map(m => {
      const fb = client?.last.get(m.id), j = jointOf(m.id);
      const faults = fb ? P.feedbackFaultNames(fb.faults) : [];
      return h('li', { 'data-id': m.id, 'aria-current': String(m.id === selected) },
        h('button', { onclick: () => select(m.id), 'data-test': `motor-${m.id}` },
          h('strong', { text: `CAN id ${m.id}` }), ' ', h('span', { class: 'rs04-joint', text: j ? j.name : m.id === P.FACTORY_ID ? 'new (factory id)' : 'no joint' }),
          h('small', { text: `uid ${m.uid || '?'} · firmware ${m.firmware || '?'}` }),
          h('small', { class: faults.length ? 'rs04-bad' : '', text: `${fb ? P.MODES[fb.mode] : '–'}${faults.length ? ' · ' + faults.join(', ') : ''}${m.dirty.size ? ' · unsaved writes' : ''}` })));
    }));
  }
  async function scan() {
    if (!client) return;
    scanBtn.disabled = true;
    const found = await busy('scan', () => client.scan({ onProgress: (i) => { scanBtn.textContent = `Scanning ${i}/127…`; } }));
    scanBtn.textContent = 'Scan bus'; scanBtn.disabled = false;
    if (!found) return;
    for (const id of [...motors.keys()]) if (!found.some(f => f.id === id)) motors.delete(id);
    for (const f of found) {
      const m = motor(f.id);
      m.uid = f.uid;
      m.firmware = (await busy(`motor ${f.id} version`, () => client.version(f.id))) ?? m.firmware;
    }
    log(found.length ? `scan: ${found.map(f => `id ${f.id} (uid ${f.uid})`).join(', ')}` : 'scan: no motor answered (check power, both 120 ohm terminators and the 1 Mbit/s bit rate)', found.length ? 'info' : 'warn');
    if (!found.some(f => f.id === selected)) selected = found[0]?.id ?? null;
    renderMotors();
    if (selected != null) await select(selected);
    else renderSelected();
  }
  async function select(id) {
    selected = id;
    renderMotors();
    renderSelected();
    await readAll();
  }

  // ---------------------------------------------------------------- telemetry
  const strips = {};
  const telemetry = h('div', { class: 'rs04-strips' });
  const faultBox = h('div', { class: 'rs04-faults', 'data-test': 'faults' });
  panes.Telemetry.append(h('p', { class: 'rs04-note', text: 'While a motor is not armed its telemetry is polled with a stop frame (it keeps the motor stopped) and a VBUS read.' }),
    telemetry, faultBox, h('button', { 'data-test': 'clear-faults', onclick: () => clearFaults() }, 'Clear faults'));
  for (const [k, title, unit, digits] of [['p', 'Angle', 'rad', 3], ['v', 'Speed', 'rad/s', 2], ['t', 'Torque', 'N m', 2], ['tempC', 'Temperature', '°C', 1], ['vbus', 'Bus voltage', 'V', 1]])
    strips[k] = createStrip(telemetry, { title, unit, digits });
  let lastVbus = 0, frameRaf = null, pollCount = 0;
  let polling_now = false, arming = false;
  async function poll() {
    if (!client || selected == null || document.hidden || polling_now || arming) return;
    polling_now = true;
    try { await pollOnce(); } finally { polling_now = false; }
  }
  async function pollOnce() {
    const id = selected, now = performance.now() / 1000;
    if (!jog) await client.stop(id).catch(() => null);
    if (now - lastVbus > 0.5 && !jog) {
      lastVbus = now;
      const v = await client.read(id, 'VBUS').catch(() => null);
      if (v != null) strips.vbus.push(now, v);
    }
    const fb = client.last.get(id);
    if (fb && fb.at > now - 0.5) {
      for (const k of ['p', 'v', 't', 'tempC']) strips[k].push(fb.at, fb[k]);
      const f = client.faults.get(id), names = [...P.feedbackFaultNames(fb.faults), ...(f ? P.faultFrameNames(f.fault, f.warning) : [])];
      faultBox.textContent = names.length ? `Faults: ${names.join(', ')}` : 'No faults';
      faultBox.dataset.bad = String(names.length > 0);
      if (jog && Math.abs(fb.v) > profile.limits.jog_speed_rad_s * 1.5 + 0.3) stopAll(`motor ${id} reached ${fb.v.toFixed(2)} rad/s, past the jog speed`);
    }
    if (++pollCount % 10 === 0) renderMotors();
    if (!frameRaf) frameRaf = requestAnimationFrame(() => { frameRaf = null; Object.values(strips).forEach(s => s.draw()); });
  }
  async function clearFaults() {
    if (selected == null || !client) return;
    if (jog) { log('disarm before clearing faults', 'warn'); return; }
    const fb = await busy('clear faults', () => client.stop(selected, true));
    if (fb) { client.faults.delete(selected); log(`motor ${selected}: faults cleared (${P.feedbackFaultNames(fb.faults).join(', ') || 'none left'})`); }
  }

  // ---------------------------------------------------------------- parameters
  const paramBody = h('tbody');
  const unsaved = h('p', { class: 'rs04-unsaved', 'data-test': 'unsaved', hidden: true });
  panes.Parameters.append(
    h('div', { class: 'rs04-row' }, h('button', { 'data-test': 'read-all', onclick: () => readAll() }, 'Read all'),
      h('button', { 'data-test': 'save', class: 'rs04-primary', onclick: () => save() }, 'Save to the motor')),
    h('p', { class: 'rs04-note', text: 'A write changes the motor at once but only until it is powered off: Save keeps every written value.' }),
    unsaved,
    h('div', { class: 'rs04-table-wrap' }, h('table', { class: 'rs04-params', 'data-test': 'params' },
      h('thead', {}, h('tr', {}, ...['Parameter', 'Index', 'Value', 'Unit', 'Range', 'New value', ''].map(t => h('th', { text: t })))), paramBody)));
  function rangeText(p) {
    const lo = p.lo ?? '', hi = p.hi ?? '';
    let r = p.lo == null && p.hi == null ? '' : `${lo} .. ${hi}`;
    if (p.name === 'limit_torque') r += ` (profile cap ${profile.limits.limit_torque_nm})`;
    if (p.name === 'canTimeout') r = `1 .. ${profile.limits.can_timeout_max_ticks} (kept on)`;
    return r;
  }
  function renderParams() {
    const m = selected != null ? motors.get(selected) : null;
    paramBody.replaceChildren(...Object.values(P.PARAMS).map(p => {
      const input = p.writable ? h('input', { type: 'number', step: p.kind === 'f' ? 'any' : '1', 'aria-label': `New ${p.name}`, 'data-param': p.name }) : null;
      return h('tr', { 'data-param': p.name, title: p.note },
        h('td', {}, h('code', { text: p.name })), h('td', { text: `0x${p.index.toString(16).toUpperCase()}` }),
        h('td', { class: 'rs04-val', text: fmt(m?.params[p.name], p) }), h('td', { text: p.unit }), h('td', { text: rangeText(p) }),
        h('td', {}, input), h('td', {}, p.writable ? h('button', { onclick: () => writeParam(p.name, input.value), 'data-write': p.name }, 'Write') : ''));
    }));
    unsaved.hidden = !m?.dirty.size;
    unsaved.textContent = m?.dirty.size ? `Unsaved writes on motor ${m.id}: ${[...m.dirty].join(', ')}. They are lost at power-off unless saved.` : '';
  }
  async function readAll() {
    if (!client || selected == null) return;
    const id = selected, m = motor(id);
    const all = await busy(`motor ${id} read`, () => client.readAll(id));
    if (all) m.params = all;
    renderParams(); renderConfig();
  }
  async function writeParam(name, raw) {
    if (!client || selected == null) return;
    const p = P.param(name), id = selected;
    const v = p.kind === 'f' ? Number(raw) : Number.parseInt(raw, 10);
    if (raw === '' || !Number.isFinite(v)) { log(`${name}: enter a number`, 'warn'); return; }
    const got = await busy(`motor ${id} write ${name}`, () => client.writeCheck(id, name, v));
    if (got == null) return;
    const m = motor(id); m.params[name] = got; m.dirty.add(name);
    log(`motor ${id}: ${name} = ${fmt(got, p)} (volatile until Save)`);
    renderParams(); renderMotors(); renderConfig();
  }
  async function save() {
    if (!client || selected == null) return;
    const m = motor(selected);
    if (!(await confirmDialog(`Save motor ${m.id}'s parameters?`, ['Every value the motor holds now is kept over a power cycle.',
      m.dirty.size ? `Written this session: ${[...m.dirty].join(', ')}.` : 'Nothing was written this session.']))) return;
    if (await busy(`motor ${m.id} save`, () => client.save(m.id))) { m.dirty.clear(); log(`motor ${m.id}: saved`); renderParams(); renderMotors(); }
  }

  // ---------------------------------------------------------------- setup: ids, profile settings, zero
  const jointSel = h('select', { 'data-test': 'joint', 'aria-label': 'Joint' }, joints.map(j => h('option', { value: j.id, text: `${j.name} → CAN id ${j.id}` })));
  const poseSel = h('select', { 'data-test': 'pose', 'aria-label': 'Zero pose' }, poses.map(p => h('option', { value: p.key, text: p.name })));
  panes.Setup.append(
    h('h3', {}, 'Give the motor its joint id'),
    h('p', { class: 'rs04-note', text: 'The new id takes effect at once; Save keeps it. Only one motor may answer at the old id.' }),
    h('div', { class: 'rs04-row' }, jointSel, h('button', { 'data-test': 'setid', onclick: () => setId(Number(jointSel.value)) }, 'Set id')),
    h('h3', {}, 'Write the profile\'s settings'),
    h('p', { class: 'rs04-note', 'data-test': 'profile-config' }),
    h('div', { class: 'rs04-row' }, h('button', { 'data-test': 'apply-profile', onclick: () => applyProfile() }, 'Write and read back')),
    h('h3', {}, 'Set the zero'),
    h('p', { class: 'rs04-note', text: 'The present angle becomes zero. Put the joint in the named pose first, with the motor stopped.' }),
    h('div', { class: 'rs04-row' }, poseSel, h('button', { 'data-test': 'zero', onclick: () => zero(poseSel.value) }, 'Set zero here')),
    profileInfo);
  const profileConfigLine = panes.Setup.querySelector('[data-test="profile-config"]');
  async function setId(newId) {
    if (!client || selected == null) return;
    const m = motor(selected), j = jointOf(newId);
    if (newId === m.id) { log(`motor ${m.id} already has that id`, 'warn'); return; }
    if (motors.has(newId)) { log(`id ${newId} already answers on this bus: scan, or give that motor another id first`, 'refused'); return; }
    if (!(await confirmDialog(`Renumber motor ${m.id}?`, [`Motor ${m.id} (uid ${m.uid || '?'}) becomes CAN id ${newId}: ${j ? j.name : 'no joint'}.`,
      'Then Save on the Parameters tab keeps it.']))) return;
    const got = await busy(`motor ${m.id} setid`, () => client.setId(m.id, newId));
    if (got == null) return;
    motors.delete(m.id);
    const n = motor(got); Object.assign(n, { uid: m.uid, firmware: m.firmware, params: m.params, dirty: new Set([...m.dirty, 'CAN id']) });
    log(`motor ${m.id} is now CAN id ${got}${j ? ` (${j.name})` : ''}: save to keep it`);
    selected = got; renderMotors(); renderSelected(); renderParams();
  }
  async function applyProfile() {
    if (!client || selected == null) return;
    const id = selected, m = motor(id);
    for (const [k, v] of Object.entries(profile.motor_config)) {
      const got = await busy(`motor ${id} ${k}`, () => client.writeCheck(id, k, v));
      if (got == null) return;
      m.params[k] = got; m.dirty.add(k);
    }
    log(`motor ${id}: ${profile.id} settings written and read back (volatile until Save)`);
    renderParams(); renderMotors(); renderConfig();
  }
  async function zero(key) {
    if (!client || selected == null) return;
    if (jog) { log('disarm before setting the zero', 'warn'); return; }
    const pose = poses.find(p => p.key === key), id = selected;
    if (!pose) return;
    if (!(await confirmDialog(`Set motor ${id}'s zero at "${pose.name}"?`, [pose.text, `Source: ${pose.source}`], 'The joint is in this pose: set zero'))) return;
    if (!(await busy(`motor ${id} zero`, () => client.zero(id)))) return;
    const at = await busy(`motor ${id} mechPos`, () => client.read(id, 'mechPos'));
    motor(id).dirty.add('zero');
    log(`motor ${id}: zero set at "${pose.name}"; it reads ${at?.toFixed(4)} rad now. Save to keep it.`);
    renderMotors();
  }

  // ---------------------------------------------------------------- jog (armed)
  const checks = ['The motor is clamped, or the leg is in the air and clear of people and the stops.',
    'A hand is on STOP (Space or Esc works too), and the bench supply\'s switch is in reach.'];
  const checkBoxes = checks.map((t, i) => h('label', { class: 'rs04-check' }, h('input', { type: 'checkbox', 'data-test': `check-${i}` }), ' ', t));
  const armBtn = h('button', { 'data-test': 'arm', class: 'rs04-arm', onclick: () => arm() }, 'Arm this motor');
  const disarmBtn = h('button', { 'data-test': 'disarm', onclick: () => disarm('disarmed') }, 'Disarm');
  const jogState = h('p', { class: 'rs04-jogstate', 'data-test': 'jog-state' });
  const hold = (dir) => {
    const b = h('button', { class: 'rs04-jog', 'data-test': dir > 0 ? 'jog-plus' : 'jog-minus' }, dir > 0 ? 'Jog + ▶' : '◀ Jog −');
    const on = (e) => { e.preventDefault(); if (jog) jog.dir = dir; }, off = () => { if (jog) jog.dir = 0; };
    b.addEventListener('pointerdown', on); b.addEventListener('pointerup', off); b.addEventListener('pointerleave', off); b.addEventListener('pointercancel', off);
    return b;
  };
  panes.Jog.append(h('p', { class: 'rs04-note', 'data-test': 'jog-limits' }), ...checkBoxes, h('div', { class: 'rs04-row' }, armBtn, disarmBtn),
    jogState, h('div', { class: 'rs04-row' }, hold(-1), hold(1)));
  function renderJog() {
    const l = profile.limits;
    panes.Jog.querySelector('[data-test="jog-limits"]').textContent =
      `Arming writes canTimeout ${l.can_timeout_ticks} (${l.can_timeout_ticks / P.TIMEOUT_TICKS_PER_S} s) and limit_torque ${l.jog_torque_nm} N m (the jog torque), reads both back, then enables. ` +
      `Holding a jog button moves the target at ${l.jog_speed_rad_s} rad/s with Kp ${l.jog_kp_max}, Kd ${l.jog_kd_max}. Disarming restores limit_torque ${profile.motor_config.limit_torque} N m (unsaved).`;
    jogState.textContent = jog ? `ARMED: motor ${jog.id}, target ${jog.target.toFixed(3)} rad` : 'Not armed.';
    jogState.dataset.armed = String(!!jog);
    armBtn.disabled = !!jog; disarmBtn.disabled = !jog;
  }
  async function arm() {
    if (!client || selected == null || jog) return;
    if (!checkBoxes.every(c => c.querySelector('input').checked)) { log('tick both checks before arming', 'warn'); return; }
    const id = selected, l = profile.limits;
    arming = true;
    const ok = await busy(`arm motor ${id}`, async () => {
      await client.stop(id);
      await client.writeCheck(id, 'run_mode', 0);
      await client.writeCheck(id, 'canTimeout', l.can_timeout_ticks);
      await client.writeCheck(id, 'limit_torque', l.jog_torque_nm);
      client.arm([id]);
      const fb = await client.enable(id);
      return fb;
    });
    if (!ok || !client) { arming = false; client?.disarm([id]); return; }
    stopped = false;
    jog = { id, target: ok.p, dir: 0, timer: null, last: performance.now() };
    jog.timer = setInterval(jogTick, 1000 / JOG_HZ);
    arming = false;
    log(`motor ${id} ARMED (jog limits of ${profile.id})`, 'warn');
    renderJog(); renderMotors();
  }
  async function jogTick() {
    if (!jog || !client || jog.inflight) return;
    jog.inflight = true;
    try { await jogOnce(); } finally { if (jog) jog.inflight = false; }
  }
  async function jogOnce() {
    const now = performance.now(), dt = Math.min(0.1, (now - jog.last) / 1000), l = profile.limits;
    jog.last = now;
    jog.target += jog.dir * l.jog_speed_rad_s * dt;
    const j = jog;
    const fb = await client.mit(j.id, j.target, j.dir * l.jog_speed_rad_s, l.jog_kp_max, l.jog_kd_max, 0).catch((e) => {
      if (jog === j) stopAll(`jog frame failed: ${e.message}`);
      return null;
    });
    if (fb && jog === j) {
      if (fb.mode !== 2) stopAll(`motor ${j.id} left run mode (${P.MODES[fb.mode]}${fb.faults ? ', ' + P.feedbackFaultNames(fb.faults).join(', ') : ''})`);
      else if (Math.abs(fb.p - j.target) > 0.5) j.target = fb.p + Math.sign(j.target - fb.p) * 0.5;   // never wind up past what the torque can follow
      jogState.textContent = `ARMED: motor ${j.id}, target ${j.target.toFixed(3)} rad, at ${fb.p.toFixed(3)} rad, ${fb.t.toFixed(2)} N m`;
    }
  }
  async function disarm(why) {
    if (!jog) return;
    const id = jog.id;
    clearInterval(jog.timer); jog = null;
    await busy(`motor ${id} stop`, () => client.stop(id));
    client.disarm([id]);
    await busy(`motor ${id} limit_torque`, () => client.writeCheck(id, 'limit_torque', profile.motor_config.limit_torque));
    log(`motor ${id} disarmed (${why})`);
    renderJog(); renderMotors();
  }

  // ---------------------------------------------------------------- config files
  const diffBody = h('tbody', { 'data-test': 'diff' });
  const importArea = h('textarea', { rows: 6, 'data-test': 'import-text', 'aria-label': 'A motor config JSON', placeholder: 'Paste a motor config JSON, or choose a file' });
  const fileIn = h('input', { type: 'file', accept: 'application/json,.json', 'data-test': 'import-file', onchange: async () => { importArea.value = await fileIn.files[0].text(); importConfig(); } });
  const exportLink = h('a', { 'data-test': 'export-link', hidden: true });
  let stored = null;
  panes.Config.append(
    h('div', { class: 'rs04-row' }, h('button', { 'data-test': 'export', onclick: () => exportConfig() }, 'Export this motor\'s config'), exportLink),
    h('h3', {}, 'Compare with a stored config'), importArea,
    h('div', { class: 'rs04-row' }, fileIn, h('button', { 'data-test': 'import', onclick: () => importConfig() }, 'Compare'),
      h('button', { 'data-test': 'compare-profile', onclick: () => { stored = null; renderConfig(); } }, 'Compare with the profile')),
    h('h3', { 'data-test': 'diff-title' }),
    h('table', { class: 'rs04-diff' }, h('thead', {}, h('tr', {}, ...['Parameter', 'Motor now', 'Stored', ''].map(t => h('th', { text: t })))), diffBody));
  function configOf(m) {
    const fb = client?.last.get(m.id), j = jointOf(m.id);
    return { schema: CONFIG_SCHEMA, exported: new Date().toISOString(), uid: m.uid, can_id: m.id, joint: j?.key ?? null,
      firmware: m.firmware, profile: { id: profile.id, version: profile.version },
      angle_at_export_rad: fb ? Number(fb.p.toFixed(5)) : null, unsaved: [...m.dirty],
      params: Object.fromEntries(Object.entries(m.params).filter(([, v]) => v != null)) };
  }
  async function exportConfig() {
    if (selected == null) return;
    await readAll();
    const m = motor(selected), cfg = configOf(m);
    const blob = new Blob([JSON.stringify(cfg, null, 2) + '\n'], { type: 'application/json' });
    exportLink.href = URL.createObjectURL(blob);
    exportLink.download = `rs04-${cfg.joint || 'id' + m.id}-${(m.uid || 'unknown').slice(0, 8)}.json`;
    exportLink.textContent = `Download ${exportLink.download}`;
    exportLink.hidden = false;
    exportLink.click?.();
    log(`motor ${m.id}: config exported`);
  }
  function importConfig() {
    try {
      const c = JSON.parse(importArea.value);
      if (c.schema !== CONFIG_SCHEMA || typeof c.params !== 'object') throw new Error(`not a ${CONFIG_SCHEMA} file`);
      stored = c;
      log(`stored config loaded: CAN id ${c.can_id}, uid ${c.uid}, exported ${c.exported}`);
      if (selected != null && c.uid && motors.get(selected)?.uid && c.uid !== motors.get(selected).uid) log(`the stored config is from another motor (uid ${c.uid})`, 'warn');
    } catch (e) { log(`import: ${e.message}`, 'error'); stored = null; }
    renderConfig();
  }
  function renderConfig() {
    const m = selected != null ? motors.get(selected) : null;
    const want = stored ? stored.params : profile.motor_config;
    panes.Config.querySelector('[data-test="diff-title"]').textContent = stored
      ? `Motor ${m?.id ?? '?'} against the stored config of CAN id ${stored.can_id} (uid ${stored.uid})`
      : `Motor ${m?.id ?? '?'} against the ${profile.id} profile v${profile.version}`;
    const rows = diffParams(m?.params, want);
    diffBody.replaceChildren(...rows.map(r => h('tr', { 'data-same': String(r.same), 'data-param': r.name },
      h('td', {}, h('code', { text: r.name })), h('td', { text: fmt(r.live, P.PARAMS[r.name]) }), h('td', { text: fmt(r.want, P.PARAMS[r.name]) }),
      h('td', { text: r.same ? 'same' : 'differs' }))));
    profileConfigLine.textContent = Object.entries(profile.motor_config).map(([k, v]) => `${k} ${v}`).join(', ');
  }

  function renderSelected() {
    const m = selected != null ? motors.get(selected) : null, j = m && jointOf(m.id);
    main.querySelector('[data-test="selected"]').textContent = m ? `Motor ${m.id}${j ? ' · ' + j.name : ''}` : 'No motor selected';
    Object.values(strips).forEach(s => s.clear());
    renderParams(); renderJog(); renderConfig();
  }

  setProfile(profile.id);
  renderSelected();
  return {
    connect, disconnect, stopAll, scan, select, get client() { return client; }, get profile() { return profile; },
    get armed() { return jog ? [jog.id] : []; }, get stopped() { return stopped; },
    destroy() { disconnect('closed'); document.removeEventListener('keydown', onKey, true); document.removeEventListener('visibilitychange', onHide); globalThis.removeEventListener?.('pagehide', onUnload); },
  };
}
export { NoReply, Refused };
