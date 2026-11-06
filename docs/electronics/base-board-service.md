# Removable turret base-board carrier

Issue #66; integration #61. This passive change keeps the existing PCB pose and adds a removable +X carrier. It changes no motor, gearing, torque, launcher speed or power requirement.

## Status

Geometry implemented; model acceptance remains incomplete after the detailed manufacturer checks failed. Physical fit, printer clearance, harness disconnection/slack and affected-base structural qualification are unverified. Do not treat this isolated mounting change as a turret print release.

The [component checklist](base-board-component-checklist.md) records exact hardware placements, assembly/service dependencies, missing connector and wiring envelopes, and the remaining acceptance evidence.
The [cut-stock and drilling plan](base-board-stock.md) defines the custom Ø3.2 PCB holes separately from the Ø3.4 printed carrier retainer holes.
The [disconnect candidate](base-board-interfaces.md) adds the rounded solder-side window, actual strain-relief anchor features, C2 pin map, interface drawing and bounded connector/service-space checks. Its authored connector reservations do not qualify the real harness; readiness remains false.

## Design contract

Preserve the pan-base foot (z <= 5 mm), bearing housing (radius <= 35.5 mm, z <= 38 mm), bearing-seat region (x +/-43, y +/-50, z 38..60 mm), and servo-pocket region (x -85..-25, y -50..60, z 0..65 mm). The PCB remains 50.8 x 30 x 1.6 mm at x 46.4..48, y +/-25.4, z 6..36; mounting centers y +/-22.4, z 9/33 mm. These are CAD design dimensions, not measured parts.

The proposed PA6-CF carrier has a 3 mm plate x 53..56, y +/-35, z 5.5..37.5, four inward PCB standoffs and four externally accessible M3 carrier screws. The carrier and PCB withdraw together along +X. Remove the robot bumper first; it blocks the lower driver paths and module extraction. PCB screws are accessed on the bench.

Hardware: four existing McMaster 91290A111 M3 x 6 PCB screws, four 91290A113 M3 x 8 carrier screws, eight 94459A140 M3 inserts. Private manufacturer STEP models are never exported publicly; authored public representations are labelled as simplified geometry.

## Required evidence

- Valid single solids and unchanged protected regions.
- Actual BREP insertion and removal against explicit obstacle sets, including the bumper-first dependency.
- Fastener seats, real holes, engagement, tip clearance and full driver envelopes.
- Original trapped geometry, retained bumper, incorrect screw length and missing holes must fail.
- Printed clearance and insert coupons must be measured before physical release.
- Harness connections must be accessible and their service slack measured before service is considered complete.

## Current evidence limits

The PCB uses the actual `turret_boards.py` footprint layout with drilled holes; components remain package envelopes, and solder tails/connectors are unverified. The isolated checker proves the carrier plus PCB and attached hardware move together. The released cad-agent v0.4.1 now supports rigid subassemblies, but this product has not integrated that API into its dossier; its sequence remains unqualified. No collision waiver substitutes for the missing product evidence.

The public model contains eight screws and eight inserts as labelled authored simplified hardware. Manufacturer fastener stages now require all three private normalized STEP inputs used by their geometry; they stop with a failing coverage verdict before loading geometry when any input is missing. Public and private hardware modes cannot mix. The final aggregate also requires every private model to be present and valid, independently of the per-stage results.

The 91290A113 M3x8 STEP remains absent. The initial single-part fetch returned no specification table, which alone did not prove an authentication failure. A single fresh Chrome session on 2026-10-29 at 08:16:39Z returned HTTP 200 with an explicit login requirement and no specification rows or CAD controls. This is evidence about that session, not all accounts or availability of the part. Cached specifications from 2026-10-27 remain historical; download, normalization and dimensional validation are still outstanding. See [the lookup lesson](../.agents/inbox/2026-10-29-missing-product-table-needs-rendered-evidence.md).

## Recorded model checks

`python cad/check_base_board_print.py` at `24b54a1` found a sampled minimum carrier wall of 1.497 mm against the declared 1.2 mm minimum. Its independent 0.6 mm thin-plate control failed as intended. The specified +90 degree rotation about Y gives a 32 x 70 mm footprint and 8 mm height. This is not a slicer or printed-fit result. Source hashes and full ray evidence are in `exports/turret/base-board-service/print-checks.json`.

The isolated hardware inventory is three SKUs and sixteen instances: eight screws and eight inserts. Four carrier screws and four anchor inserts are additional to the previous BOM; the existing four PCB screws/inserts move to the carrier.

The first manufacturer-backed run (`683ae9a`) failed rather than qualifying the mount: the real insert has a 0.105 mm thread lead-in and 5.53 mm useful thread span, giving 4.295 mm PCB-screw engagement and 4.895 mm carrier-screw engagement. The nominal 4.4/5 mm arithmetic excludes that lead-in. The checker now distinguishes grip from the usable thread start. It also registers detailed inserts individually; the volume-consistency check returned unknown for a screw and the previous compound of four receivers. An inconsistent reported volume does not establish that the Boolean geometry itself is wrong. Unknown outcomes remain failures, and negative controls must include a concrete failure of their intended mechanism.

## Latest complete run: 42db26b

The protected regions, rigid-module routes, deliberate obstruction controls and both public fastener groups passed. Each public fastener group passed 28 checks; deliberately short/long screws, missing holes and blocked tools were rejected for their intended reasons. With actual manufacturer inserts and the cached PCB screws, each group passed 24 checks and failed four tip checks on the toolkit's volume-conservation test. Those eight unknown results remain failures; the thread lead-in/engagement declarations themselves now pass.

This is a historical run, preserved unchanged. It used mixed private/public hardware because 91290A113 was absent. Independent review found that an empty private cache could make its purported manufacturer stage pass with 28 public-geometry checks. The corrected checker rejects empty and partial private caches and no longer offers that mixed mode. The old service and wall receipts retain their original source hashes; they do not qualify the revised checker. A new complete candidate run remains pending. The bounded regression command `python tools/test-base-board-manufacturer.py` covers both manufacturer stages with an empty cache and each single missing SKU, invalid/incomplete final coverage, strict loader behavior, and a real public BREP positive control.

The failure is not diagnosed as a frame or grouping defect. A separate native-frame experiment accidentally changed insert thread clocking and cannot establish frame invariance. `tools/probe-thread-boolean.py` is the corrected minimal reproducer: its `--frame canonical` applies the same rigid transform to both already positioned parts. It records private model hashes, toolkit code hash, runtime and the unchanged tolerances, without exporting vendor geometry. No tolerance relaxation is justified by the current evidence.

`checks.json` intentionally has `pass_model_checks: false`, `release_ready: false` and `physical_fit_verified: false`. This branch is not a print-release approval.

The minimal world-frame probe at product commit `991250a` independently reproduced the failure on x86_64 with CadQuery 2.8.0 / OCP 7.9.3.1, imported toolkit checkout `afccc71ddba2a7a858e8acbd39102969a1e7880d` (relations code hash recorded in `thread-probe.json`). That editable environment reports stale package metadata version0.1.0; use the source hash/commit, not its package label. The complete earlier compute-host run used the separately pinned v0.4.0 environment. Later probe receipts record the Git commits and OCP version directly. The committed probe receipt is the actual output, not rewritten to pretend it ran under the compute-host environment.
