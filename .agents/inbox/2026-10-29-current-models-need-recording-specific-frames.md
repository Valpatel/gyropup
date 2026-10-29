# Current geometry must not inherit an older recording's muzzle

2026-10-29: The landing and full robot loaded `exports/sim/v2/rig`'s 31-part older turret while the Orin bench loaded 48 detailed turret parts. Replacing the meshes alone would put archived projectiles at a different bore: old tilt-local muzzle x 194 mm/shaft 123 mm versus current x 147 mm/shaft 140 mm. The shared body's source is also an interim export: independent binary-STL bounds show deck z 216 mm, although current CAD parameters specify a later 30 mm riser.

Evidence: `python 3` binary-STL inspection of `body__interim_body.stl` returned bounds z 76..216; `body__turret_pan_bearing_5.stl` returned x−87.1500015..−22.1499996, y±32.5, giving the pan axis x−54.6500006. Exact input hashes are committed in `tests/fixtures/current-robot-mount.json`. `tools/test-current-model.mjs` captures actual world-transformed vertices, independently remaps the body datum, compares 46 poses and 90 operation frames, and deliberately breaks pivots, owners, signs, parentage and units.

Cause: a live presentation, physics recording and later CAD source were treated as interchangeable versions of one object. They encode different geometry and frames.

Rule: share current geometry on current interactive routes; preserve matching geometry for explicitly labeled historical recordings. Never generate a new geometry claim from an old physics/mass report. Derive body mounts from that snapshot's actual CAD datums, not the latest unrelated source or the manifest being tested. Async recorded loads must be atomic, retryable and unable to overwrite a newer live choice.

Limits: this change validates rendered motion and snapshot identity. No regenerated full-robot mass, physical clearance, FEA or hardware testing is implied. See `docs/validation/current-model.md` for the repeatable capture and negative controls.
