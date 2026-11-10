# A current label does not establish a current body model

2026-11-10, issue #193. The owner found the old belly battery in the build
viewer and cad-agent homepage while expecting front/rear drop-in packs.

Evidence from main `f77fcde00880d4cedf8ca1a7edabd993714deaca`:

```text
rg -n 'bay_parts|battery in the belly' hardware/cad/body/body_{frame,layout}.py
body_frame.py:756: out.update(bb.bay_parts())
body_layout.py:295: # ... the battery in the belly (D65) ...
rg -n 'share the body' software/site/designer/robot_v2.js
179: // Current live presentation and recorded physics share the body ...
```

The canonical CAD source really retained the belly enclosure. The 95 CAD
inputs matched across the README model, collected guide meshes and cad-agent
homepage despite different producing revision labels. The earlier end-pack
handoff was a plan, not implemented geometry. Separately, the Sim's `current`
mode retained an archived interim body, and a legacy editor had procedural
body geometry. See the [source/preservation receipt](../plans/end-packs/baseline.json).

Corrective rule: trace actual producer inputs and model bytes before blaming
caches or restamping an image. Implement the desired body through its existing
CAD owner, bind every latest consumer to the accepted source closure, and keep
historical recordings on their original model. Verify actual rendered frames
as well as identity metadata. Preserve printed legs independently.

Limits: this diagnosis does not qualify the proposed battery interface,
supports, body strength or crouch motion. The implementation/testing plan in
[end-packs](../plans/end-packs/README.md) tracks those checks. No new geometry
or public artifact is accepted by this note alone.

## Model API changes need real consumer call paths

On 2026-11-10, independent review of PR #287 at `3df450b2` found three source
regressions despite passing numeric/serialization tests. The real quote entry
point eagerly read removed `floor_part`/`side_part` attributes even with
`--only bus_bar`; the real v2 simulation caller supplied no fresh output and
then read the obsolete fixed model path; the rig manifest derived sensor X
from the enlarged battery bounds and Z from old fallback estimates. Its camera
point was X294.775/Z188 mm rather than source X192.6/Z142.5 mm, and eyes Z200
instead of EYES.z182. These were caller/source-arithmetic failures, not native
solid or browser observations. The [independent review](https://github.com/Valpatel/gyropup/pull/287#pullrequestreview-5846585132)
retains the original controls.

Cause: the new producer API and wider overall extent were updated without
following each consumer's call and datum ownership. Corrective rule: inventory
aliases and subprocess callers, run the actual entry function with unrelated
native/browser/solver work explicitly doubled, propagate a fresh candidate root
and returned relative file paths, and derive sensor frames from their own CAD
source. An outer assembly bound is not a camera mounting datum. Keep electrical
board fronts separate from decorative outer-face bezels.

The corrected source routes quote features through the current zero-argument
holder factory. Simulation and wheel-curb callers keep models, scenarios,
evidence and videos under fresh candidate roots; the historical pad producer
rejects the current pad-less model before file reads or child regeneration.
Sensor controls execute the actual manifest writer and the actual source
camera/eyes arithmetic with both changed pack extents and changed sensor
datums. No browser quote, CAD construction or solver runs in these controls.

During harness construction, 8 controls passed and two fixtures stopped on
missing explicit-double attributes (`mujoco.mj_step`, `barrel_x1`); completing
those doubles changed no product source. The subsequent ten consumer controls
passed. Limits: these prove caller/data flow and source frames only. Genuine
native geometry, fit, physical qualification and delivered current-model
rendering remain separate. The strict 11-of-94 fit-source closure mismatch is
still an unresolved acceptance failure, not waived by unchanged leg geometry.
