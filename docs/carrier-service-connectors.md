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

The official [ST3215 CAD resource](https://docs.waveshare.com/ST3215_Servo/Resources-And-Documents) is retained privately as a conditional case reference. Its STEP root is named`SCS215 v5`; one of its eight solids is invalid, and the PCB model supplies only plain connector blocks, with no detailed cavities, contacts, latch, mating plug or cable. It cannot qualify the pan-servo disconnect. The carrier-side service connection should avoid requiring blind unplugging beneath the installed servo; its exact compatible termination and retained OEM lead must be established before that design is frozen.

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
