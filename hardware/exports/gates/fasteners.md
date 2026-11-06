# Gate: fasteners

**PASS** · 35 checks: 35 pass, 0 warn, 0 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

None.

## Exclusions (declared)

- hopper_screws#0, hopper_screws#1: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws#0, hopper_screws#2: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws#1, hopper_screws#0: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws#1, hopper_screws#2: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws#2, hopper_screws#1: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws#2, hopper_screws#0: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- laser_foot_screws#0, laser_foot_screws#1: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- laser_foot_screws#1, laser_foot_screws#0: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design

## Assumptions

- Each fastener is read along its own axis from the declared seat (dossier fastener() axes); the model is checked, not the hardware: no tolerance stack, no print shrink, no torque or pull-out rating.
- Threads are envelopes: engagement is the axial overlap of the screw with the receiver's modelled thread region (material at 0.92 d/2 or just outside d/2 but inside d + hole_clearance/2, whichever starts first; gaps up to 1.5 pitches bridged, so crests and relief grooves read as one region), not proof of strength.
- The head bears where lines parallel to the axis (FastenerOptions.lines angles x three rings between shank and head rim) first meet the clamped part: the outer ring must bear at every angle, the inner ones may run through a chamfer at the hole, and the stack needs one clean ring per angle. Holes are measured by radial rays at 8 angles and three depths per clamped part. Features between the samples are missed.
- Without a placed screw solid the head is the declared head_d_mm x head_h_mm, else 1.6 d x 1.0 d (socket head), and the length is the record's length_mm.
- The tool is the declared envelope (stepped cylinders and an optional swing disc), swept straight along the axis from the head top; it is checked against the parts present at the assembly step that installs the fastener (parts no step fits count as present).
- Minimum engagement is the declared min_engagement_mm, else min_engagement_d x d; stock lengths are a default list of common metric and inch lengths unless the project gives its own.

## Limits

- `seat_tol_mm`: 0.05
- `gap_tol_mm`: 0.05
- `hole_clearance_mm`: 0.1
- `tip_clearance_mm`: 0.5
- `stack_tol_mm`: 0.05
- `length_tol_mm`: 0.05
- `min_engagement_d`: 0.8
- `look_ahead_mm`: 10.0
- `lines`: 8
- `service_access`: true
- `touch_mm`: 0.05
- `overlap_mm3`: 0.001
- `stock_lengths`: "default metric + inch list"

## Fasteners

| Fastener | Clamps → into | Seat | Thread start | Grip | Engagement | Min | Length | Fits | Thread depth needed | Tip clearance | Tool (step) | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hopper_screws#0 | hopper → hopper_inserts | Z 163.00 | Z 160.00 | 3.00 | 5.00 (10 thr) | 2.40 | 8.00 | 5.40–∞ | 5.00 | – | hex 2.5 (step 11) | pass |
| hopper_screws#1 | hopper → hopper_inserts | Z 163.00 | Z 160.00 | 3.00 | 5.00 (10 thr) | 2.40 | 8.00 | 5.40–∞ | 5.00 | – | hex 2.5 (step 11) | pass |
| hopper_screws#2 | hopper → hopper_inserts | Z 163.00 | Z 160.00 | 3.00 | 5.00 (10 thr) | 2.40 | 8.00 | 5.40–∞ | 5.00 | – | hex 2.5 (step 11) | pass |
| laser_foot_screws#0 | laser_mount → laser_inserts | Z 153.60 | Z 147.60 | 6.00 | 4.00 (8 thr) | 2.40 | 10.00 | 8.40–12.00 | 4.00 | 2.50 | hex 2.5 (step 17) | pass |
| laser_foot_screws#1 | laser_mount → laser_inserts | Z 153.60 | Z 147.60 | 6.00 | 4.00 (8 thr) | 2.40 | 10.00 | 8.40–12.00 | 4.00 | 2.50 | hex 2.5 (step 17) | pass |
