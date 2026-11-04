// Gyropup's gamepad bindings for the playground: the reusable kit component (kit/gamepad/) mapped onto the
// simulator's own commands. Every stick and button goes through the same `command` functions the panel's sliders
// and buttons use, so the sliders' ranges and the turret's deck limit apply to the pad too.
import { createGamepadControl, describeBinding, mountGamepadConfig } from './kit/gamepad/index.js';
import { section } from './kit/panel.js';

/** The playground's actions and their default (Xbox layout) bindings. */
export const SIM_ACTIONS = {
  drive: { label: 'Drive forward / back', kind: 'axis', default: { axis: 'LeftY', invert: true } },
  turn: { label: 'Turn right / left', kind: 'axis', default: { axis: 'LeftX' } },
  pan: { label: 'Turret pan right / left', kind: 'axis', default: { axis: 'RightX' } },
  tilt: { label: 'Turret tilt up / down', kind: 'axis', default: { axis: 'RightY', invert: true } },
  height: { label: 'Body up / down', kind: 'axis', default: { positive: 'RT', negative: 'LT' } },
  lean: { label: 'Lean right / left', kind: 'axis', default: { positive: 'Right', negative: 'Left' } },
  pitch: { label: 'Nose down / up', kind: 'axis', default: { positive: 'Down', negative: 'Up' } },
  jump: { label: 'Jump', kind: 'button', default: { button: 'A' } },
  arm: { label: 'ARM', kind: 'button', hold: true, default: { button: 'Y' }, help: 'Hold to arm, as on the robot: flywheels and laser up while held; letting go stops the feed' },
  fire: { label: 'Fire one (while ARM is held)', kind: 'button', default: { button: 'B' } },
  burst: { label: 'Burst of 8 (while ARM is held)', kind: 'button', default: { button: 'RB' } },
  reload: { label: 'Reload', kind: 'button', default: { button: 'X' } },
  demo: { label: 'Demo on / off', kind: 'button', default: { button: 'View' } },
  menu: { label: 'Gamepad settings', kind: 'button', default: { button: 'Menu' } },
};
/** Full-stick rates for the inputs that move a setting rather than set it. */
export const RATES = { panDegS: 120, tiltDegS: 30, heightPerS: 0.8, pitchDegS: 20, leanMMs: 120 };
const R2D = 180 / Math.PI;

/**
 * mountSimGamepad({ stage, panel, topbar, before, sim }) -> { control, openSettings(), closeSettings() }
 * sim: { state, gun, demo, command, sliders: { drive, turn }, bench(), takeControl(), toggleDemo() }
 */
export function mountSimGamepad({ stage, panel, topbar, before, sim, storageKey = 'gyropup.gamepad.v1' }) {
  const control = createGamepadControl({ actions: SIM_ACTIONS, storageKey, autoStart: false });
  let settings = null;
  const bound = (name) => describeBinding(control.bindings.get(name));
  const openSettings = () => {
    settings ??= mountGamepadConfig(control, { title: 'Gamepad', closeButtons: () => [control.bindings.get('menu')?.button].filter(Boolean),
      intro: 'Any Xbox-layout controller. Sticks drive and aim, the triggers raise and lower the body; hold ARM to fire, as on the robot. The pad uses the same limits as the sliders.' });
    settings.open();
  };

  // ---- the panel section and a topbar pill that appears once a pad is connected
  const box = section(panel, 'Gamepad', { note: 'Xbox-style controller', open: false });
  box.innerHTML = '<p class="hud-note gp-pad-status" role="status" aria-live="polite"></p>';
  const status = box.querySelector('.gp-pad-status');
  const settingsBtn = document.createElement('button');
  settingsBtn.type = 'button'; settingsBtn.className = 'hud-btn'; settingsBtn.textContent = 'Gamepad settings';
  settingsBtn.onclick = openSettings;
  box.append(settingsBtn);
  const pill = document.createElement('button');
  pill.type = 'button'; pill.className = 'hud-pill on'; pill.id = 'gamepad-pill'; pill.hidden = true;
  pill.title = 'Gamepad connected: open its settings';
  pill.onclick = openSettings;
  topbar.insertBefore(pill, before ?? null);
  let hintUntil = 0, hintText = '';
  function paint() {
    const pads = control.pads(), now = performance.now();
    pill.hidden = !pads.length;
    pill.style.display = pads.length ? '' : 'none';   // .hud-pill sets display, which would override [hidden]
    pill.innerHTML = `<span class="dot"></span>${now < hintUntil ? hintText : pads.length > 1 ? `${pads.length} PADS` : 'GAMEPAD'}`;
    status.textContent = pads.length
      ? `Connected: ${pads.map((p) => p.id.replace(/\s*\(.*$/, '') || 'gamepad').join(', ')}. ${bound('menu')} opens the settings.`
      : 'Connect an Xbox-layout controller and press any button. Left stick drives, right stick aims, triggers set the height; hold Y (ARM) and press B to fire.';
  }
  const hint = (text) => { hintText = text; hintUntil = performance.now() + 2200; paint(); };
  control.on('connect', paint);
  control.on('disconnect', paint);
  paint();

  // ---- apply the pad once a frame, after the simulator's own frame
  const last = { drive: 0, turn: 0 };
  const claim = () => { if (sim.demo.on || sim.state.replay) sim.takeControl(); };
  const releaseArm = () => { if (sim.gun.armHeld) sim.command.arm(false); sim.bench()?.api.pad?.({}); };
  document.addEventListener('visibilitychange', () => { if (document.hidden) releaseArm(); });
  window.addEventListener('blur', releaseArm);

  function apply(dt) {
    if (hintUntil && performance.now() >= hintUntil) { hintUntil = 0; paint(); }
    if (control.pressed('menu')) { openSettings(); return; }
    const bench = sim.bench();
    const armHeld = control.held('arm');
    if (bench) {
      if (sim.gun.armHeld) sim.command.arm(false);
      bench.api.pad?.({ pan: -control.value('pan'), tilt: control.value('tilt'), arm: armHeld, trigger: control.held('fire') });
      if (control.pressed('fire') && !armHeld) hint(`HOLD ${bound('arm').toUpperCase()} TO ARM`);
      if (control.pressed('reload')) bench.api.reload();
      return;
    }
    if (!sim.state.robot) return;
    // Absolute: the stick's deflection is the speed or turn rate. Written only when it changes, so a resting pad
    // never fights the sliders.
    for (const [name, slider, set] of [['drive', sim.sliders.drive, sim.command.speed], ['turn', sim.sliders.turn, sim.command.turnDeg]]) {
      const v = control.value(name);
      if (Math.abs(v - last[name]) < 1e-3) continue;
      last[name] = v;
      claim();
      set(v * +slider.input.max);
    }
    // Rates: a held stick or button moves the setting; the command clamps it to its slider's range.
    const rate = (name, fn) => { const v = control.value(name); if (v && dt > 0) { claim(); fn(v * dt); } };
    rate('pan', (x) => sim.command.panDeg(sim.gun.pan * R2D - x * RATES.panDegS));
    rate('tilt', (x) => sim.command.tiltDeg(sim.gun.tilt * R2D + x * RATES.tiltDegS));
    if (!sim.state.jump) rate('height', (x) => sim.command.height(sim.state.height + x * RATES.heightPerS));
    rate('lean', (x) => sim.command.rollMM(sim.state.rollMM + x * RATES.leanMMs));
    rate('pitch', (x) => sim.command.pitchDeg(sim.state.pitch * R2D + x * RATES.pitchDegS));
    if (armHeld !== sim.gun.armHeld) sim.command.arm(armHeld);
    if (control.pressed('jump') && sim.command.jump()) control.rumble({ duration: 120, weak: 0.2, strong: 0.7 });
    for (const [name, n] of [['fire', 1], ['burst', 8]]) {
      if (!control.pressed(name)) continue;
      if (sim.command.fire(n, { needArm: true })) control.rumble({ duration: 60, weak: 0.5, strong: 0.3 });
      else hint(`HOLD ${bound('arm').toUpperCase()} TO ARM`);
    }
    if (control.pressed('reload')) sim.command.reload();
    if (control.pressed('demo')) sim.toggleDemo();
  }
  stage.onFrame((t, dt) => { control.poll(); apply(dt); });

  return { control, openSettings, closeSettings: () => settings?.close(), get settings() { return settings; } };
}
