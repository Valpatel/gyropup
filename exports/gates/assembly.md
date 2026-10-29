# Gate: assembly

**FAIL** · 226 checks: 220 pass, 0 warn, 6 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

| Check | Status | Parts | Message |
|---|---|---|---|
| `step:12:insert` | fail | ball#0, ball#1, ball#4, ball#7, ball#13, ball#15, ball#16, ball#17, ball#20, ball#22, ball#23, ball#24, ball#25, ball#26, ball#27, hopper | moving in along -Z: ball#0 meets hopper 27.90 mm before its seat (first contact near (-13.2, 12.7, 163.0)); ball#1 meets hopper 79.66 mm before its seat (first contact near (-27.8, 44.7, 225.0)); ball#4 meets hopper 80.04 mm before its seat (first contact near (-93.2, -19.1, 225.0)); ball#7 meets hopper 27.90 mm before its seat (first contact near (-13.2, -12.7, 163.0)); ball#13 overlaps hopper at its seat (0.032 mm³); ball#15 overlaps hopper at its seat (0.126 mm³); ball#16 overlaps hopper at its seat (0.244 mm³); ball#17 overlaps hopper at its seat (0.016 mm³); ball#20 overlaps hopper at its seat (0.011 mm³); ball#22 overlaps hopper at its seat (0.281 mm³); ball#23 overlaps hopper at its seat (0.005 mm³); ball#24 overlaps hopper at its seat (0.057 mm³); ball#25 overlaps hopper at its seat (0.660 mm³); ball#26 overlaps hopper at its seat (0.062 mm³); ball#27 overlaps hopper at its seat (0.506 mm³) |
| `step:29:insert` | fail | tilt_yoke, horn_boss, stop_lug | moving in along +Z: tilt_yoke meets horn_boss 30.00 mm before its seat (first contact near (-0.0, 63.3, 130.0)); tilt_yoke meets stop_lug 8.16 mm before its seat (first contact near (5.5, -58.6, 108.5)) |
| `step:31:insert` | fail | tilt_bearing, tilt_yoke | moving in along +Y: tilt_bearing meets tilt_yoke 8.00 mm before its seat (first contact near (-0.0, -68.8, 140.0)) |
| `step:32:insert` | fail | tilt_bearing_inner, tilt_yoke | moving in along +Y: tilt_bearing_inner meets tilt_yoke 8.00 mm before its seat (first contact near (0.0, -68.8, 140.0)) |
| `step:50:insert` | fail | slip_ring_rotor, pan_ring, pan_spacer, tilt_yoke, ring_driver, board_bay, pan_bearing, pan_bearing_inner, circlip_50, pan_clamp | moving in along +Z: slip_ring_rotor meets pan_ring 64.89 mm before its seat (first contact near (-0.0, -22.5, 27.9)); slip_ring_rotor meets pan_spacer 56.74 mm before its seat (first contact near (-0.0, -27.3, 36.0)); slip_ring_rotor meets tilt_yoke 23.75 mm before its seat (first contact near (0.0, -27.4, 69.0)); slip_ring_rotor meets ring_driver 29.75 mm before its seat (first contact near (0.0, -18.8, 63.0)); slip_ring_rotor meets board_bay 21.75 mm before its seat (first contact near (0.0, -70.3, 71.0)); slip_ring_rotor meets pan_bearing 52.74 mm before its seat (first contact near (-0.0, -31.7, 40.0)); slip_ring_rotor meets pan_bearing_inner 52.74 mm before its seat (first contact near (-0.0, -25.7, 40.0)); slip_ring_rotor meets circlip_50 58.74 mm before its seat (first contact near (-0.0, -26.0, 34.0)); slip_ring_rotor meets pan_clamp 45.74 mm before its seat (first contact near (-0.0, -33.7, 47.0)) |
| `step:53:insert` | fail | pan_base, base_board | moving in along +Z: pan_base meets base_board 41.00 mm before its seat (first contact near (41.8, -0.0, 6.0)) |

## Exclusions (declared)

- flywheel, flywheel_motor_l: each hub's bore on its X2216's prop adapter: a 0.008 mm^3 modelling overlap where the envelopes meet (a slip fit)
- flywheel_m, flywheel_motor_r: each hub's bore on its X2216's prop adapter: a 0.008 mm^3 modelling overlap where the envelopes meet (a slip fit)
- ball#0, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#0, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#1, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#1, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#2, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#2, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#3, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#3, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#4, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#4, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#5, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#5, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#6, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#6, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#7, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#7, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#8, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#8, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#9, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#9, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#10, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#10, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#11, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#11, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#12, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#12, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#13, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#13, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#14, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#14, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#15, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#15, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#16, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#16, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#17, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#17, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#18, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#18, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#19, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#19, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#20, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#20, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#21, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#21, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#22, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#22, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#23, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#23, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#24, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#24, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#25, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#25, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#26, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#26, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#27, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#27, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#28, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#28, dial: the settle's soft contacts with the dial's cone, fins and pockets
- ball#29, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball#29, dial: the settle's soft contacts with the dial's cone, fins and pockets
- laser_screws, laser_mount: the set screws in the ring's tapped holes: the thread envelope (Ø3 in the Ø2.5 tap drill)
- esc_l, cartridge_body: the ESC envelope drawn 0.01 mm into the cage plate: 3.4 mm^3
- esc_r, cartridge_body: the ESC envelope drawn 0.01 mm into the cage plate: 3.4 mm^3
- ct_thumbscrew, cradle: the captive thumbscrew's collar in the rail: 0.34 mm^3
- ring_driver, pan_ring: the driver's three crush ribs in the turntable's bore: 2 mm^3
- circlip_50, pan_ring: the circlip drawn at its groove's d2: 0.05 mm^3
- slip_ring_rotor, ring_coupling: the tube stretched over the rotor stub: 0.10 mm^3
- slip_ring, slip_ring_rotor: one bought slip ring drawn as two solids: the rotor stub drawn 0.01 mm into the stator's end face (0.28 mm^3)
- bumper_ring, pan_base: the bumper's lug on a base tab: 0.04 mm^3 (curved faces)
- panel_switch, stand_box: the rocker's 24 mm square envelope through its Ø20.2 round cut-out: the envelope, not the part
- panel_pendant, stand_box: the TB3M socket's square envelope through its round cut-out: the envelope, not the part
- dt_plug, dt_receptacle: the mated DT connector: the plug's shell drawn over the receptacle's insert

## Assumptions

- Each part goes in along a straight line in its step's declared direction, from beyond every part present to its modelled position: no rotation, tilt or wiggle, and no room for hands or fixtures is checked.
- An insertion is checked against the parts fitted and the fasteners installed at earlier steps (the fastener gate's install_step); parts no step fits are not obstacles (the cover check fails them). A tool sweep is checked against the fastener gate's present_at (parts no step fits count as present). Instances fitted at one step are not checked against each other.
- Conservative advancement: the part steps by its gap to each obstacle (box distance or exact), which cannot skip a contact, and by max_step_mm only within that distance of it; a feature thinner than that step can pass another between two samples there.
- Exact B-rep relations within the relation tolerances (overlap_mm3 of shared volume blocks; touching and sliding along a face are allowed); no tolerance stack, print shrink or flex, so a clear path in the model does not prove the printed parts go together.
- Tool access is the fastener gate's straight sweep of the declared envelope along the screw axis, against the parts present when the screw is driven.

## Limits

- `max_step_mm`: 2.0
- `margin_mm`: 1.0
- `refine_steps`: 12
- `max_samples`: 5000
- `tool_access`: true
- `missing_direction`: "warn"
- `touch_mm`: 0.05
- `overlap_mm3`: 0.001
- `service`: false

## Assembly sequence

| Step | Fit | Onto | Direction | Present | Clearance (mm) | Touching | Fasteners | Tool | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | cartridge_body | - | -Z | 0 | - | - | - | - | pass |
| 2 | feed_motor | cartridge_body | +Z | 1 | - | cartridge_body | - | - | pass |
| 3 | flywheel_motor_l | cartridge_body | +Z | 2 | ≥ 49.04 | cartridge_body | - | - | pass |
| 4 | flywheel_motor_r | cartridge_body | +Z | 3 | ≥ 23.92 | cartridge_body | - | - | pass |
| 5 | flywheel | flywheel_motor_l | +Z | 4 | 1.81..3.52 | - | - | - | pass |
| 6 | flywheel_tyre | flywheel | +Z | 5 | 0.00..0.75 | flywheel | - | - | pass |
| 7 | flywheel_m | flywheel_motor_r | +Z | 6 | 1.81..3.52 | - | - | - | pass |
| 8 | flywheel_tyre_m | flywheel_m | +Z | 7 | 0.00..0.75 | flywheel_m | - | - | pass |
| 9 | dial | feed_motor | -Z | 8 | 0.00..0.71 | feed_motor | - | - | pass |
| 10 | hopper_inserts | cartridge_body | -Z | 9 | 2.87..4.78 | cartridge_body | - | - | pass |
| 11 | hopper | cartridge_body | -Z | 10 | 0.64..0.70 | cartridge_body, hopper_inserts | hopper_screws | hex 2.5 (hopper_screws#0: pass, hopper_screws#1: pass, hopper_screws#2: pass) | pass |
| 12 | ball | dial | -Z | 14 | 0.00..0.09 | - | - | - | fail |
| 13 | hopper_lid | hopper | -Z | 44 | 0.94..1.15 | hopper | - | - | pass |
| 14 | hopper_flap | hopper_lid | -Z | 45 | 0.00..0.36 | - | - | - | pass |
| 15 | barrel | cartridge_body | -X | 46 | ≥ 6.00 | cartridge_body | - | - | pass |
| 16 | laser_inserts | cartridge_body | -Z | 47 | ≥ 1.90 | cartridge_body | - | - | pass |
| 17 | laser_mount | cartridge_body | -Z | 48 | ≥ 5.50 | cartridge_body, laser_inserts | laser_foot_screws | hex 2.5 (laser_foot_screws#0: pass, laser_foot_screws#1: pass) | pass |
| 18 | laser_screws | laser_mount | -Z | 51 | ≥ 8.45 | - | - | - | pass |
| 19 | laser | laser_mount | -X | 52 | 1.00..2.00 | laser_screws | - | - | pass |
| 20 | esc_l | cartridge_body | -Z | 53 | ≥ 0.99 | - | - | - | pass |
| 21 | esc_r | cartridge_body | -Z | 54 | ≥ 0.99 | - | - | - | pass |
| 22 | cartridge_board | cartridge_body | -Z | 55 | ≥ 2.90 | cartridge_body | - | - | pass |
| 23 | cradle | cartridge_body | +Z | 56 | 2.00..10.51 | cartridge_body | - | - | pass |
| 24 | ct_thumbscrew | cradle | +Z | 57 | ≥ 3.99 | - | - | - | pass |
| 25 | cradle_plate_l | cradle | -Y | 58 | ≥ 2.01 | cradle | - | - | pass |
| 26 | horn_boss | cradle_plate_l | -Y | 59 | ≥ 5.18 | cradle_plate_l | - | - | pass |
| 27 | cradle_plate_r | cradle | +Y | 60 | ≥ 2.01 | cradle | - | - | pass |
| 28 | stop_lug | cradle_plate_r | +Y | 61 | 3.17 | cradle_plate_r | - | - | pass |
| 29 | tilt_yoke | cradle | +Z | 62 | 0.03..1.02 | - | - | - | fail |
| 30 | tilt_servo | tilt_yoke | -Y | 63 | ≥ 9.00 | horn_boss, tilt_yoke | - | - | pass |
| 31 | tilt_bearing | tilt_yoke | +Y | 64 | ≥ 3.64 | - | - | - | fail |
| 32 | tilt_bearing_inner | tilt_bearing | +Y | 65 | 0.00..0.10 | - | - | - | fail |
| 33 | pivot_spacer | cradle_plate_r | -Z | 66 | ≥ 0.33 | cradle_plate_r, tilt_bearing, tilt_bearing_inner, tilt_yoke | - | - | pass |
| 34 | shoulder_screw | cradle_plate_r | +Y | 67 | 0.00..0.25 | cradle_plate_r, pivot_spacer, tilt_bearing_inner | - | - | pass |
| 35 | board_bay | tilt_yoke | +Y | 68 | ≥ 7.00 | tilt_yoke | - | - | pass |
| 36 | turret_board | board_bay | +Y | 69 | ≥ 8.00 | board_bay | - | - | pass |
| 37 | board_bay_lid | board_bay | +Y | 70 | ≥ 0.39 | board_bay | - | - | pass |
| 38 | pan_ring | tilt_yoke | +Z | 71 | ≥ 19.75 | tilt_yoke | - | - | pass |
| 39 | ring_driver | pan_ring | +Z | 72 | ≥ 26.85 | tilt_yoke | - | - | pass |
| 40 | ring_coupling | ring_driver | +Z | 73 | 7.82..15.63 | ring_driver | - | - | pass |
| 41 | hall_switch | pan_ring | +Z | 74 | ≥ 13.25 | pan_ring | - | - | pass |
| 42 | pan_bearing_inner | pan_ring | +Z | 75 | 8.00..20.63 | pan_ring | - | - | pass |
| 43 | pan_clamp | pan_ring | +Z | 76 | 1.25..2.50 | - | - | - | pass |
| 44 | pan_bearing | pan_bearing_inner | +Z | 77 | 0.00..0.10 | pan_clamp | - | - | pass |
| 45 | index_magnet | pan_clamp | +Z | 78 | 0.12..2.82 | pan_clamp | - | - | pass |
| 46 | pan_spacer | pan_bearing_inner | +Z | 79 | 0.00..0.15 | pan_bearing_inner | - | - | pass |
| 47 | circlip_50 | pan_ring | +Z | 80 | ≥ 0.20 | pan_spacer | - | - | pass |
| 48 | pan_pinion | pan_ring | +Z | 81 | 0.00..0.20 | - | - | - | pass |
| 49 | pan_servo | pan_pinion | +Z | 82 | 1.82..2.41 | pan_pinion | - | - | pass |
| 50 | slip_ring_rotor | ring_coupling | +Z | 83 | ≥ 5.00 | - | - | - | fail |
| 51 | slip_ring | slip_ring_rotor | +Z | 84 | 0.10..9.00 | - | - | - | pass |
| 52 | base_board | pan_bearing | +Z | 85 | 5.59..11.40 | - | - | - | pass |
| 53 | pan_base | pan_bearing | +Z | 86 | 0.00..0.60 | index_magnet, pan_bearing, pan_clamp, pan_servo | - | - | fail |
| 54 | ring_carrier | pan_base | +Z | 87 | ≥ 4.15 | pan_base, slip_ring | - | - | pass |
| 55 | bumper_ring | pan_base | +Z | 88 | 3.07..6.13 | - | - | - | pass |
| 56 | dt_receptacle | pan_base | +Y | 89 | 1.72..3.44 | pan_base | - | - | pass |
| 57 | compute_shell | pan_base | +Z | 90 | 1.22..8.16 | pan_base | - | - | pass |
| 58 | compute | compute_shell | +Z | 91 | ≥ 9.30 | compute_shell | - | - | pass |
| 59 | input_fuses | compute_shell | +Z | 92 | 2.50..11.42 | - | - | - | pass |
| 60 | eth_jack | compute_shell | +X | 93 | ≥ 2.00 | compute_shell | - | - | pass |
| 61 | xt30_input | compute_shell | +X | 94 | ≥ 7.00 | compute_shell | - | - | pass |
| 62 | compute_tray | compute_shell | +Z | 95 | ≥ 17.10 | compute, compute_shell, input_fuses | - | - | pass |
| 63 | stand_box | compute_tray | +Z | 96 | ≥ 10.00 | compute_tray | - | - | pass |
| 64 | dock | stand_box | +Z | 97 | ≥ 6.00 | stand_box | - | - | pass |
| 65 | terminal_board | stand_box | +Z | 98 | ≥ 66.53 | stand_box | - | - | pass |
| 66 | usb_can | stand_box | +Z | 99 | ≥ 105.64 | stand_box | - | - | pass |
| 67 | panel_switch | stand_box | -X | 100 | ≥ 28.00 | - | - | - | pass |
| 68 | panel_pendant | stand_box | -X | 101 | ≥ 33.75 | - | - | - | pass |
| 69 | stand_bottom | stand_box | +Z | 102 | ≥ 21.00 | stand_box, usb_can | - | - | pass |
| 70 | stand_foot | stand_bottom | +Z | 103 | ≥ 3.00 | stand_bottom | - | - | pass |
| 71 | pack | stand_bottom | +X | 107 | 1.00..2.00 | dock, stand_bottom | - | - | pass |
| 72 | dt_plug | dt_receptacle | +Y | 108 | 0.08..9.00 | - | - | - | pass |

Blocked:

- step 12: ball#0 meets hopper 27.90 mm before its seat
- step 12: ball#1 meets hopper 79.66 mm before its seat
- step 12: ball#4 meets hopper 80.04 mm before its seat
- step 12: ball#7 meets hopper 27.90 mm before its seat
- step 12: ball#13: seat against hopper
- step 12: ball#15: seat against hopper
- step 12: ball#16: seat against hopper
- step 12: ball#17: seat against hopper
- step 12: ball#20: seat against hopper
- step 12: ball#22: seat against hopper
- step 12: ball#23: seat against hopper
- step 12: ball#24: seat against hopper
- step 12: ball#25: seat against hopper
- step 12: ball#26: seat against hopper
- step 12: ball#27: seat against hopper
- step 29: tilt_yoke meets horn_boss 30.00 mm before its seat
- step 29: tilt_yoke meets stop_lug 8.16 mm before its seat
- step 31: tilt_bearing meets tilt_yoke 8.00 mm before its seat
- step 32: tilt_bearing_inner meets tilt_yoke 8.00 mm before its seat
- step 50: slip_ring_rotor meets pan_ring 64.89 mm before its seat
- step 50: slip_ring_rotor meets pan_spacer 56.74 mm before its seat
- step 50: slip_ring_rotor meets tilt_yoke 23.75 mm before its seat
- step 50: slip_ring_rotor meets ring_driver 29.75 mm before its seat
- step 50: slip_ring_rotor meets board_bay 21.75 mm before its seat
- step 50: slip_ring_rotor meets pan_bearing 52.74 mm before its seat
- step 50: slip_ring_rotor meets pan_bearing_inner 52.74 mm before its seat
- step 50: slip_ring_rotor meets circlip_50 58.74 mm before its seat
- step 50: slip_ring_rotor meets pan_clamp 45.74 mm before its seat
- step 53: pan_base meets base_board 41.00 mm before its seat
