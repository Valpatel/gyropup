# Rendered mechanism frames

Canonical product convention and verification: [turret motion](../../docs/validation/turret-motion.md).

CAD millimetres `(x forward, y left, z up)` map to page metres `(y,z,x)`. Child joint origins are relative to their parent; exported vertices are relative to their owning joint. Rotating parts require independently checked physical datums; motor-case envelopes remain on the fixed parent. Keep effects, pocket balls and firing paths in the same documented frames.

Run `npm run test:turret` against a built local site or set `SITE_URL` to the deployed site. The test compares actual rendered vertices to independently audited CAD intent and must reject a deliberately displaced shaft. It does not certify physical fit or continuous collision clearance.

## Projectiles must meet visible geometry

Check the actual barrel STL mouth center on all three axes and its transformed bore axis, not only the muzzle's longitudinal coordinate. Validate journey and live emission after explosion sliders, paused stage skipping and compound pan/tilt. A correct assembled datum does not prove the mesh remains assembled during a demonstration. Reassemble before firing or entering the ball path; keep teaching-flight speed nominal when manual navigation skips wheel spin-up.

`tools/test-turret-frames.py` checks the three-axis mouth; `tools/test-turret-interactions.mjs` checks visible barrel/journey alignment after reassembly, paused-stage nominal speed and live firing after inspection.

## Current models and physics archives

Use the shared current renderer for current landing, playground and character routes. Recorded trajectories must retain their matching geometry and muzzle frames; lazy archive loads must not overwrite a newer live choice or discard a usable scene on failure. Body placement expectations come from the actual committed body snapshot's inspected CAD datums, not later source that added geometry absent from the snapshot. See [current model validation](../../docs/validation/current-model.md) and `npm run test:models` for cross-route, frame, failure and negative-control checks.
