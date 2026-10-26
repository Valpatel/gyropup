# RobStride open-source projects and printed-leg practice

Checked 2026-10-26. This note asks what working RobStride-class robots do about the problems our first printed leg fails on:
- the thigh's bending stiffness and strength;
- the motor plate that carries the 61812 support bearing;
- the printed yoke that ties two motors to the body.

The reference point is Gyropup: 22 kg, two RS-04 (or RS-03) per leg on the hip axis, a push-rod knee, about 48 N·m peak per leg motor and about 600 N peak wheel load.

**Labels used below:**
- **as-built:** the project built and ran it.
- **design-only:** it exists only in CAD.
- **our calc:** our own arithmetic, not a published number.
- **unverified:** a claim we could not confirm from a primary source.

**How the RobStride page was read.** https://robstride.com/open-source is a JavaScript single-page app; the HTML has no content.
- The project list was taken from the site bundle `https://robstride.com/assets/index-297ed294.js`. Its `OpenSourceHome` component has 8 built-in entries.
- The bundle also merges extra entries from `https://robstride.com/api/community-links/public`. That endpoint returned **HTTP 502** on 2026-10-26.
- So any community links the API adds were not visible. Re-check the page later.

---

## 1. Lessons for our printed leg

1. **Successful printed thighs are big boxes, not slim beams.**
   - LeRobot Humanoid is RobStride, PLA+, Bambu H2D, about 12.7 kg in its MJCF (biped, no arms). Its thigh is a two-piece clamshell measured from the published 3MF:
     - main shell 118.3 × 60 × 390.6 mm, cover 118.3 × 31 × 227 mm;
     - so the envelope at the motor end is about **118 × 91 mm**, with the RS-03 bodies inside it.
   - With the same 4 mm wall, that envelope has about **10–15× the second moment of area of our 52 × 36 box** (our calc: 2.2–3.3 × 10⁶ mm⁴ vs 0.22 × 10⁶ mm⁴). Their robot is roughly half our mass.
   - Their shin is 72.2 × 2 × 24 mm (about 72 × 48) by 280 mm.
   - **Action:** let the thigh section grow toward the motor diameter near the hip, and taper it toward the knee. Do not add wall thickness to a 52 × 36 tube.
   - Sources: [printing guide](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/manufacturing/printing_guide.md), [thigh 3MF](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/manufacturing/h2d_profiles/thigh_femur_example.3mf), [MJCF](https://github.com/Virgileboat/lerobot-humanoid-model/blob/main/models/bipedal_plateform_no_arms/mjcf/robot.xml).

2. **Support every big joint on both sides (clevis/yoke), with a small bearing on the far side, not a large bearing around the output.** This is the dominant pattern:
   - **K-Bot** (RS-04 hip pitch and knee):
     - a "Drive" plate on the output flange and an "Idle" plate on a **6805 (25 × 37 × 7)** bearing;
     - the bearing sits on a stub bolted to the motor's back face with countersunk M4s (6 per knee, 4 per hip). This is inferred from the BOM part names and fastener counts, not from a drawing;
     - the link straddles the motor.
   - **LeRobot:** the thigh is screwed to the RS-03 on one side and turns in a **15 × 21 × 4** bearing (retained by a printed "hat", 3 × M2.5) on the other.
   - **Duke Humanoid V2:** "actuator in a two-plate yoke", with a bearing retainer on every RS-03 output in the leg.
   - **Upkie:** offers printed "hip support" and "knee support" parts with a **40 × 52 × 7** bearing "to reduce play and protect knee actuators from radial load".
   - **Action:** replace the 61812 motor plate with a straddle mount (output flange + a small bearing on the motor's back face, RS-04 has 10 × M4 on both faces). Where layout allows, do the same for the knee pin. Our mech-review item A3 already flags the single-sided knee pin.
   - Sources: [K-Bot BOM](https://github.com/kscalelabs/docs/blob/HEAD/docs/robots/k-bot/assets/Kbot_BOM.xlsx) (parts KD-D-157F, 163, 190, 357F–359F, 403, 451F, 491F), [LeRobot assembly guide](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/assembly/assembly_guide.md), [Duke V2 structure notes](https://github.com/fullyopenhml/fullyopenhml.github.io/tree/HEAD/Duke_Humanoid_V2_OpenSource), [Upkie parts](https://github.com/upkie/upkie_parts).

3. **Use the whole RS-04 output pattern, and do not count on the pins in plastic.**
   - K-Bot uses all **9 × M5** per RS-04 output:
     - hip: M5 × 12, 8.3 mm clamp, 6.5 mm thread in the motor;
     - knee: M5 × 20 through a 14.5 mm aluminium flange.
   - This also confirms 9 × M5 against Primo's mesh-derived "6 × Ø5" (unverified).
   - The RS-04's Ø6 pins stand only about 3 mm proud. At 48 N·m each pin bears on 6 × 3 mm at about **50 MPa** (our calc; 124 MPa at 120 N·m). That is above the Z tensile strength of PA6-CF (48 MPa, `fabrication.md`). Clamp friction from the M5s has to carry the torque.
   - **Action:**
     - print the flange 15–20 mm thick;
     - put a bought steel ring or large washer under the M5 heads to spread the clamp load;
     - use the maximum thread engagement the manual allows ("screw depth should not exceed the casing thread depth", 6.5 mm per our drawing notes);
     - threadlock;
     - re-torque after the PA6-CF settles (anneal first, see 8).
   - Duke's first-article check found their RS-04 parts drawn with M4 where **M5** was needed. Check the flange against the drawing, not a mesh.
   - Sources: [K-Bot BOM](https://github.com/kscalelabs/docs/blob/HEAD/docs/robots/k-bot/assets/Kbot_BOM.xlsx), [RS-04 manual §1.1](https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS04/RS04User%20Manual260713.pdf), [Duke V2 structure and manufacturing](https://github.com/fullyopenhml/fullyopenhml.github.io/tree/HEAD/Duke_Humanoid_V2_OpenSource/_archive/hardware-site-docs-before-slim/design), [Primo bonegen](https://github.com/AlessioPagliai/primo/blob/HEAD/cad/bonegen/README.md).

4. **Mount the motor housing by its face bolt circle, from both faces if possible. Never clamp it radially in a print.**
   - K-Bot bolts RS-04 housings with 10 front M4 plus 4 rear M4 at the knee.
   - LeRobot screws each thigh RS-03 "four on both sides" (8 × M4 × 10).
   - Primo (design-only, PA-CF) explains why radial clamping is wrong in print: a printed clamp insulates the motor, creeps under preload, and RobStride housings are not specified for radial clamping. "Face screws with metal inserts remain the right joint for a printed robot."
   - Sources: [Primo actuator-integration](https://github.com/AlessioPagliai/primo/blob/HEAD/docs/actuator-integration.md), [LeRobot assembly guide](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/assembly/assembly_guide.md).

5. **A printed mount derates the motor thermally.**
   - The RS-04 manual rates **40 N·m continuous only on a 345 × 345 mm aluminium heat sink**, and 35 N·m on 220 × 200 mm. Winding protection uses a 145 °C limit.
   - A PA6-CF mount is not a heat sink, so the continuous knee and hip torque while crouched-balancing will be lower than 40 N·m (amount unknown; measure it).
   - Primo's simulation puts RS-04 legs above rated torque (about 45 vs 40 N·m) while walking at about 45 kg.
   - **Action:** log the motor temperature fields during long crouch tests. Consider a bought aluminium plate or the chassis as a heat path.
   - Sources: [RS-04 manual §1.2–1.3](https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS04/RS04User%20Manual260713.pdf), [Primo AI memory](https://github.com/AlessioPagliai/primo/blob/HEAD/docs/handoffs/ai-memory.md).

6. **Print the long links flat, so bending runs along the layers. Go solid at joints.**
   - LeRobot prints the thigh on its side, not its front face. Settings for thigh and shin: eSUN PLA+, 0.4 nozzle, 0.2 mm layers, **4 walls, 35 % gyroid**, 6 top / 4 bottom layers. Hip parts use **100 % infill** (zig-zag, 0.16 mm).
   - reBot (Seeed) prints load-bearing parts in ABS at 30–80 % infill.
   - Primo printed its ankle gimbal in PPA-CF with 1 wall and 90 % grid. Its rule: minimum member at least 5 mm, main load paths in the layer plane, or MJF/SLS.
   - Sources: [LeRobot 3MF profiles](https://github.com/Virgileboat/lerobot-humanoid-hardware/tree/main/docs/manufacturing/h2d_profiles), [reBot B601-RS BOM](https://github.com/Seeed-Projects/reBot-DevArm/blob/main/hardware/reBot_B601_RS/README.md), [Primo CAD README](https://github.com/AlessioPagliai/primo/blob/HEAD/cad/README.md).

7. **Do not press-fit bearings hard into prints. Use a light fit plus a screwed retaining cap.**
   - LeRobot's builder cracked both tibia bearing seats tapping in 15 × 21 × 4 bearings ("on my first attempt I cracked both slots"). The repair was melting the plastic back with a soldering iron.
   - LeRobot retains its thigh bearing with a printed hat and 3 × M2.5.
   - Primo: "no heavy interference in the printed PA-CF (it cracks the layers…)". Print, test the fit, adjust the diameter, use Loctite 603/638 as backup.
   - K-Bot's tolerances are for machined aluminium: 6805 housing 36.94–36.98 interference at hip and shoulder, 37.03–37.10 clearance at the knee. Do not copy them into plastic.
   - Sources: [LeRobot assembly guide](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/assembly/assembly_guide.md), [K-Bot bearing bores PDF](https://github.com/kscalelabs/docs/blob/HEAD/docs/robots/k-bot/assets/KBot_KD_Bearing_bores.pdf), [Primo AI memory](https://github.com/AlessioPagliai/primo/blob/HEAD/docs/handoffs/ai-memory.md).

8. **Put metal under every loaded screw.**
   - LeRobot's lower thigh screw holes were "pretty loose"; the builder added M4 heat-set inserts.
   - Berkeley Humanoid Lite adds "through-screws and embedded brass hex stands" to "prevent failures along layer boundaries".
   - RobStride's own EDULITE A3 arm uses brass inserts (M2–M4) throughout.
   - reBot warns that screws loosen in service and asks builders to threadlock every joint screw. Duke used Loctite 222; Primo uses Loctite 243 on nuts.
   - From our fabrication notes: un-annealed PA6-CF bolted joints crept daily, and annealing fixed it.
   - Sources: [BHL paper](https://arxiv.org/abs/2504.17249), [EDULITE SOP](https://github.com/RobStride/EDULITE_A3/tree/main/hardware/assembly_sop), [reBot BOM](https://github.com/Seeed-Projects/reBot-DevArm/blob/main/hardware/reBot_B601_RS/README.md).

9. **Pins: use shoulder screws as axles, and make the clamp chain metal-to-metal.**
   - LeRobot uses ISO 7379 shoulder screws Ø5 (Norelem 07534-05X40 / -05X20, 12.9) and Norelem 27628 rod ends.
   - Primo's rule for pushrod pins: the Ø8 shoulder must **bottom out** so the nut preloads on metal; the printed centre part is "only a spacer". Pins are Ø8 × M6 shoulder screws, M8 aluminium rod ends, Ø12 × M10 for the gimbal axes.
   - For slow oscillating pivots, Primo chose flanged igus plain bushings (radial in the bore, axial on the flange) over needle rollers, because needle rollers risk false brinelling.
   - K-Bot's ankle linkage uses 8 mm clevis pins with circlips in oil-free flanged bushings (Misumi MDZF-8-8, 15 mm bushes at the pivot).
   - Sources: [LeRobot BOM](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/hardware/bom/bom_buy.md), [Primo AI memory](https://github.com/AlessioPagliai/primo/blob/HEAD/docs/handoffs/ai-memory.md), [K-Bot BOM](https://github.com/kscalelabs/docs/blob/HEAD/docs/robots/k-bot/assets/Kbot_BOM.xlsx).

10. **Hard stops must not load the printed link or the motor flange.**
    - K-Bot's hip-yoke and ankle stops are separate **304 / 4340 steel** parts bolted on.
    - LeRobot's printed hip-yaw stop tab is meant to break off ("they also break off if too much force applied").
    - **Action:** a printed stop either has a bought steel insert or is a cheap, replaceable fuse part.
    - Sources: [K-Bot BOM](https://github.com/kscalelabs/docs/blob/HEAD/docs/robots/k-bot/assets/Kbot_BOM.xlsx), [LeRobot assembly guide](https://github.com/Virgileboat/lerobot-humanoid-hardware/blob/main/docs/assembly/assembly_guide.md).

11. **Use torque limits well below the motor peak.**
    - K-Bot's deployed soft limits are **70 % of peak**: RS-04 84 of 120 N·m, RS-03 42 of 60, RS-02 11.9 of 17, RS-00 9.8 of 14.
    - The RS-04 manual says not to change the torque limit, protection temperature or over-temperature time.
    - Our 48 N·m working peak on an RS-04 is about 40 % of its peak, which leaves good headroom. On an RS-03 it is 80 % of the 60 N·m peak.
    - Sources: [kinfer-kbot constants.rs](https://github.com/kscalelabs/kinfer-kbot/blob/HEAD/src/constants.rs), [RS-04 manual](https://github.com/RobStride/Product_Information/blob/main/Product%20Literature/CAN2.0/RS04/RS04User%20Manual260713.pdf).

12. **Nobody publishes measured link loads, and no open wheel-legged robot on RS-03/RS-04 was found.**
    - None of the projects publish strain or load measurements on printed links. Duke's design rule asked for SF ≥ 3, but the check column is empty for all 32 CNC parts.
    - Primo plans to log joint wrenches from its walking policy (99.5th percentile plus a fall case) and generate bones from them. That is the method our FEA load cases should follow, especially the fall, landing and kerb cases (mech-review A5).
    - We are the first we know of to put a 22 kg wheel-leg on RS-04s with printed structure. Plan a sacrificial test leg.
    - Sources: [Primo bonegen plan](https://github.com/AlessioPagliai/primo/blob/HEAD/cad/bonegen/README.md), [Duke V2 notes](https://github.com/fullyopenhml/fullyopenhml.github.io/tree/HEAD/Duke_Humanoid_V2_OpenSource/_archive/hardware-site-docs-before-slim/design).

### Load levels compared

The motor-peak figures are vendor peaks. "Per kg" is that peak divided by robot mass, a crude severity index (our calc).

| Robot | Mass | Leg big joints | Peak N·m | Peak / robot kg | Structure | Status |
|---|---|---|---|---|---|---|
| **Gyropup** | 22 kg | 2 × RS-04 (or RS-03) per leg, push-rod knee | 48 used (120 / 60 peak) | 2.2 (used) | PA6-CF / PETG printed | design |
| LeRobot Humanoid | ≈12.7 kg (MJCF, no arms) | 2 × RS-03 in each thigh (inferred: hip pitch + knee; knee via printed rods); RS-02 hip yaw; RS-05 ankles | 60 | 4.7 | PLA+ printed | as-built (photos) |
| K-Bot | ≈36.7 kg (MJCF); ≈30–34 kg quoted elsewhere | RS-04 hip pitch, knee; RS-03 hip roll/yaw; RS-02 ankle | 120 (soft limit 84) | 3.3 (2.3 soft) | CNC 6061-T6 | as-built (dev kits) |
| Duke Humanoid V2 | 36 kg with arms (as built) | RS-04 knee; RS-03 hips, ankle 1; RS-06 ankle 2 | 120 | 3.3 | CNC aluminium + printed brackets | as-built |
| Berkeley Humanoid Lite | 16 kg, 0.8 m | own printed cycloidal 6512 / 5010 actuators | about 20 tested (ramp to 20 N·m in the stiffness test) | ≈1.3 | PLA, aluminium-extrusion torso | as-built |
| Primo | ≈45 kg est. | RS-04 hips + knees, RS-06 ankles via pushrods | 120 | 2.7 | PA-CF / PPA-CF printed | design-only |

The LeRobot leg is the closest printed analogue: RobStride, printed, Bambu, push-rod knee, two motors on the thigh. But it carries about 60 % of our mass per leg, and it is not a wheel-leg. None of these robots has our wheel-side load cases.

---

## 2. Everything on robstride.com/open-source

From the site bundle (`OpenSourceHome`, 8 built-in entries; API extras not available, see above).

| # | Name | URL | Category | RobStride motors | Licence (repo) |
|---|---|---|---|---|---|
| 1 | EDULITE_A3 (EL-A3 arm) | https://github.com/RobStride/EDULITE_A3 | robot | RS-00 × 3 (L1–L3), EL05 / RS-05 × 4 (L4–L7, gripper) | MIT |
| 2 | reBot-DevArm (Seeed) | https://github.com/Seeed-Projects/reBot-DevArm | robot | B601-RS: RS-00 × 4, RS-06 × 3 (B601-DM uses Damiao) | hardware CERN-OHL-W-2.0, firmware Apache-2.0 |
| 3 | K-Bot (K-Scale) | https://github.com/kscalelabs/kbot | robot | RS-04 × 4, RS-03 × 8, RS-02 × 6, RS-00 × 2 | hardware CERN-OHL-S; software: LICENSE file is MIT but README/docs say GPL v3 (open [issue #2](https://github.com/kscalelabs/kbot/issues/2)) |
| 4 | lerobot-humanoid (Virgile Batto, ex-Hugging Face) | https://github.com/Virgileboat/lerobot-humanoid | robot | RS-00 × 2, RS-02 × 2, RS-03 × 4, RS-05 × 4 (biped platform) | umbrella: none; sub-repos (hardware, model, design, runtime) Apache-2.0 |
| 5 | MotorStudio | https://github.com/RobStride/MotorStudio | toolchain | all (config/tuning tool) | none stated |
| 6 | Python_Sample | https://github.com/RobStride/Python_Sample | toolchain | RS-00 … RS-06 | MIT |
| 7 | robstride_ros_sample | https://github.com/RobStride/robstride_ros_sample | toolchain | RS-02 (ROS) | none stated (reposted from MuShibo) |
| 8 | RobStrideSPC | https://github.com/RobStride/RobStrideSPC | toolchain | RS series, STM32 reference | none stated |

Also linked on the site:
- download page: https://github.com/RobStride, https://gitee.com/robstride
- Discord: https://discord.gg/mqYuyMhmCk
- Seeed product pages for RS-00 … RS-06
- Amazon and AliExpress stores

Other repos on the RobStride GitHub account, not on the page:
- `Product_Information`: manuals, STEP, spec books;
- `EL_A3_Data_Collection` and `EL_A3_VLA_Deploy` (MIT);
- `CAN-USB-data-conversion`;
- `SampleProgram`: STM32 RS-01 library;
- `robstride_actuator_bridge` (fork).

---

## 3. Per-project notes

### 3.1 LeRobot Humanoid (on the page): the closest printed analogue

Repos: https://github.com/Virgileboat/lerobot-humanoid (umbrella) and `-hardware`, `-model`, `-design`, `-runtime`, `-identification` under the same owner. Public Onshape: https://cad.onshape.com/documents/fb645318a27646d1d8840be6/w/d1cae8805fb652b4d1614997/e/804a1da43f242001a05129b4.

**What it is.** A low-cost biped humanoid (under USD 5k target; about USD 2.6k for the biped platform BOM). It is "3D-printed first", in PLA+ on a Bambu H2D.
- 75 STL parts, about 3.5 kg of filament.
- MJCF mass of the no-arms biped: 12.7 kg (our sum of body masses).
- Motors: torso RS-00 × 2, hip-z RS-02 × 2, thigh RS-03 × 4 (two per thigh; inferred to be hip pitch + knee), shin RS-05 × 4 (ankle).

**Construction:**
- **Thigh:** a clamshell (`femur_12` + `femur_22`), envelope about 118 × 91 × 390 mm at the motor end, holding both RS-03s.
  - Motor housings are screwed "four on both sides" (M4 × 10).
  - The thigh's far side turns in a 15 × 21 × 4 bearing in `hipxy`, retained by a printed hat (3 × M2.5).
  - Halves are joined by 4 × M4 × 30 near the top motor and 2 × M4 × 16 lower down. Those holes were loose, and the builder fitted M4 heat-set inserts.
- **Knee:** the knee RS-03 in the thigh drives a printed crank (`knee_actuation`). Two printed rods (`knee_rod12/22`, flat bars joined by 3 × M3 × 18) run to the tibia, with 15 × 21 × 4 bearings either side of the crank and in the tibia.
  - So the knee is a printed push-rod linkage like ours, with no metal rod ends.
  - The ankle uses Norelem 27628-01-05 rod ends on Ø5 ISO 7379 shoulder screws.
- **Hip yaw:** two **6207 (35 × 72 × 17)** bearings per hip carry the leg below the RS-02. The torso RS-00s also sit on a 6207 stack. Extra bearings sit wherever a small motor would otherwise carry the leg moment.
- **Print settings** (3MF and guide):
  - PLA+ (eSUN), 4 walls, 35 % gyroid, 0.2 mm (guide default 0.15 mm, 0.2 mm nozzle, 30 % gyroid);
  - **100 % infill for hip-x and hip-z parts**;
  - the thigh is printed on its side;
  - "orient prints so layer lines do not take the main tensile load".
  - Issue #1: the femurs need roughly a 300 × 300 bed. **Our 256 mm bed would need the thigh split.**
- **Assembly rules:**
  - press bearings and motor pins in during sub-assembly;
  - direct screws into plastic at "around 5 N·m for non-structural plastic threads". That value looks high for M3/M4 in PLA (unverified, possibly a typo).
  - Some fits are deliberately tight; ream at low speed.

**Failures and fixes reported** (assembly-guide comments by builder Paul Ruiz):
- tibia bearing slots cracked on press-fit, repaired with a soldering iron;
- loose femur screw holes, fixed with heat-set inserts;
- the hip-z RS-02 can only take 3 of 6 output screws (plus 3 pins) once installed, an open design issue;
- the hip stop tab is designed to break off.

**Electronics:**
- "SavvyCAN-FD is currently the only adapter proven … to handle the RobStride CAN protocol";
- commissioning script `hardware/config/commission_motor.py` (switch to MIT mode, set ID) before assembly.

**Licence:** Apache-2.0 on the hardware repo (STL, docs), model, design and runtime. The umbrella has no licence file. Copying is allowed with attribution and a NOTICE.

### 3.2 K-Bot (K-Scale Labs; on the page)

Repo https://github.com/kscalelabs/kbot. Docs source https://github.com/kscalelabs/docs: `docs/robots/k-bot/`, with BOM xlsx, bearing-bore PDF and a 93-page assembly PDF. docs.kscale.dev did not resolve on 2026-10-26 (see also kbot issue #4).
- Onshape: [public release](https://cad.onshape.com/publications/e15cf8edefacbba3009917c0/), [legs](https://cad.onshape.com/documents/56df9b1704928b974a7d6785/w/5b4e7939b4075909e2f1e83f/e/0f3313ac1d4663a7156d6caf).
- Teardown video: https://www.youtube.com/watch?v=qhZi9rtdEKg.
- A wiki reports K-Scale ceasing operations after shipping few units (single source, **unverified**: https://aiwiki.ai/wiki/k_scale_k_bot).

**Mass and motors:**
- MJCF `kbot-models/kbot/robot.mjcf` sums to 36.7 kg (other sources say 30–34 kg).
- RS-04 at hip pitch and knee, RS-03 at hip roll/yaw and shoulders, RS-02 ankle/elbow, RS-00 wrist.
- The docs' table gives RS-00 5/14 N·m, RS-02 6/17, RS-03 20/60, RS-04 40/120 rated/peak.
- Deployed soft limits are 70 % of peak (kinfer-kbot).

**Structure (BOM).** Every structural part is **CNC 6061-T6**. Hard stops are 304 or 4340 steel. The head and battery are MJF nylon/ABS mouldings. It is not printed, but the joint architecture transfers:
- **Drive/Idle clamshell yokes:** each joint link is two halves.
  - The drive half bolts to the motor output: RS-04 9 × M5 (M5 × 12 at the hip, M5 × 20 through 14.5 mm at the knee).
  - RS-03 outputs use 6 × M4 × 20 plus 3 Ø4 × 10 dowels ("7 motor, 6 yoke").
  - The idle half rides on a **6805 (61805) 25 × 37 × 7** bearing on a stub screwed to the motor's back.
  - Clamshell halves are located with Ø3 dowels and joined with M4/M5 "clam bolts".
- **Housing bolts:** knee RS-04 is held by 10 × M4 × 8 front plus 4 × M4 × 8 idle side. The hip bracket uses 7 × M4 × 16 per RS-04.
- **Bearing fits** (for aluminium, after anodising): hip and shoulder housings 37 −0.06/−0.02 (interference), shaft 25 −0.10/−0.03; knee housing 37 +0.03/+0.10 (clearance), shaft 25 +0.002/+0.03 (interference). Root radius ≤ 0.03.
- **Ankle:** a CNC four-bar with 8 mm clevis pins, circlips and Misumi oil-free flanged bushings; the end stop is 4340 steel.

**Lessons:**
- The docs call the wiring harness "the least reliable part of the robot". K-Scale replaced the stock RS-03/RS-04 CAN plug.
- A community builder (https://dev.to/infoslack/building-my-humanoid-robot-pdg) printed the arm in PLA with nylon torso sides from JLC3DP. They expect plastic will not carry two arms and plan aluminium. They also hit the 11-bit vs 29-bit CAN ID mismatch: the motors silently ignored LeRobot frames.

**Licence:** hardware **CERN-OHL-S** (strongly reciprocal: a derived hardware design must be released under the same licence). Software is ambiguous (MIT file vs GPL-3 README). `kbot-models`, `kinfer-kbot` and `kscalelabs/robstride` are MIT. **Do not copy K-Bot CAD into our private repo.** Dimensions and ideas in this note are fine.

### 3.3 EDULITE A3 (RobStride's own reference design; on the page)

https://github.com/RobStride/EDULITE_A3 (MIT); hardware in `hardware/` via Git LFS: STEP, 3MF, wiring, PCB, assembly SOP.
- **Robot:** a 6-DoF desk arm plus gripper. RS-00 × 3 (±14 N·m), EL05/RS-05 × 4 (±6/5.5 N·m). Driven over SocketCAN, CAN 2.0 extended frames, 1 Mbps.
- **Printed structure (SOP-A3-ASM-001):** 23 printed parts with brass heat-set inserts (M2 × 3.5 × 4, M3 × 4 × 5, M3 × 5 × 5, M4 × 5 × 5).
  - Joints get **thin-section support bearings 6704, 6705 (× 2), 6707** pressed into printed housings, plus dowel pins.
  - Motor outputs take **long dowels through the output pin holes into the part** (M3 × 25 at the base, M3 × 14 at upper arm and forearm) plus countersunk screws.
- **Relevance:** low loads, but it is RobStride's own pattern of "printed housing + insert + support bearing + output dowels". The 3MF holds their slicer settings, not opened here (LFS).

### 3.4 reBot DevArm B601-RS (Seeed; on the page)

https://github.com/Seeed-Projects/reBot-DevArm, BOM at `hardware/reBot_B601_RS/README.md`.
- **Robot:** RS-00 × 4, RS-06 × 3, 2.5 kg payload, 754 mm reach.
- **Structure:** CNC **5052 aluminium plates carry the load** ("Link1 Left/Right Metal", "RS06 Front/Back Extension", "Motor 1 Bearing Mount"). Printed ABS "fillers" sit between the plates at 30 % infill (gripper fingers 45 %, printed on their side). Cosmetic parts are PLA at 15 %.
- **Bearings:** 6803ZZ × 3 plus an AXK5578 thrust bearing at the base.
- **Lessons stated:**
  - the production version replaces some printed parts with metal "for durability";
  - screws loosen in service, so every joint screw is threadlocked (hot-melt glue in the kit);
  - use the lowest torque setting on powered drivers to avoid stripping.
- **Licence:** CERN-OHL-W-2.0 (weakly reciprocal) for hardware.

### 3.5 Primo (not on the page): printed PA-CF, RS-04 legs, CC0

https://github.com/AlessioPagliai/primo (earlier name `umanoide`). **Design-only, not built, STL not print-validated.**
- **Robot:** 1.40 m, about 45 kg estimated. RS-04 × 6 (hips, knees), RS-03 × 3, RS-06 × 11 (ankles by two pushrods each), RS-00 × 8, RS-05 × 2. Structure in **PA-CF / PPA-CF on a Bambu H2C**.
- **Useful content:**
  - `docs/actuator-integration.md`: why face screws with metal inserts, not clamping, in printed PA-CF.
  - `cad/bonegen/`: topology-optimised bones between motor bolt circles, with swept keep-outs and multiple load cases. The thigh pilot finds the flat 10 mm PA-CF femur plate weak sideways and in twist: the generated shape is 1.75× stiffer laterally and 1.47× in torsion at equal mass.
  - `cad/motor_proxy.fs`: an Onshape FeatureScript for RobStride envelopes and bolt patterns.
  - `docs/handoffs/ai-memory.md` (large): ankle pivot design rules (see lesson 9); RS-04 legs above rated torque in simulation.
  - `docs/motor-selection.md` and `actuator-tables.md`: RobStride vs Encos, CubeMars and others.
- **Note:** it lists the RS-04 output as "6 × Ø5 on Ø36", read from a mesh. Our drawing reading and K-Bot's BOM both say 9 × M5.
- **Licence:** **CC0 1.0**, except `sim/isaaclab/code/` (BSD-3). Anything may be copied.

### 3.6 Duke Humanoid V2 / "Fully Open Humanoid" (not on the page)

- **Duke Humanoid V2** (Duke General Robotics Lab), https://github.com/generalroboticslab/duke_humanoid_v2 (Apache-2.0).
  - As built: 36 kg with arms. RS-04 knee, RS-03 hips/waist/ankle-1, RS-06 ankle-2.
  - Machined aluminium (6061 likely; grade unverified) with printed brackets and heat-set inserts in printed holders.
  - Joints are an actuator in a two-plate yoke with front and back bearing retainers. "Main bearing 50 × 65 × 7" (61810).
  - First-article check: shafts filed, one bearing retainer bored out as a "design error", RS-04 needed M5 where the CAD had M4.
  - Team CNC rules: structural walls at least 4 mm, at least 4 mm of thread (6 preferred), SF ≥ 3 target, never recorded as checked.
- **Fully Open Humanoid v0.2**, https://fullyopenhml.github.io/ (repo https://github.com/fullyopenhml/fullyopenhml.github.io).
  - A re-documentation and redesign effort around Duke V2. v0.2 is an all-printed **design release, not built**: 1.11 m, 26 kg estimated, RS-03/06/02/05, 34 printed parts, about 7 kg filament, 250 mm bed.
  - Its site says the joint kits include output support bearings. Its roadmap plans a v0.3 test loading a bonded CF-tube socket to failure.
  - The site states MIT / CC BY 4.0 (repo has no licence file).

### 3.7 Berkeley Humanoid Lite (not RobStride; printed reference)

Paper: https://arxiv.org/abs/2504.17249 (RSS 2025). Code MIT: https://github.com/HybridRobotics/berkeley-humanoid-lite. CAD/assets **CC BY-SA 4.0**: https://github.com/HybridRobotics/berkeley-humanoid-lite-assets. Docs: https://berkeley-humanoid-lite.gitbook.io/docs.
- **Robot:** 16 kg, 0.8 m. All custom structural parts and the cycloidal gearboxes are FDM **PLA** on a Bambu X1C. The torso is aluminium extrusion. Under USD 5k.
- **Design measures** against layer failure: through-screws, embedded brass hex standoffs, merged subcomponents.
- **Results:**
  - 60 h durability test (0.5 kg × 0.5 m pendulum, −45° to +90°, 0.5 Hz): efficiency recovered and backlash grew slightly (max 0.0229 rad);
  - stiffness 319 N·m/rad (PLA). The paper compares this with about 1468 N·m/rad for another printed actuator and puts the gap down to PLA vs PA-CF.
  - The adult-size variant extends the legs with **carbon fibre tubes**.
- No structural-failure issues in the GitHub issue list (55 issues, checked).
- **Licence caveat:** CC BY-SA on the CAD is share-alike. Do not copy the CAD into our repo unless we accept BY-SA for the derived parts.

### 3.8 Upkie (not RobStride; open printed wheel-biped)

https://github.com/upkie/upkie and https://github.com/upkie/upkie_parts (Apache-2.0, FreeCAD + STL).
- **Robot:** a small printed wheel-legged biped using mjbots actuators (qdd100 class; model and mass not checked here, unverified).
- **Relevant detail:** optional printed **hip and knee supports with a 40 × 52 × 7 bearing** "to reduce play and protect knee actuators from radial load". "Hollow legs become the default" in revision 2.
- No breakage reports in the issues or discussions we scanned.

### 3.9 Other wheel-legged and small projects (low relevance)

- **huoyiwei4/cybergear-wheel-legged-robot** (MIT): six Xiaomi CyberGear (the RobStride-made RS-01-class motor, about 12 N·m), printed legs (STL in `3D_print/`), STM32 LQR + VMC. Status: "not yet validated on hardware" per its README. No structural notes.
- **N-B-Studio/Open-wheel-legged-balance-bot** (Apache-2.0): "fully 3D-printed 8-DOF wheel-legged". Motor class not stated in the README.
- **Skythinker616/foc-wheel-legged-robot** (GPL-3.0): popular desk-scale design with small gimbal motors and servos.
- **ToddlerBot** (https://arxiv.org/abs/2502.00893; about 3.4 kg, 0.56 m, fully printed) and **Open Duck Mini**: servo-scale, loads far below ours. Not reviewed further.
- Searched and **not found**: any open-source wheel-legged robot on RS-03/RS-04 with printed legs (GitHub repo search "robstride", "wheel legged", "wheeled biped", "cybergear"; web search). DDT Diablo and LimX Tron are closed.

---

## 4. RobStride resources useful to us

**Product_Information** (https://github.com/RobStride/Product_Information, last commit 384cc56 on 2026-10-16, **no licence file**). Do not commit their PDFs or STEP to our repo; link them, as `references/vendor/` with `SOURCE.txt` already does.

Per model, under `Product Literature/CAN2.0/<model>/` and `CANFD/<model>-CANFD/`:
- user manual (EN and CN), STEP;
- models RS-00, RS-01, RS-02 (+ IP67), RS-03, RS-04, RS-05, RS-06, EL05, RS10P;
- the CN folder `产品资料/` has newer manual revisions (RS-04 CN 261009 vs EN 260713).

Spec books: `灵足时代RS系列产品规格介绍(2026.010.09).pdf` and the EL series book.

Accessories with manuals and STEP:
- `canhub`: USB-CANHUB;
- `powerBoard`;
- `dischargeModule`: regen bleeder;
- `canopen`: EDS file and CODESYS DS402 guide;
- `OTA/OTA.py` with an OTA protocol PDF;
- `CH341SER.exe`: driver for the USB-UART debugger.

**RS-04 manual, points that matter for structure:**
- The outline drawing (§1.1) has the note "When fixing, the screw depth should not exceed the depth of the casing thread". Our existing reading: 9 × M5 ▼6.5 on Ø36 + 3 × Ø6 pins proud 3; 10 × M4 on Ø106 both faces (`research/actuator-interfaces.md`).
- Rated 40 N·m at 100 rpm **on a 345 × 345 mm aluminium heat sink**, 35 N·m on 220 × 200. Peak 120 N·m at 90 A pk; Kt 2.1 N·m/Arms; 9:1; 1420 g; 24–60 V, 60 V maximum (overvoltage fault at 60 V); winding limit 145 °C; −20 to 50 °C ambient.
- Warranty excludes "damage caused by exceeding peak torque". The manual asks users not to change the torque limit, protection temperature or over-temperature time.
- **No radial, axial or moment rating** is published for the output bearing (already noted in `actuator-interfaces.md`). This is why everyone adds a support bearing.

**Discharge module** (`dischargeModule/Discharge Module User Manual V1.0.pdf`):
- 15–60 V operation, 30 A continuous, 200 A / 100 ms; resistor 3 Ω / 500 W to 10 Ω / 200 W.
- In 48 V mode it **starts at 64 ± 0.5 V and stops at 59 ± 0.5 V**, above the motors' 60 V maximum. So it is not a fix for mech-review item B7 (full pack at 60–63 V). The 24 V mode clamps at 34 V.

**Toolchain:**
- **MotorStudio** (https://github.com/RobStride/MotorStudio, no licence): Windows tool for ID, mode, parameters, encoder calibration and firmware. The repo holds only instructions; the binary is in the download centre.
- **Python_Sample**, "Robstride Dynamics Python SDK" (MIT; also https://github.com/ROBSTRIDE-DYNAMICS/Robstride-Dynamics-Python-SDK). SocketCAN, private 29-bit protocol, MIT/impedance mode (`run_mode 0`), PP, CSP, velocity and current modes, scan, ID write, fault decoding.
- **RobStrideSPC** (STM32F105 reference, no licence), **SampleProgram** (STM32F103 RS-01 class, private + MIT protocol), **robstride_ros_sample** (ROS 2 + canable, no licence), **CAN-USB-data-conversion** (frame bit-shift helper for their USB-CAN dongle).
- Community, MIT:
  - https://github.com/kscalelabs/robstride
  - https://github.com/sirwart/robstride
  - https://github.com/berkeley-humanoids/actuator-control (eRob, RobStride and Sito over SocketCAN)
  - Seeed "motorbridge" (https://motorbridge.seeedstudio.com) speaks the 29-bit protocol directly.
- RobStride's own USB-serial-to-CAN dongle works only with their PC tool. On Linux use a SocketCAN adapter: robstride_ros_sample says canable; LeRobot found only SavvyCAN-FD reliable.

**Not found:**
- a RobStride-published mounting guide, recommended screw torques for the output flange, or allowable link loads;
- an official URDF or MJCF. Use K-Scale's `kbot-models` MJCF actuator classes (MIT) for armature and friction starting values: RS-04 armature 0.04, frictionloss 0.2; RS-03 0.02 / 0.2.

---

## 5. Licences: what we may copy

| Source | Hardware / CAD | Code | Use in our private repo |
|---|---|---|---|
| RobStride Product_Information, MotorStudio, RobStrideSPC, robstride_ros_sample | no licence (all rights reserved) | no licence | link and cite only; dimensions and facts fine |
| RobStride Python_Sample, EDULITE_A3, EL_A3_* | MIT | MIT | copy with the MIT notice |
| reBot DevArm | CERN-OHL-W-2.0 | Apache-2.0 | ideas/dimensions fine; copied CAD stays OHL-W, and modified files must be released if distributed |
| K-Bot | **CERN-OHL-S** | MIT file vs GPL-3 README (unresolved) | ideas/dimensions only; do not copy CAD |
| kbot-models, kinfer-kbot, kscalelabs/robstride | – | MIT | copy with notice |
| LeRobot Humanoid sub-repos | Apache-2.0 | Apache-2.0 | copy with attribution + NOTICE |
| Primo | CC0 | CC0 (Isaac Lab code BSD-3) | free |
| Berkeley Humanoid Lite | **CC BY-SA 4.0** | MIT | code fine; CAD only if we accept share-alike |
| Duke Humanoid V2 | Apache-2.0 (per CITATION.cff) | Apache-2.0 | copy with attribution |
| Fully Open Humanoid site | MIT / CC BY 4.0 (stated on site, no licence file) | – | attribution |
| Upkie parts | Apache-2.0 | Apache-2.0 | copy with attribution |

This note copies no CAD or code. It quotes dimensions and settings with links.
