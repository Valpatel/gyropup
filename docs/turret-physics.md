# Turret physics: the ball, the feed, the launch, the barrel and the flight, the target, and the turret itself, end to end

The physics agent's file (2026-10-27). It covers what [docs/turret-program.md](turret-program.md) asks the physics to prove, the
coordinator's three items (the speed ceiling, the ARM release, the command-to-muzzle time) and the turret plan's V1, V3, V13 and
V14. Every stage runs on the CAD at run time (`cad/turret.py` `Geo` and `Turret`), so the program agent's changes flow in: re-run
with `.venv/bin/python sim/turret_e2e.py` (section 15). The numbers below are from `exports/turret/{launch,feed,flight,target,e2e}/*.json`
(quick-mode populations of 120 balls unless stated; the full runs use 400).

## 0. In one paragraph

**v0 (docs/decisions.yaml D42, rerun 2026-10-27 by the turret program agent).** The flywheels are two SunnySky X2216 880 KV
on the same fixed 12 V rail with Ø34 tyres (16.3 % crush on this cage), and a third STS3215 steps the dial. With the
X2216's own constants (880 rpm/V, 117 mOhm between leads, 0.5 A at 10 V; its rotor's 4.8 kg mm^2 is est from SunnySky's
drawing, so each wheel is 6.9e-6 kg m^2, 1.5 times the Snail's), a 52 fps nominal ball needs **8,855 rpm**, 84 % of the
10,499 rpm no-load speed; the ball population at that speed is 48.9 ± 5.0 fps (p99 53.5, max 53.7). **The 70 fps cap
holds on Ø34:** at 100 % throttle on a +5 % motor and a +4 % rail, with runout and the soft tyre's growth, the fastest
swept ball is **67.7 fps** (2.3 fps of margin) and the worst single corner ball 65.4. That is over the bench's 66 fps
trip line by 1.7 fps, so the bench measures the motors' no-load speed before any ball (test 4.1): at or under **11,180
rpm** (78,260 eRPM) at 100 % on the rail, every ball stays under 66 fps by this model; the worst-corner motor and rail make
11,461. **Ø36 is out with this motor** (70.7 fps at the worst corner), so v0 prints Ø34 only. The heavier, lower-resistance
wheel brakes on the phase short through its FETs with τ 10.2 ms at low speed (5 % speed ~48 ms after release with the short at +10 ms) and draws more to spin up: 3.6 A at
the ring with a 200 ms ramp (1.8 A a circuit), **2.5 A with the 300 ms ramp the firmware now uses** (1.25 A a circuit). A
24 V fault would spin the wheels to 21,000 rpm (123-140 fps), as before. **The feed on the servo:** a 45° step settles in
232-246 ms and a ball reaches the tyres 300-330 ms after the command (~340 ms to the muzzle); the pocket must rest over
the hole ~100-160 ms for the ball to fall clear, so **3 balls/s level and 2.5 at −25° are the clean fixed-period rates**
(at 4/s and up the next step starts first and the spoke carries the ball on: 1 ball in 8 steps), and the firmware paces
each step on the previous ball reaching the chronograph's first gate. At those rates the rigid-ball model leaves about 1
step in 8 empty; parked, powered or not, through the jolt and the vibration, no ball reaches the wheels. Sections 3, 4, 5 and 9 have the v0 tables first; the Snail and M2006 figures below
them are the design before D42.

**Before D42 (the Snail 2305 and the M2006 + C610):**

A Rival ball leaves the nip at 55 fps nominal (the ESC set speed, 9,408 rpm on Ø36 tyres at 12 V), 55.8 ± 1.3 fps over the sourced ball
spread with a soft-ball tail to 48 fps. **The 70 fps cap holds by hardware, not firmware:** on the fixed 12 V rail the Snail cannot exceed
10,437 rpm, and the fastest ball of the whole swept population at 100 % throttle on a +5 % motor and a +4 % regulator, with tyre runout and
the soft tyre's centrifugal growth, is 68.0 fps (margin 2.0 fps); the single worst-corner ball is 64.2 fps. The same wheels on 24 V would
throw 79-128 fps, so the 12 V-only rule and the pre-feed RPM check are the safety items. The feed delivers one ball per 45° step, never two
in the same step at ≤ 4/s, nothing when parked through a 13.5 m/s² jolt or 5 m/s² vibration, powered or not, and nothing is sensitive to
pan slews up to 150 deg/s; but the hopper refills the pockets slowly when the dial is driven as the real M2006 drives it (a ~100 ms step
instead of the 40 ms jerk the earlier feed study assumed), so 24 % of the 108 steps in the full run came up empty until the pile was stirred:
the hopper agitator is the feed's open item. The research default of 65 fps is not reachable on this hardware at all: the nominal ball tops
out at 59.5 fps at 100 % throttle on the 12 V rail with Ø36 tyres, so the usable set speeds are 50-57 fps, and more range means a
different ceiling (section 4) or a taller stance. A shot takes ~245 ms from the dial command to the muzzle (dial step ~100 ms, the drop and the chute ~130 ms, the nip
5 ms, the bore 7 ms). Level from the 0.55 m muzzle the 55 fps ball lands at 5.0 m and can reach a 0.30 m-high target out to 3.5 m (4.1 m
at 65 fps, 4.4 m at 70 fps; 5.0-6.2 m if the robot stands 0.3 m taller), because the barrel never points up. It knocks over any hinged
plate up to ~0.5 kg at 4 m and carries 0.26 J (0.42 J at the cap: 84 % of EN 71-1's resilient limit, 41 % of ASTM's energy density; a
stock Rival blaster at 97 fps is 0.81 J). Recoil is 0.030 N s per shot and moves the aim 1.2 mrad; the biggest aim movers are the printed
pan gear's backlash (7.6 mrad), the tilt servo's backlash (8.7 mrad) and firing while panning at 90 deg/s (14.5 mrad, 8.7 cm at 6 m).
When ARM drops, the phase-short brake stops the wheels to 5 % in 45 ms; a ball already dropped rests at the nip and leaves at 7.7 fps
on the next ramped arm. The ring sees 2.2 A peak with the 200 ms soft start (12.0 A without it).

## 1. The chain: what is simulated, how, and where one stage hands to the next

| # | Stage | File | Model | Solver | Hand-over check |
|---|---|---|---|---|---|
| 1 | The ball | `sim/turret_ball.py` | sourced size/mass per brand, the foam's stiffness, restitution and friction swept over bands, worn and damp conditions | tables | one `population()` feeds every stage |
| 2 | The feed | `sim/turret_feed.py` (program agent) + `sim/turret_feed_dyn.py` | 30 rigid balls, the dial, baffle, floor hole and chute from `Geo`; the M2006 + C610 as a torque/speed-limited loop with the reflected rotor inertia; pan-slew fictitious forces, body jolts, vibration | **MuJoCo** | the ball's position, velocity and spin at the tyres' first-touch plane (the exact point stage 3 starts from) |
| 3 | The launch | `sim/turret_launch3d.py` (extends the program agent's 1D `sim/turret_launch.py`) | 6-DOF ball between two tyres on independent Snail + ESC loops: Hertz foam contact, Hunt-Crossley damping, Coulomb slip, tyre runout and centrifugal growth, the channel's floor/ceiling; bursts; braking | **reduced** (1 µs explicit, vectorised) | centred, no runout: matches the 1D model to < 0.1 % (`handover_1d`) |
| 4 | The barrel | `sim/turret_flight.py` `barrel_pass` | the same contact law on the Ø24.2 bore wall (0.75 mm play), friction and spin | **reduced** (2 µs) | the launch confines the ball to the same channel, so the entry is consistent (an earlier version without it stored 0.06 mm of false penetration and released it as a 10 mrad kick: caught by the trace); speed loss 0.9 fps over 111 mm |
| 5 | The flight | `sim/turret_flight.py` `fly` and MuJoCo's ellipsoid fluid model in `sim/turret_e2e.py` | drag Cd 0.47 (Clift-Gauvin 0.44-0.47 at Re 1.5-3.3e4, swept to 0.55), Magnus by Nathan's fit, gravity; the muzzle's own velocity while panning | Python RK + **MuJoCo** | the Python and MuJoCo flights compared at each target plane (section 11) |
| 6 | The target | `sim/turret_target.py` + `sim/turret.py` plates | impulse on a hinged plate / a free-standing block; EN 71-1 and ASTM energy measures | analytic + **MuJoCo** | the analytic knock-down criterion against MuJoCo's hinge |
| 7 | The turret | `sim/turret_dynamics.py` + `sim/turret_e2e.py` | the posed CAD meshes as pan/tilt bodies with STS3215 torque-speed servo models, the recoil pulse at the nip, gyroscopic terms; backlash and resolution analytically | **MuJoCo** + analytic | `cad/turret_motion.py`'s inertias; the aim trace |
| 8 | Power | `sim/turret_power.py` | ESC DC-side current → 12 V regulator → bank → ring resistance, stepped/ramped spin-up and an 8-shot burst | reduced (10 µs) | the wheel-speed drop per shot from stage 3 |

Reduced models are marked because MuJoCo's soft contacts cannot hold a 25 % foam crush at 18 m/s surface speed without tuning that would
hide the physics; each is checked against the stage beside it.

## 2. The ball (`exports/turret/launch/ball.json`)

Sources (all checked 2026-10-27; URLs and quotes in the JSON):

| Quantity | Value | Source |
|---|---|---|
| Diameter | Hasbro patent band 22.5-23.5 mm; Worker Cheetah 22.7, Dart Zone/Adventure Force 22.8 | US10648765B2; Out of Darts product records |
| Mass | Hasbro 1.83 g mean, AF 1.88, Worker 1.75, Dart Zone 1.85; no published SD anywhere | BlasterHub review (100 shots each), Out of Darts |
| Density | ≈ 290 kg/m³ (calc) | |
| Foam | PU (Hasbro, Dart Zone), EVA (Worker) | product records |
| Hardness | "1.5 to 2.1 kg or < 55 Shore A" (deflection not stated) | US10648765B2 |
| EVA modulus vs density | 2.8-7.0 MPa at 80-180 kg/m³ (small strain) | Chen et al., Polymers 2023 |
| Restitution | PU foam ball e ≈ 0.74 at hand-drop speed, falling at high speed; EVA resilience 60 % | arXiv 2411.05891; Koepp K/EV35 sheet |
| Friction | solid EVA 1.18 dry on a hard ball; stock flywheels slip ~30 % on darts | PMC9571719; Hasbro US11719504B1 |
| TPU 95A tyre | E 9.8 (Bambu HF) to 26-34 (NinjaTek, Polymaker) to 67 MPa (Ultimaker), 1.22 g/cm³; spinning tyres grow (~4 mm, Hasbro) | datasheets; US11719504B1 |
| Wet/dirty rounds | "perform significantly differently" | BritNerf |

What is swept (est, with the basis in the file): the Hertz-effective modulus 0.75-3.0 MPa (1 MPa gives 20 N per side at the 25 % nip crush,
the order of the patent's 1.5-2.1 kgf hardness), restitution 0.45-0.75, friction on TPU 0.6-1.0 and on PETG/PA6-CF 0.4-0.7, the within-brand
spread SD 0.15 mm and 0.10 g, worn balls (0.3 mm smaller, 40 % softer, grippier) and damp balls (+30 % mass, slippery). The earlier launch study
quoted a "Blaster Labs" mass spread (SD 0.13-0.16 g, n = 18 and 12); no such source could be found, so the spread is marked est here.

## 3. The feed under motion (`exports/turret/feed/feed_dyn.json`, `feed_dyn.png`, `feed_dyn.mp4`)

**v0: the STS3215 servo (D42).** `sim/turret_feed_dyn.py` drives the dial as the servo does: its own move profile (the
firmware's goal speed 4.0 rad/s, 85 % of the 45 rpm no-load speed, and 60 rad/s^2) tracked by a stiff position loop whose
torque is clipped by the servo's line (2.94 N m stall, 4.71 rad/s no-load at 12 V) and by the firmware's 50 % torque
limit, with its motor's inertia reflected through 345:1 (not published: 2.4e-8 kg m^2 est, 2.9e-3 kg m^2 at the dial,
swept 1e-8 to 5e-8 with no change in the step time: the move is speed-limited, not torque-limited).

| Case (3 steps/s unless stated) | Balls per step | Command → first touch (ms) | Step settled (ms) |
|---|---|---|---|
| level, hopper full | 1 1 0 1 1 1 1 1 | 308-326 | 232-244 |
| tilt −25° | 0 1 1 0 1 1 1 2 | 30-369 (a hung ball came down with the next: one double) | 232-237 |
| −25°, rolled 15° | 1 1 0 1 1 1 1 1 | 290-371 | 232-236 |
| level, pitched 10° | 1 1 1 1 1 1 1 1 | 287-315 | 232-247 |
| level and −25°, panning 90 deg/s | 1 1 0 1 1 / 0 1 1 0 2 | 26-364 | |
| −25°, a fixed period of 2.0 / 2.5 / 3.0 steps/s | 7 / 7 / 7 of 8 | | no double at 2.0 and 2.5; one at 3.0 (a hung ball released with the next) |
| −25°, 4 and 6 steps/s commanded | 1-2 balls in 8 steps | | the dial steps again before the ball falls clear |
| parked, powered and unpowered, jolt + 8/15/25 Hz shake | 0 balls at the tyres | | |

So the rate is **3 balls/s level and 2.5 at −25° on a fixed period** (each step needs ~235 ms and then ~100-160 ms with
the pocket over the hole for the ball to fall clear). The firmware therefore paces the feed on the chronograph: the next
step only after the previous ball has crossed gate 1 (or a dither, never a step, if it has not within 400 ms), at most
3/s (docs/turret-firmware.md); the bench's test 5.1 counts what that gives with real foam. The entry state at first touch is unchanged in kind (on the channel floor,
z −0.79 ± 0.02 mm; 0.41 ± 0.05 m/s forward; lateral 0.1 ± 0.5 mm). Nothing was left in the chute and nothing escaped.

**Before D42 (the M2006 + C610):**

The dial motor: M2006 P36 on a C610 (DJI manual: 500 rpm no-load, 416 rpm at 1 N m, 0.18 N m/A, 10 A limit → 1.8 N m peak, 52.8 ms mechanical
time constant; the rotor inertia is not published: 3.5e-6 kg m² est from that time constant and the bell's size, 2.2-4.6e-6 swept) through 36:1,
so the dial sees 4.5e-3 kg m² of reflected rotor against its own 3e-5. A 45° step therefore takes **90-125 ms** at the 10 A limit (80 ms with the
light rotor, 150 with the heavy; 117-138 ms at the 1 N m rating; **180-310 ms at the plan's 3 A dial cap**), not the 40 ms the first feed
study commanded. The C610's loop in the model: a 1 kHz position + speed loop clipped by the current limit and the voltage line.

| Case (3 steps/s unless stated; the full run, 108 steps in all) | Balls per step | Latency, command → first touch (ms) | Notes |
|---|---|---|---|
| level, hopper full | 1 0 0 0 1 1 1 1 | 211-238 | three empty steps: pockets not refilled (below) |
| tilt −25° | 1 1 0 1 1 1 1 1 | 215-229 | |
| −25° and the robot rolled 15° | 1 1 0 0 2 1 1 1 | 41-243 | one ball hung in the hole against the pocket's side and came down with the next step: a double |
| level, the robot pitched 10° nose-down | 1 1 1 1 0 1 1 1 | 205-233 | |
| level, panning 90 deg/s with 20 ms ramps | 1 1 1 1 1 | 223-237 | no effect of the slew on the entry state |
| level, panning 150 deg/s | 1 1 1 0 1 | 237-240 | |
| −25°, panning 90 / 150 deg/s | 1 1 0 1 1 (both) | 213-312 | |
| level and −25°, a 13.5 m/s² body jolt during the step | 1 1 1 1 (both) | | the jolt stirs the hopper: every step fed |
| level and −25°, 5 m/s² 15 Hz vibration while feeding | 1 1 1 1 (both) | | |
| parked, powered and motor-off, jolt + 8/15/25 Hz shake | 0 balls at the tyres, dial turned 0° | | the baffle and the parked pocket hold |
| stepping at 4/s | 1 1 1 1 1 1 1 1 | | **clean** |
| stepping at 5/s and 6/s | 0 1 1 0 1 1 1 2 | 13-213 | **one double each**: the dial steps before the previous ball has cleared the hole; the next spoke releases two |
| stepping at 8/s and 10/s | 1 of 8, 0 of 8 | | the spokes carry the balls over the hole |
| continuous rotation 10-75 rpm | 1 of 96 pockets | | nothing drops: see finding 3 |

Totals: 82 balls in 108 steps (76 % delivery), 3 doubles, 0 balls stuck in the chute, 0 escaped, 0 leaks when parked. Entry state at first
touch (the launch's input, 26 balls): on the channel floor (z −0.78 ± 0.04 mm), lateral 0.1 ± 0.4 mm (the bore's play), 0.42 ± 0.07 m/s forward
(0.31-0.53; lower than the 0.5-0.8 assumed before: the ball slides through the bend as much as it rolls), spin about y 3 ± 23 rad/s.

**Why the empty steps.** After settling, only 3 of the 7 pockets under the pile hold a ball (the debug view in the log): 30 rigid balls arch
over the dial's cone and spokes, and a 100 ms step stirs them far less than a 40 ms one. During a burst the pockets fill gradually (6 of 7
after five steps); a jolt fills them at once. Rigid spheres under-predict bridging (real foam is tackier), so the real hopper will be worse,
not better. The chute itself never failed: no ball was left in it in any case.

**The rate of fire.** The dial's step (~100 ms) plus the ball's fall out of the pocket (the ball's centre is under the dial's sweep ~100-130 ms
after the command) sets the minimum period at ~230 ms: **4 steps/s is the clean maximum** (the kids' 3/s is fine; 5/s doubles; 10/s
is not reachable by stepping). The command-to-muzzle time is 215-240 ms in the feed (step + drop + chute) plus 4.8 ms in the nip and 7.2 ms
down the bore: **~245 ms**, against the simulator's 146 ms (which assumed a faster dial): the firmware should expect a quarter second.

## 4. The launch in 3D (`exports/turret/launch/launch3d.json`, `launch3d.png`)

**v0: the X2216 on Ø34 (D42).** The 1D and 3D models with the X2216's constants (`sim/turret_launch.py` MOTOR) and the
cage's own crush for each tyre (the motors' axes are 53.0 mm apart, so a tyre's diameter sets its crush:
`sim/turret_launch.py` cage_crush):

| Result | Value |
|---|---|
| Set speed for 52 fps nominal on Ø34 | 8,855 rpm = 61,985 eRPM (84 % of the 12 V no-load 10,499 rpm) |
| Population at the set speed, in the channel with 0.15 mm runout | 48.9 ± 5.0 fps, p99 53.5, max 53.7; yaw SD 5.7 mrad, pitch SD 7.2 mrad |
| Contact, forces, wheel speed lost per shot | 4.7 ms; 19 N per tyre, 28 N on the cage; 1.3 % (the heavier wheel) |
| Tyre growth | 0.17-0.52 mm radial at the set speed, 0.29-0.86 at no-load + tolerance (E 30-10 MPa) |
| Bursts at 3-10 per s | no droop |
| Hand-over to the 1D model | 52.0 vs 52.0 fps |

The ceiling at 100 % throttle (the fastest of the swept population, +5 % KV, +4 % rail, runout, the soft tyre's growth),
fps, with each tyre at its crush on this cage:

| Rail | Ø32 (7.5 %) | Ø34 (16.3 %) | Ø36 (25.1 %) | Ø38 (33.9 %) |
|---|---|---|---|---|
| 12 V (X2216, D42) | 63.3 | **67.6** | 70.7 ✗ | 73.5 ✗ |
| 24 V (a wiring fault) | 123 ✗ | 129 ✗ | 136 ✗ | 140 ✗ |

The 1D model's worst single corner ball: 61.9 / 65.4 / 68.0 / 69.7 fps for Ø32-38. Ø32 cannot reach the set speed (its
nominal ball tops out at 28.6 fps at 100 %: too little crush to grip). So Ø34 is the tyre: under the cap, and under the
bench's 66 fps line once the measured no-load speed is at or under 11,180 rpm (the ceiling scales with the wheel speed:
67.6 fps x 11,180 / 11,461 = 66.0). The 24 V fault is unchanged in kind: the 12 V-only rule, the keyed CT pins and the
pre-feed eRPM check (refuse above 1.10 x KV x 12 V) stop the first ball; the chronograph trips after it.

**Before D42 (the Snail 2305 on Ø36):**

The 3D model reproduces the program agent's 1D model exactly in the centred case (55.00 vs 55.00 fps) and adds what the 1D model cannot see.

| Result | Value |
|---|---|
| Set speed for 55 fps nominal | 9,408 rpm (90 % of the 12 V no-load 10,437) |
| Population at the set speed, centred | 55.8 ± 1.3 fps, p1-p99 51.9-57.9, min 47.9 (the softest, slipperiest balls) |
| With the feed's entry offsets and 0.15 mm tyre runout, in the channel | 55.7 ± 1.3 fps; yaw at the nip exit SD 2.4 mrad (p99 5.1), pitch SD 6.3 mrad; 0.30 mm runout: yaw SD 5.0 mrad |
| The rolling ball's topspin | the ball arrives rolling and its spin rubs the tyres: a downward kick that the channel floor reacts, bouncing the ball; it leaves the nip with 35 ± 54 rad/s of topspin (section 6: this spin is what scatters the drop) |
| Contact time, peak forces | 4.6-4.8 ms; 41 N per tyre, 57 N on the cage; the wheels lose 7 % of their speed per shot |
| Tyre centrifugal growth | 0.23-0.69 mm radial at the set speed (E 30-10 MPa), 0.34-1.01 mm at no-load + tolerance: the crush grows from 25 % to 27-31 %; +0.4 fps and 1.3 mrad less yaw scatter (the tighter nip centres the ball) |
| Wheel mismatch → spin | 2 % → 120 rpm, 5 % → 300 rpm, 10 % → 600 rpm of ball spin; S ≤ 0.045 |
| Bursts at 3/5/8/10 per s | no droop: the ESC recovers the 7 % in ~3 ms at 10 A |
| Recoil | 0.030 N s per shot (0.15 N s per 5-ball burst; 0.9 N s for the hopper) |

**The ceiling (V1, V13, the coordinator's item 1).** The hardware ceiling is the rail voltage × the motor's KV × the tyre diameter. At 100 %
throttle on a +5 % KV motor and a +4 % regulator (the D24V150F12's class), with 0.15 mm runout and the soft tyre's growth:

| Rail | Ø32 | Ø34 | Ø36 | Ø38 | Ø40 |
|---|---|---|---|---|---|
| 10 V | 51.0 | 53.8 | 56.6 | 59.3 | 62.1 |
| 11 V | 55.7 | 58.7 | 61.7 | 64.7 | 67.8 |
| **12 V** | 60.2 | 63.5 | **66.8** | 70.1 ✗ | 73.4 ✗ |
| 13 V | 64.7 | 68.2 | 71.8 ✗ | 75.4 ✗ | 79.0 ✗ |
| 14 V | 69.3 | 73.1 ✗ | 76.9 ✗ | 80.8 ✗ | 84.7 ✗ |
| 24 V | 114 ✗ | 121 ✗ | 128 ✗ | 135 ✗ | 141 ✗ |

(the fastest ball of a 60-ball swept population, fps; the 120-ball main run gives 68.0 fps for 12 V / Ø36). So: **the worst single corner ball
is 64.2 fps, as the plan says, but the swept population reaches 68.0 fps: the cap holds with 2 fps of margin, not 6.** The ramp cannot raise
it (the first ball at the end of the 200 ms ramp is at the set speed). Crush does not cap balls the way it caps darts (the 1D efficiency map:
stiff balls reach η 0.9 at any crush above 18 %), and no lower-KV Snail exists; the ceiling is the rail. Recommendation: keep the fixed 12 V
rail and Ø36 (2 fps margin) only if the bench ceiling test agrees; otherwise **Ø34 tyres at 12 V (ceiling 63.5 fps, 6.5 fps margin) or 11 V
(61.7, 8.3)** — the Ø34 set is already in the tyre print set (`cad/turret.py flywheel_tyre`). A 24 V fault throws 79-128 fps: only the 12 V-only
wiring rule and a pre-feed RPM check (AM32 telemetry: refuse to feed above 11,500 rpm; a 24 V fault spins at 21,000) stop the first ball; the
chronograph trips after it (section 10).

## 5. The release and the stray ball (V14, the coordinator's item 2)

**v0 (D42), the brake as built:** the short runs through the X2216's 117 mOhm, two IRLZ44N (25 mOhm each with 4.5 V
on the gate) and the 22 AWG taps: 173 mOhm, so the time constant at low speed is **10.2 ms** (6.9 ms for the motor
alone). At speed the winding's inductance limits the current (`sim/turret_launch3d.py` brake_current: E R / (R^2 +
(w_e L)^2); the X2216's inductance is not published, 35 uH between leads est). With the short closing 10 ms after the
line drops (the circuit gives 5-14 ms, docs/turret-wiring.md 3.3):

| Winding inductance | 5 % speed after the line drops | Speed left at 96 ms |
|---|---|---|
| 0 (resistance only) | 40.0 ms | 0.02 % |
| 20 uH | 42.8 ms | 0.03 % |
| **35 uH (est)** | **48.4 ms** | 0.04 % |
| 50 uH | 57.1 ms | 0.10 % |

Nothing is left by 96 ms, when the first ball still in the chute could arrive; the peak braking current is 13-58 A
for a few milliseconds (the IRLZ44N's pulse rating is 160 A). A ball already in the nip at the release leaves at up to
42 fps (the wheels coasting, then braked: 21.9 fps at 20 ms, 6.6 at 30 ms, under 1 fps from 50 ms). In service AM32's
own brake on stop starts first (the firmware commands zero on the first missing pulse, ~4 ms), so these are the
hardware-only figures. Before D42:


The phase-short brake's time constant from the model's own inertia and resistance is **11.95 ms** (the plan's 12). With the short closing
10 ms after the line drops: 5 % speed at 45 ms, 0.07 % at 96 ms.

| Ball reaches the nip after release | Wheels | It leaves at |
|---|---|---|
| 0-10 ms | 9,400 rpm | 36 fps (it was in the nip anyway) |
| 20 ms | 4,000 | 12.7 fps |
| 30 ms | 1,700 | 5.4 fps, then rests |
| ≥ 50 ms (any ball still in the chute: they arrive ≥ 96 ms later) | < 320 | **rests at the nip, touching both tyres** |

Unbraked (coast, time constant ~2 s) the same ball leaves at 53 fps at 100 ms and 31 fps at 1.4 s: braking is required, and the hardware
short does it. **The next arm:** the tyres' runout engages the resting ball at once; with the 200 ms ramp it leaves after 24 ms at 1,124 rpm,
**7.7 fps**; with a stepped spin-up (10 A limit) 16.9 fps; a deliberate 15 % clear spin gives 2.7 fps. A dial reverse cannot pull it back: it
rests 21 mm ahead of and 21 mm below the pocket it fell from, past the chute bend. Firmware: start every arm with the muzzle depressed, treat
the first 50 ms as the stray clear, and log the ~8 fps chronograph reading as a stray ball.

## 6. The barrel and the flight (`exports/turret/flight/flight.json`, `flight.png`)

The bore (ball + 1.5 mm, 111 mm from the nip exit to the muzzle): every ball runs along its floor (gravity and the topspin kick from the
nip) and bounces in the 0.75 mm of play, losing 0.9 fps; it leaves with 78 rad/s of topspin on average, a yaw SD of 4.2 mrad and a pitch
scatter of 9 mrad SD (mean +8 mrad: the last bounce). A deliberately crooked 2° entry leaves at 1.2° after ~2 bounces and loses 4.6 fps.
**The play matters, and the other way round from intuition:**

| Bore play (radial) | 0.25 mm (ball + 0.5) | 0.5 mm (ball + 1.0) | **0.75 mm (ball + 1.5, the CAD)** | 1.0 mm (ball + 2.0) |
|---|---|---|---|---|
| Speed lost in the bore | 4.9 fps, 5 of 40 balls stuck | 1.9 fps | 1.0 fps | 0.7 fps |
| Pitch scatter at the muzzle (SD) | 21 mrad | 17 | 11.5 | **5.0** |
| Yaw scatter (SD) | 11 mrad | 8.0 | 3.9 | **2.6** |
| Topspin at the muzzle | 7 ± 149 rad/s | 2 ± 134 | 69 ± 82 | **102 ± 40** |

A tight bore makes the ball rattle between floor and ceiling (each bounce flips its vertical velocity and scrubs its spin); with 1 mm of
play it rides the floor and rolls up to a consistent topspin. The spin's spread is what scatters the drop (section 6, Magnus), so ball + 2.0
from the nip to the muzzle roughly halves the vertical dispersion and the speed loss (finding 14).

Level shots of the population from the 0.55 m muzzle (no aim error; the 55 fps set speed; the CAD bore):

| Range | 1 m | 2 m | 3 m | 4 m |
|---|---|---|---|---|
| Drop below the bore line | 1.6 cm | 8.3 | 20.8 | 39.8 |
| Height SD (speed spread + spin spread + the bore's pitch scatter) | 0.8 cm | 1.9 | 3.8 | 6.7 |
| Drift SD | 0.3 cm | 0.5 | 0.6 | 0.8 |
| 68 % radius | 0.4 cm | 1.1 | 2.5 | 4.5 |
| Speed | 52 fps | 48 | 46 | 43 |
| Time of flight | 62 ms | 128 | 198 | 274 |

(the 5 and 6 m rows of the JSON hold only the few balls that got there and are survivorship-biased). The topspin the ball carries is not
small for the drop: 35 rad/s adds 4 cm at 4 m and 100 rad/s ~12 cm, so the firmware's drop table must be measured with the real
spin (the bench's 2/4/6/8 m groups), not computed from speed alone.

A level shot lands at **5.0 m (55 fps), 5.8 (65), 6.2 (70)** from 0.55 m; the farthest 0.30 m-high target a never-above-horizontal barrel can
reach: **3.5 / 4.1 / 4.4 m**; from 0.70 m: 4.3 / 5.1 / 5.4; from 0.85 m: 5.0 / 5.8 / 6.2. The tilt for a 0.30 m target: −13.0° at 1 m, −4.95° at
2 m, −1.35° at 3 m (55 fps). Magnus: 300 rpm of yaw spin drifts 3.8 cm at 4 m, 1,000 rpm 12.8 cm (so a 2 % wheel mismatch is 1.5 cm). Panning
while firing: the muzzle is 155 mm from the pan axis, so 30 / 90 / 150 deg/s add 0.08 / 0.24 / 0.41 m/s sideways: **0.28° / 0.83° / 1.39°, i.e.
1.9 / 5.8 / 9.7 cm at 4 m.**

Validation: (a) stock Rival flywheel blasters measure 89-102 fps against Hasbro's 100 (Nemesis 94-101, Perses 99, Prometheus 98-102, Zeus 89-93,
Charger 98; BlasterHub's 100-shot test kept every Hasbro round between 92 and 101 fps, ±4.6 %, and the Kronos's only published SD is 3.3 fps at
92, 3.6 %); our launcher's spread at the set speed is 2.3 % SD with a 7 % soft tail, the same order, and its efficiency (ball/surface speed 0.95
with a PI-held Snail on a TPU tyre) sits above the stock blasters' implied 0.6-0.75 (the patent's 30 % slip; the Photon wheels' 0.57-0.62 under
brushed-motor sag). (b) The 100-shot doorway test (every ball through 0.76 m at 15 m) bounds a handheld Rival's dispersion at ~25 mrad; the
model's ball + launch dispersion alone is ~2 mrad. (c) The RoboMaster 17 mm chain: the model's ball picks up 98 % of the no-slip (Nathan)
spin from a wheel mismatch; the NUAA guide's "1000 rpm mismatch → 13 cm at 15 m" matches the model (12.6 cm) if its rpm is the ESC's eRPM (7
pole pairs) and is 7× under it if mechanical: the chain is the right order either way, and Gyropup's matched wheels sit far below it. The
guide's contact time (< 5 ms) and its 0.1 m/s → 10 cm speed sensitivity at 15 m agree with ours (4.8 ms; 1 fps → 1.6 cm at 4 m).

## 7. The target (`exports/turret/target/target.json`, `target.png`)

| Range | 1 m | 2 m | 3 m | 4 m | at the muzzle, 70 fps cap | stock Rival, 97 fps |
|---|---|---|---|---|---|---|
| Speed (fps) | 51 | 48 | 45 | 43 | 70 | 97 |
| Momentum (N s) | 0.028 | 0.027 | 0.025 | 0.024 | 0.039 | 0.054 |
| Energy (J) | 0.22 | 0.20 | 0.18 | 0.16 | 0.42 | 0.81 |
| Energy density (J/m²) | 550 | 490 | 430 | 390 | 1,030 | 2,000 |
| vs EN 71-1 0.5 J / ASTM 2,500 J/m² | 44 % / 22 % | | | 32 % / 16 % | 84 % / 41 % | 162 % / 80 % |

Knock-over: the game's 20 g hinged plate (4° rest lean) goes over at every range with a 17× margin; a 150 g plywood plate at 4° or 10° lean
too; the heaviest 200 mm hinged plate one ball tips at 4 m is **480 g at 4° lean, 190 g at 10°, 97 g at 20°**; a free-standing empty can goes,
a quarter-full 500 ml bottle and a 200 g box do not. Kid safety: at the set speed a ball carries a third of a stock Rival's energy; at the cap
half; both under the toy limits, which a stock Rival exceeds.

## 8. The turret's own dynamics (`exports/turret/e2e/dynamics.json`)

| Item | Value |
|---|---|
| Recoil | 0.030 N s per shot, 57 N peak for 4.8 ms, 0.85 N m peak about the tilt axis (the ball path is 15 mm under it); the tilting group turns 1.2 mrad nose-down before gravity's 0.04 N m preload stops it, inside the servo's 8.7 mrad lash; no pan moment |
| Gyroscopic | each tyre carries 3.8 mN m s; a pan slew is about the spin axis (no torque); a 200 deg/s tilt loads each Snail mount with 13 mN m, equal and opposite for the pair (net zero on the cartridge); one wheel faulted: 13 mN m, 0.5 % of the tilt servo's stall |
| Tilt servo | sustained need 0.12 N m (move + mean recoil at 10/s + one-wheel gyro) against 0.76 N m available at the move's peak speed: margin 6.5; hold margin at stall 63 |
| Pan servo | speed-limited (45 rpm through 3:1 = 90 deg/s at the turret): a 90° move takes 1.0 s at best; the 90° in 1.2 s target holds; torque margin large |
| Aim movers (mrad; cm at 2 / 4 / 6 m) | recoil 1.2 (0.2 / 0.5 / 0.7, down); **pan gear lash 7.6 (1.5 / 3.0 / 4.6)**; pan servo lash through 3:1 2.9; **tilt servo lash 8.7 (1.7 / 3.5 / 5.2)**; resolution 0.5 pan, 1.5 tilt; **pan slew 90 deg/s 14.5 (2.9 / 5.8 / 8.7)** |

## 9. Power across the ring (V3; `exports/turret/e2e/power.json`, `power.png`)

**v0 (D42):** the X2216's wheel takes 3.0 J at the set speed. Spin-up ramps against the ring's paralleled +24 V pair
(60 mOhm): 200 ms 3.56 A (1.78 A a circuit), **300 ms 2.51 A (1.25 A a circuit, 95 % speed in 0.285 s)**, 400 ms 2.0 A,
600 ms 1.49 A; stepped (never) 12.0 A. 8 shots at 10/s: 2.28 A peak, 0.65 A RMS. The firmware's soft start is 300 ms
(bench test 4.5 accepts at most 3 A). Before D42:


ESC DC-side current = duty × phase current / 0.95; the D24V150F12 at 90 %, 32 A instantaneous, 13.3 V dropout; 3 × 1,000 µF; the ring at 10
and 60 mΩ; the launch model's 7 % speed drop per shot.

| Case (60 mΩ ring) | Ring peak | RMS over 1 s | Charge | Bank minimum | ESC DC peak | Phase peak |
|---|---|---|---|---|---|---|
| Spin-up, stepped on the 10 A limit | **12.0 A** (36 ms to 95 % speed) | 1.69 A | 0.57 C | 23.3 V | 21 A | 10 A |
| Spin-up, 200 ms ramp | **2.19 A** (190 ms to 95 %) | 0.59 A | 0.37 C | 23.9 V | 3.9 A | 2.0 A |
| 8 shots at 10/s | 4.85 A | 1.16 A | 0.46 C | 23.7 V | 8.7 A | 4.1 A |

The ramp keeps the ring at the plan's ~2 A; nothing drops out; the burst's recovery pulses are 4.9 A for ~3 ms each. 1.9 J per wheel at speed.

## 10. The chronograph gates (V13, the coordinator's item 4)

| Spacing | 55 fps | 58 (p99 at set) | 66 (trip) | 70 (cap) | 123 (24 V fault) | 30 µs edge jitter | 5 % RC window | bore loss between gates |
|---|---|---|---|---|---|---|---|---|
| 50 mm (CAD: x0 + 30, x0 + 80) | 2,983 µs | 2,828 | **2,486** | 2,344 | 1,334 | 0.8 fps | 3.3 fps | 0.6 fps |
| 60 mm (x0 + 22, x0 + 82) | 3,579 | 3,394 | **2,983** | 2,812 | 1,600 | 0.66 fps | 3.3 fps | 0.8 fps |

A ball occludes a gate for 1.1-1.4 ms; a 1 mm beam is crossed in 47-60 µs. The RC window's tolerance is the dominant error: with ±5 % the trip
wanders 63-69 fps; use a 1 % timing part (or the MCU's timer as primary with the RC as backup). Recommendation: **60 mm spacing, gates at
x0 + 22 and x0 + 82** (8 mm past the socket, 18 mm before the muzzle, clear of the orange tip's boss), the Ø3.2 cross holes slit to a 1 mm beam,
trip window 2.98 ms. The 24 V fault ball crosses in 1.3-1.6 ms, unmistakable, but it has left: the RPM pre-feed check is what stops it.

## 11. End to end: the burst scenario (`exports/turret/e2e/e2e.json`, `e2e.png`, `e2e_*.mp4`)

The scene: the posed CAD on the robot's box (TM face 0.55 m up, est), 20 g hinged plates at 2 m (bearing +20°), 4 m (0°) and 6 m (−25°),
centres 0.30 m up; the turret slews to each (90 deg/s pan, 100 ms ramps; the tilt from the flight model's aiming solution: −8.3°, −0.5°,
0° — the 6 m target would need +1.5°, refused) and fires a 5-ball burst at 3/s. Four runs: 'settled' and 'panning' at the 55 fps set
speed and at the rail's maximum (95 % of no-load, 57.3 fps). Each ball goes feed → launch (with the burst's wheel speeds) → bore →
MuJoCo flight from the muzzle's pose and velocity at the instant it leaves, with the recoil pulse on the tilt body.

| | settled 55 | panning 55 | settled 57 | panning 57 |
|---|---|---|---|---|
| Balls fed of 15 steps | 13 | 12 | 12 | 13 |
| 2 m: crossings inside the plate / plate down | 5 of 5 / 0.92 s | 5 / 0.91 | 5 / 1.04 | 5 / 0.89 |
| 4 m | 4 of 4 / 3.34 s | 3 / 3.22 | 3 / 3.39 | 4 / 3.26 |
| 6 m (declared unreachable) | 4 balls at 2-4 cm height, floor | same | same | same |
| Heights at the 4 m plane (cm; plate 18-42) | 26-38 | 28-37 | 31-36 | 30-36 |
| Sideways at the plane (cm) | within ±1.2 | ±0.3 | ±0.5 | ±0.3 |
| Speed at the plate, 2 m / 4 m | 49-51 / 42-44 fps (the first ball of each burst 37-40: it rode a lighter wheel speed... see below) | | 50-53 / 45-46 | |
| Impact energy at 2 m / 4 m | 0.13-0.20 J / 0.12-0.17 J; analytic knock-down true for every ball | | | |
| Command → muzzle | 229-253 ms (feed 218-243 + nip 4.6 + bore 7) | | | |
| Python vs MuJoCo flight at the plane | dz ≤ 0.8 cm, sideways ≤ 0.01 cm (after the Magnus mapping fix: MuJoCo's spin lift is (C_M − 0.5) ρ V ω × v) | | | |
| Pan rate when the balls left | 0 deg/s in every run: the 240 ms latency outlasts the servo's settling, so 'panning' fired after settling (finding 10) | | | |

The first ball of each burst is 3-10 fps slower at the plate than the rest in these runs: it left the nip at 53 fps against 55-56 for the
others, because the launch chain starts each burst with the wheels exactly at the set speed and the PI loop's integral at zero, then
overshoots slightly on recovery (the 3-9 fps step from ball 1 to ball 2 is a model artefact of the loop's initial state, not a physical
droop; the full-population study shows no droop). Hits counted by contact are 1-3 per plate because the plate falls after the first ball and
the rest fly over it. Frames looked at: `e2e_settled_55fps-frame-0020.png` (the first ball in flight to the 2 m plate), `-0097.png` (the 2 m
plate flat, a ball on its way to the 4 m plate), `-0198.png` (the 6 m balls on the floor), `e2e_panning_55fps-frame-0048.png`; the 4 and 6 m
plates sit outside the fixed camera's frame, which the next run should widen. The checks (`e2e.json` `checks`, keyed to the charter):

| Checklist item | Result |
|---|---|
| The ball sourced; spread swept | pass |
| Launch: the 70 fps cap at 100 % throttle with tolerances | pass, 68.0 fps highest case, 2.0 fps margin (thin: finding 4) |
| Launch: 1D ↔ 3D hand-over | pass (< 0.1 %) |
| Bursts: speed droop ≤ 1 fps at 3-10/s | pass (0) |
| ARM release with braking | pass (phase short: rests from 30 ms; coast would leave at 53 fps) |
| Trajectory: drop, drift, dispersion 1-8 m; reach | pass (section 6) |
| Recoil ≤ 0.05 N s, aim kick ≤ 3 mrad | pass (0.030 N s, 1.2 mrad) |
| Servo margins | pass (tilt 6.5; pan 90° in 1.0 s) |
| Feed: no doubles, nothing stuck, at every pose and rate | **fail: 3 doubles in 108 steps** (two at ≥ 5/s, one with the robot rolled 15°), 0 stuck; 29 empty steps (the hopper, finding 1) |
| Feed: parked safe under jolt and vibration, powered or not | pass (0 leaks) |
| Rate of fire ≥ 3/s | pass (4/s clean by stepping; latency 240 ms) |
| Kid safety at the cap | pass (0.42 J, 1,030 J/m²) |
| End to end: reachable plates hit and down, unreachable ones declared | pass in all four runs |

## 12. Findings for the CAD (for the program agent), each with the number that demands it

1. **Hopper agitation.** With the dial stepped as the M2006 really steps (90-125 ms), only 3 of 7 pockets are filled after settling and 10-30 %
   of steps come up empty (section 3); rigid spheres under-predict real foam's bridging. Add agitation that does not depend on the step's jerk:
   taller/angled stirring vanes on the dial, an eccentric cam ring under the pile, or a hopper floor sloped ≥ 25° towards the pocket ring; and
   give the firmware a "dither" (±10° jiggle) on an empty step. Verify with the 300-ball jam counts of the bench plan.
2. **Dial step rate.** The step takes ~100 ms at the C610's 10 A and 180-310 ms at the plan's 3 A cap: the plan's cap makes 3/s marginal.
   Allow 10 A for the 100 ms of a step (the ring sees it through the 24 V dial rail: 1.8 N m × 150 rpm is 28 W, ~1.5 A for 0.1 s) or accept
   ≤ 2.5/s. Either way the clean maximum by stepping is 4/s; 10/s is not reachable with a gravity drop.
3. **Exit hole for continuous feeding (optional).** The ball + 1.5 mm exit hole lines up with a pocket for only ±1.2° of dial travel, so
   continuous rotation feeds nothing at 15-45 rpm. If continuous feeding is ever wanted, slot the exit along the pocket circle by ≥ one ball
   diameter (and re-check the parked pocket's blocking); if not, keep stepping and the hole as is.
4. **The speed ceiling margin.** The whole swept population at 100 % throttle, +5 % KV, +4 % rail, runout and soft-tyre growth reaches 68.0 fps on
   Ø36 at 12 V (2 fps under the cap; the worst corner ball alone 64.2). Print the Ø34 tyres with the set (63.5 fps ceiling) and let the bench
   ceiling test choose; keep every ESC on the fixed 12 V rail and keyed away from 24 V; a 24 V fault is 79-128 fps.
5. **Tyre growth.** TPU 95A tyres grow 0.23-0.69 mm radially at the set speed (0.34-1.01 at no-load): the crush is 27-31 % at speed, not 25 %.
   Harmless for speed (+0.4 fps) and good for centring, but the cage's wheel cavities (Ø40 + 0.75 mm clearance at 11 mm... `cav_r` 20 mm) need
   ≥ 1 mm radial clearance over the grown tyre, and the hub's rim must hold a tyre that is 1-4 % looser at speed.
6. **Pan gear backlash.** 0.15 mm per flank on the 63 T ring is 7.6 mrad (4.6 cm at 6 m), the largest static aim error. Options: thin only the
   pinion's teeth by 0.05 mm and spring-load the servo mount against the ring (a slotted servo pocket with a compression spring), or have the
   firmware always approach a target from the same side (free).
7. **Tilt lash and the recoil direction.** The tilt servo's ≤ 0.5° lash is 8.7 mrad; gravity preloads it nose-up (the CoM is 3-7 mm behind
   the axis) and the recoil kick (0.85 N m peak, 1.2 mrad) does not cross it: keep the CoM behind the axis at every hopper fill (it is: motion.json).
8. **Fire-while-panning.** The muzzle's 155 mm lever gives 14.5 mrad at 90 deg/s: fire only under ~10 deg/s of pan rate (the e2e's 'settled'
   mode) or lead by 0.16° per 10 deg/s in firmware.
9. **Range at the set speed, and the 65 fps default.** Level from 0.55 m a 55 fps ball reaches a 0.30 m target only to 3.5 m; the game's 4-6 m
   targets need 65-70 fps (4.1-4.4 m) and/or the robot standing 0.15-0.30 m taller (5.0-6.2 m at 0.85 m). But 65 fps cannot be set on the
   present hardware: the nominal ball at 100 % throttle on 12 V / Ø36 is 59.5 fps (the ceiling that holds the cap is the same thing that caps the
   range), so the set speed can only be 50-57 fps. Decide together: the muzzle height (the standing stance), the tyre diameter and rail (Ø38 at
   12 V reaches 62.7 fps nominal but its swept ceiling is 70.1 fps, over the cap; Ø36 at 13 V 71.8), or accept 3.5-4.3 m. The physics favours
   height: +0.15 m of stance buys as much reach as +10 fps and costs no safety margin.
10. **Latency and panning.** The first ball leaves ~240 ms after the fire command, by which time a decelerating pan servo has settled (the e2e's
    'panning' mode fired every ball at 0 deg/s pan rate). What matters is the pan rate when the ball leaves, not at the command: fire-on-the-move
    needs the firmware to predict the pan rate 0.24 s ahead, or simply to hold the pan still for 0.25 s after each command.
11. **Chronograph gates.** Space them 60 mm (x0 + 22, x0 + 82) with 1 mm slit beams (section 10).
12. **The release brake and the stray ball.** The phase short works as planned (τ 12 ms, 5 % at 45 ms); keep the cartridge's channel floor
    continuous through the nip (it is) so the stray ball rests on it; the firmware's arm sequence starts muzzle-down with a stray clear.
13. **Recoil and gyro loads** need no structural change (57 N on the cage for 5 ms; 13 mN m per motor mount).
14. **Bore play from the nip to the muzzle.** Make the ball channel after the tyres and the barrel's bore ball + 2.0 mm (1.0 mm of play)
    instead of + 1.5: the muzzle pitch scatter falls from 11.5 to 5 mrad, the yaw scatter from 3.9 to 2.6, the speed loss from 1.0 to 0.7 fps,
    and the topspin becomes consistent (102 ± 40 rad/s instead of 69 ± 82), halving the vertical dispersion at 4 m. Keep the dial pockets and
    the chute at + 1.5 (they fed cleanly). Do not go tighter: + 1.0 doubles the scatter and + 0.5 sticks balls.

## 13. Bench test plan

The ball tests (size/mass, compression, restitution, friction, tyre growth) and the launcher tests (chronograph vs wheel speed per brand, the
100 % throttle ceiling on the nominal and +4 % rail, high-speed video of the nip and the muzzle) are itemised in `ball.json` `bench_plan` with
what each number replaces. In addition: the jam-rate counts (300 balls per pose at 3/s and at the maximum rate, new/worn/damp balls, 30- and
5-ball hoppers), the slew-and-jolt feeding test on a lazy-susan stand, paper targets at 2/4/6/8 m (20 shots each from a clamped turret:
drop, drift, 1-σ radius), the knock-down counts, the ring's shunt trace for the stepped and ramped spin-up (expect 12 and 2.2 A), the trip
test with simulated 1.3 ms and 2.6 ms gate pairs, and the release test (wheels at 5 % within 50 ms; 20 releases during feeding: no ball above
20 fps unless it was already in the nip).

## 14. Limits of the models

- Rigid spheres cannot bridge by tack; the feed's empty-step rate is a lower bound. Friction is Coulomb with no adhesion; wear and fuzz are
  scale factors, not surfaces.
- The launch's foam law is Hertz with a restitution-matched damping; real foam plateaus beyond ~10 % strain, which the swept modulus brackets but
  does not model; the tyre is rigid except for its ring growth; no tyre wear or heating; the ESC is an ideal current source under a PI loop.
- The flight has no spin decay and a constant Cd in the subcritical range; a fuzzy, worn ball's Cd is a sweep (0.47-0.55), not a measurement.
- MuJoCo's ball flight uses the ellipsoid fluid model with coefficients mapped from the Python model (checked at the target plane, section 11).
- The servos are torque-speed-line PD loops; the STS3215's internal loop, its 345:1 gearbox's compliance and the backlash are not in MuJoCo
  (the backlash is accounted analytically). The robot body is fixed at the mount height (0.55 m, est): the balancing body's motion is not
  in the scene beyond the pitch/roll poses and the jolt in the feed.

## 15. Re-running when the CAD changes

```
.venv/bin/python sim/turret_ball.py                   # sources, ranges, bench plan
.venv/bin/python sim/turret_launch3d.py [--quick]     # launch, ceiling map, release, stray ball, 24 V fault, chronograph (~4 / 15 min)
.venv/bin/python sim/turret_flight.py [--quick]       # barrel, flight, reach, slew, validation
.venv/bin/python sim/turret_target.py
.venv/bin/python sim/turret_feed_dyn.py [--quick] [--video]   # the feed under motion (~3 / 15 min)
.venv/bin/python cad/turret_motion.py && .venv/bin/python sim/turret_dynamics.py
.venv/bin/python sim/turret_power.py
.venv/bin/python sim/turret_e2e.py [--quick] [--no-video]     # the chain and the checks (~10 min)
```
Every file reads `cad/turret.py` at import; if the CAD is mid-edit and fails to import, wait and retry.
