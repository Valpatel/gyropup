# Springs, suspension and compliance for leg v2 (2026-10-27)

The question: do Gyropup's five-bar legs need springs or anything like a suspension, both to carry the body at a
resting height and to ride and land better; what do similar robots do; how much higher could we jump and how much
smoother could we ride; and what does it cost. This file is the sourced survey (section 2), the physics of our own leg
measured in the single-leg rig (sections 3 and 4, `sim/leg_spring_study.py`, outputs in `exports/leg/springs/`), the
real parts (section 5), the trade-offs (section 6) and a recommendation (section 7).

Every URL was checked on 2026-10-27. Tags: **[derived]** = computed by us from a public model or from physics (inputs
given); **[unverified]** = seen only in a search snippet or a secondary source; **[estimate]** = our engineering
estimate where nothing is published.

---

## 1. The answer up front

- **A parallel spring does what the survey says it does, but the one place it fits is not worth it yet.** A McMaster
  extension spring between the two upper links (section 7) cut the standing hip torque from 7.7 to 0.2–1.2 N·m,
  added 14 % to the jump and held an unpowered leg at ≈300 mm in the planar rig, but it fails in 3-D (section 8): below
  250 mm the coil passes through the hip region. The layout that clears the CAD at every length, a ≥1.4 N/mm spring
  knee to knee outboard of the knee bolts (5108N807 + a 76 mm lanyard, or two 5108N78), does the same job at 13.1 kg
  (standing 9.8 → 0.3 N·m, jump +24 % with the feed-forward, the collapse from 3.0 kN to 65–70 N damped) but needs
  posts, lanyards, a guide, a boot and a 7 mm gap to the tyre at full crouch. **Build the rig without a spring, and
  bench-test the RS-04's power-off damping first** (sections 8.7, 7).
- **No spring touches the landing spike.** It is set by the rotors' reflected inertia being stopped through the tyre,
  and a parallel spring does not see an impulse. What does: a softer tyre (−27 % pneumatic-stiffness, −42 % foam),
  elastomer axle mounts (−39 %), retracting the leg through touchdown (−18 %), and a touchdown-speed cap.
- **The gearbox is not the limit on the rig's own measure**: 62 N·m through it at the 150 mm drop and 88 N·m at
  300 mm with 11 kg, under the RS-04's 120 N·m peak; the 143 N·m that raised the alarm was the quasi-static J^T·F,
  which overstates the gearbox three times and the knees twice. The knees are sized by the undamped power-off
  collapse, not by landings; the spring removes that collapse (section 4.5).
- **Nobody with a quasi-direct-drive wheel-leg uses series compliance** (section 2): parallel springs for load and
  jumps (Ascento, HKUST, the RoboMaster gas-strut teams, ANYmal's knee spring, Penn's five-bar), tyres and software
  for landings. Gas struts are jump assists with stops and short lives; torsion springs at our hips would be custom
  and the wrong torque shape.
- **A rig defect**: `sim/leg_rig.py` carries 8.5 kg, not 11 (the dummy mass on a geom is ignored when the body has an
  inertial element); every load in `rig-results.json` is for 8.5 kg (section 3.1).

---

## 2. Survey: what similar robots do

### 2.1 At a glance

| Robot | Mass | Leg | Compliance | Numbers | Source |
|---|---|---|---|---|---|
| Ascento (ETH, 2019) | 10.4 kg | 1-DOF optimised linkage, one ANYdrive SEA per hip, Maxon EC90 hub wheels | **Parallel torsion springs at the inner joint** (gravity compensation) + series-elastic hips; software virtual spring-damper on landing | jump 0.4 m; 10 cm steps; hip 40 N·m peak, 12 rad/s; hip ≈ −40 N·m to retract the legs in flight against the springs (plot read-off); spring rate not published | [arXiv 2005.11435](https://arxiv.org/pdf/2005.11435), [arXiv 2005.11431](https://arxiv.org/pdf/2005.11431) |
| Ascento R&D / Pro / Guard | 30–35 kg | not published | nothing published on springs; soft e-stop damps the motors so it "gently falls" | 5 km/h (manual), 12 km/h (Pro press); 15 cm stairs (RL paper) | [manual](https://www.docs.mybotshop.de/downloads/ASCENTO_User_Manual.pdf), [arXiv 2402.06143](https://arxiv.org/html/2402.06143v1) |
| DDT Diablo | 22.9 kg | parallelogram four-bar, direct-drive M1502D stacked at the hip | **None**: SDF joints have damping 0, no spring; tyre type not published | jump 80 mm (official spec); 8 cm obstacles; motor 9.6 N·m rated / 17 N·m stall, 2.6 kg; squat limit 15 min [unverified] | [arXiv 2407.21500](https://arxiv.org/pdf/2407.21500), [SDF](https://raw.githubusercontent.com/DDTRobot/DiabloSTLSDF/main/DIABLO/model.sdf), [spec](https://robotics.directdrive.com/products/xingtian-robot/1653337674873306) |
| DDT TITA | 24.1 kg (no battery) | 8 DoF serial with abduction | **None** (URDF has no dynamics; the RL policy's PD is 40 N·m/rad, 1 N·m·s/rad) | 120 N·m peak modules; jump 20 cm forward; 3–5 m/s | [spec](https://robotics.directdrive.com/products/tita-robot/1653341764448411), [URDF](https://raw.githubusercontent.com/DDTRobot/TITA_Description/main/tita/urdf/robot.urdf), [tita_rl](https://raw.githubusercontent.com/DDTRobot/tita_rl/master/configs/tita_constraint_config.py) |
| Upkie | ≈5.3 kg [derived] | serial, qdd100 at the knee | **None**; RC 1:8 rubber tyre only | hip 16 N·m (<1 s), 3.3 N·m continuous; wheel r 50–70 mm; no drop or jump data | [URDF](https://raw.githubusercontent.com/upkie/upkie_description/main/urdf/upkie.urdf), [BOM](https://upkie.github.io/upkie/bill-of-materials.html), [qdd100](https://mjbots.com/products/qdd100-beta-3) |
| Tencent Ollie | ≈15 kg | five-bar from the base + 2-DOF tail | **None described**; LQR balance | height 0.33–0.70 m; jump "a good foot" [press], 60 cm [unverified] | [PMC9888428](https://pmc.ncbi.nlm.nih.gov/articles/PMC9888428/), [IEEE Spectrum](https://spectrum.ieee.org/tencents-new-wheeled-robot-flicks-its-tail-to-do-backflips) |
| Tencent X-Man | 80 kg | wheel-legged, 35 cm leg stroke | **Software only**: variable-damping impedance, 500 Hz WBC | terrain steps 20 cm | [arXiv 2411.09935](https://arxiv.org/html/2411.09935v1) |
| Boston Dynamics Handle | not published | electric + hydraulic legs, prismatic/variable-length (patent snippets) | **None disclosed**; a counter-balance body | jump 1.2 m, 14 km/h, 45 kg (2017) / 15 kg boxes (2019) | [IEEE Spectrum](https://spectrum.ieee.org/boston-dynamics-handle-robot), [US10802508B2](https://patents.google.com/patent/US10802508B2/en) (claims unreadable today, HTTP 503) |
| LimX TRON 1 (wheel-foot) | ≤20 kg (model 22.3) | abd + hip + knee, Ø254 wheels | **None** in the URDF/MJCF (no stiffness, springref or tendon) | 30/60 N·m actuators, 15 rad/s; 3 m/s; 20 cm obstacle; no jump or landing data | [spec](https://www.limxdynamics.com/en/tron1/spec), [MJCF](https://raw.githubusercontent.com/limxdynamics/robot-description/master/pointfoot/WF_TRON1A/xml/robot.xml) |
| Unitree Go2-W | 18 kg | quadruped, hub wheels | **Pneumatic 7-inch tyre**; no joint springs | knee 45 N·m (URDF 35.6), wheel ±15 N·m (MJCF); 2.5 m/s; "<70 cm" climb/drop (marketing) | [go2-w](https://www.unitree.com/go2-w), [MJCF](https://raw.githubusercontent.com/unitreerobotics/unitree_mujoco/main/unitree_robots/go2w/go2w.xml) |
| Unitree B2-W | ≈85 kg | quadruped, Ø225 wheels | **None**; tyre not stated | calf 320 N·m (URDF), wheel 40 N·m / 50 rad/s; stairs 20–25 cm; 15 km/h | [b2-w](https://www.unitree.com/b2-w), [URDF](https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/b2w_description/urdf/b2w_description.urdf) |
| Swiss-Mile / wheeled ANYmal | ANYmal + ≈12 kg | quadruped on wheels, SEA legs | **Series-elastic actuators** (ANYdrive) + "active suspension" by the legs; no passive spring; tyre not published | 6.3 m/s limit, 5.0 m/s shown, 60 cm drop with a flight phase, 0.28 m front-leg jump; COT 0.16 | [Science Robotics 2024 / arXiv 2405.01792](https://arxiv.org/html/2405.01792), [arXiv 2010.06322](https://arxiv.org/abs/2010.06322) |
| ANYmal / ANYdrive | 32 kg (B) | SEA: motor, harmonic drive, rotational spring, two encoders | **Series elastic** for impact robustness and torque sensing; "compromises the power output"; a later drive has a spring "three times stiffer" | 40 N·m, 12 rad/s; torque resolution 0.08 N·m; 70 Hz torque bandwidth; spring stiffness not found | [arXiv 1901.08652](https://arxiv.org/pdf/1901.08652), [ANYmal IROS 2016](https://www.research-collection.ethz.ch/server/api/core/bitstreams/09cfc536-6001-4295-b9ae-4e6b049c151e/content) |
| ANYmal parallel-elastic knee (Bjelonic 2023) | 52.5 kg | tension spring + wire over an elliptic cam at the knee, pulling only | **Parallel spring, optimised with RL + Bayesian optimisation** | k = 4154 N/m, cam a 8.1 / b 6.0 cm, zero-force angle 0.36 rad; torque-squared cost −33 %, knee peak 73 → 52 N·m, range +11 %; +1.2 kg; "the actuators have to repeatedly work against the spring" on some tasks | [arXiv 2301.03509](https://arxiv.org/pdf/2301.03509) |
| Ghost Minitaur | 5 kg | direct-drive symmetric five-bar (l1 0.1, l2 0.2 m), T-Motor U8 | **None, all virtual**: "no gears to protect from impulses"; springs left as an option | 0.48 m jump; U8 3.5 N·m peak, reflected inertia 1e-4 kg·m² (96× less than a 23:1 Maxon) | [Kenneally RA-L 2016](https://repository.upenn.edu/server/api/core/bitstreams/8592ddaa-98e8-4163-844f-e6ea737b9422/content) |
| Penn five-bar monopod with a parallel spring | 1.85 kg | two direct-drive U8-16 on a five-bar + linear spring | **Parallel spring, measured** | 875 N/m built (1565 optimal); 5.6× energy stored, 4.8× collision efficiency in a 0.7 m drop, 1.6× kinetic energy; "the spring constant does not appear in [the impulse]" | [Kenneally IROS 2015](https://repository.upenn.edu/server/api/core/bitstreams/f233ba2a-636a-48bc-9f0b-efa264a7e1a4/content) |
| Stanford Doggo | 4.8 kg | coaxial symmetric five-bar, 3:1 belt QDD | **None**: "virtual leg compliance" (PD gains) | 1.14 m vertical jump; 4.8 N·m peak, 2.6e-4 kg·m²; landing gains "low stiffness and lots of damping" | [arXiv 1905.04254](https://arxiv.org/pdf/1905.04254), [jump.cpp](https://raw.githubusercontent.com/Nate711/Doggo/master/src/jump.cpp) |
| MIT Cheetah / Mini Cheetah | 33 / ≈9 kg | proprioceptive QDD, 5.8:1 and 6:1 (knee 9.33:1) | **None**; 3 mm rubber pad; the gearbox load at impact is set by reflected inertia | Cheetah 0.0102 kg·m² reflected, IMF 90 % of a series-elastic version; Mini Cheetah ≈0.0023 kg·m², 18/28 N·m code limits; series spring at 70 N·m/rad drops the first mode 79.7 → 13.5 Hz | [Wensing T-RO 2017](https://fab.cba.mit.edu/classes/865.18/motion/papers/mit-cheetah-actuator.pdf), [MiniCheetah.h](https://raw.githubusercontent.com/mit-biomimetics/Cheetah-Software/master/common/include/Dynamics/MiniCheetah.h) |
| Agility Cassie | 31 kg | 5 motors per leg + 2 passive leaf-spring four-bars | **Series leaf springs** (shin and heel) for contact sensing and compliance | 2300 / 2000 N·m/rad (Agility wiki), 1500 / 1250 in the sim models; knee 16:1, 195 N·m at the joint, 0.093 kg·m² reflected [derived]; survived a ≥1.5 m fall; 1.4 m learned jump | [cassie-doc wiki](https://github.com/agilityrobotics/cassie-doc/wiki/Knee-Spring-Model), [cassie.xml](https://raw.githubusercontent.com/osudrl/cassie-mujoco-sim/master/model/cassie.xml), [arXiv 1809.07279](https://arxiv.org/pdf/1809.07279), [arXiv 2302.09450](https://arxiv.org/pdf/2302.09450) |
| Agility Digit | 48 kg | as Cassie | **Series leaf-spring four-bars** (ankle, shin) "for additional compliance"; rates not published | — | [arXiv 2103.15309](https://arxiv.org/pdf/2103.15309) |
| Olympus (jumping quadruped) | 13.8 kg | diamond five-bar, AK70-10 | **Parallel cord spring across the knees**, "to aid in jumping and energy recovery while landing" | 800 N/m, natural length 0.18 m; no jump or landing numbers | [arXiv 2503.03574](https://arxiv.org/pdf/2503.03574) |
| MUPS v2 hopper (SurGE) | n/p | one-way parallel knee spring | **Parallel, one-directional** | 5570 N/m engaging at 0.135 m: −37.65 % heating + tracking objective | [arXiv 2606.21866](https://arxiv.org/pdf/2606.21866) |
| HKUST ENTERPRIZE RM2024 (five-bar 150/150/270) | 21.8 kg | HT-04 joints, M1505B hubs | **Parallel tension spring**, chassis to a hook on the thigh, subtracted as feed-forward | k = 4000 N/m, hook 22 mm from the joint at 68° to the thigh; standing 2–7 N·m → ±1 N·m; runtime ≈ ×2; HT-04 output flange broke in jumps before a CNC hub on a big bearing | [post](https://bbs.robomaster.com/article/20424), [report PDF](https://hz-rm-bbs-web-prod.oss-cn-hangzhou.aliyuncs.com/bbs-prod/413a60f39d80459a94f96c976bd59264.pdf) |
| SJTU 交龙 RM2025 (serial leg, 360° hip) | <20 kg | chain-driven hip | **Nitrogen gas springs for jumping**; force/stroke not stated | 15 cm steps, two-step stairs; wheel-gearbox planetary bearings "burst" in extremes | [post](https://bbs.robomaster.com/article/803691) |
| 山海机甲 (HEBUT) 2025/26 (offset five-bar) | 23.35 kg | DM8009P joints, MF9025 hubs | **350 N gas spring**, modelled as Fq = kp·L + b + kv·sign(L̇)·abs(L̇) and subtracted in the VMC | 420 mm jump; liftoff when support < 30 N; "with the gas spring the take-off load drops a lot, but retracting the legs in flight loads the motors heavily" | [post](https://bbs.robomaster.com/article/1969319), [post](https://bbs.robomaster.com/article/810688) |
| SPR 中国石油大学(北京) RM2026 (five-bar) | n/p | — | **300 N gas spring**, anchors 49 and 200 mm from the pivot, subtracted by virtual work | 280 mm jump; leg PID 1000 N/m, 120 N·s/m (jump 3000 / 200); "release the compensation during the jump or 0 N and 450 N give the same height"; liftoff detection misfired with the spring | [post](https://bbs.robomaster.com/article/1884251) |
| HKUST RM2025 / RM2026 (serial leg) | 24.1 / 22.5 kg | 8016E-i36 hips | **300 → 400 N undamped gas strut**, hip CNC ↔ leg; "without hard stops the leg can pull the strut apart" → polyurethane bumpers | hexroll 116 mm 60A tyre; gearbox to double bearings after teeth broke in big jumps | [2025](https://bbs.robomaster.com/article/764738), [2026](https://bbs.robomaster.com/article/1938220) |
| SCUT 华南虎 RM2025 (serial leg) | 25.5 kg | thigh 215 / shank 254 mm | **Gas springs swept 147–294 N** | best jump only ≈32 cm | [post](https://bbs.robomaster.com/article/803656) |
| Tongji SuperPower RM2026 (serial leg) | n/p | — | gas spring as a fitted passive force (cubic in leg length) subtracted from the PID | jump state machine SQUAT/JUMP/SHRINK | [post](https://bbs.robomaster.com/article/1969880) |
| WIT 武汉工程大学 2023 / 2024 | 18.4 kg | five-bar, Go1 hubs, Ø200 | **None**; 8-inch 200×45 kids'-bike **pneumatic tyre** "has its own cushioning" | 30 cm jump | [2024](https://bbs.robomaster.com/article/9657), [2023](https://bbs.robomaster.com/article/9346) |
| CUBOT 中国矿业大学 2025 (five-bar) | 23 kg | A1 joints | **None** (leg-length PD) | 200 mm jump, two-stage 300 mm; landing ≈0.13 s | [post](https://bbs.robomaster.com/article/814277) |
| 南航金城 2026 (offset parallel hero) | 29 kg | leg 0.37 m | **None** | 0.25 m stable / 0.35 m max jump; link screws shook loose and a link snapped | [post](https://bbs.robomaster.com/article/1883510) |
| DGUT ACE 2024 / Qingdao 2025 | 20 kg / n/p | A1 joints / hip module | **None** / a jump-assist spring hole reserved but unused; 5-inch rubber tyre | 2.7 m/s | [ACE](https://bbs.robomaster.com/article/54974), [Qingdao](https://bbs.robomaster.com/article/716356) |
| Hobby five-bars (Multivac11, Luo25177, Skythinker616) | 12.9 kg / n/p / desk | A1 / AK80-6 / 4010 gimbal | **None** (leg-length PD "feels like a spring"); 60A rubber or sponge tyres | Luo25177: landing D "much larger" than on the bench | [Multivac11](https://github.com/Multivac11/Wheel-legged-robot--Main_Code), [Luo25177](https://github.com/Luo25177/wheel-legged), [Skythinker616](https://github.com/Skythinker616/foc-wheel-legged-robot) |

### 2.2 What the survey says

1. **No quasi-direct-drive or direct-drive wheel-leg uses a series spring.** Diablo, TITA, Upkie, Ollie, TRON 1, the
   Unitree wheelers, every RoboMaster build, Minitaur, Doggo and the MIT Cheetahs are rigid from motor to wheel;
   their compliance is the tyre and the controller's virtual spring-damper. Series springs appear only where they hide
   a high-ratio rotor (Cassie's 16:1 knee behind 2300 N·m/rad leaf springs; ANYmal's harmonic drive behind the
   ANYdrive spring), and they cost bandwidth (Wensing: a 70 N·m/rad series spring drops the MIT Cheetah leg's first mode
   from 79.7 Hz to 13.5 Hz) and an extra state to estimate (Cassie: >0.35 rad sim-to-hardware tarsus error, ±20 %
   stiffness randomisation in training). Minitaur's designers say it outright: SEA "removes the low-pass filtering of
   actuation signals" only when you leave it out.
2. **Parallel springs are common, and always for load and energy, never for the impact.** Ascento's torsion springs
   "counteract the system's own weight and reduce the control effort of the hip motors when driving or standing,
   increasing overall efficiency and jumping height" (the sentence from the paper, p. 2). HKUST's tension spring took
   standing torque from 2–7 N·m to about ±1 N·m and doubled runtime. ANYmal's optimised knee spring cut the knee's
   torque-squared cost by a third and its peak torque by 30 %. The Penn five-bar rig stored 5.6× the energy and
   returned 1.6× the kinetic energy with a parallel spring, and states the physics: the spring constant does not appear
   in the touchdown impulse. The RoboMaster gas-strut teams (300–400 N) use the strut as a jump assist and get
   280–420 mm jumps on 20–25 kg robots.
3. **Every parallel spring must be modelled and cancelled by the controller.** HKUST: "spring torque computed from the
   two joint angles and subtracted directly"; Tongji fits the strut force as a cubic in leg length; 山海机甲 models the
   strut's progression and velocity dependence; SPR warns that if the compensation is not released during the push,
   "0 N and 450 N give the same jump height", and that the liftoff detector misfired once the strut's vertical component
   was counted as support force. Ascento and 山海机甲 both note the price: retracting the legs in flight means working
   against the spring (Ascento: up to the full 40 N·m).
4. **Gas struts need stops and die without them.** HKUST 2025: "without hard stops the leg can pull the strut apart";
   they moved to polyurethane bumpers. McMaster's own gas springs are rated 6 cycles per minute and 25,000–30,000
   cycles (section 5): lid lifters, not suspension.
5. **Landings are software plus tyre.** Everyone lands on a leg-length PD (RoboMaster: ≈1000 N/m, 100–200 N·s/m; Doggo:
   "low stiffness and lots of damping"), with contact detection from torque or support force (Ascento, Minitaur) and,
   where it is done well, re-extension of the legs before touchdown (山海机甲). The only hardware lever anyone reports
   for the impact itself is the tyre: WIT's pneumatic bike tyre, Go2-W's pneumatic 7-inch, HKUST's 60A hexroll.
6. **What breaks in landings** is the output flange or the gearbox, then the links: HT-04 flanges snapped at 3 × M4 + 3
   pins (HKUST, fixed with a CNC hub on a large bearing); planetary bearings and teeth in wheel gearboxes (SJTU,
   HKUST 2026); link screws loosening and links snapping (南航金城); bicycle-headset joints to stop joint splay (DGUT).
   This matches Wensing: "the highest loads felt in the legs, gearboxes, and other transmission components are
   governed, in large part, by design decisions centered on reflected actuator inertia."

Reflected inertia per joint, for scale (kg·m²): Minitaur 0.0001, Doggo 0.00026, Mini Cheetah ≈0.0023, MIT Cheetah
0.0102, **RS-04 ≈0.024 [estimate]**, HUBO 0.085, Cassie knee ≈0.093 (behind its leaf spring). Per kilogram of robot the
RS-04 is about three times the MIT Cheetah and a third of Cassie.

---

## 3. The physics for our leg

### 3.1 What the motors hold, and the shape of the curve

With 11 kg on one leg (the rig's half robot) the leg holds 86.7 N at the axle (the carriage, less the wheel and half the
wheel link, which the ground carries directly). The quasi-static torque per motor to hold it, through the five-bar's
Jacobian, is nearly flat over the working range **[derived, `sim/leg_spring_study.py` `hold_torque`]**:

| leg length (mm) | 110 | 140 | 170 | 200 | 230 | 250 | 270 | 300 | 330 | 360 | 390 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N·m per motor | 6.6 | 8.6 | 9.8 | 10.2 | 10.2 | 10.0 | 9.6 | 8.8 | 7.5 | 5.5 | 1.7 |

Two consequences. A gravity compensator for this leg wants a **nearly constant torque** from 150 to 300 mm and a
falling one above 330 mm, so a plain torsion spring (torque proportional to angle) is the wrong shape: sized at a
middle height it over-compensates in the crouch (the motors then hold the leg down against it) and keeps pushing at
full extension where gravity needs almost nothing. An **extension spring between the two upper links** has the right
shape because its moment arm about the hips shrinks as the leg folds while its stretch grows: with pins 100 mm out on
each upper link the spring's length runs 276 mm (300 mm leg) → 330 (200) → 347 (140) and it goes slack past 350 mm of
leg, exactly where gravity's demand collapses. A **gas strut on the leg's axis** (hip frame to the wheel axle) needs
just the held weight, 87 N, at every height, but its stroke (291 mm from the deepest crouch to full extension, 2.4:1)
is beyond any stock strut, so it can only cover the upper part of the range.

The rig's steady standing torque is **7.7 N·m per motor** at 300 mm with 11 kg (the "about 9 N·m" quoted before is the
controller's first sample, before the leg settles; the rig's own series settle at 5.1 N·m, see the next paragraph).

**A defect in the rig to fix:** `sim/leg_rig.py` gives the carriage an explicit `<inertial>` (the hip frame) and puts the
2.5 kg dummy mass on a box geom's `mass` attribute. MuJoCo ignores a geom's mass when the body has an inertial
element, so the rig carries **8.5 kg, not 11**: its standing ground force is 84.6 N instead of 108 N, and every load in
`exports/leg/rig-results.json` (1.6 kN on the axle at the 150 mm drop, 160 N·m on the stop) is for 8.5 kg. The study
restores the mass (`build_xml`, `fix_mass`) and keeps a `none_rig85` variant that reproduces the rig as it runs today.
All numbers below are for 11 kg unless they say otherwise.

### 3.2 What a landing does to the gearbox and the knees

At touchdown the wheel stops in the tyre's few milliseconds; the body (on the rail), the links and the motors' rotors
keep going. In joint coordinates the rotors' reflected inertia (0.0243 kg·m² per hip, an estimate: RobStride publishes
none) is 2.4 kg of reflected mass at the axle **per motor**, so the rotors are most of what the tyre has to stop. The
rig (since bc63ce9) measures what matters directly, every step: the torque through each gearbox, τ_motor − I_rotor·α −
b·ω, and the force through each joint (`cfrc_int`: knees, hips, and the apex's constraint). The study records the same
quantities with the same formulas (`peak_gearbox_nm`, `gearbox_over_peak_ms`, `peak_joint_force_n`) and judges every
variant on them. The earlier quasi-static mapping J^T·F of the axle force (143 N·m at 1.6 kN) assumed the hips fixed in
space; the gearbox actually carries about a third of it (62 N·m at the 150 mm drop, 11 kg), because the rest of the axle
force goes straight into the carriage through the links' axial forces (the body decelerates at 9 g in the first
millisecond) and into the lower links' own inertia; for the same reason the knee pins see about 500 N where the
quasi-static mapping of the same axle force gives 1,170 N (the "about 2×" the strength studies now correct for). That is
not an artefact of a soft loop: with the apex constraint four times stiffer (`none_stiffloop`) the numbers barely move
(section 4.3). J^T·F is kept in the drop scan for reference only.

The knees' governing case is not a landing at all but the **undamped power-off collapse**: the leg folds under the
body's weight and the upper links slam into the knee-out stops (the TPU sleeves, then the steel posts), which gives the
rig's 1.8 kN at the knee (8.5 kg) against the 6201s' static safety 1.15 and the knee eye's SF 1.03–1.18. Section 4.5
reports what each spring does to exactly that case.

Two facts follow for the design. The impulse the rotors take is set by the **wheel's absolute velocity** at touchdown,
not by what the leg is doing: if the leg is retracting at v_r as the wheel meets the ground, the wheel's ground speed
is v_body − v_r, and the joint-velocity jump the rotors must absorb is smaller by that amount. And a **parallel spring
cannot change the spike**: it acts between body and wheel in parallel with the motors, and an impulse does not see a
spring (Penn: "the spring constant, k, does not appear in [the collision]"; Wensing: series compliance "redistributes
some of the impact impulse to a window of time following impact … [it does] not change the initial impulse"). Only
series compliance between the wheel and the links (the tyre, an elastomer axle mount) stretches the spike in time.

### 3.3 The variants modelled

The rig's MJCF comes unchanged from `sim.leg_rig.mjcf()`; `sim/leg_spring_study.py` edits the XML per variant and
runs the rig's own virtual-model controller, torque-speed and 60 N·m clipping, and TPU stop torques, on every variant.

| Variant | What it is | How it is modelled |
|---|---|---|
| `none` | today's leg, solid BotWheel tyre, 11 kg | the rig with its dummy mass restored |
| `none_rig85` | the rig exactly as it runs today | 8.5 kg carried |
| `torsion_mid`, `torsion_stiff`, `torsion_preload` | torsion springs round both hips: 3.5 N·m/rad carrying the weight at 250 mm; 10 N·m/rad; 3.5 N·m/rad preloaded to 1.5× | hinge `stiffness` + `springref` on motor_f / motor_r |
| `ext_links`, `ext_links_soft` | an extension spring between pins 100 mm out on both upper links, 2.3 and 1.15 N/mm, free length fitted to carry the weight at 250 mm | a spatial tendon between two sites; the force law (free length, initial tension) applied in the loop from the tendon's length and site Jacobians |
| `ext_5108N807`, `ext_5108N807_c` | the real McMaster spring (section 5), with and without the controller cancelling it | as above, k 1.576 N/mm, free length 228.6 mm, 27 N initial tension |
| `strut_gas`, `strut_gas70`, `strut_gas130`, `strut_gas_c`, `strut_4138T168` | a gas strut from a mount 60 mm above the hip line, between the motors, to the wheel axle: 100 %, 70 % and 130 % of the held weight; the real McMaster 20 lbf strut | constant force with +20–30 % progression, 20 N·s/m seal friction, an extension stop, and a pin-in-slot lower mount so the strut is parked below its stroke (engaged above ≈190–213 mm of leg) |
| `strut_coil`, `strut_coil_light` | a coil-over on the same line, 1.5 N/mm carrying the weight at 300 mm, with and without a 150 N·s/m damper | compression spring, pushes only, coil bind at 180 mm of travel |
| `tyre_pneumatic`, `tyre_foam` | a softer tyre, about a third and a fifth of the solid tyre's rate | the tyre contact's `solref` 13 ms / 0.5 and 18 ms / 0.4 (the rig's solid tyre is 7.7 ms / 0.7) |
| `bushing`, `bushing_soft` | rubber mounts between the loop's apex and the wheel, 500 and 150 N/mm planar | a sprung two-slide carrier (±8 mm) between the wheel link and the wheel |
| `fw_retract`, `fw_retract_tyre` | firmware only: the leg retracts at 0.8 m/s through touchdown; the same on the pneumatic tyre | the leg-length command ramps down 60 mm before the expected touchdown |
| `*_c` | the controller knows the spring law and subtracts it (feed-forward), as HKUST and Tongji do | τ_cmd = τ_vmc − τ_spring(q) |
| `none_deep`, `strut_gas_deep` | jumping from a 120 mm crouch instead of 150 | pre-compress and release |

Scenarios, all at 0.5 ms with every step recorded: standing at 300, 200 and 140 mm (motor torque, I²R as a fraction of
the rated loss and in watts at an assumed 0.16 Ω); a jump at the 60 N·m cap and at 120 N·m (height, spring energy
stored and returned, motor work); drops from 25 to 300 mm with the leg holding 300 mm (axle force, J^T F, gearbox
torque, dynamic and quasi-static knee forces); a moving belt with a 20 or 40 mm bump or kerb at 1 and 2 m/s (body
acceleration, wheel load, airborne time); power loss with and without the RS-04's assumed anti-backdrive damping (where
the leg rests, the stop impact). The sweeps (`sweep-torsion.json`, `sweep-strut.json`, `sweep-ext.json`) cover rate ×
preload, 25 points per family, on standing, the jump, the 150 mm drop, power-off and the 40 mm bump.

---

## 4. Results

All from `exports/leg/springs/results.json` (one leg, 11 kg carried, 0.5 ms steps, every step recorded; figures
`scorecard.png`, `static-curves.png`, `drop-scan.png`, `impact-150.png`, `ride.png`, `sweep-*.png`; videos
`<variant>_<scenario>.mp4`). "Today" is `none`; `none_rig85` is the rig as it runs today with 8.5 kg.

### 4.1 Standing: torque and heat

| Variant | motor torque at 300 / 200 / 140 mm (N·m) | copper loss at 300 mm, fraction of the rated 40 N·m loss | W per motor at 0.16 Ω |
|---|---|---|---|
| `none` (today, 11 kg) | 7.7 / 8.3 / 7.0 | 3.7 % | 6.4 |
| `none_rig85` (the rig today, 8.5 kg) | 5.2 / 5.4 / 4.7 | 1.6 % | 2.9 |
| `torsion_mid` (3.5 N·m/rad) | 1.6 / 1.3 / 2.6 | 0.2 % | 0.3 |
| `ext_5108N807` (the real spring, uncancelled) | 1.2 / 0.6 / 2.1 | 0.1 % | 0.1 |
| `ext_5108N807_c` (cancelled by the controller) | 0.2 / 0.3 / 3.0 | 0.0 % | 0.0 |
| `strut_gas` / `strut_4138T168` (parked below ≈200 mm) | 0.8 / 3.1 / 7.5 | 0.1 % | 0.1 |
| `strut_coil` (coil-over) | 2.5 / 9.0 / 16.5 | 0.4 % | 0.6 |

Standing is not hot today: at 7.7 N·m the RS-04 runs at 3.7 % of its rated copper loss (3.7 A rms), about 6 W per motor,
26 W for four, against the 175 W the rated point dissipates. The spring removes 85–97 % of that, which is a runtime
gain of the order of 25 W whenever the robot is up, not a thermal rescue; HKUST's HT-04s at 6–7 N·m were a thermal
rescue because those motors are smaller. The gas strut and the coil-over over-compensate or vanish in the crouch
(the slot parks the strut below 200 mm; the coil-over pushes 16.5 N·m at 140 mm), so only the between-links spring
and the mid torsion spring help at every height.

### 4.2 Jumps

| Variant | jump at the 60 N·m cap (mm) | at 120 N·m (mm) | spring energy returned at liftoff (J) | motors' push work (J) |
|---|---|---|---|---|
| `none` | 278 | 296 | 0 | 29 |
| `none_deep` (120 mm crouch) | 314 | 322 | 0 | 36 |
| `torsion_mid` | 291 | 317 | 4.5 | 26 |
| `torsion_preload` (1.5×) | 298 | 321 | 6.2 | 24 |
| `ext_5108N807` | 300 | 329 | 3.5 | 27 |
| `ext_5108N807_c` | **317** | **334** | 3.6 | 31 |
| `ext_links_c` (2.3 N/mm, cancelled) | 323 | 333 | 4.1 | 30 |
| `strut_gas` / `strut_4138T168` | 294 / 292 | 318 / 317 | 2.7 / 0.5 | 29 |
| `strut_gas_deep` (120 mm crouch) | 332 | 349 | 0.2 | 36 |
| `strut_coil` / `strut_coil_light` | 149 / 234 | 169 / 257 | 6.5 / 6.9 | 20 / 21 |
| `tyre_pneumatic` / `tyre_foam` | 282 / 282 | 297 / 298 | 0 | 30 / 31 |

The real spring, cancelled by the controller so the crouch tracks cleanly, is worth +39 mm at the cap (+14 %) and
+38 mm at 120 N·m (+13 %): the 3.6 J it returns during the 0.25 s push is 12 % of the motors' own push work. Doubling
the preload (`torsion_preload`) returns 6.2 J but jumps no higher, because the stiffer leg loses it in the push
profile. The coil-over is a disaster (over-compensation in the crouch, and a damper eats half of what is left: 149 mm).
A deeper crouch is the bigger lever (+36 mm) and the two add. For comparison the main session's earlier figure, 245 mm at
the cap, was the 8.5 kg rig (`none_rig85`: 248 mm here).

### 4.3 Landings

The 150 mm drop, 11 kg, the leg holding 300 mm (touchdown at 1.48 m/s, 16 J per leg); the 300 mm drop (2.16 m/s, 32 J);
and the landing of the robot's own 60 N·m jump (an apex of 278 mm, touchdown at 2.38 m/s):

| Variant | 150 mm: axle (N), gearbox (N·m), knee (N) | 300 mm: axle, gearbox, knee | jump-60 landing: axle, gearbox, knee | drop at which the gearbox reaches 120 N·m or the knee 1,854 N |
|---|---|---|---|---|
| `none` | 1,835, 62, 494 | 2,622, 88, 709 | 2,380, 92, 719 | >300 mm (88 N·m, 754 N at 300) |
| `none_stiffloop` | 1,885, 64, 516 | 2,696, 92, 742 | 2,461, 96, 747 | >300 |
| `torsion_mid` | 2,205, 60, 668 | 3,361, 89, 1,084 | 2,474, 85, 698 | >300 |
| `torsion_preload` | 2,873, 62, 998 | 6,102 (lands on its stop), 38, 3,270 | 2,528, 80, 700 | knee at 216 mm |
| `ext_5108N807_c` | 1,873, 58, 507 | 2,684, 85, 729 | 2,537, 89, 766 | >300 |
| `strut_gas` | 2,099, 59, 646 | 3,040, 86, 953 | 2,405, 81, 675 | >300 |
| `tyre_pneumatic` | **1,338, 45, 361** | 1,910, 64, 516 | 1,760, 81, 600 | >300 |
| `tyre_foam` | **1,063, 39, 298** | 1,515, 54, 422 | 1,400, 75, 556 | >300 |
| `bushing_soft` (150 N/mm axle mounts) | **1,128, 52, 386** | 1,602, 74, 544 | 1,627, 91, 686 | >300 |
| `fw_retract` (0.8 m/s through touchdown) | 1,504, 64, 472 | 2,147, 87, 645 | 2,380, 92, 719 | >300 |
| `fw_retract_tyre` | 1,192, 52, 385 | 1,674, 71, 519 | 1,760, 81, 600 | >300 |

(Knee, hip and apex forces per scenario, the quasi-static comparators and the full drop scans from 25 to 300 mm are
in `results.json` → `scenarios` and `landing`; at 150 mm the hips see 406 N and the apex 759 N on today's leg.)

Three things stand out. **No parallel spring reduces the spike**; most raise it a little (a stiffer leg), and the
preloaded torsion spring, which extends the leg onto its stop in the air, makes the 300 mm drop a 6 kN stop impact.
**Only series compliance and firmware reduce it**: a pneumatic-stiffness tyre takes 27 % off the axle force and the
gearbox torque, a foam tyre 42 %, soft axle mounts 39 %, retracting through touchdown 18 %, retracting onto the
pneumatic tyre 35 %. **The gearbox is not the limit on the rig's own measure**: 62 N·m at 150 mm, 88 N·m at 300 mm
(`none`), under the RS-04's 120 N·m with every variant and never above it for any time; the quasi-static J^T·F that
first raised the alarm reaches 120 N·m at an 80 mm drop, but it is the wrong measure for a spike that the carriage and
the links share. The drop scan (`drop-scan.png`) is linear in touchdown speed for every variant, so the numbers scale:
each 1 m/s of touchdown speed is ≈1.2 kN on the axle and ≈40 N·m on the gearbox today, ≈0.9 kN and ≈30 N·m on the
pneumatic tyre.

### 4.4 Ride over bumps and kerbs

Peak body acceleration (g) on the moving belt, 1.15 s window round the obstacle:

| Variant | 20 mm bump, 1 m/s | 40 mm bump, 1 m/s | 20 mm bump, 2 m/s | 40 mm bump, 2 m/s | 20 mm kerb, 1 m/s | 40 mm kerb, 1 m/s | 40 mm kerb, 2 m/s |
|---|---|---|---|---|---|---|---|
| `none` | 11.9 | 3.7 | 6.2 | 4.8 | 11.7 | 2.4 | 4.8 |
| `ext_5108N807` (uncancelled) | 15.2 | 5.0 | 8.6 | 5.4 | 14.9 | 2.7 | 6.0 |
| `ext_5108N807_c` | 11.7 | 3.8 | 6.2 | 4.5 | 11.6 | 2.2 | 4.5 |
| `torsion_mid` | 16.8 | 7.6 | 9.9 | 7.3 | 16.2 | 3.0 | 6.1 |
| `torsion_preload` | 21.0 | 24.5 | 27.2 | 36.5 | 21.2 | 12.0 | 24.2 |
| `strut_gas` / `strut_gas_c` | 16.2 / 11.4 | 6.2 / 3.5 | 9.4 / 6.3 | 6.4 / 4.4 | 15.9 / 11.4 | 2.8 / 2.2 | 6.1 / 4.5 |
| `tyre_pneumatic` | **7.3** | **2.5** | **4.1** | **3.3** | **7.3** | **1.6** | **3.2** |
| `tyre_foam` | 5.0 | 2.0 | 3.0 | 2.5 | 5.1 | 1.2 | 2.5 |
| `bushing_soft` | 5.9 | 3.0 | 3.2 | 3.4 | 5.9 | 3.7 | 3.4 |

The RMS over the window is 0.4–0.9 g for every variant but the preloaded torsion spring: the ride is the leg's own PD
(3,000 N/m on 11 kg is a 2.6 Hz suspension), and a hardware spring only changes it by adding stiffness the controller
did not ask for (`ext_5108N807` uncancelled: +25 % on the peaks; cancelled: within 0.3 g of today). The sharp peaks
are the tyre's: a small sharp bump at 1 m/s is the harshest case (11.9 g for 0.17 s of flight) and the pneumatic-stiffness
tyre takes 35–40 % off it, the foam tyre 50 %. The preloaded torsion spring, sitting on its extension stop, turns the
leg rigid (24–37 g). The soft axle mounts help on bumps but bottom on the 40 mm kerb (3.7 g against 2.4).

### 4.5 Power loss: the collapse

Standing at 300 mm, then the motors lose power. Undamped, today's leg folds under the body and the upper links hit
the knee-out stops; with the RS-04's assumed anti-backdrive damping (20 % of shorted phases) it sinks onto them.
The rig's own measures, every step (`peak_joint_force_n`, `peak_gearbox_nm`):

| Variant | what the unpowered leg does | knee (N) | hip (N) | apex (N) | stop torque (N·m) | gearbox (N·m) | body speed (m/s) | damped: knee (N), stop (N·m) |
|---|---|---|---|---|---|---|---|---|
| `none_rig85` (the rig today, 8.5 kg) | folds onto the knee-out stops at 99 mm | **1,747** | 1,698 | 1,692 | 169 | 80 | 1.51 | 94, 6 |
| `none` (11 kg) | the same | **2,405** | 2,360 | 2,374 | 194 | 72 | 1.60 | 200, 13 |
| `tyre_pneumatic` / `tyre_foam` | the same | 2,385 / 2,504 | 2,341 / 2,460 | | 192 / 212 | 75 / 77 | 1.60 | 199 / 198, 13 |
| `bushing_soft` | the same, the mounts cushion it | 1,182 | 1,157 | 1,206 | 166 | 98 | 1.61 | 154, 11 |
| `ext_5108N807` | **stays up at 310–324 mm; no stop is touched** | **52** | 48 | 57 | 0 | 0 | 0.05 | 50, 0 |
| `ext_5108N807_c` | stays at 302 mm | 54 | 50 | 59 | 0 | 0 | 0.00 | 54, 0 |
| `ext_links` (2.3 N/mm) | stays up, bouncing 272–319 mm | 691 | 653 | 743 | 105 | 30 | 0.79 | 53, 0 |
| `torsion_stiff` | stays up, 278–324 mm | 62 | 59 | 67 | 0 | 0 | 0.1 | 55, 0 |
| `torsion_mid` | **extends to the knee-in stops at 392 mm** | 581 | 612 | 430 | 134 | 87 | 0.4 | 87, 13 |
| `torsion_preload` | sits on the knee-in stops already | 40 | 36 | 47 | 12 | 1 | 0.01 | 40, 11 |
| `strut_gas` (100 %) | stays up, 332–384 mm | 87 | 82 | 15 | 4 | 2 | 0.1 | 87, 0 |
| `strut_gas70` | folds onto the knee-out stops | 1,651 | 1,643 | 1,226 | 194 | 83 | 0.83 | 71, 0 |
| `strut_gas130`, `strut_4138T168` | extend to the knee-in stops | 274 / 91 | 280 / 86 | 263 / 6 | 59 / 0 | 38 / 0 | 0.3 / 0.15 | 110 / 91, 0 |

Three results. First, the rig's 1.8 kN is confirmed (`none_rig85`: 1,747 N at the knee, 169 N·m on the stop) and it
is an 8.5 kg number: with the 2.5 kg restored the same collapse puts **2.4 kN** on the knee and 194 N·m on the stop,
a third more than the strength studies' load case, which would take the knee eye from SF 1.03–1.18 to about 0.8 and the
6201s from 1.15 to about 0.85. Second, **the 5108N807 removes the case**: with gravity carried by the spring the
unpowered leg settles where the spring's torque equals the body's, 302–324 mm, touches no stop, and the knee sees
52 N, the static load; damped or undamped. The worst knee load left on that leg is the landing of a full 120 N·m
jump, 1,068 N (`jump120`), 45 % of today's collapse and 59 % of the 1.8 kN the knees are sized for; the next is the
20 mm kerb at 1 m/s, 809 N. Third, the preload decides which way a spring-loaded leg goes: a spring that carries more
than the weight at full extension (`torsion_mid`, the 130 % strut, the real 20 lbf strut, which is 26 lbf compressed)
drives the leg *up* onto the knee-in stops, 134 N·m for the torsion spring; a spring that carries less than the weight
everywhere (`strut_gas70`) still folds onto the knee-out stops. The 5108N807 is in between by construction: it is slack
above a 345 mm leg, so it cannot extend the leg, and it carries 0.9 of the weight at 300 mm, so it cannot drop it.

A spring does not make the knee stronger. A kid can still push the body down onto the stops, the robot can still fall
onto a folded leg, and the spring can break; the collapse case should stay in the strength studies as a rare case at
11 kg (2.4 kN). What the spring does is turn an everyday event (every power cut, every soft e-stop) into a rare one.

A note on the gearbox: across every scenario on today's leg its worst load is not a landing but the **20 mm sharp
edge at 1 m/s** (the bump and the kerb both: 104 N·m, with 3.8 kN on the tyre for a few milliseconds) and the full
120 N·m push itself (102 N·m); the 300 mm drop is 93 N·m, the collapse 72 N·m. Nothing exceeds 120 N·m for any time
except the stiff axle bushing in the 120 N·m jump (1.5 ms). The pneumatic-stiffness tyre takes the kerb figure to
70 N·m and the foam tyre to 50 N·m.

### 4.6 Balance control: what the spring adds

Static, at 300 mm, from the spring's force mapped to the wheel (`results.json` → `static`): the 5108N807 adds
−305 N/m along the leg (its force falls as the leg extends; the controller's virtual spring is 3,000 N/m) and 2.4 N·m
of lean torque at 15° of lean (the lean loop applies 39 N·m there); the 2.3 N/mm `ext_links` adds −810 N/m and 2.0 N·m;
`torsion_mid` +200 N/m and −4.6 N·m; the gas strut −90 N/m and −1.2 N·m. The worst torque the motors still have to
supply between 150 and 340 mm falls from 10.3 N·m (today) to 4.4 N·m (5108N807), 2.4 N·m (`torsion_mid`) and
6.9 N·m (`ext_links`). All of it is a smooth, known function of the two motor angles, and the `_c` runs show that once
the controller subtracts it the leg behaves as today in every scenario that does not saturate the motors.

### 4.7 The sweeps: rate × preload

Each family on a 5 × 5 grid of rate and preload (the fraction of the held weight the spring carries at 250 mm),
each point run through standing, the 60 N·m jump, the 150 mm drop, the collapse (undamped and damped) and the 40 mm
bump; maps in `sweep-torsion.png`, `sweep-strut.png`, `sweep-ext.png`, numbers in `sweep-*.json`. Cells below read:
standing torque at 300 mm (N·m) / worst torque left 150–340 mm (N·m) / jump at 60 N·m (mm) / collapse knee force,
undamped (N) / power-off rest length, damped (mm) / 40 mm bump at 1 m/s, peak body g. Today's leg is 7.7 / 10.3 / 278
/ 2,405 / 101 / 3.7.

**Torsion springs at the hips (N·m/rad):**

| rate \ preload | 0.5 | 0.75 | 1 | 1.25 | 1.5 |
|---|---|---|---|---|---|
| 2 | 3.4 / 5.0 / 289 / 1,428 / 127 / 4.5 | 0.6 / 2.5 / 298 / 50 / 325 / 5.9 | 2.3 / 2.2 / 295 / 645 / 392 / 8.2 | 5.5 / 4.7 / 297 / 512 / 392 / 15.9 | 1.5 / 7.2 / 299 / 43 / 392 / 26.4 |
| 3.5 | 3.9 / 5.0 / 292 / 1,278 / 137 / 4.6 | 1.2 / 2.5 / 294 / 119 / 274 / 5.7 | 1.6 / 2.4 / 291 / 581 / 392 / 7.6 | 4.5 / 4.9 / 292 / 471 / 392 / 12.1 | 1.5 / 7.4 / 298 / 40 / 392 / 25.8 |
| 6 | 4.7 / 5.2 / 280 / 1,072 / 153 / 4.2 | 2.1 / 2.7 / 287 / 117 / 227 / 4.9 | 0.5 / 3.5 / 288 / 402 / 352 / 6.6 | 3.1 / 6.0 / 289 / 588 / 392 / 9.3 | 5.8 / 8.5 / 288 / 487 / 392 / 17.0 |
| 10 | 5.8 / 6.4 / 281 / 261 / 174 / 3.9 | 3.4 / 3.9 / 281 / 118 / 225 / 4.4 | 1.0 / 5.2 / 287 / 53 / 319 / 5.3 | 1.4 / 7.8 / 286 / 334 / 381 / 6.8 | 3.8 / 10.3 / 285 / 563 / 392 / 9.7 |
| 15 | 7.0 / 8.7 / 271 / 183 / 193 / 3.8 | 4.8 / 6.1 / 276 / 122 / 232 / 4.9 | 2.5 / 7.4 / 280 / 75 / 281 / 4.9 | 0.3 / 9.9 / 278 / 50 / 327 / 5.5 | 1.9 / 12.4 / 276 / 59 / 368 / 6.7 |

The torsion family's sweet spot is soft and under-preloaded: 2–3.5 N·m/rad at 0.75× the weight (standing
0.6–1.2 N·m, +16–20 mm of jump, the unpowered leg resting at 274–325 mm with 50–119 N on the knee). Everything
above 1× drives the unpowered leg onto its extension stop (rest at 392 mm) and, uncancelled, stiffens the ride up to
26 g on the 40 mm bump; everything stiffer than 6 N·m/rad jumps lower than no spring at all. The jump gain never
exceeds +21 mm (+8 %) in this family, less than the between-links spring's +39 mm, because a torsion spring's torque
keeps rising into the crouch where the five-bar needs less.

**A strut on the leg's axis (hip frame to axle), N/m; 0 = a gas strut, on a 200 mm stroke with a lost-motion slot:**

| rate \ preload | 0.5 | 0.75 | 1 | 1.25 | 1.5 |
|---|---|---|---|---|---|
| 0 (gas) | 3.3 / 10.1 / 280 / 1,937 / 101 / 4.4 | 1.1 / 10.1 / 282 / 447 / 311 / 5.3 | 0.8 / 10.1 / 294 / 87 / 354 / 6.2 | 2.6 / 10.1 / 269 / 269 / 385 / 7.2 | 4.0 / 10.1 / 268 / 334 / 391 / 8.1 |
| 500 | 6.7 / 7.2 / 253 / 399 / 191 / 3.5 | 4.7 / bind / 255 / 376 / 233 / 3.9 | 2.8 / bind / 212 / 86 / 276 / 4.3 | 1.1 / bind / 128 / 76 / 319 / 5.1 | 0.7 / bind / 66 / 85 / 336 / 5.6 |
| 1,000 | 8.4 / 8.8 / 237 / 345 / 218 / 3.5 | 7.2 / 8.2 / 239 / 414 / 240 / 3.5 | 5.4 / 10.5 / 242 / 491 / 262 / 3.7 | 3.7 / bind / 245 / 94 / 283 / 4.0 | 2.1 / bind / 241 / 83 / 305 / 4.4 |
| 2,000 | 8.4 / 16.4 / 220 / 390 / 233 / 3.5 | 8.4 / 18.7 / 222 / 458 / 244 / 3.5 | 8.4 / 21.0 / 224 / 511 / 255 / 3.5 | 7.9 / 23.3 / 222 / 515 / 266 / 3.5 | 6.5 / 25.5 / 220 / 115 / 277 / 3.5 |
| 4,000 | 8.4 / 37.4 / 207 / 436 / 241 / 3.5 | 8.4 / 39.7 / 200 / 488 / 246 / 3.5 | 8.4 / 42.0 / 200 / 517 / 252 / 3.5 | 8.4 / 44.2 / 197 / 548 / 257 / 3.5 | 8.4 / 46.5 / 194 / 545 / 263 / 3.5 |

("bind" = the coil-over reaches its coil bind in the crouch, hundreds of N·m.) Only the gas strut at exactly the
weight is any good here (standing 0.8 N·m, +16 mm of jump, the unpowered leg held at 354 mm), and its worst residual
stays at today's 10.1 N·m because the slot parks it below 200 mm; 70 % still folds the leg (1,937 N at the knee), 125 %
and up extends it onto the stop. Every coil-over is worse than no spring: it over-compensates the crouch (standing
torque rises again above 1 N/mm) and the jump collapses (66–255 mm).

**An extension spring between the upper links, pins 100 mm out (N/m; the 5108N807 is 1,576 N/m at ≈1.0):**

| rate \ preload | 0.5 | 0.75 | 1 | 1.25 | 1.5 |
|---|---|---|---|---|---|
| 1,000 | 4.5 / 6.4 / 294 / 1,900 / 101 / 4.0 | 1.2 / 5.5 / 303 / 846 / 304 / 5.2 | 2.1 / 4.6 / 307 / 892 / 374 / 6.8 | 5.3 / 5.2 / 318 / 301 / 392 / 10.7 | 1.5 / 8.9 / 325 / 42 / 392 / 26.7 |
| 1,500 | 5.9 / 8.0 / 296 / 1,923 / 101 / 3.6 | 3.0 / 5.2 / 295 / 1,081 / 236 / 4.3 | **0.1 / 4.2 / 304 / 49 / 328 / 5.2** | 2.8 / 3.4 / 308 / 894 / 364 / 6.6 | 5.3 / 6.6 / 319 / 277 / 384 / 9.8 |
| 2,300 | 8.1 / 8.8 / 281 / 1,833 / 101 / 3.7 | 5.3 / 7.5 / 288 / 1,075 / 219 / 3.6 | 2.8 / 6.9 / 296 / 691 / 296 / 4.0 | 0.3 / 2.8 / 300 / 48 / 327 / 4.8 | 2.2 / 5.2 / 310 / 56 / 347 / 5.4 |
| 3,500 | 8.1 / 9.1 / 273 / 1,677 / 101 / 3.7 | 8.1 / 8.4 / 284 / 1,141 / 233 / 3.7 | 5.6 / 8.0 / 287 / 889 / 273 / 3.6 | 3.5 / 7.5 / 290 / 737 / 298 / 3.6 | 1.4 / 6.9 / 292 / 55 / 317 / 4.0 |
| 5,000 | 8.1 / 9.4 / 273 / 1,577 / 201 / 3.7 | 8.1 / 9.1 / 267 / 965 / 241 / 3.7 | 8.1 / 8.8 / 278 / 817 / 264 / 3.7 | 6.4 / 8.4 / 280 / 798 / 281 / 3.6 | 4.6 / 8.0 / 286 / 924 / 296 / 3.6 |

The real spring sits in the best cell: 1,500 N/m carrying the weight at 250 mm gives 0.1 N·m standing, +26 mm of jump
uncancelled (+39 cancelled, section 4.2), a 49 N collapse with the leg parked at 328 mm, and 5.2 g on the bump
uncancelled (today's 3.7 once cancelled). Softer and more preloaded springs jump higher (up to +47 mm at 1,000 N/m and
1.5×) but extend the leg onto its stop when unpowered and make the uncancelled ride harsh; stiffer springs lose the
jump and no longer hold the leg up (the knee is back at 0.8–1.9 kN). Across all three families the rule is the same:
carry about the weight at mid-height with as soft a spring as the stroke allows, and never more than the weight at full
extension.

---

## 5. Real parts (McMaster-Carr pages read one at a time on 2026-10-27)

What McMaster stocks, from the category tables and the product pages (`exports/leg/springs/mcmaster/*.page.json`):

**Extension spring for the between-links layout: [5108N807](https://www.mcmaster.com/5108N807/)** (music-wire steel,
loop ends; [5667N275](https://www.mcmaster.com/5667N275/), $15.15, is the same spring with hook ends, which McMaster
says are more likely to slip off or break, so the loop-end part is the one to buy): 9 in
(228.6 mm) long, 1 in (25.4 mm) OD, 0.125 in (3.18 mm) wire, **9 lbf/in (1.58 N/mm)**, 6.11 lb (27 N) initial tension,
67.87 lb (302 N) at the 15.84 in (402 mm) maximum extended length; $14.80 each; "Not Rated" tolerances. With its loops
on pins 100 mm out on the two upper links it is stretched 47 mm at a 300 mm leg (101 N, 0.9 of the held weight), 101 mm
at 200 mm (187 N, 0.8) and 118 mm at 140 mm (213 N, 0.43), 173 mm short of its maximum extension at the deepest
crouch, and slack above a 345 mm leg. Mass ≈0.3 kg [estimate: 68 coils of 3.2 mm wire on a 22 mm mean diameter].
Fatigue [estimate]: the uncorrected shear stress at the maximum rated load is 8·F·D/(π·d³) = 530 MPa, 645 MPa with the
Wahl factor for C = 7, about 34 % of music wire's ≈1,900 MPa tensile at this diameter, which is the edge of the usual
infinite-life band for unpeened steel springs; at our working stretch (47–101 mm, 101–187 N) it is 11–20 % and the
body of the spring will outlive the robot. The loops are the weak point of any extension spring (McMaster: loop ends
"won't slip off" but hooks and elongated hooks "are more prone to breaking if overstretched"), so the pins must be
round, 6–8 mm, and the loops must never be loaded sideways. McMaster's metric extension springs stop at 39 mm long and
its 12 lbf/in springs at 6 in, so this is the only stock spring that fits; the 10 lbf/in [5108N79](https://www.mcmaster.com/5108N79/)
(6 in, 1 in OD, 54.3 lb at 10.97 in) is the alternative if the pins move to 60–70 mm.

**Gas struts: [4138T168](https://www.mcmaster.com/4138T168/)** (20 lbf extension force, 26 lbf compressed, 18.5 in
extended, 10.74 in compressed, 7.76 in (197 mm) stroke, 0.709 in body, M6 rod thread, ball-socket ends, 5/16"-18 ball
studs, $31.93) and **[4138T193](https://www.mcmaster.com/4138T193/)** (the same at 23.03 in / 13.19 in / 9.84 in
stroke, $27.47). Both pages say **"Maximum Cycles per Minute: 6 cpm", "Maximum Cycles: 30,000"**, "Mounting Position:
Rod Down", nitrogen gas with oil, rubber seals, −13 to 176 °F. Six cycles a minute is a hatch, not a leg: a leg that
squats, hops and rides bumps cycles a strut several times a second and would use up 30,000 cycles in days. The
adjustable-force family ([6465K](https://www.mcmaster.com/products/springs/gas-springs-1~/adjustable-force-gas-springs~~/),
a bleed valve to set the force, 90 lbf and up, cycles "Not Rated", $77–92) and the sealless "long-life gas-spring-style
mechanical springs" ([1268N](https://www.mcmaster.com/products/springs/gas-springs-1~/long-life-gas-spring-style-mechanical-springs~~/),
25–30 lbf at 15.58 in with only a 4 in stroke, $152–165) do not fit either: too strong, too short a stroke, or both.

**Torsion springs:** McMaster's largest stock torsion spring, [9271K118](https://www.mcmaster.com/9271K118/) (1.102 in
OD, for a 0.666 in shaft, 0.135 in wire, 4 in legs), gives 42.86 in·lbf (4.84 N·m) at its full 90° and wraps a 17 mm
shaft. A hip spring here has to wrap the Ø72 output journal and give 10 N·m at about 50° of deflection: nothing in
the catalogue, so a torsion-spring hip means a custom spring (or a clock spring) and a seat machined into the hip frame.
The torsion variants in the simulation are therefore a bound on what such a spring could do, not a part.

**Compression springs (for a coil-over):** the metric table (DIN 2095/2098 music wire, [94125K](https://www.mcmaster.com/products/springs/compression-springs-1~/system-of-measurement~metric/))
goes to 31 N/mm in short springs; a coil-over on the leg's axis needs a guided 1.5 N/mm spring with 180 mm of travel,
which would be a bicycle-shock-class part, not a catalogue spring. Not pursued.

**Tyres and axle mounts** are not McMaster parts: the BotWheel's solid tyre is part of the hub motor. A softer tyre
means a different wheel (or a cut-down, grooved tread), and a compliant axle mount means elastomer sandwich mounts between
the wheel's 4 × M6 flange and the wheel link's foot, which is a CAD change rather than a part choice (section 7).

---

## 6. Trade-offs, plainly

**Added mass and complexity.** The between-links extension spring is one $15 part, ≈0.3 kg, two Ø8 pins with
bosses on the upper links, a sleeve, and a two-line feed-forward in the controller: +0.35 kg per leg, 0.7 kg on a
26 kg robot (3 %), and one more part to look at when the leg is serviced. A gas strut is 0.45 kg plus two ball-stud
mounts, a slot and bumpers, a part rated 6 cycles a minute, and a controller that must also decide when to stop
cancelling it (SPR's "0 N and 450 N give the same height"). Torsion springs at the hips are a custom spring and a seat
machined into the hip frame. A softer tyre is a different wheel; elastomer axle mounts are four small parts, a carrier,
and ±8 mm of wheel wobble the controller never sees.

**Stored energy and pinch points.** The 5108N807 stores ≈3 J at the standing height (47 mm of stretch) and ≈11 J at the
deepest crouch (118 mm); the fall energy of one leg's share of the robot from 150 mm is 16 J, so the spring never holds
more than the leg already does in a hop. It sits in the upper links' own layer, inside the leg's silhouette, but a
stretched coil spring is a finger trap between its coils: it needs a sleeve (a split TPU tube or a fabric sleeve) and
loops that cannot be reached from outside. The five-bar's own scissor pinch between the upper links and the hip frame
exists with or without the spring. A preloaded spring is also a leg that can move by itself: `torsion_mid`,
`torsion_preload` and the 130 % strut all drive an unpowered leg to the fully-extended stop (section 4.5), which is a
robot that suddenly stands up tall when it is switched off; the 5108N807 at 100 mm pins settles the leg at ≈300 mm
and goes slack above 345 mm, so it cannot do that.

**Fatigue.** The 5108N807's body runs at 11–20 % of its wire's tensile strength in the working range (34 % at its
rated maximum, which the leg reaches only in the deepest crouch): infinite life for the coils; the loops are where
extension springs fail, so the pins are round, the spring stays in one plane, and it is inspected like a tyre. The
McMaster gas struts are rated 25,000–30,000 cycles at 6 cycles a minute; a leg that squats, hops and rides bumps would
spend that in weeks. TPU stop sleeves and the tyre age too, but they age today.

**The nonlinear torque through the five-bar.** The spring's hip torque is T(ℓ)·∂ℓ/∂φ with ℓ the pin-to-pin distance,
a smooth function of the two motor angles that the controller computes from its own encoders (HKUST subtracts it
"directly, without affecting other tuning"; Tongji fits a cubic). Uncancelled, the 5108N807 adds −305 N/m along the leg
at 300 mm (10 % of the controller's 3,000 N/m, and in the softening direction) and 2.4 N·m of lean torque at 15° (6 % of
the lean loop's 39 N·m): the balance loop would not notice, and cancelled it sees today's plant (the `_c` rows ride
within 0.3 g of `none`). The two things to get right in firmware are the liftoff detector (do not count the spring's
force as ground support: SPR's bug) and the slack point (above a 345 mm leg the spring's force is zero, a kink the
feed-forward must include).

**Jump strategy.** Pre-compress and release is just the crouch: the motors stretch the spring slowly while crouching
(≈2 N·m extra over 0.5 s, nothing) and it gives 3.5–4.5 J back during the 0.25 s push, when the motors' torque-speed
line is the bottleneck. That is +14 % at the 60 N·m cap and +13 % at 120 N·m. A stronger spring returns more (6.2 J at
1.5× preload) but over-compensates the crouch, so the motors hold the leg down between jumps, and it extends the leg on
power-off; the sweeps (section 4.7) show the jump gain flattening past 1× while those costs grow. The crouch depth is
the bigger lever: 120 mm instead of 150 mm is +36 mm on its own, and the two add (`strut_gas_deep` 332 mm).

**What is cheaper in firmware.** The landing spike: a touchdown-speed cap and retracting the leg through touchdown
(−18 % axle force for nothing). The ride: the RMS body acceleration is the leg's PD, not hardware, and a lower virtual
stiffness with feed-forward does more than any spring; only the sharp peaks over small bumps need a softer tyre. The
collapse: the RS-04's own anti-backdrive damping, if it is what the manual implies, turns a 194 N·m stop hit into
14 N·m, but it is a firmware feature of a motor that has lost power, so the spring is the only thing that holds the
leg up unpowered. The standing heat and the jump gain cannot be had in firmware: the motors must carry the body unless
something else does.

---

## 7. Recommendation (superseded in part by section 8: the between-links spring of item 1 fails in 3-D; the knee-to-knee
layout and the no-spring fallback are weighed there)

**Build this.**

1. **One McMaster 5108N807 extension spring per leg between the two upper links**, its loops on Ø8 steel pins
   100 mm from each hip axis, in the upper links' own layer (y 0–30 mm), with a split sleeve over the coils, and the
   controller subtracting its torque from the two motor angles (`ext_5108N807_c`). For 11 kg on the leg it gives:
   standing torque 7.7 → 0.2–1.2 N·m per motor (−85 to −97 %, ≈25 W off the robot's standing draw), jump +14 % at the
   60 N·m cap (278 → 317 mm) and +13 % at 120 N·m (296 → 334), and on power loss the leg stays up at ≈300 mm instead of
   folding onto its stops: the governing knee case disappears (section 4.5). It costs $15, ≈0.3 kg and two pins per leg, 3 J of
   stored energy at the standing height, no measurable change to balance or ride once cancelled, and nothing on the
   landing spike either way. Sized for the full robot (13 kg per leg) the same spring at 100 mm pins carries 75 % of
   the weight at 300 mm; pins at 110 mm restore 90 %.
2. **Do the landings in firmware and in the tyre, not with a spring.** Cap the touchdown speed (today's gearbox is
   fine to a 300 mm drop on the rig's measure; the knees are the limit and the collapse, not a landing, sets it);
   retract the leg through touchdown (−18 % on the spike for nothing); and measure the BotWheel tyre's radial rate on
   the rig, because a pneumatic-stiffness tread is worth −27 % on every landing load and −35–40 % on the sharp bumps,
   and a foam tyre −42 % and −50 %. If the BotWheel's tyre cannot be softened, four elastomer sandwich mounts between
   its flange and the wheel link (`bushing_soft`, 150 N/mm, ±8 mm) do the landing part (−39 %) but not the kerb part.
3. **Do not build** torsion springs at the hips (custom, and the wrong torque shape: they over-compensate the crouch
   and extend the leg on power-off), gas struts (6 cycles a minute, 30,000 cycles, need stops and a slot, and extend an
   unpowered leg), coil-overs (over-compensation, and a damper halves the jump), or anything in series with the
   motors: no robot in the survey with a quasi-direct drive leg does, and the rig shows why there is no need.

**The CAD it implies (a concept, not drawn):**

- A Ø8 pin boss on each upper link at r = 100 mm from the hip axis, on the link's inner face, the pin reaching into
  the y 2–28 mm band with a retaining clip; the link is 36–46 mm wide there, so the boss is a 16 mm eye grown from the
  link's outline (the same way the knee eye is), 20 mm proud. The loops bear on the pins; a 1 mm steel washer each
  side keeps the coil centred at y = 15.
- The spring's line crosses the **inner stop posts** (at x = ±29.5, z = −36, sleeves y 0–19) at leg lengths of
  160–200 mm (the line sits at z = −17 at 140 mm and z = −78 at 300 mm, and the coil is 25 mm across): the knee-in
  stops move. Either the knee-in stop becomes a lug on the hip frame's lower flange that the link's far edge meets
  (outside the spring's band), or the four posts move outboard of the links' hubs, or the knee-in stop is dropped in
  favour of a firmware limit plus the steel post at the extension end. The outer (knee-out) posts at (±114, +43) are
  clear at every length.
- The front link's apex eye (at the axle, R45) and the hip frame's web are clear of the spring at every length; the
  spring's lowest point is at z = −78 (300 mm), 136 mm above the tyre's top.
- A split TPU sleeve (printed, 1.5 mm wall, 30 mm ID) over the coil, clipped to the pins, so no finger can get between
  the coils; the spring's free length (229 mm) and its stretch (47 mm standing, 118 mm crouched, 173 mm at full
  extension) all fit between the links at every leg length (the pins are 276 mm apart standing, 347 mm at 140 mm).
- The controller: τ_spring(φ1, φ2) = T(ℓ)·∂ℓ/∂φ with T = 27 N + 1,576 N/m·(ℓ − 0.2286 m) for ℓ > 0.2286 m, else 0;
  subtract it from the commanded torques; exclude its vertical component from the liftoff detector.

**For the main session's scorecard** (the rig's own measures, 11 kg): the gearbox peaks at 62 N·m in the 150 mm drop
and 88 N·m in the 300 mm drop, never above 120 N·m for any variant or drop up to 300 mm; the knees see ≈500 N at
150 mm and ≈700 N at 300 mm, against the collapse's 1.8 kN (8.5 kg) that sizes them; the earlier J^T·F figure of
143 N·m was the quasi-static bound and overstated the gearbox by about three times and the knees by about two. The
energy each leg absorbs is 16 J from 150 mm and 32 J from 300 mm or from its own 278 mm jump. The 2.5 kg of dummy mass
that `sim/leg_rig.py` loses (section 3.1) should be restored before the collapse case is re-run for the FEA: at 11 kg
the collapse is harder than at 8.5 kg (section 4.5).

**Open questions.**

- The RS-04's rotor inertia (0.0243 kg·m² reflected is an estimate) scales every landing number; RobStride publishes
  neither it nor the gearbox's strength. A bench test of one motor (spin-down, or a known torque step) would settle it.
- The BotWheel's tyre stiffness (7.7 ms contact time constant, ≈100 N/mm, is an estimate) is the single biggest lever
  on landings and ride: press one on the rig.
- The rig is planar: crooked landings (the 10 % side force) and the wheel's out-of-plane moment are in the strength
  studies, not here.
- The RS-04's phase resistance (0.16 Ω from a reseller sheet, possibly line-to-line) only scales the watts; the
  fraction-of-rated-loss figures do not depend on it.
- The real robot is 26 kg, 13 kg per leg; the rig's 11 kg is the earlier estimate. Everything here scales with it;
  the spring's pins move from 100 to 110 mm if the leg should carry 90 % at 300 mm.
- The spring's tolerances are "Not Rated" on McMaster's page; measure its rate and initial tension on the rig before
  trusting the feed-forward, and re-fit the two numbers in firmware.
- The power-off behaviour with the spring (a leg that stays up while the body tips over) is better for the leg and
  worse for whatever the body lands on; the fall study should include it.

---

## 8. Follow-up: the spring on the outboard side, knee to knee (2026-10-27)

The main session tested the between-links spring of section 7 against the real CAD and it fails in 3-D: centreline
pins at r = 110 mm are the only radius that holds the 13.1 kg leg (100 folds, 115 and 120 push onto the stops), and
below about 250 mm of leg length the coil and boot pass through the hip region (frame, adapters, hub screws, the
knee-in stop posts, the 61812s), because in a crouch the knees swing up and out and the pins end up on opposite sides
of the hips; edge lugs at r = 125 hold (rest 288–312 mm, 73 N on the knee at power-off) but clash worse below 200 mm.
So this section evaluates the layout that stays outside everything: **a spring between the two knee axes, outboard
of the knee bolts' heads (y ≈ 99 mm)**, with the rig at its corrected 13.1 kg (`HALF_MASS` in `sim/leg_rig.py`; the
ballast is now a welded body). Code: `sim/leg_spring_study.py --knee --tag knee --sweep knee` (results in
`exports/leg/springs/results-knee.json`, `sweep-knee-knee.json`, `*-knee.png`) and `--clash` (the 3-D check,
`knee-spring-clash.json`, `knee-spring-layout.png`).

### 8.1 The geometry, and what it asks of a spring

From `cad/fivebar.py` (matching the main session's figures): the knees are 450 mm apart at a 105 mm leg (knee line
z +4), 442 at 150 (z −34), 387 at 250 (z −92), 339 at 300 (z −116), 300 at 330, 246 at 360, 207 at 375 and 139 at
390 (z −150); the tyre's top is at z −19 at 105 mm, −44 at 130, −64 at 150. The span changes 3.2:1 over the leg's
range, which no coil spring covers (McMaster's long extension springs stretch to 1.75–2.3 × their free length), so a
knee-to-knee spring is necessarily **slack over the top of the range** and, worse, *shorter than its own free length*
there: a 229 mm coil (9 in) has to bow once the knees are closer than 237 mm, a leg of 362 mm and up; a 178 mm coil
(7 in) from 381 mm. It also passes a **dead point**: the knee line crosses the hip line at a leg length of about
108 mm, where the spring's torque about the hips goes through zero and reverses; below it the spring pulls the leg
shut onto the knee-out stops, with about 1 N·m (the moment arm is tiny there), which the motors open against without
noticing. Between the two, the spring's job is to hold 13.1 kg at a resting height of 260–330 mm.

The tension the line has to carry to hold the 107 N the leg supports (13.1 kg less the wheel and half the wheel
link) **[derived, `tendon_dl` in the study]**: 93 N at 300 mm (span 339), 105 at 285, 117 at 270, 126 at 260, 145
at 240, 181 at 210, 233 at 180, 336 at 150, 536 at 130, 889 at 120, then through the dead point at 108 mm. Standing
is cheap; the crouch is where the moment arm collapses, so a linear spring never over-compensates deep in the crouch
and the motors always win there. Fitting a linear spring T = T_i + k·(span − ℓ₀) to 93 N at the standing span and
asking where the unpowered leg rests, how far it can be pushed down before it folds, and how both move with ±10 % on
rate and initial tension (`results-knee.json` → `static`, and the statics run in this section's log):

| spring (knee to knee, 13.1 kg) | rests at | folds below | slack above | ±10 % rate / tension: rest | T at the 450 mm span |
|---|---|---|---|---|---|
| 1.0 N/mm, 20 N initial | 300 mm | 229 mm | 350 mm | **folds** at −10 % rate; 294–315 otherwise | 204 N |
| 1.4 N/mm | 300 | 188 | 339 | 284–308 | 248 N |
| 1.6 N/mm | 300 | 176 | 335 | 288–306 | 270 N |
| 2.0 N/mm | 300 | 159 | 329 | 292–305 | 314 N |
| **5108N807 + 76 mm series link** (1.58 N/mm, 27 N) | 300 | 176 | 332 | 288–306 | 269 N (its maximum is 302 N, at a 470 mm span) |
| **2 × 5108N78 + 135 mm links** (1.76 N/mm, 34 N) | 300 | 168 | 327 | 290–306 | 288 N (each 144 N of its 188 N maximum) |
| 5108N794 + 48 mm link (1.02 N/mm, 22 N) | 300 | 225 | 349 | **folds** at −10 % rate | 206 N |

So the spring has to be at least **1.4 N/mm** to hold a 10 % error, which means 250–300 N at the crouch span and a
free length (in span terms) of 290–300 mm. The 0.6–1 N/mm first estimate is not robust: at −10 % rate the 1.0 N/mm
spring has no equilibrium at all and the leg folds.

### 8.2 Real parts

McMaster's long extension springs (pages read one at a time, 2026-10-27; the 1 in, 1.25 in and 1.5 in OD families
and the 4–9 lbf/in rate pages): nothing stocked is both 11–12 in long and 8–9 lbf/in with an 18 in maximum, so a
stock spring needs a **series link** to put its free length where the leg wants it, which also keeps it inside its
maximum extension:

- **[5108N807](https://www.mcmaster.com/5108N807/)** (9 in, 1 in OD, 0.125 in wire, 9 lbf/in = 1.58 N/mm, 6.11 lb
  initial tension, 67.87 lb at 15.84 in, $14.80) with a **76 mm link**: the coil is stretched 50 mm standing
  (93 N), 153 mm at the 105 mm crouch (269 N, 20 mm short of its 402 mm maximum). One spring, the minimum of parts.
- **Two [5108N78](https://www.mcmaster.com/5108N78/)** (7 in, 1 in OD, 0.105 in wire, 5 lbf/in, 3.8 lb initial,
  42.25 lb at 14.73 in, $11.86) side by side, each with a **135 mm link**: 1.76 N/mm together, each coil stretched
  17 mm standing and 145 mm at the crouch (144 of its 188 N maximum). Shorter coils, so they bow only above a 381 mm
  leg, but two coils need 51 mm of width over the tyre.
- Not usable: [5108N794](https://www.mcmaster.com/5108N794/) (5.8 lbf/in: not robust), [9654K687](https://www.mcmaster.com/9654K687/)
  (3.6 lbf/in), the 1.25 in and 1.5 in OD springs (0.4–0.7 N/mm, or 479 mm long).

Fatigue [estimate]: the 5108N807 at its 269 N crouch load is at 30 % of its wire's tensile strength (Wahl-corrected);
at the standing 93 N, 10 %. The crouch is a rare, slow load; the standing load is forever. Fine for the coil; the
loops are the usual weak point and must not be loaded sideways.

### 8.3 The anchors on the knee axes, and the series link

The knee bolt (ISO 7379 Ø12 × 90 shoulder screw, head Ø18 × 9 at y 82–91) is clamped to the upper link by the nut in
the eye; the lower link turns on it through two 6201s (y 32–42 and 70–80). The spring's loop has to sit on a post
**on the knee axis beyond the head** (y ≈ 93–105), fixed to the bolt: a **C-bracket of 3 mm steel clamped under the
head** (a Ø12.5 hole on the shoulder between the head's washer and the outer bearing's spacer, bent twice to come back
over the head's centre) carrying a Ø8 post 12 mm long on the axis, with a 1 mm washer and a clip; the loop rides on
the post and turns on it as the knee angle changes. The bracket rotates with the bolt (with the upper link), which is
fine: the loop turns on the post. The series link is a **76 mm (or 135 mm) steel strap with a Ø8 eye at each end**, or
better a short **wire-rope lanyard** (3 mm, thimbles, swaged) so the assembly can go limp above a 332 mm leg instead
of pushing the loop off its post. Above a 362 mm leg (381 for the two-spring version) the coil itself is longer than
the span and would bow: a **two-piece guide inside the coil** (a Ø12 rod from one post sliding into a Ø16 tube from
the other, 120 mm each) keeps a slack coil straight between 139 and 250 mm of span, and has separated by the time the
coil is taut. With the guide the spring, boot and guide are a self-contained strut-like assembly hung on two posts.
Without it the leg's extension has to be limited to 360 mm (one spring) or 380 mm (two).

### 8.4 The out-of-plane moment on the knee

The pull T acts at y ≈ 99, 89 mm outboard of the eye's mid-plane (the two sleeves span y −10 to +30) and 24 mm outboard
of the outer 6201's centre. Numbers for T = 93 N standing and 270–290 N in the crouch (`knee_k1.6`, the stock parts):
- the knee bolt bends as a cantilever past the outer bearing: M = T × 0.024 = 2.2–7 N·m, 13–41 MPa on the Ø12
  shoulder (fine);
- the couple on the lower link's two 6201s, 38 mm apart: ±0.63 T = ±60 N standing, ±180 N in the crouch, on
  bearings rated 3.1 kN static;
- the moment that reaches the upper link's eye is bounded by T × 0.089 = 8.3 N·m standing and 26 N·m in the crouch,
  of which the outer bearing, 24 mm from the load, takes most; as a bound, 26 N·m over the 40 mm of sleeves is
  6·M/(d·L²) ≈ 8 MPa of extra bearing pressure, against the 31 MPa the two-sleeve eye sees in the collapse. Small, but
  it is a steady 8 N·m, every day, in a direction the eye was not designed for; worth one line in the eye's study.
- in the leg's plane the spring is simply a 93–290 N joint load at each knee, less than a landing's 500–1,000 N.

### 8.5 The 3-D clash check (`--clash`, `knee-spring-clash.json`, `knee-spring-layout.png`)

A 25.4 mm coil in a 32 mm boot, centred at y 99 on the knee axes with 12 mm of hook past each axis, intersected with
every part of `fivebar.assembly()` (motors as envelopes) at 14 leg lengths from 105 to 390 mm: **no intersection with
any part at any length**, coil or boot. The hip region is 95 mm inboard of the spring's layer, so the problem that
killed the between-links spring does not arise. The one proximity is the tyre, which shares the spring's layer (the
boot spans y 83–115, the tyre y 82–127): the gap from the boot's underside to the tyre's crown is **7.4 mm at 105 mm,
7.3 at 110, 8.1 at 120, 9.7 at 130, 14.8 at 150, 25 at 180 and 38 mm at 210**. A boot over a tread turning at up to
3 m/s with 7 mm to spare, in the pose a kid gets by sitting on the robot, is not comfortable; with the crouch limited
to 130 mm (the working range's floor) it is 10 mm, and the boot can be shaped flat on its underside to make it 13.
The check is of a straight envelope; it does not model the bow of a slack coil above 362 mm (section 8.3).

### 8.6 What the rig says (13.1 kg)

`results-knee.json`, `scorecard-knee.png`. The rig's controller does not know about the spring unless told
(`_c` = the spring's torque subtracted as feed-forward, which any real firmware would do: HKUST, Tongji); without
it the leg-length PD sits 24 mm above its command against the spring's push and the crouch stops 30–60 mm short, so
the `_c` rows are the honest ones and the plain rows show what an uncancelled spring does to the controller.

| 13.1 kg | stand 300 mm (N·m/motor; where it sits) | crouch to 110 mm: reached, motor N·m | jump 60 / 120 N·m (mm) | drop 150: axle N, gearbox N·m, knee N | power-off undamped: knee N, stop N·m, what happens | damped: knee N, rest mm | 20 mm bump 1 m/s (peak g) |
|---|---|---|---|---|---|---|---|
| `none` (today) | 9.8 (303 mm) | 117 mm (the rail stop), 7.2 | 279 / 308 | 1,885, 64, 528 | **3,026, 223, folds onto the knee-out stops** | 305, 101 | 9.4 |
| `knee_k1.6` (1.6 N/mm custom, uncancelled) | 3.1 (324 mm; the spring gives 5.5 there) | 137 mm, 2.7 | 287 / 313 | 1,870, 63, 538 | 1,102, 172, stays up, then a lean swing onto a stop | 65, 308 | 11.3 |
| `knee_k1.6_c` (cancelled) | **0.3 (300 mm; the spring gives 10.6)** | 115 mm, 5.8 (spring 1.6) | **345 / 368** (+66 / +60) | 1,934, 63, 544 | 70, 0, stays up at 304 mm | 70, 304 | 9.2 |
| `knee_5108N807_link76` (stock, uncancelled) | 3.0 (324 mm) | 137 mm, 2.8 | 282 / 317 | 1,900, 64, 546 | 1,096, 171, as `knee_k1.6` | 65, 309 | 11.6 |
| `knee_2x5108N78_link135` (stock pair) | 3.5 (325 mm) | 139 mm, 2.1 | 283 / 314 | 1,898, 65, 543 | 1,138, 178, as above | 67, 306 | 10.9 |
| `knee_k1` (1.0 N/mm, not robust) | 1.4 (331 mm) | 128 mm, 5.0 | 296 / 330 | 2,004, 62, 607 | 70, 0, stays up at 310 | 64, 319 | 12.5 |
| `knee_k1.6` built ±10 % in rate and tension (6 cases) | 2.8–3.5 | — | 284–293 / 314–320 | 1,835–1,921, 62–65, 528–552 | 1,088–1,135, 170–178 | 65–67, 302–313 | 11.3–12.1 |

What the numbers say:

- **Standing.** Cancelled, the spring carries the whole standing load (0.3 N·m left of 9.8; 10 W per motor becomes
  nothing). Between 200 and 260 mm the 1.4–2 N/mm springs over-compensate by 25–35 % (the price of the ±10 %
  robustness), so a robot parked low holds its legs *down* with 3–4 N·m per motor. At 115 mm the spring's torque is
  1.6 N·m, as the dead point predicts.
- **Jumps.** Cancelled, +66 mm at the 60 N·m cap (279 → 345, +24 %) and +60 mm at 120 N·m, with 7.5 J returned at
  liftoff from 20 J stored in the crouch; uncancelled, +3 to +8 mm, because the controller never reaches the crouch
  (SPR's "0 N and 450 N give the same height"). The knee-to-knee line stores more than the between-links spring did
  (20 J against 11) because its stretch is largest in the crouch.
- **Landings.** Unchanged, as before: 1,835–2,004 N, 62–65 N·m, 528–607 N at 150 mm.
- **The collapse.** Today, undamped: 3.0 kN on the knee and 223 N·m on the stop at 13.1 kg (the rig's 1.8 kN was
  8.5 kg); damped: 305 N. With the spring the leg does not fold: it stays at 296–319 mm. Damped, that is 65–70 N on
  the knee and no stop touched. Undamped, the 1.4–2 N/mm springs first lift the leg to 325 mm (the motors had been
  holding it down), and on the rig's free wheel the lean then grows until an upper link meets its stop 0.9 s later
  at a 30° lean: 1.1 kN on the knee, 170–180 N·m on the stop, a third of today's. The 1.0 N/mm spring does not do
  that (70 N) but folds at −10 % rate. On the real robot a power cut tips the body over anyway; what the spring buys
  is that the leg is not slammed shut while it does.
- **Ride and balance.** Cancelled, the ride is today's (9.2 g against 9.4 on the 20 mm bump). The spring's own
  stiffness along the leg is large and negative, −1.0 to −1.8 kN/m at 300 mm against the controller's 3 kN/m, and
  its lean torque at 15° is 2.4 N·m; both are smooth functions of the two motor angles and go into the feed-forward.
  Uncancelled, the peaks rise 20–35 % and the leg sits 24 mm high.
- **Robustness.** The six ±10 % builds of the 1.6 N/mm spring rest at 302–313 mm damped and behave alike in every
  scenario.
- **The sweep** (`sweep-knee-knee.json`, 30 points, uncancelled controller; cells as in section 4.7 with the
  undamped collapse's knee force in the fourth place): with the rate at 1.4–2.0 N/mm every preload from 0.8 to 1.1×
  shows the undamped lean swing (1.0–1.2 kN on the knee), and only 1.2× (the leg resting at 316–325 mm) settles
  without it (67–71 N); the softer 0.8–1.0 N/mm springs settle quietly at 1.0–1.2× (61–70 N) but are the ones that
  fold at −10 % rate. Damped, the whole grid rests at 274–347 mm. Uncancelled jumps run 276–299 mm (today 279) and
  the 40 mm bump 2.4–4.8 g (today 2.8).

### 8.7 Verdict on the knee-to-knee spring

It fits, and it works, with conditions: it is the only spring layout found that clears the CAD at every leg length,
it holds the 13.1 kg leg at 290–313 mm within ±10 % of rate and tension, it removes the standing torque and the
everyday collapse and adds a quarter to the jump. But it is no longer the one $15 part of section 7: it is a spring
rated at least 1.4 N/mm (the stock 5108N807 with a 76 mm wire-rope lanyard, or two 5108N78 with 135 mm lanyards),
two C-bracket posts clamped under the knee bolts' heads, a rod-in-tube guide inside the coil so a slack coil cannot
bow over the wheel above a 332 mm leg (or a 360 mm extension limit), a boot, 0.45–0.6 kg per leg, a boot that passes
7 mm over a turning tyre at the 105 mm crouch (10 mm at 130), a steady 8 N·m out-of-plane load on each knee bolt,
3–4 N·m of hold-down per motor whenever the robot sits at 200–260 mm, a 24 mm standing offset and a 25–35 %
over-compensation that the firmware has to model, and its jump gain only exists with that firmware.

Against that, the fallback costs nothing: **no spring, and a bench test of the RS-04's own power-off damping**,
which on the rig turns the undamped 3.0 kN collapse into 305 N at the knee (section 4.5 and `none` above) if the
motor's anti-backdrive behaviour is what the manual implies. The standing heat without a spring is 10 W per motor at
13.1 kg (5.9 % of the rated loss, 41 W for the robot), a runtime cost, not a thermal one.

**Recommendation now:** build the rig without a spring; measure the RS-04's power-off damping (the collapse is the
knees' governing case, and that one measurement decides whether it is 3.0 kN or 0.3 kN) and the standing current;
keep the knee-to-knee assembly above as the one spring that fits, to add on the rig only if the jump height or the
runtime turns out to matter more than its parts and its 7 mm. If it is built, the firmware must subtract its torque
from the two motor angles, exclude it from the liftoff detector, and the crouch floor should be 130 mm.
