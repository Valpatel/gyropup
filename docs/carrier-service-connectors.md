# Carrier stator and pan-servo service connections

Work in progress for [issue 85](https://github.com/Valpatel/gyropup/issues/85), continuing the removable carrier in [issue 66](https://github.com/Valpatel/gyropup/issues/66). This page will bind the actual connectors, cable exits and parking positions to the complete module service check. It is not fabrication approval.

The [C2 candidate](base-board-interfaces.md) already requires C3 and the pan-servo connection to be unplugged while the carrier remains mechanically retained. Their real release and parked-tail geometry is still absent. A green C2 reservation check does not cover these connections.

| Interface | Current project selection | Evidence to establish before a service claim |
| --- | --- | --- |
| C3, module side | Molex 43020-1200 housing, twelve 43031-0001 male terminals, 24 AWG board tails | Exact cavity/view map, housing and contact geometry, installed pose, free wire exit, latch/grip access and module-side retention |
| C3, fixed stator side | Molex 43025-1200 housing, twelve 43030-0010 female terminals on the slip ring's own 28 AWG leads | Actual insulation diameter, usable lead length from the installed ring exit, housing/contact geometry, unmating travel and retained parked route |
| Pan servo | Catalog `feetech-sts3215-c018-12v`, Waveshare SKU 22414; the supplied three-pin lead | Exact selected variant, connector manufacturer/series or documented compatibility, cavity polarity/view, lead length/gauge/diameter, release direction and parking |

The legacy wiring table calls C3's board tails 60 mm long and its ring leads 250 mm. Those lengths are not yet demonstrated retained service slack. The existing “Molex 5264-type” servo description does not by itself identify a particular housing, terminal, mating header or crimp tool.

The next geometry check will retain the PCB, carrier, their four PCB screws and four inserts as one rigid module with exact member identities. External carrier retainers, base inserts, servo, stator connection, fixed harness and any removed bumper hardware will retain their separate identities and explicit service order. Conditional removal prerequisites will be labelled as such; they must not silently become proved teardown operations.

Before new full-service evidence is generated, the historical service checker must adopt complete input provenance and reviewed topology/uncertainty predicates. It must reject missing or wrong manufacturer variants, inaccessible latch/grip space, still-mated interfaces, inadequate retained tails and parked cables that obstruct withdrawal. Unknown manufacturer bend radius, insulation or actual lead data remains unknown rather than becoming a guessed clearance.

Manufacturer CAD is kept privately with source URL/hash and normalized-frame receipts. Public independently authored representations remain visibly labelled; no reservation is promoted to complete hardware. The separate input-protection circuit candidate has no allocated added-board envelope here and does not qualify the current electrical interface.

## Exact connector evidence, 2026-10-29

| Part | Primary manufacturer evidence | Current limit |
| --- | --- | --- |
| [43020-1200](https://www.molex.com/en-us/products/part-detail/430201200) | Twelve positions, two rows, 3 mm pitch; panel-mounted male housing. SDA-43020 revision G gives body width 18.85 mm, axial length 16.89 mm and panel thickness 1.40–2.54 mm. | The existing carrier is 3 mm thick. Direct snap retention in that plate is not supported. Panel wings make the actual CAD width 26.08 mm; body width alone is not an access envelope. |
| [43025-1200](https://www.molex.com/en-us/products/part-detail/430251200) | Matching twelve-position female housing. Drawing 430250000-SD revision A gives axial length 14 mm, width 18.85 mm and mated overall length 24.77 mm. | Its depicted 11 mm “for latching” dimension belongs to the header-mating illustration; it is not a specified latch deflection, finger clearance or unplug stroke. |
| [43031-0001](https://www.molex.com/en-us/products/part-detail/430310001), twelve | SD-43031 revision K2: male terminal, 20–24 AWG, insulation OD at most 1.85 mm, 12.40 mm reference length; chain packaging, hot-tin finish. | Exact STEP not yet retrieved. Cutting from the carrier strip must respect the 0.25 mm maximum cut-off vestige. An uncrimped drawing does not prove the installed crimp profile. |
| [43030-0010](https://www.molex.com/en-us/products/part-detail/430300010), twelve | SD-43030 revision N5: female terminal, 26–30 AWG, insulation OD at most 1.27 mm, 11.00 mm reference length; loose packaging, hot-tin finish. | The ring's 28 AWG gauge fits this range, but its actual insulation OD and crimp/tool compatibility remain unmeasured. |

The [Micro-Fit specification PS-43045-001 revision R](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf) calls for 19.1 mm free wire exit for 10–16 circuits. Keep ties, twisting and externally biased routing outside that zone. This is **not** a minimum bend radius. Per-contact product-page headline current ratings do not qualify the populated twelve-way connector, ambient temperature, parallel current sharing or the ring wiring.

The housing and female-terminal CAD links were obtained from the exact distributor product pages and kept in the ignored vendor cache. [Private input metadata](../research/carrier-service-connectors/private-inputs.json) records each URL and SHA256. The files carry their exact Molex numeric part identities; a matching direct manufacturer download/hash has not been obtained. No vendor CAD or derived meshes are published.

## Cavity views and seating

Look **into each connector's mating end, latch side upward**. The housing drawings label circuit 1, circuit 2 and the last circuit; the intermediate numbers below extend that row pattern. The mating-end identification is an interpretation of their third-angle projection and longitudinal terminal sections, not an explicit view caption.

```text
43025 receptacle               43020 plug
       latch ↑                     latch ↑
 7  8  9 10 11 12             12 11 10  9  8  7
 1  2  3  4  5  6              6  5  4  3  2  1
```

The two faces mirror horizontally so identical circuit numbers mate. Looking from the wire-entry side with the latch still upward mirrors each grid again. Do not substitute odd/even rows or use a wire-entry view as a mating-face pin map. The housing's moulded circuit 1 identifier must agree during assembly, followed by continuity verification at both ends before power.

For a housing-local frame, put the origin at the cavity-array centre on its leading mating plane; +X is the viewer's right, +Y points toward the latch and +Z points out toward the viewer. Wires run toward−Z. Receptacle circuit 1 is at(−7.5,−1.5) mm; plug circuit 1 is at(+7.5,−1.5) mm. Both rows are 3 mm apart and all columns have 3 mm pitch. Mating reverses X and Z while preserving latch-up; the two nose planes overlap 6.12 mm, derived from 16.89+14−24.77, rather than coinciding.

The housing sections place the male tip 2.00 mm REF and female front 0.76 mm REF behind their respective leading mating planes. These are seated positions, not insertion strokes. Both rows depict the same terminal clocking, with the crimp opening toward the latch. Terminal locking tabs must be fully seated before mating. Extraction travel and a qualified installed crimp envelope remain unresolved.

The existing C3 circuit assignments are retained:

| Cavity | Net | Domain / role |
| --- | --- | --- |
| 1,2,11 | BUS_HEAD_FUSED | Shared head supply, 15–20.5 V bench or 30–42 V vehicle input; not the U2-only protected output |
| 3,4,12 | GND | Shared supply return |
| 5 | CAN_H | CAN bus |
| 6 | CAN_L | CAN bus |
| 7 | SAFETY+ | Pulse output through the existing series protection |
| 8 | SAFETY− / GND | Pulse return |
| 9 | PAN_TTL | Servo data |
| 10 | SIG_GND | Signal reference |

## Supplied geometry is not complete internal geometry

The two housing files and the female terminal each import as a valid single solid. Their bounds and exact file hashes are checked by [the bounded input probe](../tools/check-carrier-connector-inputs.py). This is input identity, not mating qualification.

The supplied housing files close the wire-entry ends and simplify internal terminal cavities. At the drawing-derived mated length, the nominally aligned raw housing solids report about 82.50 mm³ overlap in that simplified region. The reversed-latch control also overlaps; separating the housings 16 mm clears them. The probe retains these relations with the reviewed topology and numerical-error checks. It does not remove material, waive interference or declare that the physical parts collide. External-outline placement can still be investigated, but complete mated fit and terminal insertion require more detailed source geometry or measured parts.

## Pan-servo connection

[Waveshare's current ST3215 documentation](https://docs.waveshare.com/ST3215_Servo) identifies the selected 12 V/30 kg·cm variant asSKU 22414. The [FEETECH ST-3215-C018 sheet](https://www.feetechrc.com/Data/feetechrc/upload/file/20260622/6391772519923113075854851.pdf), revision A/0 dated 2023-07-20, specifies a 5264-3P connection and 15 cm lead. Its numbered table assigns 1=GND,2=VCC,3=Signal. The case view depicts the two sockets as G–V–S; that view must not be relabelled as the free plug's wire-entry view.

There is a source discrepancy: the header detail is marked A2505-WV at 2.5 mm pitch, while the case/older Waveshare callout says 5264/2.54. No exact housing/contact manufacturer identity, supplied lead gauge, insulation OD or minimum bend radius has been established. Waveshare's [SR-Cable-5264-3PIN accessory](https://www.waveshare.com/sr-cable-5264-3pin.htm) is documented as compatible, but its 300/900 mm accessory lengths do not establish what is included with everySKU 22414 shipment.

The official [ST3215 CAD resource](https://docs.waveshare.com/ST3215_Servo/Resources-And-Documents) is retained privately as a conditional case reference. Its STEP root is named `SCS215 v5`; one of its eight solids is invalid, and the PCB model supplies only plain connector blocks, with no detailed cavities, contacts, latch, mating plug or cable. It cannot qualify the pan-servo disconnect. The carrier-side service connection should avoid requiring blind unplugging beneath the installed servo; its exact compatible termination and retained OEM lead must be established before that design is frozen.

A concrete conditional option is to retain the OEM servo-end plug and replace only the carrier-end termination with **CJT A2505H-3P plus three A2505-TP contacts**, mating to a **CJT A2505WV-3P** header. [CJT's own family drawing](https://www.cjt.com/upload/A2505.pdf) explicitly identifies that mating set: 2.50 mm pitch, 3 A family rating, 22–28 AWG contacts and maximum 1.90 mm individual insulation OD. The three-way housing is 8.30 mm wide; the header is 10.00 mm wide. This avoids assuming that the OEM housing mates to CJT. It is not selected until the OEM conductor gauge/OD, termination process, current/temperature performance and accessible support are verified. No exact manufacturer STEP was found for these parts. The header also needs its own assigned support/PCB footprint; the current pad-strip envelope does not provide one.

## Termination contract before a physical pad map

This is a wiring-interface proposal, not a checked electrical schematic or soldering instruction. It preserves the existing C2/C3 nets and the protection candidate's three electrical boundaries. The protection author confirmed that its actual external pads, footprints and return-current copper remain unallocated.

| Endpoints | Proposed physical connection | Still unresolved |
| --- | --- | --- |
| C2 signal-module 1 → C3 module 5 | One continuous 24 AWG CAN_H wire, male 43031-0001 contacts at both ends | Installed length, free exits, paired route and retention |
| C2 signal-module 2 → C3 module 6 | One continuous 24 AWG CAN_L wire, same contacts | As above; no invented PCB CAN pads or extra splice |
| C2 power+ → C3 module 1/2/11 and protection input | External BUS_HEAD_FUSED junction | Exact junction hardware, current sharing, insulation, branch lengths and location |
| C2 power− → C3 module 3/4/12, C3.8/C3.10 and circuit returns | External common-return junction | Actual terminal count, current paths, copper and location |
| C2 signal-module 3 | F4-protected 12V_PAN pendant-loop output | Physical F4/harness termination |
| C2 signal-module 4 | Existing U1 pins 8/4 pendant-loop return node | Actual board pad/jumper map |
| C3 module 7 | Existing R3 output, after D1 | Actual solder termination and insulated route |
| C3 module 9 | PAN_TTL bypass toward servo disconnect | Exact disconnect cavity view, lead compatibility and route |
| Servo VCC | Existing F1-protected 12V_PAN output | Assigned terminal and lead qualification |
| Servo GND | Common return | Assigned terminal and return-current route |

The protection candidate sees only BUS_HEAD_FUSED, GND and 12V_PAN. Its U2 A4/B4 pads are **PAN_INPUT after the cutoff**, so C3's shared head BUS must not be connected there. U2 A1/B1 are 12V_PAN; A2/A3/B2/B3 are GND. CAN, pulse and TTL routing remain outside that protection sheet. A logical junction in this table is not an existing physical connector, copper area or solder pad.

## External C3 service-pose candidate

The [external-space probe](../tools/check-carrier-connector-pose.py) places the housing array centre at turret **X84/Z34 mm**, with mating along Y and the latch facing outward +X. The module plug spans Y−16.89..0. The fixed receptacle initially spans Y−6.12..7.88. The connector stays above the installed bumper; lowering the module housing 13 mm is an explicit collision control.

| Stage | Fixed receptacle translation from its mated pose | Purpose |
| --- | --- | --- |
| Seated | (0,0,0) mm | Housing pose only; mating internals remain unqualified |
| Unplugged | (0,+16,0) mm | Design separation stroke, exceeding the 6.12 mm nominal nose overlap |
| Outboard before parking | (0,+43,0) mm | Move past the carrier before coming inward |
| Parked candidate | (−30,+43,0) mm | Array centre at X54/Z34; housing stays beyond the carrier's +Y edge |

Each straight segment is enclosed in the exact axis-aligned housing bounding-box sweep, which conservatively contains all intermediate positions. These boxes clear the listed base, carrier/PCB, bumper, pan clamp/ring, authored fasteners and C2/servo reservations under the recorded aggregate error budget. A finger-space reservation outside the latch is clear of those same neighbours. The original attempt lowered 9 mm while moving inward and failed against the base and bumper; it remains recoverable at commit 43696e7. The revised path retains height. A deliberately misplaced parked connector inside the carrier also fails.

These results do **not** qualify an installed connector support, parking keeper, finger ergonomics, latch flexure, upper-head sweep or cables. The mate pair is not counted as a clear interface. C2's source halves are represented at their released positions, **not** proved parking positions; they and their tails still need a parking route before the entire module can withdraw. The released rigid-module API must eventually include the actual retained assembly and every remaining obstacle.

Two anchor coordinates are explicit candidates, not existing retention hardware:

| Tail | Anchor candidate, turret mm | Retained length from anchor to connector | Necessary geometric lower bound |
| --- | --- | --- | --- |
| Fixed stator tail | (40,−35.5,13) | 145 mm | Maximum 135.30 mm during the stated motion |
| Module tail | (84,−39,34) | 30 mm | 22.11 mm |

The calculation preserves 19.1 mm unbiased straight exit, then measures the remaining endpoint distance. The norm is convex along each straight translation segment, so its endpoint maximum bounds that length expression throughout the segment. It still omits bending, bundle shape, crimp penetration, tie-wrap and obstacles; no wire route follows merely from a positive length allowance. The ring-to-fixed-anchor and PCB-to-module-anchor lengths are additional to these retained lengths. [SparkFun's exact ROB-13065 page](https://www.sparkfun.com/slip-ring-12-wire-2a.html) states 28 AWG and 250 mm leads; those are total supplier leads, not 145 mm of automatically available service slack.

The next concrete support must preserve the carrier's original fastener seats and PCB bosses, hold the connector body without biasing its free wire exit, and retain the fixed half outside the withdrawal volume. The current base-board “servo, ring, CAN pads” entry is a 2.5×10.2 mm rotated envelope, not an assigned solder-pad map. A real net-to-pad/termination map must precede acceptance of all C2, C3 and servo wire exits. Neither the legacy 60 mm module lead nor the new candidate lengths are accepted cutting instructions.

## Separate support candidate: access and stack, not a print recommendation

[The opt-in support source](../cad/turret_carrier_support.py) adds two new mounting holes at Y±10/Z10 mm. It preserves the carrier's original PCB bosses, four insert seats and four external retainer holes. The default turret still uses the earlier carrier; this candidate must not silently replace it in fabrication exports.

[Inspect the assembled support candidate](../exports/turret/base-board-service/connectors/C3-support-layout.step). The named colours distinguish authored parts, simplified public hardware, package envelopes and connector reservations. [Support only](../exports/turret/base-board-service/connectors/C3-support-candidate.step) and [carrier candidate](../exports/turret/base-board-service/connectors/carrier-support-candidate.step) are research inspection models, not approved print files.

| Part / interface | Concrete candidate | Remaining qualification |
| --- | --- | --- |
| Support-to-carrier screws | Two exact McMaster 91290A113 M3×8; seats at X58, shafts toward−X | Torque, loosening, printed bearing/creep and thread clocking |
| Nuts | Two exact 90592A085 class 8 M3 hex nuts; X50.6..53, AF5.5×2.4 mm | Pocket AF5.7 is a design allowance, not a measured print fit |
| Stack | 2 mm local support flange +3 mm carrier +2.4 mm nut; nominal 0.6 mm tip projection | Model stack is not proof of usable thread engagement or physical seating |
| Support structure | One connected frame with 14×8 mm top rails and 5.5×14 mm uprights; the 2 mm dimension applies only to local flange/panel | Strength, print orientation, conditioned material properties, fatigue and creep |
| Connector panel | 2 mm thick at Y−8.51..−6.51; nominal revision-G 12-way stepped cutout | Printed cutout tolerance and snap-clip flex/retention; rigid vendor overlap remains evidence |

The panel's rear face follows the private model's stop faces at raw Y−0.065, transformed by−8.445 mm. The drawing's C19.20/D22.89 dimensions map to world Z; its key faces +X. These are nominal geometry and pose evidence, not a flexible latch simulation. No material is removed from the manufacturer's housing model to force a fit.

On the bench, load the two nuts through the carrier's inward-open pockets, position the support and tighten its screws **before installing the PCB**. The pockets resist nut rotation but do not retain loose nuts axially before screw engagement. Hold them during assembly. Their screws, nuts and support remain part of the rigid removable module. Replacing this support requires removing the PCB first; its straight nut-removal corridor crosses the installed board. Normal module removal does not require removing these two nuts or screws.

The [bounded checker](../tools/check-carrier-connector-support.py) uses the actual newly acquired screw and nut solids, the exact private housing, the current PCB/component layout, C2 reservations and six existing straight wire exits. It preserves individual hardware identities, checks original and new driver corridors, tests the real nut inside a conservative translation sweep, and includes blocked-hole, blocked-tool and PCB-installed nut-removal controls. Public exports use separately authored hardware and a visibly labelled housing body-dimension representation. Vendor geometry stays private.

The first load screen uses the specification's **8 N per circuit maximum mating force**, hence 96 N for twelve circuits. The fixed receptacle moves toward−Y while mating, so the supported plug receives a−Y force; extraction is the opposite direction with an unknown maximum. At the connector array centre, the mount sees a 28 mm outward lever and 24 mm vertical lever:−2,688 N·mm about Z and+2,304 N·mm about X. A static two-point reaction gives a 134.4 N axial bolt couple and 115.2 N vertical shear couple in magnitude, before preload/contact details. The conservative one-upright calculation gives about 12.8 MPa bending and 19.0 MPa torsion, or 35.4 MPa equivalent by that simplified estimate. This is not a full frame stress solution, and the torsion approximation is not a guaranteed upper bound.

**The current printed frame is not structurally qualified or recommended for fabrication.** No directional, moisture-conditioned, long-term allowable has been assigned. A verified frame/contact model and material evidence, or a stronger section/material, are required before treating it as a practical build support. The manufacturer's minimum unmating force is not a maximum extraction load. Clear geometry alone cannot settle this design.
