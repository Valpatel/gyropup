# Launcher study for Gyropup's head turret: ammo, launcher, feed, motors, jams, safety

Checked 2026-10-25. This extends [turret-and-safety.md](turret-and-safety.md) (read that first: launcher basics,
recoil, toy-standard energy limits, pan/tilt, the S1–S23 safety list). It does not repeat that file's tables; where a
number here differs from it, §0.2 says so. New parts are appended to [`catalog/turret.json`](../catalog/turret.json).
The interface it has to fit is [docs/head-payload.md](../docs/head-payload.md).

**Conventions.** "n/p" means not published. **calc** marks my arithmetic on sourced inputs. **est** marks an
engineering estimate that is not sourced and needs measuring. Out of Darts (OOD) and other Shopify data were read from
each product's `/products/<handle>.js` record, whose `weight` field is a shipping weight unless the description gives a
part mass. 1 fps = 0.3048 m/s.

**The settings the user asked for.** Foam balls (Nerf Rival size) are the candidate for indoor play and gel blasters
for outdoor play. So §7 compares one ammo for both settings with an interchangeable launcher "cartridge" per ammo.

---

## 0. Summary

### 0.1 Recommendation

| Item | Recommendation |
|---|---|
| **Ammo** | **Rival-size foam balls** (22.7 mm, 1.75–1.85 g) indoors **and** on dry grass outdoors. Gel beads are not recommended for Gyropup's kids (§2.4); short darts stay as the alternative cartridge |
| **Launcher** | Dual counter-rotating brushless flywheels: 2 × DJI Snail 2305 (24 V, 27.8 g) on AM32 or C615 ESCs, run closed-loop on RPM |
| **Feed** | A 24–30-ball gravity hopper over a RoboMaster-style motorised dial (M2006 P36 + C610 on CAN), with stall detection and reverse |
| **Velocity** | Default 65 fps, **hard cap 70 fps (21.3 m/s)**: ≤ 0.42 J and ≈ 1030 J/m² per ball (calc, 1.83 g) |
| **Rate** | Hardware 10 balls/s; kids' mode 3/s, bursts ≤ 5 (unchanged from S4) |
| **Reload** | **Automatic, at the dock**: a silo on a dock mast pours counted balls into the head hopper while Gyropup sits (balls need no orientation; darts would need a magazine swap) |
| **Modularity** | A **launcher cartridge** boundary on the tilt cradle (feed + launcher + barrel + chronograph gate + ammo ID). Pan, tilt, power, MCU, IMU, laser and safety chain are shared. Practical: it costs ≈ 40 g (est) |
| **Mass** | ≈ 1.16 kg total (≈ 0.75 kg shared head + ≈ 0.41 kg ball cartridge with 24 balls; mostly est) |
| **Power** | 24 V from a **dedicated payload converter** fed from the 45–58 V bus through the turret arming contactor, not the J501's 24 V converter. ≈ 15–25 W armed idle, ≤ 40 W game average, short peaks ≈ 150 W from pan slews (est) |

### 0.2 What changes from the earlier study

- **Rival balls are no longer "a poor fit".** At the same fps they carry about 1.8× the energy of a 1.0 g short dart,
  but over 3× the contact area. Capped at 70 fps, a ball stays under EN 71's 0.5 J and far under ASTM's 2500 J/m²
  (§6.1). Balls also feed without orientation and can be poured in at the dock, which darts cannot.
- **RoboMaster numbers have moved.** The 2025 RMUC rules specify a 16.8 mm, 3.2 g TPU ball and a 25 m/s cap for
  17 mm launchers. The 30 m/s and 2.9 g figures were from 2018.
- **Official RoboMaster prices are lower.** DJI lists the Snail 2305 at $29, the C615 at $39 and the M2006 P36 at $41,
  against $40–$95 from resellers.
- **Hasbro's own Rival round averages 1.83 g** in a reviewer's weighing
  ([BlasterHub](https://blasterhub.com/2017/12/adventure-force-tactical-strike-rounds-review/)), heavier than
  Worker's 1.75 g.
- **A dart belt does exist:** the Nerf Vulcan's 25-dart belt, now only sold used. No modern belt-fed short-dart design
  was found.
- **The power plan is out of date.** The default design now runs on a 15S FLEXVOLT (45–58 V, D25). Its 12 V rail is a
  30 W Mean Well DDR-30L-12 that already feeds the lidar and headlights, so the launcher cannot hang off it (§8.5).
- **"Hy-Shot" is not a project.** The nearest match is torukmakto4's **Hy-Con** flywheel system. Captain Xavier has
  YouTube videos but no design of his own was found.

---

## 1. Custom foam-dart blasters and robot launchers on the internet

These are the designs not covered in [turret-and-safety.md §1.3](turret-and-safety.md). That table already lists the
Blitz, Gryphon, Protean, Stryfe kit, Nightingale, Atrox, Diana, Vesper, Momentum, FDL-3, Tops76 turret, Juno,
TerraScout and RoboMaster S1.

### 1.1 Foam darts

| Design | Mechanism | Dart | Velocity | Rate of fire | Feed | Motors / power | Mass | Files / licence | Source |
|---|---|---|---|---|---|---|---|---|---|
| **T19** (torukmakto4) | Single-stage brushless flywheel (Hy-Con) + **stepper "bolt drive"** pusher: NEMA17 OSM 17HS16-2004S1, 45 mm scotch-yoke stroke, DRV8825 driver | Full-length soft-tip; T19E1 also short darts | 160–175 fps | 11.3 rps normal, 13.8 turbo | Worker 22-round mags (T19); Talon mags (T19E1 short-dart breech) | 2205/2207 FPV motors (Emax RS2205S, Racerstar BR2207S, Turnigy V-Spec 2205) on SimonK/FlyShot ESCs; Turnigy 4S 1500 mAh | n/p | Google Drive, no licence stated | [prototype](https://torukmakto4.blogspot.com/2017/12/t19-prototype-build.html), [bolt drive](https://torukmakto4.blogspot.com/2017/12/on-delay-change-per-step-pitfall-and.html), [build guide](https://torukmakto4.blogspot.com/2019/01/t19-build-guide-part-12-final-assembly.html), [T19E1](http://torukmakto4.blogspot.com/2020/05/t19e1-product-improving-t19-system.html) |
| T19 stepper pusher, detail | Self-homing: bolt limit switch + step counting, "never fail to reset the bolt home within one cycle" | — | — | ≈ 8.3 rps on early code at 11.1 V | — | "at most an amp or so RMS"; Vref ≈ 1.0 V ≈ 2.0 A/phase | NEMA17 ≈ 300 g with mount (est) | — | same |
| **Hy-Con** (torukmakto4) | Single-stage brushless cage; groove gap 8.5 / 9.0 / 9.5 mm sets crush | Full-length | 170–190 fps (9.5 mm groove, 3S) | — | — | Turnigy V-Spec 2205 2350KV, ≥ 20 A ESCs, 3S | n/p | Tgy 9.0 cage CC BY-SA 4.0; prototype no licence | [HyCon_Prototype](https://github.com/torukmakto4/HyCon_Prototype), [Hy-Con-Tgy9.0](https://github.com/torukmakto4/Hy-Con-Tgy9.0) |
| QT19 (T19 derivative) | Hy-Con + **solenoid** instead of stepper (generic 35 mm stroke, ≈ $13) | — | — | 2-round burst that waits for rev | — | — | n/p | no licence | [GitHub](https://github.com/GrubbyLittleRaccoon/QT19-T19E1-derivative) |
| **Ultra cages** (Ultrasonic2): UltraStryfe, UltraSword | Brushless drop-in cages for Stryfe / Swordfish shells; wheels 8.0–9.5 (number sets crush) | — | n/p | — | host blaster | 2205 3000KV; limit to 75–80 % power on 4S | n/p | Thingiverse (page returned 403; from search snippets) | [Thingiverse](https://www.thingiverse.com/thing:2585080), [Narfduino note](https://blastersbyairzone.com/hardware/narfduino-brushless-micro/) |
| **Worker Swordfish** + full-auto kit | Commercial shell; brushed flywheel; kit adds a pusher motor + PWM | short darts | n/p | full auto | Talon | "do not use flywheel PWM with Kraken" | kit 186 g (shipping) | dual-stage cage on Cults3D, CC BY | [OOD kit](https://outofdarts.com/products/worker-full-auto-kit-for-dominator-and-swordfish), [Cults3D](https://cults3d.com/en/3d-model/game/worker-swordfish-a-dual-sized-dual-stage-flywheel-nerf-blaster) |
| **AIT + 40MAX Lightning** | Brushless flywheel + **brushless cam pusher** | short darts | presets 87 / 117 / 132 / 140 fps (SD 2–3) | 12 rps auto | Talon | own battery; "intelligent idling" | 582 g | closed | [OOD](https://outofdarts.com/products/ait-40max-lightning-brushless-flywheel-blaster) |
| AIT + 40MAX Lailaps | Brushless flywheel + solenoid (sold separately, 63 g, §5.3) | short darts; "no wide head, hard tip, or 38 mm+ darts" | 140 fps (SD 3) | 12 rps | Talon, has a dart sensor | — | 582 g | closed | [OOD](https://outofdarts.com/products/ait-40max-lailaps-brushless-flywheel-blaster) |
| Elite 2.0 Motoblitz mod kit | Brushed 130, **cage spacing sets velocity** | AF Pro short | 39 mm → 162, 40 → 155, 41 → 143, 42 → 111 fps | — | — | 2S | — | — | [OOD](https://outofdarts.com/products/elite-2-0-motoblitz-2s-mod-kit) |
| Narfduino (Brushless Compleat / Micro) | Controller boards, not blasters: 2 FlyShot SimonK ESCs, tach inputs, a half-bridge (≈ 20 A cont., 50 A burst) for a solenoid | — | — | — | — | 3–4S recommended, "may take up to 6s" (Compleat); Micro 2–6S, 10 g | 15 g (Compleat) | — | [Compleat](https://blastersbyairzone.com/hardware/narfduino-brushless-compleat/), [Micro](https://blastersbyairzone.com/product/narfduino-brushless-micro/) |
| Caliburn (Captain Slug) | Springer, pump action | — | — | — | — | — | — | public domain | already in the earlier study |

**Not found:** Captain Xavier's own designs, "Hy-Shot", "Cyclone" as a blaster (only the ZWQ Cyclone CNC barrel
insert, $44.99), any triple-stage brushless build, and T-Motor F-series motors in blasters.

### 1.2 Foam balls and robot launchers

| Design | Mechanism | Ammo | Velocity | Rate | Feed | Motors | Mass | Source |
|---|---|---|---|---|---|---|---|---|
| Nerf Rival Nemesis MXVII-10K | Flywheels | Rival | 101 fps (rechargeable), 94 fps (D cells), measured | ≈ 4/s | Gravity hopper (100) + conveyor belt up to the wheels | — | n/p | [Blaster Piece](https://blasterpiece.com/reviews/nerf-rival-nemesis-mxvii-10k-review/) |
| Nerf Rival Perses MXIX-5000 | Flywheels | Rival | n/p | 8/s | Hopper (50) + belt | — | n/p | [OOD mod guide](https://outofdarts.com/blogs/news/mod-guide-nerf-rival-perses) |
| Nerf Rival Prometheus MXVIII-20K | Flywheels | Rival | 100 fps | up to 8/s | Hopper (200), 9.6 V NiMH | — | n/p | [Hasbro](https://instructions.hasbro.com/en-us/instruction/Nerf-Rival-Prometheus-MXVIII-20K) |
| Gyrosoft Nemesis kit | Brushed flywheel upgrade | Rival | 122 fps (SD 6), 3S | — | hopper | — | 340 g kit | [OOD](https://outofdarts.com/products/nemesis-mod-kit) |
| Nerf Hyper Mach-100 | Motorised | Hyper (≈ 1/3 of a Rival round's size) | 110 fps | — | 100-round hopper; needs shaking | 6 × D | n/p | [Hasbro](https://consumercare.hasbro.com/en-us/product/nerf-hyper-mach-100-fully-motorized-blaster-and-80-nerf-hyper-rounds-110-fps-velocity-easy-reload-100-round-capacity/B103CD4E-5DF6-4424-8A8A-EEE0643340F4), [BlasterCentral](https://www.blastercentral.com/nerf-hyper-series/) |
| **RoboMaster 17 mm launcher** (2025 rules) | Twin friction wheels + motorised dial | 16.8 mm, 3.2 g TPU 90 A | cap 25 m/s (82 fps) | must reach ≥ 10 Hz at > 20 m/s | Hopper over a dial driven by an M2006 P36 | 2 × Snail 2305 (24 V) + C615; M2006 + C610 | n/p | [Rules V2.0.0](https://terra-1-g.djicdn.com/b2a076471c6c4b72b574a977334d3e05/RM2025/RoboMaster%202025%20University%20Championship%20Rules%20Manual%20V2.0.0%EF%BC%8820250703%EF%BC%89.pdf), [Building spec S57](https://terra-1-g.djicdn.com/b2a076471c6c4b72b574a977334d3e05/RM2025/RoboMaster%202025%20University%20Series%20Robot%20Building%20Specifications%20Manual%20V2.0.0%20(20250703).pdf) |
| DJI `standard_robot` shooter code | Dial steps π/10 rad per shot; jam = dial speed < 1.0 rad/s for 700 ms, then reverse 500 ms | — | — | — | — | — | — | [shoot.c](https://github.com/RoboMaster/Development-Board-C-Examples/blob/master/20.standard_robot/application/shoot.h) |
| **DJI RoboMaster S1 / EP** gel launcher | Mechanism unconfirmed (a forum user describes a "main spring", so possibly spring/piston) | 5.9–6.8 mm gel, 0.12–0.17 g | ≈ 26 m/s | 1–8/s, 10/s max | 430-bead container, sliding release plate, drain holes | — | robot 3.3 kg | [S1 support](https://www.dji.com/ca/support/product/robomaster-s1), [container](https://store.dji.com/product/robomaster-s1-gel-bead-container), [forum](https://forum.dji.com/thread-200225-1-1.html) |
| S1 elevation lock | **Refuses to fire above 10° pitch** | — | — | — | — | — | — | [S1 support](https://www.dji.com/ca/support/product/robomaster-s1) |
| Gelblaster Wingman (open) | A Surge XL / Starfire XL gearbox moved into a printed robot shell; a relay pulls the trigger | 7.5 mm gel | stock | stock | stock hopper | Dynamixel XM430 turret servo; Jetson Xavier NX | n/p | [GitHub](https://github.com/MAVProxyUser/Gelblaster_Wingman), CC BY-NC-SA 4.0 |
| FRC 254, 2026 game | Full-width drum shooter, net hopper with a pivoting belt floor | 5.91 in foam balls | — | — | 70+ balls | — | — | [Team 254](https://www.team254.com/frc/2026/) |

**What the robot launchers teach.** Every robot that fires many rounds (RoboMaster, the S1, FRC) uses round ammo, a
hopper and a motorised indexer, not magazines. Every one of them also has a jam detector or a way to clear the feed.

---

## 2. Ammo for a compact robot turret

### 2.1 The ammo

| Ammo | Mass | Size | Price | Notes | Source |
|---|---|---|---|---|---|
| Short dart (Worker HE) | 1.0 g | 13 × 36 mm | $16.99 / 200 | Fits Talon mags | [OOD](https://outofdarts.com/products/worker-he-standard-weight-short-darts-200-pack-1-0g) |
| Full-length dart (Worker) | 1.28 g | 13 × 72 mm | $17.99 / 200 | Fits stock Nerf | earlier study |
| Rival round, Hasbro | **1.83 g** measured average | 22.2–22.7 mm | — | 97 fps average over 100 shots in a review | [BlasterHub](https://blasterhub.com/2017/12/adventure-force-tactical-strike-rounds-review/) |
| Rival round, Worker Cheetah | 1.75 g | 22.7 mm, EVA foam | $14.99 / 100 | | [OOD](https://outofdarts.com/products/worker-cheetah-rounds-rival-compatible-ammo-100-pack) |
| Rival round, Dart Zone Powerstrike | 1.85 g | 22.8 mm, polyurethane foam | $29.99 / 200 | | [OOD](https://outofdarts.com/products/dart-zone-ballistix-ops-powerstrike-rounds-rival-compatible-ammo-200-pack) |
| Nerf Hyper round | ≈ 1.4 g (unverified retailer snippet) | ≈ 13–14 mm (unverified) | — | Dense and slightly sticky; jams | [BlasterCentral](https://www.blastercentral.com/nerf-hyper-series/) |
| Gel bead (Gellets) | ≈ 0.22 g (calc: 7.5 mm sphere at ≈ 1 g/cm³); a vendor lists 0.26 g | grows to ≈ 7.5 mm | $4.99 / 10k; $14.99 / 30k | > 98 % water, sodium polyacrylate | [Gel Blaster FAQ](https://gelblaster.com/pages/faq), [Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster), [Pyramyd](https://www.pyramydair.com/product/gelbee-gel-bbs-20-000-count-blue?p=2381) |
| DJI S1 gel bead | 0.12–0.17 g soaked | 5.9–6.8 mm | — | 500 beads per 1 L, soak ≈ 4 h, use within 24 h | [DJI](https://www.dji.com/ca/support/product/robomaster-s1) |
| RoboMaster 17 mm | 3.2 g | 16.8 mm TPU 90 A | — | Hard; for robots only | 2025 rules |

### 2.2 Energy at kid speeds (calc)

KE = ½mv². KED = KE / (π d²/4), taking the whole face of the projectile as the contact area as in the earlier study.
EN 71-1 allows 0.5 J for resilient projectiles and 0.08 J for rigid ones; ASTM F963 allows 2500 J/m² above 0.08 J.

| Ammo | 70 fps | 80 fps | 100 fps | 150 fps | Speed at ASTM 2500 J/m² | Speed at EN 71 0.5 J |
|---|---|---|---|---|---|---|
| Short dart 1.0 g, 13 mm | 0.23 J, 1710 J/m² | 0.30 J, 2240 | 0.46 J, 3500 | 1.05 J, 7870 | 85 fps | 104 fps |
| Rival 1.83 g, 22.7 mm | **0.42 J, 1030 J/m²** | 0.54 J, 1350 | 0.85 J, 2100 | 1.91 J, 4730 | 109 fps | **77 fps** |
| Gel 0.22 g, 7.5 mm | 0.05 J, 1130 J/m² | 0.07 J, 1480 | 0.10 J, 2310 | 0.23 J, 5210 | **104 fps** | 221 fps (0.08 J rigid limit: 88 fps) |
| RoboMaster 3.2 g, 16.8 mm | 0.73 J, 3280 J/m² | 0.95 J, 4290 | 1.49 J, 6700 | 3.35 J | 61 fps | 58 fps |

What the commercial gel products deliver, for comparison (calc with 0.22 g unless noted):

| Product | Speed | Energy |
|---|---|---|
| RoboMaster S1 (0.17 g) | 26 m/s | 0.057 J |
| Nerf Pro Gelfire Mythic | 80 fps (one EU retailer only) | 0.065 J |
| Gelfire Uproar / Twist Shot | 150 fps | 0.23 J, ≈ 5200 J/m² |
| Gel Blaster Surge (low) / Surge XL (max) | 170 / 250 fps | 0.30 / 0.64 J |

So a gel bead is low in energy but high in energy per area: a commercial gel blaster at 150–250 fps is 2–6 times
ASTM's 2500 J/m² (calc). To stay inside the toy limits, gel has to run at ≤ ≈ 100 fps, which is the Mythic and S1
class, not the Surge class.

### 2.3 Scores for Gyropup

5 is best. Scores are my judgement from the sourced facts in §§1–6; the reasons are in the cells.

| Criterion | Short darts | Full darts | Rival balls | Gel beads |
|---|---|---|---|---|
| Compact feed and launcher | **4**: Talon mag 240 × 36 × 19 mm for 15 | 2: mags twice as long | 3: 24 balls need ≈ 0.25 L of hopper (calc) plus a dial | **5**: hundreds of beads in a fist-sized hopper |
| Capacity per kg of feed | 4: Koda 23-round mag 115 g ≈ 5 g/dart | 3 | 3 as a hopper (≈ 44 g of balls for 24, plus ≈ 150 g printed hopper and dial, est); 1 in Rival mags (≈ 15 g/round) | **5** |
| Jamming | 3: orientation, crush, tip wear, wet darts | 3 | 3: hoppers bridge, so an agitator or dial is required; no orientation | 2: beads break in the mechanism and need disassembly (S1 review); bridging data n/p |
| Outdoors (wet grass, dirt) | **1**: wet darts swell and jam | 1 | 2 (est): closed-cell EVA balls should shed water better than darts, untested | **4** for the ammo itself; water and grit are bad for piston seals |
| Kid safety at close range | **4**: 0.30 J at 80 fps; under both toy limits | 3: over ASTM at 80 fps | **4** at ≤ 70 fps: highest energy but lowest energy per area | 2: under the limits only at ≤ 100 fps; small hard-ish sphere, 19-eye and 8-child injury series; all products 14+ |
| Pickup and clean-up | 2: small, hide in grass, pets eat them | 2 | **4**: big, bright, easy to collect; kids can "feed the robot" | 3: beads shatter or dry to powder, but whole misses stay in grass for hours: the toddler and pet ingestion hazard CPSC targets |
| Cost per 1000 shots | $85 (but reusable) | $90 | $150 (reusable) | **$0.50** (single use) |
| Dock reload | 2: needs a magazine swap or a dart-orienting loader | 1 | **5**: pour counted balls into the hopper | 2: pourable, but must be pre-soaked 2–4 h, kept wet and sealed, and drained |
| Regulation | 5 | 5 | 5 | **1**: the US water-bead toy rule, Australian firearm laws (§6.6) |
| **Total (of 45)** | 29 | 25 | **36** | 25 |

### 2.4 Foam or gel, head to head, for a highly compact head turret

Gel looks simpler, and in the ammo it is: no orientation, hundreds of rounds per hopper, no pickup, cheap. The rest of
the system is not simpler.

- **Mechanism.** Every proven gel blaster is a motor + gearbox + spring piston, "mostly identical to airsoft AEG"
  ([Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster)). No flywheel gel launcher was found; beads were long
  thought too fragile even for spring followers. A piston's velocity is set by the spring, not electronically, so the
  turret loses its RPM velocity guard and keeps only the chronograph lockout.
- **Logistics.** Gellets soak ≥ 2 h (4 h for Starfire), keep 2 weeks sealed or 3 months under water
  ([FAQ](https://gelblaster.com/pages/faq)); DJI says use within 24 h. An under-soaked bead makes the blaster "function
  poorly". The dock would need a soak tank, a drain screen and a metered wet feed, all with water next to the
  robot's charge contacts.
- **Outdoor mess.** Broken beads dry to "slush powder" ([Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster)), but
  whole misses lie hydrated in the grass. The water-bead rule exists because children swallow them.
- **Kids.** Gel Blaster and Nerf Pro Gelfire are all labelled 14+; Hasbro requires eyewear "for players and people
  within range". An *Ophthalmology* series (Lin et al., 2023) covers 19 injured eyes and recommends paintball-grade
  eye protection ([AAO EyeNet](https://aao.org/eyenet/article/risk-of-ocular-trauma-from-gel-pellets)); Queensland
  Children's Hospital saw 8 children aged 4–14 in six months ([Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster)).
- **Regulation.** The US water-bead toy rule (16 CFR 1250, effective 12 March 2026) puts "water bead toy guns designed
  to shoot water bead projectiles" in scope when they are designed or marketed for children under 14, and requires
  expanded beads to pass a 5.0 mm funnel gauge. Guns marketed 14+ for paintball- or airsoft-style play are out of
  scope ([Federal Register 2025-22643](https://public-inspection.federalregister.gov/2025-22643.pdf),
  [CPSC guidance](https://www.cpsc.gov/Business--Manufacturing/Business-Education/Business-Guidance/Water-Bead-Toys-Business-Guidance)).
  Standard 7.5 mm beads are made to be bigger than 5 mm; whether one squeezes through the gauge in the test was not
  checked. A Tritium game for children under 14 should assume it is in scope. In Australia, gel blasters are firearms
  or regulated imitations in NSW, SA and WA ([Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster),
  [Mondaq](https://www.mondaq.com/australia/crime/1168846/gel-blaster-laws-in-nsw)).
- **Power.** An AEG motor on 7.4–11.1 V while cycling draws far more than a dial motor (no published current found;
  est 100+ W), and needs its own high-current stage.

**Verdict: foam, not gel, for Gyropup's kids.** Gel makes sense "because of simplicity" only for the ammo, and only for
14+ players in sealed goggles. Keep a gel cartridge as a possible later module for teen or adult outdoor events
(§7), capped at ≤ 100 fps with a chronograph lockout, and never fielded with younger children.

### 2.5 Indoors and outdoors

- **Indoors:** Rival balls at ≤ 70 fps. They are big, visible and roll out from under furniture.
- **Outdoors on dry grass:** the same balls. They are easier to find in grass than 36 mm darts (est).
- **Outdoors on wet grass:** no foam ammo is reliable (S22 already bans play in rain or on wet grass). Wet-ball
  feeding has not been tested anywhere I found, so test closed-cell EVA balls on damp grass before relaxing S22.
- **One ammo for both** is the recommendation. The cartridge boundary (§7) keeps short darts and gel possible without
  redesigning the head.

---

## 3. Feeding

### 3.1 Capacity against size

| Feed | Capacity | Size | Mass | Price | Source |
|---|---|---|---|---|---|
| Worker 15-round straight Talon mag | 15 short darts | 240 × 36 × 19 mm | 105 g | $9.99 | earlier study |
| Worker 18-round curved Talon mag | 18 | n/p | 105 g (description); 140 g shipping | $11.99 | [OOD](https://outofdarts.com/products/worker-18-round-curved-standard-talon-short-dart-magazine) |
| OOD Koda 23-round Talon mag | 23 | 315 mm long | 115 g | $19.99 | earlier study |
| Worker 22-round mag (T19's) | 22 | n/p | n/p | — | T19 posts |
| **Kptn A Super Drum** (printed, Talon) | up to 70 short darts, 8 constant-force springs | n/p | hardware 65 g; total n/p | $25.99 hardware + printed parts ($60 from IFB) | [OOD](https://outofdarts.com/products/kptn-a-super-drum-magazine-hardware-kit), [IFB](https://ifb.sg/products/superdrum-70-3d-printed-parts) |
| Nerf 18 / 25 / 35-dart drums | full-length | n/p | n/p | — | not found |
| Nerf Vulcan belt | 25 full-length | n/p | n/p | used, $15.99–25 | eBay listings (agent search) |
| Worker 15-round Rival mag | 15 balls | n/p | 227 g shipping | $9.99 | [OOD](https://outofdarts.com/products/worker-15-round-rival-magazine-apollo-juno) |
| Hasbro 12-round Rival mag | 12 | 44 × 159 × 349 mm, 200 g (in package) | — | $11.97 used | [OOD](https://outofdarts.com/products/used-nerf-rival-magazines) |
| Nerf Rival Nemesis hopper | 100 balls | — | — | — | §1.2 |
| OOD Infinite Pack | ≈ 430 balls in a 1-gallon (3.8 L) container ≈ 110 balls/L | backpack | 1250 g | $259.99 | earlier study |
| **Head hopper for 24–30 Rival balls** | 24–30 | ≈ 0.25–0.3 L, e.g. Ø80 × 60 mm (calc: 24 × 6.1 cm³ at ≈ 0.6 packing) | ≈ 150 g printed with dial (est) | filament | calc / est |
| DJI S1 gel container | ≈ 430 beads | 152 × 55 × 30 mm | n/p | $29 | [DJI](https://store.dji.com/product/robomaster-s1-gel-bead-container) |
| Nerf Pro Gelfire Mythic | 800-bead gravity hopper | blaster 355 × 266 × 66 mm | 790 g whole blaster | ≈ $18–54 street | [Fleet Farm](https://www.fleetfarm.com/detail/nerf-gelfire-mythic-blaster/0000101804219), [Best Buy CA](https://www.bestbuy.ca/en-ca/product/17664937) |
| Gel Blaster Surge XL | > 1000-bead hopper | — | n/p | $89.96 | [KK Hardware](https://kkhardware.com/p/surge-xl-water-blaster-with-gellets-shooting-modes-850040523263-123975) |

### 3.2 How robots feed

- **RoboMaster:** a hopper above a dial (the "trigger" motor, an M2006 P36), stepping a fixed angle per shot (π/10 rad
  in DJI's example code). The friction wheels must be at speed before the dial may turn. Jams are detected by dial
  stall and cleared by reversing (§1.2).
- **S1:** a sealed 430-bead container with a sliding plate that opens when it is fitted, and drain holes to let water
  out after loading.
- **Nerf hopper blasters:** a conveyor belt from the hopper to the wheels. Hasbro's own patent (US11346624B2) says soft,
  tacky spheres "tend to aggregate or bind in the hopper", especially at the feed-tunnel entrance, and adds gear-like
  agitating rollers and a compression roller ([Google Patents](https://patents.google.com/patent/US11346624B2/en)).
- **Infinite Pack:** a gear-motor agitator plus a brushless blower that pressurises the hose.

**Design rules for Gyropup's hopper:**

1. Put the dial at the bottom of the hopper, with pockets one ball wide, and stir the hopper with the dial (spokes
   or bumps on top), as the Hasbro patent does.
2. The tilt range is only about −25°…0°, so a hopper on the tilting cradle still feeds by gravity.
3. The hopper cannot be shaken, so a stall-reverse cycle is the only way to break a bridge.
4. Unpowered, the dial must block the path, so no ball can roll into the wheels after an e-stop.

---

## 4. Jamming

| Failure | Cause | Fix / design rule | Source |
|---|---|---|---|
| Firing into slow wheels | Pusher or dial moves before the wheels are at speed, or during coast-down | Gate every shot on measured wheel speed (several consecutive in-range tach readings); test at 0 rpm and during coast-down | [S-Core](http://torukmakto4.blogspot.com/2020/02/), [T19](http://torukmakto4.blogspot.com/2019/) |
| Pusher not home | Weak return spring; pusher sticks on darts | Replace the spring; home on a switch; a stepper that counts steps homes every cycle | [QT19](https://github.com/GrubbyLittleRaccoon/QT19-T19E1-derivative), T19 bolt drive |
| Solenoid misfires as the battery sags | Fixed pulse timing; "trouble firing darts around 11.15 V" | Make pulse length depend on voltage; Gyropup's regulated rail removes the sag | QT19 |
| Velocity spread / dart stalls | Wrong crush; worn or wide-head tips; 38 mm+ darts in micro-flywheelers | Set crush per ammo (Motoblitz: 39 mm → 162 fps, 42 mm → 111 fps); approved ammo only | [Motoblitz](https://outofdarts.com/products/elite-2-0-motoblitz-2s-mod-kit), [Lailaps](https://outofdarts.com/products/ait-40max-lailaps-brushless-flywheel-blaster) |
| Double feed, feed-ramp jam | Overfilled mag, weak spring, loose feed lips, burrs | Do not overfill; tight feed lips; deburr and radius the breech; diagnose by pushing up on the mag while firing | [monkeemods](https://monkeemods.com/blog/why-nerf-blasters-jam), [torukmakto4](https://torukmakto4.blogspot.com/2014/06/), Kptn A drum |
| Old or wet darts | Humidity swells foam; worn or tacky tips | Fresh, stiff darts; no play on wet grass | monkeemods, Kptn A ("prefers fresher… stiffer") |
| Ball hopper bridging | Soft tacky balls bind at the tunnel entrance; feed stops when the blaster is still | Agitator or dial that stirs; stall detection and reverse | Hasbro patent; Nemesis and Perses reviews |
| Two balls in the conveyor | Belt pockets too large | Pocket exactly one ball; RoboMaster-style dial | [Nemesis review](https://blasterpiece.com/reviews/nerf-rival-nemesis-mxvii-10k-review/) |
| Rate drops as hopper empties | Gaps on the belt | Gravity head over the dial; a dial pocket per shot | [Perses review](https://blasterpiece.com/reviews/nerf-rival-perses/) |
| Broken gel beads | Fragile beads in a piston or feed | Partial disassembly to clear; hard beads for magazines; correct soak time | [Tom's Hardware](https://www.tomshardware.com/reviews/dji-robomaster-s1-robot-stem-toy,6190.html), [Pyramyd](https://www.pyramydair.com/product/cosmoxtoys-70k-white-gel-balls-normal-7-5-mm?p=2479) |
| Feed motor stall | Any of the above | Stall = dial speed < 1 rad/s for 700 ms, then reverse 500 ms (DJI) | [shoot.c](https://github.com/RoboMaster/Development-Board-C-Examples/blob/master/20.standard_robot/application/shoot.h) |
| Stray round in a stopped launcher | A ball or dart left between the wheels | On arming, spin the wheels slowly and cycle the feeder home so a stray round is "barfed out at about 36 fps" | [S-Core](http://torukmakto4.blogspot.com/2020/02/) |

**Rules for Gyropup's cartridge:**

1. One round per feed step, with the pocket or stroke counted.
2. Fire only when both wheels are in range, from tach.
3. Stall-reverse on the feeder.
4. A chronograph on every shot, which also catches "no round left" and "slow round" as faults.
5. Approved ammo only, with the cartridge geometry rejecting other ammo.
6. At the dock, clear any stray round at low speed before arming.
7. Log every fault with its counts.

---

## 5. Motors and actuators

**Gyropup's rails:** the bus is 45–58 V. A 24 V rail (Mean Well DDR-120C-24, 120 W) is spoken for by the J501. A 12 V
rail (DDR-30L-12, 30 W) feeds the lidar and headlights. Hobby blaster parts are built for 3S–4S (11–17 V). FPV ESCs
reach 6S (25.2 V), and RoboMaster parts run on 24 V. So the payload should get its **own 24 V** (§8.5).

### 5.1 Flywheel motors

| Motor | Type | Voltage | Speed | Current | Mass | Price | Fit at 24 V | Source |
|---|---|---|---|---|---|---|---|---|
| **DJI Snail 2305** | Brushless outrunner, Ø29 × 28.2 mm | 24 V rated | 875 rpm/V → ≈ 21,000 rpm at 24 V (calc) | 0.4 A no-load (earlier study) | **27.8 g** | $29 (DJI) | **Native** | [RoboMaster](https://www.robomaster.com/en-US/products/components/detail/2397) |
| Kelly Industries Plus Motor 2207 | Brushless, blaster-specific; flywheel bolts on 4 × M3; STEP | 3S/4S | 3200 KV | needs ≥ 30 A ESC on 3S, ≥ 35 A on 4S | 51 g (shipping) | $21.99 | Too fast at 24 V (76,800 rpm no-load, calc) | [Kelly](https://kellyindustries.us/products/plus-motor-brushless) |
| Emax ECO II 2207 | Brushless FPV | 3–6S | 1700 / 1900 / 2400 KV | — | n/p | $12.99 | 1700 KV → 40,800 rpm at 24 V (calc) | [Emax](https://shop.emax-usa.com/products/eco-ii-2207-brushless-motor-1700kv-1900kv-2400kv) |
| Turnigy V-Spec 2205 2350KV | Brushless (Hy-Con) | 3S | 2350 KV | ≥ 20 A ESC | n/p | — | — | Hy-Con README |
| Supernova 1507.5 4200KV | Brushless (Momentum) | 4S | 4200 KV | — | n/p | $26.99 | earlier study | earlier study |
| OOD Loki 130 | Brushed | 3S | 62,000 rpm idle | 0.90 A idle, 21 A stall | 32 g (shipping) | $9.49 | Needs 12 V | [OOD](https://outofdarts.com/products/ood-loki-130-3s-neodymium-high-speed-high-rpm-motor-for-nerf-blasters) |
| OOD Valkyrie 130 | Brushed | 3S | 35,000 rpm | 14 A stall | 21 g (shipping) | $3.49 | Needs 12 V | [OOD](https://outofdarts.com/products/ood-valkyrie-130-3s-motor-for-nerf-blasters) |
| Worker 132 Phoenix | Brushed | 3S | "nearly 70000 RPM" | 45 A stall | 90 g pair (shipping) | $14.97 pair | Needs 12 V | [OOD](https://outofdarts.com/products/worker-high-speed-132-phoenix-motor-pair) |
| MTB Neo-Hellcat 130 | Brushed | 3S | ≈ 35,000 rpm (unverified: identical to Kraken figures) | 26 A stall (unverified) | — | — | — | [suild](https://suild.com/tools/motor-spec-finder) |

**How fast the wheels need to go.** On a Hy-Con cage, 35,000 eRPM (≈ 5,000 rpm on a 14-pole motor) gives
**≈ 36 fps** ([torukmakto4](https://torukmakto4.blogspot.com/2020/02/simonk-flyshot-digital-speed-command.html)).
Scaling linearly, 70–80 fps needs ≈ 10–11k rpm (est), a quarter to a half of any motor here.

For balls, the wheel surface speed must be at least the exit speed. 21 m/s from 40 mm wheels needs ≥ 10,000 rpm
(calc), about half the Snail's no-load speed at 24 V.

**Brushed vs brushless for a robot.** Brushless is the choice: RPM telemetry, closed-loop speed, no brush dust, and
no 26–45 A stall currents on a shared rail.

### 5.2 ESCs

| ESC | Rating | Telemetry / control | Mass | Price | Source |
|---|---|---|---|---|---|
| **Repeat Robotics AM32 35 A** | 35 A continuous, **3–6S**, 25 × 13 × 5 mm | AM32 firmware (servo PWM, DShot, bidirectional DShot, KISS telemetry per the AM32 project); RPM telemetry on this board inferred, verify | ≈ 5 g | $24.99 | [Palm Beach Bots](https://palmbeachbots.com/products/repeat-robotics-am32-brushless-drive-esc-bi-directional), [AM32](https://github.com/am32-firmware/AM32) |
| DJI C615 | 15 A continuous, 26 V max (earlier study) | PWM | 9.7 g | $39 | [RoboMaster](https://www.robomaster.com/en-US/products/components/detail/2396) |
| DJI C610 (for M2006) | 10 A continuous | **CAN** | 17 g | $41 (page price; may be motor or ESC) | [RoboMaster](https://robomaster.com/en-US/products/components/detail/1277) |
| FlyShot (SimonK fork) | — | Digital speed command with a closed-loop governor; overspeed limit at 312,500 eRPM | — | firmware | [torukmakto4](https://torukmakto4.blogspot.com/2020/02/simonk-flyshot-digital-speed-command.html) |
| Narfduino Brushless Compleat | 2 ESCs + solenoid half-bridge, 3–4S (up to 6S) | FlyShot, tach inputs | 15 g | ≈ $75 (likely AUD), out of stock | [Blasters by Airzone](https://blastersbyairzone.com/product/narfduino-brushless-compleat/) |

### 5.3 Pushers and feeders

| Actuator | Specs | Rate | Mass | Price | Source |
|---|---|---|---|---|---|
| **AIT + 40MAX Lailaps solenoid** | 22 × 27 mm body, 8 × 43.6 mm core, 12.5 mm stroke, ≈ 10 N, up to 12 A, 11–17 V, 10 ms pulse response; pulsed only | 12 rps (in the Lailaps) | **63 g** | $19.99 | [OOD](https://outofdarts.com/products/ait-40max-lailaps-solenoid-pusher) |
| Eli Wu Neutron solenoid | 26 mm stroke, 20–35 N | 10 rps 3S, 18 rps 4S | 209 g | $29.99 | earlier study |
| FTW Hyperdrive solenoid | — | 10 dps on 3S; 18 on 4S with a double spring | n/p | €59.95 | [Blaster-Time](https://www.blaster-time.eu/?p=21738) (search snippet) |
| NEMA17 stepper bolt drive (T19) | Self-homing scotch yoke, ≈ 1–2 A/phase | 8.3–13.8 rps | ≈ 300 g (est) | — | T19 posts |
| Brushless cam pusher | AIT Lightning | 12 rps | — | — | [OOD](https://outofdarts.com/products/ait-40max-lightning-brushless-flywheel-blaster) |
| **DJI M2006 P36 + C610** (ball dial) | Ø24.4 × 64.8 mm, 36:1, 1 N·m continuous, 416 rpm at 1 N·m, 500 rpm no-load, CAN | an 8-pocket dial at 75 rpm gives 10 balls/s (calc) | **90 g + 17 g** | $41 + $41 | [RoboMaster](https://robomaster.com/en-US/products/components/detail/1277) |
| Juno gear-motor pusher | 300 / 600 / 1000 rpm → 4.5 / 9 / 15 balls/s | — | — | — | [OOD](https://outofdarts.com/products/juno-rival-blaster-3d-parts-hardware-kit) |
| Feetech STS3215 (as a dial) | 45 rpm no-load at 12 V | 8 pockets → 6 balls/s max (calc); enough for 3/s kids' mode | 89 g | $21.99 | earlier study |

### 5.4 Gel gearboxes

| Part | Specs | Mass | Price | Source |
|---|---|---|---|---|
| CYMA V2 gearbox (airsoft, shell + internals, no motor) | Used in M4-pattern gel blasters with a 460 long-shaft motor at 7.4 V | n/p | $55.95–75.00 | [Evike](https://www.evike.com/products/100665/) (403 on re-check), [Newegg](https://www.newegg.com/p/03O-09W7-00077) |
| CYMA high-torque long-shaft motor | — | n/p | £24.99 | [Patrol Base](https://www.patrolbase.co.uk/cyma-high-torque-neodymium-magnet-motor-long-shaft) |
| Budget "clamshell" gearboxes | Nylon gears; wear faster at 11.1 V | n/p | — | [r/GelBlaster](https://reddit.birdcat.cafe/r/GelBlaster/comments/1jro11t/how_to_mod_an_slr/mlh2j5i/) |
| Nerf Gelfire Mythic (whole) | 7.4 V 500 mAh LiPo, 10 rps, select fire | 790 g | street ≈ $18–54 | §3.1 |
| Gel Blaster Surge 2.0 | 7.4 V Li-ion 500 mAh, 10 rps | ≈ 920 g (original Surge) | — | [varle.lt](https://www.varle.lt/radio-valdomi-zaislai/gel-blaster-surge-20--52249758.html), [Galaxus](https://galaxus.de/en/s5/product/gel-blaster-surge-toy-weapons-36841973) |

No mass or current was published for any gel gearbox or motor.

---

## 6. Safety

This adds to [turret-and-safety.md §4 and §7](turret-and-safety.md), whose limits (S1–S23) still apply.

### 6.1 Speed and energy caps

| Context | Cap | Source |
|---|---|---|
| Stock Nerf Elite | ≈ 65–73 fps measured; Hasbro publishes none | earlier study |
| Nerf Rival (14+) | 90–100 fps | Hasbro, §1.2 |
| Nerf Hyper | 110 fps | Hasbro |
| Nerf Pro Gelfire Mythic (14+) | 80 fps (one retailer) | §2.2 |
| UK public land (forum claim) | 1 J: "130 FPS for Elite darts, about 100 FPS for RIVAL" | [BritNerf](https://www.tapatalk.com/groups/britnerf/viewtopic.php?p=55753) |
| UK high-fps Nerf event | Minimum engagement distance ≈ 40 ft for blasters over 200 fps | same |
| GameSchoolCon, all ages | 150 fps, eye protection, no point-blank shots above the neck | earlier study |
| Gel field, QLD (Mango Hill) | < 300 fps: no point-blank mag dumps; 300–330: 1–2 shots inside 5 m; > 330: none inside 10 m | [kidsbook](https://kidsbook.com.au/p/mangohillskirmish) |
| Gel field (Fox "Gel Wars") | Rifles ≤ 1.5 J; DMR 1.5–2 J with a 75 ft minimum distance; ANSI Z87 full-seal goggles; under-18s add a hard lower face mask | [Fox Airsoft](https://foxairsoft.com/products/gel-wars) |
| Gelsoft venue (Asylum, AU) | No fps limits; minimum age 8; "restraint when engaging younger participants" | [Asylum rules](https://cdn.shopify.com/s/files/1/0085/5090/8001/files/Asylum_Safety_Rules.pdf) |
| RoboMaster 17 mm (robots only, no people) | 25 m/s | 2025 rules |

**Gyropup caps (one per cartridge, held in the cartridge and in the head MCU):**

| Cartridge | Default | Hard cap | KE / KED at cap (calc) |
|---|---|---|---|
| Rival balls | 65 fps | **70 fps** | 0.42 J / 1030 J/m² (1.83 g) |
| Short darts | 70 fps | 80 fps (unchanged, S1) | 0.30 J / 2240 J/m² |
| Gel (14+ events only) | 80 fps | 100 fps | 0.10 J / 2310 J/m² |

**Minimum distance.** S7's 2 m stays. No published minimum distance exists for low-fps foam play; the gel tables above
start at 5–10 m only above 300 fps.

### 6.2 Eye protection

- **Foam:** Hasbro recommends eyewear for Rival players "and people within range" (earlier study). GameSchoolCon
  requires eye protection for every round.
- **Gel:** Hasbro *requires* eyewear for Gelfire players and anyone within range
  ([Hasbro](https://consumercare.hasbro.com/en-gb/product/nerf-pro-gelfire-legion-blaster-300-hydrated-gelfire-rounds-130-round-hopper-spring-action-eyewear/4E5E1A25-2430-4A92-9FDA-654CF6272DE4)).
  Fields ask for ANSI Z87 full-seal goggles (Fox). The ophthalmologists ask for paintball-grade protection for
  bystanders too (AAO).
- Tritium's kids already wear safety glasses. For foam that matches the rules above. For gel, safety glasses alone fall
  short of every gel-specific rule found.

### 6.3 Making the turret physically unable to aim high

The body leans, so a body-frame limit alone is not enough (S5). Layers, from mechanical to software:

1. **A hard tilt stop** on the yoke at 0° body frame, and a cradle that cannot reach above it even with the servo off.
2. **A body-lean rule.** The balance controller already keeps forward lean small. If the body pitches nose-up beyond
   the margin, the arming line opens (next item). The S1 does this at 10° ([DJI](https://www.dji.com/ca/support/product/robomaster-s1)).
3. **A hardware inclination interlock in the cartridge.** A tilt switch or a small accelerometer with a comparator,
   wired into the arming loop, cuts feed power whenever the barrel is above horizontal in the world. It does not depend
   on the Jetson or the head MCU (concept; switch hysteresis must be measured, est a few degrees).
4. **World-frame gating** from the head IMU, with the ballistic head-zone prediction of S5.

### 6.4 Safe-off states

| State | What is powered | Mechanism |
|---|---|---|
| **SAFE** (default, e-stop, dead-man released, link lost) | Head MCU, IMU, LEDs only. The arming contactor is open, so ESCs and feeder have no power | Muzzle parks at −20°. The flywheels coast down. The dial blocks the path, so no ball can reach the wheels |
| **ARMED** | Flywheels idling, feeder holding | Amber LED, buzzer, laser off |
| **AIMING** | As ARMED, plus the laser | Laser on ≥ 0.35 s before the first shot (D26) |
| **FIRING** | Dial stepping | Every shot timed by the chronograph; any shot over the cap latches SAFE until a human resets it |
| **DOCKED / RELOADING** | Feeder only, at low speed | Flywheels off; the dock pours balls in; stray-round clear at low wheel speed before the next ARMED |

### 6.5 The aiming laser

| Class | Visible CW limit | Source |
|---|---|---|
| Class 1 | ≈ 0.22 mW at 514 nm, 0.4 mW at 550–700 nm (ANSI Z136.1 AEL table; 520–532 nm falls between) | [Illinois DRS](https://www.drs.illinois.edu/Page/SAfetyLibrary/LaserClassification) |
| Class 1M | 0.39 mW for a point source | [Rockwell Laser Industries](https://www.rli.com/resources/articles/classification.aspx) |
| Class 2 | 1 mW; relies on the blink reflex (≤ 0.25 s) | [Wikipedia](https://en.wikipedia.org/wiki/Laser_safety) |
| Class 3R | 5 mW | same |

- The FDA advises that laser pointers "are not toys and should not be used by minors except under the direct
  supervision of an adult" (via [Wikipedia](https://en.wikipedia.org/wiki/Laser_safety)). Gyropup's laser is part of
  a supervised game, and it never points above horizontal.
- **Recommendation:** buy a module with a stated class from a maker that certifies it. One example is the Picotronic
  520 nm, 1 mW, Class 2, 12–24 V, Ø12 × 40 mm module (16 g, €319.90;
  [Picotronic](https://shop.picotronic.de/en/p/70146981)). Cheap modules sold as "< 1 mW" have unverified output, so
  measure any of them with a power meter.
- Class 1 (≤ ≈ 0.2 mW, est at 520 nm) is safer but dimmer. Its visibility in daylight was not tested.
- The doc's current text ("Class 1 or low-power Class 2, ≤ 1 mW") is right.

### 6.6 Legal

- **US federal:** imitation firearms need a blaze-orange tip (15 U.S.C. §5001, via
  [Wikipedia](https://en.wikipedia.org/wiki/Gel_blaster)). The orange muzzle in S11 covers this. The water-bead rule
  is covered in §2.4.
- **US states:** New York and California restrict imitation firearms (same source). Check before any event there.
- **Australia:** gel blasters need a licence in NSW and SA, are banned in WA, and in QLD must be locked away and
  concealed in public ([QLD Police](https://www.police.qld.gov.au/node/1341)). Foam blasters are not affected in
  anything found.

---

## 7. One ammo, or a launcher cartridge per ammo

### 7.1 What is shared and what differs

| Part | Shared by all cartridges? | Notes |
|---|---|---|
| Head plate, pan bearing, pan motor (DM-J4310-2EC) | **Yes** | |
| Tilt yoke, tilt servo (STS3215), hard tilt stop | **Yes** | The cradle takes the cartridge |
| 24 V payload power, arming contactor, fuse | **Yes** | Each cartridge draws only through the arming line |
| Head MCU, IMU, CAN, e-stop and dead-man inputs, LEDs, buzzer | **Yes** | |
| Aiming laser | **Yes** | Mounted on the cradle, not the cartridge, so its boresight is kept |
| Chronograph electronics | **Yes** | The two gates sit in each cartridge's muzzle (bore differs), on a common connector |
| Launcher | **No** | Balls and darts both use a brushless flywheel pair and could share motors and ESCs, but the wheel diameter, spacing and crush differ. Gel needs an AEG gearbox |
| Barrel | No | 23–24 mm smooth bore for balls; 13 mm for darts; ≈ 8 mm for gel |
| Feed | No | Hopper + dial (balls, gel) or magazine + solenoid (darts) |
| Velocity limiter | No | Per-ammo wheel geometry; for gel, the spring |
| Power stage | Mostly | Flywheel cartridges take 24 V straight to their ESCs. A gel cartridge needs its own 24 → 7.4–11 V high-current stage |

### 7.2 The cartridge boundary

- **Mechanical:** two dowels and one captive thumbscrew, or a cam latch, on the tilt cradle. The cartridge's centre of
  mass sits on the tilt axis.
- **Electrical:** one blind-mate connector carrying:
  - 24 V and GND, 10 A;
  - CAN-H and CAN-L;
  - the arming loop, so it opens if the cartridge is pulled out;
  - the chronograph gate lines;
  - **two hard-wired ammo-ID pins.**
- **Why the ammo ID is in hardware.** The ID picks the velocity cap. It is a resistor or pin code read by the head MCU,
  not a software setting, so a cartridge cannot be fired under another ammo's limit. Each cartridge's wheel geometry
  also caps its own velocity mechanically (§8.3).
- **Cost:** ≈ 25 g on the head side and ≈ 15 g on the cartridge (est), plus one connector.

**Verdict: practical, and worth doing.** The shared part is about two-thirds of the head's mass. Ball and dart
cartridges fit the budget with room to spare (§8.6). A gel cartridge also fits on paper (≈ 0.5–0.6 kg, est), but it
needs its own power stage, a water-tight hopper and its own velocity limiter, and it would only be fielded for 14+
players (§2.4). Build the boundary now. Ship the ball cartridge first, keep the dart cartridge as the
second, and treat gel as a later experiment.

---

## 8. Recommended concept for Gyropup's head turret

### 8.1 The concept

| Item | Choice | Basis |
|---|---|---|
| Ammo | Rival-size foam balls, 22.7 mm, 1.75–1.85 g (Worker Cheetah or Dart Zone Powerstrike) | §2 |
| Launcher | Twin counter-rotating flywheels in the horizontal plane, ≈ 40 mm printed wheels with TPU tyres (est), 2 × Snail 2305 at 24 V | RoboMaster's proven 17 mm pair; 24 V native |
| ESCs | 2 × Repeat AM32 35 A (6S, ≈ 5 g, with RPM telemetry to verify) or 2 × C615 | §5.2 |
| Feed | Gravity hopper for 24–30 balls (≈ 0.3 L) over an 8-pocket dial on an M2006 P36 + C610 (CAN) | §3.2 |
| Velocity guards | (1) RPM closed loop; (2) wheel diameter × motor KV × regulated 24 V gives a hard ceiling; (3) two-gate chronograph, lockout on any shot over cap | S2 adapted to balls |
| Pan / tilt | DM-J4310-2EC pan (24 V, CAN), STS3215 tilt with a hard 0° stop; pan limited to ±170° with a cable loop, no slip ring | earlier study, §6.3 |
| Control | Head MCU (STM32/RP2040 class) on CAN: wheel RPM loop, dial steps, chronograph, interlocks. The Jetson asks; the MCU may refuse | earlier study |

### 8.2 Numbers

| Quantity | Value | Basis |
|---|---|---|
| Muzzle velocity | 65 fps default, **70 fps hard cap** (21.3 m/s) | §6.1 |
| Energy per ball | ≤ 0.42 J, ≤ 1030 J/m² | calc |
| Recoil per shot | 1.83 g × 21.3 m/s = **0.039 N·s** | calc; within the 0.05 N·s budget |
| Range from a 0.5 m muzzle, level | ≤ 6.8 m before touching the ground (no drag, upper bound) | calc |
| Rate of fire | 10 balls/s capable (dial at 75 rpm); **3/s, bursts ≤ 5 in kids' mode** | calc; S4 |
| Capacity | **24** in the head (hopper sized for 30) | user target |
| Envelope | ≈ 170 × 110 × 150 mm (L × W × H) for the cartridge; ≈ 130 mm swept pan radius (est) | est |
| Mass | ≈ 1.16 kg (§8.6) | mostly est |
| Power at 24 V | SAFE 3–5 W; ARMED 15–25 W; game average ≤ 40 W; peaks ≈ 150 W for < 0.5 s, mostly pan slews (est) | §8.5 |
| Reload time at the dock | ≈ 5–10 s for 24 balls (est, gravity) | §8.4 |

### 8.3 Velocity ceiling for balls

- **Why darts and balls differ.** Darts are limited by cage crush. A ball launcher can be limited by the regulated
  rail instead.
- **The ceiling.** The Snail's no-load speed at 24 V is ≈ 21,000 rpm (calc). The wheels' surface speed at that rpm is
  the most the ball can ever get.
  - With 40 mm wheels that is 44 m/s, so the motor-speed ceiling alone does not hold the cap.
  - Either fit **≈ 20–25 mm wheels**, which give 22–27 m/s at full speed, or take the ceiling from a lower-KV motor.
- **Bench check.** Measure exit speed against wheel speed. Then show that at 100 % throttle the exit speed stays
  ≤ 70 fps, as S2(b) requires for darts.
- **What it costs.** The ratio of exit speed to wheel speed is not published, so the wheel size must be settled on
  the bench. Until then the cap rests on the RPM loop and the chronograph.

### 8.4 Dock reload

- **The dock.** It gains a short mast with a ball silo (≈ 100–200 balls), a servo gate and a break-beam counter at
  the spout.
- **Docking.** Gyropup sits down (D18), pans to a stored "reload" angle and tilts to its load pose. A spring flap on
  the hopper is pushed open by the spout.
- **Filling.** The dock dispenses the number of balls the robot reports as fired, which it knows from the chronograph
  log. A hopper-full beam in the cartridge stops the fill.
- **Before the next round.** The flywheels spin slowly and the dial cycles once to clear any stray ball, before
  re-arming is allowed.
- **Game idea.** Kids collect balls and drop them into the silo: "feed the robot". That doubles as the count-out and
  count-in in S20.
- **Dart cartridge instead.** A person swaps the magazine at the dock, which is the current doc's plan. A robotic
  magazine changer is a project of its own.

### 8.5 Power: where the payload's 24 V comes from

| Rail | Converter | Already feeds | Spare for the payload |
|---|---|---|---|
| 12 V | Mean Well DDR-30L-12, 30 W | Lidar and 2 × 20 W headlights (D24 assumption) | None: already over budget on paper |
| 24 V | Mean Well DDR-120C-24, 120 W (180 W for 3 s) | J501 / AGX Orin | Not enough to promise 40 W plus peaks |
| Bus | 45–58 V FLEXVOLT (D25) | everything | Yes |

**Proposal:** a fused tap on the bus (5 A, est) through the turret arming contactor, feeding a dedicated 24 V
converter for the payload, mounted in the body.

- **Converter:** a second DDR-120C-24 ($69.20, 33.6–67.2 V in, in `power_electronics.json`), or a DDR-60L-24
  (60 W, 18–75 V in, ≈ $33; [onlinecomponents](https://onlinecomponents.com/en/mean-well/ddr60l24-50161046.html)) if
  bench tests show the peaks fit.
- **Why regulated 24 V:** it gives the flywheels a fixed voltage, which makes the hard ceiling in §8.3 possible.
- **12 V parts:** the STS3215 (and a dart cartridge's solenoid) get a small 24 → 12 V buck in the head (est 10 g).
- **Flywheel spin-up is small at these speeds.** Est 3 × 10⁻⁶ kg·m² per wheel and rotor, at 10,000 rpm, stores ≈ 1.6 J
  per wheel (calc on est inertia), so spin-up in 0.2 s needs only ≈ 30–60 W with losses (est).

### 8.6 Mass budget

**Shared head** (est unless noted):

| Part | Mass |
|---|---|
| DM-J4310-2EC | 306 g (catalog) |
| Pan bearing | 60 g |
| Cable loop | 30 g |
| STS3215 | 89 g (catalog) |
| Yoke and cradle | 130 g |
| MCU + IMU | 15 g |
| Laser | 16 g (Picotronic) |
| LEDs and buzzer | 15 g |
| Wiring | 50 g |
| 12 V buck | 10 g |
| Latch and connector, head half | 25 g |
| **Subtotal** | **≈ 746 g** |

**Ball cartridge:**

| Part | Mass |
|---|---|
| 2 × Snail 2305 | 55.6 g |
| 2 × AM32 ESC | 10 g |
| 2 × wheels | 20 g (est) |
| M2006 P36 + C610 | 107 g |
| Hopper, dial, barrel, cage | 150 g (est) |
| Chronograph gates | 10 g (est) |
| Connector half | 15 g (est) |
| 24 balls | 44 g |
| **Subtotal** | **≈ 412 g** |

**Total ≈ 1.16 kg**, leaving ≈ 0.34 kg of the 1.5 kg budget.

**Other cartridges:**

- **Dart cartridge** ≈ 422 g (est), with 23 rounds (one Koda 23-round magazine):

  | Part | Mass |
  |---|---|
  | 2 × Snail | 56 g |
  | ESCs | 10 g |
  | Wheels | 10 g |
  | Lailaps solenoid | 63 g |
  | Koda magazine | 115 g |
  | 23 darts | 23 g |
  | Cage and structure | 120 g (est) |
  | Chronograph and connector | 25 g (est) |

- **Gel cartridge** ≈ 0.5–0.6 kg (est; no gearbox mass is published).

**Centre of mass.** The pan motor is at the bottom, about 25 mm up; the cradle about 80 mm up; the hopper about
140 mm up. That puts the whole payload at ≈ 75–85 mm above the head plate (est), inside the 120 mm limit.

### 8.7 Jam mitigation in this concept

1. One ball per dial pocket, and the dial stirs the hopper.
2. The dial turns only when both wheels read in range on tach.
3. Stall-reverse on the dial, as in DJI's code: < 1 rad/s for 700 ms, then reverse 500 ms. Three tries, then SAFE
   with a "jam" message.
4. The chronograph flags no-ball and slow-ball shots.
5. Stray-round clear at low speed on every arming.
6. Approved balls only (the 23–24 mm bore and pocket reject darts and gel). Wet balls are kept out by the
   no-wet-grass rule.

### 8.8 Fit to the head payload interface

| Interface item | Fits? | Note |
|---|---|---|
| Mass ≤ 1.5 kg | Yes, ≈ 1.16 kg | |
| CoM ≤ 120 mm | Yes, ≈ 80 mm (est) | |
| Recoil ≤ 0.05 N·s | Yes, 0.039 N·s | |
| 24 shots | Yes | Hopper, not drum or belt |
| Bursts of 8 at 10/s | Hardware yes; kids' mode 5 at 3/s | |
| Power ≤ 40 W average | Yes | **Source must change** (§9) |
| Data: CAN-FD + USB | Yes | The C610 and DM-J4310 use classic CAN on the head bus; the head MCU bridges to the robot |
| Safety line | Yes | The arming contactor and the cartridge loop |
| Laser | Yes | |
| Reload at the dock | **Better:** automatic | The dock needs a silo mast |

---

## 9. What should change in docs/head-payload.md

| Row | Now | Proposed | Why |
|---|---|---|---|
| Power | "fused 24 V bus (from the 8S pack), ≤ 40 W average" | "Fused tap on the 45–58 V bus (5 A, est) through the turret arming contactor, feeding a dedicated 24 V payload converter (≥ 100 W continuous, ≥ 150 W for 0.5 s, est) in the body. ≤ 40 W average; peaks ≤ 150 W for ≤ 0.5 s" | D25 replaced the 8S pack. The J501's 24 V converter and the 30 W 12 V rail have no spare (§8.5) |
| Recoil | "≤ 0.05 N·s per shot (1.3 g dart at 38 m/s)" | "≤ 0.05 N·s per shot (a 1.83 g ball at 70 fps is 0.039 N·s; a 1.0 g dart at 80 fps is 0.024 N·s)" | 38 m/s is 125 fps, far over every cap |
| Magazine | "24 shots, drum or belt; a drum of 24 darts adds roughly 0.2–0.3 kg (estimate)" | "24 shots in the head. Default: a hopper of 24–30 foam balls (≈ 0.3 L, 44 g of balls). Alternative cartridge: a 23-round short-dart magazine (115 g)" | §3, §8 |
| Rate of fire | "bursts of 8 at up to 10 shots per second" | Keep as the hardware and simulation case; add "kids' mode: ≤ 3 per second, bursts ≤ 5 (S4)" | S4 |
| Safety line | as is | Add: "speed cap per ammo set by a hard-wired cartridge ID: balls 70 fps, darts 80 fps; any over-cap shot latches SAFE" | §6.1, §7.2 |
| Mounting | "bolt pattern to be fixed" | Add a **launcher cartridge** interface on the tilt cradle: 2 dowels + latch, one blind-mate connector (24 V 10 A, CAN, arming loop, chronograph gates, 2 ammo-ID pins) | §7.2 |
| Reload | "Swap the magazine at the reload station" | "The dock pours counted balls into the head hopper (silo on a dock mast, servo gate, break-beam counter); the dart cartridge is swapped by hand" | §8.4 |
| Range | "3.5–4 m at 24 m/s" | Re-run the `targets` scenario with 1.83 g, 22.7 mm balls at 19.8–21.3 m/s | The sim fires 1 g darts |
| Aiming laser | as is | Add "a module with a stated class from a maker that certifies it; measured ≤ 1 mW" | §6.5 |
| New row: ammo | — | "Foam only (balls or short darts) for players under 14. Gel beads only at 14+ events with sealed goggles, ≤ 100 fps" | §2.4, 16 CFR 1250 |

`designs/*.json` (`head_payload`):

- Set `magazine` to "24-ball hopper, refilled at the dock".
- Add `ammo_mass_g: 1.83`, `muzzle_speed_m_s: 21.3` and `kid_rate_hz: 3`.
- Keep `mass_g` 1500 and `com_above_top_mm` 120. The concept fits under both.

---

## 10. Open questions

- **Ball exit speed against wheel speed and diameter,** for the hard ceiling in §8.3. Settle it on the bench with a
  chronograph.
- **Foam balls on damp grass.** Does closed-cell EVA (Worker Cheetah) or PU (Dart Zone) pick up water and jam? Test it.
- **AM32 RPM telemetry** on the Repeat ESC. Confirm bidirectional DShot works; otherwise use C615 + a hall tach.
- **Whether a Tritium robot game falls under 16 CFR 1250** if gel is ever used, and whether a soft 7.5 mm bead passes
  the 5.0 mm funnel gauge.
- **The RoboMaster S1's launch mechanism** (spring piston or friction). This decides whether a compact flywheel gel
  launcher is proven.
- **Mass of the M2006 dial assembly and hopper as printed,** and the real CoM. Measure once CAD exists.
- **Laser visibility.** Class 1 at ≈ 0.2 mW against Class 2 at 1 mW in daylight. Test both before choosing.
