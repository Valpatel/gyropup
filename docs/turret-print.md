# Printing the bench turret (v0)

From `cad/turret_print.py`: every printed part of the bench turret and its stand as a 3MF in the orientation it prints in (`exports/turret/print/<part>.3mf`, one part centred on the bed), sliced by Bambu Studio for a P1S with these settings, so the grams and hours are the slicer's own. Open a 3MF in Bambu Studio, pick the printer, the filament and the settings in the table, and slice. The strength checks (cad/turret_studies.py) assume these settings: PA6-CF solid except the pan base, PETG with 2 mm walls (5 loops) and 40 % gyroid.

**Before printing:** the P1S needs its 0.4 mm hardened-steel nozzle for PA6-CF (it is abrasive), and the PA6-CF must be dried (Bambu: 80 °C for 8 h); print it on the textured PEI plate with the glue stick. Heat-set inserts go in while the part is still warm where you can. Measure the fits of bench test 1.1 as parts come off (docs/turret-bench-tests.md).

| Part | Material (Bambu profile) | Copies | On the bed | Settings | g each | h each | Note |
|---|---|---|---|---|---|---|---|
| [stand_box](../exports/turret/print/stand_box.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | upside down, on its top plate | 3 walls, 20% gyroid, tree supports | 377.64 | 8.4 | the stand first: it needs no decision |
| [stand_bottom](../exports/turret/print/stand_bottom.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | flat | 3 walls, 20% gyroid | 103.86 | 2.5 |  |
| [pan_base](../exports/turret/print/pan_base.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its foot | 4 walls, 40% gyroid, tree supports | 133.44 | 6.4 | 40 % gyroid inside 4 perimeters (the FEA case) |
| [pan_ring](../exports/turret/print/pan_ring.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | upside down: the gear teeth flat on the bed | 4 walls, 100% zig-zag, tree supports | 78.21 | 3.8 |  |
| [pan_spacer](../exports/turret/print/pan_spacer.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its wide end | 4 walls, 100% zig-zag | 2.62 | 0.1 |  |
| [pan_pinion](../exports/turret/print/pan_pinion.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | flat | 4 walls, 100% zig-zag | 7.88 | 0.6 |  |
| [ring_carrier](../exports/turret/print/ring_carrier.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its top face | 4 walls, 100% zig-zag | 29.33 | 1.2 | reprint once the ring's flange holes are measured (plan T6) |
| [ring_driver](../exports/turret/print/ring_driver.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its top face | 4 walls, 100% zig-zag | 6.83 | 0.3 |  |
| [tilt_yoke](../exports/turret/print/tilt_yoke.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its back: the layers run along the arms | 4 walls, 100% zig-zag, tree supports | 104.15 | 4.8 |  |
| [cradle](../exports/turret/print/cradle.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | flat | 4 walls, 100% zig-zag, tree supports | 76.56 | 3.5 |  |
| [cartridge_body](../exports/turret/print/cartridge_body.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 1 | on its base; supports under the floor, the chute and the cage plate | 4 walls, 100% zig-zag, tree supports | 187.58 | 10.7 | the longest print: after the motor and a servo are checked against the drawings (plan T2, T4) |
| [flywheel](../exports/turret/print/flywheel.3mf) | pa6-cf (Bambu PA6-CF @BBL X1C) | 2 | on its top face (the flange seat flat on the bed) | 4 walls, 100% zig-zag | 5.19 | 0.2 | ream the bore to 5.00 |
| [dial](../exports/turret/print/dial.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | on its bottom, cone up | 5 walls, 40% gyroid, tree supports | 45.54 | 1.7 |  |
| [hopper](../exports/turret/print/hopper.3mf) | petg-clear (Bambu PETG Translucent @BBL X1C) | 1 | upright, on its bottom rim and the baffle | 5 walls, 40% gyroid | 41.0 | 1.7 | translucent PETG so the balls show |
| [hopper_lid](../exports/turret/print/hopper_lid.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | upside down | 5 walls, 40% gyroid | 16.09 | 0.5 | the fill flap is not fitted on the bench |
| [barrel](../exports/turret/print/barrel.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | standing on its socket end | 5 walls, 40% gyroid, tree supports | 30.54 | 1.5 | change to blaze orange for the last 15 mm (a filament change at that layer) |
| [laser_mount](../exports/turret/print/laser_mount.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | on its foot | 5 walls, 40% gyroid | 6.19 | 0.4 |  |
| [board_bay](../exports/turret/print/board_bay.3mf) | petg (Bambu PETG HF @BBL P1S 0.4 nozzle) | 1 | on its back | 5 walls, 40% gyroid | 24.36 | 0.9 |  |
| [flywheel_tyre](../exports/turret/print/flywheel_tyre.3mf) | tpu95 (Bambu TPU 95A @BBL X1C) | 2 | flat | 3 walls, 100% zig-zag | 4.43 | 0.3 | Ø34 mounted (printed 4 % under the Ø28 rim): the only tyre for the X2216 (D42) |

**Totals:** 1291.1 g of filament, 50.1 h on one printer: pa6-cf 637.0 g / 31.8 h, petg 604.2 g / 16.0 h, petg-clear 41.0 g / 1.7 h, tpu95 8.9 g / 0.6 h.

## The schedule

- **Day 1**: stand_box (8.4 h), stand_bottom (2.5 h) — 10.9 h
- **Day 1-2: the pan stack (PA6-CF)**: pan_base (6.4 h), pan_ring (3.8 h), pan_spacer (0.1 h), pan_pinion (0.6 h), ring_carrier (1.2 h), ring_driver (0.3 h) — 12.4 h
- **Day 2-3: the tilt group (PA6-CF, PETG)**: tilt_yoke (4.8 h), cradle (3.5 h), board_bay (0.9 h), laser_mount (0.4 h) — 9.6 h
- **Once the X2216 and a servo are in hand: the cartridge**: cartridge_body (10.7 h), flywheel (0.4 h), dial (1.7 h), hopper (1.7 h), hopper_lid (0.5 h), barrel (1.5 h) — 16.5 h
- **Last**: flywheel_tyre (0.6 h) — 0.6 h

With one P1S that is about 2.5 days at 20 printing hours a day; the stand can go on a second printer. The cartridge, hubs, dial and hopper wait for the X2216 and a servo (their sizes are checked against the drawings first).

## Not printed for the bench

- `bumper_ring`: v1 (the robot): no bumper on the bench
- `hopper_flap`: v1: the dock's fill flap
- `pan_clamp`: cut by SendCutSend in 6061-T6 aluminium (exports/turret/pan_clamp.dxf)
