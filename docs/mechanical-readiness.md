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

The last mechanical handoff records cradle push-up SF 1.94 against a 2.0 target, a stop lug without a valid insertion route, a board enclosed in the pan-base pocket, twelve thin-wall findings, and stale exports after structural changes. Reproduce and close these on the integrated source; do not carry an earlier pass across a changed model.

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

## Branch and release closure

Gyropup `dev` starts at the reviewed public main revision; feature work integrates there through reviewed PRs and current checks. `main` remains the deployed release. Finish the open mechanical PRs by integrating validated work or explicitly retiring superseded work with preserved evidence. Ancestry inventory is in [initial-refs.json](validation/consolidation/initial-refs.json); non-ancestor snapshots need patch/tree review before disposal.

For both Gyropup and cad-agent, final cleanup requires no open applicable PR, no unclassified unique commit, no lost dirty work and no environment importing a removed worktree. Keep the unrelated RL working tree intact. Detached worktrees may remain where editable environments need their paths; final branch refs are `dev` and `main`. Keep release tags and any explicitly documented recovery provenance; do not equate deleting a branch with validating its contents.

## Immediate next step

Complete the read-only subsystem and geometry audits, write the component register, and choose a contained passive assembly blocker first. No new heavy solve has started. Long CAD/FEA jobs run on an isolated compute checkout with exact source/toolkit revisions and recoverable logs. The promotional reel is deferred; issue60 only closes the existing website-test timing investigation.
