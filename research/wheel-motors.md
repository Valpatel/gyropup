# Wheel / hub motors for gyropup

Checked 2026-10-25. Data lives in `catalog/wheel_motors.json` (27 items) and `catalog/motor_drivers.json` (19 items).
Prices are single-unit list prices before shipping and tax. "n/p" means not published. Foreign-currency prices are left unconverted.

## How the numbers were computed

- **Top speed** (km/h) = no-load rpm × π × wheel OD × 60 / 10⁶, at the voltage listed.
- **Peak ground force** (N) = peak torque / wheel radius. **Rated ground force** uses rated torque.
- **Wheel OD:**
  - For motors sold with a tyre, the published OD is used.
  - For bare motors and motors with an unpublished OD, a **170 mm wheel is assumed**, marked `*` in the tables.
  - These are flagged in JSON as `calc_wheel_diameter_assumed`.
- **Derived inputs:** a few inputs are derived rather than published, and are flagged in the JSON notes.
  - BotWheel peak torque = 15 A × Kt; no-load speed = Kv × 24 V.
  - Hoverboard no-load speed = measured Kv × 36 V.

### What gyropup needs from each wheel

These are my working assumptions, not sourced figures.

- **Friction ceiling.** A balancing robot can't push the ground harder than tyre friction allows: F ≈ μ·m·g / 2 per wheel. With μ ≈ 0.8:
  - 8 kg robot: about 31 N per wheel
  - 15 kg: about 59 N
  - 20 kg: about 78 N
- **Peak target.** Peak ground force of about 80 N or more per wheel means the motor never limits recovery before the tyre slips.
- **Continuous target.** Continuous force of about 30–60 N per wheel covers ramps (10° at 20 kg ≈ 17 N per wheel) and sustained acceleration.
- **Speed target.** No-load speed well above cruise speed. A balancer must out-run its own fall, so 6 km/h or more is a sensible floor.

## Comparison table: candidates that fit 8–20 kg

| Motor | Price (seller) | Stock | Mass / wheel | OD × width (mm) | Rated / peak Nm | No-load rpm @ V | Top speed km/h | Peak / rated ground N | Encoder | Driver | STEP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **DDT M1502D_233** | ¥60,500 (Switch Science JP); aifitlab $509 n/a | in stock (L & R) | 2.30 kg | 187 × 52 | 9.6 / ≥17 | ≥200 @24 | 7.1 | 182 / 103 | 16384 cpr, abs-zero cmd | integrated, CAN 1 Mbps, 1 kHz report | [yes](https://doc.switch-science.com/media/files/b4a814ea-b135-40a2-9451-ba1ee063797b.step) |
| **Damiao DM-H65-1EC** | $222 bare / $326 + driver (rcdrone, CN) | available | 3.15 kg | 171 × 66.3 | 6.0 / 21.5 | 260 @24 (480 @48) | 8.4 (15.5 @48) | 252 / 70 | 17-bit | DM6540-1EC, CAN-FD 5 Mbps | [yes](https://cdn.shopify.com/s/files/1/0673/6848/5000/files/DAMIAO_DM_H65_1EC.STEP) |
| **ODrive BotWheel** | $269 per 2-pack (ODrive shop) | 2-pack in stock | 2.20 kg | 171 × 44.6 | 5 / 14.3 (derived) | 209 @24 (derived) | 6.7 | 167 / 59 | hall + 3200 CPR incremental | external: S1 / Pro / moteus n1 | [Onshape](https://cad.onshape.com/publications/ffa16d9268e83ffcb5643cba/w/81f7a79746984b3bebf1d392/e/3101f331226b74a504e702ae) |
| DDT M1505A_222 | $325 (aifitlab) | backorder | 1.54 kg | 180 × 33 | 3 / ≥7.5 | 250 @24 | 8.5 | 83 / 33 | 15-bit | integrated, CAN | 2D only |
| ZLTECH ZLLG65-ASM250 V3 | $115 bare; 2 motors + ZLAC8015D $390 (aifitlab) | available | 2.95 kg | 170 × n/p | 4 / 12 | n/p (rated 500 @24) | 16.0 (at rated rpm) | 141 / 47 | 4096-line | ZLAC8015D | n/p |
| UUmotor SVH6HS 6.5" | $145 (UUmotor) | n/p | 3.40 kg | 168 × n/p | 5 / 10 | n/p (rated 400–500) | 15.8 (at rated rpm) | 119 / 60 | 1024-line optical | external | n/p |
| Hoverboard 6.5" (generic) | $75 (Amazon B0CCV76FCM) | 20 left | ~3.0 kg | 165 (nominal) × n/p | n/p | 576 @36 (Kv 16, measured) | 17.9 | n/p (≈126 N at 20 A, derived) | **hall only, 90 cpr** | external | none |
| Hoverboard 8" (generic) | $49.56–55.49 (Amazon) | 7–17 left | 2.5–3.6 kg | 200 × 50 | n/p | n/p | n/p | n/p | hall | external | none |
| CubeMars GL100 KV10 | $272.99 (CubeMars) | available* | 0.70 kg + wheel | motor 106.8 × 34.2 | 3 / 7.7 | 223 @24 | 7.2* | 91* / 35* | none (add one) | external | [yes](https://www.cubemars.com/data/cms/202602/gl100-gimbal-motor-3d-drawing.zip) |
| MAB MA-D GL100 | €527.30 (MAB, PL) | in stock | 0.75 kg + wheel | motor 106.8 × 47.2 | 3 / 7.7 | 260 max @48 | 8.3* | 91* / 35* | 14-bit absolute | integrated MD80, CAN-FD | page says yes |
| MyActuator RMD-L-9025 | $279 (rcdrone) | available | 0.88 kg + wheel | n/p | 2.79 / 5.8 | 280 max @24 | 9.0* | 68* / 33* | 14-bit (listing inconsistent) | integrated, CAN or RS485 | downloads page |
| Damiao DM-J6006-2EC (6:1) | $150 (rcdrone) | available | 0.34 kg + wheel | motor Ø76 × 36.5 | 4 / 12 | 240 @24 | 7.7* | 141* / 47* | dual 14-bit | integrated, CAN | drawing only |
| Robstride RS00 (10:1) | $159 (rcdrone) | available | 0.31 kg + wheel | 57 × 51 | 5 / 14 | 315 @48 | 10.1* | 165* / 59* | dual 14-bit | integrated, CAN | n/p |
| Robstride RS02 (7.75:1) | $189 (rcdrone) | available | 0.41 kg + wheel | 78.5 × 45.5 | 6 / 17 | 410 @48 | 13.1* | 200* / 71* | dual 14-bit | integrated, CAN | n/p |
| Unitree GO-M8010-6 (6.33:1) | $369 (Unitree shop) | available | 0.53 kg + wheel | 96.5 × 42.3 | n/p / 23.7 | 286 @24 | 9.2* | 279* / n/p | 15-bit | integrated, RS485 4 Mbps | n/p |

Notes on the table:
- `*` means computed at an assumed 170 mm wheel. For CubeMars, "available" is the store JSON flag; the rendered page showed some items sold out, so confirm before ordering.

## Too small for 8–20 kg, but cheap and useful for a desk-scale controller prototype

| Motor | Price (seller) | Mass | OD | Rated / peak Nm | No-load rpm | Top speed | Peak ground N | Encoder / bus |
|---|---|---|---|---|---|---|---|---|
| Waveshare DDSM115 (= DDT M0601C_411 = DFRobot M0601) | $64.99 (Waveshare); $64.50 (DFRobot); $83.65 backorder (RobotShop) | 765 g | 100.7 | 0.96 / 2.0 | 200 @18 V | 3.8 | 40 | 12-bit, RS485, integrated |
| Waveshare DDSM350-CT | $109.99 (Waveshare) | 1286 g | n/p | 1.1 / 3.0 | 350 @24 | 11.2* | 35* | 12-bit, CAN + UART |
| Waveshare DDSM315 (= DDT M0602C_112) | $49.99 | 349 g | n/p | 0.55 / 1.1 | 315 | 10.1* | 13* | 12-bit, RS485 |
| Waveshare DDSM210 (= DDT M0603B_224) | $23.99 | 260 g | 74.5 | 0.25 / 0.85 | 210 @14.4 | 3.0 | 23 | 12-bit, UART |
| Waveshare DDSM400 | $25.99 | 236 g | n/p | 0.15 / 0.3 | 400 @25.2 | 12.8* | 3.5* | 12-bit, LIN (STEP file is a DDSM210 duplicate) |
| Damiao DM-H6215 | $60 (rcdrone) | 360 g | motor 68 | 1 / 2 | 320 @24 | 10.3* | 24* | hall, CAN |
| Damiao DM-G6220 | $109 | 494 g | motor 68 | 1.3 / 2.7 | 300 @24 | 9.6* | 32* | magnetic (n/p), CAN |
| CubeMars GL80 KV30 | $181.99 | 312 g | motor 87 | 1 / 2.9 | 650 @24 | 20.8* | 34* | none |
| iFlight iPower GM110-10 | $174.79 ($273.04 w/ AS5048A) | 532 g | motor 110 | n/p / ~0.9–1.5 load | 292–323 @20 | 9.4* | 17* | optional 14-bit |
| mjbots mj5208 (Upkie wheel) | $74; r4.11 dev kit $239 (mjbots) | 193 g | 112 (Upkie RC tyre) | n/p / 1.7 | 7500 max | — | 30 | moteus on-axis encoder |

**Not sold or not suitable:**
- **Unitree:** does not sell the Go2-W or B2-W in-wheel motor separately ([Go2-W](https://www.unitree.com/go2-w)).
- **CubeMars:** no hub motor and no 1:1 AK model.
- **MyActuator:** has no hub motor. The L-12025 is not on myactuator.com.
- **Robstride:** has no 1:1 model.
- **T-Motor GB gimbal motors:** publish no usable torque figure.

## Balancing-relevant trade-offs

### 1. Encoder resolution decides low-speed control quality

What matters is how often the wheel-velocity estimate updates when the robot is nearly still. Counts per second at a 5 cm/s creep:

| Feedback | Counts/rev | Wheel OD | Counts/s at 5 cm/s | Time between counts |
|---|---|---|---|---|
| Hoverboard halls | 90 | 165 mm | 8.7 | ~115 ms |
| BotWheel encoder | 3200 | 171 mm | 298 | 3.4 ms |
| DDSM115 | 4096 | 100.7 mm | 647 | 1.5 ms |
| DDT M1502D_233 | 16384 | 187 mm | 1394 | 0.7 ms |
| 14-bit on a 170 mm wheel (GL100 + MA600/AS5047, MA-D, RS0x, L-9025) | 16384 | 170 mm | 1534 | 0.65 ms |
| DM-H65-1EC | 131072 | 171 mm | ~12 200 | 0.08 ms |

**Hall-only hoverboard motors are a poor fit for balancing as bought.**
- A velocity estimate that updates every ~115 ms is far too slow for a 200 Hz+ balance loop near zero speed.
- mjbots says halls have "very poor low velocity performance" ([moteus hall guide](https://github.com/mjbots/moteus/blob/main/docs/guides/hall-effects.md)).
- ODrive's hoverboard guide has to lower the encoder bandwidth to smooth the velocity estimate ([ODrive hoverboard.rst](https://raw.githubusercontent.com/odriverobotics/ODrive/master/docs/hoverboard.rst)).
- **Fix:** add an off-axis encoder (AS5047P / MA600 on a printed bracket bolted to the rotor end-cap) ([ODrive forum](https://discourse.odriverobotics.com/t/hoverboard-encoder-for-self-balancing-robot/3061)).

**Watch-outs for the integrated motors:**
- **DDSM115:** reports speed in whole rpm. At a 100.7 mm wheel, 1 rpm is 1.7 cm/s. So differentiate position yourself rather than using the speed field. Its RS485 bus is also a 115200-baud query/reply link ([Waveshare wiki](https://www.waveshare.com/wiki/DDSM115)).
- **M1502D:** pushes 1 kHz feedback over CAN ([datasheet](https://doc.switch-science.com/media/files/af909b0e-e7b2-429f-b8f5-f31c04ee66ca.pdf)).
- **DM-H65:** runs CAN-FD at 5 Mbps ([manual](https://cdn.shopify.com/s/files/1/0673/6848/5000/files/DM-H65-1EC_User_Manual-1-3.pdf?v=1767977091)).

### 2. Cogging and torque ripple

**No vendor in this list publishes cogging torque.** What can be said qualitatively:
- **Hoverboard motors:** iron-core, 15 pole pairs, cheap laminations. Builders report noticeable detent. Windings also vary by factory, so buy all units from one seller ([Project HoverArm](https://discourse.odriverobotics.com/t/project-hoverarm/441)).
- **Gimbal motors (GL100, iPower GM):** wound for low cogging but at the cost of torque per amp-heat.
- **Integrated FOC hubs (DDT, Damiao, ZLTECH):** usually ship with some compensation, but none publish it.
- **moteus:** has a documented cogging-compensation calibration you can run on any motor.

**Plan to measure ripple** on a bench (sweep position at constant current) before building a sim model. In Isaac Lab, add the ripple as a position-dependent torque disturbance.

### 3. Torque at stall

Balancing is mostly done near zero speed. So the useful number is **continuous stall torque**, which is limited by winding heat, not peak.
- **Datasheet "stall" or "peak" figures:**
  - M1502D: ≥17 Nm at ≤21 A.
  - DM-H65: 21.5 Nm.
  - BotWheel: 15 A for 3 s, which caps it at ~14 Nm for a short burst only.
- **Rated torque is the better sizing number.**
  - **10–20 kg gyropup:** 3 Nm on a ~170 mm wheel gives ~35 N, which is the minimum. The M1502D (9.6), DM-H65 (6.0) and BotWheel (5) clear it comfortably.
  - **≤10 kg gyropup:** the GL100 (3) and DM-J6006 (4) are adequate.
  - **Below the line:** DDSM115 (0.96 Nm, 19 N) only suits a ≤8 kg proof of concept.
- **Hoverboard motors:** with Kt ≈ 0.52 Nm/A (ODrive's 8.27/Kv rule, measured Kv 16), a 20 A driver limit gives ~10 Nm (derived, ignoring saturation). They are thermally large, but nobody publishes a rating.

### 4. Mass at the end of the leg (unsprung mass)

The hub sits at the foot, so its mass raises leg inertia (∝ m·L²) and the torque the knee and hip must supply. It also raises the share of robot mass that isn't the controllable body.

| Option | Pair mass | Share of a 15 kg robot |
|---|---|---|
| Hoverboard 6.5" (ODrive forum measurement: 3146 g each) | 6.3 kg | 42% |
| DM-H65-1EC | 6.3 kg | 42% |
| ZLTECH V3 | 5.9 kg | 39% |
| DDT M1502D | 4.6 kg | 31% |
| BotWheel | 4.4 kg | 29% |
| DDT M1505A | 3.1 kg | 21% |
| DDSM115 | 1.5 kg | 10% |
| GL100 / MA-D GL100 + printed wheel | ~1.4–1.5 kg + wheel/tyre (n/p) | ~10–12% |
| DM-J6006 / RS00 / RS02 (geared) + wheel | 0.6–0.8 kg + wheel | ~5% |

**The geared motors are lightest** (DM-J6006, Robstride RS00/RS02). Their trade-offs:
- gearbox backlash
- reflected rotor inertia
- poorer back-drivability on impact

Direct drive avoids these. For an RL sim, model the backlash explicitly if you choose them.

### 5. Practical

**Axles:**
- Every integrated hub here is **single-sided**: a fixed stator flange or boss, with the cable through the centre. That suits a cantilevered leg-end.
  - DDT M15: 6× M6 on a Ø40 circle.
  - BotWheel: 4× M6 on a Ø36 circle.
  - DDSM115: 3× M2.5 boss.
- **Hoverboard motors** have a single-sided threaded axle with the cable through it.
- **GL100 and other gimbal motors** need you to design the bearing, axle and tyre.

**Tyres:**
- **Solid rubber or patterned tread:** DDT, DDSM, BotWheel, ZLTECH, hoverboard 6.5". Solid rubber is easier to model in Isaac.
- **Pneumatic:** 10" hoverboard motors (10×2.125). Pneumatic adds spring and damping that the policy then has to learn around.

**Bus to the Jetson:**
- **CAN-FD:** moteus, Damiao, MAB.
- **CAN 2.0:** DDT M15, ODrive, Robstride, MyActuator.
- **RS485 or UART:** DDSM, Unitree. These add a USB adapter and a polling bottleneck.

## Drivers for non-integrated motors

| Driver | Price (seller) | Stock | V range | Cont. / peak A | Interface | Encoder support |
|---|---|---|---|---|---|---|
| moteus n1 | $149 (mjbots, US) | in stock | 10–54 | 9 (26 cooled) / 100 | CAN-FD 5 Mbps | onboard on-axis; ext. hall, quadrature, SPI (AS5047, MA600…), RS422, BiSS-C |
| moteus c1 | $69 (mjbots) | in stock | 10–51 | 5 (14 cooled) / 20 | CAN-FD | onboard; ext. SPI, quadrature, hall, I2C |
| moteus r4.11 | $94 (mjbots) | in stock | 10–44 | 12 (32 cooled) / 100 | CAN-FD | onboard; ext. SPI and I2C/UART only |
| moteus x1 | $175 (mjbots) | in stock | 10–54 | 25 (62 cooled) / 120 | CAN-FD | as n1 |
| ODrive S1 | $149 (ODrive) | **out of stock** | 12–48 (50.5 max) | 20 (40 w/ spreader) / 40–80 | CAN 2.0B 1 Mbps, USB, UART, step/dir | onboard MA702; ext. quadrature, hall, SPI, RS485 |
| ODrive Pro | $229 (ODrive) | in stock | 15–58 | 20 (80 cooled) / 100 for 3 s | CAN | ext. SSI, BiSS, RS422-SPI, ABZ, hall |
| ODrive Micro | $89 (ODrive) | in stock | 10–31 | 3.5 / 7 | CAN 2.0B | onboard MA702 12-bit; ext. quad, hall, SPI |
| Trampa VESC 6 MkVI | £185 ex VAT ≈ $249.75 shown (Trampa, UK) | in stock | 11.1–60 | 80 / 120 | USB, CAN, UART, SPI, I2C | ABI, hall, AS5047 |
| Flipsky Mini FSESC6.7 Pro 70A | $57 (Flipsky, CN) | in stock | 14–60 | 70 / 200 | USB, CAN, UART | ABI, hall, AS5047, AS5048A |
| Flipsky FSESC 6.7 Pro | $94 | in stock | 8–60 | 60 / 150 | USB, CAN, UART, BT | ABI, hall, AS5047 |
| Flipsky 75100 | $65 | in stock | 14–84 | 100 / 120 | USB, CAN, UART | ABI, hall, AS5047, AS5048A |
| Flipsky Dual FSESC6.7 Plus | $153 | in stock | 8–60 | "100 / 400" per channel (implausible claim) | USB, CAN | ABI, hall, AS5047 |
| Flipsky ODESC3.6 dual (ODrive 3.6 clone) | $59.99 | in stock | 8–56 | 50 / 120 | USB, UART, CAN, step/dir | incremental, absolute, hall, AS5047 |
| Hoverboard mainboard + [EFeru FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC) | no reliable price (salvage) | — | n/p | n/p | UART / PWM / PPM, **no CAN** | motor halls only |

**Notes on the drivers:**
- **CAN-FD to the Jetson:** mjbots mjcanfd-usb-1x, $39 ([link](https://mjbots.com/products/mjcanfd-usb-1x)). The ODrive USB-CAN adapter is CAN 2.0 only, $37.
- **Ruled out at 12S (48 V):** moteus r4.11 and ODrive Micro.
- **Bus adapters, not drivers:** Waveshare DDSM Driver HAT (A) and (B), $21.99 each, are ESP32 bus adapters for the DDSM motors, which have their own drivers built in.
- **VESC limitation:** VESC firmware is built for vehicles. Balance-loop timing over CAN is fine, but torque-mode latency and the API are less robot-friendly than moteus or ODrive.
- **Flipsky firmware warning:** Flipsky warns against firmware upgrades on several boards.

## Recommendations

### Budget, about $130–$450 for two wheels

**Waveshare DDSM115** ×2 ($130 at Waveshare/DFRobot) plus a USB-RS485 adapter or DDSM HAT (A) ($22).
- **Strengths:** integrated driver, 12-bit encoder, STEP model, IP54, tyre included. It can be on your bench this week.
- **Limits:** 2 Nm stall and 3.8 km/h top speed, so only for a ≤8 kg first prototype or for tuning the balance policy at reduced scale.

**Cheap full-size alternative: 6.5" hoverboard motors** ×2 ($150 on Amazon) plus one Flipsky ODESC3.6 dual ($60) or 2× moteus n1 ($298), plus an AS5047P/MA600 encoder bracket per wheel.
- **Strengths:** good torque and speed for almost no money.
- **Costs:** 3 kg per wheel, unknown torque ratings, factory variation, and the encoder retrofit. **Do not try to balance on halls alone.**

### Balanced, about $570–$650 for two wheels

**ODrive BotWheel 2-pack** ($269) + 2× moteus n1 ($298) + mjcanfd-usb-1x ($39). Alternatively use 2× ODrive S1 when back in stock (plug-compatible harness), or 2× ODrive Pro ($458) now.
- **Strengths:** in stock in the US, 5 Nm rated / ~14 Nm burst, 3200 CPR encoder plus halls, 171 mm solid-tread tyre, IP54, an Onshape model for CAD and Isaac Sim import, and published Kt/R/L for the motor model.
- **Watch:** 2.2 kg per wheel. The S1 is out of stock.

**Alternative: Damiao DM-H65-1EC with driver** ×2 ($652, ships from Shenzhen).
- **Strengths:** far more torque (6 / 21.5 Nm), a 17-bit encoder, CAN-FD and a STEP model.
- **Cost:** 3.15 kg per wheel.

### Premium, roughly $1,000–$1,300 for two wheels

**DDT M1502D_233** left + right (¥60,500 each at Switch Science, in stock).
- **Strengths:** DDT's own large in-wheel motor class, 9.6 Nm rated / ≥17 Nm stall, 16384 cpr, 1 kHz CAN feedback, integrated FOC, IP55, STEP model.
- **Watch:** 2.3 kg per wheel, and Japan-only stock (confirm international shipping).

**Light premium: MAB MA-D GL100** ×2 (€1,054.60) or CubeMars GL100 + moteus n1 + MA600 ring encoder (~$420 per wheel), each with a printed hub and tyre.
- **Strengths:** only ~0.75 kg of motor per leg for 3 / 7.7 Nm, giving the least unsprung mass in the direct-drive set.
- **Fit:** suits a 8–12 kg gyropup that wants fast legs.

## Sources

- **DDT / Waveshare / DFRobot:**
  - https://www.waveshare.com/ddsm115.htm
  - https://www.waveshare.com/wiki/DDSM115
  - https://www.waveshare.com/ddsm210.htm
  - https://www.waveshare.com/wiki/DDSM210
  - https://www.waveshare.com/ddsm400.htm
  - https://www.waveshare.com/wiki/DDSM400
  - https://www.waveshare.com/ddsm315.htm
  - https://www.waveshare.com/ddsm350-ct.htm
  - https://www.dfrobot.com/product-3076.html
  - https://www.robotshop.com/products/ddsm115-direct-drive-servo-motor-high-torque-low-noise-hub-motor-w-wheel
  - https://motors.directdrive.com/
  - https://www.switch-science.com/products/9218
  - https://www.switch-science.com/products/9219
  - https://doc.switch-science.com/media/files/af909b0e-e7b2-429f-b8f5-f31c04ee66ca.pdf
  - https://aifitlab.com/products/direct-drive-tech-m1505a_222-directdrive-motor
  - https://cdn.shopify.com/s/files/1/0673/6848/5000/files/M1505A_222-Installation_diagram.pdf
  - https://github.com/takasumasakazu/DirectDriveTech_test
- **ODrive:**
  - https://shop.odriverobotics.com/products/botwheels
  - https://docs.odriverobotics.com/v/latest/hardware/odrive-motors.html
  - https://docs.odriverobotics.com/v/latest/hardware/s1-datasheet.html
  - https://docs.odriverobotics.com/v/latest/hardware/pro-datasheet.html
  - https://docs.odriverobotics.com/v/latest/hardware/micro-datasheet.html
- **Hoverboard motors:**
  - https://www.amazon.com/dp/B0CCV76FCM
  - https://www.amazon.com/dp/B08Y6K2Y61
  - https://www.amazon.com/dp/B0DC21WS55
  - https://raw.githubusercontent.com/odriverobotics/ODrive/master/docs/hoverboard.rst
  - https://discourse.odriverobotics.com/t/project-hoverarm/441
  - https://github.com/EFeru/hoverboard-firmware-hack-FOC
  - https://www.uumotor.com/6-5-inch-350w-brushless-servo-single-shaft-robot-hub-motor.html
  - https://aifitlab.com/products/zhongling-zllg65-asm250-v3-0-motor
- **Damiao / Robstride / MyActuator / Unitree:**
  - https://rcdrone.top/products/damiao-dm-h65-1ec-motor
  - https://rcdrone.top/products/damiao-dm-j6006-2ec-servo-motor
  - https://rcdrone.top/collections/robstride
  - https://rcdrone.top/products/myactuator-l-9025-direct-drive-bldc-servo-motor
  - https://www.myactuator.com/rmd-l-ddmotor
  - https://shop.unitree.com/products/go1-motor
  - https://www.unitree.com/go2-w
- **CubeMars / MAB / gimbal motors:**
  - https://www.cubemars.com/product/gl100-kv10-gimbal-motor.html
  - https://store.cubemars.com/products.json
  - https://www.mabrobotics.pl/product-page/ma-d-gl100
  - https://rcdrone.top/collections/gimbal-motor
- **Upkie / mjbots:**
  - https://upkie.github.io/upkie/bill-of-materials.html
  - https://mjbots.com/products/moteus-n1
  - https://mjbots.com/products/moteus-c1
  - https://mjbots.com/products/moteus-r4-11
  - https://mjbots.com/products/mj5208
  - https://github.com/mjbots/moteus/blob/main/docs/reference/encoders.md
- **VESC / Flipsky:**
  - https://trampaboards.com/vesc-6-mkvi-the-amazing-trampa-vesc-6-mkvi-gives-maximum-power-p-27536.html
  - https://flipsky.net/products/mini-fsesc6-7-pro-70a
  - https://flipsky.net/products/odesc3-6-dual-drive-controller-56v-with-heat-sink-optimizes-high-performance-brushless-motor-high-power-foc-bldc-based-on-odrive

## Gaps

- **Prices not checked:** AliExpress, eBay and DDT's own AliExpress store blocked automated fetching or weren't reached, so no prices from them.
- **Missing listings:**
  - no verified US-stocked 10" hoverboard motor
  - no hoverboard mainboard price
  - no Trampa size, mass or CAD
- **Not published anywhere checked:**
  - **Encoder detail:** none of the DDSM motors publish whether they are absolute at power-up. BotWheel tyre material is not published.
- **Exchange rates:** yen, euro and peso prices are not converted.
