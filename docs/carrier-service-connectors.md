# Carrier stator and pan-servo service connections

Work in progress for [issue 85](https://github.com/Valpatel/gyropup/issues/85), continuing the removable carrier in [issue 66](https://github.com/Valpatel/gyropup/issues/66). This page will bind the actual connectors, cable exits and parking positions to the complete module service check. It is not fabrication approval.

The [C2 candidate](base-board-interfaces.md) already requires C3 and the pan-servo connection to be unplugged while the carrier remains mechanically retained. Their real release and parked-tail geometry is still absent. A green C2 reservation check does not cover these connections.

| Interface | Current project selection | Evidence to establish before a service claim |
| --- | --- | --- |
| C3, module side | Molex 43020-1200 housing, twelve 43031-0001 male terminals, 24 AWG board tails | Exact cavity/view map, housing and contact geometry, installed pose, free wire exit, latch/grip access and module-side retention |
| C3, fixed stator side | Molex 43025-1200 housing, twelve 43030-0010 female terminals on the slip ring's own 28 AWG leads | Actual insulation diameter, usable lead length from the installed ring exit, housing/contact geometry, unmating travel and retained parked route |
| Pan servo | Catalog `feetech-sts3215-c018-12v`, Waveshare SKU22414; the supplied three-pin lead | Exact selected variant, connector manufacturer/series or documented compatibility, cavity polarity/view, lead length/gauge/diameter, release direction and parking |

The legacy wiring table calls C3's board tails 60 mm long and its ring leads 250 mm. Those lengths are not yet demonstrated retained service slack. The existing “Molex 5264-type” servo description does not by itself identify a particular housing, terminal, mating header or crimp tool.

The next geometry check will retain the PCB, carrier, their four PCB screws and four inserts as one rigid module with exact member identities. External carrier retainers, base inserts, servo, stator connection, fixed harness and any removed bumper hardware will retain their separate identities and explicit service order. Conditional removal prerequisites will be labelled as such; they must not silently become proved teardown operations.

Before new full-service evidence is generated, the historical service checker must adopt complete input provenance and reviewed topology/uncertainty predicates. It must reject missing or wrong manufacturer variants, inaccessible latch/grip space, still-mated interfaces, inadequate retained tails and parked cables that obstruct withdrawal. Unknown manufacturer bend radius, insulation or actual lead data remains unknown rather than becoming a guessed clearance.

Manufacturer CAD is kept privately with source URL/hash and normalized-frame receipts. Public independently authored representations remain visibly labelled; no reservation is promoted to complete hardware. The separate input-protection circuit candidate has no allocated added-board envelope here and does not qualify the current electrical interface.
