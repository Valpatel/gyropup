# Wheel-legged robot packaging survey (2026-10-26)

Goal: concrete packaging lessons for condensing Gyropup (20–26 kg, 200/200 mm thigh/shin, Ø180 wheel,
2 × RS-04 per leg, hub wheels, J501 Orin box, ~14S pack, foam-dart turret). Specs already covered in
`reference-robots.md` are not repeated; this file is about **layout**.

Tags: **[derived]** = we computed it from a public CAD/URDF/SDF or from physics (inputs given);
**[inferred]** = our reading of mass/geometry data, not stated by the maker; **[unverified]** = seen only in
a search excerpt or a single secondary source, or the primary could not be opened.

---

## 1. At a glance

| Robot | Mass | Leg kinematics | Hip / knee motors | Knee drive | Abd. | Wheel Ø | Battery + compute | Lights / e-stop |
|---|---|---|---|---|---|---|---|---|
| DDT Diablo | 22.9 kg | 2-DOF, parallelogram | coaxial on body side, **knee motor rides on hip motor output** | 140 mm rod ∥ thigh, 90 mm crank ∥ shank | no | 187 | all inside the body ("head") | tail warning light, e-stop switch [unverified] |
| DDT TITA | 24.1 kg + batt | abd + hip + knee | abd in body; hip pitch outboard; knee actuator at hip [inferred] | not documented | ±45° | 185 | body 470×300×190; 2 hot-swap packs | integrated light bars; no physical e-stop listed |
| Ascento (ETH 2019) | 10.4 kg | 1-DOF optimised 4-bar | 1 SEA at hip, springs | n/a (passive linkage) | no | n/a | body houses all electronics | n/a |
| Ascento (commercial) | 30–35 kg | not published | not published | not published | no | n/a | 50.4 V pack integrated in body; Orin NX | headlight, hazard light, colour-coded status LEDs, "eyes" blink red; soft + hard e-stop |
| LimX TRON 1 (wheel) | ≤20 kg | abd + hip + knee | hip cluster in lower "pelvis"; knee actuator coaxial at hip on thigh [inferred] | rod to lever above knee [inferred] | −22…+80° | 254 | electronics box above the hips; quick-swap ≈211–240 Wh | E-stop on robot + remote |
| Tencent Ollie | ~15 kg | five-bar + 2-DOF tail | 2 per leg on base | five-bar | no | n/a | base ≈11 kg | n/a |
| RoboMaster balance infantry | 18–22 kg | five-bar (150/150/270) or coaxial "serial-look" | on chassis | five-bar / 4-bar | no | 124–200 | battery + supercap in chassis; mini-PC in turret | rule-mandated light bars; referee cuts rails |
| Upkie | 5.3 kg | serial | knee motor at knee | direct | no | 112 | battery inside torso case | none listed |

## 2. Robot notes

### 2.1 DDT Diablo — the closest analogue
Sources: [DIABLO paper, arXiv 2407.21500](https://arxiv.org/abs/2407.21500) (DDT co-authors; Fig. 2 = mechanism,
Fig. 3 = motor exploded), [DiabloSTLSDF](https://github.com/DDTRobot/DiabloSTLSDF) (STL + SDF, **no licence**),
[video](https://youtu.be/mm0XruFvZ4U).
- Table I: 22.90 kg; **width 0.540 m, length 0.371 m**, height 0.491 m standing / 0.260 m creeping; links
  L1 0.090, L2–L4 0.140 m; wheel R 0.0935 m. Resellers print the same numbers as "L × W"; the SDF confirms
  the paper (wheel outer faces at y = ±0.272 m → 544 mm) **[derived]**. Our earlier notes and the mech review
  compared Gyropup's width with "Diablo 371 mm"; the right figure is ≈540 mm.
- "The hip motor is flanged to the knee motor, resulting in a series connection that requires less torque
  from the motors when the same force is applied at the foot, as compared to a parallel coaxial arrangement."
  The SDF shows it: `Motor0` (body → `Leg0`) drives a carrier with a 90 mm crank pin; `Motor1` sits on that
  carrier and drives the thigh; a 140 mm rod runs from the crank pin to the shank, **90 mm below the knee**.
  So crank ∥ shank and rod ∥ thigh, a true parallelogram **[derived]**. The force transmission angle at the
  knee equals the interior knee angle: it is best at 90° and goes to zero only at a straight or fully folded knee.
- Virtual work for a stance with the ground force through the hip **[derived]**:
  - Diablo layout: the hip motor holds ≈0 and the knee motor holds |Q_knee|.
  - Both stators on the body (Gyropup today, mech review A2): **both** motors hold |Q_knee|.
- Packaging (SDF/STL):
  - **Body 370 L × 175 W × 245 H mm** **[derived]**, hip axis at mid-height.
  - Body CoM is 12 mm ahead of and 7 mm below the hip axis. The body is 6.7 kg of the 19.7 kg SDF total.
  - Lateral stack from the centreline: body face 88 mm → two pancake motors → thigh plane 176 → shank 215 →
    wheel centre 246 mm.
  - Hip range in the SDF is −3.53…+1.96 rad (≈315°).
  - Links are "arched … to accommodate practical wiring".
- The body ("head") houses battery, main board and IMU (IMU at the midpoint between the hip joints), plus a mini
  PC (4-core A53, 5 TOPS). **Four rollers under the head** support crawl mode (80 kg payload crawling, 4 kg
  standing).
- No abduction; roll comes from differential leg length (roll controller). 6 × M1502D direct drive (2.6 kg, 9.6 N·m rated).
- Manual (v1.1c) has "Description of Tail Lights", a tail warning light, an e-stop switch and a detachable upper
  cover **[unverified: search excerpts of [device.report](https://device.report/manual/9599244); the PDF returned 403]**.

### 2.2 DDT TITA (successor, with abduction)
Sources: [top3dshop](https://top3dshop.com/product/direct-drive-tita),
[TITA_Description URDF](https://github.com/DDTRobot/TITA_Description) (**no licence**).
- URDF: abd ±45°, hip pitch, knee, wheel. Thigh 200 mm, shank 200 mm, wheel Ø185 × 34 mm.
- **Body collision box 470 L × 300 W × 190 H mm**, 13.2 kg (48 % of the URDF total) **[derived]**.
- Abd axes at y = ±89.5 mm inside the body. The hip-pitch joint is 142.6 mm outboard on the 2.06 kg abd link.
  Track 567 mm, overall ≈600 mm **[derived]**; spec 510 × 590 × 490 mm (axes unlabelled).
- The thigh is 3.10 kg with its CoM 28 mm from the hip; the shank is 0.57 kg. So the knee actuator sits at the
  hip and drives the knee remotely **[inferred]**.
- Base CoM is 20 mm ahead of and 19 mm above the abd axis.
- **Sensors are flush in the body's front face**: stereo cameras at ±75 mm, two SPAD ToF and an ultrasonic, all
  at x ≈ +0.22…0.24 m inside the 0.235 m half-length. Nothing protrudes.
- Two hot-swap batteries (≈1 h each, 43.2 V); Orin NX 16 GB.
- "Integrated indicator light bars" show status.
- Accessories mount on the "TITA Bridge" on the back plus three bridges on top; 10 kg moving payload.
- Only an "automatic safe stop" is listed; no physical e-stop. Magnesium-alloy structure per a press release
  **[unverified]** ([IoT M2M Council](https://iotm2mcouncil.org/iot-library/news/smart-cities-news/direct-drive-wheeled-legged-urban-robot/)).

### 2.3 Ascento (ETH 2019 → Ascento Robotics)
Sources: [ICRA paper arXiv 2005.11435](https://arxiv.org/abs/2005.11435) (Fig. 2 = leg),
[RA-L WBC arXiv 2005.11431](https://arxiv.org/abs/2005.11431), [video](https://youtu.be/U8bIsUPX1ZU),
[MYBOTSHOP Ascento manual](https://www.docs.mybotshop.de/downloads/ASCENTO_User_Manual.pdf).
- **2019:** 10.4 kg, 310–660 mm tall.
  - One ANYdrive SEA (40 N·m) per leg "installed in the hip of the body". The linkage is optimised so the
    wheel path is near-vertical through the CoM; RA-L calls it a four-bar.
  - Torsion springs in the inner joints carry the weight. Maxon EC90 **frameless** hub motors keep the wheel
    compact.
  - SLS PA12 topology-optimised parts. "A body that houses all electronics": NUC i7, 4 × 3S motor pack, 4S
    compute pack. ToF jump sensors sit next to the wheels.
- **Commercial R&D unit (manual):**
  - 30–35 kg; **550 L × 600 W × 550–750 H mm**; base height 0.3–0.8 m.
  - 50.4 V 12S5P 17.5 Ah pack "**integrated inside the robot's body**" (weatherproof), >7 h balancing;
    Orin NX; D435i, Livox Mid-360, thermal and IR cameras; dock charging.
  - **Handles on top of the main body.** The power key is in a slot underneath; you tilt the robot to reach it.
  - Lights: flashlights blink at power-up; headlight and hazard light on separate commands; status LED colours
    are white = OK, orange = soft e-stop, red = error, blue = other. The "eyes blink red" when homing is needed.
  - **Soft e-stop damps the motors so the robot "gently falls"**; there is a separate hard e-stop.
- **Guard:** 50–90 × 70 × 50 cm, <30 kg ([Robot Report](https://www.therobotreport.com/ascento-launches-nimble-guard-robot-following-a-new-4-3m-funding-round/)).
  Guard 2.0 has "spotlights three times brighter" and up to 8 h ([Robot Report](https://www.therobotreport.com/ascento-guard-2-0-ready-security-duty-large-facilities/)).
  Leg actuation of the commercial versions is unpublished.

### 2.4 LimX TRON 1 (wheel-foot)
Sources: [spec](https://www.limxdynamics.com/en/tron1/spec),
[robot-description WF_TRON1A](https://github.com/limxdynamics/robot-description) (**Apache-2.0**, URDF/MJCF/STL),
[New Atlas](https://newatlas.com/robotics/limx-tron1-dual-wheel-bipedal/).
- Spec: ≤20 kg; 392 × 420 × 845 mm; 48 V actuators (30 N·m rated, 60 N·m peak); 46.8 V 4.5 Ah quick-swap
  pack (≈211 Wh by V × Ah; New Atlas says 240 Wh).
- **"E-Stop button" on the robot plus a remote E-Stop.** Peripheral port gives 24 V / 100 W, USB 3 and GbE, and
  there is a mounting point.
- URDF: thigh 300 mm, shank 300 mm, **wheel Ø254 × 50**. Abd axes at ±105 mm; base 9.59 kg (43 %).
- **"Pelvis" layout** **[derived]**: the base mesh is 287 L × 344 W × 337 H mm and the abd axes are 260 mm below
  its top, so the hip cluster sits in the lower part and the electronics box (collision 270 × 260 × 190) sits
  above. Track ≈297 mm: the wheels tuck under the body width.
- The thigh (2.3 kg) has its CoM 48 mm inboard of the hip and its mesh reaches 108 mm inboard; the shank mesh has
  a lever 41 mm above the knee. So the knee actuator is coaxial at the hip on the thigh and drives the knee by a
  rod, quadruped-style **[inferred]**.
- An optional D435 sits in the pelvis nose, pitched 61° down (commented out in the URDF).

### 2.5 Tencent Ollie
[PMC paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9888428/), [IEEE Spectrum (photos)](https://spectrum.ieee.org/tencents-new-wheeled-robot-flicks-its-tail-to-do-backflips).
- ≈15 kg, floating base ≈11 kg, height 0.33–0.70 m.
- Eight motors: four at the hips (five-bar, "without actuators on the knees"), two in the tail, two wheels.
- The tail is used only for specific motions (flips); the controller assumes it is fixed. Link and wheel sizes
  are unpublished.

### 2.6 RoboMaster balance infantry (平衡步兵) — most similar mission (two wheel-legs + pan/tilt launcher)
- **Rules** ([RMU 2024 spec manual V2.0](https://terra-1-g.djicdn.com/b2a076471c6c4b72b574a977334d3e05/RM2024/RoboMaster%202024%20University%20Series%20Robot%20Building%20Specifications%20Manual%20V2.0%20(20240712).pdf)):
  - Size and mass: Standard robot ≤25 kg with battery, excluding the referee kit (2.60 kg on balancing robots).
    ≤600 × 600 × 500 mm initial and ≤800³ mm expanded. Balancing robots carry two large armour plates.
  - Light indicators (S115–S118): mounted firmly on the chassis, illuminant ≥200 mm above the ground, fully
    visible from at least one horizontal view.
  - Bumpers (S128): teams "should design safety rods" so armour does not hit walls.
  - Power (S113): the power-management module switches **chassis, gimbal and launcher** outputs separately, and
    the launcher (flywheels, feeder, solenoid) must lose power whenever the ammo-booster port is off
    ([PM01](https://www.robomaster.com/en-US/products/components/detail/1432)).
  - The balancing class was dropped for 2025 (per SJTU's report below), but teams kept wheel-leg chassis.
- **Community-standard five-bar:** motor spacing 150 mm, thigh 150 mm, shank 270 mm. It appears identically in
  HKUST 2024, [ZJUI](https://github.com/MATH-286-Pro/ZJUI-Balance-Infantry-Ver-1.0) (8.2 kg, Ø124 CyberGear hubs)
  and Multivac11.
  - Joint motors sit on the chassis: Unitree A1/Go1, HT-04, DaMiao, CyberGear.
  - Wheels: DDT M1505B direct-drive hubs, LK hubs or geared M3508.
- **WIT 2024** ([post + SolidWorks .7z](https://bbs.robomaster.com/article/9657)):
  - 18.4 kg; Ø200 wheels on Unitree Go1 motors; jumps 30 cm.
  - Shortened links (machined thigh adapter) and compressed body height and width.
  - Planned next: a smaller geared wheel, lower the leg set, and **"move the joint motors to the body's lower
    deck to free the upper deck for the gimbal"**.
  - Climbs steps by extending the legs, bumping the step, then retracting.
- **HKUST 2024** ([post](https://bbs.robomaster.com/article/20424),
  [technical report PDF](https://hz-rm-bbs-web-prod.oss-cn-hangzhou.aliyuncs.com/bbs-prod/413a60f39d80459a94f96c976bd59264.pdf)):
  - Size and drive: 21.8 kg; 445 × 445 × 780 mm expanded; HT-04 joints; DDT M1505B hubs; 3.5 m/s.
  - **Standing needs 6–7 N·m per joint motor.** A tension spring per side cut that to **±1 N·m and about
    doubled runtime**: hook 22 mm from the joint centre at 68° to the thigh, k = 4000 N/m.
  - The thigh is carried by a CNC hub on a large bearing. Bolting it straight to the motor output (3 × M4 +
    3 × Ø4 pins) "broke legs" on jumps.
  - Frame: 1 mm-wall aluminium tube filled with low-infill prints; the outer tubes tie straight into the
    glass-epoxy shell. Joint stops are printed in TPU 95A, and the **light-bar brackets are TPU so they survive
    falls**.
  - A **wiring "belly" opens with two M4 thumb screws** for access to power and wiring.
- **DGUT ACE 2024** ([post](https://bbs.robomaster.com/article/54974)): 20 kg; **598 × 442 × 490.5 mm** initial
  (772.5 mm tall expanded); 4 × A1 joints, 2 × M3508 wheels; bicycle-headset joints.
- **SJTU 2025 "serial-leg"** ([post + PDF + CAD zip](https://bbs.robomaster.com/article/803691)):
  - Why they left the five-bar: steps can be climbed by collision-then-retract, and a **360° hip** lets the
    robot right itself.
  - Of three coaxial layouts they kept the "similar linkage": kinematically a five-bar with zero motor spacing,
    which splits load evenly between the two motors. The "simplified linkage" gave uneven load and worse control.
  - Thigh shorter than shank so the knee clears the ground when crouched; nitrogen gas springs for jumping.
  - Hip drive: motors drive the hip through **chain** (slotted mount plus a printed wedge for tension) into a
    nested two-stage hip shaft on two headset bearings. A 30 mm-bore slip ring gives continuous hip rotation.
  - Frame: 1 mm aluminium tube in a "#" grid, ≈2 kg. The hip blocks carry the gimbal frame. **"Adjust parts so
    the CoM is near the geometric centre."**
  - Turret: the magazine moved into the chassis to cut yaw inertia; the mini-PC rides on the turret.
  - **Quick-release head: 4 screws, XT30 and DB9 through two breakout PCBs, 5 minutes to separate (was over an
    hour).**
  - Protection: hinged sacrificial bumpers and guide wheels at the front-lower corners protect the core frame;
    ToF sensors are tucked beside the front armour.
  - Mass came down from 23 kg to under 20 kg.
- **Joint hardware** ([bicycle-headset note](https://bbs.robomaster.com/article/54960)):
  - Shoulder screw + flanged bearing + PTFE washer joints loosened under jumps, bound when tightened, and let
    heavy offset wheels splay ("外八").
  - The fix is headset-style angular-contact cups: SJTU machined their own; DGUT uses stock 44 mm OD / 41 mm
    bicycle headsets.
- **Licence:** forum CAD is for RoboMaster teams only and non-commercial. Use it as reference, do not copy.

### 2.7 Upkie (open source)
- Sources: [parts](https://github.com/upkie/parts) (Apache-2.0, FreeCAD/STL),
  [BOM](https://upkie.github.io/upkie/bill-of-materials.html).
- ≈5.3 kg (URDF sum); serial leg with the knee motor on the leg; 112 mm wheel.
- The battery (RYOBI 18 V) sits **inside the torso case** on a printed stud with leaf-spring contacts.
- Optional bearing hip and knee supports "protect knee actuators from radial load"; handle and camera brackets
  are add-ons. v2 uses a fork lower leg with cables run outside.
- No e-stop and no lights in the BOM.

### 2.8 Unitree, RobStride, HighTorque, other kits, Disney
- **Unitree:** no wheel biped found. Its wheel-legged products are quadrupeds: Go2-W, B2-W,
  [A2-W](https://www.unitree.com/mobile/A2-W), and AS2-W, announced 2026-07-24
  ([secondary source](https://explainx.ai/blog/unitree-as2-w-wheel-legged-robot-july-2026)).
- **RobStride ([robstride.com/open-source](https://robstride.com/open-source)):**
  - The page renders in JS. Per our crawl in `robstride-open-source-2026-10-26.md` it has 8 entries: the EL-A3
    arm, reBot arm, K-Bot humanoid (4 × RS-04), LeRobot humanoid and 4 toolchain repos.
  - **None is wheel-legged.** No public RS-04 wheel-legged build was found.
- **HighTorque:** no wheel-legged kit found. Its documented robots are humanoids (π, π+, Hi)
  ([RoboCup AP 2025](https://2025.robocupap.org/?p=2867)).
- **Other kits:**
  - [StackForce mini](https://wiki.seeedstudio.com/stackforce_mini_wheeled_legged_robot/): 540 g, 4 servos +
    2 × 2208 gimbal wheels, URDF/STL/schematics open.
  - [XGO-Rider](https://github.com/elecfreaks/XGO-Rider) (micro:bit) and
    [Rider-Pi](https://github.com/YahboomTechnology/Rider-Pi-Robot) (CM4): desk scale.
  - [Tsinghua ARX-6](https://air.tsinghua.edu.cn/OpenARX6.htm): an open wheel-legged manipulator; files not
    checked.
  - DDT sells its M1505B hubs to RoboMaster teams (HKUST and HKU credit it).
- **Disney:** no wheel-legged robot found. [BD-X](https://arxiv.org/abs/2501.05204) (15.4 kg biped) is still
  relevant for packaging and character:
  - Torso: battery module, comms board, IMU. Head: PC, radio, show board.
  - The removable battery gives ≥1 h.
  - **LED-array eyes, a head lamp and antennas are used for expression.**
  - A controller "motion stop" freezes the joints standing.

### 2.9 Hobby / student builds with CAD
- [Skythinker616](https://github.com/Skythinker616/foc-wheel-legged-robot) (GPL-3.0, SolidWorks): desk scale, a
  closed linkage driven from the body.
- [Venus-1](https://github.com/track-tech/Venus-1__Four-link-wheel-legged-robot) (GPL-3.0): four-bar, CyberGear,
  FR4 plates. Geared-wheel backlash made it jitter.
- [Multivac11](https://github.com/Multivac11/Wheel-legged-robot--Main_Code): five-bar 150/150/270, A1, 12.9 kg.
- [ZJUI](https://github.com/MATH-286-Pro/ZJUI-Balance-Infantry-Ver-1.0): Fusion; no licence.
- [huoyiwei4](https://github.com/huoyiwei4/cybergear-wheel-legged-robot) (MIT, SolidWorks + STL, not validated on
  hardware).
- [N-B-Studio](https://github.com/N-B-Studio/Open-wheel-legged-balance-bot) (Apache-2.0, "fully 3D-printed
  8-DOF"; details sparse).
- [Flamingo](https://github.com/jaykorea/Isaac-RL-Two-wheel-Legged-Bot) (MIT; Isaac Lab sim-to-real; hardware
  undocumented).

## 3. Cross-cutting packaging patterns

### 3.1 Body proportions (D = wheel diameter) **[derived]**

| Robot | Body L × W × H (mm) | Body L/D | W/D | H/D | Track c-c (mm) | Track/D | Link/D | Body CoM vs hip axis |
|---|---|---|---|---|---|---|---|---|
| Diablo | 370 × 175 × 245 (STL) | 1.98 | 0.94 | 1.31 | 492 | 2.63 | 0.75 | +12 fwd, −7 |
| TITA | 470 × 300 × 190 (URDF box) | 2.54 | 1.62 | 1.03 | 567 | 3.06 | 1.08 | +20 fwd, +19 |
| TRON 1 | 287 × 344 × 337 (base mesh) | 1.13 | 1.35 | 1.33 | 297 | 1.17 | 1.18 | +46 fwd, ≈96 above abd |
| **Gyropup now** | 181 × 206 × 112 (J501 = body) | **1.01** | 1.14 | **0.62** | 588 (CAD) | **3.27** | 1.11 | — |

Relative to its wheel, Gyropup's body is **half as long and half as tall** as Diablo's or TITA's, and its stance
is the widest. Anything that does not fit in a 181 × 206 × 112 box ends up bolted outside, which is the "box out
front".

There are two archetypes:
- **Side legs** (Diablo, TITA, Ascento, RoboMaster): the hip axis passes through the body's mid-height and the
  wheels sit outside, giving 2.6–3.1 D track.
- **Pelvis** (TRON 1): the electronics box sits above a hip cluster, the legs hang under the body and the track is
  ≈1.2 D. It needs abduction and long (300 mm) links.

### 3.2 Battery and compute
- **Inside one shell, between or under the hips.** Diablo puts battery, board and IMU in the body; Ascento's pack
  is integrated in the body; TRON 1 stacks electronics above the hips; RoboMaster keeps battery and supercap in
  the chassis.
- **Body CoM within ~20 mm of the hip axis** (Diablo, TITA).
- **Service:** quick-swap packs (TRON 1, TITA ×2), a belly cover on thumb screws (HKUST), every part reachable in
  5 minutes (SJTU).
- **Compute:** RoboMaster mounts the mini-PC on the turret near the camera (SJTU, HKUST). BD-X puts its PC in the
  head. Diablo and TITA keep compute in the body.
- **No front box anywhere.** Sensors sit flush in the body's front face (TITA cameras/ToF/ultrasonic, TRON 1's
  D435 in the pelvis nose, SJTU's ToF beside the armour). Accessories go on top or back interfaces: TITA Bridge,
  TRON 1's 24 V/100 W port, Ascento's top payload.

### 3.3 Lights
- **Integrated, not pods:** TITA light bars; Ascento headlight, hazard light, colour-coded status LEDs
  and "eyes" that blink red when homing is needed; Diablo's tail warning light [unverified]; BD-X eye arrays and
  head lamp.
- **Mounting rules from RoboMaster:** on the chassis, ≥200 mm high, visible horizontally, on TPU brackets (HKUST)
  because rigid brackets break in falls.

### 3.4 E-stop
- TRON 1: a physical button on the robot plus a remote stop.
- Ascento: a soft stop that damps the motors and sits the robot down, plus a hard stop. The key switch is
  underneath.
- RoboMaster: separate switched rails for drive, turret and launcher; the launcher dies whenever the turret rail
  does.
- Diablo: rollers under the body give it a safe resting posture.
- None of the sources documents where the e-stop button sits on the body.

## 4. Ranked recommendations for Gyropup

1. **Adopt Diablo's leg topology; keep the rod.** "Pushrod vs parallel linkage" is a false choice: Diablo's
   knee *is* a rod in a parallelogram. The difference is in three details:
   - **Series flange.** Bolt the knee RS-04's housing to a carrier on the hip RS-04's output, coaxial.
   - **Crank ∥ shank.** Put the rod's lower pin on the shank below the knee (Diablo: 90 mm crank, 90 mm below the
     knee) and run the rod parallel to the thigh. The transmission angle then equals the knee angle: best near
     the 90–100° stance and zero only at straight or fully folded. This removes mech-review A1 (dead point at 90°).
     Rod force = T / (r·sin γ).
   - **Stance load on one motor.** The knee RS-04 alone holds the stance: ≈10–15 N·m per leg at the 60 % pose
     for 20–26 kg **[derived]**. Today both motors hold it (A2). The cost is a knee-motor cable crossing the hip
     joint; Diablo routes it along arched links.
   - **Reject the RoboMaster five-bar for us.** Its 270 mm shanks reach fore and aft, which limits hip rotation
     and steps; SJTU left it for exactly this. In this survey no ≥15 kg robot drives the knee by belt (SJTU uses
     chain only at the hip).
2. **One body shell that swallows everything; no external front box.** Target ≈2 D long × 1.0–1.3 D tall
   (≈360–450 × 190–235 mm for D = 180).
   - Hip axis through the body's mid-height (Diablo).
   - J501 (206 × 192 × 112) ahead of or above the actuator block, pack behind or below, all within one shell.
   - **Balance so the body CoM falls within ~20 mm of the hip axis** with the turret fitted (Diablo/TITA).
   - Cameras, ToF and lights flush in the front face (TITA). Leave the J501 an air path (intake low, exhaust
     high or back): none of the surveyed robots documents compute cooling, so this is ours to design.
3. **Pack low and central, swapped from the rear or bottom.** Use a slide-in pack with a latch (TRON 1/TITA
   quick-swap). Put power electronics on a removable belly tray held by thumb screws (HKUST), and aim for "every
   part in 5 minutes" (SJTU).
4. **Narrow the stance to ≈2.6–3.0 D (470–540 mm track).** Recess the hip RS-04 inside the body wall and keep the
   knee RS-04 on the carrier outside. With thin link planes and the wheel just outboard of the shank this gives
   ≈540 mm overall **[derived, rough]**. Stacking both motors outside a 206 mm body gives ≈630 mm, no gain on
   today. TRON 1's pelvis layout is narrower still but needs abduction.
5. **Joints like the RoboMaster teams build them.**
   - Bearings carry the link; the actuator flange carries torque only (HKUST, SJTU, Upkie supports).
   - Headset-style angular-contact cups, or double-shear forks, at the knee and the carrier (SJTU/DGUT; fixes A3).
   - TPU end-stops.
6. **Turret as a quick-release module.** Four bolts and one connector panel through a breakout PCB (SJTU). If yaw
   inertia matters, move the magazine into the body (SJTU lower-feed).
7. **Lights integrated and meaningful.**
   - Headlights recessed in the body nose, or in the turret face so they follow aim (BD-X head lamp).
   - An RGB status band or "eyes" using Ascento's code (white OK / orange soft-stop / red fault).
   - A rear tail or hazard light (Diablo/Ascento).
   - TPU mounts, ≥200 mm high, visible from the side (RoboMaster).
8. **E-stop architecture.**
   - A latching button on the body (our suggestion: top-rear, reachable from behind) plus a remote (TRON 1).
   - A soft stop that damps and sits the robot onto skids, rollers (Diablo) or the tail before the contactor
     opens (Ascento).
   - **Separate drive, turret and launcher rails**, with the launcher always dropping with the turret
     (RoboMaster S113).
9. **Fall furniture.** Skid rollers under the body (Diablo); sacrificial bumpers and guide wheels at the lower
   front and rear corners (SJTU, RoboMaster "safety rods"); top handles (Ascento, Upkie).
10. **Springs only if heat or runtime needs them.** RS-04 holds the stance at ≈25–35 % of rated **[derived]**, but a
    tension or gas spring (HKUST ±1 N·m and 2× runtime; Ascento; SJTU) is cheap.
11. **No abduction in v1.** Diablo, Ascento, Ollie, RoboMaster and Upkie balance without it; TITA and TRON 1 pay
    for it with two actuators and width. Roll comes from differential leg length (Diablo).

## 5. Open items and unverified
- Diablo: tail-light and e-stop placement (manual blocked). TITA: battery location and knee transmission. TRON 1:
  knee rod (inferred from URDF). Ascento commercial: leg actuation. Ollie: link and wheel sizes.
  RoboMaster rules: we read 2024; the 2026 manual was not checked.
- Licences: DDT models (Diablo STL/SDF, TITA URDF) have no licence; RoboMaster CAD is restricted to teams.
  LimX descriptions are Apache-2.0 and Upkie parts are Apache-2.0, so those two are safe to reuse.
