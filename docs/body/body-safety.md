# Body hazard table: what can hurt a child, and what the design does about it

The body's hazards (milestone M5), carried from docs/body-plan.md section 1.7 into the CAD and the wiring as built
(`cad/body_*.py`, `exports/body/`, docs/body-electrical.md). Each row says where the measure lives and how it is
checked. Rules used, as the plan: ISO 13854 (a crushing gap is safe at ≥ 25 mm for fingers, ≥ 100 mm for hands),
ISO 13857 (an opening ≤ 4 mm admits no finger; a slot ≤ 8 mm admits a fingertip only, safe when the hazard is ≥ 15 mm
behind it), touch temperatures 48 °C on metal and 60 °C on plastic, SELV below 60 V DC. Written 2026-10-27.

**Status:** *in the CAD* (built into a part, checked by `cad/test_body.py` or the clash sweep), *in the wiring*
(docs/body-electrical.md), *P3* (the shell and guards, task T7), *procedure* (a rule for whoever runs the robot),
*test* (measured on the prototype, with the pass number).

## 1. Moving parts

| # | Hazard | Where | Measure | Status |
|---|---|---|---|---|
| 1 | Shear between the knee's eye boss and the body | each upper link's knee eye sweeps past the belly at \|y\| ≥ 83 mm, z +31 to -169 | the belly plate is 116 wide (\|y\| ≤ 58), not the plan's 160: the gap is ≥ 25 mm everywhere in the leg's range (it was 3 mm) | in the CAD (`BELLY_HALF_Y`); the clash sweep's nearest-distance list in exports/body/body.json |
| 2 | Shear between the battery bay and the knees | the bay's sides at \|y\| ≤ 42.8 | 40 mm to the knee eyes at the lowest stance | in the CAD (cad/body_battery.py summary) |
| 3 | Pinch between the upper links and the cheeks, tray, posts, shell or tub | the links turn beside the body | no body part within 25 mm of a moving leg part, or ≤ 4 mm with a fixed guard; the P3 shell's walls keep 46 mm (nothing of the legs rises above z +31); the tub's end caps are 97.6 mm wide so the knee pins keep 29.8 mm | in the CAD: the clash sweep with the shell and tub on (`clash_sweep`: 22 stances, 0 clashes, nearest 25.06 mm) and its `shell_gaps` list (no shell part between 4 and 25 mm of a moving part), checked by `cad/test_body.py` |
| 4 | The leg's own pinch points: knee scissor, the lower-link V, stop posts, wheel against its link | the legs | people-near mode first; the knees close no tighter than 24.9° inside the stops, so a TPU 95A wedge 58 mm long on each upper link keeps the scissor ≥ 25 mm; the apex V closes to 29.1° at full height, so a 50 mm apex fillet does the same (`cad/body_guards.py`, envelopes in `exports/body/shell/`); the stop posts' fairings wait for leg/stops (D53 moves the posts) | requirement and envelopes in the CAD (B6); fitted to the links by the leg workstream after leg/stops merges |
| 5 | The J501's fan | 21 mm under the deck's top, under the turret's riser (the cooler centred on the module: fan at robot (-60, 9), the J501 project's Rev 0.9) | the deck's cell field (the fan's outlet: it blows up): 31 cells 8 mm square on an 11 mm pitch round the fan's axis (a fingertip only, ≥ 15 mm from the blades: ISO 13857); in P2 the turret plate's opening covers none of them; in P3 a printed duct from the plate to 2 mm over the fan frame | in the CAD (`intake_cells()`, `turret_plate_intake()`, `body_shell.fan_duct`); a test-finger check on P1 |
| 6 | The wheels | the BotWheel's tyre against the ground and anything in its path | people-near mode (≤ 0.5 m/s), the radio stop; the shell does not cover the tyres | procedure + firmware (T9) |
| 7 | The turret | pan ring, flywheels, projectiles | the turret's own plan (D41: the safety line cuts the flywheels and the dial in hardware); the body's stop relay opens its safety loop and cuts its 24 V (W34, W37) | in the wiring |

## 2. Electrical

| # | Hazard | Where | Measure | Status |
|---|---|---|---|---|
| 8 | Shock | the 13S bus | 53.3 V maximum: under the 60 V DC SELV limit | in the design (D43) |
| 9 | A short circuit of the pack (the real electrical hazard: hundreds of amps, burns, fire) | the pack leads, the bus bars | the BMS's short-circuit protection; the 80 A MRBF main fuse on the + lead within 150 mm of the plug (W3); a MINI 58V fuse on every branch; every + run in red silicone with its own fuse; bus bars on printed insulators (no screw of a bar reaches the plate) | in the wiring; **open**: the pack's prospective short-circuit current against the fuses' 1 kA and 2 kA ratings, from the BMS's card or a bench trip test (docs/body-electrical.md 7) |
| 10 | A + lead chafed to the frame leaves the frame live | the aluminium frame | the frame is bonded to the - bus (W33): the fault blows the branch fuse | in the wiring; test: frame to - bus < 0.1 Ohm (bring-up step 1) |
| 11 | Live pins a child can touch | the charge port, the pack plug | the charge port is a female XT60 (sockets only) on the robot; the XT90-S's pins on the robot side are dead with the pack out, and the charge port feeds only the pack | in the wiring (W8, W9) |
| 12 | A fuse holder rated 32 V on a 53 V bus | the eleven inline MINI holders | the MINI 58V fuse interrupts (1 kA at 58 V); each holder is labelled "58 V fuses only" (a 32 V fuse fits the same socket); fuses are pulled only with the pack unplugged; a fuse board with PCB holders in P3 | procedure + in the wiring (D55) |
| 13 | A spark at the pack plug | the XT90 | the XT90-S's anti-spark resistor; the main switch off before plugging | procedure |
| 14 | The BMS bypassed through its data ground | the BMS's UART (its ground is B-) | nothing is wired to the BMS's data ports: the BMS is read over Bluetooth (D54) | in the wiring |
| 15 | No stop when the radio drops | the radio stop | the ER3C-i's failsafe (no pulses) drops the RC switch, which drops the DPDT stop relay: its pole A opens the turret's safety loop (flywheels and dial cut in 20 ms), its pole B cuts the turret's 24 V, and the MCU, sensing the coil, sits the robot down (D37, D55) | in the wiring; test: transmitter off opens the relay within 0.5 s (bring-up step 5) |

## 3. Battery and charging

| # | Hazard | Where | Measure | Status |
|---|---|---|---|---|
| 16 | Over-charge | charging | the charger stops at 53.3 V (4.10 V a cell, metered before first use); the BMS's cell over-voltage at 4.15 V is the backstop; charge over-current 6 A | procedure + the BMS settings (docs/body-electrical.md 2.1) |
| 17 | Over-discharge, over-current, temperature | driving | the BMS: 3.00 V a cell, 100 A, charge 0-45 °C, discharge -10-60 °C; the MCU's own under-voltage sit-down at 3.3 V a cell (T9) | the BMS settings; T9 |
| 18 | A cell fire | the drawer in the belly | matched cells, fish paper on every + end, Kapton over the welds; **charging only attended, on a non-flammable surface**; the bay is PETG in P0-P2, which burns: in P3 the cells sit in an aluminium tub (a 0.063 in 5052 floor bent up 20 mm, two 0.063 in side plates, the belly plate as its roof: aluminium on five sides), its PETG end caps the only printed faces (`body_shell.tub_*`, D61) | P0-P2 procedure; P3 in the CAD (the tub passes SendCutSend's rules) |
| 19 | A self-built pack | the brick | the build steps and checks of docs/body-electrical.md 2.1 (tap-order check before the BMS is plugged; a capacity and resistance test before first use) | procedure + test |

## 4. Heat and edges

| # | Hazard | Where | Measure | Status |
|---|---|---|---|---|
| 20 | Hot cooler exhaust | the G48R's fan blows up (j501-agx 94da39d): its exhaust leaves through the deck's cells and out of the riser's sides under the turret | the fan duct keeps the exhaust out of the body; the fins' open sides are kept clear inside the body (`cooler_fins_*` keep-outs); the P3 walls' louvres (14 slots 4 x 46 mm a side: no finger) let the room's air in; the hand model gives 33 °C out of the riser at 40 W and the cooler's inlet 2.5 K over the room (docs/body-thermal.md) | in the CAD; **test** B16: ≤ 45 °C out of the riser, the inlet ≤ 3 K over the room |
| 21 | Hot converters, VESCs, shunt | the power plate | inside the body, under the deck: not touchable once the shell is on (the left side's service door is held by four M3 screws: a tool opens it); on the open P1 frame, hands off while powered | P1 procedure; P3 in the CAD |
| 22 | Sharp sheet edges and the lips' corners | the tray, deck, belly, cheeks | every SendCutSend part deburred (on the order); the lips' open corners have round reliefs; the shell covers the frame in P3, its door and hatch with 3-4 mm corner radii | in the order (docs/body-orders.md); P3 in the CAD |
| 26 | Live pins on the body's leads | every 48 V, 24 V and 12 V branch | every live end on the body is a socket (XT60H-F, XT30U-F); the devices carry the pins (D58) | in the wiring; `test_no_live_pins_on_the_body` |
| 27 | The P3 shell's openings | the louvres, the port hatch, the door, the eyes' window, the D435 windows | louvres 4 mm (no finger); the hatch and door closed by screws (a tool); the eyes' and cameras' windows are filled by the board and the cameras' glass | in the CAD (`cad/body_shell.py`) |
| 23 | The lidar's laser | the VLP-16 | Class 1 (eye-safe) | in the part |

## 5. Mass and falls

| # | Hazard | Where | Measure | Status |
|---|---|---|---|---|
| 24 | The robot (29-32 kg) falling on a child | anywhere | people-near mode (a person within 0.6 m: legs hold, ≤ 0.5 m/s, no jumps, sits after 2 s); the radio stop sits it down; the undamped power cut is the legs' fault case (D39) | firmware (T9) + the leg workstream |
| 25 | A heavy robot | the mass ledger: 32.2 kg at P3 with the shell, the tub and the turret (exports/body/mass.json) | D57: designed for 32.5 kg, held under 32.0 as built: the gate (`cad/test_body.py`) passes with the open scheduled levers; the on-call levers next (docs/body-frame.md 4) | in the CAD (the ledger as the gate) |

A hazard review on the P1 frame, with this table and the clash sweep's list, comes before any session with children
(the plan's rule).
