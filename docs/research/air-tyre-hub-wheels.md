# Air-tyre hub motors for the wheels (issue #18, 2026-10-27)

The user: "for the wheels can we do something more like a 10" hub motor with air filled tires? That would give us some
suspension, ability to drive through puddles, and a step up I think? ... Maybe 8" or similar? In general I want air
tires." and "I don't think we would be able to jump, but we could maybe walk up stairs? Not sure if the hub motor would
be able to brake/lock in place?"

Air tyres are decided. This note picks the size and the part, and answers the engineering questions with the leg rig
(sim/wheel_study.py, run on a GB10), the full-robot kerb scenario, the leg's clash sweep (cad/wheel_fit.py) and hand
calculations. Raw results: exports/wheels/*.json. Nothing in cad/fivebar.py or sim/leg_rig.py was edited.

## 1. The answer up front

- **Primary: a 10 in single-shaft hoverboard-class hub motor with a 10 x 2.125 (or 10 x 2.5) pneumatic tyre, 36 V
  350 W, hall sensors, D-shaft Ø16 mm with 13.5 mm flats x 76 mm long, about 3.5 kg.** It is the only class of
  8-10 in air-tyre hub motor that is single-sided by construction (a hoverboard clamps the axle on one side only),
  runs at our 36 V bus, and sells at a listed price from several sellers. Sellers in section 2.
- **Backup: the same motor in 8.5 in** (an 8.5 in hoverboard "off-road" motor, ~3.3 kg): the same shaft and
  electricals, a 22 mm lower ride height, 15 mm more jump, 16 mm less rolling kerb.
- **Alternative with a real brake:** a 10 in 36 V 350 W scooter wheel with a drum brake and a two-sided M12 axle
  (Amazon kits about $225 with a controller we would not use). It needs a fork on the leg (section 2.4): not
  recommended for v1.
- **Does the leg support it? Yes.** Every rig scenario at 18.05 kg a leg (16.25 + the heavier wheel) stays under the
  RS-04's 120 N m (109 N m at the uncapped jump, the same as today); the landing loads on the knees and axle are
  within the cases the leg's FEA already carries (the 150 mm drop's axle spike falls from 1,727 to 1,470 N); the clash
  sweep is clean at every stance and stop pose. The jump falls from 206 to 167 mm (the wheel is 1.3-1.8 kg heavier,
  unsprung, and the leg carries it). Section 4.
- **Stairs: no, not for v1 with any wheel.** Rolling alone climbs about 25-30 mm (friction-limited at 0.22 r); the
  full-robot sim passes a 25 mm kerb and falls at 40 mm with every wheel. A jump-climb needs the wheel to clear a
  178-197 mm riser plus a 250-280 mm hop: our jump is 167 mm (10 in), 182 mm (8.5 in), 206 mm (BotWheel) at the 60 N m
  cap and about 7 mm more uncapped. A single 100 mm kerb by jump is marginal even with the BotWheel. Section 5.
- **Braking and holding: yes while powered, by the balance controller (3.8 N m a wheel on a 10 deg slope, inside the
  motor's continuous 5 N m), or by the VESC's handbrake/position hold when sitting; unpowered, the robot sits on its
  skids (D55's sit-down) and the skids are the parking brake. Phase-short braking is a damper, not a lock (3.5 N m at
  0.3 m/s, 11 N m at 1 m/s). No mechanical or electromagnetic brake for v1.** Section 6.
- **Drivers: keep the Flipsky 75100s** (14-84 V, hall + encoder ports). Hall-only FOC is fine for torque control; the
  risk is the wheel-speed estimate at near-zero speed (90 hall edges a turn). Mitigation in firmware first, a magnetic
  encoder on the rotor cover as the upgrade. Section 7.
- **Puddles: the motors are IPX4-class as sold; sealed as in section 8 they take a 40 mm puddle (the hub's seam sits
  45 mm above it on a 10 in wheel). The belly box goes to IP54 with a gasket; the harness gets Deutsch DT/DTP
  connectors.**
- **Mass: +2.7 kg (3.53 kg wheels) to +3.6 kg (4.0 kg) on a P3 ledger already at 32.27 kg against the 32.0 kg gate.**
  The gate must move (proposed D69: 35.0 kg) or the 8.5 in backup is taken (+2.2 kg). Section 4.4.

## 2. Candidates

Prices were checked 2026-10-27. Amazon, eBay, Walmart and AliExpress blocked the fetcher, so their prices come from
search snippets and are marked **[snippet]**; the implementer confirms the live listing before ordering (plan task W1).
Everything not read on a page is marked **[unverified]**.

### 2.1 Hoverboard single-shaft hub motors (group A)

The whole family (6.5, 8, 8.5, 10 in) shares one motor core: an outer-rotor BLDC, 30 magnets / 15 pole pairs, three
phase leads plus a 5-wire hall harness through a hollow D-shaft, the shaft clamped on one side in the hoverboard's
frame. ODrive's hoverboard guide ([docs.odriverobotics.com/v/0.5.5/hoverboard.html](https://docs.odriverobotics.com/v/0.5.5/hoverboard.html))
gives the electrical character: "30 permanent magnet poles, and thus 15 pole pairs", Kv "a typical value is 16" rpm/V
(so Kt = 8.27 / 16 = 0.52 N m/A), a measured phase resistance of 0.18 ohm and inductance 0.34 mH, "quite high
resistance compared to the hobby aircraft motors", and a current range of 25 A. Hoverboard controllers run them at
15 A; a VESC can push 30 A for seconds (15.5 N m, 243 W of copper loss). A 10 A continuous current (5.2 N m, 27 W)
is a safe thermal rating until the bench measures the case temperature.

| | 10 in pneumatic (primary) | 8.5 in off-road (backup) |
|---|---|---|
| Tyre | 10 x 2.125 pneumatic, tube type (e-gizmo: "Pneumatic Rubber d10 x 2.125 inches"; Hover-1 Titan: "Pneumatic", "Tubed"); 10 x 2.5 fits the same rim | 8.5 x 2.5-3.0 pneumatic on the "off-road" boards; some 8.5 in boards use solid tyres: check the listing says pneumatic |
| Outer diameter | 250-254 mm (Robokits: "Hub motor has a size of 16.3cm (with tyre 25cm)") | 216 mm [unverified] |
| Hub (motor case) diameter | 163 mm (Robokits) | 163 mm, the same core [unverified] |
| Mass | **3.53 kg** with the pneumatic tyre (e-gizmo, read on the page); 2.96 kg with an airless tyre (Robokits) | about 3.3 kg [unverified: scaled from the 10 in] |
| Shaft | **D-type, Ø16 mm round, 13.5 mm across the flat, 76 mm long** (Robokits RKI-9013, read on the page); hollow, the leads exit the end; single-sided | the same shaft [unverified] |
| Electrical | 36 V, 350 W, 15 pole pairs, Kv about 16 rpm/V, Kt about 0.52 N m/A, R 0.18 ohm, L 0.34 mH (ODrive guide); no-load about 576 rpm at 36 V = 7.7 m/s on 10 in; e-gizmo lists "800 rpm" (a faster wind or a loose figure: measure) | the same |
| Torque | 5.2 N m at 10 A continuous (estimate), 15.5 N m at 30 A peak (estimate); a hoverboard runs it at 15 A, 7.8 N m | the same; 15 % more ground force |
| Sensors | 3 hall sensors (5 wires); no encoder | the same |
| IP | "IP4" (Robokits), i.e. IPX4 splash; not submersible as sold | the same |
| Brake | none (no disc or drum mount; the cover is the rotor) | none |
| Rated load | a hoverboard carries 120 kg on two of these (Hover-1 Titan: "265 lbs"): 590 N static a wheel on a cantilevered shaft, with riding impacts on top | the same |
| Price, seller | **Robokits India RKI-9013, Rs 3,256 (about $39)**, in stock ([robokits.co.in](https://robokits.co.in/e-bike/hub-motor/10inch-36v-350w-brushless-bldc-hub-motor-with-tyre-for-e-bike-and-hoverboard), airless tyre: fit the pneumatic 10 x 2.125 tyre and tube, about $15 a wheel); **e-gizmo (PH) 230300029, PHP 999 (about $17)**, in stock, pneumatic ([e-gizmo.net](https://www.e-gizmo.net/gizmoshop/index.php?route=product%2Fproduct&product_id=49630)); **Alibaba "10 inch Hoverboard Motor Wheel 36V 350W" $12.99-26.70 a piece at 5-10 pieces [snippet]** ([alibaba.com](https://www.alibaba.com/product-detail/10-inch-Hoverboard-Motor-Wheel-36V_1600933431463.html)); **eBay 257475731234 "36V 350W 10" ... 10in Wheel Tire Assembly" $139.96 [snippet]**; Amazon "Scooter Hub Motor, 10 Inch 36V 350W" B09F5JXCWC (price not captured) | eBay 126688294737 Gyroor 8.5 in motor, used, $35 [snippet]; eBay.de 205597126956 "8.5 Inch Hoverboard Wheel 350watt 36v" (price not captured); Walmart 56207206 "36V 350W ... 8.5 Inch" (not captured) |
| US-shippable backup | a donor board: Hover-1 Titan (10 in pneumatic, tubed, 36 V, 2 x 250 W, $200-300 at Walmart [snippet]) gives two motors, a charger and a pack we do not use; the iFixit guide "Hover-1 Titan Wheel and Motor Replacement" shows the motor comes out as one part | Gyroor Warrior / Hover-1 Beast donor boards |

What is still unverified for the primary: the shaft's steel (section 2.4 assumes 45 steel, 355 MPa yield), the tyre's
pressure rating (10 x 2.125 tubes are marked 30-50 psi on scooter tyres), the no-load speed, the 8.5 in mass. Task W1
in the plan buys two 10 in motors first and measures mass, shaft, Kv, resistance and the hub's run-out before any CAD
is cut.

### 2.2 Scooter hub motors (group B; two-sided axles)

| Motor | Price, seller | Mass | Tyre | Axle | Electrical | Sensors | IP | Brake |
|---|---|---|---|---|---|---|---|---|
| Xiaomi M365 / 1S front motor, 8.5 in | about EUR 110 (wee-bot) to EUR 136 (culturevelo) [snippet]; 350 W clones EUR 62 (eBay.de 396311230106) [snippet] | not found | 8.5 x 2 pneumatic, tube | two-sided, fork | 36 V 250 W | halls | not stated | none (the M365 brakes on the rear) |
| Ninebot Max G30 rear motor, 10 in | Scooterworks (Segway AB.50.0028.88 equivalent) sold out to 2026-09 [snippet]; Wheelyshop SE, wee-bot FR (prices not captured) | not found | 10 x 2.5 tubeless | two-sided, swingarm | 36 V 350 W | halls | not stated | drum (the G30 rear) |
| Generic 10 in 36 V 350 W drum-brake wheel kits | Amazon B0GT9RBLTT / B0GTM5CRMY about $225 with a controller [snippet]; Walmart 19957963276 $225-230 [snippet] | about 4.1 kg [snippet] | 80/65-6 (255 x 80) pneumatic, tube | two-sided **M12** (10 and 25 mm thread lengths) [snippet] | 36 V 350 W, 15 km/h (about 280 rpm), geared [snippet] | halls | not stated | **drum** |
| ATO ATO-105-10 | $438.54, ATO ([ato.com](https://www.ato.com/10-inch-hub-motor)) | 4 kg | 10 in | 119 mm dropout, rear bicycle | 36/48 V 350 W, 30 N m max, geared 1:4.4 | not stated | **IP65** | V/disc |
| 10 in 48-52 V 1000 W (Zero 10X class) | $145-285 eBay [snippet]; VXB $284 (disc) [snippet] | not found | 10 x 3 | two-sided, 110 mm | 48-60 V: under-speed on our bus | halls | not stated | disc on some |

Every one of these needs a fork: a clevis spanning the wheel, bolted to the wheel link's foot, with the axle's flats in
its dropouts. Cost: two SendCutSend 6061 arms (about $25-40 each at an instant price) plus a cross-piece and the
wider track (the arm on the outboard side adds 15-20 mm a side). It also puts a part outboard of the wheel for kerbs
to hit. The drum-brake kit is the one reason to do it, and section 6 says the brake is not needed.

### 2.3 Robot hub motors (group C)

| Motor | Price | Why not |
|---|---|---|
| DDT M1502D_233 (Diablo's wheel) | JPY 60,500 Switch Science; US "contact for pricing", backordered (Robotics Center) | 24 V rated (our bus is 30-41 V), integrated driver (the VESCs would be bypassed), tyre about 187 mm [unverified], not 8-10 in; quote-only in the US (D40) |
| Unitree Go2-W wheel | not sold separately | 7 in pneumatic, no listing |
| Waveshare DDSM115 / DDSM210 | $24-79 | 0.25-2 N m, 3 kg load: far too small |
| ZLTECH ZLLG65ASM250, Honpine AGV wheels | quote or $657+ | AGV wheels, 140 mm, solid |

Nothing robot-grade exists at 8-10 in with an air tyre at a listed price. The hoverboard motor is the practical part.

### 2.4 The single-sided shaft: cantilever capacity

The D-shaft (Ø16, 13.5 across the flat): about the flats' axis I = 2,450 mm^4, Z = 363 mm^3 (a full Ø16 circle is
402). With the foot's clamp covering the shaft and the tyre's centre plane 45 mm from the clamp's inner edge (the hub
is 65 mm wide, the shaft 76 mm long), the bending moment is F x 45 mm:

| Shaft steel | Yield | Radial force at yield (45 mm lever) | Against the rig's worst axle spike with the 10 in wheel |
|---|---|---|---|
| 45 steel, normalised | 355 MPa | 2,860 N | 1,640 N (the capped jump's landing): SF 1.7; 1,470 N (drop 150): SF 1.9 |
| 45 steel, quenched and tempered | 600 MPa | 4,840 N | SF 2.9 / 3.3 |

The hoverboard carries 590 N static a wheel and survives riders' kerb hits, so the shaft is sized for this class of
load; the stress raiser where the flat ends is inside the clamp if the clamp covers the whole flat. The foot must clamp
the shaft over 40 mm or more (a split clamp with four M5s, as the hoverboard's bracket does with four M8s) so the
lever stays at 45 mm; a short clamp would double it. Plan task W3 adds the shaft to cad/leg_studies.py as a steel
beam at the rig's axle spikes, and W1 measures the shaft's hardness (a file test or a Rockwell check) to settle the
yield.

## 3. The tyre model

### 3.1 Radial stiffness of a 10 x 2.125 pneumatic tyre

Method: the membrane (inflation) model, k = 2 pi p sqrt(R r), with R the wheel radius and r the tyre's section
radius; the pressure carries the load and the contact patch grows with deflection. Calibrated against measurements:

- Rothhaemel (KTH, 2023), "Measuring vertical tyre stiffness of bicycle tyres", 20 in tyres: "31 N/mm to 147 N/mm",
  "tyre inflation pressure is the main factor", "values below 50 N/mm are related to extremely low inflation
  pressure". The model gives 162 N/mm for a 20 x 1.75 at 50 psi: the measured top is 147, so the model runs about 10 %
  high at pressure and more at low pressure (the carcass carries less than the model assumes).
- Cano-Moreno et al. (UPM, 2024), "The Vertical Stiffness of E-Scooter Tires", Latin American Applied Research
  54(3): compression tests on e-scooter wheels, "from 0.9 E5 N/m to 3.6 E5 N/m" (90-360 N/mm; the range includes
  solid tyres at the top).

So k = 0.75 x 2 pi p sqrt(R r) is taken, with r = 27 mm for a 2.125 in section (32 mm for 2.5 in):

| Tyre | 20 psi | 30 psi | 35 psi | 40 psi | 50 psi |
|---|---|---|---|---|---|
| 10 x 2.125 | 38 | 57 | **67** | 76 | 95 N/mm |
| 10 x 2.5 | 41 | 62 | 72 | 83 | 104 N/mm |
| 8.5 x 2.5 | 38 | 57 | 67 | 76 | 96 N/mm |

The rig's solid BotWheel tyre is an estimated 150-250 N/mm (sim/leg_rig.py), so the air tyre at 35 psi is a third of
it, which is what research/leg-suspension.md's `tyre_pneumatic` variant assumed. The bench test "the tyre's stiffness"
already in the leg plan (docs/handoff.md, M3) measures it: press the wheel against a scale through 10 mm at three
pressures.

### 3.2 In MuJoCo

The contact is a spring-damper with time constant tau on the mass behind it, so k goes as 1/tau^2: tau_p = 7.7 ms x
sqrt(200 / k_p). The study ran 14.1 ms / 0.5 for 60 N/mm (a conservative 35 psi), 18.4 ms / 0.45 for 35 N/mm (20 psi)
and 11.5 ms / 0.55 for 90 N/mm (50 psi). Damping ratios are the contact's, not the rubber's; the sensitivity below
covers them.

## 4. Does the leg support it?

### 4.1 The rig

rig/run.py's scenarios (its controller at 500 Hz, a tick of latency, the FLEXVOLT pair at R_int 0.1 ohm, 38 V static
and 40.5 V for the dynamic cases, the bottom bumpers at 140 mm), with the leg carrying 16.25 kg (D65's design mass)
plus the wheel's extra mass over the BotWheel. The wheel's mass was taken at 4.0 kg (the listed 3.53 kg plus the tube,
a heavier tyre and margin) with 4.5 kg as a sensitivity. The rotor share is 0.6 as for the BotWheel.

| Wheel | Leg carries | Jump 60 N m | Jump 120 N m | Jump landing: knee / axle / gearbox | Drop 150: knee / axle / gearbox | Power cut (undamped): knee | Stand torque |
|---|---|---|---|---|---|---|---|
| BotWheel 171 mm, 2.2 kg, solid | 16.25 kg | **206 mm** | 216 mm | 1,218 N / 1,542 N / 75 N m | 1,056 N / 1,727 N / 70 N m | 1,928 N | 15.8 N m |
| 8.5 in air, 3.3 kg, 67 N/mm | 17.35 kg | **182 mm** | 189 mm | 1,122 / 1,419 / 70 | 1,003 / 1,611 / 49 | 1,899 N | 15.8 N m |
| **10 in air, 4.0 kg, 60 N/mm** | 18.05 kg | **167 mm** | 173 mm | 1,311 / 1,643 / 70 | 893 / 1,470 / 50 | 1,926 N | 15.8 N m |
| 10 in, tyre at 20 psi (35 N/mm) | 18.05 kg | 167 mm | 173 mm | 1,048 / 1,314 / 69 | 763 / 1,257 / 40 | 1,912 N | 15.8 N m |
| 10 in, tyre at 50 psi (90 N/mm) | 18.05 kg | 167 mm | 175 mm | 1,513 / 1,896 / 71 | 988 / 1,628 / 58 | 1,939 N | 15.8 N m |
| 10 in, 4.5 kg | 18.55 kg | 156 mm | 164 mm | 1,146 / 1,451 / 68 | 914 / 1,507 / 48 | 1,931 N | 15.8 N m |

Reading it:

- **Gearbox:** every case stays under the RS-04's 120 N m, with 109 N m at the uncapped jump for every wheel (the
  push-off sets it, not the wheel) and 68-75 N m at the capped jump's landing. Nothing spends time over the peak.
- **Jump:** 206 to 167 mm for the 10 in, 182 mm for the 8.5 in. The push is the same; the wheel is unsprung mass the
  leg has to lift and the carriage is heavier. The uncapped jump adds only 6-10 mm, because the pack's 40.5 V start
  rule limits the push as much as the torque cap does.
- **Landings:** the 150 mm drop is 15 % kinder to the axle with the 10 in wheel (1,470 against 1,727 N) and 30 %
  kinder to the gearbox (50 against 70 N m). The capped jump's landing is about neutral (1,643 against 1,542 N on the
  axle): the tyre is three times softer but the wheel is 1.8 times heavier, and the spike is mostly the wheel's own
  mass stopping. At 20 psi the tyre wins (1,314 N); at 50 psi it loses (1,896 N). So run the tyre soft: 30-35 psi.
- **Stand torque is unchanged** at 15.8 N m: the wheel hangs below the leg; the motors hold up the body, not the
  wheel. (The issue's first table rose with wheel mass because it added the wheel to the carriage.)
- **The power cut** is 1,900-1,940 N on the knees for every wheel: that is the 16.25 kg leg (1,713 N at 14.75 kg in
  exports/leg/rig-results.json), not the wheel. D39's fault case scales with the robot's mass whichever wheel it has.
- **The knee-pin loads** (1,311 N capped jump, 893 N drop) are inside the leg's FEA cases (R1w carried the 2,065 N
  drop spike at 14.75 kg; cad/leg_studies.py reads the rig's joint forces). The front link's compression (1,269 N jump)
  is under its 1,243 N at the uncapped jump today by 2 %: re-run the studies (task W3).

### 4.2 Fit on the leg

cad/wheel_fit.py: fivebar.clashes() with the candidate's solid (a 254 x 64 tyre ring, a Ø165 x 65 hub, the Ø16 shaft
into the foot) in place of the BotWheel, at 130-380 mm with -20/0/+20 deg leans and at the six stop poses, with every
bought part: **0 clashes for the BotWheel, the 8.5 in and the 10 in** (exports/wheels/fit_clashes.json). The tyre
sits in its own y band (82-146 mm from the upper links' face against the links' 0-80 mm and the motors at -56..0), so
it can only meet the hip frame or the body, and neither reaches out there. The tyre's top passes 17 mm above the hip
axis at the shortest leg (101.5 mm) with the 10 in wheel; nothing is in that plane.

What does change:

| | BotWheel | 8.5 in | 10 in |
|---|---|---|---|
| Tyre width, y band | 44.6 mm, 82-127 | 64 mm, 82-146 | 64 mm, 82-146 |
| Track (two legs back to back, tyre centres) | 374 mm | 393 mm | 393 mm |
| Hip height at a 300 mm leg | 386 mm | 408 mm | 427 mm |
| Leg length for today's 386 mm hip height | 300 mm | 278 mm | 259 mm |
| Skids touch the ground at a leg length of | 160 mm | 138 mm | 119 mm (the leg's floor is 101.5) |
| Ground clearance under the belly, standing at 300 mm | 140 mm | 162 mm | 181 mm |
| Wheels lift when sat on the skids at full fold | 58 mm | 36 mm | 17 mm |

The wheel link's foot changes (task W2): the BotWheel's Ø50 boss recess and 4 x M6 on PCD 36 become a Ø16 D-bore
clamp, 45 mm long, split on the outer face with four M5 x 30 and heat-set inserts (or a steel clamp block from
SendCutSend if the PA6-CF clamp slips in the test), the cable exiting the shaft's hollow end into the link's Ø22 cable
hole as now. The foot's outer face moves out by the shaft's stand-off so the hub's inner cover clears the link (the
hoverboard's bracket sits 8-10 mm from the cover): about +8 mm, which the track numbers above include.

### 4.3 Body height and centre of mass

Standing at the same leg length the body rises 41 mm (10 in) or 22 mm (8.5 in); the robot's centre of mass (P3
ledger: 16 mm below the hip axis) rises with it and the balance model's pendulum gets 10 % longer: slower, easier to
balance, a touch more wheel torque in a push recovery (the sim's push scenario is in the plan's re-run). Standing at
259 mm instead keeps the hip height and the camera and lidar geometry, and leaves 158 mm of crouch (against 199 mm
today) and the same 140 mm of ground clearance. The full-robot sim's `H_RANGE` (sim/robot_v2.py) and the designer's
height slider need the new wheel radius either way (task W4).

### 4.4 The mass ledger

P3 is 32.27 kg today against the 32.0 kg gate (exports/body/mass.json; docs/body-next-plan.md lists the levers).

| Wheel | Per wheel | Robot | P3 ledger |
|---|---|---|---|
| BotWheel | 2.20 kg | | 32.27 kg |
| 8.5 in air (3.3 kg, unverified) | +1.1 kg | +2.2 kg | 34.5 kg |
| 10 in air, as listed (3.53 kg) | +1.33 kg | +2.66 kg | 34.9 kg |
| 10 in air, as simulated (4.0 kg) | +1.8 kg | +3.6 kg | 35.9 kg |

The foot's change is about neutral (a smaller recess, a longer clamp). No lever on the body's list is worth 3 kg, so
the gate moves: the proposed D69 sets the as-built ceiling at 35.0 kg with the design mass at 35.5 kg (17.75 kg a
leg), which the rig results above already bracket (18.05 kg a leg simulated). The 8.5 in backup is the choice if the
ledger must stay near 34.5.

## 5. Steps and stairs

### 5.1 By wheel torque alone

A wheel pressed against a step of height h with its axle load W, driven only by its own torque T and no push from
the body: moments about the step's corner need T >= W d with d = sqrt(2 r h - h^2); and the corner contact slips
unless d / (r - h) <= mu, i.e. h <= r (1 - cos(atan mu)). With mu = 0.8 on dry concrete that is h <= 0.22 r:

| Wheel | Axle load | Torque | Friction-limited step | Torque needed there | Torque-limited step (no slip) |
|---|---|---|---|---|---|
| BotWheel r 86 | 159 N | 14.3 N m | 19 mm | 8.5 N m | 86 mm (torque is not the limit) |
| 8.5 in r 108 | 170 N | 15.5 N m | 24 mm | 11.5 N m | 51 mm |
| 10 in r 127 | 172 N | 15.5 N m | 28 mm | 13.7 N m | 38 mm |

A two-wheeled balancer meets a kerb with both wheels at once, so there is no body push to lean on; what it has is
momentum. The full-robot sim (sim/robot_v2.py's balance controller, driving at 0.6 m/s, the kerb scenario of
sim/scenarios.py at 25-100 mm) agrees with the table: **the 10 in wheel passes 25, 30 and 35 mm at 0.6 m/s and 40 mm at 1.2 m/s, and fails
50 mm; the BotWheel passes 25 mm and fails 30 mm at either speed**, the wheel torque pinned at its peak for 1.3 s
before the robot falls forward over the kerb (exports/wheels/curb_*.json, summary_curb.json). The 10 in wheel's radius
buys 15 mm of kerb over today's; the rolling step is a 35-40 mm lip (a door sill, a paving edge, a shallow kerb cut).
A 100-150 mm US kerb is a jump.

### 5.2 By jump

The rig's jump height is the carriage's rise: 167 mm (10 in), 182 mm (8.5 in), 206 mm (BotWheel) at the 60 N m cap
and the 40.5 V start rule; 7-10 mm more uncapped. To land on a step the wheel's bottom must clear the riser by a
margin, and the robot must also travel the tread's 250-280 mm forward in the 0.4 s of flight (0.6-0.7 m/s at
take-off, feasible). Ascento does this with a 10 kg robot and a 0.4 m jump; we are 35 kg.

| Step | 10 in | 8.5 in | BotWheel |
|---|---|---|---|
| 100 mm kerb | 67 mm margin before the tuck: possible with a tuck of 50 mm, no margin for a soft landing | 82 mm | 106 mm: feasible |
| 150 mm kerb | 17 mm: no | 32 mm: no | 56 mm: marginal |
| Stair riser 178-197 mm | no | no | 9-28 mm: no |

### 5.3 Stairs for v1

No. The jump does not clear a riser with any wheel at this mass, each step would be a maximal jump with a landing on
a 250 mm tread, and a miss is a fall down a flight with a 35 kg robot and a foam-ball turret on top. The honest v1
envelope: 25-30 mm lips by rolling, a 100 mm kerb by jump as a later firmware milestone (the BotWheel would do it
today; the 10 in wheel needs the uncapped 120 N m and a fresh pack), and ramps up to the slope scenario's 10 deg.
Stairs want a lighter robot or a leg with more jump, which is a different project (a lighter body without the J501, or
the knee-to-knee spring of research/leg-suspension.md section 8 for energy return).

## 6. Braking and holding

**While powered and balancing**, the wheels are current-controlled and the balance loop holds the robot where it is:
on a 10 deg slope that is 3.8 N m a wheel for a 35.5 kg robot (1.9 N m at 5 deg, 5.7 N m at 15 deg), inside the
motor's 5.2 N m continuous, 27 W of copper loss a motor. The sim's `slope` scenario (10 deg ramp, hold) is re-run with
the new wheel in task W4. Above about 14 deg the hold exceeds the continuous rating and the motors warm: the firmware
sits the robot down after a thermal timer.

**While powered and sitting** (on the skids, legs folded), the VESC can hold the wheels: `handbrake` (a DC current
through the phases locks the rotor to the stator field, like a stepper's detent: holding torque = Kt x current, 5 N m
at 10 A, and it works with halls alone) or its position loop on the hall interpolation. Not needed: with the legs
folded the skids carry the robot and the wheels are unloaded (section 4.2).

**Unpowered:** a short across the phases gives a braking torque proportional to speed, through the phase resistance
and inductance (Kt 0.52, R 0.18 ohm, L 0.34 mH, 15 pole pairs): 3.5 N m at 0.3 m/s, 11 N m at 1 m/s, 21 N m at
2 m/s (28 / 90 / 168 N a wheel). It is a damper that stops a roll-away in a metre; it does not lock. The robot's
answer to a power loss is the sit-down (D55, D39): the legs fold, the skids (TPU 95A, mu 0.6-0.8 on concrete) take
the weight and hold it on any slope the robot can stand on (a 10 deg slope needs mu > 0.18). A passive phase-short on
power loss is cheap if P1 shows the robot rolling during the fold: three 40 A SPDT automotive relays with their NC
contacts tying the phases to a star, or the turret's brake-FET pattern (D47), about $15 a wheel; the plan leaves it
out of v1 and names it as the fix.

**A mechanical or electromagnetic brake is not worth it.** The hoverboard motor has no brake mount and its outer
cover is the rotor, so a disc or drum means the two-sided scooter wheel plus a fork (section 2.2), a cable or
hydraulic caliper, and an actuator to pull it: 0.5-0.8 kg and $100-250 a side for a parking function the skids
already give. An electromagnetic brake needs a shaft that turns, and a hub motor's shaft is fixed. If a holding brake is
ever wanted while powered, the VESC handbrake is free.

## 7. Drivers

| | Flipsky 75100 (today, docs/body-plan.md) | ODrive Pro | ODrive S1 |
|---|---|---|---|
| Bus | 14-84 V: the 30-41 V bus and regen headroom | 12-58 V | 12-50 V |
| Current | 100 A rated; the motor needs 10 A continuous, 30 A for seconds | 120 A peak | 40 A peak |
| Sensors | halls (the HALL port) and an ABI / AS5047 SPI encoder (the ENC port), both at once | halls + incremental or SPI absolute | the same |
| Price | $65 single, $172 dual (both wheels in one box) | $229 each | $149 each, out of stock |
| Interface | CAN at 500 Hz (the body plan's bus C) | CAN | CAN |

Keep the 75100s. Set-up for the hoverboard motor: FOC, 15 pole pairs, hall sensor detection in VESC Tool, hall
interpolation on, motor current max 30 A, absolute max 40 A, battery regen -15 A a wheel (the bus's 60 V fault is far
away at 41 V), a temperature cut-off from the motor's own sensor if it has one (most hoverboard motors do not: add a
10 k NTC on the stator under the cover during W1's teardown and use the VESC's motor temperature input).

**Low-speed balance quality.** Torque control with halls is sound at zero speed: FOC commutates from the hall sector
(60 deg electrical) and the VESC interpolates the angle once the wheel moves; the torque ripple from a 30 deg
electrical angle error at standstill is 13 % and it averages out across a hall transition. The risk is the
**wheel-speed estimate**: 90 hall edges a turn is 4 deg mechanical, so at a balancing creep of 0.05 m/s on a 10 in
wheel (0.4 rad/s) there are 6 edges a second, and the controller's wheel velocity is a staircase. Three fixes, in
order:

1. **Firmware (v1):** the balance loop takes pitch and pitch rate from the VN-100 and uses the wheel speed only in the
   slow outer loop (position and speed tracking); the wheel-speed estimate blends the hall edges with the commanded
   torque through a first-order model (the hoverboard FOC firmware and every hoverboard-motor balancing build do this).
   The simulation's controller (sim/controller_v2.py) is checked with the wheel speed quantised to 4 deg and delayed
   by the VESC's 500 Hz CAN tick (task W5): if it still passes stand, push and drive, this is enough.
2. **An encoder on the rotor cover:** a 6 x 2.5 mm diametric magnet glued at the centre of the rotor's outer cover
   (on a single-shaft hub motor the outer face spins and its centre is free) read by an AS5047P (14-bit, SPI, on the
   75100's ENC port) on a printed arm from the foot, in a shroud; or, inboard and protected, a magnetic ring (a 32-pole
   ring magnet on the inner cover round the shaft) read by an AS5304/AS5311-class off-axis sensor fixed to the foot.
   About $20 a wheel, a 3D-printed bracket, no change to the motor.
3. **ODrive Pro** does not help: the problem is the sensor, not the driver.

Speed: Kv 16 at 41 V is 656 rpm, 8.7 m/s on a 10 in wheel. The firmware's speed limit stays at 2.1 m/s (the sim's
`speed_limit_mps`) and the VESC's own max ERPM is set to 15,000 (1,000 rpm) as a hard ceiling.

## 8. Puddles: ingress protection

| Part | Rating needed | How |
|---|---|---|
| Hub motor | IPX5 (splashed, driven through a 40 mm puddle) | As sold it is IPX4 (Robokits "IP4"). On a 10 in wheel the hub's cover seam is at r 82 mm, 45 mm above a 40 mm puddle; the shaft-side bearing is the exposure. W1's teardown: pack the shaft-side bearing with marine grease, run a bead of neutral-cure silicone round the cover seam, seal the lead exit at the shaft's end with adhesive-lined heat-shrink and a dab of silicone, and fit a vent plug (Gore PMF100 class, $3) in the cover so the sealed hub breathes without pumping water in as it cools. |
| Harness, wheel to belly | IP67 connectors | Phase leads: TE Deutsch DTP 2-way x 2 or a DTP 4-way (25 A contacts, 12 AWG) at the wheel link's exit; halls and NTC: a DT 8-way. The body plan already uses the DT family for the turret. Cable through the wheel link's channel as now, sleeved. |
| VESCs (belly box) | IP54 | The belly plate is their heatsink (body plan); the belly box gets a foam gasket on its lid and the cable glands (PG9/PG11) on its rear face; the button and the charge port are already panel-mount parts; a vent plug in the box. The box must not be sealed tight: the VESCs dump heat into the plate. |
| RS-04 | IP52 (as is) | They sit above the wheel's hub line and inside the hip frames; rain yes, puddles no deeper than 40 mm. |
| Skids, belly | wash-down | The battery bay's door seal is the body workstream's; the FLEXVOLT docks are the pack's own weakness and face up. |

Rule for the manual: puddles to 40 mm (the tyre's lower quarter), no fords; dry the robot before charging.

## 9. What is still unverified, and where it is settled

| Item | Settled by |
|---|---|
| The 10 in motor's mass with the pneumatic tyre (3.53 kg listed), its Kv, phase resistance, no-load speed, pole count | W1: buy two, weigh, drill-test Kv, measure R and L in VESC Tool |
| The shaft's steel and the hub's run-out | W1: hardness check, dial gauge |
| Tyre pressure range and its stiffness at 30, 35, 40 psi | W1 + the leg plan's tyre bench test |
| US seller prices on Amazon/eBay (snippets only) | W1 confirms the live listing before ordering |
| The 8.5 in motor's mass and tyre | W1 if the backup is bought |
| The balance loop on hall-only speed | W5 (quantised-speed sim), then P1 on the bench |

## Sources

- ODrive hoverboard motor guide: https://docs.odriverobotics.com/v/0.5.5/hoverboard.html (15 pole pairs, Kv 16, R 0.18 ohm, L 0.34 mH, 25 A)
- Robokits RKI-9013 10 in 36 V 350 W hub motor: https://robokits.co.in/e-bike/hub-motor/10inch-36v-350w-brushless-bldc-hub-motor-with-tyre-for-e-bike-and-hoverboard (Rs 3,256; shaft Ø16 / 13.5 flat / 76 mm; hub 163 mm; 2.96 kg airless; IP4)
- e-gizmo 10 in 350 W BLDC hub motor, pneumatic: https://www.e-gizmo.net/gizmoshop/index.php?route=product%2Fproduct&product_id=49630 (PHP 999; 10 x 2.125; 3.53 kg; halls)
- Alibaba 10 in hoverboard motor wheel 36 V 350 W: https://www.alibaba.com/product-detail/10-inch-Hoverboard-Motor-Wheel-36V_1600933431463.html [snippet]
- Hover-1 Titan (10 in pneumatic, tubed, 36 V, 265 lb): https://eridehero.com/?p=5576 and https://www.hover-1.com/products/hover-1-titan-hoverboard
- iFixit, Hover-1 Titan wheel and motor replacement: https://www.ifixit.com/Device/Hover-1_Titan
- ATO 10 in hub motor: https://www.ato.com/10-inch-hub-motor ($438.54, 4 kg, IP65, 119 mm dropout, 30 N m)
- Amazon 10 in 36 V 350 W drum-brake wheel kits: https://www.amazon.com/Brushless-Motor-Electric-Scooter-Wheelbarrow/dp/B0GT9RBLTT, https://www.amazon.com/Brushless-Off-Road-Pre-Assembled-Controller-Wheelbarrow/dp/B0GTM5CRMY [snippet]
- esk8.news, 10 in hoverboard hub motors on VESC: https://forum.esk8.news/t/4wd-mountainboard-10-inch-hoverboard-hub-motor-vesc4-trampa-holypro-deck/16307
- DDT M1502D_233: https://www.roboticscenter.ai/store/product/direct-drive-tech-m1502d233-directdrive-motor/ (24 V, Kt 0.88, IP55, 2.3 kg, backorder)
- Unitree Go2-W: https://unitree.com/go2-w (7 in pneumatic)
- Rothhaemel, KTH 2023, bicycle tyre vertical stiffness: https://dapp.orvium.io/deposits/650c004def25b2f0766f520b/view
- Cano-Moreno et al. 2024, e-scooter tyre vertical stiffness, LAAR 54(3): https://www.laar.plapiqui.edu.ar/OJS/index.php/laar/article/view/1069
- VESC handbrake and hall hold threads: https://vesc-project.com/node/180
- The rig and the sweeps: sim/wheel_study.py, cad/wheel_fit.py, exports/wheels/ (this branch)
