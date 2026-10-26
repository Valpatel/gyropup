# Gyropup CAD plan: robot + turret (2026-10-25)

Companion to the review [`research/mech-review-2026-10-25.md`](../research/mech-review-2026-10-25.md) (finding IDs
A1…F4 are cited below). Frame everywhere: x forward, y left, z up, origin on the hip axis; left leg built, right mirrored.

## 1. Verdicts

| Area | Verdict |
|---|---|
| Concept | Right: coaxial hip + knee at the body, parallelogram knee, hub-motor wheels, J501 box as the body, lidar under the waist, turret on the head. Keep. |
| Knee drive as drawn | **Not buildable**: dead point at a 90° knee, 6° from the standing pose (A1). One geometry change fixes it. |
| Physics model | **Does not represent the machine**: serial knee instead of a base-grounded parallelogram (A2); no collision for the leg modules or the lidar (C2); primitive inertias (C3). The hip motor's real load is 11 N·m continuous and 61 N·m peak where the sim reports 0.14 / 37. |
| 3D simulator | The CAD rig is the right idea; four copies of the leg kinematics and a procedural turret are not (D1–D3). The page should set transforms the physics writes, nothing else. |
| Structure | Aluminium where motors and bearings bolt on is right; "CNC from solid everywhere" is not. 6.9 kg of made parts → 3.6 kg with sheet, tube and four machined plates (A6, E1). |
| Load cases | Static and the simulator's mild peaks only. Missing: falls, kerb drop, landing, rod, pin, bolts, chassis, fatigue (A5). |
| Head, battery, dock | No load path for the head except the printed J501 lid (B1); no battery door (B2); dock and lidar collide (B3). A frame fixes all three. |
| GMI | Keep the faces as the drawing standard; stop making every face a separate CNC part (E3). |
| Turret | Head is the right place with a frame under it; servo ring-gear pan with an open centre, launcher cartridge, dedicated 24 V (F1–F3). |

## 2. Architecture decisions

| # | Decision | Alternatives considered | Why |
|---|---|---|---|
| P1 | **Knee drive: parallelogram, lever along the shin.** Shin lever at β = 75° from the perpendicular (15° off the shin axis), pointing up past the knee; crank parallel to it; crank radius 60 mm; knee range 48–155°. | (a) Lever perpendicular (current): dead point at 90° (A1). (b) Knee motor on the thigh at the hip (knee reacts on the thigh): exact serial model, hip idles at rest, but the knee cable crosses the hip and the leg gains 0.9 kg at the axis. (c) Knee motor at the knee (Upkie): no rod, exact model, but 0.9 kg at the knee, motor near the ground, 50 mm wider. (d) Non-parallelogram four-bar: better crouch ratio, harder to model. | min sin φ = 0.5 over the range, rod force ≤ 1.8 kN at 54 N·m; both big motors stay on the body; the sim mapping τ_hip = Q_hip − Q_knee is exact and cheap (tendon). (b) stays a loop variant (`leg.topology`). |
| P2 | **Frame = two 6 mm 6061 side plates** (tray floor to head plate, laser-cut with windows) + bent 3 mm 5052 crossmembers (floor channel, front and rear) + 4 mm 6061 head plate. Leg modules bolt to the outside of the side plates (HM). J501 box sits inside on 4 rubber isolators and carries nothing. | (a) Current: 3 mm closed sheet box + box on top + 952 g machined yokes. (b) Printed PET-CF frame with aluminium inserts: FEA says printed yoke bent 10 mm. (c) CF plate sides: lighter by 40 %, v2 once loads are measured. | One flat part per side carries the hips, the head and the bumpers; SendCutSend, 2–4 days; removes the yoke wall, the chassis walls and the M3 load path (B1). |
| P3 | **Hip module (per side):** hip motor inboard against the side plate (rear lug face on a 19 mm spacer ring, 8 × M4, if the rear threads are confirmed; else a bent-sheet hat bracket), hip motor plate (CNC, 61812 support bearing), thigh hub, rod plane, crank, knee motor plate (CNC, 61812), knee motor outboard. Three M5 posts above the axis. Yoke = bent 3 mm 5052 hat (150 g) instead of 952 g machined. | Both motors inboard (needs a hollow shaft: none available). Knee outboard but wheel inboard of it: 48 mm narrower, needs a 20 mm longer axle offset. | Keeps the stack that exists; drops 1.6 kg; width 560–590 mm accepted (A4) and left to the loop. |
| P4 | **Links: 40 × 30 × 2 6061-T6 rectangular tube** with machined end fittings (hip hub with the AO-L mate; knee fork; shin hub with 2 × 6001-2RS and the lever; wheel foot with WH). Fittings bonded (3M DP420) and cross-pinned (2 × M5). | CNC from solid (current, 377 g); flat 6 mm plate pairs (SF 1.5 out of plane); CF 25 mm round tube in printed sockets (v2 for the shin). | Tube: 230/190 g, stiff in both planes, cables inside. |
| P5 | **Knee: shin fork around the thigh hub** (bearings 36 mm apart), ISO 7379 12 h8 shoulder screw, lever on the outer cheek. | Cantilever pin (current, A3). | Double shear, no bore ovalising. |
| P6 | **Output adapter merged into the link hub** where the motor is the RS-03 (one CNC part per joint presenting AO-L outward for swaps); keep separate adapters only when a different motor is fitted. | Four separate adapters (current). | −4 parts, −0.15 kg, −$250; the standard face survives as the drawing. |
| P7 | **Battery: rear-loading** through a hinged rear door in the rear crossmember; dock adapter fixed at the front of the tray; pack slides on its own rail. | Backpack pack outside the frame (loop variant: CoM +40 mm back). | 10 s swap with no tools (B2). |
| P8 | **Charge contacts on the rear lower edge of the side plates**, engaged by reversing onto the dock, crouch sets the height; lidar stays under the waist. | Plate under the tray (D18, collides with the lidar). | Resolves B3. |
| P9 | **Bus: revert to D23 (2 × FLEXVOLT in 20 V mode in series, 40 V)** unless the user accepts a "arm below 58 V" rule. | One pack 60 V (D25). | RS-03 absolute max 60 V = a full pack (B7). The loop evaluates both. |
| P10 | **Head: turret on the head plate** on a servo ring-gear pan with an open centre, launcher cartridge detachable, TPU bumper ring, pan axis 35 mm forward of the box centre, chimney snorkel. | Chin turret (lower, protected, −150 mm muzzle height). | F1–F3. |
| P11 | **Materials:** 6061-T6 (plates, tube, fittings), 5052-H32 (bent brackets), PET-CF (printed structure, covers, turret), PETG (cradles, hopper), TPU 95A (guards, bumpers, tyres on flywheels). PA6-CF only annealed. | PA-CF everywhere; CF plate. | E1, E4. |
| P12 | **Weather: v1 is dry-outdoors (IP43-ish)**: motor boots, glands, drip skirt, snorkel, conformal coat. | IP54 now. | B6; RS-03 is IP52. |

## 3. Part tree: robot

Qty per robot. "SCS" = SendCutSend (2–4 days). "CNC" = JLCCNC/PCBWay 6061 (7–10 days). Masses are targets (est).

### 3.1 Made parts

| Part | Qty | Material / process | Mass | Notes |
|---|---|---|---|---|
| side_plate | 2 | 6061-T6 6.35 mm, SCS laser; dowel holes hand-reamed | 420 g | HM pattern (6 × M6 + 2 × Ø6 dowels), hip spacer ring holes (8 × M4 on Ø98), head plate tabs, bumper bosses, charge contact pad, cable passes (CP), lightening windows |
| floor_channel | 1 | 5052-H32 3.175 mm, SCS bent | 220 g | Ties the side plates; battery cradle rails bolt on; lidar hanger (4 × M4); drain holes with mesh |
| front_crossmember | 1 | 5052-H32 3.175 mm, SCS bent | 90 g | Face, headlights, front camera cradle |
| rear_door_frame + door | 1 + 1 | 5052-H32 3.175 mm, SCS bent; hinge pin | 140 g | Battery access; rear camera on the door; two draw latches |
| head_plate | 1 | 6061-T6 4.75 mm, SCS laser | 230 g | TM pattern (4 × M5 on 80 × 80 + 2 × Ø5 dowels + Ø45 centre hole), 4 corner bumper posts, chimney cutout + snorkel mount |
| hip_spacer_ring | 2 | PET-CF print (or 6061 ring, CNC) | 40 g | 19 mm, RS-03 rear lug face → side plate; **only if the rear M4 threads are confirmed** |
| yoke_hat | 2 | 5052-H32 3.175 mm, SCS bent | 150 g | Wall flange (HM), deck, two drops to the plate tabs; replaces `yoke_bracket` |
| hip_motor_plate | 2 | 6061-T6 8 mm, CNC | 200 g | 61812 seat H7, RS-03 lug pattern + Ø70 spigot recess, 3 post holes, tab; pocketed |
| knee_motor_plate | 2 | 6061-T6 8 mm, CNC | 200 g | same |
| thigh_tube | 2 | 6061-T6 40 × 30 × 2 rectangular tube (McMaster/OnlineMetals 1.5 × 1 × 0.065 in) | 150 g | cable ports, bonded fittings |
| thigh_hip_hub | 2 | 6061-T6, CNC | 90 g | RS-03 output pattern (6 × M4 + 3 × Ø4 dowels on Ø30.36), Ø60 bearing journal, AO-L face outward (P6) |
| thigh_knee_hub | 2 | 6061-T6, CNC | 60 g | Ø12 H7 bore, 30 mm wide, inside the shin fork |
| shin_tube | 2 | 6061-T6 34 × 24 × 2 (or 40 × 30 × 2 until the FEA says otherwise) | 120 g | |
| shin_knee_fork | 2 | 6061-T6, CNC | 110 g | two 6001-2RS seats 36 mm apart; lever at β = 75°, r = 60 mm, M8 rod-end pin boss |
| shin_foot | 2 | 6061-T6 6.35 mm, SCS laser | 40 g | WH: 6 × M5 PCD 50, Ø32 bore; or integrated into the wheel adapter |
| wheel_adapter | 2 | 6061-T6 6.35 mm, SCS laser | 36 g | BotWheel 4 × M6 PCD 36 + Ø50 boss, Ø16 cable bore |
| knee_crank | 2 | 6061-T6 8 mm, CNC (shares the plate order) | 80 g | RS-03 output pattern + journal, arm to r = 60 at β |
| battery_cradle | 1 | PETG print | 50 g | rails + adapter mount |
| lidar_hanger | 1 | PET-CF print | 60 g | 1/4-20 + 2 pins; vibration pads |
| camera_cradle | 2 | PETG print | 34 g | D435/D415, 1/4-20 |
| face | 1 | PETG print | 60 g | DualEye window, LED pod bosses |
| knee_guard | 2 | TPU 95A print | 40 g | web across the inside of the knee scissor (B5) |
| motor_boot | 4 | TPU 95A print | 30 g | over each rear cover and its connectors (B5, B6) |
| crank_cover | 2 | PETG print | 20 g | disc over the crank sweep |
| bumper | 4 + 2 | TPU 95A print | 30 g | head plate corners, side plate lower rear |
| cable_clips, grommets | — | TPU / bought | — | CP every 60 mm |

Made-part total target: **≈ 3.6 kg** (from 6.9).

### 3.2 Bought parts (robot)

| Part | Qty | Part number / spec | Source, availability (2026-10-25) |
|---|---|---|---|
| Leg actuator | 4 | RobStride RS-03 (60 N·m peak, 20 rated, 880 g) | Seeed "in stock" CN warehouse $225; rcdrone.top $224 (`catalog/availability.json`) |
| Wheel | 2 | ODrive BotWheel BW0124 (171 mm, 2.2 kg) | ODrive shop, $269/pair, in stock (US) |
| Wheel driver | 2 | Flipsky 75100 (single) VESC, 14–84 V | Flipsky, in stock |
| Support bearing | 4 | 61812-2RS (60 × 78 × 10) + DIN 472-78 / DIN 471-60 circlips | Amazon/VXB/Motion, stock |
| Knee bearing | 4 | 6001-2RS (12 × 28 × 8) | stock anywhere |
| Knee pin | 2 | ISO 7379 shoulder screw 12 h8 × 40, M10, 12.9 | McMaster, stock |
| Rod end | 4 | igus igubal KBRM-08 (female M8) or SKF SIKAC 8 M | igus/Motion, stock |
| Push-rod tube | 2 | 4130 steel Ø14 × 1.5, M8 bonded/welded inserts (or 6061 16 × 2) | McMaster |
| Rod-end pins | 4 | ISO 7379 8 h8 × 20, M6 | McMaster |
| Posts | 6 | Ø10 aluminium standoff, M5 F/F, length = plate gap (54 mm) | McMaster |
| Hip spacer screws | 16 | M4 × 12 12.9 DIN 912 | |
| AO-L / hub screws | 24 + | M4 × 10 12.9 (motor), M5 × 16 12.9 (faces); Loctite 243 | |
| HM screws | 12 | M6 × 16 12.9 + Nord-Lock | |
| Inserts | — | Ruthex M3/M4/M5 heat-set (prints) | |
| Battery | 1–2 | DeWalt DCB609 FLEXVOLT 9 Ah | user has |
| Battery dock | 1–2 | Terrafirma FLEXVOLT 60 V dock adapter (or 20 V adapters × 2 for P9) | Amazon |
| Power | 1 each | Mean Well DDR-120C-24 (J501), DDR-30L-12 (lidar, lights), DDR-60L-24 (payload, P10) | Mouser/Digikey, stock |
| Protection | — | Blue Sea 5191 MRBF block + 80 A fuse; Altran ALEV100-BS contactor; Flipsky Antispark Pro 200 A; HB2-ES544 e-stop | in catalog |
| Compute / sensors | — | Seeed J501 + AGX Orin 32 GB (own box), VLP-16, 2 × RealSense D435, VN-100 Rugged, Waveshare 0.71 in DualEye | user has |
| Balance MCU | 1 | WeAct STM32G474 core (assumed, D7) + 2 × SN65HVD230 | AliExpress/Amazon |
| Glands | 6 | PG9 nylon, IP68 | Amazon |
| Isolators | 4 | M4 rubber-metal mounts, 30 shore | Amazon |

## 4. Part tree: turret (head payload, concept from the launcher study §8)

### 4.1 Made

| Part | Qty | Material / process | Mass | Notes |
|---|---|---|---|---|
| pan_base | 1 | PET-CF print | 90 g | bolts to TM on the head plate; holds the 61810-2RS outer race; STS3215 pan servo pocket; hard stops ±170°; drip skirt |
| pan_ring | 1 | PET-CF print | 70 g | 60 T internal ring gear (module 1) on the bearing inner race; Ø45 open centre for the clock-spring loop; mounts the tilt yoke |
| pan_pinion | 1 | PET-CF print | 5 g | 20 T on the STS3215 horn (3:1) |
| tilt_yoke | 1 | PET-CF print (2 arms + bridge) | 80 g | STS3215 tilt servo on one arm, 6 × 12 bearing on the other; **hard stop at 0° body frame** |
| cradle | 1 | PET-CF print | 50 g | cartridge seat: 2 dowels + cam latch; blind-mate connector |
| cartridge_body | 1 | PET-CF print | 110 g | flywheel cage (2 × Snail 2305, 40 mm wheels at 60 mm centres), barrel socket, ammo ID pins |
| flywheel | 2 | PET-CF hub + TPU 95A tyre print | 10 g | Ø40, 5 mm bore with flat; bench-tuned diameter (study §8.3) |
| hopper + lid + flap | 1 | PETG print, clear window | 90 g | 30 balls (0.3 L); spring flap for the dock spout; hopper-full beam |
| dial | 1 | PETG print | 20 g | 8 pockets, stirring spokes, on the M2006 output; blocks the path unpowered |
| barrel | 1 | 25 mm OD acrylic/PETG tube, 120 mm | 25 g | chronograph gate windows |
| laser_mount | 1 | PETG print | 8 g | beside the barrel, boresight screws |
| bumper_ring | 1 | TPU 95A print | 40 g | around the pan base |

### 4.2 Bought

| Part | Qty | Part number | Notes |
|---|---|---|---|
| Pan / tilt servo | 2 | Feetech STS3215 (12 V, 30 kg·cm) + 1 bus adapter | $22 each; the pan via 3:1 ring → 8.7 N·m, 90°/s |
| Pan bearing | 1 | 61810-2RS (50 × 65 × 7) | |
| Tilt bearing | 1 | MR126-2RS (6 × 12 × 4) | |
| Flywheel motors | 2 | DJI RoboMaster Snail 2305 | $40 each |
| ESC | 2 | Repeat Robotics AM32 35 A (RPM telemetry) | $25 each |
| Feed motor | 1 | DJI RoboMaster M2006 P36 + C610 ESC (CAN) | $95 + |
| Head MCU | 1 | WeAct STM32G431 core + SN65HVD230 (or the user's CAN board) | runs RPM loop, dial, chronograph, interlocks |
| Chronograph | 2 | IR break-beam pairs (ITR9608) | |
| Laser | 1 | Picotronic DD520-1-24(12×40), 520 nm Class 1 | |
| Payload converter | 1 | Mean Well DDR-60L-24 + 2 × 2200 µF 35 V | behind the arming relay |
| Arming relay | 1 | 24 V 10 A automotive relay (or Pololu high-side MOSFET switch) in series with the e-stop loop | |
| Connector | 1 pair | Deutsch DT04-12PA / DT06-12SA (12-way, IP68) | head plate ↔ turret |
| Ammo | — | Worker Cheetah or Dart Zone Powerstrike Rival rounds | |

Turret total target ≈ **1.15 kg**, CoM ≈ 80 mm above the head plate.

## 5. Interfaces (GMI v0.3: the faces that stay)

| Code | Between | Definition | Design load | Status |
|---|---|---|---|---|
| HM | side plate ↔ hip module | 6 × M6 on 100 × 60 + 2 × Ø6 dowels + Ø18 CP | 600 N, 80 N·m | unchanged |
| AO-L | motor output (hub) ↔ link | Ø40 h7 spigot, 8 × M5 on Ø50, 2 × Ø5 dowels (22.5°, 247.5°) | 80 N·m, 2 kN, 60 N·m tilt | unchanged; hub may *be* the adapter (P6) |
| AC-L | motor case ↔ plate | motor lugs + spigot; 61812 seat; 3 posts R82 at 30/90/150°; tab 3 × M5 | leg bending via the bearing | unchanged |
| KC | thigh ↔ shin | **fork on the shin**, 2 × 6001-2RS 36 mm apart, 12 h8 pin | 3 kN | changed (P5) |
| PR | crank ↔ shin lever | M8 rod ends, Ø14 × 1.5 tube, **lever β = 75°, r = 60 mm**, min sin φ ≥ 0.5 | ±2 kN | changed (P1) |
| WH | shin ↔ wheel | 6 × M5 PCD 50, Ø32 bore, Ø16 cable bore | 400 N, 30 N·m | unchanged |
| TM | head plate ↔ payload | **4 × M5 on 80 × 80 + 2 × Ø5 dowels + Ø45 centre hole**; DT 12-way (24 V 10 A, GND, CAN H/L, e-stop loop ×2, dead-man, laser enable, 2 ammo-ID, spare ×2) | 1.5 kg at 120 mm, 0.05 N·s/shot, 30 g fall | fixed now (B4) |
| CT | cradle ↔ cartridge | 2 × Ø4 dowels + cam latch; 8-pin blind-mate (24 V, CAN, chrono ×2, ID ×2) | 0.5 kg | new (study §7.2) |
| CP | every module boundary | Ø18 grommet or PG9 gland + strain relief | — | unchanged |
| DK | robot ↔ dock | 2 spring contacts on the side plates' rear lower edge; fiducial; silo spout to the hopper flap | 10 A charge | new (P8) |

## 6. Staged plan and verification

| Stage | When | Do | Verify (pass) |
|---|---|---|---|
| **S0 tonight (3 h)** | now | 1. `cad/interfaces.json` PR: add `lever_beta_deg: 75`, `crank_r: 60`; `cad/leg.py` shin lever and crank at β; `pose()` and `cadrig.js` unchanged in form (the pin moves with β). 2. `sim/model.py`: knee actuator = fixed tendon (hip 1, knee 1); report motor torques; knee armature on the tendon's DOFs (approximate on both joints until the closed loop lands). 3. `cad/studies.py`: P = T/(r sin φ) at the worst pose; add rod buckling + rod-end check. 4. `sim/scenarios.py`: `fall_front/back/side`, `kerb_drop_50`, `hop_landing`. 5. `build.py` cleans `exports/{view,links}` and stale `*.step`. 6. `pip install optuna`; fix `trial_eval` → run the loop (§8). | `min sin φ ≥ 0.5` over 48–155°; `stand` hip motor RMS ≈ knee RMS (≈11 N·m at 22 kg); no scenario asks > 60 N·m of either motor; rod force ≤ 2 kN; leaderboard filling by morning. |
| **S1 day 1–2** | frame + leg v2 in CAD | `build.py`: side plates, crossmembers, head plate, rear door; `leg.py`: tube links + fittings, shin fork, hub-as-adapter; yoke hat; guards and boots as envelopes. Weigh the J501 box, an RS-03 and a BotWheel if on hand; **check the RS-03 rear lug threads** (P3). Clash sweep with a 25 mm finger probe. | Made mass ≤ 3.8 kg; clash-free 48–155° with look-up; every finger gap ≥ 25 mm or ≤ 4 mm or guarded; model mass ≤ 19 kg. |
| **S2 day 2–3** | analysis set | FEA: thigh T1/T2 at the new loads, shin, fork, pin, crank, rod (buckling), plates, yoke hat, side plate (HM + head + fall), head plate (fall 30 g on 1.2 kg = 350 N at the corner), AO-L bolt group. Mesh 2 and 4 mm on the governing case. Cables re-checked (`cables.py`) with the lever in the loop plane. | Metal SF ≥ 2 on yield for the floor cases, ≥ 1.2 for the fall cases; wheel deflection ≤ 2 mm; mesh delta ≤ 10 %; cable clearance ≥ 5 mm. |
| **S3 day 3** | order | SCS: side plates, floor channel, crossmembers, door, head plate, yoke hats, shin feet, wheel adapters (one order, DXF/STEP). CNC: 4 plates, 2 cranks, 4 hubs, 2 forks (JLCCNC). Bearings, rod ends, tube, pins, inserts, glands, isolators (Amazon/McMaster, 1–2 days). Motors/wheels if not owned (CN, 1–3 weeks). Turret: servos, Snails, ESCs, M2006 + C610, laser, DT connectors. | Orders placed with the drawing rev in the filename; BOM in `exports/bom-mechanical.json` matches the carts. |
| **S4 day 4–7** | bench leg | While metal ships: print PET-CF stand-ins for plates and hubs; assemble one leg module on a bench plate with two RS-03s and a BotWheel; sweep the knee under a 10 kg hanging load; measure rod force with a strain-gauged rod (or a 2 kN load cell in series); run the wheel harness through the links over the range 1,000 cycles. | No dead point; rod force within 20 % of the sim at three poses; hip and knee currents match τ_hip = Q_hip − Q_knee within 15 %; no cable chafe. |
| **S5 week 2** | frame + robot | Metal arrives: assemble frame, legs, battery door, lidar, cameras, head plate. Power and CAN per D9; balance on a tether at 0.6 height; then push, drive, kerb; then a deliberate fall onto grass at full height with the turret mass dummy. | Stands 60 s; survives 0.35 N·s/kg push; 25 mm kerb at 0.6 m/s; fall: no plastic deformation, bumpers only, box isolators intact; battery swap < 15 s. |
| **S6 week 2, parallel** | turret bench | Print pan base/ring/yoke/cradle/cartridge; bench rig: flywheel RPM vs exit speed with the chronograph; dial feed 24 balls; interlocks (tilt-above-horizon kill, e-stop, dead-man); then on the head plate: slew while balancing (`recoil` scenario live). | ≤ 70 fps at 100 % throttle by wheel size alone; 24/24 fed, ≤ 1 jam, stall-reverse clears; mass ≤ 1.2 kg; pan ±170° with the loop intact after 1,000 cycles. |
| **S7 week 3** | calibrate the loop | Feed measured masses, stiffness (dial gauge at the wheel under 200 N) and motor currents back into the catalog and the FEA material/BC factors; retrain RL finalists on the corrected model. | Sim vs bench within 15 % on torques and 25 % on deflections. |

## 7. Simulator changes

### 7.1 Physics (`sim/model.py`, `sim/scenarios.py`)

| Change | How |
|---|---|
| Knee drive (A2) | **Level 1:** `<tendon><fixed name="knee_motor_l"><joint joint="hip_l" coef="1"/><joint joint="knee_l" coef="1"/></fixed></tendon>` + `<general tendon="knee_motor_l" ctrlrange="-60 60"/>`; the hip motor stays on `hip_l`. The controller converts its serial torques: ctrl_knee_motor = Q_k, ctrl_hip_motor = Q_h − Q_k; clip each to the RS-03 line. Armature of the knee rotor: put J_k on both hip and knee DOFs (upper bound) until Level 2. **Level 2:** crank body (hinge on the base at the hip axis, armature J_k, the knee actuator on it), rod body (hinge at the crank pin), `<equality><connect>` rod tip ↔ shin lever pin; the serial knee joint stays (passive). Rod force = the equality's `efc_force` → FEA. `leg.topology` selects `serial|tendon|closed`. |
| Collisions (C2) | Per-link convex hulls from `exports/links/*.stl` (decimate to ≤ 2k faces; `mesh` geoms, `contype 4`), motors as cylinders, lidar cylinder, turret boxes; the body hull from side plates + box + head plate. Legs may contact the body (`conaffinity` 1 | 4). |
| Mass properties (C3) | `build.py` writes mass, CoM, full inertia per link from the solids (`cadagent.robot` B-rep moments); bought parts as catalog mass at CAD positions (RS-03 as a cylinder with 35 % rotor); push-rod and crank on their own bodies in Level 2. |
| Joint limits (C4) | `clashes_for_design` sweeps hip × knee and writes limits to `mech-layout.json`; the model reads them. |
| Scenarios (A5, C5) | `fall_front`, `fall_back`, `fall_side` (torque off at t = 1 s from 0.6 and 1.0 height, log peak contact force per body and the first body to touch), `kerb_drop_50` (drive off a 50 mm step at 1 m/s), `hop_landing` (scripted 80 mm hop), `kick` (0.3 N·s/kg at the knee), `side_push`. Loads: add the rod equality force, the turret's `cfrc_int` (head plate), and the HM wrench (hip body `cfrc_int` already) to `link_loads`. |
| Motor thermal | I²t per motor: RMS torque over each run vs rated (20 N·m) → `of_rated_rms`; fail if > 0.7 for a 60 s run. |
| Turret (F4) | Mass/inertia/joint positions from the turret CAD; ball projectile (sphere 22.7 mm, 1.83 g, drag) at 21.3 m/s; pan limits ±2.97 rad; recoil 0.039 N·s. |

### 7.2 3D view (`designer/cadrig.js`, `sim.js`, `build.py`)

| Change | How |
|---|---|
| One kinematics (D1) | The run JSON carries per-frame body poses for every rig link (`base, thigh_l/r, shin_l/r, wheel_l/r, crank_l/r, rod_l/r, pan, tilt, cartridge`) as `xpos/xquat` (or qpos incl. the crank and rod hinges). `cadrig.js` only assigns transforms by link name; delete its crank/rod math. Live pose: the page asks a tiny MuJoCo-free FK in JS **generated** from the manifest (`joints` with axes/anchors), one implementation shared with `robot3d.js`. |
| Meshes per link (D2) | `build.py` writes `exports/links/<link>/*.stl` for every made and bought part incl. the frame, box, lidar, cameras, turret; `manifest.json` gains `joints`, `limits`, `interfaces`, `inertia`. The procedural robot is deleted from `sim.html`; any design's rig is built on demand by the loop (cache by design hash). |
| Turret from CAD (D3) | `links.pan`, `links.tilt`, `links.cartridge`; the laser origin and muzzle sites come from the manifest. |
| Hygiene (D4) | `build.py` wipes `exports/view`, `exports/links` and every `*.step` it does not write; commit the clean tree. |
| Overlays | Show the pinch probe result (red where a 25 mm gap closes), the lidar occlusion band, and the rod force colour in replays. |

## 8. Overnight iteration loop (tonight)

What exists: `tools/iterate.py` (Optuna TPE over actuator, link lengths, section sizes, yoke, crank) → `tools/trial_eval.py`
(designer → CAD `--fast` → clashes → sims → FEA → cables), `GYROPUP_EXPORTS` isolation per trial. Not yet: optuna is **not
installed** in `.venv`; the lever angle, frame and tendon model do not exist; the objective is single (mass). This machine
is 24 cores / RTX 3080 12 GB (`nproc`, `nvidia-smi`); scale `--workers` to the box it runs on (32-core / 4090: 28 workers).

| Item | Spec |
|---|---|
| Prerequisites (S0) | `pip install optuna`; P1 lever geometry and the tendon model in place; `trial_eval` stage `sims` also runs the fall/kerb/hop scenarios; `studies.py` adds rod/fork/pin/plate cases; `catalog/availability.json` drives the in-stock penalty (exists). |
| Design vector | Categorical: `leg_actuator` ∈ {RS-03, RS-04}, `bus` ∈ {2 × 20 V series (40 V), 1 × 60 V}, `battery_position` ∈ {tray, backpack}, `leg.topology` ∈ {tendon-parallelogram, knee-on-thigh}. Integer/float: `thigh_mm`, `shin_mm` ∈ [170, 240] step 10; `crank_r` ∈ [45, 70] step 5; `lever_beta_deg` ∈ [60, 90] step 5; `knee_min_deg` ∈ [42, 60]; `knee_max_deg` ∈ [140, 160]; `wheel_y_offset` ∈ [0, 30] (track); tube section ∈ {40×30×2, 40×30×1.5, 35×25×2}; `side_plate_t` ∈ {4.75, 6.35}; `plate_t` ∈ {6, 8}; `head_mass_g` ∈ {1000, 1500}; `head_com_mm` ∈ {80, 120}. |
| Constraints (reject) | designer `fail`; any clash; finger gap 4–25 mm unguarded; `min sin φ < 0.5`; tyre–knee-motor gap < 20 mm; any scenario fail (incl. falls: no body peak > 3 kN, lidar never touches); motor peak > 0.95 × 60 N·m; RMS > 0.7 × rated in `stand`; metal SF < 2 (floor) or < 1.2 (fall); wheel deflection > 2 mm; cable clearance < 5 mm; part not in stock. |
| Objectives (multi, NSGA-II) | minimise **model mass**, **cost**, **worst motor RMS/rated**, **−push impulse survived** (bisect 0.2–0.6 N·s/kg in `push`), **width**; report rod force, SF margins, runtime, lidar occlusion as attributes. |
| Per candidate | derive (0.1 s) → CAD fast (60–120 s) → clash (20 s) → 14 scenarios (≈ 60 s) → FEA 10 studies at 3.5 mm (≈ 3 min) → cables (10 s): **≈ 6 min / core**. 28 workers × 8 h ≈ **2,200 candidates**; staged rejection makes most cheaper. |
| Runner | `optuna.samplers.NSGAIISampler(seed)` on `work/iterate/study.db` (SQLite, WAL), one process per worker, `GYROPUP_EXPORTS=work/iterate/<trial>`; `--hours 8`; leaderboard every trial; a Pareto front JSON + the top-5 designs copied to `designs/candidates/`. |
| GPU | After 4 h, take the 3 Pareto leaders and train the mjlab velocity policy (`rl/train.py`, 1–2 h each on the GPU) with the tendon model; report tracking error and fall rate under 20/40 ms delay (`rl/scripts/sim2sim.py`). |
| Morning report | `exports/iterate/leaderboard.json` + `report.md`: Pareto plots (mass vs push, mass vs width), the best design's full metrics, which constraints killed most candidates, and the rod-force and hip-RMS histograms. |

## 9. Risks and open questions for the user

| # | Question / risk | Why it matters | Default if unanswered |
|---|---|---|---|
| Q1 | Bus voltage: revert to 2 × 20 V series (D23) or keep 1 × 60 V with an "arm below 58 V" rule? | RS-03 abs. max 60 V = a full pack (B7). | 2 × 20 V (the loop evaluates both). |
| Q2 | Do you own RS-03s and BotWheels yet? If so, measure the RS-03 rear lug threads and the real masses. | P3 hip mount; 22 kg vs 18 kg. | Hat bracket; catalog masses. |
| Q3 | Width: is 560–590 mm (632 overall) acceptable for doors and the car? | A4. | Yes; loop reports it. |
| Q4 | Charge contacts on the rear lower edge (P8) instead of under the tray? | B3. | Yes. |
| Q5 | Battery rear door vs backpack? | B2; CoM. | Rear door. |
| Q6 | Turret: STS3215 ring-gear pan (90°/s) accepted instead of the DM-J4310? | F1; −217 g, −$103. | Yes. |
| Q7 | Launcher ammo: Rival balls confirmed (study's recommendation awaiting your call)? | Cartridge design. | Balls; dart cartridge as the alternative. |
| Q8 | Which machine runs the loop tonight (this box is 24 cores / RTX 3080)? | Worker count. | 20 workers here. |
| R1 | Knee-on-thigh topology may beat the parallelogram on hip thermal load; the loop decides, but the CAD for it is not written. | S0/S1 scope. | Loop variant only in the sim. |
| R2 | FEA boundary conditions still idealise bolted joints; bench deflection (S4) is the real check. | E2. | Keep SF ≥ 2. |
| R3 | SendCutSend laser tolerance (±0.13 mm) for dowel holes and bearing seats. | Fit. | Ream dowels; CNC the bearing plates. |
| R4 | Printed PET-CF stand-ins for the plates (S4) are for kinematics only, not loads. | Safety on the bench. | Hang ≤ 10 kg. |
| R5 | IP43 in v1: no wet grass, no rain. | B6. | Rule in software + sticker. |
