# Front/rear packs from the existing robot CAD

Issue [#193](https://github.com/Valpatel/gyropup/issues/193), resumed 2026-11-10.
The owner selects the chunky DCB609 20V/60V FLEXVOLT model, one pack dropping
into each end, with smaller-pack support. Keep the leg parts already being
printed unchanged. This plan accompanies implementation and testing; it is not
an accepted CAD result or a manufacturing release.

## Source and preservation boundary

The existing canonical chain is `body_battery` → `body_frame`/`body_layout` →
`robot_view.collect` → source-bound exports and the Robot/Combined guide
collection. Its belly enclosure is real current CAD. The present README,
build guide, fresh native collection and cad-agent homepage share the same
95 CAD inputs. No implemented end-pack branch was recovered.

[The baseline](baseline.json) retains the main source, five leg source hashes,
leg CAD/manufacturing trees and 80 L/R mesh hashes. Preserve the leg source,
manufacturing originals, hip datums, stance, travel and torque limits. Body
changes must fit those interfaces. Do not move the legs to make a battery fit.
Old studies, guides and recorded simulations keep their original source and
qualification. Native jobs 261–263 describe this previous design.

## Extend the existing CAD

1. Keep pack choice, dimensions, mass, mounting datum and evidence status in
   `hardware/cad/body/body_battery.py` or its existing catalogue input. DCB609
   is the default planning envelope. Smaller packs use the same explicit
   adapter datum, not a scaled rail, latch or mounting pattern. Reject
   nonfinite/negative envelopes and variants exceeding the supported envelope.
2. Define front/rear vertical slide transforms in the robot frame. The pack
   interface faces the body; insertion is down and removal is up. Position
   each assembled envelope outside its end wall and above the belly's lower
   plane. Model the full insertion/removal and hand-access reservation as
   conditional geometry. Check cameras/lidar and existing moving legs.
3. Replace the belly enclosure through the existing frame/layout/joint
   producers, including BOM and service descriptions. Mount/retention/skid
   design must have an explicit load path. The old bay floor and its validated
   pad load case cannot stand in for a new support. Unknown bought adapter
   holes and latch geometry remain unknown, not guessed fabrication features.
4. Carry the owner's Azocek ASIN B0CDGR4Y8K reference correctly. The old
   Terrafirma drawing is not its dimensional evidence. Keep electrical topology
   and operating limits separate from appearance; the pack's 60V branding is
   not permission to change the robot supply. Future charging/hot-swap work
   remains separate.

Current pack dimensions are explicitly an approximation derived from another
DeWalt pack; exact DCB609/adapter mating data are still missing. Overall size
research must distinguish product from shipping dimensions and retain
disagreements. A WIP placement picture does not establish fit or strength.

## One latest model, multiple representations

Extend the existing collection/export contract rather than adding a second
robot implementation. Capture one accepted CAD input closure, then bind the
latest Robot/Combined guides, README model and cad-agent homepage import to
that source. Regenerate real meshes/renders; never rewrite their revision
labels to make old geometry appear current.

The browser Sim currently shares an archived interim body between `current`
and `recorded` modes. Keep recorded geometry and trajectories together, but
make current presentation consume the canonical current body collection.
Preserve the existing leg and turret scene ownership, units and kinematics.
The legacy custom designer's procedural body must not claim to be current
CAD: route its current-CAD presentation through the same source contract while
retaining explicitly conceptual editing where supported. Extend existing
manifests/selectors and validators, not a new independent latest registry.

## Testing and adoption

| Concern | Required evidence and negative control |
| --- | --- |
| Pack variants | DCB609 default and a smaller explicit envelope share the mounting datum; oversize/nonfinite values fail; no scaled interface. |
| Physical placement | Actual CAD bounds and source-derived transforms prove end-wall positions, upward removal/downward insertion and no belly battery enclosure. A reversed transform fails. |
| Printed legs | Unchanged leg source/manufacturing tree and all 80 collected L/R meshes at the same stance. A changed mesh or datum fails adoption. |
| Clearances | Native checks against body, legs/wheels through existing stops, removal path, ground at sit/185/300 mm, cameras/lidar and service volumes. Report unresolved contact; do not add arbitrary exemptions. |
| Supports and mass | New support geometry, mass/CoM/inertia and applicable impact/fall cases. Historical pad results remain historical. Unknown retention fit stays open. |
| Source coherence | Every latest consumer identifies the accepted CAD input closure and actual geometry hashes; an old body, mixed snapshot or changed input fails. Historical selection still opens its original model. |
| Renderer | Actual world vertices/landmarks agree at home and moving poses; fixed body parts stay fixed. Wrong frame, scale, parent and current/recorded mixing fail. |
| Reader experience | Desktop/mobile real browsers show front/rear packs in build, current Sim, README and cad-agent homepage; leg appearance/motion unchanged; no missing parts or page errors. |

Use existing generator, motion-trace, body, guide, privacy and browser harnesses.
Build and check ordinary consumers before broad tests. Expensive regeneration
or physics uses a source-pinned, bounded detached compute job with independently
reviewed command and a retrievable result; no full-workstation pipeline.

Normal review and dev→main publication follow genuine adopted outputs. Verify
actual public versions and model bytes on gyropup.com and cad-agent.valpatel.com.
Keep issue #193 open for any remaining physical interface/retention/drop
acceptance; a visual WIP slice must not close the full mechanical issue.
