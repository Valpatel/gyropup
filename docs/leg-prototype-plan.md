# Leg v2 on the single-leg rig: the plan to a first physical leg (M3)

Written 2026-10-27 by the planner (Fable 5.1) for the Opus implementer. Not committed. Read first: `cad/fivebar.py`,
`cad/build_leg.py`, `cad/leg_studies.py`, `sim/leg_rig.py`, `exports/leg/{bom.json,print-plan.json,leg.json,rig-results.json}`,
`exports/leg/fea/summary.json`, `research/leg-suspension.md` (sections 1-8), `docs/decisions.yaml` D36-D41,
`docs/milestones.yaml` M2-M3, `catalog/{hardware,alternates,sourcing,images}.json`.

Every price and stock line below says where and when it was read. "Checked today" = 2026-10-27 by this session or by
`catalog/alternates.json` (also 2026-10-27). Sections marked **TODO (next session)** were cut short by the usage limit.

---

## 0. In one paragraph

Build the leg exactly as drawn (no spring, TPU stops kept, wheel fitted but unpowered), print it in PA6-CF after a
day of PA6-CF fit coupons (not a PETG leg: PETG shrinkage does not transfer to PA6-CF seats), and hang it on one
8080 extrusion post with two HGR15 profile rails and four HGH15CA blocks behind the hip frame, a 6.35 mm aluminium
carriage plate bolted to the frame's six M5 flange inserts, weight plates on two rods for the ballast, printed TPU
bumpers under the carriage, and a braced extrusion base with a plywood deck the wheel lands on. Power the RS-04s from
the user's FLEXVOLT 60 V pack (48-55 V window, it is the only regen sink that needs no custom electronics), through a
30 A DC fuse and a 12 V-coil DC contactor held in by the pendant loop with a 1 s off-delay; CAN at 1 Mbit/s from a
candleLight USB adapter to the laptop, a Feather M4 CAN as the rig's sensor and safety node. The controller is
`sim/leg_rig.py`'s own virtual-model controller run at 500 Hz from Python over SocketCAN, first against a MuJoCo
backend, then against the motors, with every run logged and overlaid on `rig-results.json`. Bench tests come before
the leg stands: the RS-04's unpowered back-drive torque against speed (decides D39's knee case), the rotor inertia,
the TPU sleeve's stiffness, the heat-set insert's torque-tension and pull-out in printed PA6-CF, and the tyre's
radial rate. Then stand, squat, jump, drop, and the power cut last, with the bumper set high until the damping is known.

---

## 1. Review: what is ready to build, what to simplify, what to defer

### 1.1 Ready (as of commit 8717f28 plus the uncommitted 07:49 edits to `cad/fivebar.py`, `cad/leg_studies.py`)

- **Kinematics and the printed parts.** `exports/leg/leg.json`: range 101.5-392.4 mm, no clash at 8 heights x 5
  leans, the cable route clears every part, every part fits the 256 mm bed (the hip frame, front link and wheel link
  turned). Printed mass 2.74 kg, bought 6.39 kg, 9.13 kg per leg. Print plan 182.8 h (PA6-CF 178.5 h, 2.72 kg, $218;
  TPU 4.3 h).
- **Bought parts.** `exports/leg/bom.json`: every line has a McMaster number, $1,121.39 per leg at McMaster prices;
  `catalog/alternates.json` (checked today) has a second source for each, and the bearings are much cheaper elsewhere
  (section 6.1).
- **Strength, everyday and landings.** `exports/leg/fea/summary.json` (written 07:22): everyday minimum SF 2.37
  (front link E1); landings (R1, the rig's real knee force 753 N at 330 mm, 10 % fore-aft and sideways): whole leg
  2.33, upper link 1.41 / 1.64, front link 1.30, wheel link 1.95 (1.36 at the full 1,719 N axle spike), hip frame
  1.67, knee 6201s s0 1.39, pins 1.88, eye pressure 1.71, apex 61812 4.59, hub tipping 2.03; front-link buckling
  SF 11. **The output adapters are machined 6061-T6 (D46, 2026-10-27):** held where they really sit on the motor (the
  contact face and the motor's pins), the printed adapter came out at SF 0.86-1.04 across the layers in R1 at the
  14.75 kg design mass; the CAD check also found its two face dowels sat inside bolt holes (so there were none), six
  face inserts broke into the motor-screw counterbores, and the motor screws' heads stood 0.2-1.2 mm into the upper
  link. The machined adapter fixes all three (exports/leg/cnc/README.md) and is at SF 7.6 in R1.
- **The rig physics.** `sim/leg_rig.py` at 13.1 kg (carriage 8.398 kg = frame 3.842 incl. motors and bearings +
  dummy 4.556; moving parts 4.702 kg): stand-up 12.1 N m peak; squat 12.2 N m; jump at the 60 N m cap 278.9 mm,
  3,700 N on the tyre, 2,514 N on the axle, 97.6 N m through a gearbox, 753 N on a knee; 150 mm drop 1,719 N on the
  axle, 66.5 N m gearbox, 551 N knee, 35.5 N m motor; undamped power cut: 12.2 rad/s, 1,458 N on the knees, 96.8 N m
  on a stop; with the assumed 5.9 N m s/rad of motor damping: 1.74 rad/s, 192 N, 8.3 N m.

### 1.2 Known gaps (flag to the main session)

- `exports/leg/fea/summary.json` predates the last rig run (`rig-results.json` 07:50): its R3 case still carries
  2,609 N on the axle and 2,983 N on the pins (joints 0.69-1.09, upper link R3K 0.75) and is tagged `rare`, while
  `cad/leg_studies.py` now tags it `fault` (target 1.0) and the current rig gives 1,316 N axle / 1,458 N knee.
  **Re-run `cad/leg_studies.py` before the build package is final** (owner: main session).
- The sim's TPU stop (816 N m/rad, 7.5 mm of travel), tyre (7.7 ms / 0.7 contact), rotor inertia (0.0243 kg m^2
  reflected) and power-off damping (20 % of shorted phases) are all estimates: that is what the bench tests are for.

### 1.3 Simplify for the first physical leg (decisions made here)

1. **No PETG leg.** PETG and PA6-CF shrink differently and PETG prints on a brass nozzle at different flow, so a PETG
   fit check does not prove a PA6-CF bearing seat, insert hole or dowel fit, and a second 180 h print buys nothing.
   Instead: **PA6-CF fit coupons first** (one evening of printing, section 6.2): a 20 mm slice of the hip frame around
   one motor (10 x M4 lug pattern, two dowel holes, the 61812 seat with its lip), an upper-link hub face (AO face,
   8 x M5 inserts, 2 dowels, the spigot recess), a knee eye (two 12 x 18 x 20 sleeves pressed), a knee boss (two 6201
   seats and the 27 mm web), an apex eye (61812 seat) and a hub stub (the 60 mm journal with the circlip groove).
   Every seat diameter gets dialled in on the coupons (LeRobot's builder cracked both bearing seats pressing 15 x 21
   bearings into a print; Primo's rule: light fit plus retaining compound, never a heavy interference in PA-CF).
   Then the structural parts, hip frame last (section 6.2).
2. **The wheel is fitted but not driven on the rig.** Every rig scenario commands zero wheel torque (`d.ctrl[wheel]
   = 0`); the tyre test is static. No BotWheel driver is bought for M3. When the wheel must turn under power
   (after the drop test passes), the driver is the robot's Flipsky 75100 (14-84 V, $65, in stock at Flipsky CN,
   catalog 2026-10-25); backup ODrive Pro ($229, 58 V max; S1 sold out). The BotWheel's phase and hall leads are
   taped along the links for M3; the through-hub cable route is tried later.
3. **The stops stay as drawn** (TPU 95A sleeves on 10 mm shoulder posts). The rig's bottom bumper is set so the
   carriage lands on the rig at a leg length of 115 mm, above the leg's own stops (101.5 mm), for every test until
   the power-off damping is measured; only the deliberate collapse test (last) lowers the bumper.
4. **No spring** (D39, research section 8.7). The knee-to-knee add-on stays on the shelf.
5. **Cheaper bearings:** 6812-2RS and 6201-2RS from Bearings Direct / VXB (section 6.1), $120 + $69 less per leg.
6. **Ballast is standard 1 in weight plates on two rods**, not a welded block: the carriage's own plate, blocks and
   rods are already about 3.3 kg of the 4.56 kg dummy mass, and plates make the half-mass adjustable for the sim's
   `--half-mass` sweeps.
7. **First motor tests in a printed bench fixture, not in the hip frame**, so the bench tests start the day the
   motors arrive (the hip frame is the last and riskiest print).

### 1.4 Defer

- The BotWheel driver, the wheel cable through the hub, the knee-to-knee spring, any body parts.
- A measured carriage-height sensor better than a time-of-flight module plus slow-motion video (section 3.4).
- A real-time MCU controller: the first stand is Python on the laptop at 500 Hz; the Feather M4 CAN on the rig is the
  safety and sensor node now and the place a 1 kHz loop moves to later.

---

## 2. The rig

Module frame as in `cad/fivebar.py`: x forward, y outwards (+y is the linkage and wheel side), z up, y = 0 the
motors' output face. Numbers from `fivebar.Y` and `hip_frame()`: the frame's flange ends and its six M5 insert bosses
are flush on the plane **y = -82.3 mm** (the robot's centre plane), inserts at **(x, z) = (-83, +-67), (0, +-67),
(+83, +-67)**, flanges 7 mm thick (z 62-69) spanning x +-95; the motors' rear faces are at y = -80.3 (2 mm inboard of
that plane), their 310 mm harnesses exit radially from the O94 rear covers; the stop posts are at (+-108.8, +47.2) and
(+-25.6, -30.4). Knees reach x +-225 (z +8) at the 101.5 mm crouch and x +-60 (z -149) at 392 mm; the wheel axle is at
(0, -L), and (+-103, -282) at +-20 deg of lean at 300 mm; the tyre's mid-plane is y = 104.6 (tyre y 82-127).

### 2.1 Layout (one post, two rails, behind the hip frame, where the sim already puts the rail)

```
          side view (looking along +x)                 plan (looking down)
   post 8080 |B|                                        ┌───── base 700 (x) x 900 (y) ─────┐
     rails   |B|  carriage plate 6.35 mm                │         post ▓▓ at y -132..-212   │
   blocks  ▓▓|B|▓ y -89..-117                           │   brace ─╲   ▓▓                    │
             |B|▓──┐ hip frame flange face y -82.3      │           ╲  ▓▓ rails (x = +-20)   │
             |B|▓  │ motors y -80..-25                  │   deck      ▓▓ plate x +-150       │
             |B|▓  │ links y 0..80, tyre y 82..127      │        frame x +-95                │
   bumper ▄▄ |B|   └── wheel E = (0, -L)                │        wheel lands here, x +-110   │
   ───────────────── deck (18 mm plywood on 4040)       └──────────────────────────────────┘
```

- **Post:** MISUMI HFS8-8080 (80 x 80, 10 mm slots, two slots per face 40 mm apart, 4.57 kg/m, I about 129 cm^4 per
  the MISUMI table), **1,200 mm**. The two rails bolt to its front face on the slot centres x = +-20 with M4 T-nuts.
  Why not 2040 V-slot and V-wheels: the carriage must react the wheel force's roll moment about x, F x (104.6 + 132)
  mm: 3,700 N x 0.237 m = **about 880 N m at the jump's push, 410 N m in the 150 mm drop**. A V-wheel gantry plate's
  wheels are 60-80 mm apart and rated tens of kilograms each: it cannot. Profile rail blocks can.
- **Rails and blocks:** two **HGR15 x 1,000 mm** rails, four **HGH15CA** blocks (34 mm wide, 61.4 long, 4 x M4 on
  26 x 26, Hiwin C0 about 17 kN), two per rail, **250 mm apart in z** (the hip axis midway). The 880 N m couple over
  0.25 m is 3.5 kN, shared by the two rails: about 1.8 kN of lateral load per block in y, plus the lean's pitch
  moment (3,700 N x 0.10 m = 370 N m -> 0.75 kN per block in x): about 2 kN resultant against 17 kN, SF 8. Generic
  HGR15/HGH15CA sets (section 6.1) are the primary; HGR20/HGH20CA (44 mm wide blocks, C0 40 kN) is the backup if the
  block spacing has to shrink, on the same slots with M5 T-nuts.
- **Post stress and sway:** 880 N m on the 8080 at 0.9 m up: 27 MPa bending, 3.8 mm of sway as a bare cantilever
  (M h^2 / 2EI with I = 1.29e6 mm^4), so add **one 4040 diagonal brace** in the y-z plane from the post at z = 600 to
  the base's rear member, 400 mm behind the post (a 1.6 kN strut; sway then well under 1 mm).
- **Rail length check:** hip axis from 186 mm above the deck (leg 100 mm) to about 790 mm (leg 392 + the 120 N m
  jump's 308 mm + the wheel radius 86); blocks reach +-155 mm from it: 31 to 945 mm. 1,000 mm rails from the deck
  level work with 30 mm to spare at the bottom; put the rails' bottom end 20 mm below the deck's top if the post is
  bolted beside the base frame rather than on it. The sim's rail is 1.1 m.
- **Carriage plate:** 6061-T6, **6.35 mm (1/4 in), 300 (x) x 320 (z) mm**, from SendCutSend (section 6.3). Its front
  face is the y = -82.3 plane: 6 x O5.5 for M5 x 16 into the frame's inserts (the 7.9 mm inserts take 8 mm of
  thread); 16 x O4.5 for the four blocks at x = +-20, z = +-125 (26 x 26 patterns); 2 x O8.5 at x = +-120, z = 0 for
  the ballast rods; a 60 x 15 mm slot at the top edge for the motor harnesses and the leg's cables; a 12 mm hole in a
  side tab at x = +150, z = 0 for the drop-release pin; four O6.6 at the corners for the top and bottom bumper
  strikers. Mass 1.65 kg.
- **Ballast:** two 25 mm aluminium rods 150 mm long pointing back (-y) from the plate at x = +-120, each tapped M8 at
  the plate end; **standard 1 in weight plates** (2.5 lb and 5 lb) held by 1 in spring collars. Carriage budget:
  plate 1.65 + four HGH15CA about 0.7 + rods and collars about 0.8 + screws 0.15 = 3.3 kg; the sim's dummy mass is
  4.556 kg, so **about 1.3 kg of plates** gets the rig to the sim's 8.40 kg carriage; `cad/build_rig.py` computes the
  exact figure from the CAD masses and writes it to `exports/rig/rig.json` (task T2). The half-mass sweep (11-16 kg)
  is then plates only.
- **Bottom stop (fall catch):** two **printed TPU 95A bumper blocks 60 x 60 x 40 mm, 15 % gyroid**, on a PETG bracket
  clamped in the post's front slots (two M8 T-nuts each), struck by the plate's bottom edge. Set so the carriage lands
  at a leg length of **115 mm** (plate bottom 51 mm above the deck); a 13 mm shim drops it to the leg's own stops
  (101.5 mm) for the collapse test. Energy: a power cut from 300 mm is 8.4 kg falling 185 mm, 15 J; a 25 mm crush at
  600 N average takes it. Printed, replaceable, no bought bumper. **Top stop:** the same bracket inverted near the
  rail's top, plus the rails' own end caps.
- **Safety tether:** a 25 mm webbing loop from the carriage plate's top slot to the post top (through a sewn loop and
  a carabiner), 150 mm longer than the maximum jump, as the backstop if a block ever leaves a rail; and a 600 mm
  loop from the wheel link's knee boss to the carriage, so a broken link cannot fly.
- **Drop release:** a 10 mm steel pin with a lanyard through a PETG bracket clamped to the post at the drop height into
  the plate's side tab; the carriage (82 N on the pin) is lifted by hand or a rope over the post top, pinned, and the
  pin pulled.
- **Base:** 8-series **4040 extrusion** rectangle 700 (x) x 900 (y) with one middle cross member, 8-series angle
  brackets at every joint, an **18 mm plywood deck** screwed on top (the wheel lands on it: the jump's 3,700 N down
  through the tyre and the 880 N m couple through the post's foot are then internal to one stiff frame, so the base
  cannot tip; the wheel must never run on the bare floor beside the base). The post stands on the rear member, 300 mm
  from the back edge, with four 8080 brackets and the diagonal brace. Rubber feet or a mat under the frame.
  Estimated rig mass 25 kg (post 5.5, base 7.5, deck 8, plate and blocks 2.4, brackets 1.5).
- **Load plate (stand/squat only):** a 400 x 300 x 12 mm plywood pad on four 50 kg half-bridge cells and an HX711
  (80 Hz) placed under the wheel for the static tests; removed for jumps and drops (3.7 kN would crush 50 kg cells).
- **Cable management:** a hanging service loop from an eye at the post top to the carriage (power 2 x 12 AWG, CAN pair,
  the Feather's USB), zip-tied to the plate's top slot.

### 2.2 What the rig CAD must check (task T2)

A clearance sweep of the posed leg (`fivebar.assembly()` at 14 lengths 101.5-392 mm and leans -20/0/+20 deg) against
post, rails, blocks, brace, bumpers, bracket, deck and plate (minimum 10 mm); the carriage's travel against the rail
length for the 120 N m jump; the block loads at the jump's 3,700 N; the post's bending with and without the brace; the
motor harness grommets (vendor STEP, `references/vendor/robstride-rs-04/RS04.stp`) against the plate and its slot at
the frame's lug clocking (7 deg); the masses; the TPU bumper's crush energy.

---

## 3. Electronics and power

### 3.1 The RS-04 as a load

RS-04 (`catalog/leg_actuators.json`, `research/robstride-open-source-2026-10-26.md` section 4): rated 48 V, operating
24-60 V with an over-voltage fault at 60 V (the manual; rcdrone's listing says 15-60 V), 40 N m rated on a 345 x 345 mm
heat sink, 120 N m peak at 90 A phase current, Kt 2.1 N m/A at the output, 9:1, 200 rpm no load. On the rig the two
motors hold about 12 N m each standing (10 W each); the 60 N m jump is about 1 kW mechanical per motor for 0.3 s, so
**45-50 A of bus current at 48 V for 0.3 s**; landings and squats push energy back into the bus (16 J per 150 mm drop,
up to 19 J per squat half-cycle). A bench supply cannot sink that: 16 J into a 2 mF output stage is a 135 V spike,
and the RS-04 faults at 60 V. So:

### 3.2 Power: the FLEXVOLT pack for every test that moves, a bench supply for the bench

- **Primary (everything dynamic): DeWalt DCB609 FLEXVOLT 9 Ah in 60 V mode** (the user's packs; 15S, 54 V nominal,
  60 V full, 3 Ah at 60 V, tool-grade cells). Rule: **start every dynamic test between 48 and 55 V** (regen at 40 A
  through the pack's internal resistance lifts the terminals a few volts; the RS-04 trips at 60 V); the laptop logs
  the motors' VBUS every tick and aborts above 58 V or below 46 V (the pack has no BMS cut-off of its own). Dock
  adapter with 12 AWG leads for the 60 V mode: Terrafirma Technology on eBay about $16.50, Newegg $23.35, an Etsy
  seller $16 (search snippets today; none read live; confirm the adapter engages the 60 V tab, as the catalog note
  says). Charger: the user's DeWalt charger.
- **Bench supply (back-drive, spin-down, coupon tests, first static enable): Mean Well LRS-600-48**, 48 V 12.5 A,
  $59.90 at Jameco (68 in stock in the snapshot read today), or the LRS-600N2-48 (200 % peak) $66.10. The bigger
  RSP-1000-48 (21 A) is $267.95 at Digi-Key via an aggregator / $267.90 at Master Electronics (65 in stock). Never
  run a drop, jump or squat series on the supply alone.
- **Fuse:** Littelfuse **KLDR030** Class CC time-delay, 30 A, 600 VAC / **300 VDC**, $31.70 (536 in stock, Standard
  Electric Supply, read today) in a Class CC holder (Littelfuse LPSC/LPSM class; **TODO: holder part number and
  price**). A 30 A time-delay passes the 0.3 s 50 A jump pulse. Backup: Blue Sea 5191 MRBF block ($29.93 Amazon,
  catalog) with a 60 A MRBF, 58 VDC rated, acceptable only with the 55 V starting rule.
- **Hold-to-run power cut: a 12 V-coil DC contactor in the pack's positive lead.** TE Kilovac **LEV100A4ANG** (100 A,
  900 VDC, 12 V coil 5.5 W): RS Components UK GBP 98.80 (65 ready, read today), Cytech $172.99 (500 available), no
  Digi-Key/Mouser stock found; the EV200AAANA (500 A) is GBP 174 at RS and 45 weeks at Digi-Key. **TODO: a cheaper
  in-stock US source or a listed-price Amazon 100 A "EV relay" as the backup.** Coil supply: the catalog's Mean Well
  DDR-30L-12 (18-75 V in, 12 V 2.5 A, $27.60 Bravo Electro) from the pack side of the fuse.
- **Pre-charge:** none needed with a contactor into two RS-04s (their input capacitance is small; the LEV100 is
  rated for it). Confirm on first power-up with a 10 ohm / 25 W resistor across the contacts for 1 s if the contactor
  welds or the pack adapter sparks.

### 3.3 The safety line (the turret bench's pendant pattern, `docs/turret-plan.md` section 2)

- **Pendant: AbleNet Specs IC** (normally-open momentary, 3.5 mm mono plug, 1.83 m cord), $75, in stock (alternates,
  today); backup Coyote Direct / Motion Raceworks sealed button with a 6 ft cord, $60 (needs a plug soldered on).
  It carries only the 12 V signal loop, never motor current.
- **Loop -> hardware:** pendant closed -> 12 V to (a) an **off-delay timer relay set to 1.0 s** (12 V DC, 1-10 s
  adjustable; **TODO: part**) that holds the contactor coil, and (b) an opto-isolated input on the Feather.
  Pendant released -> the Feather stops its RUN frame at once -> the laptop commands a 0.3 s sit-down to 150 mm then
  the RS-04 stop frame -> 1.0 s later the contactor opens whatever the software did. A power cut while standing is the
  collapse case, which the bottom bumper catches at 115 mm (section 2.1), so the hardware cut is always safe for the
  leg on the rig.
- **Loop -> software:** the laptop sends torque only while RUN frames are fresher than 50 ms; the Feather sends RUN
  at 100 Hz on an 11-bit ID (0x100) that cannot collide with the motors' 29-bit frames; an ARM command from the
  laptop is also required (the pendant alone starts nothing). Motor-side: set `limit_torque` to 60 N m in the
  motors' own firmware (the cap of D38, independent of the laptop) and the motor-side CAN watchdog
  (`robstride_ros2` configures "a nonzero motor-side CAN watchdog on every activation"; **TODO: its parameter name
  and index from the RS04 manual**) so a hung laptop or an unplugged CAN lead stops the motors within 100 ms.

### 3.4 CAN, sensing, the rig node

- **USB-CAN to the laptop:** BIGTREETECH **U2C V2.1** ($23.99, BIQU, orderable, candleLight-based gs_usb -> native
  SocketCAN `can0`; bitrate is set by `ip link`, 1 Mbit/s), backup **FYSETC UCAN** ($8, STM32F072, flash candleLight),
  the original CANable 2.0 is sold out at Openlight Labs; an isolated option is the InnoMaker USB2CAN (RS UK GBP
  56.99, 3 kV isolation). 120 ohm termination at the adapter and at the far motor (the RS-04 has a selectable
  internal resistor on recent firmware; check `can_status`).
- **Rig node: Adafruit Feather M4 CAN Express** (ATSAME51, built-in CAN transceiver on a 3-pin terminal, 6 x 12-bit
  ADC, 5 V boost for the transceiver), $24.95, in stock (read today). Same board family as the turret (D41). It reads
  the pendant loop, a VL53L1X time-of-flight module on the carriage pointing at the deck (Adafruit 3967, $14.95, in
  stock, 30-4,000 mm, 50 Hz) for the carriage height, the HX711 (SparkFun SEN-13879, $4.95, in stock, 80 Hz) on the
  load plate, and sends them on the bus at 100 Hz.
- **Carriage height:** the ToF module at 50 Hz is enough for jump apex and rest heights; impact timing comes from the
  motors' 500 Hz feedback. Always also film at 240 fps against a millimetre tape on the post. A draw-wire sensor
  (CALT CWP-S series, 0-5 kohm, $125-140 for 1-2 m units on the sites read today; no 500 mm price found) is the
  upgrade if the ToF is not good enough.
- **Ground force (slow tests):** 4 x 50 kg half-bridge cells + HX711 kit (about $10 on Amazon, widely stocked; 200 kg
  as a full bridge); SparkFun's 200 kg S-type (SEN-14282, $96.95, in stock) with the same HX711 is the upgrade for the
  collapse test's 1.3 kN.
- **Wiring a person can build from:** 2 x 12 AWG silicone from the pack adapter -> fuse -> contactor -> an XT60
  panel socket on a printed pod on the post (the turret stand's pod pattern: XT60E-F, rocker switch for the 12 V side,
  3.5 mm jack for the pendant, the U2C inside, `cad/turret_stand.py` PANEL) -> the two RS-04 XT30 leads in parallel
  (each lead is 310 mm; a Y-splice with XT30 plugs at the carriage); CAN as one twisted pair daisy-chained adapter ->
  Feather -> motor 1 -> motor 2 (terminated at both ends) using the motors' GH1.25 plugs; the Feather on the laptop's
  USB for logs and power; grounds: the CAN ground is the pack negative (the RS-04's black lead), so a non-isolated
  USB-CAN ties the laptop ground to the pack negative — acceptable on a bench supply or a floating pack, use the
  isolated adapter if the laptop is on mains. Task T10 draws this as one page.

---

## 4. Software path: from `sim/leg_rig.py` to the motors

### 4.1 What is reused unchanged

`fivebar.fk / ik / stance / jacobian / stop_angles` and `sim.leg_rig.vmc / Gains / clip_motor / pin_forces` are the
controller: a spring-damper on the virtual leg (kp_L 3,000 N/m, kd_L 250, kp_th 150 N m/rad, kd_th 6) with the
gravity feed-forward `ff = half_mass * g - (rotor + half the wheel link) * g`, mapped by J^T to the two motors, each
torque clipped to the RS-04's torque-speed line and the 60 N m cap. The scenario commands (`command()`: stand-up
ramp, 0.5 Hz squat, the jump's crouch / push / tuck, the drop's hold) are reused too.

### 4.2 What is sim-only and must NOT be ported (the "firmware cancel" list)

- `stop_torque()` (the TPU sleeves as springs applied through `qfrc_applied`): a model of a real part; on hardware the
  sleeves are real. The controller never adds it.
- `OFF_DAMPING` (the assumed power-off damping): replaced by the measured curve; the controller never emulates it.
- `ARMATURE`, `TYRE_SOLREF`, `STOP_K/STOP_B`: model parameters, set from the bench tests (section 5), not control.
- The RS-04's own MIT loop: command with **Kp = 0, Kd = 0** so the torque field is a pure feed-forward and the laptop's
  VMC is the only loop (a small Kd, 0.5-1 N m s/rad, is an acceptable safety damper during the first stand; log it).
  Anything the motor firmware adds (its `limit_torque`, speed limit, the damper parameter) is configuration, not
  control, and is written once and read back at start-up.

### 4.3 The RS-04 private protocol (29-bit extended IDs, 1 Mbit/s)

From the RobStride Python SDK README, the Seeed wiki, `robstride_ros2` and the firmware release notes (all read today):
- Frame types (the ID's top bits): 0 get device ID, **1 motion control (MIT)**, **2 feedback**, **3 enable**, **4 stop**,
  6 set mechanical zero, 7 set CAN ID, **17 read parameter, 18 write parameter**, 21/22 fault and baud, 24 active
  reporting (the motor answers every command with a type-2 feedback frame unless active reporting is on). Default motor
  ID 127; the leg uses IDs 1 (front) and 2 (rear).
- MIT frame encoding ranges for the **RS04: position +-4 pi rad, velocity +-15 rad/s, torque +-120 N m, Kp 0-5000,
  Kd 0-100** (16-bit fields; the torque rides in the ID's data bits, position/velocity/Kp/Kd in the 8 data bytes, as
  in the CyberGear-family layout: **verify the exact bit positions against RS04 User Manual 260713 section 4.1 in
  `references/vendor` or the RobStride Product_Information repo before coding, task T6**).
- `run_mode` 0 = MIT (operation control), 1 = PP position, 2 = velocity, 3 = current, 5 = CSP. Parameters by name:
  `run_mode, iq_ref, spd_ref, limit_torque, limit_spd, limit_cur, loc_ref, mechPos, mechVel, VBUS, loc_kp, spd_kp,
  spd_ki` (indices in the manual section 4.3; the CyberGear family puts them at 0x7005-0x7020, verify). Feedback:
  angle, velocity, torque, temperature x10, fault bits (uncalibrated, stall, encoder, over-temperature,
  over-current, under-voltage) and mode bits.
- **Damper parameter 0x2023** (RS04 firmware 0.4.1.6 and later): the unpowered back-drive protection; 1 disables it.
  The power-off test runs with it at 0 (default) and at 1.
- Use the 29-bit private protocol, not the separate 11-bit "MIT protocol" (motors silently ignore 11-bit frames on
  the private setting; a K-Bot community note). MotorStudio (Windows) or the SDK's CLI sets IDs and modes.
- Bus budget: 4 frames per tick (2 commands, 2 replies) is about 0.52 ms at 1 Mbit/s: 500 Hz uses half the bus.

### 4.4 Code layout (new files, the implementer's worktree)

- `rig/rs04.py`: frame pack/unpack for types 0-4, 6, 17, 18 with the RS04 ranges; `Motor.enable/stop/zero/mit(pos,
  vel, kp, kd, tau)`; parameter read/write by name; a `scan`; CLI `python -m rig.rs04 scan|enable|stop|param`.
- `rig/bus.py`: `class MotorBus` with `step(tau_f, tau_r) -> (phi_f, w_f, tau_meas_f, T_f, phi_r, ...)` at a fixed
  tick; two backends: `rig/can_bus.py` (python-can SocketCAN) and `rig/sim_bus.py` (MuJoCo via `sim.leg_rig.mjcf()`
  stepped at 0.5 ms, 4 steps per tick).
- `rig/leg_control.py`: the VMC port (imports from `cad/fivebar.py` and `sim/leg_rig.py`); the scenario state machine;
  safety (RUN heartbeat, VBUS and temperature windows, torque cap, a leg-length window 95-395 mm, a rate limit on
  commanded torque).
- `rig/run.py --backend sim|can --test stand|squat|jump|drop|power_off --half-mass 13.1 --log name`: the runner.
- `rig/log.py` and `rig/compare.py`: 500 Hz logs to `exports/rig/runs/<date>-<test>.npz` + a JSON summary with the
  same keys as `rig-results.json` (`peak_motor_nm, peak_motor_speed_rad_s, L_range_mm, jump_height_mm, ...`), the
  measured series overlaid on the sim's `series` (which are at 10 ms), and pass/fail from `rig/criteria.json`.
- `rig/firmware/feather_rig/`: CircuitPython for the Feather (pendant input, RUN frame, VL53L1X, HX711, USB log).
- `rig/bench/`: `backdrive.py`, `spin_down.py`, `fit_params.py` (the measured curves to sim parameters).

### 4.5 Bring-up order

1. `rig/run.py --backend sim` reproduces `rig-results.json` (stand-up and squat peaks within 5 %, jump height within
   10 mm) with the controller running through the bus abstraction at 500 Hz: proves the port.
2. One motor on the bench supply in the dyno fixture: scan, read parameters, enable, zero, MIT torque steps of 1-5 N m
   with Kp = Kd = 0, feedback at 500 Hz, loop jitter measured (target: 99 % of ticks within +-0.3 ms; if Python cannot,
   drop to 250 Hz for the first stand and move the loop to the Feather later).
3. Two motors in the hip frame on the rig, carriage on the bottom bumper, leg hanging: the controller holds a
   commanded length in the air (no ground), then the stand.

---

## 5. Bench test sequence (M3 list first), each with the sim's number and the pass/fail

Fixtures (task T4): the **dyno pair**, two printed PETG lug plates (10 x M4 on O106 with the two O5 dowel holes) on a
plywood board holding the two RS-04s output-to-output through a printed coupler disc (9 x M5 + 3 pin sockets each
side); an **insert coupon** (a PA6-CF block printed in the output adapter's orientation `pa6_cf_z` with M5 and M8
heat-set inserts); a **sleeve test block** (a 10 mm post in a PA6-CF block, the TPU sleeve on it, pressed by a flat
anvil); a **tyre cradle** (the BotWheel on its 4 x M6 flange, pressed radially against a flat plate).

| # | Test | Method | Sim assumes | Pass / decision |
|---|---|---|---|---|
| B1 | **RS-04 power-off damping** (decides D39) | Motor A unpowered (bus lead unplugged), motor B drives it through the coupler in velocity mode at 0.5, 1, 2, 4, 7, 10, 13, 15 rad/s both directions, B's torque feedback at 500 Hz = A's drag; repeat with A powered but disabled (stop state), and with `damper` 0x2023 = 1; also by hand: a 0.3 m lever and 2-10 kg masses, speed from video | 5.9 N m s/rad linear (20 % of shorted phases); the undamped case is 0 | Deliver the curve tau(omega). The main session reruns `sim/leg_rig.py power_off` with it (flag F1). **If the knee force stays at or below the fault case's SF 1.0 figure, no spring and D39 stands; if not: the knee-to-knee spring, softer longer-travel bumpers, and a firmware sit-down before any planned power-off** |
| B2 | **Rotor inertia** | Motor alone, no load, MIT torque step 2 N m for 0.2 s from rest, log omega(t); J = tau / alpha corrected by the friction measured from the steady speed; also a spin-down from 10 rad/s | 3e-4 kg m^2 rotor, 0.0243 reflected | A value with +-20 %; the main session sets `ARMATURE` (flag F1) and the landing predictions move with it |
| B3 | **TPU stop sleeve** | Sleeve on the test post, load 0-2,000 N in 200 N steps by a bathroom scale under a lever (or the S-type cell), deflection by dial gauge; 10 cycles to 7 mm | 243 N/mm (E 9.8 MPa over 18 x 11 mm, 8 mm wall), 7.5 mm travel before the steel post, 816 N m/rad at r 58 | Measured k within 0.5-2x of 243 N/mm, no tearing after 10 cycles; `STOP_K / STOP_TRAVEL` updated (flag F1) |
| B4 | **Heat-set insert torque-tension and pull-out** (M5, M8, PA6-CF) | M5 x 30 through a washer stack and the S-type cell into the coupon; tighten in 0.5 N m steps to 4 N m, record tension; then pull-out to failure; same for M8 | 1,200 N preload per M5 (`HUB_PRELOAD_N`), mu 0.15 | A torque that gives >= 1,200 N with pull-out >= 2,400 N and no thread strip; that torque becomes the assembly spec; `leg_studies.py` reruns with the measured preload (flag F2) |
| B5 | **Tyre radial stiffness** | Wheel in the cradle, 0-1,000 N in 100 N steps, deflection by dial gauge; three spots round the tyre | 7.7 ms / 0.7 contact (about 100-250 N/mm) | A rate and a hysteresis figure; `TYRE_SOLREF` refitted (flag F1); if under 100 N/mm the landing loads fall and the drop test's predicted numbers are regenerated first |
| S1 | **Stand-up** (`stand_up`) | From 140 mm to 300 mm in 1 s, hold 10 s; load plate under the wheel | peak motor 12.1 N m, wheel 140 N, axle 127 N, knee 120 N, L 140-303 | Holds 300 +-10 mm, peak torque <= 18 N m, no oscillation > 5 mm p-p, load plate 100-150 N steady, motor temperature rise < 10 C in 10 min |
| S2 | **Squat** (`squat`) | Three squats 300 -> 150 mm at 0.5 Hz, then 30 cycles | peak 12.2 N m, 1.0 rad/s, wheel 139 N, L 157-302 | Tracks within +-15 mm, peak <= 18 N m, VBUS stays under 58 V (regen), nothing loosens (re-check every screw after) |
| S3 | **Jump** (`jump`, 60 N m cap) | Crouch to 150, push at the cap, tuck, land; load plate removed; tether on | height 278.9 mm, peak 60 N m at up to 16.7 rad/s, wheel 3,700 N, gearbox 97.6 N m, knee 753 N, L 156-345 | First jump >= 200 mm (losses the sim does not have) and <= 320 mm; landing motor torque feedback <= 70 N m; leg settles to 250 +-15 mm within 0.5 s; inspect the knees, adapters and stop sleeves; then compare with the sim rerun at the measured J and tyre rate |
| S4 | **Drop 150** (`drop_150`) | Carriage pinned 150 mm up, leg holding 300, pin pulled | axle 1,719 N, motor 35.5 N m, gearbox 66.5, knee 551 N, L 284-330 | Motor torque feedback <= 55 N m, leg back to 300 +-10 mm within 0.5 s, no damage on inspection, measured L(t) within 20 % of the sim's dip (16 mm) |
| S5 | **Power cut, bumper high** | Standing at 300, open the contactor by the pendant | with 5.9 N m s/rad: 1.74 rad/s, knee 192 N; undamped 12.2 rad/s | The carriage lands on the bumper at 115 mm; fall time within 30 % of the sim rerun with B1's curve |
| S6 | **Power cut onto the leg's stops** (only if B1 and the rerun say the knee stays under the fault limit) | Bumper shimmed down to 101.5 mm, same cut | undamped: 1,458 N knee, 96.8 N m stop; damped 192 N, 8.3 N m | D39: nothing breaks; knees, eye sleeves, pins and 6201s inspected after; the sleeves show no permanent set |

Order: B1-B5 as the motors arrive (B3, B4 need only coupons; B5 needs the wheel), then S1-S6. Every run writes
`exports/rig/runs/<date>-<test>.json` with raw series and the criteria verdict.

---

## 6. Build package

### 6.1 BOM: leg (per leg), rig, electronics — primary and backup

Prices as read on the date given; the leg's McMaster lines are from `catalog/hardware.json` (2026-10-26) and
`exports/leg/bom.json`; alternates from `catalog/alternates.json` (2026-10-27).

**Leg, bought (per leg):**

| Part | Qty | Primary | Backup |
|---|---|---|---|
| RobStride RS-04 (CAN 2.0, not CAN-FD) | 2 | Seeed Studio $255, CN warehouse (11 on hand + 80 due 2026-11-14 on 10-25; page returned 403 today) | OpenELAB $297.99, orderable, 8-15 business days, duties included (today); rcdrone.top $319 orderable; aifitlab $255 and roboticscenter.ai $295 both backordered 4-6 weeks |
| ODrive BotWheel BW0124 | 1 (sold as 2) | ODrive US shop $269 per 2-pack, orderable (today) | ODrive EU EUR 269 per pair, 40 in stock (today) |
| 6812-2RS / 61812 (60 x 78 x 10) | 4 | Bearings Direct 6812-2RS $38.58, 5 in stock (today) | VXB Kit7454 $49.99; McMaster 6656K236 (2Z) $69.11 |
| 6201-2RS (12 x 32 x 10) | 4 | Bearings Direct $2.13, 4,428 in stock | VXB 4-pack $19.99; McMaster 5972K42 $19.37 |
| Knee pin ISO 7379 12 x 90, M10 | 2 | McMaster 92981A411 $8.02 | Aspen ME343-1015X90X12 (box of 10, $168.80, plain) |
| M10 nyloc | 2 | McMaster 94645A220 $0.46 | any class 10 M10 nyloc |
| M12 thin washer DIN 433 | 4 | McMaster 98689A118 $0.14 | any 13 x 20 x 2 |
| Knee spacer tube 5/8 x 0.065 wall, cut 28 mm | 2 | McMaster 9056K68 $6.26 per 6 in | any 6061 tube 15.9 x 12.6 |
| Eye sleeve DIN 179 12 x 18 x 20 | 4 | McMaster 96990A403 $16.11 | JW Winco DIN 179-B12-20 (stainless, price not shown); Reid DM-12025 $7.88 is 25 long (eye change) |
| Stop post ISO 7379 10 x 20, M8 | 4 | McMaster 92981A303 $3.50 | Belmetric BSHLDR8X10X20/33 $4.05, in stock |
| M8 heat-set insert 12.7 long | 4 | McMaster 94459A778 $0.65 | CNC Kitchen M8 x 12.7 (3DJake $11.18 / 20; 9.7 mm hole) |
| M5 heat-set insert 7.9 long | 6 (+ coupons) | McMaster 94459A775 $0.27 | CNC Kitchen M5 x 9.5 (3DJake, deeper hole) |
| M4 x 20 SHCS | 20 | McMaster 91290A168 $0.14 | any 12.9 |
| O5 x 16 dowel | 8 | McMaster 91595A352 $0.38 | any DIN 6325 m6 (4 into the motors, 2 in each adapter's face) |
| M5 x 25 SHCS | 18 | McMaster 91290A252 $0.22 | any 12.9 (heads sit 0.6 mm below the adapter's face: not longer) |
| M5 x 40 SHCS partial thread | 16 | McMaster 91290A662 $0.16 | any 12.9 |
| M6 x 30 SHCS | 4 | McMaster 91290A332 $0.23 | measure the BotWheel's thread depth first (bom.json note) |
| DIN 471-60 circlip | 1 | McMaster 98541A174 $3.05 | McMaster 90154A811 $4.41 (zinc) |
| Filament PA6-CF | 3 kg + 1 spare | Bambu Lab US $79.99/kg (catalog 10-25); Gigaparts $79.99 in stock (today) | Bambu PAHT-CF $94.99/kg (same nozzle, slightly weaker) |
| Filament TPU 95A HF, PETG | 1 + 1 kg | Bambu US $41.99, $13.99 | any |

**Leg, machined to order (per leg; D40, D46):**

| Part | Qty | Primary | Backup |
|---|---|---|---|
| Output adapter, 6061-T6, `exports/leg/cnc/output_adapter.step` + the callouts in `exports/leg/cnc/README.md` | 2 | JLCCNC instant price on upload (estimate $40 each, 5-10 days shipping from China) | Xometry instant quote from the STEP |

Leg bought total about **$930 with the alternate bearings** ($1,121 all-McMaster), plus the adapters (about $80 per
leg) and filament about $300.

**Rig (quantities for one rig):**

| Part | Qty | Primary | Backup / note |
|---|---|---|---|
| HGR15 rail 1,000 mm + 2 HGH15CA | 2 sets | VXB "Beefy Square" HGH15 1,000 mm kit, $159.95 (page labels reversed; 5-10 business days) | eBay HIWIN HGR15 + 2 blocks $49.99 + $38 shipping (DE); generic Amazon sets exist (not read today); HGR20/HGH20CA sets as the stronger backup |
| Post HFS8-8080 x 1,200 | 1 | MISUMI US configurator (EU catalog about EUR 43.6/m; **TODO US price**) | 80 x 80 from 8020.net / TNUTZ |
| Base 4040 8-series: 2 x 900, 3 x 700; brace 1 x 800 | 6 | MISUMI HFS8-4040 (**TODO price**) | any 40 x 40 10 mm-slot |
| 8-series brackets (4040 corner x 12, 8080 foot x 4, brace ends x 2), M8 T-nuts and screws | lot | MISUMI HBLFSN8 family (**TODO**) | 8020 / TNUTZ equivalents |
| M4 T-nuts for the rails (8-series slot) | 34 | MISUMI HNTT8-4 (**TODO**) | drill and tap a 6061 bar strip instead |
| Plywood deck 18 mm, 700 x 900; load-plate pad 400 x 300 x 12 | 1 + 1 | hardware store (Home Depot lists prices) | MDF |
| Carriage plate 6061-T6 6.35 mm 300 x 320 | 1 | SendCutSend instant quote (est. $60-90) | Xometry instant quote |
| Ballast rods 25 mm Al, 150 mm; 1 in spring collars; weight plates 2 x 2.5 lb + 2 x 5 lb | lot | McMaster round bar / collars (**TODO numbers**); plates from any sports store | threaded 1 in-8 rod with nuts |
| TPU bumpers, PETG bumper and pin brackets, pod | printed | P1S | |
| Webbing 25 mm + 2 carabiners; drop pin 10 mm | lot | hardware store | |
| 4 x 50 kg half-bridge cells + HX711 | 1 kit | Amazon kit about $10 (today, snippets) | SparkFun HX711 $4.95 + 200 kg S-type $96.95 (in stock today) |

**Electronics:**

| Part | Qty | Primary | Backup |
|---|---|---|---|
| FLEXVOLT 60 V dock adapter, 12 AWG | 1 | Terrafirma (eBay) about $16.50 | Newegg $23.35; Etsy $16 |
| Mean Well LRS-600-48 bench supply | 1 | Jameco $59.90 (68 in stock) | LRS-600N2-48 $66.10; RSP-1000-48 $267.95 |
| Fuse KLDR030 + Class CC holder | 1 | Standard Electric $31.70 (536) + holder **TODO** | Blue Sea 5191 $29.93 + MRBF 60 A (58 V) |
| DC contactor LEV100A4ANG (12 V coil) | 1 | RS UK GBP 98.80 (65 ready) | Cytech $172.99; EV200AAANA GBP 174 RS; **TODO a US-stock cheaper part** |
| Off-delay timer relay 12 V, 1 s | 1 | **TODO part** | a 555 + MOSFET on the Feather's proto area |
| Mean Well DDR-30L-12 (coil and pod 12 V) | 1 | Bravo Electro $27.60 | Jameco $27.60 |
| USB-CAN: BTT U2C V2.1 | 1 | BIQU $23.99 orderable | FYSETC UCAN $8; InnoMaker USB2CAN (isolated) RS GBP 56.99; PCAN-USB $256 |
| Adafruit Feather M4 CAN Express | 1 | Adafruit 4759 $24.95 in stock | a second one as spare |
| Adafruit VL53L1X | 1 | Adafruit 3967 $14.95 in stock | draw-wire CALT CWP-S (about $125-140) |
| Pendant AbleNet Specs IC | 1 | AbleNet $75 in stock | Coyote Direct $60 |
| Pod panel parts: XT60E-F, 3.5 mm jack, rocker, 5 x 20 holder | 1 each | per `catalog/sourcing.json` parts (Jameco XT60E-F $0.95, Switchcraft 35PM2A, E-Switch RCA1913, Littelfuse 03455LS1H $7.16) | |
| 12 AWG silicone wire 2 m red/black, XT30 plugs x 4, XT60 pair, 22 AWG twisted pair 3 m, 120 ohm x 2, ferrules, heat-shrink | lot | Amazon / Digi-Key | |

Electronics about $330-470 depending on the contactor; rig about $400-500; whole first build about **$2,400-2,700**
plus the motors' shipping and duties.

### 6.2 Print plan on the P1S (hardened nozzle and extruder, textured PEI, glue; PA6-CF dried 8-12 h at 80 C before
every print, fed from a dry box, not the AMS)

Hours from `exports/leg/print-plan.json` (grams / density / 14 cm^3 per h for PA6-CF: rough, expect +20 %).

| Day | Prints | Material | Hours | Purpose |
|---|---|---|---|---|
| 1 | dyno lug plates x 2, coupler disc, bumper/pin brackets, pod | PETG | 10 | bench fixtures and rig parts (order of parts does not wait on them) |
| 1-2 | fit coupons: frame motor-ring slice, hub face (the link's side: spigot recess, clearance and dowel holes), knee eye, knee boss, apex eye, hub stub; insert coupon; sleeve block | PA6-CF | 8 | every seat and insert dialled in before any big part; B3 and B4 run on these |
| 2 | stop sleeves x 4 (+2 spare), TPU bumpers x 2 | TPU | 10 | B3, the rig's bottom stop |
| 3-5 | upper links x 2 | PA6-CF | 48 | |
| 5-6 | front link | PA6-CF | 29 | turned on the bed |
| 6-8 | wheel link | PA6-CF | 40 | turned |
| 8-10 | hip frame | PA6-CF | 51 | last: the biggest print (274 x 148 x 81, turned 45 deg, 782 g); print it only after the coupons prove the seats and the P1S holds PA6-CF flat at that size (a 150 x 150 test slab first if there is any doubt) |
| 10 | apex spacer, spares | PA6-CF | 2 | |

About 198 h of printing (the adapters are machined now): 9 days if nothing fails; plan **three weeks** with drying and one reprint. The motors' lead
time from China (1-3 weeks) runs in parallel; the bench fixtures and coupons are done before the motors arrive.

### 6.3 SendCutSend

The rig's one part: the carriage plate (6061-T6, 0.25 in, 300 x 320 mm, hole table in section 2.1, deburred). The
leg's machined parts (the two output adapters, CNC, D46) are ordered the same day from `exports/leg/cnc/`: JLCCNC or
Xometry, the STEP plus the README's callouts. `cad/build_rig.py`
exports `exports/rig/sendcutsend/carriage_plate.dxf` (flat, mm, holes as circles, no text) and the order sheet with the
instant price read at upload. Everything else on the rig is extrusion, bought hardware or printed.

### 6.4 Assembly order (torques from B4; threadlocker on every screw into steel; never a hard press into PA6-CF)

1. Hip frame: M5 inserts (6) and M8 inserts (4) set with the soldering iron at the coupon-proven temperature; the
   two 61812s pressed in from the motor side onto the lip (light fit + retaining compound if the coupon says so);
   O5 dowels into the frame's locating holes.
2. Output adapters (machined) onto the motors: the motor's 3 pins into the adapter's sockets, 9 x M5 x 25 (no
   washers: the heads sit in the pockets), threadlocker, the motor maker's torque; two O5 x 16 dowels pressed into
   each adapter's face (H7 holes, 8 mm in). Then each motor into the frame on its 2 dowels and 10 x M4 x 20 (heads
   10 mm down in the counterbores), the adapter's j6 journal into the frame's 61812 with retaining compound (Loctite
   641: it comes apart); check the harness exits clear the flanges and the carriage plate's slot.
3. Upper links: two eye sleeves pressed end to end from the outer face; the link onto the adapter's face (over its
   2 dowels and spigot, 8 x M5 x 40 into the tapped holes, B4 torque: the printed link under the heads sets the limit).
4. Knees: two 6201s and the 28 mm spacer tube into each lower link's boss, a DIN 433 washer each side, the 12 x 90
   shoulder screw from the outer side through the eye, the M10 nyloc in the pocket torqued onto the steel sleeve.
5. Apex: inner 61812 pressed into the front link from the inside, the apex spacer, the wheel link's hub through from
   the outside, the outer 61812, the DIN 471-60 circlip.
6. Wheel: 4 x M6 x 30 from inside the hub (measure the flange's thread depth first; bom.json note), cable taped along
   the wheel link and rear upper link.
7. Stop posts with their TPU sleeves into the M8 inserts; swing the leg by hand to both stops: no clash, free knees.
8. Carriage plate: blocks on (16 x M4), rods on, plate onto the frame's six inserts (M5 x 16); carriage onto the rails
   from the top, end caps on, tethers on; bumpers set at the 115 mm position, ballast plates to the rig.json figure.
9. Electrics: pod, fuse, contactor, pendant, CAN chain with both terminators, VBUS read on the laptop before any enable.
10. First power: bench supply at 48 V, current limit 5 A, carriage on the bumper, leg in the air: scan, parameters,
    limit_torque 60, zero both motors at a jig-defined pose (upper links horizontal on the knee-out stops is the
    simplest reference: phi = +3 deg / -183 deg), enable, hold a length in the air, then the stand.

---

## 7. Ordered task list for the Opus implementer

Work in your own worktree on new files; `cad/fivebar.py`, `cad/leg_studies.py` and `sim/leg_rig.py` are the main
session's (requests to them are the **F** items at the end). Estimates are working days.

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| T1 | **Order list** so purchasing starts today: every bought part of section 6.1 with price, link, date checked, primary and backup, quantity, and the TODO prices filled (MISUMI configurator, holder, timer, contactor backup) | `docs/leg-rig-orders.md`, `catalog/rig.json` (items in the catalog schema) | every line has a price and a buy link read on the day, or a printed/SendCutSend note; totals per vendor | 0.5 |
| T2 | **Rig CAD and checks**: post, rails and blocks (envelopes), carriage plate, rods, bumpers and brackets, base frame, deck, brace, pod; the checks of section 2.2 | `cad/rig_parts.py`, `cad/build_rig.py` -> `exports/rig/{*.step,*.stl,rig.json,print-plan.json,bom.json,renders}` | clearance sweep >= 10 mm at 14 lengths x 3 leans; carriage mass and the plate figure in rig.json; block loads and post stress printed; renders of the rig with the leg at 130/300/392 mm and the jump apex; read the frame's insert positions from `fivebar.Y` and `hip_frame()`'s constants (fl_x 95, 12 mm inset, z +-67) without editing fivebar | 2 |
| T3 | **Carriage plate DXF and SendCutSend sheet** | `exports/rig/sendcutsend/carriage_plate.dxf`, `exports/rig/sendcutsend/README.md` | DXF re-imports with the hole table of section 2.1; the instant price recorded | 0.5 |
| T4 | **Bench fixtures CAD**: dyno lug plates and coupler, insert coupon, sleeve block, tyre cradle, the six fit coupons | `cad/rig_bench.py` -> `exports/rig/bench/` | each a valid solid, fits the bed, STL + STEP; coupon seat diameters parameterised +-0.1 mm in three steps | 1 |
| T5 | **Print schedule** from the two print plans (leg + rig) in the order of section 6.2 with drying windows | `tools/print_schedule.py` -> `exports/rig/print-schedule.md` | the table of section 6.2 regenerated from the JSON, total hours, the hip frame last | 0.5 |
| T6 | **RS-04 driver** (section 4.3), with the frame layout verified against the RS04 manual section 4 | `rig/rs04.py`, `rig/tests/test_rs04.py` | pack/unpack round-trips for every type; MIT encoding at the RS04 ranges exact at the end points; a recorded-frame test; CLI scan/enable/stop/param works on one motor | 1.5 |
| T7 | **Bus abstraction + MuJoCo backend** | `rig/bus.py`, `rig/sim_bus.py`, `rig/can_bus.py` | `run.py --backend sim` reproduces rig-results.json stand-up and squat peaks within 5 % and the jump height within 10 mm | 1 |
| T8 | **Controller port + runner + safety state machine** (section 4.2, 4.5) | `rig/leg_control.py`, `rig/run.py`, `rig/criteria.json` | the sim-backend runs of all five scenarios; the RUN-frame, VBUS, temperature, length-window and rate-limit aborts each demonstrated in sim by fault injection | 1.5 |
| T9 | **Logging and comparison** | `rig/log.py`, `rig/compare.py` -> `exports/rig/runs/` | 500 Hz npz + JSON summary with rig-results keys; overlay plots; pass/fail from criteria.json; a sample run checked in | 1 |
| T10 | **Wiring page** (section 3): one diagram a person builds from, connector pinouts, wire gauges, fuse, contactor, timer, pendant loop, CAN chain and terminators, grounds | `docs/leg-rig-wiring.md`, `exports/rig/wiring.svg` | every wire has a gauge and both ends named; the pendant chain traced from button to contactor coil and to the Feather | 1 |
| T11 | **Feather firmware** | `rig/firmware/feather_rig/code.py` | RUN frame at 100 Hz only while the loop is closed; ToF and HX711 frames at 50 Hz; USB log; tested on the bench with the U2C | 1 |
| T12 | **Bench test procedures and analysis** (section 5 B1-B5) | `docs/leg-bench-tests.md`, `rig/bench/{backdrive,spin_down,fit_params}.py` | each test has a step list, a data sheet template, and a script that turns the data into the sim parameter it feeds (b(omega) table, J, k_stop, preload-torque curve, k_tyre) | 1 |
| T13 | **Assembly and safety docs** (section 6.4 plus a pre-test checklist: tethers, bumper height, pack voltage, pendant test, clear zone) | `docs/leg-rig-assembly.md`, `docs/leg-rig-safety.md` | checklists usable at the bench; torques filled from B4 | 0.5 |
| T14 | **Site page**: the rig on the progress site with the shared top bar (renders, print schedule, BOM, run results) | `designer/` (per the site conventions) | linked from the progress page; no URL needed to reach it | 0.5 |

**Flagged for the main session (owner of fivebar.py, leg_studies.py, sim/leg_rig.py):**
- **F1** `sim/leg_rig.py`: take the rail position, `rail_low` (bumper height) and the carriage mass from
  `exports/rig/rig.json`; add a damping-curve option b(omega) from B1 and a sweep that reports the knee force against b
  (the D39 decision); refit `ARMATURE`, `STOP_K/STOP_TRAVEL`, `TYRE_SOLREF` from B2, B3, B5.
- **F2** `cad/leg_studies.py`: re-run so `summary.json` matches the 07:50 rig results (R3 as the fault case at
  SF 1.0); `HUB_PRELOAD_N` from B4; a damped-collapse case once B1 is in.
- **F3** `cad/fivebar.py` (optional): expose `frame_mounts()` returning the six insert positions and the mount plane
  so T2 does not duplicate `hip_frame()`'s constants; check the harness grommet clocking against a plate at y = -82.3.
- **F4** (optional) move `vmc / Gains / clip_motor` into a MuJoCo-free module so the laptop controller does not
  import mujoco.

First five for the implementer, in order: **T1, T2, T4 (so the fixtures print while parts ship), T6, T7** — then T8/T9
as a pair, T10/T11 as a pair.

---

## 8. Top risks

1. **RS-04 supply**: five sellers, all China; two backordered 4-6 weeks. Order on day 1 from Seeed (or OpenELAB with
   duties included) and nothing else on the plan waits on the motors except the bench tests.
2. **PA6-CF on a P1S at the hip frame's size** (274 x 148, 782 g, turned 45 deg): warping and layer adhesion without a
   heated chamber. Mitigation: coupons and a test slab first, textured PEI with glue, the chamber pre-warmed, the
   frame printed last; the fallback is splitting the frame (a fivebar change, main session).
3. **Bearing seats in printed PA6-CF** crack on a hard press (LeRobot) or walk when loose: the coupons set a light fit;
   retaining compound as the backup.
4. **The power-off collapse** is the knees' governing case and depends on one unmeasured motor behaviour: B1 is first,
   the bumper stays high until it is known, and the spring add-on is on the shelf.
5. **Regen over-voltage on a 60 V-limited motor**: no bench-supply dynamics, the pack at 48-55 V, VBUS watched every
   tick, a 58 V abort.
6. **A 500 Hz Python loop** over USB-CAN may jitter: measured in bring-up step 2; 250 Hz is acceptable for the first
   stand (the sim can confirm the margin at 250 Hz: F1), and the Feather is the landing place for a 1 kHz loop.
7. **The hold-to-run contactor**: the proper parts are GBP 99-174 and not all in US stock; the backup is a listed-price
   Amazon EV relay, to be verified, or the AC-side cut when on the bench supply.
8. **The rail blocks' roll moment** (880 N m at the jump) and rail alignment: two rails on one post face, blocks
   250 mm apart, checked in T2; loosen-and-retighten alignment on assembly, and the first jumps at 30 N m.
9. **Insert preload in PA6-CF** is an assumption (1,200 N) behind the hub joint checks: B4 before the adapters are
   torqued.
10. **The motor harness clocking** against the carriage plate (2 mm behind the motors' rear faces): T2 checks the
    vendor STEP; the plate's top slot is the escape.

---

## 9. TODO (next session)

- Fill the TODO prices: MISUMI US configurator (HFS8-8080 x 1,200, 4040 lengths, brackets, T-nuts), a Class CC fuse
  holder, the 12 V off-delay timer, a US-stock contactor backup, the ballast rod and collar part numbers.
- Verify the RS-04 MIT frame bit layout, the parameter indices and the CAN-watchdog parameter name against the RS04
  manual 260713 section 4 (the PDF in the RobStride Product_Information repo; GitHub returned 403 to the fetch tool
  today, so read it from `references/vendor/` or a browser).
- Read one Amazon HGR15/HGR20 rail-set listing live for a US price and delivery.
- Decide whether the first stand runs at 500 or 250 Hz once the loop jitter is measured.
- The site page (T14) conventions: check `designer/` for the shared top bar before writing it.
