# Turret carrier purchasing audit — 2026-10-29

**In progress. This is a purchasing-evidence audit, not a build release.** Scope is the removable base-board carrier in PR #67 at `faed5f510586ab282db4a27f6453165ac56f70d2`, based on integration `154d4de`. It excludes the rotor, cartridge, whole robot, purchases, substitutions and geometry changes. Tracking: #79, mechanical program #61.

## Scope and source

The carrier author identified four McMaster 91290A111 M3×6 PCB screws, four 91290A113 M3×8 external retainers, eight 94459A140 M3 inserts, one PA6-CF carrier, the ten base-board circuit parts, three adjacent protection parts, the head-branch fuse and holder, one stator-side Micro-Fit mating pair and its 24 contacts, the base DT12 receptacle/wedge/pins, substrate, and C2/C3 wire. Quantities come from `cad/turret_base_board.py`, `cad/turret_boards.py:128`, and `docs/turret-wiring.md:77,239,269,563` at the carrier source above. The full turret BOM is not a standalone carrier BOM.

Evidence will be recorded per exact manufacturer part number with supplier URL, observation date, pack/order unit, current stock indication and lead-time limits. Current stock is a page observation, not a reserved delivery promise. Missing CAD or an access/login gate is not evidence of unavailable stock. Licensed vendor models stay private.

## Confirmed design discrepancies requiring resolution

- **Head-branch holder voltage:** `docs/turret-wiring.md:139` selects 0FHM0001ZXJ upstream of D8/D14 and the regulator. Lines 457–458 explicitly place this on the robot's 30–42 V BUS. [Newark's exact SKU](https://www.newark.com/littelfuse/0fhm0001zxj/fuse-holder-in-line/dp/56P4440) specifies 32 VDC/20 A; it showed 779 units, minimum/multiple one, $9.71 each and 23-week manufacturer lead time on this date. The [Littelfuse FHM datasheet, revision 062923-B, p1](https://www.mouser.com/datasheet/2/240/Littelfuse_Fuse_Holder_MINI_FHM_Datasheet-3313789.pdf) gives the family maximum as 32 VDC. Its table does not list the unsuffixed ZXJ; the [manufacturer's family page](https://info.littelfuse.com/mini-fhm-series-landing-page) explicitly includes that exact part. This is a confirmed rating mismatch for the 42 V robot configuration; it does not establish a voltage mismatch for the separate 15–20.5 V stand. A 58 V fuse does not increase the holder rating.
- **DT12 contact conductor range:** [TE 0460-202-16141](https://www.te.com/en/product-0460-202-16141.html) specifies 16–20 AWG. The wiring at lines 77–87 and 269 assigns this contact to 24 AWG CAN pins 5–6 and safety-loop pins 7–8. No intermediate splice/adapter is documented in the scoped wiring. The catalog's 14–16 AWG description is also wrong. The documented direct crimp is outside the manufacturer's wire range; the electrical owner must resolve it before termination.
- **Substrate identity and order unit:** the carrier's modeled board is 50.8×30 mm. Its catalog key `proto-board-52x50` describes generic 50×70 mm material but links [SparkFun PRT-08619](https://www.sparkfun.com/protoboard-wombat-pth.html), an 80×100 mm Wombat PTH board. Catalog `pack_qty: 2` is a fabrication-yield assumption, not two boards in the seller's pack. The actual cut outline, mounting holes and solder layout still need validation.

## Remaining audit work

- [ ] Complete exact-part supplier observations for all scoped rows.
- [ ] Separate catalog history, live stock, unknown stock, fabrication yield and retail pack sizes.
- [ ] Check harness conductor ranges, supply ratings and documented wire lengths; record unresolved disconnect/slack and unused-pin sealing policy.
- [ ] Reconcile coverage against the frozen carrier inputs without changing the live catalog or geometry.
- [ ] Obtain independent review before integration.
