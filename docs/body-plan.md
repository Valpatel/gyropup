# Body plan (milestone M5): the body around two legs

Written 2026-10-27 by the body planner (Fable 5.1) for the user and for the Opus implementer who will work it.
Sources read: docs/requirements.md, docs/decisions.yaml (D28-D41), docs/milestones.yaml, docs/head-payload.md,
docs/turret-plan.md, docs/mechanical-interfaces.md, docs/cad-plan.md, sim/robot_v2.py, sim/leg_rig.py,
designer/robot_v2.js, catalog/*.json, exports/leg/leg.json, bom.json and rig-results.json, build/sim/v2/model.json,
cad/fivebar.py (hip_frame, stack), cad/turret.py (the TM pattern), cad/turret_box.py, research/power-electronics.md,
research/lfp-batteries.md, the RS-04 manual (references/vendor/robstride-rs-04), the Mean Well DDR-60 datasheet and
the Littelfuse KLKD page (2026-10-27), and the J501 project (~/Code/j501-agx: README, cad/parameters.json; read only).
Prices carry the date they were checked; "verify" means the page was not read today. Section 9 lists what is still
to verify.

Every "decide" below is decided here, as the user asked (D41: "You don't need to wait on anything for me"). Three
of them change the current sim default (designs/default.json); they are written up as proposed decisions D42-D44 in
section 7 for the user to record.

## 0. The plan in one paragraph

Build the body as an aluminium **spine box** between the two hip frames plus a **floor tray**, a **deck plate** and a
**belly plate**, all SendCutSend sheet at an instant price, with printed PA6-CF posts, riser and battery cassette and
printed PETG shell panels that carry nothing structural. The two hip frames bolt to the spine's cheeks with the six
M5 inserts each already has (cad/fivebar.py `hip_frame`), 42 mm apart; the gap between the cheeks is the cable chase.
The body is 320 × 260 × 140 mm over the hips (the sim's 280 mm interim shell cannot hold the J501 carrier, the battery
and the 24 V converter side by side; section 1.9 lays it out). The robot runs on a **13S Li-ion bus (48.1 V nominal,
charged to 4.10 V/cell = 53.3 V)** with a 100 A-class BMS: the one voltage that keeps the RS-04s at the speed the
jump needs (the rig's jump peaks at 16.7 rad/s at 60 N·m), stays under the RS-04's 60 V over-voltage fault with room
for regen (so the $444 maxon clamp goes), and feeds the J501 and the turret through the catalogued Mean Well
DDR-120C-24. **The FLEXVOLT 60 V default (D25) cannot stay:** DeWalt's "60V MAX" is the pack's initial no-load
voltage, and the RS-04 manual sets its over-voltage fault at 60 V, so a fresh pack faults the leg motors before the
first regen pulse. The first physical prototype is the open frame with the battery, compute and power skid and no
shell, balancing on a tether; the shell follows.

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
two cheeks 36 mm apart; each frame bolts to its own cheek from inside the gap (6 × M5 × 16 button heads, a 4 mm
L-key or a stubby driver; the gap is open at both ends and at the top through the floor tray's centre slot). The
frames' boss faces then sit at robot y = ±21 mm, the track grows from 373.8 to **415.8 mm** (`Y_OFF` from -82.3 to
-103.3), and the gap doubles as the cable chase: the four RS-04 harnesses and the two wheel harnesses (through the
frame's Ø18 pass at x = 0, z = 0) enter the gap through windows in the cheeks and go up through the floor tray's slot
or down to the belly.

| Part | Material, process | Size (mm) | Carries | Est. mass |
|---|---|---|---|---|
| **Spine (hat channel)** | 5052-H32 0.125 in (3.18 mm), SendCutSend laser + 4 bends, PEM nuts SS-M5-0 pressed into the lips and web | web 36 × 300 at z = -76; cheeks 150 tall (z -76..+76); 15 mm lips turned out at the top under the floor tray (SendCutSend's minimum flange after a 90° bend in 0.125 in 5052 is 0.476 in = 12.1 mm) | both hip modules (6 × M5 each), the floor tray on its lips, the belly plate under its web; cable windows |x| ≤ 20, |z| ≤ 25 in each cheek (clear of the frame's gusset at x = 0, z 28..62), every cut feature ≥ 8 mm (half the 0.630 in die) from a bend centreline | 0.45 kg |
| **Floor tray** | 5052-H32 0.100 in (2.54 mm), bent: 15 mm lips down all round; a 36 × 100 centre slot over the spine gap; PEM SS-M5-0 nuts where the posts and the spine lips bolt | 320 × 254, underside at z = 76 (the sim's shell floor) | the battery cassette, the compute pallet on 4 rubber isolators, the DDR-120C-24, the VN-100; bolts to the spine lips (6 × M5) and to the posts | 0.6 kg |
| **Deck plate** | 6061-T6 0.100 in flat, pocketed; black Type II anodize optional (+1-3 days) | 320 × 254 at z = 216 (`TOP`, as the sim) | the lidar (1/4-20 at x = 108.35 plus two Ø4.06 pin holes at x = 63.9 and 152.8, y = 0), the turret riser on the TM pattern at x = -34.65, the fan intake hex field inside the riser (10 mm cells: fingers stay out), the head harness grommet, the board shelf's standoffs | 0.45 kg |
| **Belly plate** | 6061-T6 0.100 in flat | 320 × 160, top face at z = -78, under the spine web | the two Flipsky 75100 VESCs (the plate is their heatsink, fins down), the anti-spark switch, the MRBF block, the two bus bars, the branch fuse holders, the shunt, the DDR-60L-12; a TPU skid rail each side | 0.35 kg |
| **Compute pallet** | 6061-T6 0.125 in flat with SendCutSend 90° countersinks (they countersink only ≥ 0.125 in) | 206 × 190 | the J501 carrier on 4 × M3 × 16 standoffs (PCB holes (15, 16.5), (165, 16.5), (15, 146.5), (165, 146.5)) and the cooler tie-down from below (4 × M3 × 35 flat heads on the module's 92 × 79 pattern at PCB (44, 51)…(136, 130); the user's rule: the screws thread 4 mm into the module-to-heatsink standoffs) | 0.3 kg |
| **Corner posts** (4) | PA6-CF, printed | 24 × 24 × 140 with M5 inserts both ends, at (±148, ±115) | the deck's corners; the side walls screw to them | 0.2 kg |
| **Turret riser** | PA6-CF, printed, 100 % solid | Ø144 ring, 30 mm tall, four legs with open sides | the turret base on the TM pattern (4 × M5 inserts on 80 × 80, dowels at (52, 0) and (0, -52), Ø45 hole); the open sides are the fan's intake path | 0.15 kg |
| **Battery cassette** | PETG shell, PA6-CF rail and latch | 95 × 160 × 85 | 13S2P cells, the BMS, the XT90-S lead | 0.25 kg (in the pack's 2.0) |
| **Shell panels** | PETG 3 mm (side walls PA6-CF where the ears and the port windows are) | two sides 320 × 140, front and rear 254 × 140, a battery door in the right side, port hatches both sides | the ear pods, vents, eyes, cameras, antennas, radio-stop jack; no structural load | 0.7 kg |
| **Belly box sides, skid** | PETG; TPU 95A skids | 320 × 160 × 60 | guards the VESCs and power parts; the button and the charge port on its rear face; the sit-down bumper | 0.25 kg |

Why sheet and not print for the frame (D33 says every made part is printed; D40 allows SendCutSend): the frame ties
two 9 kg legs together through twelve M5 bolts and carries about 10 kg of body with the turret on top; a 320 mm
printed box flexes and creeps under the cooler clamp and the leg moments, and the first prototype has to be stiff so
the balance loop can be tuned against the simulation. Five laser-cut parts arrive in days at an instant price. The
printed body of M5's done_when ("a custom printed body") is the shell around this frame; a printed spine can be tried
later on the same hole pattern once the loads are measured.

SendCutSend's rules, read 2026-10-27 (sendcutsend.com/materials, /services/cnc-bending, /services/hardware,
/services/countersinking, /faq): 6061-T6 is cut in 0.040-0.750 in but **not bent**; 5052-H32 is bent in
0.040-0.250 in. For 0.125 in 5052: K-factor 0.44, effective radius 0.125 in at 90°, die width 0.630 in, minimum
flange 0.476 in after the bend, maximum bend length 44 in, no custom radii, no angle sharper than 130° or flatter
than 5°, cut features at least half the die width from a bend centreline. Flat parts: instant quote up to
30 × 44 in; minimum 0.25 × 0.375 in. Hardware insertion: press-fit nuts S-M3-0, S-M4-0, SS-M5-0, S-M6-0 and M3/M4/M5
standoffs in aluminium 0.040-0.500 in ("starts at $9 per order, many fasteners under $1"); tapping M2-M10 up to 3 ×
diameter deep; countersinking 90° metric M2-M8 only in ≥ 0.125 in stock. Production: sheet 2-4 business days, bending
+1-2, hardware +1-3, countersinking +1-2, anodizing +1-7; no minimum quantity; free US shipping over $39. So the bent
parts are 5052, the flat parts 6061, the pallet is 0.125 in for its countersinks, and the whole set ships in about a
week.

**Load path and the FEA cases (task T6).** Per hip: the HM budget of 600 N and 80 N·m (docs/mechanical-interfaces.md)
and the rig's real peaks (exports/leg/rig-results.json, 13.1 kg per leg): jump_peak hip joint forces 1.03 kN each
(axle 2.38 kN), the undamped power-off collapse 1.43 kN per hip joint, the stop torque 97 N·m; the motors' 2 × 60 N·m
reacted by the frame into the cheeks as a couple on the top and bottom boss rows (0.9 kN fore-aft per row); the leg's
out-of-plane load (120 N sideways at the wheel). The deck: the turret's 0.05 N·s recoil, a 300 N hand load, 1.5 kg at
120 mm. Targets: SF ≥ 2 on yield (6061-T6 240 MPa, 5052-H32 190 MPa), deck deflection ≤ 0.5 mm under 300 N, the
frame's twist between the two hip faces ≤ 0.1° under one leg's 80 N·m. The twelve inserts are the one unmeasured link
(M3's coupon test measures an M5 insert's pull-out in printed PA6-CF): the cheeks also bear on the flanges' end faces,
so the bolts see mostly shear and the bottom row's tension in a landing (≤ 0.45 kN per bolt at 2.5 kN per leg).

### 1.2 Battery (D65, replacing D43/D54: rewritten 2026-10-27)

**Loads (standing, lights off):** 4 × RS-04 at ~10 W = 40 W; Orin AGX + J501 ~40 W (15-40 W module modes, 60 W
system max); VLP-16 8 W; 2 × D435 7 W; VESCs and wheels balancing ~10 W; MCU, IMU, eyes ~3 W: **~110 W**. Playing:
plus the turret (D66: its own robot on a bus branch, ~40 W average, flywheel bursts to ~140 W) and the SSC1 pods
25.6 W: **~190 W**. Peaks: a jump's push draws about 70 A for 0.3 s (the leg rig's HIL at 16.25 kg a leg).

**Decision (D65, the user's): two DeWalt DCB609 FLEXVOLT 9.0 Ah packs in 20 V mode, in series: 10S3P, 36 V nominal,
41 V full, 30 V empty, 360 Wh rated, 3.1 kg (DeWalt US: 3.45 lb a pack).** Each pack slides onto an off-the-shelf
rail adapter (Terrafirma Technology, 10 AWG leads, 30 A stated, no fuse or switch; $64.00 the four on Amazon,
B07HYJ628S). 60 V mode is ruled out: a fresh pack sits at the RS-04's 60 V over-voltage fault. One pack (18 V) is
under the RS-04's 24 V.

- **Where:** the battery bay under the belly plate, between the knees (cad/body_battery.py; docs/body-sections.md 1):
  the packs hang from their adapters on printed plates as from a tool, rails along x, the front one slides out of the
  front door and the rear one out of the rear, each door on two knurled M3 thumbscrews (tool-free). The bay is a
  SendCutSend 0.063 in floor and sides on printed rails, TPU skids on VHB under it: 318 × 102 × 132 mm, its bottom at
  z -224.6. The robot sits on the skids under a 139 mm leg; the controller's lowest height is 160 mm (21 mm off the
  floor). A pack's 97 mm height is why the bay is 64 mm deeper than the 13S2P brick's.
- **Protection is the robot's own** (the packs talk to nothing): the firmware's windows (docs/body-firmware.md 5):
  warn 35.0 V, no jump under 34.0 V resting, sit 32.0 V, a latched cut-off at 30.0 V under load (3.0 V a cell); the bus
  current limited to 30 A (1 s) and 80 A (0.5 s); regen clamped over 41.5 V; latched off over 44.0 V; no arming over
  42.0 V. The MRBF 80 A main fuse and the anti-spark switch stay (D55).
- **The jump** (the leg rig's HIL with the firmware's current-limited push): 199 mm on a full pair (41 V), 150 mm at
  36 V, 104 mm at 34.1 V, refused under 34 V; the 13S pack gave 245/231 mm.
- **Charging:** the packs come out and charge on DeWalt's chargers; the robot has no charge port. The dock (D18, D64)
  as planned charged the pack through pads in the tub's floor; with tool packs it is overtaken (docs/body-next-plan.md 9).
- **Converters:** the DDR-120C-24 starts at 33.6 V, inside the 10S range, so one TRACO TEP 150-4812WI (18-75 V in,
  isolated, 12 V 12.5 A) feeds the J501 (12-36 V in) and the 12 V rail in place of the DDR-120C-24 and DDR-60L-12.
- **Mass:** the battery group is 3.27 kg against the brick's 1.54: the P3 ledger is 1.8 kg over the 32.0 kg gate
  (D57); where the mass comes from is open (docs/body-sections.md 6, issue #10).

### 1.3 Power distribution

```
pack (13S, XT90-S) ─ Flipsky anti-spark switch (soft start; 16 mm button on the belly's rear face) ─ MRBF 80 A ─ + bus bar
   ├─ gPV 20 A × 4 ─ each RS-04 (XT30 as shipped; 10 AWG trunk to the chase)
   ├─ gPV 30 A × 2 ─ VESC L, VESC R (XT60, 12 AWG)
   ├─ gPV 5 A ─ DDR-120C-24 → 24 V → J501 DC-IN (Phoenix MSTB 2-pin; polarity checked with a meter first: j501-agx README)
   │                             └→ gPV 5 A (24 V side) → turret DT12 pins 1-4 (≤ 2.5 A; the ramped spin-up is 2.1 A; the stepped one is forbidden on the robot)
   ├─ gPV 3 A ─ DDR-60L-12 → 12 V → lidar interface box (9-18 V, 8 W, 3 A spin-up), SSC1 pods (2 A, PWM-dimmed by a low-side MOSFET), eye controller
   └─ gPV 2 A ─ Mean Well DDR-30L-5 (18-75 V in, isolated) → 5 V → balance MCU, VN-100, CAN boards, INA228, radio-stop receiver
   (gPV = 10 × 38 mm 1000 V DC solar fuses in DIN holders; section "Fusing" below)
 - bus bar ─ 100 A / 50 mV shunt ─ pack
charge port (XT90E panel socket, belly rear) ─ pack side of the switch (through the BMS)
```

- **Voltages:** bus 39-53.3 V (RS-04 24-60 V; Flipsky 75100 14-84 V; the anti-spark switch 12-60 V; MRBF 58 V max,
  so the bus must never exceed 57 V: the VESCs' max-input-voltage parameter at 57 V reduces regen above 55 V, and the
  13S charge rule keeps the resting pack at 53.3 V).
- **Converters:** the DDR-120C-24 is catalogued ($69.20 at Bravo Electro and at Master Electronics, where 235 were in
  stock on 2026-10-27, though that page also says "no longer being manufactured" with a 19-week factory lead: order
  two now, one as the spare, and ask Mean Well in T5 whether the DDR-120 is really ending; 33.6-67.2 V in, 120 W,
  180 W for 3 s, 102 × 32 × 125 mm, 0.51 kg packed) and keeps the Jetson's ground away from motor ground. **Decision:
  the J501 and the turret share it** (as cad/turret_box.py's pod does on the box): J501 ≤ 60 W plus the turret's 40 W
  average and 2.1 A ramped peaks stay under 120 W, the turret's 3 × 1,000 µF bank rides through, and the stepped
  spin-up is forbidden on the robot. If the DDR-120 goes away, the **SD-100C-24** ($40.70, Bravo 2026-10-27; 36-72 V
  in, 100 W, 199 × 98 × 38 mm chassis mount) takes its place on the floor tray and T3 reserves its 20 × 10 cm
  footprint; the **DDR-60L-24** ($34.20, Bravo; 18-75 V in, 60 W, 52.5 × 90 × 54.5 mm, 216 g; Mean Well DDR-60
  datasheet, read 2026-10-27) is the upgrade if P2's tests show the J501's input dipping under the turret. The 12 V
  rail is the **DDR-60L-12** ($34.20, Bravo; same case, 91 %; the catalogued DDR-30L-12 is too small once the pods'
  25.6 W and the lidar's 3 A surge share it). The 5 V rail is the isolated **DDR-30L-5** (18-75 V in, 5 V 6 A,
  54.5 × 35 × 90 mm; about $27.60 at Bravo, verify today's figure), because every Pololu 60 V-input buck (D42V55F5,
  D42V110F5, D42V55F12, D42V110F12, D36V50F5/F12) was out of stock or "rationed" with backorders on 2026-10-27. The
  DDR-60L-12 and the DDR-30L-5 lie on their sides in the belly (52.5 and 35 mm tall); the DDR-120C stands on its 32 mm
  side on the floor tray at ≤ 50 % load (Mean Well rates derating only for vertical mounting, so all three run well
  under their ratings; section 1.9).
- **Fusing (all DC-rated for the bus):** MRBF (58 V DC) 80 A for the main; **10 × 38 mm gPV solar fuses (1000 V DC,
  2-32 A; Amazon kits with DIN 10 × 38 holders, about $1-2 per fuse, verify)** for the branches: 20 A per RS-04 (its
  XT30 lead), 30 A per VESC, 5 A for the DDR-120C, 3 A for the DDR-60L-12, 2 A for the 5 V buck, 5 A on the turret's
  24 V branch. The branded option is Littelfuse KLKD (600 V AC/DC, 1/10-30 A, fast-acting; littelfuse.com, read
  2026-10-27), but at $12-24 each from distributors (findchips/Digi-Key snapshot 2026-10-27) it is the backup, and
  Littelfuse's SPF PV series (1000 V DC) the middle ground. ATO/MINI blade fuses are 32 V parts and are not allowed on
  the bus; the turret base keeps its own 10 A blade fuse on its 24 V side.
- **Pre-charge:** the anti-spark switch's soft start charges the VESCs', RS-04s' and converters' input capacitors;
  the XT90-S covers hot-plugging the cassette.
- **No contactor, no e-stop button (D37):** the STOP input (the radio stop, designed separately) tells the MCU to
  sit the robot down and disable torque; it may also drive the switch's OFF pin after the sit. Flipsky's and Pololu's
  own notes apply: a MOSFET switch is not a safety device.
- **Regen:** absorbed by the pack (the charge FET stays closed below 4.25 V/cell); the maxon DSR 70/30 is dropped.
  The first tethered tests put a scope on the bus during a hard brake from 2 m/s and a full squat to confirm it stays
  under 57 V. If it does not, the fallback is RobStride's own **Discharge Module** (Product_Information repo, read
  2026-10-27: 15-60 V operating, 80 V for 100 ms, 30 A continuous and 200 A for 100 ms into a 3 Ω/500 W to 10 Ω/200 W
  resistor; in its "48 V mode" it starts bleeding at 64 V and stops at 59 V, i.e. above the RS-04's 60 V figure, so
  for this bus its threshold would be set by the resistor-free "48 V mode" only after a bench check; listed at $47.55
  by the reseller rcdrone.top, sold out on 2026-10-27, and not found on Seeed's store: verify before relying on it).
  RobStride also notes that the RS-04's "post-power-off anti-backdrive protection" (its damper register) is what
  prevents surges when an unpowered motor is back-driven: the leg workstream's D39 bench test should measure it with
  that setting both ways.

### 1.4 Controller, IMU, CAN

- **Balance MCU:** STM32G474 (3 × FDCAN, 170 MHz, FPU; D7's assumption stands). Primary board: **ST Nucleo-G474RE**
  ($19.90, in stock at ST's eStore on 2026-10-27; Digi-Key and Mouser would not open) or the catalogued WeAct core;
  backup: Teensy 4.1 (3 CAN, one FD; $31.50, in stock at SparkFun 2026-10-27). Three transceiver boards: Adafruit
  CAN Pal 5708 (TJA1051T/3, 3.3 V, CAN-FD to 5 Mbit/s, $3.95, in stock 2026-10-27), which also covers bus C's FD
  option; the Waveshare SN65HVD230 ($4.99, classic 1 Mbit) is the alternative.
- **IMU:** the user's VN-100 Rugged (D6) on its 2 × M3 + 2 dowel pattern, flat on the floor tray beside the spine
  slot (x ≈ -30, y ≈ 0, 100 mm above the COM, under the carrier's standoffs), read at 800 Hz over TTL serial;
  backup Adafruit ISM330DHCX (raw 6-DoF to 6.7 kHz, $19.95, in stock 2026-10-27). VectorNav lists no price but
  "ships within 1 business day" (vectornav.com, 2026-10-27).
- **Loop:** the rig's virtual-model controller (sim/controller_v2.py) at 1 kHz: leg length and lean through the
  five-bar Jacobian, wheel torque for balance, the TPU stop springs; MIT-mode torque to the RS-04s, current mode to the
  VESCs. Start-up: switch on → the MCU waits for bus ≥ 39 V → enables motors → the Jetson commands stand-up.
- **CAN topology (the J501 has two isolated CAN-FD ports: the Seeed wiki, read 2026-10-27, says "two CAN interfaces
  that support CAN FD at 5 Mbps", capacitively isolated, a 120 Ω terminator each "installed by default" and toggled
  by GPIO, both on the J25 20-pin terminal: CAN0_H/L at the end of the top row, CAN1_H/L at the end of the bottom row
  next to the two GND_ISO pins; the datasheet's "1x CAN" is wrong, and there is no 40-pin header on the J501):**
  - Bus A (MCU FDCAN1, 1 Mbit classic): left leg RS-04 × 2 at 1 kHz (~0.5 Mbit/s); 120 Ω at the far motor's lead.
  - Bus B (FDCAN2): right leg RS-04 × 2, the same.
  - Bus C (FDCAN3): VESC L + VESC R at 500 Hz plus the J501 can0 (setpoints 100 Hz, state 200 Hz, 200 ms heartbeat);
    the J501's own termination is one end, the far VESC the other.
  - J501 can1: the turret's Feather M4 CAN (docs/turret-plan.md D3), the J501 terminating; the turret terminates its
    own end.
  - Motor-side CAN grounds tie to the J501's GND_ISO.
- **Jetson link protocol:** velocity, yaw rate, height, lean, "sit", "jump" in; pose, bus V/I, motor temperatures,
  faults out; heartbeat loss → balance in place for 2 s, then sit. Same for the STOP input.
- **Eyes and character:** the Waveshare DualEye on an Adafruit QT Py ESP32-S3 (5426, $12.50, in stock 2026-10-27)
  over USB from the Jetson, off the balance loop (D16).

### 1.5 Head

As the user set it (2026-10-26) and sim/robot_v2.py computes, moved to the 320 mm deck: the VLP-16 flush with the
deck's front edge (axis x = 160 - 51.65 = **108.35**, pins fore and aft at x = 63.9 and 152.8, cable exit +y), the
turret's pan axis 143 mm behind it (**x = -34.65**; the sim's 5 mm clearance rule between the lidar and anything that
turns) on the **30 mm riser** (D41: 13.9° of depression facing forward over the lidar, 25° beyond ±56° of pan, from
the sim's riser study); the turret's base reaches to x = -119.3 and the bumper ring to -120.65, 39 mm inside the rear
edge at pan 0 (it overhung by 0.7 mm on the 280 deck); the turret hides 84° of lidar azimuth behind the robot at pan 0.
The ears are the two SSC1 pods on the side walls (x -10..51, 109 mm behind the front face so the battery door can
be in front of them; section 1.9), their tops at least 23 mm below the deck so they stay under the lidar's -15° beam
(the sim's `ear_top` rule for the new lidar position), aimed forward with the bracket's tilt bolt; the DualEye alone on the face at z ≈ 166 (the
sim's `eyes` mount); the front D435 in the front wall at z ≈ 93, the rear D435 in the rear wall; nothing sticks out
the front. The VLP-16's 3 m cable is "permanently attached to the sensor" (user manual 63-9243 Rev F §5.4.1, read
2026-10-27; cutting it needs a Velodyne waiver) and ends in the interface box, a Polycase LP-41 enclosure (drawing
50-6001: about 84 × 84 × 32 mm, ~90 g, unconfirmed; RJ45, a 5.5 × 2.5 mm barrel jack, 9-18 V, an internal 3 A blade
fuse and 32 V over-voltage trip, 3.0 A at spin-up). Box and coiled cable, about 0.35 kg, sit above the battery
cassette (section 1.9); the Ethernet goes to the J501's 1GbE on the right side (a 12-55 V DIN switch such as the
SODOLA SL720S-4T1GT, $28.99 on Amazon 2026-10-27, only if a second Ethernet device appears; the TP-Link TL-SG105 is a
5 V unit).

### 1.6 Cooling

- **Orin:** 40 W module mode (60 W system max; J501 parameters.json thermal: TTP 80 °C limit, PETG wall limit 60 °C).
  The Seeed cooler's 8015 fan draws air down through its top grille and exhausts along the fin edges (±X of the
  carrier, which is the robot's ±x in the layout of section 1.9). The cooler sits under the riser with its fan inside
  the riser's Ø144 footprint (fan centre x = -60, y = +9 against the pan axis at -34.65): the riser's open sides and a
  hex field in the deck inside it are the intake, 66 mm above the cooler's top; the exhaust leaves through louvres low
  in the rear panel and the forward side panels. The j501-agx CFD (tools/thermal.py, cadagent.cfd) is the check (task
  T7): plate ≤ 70 °C at 40 W in 25 °C air, fan intake within 3 K of the room (Rev 0.8 of the box reached 57 °C with
  the fan re-breathing 7 K warm air; the open riser should do better).
- **VESCs:** bolted flat to the belly plate (fins down in the moving air under the body); 100 A parts at ≤ 15 A.
- **RS-04s:** inside the hip frames between the flanges; the motors' rated 40 N·m is far above the 10-17 N·m standing
  load; the MCU reads their temperatures over CAN and derates at 70 °C.
- **Converters:** the DDR-120C on its side at ≤ 50 % load with a side-wall vent above it; the DDR-60L-12 lying in the
  belly at ≤ 60 % load in the air under the body.
- **Ear pods:** 12.8 W each in a die-cast housing: a vented printed cowl keeps the fins in free air and fingers off.

### 1.7 Kid safety

Rules used: ISO 13854 (crushing: ≥ 25 mm for fingers, ≥ 100 mm for hands), ISO 13857 (an opening ≤ 4 mm admits no
finger), touch temperatures of 48 °C on metal and 60 °C on plastic (IEC 62115-class limits with our margin), the
turret's hard rules (barrel never above horizontal, ≤ 70 fps, the safety line held) and the stops of R37/D39 (sit
before any planned power-off; an unplanned cut is the legs' case).

| Hazard | Where | Mechanism | Measure |
|---|---|---|---|
| Knee scissor | each upper link against its lower link, both legs | the angle closes toward the crouch stop; 60 N·m at 150 mm = 400 N at the link | people-near mode (below); a TPU wedge on the upper link's inner edge that keeps the closing angle ≥ 25 mm wide at the stop (T7 decides from the clash sweep); supervision rule: no hands on the legs while powered |
| Lower-link V | the front link and the wheel link converge at the axle | the V narrows as the leg extends | people-near mode; the wheel link's own width keeps the V ≥ 25 mm beyond 60 mm from the axle (check in T7); a TPU fillet at the apex |
| Stop posts | the upper link lands on the post's TPU sleeve, 1 kN at 60 N·m | a finger between link edge and sleeve | a PETG fairing on the frame's post bosses over the link's approach sector (T7) |
| Wheel vs wheel link | the rotating hub cover beside the fixed link | 2 mm gap | ≤ 4 mm: closed by ISO 13857; keep it ≤ 4 mm in the leg's CAD |
| Pan ring | the turret base, bumper ring Ø172 | the turret's own plan | docs/turret-plan.md D7: pan ≤ 100°/s while disarmed |
| Hopper flap, dial | the turret | the turret's own plan | as there |
| Side door, hatches | the shell | edges | 2 mm radii, captive screws |
| Hot: ear pods | 12.8 W each | housing above 60 °C possible | vented cowl, 50 % PWM in people-near mode, measured on P3 |
| Hot: exhaust | the louvres | ≤ 45 °C air at 40 W | measured on P3 |
| Hot: motors, VESCs, converters | enclosed | not touchable | the shell and belly box close them |
| Battery | the cassette | OV, UV, OC, short, temperature, charging | the BMS's protections and 0 °C charge block, the 80 A fuse, the 4.10 V/cell rule, charging only through the BMS, the PETG cassette holding the cells off the shell, removable for storage |
| Falls | a tip-over | 29 kg on a child | people-near mode's speed cap; the robot sits when a person is within 0.6 m for more than 2 s |

**People-near mode:** a person within 0.6 m in the lidar or either depth camera (the lidar's rear 84° is blind, so the
rear camera counts): the legs hold their length, wheel speed ≤ 0.5 m/s, no jumps, turret pan ≤ 100°/s, lights at
50 %, and the robot sits if someone stays within 0.6 m for 2 s. A hazard review on the P1 frame precedes any session
with children.

### 1.8 Mass and centre of mass

| Group | Sim today (26.2 kg) | This plan | Change |
|---|---|---|---|
| Two legs incl. hip modules (exports/leg/bom.json) | 18.25 | 18.25 | – |
| Frame, shell, hardware (interim shell 1.4 + hardware 0.25) | 1.65 | spine 0.45, floor 0.6, deck 0.45, belly 0.35, pallet 0.3, posts 0.2, riser 0.15, shell 0.95, hardware 0.3 = 3.75 | +2.1 |
| Battery + adapter | 1.63 | 13S2P cassette 2.0 | +0.4 |
| Compute (Orin + carrier + cooler, no box) | 0.98 | 0.98 | – |
| Converters + clamp | 1.13 (DDR-120 0.51, DDR-30 0.12, maxon 0.5) | DDR-120C 0.51 + DDR-60L-12 0.22 + DDR-30L-5 0.12 = 0.85 | -0.3 |
| VESCs, switch, fuses, bus bars, boards | 0.71 | 1.0 (adds bus bars, fuse holders, shunt, INA, MCU, 3 CAN boards) | +0.3 |
| Cameras, eyes, lights | 0.47 | 0.47 | – |
| Harness | (in hardware) | 0.4 | +0.4 |
| Lidar + cable and box | 0.83 | 1.18 | +0.35 |
| Turret (base + pan + tilt) | 1.34 | 1.34 | – |
| **Total** | **26.2** | **~29.5** | **+3.3** |

That is 12 % over the mass the leg rig carries (13.1 kg per leg). **Budget: body + head ≤ 10.3 kg, robot ≤ 28.5 kg**
(levers, in order: pocketed deck and belly, a 2.5 mm floor, the 13S1P pack (-0.9 kg), posts merged into the side
walls); T3's mass table is the ledger and T4 re-runs the rig at **half the real mass from T3** so the leg studies see
the true load. If a leg part drops under SF 2 everyday or 1.2 in a rare event, the leg workstream hears about it
before anything is printed. Balance (hand estimate from section 1.9's positions): fore-aft moment about the hip axis
≈ +0.1 kg·m over 29 kg → the COM 3 mm ahead of the axle; sideways ≈ -3 mm (the DDR-120C and the 12 V converter on the
right, the boards and the lidar box on the left). Acceptance: |x_com| ≤ 10 mm, |y_com| ≤ 5 mm at the 300 mm stance,
from the CAD in T3; the COM height stays within 30 mm of today's -21 mm below the hip axis (the riser lifts the turret
30 mm; the belly's 1 kg pulls the other way).

### 1.9 Layout (robot frame, mm; x forward, y left, z up from the hip axis; the floor tray's top at z = 78.5, the deck's underside at 213.5)

The interim body (280 long) put the FLEXVOLT (87 mm wide) beside the compute. A 160 mm wide cassette, a 176 × 163 mm
carrier whose ports need 40 mm of cable room, and a 125 × 102 mm converter do not fit in 280 × 254 together; 320 does.

| Item | Envelope (x, y, z) | Place | Why |
|---|---|---|---|
| J501 carrier + module + cooler on the pallet | 176 × 163 PCB; stack 16 + 1.6 + 19.2 + 0.5 + 34 = 71.3 above the pallet (underside cards need the 16 mm standoffs) | PCB x -150..26, y -81.5..81.5 (the carrier's X along the robot's x); port edges face the sides: DC-IN, 1GbE, 10GbE and audio to the right (-y) panel, USB × 5, HDMI, the J25 CAN/DIO terminal and the REC/RST buttons to the left (+y) panel; the plugs project ±y into the 45 mm strips beside the carrier, which hold nothing else; cooler top at z ≈ 150 | the fan (centre x = -60, y = +9) sits inside the riser's footprint (x -106.65..37.35); port hatches in the side panels make the computer serviceable from outside, as the j501 box is |
| Battery cassette | 95 × 160 × 85 | x 60..155, y -65..95, on the floor in front of the carrier; slides out along -y through the right door (opening x 55..160, z 76..168): nothing stands between it and the right wall | in front of the carrier, where no plug projects |
| DDR-120C-24 | 125 × 32 × 102, on its 32 mm side | x 30..155, y 95..127, z 78.5..180.5 | the left-front strip beside the cassette (its 32 mm width is the strip's width: T3 confirms 2 mm of clearance or narrows the cassette to 155 mm); terminals face ±x |
| DDR-60L-12 | 52.5 × 54.5 × 90, lying on its 90 × 54.5 face (52.5 tall) | the belly, front left | no floor space is left in the front zone; the 12 V loads (lidar box, pods, eyes) are reached through the chase; the DDR-60L-24 upgrade, if ever fitted, goes beside it |
| Nucleo + 3 CAN boards + INA228 | 82 × 70 × 15 flat, plus two small boards | a shelf under the deck at the right front, x 60..150, y -127..-65, z 180..200, above the cassette's slide path | short runs to the VN-100 (down the right wall), the chase and the J501's left-side CAN plug; the eye controller sits on the front wall behind the eyes |
| VN-100 | 36 × 33 × 9 | on the floor tray at x -30, y 0, under the carrier's standoffs, beside the chase slot | rigid, near the COM, away from the fan and the lidar rotor |
| Lidar interface box + 3 m cable coil | 84 × 84 × 32 (Polycase LP-41, est.) + Ø120 × 35 | above the cassette, z 165..200, x 60..155, y -65..95 (the box at the left end) | the only flat 95 × 160 zone left; the coil is wound to Ø100 if needed; the cable comes down the left wall from the deck grommet at (108, 95) |
| Ear pods (SSC1) | 50.8 wide × 61 deep × 66 tall with the bracket | on each side wall at x -10..51, pod body z 142..193 (top ≥ 23 mm below the deck for the lidar's -15° beam at this distance), behind the right door's x range | the sim's 15 mm setback is replaced by 109 mm so the door and the pod do not share wall; on a 320 mm head the ears still read as ears (T7 renders both and the user chooses) |
| Turret harness (DT06 plug on a 300 mm pigtail) | | the deck grommet at (-130, 60), down the rear-left corner to the 24 V and can1 terminals | misses the cooler (x -110..-10) and the USB plugs (x -124..4 on the left) |
| Belly (320 × 160 × 60 inside) | VESC 2 × 108 × 51 × 35 (cables out one end, toward the chase); switch 84 × 45 × 17; MRBF block 61 × 20 × 45; 2 bus bars; five two-pole 10 × 38 DIN fuse holders (Bussmann CHPV2U, 30 A, about $21 each at TME on 2026-10-27, or a Weidmüller gPV holder strip) on a 100 mm DIN rail; the shunt; the DDR-60L-12 and the DDR-30L-5 | VESCs at x ±(10..118) under the frames' ends; the switch and MRBF at x -150..-60; the fuse holders and the two small converters along the front; the bus bars either side of the chase (about 85 % of the floor used: T3 proves it, and moves the DDR-30L-5 up beside the DDR-120C if it does not fit) | the wheel harnesses come straight down the chase; the button and the XT90 charge socket on the belly's rear face |
| Radio-stop receiver bay | 30 × 50 | the rear panel, inside, beside the four RP-SMA bulkheads | D37: designed separately; the body gives it a 4-pin jack (STOP_A/B, +12 V, GND) |

Ground clearance: the belly box bottom at z ≈ -141; at the leg's 101.5 mm minimum the hip axis is 186 mm up, so
45 mm remain, 74 mm at the 130 mm crouch; the legs' lower links sweep outside |y| = 135 and never reach the belly.
The deck height stays `TOP` = 216 (10 mm of room above the carrier stack was the tightest number: the cooler top at
~150, the deck underside at 213.5); the implementer may raise `TOP` by up to 10 mm if T3's real envelopes need it.

## 2. The simplest first body prototype, and the steps to the finished shell

**P0, the power skid (bench, no legs).** The belly plate with the switch, MRBF, bus bars, fuse holders, shunt and the
two VESCs; the floor tray with the converters, the boards, the VN-100 and the compute pallet; one battery cassette.
Power up, check every rail, run one RS-04 and one BotWheel from the MCU over CAN, the Jetson link over can0, UVLO and
the STOP input. Everything here is reused unchanged.

**P1, the open frame (first physical body).** The spine with both hip modules (from M3's build), the floor tray, the
deck plate on four posts, the belly plate, no shell. The compute pallet and the cassette drop in. The lidar and a mass
dummy for the turret on the deck (1.5 kg at 120 mm). The robot stands on a tether (a ceiling line or a gantry with
0.3 m of slack) and runs the controller from sim; tests in order: stand up, hold, squat, drive 1 m/s, push recovery,
brake from 2 m/s with the scope on the bus, then the first jump. This is the robot that proves the balance loop, the
power system and the frame stiffness; nothing in it waits on a printed shell.

**P2, the head.** The riser and the real turret on the TM pattern, the DT12 harness, the lidar; the target-practice
scenario on the floor with the robot tethered, then untethered in a padded room.

**P3, the shell.** Side walls with the ears, the door and the port hatches, vents; the front face with the eyes and
camera; the rear with the camera, antennas and the radio-stop jack; the belly box with the button and charge socket;
skids; the thermal test at 40 W; the hazard review.

**P4, the dock** (section 2.5).

### 2.5 The dock (D18), outline for the next session

The robot reverses over a 40 mm tall dock using the rear D435 on an AprilTag and the lidar, then sits. Under the
belly plate two brass pads (McMaster brass bar, 25 × 60 × 3 mm, on a PETG insulator) land on two spring contacts in a
printed funnel that corrects ±8 mm; the dock's supply is a sealed CC/CV LED driver (Mean Well HLG-320H-54A, output
pot set to 53.3 V, current pot at 3 A: $99.00 at Bravo Electro on 2026-10-27, and Mean Well's HLG-320H spec gives
the A-type's adjust ranges as 49-58 V and 2.97-5.95 A; the HLG-240H-54A at $73.30 is the smaller choice) with a
dock-present signal (a 24 V line through a
third contact pair); the robot closes its charge relay (a 10 A automotive relay driven by the MCU, in the charge
socket's line) only when it has seen the tag, sits with the contacts closed and reads the dock-present line; the BMS
does the rest. The dock's weight-held contacts follow D18; a magnetic pogo pair is the backup if the pads foul. The
reload station of D22 (balls poured into the hopper's flap) shares the dock. Everything here is TODO (next session).

### Order of ordering (long poles first)

The pack cells, BMS and welder; the SendCutSend set (spine, floor tray, deck, belly, pallet: one cart, 5052 bent parts
and 6061 flat parts; the rules were read 2026-10-27); the Mean Well converters and the gPV fuses and holders; the Nucleo and
CAN boards; the remaining connectors and McMaster hardware. Printing (posts, riser, cassette, shell) runs in
parallel. The hip modules, motors and wheels come from the leg workstream's M3 order. Section 8 is the P1 cart.

## 3. Highly available components (primary and backup)

Prices: (c) = catalog/*.json with its `price_checked` date; (r) = research/*.md 2026-10-25; (d) = read 2026-10-27;
"verify" = not read today. Every part is off the shelf, printed, or an instant-price custom part (D40).

| Function | Primary | Backup |
|---|---|---|
| Battery | 13S2P built pack: 26 × Molicel P50B $8.99 (60 A, Li-ion Wholesale, 12,334 in stock, d) or P45B $7.49 (45 A, 12,701 in stock, d), in a printed cassette | a second cassette on a Daly 13S 100 A BMS; a 13S1P cassette (1.1 kg); WREKD lists no 12S/13S pack any more (d) |
| BMS | JK JK-B2A24S15P, 8-24S, 150 A / 300 A peak, 2 A active balance, BT + UART: $145.00 at 18650batterystore.com but sold out there on 2026-10-27; its siblings JK-B1A24S15P (1 A balance) and JK-B2A24S20P (200 A) are listed on the same store (stock verify) | Daly 13S 48 V 100 A smart, $70.99-95.47 by variant (Amazon, d; the exact variant to verify) |
| Charger | 13S 54.6 V 5 A CC/CV charger: EM3ev 54.6 V 5 A from $30.00 (Anderson lead, em3ev.com 2026-10-27) or a Walmart-listed 54.6 V 5 A at $25.99 (5.5 × 2.1 mm plug, 2026-10-27); fit an XT90; the BMS stops at 4.10 V/cell | Mean Well HLG-320H-54A set to 53.3 V and 3 A (the dock supply; $99.00 at Bravo, d; adjust 49-58 V / 2.97-5.95 A per Mean Well's spec) |
| Main switch / pre-charge | Flipsky Antispark Switch Pro V3.0 with alu PCB and case, 100 A continuous, 12-60 V, $48.00, available (d; $33 heatsink / $43 bare-board versions) | Flipsky Anti Spark Switch Smart Enhanced 300A V2.0, 12-84 V, 100 A continuous, $52.00, in stock (d) |
| Main fuse | Blue Sea 5191 MRBF block $30.12, in stock on Amazon (d; $37.99 with 48 in stock at CurrentConnected) + MRBF 80 A fuse (Blue Sea 5181; the 100 A 5183 is $23.53 on Amazon, d); 58 V DC | a second 5191 and fuse as the spare; the Blue Sea 5502 Class T block ($51.95, 388 in stock at Nomadic Supply, d; 160 V DC) only if the main ever grows past 225 A |
| Branch fuses | 10 × 38 mm gPV solar fuses, 1000 V DC (Amazon kits ~$1-2 each, verify; Weidmüller and Bussmann sell them at distributors): 20 A × 4, 30 A × 2, 5 A × 2, 3 A, 2 A, in two-pole DIN holders (Bussmann CHPV2U ~$21 at TME, d; or a Weidmüller multi-string holder) | Littelfuse KLKD 600 V AC/DC (d; $12-24 each at distributors) or Littelfuse SPF (1000 V DC) in the same holders |
| Bus bars | two bars cut from McMaster C110 copper bar (1/8 × 3/4 in) with M6 studs, on a printed PA6-CF insulator block (the Blue Sea 2301 is rated 48 V DC, d, so it is not allowed on this bus) | a 600 V-rated DIN power distribution block (Eaton/Bussmann or AutomationDirect class, verify) |
| Current monitor | Adafruit INA228 $14.95 (r) + 100 A / 50 mV shunt | Holybro PM07 (2-14S, 90 A) $43.99 (r) |
| 24 V (J501 + turret) | Mean Well DDR-120C-24 $69.20 (Bravo Electro; Master Electronics 235 in stock, flagged "no longer being manufactured", d): order two | Mean Well SD-100C-24 $40.70 (Bravo, d; 36-72 V, 100 W, 199 × 98 × 38); DDR-60L-24 $34.20 (Bravo, d) as a second converter for the turret |
| 12 V rail | Mean Well DDR-60L-12, 18-75 V, 60 W, 52.5 × 90 × 54.5, $34.20 (Bravo, d) | Pololu D42V55F12 $47.95 or D42V110F12 (9 A) $69.95, both backordered (d); DDR-30L-12 $27.60 (Bravo, d) if the pods are dropped |
| 5 V rail | Mean Well DDR-30L-5, 18-75 V in, 5 V 6 A, isolated, about $27.60 (Bravo; verify) | Pololu D42V55F5 $47.95 (6 A, 25.4 × 25.4 × 9 mm) or D36V50F5 $39.95, both backordered (d) |
| Leg actuators | RobStride RS-04 $255 (c), Seeed | – (the leg's choice) |
| Wheels | ODrive BotWheel 2-pack $269.00, available (d, shop feed 2026-10-27); the single at $139 is sold out | – |
| Wheel drivers | Flipsky 75100 single, 14-84 V, 100 A, $65.00, available (d) | Flipsky Dual 75100 with aluminium PCB, 14-84 V, $172.00, available (d): one box for both wheels; or ODrive Pro $229 (c note) |
| Balance MCU | ST Nucleo-G474RE, 3 × FDCAN, 170 MHz, FPU: $19.90, in stock at ST's eStore (d); or WeAct STM32G474 core (c; AliExpress, price not readable) | Teensy 4.1, 3 CAN (one FD), 600 MHz: $31.50, in stock at SparkFun (d); Adafruit Feather M4 CAN 4759 $24.95 in stock (d) has only one CAN |
| CAN transceivers | 3 × Adafruit CAN Pal 5708 (TJA1051T/3, CAN-FD to 5 Mbit/s) $3.95, in stock (d) | Waveshare SN65HVD230 board $4.99 (c 2026-10-26; classic CAN only); Copperhill CAN-FD-BB (MCP2561FD) $39.95 (d) |
| IMU | VectorNav VN-100 Rugged (user's; no listed price, ships in 1 business day, d) | Adafruit ISM330DHCX $19.95 in stock (d; 6.7 kHz); BNO085 $29.50 in stock (d; 400 Hz fused); SparkFun BMI270 $18.50 in stock (d) |
| Compute | Seeed J501 $379 + AGX Orin 32 GB $900 + Seeed cooler $49 (c) | – |
| Depth cameras | 2 × RealSense D435 $375.00, "in stock" but a 6-8 week lead time (store.realsenseai.com, d); the user has D415/D435, so the prototype uses his | D415 $325.00 in stock (d); D435i $399 on backorder (d) |
| Lidar | VLP-16 (user's; ~$4,000 list, c) | – |
| Lights | Diode Dynamics SSC1 Sport white pair $179.95, "18 units available for immediate shipment" (d); 12.8 W per pod, 9-16 V | Auxbeam 2 in pod pair $67.98 Prime (Amazon, d; claims 40 W per light, so the dimmer must hold it to the 12 V rail's budget) |
| Eyes | Waveshare 0.71 in DualEye SKU 29381 $15.99 (d; stock not shown) | 2 × Waveshare 1.28 in round GC9A01 $14.99 (d) or 2 × Adafruit 6178 round TFT $17.50, 32 in stock (d) |
| Eye controller | Adafruit QT Py ESP32-S3 5426 $12.50, in stock (d) | Waveshare ESP32-S3-Zero $5.49-7.99 (d); Raspberry Pi Pico 2 W $7.00 (PiShop, d; Adafruit out of stock) |
| Turret electrics | per docs/turret-plan.md §5 (Feather M4 CAN $24.95, Pololu regulators, SparkFun ROB-13065 ring $27.95) | as there |
| Main connectors | XT90-S pair $2.25 (Gator-RC, in stock, d) for the pack; XT60E-M panel plug $11.99 per 10 (Pyrodrone, in stock, d) for the charge port (the XT90E-M was out of stock there); XT60 (VESCs), XT30 (RS-04 as shipped), TE DT12 set ~$25 (turret plan), Molex Micro-Fit 3.0 and JST-XH for signals, RP-SMA bulkheads × 4 (j501-agx), Phoenix MSTB 2,5/2-STF-5,08 for the J501 DC-IN | Anderson SB50 kit $6.60 each, two per mating pair (AndyMark, appears backordered, d) |
| Frame sheet | SendCutSend (d): 5052-H32 0.125 in and 0.100 in bent (spine, floor tray) with pressed SS-M5-0 nuts, 6061-T6 0.100 in flat (deck, belly) and 0.125 in countersunk (pallet); instant price, sheet in 2-4 days plus 1-3 for bending and hardware; no minimum | Xometry (instant quote from STEP, 6061/5052, 3-7 business days) or JLCCNC (instant, from $5, 3 days), both read 2026-10-27; McMaster 6061 sheet cut by hand |
| Inserts and screws | McMaster: M5 94459A775 $0.27, M3 94459A140 $0.22, M8 94459A778 $0.65 (c hardware.json); 5/16-18 inserts for the pod feet (verify number); M5 × 16 button heads, M3 × 35 flat heads (j501-agx), M3 × 16 standoffs, rubber isolators | – |
| Printed | PA6-CF: posts, riser, cassette rail, ear bosses, side walls; PETG: shell panels, cassette, belly sides; TPU 95A: skids, guards | – |

Radio stop (D37, designed separately): the body provides a 4-pin rear jack (STOP_A/B dry loop, closed = run, +12 V,
GND) and a 30 × 50 mm bay beside the rear antenna bulkheads; an ELRS receiver (RadioMaster RP1 V2, $18.99, available
at radiomasterrc.com 2026-10-27; $24.99 with 225 in stock at RaceDayQuads) driving a Pololu RC switch with relay #2804
($19.95, r) is the simplest non-rated version; no 2.4 GHz wireless e-stop with a dry-contact output was found on
Amazon (the nearest is a 310-331 MHz crane remote with an 8 A relay, $93); FORT Robotics is the rated one (no listed
price, so outside D40).

## 4. Interfaces to freeze now

With the **leg** workstream (cad/fivebar.py, sim/leg_rig.py):

1. **Hip frame to body:** the six M5 inserts per frame at the centre-plane face, (x, z) = (0, ±67), (±83, ±67), bosses
   Ø14, inserts 11 mm deep, the six boss faces and the two flange end faces flat and coplanar within ±0.2 mm (a print
   requirement). The body side is a 3.2 mm 5052 cheek per frame; M5 × 16 button heads, 3 N·m. Loads as section 1.1.
2. **Spacing and track:** the frames' centre-plane faces at robot y = ±21 mm (`SPINE_W` = 42 mm); track 415.8 mm;
   `Y_OFF` = -103.3 mm. The sim, the designer and the CAD read it from one constant.
3. **Harness exit:** the RS-04 leads leave the rear covers into the spine gap through cheek windows |x| ≤ 20,
   |z| ≤ 25; the leg keeps that zone free between the motors' rear covers and the centre plane (the gusset at x = 0,
   z 28..62 stays). The wheel harness uses the frame's Ø18 pass at (0, 0) and runs inward to the gap. Lead lengths:
   the RS-04's 310 + 40 mm reaches the belly bus bars (≈ 150 mm) and the chase; its CAN leads get GH1.25 extensions
   to the MCU shelf (≈ 350 mm).
4. **Sweep envelope near the body** (robot frame, both sides): upper links |y| 103.3..133.3, reaching z ≤ +31
   (the +3° stop plus half a link width) within |x| ≤ 225; front links |y| 135..155; wheel links |y| 157..183; tyres
   |y| 185.6..230.2; the stop posts stand on the frame's outer face at (±114, 42.9) and (±29.5, -36). So: the body
   shell above z = +35 may be full width (±130); below that, and the whole belly, stays within |y| < 100 and the hip
   frames' own envelope; the belly bottom at z ≥ -141 (45 mm of ground clearance at the leg's 101.5 mm minimum).
5. **Mass:** the body + head budget 10.3 kg; the rig re-run at half of T3's real total is the leg's acceptance for it.

With the **turret** workstream (cad/turret.py, docs/turret-plan.md):

6. **TM on the head:** the 30 mm riser's top face is the TM face at (x, z) = (-34.65, 246) in the robot frame (deck
   `TOP` 216 + 30), 4 × M5 inserts on 80 × 80, dowels Ø5 at (52, 0) and (0, -52) in the turret's frame, Ø45 hole;
   the turret's Ø144 foot and Ø172 bumper ring sit 39 mm inside the deck's rear edge (x = -160); the lidar's axis is
   143 mm ahead of the pan axis with 5 mm between them at any pan; the depression table per D41 (13.9° forward, 25°
   beyond ±56° pan) regenerated by cad/turret_lidar.py for the riser.
7. **DT12:** the body carries the DT06-12SA plug on a 300 mm pigtail from the deck grommet at (-130, 60), wired per
   docs/turret-plan.md §2.3: pins 1-2 +24 V from the body's DDR-120C-24 through a 5 A 10 × 38 fuse (≤ 2.5 A; ramped spin-up
   only), 3-4 GND, 5-6 CAN to the J501's can1 (the J501 terminates), 7-8 the body's STOP loop (closed = run),
   11 LINE_SENSE 24 V.
8. **Cable routes on the deck:** the lidar's cable leaves at +y and drops through the grommet at (108, 95); the
   turret's harness drops at (-130, 60); nothing crosses the fan intake field inside the riser.

With the **J501** (read only, ~/Code/j501-agx cad/parameters.json): the carrier's 4 × M3 mount holes and the module's
92 × 79 tie-down pattern, the cooler 100 × 87 × 34 at PCB (90, 90.5) with ≥ 10 mm above it, 16 mm standoffs for the
underside cards (M.2 E Wi-Fi, Mini PCIe, M.2 B), DC-IN 24 V on the Phoenix plug, can0 to the MCU, can1 to the turret,
the four RP-SMA bulkheads in the body's rear panel, pin access to the REC/RST buttons through the left hatch, the
port windows in the side panels derived from the mated plugs as cad/ports.py does there (never from a receptacle
bounding box).

## 5. The ordered task list for the Opus implementer

Estimates are working days for one agent; "sim time" means waiting on MuJoCo or FEA runs. New CAD goes in
`cad/body_*.py`; exports in `exports/body/`. Nothing in cad/fivebar.py or cad/turret.py changes without the owning
workstream. Keep the design simple and every bought part highly available (D40).

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| T1 | **Body parameters.** One module holding every number above (`SPINE_W` 42, `BODY_X` ±160, `TOP` 216, plate thicknesses, post positions, the riser), reading the frame insert pattern from `fivebar.hip_frame`'s constants, the TM pattern from `turret.TM_BOLTS/TM_DOWELS/TM_HOLE`, the J501 holes and cooler from `~/Code/j501-agx/cad/parameters.json` (`J501_DIR` as cad/turret_box.py does), the VLP-16 pattern from catalog/sensors_compute.json: nothing retyped | `cad/body_params.py`, a test in `cad/test_body.py` | the test asserts the three patterns match their sources; the track and `Y_OFF` print from the constant | 0.5 |
| T2 | **Frame CAD.** Hat-channel spine (folded solid plus a DXF flat pattern with SendCutSend's published K-factor 0.44, radius 0.125 in and bend reliefs), floor tray (0.100 in 5052: take its K and radius from sendcutsend.com/bending-calculator), deck plate, belly plate, compute pallet, posts, riser, cassette; STEP + DXF per part with material and thickness in the filename; a clash sweep of the frame against both hip modules and the legs over 101.5-392 mm and ±20° lean (reuse `fivebar.clashes` with the body solids added) | `cad/body_frame.py`, `cad/build_body.py`, `exports/body/` | zero clashes; every sheet part passes SendCutSend's rules (holes ≥ thickness, webs ≥ 2 t, flanges ≥ 0.476 in after the bend, cut features ≥ 8 mm from a bend centreline, no bend over 44 in, PEM nut holes per the SS-M5-0 spec, countersinks only in the 0.125 in pallet); each printed part fits the 256 mm bed; pictures as cad/build_leg.py makes them | 2 |
| T3 | **Layout, mass, COM.** Every bought part as its real envelope (catalog dimensions; STEP where it exists: DDR-120, DDR-60, VN-100, D435, DualEye, the 75100 from its drawing), the cassette and its slide path through the door, the lidar box and coil zone, cable chases and lead lengths; a `check_layout` overlap test as sim/robot_v2.py has; the mass ledger against the 10.3 kg budget; the COM | `cad/body_layout.py`, `exports/body/mass.json` | no overlaps; the cassette slides out with the door open; body + head ≤ 10.3 kg (or the 13S1P lever applied and recorded); |x_com| ≤ 10 mm, |y_com| ≤ 5 mm at 300 mm; every mass sourced or marked estimate | 1.5 |
| T4 | **Sim on the real body.** Replace the interim shell in sim/robot_v2.py with the T2/T3 solids and masses, `BODY_X` ±160, `Y_OFF` from `SPINE_W`, collision shapes for the belly and ears; `BUS_V` 48.1 in sim/leg_rig.py and robot_v2.py; the rig at `--half-mass` = half of T3's total; the thirteen scenarios in exports/sim/v2; the leg studies on the new rig loads | `sim/robot_v2.py`, `sim/leg_rig.py`, `exports/sim/v2/`, `exports/leg/rig-results.json`, `exports/leg/fea/` | every scenario passes; jump height ≥ 85 % of the 54 V figure (279 → ≥ 237 mm); no leg part under SF 2 everyday / 1.2 rare (else a dated note to the leg workstream in docs/milestones.yaml) | 1 + sim time |
| T5 | **Electrical BOM and harness.** Catalog entries for the pack, BMS, charger, converters, the 10 × 38 gPV fuses and holders, bus bars, shunt, connectors, the Nucleo and CAN boards (price, link, date, dimensions, mass); designs/default.json moved to the 13S pack with the maxon clamp, the FLEXVOLT pack, its adapter and the DDR-30L-12 removed; the harness table (every conductor: gauge, length, connector, route) and the CAN map; the fuse list with DC ratings | `catalog/power_electronics.json`, `catalog/alternates.json`, `designs/default.json`, `docs/body-electrical.md` | every line priced and linked with a date; no part needs a quote; the current budget of section 1.3 reproduced from the catalog; every fuse ≥ 60 V DC | 1 |
| T6 | **Frame strength.** FEA (cadagent.fea, as cad/leg_studies.py) of the spine and floor tray under the jump_peak and power_off hip reactions from rig-results.json and the 80 N·m out-of-plane case; the deck under 300 N and the turret's load; the belly under 3 g; overload videos as R43 asks | `cad/body_studies.py`, `exports/body/fea/` | SF ≥ 2 on yield for every sheet part, deck deflection ≤ 0.5 mm, hip-face twist ≤ 0.1°; the insert pull-out assumption flagged until M3's coupon test | 1.5 + sim time |
| T7 | **Shell, guards and thermal.** Side walls with the ear bosses and cowls, the door, the port hatches, vents; front face (eyes, camera); rear (camera, antennas, radio-stop jack); the belly box (button, charge socket, skids); the knee wedge, apex fillet and stop-post fairings of section 1.7 checked in the clash sweep; the fan intake field and the riser's open sides; the J501 CFD at 40 W with the body around it (j501-agx tools/thermal.py) | `cad/body_shell.py`, `cad/body_guards.py`, `exports/body/thermal/` | plate ≤ 70 °C at 40 W in 25 °C air, intake within 3 K of the room; no shell gap between 4 and 25 mm beside a moving part; the ears below the lidar's -15° beam; every printed part fits the bed | 3 + sim time |
| T8 | **Build pack: order list, print plan, assembly, test plan.** The SendCutSend cart (DXFs, material, thickness, quantity, PEM nuts), the McMaster list with numbers (tools/mcmaster_cad.py, one at a time), the electronics list, the print plan; the assembly order for P0-P3; the test plan with pass numbers (rails, CAN, UVLO, STOP, bus voltage during braking ≤ 57 V, stand/squat/drive/push/jump on the tether) | `docs/body-assembly.md`, `exports/body/bom.json`, `exports/body/print-plan.json` | every part orderable today with a price and link; the progress page shows the body like the leg | 1 |
| T9 | **Firmware skeleton** (after the rig hardware exists): G474 with 3 × FDCAN, VN-100 at 800 Hz, the 1 kHz VMC loop ported from sim/controller_v2.py, the Jetson protocol, STOP, UVLO, people-near mode hooks | `firmware/balance/` | one RS-04 and one BotWheel closed-loop on the bench; a HIL replay of the sim's stand_up within 5 % | 3 |
| T10 | **Dock** (section 2.5): contacts, funnel, the HLG supply, the charge relay, the AprilTag, the docking scenario | `cad/dock.py`, `sim` scenario | TODO (next session) | 2 |

## 6. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| The jump needs the bus above ~45 V; near empty the legs slow | smaller hops late in a charge | the controller scales jump height with bus voltage; 13S2P keeps the voltage up under load |
| Regen on a full pack reaches the RS-04's 60 V fault or the MRBF's 58 V | motors fault mid-brake | charge rule 4.10 V/cell, VESC max-input 57 V, the bus scope test in P1; a brake-resistor module is the fallback if the test fails |
| Mass creep (+3 kg over the sim) | leg margins shrink | the 10.3 kg budget, T3's ledger, T4's rig re-run and leg studies at the real mass |
| Twelve M5 inserts in printed PA6-CF carry the body | insert pull-out unmeasured | M3's coupon test, the cheeks bearing on the flange ends, T6's FEA; fallback: a through-bolted frame revision agreed with the leg workstream |
| A self-welded pack | quality, kid safety | the JK BMS's protections, a capacity and IR test before first use, the WREKD pack as the no-welding option |
| The Orin's fan inside a shell | throttling at 40 W | the open riser intake and louvres, the CFD in T7, a temperature log on the robot |
| Knee and stop-post pinch points | a child's finger | people-near mode, the guards of section 1.7, the hazard review before any kid session |
| The VLP-16's 3 m cable and interface box | 0.35 kg and a 120 × 160 × 35 mm zone the sim lacks | allotted in section 1.9; measure the user's box in T3 |
| The DDR-120C on its side | derating not rated by Mean Well | ≤ 50 % load, a vent above it, a temperature check in P0; the DDR-60L-24 split as the upgrade |
| The J501's second CAN port | the datasheet says one; the wiki and schematic say two (read 2026-10-27) | `ip link` on the board in P0 as the last check; if only one comes up, the turret goes on a CANable 2.0 Pro (isolated USB-CAN, as the bench) |
| The RS-04's real over-voltage threshold | the manual says 60 V; RobStride's own bleeder starts at 64 V in "48 V mode" | the 13S bus never needs the margin; the P1 scope test confirms the bus stays under 57 V |
| The DDR-120C-24 is flagged "no longer being manufactured" by one distributor; every Pololu 60 V-input buck is backordered | the 24 V and 5 V rails | buy two DDR-120C-24 now (235 in stock on 2026-10-27); the SD-100C-24 is the successor; the 5 V rail is a Mean Well DDR-30L-5, not a Pololu |
| No ready-made 13S high-current pack exists at a listed price (WREKD's listing is gone) | the pack must be built | the JK BMS and the kWeld make it a half-day job; a capacity and internal-resistance test before first use; the 13S1P cassette as the smaller first build |

## 7. Proposed decisions for docs/decisions.yaml (the user records them)

- **D42 (proposed): the bus is 13S Li-ion, 48.1 V nominal, charged to 4.10 V/cell; the FLEXVOLT 60 V default and
  the maxon regen clamp are dropped.** Why: the RS-04's 60 V over-voltage fault against DeWalt's 60 V initial voltage;
  the rig's jump speed; 180 Wh; no pack protection. The user's packs stay useful on the bench and for the turret stand.
- **D43 (proposed): the body frame is SendCutSend sheet (a bent 5052 spine and floor tray, flat 6061 deck, belly and
  pallet) with printed posts, riser, cassette and shell, 320 × 260 × 140 mm over the hips;** the hip frames bolt to the
  spine's cheeks with their six inserts, 42 mm apart (track 415.8 mm).
- **D44 (proposed): the J501 and the turret share the body's DDR-120C-24; the turret's CAN is the J501's can1; the
  stepped flywheel spin-up is forbidden on the robot** (the ramped 2.1 A is the design point); branch fuses on the bus
  are 10 × 38 mm 600 V DC midget fuses.

## 8. The P1 cart (quantities; the implementer's T8 turns this into exports/body/bom.json with checked prices)

| Group | Items | Est. cost |
|---|---|---|
| SendCutSend | spine (5052-H32 0.125 in, 4 bends, 12 PEM M5), floor tray (5052-H32 0.100 in, 4 bends), deck (6061-T6 0.100 in), belly (6061-T6 0.100 in), pallet (6061-T6 0.080 in): 1 each | $180-300 (instant quote; verify) |
| Battery (D65) | 2 × DeWalt DCB609 ($259 each; the user's own packs and chargers serve), Terrafirma 10 AWG rail adapters (4 for $64.00), 2 × XT90-S pairs, knurled M3 thumbscrews, VHB tape; the bay is SendCutSend (floor and sides) and printed (rails, adapter plates, doors, skids) | $90 without the packs, $608 with two |
| Power | TRACO TEP 150-4812WI ($222.65-275.99 listed: the J501 and the 12 V rail), Flipsky switch ($48), Blue Sea 5191 ($30.12) + MRBF 80 A (~$20), the C110 bus bars (SendCutSend), MINI 58V fuses and inline holders, INA228 + shunt (~$30), Pololu 5 V buck | ~$420 |
| Control | Nucleo-G474RE ($19.90), 3 × Adafruit CAN Pal ($11.85), DualEye ($15.99), 10 AWG / 12 AWG / 16 AWG silicone wire, XT60 and XT30 leads, Micro-Fit and JST-XH kits, GH1.25 extensions (~$80) | ~$140 |
| Lights, cameras | SSC1 pair ($179.95); the D435s are the user's (a new D435 is $375 with a 6-8 week lead time) | $180 |
| Printed | PA6-CF ~1.5 kg, PETG ~1.2 kg, TPU 95A 0.3 kg | ~$130 |
| McMaster | M5 inserts × 60, M3 × 40, M8 × 8, 5/16-18 × 2; M5 × 16 button heads × 60, M3 × 35 flat heads × 4, M3 × 16 standoffs × 4, M3 × 10 × 40; 4 rubber isolators; Ø18 grommets × 6; cable-tie mounts | ~$90 |
| From the leg workstream (M3) | 2 hip modules with 4 × RS-04 and 2 × BotWheel, 2 × Flipsky 75100 | (their order) |
| **Body P1 total, excluding motors, wheels, compute, sensors and the packs** | | exports/body/bom.json is the priced list (docs/body-orders.md): $1,608 bought + $483 SendCutSend as last read (2026-10-27; the bay's and changed plates' prices to re-read) |

## 9. Still to verify, and TODO (next session)

- Prices and stock were read on 2026-10-27 for the cells, the JK and Daly BMS, the chargers, the Mean Well units
  (Bravo Electro and Master Electronics; Digi-Key and Mouser would not open), the Pololu bucks, the Flipsky switch and
  ESCs, the Blue Sea block and fuses, the Nucleo, Teensy, Feather, CAN Pal, the IMUs, the eyes and their controllers,
  the cameras, the lights, the RP1 receiver, the BotWheel, SendCutSend's rules and the J501's CAN ports; they are in
  the text with (d). Still to verify: the DDR-30L-5's price, the gPV fuse kit on Amazon, the exact Daly 13S variant,
  the copper bar stock number and the 5/16-18 insert for the SSC1 feet, Weidmüller's gPV holder number, and whether
  Mean Well itself has ended the DDR-120.
- The exact 5/16-18 insert for the SSC1 feet; the VLP-16 interface box's size and mass (measure the user's unit);
  which FLEXVOLT packs the user has (for the bench), and whether one of his own CAN microcontrollers replaces the
  Nucleo (D7).
- The dock (section 2.5, T10) and the people-near mode's sensor logic (which runs on the Jetson).
