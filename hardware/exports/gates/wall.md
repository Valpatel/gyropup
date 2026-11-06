# Gate: wall

**FAIL** · 28 checks: 16 pass, 0 warn, 12 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

| Check | Status | Parts | Message |
|---|---|---|---|
| `wall:cartridge_body` | fail | cartridge_body | thinnest 0.002 mm < 0.8 mm (sampled; see witnesses) |
| `wall:compute_shell` | fail | compute_shell | thinnest 0.100 mm < 0.8 mm (sampled; see witnesses) |
| `wall:cradle` | fail | cradle | thinnest 0.200 mm < 0.8 mm (sampled; see witnesses) |
| `wall:dial` | fail | dial | thinnest 0.636 mm < 0.8 mm (sampled; see witnesses) |
| `wall:hopper` | fail | hopper | thinnest 0.617 mm < 0.8 mm (sampled; see witnesses) |
| `wall:hopper_lid` | fail | hopper_lid | thinnest 0.704 mm < 0.8 mm (sampled; see witnesses) |
| `wall:laser_mount` | fail | laser_mount | thinnest 0.400 mm < 0.8 mm (sampled; see witnesses) |
| `wall:pan_base` | fail | pan_base | thinnest 0.071 mm < 0.8 mm (sampled; see witnesses) |
| `wall:pan_ring` | fail | pan_ring | thinnest 0.025 mm < 0.8 mm (sampled; see witnesses) |
| `wall:pivot_spacer` | fail | pivot_spacer | thinnest 0.750 mm < 0.8 mm (sampled; see witnesses) |
| `wall:ring_carrier` | fail | ring_carrier | thinnest 0.002 mm < 0.8 mm (sampled; see witnesses) |
| `wall:tilt_yoke` | fail | tilt_yoke | thinnest 0.155 mm < 0.8 mm (sampled; see witnesses) |

## Assumptions

- thickness is measured by rays along the inward surface normal: mesh rays from triangle centroids (sub-sampled to max_rays) and exact B-rep rays from a UV grid on every face
- a pass means no sample was thinner than wall_mm - tol_mm; regions between samples and walls met at a slant are not measured
- the per-part wall_mm is the declared minimum; whether it suits the printer, nozzle, material and load is not checked
- a mesh reads curved walls thin by its chord error (about 0.09 mm seen on a 2.4 mm spherical shell tessellated at 0.05 mm); with the B-rep given, thin mesh samples are re-measured exactly and only confirmed ones fail; with a mesh alone, tol_mm must cover that error
- the model is checked, not the print: no shrink, elephant foot, or slicer perimeter rounding

## Limits

- `tol_mm`: 0.01
- `max_rays`: 20000
- `brep_grid`: [3, 16]
- `brep_spacing_mm`: 2.0
- `parts`: {"barrel": {"wall_mm": 0.8}, "board_bay": {"wall_mm": 0.8}, "board_bay_lid": {"wall_mm": 0.8}, "bumper_ring": {"wall_mm": 0.8}, "cartridge_body": {"wall_mm": 0.8}, "compute_shell": {"wall_mm": 0.8}, "compute_tray": {"wall_mm": 0.8}, "cradle": {"wall_mm": 0.8}, "dial": {"wall_mm": 0.8}, "flywheel": {"wall_mm": 0.8}, "flywheel_m": {"wall_mm": 0.8}, "flywheel_tyre": {"wall_mm": 0.8}, "flywheel_tyre_m": {"wall_mm": 0.8}, "hopper": {"wall_mm": 0.8}, "hopper_flap": {"wall_mm": 0.8}, "hopper_lid": {"wall_mm": 0.8}, "horn_boss": {"wall_mm": 0.8}, "laser_mount": {"wall_mm": 0.8}, "pan_base": {"wall_mm": 0.8}, "pan_pinion": {"wall_mm": 0.8}, "pan_ring": {"wall_mm": 0.8}, "pan_spacer": {"wall_mm": 0.8}, "pivot_spacer": {"wall_mm": 0.8}, "ring_carrier": {"wall_mm": 0.8}, "ring_driver": {"wall_mm": 0.8}, "stand_bottom": {"wall_mm": 0.8}, "stand_box": {"wall_mm": 0.8}, "tilt_yoke": {"wall_mm": 0.8}}
