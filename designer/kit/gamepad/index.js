// Standard gamepad (Xbox layout) control for the browser: one import for the whole component.
// MIT licensed (LICENSE in this folder). See README.md.
export { AXES, BUTTONS, DEFAULT_TUNING, LABELS, STICKS, canRumble, createGamepads, normalizeTuning, readPad, rumble,
  shapeStick, shapeTrigger } from './gamepad.js';
export { bindingInputs, createBindings, describeBinding, readBinding, safeStorage, validBinding } from './bindings.js';
export { createGamepadControl } from './control.js';
export { createDiagram } from './diagram.js';
export { mountGamepadConfig } from './config-ui.js';
