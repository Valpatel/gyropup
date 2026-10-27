# Body plan (milestone M5): the body around two legs

Written 2026-10-27 by the body planner (Fable 5.1) for the user and for the Opus implementer who will work it. Not
committed. Sources read: docs/requirements.md, docs/decisions.yaml (D28-D41), docs/milestones.yaml,
docs/head-payload.md, docs/turret-plan.md, docs/mechanical-interfaces.md, sim/robot_v2.py, designer/robot_v2.js,
catalog/*.json, exports/leg/leg.json, bom.json and rig-results.json, build/sim/v2/model.json, cad/fivebar.py
(hip_frame, stack), cad/turret.py (TM pattern), cad/turret_box.py, research/power-electronics.md,
research/lfp-batteries.md, the RS-04 manual (references/vendor/robstride-rs-04), and the J501 project
(~/Code/j501-agx: README, cad/parameters.json, read only). Prices carry the date they were checked; "verify" means
the page was not read today (a research pass on those items was still running when this was written: see section 8).

Every "decide" below is decided here, as the user asked (D41: "You don't need to wait on anything for me"). Two of
them change the current sim default (designs/default.json) and are flagged as proposed decisions D42-D44 in section 7.

## 0. The plan in one paragraph

Build the body as an aluminium **spine box** between the two hip frames plus a **floor tray**, a **deck plate** and a
**belly plate**, all SendCutSend sheet (instant price), with printed PA6-CF posts, riser and cassette, and printed PETG
shell panels that carry nothing structural. The two hip frames bolt to the spine's cheeks with the six M5 inserts each
already has (cad/fivebar.py hip_frame), 42 mm apart, and the gap between the cheeks is the cable chase. The robot runs
on a **13S Li-ion bus (48.1 V nominal, charged to 4.10 V/cell = 53.3 V)** with a 100 A-class BMS: the one voltage that
keeps the RS-04s at the speed the jump needs (the rig's jump peaks at 16.7 rad/s at 60 N·m), stays under the RS-04's
60 V over-voltage fault with room for regen (so the $444 maxon clamp goes), and feeds the J501 through the catalogued
Mean Well DDR-120C-24. **The FLEXVOLT 60 V default (D25) cannot stay:** DeWalt's "60V MAX" is the pack's initial
no-load voltage, and the RS-04 manual sets its over-voltage fault at 60 V, so a fresh pack faults the leg motors
before the first regen pulse. The first physical prototype is the open frame with the battery, compute and power skid
and no shell, balancing on a tether; the shell follows.

## 1. Architecture

### 1.1 Structure

**What the legs give us.** Each hip module (cad/fivebar.py `hip_frame`, exports/leg/leg.json) is a printed PA6-CF
"C": a 24 mm web on the leg side holding both RS-04s on their lugs, and two 7 mm flanges (top and bottom, z = ±62 to
±69, x = ±95) that run inward over the motors to the module's centre plane (`Y['centre_plane']` = -82.3 mm from the AO
face). Six Ø14 bosses on the flange ends, at (x, z) = (0, ±67) and (±83, ±67), carry M5 heat-set inserts
(McMaster 94459A775) 11 mm deep, axis along y, facing the centre plane. That face is the only body interface the leg
offers; the motors' rear covers sit 2 mm behind it, and the RS-04 harnesses leave those covers radially, i.e. right at
the centre plane. The flanges reach only 2 mm above the Ø120 motors, so nothing can bolt down through them.

**Decision: a spine box between the frames, 42 mm wide.** Two frames cannot bolt to one plate: their bolt patterns
coincide (the right frame is the left one mirrored), so the heads collide. The spine is therefore one bent part with
two cheeks 36 mm apart; each frame bolts to its own cheek from inside the gap (6 × M5 × 16 button heads, 4 mm L-key or
stubby driver; the gap is open at both ends and at the top through the floor tray's centre slot). The frames' boss
faces then sit at robot y = ±21 mm, the track grows from 373.8 to **415.8 mm** (`Y_OFF` from -82.3 to -103.3), and the
gap doubles as the cable chase: the four RS-04 harnesses and the two wheel harnesses (through the frame's Ø18 pass at
x = 0, z = 0) enter the gap through windows in the cheeks and go up through the floor tray or down to the belly.

| Part | Material, process | Size (mm) | Carries | Est. mass |
|---|---|---|---|---|
| **Spine (hat channel)** | 5052-H32 3.2 mm (0.125 in), SendCutSend laser + 4 bends | web 36 × 300 at z = -76; cheeks 150 tall (z -76..+76); 20 mm lips turned out at the top under the floor tray | both hip modules (6 × M5 each), the floor tray on its lips, the belly plate under its web; cable windows |x| ≤ 20, |z| ≤ 25 in each cheek (clear of the frame's gusset at x = 0, z 28..62) | 0.45 kg |
| **Floor tray** | 5052-H32 3.2 mm, bent: 12 mm lips down all round | 280 × 254 at z = 76 (its underside), as the sim's shell floor | battery cassette, compute pallet, converters, MCU + IMU; bolts to the spine lips (6 × M5) and to the shell posts | 0.6 kg |
| **Deck plate** | 6061-T6 3.2 mm flat, pocketed | 280 × 254 at z = 216 (`TOP`, as the sim) | the lidar (1/4-20 at x = 88.35 + two Ø4.06 pin holes at x = 43.9 and 132.8, y = 0), the turret riser on the TM pattern at x = -54.65 (D41), the fan intake field inside the riser, the head harness grommet | 0.5 kg |
| **Belly plate** | 6061-T6 3.2 mm flat | 280 × 160 at z = -78, under the spine web | the two Flipsky 75100 VESCs (the plate is their heatsink, fins down), the anti-spark switch, the MRBF fuse block, the bus bars; a TPU skid rail each side | 0.35 kg |
| **Compute pallet** | 6061-T6 3.2 mm flat | 206 × 190 | the J501 carrier on 4 × M3 × 16 standoffs (holes at the PCB's (15, 16.5), (165, 16.5), (15, 146.5), (165, 146.5)), the cooler tie-down from below (4 × M3 × 35 flat heads through countersunk holes on the module's 92 × 79 pattern at PCB (44, 51)…(136, 130); the user's rule: the screws thread into the module-to-heatsink standoffs, 4 mm engagement); the pallet sits on 4 rubber isolators on the floor tray | 0.3 kg |
| **Corner posts** (4) | PA6-CF, printed | 24 × 24 × 140 with M5 inserts both ends, at (±128, ±115) | the deck's four corners; the side walls screw to them | 0.2 kg |
| **Turret riser** | PA6-CF, printed, 100 % solid | Ø144 ring, 30 mm tall, open sides | the turret base on the TM pattern (4 × M5 inserts on 80 × 80, dowels at (52, 0) and (0, -52), Ø45 hole); its open sides are the fan intake path | 0.15 kg |
| **Shell panels** | PETG 3 mm (side walls PA6-CF where the ears bolt on) | two sides 280 × 140, front and rear 254 × 140, a battery door in the right side | the ear pods, vents, eyes, cameras, button, ports; no structural load | 0.6 kg |
| **Belly box sides, skid** | PETG; TPU 95A skid rails | 280 × 160 × 60 | guards the VESCs and the power parts; the sit-down bumper | 0.2 kg |

Why sheet and not print for the frame (D33 says every made part is printed; D40 allows SendCutSend): the frame ties
two 9 kg legs together through twelve M5 bolts and carries 11 kg of body with the turret on top; a 300 mm printed box
flexes and creeps under the cooler clamp and the leg moments, and the first prototype needs to be stiff enough to tune
the balance loop against the simulation. Four laser-cut parts arrive in days at an instant price. The printed body of
M5's done_when ("a custom printed body") is the shell around this frame; a printed spine can be tried later on the same
hole pattern once the loads are measured.

**Load path and the FEA cases (task T5).** Per hip: the HM budget of 600 N and 80 N·m (docs/mechanical-interfaces.md)
and the rig's real peaks (exports/leg/rig-results.json): jump_peak hip joint forces 1.03 kN each (axle 2.38 kN), the
undamped power-off collapse 1.43 kN per hip joint, stop torque 97 N·m; the motors' 2 × 60 N·m reacted by the frame into
the cheeks as a couple on the top and bottom boss rows (0.9 kN fore-aft per row); the leg's out-of-plane load (the
sideways case, 120 N at the wheel). The deck: the turret's 0.05 N·s recoil, a 300 N hand load, 1.5 kg at 120 mm.
Targets: SF ≥ 2 on yield (6061-T6 240 MPa, 5052-H32 190 MPa), deck deflection ≤ 0.5 mm under 300 N, the frame's
twist between the two hip faces ≤ 0.1° under one leg's 80 N·m.

### 1.2 Battery

**Loads (standing, lights off):** 4 × RS-04 at ~10 W = 40 W; Orin AGX + J501 ~40 W (15-40 W module modes, 60 W system
max); VLP-16 8 W; 2 × D435 7 W; VESCs and wheels balancing ~10 W; MCU, IMU, BMS, eyes ~3 W: **~110 W**. Playing: plus
the turret's 40 W average (docs/head-payload.md) and the SSC1 pods 25.6 W: **~190 W**. Peaks: a jump is 4 motors at
60 N·m × 16.7 rad/s ≈ 1 kW each for ~0.2 s, plus the turret's 2.1 A ramped spin-up: ~4 kW, **~80 A at 48 V**.

**Why 48 V class and not 8S LiFePO4 (R23) or the FLEXVOLT (D25):**
- The rig's jump (exports/leg/rig-results.json) peaks at 16.67 rad/s at 60 N·m (jump_peak 17.69 rad/s at 120 N·m);
  the sim's RS-04 line gives 60 N·m up to about 160 rpm × V/48 V. At 8S LFP (25.6 V) that is 8.9 rad/s: no jump at
  all; stand, squat (1.0 rad/s) and balance are unaffected. At 13S (48.1 V nominal) it is 16.8 rad/s: the jump as
  simulated. Below ~45 V the jump shrinks and the controller should scale it with bus voltage.
- RS-04 manual (references/vendor/robstride-rs-04/RS04User_Manual260713.pdf): "Rated voltage 48 VDC; operating range
  24-60 VDC; maximum allowable voltage 60 VDC; overvoltage fault: the motor voltage exceeds the protection voltage of
  60 V; undervoltage fault below 12 V". DeWalt states that "60V MAX" is the maximum initial no-load voltage, so a fresh
  FLEXVOLT sits at 60 V: the RS-04s fault at power-on, and D25's 58 V shunt clamp would then dissipate across the pack
  until it bled down to 58 V. The Flipsky switch is rated 60 V and the MRBF block 58 V as well. One FLEXVOLT is also
  only 180 Wh (about 1 h here) with no discharge protection of its own.
- 12S (50.4 V full, 36 V empty) is the fallback: everything in rating, 10 % less jump, and WREKD sells a 12S2P pack
  at a listed price (below). 14S at 4.10 V/cell is 57.4 V, too close to 60 V with regen.

**Decision: 13S2P Molicel INR21700-P45B (or P50B), 48.1 V nominal, 9-10 Ah, 433-480 Wh, 2.0 kg with BMS, in a printed
PETG cassette.** Charged to 4.10 V/cell (53.3 V) by setting the BMS's cell OVP, so regen always has ≥ 1.9 V/cell of
headroom to the 4.25 V/cell cut and the bus stays under 57 V. Continuous 90 A (2 × 45 A), far above the 80 A jump
pulses. Runtime with 85 % of capacity usable (4.10 to 3.2 V/cell): about **1.9 h playing, 3 h standing**. A 13S1P
(216 Wh, 1.1 kg) is the light option if the mass budget bites; it still covers 1 h of play.

- **Primary pack:** built from 26 cells (18650batterystore.com or liionwholesale.com, about $5.50-6.50 each on
  2026-10-25 research, verify) spot-welded with 0.2 mm nickel (kWeld, or a Glitter 801D class welder, verify prices),
  a **JK (JiKong) JK-B2A24S15P smart BMS** (8-24S configurable, 150 A, 1 A active balance, Bluetooth + UART;
  about $110 on Amazon, verify) set to 13S, cell OVP 4.10 V, UVP 3.0 V, charge current 5 A, 0 °C charge block;
  XT90-S power lead, a 4-pin JST-XH for the BMS UART to the balance MCU, a 10 kΩ NTC on the cell block.
  Cassette: cells upright in a 4 × 7 footprint (86 × 150 mm) → cassette about 95 × 160 × 85 mm, a PETG shell with a
  PA6-CF rail, a latch, and the XT90-S on its end face.
- **Backup pack (no welding):** **WREKD 12S2P Molicel P50B**, 50.4 V full, 432 Wh, 120 A, 1.8 kg, 275 × 48 × 72 mm,
  $504 listed on wrekd.com (research/power-electronics.md, 2026-10-25; verify), no BMS: the robot's INA228 monitor
  does UVLO and an iCharger X12 ($179.99, 2026-10-25) balance-charges it. A 13S WREKD pack would be better if listed
  (verify).
- **Robot-side protection regardless of pack:** the 80 A MRBF main fuse, the anti-spark switch, an INA228 + 100 A
  shunt on the MCU (voltage, current, charge counting), firmware UVLO: warn 3.5 V/cell (45.5 V), sit and stop at
  3.2 V/cell (41.6 V), the BMS cuts at 3.0 V/cell (39 V). The DDR-120C-24's 33.6 V minimum is covered.

**Charging.** Off-robot on the bench with a standard 13S 54.6 V CC/CV e-bike charger (4-5 A, about $40-60 on Amazon,
verify); the BMS stops the charge at 4.10 V/cell, so the charger's 54.6 V is never reached. The dock (D18, R24) uses
the same principle: a sealed CC/CV supply (Mean Well HLG-320H-54A, output pot set to 53.3 V, verify price and adjust
range) feeding two spring contacts under the belly plate that the robot lands on when it sits; the robot closes a
charge relay only when it has recognised the dock, and the BMS does the rest. The dock is **TODO (next session)**.

**Swapping.** The cassette slides in through the right side door into a tray on the floor tray (front right, low),
latched; two cassettes make the robot continuous. The XT90-S has its own pre-charge resistor, so plugging in never
sparks even with the main switch left on.

### 1.3 Power distribution

```
pack (13S, XT90-S) ─ Flipsky anti-spark switch (soft start, 16 mm button on the rear) ─ MRBF 80 A ─ + bus bar
                                                                                           ├─ left leg: 2 × RS-04 (XT30 each, 10 AWG, MRBF 30 A)
                                                                                           ├─ right leg: 2 × RS-04 (same)
                                                                                           ├─ VESC L, VESC R (XT60, 12 AWG, MRBF 30 A each)
                                                                                           ├─ DDR-120C-24 → 24 V → J501 DC-IN (Phoenix MSTB 2-pin; polarity checked with a meter first, j501-agx README)
                                                                                           ├─ DDR-60L-24  → 24 V → turret DT12 pins 1-4 (≤ 2.5 A; the ramped spin-up is 2.1 A, the stepped one is forbidden on the robot)
                                                                                           ├─ DDR-60L-12  → 12 V → lidar interface box (9-18 V, 8 W, 3 A spin-up), SSC1 pods (2 A, PWM-dimmed by a low-side MOSFET), eye controller, Ethernet switch
                                                                                           └─ Pololu D42V55F5 (5-60 V in) → 5 V → balance MCU, VN-100, CAN boards, INA228, radio-stop receiver
 - bus bar ─ 100 A / 50 mV shunt ─ pack
```

- **Voltages:** bus 39-53.3 V (RS-04 24-60 V; Flipsky 75100 14-84 V; the anti-spark switch 12-60 V; MRBF 58 V max,
  so the bus must never exceed 57 V: the VESCs' max-input-voltage parameter at 57 V reduces regen above 55 V, and the
  13S charge rule keeps the resting pack at 53.3 V).
- **Why isolated DIN converters:** the DDR-120C-24 is already catalogued ($69.20, 2026-10-25, 33.6-67.2 V in, 120 W,
  180 W for 3 s) and keeps the Jetson's ground away from motor ground; the turret gets its own DDR-60L-24 (18-75 V in,
  60 W; verify ~$45) so a flywheel spin-up can never brown the Jetson out; the DDR-30L-12 of designs/default.json is too
  small once the pods (25.6 W) and the lidar (8 W, 3 A surge) share it, so it becomes the DDR-60L-12 (verify ~$40).
  The converters lie flat on the floor tray (125 mm tall standing would not fit the 140 mm interior); Mean Well rates
  the derating for vertical mounting, so they run at ≤ 80 % of rating: 60 W of 120, 48 W of 60, 36 W of 60.
- **Fusing:** MRBF (58 V DC) for the main (80 A) and each motor branch (30 A); the converter branches on DC-rated
  (≥ 60 V) 10 A fuses (verify the DC rating of the 5 × 20 mm ceramic series chosen; ATO blade fuses are 32 V parts and
  are not allowed on the bus). The turret base keeps its own 10 A blade fuse on its 24 V side.
- **Pre-charge:** the anti-spark switch's soft start charges the VESCs', RS-04s' and converters' input capacitors;
  the XT90-S covers hot-plugging the cassette.
- **No contactor, no e-stop button (D37):** the STOP input (radio stop, designed separately) tells the MCU to sit the
  robot down and disable torque; it may also drive the switch's OFF pin after the sit. Flipsky's and Pololu's own
  notes apply: a MOSFET switch is not a safety device.
- **Regen:** absorbed by the pack (the charge FET stays closed below 4.25 V/cell); the maxon DSR 70/30 is dropped.
  The first tethered tests put a scope on the bus during a hard brake from 2 m/s and a full squat to confirm it stays
  under 57 V (acceptance in T4/T9).

### 1.4 Controller, IMU, CAN

- **Balance MCU:** STM32G474 (3 × FDCAN, 170 MHz, FPU; D7's assumption stands). Primary board: **ST Nucleo-G474RE**
  (Digi-Key/Mouser, about $17, verify) or the catalogued WeAct core; backup: Teensy 4.1 (3 CAN, $31.70, verify).
  Three transceiver boards (Waveshare SN65HVD230, $4.99 2026-10-26; classic CAN 1 Mbit).
- **IMU:** the user's VN-100 Rugged (D6) on its 2 × M3 + 2 dowel pattern, flat on the floor tray next to the spine
  slot (x ≈ -20, y ≈ 0, 100 mm above the COM), read at 800 Hz over TTL serial; backup Adafruit ISM330DHCX (raw 6-DoF,
  $19.95, verify).
- **Loop:** the rig's virtual-model controller (sim/controller_v2.py) at 1 kHz: leg length and lean through the
  five-bar Jacobian, wheel torque for balance, the TPU stop springs; MIT-mode torque to the RS-04s, current mode to the
  VESCs. Start-up: switch on → the MCU waits for bus ≥ 39 V → enables motors → the Jetson commands stand-up.
- **CAN topology (the J501 has two isolated CAN-FD ports, can0/can1 on J25 pins 17-20 with switchable 120 Ω
  termination: research/power-electronics.md §4 from the Seeed schematic):**
  - Bus A (MCU FDCAN1, 1 Mbit classic): left leg RS-04 × 2 at 1 kHz (~0.5 Mbit/s); 120 Ω at the far motor's lead.
  - Bus B (FDCAN2): right leg RS-04 × 2, the same.
  - Bus C (FDCAN3): VESC L + VESC R at 500 Hz plus the J501 can0 (setpoints 100 Hz, state 200 Hz, 200 ms heartbeat);
    the J501's own termination is one end, the far VESC the other.
  - J501 can1: the turret's Feather M4 CAN (docs/turret-plan.md D3), the J501 terminating; the turret terminates its
    own end.
  - Motor-side CAN grounds tie to the J501's GND_ISO.
- **Jetson link protocol:** velocity, yaw rate, height, lean, "sit", "jump" in; pose, bus V/I, motor temperatures,
  faults out; heartbeat loss → balance in place for 2 s, then sit. Same for the STOP input.
- **Eyes and character:** the Waveshare DualEye on a QT Py ESP32-S3 (verify ~$12.50) over USB from the Jetson, off the
  balance loop (D16).

### 1.5 Head

As the user set it (2026-10-26) and the sim computes (build/sim/v2/model.json): the VLP-16 flush with the deck's front
edge (axis x = 88.35, pins fore and aft, cable exit +y), the turret's pan axis 143 mm behind it (x = -54.65) on the
**30 mm riser** (D41: 13.9° of depression facing forward over the lidar, 25° beyond ±56° of pan), its bumper ring
0.7 mm past the rear edge; the turret hides 84° of lidar azimuth behind the robot at pan 0. The ears are the two SSC1
pods on the side walls at the top front, their tops below the lidar's -15° beam (the sim's `ear_top`), aimed forward
with the bracket's tilt bolt; the DualEye alone on the face at z ≈ 166 (the sim's `eyes` mount); the front D435 in the
front wall at z ≈ 93, the rear D435 in the rear wall; nothing sticks out the front. The VLP-16's 3 m integrated cable
and its interface box (unpublished size; est. 90 × 60 × 35 mm, 0.35 kg with the coiled cable) need a 120 × 120 × 35 mm
zone under the deck at the front left: **a real volume the sim does not have; task T3 allots it.** The lidar's
Ethernet goes to the J501's 1GbE through a 12 V 5-port switch only if a second Ethernet device appears; otherwise
straight in.

### 1.6 Cooling

- **Orin:** 40 W module mode (60 W system max; J501 parameters.json thermal: TTP 80 °C limit, PETG wall limit 60 °C).
  The Seeed cooler's 8015 fan draws air down through its top grille and exhausts along the fin edges (±X of the
  carrier). The carrier mounts under the turret riser with the fan inside the riser's Ø144 footprint: the riser's open
  sides and a hex field in the deck under it are the intake (as cad/turret_box.py does on the J501 box); the exhaust
  leaves through louvres in the rear and side panels. The j501-agx CFD (tools/thermal.py, cadagent.cfd) is the check
  (task T6): plate ≤ 70 °C at 40 W in 25 °C air, fan intake within 3 K of the room (Rev 0.8 of the box reached 57 °C
  with the fan re-breathing 7 K warm air; the open riser should do better).
- **VESCs:** bolted flat to the belly plate (fins down in the moving air under the body); 100 A parts at ≤ 15 A.
- **RS-04s:** inside the hip frames between the flanges; the motors' rated 40 N·m is far above the 10-17 N·m standing
  load; the MCU reads their temperatures over CAN and derates at 70 °C.
- **Converters:** flat on the floor tray at ≤ 80 % load, with the side-wall vents above them.
- **Ear pods:** 12.8 W each in a die-cast housing: a vented printed cowl keeps the fins in free air and fingers off.

### 1.7 Kid safety

- **Pinch and crush points** (ISO 13854: ≥ 25 mm for fingers, ≥ 100 mm for hands; ISO 13857: ≤ 4 mm is closed):
  the knee scissor between each upper link and lower link; the V between the front link and the wheel link that
  closes toward the axle as the leg extends; the upper link landing on its stop post (1 kN at the post at 60 N·m);
  the wheel against the wheel link. Mitigations: the shell has no gap between 4 and 25 mm next to a moving part;
  TPU guards on the stop posts' approach; and a **people-near mode** (a person within 0.6 m in the lidar or depth
  cameras: legs hold their length, wheel speed ≤ 0.5 m/s, turret pan ≤ 100°/s, no jumps). **TODO (next session):**
  a hazard table per joint with the guard decided for each.
- **Hot surfaces:** nothing a child can touch above 48 °C on metal or 60 °C on plastic (IEC 62115 class limits, our
  margin): the motors and VESCs are enclosed; the exhaust air is ≤ 45 °C; the ear pods are dimmed to 50 % in
  people-near mode and measured on the prototype.
- **Battery:** BMS (OV, UV, OC, short, temperature, 0 °C charge block), the 80 A fuse, the 4.10 V/cell rule, a PETG
  cassette with the cells held off the shell, charging only through the BMS, the cassette removable for storage.
- **Turret:** its hard rules stand (barrel never above horizontal, ≤ 70 fps, the safety line held); the body's STOP
  loop is the line on DT12 pins 7-8.
- **Stops:** the robot sits before any planned power-off (R37); an unplanned cut is the legs' case (D39); the belly
  skid and the ear cowls are what it lands on.

### 1.8 Mass and centre of mass

| Group | Sim today (26.2 kg) | This plan | Change |
|---|---|---|---|
| Two legs incl. hip modules (exports/leg/bom.json) | 18.25 | 18.25 | – |
| Frame + shell (interim shell 1.4 + hardware 0.25) | 1.65 | spine 0.45, floor 0.6, deck 0.5, belly 0.35, pallet 0.3, posts 0.2, riser 0.15, shell 0.8, hardware 0.3 = 3.65 | +2.0 |
| Battery + adapter | 1.63 | 13S2P cassette 2.0 | +0.4 |
| Compute (Orin + carrier + cooler, no box) | 0.98 | 0.98 | – |
| Converters + clamp | 1.13 (DDR-120 0.51, DDR-30 0.12, maxon 0.5) | DDR-120C 0.51 + DDR-60L-24 0.21 + DDR-60L-12 0.21 + 5 V buck 0.02 = 0.95 | -0.2 |
| VESCs, switch, fuse, bus bars, boards | 0.71 | 0.95 (bus bars, shunt, INA, MCU, 3 CAN boards) | +0.2 |
| Cameras, eyes, lights | 0.47 | 0.47 | – |
| Harness | (in hardware) | 0.4 | +0.4 |
| Lidar + cable/box | 0.83 | 1.18 | +0.35 |
| Turret (base + pan + tilt) | 1.34 | 1.34 | – |
| **Total** | **26.2** | **~29.1** | **+2.9** |

That is 11 % over the mass the leg rig carries (13.1 kg per leg). **Budget: body + head ≤ 10.3 kg, robot ≤ 28.5 kg**
(trim: deck 3.2 → 2.5 mm pocketed, floor lips shorter, posts into the side walls, 13S1P if needed), and the rig is
re-run at a half mass of 14.25 kg (task T4) so the leg studies see the real load; if a leg part drops under SF 2
everyday, the leg workstream hears about it before anything is printed. Balance: with the battery front right low
(x ≈ +70), the compute under the riser (x ≈ -40), the converters rear left, the VESCs in the belly at x = 0, the lidar
at +88 and the turret at -55, the COM lands within ~3 mm of the axle fore-aft and ~1 mm sideways (hand estimate; T3
proves it from the CAD). Acceptance: |x_com| ≤ 10 mm, |y_com| ≤ 5 mm at the 300 mm stance; the COM height stays within
30 mm of today's -21 mm below the hip axis.

## 2. The simplest first body prototype, and the steps to the finished shell

**P0, the power skid (bench, no legs).** The belly plate with the switch, fuse block, bus bars, shunt and the two
VESCs; the floor tray with the converters, the MCU + IMU, the compute pallet; one battery cassette. Power up, check
every rail, run one RS-04 and one BotWheel from the MCU over CAN, the Jetson link over can0, UVLO and the STOP input.
Everything here is reused unchanged.

**P1, the open frame (first physical body).** The spine with both hip modules (from M3's build), the floor tray,
the deck plate on four posts, the belly plate, no shell. The compute pallet and the cassette drop in. The lidar and
a mass dummy for the turret on the deck (1.5 kg at 120 mm). The robot stands on a tether (a ceiling line or a gantry
with 0.3 m of slack) and runs the controller from sim; tests in order: stand up, hold, squat, drive 1 m/s, push
recovery, brake from 2 m/s with the scope on the bus, then the first jump. This is the robot that proves the balance
loop, the power system and the frame stiffness; nothing in it waits on a printed shell.

**P2, the head.** The riser and the real turret on the TM pattern, the DT12 harness, the lidar; the target-practice
scenario on the floor with the robot tethered, then untethered in a padded room.

**P3, the shell.** Side walls with the ears, the door, vents; the front face with the eyes and camera; the rear with
the camera, button, charge port and radio-stop jack; the belly box and skids; the thermal test at 40 W. Then the
dock.

Order of ordering (long poles first): the pack cells and BMS and the welder; the SendCutSend set (hat channel, floor
tray, deck, belly, pallet: one cart, 5052 bent parts and 6061 flat parts, verify current lead time); the Mean Well
converters; the Nucleo and CAN boards; the remaining connectors and McMaster hardware. Printing (posts, riser,
cassette, shell) runs in parallel.

## 3. Highly available components (primary and backup)

Prices: (c) = catalog/*.json with its `price_checked` date; (r) = research/*.md 2026-10-25; "verify" = not read
today. Every part is off the shelf, printed, or an instant-price custom part (D40).

| Function | Primary | Backup |
|---|---|---|
| Battery | 13S2P Molicel INR21700-P45B/P50B built pack, 26 cells ~$160 (verify at 18650batterystore.com / liionwholesale.com) in a printed cassette | WREKD 12S2P P50B, $504 listed (r, verify), 432 Wh, no BMS; or 13S1P of the same cells (1.1 kg) |
| BMS | JK JK-B2A24S15P, 8-24S, 150 A, 1 A active balance, BT + UART, ~$110 Amazon (verify) | Daly 13S 48 V 100 A smart (Amazon, verify); for the WREKD pack: no BMS, INA228 UVLO + iCharger X12 $179.99 (r) |
| Charger | 13S 54.6 V 5 A CC/CV e-bike charger, XT60, ~$50 Amazon (verify); the BMS stops at 4.10 V/cell | Mean Well HLG-320H-54A set to 53.3 V (dock supply; verify) |
| Main switch / pre-charge | Flipsky Antispark Switch Pro V3.0 alu case, 100 A, 12-60 V, $48 (c 2026-10-25) | XT90-S pre-charge connector + Blue Sea 6006 300 A battery switch (~$25, verify) |
| Main fuse | Blue Sea 5191 MRBF block $29.93 (c) + MRBF 80 A fuse (~$10, verify) | Blue Sea Class T block + 100 A fuse (verify) |
| Bus bars | 2 × Blue Sea 2301 150 A (verify ~$20 each) | printed PA6-CF block with M6 studs and ring terminals |
| Current monitor | Adafruit INA228 $14.95 (r) + 100 A / 50 mV shunt | Holybro PM07 (2-14S, 90 A) $43.99 (r) |
| 24 V for the J501 | Mean Well DDR-120C-24 $69.20 (c) | Mean Well SD-100C-24 (36-72 V, 100 W; verify ~$60) |
| 24 V for the turret | Mean Well DDR-60L-24 (18-75 V, 60 W; verify ~$45) | a second DDR-120C-24 |
| 12 V rail | Mean Well DDR-60L-12 (18-75 V, 60 W; verify ~$40) | Pololu D42V55F12 (5-60 V in) $47.95 (r) |
| 5 V rail | Pololu D42V55F5 (5-60 V in, 6 A) $47.95 (r) | Pololu D24V22F5 from the 12 V rail (verify) |
| Leg actuators | RobStride RS-04 $255 (c), Seeed | – (the leg's choice) |
| Wheels | ODrive BotWheel $134.50 per wheel in 2-packs (c) | – |
| Wheel drivers | Flipsky 75100 $65 (c, in stock) | ODrive Pro $229 (c note) or a Flipsky dual ESC ≥ 60 V (verify) |
| Balance MCU | ST Nucleo-G474RE, 3 × FDCAN (verify ~$17 Digi-Key/Mouser); or WeAct STM32G474 core (c, no price) | PJRC Teensy 4.1, 3 CAN, $31.70 (verify) |
| CAN transceivers | 3 × Waveshare SN65HVD230 board $4.99 (c 2026-10-26) | Adafruit CAN Pal (verify); for CAN-FD on bus C a TCAN332/MCP2562FD board (verify) |
| IMU | VectorNav VN-100 Rugged (user's; quote-only price, c) | Adafruit ISM330DHCX $19.95 (verify); BNO085 $24.95 (verify) |
| Compute | Seeed J501 $379 + AGX Orin 32 GB $900 + Seeed cooler $49 (c) | – |
| Depth cameras | 2 × RealSense D435 $375 (c, in stock; user has D415/D435) | D415 (user's) |
| Lidar | VLP-16 (user's; ~$4,000 list, c) | – |
| Lights | Diode Dynamics SSC1 Sport white pair $179.95 (c 2026-10-26, in stock) | Nilight/Auxbeam 2 in 18 W pods pair ~$25 Amazon (verify) |
| Eyes | Waveshare 0.71 in DualEye $15.99 (c) | 2 × Waveshare 1.28 in round GC9A01 (~$10 each, verify) |
| Eye controller | Adafruit QT Py ESP32-S3 (~$12.50, verify) | Raspberry Pi Pico 2 W (~$7, verify) |
| Turret electrics | per docs/turret-plan.md §5 (Feather M4 CAN $24.95, Pololu regulators, SparkFun ROB-13065 ring $27.95) | as there |
| Main connectors | XT90-S (pack), XT60 (VESCs), XT30 (RS-04 as shipped), TE DT12 set ~$25 (turret plan), Molex Micro-Fit 3.0 and JST-XH for signals, RP-SMA bulkheads × 4 (j501-agx), Phoenix MSTB 2,5/2-STF-5,08 for the J501 DC-IN | Anderson SB50 for the main (verify ~$10) |
| Frame sheet | SendCutSend: 5052-H32 0.125 in bent (spine, floor tray), 6061-T6 0.125 in flat (deck, belly, pallet); instant price (verify today's rules: bend limits, PEM M5 insertion, lead time) | Xometry / JLCCNC instant laser or CNC from the same STEP; McMaster 6061 0.125 in sheet cut by hand |
| Inserts and screws | McMaster: M5 94459A775 $0.27, M3 94459A140 $0.22, M8 94459A778 $0.65 (c hardware.json); 5/16-18 inserts for the pod feet (verify number); M5 × 16 button heads, M3 × 35 flat heads (j501-agx) | – |
| Printed | PA6-CF: posts, riser, cassette rail, ear bosses, side walls; PETG: shell panels, cassette, belly sides; TPU 95A: skids, guards | – |

Radio stop (D37, designed separately): the body provides a 4-pin rear receptacle (STOP_A/B dry loop, closed = run,
+12 V, GND) and a 30 × 50 mm bay beside the rear antenna bulkheads; an ELRS receiver (RadioMaster RP1 class, verify)
driving a Pololu RC switch with relay #2804 ($19.95, r) is the simplest non-rated version; FORT Robotics is the rated
one (quote only, so not under D40).

## 4. Interfaces to freeze now

With the **leg** workstream (cad/fivebar.py, sim/leg_rig.py):

1. **Hip frame to body:** the six M5 inserts per frame at the centre-plane face, (x, z) = (0, ±67), (±83, ±67), bosses
   Ø14, inserts 11 mm deep, the six boss faces and the two flange end faces flat and coplanar within ±0.2 mm (a print
   requirement). The body side is a 3.2 mm 5052 cheek per frame; M5 × 16 button heads, 3 N·m. Loads as section 1.1.
2. **Spacing and track:** the frames' centre-plane faces at robot y = ±21 mm (`SPINE_W` = 42 mm); track 415.8 mm;
   `Y_OFF` = -103.3 mm. The sim, the designer and the CAD read it from one constant.
3. **Harness exit:** the RS-04 leads leave the rear covers into the spine gap through cheek windows |x| ≤ 20,
   |z| ≤ 25; the leg keeps that zone free between the motors' rear covers and the centre plane (the gusset at x = 0,
   z 28..62 stays). The wheel harness uses the frame's Ø18 pass at (0, 0) and runs inward to the gap.
4. **Sweep envelope near the body** (robot frame, both sides): upper links |y| 103.3..133.3, reaching z ≤ +31
   (the +3° stop plus half a link width) within |x| ≤ 225; front links |y| 135..155; wheel links |y| 157..183; tyres
   |y| 185.6..230.2; the stop posts stand on the frame's outer face at (±114, 42.9) and (±29.5, -36). So: the body
   shell above z = +35 may be full width (±130); below that, and the whole belly, stays within |y| < 100 and the hip
   frames' own envelope; the belly bottom at z ≥ -138 (50 mm of ground clearance at the leg's 101.5 mm minimum).
5. **Mass:** the body + head budget 10.3 kg; the rig re-run at 14.25 kg per leg is the leg's acceptance for it.

With the **turret** workstream (cad/turret.py, docs/turret-plan.md):

6. **TM on the head:** the 30 mm riser's top face is the TM face at (x, z) = (-54.65, 246) in the robot frame (deck
   `TOP` 216 + 30), 4 × M5 inserts on 80 × 80, dowels Ø5 at (52, 0) and (0, -52) in the turret's frame, Ø45 hole;
   the turret's Ø144 foot and Ø172 bumper ring; the body's rear edge stays at x = -140 so the ring's 0.7 mm overhang
   holds; depression table per D41 (13.9° forward, 25° beyond ±56° pan) regenerated by cad/turret_lidar.py for the
   riser.
7. **DT12:** the body carries the DT06-12SA plug on a 300 mm pigtail from a deck grommet behind the riser, wired per
   docs/turret-plan.md §2.3: pins 1-2 +24 V from the body's DDR-60L-24 (≤ 2.5 A; ramped spin-up only), 3-4 GND,
   5-6 CAN to the J501's can1 (the J501 terminates), 7-8 the body's STOP loop (closed = run), 11 LINE_SENSE 24 V.
8. **Cable routes on the deck:** the lidar's cable leaves at +y and drops through a grommet at (88, 95); the turret's
   harness drops behind the riser at (-130, 0); nothing crosses the fan intake field inside the riser.

With the **J501** (read only, ~/Code/j501-agx cad/parameters.json): the carrier's 4 × M3 mount holes and the module's
92 × 79 tie-down pattern, the cooler 100 × 87 × 34 at PCB (90, 90.5) with ≥ 10 mm above it, the 6.5 mm of parts below
the PCB (16 mm standoffs if the underside cards are fitted), DC-IN 24 V on the Phoenix plug, can0 to the MCU, can1 to
the turret, the four RP-SMA bulkheads in the body's rear panel, pin access to the REC/RST buttons through the side
door.

## 5. The ordered task list for the Opus implementer

Estimates are working days for one agent; "sim time" means waiting on MuJoCo or FEA runs. New CAD goes in
`cad/body_*.py`; exports in `exports/body/`. Nothing in cad/fivebar.py or cad/turret.py changes without the owning
workstream.

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| T1 | **Body parameters.** One module holding every number above (`SPINE_W` 42, `TOP` 216, plate thicknesses, post positions, the riser), reading the frame insert pattern from `fivebar.hip_frame`'s constants, the TM pattern from `turret.TM_BOLTS/TM_DOWELS/TM_HOLE`, the J501 holes from `~/Code/j501-agx/cad/parameters.json` (`J501_DIR` as cad/turret_box.py does), the VLP-16 pattern from catalog/sensors_compute.json: nothing retyped | `cad/body_params.py`, a test in `cad/test_body.py` | the test asserts the three patterns match their sources; the track and `Y_OFF` print from the constant | 0.5 |
| T2 | **Frame CAD.** Hat-channel spine (folded solid + a DXF flat pattern with SendCutSend's K-factor and bend reliefs), floor tray, deck plate, belly plate, compute pallet, posts, riser; STEP + DXF per part with material and thickness in the filename; a clash sweep of the frame against both hip modules and the legs over 101.5-392 mm and ±20° lean (reuse `fivebar.clashes` with the body solids added) | `cad/body_frame.py`, `cad/build_body.py`, `exports/body/` | zero clashes; every sheet part passes SendCutSend's rules (holes ≥ thickness, webs ≥ 2 t, bend relief, flange ≥ the minimum); each printed part fits the 256 mm bed; pictures as cad/build_leg.py makes them | 2 |
| T3 | **Layout, mass, COM.** Every bought part as its real envelope (catalog dimensions, STEP where it exists: DDR-120 and DDR-30/60, VN-100, D435, DualEye, 75100 from the drawing), the cassette, the lidar cable zone, cable chases; a `check_layout` overlap test as sim/robot_v2.py has; a mass table against the 10.3 kg budget; the COM | `cad/body_layout.py`, `exports/body/mass.json` | no overlaps; body + head ≤ 10.3 kg; |x_com| ≤ 10 mm, |y_com| ≤ 5 mm at 300 mm; every mass sourced or marked estimate | 1.5 |
| T4 | **Sim on the real body.** Replace the interim shell in sim/robot_v2.py with the T2/T3 solids and masses, `Y_OFF` from `SPINE_W`, collision shapes for the belly and ears; `BUS_V` 48.1 in sim/leg_rig.py and robot_v2.py; the rig at `--half-mass 14.25`; the thirteen scenarios in exports/sim/v2 | `sim/robot_v2.py`, `sim/leg_rig.py`, `exports/sim/v2/`, `exports/leg/rig-results.json` | every scenario passes; jump height ≥ 85 % of the 54 V figure (279 → ≥ 237 mm); the leg studies re-run on the new rig loads with no part under SF 2 everyday / 1.2 rare (else a note to the leg workstream) | 1 + sim time |
| T5 | **Electrical BOM and harness.** catalog entries for the pack, BMS, charger, converters, bus bars, shunt, connectors, Nucleo and CAN boards (price, link, date, dimensions, mass); designs/default.json moved to the 13S pack with the maxon clamp and the FLEXVOLT parts removed; the harness table (every conductor: gauge, length, connector, route) and the CAN map; the fuse list with DC ratings | `catalog/power_electronics.json`, `designs/default.json`, `docs/body-electrical.md` | every line priced and linked with a date; the budget table of section 1.3 reproduced from the catalog; no part needs a quote | 1 |
| T6 | **Frame strength.** FEA (cadagent.fea, as cad/leg_studies.py) of the spine and floor tray under the jump_peak and power_off hip reactions from rig-results.json and the 80 N·m out-of-plane case; the deck under 300 N and the turret's load; the belly under 3 g; overload videos as R43 asks | `cad/body_studies.py`, `exports/body/fea/` | SF ≥ 2 on yield for every sheet part, deck deflection ≤ 0.5 mm, hip-face twist ≤ 0.1°; the insert pull-out assumption flagged until M3's coupon test | 1.5 + sim time |
| T7 | **Shell and thermal.** Side walls with the ear bosses and cowls, the door, vents; front face (eyes, camera), rear (camera, button, charge port, radio-stop jack, RP-SMA × 4); the fan intake field and the riser's open sides; the J501 CFD at 40 W with the body around it (j501-agx tools/thermal.py) | `cad/body_shell.py`, `exports/body/thermal/` | plate ≤ 70 °C at 40 W in 25 °C air, intake within 3 K of the room; no shell gap between 4 and 25 mm beside a moving part; the ears below the lidar's -15° beam | 3 + sim time |
| T8 | **Build pack: order list, print plan, assembly, test plan.** The SendCutSend cart (DXFs, material, thickness, quantity), McMaster list with numbers (tools/mcmaster_cad.py one at a time), electronics list, print plan; the assembly order for P0-P3; the test plan with pass numbers (rails, CAN, UVLO, STOP, bus voltage during braking ≤ 57 V, stand/squat/drive/push/jump on the tether) | `docs/body-assembly.md`, `exports/body/bom.json`, `exports/body/print-plan.json` | every part orderable today; the progress page shows the body like the leg | 1 |
| T9 | **Firmware skeleton** (after the rig hardware exists): G474 with 3 × FDCAN, VN-100 at 800 Hz, the 1 kHz VMC loop ported from sim/controller_v2.py, the Jetson protocol, STOP, UVLO, people-near mode hooks | `firmware/balance/` | one RS-04 and one BotWheel closed-loop on the bench; a HIL replay of the sim's stand_up within 5 % | 3 |
| T10 | **Dock** (D18): contacts under the belly, the fiducial, the HLG supply, the charge relay; **TODO (next session)** | | | |

## 6. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Jump needs the bus above ~45 V; near empty the legs slow | smaller hops late in a charge | the controller scales jump height with bus voltage; 13S2P keeps the voltage up under load |
| Regen on a full pack reaches the RS-04's 60 V fault or the MRBF's 58 V | motors fault mid-brake | charge rule 4.10 V/cell, VESC max-input 57 V, bus scope test in P1; a brake-resistor module is the fallback if the test fails |
| Mass creep (+2.9 kg over the sim) | leg margins shrink | the 10.3 kg budget, T3's table, T4's rig re-run and leg studies at 14.25 kg |
| Twelve M5 inserts in printed PA6-CF carry the body | insert pull-out unmeasured | M3's coupon test (torque, pull-out), the cheeks bearing on the flange ends, T6's FEA; fallback: a through-bolted frame revision agreed with the leg workstream |
| A self-welded pack | quality, kid safety | the JK BMS's protections, a capacity and IR test before first use, the WREKD pack as the no-welding option |
| The Orin's fan inside a shell | throttling at 40 W | the open riser intake and louvres, the CFD in T7, a temperature log on the robot |
| Knee and stop-post pinch points | a child's finger | people-near mode, guards, the hazard table (TODO) before any kid session |
| The VLP-16's 3 m cable and interface box | 0.35 kg and a 120 × 120 × 35 mm volume the sim lacks | allotted in T3 |
| Flat-mounted DIN converters | derating not rated by Mean Well | ≤ 80 % load, vents above them, a temperature check in P0 |

## 7. Proposed decisions for docs/decisions.yaml (the user records them)

- **D42 (proposed): the bus is 13S Li-ion, 48.1 V nominal, charged to 4.10 V/cell; the FLEXVOLT 60 V default and
  the maxon regen clamp are dropped.** Why: the RS-04's 60 V over-voltage fault against DeWalt's 60 V initial voltage;
  the rig's jump speed; 180 Wh; no pack protection. The user's packs stay useful on the bench and for the turret stand.
- **D43 (proposed): the body frame is SendCutSend sheet (a bent 5052 spine and floor tray, flat 6061 deck, belly and
  pallet) with printed posts, riser, cassette and shell;** the hip frames bolt to the spine's cheeks with their six
  inserts, 42 mm apart (track 415.8 mm).
- **D44 (proposed): the turret's 24 V comes from its own DDR-60L-24 and its CAN from the J501's can1;** the stepped
  flywheel spin-up is forbidden on the robot (the ramped 2.1 A is the design point).

## 8. Open items and TODO (next session)

- Verify today's prices and stock for every "verify" row in section 3 (a research pass on cells, BMS, chargers,
  converters, Nucleo, lights, eyes, SendCutSend's current rules, the J501's CAN count from the wiki and the BotWheel
  stock was still running when this was written; fold its results into the table and catalog entries in T5).
- The DC rating of the converter-branch fuses; the exact 5/16-18 insert for the SSC1 feet; the VLP-16 interface box's
  size and mass (measure the user's unit).
- The per-joint hazard table and the guards (section 1.7); the dock (T10); the people-near mode's sensor logic.
- Whether the user's own CAN microcontrollers (D7) replace the Nucleo; which FLEXVOLT packs he has (for the bench).
