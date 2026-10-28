# Body next plan (milestone M5, stages P2-P4): after the power skid and the open frame

Written 2026-10-27 by the body planner (Fable 5.1) for the user and for the Opus implementer who will work it.
Sources read, all on main 0e1b0ec: docs/body-plan.md (the plan P0/P1 were built from; its part list is stale),
docs/body-frame.md, docs/body-electrical.md, docs/body-safety.md, docs/body-orders.md, cad/body_*.py, cad/build_body.py,
cad/test_body.py, exports/body/{body,bom,mass,leg-loads,wiring,print-plan}.json, exports/body/fea/summary.json,
exports/body/sendcutsend/, catalog/body.json, docs/decisions.yaml (D39, D40, D43-D47, D54-D56), docs/turret-next-plan.md
(sections 3-5: the proposed D48-D52), exports/turret/turret.json, exports/leg/{leg,rig-results}.json,
exports/leg/fea/summary.json, cad/fivebar.py `frame_mounts()`, sim/leg_rig.py, sim/robot_v2.py, exports/sim/v2/summary.json,
the leg/stops and legrig/program branches (read only), docs/requirements.md, docs/milestones.yaml, docs/head-payload.md,
docs/handoff.md, and the J501 project (~/Code/j501-agx cad/parameters.json revision 0.9-g48r, exports/simulation-checks.json;
read only). SendCutSend's 5052 and 6061 material pages were read today (section 2.3). The arithmetic behind section 2 is in
/mnt/storage-10tb/claude-scratch/gyropup/body-planner/ledger_levers.py (its output beside it).

Every "decide" below is decided here (D41's rule: the user does not wait on decisions); they are written up as proposed
decisions D57-D64 in section 6 for the implementer to record. Task numbers in this plan are B0-B17; the old plan's
T-numbers are quoted where a task continues one of them.

## 0. In one paragraph

P0 (the power skid) and P1 (the open frame) are a sound build package: seven SendCutSend parts that pass every published
rule, a frame at SF 2.8-4.4 in the leg's real landing loads, zero clashes over 22 stances, a 13S bus whose every part is
rated, and an order list where every line has a price, a link and a backup. **Order it today** with three small fixes
(section 1.2). The one thing the plan got wrong is the mass: the body and head came out at 13.3 kg against the 10.3 kg
budget and the robot at 32.3 kg against 28.5, mostly for good reasons (3/16 in cheeks because 1/8 in failed, a 1/8 in
tray, a power plate and a printed battery bay the plan did not have, the turret's 1.70 kg, the legs' thicker flanges and
machined adapters). That budget cannot be met by any body that holds these parts, so it is retired. **The call
(section 2.4): the robot is designed for 32.5 kg (16.25 kg a leg) in every strength case, held under 32.0 kg as built by
a ledger that gates every commit, and expected at about 31.8 kg after the levers of section 2.3 (about -0.7 kg scheduled
for P2/P3, -1.0 kg more on call).** The legs
must be sized for 16.25 kg: at that mass their three weakest checks (the wheel link's sideways case 1.03, the front link
1.10, the hub dowel bearing 1.12) sit under the 1.2 target, so the leg workstream's stop redesign is the moment to fix
them. Then P2 puts the turret on the deck over a 6061 mount plate that takes the tip-over case from SF 1.3 to over 2,
P3 closes the shell in 2 mm PETG with a fuse board and an aluminium battery tub, and P4 is the dock. The sim, the
firmware and the thermal check (the old T4, T7, T9, T10) are tasks B3, B6-B8 and B9 here.

## 1. Review: P0 and P1 as built

### 1.1 Ready to order and cut today

| What | Evidence | Cost (2026-10-27 prices) |
|---|---|---|
| The SendCutSend set: 2 x cheek (5052 3/16 in, 2 bends, 8 PEM SS-M5-0, 8 countersinks), floor tray (5052 1/8 in, 4 bends, 6 PEM S-M4-0, 2 x M3 taps), belly plate (6061 0.100 in, 12 PEM), deck (5052 0.100 in, 4 bends), compute pallet (6061 0.125 in, 8 countersinks), power plate (5052 0.100 in, 16 flush PEM), 2 x bus bar (C110 0.125 in, 5 x M6 taps) | `exports/body/sendcutsend/*.dxf` and `.step`; `cad/body_sheet.py` reports no rule broken on any part (bend radius and K, half-die distance, PEM edge distances, the channel 2x rule, countersink depth, 0.125 in minimum for countersinks); every flat inside 30 x 44 in | ~$383 estimate; the instant prices are read when the DXFs are uploaded (B1 records them) |
| The frame's strength | `exports/body/fea/summary.json`: S1 landing SF 4.42 away from the standoff ends (1.52 at the bonded ends, a singular corner), S1F fault 2.88 (1.7), S1b one-leg 2.8, S2 twist 0.013 deg, S3 pitch 27, T1 tray 2.5, D1 hand 2.53 / 2.89 with 0.33-0.38 mm at the load, D2 turret fall 1.31 against the 1.2 abuse target; loads from the rig at 15.97 kg a leg (D56) | - |
| The hip-frame interface | `cad/body_params.py frame_mounts()` reads `fivebar.frame_mounts()` (x 0, +-83; z +-70; the plane y -82.3; pilots 11 mm) and measures the same holes from the frame's solid; `test_cheek_holes_on_the_frames_inserts` passes; M5 x 12 through the 4.75 mm cheek engages 7.3 mm of the 7.9 mm insert | - |
| Clearance | `cad/build_body.py` clash sweep: 0 clashes at 22 stances; nearest moving part 25.06 mm (the upper links to the belly plate at 280 mm); the knee pins 29 mm from the narrowed bay door | - |
| The electrics | docs/body-electrical.md: 39 wires with gauge, ends and fuse; every part rated across 39-53.3 V; the MINI 58V branch fuses; the MRBF 80 A main; the DPDT stop relay with the turret's dry loop on pole A and its 24 V on pole B (what docs/turret-next-plan.md 3.2 asked for) | $1,494 bought (incl. the $290 welder and the $100 charger) |
| The prints | 50.2 h on the P1S: posts, riser, isolators, DIN rail pieces, plate posts, bus insulators, the PETG bay halves and door, TPU skids; nothing over the bed | $47 of filament |
| The build and test plan | docs/body-frame.md 6 (eight assembly steps), docs/body-electrical.md 6 (eight bring-up steps with pass numbers) | - |

Everything the leg's interface asked for is taken (the six inserts, the plane, the harness exits past the cheeks' ends, the
wheel harness through the cheek windows), and both of the turret's cross-workstream items (the lidar 143 mm ahead of the
pan axis, the harness grommet at the right rear (-130, -60)) are in `cad/body_params.py` with tests.

### 1.2 Change before ordering

1. **The live ends of the branch leads are sockets, not pins.** The wire list puts an XT60H **male** on the body's end
   of every RS-04 and VESC branch (W10-W15) and an XT30 male on the 24 V and 12 V branches (W21, W24): those pins are live
   whenever the pack is in (the + bus is unswitched; the switch is on the negative). The same rule the charge port already
   follows (hazard 11: "no live pins on the robot") applies: the body's branch leads end in XT60H-**F** / XT30U-**F**
   (sockets); the motor pigtails, the VESC leads and the J501's and lidar box's adapter leads carry the males. In the
   Pyrodrone order: 2 x XT60H-F 5-pack instead of the XT60H-M 5-packs (the females for the charge port stay); XT30U-F
   8-pack for the body, the XT30U-M 8-pack for the device leads. $0 net. `cad/body_wiring.py` W10-W15, W21, W24 and
   the leg's pigtail request (section 5.1 item 5) say which end is which.
2. **Two DDR-120C-24, not one.** Master Electronics flags it "no longer being manufactured" (docs/body-plan.md 1.3); the
   old plan's instruction to buy two stands. +$69.20 (Bravo Electro). The SD-100C-24 is the successor if both ever die.
3. **Read the instant prices before the cart goes** (the ~$383 is an estimate) and record them in `exports/body/bom.json`
   `made_to_order` with the date, so the Build page stops saying "estimate".

Nothing else changes before ordering. In particular the cheeks stay 3/16 in (section 2.3), the deck is cut as drawn (the
turret mount plate of P2 bolts under it through its existing riser holes), and the PETG battery bay is accepted for the
bench and the tether (procedure: charging attended, on a non-flammable surface) until P3's aluminium tub.

### 1.3 Risks carried into P2-P4

| Risk | Where it bites | Measure |
|---|---|---|
| **Mass:** 32.3 kg at P3 against the plan's 28.5; every kilogram raises the legs' loads about in proportion (section 2.2) | the legs' weakest checks, the jump height, the balance gains tuned in sim at 26.2 kg | section 2: the design mass 32.5 kg, the ledger gate, the levers; T4 (B3) at the real mass |
| **The 24 V rail in a jump near empty.** The 13S2P P30B pack is about 112 mOhm (13 x 15 mOhm / 2 + leads): 9 V of sag at the 80 A jump pulse; at a 42 V resting pack the bus dips to 33 V, under the DDR-120C-24's 33.6 V minimum: the J501 could brown out mid-jump | the Jetson, the turret | firmware (B8): no jump below 44 V resting (35 V at 80 A), the jump scaled with bus voltage above that; the Daly K's discharge over-current delay set to 3 s if its app exposes it (else its default checked in step 9) so an 80 A pulse never trips it; P0 step 9 (B12) puts an 80 A pulse on the pack at 44 V with the 24 V output on a scope |
| The turret's tip-over case at SF 1.31 (D2), passed only as an abuse case | the deck round the riser | the turret mount plate (B4, D59): target 2.0 |
| Twelve M5 inserts in printed PA6-CF carry the body: 0.5-0.7 kN each in the landing (bottom row, tension) | the hip frames' flanges | the leg plan's bench test B4, the insert coupon (docs/leg-prototype-plan.md 5: pull-out >= 2.4 kN), covers it at SF >= 3.4; the cheeks also bear on the flange ends |
| The pack's prospective short-circuit current against the fuses' interrupt ratings (open item in docs/body-electrical.md 7) | the MINI 58V (1 kA) and MRBF (2 kA) | by arithmetic it is about 430-480 A (53.3 V over ~112 mOhm plus leads), under 1 kA, and the BMS trips in microseconds first; B12 confirms the BMS's short-circuit setting from its card. Closed unless the BMS card says otherwise |
| The low-side main switch: with it OFF the + bus is still live and the - bus and the frame (bonded to the - bus, W33) float toward + | the bench, the meter's ground, any - bus conductor touching the frame | it is how every e-board is wired and it fails safe (a + chafe blows a fuse once the switch closes; a - chafe is harmless); rule: every - bus conductor insulated from the frame, meter and scope grounds on the - bus only with the switch ON; bring-up step 1 gains "switch off: - bus to pack - reads open" |
| The DDR-120C-24's end of life; every Pololu 60 V buck backordered | the 24 V and 12 V rails | two DDR-120C now; the Pololu D42V110F12 is an opportunistic lever (section 2.3) when it returns |
| The J501's second CAN port (the datasheet says one, the wiki two) | the turret's bus | `ip link` in P0 (B12); the turret stays on its USB-CAN adapter if only can0 comes up |
| The body's CAD reads the J501's parameters from an uncommitted working tree (~/Code/j501-agx, revision 0.9-g48r on branch rev0.8-thermal); the cooler centre is +-3 mm from a photo | the pallet, the fan intake field, the riser's clearance | B10 vendors a dated snapshot with a hash test and the fan centre is measured from the PCB edges when the carrier is on the pallet |
| Ground clearance at the leg's stops is 25 mm (the battery tub's skids at z -160.5; hip height = leg length + 84.5 mm), not the plan's 45 | kerbs at a crouch, the dock's height | the robot drives tall (the sim's curb scenarios); the dock is 30 mm, not 40 (B9); the TPU skids are the sit-down bumper |
| Regen on a full pack reaching 57 V | the RS-04's 60 V fault, the MRBF's 58 V | the P1 scope test (brake from 2 m/s, a full squat) stays the gate before any untethered run |
| The thermal check: the J501 project's own CFD for Rev 0.9-g48r is not settled (exports/simulation-checks.json: fins not calibrated, plate margin unknown) | the shell's vents (T7) | B7 uses a hand model and the thermometer; the CFD only after the J501's case settles, one heavy solver at a time on this machine |
| A 32 kg robot on a tether | the first stand-up | a gantry or ceiling anchor rated >= 100 kg with 0.3 m of slack, a rope not a line, two people |

## 2. The mass problem, first

### 2.1 Where the 32.3 kg are (exports/body/mass.json, stage P3)

| Group | kg | What is in it |
|---|---|---|
| Legs | 18.96 | 2 x (exports/leg/leg.json 9.28 + 0.2 announced for the 13 mm flanges and the stops); of which motors 5.68, wheels 4.40, printed 5.22 |
| Frame | 4.31 | cheeks 0.98, floor tray 0.75, deck 0.65, belly 0.24, pallet 0.23, posts 0.25, riser 0.17, power plate and posts 0.20, bus bars and insulators 0.16, PETG bay and skids 0.36, hardware 0.30 (est) |
| Compute | 1.51 | carrier 0.23, module 0.28, copper spreader 0.20, G48R cooler 0.45 (est), lidar box 0.12 and 3 m cable coil 0.23 (est) |
| Power | 2.02 | DDR-120C 0.45, 2 x VESC 0.46, switch 0.11, shunt 0.09, DDR-60L-12 0.22, MRBF 0.09, fuses and holders 0.11, MCU board 0.08, VN-100 0.02, harness 0.40 (est) |
| Head | 2.53 | VLP-16 0.83, the turret at its 1.70 kg budget (turret.json: 1.639 with 30 balls) |
| Battery | 1.54 | 13S2P P30B with the Daly K BMS |
| Shell | 1.40 | panels 0.80 (est, 3 mm PETG), 2 x D435 0.15, eyes 0.02, 2 x SSC1 pod 0.31, belly skids and door 0.12 |
| **Robot** | **32.27** | body and head 13.31 against the plan's 10.3; P1 (no turret, no shell) 29.17 |

Against the plan's section 1.8 estimate (its table says 29.5 kg; its rows add to 30.2): the cheeks +0.5 (3/16 in on
standoffs against a 1/8 in U), the tray +0.15, the deck +0.2, the power plate with its posts and bus bars +0.36 (the plan
hung those parts on the belly plate), the printed battery bay +0.36 (the plan's cassette was inside the pack's 2.0 kg,
and the pack itself came in 0.46 lighter), the shell +0.2, the G48R cooler and spreader +0.18 against the plan's 34 mm
cooler, the turret +0.36, the legs +0.7 (D46's machined adapters and the flanges); the converters -0.18 and the battery
-0.46 went the other way. About 16.8 kg of the 32.3 are bought parts the body cannot change (motors, wheels, lidar and
cable, turret, compute, battery, VESCs, converters); the rest is the legs' printed parts (5.2), the frame (4.3), the
shell (1.4) and wiring and hardware (0.7).

### 2.2 What every kilogram costs the legs

The leg rig's loads rise about in proportion to the mass it carries: from the leg's committed 14.75 kg a leg
(exports/leg/rig-results.json) to the body's 15.97 kg (exports/body/leg-loads.json), +8.3 % of mass gave +7.1 % on the
drop_150 axle force, +9.4 % on jump_peak and +8.5 % on the undamped power cut; the knee pins +6 to +10 %. (The jump's
push-off is torque-capped, so it does not grow; the landings and the collapse onto the stops carry the mass.) The leg's
strength checks (exports/leg/fea/summary.json, 14.75 kg) already have three under their 1.2 rare-event target or on it:

| Check (target) | at 14.75 kg | at 16.25 kg (loads x1.10) | at 15.97 kg, the ledger today |
|---|---|---|---|
| wheel link R1w, the full axle spike sideways on the link alone (1.2) | **1.13** | 1.03 | 1.04 |
| front link R1 (1.2) | 1.21 | 1.10 | 1.12 |
| hub rear dowel bearing R1 (1.2) | 1.23 | 1.12 | 1.14 |
| upper link R3K, the undamped power cut on the knee (1.0) | 1.27 | 1.15 | 1.17 |
| upper link R1 (1.2) | 1.44 | 1.31 | 1.33 |
| hip frame R1 (1.2) | 1.60 | 1.45 | 1.48 |
| everything else | >= 1.76 | >= 1.60 | >= 1.62 |

So the robot as the ledger stands already puts three leg checks under target, and the leg workstream's stop redesign
(branch leg/stops) is the right moment to fix them for the mass the robot will really have, once, instead of twice.
The gearbox torques (99-108 N m in the jumps at 15.97 kg) stay under the RS-04's 120, and the jump at the 60 N m cap
drops from 268 mm (14.75 kg) to 258 mm (15.97): about 4 % per 8 % of mass.

### 2.3 The levers, ranked

Grams are against exports/body/mass.json; costs are today's prices from docs/body-orders.md where the part is already
listed and estimates (est) elsewhere. SendCutSend's 5052-H32 comes in 0.040, 0.063, 0.080, 0.090, 0.100, 0.125, 0.187
and 0.250 in (bendable) and 6061-T6 in 0.040-0.750 in (not bent), read today: there is no 0.160 in, so the cheeks' only
step down is 0.125 in, which failed the landing case.

**Scheduled (B2, B4, B5, B6): about -0.7 kg**

| # | Lever | Grams | Cost | Stage | Why it is safe |
|---|---|---|---|---|---|
| 1 | Shell panels in 2 mm PETG with 1.6 mm ribs instead of 3 mm (PA6-CF only at the ear-pod bosses) | -240 | $0 (less filament) | P3 | the shell carries nothing structural (docs/body-plan.md 1.1); the walls span <= 140 mm between the tray and deck lips |
| 2 | Floor tray: lightening cutouts where nothing bolts and T1's stress map is low (a Rev B part; 1/8 in stays) | -150 | $62 (a second tray) | P3 | T1 is at SF 2.5 and 0.48 mm; the cutouts stay out of the overhang past the cheeks' ends, where the 0.100 in tray was 1.55 |
| 3 | Deck: cutouts outside the lidar's and the TM patterns and the intake field (Rev B) | -120 | $65 (a second deck) | P3 | D1 re-run (<= 0.5 mm at the load), D2 with the mount plate |
| 4 | **The turret mount plate** under the deck at the riser: 6061-T6 0.125 in, 160 x 140, pocketed (D59) | **+135** | $25 (est; the pallet is $30) | P2 | the one lever that adds: it takes D2 from 1.31 to over 2 (two plates in bending; the 0.125 in 6061 alone has 1.56 x the 0.100 in 5052's section modulus and 1.4 x its yield: 2.2 x the moment capacity on its own) |
| 5 | Deck posts printed hollow (22 mm square, 4 mm walls, 100 %) instead of solid | -100 | $0 | P2 | the posts carry 290 N each at the landing's 8.65 g (the deck, lidar and turret 3.4 kg over four); the inserts need 4 mm walls |
| 6 | Compute pallet: cutouts under the module between the tie-down pattern and the standoffs (Rev B, or the P1 pallet as cut) | -60 | $30 (a second pallet) or $0 | P3 | the pallet is clamped at four isolators and loaded by the J501 on its standoffs |
| 7 | The fuse board (D60) replaces ten inline MINI holders and their leads | -35 | $20 (JLCPCB 5 boards + 12 Keystone 3568/3570 holders at ~$0.30 on LCSC) | P3 | planned in D55; the inline holders stay on P0-P2 labelled "58 V fuses only"; the PCB holders are 32 V parts too, so D55's rule (the fuse interrupts; never pulled live) carries over, and on a board under the shell no one pulls a fuse without the cover off |
| 8 | The shunt on the fuse board (a 1 mOhm 5 W part under the INA228) instead of the 85 g Blue Sea 150 A block | -75 | $3 | P3 | 80 A for 0.3 s is 6.4 W for 0.3 s in a 5 W part: fine; 5 A average is 25 mW; the Blue Sea shunt stays on P0/P1 |
| 9 | The main path in 10 AWG (the 8 AWG 10 ft becomes the spare), the VESC leads in 14 AWG at the firmware's 25 A, lengths cut to P0's measurements | -60 | $25 (BNTECHGO 10 AWG 25 ft) | P2 | 10 AWG silicone carries 55 A continuous; the 80 A jump pulse is 0.3 s; 1.5 m of 10 AWG is 4.9 mOhm, 0.4 V at 80 A |

**On call, in this order, when the ledger needs them (D57): about -1.0 kg more**

| # | Lever | Grams | Cost | When |
|---|---|---|---|---|
| 10 | Pololu D42V110F12 (60 V in, 9 A, ~15 g) instead of the 216 g DDR-60L-12 | -200 | $69.95 | when Pololu restocks it (backordered 2026-10-27); the 12 V rail needs no isolation (both converters' -V are tied to the - bus anyway, W23, W27) |
| 11 | Cheeks Rev B: 1/8 in 5052 with 10 mm-hex M6 standoffs or four more standoffs (-330), or lightening holes in the 3/16 in web where S1 is under 40 MPa (-150) | -150 to -330 | $120 (two cheeks) | P3 or later, only with the FEA >= 2.0 away from the standoff ends and 1.2 at them; never before P1's measured loads |
| 12 | Aluminium hex standoffs (M5, 120 mm) in place of the printed posts | -80 | ~$30 (part number to read) | P3 |
| 13 | The 34 mm WS-RDN-601 cooler (~250 g est) instead of the fitted G48R | -200 | $49 | the user's call after the thermal test; the G48R is what is on the J501 today (j501-agx 0.9-g48r, user photos) |
| 14 | The lidar cable shortened to 1 m | -150 | $0 | the user's call: Velodyne's manual says the cable is permanently attached (a waiver) |
| 15 | The turret's own levers: a 24-ball hopper (-11), a one-board bay (-40) | -51 | $0 | the turret's, listed in its plan, not scheduled |

**Not pulled, and why**

- **The battery stays 13S2P P30B (1.54 kg).** It is already the light choice (D54; the P50B brick is 2.17 kg). A 13S1P
  cannot deliver the 80 A jump pulse (36 A a cell) and would sag 18 V; a 13S1P of 21700 P45B (1.22 kg, -0.3 kg) sags
  15.6 V at 80 A, under the DDR-120C's minimum from a half-charged pack. The pulse sets the pack: two strings of 36 A cells
  is the floor. The jump gate (section 1.3) is the mitigation for the sag the 2P pack already has.
- **The J501 box is not on the robot** (M5's done_when: "no separate box"); the ledger carries the carrier, module,
  spreader and cooler only (1.16 kg). The box's 0.4 kg of PLA was never counted.
- **The head's parts:** the VLP-16 (0.83) and the turret (1.70, D49) are fixed by their workstreams; the lidar box and
  coil (0.35) are the cable's.
- **The riser stays solid** (0.17 kg): it is the turret's load path into the deck and holds the TM inserts.
- **The ear pods stay** (0.31 kg): R27's forward lights and the character (the ears).
- **The 3/16 in cheeks stay for P1** (section 1.2): 1/8 in was SF 0.6 in the landing; lever 11 is a study for later.

### 2.4 The call

- **The design mass is 32.5 kg: 16.25 kg a leg** in every strength case of the legs (cad/leg_studies.py, the rig at
  `--half-mass 16.25`, at BUS_V 48.1) and of the body (cad/body_legloads.py `--half-mass 16.25`, cad/body_studies.py).
  The body's cases at 15.97 kg move by +1.8 % in load: S1 4.42 to about 4.34 away from the standoff ends, S1F 2.88 to 2.83,
  everything still passes (B3 re-runs them).
- **The ledger ceiling as built is 32.0 kg**: legs 9.6 kg each (19.2: the 9.48 of today plus 0.12 for the stops' redesign
  and the three fixes above), body and head <= 12.8 kg. `cad/body_layout.py` carries these as the budget and
  `cad/test_body.py` fails any commit that puts the P3 ledger over them (B2). The plan's 28.5 / 10.3 kg budget is retired.
- **The expected robot is about 31.8 kg**: 32.27 as built, -0.7 kg of scheduled levers, +0.24 kg for the legs at 9.6
  (31.6 if the legs stay at 9.48).
  If the ledger crosses 32.0 (the harness, hardware and cooler masses are estimates until P1 is weighed), the on-call
  levers are taken in order 10, 11, 12 before the next part is ordered.
- **What the legs are designed for:** 16.25 kg a leg at 48.1 V; the wheel link's R1w, the front link's R1 and the hub's
  dowel bearing brought to >= 1.2 at that mass (today 1.03, 1.10, 1.12 scaled); the hip frame's insert pull-out coupon
  (the leg plan's bench test B4) at >= 2.4 kN; the jump at the cap re-run (expect about 250 mm at 16.25 kg and 48.1 V). The leg's
  extra material for those fixes is inside the 0.12 kg a leg the ceiling allows.
- **Why not lighter:** 30 kg would need every lever including the cheeks in 1/8 in (unproven), the other cooler, a cut
  lidar cable and the leg's printed parts 10 % lighter; 30.6-30.8 kg is the floor with every lever pulled (the scratch
  script).
  Designing the legs for a number the robot cannot meet is how the 14.75 kg rig got 1.13 on the wheel link.

## 3. The stages

### 3.1 P2: the head (after P1 balances on the tether)

The turret mount plate under the deck (B4), the riser, the turret on the TM pattern (after the turret's N16 sign-off),
the DT12 harness and the STOP contact (already wired in P0: W34-W37), the lidar; the turret's own N18 tests on the robot
(the barrel and every ball 10 mm clear of the lidar at every pan, the 30 cm drop on the stand); then target practice
tethered, then untethered in a padded room. P2 also fits the hollow posts and the 10 AWG harness if P1's parts are
reprinted or re-cut for any other reason (otherwise they wait for P3). Blocked on: the turret's `exports/turret/mount.json`
(N5) for the final plate and riser (the plug's sweep box), and the turret hardware (N12-N16).

### 3.2 P3: the shell, the fuse board, the tub, the thermal test, the hazard review

Side walls in 2 mm ribbed PETG with the ear pods, the door and the port hatches cut from the mated plugs; the front face
(eyes, D435 cradle); the rear (D435, four RP-SMA bulkheads, the radio receiver bay and stop jack, the switch's 16 mm
button, the charge port); the belly box skids; the knee wedge, apex fillet and stop fairings against the leg's stops as
merged; the battery tub in bent 0.063 in 5052 with printed end caps (the PETG bay burns: hazard 18); the fuse board with
the shunt and INA228 on it; the Rev B tray, deck and pallet if the ledger needs them. The thermal test at 40 W with a
thermometer; the touch temperatures; the hazard review on the P3 robot with the clash list before any session with children.

### 3.3 P4: the dock

The old plan's section 2.5 with one change: the battery is in the belly now, so the charge pads sit in the tub's floor,
the lowest point of the body, and the dock is 30 mm tall so the pads land with the legs 8 mm above their stops (B9).

## 4. Tasks for the Opus implementer

Estimates are agent working hours; "compute" is FEA or MuJoCo time; "bench" is days with hardware in hand, where the
user's hands are needed (the implementer writes the procedure and the log). Work in a feat/ worktree of ~/Code/gyropup
with a PR into dev. New CAD goes in `cad/body_*.py`, exports in `exports/body/`. Nothing in cad/fivebar.py, cad/turret.py
or sim/leg_rig.py changes without the owning workstream (requests to them are section 5). Heavy results go to
/mnt/storage-10tb/claude-scratch/gyropup/ (the root drive is nearly full); only the summaries are committed.

### 4.1 Now, without hardware

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| B0 | **Baseline.** Build main 0e1b0ec: `cad/build_body.py --no-render --quick`, `cad/test_body.py`, `cad/body_bom.py`; `cad/body_studies.py --only D2` for one case. Record 29.17 / 32.27 kg, 0 clashes, D2 1.31, the sheet rules clean | exports/body/* | every build runs; the numbers reproduced within 1 % | 0.5 h + 0.5 h compute |
| B1 | **The order, fixed and priced** (section 1.2): the XT60H / XT30U genders in `cad/body_wiring.py` (W10-W15, W21, W24: sockets on the body) and the Pyrodrone lines; a second DDR-120C-24; the SendCutSend instant prices read from the uploaded DXFs and written to `bom.json` `made_to_order` with the date; docs/body-orders.md and the Build page regenerated | cad/body_wiring.py, cad/body_bom.py, exports/body/bom.json, docs/body-orders.md, docs/body-electrical.md 3.1 | no live pin on any body-side lead; every made-to-order line carries a read price; `test_every_bought_line_has_a_price_and_a_backup` passes | 1.5 h |
| B2 | **The ledger as the gate (D57).** `cad/body_layout.py`: the budget becomes {robot 32.0, legs 9.6 each, body_and_head 12.8, design mass 32.5}; `LEG_STOPS_EXTRA_G` read from exports/leg/leg.json when the leg publishes its new total; a `LEVERS` table (section 2.3: grams, cost, stage, status taken/open) written into mass.json; `cad/test_body.py` asserts the P3 ledger <= the ceiling once the P2/P3 levers' CAD exists (until then the test reports the gap and the open levers) | cad/body_layout.py, cad/test_body.py, exports/body/mass.json, docs/body-frame.md 4 | mass.json shows the ceiling, the gap and every lever's status; the test fails on a ledger over 32.0 kg with the levers taken | 1.5 h |
| B3 | **The sim on the real body (old T4; D62).** sim/robot_v2.py reads the body: `BODY_X` +-160 and `Y_OFF` from `cad/body_params.py`, the frame's solids as collision boxes (cheeks, tray, deck with lips, belly plate, the battery tub as the lowest body, the ear pods), every mass and centre from mass.json P3 (the legs from leg.json as now), the head payload from `body_params.tm()`; `BUS_V` 48.1 in robot_v2; the fifteen scenarios in exports/sim/v2 re-run; `cad/body_legloads.py --half-mass 16.25` and `cad/body_studies.py` re-run at the design mass; the RL build (rl/gyropup_rl/robot.py) left to regenerate on its next run with the trained policy frozen under GYROPUP_MODEL_DIR | sim/robot_v2.py, exports/sim/v2/*, exports/body/leg-loads.json, exports/body/fea/*, exports/body/body.json | every scenario passes at the ledger's mass (31.8-32.0 kg; or a dated note per failure); mass_reconciles true; the jump >= 230 mm at 48.1 V; every body case passes its target at 16.25 kg; `cad/test_body.py` `test_body_loads_from_the_mount_plane` reads the new file | 4 h + 3 h compute |
| B4 | **The turret mount plate (D59) and the riser.** `body_frame.py`: a 6061-T6 0.125 in plate 160 x 140 under the deck centred on the pan axis, pocketed, Ø5.5 on the riser's 80 x 80 feet (clamped by the riser's four screws from below; its screws grow by 3.2 mm), two PEM SS-M5-0 at its +-x ends for M5 screws down through the deck (two new Ø5.5 holes in the Rev B deck; drilled by hand in the P1 deck at the plate's positions); the plate clear of the intake field and the fan's exhaust keep-outs; the riser reads exports/turret/mount.json when it lands (the plug's sweep box as a keep-out); the D2 case with the plate; the P2 SendCutSend cart (the plate; the Rev B tray/deck/pallet as options) | cad/body_frame.py, cad/body_studies.py, cad/body_sheet.py, exports/body/sendcutsend/turret_plate_6061-T6_0.125in_x1.{dxf,step}, exports/body/fea/D2-turret-fall.*, exports/body/bom.json | D2 >= 2.0 and D1 at the riser <= 0.5 mm at the load; the plate passes the sheet rules; 0 clashes with the sweep and the plug box; the ledger +135 g or less | 3 h + 1 h compute |
| B5 | **The fuse board (D60).** A KiCad project: twelve Keystone 3568 (or 3570) MINI holders (eleven branches and a spare) on 2 oz copper with M6 lug pads for the + bus input, the 1 mOhm 5 W shunt with Kelvin pads to an INA228 footprint (the Adafruit 5832 stays usable as a daughter), the - star point stud and the frame-bond stud, "58 V fuses only" in silk at every holder; JLCPCB gerbers; the catalog entries (board, holders, shunt) with prices and links; `cad/body_layout.py` carries its envelope on the power plate where the inline holders were; the wire list's P3 rows | hardware/fuse-board/ (KiCad), catalog/body.json, cad/body_layout.py, cad/body_wiring.py, docs/body-electrical.md | the board fits the plate_fuses box (120 x 42 x 32) or the layout shows where it moved; every branch's trace carries its fuse's rating at 2 oz; the INA228 reads the shunt within 1 %; JLCPCB's DFM passes; every line priced with a link | 6 h |
| B6 | **Shell and guards CAD (old T7, part 1; D61).** `cad/body_shell.py`, `cad/body_guards.py`: side walls 2 mm PETG with ribs, the ear-pod bosses (PA6-CF inserts, the SSC1's 5/16-18 feet), the right door, the port hatches cut from the **mated plugs** with cadagent.connectors (the J501's `ports` in its parameters.json; never a receptacle bbox), the front face (DualEye, the D435 cradle), the rear (D435, 4 x RP-SMA, the receiver bay 30 x 50, the stop jack, the switch's 16 mm button, the XT60 charge port bezel), the belly box and TPU skids, the battery tub in 0.063 in 5052 (bent, printed end caps, the pads' positions for B9), the knee wedge, apex fillet and stop fairings against the leg's stops as merged; the clash sweep with the shell on; the wall stepped in under z +35 where the upper links sweep (|y| 102.5-132.5); the vents sized by B7; every part on the bed | cad/body_shell.py, cad/body_guards.py, cad/build_body.py, exports/body/shell/*, docs/body-safety.md | 0 clashes over the sweep; no shell gap between 4 and 25 mm beside a moving part; the ears' tops under the lidar's -15 deg beam; every port's plug inserts and withdraws in the sweep check; the ledger's shell group <= 1.16 kg (1.40 - 0.24); the tub passes the sheet rules | 8 h + 1 h compute |
| B7 | **Thermal (old T7, part 2).** A hand model first: the G48R's fan at its 16 CFM operating point (the J501 project's checks) against the intake field and the louvres' free area, the exhaust path at +-y under the deck, the DDR-120C at <= 50 % load on its side; the louvre areas set so the fan sees <= 5 Pa of extra back-pressure; the CFD (j501-agx tools/thermal.py, cadagent.cfd) only after the J501's own Rev 0.9-g48r case reports `calibrated` and `steady`, one heavy solver at a time; otherwise the thermometer test in B16 is the acceptance | docs/body-thermal.md, exports/body/thermal/ | the hand model's numbers with their assumptions labelled; the vents' areas in B6's CAD; the CFD case, if run, within 3 K of the hand model's intake temperature | 3 h (+ 6 h compute if the CFD runs) |
| B8 | **Firmware skeleton (old T9, part 1; D63).** `firmware/balance/`: C on the Nucleo-G474RE (CMake + arm-none-eabi, STM32 HAL): three FDCAN at 1 Mbit classic, the VN-100 at 800 Hz on a UART, the 1 kHz loop ported from sim/controller_v2.py, the RS-04 private protocol as the leg rig's rig/rs04.py defines it, the VESC current mode, the Jetson protocol on can0 (setpoints 100 Hz, state 200 Hz, 200 ms heartbeat: balance 2 s then sit), the STOP sense (the relay coil) and MCU_RUN, the INA228 over I2C, UVLO (warn 45.5 V, sit at 41.6 V) and the jump gate (no jump under 44 V resting, height scaled with voltage), the people-near caps as inputs; a HIL harness in Python reusing rig/rs04_emu.py and rig/sim_bus.py from legrig/program through a USB-CAN adapter; CI builds the firmware | firmware/balance/*, firmware/balance/hil/*, docs/body-firmware.md | the firmware builds in CI; the HIL replays the sim's stand_up within 5 % of leg length and lean against the emulated RS-04s; the jump gate and UVLO trip in the HIL at their numbers | 8 h |
| B9 | **The dock (old T10; D64).** `cad/dock.py`: the two brass pads (McMaster brass bar 25 x 60 x 3 on a PETG insulator) in the tub's floor, the printed funnel correcting +-8 mm, the spring contacts, the dock-present pair, the HLG-320H-54A (53.3 V, 3 A) in a printed housing, the AprilTag on the dock's face; the charge relay (10 A automotive, MCU-driven) in the charge port's line in the wire list; the docking scenario in robot_v2 (reverse over the tag at 0.3 m/s, sit to 108 mm, pads closed, the relay only after the tag, the sit and the present line); the parts list with prices | cad/dock.py, exports/dock/*, sim/robot_v2.py scenario `dock`, docs/body-dock.md, catalog/body.json | the pads land inside the funnel from +-8 mm and +-5 deg; the dock 30 mm tall clears the tub at every drive stance; the scenario passes ten times from random starts; every part priced with a link | 6 h + 1 h compute |
| B10 | **Provenance and CI.** Vendor the J501's parameters as `references/vendor/j501/parameters-0.9-g48r.json` with its git hash and the photo note; `body_params.j501()` reads the live file when present and the snapshot otherwise, and a test fails when they differ; exports/turret/mount.json and exports/leg/leg.json read with their hashes recorded in body.json; a CI job runs `cad/test_body.py` and `cad/build_body.py --quick --no-render` | cad/body_params.py, cad/test_body.py, references/vendor/j501/, .github/workflows or the repo's CI | the tests pass with and without ~/Code/j501-agx present; a changed cooler centre fails the test until the snapshot is updated on purpose | 1.5 h |
| B11 | **Record.** D57-D64 in docs/decisions.yaml (section 6's text); docs/body-frame.md, body-electrical.md, body-safety.md, body-orders.md updated for B1-B9; docs/milestones.yaml M5's evidence; the progress and Build pages show P2-P4 | docs/*, designer | every open line of this plan points at a task or a bench test; the Build page lists the P2 cart | 1.5 h |

Order: B0, B1 (the user orders), B2, B3 and B4 together (B3's loads feed B4's D2), B5-B9 in any order, B10, B11 last.
About 45 h of agent time and 8 h of compute: four or five sessions. Printing of the P1 parts and the leg's and turret's
builds run alongside.

### 4.2 With hardware in hand

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| B12 | **P0 bring-up** (docs/body-electrical.md 6, plus: step 1 gains the switch-off float check; the Flipsky card read for the switch's side; the BMS's short-circuit setting from its card; `ip link` for can1; the INA228 calibrated against a meter; **step 9:** an 80 A, 0.3 s pulse (the two RS-04s stalled at a current limit, or an electronic load) on the pack at 44 V resting with the 24 V output on a scope: no dip under 20 V; the measured lengths and masses of every wire and part into the ledger) | docs/body-electrical.md 6-7, exports/body/bringup.json, exports/body/mass.json | the eight steps green with their numbers; the 24 V rail holds through the pulse; the ledger's power and harness rows say "measured" | 2 h + 1 bench day |
| B13 | **Firmware on hardware (old T9, part 2).** One RS-04 and one BotWheel closed-loop from the Nucleo; the VN-100 at 800 Hz; the stop relay from the radio; then both legs on the P1 frame on the tether | firmware/balance/*, exports/body/firmware-tests.json | the HIL's stand_up reproduced on hardware within 10 %; the stop drops torque and sits within 0.5 s of the transmitter off | 6 h + 2 bench days |
| B14 | **P1 assembly and the tether tests** (docs/body-frame.md 6; the plan's order: stand, hold, squat, drive 1 m/s, push, brake from 2 m/s with the scope on the bus, the first jump); the weigh-in of every group into the ledger; a thermometer on the cooler's intake and the DDR-120C on the open frame at 40 W (the baseline for P3) | docs/body-tests.md, exports/body/p1-tests.json, exports/body/mass.json | bus <= 57 V in every brake and squat; stand and hold for 60 s; the measured robot mass within 3 % of the ledger (else the ledger corrected and B2's gate re-run) | 4 h + 3 bench days |
| B15 | **P2: the head.** The mount plate and riser fitted; the turret on (after its N16); the DT12 plugged with the stop relay open; the turret's N18 tests; target practice tethered, then untethered in a padded room; the recoil scenario against the real robot's log | exports/body/p2-tests.json, docs/body-tests.md | every ball and the barrel 10 mm clear of the lidar at every pan; the robot holds balance through an 8-shot burst; the stop cuts the flywheels and sits the robot | 3 h + 2 bench days |
| B16 | **P3: the shell.** The 2 mm panels, guards, the tub, the fuse board (the inline holders and the Blue Sea shunt come out), the lights, eyes and cameras; the 40 W thermal test with a thermometer: the cooler's intake within 3 K of the room, the plate <= 70 C, the exhaust air <= 45 C at the louvres, the ear pods' housings <= 60 C at 50 % PWM; the touch temperatures; the hazard review with the clash list and the table | exports/body/p3-thermal.json, docs/body-safety.md (every row's status to "test" with its number) | every thermal number inside its limit, or the louvres opened and re-tested; the hazard table has no row left "open" before a session with children | 6 h + 3 bench days + ~30 printer hours |
| B17 | **P4: the dock.** Build and the docking test: ten approaches from +-0.3 m and +-15 deg, the charge logged by the INA228 | exports/dock/tests.json | 9 of 10 dock and charge at 3 A; the relay never closes without the tag, the sit and the present line | 4 h + 2 bench days |

## 5. The interfaces to freeze, and what is blocked on them

### 5.1 With the leg workstream (cad/fivebar.py, sim/leg_rig.py, branch leg/stops)

1. **The design mass: 16.25 kg a leg (D57).** sim/leg_rig.py `HALF_MASS` 16.25 and `BUS_V` 48.1 (the body does not edit
   the rig; `cad/body_legloads.py` passes `--half-mass`); cad/leg_studies.py at those loads; the wheel link R1w, the front
   link R1 and the hub dowel bearing to >= 1.2 at that mass; the extra material <= 0.12 kg a leg; the jump re-run.
   The body's loads of docs/body-frame.md 3 were taken with the rig at 54 V: at 48.1 V the jump's speed cap is lower, so
   they are if anything conservative.
2. **The hip-frame interface, frozen with the cheeks' order:** six M5 inserts at (x, z) = (0, +-70), (+-83, +-70) on the
   plane y = -82.3, pilots Ø6.4 x 11 mm, the flange end faces flat on that plane (face [-95, 95] x [62, 77] and its
   mirror); M5 x 12 button heads at 3 N m from inside the gap. Any move of a boss or the plane after the cart is ordered
   is a new pair of cheeks ($120). The leg/stops branch does not touch them (checked: its leg.json and frame_mounts are
   unchanged).
3. **Insert pull-out:** the body's bottom row sees <= 0.7 kN a bolt in the landing, with the cheek bearing on the flange
   ends; the leg plan's bench test B4, the insert coupon (docs/leg-prototype-plan.md 5: pull-out >= 2.4 kN, torque against preload), is the
   body's evidence too. If it comes in under 1.4 kN the body's fallback is a through-bolted row (M5 nuts behind the
   flanges), agreed with the leg.
4. **Harness exits, frozen:** the RS-04 leads leave past the cheeks' ends (`fivebar.harness_angle()`: the front one at
   (127.6, 24.5) at +25 deg, the rear at (-131.9, -11.1) at -169 deg, exports/body/body.json) and turn into the gap; the
   wheel harness through the cheek window |x| <= 20, |z| <= 25; the zone between the motors' rear covers and the centre
   plane stays free (the gusset at x = 0, z 28..62 stays).
5. **Motor pigtails:** 450 mm from the rear cover, ending in **XT60H-M** (the body's branch lead carries the socket:
   section 1.2); the CAN on GH1.25 with 350 mm extensions to the MCU shelf; a 120 Ohm plug at the far motor of each leg.
6. **The sweep envelope near the body, frozen as a test:** upper links |y| 102.5..132.5 reaching z <= +31 within
   |x| <= 225; the knee eyes at |y| >= 83 (the belly plate is 116 wide for them: hazard 1); the stop pins on the frame's
   outer face only. The body's clash sweep (`cad/build_body.py`) runs on both sides' CI; when leg/stops merges, B6 re-runs
   it before the fairings are drawn.
7. **The leg's mass:** exports/leg/leg.json `mass_g.total` with the stops' redesign (today 9,282 g + 0.2 kg announced);
   the ledger reads it (B2). The ceiling allows 9.6 kg.

Blocked on the leg: the three strength fixes and the rig at 16.25 kg (B3's leg-side acceptance); leg/stops merged (B6's
fairings); the coupon test (item 3); the pigtails (P1's wiring); the rig's bench test B1 (the RS-04's power-off damping,
which sets the fault loads the body's S1F case uses: 275 N m undamped, 42 N m damped).

### 5.2 With the turret workstream (cad/turret.py, docs/turret-next-plan.md)

1. **The TM face at (x, z) = (-40, 246)** (deck 216 + riser 30), the lidar's axis 143 mm ahead at x 103, the foot Ø144 and
   the bumper Ø172 (its rear at x -126, 34 mm inside the deck's rear edge); `cad/turret_lidar.py --x 143` is the turret's
   N5; `body_params.LIDAR_TO_PAN` is the one source.
2. **The grommet at (-130, -60), right rear** (D52 taken; `test_turret_grommet_on_the_right_rear`); the DT06 plug stands at
   y -78..-123 from the pan axis at z 265 and withdraws to -153: above the deck and the side wall's top, over the right
   ear pod (z 142..193). B6 keeps that box empty.
3. **exports/turret/mount.json (N5):** mass with and without balls, the centre, the plug's sweep box, the recoil;
   `body_params.tm()` already reads it and takes the larger of it and the 1.70 kg budget. Until it lands the riser and the
   plate are built to the budget and the plug box of docs/turret-next-plan.md 3.1.
4. **The electrical interface, frozen as wired in P0:** pins 1-2 +24 V through the stop relay's pole B and a 5 A MINI 58V
   fuse (W22, W34), 3-4 GND (W35), 5-6 CAN to the J501's can1 (W36; the J501 terminates), 7-8 the dry loop on pole A
   (W37; closed = run; opens on the radio stop, the receiver's failsafe and the sit). The DT12 is plugged only with the
   relay open (the turret's 3 x 1,000 uF). The 24 V rail is 120 W for the J501 and the turret together: the firmware
   staggers the flywheel start from the Jetson's boot; the DDR-240C-24 is the step up if B12 shows the rail at its limit.
5. **The riser's TM inserts:** M5 x 4, 8 mm deep in PA6-CF, under the plate of D59; the turret's 30 cm drop test on the
   stand (N18) is the turret's; the body's D2 case is the deck's.

Blocked on the turret: mount.json (B4's final geometry), the turret hardware signed off (N16) for P2, the N18 tests on
the robot, and the lidar table at 143 mm in the turret's CONFIG.

### 5.3 With the J501 project (read only)

The carrier's holes, the module's tie-down pattern, the G48R cooler (102 x 97 x 50.3 over the spreader at PCB (88, 70.5)
+-3 mm) and the ports come from ~/Code/j501-agx/cad/parameters.json revision 0.9-g48r, an uncommitted working tree on
branch rev0.8-thermal. B10 snapshots it. The fan centre is measured from the PCB edges when the carrier is on the pallet
(B14) and the snapshot corrected if it moved. The cooler tie-down keeps the user's rule (four M3 x 35 flat heads from
below through the pallet into the module-to-heatsink standoffs, 4 mm of thread; the M3 x 35 is still to source:
docs/body-orders.md 4).

## 6. Proposed decisions (for docs/decisions.yaml; the implementer records them in B11)

- **D57 (proposed): the robot's design mass is 32.5 kg (16.25 kg a leg) in every strength case of the legs and the
  body; the ledger ceiling as built is 32.0 kg (legs 9.6 kg each, body and head 12.8 kg), gated by `cad/test_body.py`;
  the expected robot is about 31.8 kg. The plan's 28.5 / 10.3 kg budget is retired.** Why: the body and head came out
  at 13.3 kg for reasons the FEA and the real parts forced (3/16 in cheeks where 1/8 in was SF 0.6, a 1/8 in tray, the
  power plate and the printed bay, the fitted G48R cooler, the turret's 1.70 kg, the legs' thicker flanges and machined
  adapters); 16.8 kg of the robot are bought parts the body cannot change; every lever in section 2.3 pulled reaches
  30.6-30.8 kg, not 28.5.
  The legs' loads rise about in proportion to the mass (leg-loads.json against rig-results.json), and their three
  weakest checks are already under 1.2 at the ledger's mass, so the legs are sized once, for 16.25 kg, during the stop
  redesign. The levers are taken in order: scheduled (1-9) in P2/P3, on call (10-15) whenever the ledger crosses 32.0.
- **D58 (proposed): P0 and P1 are ordered as built, with three fixes: every live end on the body is a socket (XT60H-F
  and XT30U-F on the branch leads; the device leads carry the males), two DDR-120C-24, and the SendCutSend instant prices
  recorded before the cart goes. The cheeks stay 3/16 in; the P1 tray, deck, pallet and PETG bay are not re-cut before
  P1 is weighed and tested.** Why: the package passes every published rule and every strength case; a day's delay for
  pockets would buy 0.3 kg at the cost of re-running checked FEA on an unordered part; the socket rule is the charge
  port's rule (hazard 11) applied to eleven more plugs; the converter is flagged end-of-life by a distributor.
- **D59 (proposed): the turret stands on the 30 mm printed riser over a 6061-T6 0.125 in mount plate (160 x 140, pocketed)
  bolted under the deck through the riser's feet and two PEM nuts, ordered with P2; the deck stays 0.100 in 5052; the
  turret tip-over case (D2) is held to SF >= 2.0 (the everyday target), not the 1.2 abuse target it passed at 1.31.**
  Why: a 1.7 kg head 130 mm above the deck on a 0.100 in sheet is the body's lowest margin and the one a child's shove or
  a fall loads; two plates in bending with the 6061's 276 MPa take it over 2 for 135 g and about $25; the plate also
  stiffens the D1 hand case at the riser (0.51 mm maximum today).
- **D60 (proposed): a JLCPCB fuse board (2 oz copper, twelve Keystone 3568 MINI holders, the 1 mOhm shunt with Kelvin pads
  and the INA228, the - star point and the frame-bond stud, 58 V markings) replaces the inline Bussmann HHM holders and the
  Blue Sea shunt in P3; the holders stay on P0-P2 labelled "58 V fuses only" (D55).** Why: D55 named the board; it also
  removes 110 g of holders and leads and 85 g of shunt, puts every fuse where one glance finds it, and ends the 32 V
  holder on a 53 V bus.
- **D61 (proposed): the shell is 2 mm ribbed PETG (PA6-CF at the ear-pod bosses), every port hatch cut from the mated plug
  with cadagent.connectors and proven by an insertion sweep, the battery tub a bent 0.063 in 5052 box with printed end
  caps, and the thermal acceptance is a thermometer on the robot (intake within 3 K of the room, plate <= 70 C, exhaust
  <= 45 C at 40 W) with the CFD run only after the J501 project's own Rev 0.9-g48r case is calibrated and steady.** Why:
  the shell carries nothing (D44's frame does); 3 mm was the plan's guess and costs 240 g; the mating-plug rule is the
  cad-agent standard since the J501's windows sat 2 mm low; the PETG bay burns (hazard 18) and the 0.063 in tub is
  mass-neutral; the J501's CFD is not settled and a solver fighting the FEA on one machine proves nothing a thermometer
  cannot.
- **D62 (proposed): sim/robot_v2.py models the body as built (the frame's solids, the tub as the lowest body, the ear
  pods, every mass from exports/body/mass.json, BUS_V 48.1, BODY_X +-160, Y_OFF from cad/body_params.py), the fifteen v2
  scenarios are re-run at the ledger's mass, and the RL build regenerates its model from it while the trained policy stays
  frozen under GYROPUP_MODEL_DIR; the body's and the legs' strength loads come from the rig at the design mass, not the
  ledger.** Why: the sim today balances a 26.2 kg robot with an interim shell; the controller gains and the leg studies
  must see 32 kg before P1 stands up; the RL policy is M6's and is not invalidated by a model it does not read.
- **D63 (proposed): the balance firmware is C on the Nucleo-G474RE (three FDCAN, the VN-100 at 800 Hz, the 1 kHz loop
  from sim/controller_v2.py), with the RS-04 protocol as the leg rig's rig/rs04.py defines it and a Python HIL on the rig's
  emulator; it enforces UVLO (warn 45.5 V, sit 41.6 V), a jump gate (no jump under 44 V resting, height scaled with bus
  voltage), the Jetson heartbeat (2 s balance then sit), the STOP sense and the people-near caps; the Jetson decides
  "people near" from the lidar and both cameras (the lidar's rear 84 deg is behind the turret); the Daly BMS's discharge
  over-current delay is set to 3 s where its app allows.** Why: D7 assumed the G474 and nothing better was named; the
  rig node's CircuitPython on a Feather M4 CAN serves one bus at the rig's rate, and the body needs three buses, the IMU
  and an FPU loop at 1 kHz; the 112 mOhm pack sags 9 V at 80 A, so a jump from an empty pack would take the 24 V
  rail under the DDR-120C's 33.6 V minimum; a 100 A BMS with a short delay would trip on a jump pulse.
- **D64 (proposed): the dock is the plan's section 2.5 with the charge pads in the battery tub's floor and a 30 mm dock
  height: the robot reverses over an AprilTag on the rear D435 and the lidar, sits to a 108 mm leg length, two brass pads
  land in a printed funnel on spring contacts, a dock-present pair and the tag gate a 10 A charge relay in the charge
  port's line, the dock holds an HLG-320H-54A set to 53.3 V and 3 A, and the BMS does the rest.** Why: D18 and R24 as
  decided; the tub is now the lowest point of the body (25 mm of clearance at the stops), so the pads go there and the
  dock must be lower than the plan's 40 mm; the charge port's fuse and the BMS already protect the path.

## 7. Still to verify, and TODO

- The SendCutSend instant prices (B1); the M3 x 35 flat heads (Belmetric's socket head is the fallback); the aluminium
  standoff for lever 12 (a McMaster number, read one page at a time); the Keystone 3568's current rating at 30 A
  (the VESC branches) against its datasheet; the 1 mOhm shunt's part number; Pololu's restock of the D42V110F12.
- The G48R's real mass (the ledger's 450 g is an estimate; weigh it in B14) and the DDR-120C's (450 g est against the
  datasheet's 510 g packed); the harness (400 g est) and hardware (300 g est) from P0's and P1's weigh-ins.
- The Flipsky card (the switch's side), the Daly card (the short-circuit trip and the over-current delay), the Luna
  charger's 90 % voltage metered at 53.3 V: all on arrival (B12).
- The leg's new leg.json total and the stops' positions after leg/stops merges; the turret's mount.json after N5.
- The cheek Rev B study (lever 11) needs P1's measured landing loads first: a strain gauge or the rig's drop test on the
  frame before any 1/8 in cheek is drawn.
- Not in this plan: the game page and the voice (M6), the RL policy at the new mass (M6), the leg's spring question
  (D39: after the damping test).

## 8. Notes from the work (2026-10-27)

- **B8 (merged from body/b8-firmware):** the LQR gain table in `firmware/balance/include/gp/gp_model.h` came from the
  interim 26.8 kg model; it is regenerated (`firmware/balance/tools/gen_model.py`) on B3's model of the real body,
  and again whenever `sim/robot_v2.py` changes (the 10S bus of D65 is the next). The jump-height scaling with bus
  voltage is the firmware agent's own rule (docs/body-firmware.md), not a sim result: B13 checks it on the bench. The
  motor calibrations in the firmware are placeholders until `rig/calibrate.py` runs on the bench (B13).
- **The J501's fan blows up** (j501-agx 94da39d): the body's louvres are the inlet and the deck's cells the outlet;
  the printed shroud became a duct (docs/body-thermal.md). The turret box (`cad/turret_box.py`) still assumes the fan
  draws in through the deck.
- **D65 and D66 (main, 0b69b6d, 0a636a4):** the 13S2P brick, its Daly BMS and its tub give way to two DeWalt DCB609
  packs in 20 V mode in series (10S, 30-41 V) on two dock adapters; the DDR-120C-24 gives way to a converter rated to
  28 V or below; the turret's 24 V branch gives way to an XT30 branch off the bus. The voltage windows above (UVLO
  45.5 / 41.6 V, the 44 V jump gate) move to the 10S range: section 9 below records the new ones.

## 9. D65 and D66 in the body (2026-10-27; issues #10, #12, #13)

- **The battery bay** (cad/body_battery.py): the two DCB609 packs hang from their rail adapters under the belly, out
  through two end doors on thumbscrews; 132 mm deep; the robot sits on its skids under a 139 mm leg (H_RANGE 160-375).
- **One converter**, TRACO TEP 150-4812WI (12 V 150 W, 18-75 V), for the J501 and the 12 V rail; the DDR-120C-24 and
  DDR-60L-12 are gone. The turret (D66) is a 7.5 A branch of the bus through the stop relay's pole B (the G2RL-2's
  contact carries 8 A at 30 V, about 6 A breaking at 41 V: B15 measures the inrush and the contact).
- **The firmware's 10S windows** (merged from body/b8-firmware): warn 35.0, jump gate 34.0, sit 32.0, cut-off 30.0 V
  under load, 30 A / 80 A current limits, the regen clamp over 41.5 V and the 44.0 V latch; the jump 199 / 150 / 104 mm
  at 41 / 36 / 34.1 V. The LQR table is regenerated on the D65 model (33.58 kg).
- **B9 (the dock) and B17 are overtaken:** D64 charged the pack through pads in the tub's floor; tool packs charge on
  DeWalt's chargers. A parking stand with the user's DeWalt chargers is the obvious successor; not planned until the
  coordinator asks for it.
- **The mass gate fails:** P3 33.8 kg against 32.0 (the packs 3.13 kg against the brick's 1.54). The options are in
  docs/body-sections.md 6; the gate's test is a strict expected failure until one is chosen.
- **The B5 fuse board** is reworked for 10S (body/b5-fuse-board 760e889, merged): F7 the TRACO 10 A, F8 the turret
  7.5 A, F11 the J501 10 A, F12 the other 12 V loads 7.5 A, F9-F10 spare.
- **Mechanics first** (issue #13): cad/body_joints.py models every screw as a joint and checks it through the CAD; it
  found and fixed thirteen faults (the commit messages list them); cad/body_sections.py writes docs/body-sections.md.
