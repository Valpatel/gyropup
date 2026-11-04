# Gamepad component

Standard gamepad (Xbox layout) control for any browser page: plain ES modules, no dependencies, no build step,
nothing loaded from a CDN. It knows nothing about the page that uses it, so the folder can be copied into another
project, or lifted out into its own repository, as it is. MIT licensed ([LICENSE](LICENSE)).

| File | What it gives you |
|---|---|
| `gamepad.js` | `createGamepads()`: hot-plug for several pads, polled once a frame; the W3C standard mapping under Xbox names (`BUTTONS`, `AXES`); radial stick dead zones, full-scale point and response curve (`shapeStick`); trigger dead zones (`shapeTrigger`); per-axis inversion; `rumble()` / `canRumble()` behind a feature check |
| `bindings.js` | `createBindings()`: actions bound to buttons, axes or button pairs; validation; persistence in `localStorage` (every access in try/catch, memory fallback when storage is blocked); clash detection; reset to defaults |
| `control.js` | `createGamepadControl()`: the one object a page uses. `value(name)`, `held(name)`, `pressed(name)`, `released(name)` after each poll; `'action'` events; rebind `capture()`; `suspend()`; tuning; rumble |
| `config-ui.js` | `mountGamepadConfig(control)`: a native `<dialog>` with a live controller diagram, every action with a **Change** (rebind) button, dead-zone / full-scale / curve / trigger sliders, per-axis invert, rumble test and reset |
| `diagram.js` | `createDiagram()`: the live Xbox-layout controller drawing in SVG (pressed buttons light up, sticks move, triggers fill) |
| `gamepad.css` | Dialog and diagram styles. Theme with the `--gpad-*` custom properties; by default they follow a page's `--surface-1`, `--surface-2`, `--text`, `--text-dim`, `--hairline` and `--cyan` tokens, or the browser's light or dark system colours |
| `demo.html` | A small working page: plug in a controller and open it |
| `gamepad.test.mjs` | Unit tests for the logic (`node --test designer/kit/gamepad/gamepad.test.mjs`) |

## Use it

```js
import { createGamepadControl, mountGamepadConfig } from './kit/gamepad/index.js';

const control = createGamepadControl({
  storageKey: 'my-game.gamepad.v1',
  actions: {
    move:  { label: 'Forward / back', kind: 'axis',   default: { axis: 'LeftY', invert: true } },  // up is +1
    steer: { label: 'Steer',          kind: 'axis',   default: { axis: 'LeftX' } },
    speed: { label: 'Throttle',       kind: 'axis',   default: { positive: 'RT', negative: 'LT' } },
    jump:  { label: 'Jump',           kind: 'button', default: { button: 'A' } },
    arm:   { label: 'Arm',            kind: 'button', default: { button: 'Y' }, hold: true },
    menu:  { label: 'Settings',       kind: 'button', default: { button: 'Menu' } },
  },
});
const settings = mountGamepadConfig(control, { title: 'Gamepad' });
control.on('action', ({ name, pressed }) => { if (name === 'menu' && pressed) settings.open(); });
control.on('frame', () => {
  player.speed = control.value('move');          // -1..1, dead zone and curve applied
  if (control.pressed('jump')) player.jump();    // true on the frame it went down
  player.armed = control.held('arm');
});
```

The controller polls on `requestAnimationFrame` by itself. To keep input in step with your own simulation, pass
`autoStart: false` and call `control.poll()` at the start of your frame instead.

### Bindings

| Binding | Reads |
|---|---|
| `{ button: 'A' }` | 0..1 (analogue triggers read their travel) |
| `{ axis: 'LeftY', invert: true }` | -1..1; `invert` flips it for this action only |
| `{ positive: 'RT', negative: 'LT' }` | positive − negative, -1..1 (two buttons as one axis) |
| `null` | unbound |

Names: buttons `A B X Y LB RB LT RT View Menu LS RS Up Down Left Right Guide`; axes `LeftX LeftY RightX RightY`
(Y is positive downwards, as the browser reports it). A `'button'` action takes a button; an `'axis'` action takes
an axis or a pair. Each action reads whichever connected pad pushes it furthest, so a second pad works without setup.

Rebinding (`control.capture({ kinds })`) ignores anything already held when it starts, suspends the actions meanwhile
and until the captured input is released (so the press that rebinds never also drives the page) and resolves with `{ type: 'button', button }`,
`{ type: 'axis', axis, sign }` or `null` (cancel or timeout). The dialog uses it: for an axis action, push the stick
the way that means "more" (the sign sets `invert`), or press a button for "more" and then one for "less".

### Tuning

`DEFAULT_TUNING`: stick dead zone 15 %, full scale at 95 % deflection, response exponent 1.5, trigger dead zone 6 %,
no axis inverted. The stick dead zone is **radial**: it acts on the stick's distance from centre, so a small diagonal
is not snapped onto an axis; the remaining travel is rescaled from the dead zone to full scale and shaped by the
exponent, keeping the direction. Tuning persists with the bindings; `control.reset()` restores both.

### Input and safety notes

- Polling only reads state. It never calls `preventDefault`, never takes focus and adds no keyboard or mouse
  listeners, so a page's keyboard and mouse controls keep working beside it.
- A pad that disconnects (or whose slot another pad takes) releases everything it held first. A page that
  implements a hold-to-run control (like an ARM button) should also release it when the tab is hidden (animation
  frames, and so polling, stop) and on window `blur` (another window has the user's attention, and some browsers stop
  updating pads for unfocused pages), and keep it released until the pad reports that button let go, so it must be
  pressed again; the playground does this.
- Pads with `mapping !== 'standard'` are read by index on a best-effort basis and flagged `standard: false`; the
  dialog says so.
- Browsers expose a pad only after a button press on the page, and only in a secure context (https or localhost).
- Rumble uses `vibrationActuator.playEffect('dual-rumble')` (Chromium) or `hapticActuators[0].pulse` (older Firefox)
  when present; otherwise `rumble()` returns false and the dialog's test button is disabled.

### Testing a page

Mock `navigator.getGamepads` before the page loads (Playwright `addInitScript`), with plain objects shaped like
Gamepad (`index`, `id`, `mapping: 'standard'`, `connected`, `axes[4]`, `buttons[17]` of `{ pressed, value }`).
Under software rendering a frame can take longer than a short press: hold a button until a poll has seen it before
releasing it. The Gyropup playground's suite is `tools/test-gamepad.mjs`.

## Adopt or build: the survey (2026-11-03)

The ask was to use the best free and open-source Xbox controller web UI elements, preferring MIT. We surveyed input
layers over the Gamepad API and visual controller widgets, and checked licence, upkeep, size, dependencies,
standard-mapping support, dead zones, remapping and hot-plug.

**Input layers**

| Candidate | Licence | Last change | Size, dependencies | Form | Standard mapping | Dead zones | Remap / persist | Hot-plug, rumble |
|---|---|---|---|---|---|---|---|---|
| [gamecontroller.js](https://github.com/alvaromontoro/gamecontroller.js) 1.5.0 | MIT | 2023-03 | 213 kB package, none | global script (`window.gameControl`) | yes | one per-axis threshold | no / no | events; vibration |
| [joypad.js](https://github.com/ArunMichaelDsouza/joypad.js) 2.3.5 | MIT | 2023-03 | 2.1 MB package, none | UMD | yes | one per-axis movement threshold | no / no | events; vibration |
| [joymap](https://github.com/diegodoumecq/joymap) 2.3.0 | MIT | 2026-06 | 338 kB package, lodash + fast-memoize | ES module build with bare `lodash/fp` imports (needs a bundler or an import map plus vendored lodash) | yes | one press threshold for all inputs | yes / no | yes; rumble |
| [gameinputjs](https://github.com/lunarcloud/gameinputjs) 13.3.2 | MIT | 2026-11 | 1.2 MB package (≈150 kB source + controller database and images), none | ES modules | own schema plus a model database | radial, per-stick override | no / no | yes; rumble |
| [gamepad.js](https://github.com/neogeek/gamepad.js) | MIT | 2020-08 | small, none | ES/UMD | yes | threshold | event binding / no | yes |
| [Controller.js](https://github.com/samiare/Controller.js), [HTML5 Gamepad Controller Library](https://github.com/kallaspriit/HTML5-JavaScript-Gamepad-Controller-Library) | no licence | 2022, 2014 | — | — | — | — | — | not usable |

**Controller diagrams and testers**

| Candidate | Licence | Last change | What it is | Why not vendored |
|---|---|---|---|---|
| [gamepad-viewer](https://github.com/e7d/gamepad-viewer) (Xbox One skin) | MIT (code) | 2026-08 | CSS-sprite SVG skins driven by its own script | Its README says the skins are reworked from artwork made for another viewer site whose licence we could not find (the original repository is gone), so the artwork's licence chain is not clear; sprite sheets also resist theming |
| [xbox360-svg-controller](https://github.com/ChetasLua/xbox360-svg-controller) | MIT | 2026-10 | one hand-built interactive SVG | 1.9 MB, an Xbox 360 layout, its own interaction model |
| [ControllerInputVisualizer](https://github.com/AnonymerNiklasistanonym/ControllerInputVisualizer) | MIT | 2021-08 | canvas visualiser with profiles | unmaintained, canvas only (no per-button DOM to theme or test) |
| [gamepadtest](https://github.com/luser/gamepadtest), [MDN gamepad example](https://github.com/mdn/dom-examples) | CC0 | 2020, 2026 | text-and-bars testers | no controller diagram; used as references for the raw API |

**Decision: build a thin layer on the raw Gamepad API, and draw our own diagram.** Since browsers normalise Xbox
pads to the W3C standard mapping, the polling and naming layer is about two hundred lines. What the owner asked
for beyond that (radial dead zones with a response curve and per-axis inversion, an action-binding layer persisted
in localStorage with reset, a rebind flow and a settings UI) is missing from every candidate, so it would be ours in
any case. Of the MIT input layers, gamecontroller.js and joypad.js have been unchanged since 2023, are global or UMD
scripts and only offer an axial threshold; joymap's ES build imports lodash by bare name, so it needs a bundler or an
import map with lodash vendored beside it; gameinputjs is active and the closest
match, but it would add about 150 kB, a second input schema and a controller database to cover what the standard
mapping already provides, with a single maintainer and thirteen major versions of API churn. A dependency-free core
is also the easiest to lift into its own repository. For the diagram, the one maintained MIT viewer has artwork with
an unclear upstream licence, and the other is 1.9 MB, so `diagram.js` draws the controller from simple shapes. The
only third-party material in this folder is the W3C standard-mapping order (the specification's button and axis
indices), which is a fact of the API rather than copied code.

## Moving it to its own repository

Copy this folder. It imports nothing outside itself; `demo.html` (drop its two `/web/theme.*` lines, which only the Gyropup site needs) and `gamepad.test.mjs` run as they are
(`node --test gamepad.test.mjs`, or serve the folder and open `demo.html`). Keep `LICENSE` with it.
