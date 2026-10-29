# Removable turret base-board carrier

Issue #66; integration #61. This passive change keeps the existing PCB pose and adds a removable +X carrier. It changes no motor, gearing, torque, launcher speed or power requirement.

## Status

Design and validation in progress. Physical fit, printer clearance, harness disconnection/slack and affected-base structural qualification are unverified. Do not treat this isolated mounting change as a turret print release.

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

The PCB uses the actual `turret_boards.py` footprint layout with drilled holes; components remain package envelopes, and solder tails/connectors are unverified. The isolated checker proves the carrier plus PCB and attached hardware move together. The generic dossier's single-part assembly model cannot yet represent this bench subassembly, so its sequence remains unqualified; no collision waiver substitutes for that missing capability.

The public model contains eight screws and eight inserts as labelled authored simplified hardware. Engineering fastener checks use private manufacturer STEP for 91290A111 and 94459A140 where present. The 91290A113 M3x8 STEP was absent from the local cache; a sequential single-part fetch on 2026-10-29 failed because the returned page contained no specification table. Its public authored geometry is not manufacturer CAD, and complete manufacturer-model coverage is not claimed.

## Recorded model checks

`python cad/check_base_board_print.py` at `24b54a1` found a sampled minimum carrier wall of 1.497 mm against the declared 1.2 mm minimum. Its independent 0.6 mm thin-plate control failed as intended. The specified +90 degree rotation about Y gives a 32 x 70 mm footprint and 8 mm height. This is not a slicer or printed-fit result. Source hashes and full ray evidence are in `exports/turret/base-board-service/print-checks.json`.

The isolated hardware inventory is three SKUs and sixteen instances: eight screws and eight inserts. Four carrier screws and four anchor inserts are additional to the previous BOM; the existing four PCB screws/inserts move to the carrier.

The first manufacturer-backed run (`683ae9a`) failed rather than qualifying the mount: the real insert has a 0.105 mm thread lead-in and 5.53 mm useful thread span, giving 4.295 mm PCB-screw engagement and 4.895 mm carrier-screw engagement. The nominal 4.4/5 mm arithmetic excludes that lead-in. The checker now distinguishes grip from the usable thread start. It also registers detailed inserts individually; OCCT could not consistently subtract a screw from the previous compound of four receivers. Unknown kernel outcomes remain failures, and negative controls must include a concrete failure of their intended mechanism.
