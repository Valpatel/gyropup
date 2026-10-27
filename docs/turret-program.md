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

## Where it sits

- On the robot (body not designed yet): behind the VLP-16 lidar on the top deck, firing over it (user, 2026-10-26).
  The ball path and the barrel must clear the lidar at every allowed tilt, or a pan-dependent depression limit applies.
- On the bench: `cad/turret_stand.py` (24 V in, fuse, switch, USB-CAN, hold-to-run pendant).
- Interface to the robot: the TM pattern (4 x M5 on 80 x 80, 2 x Ø5 dowels, Ø45 cable hole) and the DT12 connector.

## Validation checklist

Tick with a link to the evidence (file, picture, result JSON). Unticked = open.

**Ball and launch**
- [ ] The ball: Rival-size foam ball diameter, mass and its spread from real products (sourced); the bore, chute and
      dial clearances checked against the spread.
- [ ] Flywheel launch model: wheel speed, crush, contact time, slip → muzzle speed; at or under 70 fps at the motors'
      set speed with margin, and how the speed varies with ball size and wear.
- [ ] Trajectory and accuracy: drop and drift at 1-5 m, spin (matched wheels: none), dispersion budget.
- [ ] Recoil per shot and per burst, on the robot (feeds sim/turret.py and the head-payload budget).

**Feed**
- [ ] Hopper → dial → chute → wheels: no jam in any pan/tilt pose (gravity direction at -25 deg tilt), double-feed
      impossible, the dial parks safe with the motor off.
- [ ] Rate of fire: dial speed vs flywheel recovery between shots.

**Structure and motion**
- [ ] Strength of every printed load path (pan ring and gear teeth, yoke, cradle, cartridge, barrel mount) under
      slewing, recoil, a drop of the robot and handling, with the cad-agent FEA and its overload videos.
- [ ] Servo torque margins (STS3215 pan through 63:21, tilt direct) for the turret's inertia at the wanted slew rates.
- [ ] Clearances and stops over the whole pan/tilt range, including the lidar in front and the DT12 harness.

**Build**
- [ ] Every printed part: orientation, supports, bed fit, print time; tolerances for bearings, inserts and the gear.
- [ ] Every bought part with a real part number and price; nothing left as "estimate" that can be sourced.
      Each line carries a catalogue key, part number and source URL, so the BOM can show its thumbnail and its
      alternates (coordinator, 2026-10-27: tools/part_images.py and cad/bom_media.py enrich() are being built in
      the main checkout; call enrich() in the turret's BOM once it lands). Parts with no buyable source or no
      alternate are listed here.
- [ ] Wiring: power (24 V → 12 V buck for the servos/laser), the ESCs, the M2006 + C610, CAN, the DT12 pinout.
      **On hold (coordinator, 2026-10-27):** the user wants a high-quality electrical slip ring in the pan joint; a
      separate planner is researching the ring and the electrical architecture across the pan axis
      (docs/turret-plan.md, research/turret-slip-ring.md in the main checkout). Until that lands: keep the pan axis
      and the centre hole free for a ring, add no hard pan stops that would rule out continuous rotation, and do not
      finalise the pan joint's cable path, the wiring or the DT12 pinout.
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
