# Foam-dart turret and kid safety for Gyropup

Checked 2026-10-25. Parts and prices are in [`catalog/turret.json`](../catalog/turret.json) (32 items, category `turret`, plus one
`sensor`). The pan motor recommended below, the Damiao DM-J4310-2EC, is already in
[`catalog/leg_actuators.json`](../catalog/leg_actuators.json).

Gyropup is a Tritium robot: kids play against it outdoors, with a foam-dart turret on its head (requirement R25 in
[docs/requirements.md](../docs/requirements.md)). This file covers five things:

1. Launcher mechanisms
2. Pan/tilt
3. Recoil
4. Kid safety
5. Outdoor driving

It ends with a recommended turret, its mass, power and cost budget, and a list of safety requirements.

**Conventions**

- "n/p" means not published.
- Numbers marked **calc** are my arithmetic on sourced inputs.
- Numbers marked **est** are my engineering estimates. They are not sourced, and they need to be measured.
- Out of Darts (OOD) product data was read from each product's own store record (`/products/<handle>.js`).
- The fps figures from OOD are the shop's own 20-shot chronograph averages unless noted
  ([method](https://outofdarts.com/blogs/news/nerf-by-numbers-how-we-test-blaster-performance)).
- Unit conversions: 1 fps = 0.3048 m/s, so 70 fps = 21.3 m/s, 100 fps = 30.5 m/s and 150 fps = 45.7 m/s.

## Summary

- **Recoil does not matter for balance.**
  - One 1.0 g dart at 80 fps carries 0.024 N·s. A 10-dart burst carries 0.24 N·s.
  - On a 15 kg robot, that burst changes speed by 0.016 m/s. The average force while firing at 10 darts/s is the same as
    leaning about 0.14°.
  - Slewing the turret disturbs the robot more than firing does. RoboMaster's balancing robots shoot heavier 17 mm balls
    and, in the code I read, do nothing special for recoil.
- **The safety limit is energy per dart, not recoil.**
  - The toy standards give two limits:
    - EN 71-1: 0.5 J for resilient projectiles.
    - ASTM F963: 2500 J/m² kinetic-energy density above 0.08 J.
  - With 1.0 g short darts, these work out to about 104 fps (EN 71) and about 85 fps (ASTM). The ASTM figure assumes the
    whole 13 mm dart face is the contact area.
  - A stock Nerf blaster measures about 65–73 fps. Hobby games cap at 100–150 fps. Brushless hobby blasters reach
    140–200 fps.
- **Recommended limits:**
  - Short darts at a default of 70 fps.
  - A hard cap of 80 fps (24.4 m/s, 0.30 J). The cap is enforced by flywheel speed and checked on every shot by a
    muzzle chronograph.
  - The barrel never points above horizontal in the world frame.
  - The turret only fires at worn targets, never at faces.
- **Recommended turret:**
  - Launcher: brushless flywheels with a Neutron solenoid pusher and a 15-round Talon magazine.
  - Tilt: Feetech STS3215 servo. Pan: DM-J4310-2EC motor, with a 12-wire slip ring for continuous pan.
  - Budget: about 1.3 kg (est), about $415 (part-sourced), 25–35 W while ready to fire, and peaks of a few hundred
    watts for under a second.
- **Moving near kids.** A 15 kg robot cannot meet cobot contact limits at play speeds. The ISO/TS 15066 adult values
  (calc) give about 0.15 m/s for a shin and about 0.28 m/s for a thigh, so speed must depend on distance to the nearest
  person. Boston Dynamics tells people to stay at least 2 m from Spot.

---

## 1. Foam-dart launcher mechanisms

### 1.1 How the options work

- **Flywheel ("flywheeler").**
  - Two counter-rotating wheels grip the dart and fling it. The cage crush (wheel spacing) and the wheel speed set the
    velocity.
  - Motors come in two kinds:
    - Brushed "130" motors (Kraken, Fang, Valkyrie) on 2S–3S.
    - Small brushless outrunners (1404, 1507.5, 2205/2206 FPV class) on 4S, run through ESCs.
  - This is the only type that suits a robot: it can fire continuously, needs no priming, and its velocity can be set
    electronically.
- **Pusher.** The pusher moves a dart from the magazine into the wheels. Options:
  - A solenoid (the Neutron is the hobby standard).
  - A gear-motor cam (Atrox, Juno: 600 rpm motor ≈ 9 balls/s).
  - A servo (simple turrets).
  - A solenoid gives one dart per stroke, so the controller can count every shot and cap the rate of fire exactly.
- **Springer** (Harrier, Caliburn). A spring piston is primed by hand. It is high-energy (Harrier 183–205 fps) and needs
  manual or motorised priming. It is a poor fit for a robot and is not considered further.

### 1.2 Ammunition

| Ammo | Mass | Size | Notes | Source |
|---|---|---|---|---|
| Worker HE short ("half") dart | **1.0 g** (0.9 g light, 1.2 g heavy) | 13 × 36 mm | OOD reference dart; fits standard "Talon" magazines | [OOD](https://outofdarts.com/products/worker-he-standard-weight-short-darts-200-pack-1-0g) |
| Worker full-length dart | **1.28 g** | 13 × 72 mm | "Elite-spec"; fits stock Nerf | [OOD](https://outofdarts.com/products/worker-full-length-foam-darts) |
| Nerf Elite dart | n/p (≈1 g: 10 darts ≈ 10 g on a kitchen scale) | 7.2 cm × 1.2 cm (retailer) | Hasbro does not publish mass | [Orzel](https://chadorzel.com/principles/?p=9912) |
| Rival round (Worker Cheetah) | **1.75 g** | 22.7 mm ball | Hasbro Rival is 14+ with eyewear recommended | [OOD](https://outofdarts.com/products/worker-cheetah-rounds-rival-compatible-ammo-100-pack) |
| Accufire / AccuStrike | n/p | n/p | No mass found; not pursued | — |
| DJI S1 gel bead | 0.12–0.17 g (soaked) | 5.9–6.8 mm | Not foam | [DJI store](https://store.dji.com/product/robomaster-s1-gel-beads) |

**Short darts are the right choice for Gyropup:**

- They are the lightest, so they carry the least energy at a given speed.
- Their magazines are short.
- The standard Talon magwell is shared by Blitz, Protean, Momentum and Harrier.

**Rival balls are a poor fit.** They are 75 % heavier, so they carry 75 % more energy at the same speed. Hasbro rates
the Rival Helios at 100 fps for ages 14+ and recommends eyewear
([Hasbro](https://consumercare.hasbro.com/product/nerf-rival-helios-xviii-700-red/73F68C0E-507D-437D-B8A5-23C60A000A53)).

### 1.3 Blasters and launch modules compared

| Blaster / module | Type | Muzzle velocity | Rate of fire | Mass | Motors / power | Control | Price | Licence / CAD |
|---|---|---|---|---|---|---|---|---|
| Stock Nerf Elite flywheeler (Stryfe class) | brushed flywheel | ≈65–73 fps (reviewer chronos; physicist measured 20.9–22.1 m/s) | semi | n/p | 130 motors, 4×AA | trigger switch | n/p | closed |
| [OOD Stryfe Ultimate Mod Kit](https://outofdarts.com/products/stryfe-ultimate-mod-kit) | brushed flywheel mod | 155 fps short / 177 fps full | semi | kit 120 g | 2× Kraken/Fang, 2S/3S LiPo | microswitch | $57.99 | closed blaster |
| [Chance Blitz](https://outofdarts.com/products/chance-blitz-hardware-kit) | brushed flywheel + solenoid | 96 / 100 / 126 fps (22 / 19.5 / 25 mm cages) | solenoid | **321 g** assembled | 2× Kraken, 3S | microswitches + MOSFET | $65.99 kit | [Printables](https://www.printables.com/model/1003532-blitz) CC-BY-NC-SA, STL |
| [Flygonial Gryphon](https://outofdarts.com/products/flygonial-gryphon-hardware-kit) | brushed flywheel | n/p | manual pusher | kit 142 g | 2× Kraken, Daybreak wheels | microswitch | $44.99 kit | [Printables](https://www.printables.com/model/208101-the-gryphon-foam-dart-blaster) **CC0** |
| [Flygonial Protean (OOD ed.)](https://outofdarts.com/products/flygonial-protean-hardware-kit) | brushed flywheel + solenoid | 102 / 123 / 133 / 141 fps for 42 / 41.5 / 41 / 40 mm cages | solenoid | 672 g (listing) | 4× Kraken, 3S | MOSFET | $109.99 kit | [Printables](https://www.printables.com/model/1830195-flygonial-protean-modular-flywheel-blaster-ood-edi) CC-BY-NC-SA |
| [Worker Nightingale 2.0](https://outofdarts.com/products/worker-nightingale-2-blaster) | brushed micro-flywheel | 110 (2S) / 127 (3S) / 134 (4S) fps | 6 / 11 / 15 rps (full-auto) | n/p | 132 motors | stock board | $84.99–94.99 | closed |
| [Xtra Atrox](https://outofdarts.com/products/xtra-atrox-brushless-flywheel-blaster) | brushless flywheel + brushless cam pusher | ≈140 fps | 12 rps | 582 g | brushless, own battery | OLED, USB-C firmware | $139.99 | closed |
| [Hare Tech Diana](https://outofdarts.com/products/hare-tech-diana-brushless) | brushless + solenoid | ≈140 fps (4S) | 16 rps | 590 g | 2 brushless, 4S | fire modes, motor idle | $249.99 | closed |
| [Hare Tech Vesper](https://outofdarts.com/products/hare-tech-hc-tac-vesper-brushless-flywheel-blaster) | brushless 1404 + solenoid | **presets 48 / 134 / 176 fps** (4S) | ≈15 rps | 990 g (no battery) | 2× 1404, 4S | velocity + fire-mode presets, 120 ms response | $314.99 | closed |
| [Eli Wu Momentum](https://outofdarts.com/products/eli-wu-momentum-dual-stage-brushless-blaster) | 2-stage brushless + Neutron | presets 100–200 fps, firmware up to 215 | presets 7–26 rps, up to 35 | n/p | 4× Supernova 1507.5, 4S | custom board, fps/ROF/burst presets | $649.99, **sold out** | closed |
| [Project FDL-3](https://github.com/Nikkelmann/FDL-3-Blaster) | flywheel, modular noses/tails | n/p (unitless 0–100 "Speed") | 0–100 "ROF", burst 1/2/3/auto | n/p | 3S (12.6 V full) | OLED firmware v1.05; MinSpin 120–500 ms | n/p | CC BY-NC-SA 4.0; CAD + STL folders |
| [Tops76 Dart Turret](https://github.com/Tops76/Dart-Turret) | brushless flywheel turret | "max 140 km/h" = 38.9 m/s ≈ 128 fps | n/p | n/p | 2× Armattan 2206 2300 KV, 20–30 A ESCs, 4×18650 | ESP32; **built-in dart speed sensor**; 2× Waveshare SC15 servos | DIY | [Printables](https://www.printables.com/model/338574-nerf-dart-turret-brushless-wifi-wip) CC-BY-NC-SA |
| [Juno (Rival)](https://outofdarts.com/products/juno-rival-blaster-hardware-kit) | brushed flywheel, gear-motor pusher | 130 fps (Kraken) | ≈9 balls/s | n/p | Krakens, 3S | — | $89.99 kit | [Printables](https://www.printables.com/model/1876250-out-of-darts-juno-full-auto-rival-flywheel-blaster) CC-BY-NC-SA |
| Nerf N-Strike Elite TerraScout (B8072, 2016) | RC tracked drone with dart launcher | n/p | n/p | ≈11.25 lb (one spec sheet) | 9.6 V NiMH | RC + 720p camera | $200 at launch; discontinued | closed ([Hasbro instructions](https://instructions.hasbro.com/en-us/instruction/Nerf-N-Strike-Elite-TerraScout)) |
| DJI RoboMaster S1 (gel beads) | 2-axis gimbal + gel blaster | ≈26 m/s | 1–8/s, max 10/s | 3.3 kg robot | — | app | discontinued | closed |

Notes on the table:

- **Stock Nerf velocity sources:**
  - Physicist Chad Orzel filmed a Nerf dart at 22.1 ± 0.3 m/s and 20.9 ± 0.2 m/s, with darts of ≈1 g each
    ([blog](https://chadorzel.com/principles/?p=9912)).
  - Retailer user reviews with ProChrono chronographs report 65–73 fps for stock Elite/Modulus blasters. These are
    single reviewers and are only indicative.
  - Hasbro does not publish fps for Elite blasters. It does publish 90–100 fps for Rival.
- **TerraScout details** come from search snippets of retailer and news listings (18-dart clip, later a 35-dart drum,
  720p camera). I could not fetch a primary spec page, so treat them as unverified.
- **Not found:**
  - No "Caliburn" flywheel exists. The Caliburn is Captain Slug's public-domain, spring-powered, pump-action blaster
    ([Thangs](https://thangs.com/prints/designer/ZackFreedman/3d-model/Caliburn%20-%20Mag-Fed%20Pump-Action%20Nerf%20Blaster-14003);
    from a search result, because the page blocks direct fetches).
  - No project called "Hy-Fly" could be found.
  - No "Nerf Sentry" product exists. TerraScout is Hasbro's only robot.
- **Cage crush works as a mechanical velocity limiter.** The Protean's numbers show this: the same motors give 102 fps
  with a 42 mm cage and 141 fps with a 40 mm cage. A deliberately wide-crush cage limits velocity even if the software
  fails.

### 1.4 Launch motors, pushers, feed

| Part | Key specs | Price | Source |
|---|---|---|---|
| **Eli Wu Neutron solenoid** | 209 g; 26 mm stroke; 20–35 N push; 2.3 Ω coil; up to 25 A; 10 rps on 3S, 18 rps on 4S, up to 40 rps with a 32 V boost circuit and an upgrade spring; [STEP](https://www.dropbox.com/s/tnca329kvp6ozdi/High%20ROF%20Solenoid.STEP?dl=0) | $29.99 | [OOD](https://outofdarts.com/products/eli-wu-neutron-compact-high-rate-of-fire-solenoid) |
| **Supernova 1507.5 brushless** | 4200 KV, 1.5 mm T-mount, 19.4 mm OD, 4S recommended; mass n/p | $26.99 each | [OOD](https://outofdarts.com/products/supernova-brushless-motors-for-momentum) |
| OOD Kraken 130 (brushed) | 3S, 35,000 rpm idle, 0.55 A idle, 26 A stall, 740 g·cm stall | $8.99 | [OOD](https://outofdarts.com/products/ood-kraken-130-3s-neodymium-high-performance-motor) |
| DJI Snail 2305 + C615 | 27.8 g; 21,000 rpm at 24 V; 0.4 A no-load; C615 15 A continuous, **26 V max**, PWM; STEP linked | $40 motor / $100 with C615 | [aifitlab](https://aifitlab.com/products/dji-robomaster-snail-2305-motor-c615-speed-controller) |
| BLHeli LittleBee-Spring 30 A ESC | 2–6S, 30 A continuous / 35 A burst, DShot; RPM telemetry n/p | $12.99 | [OOD](https://outofdarts.com/products/brushless-esc-30a) |
| Worker Nightingale micro-flywheels | 18.1 mm OD, 2 mm bore, 3 g each, acetal | $8.99 pair | [OOD](https://outofdarts.com/products/nightingale-flywheel-pair) |
| Worker metal cage V3 (Stryfe pattern) | 88 g, 43.5 mm spacing | $22.00 | [OOD](https://outofdarts.com/products/worker-metal-flywheel-cage) |
| **Worker 15-round straight Talon mag** | 105 g, 240 × 36 × 19 mm | $9.99 | [OOD](https://outofdarts.com/products/worker-15-round-straight-standard-talon-short-dart-magazine-clip) |
| OOD Koda 23-round mag | 115 g, 315 mm long, glass-fibre nylon | $19.99 | [OOD](https://outofdarts.com/products/ood-koda-23rd-talon-magazine) |
| OOD Infinite Pack (Rival hopper) | 1250 g, ≈430 balls, blower-pressurised hose feed, 20 rps continuous / 30+ burst through up to 4 ft of hose | $259.99 kit | [OOD](https://outofdarts.com/products/ood-infinite-pack-rival-hopper) |
| DJI M2006 P36 (RoboMaster feed dial) | 90 g, 36:1, 1 N·m rated | $95 | [aifitlab](https://aifitlab.com/products/dji-robomaster-m2006-p36-brushless-dc-gear-motor) |

**Feed options:**

- **Magazine.** Talon or Worker short-dart mags, 15–23 rounds. This is the simplest and most reliable option.
- **Belt.** No off-the-shelf dart belt feed was found.
- **Hopper.** A blower-pressurised hopper exists only for Rival balls (the Infinite Pack).

**For Gyropup:** use one 15-round magazine for a capped, game-sized load, then reload. Swapping magazines is a natural
"pit stop" in a kids' game.

**Power and control in practice:**

- **Brushed builds** switch the flywheel motors with a microswitch or MOSFET and fire the solenoid through a MOSFET with
  a flyback diode. The OOD parts sold for solenoid builds include 1N5400 rectifier diodes.
- **Brushless builds** use hobby ESCs (PWM, OneShot or DShot). Firmware-driven blasters (Momentum, Vesper, FDL-3)
  expose speed, rate-of-fire and spin-up settings.
- **Spin-up time.** The FDL-3 firmware's MinSpin range of 120–500 ms (default 220 ms) shows the scale. Motor idling
  (Diana, Vesper) cuts trigger response to 120–160 ms.

---

## 2. Pan/tilt for a 0.5–1.5 kg head

### 2.1 Torque and speed needed (est)

**Tilt:**

- Assumed payload: 1.0 kg with its centre of gravity 20 mm off the tilt axis.
- Holding torque ≈ 0.2 N·m.
- Inertia ≈ 1.0 kg × (0.08 m)² ≈ 0.0064 kg·m².
- Reaching 300 °/s in 0.1 s needs α ≈ 52 rad/s², which takes ≈ 0.33 N·m.
- **Total: about 0.5 N·m.**

**Pan:**

- About 1.2 kg at roughly 70 mm radius gives ≈ 0.01 kg·m².
- At the same acceleration, pan needs ≈ 0.5 N·m. It also has to reject the body's yaw motion.

**Speed:**

- A child running 5 m/s at 3 m range needs about 1.7 rad/s (≈ 95 °/s) of tracking.
- A pan capability of 180–360 °/s covers that plus the robot's own turning.
- The DJI RoboMaster S1 gimbal is specified at 540 °/s maximum.

**Safety cap on pan speed:**

- In software, cap pan speed when people are within reach (see §4.6).
- Basis (calc): ISO/TS 15066 adult face values of 65 N and 75 N/mm, with a 1 kg moving turret.
  - Contact speed limit ≈ 0.26 m/s.
  - With the muzzle 0.15 m from the pan axis, that is ≈ 1.75 rad/s ≈ 100 °/s.

### 2.2 Actuators compared

| Actuator | Mass | Torque | Speed | Voltage | Interface / encoder | Price | Source |
|---|---|---|---|---|---|---|---|
| **Feetech STS3215 (12 V)** | 89 g (Waveshare; others list 55 g) | 30 kg·cm ≈ 2.9 N·m stall | 45 rpm (270 °/s) no-load | 6–12.6 V | TTL serial bus to 1 Mbps; 12-bit absolute magnetic, 360° | $21.99 | [Waveshare](https://www.waveshare.com/st3215-servo.htm?sku=22414) |
| ROBOTIS XM430-W350-T | 82 g | 4.1 N·m stall at 12 V | 46 rpm at 12 V | 10–14.8 V | TTL to 4.5 Mbps; 4096 counts/rev | $310.39 | [e-manual](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/), [store](https://www.robotis.us/dynamixel-xm430-w350-t/) |
| **Damiao DM-J4310-2EC** (already in catalog) | 306 g | 3 N·m rated / 7 N·m peak | 200 rpm no-load at 24 V | **15–32 V** (fits the 7S bus) | CAN / CAN-FD; dual 14-bit encoders, output absolute | $125 | [leg_actuators.json](../catalog/leg_actuators.json), [GitHub](https://github.com/dmBots/DM-J4310-2EC) |
| DJI RoboMaster GM6020 | 468 g | 1.2 N·m rated | 320 rpm no-load, 132 rpm at rated torque | 24 V rated (maximum n/p) | CAN or PWM; 13-bit; **18 mm hollow shaft** | $225 (aifitlab) | [RoboMaster](https://www.robomaster.com/en-US/products/components/general/GM6020), [aifitlab](https://aifitlab.com/products/dji-robomaster-gm6020-brushless-dc-motor) |
| Waveshare SC15 (as used in Tops76 turret) | n/p | "17 kg" | n/p | n/p | serial bus | n/p | [Tops76 BOM](https://github.com/Tops76/Dart-Turret) |

**Gear rings.**

- A direct-drive QDD (DM-J4310, GM6020) on the pan axis needs no ring gear.
- A servo pan can drive a printed ring gear or belt (for example 3:1). That trades speed for torque and lets the servo
  sit off-axis so the slip ring can go on the axis.
- No sourced ring-gear product was selected.

### 2.3 Slip rings for continuous pan

| Slip ring | Circuits | Current | Max rpm | IP | Price | Source |
|---|---|---|---|---|---|---|
| **Adafruit 1196**, 22 mm capsule, 44 mm flange | 12 × 28 AWG | 2 A each, 240 V | 300 | n/p | $19.95 | [Adafruit](https://www.adafruit.com/product/1196) |
| Ingiant DHK012-12, through-bore 12.7 mm | 12 (also 6 / 18 / 24) | 2, 5 or 10 A each | 300 (600 custom) | IP51 (IP54 / IP65 optional) | quote | [Ingiant](https://www.ingiant-slipring.com/12-7mm-id-through-bore-slip-ring-12-circuits-5a10a-380vac-300rpm-ip51-hollow-shaft-rotary-connector-product/) |

**Wiring for the Adafruit ring:**

- Run 12 V power to the launcher as two rails, each paralleled over 3–4 circuits.
- Run the CAN/UART signal on a twisted pair.
- Use the rest for the arming loop: the dead-man/e-stop line must reach the launcher without depending on software.
- Alternative: give the pan a limited range (for example ±170°) and use a cable chain. This avoids the slip ring's
  contact noise and wear.

### 2.4 Existing robot turrets and what they teach

**DJI RoboMaster S1**
([user manual specifications](https://cdn.multitronic.fi/media/7/3/mmo_76336354_1576855122_309_26320.pdf), DJI 2019):

| Spec | Value |
|---|---|
| Mass | about 3.3 kg |
| Gimbal pitch range | −20° to +35° controllable (−24° to +41° mechanical) |
| Gimbal yaw range | ±250° controllable (±270° mechanical), so **not continuous** |
| Gimbal speed | 540 °/s max |
| Vibration control | ±0.02° (flat surface, blaster idle) |
| Blaster | ≈ 26 m/s, 1–8 shots/s controllable, 10/s max |

The manual also says:

- "make sure to wear the safety goggles provided by DJI"
- "DO NOT aim the blaster at people or animals"

So DJI's own gel-bead robot is not meant to shoot people.

**RoboMaster infantry and balancing infantry robots**

These are the most relevant precedent: they carry a gimbal and launcher on a wheel-legged balancing chassis.

- **Gimbal control.** DJI's standard infantry firmware, reused by teams, controls the gimbal in "gyro mode" from the
  gimbal's IMU: an angle loop driving a speed loop for yaw and pitch, with an encoder mode as fallback. See
  [gimbal_task.h](https://github.com/wu-shidong/ZSTU_RoboMaster2023_Balancing-infantryV1_Program/blob/master/application/gimbal_task.h)
  from Zhejiang Sci-Tech's 2023 balancing infantry. The gimbal is stabilised in the world frame and the chassis follows.
- **Shooting.**
  [shoot.h](https://github.com/wu-shidong/ZSTU_RoboMaster2023_Balancing-infantryV1_Program/blob/master/application/shoot.h)
  does the following:
  - Ramps the friction-wheel speed up before firing is allowed.
  - Drives a trigger (feed-dial) motor in angle steps.
  - Detects a jam (trigger speed too low for too long) and reverses.
  - Keeps a barrel-heat budget from the referee system.
- **Recoil.** I found no recoil feed-forward in the shoot or gimbal code I read. Disturbance rejection is left to the IMU
  loops, which fits the small impulses computed in §3.
- **Wheel-leg control.** Current teams publish their designs:
  - [Fudan's RM2026 balancing infantry](https://github.com/chushanxiaodaoshi/XYEGA_RM2026_WheelLeg_Infatry_RLdeploy)
    runs an RL policy at 100 Hz inside a 500 Hz loop. It uses four DM 8009P hip motors and two 3508 wheel motors, plus
    supercapacitors to stop the hip motors dropping out on undervoltage.
  - Other repos: [COD 2024](https://github.com/GrassFanWang/COD-2024RoboMaster-Balanced_Infantry) (VMC and Vision tasks)
    and [Mas 2025](https://github.com/zpclyn/Mas2025_Balance_Control).
- **Over-speed policing.** The RoboMaster referee system measures projectile speed at the muzzle with a speed monitor
  module ([17 mm version](https://www.robomaster.com/en-US/products/components/detail/1296): 175 g, 1–50 m/s,
  1–50 Hz). Older rules capped 17 mm launch speed at 30 m/s and deducted HP for violations
  ([2018 rules](https://cdn-hz.robomaster.com/documents/cc95944f46941529667085614363746.pdf)).
- **What Gyropup copies from RoboMaster:**
  - A world-stabilised gimbal from the gimbal's own IMU.
  - A spin-up gate before firing.
  - Jam detection.
  - A per-shot speed check with lockout.

**Hobby Nerf turrets**

Many hobby turrets use face tracking, for example
[brianlevis/nerf-iron-dome](https://github.com/brianlevis/nerf-iron-dome) (Unlicense, RapidStrike, HS-805BB servos,
"track and engage faces") and [rohan-bansal/NerfTurret](https://github.com/rohan-bansal/NerfTurret). Gyropup must do
the opposite and **suppress fire when a face is in the line of fire**. The
[Tops76 Dart Turret](https://github.com/Tops76/Dart-Turret) is the closest hardware match: brushless flywheels,
serial-bus-servo gimbal and an integrated speed sensor.

---

## 3. Recoil

**Reaction impulse per dart = dart mass × muzzle velocity** (calc).

- This holds for a flywheel launcher: the wheels push on the dart, and the cage pushes back on the turret.
- The air the dart drags along is ignored.
- A counter-rotating flywheel pair has close to zero net angular momentum. Panning the turret then creates almost no
  gyroscopic torque, and the two motors' spin-up reaction torques cancel.

| Velocity | Short dart 1.0 g: per dart / 10-dart burst / KE | Full dart 1.28 g: per dart / 10-dart burst / KE | Rival 1.75 g: per round / 10 / KE |
|---|---|---|---|
| 70 fps (21.3 m/s) | 0.021 N·s / 0.21 N·s / 0.23 J | 0.027 / 0.27 N·s / 0.29 J | 0.037 / 0.37 N·s / 0.40 J |
| 80 fps (24.4 m/s) | 0.024 / 0.24 N·s / 0.30 J | 0.031 / 0.31 N·s / 0.38 J | 0.043 / 0.43 N·s / 0.52 J |
| 100 fps (30.5 m/s) | 0.031 / 0.31 N·s / 0.46 J | 0.039 / 0.39 N·s / 0.59 J | 0.053 / 0.53 N·s / 0.81 J |
| 130 fps (39.6 m/s) | 0.040 / 0.40 N·s / 0.79 J | 0.051 / 0.51 N·s / 1.00 J | 0.069 / 0.69 N·s / 1.37 J |
| 150 fps (45.7 m/s) | 0.046 / 0.46 N·s / 1.05 J | 0.058 / 0.59 N·s / 1.34 J | 0.080 / 0.80 N·s / 1.83 J |
| 200 fps (61.0 m/s) | 0.061 / 0.61 N·s / 1.86 J | 0.078 / 0.78 N·s / 2.38 J | 0.107 / 1.07 N·s / 3.25 J |

For comparison, a DJI S1 gel bead carries 0.003–0.004 N·s (0.12–0.17 g at 26 m/s).

### What the balancing robot feels (calc)

Assumptions:

- Robot mass 15 kg.
- Muzzle 0.6 m above the wheel axle.
- Pitch inertia about the axle ≈ m·l² = 15 × 0.4² = 2.4 kg·m², taking the centre of mass 0.4 m up.

| Case | Linear Δv | Pitch-rate kick Δω = J·h / I | Average force at 10 darts/s | Equivalent static lean |
|---|---|---|---|---|
| One short dart at 80 fps (0.024 N·s) | 0.0016 m/s | 0.006 rad/s | — | — |
| 10 short darts at 80 fps (0.24 N·s) | 0.016 m/s | 0.061 rad/s if all at once | 0.24 N, so 0.15 N·m | **0.14°** |
| 10 full darts at 150 fps (0.59 N·s) | 0.039 m/s | 0.15 rad/s if all at once | 0.59 N, so 0.35 N·m | 0.34° |

**What disturbs the robot more than recoil:**

- **Turret slew reaction.** Tilting a 1 kg head at 52 rad/s² puts ≈ 0.33 N·m (est) back into the body. That equals
  about a 0.3° lean, already larger than a whole capped burst.
- **Payload.** The robot also carries a 1.3 kg payload whose centre of gravity moves as the turret tilts. A 20 mm shift
  of a 1.2 kg turret moves the robot's centre of mass by about 1.6 mm.
- **A child's push.** A child pushing the robot is a far larger disturbance than any of the above.

**Design conclusion:**

- No recoil compensation is needed in the balance controller.
- Model each shot as a known impulse in simulation (the sim's recoil scenario) to confirm this.
- Spend control effort on two things instead:
  - World-frame turret stabilisation.
  - Feeding the turret's commanded accelerations forward into the balance controller.

---

## 4. Kid safety

### 4.1 Toy-projectile rules

| Rule | Requirement | Source |
|---|---|---|
| **ASTM F963-17 §4.21.2.3** (projectile toys with stored energy) | Projectiles with KE > 0.08 J (test 8.14.5) "shall not have a kinetic energy per unit area of contact … (KED) greater than 2500 J/m²" (test 8.14.6) | [Intertek summary of F963-17](https://www.intertek.com.cn/eninfo_itemid_6742_lcid_40.html); [CPSC enforcement letter, 2017](https://www.cpsc.gov/s3fs-public/TIA_projectile%20toys_let_3.31.17.pdf) |
| ASTM F963-23 | Mandatory US toy standard for toys made on or after 20 Apr 2024. Projectile changes: a revised bow-and-arrow test, the conditioning sequence in 8.14.3 / 8.14.5.4 / 8.14.6.2 reordered, and environmental conditions changed. Whether the 0.08 J / 2500 J/m² values changed was not verified | [Bureau Veritas](https://cps.bureauveritas.com/newsroom/cpsc-approves-federal-toy-safety-standard-update-effective-date-april-20-2024) |
| **EN 71-1 §4.17.3** (2011+A3:2014 text) | Max KE **0.08 J** for rigid projectiles without resilient impact surfaces, **0.5 J** for resilient projectiles; arrows > 0.08 J need resilient tips ≤ 0.16 J/cm² (1600 J/m²); rigid tip radius ≥ 2 mm; warning if the toy can fire other projectiles > 0.08 J | [EN 71-1 text](https://law.resource.org/pub/eu/toys/en.71.1.2014.html) |
| EN 71 (QIMA summary) | "projectiles with a kinetic energy greater than 0.08 J must have a kinetic energy per unit area of no more than 2500 J/m²" | [QIMA](https://www.qima.com/consumer-products/lab-testing/toy-gun-projectile-safety) |
| ISO 8124-1:2022 | International counterpart; text paywalled, numbers not retrieved | [ISO via ANSI](https://webstore.ansi.org/standards/iso/iso81242022) |

**Limits applied to darts** (calc):

- KED assumes the whole 13 mm dart face is the contact area, which is 1.33 × 10⁻⁴ m².
- The F963 test method 8.14.6 was not read, so the true contact area may differ.

| Ammo | EN 71 0.5 J limit | ASTM 2500 J/m² limit |
|---|---|---|
| Short dart 1.0 g | ≤ 31.6 m/s (104 fps) | ≤ 0.33 J, so ≤ 25.8 m/s (**85 fps**) |
| Full dart 1.28 g | ≤ 28.0 m/s (92 fps) | ≤ 22.8 m/s (**75 fps**) |
| Rival 1.75 g, 22.7 mm | ≤ 23.9 m/s (**78 fps**) | ≤ 34 m/s (112 fps) |

**Checks against products:**

- A full-length dart from a stock blaster at 70 fps has a KED of ≈ 2200 J/m², just under the limit. This fits stock Nerf
  being designed around these rules.
- Hasbro's 100 fps Rival Helios puts ≈ 0.8 J into a 1.75 g ball. That is above the EN 71 resilient figure, and Hasbro
  grades the product 14+.

**Toy standards do not directly cover Gyropup.** They govern toys sold for children; a robot used to run a game is not
a toy. They are still the best published, kid-specific energy limits, so Gyropup adopts them as design targets.

### 4.2 Field practice: velocities and eyewear

| Source | FPS cap / velocity | Eye protection | Other rules |
|---|---|---|---|
| Stock Nerf Elite (measured) | ≈ 65–73 fps; ≈ 21–22 m/s | Box warning | — |
| Hasbro Rival Helios | 100 fps (30 m/s); other Rival 90 fps | "Use of eyewear recommended for players and people within range"; "Do not aim at eyes or face"; 14+ | [Hasbro](https://consumercare.hasbro.com/product/nerf-rival-helios-xviii-700-red/73F68C0E-507D-437D-B8A5-23C60A000A53) |
| Univ. of Waterloo Humans vs Zombies | "must fire under 100 FPS"; modded ball blasters banned; hard-tipped darts banned | — | [rulebook](https://uwhvz.uwaterloo.ca/static/files/Rulebook-vWKND.pdf) |
| GameSchoolCon "Nerf battles all ages" | 150 fps | "All players must have eye protection for each round"; full face masks not allowed | "NO POINT BLANK SHOTS ABOVE THE NECK!", aim at torso/legs, "Hold" call stops play | [sched](https://gameschoolcon2025.sched.com/event/1moVl/nerf-battles-all-ages) |
| Out of Darts (Pacific NW games); Endwar 2022 | "commonly have a 150 cap"; Endwar soft cap 130 fps on a 5-shot average | — | Chronograph each blaster before play | [OOD](https://outofdarts.com/blogs/news/nerf-by-numbers-how-we-test-blaster-performance) |
| Hobby brushless blasters | 140–200+ fps (Diana, Atrox, Vesper high, Momentum) | — | — | OOD listings above |

**Injuries are real even at stock energies:**

- BMJ Case Reports (Bizrah & Verma, 2017, doi:10.1136/bcr-2017-220967) describes three traumatic hyphaemas from Nerf
  darts. The authors call for protective eyewear and a review of age limits. This is reported via secondary pages,
  because the BMJ newsroom returned 403.
- Eye News (Joshi, Troiani & Kulshrestha, June 2023) reports three eye injuries:
  - An 11-year-old hit at close range: corneal oedema and hyphaema.
  - A 12-year-old hit from 3 m: hyphaema.
  - An adult hit from 2 m: a retinal hole needing laser treatment.
  - The authors recommend that safety goggles be supplied with Nerf guns
    ([Eye News](https://www.eyenews.uk.com/education/case-reports/post/traumatic-injuries-from-foam-nerf-bullets)).

### 4.3 What this means for the turret

1. **Velocity.** Default 70 fps; hard cap **80 fps (24.4 m/s)** with 1.0 g short darts.
   - That gives 0.30 J, which is under EN 71's 0.5 J. KED is ≈ 2240 J/m² (calc), under ASTM's 2500.
   - Never use Rival balls or full-length darts at the short-dart setting.
   - Enforce the cap in three independent ways:
     - Flywheel RPM (closed loop, brushless).
     - A wide-crush cage that cannot exceed the cap at full motor speed. Verify this on the bench.
     - A muzzle chronograph on every shot. Any shot over 80 fps locks the launcher out until a human resets it.
2. **Rate of fire.** At most 3 darts/s and a 5-dart burst limit in the kids' game (a design choice), with a magazine of
   15. The solenoid makes each dart countable.
3. **Elevation.** The barrel must never point above horizontal in the world frame.
   - Gyropup balances by leaning, so the body pitch changes all the time. A tilt limit relative to the body is not
     enough. Measure the limit with the turret's own IMU in the world frame.
   - Add a mechanical hard stop that holds even at the robot's worst-case forward lean.
   - Ballistics (calc, no drag, so these are upper bounds). From a 0.5 m muzzle at 0° and 24 m/s, a dart is at
     ≤ 0.47 m at 2 m range and ≤ 0.29 m at 5 m. At +10° it reaches 1.17 m at 5 m, which is a child's face height.
   - So also predict the dart's height at every range up to its maximum. Inhibit firing if the predicted path passes
     through the head zone (≥ 0.9 m) of any detected person, or the leg height changes the muzzle height enough to.
4. **Targeting.**
   - Fire only at worn targets: a vest or belt panel with a fiducial or colour patch at belly height or lower.
   - Never fire at a detected face or head.
   - Never fire at animals.
   - Never fire at anyone not wearing a target, which covers bystanders, parents and toddlers.
   - The opposite approach, "track and engage faces" (iron-dome), is explicitly forbidden.
5. **Range.** No firing at a person closer than 2 m. The "no point-blank above the neck" rule exists for this reason, and
   two of the Eye News injuries came from close range.
6. **Eyewear and game rules.** Players need eye protection. The robot checks for it where practical (eyewear-detection
   flag) but does not rely on it. The game master holds the dead-man switch.

### 4.4 Dead-man switch, e-stop, safe zone

- **Two-level stop.**
  - **Wireless e-stop:** cuts motor power for both drive and turret through hardware, and must work if the computer
    hangs. See the `estop` items in [power_electronics.json](../catalog/power_electronics.json) and
    [power-electronics.md](power-electronics.md).
  - **Turret disarm:** a separate hardware contactor on the 12 V launcher rail. It needs a held dead-man button (or a
    continuous heartbeat from the game-master remote) to stay closed. If the dead-man is released, or the link is lost
    for more than about 200 ms (est), the turret disarms. The robot keeps balancing, because a balancer that drops
    power falls over.
- **Visible state.** An LED ring or beacon shows SAFE (green), ARMED (amber) and FIRING (red), plus a buzzer when armed.
  An orange muzzle is used, as on OOD's Momentum: "all muzzles will always be printed in orange".
- **Safe zones.** Geofenced or tagged areas (entry, spectators, the pit where magazines are reloaded) where the turret
  is disarmed and the drive speed is capped at crawl.

### 4.5 Speed and contact with a 15 kg robot

**ISO/TS 15066 (collaborative robots, adults).** The permissible contact speed is
v = F / √(μ·k), where μ = (1/m_H + 1/m_R)⁻¹. Values from
[arXiv 2311.13814, Table 1](https://arxiv.org/pdf/2311.13814):

- Lower legs: 130 N, 60 N/mm, m_H 75 kg.
- Thighs and knees: 220 N, 50 N/mm, 75 kg.
- Face: 65 N, 75 N/mm, 4.4 kg.

Contact speeds (calc). The whole robot is taken as moving mass, which is conservative.

| Contact | 15 kg robot | 7.5 kg (half, e.g. an effective mass) |
|---|---|---|
| Shin (lower leg) | **0.15 m/s** | 0.20 m/s |
| Thigh / knee | 0.28 m/s | — |
| Face, struck by a 1 kg turret | 0.26 m/s | — |

These are adult industrial limits; children are not covered. Play needs faster movement than this, so the robot has to:

- slow down by distance to the nearest person;
- avoid driving at people; and
- keep its contact surfaces soft.

**Boston Dynamics on Spot** ([user guide R2.0](https://www.generationrobots.com/media/spot-boston-dynamics/spot-user-guide-r2.0-va.pdf)):

- "People must stay a safe distance (at least 2m) from Spot during operation to avoid injury."
- Injuries "may be caused by collisions, Spot falling or tipping onto people, or contact with Spot's pinch points".
- Fingers "may break or get amputated if caught in joints while Spot's motors are active".

Gyropup is lighter than Spot but has the same hazards: falling, tipping, collisions and leg pinch points.

**Sidewalk robots.** Iowa's personal-delivery-device law caps them at 6 mph (2.7 m/s) in pedestrian areas and at
550 lb ([Iowa Code 321O](https://www.legis.iowa.gov/docs/code/2026/321O.html)). That is far heavier and faster than
Gyropup. Use it only as an upper bound.

**Stopping distance** (calc): d = v·t_r + v²/(2a), with a 0.25 s reaction time (est). A balancer must first tilt back
before it can brake, so its deceleration a is lower than tyre friction alone would allow; 1.5–3 m/s² is assumed (est).

| Speed | Kinetic energy (15 kg) | Stop at 1.5 m/s² | Stop at 3 m/s² |
|---|---|---|---|
| 0.5 m/s | 1.9 J | 0.21 m | 0.17 m |
| 1.0 m/s | 7.5 J | 0.58 m | 0.42 m |
| 1.5 m/s | 16.9 J | 1.12 m | 0.75 m |
| 2.0 m/s | 30 J | 1.83 m | 1.17 m |

**Pinch points.**

- Hazards: the knee and hip linkages, wheel-to-leg gaps, and the pan bearing.
- Apply minimum gaps per ISO 13854. That standard covers crushing only; its table was not retrieved because it is
  paywalled ([ISO](https://www.iso.org/standard/66459.html)).
- Otherwise use covers: printed leg shrouds, a closed wheel arch and a skirted turret ring.
- Limit joint torque when a child or dog is within 1 m.

### 4.6 Dogs

- **Ingestion.** Pets eat foam darts. A cat needed surgery to remove a Nerf dart tip from its small intestine
  ([VetLove](https://vetlove.com.au/childs-nerf-toy-becomes-hazard/)). Count darts out and back in, and do a field sweep
  after the game.
- **No firing at animals.** The animal classifier inhibits fire whenever an animal is in the predicted fire cone. DJI
  forbids aiming its S1 at animals too.
- **Robustness.** Dogs chase and bite moving things. The robot needs:
  - bumpers and shrouds;
  - no exposed cables;
  - no loose straps on the turret; and
  - speed limits that apply to dogs as they do to children.

---

## 5. Outdoor driving for a 15 kg two-wheeled balancer

Wheel and motor choice is covered in [wheel-motors.md](wheel-motors.md). This section adds terrain.

### 5.1 Tyres

- **Pneumatic** (for example 10" hoverboard 10 × 2.125):
  - Grips and cushions better on grass and gravel, and spreads load on soft ground.
  - Adds spring and damping that the balance policy has to learn around ([wheel-motors.md](wheel-motors.md)).
  - Can puncture.
  - Pressure changes the rolling radius, which affects odometry.
- **Solid or semi-pneumatic** (BotWheel 171 mm solid tread, DDT M1502 tyre-wheel):
  - Predictable for control and puncture-proof.
  - Gives a harsher ride over roots and gravel.
- **Diameter and kerbs:**
  - Typical US kerbs are 6 in (150 mm) standard and 4–6 in sloped
    ([Iowa DOT](https://iowadot.gov/design-manual/chapter-3-cross-sections/3c-2-curbs)).
  - A 170–190 mm wheel (85–95 mm radius) cannot roll up a 150 mm kerb. Gyropup has to use its legs to step or hop, as
    the Diablo's four-bar legs do for "curb-climb" ([reference-robots.md](reference-robots.md)).
  - A rolling-only climb is realistic only well below the wheel radius. The exact limit depends on traction and lean
    and was not computed here.

### 5.2 Rolling resistance

Rolling resistance coefficients:

| Surface | Coefficient | Source |
|---|---|---|
| Short grass, 10 km/h | 0.049–0.09 | ATV tyres ≥ 480 mm, firm silt loam ([Petterson & Gooch, DESIGN 2020](https://doi.org/10.1017/dsd.2020.75)) |
| Short grass, 20 km/h | 0.07–0.10 | same |
| Long grass (200–250 mm), 20 km/h | 0.08–0.12 | same |
| Hard laneway | 0.035–0.09 | same |
| Gravel, loose and worn / medium-hard soil | 0.04–0.08 | Car tyres ([Engineering ToolBox](https://www.engineeringtoolbox.com/rolling-friction-resistance-d_1303.html)) |
| Concrete / new asphalt | 0.01–0.015 | same |
| Loose sand | 0.2–0.4 | same |

Small robot wheels (150–200 mm) on grass were not measured in any source found. They will sit **above** the ATV
values, because smaller wheels sink and climb more. Take 0.10–0.15 on lawn as a planning figure (est).

**Drive force on lawn** (calc): 0.12 × 15 kg × 9.81 = **18 N**, or about 9 N per wheel. Add slope:

- 15° adds 38 N.
- 10° adds 26 N.

### 5.3 Slopes in yards

- **Riding mowers.** UGA Extension says riding mowers "will slide and roll over on slopes greater than 27 percent"
  (≈ 15°). Push mowers "can be used on slopes up to 20 degrees"
  ([UGA](https://site.extension.uga.edu/forsyth/lawn-mower-safety-on-slopes-and-hills)).
- **One manufacturer's limit.** A Kentucky FACE fatality report (a mower rolled on a 30° slope) quotes the manual:
  "Under no circumstances should the machine be operated on slopes greater than 15 degrees"
  ([KIPRC 15KY041](https://kiprc.uky.edu/sites/default/files/2021-03/15KY041.pdf)).
- **Gyropup targets:**
  - Design for 15° on dry grass.
  - Refuse slopes over 20°, detected from the IMU and terrain.
  - Ban play near downhill edges, since a falling robot rolls.

### 5.4 Ingress protection

IEC 60529 codes, from a vendor summary because the IEC page returned 403:

- **IP54:** IP5X is dust-protected (limited ingress, 8 h dust chamber); IPX4 is splashing water from all directions.
- **IP65:** IP6X is dust-tight (no ingress); IPX5 is water jets (12.5 L/min, 6.3 mm nozzle, 3 m, 15 s).

Source: [summary](https://industrialmonitordirect.com/blogs/knowledgebase/iec-60529-ip-rating-water-protection-level-comparison).

**What already has a rating:**

- DDSM115 and BotWheel motors: IP54.
- DDT M1502: IP55 ([wheel-motors.md](wheel-motors.md)).
- Slip rings: IP54/65 variants exist (Ingiant).
- Foam darts and magazines: none. Wet darts swell and jam, and wet grass ruins them.

**Gyropup targets:**

- **Body and electronics: IP54 minimum.** Use gasketed lids, cable glands, a drip loop at the pan ring, and a vent with
  a membrane for the Orin's heat.
- **Turret:** splash shroud over the cage and magazine well.
- **No play in rain or on wet grass.**

---

## 6. Recommended turret concept for Gyropup

**Concept.**

- A world-stabilised 2-axis head with continuous pan.
- A single-stage brushless micro-flywheel cage, derived from the CC0 Gryphon geometry, with the crush set wide enough
  that full motor speed stays under the cap.
- A Neutron solenoid pusher.
- One 15-round standard Talon magazine of 1.0 g short darts lying along the pitch axis.
- A two-gate muzzle chronograph.
- An arming contactor on its own 12 V rail.

**Control.**

- A small MCU in the head does the following:
  - Closes the flywheel RPM loop.
  - Fires the solenoid.
  - Reads the chronograph.
  - Enforces the velocity, rate and elevation interlocks.
- The Jetson only requests shots at a validated target. The MCU can refuse.

### 6.1 Parts list

| # | Part | Qty | Unit price | Mass each | Source / status |
|---|---|---|---|---|---|
| 1 | Supernova 1507.5 4200 KV brushless motor | 2 | $26.99 | n/p (shipping weight 30 g); budget 30 g | catalog `eli-wu-supernova-1507-5-4200kv` |
| 2 | Brushless ESC with RPM telemetry (LittleBee 30 A shown; telemetry must be verified) | 2 | $12.99 | n/p; budget 9 g | `favourite-littlebee-spring-30a-esc` |
| 3 | Flywheels for 1.5 mm T-mount (printed, or OOD "Helix", whose price was not found) | 2 | est $5 | budget 5 g | est |
| 4 | Printed cage, barrel and turret structure (PETG/PLA-CF) | 1 | est $15 filament | est 250 g | est |
| 5 | Neutron solenoid + MOSFET + flyback/Zener | 1 | $29.99 + est $5 | 209 g | `eli-wu-neutron-solenoid` |
| 6 | Worker 15-round straight Talon magazine | 2 | $9.99 | 105 g (+15 g of darts) | `worker-15rd-straight-talon-short-dart-mag` |
| 7 | Worker HE 1.0 g short darts, 200-pack | 1 | $16.99 | 1.0 g/dart | `worker-he-short-darts-1-0g-200` |
| 8 | Tilt: Feetech STS3215 12 V + bus adapter | 1 | $21.99 + est $10 | 89 g | `feetech-sts3215-c018-12v` |
| 9 | Pan: Damiao DM-J4310-2EC (on the 24 V CAN bus) | 1 | $125 | 306 g | `damiao-dm-j4310-2ec` (leg_actuators.json) |
| 10 | Slip ring, Adafruit 1196 12-wire | 1 | $19.95 | n/p; budget 30 g | `adafruit-1196-slip-ring-22mm-12w` |
| 11 | Pan bearing (thin-section or turntable) | 1 | est $10 | est 60 g | est |
| 12 | Turret MCU + IMU (for example STM32/RP2040 + 6-axis IMU) | 1 | est $15 | est 15 g | est |
| 13 | Muzzle chronograph: 2 fast IR gates, photodiode + comparator. The Adafruit 2167 break-beam's "<2 ms" response is too slow at 24 m/s | 1 | est $10 | est 15 g | est |
| 14 | 7S to 12 V buck converter, ≥ 10 A, plus arming contactor/relay | 1 | est $35 | est 80 g | est; not yet in catalog |
| 15 | Status LED ring + buzzer | 1 | est $5 | est 15 g | est |
| 16 | Wiring, XT30, connectors | — | est $15 | est 60 g | est |

### 6.2 Mass budget

| Group | Mass |
|---|---|
| Launcher: motors, ESCs, wheels, cage share, solenoid | ≈ 60 + 18 + 10 + 120 + 209 = **417 g** |
| Magazine, loaded | 120 g |
| Structure (rest of the head) | 130 g (est) |
| Tilt servo | 89 g |
| Pan motor + bearing + slip ring | 306 + 60 + 30 = 396 g |
| Electronics: MCU/IMU, chronograph, buck/contactor, LEDs, wiring | ≈ 185 g (est) |
| **Total** | **≈ 1.34 kg** (mostly est). The pan motor is the stationary part on the body side, so the moving pitch assembly is ≈ 0.75 kg. |

**A lighter option** is about 1.1 kg: use a second STS3215 on a 3:1 ring gear for pan instead of the DM-J4310. It saves
≈ 217 g and $103, at the cost of pan speed. A 3:1 ring takes 270 °/s down to 90 °/s.

### 6.3 Power budget

Figures marked † are from comparable parts' published specs: the Snail 2305's 0.4 A at 24 V, and the Kraken's 0.55 A
at 11.1 V.

| State | Draw | Basis |
|---|---|---|
| Safe (powered, disarmed, holding pose) | ≈ 5–8 W | est |
| Armed, flywheels idling at target RPM | ≈ 15–30 W | est, from comparable no-load currents of 6–10 W per motor† |
| Spin-up (≈ 0.2 s) | up to ≈ 2 × 10 A × 12 V = 240 W if ESC current is limited to 10 A | calc on an assumed limit |
| Solenoid stroke | 12 V / 2.3 Ω = 5.2 A peak, ≈ 62 W per stroke | calc. At ≤ 3 shots/s the average is ≈ 10–20 W (est) |
| Pan/tilt slewing | DM-J4310 peak 7.5 A × 24 V = 180 W; typically ≪ that | sourced peak; typical is est |
| **Game average** (50 % armed, 10 % firing) | **≈ 20–35 W** | est. About 10 % of a 252 Wh 7S2P pack per hour ([power-electronics.md](power-electronics.md)) |

### 6.4 Cost

- **Sourced parts:** ≈ $315. That is 2×26.99 + 2×12.99 + 29.99 + 2×9.99 + 16.99 + 21.99 + 125 + 19.95.
- **Estimated items:** ≈ $100.
- **Total: ≈ $415.**
- **Cheaper brushed option:** a Chance Blitz kit ($65.99, 321 g, 100 fps with Nightingale wheels on 3S) as a ready
  launcher module. It has no speed feedback, so the chronograph lockout becomes the main velocity guard. Its open-loop
  velocity also changes with battery voltage.

### 6.5 Why this concept

- **Brushless + RPM loop + crush + chronograph** gives three independent velocity limits. The Vesper's 48/134/176 fps
  presets show that brushless firmware can hold low velocities.
- **A solenoid gives one dart per stroke,** so every shot is counted and rate-limited.
- **Talon magazines are a standard,** short darts are the lowest-energy ammo, and reloading is quick.
- **DM-J4310 pan on the existing CAN bus.**
  - It has the same driver and protocol as the rest of Gyropup.
  - Its absolute output encoder keeps pan known through power loss.
  - Its 15–32 V range accepts the 7S pack directly, which the GM6020 (24 V rated) and C615 ESC (26 V max) may not.
- **STS3215 tilt.**
  - It is light, cheap and absolutely encoded, so tilt is known at boot before any shot.
  - Its 2.9 N·m stall torque is about 6 times the ≈ 0.5 N·m estimate.

---

## 7. Safety requirements

IDs are for traceability in the designer and the simulation.

| ID | Requirement | Enforced in |
|---|---|---|
| **S1** | Muzzle velocity default 70 fps, **hard cap 80 fps (24.4 m/s)** with 1.0 g short darts; ≤ 0.30 J and ≤ 2500 J/m² (calc) per dart | firmware + mechanics |
| S2 | Three independent velocity guards: (a) closed-loop flywheel RPM limit; (b) a cage crush that cannot exceed the cap at full motor speed, bench-verified with 20-shot chronograph tests; (c) every dart timed at the muzzle, and any shot over cap latches a lockout that needs a human reset | firmware + mechanics + test |
| S3 | Only approved ammo: Worker HE 1.0 g short darts. Magazine well geometry rejects full-length darts and balls | mechanics |
| S4 | Rate of fire ≤ 3 darts/s, burst ≤ 5, one 15-round magazine per round of play | firmware |
| **S5** | Barrel elevation ≤ 0° in the **world frame** (turret IMU). Mechanical up-stop holds at the worst-case body lean. Inhibit firing if the predicted dart path crosses ≥ 0.9 m height at any person's range | firmware + mechanics + sim |
| **S6** | Fire only at worn game targets (belly height or lower). Never fire if a face, head, animal or untagged person is inside the predicted fire cone. Face tracking for aiming is prohibited | perception + firmware |
| S7 | No firing at a person closer than 2 m | perception + firmware |
| S8 | Barrel settled before firing: pointing error and turret rate below thresholds; flywheels at set RPM (RoboMaster-style spin-up gate) | firmware |
| **S9** | Hardware wireless e-stop cuts drive and turret power independently of the computer | electrical |
| **S10** | Turret arming needs a held dead-man / heartbeat from the game master. Release or link loss over ≈ 200 ms (est) opens the 12 V launcher contactor. The robot keeps balancing and drives to a stop | electrical + firmware |
| S11 | Visible and audible state: green SAFE, amber ARMED, red FIRING, buzzer when armed; orange muzzle | hardware |
| S12 | Safe zones (entry, spectators, reload pit): turret disarmed, drive at crawl | firmware (geofence / tags) |
| **S13** | Drive speed by distance to the nearest person or dog: > 3 m: ≤ 1.5 m/s; 1–3 m: ≤ 0.5 m/s and no closing motion; < 1 m: ≤ 0.2 m/s, no approach. ISO/TS 15066 adult shin/thigh contact speeds (calc) are 0.15–0.28 m/s | firmware + sim |
| S14 | Braking distance at each speed limit is verified in simulation and on hardware against the zone sizes (§4.5 table) | sim + test |
| S15 | Pan speed ≤ 100 °/s (calc) when a person is within 1 m of the head; soft or foam-covered turret edges | firmware + mechanics |
| S16 | Pinch points guarded: leg shrouds, wheel arch, skirted pan ring, gaps per ISO 13854. Leg joint torque limited when anyone is within 1 m | mechanics + firmware |
| S17 | Soft bumpers on the leading surfaces at child-shin height | mechanics |
| S18 | Fall behaviour: if balance is lost, disarm the turret and fold the legs to fall low and inward, not onto people | firmware + sim |
| S19 | Eye protection required for all players (game rule). Robot shows a reminder; optional eyewear detection does not replace the rule | game rules |
| S20 | Count darts out and back in; sweep the field after play (pets eat foam) | game rules |
| S21 | Slope limit: play area ≤ 15°; robot refuses > 20° | firmware + site rules |
| S22 | No play in rain or on wet grass; electronics at IP54 minimum | site rules + mechanics |
| S23 | Log every shot: time, velocity, aim, target ID, and the interlock state at release | firmware |

## 8. Open questions

- **ASTM F963-23 projectile numbers.** These changed in 2023 and were not retrieved. Buy or borrow the standard, and
  check the KED contact-area definition in §8.14.6.
- **ESC RPM telemetry.** Confirm which small ESC firmware reports eRPM at 50k+ rpm (the LittleBee listing doesn't say).
  Otherwise put a hall or optical tach on one flywheel.
- **Flywheel speed for 70–80 fps.** Find the rpm and crush that give 70–80 fps with 1.0 g darts by bench test. This is
  far below the Momentum and Vesper "high" presets.
- **GM6020 maximum input voltage.** Not found. Needed only if the GM6020 replaces the DM-J4310.
- **Supernova motor mass and Helix flywheel price.** Not published in the listings fetched.
