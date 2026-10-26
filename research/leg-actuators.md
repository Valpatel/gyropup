# Leg actuators for gyropup: what you can actually buy (checked 2026-10-25)

Quasi-direct-drive (QDD) joint actuators for the hip and knee of an 8–20 kg wheel-legged biped: planetary ~6:1–10:1, integrated driver, CAN or RS485. Machine-readable data: [`catalog/leg_actuators.json`](../catalog/leg_actuators.json) (49 items, category `leg_actuator`). Each item has sources, a STEP link where one exists, and notes. Unknown numbers are `null`; "n/p" below means *not published*.

**How the data was gathered.** Official stores and Shopify product JSON, vendor GitHub repos, manuals and selection guides, Seeed, Amazon, RobotShop, aifitlab, OpenELAB and roboticscenter.ai. Prices are one unit with the driver included, before shipping and tax.

**Caveats.**
- The session's web-search quota ran out partway through, so forum and Reddit reputation was not checked; reputation notes come from GitHub issues, Hackaday and the Arduino forum.
- Some RobotShop prices come only from search snippets. The JSON marks these `confidence: "seller listing"`.
- Vendors often disagree with themselves. RobStride's website, manual and 2026 spec PDF, and Damiao's manual and selection guide, give different numbers in several places. Where they disagree, the JSON uses the newest official figure and puts the conflict in `notes`.
- "Peak" for Steadywin, HighTorque and Westwood is a stall or locked-rotor torque, not a cycle-safe peak.

## How much torque does a 10 kg robot need to squat?

Each leg carries half the weight: F = m·g/2 = 49 N at 10 kg. A serial hip-and-knee leg in a deep squat (thigh horizontal, wheel under the hip) puts F × L_thigh on the knee:

| Robot mass | L_thigh 0.15 m | L_thigh 0.20 m |
|---|---|---|
| 10 kg | 7.4 Nm | 9.8 Nm |
| 15 kg | 11.0 Nm | 14.7 Nm |
| 20 kg | 14.7 Nm | 19.6 Nm |

That torque is **continuous** whenever the robot holds a crouch, so compare it with **rated** torque. Then add about 2–3× of **peak** for balance recovery, standing up fast and small jumps.

The budget cutoff is therefore roughly ≥ 7–8 Nm rated and ≥ 18–20 Nm peak at the knee for 10 kg. A Diablo-style five-bar leg, with both motors at the hip, shares the load between the two motors and roughly halves the per-motor requirement.

## Comparison: sorted by price per peak Nm (cheapest first)

"Output-abs encoder" means the joint angle is known at power-up without homing: "yes" = encoder on the output; "option" = second encoder sold separately; "dual, unclear" = two encoders but the vendor does not say one is on the output.

**Not QDD (listed only because they were requested):** #7 Damiao 4340 (40:1), #13 CubeMars AK80-64 (64:1) and the Unitree IM6014 (12.7:1).

| # | Actuator | Price | $/peak Nm | Peak Nm | Rated Nm | Mass g | Peak Nm/kg | Rated Nm/kg | Ratio | V nom (range) | No-load rpm | Bus | Output-abs encoder | In stock (ships) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | RobStride RS-04 | $255 | 2.1 | 120 | 40 | 1420 | 84.5 | 28.2 | 9 | 48 (15-60) | 200 | CAN | dual, unclear | yes (CN) |
| 2 | Damiao DM-J10010L-2EC | $265 | 2.2 | 120 | 40 | 1375 | 87.3 | 29.1 | 10 | 48 (15-52) | 200 | CAN/CAN-FD | yes | yes |
| 3 | Damiao DM-J10010-2EC | $455 | 3.0 | 150 | 40 | 1485 | 101.0 | 26.9 | 10 | 48 (15-52) | 150 | CAN/CAN-FD | yes | yes |
| 4 | RobStride RS-03 | $225 | 3.8 | 60 | 20 | 880 | 68.2 | 22.7 | 9 | 48 (15-60) | 195 | CAN | dual, unclear | unclear |
| 5 | Steadywin GIM8115-9 + GDM810 (MIT) driver | $214 | 5.3 | 40 | 13 | 705 | 56.7 | 18.4 | 9 | 24 | 129 | CAN | option | yes (CN) |
| 6 | Steadywin GIM10015-9 + GDZ810 | $356 | 5.7 | 62.1 | 30 | 1372 | 45.3 | 21.9 | 9 | n/p | 104 | CAN | no | yes (CN) |
| 7 | Damiao DM-J4340-2EC | $155 | 5.7 | 27 | 9 | 362 | 74.6 | 24.9 | 40 | 24 (15-32) | 52.5 | CAN/CAN-FD | yes | yes |
| 8 | RobStride RS-06 | $210 | 5.8 | 36 | 11 | 621 | 58.0 | 17.7 | 9 | - (15-60) | 480 | CAN | dual, unclear | unclear |
| 9 | Steadywin GIM8108-8 + GDS68 driver | $129 | 5.9 | 22 | 7.5 | 396 | 55.6 | 18.9 | 8 | 48 (12-56) | 320 | CAN | option | yes (CN) |
| 10 | DDT (Direct Drive Tech) P1010A_111 | $699 | 7.8 | 90 | 25 | n/p | n/p | n/p | 10 | 48 (36-60) | n/p | n/p | n/p | no |
| 11 | Unitree IM6014 (N6014B-12.6) | $269 | 7.8 | 34.4 | n/p | 535 | 64.3 | n/p | 12.7 | - (24-75) | 518 | RS485 | yes | yes |
| 12 | RobStride RS-01 | $135 | 7.9 | 17 | 6 | 380 | 44.7 | 15.8 | 7.8 | 36 (24-48) | 315 | CAN | no | yes (US) |
| 13 | CubeMars AK80-64 KV80 | $990 | 8.2 | 120 | 48 | 850 | 141.2 | 56.5 | 64 | 48 (18-52) | 75 | CAN | no | yes (CN) |
| 14 | RobStride RS-02 | $145 | 8.5 | 17 | 6 | 405 | 42.0 | 14.8 | 7.8 | 48 (24-60) | 410 | CAN | dual, unclear | yes (CN) |
| 15 | Steadywin GIM6010-8 + GDS68 driver | $94 | 8.5 | 11 | 5 | 388 | 28.4 | 12.9 | 8 | 24 (12-56) | 420 | CAN | option | yes (CN) |
| 16 | LKMTECH MG8016E-i6 V2 | $330 | 8.9 | 37 | 12 | 759 | 48.7 | 15.8 | 6 | 48 (12-60) | 300 | RS485 or CAN | option | unclear |
| 17 | Damiao DM-J8009P-2EC | $395 | 9.9 | 40 | 20 | 963 | 41.5 | 20.8 | 9 | 48 (15-52) | 335 | CAN/CAN-FD | yes | yes |
| 18 | RobStride RS-00 | $139 | 9.9 | 14 | 5 | 310 | 45.2 | 16.1 | 10 | 48 (24-60) | 315 | CAN | dual, unclear | yes (US) |
| 19 | Damiao DM-J8006-2EC V1.1 | $210 | 10.5 | 20 | 8 | 559 | 35.8 | 14.3 | 6 | 48 (15-52) | 392.8 | CAN/CAN-FD | yes | yes |
| 20 | DDT (Direct Drive Tech) P1010B_111 | $545 | 10.9 | 50 | 20 | 1400 | 35.7 | 14.3 | 10 | 24 (18-36) | n/p | n/p | dual, unclear | yes |
| 21 | Damiao DM-J8009-2EC | $470 | 11.8 | 40 | 20 | 896 | 44.6 | 22.3 | 9 | 48 (15-52) | 335 | CAN/CAN-FD | yes | yes |
| 22 | LKMTECH MG6012E-i8 V2 | $190 | 11.9 | 16 | 6 | 430 | 37.2 | 14.0 | 8 | 48 (12-60) | 310 | RS485 or CAN | option | unclear |
| 23 | LKMTECH MG8015E-i9 V3 | $340 | 12.1 | 28 | 14 | 705 | 39.7 | 19.9 | 9 | 48 (12-60) | 216 | RS485 or CAN | option | unclear |
| 24 | LKMTECH MG8008E-i9 V3 | $260 | 13.0 | 20 | 10 | 570 | 35.1 | 17.5 | 9 | 48 (12-60) | 220 | RS485 or CAN | option | unclear |
| 25 | Damiao DM-J6006-2EC | $150 | 13.6 | 11 | 4 | 335 | 32.8 | 11.9 | 6 | 24 (15-52) | 226 | CAN/CAN-FD | yes | yes |
| 26 | Xiaomi CyberGear micromotor | $179 | 14.9 | 12 | 4 | 317 | 37.9 | 12.6 | 7.8 | 24 | 296 | CAN | no | unclear |
| 27 | Unitree A1 joint motor | $500 | 14.9 | 33.5 | n/p | 605 | 55.4 | n/p | 9.1 | n/p | 200 | RS485 | no | yes |
| 28 | CubeMars AK10-9 V3.0 KV60 | $799 | 15.1 | 53 | 18 | 940 | 56.4 | 19.1 | 9 | 48 (18-52) | 320 | CAN | yes | yes (CN) |
| 29 | DIY (ODrive) OpenQDD V1: Eaglepower 8308 90KV + printed 9:1 planetary + ODrive S1 | $247 | 15.1 | 16.4 | n/p | n/p | n/p | n/p | 9 | - (12-50.5) | n/p | CAN/CAN-FD | no | no |
| 30 | Unitree GO-M8010-6 | $369 | 15.6 | 23.7 | n/p | 530 | 44.7 | n/p | 6.3 | 24 (12-30) | 286 | RS485 | no | yes |
| 31 | HighTorque HTPW-7507-02-DNE | $189 | 15.8 | 12 | 4 | 390 | 30.8 | 10.3 | 7 | n/p | 270 | n/p | n/p | yes |
| 32 | CubeMars AK70-9 V3.0 KV60 | $499 | 17.1 | 29.2 | 8.5 | 540 | 54.1 | 15.7 | 9 | 48 (18-52) | 320 | CAN | yes | yes (CN) |
| 33 | Damiao DM-J4310-2EC V1.1 | $125 | 17.9 | 7 | 3 | 306 | 22.9 | 9.8 | 10 | 24 (15-32) | 200 | CAN/CAN-FD | yes | yes |
| 34 | MyActuator RMD-X8-P9-25 (X8-Pro 1:9 V2) | $470 | 18.8 | 25 | 10 | 710 | 35.2 | 14.1 | 9 | 48 | 254 | CAN or RS485 | no | no |
| 35 | CubeMars AK70-10 KV100 | $499 | 20.1 | 24.8 | 8.3 | 621 | 39.9 | 13.4 | 10 | 48 (18-52) | 480 | CAN | no | yes (CN) |
| 36 | MyActuator RMD-X8-P6-20 (X8-Pro-H 1:6 V3) | $425 | 21.2 | 20 | 10 | 780 | 25.6 | 12.8 | 6 | 48 | 220 | CAN or RS485 | dual, unclear | yes |
| 37 | Westwood Robotics Panda BEAR Plus PB02P | $1459 | 21.8 | 67 | 23 | 925 | 72.4 | 24.9 | 6 | - (9-48) | n/p | RS485 | n/p | no |
| 38 | CubeMars AK80-8 KV60 | $570 | 22.8 | 25 | 10 | 570 | 43.9 | 17.5 | 8 | 48 (18-52) | 360 | CAN | yes | yes (CN) |
| 39 | MyActuator RMD-X8-P9-32-R (X8 Pro V4) | $799 | 25.0 | 32 | 8 | 550 | 58.2 | 14.5 | 9 | 24 | 277 | RS485 | no | yes (US) |
| 40 | CubeMars AK80-9 V3.0 KV100 | $580 | 26.4 | 22 | 9 | 490 | 44.9 | 18.4 | 9 | 48 (18-52) | 570 | CAN | no | yes (CN) |
| 41 | CubeMars AK60-6 V3.0 KV80 | $299 | 33.2 | 9 | 3 | 380 | 23.7 | 7.9 | 6 | 48 (18-52) | 640 | CAN | no | yes (CN) |
| 42 | CubeMars AK60-6 V1.1 KV140 | $299 | 33.2 | 9 | 3 | 368 | 24.5 | 8.2 | 6 | 24 (18-28) | 560 | CAN | no | yes (CN) |
| 43 | MyActuator RMD-X6-P8-8 (X6 V3 1:8) | $275 | 34.4 | 8 | 4.5 | 490 | 16.3 | 9.2 | 8 | 48 | 387 | CAN or RS485 | dual, unclear | yes |
| 44 | Westwood Robotics Panda BEAR PB02 | $1189 | 35.5 | 33.5 | 11.8 | 685 | 48.9 | 17.2 | 6 | - (9-48) | n/p | RS485 | n/p | yes |
| 45 | CubeMars AK80-6 KV100 | $570 | 47.5 | 12 | 6 | 485 | 24.7 | 12.4 | 6 | 48 (18-52) | 800 | CAN | no | yes (CN) |
| 46 | mjbots qdd100 beta 3 | $879 | 54.9 | 16 | 3.3 | 507 | 31.6 | 6.5 | 6 | - (10-44) | 600 | CAN-FD | n/p | no |
| 47 | MyActuator RMD-X10-P7-40 (X10 V3 1:7) | n/p | n/p | 40 | 15 | 1150 | 34.8 | 13.0 | 7 | 48 | 186 | CAN or RS485 | dual, unclear | yes |
| 48 | DIY (mjbots moteus) moteus-n1 + 8308 motor + mjbots M0.5 6x steel planetary | $277 | n/p | n/p | n/p | n/p | n/p | n/p | 6 | - (10-54) | n/p | CAN-FD | option | yes |
| 49 | DIY (Berkeley Humanoid Lite) 6512 actuator: MAD M6C12 150KV + B-G431B-ESC1 + printed cycloidal | $189 | n/p | n/p | n/p | n/p | n/p | n/p | n/p | n/p | n/p | CAN | no | yes |

**Readings from the table.**
- Cheapest per Nm are the big 9–10:1 units: RobStride RS-04 and RS-03, and Damiao DM-J10010L. But at 0.9–1.4 kg each they add 3.5–5.5 kg to the legs. Use them only if the robot ends up near 20 kg.
- Best in the sub-650 g class, ranked by peak Nm per kg and price: Steadywin GIM8108-8 (55.6 Nm/kg, $129), RobStride RS-06 (58 Nm/kg, $210), CubeMars AK70-9 V3 (54 Nm/kg, $499).
- Avoid for this robot:
  - CubeMars AK80-6 / AK60-6 and MyActuator X6-8: too little torque per dollar.
  - mjbots qdd100: not stocked, minimum order 50.
  - CubeMars AK80-64 and Damiao 4340: not backdrivable enough.
  - Xiaomi CyberGear: end of life.
  - Unitree A1: legacy, conflicting specs.
  - DDT P1010: reseller only, interface not published.

## Recommendations

### Budget: cheapest that can still squat a 10 kg robot
**Steadywin GIM8108-8 with GDS68 driver: $129.20** (or **$140.95 with the 2nd encoder**; buy that version so you don't need homing).
- 22 Nm stall, 7.5 Nm rated, 396 g, 8:1, 320 rpm no-load at 48 V, 12–56 V, CAN, MIT mode. Four leg joints ≈ $520–565.
- Meets the 10 kg squat with 0.15 m links, but is marginal at 0.20 m.
- Downsides:
  - Ships from China, 7–20 business days.
  - Steadywin is phasing out the GDS and GDZ drivers.
  - Known tooling problems: enabling CAN disables USB, calibration has to be redone after firmware updates, and the CAN cable ships with H and L swapped.
  - Specs conflict between sellers.
- https://steadywin.cn/en/h-pd-133.html; issue log: https://github.com/farouk15160/gim8108-quadruped

**Easiest-to-buy alternative: RobStride RS-01 at $135 on Amazon (US, Prime) or RS-02 at $145 from Seeed.**
- 17 Nm peak, 6 Nm rated, 380–405 g, 7.75:1.
- Good docs, STEP files and Python/ROS 2 samples.
- Enough for an 8–10 kg robot with ≤ 0.15 m thighs or a five-bar leg. Not enough for deep squats at 10 kg with 0.20 m links.
- The RS-01 has only a motor-side encoder, so it needs homing.
- https://www.amazon.com/dp/B0H2GMCH1Z, https://www.seeedstudio.com/Robostride-02-Actuator-p-6665.html

### Balanced: best value across the whole 8–20 kg range
**RobStride RS-03: $225** (Seeed; also roboticscenter.ai $245).
- 60 Nm peak, 20 Nm rated, 880 g, 9:1, 195 rpm, 15–60 V, CAN 1M with MIT mode, IP52.
- Covers a 20 kg robot with margin for jumping. At $3.75 per peak Nm it is one of the cheapest on the market.
- RobStride publishes torque-speed points (copied into the RS-03 `notes` in the JSON), which is very useful for Isaac Lab actuator models. STEP: https://github.com/RobStride/Product_Information
- Stock: back-ordered at Seeed right now, with 47 units due 2026-11-20. Order early.
- For a lighter build (≤ 12 kg) that needs fast legs, the **RobStride RS-06** ($210, 36 / 11 Nm, 621 g, 480 rpm) is the better knee.

**In-stock alternative with output-absolute encoders and CAN-FD: Damiao DM-J8009P-2EC ($395, aifitlab; 40 / 20 Nm, 963 g).**
- The cheaper **DM-J8006-2EC** ($210; 20 / 8 Nm, 559 g, 6:1) is enough for ≤ 12 kg.
- Damiao publishes torque-speed and thermal curves for each model (under `test-data/` in its repos) and an open-source wheel-legged reference robot that uses these motors: https://github.com/dmBots/wheel-legged
- Damiao's 15–52 V range runs the same motor on a 24 V or a 48 V bus.

### Premium: best-supported and lightest per Nm, cost secondary
**CubeMars AK70-9 V3.0: $498.90** (official store, with driver) for ≤ 12 kg.
- 29.2 Nm peak, 8.5 Nm rated, 540 g, 9:1, 320 rpm.
- Dual 21-bit encoders, one on the output, so no homing.
- MIT mode over CAN 1M. STEP and X_T: https://www.cubemars.com/data/cms/202608/ak70-9-v3-0-robotic-actuator-3d-drawing.zip

**CubeMars AK10-9 V3.0: $798.90** for 15–20 kg.
- 53 Nm peak, 18 Nm rated, 940 g. Has an output encoder.

**Caveats for both:**
- Ships from China by UPS/DHL in 7–15 days.
- The V3 MIT-mode CAN frame is incompatible with the V2 frame used by the AK70-10, AK80-8 and AK80-6 and by older libraries. Don't mix versions on one bus.
- Torque-speed curves are images only.

**US-stocked premium alternative:** Westwood Panda BEAR PB02 ($1,189; 6:1, 33.5 Nm stall, 685 g). It is RS485 only, and MIT-mode support is not published.

## Voltage: pairing legs with wheel motors

| Bus | Common wheel motors | Leg actuators that run natively | Leg actuators that run, but slower |
|---|---|---|---|
| **24 V** (6S Li-ion, 25.2 V full) | DDT M1502E hub (24 V, 12–36 V, CAN, $359); ODrive BotWheel (24 V); Unitree GO-M8010-6 (24 V, 30 V abs max) | Damiao 4310/4340/6006 24 V versions; CubeMars AK60-6 V1.1 (18–28 V); RobStride RS-01 (24–48 V, 36 V nominal); Steadywin GIM6010-8 / GIM8115-9 (24 V windings); MyActuator X8-32 (24 V); DDT P1010B (18–36 V); Unitree GO-M8010-6 | Every 48 V-nominal unit with a range down to 15–18 V (Damiao 8006/8009/10010L, RobStride RS-02/03/04/06, CubeMars V3, Steadywin GIM8108-8): about half the no-load speed. Example: DM-J8009 runs 168 rpm at 24 V vs 335 rpm at 48 V. |
| **48 V class** (10S–12S) | RobStride RS-02 or Steadywin GIM8108-8 as wheels; ODrive M8325s + Pro; hoverboard hubs (36 V, 10S) | RobStride (15/24–60 V), Damiao 8006/8009/10010 (15–52 V), CubeMars (18–52 V), Steadywin GIM8108-8 (12–56 V), LKMTECH (12–60 V), DDT P1010A (36–60 V, will **not** run at 24 V) | n/a |

**Recommendation:** run one bus.
- **Damiao** and **RobStride** joints run on either bus, so the choice can wait.
- On a **24 V bus** (needed for the DDT M1502E hub or a Unitree GO-M8010-6 wheel), Damiao or Steadywin joints are the better match. Expect about half the joint speed from 48 V-nominal units.
- On a **48 V-class bus**, use **10S (42 V full) or 11S (46.2 V full)**, not 12S:
  - CubeMars and Damiao have a 52 V maximum. A 12S pack at 50.4 V leaves under 2 V of headroom for regenerative braking from the legs.
  - RobStride's 60 V maximum is the only one comfortable at 12S.
- Unitree GO-M8010-6 has a 30 V absolute maximum, so never use more than 6S with it.

## Simulation notes (Isaac Sim / Isaac Lab)
- For an `ImplicitActuator` or `DCMotor` model you need peak torque (saturation effort), no-load speed (velocity limit), rated torque (effort limit) and **armature**: reflected rotor inertia, rotor inertia × ratio².
- **No vendor here publishes rotor inertia.** RobStride was asked directly and has not answered (https://github.com/RobStride/Product_Information/issues/2). Identify it on a test stand, or estimate it from the STEP file.
- **Torque-speed data, best to worst:**

| Vendor | What is published | Where |
|---|---|---|
| RobStride | Numeric curve points | `notes` in the JSON; https://github.com/RobStride/Product_Information (2026 spec PDF) |
| Damiao | PNG curves at 24 V and 48 V, plus thermal curves | `test-data/` in each https://github.com/dmBots model repo |
| MyActuator | Tables in the manuals | https://www.myactuator.com/downloads-xseries |
| CubeMars | Chart images, 48 V | Linked in each item's `sources` |
| LKMTECH | Curve on the drawing PDF | Drawing PDF |
| mjbots moteus | Thermal and torque modelling tool | https://mjbots.github.io/moteus/mpat.html |

- **MIT-mode gain scaling differs by vendor:**
  - Unitree applies kp/kd on the rotor side. Divide output-side gains by ratio² (GO-M8010-6: 6.33² ≈ 40).
  - Damiao, RobStride, CubeMars and MyActuator use output-side gains.

## Considered and excluded
- **Too small for a leg joint:** RobStride RS-05 ($110, 5.5 Nm) and EduLite 05 ($80, 6 Nm); MyActuator X4-3.
- **Not QDD (ratio far above 10:1):**
  - MyActuator X4-36 (36:1), X6-60 (19.6:1), X8-120/150 (20:1), X10-200 and X12-320.
  - HighTorque HTDW series (22–36:1).
  - Damiao DM-J8520P (20:1) and DM-J6216L (16:1).
  - ENCOS: all models ≥ 11.4:1 and ≥ $700.
- **Not actuators, or not sold as joints:**
  - DDT sells hub motors only. Its P10 joint collection on shop.directdrive.com is empty; P1010A/B are available only through aifitlab.
  - MAD Components sells bare motors only.
  - ODrive S1/Pro/Micro and moteus r4.11/c1/n1/x1 are drivers. They belong in `motor_driver`; the DIY entries here use them.
- **No price found:** MyActuator X10-40 has no US listing; RobotShop CA and EU list it at CAD 865 and EUR 765.

## Key sources
- **CubeMars**
  - Store: https://www.cubemars.com/category-122-AK+Series+Robotic+Actuation+Module.html
  - Downloads: https://www.cubemars.com/technical-support-and-software-download.html
  - V3 manual: https://www.cubemars.com/data/cms/202610/ak-series-motor-module-v3-driver-software-user-manual-en.pdf
  - Community issues: https://github.com/neurobionics/TMotorCANControl/issues
- **RobStride**
  - Specs and STEP: https://github.com/RobStride/Product_Information
  - SDK: https://github.com/RobStride/Python_Sample
  - Seeed: https://www.seeedstudio.com/Robostride-01-Actuator-p-6773.html
- **Damiao**
  - 2026 selection guide: https://github.com/dmBots/dmBot/blob/master/2026-Damiao%20Technology-%20Selection%20Guide-2026-09-23.pdf
  - Repos: https://github.com/dmBots
  - aifitlab: https://aifitlab.com/collections/damiao
  - OpenELAB: https://openelab.io/collections/damiao-motor
- **MyActuator**
  - Downloads: https://www.myactuator.com/downloads-xseries
  - US store: https://myactuator.us/products/rmd-x-series
  - SDK issues: https://github.com/2b-t/myactuator_rmd/issues
- **Steadywin**
  - GIM6010-8: https://steadywin.cn/en/h-pd-116.html
  - GIM8108-8: https://steadywin.cn/en/h-pd-133.html
  - Comparison test: https://hackaday.io/project/202366-the-unnamed-spider-bot/log/239239-steadywin-gim6010-8-vs-xiaomi-cybergear-micromotor
- **Unitree**
  - GO-M8010-6: https://www.unitree.com/mobile/go1/motor/
  - IM6014: https://www.unitree.com/mobile/IM6014
  - SDK: https://github.com/unitreerobotics/unitree_actuator_sdk
- **mjbots / ODrive / DIY**
  - mjbots: https://mjbots.com/products/qdd100-beta-3, https://github.com/mjbots/moteus
  - ODrive: https://docs.odriverobotics.com/v/latest/hardware/s1-datasheet.html
  - OpenQDD: https://github.com/aaedmusa/OpenQDD-V1
  - Berkeley Humanoid Lite: https://arxiv.org/abs/2504.17249
- **Others**
  - Westwood: https://store.westwoodrobotics.io/
  - LKMTECH (via aifitlab): https://aifitlab.com/products/lkmtech-mg8016e-i6-v2-motor
  - DDT: https://shop.directdrive.com
  - HighTorque: https://store.hightorque.cn/
