# Repeated links to a model need one preview action in a BOM row

Date: 2026-10-29. Gyropup issue70. Production c9229dd had two visible Preview3D links per made/printed row: the thumbnail and named download pointed to the exact same file, and generic augmentation decorated both. A real browser probe reproduced this in Build (output_adapter/carriage_plate/body cut parts) and Progress (hip_frame/upper_link/wheel_link/etc.). There were no JavaScript errors.

Corrective rule: group only repeated exact model identities within one table row, prefer the named download for the preview action, and keep every original download. Different models and independent directory entries retain separate actions. Repeated augmentation, cloned rows and table re-rendering must not duplicate controls.

Evidence: four DOM tests in tools/test-model-links.mjs cover duplicate repair, repeat calls, clones, unrelated models/directories and excluded URLs/viewer pages. The real Build/Progress browser suite now compares each row's unique original-model set against its preview-action set before and after workstream rerendering.

Limits: grouping is by exact published file URL in a row. It does not assert that two differently named or differently formatted files contain identical geometry. This is a browsing correction, not mechanical completeness.
