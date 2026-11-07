# Rendered turret motion evidence

The Orin AGX bench uses cartridge geometry translated into a tilt frame. `hardware/cad/turret/turret.py:Turret.pose_shape` subtracts `Geo.tilt_x` (48 mm in this snapshot), then raises the geometry onto the mount. That translation must also be applied to joint origins and effects. Exported vertices are local to their owning group; the group is placed once, relative to its parent. Pinion vertices are the documented legacy exception: exported in box coordinates and recentered by the loader.

The 2026-10-28 live defect was invisible in a zero-angle assembly: wheel and dial meshes carried a -48 mm local offset, while their declared origins were 48 mm too far forward. At 180 degrees their centers moved 96 mm. Motor envelopes were correctly stationary in the tilt group. The flap had the same datum error. Static mesh bounds alone passed for all 66 components / 151,176 triangles.

## Independent reference and coverage

`tools/engineering/turret/reference-turret-motion.py --revision <full-reviewed-commit>` regenerates `tests/fixtures/turret-motion-reference.json` from an immutable accepted full scene and the pinned toolkit pose generator. The audited datums and explicit 80-name ownership table come from CAD source, not the display manifest. Whole feed/flywheel motor envelopes remain on the tilting cartridge; the pan/tilt servo cases remain on their supports, the wheel/dial/flap rotors have separate owners, and the pinion is the documented root mesh in box coordinates. The historical datum sources were audited at revision `4769888bf0334608ff997faeff5e663d96a1a70d` (PR 196: the D76 turret straight on the box deck, a full build; until then the October snapshot `3eb32ba649a2b0b66dd80c4a2dfb3179b0697f20`):

| Joint | Assembly-home pivot (mm) | Source / ownership |
| --- | --- | --- |
| Pan | 0, 0, 145 | Box TM face (`turret_box.Z_TM`); carries pan and tilt |
| Tilt | 0, 0, 285 | TM + `Geo.path_t` + `Geo.tilt_c` (140); carries cartridge and motor housings |
| Feed dial | -48, 0, 285 | Cartridge origin minus `Geo.tilt_x` |
| Left / right wheel | 25, ±25.81, 285 | `Geo.wheel_x - Geo.tilt_x`, ±`Geo.wheel_y` |
| Fill flap | -87, 0, 376 | `FILL_PORT.x - 19 - Geo.tilt_x`; hopper top + 6 |
| Pan pinion | -52.65, 0, 145 | Pan servo shaft; gear ratio -3 |

Reference landmarks are four affinely independent actual STL vertices per component. Their assembled rest positions come from the pinned full-build export (each mesh in its group frame, placed by the audited pivots; the generator asserts the scene's own frames agree); their ownership and physical axes are audited separately against CAD source. The fixture keeps vertex indices so browser tests capture those same actual vertices after the complete Three.js parent transform. Changing a mesh requires a new independently reviewed reference; do not bless a failing renderer by copying its positions into the fixture.

The historical reference exercised every exported component in 46 home/isolated/intermediate/end/compound poses, stationary motor housings, and normal live firing under combined pan and tilt. Current pose coverage is generated from the independently audited ranges rather than retaining that historical count. It deliberately displaces a shaft and requires rejection. It separately checks ball-pocket/chute alignment, actual barrel and laser front faces, CAD chronograph spacing (22/82 mm from the shoulder), configured launch speed, older robot CAD laser attachments, and phone layouts. `tests/evidence/test-turret-frames.py` checks all mesh vertices for finiteness, file integrity and bounds, actual rotor centering and reproducible coordinate regeneration.

```
python3 tests/evidence/test-turret-frames.py
npm run build
PORT=8879 node tools/site/serve-site.mjs --ephemeral
# In another terminal:
node tests/site/models/test-turret-motion.mjs
PLAYWRIGHT_BROWSER=webkit node tests/site/models/test-turret-motion.mjs
```

`SITE_URL=https://gyropup.com` validates the deployed application with the same test. Evidence goes to `/tmp/gyropup-turret-motion` (override `TEST_OUTPUT`). The contract and observed trace also run through cad-agent's independent `motion-trace` validator; see [cad-agent PR61](https://github.com/Valpatel/cad-agent/pull/61). CI runs the shipped-scene test on each PR.

## Current recovery acceptance

The source at `ec44a63730caafbdeb7a927cc77b5c9a968086f6` retains the audited pivots and right-handed CAD `(x,y,z)` → page `(y,z,x)` mapping, and extends the mechanical tilt range to −25/+12 degrees. Pan ±170 degrees is bounded viewer coverage; the CAD pan is continuous, not stopped there. The separate +10-degree firing ceiling is a simulated feed criterion pending bench proof. The actual module label/class and physical fit, feeding and HIL remain unresolved.

The current reference generator rejects unknown/missing/duplicate names, different display ownership, units/frame changes, malformed or nonfinite STL data, and coplanar landmarks. It binds the immutable manifest and every mesh byte. Existing Python and browser consumers require that binding to match current files and the actual responses loaded by the renderer. A manifest-derived owner must not become the expected owner.

The existing real-renderer wrong-pivot control preserves home geometry and fails a quarter turn. Additional actual renderer controls exercise an extra unit conversion, reversed tilt sign, lost pan parent and a whole motor case wrongly attached to a wheel. The latter ownership/parent mutations also preserve home geometry. All keep the existing 0.02 mm acceptance tolerance. The genuine current scene and immutable reference were accepted separately before fleet253 ran the existing motion test in Chromium141.0.7390.37 and WebKit26.0. Independent review of its actual sealed traces and capture is linked below; an old reference or synthetic parser fixture is not substituted for current geometry evidence.

Run builds and substantial browser/native validation on the fleet under a reviewed bounded packet. Use the existing pinned toolkit environment for reference generation and the independent `motion-trace` report; a system-global package is not the recorded toolkit. Preserve the returned pose/asset hashes, every negative control and the original evidence limitations.

## Artifact generation and limits

`python3 tools/engineering/turret/reframe-turret-scene.py` deterministically regenerates this snapshot from pinned Git objects, checks the input manifest hash, translates only the six moving mesh files into corrected local frames, and updates their dependent metadata. It never increments already-corrected meshes. Rest geometry, normals, topology and manufacturing exports are unchanged. `hardware/cad/builders/build_turret_box.py` implements the corrected coordinates for subsequent full CAD builds. The shipped snapshot is now such a full build (the D76 turret, PR 196), so the reframer no longer reproduces it and the frames test checks the full build's datums instead.

This is a sampled kinematic validation, not a continuous collision sweep, physical fit, force, hardware safety, feeding reliability or live hardware validation. Motor exports are whole purchased-part envelopes, so their cases stay fixed; no separate rotor mesh is claimed. Existing mass, torque, clearance and airflow reports retain their original build provenance and were not rerun by this coordinate-only migration. The audit separately identified the approximate 30-ball mass centroid's omitted -48 mm offset in the full-build estimate; track that physical-report correction with the turret hardware work before treating its torque estimate as current verification.

The current browser consumer also exercises the native tilt slider and actual servo frame loop through the +12° stop, then checks that a spun-up model holds its queued feed above the separate +10° firing ceiling. The explicitly enabled model laser reference must follow ARM and go off on release; its display keeps the actual hardware class unverified. Those controls supplement the immutable landmark/asset oracle and do not establish physical interlocks or measured feed performance. The genuine current two-engine result is recorded below; these are virtual behavior checks, not physical interlock or hardware qualification.


## Current sampled runtime result, 2026-11-07

[Fleet253 independent artifact review](https://github.com/Valpatel/gyropup/pull/255#pullrequestreview-5813302236) verifies both actual browser engines against the immutable `ab493a36` scene reference: **80 components × 47 required poses**, at the unchanged **0.02 mm** landmark tolerance. The largest point error is **0.00000758 mm**; the largest fitted pivot-anchor diagnostic is **0.000174 mm**. All actual loaded mesh/manifest bytes and ownership are bound to the served build. Units, reversed axis, lost parent and rotating whole-motor faults exceed 1 mm, while the deliberately preserved home poses remain below tolerance. Pan ±170° remains bounded viewer sampling, not a mechanical hard stop or continuous-clearance proof.

The actual native slider/servo reaches +12°. Both engines record 15 armed, spun-up frames with two queued commands held above the separate +10° simulated firing ceiling, and execute the model-laser ARM/release checks. Each also checks 25 legal-fire landmark frames and the virtual chronograph against the configured model speed. Those other live landmark samples were checked by the audited existing test but not separately serialized; the 47-pose traces, upper-stop and seeded-fault samples are retained. Four phone widths and a landscape viewport are checked, including an actual 390 px screenshot.

The same genuine build produced all 480 source-bound highlight frames. [Independent sealed highlight review](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6709535643) separately accepted the six encoded outputs: both companions decode to 660 frames / 22 seconds, all six segments move, original historical E1 labels and the poster match, and all 25 negative controls reject. Fleet254 itself remains FAILED because its shallow worker omitted the E1 renderer's historical Git object; the unchanged full guard passed later on a fresh sealed extraction, and again after coherent adoption. Neither that failed receipt nor the media receipts were resealed.

This resolves sampled viewer/transform and media behavior, not the underlying hardware findings. In particular, scene airflow remains failed at **10.1% loss against 10%**, and sampled exhaust/plume clearance remains failed at **0 mm against 10 mm**. Actual laser label/class, measured feeding/fit, manufacturing and HIL remain unresolved. Historical feed/FEA failures keep their original source and scope.
