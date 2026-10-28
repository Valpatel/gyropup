# The turret program

The user: "keep a good agent running 24/7 making our turret something we can manufacture, fully validated and
awesome with nerf balls." This file is that agent's charter, checklist and log. Every turret agent reads it first,
works the next open items, ticks what it proved (with the evidence), and appends to the log before it stops.

## The goal

A foam-ball turret (Nerf Rival-size balls) for Gyropup that:

1. **can be built**: every made part printable on a 256 mm bed in the materials we use (PA6-CF structure, PETG, TPU),
   in a sensible orientation, with every bought part a real part number (McMaster-Carr through `tools/mcmaster_cad.py`,
   or a named vendor part) and an assembly order a person can follow;
2. **is validated**: each claim below backed by a simulation, a calculation with its inputs, or a bench test plan;
3. **is awesome with Nerf balls**: it feeds every time, fires accurately at a kid-safe speed, sounds and looks great,
   and is easy to reload and to service.

Hard rules: the barrel never points above horizontal (kid safety, docs/head-payload.md); muzzle speed at or under
70 fps (21.3 m/s) for balls; nothing spins or feeds unless the safety line (the bench pendant now, the radio stop on
the robot) is held; private fleet details stay out of public repos.

The speed cap is held by hardware, not by firmware (coordinator, 2026-10-27): the flywheel ESCs are fed only from the
fixed-output 12 V regulator, never from 24 V, and at every connector the 12 V flywheel pins and the 24 V pins are keyed
so they cannot be swapped. The ceiling goes as motor KV x rail voltage x tyre diameter, so a flywheel motor, rail or
tyre may change only when the physics agent's ceiling map (sim/turret_launch3d.py `ceiling_map`: 100 % throttle, a
+5 % KV motor, a +4 % rail, runout and tyre growth) keeps the fastest ball at or under 66 fps on the cartridge as
built. The Snail 2305 is 875 rpm/V; a drone 2306 at 1700-2600 rpm/V on 12 V would throw far over 70 fps, so a drone
motor is never a drop-in replacement: its rail comes down in proportion (about 6 V at 1700 rpm/V) and the map is
rerun before it is fitted.

Parts rule (the user, docs/decisions.yaml D40): every part is off the shelf with a listed price and a buy link
(McMaster-Carr first; Digi-Key, Mouser, SparkFun, Adafruit, Pololu; the makers' stores for motors and servos), or 3D
printed, or ordered to our drawing at an instant online price (SendCutSend for laser-cut, bent or machined sheet and
plate; Xometry or JLCCNC for CNC; JLCPCB or PCBWay for boards). Nothing that needs a quote. The plan's choices D1-D10
are decided (D41, docs/turret-plan.md section 1): continuous pan; the SparkFun ROB-13065 ring on the bench and the
robot; the Feather M4 CAN; the servo bus across the ring; one fixed 12 V regulator as the speed ceiling; two ring
circuits kept for a camera; the line cuts the wheels and the dial in hardware, pan and tilt stay live and capped at
100 deg/s; a phase-short brake with brake-on-stop; a 66 fps chronograph trip. The turret stands on a 30 mm printed riser
on the top deck.

## Where it sits

- On the robot (body not designed yet): behind the VLP-16 lidar on the top deck, firing over it (user, 2026-10-26).
  The ball path and the barrel must clear the lidar at every allowed tilt, or a pan-dependent depression limit applies.
- On the bench: `cad/turret_stand.py` (24 V in, fuse, switch, USB-CAN, hold-to-run pendant).
- Interface to the robot: the TM pattern (4 x M5 on 80 x 80, 2 x Ø5 dowels, Ø45 cable hole) and the DT12 connector.

## Validation checklist

Tick with a link to the evidence (file, picture, result JSON). Unticked = open.

**Ball and launch**
- [x] The ball: Rival-size foam ball diameter, mass and its spread from real products (sourced); the bore, chute and
      dial clearances checked against the spread. Evidence: docs/turret-physics.md section 2, exports/turret/launch/ball.json;
      the bore study (section 6) made the channel after the nip and the barrel ball + 2.0 (cad/turret.py `bore_out`).
- [x] Flywheel launch model: wheel speed, crush, contact time, slip → muzzle speed; at or under 70 fps at the motors'
      set speed with margin, and how the speed varies with ball size and wear. Evidence (v0, the X2216 880KV on Ø34,
      D42): docs/turret-physics.md section 4: 52 fps nominal at 8,855 rpm, the population 48.9 +- 5.0 fps; the fastest
      swept ball at 100 % on a +5 % motor and a +4 % rail 67.6 fps (2.3 under the cap; exports/turret/launch/launch3d.json);
      on this cage's 53.0 mm spacing Ø36 would reach 70.7, so `TYRE_SET` prints Ø34 only.
- [x] Trajectory and accuracy: drop and drift at 1-5 m, spin (matched wheels: none), dispersion budget. Evidence:
      docs/turret-physics.md sections 6-7, exports/turret/flight/flight.json.
- [x] Recoil per shot and per burst, on the robot (feeds sim/turret.py and the head-payload budget). Evidence:
      docs/turret-physics.md section 8 (0.030 N s per shot, 1.2 mrad of aim).

**Feed**
- [ ] Hopper → dial → chute → wheels: no jam in any pan/tilt pose (gravity direction at -25 deg tilt), double-feed
      impossible, the dial parks safe with the motor off. v0 (the STS3215 feed, docs/turret-physics.md section 3):
      parked-safe passes powered and unpowered; nothing sticks in the chute; on a fixed period 3/s level and 2.5/s at
      -25 deg feed without a double (a hung ball at -25 deg and 3/s came down with the next ball), about 1 step in 8
      empty with rigid balls. The firmware's answer: each step paced on gate 1, a dither instead of a step when no ball
      arrives (docs/turret-firmware.md). Open until bench test 5.1 counts it with real foam. Points at bench test 5.1 (docs/turret-next-plan.md N15).
- [x] Rate of fire: dial speed vs flywheel recovery between shots. Evidence (v0, the STS3215 feed):
      docs/turret-physics.md section 3: a step settles in 232-246 ms; 3 balls/s level and 2.5 at -25 deg on a fixed
      period, so the firmware paces each step on gate 1 (docs/turret-firmware.md); the X2216's wheels lose 1.3 % a shot
      and recover between shots at every rate.

**From the turret-on-Orin-box scene (coordinator, 2026-10-27; cad/turret_box.py on main)**
- [x] Hardware speed ceiling that holds at 100 % throttle (safety, highest priority): at full speed on 24 V the
      flywheels would throw 123-140 fps. The design answer: the ESCs only on the fixed 12 V regulator's output and
      Ø34 tyres, so the motors' no-load speed caps the ball; the chronograph trip is the backup. Evidence (v0):
      docs/turret-physics.md section 4 (67.6 fps the fastest swept ball with the X2216); the bench keeps every ball
      under 66 fps by test 4.1 (no-load at most 11,180 rpm on the rail before any ball: docs/turret-bench-tests.md);
      the 12 V regulator is the parts list's el_flywheel_regulator (Pololu 2885).
- [x] ARM release is not instant: a dropped ball still fires ~96 ms after ARM is released and the wheels coast
      ~1.4 s. The design answer (D9) is the phase-short brake, not a gate: six FETs short the motors' phases to GND
      5-14 ms after the line drops (through the FETs and the winding's inductance: tau 10.2 ms at low speed, 5 % speed
      ~48 ms after release, nothing left before a dropped ball reaches the nip at 96 ms), plus AM32's brake_on_stop,
      which the firmware triggers first. Evidence: docs/turret-physics.md section 5; docs/turret-wiring.md 3.3; bench
      test 4.7.
- [ ] Command to muzzle: ~340 ms with the servo-stepped dial in v0 (the step ~235 ms, the drop and chute ~90 ms, the
      nip and bore ~12 ms: docs/turret-physics.md section 3). Pre-staging a ball is not in v0; the firmware leads its
      shots by the measured latency. Points at the feed and accuracy tests (N15), which log trigger to muzzle per shot.
- [x] Firing backwards: at pan 140 deg the muzzle clears the deck's rear corner by 3 mm, where the operator stands.
      Add a pan keep-out behind and check the muzzle's clearance at every pan and tilt (a general obstacle check,
      as for the lidar). Evidence: cad/turret_lidar.py is now that general check (obstacles as cylinders and boxes,
      the ball path at the slowest stray-ball speed); `--scene box` finds every pose clear of the deck and the antennas
      and keeps firing out within 60 deg of straight back (exports/turret/lidar/box.json `keep_out_fire_pan_deg`;
      docs/turret-firmware.md section 5).
- [x] Torque caps: the tilt holds with a 46x margin and slewing is speed-limited. Evidence: the firmware writes the
      servos' torque limit (register 48, config.SERVO_TORQUE_LIMIT = 500: 50 % of stall) to the pan and tilt servos at
      BOOT (firmware/turret/turret_fw.py) and to the feed servo whenever it comes back on the bus (feed.py; checked by
      test_firmware.py's feed-servo re-init case); the pinion at the cap is SF 2.7 (FEA); bench test 2.3 holds a stall.
- [x] Box-specific (cad/turret_box.py on the J501's committed Rev 0.9, D50): the antennas no longer limit the
      depression (the box scene clear at every pan and tilt, firing kept out within 60 deg of straight back:
      exports/turret/lidar/box.json); the stack tips at a 10.6 N push at the tilt axis; the shroud costs 9.2 % of the
      9215's flow by hand (exports/turret/box/box.json). The proof is the thermometer in the collar (N17).

**Structure and motion**
- [ ] Strength of every printed load path (pan ring and gear teeth, yoke, cradle, cartridge, barrel mount) under
      slewing, recoil, a drop of the robot and handling, with the cad-agent FEA and its overload videos. v0 (plan T9,
      exports/turret/fea/summary.json): every part meets SF 2 everyday and 1.2 in the 30 g falls, or has its peak at a
      modelled corner (yoke push 1.82, cartridge recoil 1.57, pan base at a servo stall 1.13; p99 SF 4-11), except the
      **cradle**, whose cheeks bend across the layers (0.78 / 0.62 in the falls, 0.77 under a 50 N push on the
      muzzle): named for v1 (plan T16); on the bench no pushing on the barrel. Open until the cradle is fixed.
- [x] Servo torque margins (STS3215 pan through 63:21, tilt direct) for the turret's inertia at the wanted slew rates.
      Evidence: exports/turret/motion.json (cad/turret_motion.py, with the slip ring and the boards): tilt move 5.9,
      hold 47.6, world-frame 21.9; pan 90 deg in 1.2 s with a margin of 10.0 at the 50 % torque cap, yaw 104; the
      pinion (16 mm face, full-round roots) SF 2.52 at the cap and 1.26 at stall by FEA of one tooth.
- [x] Clearances and stops over the whole pan/tilt range, including the lidar in front and the DT12 harness. The
      turret itself is clear: no overlap and nothing moving within 1 mm but the lug on the yoke's stops at 0 and -25 deg,
      at pans 0-350 every 10 deg x tilts 0, -5, -12.5, -20, -25 (exports/turret/clash-sweep.json); every degree of pans
      130-230 at full depression, the nearest part to the pan pinion is the rail frame at 5.38 mm
      (exports/turret/t1-fine-checks.json, cad/turret.py pinion_check). Over the lidar at the body's 143 mm
      (cad/turret_lidar.py, the 30 mm riser): limited only within pan +-26 deg, to -16.5 deg at worst
      (exports/turret/lidar/lidar.json; the firmware's robot default). On the Orin box: no limit, firing kept out within
      60 deg of straight back (exports/turret/lidar/box.json). The DT plug's 30 mm withdrawal path is clear of the fixed
      parts; exports/turret/mount.json gives the body the plug's sweep as a box.
- [x] The turret's interface for the body. Evidence: exports/turret/mount.json (cad/turret_mount.py, written by every
      bench build: the TM pattern, the riser, the DT12 and its sweep, the harness, the mass and centre with and without
      balls, power, CAN, the lidar table, the recoil; it round-trips cad/turret.py's TM constants); the robot's harness and
      safety line (docs/turret-wiring.md 1.1b, D52); the host bridge for the laptop and the Jetson
      (firmware/turret/host.py, its test in test_firmware.py: 20 of 20).
- [x] Mass: the head payload's budget is 1.70 kg with a full hopper, its centre at most 100 mm above the TM face (D49).
      As built after D48: 1.684 kg with 30 balls, 1.629 empty, the centre 95.7 mm above the TM face
      (exports/turret/turret.json, exports/turret/mount.json). docs/head-payload.md and the designs' head_payload take
      1.70 at the main session's tick; the levers (a 24-ball hopper, a one-board bay) stay listed.

**Build**
- [x] Every printed part: orientation, supports, bed fit, print time; tolerances for bearings, inserts and the gear.
      Evidence: exports/turret/print/*.3mf (each part in its print orientation) and print.json, sliced by Bambu Studio
      for a P1S (21 parts, 1,281 g, 49.3 h; the rail frame flat with no supports); docs/turret-print.md (settings,
      schedule); the fits are bench test 1.1.
- [x] Every bought part with a real part number and price; nothing left as "estimate" that can be sourced. Evidence
      (v0 with D48 and D51): exports/turret/bench/bom.json (`not_in_a_catalogue`, `no_listed_price` and
      `no_second_source` empty) and the order sheets exports/turret/bench/orders/ (131 lines from 18 sellers, a backup
      seller on every line, $1,686.96 in whole packs with the stand and the tools; both AM32 ESC pairs, D51). The
      SendCutSend cart is four parts in two thicknesses (the pan clamp, the cradle's two cheek plates, the stop lug),
      each DXF drawn from its countersunk face. Every part follows the parts rule (D40); the longest lead is the servos
      from Waveshare (1-3 weeks).
- [x] Wiring (v0): docs/turret-wiring.md (every connector, conductor and crimp; the +24 V traced to each ESC phase;
      the arm chain drawn with a designator on every part and exports/turret/wiring/parts.md listing each part's value,
      catalogue key and pins; the boards laid out and checked by cad/turret_boards.py). The plan's 5 V logic, 5 V 555,
      floating brake star and 3.3 V laser gate were corrected before anything was soldered (D47).
- [x] Assembly order with pictures; a bench test plan (chronograph, accuracy, jam rate, the pendant). Evidence:
      docs/turret-assembly.md (twelve steps, a picture each from the CAD, the v0 cartridge), docs/turret-bench-tests.md
      (the v0 procedure with its numbers). Step 8 is the cradle on its aluminium cheeks (D48).

**Awesome**
- [ ] Sounds, look and feedback (the laser, lights) on the 3D page match the real thing. Points at N19.
- [ ] Reload at the dock: the hopper's fill port and flap. Points at N19 (the fill flap and its spring).

## Log

Newest last. One entry per agent run: what it did, what it proved, what is next.

- 2026-10-26: charter written. The turret exists in CAD (cad/turret.py), on a bench stand (cad/turret_stand.py,
  cad/build_turret.py), in the physics (sim/turret.py: balls at 70 fps from a 30-ball hopper). Nothing above is
  validated yet.
- 2026-10-27 (in progress): the coordinator passed on the user's request for a high-quality electrical slip ring in
  the pan joint. A separate planner is researching it. The pan joint's cable path, the wiring and the DT12 pinout
  wait for its plan; the pan axis and centre hole stay free, and no new hard pan stops go in.
- 2026-10-27 (in progress): physics handed to a dedicated physics agent (coordinator), which now owns sim/turret_*.py
  and builds sim/turret_e2e.py; its "Findings for the CAD" in docs/turret-physics.md feed the CAD. Committed as they
  stood, for it to build on:
  - sim/turret_launch.py: a one-shot flywheel model (Hertz foam contact with Hunt-Crossley damping, Coulomb tyre
    friction, the Snail's DJI motor constants behind an ESC current limit). It found that 12 % crush makes the speed
    swing with the foam (efficiency 0.36-0.89), while 25 % gives 0.66-0.92 with no rejections. Ø36 TPU tyres on a
    regulated 12 V flywheel rail: 55 fps at 90 % of no-load, 54.7 +- 1.0 fps over 400 balls (sourced size and mass
    spread, foam and grip swept); at 100 % throttle on a +5 % motor and a +4 % rail the worst ball reaches 66.4 fps (a
    3.6 fps ceiling margin); 8-ball bursts at 10/s hold speed; recoil 0.031 N s, 0.045 at the cap. The model's
    efficiency (~0.95) is above what hobby Rival blasters measure (0.40-0.75 at higher wheel speeds), so the bench picks
    the tyre from a printed set: the fastest ball at 100 % stays at or under 66 fps.
  - sim/turret_feed.py: MuJoCo, the dial, housing, baffle and chute from the CAD's numbers with 30 balls. Found: the
    hopper held only 15-16 balls under the old lid (raised to 100 mm, which fits 34); the parked dial never lets a ball
    out (tilt 0 and -25 deg, shaken at 5 m/s^2, powered or not); feeding is 30/30 at 0 deg and 27-30/30 down to -25 deg
    in 40 steps. Below about -12 deg the last balls of a magazine collect on the baffle (the front is the hopper's low
    side), so the firmware lifts to 0 deg for 0.4 s after an empty step. The one "double" traced so far was a ball that
    stalled at the top of the chute for a step and then reached the wheels with the next, not two out of the dial.
- 2026-10-27 (in progress): the user asked for thumbnail pictures of every BOM part, to be sure each can be ordered
  and to keep alternates in mind. Every turret bought part gets a catalogue key with a real part number and source
  URL; the turret BOM calls cad/bom_media.py enrich() once it is on main.
- 2026-10-27: the slip ring is in the turret (plan task T1), the physics' findings are in the CAD, every bought part
  has a catalogue key, and the wiring and firmware plans are written (T2, T4).
  - Pan joint (cad/turret.py): `RING_MODELS` (SparkFun ROB-13065 for the bench, Senring M220-0210-12S for the robot,
    Moflon MC330, Servotecnica A03), `ring_carrier` (drops into the foot's Ø65 opening from below on three tabs, 3 x M3 x
    10 flat heads into inserted bosses; the ring's flange on its top), `ring_driver` (in the turntable's bore; a 5/16 in
    tube couples the ring's rotor), the rotor leads as a Ø7.5 bundle beside the coupling and through the yoke.
    `CONTINUOUS_PAN = True` (the user's D1 stays open: False brings back the stop post and finger). The index: a 1/4 in
    magnet on the housing's top through the clamp ring, an A1120 hall switch in the turntable 2.9 mm over it.
  - Two deviations from the plan, by design: (1) the carrier's screws sit at r 35.75 under the foot, outside the TM's
    Ø45 hole and under the head ring, so the ring is changed with the turret off its mount (4 x M5 and the DT12;
    exports/turret/turret-pan-joint.png). The plan's Ø63 ledge would leave a 1 mm lip for M3 screws, and its screws at
    r 32 are outside the Ø45 hole as well. (2) The lead bundle is Ø7.5, not Ø12: 12 x 26 AWG + 2 x 17 AWG PTFE is Ø5.1 by
    area, and a Ø12 bundle cannot pass the coupling in the Ø40 bore with 3 mm on both sides. It keeps 3.25 mm from the
    bore and 3.7 from the coupling, 3.0 at the yoke's slot; the driver's crescent (0.75 mm) is where it is tied.
  - The bays: the base board on four bosses on a wall at +x in the base; the turret's electronics on a three-board stack
    in a PETG tray on the -y yoke arm (the module footprints from Pololu and Adafruit set its 52 x 50 boards); it reaches
    r 118.6 at z 71..128, where nothing fixed stands (the tilt servo already sweeps r 112).
  - What the clash sweep found and how it was fixed: the 16 mm pinion (for its strength) rose to the turntable's top
    plane, so the yoke's underside is relieved 1.5 mm outside r 37, and the cradle's front at full depression met it
    behind the turret, so the ball path rose 4 mm (`path_t` 125). Result: no overlap and nothing moving within 1 mm
    except the tilt stops, pans 0-350 every 10 deg x tilts 0/-25 (exports/turret/clash-sweep.json), 2.5 mm where the
    cradle passes over the pinion at every degree (exports/turret/t1-fine-checks.json).
  - The physics' findings in the CAD (docs/turret-physics.md section 12): the channel after the nip and the barrel bore
    ball + 2.0 (14); the gates 60 mm apart with 1 mm slits (11); the wheel cavities cut 0.5 mm wider for the tyre's
    growth (5); the tyre printed with its bore 4 % under the rim (5); the Ø34/Ø36 tyre set, Ø38 dropped after the
    ceiling map on this cage's fixed wheel spacing gave 69.7 fps (4); the dial's 30 deg cone with four fins (1). The
    physics agent reruns the feed and the flight on them.
  - Motion (exports/turret/motion.json): tilt move 5.9, hold 47.6; pan 10.0 at the 50 % cap, yaw 104. Against the
    turret before this change (the same method): tilt move -5 %, hold -10 % (the cone and fins at the rear), pan -14 %
    (the turret boards, 110 g at r 90). All still large margins; the plan's "within 5 %" is not met for pan and hold.
  - Mass: 1.594 kg with 30 balls, over the head payload's 1.5 kg. Open item on the checklist.
  - Hardware and parts: inserts sized to their parts (short M3 inserts in 6 mm bumper tabs, bosses for the base board,
    insert pilots past every screw tip), the CT thumbscrew (DIN 464 M4 x 12, McMaster 92581A250, kept by an O-ring), the
    C610 held by two cable ties through slots, the yoke's M4 x 10. 35 McMaster product pages read one at a time
    (tools/mcmaster_cad.py --pages-only, now committed as a generic option), every one with cad.pending for its CAD.
    The pan bearing's catalogue entry (bearing_61810) now names the 6810-2Z 6656K229 that the CAD draws; the $194.88
    stainless 4668K273 is its alternate. 40 electronics entries with maker part numbers (catalog/turret.json).
  - Parts list (cad/build_turret.py, exports/turret/bench/bom.json): every line names a catalogue key and goes through
    cad/bom_media.py enrich(); `not_in_a_catalogue` is empty. Pictures fetched with tools/part_images.py for the new
    keys (catalog/images.json; the photos themselves stay on this machine); 23 electronic parts have none because their
    buy link is a distributor that blocks automated reads (Mouser, Digi-Key) or a page without a product photo (TI's
    store): catalog/sourcing.json `image_pages` can name another page for them.
  - Bench stand (cad/turret_stand.py; the same cutouts in cad/turret_box.py): the rocker's 19.4 x 13.0 snap-in hole in a
    2.5 mm thinned panel, the fuse holder's Ø12.75 D-hole, the jack's Ø6.35 in a 2 mm panel, the XT60E-M inlet (the
    supply's lead carries the female) with its screws slotted 18-28 mm, a DC-rated fuse (Littelfuse 0477005.MXP), the
    3M SJ5003 feet, the terminal board's bosses moved onto the bottom plate at 66 x 46 (they were floating in the box).
    The box scene rebuilt: with the ball path 4 mm higher, its antennas no longer limit the depression.
  - Wiring (docs/turret-wiring.md): the DT12 and ring pin maps, the ring's two Micro-Fit 2 x 4 connectors, the CT as a
    2 x 3 power and a 2 x 6 signal Micro-Fit (they cannot cross-mate; 24 V reaches only the C610), every run's gauge
    and length, the arm chain with no MCU in it, the trip (2.98 ms for 60 mm gates), the brake, the fuses, the budget.
  - Firmware (docs/turret-firmware.md, firmware/turret/): the pin map, the states, the spin-up with the pre-feed RPM
    check (below 11,500 rpm), the feed's dither and jam rules, the aiming rules from the physics, the CAN message set.
    Pan homing passes 1,000 random power-ups (firmware/turret/test_homing.py): all homed, median 3.5 s, at most 6.7 s
    and 368 deg; repeatability 0.07 deg; settled tracking 0.09 deg over random moves to +-720 deg; 980 index re-checks
    within 0.05 deg; no false re-home (exports/turret/firmware/homing.json).
  - Supply (the thumbnails agent's finding, catalog/sourcing.json risk): the Snail 2305 is delisted, the M2006 and C610
    are out of stock. The speed-ceiling rule is now a hard rule above: no drone motor goes on the 12 V rail.
  - Next: the FEA of every printed part on this geometry; the lidar table and the box's keep-outs with the new
    obstacle check; cutting 100 g; the assembly order with pictures and the bench test plan (T5 needs the parts).
- 2026-10-27 (later): the parts rule (D40) and the decided choices (D41) applied, every printed load path analysed and
  strengthened where the FEA asked, the clearance study generalised, the assembly order drawn.
  - D40/D41: the SparkFun ROB-13065 ring on the bench and the robot (RING_MODELS keeps it and the Adafruit 1196 as its
    alternate; the quote-only rings are gone), mapped 2+2 power, CAN, safety, servo TTL, signal ground, two kept for a
    camera (docs/turret-wiring.md 1.2), on 2 x 6 Micro-Fit connectors; the CT signal connector is now 2 x 5, so the
    three Micro-Fit sizes cannot cross-mate. The pan bearing is VXB's chrome-steel 6810-2RS ($24.99); the laser a
    Quarton VLM-520-73 LPT from Digi-Key ($41.82, Class 2, Ø7 x 26, on 5 V); the pan clamp is a SendCutSend part in
    0.125 in 6061-T6 (exports/turret/pan_clamp.dxf and .step, instant price on upload). The lidar study puts the TM face
    on the 30 mm riser. No quote text is left in the turret's files.
  - FEA (cad/turret_studies.py; the last full run was stopped at the wrap-up, so its pictures and summary.json are not
    committed): on the final geometry the yoke is SF 2.53 / 2.35 / 1.99 in the 30 g falls and 1.72 in the everyday push at
    the muzzle (target 2; the peak sits at the relief's step, p99 12 MPa), the turntable 3.59 down; from the targeted
    runs, the pan base 7.2 / 1.61 (falls) and 2.52 / 1.26 (servo cap / stall), the aluminium clamp 3.1, the pinion 2.7 /
    1.35, the turntable's teeth 3.2 / 1.6; the cradle 1.0 / 0.83 / 0.81 against the across-layer strength (1.7-2.1 along
    the layers, p99 SF 1.7-2.0). Not run yet: the cartridge (fall and recoil) and the dial (jam).
  - What the FEA changed: the clamp ring (printed, 3 ears) failed the lift case at SF 0.18 and became aluminium with
    five ears (SF 3.1); the yoke's bridge, once its underside was relieved for the pinion, carried the arms as thin
    windowed beams (SF 0.6): it is now 10 mm, solid, and the relief steps up in three 0.5 mm steps from r 35; the
    cradle's rails and cheeks bent (SF 0.27-0.5 at first): 2 mm deeper rails behind the front dowel, filleted gussets
    at the cheeks, 6 mm cheeks, a Ø18 boss round the pivot insert and a deeper-rooted stop lug; the pan base's servo
    pocket wall now runs into the housing tube (its notch was the side-fall peak).
  - Mass: 1.556 kg with 30 balls, 1.502 kg empty (exports/turret/turret.json), down from 1.594: still 56 g over the head
    payload's 1.5 kg with a full hopper. Saved: the bumper 4 mm with screw lugs, the carrier and the turntable pocketed,
    the bay's walls 1.2 mm, the lid 2 mm, the hopper's wall 1.6 mm, the pan base at 40 % gyroid, a 3.8 g laser. Added by
    the FEA: the 10 mm solid bridge, 6 mm cheeks, deeper rails, the aluminium clamp.
  - Motion (exports/turret/motion.json): tilt move 5.8, hold 42.9, world-frame 21.8; pan 9.2 at the 50 % cap, yaw 96.7;
    the tilting group's centre 8-11 mm behind the axis empty to full (nose-up preload kept).
  - Clearance (cad/turret_lidar.py, now a general obstacle check with point pruning, ~2 min a scene): on the robot, the VLP-16 148 mm ahead with its top 41.7 mm above the TM face, the depression is limited only within pan +-26 deg, to -16 deg at worst (the ball path binds, 11.8 mm clear; the firmware table every 5 deg is in exports/turret/lidar/lidar.json); on the Orin box nothing limits it (the deck and the antennas clear at full depression), and firing is kept out within 60 deg of straight back, where the operator stands (exports/turret/lidar/box.json).
  - Assembly (cad/turret_assembly.py, docs/turret-assembly.md): twelve steps with an exploded picture each from the
    CAD and the hardware table from the parts list. Bench tests: docs/turret-bench-tests.md (fits, strength, the
    electrics without motors, the speed ceiling first, the feed, accuracy).
  - Not done at the wrap-up (2026-10-27): the full FEA rerun (cartridge, dial, summary.json); the electronics' listed
    prices (a research agent was gathering them; `no_listed_price` in exports/turret/bench/bom.json lists what is
    missing, with the bench stand's rocker and feet); the last 56 g.
  - Next: the prototype plan the planner is writing (main's docs/turret-prototype-plan.md) becomes the task list.
- 2026-10-27 (evening): v0 ready to order, print and build (docs/turret-prototype-plan.md T0-T5, T8 and the build
  package; decision D42).
  - T0: main as merged builds clean (1.556 kg with 30 balls, 1.502 empty; 0 clashes; tilt 5.8, pan 9.2).
  - T1: D42 recorded (the X2216 880KV motors, the STS3215 feed, the red Class 2 laser, the bench items not fitted).
    The catalogue has every v0 part with a listed price, a buy link and a second seller (three research passes:
    Digi-Key and Mouser for the electronics, a second seller for the McMaster hardware, the bench kit and the tools);
    `not_in_a_catalogue`, `no_listed_price` and `no_second_source` are empty in exports/turret/bench/bom.json. Found on
    the way: the MF-R200 does not exist (MF-R250), the SN74HC123N is broker-only (CD74HC123E), the 3557-2 takes ATO not
    MINI blades, no 18 AWG silicone wire fits the Micro-Fit crimp (1.85 mm insulation at most: 1.75 mm PTFE), the
    ring's 28 AWG leads need the 26-30 AWG crimp (43030-0010), the plan's backup laser is a line laser, there is no
    Worker 200-pack, the Micro-Fit crimpers the plan named stop at 20 AWG. Order sheets: exports/turret/bench/orders/
    (cad/turret_orders.py: 100 lines, 18 sellers, $1,559 in whole packs; the servos and motors first).
  - T2: the X2216 drawn from SunnySky's own drawing (cad/turret.py `MOTOR`): bell-down under the cage plate (radial
    slots take its 16/19 cross in any quarter turn), the hub a PA6-CF disc on the motor's bolt-on prop adapter (Ø5
    pilot, M5 stud, washer and nylon-insert nut); the cage plate rises 13.7 mm (plate_z0 42). The heavier motors moved
    the tilting group's centre ahead of the axis when empty, so the tilt axis is now 48 mm ahead of the dial axis
    (`tilt_x`): 8.5 mm behind with 30 balls, 5.2 empty; motion margins tilt 5.9, pan 8.9 (exports/turret/motion.json).
  - T3 (the launch physics rerun here, the physics agent having finished): with the X2216's constants the ceiling on Ø34
    is 67.6 fps at the worst corner (2.3 under the cap), Ø36 70.7 (over): `TYRE_SET` is Ø34 only; the bench keeps every
    ball under 66 fps by checking the no-load speed first (<= 11,180 rpm). The set speed is 8,855 rpm for 52 fps; the
    brake's tau 6.9 ms; the soft start 300 ms (2.5 A at the ring). docs/turret-physics.md sections 0, 4, 5, 9.
  - T4: the feed servo under the dial floor (its face 0.75 mm up in a pocket so the dial sits flat on its horn, 4 x
    M2 x 6 countersunk), the dial on the horn with 4 x M3 x 8 from the top; the M2006 and C610 features gone.
    T5: the feed physics on the servo: a step settles in 232-246 ms; 3 balls/s level and 2.5 at -25 deg on a fixed
    period, so the firmware paces each step on gate 1 (a dither, never a step, if no ball arrives); parked-safe passes.
  - Build package: the print files (exports/turret/print/*.3mf in their print orientations, sliced by Bambu Studio
    for a P1S: 1,291 g, 50 h; docs/turret-print.md with the settings and the schedule); the SendCutSend clamp
    (exports/turret/pan_clamp.dxf, 6061-T6 0.125 in, in the order sheets); the wiring (docs/turret-wiring.md, rewritten
    for v0, with the boards laid out and checked by cad/turret_boards.py); the assembly order regenerated; the bench
    test procedure (docs/turret-bench-tests.md) with the v0 numbers.
  - T8 changed three things in the plan's wiring, each with its reason in docs/turret-wiring.md: the flywheel regulator
    is always on and the 2815 switches its 12 V output (the tilt servo on the always-on 12 V; one regulator fewer: the
    bay's boards could not hold the plan's parts); one 5 A MINI fuse in line in the base protects the ring's 2 A circuits
    (no PCB blade holder fits the heights); and **the 2815's slide switch must be OFF**: with it ON the MOSFET stays on
    whatever ARM does (Pololu's page), so the plan's "slide switch left ON" would have defeated the safety line.
  - Also: the turntable's lightening pockets moved off the shoulder's root (the side-fall peak, SF 1.12); the stand's
    rocker cutout is the Ø20.2 round of the DC-rated Bulgin / Switch Components rockers.
  - Firmware v0 (T7) is with a separate agent in firmware/turret/ (the servo bus with the feed, the gate-paced feed,
    CONFIG from the physics, the AM32 settings, the bench host script).
  - Next: the FEA rerun on this geometry (running: cad/turret_studies.py, summary.json); measure the X2216, a servo and
    the ring in hand (T6); order; print the stand and the pan stack; then T10-T15.
- 2026-10-27 (late): the electrics made buildable part by part and reviewed, the brake modelled as built, and the FEA
  on the v0 geometry (plan T8, T9; decision D47).
  - Four faults in the plan's wiring, fixed first (docs/turret-wiring.md section 3, every part with a designator;
    exports/turret/wiring/parts.md lists them and cad/turret_boards.py counts the parts list's passives from them): the
    arm chain ran on 5 V and fed the Feather's pins, which are not 5 V tolerant (it runs on the Feather's 3.3 V now); a
    5 V 555 drove the opto's LED at about 0.5 mA (the 555 runs on the pendant loop's 12 V: 2 mA); the brake FETs to a
    floating star could stay off (each phase is shorted to GND, as AM32's own brake does); the laser's 2N7000 had
    3.3 V on its gate against a threshold of up to 3 V (the bus buffer's spare channel drives it at 5 V, from A5).
  - Then an independent review of the drawn circuit against the datasheets (a separate agent) found two blockers and
    nine more, all fixed: the trip latch could be cleared by the next slower ball (now set-only); the Feather could
    raise ARM through its own pins (it reads ARM and the pulse train through 100 k); a '123 one-shot fires on a rising
    reset (the CD74HC423E does not; an MCP120 makes the power-up reset); the ESC's phase edges would lift the brake FETs'
    gates (100 nF gate to source); complementary PWM would push the wheels' energy into the buck-fed 12 V rail (off,
    plus TVS diodes, Pololu's Schottky at the 2815 and ramps between set speeds); the RX divider had no margin (a
    Schottky); A4 shares an interrupt line with D10 (PULSE_MON on A3); the Feather's USB pin is its USB-C VBUS (fed
    through a 1N5817); signals into the unpowered ESCs and feed servo (1 k series, DShot low while disarmed); a reversed
    supply (a 1N5822 after the fuse); and any headphone plug would have closed the pendant's 3.5 mm loop (a keyed
    Switchcraft mini-XLR now, and a 0.1 A polyfuse). Also from it: K = 0.475 at 3.3 V (R11 starts at 63.4 k), R9 39 k
    for the 4N35's margin, 1 k gate pull-ups, a bench check of the gates' light (3.10), the hall's bypass capacitor.
  - The firmware and its bench host follow the circuit: 19 firmware tests pass (a new set speed ramps; no DShot frame
    while the ESCs are unpowered) and 33 of 33 simulated bench tests (3.1 reads the 555's frequency, the opto's current
    and every Feather input; 3.3 a slower pair after a trip stays latched; 3.10 the gates' light; 4.10 no FET gate kick
    and no rail over 13 V through a step down).
  - The brake as built: two FETs and the taps make the short 173 mOhm (tau 10.2 ms at low speed, 6.9 for the motor
    alone), and the winding's inductance (not published; 35 uH est, swept 0-50) weakens it at speed: 5 % speed 40-57
    ms after release (48 at 35 uH; it read 30 before), nothing left at the 96 ms when a ball in the chute could arrive.
  - FEA (T9: cad/turret_studies.py on the final geometry, exports/turret/fea/summary.json). Targets: 2 everyday, 1.2 rare.

    | Part | Falls (30 g) | Everyday | Stall / jam |
    |---|---|---|---|
    | tilt yoke | 2.78 / 2.05 / 1.78 | 1.82 (50 N push up at the muzzle; p99 SF 4.4) | |
    | turntable, its teeth | 8.38 / 2.19 | 3.31 (servo cap) | 1.66 |
    | pinion | | 2.7 | 1.35 |
    | pan base | 6.12 / 1.38 | 2.26 (servo cap) | 1.13 (p99 SF 9) |
    | aluminium clamp | 2.89 (lift) | | |
    | **cradle** (across the layers) | **0.78 / 0.62** | **0.77** (the push) | |
    | cartridge | 1.57 | 1.57 (recoil at 66 fps; p99 SF 11) | |
    | dial (PETG) | | 5.75 (jam at the 30 % cap) | 1.72 |

    Changes from it: the yoke's stepped relief is a cone (its 30 g down case 2.25 -> 2.78; the sweep still clean); the
    cartridge's recoil takes the X2216's own loads at 66 fps. Named for v1 (T16): the cradle's cheeks bend across the
    layers (0.77 under a 50 N push with humid PA6-CF, about 1.6 dry): on the bench no pushing on the barrel, keep it
    dry, print a spare.
  - The bench print plan holds v0's parts only with the slicer's numbers (19 parts, 1,292 g, 50 h; the build page reads
    it). The order sheets: 125 lines from 17 sellers, $1,609.89 with the stand and the tools; the boards' passives 94
    pieces for $15.74; every line priced with a second seller.
  - cad/turret_box.py now tolerates the J501's Rev 0.9 parameters (its fan duct became a flush grille); the adapter's
    intake shroud was drawn round the Rev 0.8 duct and needs a look when Rev 0.9 lands.
  - Next: order (the servos and the X2216s first: Waveshare ships from China); print the stand and the pan stack; test-
    fit the TB3M's panel hole; T6's measurements on the parts in hand; then T10-T15.
- 2026-10-27/28: docs/turret-next-plan.md section 4.1, N0-N8 (decisions D48-D52).
  - N0: main 3ceadf8 rebuilt, every number reproduced (1.639 / 1.584 kg, 0 clashes, tilt 5.9, pan 8.9, the cradle 0.78
    / 0.62 / 0.77, 19 firmware tests, 33 of 33 simulated bench tests).
  - N1 (D48): the cradle is a printed rail frame on two SendCutSend 6061-T6 cheek plates with an aluminium stop lug;
    the checks changed the plan's sketch: 10 mm feet (12 passed 0.37 mm over the rotor leads), feet to x -10 (the rail
    cantilevered 46 mm to the rear dowel), a +-10 deg lug band, and a yoke with a 12 mm bridge, 6 mm root fillets, a
    smaller lead window and buttressed stop sectors (its push was 1.07 at first). 1.684 kg with balls; sweep at five
    tilts clean; the rail frame prints in 2.1 h with no supports.
  - N2: every printed part's FEA has a layer-aware column (across 23 / shear 11.5 / along 49 MPa) and the verdict uses
    it; on the final geometry the rail frame 2.51 / 4.29 / 2.22 and the yoke 3.79 / 2.03 / 5.10 / 2.14-2.36 (the full
    run's summary.json with every part follows).
  - N3 (D51): the Lumenier AM32 pair and the gates' 39 k alternates in the first order; $1,686.96, 131 lines, 18 sellers.
  - N4 (D50): the J501 adapter on the committed Rev 0.9 (the fan re-centred): inserts wholly in the deck, a 40 mm gap,
    a 158 mm mouth; 9.2 % of the fan's flow, 3.7 mm to the legs, the box scene clear.
  - N5, N6, N7: mount.json for the body, the lidar table at 143 mm (-16.5 deg worst), the host bridge (20 of 20
    firmware tests, 33 of 33 bench), the robot's DT12 harness and STOP contact (wiring 1.1b).
  - For the body workstream (D52 is already in its code and next plan): docs/body-plan.md still says the grommet at
    (-130, 60) and a "10 A blade fuse" on the turret (it is a 5 A MINI); the STOP relay's pole A carries about 10 mA at
    12 V (the 555's own supply as well as the opto's 2 mA: a gold-clad contact), and pole B closes onto the turret's
    2 x 1000 uF bank (rate it for the inrush or put an NTC in the branch).
  - For the main session: docs/head-payload.md and designs' head_payload take D49's 1.70 kg; cad/leg_studies.py's
    docstring can say the layer-aware post-process applies there (N2's note); designer/turret_bench.js text changes are
    in the report.
