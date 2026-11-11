# One current CAD presentation, separate recorded models

Draft implementation/action plan,2026-11-10. No new CAD, projection, browser or
poster run is authorized by this document. PR287 remains WIP. Existing native
collection266 and the current hip correspondence retain their original producer
identities. The current consumer review at25c passed independently; normal dev
composition is44eb58ea, including dev99a/PR286. Both conflict resolutions kept
the union of lessons and test imports. Hardware, firmware, measured producer,
sampler and historical validator bytes stayed unchanged; current6/data9/recipe7
controls passed. Source/action review precedes the next significant capture.

## Current consumer inventory

| Consumer | Actual source today | Required current adoption |
| --- | --- | --- |
| README/current-design SVG | `readme_design.py`, old scene/receipt versus new config | Fresh collection-bound projection using existing shared projection/rendering; no restamp |
| Landing interactive hero | `landing.js` → `buildRobotV2` | Current complete body/frame/sensor presentation; existing poster hook recaptured separately |
| Landing static fallback | `robot-poster.png` | Exact same accepted current hero pose/geometry, before fallback is advertised as current |
| Play v2 live/inspection | `sim.js` → `buildRobotV2` | Current body, physical module frames, mounting/effect anchors and current-source identity |
| Play recorded runs | Archived v2 rig/qpos, lazily loaded recorded turret | Preserve entire old body/leg/turret/sensor/pose/mass context; no new physics claim |
| Legacy v1/configurable renderer | `robot3d.js`/`cadrig.js` | Keep explicitly legacy/conceptual; do not substitute a five-bar body into a serial-leg design |
| Build model/assembly | Accepted266 collection plus existing guide exporter | Compose updated recipes/286 UI, retain old snapshots, independently accept new guide artifacts |
| Build Prepare | Accepted current hip correspondence + original geometry-only3MF | Preserve exact L/R feature, current95/full historical contracts and unrelated pending parts |
| Build buying/printing tables | Old `exports/body/{body,bom,print-plan}.json` | Stop presenting old bay files/quantities as current; source-bound current metadata or explicit historical/pending ownership |
| Progress/Design Notes | Old body mass/print reports and engineering studies | Keep recorded evidence dated and false readiness; do not infer new mass/fit/drop results from display meshes |
| cad-agent current example/model528 | Root-owned consumer | Same accepted266 CAD-mm/Z-up collection/model identity through existing reusable viewer kit |

There is no live standalone configurable-editor entry in this source tree:
`sim.fromDesigner` is null and selectable designs are v2, explicitly legacy v1
and turret box. The `@designer` branch is unreachable through that selector.
Do not create a new editor/framework to repair an obsolete route. Any separately
identified current editor must use a product adapter to the same bound current
model; hypothetical/user-edited variants remain visibly conceptual until bound.

## Why replacing only the body is insufficient

The archived rig uses module y-offset82.3mm and height range150..375mm. Current
accepted CAD uses102.5498mm and the already-existing185..375 current command
range. Archived turret pan is(-54.65,0,216)mm; current TM is(-40,0,246)mm.
Eyes, camera and light effects currently come from the archived sensor map.
Those recorded values must remain untouched for recorded playback, but must
not drive a newly displayed current body.

The archived right-leg renderer reflects geometry acrossY. Actual current
right modules rotate180degrees aboutZ; the accepted native module reference
and current hip correspondence retain that proper rotation. Non-home right
joint motion must be checked, not inferred from a symmetric home screenshot.
`fivebar.STATIC` is a collision-pair optimization, not a joint-ownership oracle:
it includes adapters even though `assembly` rotates them with upper links.

The effective collection includes the existing D69 wheel override: actual tyre
X span254mm and width64mm, nominal radius127mm. Do not substitute the isolated
BotWheel default or half a sampled curved Z extent. The verified override
[provenance lesson](../../inbox/2026-11-10-collection-geometry-needs-effective-runtime-parameters.md)
records this correction; no wheel/clearance/source value was changed.

## Proposed bounded extension of existing capabilities

### 1. Bind current presentation to accepted collection266

Use its224 actual world meshes and original collection hash. Require complete
current95 membership/hashes, native source/runtime and all80 protected leg
mesh identities. Do not construct another body CAD model or reuse an old
same-name shape as equivalent. Keep current consumer conversion provenance
separate from native execution3a408919 and measured implementation3a6b0cd9.

Extend the existing product export/adapter contracts, not the generic toolkit
UI: `robot_v2.js`/`current_turret.js`, existing shared data/mesh loaders, stage
and assembly viewer remain the owners. Use the existing hash-checking asset
reader where available; a failed current part must produce a retryable failure,
not a silently substituted archived body. Product-specific part/joint/source
mapping stays in Gyropup; generic loading, tracing and controls stay cad-agent.

Current stationary body geometry is directly available as82 non-L/R/non-turret
parts. Current fixed and moving leg parts need an explicit complete ownership
map from `fivebar.assembly`, `link_frames`, `bought_parts` and `screw_groups`.
Keep motor housings/hip supports stationary, adapters on their upper links and
the physical right-module transform intact. Reuse the existing five-bar scene
graph and solver; do not add another kinematics engine.

Grouped `screws_links`/`screws_outputs` span both motor joints. They cannot be
assigned as one rigid mesh to one joint. A pure triangle partition is possible
only with source-derived owner regions, no straddling/unassigned triangles,
and exact re-union/byte/landmark evidence. Treat ambiguous partitions as unknown,
not missing invisible hardware. If a complete mapping cannot be established
from these actual bytes, propose one bounded existing joint-local export as a
separate action; do not silently omit parts or launch a full physics pipeline.

### 2. Extend the existing current/recorded switch coherently

Prefer distinct current/recorded body-and-leg holder trees under the existing
free-body parent, extending the existing turret/attachment presentation switch.
Current uses canonical world→joint frames and current sensor/TM anchors;
recorded retains its original mirrored rig, qpos layout, mount map and metadata.
Current and recorded frame conventions must never be mixed within one pose.
Apply a completed presentation change atomically, retain stale-load request
guards, and preserve the usable current model when an archived fetch fails.

Rebind eyes/bezel/screens, headlights, FOV origin, turret base/muzzle and camera
framing from current source datums checked against266 mesh geometry. Current
mass/COM/dynamic readouts must be explicitly unknown or separately bound
planning data. Keep archived physics mass/limits with recorded runs. Changing
presentation does not rerun physics, retune firmware or qualify motion/clearance.

### 3. Reuse collection triangles for the README illustration

The existing projection config uses tolerance0.25/angular0.3, the same declared
tessellation parameters as266. A small explicit collection-extraction entry
in `readme_design.py` can validate and pass those actual STL triangles into
the unchanged shared `mesh_topology`/`group_drawing` and motif renderer. Keep
far_leg/body/turret/near_leg grouping and existing role rules.

Record the collection/raw mesh hashes, native runtime, conversion/runtime/tool
hashes and a new collection-extraction key/schema. Do not claim a new CadQuery
construction or force the old scene to match `extract_key`. Grouped projection
may still be expensive; freeze a separate bounded compute action before running
it. Preserve old successful/failing scene receipts. Inspect current SVG for both
packs/supports, old-bay absence, preserved legs and no implied engineering pass.

### 4. Finish Build/CI and secondary metadata together

Use only accepted current tracked collection/meshes for mandatory current
mapper/exporter checks; no private scratch dependency in CI or site generation.
Keep the full actual historical archive positive, default-current stale
negative, current-code adversarial controls and accepted current consumer
positive mandatory together. The protected checker/packager/default source
guard and historical receipts stay unchanged. Historical snapshots are checked
as historical artifacts, not regenerated with changed current source and called
identical. No broad `--pure` replacement without these real assertions.

Current body buying/print/mass metadata still includes old bay rows. Reconcile
through existing owners: report only current source-bound quantities/files;
mark unmeasured Azocek retention and new holder/foot fabrication pending.
Do not overwrite printed-leg originals or inherit old pad/drop qualification.
If current engineering/mass outputs need native recomputation, prepare a
separate narrow action; collection bounds alone cannot supply those results.

## Required independent validation before adoption

- Apply cad-motion-validation: inventory every joint/component/anchor and source
  owner, use at least four noncoplanar actual mesh landmarks, and compare actual
  renderer world vertices converted back to robot-mm with independent source
  mechanical intent via shared `cadagent.motion_trace`.
- Current home at300mm must match266 actual world vertices and source anchors;
  test both modules, non-home parent/child combinations, fixed housings, wheel
  and adapter axes, grouped hardware partitions and exact membership.
- Reject wrong right rotation/reflection, y-offset, units/basis, pivot with
  correct home placement, sign, missing parent/part and stationary-case rotation.
  Fix tolerances from export precision before observing pass/fail.
- Exercise current→recorded→current and repeated/stale async switches, replay
  qpos, firing/stop/start, explode reset and current-load failure. Verify recorded
  world vertices/muzzle/body source and old file hashes remain unchanged.
- Capture actual landing/Play/Build current frames and first-ready/fallback
  handoff, then the existing hero-poster hook to a fresh candidate output.
  Inspect desktop/mobile framing and no old belly bay; no browser before lane
  and exact action packet review. Do not write a poster directly into public
  source before independent artifact acceptance.
- README SVG/model528/Build/current hero must identify the same accepted native
  collection; configuration, scene, receipt, displayed geometry and fallback
  poster must agree. Source metadata alone is insufficient.
- Preserve all leg/source/export/firmware/history/pad identities and existing
  engineering failures. Keep issue193 open until complete consumer adoption,
  current/historical CI ownership, source/artifact reviews and public verification.

Shared-kit architecture527 is a separate backlog. This plan extends existing
export, current/recorded renderer and validation contracts only.
