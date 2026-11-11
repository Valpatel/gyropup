// Public simulator availability. Archived source/data remain available to research tools.
export const LEGACY_DESIGN = 'designs/default.json';
export const PUBLIC_DESIGNS = Object.freeze([
  Object.freeze({ group: 'Gyropup', name: 'Gyropup v2 (five-bar)', file: 'v2', available: true }),
  Object.freeze({ group: 'Gyropup', name: 'Gyropup v1 — unavailable', file: LEGACY_DESIGN, available: false }),
  Object.freeze({ group: 'Turret', name: 'Turret on the Orin AGX box', file: 'turret-box', available: true }),
]);
export const LEGACY_UNAVAILABLE = 'Gyropup v1 is unavailable while its concept is being reworked. Showing the current Gyropup instead.';
export function resolvePublicDesign(value) {
  return PUBLIC_DESIGNS.find(design => design.file === value && design.available)?.file ?? 'v2';
}
