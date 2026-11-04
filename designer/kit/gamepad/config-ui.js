// The gamepad settings dialog: a live controller diagram, every action with its binding and a rebind flow,
// stick dead zone, full scale, response curve, trigger dead zone, per-axis inversion, rumble test and reset.
// Plain DOM in a native <dialog>. MIT licensed (LICENSE in this folder).
import { AXES, LABELS } from './gamepad.js';
import { bindingInputs, describeBinding } from './bindings.js';
import { createDiagram } from './diagram.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let serial = 0;

function loadCss() {
  if (document.querySelector('link[data-gamepad-css]')) return;
  const link = document.createElement('link');
  const url = new URL('./gamepad.css', import.meta.url);
  url.search = new URL(import.meta.url).search;     // keep a page's cache-busting version on the stylesheet too
  link.rel = 'stylesheet'; link.href = url.href; link.dataset.gamepadCss = '';
  document.head.append(link);
}

/**
 * mountGamepadConfig(control, { title, parent, closeButtons, css, intro }) -> { element, open(), close(), toggle(),
 * isOpen, destroy() }
 *
 * While it is open the controller's actions are suspended (so a menu press never also drives the page);
 * closeButtons (default ['Menu']) close it from the pad, and the suspension lasts until that button is released.
 */
export function mountGamepadConfig(control, { title = 'Gamepad', parent = document.body, closeButtons = ['Menu'], css = true, intro = '' } = {}) {
  if (css) loadCss();
  const id = `gpad-config-${++serial}`;
  const dialog = document.createElement('dialog');
  dialog.className = 'gpad-config';
  dialog.setAttribute('aria-labelledby', `${id}-title`);
  dialog.innerHTML = `<div class="gpad-head"><h2 id="${id}-title">${esc(title)}</h2>
      <p class="gpad-status" role="status" aria-live="polite"></p>
      <button type="button" class="gpad-close" aria-label="Close gamepad settings">✕</button></div>
    ${intro ? `<p class="gpad-intro">${esc(intro)}</p>` : ''}
    <div class="gpad-grid"><div class="gpad-view"></div>
      <div class="gpad-side">
        <section class="gpad-block"><h3>Controls</h3><table class="gpad-actions"><tbody></tbody></table></section>
        <section class="gpad-block gpad-tuning"><h3>Sticks and triggers</h3></section>
        <div class="gpad-foot"><button type="button" class="gpad-btn" data-reset>Reset to defaults</button>
          <button type="button" class="gpad-btn" data-rumble>Test rumble</button></div>
      </div></div>`;
  parent.append(dialog);
  const status = dialog.querySelector('.gpad-status');
  const diagram = createDiagram({ title });
  dialog.querySelector('.gpad-view').append(diagram.element);
  const body = dialog.querySelector('.gpad-actions tbody');
  const tuningBox = dialog.querySelector('.gpad-tuning');
  const rumbleBtn = dialog.querySelector('[data-rumble]');
  let release = null, pending = null, holdover = null;

  // ---- the action table, with a rebind button per action
  const rows = {};
  for (const [name, action] of Object.entries(control.actions)) {
    const tr = document.createElement('tr');
    tr.dataset.action = name;
    tr.innerHTML = `<th scope="row">${esc(action.label ?? name)}${action.hold ? ' <small>(hold)</small>' : ''}</th>
      <td class="gpad-binding"></td><td><button type="button" class="gpad-btn gpad-rebind">Change</button></td>`;
    tr.title = action.help ?? '';
    tr.querySelector('.gpad-rebind').onclick = () => (pending?.name === name ? cancelRebind() : rebind(name));
    body.append(tr);
    rows[name] = tr;
  }
  function paintBindings() {
    for (const [name, tr] of Object.entries(rows)) {
      if (pending?.name === name) continue;
      const binding = control.bindings.get(name), clash = control.bindings.conflicts(name);
      tr.querySelector('.gpad-binding').innerHTML = esc(describeBinding(binding))
        + (clash.length ? ` <small class="gpad-warn">also ${esc(clash.map((c) => control.actions[c].label ?? c).join(', '))}</small>` : '');
      tr.querySelector('.gpad-rebind').textContent = 'Change';
      tr.classList.remove('capturing');
    }
  }

  async function rebind(name) {
    cancelRebind();
    const action = control.actions[name], tr = rows[name], cell = tr.querySelector('.gpad-binding');
    tr.classList.add('capturing'); tr.querySelector('.gpad-rebind').textContent = 'Cancel';
    cell.textContent = action.kind === 'button' ? 'Press a button…' : 'Push a stick the way that means “more”, or press a button…';
    diagram.highlight(bindingInputs(control.bindings.get(name)));
    const me = pending = { name, capture: control.capture({ kinds: action.kind === 'button' ? ['button'] : ['button', 'axis'] }) };
    const first = await me.capture.promise;
    if (pending !== me) return;
    let binding = null;
    if (first?.type === 'button' && action.kind === 'button') binding = { button: first.button };
    else if (first?.type === 'axis') binding = { axis: first.axis, ...(first.sign < 0 ? { invert: true } : {}) };
    else if (first?.type === 'button') {
      cell.textContent = `${LABELS[first.button]} = more. Now press the button for “less” (or wait to leave it out)…`;
      me.capture = control.capture({ kinds: ['button'], timeoutMs: 4000 });
      const second = await me.capture.promise;
      if (pending !== me) return;
      binding = { positive: first.button, ...(second && second.button !== first.button ? { negative: second.button } : {}) };
    }
    pending = null;
    if (binding) control.bindings.set(name, binding);
    diagram.highlight([]);
    paintBindings();
  }
  function cancelRebind() {
    if (!pending) return;
    const p = pending; pending = null;
    p.capture.cancel();
    diagram.highlight([]);
    paintBindings();
  }

  // ---- tuning controls
  const sliders = [
    ['stickDeadZone', 'Stick dead zone', 0, 0.5, 0.01, (v) => `${Math.round(v * 100)}%`],
    ['stickOuter', 'Stick full scale at', 0.6, 1, 0.01, (v) => `${Math.round(v * 100)}%`],
    ['curve', 'Stick response curve', 1, 3, 0.1, (v) => (v === 1 ? 'linear' : `×${v.toFixed(1)} finer near centre`)],
    ['triggerDeadZone', 'Trigger dead zone', 0, 0.3, 0.01, (v) => `${Math.round(v * 100)}%`],
  ].map(([key, label, min, max, step, fmt]) => {
    const wrap = document.createElement('label');
    wrap.className = 'gpad-slider';
    wrap.innerHTML = `<span>${esc(label)}</span><output></output><input type="range" min="${min}" max="${max}" step="${step}">`;
    const input = wrap.querySelector('input'), out = wrap.querySelector('output');
    input.dataset.tuning = key;
    input.addEventListener('input', () => { control.setTuning({ [key]: +input.value }); out.textContent = fmt(+input.value); });
    tuningBox.append(wrap);
    return { key, input, out, fmt };
  });
  const inverts = document.createElement('fieldset');
  inverts.className = 'gpad-inverts';
  inverts.innerHTML = '<legend>Invert</legend>' + AXES.map((a) => `<label><input type="checkbox" data-invert="${a}"> ${esc(LABELS[a])}</label>`).join('');
  inverts.addEventListener('change', (ev) => { const a = ev.target.dataset.invert; if (a) control.setTuning({ invert: { [a]: ev.target.checked } }); });
  tuningBox.append(inverts);
  function paintTuning() {
    const t = control.tuning;
    for (const s of sliders) { s.input.value = String(t[s.key]); s.out.textContent = s.fmt(+t[s.key]); }
    for (const box of inverts.querySelectorAll('input')) box.checked = !!t.invert[box.dataset.invert];
  }

  dialog.querySelector('[data-reset]').onclick = () => { cancelRebind(); control.reset(); paintBindings(); paintTuning(); };
  rumbleBtn.onclick = () => control.rumble({ duration: 250, weak: 0.8, strong: 0.5 });
  dialog.querySelector('.gpad-close').onclick = () => close();
  // Escape cancels a rebind first; the next Escape closes.
  dialog.addEventListener('cancel', (ev) => { if (pending) { ev.preventDefault(); cancelRebind(); } });
  dialog.addEventListener('close', () => finishClose());

  // ---- live state
  function paintStatus(list) {
    const pads = list ?? control.pads();
    status.textContent = pads.length
      ? pads.map((p) => `${p.index + 1}: ${p.id.replace(/\s*\(.*$/, '') || 'gamepad'}${p.standard ? '' : ' (non-standard layout: buttons may differ)'}`).join(' · ')
      : 'No gamepad yet: connect one and press any button';
    const rumble = control.canRumble();
    rumbleBtn.disabled = !rumble;
    rumbleBtn.title = rumble ? 'Rumble every connected pad that supports it' : 'This browser or pad does not support rumble';
  }
  const offFrame = control.on('frame', (list) => { if (dialog.open) { diagram.update(list[0] ?? null); paintStatus(list); } });
  const offButton = control.on('button', ({ button, pressed }) => {
    if (dialog.open && pressed && !pending && closeButtons.includes(button)) close(true);
  });
  const offHold = control.on('frame', (list) => {
    if (!holdover) return;
    if (!list.some((p) => Object.values(p.buttons).some((b) => b.pressed))) { const r = holdover; holdover = null; r(); }
  });

  function open() {
    if (dialog.open) return;
    if (holdover) { holdover(); holdover = null; }
    release = control.suspend();
    paintBindings(); paintTuning(); paintStatus(); diagram.update(control.pads()[0] ?? null);
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
  }
  let closingFromPad = false;
  function close(fromPad = false) {
    if (!dialog.open) return;
    closingFromPad = fromPad;
    if (typeof dialog.close === 'function') dialog.close(); else { dialog.removeAttribute('open'); finishClose(); }
  }
  function finishClose() {
    cancelRebind();
    const r = release; release = null;
    // A pad press that closed the dialog must not also reach the page: hold the suspension until it is let go.
    if (r && closingFromPad) holdover = r; else r?.();
    closingFromPad = false;
  }

  return {
    element: dialog, open, close: () => close(false), toggle: () => (dialog.open ? close(false) : open()),
    get isOpen() { return dialog.open; },
    destroy() { close(false); offFrame(); offButton(); offHold(); holdover?.(); dialog.remove(); },
  };
}
