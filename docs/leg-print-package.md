# Leg print package (first leg)

What to buy, print, check and assemble for the first leg, after the pre-print review
([research/leg-preprint/](../research/leg-preprint/README.md)) and the D74 joint policy. The files come from
`cad/build_leg.py`. The CAD and FEA records below do not prove fit or strength. The coupons (C1-C4) and the
unpowered proof loads at the end of this page settle them, and nothing here replaces them.

No part has been bought and no powered test run for this page.

## 1. Buy first (nothing is ordered yet)

The leg's bought parts and their links are in [leg-rig-orders.md](leg-rig-orders.md) (regenerated from
`exports/leg/bom.json`). New or changed for the first print:

| Item | Qty a leg | Why | Status |
|---|---|---|---|
| DIN 433 M6 washer, 6.4 x 11 x 1.6, stainless (`washer_m6_din433`) | 4 | under the BotWheel screws' heads (D74) | McMaster-Carr part number to confirm: its product pages returned no data on 2026-11-01 |
| Structural epoxy for metal to nylon (two-part, gap-filling, about 0.1-0.25 mm) | 1 kit | the stop pins, the knee-eye sleeves and the RS-04 dowels (D74): Henkel does not recommend the anaerobic retainer (LOCTITE 638) on thermoplastics | the owner picks the product; C1 tries it |
| PA6-CF, two 1 kg spools of one lot | 3.1 kg in all | the hip frame alone is 1,106 g | dry before use (section 3) |
| TPU 95A | 62 g | the four stop sleeves | |

## 2. Print the coupons first

The four coupons and their measurement sheets are in
[research/leg-preprint/README.md](../research/leg-preprint/README.md#coupons) and
[research/leg-preprint/sheets/](../research/leg-preprint/sheets/). They take hours, not days, and each one changes a
number in the CAD:

- **C1, the bores.** It measures the printed-hole error that `PRINT_HOLE_COMP` assumes (0.125 mm on the diameter, the
  middle of an assumed -0.20 to -0.05 mm). Set the constant from it before printing the links.
- **C2, the insert.** It measures the M5 insert's pull-out against the hip-frame mount's preload.
- **C3, the clamp.** It measures how much preload creep takes from a clamped printed stack in 24 h. That sets the
  re-torque schedule.
- **C4, the boss root.** It loads a printed boss root across its layers. The layer check uses an interlayer
  shear strength that nobody has measured (S_z / sqrt(3)), and C4 measures it (section 7).

## 3. Drying and printer set-up

These come from the filament's data sheet, as in [rs04-fit-job.md](rs04-fit-job.md):

- Dry PA6-CF at 80 °C for 8-12 h.
- Feed it dry, below 20 % RH: from a dry box, for the whole print. The hip frame runs for three days.
- Use a hardened nozzle.
- Nozzle 260-290 °C, bed 80-100 °C with glue.

Record the filament lot, the drying, the nozzle, the slicer and its settings, and each part's mass after printing.

## 4. The parts

Each printed part is written as `exports/leg/<part>.step`, plus `.stl` and `.3mf` meshes in their print orientation on
z = 0. `exports/leg/print-plan.json` gives each part's hours and grams.

| Part | Qty | Face on the bed | Settings | Watch for |
|---|---|---|---|---|
| hip_frame | 1 | the web's outer (leg-side) face; turned 45° to fit the 256 mm bed | 100 % solid | 72 h and more than one spool: splice or change the spool at a layer change, from the same lot; brim. The stop-pin holes open on the bed: keep their 0.5 mm lead-ins clean |
| upper_link | 2 | the outer face (the head pockets open at the bed) | 100 % solid | the knee-eye sleeve holes open on the bed |
| front_link | 1 | the inner face | 100 % solid; **supports from the bed under the link's body** | it floats: only the apex ring (16 cm²) touches the bed, with 141 cm² of underside 32 mm up. Use tree supports from the build plate only, never in the bearing seats |
| wheel_link | 1 | the outer face | 100 % solid | the outer knee seat opens on the bed |
| apex_spacer | 1 | the inner face | 100 % solid | |
| stop_sleeve | 4 | cap down | TPU 95A, 100 % | |

## 5. After printing, before assembly

1. Weigh each part and compare it with the print plan. More than 5 % light means voids: do not use the part.
2. Measure every press-fit bore at its mouth and 5 mm in, on two diameters, as C1's sheet does:
   - the knee-eye sleeve holes, drawn Ø18.125;
   - the 6301 seats, Ø37.04;
   - the 61812 seats, Ø78.04;
   - the RS-04 dowel holes, Ø5.155;
   - the stop-pin holes, Ø16.1.

   Compare each with the band C1 measured.
3. Check that the hip frame's motor faces and the links' faces are flat (feeler gauge on a surface plate). Check the
   flange ends for warp.
4. Look for open layers at the boss roots, the flange roots and the apex ring. Those are the places the layer check
   names.

## 6. Assembly order and the D74 joints

Follow [leg-rig-assembly.md](leg-rig-assembly.md). The D74 joints change it here:

- **Stop pins, knee-eye sleeves and RS-04 dowels:** bond them with the structural epoxy, pressed or pushed to depth,
  and let it cure fully before you load them. The sleeve holes are drawn for about 0.05 mm of press at the printed
  band's middle; C1 says whether they come out loose or tight.
- **BotWheel:** 4 x M6 x 30, each on a DIN 433 washer, at 1.8 N m with threadlocker (it was 8 N m). The plastic
  under a bare head was at 150 MPa; under the washer it is at 25 MPa.
- **Re-torque** every clamped printed joint after 24 h and after the first humid week. C3 sets the schedule.
- The stop sleeves go on last, over the bonded pins.

## 7. Unpowered proof loads

Run these on the bench with the motors unpowered, before any powered rig test. Set-up:

- The leg is folded onto its stop posts (the R3 posture), so the stops, not the motors, react the load.
- The hip frame is bolted to the rig's carriage plate, with the carriage clamped.
- Load the wheel's axle with weights, or with the bench press and its load cell.
- A dial indicator reads at the axle.

| Step | Load at the axle | Hold | Pass |
|---|---|---|---|
| P1 | 460 N vertical (E1: 2.5 x the standing 184 N) | 10 min | it returns to within 0.05 mm of its start; no whitening, cracking or creaking |
| P2 | 945 N vertical (R1: the landing's quasi-static axle force) | 1 min | set after unloading under 0.1 mm; the same visual checks; the torque marks have not moved |
| P3 | 10 % of P2 sideways, at the tyre's mid-plane | 1 min | the same |

After P2, look closely with a lamp at:

- the upper links' knee-eye roots;
- the wheel link's knee boss root and hub root;
- the front link's apex ring;
- the hip frame's flange roots.

These are where the layer check below is short. Any crack there stops the build: the part goes to metal or is
redesigned.

The folded posture loads the stops, the links' bending and the frame, but it does not reproduce every R1 or E1 path
through the knees and the apex. The rig's powered tests (S1-S5 in [leg-bench-tests.md](leg-bench-tests.md)) cover
those, after this page.

## 8. The leg's studies after these changes

<!-- gen:final-record -->
<!-- /gen:final-record -->

## 9. Mass

<!-- gen:mass -->
<!-- /gen:mass -->

## 10. Owner decisions still open

<!-- gen:decisions -->
<!-- /gen:decisions -->
