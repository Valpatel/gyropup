# Rendered turret motion evidence

The Orin AGX bench uses cartridge geometry translated into a tilt frame. `cad/turret.py:Turret.pose_shape` subtracts `Geo.tilt_x` (48 mm in this snapshot), then raises the geometry onto the mount. That translation must also be applied to joint origins and effects. Exported vertices are local to their owning group; the group is placed once, relative to its parent. Pinion vertices are the documented legacy exception: exported in box coordinates and recentered by the loader.

The 2026-10-28 live defect was invisible in a zero-angle assembly: wheel and dial meshes carried a -48 mm local offset, while their declared origins were 48 mm too far forward. At 180 degrees their centers moved 96 mm. Motor envelopes were correctly stationary in the tilt group. The flap had the same datum error. Static mesh bounds alone passed for all 66 components / 151,176 triangles.

## Independent reference and coverage

`tools/reference-turret-motion.py` regenerates the reference using the pinned Git snapshot and cad-agent's pose generator. `tests/fixtures/turret-motion-reference.json` records independently audited mechanical datums in box millimetres, rather than copying the corrected display manifest. Datum sources at revision `3eb32ba649a2b0b66dd80c4a2dfb3179b0697f20`:

| Joint | Assembly-home pivot (mm) | Source / ownership |
| --- | --- | --- |
| Pan | 0, 0, 141 | Box TM face; carries pan and tilt |
| Tilt | 0, 0, 281 | TM + `Geo.tilt_t`; carries cartridge and motor housings |
| Feed dial | -48, 0, 281 | Cartridge origin minus `Geo.tilt_x` |
| Left / right wheel | 23, ±26.5125, 281 | `Geo.wheel_x - Geo.tilt_x`, ±`Geo.wheel_y` |
| Fill flap | -87, 0, 372 | `FILL_PORT.x - 19 - Geo.tilt_x`; hopper top + 6 |
| Pan pinion | -52.65, 0, 141 | Pan servo shaft; gear ratio -3 |

Reference landmarks are four affinely independent actual STL vertices per component. Their assembled rest positions come from the pinned, pre-fix export, whose zero-angle solid positions were correct; their ownership and physical axes are audited separately against CAD source. The fixture keeps vertex indices so browser tests capture those same actual vertices after the complete Three.js parent transform. Changing a mesh requires a new independently reviewed reference; do not bless a failing renderer by copying its positions into the fixture.

The test covers every exported component, 46 home/isolated/intermediate/end/compound poses, stationary motor housings, and normal live firing under combined pan and tilt. It deliberately displaces a shaft and requires rejection. It separately checks ball-pocket/chute alignment, actual barrel and laser front faces, CAD chronograph spacing (22/82 mm from the shoulder), configured launch speed, older robot CAD laser attachments, and phone layouts. `tools/test-turret-frames.py` checks all mesh vertices for finiteness, file integrity and bounds, actual rotor centering and reproducible coordinate regeneration.

```
python3 tools/test-turret-frames.py
npm run build
PORT=8879 node tools/serve-site.mjs
# In another terminal:
node tools/test-turret-motion.mjs
PLAYWRIGHT_BROWSER=webkit node tools/test-turret-motion.mjs
```

`SITE_URL=https://gyropup.com` validates the deployed application with the same test. Evidence goes to `/tmp/gyropup-turret-motion` (override `TEST_OUTPUT`). The contract and observed trace also run through cad-agent's independent `motion-trace` validator; see [cad-agent PR61](https://github.com/Valpatel/cad-agent/pull/61). CI runs the shipped-scene test on each PR.

## Artifact generation and limits

`python3 tools/reframe-turret-scene.py` deterministically regenerates this snapshot from pinned Git objects, checks the input manifest hash, translates only the six moving mesh files into corrected local frames, and updates their dependent metadata. It never increments already-corrected meshes. Rest geometry, normals, topology and manufacturing exports are unchanged. `cad/build_turret_box.py` implements the corrected coordinates for subsequent full CAD builds.

This is a sampled kinematic validation, not a continuous collision sweep, physical fit, force, hardware safety, feeding reliability or live hardware validation. Motor exports are whole purchased-part envelopes, so their cases stay fixed; no separate rotor mesh is claimed. Existing mass, torque, clearance and airflow reports retain their original build provenance and were not rerun by this coordinate-only migration. The audit separately identified the approximate 30-ball mass centroid's omitted -48 mm offset in the full-build estimate; track that physical-report correction with the turret hardware work before treating its torque estimate as current verification.
