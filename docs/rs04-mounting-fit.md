# RS-04 mounting fit: leg-arrival candidate

This work corrects the motor mounting stack before the ordered RS-04 actuators arrive.
It is tracked in [issue #116](https://github.com/Valpatel/gyropup/issues/116), under the
[mechanical readiness tracker](https://github.com/Valpatel/gyropup/issues/61).
The parts are design candidates, not a print or operating release. No physical fit,
fastener preload, thread strength or powered fixture test has been completed.

## What changed

The RS-04 drawing guarantees **5 mm minimum usable thread** at the ten output-side
M4 mounting holes. Its STEP model has 7 mm drilled cylinders. That extra drill depth
does not authorize a longer screw. The manufacturer drawing and STEP are recorded
in [the actuator interface research](../research/actuator-interfaces.md#robstride-rs-04-swap-candidate)
and [interface catalog](../catalog/interfaces.json).

| Interface | Previous nominal penetration | Candidate geometry with M4 × 20 | Candidate nominal penetration |
| --- | --- | --- | --- |
| Hip frame | 6.9 mm, despite a 4.9 mm code comment | 24.1 mm frame, 8.5 mm counterbore, 15.6 mm grip | 4.4 mm |
| Dyno lug plate | 6.0 mm | 14 mm main plate with local head seats raised to 15.6 mm | 4.4 mm |
| Nominal motor-fit coupon | 6.0 mm; no counterbores | Exact motor-ring section of the parent hip frame | 4.4 mm |

The retained screw is McMaster-Carr **91290A168**, M4 × 0.7 × 20, class 12.9,
socket head Ø7 × 4 with a 3 mm hex drive. Its actual normalized manufacturer model
is a private engineering input. Public files contain authored printed parts only.
The catalog's price/availability date remains historical; no new purchase is implied.

The 0.6 mm nominal thread-depth reserve is **not a manufacturing tolerance budget**.
Screw-length variation, printing error and the actual mounting faces still need
measurement. A 4 mm minimum engagement is a geometric screening assumption, not a
thread pullout calculation or torque approval. Record measured screw length and grip;
reject penetration outside the validated range before trying the mounting screws.

## Preserve the rotating hub's space

Thickening the entire dyno plate would intersect the hub's Ø90 disc. Instead, the ten
Ø10 head-seat bosses sit on the Ø106 lug circle; their inner edges are 3 mm outside
the disc. A front relief of radius 46 mm ends at y=13 mm, while the disc's rear face
is nominally y=14 mm. The manufacturer's output offset of 0.5 ± 0.3 mm gives a
calculated axial gap of 0.7–1.3 mm before printing and assembly errors. These gaps
must be measured on the real fixture; they do not establish dynamic clearance under load.

Install motor lug screws before attaching the upper links. Link arms and stop dogs
can block later access; an empty screw hole does not prove assembled service access.

## A coupon that represents its parent

The nominal ring is clipped from `fivebar.hip_frame()`, preserving the full thickness,
counterbores, dowel holes and bearing seat. It uses the parent's outer-face-down
orientation from `build_leg.ROT['hip_frame']`. The ±0.1 mm rings remain bearing-fit
specimens only; they do not validate motor mounting. Use the same material,
conditioning and print process as the intended parent when conducting a fit trial.

Existing `exports/leg/` and `exports/rig/bench/` files predate this correction. They
are historical evidence and must not be used as a current motor-mount print kit.
New bounded checks and candidate exports must be generated from the revised source
and retain their source, toolkit and private-input hashes. A successful mesh export
alone does not approve fabrication.

## Validation and remaining leg work

The [first complete CAD run](../research/rs04-lug-stacks/README.md) confirms all
forty nominal screw depths but **fails eight receiver-support checks** near
factory-retainer recesses in the motor. The adjacent factory screw heads are
recessed too. These failures remain unresolved; the corrected depth alone does
not qualify the mounting interface.

The check uses cad-agent's measured fastener interfaces and exact geometric
relations, plus the drawing's usable-depth limit. It must reject the old seat depths,
missing manufacturer inputs, invalid geometry and inadequate engagement. Kernel
errors are failures, never zero interference. Evidence must distinguish nominal CAD
clearance from manufacturing and physical qualification.

The complete leg remains blocked by the failed hip-frame and knee-bearing cases in
[issue #29](https://github.com/Valpatel/gyropup/issues/29), wheel interface measurements
in [#24](https://github.com/Valpatel/gyropup/issues/24), the wheel redesign in
[#25](https://github.com/Valpatel/gyropup/issues/25), cable interference and coherent
rig validation in [#8](https://github.com/Valpatel/gyropup/issues/8). These are separate
acceptance steps; closing the mounting-stack issue cannot close them.
