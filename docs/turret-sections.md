# The turret, section by section

The turret's mechanical design broken into its six sections, each reviewed on its own: what it must do (with numbers),
how it meets its neighbours, every part (material, process, how it is held), each design decision with the
alternatives turned down, and the checks that prove it. The CAD is `cad/turret.py`; the numbers below are its `Geo`
values (mm, degrees). The design gates are `cad/turret_gates.py` (the turret's parts through the generic checks in
`cad/gates.py`), stored in `exports/turret/gates.json` and enforced by `cad/build_turret_box.py`, which will not build
the 3D page's scene from a model that fails them or from a stale result.

Since D66 the turret is a robot of its own: its own Jetson and power input in a compute plinth under the pan base
(section 7), on Gyropup's head or on its own stand with a FLEXVOLT pack (section 8).

Frames: T, the turret frame (origin on the pan axis at the pan base's mounting face, z up; the compute plinth is below
it, z -86 to 0); C, the cartridge frame (x along the
barrel, the dial axis at x = y = 0, the ball path at z = 0). At tilt 0, C sits 125 mm (`path_t`) over the mounting
face and 48 mm (`tilt_x`) behind the pan axis; the tilt axis is at C (48, y, 15), over the pan axis.

The parts rule (D40): every part is bought at a listed price, printed, or cut at an instant online price. Kid safety
is a hard rule: the barrel never above level (hard stops at 0 and -25 deg), at most 105 fps by the hardware (D68: about 100 fps for a Hasbro round, under ASTM F963's 2,500 J/m2; eye protection recommended, as Hasbro does), and
nothing spins unless the ARM line is held.

## The design gates (all sections)

| Gate | What it proves | Pass |
|---|---|---|
| `hopper_in_cavity` | each of the 30 balls of a full hopper (the settled pile and the 8 dial pockets) against every solid of the tilt group, the dial parked | every sphere-solid intersection under 1 mm^3 |
| `hopper_overlap` | no two balls through each other | worst overlap 0.1 mm or less |
| `path_in_cavity` | a ball every 2 mm along its way, the exit pocket to the muzzle, against every solid (the dial at its step angle); only the tyres may touch it, at the nip | under 1 mm^3 |
| `connected` | one connected body per moving group (base, pinion, pan, tilt, dial, each flywheel, the fill flap): every part touches a neighbour or is fastened through a declared link, and every joint between moving bodies is closed (within 0.5 mm) | 1 body each, all joints closed |
| `ammo_range` | D67: any Rival-compatible round 22.2-22.8 mm (1.6-2.0 g) feeds and fires: the biggest ball along the path and in every pocket clear of the solids, the smallest one to a pocket and still squeezed at the nip, the bore's play for both | pass: pocket 25.06 mm long (two balls need 44.4), nip squeeze 23.3-25.3 %, bore play 1.4-2.0 mm (feed and chute), 1.9-2.5 mm (barrel) |
| `sweep_with_balls` | the hopper's balls against every part outside the tilt group at 8 pans x 5 tilts | under 1 mm^3 |

The clash sweep of the parts themselves is `turret.sweep()` (every pan in 10 deg steps at 0, -5, -12.5, -20 and
-25 deg tilt; `exports/turret/clash-sweep.json`).

The pile is a physics settle, not hand-placed rings: `sim/turret_feed.py --pile` (MuJoCo, run on a GB10) drops 30
balls through the fill port onto the dial's real cone and fins, parked, a ball seated in each pocket, and lets them
rest (slowest ball 0.0009 m/s at the end). `exports/turret/feed/pile.json` holds the result; the gates and the 3D page
both read it.

---

## 1. Base and pan drive

**Function.** Carry the whole turret on the head's mounting face (TM) and turn it continuously (no pan stop: the slip
ring passes power and signals), 3:1 off an STS3215, at up to the servo's rate, with an absolute index at pan 0.

**Requirements.**
- Mount: the TM bolt pattern; 4 x M5 into the head ring; 2 x Ø5 dowels locate it.
- Bearing: carry the tilting group (1.68 kg with 30 balls) plus a 1.2 x fall load (FEA cases `R-fall-down`,
  `R-fall-side`) and the reaction of the gear mesh; 61810-2RS (50 x 65 x 7).
- Drive: 63:21 spur pair, module 1.25, centre distance 52.65 (52.5 + 0.15 mm backlash allowance).
- Index: a hall switch on the turntable 3.5 mm over a magnet on the base (760 G, 4 x the A1120's operate point).
- Clear the DT12 plug's 30 mm withdrawal path with the turret parked.

**Interfaces.** TM face (z 0) to the compute plinth's top (4 x M5 x 16 into inserts in its columns; section 7); the 61810's outer race in the base (clamped by `pan_clamp`), its inner race
on the turntable's journal (DIN 471-50 circlip below); the yoke bolts to the turntable's top (z 69, 4 x M4 into
inserts); the slip ring's stator in the ring carrier under the base, its rotor turned by the driver in the turntable's
bore (section 6).

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| `pan_base` | PA6-CF, printed on its foot, 4 walls 40 % gyroid | 4 x M5 x 16 into the plinth's column inserts, 2 x Ø5 dowels |
| `pan_clamp` | 6061-T6 0.125 in, SendCutSend | 3 x M3 into inserts in the base; clamps the 61810 outer race |
| `pan_bearing` | 61810-2RS, bought | outer race in the base's housing under the clamp |
| `pan_ring` (turntable) | PA6-CF, printed upside down (teeth on the bed), solid | its journal through the inner race, DIN 471-50 circlip |
| `pan_spacer` | PA6-CF | between the inner race and the circlip |
| `pan_pinion` | PA6-CF, solid | 4 x M2 to the pan servo's horn |
| `pan_servo` | Feetech STS3215, bought | four posts on the base, plugs from below |
| `bumper_ring` | TPU 95A | 5 x M3 with washers on the base's tabs |
| `index_magnet`, `hall_switch` | bought | the magnet glued on the housing top through the clamp; the hall CA'd against the roof of a pocket in the turntable's underside |

**Decisions.**
- *A ring gear on the turntable driven by a servo beside it*, not a servo under the axis: the axis stays open (40 mm)
  for the slip ring and the cable. Rejected: a direct-drive servo on the axis (blocks the ring; no continuous pan).
- *3:1 on a 63 T ring:* the STS3215's 360 deg absolute range then covers 120 deg of pan; the hall index and counting
  turns give the absolute pan (docs/turret-plan.md 3.2). Rejected: 1:1 (too little holding torque against a push on the
  barrel), 4:1 (too slow a slew).
- *A thin-section 61810* over a pair of small bearings: one part carries the overturning moment with the 50 mm bore free.
- *The hall in a closed-roof pocket* (rev. 2026-10-27): the first pocket was open 0.2 mm above the switch, so it was
  drawn floating; now the switch is glued up against the pocket's roof (found by the `connected` gate).

**Checks.** FEA `pan_base` / `pan_ring` / `pan_pinion` (cad/turret_studies.py, exports/turret/fea/); the gear check
`turret.pinion_check()`; the clash sweep; `connected` (base, pan, pinion one body each; joints: the 61810's races, the
pinion on its horn, the mesh). Open: `pan_pinion R-stall` reads 1.05 layer-aware against 1.2 and `pan_base E-cap-servo`
1.14 against 2.0 in the layer-aware post-process (isotropic 1.2 and 2.26 pass); see the FEA summary.

## 2. Tilt yoke and cradle

**Function.** Hold the cartridge on a horizontal axis over the pan axis and tilt it 0 to -25 deg (muzzle down) off an
STS3215 directly, with hard stops at both ends so the barrel can never point above level.

**Requirements.**
- Tilt axis at C (48, 15): the tilting group's centre of mass 8.5 mm behind it with 30 balls, 5.2 mm empty, so an
  unpowered barrel rises onto the 0 deg stop and never drops onto the lidar ahead.
- Stops: 0 and -25 deg, metal on printed sectors, taking the servo's stall torque.
- FEA targets: 1.2 on the rare cases (falls), 2.0 on the everyday ones (a push on the muzzle), layer-aware.

**Interfaces.** The yoke's bridge on the turntable (4 x M4 x 10, heads 6 mm down in the 12 mm bridge); the tilt servo
on the +y arm, its horn on the horn boss on the +y plate (4 x M3 x 14 flat heads); an MR126 in the -y arm, a Ø6
shoulder screw through it and the pivot spacer into the -y plate; the cartridge on the cradle's rails (2 dowels and a
thumbscrew, `ct_thumbscrew`).

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| `tilt_yoke` | PA6-CF, printed on its back (layers along the arms), solid | 4 x M4 x 10 to the turntable |
| `cradle` (rail frame) | PA6-CF, flat, no supports | 8 x M3 inserts take the plates' button heads |
| `cradle_plate_l`, `cradle_plate_r` | 6061-T6 0.125 in, SendCutSend (DXFs in exports/turret/) | 4 x M3 x 8 button heads each into the rail's inserts |
| `stop_lug` | 6061-T6 0.100 in, SendCutSend, 2 holes tapped M3 | 2 x M3 x 6 flat heads from the -y plate, CA gel |
| `horn_boss`, `pivot_spacer` | PA6-CF | clamped between the plates and the horn / the MR126 |
| `tilt_servo` | STS3215 | 4 x M2 x 10 from the arm's inner face, in a pocket whose walls run out over the whole case (34.9 mm; 15 until 2026-10-27, when the servo stood 19 mm proud of them) |
| `tilt_bearing` + `shoulder_screw` | MR126 (6 x 12 x 4), Ø6 shoulder screw | bearing pressed in the arm; screw through the spacer into the plate |

**Decisions (D48).**
- *Aluminium cheek plates on a printed rail frame*, not printed cheeks: the printed cheeks failed the layer-aware push
  case (interlaminar shear across the cheek's layers); 3.2 mm 6061 carries it in-plane. Rejected: a printed cradle on
  its side (layers then fail the rail), a machined cradle (quote only, against D40).
- *Direct drive off the servo's horn*, no gears: the STS3215's 30 kg.cm holds the group's 0.11 N.m with margin (the
  holding check in the box build); a gear would add backlash at the muzzle.
- *A metal stop lug against printed sectors:* the lug takes the impact, the yoke's sectors are true arcs clipped to the
  arm with buttresses (FEA: 2.14 to 2.36 layer-aware on the push case).
- *10 mm rail feet* (from 12): 2.37 mm over the slip ring's rotor leads at full depression (was 0.37).

**Checks.** FEA `tilt_yoke`, `cradle`, `cradle_plate_l/r`, `stop_lug` and the hand checks (horn screws, lug screws,
pivot land, the -y plate out of plane, inserts, the pivot thread); the clash sweep with `STOP_PAIR` touching only at 0
and -25; `connected` (tilt one body; the MR126's races, the horn on its boss).

## 3. Feed: hopper, dial, exit, chute

**Function.** Hold 30 balls and hand exactly one at a time to the flywheels on command, three a second; with the dial
parked, powered or not, no ball can reach the wheels.

**Requirements.**
- 30 Rival rounds (D67: Hasbro's own or any Rival-compatible round 22.2-22.8 mm and 1.6-2.0 g; design ball 22.7 mm,
  1.83 g), bores ball + 1.5 = 24.2: 1.4 mm of play for the biggest round, 2.0 for the smallest (the `ammo_range` gate).
- The ammo bought (D67): a third-party 100-pack (Worker Cheetah, US$0.15 a round) and the official Nerf Rival 60
  Accu-Round refill (Hasbro F5052, US$0.33 a round), side by side, cheapest first.
- One ball per 45 deg step, no double feed, no empty step while balls remain (sim/turret_feed.py: every pose,
  friction 0.4-1.0, 3 and 8 balls/s).
- Parked: a spoke over the exit hole.

**Interfaces.** The dial on the feed servo's horn (4 x M3 x 8 from the top, through holes in the cone); the hopper on
the cartridge's dial housing (3 x M3 lugs); the exit hole in the housing floor under the front pocket (C x 37); the
chute, a quarter bend of radius 21.35 inside the cartridge body, turning the ball onto the path (z 0) at C x 58.35.

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| `dial` | PETG, printed on its bottom, cone up | 4 x M3 x 8 into the feed servo's horn |
| `hopper` | translucent PETG, upright | 3 x M3 to the housing |
| `hopper_lid`, `hopper_flap` | PETG | the lid's spigot in the hopper; the flap on a Ø2 pin with a torsion spring |
| `feed_motor` | STS3215 (ID 3) | under the housing floor, its face in a 0.75 mm pocket |

**Decisions.**
- *An 8-pocket dial under a gravity hopper* (study 8): one servo, the pocket sets the dose. Rejected: an auger (jams
  on foam), a pusher (two moving parts and a magazine).
- *Pitch radius 37*: the gap between 4 mm spokes at least the bore.
- *A 30 deg cone with four fins on the dial*: the pile's middle rolls out to the pockets and the fins stir it at every
  step (physics finding 1: without them 3 of 7 pockets filled under a settled pile).
- *The baffle over the exit pocket* (+-24 deg): nothing refills the pocket over the hole, so one ball per step.
- *Hopper top at 100*: a physics fill fits 29 balls under 95, 34 under 100.

**Checks.** `hopper_in_cavity`, `hopper_overlap`, `path_in_cavity` (the chute), `sweep_with_balls`; the feed sim's
verdict (exports/turret/feed/feed.json: double feeds 0, parked leaks 0).

## 4. Launcher: flywheel cage, motors, nip

**Function.** Throw a Rival round like a stock Rival flywheel blaster, about 95-100 fps (29-30.5 m/s), from two
counter-rotating wheels that squeeze it 40 %, and never let any accepted round leave above 105 fps: the ceiling is the
hardware's, not the firmware's (D68).

**Requirements.**
- A Hasbro Rival round (22.7 mm, 1.83 g) leaves at 95-100 fps at full throttle.
- No accepted round (D67: 22.2-22.8 mm, 1.6-2.0 g, any foam stiffness 0.75-3 MPa and grip 0.6-1.0) leaves above
  105 fps at 100 % throttle, with the whole tolerance stack: the motors' KV spread, the rail's regulation, the motors
  warm, 0.15 mm tyre runout, the tyres' growth at speed, the feed's entry offsets. The densest accepted round stays
  under ASTM F963's 2,500 J/m² (D68's safety basis).
- The flywheels run from a fixed regulated rail whose no-load speed is the ceiling; no firmware setting can exceed it.
  The rail must be reachable from both supplies (D66): one DCB609 in 20 V mode (15-20.5 V under load) and Gyropup's
  10S bus (30-42 V).
- Every rating holds at the ceiling: the motors' voltage, current and speed, the ESCs' voltage, the tyre and the hub
  at speed.
- Nothing spins unless ARM is held (the ESCs' supply is switched by the safety line; phase-short brake on release);
  the chronograph trips at 105 fps.

**Interfaces.** The motors hang bell-down under the cage's top plate (z 42 to 45.5 in C), the hubs on the prop adapters
(washer + M5 nylon-insert nut), the tyres' mid-plane on the ball path, the motors' axes at C x 73, y ±25.81 (51.62
apart); the cage's shells on Ø42, cut to Ø43 over the Ø38 tyres; the barrel socket at the cage's front (C x 98). The
rail: the TDK i6A4W's output to both ESCs through the safety switch, its trim resistor on the board beside it.

**Parts.** `cartridge_body` (PA6-CF; the dial housing, chute, cage and barrel socket in one print), `flywheel` x 2
(PA6-CF, a Ø30 x 12 rim, reamed to 5.00), `flywheel_tyre` x 2 (TPU 95A, Ø38 x 12, 4 mm thick, printed 4 % under the
rim and **bonded** to it), `flywheel_motor_l/r` (SunnySky X2216 1400KV V3, short shaft, $24.99: SunnySky USA,
ReadyMadeRC), `esc_l/r` (Repeat Robotics AM32 35 A), the flywheel rail (TDK-Lambda i6A4W020A033V-001-R, $47.46
Digi-Key, Newark backup; catalog `tdk-lambda-i6a4w020a033v-001-r`), `cartridge_board`.

**Decisions.**
- *Horizontal wheels either side of the path*, motors above: the ball's spin axis is vertical (no lift), and the
  motors sit over the cartridge, not beside the barrel.
- *One printed cartridge body* for the housing, chute, cage and socket: the ball's path is in one part, so nothing can
  step at a joint. Rejected: separate cage and housing (a seam across the chute).
- *40 % crush on Ø38 tyres* (sim/turret_launch.py `crush_choice`). With Coulomb friction a ball that slips through the
  whole nip leaves at a speed set by its grip, not the wheel speed (on the old Ø34 at 16 % the Hasbro ball tops out at
  ~48 fps on any rail); with enough crush it catches the tyre and leaves at ~0.95 of the surface speed, the regime
  D68 needs, because the ceiling is the surface speed (the stiff, grippy light ball leaves at 0.97-0.98 of it). The
  Hasbro ball at 100 %: 86 fps at 32 % crush, 95 at 36 %, 97 at 38-44 %; 40 % leaves room for a softer foam than the
  model's. Ø38 at 40 % puts the axes 51.62 apart, so the cage is as wide as it was (cage_y 49.3 against 49.0); the
  hub's rim grows to Ø30 and the wheels move 2 mm forward with the nip. Rejected: Ø36 at 31 % on the old cage (the
  Hasbro ball 82 fps), Ø40 at 49 % (the worst corner 108.5 fps on the same rail, and more squeeze on the bearings).
- *The X2216 1400 KV on an ~11.3 V rail, not the 880 KV on ~18 V* (sim/turret_launch.py `routes`). Both reach the
  same no-load speed; the 880 KV needs 17.1-18.9 V (5S, over the X2216's 2-4S rating) and a buck-boost from a pack
  that sags to 15 V; the 1100 KV (13.7-15.1 V) and 1250 KV (12.1-13.3 V) sit too close to 15 V for a buck. The
  1400 KV needs 10.8-11.9 V: inside its rating, and a plain buck holds it from both supplies. Same can, stator, shaft
  and prop adapter, so the hub and cage plate do not change. The cost: ~16 W of no-load loss a motor at speed.
- *The rail trimmed per turret* (one fixed resistor on the TDK i6A4W's TRIM pin, chosen on the bench so the faster
  motor, warm, turns 15,722 rpm at 100 % throttle). A fixed set point carries the KV spread (+5 %, est) and the
  converter's ±4 %: then the rail either holds the worst corner at 104 fps with the Hasbro ball at 92, or gives the
  Hasbro ball 95 and the worst corner 107 (`trim.untrimmed`): both D68 numbers at once are impossible untrimmed. The
  trim leaves the magnets warming 15 °C past the trim (+1.8 %) and the rail's drift and the eRPM reading (+2.0 %). The
  speed limit alone would allow 15,930 rpm (Hasbro 98.4 fps), but D67's densest round (2.0 g on 22.2 mm) would then
  carry 2,537 J/m²; the trim aims it 1 % under ASTM's 2,500. Rejected: a Pololu D42V110F12 (fixed 12 V, ±4 %, $59.95:
  no trim), a pot (it can be turned), KV-binned motors (SunnySky publishes no KV tolerance to bin on).
- *The tyres bonded to the hubs* (a cyanoacrylate for elastomers over the 4 % stretch). At ~16,000 rpm a free TPU ring
  (E 10 MPa) grows 8 % in its bore, twice the stretch: the tyre would float, grow 2.4 mm, crush the ball 61 % and
  throw 113 fps. Bonded, the face grows 0.04 mm.

**Numbers** (sim/turret_launch.py and sim/turret_launch3d.py, run on the GB10s 2026-10-27):

| | Value |
|---|---|
| Hasbro ball flat out / at the 95 fps set speed | **97.1 fps** / 95.0 fps at 15,286 rpm (97 % of no-load) |
| Fastest accepted ball, every tolerance (3D: feed offsets, runout, growth) | **103.9 fps** (1.6 g, 22.8 mm, soft and grippy): 1.1 fps under 105 |
| Densest accepted ball (2.0 g on 22.2 mm), every tolerance | **2,480 J/m²** at ~101.6 fps (ASTM 2,500) |
| Accepted population at the set speed / flat out | 92.4 ± 4.9 fps / 94.1 ± 5.5, max 99.3 (the tail: soft, slippery foam) |
| Squeeze per tyre: Hasbro / stiffest corner | 71 N / 276 N for ~5 ms |
| Wheel speed lost per shot; bursts at 3-10/s | 5.7 %; no droop |
| Recoil | 0.052 N s a shot, 95 N peak on the cage, 1.43 N m about the tilt axis for 5 ms: a 2.1 mrad kick inside the tilt lash |
| Firmware | eRPM guard 16,390 rpm (114,730 eRPM), trip 105 fps, set 40-100 fps (95 default), ramp 800 ms |

**Ratings at the ceiling** (the trim with every tolerance: 16,330 rpm, 32.5 m/s at the tyre).

| Item | Rating | At D68 | Margin |
|---|---|---|---|
| X2216 1400 KV voltage | 2-4S, 7.4-16.8 V (SunnySky) | 10.8-11.9 V | 4.9 V under 4S full |
| X2216 1400 KV current | 33 A for 30 s (SunnySky) | 10 A AM32 limit; ~4 A in the 800 ms ramp | 3.3x at the limit |
| X2216 speed and bearings | not published; the same can and bearings are sold as the 2600 KV on 3-4S (~40,000 rpm) | 16,330 rpm | ~2.5x |
| Bearing load | not published (est 3-4 mm bore miniatures) | 71 N (Hasbro) to 276 N (stiffest ball) a tyre for 5 ms, overhung ~13 mm past the front bearing | the open item: check on the bench (runout after 1,000 shots) |
| AM32 ESC voltage | Repeat 35 A: 9-25.2 V (3-6S); Lumenier: 2-6S | 10.8-11.9 V | 1.8 V over the minimum; 13 V under the maximum |
| AM32 eRPM | not stated; est: AM32 runs ~2,000 KV racing motors on 6S, ~300,000 eRPM | 114,300 eRPM | ~2.5x (est) |
| TDK i6A4W | 9-53 V in, 20 A / 250 W out, 27 A over-current | 15-42 V in; ~89 W in the ramp, 2 x 10 A x 11.3 V for a recovery pulse | 11 V over the 10S full; 2.8x / 1.1x |
| TPU 95A tyre (Bambu: 27.3 MPa tensile, E 9.8 MPa) | | bonded: hoop ≤ 0.12 MPa, the bond's tension 0.26 MPa; free ring 1.29 MPa | 21x on the free ring; the bond (CA on TPU, est ≥ 2 MPa) ~8x |
| PA6-CF hub (Bambu: 102 MPa; D33's humid, printed knock-down x0.6 x0.8 = 49 MPa, 23 across layers) | | rim: 0.72 MPa its own, + 1.3 MPa from the bonded tyre's pull | ≥ 11x across the layers |

**Checks.** `path_in_cavity` (only the tyres touch the ball, at the nip; 0.35 mm tightest elsewhere); `connected`
(each wheel one body on its motor); sim/turret_launch3d.py's `ceiling` (holds, under ASTM) and `ceiling_map`;
sim/turret_dynamics.py (recoil, tilt servo margin 4.3); the cage FEA (recoil); firmware/turret's tests (the 105 fps
trip, the eRPM guard at 16,390 rpm). On the bench, before any ball: the trim (test 4.1: the faster motor warm at or
under 15,722 rpm on its resistor), each tyre spun at that speed, the trip pairs (1.80 ms latches, 1.95 ms does not),
the winding's inductance (the release brake: 5 % at ~80 ms if it is 14 uH as estimated); then Hasbro rounds flat out
(95-100 fps) and the lightest and densest off-brand rounds (all ≤ 105). Everyone in range wears eye protection, as
Hasbro recommends for Rival.

## 5. Barrel and laser

**Function.** Guide the ball out straight, time it (two IR gates 60 mm apart, a built-in chronograph that trips the
safety line over 105 fps), and show the aim with a laser parallel to the bore.

**Parts.** `barrel` (PETG, standing; Ø30 x 100, bore 24.7 from the nip on, the last 15 mm blaze orange),
`laser_mount` (PETG ring on the cradle's laser tab, 2 x M3), `laser` (Quarton VLM-650-03, < 1 mW, Class 2) held by
three M3 nylon-tip boresight screws, 2 mm clear of the ring's bore.

**Decisions.** *Bore ball + 2.0 past the nip* (finding 14: the ball rides the floor and rolls to a steady topspin;
pitch scatter 11.5 to 5 mrad); *the laser on the cradle, not on the barrel*, so the barrel can be swapped without
re-boresighting.

**Checks.** `path_in_cavity` through the barrel; `connected` (the laser fastened through its boresight screws);
the box build's `ball_path` (the ball's way out at every pan and tilt clear of the deck and antennas, 10 mm margin).

## 6. Wiring and slip ring

**Function.** Carry 12 V power, the servo bus, CAN and the safety line from the fixed base to the turning head, for
continuous pan.

**Parts.** `slip_ring` (SparkFun ROB-13065, 12 x 2 A, the stator in `ring_carrier` under the base), its rotor stub
turned by `ring_driver` (PA6-CF, in the turntable's bore: three crush ribs and CA) through `ring_coupling` (McMaster
51225K24, 3/16 in ID TPV tube, 25 mm), `ring_leads_rotor` (the rotor's leads, up the axis, along the bridge, through the
-y arm's window to the board bay), `board_bay` (PETG tray on the -y arm, three boards) and its snap lid
`board_bay_lid` (modelled since 2026-10-27: the bay is a closed pod, not an open tray; the clash sweep then found
the board stack 0.8 mm out of the bay's open face, so the bay is 3 mm deeper, to y -118), `dt_receptacle` (DT12 on the
base, the robot's harness).

**Decisions.**
- *A compliant tube coupling* between the rotor stub and the driver: the ring is driven, never pushed, and the tube
  takes the misalignment between the base and the turntable. *Changed 2026-10-27:* the 5/16 in ID tube first chosen
  sat 1 mm loose round the Ø6 stub and could not drive it (the `connected` gate found the rotor floating); the 3/16 in
  ID tube stretches 26 % over the stub and grips it, its other end pushed into a Ø7.64 socket (0.3 mm squeeze).
- *Boards on the yoke* (turning with pan), so only power, bus, CAN and the safety line cross the ring.

**Checks.** `connected` (the rotor turned by the coupling; the leads part of the ring), the clash sweep at every pan
(the leads 2.37 mm under the rails at full depression), docs/turret-wiring.md for the pin map.

## 7. Compute and power (D66)

**Function.** Make the turret a robot of its own: its own computer, one power input that takes both the stand's
battery and Gyropup's bus, and its fuses, all inside the turret, so it can be built, tested and played with before
Gyropup walks, and a fault in one robot does not take the other down.

**Requirements.**
- Compute: a Jetson Orin NX 16 GB (the user's choice) on Seeed's reComputer Mini carrier (88 x 56 x 17 mm board,
  12-54 V on an XT30), up to 40 W in its top power mode (10-40 W), cooled by a fan and heat sink sold for the NX on
  that carrier; Ethernet to the J501, CAN to the turret's own MCU through the slip ring.
- Input: one XT30, 12-54 V: one DCB609 in 20 V mode on the stand (15-20.5 V, down to 15 V when empty), Gyropup's 10S
  bus on the robot (30-41 V, 42 V full; D65), each through its own 58 V fuse (D55).
- Nothing hung outside: the computer, its cooling, the input, the fuses and the leads in pockets with mounts.
- The interface to Gyropup unchanged in kind: the TM bolt pattern (4 x M5 on 80 x 80, 2 x Ø5 dowels), the XT30
  branch, Ethernet, the dry safety loop (DT12, as before).

**The power budget** (the flywheels' share follows section 4's rail once D68's resize lands):

| Load | Typical | Peak | Note |
|---|---|---|---|
| J4012 (NX 16 GB + carrier + fan + NVMe) | 20-25 W | 48 W (40 W module, est. 8 W carrier, fan, SSD) | 3.2 A at 15 V, 1.2 A at 41 V |
| Turret MCU, regulators, lights, laser | 3 W | 5 W | |
| Servos (pan, tilt, feed; STS3215 at 12 V) | 3-5 W | 3 x 2.7 A stall at 12 V (est. 100 W for a moment) | torque-capped at 50 % in firmware |
| Flywheels (while ARM is held) | see section 4 | see section 4 | the converter's input current limit holds the spin-up peak |

On one DCB609 (9 Ah in 20 V mode, about 160 Wh usable): **about 4 h** at a typical 40 W (the NX at 25 W, the
turret idling between shots), **about 2.2 h** with the NX flat out at 48 W and the turret playing (73 W average,
est.). The main fuse is a 20 A MINI 58 V (the stand's own and the turret's input), the J4012 a 5 A MINI 58 V branch.

**Interfaces.** The plinth's underside carries the TM pattern (4 x M5 x 16 down into the head's or the stand's
inserts, 2 x Ø5 dowels); its top carries the pan base (4 x M5 x 16 into inserts in the plinth's four columns); the
XT30 input and the RJ-45 jack in the -x wall (the operator's side); CAN and power to the slip ring's stator leads
above the J4012; the head's Ø45 TM cable hole is no longer used (the plinth's floor closes it).

**Parts.**

| Part | Material, process | Held by | Price |
|---|---|---|---|
| `compute_tray` | PA6-CF, flat, 4 walls 40 % gyroid; Ø156 x 10 | 4 x M5 x 16 into the head (put in first), 2 x Ø5 dowels; 4 x M4 inserts for the shell | printed |
| `compute_shell` | PETG, upside down; Ø156 ring, 2.5 mm wall, 4 columns, vents | 4 x M4 x 10 down into the tray; 4 x M5 inserts take the pan base | printed |
| `compute` | Seeed reComputer Mini J4012 with Extension (NX 16 GB, carrier, extension with RJ-45 and CAN, fan and heat sink, 128 GB NVMe), 95 x 63 x 66.7, 462 g | between the tray's locating ribs, held down by the shell's four tabs | US$999 Seeed (backup: Switch Science, the same kit; or the carrier US$89 + extension US$59 at Seeed with an NX module) |
| `eth_jack` | Adafruit 909 panel RJ-45 (25 cm to the J4012's port) | 2 x 4-40 through its ears in the wall | US$4.95 Adafruit / Digi-Key |
| `xt30_input` | Amass XT30U-F on 14 AWG | its housing clamped in the wall's pocket | body.json xt30_f |
| `input_fuses` | 2 x Bussmann HHM inline MINI holders, 20 A and 5 A Littelfuse MINI 58 V | clipped to the tray beside the J4012 | body.json (D55) |

**Decisions.**
- *The reComputer Mini J4012 with Extension kit, not the bare carrier:* it is the one listing that brings the NX
  16 GB with a fan and heat sink sold for it on that carrier (Seeed sells no Mini cooler alone), and its extension
  board has the RJ-45 and the CAN the turret needs. Rejected: the bare carrier with a dev-kit heat sink (no cooler
  sold for the NX on this carrier; it would be our guess at 40 W), a USB Ethernet dongle instead of the extension
  (one more part hanging on a port).
- *A plinth under the pan base*, not the computer inside the pan base: the J4012 is 95 x 63 x 67 and the pan base's
  middle is the slip ring's; around the ring there is no 95 mm chord inside r 72. The plinth is round (Ø156, inside
  the bumper's Ø172) so the turret still reads as one body; it adds 86 mm of height and about 0.8 kg (J4012 462 g,
  the plinth about 280 g printed, the jacks and fuses). Rejected: a square box (corners outside the bumper, a separate
  box look), the computer in Gyropup's head (D66: the turret must stand alone).
- *A tray and a shell*, not one printed box: the tray goes on first with short M5s (the head's inserts at the TM
  pattern), the shell's columns then take the pan base's M5s at the same positions. One box would need 90 mm
  through-bolts (none at a listed price we could read) or screws under the columns that cannot be reached.
- *Ports on the -x side*, the operator's side and away from the barrel's arc; the vents on the +-y walls beside the
  J4012's long sides (43 mm of air each side).

**Checks.** `connected` (the base group one body: the J4012 on the tray and under the tabs, the jack and the XT30
fastened through the wall); the clash sweep (the DT12 plug 3 mm outside the shell); the box scene (the plinth on
the J501 box's deck); the airflow of the J4012 in the plinth is open (bench test: the module's temperature at 40 W
with the shell on).

## 8. The stand and its battery (D66)

**Function.** Carry the turret on its own and power it from one FLEXVOLT pack, with the hold-to-run pendant, for the
bench and for play without Gyropup.

**Parts and decisions.** `stand_box` (PETG, 200 x 200 x 150, printed upside down) and `stand_bottom`
(cad/turret_stand.py): the turret's TM pattern on the top plate (M5 inserts); the DCB609 slides in from the back
onto a 20 V MAX dock adapter (12 AWG; Walmart US$12.95, Etsy US$13.50) fixed under the top plate, as onto a drill,
and rests on two ribs on the floor; its leads go through a 20 A MINI 58 V fuse and the rocker switch to an XT30 lead
out of the top plate's rear notch to the plinth. The pendant's socket and the rocker stay on the front panel; the
terminal board moves to the +y wall; the USB-CAN adapter sits beside the pack. *Rejected:* the dock on the top plate
behind the turret (in the barrel's arc at pan 180, and the turret then stands on a narrower stand), a 24 V mains supply (the turret is meant
to run untethered).

Open: the rocker is a 10 A 28 VDC part; with section 4's new flywheel rail, the stand's peak current is to be checked
against it.

---

## Review log

| Section | Reviewed | Found | Fixed | Gate | Screenshots |
|---|---|---|---|---|---|
| all | 2026-10-27 | the 3D page drew every ball, the ball path, the muzzle, the laser, the flywheels' and the flap's pivots and the dial's pivot in C, not in the scene's tilt frame (48 mm forward of the parts): balls outside the shells, the dial and wheels orbiting the tilt axis | cad/build_turret_box.py: one C-to-tilt transform for every point, the dial in its own frame about its axis | all gates, read by the build | |
| 3 Feed | 2026-10-27 | the hopper pile was hand-placed rings (interpenetrating, on the cone) | the physics settle (pile.json) | `hopper_*` pass: worst overlap 0.069 mm, no ball in a solid | |
| 1 Base | 2026-10-27 | the hall switch drawn 0.2 mm under its pocket's roof (floating) | the pocket's roof seats it | `connected` | |
| 6 Wiring | 2026-10-27 | the coupling tube 1 mm loose on the rotor stub (could not drive it) | 51225K24 3/16 in ID | `connected` | |
| 1 Base | 2026-10-27 | the full FEA (layer-aware): the servo posts 0.57 at a full stall, 1.14 at the cap; the pinion 1.05 at a full stall | open | FEA | |
| 7 Compute | 2026-10-27 | D66: the turret's own Jetson and input | the compute plinth (tray, shell, J4012, jack, XT30, fuses) | `connected`, sweep | |
| 8 Stand | 2026-10-27 | D66: the stand on a FLEXVOLT | the pack slides into the stand's back onto a dock | stand overlap check | |
| 2, 6 Layout | 2026-10-27 | the tilt servo stood 19 mm proud of its pocket, the board bay was an open tray: two boxes on the yoke's sides | the pocket's walls over the whole servo; the bay's lid | clash sweep, `connected` | |
| 5 Laser | 2026-10-27 | the laser on its tab 32 mm beside the barrel reads as a separate box | open: on the cartridge's top over the barrel, on the axis (keeps it off the barrel, so a barrel swap needs no re-boresight) | | |
