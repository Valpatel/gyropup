# Actuator and wheel-motor interfaces

Checked 2026-10-25. Machine-readable copy: `catalog/interfaces.json` (keyed by catalog id). Vendor files:
`references/vendor/<catalog-id>/` with a `SOURCE.txt` in each folder.

**How to read the tables.**
- Units are mm, g, N and N·m.
- "PCD" is the bolt-circle diameter. "▼6" means thread depth 6.
- **Output face** is the rotating face the link bolts to. **Case** is the stator or housing.
- The source column says where each value came from:
  - **drawing** is the vendor's dimensioned 2D drawing. These are primary.
  - **STEP** means measured in the vendor STEP with OCP (cylinder faces grouped by radius, PCD and depth). STEP values are secondary and are used where the drawing is silent.
  - **inferred** gives its reasoning.
  - **not found** means the vendor publishes no value. Nothing here is guessed.
- **Thread depth on the STEP models.** RobStride, CubeMars and Damiao model tapped holes as tap-drill cylinders (3.3 mm for M4, 2.5 mm for M3, 4.2 mm for M5), sometimes with a cosmetic major-diameter body. A STEP depth is drill depth, so the drawing's ▼ value wins.

Short URL keys used in the tables:

| Key | URL |
|---|---|
| RS-git | https://github.com/RobStride/Product_Information (commit 384cc56, `Product Literature/CAN2.0/<model>/`) |
| RS03-man | https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS03/RS03User%20Manual261013.pdf |
| RS04-man | https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS04/RS04User%20Manual260713.pdf |
| RS06-man | https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS06/RS06User%20Manual260713.pdf |
| RS00-man | https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS00/RS00User%20Manual260713.pdf |
| RS02-man | https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS02/RS02User%20Manual260713.pdf |
| RS-readme | https://github.com/RobStride/Product_Information/blob/main/README.md |
| RS-spec | `灵足时代RS系列产品规格介绍(2026.010.09).pdf` in RS-git (spec book, 2026-10-09) |
| BW-shop | https://shop.odriverobotics.com/products/botwheels |
| BW-dwg | https://cdn.shopify.com/s/files/1/0580/2904/7878/files/BotWheel_Drawng.png?v=1738951877 |
| BW-docs | https://docs.odriverobotics.com/v/latest/hardware/odrive-motors.html#odrive-botwheel |
| CM-dl | https://www.cubemars.com/technical-support-and-software-download.html |

---

## Summary

| Part | Drawing | STEP downloaded | Output pattern | Case pattern | Output bearing |
|---|---|---|---|---|---|
| RobStride RS-03 | yes (manual p.9) | yes | 6×M4▼6 + 3×Ø4 dowel holes on Ø30.36 | 8×M4▼8 on Ø98, Ø70 spigot | 45×58×7 deep-groove (STEP) |
| RobStride RS-04 | yes | yes | 9×M5▼6.5 on Ø36 + 3×Ø6 pins (proud 3) | 10×M4 on Ø106 both faces | 61810 50×65×7 deep-groove (STEP) |
| RobStride RS-06 | yes | yes (2 versions) | 6×M4▼6 + 3×Ø4 on Ø24, Ø37 boss | 8×M3▼8.5 on Ø82, Ø52 spigot | 35×47×7 (STEP) |
| RobStride RS-00 | yes | yes | 6×M3▼5 on Ø27 + 3×Ø3 on Ø24.46 | 6×M3 + 2×Ø3 on Ø50; rear 4×M3▼4 Ø38 | not found |
| RobStride RS-02 | yes | yes | 6×M4▼7 + 3×Ø4 on Ø24 | 9×M3▼8 + 3×Ø3 on Ø73, Ø43 spigot | not found |
| ODrive BotWheel | yes (shop image) | **no** (Onshape, login) | n/a (rotating tyre) | 4×M6 on Ø36, Ø50 boss (stator) | 80 kg/wheel rated load |
| CubeMars AK70-10 | yes | yes | 6×M3▼7 on Ø25, Ø20 pilot | 8×M3 on Ø83 both faces | crossed roller, C 2000 / C0 2520 N |
| CubeMars AK10-9 V3 | yes | yes | 6×M4▼7 + 2×Ø3 on Ø24 | 6×M4 on Ø90 both faces | not found |
| CubeMars AK80-64 | yes | yes | 6×M4▼8 on Ø28, Ø21 pilot | 8×M3 Ø89 / Ø85 | C 2000 / C0 2520 N |
| Damiao DM-J8009P-2EC | yes | yes | 6×M5▼8 + Ø4/Ø3 dowels on Ø32 | 6×M4 on Ø90 both faces | crossed roller (RAU5005) |
| Damiao DM-J10010L-2EC | yes | yes | 9×M5▼5 on Ø36 + 3×Ø5 pins | 10×M4▼5 on Ø106 both faces | not found |
| Unitree GO-M8010-6 | **no** | no (CC BY-NC-SA, in Qmini) | not found | not found | not found |

### Things that matter for the design

1. **RS-03 strings decoded.** Our catalog strings were `30.35x9x6 M4` and `98x8x8 M4`. The drawing shows they are PCD × hole count × depth, but the counts hide something:
   - **Output, `30.35x9x6`.** The "9" is **6 tapped M4▼6 plus 3 plain Ø4 (+0.1/0) dowel holes ▼7**, all on Ø30.36±0.2.
     - The M4 holes sit at 30°, 90°, 150°…, 60° apart.
     - The dowel holes sit at 60°, 180° and 300°.
     - So the pattern is **not** 9 equally spaced M4 holes. A 9×M4 bolt circle will not fit.
     - The exact PCD is 30.36, not 30.35.
   - **Case, `98x8x8`.** This one reads as written: **8×M4▼8 on Ø98±0.2**, on the lug faces on the output side, at 22.5° + 45°·k.
     - The mounting face also has a **Ø70 0/−0.1 male spigot, 2.5 mm high**.
   - **Do not use the website's "106 × 106".** The STEP envelope is Ø100.5 over the lugs. The drawing gives no outside diameter.

2. **The RS-03 output face is flush with a stationary ring.** In the STEP, the Ø47 output flange face and the Ø59–70 housing spigot ring lie in the same plane, with zero axial gap.
   - A link plate larger than about Ø58 that bolts flat to the output will rub the housing.
   - The link needs a boss of Ø58 or less (Ø56 is suggested), or a relief.
   - RS-06 has the same arrangement: the Ø37 output sits flush with a Ø48–52 housing ring.
   - RS-04 and RS-02 sit only 0.5 mm proud.
   - Measured from the STEP, not stated in the manuals.

3. **The RS-03 rear is 2.5 mm longer in the STEP than on the drawing:** 56.6 mm in the STEP against 54.1 mm on the drawing. Use 56.6 for packaging until a real unit is measured.

4. **The RobStride output bearings are thin-section deep-groove ball bearings, not crossed rollers.**
   - RS-03: 45×58×7. RS-04: 61810, 50×65×7. RS-06: 35×47×7.
   - These come from the STEP part names and sizes.
   - RobStride publishes **no axial, radial or moment ratings**.
   - For cantilevered thigh and shank loads in a 19 kg robot, give the joint its own support bearing, or at least check the moment, before trusting the actuator bearing.
   - The DM-J8009P (crossed roller) and AK70-10 (crossed roller, C0 2520 N) are the alternatives with published or stated crossed rollers.

5. **RS-04 and DM-J10010L look interchangeable but are not.** Both are Ø120 with 10×M4 on Ø106 at the case and 9×M5 on Ø36 at the output, each with 3 pins on the output. The pins differ:
   - RS-04: Ø6 on Ø35.86.
   - DM-J10010L: Ø5 on a 19.5 radius (Ø39).

   One adapter could serve both only if it carries both pin sets.

6. **Cables exit radially at the rear on every RobStride unit.**
   - RS-03: two connector pockets on opposite flats of the Ø79.5 rear cover.
   - RS-00: on the side of the body.
   - RS-04: a **fixed 310 mm harness** through a silicone-sealed grommet.

   No hollow shafts are available in any of these parts, so cables cannot go through a joint axis. Plan an external service loop at each joint.

7. **BotWheel.**
   - Mount: single-sided on a fixed stator boss, Ø50 0/−0.04, carrying 4×M6 on Ø36±0.05.
   - The boss face sits 7.5±0.8 mm outboard of the tyre side.
   - The cable leaves **axially through the centre of that boss**.
   - The harness is 300±25 mm long and ends in JST WPJ (3-pin phase) and JST JWPF (8-pin feedback) waterproof connectors.
   - The leg bracket therefore needs a central through-hole for the cable inside the M6 pattern.
   - M6 thread depth is not published.

---

## RobStride RS-03 (hip and knee, 4 per robot)

Drawing: RS03-man, section 1.1 (PDF page 10). STEP: `references/vendor/robstride-rs-03/RS03.stp`, a Creo assembly dated 2025-08-20 with 47 bodies, some of which are empty. STEP axis is +Z, with the output at +Z and the connector pockets at ±Y.

| Item | Value | Source |
|---|---|---|
| **Envelope** | | |
| Lug ring (case) outside diameter | Ø100.5 max (STEP r = 50.25); the drawing gives no OD | STEP |
| Website "106 × 106" | not supported by drawing or STEP | RS-git product page / STEP |
| Rear driver cover | Ø79.5 | drawing |
| Body length (lug ring incl. 2.5 spigot) | 39.5 | drawing |
| Overall length | 54.1 on the drawing; **56.6 in the STEP** (rear cover face 2.5 further) | drawing / STEP |
| Mass | 880 ± 20 g (manual); 900 ± 20 g (README); 928 ± 20 g (spec 2026-10-09) | RS03-man §1.4, RS-readme, RS-spec |
| **Output (rotor)** | | |
| Output flange diameter | Ø47 | STEP |
| Output face position | flush with the housing Ø70 spigot face; 2.5 beyond the lug mounting face | drawing (2.5) / STEP (flush) |
| Tapped holes | 6 × M4 ▼6 blind, on Ø30.36 ± 0.2, at 30°+60°·k | drawing / STEP angles |
| Dowel holes | 3 × Ø4 +0.1/0 EQS, depth 7 blind, same Ø30.36 PCD, at 60°/180°/300° | drawing / STEP angles |
| Centre feature | Ø20.2 × 2.5 deep recess, then Ø15 bore with internal 635 bearing and Ø5 shaft (not a through-hole) | STEP |
| Hollow shaft | none | STEP |
| Internal-only | 3 × M5 on Ø38.5 (carrier screws, not an interface) | STEP |
| **Case (stator)** | | |
| Mounting holes | 8 × M4 ▼8, EQS on Ø98 ± 0.2, at 22.5°+45°·k, on the output-side lug faces | drawing |
| Spigot | Ø70 0/−0.1 male, 2.5 high, on the output side | drawing |
| Rear-face mounting | not specified. The STEP models M4 threads from the rear lug face as well, but on the drawing's back view 4 of the 8 rear positions carry socket screws. Unconfirmed; do not use. | drawing / STEP |
| **Bearing** | | |
| Output bearing | single deep-groove ball, 45×58×7 (STEP part "1_2_04_680902"; size matches 6809/61809) | STEP (inferred type) |
| Axial / radial / moment rating | not found | — |
| **Connectors** | | |
| Power | AMASS XT30APW-M on the board; mating XT30UW-F | RS03-man §2.3 |
| CAN | GH1.25-2PWT on the board; mating GH1.25-T. Pin 3 CAN_L, pin 4 CAN_H | RS03-man §2.3–2.4 |
| Debug | 4-pad SWD (SWDIO, SWCLK, 3V3, GND) | RS03-man §2.4 |
| Exit | radial. Two pockets in the rear-cover flats at ±Y, within the rear ~6 mm; XT30 window about 11 × 5.3, GH window about 6.8 wide. Plugs insert radially. | STEP (inferred) |
| Fixed leads / cable OD / bend radius | none / not found / not found | — |
| **Encoder** | | |
| Encoders | 2 magnetic, 14-bit; "absolute turn". The manual does not say the second one reads the output directly. | RS03-man §2.1, RS-readme |
| Through-bore | no | STEP |
| **Downloads** | | |
| STEP | `RS03.stp` (3.98 MB): `Product Literature/CAN2.0/RS03/RS03.stp`. Downloaded. | RS-git |
| Licence | none in repo (all rights reserved by default); kept local only | RS-git |

## RobStride RS-04 (swap candidate)

Drawing: RS04-man §1.1 (PDF page 10). STEP: `RS04.stp`, a Creo assembly. Output at +Z.

| Item | Value | Source |
|---|---|---|
| Outside diameter | Ø120 | drawing |
| Body / rear cover | 39 ± 0.15 body, plus a Ø94 × 13.2 ± 0.2 rear cover | drawing |
| Overall | 52.2 + 0.5 output step + 3 pins; STEP 55.7 | drawing / STEP |
| Mass | 1420 ± 20 g (manual); 1510 g (spec PDF) | RS04-man, RS-spec |
| Output face | 0.5 ± 0.3 proud of the case front face; flange about Ø49.8 | drawing / STEP |
| Output tapped holes | 9 × M5 ▼6.5 min, on Ø36 ± 0.1 | drawing |
| Output pins | 3 × Ø6 0/−0.01 **installed** dowel pins on Ø35.86 ± 0.025, protruding 3 ± 0.25 | drawing / STEP (pins modelled) |
| Case, front | 10 × M4 EQS ▼5 min, on Ø106 ± 0.1 | drawing |
| Case, front locating | 2 × Ø5 0/−0.01 (as drawn), on Ø106 at 3° and 183°; the STEP shows 4.5-deep holes | drawing / STEP |
| Case, rear | 10 × M4 EQS ▼6, on Ø106 ± 0.1 | drawing |
| Output bearing | 61810 (50×65×7) deep-groove ball, from the STEP part name | STEP |
| Bearing ratings | not found | — |
| Connectors | **Fixed harness**: 310 ± 5 mm sheathed lead through a silicone-sealed grommet ("出线口使用硅胶密封"), radial exit from the rear cover, then a 40 ± 3 mm breakout. Board end XT30APW-M and GH1.25-2PWT; line end XT30UW-F and GH1.25. Colours: blue CAN_H, brown CAN_L, black GND, red VBAT+. | RS04-man §2.2–2.4 |
| Cable OD / bend radius | not found | — |
| Encoder | 2 magnetic, 14-bit | RS04-man |
| STEP | `RS04.stp` (8.7 MB). Downloaded. | RS-git |

## RobStride RS-06 (tail lift)

Drawing: RS06-man §1.1 (PDF page 9). The STEP comes in two versions: `RS06-new.step` (Onshape, 2026-03, single body) and `RS06.STEP` (older multi-body). Both are 84.5 × 82 × 50.5.

| Item | Value | Source |
|---|---|---|
| Envelope | (Ø88) reference over the lugs; STEP 84.5 × 82 | drawing / STEP |
| Length | 49 ± 0.5 rear face to lug face, body 33 ± 0.5; plus a 1.5 ± 0.1 output boss, so 50.5 total | drawing / STEP |
| Rear cover | (Ø70) | drawing |
| Mass | 621 ± 3 g | RS06-man |
| Output boss | Ø37 0/−0.05, 1.5 ± 0.1 proud of the lug face. Flush with a Ø48–52 housing ring in the STEP. | drawing / STEP |
| Output tapped | 6 × M4 ▼6, on Ø24 ± 0.1 | drawing |
| Output dowels | 3 × Ø4 +0.05/0, depth 4, on Ø24 at 0°/120°/240° | drawing / STEP |
| Centre | Ø14 +0.05/0 recess, Ø10 ± 0.1 step; not a through-hole | drawing / STEP |
| Case | 8 × M3 ▼8.5, on Ø82 ± 0.2, on the output-side lug face | drawing |
| Spigot | Ø52 0/−0.05 | drawing |
| Rear mount | not specified; the STEP shows M3 from the rear on 4 of the 8 lugs | STEP |
| Output bearing | 35×47×7 ring (6807/61807 size) | STEP `RS06.STEP` |
| Bearing ratings | not found | — |
| Connector | AMASS XT30PB(2+2)-M.G.B on the board, mating XT30(2+2)-F.G.B, carrying power and CAN together. Radial pocket on the side (inferred from the STEP feature at −X). | RS06-man §2.3 / STEP |
| Encoder | 2 magnetic, 14-bit | RS06-man |
| STEP | both files downloaded | RS-git |

## RobStride RS-00 (tail wag)

Drawing: RS00-man §1.1 (PDF page 8). STEP: `RS00.step`, single body.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø57; 51 ± 1 body, plus a Ø35 output boss 1 proud (STEP shows 0.4); STEP 51.4 total | drawing / STEP |
| Mass | 310 ± 3 g | RS00-man |
| Output tapped | 6 × M3 ▼5 blind, on Ø27 ± 0.1, at 30°+60°·k | drawing |
| Output dowels | 3 × Ø3, on Ø24.46 ± 0.1, at 0°/120°/240°; depth 3.1 in the STEP; no tolerance on the drawing | drawing / STEP |
| Case, front | 6 × M3 EQS on Ø50 ± 0.1 (depth not on the drawing; STEP 5.5); 2 × Ø3 +0.04/+0.02 ▼5 dowel holes on Ø50 at 15° and 195° | drawing / STEP |
| Case, rear | 4 × M3 ▼4, on Ø38 ± 0.1, at 45°+90°·k | drawing |
| Bearing | not found | — |
| Connector | XT30PB(2+2)-M.G.B, mating XT30(2+2)-F.G.B. **Radial, on the cylindrical side** of the body, visible on the drawing side view. | RS00-man §2.3 / drawing |
| Encoder | 2 magnetic, 14-bit | RS00-man |
| STEP | `RS00.step`. Downloaded. | RS-git |

## RobStride RS-02 (swap candidate)

Drawing: RS02-man §1.1 (PDF page 8). STEP: `rs02.stp`, single body. The IP67 variant has its own STEP, `RS02-ip67-20261013.stp`, which was not downloaded.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø78.5; body 28; 41.5 total (STEP 45.5); rear cover Ø65 | drawing / STEP |
| Mass | 380 ± 3 g (README); 405 g (Seeed / catalog) | RS-readme |
| Output | spigot Ø43 0/−0.1 stands 3.5 0/−0.3 proud of the case face; output face 0.5 beyond the spigot | drawing |
| Output tapped | 6 × M4 ▼7 min, on Ø24 ± 0.2 | drawing |
| Output dowels | 3 × Ø4 +0.1/0 EQS on Ø24 (90°/210°/330° in the STEP); depth not found | drawing |
| Case | 9 × M3 ▼8 EQS on Ø73 ± 0.2, plus 3 × Ø3 +0.1/0 "工艺孔" (tooling holes) on Ø73 | drawing |
| Bearing | not found | — |
| Connector | XT30PB(2+2)-M.G.B. Radial notch in the rear cover (drawing back view). | RS02-man §2.3 |
| Encoder | 2 magnetic, 14-bit | RS02-man |
| IP | IP52 per the website and catalog; not in the manual | catalog |
| STEP | `rs02.stp`. Downloaded. | RS-git |

---

## ODrive BotWheel (wheel hub motor, 2 per robot)

Drawing: BW-dwg, a dimensioned PNG on the shop page. It is in first-angle projection with Chinese labels. "视图A" means "view A".

| Item | Value | Source |
|---|---|---|
| Tyre / wheel OD | Ø171.30 (reference); shop says 171 | BW-dwg / BW-shop |
| Wheel width | 44.6 ± 1.5 | BW-dwg |
| Mounting | **Single-sided.** Fixed stator flange on one side only; the other side is a closed hub with a centre cap and no axle. | BW-dwg (both side views) |
| Mounting boss | Ø50 0/−0.04 male boss, 5 ± 0.1 thick. The boss face is 7.5 ± 0.8 outboard of the tyre side face. | BW-dwg |
| Bolt pattern | 4 × M6 on Ø36 ± 0.05 (shop: "4x M6 screw holes on a 36mm diameter circle pattern") | BW-dwg / BW-shop |
| M6 thread depth | not found | — |
| Overall width to mounting face | about 52.1 (44.6 + 7.5) | inferred |
| Hub cover screws | 10 × M3 (assembly only, not an interface) | BW-dwg |
| Mass | 2.2 kg | BW-shop |
| Load rating | "Rated load weight: 80kg / wheel", about 785 N radial | BW-shop |
| Axial / moment rating | not found | — |
| Cable exit | **axial, from the centre of the stator boss.** The bracket needs a clearance hole inside the 4×M6 pattern. | BW-dwg |
| Cable length | 300 ± 25 from the boss face to the connectors; a "200 REF" dimension is probably the sheathed portion | BW-dwg (inferred for 200) |
| Phase connector | JST 03T-WPJV-1-SM (WPJ series, 3-pin, waterproof) | BW-dwg, BW-shop |
| Feedback connector | JST 08R-JWPF-VSLE-D housing with SWPR-001T-P025 pins (JWPF 8-pin, waterproof). The supplied stub harness ends in JST PUD with the ODrive S1 pinout. | BW-dwg, BW-shop |
| Cable OD / bend radius | not found | — |
| Encoder | hall sensors plus a 3200 CPR incremental encoder; not absolute | BW-docs |
| Thermistor | NTC 20k 3950 | BW-docs |
| IP rating | IP54 ("Driving in rain is ok but driving through puddles is not.") | BW-shop |
| Tyre type | patterned tread; solid or pneumatic not stated | BW-shop photos |
| STEP | **not downloaded.** Onshape publication https://cad.onshape.com/publications/ffa16d9268e83ffcb5643cba/w/81f7a79746984b3bebf1d392/e/3101f331226b74a504e702ae. STEP export needs an Onshape login. | BW-shop |

---

## CubeMars AK70-10 (swap candidate)

Drawing: https://www.cubemars.com/data/cms/202602/ak70-10-robotic-actuator-2d-drawing.pdf (first-angle). STEP: `AK70-10 V2.0.STEP`, taken from the 3D zip on CM-dl.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø89 × 50.25; rear cover Ø71 × 11.2; output-side ring Ø77, 6 proud | drawing |
| Mass | 621 g | product page |
| Output flange | Ø30, 0.5 beyond the Ø77 ring | drawing |
| Output tapped | 6 × M3 ▼7 on Ø25 | drawing |
| Output pilot | Ø20 +0.02/0 ▼2, a female centre recess | drawing |
| Extra | the STEP also has 2 × Ø3 × 3 holes at 90°/270° on Ø25 (not on the drawing) | STEP |
| Case | 8 × M3 ▼10 on Ø83 (output side); 8 × M3 ▼3.5 on Ø83 (rear) | drawing |
| Bearing | crossed roller ("Equipped with cross-roller bearing"); basic load ratings C = 2000 N, C0 = 2520 N | https://www.cubemars.com/product/ak70-10-kv100-robotic-actuator.html |
| Connectors | XT30PW-M power; A1257WR-S-4P CAN; A1257WR-S-3P UART; radial on the rear cover | product page / drawing |
| Encoder | single 14-bit magnetic, motor side | product page |
| STEP | downloaded | CM-dl |

## CubeMars AK10-9 V3.0 (swap candidate)

Drawing: https://www.cubemars.com/data/cms/202602/ak10-9-v3-0-robotic-actuator-2d-drawing.pdf (first-angle). STEP: `AK10-9 KV60 V3.0-3D.STEP`.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø98 × 61.7 ± 0.15; body 50.5; output-side stack Ø82 / Ø55 / Ø30 rising 10.2 above the case | drawing |
| Mass | 940 g | product page |
| Output | Ø30 flange, 2 proud of the Ø55 step; 6 × M4 ▼7 on Ø24; 2 × Ø3 +0.05/0 ▼3 dowels on Ø24 (72°/252° in the STEP) | drawing / STEP |
| Case | 6 × M4 ▼8 on Ø90 (output side); 6 × M4 ▼4 on Ø90 (rear) | drawing |
| Bearing | not found | — |
| Connectors | black XT30 (2+2) for power and CAN; white CJT 3-pin for UART; radial slot in the rear cover | https://www.cubemars.com/product/ak10-9-v3-0-kv60-robotic-actuator.html / drawing |
| Encoder | dual: 21-bit motor plus 15-bit output; keeps position after power-off | product page |
| STEP | downloaded (the zip also has a Parasolid .x_t, not extracted) | CM-dl |

## CubeMars AK80-64 (listed in the brief; 64:1, not QDD)

| Item | Value | Source |
|---|---|---|
| Envelope | Ø98 × 61.9; rear cover Ø71 × 11.2; output-side Ø80 ring 8 proud, Ø35 boss 1 proud | drawing https://www.cubemars.com/data/cms/202602/ak80-64-robotic-actuator-2d-drawing.pdf |
| Output | 6 × M4 ▼8 on Ø28; 2 × Ø3 +0.05/0 ▼3; Ø21 +0.02/0 ▼4.5 centre pilot recess | drawing |
| Case | 8 × M3 ▼10 on Ø89 (output side); 8 × M3 ▼7 on Ø85 (rear) | drawing |
| Bearing | C = 2000 N, C0 = 2520 N (the same figures as AK70-10, possibly copied) | product page |
| Connectors | XT30PW-M / A1257WR-S-4P / A1257WR-S-3P | product page |
| STEP | `ak80-64.stp` (2022). Downloaded. | CM-dl |

---

## Damiao DM-J8009P-2EC (crossed-roller 8009)

Drawing: https://github.com/dmBots/DM-J8009P-2EC/tree/master/drawings/2d (`8009-rau 5005-20240809.PDF`). STEP: `models/3d/8009-RAU_5005_外形尺寸-20240809.stp`, saved locally as `8009-RAU_5005_outline-20240809.stp`. Manual: `manual/DM-J8009P-2EC Gear Motor User Manual V1.3 2026-09-10.pdf`, read but not copied.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø98 × 61.70; body 40.80; rear Ø71; output-side steps Ø82 / Ø70 / Ø52.5 | drawing |
| STEP envelope | 107.2 wide: something sticks out beyond Ø98, probably at the connector; check before packaging | STEP |
| Mass | about 963 g | manual V1.2 change log |
| Output | Ø40 flange, 1 proud of the Ø52.5 step; 6 × M5 ▼8 on Ø32 | drawing / STEP |
| Output dowels | Ø4 +0.04/+0.02 ▼4 and Ø3 +0.04/+0.02 ▼4 on Ø32. The drawing calls one of each; the STEP has 2 × Ø4 (0°/180°) and 2 × Ø3 (120°/300°). | drawing / STEP |
| Case | 6 × M4 ▼6 on Ø90 (output side); 6 × M4 ▼4 on Ø90 (rear) | drawing |
| Bearing | crossed roller ("The output shaft of the DM-J8009P-2EC uses a cross roller bearing"); file name says RAU5005; ratings not found | manual / drawing |
| Connectors | XT30 power (200 mm pigtail supplied); GH1.25 2-pin CAN; GH1.25 3-pin UART debug; on the side of the rear cover | manual / drawing |
| Encoder | 2 magnetic, single-turn absolute at the output (survives power loss) | manual |
| STEP | downloaded (1.4 MB) | dmBots |

## Damiao DM-J10010L-2EC

Drawing: https://github.com/dmBots/DM-J10010L-2EC/tree/master/drawings/2d (`dm-j10010l-2ec-2D尺寸图.pdf`, first-angle). STEP: `models/3d/dm-j10010l-0730_1.STEP`, 25 MB.

| Item | Value | Source |
|---|---|---|
| Envelope | Ø120; body 37.7 ± 0.25 plus rear Ø94 +0.2/−0.5 × 15 0/−0.6; manual says "53 mm excl. locating pins"; STEP 60.9 | drawing / manual / STEP |
| Mass | about 1372 g | manual V1.1 |
| Output | face 0.5 ± 0.2 proud; 9 × M5-6H ▼5 on Ø36 ± 0.12 | drawing |
| Output pins | 3 × Ø5 0/−0.02 **installed** pins at radius 19.5 ± 0.02 (Ø39; the STEP confirms R19.5 at 30°/150°/270°), protruding 3 +0.1/−0.2 | drawing / STEP |
| Output centre | Ø28 +0.08/0 bore; depth not found; not through (closed rear cover) | drawing |
| Case | 10 × M4-6H ▼5 on Ø106 ± 0.12, on both faces | drawing |
| Bearing | not found | — |
| Connectors | XT30 power; GH1.25 CAN; RS485 port ("not yet open"); GH1.25 3-pin UART; on the side of the Ø94 rear cover | drawing / manual |
| Encoder | 2 magnetic, 14-bit, output single-turn absolute | manual |
| STEP | downloaded (SolidWorks native files not downloaded) | dmBots |

DM-J10010-2EC (non-L) also has a drawing and STEP in its repo (https://github.com/dmBots/DM-J10010-2EC). It was not processed because the catalog already prefers the L version.

## Unitree GO-M8010-6 (basic only)

| Item | Value | Source |
|---|---|---|
| Envelope / mass | Ø96.5 × 42.3, 530 g (existing catalog entry; no drawing found) | https://www.unitree.com/mobile/go1/motor/ |
| Output / case bolt patterns | not found; no public drawing. Photos show a flanged output with 6 pockets. | https://shop.unitree.com/products/go1-motor |
| Connector | XT30 (2+2) carrying power and RS-485, on the side of the rear housing; the RS-485 adapter uses GH1.25-3 | GO-M8010-6 manual V1.0 (techshare.co.jp copy); product photos (inferred position) |
| Encoder | single-turn absolute on the rotor; not absolute at the output | manual §3 |
| Bearing ratings | not found | — |
| STEP | none for the motor alone. It exists only inside the Qmini biped assembly (https://github.com/unitreerobotics/Qmini, Git LFS, 88 MB, CC BY-NC-SA 4.0). Not downloaded. | GitHub |

---

## How comparable robots route leg cables

Nobody in this group routes through a hollow joint axis:

- **Upkie** daisy-chains power (XT30, 14 AWG, 42 cm leads) and CAN (JST PH-3, 26 AWG twisted pairs) from hip to knee to wheel along the outside of the legs. Its hip joint limit is set by "Cables fully stretched" ([cables](https://upkie.github.io/upkie/cables.html), [electronics testing](https://github.com/tasts-robots/upkie/wiki/4%29-Electronics-testing), [upkie_description](https://github.com/upkie/upkie_description)).
- **DIABLO** uses a parallelogram leg with the wheel motor flanged to the bottom link. "Some linkages are designed in an arched form to accommodate practical wiring considerations", which means external cables in a protected channel ([arXiv 2407.21500](https://arxiv.org/abs/2407.21500)).
- **Ascento** keeps the leg actuators (ANYdrive) in the body and drives the legs through four-bar linkages, so only the frameless hub-motor (Maxon EC90) cables run down the leg ([arXiv 2005.11435](https://arxiv.org/abs/2005.11435)).
- **Unitree Go2-W** and **LimX TRON 1** routing is not publicly documented. TRON 1's tool-free swappable foot modules with automatic recognition imply a connector at the lower leg (inferred; [New Atlas](https://newatlas.com/robotics/limx-tron-1-biped-robot/)). A Go2 teardown notes only "meticulous cable management" ([Simplexity](https://www.simplexitypd.com/blog/unitree-go2-quadruped-robot-dog-teardown/)).

None of these robots documents slip rings or cable carriers. With no hollow actuators in our candidate list, the practical pattern is the Upkie/DIABLO one: an external service loop at each joint, sized for the full joint range, plus a protected channel along each link.
