# Reference robots for wobbit

Research date: 2026-10-25. All numbers carry a source URL. Where a number could not be found it is written as **unknown**. Where we worked a number out ourselves (from a URDF/SDF or from physics), it is labelled **(derived)** and the inputs are shown.

wobbit summary for context: a self-balancing wheel-legged biped like the DDT Diablo. It carries a ~1.5–2.5 kg Jetson AGX Orin 32GB / Seeed J501 box (206 × 181 × 112 mm, 12–36 V input), will be trained with RL in Isaac Sim / Isaac Lab, and will be **mostly 3D printed in PLA on a Bambu P1S at first** (carbon-fibre-filled filament later; SendCutSend metal / CF plate later still).

---

## 1. DDT (Direct Drive Tech) Diablo

### Headline specs

| Item | Value | Source |
|---|---|---|
| Size, standing (L × W × H) | 540 × 371 × 491 mm | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Size, "creeping" (crouched, body down) | 540 × 371 × 270 mm | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Mass | 22.9 kg | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Payload | 4 kg standing, 80 kg creeping | [RobotShop](https://www.robotshop.com/products/diablo-worlds-first-direct-drive-self-balancing-wheeled-leg-robot), [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Top speed | 2 m/s | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) (other resellers say 2.4 m/s or 10 km/h; treat 2 m/s as the conservative figure) |
| Jump height | 8 cm, no load | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Battery | Li-ion, 32 V rated, 6 Ah (≈192 Wh, **derived** 32 × 6) | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Runtime | ≈3 h standing at 25 °C; ≈4 h continuous travel in creeping mode; ≈3 h travel in standing mode (low speed); **only ≈15 min standing in squatting mode** | [top3dshop](https://top3dshop.com/product/direct-drive-diablo-wheeled-bipedal-robot) |
| Noise | < 49 dB | [RobotShop](https://www.robotshop.com/products/diablo-worlds-first-direct-drive-self-balancing-wheeled-leg-robot) |
| Motors | 6 × DDT M1502D direct-drive joints (2 hip, 2 knee, 2 wheel) | [RobotShop](https://www.robotshop.com/products/diablo-worlds-first-direct-drive-self-balancing-wheeled-leg-robot) |
| Compute | Onboard Raspberry Pi (model not stated) in the MYBOTSHOP integration; SDK runs on "most Linux devices that support serial ports" | [MYBOTSHOP docs](https://www.docs.mybotshop.de/diablo.html), [diablo-sdk-docs](https://diablo-sdk-docs.readthedocs.io/en/latest/) |
| Software | ROS 2 recommended (ROS 1 and plain C++ also), rviz2 + Gazebo visualisation, Python keyboard teleop | [diablo-sdk-docs](https://diablo-sdk-docs.readthedocs.io/en/latest/) |
| Price | US $4,399 (special order) | [RobotShop](https://www.robotshop.com/products/diablo-worlds-first-direct-drive-self-balancing-wheeled-leg-robot) |

### Leg kinematics: not a five-bar

The user brief guessed a five-bar leg. DDT's own Gazebo model says otherwise. In [DDTRobot/DiabloSTLSDF `model.sdf`](https://github.com/DDTRobot/DiabloSTLSDF) each leg is:

- `Motor0` (hip) on the body, driving `Leg0` (2.46 kg; this link carries the second motor);
- `Motor1` (knee drive) on `Leg0`, driving `Leg1` (the 0.14 m thigh link). It sits coaxially with the hip, so both leg motors are at the body;
- a passive rod `Leg2` (0.10 kg), also pinned to `Leg0`, joined to the shank `Leg3` 0.05 m from the knee. Together with `Leg1` this closes a **four-bar (parallelogram-style) loop** that transmits the knee drive from the hip down to the knee;
- `Motor2` drives the wheel directly at the foot.

MYBOTSHOP's integration docs say the same: "two parallel-linkage legs, each ending in a single drive wheel", with a "4-bar linkage" for crouch, lean and curb-climb ([MYBOTSHOP](https://www.docs.mybotshop.de/diablo.html)). So Diablo gets the main five-bar benefit (both heavy leg motors at the body, so the moving leg is light) from **coaxial hip + knee motors and a four-bar transmission**. There is **no hip abduction**. Each leg has 3 actuated DOF (hip, knee, wheel), 6 in total.

Masses from the SDF: body 6.72 kg; per leg Leg0 2.46 + Leg1 1.25 + Leg2 0.10 + Leg3 1.30 + wheel 1.36 kg. That totals ≈19.7 kg (**derived**), against 22.9 kg spec, so the SDF is approximate.

DDT's RL model ([Col_DIABLO_Issac_RL `diablo.urdf`](https://github.com/DDTRobot/Col_DIABLO_Issac_RL)) replaces the linkage with an **equivalent serial 2-link leg**: thigh 0.14 m, shank 0.14 m, **wheel radius 0.10 m (200 mm wheel)**. All joints have effort 27 N·m and velocity 26 rad/s, the base is 11.64 kg and the total is ≈20.9 kg (**derived**). Swapping a closed linkage for an equivalent serial chain in sim is a useful trick for wobbit too.

### DDT M1502D motor (Diablo's joint)

| Item | Value | Source |
|---|---|---|
| Voltage | 24 VDC | [AIFIT Lab](https://aifitlab.com/products/direct-drive-tech-m1502d_133-directdrive-motor) |
| Rated / stall torque | 9.6 N·m / ≥17 N·m | same |
| Rated / no-load speed | 115 rpm / ≥200 rpm | same |
| Kt, Kv | 0.88 N·m/A, 8.3 rpm/V | same |
| Rated / stall current | ≤11.5 A / ≤21 A | same |
| Encoder | 16384 counts | same |
| Mass | 2.3 kg (another listing says 1 kg; conflict) | same; [Robotics Center](https://www.roboticscenter.ai/ar/store/product/direct-drive-tech-m1502d133-directdrive-motor) |
| IP rating | IP55 | same |
| Sold separately? | Yes. M1502D_133 at US $310 (sold out / backorder); M1502D_233 tyre-wheel version at US $509; Switch Science JP sells the tyre version at ¥60,500 | [AIFIT Lab](https://aifitlab.com/products/direct-drive-tech-m1502d_133-directdrive-motor), [AIFIT Lab 233](https://aifitlab.com/products/direct-drive-tech-m1502d_233-directdrive-motor), [Switch Science](https://www.switch-science.com/collections/all/products/9065) |
| Bus / protocol | **unknown** from the product page. DDT publishes [motor-driver-examples](https://github.com/DDTRobot/motor-driver-examples) (Apache-2.0) | — |

**Derived check:** with the RL-model leg (0.14 m segments), holding a deep crouch needs about (22.9 − 2·1.36 − 2·0.1) kg · g / 2 · 0.14 m ≈ **13.7 N·m per knee**. That is above the M1502D's 9.6 N·m rated torque and below its ≥17 N·m stall torque. It fits the spec sheet's **≈15 min limit in squatting mode**: a direct-drive knee overheats when it holds a crouch. Lesson: an unloaded direct-drive leg is efficient when it stands straight and costly when it holds a crouch.

### Open-source status of Diablo models

DDT's GitHub org ([github.com/DDTRobot](https://github.com/DDTRobot)) has:
- [diablo_ros2](https://github.com/DDTRobot/diablo_ros2) (Apache-2.0, ~100 stars) and [diablo_sdk](https://github.com/DDTRobot/diablo_sdk) (Apache-2.0);
- [DiabloSTLSDF](https://github.com/DDTRobot/DiabloSTLSDF): STL + SDF with the real linkage. **No LICENSE file, so all rights are reserved by default**;
- [Col_DIABLO_Issac_RL](https://github.com/DDTRobot/Col_DIABLO_Issac_RL): Isaac Gym RL with a Diablo URDF, based on clearlab-sustech Wheel-Legged-Gym. Its README says it "takes about three thousand iterations to reach convergence". **No LICENSE file**;
- [diablo-sim-env](https://github.com/DDTRobot/diablo-sim-env): Webots. No licence.
- No official USD found.

### DDT TITA (the successor)

TITA is a **wheel-legged biped with hip abduction**: 4 joints per leg, 8 DOF. It can also be reconfigured: the retailer lists "two-wheeled self-balancing, two-wheeled legged, bipedal, quadruped, wheeled quadruped" configurations ([top3dshop](https://top3dshop.com/product/direct-drive-tita)). DDT's GitHub also has a "titatit" quadruped mode ([titatit_rl](https://github.com/DDTRobot/titatit_rl)).

| Item | Value | Source |
|---|---|---|
| Size | 510 × 590 × 490 mm standing; 300 mm high creeping | [top3dshop](https://top3dshop.com/product/direct-drive-tita) |
| Mass | 24.1 kg without battery (URDF sums to ≈27.7 kg, **derived**) | [top3dshop](https://top3dshop.com/product/direct-drive-tita), [TITA_Description](https://github.com/DDTRobot/TITA_Description) |
| Payload | 10 kg moving | [top3dshop](https://top3dshop.com/product/direct-drive-tita) |
| Speed / jump / slope | 3 m/s / 30 cm (another listing: 20 cm) / 30° | [top3dshop](https://top3dshop.com/product/direct-drive-tita) |
| Actuators | 8 "quasi-direct drive joint modules", peak 120 N·m | same |
| Battery | 43.2 V nominal; 1 h per pack; 2 hot-swap packs | same |
| Compute | NVIDIA Jetson Orin NX 16GB | same |
| SDK | ROS 2 + Zenoh | same |
| Price | US $12,999 | same |
| Leg (from URDF) | `leg_1` hip abduction ±45°; `leg_2` hip pitch −110°…+200°; `leg_3` knee −153°…−40°; `leg_4` wheel, **wheel radius 0.0925 m (185 mm)** | [TITA_Description robot.urdf](https://github.com/DDTRobot/TITA_Description) (no licence file) |

TITA has the richest public RL tooling of any commercial wheel-legged biped: [tita_rl](https://github.com/DDTRobot/tita_rl) (**MIT**, ~140 stars, Isaac Gym) and [DDT_Lab](https://github.com/DDTRobot/DDT_Lab) (Isaac Lab, D1 + TITA; no root LICENSE file found). DDT's [d1_mjlab](https://github.com/DDTRobot/d1_mjlab) ports the same work to MuJoCo/mjlab for its **D1**, a wheeled quadruped.

---

## 2. Other wheel-legged robots with published design data

### Ascento (ETH Zurich → Ascento Robotics)

Source: Klemm et al., "Ascento: A Two-Wheeled Jumping Robot", ICRA 2019 ([arXiv 2005.11435](https://arxiv.org/abs/2005.11435)).
- **Topology:** one motor per leg at the hip. A numerically optimised **three-bar linkage** approximates straight vertical wheel travel, which decouples driving from jumping. **Torsion springs** in the inner joints carry the robot's weight and boost the jump. No knee motor and no abduction.
- **Height:** adjustable from 31 to 66 cm. **Mass:** 10.4 kg. **Runtime:** ≈1.5 h.
- **Hip actuators:** ANYbotics ANYdrive series-elastic actuators, up to 40 N·m peak.
- **Wheel actuators:** Maxon EC90 **frameless, direct-drive hub motors**, 3.5 N·m maximum. The paper chose direct drive for "almost backlash free motion", because "near-zero backlash and high wheel torques are required" to stabilise.
- **Structure:** topology-optimised parts, **SLS-printed PA12**.
- **Battery:** 4 × 3S LiPo in series for the motors; a separate 4S LiPo for the computer. **Compute:** Intel NUC i7.
- **Control:** LQR on a two-wheeled inverted pendulum model.
- **Jump height:** ≈0.4 m ([New Atlas](https://newatlas.com/robotics/ascento-wheeled-legged-robot)). Wheel diameter: **unknown**.
- The paper notes that wheeled robots "fail to handle … obstacles larger than their wheel's radius".
- Commercial follow-ons: Ascento Pro, reported at up to 12 km/h and 8 h ([Laughing Squid](https://laughingsquid.com/ascento-pro-two-wheeled-robot/)). The Ascento Guard security robot is reported at 66.1 lb / 30 kg, 3.1 mph and 4.5 h ([Automated Warehouse](https://www.automatedwarehouseonline.com/?p=1075)). Closed source.

### Upkie (Stéphane Caron et al.; fully open source)

- **Repos:** [upkie/upkie](https://github.com/upkie/upkie) (Apache-2.0, ~450 stars, active Oct 2026); [upkie_description](https://github.com/upkie/upkie_description) (URDF, Apache-2.0, wheel tyre mesh CC BY 4.0); [upkie/parts](https://github.com/upkie/parts) (FreeCAD/Blender/3MF/STL, Apache-2.0).
- **Topology:** **serial** 2-link leg with **the knee motor on the leg** (the URDF attaches the knee qdd100 stator to the femur). No abduction. Six actuators.
- **Actuators** ([BOM](https://upkie.github.io/upkie/bill-of-materials.html)): 4 × mjbots **qdd100 beta 2** (hip + knee) and 2 × **moteus developer kit** for the wheels (a direct-drive BLDC with the moteus controller).
- **Electronics:** mjbots pi3hat r4.4b+, mjbots power_dist r4.3b+, Raspberry Pi 4B, RYOBI 18 V tool battery, 24 V fan.
- **Joint limits** ([kinematics doc](https://upkie.github.io/upkie/kinematics.html)): hip ±1.26 rad and knee ±2.51 rad, both 28.8 rad/s and 16 N·m peak (< 1 s). Wheel 111 rad/s and 1.7 N·m.
- **Wheels:** RC 1:8 rubber tyres, 112 mm OD, 17 mm hex drive ([BOM](https://upkie.github.io/upkie/bill-of-materials.html)). The docs give the "typical" wheel radius as 5–6 cm ([kinematics](https://upkie.github.io/upkie/kinematics.html)).
- **Mass:** ≈5.3 kg summed from the URDF (**derived**; [upkie.urdf](https://github.com/upkie/upkie_description)). Height **unknown**.
- **Cost:** "around $3,000" from off-the-shelf parts ([FOSDEM 2026 talk abstract](https://archive.fosdem.org/2026/schedule/event/8PUMMD-open-source-robotics-practice-upkie-wheeled-bipeds/)). Printed parts come from a Prusa-class FDM printer; the filament is not specified ([BOM](https://upkie.github.io/upkie/bill-of-materials.html)).
- **Lessons from the FOSDEM 2026 talk** ([transcript](https://ftp.fau.de/fosdem/2026/ub2147/8PUMMD-open-source-robotics-practice-upkie-wheeled-bipeds.vtt)):
  - **Printed tibias and femurs broke.** Upkie v2 redesigned the lower leg as a **fork**, which is "much stiffer". After a wall hit, the part "slightly broke, but it's not a complete failure".
  - They moved from Blender to parametric FreeCAD so leg lengths can be changed.
  - v2 has fewer parts, and the cables run outside so they are easy to reach.
  - Their MPC carries over between Upkie variants by changing mostly the **wheel radius**.
  - The RL reward keeps a point at the top of the robot at its reference, adds action smoothness, and uses a ground-velocity action.
  - An mjlab (MuJoCo Warp, GPU) policy learned to **use the legs as well as the wheels** and was "much smoother" than the straight-leg policy.
  - Sharing one code path between the real robot, sim tests and RL was "too greedy", so they decoupled them.
  - Wi-Fi setup complexity hurt; pixi-pack deployment helped.

### LimX Dynamics TRON 1 (commercial; multi-modal biped)

Interchangeable point-foot, sole and **wheel** feet ([LimX spec](https://limxdynamics.com/en/tron1/spec)).
- **Size:** ≤ 392 × 420 × 845 mm. **Mass:** ≤ 20 kg. **Payload:** ≤ 10 kg.
- **Speed:** wheeled ≤ 3 m/s. Climbs ≤ 30° and ≤ 20 cm obstacles.
- **Joint actuators:** 48 V, 30 N·m rated, 60 N·m peak, 15 rad/s peak. One press piece says 80 N·m peak; the official page says 60.
- **Battery:** 46.8 V, 4.5 Ah, ≤ 2 h. **Compute:** Intel i3 12th gen, 16 GB.
- **Price:** US $25,000 EDU at [RobotShop](https://www.robotshop.com/products/limx-dynamics-tron-1-multi-modal-biped-robot-edu).
- **Wheel diameter and leg topology:** unknown from the spec page.
- **Sim:** [tron1-mujoco-sim](https://github.com/limxdynamics/tron1-mujoco-sim) (Apache-2.0).

### Unitree

As of this research, Unitree's wheel-legged products are **quadrupeds** (Go2-W, B2-W), not bipeds. Go2-W: 18 kg, ≈45 N·m knee motor, Orin Nano / NX compute ([RobotShop](https://www.robotshop.com/products/unitree-go2-w-wheeled-robotic-dog-us); reseller figures conflict). They are relevant mainly for RL technique (e.g. [DreamWaQ_Go2W](https://github.com/ShengqianChen/DreamWaQ_Go2W)), not for wobbit's mechanics.

### Open-source hobby / student builds

| Build | Leg topology | Leg motors | Wheel motors | Size / mass | Cost | Links / licence | Notes |
|---|---|---|---|---|---|---|---|
| **Skythinker616 foc-wheel-legged-robot** | 2 motors per leg at the body driving a closed linkage, controlled as a "virtual leg" (VMC) + LQR whose gains are fitted against leg length | 4 × 4010 gimbal BLDC, 12 V, 0.22 N·m stall, 125 g, ¥50 | 2 × 2804 gimbal BLDC, 0.04 N·m stall, ¥13 (direct drive) | desk-top; 3S 800 mAh, 20–30 min | **¥549** total (≈US $75) | [GitHub](https://github.com/Skythinker616/foc-wheel-legged-robot) **GPL-3.0**, 1.8k stars; SolidWorks + Simscape + STM32 FOC + ESP32 | Mostly **3D printed** + acrylic base ([solidworks README](https://github.com/Skythinker616/foc-wheel-legged-robot/tree/main/solidworks)) |
| **MuShibo Micro-Wheeled_leg-Robot** | small linkage leg driven by **Feetech bus servos** | 2 × bus servos | 2 × gimbal BLDC via SimpleFOC (L6234 driver, AS5600 encoders) | "smallest two-wheeled-leg robot" | unknown | [GitHub](https://github.com/MuShibo/Micro-Wheeled_leg-Robot) (no licence file), ~3.8k stars | ESP32, MPU6050, web joystick |
| **Venus-1 (track-tech)** | four-link (four-bar) leg | 2 × **Xiaomi CyberGear** (¥499 each) | 2 × DJI M2006 P36 **geared** + C610 | 90 mm PU wheels; 3 mm FR4/3240 epoxy plates; printed electronics bay | ≈¥2,576 without RC | [GitHub](https://github.com/track-tech/Venus-1__Four-link-wheel-legged-robot) **GPL-3.0** | Author's failure list: **M2006 gearbox backlash made the body shake at the balance point; recommends a direct-drive gimbal motor for the wheel**. CyberGear single-encoder needs re-zeroing at every power-up. Bought PU wheels came loose; recommends printed hubs. Yaw drift unsolved |
| **Multivac11 wheel-legged robot** | **five-bar**: motor spacing 150 mm, thigh 150 mm, shank 270 mm, virtual leg 95.5–398 mm | 4 × **Unitree A1** (RS-485, 1 port per motor; 1 kHz was buggy, ran at 500 Hz) | 2 × DJI M3508 (modified gearbox) | 12.9 kg total; body 9.5 kg; wheel radius 75 mm | unknown | [GitHub](https://github.com/Multivac11/Wheel-legged-robot--Main_Code) (no licence) | Solo build, mechanics + electronics + control |
| **RoboMaster "balance infantry" (e.g. RP_Balance)** | **five-bar**, variable leg length, VMC + LQR with K fitted against leg length | unknown | unknown | — | — | [RP_Balance](https://github.com/WilliamGwok/RP_Balance) **MIT** | Warning: a **printed part clamped under a motor deformed from heat/vibration**, and a screw later went into the motor windings |
| **scutrobotlab wheeled-legged_RL** | RoboMaster wheel-leg | — | M3508 actuator model | — | — | [GitHub](https://github.com/scutrobotlab/wheeled-legged_RL) **MIT** | Isaac Sim 4.5/5.1 + Isaac Lab 2.1/2.3 + RSL-RL; sim2real still on its roadmap |

No public wheel-legged biped built on **hoverboard hub motors** was found in this research. The web-search budget ran out before a dedicated search could be done, so treat this as "not found", not "does not exist".

**Actuator price points for a wobbit-class build** (reseller listings):
- **RobStride 02:** 17 N·m peak, 6 N·m rated, 7.75:1, 405 g, ≈US $145 ([AIFIT Lab](https://aifitlab.com/products/robstride-02-motor)).
- **Xiaomi CyberGear:** 12 N·m peak, 4 N·m continuous, 317 g, ≈US $179, now end-of-life ([OpenELAB](https://openelab.io/blogs/learn/xiaomi-cybergear-micromotor-guide)); launched at ¥499 ([SMM](https://news.metal.com/newscontent/102352716)).
- **Damiao DM-J4310-2EC:** 7 N·m peak (V3 driver) / 12.5 N·m (V4), ≈US $125–167 ([OpenELAB](https://openelab.com/products/damiao-brushless-servo-dm-j4310), [AIFIT Lab](https://aifitlab.com/products/damiao-dm-j4310-2ec-v1-1-servo-motor)).
- **DDT M1502D direct-drive:** 17 N·m stall, 2.3 kg, US $310.
- **mjbots qdd100:** 16 N·m peak per the Upkie docs; price unknown (mjbots page rate-limited).

---

## 3. Design rules of thumb

Rules marked **(derived)** are our physics, checked against the reference robots above.

1. **Put the heavy leg motors at the body.** Diablo does it with coaxial hip + knee motors and a four-bar ([SDF](https://github.com/DDTRobot/DiabloSTLSDF)). Five-bar builds put both motors on the body ([Multivac11](https://github.com/Multivac11/Wheel-legged-robot--Main_Code), [RP_Balance](https://github.com/WilliamGwok/RP_Balance), [Skythinker](https://github.com/Skythinker616/foc-wheel-legged-robot)). Ascento uses one hip motor plus a linkage ([paper](https://arxiv.org/abs/2005.11435)). Upkie carries the knee motor on the leg, which is simplest but makes the leg heavier ([URDF](https://github.com/upkie/upkie_description)).
   - **Why five-bar:** both motors push together in the downward (jump) direction, and springs can sit between the hip links ([Olympus paper](https://arxiv.org/pdf/2503.03574)). Penn's direct-drive symmetric five-bar delivered "more than half again as much kinetic energy" to the body ([Penn](https://repository.upenn.edu/ese_papers/793)). Low leg inertia also helps the balance loop, because the wheel sees less unmodelled leg swing.
   - The RoboMaster community controls the five-bar as a single **virtual leg** (length + angle) with VMC, and **schedules LQR gains on leg length** ([Skythinker MATLAB](https://github.com/Skythinker616/foc-wheel-legged-robot/tree/main/matlab), [RP_Balance](https://github.com/WilliamGwok/RP_Balance)).
2. **Wheel motors: direct drive.**
   - Ascento chose direct-drive frameless hub motors for "almost backlash free motion" ([paper](https://arxiv.org/abs/2005.11435)).
   - Venus-1's geared M2006 wheel made the body **jitter at the balance point**; its author recommends gimbal motors ([README](https://github.com/track-tech/Venus-1__Four-link-wheel-legged-robot)).
   - Diablo, Upkie (moteus dev-kit motor) and Skythinker (2804 gimbal) all drive the wheel directly.
3. **Wheel torque (derived):** peak torque per wheel ≈ (1.0–1.5) × m·g·r / 2.
   - Diablo: 2 × 17 N·m / 0.10 m ÷ (22.9 kg · g) ≈ 1.5 g of wheel traction. Upkie: 2 × 1.7 N·m / 0.056 m ÷ (5.34 kg · g) ≈ 1.2 g.
   - Holding position on a slope α needs m·g·r·sin α in total. Example: 7 kg, r = 0.08 m, 15° slope ≈ 1.4 N·m total.
   - The wheel also needs **torque headroom at top speed** to tip the body back. Size so the torque–speed curve still gives ≥ 0.5 × peak at v_max / r. For example, 2 m/s on a 160 mm wheel is 25 rad/s ≈ 240 rpm.
   - Diablo runs 2 m/s on a 200 mm wheel (≈191 rpm) with a motor rated ≥200 rpm no-load at 24 V on a 32 V pack. That margin is tight.
4. **Knee torque for squat-to-stand (derived):** for a serial-equivalent leg with segment length L, wheel under the hip, and supported mass m_s, the knee torque is about (m_s · g / 2) · L · sin φ (φ = segment angle from vertical). Multiply by ≈1.7 for a 10 cm jump with a 15 cm push stroke (a = g·h/s), and by 2–3 for landing.

   | m_total | L | static, full crouch | φ = 60° | × jump (1.67) | × landing (2.5) |
   |---|---|---|---|---|---|
   | 6 kg | 0.12 m | 2.7 N·m | 2.3 | 3.8 | 5.7 |
   | 6 kg | 0.15 m | 3.3 | 2.9 | 4.8 | 7.2 |
   | 9 kg | 0.12 m | 4.4 | 3.8 | 6.4 | 9.6 |
   | 9 kg | 0.15 m | 5.5 | 4.8 | 8.0 | 12.0 |

   These numbers assume ~1.5 kg of legs + wheels is not carried by the knee. Cross-checks: Upkie (5.3 kg) runs 16 N·m peak hip/knee, a large margin; Diablo (22.9 kg, L = 0.14 m) needs ≈13.7 N·m at full crouch on a 9.6 N·m rated motor, hence its 15-minute squat limit. **Size the knee so that a deep crouch held for minutes stays under the actuator's continuous rating**, not only its peak.
5. **Leg length versus wheel size:**
   - Diablo: 2 × 140 mm segments on a 200 mm wheel; 491 → 270 mm height range.
   - TITA: 185 mm wheel; 490 → 300 mm height range.
   - Multivac11: 150/270 mm links on a 150 mm wheel; virtual leg 96–398 mm.
   - Upkie: 112 mm wheel. Ascento: 31–66 cm height range.
   - **Rule of thumb (derived):** thigh/shank ≈ 0.7–1.0 × wheel diameter, and a usable stroke of ≈ 1–1.5 wheel diameters.
   - A bigger wheel rolls over bigger steps (a wheel fails above roughly its radius, per [Ascento](https://arxiv.org/abs/2005.11435)) but costs wheel torque linearly in r.
6. **Gear ratios seen:**
   - 1:1 direct drive: Diablo's six joints; Ascento, Upkie and Skythinker wheels.
   - Quasi-direct drive (QDD) about 6–10:1: RobStride 02 is 7.75:1; qdd100, CyberGear and TITA's modules are also QDD.
   - Series-elastic: Ascento's hip (ANYdrive).
   - Wheels stay direct drive; legs use low-ratio QDD for back-drivability and impact tolerance.
7. **Springs/gravity compensation:** Ascento's torsion springs cut hip effort while standing and add jump height ([paper](https://arxiv.org/abs/2005.11435)). This matters most when using a direct-drive or small leg motor that would otherwise hold load continuously.
8. **Printed structure:**
   - Ascento used SLS PA12 with topology optimisation ([paper](https://arxiv.org/abs/2005.11435)).
   - Upkie's FDM legs broke until v2's fork-shaped lower leg ([FOSDEM](https://ftp.fau.de/fosdem/2026/ub2147/8PUMMD-open-source-robotics-practice-upkie-wheeled-bipeds.vtt)).
   - RP_Balance had a printed part under a motor creep from heat and vibration ([README](https://github.com/WilliamGwok/RP_Balance)).
   - Venus-1 used FR4 plates for structure and print only for the electronics bay ([README](https://github.com/track-tech/Venus-1__Four-link-wheel-legged-robot)).

---

## 4. RL and sim-to-real for wheel-legged bipeds

### Published or public work

- **Ascento, blind stair climbing** ([arXiv 2402.06143](https://arxiv.org/html/2402.06143v1)).
  - Setup: Isaac Gym, PPO with an asymmetric actor-critic (rsl_rl), 4096 envs, ≈5k iterations on one DGX A100.
  - Actions: leg joints get PD position targets; wheels get angular-velocity targets. They found a position-based formulation essential for stairs.
  - Actuator modelling: no actuator network, but a **20 ms control delay** is simulated.
  - Without delay randomization, joints oscillated at up to 15 rad/s on hardware; with it they stayed under 1.5 rad/s.
  - High sim friction let the policy exploit grip that the real robot did not have.
  - Without privileged critic inputs, success on 14 cm steps was 0 %.
- **Upkie** ([ppo_balancer](https://github.com/upkie/ppo_balancer), now on [Codeberg](https://codeberg.org/upkie/ppo_balancer); Apache-2.0).
  - PyBullet + Stable-Baselines3 PPO, 1M steps.
  - Wheels-only **ground-velocity action** (≤2 m/s, ≤10 m/s²), agent at 200 Hz, 16×16 MLP, 10-step observation history.
  - Sim-to-real measures: low-pass filter, action and observation noise.
  - [mjlab_upkie](https://github.com/MarcDcls/mjlab_upkie) (Apache-2.0) is a GPU MuJoCo-Warp velocity task: legs on position actions, wheels on velocity actions. Hardware deployment is "planned".
- **DDT TITA** ([tita_rl](https://github.com/DDTRobot/tita_rl), MIT).
  - Isaac Gym, NP3O (constrained PPO), Webots sim-to-sim check, TensorRT on Orin NX.
  - Legs: PD Kp 40 / Kd 1.0. Wheels: velocity loop. Policy rate ≈100 Hz.
  - Domain randomization: friction 0.2–2.75, added mass −1…+3 kg, motor strength 0.8–1.2, Kp/Kd 0.8–1.2, **3-step lag**.
- **DDT Diablo** ([Col_DIABLO_Issac_RL](https://github.com/DDTRobot/Col_DIABLO_Issac_RL), no licence).
  - Isaac Gym, forked from Wheel-Legged-Gym.
  - Gains: hip Kp 15 / Kd 0.3, knee Kp 18 / Kd 0.2, wheel Kd 0.3.
  - ≈3000 iterations to converge. No peer-reviewed Diablo RL paper was found.
- **Wheel-Legged-Gym** ([clearlab-sustech](https://github.com/clearlab-sustech/Wheel-Legged-Gym); BSD-3 text inherited from legged_gym, which GitHub reports as NOASSERTION).
  - Isaac Gym. One variant has the policy output **virtual-leg (VMC) angle and length targets** instead of joint targets.
  - Domain randomization includes 0–10 ms action delay and 2 m/s pushes.
- **LimX TRON 1 wheel-foot** ([tron1-rl-isaaclab](https://github.com/limxdynamics/tron1-rl-isaaclab), Apache-2.0, ships a USD).
  - Six leg position actions (scale 0.25) plus two wheel-velocity actions.
  - Actuators: ImplicitActuator legs Kp 40 / Kd 2.5; wheels Kp 0 / Kd 0.8. Policy at 50 Hz.
  - The code carries a "TODO: change to delayed implicit actuator".
  - The [Isaac Gym version](https://github.com/limxdynamics/tron1-rl-isaacgym) (BSD-3) randomizes 0–20 ms delay.
- **Wheeled quadruped technique** (ANYmal / Swiss-Mile, [arXiv 2405.01792](https://arxiv.org/html/2405.01792)).
  - Joints use an SEA actuator network.
  - Wheels use a **learned map from velocity command to motor current**, then τ = Kt·GR·I.
  - Joint friction is randomized.
- **Community Isaac Lab projects:**
  - [jaykorea/Isaac-RL-Two-wheel-Legged-Bot](https://github.com/jaykorea/Isaac-RL-Two-wheel-Legged-Bot), MIT.
  - [zyicome/Wheel-Legged-Lab](https://github.com/zyicome/Wheel-Legged-Lab), Apache-2.0: balance, locomotion and jumping.
  - [scutrobotlab/wheeled-legged_RL](https://github.com/scutrobotlab/wheeled-legged_RL), MIT, Isaac Lab 2.1/2.3.
  - These licences come from the GitHub API; we did not read the repos in depth.

**Common recipe across the wheel-legged RL work above:**
- Leg joints: PD position targets.
- Wheels: velocity targets on a damping-only drive (Kp = 0, Kd ≈ 0.3–0.8).
- Policy rate: 50–100 Hz.
- Randomize: 0–20 ms delay, Kp/Kd and motor strength ±10–20 %, friction, added base mass and CoM.

### Isaac Lab status

- Isaac Lab v3.0.0 (2026-10-20) ships **no wheel-legged asset or task** in `isaaclab_assets` / `isaaclab_tasks` (subagent check of [IsaacLab](https://github.com/isaac-sim/IsaacLab)).
- Available actuator models: Implicit, IdealPD, **DCMotor** (a torque–speed envelope from stall torque and no-load speed), **DelayedPD**, RemotizedPD (angle-dependent limit for linkages) and ActuatorNet MLP/LSTM.
- A `BamActuatorCfg` (Rhoban BAM) was merged to main on 2026-10-15. It is not in v3.0.0 and needs the Newton/MJWarp backend.
- [Rhoban BAM](https://github.com/Rhoban/bam) (Apache-2.0, [paper](https://arxiv.org/pdf/2410.08650v1)) identifies Stribeck and load-dependent friction. It ships fits for Dynamixel, eRob80 and **Feetech STS3215**.

### Licences of possible starting points

| Repo | Sim | Licence |
|---|---|---|
| [limxdynamics/tron1-rl-isaaclab](https://github.com/limxdynamics/tron1-rl-isaaclab) | Isaac Lab, with USD | **Apache-2.0**. Best fork base |
| [DDTRobot/tita_rl](https://github.com/DDTRobot/tita_rl) | Isaac Gym | **MIT** |
| [DDTRobot/DDT_Lab](https://github.com/DDTRobot/DDT_Lab) | Isaac Lab 2.3 / Isaac Sim 5.1 (TITA, D1) | **none**: all rights reserved, reference only |
| [DDTRobot/Col_DIABLO_Issac_RL](https://github.com/DDTRobot/Col_DIABLO_Issac_RL) | Isaac Gym | **none** |
| [clearlab-sustech/Wheel-Legged-Gym](https://github.com/clearlab-sustech/Wheel-Legged-Gym) | Isaac Gym | BSD-3 text (legged_gym heritage) |
| [upkie/upkie](https://github.com/upkie/upkie), [upkie_description](https://github.com/upkie/upkie_description) | Bullet / MuJoCo | **Apache-2.0** |
| [MarcDcls/mjlab_upkie](https://github.com/MarcDcls/mjlab_upkie) | mjlab | **Apache-2.0** |
| [mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie) | MuJoCo | no wheel-legged biped models |

---

## 5. Open Duck Mini, and Hugging Face / Pollen's Microduck

### What exists

- **Open Duck Mini v2** by Antoine Pirrone ([apirrone](https://github.com/apirrone), R&D engineer at Pollen Robotics, team Rhoban).
  - Repo: [Open_Duck_Mini](https://github.com/apirrone/Open_Duck_Mini), Apache-2.0, ≈4.5k stars.
  - A small walking biped inspired by Disney's BDX droid, sponsored by Hugging Face and Pollen Robotics. ≈42 cm tall with legs extended. The README targets a BOM "under $400".
  - No "v3" was found.
- **Microduck** ([pollen-robotics/microduck](https://github.com/pollen-robotics/microduck), Apache-2.0).
  - A Hugging Face / Pollen commercial successor: ≈25 cm, 800 g, 15 servos, Rockchip RK3566, 50 Hz control.
  - It walks, **roller-skates on passive wheels**, picks things up with its beak and self-rights.
  - **$399**; pre-orders opened 2026-08-27; $39 accessory pack with roller attachments ([Pollen](https://pollen-robotics.com/microduck), [TechCrunch](https://techcrunch.com/2026/08/27/hugging-face-is-selling-a-cute-399-open-source-duck-robot-microduck/)).
  - NP-F550 battery (≈1 h); two IMUs, an 8×8 ToF sensor, camera, microphones and speaker ([CNX Software](https://cnx-software.com/2026/08/28/microduck-a-duck-like-biped-robot-designed-for-physical-ai-experimentation-and-fun)).
  - Pollen asked the press not to call it "open-source hardware".
  - RL code: [microduck_rl](https://github.com/pollen-robotics/microduck_rl). Code is Apache-2.0; **STL meshes are CC BY-NC-SA 4.0**.
- Upkie's maintainer cited Open Duck Mini at FOSDEM 2026 as reproduced "more than 50 times", "very cute", and trainable with one command ([transcript](https://ftp.fau.de/fosdem/2026/ub2147/8PUMMD-open-source-robotics-practice-upkie-wheeled-bipeds.vtt)).

### What makes it cute

- **Open Duck:** head on a 4-DOF neck (neck pitch plus head pitch/yaw/roll), two antennas on 9 g hobby servos, planned LED eyes, a projector, and random sounds triggered from the gamepad ([Runtime README](https://github.com/apirrone/Open_Duck_Mini_Runtime), [BOM sheet](https://docs.google.com/spreadsheets/d/1gq4iWWHEJVgAA_eemkTEsshXqrYlFxXAPwO515KpCJc)).
- **Microduck adds character features:**
  - a **per-robot voice synthesized from a seed**, with pitch, nasality and "quackiness" ([microduck_sounds](https://github.com/apirrone/microduck_sounds));
  - petting detection with a head microphone ([microduck_pet_detect](https://github.com/apirrone/microduck_pet_detect));
  - a Tamagotchi-style app that "sleeps cutely" when the robot is offline ([microduck_app](https://github.com/apirrone/microduck_app)).
- **Microduck's heavy head:** it is 38 % of body mass and must bob while walking. Penalizing the bob too hard made the policy stand still ([microduck_rl AGENTS.md](https://github.com/pollen-robotics/microduck_rl/blob/develop/AGENTS.md)).
- **Disney BDX** ("Design and Control of a Bipedal Robotic Character", RSS 2024, [arXiv 2501.05204](https://arxiv.org/html/2501.05204v1)): 0.66 m, 15.4 kg, 5 DOF per leg plus 4 neck/head.
  - Design followed creative intent rather than function. Animators iterated on proportions and gait in a procedural tool that reports joint torques.
  - Show functions (antennas, eyes, lamp, sounds) run **open-loop, outside the RL policy**.
  - There is one policy each for standing, walking and tricks, switched at runtime.
  - Rounded foam soles give passive roll compliance.

### How Open Duck is built

Sources: [print guide](https://github.com/apirrone/Open_Duck_Mini/blob/main/docs/print_guide.md), [BOM](https://docs.google.com/spreadsheets/d/1gq4iWWHEJVgAA_eemkTEsshXqrYlFxXAPwO515KpCJc), [assembly guide](https://github.com/apirrone/Open_Duck_Mini/blob/main/docs/assembly_guide.md).

- **Printing:** fully 3D printed in **standard PLA at 15 % infill**, with TPU foot soles at 40 %. About 500 g of filament. Heat-set M3 inserts.
- **Servos:** 14 × **Feetech STS3215 7.4 V "19 kg·cm"** at ≈€14 each: 5 per leg plus 4 neck/head.
  - The identified sim model caps torque at **3.35 N·m** ([Open_Duck_Playground](https://github.com/apirrone/Open_Duck_Playground)).
  - Servo controller: Waveshare Bus Servo Adapter (A).
- **Electronics:** Raspberry Pi Zero 2W, BNO055 IMU, 4 foot switches, 2S 18650 pack (Molicel P30B) with BMS, and a 5 V UBEC.
- **Cost:** BOM total €398.10 (€432.34 with the expression package). Kit on Tnkr is $600 ([Tnkr](https://tnkr.ai/explore/docs/open-duck-mini/open-duck-mini-v2)).
- **Mass:** ≈2.1 kg, summed from MJCF body masses (**derived** by the subagent; no published figure).
- **Known problems:**
  - A builder with the C001 1:345 servo variant gets ≈2.7 rad/s, but training assumes 5.24 rad/s, so gaits fail ([issue #48](https://github.com/apirrone/Open_Duck_Mini/issues/48)).
  - A full 2S pack is 8.4 V into servos rated 7.4 V ([issue #51](https://github.com/apirrone/Open_Duck_Mini/issues/51)).
  - A screw head wore its own slot into a printed hip part ([issue #17](https://github.com/apirrone/Open_Duck_Mini/issues/17)).
  - No reports of PLA structural failure were found. Note that this is a 2.1 kg robot with ≈3 N·m joints.

### How it was trained

- **Open Duck** ([Open_Duck_Playground](https://github.com/apirrone/Open_Duck_Playground); no licence file):
  - MuJoCo Playground / MJX.
  - **Imitation reward on reference motions** from a parametric Placo walk engine, fitted to polynomials ([Open_Duck_reference_motion_generator](https://github.com/apirrone/Open_Duck_reference_motion_generator); no licence file).
  - **Motors identified with Rhoban BAM**; STS3215 parameters are published ([bam params](https://github.com/Rhoban/bam/tree/main/params/feetech_sts3215_7_4V)).
  - Timing: 50 Hz policy, 500 Hz sim, action scale 0.25, action and IMU delay randomized 0–3 steps.
  - Domain randomization: friction 0.5–1.0, mass ±10 %, CoM ±5 cm, kp ±10 %, joint offsets ±0.03 rad.
  - Backlash is modelled.
  - Masses in the model come from the slicer, not CAD ([sim2real.md](https://github.com/apirrone/Open_Duck_Mini/blob/main/docs/sim2real.md)).
  - Gain units differ between firmware and sim: firmware kp 32 ≈ MuJoCo 17.8 ([issue #20](https://github.com/apirrone/Open_Duck_Mini/issues/20)).
- **Microduck** ([microduck_rl](https://github.com/pollen-robotics/microduck_rl)):
  - mjlab (MuJoCo Warp), PPO at 50 Hz; a usable gait in 1–2 h at 4096 envs.
  - BAM motor models with battery voltage and **voltage sag** randomized.
  - **Backlash ±1° as a passive hinge, with the encoder read through the play.**
  - One shared 61-dimensional observation across all policies, which are swapped at runtime. The roller-skate tasks use passive wheels.
- **Microduck author lessons** ([AGENTS.md](https://github.com/pollen-robotics/microduck_rl/blob/develop/AGENTS.md)):
  - Actuator fidelity is "most of the sim2real gap".
  - Do no action filtering unless training and runtime match.
  - Randomization must not accumulate across resets; one CoM bug degraded runs "for months".
  - Train the all-zero command explicitly.
  - Use potential-based shaping and no "jackpot" rewards.
  - Run a smoke test before every long run.

### Lessons from Open Duck Mini for wobbit

1. **Character is cheap and separate from the policy.** Copy the open-loop show layer from Disney and Open Duck:
   - a head or "face" on a small neck (1–3 DOF), antennas or ears on hobby servos, LED or screen eyes, sounds;
   - a **seeded per-robot voice**, petting or touch detection, and an idle "sleep" behaviour.
   - None of this touches the balance controller.
2. **Proportions:** a big head/body over short legs reads as cute (BDX, Open Duck, Microduck).
   - wobbit's 206 × 181 × 112 mm Orin box is a natural "big head/body". Put the face on it.
   - Treat the box like Microduck's 38 %-of-mass head: give it a **body-pitch/height command input**, allow some natural bob, and randomize its mass and CoM.
3. **Low-cost printed build works at small scale:** PLA at 15 % infill, heat-set inserts, TPU soles.
   - But Open Duck is ≈2 kg on ≈3 N·m joints. wobbit will be ~6–9 kg with ~5–12 N·m knees (section 3), so **PLA loads are 3–4× higher**.
   - Combine this with the Upkie (printed tibia and femur broke) and RP_Balance (printed part crept under a hot motor) findings. For wobbit in PLA:
     - use high wall counts / ≥40 % infill on load paths;
     - put **bearings and metal shafts at every pivot**; PLA must not be the bearing surface (see Open Duck's screw wearing its own slot);
     - **never clamp PLA directly against a motor housing**; PLA softens near 55–60 °C and creeps under sustained load;
     - make the fork/double-shear leg links Upkie v2 moved to;
     - plan the links as swappable consumables until CF-nylon or plate parts arrive.
4. **RL pipeline to copy:**
   - identify the actual actuators (BAM-style, including voltage sag);
   - confirm the **exact gear variant and voltage** match the sim limits;
   - model backlash as a passive hinge with the encoder read through it;
   - randomize 0–3 steps of action and IMU delay at 50 Hz;
   - use slicer masses (not CAD) in the URDF;
   - one shared observation space with swappable mode policies (balance / drive / jump / "trick");
   - optionally, an imitation term from a reference-motion generator for expressive moves.
5. **Microduck's passive-wheel "roller mode" plus policy switching** is the closest public template for mixing legged expression with wheeled motion on a cheap printed robot.
6. **Licence hygiene:** three Open Duck repos and several DDT repos have no licence. Pick wobbit's licence on day one, and only fork code with a clear permissive licence.

---

## 6. Comparison table

"—" means unknown. Sources are in the sections above and in `reference-robots.json`.

| Robot | Open? | Height (mm) | Mass (kg) | Payload (kg) | Wheel Ø (mm) | Leg topology | Leg motors | Wheel motors | Battery | Price (US$) |
|---|---|---|---|---|---|---|---|---|---|---|
| DDT Diablo | SDK Apache-2.0; models unlicensed | 491 / 270 | 22.9 | 4 (80 creeping) | 200 (RL URDF) | coaxial hip + knee motors at body + four-bar; no abduction | 4 × M1502D direct drive | 2 × M1502D direct drive | 32 V 6 Ah | 4,399 |
| DDT TITA | RL MIT; URDF unlicensed | 490 / 300 | 24.1 (w/o battery) | 10 | 185 (URDF) | serial with hip abduction, 4 DOF per leg | QDD modules, 120 N·m peak | QDD (in 8 DOF) | 43.2 V, 1 h × 2 hot-swap | 12,999 |
| Ascento (2019 research) | no | 310–660 | 10.4 | — | — | 1 hip motor + 3-bar linkage + torsion springs | 2 × ANYdrive SEA, 40 N·m | 2 × Maxon EC90 frameless direct drive, 3.5 N·m | 4 × 3S LiPo + 4S (compute) | — |
| Upkie | Apache-2.0 | — | ≈5.3 (URDF) | — | 112 | serial 2-link, knee motor on leg | 4 × mjbots qdd100, 16 N·m peak | 2 × moteus dev kit (direct), 1.7 N·m | RYOBI 18 V | ≈3,000 |
| LimX TRON 1 (wheel feet) | sim Apache-2.0 | 845 (size incl.) | ≤20 | ≤10 | — | — | 30 N·m rated / 60 peak, 48 V | — | 46.8 V 4.5 Ah, ≤2 h | 25,000 (EDU) |
| Skythinker foc-wheel-legged | GPL-3.0 | — | — | — | — | closed linkage, 2 body motors per leg (VMC) | 4 × 4010 gimbal, 0.22 N·m | 2 × 2804 gimbal | 3S 800 mAh | ≈75 (¥549) |
| Venus-1 | GPL-3.0 | — | — | — | 90 | four-bar | 2 × CyberGear | 2 × DJI M2006 geared | 24 V LiPo | ≈355 (¥2,576) |
| Multivac11 | no licence | — | 12.9 | — | 150 | five-bar (150/150/270 mm) | 4 × Unitree A1 | 2 × DJI M3508 | — | — |
| Open Duck Mini v2 | Apache-2.0 (main) | ≈420 | ≈2.1 (MJCF) | — | n/a (walker) | 5-DOF serial legs + 4-DOF neck | 14 × Feetech STS3215 | n/a | 2S 18650 | <400 (BOM) |
| Microduck (Pollen/HF) | code Apache-2.0; meshes CC BY-NC-SA | ≈250 | 0.8 | — | passive roller add-on | 15-servo biped | XL330-class servos (per BAM model) | passive | NP-F550 | 399 |

The CNY → USD conversions are approximate, at about ¥7.2 per $1, and are not from a source.

---

## 7. What wobbit should copy / avoid

### Copy

1. **Heavy leg motors at the body, light legs.** Use either:
   - Diablo-style coaxial hip + knee motors with a four-bar/parallelogram to the knee, or
   - a symmetric five-bar with both motors on the body.

   Both keep leg inertia low and let the body hold the actuators. Treat the leg in sim as an equivalent serial chain (DDT does this in its RL URDF) or as a virtual leg (Wheel-Legged-Gym VMC task).
2. **Direct-drive wheel motors** (a gimbal/hub BLDC with FOC and an absolute encoder), not geared hobby motors. Size the wheels so peak torque per wheel ≈ 1–1.5 × m·g·r/2, with speed headroom at v_max (section 3).
3. **QDD leg actuators sized for continuous crouch torque**, not peak alone. RobStride 02 / CyberGear / DM-J4310 class (≈12–17 N·m peak, ≈$125–180) fits a 6–9 kg robot with 0.12–0.15 m links. Consider a gravity-compensation spring (Ascento) so standing does not cook the knees (Diablo's 15-minute squat limit).
4. **Wheel ≈150–200 mm, segments ≈0.7–1.0 × wheel diameter.** Diablo and TITA sit at 185–200 mm wheels for ~490 mm standing height. A smaller robot can scale down; Upkie uses 112 mm.
5. **RL recipe:**
   - leg PD position targets plus wheel velocity targets on damping-only drives, policy at 50–100 Hz;
   - DCMotor torque–speed limits, 0–20 ms delay randomization, Kp/Kd/strength ±20 %, backlash, moderate friction;
   - asymmetric actor-critic;
   - fork **limxdynamics/tron1-rl-isaaclab (Apache-2.0)**;
   - check in MuJoCo before hardware.
6. **Character layer from Open Duck / Disney:** open-loop face, antennas, sounds and seeded voice on the Orin "head", plus mode policies sharing one observation space.
7. **Upkie's hardware habits:** parametric CAD (FreeCAD/Onshape) so leg lengths change in one place, external cable routing, an add-on screw pattern on the body, and a handle or bumpers.

### Avoid

1. **Geared or backlash-prone wheel drives.** Venus-1's M2006 backlash made the body shake at the balance point.
2. **Holding torque on direct-drive knees without a margin.** Diablo can squat for only ≈15 min.
3. **PLA as the bearing surface or clamped against motors.** Expect PLA to creep above ~50 °C (RP_Balance's deformed part, Open Duck's worn screw slot). Expect printed legs to break until they become forks or double-shear (Upkie v1 → v2). Use bearings, metal pins, inserts and swappable link parts, and move to CF-filled filament or plate for the leg links once the geometry is frozen.
4. **Single-encoder actuators without a homing strategy.** CyberGear needs re-zeroing at every power-up (Venus-1). Prefer absolute output encoders, or design hard stops for homing.
5. **Unlicensed starting code.** DDT_Lab, the Diablo RL repo, the TITA URDF and several Open Duck repos have no licence file, so use them as reference only.
6. **Ignoring actuator dynamics in sim.** Without delay randomization, Ascento oscillated at up to 15 rad/s on hardware. Microduck's authors say actuator fidelity is "most of the sim2real gap". Open Duck builders with the wrong servo gear ratio could not walk.
7. **Hip abduction in v1.** Diablo, Upkie, Ascento and every hobby build balance without it. TITA has it, at 8 DOF and $13k. Leave it out until there is a reason; leaning on uneven ground can come from differential leg length.

