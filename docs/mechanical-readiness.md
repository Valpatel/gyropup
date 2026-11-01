# Mechanical readiness and integration plan

> **Status guide — 2026-10-31:** The priority is the two ordered motor families: four RS-04 leg actuators and the Amazon PRO3115-900KV flywheel motors. Separate unpowered fit jobs are available; no complete turret or leg is released for fabrication or operation. The integration table below is historical. Current ownership and acceptance are tracked in [program #31](https://github.com/Valpatel/gyropup/issues/31) and [mechanical #61](https://github.com/Valpatel/gyropup/issues/61).

This is the component review entry point for the first physical turret and the complete Gyropup assembly. It supersedes blanket “print now” statements in older planning documents until their referenced geometry, hardware assumptions and checks are reconciled. It does not declare physical fit or safe operation.

Program tracker: [issue #61](https://github.com/Valpatel/gyropup/issues/61). The user requested a deliberate component-by-component review, hardware-complete models across legs and turret, consistent landing geometry, and a final repository state containing only `dev` and `main` branches.

## Current print-preparation checkpoint

| Interface | Available evidence and job | Still required |
| --- | --- | --- |
| Ordered 3115-900KV flywheel motor | [Exact listing, sample survey and sliced shaft gauge](ordered-turret-motor.md); all eight size labels survive the 0.4 mm slice, about 28 minutes / 8.5 g | Delivered-part dimensions, calibrated printed widths, mounting and shaft/retention design; the older SunnySky cartridge is a different motor |
| RS-04 leg mounting | [Corrected parent geometry](rs04-mounting-fit.md) and [retained unpowered coupon job](rs04-fit-job.md), about 6 h 33 min / 172.44 g | Inspect the unsupported roofs and all screw seats, measure the actual stack, resolve motor-side support/load spreading ([support-ring comparison](rs04-support-study.md)) and establish tightening/preload limits |

Both packages retain resolved profiles, executable toolpaths, source identities,
inspection images and blank measurement records. Slicer estimates and valid solids
are not physical measurements. The eight RS-04 support failures remain explicit;
no manufacturer mounting torque has been established. Small fit specimens come
before the full frames or a complete turret cartridge. Their successful printing
would not close structure, bearings, guarded rotating parts, cables or powered tests.

## Historical integration baseline and recorded blockers

| Source | What it represents | Use now |
| --- | --- | --- |
| Website baseline `e8d160d` (2026-10-29) | Public portal baseline, refreshed Progress page and canonical rendered robot, with the older turret hardware configuration | Preserve application behavior; do not infer complete physical assembly from its appearance |
| `turret/program` `14a4127` / PR15 | Newer mechanical and compute changes, including a front cartridge latch and different launcher assumptions | Design work in progress; latest structural geometry lacks complete regenerated gates |
| `turret/dossier` `630a2db` / PR27 | Eight subsystem registry and source-bound run-3 checks | Useful failure evidence for its own revision; it is not the final latch geometry |
| `body/program` `5fe10c6` / PR28 | Body/power/retention changes | Review deck load-path evidence, mass assumptions and battery interface measurements |
| `legrig/program` `d862b59` / PR30 | Rig predictions at 18.75 kg per leg and 36 V | Review tyre interference, ballast and new gate coverage before use |
| Candidate research PR46 | CAN ESC/servo and 3115 motor candidates | Research only; no selected motor/servo substitution or mating dimensions implied |

The handoffs contain different cradle push-up results (including 1.36 and 1.94 against a 2.0 target). Neither establishes acceptance of the final latch geometry. The audits also found a stop lug without a valid insertion route, a board enclosed in the pan-base pocket, twelve thin-wall findings, and stale exports after structural changes. Reproduce and close these on the integrated source; do not carry an earlier pass across a changed model.

The sources also disagree about motor KV, flywheel size and launch target. Freeze launcher fit-dependent output until the intended configuration and actual hardware dimensions are reconciled. Existing research speed/energy statements are not a certification. The newly requested 100 lb robot ceiling does not retroactively validate old load cases.

## Review order

1. **Baseline and bought interfaces.** Identify the actual motor/servo/compute/slip-ring variant, datum conventions, quantities and in-hand measurements. Preserve alternate studies separately. Start a hardware/geometry coverage ledger.
2. **Stationary base and service access.** Board insertion/removal, enclosure opening, connector withdrawal, fastener seats, inserts and tool access. Verify an achievable assembly sequence with real hardware geometry.
3. **Pan bearing and drive stack.** Bearing seats, clamp/spacer/circlip stack, servo horn, gear engagement/backlash, axial retention, ring coupling and cable path.
4. **Tilt yoke, stop lug and cradle.** Establish assembly order, accessible fasteners and valid hard-stop contact; resolve the structural shortfall with source-bound checks, not a lowered acceptance threshold.
5. **Cartridge, launcher and barrel interfaces.** Verify motor mounting stack, shaft/hub/washer/nut engagement, rotating versus fixed ownership, removable cartridge datums, retention and guarded clearances against the chosen hardware.
6. **Feed and reload hardware.** Hopper, lid, flap, dial, chute and sensors: wall thickness, print seams, serviceability and ammunition clearances. Separate simulated feed success from real foam-ball trials.
7. **Electronics and harness integration.** Mount all boards/connectors/ESCs and reserve cables, strain relief, plugs and thermal/service space. Keep the physical stop/ARM design and wiring review explicit.
8. **Bench mount and robot interface.** Stand stability, mounting face, plinth/compute/battery service path and body deck interface; verify the assembled mass/centre of mass and load assumptions.
9. **Legs, wheels and body.** Audit every link, bearing, adapter, shaft, clamp, stop, fastener and battery mount; close known strength/tyre-clearance/ballast issues and measurements before calling the full robot complete.
10. **Unified export and presentation.** Generate the permitted public meshes from the reviewed assembly. Show the same current robot in the landing page and all playgrounds; retain historical replay geometry with its historical data.

## Completion contract for every component

Each row in the forthcoming detailed register must include:

- Stable part identity, subsystem, required quantity and every assembly placement.
- Buy/print/cut process, exact part number or source revision, and geometry provenance: manufacturer CAD, measured model, drawing-based model, simplified preview or missing.
- Mating datum, axis and dimensions; actual head/nut/washer/insert geometry; engagement and available thread depth; tool and insertion paths.
- Print material, orientation, minimum walls, supported surfaces, fit allowance and printer/profile assumptions; expected finishing or inserts and a coupon where appropriate.
- Evidence tied to source/export hashes: topology, assembly, connectivity, containment, motion, structural/load case and slicer checks as relevant.
- Status that distinguishes **blocked**, **ready for fit coupon**, **ready for unpowered assembly trial**, **CAD checks passed**, and **physically verified**. A successful render is not any of the last three by itself.
- Exact next action and whether it requires a part measurement, a model correction, a computed check or a bench observation.

No unresolved critical load path, missing retention, impossible insertion or unverified rotating-part fit is silently classified as ready for a functional print. Coupons and noncritical unpowered fit samples may be released separately with their scope recorded.

## Geometry visibility and licensing

Bought hardware must be represented in the engineering assembly with verified dimensions and placements. McMaster/vendor models whose license disallows redistribution remain private. A public preview must use separately permitted geometry, with its representation basis visible in the coverage ledger; it must not silently publish private vendor meshes or claim that a simple envelope is a detailed component. Missing placements must fail a completeness check rather than disappear from a rendering unnoticed.

The first independent coverage audit found approximately 87 assembly mesh instances in the published landing robot: 27 non-turret fixed instances, 12 moving leg instances and 48 current turret instances. The rig manifest explicitly identifies its body as interim. The newer body branch has more geometry, but still has envelope components and does not establish hardware completeness. In particular, the current exporter puts four leg output adapters into the fixed body, although `cad/fivebar.py` places them in rotating upper-link frames. Correct ownership and actual rendered vertices must be checked together. That specific adapter error is corrected in the integration candidate by reviewed PR65: all four adapters and 36 attached screws follow their upper links, while the motor cases remain fixed. Validation covered 79 poses and deliberately wrong ownership/pivot cases. This does not establish full hardware coverage or physical leg qualification.

The turret dossier registers 72 part keys and 44 joints, but only two fastener groups (five screws). That is not coverage of its 112-line bench BOM. The leg BOM likewise contains many bought parts missing from the public scene. Catalogue `available` metadata is insufficient: the referenced model must exist, have a verified frame and license, and have the expected number of installed instances. Tools, spare parts and consumables require explicit non-installed classifications rather than pretend assembly meshes.

Keep four separate outcomes for every subsystem: **visual completeness**, **assembly and clearance**, **fabrication readiness**, and **physical acceptance**. None implies the others.

## Repeated release-candidate review

The user requires fresh critical reviews after a candidate appears complete. Each pass records the exact source/toolkit/export hashes, questions asked, observed failures, corrections and untested limits. A new geometry or placement revision invalidates affected evidence; it does not inherit a prior pass because its filename is unchanged.

1. **Engineering intent:** independently derive axes, seats, load paths and fastener engagement from drawings/measurements and CAD. Check configurations and units before running solvers.
2. **Manufacturing and assembly:** inspect the print orientation, thin features, supports, inserts, insertion order, tool clearance and removal. Exercise the fully assembled robot, including obstructing bumpers, cables and covers. Produce fit coupons before large structural prints where dimensions are unmeasured.
3. **Rendered mechanism:** capture actual browser vertices during compound poses, operation and repeated scene transitions. Deliberately inject a wrong parent/pivot, unit or sign and require rejection. A 0°/360° pair is one orientation, not a rotation sweep.
4. **Product use and presentation:** use desktop and narrow/tall/landscape phone layouts, both supported browser engines, touch/keyboard, loading/failure/retry, mute and repeated play/inspection. Inspect actual screenshots and interactive scenes; request a fresh GPT-6 Astra visual review on the final candidate.
5. **Integrated release rehearsal:** reproduce artifacts from the committed source, verify file/BOM/instance coverage and evidence freshness, then independent PR review and current CI. After deployment, verify the served revision and repeat affected interactions on that revision.

A failure returns the affected subsystem to correction and review, followed by an integrated regression pass. Repeated identical passing commands do not replace a missing measurement, a continuous-clearance argument, a load case, or a physical bench observation. Record unknowns rather than hiding them behind a green aggregate result.

## Audited historical gate limits

PR27's run-3 JSON reports connectivity 136 pass / 1 warning / 2 failures; assembly 220 pass / 6 failures; walls 16 pass / 12 failures; and motion 2 pass / 1 warning. Some prose counts differ. The geometry changed afterward, so these counts describe historical failure evidence only.

The motion configuration samples flywheels at 0° and 360° only; `max_step_deg`/`max_step_mm` are unset and `strict_contacts` is false. Assembly has no service/removal coverage. Each inspected gate says `physical_fit_verified:false`. Correct those coverage gaps before using new passes as release evidence. The historical full-kit print source named a Ø34 tyre while the program CAD used Ø38. The candidate now consumes the canonical selected tyre and rejects unbound/mixed print inputs; no regenerated or qualified full kit has been released. See [print source provenance](print-source-provenance.md).

The full robot's existing 37–37.75 kg studies do not establish the requested 100 lb (45.36 kg) ceiling. The FEA records were regenerated on cad-agent v0.6.0's humid PA6-CF and 6061-T6 data in [PR 135](https://github.com/Valpatel/gyropup/pull/135) (issue 29; before and after in `research/fea-v060-29/`). The hip-frame E1 result remains open: 1.63 at the 4 mm gate and 1.41 at 3 mm against 2.0, not converged. The leg has 7 strength cases below target, against 1 before (hip-frame E1): the upper link's E1, E1F and R3K, the front link's E1, and the hip frame's E1, E3o and R3o. Its joint checks all pass: the knee bearing's static factor is 1.13 in R3 (6301-2RS on SKF's C0). The turret has 9 cases below target on its layer-aware verdict, against 1 before. Measured wheel-clamp and battery-dock interfaces remain open too.

## Branch and release closure

Gyropup `dev` starts at the reviewed public main revision; feature work integrates there through reviewed PRs and current checks. `main` remains the deployed release. Finish the open mechanical PRs by integrating validated work or explicitly retiring superseded work with preserved evidence. Ancestry inventory is in [initial-refs.json](validation/consolidation/initial-refs.json); non-ancestor snapshots need patch/tree review before disposal.

For both Gyropup and cad-agent, final cleanup requires no open applicable PR, no unclassified unique commit, no lost dirty work and no environment importing a removed worktree. Keep the unrelated RL working tree intact. Detached worktrees may remain where editable environments need their paths; final branch refs are `dev` and `main`. Keep release tags and any explicitly documented recovery provenance; do not equate deleting a branch with validating its contents.

## Current carrier checkpoint — 2026-10-29

The website baseline is the reviewed Progress release: main `e8d160d` and dev `6bf9aeb` had equal trees. The currently deployed revision is available in the [site version manifest](https://gyropup.com/version.json). Rendered Mermaid, one BOM preview action, themed inspection, demo target knockdown and the decoded 12-second E1 study remain live. Progress now features that study and current evidence-linked updates, with detailed reports and history collapsed. Hosted Chrome/WebKit checks covered 21 layouts. E1 remains the historical 37.5 kg static load case with safety factor 1.65 against 2.0, not a new robot load qualification.

The engineering integration combines the program/dossier sources with that portal. Imported full-kit print files and gate reports remain historical. Current inspection exports and print-provenance checks establish bounded file/source evidence; no complete turret print kit has been regenerated or qualified. [The old v0 print plan](turret-print.md) is an archive. The separate [insert-fit specimens](../research/carrier-insert-fit/README.md) preserve two local orientations and provide blank measurement records; their 3MF files contain geometry only, with no printer profile, G-code or physical results.

The **stationary base and removable electronics carrier** remain a separate unfinished workstream after the two ordered-motor interfaces. The [current component register](base-board-component-checklist.md) records actual parts, placements, evidence and next actions. Reviewed PR67 and PR86 are integrated, including complete source binding, fail-closed geometry predicates, bounded connector poses and the 34-part support inspection assembly. Their independent engineering/browser reviews and negative controls passed. The two original mounting stacks remain intact. Full wired-module service, connector retention, support strength and physical fit remain unqualified; a housing path is not a routed-harness result.

The exact manufacturer STEP for retainer screw 91290A113 and support nut 90592A085 was acquired and normalized in PR86. It is no longer a missing-input blocker. Detailed-thread mating, heat-setting access, installed terminal/lead geometry and measured insert fits remain separate open questions. The earlier full thread probe timed out and established no mating pass.

The [supplier audit](../research/supply/turret-carrier-2026-10-29.md), [supply-protection comparison](../research/protection/carrier-input-protection.md), [native electrical candidate](../hardware/carrier-pan-protection/README.md) and [lower-loss architecture comparison](../research/protection/carrier-practical-architecture.md) are integrated. The native candidate has 29 parts and 102 leads with independent exported connectivity checks; it is not an allocated PCB or a qualified protection circuit. The full reference-network alternative still needs an actual package, thermal path and electrical qualification. Contact/seal incompatibility, fuse-holder documentation, wire bend limits, startup, charged-output stress and regeneration remain explicit constraints. The selected 12 V pan servo's 2.7 A stall rating supersedes using the 1.5 A modeled operating point as a supply-sizing maximum.

Cad-agent v0.4.2 is released at `2ad4269`, with validated-solid and aggregate volume-error predicates. The FEA records and the ordered-motor CI use v0.6.0 (`50d4921`) since PR 135; the retained fit job stays on v0.4.2, because its package records the hashes of the helpers it ships. Its preceding v0.4.1 provides the generic rigid-module API. Product checks use exact reviewed source revisions in isolated runs; existing project environments remain unchanged. The historical fused carrier checker does not establish full service through that API.

When returning to the carrier, its acceptance steps are:

1. Complete [issue96's shared packaging contract](https://github.com/Valpatel/gyropup/issues/96): actual component, terminal, PCB and thermal space, plus a noncircular assembly/removal order. PR97 and PR103 published the paper/source contract; actual component allocation and complete installation remain open.
2. Finish actual disconnects, junctions, solder-side insulation, strain relief, connector parking and bend-qualified cable routes. Validate the retained module and all remaining obstacles through the released rigid-module API, including prerequisite bumper/tool access.
3. Resolve detailed-thread mating, heat-setting access and physical measurements using the separate source-bound specimens. Preserve failed and absent observations; a nominal coupon model is not a measured fit.
4. Renew affected base/support structural and print evidence before a scoped unpowered assembly trial. Proceed to the pan drive and tilt assembly only after this carrier checkpoint is coherent.

No complete assembly or structural qualification has passed. The cradle, stop-lug, thin-wall, motor-variant and 100 lb load-case issues remain open. Independent combined publication review is required before the engineering candidate reaches dev/main; publishing explicitly unqualified evidence does not close fabrication gates. Final branch cleanup follows reviewed integration while preserving dirty work, private inputs, previews and environment-dependent worktrees.
