# PAN carrier mechanical envelope — contract proposal

**2026-10-29; not frozen, not a fit or fabrication approval.** This read-only
investigation uses engineering `fa459d09aebe416be21edc1c11ceb37fe41c3f7e`,
including the reviewed PR86 C3 support. No CAD, circuit, vendor geometry or
generated receipt changed. The electrical and mechanical authors must accept a
complete component, terminal, thermal and service contract before generating a
new candidate. [Issue96](https://github.com/Valpatel/gyropup/issues/96) tracks that
work; [issue85](https://github.com/Valpatel/gyropup/issues/85) still tracks the
incomplete carrier service.

The preferred architecture retains the complete PAN electronics with the
removable carrier. The existing control PCB remains occupied. A separately fixed
powered board would add a service boundary and is not the proposal here. The
conditional CJT servo connector is unselected; neither its current rating nor
the OEM lead/interface has been qualified for the electrical load contract.

## Coordinates and existing constraints

All coordinates below are millimetres in turret frame T: the mounting face is
Z=0, the carrier is on +X, and its existing outward service direction is +X.
The +45 mm illustration is a finite removal endpoint to investigate, not a new
whole-module sweep result. The robot bumper is removed before carrier service;
the pan base, bearing, clamp and servo remain installed.

| Item | Existing occupied region or requirement | Source and limitation |
| --- | --- | --- |
| Control PCB | X46.4..48, Y−25.4..25.4, Z6..36; four original mounting holes remain | `cad/turret_base_board.py:pcb`, `cad/turret_boards.py:BOARDS['base']`; occupied, not spare protection-board area |
| Control components | Seven individually placed footprint/package envelopes on the inward −X face; legacy U2 X36.9..46.4, Y−6.4..19, Z8.3..33.7 | `turret_base_board.py:components`; envelopes omit actual solder and wires; legacy U2 is not the new protected converter layout |
| Carrier | X48..56, Y−35..35, Z5.5..37.5, including inward PCB bosses | PR86 `support-candidate.json`, `valid:carrier`; original PCB/retainer stacks must remain |
| C3 support | X56..93, Y−27..19, Z6..56 | Same receipt, `valid:support`; its approximately 35.4 MPa section screen has no accepted allowable or strength result; **not recommended for fabrication** |
| Fixed base foot/skirt | Foot radius 72, Z0..5; skirt radius 69.5..72, Z0..18 | `cad/turret.py:Geo`, `pan_base`; carrier opening removes skirt only in Y−35.25..35.25 and Z5.25..37.75, per `service_base` |
| Central housing/bearing | Housing radius 35.5 below Z38; bearing seat outside radius 31 with outer radius 37, Z38..47, plus clamp ears | `pan_base`; preserve the actual source geometry, not just its bounding cylinder |
| Clamp and moving ring | Clamp starts Z47 and is 3.175 thick; ring gear starts Z53, upper face Z69 | `pan_clamp`, `Geo.turntable_z`; these heights are useful first screens, not proof of complete upper-head motion clearance |
| Pan servo | Shaft axis at X−52.65,Y0; body width 24.7, Z17..49, with horn/estimated plug reservations | `Geo.servo_pan_xy`, `servo_envelope`; body/plug representation is not exact installed lead evidence |
| Fixed C2 saddle | X50..58,Y37..42,Z4.99..12 | `turret_base_board.py:fixed_harness_saddle`; its tie and wire fit remain unqualified |
| Robot bumper | Main ring radius 82..86 and lugs to 87.5, Z6..20 | `bumper_ring`; this does **not** bound screw heads, washers, cables or tools |
| +Y bumper fastener | Axis approximately X0, Y84; M3 socket head Ø5.5×3 over a Ø9 washer0.7..0.9 thick | `BUMPER_BOLT_R`, `BUMPER_TABS`, catalog91116A120/91290A123; at the nominalZ20 seat, washer/head can reachZ23.9. Preserve access to remove it before the carrier. Actual installed hardware still needs checking. |
| Original retainer tools | Four Ø6 shaft reservations, X59.01..119 at Y±31,Z9/33 | PR86 support checker; these are tested shaft corridors, not a complete screwdriver/hand envelope |
| C3 support screw tools | Two Ø6 shaft reservations, X61.01..121.01 at Y±10,Z10 | Same checker; bench assembly retains nuts/screws with the module |

The central housing, base anchors, original PCB fasteners and protected original
mount regions are not available to cut away for this packaging exercise.
The new support's two nuts can only be replaced after removing the PCB on the
bench. That prerequisite remains unchanged.

## Why the first shelf and the low-only alternative are insufficient

The reviewed C3 source-half path is +16Y to unplug, +43Y total outboard, then
−30X to park. Its exact housing bounding-box records give:

| C3 item at the existing park | X | Y | Z |
| --- | --- | --- | --- |
| Housing | 49.86..60.71 | 36.88..50.88 | 24.58..43.43 |
| Full-array straight wire exit | 52.15..55.85 | 50.88..69.98 | 24.925..43.075 |

The second row is the source-derived 19.1 mm unbiased exit from
PS-43045-001 revision R for 10–16 circuits, translated with the housing. It is
**not** a minimum bend radius or an actual installed wire model. The full-array
rectangle comes from the existing support checker; the source-side crimp,
insulation, bundle, bend and keeper are still incomplete.

A proposed retained shelf around X4..48,Y53..93 can avoid the parked housing
while seated, but its +X removal sweep crosses the mandatory wire exit. Moving
only beyond Y52.88 is therefore insufficient. Keeping the existing park and a
2 mm design separation would require tall electronics beyond Y71.98, before
allowing any real bend or return route. That is an outward size increase, not
free space established by the earlier receipt.

A low-only shelf below Z23.58 also does not make the complete electronics fit.
For material at |Y|>35.25 initially inside the skirt, straight +X withdrawal
crosses the fixed radius 69.5..72 skirt up to Z18. It remains after bumper
removal. A provisional 1 mm separation above that skirt and the Z23.58 ceiling
leave **Z19..23.58, only 4.58 mm total** for PCB, solder, components, support and
insulation. The existing converter and capacitor body (11.5 mm nominal;
electrical author now records 12.5 mm maximum, with vent/mounting gaps additional)
cannot simply be
placed in that total stack. An inward low component may be seated without
interference yet fail removal. A different compound removal motion or an
entirely external region would need new evidence; neither is assumed here.

These are source-derived interval conflicts, not newly run BREP collisions.
They are sufficient to reject using either simple bounding-box idea as a
complete service contract.

## One finite candidate to negotiate

Investigate a **far-+Y retained electronics region coupled to a quarter-turned
C3 parking pose**. The following bounds are proposed design budgets, not
available-volume claims or manufacturer minimum sizes:

| Zone | Proposed T-frame bounds | Intended role and condition |
| --- | --- | --- |
| Complete added electronics/thermal assembly | X4..48,Y53..93,Z23..41:44×40×18 overall | Includes PCB, components, solder, mounts, insulation and any heat spreader. The18 mm height is an initial electrical planning ceiling, not a verified stack. Actual inventory and PCB contour are still being assigned. |
| Low transfer/attachment zone | X43..56,Y33..56,Z21..23.58 | Connection to the carrier's existing +Y side rail and onward to the added region; no support, holes or section is designed yet. Keep the original retainer corridors and fixed saddle clear. |
| Proposed PCB plane within the overall zone | Undecided | Freeze thickness, actual copper/land layout, each side's height and lead/solder projection jointly. Do not allocate the full 18 mm both above and below a board. |
| Terminals and strain relief | Unallocated within the complete inventory | Real BUS/GND/PAN output and signal terminations, their tool/exit zones, ties and guards must be accounted for before freezing the contour. They cannot be placed in the legacy 2.5×10.2 mm pad placeholder. |

The full region extends to Y93 versus the main bumper's Y86 and to radial 104.657
at its outer corner versus the bumper lugs' 87.5. It is a deliberate packaging
extension requiring support, protection and robot-envelope review. It is not a
drop-in board within the old base. X≥4 nominally leaves 1.25 mm beside the +Y
bumper screw head and 1 mm beside a Ø6 straight tool shaft atX0, Y84; real tool
and hand access, washer placement and removing the ring still need validation.
The region's Z23 bottom clears the bare bumper body by 3 mm, but this observation
does not substitute for the head/washer check.

AtZ≤41 the proposed electronics remain 6 mm below the clamp's bottom and 12 mm
below the ring gear's bottom. Y≥53 separates them from the current carrier,
support, C2 released-body reservations and fixed saddle. These interval
separations are only the seated screen. The proposed +45X removal screen for
this region spans X4..93,Y53..93,Z23..41. No continuous module sweep, motion
of the upper head, carrying strength or service grip has passed for it.

### Proposed C3 park orientation

At the existing outboard position, rotate the fixed housing and its attached
contacts/straight exits **90° clockwise when viewed from +Z**, about
T=(85.285,43.88,34). Then translate −30X. The pivot is the exact housing's XY
bounding-box centre at outboard; Z34 is the existing interface centre and does
not affect the planar transform. This is a prescribed candidate transform,
not evidence that a flexible harness can perform it.

| Candidate parked feature after the quarter turn | X | Y | Z |
| --- | --- | --- | --- |
| Exact housing bounding box transformed analytically | 48.285..62.285 | 38.455..49.305 | 24.58..43.43 |
| Existing full-array19.1 mm straight-exit reservation | 62.285..81.385 | 43.315..47.015 | 24.925..43.075 |

The wire exit now points+X. The proposed electronics startY53, leaving 3.695 mm
to the housing's Y extent and 5.985 mm to that exit rectangle throughout the
subsequent +X electronics removal. The low transfer zone remains 1 mm below
the housing and 1.345 mm below the straight-exit reservation. These are design
separations before tolerances, print distortion, wire flex and keeper geometry.

The clockwise choice matters: turning the long exit through the−X side would
bring it toward the released C2 source bodies. A clockwise quarter turn keeps
the existing exit rectangle atX≥82.15 during the turn. The housing's rotation
radius is 8.8562 mm about that pivot; its circular enclosure starts Y35.0239,
above the current support's Y19 maximum. The subsequent housing/exit
translation has Y≥38.455/43.315 respectively, above the current released C2
bodies. This provides a concrete motion to test, **not** a collision result for
all attached wires, contacts and other neighbours. A real parked keeper and
latch access are unallocated. Rotating the housing changes the latch direction
from+X toward−Y; the keeper must not load or hide the latch.

For the existing fixed anchor candidate(40,−35.5,13), the transformed rear-exit
centre is(62.285,45.165,34), and the end of the required straight exit is
(81.385,45.165,34). The necessary length bound at park becomes 112.1621 mm.
Over the quarter turn, maximizing the distance from this free-exit end to the
anchor gives 138.4820 mm including the 19.1 mm straight length, leaving only
6.5180 mm under the existing 145 mm retained-length proposal. The maximum occurs
inside the rotation, so checking endpoints alone is insufficient. This is still
only a lower bound: it includes no wire bend-radius penalty, abrasion path,
crimp compliance, keeper or tolerances. It **cannot** authorize 145 mm cut leads
or claim service slack. Extending the same point-anchor calculation to all
corners of the full-array free-exit rectangle gives **140.5588 mm**, leaving
only 4.4412 mm. The worst corner occurs at an interior clockwise angle of about
36.55°. This is a conservative rectangle/point-anchor length screen, not actual
individual wire lengths; the anchor's real bundle cross-section remains unknown.
The real route may require a different length/anchor.

## Thermal and terminal obligations before freezing

The IPB200N25N3G source's 40×40 mm vertical FR4/6 cm² copper characterization is
not a minimum board outline and is not the cooling behavior of this proposed
horizontal assembly. Even a 40×40 outline inside the 44×40 planning region would
not supply its specified copper automatically: clearances, component lands,
electrical isolation, fasteners and connector zones consume area. An underside
plate or conductive support must be represented in the same18 mm total stack,
with its electrical isolation, contact, retention and service motion. Printed
PA6-CF support is not credited as a heat sink.

The electrical author's preliminary inventory is 38 protection/converter parts
(28 retained after removing the series-D1 approach, plus the full 10-part
LTC4359 reference network), with nine existing control-board parts and harness
terminations additional. The final inventory must include the full reference
network, cutoff/current-sense/EN components, actual converter and terminals,
not just controller IC bodies. A 44×40 board is not asserted to hold that
inventory on one side. The existing NE555/control functions remain in
their occupied board region. The BUS feed to C3 remains separate from protected
PAN_INPUT; board convenience cannot merge them. Proposed source/return junction
hardware and servo disconnection remain unallocated. Real connector pin
identities, crimp or solder access, current/gauge pairing, insulation diameter,
unbiased exits and strain relief are prerequisites to a freeze.

No minimum bend radii, OEM servo lead dimensions or physical solder/termination
stack have been invented. Copper thickness/area, enclosure ambient, converter
and clamp losses, heat-spreader dimensions, allowable contact temperature and
printed-support thermal exposure must be named assumptions or unresolved fields.
The existing unqualified C3 support strength stays visible alongside any new
mounting load; adding electronics cannot inherit strength from a geometry pass.

## Required next evidence

1. Electrical author returns the complete exact component/land and terminal
   inventory, a practical layout/thermal assumption, actual PCB thickness and
   assembled per-side heights. Jointly accept or revise the single contour and
   clockwise C3 park proposal above before any CAD/circuit generation.
2. Source-bound BREP checks must include actual base/skirt, existing PCB and all
   retained hardware, bearing/clamp/servo, C3 support, bumper fasteners and real
   connector parts. Check seated, unplugged, quarter-turn, parked and every
   continuous insertion/removal segment with exact member identities. The
   released rigid-module API must replace the historical fused service checker
   before a whole-module service claim.
3. Include new PCB mounts/retention, old/new tools, solder access, fixed and
   retained harness anchors, keeper, strain relief, complete free exits and
   routed slack. Check removal prerequisites rather than silently deleting
   obstructing parts. Required unresolved dimensions must fail readiness.
4. Meaningful negatives: unchanged+Y C3 exits block the initial shelf removal;
   a low inward component below the skirt top blocks straight removal; a
   protruding attached terminal/fastener blocks the module; blocked retainer and
   bumper-tool access fail; omission or incorrect orientation of a retained
   member fails inventory. A housing-only pass must not count as a wired pass.
5. Independent review of the frozen source and actual imported assembly precedes
   integration. Coupon measurements, thermal/strength qualification, electrical
   clamp/startup/regeneration tests and physical assembly/service remain later
   explicit gates. No purchases or energized test is implied.

## Read-only evidence identity

The arithmetic above uses the existing receipt bounds and explicit coordinate
transforms; Python standard-library calculations on 2026-10-29 gave the values
shown. No kernel or new geometry was run. Reproduce the key length screen with:

```python
from math import hypot
pivot = (85.285, 43.88)
anchor = (40.0, -35.5, 13.0)
radius = hypot(84.0 - pivot[0], 69.98 - pivot[1])
# The radial alignment with pivot-anchor occurs within the clockwise quarter turn.
maximum = 19.1 + hypot(hypot(pivot[0]-anchor[0], pivot[1]-anchor[1]) + radius, 34-anchor[2])
assert abs(maximum - 138.48195538027392) < 1e-9
# Full-array corner envelope, still using the same unqualified point anchor:
outer_radius = hypot(82.15-pivot[0], 69.98-pivot[1])
array_maximum = 19.1 + hypot(hypot(pivot[0]-anchor[0], pivot[1]-anchor[1]) + outer_radius, 43.075-anchor[2])
assert abs(array_maximum - 140.5588235466063) < 1e-9
```

| Read input | SHA256 at this investigation |
| --- | --- |
| `cad/turret.py` | `76d4fa676c3181e1d3bf0c623cefa75e420a3b2ed90057320d038c8b7aa41534` |
| `cad/turret_base_board.py` | `153e49871e0a3359478cd34a50daf7e44f4497970097475c829dbbcdacda90ba` |
| `cad/turret_boards.py` | `c7a115d2fe3cefddf46b0dd521e21076e1f7721235df3e7bd22fadb6e165707b` |
| `cad/turret_carrier_support.py` | `ce4badb9b9314fc3a03ab187c5b2ba21b1a8a865c6c38a4637221071176110de` |
| `research/carrier-service-connectors/external-pose.json` | `d684aaad772e390b68fc17e34ae6bb087b23a62a57e7a77dcaa5d7a78a98867d` |
| `research/carrier-service-connectors/support-candidate.json` | `0abb60d59e186ebfbb7c4ffaaf9bad3a058b548959daa0da40f13a1cabfc209f` |
| `tools/check-carrier-connector-support.py` | `ddaef1821bb40721ef7f91f02e04b697c7fbc754829ae1eff17647329345838a` |

These identify the read inputs; they are not a replacement for the existing full
CAD/config/catalog dependency closure or an executable packaging acceptance
receipt. The integrated review evidence remains attached to PR86. This document
adds a proposed contract and two rejected space assumptions, not new readiness.
