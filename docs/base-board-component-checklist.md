# Carrier component checklist

Audit date: 2026-10-29. Mechanical source snapshot: `faed5f510586ab282db4a27f6453165ac56f70d2`, PR #67 / issue #66.

Scope remains the passive pan-base opening and removable electronics carrier. No launcher, motor, rail, torque, or other turret/leg redesign. The missing-cache correction at this snapshot passed independent recheck, including the original reproduction and eight empty/partial-cache cases; its specific PR thread is resolved. This does not qualify numerical volumes, hardware fit or service. No new complete CAD run was started for this audit. Subsequent implementation must regenerate evidence from its own source head.

### Exact mounting inventory and placements

Coordinates are millimetres in turret frame T, not measured fit. Instance order is `(negative y, z9)`, `(negative y, z33)`, `(positive y, z9)`, `(positive y, z33)`.

| Component | Quantity / placement | Evidence and remaining gap |
|---|---|---|
| PA6-CF carrier | 1; plate x53..56, y±35, z5.5..37.5; four inward bosses x48..53, radius3.5 | `cad/turret_base_board.py:48–56`; public STEP exists, but current print receipt is historical; physical clearance and insert coupons absent. |
| PCB | 1; x46.4..48, y±25.4, z6..36; holes y±22.4, z9/33 | `cad/turret_base_board.py:59–63`; CAD uses Ø3.4, while `docs/turret-wiring.md:570–571` says drill Ø3.2. Resolve deliberately before a drawing/print release. Perfboard purchase identity also conflicts between wiring notes and catalog. |
| PCB screws | 4 × McMaster 91290A111 M3×6; head bearing faces `(46.4, ±22.4, 9/33)`, shaft direction +X | `cad/turret_base_board.py:108–113`; private STEP cached. Public model is authored simplified hardware. Four existing screws transfer to the carrier; not four extra purchases. |
| Carrier retainers | 4 × McMaster 91290A113 M3×8; head bearing faces `(56, ±31, 9/33)`, shaft direction −X | Same source; four additional screws. Private normalized STEP is absent; supplier stock and CAD-download access are distinct questions. No substitution selected. |
| Board inserts | 4 × McMaster 94459A140; mouths `(48, ±22.4, 9/33)`, bodies extend +X | `cad/turret_base_board.py:130–132`; existing four transfer to carrier. Nominal total model length 5.74; recorded useful thread 5.53 with 0.105 lead-in. Heat-setting tool and actual fit not yet checked. |
| Base-anchor inserts | 4 × 94459A140; mouths `(53, ±31, 9/33)`, bodies extend −X into anchor rails x45..53 | `cad/turret_base_board.py:32–45,130–132`; four additional inserts. Ø4 pilot bores x46.5..53.1; coupon, insertion tool and renewed anchor/base strength evidence absent. |

Total carrier mounting hardware is **8 screws + 8 inserts**, three SKUs. Historical useful engagement calculations are 4.295 mm for PCB screws and 4.895 mm for carrier retainers, against the declared 3 mm minimum; these are not new measured or complete manufacturer qualification results.

Protected regions remain foot z≤5; central tube radius≤35.5, z≤38; bearing seat x±43/y±50/z38..60; servo pocket x−85..−25/y−50..60/z0..65 (`docs/base-board-service.md:11`). The recorded symmetric-difference checks are historical and must be regenerated from the eventual final candidate.

### Required assembly and service order

1. Verify the board stock/cut size, hole diameter, screw/insert dimensions and measured printer coupons. Install four inserts in the carrier and four in the base using a specified heat-setting tip and accessible axial route. **Heat-setting access is not covered by the current screw-driver test.**
2. On the bench, assemble the PCB/component assembly to the carrier with the four M3×6 screws. Components face −X. Complete soldering and strain relief while both board faces are accessible; backside solder/jumper volume in the x48..53 gap is currently unmodelled.
3. Remove the TPU bumper and its retainers before module insertion or external carrier-driver access. The bumper uses five existing M3×20 screws, five washers and five short inserts (`cad/build_turret.py:127`); the current carrier checker assumes the bumper has already been removed and does not prove its teardown/tool route.
4. Connect or disconnect the module harness at an accessible service position determined from actual connector bodies and latch/finger envelopes. **This position and the C2 disconnect architecture are not yet defined.** No complete installation/removal claim is possible until this is resolved.
5. Insert the rigid carrier/PCB/attached PCB screws/inserts along −X; then fit the four external M3×8 retainers from +X; refit the bumper. The released generic rigid-module API is available in cad-agent v0.4.1, but this product has not integrated it yet.
6. For removal: isolate power under the existing project procedure; remove bumper; remove four external retainers; release strain relief and unplug at the verified service position; withdraw the complete PCB/carrier along +X; only then undo the inward-facing PCB screws on the bench.

The current checker moves the module against only the base, pan ring, pan clamp and pan pinion. Its historical base route travel is 42.8772 mm, derived per obstacle by the sweep; it **does not explicitly prove a 60 mm service stroke**. The retained-bumper negative is blocked over its 50.1 mm query. A proposed service stroke must be declared and checked with the real harness/connector configuration. Pan servo, stator connector/leads, fuse holder, DT rear tails and strain-relief features are not all present in that route obstacle set.

Driver envelope currently assumed: Ø6×60mm shaft plus Ø25 × 80 mm handle, straight axial approach, no hand/finger or ratchet swing envelope (`cad/check_base_board_service.py:27`). PCB drive approach is from−X on the bench; external-retainer drive approach is from+X with the bumper removed. Match an actual tool or record this as a conservative design envelope; do not call it verified user access yet.

### Electronics and harness completeness

| Interface / group | Existing source contract | Missing hard evidence / next action |
|---|---|---|
| Board components | One each U1 NE555P; U2 D36V50F12; F1 MF-R300; R1/R2/R3; C1/C2/C3; D1, from `cad/turret_boards.py:128–142` | Seven footprint/group envelopes are present; actual solder tails, leads, component retention and connector housings are absent. Model the selected physical items without shrinking their extents. |
| Board backside | PCB rear x48, carrier front x53 (nominal5mm gap away from bosses) | No solder joints, jumper wire, insulation, or strain-relief relief pockets are represented. A bare 5 mm gap is not evidence that the wired board fits. |
| C2 incoming bundle | 2 power + 4 signal conductors; 18/24 AWG; 120 mm route estimate around housing; tie at 60 mm (`docs/turret-wiring.md:239`) | No accessible detachable joint has been selected for the carrier end; no actual route, bundle diameter, latch access or pullout loop. Cannot treat fixed soldered wires as a removable connector. |
| C2 protection parts | One each MF-R010,1N5408,P6KE51A in adjacent harness;10A MINI58V fuse and holder | Heat-shrink/bend/retention envelopes absent. Catalog holder0FHM0001ZXJ says 32 VDC while wiring describes a 30–42 V bus; primary-source verification assigned to supplier audit, no silent substitution. |
| C3 stator plug | One43020-1200 board plug +12 × 43031-0001 male contacts on12 × 24 AWG, 60 mm tails; mates one 43025-1200 +12 × 43030-0010 on ring's28AWG leads (`docs/turret-wiring.md:177–183,240`) | Housings, mating stroke, latch pressure/finger space, wire exit and retained-loop routes absent from CAD. Need full mated/unmated envelopes and observable release action. Rotor-side duplicates are outside this carrier inventory. |
| Pan servo connection | Existing STS3215 own3-pin lead (`docs/turret-wiring.md:224`) | Exact mating connector, lead outside diameter, exit direction, disconnect access and service allowance unverified; not a newly selected CAN servo. |
| DT12 interface | DT04-12PA-L012, W12P, catalog pin0460-202-16141; only signals5–8 active under current wiring | Catalog pin describes 14–16 AWG; the supplier audit reports [TE primary documentation](https://www.te.com/en/product-0460-202-16141.html) specifies 16–20 AWG, still incompatible with the planned 24 AWG signals. Reconcile the selected contact and unused-cavity policy before harness release; no alternate is selected here. DT outer envelope does not prove rear-tail/crimp access. |
| Wire bend radius | Catalog24AWG UL1007 OD1.4mm;18AWG PTFE OD1.75mm | No source-backed minimum static/service bend radius is defined for these installed bundles. Obtain wire/connector limits; reserve geometry using that radius and measured assembly, not an invented universal multiplier. |
| Slack and strain relief | Wiring notes say cut 20% long then trim; C2 tie at 60 mm, C3 tie atboard (`docs/turret-wiring.md:231–240`) | 20% cutting allowance is not service slack. Define anchor points, retained slack, release stroke, connector unmating displacement and clearance at every intermediate position. Test removal with each intended tie still in place and with all required release steps explicit. |

### Acceptance blockers and adversarial checks

- [x] Independent review confirms missing/partial manufacturer caches fail closed at the exact source head (`faed5f5`; [review](https://github.com/Valpatel/gyropup/pull/67#pullrequestreview-5695909038)). No empty-cache fallback can turn a geometry qualification green.
- [ ] Obtain and validate actual 91290A113 private STEP; pin all three model hashes. Availability checks do not replace CAD coverage.
- [ ] Integrate the reviewed generic rigid-module API, retaining exact instance identities and ordinary bench sequence; do not fuse away attached-fastener identities or use broad collision waivers.
- [ ] Resolve adaptive-volume qualification through the separate toolkit work, then run exact-head evidence. No tolerance changes or rewrite of historical red receipts.
- [ ] Include all installed neighboring hardware/electrical envelopes in seated/insertion/removal/tool checks. Keep originals, retained bumper, attached external screws, wrong direction, missing holes, wrong screw lengths, too-short lead, blocked latch and unremoved tie as intentional failing variants.
- [ ] Prove insertion and removal independently with actual service prerequisites, explicit stroke, connector release access and no trapped module. A declared prerequisite is not teardown evidence.
- [ ] Specify and check heat-setting tip access, backing wall, PCB solder-side clearance, fastener stack and thread engagement against real hardware.
- [ ] Reconcile board/pilot/drill dimensions, print orientation/material and measurable fit-coupon acceptance; physical board/insert/PCB-hole checks remain unperformed.
- [ ] Renew affected pan-base structural qualification after the opening/anchor change. Preserved bearing surfaces alone do not establish unchanged load paths.
- [ ] Regenerate source-bound public project-authored exports after all above implementation changes, independently inspect them, and keep release_ready/physical_fit_verified false until their separate real-world evidence exists.

Procurement audit is delegated separately; it has the exact three-SKU hardware subset, board/discrete keys, local connector quantities and wire scope. It will preserve selected parts and report conflicts/candidates separately. No other turret/leg redesign is authorized by this checkpoint.
