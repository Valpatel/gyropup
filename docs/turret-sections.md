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

`cad/turret_gates.py`, on cad-agent's integrity gates (`cadagent.gates`: the toolkit's docs/gates.md). Each gate writes
a verdict (`exports/turret/gates/<gate>.json`, schema `cadagent.gate/1`, with its assumptions and
`physical_fit_verified: false`); `exports/turret/gates.json` sums them up with a fingerprint of the CAD, the pile, the
launch ceiling and the toolkit's gate code, and `cad/build_turret_box.py` refuses a failing or stale one.

| Gate | What it proves | Pass |
|---|---|---|
| `connectivity` | the whole turret at home as one `Assembly` (T frame): every part grounded (at `compute_tray`) through contacts, fasteners and joints measured to hold; each moving body (pan, pinion, tilt, dial, each flywheel, the fill flap) held by its joint (9 revolute joints within 1 mm; the mesh a `gear` interface within 0.5 mm); the laser held by its modelled set screws | no floating part, every joint holds; undeclared contacts are warnings |
| `hopper` | the 30 balls of the physics-settled pile (`contains` in the hopper's registered `@cavity`: the Ø dial-wall cylinder from the floor to the lid, less every tilt-frame solid, the dial parked): each inside, none in the hopper's wall, none through another, each resting on the cavity or a ball below it | 0.5 mm^3 outside or shared at most (the settle's soft contacts), touching at 0.1 mm |
| `path` | a ball every 2 mm from the exit pocket round the chute, through the nip and the barrel to the muzzle, each inside the path's `@cavity` (the ball's free space, the tyres left in: they squeeze by design) | cadagent's defaults (0.001 mm^3) |
| `sweep` | the relation table on the posed turret: the hopper's balls against every part that moves relative to them (base, pinion, pan frame) at 8 pans x 5 tilts | no shared volume |
| `ammo_range` | D67: the biggest round (22.8 mm) through the `path` and the pockets' containment, the smallest (22.2 mm) one to a pocket and still squeezed at the nip, the bore's play for both, and the launch ceiling's corners: the lightest round (1.6 g) at or under 105 fps, the densest under ASTM F963's 2,500 J/m^2 | all pass |

The relation table is cached by content hash and placement (`.cadagent-cache/gates`, or `$CADAGENT_GATE_CACHE` on the
compute hosts), so a rerun after a change to one part re-queries only that part's pairs.

The clash sweep of the parts themselves is `turret.sweep()` (every pan in 10 deg steps at 0, -5, -12.5, -20 and
-25 deg tilt; `exports/turret/clash-sweep.json`).

The pile is a physics settle, not hand-placed rings: `sim/turret_feed.py --pile` (MuJoCo, run on a GB10) drops 30
balls through the fill port onto the dial's real cone and fins, parked, a ball seated in each pocket, and lets them
rest (slowest ball 0.0009 m/s at the end). `exports/turret/feed/pile.json` holds the result; the gates and the 3D page
both read it.

## The dossier (cad-agent's process)

The turret is the first part of Gyropup on cad-agent's full process (the toolkit's docs/dossier.md and docs/gates.md):
these eight sections as a YAML dossier, the geometry declared on the dossier registry, every integrity gate and the
dossier lint run by `cad-agent gates`, and `cad-agent check` failing on a failing, missing or stale verdict.

| File | What it holds |
|---|---|
| `dossier/project.yaml` | the requirements (R1-R19, each with its source and how it is verified), the interfaces between sections, the gates' declarations (ground, free parts, intended overlaps, ignored pairs, tools) |
| `dossier/sections/S1-base.yaml` .. `S8-stand.yaml` | each section's purpose, requirements, interfaces, decisions (with the alternatives rejected) and a card per part: its function, interfaces, material, screws, checks |
| `dossier/decisions.yaml` | the turret's project decisions (D40, D48, D66-D68, D70) and the dossier's own (T0.1-T0.8) |
| `dossier/gate-declarations.yaml` | what the schema cannot say yet: the hopper's `contains` with `closed_by`, the screws' thread overlaps |
| `cad/turret_dossier.py` | the registry build: every part at home in T (the stand under the plinth), the hopper's cavity, the joints, the gated screws, the build order -> `exports/dossier-geometry.json` |
| `exports/gates/*.json`, `*.md` | the verdicts: connectivity, containment, fasteners, motion, assembly, wall, the dossier lint; and the turret's own `turret-path`, `turret-ammo` |

```
.venv/bin/cad-agent gates --build             # build the record, run every gate and the lint (heavy: run it on a CAD host with tools/gp-remote)
.venv/bin/python cad/turret_gates.py --dossier   # the ball path and D67's ammo range, bound to that record
.venv/bin/cad-agent dossier                   # the lint again, with the turret's own verdicts
.venv/bin/cad-agent check                     # fails on a failing, missing or stale verdict
```

**Bodies and the chain rule (T0.1).** cadagent puts a part in a moving body only through a declared fixed joint or
fastener, growing from the joint's moving part, and stops at every moving joint's fixed part. So each child joint hangs
on its parent's moving part: I-tilt on `pan_ring` (the pan's), I-feed, I-wheel-l, I-wheel-r and I-flap on
`cartridge_body` (the tilt's). Their holds are measured from those parts, with declared clearances where the gap is not
the bearing's (I-tilt 39 mm, I-flap 69 mm, the wheels 4 and 1.5 mm); the bearings (the 61810's races, the MR126, the
horns) are the joints' intended contacts. The 37 fixed joints are the mounts of the moving parts, each an interface in
the dossier. The settled load rides with the hopper (I-pile, T0.2), so the motion gate sweeps it with the tilt frame.

**Results (run 3, on the recording compute host, 2026-10-28; the record built at d627004 + the merges of dd96792 and dd02fcd):**

| Gate | Result | What is open |
|---|---|---|
| connectivity | 137 pass, 1 warn, 2 fail | I-wheel-r's declared clearance (1.5 mm) is under the right hub's gap since dd96792 moved the CT dowel's boss (3.5 mm, as the left): set it to 4 mm and rerun. The warning: index_magnet on pan_clamp (a line contact through the clamp's hole), undeclared |
| containment | 64 pass, 1 warn | the support check (report only: balls held in an arch) |
| fasteners | 35 pass | |
| motion | pass, 1 warning (7,560 poses: pan 35 x tilt 6 x dial 3 x flap 3 x wheels 2, plus the pinion 13; 9,903 s on the recording compute host) | run 2 found the flap's knuckle on the lid at 51.1 deg and the hub overlaps, both fixed |
| assembly | 220 pass, 6 fail | stop_lug: the cradle cannot be lowered into the yoke with the lug on its plate (the upper stop sector, 8.2 mm before its seat); base_board: drawn in a closed pocket of pan_base (no straight way in); both open mechanical items for the next round. The poured load, the rotor's leads (a cable) and the MR126's races (pressed in from inside before the cradle) are not straight insertions |
| wall | 16 pass, 12 fail | features under 0.8 mm, mostly boolean sliver skins: cartridge_body and ring_carrier 0.002 mm, pan_ring 0.025, pan_base 0.07, compute_shell 0.10, laser_mount 0.12, tilt_yoke 0.15, cradle 0.20; dial 0.64, hopper 0.62, hopper_lid 0.70, pivot_spacer 0.75 |
| turret-path, turret-ammo | pass (410 and 6 checks), bound to this record on the recording compute host | they bind only to a record their own machine reproduces: the GB10's hashes differ from the workstation's |
| dossier lint | 7 errors (section-below-gated: the failures above and the FEA's open recoil case), 2 warnings; S8 gated, the others built | T4.7 (the cartridge's recoil SF) and T8.2 (the stand's switch cut-out) open |

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
  drawn floating; now the switch is glued up against the pocket's roof (found by the `connectivity` gate).

**Checks.** FEA `pan_base` / `pan_ring` / `pan_pinion` (cad/turret_studies.py, exports/turret/fea/); the gear check
`turret.pinion_check()`; the clash sweep; `connectivity` (base, pan, pinion one body each; joints: the 61810's races, the
pinion on its horn, the mesh). The pan servo's pocket end wall is 8 mm (it was 3: the FEA's layer-aware post-process
found it bending across its layers, 0.57 at a full stall; now 1.91, and 3.81 at the 50 % cap). Open: `pan_pinion
R-stall` read 1.05 layer-aware against 1.2 at 100 % of the servo's stall; its peak is at the tooth's root fillet
(x -41.1 = the root circle), not a load-patch artefact. Fix (2026-10-28): the pan servo's own EEPROM torque ceiling
(register 16) is set to 80 % by the setup tool and verified by the firmware at every init (it refuses a pan servo set
higher: SERVO_CONFIG, tested); the servo starts every power-up at it, so with the firmware's 50 % cap lost the mesh
sees 80 %. R-stall now loads 80 % (cad/turret_studies.py CEILING) for the pinion, the ring's teeth (1.2 at 100 %) and
the servo pocket. *Rejected:* a profile shift (it moves strength from the ring's teeth, which are at 1.2 themselves),
a wider face (the ring's face sets the mesh), a metal pinion against a printed ring (wear).

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
and -25; `connectivity` (tilt one body; the MR126's races, the horn on its boss).

## 3. Feed: hopper, dial, exit, chute

**Function.** Hold 30 balls and hand exactly one at a time to the flywheels on command, three a second; with the dial
parked, powered or not, no ball can reach the wheels.

**Requirements.**
- 30 Rival rounds (D67: Hasbro's own or any Rival-compatible round 22.2-22.8 mm and 1.6-2.0 g; design ball 22.7 mm,
  1.83 g), bores ball + 1.5 = 24.2: 1.4 mm of play for the biggest round, 2.0 for the smallest (the `ammo_range` gate).
- The ammo (D67), side by side, cheapest a round first (`exports/turret/bench/bom.json` `ammo_side_by_side`, from
  cad/build_turret.py AMMO_SIDE_BY_SIDE; prices read 2026-10-25..27):

  | Pack | Maker | Seller | Price | A round | Ø / mass | D67 | Bought |
  |---|---|---|---|---|---|---|---|
  | Cheetah Rival-compatible, 100 | Worker (third party) | Out of Darts | US$14.99 | US$0.15 | 22.7 mm / 1.75 g | yes | 2 |
  | Rival-compatible, 100 (ASIN B071SC9QYG) | third party (page names Little Valentine) | Amazon | US$14.99 | US$0.15 | not published | weigh and gauge 10 first | 0 |
  | Nerf Rival 60 Accu-Round (F5052) | Hasbro (official) | eBay | US$16.95 | US$0.28 | 22.7 mm / 1.83 g | yes | 0 |
  | Nerf Rival 50-Round Refill | Hasbro (official) | Walmart | US$15.95 | US$0.32 | 22.7 mm / 1.83 g | yes | 0 |
  | Nerf Rival 60 Accu-Round (F5052) | Hasbro (official) | Walmart | US$19.99 | US$0.33 | 22.7 mm / 1.83 g | yes | 1 |
  | Powerstrike rounds | Dart Zone (third party) | not priced | | | 22.8 mm / 1.85 g | yes | 0 |
  | Adventure Force rounds | Walmart's own (third party) | Walmart, not priced | | | 22.8 mm / 1.88 g | yes | 0 |

  The lightest accepted round (1.6 g, 22.8 mm) is the launch ceiling's fastest corner: 103.9 fps, under the 105
  ceiling (the `ammo_range` gate reads it from exports/turret/launch/launch3d.json).
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

**Checks.** `hopper`, `hopper_overlap`, `path` (the chute), `sweep`; the feed sim's
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

**The cage on D68's recoil (2026-10-28).** The FEA's recoil case had scaled D68's launch loads by v0's 66 / 52 (and
the summary before it held v0's loads): rescaled to the 105 fps trip over the 95 fps design point (79 N squeezing each
tyre apart, 53 N back on each motor), the cartridge read layer-aware 0.35 for the recoil and 0.48 for a 30 g fall,
peaking at square window corners right over the CT latch and dowels, at the short latch boss, and where the shells
twist on the chute. Changed: a 5 mm spine on the cage's centre plane from the channel to the top plate (clear of the
hopper's lug, the tyres' cavities and the bells), a web each side from the shell's rear onto the chute, the latch
boss Ø14 up to z 2 (was Ø10 x 9), Ø12 bosses over the dowels, the side windows narrowed to x +-11 with rounded
corners, the base window's corners rounded. Now: fall 2.21 (>= 1.2); recoil 1.38 against 2.0 (open), its peak at the
CT's rear dowel in the 3 mm base plate. Next: Ø4 x 12 dowels in holes 6 mm into the new bosses, or a second latch.
The load is the 5 ms contact peak applied statically, at the 105 fps ceiling (1.53 at the 95 fps set speed).

**Checks.** `path` (only the tyres touch the ball, at the nip; 0.35 mm tightest elsewhere); `connectivity`
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
`laser_mount` (PETG: a ring over the barrel on a foot that sits on the barrel socket's pad on the cartridge's top,
2 x M3 x 10 into the pad's inserts; a Ø6 hole through the foot over the barrel's set screw for the hex key), `laser`
(Quarton VLM-650-03, < 1 mW, Class 2) 29.5 mm above the bore's axis and on its plane, held by `laser_screws` (three
McMaster 93285A115 M3 x 6 nylon-tip set screws at 120 deg, modelled: their tips on the laser, their threads in the
ring), 2 mm clear of the ring's bore.

**Decisions.** *Bore ball + 2.0 past the nip* (finding 14: the ball rides the floor and rolls to a steady topspin;
pitch scatter 11.5 to 5 mrad); *the laser on the cartridge's top, over the barrel* (2026-10-28): on the cradle's
front-left tab, 32 mm beside the barrel, it read as a box stuck on the side and put 32 mm of sideways parallax on
the aim; over the barrel it is on the bore's vertical plane, it comes off with the cartridge so its boresight is to
the barrel it sits on, and the cradle loses its tab (which bound the path height over the pan pinion). *Rejected:*
the laser in the barrel (the barrel is a swap part and a ball path), the laser under the barrel (in the depression
arc over the deck).

**Checks.** `path` through the barrel; `connectivity` (the laser held through its modelled set screws: the
fastener touches the laser and threads into the ring);
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
  sat 1 mm loose round the Ø6 stub and could not drive it (the `connectivity` gate found the rotor floating); the 3/16 in
  ID tube stretches 26 % over the stub and grips it, its other end pushed into a Ø7.64 socket (0.3 mm squeeze).
- *Boards on the yoke* (turning with pan), so only power, bus, CAN and the safety line cross the ring.

**Checks.** `connectivity` (the rotor turned by the coupling; the leads part of the ring), the clash sweep at every pan
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

**The power budget** is under *Power* below (sim/turret_power.py, with section 4's D68 flywheels).

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
  J4012's long sides (43 mm of air each side), **behind the pan axis only**: on Gyropup's J501 box the J501's fan blows
  up (J501 94da39d; the adapter was drawn for a fan blowing down), so the adapter's "intake shroud" is in fact its
  exhaust duct and throws the J501's hot air out of the deck's front mouth. The plinth breathes from behind, about
  90 mm from the mouth and above the plume's start; the J501's own vents are all below the mouth's floor
  (cad/build_turret_box.py `exhaust_check`, in the box scene's checks). To prove on the bench: both computers at full
  load, the J501's intake and the J4012's within 3 K of the room.

**Checks.** `connectivity` (the base group one body: the J4012 on the tray and under the tabs, the jack and the XT30
fastened through the wall); the clash sweep (the DT12 plug 3 mm outside the shell); the box scene (the plinth on
the J501 box's deck); the airflow of the J4012 in the plinth is open (bench test: the module's temperature at 40 W
with the shell on).

### Power (D66, D68)

**Rails** (docs/turret-wiring.md 4 has every part). The XT30 feeds the J4012 directly (20 A MINI 58 V main, 5 A MINI 58 V
branch) and the head branch through a 10 A MINI 58 V to the base board: **BUS**, 15-42 V. On the base board BUS makes
12 V PAN (Pololu D36V50F12) for the pan servo and goes up the slip ring on three paralleled circuits each way (1, 2, 11
and 3, 4, 12: the pair D41 kept for a camera is now the third power pair). In the bay, level 0: the bank (2 x 470 uF
63 V), a P6KE51A clamp and the flywheel rail, **RAIL**: a TDK i6A4W, always on, trimmed per turret to ~11.31 V
(10.8-11.9 V) by R59 1.33 k and six bridgeable resistors (10-324 R: 0.5 % steps) on its TRIM pin, sealed after bench
test 4.1. Level 1: the Pololu 2815 switches RAIL to **FLY** (the two ESCs and the feed servo) only while ARM is held, the
brake unchanged; a second D36V50F12 makes **12 V AUX** for the tilt servo, and a D36V28F5 the 5 V logic, both from BUS,
so the rail's trim never moves their supply. Every part on BUS is rated 50 V or more (the i6A4W 53 V, the Pololus 50 V,
the bank 63 V, the clamps' 43.6 V standoff over the 42 V full bus, the reverse crowbar a 1000 V 1N5408); the 2815
(32 V) sits on RAIL. Level 0 is 13 mm tall for the i6A4W (12.7) and level 1 11 mm, so the bay's stack and its standoffs
are as deep as before (`TB['levels']`; the stack 1.9 mm inside the bay's face).

**Converter choices.** *The flywheel rail is the TDK i6A4W* (9-53 V in, 3.3-15 V by one resistor, 20 A, 250 W, $47.46
Digi-Key, Newark $40.32): one buck from both supplies, the trim sets each turret's ceiling (D68). Rejected: the
Pololu D24V150F12 (13.3-40 V in: under the 42 V bus; fixed, no trim), the D42V110F12 (60 V in but fixed 12 V ±4 %: D68's
stack fails untrimmed), a buck-boost (not needed: the ~11.3 V rail sits 3 V under the empty pack), switching the
i6A4W's ON/OFF pin from ARM (the rail would soft-start on every ARM; the 2815 on its output keeps one switch, on a stiff
rail). *The tilt servo and the logic on their own Pololu D36V50F12 / D36V28F5* (50 V in, $39.95 / $23.95), not on the
rail: a servo on a per-turret trim would change with every turret; a second i6A4W would be $47 for ~25 W. *The bank:
Panasonic EEU-FR1J471B*, 470 uF 63 V (Digi-Key $1.54, Newark $2.13), replacing the 35 V parts.

**Budget** (sim/turret_power.py; "play": the servos moving and the J4012 at 48 W; "worst": every servo at its 50 %
torque cap at once; the ring's busiest circuit carries 42 % of the three; a spin-up by its 100 ms peak, a burst by its
worst 1 s RMS):

| | 15 V (pack empty) | 20.5 V (pack full) | 30 V (bus) | 42 V (bus full) |
|---|---|---|---|---|
| Input: spin-up (800 ms) peak, play / worst | 11.2 / 13.1 A | 7.9 / 9.1 A | 5.2 / 6.1 A | 3.7 / 4.3 A |
| Input: 8 shots at 10/s, play / worst | 11.3 / 13.7 A | 8.0 / 9.7 A | 5.2 / 6.3 A | 3.7 / 4.4 A |
| Input: game average, J4012 at 25 / 48 W | 3.9 / 5.4 A (58 / 81 W) | 2.8 / 3.9 A | 1.9 / 2.7 A | 1.4 / 1.9 A |
| Ring, busiest circuit: spin-up / burst, play | **3.0 / 3.3 A** | **2.1 / 2.4 A** | 1.4 / 1.5 A | 1.0 / 1.1 A |
| Ring, game average a circuit | 0.64 A | 0.47 A | 0.32 A | 0.23 A |

The flywheels draw ~85 W at the top of the 800 ms ramp (100 ms), ~37 W holding speed and up to ~270 W for ~10 ms in a
shot's recovery; the J4012 up to 48 W. **The slip ring (2 A a circuit) holds on the bus at the firmware's 800 ms and
10/s, with every servo at its cap; on the stand's pack it does not.** So the firmware runs a stand profile from BUS_V
(the Feather's A0: BUS through 182 k / 10 k): a 1.0 s ramp and bursts of at most 4/s at 20.5 V, 1.6 s and 2/s at 18 V,
2.4 s and 1/s at 15 V, which hold the busiest circuit at 1.8-2.0 A in play (2.4-2.6 A if every servo hit its cap at
once at 15 V: the open margin). The real fix is more ring (the plan's two-10-A-circuit robot ring) or a boost in the
stand; not in this change.

**The stand's switch (D70): a Blue Sea 6006 battery switch** (48 V DC, 275 A continuous; Walmart US$34.16,
NavStore and Waytek as backups). The Bulgin R13244AAAA rocker it replaces (10 A 28 V DC) was **over its 10 A** at
15 V with the firmware's 800 ms and 10/s (11.2-11.3 A in play, 13.1-13.7 A worst, 24.6 A instant). No panel rocker
with a DC rating of 15 A at 20.5 V or more was found in stock (the 20 A rockers are rated at 12-14 V DC), so a marine
battery switch: it switches the pack itself and never breaks a load's pulse. The firmware's supply profile
(firmware/turret/config.py, D70) is implemented and tested: the ring sets it, the switch no longer does.

**Run time** on one DCB609 (about 160 Wh in 20 V mode): ~5 h idle (the J4012 at 25 W, nothing moving: ~32 W), ~2.8 h
at the game average (58 W), ~2.0 h with the J4012 flat out (81 W).

## 8. The stand and its battery (D66)

**Function.** Carry the turret on its own and power it from one FLEXVOLT pack, with the hold-to-run pendant, for the
bench and for play without Gyropup.

**Parts and decisions.** `stand_box` (PETG, 200 x 200 x 150, printed upside down) and `stand_bottom`
(cad/turret_stand.py): the turret's TM pattern on the top plate (M5 inserts); the DCB609 slides in from the back
onto a 20 V MAX dock adapter (12 AWG; Walmart US$12.95, Etsy US$13.50) fixed under the top plate, as onto a drill,
and rests on two ribs on the floor; its leads go through a 20 A MINI 58 V fuse and the power switch to an XT30 lead
out of the top plate's rear notch to the plinth. The pendant's socket and the rocker stay on the front panel; the
terminal board moves to the +y wall; the USB-CAN adapter sits beside the pack. *Rejected:* the dock on the top plate
behind the turret (in the barrel's arc at pan 180, and the turret then stands on a narrower stand), a 24 V mains supply (the turret is meant
to run untethered).

The power switch is a Blue Sea 6006 battery switch (D70: DC-rated for 15 A or more; section 7). Open: the stand's
front panel still has the Bulgin rocker's Ø20.2 hole; the 6006's cut-out and screw holes are drawn from Blue Sea's
dimensioned drawing when the switch arrives (bluesea.com refuses a plain fetch), not guessed from a box.

---

## Review log

| Section | Reviewed | Found | Fixed | Gate | Screenshots |
|---|---|---|---|---|---|
| all | 2026-10-27 | the 3D page drew every ball, the ball path, the muzzle, the laser, the flywheels' and the flap's pivots and the dial's pivot in C, not in the scene's tilt frame (48 mm forward of the parts): balls outside the shells, the dial and wheels orbiting the tilt axis | cad/build_turret_box.py: one C-to-tilt transform for every point, the dial in its own frame about its axis | all gates, read by the build | |
| 3 Feed | 2026-10-27 | the hopper pile was hand-placed rings (interpenetrating, on the cone) | the physics settle (pile.json) | `hopper_*` pass: worst overlap 0.069 mm, no ball in a solid | |
| 1 Base | 2026-10-27 | the hall switch drawn 0.2 mm under its pocket's roof (floating) | the pocket's roof seats it | `connectivity` | |
| 6 Wiring | 2026-10-27 | the coupling tube 1 mm loose on the rotor stub (could not drive it) | 51225K24 3/16 in ID | `connectivity` | |
| 1 Base | 2026-10-27 | the full FEA (layer-aware): the pan servo's pocket end wall bent across its layers, 0.57 at a full stall, 1.14 at the cap; the pinion 1.05 at a full stall | the end wall 3 -> 8 mm (SERVO_END_WALL): 1.91 at a stall, 3.81 at the cap (pan_base rerun on a CAD host; the falls 3.24 / 1.25 unchanged). The pinion stays open: its peak sits at the edge of the one-tooth model's load patch (p99 4x lower) | FEA | |
| 7 Compute | 2026-10-27 | D66: the turret's own Jetson and input | the compute plinth (tray, shell, J4012, jack, XT30, fuses) | `connectivity`, sweep | |
| 8 Stand | 2026-10-27 | D66: the stand on a FLEXVOLT | the pack slides into the stand's back onto a dock | stand overlap check | |
| 2, 6 Layout | 2026-10-27 | the tilt servo stood 19 mm proud of its pocket, the board bay was an open tray: two boxes on the yoke's sides | the pocket's walls over the whole servo; the bay's lid | clash sweep, `connectivity` | |
| 5 Laser | 2026-10-27 | the laser on its tab 32 mm beside the barrel reads as a separate box | open: on the cartridge's top over the barrel, on the axis (keeps it off the barrel, so a barrel swap needs no re-boresight) | | |
| 5 Laser | 2026-10-28 | (the open row above) | done: the holder on the barrel socket's pad on the cartridge's top, the beam 29.5 mm over the bore on its plane; the cradle's tab removed; the three set screws modelled (McMaster 93285A115) | `connectivity` (the laser held through its set screws), clash sweep | |
| all | 2026-10-28 | the turret's own gates moved onto cadagent.gates: the first run found the XT30 floating 0.2 mm in its pocket, the RJ-45 jack held only by touching the J4012's envelope, the laser touching nothing | 8 mm bosses inside the plinth's wall hold both connectors line to line; the jack ends 2 mm short of the J4012; the set screws modelled | `connectivity`, `hopper`, `path`, `sweep`, `ammo_range` | |
| 1 Base | 2026-10-28 | the pinion's 1.05 at a full stall is at the root fillet, a real peak | the pan servo's EEPROM torque ceiling at 80 %, verified by the firmware: R-stall loads 80 %: pinion 1.31, ring teeth 1.5 | FEA (CAD-host run 2026-10-28), test_firmware | |
| 7, 8 Power | 2026-10-28 | D70: the stand's 10 A rocker below the 11-14 A of an unprofiled spin-up | Blue Sea 6006 battery switch (48 V DC, 275 A); the firmware's supply profile implemented and tested | turret_power, test_firmware `supply_*` | the stand panel's cut-out for the 6006 on arrival |
| 3, 4 Cartridge | 2026-10-28 | cadagent's assembly gate (turret/dossier): the hopper's 0 deg lug under the cage plate (the hopper could not be lowered on); the CT front dowel at x 75 inside the right motor's opening from below (no material round it: the cartridge stood on one dowel) | lugs at 45/150/210 deg; the front dowel at x 50 (its Ø12 boss); cartridge FEA: fall 3.9, recoil 2.22 | assembly, FEA | the cradle's push-up case now 1.36 (< 2.0) with the dowel at x 50 |
| 2 Tilt, 1 Base | 2026-10-28 | the assembly gate: the stop lug, on the -y plate, meets the yoke's upper stop sector 8 mm before the cradle seats; the base board sits in a closed pocket of the pan base (no straight path in or out) | open: the lug fitted after the cradle is hung (a route and screw access in the 4 mm stop gap), the base board's pocket opened on one side | assembly | both open |
| all | 2026-10-28 | the wall gate (0.8 mm, two lines): sliver skins 0.002-0.2 mm in cartridge_body, ring_carrier, pan_ring, pan_base, compute_shell, laser_mount, tilt_yoke, cradle; dial, hopper, hopper_lid, pivot_spacer 0.6-0.75 | open (exports/gates/wall.json on turret/dossier) | wall | open |
| 8 Stand | 2026-10-28 | the USB-CAN adapter floated 10 mm up | on the floor against the wall on a VHB pad | connectivity | |
