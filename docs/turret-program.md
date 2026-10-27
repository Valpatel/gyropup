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
      set speed with margin, and how the speed varies with ball size and wear. Evidence: docs/turret-physics.md
      section 4 (55.8 +- 1.3 fps at the set speed; 68.0 fps the fastest ball at 100 % on Ø36, 2.0 fps under the cap),
      and the same map on this cartridge's fixed 53.0 mm wheel spacing (Ø34 at 16.2 % crush 64.5 fps, Ø36 67.5,
      Ø38 69.7: cad/turret.py `TYRE_SET` prints Ø34 and Ø36, not Ø38).
- [x] Trajectory and accuracy: drop and drift at 1-5 m, spin (matched wheels: none), dispersion budget. Evidence:
      docs/turret-physics.md sections 6-7, exports/turret/flight/flight.json.
- [x] Recoil per shot and per burst, on the robot (feeds sim/turret.py and the head-payload budget). Evidence:
      docs/turret-physics.md section 8 (0.030 N s per shot, 1.2 mrad of aim).

**Feed**
- [ ] Hopper → dial → chute → wheels: no jam in any pan/tilt pose (gravity direction at -25 deg tilt), double-feed
      impossible, the dial parks safe with the motor off. Parked-safe passes; the end-to-end run had 3 doubles in 108
      steps and 24 % empty steps with the M2006's real 100 ms step (docs/turret-physics.md section 3, finding 1). CAD
      answer: the dial's hub is now a 30 deg cone with four fins that stir the pile at every step
      (cad/turret.py `DIAL_CONE`); the physics agent reruns sim/turret_feed_dyn.py on it.
- [x] Rate of fire: dial speed vs flywheel recovery between shots. Evidence: docs/turret-physics.md sections 4 and 11
      (4 balls/s clean by stepping; the wheels recover their 7 % in ~3 ms at 10 A).

**From the turret-on-Orin-box scene (coordinator, 2026-10-27; cad/turret_box.py on main)**
- [x] Hardware speed ceiling that holds at 100 % throttle (safety, highest priority): at full speed on 24 V the
      Snails would throw ~37 m/s (123 fps). The design answer here: the flywheel ESCs on their own regulated 12 V
      rail and Ø36 tyres at 25 % crush, so the motors' no-load speed caps the ball; the chronograph lockout is the
      backup. Evidence: docs/turret-physics.md section 4 (68.0 fps the fastest swept ball, Ø34 64.5 on this cage);
      the fixed 12 V regulator is on the parts list (exports/turret/bench/bom.json el_flywheel_regulator, Pololu 2885)
      and the rule is in the hard rules above. The bench's V13 test (100 % throttle on the real rail) confirms it.
- [ ] ARM release is not instant: a dropped ball still fires ~96 ms after ARM is released and the wheels coast
      ~1.4 s. Enable active braking in the ESCs (AM32), and add a fail-safe gate that holds the dropped ball at the
      chute (spring-closed, opened only while armed). The same gate pre-stages the next ball (item below).
- [ ] Command to muzzle takes 146 ms, 86 ms of it the ball's drop through the chute: pre-stage a ball at the gate.
- [ ] Firing backwards: at pan 140 deg the muzzle clears the deck's rear corner by 3 mm, where the operator stands.
      Add a pan keep-out behind and check the muzzle's clearance at every pan and tilt (a general obstacle check,
      as for the lidar).
- [ ] Torque caps: the tilt holds with a 15x margin and slewing is speed-limited (~100x torque margin). Cap both
      servos' torque in firmware to protect the printed gear and fingers (the pinion is the weak tooth: see the FEA).
- [ ] Box-specific, for cad/turret_box.py when the turret's base changes: the antennas collide at full depression,
      the stack tips at a 10.6 N push, the shroud costs ~7 % of the fan's airflow (est).

**Structure and motion**
- [ ] Strength of every printed load path (pan ring and gear teeth, yoke, cradle, cartridge, barrel mount) under
      slewing, recoil, a drop of the robot and handling, with the cad-agent FEA and its overload videos.
- [x] Servo torque margins (STS3215 pan through 63:21, tilt direct) for the turret's inertia at the wanted slew rates.
      Evidence: exports/turret/motion.json (cad/turret_motion.py, with the slip ring and the boards): tilt move 5.9,
      hold 47.6, world-frame 21.9; pan 90 deg in 1.2 s with a margin of 10.0 at the 50 % torque cap, yaw 104; the
      pinion (16 mm face, full-round roots) SF 2.52 at the cap and 1.26 at stall by FEA of one tooth.
- [ ] Clearances and stops over the whole pan/tilt range, including the lidar in front and the DT12 harness. The
      turret itself is clear: no overlap and nothing moving within 1 mm but the designed tilt stops, at pans 0-350
      every 10 deg x tilts 0 and -25 (exports/turret/clash-sweep.json), and every degree where the cradle passes over
      the pan pinion at full depression (2.5 mm, exports/turret/t1-fine-checks.json). The lidar table is rerun next.
- [ ] Mass: 1.594 kg with a full hopper (exports/turret/turret.json) against the head payload's 1.5 kg
      (docs/head-payload.md): the slip ring, its carrier and driver, and the two board bays added ~250 g. Cut at least
      100 g (infill where the FEA allows, a lighter carrier and bay) or agree a new budget with the leg's sizing.

**Build**
- [ ] Every printed part: orientation, supports, bed fit, print time; tolerances for bearings, inserts and the gear.
- [ ] Every bought part with a real part number and price; nothing left as "estimate" that can be sourced.
      Each line carries a catalogue key, part number and source URL, so the BOM can show its thumbnail and its
      alternates: done for every line (exports/turret/bench/bom.json, `not_in_a_catalogue` empty; cad/build_turret.py
      calls cad/bom_media.py enrich()). Open: the electronics' prices are estimates until ordered; the robot ring
      (Senring M220-0210-12S) is a quote. Hard to buy (catalog/sourcing.json risk): the Snail 2305 (DJI delisted it;
      backorder) and the M2006 and C610 (out of stock; the Damiao DM-2325 with its own driver is the alternate and
      needs a new dial-motor mount); the Picotronic laser ships only from Germany. No buyable alternate within the
      speed rule yet for the Snail: a drone motor needs its own lower rail (hard rules).
- [ ] Wiring: power (24 V → 12 V buck for the servos/laser), the ESCs, the M2006 + C610, CAN, the DT12 pinout. The
      slip-ring hold is lifted (docs/turret-plan.md, main 5f09bd9): the ring, its carrier and driver, the index and
      both board bays are in the CAD; the wiring page (plan task T2) is next.
- [ ] Assembly order with pictures; a bench test plan (chronograph, accuracy, jam rate, the pendant).

**Awesome**
- [ ] Sounds, look and feedback (the laser, lights) on the 3D page match the real thing.
- [ ] Reload at the dock: the hopper's fill port and flap.

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
