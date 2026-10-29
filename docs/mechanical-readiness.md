# Mechanical readiness and integration plan

This is the component review entry point for the first physical turret and the complete Gyropup assembly. It supersedes blanket “print now” statements in older planning documents until their referenced geometry, hardware assumptions and checks are reconciled. It does not declare physical fit or safe operation.

Program tracker: [issue #61](https://github.com/Valpatel/gyropup/issues/61). The user requested a deliberate component-by-component review, hardware-complete models across legs and turret, consistent landing geometry, and a final repository state containing only `dev` and `main` branches.

## Current baseline and blockers

| Source | What it represents | Use now |
| --- | --- | --- |
| Published main `1475902` | Current public portal and canonical rendered robot, with the older turret hardware configuration | Preserve application behavior; do not infer complete physical assembly from its appearance |
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

The first independent coverage audit found approximately 87 assembly mesh instances in the published landing robot: 27 non-turret fixed instances, 12 moving leg instances and 48 current turret instances. The rig manifest explicitly identifies its body as interim. The newer body branch has more geometry, but still has envelope components and does not establish hardware completeness. In particular, the current exporter puts four leg output adapters into the fixed body, although `cad/fivebar.py` places them in rotating upper-link frames. Correct ownership and actual rendered vertices must be checked together.

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

The motion configuration samples flywheels at 0° and 360° only; `max_step_deg`/`max_step_mm` are unset and `strict_contacts` is false. Assembly has no service/removal coverage. Each inspected gate says `physical_fit_verified:false`. Correct those coverage gaps before using new passes as release evidence. The full-kit print source still names a Ø34 tyre while the program CAD uses Ø38; do not release a mixed kit.

The full robot's existing 37–37.75 kg studies do not establish the requested 100 lb (45.36 kg) ceiling. The hip-frame E1 result (1.65 vs 2.0) and undamped knee-bearing static factor (0.94 vs 1.0) remain open, together with measured wheel-clamp and battery-dock interfaces.

## Branch and release closure

Gyropup `dev` starts at the reviewed public main revision; feature work integrates there through reviewed PRs and current checks. `main` remains the deployed release. Finish the open mechanical PRs by integrating validated work or explicitly retiring superseded work with preserved evidence. Ancestry inventory is in [initial-refs.json](validation/consolidation/initial-refs.json); non-ancestor snapshots need patch/tree review before disposal.

For both Gyropup and cad-agent, final cleanup requires no open applicable PR, no unclassified unique commit, no lost dirty work and no environment importing a removed worktree. Keep the unrelated RL working tree intact. Detached worktrees may remain where editable environments need their paths; final branch refs are `dev` and `main`. Keep release tags and any explicitly documented recovery provenance; do not equate deleting a branch with validating its contents.

## Immediate next step

The independent subsystem and geometry audits are complete. Program and dossier sources have been combined on the unreleased integration branch, preserving current web behavior; their imported reports are historical. Finish the component register and the passive base-board mounting/service-access correction first, followed by the tilt assembly. An isolated compute environment is being prepared at cad-agent v0.4.0; no new heavy solve has started. The promotional reel is deferred. The website-test timing correction passed independent review and merged as PR62.
