# Turret bench tests (v0)

What to measure on the first built turret (docs/decisions.yaml D42), in the order it is built, and the number each test
must meet. It follows docs/turret-prototype-plan.md section 5 with the v0 numbers from the physics' reruns
(docs/turret-physics.md, the v0 sections). Every test writes its raw readings and its pass or fail to a JSON file under
`exports/turret/bench/`, named after the test; `firmware/turret/bench_host.py` runs the ones that need the turret's
firmware or CAN and writes those files (its `--sim` mode rehearses every test against a simulated turret and writes to
`exports/turret/bench/sim/`, which is never evidence).

**The safety rules hold in every test:** the barrel never above horizontal (the hard stop at 0°); every ball at or
under 66 fps on the bench (the hard cap is 70); nothing spins or feeds unless the pendant is held; never 24 V on the ESC
side, not even for a test. Wear eye protection; the muzzle points into a catch box or at the targets.

**Rig:** the turret on its stand (cad/turret_stand.py) clamped to the bench through its tabs; the laptop on the
USB-CAN running `bench_host.py`; the hold-to-run pendant; the 24 V supply (Mean Well LRS-350-24) with a 10 A current
limit; a 20 mOhm shunt in the ring's +24 V stator lead; a two-channel scope with a 100:1 probe; the reference chronograph
1 m out beside the barrel's own gates; calipers; a 0.01 g scale; a spring scale to 100 N; a dial indicator on a
magnetic base; a thermocouple or IR thermometer; 300 balls of one brand (Worker Cheetah), plus 50 worn and 50 damp ones
for test 5.3.

## 1. Parts and fits (nothing powered)

| # | Test | Accept | JSON |
|---|---|---|---|
| 1.1 | Printed sizes: the bearing seat Ø65.0, the journal Ø50.0, the carrier's Ø65 opening, the tyre bore 26.9, the CT dowel holes, the hub's bore after reaming (5.00 on the X2216's pilot) | a light press for the seat, a slip fit for the journal, the hub a close slip fit on the pilot and flat on the adapter's flange | fits.json |
| 1.2 | Inserts: pull an M3 and an M4 insert from a PA6-CF coupon | > 300 N (M3), > 500 N (M4) | fits.json |
| 1.3 | Gear mesh: dial-indicator backlash at the turntable's rim; two full turns by hand at tilt 0 and -25° | 0.2-0.4 mm; no binding; nothing touches; the ring's leads do not wind | fits.json |
| 1.4 | Tilt stops by hand | hard stop at 0° (level) and -25°; nothing else touches at any pan | fits.json |
| 1.5 | Hub runout on each X2216 (dial indicator at the rim, motor turned by hand) | <= 0.15 mm; the tyre stays put after 50 turns by hand | fits.json |
| 1.6 | Ball sizes: 50 balls on the calipers and the scale | Ø22.2-22.8, 1.6-1.9 g; outliers rejected from the hopper | balls.json |
| 1.7 | The ring turns freely by hand with the carrier's screws loose and tight; the tube coupling does not load it sideways | no change in stiffness when tightened | fits.json |
| 1.8 | The motors against SunnySky's drawing: the 16/19 M3 cross, the 32 mm stack, the prop adapter's Ø5 pilot and M5 stud | as cad/turret.py MOTOR; else the cage plate is redrawn before the cartridge is printed | fits.json |

## 2. Strength (bench level; the robot's falls are v1)

| # | Test | Accept | JSON |
|---|---|---|---|
| 2.1 | 50 N up on the muzzle with the cradle on its 0° stop, 200 times | no crack; the stop creeps < 0.2 mm (the yoke's and cradle's everyday case, exports/turret/fea/summary.json) | strength.json |
| 2.2 | Lift the turret by its yoke to 100 N (spring scale) | the bearing's outer race does not move under the aluminium clamp | strength.json |
| 2.3 | The pan servo at 50 % torque against a held turntable (once), then held 10 s | no tooth marks | strength.json |

## 3. Electrics without motors (the ESC and feed rails unplugged at the CT)

**Before the first power-up:** the Pololu 2815's slide switch is OFF (docs/turret-wiring.md: with it ON the safety line
cannot cut the flywheels), the in-line fuse is the 5 A MINI, the Feather's Trm jumper is closed (its 120 R is the
turret's only CAN terminator), and the CT power plug is out (the signal plug goes in for 3.4).

| # | Test | Accept | JSON |
|---|---|---|---|
| 3.1 | Power-up: 5 V, 3.3 V, 12 V MAIN and 12 V PAN present; the Feather's heartbeat on CAN; the pan and tilt servos answer their IDs. With the pendant held: the 555's train at ring 7, the drop across R8, and every Feather input on the scope (D0, D9-D12, A0, A1, A4) | all within 2 s; no fuse or polyfuse opens; 930-1,045 Hz (986 nominal); R8's drop 3.5-5.3 V peak (1.6-2.4 mA in the opto's LED); no Feather pin above 3.4 V | electrics.json |
| 3.2 | The pulse-train safety line with a 12 V lamp on 12 V FLY: pendant held -> lamp on; released -> off; the SAFETY pair opened at the ring, shorted to GND, shorted to +24 V, held at a DC level. Then a 300 Hz and a 3 kHz train and 50 Hz hum from a generator, with the wheels' throttle commanded | the hardware faults turn the lamp off within 25 ms (scope on the 2815's output); the wrong-frequency trains leave the lamp on (the one-shot sees edges) and the firmware zeroes the throttle and refuses to feed within 10 ms (PULSE_MON) | safety_line.json |
| 3.3 | The trip latch with simulated gate pairs from a generator at 1.3, 2.6, 2.9, 3.1 and 3.5 ms (60 mm gates: 2.98 ms is 66 fps) | latched at <= 2.9 ms (>= 67.9 fps), not at >= 3.1 ms (<= 63.5 fps); it holds until the button; ARM cannot rise while latched. Select one-shot B's R (60-73 k) here | trip.json |
| 3.4 | Brake timing: the cartridge's signal plug in, its power plug out (no motor powered); scope ARM (CT signal 5), BRAKE (U12 pin 2) and 12 V FLY; release and re-arm 5 times | BRAKE rises 5-14 ms after ARM falls (6.8 ms x ln(3.3 / V_T-)); falls within 1 ms of ARM rising (D3 and R26; the ESCs drive nothing for 0.5 s after 12 V FLY returns, AM32 arming on zero throttle); each FET gate at >= 4.3 V while BRAKE is high | brake_timing.json |
| 3.5 | Homing: 50 power-ups at random pans | every home within 7 s; the index centre's spread <= 0.1°; 10 continuous turns each way and back within 0.2° | homing_bench.json |
| 3.6 | The servo bus over the ring: 1 h of 100 Hz reads and writes to the pan servo at 500 kbit/s while panning | checksum retries < 0.1 %; no command lost (position within 2 counts) | ring_bus.json |
| 3.7 | Ring contact resistance and dropouts: 5 A through the paralleled pairs at 12 pan positions, then panning at 15 and 2 rpm, scope at 1 MHz | <= 60 mOhm per paralleled pair; no dropout > 100 us; variation <= 60 mOhm | ring_contacts.json |
| 3.8 | CAN over the ring: 1,000 frames/s at 15 rpm for 1 h, then at 2 rpm for 1 h | 0 bus-off; error frames < 1 in 10^6; no lost telemetry second | ring_can.json |
| 3.9 | The feed servo alone (12 V from the bench through CT power pins 1-3, the ESCs unplugged): 200 steps of 45° under an empty hopper, then a full one | settled within 2° in <= 250 ms (the model: 232-246 ms); the load reading repeatable; a pencil in a pocket detected within 300 ms and reversed | feed_servo.json |

## 4. Flywheels: the ceiling before anything else

| # | Test | Accept | JSON |
|---|---|---|---|
| 4.1 | **No-load speed at 100 % throttle on the 12 V rail**, no balls, both wheels (eRPM telemetry / 7; confirm first that each ESC returns bidirectional-DShot eRPM, which the pre-feed check needs: firmware/turret/am32_settings.md) | **<= 11,180 rpm (78,260 eRPM)** for the Ø34 tyres: at or under that every ball stays under 66 fps by the model (the worst-corner motor and rail make 11,461); the rail 12.0 ± 0.5 V under load. Above it: stop, a lower-KV motor | ceiling.json |
| 4.2 | **Ceiling with balls**: 20 balls at 100 % throttle, Ø34 tyres | every ball <= 66 fps on both chronographs. Any ball over 66: this motor and tyre are rejected (Ø32 cannot be used: it does not grip). Ø36 is not fitted with the X2216 (70.7 fps at the worst corner) | ceiling.json |
| 4.3 | Speed at every throttle: 10 balls each at 60, 70, 80, 90 and 100 % | a monotonic table, SD <= 1.5 fps at each: the firmware's throttle-to-speed map | speed_map.json |
| 4.4 | Set speed: 50 balls of one brand at the set speed for 52 fps (8,855 rpm, 61,985 eRPM) | mean within ± 2 fps of 52, SD <= 2.5 fps (the model's one-brand spread is ~2), none over 60 | set_speed.json |
| 4.5 | Spin-up current at the ring's shunt with the **300 ms ramp** (never a stepped start on this ring) and burst recovery (8 balls at 3/s) | peak <= 3 A at 24 V (the model: 2.5 A); the bus never below 16 V at the board; no ESC reset; every shot of the burst within ± 3 fps of the set speed | power.json |
| 4.6 | **The 24 V fault, simulated without a ball**: (a) hopper empty, muzzle into the catch box, the feed servo unplugged, no balls anywhere on the bench: feed the ESC rail from the bench supply at 24 V through the CT power plug only, read the no-load eRPM (expect ~21,000 rpm) and confirm the firmware's pre-feed check goes SAFE and refuses to step; (b) the trip latch with a 1.3-1.6 ms simulated gate pair (test 3.3). Never a ball at 24 V | (a) SAFE within 100 ms of the first eRPM read over the limit; (b) latched | fault_24v.json |
| 4.7 | Release braking: wheels at speed, no ball; release; scope one phase through the 100:1 probe and read eRPM | the ESC rail off <= 25 ms after the last pulse (the one-shot: 18 ms, 16-22); the short closed 5-14 ms after the rail off; speed <= 5 % by +50 ms after the rail off (the model: the short alone reaches 5 % ~48 ms after ARM falls; AM32's brake on stop, from ~4 ms, makes it sooner); the FETs < 60 °C after 20 releases in 2 min | release.json |
| 4.8 | Tyre growth and creep: the OD at the set speed by strobe or video; the tyres after 500 balls | growth <= +0.7 mm on the diameter; no creep on the rim | tyres.json |
| 4.9 | Ring temperature: 5 A for 1 h at 15 rpm, a thermocouple on the ring's body and the carrier | rise <= 20 K | ring_temperature.json |

## 5. Feeding

| # | Test | Accept | JSON |
|---|---|---|---|
| 5.1 | 100 balls per pose at 3/s: level; -25°; level while panning at 60 deg/s | 0 doubles; <= 1 jam per 100 (a step that needed a reverse); <= 5 % empty steps after the dither; jams and empties logged per 100 | feed.json |
| 5.2 | The firmware's maximum rate (3/s: the model shows the servo's 235 ms step leaves too little time for the ball to fall clear at 4/s) | 0 doubles | feed.json |
| 5.3 | 50 worn and 50 damp balls, level, 3/s | 0 doubles; jams logged (information) | feed.json |
| 5.4 | Parked safe: the dial parked, the rail off; the stand shaken by hand (~5 m/s²) and knocked (~13 m/s²) at tilt 0 and -25° | no ball reaches the wheels | feed.json |
| 5.5 | The last 5 balls of a hopper at -25° | the lift-to-0 rule empties it; no ball left behind | feed.json |

## 6. Accuracy and the game

| # | Test | Accept | JSON |
|---|---|---|---|
| 6.1 | Boresight the laser at 4 m | the dot within 2 cm of the group's centre at 4 m | groups.json |
| 6.2 | Groups: the turret clamped, 20 shots at paper at 2 m and at 4 m, the barrel level and at the tilt the firmware chooses for a 0.30 m target | 68 % radius <= 1.5 cm at 2 m, <= 5 cm at 4 m; the group centres recorded: the drop table | groups.json |
| 6.3 | Aim repeatability: 20 moves to the same target from both pan sides | within 3 mrad approaching in +pan | groups.json |
| 6.4 | Fire while panning at 10 and 90 deg/s | the firmware holds fire above 10 deg/s | game.json |
| 6.5 | Knock-down: 20 g hinged plates at 2 and 4 m (sim/turret.py's plate), 5 balls each | every plate down | game.json |
| 6.6 | Temperature: 100 balls in 2 min, then 10 min at speed; the IR gun on the ESCs, the motors, the flywheel regulator and each servo | ESCs <= 80 °C, motors <= 70 °C, the regulator <= 60 °C, the servos <= 60 °C | game.json |
| 6.7 | Safety-line release during feeding: 20 releases at random points of 8-ball bursts | no ball above 25 fps after a release, and none above 20 fps that was more than 10 ms from the nip at the release (docs/turret-physics.md section 5); where each resting ball ended up, logged | game.json |

## 7. Where the numbers go

Numbers that differ from the models go back to their owners: the launch and the feed to the physics
(sim/turret_launch*.py, sim/turret_feed_dyn.py), fits and strength to cad/turret.py and cad/turret_studies.py, timings
to docs/turret-firmware.md. The v0 sign-off (plan T15) ticks the charter's checklist with these JSON files.
