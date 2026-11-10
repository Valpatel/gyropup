# Bind assembly instructions to their recipe as well as mesh identities

On 2026-11-09, read-only inspection of main `4866459e` found the live Build page had procurement/printing tables but no assembly view. All 53 logical additions in the retained turret sequence resolved to the current scene, yet `hardware/exports/turret/assembly/steps.json` step 8 and `docs/turret/turret-assembly.md` still specified the old zero-degree upper stop. The actual authored `hardware/cad/turret/turret_assembly.py` STEPS already specified +12/-25. Matching part names was therefore not freshness evidence.

The guide adapter consumes the literal current recipe without importing CAD, checks every original file against the pinned Git commit and scene digest, and bakes the existing neutral joint translations exactly once. It retains all original mesh triangle order/normals and explicit coverage/exclusions. Shared guide/view loading binds the recipe/model/mesh identities; product source metadata retains BOM and original producer identities. The historical page receives only a clear archival preface; its old payload is not rewritten or relabelled current.

Corrective rule: generate interactive state, written instructions and fresh illustrations from one bound recipe, retaining camera, frame, offsets, part-instance membership and source identity. Never combine a name-compatible old step export with newer geometry without checking actual recipe/picture freshness. Existing motor-day visual-input checks provide the same precedent for parts/offsets/camera. Do not alter unrelated geometry or relax manufacturing validators merely to publish instructions.

Limits: translation and viewer presentation cannot establish assembly access, fit, safe tightening, strength, feed behaviour or laser class. This lesson accompanies an implementation draft; actual browser/poster/release/publication results remain separate gates.


## Bind immutable instruction data; validate compiled HTML semantically

The first integrated static build rejected a raw `instructions.html` digest because the existing site compiler legitimately injects prototype notices, model links and content-versioned URLs into published HTML. That build remained failed. An initial browser probe was mistakenly started before its result was inspected; its exact owned service was stopped, its listener closed and no result accepted.

The corrected consumer binds unchanged `instructions.json` bytes to the guide and checks the compiled HTML against those same stage IDs, titles, prose, parts and poster identities. It permits normal compiler furniture outside the instruction content; it rejects a changed stage heading or stop instruction. The pure regression covers both legitimate compiler transformations and actual stale-title/prose mutations. This avoids both treating source HTML bytes as served HTML and dropping meaningful instruction freshness checks.
