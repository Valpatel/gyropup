# Turret prototype plan: v0 on the bench, then v1 on the robot

Written 2026-10-27 by the planner (Fable 5.1) for the turret program agent (Opus 5.5), from a read of the turret
worktree `~/Code/gyropup-turret` (branch `turret/program`, commit 55bb6a7) and of main (8717f28). The user's words: "Fable
5.1 should review our turret and figure out how we drive that towards a first physical prototype, then opus 5.5 should
work the plan, make sure we pick highly available components and keep the design simple etc."

This page is the review and the plan. Section 6 is the ordered task list; every task names its files, its acceptance
check and an estimate, and flags the ones that change the Turret API (`cad/turret.py` `Turret(L)`, `.posed()`, `.meta`,
`.bought`), because `cad/build.py` (the robot model), `sim/robot_v2.py`, `sim/turret_e2e.py`, `cad/build_turret_box.py`,
`cad/turret_assembly.py`, `cad/turret_motion.py`, `cad/turret_lidar.py` and `tools/part_images.py` all build on it.

Hard rules stand and are not relaxed anywhere below: the barrel never points above horizontal; muzzle speed at most
70 fps (21.3 m/s), held physically by a fixed 12 V flywheel rail (motor KV x rail x tyre diameter inside the cap);
nothing spins or feeds unless the safety line is held. Parts rule D40: off the shelf with a listed price and a buy
link, printed (PA6-CF, PETG, TPU on the P1S's 256 mm bed), or ordered online at an instant price. No quotes.

Prices and stock in section 3 were read on 2026-10-27 from public pages; each row says where and when. Nothing was
ordered and no vendor was contacted.

## 0. In one paragraph

**v0** is the turret as drawn in `cad/turret.py`, built on its printed bench stand, with four changes that make it
buildable this month and simpler: (1) the pan joint is the `CONTINUOUS_PAN = False` build that the CAD already keeps
(a +-170 deg pan on a cable loop through the Ø40 bore, with the stop post and finger), so the slip ring and everything
it drags in (the 1 kHz safety-pulse chain, the TTL-over-ring link, the 2 A-per-circuit budget, the ring connectors,
carrier, driver and coupling) move to v1; (2) the delisted DJI Snail 2305 flywheel motors become two stock 22xx-class
outrunners of about 880 rpm/V on the same fixed 12 V rail, with the tyre set (Ø34 / Ø36) absorbing the KV change and the
bench ceiling test choosing the tyre; (3) the out-of-stock DJI M2006 + C610 feed drive becomes a third Feetech STS3215
(the servo already on pan and tilt) stepping the dial 45 deg on the same serial bus, which removes the only CAN node on
the cartridge and a $250 ESC; (4) the lights, hopper beam, fill flap, TPU bumper, aluminium clamp and the mass cut are
v1. v0 keeps what the physics proved matters: the 12 V-only flywheel rail with keyed connectors, the two chronograph
gates with the hardware trip latch, the phase-short brake on release, the hard tilt stops, the ball + 2.0 bore, the
dial's cone and fins. It proves on the bench: feed -> wheels -> every ball at or under 66 fps at 100 % throttle -> aim
-> plates down at 2 and 4 m, with the pendant held. **v1** then fits the ring and the pulse chain, cuts the mass to
1.5 kg, adds the lidar depression table and the riser, the lights and beam, the aluminium clamp and bumper, and goes on
the robot's DT12 harness with the radio stop.

## 1. Review of the turret as it stands

### 1.1 What is right: keep it

| Item | Why it is right | Evidence |
|---|---|---|
| The physics chain and its 14 findings | Ball, feed, launch, bore, flight, target, dynamics and power are modelled end to end on the CAD at run time, and the findings are already in the CAD (ball + 2.0 bore after the nip, 60 mm gates with 1 mm slits, 0.5 mm wider wheel cavities, the tyre printed 4 % under the rim, Ø38 dropped, the dial's cone and fins) | docs/turret-physics.md sections 0-12; exports/turret/{launch,feed,flight,target,e2e} |
| The speed ceiling is physical | ESCs fed only by a fixed-output 12 V regulator; a 24 V fault is 79-128 fps, so the 12 V-only rule, keyed CT pins and the pre-feed RPM check are the safety items; the chronograph trip is the backstop | physics section 4 and 10; wiring 1.4 and 3.2 |
| Release braking | Phase-short brake, tau 12 ms, 5 % speed at 45 ms, before a dropped ball (96 ms) reaches the nip; a stray ball leaves at 7.7 fps on the next ramped arm | physics section 5 |
| The cartridge concept | The whole feed-and-launch group lifts off the cradle on two dowels and a thumbscrew with two keyed Micro-Fit plugs; everything that wears is on it | cad/turret.py `cartridge_body`, `ct_points`; assembly step 12 |
| The hopper, dial and baffle | 30 balls really fit (lid at 100 mm); the parked dial never lets a ball out, powered or not, through a 13.5 m/s^2 jolt; no double at <= 4 steps/s; nothing ever stuck in the chute | physics section 3 |
| Hard tilt stops, CoM behind the tilt axis | Unpowered the barrel rises to the 0 deg stop and can never drop onto the lidar; tilt hold margin 43 | cad/turret.py Geo (tilt_x 40), exports/turret/motion.json |
| The printed 63:21 pan drive on a 6810 bearing | Cheap, 90 deg/s, pinion SF 2.87 at the 50 % torque cap by Lewis and 2.52 by FEA; the one-sided approach in firmware takes the 7.6 mrad lash out | motion.json, exports/turret/fea/pan_pinion-*.png, firmware 5 |
| The bench stand and the TM interface | The stand carries the real TM pattern and the DT12 harness, so the bench turret is the robot turret; the hold-to-run pendant is wired through the same pins the radio stop will use | cad/turret_stand.py, wiring 1.1 |
| The parts discipline | Every bought line has a catalogue key, a part number, a price and a picture; alternates per part; the fits of the stand's switch, fuse holder and jack were found wrong by the sourcing pass and are already redrawn in the worktree (the rocker's 19.4 x 13.0 snap-in in a 2.5 mm panel, the Ø12.75 D-hole, the Ø6.35 jack in 2 mm) | exports/turret/bench/bom.json, catalog/alternates.json, the program log |
| The firmware plan | States, pin map, CAN set, the aiming rules from the physics (settle 0.25 s, one-sided approach, depression table, keep-outs), homing proven on 1,000 random starts | docs/turret-firmware.md, firmware/turret/test_homing.py |

### 1.2 Over-built or risky for a first prototype: simplify or defer

| Item | What it costs now | v0 decision | Comes back |
|---|---|---|---|
| **The slip ring and continuous pan** (D1, D2) | The ring itself is cheap ($28) but it forces: the safety line as a 1 kHz pulse train (555, 78L05, 4N35, 74HC123) because a ring contact can bounce or short; the pan servo's TTL across a ring; two 12-way Micro-Fit pairs; the carrier, driver and tube coupling; the 2 A-per-circuit budget that makes the soft start safety-critical; homing over continuous rotation. None of it is needed to prove the turret on a bench | **Cable loop.** `CONTINUOUS_PAN = False` is already in the CAD (stop post and finger, +-170 deg, the Ø40 bore free for a harness). The safety line becomes a dry loop that gates the Pololu 2815 directly. The index magnet and hall stay (they are $3.40 and the homing code exists); the homing sweep learns the stops | v1 (the robot wants continuous pan: D41 stands). The ring design work in the worktree is not wasted: it is behind the flag |
| **DJI parts** (Snail 2305, M2006 + C610) | Delisted / out of stock; the C610 is $250-320 elsewhere; the M2006 is 1 N m for a dial that needs ~0.05; the C610 adds a CAN node and DJI's protocol to the cartridge | **Swap** (section 3.1, 3.2): a 22xx outrunner of ~880 KV with the standard 16 x 19 mm M3 base; a third STS3215 for the dial | never |
| **Three-level board stack of perfboards** | Reasonable, but with the pulse chain gone level 1 shrinks to the 5 V regulator, the trip latch, the arm AND and the brake driver | Keep the bay as drawn (no CAD churn); fewer parts on level 1 | v1 adds the pulse chain back |
| **The chronograph trip latch** (D10) | Five logic parts and a selection test; the physics shows it acts only after one fast ball has left; the rail is the real ceiling | **Keep** (it is cheap, it catches a wrong regulator or wrong tyre, and the bench can test it with simulated gate pairs in ten minutes) | - |
| **The hopper agitator** | The feed sim shows 24 % empty steps with the M2006's 100 ms step; rigid spheres under-predict foam bridging. The cone and four fins are already in the dial print and cost nothing | **Measure first**: cone + fins + the firmware dither (+-10 deg on an empty step). Decide a cam ring or sloped floor from the 300-ball counts, not from the sim | v1 if the bench shows > 5 % empty steps after the dither |
| **Lights, buzzer, hopper-full beam, fill flap** (the "awesome" and dock items) | Parts, wiring and firmware that prove nothing on the bench | Defer | v1 |
| **SendCutSend aluminium pan clamp, TPU bumper ring** | The aluminium clamp's reason is the robot's fall case (R-fall-up SF 1.31 on the printed one); the bumper is for kids and the lidar. Neither is loaded on a clamped bench stand | Print the clamp in PA6-CF for v0 (the function exists; 0.7 h); no bumper. Order the aluminium clamp with the v1 kit (the DXF exists, instant price on upload) | v1 |
| **The specific laser** (Quarton VLM-520-73 LPT, $41.82, Digi-Key) | Out of stock at the only listed seller; Class 2 green is nice but not what v0 proves | An in-stock Class 2 red module (section 3.3); the mount's bore follows the part | v1 may go green |
| **Mass 1.59-1.62 kg with balls** (budget 1.5) | A robot problem, not a bench one; the new motors add ~70 g and the servo feed takes ~50 g off | Measure the v0 as built; cut in v1 | v1 |
| **The $75 AbleNet pendant** | A momentary foot switch does the same job for a fifth of the price | Foot switch primary (section 3.3); the AbleNet switch is the hand-held backup | - |
| **The stand's rocker switch** | The chosen E-Switch RCA1913 has no findable seller page | A DC-rated rocker that is sold (section 3.3) | - |
| **Fire-while-panning, pan backlash, tilt lash** | Aim movers of 7-15 mrad | Firmware rules already written (settle 0.25 s, one-sided approach); nothing to build | - |

### 1.3 What the bench must settle first (the models' open ends)

1. The real empty-step and jam rate of a foam pile over the cone and fins (the sim's 76 % delivery is a lower bound on
   the problem, not the answer).
2. The ceiling: the fastest ball at 100 % throttle on the real rail, real tyre and real motor (the model leaves 2 fps on
   Ø36 with the Snail; with the new motor the tyre set is chosen on the bench, section 3.1).
3. Tyre runout and creep on the printed hub (the new hub rides a prop shaft, not the Snail's pinned seat).
4. Whether the STS3215 steps the dial in <= 250 ms (3 balls/s) under a full hopper, and whether its load reading
   detects a jam.
5. The drop table at 2 and 4 m with the real topspin (the physics says it cannot be computed from speed alone).

## 2. Prototype v0, and the road to v1

### 2.1 v0 scope by subsystem

| Subsystem | v0 (bench) | v1 (robot-ready) |
|---|---|---|
| Pan joint | +-170 deg on a cable loop; stop post and finger; hall index at pan 0; `CONTINUOUS_PAN = False` | slip ring (SparkFun ROB-13065), continuous pan, carrier/driver/tube, `CONTINUOUS_PAN = True` |
| Safety line | dry loop from the pendant (DT12 7-8) gates the Pololu 2815; TRIP latch ANDed; phase-short brake | 1 kHz pulse train across the ring (555, 78L05, 4N35, 74HC123) as designed |
| Flywheels | 2 x 22xx ~880 KV outrunner, AM32 35 A ESCs, fixed 12 V rail, Ø34 or Ø36 TPU tyres (bench picks), two chronograph gates, trip latch | same; green laser optional |
| Feed | STS3215 #3 under the dial floor, dial on its horn; 45 deg steps; cone + fins; dither | + agitator cam only if the bench asks; hopper beam; fill flap for the dock |
| Pan, tilt | STS3215 x 2 as drawn | same |
| Electronics | base board (ATO fuse, 12 V PAN regulator); turret bay level 0 (2815, 12 V FLY regulator, 12 V AUX regulator, 3 x 1000 uF), level 1 (5 V regulator, trip latch, arm AND, brake driver), level 2 (Feather M4 CAN); cartridge board (6 brake FETs, LM393) | + pulse chain on level 1; + lights; the same Feather |
| Structure | every printed part as drawn; pan clamp printed PA6-CF; no bumper | aluminium clamp (SendCutSend), TPU bumper, infill cuts for mass, FEA rerun, drop test |
| Mount | the printed bench stand (TM pattern, DT12 harness, pendant, USB-CAN) | the 30 mm riser on the top deck; the lidar depression table; the radio stop in the loop |
| Laser | Class 2 red module in the printed mount | green if wanted |
| Firmware | states, servo bus x 3, homing with stops, DShot + eRPM, gates, CAN set as written | + ring telemetry (ring-drop counter), + lights |

### 2.2 What v0 proves (its acceptance, in one table)

| Claim | Pass |
|---|---|
| Feed | 100 balls per pose at 3/s, poses level / -25 deg / panning 60 deg/s: 0 doubles, <= 1 jam per 100 (a step that needs a reverse), <= 5 % empty steps after the dither; parked and shaken: 0 balls out |
| Wheels, ceiling | at 100 % throttle on the 12 V rail: no-load eRPM <= 1.10 x KV x 12 V; 20 balls all <= 66 fps on both chronographs |
| Wheels, set speed | 50 balls at the set speed: mean within +-2 fps of the set value, SD <= 1.5 fps |
| Aim | pan and tilt reach the commanded angles within 0.5 deg (one-sided approach); a 90 deg pan in <= 1.2 s; tilt never above 0 deg at any command |
| Hit | 20 shots each at paper targets at 2 and 4 m: 68 % radius <= 1.5 cm and <= 5 cm; 20 g hinged plates at 2 and 4 m: every plate down |
| Safety line | release: ESC rail off <= 25 ms, brake closed at +10 +-3 ms, wheels <= 5 % by +50 ms; 20 releases during feeding: no ball above 20 fps; the trip latches on a simulated 1.3 ms gate pair and only the button clears it |
| Temperature | after 100 balls in 2 min then 10 min at speed: ESCs <= 80 C, motors <= 70 C, flywheel regulator <= 60 C, servos <= 60 C |

### 2.3 From v0 to v1, in order

1. **Measure v0 as built**: mass by group (base, pan, tilt), the drop table, speed vs throttle, jam counts, servo step
   time. Feed the numbers back: launch and feed to the physics agent, fits and strengths to the CAD, timings to the
   firmware (docs/turret-bench-tests.md section 7).
2. **The ring** (`CONTINUOUS_PAN = True`): print the carrier and driver, fit the ROB-13065, add the pulse chain to
   level 1 and the two Micro-Fit 2 x 6 pairs, move the pan servo's TTL onto ring circuits 9/10 as in wiring 1.2; run the
   ring tests 6.1-6.8 of docs/turret-plan.md; homing on continuous rotation (already proven in simulation).
3. **Mass to <= 1.5 kg with balls**: from the measured groups; candidates in order of cost: the yoke and cradle at the
   infill the FEA allows, a lighter board bay, 2.0 mm cartridge walls where the FEA allows, a 24-ball hopper (the
   payload interface asks for 24 shots), or agree a new budget with the leg's sizing.
4. **Lidar and riser**: rerun `cad/turret_lidar.py` on the final geometry; the 30 mm riser print; the firmware's
   depression table and keep-outs loaded from CONFIG.
5. **Awesome and dock**: the NeoPixel ring and buzzer, the hopper-full beam, the fill flap and its spring, a green laser
   if the red one is hard to see on a floor.
6. **Strength for the robot**: the FEA rerun on the taller cage and the servo mount; the aluminium pan clamp
   (SendCutSend 6061-T6 0.125 in, exports/turret/pan_clamp.dxf) and the TPU bumper; the 30 cm drop test.
7. **The robot harness**: DT06-12SA plug with a 90 deg backshell, the radio stop in the safety loop, CAN to the J501's
   port (classic CAN at 1 Mbit/s; FD later), then manual firing on the Orin box (`cad/turret_box.py`, plan task T7).

## 3. Highly available components

Checked 2026-10-27 by three sourcing passes (public product pages or their Shopify product JSON; "snippet" means a
search-engine cache because the site blocks automated reads: Digi-Key, Mouser, Seeed, GetFPV, HobbyKing, Jameco).
The bench-kit pass (pendant, USB-CAN, PSU, chronograph, crimp tools, ammo) had not reported when this page was
written: those rows carry the catalogue's last-read price and are marked **TODO (next session)**.

### 3.1 The flywheel motor: the swap and the KV check

The Snail 2305 (875 rpm/V, 27.8 g, 4 x M3 on a 16/19 cross, the wheel on the bell) is backorder-only at aifitlab
($40, ships from China; RoboMaster sells it to competition teams only; the "$19.49 at RaceDayQuads" alternate in
catalog/alternates.json does not exist: RDQ has no Snail listing, and GetFPV's $18.99 "Snail 2305 Racing" is the 2,400
rpm/V racing winding). Note for the physics: aifitlab prints both 2,400 and 875 rpm/V on one page; 875 at 24 V is
the RoboMaster spec the design uses (21,000 rpm no-load).

The replacement must sit in the KV band this cage accepts on the fixed 12 V rail (appendix): **790-860 KV with Ø36,
860-910 KV with Ø34**; the 22xx base pattern (4 x M3 on 16 x 19 mm) is the one the cage plate already has.

| Motor | KV | Mass | Shaft and wheel mount | Tyre | Worst-corner ball (formula / map) | 52 fps throttle | Sellers, price, stock (2026-10-27) |
|---|---|---|---|---|---|---|---|
| **SunnySky X2216 880KV (V3 short shaft, SKU SS-XV3-X2216-S-880-V3): primary** | 880 | 67.5 g | 3.17 mm shaft; a bolt-on collet prop adapter and the X-mount are in the box; base pattern not printed on any seller page (the 22xx standard 16 x 19 is expected: confirm on the drawing before the plate is cut) | Ø34 (Ø36 only if the ceiling test allows) | 64.1 / 63.9 fps | 90 % | sunnyskyusa.com $24.99 (V3) and $18.99 (V2), available: true, https://sunnyskyusa.com/products/sunnysky-x2216 ; readymaderc.com $22.99 "In Stock", https://www.readymaderc.com/products/details/sunny-sky-x2216-brushless-motor-short-shaft-880kv ; amazon.com $26.99 FBA "only 3 left", https://www.amazon.com/dp/B0BR4VV3FG ; buddyrc.com $19.99 (long shaft) |
| **T-Motor MN2212 V2 920KV: backup part** | 920 | 54 g (65 with leads) | 4 mm shaft; 16 x 19 and 19 x 25 patterns per the RobotShop listing | Ø34 only | 67.0 / 66.8 fps: at the edge of the 66 fps bench limit; the bench ceiling test decides, and a failure means Ø34 at 11 V is not available (no fixed 11 V part): then only 880 KV motors | 86 % | robotshop.com $55.90 "In stock", https://www.robotshop.com/products/t-motor-navigator-mn2212-v2-920kv-brushless-motor ; store.tmotor.com $46.90 (China) |
| Generic 2212 920KV (HAWK'S WORK, threaded bell boss with cap nut, 16 and 19 mm holes printed on the listing) | 920 | 52 g | threaded bell-top boss + cap nut (the easiest hub: a Ø-clearance bore clamped under the cap) | Ø34 only | as the MN2212 | 86 % | amazon.com $12.99 FBA "only 13 left", https://www.amazon.com/dp/B0DNHRWRQ7 |
| Not chosen | | | | | | | EMAX MT2216 810KV: sold out at EMAX global, not listed by EMAX USA; Hobbywing XRotor 2216 880KV: no listing anywhere; T-Motor MT2216 900KV: not in T-Motor's store; A2212 930KV ($8-13, everywhere): 930 KV is over the band |

The check, at the worst corner (KV +5 %, rail +4 %, tyre grown): v_max = 0.945 x 1.05 KV x 12.48 V x pi x D / 60 +
0.5 fps. X2216 880 on Ø34: 0.945 x 924 x 12.48 x pi x 0.034 / 60 = 19.4 m/s = 63.6 + 0.5 = **64.1 fps** (the physics'
Ø34 map row scaled by 880/875: 63.9); on Ø36: 67.7 fps, over the 66 fps bench limit, so Ø34 is the first tyre and
Ø36 is fitted only if every ball of test 4.2 on Ø34 is under 60 fps. The 24 V fault on this motor: 2 x 12 V no-load,
~21,100 rpm, 128 fps on Ø34: the same fault, the same three guards (12 V-only rail with keyed CT pins, pre-feed eRPM
check, trip latch).

**The hub on this motor** (T2): the X2216's shaft is Ø3.17 and its collet prop adapter clamps on it and gives a
threaded stud with a washer and nut. The flywheel hub becomes a PA6-CF disc with a clearance bore for the stud,
clamped between the adapter's flange and the nut (as a propeller is); the motor hangs bell-down under the cage plate
with the shaft down, the hub below the bell. Its height is read from the motor's drawing (short-shaft version) and sets
the cage plate's rise. Runout is measured at assembly (test 1.5, <= 0.15 mm); a 2 mm pin through hub and adapter flange
is the fallback if the nut alone lets it slip. The HAWK'S WORK motor's threaded boss needs only a plain bore and its
cap nut.

### 3.2 The feed drive: a third STS3215 instead of the M2006 + C610

The dial needs 45 deg steps in <= 250 ms, a few hundredths of a N m, a hold when parked, and jam detection. The
STS3215 (2.94 N m stall, 45 rpm at 12 V, 12-bit absolute angle, load and position feedback on the serial bus) does all
of it, is already on pan and tilt (one part type, one bus, one driver), weighs 60 g against 107 g, and costs $22
against $95 + $39 (and the C610 is $250-320 where it can be had at all). The physics agent reruns the feed with the
servo's torque-speed line (T5); the expected rate is 3 balls/s clean, 4/s to be measured (appendix). Jam detection is
position-based first (not settled in 300 ms) with the load reading as the second signal.

### 3.3 Every bought part: primary and backup, with stock and links

| Part | Primary | Backup | Notes |
|---|---|---|---|
| Flywheel motor x 2 | SunnySky X2216 880KV V3, $24.99, sunnyskyusa.com, in stock (section 3.1) | the same part at readymaderc.com $22.99 "In Stock" or amazon.com $26.99 FBA; backup part T-Motor MN2212 V2 920KV, robotshop.com $55.90 in stock | 3 US sellers of the primary; the backup part is at the KV edge |
| ESC x 2 | Lumenier Razor Pro F4 45A 2-6S AM32, $31.49, racedayquads.com, available: true, https://www.racedayquads.com/products/lumenier-razor-pro-f4-45a-2-6s-am32-esc (getfpv.com $23.99, stock unconfirmed) | Repeat Robotics AM32 35A, $25.00 repeat-robotics.com and $24.99 palmbeachbots.com, both available: true (ships with Repeat's drive settings: reflash stock AM32 for bidirectional DShot); Holybro Tekko32 F4 45A AM32 $23.99 holybro.com (HK) | stock AM32 with a telemetry pad on the primary; 4-in-1 fallback Sequre Blueson A2 65A AM32 30x30, pyrodrone.com $48.99 |
| Servo x 3 (pan, tilt, feed) | Waveshare ST3215 12 V 30 kg-cm (SKU 22414), about $21.99, waveshare.com, no US warehouse (express 3-8 working days from China), https://www.waveshare.com/st3215-servo.htm | amazon.com B0CFY52HVV $30.99 "In Stock" (seller-fulfilled, Nov 10-18) and B0B6P9271Q $30.90 FBA ("only 1 left"); robotshop.com $31.71 backorder; openelab.com $27.99 pre-order; seeedstudio.com ST3215-C047 $22 "in stock" (snippet, unverified) | **the schedule risk: order on day one.** Add the Waveshare Bus Servo Adapter (A), $4.99 (amazon $10.55), to set IDs |
| Controller | Adafruit Feather M4 CAN Express 4759, $24.95, adafruit.com "In stock", https://www.adafruit.com/product/4759 | the same at Digi-Key 1528-4759-ND (~495, snippet) and Mouser 485-4759 (~430, snippet); backup part Adafruit Feather RP2040 CAN 5724, $19.95, in stock | three sellers |
| 12 V flywheel regulator (fixed) | Pololu D24V150F12 #2885, $79.95, "Rationed (Active)", 103 in stock 2026-10-27 + 95 within days, backorders allowed, https://www.pololu.com/product/2885 | Pololu D42V110F12 #5677, $69.95, 180 in stock (9-10 A at 24 V in: enough for the ramp and 3/s; the 3 ms recovery pulses ride the bank); a sealed fixed 24->12 V 15 A module, amazon.com B0BLC1C1RM $23.99 (15 left) as the last resort | Mean Well SD-100B/150B-12 have a trim pot (11-16 V): not allowed on this rail |
| 12 V PAN and 12 V AUX regulators x 2 | Pololu D36V50F12 #4095, $39.95, 343 in stock | Pololu D42V55F12 class (under 8 A, fine for a servo) | |
| 5 V regulator | Pololu D36V28F5 #3782, $23.95, 86 in stock | Pololu D24V22F5 class | |
| Safety switch | Pololu 2815, $8.49, 49 in stock + 100 within days | a 20 A logic-level P-channel high-side switch board (any) | |
| Slip ring (v1) | SparkFun ROB-13065, $27.95, "In stock" | Adafruit 1196, $19.95, 6 in stock; Digi-Key 1568-13065-ND (~50, snippet) | |
| Hall switch | Allegro A1120LUA-T, Digi-Key 620-1330-ND, $1.79, ~22k (snippet) | Honeywell SS443A, Mouser 785-SS443A $4.69 (~3.8k, snippet) | not at Mouser; avoid DRV5032FB (0 stock until 2027) |
| Index magnet | McMaster 5862K102 (3/16 x 1/8 in N42), $1.00 | K&J Magnetics D32 | |
| Laser (Class 2, < 1 mW) | Quarton VLM-650-03 LPT, 650 nm 1 mW Ø7.0 2.6-5 V, Digi-Key $18.31-25.03, in stock in every snapshot (371-2,275), https://www.digikey.com/en/products/detail/quarton-inc/VLM-650-03-LPT/1010454 | Quarton VLM-650-28 LPT (63, snippet); the green VLM-520-73 LPT is 0 stock, 4-week lead | the Ø7 bore of `laser_mount` is kept; the LPA variants are 2.5 mW Class IIIa: not allowed; Adafruit's lasers are all 5 mW |
| Pan bearing 6810-2RS | VXB Kit7458, $24.99, in stock | Bearings Direct $29.19 (1); McMaster 6656K229 (6810-2Z) $33.29 | |
| Tilt bearing MR126-2RS | Bearings Direct $4.56 (646) | VXB $7.77; McMaster 7804K112 $8.89 | |
| Circlip DIN 471-50, shoulder screw, thumbscrew, O-ring, screws, inserts, dowels, standoffs | McMaster (numbers in bom.json) | Belmetric (screws, washers), ruthex / 3DJake (inserts), Aspen (boxes) | McMaster delivers next day |
| DT12 set | TE DT04-12PA-L012 LCSC C6423585 $10.36 (Newark ~$15, Del City $12.84); DT06-12SA + W12S + sockets, Digi-Key $8.50; W12P $1.20; 12 x 0460-202-16141 $0.30 | Amphenol AT06-12SA kit at Chief Enterprises $10.49 (buy plug and receptacle from one family) | needs a size-16 crimper (tools) |
| Micro-Fit 3.0 housings and crimps | Heilind / Digi-Key / Mouser (numbers in 4.4) | any of the three | |
| XT60E-M (stand inlet) | Pyrodrone 10-pack $11.99 | Jameco $0.99 each | |
| Stand rocker, DC rated | Carling RA581-VB-B-0-V (8 A at 12 VDC, 10 A at 30 VDC), waytekwire.com | Switch Components RA1-1A-DC-2-B-1 (10 A 28 VDC), jameco.com | **TODO (next session)**: price and cutout; the E-Switch RCA1913 has no seller page |
| Stand fuse holder and fuse | Littelfuse 03455LS1H $7.16 and 0477005.MXP $1.00, Digi-Key | LCSC (holder, out of stock) | |
| Pendant (hold-to-run) | a momentary NO foot switch (Linemaster at Digi-Key, or a generic foot pedal) | AbleNet Specs IC, $75, in stock | **TODO (next session)**: confirm a specific foot switch's price and stock |
| USB-CAN | Fysetc UCAN, $8 (catalogue) | BIQU U2C $23.99; Innomaker USB2CAN (isolated version preferred) | **TODO (next session)**: stock |
| 24 V bench supply | Mean Well LRS-350-24 (14.6 A) | LRS-200-24 | **TODO (next session)**: price and stock |
| Ammo (300 balls) | Out of Darts Worker Cheetah 200-pack $29.99 + 100-pack $14.99 (in stock 2026-10-25) | Hasbro Rival refill, Adventure Force (Walmart) | **TODO (next session)**: the alternates' stock |
| Reference chronograph | Caldwell Ballistic Precision (optical) | Competition Electronics ProChrono DLX | **TODO (next session)**: price and stock |

### 3.4 Single-source watch list

The STS3215 (every US seller is a reseller of one Chinese maker; only Waveshare direct is reliable today), the Pololu
regulators and switch (all "rationed", all in stock today), the Feather (one maker, three sellers), the X2216 (one
maker, three US sellers). None is a blocker; all four go in the first order.

## 4. Build package

### 4.1 BOM with costs and stock (v0)

Unit prices as read on 2026-10-27 (section 3.3 and catalog/turret.json); McMaster hardware is bought in packs, so two
numbers are given. Stock: "in" = the seller's page said so on 2026-10-27; "backorder" or "TODO" as marked.

| Group | Line | Qty | Unit | Line | Source | Stock |
|---|---|---|---|---|---|---|
| Drives | SunnySky X2216 880KV V3 | 2 | $24.99 | $49.98 | sunnyskyusa.com | in |
| Drives | Lumenier Razor Pro F4 45A AM32 ESC | 2 | $31.49 | $62.98 | racedayquads.com | in |
| Drives | Feetech STS3215 / Waveshare ST3215 12 V | 3 | $21.99 | $65.97 | waveshare.com | ships from CN |
| Drives | Waveshare Bus Servo Adapter (A) | 1 | $4.99 | $4.99 | waveshare.com | - |
| | **Drives subtotal** | | | **$184** | | |
| Electronics | Feather M4 CAN Express 4759 | 1 | $24.95 | $24.95 | adafruit.com | in |
| Electronics | Pololu D24V150F12 (12 V FLY) | 1 | $79.95 | $79.95 | pololu.com | in (rationed) |
| Electronics | Pololu D36V50F12 (12 V PAN, 12 V AUX) | 2 | $39.95 | $79.90 | pololu.com | in |
| Electronics | Pololu D36V28F5 (5 V) | 1 | $23.95 | $23.95 | pololu.com | in |
| Electronics | Pololu 2815 switch | 1 | $8.49 | $8.49 | pololu.com | in |
| Electronics | Panasonic EEU-FR1V102 1000 uF 35 V | 3 | $1.20 | $3.60 | Mouser / Digi-Key | - |
| Electronics | LM393P, SN74HC123N, SN74HC74N, SN74HC08N, SN74HC14N, SN74AHCT125N, 2N7000, reset button, passives | 1 set | | $9 | Digi-Key | - |
| Electronics | IRLZ44NPBF | 6 | $1.60 | $9.60 | Mouser / Digi-Key | - |
| Electronics | TSAL4400 + TEFT4300 (gates) | 2 + 2 | | $1.70 | Mouser / Digi-Key | - |
| Electronics | A1120LUA-T + 5862K102 magnet | 1 + 1 | | $2.79 | Digi-Key, McMaster | in |
| Electronics | Quarton VLM-650-03 LPT laser | 1 | ~$22 | $22 | Digi-Key | in (snippet) |
| Electronics | Micro-Fit 3.0: 43025-0600, 43020-0600, 43025-1000, 43020-1000, 12 + 12 crimps 18 AWG, 30 + 30 crimps 24 AWG | 1 set | | $13.20 | Heilind / Digi-Key | - |
| Electronics | DT12: DT04-12PA-L012, W12P, 12 pins; DT06-12SA kit | 1 set | | $23.66 | LCSC / Digi-Key | in |
| Electronics | Fuses and holders: 3 x 3557-2, 2 x 0287010.PXCN, 2 x 0297015.WXNV, 3 x MF-R300, 1 x MF-R200 | 1 set | | $6.15 | Mouser / Digi-Key | - |
| Electronics | Wire: 2 x 18 AWG 25 ft (Remington), 26 AWG kit (Adafruit 2517) | 1 set | | $22.95 | Zoro, Adafruit | - |
| Electronics | 4 x 50 x 70 perfboard, 4 + 4 M3 standoffs | 1 set | | $10.64 | Tayda, McMaster | - |
| | **Electronics subtotal** | | | **$342** | | |
| Mechanical | 6810-2RS (VXB Kit7458) | 1 | $24.99 | $24.99 | vxb.com | in |
| Mechanical | MR126-2RS | 1 | $4.56 | $4.56 | bearingsdirect.com | in (646) |
| Mechanical | DIN 471-50 circlip 98541A167 | 1 | $3.10 | $3.10 | McMaster | next day |
| Mechanical | Shoulder screw 92981A101 | 1 | $2.82 | $2.82 | McMaster | next day |
| Mechanical | Thumbscrew 92581A250 + O-ring 9452K14 (pack) | 1 + 1 | | $9.64 | McMaster | next day |
| Mechanical | Screws (M2 x 8/10/20, M3 x 6/8/10/12/16/20 socket, M3 flat, M4 x 10, M5 x 16), nylon-tip set screws, inserts (M3, M3 short, M4, M5), washers, dowels Ø5 x 16 and Ø4 x 8 (numbers in bom.json; the Snail's drive pins and the flap pin/spring dropped) | 22 lines | | $36 used / ~$110 as packs | McMaster | next day |
| | **Mechanical subtotal** | | | **$81 used / ~$155 as packs** | | |
| Printed | PA6-CF ~500 g, PETG ~455 g (incl. the stand), TPU ~12 g | | | ~$56 | Bambu | - |
| | **Turret, all in** | | | **~$660 used / ~$740 as packs** | | |
| Bench | XT60E-M (10-pack), DC rocker, 03455LS1H + 2 x 0477005.MXP, 3.5 mm jack 35PM2A, SJ5003 feet, 70 x 50 perfboard | 1 set | | ~$37 | Pyrodrone, Waytek, Digi-Key, Tayda | rocker TODO |
| Bench | Pendant: momentary foot switch | 1 | ~$20 | ~$20 | Digi-Key / Amazon | TODO |
| Bench | USB-CAN (Fysetc UCAN or BIQU U2C) | 1 | $8-24 | ~$24 | fysetc.com / biqu | TODO |
| Bench | 24 V PSU Mean Well LRS-350-24 | 1 | ~$32 | ~$32 | Digi-Key / Mouser / Amazon | TODO |
| Bench | Balls: Worker Cheetah 200 + 100 | 300 | | $44.98 | outofdarts.com | in (10-25) |
| Bench | Reference chronograph (Caldwell Ballistic Precision class) | 1 | ~$100 | ~$100 | Amazon / MidwayUSA | TODO |
| | **Bench subtotal** | | | **~$258** | | |
| Tools (once) | Deutsch size-16 crimper (~$30), Micro-Fit crimper iCrimp IWS-3220M (~$30), AM32 USB linker / ESC programmer (~$15), external circlip pliers for 50 mm (~$12), heat-set insert tip (~$10), 5 mm hand reamer (~$10), dial indicator with a base (~$30) | | | ~$140 | Amazon / Digi-Key | TODO: confirm |
| | **v0 total** | | | **~$1,060 (turret ~$660-740, bench ~$260, tools ~$140)** | | |

Lead times: McMaster next day; Pololu, Adafruit, SparkFun, VXB, RDQ, SunnySky USA 2-5 days; the servos 1-3 weeks
from China (the critical path: order first); Digi-Key / Mouser 2-3 days. The first printer-days overlap the servo
wait.

### 4.2 Print plan (v0)

From `exports/turret/bench/print-plan.json` (hours are the planner's rough estimate for a P1S at 0.2 mm; PA6-CF structure
100 % solid on a hardened nozzle, PETG 2 mm walls 40 % gyroid, TPU 95A), with the v0 changes applied: the pan clamp
printed, the ring parts and the bumper not printed, the cartridge body taller for the new motors, both tyre sizes.

| Part | Material | Qty | Bed (mm) | g | h | Orientation and notes |
|---|---|---|---|---|---|---|
| pan_base | PA6-CF | 1 | 158 x 155 x 47 | 70 | 4.6 | on its foot; the only PA6-CF part at 40 % infill (`PARTIAL_FILL`) |
| pan_ring (turntable) | PA6-CF | 1 | 81 x 81 x 41 | 72 | 4.7 | upside down; gear teeth flat on the bed |
| pan_spacer | PA6-CF | 1 | 59 x 59 x 4 | 3 | 0.2 | wide end down |
| pan_pinion | PA6-CF | 1 | 29 x 29 x 17 | 8 | 0.5 | flat; 100 % |
| pan_clamp (v0: printed) | PA6-CF | 1 | 87 x 86 x 5 | 11 | 0.7 | flat; the SendCutSend DXF is the v1 part |
| tilt_yoke | PA6-CF | 1 | 152 x 91 x 48 | 101 | 6.6 | on its back: layers along the arms |
| cradle | PA6-CF | 1 | 182 x 126 x 59 | 76 | 5.0 | flat |
| cartridge_body | PA6-CF | 1 | 163 x 103 x ~70 (taller cage) | ~150 | ~10 | on its base; supports under the chute; the longest print: start it first |
| flywheel hub | PA6-CF | 2 | 28 x 28 x 15 | 7 each | 0.9 | flat; Ø5 bore printed at 4.9 and reamed |
| flywheel_tyre Ø34 and Ø36 | TPU 95A | 2 + 2 | 36 x 36 x 12 | 3 each | 1.0 | flat; bore 4 % under the rim (printed from `flywheel_tyre_print`) |
| dial | PETG | 1 | 91 x 91 x 44 | 21 | 0.8 | cone up; the horn recess underneath |
| hopper | PETG (translucent) | 1 | 111 x 101 x 65 | 20 | 0.8 | upright |
| hopper_lid | PETG | 1 | 102 x 102 x 13 | 8 | 0.3 | upside down; no flap in v0 (a plain port cover) |
| barrel | PETG | 1 | 35 x 30 x 100 | 13 | 0.5 | standing; last 15 mm blaze orange (filament change) |
| laser_mount | PETG | 1 | 20 x 18 x 24 | 3 | 0.1 | bore per the chosen module |
| board_bay | PETG | 1 | 58 x 57 x 46 | 12 | 0.5 | on its back |
| stand_box | PETG | 1 | 200 x 180 x 100 | 292 | 11.7 | upside down (on its top plate); cutouts per the parts bought |
| stand_bottom | PETG | 1 | 240 x 180 x 16 | 86 | 3.4 | flat |
| **Total** | PA6-CF ~500 g / 33 h; PETG ~455 g / 18 h; TPU ~12 g / 1 h | | | ~970 | ~52 | three days of printing on one P1S; the stand can print on a second machine |

Not printed in v0: ring_carrier (2.0 h), ring_driver (0.5 h), bumper_ring (1.4 h TPU), hopper_flap (0.1 h): v1.
Materials: Bambu PA6-CF (hardened nozzle, dried; the FEA allowables assume the humid, print-knocked-down values),
Bambu PETG Translucent for the hopper, PETG for the rest, TPU 95A HF for the tyres. Heat-set inserts go in with the
part still warm from the bed where possible; the fits table (section 5, test 1) is measured before assembly.

### 4.3 SendCutSend parts

v0: none. v1: `pan_clamp` in 6061-T6 aluminium, 0.125 in (3.175 mm), from `exports/turret/pan_clamp.dxf` (deburred, no
finish); SendCutSend gives an instant price on upload (`cad/turret.py` `SHEET`, `SHEET_PARTS`). Optional for the
robot, not the turret: the head plate under the TM pattern (docs/head-payload.md allows a SendCutSend plate).

### 4.4 Wiring (v0), at the level a person can build from

Three places, two moving joints; the pan joint is a cable loop in the Ø40 bore, the tilt joint a 40 mm lead loop beside
the -y pivot, the cartridge unplugs at two Micro-Fit connectors. Part numbers are the catalogue keys of
`exports/turret/bench/bom.json` and section 4.1.

```
 STAND (fixed)                 | TURRET BASE (fixed)              | LOOP (Ø40 bore,    | TURRET (pans)                       | CT   | CARTRIDGE (tilts, lifts off)
 XT60E-M <- 24 V PSU           | DT04-12PA receptacle (-y pad)    |  8 wires, +-170°)  | bay on the -y yoke arm:              |      | 2 x AM32 ESC
 DC rocker, 5 A fuse           | base board (+x): 10 A ATO fuse,  |                    |  L0  2815 switch, 12 V FLY reg,      |      | cartridge board: 6 x IRLZ44N
 3.5 mm jack <- pendant        |  D36V50F12 -> 12 V PAN           |                    |      12 V AUX reg, 3 x 1000 uF       |      |   brake, LM393 gate comparator
 USB-CAN <- laptop             | pan servo STS3215 (ID 1)         |                    |  L1  5 V reg, trip latch, arm AND,   |      | feed servo STS3215 (ID 3)
 terminal board (70 x 50)      | index magnet (housing top)       |                    |      brake driver, laser switch      |      | 2 chronograph gates
                               |                                  |                    |  L2  Feather M4 CAN, 74AHCT125 bus   |      |
                               |                                  |                    | tilt servo STS3215 (ID 2), +y arm    |      |
                               |                                  |                    | hall switch (under the turntable)    |      |
                               |                                  |                    | laser (cradle tab)                   |      |
```

**Connectors and pinouts** (unchanged from docs/turret-wiring.md where not stated):

| Connector | Part | Pins |
|---|---|---|
| TM: DT12 on the base, plug on the stand harness | DT04-12PA-L012 + W12P + 12 x 0460-202-16141; DT06-12SA + W12S + 12 x 0462-201-16141 | 1,2 +24 V (paralleled, 18 AWG each on the bench); 3,4 GND; 5,6 CAN_H/L (twisted); 7,8 SAFETY_A/B (the pendant's dry loop, twisted); 9-12 spare |
| CT power (cradle -> cartridge) | Micro-Fit 3.0 2 x 3: 43025-0600 receptacle on the cradle's harness, 43020-0600 plug on the pigtail; 43030-0038 / 43031-0021 crimps (18 AWG) | 1,2 +12 V FLY (the two ESCs); 3 +12 V FEED (the dial servo, through a 3 A polyfuse on L0; it is the same switched rail); 4,5,6 GND. 24 V never reaches this connector in v0 |
| CT signal | Micro-Fit 3.0 2 x 5: 43025-1000 / 43020-1000; 43030-0001 / 43031-0001 crimps (24 AWG) | 1 ESC_L (bidirectional DShot300); 2 ESC_R; 3 FEED_TTL (the servo bus); 4 spare; 5 BRAKE; 6 +5 V; 7 GATE_1; 8 GATE_2; 9 spare (BEAM in v1); 10 SIG_GND |
| Servo leads | the STS3215's own 3-pin (Molex 5264 type): V, TTL, GND | pan: 12 V PAN from the base board; tilt: 12 V AUX from L0; feed: 12 V FEED from CT power pin 3 |
| Laser | 2-pin JST-XH (or a soldered 24 AWG pair) | 5 V through a 2N7000 (gate from the Feather's LASER_EN) and GND |
| Hall | 3 x 26 AWG up the Ø2.8 hole beside its pocket to L2 | 5 V, GND, PAN_INDEX (open drain, 10 k pull-up to 3.3 V on L2) |

**Cables** (silicone-insulated stranded wire; lengths from the CAD, est):

| # | Run | Conductors | Gauge | Length | Strain relief |
|---|---|---|---|---|---|
| C1 | stand: XT60E-M -> rocker -> 5 A fuse -> terminal board -> DT06 plug pins 1-4 | 2 + 2 | 18 AWG | 250 mm | the DT06's backshell |
| C1b | stand: 3.5 mm jack -> DT06 pins 7-8; USB-CAN CAN_H/L -> pins 5-6 (120 R at the USB-CAN) | 2 pairs | 24 AWG twisted | 250 mm | same |
| C2 | base: DT04 pins 1-4 -> base board (ATO fuse, D36V50F12) -> 12 V PAN to the pan servo; pins 5-8 straight to the loop | 4 + 4 | 18 / 24 AWG | 120 mm | tie to the housing at 60 mm |
| C3 | **the loop**: base board -> up the Ø40 bore -> yoke slot -> bay L0/L2: +24 V, GND (18 AWG); CAN_H, CAN_L; SAFETY_A, SAFETY_B; PAN_TTL, SIG_GND (24 AWG, three twisted pairs) | 8 | 18 / 24 | 220 mm, of which 60 mm free in the bore | a tie at the base's cable window (z 5..23) and one at the yoke slot; a 50 mm sleeve of 2:1 heat-shrink over the free length so the +-170 deg twist spreads over it; no tie in between |
| C4 | bay L0 -> CT power receptacle on the cradle's -y rail (through the tilt loop) | 6 | 18 AWG | 220 mm incl. the 40 mm loop | tie at the yoke arm and at the cradle rail |
| C5 | bay L1/L2 -> CT signal receptacle | 10 | 24-26 AWG | 220 mm | same |
| C6 | cartridge pigtail: the two plugs -> ESCs (power 18 AWG, signal 26 AWG), cartridge board (BRAKE, +5 V, GATE_1/2, SIG_GND), feed servo lead | | | 150 mm | a tie at the cartridge base plate |
| C7 | bay L2 -> tilt servo on the +y arm | 3 | the servo's own + 200 mm extension | | ties on the bridge |
| C8 | bay L1 -> laser on the cradle tab | 2 | 24 AWG | 250 mm in the tilt loop | tie at the cradle tab |
| C9 | hall -> L2 | 3 | 26 AWG | 90 mm | the pocket's hole |

**Boards** (double-sided 50 x 70 mm perfboard, cut to the bay's 52 x 50 where it rides in the bay; M3 standoffs 12 and
14 mm):

- **Base board** (in the base, +x): the 10 A ATO fuse in a Keystone 3557-2 holder on +24 V in; D36V50F12 (24 -> 12 V
  PAN) with a 3 A polyfuse (MF-R300) on its output to the pan servo's lead; a 3-pin header for the pan servo (V, TTL, GND);
  pass-through screw terminals for CAN and SAFETY to the loop.
- **L0, power**: +24 V from the loop into the 3 x 1000 uF bank; Pololu 2815 (its ON pin from L1's ARM, its slide
  switch left ON); 15 A mini blade fuse (0297015.WXNV) -> flywheel regulator (fixed 12 V, section 3.3) -> 12 V FLY to CT
  power 1-2, and through MF-R300 to CT power 3 (12 V FEED); +24 V unswitched -> D36V50F12 -> 12 V AUX (MF-R300) -> the
  tilt servo; a 2-pin header for the AUX rail's return.
- **L1, logic**: +24 V unswitched -> D36V28F5 -> 5 V (MF-R200) -> L2, the hall, the gates, the laser switch. The arm
  chain (below). The trip latch (74HC123 one-shot 2.98 ms, 74HC74, recessed reset button). The brake driver (74HC14 +
  10 k / 1 uF). A 2N7000 for the laser.
- **L2, MCU**: Feather M4 CAN (USB pin on 5 V); 74AHCT125 + 4.7 k pull-up for the servo bus (D0/D1, direction on D4);
  the three servo branches (pan via the loop's PAN_TTL, tilt, feed via CT signal 3); the CAN pair with its 120 R; the
  hall input; the gate inputs (10 k to 3.3 V); ARM_IN and TRIP_IN.
- **Cartridge board** (on the cage plate beside the ESCs): 6 x IRLZ44N (3 per motor, drains to the phases, sources to a
  star, gates from BRAKE through 100 R with 10 k to source); LM393 with 50 mV hysteresis for the two TEFT4300
  phototransistors (4.7 k pull-ups), open-collector outputs to GATE_1/2; the two TSAL4400 emitters on 5 V through 100 R.

**The arm chain, v0 (no microcontroller in it)**:

```
 DT12 7 <- +5 V through 10 k (L1)                                  recessed RESET button -> 74HC74 /CLR (and a power-up RC)
 DT12 8 -> LOOP node: 10 k to GND, 100 nF  -> 74HC14 x2 -> LOOP_OK ----+
                                                                       |-- 74HC08: ARM = LOOP_OK AND /TRIP
 GATE_1 -> 74HC123 one-shot (2.98 ms) -> D of 74HC74; GATE_2 -> CLK;  |        |
           Q = TRIP (latched until RESET) -> /TRIP --------------------+        +--> Pololu 2815 ON pin  (> 1 V = on: 12 V FLY and 12 V FEED live)
                                                                                +--> Feather ARM_IN (read only)
                                                                                +--> 74HC14 -> 10 k / 1 uF -> 74HC14 x2 -> BRAKE (high 10 ms after ARM falls; low again before the 2815 re-powers)
```

Open loop, a cut loop wire, an unplugged pendant, a short of either wire to GND: LOOP_OK low -> ARM low -> the 2815
removes 12 V FLY and 12 V FEED -> 10 ms later BRAKE shorts the phases (tau 12 ms, 5 % speed at 45 ms). The MCU, the
pan and tilt servos, the laser and the gates stay powered. Known blind spot of a dry loop: a short of pin 7 to pin 8
inside a crushed harness reads as "held"; accepted on the bench (the harness is 250 mm on a table), removed in v1 by
the pulse train. The Feather also requires ARM_IN high and a CAN heartbeat <= 200 ms old before any spin command and
commands zero throttle without them; it cannot raise ARM.

**Fuses**: stand 5 A time-lag DC-rated (0477005.MXP); base 10 A ATO (0287010.PXCN); L0 15 A mini (0297015.WXNV) at the
flywheel regulator's input; polyfuses 3 A (MF-R300) on 12 V PAN, 12 V AUX and 12 V FEED, 2 A (MF-R200) on 5 V. All DC
rated. The regulators' own reverse-voltage protection and the 2815's cover a reversed supply.

**Servo bus**: one half-duplex TTL line at the Feetech default 1 Mbit/s (a cable loop needs no margin; v1 drops to
500 kbit/s over the ring), IDs 1 pan, 2 tilt, 3 feed, set with the Feetech/Waveshare tool before assembly and written on
each servo. The STS3215 holds position on a bus fault; the feed servo loses power with the rail on every release and
re-appears on the bus on the next arm (firmware task 6.T7).

**The flywheel rail's keying**: 12 V FLY and 12 V FEED are the only rails on CT power; the 2 x 3 and 2 x 5 Micro-Fits
cannot cross-mate; no 24 V is wired to the cartridge in v0. The regulator is a fixed-output part (no trim pot). The
bench rule stands: never put 24 V on the ESC side, not even for a test (section 5, test 4.6 simulates the fault
without a ball).

### 4.5 Assembly order (v0)

From `exports/turret/assembly/steps.json`, with the v0 changes (steps 6 and 10 change; `cad/turret_assembly.py` redraws
the pictures from the CAD once the parts are in):

1. **Pan base and its inserts** (base on its foot): 5 x M3 in the clamp ears, 4 x M3 in the base-board bosses, 4 x M4 in
   the DT pad. (No carrier bosses or bumper tabs in v0.)
2. **Pan servo (ID 1), pinion, DT12 receptacle**: the servo in its pocket, bus plugs down, 4 x M2 x 20 up through the
   foot; the pinion on the horn, 4 x M3 x 16 sunk; the DT04-12PA on the pad, 4 x M4 x 10, with its 12 pins and wedge on
   the base harness (C2).
3. **Base board and the index magnet**: the board on its bosses, 4 x M3 x 6; the 3/16 in magnet glued on the housing's
   top at pan 0.
4. **Pan bearing and the printed clamp**: the 6810-2RS pressed onto the Ø62 shoulder; the clamp over it, 5 x M3 x 10.
   Check: the outer race does not turn by hand; the inner race turns freely.
5. **Turntable, spacer, circlip**: 4 x M4 inserts in its top; the hall switch glued in its pocket underneath, leads up
   its hole; the journal down through the inner race with the gear in mesh with the pinion and the stop finger inside
   the post's sector; from below, the spacer and the DIN 471-50 circlip. Check: a full +-170 deg sweep by hand meets the
   stops and nothing else; backlash at the rim 0.2-0.4 mm.
6. **The loop harness** (replaces the ring step): C3 made up on the bench with its sleeve; fed up through the base's
   cable window, the Ø40 bore and the yoke's slot; tied at the window. Leave the top end free until step 7.
7. **Tilt yoke and the board bay**: the yoke on the turntable, 4 x M4 x 10 (heads 4 mm down in the bridge), the loop
   through its slot and tied there; 4 x M3 inserts in the -y arm; the bay on them, 4 x M3 x 8 flat heads; L0, L1, L2 on
   their standoffs, wired per 4.4; the loop's top end into L0/L2.
8. **Tilt servo (ID 2) and the cradle**: the servo into the +y arm's pocket, 4 x M2 x 10; the MR126 into the -y arm's
   seat; the cradle's hub on the horn (4 x M3 x 12), the ISO 7379 shoulder screw through the -y arm and the bearing into
   the cradle's M5 insert. Check the 0 and -25 deg stops by hand. The CT receptacles onto the cradle's -y rail (C4, C5).
9. **Laser**: the mount on the cradle's tab, 2 x M3 x 10; the module on its three nylon-tip set screws (boresight on
   the bench at 4 m, step 13).
10. **The cartridge, on the bench** (not on the turret): the feed servo (ID 3) up against the dial floor's underside,
    horn through the floor, 4 x M2 x 10 countersunk from above; the dial onto the horn (4 x M3 x 8 through the hub, from
    the top with the hopper off); set the servo's zero so a pocket is centred over the exit hole and write the count
    down. The two flywheel motors up under the cage plate, 4 x M3 x 6 each on the 16 x 19 cross, leads through their
    slots; each hub pressed on its M5 shaft against the bell's shoulder with the motor's washer and nylock nut
    (torque: snug plus a quarter turn; check runout with a dial indicator: <= 0.15 mm at the rim, or re-seat); the Ø34
    tyres stretched on first (the ceiling test decides). The two ESCs and the cartridge board on the plate; the brake
    FETs to the phase leads; the pigtail C6.
11. **Barrel, gates, hopper, lid**: the barrel into its socket (nylon-tip M3 set screw), the emitters and
    phototransistors in the gate bosses with their slits toward the bore; the hopper on the housing, 3 x M3 x 8; the
    lid (plain in v0).
12. **Cartridge onto the cradle**: down onto the two dowels, the thumbscrew up into its insert; the two CT plugs. Then
    the turret onto the stand: 2 x Ø5 dowels, 4 x M5 x 16, the DT06 plug.
13. **The stand**: inserts (4 x M5 in the top, 4 x M3 corners, 4 x M3 board bosses); the XT60E-M, rocker, fuse holder
    and jack in the front panel; the terminal board on its bosses; the USB-CAN at the back wall; the feet; C1 and C1b;
    the bottom plate. Clamp the stand to the bench through its tabs before any powered test.

## 5. Bench test sequence (v0), with pass/fail

In the order the turret is built. Every test writes its readings and pass/fail to a JSON under
`exports/turret/bench/` named after the test (the charter's checklist links them). Rig: the turret on its clamped
stand, the laptop on the USB-CAN running the host side of the CAN set, the pendant, a 24 V supply with its current limit
at 10 A, a two-channel scope, a 100:1 probe, a commercial optical chronograph 1 m out as the reference beside the
barrel's own gates, calipers, a 0.01 g scale, a spring scale to 100 N, a dial indicator, a thermocouple or IR
thermometer, 300 balls of one brand (plus 50 worn and 50 damp ones for test 5.3).

### 5.1 Parts and fits (nothing powered)

| # | Test | Accept |
|---|---|---|
| 1.1 | Printed sizes: bearing seat Ø65.0, journal Ø50.0, tyre bore 26.9, the CT dowel holes, the hub bore after reaming 5.00 +0.02 | a light press for the seat, a slip fit for the journal, the hub a light press on the M5 shaft's unthreaded shoulder |
| 1.2 | Inserts: pull an M3 and an M4 insert from a PA6-CF coupon | > 300 N (M3), > 500 N (M4) |
| 1.3 | Gear mesh: dial-indicator backlash at the turntable rim; a full sweep by hand | 0.2-0.4 mm; no binding; the stops at +-173.5 deg and nothing else |
| 1.4 | Tilt stops by hand | hard stop at 0 deg (level) and -25 deg; nothing else touches at any pan |
| 1.5 | Hub runout on the motor (dial indicator at the rim, motor turned by hand) | <= 0.15 mm; the tyre stays put after 50 turns by hand |
| 1.6 | Ball sizes: 50 balls on calipers and scale | Ø22.2-22.8, 1.6-1.9 g; outliers rejected from the hopper |

### 5.2 Strength (bench level)

| # | Test | Accept |
|---|---|---|
| 2.1 | 50 N up on the muzzle with the cradle on its 0 deg stop, 200 times | no crack, stop creep < 0.2 mm |
| 2.2 | Lift the turret by its yoke to 100 N (spring scale) | the bearing's outer race does not move under the printed clamp |
| 2.3 | Pan servo at 50 % torque against the stop (once), then held 10 s | no tooth marks; the stop finger whole |

### 5.3 Electrics without motors (ESC and servo rails unplugged at the CT)

| # | Test | Accept |
|---|---|---|
| 3.1 | Power-up: 5 V, 12 V AUX, 12 V PAN present; the Feather's heartbeat on CAN; the pan and tilt servos answer their IDs | all present within 2 s; no fuse blown |
| 3.2 | Safety line with a lamp in place of the ESCs on 12 V FLY: pendant held -> lamp on; released -> off; each loop wire cut or shorted to GND -> off; power-up with the pendant held -> off until released and re-held (the firmware's re-arm) | rail off <= 25 ms after release (scope on the 2815 output) |
| 3.3 | Trip latch with simulated gate pairs from a signal generator at 1.3, 2.2, 2.4, 2.6, 3.0 ms | latched at <= 2.4 ms, not at >= 2.6 ms; the latch holds until the button; ARM cannot rise while latched. Select the window's R here |
| 3.4 | Brake timing with a lamp: BRAKE rises 10 +-3 ms after ARM falls; falls before 12 V FLY returns on re-arm | scope |
| 3.5 | Homing: 50 power-ups at random pans within +-170 deg | every home within 7 s; the index centre's spread <= 0.1 deg; 10 sweeps to each stop and back within 0.2 deg |
| 3.6 | Feed servo alone (powered from the bench through CT 3): 200 steps of 45 deg under an empty hopper, then a full one | step settled (within 2 deg) in <= 250 ms; load reading repeatable; a deliberate jam (a pencil in a pocket) detected within 300 ms and reversed |

### 5.4 Flywheels (the ceiling before anything else)

| # | Test | Accept |
|---|---|---|
| 4.1 | **No-load eRPM at 100 % throttle on the 12 V rail**, no balls: both wheels | <= 1.10 x KV x 12 V (for 880 KV: <= 11,600 rpm, 7 pole pairs); the rail 12.0 +-0.5 V under load |
| 4.2 | **Ceiling with balls**: 20 balls at 100 % throttle, Ø34 tyres | every ball <= 66 fps on both chronographs. If any passes 66, this motor/tyre pair is rejected (go to Ø32 only with a cage change; otherwise a lower-KV motor). If all are <= 60 fps, repeat with Ø36 and keep Ø36 if still <= 66 |
| 4.3 | Speed at every throttle: 10 balls each at 60, 70, 80, 90, 100 % | a monotonic table, SD <= 1.5 fps at each point; this is the firmware's throttle-to-speed map |
| 4.4 | Set speed: 50 balls at the set rpm for 52 fps (Ø34) or 55 fps (Ø36) | mean within +-2 fps, SD <= 1.5 fps, none > 60 fps |
| 4.5 | Spin-up current with the 200 ms ramp (shunt in the +24 V lead) and burst recovery (8 balls at 3/s) | peak <= 3 A at 24 V ramped; every shot of the burst within +-3 fps of the set speed |
| 4.6 | **The 24 V fault, simulated without a ball**: (a) with the hopper empty and the muzzle into a catch box, feed the ESC rail from the bench supply at 24 V through the CT power plug ONLY with the dial servo unplugged and no balls anywhere on the bench: read the no-load eRPM (expect ~2 x the 12 V value, ~21,000 rpm) and confirm the firmware's pre-feed check goes SAFE and refuses to step; (b) the trip latch with a 1.3-1.6 ms simulated gate pair (test 3.3). Never a ball at 24 V | (a) SAFE within 100 ms of the first eRPM read above the limit; (b) latched |
| 4.7 | Release braking: wheels at speed, no ball; release; scope one phase through the 100:1 probe and read eRPM | ESC rail off <= 25 ms, short closed at +10 +-3 ms, speed <= 5 % by +50 ms; FETs < 60 C after 20 releases in 2 min |
| 4.8 | Tyre growth and creep: OD at the set speed by strobe or video; the tyres after 500 balls | growth <= +0.7 mm on the diameter; no creep on the rim |

### 5.5 Feeding

| # | Test | Accept |
|---|---|---|
| 5.1 | 100 balls per pose at 3/s: level; -25 deg; level while panning at 60 deg/s | 0 doubles; <= 1 jam per 100 (a step that needed a reverse); <= 5 % empty steps after the dither; log the jams and empties per 100 |
| 5.2 | The same at the firmware's maximum rate (4/s target; 3.5/s if the servo step is 250 ms) | 0 doubles |
| 5.3 | 50 worn and 50 damp balls, level, 3/s | 0 doubles; jams logged (an information test) |
| 5.4 | Parked safe: dial parked, rail off; the stand shaken by hand (~5 m/s^2) and knocked (~13 m/s^2) at tilt 0 and -25 | no ball reaches the wheels |
| 5.5 | The 5-ball hopper (the last balls of a magazine) at -25 deg | the lift-to-0 rule empties it; no ball left behind |

### 5.6 Accuracy and the game

| # | Test | Accept |
|---|---|---|
| 6.1 | Boresight the laser at 4 m | the dot within 2 cm of the group centre at 4 m |
| 6.2 | Groups: turret clamped, 20 shots at paper at 2 m and at 4 m, barrel level and at the tilt the firmware chooses for a 0.30 m target | 68 % radius <= 1.5 cm at 2 m, <= 5 cm at 4 m; record the group centres: this is the drop table |
| 6.3 | Aim repeatability: 20 moves to the same target from both pan sides | within 3 mrad when approaching in +pan |
| 6.4 | Fire while panning at 10 and 90 deg/s | the firmware holds fire above 10 deg/s |
| 6.5 | Knock-down: 20 g hinged plates at 2 and 4 m (sim/turret.py's plate), 5 balls each | every plate down |
| 6.6 | Temperature: 100 balls in 2 min then 10 min at speed; IR gun on ESCs, motors, the flywheel regulator, each servo | ESCs <= 80 C, motors <= 70 C, regulator <= 60 C, servos <= 60 C |
| 6.7 | Safety-line release during feeding: 20 releases at random points of 8-ball bursts | no ball above 20 fps after a release; where each resting ball ended, logged |

Numbers that differ from the models go back to their owners: launch and feed to the physics agent (sim/turret_*.py),
fits and strengths to cad/turret.py and cad/turret_studies.py, timings to docs/turret-firmware.md.

## 6. Ordered task list for the implementer

Estimates are agent working hours (an Opus session), not calendar days; printing, shipping and the user's hands are
noted separately. Branch: `turret/program` in `~/Code/gyropup-turret` (feat/ worktrees and PRs into dev per the repo's
workflow; never push main). **API** marks a task that changes `Turret(L)`, `.posed()`, `.meta` or `.bought` (names,
frames or envelopes), so the consumers listed at the top of this page must be rebuilt and checked.

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| T0 | **Baseline.** Build the worktree as it stands and keep the numbers: `cad/turret.py`, `cad/build_turret.py --no-render`, `cad/turret_motion.py`, the quick e2e. Record mass, print hours, margins | exports/turret/* | every build runs; `clashes()` empty; the numbers in this page's section 1 reproduced within 2 % | 1 h |
| T1 | **Record the v0 decisions and source the parts.** D42 in docs/decisions.yaml (v0 scope: cable loop, 22xx motor, servo feed, deferred items; D41 unchanged for the robot). Catalogue entries (catalog/SCHEMA.md shape) for the motor, its backup, the ESC backup, the servo sources, the regulator, the laser, the pendant, the USB-CAN, the PSU, the chronograph; sourcing.json risks updated (the DJI rows marked replaced); alternates.json second sources for every new part | docs/decisions.yaml, catalog/turret.json, catalog/sourcing.json, catalog/alternates.json | `cad/build_turret.py` writes a bom.json whose v0 lines all have a price, a buy link and an alternate; `no_listed_price` and `not_in_a_catalogue` empty | 3 h |
| T2 | **CAD: the flywheel motor swap.** Replace `SNAIL` by a `MOTOR` dict from the chosen motor's drawing (Ø, height from the mount face to the bell end, shaft Ø5 and its length, the 16 x 19 M3 cross, mass, KV, pole pairs); raise the cage plate so the wheel on the shaft sits on the ball path; the hub (`flywheel`) with a Ø5 bore, a Ø14 x 8 boss and the nut below the bell; the cavities and the lead slots; keep `wheel_c` 53.0 and the tyre set. **API**: `.bought['flywheel_motor_l/r']` envelopes and masses change (names kept) | cad/turret.py (`SNAIL`->`MOTOR`, `Geo` plate_z0/z1, `flywheel`, `cartridge_body`, `bought_parts`) | `clashes()` and `sweep()` clean at pans 0..350 x tilts 0/-25; the wheel's centre on z = 0 of the C frame within 0.1 mm; the hub's bore and boss drawn; print plan regenerated; `cad/turret_motion.py` rerun (tilt margins >= 5 with the heavier cage) | 6 h |
| T3 | **Physics: the launch on the new motor.** The motor constants (KV, phase resistance, no-load current, rotor inertia from the datasheet or est with the basis) into `sim/turret_launch.py` / `turret_launch3d.py`; rerun the ceiling map for Ø34 and Ø36 at 12 V with +5 % KV, +4 % rail, runout and growth; the set speeds per tyre; the 24 V fault row | sim/turret_launch.py, sim/turret_launch3d.py, docs/turret-physics.md section 4 | launch3d.json: the fastest swept ball at 100 % <= 66 fps for at least one tyre of the set; the set speed and throttle per tyre written for the firmware | 3 h (+ 15 min compute) |
| T4 | **CAD: the feed servo.** The STS3215 under the dial floor (its output face against the floor's underside, the horn through a Ø21 hole, 4 x M2 x 10 countersunk from above, 12 mm kept under its idler face for the plugs); the dial's hub on the horn (Ø20.2 x 3.2 recess, 4 x M3 on Ø14, from the top); remove the M2006 boss hole and the C610 window and cable-tie slots. **API**: `.bought['feed_motor']` becomes the servo envelope (name kept); `.bought['feed_esc']` is removed: update `cad/turret_assembly.py` step 10's `adds`, `cad/build_turret.py` `TURRET_BOUGHT`, `tools/part_images.py` if it lists it | cad/turret.py (`cartridge_body`, `dial`, `bought_parts`), cad/turret_assembly.py, cad/build_turret.py | clashes and sweep clean; the servo's bus plugs reachable from the housing's side window; the dial parks with a pocket over the hole at the servo's zero; `cad/turret_motion.py` rerun; the assembly picture for step 10 regenerated | 5 h |
| T5 | **Physics: the feed on the servo.** Replace the M2006 + C610 loop in `sim/turret_feed_dyn.py` by the STS3215 model already used in `sim/turret_dynamics.py` (torque-speed line 2.94 N m / 45 rpm, a 50 % torque cap, an est reflected inertia through 345:1 with its basis); rerun the stepping rates, the poses, the jolt and vibration cases | sim/turret_feed_dyn.py, docs/turret-physics.md section 3 | feed_dyn.json: the clean maximum step rate, the step time, 0 doubles at <= 3/s, parked-safe unchanged; finding 2 rewritten for the servo | 3 h (+ 15 min compute) |
| T6 | **CAD: the v0 pan joint and the stand.** Build with `CONTINUOUS_PAN = False`; a `LOOP` bundle envelope (Ø8, 'base' frame from the cable window to z 69, then 'pan' frame to the bay) in `bought_parts` in place of the ring's rotor leads; the printed pan clamp back in `MADE` for v0 (`pan_clamp` made, not bought; keep the DXF export for v1); the carrier bosses and bumper tabs off the base when the flag is False; the stand: the pendant's jack per the chosen pendant, the rocker's cutout per the chosen DC-rated part, the terminal board bosses measured against the board. **API**: `.bought` loses `slip_ring`, `slip_ring_rotor`, `ring_coupling`, `ring_leads_rotor` when the flag is False; `.meta` loses `ring_carrier`, `ring_driver`, `bumper_ring` and gains `pan_clamp` | cad/turret.py, cad/turret_stand.py, cad/build_turret.py, cad/turret_assembly.py (step 6 becomes the loop) | clashes and sweep clean at pans -170..170 with the stop post and finger (the bundle inside the bore by construction); turret.json shows `pan_range_deg` +-170 and the stop; motion margins within 5 % of T0; print-plan and bom regenerated | 4 h |
| T7 | **Firmware v0.** (a) The servo bus with three IDs; the feed as position steps of 45 deg (512 counts), speed/accel for <= 250 ms, settled = within 23 counts, jam = not settled in 300 ms or load above a threshold -> reverse 20 deg and retry, three in a row stops; the dither; the feed servo dropping off the bus on release and returning on arm. (b) Homing with hard stops: sweep +pan until the index or a stop (position not advancing for 200 ms), then -pan; `firmware/turret/homing.py` and its test with stops. (c) The set speed from the tyre and KV in CONFIG; the pre-feed check as eRPM <= 1.10 x KV x 12 V. (d) A host script that runs section 5's tests and writes their JSON | docs/turret-firmware.md, firmware/turret/*.py, a new firmware/turret/bench_host.py | test_homing.py passes 1,000 random starts within +-170 deg with stops (every home within 7 s, no wrong side of the stop); the message set unchanged; the bench script dry-runs against a simulated turret | 10 h |
| T8 | **Wiring v0 and the order sheets.** A "v0 bench build" section in docs/turret-wiring.md with section 4.4 of this page made exact from the CAD's lengths and the board layouts (which part on which perfboard, drawn as a grid); order sheets per vendor from bom.json (McMaster, Digi-Key or Mouser, Pololu, Adafruit, the motor shop, the servo seller, VXB, the ammo and the bench items) for the user to place | docs/turret-wiring.md, exports/turret/bench/orders/*.md | every conductor and connector named with a length; a reviewer agent can trace +24 V from the XT60 to each ESC phase without a question; the sheets total within 5 % of section 4.1 | 4 h |
| T9 | **Print.** Start in the print plan's order (cartridge first, stand on a second machine if there is one); measure every fit of test 1.1 as parts come off; re-print what misses | exports/turret/*.stl, exports/turret/bench/fits.json | fits.json complete; nothing re-printed twice for the same reason | 2 h agent, ~3 days printer |
| T10 | **Assemble** per section 4.5 as parts and orders arrive; sub-tests 1.2-1.6, 2.1-2.3 as each group completes; pictures per step regenerated from the CAD and photographed | exports/turret/assembly/, exports/turret/bench/*.json | steps.json updated; tests 1 and 2 green | 3 h agent, the user's hands |
| T11 | **Electrics without motors**: section 5.3 | exports/turret/bench/electrics.json, trip.json, homing_bench.json, feed_servo.json | 3.1-3.6 green; the trip window's R recorded | 2 h agent, 1 bench day |
| T12 | **Flywheels**: section 5.4 in order, 4.1 and 4.2 before any other powered flywheel test | exports/turret/bench/ceiling.json, speed_map.json, release.json | 4.1-4.8 green; the tyre chosen and written to CONFIG and to `TYRE_SET`'s note | 2 h agent, 1 bench day |
| T13 | **Feed and accuracy**: sections 5.5 and 5.6 | exports/turret/bench/feed.json, groups.json, game.json | green, or the failure named with its count; the drop table into the firmware | 2 h agent, 1-2 bench days |
| T14 | **v0 sign-off.** Tick the charter's checklist with links; the measured numbers back to the physics (launch, feed), the CAD (fits, strength) and the firmware (timings); the log entry | docs/turret-program.md, docs/turret-physics.md, docs/turret-firmware.md | every v0 claim in section 2.2 has a JSON; the open items for v1 listed with the number that demands each | 2 h |
| T15 | **v1: the ring.** `CONTINUOUS_PAN = True`; the pulse chain on L1; the Micro-Fit 2 x 6 pairs; the TTL over circuits 9/10; the ring tests 6.1-6.8 of docs/turret-plan.md. **API**: the v0 `pan_clamp`/`LOOP` changes reverse; the ring parts return | cad/turret.py, docs/turret-wiring.md, exports/turret/bench/ring_*.json | the acceptance numbers of plan 6.1-6.8 | 6 h agent, 1 bench day |
| T16 | **v1: mass, lidar, riser.** The measured groups vs 1.5 kg; infill and wall cuts where `cad/turret_studies.py` allows (SF >= 2 everyday, 1.2 in falls); `cad/turret_lidar.py` rerun; the riser print; CONFIG rows | cad/turret.py, cad/turret_studies.py, cad/turret_lidar.py, exports/turret/lidar/ | mass_g_with_balls <= 1500 in turret.json or a new budget agreed in docs/head-payload.md; the depression table regenerated | 6 h |
| T17 | **v1: awesome and dock, robot hardware.** Lights and buzzer, hopper beam, fill flap and spring, green laser if wanted; the aluminium clamp ordered and fitted, the bumper printed; the FEA rerun on the final geometry and the drop test; the DT06 robot harness with the radio stop; manual firing on the Orin box (`cad/turret_box.py`) | cad/turret.py, cad/turret_box.py, docs/turret-wiring.md | each item's acceptance from docs/turret-program.md's checklist; the box scene fires 24 balls on command with the pendant held | 10 h agent, 2 bench days |

Dependencies: T2 and T4 can run in parallel; T3 needs T2's motor choice (not its CAD); T5 needs T4; T6 after T2 and T4
(one sweep for all three); T7 is independent of the CAD; T8 after T1 and T6; T9 after T6; T10-T13 in order; T15-T17
after T14.

## 7. Risks

| Risk | Likelihood / effect | What to do |
|---|---|---|
| Real foam bridges over the dial: empty steps well above the sim's 24 %, or jams | high / the rate of fire and the game | The dither and the lift-to-0 rule first (free); test 5.1's counts decide an agitator in v1 (an eccentric cam ring under the pile is the physics' first candidate); never a faster step: 4/s is the clean limit |
| The ceiling margin is thin (2 fps on Ø36 with the Snail; with the new motor the tyre set absorbs KV but the real tyre, hub and rail decide) | medium / safety | Test 4.2 before any other firing; Ø34 first; the trip latch at 66 fps; the pre-feed RPM check; no 24 V on the ESC side, ever |
| The hub on a prop shaft runs out or the tyre creeps | medium / accuracy (0.30 mm runout doubles the yaw scatter) and a thrown tyre | Ream the bore, test 1.5 (<= 0.15 mm), the 4 % stretch, a drop of CA under the tyre if it walks; a hub with a D-flat if the nut alone slips |
| The STS3215 steps the dial slower than 250 ms under a full hopper, or its load reading misses a jam | medium / rate of fire 3/s instead of 4; a jam un-noticed | Test 3.6 early (it needs only the cartridge); position-based jam detection does not depend on the load reading; the step's speed and acceleration registers tuned on the bench |
| AM32's current limit does not limit (reported unreliable before the 2025 PID loop) | medium / a 12 A spin-up pulse | The 200 ms ramp is the primary limit; the shunt measurement of test 4.5 on the first spin-up; the 15 A fuse |
| Pololu regulators rationed; the D24V150F12 superseded | medium / schedule | Pololu's own recommendation is the D42V110Fx family (same size and pinout): the 12 V member is the primary in section 3.3; order with the first batch |
| The servo ships from China (Waveshare) and takes 2-3 weeks | medium / schedule | Order three on day one from the US-stock seller in section 3.3; the pan and tilt servos are needed last (step 2 and 8), the feed servo first (step 10) |
| The dry-loop safety line's blind spot (a short across the loop reads as held) | low on a bench / severe on a robot | Accepted for v0 with a 250 mm harness on the table; v1's pulse train removes it; the robot's radio stop cuts the head rail upstream as well |
| Printed pinion at servo stall (SF 1.26-1.44) | low / a tooth | The 50 % torque cap in BOOT; test 2.3 once |
| PA6-CF moisture and layer strength | low / fits and cracks | Dry the spool; the fits table; the allowables already assume humid, print-knocked-down values |
| The Feather M4 CAN is one product from one maker | low / schedule | Adafruit, Digi-Key and Mouser all stock it; the Feather RP2040 CAN (same pinout family) is the backup; the pin map fits both |
| The taller cage changes the tilt group's CoM | low / the barrel must still rise to 0 deg unpowered | T2's `cad/turret_motion.py` rerun: the CoM stays behind the tilt axis at every hopper fill (gravity torque negative in motion.json) |

## Appendix: the numbers used

- **Ceiling formula** (checked against the physics' map): v_ball,max = 0.945 x (1.05 KV) x (1.04 x 12 V) x pi x D / 60
  + 0.5 fps for the tyre's growth, with D the nominal tyre diameter in m and 0.945 the launch model's ball-to-surface
  speed ratio. Snail 875 KV, Ø36: 67.5 fps (the map: 66.8-68.0). 880 KV, Ø34: 64.1 fps (the map scaled: 63.9). 810 KV,
  Ø36: 62.3 fps. 920 KV, Ø34: 67.0 fps (over the 66 fps bench limit: not accepted).
- **Set speed**: rpm = (v_set / 0.945) x 60 / (pi x D). 52 fps on Ø34 is 9,500 rpm (90 % of 880 KV x 12 V); 55 fps on Ø34
  is 10,040 rpm (95 %: too little headroom for the recovery loop; the physics' usable band is 50-57 fps on this cage).
  eRPM = rpm x 7 for a 12N14P motor.
- **The KV band this cage accepts on 12 V**: 790-860 KV with Ø36 (25 % crush), 860-910 KV with Ø34 (16.2 % crush).
  Below 790 the set speed needs > 92 % throttle; above 910 the Ø34 ceiling passes 66 fps and Ø32 would crush only 7.5 %
  (the physics wants >= 18 %). A fixed 9 V rail (Pololu D24V150F9, rationed like the 12 V) would open 1,050-1,150 KV
  motors on Ø36, at the cost of a 2S-capable ESC; not used unless no 790-910 KV motor can be bought.
- **Servo-stepped dial**: STS3215 at 12 V, 45 rpm no load = 270 deg/s; a 45 deg step is 167 ms at full speed plus
  ramps, ~200-250 ms settled (est, test 3.6 measures); plus the ball's 130 ms drop and chute: ~350 ms command to muzzle,
  3 balls/s clean (the kids' rate), 4/s to be measured.
- **Loop twist**: +-170 deg over 60 mm of free length on a Ø8 bundle of eight silicone-insulated wires; the sleeve
  spreads the twist; tie points only at the ends.
