# Turret prototype plan: v0 on the bench, then v1 on the robot

Written 2026-10-27 by the planner (Fable 5.1) for the turret program agent (Opus 5.5), from a read of the turret as
merged on main (7ef69a2: the slip ring and continuous pan built and swept clean, the physics end to end, the parts rule
applied, the load paths strengthened by the FEA, the clearance check, the assembly order; outputs rebuilt in 641ee22).
The user's words: "Fable 5.1 should review our turret and figure out how we drive that towards a first physical
prototype, then opus 5.5 should work the plan, make sure we pick highly available components and keep the design simple
etc." and "full steam ahead, finish our plans and get this ready for first prototype manufacturing."

This page is the review and the plan. Section 6 is the ordered task list; every task names its files, its acceptance
check and an estimate, and flags the ones that change the Turret API (`cad/turret.py` `Turret(L)`, `.posed()`, `.meta`,
`.bought`), because `cad/build.py` (the robot model), `sim/robot_v2.py`, `sim/turret_e2e.py`, `cad/build_turret_box.py`,
`cad/turret_assembly.py`, `cad/turret_motion.py`, `cad/turret_lidar.py`, `cad/turret_studies.py` and
`tools/part_images.py` all build on it.

Hard rules stand and are not relaxed anywhere below: the barrel never points above horizontal; muzzle speed at most
70 fps (21.3 m/s), held physically by a fixed 12 V flywheel rail (motor KV x rail x tyre diameter inside the cap);
nothing spins or feeds unless the safety line is held. Parts rule D40: off the shelf with a listed price and a buy
link, printed (PA6-CF, PETG, TPU on the P1S's 256 mm bed), or ordered online at an instant price. No quotes.

Prices and stock in section 3 were read on 2026-10-27 from public pages; each row says where and how (a page read, its
Shopify product JSON, or a search snippet where the seller blocks automated reads). Nothing was ordered and no vendor
was contacted.

## 0. In one paragraph

**v0** is the turret exactly as drawn on main, built on its printed bench stand, with three part substitutions forced
by availability and nothing else changed in the design: (1) the delisted DJI Snail 2305 flywheel motors become two
SunnySky X2216 880 KV outrunners (three US sellers in stock) on the same fixed 12 V rail, with the tyre set (Ø34 first,
Ø36 only if the ceiling test allows) absorbing the 0.6 % KV difference and a new hub on the motor's shaft; (2) the
out-of-stock DJI M2006 + C610 feed drive becomes a third Feetech STS3215, the servo already on pan and tilt, stepping
the dial 45 deg on the same serial bus, which removes the only CAN node on the cartridge, the 24 V dial rail and a
$250 ESC; (3) the green Quarton laser (0 stock, 4-week lead) becomes the red Quarton VLM-650-03 LPT, the same Ø7
Class 2 module in the same mount. Four things in the CAD are simply not fitted on the bench (the TPU bumper, the fill
flap and its spring, the lights and buzzer, the hopper-full beam). The slip ring, the continuous pan, the pulse-train
safety line, the aluminium clamp, the two chronograph gates with the hardware trip, the phase-short brake, the hard tilt
stops and the ball + 2.0 bore all stay: they are built, swept and documented, and the ring is $27.95 in stock. The
+-170 deg cable loop (`CONTINUOUS_PAN = False`) stays the documented fallback if the ring fails its bench tests. v0 proves
on the bench: feed -> wheels -> every ball at or under 66 fps at 100 % throttle -> aim -> plates down at 2 and 4 m, with
the pendant held. **v1** cuts the mass to 1.5 kg, reruns the FEA on the final geometry and drop-tests, adds the lidar
depression table and the 30 mm riser, the lights, beam and flap, and goes on the robot's DT12 harness with the radio
stop.

## 1. Review of the turret as it stands (main 7ef69a2)

### 1.1 What is right: keep it

| Item | Why it is right | Evidence |
|---|---|---|
| The physics chain and its 14 findings | Ball, feed, launch, bore, flight, target, dynamics and power are modelled end to end on the CAD at run time, and the findings are in the CAD (ball + 2.0 bore after the nip, 60 mm gates with 1 mm slits, 0.5 mm wider wheel cavities, the tyre printed 4 % under the rim, Ø38 dropped, the dial's cone and fins) | docs/turret-physics.md sections 0-12; exports/turret/{launch,feed,flight,target,e2e} |
| The speed ceiling is physical | ESCs fed only by a fixed-output 12 V regulator; a 24 V fault is 79-128 fps, so the 12 V-only rule, keyed CT pins and the pre-feed RPM check are the safety items; the chronograph trip is the backstop | physics sections 4 and 10; wiring 1.4 and 3.2 |
| Release braking | Phase-short brake, tau 12 ms, 5 % speed at 45 ms, before a dropped ball (96 ms) reaches the nip; a stray ball leaves at 7.7 fps on the next ramped arm | physics section 5 |
| The pan joint | The ROB-13065 ring on a printed carrier, driven through a silicone tube; swept clean at pans 0-350 x tilts 0/-25 with the Ø7.5 lead bundle; the safety line as a 1 kHz pulse train so a bouncing contact fails safe; homing on the index proven on 1,000 random starts | cad/turret.py `ring_carrier`, `ring_driver`; exports/turret/clash-sweep.json; wiring 3.1; firmware/turret/test_homing.py |
| The cartridge concept | The whole feed-and-launch group lifts off the cradle on two dowels and a thumbscrew with two keyed Micro-Fit plugs; everything that wears is on it | cad/turret.py `cartridge_body`, `ct_points`; docs/turret-assembly.md step 12 |
| The hopper, dial and baffle | 30 balls fit (lid at 100 mm); the parked dial never lets a ball out, powered or not, through a 13.5 m/s^2 jolt; no double at <= 4 steps/s; nothing ever stuck in the chute | physics section 3 |
| Hard tilt stops, CoM behind the tilt axis | Unpowered the barrel rises to the 0 deg stop; the tilting group's centre sits 8-11 mm behind the axis empty to full; tilt hold margin 43 | exports/turret/motion.json |
| The load paths after the FEA | Yoke SF 2.53 / 2.35 / 1.99 in the 30 g falls and 1.72 in the everyday push at the muzzle; turntable 3.59; pan base 7.2 / 1.61 (falls), 2.52 / 1.26 (servo cap / stall); the aluminium clamp 3.1 (the printed one was 0.18 in the lift case); pinion 2.7 / 1.35; teeth 3.2 / 1.6 | the program log 2026-10-27 (later); exports/turret/fea/*.png |
| The clearance check is general | `cad/turret_lidar.py` takes obstacles as cylinders and boxes and the ball path at the slowest stray-ball speed: over the lidar on the 30 mm riser the depression is limited only within pan +-26 deg (to -16 deg); on the Orin box nothing limits it and firing is kept out within 60 deg of straight back | exports/turret/lidar/lidar.json, box.json |
| The bench stand and the TM interface | The stand carries the real TM pattern and the DT12 harness, so the bench turret is the robot turret; the pendant is wired through the pins the radio stop will use; the switch, fuse holder and jack cutouts were redrawn to the makers' panel drawings | cad/turret_stand.py, wiring 1.1 |
| The parts discipline | Every bought line has a catalogue key, a part number, a price and a picture; alternates per part; `no_listed_price` is down to five lines | exports/turret/bench/bom.json, catalog/alternates.json |
| The assembly order, the bench tests, the wiring and firmware plans | Twelve steps with a picture each from the CAD; the tests in build order with their numbers; every connector and conductor named; states, pin map, CAN set, the aiming rules from the physics | docs/turret-assembly.md, docs/turret-bench-tests.md, docs/turret-wiring.md, docs/turret-firmware.md |

### 1.2 Over-built or risky for a first prototype: what v0 changes, simplifies or defers

| Item | What it costs now | v0 decision | Comes back |
|---|---|---|---|
| **DJI parts** (Snail 2305, M2006 + C610) | Delisted / out of stock; the C610 is $250-320 elsewhere; the M2006 is 1 N m for a dial that needs ~0.05; the C610 adds a CAN node, DJI's protocol, a 24 V rail and a 10 A fuse to the cartridge | **Swap** (section 3.1, 3.2): SunnySky X2216 880KV on the standard 16 x 19 M3 base; a third STS3215 for the dial on the servo bus | never |
| **Continuous pan vs a cable loop** (D1) | The ring brings the pulse chain (555, 78L05, 4N35, 74HC123), two 12-way Micro-Fits, the TTL over a ring and the 2 A-per-circuit budget. Weighed against a loop: the loop would be new CAD (the `CONTINUOUS_PAN = False` build has not been swept since the ring went in), a new harness route and twist check, a stop-aware homing and a second wiring variant, for a joint the robot does not want | **Keep the ring.** It is built, swept, documented and $27.95 in stock; the pulse chain is four DIP parts whose failure mode is "will not arm"; the bench tests 6.1-6.8 of docs/turret-plan.md retire the v1 ring risk now. The loop stays the fallback if 6.1 or 6.2 fail (section 2.4) | - |
| **The pan clamp** | The printed clamp failed the lift case at SF 0.18; the SendCutSend 6061-T6 one is 3.1 | Order it as drawn (exports/turret/pan_clamp.dxf, instant price): no CAD change | - |
| **The chronograph trip latch** (D10) | Five logic parts and a selection test; the physics shows it acts only after one fast ball has left | **Keep** (cheap; it catches a wrong regulator or tyre; the bench tests it with simulated gate pairs in ten minutes) | - |
| **The hopper agitator** | The feed sim shows 24 % empty steps with the M2006's 100 ms step; rigid spheres under-predict foam bridging; the cone and four fins are already in the dial print | **Measure first**: cone + fins + the firmware dither; decide a cam ring or sloped floor from the 300-ball counts, not from the sim | v1 if the bench shows > 5 % empty steps after the dither |
| **Lights, buzzer, hopper-full beam, fill flap and spring, TPU bumper** | Parts, wiring and firmware that prove nothing on the bench; the bumper is for kids and the lidar | Not fitted on the bench (no CAD change: `bumper_ring` and `hopper_flap` are simply not printed; the NeoPixel, beam and spring lines drop from the v0 order) | v1 |
| **The laser** (Quarton VLM-520-73 LPT, $41.82) | 0 stock at Digi-Key, 4-week lead | The red VLM-650-03 LPT (same Ø7, Class 2, in stock, ~$22); `LASER['L']` 21 mm instead of 26.1 | green in v1 if a red dot is hard to see |
| **Mass 1.556 kg with balls, 1.502 empty** (budget 1.5) | 56 g over; the X2216s add ~80 g and the servo feed takes ~47 g off: ~1.59 kg in v0 | A bench problem only in that it is measured | v1 cuts ~90 g |
| **The FEA is unfinished** | The cartridge (fall, recoil) and the dial (jam) were not run; the cradle is SF 1.0 / 0.83 / 0.81 across the layers in the falls (1.7-2.1 along) | Rerun after the motor and feed changes (T9); the falls are the robot's case, not the bench's | v1 fixes the cradle if the rerun holds it under 1.2 |
| **The three-level board stack of perfboards** | Reasonable; the C610's rail, fuse and CAN pair leave level 0 and the CT connector | Keep the bay as drawn; fewer parts on level 0 and the cartridge board | - |
| **The $75 AbleNet pendant** | A momentary foot switch does the same job; the only in-stock industrial one found (Linemaster 491-SC3) is $101 | Keep the AbleNet Specs IC ($75, in stock) as the primary; a generic momentary foot pedal (Amazon, ~$15) as the backup, to be confirmed on order day | - |
| **The stand's rocker switch** | The chosen E-Switch RCA1913 has no seller page; the Carling RA581 is 0 stock (106 days) | Switch Components RA1-1A-DC-2-B-1 (10 A at 28 VDC, Ø20.2 round snap-in): Jameco $1.54 (10+), TME $1.99 (231 in stock); the stand's cutout becomes a Ø20.2 hole | - |
| **Fire-while-panning, pan backlash, tilt lash** | Aim movers of 7-15 mrad | Firmware rules already written (settle 0.25 s, one-sided approach); nothing to build | - |

### 1.3 What the bench must settle first (the models' open ends)

1. The real empty-step and jam rate of a foam pile over the cone and fins (the sim's 76 % delivery is a lower bound on
   the problem, not the answer).
2. The ceiling: the fastest ball at 100 % throttle on the real rail, real tyre and real motor (the model leaves 2 fps on
   Ø36 with the Snail; with the X2216 the tyre set is chosen on the bench, section 3.1).
3. Tyre runout and creep on the printed hub (the new hub rides the motor's shaft and collet adapter, not the Snail's
   pinned seat).
4. Whether the STS3215 steps the dial in <= 250 ms (3 balls/s) under a full hopper, and whether its load reading
   detects a jam.
5. The ring under flywheel current: contact noise, CAN error counters, the pulse train's fault tests.
6. The drop table at 2 and 4 m with the real topspin (the physics says it cannot be computed from speed alone).

## 2. Prototype v0, and the road to v1

### 2.1 v0 scope by subsystem

| Subsystem | v0 (bench) | v1 (robot-ready) |
|---|---|---|
| Pan joint | as drawn: ROB-13065 ring on its carrier, tube coupling, continuous pan, hall index at pan 0 | same; the ring's life test in the background |
| Safety line | as drawn: the pendant's dry loop into the base's 1 kHz oscillator, the pulse pair across the ring, the opto and retriggerable monostable on level 1, TRIP ANDed, the phase-short brake | same, with the radio stop in place of the pendant |
| Flywheels | 2 x SunnySky X2216 880KV, 2 x AM32 35 A ESCs, fixed 12 V rail, Ø34 (then Ø36 if allowed) TPU tyres, two chronograph gates, trip latch | same |
| Feed | STS3215 #3 under the dial floor, dial on its horn; 45 deg steps; cone + fins; dither; 12 V FEED from the switched rail | + agitator cam only if the bench asks; hopper beam; fill flap for the dock |
| Pan, tilt | STS3215 x 2 as drawn | same |
| Electronics | base board (ATO fuse, 12 V PAN regulator, 555 + 78L05); level 0 (2815, 12 V FLY regulator, 12 V AUX regulator, 3 x 1000 uF); level 1 (5 V regulator, opto + monostable, trip latch, arm AND, brake driver); level 2 (Feather M4 CAN, bus buffer, the ring's rotor plug); cartridge board (6 brake FETs, LM393) | + lights; the same Feather |
| Structure | every printed part as drawn; the SendCutSend clamp; no bumper fitted | bumper, infill cuts for mass, FEA rerun, drop test |
| Mount | the printed bench stand (TM pattern, DT12 harness, pendant, USB-CAN) | the 30 mm riser on the top deck; the lidar depression table; the robot harness |
| Laser | Quarton VLM-650-03 LPT (red, Class 2) in the printed mount | green if wanted |
| Firmware | states, servo bus x 3, homing on the index, DShot + eRPM, gates, CAN set as written | + lights, + the robot's CONFIG rows |

### 2.2 What v0 proves (its acceptance, in one table)

| Claim | Pass |
|---|---|
| Feed | 100 balls per pose at 3/s, poses level / -25 deg / panning 60 deg/s: 0 doubles, <= 1 jam per 100 (a step that needs a reverse), <= 5 % empty steps after the dither; parked and shaken: 0 balls out |
| Wheels, ceiling | at 100 % throttle on the 12 V rail: no-load eRPM <= 1.10 x KV x 12 V; 20 balls all <= 66 fps on both chronographs |
| Wheels, set speed | 50 balls at the set speed: mean within +-2 fps of the set value, SD <= 1.5 fps |
| Aim | pan and tilt reach the commanded angles within 0.5 deg (one-sided approach); a 90 deg pan in <= 1.2 s; tilt never above 0 deg at any command; homing within 7 s at 50 random power-ups |
| Hit | 20 shots each at paper targets at 2 and 4 m: 68 % radius <= 1.5 cm and <= 5 cm; 20 g hinged plates at 2 and 4 m: every plate down |
| Safety line and ring | only the genuine 1 kHz train arms; every fault (open, short to GND, short to +24 V, DC, 300 Hz, 3 kHz, 50 Hz hum) disarms within 25 ms; release: ESC rail off <= 25 ms, brake closed at +10 +-3 ms, wheels <= 5 % by +50 ms; 20 releases during feeding: no ball above 20 fps; the trip latches on a simulated 1.3 ms gate pair and only the button clears it; the ring: <= 60 mOhm per paralleled pair, no dropout > 100 us at 15 rpm with 5 A, 0 bus-off in 1 h of 1,000 frames/s |
| Temperature | after 100 balls in 2 min then 10 min at speed: ESCs <= 80 C, motors <= 70 C, flywheel regulator <= 60 C, servos <= 60 C, ring body <= 20 K over ambient |

### 2.3 From v0 to v1, in order

1. **Measure v0 as built**: mass by group (base, pan, tilt), the drop table, speed vs throttle, jam counts, servo step
   time, the ring's resistance and error counts. Feed the numbers back: launch and feed to the physics agent, fits and
   strengths to the CAD, timings to the firmware (docs/turret-bench-tests.md section 7).
2. **Mass to <= 1.5 kg with balls**: from the measured groups; candidates in order of cost: the yoke and cradle at the
   infill the FEA allows, a lighter board bay, 2.0 mm cartridge walls where the FEA allows, a 24-ball hopper (the
   payload interface asks for 24 shots), or agree a new budget with the leg's sizing.
3. **Strength for the robot**: the FEA rerun on the final geometry (the taller cage, the servo mount, the cradle's
   across-layer cases), the 30 cm drop test, the bumper fitted.
4. **Lidar and riser**: rerun `cad/turret_lidar.py` on the final geometry; the riser print; the firmware's depression
   table and keep-outs loaded from CONFIG.
5. **Awesome and dock**: the NeoPixel ring and buzzer, the hopper-full beam, the fill flap and its spring, a green laser
   if the red one is hard to see on a floor.
6. **The robot harness**: DT06-12SA plug with a 90 deg backshell, the radio stop in the safety loop, CAN to the J501's
   port (classic CAN at 1 Mbit/s; FD later), then manual firing on the Orin box (`cad/turret_box.py`, plan task T7).
7. **The ring's life test** (docs/turret-plan.md 6.4) in the background on a gearmotor-driven stand.

### 2.4 The fallback if the ring fails its bench tests

If 6.1 (contact noise) or 6.2 (CAN errors) fail on the ROB-13065 and the Adafruit 1196 does no better: build with
`CONTINUOUS_PAN = False` (the stop post and finger return, +-170 deg), route the harness as a Ø8 bundle up the Ø40 bore
with a 60 mm free length sleeved for the twist, make the safety line a dry loop into the 2815's ON pin through a
Schmitt stage, and home by sweeping to the index with a reversal at a stop. It is 2-3 days of CAD, wiring and firmware;
it is written here so nobody has to design it in a hurry.

## 3. Highly available components

Checked 2026-10-27. "page" = the seller's page or its Shopify product JSON was read; "snippet" = a search-engine cache,
because the seller blocks automated reads (Digi-Key, Mouser, Seeed, GetFPV, HobbyKing, Jameco).

### 3.1 The flywheel motor: the swap and the KV check

The Snail 2305 (875 rpm/V, 27.8 g, 4 x M3 on a 16/19 cross, the wheel on the bell) is backorder-only at aifitlab
($40, ships from China; RoboMaster sells it to competition teams only). The "$19.49 at RaceDayQuads" alternate in
catalog/alternates.json does not exist (RDQ has no Snail listing); GetFPV's $18.99 "Snail 2305 Racing" is the 2,400
rpm/V racing winding. Note for the physics: aifitlab prints both 2,400 and 875 rpm/V on one page; 875 at 24 V is the
RoboMaster spec the design uses (21,000 rpm no-load).

The replacement must sit in the KV band this cage accepts on the fixed 12 V rail (appendix): **790-860 KV with Ø36,
860-910 KV with Ø34**; the 22xx base pattern (4 x M3 on 16 x 19 mm) is the one the cage plate already has.

| Motor | KV | Mass | Shaft and wheel mount | Tyre | Worst-corner ball (formula / map) | 52 fps throttle | Sellers, price, stock |
|---|---|---|---|---|---|---|---|
| **SunnySky X2216 880KV V3, short shaft (SKU SS-XV3-X2216-S-880-V3): primary** | 880 | 67.5 g | 3.17 mm stainless shaft; a bolt-on collet prop adapter and the X-mount are in the box; 22 mm stator, 14 poles; the base pattern is not printed on any seller page (the 22xx standard 16 x 19 M3 is expected: **measure the motor in hand before the cage plate is printed**, T2) | Ø34 (Ø36 only if the ceiling test allows) | 64.1 / 63.9 fps | 90 % | sunnyskyusa.com $24.99 (V3) and $18.99 (V2), available: true (page), https://sunnyskyusa.com/products/sunnysky-x2216 ; readymaderc.com $22.99 "In Stock" (page), https://www.readymaderc.com/products/details/sunny-sky-x2216-brushless-motor-short-shaft-880kv ; amazon.com $26.99 FBA "only 3 left" (page), https://www.amazon.com/dp/B0BR4VV3FG ; buddyrc.com $19.99 (long shaft) |
| **T-Motor MN2212 V2 920KV: backup part** | 920 | 54 g (65 with leads) | 4 mm shaft; 16 x 19 and 19 x 25 patterns per the RobotShop listing | Ø34 only | 67.0 / 66.8 fps: at the edge of the 66 fps bench limit; the bench ceiling test decides, and a failure means only 880 KV motors (no fixed 11 V regulator exists) | 86 % | robotshop.com $55.90 "In stock" (page), https://www.robotshop.com/products/t-motor-navigator-mn2212-v2-920kv-brushless-motor ; store.tmotor.com $46.90 (China) |
| Generic 2212 920KV (HAWK'S WORK): the cheap fallback | 920 | 52 g | threaded bell-top boss with a cap nut (the easiest hub: a plain bore clamped under the cap); 16 and 19 mm holes printed on the listing | Ø34 only | as the MN2212 | 86 % | amazon.com $12.99 FBA "only 13 left" (page), https://www.amazon.com/dp/B0DNHRWRQ7 |
| Not chosen | | | | | | | EMAX MT2216 810KV: sold out at EMAX global, not listed by EMAX USA; Hobbywing XRotor 2216 880KV: no listing anywhere; T-Motor MT2216 900KV: not in T-Motor's store; A2212 930KV ($8-13, everywhere): over the band |

The check, at the worst corner (KV +5 %, rail +4 %, tyre grown): v_max = 0.945 x 1.05 KV x 12.48 V x pi x D / 60 +
0.5 fps. X2216 880 on Ø34: 0.945 x 924 x 12.48 x pi x 0.034 / 60 = 19.4 m/s = 63.6 + 0.5 = **64.1 fps** (the physics'
Ø34 map row scaled by 880/875: 63.9); on Ø36: 67.7 fps, over the 66 fps bench limit, so Ø34 is the first tyre and Ø36
is fitted only if every ball of test 4.2 on Ø34 is under 60 fps. The 24 V fault on this motor: 2 x 12 V no-load,
~21,100 rpm, 128 fps on Ø34: the same fault, the same three guards (12 V-only rail with keyed CT pins, pre-feed eRPM
check, trip latch). The pre-feed check becomes "eRPM below 1.10 x KV x 12 V" (11,600 rpm for 880 KV) in CONFIG.

**The hub on this motor** (T2): the X2216's shaft is Ø3.17 and its collet prop adapter clamps on it and gives a threaded
stud with a washer and nut. The flywheel hub becomes a PA6-CF disc with a clearance bore for the stud, clamped between
the adapter's flange and the nut, as a propeller is; the motor hangs bell-down under the cage plate with the shaft
down and the hub below the bell. Its height is read from the motor in hand (short-shaft version) and sets the cage
plate's rise (~15-20 mm, est). Runout is measured at assembly (test 1.5, <= 0.15 mm); a 2 mm pin through hub and
adapter flange is the fallback if the nut alone lets it slip. Mass: +2 x 40 g against the Snails.

### 3.2 The feed drive: a third STS3215 instead of the M2006 + C610

The dial needs 45 deg steps in <= 250 ms, a few hundredths of a N m, a hold when parked, and jam detection. The
STS3215 (2.94 N m stall, 45 rpm at 12 V, 12-bit absolute angle, load and position feedback on the serial bus) does all
of it, is already on pan and tilt (one part type, one bus, one driver), weighs 60 g against 107 g, and costs $22
against $95 + $39 (the C610 is $250-320 where it can be had at all). It takes its power from the switched 12 V rail
through a 3 A polyfuse (CT power pin 3, "12 V FEED"), so the safety line still cuts the dial in hardware, and the 24 V
rail no longer reaches the cartridge at all. The physics agent reruns the feed with the servo's torque-speed line
(T5); the expected rate is 3 balls/s clean, 4/s to be measured (appendix). Jam detection is position-based first (not
settled in 300 ms) with the load reading as the second signal.

### 3.3 Every bought part: primary and backup, with stock and links

| Part | Primary | Backup | Notes |
|---|---|---|---|
| Flywheel motor x 2 | SunnySky X2216 880KV V3, $24.99, sunnyskyusa.com, in stock (page) | the same part at readymaderc.com $22.99 or amazon.com $26.99 FBA; backup part T-Motor MN2212 V2 920KV, robotshop.com $55.90 in stock (page) | three US sellers of the primary; the backup part is at the KV edge |
| ESC x 2 | Repeat Robotics AM32 35A (the catalogue's part), $24.99 palmbeachbots.com and $25.00 repeat-robotics.com, both available: true (page) | Lumenier Razor Pro F4 45A 2-6S AM32, $31.49 racedayquads.com, available: true (page), https://www.racedayquads.com/products/lumenier-razor-pro-f4-45a-2-6s-am32-esc (getfpv.com $23.99, snippet); Holybro Tekko32 F4 45A AM32 $23.99 holybro.com (HK) | both need the AM32 configurator once (bidirectional DShot, brake_on_stop, current limit, max_ramp): a USB linker is in the tools; 4-in-1 fallback Sequre Blueson A2 65A AM32 30x30, pyrodrone.com $48.99 |
| Servo x 3 (pan, tilt, feed) | Waveshare ST3215 12 V 30 kg-cm (SKU 22414), about $21.99, waveshare.com, no US warehouse (express 3-8 working days from China), https://www.waveshare.com/st3215-servo.htm (page) | amazon.com B0CFY52HVV $30.99 "In Stock" (seller-fulfilled, Nov 10-18) and B0B6P9271Q $30.90 FBA ("only 1 left"); robotshop.com $31.71 backorder; openelab.com $27.99 pre-order; seeedstudio.com ST3215-C047 $22 "in stock" (snippet, unverified) | **the schedule risk: order on day one.** Add the Waveshare Bus Servo Adapter (A), $4.99 (amazon $10.55), to set IDs |
| Controller | Adafruit Feather M4 CAN Express 4759, $24.95, adafruit.com "In stock" (page) | the same at Digi-Key 1528-4759-ND (~495, snippet) and Mouser 485-4759 (~430, snippet); backup part Adafruit Feather RP2040 CAN 5724, $19.95, in stock | three sellers |
| 12 V flywheel regulator (fixed) | Pololu D24V150F12 #2885, $79.95, "Rationed (Active)", 103 in stock 2026-10-27 + 95 within days, backorders allowed (page), https://www.pololu.com/product/2885 | Pololu D42V110F12 #5677, $69.95, 180 in stock (9-10 A at 24 V in: enough for the ramp and 3/s; the 3 ms recovery pulses ride the bank); a sealed fixed 24->12 V 15 A module, amazon.com B0BLC1C1RM $23.99 (15 left) as the last resort | Mean Well SD-100B/150B-12 have a trim pot (11-16 V): not allowed on this rail |
| 12 V PAN and 12 V AUX regulators x 2 | Pololu D36V50F12 #4095, $39.95, 343 in stock (page) | Pololu D42V55F12 class | |
| 5 V regulator | Pololu D36V28F5 #3782, $23.95, 86 in stock (page) | Pololu D24V22F5 class | |
| Safety switch | Pololu 2815, $8.49, 49 in stock + 100 within days (page) | a 20 A logic-level high-side switch board (any) | |
| Slip ring | SparkFun ROB-13065, $27.95, "In stock" (page) | Adafruit 1196, $19.95, 6 in stock (page); Digi-Key 1568-13065-ND (~50, snippet) | both share the Ø22 body and Ø44-44.5 flange: `RING_MODELS` has both |
| Hall switch | Allegro A1120LUA-T, Digi-Key 620-1330-ND, $1.79, ~22k (snippet) | Honeywell SS443A, Mouser 785-SS443A $4.69 (~3.8k, snippet) | not at Mouser; avoid DRV5032FB (0 stock until 2027) |
| Index magnet | McMaster 5862K102 (3/16 x 1/8 in N42), $1.00 | K&J Magnetics D32 | |
| Laser (Class 2, < 1 mW) | Quarton VLM-650-03 LPT, 650 nm 1 mW, Ø7.0 x 21 mm, 2.6-6 V, < 35 mA, Digi-Key $18.31-25.03, in stock in every snapshot (371-2,275), https://www.digikey.com/en/products/detail/quarton-inc/VLM-650-03-LPT/1010454 | Quarton VLM-650-28 LPT (63, snippet); the green VLM-520-73 LPT is 0 stock, 4-week lead | the Ø7 bore of `laser_mount` is kept; the LPA variants are 2.5 mW Class IIIa: not allowed; Adafruit's lasers are all 5 mW |
| Pan bearing 6810-2RS | VXB Kit7458, $24.99, in stock (page) | Bearings Direct $29.19 (1); McMaster 6656K229 (6810-2Z) $33.29 | |
| Tilt bearing MR126-2RS | Bearings Direct $4.56 (646, page) | VXB $7.77; McMaster 7804K112 $8.89 | |
| Pan clamp (SendCutSend) | 6061-T6 0.125 in from exports/turret/pan_clamp.dxf, instant price on upload (est $15-25 with the minimum order) | Xometry sheet-cut upload (instant price) | the one custom part |
| Circlip DIN 471-50, shoulder screw, thumbscrew, O-ring, screws, inserts, dowels, standoffs | McMaster (numbers in bom.json) | Belmetric (screws, washers), ruthex / 3DJake (inserts) | McMaster delivers next day |
| DT12 set | TE DT04-12PA-L012 LCSC C6423585 $10.36 (Newark ~$15, Del City $12.84); DT06-12SA + W12S + sockets, Digi-Key $8.50; W12P $1.20; 12 x 0460-202-16141 $0.30 | Amphenol AT06-12SA kit at Chief Enterprises $10.49 (buy plug and receptacle from one family) | needs a size-16 solid-contact crimper (tools) |
| Micro-Fit 3.0 housings and crimps | Heilind / Digi-Key / Mouser (numbers in docs/turret-wiring.md) | any of the three | the 2 x 5 pair (43025-1000 / 43020-1000) has no price in the catalogue yet: ~$0.60 each like its siblings |
| XT60E-M (stand inlet) | Pyrodrone 10-pack $11.99 (page) | Jameco $0.99 each | |
| Stand rocker, DC rated | Switch Components RA1-1A-DC-2-B-1, SPST 10 A 28 VDC, Ø20.2 round snap-in, 0.187 in tabs: Jameco 2337967 $1.54 (10+, NCNR; 1,222 in stock per its page, snippet), TME $1.99 (231 in stock, snippet) | Carling RA581-VB-B-0-V (10 A 30 VDC), waytekwire.com $2.21 (5+): 0 in stock, 106-day lead | the stand's rectangular cutout becomes a Ø20.2 hole (T6) |
| Stand fuse holder and fuse | Littelfuse 03455LS1H $7.16 and 0477005.MXP $1.00, Digi-Key | LCSC (holder, out of stock) | |
| Pendant (hold-to-run) | AbleNet Specs IC, $75.00, in stock (catalogue 2026-10-27) | a generic momentary (NO) foot pedal, amazon.com ~$15 (confirm on order day); the industrial one, Linemaster 491-SC3 NO momentary, masterelectronics.com $101.06, 7 in stock (snippet) | the 3.5 mm jack stays; a foot pedal is wired to a 3.5 mm plug |
| USB-CAN | Fysetc UCAN (MM-U2CAN-0001), $8, fysetc.com (catalogue 2026-10-27) | BIQU U2C $23.99 (orderable); Innomaker USB2CAN isolated (amazon, ~$35, confirm); Openlight CANable 2.0 $35 (out of stock) | an isolated adapter is preferred on the Orin box (docs/turret-plan.md 2.12) |
| 24 V bench supply | Mean Well LRS-350-24 (24 V 14.6 A): masterelectronics.com $31.40, 601 in stock (snippet); Jameco $32.10, 299 in stock (snippet) | LCSC $18.68 (127 in stock, snippet); LRS-200-24 | a 350 W supply covers the J501 as well on the box |
| Ammo (300 balls) | Out of Darts Worker Cheetah 100-pack $15.00 (page, stock not shown) and 200-pack $29.99 | Hasbro Rival 100-round refill (Amazon / Target), Adventure Force (Walmart) | buy one brand for the counts |
| Reference chronograph | Caldwell Ballistic Precision 2.0 (optical, Bluetooth): Walmart $144.37, Knife Country USA $146.24 "in stock" (snippets) | Competition Electronics ProChrono DLX: grafs.com $136.99 "In Stock" (snippet) | optical gates read foam balls; a radar unit (Garmin Xero) is not needed |
| Tools (once) | IWISS IWD-1620 Deutsch size-16 solid-contact crimper $24.99 (iwiss.com); an open-barrel crimper for Micro-Fit 3.0 (IWISS IWS-3220M or Engineer PA-09, ~$30-50, Amazon); an AM32/BLHeli_32 USB linker (~$10-15 on Amazon; VXB $49.99 as the US fallback); external circlip pliers for 50 mm; heat-set insert tips M3/M4/M5; a 5 mm hand reamer; a dial indicator with a base | | docs/turret-assembly.md lists the hand tools |

### 3.4 Single-source watch list

The STS3215 (every US seller is a reseller of one Chinese maker; only Waveshare direct is reliable today), the Pololu
regulators and switch (all "rationed", all in stock today), the Feather (one maker, three sellers), the X2216 (one
maker, three US sellers), the ring (SparkFun and Adafruit sell two makers' equivalents). None is a blocker; all go in
the first order.

## 4. Build package

### 4.1 BOM with costs and stock (v0)

Unit prices as read on 2026-10-27 (section 3.3 and catalog/turret.json); main's bom.json totals $788.94 for the turret
and $119.59 for the stand with the DJI parts and the green laser; the v0 lines below replace those. McMaster hardware
is bought in packs, so two numbers are given.

| Group | Line | Qty | Unit | Line | Source | Stock |
|---|---|---|---|---|---|---|
| Drives | SunnySky X2216 880KV V3 | 2 | $24.99 | $49.98 | sunnyskyusa.com | in |
| Drives | Repeat Robotics AM32 35A ESC | 2 | $24.99 | $49.98 | palmbeachbots.com | in |
| Drives | Feetech STS3215 / Waveshare ST3215 12 V | 3 | $21.99 | $65.97 | waveshare.com | ships from CN |
| Drives | Waveshare Bus Servo Adapter (A) | 1 | $4.99 | $4.99 | waveshare.com | - |
| | **Drives subtotal** | | | **$171** | | |
| Electronics | Feather M4 CAN Express 4759 | 1 | $24.95 | $24.95 | adafruit.com | in |
| Electronics | Pololu D24V150F12 (12 V FLY) | 1 | $79.95 | $79.95 | pololu.com | in (rationed) |
| Electronics | Pololu D36V50F12 (12 V PAN, 12 V AUX) | 2 | $39.95 | $79.90 | pololu.com | in |
| Electronics | Pololu D36V28F5 (5 V) | 1 | $23.95 | $23.95 | pololu.com | in |
| Electronics | Pololu 2815 switch | 1 | $8.49 | $8.49 | pololu.com | in |
| Electronics | SparkFun ROB-13065 slip ring | 1 | $27.95 | $27.95 | sparkfun.com | in |
| Electronics | Panasonic EEU-FR1V102 1000 uF 35 V | 3 | $1.20 | $3.60 | Mouser / Digi-Key | - |
| Electronics | NE555P, UA78L05, 4N35, 2 x SN74HC123N, SN74HC74N, SN74HC08N, SN74HC14N, SN74AHCT125N, LM393P, 2N7000, reset button, passives | 1 set | | $12 | Digi-Key / TI store | - |
| Electronics | IRLZ44NPBF | 6 | $1.60 | $9.60 | Mouser / Digi-Key | - |
| Electronics | TSAL4400 + TEFT4300 (gates) | 2 + 2 | | $1.70 | Mouser / Digi-Key | - |
| Electronics | A1120LUA-T + 5862K102 magnet | 1 + 1 | | $2.79 | Digi-Key, McMaster | in |
| Electronics | Quarton VLM-650-03 LPT laser | 1 | ~$22 | $22 | Digi-Key | in (snippet) |
| Electronics | Micro-Fit 3.0: 2 x (43025-1200 + 43020-1200) ring pairs, 43025-0600 + 43020-0600, 43025-1000 + 43020-1000, 12 + 12 crimps 18 AWG, 30 + 30 crimps 24 AWG | 1 set | | $16 | Heilind / Digi-Key | - |
| Electronics | DT12: DT04-12PA-L012, W12P, 12 pins; DT06-12SA kit | 1 set | | $23.66 | LCSC / Digi-Key | in |
| Electronics | Fuses and holders: 3 x 3557-2, 2 x 0287010.PXCN, 2 x 0297015.WXNV, 3 x MF-R300, 1 x MF-R200 | 1 set | | $6.15 | Mouser / Digi-Key | - |
| Electronics | Wire: 2 x 18 AWG 25 ft (Remington), 26 AWG kit (Adafruit 2517) | 1 set | | $22.95 | Zoro, Adafruit | - |
| Electronics | 4 x 50 x 70 perfboard, 4 + 4 M3 standoffs, 51225K32 silicone tube | 1 set | | $11.60 | Tayda, McMaster | - |
| | **Electronics subtotal** | | | **$377** | | |
| Mechanical | 6810-2RS (VXB Kit7458) | 1 | $24.99 | $24.99 | vxb.com | in |
| Mechanical | MR126-2RS | 1 | $4.56 | $4.56 | bearingsdirect.com | in (646) |
| Mechanical | Pan clamp, SendCutSend 6061-T6 0.125 in | 1 | ~$20 | ~$20 | sendcutsend.com | instant price |
| Mechanical | DIN 471-50 circlip 98541A167 | 1 | $3.10 | $3.10 | McMaster | next day |
| Mechanical | Shoulder screw 92981A101 | 1 | $2.82 | $2.82 | McMaster | next day |
| Mechanical | Thumbscrew 92581A250 + O-ring 9452K14 (pack) | 1 + 1 | | $9.64 | McMaster | next day |
| Mechanical | Screws (M2 x 8/10/20, M3 x 6/8/10/12/16/20 socket, M3 flat, M4 x 10, M5 x 16), nylon-tip set screws, inserts (M3, M3 short, M4, M5), washers, dowels Ø5 x 16 and Ø4 x 8 (numbers in bom.json; the Snail's drive pins and the flap pin and spring dropped) | 22 lines | | $36 used / ~$110 as packs | McMaster | next day |
| | **Mechanical subtotal** | | | **$101 used / ~$175 as packs** | | |
| Printed | PA6-CF ~520 g, PETG ~455 g (incl. the stand), TPU ~12 g | | | ~$56 | Bambu | - |
| | **Turret, all in** | | | **~$705 used / ~$780 as packs** | | |
| Bench | XT60E-M (10-pack), RA1-1A-DC-2-B-1 rocker (10, NCNR), 03455LS1H + 2 x 0477005.MXP, 3.5 mm jack 35PM2A, SJ5003 feet, 70 x 50 perfboard | 1 set | | ~$50 | Pyrodrone, Jameco, Digi-Key, Tayda | in |
| Bench | Pendant: AbleNet Specs IC | 1 | $75.00 | $75.00 | ablenetinc.com | in |
| Bench | USB-CAN: Fysetc UCAN | 1 | $8.00 | $8.00 | fysetc.com | orderable |
| Bench | 24 V PSU Mean Well LRS-350-24 | 1 | $31.40 | $31.40 | masterelectronics.com | in (snippet) |
| Bench | Balls: Worker Cheetah 200 + 100 | 300 | | $44.99 | outofdarts.com | confirm |
| Bench | Reference chronograph, Caldwell Ballistic Precision 2.0 | 1 | $144.37 | $144.37 | walmart.com | in (snippet) |
| | **Bench subtotal** | | | **~$354** | | |
| Tools (once) | IWD-1620 Deutsch crimper $24.99; Micro-Fit crimper ~$40; AM32 USB linker ~$15; external circlip pliers ~$12; insert tips ~$10; 5 mm reamer ~$10; dial indicator and base ~$30 | | | ~$142 | iwiss.com, Amazon | confirm |
| | **v0 total** | | | **~$1,200 (turret ~$705-780, bench ~$354, tools ~$142)** | | |

Lead times: McMaster next day; Pololu, Adafruit, SparkFun, VXB, Palm Beach Bots, SunnySky USA 2-5 days; SendCutSend
3-5 days; the servos 1-3 weeks from China (the critical path: order first); Digi-Key / Mouser 2-3 days. The first
printer-days overlap the servo wait.

### 4.2 Print plan (v0)

From main's `exports/turret/bench/print-plan.json` (hours are rough, for a P1S at 0.2 mm; PA6-CF structure 100 %
solid on a hardened nozzle except the pan base at 40 % gyroid, PETG 2 mm walls 40 % gyroid, TPU 95A), with the v0
changes: the cartridge body taller for the new motors, both tyre sizes, the bumper and flap not printed.

| Part | Material | Qty | Bed (mm) | g | h | Orientation and notes |
|---|---|---|---|---|---|---|
| pan_base | PA6-CF | 1 | 160 x 158 x 47 | 70 | 4.6 | on its foot; 40 % gyroid (`PARTIAL_FILL`) |
| pan_ring (turntable) | PA6-CF | 1 | 81 x 81 x 41 | 72 | 4.7 | upside down; gear teeth flat on the bed |
| pan_spacer | PA6-CF | 1 | 59 x 59 x 4 | 3 | 0.2 | wide end down |
| pan_pinion | PA6-CF | 1 | 29 x 29 x 17 | 8 | 0.5 | flat; 100 % |
| ring_carrier | PA6-CF | 1 | 73 x 65 x 12 | 30 | 2.0 | on its top face; reprinted once the ring's flange holes are measured (T6) |
| ring_driver | PA6-CF | 1 | 40 x 39 x 14 | 7 | 0.5 | on its top face |
| tilt_yoke | PA6-CF | 1 | 152 x 91 x 48 | 101 | 6.6 | on its back: layers along the arms |
| cradle | PA6-CF | 1 | 182 x 126 x 59 | 76 | 5.0 | flat |
| cartridge_body | PA6-CF | 1 | 163 x 103 x ~70 (taller cage) | ~150 | ~10 | on its base; supports under the chute; the longest print, after the motor is measured |
| flywheel hub | PA6-CF | 2 | 28 x 28 x 15 | 7 each | 0.9 | flat; the stud bore reamed to a clearance fit |
| flywheel_tyre Ø34 and Ø36 | TPU 95A | 2 + 2 | 36 x 36 x 12 | 3 each | 1.0 | flat; bore 4 % under the rim (`flywheel_tyre_print`) |
| dial | PETG | 1 | 91 x 91 x 44 | 21 | 0.8 | cone up; the horn recess underneath |
| hopper | PETG (translucent) | 1 | 111 x 101 x 65 | 20 | 0.8 | upright |
| hopper_lid | PETG | 1 | 102 x 102 x 13 | 8 | 0.3 | upside down; the flap not fitted in v0 |
| barrel | PETG | 1 | 35 x 30 x 100 | 13 | 0.5 | standing; last 15 mm blaze orange (filament change) |
| laser_mount | PETG | 1 | 20 x 18 x 24 | 3 | 0.1 | Ø7 bore as drawn |
| board_bay | PETG | 1 | 58 x 57 x 46 | 12 | 0.5 | on its back |
| stand_box | PETG | 1 | 200 x 180 x 100 | 292 | 11.7 | upside down (on its top plate); the rocker's Ø20.2 hole |
| stand_bottom | PETG | 1 | 240 x 180 x 16 | 86 | 3.4 | flat |
| **Total** | PA6-CF ~530 g / 35 h; PETG ~455 g / 18 h; TPU ~12 g / 1 h | | | ~1,000 | ~54 | three days on one P1S; the stand can print on a second machine |

Not printed in v0: bumper_ring (1.7 h TPU), hopper_flap (0.1 h): v1. Print order: the stand first (it needs no
decision), then base, turntable, yoke, cradle, carrier and driver; the cartridge, hubs and dial after the motor and the
servo are measured in hand (T2, T4); the tyres last. Materials: Bambu PA6-CF (hardened nozzle, dried; the FEA
allowables assume the humid, print-knocked-down values), Bambu PETG Translucent for the hopper, PETG for the rest, TPU
95A HF for the tyres. Heat-set inserts go in with the part still warm from the bed where possible; the fits table
(section 5, test 1) is measured before assembly.

### 4.3 SendCutSend parts

v0: `pan_clamp` in 6061-T6 aluminium, 0.125 in (3.175 mm), from `exports/turret/pan_clamp.dxf` (deburred, no finish);
SendCutSend gives an instant price on upload (`cad/turret.py` `SHEET`, `SHEET_PARTS`). Nothing else. Optional for the
robot, not the turret: the head plate under the TM pattern (docs/head-payload.md allows a SendCutSend plate).

### 4.4 Wiring (v0), at the level a person can build from

The wiring is docs/turret-wiring.md as written (the DT12 and ring pin maps, the ring's two Micro-Fit 2 x 6 connectors,
the pulse-train arm chain, the trip latch, the phase-short brake, the gates, the fuses, the budget), with these v0
deltas, which T8 writes into that page:

| Where | As written | v0 |
|---|---|---|
| CT power (2 x 3) pin 3 | +24 V DIAL to the C610 alone, 10 A MINI fuse | **+12 V FEED**: the dial servo, from 12 V FLY through a 3 A polyfuse (MF-R300) on level 0. No 24 V on the cartridge at all; the 10 A MINI fuse (`littelfuse-0297010-wxnv`) is not fitted |
| CT signal (2 x 5) pins 3, 4 | CAN_H, CAN_L to the C610 | **FEED_TTL** (the servo bus) and spare |
| CT signal pin 9 | BEAM | spare in v0 |
| Level 0 | the +24 V DIAL branch behind the 2815 | gone; the 12 V FEED branch instead |
| Level 2 | the NeoPixel header | not fitted in v0 |
| Cartridge | the C610 on the base plate behind the M2006, two cable ties | the servo's 3-pin lead to the pigtail; the cartridge board (6 x IRLZ44N + the LM393 with the two gates' resistors) on the cage plate beside the ESCs |
| Laser | Quarton VLM-520-73 LPT on 5 V | Quarton VLM-650-03 LPT on 5 V through the 2N7000 (< 35 mA) |
| Servo bus | pan across ring circuit 9, tilt on the +y arm | + the feed servo on CT signal pin 3; IDs 1 pan, 2 tilt, 3 feed, set with the Waveshare adapter before assembly and written on each servo; 500 kbit/s as written (margin over the ring) |

Everything else is unchanged and is not repeated here: the pulse chain (base 555 at 1 kHz into ring circuits 7/8, the
4N35 and the 20 ms retriggerable 74HC123 on level 1, ARM = pulses AND /TRIP into the 2815's ON pin and the Feather's
ARM_IN), the trip (74HC123 one-shot 2.98 ms from GATE_1, 74HC74 clocked by GATE_2, recessed reset), the brake (74HC14
+ 10 ms RC, six IRLZ44N shorting the phases 10 ms after the rail drops), the ring map (1-2 +24 V, 3-4 GND, 5-6 CAN,
7-8 SAFETY, 9 SERVO_TTL, 10 SIG_GND, 11-12 kept), the DT12 pinout, the fuses (stand 5 A DC-rated; base 10 A ATO; level
0 15 A MINI at the flywheel regulator; polyfuses 3 A on 12 V PAN, 12 V AUX and now 12 V FEED, 2 A on 5 V).

**The 12 V-only rule in v0 is simpler than drawn**: the cartridge's power connector carries 12 V on every pin; the only
24 V on the turret is the ring's pair into level 0. The regulator is a fixed-output part (no trim pot). The bench rule
stands: never put 24 V on the ESC side, not even for a test (section 5, test 4.6 simulates the fault without a ball).

**Board contents** (double-sided 50 x 70 mm perfboard cut to the bay's 52 x 50; M3 standoffs 12 and 14 mm):

- **Base board** (+x in the base): the 10 A ATO fuse in a Keystone 3557-2 holder on +24 V in; D36V50F12 (12 V PAN) with
  MF-R300 to the pan servo's 3-pin header; UA78L05 from 12 V PAN and the NE555 astable (1 kHz, 50 %) powered through the
  pendant loop (DT12 7-8), its output through 2k2 to the ring's stator plug pins 7/8; the stator plug (43020-1200)
  carrying +24 V and GND doubled (pins 1-4), CAN (5-6), SAFETY (7-8), SERVO_TTL and SIG_GND (9-10).
- **Level 0, power**: +24 V from the rotor plug into the 3 x 1000 uF bank; Pololu 2815 (ON from level 1's ARM, slide
  switch left ON); 15 A MINI (0297015.WXNV) -> D24V150F12 -> 12 V FLY to CT power 1-2 and, through MF-R300, 12 V FEED to
  CT power 3; +24 V unswitched -> D36V50F12 -> 12 V AUX (MF-R300) -> the tilt servo.
- **Level 1, logic**: +24 V unswitched -> D36V28F5 -> 5 V (MF-R200) -> level 2, the hall, the gates, the laser switch.
  The 4N35 with its 2k2 / 1 W on SAFETY+/-; the 20 ms 74HC123; the trip's 74HC123 and 74HC74 with the recessed button;
  the 74HC08 (ARM); the 74HC14 brake driver with its 10 k / 1 uF; the 2N7000 for the laser.
- **Level 2, MCU**: Feather M4 CAN (USB pin on 5 V); 74AHCT125 + 4.7 k pull-up for the servo bus (D0/D1, direction D4);
  the three servo branches (pan via ring 9/10, tilt, feed via CT signal 3); the CAN pair with its 120 R; the hall input;
  the gate inputs (10 k to 3.3 V); ARM_IN, TRIP_IN, PULSE_MON; the rotor plug (43025-1200 on the ring's leads).
- **Cartridge board** (on the cage plate beside the ESCs): 6 x IRLZ44N (3 per motor, drains to the phases, sources to a
  star, gates from BRAKE through 100 R with 10 k to source); LM393 with 50 mV hysteresis for the two TEFT4300
  phototransistors (4.7 k pull-ups), open-collector outputs to GATE_1/2; the two TSAL4400 emitters on 5 V through 100 R.

**Cables** (silicone-insulated stranded wire; lengths est from the CAD, T8 makes them exact):

| # | Run | Conductors | Gauge | Length | Strain relief |
|---|---|---|---|---|---|
| C1 | stand: XT60E-M -> rocker -> 5 A fuse -> terminal board -> DT06 plug pins 1-4 | 2 + 2 | 18 AWG | 250 mm | the DT06's backshell |
| C1b | stand: 3.5 mm jack -> DT06 pins 7-8; USB-CAN CAN_H/L -> pins 5-6 (120 R at the USB-CAN) | 2 pairs | 24 AWG twisted | 250 mm | same |
| C2 | base: DT04 pins 1-4 -> base board; pins 5-8 -> base board (CAN through, the loop into the 555's supply) | 4 + 4 | 18 / 24 AWG | 120 mm | tie to the housing at 60 mm |
| C3 | base board -> the ring's stator plug (the ring's own 250 mm leads, 28 AWG, doubled on pins 1-4) | 12 | 28 AWG | 100 mm | the carrier; a tie at the board |
| C4 | the ring's rotor leads -> level 2 (up the Ø40 bore beside the coupling, through the yoke's slot and the -y arm's window) | 12 | 28 AWG | 160 mm | tied to the driver disc's crescent |
| C5 | level 0 -> CT power receptacle on the cradle's -y rail (through the 40 mm tilt loop) | 6 | 18 AWG | 220 mm | tie at the yoke arm and at the cradle rail |
| C6 | level 1/2 -> CT signal receptacle | 10 | 24-26 AWG | 220 mm | same |
| C7 | cartridge pigtail: the two plugs -> ESCs (power 18 AWG, signal 26 AWG), cartridge board (BRAKE, +5 V, GATE_1/2, SIG_GND), the feed servo's lead | | | 150 mm | a tie at the cartridge base plate |
| C8 | level 2 -> tilt servo on the +y arm | 3 | the servo's own + 200 mm extension | | ties on the bridge |
| C9 | level 1 -> laser on the cradle tab | 2 | 24 AWG | 250 mm in the tilt loop | tie at the cradle tab |
| C10 | hall -> level 2 | 3 | 26 AWG | 90 mm | the pocket's hole |

### 4.5 Assembly order (v0)

docs/turret-assembly.md's twelve steps as written, with the v0 deltas (T6 and T10 regenerate the pictures from the
CAD; the hand tools are listed at the top of that page):

1. **Pan base and its inserts**: as written (5 x M3 in the clamp ears, 3 x M3 in the carrier bosses from below, 4 x M3
   base-board bosses, 4 x M4 DT pad; the 5 short M3 in the bumper tabs can wait for v1).
2. **Pan servo (ID 1), pinion, DT12 receptacle**: as written.
3. **Base board and the index magnet**: as written; the base board per section 4.4.
4. **Pan bearing and the aluminium clamp**: as written (5 x M3 x 8). Check: the outer race does not turn by hand; the
   inner race turns freely.
5. **Turntable, hall, spacer, circlip**: as written. Check: backlash at the rim 0.2-0.4 mm; two full turns by hand.
6. **Ring driver, the ring on its carrier, the coupling**: as written. Before this step the ring's flange holes are
   measured and the carrier reprinted to them (T6). Check: the ring turns freely before the carrier's screws are
   tightened (Moflon's rule), and after.
7. **Tilt yoke and the board bay**: as written; levels 0-2 per section 4.4; the rotor plug and the hall into level 2.
8. **Tilt servo (ID 2) and the cradle**: as written. Check the 0 and -25 deg stops by hand. The CT receptacles onto the
   cradle's -y rail (C5, C6).
9. **Laser**: as written, with the VLM-650-03 LPT (boresight at 4 m, test 6.1).
10. **The cartridge, on the bench** (changed): the feed servo (ID 3) up against the dial floor's underside, horn
    through the floor, 4 x M2 x 10 countersunk from above; the dial onto the horn (4 x M3 x 8 through the hub, from the
    top with the hopper off); set the servo's zero so a pocket is centred over the exit hole and write the count down.
    The two X2216s up under the cage plate, 4 x M3 x 6 each on the 16 x 19 cross, leads through their slots; each hub
    on its collet adapter under the bell with the washer and nut (snug plus a quarter turn; dial indicator at the rim:
    <= 0.15 mm, or re-seat); the Ø34 tyres stretched on first. The two ESCs and the cartridge board on the plate; the
    brake FETs to the phase leads; the pigtail C7.
11. **Barrel, gates, hopper, lid**: as written (the flap and spring not fitted).
12. **Cartridge onto the cradle, the mount**: as written (no bumper); then the turret onto the stand: 2 x Ø5 dowels,
    4 x M5 x 16, the DT06 plug.
13. **The stand**: inserts (4 x M5 top, 4 x M3 corners, 4 x M3 board bosses); the XT60E-M, the Ø20.2 rocker, fuse holder
    and jack in the front panel; the terminal board on its bosses; the USB-CAN at the back wall; the feet; C1 and C1b;
    the bottom plate. Clamp the stand to the bench through its tabs before any powered test.

## 5. Bench test sequence (v0), with pass/fail

docs/turret-bench-tests.md in build order, with the v0 motor, feed and ring items made explicit. Every test writes its
readings and pass/fail to a JSON under `exports/turret/bench/` named after the test (the charter's checklist links
them). Rig: the turret on its clamped stand, the laptop on the USB-CAN running the host side of the CAN set, the
pendant, the 24 V supply with its current limit at 10 A, a 20 mOhm shunt in the ring's +24 V stator lead, a two-channel
scope, a 100:1 probe, the reference chronograph 1 m out beside the barrel's own gates, calipers, a 0.01 g scale, a
spring scale to 100 N, a dial indicator, a thermocouple or IR thermometer, 300 balls of one brand (plus 50 worn and 50
damp ones for test 5.3).

### 5.1 Parts and fits (nothing powered)

| # | Test | Accept |
|---|---|---|
| 1.1 | Printed sizes: bearing seat Ø65.0, journal Ø50.0, the carrier's Ø65 opening, tyre bore 26.9, the CT dowel holes, the hub's stud bore | a light press for the seat, a slip fit for the journal, the hub a clearance fit on the stud and flat on the adapter's flange |
| 1.2 | Inserts: pull an M3 and an M4 insert from a PA6-CF coupon | > 300 N (M3), > 500 N (M4) |
| 1.3 | Gear mesh: dial-indicator backlash at the turntable rim; two full turns by hand at tilt 0 and -25 | 0.2-0.4 mm; no binding; nothing touches; the ring's leads do not wind |
| 1.4 | Tilt stops by hand | hard stop at 0 deg (level) and -25 deg; nothing else touches at any pan |
| 1.5 | Hub runout on the motor (dial indicator at the rim, motor turned by hand) | <= 0.15 mm; the tyre stays put after 50 turns by hand |
| 1.6 | Ball sizes: 50 balls on calipers and scale | Ø22.2-22.8, 1.6-1.9 g; outliers rejected from the hopper |
| 1.7 | The ring turns freely by hand with the carrier screws loose and tight; the coupling tube does not load it radially | no stiffness change when tightened |

### 5.2 Strength (bench level; the robot's falls are v1)

| # | Test | Accept |
|---|---|---|
| 2.1 | 50 N up on the muzzle with the cradle on its 0 deg stop, 200 times | no crack, stop creep < 0.2 mm |
| 2.2 | Lift the turret by its yoke to 100 N (spring scale) | the bearing's outer race does not move under the clamp |
| 2.3 | Pan servo at 50 % torque against a held turntable (once), then held 10 s | no tooth marks |

### 5.3 Electrics without motors (ESC and feed rails unplugged at the CT)

| # | Test | Accept |
|---|---|---|
| 3.1 | Power-up: 5 V, 12 V AUX, 12 V PAN present; the Feather's heartbeat on CAN; the pan and tilt servos answer their IDs | all present within 2 s; no fuse blown |
| 3.2 | The pulse-train safety line with a lamp on 12 V FLY (docs/turret-plan.md 6.5): pendant held -> lamp on; released -> off within 25 ms; the SAFETY pair opened at the ring; shorted to GND; shorted to +24 V; a DC level, a 300 Hz and a 3 kHz train, 50 Hz hum from a generator | only the genuine 1 kHz train arms; every fault disarms within 25 ms (scope at the 2815 output) |
| 3.3 | Trip latch with simulated gate pairs at 1.3, 2.2, 2.4, 2.6, 3.0 ms (6.7, first half) | latched at <= 2.4 ms, not at >= 2.6 ms; the latch holds until the button; ARM cannot rise while latched. Select the window's R here |
| 3.4 | Brake timing with a lamp: BRAKE rises 10 +-3 ms after ARM falls; falls before 12 V FLY returns on re-arm | scope |
| 3.5 | Homing: 50 power-ups at random pans | every home within 7 s; the index centre's spread <= 0.1 deg; 10 continuous turns each way and back within 0.2 deg |
| 3.6 | The servo bus over the ring (6.6): 1 h of 100 Hz reads and writes to the pan servo at 500 kbit/s while panning | checksum retries < 0.1 %; no command lost (position within 2 counts) |
| 3.7 | Ring contact resistance and dropouts (6.1 steps 1-2): 5 A through the paralleled pairs at 12 pan positions, then panning at 15 and 2 rpm, scope at 1 MHz | <= 60 mOhm per paralleled pair; no dropout > 100 us; variation <= 60 mOhm |
| 3.8 | CAN over the ring (6.2): 1,000 frames/s at 15 rpm for 1 h, then 2 rpm for 1 h | 0 bus-off; error frames < 1 per 10^6; no lost telemetry second |
| 3.9 | Feed servo alone (powered from the bench through CT power 3): 200 steps of 45 deg under an empty hopper, then a full one | step settled (within 2 deg) in <= 250 ms; load reading repeatable; a deliberate jam (a pencil in a pocket) detected within 300 ms and reversed |

### 5.4 Flywheels (the ceiling before anything else)

| # | Test | Accept |
|---|---|---|
| 4.1 | **No-load eRPM at 100 % throttle on the 12 V rail**, no balls: both wheels | <= 1.10 x KV x 12 V (880 KV: <= 11,600 rpm, 7 pole pairs); the rail 12.0 +-0.5 V under load |
| 4.2 | **Ceiling with balls**: 20 balls at 100 % throttle, Ø34 tyres | every ball <= 66 fps on both chronographs. If any passes 66, this motor/tyre pair is rejected (only a lower-KV motor remains: the cage cannot take Ø32). If all are <= 60 fps, repeat with Ø36 and keep Ø36 if still <= 66 |
| 4.3 | Speed at every throttle: 10 balls each at 60, 70, 80, 90, 100 % | a monotonic table, SD <= 1.5 fps at each point: the firmware's throttle-to-speed map |
| 4.4 | Set speed: 50 balls at the set rpm for 52 fps (Ø34) or 55 fps (Ø36) | mean within +-2 fps, SD <= 1.5 fps, none > 60 fps |
| 4.5 | Spin-up current at the ring's shunt with the 200 ms ramp (6.1 step 3; never a stepped start on this ring) and burst recovery (8 balls at 3/s) | peak <= 3 A at 24 V ramped, bus never below 16 V at the board, no ESC reset; every shot of the burst within +-3 fps of the set speed |
| 4.6 | **The 24 V fault, simulated without a ball**: (a) hopper empty, muzzle into a catch box, the feed servo unplugged, no balls anywhere on the bench: feed the ESC rail from the bench supply at 24 V through the CT power plug only, read the no-load eRPM (expect ~2 x the 12 V value, ~21,100 rpm) and confirm the firmware's pre-feed check goes SAFE and refuses to step; (b) the trip latch with a 1.3-1.6 ms simulated gate pair (test 3.3). Never a ball at 24 V | (a) SAFE within 100 ms of the first eRPM read above the limit; (b) latched |
| 4.7 | Release braking (6.8): wheels at speed, no ball; release; scope one phase through the 100:1 probe and read eRPM | ESC rail off <= 21 ms after the last pulse, short closed at +10 +-3 ms, speed <= 5 % by +50 ms; FETs < 60 C after 20 releases in 2 min |
| 4.8 | Tyre growth and creep: OD at the set speed by strobe or video; the tyres after 500 balls | growth <= +0.7 mm on the diameter; no creep on the rim |
| 4.9 | Ring temperature (6.3): 5 A for 1 h at 15 rpm, thermocouple on the ring body and carrier | rise <= 20 K |

### 5.5 Feeding

| # | Test | Accept |
|---|---|---|
| 5.1 | 100 balls per pose at 3/s: level; -25 deg; level while panning at 60 deg/s | 0 doubles; <= 1 jam per 100 (a step that needed a reverse); <= 5 % empty steps after the dither; jams and empties logged per 100 |
| 5.2 | The same at the firmware's maximum rate (4/s target; 3.5/s if the servo step is 250 ms) | 0 doubles |
| 5.3 | 50 worn and 50 damp balls, level, 3/s | 0 doubles; jams logged (an information test) |
| 5.4 | Parked safe: dial parked, rail off; the stand shaken by hand (~5 m/s^2) and knocked (~13 m/s^2) at tilt 0 and -25 | no ball reaches the wheels |
| 5.5 | The 5-ball hopper (the last balls of a magazine) at -25 deg | the lift-to-0 rule empties it; no ball left behind |

### 5.6 Accuracy and the game

| # | Test | Accept |
|---|---|---|
| 6.1 | Boresight the laser at 4 m | the dot within 2 cm of the group centre at 4 m |
| 6.2 | Groups: turret clamped, 20 shots at paper at 2 m and at 4 m, barrel level and at the tilt the firmware chooses for a 0.30 m target | 68 % radius <= 1.5 cm at 2 m, <= 5 cm at 4 m; the group centres recorded: the drop table |
| 6.3 | Aim repeatability: 20 moves to the same target from both pan sides | within 3 mrad when approaching in +pan |
| 6.4 | Fire while panning at 10 and 90 deg/s | the firmware holds fire above 10 deg/s |
| 6.5 | Knock-down: 20 g hinged plates at 2 and 4 m (sim/turret.py's plate), 5 balls each | every plate down |
| 6.6 | Temperature: 100 balls in 2 min then 10 min at speed; IR gun on ESCs, motors, the flywheel regulator, each servo | ESCs <= 80 C, motors <= 70 C, regulator <= 60 C, servos <= 60 C |
| 6.7 | Safety-line release during feeding: 20 releases at random points of 8-ball bursts | no ball above 20 fps after a release; where each resting ball ended, logged |
| 6.8 | Mock lidar: a Ø103 x 72 cylinder 148 mm ahead, its top 41.7 mm above the TM face, the depression table loaded | the barrel and every ball 10 mm clear at every pan |

Numbers that differ from the models go back to their owners: launch and feed to the physics agent (sim/turret_*.py),
fits and strengths to cad/turret.py and cad/turret_studies.py, timings to docs/turret-firmware.md.

## 6. Ordered task list for the implementer

Estimates are agent working hours (an Opus session), not calendar days; printing, shipping and the user's hands are
noted separately. Work in a feat/ worktree of `~/Code/gyropup` with a PR into dev (the repo's workflow; never push
main). **API** marks a task that changes `Turret(L)`, `.posed()`, `.meta` or `.bought` (names, frames or envelopes), so
the consumers listed at the top of this page must be rebuilt and checked.

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| T0 | **Baseline.** Build main as it stands and keep the numbers: `cad/turret.py`, `cad/build_turret.py --no-render`, `cad/turret_motion.py`, `cad/turret_assembly.py`, the quick e2e. Record mass (1.556 / 1.502 kg), print hours, margins, `no_listed_price` | exports/turret/* | every build runs; `clashes()` empty; the numbers in section 1 reproduced within 2 % | 1 h |
| T1 | **Record the v0 decisions and source the parts.** D42 in docs/decisions.yaml (v0 scope: X2216 880KV on Ø34, the STS3215 feed on the switched 12 V rail, the red laser, the items not fitted; the ring kept as D41 says). Catalogue entries (catalog/SCHEMA.md shape) for the X2216 and the MN2212, the Lumenier ESC, the servo sources, the VLM-650-03 LPT, the rocker, the PSU, the chronograph, the tools; the DJI rows marked replaced in catalog/sourcing.json `risk` and the false RDQ alternate removed from alternates.json; a second source for every new part. **Order sheets** per vendor from bom.json (McMaster, Digi-Key or Mouser, Pololu, Adafruit, SparkFun, SunnySky USA, Palm Beach Bots, Waveshare, VXB, Bearings Direct, LCSC, Pyrodrone, Jameco, Out of Darts, the PSU and chronograph sellers, SendCutSend upload) for the user to place; the servos and the motors first | docs/decisions.yaml, catalog/turret.json, catalog/sourcing.json, catalog/alternates.json, cad/build_turret.py `TURRET_BOUGHT`/`BENCH_BOUGHT`, exports/turret/bench/orders/*.md | bom.json: every v0 line has a price, a buy link and an alternate; `no_listed_price` and `not_in_a_catalogue` empty; the sheets total within 5 % of section 4.1; the user has clicked | 4 h |
| T2 | **CAD: the flywheel motor swap.** Replace `SNAIL` by a `MOTOR` dict from the X2216 measured in hand (Ø, height from the mount face to the bell end, the shaft and the collet adapter's stud, the base pattern, mass, KV, pole pairs); raise the cage plate so the hub on the stud sits on the ball path; the hub (`flywheel`) with the stud's clearance bore and a flat face on the adapter's flange; the cavities and the lead slots; keep `wheel_c` 53.0 and `TYRE_SET`. **API**: `.bought['flywheel_motor_l/r']` envelopes and masses change (names kept); `Geo.plate_z0/z1` move | cad/turret.py (`SNAIL`->`MOTOR`, `Geo`, `flywheel`, `cartridge_body`, `bought_parts`) | `clashes()` and `sweep()` clean at pans 0..350 x tilts 0/-25; the hub's centre on z = 0 of the C frame within 0.1 mm; the hub drawn with its bore and flange face; print plan regenerated; `cad/turret_motion.py` rerun: tilt move margin >= 5, the tilting CoM still behind the axis at every fill | 6 h (after the motor arrives) |
| T3 | **Physics: the launch on the new motor.** The motor constants (KV, phase resistance, no-load current, rotor inertia from the datasheet or est with the basis) into `sim/turret_launch.py` / `turret_launch3d.py`; rerun the ceiling map for Ø34 and Ø36 at 12 V with +5 % KV, +4 % rail, runout and growth; the set speeds per tyre; the 24 V fault row; the pre-feed eRPM limit | sim/turret_launch.py, sim/turret_launch3d.py, docs/turret-physics.md section 4 | launch3d.json: the fastest swept ball at 100 % <= 66 fps for Ø34; the set speed and throttle per tyre written for the firmware | 3 h (+ 15 min compute) |
| T4 | **CAD: the feed servo.** The STS3215 under the dial floor (its output face against the floor's underside, the horn through a Ø21 hole, 4 x M2 x 10 countersunk from above, 12 mm kept under its idler face for the plugs); the dial's hub on the horn (Ø20.2 x 3.2 recess, 4 x M3 on Ø14, from the top); remove the M2006 boss hole, the C610 window and the cable-tie slots; the cartridge board's place beside the ESCs. **API**: `.bought['feed_motor']` becomes the servo envelope (name kept); `.bought['feed_esc']` is removed: update `cad/turret_assembly.py` step 10, `cad/build_turret.py` `TURRET_BOUGHT`, `tools/part_images.py` if it lists it, and grep every consumer for `feed_esc` | cad/turret.py (`cartridge_body`, `dial`, `bought_parts`), cad/turret_assembly.py, cad/build_turret.py | clashes and sweep clean; the servo's bus plugs reachable from the housing's side window; the dial parks with a pocket over the hole at the servo's zero; `cad/turret_motion.py` rerun; the assembly picture for step 10 regenerated | 5 h |
| T5 | **Physics: the feed on the servo.** Replace the M2006 + C610 loop in `sim/turret_feed_dyn.py` by the STS3215 model used in `sim/turret_dynamics.py` (torque-speed line 2.94 N m / 45 rpm, a 50 % torque cap, an est reflected inertia through 345:1 with its basis); rerun the stepping rates, the poses, the jolt and vibration cases | sim/turret_feed_dyn.py, docs/turret-physics.md section 3 | feed_dyn.json: the clean maximum step rate, the step time, 0 doubles at <= 3/s, parked-safe unchanged; finding 2 rewritten for the servo | 3 h (+ 15 min compute) |
| T6 | **CAD: the small fits.** The ring's flange hole pattern measured on the ROB-13065 in hand into `RING_MODELS` (its `pcd` and hole size are assumed today) and the carrier regenerated; `LASER` = Ø7 x 21 (the VLM-650-03 LPT) and the mount's set-screw positions checked; the stand's rocker cutout to the RA1-1A-DC-2-B-1's Ø20.2 round; the stand's terminal-board bosses measured against the board in hand; the bumper tabs' short inserts noted as v1 in the assembly text. No API change | cad/turret.py (`RING_MODELS`, `LASER`), cad/turret_stand.py (`PANEL`), docs/turret-assembly.md | the carrier's holes match the ring (test 1.7 passes); print plan and bom regenerated; the stand's panel cutouts match the parts bought | 3 h (after the ring and the rocker arrive) |
| T7 | **Firmware v0.** (a) The servo bus with three IDs; the feed as position steps of 45 deg (512 counts), speed/accel for <= 250 ms, settled = within 23 counts, jam = not settled in 300 ms or load above a threshold -> reverse 20 deg and retry, three in a row stops; the dither; the feed servo dropping off the bus on release and returning on arm. (b) The set speed from the tyre and KV in CONFIG; the pre-feed check as eRPM <= 1.10 x KV x 12 V. (c) The AM32 settings file (bidirectional DShot, brake_on_stop, current limit 10 A, max_ramp) for the configurator. (d) A host script that runs section 5's tests and writes their JSON. Homing stays as written (continuous, on the index) | docs/turret-firmware.md, firmware/turret/*.py, a new firmware/turret/bench_host.py, firmware/turret/am32_settings.md | test_homing.py still passes 1,000 random starts; the feed driver's unit test steps a simulated servo at 3/s with a jam injected and recovered; the message set unchanged; the bench script dry-runs against a simulated turret | 10 h |
| T8 | **Wiring v0.** Section 4.4's deltas written into docs/turret-wiring.md (the 12 V FEED branch, the CT pinouts, the cartridge board, the laser), the board layouts drawn as grids (which part where on each perfboard), the cable lengths made exact from the CAD | docs/turret-wiring.md | every conductor and connector named with a length; a reviewer agent can trace +24 V from the XT60 to each ESC phase without a question; the 24 V cannot reach the cartridge by any mis-plug | 3 h |
| T9 | **FEA on the final geometry.** `cad/turret_studies.py` rerun on the taller cage and the servo mount: the cartridge (fall and recoil), the dial (jam at the servo's capped torque), the cradle's across-layer cases, the yoke and base re-checked; summary.json committed | cad/turret_studies.py, exports/turret/fea/ | SF >= 2 everyday and >= 1.2 in the falls, or the part named with its number for v1 (the bench's own loads are the everyday ones) | 4 h agent, ~3 h compute, in parallel with printing |
| T10 | **Print.** In the order of section 4.2 (the stand first; the cartridge, hubs and dial after T2 and T4); measure every fit of test 1.1 as parts come off; re-print what misses | exports/turret/*.stl, exports/turret/bench/fits.json | fits.json complete; nothing re-printed twice for the same reason | 2 h agent, ~3 days printer |
| T11 | **Assemble** per section 4.5 as parts and orders arrive; sub-tests 1.2-1.7, 2.1-2.3 as each group completes; pictures per step regenerated from the CAD and photographed | exports/turret/assembly/, exports/turret/bench/*.json | docs/turret-assembly.md current; tests 1 and 2 green | 3 h agent, the user's hands |
| T12 | **Electrics without motors**: section 5.3, the ring tests included | exports/turret/bench/electrics.json, trip.json, homing_bench.json, ring_*.json, feed_servo.json | 3.1-3.9 green (or the ring fails 3.7/3.8 and section 2.4's fallback is started); the trip window's R recorded | 3 h agent, 1-2 bench days |
| T13 | **Flywheels**: section 5.4 in order, 4.1 and 4.2 before any other powered flywheel test | exports/turret/bench/ceiling.json, speed_map.json, release.json | 4.1-4.9 green; the tyre chosen and written to CONFIG and to `TYRE_SET`'s note | 2 h agent, 1 bench day |
| T14 | **Feed and accuracy**: sections 5.5 and 5.6 | exports/turret/bench/feed.json, groups.json, game.json | green, or the failure named with its count; the drop table into the firmware | 2 h agent, 1-2 bench days |
| T15 | **v0 sign-off.** Tick the charter's checklist with links; the measured numbers back to the physics (launch, feed), the CAD (fits, strength) and the firmware (timings); the log entry; the mass by group measured | docs/turret-program.md, docs/turret-physics.md, docs/turret-firmware.md | every v0 claim in section 2.2 has a JSON; the open items for v1 listed with the number that demands each | 2 h |
| T16 | **v1: mass, strength, lidar, riser.** The measured groups vs 1.5 kg; infill and wall cuts where T9 allows; the cradle's across-layer case fixed if under 1.2; `cad/turret_lidar.py` rerun; the riser print; the 30 cm drop test; the bumper fitted; CONFIG rows | cad/turret.py, cad/turret_studies.py, cad/turret_lidar.py, exports/turret/lidar/ | mass_g_with_balls <= 1500 in turret.json or a new budget agreed in docs/head-payload.md; every fall case >= 1.2; the depression table regenerated | 8 h, 1 bench day |
| T17 | **v1: awesome and dock, robot hardware.** Lights and buzzer, hopper beam, fill flap and spring, green laser if wanted; the DT06 robot harness with the radio stop; manual firing on the Orin box (`cad/turret_box.py`); the ring's life test started in the background | cad/turret.py, cad/turret_box.py, docs/turret-wiring.md | each item's acceptance from docs/turret-program.md's checklist; the box scene fires 24 balls on command with the pendant held | 10 h agent, 2 bench days |

Dependencies: T1 first (the servos and motors are the critical path); T2 and T4 can run in parallel once the motor
and a servo are in hand (T2 waits for the motor's base pattern; T4 only for the servo's drawing, which is in
`SERVO`); T3 needs T2's motor choice (not its CAD); T5 needs T4; T6 after the ring and the rocker arrive; T7 and T8 are
independent of the CAD; T9 after T2 and T4; T10 after T6 for the stand and carrier, after T2 and T4 for the cartridge;
T11-T14 in order; T16-T17 after T15.

## 7. Risks

| Risk | Likelihood / effect | What to do |
|---|---|---|
| Real foam bridges over the dial: empty steps well above the sim's 24 %, or jams | high / the rate of fire and the game | The dither and the lift-to-0 rule first (free); test 5.1's counts decide an agitator in v1 (an eccentric cam ring under the pile is the physics' first candidate); never a faster step: 4/s is the clean limit |
| The ceiling margin is thin (2 fps on Ø36 with the Snail; with the X2216 the tyre set absorbs KV but the real tyre, hub and rail decide) | medium / safety | Test 4.2 before any other firing; Ø34 first; the trip latch at 66 fps; the pre-feed RPM check; no 24 V on the ESC side, ever |
| The X2216's base pattern or shaft is not what the 22xx standard says | medium / a reprinted cage plate | The motor is measured in hand before the cartridge prints (T2); the stand and base print meanwhile |
| The hub on a collet stud runs out or the tyre creeps | medium / accuracy (0.30 mm runout doubles the yaw scatter) and a thrown tyre | Ream the bore, test 1.5 (<= 0.15 mm), the 4 % stretch, a drop of CA under the tyre if it walks; a pin through hub and flange if the nut alone slips |
| The STS3215 steps the dial slower than 250 ms under a full hopper, or its load reading misses a jam | medium / rate of fire 3/s instead of 4; a jam un-noticed | Test 3.9 early (it needs only the cartridge); position-based jam detection does not depend on the load reading; the speed and acceleration registers tuned on the bench |
| The ring's contacts bounce under the flywheel current or shed CAN frames | medium / the v1 risk, retired or not in v0 | Tests 3.7, 3.8, 4.5 on the ROB-13065, then the Adafruit 1196; the cable-loop fallback of section 2.4 is written |
| AM32's current limit does not limit (reported unreliable before the 2025 PID loop) | medium / a 12 A spin-up pulse on a 2 A-per-circuit ring | The 200 ms ramp is the primary limit; the shunt measurement of test 4.5 on the first spin-up; the 15 A fuse |
| Pololu regulators rationed; the D24V150F12 superseded | medium / schedule | Pololu's own recommendation is the D42V110Fx family (same size and pinout): the backup in section 3.3; order with the first batch |
| The servo ships from China (Waveshare) and takes 2-3 weeks | medium / schedule | Order three on day one; the pan and tilt servos are needed at steps 2 and 8, the feed servo at step 10; the prints and the electronics fill the wait |
| The ring's flange hole pattern is not the carrier's | medium / one carrier reprint | T6 measures the ring before the carrier prints; the carrier is a 2 h print |
| Printed pinion at servo stall (SF 1.26-1.35) | low / a tooth | The 50 % torque cap in BOOT; test 2.3 once |
| PA6-CF moisture and layer strength | low / fits and cracks | Dry the spool; the fits table; the allowables already assume humid, print-knocked-down values |
| The Feather M4 CAN is one product from one maker | low / schedule | Adafruit, Digi-Key and Mouser all stock it; the Feather RP2040 CAN is the backup; the pin map fits both |
| The taller cage changes the tilt group's CoM | low / the barrel must still rise to 0 deg unpowered | T2's `cad/turret_motion.py` rerun: the CoM stays behind the tilt axis at every hopper fill (gravity torque negative in motion.json) |
| The cradle's across-layer SF in a robot fall (1.0 / 0.83 / 0.81) | low on the bench / a v1 fix | T9 reruns it; T16 fixes it (a thicker rail root or layers turned) before the robot |

## Appendix: the numbers used

- **Ceiling formula** (checked against the physics' map): v_ball,max = 0.945 x (1.05 KV) x (1.04 x 12 V) x pi x D / 60
  + 0.5 fps for the tyre's growth, with D the nominal tyre diameter in m and 0.945 the launch model's ball-to-surface
  speed ratio. Snail 875 KV, Ø36: 67.5 fps (the map: 66.8-68.0). 880 KV, Ø34: 64.1 fps (the map scaled: 63.9). 810 KV,
  Ø36: 62.3 fps. 920 KV, Ø34: 67.0 fps (over the 66 fps bench limit: a backup only, the bench decides).
- **Set speed**: rpm = (v_set / 0.945) x 60 / (pi x D). 52 fps on Ø34 is 9,500 rpm (90 % of 880 KV x 12 V); 55 fps on Ø34
  is 10,040 rpm (95 %: too little headroom for the recovery loop; the physics' usable band is 50-57 fps on this cage).
  eRPM = rpm x 7 for a 12N14P motor. Level from the 0.55 m TM face a 52 fps ball lands at ~4.7 m and reaches a 0.30 m
  target to ~3.3 m; the bench targets at 2 and 4 m are set at a height the drop table reaches.
- **The KV band this cage accepts on 12 V**: 790-860 KV with Ø36 (25 % crush), 860-910 KV with Ø34 (16.2 % crush).
  Below 790 the set speed needs > 92 % throttle; above 910 the Ø34 ceiling passes 66 fps and Ø32 would crush only 7.5 %
  (the physics wants >= 18 %). A fixed 9 V rail (Pololu D24V150F9 #2884, rationed like the 12 V) would open
  1,050-1,150 KV motors on Ø36, at the cost of a 2S-capable ESC; not used unless no 790-910 KV motor can be bought.
- **Servo-stepped dial**: STS3215 at 12 V, 45 rpm no load = 270 deg/s; a 45 deg step is 167 ms at full speed plus
  ramps, ~200-250 ms settled (est, test 3.9 measures); plus the ball's 130 ms drop and chute: ~350 ms command to muzzle,
  3 balls/s clean (the kids' rate), 4/s to be measured.
- **The ring's budget** (physics section 9, wiring 1.2): 2.2 A peak at the ring with the 200 ms ramp (1.1 A a circuit on
  the paralleled pairs), 4.9 A for ~3 ms per shot in a 10/s burst (RMS 0.6 A); the game average <= 2 A.
- **Mass in v0** (est): 1.556 kg as drawn with 30 balls + 2 x 40 g (X2216 against the Snail) - 47 g (the servo against
  the M2006 + C610) - 17 g (no bumper) - 1 g (no flap) = ~1.57 kg; v1 cuts ~70 g.
