# Gate: turret-ammo

**PASS** · 6 checks: 6 pass, 0 warn, 0 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

None.

## Assumptions

- the biggest round is checked at the design pile's pocket positions and on the path's centre line
- the smallest round's checks are arithmetic on the pitch circle and the nip gap
- the model is checked, not the print: no tolerance stack, shrink or deflection

## Limits

- `diameters_mm`: [22.2, 22.8]
