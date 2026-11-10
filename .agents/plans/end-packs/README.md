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

## Numeric implementation checkpoint — 2026-11-10

The first author slice adds pure envelope/placement calculations in the existing
`body_battery` owner; it does not yet switch the production body out of the bay.
The dated [AMKUS LAI-002 Rev05, page 8](https://device.report/m/ece13665cf944f3420373a08d01f8946493f8ec6b33ccaa41fbd18d8d414dc6d.pdf#page=8)
lists DCB609 at 137×97×91 mm and 1.45 kg. Its 2021 date and disagreement with
the existing DCB547-derived 138×87×97 mm remain explicit. DCB609 retains the
existing 1.565 kg conservative mass budget until weighing. DCB606's published
124×84×91 mm / 1.0 kg is an optional smaller example, not a requirement to
purchase it. Custom smaller outlines require independent mass and reject
unsupported interface/electrical fields. Selected Azocek holes, rails, latch
and ratings remain unmeasured/unverified.

Clearance calculations use the reference union 138×97×97 mm; this is not a
measured pack. The same fixed top/mating datum serves every profile. Front
rotation RY(−90°), rear RZ(180°)·RY(−90°) preserve proper rigid frames and map
the local rail axis to +Z at both ends. Downward insertion and +188 mm removal
are conditional reservations, with 50 mm vertical room after the conservative
pack clears the adapter envelope. They do not describe measured latch travel.

At the independent fixture belly plane −93.04 mm, 320 mm body and 3.175 mm
support stock, default pack bounds are X195.775..286.775 (mirrored at rear),
Y±48.5, Z−87.04..49.96 mm. The conservative union starts 5 mm above the belly;
the nominal pack starts 6 mm above it. Moving only the cameras upward inside
the body crosses current power/compute/lidar reservations, so camera relocation
needs an actual outward cradle and checks. Localized sit feet also need a
computed load path and new ground/fall evidence; old bay-pad acceptance does
not transfer.

The initial numeric test run retained one failure: a strictly-greater-than
assertion rejected the exactly 50 mm planned removal room (39 passed, one
failed). The corrected assertion requires that actual difference to equal
50 mm; geometry and travel were unchanged. These tests construct no native
solids. Native body/collection/sweep acceptance and current-consumer adoption
remain pending a frozen source and separately reviewed bounded run packet.

## Body integration candidate — 2026-11-10

The next source slice switches the existing `body_frame`/`body_layout` owners
to the end-pack geometry. It retires the old bay floor, side rails, doors and
crush-pad parts; it does not change a leg source, manufacturing original,
mounting datum or controlled height/torque limit. The one-bend 5052 holder uses
the existing belly end lands. Rigid printed sit frames share its body-side
M4×12 stack through 1.5 mm counterbored seats; the existing catalogue family
is retained, not replaced with invented fastener dimensions or an extra SKU.
Bought-adapter mounting and pack latch/secondary retention remain explicit
unresolved interfaces, rather than inferred connectivity holds.

The localized rigid feet plan for Z−228.5 mm at the existing 127 mm wheel /
101.5 mm leg-stop reference. Their nominal ground room is 83.5 mm at 185 mm
and 198.5 mm at 300 mm; the central belly clearance is a different quantity.
No old pad stroke, plateau, rebound law or drop pass is transferred. The
camera envelope moves upward/outward on an existing cradle owner, with screws
from inside into outside feet; actual native interference, cable/optical and
strength checks remain pending. These are source proposals, not accepted solids.

Current simulation generation requires a fresh explicit output outside the
checkout and preserves the recorded v2 rig. Its proposed rigid-foot stock
collision boxes omit screw/tool holes and are labelled conditional; they are
not exact contact geometry. [History protection](history-protection.json)
pins the old rig tree and pad reports. Old pad-lip/web tests are retired with
their removed component, while source/hash guards prevent their results being
reused as current qualification. Native tests must validate the new component.

Assembly source operations distinguish downward floor-tray placement, upward
belly/support placement, outward adapter reservations and common +188 mm pack
arrival. Leg operations and all historical guide files stay unchanged. The
recipe test's 162-name transition is explicitly a declaration derived from the
171-name archived inventory; it is not fresh native collection evidence. A
stale old inventory is rejected. No new collision exemption was added.

Numeric/output/history/preservation tests passed 56 cases (29 unrelated native
body cases deselected), and six kernel-free recipe controls passed. They
constructed no solids. A first native collection must use a clean immutable
source, the existing pinned producer/runtime, fresh isolated output and existing
detached fleet wrapper; compare all 80 old leg mesh hashes before adoption.
Capture failed/partial results without overwriting historical or manufacturing
files. Current source-bound figures/snapshots/consumer changes remain pending;
never relabel the old geometry as these new supports. No such native job has
been run or approved by this checkpoint.

## Original-byte producer boundary and pending acceptance

The first new collection must use `--emit-brep`: the STL and original BREP
payload are emitted from the same collected worldshape, with identity placement
and the original producer hash platform. Only the two already reviewed additive
producer changes from `a684eeca47118a5f38019441982be32fdc89c47c` / `542b9a40`
are ported. Their file bytes stay identical to that reviewed producer; no study
adapter, stored evidence or alternate geometry engine is imported. The body CAD
and simulation source stay byte-identical to `696666c7`. Help/import-safety and
same-object serialization-flow tests use explicit non-CAD doubles; they do not
establish native geometry equivalence. No STL-only collection is proposed.

The frozen `696666c7` CI also retained a separate failure in
[run 42866125306, job 130005097895](https://github.com/Valpatel/gyropup/actions/runs/42866125306/job/130005097895):
`package-fit-job.py` called `rs04_lug_checks.validate_receipt`, which rejected
`Source/context closure changed`. The receipt and closure were not restamped or
relaxed, and no retry was used. Review must identify the exact changed dependency
and distinguish historical printed-leg fit evidence from changed body/system
qualification before an acceptance fix is selected. Protected leg source/export
bytes still match; that fact alone does not settle this failing consumer.

## Consumer corrections awaiting review — 2026-11-10

The three source/caller blockers from the independent `3df450b2` review are
corrected in their existing owners. Quote `main()` uses `holder_part()` and
still quotes an unrelated bus bar without evaluating retired bay factories.
The v2 simulation CLI requires a fresh output root, passes it to the builder,
and consumes returned relative model/rig paths; scenarios, videos and body
evidence stay under that candidate. The direct wheel-curb caller has the same
per-model output contract. The historical pad-depth subprocess caller rejects
the current pad-less model before file reads or regeneration. Firmware and
leg-load callers only use existing wheel parameters or read reviewed models;
they are not direct v2 builders and their control limits remain unchanged.

The actual rig manifest writer derives eyes/camera datums from `body_shell`
source, separating the electrical board front from the decorative outer-face
bezel. Overall battery bounds and old fallback `SHELL_ITEMS` heights cannot
move them. Actual entry-point and writer controls use explicit unrelated
browser/CAD/solver doubles, changed sensor datums and changed outer extents.
They do not construct solids or establish optical/physical qualification.

[The strict fresh-fit proposal](fit-refresh-plan.md) preserves the unchanged
validator, failed original receipt and all printed-leg originals while setting
out genuine recomputation and separately reviewed packaging/CI ownership.
No fresh fit, native collection or pipeline has been launched by these fixes.

## Separately accepted collection and current preparation evidence

The [accepted266 collection](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6775564625)
contains224 parts, all80 protected leg mesh bytes unchanged. The separate
[current hip correspondence review](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6776726093)
accepted the actual56.5317s measurement, not current body engineering.
Its exact proof and separate acceptance are recorded here without changing
the measured producer, original printed parts or historical engineering flags.

The [current preparation plan](current-print-correspondence.md) and
[actual candidate consumer checks](current-print-consumer-checks.json) record
both L/R hip Prepare actions in Chrome and WebKit, actual STL/geometry-only3MF
downloads and readbacks, other-part pending state, and corrupt-project
rejection. These tests used an isolated candidate web root at520505f5; no
public guide asset was adopted. Historical322/40/8 remains failing, release
flags remain false and measurement sheets remain blank. Independent final
guide/adoption review and coherent CI ownership replacement remain pending.
