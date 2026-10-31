# RS04 support investigation

This is bounded research for [#116](https://github.com/Valpatel/gyropup/issues/116),
not a revised print kit or an accepted mounting design. The original eight
axial-stack failures remain in the [mounting receipt](../../exports/leg/rs04-mounting-fit/checks.json).
Its 40 drawing-depth checks pass; the support/load-spreading problem is separate.

The screw head loads 15.6 mm of printed grip, whose motor-side face partly
overhangs adjacent factory-retainer recesses at two lugs per motor. The factory
heads are 0.21 mm below the mounting plane. The printed material can distribute
load laterally, but neither the sampled axial fastener check nor the existing
global frame FEA measures that local load path. The manual supplies no mounting
M4 torque, preload, casing alloy, local bearing allowance or thread pull-out rating.
The older bench note's 2.5 N·m is not a manufacturer mounting approval.

## Comparison geometry

The probe compares eight authored ring concepts: ID80 or ID94, OD118 or OD120,
each in 0.080 inch (2.032 mm) or 0.125 inch (3.175 mm) stock. Those thicknesses are
listed for [6061-T6 sheet by SendCutSend](https://sendcutsend.com/materials/6061-aluminum/)
(accessed 2026-10-30). Material availability is not a strength result or an order.
Flatness, thickness tolerance, edge finish, machining and pocket fit are unresolved.

Each ring has ten Ø4.5 clearance holes on PCD106 and two provisional Ø5.3 dowel
clearances at the native 3°/183° axes. It occupies native z25..25+t, replacing equal
printed thickness. It would leave the motor/output/bearing datums and total 15.6 mm
nominal grip unchanged: frame pocket y−25.1..−25.1+t; dyno pocket y0..t. The remaining
printed grip would be 13.568 or 12.425 mm. These are design dimensions, not a checked
pocket, an accepted dowel fit, or a manufacturing tolerance stack.

Ring clearance is checked against **all 43 manufacturer solids**, plus the authored
leg output adapter and dyno hub at eight clock angles. In particular the Ø90 dyno
disc begins 14 mm beyond the case mounting face, while these proposed rings end at
3.175 mm or less. Radial overlap alone cannot establish a collision or clearance;
the probe evaluates the placed solids. The rings do not enter the print job: a
future parent pocket would retain the parent's print orientation and need renewed
coupon, support, dimensional and assembly evidence.

A stock washer has not been selected or substituted with an envelope. A washer
under the head alone does not restore the missing motor-side support. A washer
inserted at the motor interface changes its datum and grip unless recessed; it
also still needs a measured load path over the factory recess. A chosen washer
requires its actual manufacturer STEP and specification before comparison.

## Reproduce and interpret

Root runs this committed source in an isolated copy of the previous mechanical
task's CadQuery2.8.0/OCP7.9.3.1 environment with cad-agent v0.4.2 at `2ad4269`:

```sh
python -B research/rs04-support/probe.py --vendor-root references/vendor --out /absolute/new/probe-directory
```

The probe verifies the complete existing receipt and private/toolkit identities,
hashes all 43 vendor solids, measures the projected head-bearing footprints on the
actual motor plate with released `relate(..., contact_area=True)`, and records every
candidate relation. Each ring uses released `relation_table(..., only=[ring])`
with no pair cache and an explicit **0.01 mm broad-phase near margin**. Touch,
overlap, containment and volume-conservation tolerances retain their released
defaults. The near margin equals the default touch margin: any larger enclosing-box
gap already proves the solids apart under that nominal classification. This is
not a manufacturing clearance requirement. The table memoizes solid volume
integration and runs exact Boolean/distance queries where the boxes are within
0.01 mm. Its `get()` method is called for all
59 requested pairs; table iteration alone would omit the remote pairs.

Remote pairs carry `exact: false` and a `gap_lower_bound_mm`, not an exact measured
clearance. The report records the toolkit's analytic `bounding_box()` values,
manufacturer content identities and all 16 actual posed authored content identities.
The receipt verifier independently calculates box separation and requires a bound
strictly greater than the recorded 0.01 mm near margin. Every closer pair must be
exact. In particular motor-plate support must remain exact, touching and positive.
The original 1 mm broad phase spent more than 20 minutes integrating a factory
fastener with a proved 0.21 mm box gap. A separate timed diagnostic located that
cost inside adaptive volume integration, before any Boolean query. This policy
avoids that unnecessary measurement; it does not certify a usable 0.21 mm clearance.
No contact or overlap measurement is inferred from a bounding box. This optimization
does not skip any of the 472 candidate/counterpart pairs or change the ring geometry.

Invalid shapes, uncertain relations, missing inputs or source
changes fail the probe. It exports only the eight authored ring STEP files. Private
manufacturer CAD remains private. Baseline and footprint diagnostics are saved
before the candidate loop. Each ring has progress, elapsed time and kernel-query
statistics. Atomic `probe-incomplete.json` checkpoints survive an interrupted later
query; they remain explicitly incomplete and are removed only after the final
`probe.json` is written successfully. A complete public result directory has the
final JSON and exactly eight authored STEP files.

Run the kernel-free receipt and negative-control checks after collecting results:

```sh
python3 -B tools/test-rs04-support-probe.py
```

The default receipt is `research/rs04-support/results/probe.json`. The reviewed
manufacturer and authored-pose inventory fingerprints must be pinned in the verifier
after independent inspection of the real result. Until then, real-receipt validation
deliberately fails. `--pure` runs only synthetic orchestration/integrity controls;
it neither inspects geometry nor accepts a missing research result. Those controls
cover missing rows, changed inputs/artifacts, uncertain relations, invented bounds,
the 0.01 mm broad-phase boundary, lost exact plate contact, interrupted checkpoints and falsely
promoted readiness. A passing integrity test is not leg qualification.

Exit zero means the investigation completed, even if it found a collision. The
report always keeps engineering acceptance, structural qualification, fabrication
release and physical fit false. Candidate geometry has not altered the original
fastener checks or erased their failures.

Choosing a ring, its thickness, or retaining the original plastic requires positive
local bearing/bridge/preload evidence. Released `cadagent.fea.Study` is linear
elastic, excludes contact/preload and excludes support/load-patch elements from its
design stress. Its usual scalar safety factor cannot by itself qualify this local
bearing problem. A later analysis or test must report those interfaces explicitly,
including contact opening, print compression/creep, ring deflection and motor-thread
capacity. No guessed tightening torque is introduced by this probe.
