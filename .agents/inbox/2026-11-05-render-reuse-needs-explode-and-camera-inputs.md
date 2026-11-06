# Reusing assembly pictures requires explode offsets and camera inputs

On 2026-11-05, issue #198 recorded that `tools/motor_day.py --no-render` compared
step parts but accepted changed explode offsets and camera vectors. Either changes
pixels while leaving part membership and item numbers intact.

The pre-fix guard compared `rendered['step_parts']` to `[list(st[1]) for st in STEPS]`.
Changing `STEPS[2][2]` (lift) or `STEPS[2][3]` (view) leaves that expression unchanged.

Corrective rule: persist JSON-normalized parts, ordered lift-map pairs and camera for every step, and
require equality before reusing pictures. Old parts-only metadata requires a genuine
render; never backfill a camera claim onto pixels without regenerating them.

Evidence, 2026-11-05:

```text
python3 tools/test-motor-day-render-inputs.py -v
Ran 9 tests in 0.003s
OK
```

Controls change parts, lift and view independently, reorder overlapping lift prefixes, reject legacy metadata and
changed BOM/counts, and allow the established editable-prose behavior. They execute
the actual guard extracted from the generator without importing the CAD runtime.

Limits: this guard covers only declared step membership/explode/camera and BOM
identity. Titles and instructions also appear in PNG captions, but remain intentionally editable under the existing prose-only reuse policy. It does not certify CAD source geometry, dimensions, printed fit or load
qualification. Existing evidence checks retain those separate responsibilities.
