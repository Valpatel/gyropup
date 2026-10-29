# Pin and interface contract

This is a circuit candidate; none of its reference designators replace the existing carrier BOM yet. `U1` in this directory is the cutoff controller (the carrier's existing NE555 is outside this sheet). The converter retains the functional name `U2` for clarity.

## Manufacturer pins

[LTC4368 rev C p2, MS10 top view](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf):

| Pin | Function | Candidate net |
|---:|---|---|
| 1 | VIN | BUS_HEAD_FUSED |
| 2 | UV | UV_DIV |
| 3 | OV | OV_DIV |
| 4 | RETRY | GND (forward overcurrent latch) |
| 5 | GND | GND |
| 6 | SHDN | SHDN_DIV |
| 7 | FAULT | Explicit NC, no indicator or logic connection |
| 8 | VOUT | PAN_INPUT, after sense resistor |
| 9 | SENSE | SENSE_HI, before sense resistor |
| 10 | GATE | GATE, directly both MOSFET gates |

[TI CSD19531Q5A rev B p1 top view](https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf): pins1–3 SOURCE, pin4 GATE, pins5–8 DRAIN. The exposed drain metal is drain, not an invented ninth terminal. Each of the eight leads is represented in the netlist. Q1 drain is BUS_HEAD_FUSED; Q2 drain is SENSE_HI; **both sources join COMMON_SOURCE**. Intrinsic diodes point from that common source toward the separate drains. The two gates share U1.10 directly. R8 belongs only in the branch to C2; it does not isolate the gates from the fast pull-down.

## Pololu module: project-assigned physical pad IDs

Pololu publishes signal names, not pad numbers. This schematic assigns **A/B IDs solely for traceability**; these are not manufacturer numbers or a released footprint. Look from the **component/top side**, terminal rows along the bottom edge, large capacitors at the top, as in the [manufacturer top photo](https://a.pololu-files.com/picture/0J13509.1200.jpg?92a6d5d0b8976c2542720c3daed1685a). A is the inner row, B the edge row; columns1–6 run left to right. The [bottom photo](https://a.pololu-files.com/picture/0J13510.1200.jpg?07698eb9b3d80e21445afe4b491b775a) is mirrored horizontally and supplies VIN/VRP labels. The [18 June2025 dimension drawing](https://www.pololu.com/file/0J2180/d42v55fx-step-down-voltage-regulators-dimensions.pdf) confirms two rows of six holes on 2.54 mm spacing.

| Top-side column | Inner A | Edge B | Candidate connection |
|---:|---|---|---|
| 1 | VOUT | VOUT | 12V_PAN, both |
| 2 | GND | GND | GND, both |
| 3 | GND | GND | GND, both |
| 4 | VIN | VIN | PAN_INPUT, both |
| 5 | VRP | VRP | Both NC: do not bypass the module's reverse-protection input |
| 6 | PG | EN | Both NC; different functions, **not duplicated** |

[Manufacturer connection functions](https://www.pololu.com/product/5577): EN has an internal1 MΩ pullup to VIN and may remain open; PG is open drain and requires an external pullup if used. Its typical high-output fault threshold is10% above nominal, so PG cannot enforce a12.6 V maximum. Four ground pads must not collapse to two omitted physical pads. Continuity and board revision still need checking on an actual received module before fabrication.

Stacked duplicate power leads are represented as passive pins at the same electrical connection, with the first pin carrying the power input/output type. Hidden **power** pins would create implicit global nets named VIN/VOUT in KiCad; they are deliberately avoided. Hidden passive leads remain enumerated in the exported netlist and checked individually.

## Existing carrier boundaries (not newly selected connectors)

Contract from PR67 `8b86e7f`, geometry/pin map unchanged at author checkpoint `36aa696`:

| Existing interface | Net assignment | Candidate effect |
|---|---|---|
| C2-P XT30U-F.G.Y source / -M.G.Y module | + BUS_HEAD_FUSED; − GND | Tap only U2 feed. Whole-head10 A fuse remains upstream. |
| C2-S43020-0400/43025-0400 pin1 | CAN_H: DT12.5 ↔ C3.5 | Bypasses this sheet |
| C2-S pin2 | CAN_L: DT12.6 ↔ C3.6 | Bypasses this sheet |
| C2-S pin3 | SAFETY_A:12V_PAN → existing F4 → DT12.7 | Supply may disappear/recover; no arming decision here |
| C2-S pin4 | SAFETY_B: DT12.8 → NE555 pins8/4 | Existing pendant return; backfeed must be reviewed |
| C3 pins1,2,11 | Shared BUS_HEAD_FUSED | **Never PAN_INPUT** |
| C3 pins3,4,12 | GND | Shared return |
| C3 pins5,6 | CAN_H,CAN_L | Bypass |
| C3 pins7,8 | Pulse+, pulse−→GND | Existing circuit outside sheet |
| C3 pins9,10 | PAN TTL, SIG_GND | Existing signal interface; unpowered injection unresolved |
| PAN servo own3-pin lead | Voltage after existing F1, GND, TTL | Cavity numbering unverified; no invented numbered connector |

External solder/interconnect nodes are BUS_HEAD_FUSED, GND and12V_PAN; SHDN_DIV is a candidate service/reset node only. No additional physical connector, test-point hardware or switch is selected by this schematic. A reset requires a reviewed means to ground SHDN then release it; no live manual procedure is authorized. Service removal still requires upstream isolation and residual-energy verification.
