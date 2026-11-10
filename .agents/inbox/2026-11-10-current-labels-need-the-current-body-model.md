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
