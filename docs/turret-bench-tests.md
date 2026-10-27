# Turret bench tests

What to measure on the first built turret, in the order it is built, and the number each test must meet. The pan
joint's electrical tests are written out in docs/turret-plan.md section 6 (6.1-6.9) and are referenced here, not
repeated. Every test writes its raw readings and its pass or fail to a JSON file under exports/turret/bench/, named
after the test, so the charter's checklist (docs/turret-program.md) can link the evidence.

Rig: the turret on its stand (cad/turret_stand.py, the bench ring), the laptop on the USB-CAN, the hold-to-run
pendant, a 24 V supply with a 15 A current limit, a 20 mOhm shunt in the ring's +24 V stator lead, a two-channel scope,
a chronograph (two gates of our own in the barrel, and a commercial one 1 m out as the reference), a 0.01 g scale,
calipers, a spring scale to 100 N, a thermocouple.

## 1. Parts and fits (before anything is powered)

| Test | How | Accept | Source of the number |
|---|---|---|---|
| Printed sizes | measure the bearing seat (Ø65.0), the journal (Ø50.0), the carrier's opening (Ø65), the CT dowel holes, the tyre bore | within the printer's tuning: bearing seat a light press, journal a slip fit; tyre bore 26.9 (4 % under the rim) | cad/turret.py BRG, TYRE_STRETCH |
| Inserts | pull one M3 and one M4 insert from a test coupon with the spring scale | > 300 N (M3), > 500 N (M4); the FEA's fastener checks assume ~700 and ~1100 N | cad/turret_studies.py hand checks |
| Gear mesh | mount the pinion and the turntable; dial-indicator backlash at the turntable's rim | 0.2-0.4 mm at the pitch circle (0.15 mm per flank drawn); no binding over a full turn | cad/turret.py gear_profile |
| Tilt stops | turn the cradle by hand | hard stops at 0 deg (barrel level, never above) and -25 deg; no other contact | cad/turret.py stop sectors |
| Clash | turn the pan by hand through 2 turns at tilt 0 and -25 | nothing touches; the ring's leads do not wind | exports/turret/clash-sweep.json |
| Ball sizes | 50 balls of each brand on the calipers and the scale | Ø22.2-22.8 mm, 1.6-1.9 g; reject the outliers from the hopper | docs/turret-physics.md section 2 |

## 2. Strength (mechanical, before the motors)

| Test | How | Accept | Source |
|---|---|---|---|
| Push at the muzzle | 50 N up on the muzzle with the cradle on its 0 deg stop, 1,000 times | no crack, no creep of the stop (< 0.2 mm) | the everyday case the FEA leaves closest to its target: the cradle's and the yoke's E-push-up (cad/turret_studies.py, exports/turret/fea/summary.json) |
| Lift by the yoke | lift the whole turret by its yoke (spring scale) to 300 N | no movement of the bearing's outer race; the aluminium clamp flat | the pan clamp's FEA (R-fall-up, SF 3.1 in 6061-T6) |
| Pan servo stall | hold the turntable and command the pan servo to 50 % torque, then (once) to 100 % | no tooth damage at 50 %; at 100 % a tooth may mark but not crack | the pinion FEA (SF 2.52 / 1.26) |
| Drop | turret on its stand, 30 cm drop onto a rubber mat, upright and on its side | nothing cracked, every fastener tight | the 30 g cases in cad/turret_studies.py |

## 3. Electrics without motors

1. Power-up with the motors' rails unplugged at the CT: the logic and aux rails, the Feather's heartbeat on CAN.
2. The safety line faults, docs/turret-plan.md 6.5, with a lamp on the motor rails instead of the ESCs.
3. The overspeed trip with simulated gate pairs, 6.7 first half. Set the window's R by selection here (1.3, 2.6, 3.0 ms
   pairs; the 60 mm gates trip at 2.98 ms, docs/turret-wiring.md 3.2).
4. Homing (docs/turret-firmware.md 3): 100 power-ups at random pans; the index centre's spread **within 0.1 deg**
   (the reference implementation's model gives 0.07: firmware/turret/test_homing.py); 10 continuous turns each way
   and back to the start **within 0.2 deg**; every homing **within 7 s**.
5. The pan joint, 6.1-6.4 and 6.6 (contact noise, CAN error counters, temperature, life, the servo bus over the ring).

## 4. Flywheels (the speed ceiling first)

1. **V13, the ceiling**: the wheels at 100 % throttle on the 12 V regulator, no ball: both wheels' eRPM **at or below
   10,437 x 1.05 x 1.04 = 11,400 rpm**; then 20 balls at 100 %: every one **at or under 66 fps** on both chronographs.
   With the Ø36 tyres the model leaves 2 fps; if any ball passes 66 fps, fit the Ø34 set (64.5 fps modelled on this
   cartridge) and repeat. Never run this test with 24 V on the ESC rail.
2. Set speed: 9,408 rpm (Ø36) or the Ø34 equivalent; 50 balls: **mean 55 +- 2 fps, SD <= 1.5 fps**
   (docs/turret-physics.md section 4: 55.8 +- 1.3 modelled).
3. Spin-up current: 6.1 step 3 (2.2 A ramped, 12 A stepped; the bench ring only ever ramped).
4. Braking on release: 6.8 (5 % speed by 50 ms; no ball above 20 fps after a release).
5. Tyre growth: the tyre's OD at the set speed by a strobe or high-speed video **within +0.7 mm**; the tyres stay put on
   their rims after 1,000 balls.

## 5. Feeding

| Test | How | Accept | Source |
|---|---|---|---|
| Jam rate | 300 balls per pose (tilt 0 and -25, pan still and slewing at 60 deg/s), at 3/s and at 4/s; new, worn and damp balls; a 30-ball and a 5-ball hopper | no double feed; jams (a step that needs a reverse) < 1 in 300; empty steps < 5 % after the dial's cone and fins | docs/turret-physics.md section 3, finding 1 |
| Parked safe | the dial parked, motor off, the turret shaken (5 m/s^2) and jolted (13.5 m/s^2) at tilt 0 and -25 | no ball reaches the wheels | feed_dyn.json |
| Hopper beam | fill to 30 | the beam reports full at 28-30 | |

## 6. Accuracy and the game

| Test | How | Accept | Source |
|---|---|---|---|
| Groups | the turret clamped, 20 shots at paper at 2, 4, 6 and 8 m | 68 % radius within 1.5 cm at 2 m and 5 cm at 4 m; the drop table measured for the firmware | docs/turret-physics.md section 6 |
| Aim repeatability | 20 moves to the same target from both sides | within 3 mrad when approaching from +pan only (the backlash taken up) | finding 6 |
| Fire while panning | bursts while panning at 10 and 90 deg/s | the firmware holds fire above 10 deg/s | findings 8, 10 |
| Knock-down | 20 g hinged plates at 2 and 4 m | every plate down | docs/turret-physics.md section 7 |
| Mock lidar | a Ø103 x 72 cylinder 148 mm ahead, its top 43.7 mm above the TM face | the depression table (exports/turret/lidar/lidar.json) keeps the barrel and every ball 10 mm clear | cad/turret_lidar.py |

## 7. What the results change

Each JSON goes into the charter's checklist as evidence. Numbers that differ from the models go back to their owners:
the launch and feed numbers to the physics agent (sim/turret_*.py), the fits and strengths to cad/turret.py and
cad/turret_studies.py, the timing and the homing to docs/turret-firmware.md.
